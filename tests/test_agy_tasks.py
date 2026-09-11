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
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/antigravity-cli/scripts/agy.py"
FIXTURE = ROOT / "tests/fixtures/agy_stream_agent.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("agy_task_runner", SCRIPT)
agy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agy)


class AgyTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = agy.Store(self.root / "state")
        self.tasks = []

    def tearDown(self):
        for task in self.tasks:
            if not self.store.status(task)["closed"]:
                self.store.submit(task, {"action": "close"})
                self.until(task, lambda s: s["closed"])
        self.store.close()
        for attempt in range(40):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)

    def start(self, prompt="hello", mode="normal", **options):
        config = {
            "cwd": str(self.root),
            "command": [
                sys.executable,
                str(FIXTURE),
                str(self.root / "trace.jsonl"),
                mode,
            ],
            "prompt": prompt,
            "conversation": None,
            "startup_timeout": 3,
            "turn_timeout": 15,
            "idle_timeout": 60,
            "exit_timeout": 2,
            **options,
        }
        state = agy.launch(self.store, config)
        self.tasks.append(state["task_id"])
        return state["task_id"]

    def until(self, task, predicate, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.store.status(task)
            if predicate(state):
                return state
            time.sleep(0.04)
        self.fail(f"Timed out: {state}")

    def finished(self, task):
        return self.until(
            task, lambda s: s["status"] in agy.FINISHED and not s.get("closing")
        )

    def trace(self):
        return [
            json.loads(line)
            for line in (self.root / "trace.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def cli(self, *args, env=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--state-dir", str(self.store.root), *args],
            capture_output=True,
            timeout=15,
            env=env,
            check=False,
        )
        return result, json.loads(result.stdout)

    def assert_child_stopped(self):
        marker = self.root / "trace.child"
        self.assertTrue(marker.exists())
        previous = marker.read_bytes()
        time.sleep(0.2)
        self.assertEqual(marker.read_bytes(), previous)

    def test_followup_starts_new_process_and_resumes_exact_conversation(self):
        task = self.start("你好\n` $() text")
        first = self.finished(task)
        self.assertEqual(first["text"], "turn 1: 你好\n` $() text")
        self.assertFalse(first["closed"])
        self.store.submit(task, {"action": "reply", "prompt": "follow-up"})
        second = self.finished(task)
        self.assertEqual(second["text"], "turn 2: follow-up")
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(second["turn"], 2)
        self.assertEqual(second["result"]["usage"]["input_tokens"], 200)
        launches = [m for m in self.trace() if "pid" in m]
        self.assertEqual(len(launches), 2)
        self.assertNotEqual(launches[0]["pid"], launches[1]["pid"])
        self.assertEqual(launches[1]["conversation"], first["session_id"])

    def test_wait_timeout_observes_without_cancelling_and_rejects_running_reply(self):
        task = self.start("hold")
        self.until(task, lambda s: bool(s["tools"]))
        process, result = self.cli("wait", task, "--timeout", "0.1")
        self.assertEqual(process.returncode, 0)
        self.assertEqual(result["status"], "running")
        with self.assertRaises(agy.TaskError):
            self.store.submit(task, {"action": "reply", "prompt": "overlap"})

    def test_large_prompt_transfer_and_blocked_pipe_deadline(self):
        text = "中文" * 100_000
        task = self.start(text)
        self.assertEqual(self.finished(task)["text"], "turn 1: " + text)
        blocked = self.start(text, mode="stdin_hang", turn_timeout=0.3)
        state = self.until(blocked, lambda s: s["closed"])
        self.assertEqual(state["status"], "timed_out")
        self.assertEqual(state["stop_reason"], "turn_timeout")

    def test_cancel_interrupts_a_blocked_prompt_write(self):
        task = self.start("x" * 1_000_000, mode="stdin_hang")
        self.until(task, lambda s: s["status"] == "running")
        response = self.store.submit(task, {"action": "cancel"})
        self.assertEqual(response["status"], "cancelled")
        self.assertEqual(self.until(task, lambda s: s["closed"])["status"], "cancelled")

    def test_permission_denial_is_blocked_even_with_native_success_and_zero_exit(self):
        task = self.start("permission")
        state = self.finished(task)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["raw_status"], "SUCCESS")
        self.assertEqual(state["exit_code"], 0)
        self.assertEqual(state["denied_actions"][0]["action"], "command")
        process, observed = self.cli("wait", task)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(observed["stop_reason"], "permission_denied")
        self.store.submit(task, {"action": "reply", "prompt": "hello"})
        recovered = self.finished(task)
        self.assertEqual(recovered["status"], "completed")
        self.assertEqual(recovered["denied_actions"], [])

    def test_delayed_stderr_timeout_never_becomes_completed(self):
        task = self.start("timeout")
        observed = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.store.status(task)
            observed.append(state["status"])
            if state["status"] == "timed_out":
                break
            time.sleep(0.02)
        self.assertNotIn("completed", observed)
        self.assertEqual(state["status"], "timed_out")
        self.assertEqual(state["text"], "partial")
        self.assertEqual(state["raw_status"], "SUCCESS")
        self.assertEqual(state["stop_reason"], "print_timeout")
        self.assertEqual(state["exit_code"], 0)

    def test_failure_preserves_partial_text_and_allows_explicit_recovery(self):
        task = self.start("error")
        state = self.finished(task)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["text"], "partial before failure")
        self.assertEqual(state["error"], "Provider location failed")
        self.store.submit(task, {"action": "reply", "prompt": "recovered"})
        state = self.finished(task)
        self.assertEqual(state["status"], "completed")
        self.assertNotIn("error", state)
        self.assertEqual(state["stderr_tail"], "")

    def test_cancel_stops_process_tree_closes_task_and_allows_new_task_resume(self):
        task = self.start("hold")
        active = self.until(task, lambda s: bool(s["tools"]))
        self.store.submit(task, {"action": "cancel"})
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(state["stop_reason"], "forced_stop")
        self.assert_child_stopped()
        with self.assertRaises(agy.TaskError):
            self.store.submit(task, {"action": "reply", "prompt": "no"})
        recovered = self.start("recovered", conversation=active["session_id"])
        state = self.finished(recovered)
        self.assertEqual(state["session_id"], active["session_id"])
        self.assertEqual(state["text"], "turn 2: recovered")

    def test_close_active_task_stops_its_tools(self):
        task = self.start("hold")
        self.until(task, lambda s: bool(s["tools"]))
        self.store.submit(task, {"action": "close"})
        self.assertEqual(self.until(task, lambda s: s["closed"])["status"], "cancelled")
        self.assert_child_stopped()

    def test_turn_deadline_stops_task_and_children(self):
        task = self.start("hold", turn_timeout=0.5)
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "timed_out")
        self.assertEqual(state["stop_reason"], "turn_timeout")
        self.assert_child_stopped()

    def test_final_result_without_exit_is_not_completion(self):
        task = self.start("result_hang", exit_timeout=0.3)
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "timed_out")
        self.assertEqual(state["stop_reason"], "exit_timeout")
        self.assertEqual(state["text"], "done")
        self.assert_child_stopped()

    def test_agent_crash_stops_children_inheriting_output_handles(self):
        task = self.start("child_exit")
        state = self.finished(task)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["exit_code"], 7)
        self.assert_child_stopped()

    def test_startup_failures_never_send_prompt(self):
        for mode in ("authfail", "startup_hang", "wrong_cwd"):
            with self.subTest(mode=mode):
                trace = self.root / "trace.jsonl"
                trace.unlink(missing_ok=True)
                task = self.start(mode=mode, startup_timeout=0.5)
                state = self.until(task, lambda s: s["closed"])
                self.assertIn(state["status"], {"failed", "timed_out"})
                self.assertEqual(state["turn"], 0)
                self.assertFalse(any(m.get("event") == "user" for m in self.trace()))

    def test_startup_cancel_does_not_send_prompt(self):
        task = self.start(mode="startup_hang")
        self.until(task, lambda s: "agy_pid" in s)
        self.store.submit(task, {"action": "cancel"})
        self.assertEqual(self.until(task, lambda s: s["closed"])["status"], "cancelled")
        # Cancellation can stop Python before the fixture even creates its trace.
        state = self.store.status(task)
        self.assertEqual(state["turn"], 0)
        events = [
            json.loads(line)
            for line in (Path(state["log_dir"]) / "events.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertFalse(any(event.get("type") == "prompt" for event in events))

    def test_wrong_resume_id_fails_before_sending_prompt(self):
        task = self.start(mode="wrong_resume", conversation=str(uuid.uuid4()))
        self.assertEqual(self.until(task, lambda s: s["closed"])["status"], "failed")
        self.assertFalse(any(m.get("event") == "user" for m in self.trace()))

    def test_invalid_protocol_closes_task(self):
        for prompt in ("bad_json", "malformed_result", "duplicate_result", "wrong_id"):
            with self.subTest(prompt=prompt):
                task = self.start(prompt)
                state = self.until(task, lambda s: s["closed"])
                self.assertEqual(state["status"], "failed")
                self.assertTrue(state["error"])

    def test_incomplete_and_nonzero_outputs_fail(self):
        for prompt in (
            "empty",
            "missing_result",
            "nonzero_success",
            "stderr_error",
            "exit",
        ):
            with self.subTest(prompt=prompt):
                task = self.start(prompt)
                state = self.finished(task)
                self.assertEqual(state["status"], "failed")
                self.assertTrue(state["error"])

    def test_tool_errors_and_unknown_observations_are_preserved(self):
        task = self.start("tool_error")
        state = self.finished(task)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["tool_errors"][0]["error"]["type"], "IOError")
        self.store.submit(task, {"action": "reply", "prompt": "unknown_event"})
        state = self.finished(task)
        self.assertEqual(state["last_unknown_event"], "future_observation")
        self.assertNotIn("tool_errors", state)

    def test_idle_timeout_preserves_result(self):
        task = self.start(idle_timeout=0.2)
        state = self.until(task, lambda s: s["closed"])
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["text"], "turn 1: hello")
        self.assertEqual(state["close_reason"], "idle_timeout")

    def test_ascii_stdout_and_utf8_prompt_file(self):
        task = self.start("中文")
        self.finished(task)
        prompt = self.root / "prompt.txt"
        prompt.write_text("后续 $() ` quoted", encoding="utf-8-sig")
        result, _ = self.cli("reply", task, "--prompt-file", str(prompt))
        self.assertEqual(result.returncode, 0)
        self.finished(task)
        result, state = self.cli(
            "status", task, env={**os.environ, "PYTHONIOENCODING": "ascii"}
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(state["text"], "turn 2: 后续 $() ` quoted")
        self.assertEqual(result.stderr, b"")

    def test_cli_binds_workspace_and_preserves_configuration_by_default(self):
        prompt = self.root / "prompt.txt"
        prompt.write_text("中文 $() ` quoted", encoding="utf-8-sig")
        with (
            patch.object(agy, "executable", return_value=sys.executable),
            patch.object(agy, "launch", return_value={}) as launch,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                agy.main(
                    [
                        "--state-dir",
                        str(self.store.root),
                        "start",
                        "--cwd",
                        str(self.root),
                        "--prompt-file",
                        str(prompt),
                    ]
                ),
                0,
            )
        config = launch.call_args.args[1]
        self.assertEqual(
            config["command"],
            [
                sys.executable,
                "--add-dir",
                str(self.root),
                "--input-format",
                "stream-json",
                "--output-format",
                "stream-json",
                "--print-timeout",
                "1020s",
            ],
        )
        self.assertEqual(config["prompt"], "中文 $() ` quoted")
        self.assertIsNone(config["conversation"])

    def test_overrides_are_explicit_and_conversation_is_validated(self):
        session = str(uuid.uuid4())
        with (
            patch.object(agy, "executable", return_value=sys.executable),
            patch.object(agy, "launch", return_value={}) as launch,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = agy.main(
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
                    "--mode",
                    "accept-edits",
                    "--sandbox",
                    "--dangerously-skip-permissions",
                    "--conversation",
                    session,
                ]
            )
        self.assertEqual(code, 0)
        config = launch.call_args.args[1]
        self.assertEqual(
            config["command"][-8:],
            [
                "--model",
                "chosen",
                "--effort",
                "high",
                "--mode",
                "accept-edits",
                "--sandbox",
                "--dangerously-skip-permissions",
            ],
        )
        self.assertEqual(config["conversation"], session)

    def test_invalid_inputs_and_explicit_missing_binary_fail(self):
        result, state = self.cli(
            "start",
            "--cwd",
            str(self.root),
            "--agy",
            "no-such-agy-executable",
            "--prompt",
            "test",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error", state)
        for value in ("0", "-1", "nan", "inf"):
            with self.assertRaises(argparse.ArgumentTypeError):
                agy.seconds(value)
        with self.assertRaises(agy.TaskError):
            agy.conversation_id("--another-flag")
        with self.assertRaises(agy.TaskError):
            self.store.status("../outside")
        with self.assertRaises(agy.TaskError):
            agy.read_prompt(
                agy.parser().parse_args(["reply", "0" * 32, "--prompt", " "])
            )

    def test_stale_worker_is_not_reported_as_running(self):
        state = self.store.create({"cwd": str(self.root)})
        state["updated_at"] -= 60
        with self.store.db:
            self.store.db.execute(
                "UPDATE tasks SET state=? WHERE id=?",
                (json.dumps(state), state["task_id"]),
            )
        self.assertEqual(self.store.status(state["task_id"])["status"], "unresponsive")
        with self.assertRaises(agy.TaskError):
            self.store.submit(
                state["task_id"], {"action": "reply", "prompt": "duplicate"}
            )

    def test_skill_scripts_run_without_repository_or_other_skills(self):
        installed = self.root / "installed"
        package_spec = importlib.util.spec_from_file_location(
            "agy_package_test", ROOT / "scripts/package_skill.py"
        )
        package = importlib.util.module_from_spec(package_spec)
        package_spec.loader.exec_module(package)
        archive = package.package_skill(ROOT, "antigravity-cli", self.root / "dist")
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(installed)
        result = subprocess.run(
            [sys.executable, str(installed / "scripts/agy.py"), "start", "--help"],
            capture_output=True,
            cwd=self.root,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
