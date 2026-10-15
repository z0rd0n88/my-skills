---
name: drift-status-check
description: Use when asked for a project's status vs. its roadmap/spec/PRD, which specs are written but unbuilt, or whether a plan doc still matches reality — spans code, trackers, docs, and spec coverage. Not for single-file review or bug hunts.
---

# Drift Status Check

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Audits a project against its plan of record — a roadmap, PRD, spec, or epic —
and reports where code, PR/issue trackers, docs, and spec coverage have diverged
from it, including which specs are written but unbuilt and which features have no
spec at all. Use it for "what's the current status" or "does this doc still match
reality" questions, not for a single-file code review or a narrow bug investigation.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<target>` | repo or feature name | inferred from the request | What to audit against its plan of record |
| `--no-write` | flag | off — report is written to `.drift-status/<date>-<slug>.md` | Print the report only, skip persisting it to disk |

## Overview

Audits a software project against its plan of record and reports where they've
diverged: what's built, what's stalled, what the plan claims that reality
contradicts, and what reality has done that the plan doesn't know about yet.

Spec coverage is one of those dimensions, not a footnote: which specs the project has,
which of them are actually built, and which in-flight features have no spec at all.
Every count in that section is derived from — and printed alongside — the enumerated
list of instances behind it.

## When to Use

Trigger on requests to audit or summarize project state against a plan-of-record doc
(roadmap, PRD, spec, epic) — "what's the state of the project", "where do we stand vs
the roadmap", "does this doc still match reality". Don't use for a single-file code
review, a narrow bug investigation, or a request that already names its own output
shape (those have their own skills/commands).

## Tooling Choice — Read This Before Reaching for Anything Heavier

This task is **fan-out gathering + single-context cross-referencing**, not independent
parallel analysis. Match tools accordingly:

| Don't reach for | Why not |
|---|---|
| A subagent dispatch (Explore, general-purpose, etc.) | Adds a summarization layer between you and primary sources. The report's value is citing exact PR numbers / line numbers / commit SHAs, and a subagent hands back its own paraphrase instead. |
| Multi-agent Workflow orchestration | Solves independent-perspective or redundant-verification problems. This task has neither — one analyst reading primary sources needs no second independent voice. Also expensive relative to a single-session report. |
| A dedicated persistent planning-file system, if the whole task fits one session | If nothing here needs to survive a `/clear` or compaction boundary, that machinery is ceremony. Reach for it only if the task is genuinely large enough to risk losing state mid-way. |

**What actually fits:**
- A **todo/task list** for phase tracking (gather → cross-reference → write → verdict).
- A **single scratch findings file** to flush large batched-tool-call results into before
  the next batch pushes them out of context — not a full plan/progress/findings trio
  unless the task will span multiple sessions.
- **Batched, concurrent tool calls** for the actual fan-out — gathering PRs/issues/git
  log/docs in parallel is I/O-bound gathering, not reasoning, so it doesn't need
  separate agent contexts to parallelize.

The cross-referencing step — finding that a doc's Part 2 contradicts its own Part 1
because only one was updated, or that four "done" commits never went through the
review the project itself requires — needs both halves in the same reasoning context.
Don't split that across agents.

## Inputs

| Parameter | Default |
|---|---|
| Target | the repo/feature named in the request |
| Plan of record | discovered in Step 1 below — may not be a file in this repo |
| Spec corpus | auto-discovered in Step 2 — `docs/specs/`, `docs/design/`, `rfcs/`, `adr/`, or this repo's own convention; the spec-coverage section is omitted if none exists |
| Window | the plan doc's own last-updated date, if it has one; else the earliest commit touching the feature |
| `--no-write` | off — the report is written to `.drift-status/<YYYY-MM-DD>-<slug>.md` by default (Step 6). Pass it to print only. |

## Process

