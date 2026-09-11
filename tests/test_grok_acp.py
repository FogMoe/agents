from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/grok-cli/scripts/grok.py"
FIXTURE = ROOT / "tests/fixtures/grok_acp_agent.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("grok_task_runner", SCRIPT)
grok = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grok)


class GrokTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = grok.Store(self.root / "state")
        self.tasks = []

    def tearDown(self):
        for task_id in self.tasks:
            state = self.store.status(task_id)
            if not state["closed"]:
                self.store.submit(task_id, {"action": "close"})
                self.until(task_id, lambda s: s["closed"], timeout=20)
        self.store.close()
        # The worker publishes its final state immediately before interpreter exit.
        for attempt in range(40):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)

    def start(self, prompt="hello", mode="normal", **kwargs):
        config = {
            "cwd": str(self.root),
            "command": [
                sys.executable,
                str(FIXTURE),
                str(self.root / "trace.jsonl"),
                mode,
            ],
            "prompt": prompt,
            "startup_timeout": 3,
            "turn_timeout": 30,
            "idle_timeout": 60,
            **kwargs,
        }
        state = grok.launch(self.store, config)
        self.tasks.append(state["task_id"])
        return state["task_id"]

    def until(self, task_id, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.store.status(task_id)
            if predicate(state):
                return state
            time.sleep(0.05)
        self.fail(f"Timed out: {state}")

    def finished(self, task_id):
        return self.until(task_id, lambda s: s["status"] in grok.FINISHED)

    def trace(self):
        return [
            json.loads(line)
            for line in (self.root / "trace.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def cli(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--state-dir", str(self.store.root), *args],
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=15,
            check=False,
        )
        return result, json.loads(result.stdout)

    def test_background_task_streams_unicode_and_reuses_session(self):
        task = self.start("你好\nquoted ` $() text")
        first = self.finished(task)
        self.assertEqual(first["text"], "turn 1: 你好\nquoted ` $() text")
        self.assertFalse(first["closed"])
        reply = self.store.submit(task, {"action": "reply", "prompt": "follow-up"})
        self.assertEqual(reply["turn"], 2)
        second = self.finished(task)
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(second["text"], "turn 2: follow-up")
        trace = self.trace()
        self.assertEqual(sum(m.get("method") == "session/new" for m in trace), 1)
        self.assertEqual(trace[0]["params"]["clientCapabilities"], {})
        auth = next(m for m in trace if m.get("method") == "authenticate")
        self.assertEqual(auth["params"]["methodId"], "cached_token")
        self.assertEqual(auth["params"]["_meta"], {"headless": True})

    def test_permission_options_are_validated_and_all_requests_handled(self):
        task = self.start("permission")
        state = self.until(task, lambda s: len(s["pending_permissions"]) == 2)
        self.assertEqual(state["status"], "needs_approval")
        with self.assertRaises(grok.TaskError):
            self.store.submit(
                task,
                {"action": "permission", "request_id": "801", "option_id": "invented"},
            )
        self.store.submit(
            task, {"action": "permission", "request_id": "801", "option_id": "yes"}
        )
        self.assertEqual(self.store.status(task)["status"], "needs_approval")
        with self.assertRaises(grok.TaskError):
            self.store.submit(
                task, {"action": "permission", "request_id": "801", "option_id": "yes"}
            )
        self.store.submit(
            task, {"action": "permission", "request_id": "802", "option_id": "no"}
        )
        state = self.finished(task)
        self.assertEqual(state["text"], "permissions handled")
        self.assertFalse(state["pending_permissions"])

    def test_cancel_resolves_permissions_and_allows_followup(self):
        task = self.start("permission")
        self.until(task, lambda s: len(s["pending_permissions"]) == 2)
        self.store.submit(task, {"action": "cancel"})
        state = self.finished(task)
        self.assertEqual(state["status"], "cancelled")
        self.assertFalse(state["closed"])
        outcomes = [
            m["result"]["outcome"]["outcome"]
            for m in self.trace()
            if m.get("id") in {801, 802}
        ]
        self.assertEqual(outcomes, ["cancelled", "cancelled"])
        self.store.submit(task, {"action": "reply", "prompt": "after cancellation"})
        self.assertEqual(self.finished(task)["text"], "turn 2: after cancellation")

    def test_wait_timeout_does_not_cancel_and_running_reply_is_rejected(self):
        task = self.start("hold")
        self.until(task, lambda s: s["status"] == "running")
        result, state = self.cli("wait", task, "--timeout", "0.2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(state["status"], "running")
        with self.assertRaises(grok.TaskError):
            self.store.submit(task, {"action": "reply", "prompt": "overlap"})
        self.assertFalse(any(m.get("method") == "session/cancel" for m in self.trace()))

    def test_turn_deadline_cancels_instead_of_claiming_completion(self):
        task = self.start("hold", turn_timeout=0.2)
        state = self.finished(task)
        self.assertEqual(state["status"], "timed_out")
        self.assertEqual(state["stop_reason"], "cancelled")
        result, _ = self.cli("status", task)
        self.assertEqual(result.returncode, 1)

    def test_unacknowledged_cancel_closes_process_and_preserves_reason(self):
        task = self.start("hold", mode="ignore_cancel")
        self.until(task, lambda s: s["status"] == "running")
        self.store.submit(task, {"action": "cancel"})
        state = self.until(task, lambda s: s["closed"], timeout=15)
        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(state["stop_reason"], "forced_stop")

    def test_close_active_task_cancels_and_retains_result(self):
        task = self.start("hold")
        self.until(task, lambda s: s["status"] == "running")
        self.store.submit(task, {"action": "close"})
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "cancelled")
        with self.assertRaises(grok.TaskError):
            self.store.submit(task, {"action": "reply", "prompt": "closed"})

    def test_idle_timeout_closes_without_losing_completed_text(self):
        task = self.start(idle_timeout=0.2)
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["text"], "turn 1: hello")
        self.assertEqual(state["close_reason"], "idle_timeout")

    def test_provider_error_is_visible_and_same_session_can_be_retried(self):
        task = self.start("error")
        state = self.finished(task)
        self.assertEqual(state["error"]["message"], "Provider failed")
        self.store.submit(task, {"action": "reply", "prompt": "retry"})
        state = self.finished(task)
        self.assertEqual(state["status"], "completed")
        self.assertNotIn("error", state)

    def test_non_end_turn_stop_reason_is_incomplete_with_partial_text(self):
        task = self.start("limit")
        state = self.finished(task)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["stop_reason"], "max_tokens")
        self.assertEqual(state["text"], "partial")

    def test_protocol_and_process_failures_close_task(self):
        for prompt in ("exit", "bad_json"):
            with self.subTest(prompt=prompt):
                task = self.start(prompt)
                state = self.until(task, lambda s: s["closed"])
                self.assertEqual(state["status"], "failed")
                self.assertTrue(state["error"])

    def test_agent_exit_does_not_leave_its_tool_process_running(self):
        task = self.start("child_exit")
        self.until(task, lambda s: s["closed"])
        marker = self.root / "trace.child"
        self.assertTrue(marker.exists())
        previous = marker.read_bytes()
        time.sleep(0.2)
        self.assertEqual(marker.read_bytes(), previous)

    def test_setup_failures_never_send_prompt_or_change_auth_method(self):
        for mode in ("authfail", "bad_version", "startup_hang"):
            with self.subTest(mode=mode):
                (self.root / "trace.jsonl").unlink(missing_ok=True)
                task = self.start(mode=mode, startup_timeout=0.3)
                state = self.until(task, lambda s: s["closed"])
                self.assertEqual(state["status"], "failed")
                self.assertEqual(state["turn"], 0)
                trace = self.trace()
                self.assertFalse(
                    any(m.get("method") == "session/prompt" for m in trace)
                )
                self.assertFalse(
                    any(
                        m.get("params", {}).get("methodId") == "xai.api_key"
                        for m in trace
                    )
                )

    def test_startup_can_be_cancelled_without_sending_prompt(self):
        task = self.start(mode="startup_hang", startup_timeout=15)
        self.until(task, lambda s: "grok_pid" in s)
        self.store.submit(task, {"action": "cancel"})
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "cancelled")
        self.assertFalse(any(m.get("method") == "session/prompt" for m in self.trace()))

    def test_unsupported_client_request_returns_method_not_found(self):
        task = self.start("unsupported")
        self.assertEqual(self.finished(task)["text"], "unsupported callback: -32601")

    def test_stale_heartbeat_is_not_reported_as_live_work(self):
        state = self.store.create({"cwd": str(self.root)})
        state["updated_at"] -= 60
        with self.store.db:
            self.store.db.execute(
                "UPDATE tasks SET state=? WHERE id=?",
                (json.dumps(state), state["task_id"]),
            )
        self.assertEqual(self.store.status(state["task_id"])["status"], "unresponsive")
        with self.assertRaises(grok.TaskError):
            self.store.submit(
                state["task_id"], {"action": "reply", "prompt": "duplicate"}
            )

    def test_cli_uses_argument_array_and_inherits_unspecified_options(self):
        prompt = self.root / "task.txt"
        prompt.write_text("你好 $() `quoted`", encoding="utf-8-sig")
        output = io.StringIO()
        with (
            patch.object(grok, "launch", return_value={"status": "starting"}) as launch,
            patch.object(grok.shutil, "which", return_value=sys.executable),
            contextlib.redirect_stdout(output),
        ):
            code = grok.main(
                [
                    "--state-dir",
                    str(self.store.root),
                    "start",
                    "--cwd",
                    str(self.root),
                    "--prompt-file",
                    str(prompt),
                ]
            )
        self.assertEqual(code, 0)
        config = launch.call_args.args[1]
        self.assertEqual(
            config["command"],
            [str(Path(sys.executable).resolve()), "agent", "--no-leader", "stdio"],
        )
        self.assertEqual(config["prompt"], "你好 $() `quoted`")
        self.assertEqual(json.loads(output.getvalue()), {"status": "starting"})

    def test_cli_overrides_are_scoped_and_in_correct_argument_positions(self):
        with (
            patch.object(grok, "launch", return_value={}) as launch,
            patch.object(grok.shutil, "which", return_value=sys.executable),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            grok.main(
                [
                    "--state-dir",
                    str(self.store.root),
                    "start",
                    "--cwd",
                    str(self.root),
                    "--prompt",
                    "test",
                    "--model",
                    "chosen",
                    "--effort",
                    "high",
                    "--permission-mode",
                    "default",
                    "--sandbox",
                    "workspace",
                ]
            )
        self.assertEqual(
            launch.call_args.args[1]["command"][1:],
            [
                "--permission-mode",
                "default",
                "--sandbox",
                "workspace",
                "agent",
                "--no-leader",
                "--model",
                "chosen",
                "--reasoning-effort",
                "high",
                "stdio",
            ],
        )

    def test_cli_rejects_missing_binary_bad_task_id_empty_prompt_and_timeout(self):
        result, body = self.cli(
            "start",
            "--cwd",
            str(self.root),
            "--grok",
            "grok-does-not-exist",
            "--prompt",
            "test",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error", body)
        with self.assertRaises(grok.TaskError):
            self.store.status("../outside")
        with self.assertRaises(grok.TaskError):
            grok.read_prompt(
                grok.parser().parse_args(["reply", "0" * 32, "--prompt", " "])
            )
        for value in ("0", "-1", "nan", "inf"):
            with self.assertRaises(argparse.ArgumentTypeError):
                grok.seconds(value)

    def test_json_stdout_roundtrips_under_ascii_encoding(self):
        task = self.start("中文")
        self.finished(task)
        env = {**os.environ, "PYTHONIOENCODING": "ascii"}
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--state-dir",
                str(self.store.root),
                "status",
                task,
            ],
            capture_output=True,
            env=env,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["text"], "turn 1: 中文")
        self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
