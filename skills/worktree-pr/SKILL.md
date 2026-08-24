---
name: worktree-pr
description: "Decide whether a task deserves its own git worktree and, if chosen, run it end to end: branch from the integration branch rather than the current tree, keep the main working copy untouched while the task runs, compare the result against the untouched baseline before declaring it done, and prepare it for a pull request instead of merging. Use when a request says to do the work in a new worktree or branch, when a change is large or risky enough that the main tree should stay usable, when several tasks need to run in parallel on one repository, when a result has to be diffed against current behavior, and when deciding where screenshots, builds, and other artifacts produced in a worktree should end up."
license: Apache-2.0
metadata:
  author: scarletkc
  source: https://github.com/scarletkc/agents
  summary: "Optionally run a task in its own worktree: branch from the integration branch, compare against the baseline, and prepare it for a PR."
---

# Worktree & PR

A worktree buys two things: the main working copy stays usable while the task
runs, and the untouched copy remains available as a baseline to compare
against. Both are worth real setup cost, and neither applies to every change.

This covers the isolation mechanics. How large the change itself should be is
[`scoped-change`](https://github.com/scarletkc/agents/blob/main/skills/scoped-change/SKILL.md),
and it applies inside a worktree exactly as it does anywhere else.

## Deciding

Consider a worktree when at least one holds: the task is large enough that a
half-finished state would block other work, several tasks need to progress on
the same repository at once, the result has to be compared against current
behavior, or the change is risky enough that abandoning it should cost
nothing.

Skip it when the change is small, self-contained, and reviewable in one pass.
Setting up an isolated copy for a typo fix or a one-line config edit costs
more than it saves, and the extra branch, directory, and PR are all overhead
that someone pays later. When the requester says to work directly on the
current branch, that decision is already made.

## Running

- **Branch from the integration branch, not from whatever is checked out.**
  The point of the isolated copy is a clean starting state; inheriting
  unrelated in-progress edits forfeits it and makes the eventual diff
  unreadable. Fetch first so the base is current, not a stale local ref.
- **Leave the main working copy alone while the task runs.** Editing both
  defeats the isolation and destroys the baseline. If the task turns out to
  need a change in the main tree, stop and say so rather than reaching
  across.
- **Parallel worktrees stay independent only while they stay disjoint.** Two
  copies of one repository editing the same files converge into a conflict
  nobody scheduled, and the cost lands at merge time rather than now. Before
  opening a second one, check what the first is touching.
- **Name the artifacts' destination explicitly.** Screenshots, builds, and
  exports produced inside a worktree vanish with it. Anything the requester
  needs to see must be written somewhere durable, or attached to the PR, and
  the location has to be stated rather than assumed.

## Before declaring it done

- **Compare against the untouched baseline, not against expectation.** The
  reason to keep a clean copy is to run both and see the difference. For
  behavior changes this means exercising the old path and the new one; for
  visual changes it means the same view captured twice. "Should be
  equivalent" is a claim, and the baseline is right there to check it.
- **Account for what the tooling added.** Generated output, formatter churn,
  and dependency lock updates accumulate in an isolated copy without anyone
  choosing them, and they are indistinguishable from intent once merged.
  Either explain why each belongs in this branch, or drop it.

## Landing

Follow the user's established authorization preferences. If committing,
pushing, or opening a pull request requires explicit authorization, complete
and validate the local changes, then hand over the exact commands until
authorized. When authorized, push the branch and open a pull request describing
motivation, the commands exercised, and anything reviewers must check by hand;
leave merging to the repository owner unless told otherwise. Say plainly which
parts are done, which are unverified, and which were deliberately left out,
since a worktree's isolation makes it easy to report an untested result as
finished. Once the branch has landed, remove the worktree; a stale copy of a
merged branch is a trap for the next session that opens it.
