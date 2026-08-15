# Agents

Shared standards and skills for AI coding agents: Claude Code, Codex CLI,
and anything else that reads `AGENTS.md` or the
[SKILL.md](https://agentskills.io) format.

## Contents

- [`AGENTS.md`](AGENTS.md): project-agnostic base guidelines. Copy it into a
  repository and prepend the project-specific sections (structure, commands,
  domain notes).
- [`skills/`](skills/): cross-agent skills; each skill is a directory
  containing a `SKILL.md` plus optional resources.

## Skills

Each summary is generated from the skill's own metadata. Open its `SKILL.md`
for the complete activation description and instructions.

<!-- skills:start -->
| Skill | Summary |
|-------|---------|
| [marketing-copy](skills/marketing-copy/SKILL.md) | Write outbound promo copy that stays truthful, discloses only what may be public, and earns attention without hype. |
| [talk-like-scarletkc](skills/talk-like-scarletkc/SKILL.md) | Write and translate in scarletkc's natural voice without generic AI phrasing. |
| [ux-writing](skills/ux-writing/SKILL.md) | Review user-facing copy and documentation for clarity, consistency, and facts that do not go stale. |
| [worktree-pr](skills/worktree-pr/SKILL.md) | Run a task in its own worktree: branch from the integration branch, compare against the baseline, land through a PR. |
<!-- skills:end -->

## Install skills

Send this prompt to your coding agent:

> Install skills from https://github.com/FogMoe/agents. Show me the available
> skills and let me choose which ones to install.

You can also use either CLI directly. Both installers let you choose individual
skills. Replace `codex` with another supported agent, such as `claude-code`,
when needed.

### GitHub CLI

Browse the repository and install a skill for the current user:

```sh
gh skill install FogMoe/agents --agent codex --scope user
```

For a non-interactive installation, provide the skill name:

```sh
gh skill install FogMoe/agents <skill> --agent codex --scope user
```

Update installed skills with `gh skill update --all`.

### skills CLI

Browse the repository and choose skills and agents interactively:

```sh
npx skills add FogMoe/agents -g
```

For a non-interactive installation, provide the skill and agent:

```sh
npx skills add FogMoe/agents --skill <skill> --agent codex -g -y
```

Update global skills with `npx skills update -g -y`.

## Feedback and contributions

Report problems or suggest improvements through
[GitHub Issues](https://github.com/FogMoe/agents/issues). Pull requests are
welcome.

## License

[Apache-2.0](LICENSE). Attribution information is provided in
[`NOTICE`](NOTICE).
