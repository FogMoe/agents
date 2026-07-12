# Agents

Shared standards and skills for AI coding agents — Claude Code, Codex CLI,
and anything else that reads `AGENTS.md` or the
[SKILL.md](https://agentskills.io) format.

## Contents

- [`AGENTS.md`](AGENTS.md) — project-agnostic base guidelines. Copy it into a
  repository and prepend the project-specific sections (structure, commands,
  domain notes).
- [`skills/`](skills/) — cross-agent skills; each skill is a directory
  containing a `SKILL.md` plus optional resources.

## Skills

| Skill | Description |
|-------|-------------|
| [ux-writing](skills/ux-writing/SKILL.md) | Judgment rules for user-facing text and documentation — CLI output, diagnostics, error messages, docs structure, and keeping copy in sync with behavior |

## Install a skill

Copy a skill directory into the agent's global skills directory:

- Claude Code: `~/.claude/skills/<name>/`
- Codex CLI: `~/.codex/skills/<name>/`

## License

[Apache-2.0](LICENSE)
