---
name: dw-review-codex
description: Review a committed PR or branch with Codex native subagents, independent specialist lanes, and an adversarial skeptic before reporting findings.
---

# dw-review-codex

## `-h` / `--help`

If the trimmed argument is exactly `-h`, `--help`, or `help` (case-insensitive),
output only this help section and stop:

> Review a committed PR or branch with two or three parallel Codex subagents,
> followed by one skeptic if any lane finds a defect. Target: `pr <N>`, a branch,
> or the current branch. The review is read-only and reports in chat. An
> unchecked-out target may need a temporary git worktree. Lanes also return the
> questions only the author can answer; any left pending caps the verdict at
> merge-with-fixes until each is answered, filed, or declined. No PR comment or
> repository report is published without a separate request.

Use this skill only where Codex native subagent dispatch and waiting are available.
Invoking it authorizes up to three reviewer agents and one skeptic. If those
tools are unavailable, say the workflow cannot run; do not present a solo
review or a `codex review` CLI run as this workflow.

## 1. Freeze the review scope

Accept `pr <N>`, a branch, or no target (current branch). Review committed
changes only. From the primary checkout, identify the actual base branch from
the PR metadata or repository default, then verify it against the user's
target; do not infer it merely from a local `main` or `develop` branch. Fetch
the base and target when a remote is available. For an unchecked-out target,
create a detached worktree at the target commit and read its path back from
`git worktree list`. Reuse an existing worktree only if it holds that commit.

Record the absolute worktree path, base commit SHA, target commit SHA, and
three-dot diff `BASE_SHA...TARGET_SHA`. Require the target worktree's `HEAD`
to equal the recorded target SHA, no tracked changes (`git status --porcelain
--untracked-files=no`), and a successful, nonempty `git diff --stat
BASE_SHA...TARGET_SHA`. Stop before dispatch if any check fails or the base is
uncertain. Never substitute a two-dot diff or silently review the current
checkout. Read repository instructions, changed paths, and the diff to identify
change-specific invariants and effects that become hard to reverse at merge
(for example migrations, published APIs, or release versions).

## 2. Dispatch independent lanes

Choose two or three *distinct* angles from the diff, such as contract and
behavior, security and failure paths, data and concurrency, release wiring,
or tests. If tests changed, one lane must check whether each new test fails
when the behavior it claims to protect is removed. State the chosen lanes and
their focus before dispatch. Use available specialist agent types when they
fit; otherwise give a default agent a precise specialist brief. Dispatch the
lanes in parallel with native subagent tools, then wait for every result.

Give every lane the same absolute worktree path, base SHA, target SHA, relevant
repository invariants, and its own distinct questions. Require it to verify
`HEAD == TARGET_SHA` and the nonempty three-dot diff *before* reviewing. Each
lane is read-only: no edits, commits, pushes, or comments. It may run focused
checks that do not modify tracked files. Ask for findings with priority,
precise changed-line location, reproduction or reasoning, and merge impact;
also ask what it checked and what remains unexamined. Ask separately for its
open questions: decisions only the author can make (a scope call, an intent the
tree cannot settle, a dependency outside the diff). They are not findings and
not dropped; they are gated at merge exactly as a finding is. Report all
supported findings to the coordinator, including lower-severity ones; filter
and deduplicate during synthesis.

Treat a failed dispatch, missing scope verification, empty or wrong diff, or
missing lane result as **INCOMPLETE**, never as a clean review. Retry a failed
lane only while the recorded SHAs still match; otherwise stop and report the
gap. Recheck target HEAD and the diff before synthesis.

## 3. Challenge findings, then report

If any lane reports a candidate defect, send the *complete, deduplicated*
candidate set to one fresh skeptic agent. Give it the same pinned scope and
read-only rules. It must independently inspect code and tests, try to refute
each candidate, spot-check material claims that reviewers marked verified,
and classify each finding as confirmed, refuted, or unresolved with evidence.
Also give it every lane's open questions. For each one it tries to settle the
question from the tree: ANSWERED when the code or docs decide it (citing what it
read), else PENDING with what the author must decide. A statement inside the
diff under review never settles a question about that diff; ANSWERED needs a
source outside the changed hunks, such as base-branch docs, an ADR, or a test
that exercises it. It never declines one; that is the author's call, and it
returns every question it was given. While any question is PENDING the verdict is at most
MERGE-WITH-FIXES, whatever the skeptic wrote: the code can be right and the PR
still not mergeable. If the skeptic fails or scope drifts, report
**INCOMPLETE** and do not turn unverified candidates into confirmed findings.

If no lane finds anything, skip the skeptic and use **NO-FINDINGS**, not
`APPROVE`: there was no adversarial verification. Nobody tried to answer the
open questions either, so relay every one as PENDING. In every report name the
exact target and base SHAs, reviewed paths, lanes, checks, confirmed and
refuted findings, unresolved claims, open questions with their dispositions,
and residual risk. Open questions are a gate, not an appendix: while any is
PENDING say so in one line (`not merge-ready: <n> open questions pending`). In
the record the author replaces each PENDING with `ANSWERED - <one
sentence>[, <commit>]`, `FILED - #<issue>`, or `DECLINED - <one sentence why it
does not apply>`; the PR merges and its issue closes only when none is PENDING,
and a FILED issue carries that remainder. Label findings with the scale in
`refs/severity-scale.md` (CRITICAL / HIGH / MEDIUM / LOW, each shown with its
action, ids F1, F2, ...). Distinguish a before-merge blocker
from a follow-up issue, especially for irreversible changes. Findings must
point to actionable lines in the reviewed diff.

Report in chat by default. A PR comment or repository file is a separate
publication action: prepare its exact body and destination, then follow the
user's authorization and repository rules before writing. If a file is
requested, create it only on a feature branch in its own worktree. Do not
create both a PR comment and file unless explicitly requested.
