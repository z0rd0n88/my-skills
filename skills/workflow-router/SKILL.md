---
name: workflow-router
description: Use at the start of an engineering task, and whenever a task needs or would be improved by a workflow, to pick the one that fits. Routes three kinds. The process to follow (feature, bug fix, spike, TDD-Ralph loop, refactor, migration, dependency upgrade, debugging, onboarding, incident response, code review). The agent orchestration shape when work outgrows one context (classify, fan out, adversarial verify, generate and filter, tournament, loop until done). The durable workflow design for application code (trigger, step shape, engine such as Temporal or Inngest, reliability checks). Also says when no workflow is needed.
---

# workflow-router

Picks the workflow that fits the situation and states it before the work starts. "Workflow"
means three different things, so the router has three lanes:

| Lane | What it decides | Reference |
|---|---|---|
| **Process** | How you and the user structure a piece of engineering work, and which gate must not be skipped | [references/engineering-workflows.md](references/engineering-workflows.md) |
| **Orchestration** | How to spread a step across many agents when it is too big for one context | [references/agent-orchestration.md](references/agent-orchestration.md) |
| **Durable** | How application code runs a multi-step process on a workflow engine | [references/durable-workflows.md](references/durable-workflows.md) |

[references/catalog.md](references/catalog.md) lists all 42 named choices across the lanes on one
page, for looking a name up.

Routing takes seconds. Do it, say the route in a line, then read only the reference section for
the workflow you picked. A change with no behaviour at stake (a typo, a comment, a version
string) needs no workflow: say so and make it. The kind of work picks the workflow, not the size
of the diff, so a one-line fix to wrong behaviour is still a Bug Fix.

## Step 1 — which lanes apply?

- Any work on a codebase gets a **process** workflow (Step 2).
- Add an **orchestration** shape when one step of that process is too large for one context, has
  many independent items, or needs independent verification (Step 3).
- Add a **durable** design when the thing being built or changed is itself a multi-step process
  that must survive failures: payments, webhooks, long waits, background jobs, cron (Step 4).

Lanes stack. "Add an order-fulfilment flow" is Feature Implementation (process) building a
sequential event-driven workflow (durable). "Replace library X in 400 files" is Migration
(process) executed by the Migrate shape (orchestration).

Not routed here: a build, test or deploy pipeline goes to `addyosmani-ci-cd-and-automation`.

## Step 2 — process lane: pick one primary workflow

Ask in this order and take the first match.

| # | Question | Workflow | Gate you must not skip |
|---|---|---|---|
| 1 | Is production broken right now? | Incident Response | Mitigate before diagnosing; always write the postmortem |
| 2 | Is someone else's change in front of you to judge? | Code Review | Understand the intent before commenting; triage every comment |
| 3 | Is behaviour wrong and you can't yet explain or reproduce it? | Debugging | Reproduce before theorising; keep a written hypothesis log |
| 4 | Is behaviour wrong, reproducible, with the right behaviour known? | Bug Fix | A reliable reproduction, then a failing test, before the fix |
| 5 | Is the real question "would this approach even work"? | Spike / Prototype | Time-box it and throw the code away |
| 6 | Is the codebase unfamiliar and you need more than one change's worth of it? | Onboarding | One small real contribution early |
| 7 | Is it one dependency moving to a newer version? | Dependency Upgrade | Read the full changelog; one major version at a time |
| 8 | Is it replacing pattern X with Y across the codebase? | Migration | Inventory before estimating; not done until the old path is deleted |
| 9 | Is it structure only, with no behaviour change? | Refactor | Tests cover the area first; one named transform per commit |
| 10 | Is it new capability? | Feature Implementation | The plan is approved before code is written |
| 10a | …and large, split into spec'd tasks, with fast deterministic tests and a sandbox? | TDD-Ralph loop | A sandbox and human-written failing tests before the loop runs |

The common mistake is running Feature Implementation for everything: a full plan for a one-line
null check, or a fix started before the bug is reproduced.

**Composition rules**

1. **One workflow is primary.** A small refactor inside a feature is a sub-step with its own
   commit. When a sub-task starts to dominate, ship what you have and start that workflow fresh.
2. **Hand-offs are written down.** Debugging ends in a conclusion that Bug Fix starts from. A
   Dependency Upgrade stays the starting workflow even for a big version jump, and hands off to
   Migration when the new version has no drop-in replacement or a breaking change touches many
   files. Incident Response
   hands off to Debugging once service is stable.
