---
name: code-cleaver
description: Sets up a whole-codebase audit. Cuts the repo into reviewable slices, writes the plan and reviewer checklist, proves them on one tracer slice, then reviews and fixes the plan.
argument-hint: "[path to limit the audit to] | -h"
disable-model-invocation: true
---

# code-cleaver

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help` or `help`, output
only the block below and stop.

> **Sets up an audit; it does not run the audit.** One run ends with a slice plan that has
> survived review, a reviewer checklist, a baseline, and one real slice report (the tracer).
> The remaining slices, every code fix and every commit are left to you.
>
> **It spends agents.** Three stages fan out: the tracer review, the plan review, and the
> plan fix, which runs the Workflow tool through `finding-fixer`. Invoking code-cleaver is
> the go-ahead for all three. One measured run, on a 95,000-line repo with two apps: about
> 110 minutes and 1.6M subagent tokens across those stages. That is one data point, not an
> estimate for your repo.
>
> **It asks three questions**, after cutting the slices and before spending: when reports
> are committed, what an open CRITICAL or HIGH blocks, and which slices get adversarial
> refutation. Everything else it has to decide lands in the plan's Open questions.
>
> **What it creates:** a `chore/audit-plan` branch and worktree, untracked files under the
> repo's review-docs folder there, and whatever ignored build output the repo's own gates
> leave in that worktree (a virtualenv, caches). It changes no tracked file and commits
> nothing.
>
> Needs `zord-multi-agent-review`, `zord-reasoned-review` and `finding-fixer`, a git repo,
> and a top-level session.
>
> ```
> /code-cleaver                 # the whole repo
> /code-cleaver services/api    # only this tree
> ```

## What a run leaves behind

In a worktree cut from the remote default branch, uncommitted:

```
<review folder>/<YYYY-MM-DD>-audit-plan.md     the plan
<review folder>/<YYYY-MM>-audit/               the audit folder
  checklist.md                                 what every reviewer receives
  <id>-checklist.md                            the tracer's copy, This run filled in
  <id>-<slice-name-in-kebab-case>.md           the tracer slice's report
  plan-review.md                               the review of the plan
  tools/                                       any script written to produce a plan number
