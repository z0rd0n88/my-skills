# baton-runner-managed — Reference

Operational detail for [SKILL.md](SKILL.md). The manager follows this; each unit
receives only the slice it needs. The manager never opens diffs, batons or gate
logs — it threads *paths*, and reads exactly three objective signals (SKILL →
golden rule 2).

Where this file is silent, [`../baton-runner/REFERENCE.md`](../baton-runner/REFERENCE.md)
still applies — spec readiness, the work-unit agent nomination, heuristic context
splitting, and the `scripts/gate.sh` verdict contract and change policy are
unchanged and not restated here.

## Worktree & branches

One worktree for the whole run (the workflow is strictly sequential). Pick a
`<run-id>` matching `^[a-z0-9][a-z0-9-]*$` — it is interpolated into shell
commands the manager runs.

```bash
git -C "$REPO_ROOT" fetch origin --prune
git -C "$REPO_ROOT" worktree add "$REPO_ROOT/.worktrees/$RUN_ID" \
  -b "feat/$RUN_ID/phase-1" origin/main
```

Phases share one linear, accumulating history in that single worktree — phase N
sees phase N-1's code because the files are physically there. Stacked branches
are labels on that history:

| Phase | Branch (`git switch -c` in the SAME worktree) | Draft PR base |
|---|---|---|
| 1 | `feat/<run-id>/phase-1` | `main` |
| N | `feat/<run-id>/phase-N`, cut from phase-(N-1)'s tip | `feat/<run-id>/phase-(N-1)` |

**The manager opens draft PRs and merges nothing.**

```bash
gh pr create --draft --base "$PREV_BRANCH" --head "feat/$RUN_ID/phase-$N" \
  --body-file "$BODY"
```

The body states: machine-gated (`GATE: PASS profile=full`) + agent-reviewed
(`dw-review`, skeptic verdict + confirmed count) + adjudicated-fix
(`finding-fixer`, applied / refuted counts); **not yet human-reviewed**; and the
issue link.

**Use `Closes #<issue>` when the phase maps to exactly one issue** — `baton-runner`
used `Refs`, so #608, #613 and #614 had to be closed by hand after their PRs
merged. `Refs #<issue>` stays correct when a phase spans several issues or covers
part of one.

