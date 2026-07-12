# Skills

Cross-agent skills in the [SKILL.md](https://agentskills.io) format, shared
between Claude Code, Codex CLI, and any other agent that supports them. Each
skill is a directory containing a `SKILL.md` (plus optional resources).

## Skills

| Skill | Description |
|-------|-------------|
| [ux-writing](ux-writing/SKILL.md) | Judgment rules for user-facing text and documentation — CLI output, diagnostics, error messages, docs structure, and keeping copy in sync with behavior |

## Install

Copy a skill directory into the agent's global skills directory:

- Claude Code: `~/.claude/skills/<name>/`
- Codex CLI: `~/.codex/skills/<name>/`