1. **Identify the plan of record — don't assume it's a committed file in this repo.**
   Check repo docs first (grep for "supersedes"/"superseded by" if more than one
   exists). If nothing local fits, check open PRs and issues — including in other
   repos the project links to — for a design doc, spec, or phase plan. **If the plan
   of record itself turns out to be an unmerged, still-being-edited PR or draft, that
   is a first-class finding, not backdrop** — report it prominently, not as a footnote,
   since everything downstream is being measured against something not yet ratified.
   **If no plan of record exists anywhere** (repo, linked repos, trackers), say so
   explicitly and produce a state-only report — what exists, per-component status —
   skipping the plan-vs-reality section rather than fabricating an implied plan or
   silently dropping the report.

2. **Gather actual state, batched and concurrent:**
   - Code reality: module/directory structure, file counts, what's scaffold vs built.
     Don't trust doc claims — check the source tree.
   - Tracker state: open/merged/closed PRs, open/closed issues, with dates and mergeable
     status. Note PRs that conflict with the base branch — often the single best signal
     of stalled work.
   - **Spec corpus:** enumerate every document in the project's spec/design/RFC directory
     and classify each one by whether the artifacts it names actually exist — plus the
     open tracker items with no spec at all. Full procedure, buckets, and the
     reconciliation rule: **Spec Coverage**, below. Classification consumes both the code
     reality and the tracker state above, so run it after them, not in the same batch.
   - **Governance/process conformance, not just code completeness:** for work the plan
     marks "done," check whether it actually went through the project's own required
     process (PR + review, worktree isolation) — not just whether the code exists.
     Commits landed straight to the default branch with no associated PR is a real
     finding, distinct from and orthogonal to whether the code itself is complete.
   - Commit history since the plan doc's date, filtered to non-merge commits — real
     velocity, not activity noise. **Verify claims empirically where feasible** (run the
     test suite, check a build) rather than trusting a commit message's claimed pass
     count — a commit message is just another doc, with the same unverified status as
     the roadmap.
   - Any parallel/background work in flight (other sessions, worktrees, branches) not
     yet reflected in the tracker.

3. **Read the plan doc(s) and any decision-tracking doc** (worksheets, ADRs, decision
   logs). Note explicit action items, open questions, and their status.

4. **Cross-reference — this is the actual analytical work, not the gathering:**
   - Walk the plan's own phase/milestone table against what's actually built. Mark each
     row accurate / stalled / wrong.
   - Check for **internal contradiction**, not just staleness: if a doc was partially
     updated for a later decision, does an earlier section still assert the superseded
     position? Worse than plain staleness — partial freshness reads as full authority.
   - Check for material findings in **open, unmerged** PRs/docs the plan doesn't know
     about yet — flag these explicitly as *proposed, not yet reflected*, not settled.
   - Note **decision debt**: open questions/action items sitting untouched since filed,
     especially ones blocking a phase the plan calls "next."
   - **Separate self-disclosed debt from independently discovered debt.** If the plan or
     a commit message already admits a limitation as accepted/deferred, that's evidence
     the plan is honest — credit it as such, don't re-report it as a fresh finding or,
     worse, drop it because it "isn't news."
   - **Note when a claim can't be verified** with the tooling available (e.g., a coverage
     percentage with no coverage tool installed). Say so explicitly — don't silently
     assume pass, and don't silently omit the claim.
   - **Reconcile the spec corpus against both code and tracker.** A spec whose issue is
     closed while its artifacts don't exist, a spec whose own implementation index
     contradicts the merge log, and an open feature with no spec at all are each drift —
     in the specs, not only in the plan of record. Treat a spec's internal contradiction
     as seriously as the plan doc's.

