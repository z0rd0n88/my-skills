# PR fix cycles

Load this file only for a looping `pr` invocation of
[multi-agent-review-codex](../SKILL.md). Use the calling Codex agent as the
coordinator and sole source writer. Every reviewer, refuter, verifier, and
auditor remains read-only. Do not invoke another fixing loop from this one.

## Establish authority and the branch

Honor an explicit request to review without changes by selecting one-shot
mode. A request to run this skill's PR loop or to fix the PR authorizes its
in-scope fixes, commits, and pushes, subject to repository and user boundaries.
Explain the concrete scope and obtain missing authorization before mutation
if the request does not establish it; do not ask again for an already
authorized action. `--yes` skips this skill's optional confirmation, never a
repository or host gate. When unattended fixes are requested without
`--adversarial`, note once that fixes will act on findings without refutation.

Require an open PR and a dedicated feature worktree on its exact head branch.
Require a clean initial tree and local HEAD equal to the recorded remote head.
Resolve repository identity as well as the branch name. Use an existing
matching worktree or create one when authorized by the task; never reset,
clean, or overwrite unrelated work. Keep a ledger of starting head, requested
review slots, finding IDs and dispositions, tests, and resulting head for each
cycle. A changed remote head stops the run before further writes.

## Review and decide

Run the one-pass procedure in SKILL.md from the caller. Dispatch fresh
reviewers for each pass and reconcile every required response before triage.
Keep the caller's roster, prelude, refutation, and audit settings throughout
the run. Force the HIGH cap off, with a warning if a numeric cap was supplied.
Suppress per-pass report files and PR comments; the final report is written
and published once according to the caller's output settings.

Stop with INCOMPLETE before applying any fix if a required reviewer is
missing, the snapshot changed, or required refutation cannot complete. Do not
substitute a solo pass to keep a loop moving. Keep uncertain, contested, and
unverified claims visible, with their original severity and evidence limits.

Validate claims against the snapshot. Address CRITICAL/HIGH; select MEDIUM
fixes by evidence and scope, and normally defer LOW. With
`--high-and-up-only`, defer both MEDIUM and LOW. Record an explicit disposition
for every finding, including dropped/refuted claims. A label is not proof:
do not implement an unsupported finding merely because it is HIGH.

## Apply, verify, and publish the branch

Apply selected fixes serially in the caller. Follow repository scope rules
and name exact additional paths if the change would exceed authorization.
Run verification that exercises the changed behavior. For each fix, send the
original claim, final diff, relevant source, and test evidence to an independent
read-only verifier. Require a verdict and evidence, not an applier's assurance.
Leave uncertain or failed fixes open; do not commit or push them as verified.
Run the project's relevant smoke test only when a changed path is covered,
unless `--no-smoke` was requested. Never claim skipped checks passed.

Recheck local and remote heads before committing and pushing. Stage only
intended paths, excluding report artifacts that have not been finalized.
Commit and push verified fixes only under the established authority. Stop on
a concurrent update; never force-push over it. Record the resulting remote SHA
and run a post-fix review at that exact SHA.

## Count cycles and stop accurately

`--max-iterations` caps **fix cycles**, not review passes. The default of one
means: initial review, at most one batch of fixes, and a post-fix review if
that batch was committed. A clean initial review needs no fix or extra pass.
At the cap, finish the post-fix review but start no further fix cycle. This is
an explicit Codex behavior; the Claude variant described in PR #190 counts
rounds differently and may finish its default round without a re-review.

After fixes, rotate the review shape to check cross-axis contradictions or
analogous sites. Preserve explicit reviewer selections; change their brief's
evidence focus rather than silently replacing the requested roster. Include
findings in the ledger, but never ask reviewers to ignore a whole function or
file merely because it was edited. A verified claim is bound to the examined
head; a later commit requires rechecking assumptions before treating it as
settled.

Use these outcomes:

- APPROVE: complete review at the final head, no unresolved CRITICAL/HIGH or
  selected-for-fix finding, and required verification passed. List deferred
  MEDIUM/LOW and unperformed advisory audits explicitly.
- STOPPED: repeated unresolved claim, failed test/verifier, incomplete
  coverage, missing authorization, concurrent change, or exhausted fix budget
  with a blocking finding. Include the exact reason and remaining IDs.
- STALE: reviewed material changed; do not publish the result as current.

This skill does not resume saved checkpoints. Reject `--resume-stopped` and
require a new explicitly requested run after a stop is resolved; never make
the reset an automatic way around a safety stop.

Include per-cycle heads, dispositions, tests, verification evidence, coverage,
and the stop reason in the final report. Recheck the remote head before the
single final PR comment. Update this run's existing comment if publication is
retried. Apply `--no-write` and `--no-comment` independently.
