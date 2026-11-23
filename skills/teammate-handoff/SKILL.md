---
name: teammate-handoff
description: Package a job as a runbook a teammate's plain Claude Code runs unattended on their own machine, reviewed until an adversarial critique finds nothing, delivered as a PR with a paste prompt.
disable-model-invocation: true
---

# teammate-handoff

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop. Do not run any other step in this
skill.

> **⚠️ Commits, pushes, opens a PR, posts to GitHub and spends 10 to 20 agents over several hours.** Every
> critique round dispatches an independent reviewer, every fix pass dispatches adjudicators and a
> writer, and the run ends by merging the docs PR from the primary checkout and tearing down the
> worktree.

Turns a job you finished scoping (a PR stack to land, a status check, a device run) into a
runbook that a teammate with plain Claude Code and none of your skills executes unattended,
then critiques that runbook against the rules in `references/runbook-rules.md` until an
independent reviewer finds nothing. Use it when the job will run on a machine you do not sit at;
for a hand-off between your own sessions use `session-switcher` instead.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<source>` | an issue, a PR or PR stack, or a report item (path or URL) | required | What the runbook packages. Everything else is asked in Phase 1, one question at a time. |

## What it produces

In the target repo, on a `docs/<slug>` branch with an open PR: the runbook. In an untracked
critique folder: `facts.md`, `probes.sh`, `session.md`, `logs/check-N-*.md`, the
instruction-ledger rebuild, the finding-fixer report, `teammate-handoff.md`. On the PR: the teammate handoff as a
comment. In the terminal: a one-screen summary for the owner.

Version 1 targets a Mac teammate; the Linux and Windows seams are the `<!-- platform: <os> -->`
markers of rule D8 (`${CLAUDE_PLUGIN_ROOT}/skills/teammate-handoff/README.md`, "Versions").

## Phases

Each phase ends on its verify. The next phase does not start until it passes. Phases 5 to 8 run
in this session, not in a subagent: `finding-fixer` uses the Workflow tool, which a subagent
cannot run. Shell-quote each value you substitute for a `<...>` field in a command below: wrap it
in single quotes and write a `'` inside it as `'\''`. Expand a leading `~` to the home directory's
absolute path first; inside quotes it stays a literal `~`.

**Push rule.** Before every `git push` of the docs branch: `git fetch origin && git merge
--no-edit origin/<default>`, then `git rev-list --count HEAD..origin/<default>` prints `0`. The
paste prompt reads the runbook from the branch, so a push that is behind serves the teammate a
runbook that no longer matches the repo.

`<slug>` is the source item's title (for a PR stack, the bottom PR's title; for a file, its name
without extension), lowercased, each run of characters other than `a-z` and `0-9` replaced by one
hyphen, leading and trailing hyphens dropped, cut to 50 characters; it names the docs branch and
the critique folder. The critique folder is `<primary checkout>/.claude/worktrees/<slug>-critiques/`. Before
writing to it, `git -C <primary checkout> check-ignore -q <folder>` must exit 0; otherwise use
`~/.claude/handoffs/<repo>/<slug>/` and say so in the summary.

### Phase 1: intake, one question at a time

Read the source item in full. Then ask the owner, with `AskUserQuestion`, one question per
call, in this order. Record every answer in `facts.md` under "Owner decisions".

1. What is the job: review and land a PR stack, a status check, a device run, or something
   else? (The template fits the first; the others reuse its shape with a different loop.)
2. What does the teammate have: Claude Code with no custom skills, which platform (Mac in this
   version), and which platform tools (Xcode, Android Studio, a simulator runtime)?
3. Where does the runbook go: which path in the target repo, on a `docs/<slug>` branch and PR (the PR is the
   review surface and the comment channel for stop reports and the run ledger)?
4. For a stack: merge commits with no rebase cascade, or something else?
5. Authority: fully unattended with every merge pre-authorised, or per-piece sign-off?
6. What is not this job: the items the teammate must comment on and never fix.

Verify: six answers in `facts.md`, each quoted. If the platform answer is not Mac, stop here and
tell the owner this version builds the Mac runbook only (rule D8); `facts.md` keeps the six answers.

### Phase 2: verify every fact live before writing

Every runbook sentence rests on a command run this session or, for a command this box cannot or
must not run (a platform-only tool, or a mutating step such as `gh pr merge` on the stack), on the
source or docs recorded for it in `facts.md` (rule D4). Before the first sentence, run and record in
`facts.md`, as `command`, then output verbatim:

- PR chain: number, state, draft flag, base, head, author, additions, deletions, file count,
  file list per branch, for every piece.
- Repo settings: `gh repo view --json mergeCommitAllowed,deleteBranchOnMerge,defaultBranchRef`;
  branch protection and rulesets (a 403 is itself a fact); CI presence (`.github/workflows`).
- The repo's gate script and guard script, read line by line, with the exact lines they print.
- The dependency diff of the first piece, if the gate has a frozen-lockfile check.
- Every output shape an Expected block will quote: run the probe and paste the output.
- `gh api user --jq .login` on this box, and `gh api repos/O/R --jq .permissions.push`.
- The repo's tracked Claude hooks: `.claude/settings.json` and every script it loads, read in
  full. The teammate's plain Claude Code runs them too, so a worktree guard, a refused git
  command or a Stop hook that builds shapes the loop (rule A12).
- The repo's `AGENTS.md` or `CLAUDE.md` and its constraints file if it has one, read in full (rule D12).
- The commit prefix is unused on the default branch since the stack branched (rule C5):
  `git log --format=%s "$(git merge-base origin/<first piece branch> origin/<default>)"..origin/<default> | grep -c '^<prefix>' || true` prints `0`.

Write every read-only probe, one per line, into `probes.sh` in the critique folder; the check
script runs that file under `bash -eo pipefail`, so every line must exit 0. A probe whose non-zero
exit is the fact (the 403 above) ends in `|| true`, its output recorded in `facts.md` (rule A7's
pattern); a probe bounds its output with the tool's own flag (`git log -1`) instead of a pipe into
`head`, which fails under `pipefail` with SIGPIPE. Commands this box cannot or must not run are listed in `facts.md`
under "Verified from source or docs, not run", with the source.

Verify: `bash -eo pipefail <critique folder>/probes.sh` from the primary checkout exits 0.

### Phase 3: write the runbook

In a worktree of the target repo on a new branch `docs/<slug>` (the repo's own worktree convention),
copy the part of `references/runbook-template.md` below its first `---` line to `<runbook path>`
(the path the owner gave in Phase 1 question 3), fill every `{{slot}}` from `facts.md` except
`{{delivery PR}}`, which Phase 4 fills, delete the slots that do not apply, keep every rule-bearing sentence. Read `references/runbook-rules.md` once
before writing, so the critique finds new defects instead of the known ones. Platform-only
steps and their setup checks sit inside
the `<!-- platform: mac -->` markers.

Verify: `bash "${CLAUDE_PLUGIN_ROOT}/skills/teammate-handoff/scripts/check-runbook.sh" <runbook>
--repo <worktree> --ref origin/<top piece branch>,origin/<branch a pointer names> --prefix <paths prefix> --probes <probes.sh>
--created <ledger file>` prints `CHECK: PASS`, or only one `FAIL unfilled {{slot}}` line whose line
numbers are exactly the `{{delivery PR}}` lines. Drop `,origin/<branch a pointer names>` when no
pointer names another branch; add one `,origin/<branch>` per further branch. Keep the exact
invocation; every later verify reuses it.

### Phase 4: deliver on a docs branch

In the Phase 3 worktree,
commit the runbook, push (push rule), open a non-draft PR whose body states
the authority level and names the critique folder. The PR number goes into the runbook's
`{{delivery PR}}` slots; commit that edit too.

Verify: `gh pr view <n> --json state,isDraft --jq '"\(.state) \(.isDraft)"'` prints
`OPEN false`, `git show origin/docs/<slug>:<runbook path>` prints the runbook, and the Phase 3
invocation prints `CHECK: PASS`.

### Phase 5: adversarial critique

Dispatch one `general-purpose` subagent with `references/critique-prompt.md` filled in (its
`{{rules path}}` is
`${CLAUDE_PLUGIN_ROOT}/skills/teammate-handoff/references/runbook-rules.md`),
mode full. Its report lands in the critique folder; read it in full. Its failing criteria, every claim-ledger row
with verdict WRONG or PARTLY, and its "Unattended failure scenarios" list are the findings for
Phase 6, numbered `F1`, `F2`, ... in the order the report gives them.

Verify: `session.md` has a new `## Check #N` entry and `logs/` a new file.

