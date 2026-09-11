"""Offline Antigravity peer for process, stream, and recovery tests."""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

if sys.argv[1] == "--child":
    marker = Path(sys.argv[2])
    while True:
        marker.write_text(str(time.monotonic()), encoding="utf-8")
        time.sleep(0.03)

parser = argparse.ArgumentParser()
parser.add_argument("trace", type=Path)
parser.add_argument("mode")
parser.add_argument("--conversation")
args = parser.parse_args()
trace = args.trace
history = trace.with_suffix(".history.json")
stored = (
    json.loads(history.read_text())
    if history.exists()
    else {"turns": 0, "id": str(uuid.uuid4())}
)
session = args.conversation or stored["id"]
if args.mode == "wrong_resume":
    session = str(uuid.uuid4())


def record(value):
    with trace.open("a", encoding="utf-8") as log:
        log.write(json.dumps(value) + "\n")


def send(event, **values):
    print(json.dumps({"event": event, **values}), flush=True)


def step(kind, **values):
    send(
        "step_update",
        step_update={
            "conversation_id": session,
            "step_index": 1,
            "state": "DONE",
            "step_type": kind,
            **values,
        },
    )


def result(status="SUCCESS", text="", **extra):
    send(
        "result",
        result={
            "conversation_id": session,
            "status": status,
            "response": text,
            "num_turns": stored["turns"],
            **extra,
        },
    )


def child():
    marker = trace.with_suffix(".child")
    proc = subprocess.Popen(
        [sys.executable, __file__, "--child", str(marker)], stdin=subprocess.DEVNULL
    )
    record({"child_pid": proc.pid})
    deadline = time.monotonic() + 3
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)


record({"pid": os.getpid(), "conversation": args.conversation})
if args.mode == "startup_hang":
    while True:
        time.sleep(0.2)
if args.mode == "authfail":
    send(
        "result",
        result={
            "conversation_id": "",
            "status": "ERROR",
            "error": "Authentication required",
            "response": "",
        },
    )
    print("error: Authentication required", file=sys.stderr, flush=True)
    sys.exit(1)

send(
    "init",
    conversation_id=session,
    init={
        "cwd": "/wrong" if args.mode == "wrong_cwd" else os.getcwd(),
        "permission_mode": "request-review",
        "tools": ["view_file"],
    },
)
if args.mode == "stdin_hang":
    while True:
        time.sleep(0.2)
for line in sys.stdin:
    message = json.loads(line)
    record(message)
    prompt = message["message"]["content"]
    stored["turns"] += 1
    stored["id"] = session
    history.write_text(json.dumps(stored), encoding="utf-8")
    step("user_input")
    if prompt in {"hold", "child_exit", "result_hang"}:
        child()
        step(
            "tool",
            tool_name="test_child",
            state="ACTIVE",
            tool_info={"name": "test_child"},
        )
        if prompt == "child_exit":
            sys.exit(7)
        if prompt == "result_hang":
            result(text="done")
        while True:
            time.sleep(0.2)
    if prompt == "bad_json":
        print("not JSON", flush=True)
        while True:
            time.sleep(0.2)
    if prompt == "malformed_result":
        send("result", result={"status": "SUCCESS", "response": 12})
        continue
    if prompt == "error":
        step("agent_response", text_delta="partial before failure")
        result("ERROR", error="Provider location failed")
        print("error: Provider location failed", file=sys.stderr, flush=True)
        sys.exit(1)
    if prompt == "exit":
        sys.exit(7)
    if prompt == "permission":
        result(denied_actions=[{"action": "command", "display_name": "RunCommand"}])
        print("jetski: command permission denied", file=sys.stderr, flush=True)
        continue
    if prompt == "timeout":
        step("agent_response", text_delta="partial")
        result(text="partial")
        # The result arrives before its diagnostic. A client must await exit.
        time.sleep(0.35)
        print(
            "[agy] print timeout after 1ms with turn in progress; returning partial output",
            file=sys.stderr,
            flush=True,
        )
        continue
    if prompt == "empty":
        result()
        continue
    if prompt == "missing_result":
        step("agent_response", text_delta="partial")
        continue
    if prompt == "wrong_id":
        session = str(uuid.uuid4())
        result(text="wrong session")
        continue
    if prompt == "unknown_event":
        send("future_observation", information="retained in log")
    if prompt == "tool_error":
        step(
            "tool",
            tool_name="view_file",
            tool_info={"error": {"type": "IOError", "message": "Missing file"}},
        )
    text = f"turn {stored['turns']}: {prompt}"
    step("agent_response", state="ACTIVE", text_delta=text[:2])
    step("agent_response", text_delta=text[2:])
    result(text=text, usage={"input_tokens": stored["turns"] * 100})
    if prompt == "duplicate_result":
        result(text="duplicate")
    if prompt == "stderr_error":
        print("error: final shutdown failure", file=sys.stderr, flush=True)
    if prompt == "nonzero_success":
        sys.exit(3)
