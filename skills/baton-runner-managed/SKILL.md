---
name: baton-runner-managed
description: Use when driving a multi-phase build on a machine where subagents cannot run Workflow or a 10+ minute gate — the manager session owns the dw-review fan-out, the finding-fixer pass and the full gate. User-invoked.
---

# baton-runner-managed

A fork of [`baton-runner`](../baton-runner/SKILL.md) with one structural change:
**the steps a subagent cannot run — the `dw-review` fan-out, the `finding-fixer`
pass and the full gate — run in the manager session.** Golden rules, budgets,
pause/resume, STATE/log mechanics, and the containment and return contracts are
carried over unchanged.

You (the session running this skill) are the **manager**: a thin, restartable
scheduler. You never write product code, and you never open diffs, batons, or
gate logs. You spawn **units** (subagents), thread file *paths* between them,
commit, open a draft PR per phase, enforce budgets, log, and pause. All state
lives on disk (`baton-runner/<run-id>/`) so a fresh manager session resumes from
`STATE.md` indistinguishably.

> Correctness over speed — say that in every unit prompt; a session cannot set
> its own or a subagent's reasoning effort. Detail lives in
> [REFERENCE.md](REFERENCE.md); this file is the control flow.

## Use this instead of `baton-runner` when

Either of these holds on this machine — both did for the `maker-lab-3-5` run
(#615, #618, #619):

- **`Workflow` is blocked inside subagents** by the user-scope
  `nested-fanout-guard` hook, so a unit can run neither `ClaudesMods:dw-review`
  nor `ClaudesMods:finding-fixer` — both are Workflow skills.
- **The phase-closing gate outlasts a subagent.** `GATE_PROFILE=full
  scripts/gate.sh` runs 10–20 minutes; a subagent's foreground Bash caps at
  600 s, and its backgrounded task is killed the moment the unit returns
  (observed: `[killed]`, no verdict).

If neither holds, use `baton-runner` — it spends fewer units per phase.

## Golden rules

1. **Model is a run parameter**, not a constant. Default `opus`; the user may
   override per run (this shape was proven on `fable`). Record it as `model:` in
   `STATE.md` and use the same value for every `Agent` spawn *and* every
   `agent()` call in the review Workflow. Never mix models within a run.
2. **Manager stays lean, with three named exceptions.** Read only each unit's
   short return block (`STATUS`/`VERDICT`/`BATON`/`NOTES`); move *paths*, never
   contents. The three steps the manager now owns are the exceptions:
   - the `dw-review` Workflow's **structured result** — persist the whole JSON
     to `baton-runner/<run-id>/review-phase-<N>-dw.json` and read only the
     extractor's summary (verdict, per-lens counts, confirmed findings as
     `F<n> [SEVERITY] BEFORE-MERGE title (location)`, refuted titles, wrong
     claims, the residual-risk count and the grouping hint);
   - the `finding-fixer` Workflow's **per-finding verdict lines**
     (`F<n>=<verdict>`), the script's `INCOMPLETE:` and `Discarded edits from`
     log lines, and the writer's `applied` / `skipped` ids — never the
     adjudicators' evidence or their proposed edits, which stay in the JSON;
   - the full gate's **`GATE:` verdict line and exit code** — never the gate
     logs, which stay on disk for the closing unit.

   Nothing else — in particular the manager never reads a finding's body. Both
   Workflows are handed *pointers* into the persisted JSON and their own agents
   read it. The `NOTES` line is also manager input, not file contents, so
   comparing NOTES across returns is allowed (see "No progress").
3. **Manager does all git/remote; units never do.**
4. **Verification is delegated** — "done" is the unit's `STATUS`, the closing
   unit's `VERDICT`, and the three objective signals in rule 2. Never your own
   reading of the code.
5. **Context crosses agents only through files** — batons, phase-exit digests,
   the persisted review JSON.
6. **Stop, don't guess** — user input needed, budget ceiling, or fatal error →
   PAUSE (write STATE, show the user, stop).

## Roles