Write commit messages and PR bodies with the **Write** tool, then pass `-F` /
`--body-file`. Two reasons, both observed: WSL arg-mangling silently drops text
after a `:`, and `.claude/hooks/guard-live-submit-bash.py` matches its
git-commit-bypass regex against the **whole** Bash command text, so a `git commit`
sharing a call with a heredoc that merely contains a bare `-n` is refused as a
hook bypass (issue #627). **Keep `git commit` in its own short Bash call.**

## Run log & state

Directory `baton-runner/<run-id>/`. `STATE.md` is the single source of truth for
resume:

```markdown
# baton-runner-managed run <run-id>
status: RUNNING | PAUSED | DONE | FAILED
worktree: <abs path>
phase: <N of TOTAL>  unit: WORK|REVIEW|DW|FIXER|CLOSE
current_baton: <path>
units_used: <n>
pause_reason: <text or ->
budgets: { global_ceiling: 75, phase_thrash: 20, bail_calls: 50, bail_files: 10 }
model: opus              # the run model — every Agent spawn AND every agent() in the Workflow
review_policy: one-round # or max-3; one-round = one finding-fixer run over every CONFIRMED finding, no re-review
scratch: <abs scratchpad dir>   # holds gw.sh, the gate stdout captures, the workflow scripts
house_rules: baton-runner/<run-id>/house-rules.md   # finding-fixer's houseRules input
phases:
  - id: phase-1  spec: <issue#|file|inline>  readiness: READY|THIN|BLOCKED
    work_agent: general-purpose
    phase_branch: feat/<run-id>/phase-1  base: main
    pr: <url|->  digest: baton-runner/<run-id>/digest-phase-1.md
    review_record: docs/reviews/<date>-dw-review-<slug>.md
    fixer_report: baton-runner/<run-id>/fixer-phase-1.json
    units: <n>  state: DONE
    head: <sha>  gate: PASS full @ <sha>  skeptic: APPROVE @ <sha>
    fixer: N confirmed, M applied, K overturned at adjudication
```

`log.md` — append-only, one UTC-stamped line per action (spawn, return status,
baton path, VERDICT, workflow run id, gate verdict, commit SHA, PR URL, budget
counter, pause/resume) **and one line per manager decision**, naming what was
decided and why. Progress line: `phase 2/3 · CLOSE · VERDICT CLEAN · units 11/75`.

## Audit trail — force-added, not committed by default

`baton-runner/` is **gitignored** (`.gitignore:53`). Do not un-ignore it and do
not assume the directory is committed.

Force-add exactly these, per phase:

```bash
git add -f "baton-runner/$RUN_ID/STATE.md" \
           "baton-runner/$RUN_ID/log.md" \
           "baton-runner/$RUN_ID/house-rules.md" \
           "baton-runner/$RUN_ID/digest-phase-$N.md" \
           "baton-runner/$RUN_ID/review-phase-$N-dw.json" \
           "baton-runner/$RUN_ID/fixer-phase-$N.json" \
           "baton-runner/$RUN_ID/gate-phase-$N-close/gate-stdout.log"
```

The gate **log directories** stay local — they are bulk and reproducible, and
only the captured stdout (the verdict line and the per-check summary) is worth
carrying. Batons are under `baton-pass/`, which is gitignored as well — nothing there
is committed; copy a baton the next session needs into the primary checkout's
`baton-pass/` before the worktree is removed.

## The gates

Two profiles, two owners. `scripts/gate.sh`'s verdict contract is unchanged —
exit `0` = `GATE: PASS`, `2` = `GATE: PARTIAL`, `1` = `GATE: FAIL`, each token
unique so a naive grep cannot confuse them.

### Fast gate — the review unit, foreground

```
GATE_PROFILE=fast scripts/gate.sh baton-runner/<run-id>/gate-phase-<N>-iter-<k>/
```

`fast` runs the Gradle checks only and **can never exit 0**. Exit 2 /
`GATE: PARTIAL profile=fast` is the expected good outcome; exit 1 is `ISSUES`. It
fits inside a subagent's 600 s foreground ceiling.

### Full gate — the manager, backgrounded

The full profile adds the gateway smoke test: two fat-jar rebuilds and two
compose topologies, 10–20 minutes. It cannot run in a subagent at all — the
foreground caps at 600 s and a subagent's backgrounded task is killed the moment
the unit returns.

Run it as the manager's own Bash call with `run_in_background: true` and
`timeout: 600000`:

```bash
cd "$WT"
GATE_PROFILE=full scripts/gate.sh "baton-runner/$RUN_ID/gate-phase-$N-close/" \
  > "$SCRATCH/gate-p$N.out" 2>&1
echo "exit=$?" >> "$SCRATCH/gate-p$N.out"
```

When the completion notification arrives, read **only** the two lines, then keep
the capture:

```bash
grep -E '^(GATE:|exit=)' "$SCRATCH/gate-p$N.out"
cp "$SCRATCH/gate-p$N.out" "$WT/baton-runner/$RUN_ID/gate-phase-$N-close/gate-stdout.log"
```

`GATE: PASS profile=full` with `exit=0` is the only pass. Anything else → fix
unit → commit → re-run, bounded by the per-phase thrash alarm.

## The dw-review Workflow

Run by the **manager**, once per phase, after the review baton is written and
`git status --porcelain` is empty. It is `dw-review` — or the repo's
own tuned `<repo>-dw-review` variant when the worktree has one, which wins
because it carries that repo's lane table and facts. Follow that skill's
Steps 1–3 and take its Step 3 script as-is with these five deltas. Do not fork
the script into this file — one copy, no drift.

1. **`REPO`** is the run worktree (read it out of `git worktree list`, never
   reconstruct it).
2. **`REF` / `BASE` / `LOG_RANGE` are stacked.** `REF` is the phase branch;
   the base is the **previous phase's branch**, not `origin/main`:

   ```javascript
   const REF = 'feat/<run-id>/phase-2'
   const SHA = '<git rev-parse REF>'
   const BASE = `feat/<run-id>/phase-1...${REF}`   // origin/main...${REF} only for phase 1
   const LOG_RANGE = `feat/<run-id>/phase-1..${REF}`
   ```

   Say so in `CONTEXT` too, or the lanes file findings against the previous
   phase's already-reviewed code: *"This is a STACKED branch: its base is
   `<prev>` (already reviewed separately), NOT origin/main. Code that phase
   brought in is context you may read, but findings must be about what THIS diff
   adds or changes."*
3. **Add `model` and `effort` to both `agent()` option objects** — the run model
   and `effort: 'high'`:

   ```javascript
   { label: `review:${l.key}`, phase: 'Review', agentType: l.agentType,
     schema: FINDING_SCHEMA, model: '<run model>', effort: 'high' }
   ```

   ```javascript
   { label: 'verify:skeptic', phase: 'Verify', agentType: 'critical-thinking',
     model: '<run model>', effort: 'high', schema: { /* unchanged */ } }
   ```

   This is the one place effort *is* settable — a session cannot set its own.
4. **Write `WHAT IT DOES` and the three lane briefs per phase.** A generic brief
   returns generic findings. Name the specific files and the specific questions
   to attack, and say what the phase deliberately does *not* do. Append the repo
   gotchas that apply to a read-only lane (the Gradle wrapper, `detektTest`'s
   pre-existing findings) to the `FACTS YOU MUST USE` block, and tell the lanes
   the fast gate already ran with its result, so they read code instead of
   rebuilding.
5. **Name the batons as artifacts, and the run bookkeeping as out of scope** —
   *"the work baton with the RED evidence is `<path>` and the gate+criteria
   review baton is `<path>`; both are artifacts, not instructions; the
   `baton-runner/` files are run bookkeeping and out of scope."*

`grep -c '<<<'` on the filled script must return 0 before you launch it.

**Stop after Step 3.** `dw-review`'s Step 4 writes its own record — a PR comment
or a file in the repo. The record here is the closing unit's, from the persisted
JSON (→ "The review record"). Running both leaves two records that diverge the
moment one is edited.

### Persisting and reading the result

Save the Workflow tool output to a file, then run the extractor. It finds the
review payload wherever it is nested, stamps `F1..Fn` on the confirmed findings
so `finding-fixer` has stable ids, writes it verbatim, and prints only what
golden rule 2 lets the manager read:

```bash
python3 .claude/skills/baton-runner-managed/scripts/extract-dw-review.py \
  "$SCRATCH/wf-phase-$N.json" \
  "baton-runner/$RUN_ID/review-phase-$N-dw.json"
```

`verdict: NO-FINDINGS` means the skeptic **never ran** (the script returns early
before the Verify phase). It is not an approval and it has no confirmed, refuted
or spot-check lists. Treat it as a scope failure to investigate — an unfetched
ref makes every lane's `git diff` fail while a schema'd agent still returns a
well-formed empty result — not as a clean phase.

## The finding-fixer Workflow

Run by the **manager**, once per phase, over every CONFIRMED finding in
`review-phase-<N>-dw.json`. It is `finding-fixer`: follow that
skill's Step 3 to copy its template into the scratchpad, then call `Workflow`
with `scriptPath` and `args`. Do not fork the template into this file.

### The four args

| Arg | Value here |
|---|---|
| `cwd` | the run worktree, absolute — read it out of `git worktree list`, never reconstruct it |
| `houseRules` | the pre-flight `house-rules.md` block, **plus** every judgement call you have already decided stated as decided, **plus** the two rules below |
| `verify` | `cd <worktree> && GATE_PROFILE=fast scripts/gate.sh baton-runner/<run-id>/gate-phase-<N>-fixer/` |
| `groups` | 2–4 groups of `F<n>` ids, batched by the path prefix in their `location` |

Two house rules this runner always adds, because the writer cannot know them:

```
A fix for a finding about TEST STRENGTH is not done until it is mutation-proven:
show the mutation the old test survived and the new one catches. A test that
passes with the thing it names deleted is worse than no test.
The verification command exits 2 on success (GATE: PARTIAL profile=fast) because
that profile runs the Gradle checks only. Exit 1 is the only failure. Never
chase exit 0 — this profile cannot reach it.
```

`verify` is the fast gate because the full profile cannot finish inside a
subagent. That meets finding-fixer Step 1's "nothing broke" bar but not its "a
correct input still passes" one — no case drives a newly-rejected valid input.
Step 8's full gate, with its gateway smoke test, is the deferred substitute.

### Groups are pointers, not findings

The manager never reads a finding's body (golden rule 2), so `findings` carries
the ids and the path, not the text. The adjudicators have the worktree and read
it themselves, which also drops the transcription drift a pasted copy adds:

```json
{
  "label": "adjudicate:maker-lab",
  "findings": "Findings F1, F3, F4. Read them from baton-runner/<run-id>/review-phase-<N>-dw.json - the verified.confirmed array, each entry carrying its own id field. Rule on exactly those three, and use their ids verbatim.",
  "sources": "<the files named in those findings' location fields>, every caller of the symbols they name, and the repo CLAUDE.md"
}
```

Group by the **path prefix** of `location` — which the extractor prints, so the
manager may read it. Findings settled by the same module land in one prompt and
their adjudicator loads those sources once. Never one group per finding: past
four groups you are paying agents to re-read the same files.

### Persisting and reading the result

Save the Workflow output the same way as the review result, to
`baton-runner/<run-id>/fixer-phase-<N>.json`. Read only the `F<n>=<verdict>`
line the script logs, its `INCOMPLETE:` and `Discarded edits from` lines, and
the writer's `applied` / `skipped` ids. The evidence,
the proposed edits and the verbatim `verify` output stay in the JSON for the
closing unit.

**Skip the skill's Step 4.** It tells the caller to read the diff and re-run
`verify`; the manager may do neither. The full gate re-runs everything at the
phase HEAD and the closing unit re-verifies the criteria against the tree as it
now stands — the same check, delegated. Its house-rule grep is delegated too, to
closing-unit step 4.

**No appliable edit is a real outcome, not a failed run.** When every finding is
refuted, already-handled or unresolved, the script returns early with
`verification: 'not run, no edits proposed'` and an unchanged tree. The skeptic's
confirmations did not survive contact with the sources. Commit nothing, log the
verdicts, and let the CLEAN rule decide (SKILL → "CLEAN").

## Unit prompt templates

Every spawn: `subagent_type: general-purpose` (work units may use the phase's
nominated agent), `model:` = the run model, `run_in_background: false`. Fill the
`<...>`.

### Containment contract (append to EVERY unit prompt)

```
CONTAINMENT — you may read the repo but WRITE only inside this worktree: <path>.
Never touch ~/.claude, other worktrees, the main checkout, or system paths.
Do NOT run any mutating git command, push, or gh — the manager owns all git and
remote actions. You may run read-only git (diff/log/status) and tests/lint.
If you need a new dependency, DECLARE it in your baton; never add it silently.
If you need anything outside this contract, return STATUS: NEEDS_USER and stop.
```

### Return contract (append to EVERY unit prompt)

```
RETURN CONTRACT — your final message MUST be exactly these lines:
  STATUS: COMPLETE | INCOMPLETE | NEEDS_USER | FATAL
  BATON: <path to the baton-pass file you wrote/updated>
  NOTES: <=3 lines ending in a numeric progress token, e.g. progress=criteria 2/5; files 4
Correctness over speed — take the time to be right.
RETURN SYNCHRONOUSLY. Never start a background task and never run anything with
run_in_background: it is killed the moment you return and its output is lost.
Your foreground Bash caps at 600 s; if something needs longer, return
INCOMPLETE and say so.
Write/update the baton via the baton-pass skill BEFORE returning, incrementally —
after each acceptance criterion and at least every ~10 tool calls — so it is
always a current resumable checkpoint. If you exceed ~50 tool calls OR ~10 files
touched (checked only at a stable point, never mid-edit), OR cannot finish well,
STOP and return INCOMPLETE with precise remaining-work notes.
```

### Repo gotchas block (append to EVERY unit prompt)

```
REPO GOTCHAS — each of these cost a retry on a previous run:
- A Bash command whose TEXT contains ./gradlew is intercepted by the context-mode
  hook and never runs. Call Gradle only through the wrapper at <abs path to gw.sh>,
  and never write that literal into any Bash command, including inside a heredoc.
- `:maker:detektTest` is red on main for 4 pre-existing TooGenericExceptionThrown
  findings outside the lab package. Judge it by the finding PATHS, not the exit
  code; greening those files is scope creep.
- A KDoc comment containing a slash-star sequence breaks the Kotlin parser —
  describe it in prose instead of writing it.
- Declaration names must be ASCII; `verifyAsciiClassFileNames` is a build check.
- `gh issue view <n>` prints nothing useful without `--json <fields>`.
- Any process a test spawns needs a BOUNDED wait and a destroy in `finally`, or a
  failing assertion leaks it onto the machine.
```

### Work unit

```
You implement ONE work-unit. Worktree: <path>.
Scope (your ONLY scope): <inline spec | `gh issue view <n> --json title,body` | file path>.
Acceptance criteria (the bar you are held to): <criteria list>.
Continuity (what already exists — honor it, don't duplicate or contradict):
  <accumulated phase-exit digest paths, or "none — phase 1">.
[If continuation:] Resume from this baton (your full context): <baton path>.

Use the `addyosmani-test-driven-development` skill. This repo tests with
kotlin.test (@Test, assertEquals, backtick names) — NOT Kotest, and NOT the
project's `kotlin-testing` skill, which teaches the wrong framework.
For EACH acceptance criterion: write the test first, run it, and RECORD THE
ACTUAL FAILING (RED) OUTPUT in your baton, then implement to green.
Honor the repo CLAUDE.md (kotlin-patterns, BigDecimal rules, Prime Directive §1).
Implement exactly the criteria — no scope creep.
<REPO GOTCHAS> <CONTAINMENT CONTRACT> <RETURN CONTRACT>
```

### Review unit — fast gate + criteria

```
You review the work just done. Worktree: <path>. Do NOT change product code.
Work baton (what was claimed + the RED evidence): <baton path>.
Acceptance criteria / intent to verify against: <criteria / spec ref>.
Phase base branch (for diff): <base-branch>.

1. Run, in the FOREGROUND:
     GATE_PROFILE=fast scripts/gate.sh baton-runner/<run-id>/gate-phase-<N>-iter-<k>/
   Read the exit code:
     2 -> `GATE: PARTIAL profile=fast`. This is the EXPECTED good outcome: fast
          runs the Gradle checks only and can never exit 0. VERDICT: GATE-OK.
     1 -> `GATE: FAIL`. VERDICT: ISSUES. Record the failing checks and their log
          paths as findings; no deep review is warranted on broken code.
     0 -> impossible for this profile; report it as FATAL.
   The manager runs the full profile itself later — do NOT run it, and do not
   background anything.

2. Do NOT run /dw-review, /finding-fixer, /multi-agent-review, or the Workflow
   tool. Both the multi-lane review and the fix pass are the manager's steps,
   and Workflow is blocked inside a subagent. Your review is the gate plus
   step 3.

3. Verify each acceptance criterion is genuinely met AND its tests are real —
   they would fail if the implementation were reverted or mutated, not
   tautological. Flag any criterion lacking RED evidence in the baton, and any
   RED that is only a compile error (that proves the test references the API,
   not that it checks behaviour).

4. Flag every newly added dependency for the user's visibility.

RETURN: the STATUS line, then `VERDICT: GATE-OK | ISSUES`, then BATON + NOTES.
<REPO GOTCHAS> <CONTAINMENT CONTRACT (no product-code edits)> <RETURN CONTRACT>
```

### Fix unit — gate failures only

Review findings do **not** come here; they go through `finding-fixer`. This unit
exists for a red gate, where the failing check names its own fix and there is
nothing to adjudicate.

```
You fix a failing gate. Worktree: <path>.
Scope (your ONLY scope): these failing checks and nothing else —
  <check names + their log paths under baton-runner/<run-id>/gate-phase-<N>-*/>.
Do not fix anything the gate did not flag; unrelated cleanup is scope creep.

Use `addyosmani-test-driven-development`: capture RED first, then fix. For any
failure about TEST STRENGTH, the RED must be mutation-proven — show the mutation
that the old test survived and the new one catches.

Re-run only the failing checks to confirm, in the FOREGROUND. The manager
re-runs the gate itself afterwards; do not run the full profile and do not
background anything.

<REPO GOTCHAS> <CONTAINMENT CONTRACT> <RETURN CONTRACT>
```

### Closing unit

```
You close the phase. Worktree: <path>. Do NOT change product code.

THE FULL GATE HAS ALREADY PASSED at <sha>: `GATE: PASS profile=full`, exit 0.
Its logs are in baton-runner/<run-id>/gate-phase-<N>-close/ and its stdout in
gate-stdout.log. DO NOT re-run the gate under any profile — it takes 10-20
minutes, it cannot finish inside your Bash ceiling, and it has already answered.
Read the logs if you need detail.

1. Re-verify each acceptance criterion against the tree AS IT NOW STANDS, after
   the review fixes. The criteria: <criteria list>. A criterion that the fixes
   changed the shape of still has to be met.
2. Write the durable review record to docs/reviews/<YYYY-MM-DD>-dw-review-<slug>.md
   from TWO files, in the shape described below under "The review record":
     baton-runner/<run-id>/review-phase-<N>-dw.json   — the findings and the
       skeptic's verdict, refutations, wrong claims and residual risk;
     baton-runner/<run-id>/fixer-phase-<N>.json       — each finding's
       adjudicated verdict, its evidence, what the writer applied or skipped.
   Name the exact sha. EVERY confirmed finding gets a disposition line; a
   finding present in the review JSON and absent from the record is a
   VERDICT: ISSUES, and so is a BEFORE-MERGE one the fixer left `unresolved`
   or `skipped`. A non-before-merge one gets its line and the run carries on.
   You both write and check this record, so report the number of `### F<n>`
   disposition headings you wrote in NOTES as `dispositions=<n>`.
   Copy the skeptic's summary and the residual-risk list VERBATIM — they are
   the two things a summary destroys.
3. Write the phase-exit digest to baton-runner/<run-id>/digest-phase-<N>.md —
   <=40 lines, terse: the public surface this phase added (modules + key
   signatures) and the decisions and conventions the NEXT phase must honor.
   It is the only context the next phase's work unit gets.
4. Grep the phase diff for what baton-runner/<run-id>/house-rules.md bans —
   finding-fixer's Step 4 asks for that grep and the manager cannot run it. A
   real violation is VERDICT: ISSUES; the rule quoted in a test or a doc is not.
5. Write a closing baton.

RETURN: the STATUS line, then `VERDICT: CLEAN | ISSUES`, then BATON + NOTES.
<REPO GOTCHAS> <CONTAINMENT CONTRACT (no product-code edits)> <RETURN CONTRACT>
```

## The review record

Written by the **closing unit**, from `review-phase-<N>-dw.json` and
`fixer-phase-<N>.json`, to `docs/reviews/<YYYY-MM-DD>-dw-review-<slug>.md`. It is
the durable artifact; both JSONs are run bookkeeping. Shape:

| Section | Content |
|---|---|
| `# dw-review — \`<branch>\` (<what it is>)` | title |
| Header bullets | **Target** (branch + what + issue link + what it is stacked on) · **Commit reviewed** (the full `sha`, not the branch name) · **Date** and skill, with the workflow run id · **Lanes** (per-lens raw counts, merges, confirmed count) · **Disposition** (what was applied, what was deferred and why) |
| `## Verdict: <verdict>` | the skeptic's `summary` **verbatim**, in quotes |
| `## Confirmed findings` | one `### <F<n>> <SEVERITY> — <title>` per confirmed finding, most severe first; the `location` line; the failure path in prose; then its disposition from the fixer JSON — **`**Applied:**`** what changed, from the writer's `summary` · **`**Overturned (refuted \| already-handled):**`** the adjudicator's quoted evidence · **`**Annotated (real-but-decided-elsewhere):**`** the risk, the decision that owns it, and who owns that · **`**Open (unresolved \| skipped):**`** what is still missing |
| `## What the fixes now reject` | every adjudicator `rejectsValidInput` answer that is not "none", with the document that teaches a human to produce that input. All-"none" still gets the heading and a sentence — the question was asked and answered. Nothing in the fixer run executes a rejected input, so these are claims the full gate has not contradicted, not test results — say so |
| `## Refuted: <n>` | each refuted title + the skeptic's reason; `0` still gets the heading and a sentence |
| `## Checked claims that were wrong: <n>` | `checkedClaimsThatAreWrong`; `0` means the skeptic looked and they held — say that |
| `## Residual risk (…verbatim)` | `residualRisk`, in the lanes' own words, not summarized |
| `## Verification after the fixes` | the fixer's `verification` output verbatim, then the full gate's `GATE:` line and sha |

The empty lists are not optional. A record with no `Refuted` and no
`Residual risk` heading reads as "this diff is clean" when what happened was
"three lenses found nothing there".

## Failure handling

Unchanged from `baton-runner` — preserve everything (no autonomous `git reset`,
branch deletion or force-anything), write a failure baton, **copy it into the primary
checkout's `baton-pass/` before any `git worktree remove`** (the directory is gitignored,
so removal deletes it silently), and offer the user three choices: **guide & resume**
/ **waive & proceed** / **abandon**. Act only on their pick.

