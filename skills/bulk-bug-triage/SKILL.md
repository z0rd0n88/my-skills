---
name: bulk-bug-triage
description: Review an open-bug backlog against current code and publish verified, evidence-backed dispositions to GitHub. Use for "triage the bug backlog", "review all open bugs", or "which issues are real".
---

# bulk-bug-triage

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Reviews every open issue carrying a chosen label against the current code, then
publishes one evidence-backed comment per issue, fixes labels, and closes what is
demonstrably done. Publication is idempotent and independently verified.

| Option | Where | Values | Default | Effect |
|---|---|---|---|---|
| `label` | config | any repo label | `bug` | Which backlog to review |
| `branch` | config | any branch name | `main` | Branch the pinned `sha` must still point at |
| `--config PATH` | flag | a path | `triage.config.json` | Which config to read |
| `--batch-size N` | flag | 1–50 | 24 | Issues per GraphQL call during verify |

Related: `drift-status-check` compares a roadmap against reality; this one
compares an issue backlog against reality.

---

Current code is the authority on whether a bug is still real. History and old
session logs explain where an issue came from — they never decide whether to
close it.

## Phases

**1. Inventory.** Pin the commit you will review against (`git ls-remote origin
refs/heads/<branch>`, `main` unless `config.branch` says otherwise). List every
open issue with the label, **capturing each one's number and title** — `publish`
refuses a row whose live title has changed, so a manifest without titles fails
preflight. Record the moment you took the inventory — it becomes
`inventoryCutoff`, and anything edited after it gets re-read before publication.

**2. Investigate.** Split the issues into disjoint sets across parallel
subagents. Each returns one JSON record per issue, carrying the title from the
inventory unchanged. Expand beyond the labelled
set when the inventory shows obvious defect reports that were never labelled.

**3. Reconcile.** Merge the records into `triage-decisions.json`. Resolve
disagreements by reading the code yourself. Never close on a subagent's word
alone.

**4. Publish.** `preflight`, then `publish`. Both refuse to run if the pinned
branch has moved off the pinned commit.

**5. Verify.** `verify` re-reads every issue from GitHub and compares it against
the manifest. Report what it prints, not what you intended.

## Decision record

One object per issue in `triage-decisions.json`:

```json
{
  "number": 63,
  "title": "Order journey doc claims a COMPLETE state the code lacks",
  "status": "valid",
  "system": "Merchant / order lifecycle",
  "labels": ["bug", "merchant", "ready-for-agent"],
  "removeLabels": ["question"],
  "reason": "Prose still defines a COMPLETE state the code does not have.",
  "evidence": [{"path": "src/OrderState.kt", "line": 23, "end": 32}],
  "history": "Filed during the June migration.",
  "nextStep": "Reword the journey doc to match OrderState.",
  "closureReason": null
}
```

`status` is one of `valid`, `partial`, `fixed`, `obsolete`, `superseded`.
`closureReason` is `completed` or `not_planned` on `fixed`, `obsolete` and
`superseded`, and absent on `valid` and `partial` — preflight rejects any other
pairing, because the comment text comes from `status` and the close comes from
`closureReason`. Every retained issue needs exactly one triage label; closed
issues get theirs stripped. `evidence` is required and must cite the pinned
commit — it renders as permalinks. `title` is the issue's title as read at
inventory: `publish` refuses the row if the live title differs, or if the number
turns out to be a pull request.

## Running it

```bash
# Run from the checkout you are triaging, never from inside the skill dir:
# `npx skills update` replaces it mid-review.
cp "$HOME/.agents/skills/bulk-bug-triage/triage.config.example.json" triage.config.json   # then edit
python3 "$HOME/.agents/skills/bulk-bug-triage/scripts/triage.py" preflight --config triage.config.json
python3 "$HOME/.agents/skills/bulk-bug-triage/scripts/triage.py" publish   --config triage.config.json
python3 "$HOME/.agents/skills/bulk-bug-triage/scripts/triage.py" verify    --config triage.config.json
```

`triage-decisions.json` resolves beside the config file, so both live in that
working directory — not in the plugin.

`preflight` mutates nothing. It fails if the pinned branch moved, a label does
not exist in the repo, a record lacks a title, evidence or a triage label, an
evidence path is absent from the pinned tree, or an open labelled issue is
missing from the manifest. `publish` re-runs it before touching anything.

Self-check: `python3 "$HOME/.agents/skills/bulk-bug-triage/scripts/test_triage.py"`.

## What protects you

**Re-running is safe.** Each comment carries a `<!-- bug-triage:SHA -->` marker
keyed on the pinned commit alone, so editing `date` cannot hide it. An issue
already carrying it is skipped when the body matches and aborts the run when it
does not, so an interrupted run resumes by simply running `publish` again and
never double-posts. A guard that fires stops the whole run: fix the issue it
names, then re-run — rows already published are skipped.

**Concurrent edits abort.** Each issue is fingerprinted before and after the
comment posts. If it changed in between, the run stops — the comment is posted
but labels and state are not, and the message says so.

**Edits after inventory abort.** An issue touched after `inventoryCutoff` stops
the run. Re-read it, then add `"number": "<its updated_at>"` to
`config.rereviewed` to continue. Do not widen the cutoff to silence this.
`inventoryCutoff` is required and must carry a UTC offset (`...Z` or `+02:00`);
local time without one is rejected rather than quietly compared as text. Any
activity counts — a bot comment or a CI reply trips it too — so on a busy
tracker expect one `rereviewed` entry per touched issue.

**Coverage is enforced.** Both `preflight` and `verify` fail if any labelled
issue that was open at `inventoryCutoff` is missing from the manifest, so the
backlog cannot be half-reviewed. Issues filed after the inventory are out of
scope and do not wedge the run.

## Rules

- No source edits, no deployments, no issue-body rewrites. Comments, labels, and
  state only.
- Never close an issue you are not certain about. Downgrade it to `partial` and
  keep it open.
- Missing wiring is not removal — an unreferenced implementation is still a bug.
- A cited test is source evidence, not a passing run. Say "the test asserts X"
  unless you actually ran it.
- Never paste session transcripts or secrets into a GitHub comment.