3. **Keep every gate.** When workflows nest, each one's gate still applies.

Gates that act outside the repo stay with the user: reverting or failing over in production,
posting review comments, and starting a TDD-Ralph loop all wait for their go-ahead.

## Step 3 — orchestration lane: pick a shape

Take the simplest shape that fits. Shapes stack (fan out, then verify, then loop).

| Shape | Pick it when |
|---|---|
| Classify and act | Mixed inputs that each need a different handler, or untrusted content that should be read by one agent and acted on by another |
| Fan out and synthesize | The work splits into non-overlapping slices and the answer needs all of them |
| Adversarial verification | Output could be plausible and wrong; separate agents try to refute each item |
| Generate and filter | A matter of taste; overgenerate, then a different agent judges down |
| Tournament | Many candidates to rank, where scoring each one cold drifts |
| Loop until done | The number of attempts can't be known in advance |

Ready-made combinations for engineering work (Understand, Design, Review, Research, Migrate),
the quality patterns and the scripting rules are in the reference.

**Opt-in.** In Claude Code these run through the `Workflow` tool, which needs the user's
explicit opt-in: they ask for a workflow or a fan-out, `ultracode` is on, or they invoke a skill
that calls it. Selecting a shape is always allowed; running it is not. Without opt-in, offer it
only when the fit is strong (about five or more independent, substantial units, or findings that
need independent verification): name the shape and the rough agent count in the route, ask, and
carry on with what can be done inline. A weaker fit is done inline without asking. Scout inline
first (list the files, find the call sites) so the run gets a real work-list.

Existing skills already implement some shapes, so use them when the task matches:
`dw-review` and `zord-multi-agent-review` (Review), `branch-off` (best-of-N with judges),
`zord-baton-runner` (a phased build), `code-cleaver` (a whole-codebase audit).

## Step 4 — durable lane: design the workflow

Follow [references/durable-workflows.md](references/durable-workflows.md). In short:

1. **Check it needs an engine.** Money or state that can't be lost half-way, several external
   side effects, long waits, or work that must survive a crash. Otherwise a function, a queue
   job or a cron entry is enough. A framework already in the project wins over any new choice.
2. **Pick a trigger** (event, schedule, direct start) **and a shape** (sequential, parallel,
   orchestrator-worker). Retry and recovery always applies.
3. **Pick the platform:** n8n, AWS Step Functions, Azure Durable Functions, Temporal or Inngest.
4. **Apply the reliability checks** in [references/sharp-edges.md](references/sharp-edges.md):
   idempotency keys, determinism, timeouts, small steps, a failure path.

## Step 5 — state the route

For most tasks, one line before starting:

```
Workflow: Bug Fix — gate: reproduce, then a failing test, before the fix.
```

When lanes stack, one line per lane:

```
Workflow route
- Process:        Migration — gate: inventory first; done only when the old path is deleted
- Orchestration:  Migrate shape (discover → transform per worktree → verify), about 8 agents — needs your opt-in
- Durable:        not applicable
- Open:           <anything you could not determine>
```

A note headed "Suggested workflow route" may already be in context, put there by the optional
hook in [hooks/](hooks/README.md). It is a fast classifier's guess from the prompt alone: use it
as a starting point, check it against Steps 1 to 4, and overrule it when they disagree. It never
counts as the user opting in to a workflow.

Then do the work by the steps in the reference, and stop at each gate until it is met. If the
task changes shape part-way (a bug fix that turns out to need debugging), say so and re-route.

## Examples

| Situation | Route |
|---|---|
| "Checkout total is wrong for orders with a discount" | Bug Fix, if it reproduces; otherwise Debugging first |
| "Tests fail one run in thirty" | Debugging · loop until done to reproduce it |
| "Can Postgres full-text search replace our Elasticsearch?" | Spike · Research shape if the reading is wide |
| "Move every call from Moment.js to date-fns" | Migration · Migrate shape for the bulk |
| "Bump React from 17 to 19" | Dependency Upgrade, 17 → 18 → 19 · stop at each major |
| "Review this PR" | Code Review · Review shape via `dw-review` |
| "Charge the card, ship the order and email a receipt on each purchase" | Feature Implementation · durable: event, sequential, Temporal or the repo's engine |
| "Rank these 200 name ideas" | Generate and filter, or Tournament for the final ranking |
| "Fix this typo" | No workflow |
