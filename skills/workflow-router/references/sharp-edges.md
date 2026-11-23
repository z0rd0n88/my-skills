# Sharp edges and review checks

The failure modes behind the reliability checks in [durable-workflows.md](durable-workflows.md),
each as symptom, cause and fix, followed by a checklist for reviewing workflow code. Engine specifics here are pointers: confirm them
against the docs for the SDK version the project has installed.

## Contents

1. Non-idempotent steps (critical)
2. Side effects outside steps (critical)
3. No timeouts (high)
4. Long runs without checkpoints (high)
5. Large data in workflow state (high)
6. No failure handler (high)
7. Retries without backoff (medium)
8. Long Temporal activities without heartbeat (medium)
9. n8n workflow without an Error Trigger (medium)
10. Review checklist

## 1. Non-idempotent steps — critical

**Symptom:** a customer charged twice, an email sent three times, duplicate rows.

**Cause:** a completed step normally replays its recorded result, but a step whose side effect
succeeded just before its completion was recorded will run again. The external service cannot
tell that the second call is a retry.

**Fix:** give every external write a key built from stable inputs, never from a random value or
the clock, and pass it to the provider.

- Payments: the provider's idempotency key, e.g. `order-<orderId>-payment`.
- Database: an upsert or `INSERT … ON CONFLICT (id) DO NOTHING` on a deterministic id.
- Email and messages: a check-then-send still races. Use a transactional outbox with a unique
  key, plus the provider's own deduplication where it has one.
- When a call's outcome is unknown (timeout after send), reconcile with the provider before
  retrying.

## 2. Side effects outside steps — critical

**Symptom:** non-determinism errors, "workflow corrupted", a replay that behaves differently
from the first run.

**Cause:** workflow code outside steps runs again on every replay. A random id or a clock read
there yields a new value each time, so the replay no longer matches recorded history.

**Fix:** generate ids, read the time and do all I/O inside a step or activity, so the value is
recorded once. Reading arguments and pure calculation are safe in workflow code. Semantics
differ by SDK: Temporal's TypeScript sandbox makes `Date.now()` deterministic, and other SDKs
offer a replay-safe side-effect API. Use what the installed SDK documents; don't carry an API
across languages.

## 3. No timeouts — high

**Symptom:** workflows that hang forever, an exhausted worker pool, runs that must be killed by
hand.

**Cause:** an external API can hang indefinitely, and most engines put no default timeout on an
activity.

**Fix:** set a timeout on every activity and every outbound call, and keep it shorter than the
workflow's own timeout.

- Temporal: `startToCloseTimeout` always; `scheduleToCloseTimeout` and `heartbeatTimeout` as needed.
- Inngest: a timeout on the request inside the step (`AbortSignal.timeout`), and treat a non-2xx
  response as an error.
- Step Functions: `TimeoutSeconds`, and `HeartbeatSeconds` for long tasks.
- n8n: node timeout and workflow timeout settings.

## 4. Long runs without checkpoints — high

**Symptom:** growing memory, worker timeouts, hours of progress lost on a crash, "maximum
duration exceeded".

**Cause:** progress is saved only at step boundaries. One step that loops over a thousand items
is one checkpoint.

**Fix:** one step per item or per small batch, each with a stable name such as
`process-<itemId>`. Use the engine's durable sleep for waits; it holds no worker while it waits.
Hand large batches to a child workflow.

## 5. Large data in workflow state — high

**Symptom:** slow runs and replays, memory errors, "payload too large", storage bills.

**Cause:** every step's return value is persisted and deserialised on replay. Some engines cap
it outright (Step Functions: 256 KB).

**Fix:** write the data to object storage or a database inside the step and return only the key.
The next step loads it by key.

## 6. No failure handler — high

**Symptom:** failed runs vanish, nobody is alerted, the customer finds out first, and there is
nothing to recover from.

**Cause:** retries run out eventually, and by default most engines only mark the run as failed.

**Fix:** every production workflow has a path for exhausted runs that does three things:
records the error (redacted), alerts a person, and stores the failed job where a recovery
process can pick it up.

- Inngest: an `onFailure` handler on the function.
- n8n: an Error Trigger workflow (see 9).
- Temporal: handle the workflow failure where it is started or awaited, or signal a
  compensating workflow.
- Step Functions: `Catch` on the state, routing to a failure state or queue.

## 7. Retries without backoff — medium

**Symptom:** retry storms, rate limiting, a struggling dependency pushed over, your client
blocked.

**Cause:** immediate retries from many runs arrive together at a service that is already
failing.

**Fix:** exponential backoff with a cap and jitter, a bounded number of attempts, and a list of
errors that must not be retried (validation failures, a declined card). Temporal: `initialInterval`,
`backoffCoefficient`, `maximumInterval`, `maximumAttempts`, `nonRetryableErrorTypes`. Inngest
backs off by default; throw its non-retriable error for permanent failures.

## 8. Long Temporal activities without heartbeat — medium

**Symptom:** an activity times out while it is still working, work is lost when a worker
restarts, and cancellation does nothing.

**Cause:** without heartbeats the server cannot tell a busy activity from a dead one.

**Fix:** for any activity longer than about ten seconds, heartbeat with progress details, set
`heartbeatTimeout`, honour cancellation, and resume from the last heartbeat's details.

## 9. n8n workflow without an Error Trigger — medium

**Symptom:** a production workflow fails and the only record is the execution log in the UI.

**Cause:** n8n does not notify anyone on failure by default.

**Fix:** an Error Trigger workflow that extracts the error details, logs them to an error
service, alerts the team, and stores the failed job for a separate recovery workflow. Also turn
on per-node retry for retryable failures only, and set node and workflow timeouts.

## 10. Review checklist

Run this over workflow code before calling it done.

| Level | Check |
|---|---|
| Error | A payment or other money call without an idempotency key |
| Error | A Temporal `proxyActivities` call without `startToCloseTimeout` |
| Error | Uncontrolled randomness in workflow code outside a step or the SDK's replay-safe API |
| Error | A clock read in workflow code on an SDK that does not virtualise it |
| Warning | An email or message send with no deduplication |
| Warning | An external API call inside a step with no timeout |
| Warning | A production function with no failure handler |
| Warning | Retries configured without backoff |
| Warning | A step that does not distinguish retryable from permanent errors |
| Info | A step returning data that could be large; return a reference instead |