5. **Compose the report** with, at minimum:
   - Executive summary — the state in 3-5 sentences, leading with the biggest gap.
   - Per-component status: completed / pending / open / future.
   - Plan-vs-reality table or section, citing specific line numbers / PR numbers / commit
     SHAs, not paraphrases — **omit this section, explicitly, if Step 1 found no plan
     of record at all**; don't fabricate one to fill the shape.
   - **Spec coverage** — the two tables defined in **Spec Coverage** below: a metrics
     table whose every count is derived from, and reconciles with, an instances table
     enumerating the documents behind it. Omit the section, explicitly, if the repo has
     no spec corpus. Lead it with finished-but-unscheduled designs, not with the
     missing-spec count.
   - A verdict: does the plan doc need updating, and if so, at what level (mechanical
     correction vs re-plan vs structural fix to prevent recurrence) — or, if no plan
     exists, whether one should be written?
   - A suggested action sequence, ordered by dependency, not by section order.

   Every count anywhere in the report — not only in the spec section — is derived from
   an enumeration the report itself shows. A number with no visible list behind it does
   not go in.

6. **Persist it — without being asked.** This report is the distillation of an expensive
   cross-source gathering pass, and it is worthless the moment it scrolls out of context.
   Write it to `<root>/.drift-status/<YYYY-MM-DD>-<slug>.md`, where `<root>` comes from
   `git rev-parse --show-toplevel` (fall back to the cwd with a one-line warning if that
   fails — a missing canonical root is not a reason to skip the write). `mkdir -p` the
   directory.
   - **Slug** — the plan-of-record doc's basename with its extension dropped and `-drift`
     appended (`ROADMAP.md` → `roadmap-drift`, `docs/prd/maker.md` → `maker-drift`); with
     no plan of record, the repo name plus `-drift`. Normalize in this order: lowercase;
     collapse every run of non-alphanumerics to a single `-`; trim leading and trailing
     `-`; truncate to 60 chars on a `-` boundary. This is derivation, not rewriting of a
     caller's value — there is no `--slug` flag — so nothing here is rejected; if the
     result is empty or a bare `-`, fall back to `status-drift`.
   - **Collision** — if the file already exists (same plan audited twice in one day),
     append `-2`, then `-3`, … until it doesn't; give up after `-20` and append
     `$(date +%H%M%S)`. **Do not ask.** An unattended audit has nobody to answer, and the
     two things an agent improvises when it can't ask are overwriting the previous report
     or skipping the write — losing one report either way, which is the failure this step
     exists to prevent.
   - Then print the report in full to the user with `Wrote: <absolute path>` as the first
     line. `--no-write` skips the file and prints only.
   - **If the write itself fails** (permissions, read-only mount, full disk, or the
     resolved directory turns out to be a file), print the report in full anyway with a
     one-line note naming the path and the error. Never discard a finished audit over a
     failed write — and never print `Wrote:` for a file that isn't there. The same applies
     when the git-root lookup fell back to the cwd: say so in the output, not only on
     stderr, or the report lands somewhere nobody thinks to look.

   `.drift-status/` is transient working output, not a deliverable — it belongs in
   `.gitignore`. Tell the user to add it if the repo doesn't have it yet; an untracked
   directory quietly polluting `git status` is its own small drift.

7. **Don't silently execute the fix.** A status report is diagnostic. If the verdict is
   "update the plan," propose it and stop — let the user confirm scope before editing a
   plan-of-record doc, especially one other people read as authoritative.

## Spec Coverage — Inventory, Classification, Reconciliation

A project's specs are a third source of drift alongside code and trackers, and they
drift in both directions: specs describing work nobody built, and work nobody wrote a
spec for. Run this whenever a spec corpus exists. If none does, say so in one line and
omit the section — the same graceful degradation Step 1 applies when there is no plan of
record.

### 1. Enumerate the corpus first

Find the spec corpus — `docs/specs/`, `docs/design/`, `rfcs/`, `adr/`, `specs/`, or
whatever this repo calls it; check `CLAUDE.md` / `CONTRIBUTING.md` for the convention.
List every file. That list is the denominator for everything below, and it is a **file
listing**, not an estimate or a recollection.

If the corpus is too large to verify deeply (say, over 40 documents), still enumerate
all of them — filenames are cheap — and deep-verify a stated subset: every spec the plan
of record references, every spec touched inside the audit window, and every spec whose
bucket isn't obvious. Then report how many were enumerated and how many were
deep-verified. A declared sample beats a silent one.

