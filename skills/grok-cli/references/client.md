# ACP client operations

Run `scripts/grok.py --help` or `<command> --help` for flags and defaults.
The client starts a private Grok process for each task. The process keeps
its session until `close`, a connection failure, or the idle timeout.

## Inputs and results

`start` and `reply` accept `--prompt`, `--prompt-file`, or UTF-8 stdin.
Prompt files can include a UTF-8 BOM. Prefer files to shell-quoted multiline
text. The client passes an argument array to Grok and does not invoke a
shell to interpret the prompt.

Commands emit one JSON object on stdout. Unicode is escaped for Windows
pipe compatibility. Runtime failures return a nonzero exit code and an
`error`; argparse usage errors go to stderr. `status` and `wait` also exit
nonzero for failed, timed-out, or unresponsive tasks. A successful exit
with a running state means observation succeeded, not that Grok finished.

| Field | Meaning |
| --- | --- |
| `task_id` | Helper ID used in every follow-up command |
| `session_id` | Grok ACP session ID, available after initialization |
| `status` | Starting, running, needs approval, cancelling, completed, cancelled, failed, timed out, or unresponsive |
| `closed` | Whether the worker released its Grok process; closed tasks cannot accept replies |
| `closing` | A close request is being processed; wait until `closed` is true |
| `turn` | Turn number; each accepted reply starts another turn |
| `text` | Accumulated assistant text from the current/latest turn |
| `tools` | Up to ten recent tool names, statuses, and locations; full inputs and results are in the event log |
| `pending_permissions` | Outstanding request IDs, tool context, and offered option IDs |
| `stop_reason` | Grok's completion reason; `forced_stop` means cancellation required terminating its process tree |
| `error` | Failure or incomplete-turn information, when present |
| `log_dir` | Absolute path to this task's diagnostic files |

`model` and `config_options` show the model and options returned by Grok.
Missing fields mean that initialization has not reached that point, or the
agent did not advertise the value. The helper does not inspect credential
files or rewrite Grok configuration.

## Waiting, cancellation, and follow-ups

`wait` returns when a turn ends, the task closes, approval is needed, or
its own timeout expires. It does not kill a running task.

`cancel` sends ACP `session/cancel` and answers outstanding permissions
with the cancelled outcome. Keep waiting until cancellation is acknowledged.
If Grok acknowledges, `reply` can reuse the session. If Grok does not
acknowledge within the cancellation grace period, the helper terminates
that Grok process tree and closes the task. Cancellation does not undo
file changes or external actions already performed.

`close` cancels active work and releases the process. Finished results and
logs remain readable. A turn timeout requests cancellation; an idle timeout
closes an already-finished session. Configure these on `start` if the task
needs longer. Sessions closed by the helper are not automatically reloaded.

Control commands return a `command_id` once queued. Usually the worker
acknowledges immediately and returns its new state. A
`command_status: "queued"` result means acknowledgment has not arrived:
inspect `status` before retrying, especially for `reply`, to avoid sending
the same work twice.

## Storage and diagnostics

Task state is stored under `%LOCALAPPDATA%/grok-acp` on Windows, or
`$XDG_STATE_HOME/grok-acp` (default `~/.local/state/grok-acp`) elsewhere.
Use `--state-dir <absolute-path>` **before the command** to choose another
location, and use the same location for all commands concerning that task.
Keep it outside a shared or tracked repository: prompts, responses, tool
events, and logs may contain project data.

Each task has `events.jsonl` for prompts, streamed ACP updates, and turn
results; `grok.log` for Grok stderr; and `worker.log` for helper diagnostics.
Earlier turns remain in the event log after `reply` resets the current
snapshot. Logs are not automatically deleted. Close tasks before removing
their state directory.

If a worker stops updating its heartbeat, `status` reports `unresponsive`
instead of claiming that the saved running state is still live. Inspect its
logs and process before launching replacement work. If authentication
requires a browser, complete `grok login` outside the helper and start a
new task. Model and provider failures belong to Grok's configuration;
the helper does not switch providers or authentication methods on retry.

The client advertises no filesystem or terminal callbacks: Grok executes
its own tools. It handles permission requests and rejects unsupported
client methods rather than leaving them waiting indefinitely. Protocol
references: [Grok ACP](https://docs.x.ai/build/cli/headless-scripting) and
[ACP prompt turns](https://agentclientprotocol.com/protocol/v1/prompt-turn).