### Phase 6: first fix pass through finding-fixer

Invoke the `finding-fixer` skill with: `cwd` the docs worktree; `houseRules` the repo's rules
plus every rule in `references/runbook-rules.md` stated as decided; `verify` the exact
check-script invocation from Phase 3; `groups` two to four, batched by runbook section (setup,
the loop, finish and stop list, prose sections), each group's `sources` naming `facts.md`, the
rules file and the GitHub probes that decide its findings. Instruction text gets an
instruction-ledger proof (every instruction, qualifier, exception and named entity the edit
touches, marked preserved, changed, dropped or added), so every verdict carries `ledger:`; read
each applied ledger before trusting the edit.
Commit the applied edits on the docs branch and push (push rule); Phase 7 reads them from
`origin/docs/<slug>`.

`verify` is the regression gate: it passed at Phase 3 and stays green across the pass. It cannot
see the critique's findings, so their proof is the next round's critique: its claim ledger for a
WRONG or PARTLY row, its literal-executor read for every other finding. If
`finding-fixer` is not installed on this box, apply each finding yourself, each verified live
against the repo or GitHub first, and say in the report that the pass had no independent
adjudication.

Verify: the check script prints `CHECK: PASS`, and every `F` id appears once in the report as
applied, refuted, decided elsewhere, or still open.