### 2. Classify by evidence, never by the spec's own Status header

**A spec's Status header is the least reliable field in the document.** It is written
once and rarely revisited. In the run the worked example comes from, one spec's header
asserted "there is no amendment section to apply on top" while four of its stated
premises were already stale. Read it, then classify without it.

Classify from artifacts instead:

- **Extract the concrete nouns the spec names** — class and type names, endpoint paths,
  table and migration names, config keys, module names, CLI flags, env vars — and look
  up each one. A spec is implemented to the extent that the things it names exist.
- **A grep hit is not a declaration.** Filter out doc-comment mentions, string literals,
  test fixtures, and other specs quoting this one. In the source run a stated absence
  ("exists only in X and Y") was wrong because the Y hits were doc comments, not
  declarations. Check each hit's context before it counts.
- **Check the wiring, not just the file.** A module on disk but absent from the build
  file (`settings.gradle*`, `pyproject.toml`, `Cargo.toml`, workspace globs, `go.work`)
  is not implemented. A migration file no migration table references is not applied. A
  route defined but never registered is not reachable. File presence is the weakest
  evidence available.
- **Cross-check the tracker.** A spec whose issue is closed while its artifacts don't
  exist — or the reverse — is a finding in its own right, not just a classification
  input.
- **Verify a spec's own implementation index against the code.** When a spec carries a
  checklist or an "implemented in" table, treat it as a plan doc in miniature and apply
  Step 4's internal-contradiction check to it. A stale self-index inside a spec is the
  same defect as a stale section inside a roadmap.

### 3. Buckets — exactly one per document

| Bucket | Test | Why it matters |
|---|---|---|
| As-built record | Every named artifact exists. | It's documentation, not a plan. No action — do not report it as outstanding work. |
| Partially implemented | Some named artifacts exist, some don't. | Record as `landed/total` against the spec's *own* step or phase list, citing step numbers on both sides. |
| Written, unimplemented, unblocked | No artifacts exist and nothing outside engineering is stopping it. | **The highest-value bucket.** Design done, cost known, nobody scheduled it. Sub-flag any member sitting on a gate or critical path. |
| Written, unimplemented, blocked | Same, but a named external dependency (product decision, counsel, vendor, upstream API) is outstanding. | Name the blocker and where it's tracked. Unnamed, it collapses into the row above and misdirects the reader. |
| Spike / investigation, not yet run | The deliverable is an answer, not a feature. | Different exit criterion — a finding, not a merge. Usually cheap, often unblocking. |
| Stale / historical | The subject no longer exists or was superseded. | Prove it structurally: module de-registered from the build, directory gone, superseding doc named. Age alone proves nothing. |
| Unclassified | You could not place it. | **Report the count.** An unclassified spec is a gap in the audit, not the absence of one. Dropping it is how bucket totals stop summing. |

Separately, and **not** a spec bucket: **features with no spec** — open tracker items
with no corresponding document. Report these as two distinct numbers: the count of
tracker items, and the count of specs that would have to be written to cover them. Those
differ whenever items merge into one design.

### 4. Metrics must reconcile with instances

This is the rule the rest of this section exists to serve, and it is the one that fails
in practice. The order of operations is fixed:

1. **Enumerate the instances first.** One row per document, written down.
2. **Derive every count by counting rows** — not from memory, not from a running tally
   kept while reading.
3. **Never state a number that isn't backed by a list in the same report.**

Then these five properties, built in rather than checked after:

- **Every count carries its unit in its own label.** "16 open feature issues" and "15
  specs to write" are different units over the same set; writing one and labelling it
  with the other's noun is the most common form of this error.
- **The bucket-total row is mandatory** and must equal the corpus count. When it doesn't,
  you have documents you failed to report — move them into Unclassified rather than
  adjusting the total.
- **Ranges are not counts.** `#333–#342` spans 10 numbers, not 16, and a range is no
  evidence that every number inside it belongs to the set. Enumerate members first;
  present the range as shorthand only once the enumeration confirms it is contiguous.
