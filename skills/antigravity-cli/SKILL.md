---
name: antigravity-cli
description: "Delegate bounded investigation, review, or implementation tasks to Antigravity CLI from a supervising agent. Includes a background client for task progress, follow-up prompts, conversation recovery, cancellation, and visible failures."
license: Apache-2.0
metadata:
  author: scarletkc
  source: https://github.com/scarletkc/agents
  summary: "Delegate work to Antigravity CLI, inspect progress and tool failures, and continue the same conversation across follow-up tasks."
---

# Antigravity CLI

Use the installed `agy` CLI as an external coding agent. The bundled client
returns a task ID immediately and keeps a background worker available for
follow-ups. It runs each turn with official streaming JSON input/output and
resumes the exact Antigravity conversation on the next turn. Waiting for the
process and stderr to finish makes permission denials and partial-output
timeouts visible; each follow-up incurs CLI startup time.

Delegate when the user requests Antigravity or another agent can add value
that you can verify. Keep routine work with the supervising agent when the
extra startup and review time would outweigh that benefit.

Antigravity CLI must already be installed and authenticated. Run
[scripts/agy.py](scripts/agy.py) with the project's Python 3.12+ interpreter.
The helper uses only the standard library; when the project has no Python
environment, `uv run --python 3.12 <script> ...` also works. Resolve the
script relative to this skill, not the project receiving the task.

## Assign and follow up

Provide the goal, absolute working directory, relevant files and evidence,
scope, and completion check. Antigravity does not inherit the supervising
agent's conversation. Use a UTF-8 prompt file for substantial instructions:

```sh
python <script> start --cwd <absolute-project-path> --prompt-file <task-file>
python <script> wait <task_id> --timeout 30
python <script> status <task_id>
python <script> reply <task_id> --prompt-file <follow-up-file>
python <script> cancel <task_id>
python <script> close <task_id>
```

Keep independent work with the supervising agent while the task runs.
`wait` timing out only returns a snapshot; it does not cancel the task.
`reply` is accepted after the current turn finishes. Retain the `task_id`
and close the worker when no more follow-ups are needed.

The helper supplies both the process working directory and `--add-dir`.
For concurrent edits to overlapping files, use separate worktrees and pass
their paths as `--cwd`; the helper does not create worktrees. Check actual
output paths, since Antigravity can also write to its conversation artifacts.

## Configuration and permissions

Inherit Antigravity's authentication, model, and permission configuration.
Subscription and API authentication remain Antigravity's responsibility.
Do not switch providers, change authentication, or rewrite its global
settings to conceal a failure.

`start --model`, `--effort`, `--mode`, and `--sandbox` are task-specific
overrides. Honor the user's model or effort choice. Otherwise choose effort
according to complexity, error cost, and ease of verification; omit the
override when the model's support or the appropriate choice is uncertain.
Discover models with `agy --output-format json models`.

Match permissions to the authorized work. `--mode plan` is a planning
instruction, not enforced read-only access: headless plan review can proceed
automatically. The supervising agent's sandbox does not configure AGY's.
Do not promise isolation without checking the target platform's support.

For authorized workspace edits, `--mode accept-edits` allows file changes
without interactive diff review; shell commands still follow tool permission
rules. If a file tool rejects the target as an invalid artifact path, ask
Antigravity to write a regular workspace file instead of an artifact. Inspect
that tool error before attempting a shell workaround or expanding permissions.

Headless AGY cannot accept programmatic approval responses. When the helper
reports `blocked`, inspect `denied_actions` and the partial result. If the
task requires those tools, use scoped Antigravity permission rules or an
interactive AGY session to establish the required permissions, following the
original authorization. Do not repeatedly submit a blocked operation with
unchanged permissions. The helper exposes `--dangerously-skip-permissions`
only as an explicit override; do not use it merely to avoid an approval.
Scoped rules limit which actions match; they are stored in Antigravity's
global settings, not as temporary grants managed by this helper.

## Check results and recover

Read `status`, `closed`, `stop_reason`, `error`, `denied_actions`, and
`tool_errors` together. `completed` means the turn returned a response, not
that its claims or edits were verified. Inspect the diff, output files, and
relevant checks. AGY may recover from an individual tool error, so tool
errors remain visible even when the final turn completes.

The helper does not equate native `SUCCESS` or exit code 0 with completion.
It checks permission denials and stderr timeout diagnostics, and enforces
its own startup, turn, and shutdown deadlines.

`cancel` stops that task's AGY process tree and closes its worker. It does
not undo edits or external actions already performed. Read partial results
before retrying. To continue a closed conversation, explicitly start a new
task with its returned `session_id`:

```sh
python <script> start --cwd <same-project-path> --conversation <session_id> --prompt-file <follow-up-file>
```

An open task can use `reply` after a provider failure. This is an explicit
new turn in the same conversation; there is no automatic retry. If startup
failed before a session ID was obtained, resolve the error and start again.

If installation, authentication, network, permissions, or execution blocks
the task, tell the user what failed and what remains incomplete. Do not
silently replace the requested Antigravity contribution with your own work
or another provider. Committing, publishing, and other external actions
retain the authorization boundaries of the original assignment.

Use `<script> --help` for commands and
[references/client.md](references/client.md) for state fields, timeouts,
storage, and diagnostics.
