---
name: marketing-copy
description: "Write outbound promotional copy for a product or project: launch and update posts for community platforms and social media, store page descriptions and short blurbs, landing page headlines and calls to action, press-style announcements, and the naming of a product for another language or market. Covers what may be disclosed publicly, keeping claims traceable to shipped changes, and writing a headline that carries information instead of hype. Use when drafting or revising anything aimed at people who do not use the product yet, and when deciding whether a link, key, price, or unreleased detail can appear in public copy."
license: Apache-2.0
metadata:
  author: scarletkc
  fogmoe-source: https://github.com/FogMoe/agents
  fogmoe-summary: "Write outbound promo copy that stays truthful, discloses only what may be public, and earns attention without hype."
---

# Marketing Copy

Outbound copy reaches people who have no product context and no reason to
finish reading. It is also the surface where a disclosure mistake is
permanent: a post can be deleted, a screenshot of it cannot. Both facts push
the same way, toward concrete claims a reader can check.

This covers copy aimed outward. Product-internal strings and documentation
follow [`ux-writing`](../ux-writing/SKILL.md); matching the author's personal
voice is [`talk-like-scarletkc`](../talk-like-scarletkc/SKILL.md).

## Disclosure comes first

Decide what may be public before writing, because the draft is where a leak
gets normalized.

- **Keys, invite codes, and credentials are not copy.** Anything that grants
  access belongs in the channel that distributes it under its own terms,
  never inline in a public post, and never pasted into a draft "to be removed
  later".
- **An unreleased or unlisted URL stays unlisted.** A link that has not been
  announced is not published just because it resolves. The same applies to
  endpoints, staging hosts, and pages reachable only by those already told.
- **Platform rules bind the copy, not just the account.** Each destination
  has its own limits on what may be promoted, linked, priced, or given
  away, and they differ between platforms carrying the same post. When a
  rule makes a detail unpostable, drop the detail; hinting at it obliquely
  to stay within the letter of the rule is the same violation with worse
  writing.
- **Unshipped work is not a feature.** Roadmap items, planned platforms, and
  anything gated behind review get described as what they are, or left out.
  Announcing a date creates an obligation the copy cannot see.

When a constraint blocks a detail the requester wanted to include, say which
detail and why, and let them decide, rather than quietly dropping it or
quietly keeping it.

## Claims stay traceable

Take substance from what actually shipped: the changelog, the commit range,
the release notes. Every concrete claim should trace to one of those, and
specifics beat adjectives at the same length. A number, a mechanism, or a
before-and-after carries conviction that "greatly improved" cannot, and it
also survives a reader who checks.

Never invent a metric, a benchmark, a user count, a review quote, or a
comparison against a named competitor. When the honest version is thin, that
is information about the release, not a prompt to inflate it.

## Earning the read

- **The opening line delivers the news.** It is the only part most people
  see. A headline that describes the category ("a new update is here")
  spends the reader's only guaranteed attention on nothing.
- **Say what it is before why it matters.** A reader who cannot tell what the
  product does will not care that it improved.
- **One post, one thing to take away.** Everything else is support, and a
  post arguing several unrelated points lands none of them.
- **Ask for one action.** Name it specifically and put it where the reader
  arrives at it. Two competing asks split the response.
- **Skip the promotional register.** Revolutionary, seamless, game-changing,
  and unleash read as filler because they appear in every launch post
  regardless of what shipped. So do manufactured urgency and invented
  scarcity.

## Naming across languages

A product name rendered for another market is a naming decision, not a
translation. Check that the candidate is pronounceable and memorable for
that audience, carries no unintended meaning, and does not collide with an
existing product in the same category. Prefer a name the audience can
search, and once a rendering has shipped anywhere public, keep it stable. A
second name for the same product splits every search result and every
conversation about it.
