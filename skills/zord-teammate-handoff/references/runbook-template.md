# Runbook template

The section shape of a runbook a teammate's Claude runs unattended. Two kinds of slot:

- `{{slot}}` is filled by the author while writing (repo, default branch, gate command, piece
  table). None survives into the delivered runbook.
- `N`, `PR`, `BRANCH`, `NEXT_PR` and `<...>` are the runner's placeholders. They stay in
  the delivered runbook and are defined once, in the "Substitute before running" sentence.

Rules D4 (every Expected pasted from a live run, or marked not run) and D8 (platform markers,
with the executor's equivalent beside a step only another platform can run) bind every block.

The text below is the skeleton with the generic commands already in it; Phase 3 of the skill
says how to fill it.

---

# {{Title: the job in one line}}

Written {{date}} for a teammate on a {{platform}} with Claude Code installed and no custom skills.
Every command below runs in a plain terminal or is a prompt to paste into Claude Code; nothing
needs a plugin, a hook, or a skill.

## Summary

{{What the pieces are, where they came from, what "done" means.}} The job: {{review each piece in
order, fix what the review finds, mark it ready, merge it with a merge commit, then move to the
next piece}}. The run is unattended; the owner reads the ledger at the end. "Unattended run" at
the bottom has the prompt to paste and the conditions that stop the run early.

- Time: {{per-piece estimate and what drives it}}.
- {{What this job never touches: devices, dashboards, release builds, other repos.}}
- The pieces merge with **merge commits**, not squashes, so no rebases and no force-pushes.
  After each merge GitHub retargets the next PR to `{{default branch}}` by itself, because the head branch
  is deleted.
- {{CI status: "The repo has no CI; green means the local gate passed on your machine", or the
  check names the executor waits for.}}

## Facts that shape every step

| Fact | What it means for you |
|---|---|
| Each PR's base is the previous piece's branch; the first piece targets `{{default branch}}`. | GitHub shows every piece as `MERGEABLE` into its base, so `gh pr merge` on piece 2 before piece 1 lands merges it into piece 1's branch, not into `{{default branch}}`, and nothing refuses it. Review and merge in order, never out of order. |
| `{{gate script path}}` runs {{what it runs}}. | {{What the gate's output shape is and which failure, if any, is expected by design.}} |
| A fix committed on piece N reaches `{{default branch}}` through N's merge, but piece N+1's branch still has the old code until `{{default branch}}` is merged into it. | Loop step 1 merges `origin/{{default branch}}` into every piece before its gate runs, so the gate tests what `{{default branch}}` will become. |
| All pieces were opened by `{{author login}}`. GitHub does not let an author approve their own PR. | The reviewer running this plan is the GitHub approver. The owner authorised the merges up front ({{date}}) and reads the ledger afterwards. |
| `deleteBranchOnMerge` is {{on/off}} in repo settings. | Always merge with `--delete-branch`; GitHub retargets the next PR to `{{default branch}}` only when the head branch is deleted. |
| `{{default branch}}` keeps moving under the stack and changes files the stack also changes, so a clean merge is proved by a command, not by this table. | No rebase. Task 0 step 2 proves every piece still merges clean; loop step 1 does the real merge. If a merge conflicts, see "If something goes wrong". |

The pieces, bottom to top:

| Piece | PR | Head branch | Size | Read first (from the PR body) |
|---|---|---|---|---|
| 1/{{K}} | #{{n}} | `{{branch}}` | +{{a}}/-{{d}}, {{f}} files | `{{full paths from the repo root}}` |

{{Pointers to the design the pieces implement, with the branch each pointer is on.}}

---

## Task 0: Set up the machine (once)

- [ ] **Step 1: Tools.** Run each; the expected line follows.

```bash
{{tool}} --version
```
Expected: {{the version line's shape and the floor, with the file that pins it}}.

<!-- platform: mac -->
```bash
{{mac-only tool check}}
```
Expected: {{the real row shape}}.
<!-- /platform -->

```bash
gh auth status
```
Expected: logged in to github.com. Then prove the account can push:

```bash
gh api repos/{{owner}}/{{repo}} --jq .permissions.push
```
Expected: `true`. `false` is read access only: stop and ask the owner for write access.

- [ ] **Step 2: Prove the baseline is green.** (Clone first if you have not:
`git clone git@github.com:{{owner}}/{{repo}}.git`.) From the repo root. A relaunch is any run
after a crash or after the owner cleared a stop; every "relaunch" sentence below means both. If
the previous attempt left a merge in progress (`git status` says "You have unmerged paths"), run
`git merge --abort` first; loop step 1 redoes that merge. If it left uncommitted edits from step 5
(`git status` lists modified files on a piece branch), run
`git stash push -u -m crashed-step-5 -- {{paths the pieces touch}}` (the pathspec keeps
`{{ledger file}}` out of the stash); the review at step 5 finds the same thing again:

```bash
git fetch --prune origin && git checkout {{default branch}} && git pull --ff-only
{{the gate and every check the gate does not run}}
```
Expected: {{the live output}}. Note each test count: loop step 3 checks it never shrinks.

Then prove every piece still merges clean into `{{default branch}}` (loop step 1 does the real merge):

```bash
for b in {{branch suffixes}}; do git rev-parse -q --verify origin/{{branch prefix}}$b >/dev/null || { echo "$b merged"; continue; }; git merge-tree --write-tree origin/{{default branch}} origin/{{branch prefix}}$b >/dev/null && echo "$b clean" || echo "$b not clean"; done
```
Expected: one `clean` line per piece. On a relaunch, every piece already merged prints `merged`
instead (its branch was deleted by the merge; `clean` if a crash left the branch): not a stop. A
`not clean` line has two causes:
`git --version` older than 2.38 (no `--write-tree`; update git and re-run), or a real conflict
ahead at that piece's loop step 1. Whether a real conflict is foreign is read from GitHub, not
from these lines: `gh pr view {{first PR}} --json state --jq .state` printing anything but
`MERGED` means nothing of this run is on `{{default branch}}` yet, so the conflict is foreign: stop.
`MERGED` means it is decided at that piece's loop step 1 by the conflict rule under "If something
goes wrong".

- [ ] **Step 3: Read, in this order:** {{the repo's always-loaded rules, the constraints file, the
source PR or issue body}}.

- [ ] **Step 4: Confirm the stack looks like the table above, and find where the run starts.**

```bash
gh pr list --state open --limit 100 --json number,isDraft,baseRefName,headRefName --jq '.[] | "\(.number)\t\(.isDraft)\t\(.baseRefName) <- \(.headRefName)"' | sort -n
```
Expected: one line per open PR (number, draft flag, `base <- head`). On a fresh run the pieces
print `true` with bases chained as in the table. On a relaunch, any merged piece is gone, the
first `OPEN` piece's base is `{{default branch}}` (or its predecessor's branch until loop step 1 fixes it)
and it may print `false`: the resume check below decides, not this listing. Other open PRs print
too (this plan's own PR while it is open); they are other work, ignore them.

The resume check. Its answer, read from GitHub and never from a file on disk, says where the run
starts, so a relaunch lands on the right piece:

```bash
for PR in {{PR numbers}}; do gh pr view $PR --json number,state,isDraft,mergedAt --jq '"\(.number) \(.state) draft=\(.isDraft) merged=\(.mergedAt)"'; done
for PR in {{PR numbers}}; do printf '%s ' "$PR"; gh api repos/{{owner}}/{{repo}}/pulls/$PR --jq '.stack == null'; done
```
Expected on a fresh run: one `OPEN draft=true merged=null` line per piece, then one `true` line
per piece. The second loop says none of the PRs is a GitHub stack, which `gh pr merge` cannot
land (GitHub adds a `stack` field to a PR only once it is in one): any `false` is a stop.
Read the first loop top down: every `MERGED` piece is done, skip its loop but make sure
`{{ledger file}}` has its row (loop step 8 writes it; a crash after the merge can leave it out,
so run step 8's two `printf` lines for that piece, header first, with the cells still in `<...>`
taken from that PR's step 6 comment, `gh pr view PR --comments`); the first `OPEN` piece is where
the loop starts; if that piece is `draft=false`, a previous attempt crashed between loop steps 6
and 7, so run steps 1 to {{last check step}} again and, when they are green, run step 6's last
line: `approvals=0` means the approve line never landed, run it; then go on from step 7 (not
green: a step 5 finding, then a follow-up to step 6's comment). `CLOSED` with `merged=null`, or a
`MERGED` piece above an `OPEN` one, is a stop. All pieces `MERGED`: go to Task 9.

---

## Tasks 1 to {{K}}: the per-piece loop

Run this loop once per piece, N = 1 to {{K}}, in order. Do not start piece N+1 until piece N is
merged. Substitute before running: `N` is the piece number (1 to {{K}}), `PR` the PR number from
the table, `BRANCH` its head branch, `NEXT_PR` the PR number of piece N+1 (none after the last
piece){{, any platform placeholder such as a simulator id, defined by its shape}}. Fill every
`<...>` field before running.

- [ ] **Step 1: Check out the piece, bring `{{default branch}}` into it, confirm it is mergeable.**
{{If a repo hook forbids edits outside a worktree (rule A12): the second line below becomes the
repo's worktree command for `BRANCH` followed by a `cd` into it, the hook is named here, the ledger
file path is absolute in the primary clone, and Task 9 step 2 runs from the primary clone. Delete
this slot otherwise.}}

```bash
git fetch --prune origin
git checkout BRANCH && git pull --ff-only
git merge --no-edit origin/{{default branch}} && git push
gh pr view PR --json baseRefName,isDraft,mergeable --jq '"\(.baseRefName) draft=\(.isDraft) \(.mergeable)"'
```
Expected: the merge is clean (Task 0 step 2 proved it before any fix landed) and pushes one merge
commit, or says "Already up to date" and pushes nothing. Then: base is `{{default branch}}` (piece 1, and
every later piece after its predecessor merged), `draft=true` (`false` once step 6 has run: on
step 7's `base moved` repeat and on the crash-between-6-and-7 relaunch Task 0 step 4 names),
`MERGEABLE`. A base that still names the previous piece's branch means that merge's branch
delete or retarget did not happen (a crash, or the fallback merge): `gh pr edit PR --base {{default branch}}`
and re-run this line. `UNKNOWN` means GitHub has not computed it yet: wait a minute and re-run,
up to five times (still `UNKNOWN` after that is a stop). The merge can conflict when a fix on an
earlier piece touched a file this piece also changes ({{the files most pieces share}}): see "If
something goes wrong". Never skip the merge: it is what makes the gate test the code `{{default branch}}`
will actually contain after this piece lands, fixes from earlier pieces included.

- [ ] **Step 2: Run the gate.**

```bash
{{gate command with a per-PR log dir}}
```
Expected: {{the gate's full output, header lines included, pasted from a live run}}. Any other
failure is a real finding: on piece 1 fix it in step 5; on later pieces first apply "Piece N+1's
step 2 fails after a clean step 1" under "If something goes wrong". The gate can outrun Claude
Code's default timeout for a foreground command (two minutes; the launch line at the bottom
raises it to 30 minutes). A result that says the command was moved to the background, timed out
or was stopped is not a gate result and not a fix attempt. A call moved to the background is
still running: never start the gate again while it is. Read the Bash tool's own output file (the
one the result names, not the gate's per-check logs) until its last line is the gate's verdict
line (the file is quiet while the tests run, so quiet is not stuck). If it has no verdict line 30
minutes after the move (wait with one `sleep 1740` Bash call, then read), stop that background
task (TaskStop, with the id the moved-to-background result gave), run the gate once more, and
treat a second run with no verdict line 30 minutes after its move as a hang: a finding for step 5.

- [ ] **Step 3: The checks the gate does not run.**

```bash
{{guard script, second suite, anything the gate skips}}
```
Expected: {{live output}}. A test count may grow when `{{default branch}}` adds tests (step 1 merges
`{{default branch}}` in) and must never shrink below Task 0's.

<!-- platform: mac -->
- [ ] **Step 3b: {{Platform-only smoke}}.** {{What it proves and why it needs no secrets.}} Run
the long line as one Bash call with `timeout` 1800000 (30 minutes).

```bash
{{the smoke, ending in a positive grep whose Expected is 1 and an exception grep, each with || true}}
```
Expected: {{live shape}}; the two `grep` lines print `1` then `0`. Any other pair is a finding:
fix it in step 5. A call that hits the 30 minute timeout follows the background rule in loop step
2, with these deltas: the smoke line stands for the gate (the retry runs the smoke once more) and
the two `grep` counts for the verdict line, and on the run's first build the
wait (an hour in all before TaskStop) is not a finding. On a later build (one after a call that
printed the counts) a build that needs more than 30 minutes is a finding for step 5.
<!-- /platform -->

- [ ] **Step 4 (piece 1 only): {{the inspection that clears an expected gate failure, if any}}.**

```bash
{{the diff command}}
```
Expected: {{exactly the hunks allowed}}. Anything else is a finding.

- [ ] **Step 5: Review, then fix.** Do the review in "Review prompt" below with `PR` filled in
(a person pastes it into Claude Code; an unattended Claude follows it directly). It reports
findings and edits nothing. For each finding decide: fix, or record why not. Fixes go on `BRANCH`
as normal commits (no force-push, no amend of pushed commits), test-first where the finding is
behavior:

```bash
# after editing
{{the quick check}}
git add <the files you changed>
git commit -m "{{prefix}} <what the finding was>"
git push
```
Expected: {{the quick check's green line}}; `git push` prints {{the push's last line, pasted}}.
Every commit this run makes, a test-only commit included, starts with `{{prefix}}`: the conflict
rule under "If something goes wrong" tells this run's commits from everyone else's by that
prefix. Re-run steps 2, 3{{ and 3b}} after the last fix. A finding about something in "Not this
job" is a comment, not a fix.

- [ ] **Step 6: Record the review on the PR and mark it ready.** Post one comment with: the gate
output (verbatim), the step 3 results, the findings list with what you did about each (every
finding, none filtered){{, and the piece-1 answers}}. Then:

```bash
gh pr comment PR --body-file - <<'EOF'
<the comment described above>
EOF
gh pr review PR --approve --body "Reviewed per {{runbook path}}; findings and gate output in my comment above."
gh pr ready PR
gh pr view PR --json isDraft,reviews --jq '"draft=\(.isDraft) approvals=\([.reviews[]|select(.state=="APPROVED")]|length)"'
```
Expected: `gh pr comment` prints the comment's URL; `gh pr review` prints nothing (gh prints its
confirmation only to a terminal, and the Bash tool is not one); `gh pr ready` prints a line to
stderr; the last line prints `draft=false approvals=1`. If the approve line errors because the
PR is a draft, run `gh pr ready PR` first, then the approve line again.

- [ ] **Step 7: Merge.** Only when steps 2, 3{{ and 3b}} are green, no finding is left open, and
`{{default branch}}` has not moved since step 1 (the first command below proves it):

```bash
git fetch origin && git merge-base --is-ancestor origin/{{default branch}} HEAD && echo "base unchanged since step 1" || echo "base moved: back to step 1"
```
Expected: `base unchanged since step 1`. On `base moved: back to step 1`, repeat steps 1 to
{{last check step}}, post the new gate output as a follow-up comment on the PR, then return here.
The third `base moved` on one piece is a stop: `{{default branch}}` is too busy for an unattended merge.

```bash
gh pr merge PR --merge --delete-branch
```
Expected: exit 0. gh prints nothing of its own off a terminal. {{primary clone: because `BRANCH`
is checked out it switches the clone to the default branch and fast-forwards it, so git prints
`Switched to branch`, `Updating ..`, `Fast-forward` and a diffstat; that output is normal, and the
clone now sits on the default branch (the next piece's step 1 checks out its own branch) | linked
worktree (A4), the case a repo hook that forbids edits outside a worktree forces (rule A12), where
step 1's `git checkout BRANCH && git pull --ff-only` becomes a worktree for `BRANCH`: gh warns,
skips the local delete and exits 0; the clone stays on `BRANCH`}}. Decide
the step by the
proof line only: `gh pr view PR --json state,mergeCommit --jq '"\(.state) \(.mergeCommit.oid)"'`
prints `MERGED <sha>`. On a non-zero exit other than the stack refusal below (a CLI error), the
fallback named under "Unattended run" merges the same way but leaves the head branch: delete it
with `git push origin --delete BRANCH` so GitHub retargets the next PR, which step 8 checks. A
refusal that the PR is "part of a stack and must be merged using the asynchronous merge REST API"
is a stop: that fallback does not take stacked pull requests, and Task 0 step 4 checked that none
of these is one.

- [ ] **Step 8: Prove the retarget before moving on.**

```bash
git fetch origin && git log -1 --oneline origin/{{default branch}}
test -f {{ledger file}} || printf '| Piece | PR | Merge commit | Gate | Findings found/fixed | Left for owner |\n|---|---|---|---|---|---|\n' > {{ledger file}}
printf '| N | #PR | %s | <gate result> | <found>/<fixed> | <left for owner, or none> |\n' "$(gh pr view PR --json mergeCommit --jq .mergeCommit.oid)" >> {{ledger file}}
gh pr view NEXT_PR --json baseRefName --jq .baseRefName
```
Expected: `origin/{{default branch}}` tip is the merge commit for `PR` (or a later push to `{{default branch}}`; the
ledger row reads the merge commit from GitHub either way); `{{ledger file}}` stays untracked
(step 5 adds named files only, so it never reaches a commit; it is the record for Task 9, not
resume state); the next PR's base now reads `{{default branch}}`. If it is anything but `{{default branch}}`, set it:
`gh pr edit NEXT_PR --base {{default branch}}`. After the last piece, `NEXT_PR` is the first PR stacked above
the job if one exists (the merge retargets it like any other), else skip the `NEXT_PR` line and
the retarget check.

Then piece N+1.

---

## Task 9: Finish

- [ ] **Step 1:** `gh pr list --state open --limit 100 --json number --jq '.[].number'` lists none
of the pieces. Other open PRs are fine.
- [ ] **Step 2:** From `{{default branch}}`, run the gate one last time: `git checkout {{default branch}} && git pull
--ff-only && {{gate command}}` and expect {{the verdict line}} (a call moved to the background:
loop step 2).
- [ ] **Step 3:** {{Close the source PR unmerged, or whatever the source item needs.}}
- [ ] **Step 4: Ledger.** Post the ledger the loop's step 8 wrote, with its closing line, as one
comment on #{{delivery PR}} (the plan's PR):

```bash
printf '\nNext job: {{what follows}}.\n' >> {{ledger file}}
gh pr comment {{delivery PR}} --body-file {{ledger file}}
```
Expected: `{{ledger file}}` has one row per piece, and `gh` prints the new comment's URL.

---

## Review prompt (paste into Claude Code at the repo root, one piece at a time)

```text
Review pull request PR of {{owner}}/{{repo}}. Read only; do not edit, stage or commit anything.

1. Run `gh pr view PR --json body --jq .body` and use its "{{review guide section}}" to decide where to start.
2. Run `git diff origin/{{default branch}}...HEAD` for the diff. That is the whole piece; ignore anything outside it.
3. Read {{the repo's rules files and the design doc row for this piece}}.

Report every finding as: file:line, severity (CRITICAL / HIGH / MEDIUM / LOW), what is wrong, what you would change. Check especially: {{the job's own risk list}}. Say explicitly which claims in the PR body you verified and which you could not. Report everything you find; do not filter by severity.
```

Replace `PR` before pasting.

---

## Not this job

Findings about these become a PR comment that names the item, not a fix:

- {{Owner items declined as steps, each with the reason and who carries the risk.}}

## If something goes wrong

- **The step 1 merge conflicts.** Resolve it only when it is self-inflicted: every `{{default branch}}`-side
  commit that touched a conflicted file is a fix this run made on an earlier piece. Decide with
  `git log --no-merges --format=%s "$(git merge-base HEAD origin/{{default branch}})"..origin/{{default branch}} -- $(git diff --name-only --diff-filter=U) | grep -v '^{{prefix}}'`,
  run while the merge is still in progress. Nothing printed means self-inflicted: resolve by hand
  keeping the fix's intent (never rebase; the pieces above depend on this branch's commits),
  `git add` the resolved files, `git commit --no-edit`, run steps 2, 3{{ and 3b}}, then
  `git push`; the pieces above pick it up through the chain. Any line printed is someone else's
  change, which the owner did not authorise resolving: `git merge --abort` and stop.
- **Piece N+1's step 2 fails after a clean step 1.** First learn whether `{{default branch}}` itself is
  broken: `git checkout {{default branch}} && git pull --ff-only && {{gate command}}`, then
  `git checkout BRANCH`. A green gate means `{{default branch}}` is fine and only N+1 needs adapting to piece
  N's fix: fix it there, on N+1's branch, as a step 5 finding. A red gate while
  `git rev-parse origin/{{default branch}}` still equals piece N's merge commit means piece N broke
  `{{default branch}}`: do not patch forward. Revert and stop:
  `git checkout {{default branch}} && git revert --no-edit -m 1 <merge sha of N> && git push` (the sha is in
  `{{ledger file}}`, or `gh pr view <N's PR> --json mergeCommit --jq .mergeCommit.oid`), then post
  the sha and both gate outputs on #{{delivery PR}}. If `{{default branch}}` has moved past N's merge, the
  breakage may be someone else's: stop without reverting and post both outputs. Never revert and
  continue: the reverted commits still sit in the branches above and come back at the next step 1
  merge, so the owner decides.
- **You merged with squash by mistake.** Stop and tell the owner before touching the next piece;
  the remaining pieces now need a rebase, which this plan does not cover.
- **The gate fails a test.** {{Where its log is}}, then run the gate once more. One test that
  failed the first run and passes the second, with the same test count both runs, is a flake;
  anything else is a finding for step 5. No count may shrink between runs.

## Unattended run

The teammate starts Claude Code in the clone with permission prompts off and pastes the prompt
below. Claude then runs Task 0 through Task 9 by itself. It stops early, leaving the stack as it
stands and posting a comment on #{{delivery PR}} that says where and why, when any of these
happens:

- `gh api user --jq .login` prints `{{author login}}` (the check beside the launch line at the
  bottom; Claude repeats it before Task 0).
- `{{default branch}}` moves a third time under one piece (loop step 7).
- Any Task 0 Expected line is not met, the resume check in step 4 saying stop included.
- A step 2, 3{{ or 3b}} check{{ other than the expected piece-1 failure}} still fails after two fix
  attempts.
- `mergeable` is still `UNKNOWN` after five re-runs at loop step 1.
- {{The piece-1 inspection finds anything beyond what step 4 names.}}
- A CRITICAL finding whose fix would touch something under "Not this job".
- The step 1 merge of `origin/{{default branch}}` conflicts and the conflict rule under "If something goes
  wrong" does not allow resolving it.
- Piece N+1's gate fails and the gate on `{{default branch}}` fails too: the revert rule under "If something
  goes wrong" (revert only while `origin/{{default branch}}` is still N's merge commit, post, stop).
- `gh pr merge` fails and the fallback (`gh api -X PUT repos/{{owner}}/{{repo}}/pulls/PR/merge -f merge_method=merge`, which covers a CLI failure only and cannot merge a GitHub stack) fails too, or either one refuses because the PR is part of a stack.
- After a merge the next PR's base is not `{{default branch}}` and `gh pr edit --base {{default branch}}` fails.

The prompt:

```text
Work unattended on {{owner}}/{{repo}}. First: if the current directory is not a clone of that repo, run git clone git@github.com:{{owner}}/{{repo}}.git and work inside it from then on. Then run git fetch --prune origin and read the plan in full with: git show origin/{{docs branch}}:{{runbook path}}. If gh pr view {{delivery PR}} --json state --jq .state prints MERGED (the plan has landed; its branch may be stale or gone), or that git show fails, read the same path from {{default branch}} instead: git show origin/{{default branch}}:{{runbook path}}. Keep the plan open and re-read it with the same command after you check out other branches.

Then run the gh api user check beside the launch line under "Unattended run" and execute the plan exactly: Task 0, the loop from the piece Task 0 step 4 names through the last piece in order, Task 9. Do not ask me anything; the owner has authorised every merge in advance. Where the plan says "a person pastes this into Claude Code", do that work yourself. Fix findings test-first on the piece's branch with ordinary commits; never rebase, amend a pushed commit, force-push, squash{{, or merge the source PR}}. Stop early only on the conditions listed under "Unattended run" in the plan, and when you stop, post a comment on PR #{{delivery PR}} saying which piece, which condition, and the exact command output.

When all pieces are merged{{ and the source PR is closed}}, post the ledger from Task 9 step 4 on PR #{{delivery PR}} and finish with a one-screen summary here: pieces merged, findings fixed, anything left for the owner.
```

Launch, from the clone or from the folder the clone should land in, after one check:

```bash
gh api user --jq .login
```
Expected: any login other than `{{author login}}`. That is the author of every PR, and GitHub
refuses an author's own approval (Facts table), so a machine signed in as `{{author login}}`
cannot do loop step 6: `gh auth login` as the teammate before launching.

```bash
BASH_DEFAULT_TIMEOUT_MS=1800000 BASH_MAX_TIMEOUT_MS=1800000 claude --dangerously-skip-permissions
```
The two variables raise the Bash tool's foreground timeout from two minutes to 30, so the gate
and the longest build finish in one call instead of being cut off (loop step 2).
