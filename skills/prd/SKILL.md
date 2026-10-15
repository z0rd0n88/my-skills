---
name: prd
description: 'Interactive PRD generator: scoping intake, then a 3-4 question interrogation of assumptions, before drafting; not for code-grounded engineering specs (use spec-tacular)'
argument-hint: "[optional-context]"
---

# PRD

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Two mandatory halts** — this skill pauses for user input twice (after
> intake, after interrogation) before it drafts anything. Don't skip ahead on
> a "confident enough" answer; each halt exists to catch a gap the next phase
> can't recover from.

Generates a concise, rigorously tested product requirements document (PRD)
through an interactive scoping-then-interrogation process. Reach for it
instead of drafting a PRD directly when the request arrives thin — a feature
name, a one-liner, or nothing at all — and the risk is guessing the scope
instead of asking. Not for code-grounded engineering specs with `path:line`
citations and acceptance criteria (use `spec-tacular`).

| Option | Values | Default | Effect |
|---|---|---|---|
| `[optional-context]` | free text (optional) | none | Seeds the Intake Phase. Thin or missing context triggers an explicit scoping question instead of guessing. |

## Execution Flow

1. **Intake Phase.** Acknowledge the command. If `optional-context` is brief,
   vague, or missing, ask exactly one question: "What specific feature,
   update, or scope do you want to build?" If the context already states a
   clear feature, scope, and objective, skip straight to step 3 — don't ask a
   question that's already answered.
2. **Halt for Input 1 (Scoping).** Stop and wait for the user to define the
   target feature, scope, and core objectives. Do not proceed on a partial
   answer — if the scope is still ambiguous after this response, ask a single
   sharper follow-up rather than filling the gap with an assumption.
3. **The Grill (Interrogation Phase).** Analyze the scoping response and output
   exactly 3 to 4 sharp, critical questions that expose edge cases, unstated
   assumptions, or missing metrics. Draw from, but don't mechanically cover all
   of, these angles:
   - What is the actual user pain point, and what evidence proves it's real?
   - What is the cost of doing nothing?
   - How does this degrade, break, or fail at scale?
   - What is the most brutal metric that would conclusively prove this feature
     is a failure?
4. **Halt for Input 2 (Defense).** Stop and wait for the user to answer the
   interrogation questions.
5. **Drafting Phase.** Synthesize the intake scope and the interrogation
   answers into the Final Output Structure below. Every weak spot the
   interrogation surfaced should sharpen a specific section — a shaky pain
   point sharpens the Problem Statement, a scale failure sharpens Acceptance
   Criteria — not get dropped once drafting starts.

## Final Output Structure

* **Problem Statement** — sharpened by the interrogation phase, not just the
  raw scoping answer.
* **Goals and Non-goals** — explicitly name what will *not* be built, to
  prevent scope creep.
* **User Stories and Acceptance Criteria** — include the edge cases and
  failure states surfaced in the Grill.
* **Metrics and Success Thresholds** — hard, measurable criteria, including
  the failure threshold from the Grill's "brutal metric" question.
* **Scope and Technical Assumptions** — major constraints, bottlenecks, or
  risks named during scoping or interrogation.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipping Halt 1 because the initial context "seems complete enough" | If a feature, scope, and objective are all explicitly stated, skipping is correct — the halt is for genuinely missing information, not a formality to always perform. |
| Asking more than one question at Intake | Exactly one question, so the user isn't grilled twice. Save the multi-question interrogation for step 3. |
| Answering the interrogation questions yourself | They're addressed to the user. Wait for their response — don't infer answers to move faster. |
| Drafting before Halt 2 resolves | The Grill's answers are load-bearing for the Problem Statement and Metrics sections; drafting without them produces a generic PRD instead of a scoped one. |
