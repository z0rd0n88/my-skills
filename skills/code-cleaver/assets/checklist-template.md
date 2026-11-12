# Audit checklist: read before reviewing any slice

This review is one slice of a whole-codebase audit (`<<plan path, from the repo root>>`).
Leave every tracked file as it is. Running the repo's tests is expected, and the ignored
build output that creates is fine. A script or test written to reproduce a finding goes in
the session scratchpad outside the repository, and the finding says it was run.

## This run

- Slice: <<id and name>>. Audited commit: <<full SHA>>.
- Also in this slice, outside the directory you were handed: <<each extra file by path, or
  none>>. Read each in full and review it with the slice.
- Tests that cover this slice: <<test files or directories, by path>>.
- Open PRs that touch this slice: <<list, none, or unknown>>.
- A defect outside the slice is still reported, marked out of slice with its path.

## The code

<!-- Fill every bullet from the repo itself. Delete a bullet that does not apply, and delete these comments. -->

- <<What the software is and who or what uses it, in two sentences.>>
- <<Run modes, and what differs between them: which are live, which read fixtures or mocks,
  which flag or variable switches them. Say which mode a finding applies to.>>
- <<Anything the code talks to whose version matters, and where that version is pinned. If
  nothing is pinned: a finding that turns on what the other side does is marked unverified.>>
- Repo rules: <<each rule file with the one-line rule it sets>>. Read the parts that bear on
  your role.
- Already tracked, so not re-reported: <<open issues or earlier findings that cover this
  code, or none found>>.
- Tests live in <<test locations>> and run with <<command>>. Ignore test tools your role
  definition names that this repo does not use.
- <<Test status, one of three. Red: "N tests fail on the audited commit before any slice
  is touched; the audit plan's Baseline lists them. A failure on that list is known: say
  whether your slice's code causes it. A failure not on the list is a finding." Green: "The
  suite is green on the audited commit, so any failure you see is a finding." Not run: "The
  suite was not run for the baseline, because REASON, so say whether each failure you see
  is caused by your slice's code.">>

## What to look for

Report through your own role first. Then report anything you see under these seven lenses,
even where it falls outside your role:

1. **Number safety.** A float holding money, a quantity or a rate; rounding direction;
   truncation; overflow; division by zero; sign errors; units confused (percent, basis
   points, fraction; seconds, milliseconds); time zones; parse and format that do not
   round-trip; a value compared after formatting. <<Repo rule, with its file, or delete.>>
2. **Correctness.** Wrong logic, wrong state transition, a race, use after release, a null
   path, a swallowed exception, an action a retry or double submit runs twice.
   <<Repo rule, with its file, or delete.>>
3. **Accuracy.** An output that differs from its source; a label or message that claims
   more than the code delivers; made-up data; a fixture a live run can show; a doc comment
   the code contradicts. <<Repo rule or product ban, with its file, or delete.>>
4. **Security.** A secret in source; key material, tokens or personal data in logs;
   sensitive data outside secure storage; an irreversible action taken without showing what
   it does; unvalidated input at a trust boundary; a token kept, cached or passed on where
   it should not be; unsafe URL handling, including plain `http` and a skipped TLS or
   host-key check. <<Repo rule, with its file, or delete.>>
5. **What a user touches.** <<Write this lens for what this code presents. Screens: a
   missing loading, empty, error or stale state, plus the repo's UI standard. A CLI or
   script: exit codes, messages the caller can act on, behaviour on bad input. An API or
   service: status codes, error bodies, timeouts, what a caller sees when a dependency is
   down. A bot or agent: what it says when it cannot do what was asked.>>
6. **Simplification.** Dead code, duplicated logic, an abstraction with one user,
   hand-written code the standard library or an existing helper already covers.
   <<Repo rule, with its file, or delete.>>
7. **Tests.** A critical path or state transition with no test; a test that asserts only
   that code runs; a weak matcher standing in for a real check; a test that pins wrong
   behaviour; a test the slice's code has left red. <<Repo rule, with its file, or delete.>>

## How to report

- Report every finding you can support, at every severity. Keep distinct findings
  separate. Severity is applied to the finished list, so a finding you leave out is lost.
- Severity: CRITICAL is a security vulnerability or data-loss risk; HIGH a bug or
  significant quality issue; MEDIUM a maintainability concern; LOW style or a minor
  suggestion.
- Each finding names `file:line`, quotes the lines it rests on, says what goes wrong and
  for whom, and proposes the smallest fix. A secret, token or key material is named by
  `file:line` and kind, and its value is left out.
- Say which lens each finding belongs to.
- If a lens has nothing to report in this slice, say so in one line. Silence reads as
  "not checked".
- Mark anything you could not verify from the code as unverified, and say what would
  verify it.
- In your coverage notes, list the files you read, including the extra files named under
  This run.
- Synthesizer: keep each finding's lens in its row (start the one-line description with
  `Lens N:`), and end the Coverage Report with one line for each lens that had nothing to
  report.
