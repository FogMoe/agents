#!/usr/bin/env python3
"""Delegate background tasks to Grok Build over ACP. Requires Python 3.12+."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import time
import traceback
from pathlib import Path
from typing import Any

from acp_client import ACPClient, ACPError
from agent_task_runtime import (
    Store,
    TaskError,
    encode,
    launch_worker,
    read_prompt,
    seconds,
)

FINISHED = {"completed", "cancelled", "failed", "timed_out"}


def default_state_dir() -> Path:
    if os.name == "nt":
        return (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            / "grok-acp"
        )
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "grok-acp"
    )


class Worker:
    def __init__(self, store: Store, task_id: str):
        self.store = store
        self.config, self.state = store.get(task_id)
        self.directory = store.root / task_id
        self.client: ACPClient | None = None
        self.active_request: int | None = None
        self.responses: dict[int, dict[str, Any]] = {}
        self.permissions: dict[str, dict[str, Any]] = {}
        self.turn_started = 0.0
        self.idle_since = time.monotonic()
        self.cancel_deadline: float | None = None
        self.cancel_status = "cancelled"
        self.closing = False
        self.stop = False
        self.last_save = 0.0

    def save(self) -> None:
        self.state["pending_permissions"] = list(self.permissions.values())
        self.store.save(self.state)
        self.last_save = time.monotonic()

    def record(self, message: dict[str, Any]) -> None:
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                encode({"time": time.time(), "turn": self.state["turn"], **message})
                + "\n"
            )

    def rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.stop:
            raise TaskError("Task closed during initialization")
        request_id = self.client.request(method, params)
        deadline = time.monotonic() + self.config["startup_timeout"]
        while request_id not in self.responses:
            if self.stop:
                raise TaskError("Task closed during initialization")
            if time.monotonic() >= deadline:
                raise TaskError(
                    f"Grok did not answer {method} before --startup-timeout"
                )
            self.pump()
        message = self.responses.pop(request_id)
        if "error" in message:
            error = message["error"]
            raise ACPError(f"{method}: {error.get('message', error)}")
        return message.get("result", {})

    def initialize(self) -> None:
        self.client = ACPClient(
            self.config["command"], self.config["cwd"], self.directory / "grok.log"
        )
        self.state["grok_pid"] = self.client.process.pid
        init = self.rpc(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {},
                "clientInfo": {"name": "grok-cli-skill", "version": "1"},
            },
        )
        if init.get("protocolVersion") != 1:
            raise TaskError("Grok negotiated an unsupported ACP protocol version")
        self.state["agent_version"] = init.get("_meta", {}).get("agentVersion")
        methods = {m["id"] for m in init.get("authMethods", [])}
        method = init.get("_meta", {}).get("defaultAuthMethodId")
        if method in {"cached_token", "xai.api_key"} and method in methods:
            self.rpc("authenticate", {"methodId": method, "_meta": {"headless": True}})
            self.state["auth_method"] = method
        elif method in {"grok.com", "oidc"}:
            raise TaskError(
                "Grok requires interactive login; run grok login, then start a new task"
            )
        session = self.rpc("session/new", {"cwd": self.config["cwd"], "mcpServers": []})
        self.state["session_id"] = session["sessionId"]
        self.state["model"] = session.get("models", {}).get("currentModelId")
        self.state["config_options"] = session.get("configOptions", [])
        self.begin_turn(self.config["prompt"])

    def begin_turn(self, prompt: str) -> None:
        if self.stop:
            raise TaskError("Task closed before the prompt was sent")
        if self.active_request is not None:
            raise TaskError(
                "A turn is already running; wait or cancel it before replying"
            )
        self.state.update(
            status="running", text="", tools=[], turn=self.state["turn"] + 1
        )
        for key in ("error", "stop_reason", "cancel_requested"):
            self.state.pop(key, None)
        self.cancel_deadline = None
        self.cancel_status = "cancelled"
        self.turn_started = time.monotonic()
        self.record({"type": "prompt", "text": prompt})
        self.active_request = self.client.request(
            "session/prompt",
            {
                "sessionId": self.state["session_id"],
                "prompt": [{"type": "text", "text": prompt}],
            },
        )
        self.save()

    def cancel(self, status: str = "cancelled") -> None:
        if self.active_request is None:
            raise TaskError("No active turn to cancel")
        if self.cancel_deadline is not None:
            return
        self.cancel_status = status
        for permission in self.permissions.values():
            self.client.send(
                {
                    "id": permission["rpc_id"],
                    "result": {"outcome": {"outcome": "cancelled"}},
                }
            )
        self.permissions.clear()
        self.client.notify("session/cancel", {"sessionId": self.state["session_id"]})
        self.cancel_deadline = time.monotonic() + 10
        self.state.update(status="cancelling", cancel_requested=True)
        self.save()

    def control(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload["action"]
        if self.closing:
            raise TaskError("Task is closing")
        if action == "close":
            self.closing = True
            self.state["closing"] = True
            if self.active_request is not None:
                self.cancel()
            else:
                self.stop = True
        elif action == "cancel":
            if self.state["status"] == "starting":
                self.state["status"] = "cancelled"
                self.stop = True
            else:
                self.cancel()
        elif action == "reply":
            if self.state["status"] not in FINISHED:
                raise TaskError("Wait for the current turn to finish before replying")
            self.begin_turn(payload["prompt"])
        elif action == "permission":
            permission = self.permissions.get(payload["request_id"])
            if permission is None:
                raise TaskError("Permission request is no longer pending; check status")
            options = {o["optionId"] for o in permission["options"]}
            if payload["option_id"] not in options:
                raise TaskError(
                    "Unknown option ID; select an option from pending_permissions"
                )
            self.client.send(
                {
                    "id": permission["rpc_id"],
                    "result": {
                        "outcome": {
                            "outcome": "selected",
                            "optionId": payload["option_id"],
                        }
                    },
                }
            )
            del self.permissions[payload["request_id"]]
            self.state["status"] = "needs_approval" if self.permissions else "running"
        else:
            raise TaskError(f"Unknown worker command: {action}")
        self.save()
        return self.state.copy()

    def handle(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method is None:
            if (
                message.get("id") == self.active_request
                and self.active_request is not None
            ):
                self.finish(message)
            else:
                self.responses[message.get("id")] = message
            return
        params = message.get("params", {})
        if method == "session/request_permission" and "id" in message:
            if (
                params.get("sessionId") != self.state["session_id"]
                or self.cancel_deadline is not None
                or self.active_request is None
            ):
                self.client.send(
                    {
                        "id": message["id"],
                        "result": {"outcome": {"outcome": "cancelled"}},
                    }
                )
                return
            request_id = str(message["id"])
            self.permissions[request_id] = {
                "request_id": request_id,
                "rpc_id": message["id"],
                "tool_call": params.get("toolCall", {}),
                "options": params.get("options", []),
            }
            self.state["status"] = "needs_approval"
            self.record(message)
            self.save()
        elif "id" in message:
            # No filesystem or terminal callbacks are advertised. Grok owns
            # execution; a new callback must be implemented before advertising it.
            self.client.send(
                {
                    "id": message["id"],
                    "error": {
                        "code": -32601,
                        "message": f"Client does not implement {method}",
                    },
                }
            )
        elif (
            method == "session/update"
            and params.get("sessionId") == self.state["session_id"]
        ):
            update = params.get("update", {})
            kind = update.get("sessionUpdate")
            if kind == "agent_message_chunk":
                content = update.get("content", {})
                if content.get("type") == "text":
                    self.state["text"] += content.get("text", "")
            elif kind in {"tool_call", "tool_call_update"}:
                summary = {
                    key: update[key]
                    for key in ("toolCallId", "title", "kind", "status", "locations")
                    if key in update
                }
                tools = self.state["tools"]
                existing = next(
                    (
                        t
                        for t in tools
                        if t.get("toolCallId") == update.get("toolCallId")
                    ),
                    None,
                )
                if existing is None:
                    tools.append(summary)
                    del tools[:-10]
                else:
                    existing.update(summary)
            elif kind == "config_option_update":
                self.state["config_options"] = update.get("configOptions", [])
                for option in self.state["config_options"]:
                    if option.get("id") == "model":
                        self.state["model"] = option.get("currentValue")
            self.record(message)

    def finish(self, message: dict[str, Any]) -> None:
        self.active_request = None
        self.permissions.clear()
        self.idle_since = time.monotonic()
        self.record({"type": "turn_result", "response": message})
        if "error" in message:
            self.state.update(status="failed", error=message["error"])
        else:
            reason = message.get("result", {}).get("stopReason")
            status = (
                "completed"
                if reason == "end_turn"
                else "cancelled"
                if reason == "cancelled"
                else "failed"
            )
            self.state.update(status=status, stop_reason=reason)
            if status == "failed":
                self.state["error"] = (
                    f"Grok stopped with {reason!r}; inspect the partial result before retrying"
                )
        if self.cancel_deadline is not None and self.cancel_status == "timed_out":
            self.state.update(
                status="timed_out",
                error="Turn exceeded --turn-timeout and was cancelled",
            )
        self.cancel_deadline = None
        if self.closing:
            self.stop = True
        self.save()

    def pump(self) -> None:
        for command_id, raw in self.store.commands(self.state["task_id"]):
            try:
                result = self.control(json.loads(raw))
            except TaskError as exc:
                result = {"command_error": str(exc)}
            self.store.acknowledge(command_id, result)
        if self.stop:
            return
        message = self.client.receive()
        if message is not None:
            self.handle(message)
        now = time.monotonic()
        if (
            self.active_request is not None
            and now - self.turn_started > self.config["turn_timeout"]
        ):
            self.cancel("timed_out")
        if self.cancel_deadline is not None and now >= self.cancel_deadline:
            self.state.update(
                status=self.cancel_status,
                stop_reason="forced_stop",
                error="Grok did not acknowledge cancellation; its process tree was stopped",
            )
            self.stop = True
        if now - self.last_save >= 1:
            self.save()

    def run(self) -> None:
        self.state["worker_pid"] = os.getpid()
        self.save()
        try:
            self.initialize()
            while not self.stop:
                self.pump()
                if (
                    self.active_request is None
                    and time.monotonic() - self.idle_since
                    >= self.config["idle_timeout"]
                ):
                    self.state["close_reason"] = "idle_timeout"
                    break
        except Exception as exc:
            traceback.print_exc()
            if self.state["status"] != "cancelled":
                self.state.update(status="failed", error=str(exc))
            raise
        finally:
            try:
                if self.client is not None:
                    self.client.close()
            finally:
                self.permissions.clear()
                self.state["closed"] = True
                self.state["closing"] = False
                self.save()


def launch(store: Store, config: dict[str, Any]) -> dict[str, Any]:
    return launch_worker(store, config, Path(__file__))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--state-dir",
        type=Path,
        default=default_state_dir(),
        help="task storage directory (reuse it across commands)",
    )
    root.add_argument("--worker", help=argparse.SUPPRESS)
    sub = root.add_subparsers(dest="action")
    start = sub.add_parser(
        "start", help="start a background Grok session and return its task ID"
    )
    start.add_argument(
        "--cwd", type=Path, required=True, help="working directory for Grok"
    )
    start.add_argument("--grok", default="grok", help="Grok executable name or path")
    start.add_argument("--model", help="override model for this task only")
    start.add_argument("--effort", help="override reasoning effort for this task only")
    start.add_argument(
        "--permission-mode",
        choices=[
            "default",
            "acceptEdits",
            "auto",
            "dontAsk",
            "bypassPermissions",
            "plan",
        ],
        help="explicit Grok permission override; otherwise inherit configuration",
    )
    start.add_argument(
        "--sandbox",
        help="explicit Grok sandbox profile; otherwise inherit configuration",
    )
    start.add_argument(
        "--startup-timeout",
        type=seconds,
        default=30,
        help="seconds allowed per ACP setup request",
    )
    start.add_argument(
        "--turn-timeout",
        type=seconds,
        default=900,
        help="seconds per turn before requesting cancellation",
    )
    start.add_argument(
        "--idle-timeout",
        type=seconds,
        default=1800,
        help="seconds to keep a completed session open for replies",
    )
    reply = sub.add_parser(
        "reply", help="send another prompt to an open, finished task"
    )
    for item in (start, reply):
        prompts = item.add_mutually_exclusive_group()
        prompts.add_argument(
            "--prompt", help="task text; defaults to reading UTF-8 stdin"
        )
        prompts.add_argument(
            "--prompt-file", type=Path, help="UTF-8 file containing task text"
        )
    reply.add_argument("task_id")
    for name, help_text in [
        ("status", "read the latest state and response"),
        ("wait", "wait for a result or permission request"),
        ("cancel", "cancel the current turn; keep the session if Grok acknowledges"),
        ("close", "cancel active work and release the session"),
        ("permission", "answer one pending permission request"),
    ]:
        item = sub.add_parser(name, help=help_text)
        item.add_argument("task_id")
        if name == "wait":
            item.add_argument(
                "--timeout",
                type=seconds,
                default=30,
                help="maximum seconds to wait; does not cancel Grok",
            )
        if name == "permission":
            item.add_argument("--request-id", required=True)
            item.add_argument("--option-id", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if not args.action and not args.worker:
        cli.error("a command is required")
    store: Store | None = None
    try:
        store = Store(args.state_dir)
        if args.worker:
            Worker(store, args.worker).run()
            return 0
        if args.action == "start":
            cwd = args.cwd.expanduser().resolve(strict=True)
            if not cwd.is_dir():
                raise TaskError("--cwd must be a directory")
            grok = shutil.which(args.grok)
            if grok is None:
                raise TaskError(
                    "Grok Build executable not found; install Grok or pass --grok with its path"
                )
            command = [str(Path(grok).resolve())]
            for key, flag in [
                ("permission_mode", "--permission-mode"),
                ("sandbox", "--sandbox"),
            ]:
                if getattr(args, key):
                    command.extend([flag, getattr(args, key)])
            command.extend(["agent", "--no-leader"])
            for key, flag in [("model", "--model"), ("effort", "--reasoning-effort")]:
                if getattr(args, key):
                    command.extend([flag, getattr(args, key)])
            command.append("stdio")
            result = launch(
                store,
                {
                    "cwd": str(cwd),
                    "command": command,
                    "prompt": read_prompt(args),
                    "startup_timeout": args.startup_timeout,
                    "turn_timeout": args.turn_timeout,
                    "idle_timeout": args.idle_timeout,
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
                        and result["status"]
                        in FINISHED | {"needs_approval", "unresponsive"}
                    )
                    or time.monotonic() >= deadline
                ):
                    break
                time.sleep(0.1)
        else:
            payload = {"action": args.action}
            if args.action == "reply":
                payload["prompt"] = read_prompt(args)
            elif args.action == "permission":
                payload.update(request_id=args.request_id, option_id=args.option_id)
            result = store.submit(args.task_id, payload)
        print(encode(result))
        return (
            1 if result.get("status") in {"failed", "timed_out", "unresponsive"} else 0
        )
    except (TaskError, OSError, ValueError, sqlite3.Error) as exc:
        print(encode({"error": str(exc)}))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