| Term | Meaning |
|---|---|
| **work-unit** | Implements a phase's acceptance criteria via `superpowers:test-driven-development`, recording the actual RED output as evidence. |
| **review-unit** | Independent of the implementer. Runs `GATE_PROFILE=fast scripts/gate.sh` in the **foreground** and verifies each criterion + the RED evidence against the diff. Runs **no** fan-out review and **no** `Workflow`. Emits `VERDICT: GATE-OK \| ISSUES`. |
| **dw-review** | The manager's own `Workflow` run of `ClaudesMods:dw-review` — three lanes picked from the diff plus a `critical-thinking` skeptic. A repo-tuned `<repo>-dw-review` variant wins when the worktree has one. Counts as one unit. |
| **finding-fixer** | The manager's own `Workflow` run of `ClaudesMods:finding-fixer` — read-only adjudicators rule each CONFIRMED finding against the sources that decide it, then one writer applies only what survives. One round, no re-review. Counts as one unit. |
| **fix-unit** | A subagent, used **only** for fast-gate and full-gate failures — never for review findings, which go through `finding-fixer`. |
| **closing-unit** | Told the full gate already passed and must not re-run it. Re-verifies each criterion after the fixes, writes the durable review record from the two persisted JSONs, writes the phase-exit digest. Emits `VERDICT: CLEAN \| ISSUES`. |
| **baton / digest** | `baton-pass` file carrying unit state (updated incrementally) / terse map of public surface + conventions threaded to later phases. |

## Pre-flight — before work unit 1

- [ ] **`scripts/gate.sh` present on `origin/main`.** Absent → stop and tell the
      user to merge the PR that introduces it first.
- [ ] **Fresh single worktree**; confirm `baton-pass`,
      `superpowers:test-driven-development`, `ClaudesMods:dw-review` and
      `ClaudesMods:finding-fixer` resolve there.
      **There is no skill named `tdd`**, and do not substitute the project's
      `kotlin-testing` skill — it teaches Kotest/MockK and this repo tests with
      `kotlin.test` (`@Test`, `assertEquals`, backtick names).
- [ ] **Run id matches `^[a-z0-9][a-z0-9-]*$`.** It is interpolated into shell
      commands the manager runs; a space or quote in it reaches command position.
- [ ] **Gradle wrapper.** Create `<scratch>/gw.sh` with the **Write tool, never
      Bash** — any Bash command whose *text* contains `./gradlew` is intercepted
      by the context-mode hook and never runs, including the heredoc that would
      write the wrapper. Pass its absolute path in every unit prompt
      (REFERENCE → "Repo gotchas block").
- [ ] **Docker up** — `docker info` green before unit 1; the full gate needs it.
      Docker Desktop stopped → launch it as a **backgrounded** Bash call (the
      interop launcher blocks) and poll `docker info`.
- [ ] **Parse + right-size** the phase list (≤ ~5 acceptance criteria / ~10 files
      each; split larger into ordered sub-units).
- [ ] **Spec readiness** per phase → `READY` / `THIN` / `BLOCKED` (draft proposed
      criteria for `THIN`; never invent silently).
- [ ] **Work-unit agent (optional)** — default `general-purpose`; any nominee
      must hold file edits + Bash + the `Skill` tool. Review, fix and closing
      units stay `general-purpose`.
- [ ] **House rules** — draft the `houseRules` block `finding-fixer` requires
      (the repo `AGENTS.md`, its ADRs, the numeric and safety invariants) once
      for the whole run, and save it to `baton-runner/<run-id>/house-rules.md`.
      The Workflow refuses to start without it, and it is the only thing
      stopping a writer from "improving" a deliberate constraint.
- [ ] **Review policy** — default **one round** (below). Offer `max 3` as the
      opt-in and record whichever is chosen in `STATE.md`.
- [ ] **Model** — confirm the run model; record it in `STATE.md`.
- [ ] **Open questions + signoff** — surface ambiguities, proposed criteria, the
      agent and the model. **Do not spawn work unit 1 until the user signs off.**
