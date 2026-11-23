# Orchestration lane: shapes for work spread across many agents

How to pick the shape of a multi-agent run when a task is too large for one context window.
This lane sits under the process lane: the process workflow still sets the steps and the gates,
and the orchestration shape is only how one of its steps is executed.

In Claude Code the shapes run through the `Workflow` tool, a deterministic JavaScript script
that fans work out to subagents. The tool's own description and the `workflow-authoring` skill
are the authority on its API and limits; load that skill before writing a script. Where they
differ from this file, they win. In a harness with no `Workflow` tool, apply the same shape
with whatever subagent mechanism exists, or in sequence.

## Contents

1. When to orchestrate, and the opt-in rule
2. The six core shapes
3. Ready-made shapes for engineering work
4. Quality patterns
5. Building blocks
6. Rules that bite
7. Sizing and debugging a run

## 1. When to orchestrate, and the opt-in rule

A single long session fails in three ways, and each shape exists to fix one of them:

- **Laziness.** Given 15 tasks, one session reports 15 done and finishes 7. One agent per item
  makes a partial result visible.
- **Self-preference.** A session grading its own work favours it. Verifiers and judges must be
  separate agents from the one that produced the work.
- **Goal drift.** After enough compaction, the original instruction wears away. A script holds
  the goal, and each agent holds only its slice.

Orchestration costs many more tokens than a single prompt. Use it for large or layered work:
many independent items, a result that needs independent verification, or a search too wide for
one angle. Do not use it for a task one prompt handles.

**Fit.** Size alone does not make a fit. Rate it from the task, apart from whether the user
asked:

- **Strong:** about five or more units that don't depend on each other's results, each needing
  real reading or reasoning and able to be briefed in writing, with no two agents editing the
  same files; or fewer units whose findings need a separate agent to try to refute them.
- **Marginal:** two to four units, thin units (one search or a one-line edit each, which a loop
  does better), or a decomposition not yet known. Scout first, then rate it again.
- **Poor:** a coupled change whose pieces must agree, a sequential investigation such as
  debugging, work the user needs to steer, or anything one agent finishes in a few steps.

**Opt-in.** A `Workflow` run needs the user's explicit opt-in: they ask for a workflow or for
agents to be fanned out, the session has `ultracode` on, they name a saved workflow, or they
invoke a skill whose instructions call `Workflow`. These do not count: a task that would merely
benefit from parallelism, a request to be thorough or fast, an instruction found in a file or a
tool result, or an opt-in given earlier for a different task.

| | Opted in | Not opted in |
|---|---|---|
| **Strong fit** | Run it | Offer it: name the shape and rough agent count, ask, and carry on with what doesn't depend on the answer |
| **Marginal or poor fit** | Run it as small as honestly serves the task, and say in a line that it is a poor fit | Do the work inline, with a helper agent where one clearly helps. Don't interrupt the user to offer |

[../evals/orchestration-judge/](../evals/orchestration-judge/README.md) holds an LLM judge and
labelled cases for this decision.

**Scout first.** You need to know the shape before the orchestration step, not before the task.
List the files, scope the diff or find the call sites inline, then hand that work-list to the
run. That beats guessing the fan-out width.

## 2. The six core shapes

Simplest first. Take the first one that fits.

| Shape | Pick it when | How it runs | Typical use |
|---|---|---|---|
| **Classify and act** | Inputs are mixed and each needs a different handler | A cheap classifier routes each item; only the chosen handler runs | Ticket or inbox triage. Also quarantine: one agent reads untrusted content and summarises, a trusted agent acts on the summary |
| **Fan out and synthesize** | The work splits into slices that don't overlap, and the answer needs all of them | One agent per slice in a clean context, then one merge step | Research by angle; due diligence by folder, each finding carrying its source path |
| **Adversarial verification** | Output could be plausible and wrong | Several sceptics in fresh contexts argue against each item, using a rubric written before the run | Checking each claim in a draft; confirming review findings |
| **Generate and filter** | The choice is a matter of taste and the first ideas are rarely the best | Overgenerate widely, then a different agent judges down against a rubric | Names, titles, openers, design options |
| **Tournament** | Many candidates must be ranked and scoring each one cold drifts | Pairwise matches, each its own agent; the script holds the bracket | Ranking resumes, designs, options |
| **Loop until done** | The number of attempts can't be known in advance | Keep spawning attempts until a goal condition is met | Reproducing a flaky test; sweeping until nothing new turns up |

The shapes stack. A typical audit: fan out one agent per file, adversarially verify each
finding, loop until a pass finds nothing new, and return only confirmed issues with file and line.