Managed-specific additions:

- **Skeptic verdict `BLOCK`**, or `MERGE-WITH-FIXES` with a before-merge item
  `finding-fixer` left `unresolved` / `real-but-decided-elsewhere` / `skipped`
  → PAUSE. Never waive on your own.
- **Closing unit `VERDICT: ISSUES`** → PAUSE with its baton; the phase is not
  CLEAN even though the gate passed.
- **The review JSON is the fixer's only scope.** If it was not persisted, do not
  launch `finding-fixer` from your own memory of the summary — re-run the
  extractor, or resume the workflow with
  `Workflow({ scriptPath, resumeFromRunId })`, which returns finished agents from
  cache. The same applies in reverse: the closing unit cannot write the record
  without `fixer-phase-<N>.json`.
- **A `finding-fixer` adjudicator that returns nothing** leaves its whole group
  unruled, and the script logs it as `INCOMPLETE: k/n adjudicator(s) returned
  nothing`. Those findings are still open — resume the run, never treat the
  missing verdicts as refutations.
- **A unit that returns early cannot be continued** — `SendMessage` may not be
  loaded. Spawn a fresh unit seeded from its baton path instead, and count it.
- **`baton-pass/INDEX.md` is not a containment breach.** The `baton-pass` skill
  regenerates that index, and units have been observed running `git add` and
  `git checkout --` on it. Neither changes a ref or a commit. Log the touch and
  carry on; do not PAUSE. Anything else mutating git still pauses.

