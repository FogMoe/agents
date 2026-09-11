"""Offline ACP peer used by the Grok skill's subprocess tests."""

import json
import subprocess
import sys
import time
from pathlib import Path

if sys.argv[1] == "--child":
    marker = Path(sys.argv[2])
    while True:
        marker.write_text(str(time.monotonic()), encoding="utf-8")
        time.sleep(0.03)

trace = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "normal"
session_id = "test-session"
active = None
permissions = set()
turns = 0


def send(**message):
    print(json.dumps({"jsonrpc": "2.0", **message}), flush=True)


def update(session_update, **values):
    send(
        method="session/update",
        params={
            "sessionId": session_id,
            "update": {"sessionUpdate": session_update, **values},
        },
    )


def complete(text):
    global active
    update("agent_message_chunk", content={"type": "text", "text": text[:2]})
    update("agent_message_chunk", content={"type": "text", "text": text[2:]})
    send(id=active, result={"stopReason": "end_turn"})
    active = None


for line in sys.stdin:
    message = json.loads(line)
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(message) + "\n")
    method = message.get("method")
    params = message.get("params", {})
    request_id = message.get("id")
    if method == "initialize":
        if mode == "startup_hang":
            continue
        send(
            id=request_id,
            result={
                "protocolVersion": 99 if mode == "bad_version" else 1,
                "authMethods": [{"id": "cached_token"}, {"id": "xai.api_key"}],
                "_meta": {"defaultAuthMethodId": "cached_token"},
            },
        )
    elif method == "authenticate":
        if mode == "authfail":
            send(id=request_id, error={"code": -32000, "message": "Login expired"})
        else:
            send(id=request_id, result={})
    elif method == "session/new":
        send(
            id=request_id,
            result={
                "sessionId": session_id,
                "models": {"currentModelId": "configured-model"},
            },
        )
    elif method == "session/prompt":
        assert params["sessionId"] == session_id
        active = request_id
        turns += 1
        prompt = params["prompt"][0]["text"]
        if prompt == "hold":
            update(
                "tool_call",
                toolCallId="t1",
                title="Waiting",
                kind="read",
                status="in_progress",
            )
        elif prompt == "permission":
            permissions = {801, 802}
            for permission_id in sorted(permissions):
                send(
                    id=permission_id,
                    method="session/request_permission",
                    params={
                        "sessionId": session_id,
                        "toolCall": {
                            "toolCallId": str(permission_id),
                            "title": "Read file",
                            "kind": "read",
                        },
                        "options": [
                            {
                                "optionId": "yes",
                                "kind": "allow_once",
                                "name": "Allow once",
                            },
                            {"optionId": "no", "kind": "reject_once", "name": "Reject"},
                        ],
                    },
                )
        elif prompt == "unsupported":
            send(
                id=900,
                method="fs/read_text_file",
                params={"sessionId": session_id, "path": "/unused"},
            )
        elif prompt == "error":
            send(id=request_id, error={"code": -32000, "message": "Provider failed"})
            active = None
        elif prompt == "limit":
            update("agent_message_chunk", content={"type": "text", "text": "partial"})
            send(id=request_id, result={"stopReason": "max_tokens"})
            active = None
        elif prompt == "exit":
            sys.exit(7)
        elif prompt == "child_exit":
            marker = trace.with_suffix(".child")
            child = subprocess.Popen(
                [sys.executable, __file__, "--child", str(marker)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            sys.exit(7)
        elif prompt == "bad_json":
            print("not JSON", flush=True)
        else:
            complete(f"turn {turns}: {prompt}")
    elif method == "session/cancel":
        if mode != "ignore_cancel":
            send(id=active, result={"stopReason": "cancelled"})
            active = None
            permissions.clear()
    elif method is None and request_id in permissions:
        if message.get("result", {}).get("outcome", {}).get("outcome") == "selected":
            permissions.remove(request_id)
            if not permissions:
                complete("permissions handled")
    elif method is None and request_id == 900:
        complete("unsupported callback: " + str(message.get("error", {}).get("code")))
