#!/usr/bin/env python3
"""Delegate background tasks to Antigravity CLI. Requires Python 3.12+."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from agent_task_runtime import (
    Store,
    TaskError,
    encode,
    launch_worker,
    read_prompt,
    seconds,
)

FINISHED = {"completed", "blocked", "failed", "cancelled", "timed_out"}
FAILURES = {"blocked", "failed", "timed_out", "unresponsive"}


def default_state_dir() -> Path:
    if os.name == "nt":
        return (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            / "antigravity-tasks"
        )
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "antigravity-tasks"
    )


def conversation_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise TaskError(
            "Invalid conversation ID; use the session_id returned by a previous task"
        ) from exc


class TurnProcess:
    """One NDJSON turn; collect both channels before reporting completion."""

    def __init__(self, command: list[str], cwd: str, log_path: Path):
        self.messages: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.log_path = log_path
        self.log = log_path.open("ab")
        self.log_offset = self.log.tell()
        self.job = None
        self.closed = False
        self.writer: threading.Thread | None = None
        options = (
            {"creationflags": subprocess.CREATE_NO_WINDOW}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        try:
            self.process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
                encoding="utf-8",
                errors="strict",
                bufsize=1,
                **options,
            )
        except BaseException:
            self.log.close()
            raise
        if os.name == "nt":
            from agent_task_runtime import WindowsJob

            try:
                self.job = WindowsJob(self.process.pid)
            except BaseException:
                self.process.kill()
                self.process.wait(timeout=10)
                self.process.stdin.close()
                self.process.stdout.close()
                self.log.close()
                raise
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        try:
            for line in self.process.stdout:
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(
                    event.get("event"), str
                ):
                    raise TypeError("expected an event object")
                self.messages.put(("event", event))
        except (TypeError, ValueError, OSError) as exc:
            self.messages.put(("error", f"Could not read Antigravity stream: {exc}"))
        finally:
            self.messages.put(("eof", None))

    def prompt(self, text: str) -> None:
        # A peer that stops reading stdin must not block the worker's watchdog
        # or its command queue. The writer owns stdin until EOF or termination.
        self.writer = threading.Thread(
            target=self._send_prompt, args=(text,), daemon=True
        )
        self.writer.start()

    def _send_prompt(self, text: str) -> None:
        error = None
        try:
            self.process.stdin.write(
                encode({"event": "user", "message": {"content": text}}) + "\n"
            )
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            error = str(exc)
        finally:
            try:
                # EOF ends this process after its turn. Replies resume the ID.
                self.process.stdin.close()
            except (OSError, ValueError) as exc:
                error = error or str(exc)
        if error is not None:
            self.messages.put(
                (
                    "error",
                    f"Could not send the prompt to Antigravity: {error}; inspect agy.log",
                )
            )

    def close(self) -> None:
        if self.closed:
            return
        if self.job is not None:
            self.job.close()
        else:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.wait(timeout=10)
        if self.writer is not None:
            self.writer.join(timeout=2)
            if self.writer.is_alive():
                raise TaskError(
                    "Antigravity stdin did not close after stopping its process tree"
                )
        self.reader.join(timeout=2)
        if self.reader.is_alive():
            raise TaskError(
                "Antigravity stdout did not close after stopping its process tree"
            )
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()
        self.closed = True

    def diagnostics(self) -> tuple[str, str | None, str | None]:
        timeout = None
        error = None
        tail = ""
        with self.log_path.open("rb") as stream:
            stream.seek(self.log_offset)
            for raw in stream:
                line = raw.decode("utf-8", errors="replace")
                tail = (tail + line)[-8192:]
                if line.startswith("[agy] print timeout after "):
                    timeout = line.strip()
                elif line.startswith("error:"):
                    error = line.strip()
        return tail, timeout, error


class Worker:
    def __init__(self, store: Store, task_id: str):
        self.store = store
        self.config, self.state = store.get(task_id)
        self.state.pop("pending_permissions", None)
        self.state["session_id"] = self.config.get("conversation")
        self.state["denied_actions"] = []
        self.directory = store.root / task_id
        self.process: TurnProcess | None = None
        self.pending_prompt: str | None = self.config["prompt"]
        self.initialized = False
        self.result: dict[str, Any] | None = None
        self.started = 0.0
        self.turn_started: float | None = None
        self.result_at: float | None = None
        self.idle_since = time.monotonic()
        self.last_save = 0.0
        self.stop = False

    def save(self) -> None:
        self.store.save(self.state)
        self.last_save = time.monotonic()

    def record(self, value: dict[str, Any]) -> None:
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as log:
            log.write(
                encode({"time": time.time(), "turn": self.state["turn"], **value})
                + "\n"
            )

    def start_process(self) -> None:
        command = self.config["command"].copy()
        if self.state["session_id"]:
            command.extend(["--conversation", self.state["session_id"]])
        self.initialized = False
        self.result = None
        self.result_at = None
        self.turn_started = None
        self.started = time.monotonic()
        self.state.update(status="starting", text="", tools=[], denied_actions=[])
        for key in (
            "error",
            "stop_reason",
            "raw_status",
            "result",
            "stderr_tail",
            "exit_code",
            "tool_errors",
        ):
            self.state.pop(key, None)
        self.process = TurnProcess(
            command, self.config["cwd"], self.directory / "agy.log"
        )
        self.state["agy_pid"] = self.process.process.pid
        self.record({"type": "process_start", "pid": self.state["agy_pid"]})
        self.save()

    def handle(self, event: dict[str, Any]) -> None:
        self.record({"type": "event", "message": event})
        kind = event["event"]
        if kind == "init":
            if self.initialized or self.result is not None:
                raise TaskError("Antigravity sent an unexpected init event")
            session = conversation_id(event.get("conversation_id"))
            expected = self.state["session_id"]
            if expected and expected != session:
                raise TaskError(
                    "Antigravity resumed a different conversation; no prompt was sent"
                )
            init = event.get("init")
            if not isinstance(init, dict) or not isinstance(init.get("cwd"), str):
                raise TaskError(
                    "Antigravity init did not identify its working directory"
                )
            if os.path.normcase(os.path.realpath(init["cwd"])) != os.path.normcase(
                self.config["cwd"]
            ):
                raise TaskError(
                    "Antigravity reported a different working directory; no prompt was sent"
                )
            self.initialized = True
            self.state.update(session_id=session, init=init)
            self.state.update(status="running", turn=self.state["turn"] + 1)
            prompt = self.pending_prompt
            self.pending_prompt = None
            self.record({"type": "prompt", "text": prompt})
            self.turn_started = time.monotonic()
            self.process.prompt(prompt)
            self.save()
        elif kind == "step_update":
            step = event.get("step_update")
            if (
                not self.initialized
                or self.result is not None
                or not isinstance(step, dict)
            ):
                raise TaskError("Antigravity sent an unexpected step update")
            if step.get("conversation_id") != self.state["session_id"]:
                raise TaskError("Antigravity step belongs to a different conversation")
            text = step.get("text_delta", "")
            if not isinstance(text, str):
                raise TaskError("Antigravity sent an invalid text delta")
            if step.get("step_type") == "agent_response":
                self.state["text"] += text
            if step.get("step_type") == "tool":
                summary = {
                    key: step[key]
                    for key in ("step_index", "tool_name", "state")
                    if key in step
                }
                info = step.get("tool_info", {})
                if not isinstance(info, dict):
                    raise TaskError("Antigravity sent invalid tool information")
                if info.get("error"):
                    summary["error"] = info["error"]
                    self.state.setdefault("tool_errors", []).append(summary.copy())
                    del self.state["tool_errors"][:-10]
                tools = self.state["tools"]
                old = next(
                    (
                        t
                        for t in tools
                        if t.get("step_index") == summary.get("step_index")
                    ),
                    None,
                )
                if old is None:
                    tools.append(summary)
                    del tools[:-10]
                else:
                    old.update(summary)
        elif kind == "result":
            result = event.get("result")
            if (
                self.result is not None
                or not isinstance(result, dict)
                or not isinstance(result.get("status"), str)
            ):
                raise TaskError("Antigravity sent an invalid or duplicate result")
            session = result.get("conversation_id")
            if session and session != self.state["session_id"]:
                raise TaskError(
                    "Antigravity result belongs to a different conversation"
                )
            if result["status"] == "SUCCESS" and not self.initialized:
                raise TaskError(
                    "Antigravity reported success before initializing the conversation"
                )
            if not isinstance(result.get("response", ""), str):
                raise TaskError("Antigravity returned an invalid response")
            denied = result.get("denied_actions", [])
            if not isinstance(denied, list) or any(
                not isinstance(item, dict) for item in denied
            ):
                raise TaskError("Antigravity returned invalid denied_actions")
            self.result = result
            self.result_at = time.monotonic()
            self.state.update(
                result=result,
                raw_status=result["status"],
                text=result.get("response") or self.state["text"],
                denied_actions=denied,
            )
            self.pending_prompt = None
            if self.process.writer is None and not self.process.process.stdin.closed:
                self.process.process.stdin.close()
        else:
            # Keep unknown observational events in the log without assigning
            # them completion, permission, or execution semantics.
            self.state["last_unknown_event"] = kind

    def drain(self, limit: int | None = 64) -> None:
        count = 0
        while limit is None or count < limit:
            try:
                kind, value = self.process.messages.get_nowait()
            except queue.Empty:
                return
            if kind == "error":
                raise TaskError(value)
            if kind == "event":
                self.handle(value)
            count += 1

    def finish(self) -> None:
        code = self.process.process.returncode
        self.process.close()
        self.drain(limit=None)
        tail, timeout, error = self.process.diagnostics()
        self.state.update(exit_code=code, stderr_tail=tail)
        self.process = None
        self.idle_since = time.monotonic()
        self.pending_prompt = None
        result = self.result or {}
        raw = result.get("status")
        if timeout:
            self.state.update(
                status="timed_out", stop_reason="print_timeout", error=timeout
            )
        elif code != 0 or raw != "SUCCESS" or error:
            status = "cancelled" if raw in {"CANCELED", "INTERRUPTED"} else "failed"
            self.state.update(
                status=status,
                stop_reason=raw or "missing_result",
                error=result.get("error")
                or error
                or f"Antigravity exited {code} with status {raw!r}; inspect agy.log",
            )
        elif self.state["denied_actions"]:
            self.state.update(
                status="blocked",
                stop_reason="permission_denied",
                error="Antigravity denied tool actions; inspect denied_actions and configure scoped permissions in Antigravity before continuing",
            )
        elif (
            not result.get("response", "").strip() and "structured_output" not in result
        ):
            self.state.update(
                status="failed",
                stop_reason="empty_response",
                error="Antigravity returned an empty response; inspect tools and agy.log before retrying",
            )
        else:
            self.state.update(status="completed", stop_reason="SUCCESS")
        if not self.initialized:
            self.stop = True
        self.save()

    def terminate(self, status: str, reason: str, error: str | None = None) -> None:
        self.state.update(status=status, stop_reason=reason, closing=True)
        if error:
            self.state["error"] = error
        self.stop = True
        self.save()

    def control(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.stop:
            raise TaskError("Task is closing")
        action = payload["action"]
        if action == "reply":
            if (
                self.process is not None
                or self.pending_prompt is not None
                or self.state["status"] not in FINISHED
            ):
                raise TaskError("Wait for the current turn to finish before replying")
            self.pending_prompt = payload["prompt"]
            self.state["status"] = "starting"
        elif action == "cancel":
            if self.process is None and self.pending_prompt is None:
                raise TaskError(
                    "No active turn to cancel; use close to release an idle task"
                )
            self.terminate("cancelled", "forced_stop")
        elif action == "close":
            if self.process is not None or self.pending_prompt is not None:
                self.terminate("cancelled", "forced_stop")
            else:
                self.state.update(closing=True, close_reason="requested")
                self.stop = True
        else:
            raise TaskError(f"Unsupported worker command: {action}")
        self.save()
        return self.state.copy()

    def run(self) -> None:
        self.state["worker_pid"] = os.getpid()
        self.save()
        try:
            while not self.stop:
                for command_id, raw in self.store.commands(self.state["task_id"]):
                    try:
                        response = self.control(json.loads(raw))
                    except TaskError as exc:
                        response = {"command_error": str(exc)}
                    self.store.acknowledge(command_id, response)
                if self.stop:
                    break
                if self.process is None and self.pending_prompt is not None:
                    self.start_process()
                if self.process is not None:
                    self.drain()
                    now = time.monotonic()
                    if (
                        self.result is None
                        and self.turn_started is None
                        and now - self.started >= self.config["startup_timeout"]
                    ):
                        self.terminate(
                            "timed_out",
                            "startup_timeout",
                            "Antigravity did not initialize before --startup-timeout; no prompt was sent",
                        )
                    elif (
                        self.result is None
                        and self.turn_started is not None
                        and now - self.turn_started >= self.config["turn_timeout"]
                    ):
                        self.terminate(
                            "timed_out",
                            "turn_timeout",
                            "Turn exceeded --turn-timeout; its process tree was stopped",
                        )
                    elif self.process.process.poll() is not None:
                        self.finish()
                    elif (
                        self.result_at is not None
                        and now - self.result_at >= self.config["exit_timeout"]
                    ):
                        self.terminate(
                            "timed_out",
                            "exit_timeout",
                            "Antigravity returned a result but did not exit before --exit-timeout",
                        )
                elif time.monotonic() - self.idle_since >= self.config["idle_timeout"]:
                    self.state["close_reason"] = "idle_timeout"
                    self.stop = True
                if time.monotonic() - self.last_save >= 1:
                    self.save()
                time.sleep(0.05)
        except Exception as exc:
            traceback.print_exc()
            self.state.update(
                status="failed", error=str(exc), stop_reason="client_error"
            )
            raise
        finally:
            try:
                if self.process is not None:
                    self.process.close()
                    tail, _, _ = self.process.diagnostics()
                    self.state.update(
                        stderr_tail=tail, exit_code=self.process.process.returncode
                    )
            except Exception as exc:
                traceback.print_exc()
                self.state.update(
                    status="failed", error=f"Could not clean up Antigravity: {exc}"
                )
                raise
            finally:
                self.state.update(closed=True, closing=False)
                self.save()


def launch(store: Store, config: dict[str, Any]) -> dict[str, Any]:
    return launch_worker(store, config, Path(__file__))


def executable(value: str | None) -> str:
    found = shutil.which(value or "agy")
    if found:
        return str(Path(found).resolve())
    if value is None:
        candidate = (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            / "agy/bin/agy.exe"
            if os.name == "nt"
            else Path.home() / ".local/bin/agy"
        )
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
    raise TaskError(
        "Antigravity CLI executable not found; install agy or pass --agy with its path"
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    root.add_argument(
        "--state-dir",
        type=Path,
        default=default_state_dir(),
        help="task storage directory (reuse it across commands)",
    )
    root.add_argument("--worker", help=argparse.SUPPRESS)
    sub = root.add_subparsers(dest="action")
    start = sub.add_parser(
        "start",
        help="start a background task",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    start.add_argument(
        "--cwd",
        type=Path,
        required=True,
        help="task working directory and Antigravity workspace",
    )
    start.add_argument("--agy", help="Antigravity executable name or path")
    start.add_argument(
        "--conversation", help="explicitly resume a previous session_id in a new task"
    )
    start.add_argument(
        "--model",
        help="per-task model override; otherwise inherit Antigravity configuration",
    )
    start.add_argument(
        "--effort",
        choices=["low", "medium", "high"],
        help="per-task reasoning effort override",
    )
    start.add_argument(
        "--mode",
        choices=["accept-edits", "plan"],
        help="per-task execution mode; plan is not an enforced read-only mode",
    )
    start.add_argument(
        "--sandbox",
        action="store_true",
        help="enable Antigravity terminal sandbox for this task",
    )
    start.add_argument(
        "--dangerously-skip-permissions",
        action="store_true",
        help="explicitly auto-approve all tools for this task",
    )
    for name, default, help_text in [
        ("startup", 60, "seconds for each AGY process to initialize"),
        ("turn", 900, "seconds per turn before stopping its process tree"),
        ("exit", 10, "seconds for AGY to exit after its final result"),
        ("idle", 1800, "seconds to retain a finished task for follow-ups"),
    ]:
        start.add_argument(
            f"--{name}-timeout", type=seconds, default=default, help=help_text
        )
    reply = sub.add_parser("reply", help="continue a finished, open task")
    reply.add_argument("task_id")
    for item in (start, reply):
        prompts = item.add_mutually_exclusive_group()
        prompts.add_argument("--prompt", help="prompt text; defaults to UTF-8 stdin")
        prompts.add_argument(
            "--prompt-file", type=Path, help="UTF-8 prompt file (BOM accepted)"
        )
    for name, help_text in [
        ("status", "read task state and the latest result"),
        ("wait", "wait for a finished turn without cancelling it"),
        ("cancel", "stop active work and close the task"),
        ("close", "release the task; stop active work if necessary"),
    ]:
        item = sub.add_parser(name, help=help_text)
        item.add_argument("task_id")
        if name == "wait":
            item.add_argument(
                "--timeout",
                type=seconds,
                default=30,
                help="seconds to wait (default: 30); does not stop AGY",
            )
    return root


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if not args.action and not args.worker:
        cli.error("a command is required")
    store = None
    try:
        store = Store(args.state_dir)
        if args.worker:
            Worker(store, args.worker).run()
            return 0
        if args.action == "start":
            cwd = args.cwd.expanduser().resolve(strict=True)
            if not cwd.is_dir():
                raise TaskError("--cwd must be a directory")
            command = [
                executable(args.agy),
                "--add-dir",
                str(cwd),
                "--input-format",
                "stream-json",
                "--output-format",
                "stream-json",
            ]
            # Our watchdog fires first. Native timeouts can report SUCCESS with
            # partial output, so their stderr is still checked after process exit.
            command.extend(
                [
                    "--print-timeout",
                    f"{args.startup_timeout + args.turn_timeout + 60:g}s",
                ]
            )
            for key in ("model", "effort", "mode"):
                if getattr(args, key):
                    command.extend(["--" + key, getattr(args, key)])
            for key in ("sandbox", "dangerously_skip_permissions"):
                if getattr(args, key):
                    command.append("--" + key.replace("_", "-"))
            result = launch(
                store,
                {
                    "cwd": str(cwd),
                    "command": command,
                    "prompt": read_prompt(args),
                    "conversation": conversation_id(args.conversation)
                    if args.conversation
                    else None,
                    **{
                        f"{key}_timeout": getattr(args, f"{key}_timeout")
                        for key in ("startup", "turn", "idle", "exit")
                    },
                },
            )
        elif args.action in {"status", "wait"}:
            deadline = time.monotonic() + (args.timeout if args.action == "wait" else 0)
            while True:
                result = store.status(args.task_id)
                if (
                    result["closed"]
                    or (
                        not result.get("closing")
                        and result["status"] in FINISHED | {"unresponsive"}
                    )
                    or time.monotonic() >= deadline
                ):
                    break
                time.sleep(0.1)
        else:
            payload = {"action": args.action}
            if args.action == "reply":
                payload["prompt"] = read_prompt(args)
            result = store.submit(args.task_id, payload)
        print(encode(result))
        return int(result.get("status") in FAILURES)
    except (TaskError, OSError, ValueError, sqlite3.Error) as exc:
        print(encode({"error": str(exc)}))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
