# Whole-codebase audit: slice plan

<!-- Angle-bracket slots are filled in. Comments like this one are instructions: follow them, then delete them. -->

**Written <<YYYY-MM-DD>>** against `<<remote/branch>>` @ `<<short SHA>>`. A plan plus a
baseline. Slice status lives in the tables below; each finished slice links its report.
Until they are committed, this plan and everything under `<<audit folder, from the repo
root>>/` exist only as untracked files in the worktree at `<<worktree path>>`, so that
worktree is never removed with `--force`. Commands written as `cleaver.py ...` are the
code-cleaver skill's helper script.

## Summary

- <<What the repo holds: each code tree with its measured code files and lines and the date
  of its last code change; anything that marks the project paused or archived. Test files
  and lines, measured.>>
- The audit is cut into **<<n>> slices by area**, not by audit type. <<Measured smallest
  and largest slice in code lines.>> Each slice gets the same seven-lens checklist, one
  findings report, and at most two fix PRs.
- In scope: <<paths>>. Left out, each with its reason, in the last slice table.
- Order is by what a bug costs: <<this repo's order, highest cost first>>.
- <<Either: n slices overlap open PRs, with the PR groups. Or: open PRs could not be read
  (the reason), so every In flight cell says unknown.>>
- The baseline and the tracer slice (<<id>>) run first. The tracer covers the review step
  only: triage, the fix PRs and the done check have not been run on any slice.

## Decided

Three answers from the repo owner on <<YYYY-MM-DD>>. Later stages reproduce them.

1. **When reports are committed:** <<option chosen, and any note the owner typed>>.
2. **What an open finding blocks:** <<option chosen, naming this repo's release steps, or
   that none was found>>.
3. **Which slices are refuted:** <<option chosen, with the slice ids it selects>>.

## What every slice checks

The seven lenses in [the checklist](<<audit folder, relative to this file>>/checklist.md):
number safety, correctness, accuracy, security, what a user touches, simplification, tests.
The checklist is what reviewers receive, so a lens is changed there and nowhere else.

## What every slice produces

- **Report:** `<<audit folder, from the repo root>>/<slice-id>-<name>.md`, committed as
  answer 1 says, in the form the checklist's `How to report` sets: lens, severity,
  `file:line`, evidence and a proposed fix for every finding. The report is the tool's
  merged synthesis: duplicates are folded into one row and nothing is dropped for being
  minor.
- **Fix PRs, after triage.** Triage confirms each finding's severity and decides whether it
  is fixed or stays, with the reason. Then at most two per slice, each on its own branch:
  `fix/audit-<slice-id>-behaviour` and `fix/audit-<slice-id>-simplify`.
  - *Behaviour fixes* (lenses 1 to 5, and tests missing under lens 7), each with a test that
    fails before the fix. The PR description quotes that failing run, or says why no test
    can fail first.
  - *Simplification* (lens 6), behaviour-preserving, tests green before and after. Where no
    test pins the code, that test comes first, in the behaviour PR. A change that alters
    output is a behaviour fix.
  - Each PR lists its exact files, which may sit outside the slice, and the open PRs that
    touch them, and waits for confirmation before the first edit.
- **Done when:** every CRITICAL and HIGH is fixed or has a written reason it stays, and the
  gates in the Baseline pass for the code the fix touched: <<the gate commands by their
  Baseline number, with any coverage floor>>. A gate that is red in the Baseline is fixed as
  its own step first, because no fix can show it green until then.

**What an open finding blocks.** <<Answer 2 written as a rule.>>

## How a slice is run

- One slice is one `zord-multi-agent-review` run on **one or two directories**: `dir` for
  one, `slices` for two. The tool runs the whole roster once per directory and hard-fails
  when roster times directories passes <<limit>>, and its automatic roster is <<seats>>
  seats. A directory with more than <<file cap>> tracked files passes `--max-files <n>`.
  These are the tool's own figures, version <<version, and whether checked against the
  installed copy>>. A smaller named roster fits more directories; that trade is the owner's
  (see Open questions).
- A slice's files that sit outside its directories (an entry-point file, a build file) are
  named in its checklist's `This run` block, and reviewers are told to read them. This
  delivery is unproven until a report's coverage notes list those files as read.
- Every run passes `--prompt-prelude` (the slice's own copy of the checklist, `This run`
  filled in), `--write-to` (the report path) and `--high-cap off`, as absolute paths inside
  the audit worktree. The cap is off because "every HIGH fixed" needs the uncapped list. The
  roster stays automatic; `--reviewers` replaces the whole roster, so it is passed only with
  every seat listed.
