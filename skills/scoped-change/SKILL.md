---
name: scoped-change
description: "Judgment rules for holding a change to the size the request actually defines: not editing surfaces nobody named, not adding speculative compatibility layers, flags, or abstractions, reusing the existing implementation instead of writing a second one beside it, finishing every site the requested change implies, answering a question as a question instead of starting work, and getting consent before expensive or irreversible actions. Use before implementing any requested change, when tempted to add a wrapper, fallback, option, or component that was not asked for, when a change looks like it needs a migration or backward-compatible path, when a request reads as a question rather than a task, and when reviewing a diff for edits outside the stated scope."
license: Apache-2.0
metadata:
  author: scarletkc
  fogmoe-source: https://github.com/FogMoe/agents
  fogmoe-summary: "Hold a change to the size the request defines: no unrequested surfaces, no speculative layers, no half-applied edits."
---

# Scoped Change

A change has one correct size and the request defines it. Overshooting and
undershooting are the same failure — a boundary that was never located —
and they fail differently: unrequested edits surface in review or in
production, missing edits surface as the user finding them. Locate the
boundary first, then be exhaustive inside it and inert outside it.

## Outside the boundary

- **Edit only the surfaces the request names.** A request that names one
  layer is a request about that layer, and the neighboring layers stay
  untouched even when they look wrong. Report what you noticed instead of
  fixing it; a separate observation is cheap, an entangled diff is not.
  *Counter-example: asked to adapt a backend endpoint to an existing signup
  form, an agent redesigned the form too, and the reviewer had to pull the
  two apart before either could ship.*
- **Compatibility is a cost, and someone must already be paying it.**
  Migrations, dual-read paths, deprecated aliases, and version shims are
  correct only when real users hold the old state. Establish that they exist
  before writing one; when they don't, a clean break is the smaller change.
  This is a question of fact, not caution. *Counter-example: an unreleased
  product with no installed base got a save-format migration path for data
  no user had ever written, and the dead branch still had to be maintained
  and tested.*
- **Reuse the existing implementation; never add a second one beside it.**
  If the project already renders this panel, formats this message, or awards
  this promotion, extend that path. A parallel implementation that looks
  correct is worse than an obvious gap, because it diverges silently and
  nothing fails when it does. *Counter-example: a new promotion banner was
  written from scratch next to the existing level-up banner; a release later
  only one of them had the new animation.*
- **Prefer changing an existing rule to adding one next to it.** A new
  constant, flag, or branch that coexists with the rule it was meant to
  replace leaves two sources of truth and doubles the states to reason
  about. *Counter-example: a request to restrict upgrades to a single branch
  arrived as a new second rule constant; narrowing the meaning of the
  original constant was the entire change.*
- **Solve the stated problem, not its general form.** Extension points,
  plugin layers, and configuration surfaces are worth building when a second
  caller exists, not when one is imagined. The simple implementation is the
  deliverable unless the request asked for the general one.

## Inside the boundary

- **Apply the change at every site it implies.** The requested behavior is
  the unit, not the file you happened to open. Before declaring it done,
  grep for the siblings of what you edited — the other cards of that type,
  the other localized strings of that key, the other callers of that helper
  — and confirm each one either changed or correctly didn't.
  *Counter-example: a new card type shipped without the category prefix that
  every other card's label carries, so it read as a different kind of object
  in the UI.*
- **Matching the siblings is part of the request, not extra scope.** A new
  item of an existing kind inherits that kind's required fields, naming
  convention, rarity or tier metadata, and text conventions without being
  told. Ask when the value is genuinely undetermined; don't ship the field
  missing. *Counter-example: a new entity landed without the rarity field
  every sibling declares, and only surfaced when a loader that groups by
  rarity silently dropped it.*

## Before the first edit

- **A question is a question.** "What is the current value", "does X still
  happen when Y", "is this reasonable" ask for an answer and its source, not
  for a fix. Answer with the file and symbol that owns the fact, then stop;
  the follow-up will say whether to change it. *Counter-example: asked what
  the current refresh price was, an agent changed it.*
- **Propose before implementing when the change is structural.** New
  systems, schema changes, and anything touching an agreed-upon design get a
  short plan and an explicit go-ahead first. Rewriting after the fact costs
  more than the round trip, and the plan is where a wrong assumption is
  cheapest to catch.
- **Scope covers cost, not just code.** A full rebuild, a full suite on a
  one-line data edit, a deploy, or a session on a remote host is a decision
  the user owns even when it is technically reversible. Match the
  verification to the change, and ask — or hand over the command to run —
  before anything remote or expensive. *Counter-example: a data-only edit
  triggered a full rebuild and suite on a machine where that costs fifteen
  minutes, twice, before the user asked it to stop.*

## Order of work

- **Lock behavior in tests once it is settled, not while it is moving.**
  Every behavior change still ships with happy-path and failure coverage;
  the point is sequence. Tests and docs written against logic that is still
  under discussion pin the wrong behavior and then argue for it, and the
  rewrite costs more than the wait. Get the logic confirmed, then cover it.