- [ ] **Init** `baton-runner/<run-id>/` (`STATE.md` + `log.md` with budgets).
      TodoWrite: one todo per phase.

## Per-phase loop

For each phase in order, on branch `feat/<run-id>/phase-N`, with fresh context
(this phase's spec + the accumulated phase-exit digests only). Steps the
**manager** performs are marked M.

1. **WORK unit.** `INCOMPLETE` → spawn a continuation seeded only with its baton
   path, until `COMPLETE`. `NEEDS_USER`/`FATAL` → PAUSE.
2. **M — commit.** Explicit `git add` of the paths the unit listed. Run-state
   files need `git add -f` (REFERENCE → "Audit trail"). Transient red is fine.
3. **REVIEW unit (fast gate + criteria).** Foreground
   `GATE_PROFILE=fast scripts/gate.sh baton-runner/<run-id>/gate-phase-<N>-iter-<k>/`.
   Exit 2 / `GATE: PARTIAL profile=fast` is the **good** outcome here — `fast`
   can never exit 0. Exit 1 → `VERDICT: ISSUES`.
   `ISSUES` → fix unit scoped to the gate failures → commit → re-spawn the
   review unit. That loop is bounded by the per-phase thrash alarm, not by the
   review-round policy; it did not fire on the reference run.
4. **M — clean the tree.** `dw-review` reviews **committed work
   only**; `git status --porcelain` must be empty before step 5 (the review
   baton sits in gitignored `baton-pass/`, so it never shows there).
5. **M — run `dw-review` yourself** via the `Workflow` tool. Three lanes
   chosen from the diff + the `critical-thinking` skeptic; `model` = the run
   model and `effort: 'high'` on **every** `agent()` call. Diff three-dot
   against **the phase base branch**, which is stacked: phase 2 diffs against
   phase 1, not `origin/main`. Persist the whole result to
   `baton-runner/<run-id>/review-phase-<N>-dw.json` and print only the
   extractor's summary — the extractor stamps `F1..Fn` on the confirmed
   findings, and those ids are how step 6 addresses them. Template + extractor:
   REFERENCE → "The dw-review Workflow".
   Skeptic verdict `BLOCK` → PAUSE.
6. **M — run `finding-fixer` yourself** via the `Workflow` tool, over **every**
   CONFIRMED finding. Group the `F<n>` ids by the path prefix in their
   `location` (2–4 groups); each group's `findings` is a *pointer* — the ids
   plus the path to the persisted review JSON — so the adjudicators read the
   bodies and you never do. `verify` is the fast gate. `houseRules` is the
   pre-flight block **plus any judgement call you have already decided** (the
   reference run chose allowlist over denylist for an environment fix), stated
   as decided so no adjudicator re-opens it. Persist the result to
   `baton-runner/<run-id>/fixer-phase-<N>.json`. Skip `finding-fixer`'s own
   Step 4: reading the diff is not yours — step 8's full gate and step 9's
   closing unit are that check. Args + grouping: REFERENCE → "The finding-fixer
   Workflow".
   A **before-merge** finding that ends `unresolved`,
   `real-but-decided-elsewhere`, or in the writer's `skipped` list → PAUSE.
7. **M — commit the fix.**
8. **M — run the full gate** as your own `run_in_background: true` Bash with
   `timeout: 600000`, and read **only** the `GATE:` line and the exit code
   (REFERENCE → "The full gate"). Non-zero → fix unit → commit → re-run the
   gate, bounded by the thrash alarm.
9. **CLOSING unit.** Told the gate already passed at this HEAD and that it must
   **not** re-run it. Re-verifies each criterion after the fixes, **writes** the
   durable review record `docs/reviews/YYYY-MM-DD-dw-review-<slug>.md` from the
   review JSON + the fixer JSON — the exact sha named, every confirmed finding
   dispositioned — then writes `baton-runner/<run-id>/digest-phase-<N>.md`
   (≤40 lines) and a closing baton. `VERDICT: ISSUES` → PAUSE. Its NOTES carries
   `dispositions=<n>`; that number ≠ the extractor's `confirmed:` count → PAUSE,
   since the unit's own completeness clause is the author checking itself.
10. **M — close the phase.** Commit the closing artifacts, push, open the draft
    PR stacked on the previous phase branch, then fold the `STATE.md`/`log.md`
    updates into a final commit and push. Progress line, update `STATE.md`, cut
    `feat/<run-id>/phase-(N+1)` from this tip, advance.

Clean-path budget: **3 Agent spawns + 2 Workflows per phase** (5 units) — work,
review, closing, plus the two Workflow steps. A work continuation or a
gate-failure fix unit adds one each. The reference run spent 16 units on 3
phases against a 75 ceiling, on the older shape that fixed findings in a unit.

When all phases are `CLEAN` + PR'd: set `STATE = DONE` and summarize (draft PRs,
stacked-merge order, any waivers).

