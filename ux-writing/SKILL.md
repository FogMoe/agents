---
name: ux-writing
description: Judgment rules for user-facing text and documentation — CLI/tool output, status and diagnostic displays, error messages, help text, README and docs structure, and keeping copy in sync with behavior. Use when writing or changing any user-visible string, when adding or restructuring documentation, or when reviewing a diff that touches copy or docs.
---

# UX Writing & Docs

User-visible text is product behavior and carries the same quality bar as
code. Every rule below is distilled from a real defect caught in review, and
keeps its counter-example because the reasoning is the point. When in doubt,
re-read the output as the user who just hit the problem.

## Status output & diagnostics

- **Report effective values, not stored ones.** A status display answers
  "what will happen when I run this", so resolve values exactly the way the
  runtime does — including environment variables and layered config.
  *Counter-example: a config viewer printed "API key set: no" while an env
  var held the key the next run would actually use.*
- **Diagnostics must stay truthful under failure.** When one config layer
  fails to load, fall back to the most complete state that still loads —
  never to blank defaults. A diagnostic that misreports is worse than one
  that aborts. *Counter-example: a broken project-level config made a doctor
  command check blank defaults and report a missing API key that was in fact
  configured — the fake failure buried the real one.*
- **Show deltas, not dumps.** A health/diagnostic command lists what
  deviates and who set it; the exhaustive listing belongs to the dedicated
  inspect command. Don't make one command duplicate another's job.
  *Counter-example: a doctor check printed fifteen "field: origin" lines,
  most of which said "global" — replaced by one line naming the two
  overrides.*
- **Annotate at the granularity of the claim.** If one sub-part of a
  composite value has a different source or state, say it on the sub-part;
  don't relabel the whole. *Counter-example: an env-injected API key
  relabeled an entire endpoint block "(environment)" although its URL and
  model came from a file — fixed as "key from env" with the block label
  unchanged.*
- **Re-read neighboring labels after adding metadata.** New suffixes collide
  with existing value labels. *Counter-example: "Embedding dimensions:
  default (default)" — the value was renamed "auto".*
- **Machine-readable output is a contract.** Porcelain/TSV/JSON output never
  gains decoration, notices, or annotations; informational text goes to
  stderr or the human-format path. Absence is part of the contract — write
  the negative test (`"(project)" not in stdout`).
- **Never truncate the payload.** Paths, IDs, and URLs in diagnostics must
  survive narrow terminals un-ellipsized (disable auto-wrap/crop for those
  lines); a truncated path cannot be copied into the next command.

## Error messages

Every error answers three questions: what happened, where, and what to do
now. The strongest pattern: name the offending file or input, list the
rejected fields, list the allowed fields, and say where the rejected setting
belongs instead. Fail loudly rather than degrade silently; when catching an
exception purely to suppress a traceback, keep the message intact.

## Documentation

- **One canonical home per fact.** Details that change together — field
  lists, precedence chains, supported values — live in exactly one document;
  every other mention links to it. Legitimate copies: artifacts distributed
  standalone (a bundled skill file that ships without the repo), and
  genuinely surface-specific nuance. *Counter-example: a seven-field
  allowlist pasted into five docs.*
- **Restating and linking is a bug, not thoroughness.** If a section
  duplicates the canonical content and then ends with "see X for the full
  contract", it already is the full contract — delete the restatement, keep
  the link and whatever is specific to this surface.
- **Insertion respects adjacency.** Before adding a section, check what the
  surrounding paragraphs attach to. *Counter-example: a new section landed
  between a flags table and its output-format footnote, orphaning the
  footnote in the wrong chapter.*
- **Adjectives need evidence.** "Recommended", "faster", "better" come from
  your own benchmarks, not optimism. *Counter-example: a feature was about
  to ship commented "# recommended" while the project's own eval showed it
  losing to the default on strong models — shipped as "optional".*
- **Every README section has one job.** Positioning sections ("Why X?")
  don't accumulate feature bullets; quick-starts don't explain architecture.
  A README stays lean and links into the docs — detail accumulating in the
  README usually means it left its canonical home.
- **Reminders name the most-forgotten item only.** A guideline that
  enumerates every artifact reads as noise and gets skipped whole. "Update
  whichever docs the change affects — the bundled skill is the easiest to
  forget" beats a list of six file types.

## Sync sweep for behavior changes

A behavior change is unfinished until its copy sites agree. Grep for the old
wording across, in rough order of forgettability:

1. `--help` option strings — the most-missed site: a flag's help kept saying
   "show current configuration" after the command learned origin labels,
2. centralized message/string modules and command docstrings,
3. README and docs pages,
4. bundled skill files, plugin metadata, MCP tool descriptions (these are UX
   for agents — same rules apply),
5. roadmap or status notes describing the old behavior.

## Testing copy

- Assert flattened text or behavior, not console formatting: consoles wrap
  (~80 columns under test runners), so multi-word substrings split across
  lines — `" ".join(output.split())` before substring assertions.
- Color env leakage: `FORCE_COLOR` / `COLORTERM` in the invoking shell make
  rich consoles emit ANSI into captured output; clear them for test runs.
- For machine formats, assert what must be absent, not only what must be
  present.
