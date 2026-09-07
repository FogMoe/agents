---
name: product-writing
description: "Write, edit, or review UI copy, CLI messages, help text, code comments, and technical documentation covering product behavior, errors, status, setup, compatibility, or technical results."
license: Apache-2.0
metadata:
  author: scarletkc
  source: https://github.com/scarletkc/agents
  summary: "Write accurate product copy and useful technical docs."
---

# Product Writing

Help the reader understand what is happening and what they can do next.

## Work from the task

Use only the sections relevant to the requested copy. Preserve the user's
meaning, terminology, audience, and requested format. Follow existing product
conventions where they help readers recognize controls, commands, and states.
A wording task does not itself authorize changes to product behavior or a
reorganization of the documentation.

Ground behavioral claims in supplied facts, the relevant implementation or
specification, or an observed result. When a fact cannot be verified, identify
that uncertainty where it matters and complete the parts that are supported.
Do not invent behavior or a cause to make the text sound complete.

## Interface copy, errors, and help

- **Name the action or state accurately.** Distinguish saving a setting from
  testing a connection, accepting a request from completing a job, and partial
  success from full success. For example, a queued export should not announce
  that a file is ready to download.
- **Make recovery useful.** Identify what failed and the relevant input or
  operation. Include a next step when it is known and actionable. An unknown
  network failure does not establish that credentials are wrong. Put detail
  in the message, an expanded view, or a specific help link as the interface
  allows; an error need not fill a fixed template.
- **Preserve meaningful distinctions.** Keep prerequisites, limits, and
  consequences that affect the reader's decision. Use the product's names for
  controls and commands. Do not shorten away which item an action affects or
  imply that an irreversible action is temporary.

## Status and diagnostic output

- **Describe the state the label promises.** Effective settings account for
  runtime overrides; stored settings should be identified as such. If only
  the API key comes from the environment, label that field rather than the
  entire endpoint as environment-provided.
- **Keep failure visible.** Distinguish unknown or unavailable values from
  empty, missing, or default values. If partial results are supported, identify
  what could not be checked. Follow the project's failure behavior instead of
  introducing a fallback merely to produce a message.
- **Preserve output contracts.** Keep prose and decoration out of JSON, TSV,
  and other machine formats. Use existing diagnostic channels for explanations.
  Keep paths, IDs, and commands complete where users need to copy them, subject
  to the product's redaction rules.
- **Give diagnostic views distinct jobs.** When a dedicated inspection command
  already provides all values and origins, a health summary can focus on
  deviations, failures, and their sources, with a pointer to full details.
  Without that separate view, preserve the values needed to investigate the
  problem. Fifteen normal `field: origin` rows can bury the two overrides that
  matter, but removing the only available configuration view loses information.
  Re-read adjacent labels to catch duplication such as `default (default)`.

## Documentation and technical explanations

- **Give each page one responsibility.** A how-to completes an operation, a
  reference defines a contract, a design record explains choices, and a report
  presents findings and their basis. Put a section on the page that owns its
  reader question. When a page mixes independent tasks, separate them and leave
  a useful pointer at the boundary. An overview's responsibility is orientation:
  summarize the available paths and link to their details instead of becoming
  a second reference manual.
- **Keep README sections focused.** The introduction identifies the product,
  its audience, and its purpose. Positioning explains why someone would choose
  it. Quick-start instructions give the shortest complete path to a useful
  result, including prerequisites, commands, and essential caveats. Full option
  catalogs, architecture explanations, and decision histories belong in their
  respective documents, linked from the relevant section. Do not turn a quick
  start into an architecture tour or a positioning section into a feature dump.
  Keep a compatibility warning beside the step it affects; moving background
  detail must not hide a condition needed to follow the instructions safely.
- **Keep reasons near the decisions they support.** A setup step may need a
  short explanation of why a prerequisite matters. A long history of rejected
  designs usually belongs in a design record linked from the guide, unless
  that history is the page's purpose. Reports need enough method, source context,
  assumptions, and limitations for readers to assess the findings.
- **Separate summaries from competing specifications.** Keep one maintained
  source for a detailed contract. A summary explains what the reader needs now;
  a second complete field table, default list, or precedence rule creates
  another specification to maintain. For example, a README can show a minimal
  configuration and link to the full schema instead of copying all seven fields
  into another table. Detailed repetition may be necessary for independently
  distributed artifacts; check how those copies stay synchronized.
- **Plan how changeable facts stay correct.** Supported versions, pinned install
  commands, and compatibility limits may be necessary. Verify them against the
  maintained source, then check what will keep them aligned on the next change:
  generation, an existing release check, or an explicit maintenance responsibility.
  Avoid adding a second hand-maintained copy of a build ID, migration count, or
  current deployment version just to make a page self-contained. Prefer a
  pointer or generated value when the reader needs the current answer. Preserve
  version constraints that are part of the instructions; do not remove them
  simply because versions change.
- **Distinguish records from live state.** A dated report can record the version
  and status actually observed, with the evidence and limits of that observation.
  A standing operational guide should direct readers to the command or dashboard
  that answers what is running now. A merged change alone does not establish
  deployment, and a successful deployment alone does not establish every health
  or verification claim.
- **Make the next reference useful.** Link to the section, command, API entry,
  or symbol that answers the reader's question. For implementation details,
  `PROTOCOL_VERSION` is a useful pointer; a repository root leaves the reader
  to search again. For normal setup, prefer user-facing instructions. Keep caveats
  next to the steps they qualify and preserve working anchors.

## Comments and standalone artifacts

Read titles, comments, and deliverables as someone who has not seen the working
conversation. Remove abandoned options and temporary scope qualifications that
make sense only in that conversation. An export button title does not need
"without the bulk-download panel" if readers were never offered such a panel.
Keep exclusions when they explain a real contract, compatibility limit, or
tradeoff the reader needs; preserve history in documents requested to record it.

Comments are most useful for reasons the code does not make apparent: ordering
constraints, upstream defects, compatibility workarounds, and invariants a later
edit could break. Explain an alternative when it is one a maintainer would
reasonably reach for. For example, a comment explaining why a lock must be
released before invoking a callback can prevent a deadlock; "release the lock"
merely repeats the operation. Do not replace that reason with a shorter restatement
of the code. Keep public API documentation and useful algorithm overviews as well.

## Claims and evidence

Match the support to the claim. Performance comparisons need applicable
measurements or a cited result with its scope. Compatibility claims need the
relevant implementation or maintained specification. An editorial recommendation
can explain a concrete benefit, such as naming the failed field so the reader
can locate it; recommending clearer wording does not require a benchmark.

Keep observations, hypotheses, preferences, and recommendations distinct.
Preserve user-provided opinions as opinions. Qualify unsupported claims or
explain the gap rather than invent proof or erase useful uncertainty.

## Review and verification

In a review, identify the wording, its effect on the reader, and a concrete
correction when the evidence supports one. If the copy already works, say so;
optional preferences should not become required rewrites. For an editing task,
make the requested edits and explain consequential choices only as needed.

Check meaning, terminology, formatting, and affected links. When behavior
changes, search for dependent help text, errors, documentation, and bundled
skill descriptions that need the same update. Keep catalog and localization
entries in sync where applicable; avoid turning a small edit into a general audit.

Use the project's relevant checks. When output behavior changes, cover success
and failure: parse machine formats and check channels; for human messages,
assert the relevant information without relying on incidental wrapping or color.