### CLEAN

`CLEAN` iff **both**:

- the **full** gate exits 0 (`GATE: PASS profile=full`) at the phase HEAD, and
- the skeptic verdict is `APPROVE` or `MERGE-WITH-FIXES` **and every
  before-merge item is closed** — applied by the fixer's writer, or ruled
  `refuted` / `already-handled` by an adjudicator. The evidence check is the
  closing unit's record, which quotes that adjudicator verbatim; the manager
  never reads it.

`BLOCK`, a before-merge item left `unresolved` / `real-but-decided-elsewhere` /
`skipped`, or a closing `VERDICT: ISSUES` → PAUSE. Never waive on your own;
waiving is the user's call at the pause. An adjudicator overturning a finding —
before-merge or not — is the workflow working: log it, carry on, and the
closing unit records it in the review record.

### Review policy: one round by default

Put every CONFIRMED finding through a single `finding-fixer` run and do **not**
re-review.
Rounds do not converge — measured across 10 real loop runs, ~0% of findings
carry from one round to the next while 22–56% of the *files* overlap, so an
extra round buys fresh noise rather than closure. `max 3` review rounds stays
available as an explicit opt-in, recorded in `STATE.md`.

### Detecting "no progress" without reading the baton

Every unit embeds a numeric progress token in `NOTES` (e.g. `progress=criteria
2/5; files 4`). Compare NOTES across consecutive `INCOMPLETE` returns from the
same phase:

- unchanged across 3 consecutive `INCOMPLETE` returns → fatal, PAUSE with a
  failure baton;
- changed → spawn a continuation from the latest baton path.

## Spawning, budgets, pause

- **Spawn:** `subagent_type: general-purpose` (work units may use the phase's
  nominated agent), `model:` = the run model, `run_in_background: false`. Build
  prompts from the REFERENCE templates — always the spec/baton path, the
  worktree path, the **repo gotchas block**, the containment and return
  contracts, "correctness over speed", "return synchronously — never background
  a task, it is killed when you return", and the bail budget (≈50 tool calls /
  ≈10 files). Record the returned baton path in STATE first.
- **Budgets:** a progress line after every unit; global ceiling **75** units
  (pause → reauthorize); per-phase thrash alarm **20**. Each Workflow run counts
  as one unit. Tunable in STATE.
- **Containment:** units write only inside the worktree, never mutate
  git/remote, and declare rather than silently add dependencies. Out of bounds →
  PAUSE.
- **Pause/resume:** on any pause write `STATE = PAUSED` with the exact resume
  point and stop; re-invoking the skill reads `STATE.md` and continues. Never
  restart completed phases.
- **No `SendMessage` fallback.** If a unit returns early and cannot be
  continued, spawn a fresh unit seeded from its baton — do not assume the
  stopped agent is reachable.

## References

[REFERENCE.md](REFERENCE.md) — state schema, prompt templates, the repo gotchas
block, the dw-review Workflow template and JSON extractor, the finding-fixer
args, gate mechanics, branch/PR mechanics, the review record, audit trail,
budgets, failure handling.
Depends on `baton-pass`, `superpowers:test-driven-development`,
`ClaudesMods:dw-review` and `ClaudesMods:finding-fixer`.