```

The review folder is wherever the repo's most recent review reports are tracked, or
`docs/reviews` when it has none. Keep these file names even where the repo names its
reports differently, because a resumed run finds the plan by name; note the repo's own
pattern in the plan header for whoever commits the files.

`$C` is `scripts/cleaver.py` beside this file, called by absolute path; in the plan, write
it as `cleaver.py`. `<scratch>` is the session scratchpad, outside the repo. An argument
path is passed to `measure` and `verify` as `--only <path>`.

Every number the plan states is **measured**. It comes from `$C` or from a command the plan
records, so anyone can re-measure it. Remove a number that has no command behind it. Cost
and time are where this slips, because one tracer run invites a multiplied total. Where the
plan states a judgement, such as which trees are high-risk, it says it is one.

## Review tool limits

Five figures from `zord-multi-agent-review` 2.3.0, checked against the installed copy in
stage 1. `cleaver.py` carries the first and last as `MAX_FILES_DEFAULT` and `PRELUDE_CAP`.

| Figure | 2.3.0 |
|---|---|
| Tracked files in one directory before `--max-files` is needed | 50 |
| Roster times directories, past which a `slices` run hard-fails | 16 |
| Seats in the automatic roster | up to 6 |
| Token cost of `--adversarial`, as a multiple of a plain run | about 4.3 |
| Size of a `--prompt-prelude` file | 16 KB |

Nine stages, in order. Each ends on a check; move on when the check holds.

## 1. Preflight

1. Confirm this is a top-level session; in a subagent, stop and say code-cleaver must be
   run from the main session. The review skills dispatch two layers of agents of their own,
   and the tool supports no third.
2. Confirm `zord-multi-agent-review`, `zord-reasoned-review` and
   `finding-fixer` are in this session's skill list. If one is absent, stop with
   `code-cleaver needs <name>, which is not installed in this session.` Leave installing to
   the user. Use the session's installed skills even where the repo vendors its own copy,
   and note a version difference under Open questions. Then check the figures under Review
   tool limits against the installed tool's `-h` output and `references/`, and use the
   installed values from here on.
3. `git fetch`, then resolve the default branch
   (`git symbolic-ref --short refs/remotes/origin/HEAD`) and its SHA. With no remote, use
   the local default branch and record that in the plan header.
4. `gh auth status`. On failure, continue: open PRs and issues are recorded as `unknown`.
5. Look for an earlier run: `git worktree list` for a `chore/audit-plan` branch, and a
   `*-audit-plan.md` inside that worktree. With a plan, read it, resume at the first stage
   whose section is unfilled, and keep every existing report as it is. With a worktree and
   no plan, start again at stage 2 in that worktree.
6. Otherwise `git worktree add --no-track -b chore/audit-plan <path> <remote>/<default>`,
   with `<path>` beside the repo's other worktrees, or `.worktrees/audit-plan` when it has
   none. Work there with absolute paths, and read all repo state from it: the primary
   checkout may be stale or dirty.

Check: `git -C <worktree> rev-parse HEAD` prints the SHA resolved in step 3, or on a resumed
run the SHA in the plan header.

## 2. Measure

1. `python3 $C measure --root <worktree> --json <scratch>/units.json`. Its **units** are
   the shallowest directories whose code fits a line budget it picks from the repo's size.
   It counts code by file extension, so markup, workflows and container files land in
   `other` and go to the platform slice.
2. `python3 $C overlap --root <worktree> --units <scratch>/units.json` for the open PRs
   that change files in each unit. `UNKNOWN` is a valid result: every In flight cell then
   reads `unknown`.
3. Read what the repo says about itself. In full: agent and contributor rule files, a
   constraints or standards file, the README, CI workflows, any release or rollout plan,
   and any notice that the project is paused or archived. Titles and summaries only:
   earlier audits, review reports and open issues, to learn what is already tracked.
4. Work out what the next two stages need, and mark each as a judgement where no command
   shows it:
   - the **release steps**: whatever puts code in front of users (a flag, a staging config,
     a rollout plan's step, a deploy workflow). A repo may have several, a paused one, or
     none;
   - the **high-risk units**: code that moves money, handles identity or keys, deletes or
     migrates data, enforces a safety or compliance gate, or writes to an external system.
     When that marks most of the code, rank the units by what a bug costs and take them
     from the top until they hold a third of the code lines;
   - trees that are not this product's code (agent and editor config, vendored copies,
     mirrors), which become Left out rows. Hooks and scripts that gate this repo's own
     commits and builds belong to the platform slice.

Check: every unit `measure` printed is marked high-risk, ordinary or left out, and the
release steps are named or recorded as none found.

## 3. Cut the slices

A **slice** is the unit of review: a bounded area of code that gets the seven lenses, one
report and at most two fix PRs.

1. Build slices from the units. Each slice is **one directory or two**: one review run
   takes one (`dir`) or fans the whole roster out per directory (`slices`), and roster
   times directories has to stay inside the tool's limit. Pair small neighbours. A slice
   may run up to a quarter over the budget when the alternative is several tiny ones, and a
   unit `measure` marks as over budget with nothing to split on is one slice at whatever
   size it is. Where a directory mixes product code and tests, cut at the code directory
   (`module/src/main`, not `module`).
2. Attach loose files (code sitting directly in a directory whose children are slices) and
   stray small units to the slice they wire up or belong beside. The review tool takes
   directories, so these reach reviewers through the slice's checklist, and its Paths cell
   lists them. Loose files too large to attach without breaking the budget become a slice
   of their own, with `unresolved` in its Run cell and how to run it under Open questions.
3. Add one slice for platform and supply chain: the build, dependency, container and CI
   files and directories that no code slice covers. Size it with
   `git ls-files -- <its paths> | wc -l`. Its run target is the directory holding most of
   those files, and the rest go through its checklist. Name lock files and other generated
   manifests there as checked for pins and known-bad versions only.
4. Give each left-out tree from stage 2 a row in the Left out table, with its reason and
   who decides.
5. Group slices into phases ordered by what a bug costs. The usual order is money and
   data-loss paths, then identity and platform, then other features, then shared code; move
   shared code up when it holds the costly logic.
6. Fill `In flight` from the overlap map and `Refuted` as `yes` for slices holding a
   high-risk unit, or the high-risk files of a unit split between slices. A slice where
   open PRs change a fifth or more of the files defaults to waiting for the merge, and that
   choice goes under Open questions.
7. Pick the **tracer**: the smallest first-phase slice that is one directory, at least
   half the budget and no more than a quarter over it, exercised by tests named by path,
   and untouched by any open PR (when overlap is `unknown`, say so). When no first-phase
   slice qualifies, take the first later one that does; when none does anywhere, take the
   one-directory slice nearest the budget and say in the plan which condition it misses. A
   tracer marked refuted runs with refutation, as its row says.

Check: every slice is listed with its paths; every unit `measure` printed, or each file of
a unit split by file, is assigned to one slice or one Left out row; and one slice is named
the tracer.

## 4. Ask the three policy questions

Ask with the question dialog, one question per call, recommended option first. Each question
must stand alone, so put this repo's facts in the wording: what it does with reports today,
its release steps, how many slices are marked for refutation and which.

| Question | Option labels, recommended first |
|---|---|
| When do slice reports go into git? They name unfixed security findings by file and line. | `With the fix PR`; `Never, plan only`; `Redacted index only`; `Immediately` |
| What does an open CRITICAL or HIGH block? | `Block release` (a CRITICAL stops the slice queue; an open CRITICAL or HIGH blocks the release step for that slice's code; other slices continue); `Fix before next slice`; `Only CRITICAL stops`; `Nothing` |
| Which slices get adversarial refutation, at the cost multiple under Review tool limits? | `High-risk slices only`; `None, verify at fix time`; `Every slice`; `No extra verification` |

When no release step was found, say so in the second question: the rule then binds from
the day one exists. When there are several in sequence, name them all, and the recommended
option blocks the next one that slice's code has not passed.

The three answers are **decided**: later stages reproduce them as given. From the third
answer on, every decision met goes under the plan's Open questions, with enough context to
answer cold, and the run continues.

Check: three option labels recorded, with any note the user typed.

## 5. Write the plan and the checklist

1. Copy `assets/plan-template.md` and `assets/checklist-template.md` to the paths above.
   Fill every `<<slot>>` that stages 2 to 4 can answer, follow each `<!-- comment -->` and
   delete it, and delete a line that does not apply. Leave the Baseline section's slots for
   stage 6.
2. If the third answer changed which slices are refuted, update the `Refuted` column.
3. Fill the checklist's lenses from the repo's own rules: quote the rule and name the file
   it lives in. A lens the repo says nothing about keeps its generic text. The seven lens
   names stay fixed, and lens 5 is written for whatever this code presents.
4. Keep lens wording in the checklist only, so it and the plan cannot drift apart.
5. Leave the checklist's `This run` slots in place; each slice fills them in its own copy.
6. Fill the plan's tool-figure slots from Review tool limits, as checked in stage 1.

Check: the plan holds the slice tables and the Decided section, and the checklist's only
slots are `This run` and the test-status bullet that stage 6 fills.

## 6. Baseline

1. Find the repo's own gates: CI workflow steps, a gate script, `Makefile` or package
   scripts, a constraints file. Install dependencies the way the repo's docs say, inside
   the worktree. Run the analyzer or linter, the test suite and coverage as the repo scopes
   them, once per package or once where it has one aggregate gate, in the background when
   slow. Record each command, exit code, counts and the runner's own clock. Code the gates
   do not cover is a lead. Measure coverage only where the repo defines it, and point any
   gate that would rewrite a tracked file at an output path outside the repo.
2. For every gate that is red: list what fails (each test with its assertion), look for a
   tracking issue, and where CI exists check whether it fails the same way, so a local-only
   failure is not reported as the repo's. Red gates become their own step in the plan, ahead
   of the first fix PR, because no fix can show a gate green until then.
3. `python3 $C secrets --root <worktree>`. It prints kind and `file:line`. Read each line
   to rule out a test value or placeholder. Record a lead as kind and `file:line`; the value
   stays in its file, out of everything written and out of this conversation. Its pattern
   list is short, so add a `git grep -n` for the kinds of secret this repo handles that the
   list lacks, and print only `file:line` from it.
4. Scan for leads with patterns written for this repo's languages, choosing what fits the
   kind of software:
   - everywhere: suppression comments and unimplemented stubs; handlers that swallow an
     error, in one-line and multi-line form; logging that may carry errors, tokens or
     personal data; plain `http://` URLs; floats on money paths when the repo handles money;
   - a client: where sensitive data is stored, URL launching, clipboard use;
   - a service: SQL or shell built from input, deserialising untrusted data, outbound URLs
     taken from input, routes without an auth check, disabled TLS or host-key checks;
   - scripts and infrastructure: suppressed failures (`|| true`, `set +e`), downloads piped
     to a shell, unpinned versions.
