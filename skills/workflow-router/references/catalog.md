# Catalog: all 42 choices

Every named thing the router can pick, in one place. The first 20 answer "what kind of work is
this?": one process workflow, and where they apply one orchestration shape and one durable
shape. The other 22 are follow-up choices that only come up after that. Each lane also has a
"no workflow" answer, which is not numbered.

Use this to look a name up. The steps, gates and rules are in the file named under each heading.

## Contents

1–11 Process workflows · 12–17 Orchestration shapes · 18–20 Durable shapes ·
21–25 Orchestration combinations · 26–28 Durable triggers · 29–33 Durable engines ·
34–42 Orchestration quality patterns

## Process workflows (11)

Pick exactly one as primary. Detail: [engineering-workflows.md](engineering-workflows.md).

| # | Workflow | Pick it when |
|---|---|---|
| 1 | Incident Response | Production is broken right now |
| 2 | Code Review | Someone else's change is in front of you to judge |
| 3 | Debugging | Behaviour is wrong and you can't yet explain or reproduce it |
| 4 | Bug Fix | Behaviour is wrong, reproducible, and the right behaviour is known |
| 5 | Spike / Prototype | The real question is whether an approach would work |
| 6 | Onboarding | The codebase is unfamiliar and you need a lasting understanding of it |
| 7 | Dependency Upgrade | One dependency is moving to a newer version |
| 8 | Migration | Pattern X is being replaced with Y across the codebase |
| 9 | Refactor | Structure changes, behaviour doesn't |
| 10 | Feature Implementation | New capability, large enough to need a plan |
| 11 | TDD-Ralph loop | A large, fully specified feature with fast tests and a sandbox, built unattended |

## Orchestration shapes (6)

Pick the simplest that fits; they stack. Detail: [agent-orchestration.md](agent-orchestration.md).

| # | Shape | Pick it when |
|---|---|---|
| 12 | Classify and act | Mixed inputs each need a different handler |
| 13 | Fan out and synthesize | The work splits into non-overlapping slices and the answer needs all of them |
| 14 | Adversarial verification | Output could be plausible and wrong, so separate agents try to refute it |
| 15 | Generate and filter | It's a matter of taste: overgenerate, then a different agent judges down |
| 16 | Tournament | Many candidates need ranking and scoring each one cold drifts |
| 17 | Loop until done | The number of attempts can't be known in advance |

## Durable shapes (3)

Pick one; they nest. Detail: [durable-workflows.md](durable-workflows.md).

| # | Shape | Pick it when |
|---|---|---|
| 18 | Sequential | Each step needs the previous step's output |
| 19 | Parallel | Steps are independent and their results are combined at the end |
| 20 | Orchestrator-worker | The subtasks aren't known until the input is examined |

## Orchestration combinations (5)

Pre-built stacks of shapes 12–17 for engineering work. Detail:
[agent-orchestration.md](agent-orchestration.md).

| # | Combination | What it does |
|---|---|---|
| 21 | Understand | Parallel readers, one per subsystem, return a map of how the code works |
| 22 | Design | Several independent approaches go to a judge panel, which returns a scored synthesis |
| 23 | Review | Agents find issues by dimension, then others try to refute each finding |
| 24 | Research | Agents search several ways, deep-read, and return a cited synthesis |
| 25 | Migrate | Agents discover the call sites, transform each in its own worktree, then verify |

## Durable triggers (3)

What starts a durable workflow. Every one has exactly one. Detail:
[durable-workflows.md](durable-workflows.md).

| # | Trigger | Pick it when |
|---|---|---|
| 26 | Event-driven | Something happens: a user action, a webhook, another system's event |
| 27 | Scheduled | The clock starts it: a daily report, a periodic sync |
| 28 | Direct start | A person or a caller asks for this one run |

## Durable engines (5)

Where a durable workflow runs. An engine already in the project wins over all of these. Detail:
[durable-workflows.md](durable-workflows.md).

| # | Engine | Pick it when |
|---|---|---|
| 29 | n8n | Non-developers will build and own it, or it's a quick integration prototype |
| 30 | AWS Step Functions | The stack is AWS-native with Lambdas already written |
| 31 | Azure Durable Functions | The stack is Azure, in .NET or TypeScript |
| 32 | Temporal | Money moves, or correctness across services is critical |
| 33 | Inngest | None of the above: event-driven, serverless, TypeScript, AI steps |

## Orchestration quality patterns (9)

Add-ons that refine a shape. Use as many as the task needs. Detail:
[agent-orchestration.md](agent-orchestration.md).

| # | Pattern | What it adds |
|---|---|---|
| 34 | Adversarial verify | Independent sceptics try to refute each finding; it's dropped on a majority refutation |
| 35 | Perspective-diverse verify | Each verifier gets a different lens, such as correctness, security or reproduction |
| 36 | Judge panel | Independent attempts are scored by parallel judges, then synthesised from the winner |
| 37 | Loop until count | Results accumulate until a target number is reached |
| 38 | Loop until dry | The run continues until several rounds in a row find nothing new |
| 39 | Loop until budget | Depth scales to the token budget the user set |
| 40 | Multi-modal sweep | Parallel agents each search a different way |
| 41 | Completeness critic | A last agent asks what was missed, and its answer becomes the next round |
| 42 | No silent caps | Anything a top-N, a sample or a no-retry rule dropped gets logged |