- **A stated absence is a claim** and carries the same evidence burden as a stated
  presence. "Only exists in X and Y" requires confirming the Y hits are declarations.
- **Write the prose from the table, not from memory.** Prose drafted before a table gets
  corrected is the failure mode: in the source run, a sentence said "six of eight steps"
  twelve lines above a table showing four. A reader who checks one number and finds it
  wrong stops trusting all of them.

### 5. Report shape

Two tables, in this order, in the report's spec-coverage section.

**Spec coverage — metrics.** Every Count is `COUNT()` over the instances table below it.

| Metric | Count | Unit |
|---|---|---|
| Specs in corpus | N | documents |
| — As-built record | | documents |
| — Partially implemented | | documents |
| — Written, unimplemented, unblocked | | documents |
| — Written, unimplemented, blocked | | documents |
| — Spike, not yet run | | documents |
| — Stale / historical | | documents |
| — Unclassified | | documents |
| **Bucket total — must equal corpus** | N | documents |
| Open features with no spec | | tracker items |
| Specs needed to cover them | | documents to write |

**Spec coverage — instances.** One row per document; every metric above is a filter over
this table.

| Spec | Bucket | Evidence checked | Blocker | Action |
|---|---|---|---|---|

- **Spec** — path, not title. The reader has to be able to open it.
- **Bucket** — exactly one of the seven. No "mostly" or "partially-ish".
- **Evidence checked** — the artifact lookup that decided the bucket *and its result*.
  `TransferAuditRecord — 0 declarations` is evidence; "not implemented" is the bucket
  restated.
- **Blocker** — the named external dependency and where it's tracked, or
  `none — engineering-ready`.
- **Action** — one verb: implement / write spec / run spike / archive / classify.

Then a third table for the other direction:

| Open feature | Tracker ref | Spec needed | Merges with |
|---|---|---|---|

Lead the section's prose with the **written, unimplemented, unblocked** rows, not with
the missing-spec count. Missing specs are a documentation gap; a finished design for
gate-blocking work that nobody scheduled is a delivery gap, and it is the more
actionable of the two.

## Quick Reference — Drift Signal Types

| Signal | How you catch it |
|---|---|
| Stale claim | Doc says X; source tree/tracker says otherwise. |
| Internal contradiction | Doc section A still asserts what doc section B supersedes — only B was updated. |
| Proposed, not settled | An open, unmerged PR/doc contains findings the plan doesn't reflect yet. |
| Decision debt | An open question or action item has sat untouched, blocking a phase the plan calls next. |
| Process/governance gap | Code the plan marks "done" landed without the review process the project itself requires. |
| Unverifiable claim | A metric the plan cites (coverage %, benchmark number) can't be checked with tooling on hand. |
| Plan itself unratified | The "plan of record" is an unmerged draft — everything measured against it inherits that uncertainty. |
| Written spec, unscheduled | A spec names artifacts that don't exist and no external dependency blocks it — the design is finished and nobody picked it up. |
| Spec self-index stale | A spec's own implementation index or Status header claims a state the source tree contradicts. |
| Uncovered feature | An open tracker item with no spec — work in flight with no written design to drift *from*. |
| Orphaned spec | The spec's subject is gone from the build (module de-registered, directory removed) but the spec still reads as current. |

## Examples

**Worked example — the spec-coverage section of a real report.** Kotlin/Gradle
multi-module trading backend, 19-document corpus, audited 2026-08-26. Reproduce this
shape. The numbers are a dated snapshot; the reconciliation is not optional.