- **Refutation.** Slices marked `yes` under Refuted run with `--adversarial`. The tool's
  help puts that at about <<multiple>> times a run's token cost; it is not measured here. Findings
  its refuter budget does not reach come back UNVERIFIED and are recorded that way.
- Every slice audits a worktree cut from `<<remote/branch>>`, and its report records the
  SHA it audited.

## Slices

Slice ids are one to three capital letters and a number (`A1`, `M6`). `Paths` are from the
repo root, each in backticks; a slice's extra files are listed there too. `Run` is the
target and any `--max-files`. `In flight` names the open PRs that change files in the slice.
A defect caused by another slice's file is passed to the slice that owns the file and
reported once, there. <<Where this repo's tests live and how each slice finds its own.>>

### Phase 0: baseline

| ID | Slice | Paths | Status |
|---|---|---|---|
| S0 | Mechanical baseline | whole repo | <<Run, see Baseline below. Or what was not run.>> |

### Phase <<n>>: <<name>>

| ID | Slice | Paths | Code files | Code lines | Run | In flight | Refuted | Status |
|---|---|---|---|---|---|---|---|---|
| <<A1>> | <<name>> | `<<dir>>` | <<n>> | <<n>> | <<dir, or slices; --max-files n>> | <<PRs, none, unknown>> | <<yes or no>> | |

**Checkpoint:** <<what is looked at before the next phase starts.>>

<!-- One table per phase, highest cost first. One slice is platform and supply chain: its Paths are the build, dependency, container and CI files and directories no code slice covers, its Code lines cell is n/a, and it is sized by tracked files. -->

### Left out

| ID | Tree | Paths | Code files | Code lines | Why |
|---|---|---|---|---|---|
| <<X1>> | <<name>> | `<<dir>>` | <<n>> | <<n>> | <<vendored copy, generated, tooling, dormant: and who decides>> |

## Tracer result

<<Filled by the tracer stage. Why this slice was the tracer. The run exactly as invoked,
wall-clock minutes, the token figure the tool reported and what it does or does not cover,
the finding counts, each CRITICAL and HIGH with whether its cited lines say what the finding
says, whether lens tags came through and extra files were read, what the report's own audit
section raised. No total is extrapolated to the slices that remain.>>

## Baseline (slice S0)

Run <<YYYY-MM-DD>> on `<<short SHA>>`. These are leads for the slices named, not findings.
`Cmd` is a number in the command list under the table.

| Check | Cmd | Result | Goes to |
|---|---|---|---|
| <<analyzer or linter>> | 1 | <<exit code and issue count, or not run: reason>> | |
| <<test suite>> | 2 | <<passed, failed, skipped, the runner's own clock>> | |
| <<coverage>> | 3 | <<percent, lines hit of total, the repo's floor if it has one>> | <<lowest-covered areas, to lens 7 of their slices>> |
| Secret-shaped strings | 4 | <<kinds and file:line, or nothing matched>> | <<platform slice>> |
| <<lead scan>> | 5 | <<count, and what the pattern over- or under-counts>> | <<slice or lens>> |

```
1. <<command, exactly as run>>
2. <<command>>
3. <<command>>
4. cleaver.py secrets
5. <<command>>
```

**Red at baseline on `<<short SHA>>`.** <<Each failing test with its file, name and the
assertion that fails, and each other gate that is red, with the cause where a log shows it
and the tracking issue if one exists. These are fixed as their own step before the first
fix PR. If every gate is green, say so in one line.>>

## Risks

| Risk | Mitigation |
|---|---|
| A fix PR collides with an open PR. `In flight` covers a slice's audit paths, not the files its fixes touch | Each fix PR checks its own file list against the open PRs before it is confirmed |
| Code changes after its slice is audited | Each report records the SHA it audited |
| Reviewers report less when told to be conservative | Reviewers are asked for everything; severity is applied afterwards |
| <<repo-specific risk>> | <<mitigation>> |

## Open questions

<!-- Every decision met along the way that the three answers do not settle, one bullet each, written so the owner can answer it without opening another file. Keep the three below if they apply. -->

- When is this plan itself committed, and how does a report reach its fix PR's branch?
- Does a slice ever run with a smaller named roster so it can span more than two
  directories, and which seats stay?
- <<question>>
