---
name: daily-loop
description: "Session-start routing table (auto-triggered): feature → addy-code; returning → recall; 3+ steps → planning-with-files; pre-merge → zord-multi-agent-review pr <ref> --yes."
---

# Daily Loop — Workflow Routing Table

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Session-start routing table that maps a situation — new feature, returning
work, a multi-step task, pre-merge, or being stuck — to the required skill
chain, so workflow decisions are enforced rather than left to advice. It has
no slash command and no arguments of its own; a SessionStart hook injects its
routing tables at the start of a session.

| Option | Values | Default | Effect |
|---|---|---|---|
| *(none — auto-triggered)* | n/a | n/a | Injected by the SessionStart hook; not invoked with explicit arguments |

This skill encodes the standard workflow routing decisions so they are harness-enforceable rather than advice. Apply this at the start of every session to pick the right chain.

**This skill is not user-invocable.** It has no slash command; `~/.claude/hooks/daily-loop-inject.sh` injects its routing tables at SessionStart (set `DAILY_LOOP_INJECT=0` for unattended children whose brief owns the routing), rather than firing on `/daily-loop`.

## Session-Start Ritual

Set `/model` and `/effort` once, at the start of the session — a mid-session
switch breaks the prompt cache and forces a full re-prefill at full price.
Default effort is `low`; raise it only on demonstrated need, per the R9 policy
already defined in `llm-fit-check` (`ClaudesMods/llm-fit-check/commands/model-route.md`,
"Effort defaults low (R9)") — not duplicated here. On a fresh session, run
`/context` to audit what is loaded and `/mcp` to disable servers this session
doesn't need.

## Session Type → Skill Chain

| Situation | Required skill chain |
|-----------|----------------------|
| New feature or new functionality | `addy-code` (interview → plan on disk → context pack → thin slices with `addyosmani-test-driven-development` → review loop → draft PR). A heavier workflow (`zord-multi-agent-developer`, `zord-code-rinse-repeat`, `baton-runner`, `big-next-job`, `build-lil-things`) only when the user names it or the brief calls for it |
| Returning to in-progress work | Check `memory/MEMORY.md` + recent session summaries in `~/.claude/session-data/` first, then resume |
| Any task with 3+ tool calls or steps | `planning-with-files` (create task_plan.md before touching code) |
| Pre-merge / pre-PR | `zord-multi-agent-review pr <ref> --yes` as the quality gate before opening a PR |
| Stuck / uncertain which approach | stuck → `lateral` (diagnoses the symptom, picks the technique); choosing between approaches → `ThinkTime:idea-panel` (parallel mental-model lenses, ranked) |

## Brainstorm Routing

| Goal | Use |
|------|-----|
| New product, business direction, or research angle | `ThinkTime:idea-nebula` |
| Scope or design a feature | `addyosmani-interview-me` (vague ask) → `addyosmani-spec-driven-development` |
| Attack an existing plan or proposal | `grill-with-docs` |

## Rules

1. **Never skip scoping for anything that is not a trivial bugfix.** "Let me just start" → use `addyosmani-interview-me` first (addy-code step 0), then `addyosmani-spec-driven-development` for a feature.
2. **Never skip plans for multi-step work.** 3+ steps → `planning-with-files` before the first edit.
3. **Never merge without a review.** Feature branch → `zord-multi-agent-review pr <ref> --yes` before opening PR.
4. **Returning work → recall first.** Read `memory/MEMORY.md` and the latest entry in `session-data/` before asking what was last done.
5. **Stuck → `lateral`, approach choice → `ThinkTime:idea-panel`; never a thinking lens at random.** `lateral` diagnoses the symptom and picks the technique; `idea-panel` runs the mental-model lenses in parallel and ranks the result.
6. **Delegate for breadth, never to check your own work.** Spawn subagents for large, genuinely independent, parallelisable tracks. Do not spawn one to verify, re-check, or second-guess work you just did — that is the current model's default behaviour already, and paying an agent for it buys a second opinion on your own reasoning rather than a new one.
7. **Blind-spot pass before implementation.** After the plan, before the first edit, answer in the transcript: "what are the unknown-unknowns here — what would someone with more context on this codebase or domain flag that the plan missed?" Address or explicitly park each answer. (R13, ClaudeConfig#172.)
8. **Comprehension check before merging a large change.** Before `gh pr merge` on a diff spanning many files or an unfamiliar subsystem, state in the transcript, in your own words, what changed and why. Unable to → re-read the diff first; the check is of understanding, not of the code (rule 3's review already covered that). (R13.)

## Why `verification-before-completion` left the feature chain

It was a mandatory step in the chain above until 2026-08-15. Claude Opus 5
self-verifies and self-corrects without being told to, so an explicit
"now verify" step compounds with behaviour that is already happening and costs
tokens without changing the outcome.

**The claim discipline stays.** Never assert that tests pass, a build is green,
or a bug is fixed without fresh output in the transcript showing it. That is an
honesty rule about what you say, and it is unaffected — what changed is that it
is no longer a ritual step in a chain, because a chain step is exactly the shape
that gets performed rather than meant.

Rule 3 also stays as written. One review pass at PR time is correct and cheap;
it only ever looked excessive because two adversary layers used to run beneath
it, and refutation is opt-in now.

## Precision Principle

Fewer, non-contradictory instructions produce better routing than more instructions. This skill exists to enforce the critical chain — don't add steps outside this table without a concrete reason.