```markdown
## Spec coverage

**Lead finding: four engineering-ready work items — two on the live-signing critical
path — have finished designs and no owner.** That is a larger delivery gap than the 16
uncovered features below: those need a spec written; these need someone to pick up work
that is already specified.

### Metrics

| Metric | Count | Unit |
|---|---|---|
| Specs in corpus (`docs/specs/`) | 19 | documents |
| — As-built record | 3 | documents |
| — Partially implemented | 2 | documents |
| — Written, unimplemented, unblocked | 3 | documents |
| — Written, unimplemented, blocked | 0 | documents |
| — Spike, not yet run | 1 | documents |
| — Stale / historical | 6 | documents |
| — Unclassified | 4 | documents |
| **Bucket total — must equal corpus** | **19** | documents |
| Open features with no spec | 16 | tracker items |
| Specs needed to cover them | 15 | documents to write |

Three unit notes — each one a place this report nearly stated a wrong number:

- **Engineering-ready work is 4 items across 3 documents**, not 4 documents. The fourth
  is §9 steps 3/7/8 of `2026-06-30-merchant-build-spec.md`, a document already counted
  under *Partially implemented*. The bucket row counts documents; the lead sentence
  counts work items; both say which.
- **16 tracker items → 15 specs.** #316 and #386 are one design. The issue count and the
  spec count are different numbers and neither may wear the other's noun.
- **Stale is 6 and As-built is 3 — the first pass said 5 and 2.** The buckets summed to
  17 against a corpus of 19. The mandatory total row is what caught it; the two missing
  documents were `2026-07-30-maker-mvp-build-spec.md` and
  `2026-07-19-module-communication-design.md`.

### Instances — specs

| Spec | Bucket | Evidence checked | Blocker | Action |
|---|---|---|---|---|
| `2026-07-30-maker-domain-core-spec.md` | As-built | Every named type declared under `Maker/` | — | none |
| `2026-07-24-issue-77-signer-resolution-gate.md` | As-built | `GatedSignerProvider` declared, `SignerProvider.kt:83` | — | none |
| `2026-07-19-module-communication-design.md` | As-built | Two-listener topology shipped per ADR-0010 | — | none |
| `2026-06-30-merchant-build-spec.md` | Partial | §9 tracer-bullet: 4 of 8 steps landed (1, 2, 4, 5); step 7 executor map is `emptyMap()` at `Main.kt:220` | none — engineering-ready | implement §9 steps 3, 7, 8 |
| `2026-08-08-gateway-initial-draft-spec.md` | Partial | 8 phases merged (#333–#342); the spec's own §13.0 index still lists as ❌ two items #365 landed | — | correct §13.0 index |
| `2026-07-09-privy-signing-harness-spec.md` | Written, unblocked | Harness built; #143 open — `LivePrivyGateway` folds 401 revocation into `PolicyDenied` | none — engineering-ready | implement — gates trusting the audit trail |
| `2026-07-30-merchant-signer-wiring-plan.md` | Written, unblocked | `PrivyDelegatedSigner` declared only in `:privy-harness`; absent from `Merchant/.../signing/` | none — engineering-ready | implement — live-signing path |
| `2026-07-06-privy-delegated-signer-design-note.md` | Written, unblocked | `delegated_execution_audit` + 2 sibling tables: 0 hits across all `*.sql`; migrations stop at `V010` | none — engineering-ready | implement — live-signing path |
| `2026-08-12-privy-did-stability-spike-spec.md` | Spike, not run | `privy-harness/spike/` absent; no evidence doc | — | run spike |
| `2026-07-30-maker-mvp-build-spec.md` | Stale | §8.1 lists S25–S27 blocked on 5 conditions; 2 are now false, and ADR-0013 deletes S25 outright rather than unblocking it | — | supersede via #278 |
| `2026-04-2x-*` — 5 Traitor specs | Stale | `traitor` absent from `app/build.gradle.kts` — de-registered, not merely old | — | archive or mark superseded |
| 4 further documents | Unclassified | Not reached this pass | — | classify next pass |

### Instances — open features with no spec

| Open feature | Tracker ref | Spec needed | Merges with |
|---|---|---|---|
| Live wallet balance | #316 | balance + account-watch | #386 |
| Crypto deposit detection | #386 | (covered by #316's spec) | #316 |
| Stop-loss / take-profit | #313 | venue-native trigger orders | — |
| … 13 further rows, one per open issue … | | | |

### Verdict on spec coverage

Two of the three unblocked written specs sit on the live-signing critical path and
neither has an owner. Sequence them ahead of the 15 specs that still need writing: a
finished design nobody scheduled is closer to shipping than a feature with no design.
```

