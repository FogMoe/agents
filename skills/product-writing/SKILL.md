---
name: product-writing
description: "Write, edit, or review product interface copy, CLI messages, help text, and technical documentation. Use when explaining product behavior, errors, status, setup, compatibility, or technical results. A compact alternative to ux-writing that preserves accuracy and reader context while leaving structure and phrasing to the task. Ordinary conversation, personal voice writing, and code-only reviews are outside its scope."
license: Apache-2.0
metadata:
  author: scarletkc
  source: https://github.com/scarletkc/agents
  summary: "Write accurate product copy and useful technical docs with a compact alternative to ux-writing."
---

# Product Writing

Help the reader understand what is happening and what they can do next.
This skill is self-contained and can be used in place of `ux-writing`.
Use one of these alternatives for a task; there is no prerequisite review
with the other skill.

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
- **Choose useful detail.** A health summary may emphasize problems; an
  inspection view may need complete values. Preserve the context needed for
  either use, and check adjacent labels for duplication or ambiguity.

## Documentation and technical explanations

- **Keep explanations that earn their place.** A short rationale can belong
  beside a setup step. Reports need enough method, source context, assumptions,
  and limitations for readers to assess the findings. Remove production chatter
  and abandoned options that add no useful context; retain relevant tradeoffs
  and requested design history.
- **Avoid competing specifications.** Keep a maintained source for detailed
  contracts and link other pages to it. Summaries and examples beside links
  can make a page usable on its own. Check repeated details for agreement;
  duplication alone is not a reason to delete useful context.
- **Scope changeable facts.** Supported versions, pinned installation commands,
  and compatibility limits may be essential. Check them against the maintained
  source. Date runtime observations in reports; point to a live check when the
  reader needs current state. A merged change alone does not establish deployment.
- **Make the next reference useful.** Link to the section, command, API entry,
  or symbol that answers the reader's question. Keep caveats next to the steps
  they qualify. Preserve working anchors and requested structure; organize by
  the reader's task without imposing a fixed number of sections or purposes.

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
