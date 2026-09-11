# Client operations

The helper maintains a background worker for each task. Each turn starts a
private AGY process with `--input-format stream-json --output-format
stream-json`, supplies `--add-dir`, waits for `init`, sends one prompt, and
closes stdin. Subsequent turns use the returned conversation ID. Results
are finalized only after the process exits and both output channels have
been collected. No MCP server or unofficial ACP adapter is required.

## Input and output

`start` and `reply` accept `--prompt`, `--prompt-file`, or UTF-8 stdin.
Prompt files may contain a UTF-8 BOM. Prompts travel as JSON through stdin,
not shell-interpreted command text. AGY itself determines prompt and skill
expansion; stream input does not support CLI-handled slash commands.

The helper emits one JSON object on stdout with Unicode escaped for Windows
pipe compatibility. Usage errors go to stderr. Runtime errors and states
`blocked`, `failed`, `timed_out`, and `unresponsive` produce a nonzero helper
exit code. A successful observation of `starting` or `running` does not mean
the task has finished.

| Field | Meaning |
| --- | --- |
| `task_id` | Helper ID for status, wait, reply, cancel, and close |
| `session_id` | Antigravity conversation ID; absent until initialization succeeds |
| `status` | Starting, running, completed, blocked, failed, cancelled, timed out, or unresponsive |
| `closed` | The background worker has ended; no more replies can be accepted. Check `error` for any cleanup failure |
| `closing` | Cleanup is in progress; wait for `closed` before starting replacement work |
| `turn` | Prompts sent by this helper task; a recovered conversation can have additional earlier turns |
| `text` | Latest response or partial streamed text |
| `tools` | Up to ten recent tool names, indices, states, and errors |
| `tool_errors` | Up to ten reported tool errors, including errors AGY later recovered from |
| `denied_actions` | Actions AGY refused under its headless permission policy |
| `result` | Native result, including its cumulative conversation usage and turn count |
| `raw_status` | Native AGY status, which can be SUCCESS for blocked or timed-out work |
| `stop_reason`, `error` | Helper completion reason and failure details |
| `init` | Configuration AGY advertised, including its cwd, tools, and any explicit model override |
| `exit_code` | Native exit code; forced termination can still produce 0 on Windows |
| `stderr_tail` | Recent diagnostics from this turn; the full log is retained |
| `log_dir` | Absolute path to logs and events |

Native counters in `result.usage`, `result.num_turns`, and
`result.duration_seconds` describe the whole conversation. Do not add these
cumulative counters across replies as though they described separate turns.

Control commands return a `command_id` after queuing the request.
`command_status: queued` means the worker has not acknowledged it yet.
Inspect state before retrying, particularly for `reply`, to avoid duplicate
prompts. A stale worker heartbeat produces `unresponsive`; inspect its
process and logs instead of assuming the saved running state is current.

## Deadlines and process ownership

`start --help` lists the defaults. `--startup-timeout` applies to each new
AGY process, `--turn-timeout` to prompt execution, `--exit-timeout` to a
process that has returned a result but has not exited, and `--idle-timeout`
to a finished worker waiting for another prompt. The helper gives AGY a
longer native print timeout so the helper's watchdog normally fires first.
It also checks AGY's timeout diagnostics after exit, because native print
timeouts can return SUCCESS and partial output.

An idle timeout releases the worker and preserves its last result. A helper
startup, turn, or exit timeout stops active work and closes the task. A
native timeout result can leave the idle worker available for an explicit
follow-up. No timeout automatically resubmits a prompt.

Windows processes belong to a Job Object; other platforms use a dedicated
process group. Cleanup stops that task's process tree, including tool
children that remain after AGY exits. This also stops task-owned development
servers; use another process for services intended to outlive the task.
Cancellation cannot undo work already done. No in-process cooperative
cancel or approval protocol is advertised.

## Storage and troubleshooting

State defaults to `%LOCALAPPDATA%/antigravity-tasks` on Windows, or
`$XDG_STATE_HOME/antigravity-tasks` (`~/.local/state/antigravity-tasks` by
default) elsewhere. To override it, place `--state-dir <absolute-path>`
before the command and reuse that path for all commands for the task.
Keep state outside shared or tracked repositories: logs can contain prompts,
file contents, tool output, and other project data.

Each task retains `events.jsonl` for prompts, process starts, and native
events; `agy.log` for stderr across all turns; and `worker.log` for helper
diagnostics. Logs are not automatically deleted. Close tasks before removing
their state directory.

The helper discovers `agy` in PATH or its standard user install directory.
An explicit `--agy` path never falls back to another binary. Authentication
is handled by the installed CLI; finish any required interactive sign-in
outside the helper. A model list or valid login does not prove model requests
can complete. Preserve network and provider errors without attributing them
to credentials or changing providers automatically.

On Windows the standard binary is `%LOCALAPPDATA%/agy/bin/agy.exe`. If a
new installation is not yet on the current shell's PATH, open a new terminal
or use the absolute binary path for direct CLI commands, for example:

```powershell
& "$env:LOCALAPPDATA\agy\bin\agy.exe" --output-format json models
```

Protocol references: [Headless mode](https://www.antigravity.google/docs/cli/headless/),
[permissions](https://www.antigravity.google/docs/cli/permissions/), and
[installation and authentication](https://antigravity.google/docs/cli/install/).