**Count without an enumeration — bad vs. good**

Bad:
> Roughly 15 open feature issues have no spec, and about six of the eight tracer-bullet
> steps have landed.

Why bad: "roughly" and "about" over a set that can be counted exactly; `15` is the spec
count wearing the issue count's noun; and "six of eight" contradicts the instances table
twelve lines below, which shows four. Every one of these is visible to a reader who has
the table in front of them.

Good:
> 16 open feature issues have no spec; #316 and #386 merge, so 15 specs need writing —
> both lists are in *Instances* below. `merchant-build-spec` §9: 4 of 8 tracer-bullet
> steps landed (1, 2, 4, 5); steps 3, 7 and 8 have 0 declarations.

**Classifying from a Status header — bad vs. good**

Bad:
> `merchant-signer-wiring-plan.md` — Status: *"build from §1 forward; there is no
> amendment section to apply on top."* Current, ready to build.

Why bad: the header records the author's belief at writing time. This one names two
dependency issues as OPEN that are both closed, calls a third reopened when it is
closed, and asserts a file is a 15-line stub that is now 427 lines. The Status header is
the last field anyone updates and the first one to lie.

Good:
> `merchant-signer-wiring-plan.md` — Written, unblocked. `PrivyDelegatedSigner` is
> declared only in `:privy-harness`, absent from `Merchant/.../signing/`. Header claims
> no outstanding amendments; four of its stated premises are stale (2 closed deps
> reported open, 1 closed reported reopened, 1 file 15 lines → 427). Action: implement,
> re-verifying premises against the tree first.

## Common Mistakes

- Reporting doc claims as fact without checking the source tree / tracker.
- Trusting a commit message's claimed test/pass count instead of running the suite.
- Treating "the roadmap was updated on date X" as evidence the whole doc is current —
  check whether *every* affected section was updated, not just the one the changelog
  mentions.
- Burying the contradiction/drift finding under a wall of per-module status — lead with
  it if it's the most actionable finding.
- Treating an open, unmerged PR's findings as settled plan — mark them proposed.
- Assuming the plan of record is a file in this repo — it may be an issue, an open PR,
  or a doc in a different, linked repo.
- Flagging code-completeness only — a phase can be code-complete but process-incomplete
  (no PR, no review) if the project requires one; report that as its own gap.
- Re-reporting self-disclosed, already-accepted debt as a new discovery instead of
  crediting the plan for disclosing it.
- Skipping the "should the plan be updated" verdict — a status report that doesn't say
  what to do about drift is just a data dump.
- Leaving the report in chat only. Its whole value is being re-readable next week, by a
  different session — a transcript is not a durable artifact.
- Stating a count the report doesn't enumerate. Every number needs a visible list behind
  it — derive counts from the instances table, never the reverse.
- Letting a count wear the wrong unit: reporting the number of specs needed as a number
  of issues, or a tracker range's span as a member count. Put the unit in the metric's
  own label.
- Leaving prose numbers unreconciled with the table below them after an edit. The table
  gets corrected; the sentence drafted before it does not.
- Classifying a spec from its own Status header instead of from whether the artifacts it
  names exist. The header is the least-maintained field in the file.
- Counting a grep hit as an implementation. Doc comments, string literals, and other
  specs quoting this one are mentions, not declarations — and a module on disk but
  absent from the build file is not wired in.
- Leading the spec section with "N features have no spec." The sharper finding is usually
  the opposite: a finished, unblocked design for blocking work that nobody picked up.
- Dropping the specs you couldn't classify. Report them as Unclassified with a count — a
  silent omission is exactly what makes a bucket total stop summing to the corpus.
