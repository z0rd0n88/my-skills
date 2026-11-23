# Durable lane: workflow design for application code

How to route a multi-step process in a product onto a workflow engine: whether it needs one,
what starts it, how its steps relate, which engine, and which reliability checks apply.
"Durable" means the engine checkpoints each step, retries failures and resumes after a crash.

## Contents

1. Does it need a workflow engine at all?
2. Route on three axes: trigger, shape, reliability
3. Platform
4. Reliability checks
5. Route card
6. Examples

**The project's own framework wins.** Look for one before choosing anything: a workflow SDK in
the lockfile (`@temporalio/*`, `inngest`, `@outputai/*`), Step Functions state machine
definitions, n8n workflow exports, or a plugin that claims workflow creation (Output.ai's
`output-plan-workflow`, for example). When one exists, use it and its skills, skip section 3,
and still do sections 1, 2 and 4.

## 1. Does it need a workflow engine at all?

Start simple; add an engine only when reliability demands it. One is warranted when at least
one of these holds:

- Money or other state that must never be lost or applied twice when something fails half-way.
- Two or more external side effects, where a failure between them leaves things inconsistent.
- A wait longer than a request or a process lives: hours, days, a human approval.
- Work that has to survive a deploy, a crash or a worker restart.
- A recurring job whose failures someone must hear about.
- A long loop over many items where losing progress is expensive.

Signs in existing code that it would be improved by one: a hand-written retry loop around an API
call; `setTimeout` or `sleep` standing in for a delay of hours; a cron script with no failure
alert; a webhook handler that does the heavy work before it answers; a status column plus a
polling job acting as a state machine; "resume from where it failed" done by hand.

If none apply, say **no workflow needed** and name the simpler thing: a plain function, one
idempotent job on the queue the project already has, or a single cron entry. Then stop. The
same goes for your own low-volume automations where a person sees the output: a scheduled
agent session is enough.

## 2. Route on three axes

The patterns are not six alternatives. Pick one trigger and one shape; the reliability layer is
always on.

**Trigger: what starts it?**

| It starts when | Trigger |
|---|---|
| Something happens: a user action, a webhook, another system's event | Event-driven |
| The clock says so: a daily report, a periodic sync, a batch window | Scheduled |
| A person or a caller asks for this one run | Direct start |

Prefer an event when either would work. A schedule that polls for changes is usually an event
trigger with extra delay.

**Shape: how do the steps relate?**

| Shape | Pick it when | Typical cases |
|---|---|---|
| Sequential | Each step needs the previous step's output, or order matters | Order → payment → shipment → confirmation; content pipelines |
| Parallel | Steps are independent and their results are combined at the end | Several analyses of one document; data from several sources |
| Orchestrator-worker | The subtasks are not known until the input is examined, or need different specialists | A planner that splits a request and dispatches to create, modify and delete workers |

Take the simplest shape that fits: sequential, then parallel, then orchestrator-worker. Shapes
nest, so a sequence with one fanned-out stage is still sequential with a parallel step. When an
LLM writes the orchestrator's plan, validate it against an allowlisted schema and a permission
and budget limit before dispatching anything.

**Reliability layer: retry and recovery.** Any step that touches something external gets
retries with backoff and a place for runs that exhaust them. Section 4 covers it.

## 3. Platform

Ask in this order and stop at the first match:

| Question | Platform | Cost of the choice |
|---|---|---|
| Will non-developers build and own it, or is it a quick prototype of integrations? | n8n | Visual and self-hostable; alerting on failure is not on by default |
| Is the stack AWS-native with Lambdas already written? | AWS Step Functions | JSON state definitions; 256 KB payload limit |
| Is the stack Azure, in .NET or TypeScript? | Azure Durable Functions | Checkpoint-and-replay rules apply to orchestrator code |
| Is it money, or correctness-critical across services? | Temporal | Strongest durability guarantees; steepest learning curve and its own cluster or cloud |
| Otherwise: event-driven, serverless, TypeScript, AI steps | Inngest | Runs on any hosting; least ceremony |

## 4. Reliability checks

Apply every line that fits the route. Symptoms, causes and fixes are in
[sharp-edges.md](sharp-edges.md); read it before writing or reviewing workflow code.

- **Critical: idempotent side effects.** Durable does not mean exactly-once. Each external write
  carries a key built from stable inputs (`order-<id>-payment`), passed to the provider.
- **Critical: nothing non-deterministic in replayed workflow code.** Random values, clock reads
  and I/O belong in steps or activities, or in the SDK's replay-safe API.
- **High: a timeout on every activity and external call**, shorter than the workflow's own.
- **High: many small steps, not one long one.** Durable sleep for waits; child workflows for batches.
- **High: references, not payloads, between steps.** Store large data and pass its key.
- **High: a failure path.** Runs that exhaust retries are logged, alerted on and stored for recovery.
- **Medium: exponential backoff** with a cap and jitter, and named non-retryable errors.
- **Medium: heartbeats** on long Temporal activities; **an Error Trigger** on every production n8n workflow.

Always, whatever the route: authenticate webhooks, deduplicate events, keep payloads and
credentials out of workflow history and logs, use test accounts for payments, and never send
real messages or create schedules without the user's go-ahead.

## 5. Route card

Give this card, one line per field, before writing code:

```
Workflow route (durable)
- Needed:    yes — <the section 1 reason>       (or: no — <the simpler thing>; stop here)
- Trigger:   event <name> | schedule <cron> | direct start
- Shape:     sequential | parallel | orchestrator-worker — <why>
- Platform:  <name> — <why, or "already in the repo">
- Steps:     1. <step> [side effect? key? timeout?]  2. …
- Failure:   <where exhausted runs go and who hears about it>
- Open:      <anything you could not determine>
```

Ask the user only when the route turns on something the repo cannot tell you, such as which
cloud they deploy to or whether real money moves. Otherwise state the route and proceed.

Write code against the installed SDK's version and its current docs, not from memory: workflow
SDK signatures change between major versions (Inngest's `createFunction`, Temporal's schedules),
and `addyosmani-source-driven-development` describes how to check.

## 6. Examples

| Situation | Route |
|---|---|
| Charge the card, create a shipment and email a confirmation when an order is placed | Event · sequential · Temporal (money), or the engine already in the repo · keys on charge, shipment and email |
| Run security, performance and compliance analysis on each uploaded document | Event · parallel, then one aggregate step · Inngest |
| Welcome email an hour after signup, a nudge after three days if inactive | Event · sequential with durable sleeps · Inngest |
| Every morning at 9, gather metrics and mail the report | Scheduled · sequential · n8n if ops owns it, otherwise the repo's engine · failure alert required |
| "Do whatever this free-text request needs" | Direct start or event · orchestrator-worker · plan validated before dispatch |
| Resize an image on upload | No workflow: one idempotent job on the existing queue |