### Phase 7: independent instruction ledger from the diff alone

Dispatch a fresh `general-purpose` subagent whose prompt opens with the read-only paragraph of
`references/critique-prompt.md` ("You are strictly read-only") and that sees only
`git diff origin/<default>...origin/docs/<slug> -- <runbook>` and the repo. It rebuilds the
instruction ledger (Phase 6) for the whole diff without the adjudicators' ledgers, then reads each changed sentence as a newcomer and lists: sentences
that parse two ways; contradictions between sections; command-syntax doubts, with the commands
run; wrong repo claims. Save it as `logs/ledger-rebuild-<date>.md`. Compare with Phase 6's
ledgers; every disagreement and every newcomer item is a finding for the next fix.

Verify: the file exists and its four lists are each either empty or carried into Phase 8.

### Phase 8: re-critique loop

Loop:

1. Fix the open findings (Phase 6's method; after the first pass you may apply them yourself,
   each verified live, and say so in the report).
2. Commit and push (push rule).
3. Dispatch the critique in targeted mode (`references/critique-prompt.md` defines it).
4. The loop ends when the re-check passes with "other N: unchanged", or when every finding it
   raises is `non-stopping` (`references/critique-prompt.md`, Output, section 3); record those
   as open in the finding-fixer report. A `stopping` finding goes back to step 1; the third pass
   through step 1 in one loop is the cap.

Then one full critique before the handoff, even after a clean targeted round: rounds two to
eight of the reference run each found something real. If it raises a `stopping` item, run the
loop once more; that is the cap. If the cap's last re-check still has a `stopping` item, go
straight to Phase 11 and give the owner the summary with those items as still open.

Verify: the last critique's sections 3 and 7 carry no `stopping` item, every `non-stopping` item
is recorded as open in the finding-fixer report, and the check script is green on the pushed
commit (`git diff origin/docs/<slug> -- <runbook>` is empty).

### Phase 9: teammate handoff

Write `teammate-handoff.md` in the critique folder and post it as a comment on the delivery
PR with `gh pr comment <n> --body-file`. Its sections, in order:

1. One paragraph: what the job is, that the run is unattended, how long it takes, that every
   merge is pre-authorised.
2. **Before you start**: install Claude Code and `gh`; the platform tools the run checks; sign
   in to GitHub as yourself (`gh auth login`), then `gh api user --jq .login` must print your
   login, not the author's, and why.
3. The launch line, verbatim from the runbook, and where to run it.
4. **The prompt**, verbatim from the runbook's "Unattended run", as one fenced block.
5. **What happens, and what to do if it stops**: the run ledger comment at the end; on a stop, send
   the PR comment to the owner and do not fix by hand; after the owner clears it, relaunch with
   the same line and the same prompt, and why that is safe (state comes from GitHub); sleep or
   a closed terminal is the same relaunch.
6. The runbook's path on the default branch, for a reader who wants it.
7. **Unverified**: the `facts.md` list "Verified from source or docs, not run", so the teammate
   knows which Expecteds were never run on the author's machine.

Verify: `gh pr view <n> --json comments --jq '.comments[-1].body'` prints the comment, and the prompt in it is byte-identical
to the runbook's (`diff` the two fenced blocks).

### Phase 10: merge the docs PR and tear down

From the primary checkout, never from inside the worktree: `gh pr merge <n> --merge
--delete-branch`, proved by `gh pr view <n> --json state,mergeCommit --jq '"\(.state) \(.mergeCommit.oid)"'`. Then
`git worktree remove <path>` and `git branch -d docs/<slug>`. The critique folder lives outside
the worktree, so it survives; if it sits inside the worktree, copy it out first.

Verify: `MERGED <sha>`, `git worktree list` without the path, and `ls <critique folder>/logs`
still lists every check.

### Phase 11: summary to the owner

One screen: the PR link and the runbook path on the default branch; rounds run with each
score (`15/22, 21/22, ...`); findings fixed, refuted, decided elsewhere, and still open with
their reasons; what stayed unverifiable on this box; the handoff comment link; the next action
for the owner (send the handoff to the teammate).

Verify: the summary carries the PR URL that `gh pr view <n> --json url --jq .url` prints and the
handoff comment's URL.
