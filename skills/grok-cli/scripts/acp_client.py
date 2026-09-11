"""Line-delimited ACP transport for the bundled Grok task runner."""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any


class ACPError(RuntimeError):
    pass


class ACPClient:
    def __init__(self, command: list[str], cwd: str, log_path: Path):
        self.messages: queue.Queue[dict[str, Any] | Exception] = queue.Queue()
        self.next_id = 0
        self.log = log_path.open("ab")
        self.job = None
        options: dict[str, Any] = {}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        try:
            self.process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.log,
                encoding="utf-8",
                errors="strict",
                text=True,
                bufsize=1,
                **options,
            )
        except BaseException:
            self.log.close()
            raise
        if os.name == "nt":
            from windows_job import WindowsJob

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
                message = json.loads(line)
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise ACPError("Grok returned an invalid JSON-RPC message")
                self.messages.put(message)
        except (ACPError, ValueError, OSError) as exc:
            self.messages.put(ACPError(f"Could not read Grok ACP output: {exc}"))
        finally:
            self.messages.put(ACPError("Grok closed its ACP output; inspect grok.log"))

    def send(self, message: dict[str, Any]) -> None:
        try:
            self.process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise ACPError("Could not send to Grok; inspect grok.log") from exc

    def request(self, method: str, params: dict[str, Any]) -> int:
        self.next_id += 1
        self.send({"id": self.next_id, "method": method, "params": params})
        return self.next_id

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self.send({"method": method, "params": params})

    def receive(self, timeout: float = 0.1) -> dict[str, Any] | None:
        try:
            message = self.messages.get(timeout=timeout)
        except queue.Empty:
            return None
        if isinstance(message, Exception):
            raise message
        return message

    def close(self) -> None:
        # Kill only this client's process tree, including tools still running
        # after a stalled cancellation. Never target another Grok session.
        if self.job is not None:
            self.job.close()
        else:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.wait(timeout=10)
        self.reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()
