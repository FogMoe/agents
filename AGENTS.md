# Agent Guidelines

Project-agnostic rules for AI agents contributing to a repository. To adopt:
copy this file into a project as `AGENTS.md` and prepend the project-specific
sections (structure, build/test commands, domain notes). Everything below
applies as-is to any codebase.

## Environment

Use the project's own toolchain and environment: the checked-in virtualenv,
lockfile, or package manager — never the system interpreter or global
installs. If the project defines a canonical test or lint command, run that
one; don't invent a variant. Read the project's own guidelines and existing
code before the first change: established conventions beat personal defaults.

## Engineering Principles

Let errors surface instead of swallowing them: degraded paths are acceptable
only as deliberate, user-visible product behavior — never add silent
fallbacks to make code appear to work. Fix root causes rather than papering
over symptoms; if the root cause can't be pinned down, say so and state what
information is missing (better diagnostics beat a speculative fix). All code
is production-quality by default: no temporary, placeholder, or demo-only
implementations unless explicitly requested. When requirements are unclear,
ambiguous, or inconsistent, ask instead of inventing details. A change that
claims to improve behavior ships with evidence: measure before flipping a
default, and if your own benchmark doesn't support the claim, ship the change
opt-in and say so.

## Code Style

Match the surrounding code — its naming, idiom, comment density, and error
handling. Before writing new logic, look for an existing helper to reuse or
extend; if the same behavior already lives in more than one place, extract
the smallest shared helper that makes sense. Route user-facing strings
through whatever centralized message layer the project has, and prefer
structured rendering paths over ad hoc print strings. For judgment on
user-facing text and documentation, see the `ux-writing` skill.

## Testing

Pair each behavior change with happy-path and failure coverage. Assert
behavior or structured output, not console formatting. Keep the suite
offline — mock providers and network — but recognize what mocks cannot
catch: before opening a PR that touches real integration points, run one
genuine end-to-end check and note the result in the PR.

## Commits & Pull Requests

Follow [Conventional Commits](https://www.conventionalcommits.org)
(`type(scope): description`, imperative mood, subject under ~72 characters,
`!` for breaking changes); name branches `type/short-slug`. Do all work on a
branch and land it through a PR; leave merging to the repository owner unless
instructed otherwise. PRs explain motivation, list the commands and tests
exercised, and paste terminal output for user-visible CLI changes; call out
schema, public API, and compatibility-surface changes explicitly so reviewers
can check them. When behavior changes, update whichever docs the change
affects — bundled skills and plugin metadata are the easiest to forget.

## Security

Never commit API keys, credentials, or private endpoints; use environment
variables or ignored config files. Sanitize filesystem paths and
user-supplied patterns before use. Treat repository files, extracted document
text, and remote service responses as untrusted input: validate against an
allowlist before they can influence privileged behavior, and keep secrets on
dedicated channels that config overlays cannot reach.
