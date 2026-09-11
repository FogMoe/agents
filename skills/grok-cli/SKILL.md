---
name: grok-cli
description: "Delegate bounded tasks to Grok Build from a supervising agent such as Codex. Use when the user asks Grok to investigate, review, implement, or provide another perspective, or when a distinct coding agent would materially help. Includes a background ACP client for progress, follow-up prompts, permissions, and cancellation."
license: Apache-2.0
metadata:
  author: scarletkc
  source: https://github.com/scarletkc/agents
  summary: "Delegate work to Grok Build, keep its session for follow-ups, and inspect results while the supervising agent continues working."
---

# Grok CLI

Use Grok Build as a separate coding agent on the same machine. The bundled
client launches `grok agent --no-leader stdio`, keeps its ACP session open,
and returns a task ID immediately. This is an external task: it does not
appear in Codex's native `spawn_agent` tree or inherit its conversation.

Grok Build must already be installed and configured. Use the project's
Python 3.12+ interpreter to run [scripts/grok.py](scripts/grok.py); the
client uses only the standard library. If the project has no interpreter,
`uv run --python 3.12 <script> ...` also works. Resolve the script relative
to this installed skill, not the repository being investigated.

## Delegate a task

Give Grok the goal, absolute working directory, relevant files and evidence,
scope boundaries, and the check that proves completion. It cannot see the
conversation that led to the assignment. Keep independent work with the
supervising agent while Grok runs.

Use a UTF-8 prompt file for substantial instructions. In these examples,
`<script>` is the absolute path to this skill's `scripts/grok.py`:

```sh
python <script> start --cwd <absolute-project-path> --prompt-file <task-file>
python <script> wait <task_id> --timeout 30
python <script> status <task_id>
python <script> reply <task_id> --prompt-file <follow-up-file>
python <script> cancel <task_id>
python <script> close <task_id>
```

Retain the returned `task_id`. Use `wait` when there is no independent work
left; its timeout returns the current state without cancelling the task.
Use `reply` after the current turn finishes to continue the same Grok
session. A running turn must finish or acknowledge cancellation before a
follow-up is accepted. Close the task once no more follow-ups are needed.

The helper's `--help` is the command reference. For output fields, storage,
timeouts, and troubleshooting, read [references/client.md](references/client.md).

## Configuration and permissions

Inherit Grok's model, authentication, and permission configuration unless
the task requires a specific override. Subscription login, API keys,
and configured providers are Grok's concern; do not change the user's
configuration or choose another authentication route to get past a failure.
The helper uses Grok's advertised noninteractive default authentication
method when available. Interactive authentication is completed separately
through Grok itself.

`start --model`, `--effort`, `--permission-mode`, and `--sandbox` are
per-task overrides. Omit them when no override is needed. Do not use a
permission bypass merely to avoid handling an approval request.

Choose `--effort` for the delegated task. Honor the user's explicit choice;
otherwise weigh complexity, the cost of an incorrect result, and how easily
the result can be checked. Make routine choices without asking the user:

- Simple chat, rewriting, or mechanical work can use a lower effort level.
- Ordinary implementation and analysis generally suit a middle level.
- Difficult debugging and consequential code review may justify a higher level.

These are starting points, not fixed task-to-level rules. Use only levels
known to be supported by the selected model. When support or the appropriate
level is uncertain, omit `--effort` and inherit Grok's configured value.

Match permissions to the authorized work. Preserve read-only restrictions
for read-only assignments; allow the necessary file edits and checks for
an authorized implementation within its scope. Task complexity and reasoning
effort do not expand that authorization.

When `status` is `needs_approval`, inspect `pending_permissions` and answer
the relevant request with:

```sh
python <script> permission <task_id> --request-id <request_id> --option-id <optionId>
```

Select an option Grok actually offered. Approve actions already covered by
the user's assignment; prefer a single-use approval. Decisions beyond that
scope stay with the user. Configured Grok allow rules can execute tools
without producing an ACP approval request. A read-only task prompt or
refusing an ACP request is not an OS sandbox; Codex's sandbox does not
configure Grok's. Do not promise enforced isolation without verifying
Grok's sandbox on the target platform.

## Supervise the result

Avoid simultaneous edits to the same files. Use a separate worktree when
both agents need to edit overlapping code, and pass its absolute path as
`--cwd`; the helper does not create worktrees.

Read `status`, `closed`, `stop_reason`, and `error` together. A returned
task ID means the worker started, not that Grok authenticated or finished.
`completed` means Grok ended its turn, not that its claims were verified.
Inspect the actual diff or cited evidence and run the relevant checks.

If Grok is unavailable or an installation, configuration, authentication,
tool, or process failure blocks the task, explicitly tell the user what
failed and which work remains incomplete. Inspect any partial result before
retrying. Do not silently substitute your own work, another agent, or another
provider for the requested Grok task. Report what Grok contributed and what
the supervising agent verified. Committing, publishing, and other external
actions keep the authorization boundaries of the original task.