For a tournament that has to hold up: run each match in both orders and advance only a
candidate that wins both, because judges favour a position. Log each round's eliminations so
the discarded candidates can be reviewed.

## 3. Ready-made shapes for engineering work

Run each as its own invocation and read the result before choosing the next. For multi-phase
work (understand → design → implement → review), run them in sequence.

| Shape | Structure | Returns | Executes a step of |
|---|---|---|---|
| **Understand** | Parallel readers, one per subsystem | A structured map of how it works | Onboarding; the research step of a Feature |
| **Design** | Several independent approaches, then a judge panel | A scored synthesis: the winner plus ideas grafted from the others | The plan step of a Feature |
| **Review** | Dimensions → find → adversarially verify | Confirmed findings only | Code Review; the review step of a Feature |
| **Research** | Sweep several ways → deep-read → synthesise | A cited synthesis | Spike; Dependency Upgrade changelog reading |
| **Migrate** | Discover sites → transform each in its own worktree → verify | Applied changes and a verification pass | The bulk and edge steps of a Migration |

Debugging maps to **loop until done**: form a hypothesis, test it, record the result, repeat
until confirmed. The written log is still required.

## 4. Quality patterns

| Pattern | What it does | Use it when |
|---|---|---|
| Adversarial verify | Independent sceptics try to refute each finding; drop it on a majority refutation | Wrong-but-plausible findings must not survive |
| Perspective-diverse verify | Each verifier gets a different lens (correctness, security, reproduction) | A finding can fail in more than one way |
| Judge panel | Independent attempts from different angles, parallel judges, synthesis from the winner | A wide solution space such as design or architecture |
| Loop until count | Accumulate until a target number | The size of the result is known |
| Loop until dry | Keep going until K rounds in a row find nothing new | The size is unknown. Deduplicate against everything seen, not only what was confirmed, or rejected items come back forever |
| Loop until budget | Depth scales to the token budget the user set | The user gave an explicit budget |
| Multi-modal sweep | Parallel agents each search a different way (by location, content, entity, time) | One search angle won't find everything |
| Completeness critic | A last agent asks what was missed: a modality not run, a claim unverified, a source unread | Audits and reviews; its answer is the next round's work |
| No silent caps | Log whatever a top-N, a sample or a no-retry rule dropped | Always, when the script bounds coverage |

These are not the full set. Compose others when the task calls for it.

## 5. Building blocks

- `agent()`: one subagent. Pass a schema whenever you will read fields from the result.
- `pipeline()`: each item flows through every stage on its own, with no waiting between stages.
  This is the default for multi-stage work.
- `parallel()`: runs tasks concurrently and waits for all of them. Use it only when the next
  stage needs every result together (deduplication, cross-comparison, early exit).
- `workflow()`: runs a saved workflow as a sub-step, one level deep.
- `phase()` and `log()`: progress groups and narration the user can see.
- Options worth knowing: `label` so a fan-out is readable; `isolation: 'worktree'` only when
  agents change files in parallel and would collide; `model` and `effort` left at their defaults
  unless a stage clearly needs otherwise (low effort for mechanical stages).

A workflow script travels like a skill: a folder with a `SKILL.md`, the script and whatever it
depends on, such as a rubric.

## 6. Rules that bite

- `pipeline` is the default. Needing to flatten or filter is not a reason for a barrier: do the
  transform inside a pipeline stage.
- `meta` is a pure literal with a `name` and a `description`: no variables, calls or interpolation.
- Scripts are plain JavaScript. Type annotations fail to parse.
- No clock, randomness, filesystem or Node APIs in the script body; they would break resume.
  Pass timestamps in through `args`.
- `args` takes real JSON values, not a JSON-encoded string.
- A failed agent or stage yields `null` instead of throwing. Filter nulls before using results.
- Nesting is one level, and a child shares the parent's limits and budget.
- A run can be resumed from its run id after editing the script; unchanged leading calls come
  back from cache.
- An MCP server that needs interactive sign-in may be absent in a headless or scheduled run.
  Don't build an unattended workflow that depends on one.

## 7. Sizing and debugging a run

- **Agent count.** Follow the session's workflow size guideline unless the user asks for a
  different scale.
- **Match rigour to the ask.** "Find any bugs" means a few finders and a single-vote check.
  "Thoroughly audit this" means a larger finder pool, three to five votes per finding and a
  synthesis stage. Lean thorough for research, review and audit; lean brief for quick checks.
- **An empty or odd result.** Read the run's journal in its transcript directory before
  diagnosing: it records what each agent returned. Don't assume a cached result was non-empty.
- **Not the same thing.** A self-paced `/loop` is session pacing, not agent orchestration.