5. Write the results into the plan's Baseline table, each command in the numbered list
   under it (a pattern containing `|` would break a table cell). Record what each pattern
   over- or under-counts. Each row is a **lead**, routed to the slice that owns the file.
6. Fill the checklist's test bullet, then run
   `python3 $C verify --worktree <worktree> --plan <plan> --audit-dir <audit folder>`,
   both paths from the repo root.

Check: every baseline row has a command and a measured result, or `not run:` and the reason;
and `verify` prints `VERIFY: PASS`.

## 7. Run the tracer

1. Copy `checklist.md` to `<id>-checklist.md` and fill `This run`. Note the start time.
2. Invoke `zord-multi-agent-review` and follow it, with the target and flags
   the plan's `How a slice is run` section sets for the tracer's row.
3. When it returns, check the report before believing it: the file exists, its Coverage
   Report says `Reviewers: n/n returned` with equal numbers, and `Reviewed at:` is the
   audited SHA. Open the cited lines of every CRITICAL and HIGH and confirm the code says
   what the finding says. See whether rows carry a `Lens N:` tag and whether any extra
   files were read.
4. `git status` in the worktree: only audit files may differ.
5. Fill the plan's `Tracer result` and the tracer's Status cell from the report.

Check: the tracer row links the report, each count in it can be re-counted from the report
file, the Tracer result says for every CRITICAL and HIGH whether its cited lines match, and
`verify --stage final` passes.

