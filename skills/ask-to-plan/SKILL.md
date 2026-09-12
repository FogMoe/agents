---
name: ask-to-plan
description: "Guide a user from an unclear idea to an actionable plan through the agent harness's native ask tool and clickable choices. Use when the user wants a guided requirements interview, step-by-step questions, help deciding what to build, or a button-led path from goals to scope, solution, and technology choices. Do not turn an ordinary implementation request or a single clarification into an interview."
license: Apache-2.0
metadata:
  author: scarletkc
  source: https://github.com/scarletkc/agents
  summary: "Turn a rough idea into clear goals, requirements, a solution, and an actionable plan through guided questions and native choices."
---

# Ask to Plan

Help the user discover what they want by making one useful decision at a time.
Move from broad outcomes to concrete requirements and then an implementable
plan. The user should be able to make progress by choosing buttons, including
when they have no idea yet or do not know technical terms.

The default deliverable is a plan. Starting this interview or accepting a
solution does not itself request implementation. If the user later asks to
build it, carry the settled requirements into that work.

## Use the harness's actual ask tool

Identify the native structured-question tool exposed in the current session,
such as `request_user_input`, `request_user_input_async`, or the harness's
equivalent. Use the tool to present choices. Follow its actual schema and
current mode restrictions, including question limits, option limits, and
whether the interface already supplies free-text input or an Other option.
Tool names here are discovery hints, not a promise that a tool is available.

Start with a brief explanation of the next decision and one native question.
Do not print a questionnaire, simulate buttons in Markdown, or produce a
complete solution before learning the user's intent. If structured input is
unavailable or fails, explain that buttons are unavailable here and use a
concise text question if the harness permits it. A skill cannot add a missing
tool or override its restrictions; do not change agent settings to enable it.

For an asynchronous ask tool, submission acknowledgement means the question is
pending. Wait for the actual answer before asking a dependent question or
settling that decision; only independent inspection can advance meanwhile.
If a prompt is dismissed or returns no answer, follow the harness's rules for
waiting or continuing with assumptions. Keep unanswered choices unresolved or
explicitly provisional. A preselected option, timeout, or tool success is not
the user's choice.

## Make each question easy to answer

- Ask one question per round by default. Its answer should change the goal,
  scope, approach, or next question. Skip details that do not affect the plan.
- Offer two or three short, distinct choices within the tool's limits. Explain
  the practical consequence of each in a short description when supported.
  Ask about one dimension; do not bundle audience, platform, and budget into
  a single choice.
- Build options from what is already known. Use the user's language and level
  of detail. A beginner can choose "only on my computer" or "shared across
  devices" without knowing database names.
- Provide a useful uncertainty choice when needed, such as "Help me choose"
  or "Show me examples". After that choice, offer concrete directions or a
  reasoned recommendation; do not repeat the same difficult question.
- Recommend an option when the known needs support it and explain why. If
  the tool requires a recommended option, ground it in the stated context or
  a disclosed provisional assumption. Do not invent a user preference.
- Accept free-text corrections and combinations where supported. Use multiple
  selection only for choices that can coexist; incompatible approaches need
  a single choice. If exact input matters, such as a project path, request it
  through a supported input surface instead of guessing it from buttons.

Users can change a previous answer, ask for an explanation, let the agent
choose, or ask for the plan now. Mention these possibilities briefly when
useful; they do not all need to occupy an option in every question.

## Narrow from outcomes to implementation

First extract what the user has already supplied. For an existing project,
inspect the relevant context within the authorized scope before asking for
facts the project can answer. Enter at the first consequential gap instead
of restarting a prepared sequence.

Use the following progression as a map, not a mandatory questionnaire. After
each answer, choose the next uncertainty whose resolution most changes the
plan. Skip settled or irrelevant areas and revisit earlier decisions when a
new constraint changes them.

| Area | Decision to uncover |
|------|----------------------|
| Direction | What improvement does the user want, and for whom? If they have no idea yet, offer a few concrete outcomes to explore. |
| Problem and success | What is difficult today, what main scenario should become possible, and what observable result would count as success? |
| First useful scope | What must the first version do, what can wait, and what is outside this effort? Resolve competing priorities with a concrete tradeoff. |
| Constraints | Which limits actually affect this idea: existing tools, intended devices, collaborators, data, budget, deadline, or maintenance capacity? |
| Solution | Which approach fits the chosen outcome and constraints? Compare meaningful alternatives only where the choice changes the result. |
| Implementation plan | What tools or technology are needed, what comes first, and how will each useful result be checked? |

For example, after "I want to build something but have no idea", the first
native question might offer "Save time on a repeated task", "Make something
for others to use", and "Explore a few ideas". Selecting the first should
lead to relevant tasks to simplify. Selecting the second should lead to an
audience or problem to serve. Neither answer establishes a website, a mobile
app, an AI feature, or a technology stack.

Once the purpose is clear, specialize the questions to its domain. A booking
tool may need to settle who manages availability; a learning plan may need
to settle what the learner wants to practice. Do not keep asking generic
startup questions after a concrete workflow is known.

## Derive the technical choices

Ask about consequences the user can judge before asking about implementation
preferences. Work out local versus shared use, important data needs, external
integrations, and maintenance expectations only as relevant to the idea.

Then recommend a coherent, appropriately sized solution. For software, map
each proposed stack component to a requirement and explain the tradeoffs in
plain language. Respect an existing stack or an explicit technical preference;
inspect compatibility before recommending a change. A user who says "you
choose" has delegated that decision, so make it and record the reason rather
than continuing to quiz them about frameworks.

Verify changeable claims such as service pricing, supported integrations, and
compatibility against current authoritative sources when they affect the
choice. If verification is unavailable, mark the assumption and include the
needed check in the plan. Do not force software architecture or a technology
stack into a non-software outcome; specify the relevant tools and method.

## Carry decisions forward

Maintain a compact working record in conversation context: the goal, accepted
decisions, constraints, agent recommendations or assumptions, and consequential
open questions. Keep user choices distinct from inferred facts. Show a short
recap at a change of direction or before comparing solutions, rather than
reprinting the full record after every answer.

If the user changes an earlier choice, update dependent scope, solution, and
stack decisions. Preserve answers that still apply. When answers conflict,
explain the specific tradeoff and ask which should take priority. Do not keep
an obsolete decision in the final plan or silently resolve a material conflict.

## Converge and deliver the plan

Stop exploring when the goal and audience, first useful scope, major
constraints, solution, and acceptance criteria are clear enough for someone
to take the next step. Unknowns that could overturn feasibility need a choice
or an explicit validation task. Routine implementation details can remain
agent decisions; they do not justify more interview rounds.

Show a compact preview of the proposed outcome and let the user choose to
receive the plan or revisit the part that still feels wrong. This is alignment
on requirements, not permission to execute. If the user already asks to finish
or output the plan, deliver it directly and label unresolved assumptions.

Write a self-contained plan at a depth appropriate to the task. Cover:

- The goal, intended users, and observable success criteria.
- The main scenario and requirements, first-version priorities, and deferred
  or excluded work that matters to the agreed boundary.
- The chosen solution and why it fits; for software, the proposed technology
  stack and the role of each component.
- An ordered implementation path with concrete deliverables, dependencies,
  and acceptance checks for the useful milestones.
- Remaining assumptions, consequential risks or unknowns, and how to resolve
  them, followed by the first actionable step.

Do not fill the plan with invented budgets, deadlines, scale targets, or
confirmed-sounding guesses. If the user ends discovery early, deliver a useful
provisional plan with its gaps visible. End after the requested plan unless
the user has also requested further work.