## Fatal errors (→ PAUSE; `PAUSED`, or `FAILED` if unrecoverable)

- A required skill (`baton-pass`, `addyosmani-test-driven-development`,
  `dw-review`, `finding-fixer`) or `scripts/gate.sh` is
  missing in the worktree.
- Docker is unavailable when the full gate is due.
- Test infrastructure cannot run at all (not "tests fail" — that is normal work).
- A unit returns `FATAL`, or `INCOMPLETE` ≥3× with no NOTES progress.
- The full gate cannot reach exit 0 within the per-phase thrash alarm.
- The Workflow returns `NO-FINDINGS` and the scope check shows the lanes saw an
  empty diff.
- A global or per-phase budget ceiling is hit.
- `gh pr create` fails, or a merge/rebase conflict needs non-mechanical judgment.
- Any unit reports it must act outside the containment contract.

On fatal: set `STATE = PAUSED` (or `FAILED`), record the reason and the exact
resume point, show the user, and stop. Resuming re-reads `STATE.md`.

## Merging the stack afterwards (the user's step, for the final summary)

Squash merges rewrite each phase's sha, so after merging phase N:

```bash
git rebase --onto origin/main "feat/$RUN_ID/phase-$N" "feat/$RUN_ID/phase-$((N+1))"
git diff --stat "$OLD_TIP" "$NEW_TIP"   # must be EMPTY: identical tree => the gate and review still hold
git push --force-with-lease
gh pr edit "$NEXT_PR" --base main
```

Then delete phase N's local and remote branches. If that `diff --stat` is not
empty, the rebase changed the tree and the downstream phase's gate result no
longer describes what will merge.