## 8. Review the plan, then fix it

A first-draft plan reads fine and fails in use: the run this skill came from had twelve HIGH
problems that showed only when reviewers set the plan against the tracer report.

1. Invoke `zord-reasoned-review` on the plan's absolute path, asking it to
   forward `--write-to <abs audit folder>/plan-review.md`. If the report lands in the tool's
   default folder, copy it into the audit folder. Run the stage 7 step 3 integrity check.
2. `python3 $C stamp <plan-review.md> <scratch>/plan-review-findings.md` to give every
   finding an id.
3. Copy the plan and `checklist.md` to `<scratch>`: they are untracked, so git cannot
   restore them if the fix run damages one. Then record hashes of the files the fix must
   leave alone:
   `sha256sum <abs tracer report> <abs plan-review.md> > <scratch>/frozen.sha256`.
4. Invoke `finding-fixer` on **every** finding, at every severity, with:
   - `cwd`: the audit worktree;
   - `verify`: the stage 6 `verify` command plus `--stage final --frozen <scratch>/frozen.sha256`;
   - `groups`: two to four, batched by what settles them (how the review tool behaves; the
     state of the tree and open PRs; the repo's written rules and the baseline), each
     pointing at the stamped findings file and listing its ids;
   - `houseRules`: the text of `assets/house-rules.md`, its four slots filled.
5. Then do finding-fixer's own step 4 yourself: read the whole edited plan, re-run `verify`,
   and re-measure a sample of the numbers the run wrote in.

Check: every stamped id has an outcome: applied, open with the file its fix belongs in,
refuted, or no edit needed.

## 9. Report

Send the plan, the tracer report and the plan review to the user as files. Then report, in
this order:

1. Where the files are, and that nothing is committed.
2. The tracer: counts per severity and the title of every CRITICAL and HIGH. A CRITICAL
   leads the message.
3. The plan review: how many findings were applied, left open and refuted, and each open
   one with the file its fix belongs in.
4. The baseline's red items: failing gates and any secret lead.
5. The count of Open questions, and the one to answer first.
6. What this run did not do: the other slices, any code fix, any commit.
