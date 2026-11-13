---
name: pr-review-router
description: Use when open PRs in VBE (VistaMarkets/vbe) or VFE (VistaMarkets/vfe) (or one named PR) need a review posted as a PR comment plus cleanup commits pushed to the PR branch, picking the review and fix skills from what the diff touches. Built for unattended scheduled runs; never approves, merges, or force-pushes.
argument-hint: "[<owner>/<repo> <N>] [--max <n>] [--no-push] [--dry-run] | -h"
---

# pr-review-router

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop. Do not run any other step in this
skill.

> **⚠️ Posts one comment on each reviewed PR, and pushes cleanup commits to that PR's branch,
> including PRs other people opened.** Each PR gets a main review (up to four agents), a
> thermo-nuclear quality review, and up to four fix passes. It never approves, merges,
> force-pushes, or rewrites history.

Finds open PRs with no review of their current head commit, reviews each one with the skills its
diff calls for, lets the fix skills commit their changes to the PR branch once the repo's checks
pass, and posts one comment saying what was found and what was pushed.

| Option | Values | Default | Effect |
|---|---|---|---|
| target | `<owner>/<repo> <N>` or nothing | scan every repo in the table below | Review one PR, or scan for PRs that need a review. |
| `--max <n>` | integer 1–10 | 3 | Most PRs handled in one run (scan mode only). |
| `--no-push` | flag | off | Review and comment only; the fix skills run with nothing pushed. |
| `--dry-run` | flag | off | Print the plan and the composed comments; post and push nothing. |

## Repos

| Repo | Checkout | Code review skill | Gate (must pass before a code push) |
|---|---|---|---|
| `VistaMarkets/vbe` | `vbe/` | `vista-dw-review` (repo-local; picks Vista's reviewer agents) | `./gradlew build` (needs JDK 17, installed by the environment's setup script, and a running Docker daemon for Testcontainers; see Step 6) |
| `VistaMarkets/vfe` | `vfe/` | `dw-review` (generic) | `flutter analyze` and `flutter test` in each package the PR touches |

Find a checkout by its remote, not by guessing a path:

```bash
for d in /home/user/*/ "$PWD"/../*/; do
  url=$(git -C "$d" remote get-url origin 2>/dev/null) || continue
  case "$url" in *"$REPO"|*"$REPO".git) echo "$(cd "$d" && pwd)"; break;; esac
done
```

No checkout for a repo means skip it and say so in the summary. Never clone a repo from here.

## Hard rules

1. **Running this skill is the owner's go-ahead to post and to push.** That covers one comment
   per PR and fast-forward pushes to PR branches, other people's included. It does not cover
   approving, requesting changes, merging, marking a PR ready, or resolving someone else's
   review thread. Never call `perseus08-rvw-agy` or `pr-merge-cleanup`: those merge.
2. **Fast-forward pushes only.** Never force-push, rebase, amend, or rewrite history on a PR
   branch. Other people have those branches checked out, and a rewrite breaks their checkout.
   So `make-pr-easy-to-review` never does its history cleanup here, and `babysit` brings a
   conflicting base in with a merge commit, never a rebase.
3. **Gate before every code push.** A commit that changes code is pushed only when the repo's
   gate passes on the final tree. When the gate can't run (no JDK, no Docker, no Flutter SDK),
   push no code commits and say so in the comment. Never skip a test, loosen an assertion, or
   pass `--no-verify` to get through the gate.
4. **One writer at a time on a branch.** Run `Z0rd0nZords:zord-multi-agent-review` only with
   `--no-loop --no-comment`. Its own fix loop would push on top of this skill's fix passes.
5. **REST, not GraphQL.** In cloud sessions `gh pr …` and `gh issue …` fail with a 403. Use
   `gh api repos/{owner}/{repo}/…` (and the GitHub MCP tools when a REST write is refused).
6. **Never fake a review.** If the main review fails or returns no report, post nothing and push
   nothing for that PR, and list it under "failed" in the summary.
7. **Run every step in this session; never hand a PR to a subagent.** This session is the
   manager, as in `baton-runner-managed`, for the same two reasons. `dw-review` and
   `vista-dw-review` are `Workflow` skills, and a subagent may not be able to run `Workflow`
   (a user-scope `nested-fanout-guard` hook blocks it on some machines, and subagent-of-subagent
   dispatch is not guaranteed anywhere). And a gate can outlast a subagent: its foreground Bash
   stops at 600 s and its background tasks die when it returns. The skills may still spawn their
   own agents (`dw-review`'s lanes, thermo-nuclear's reviewers, `zord-multi-agent-review`'s
   orchestrator); that is one layer down from here, which they are built for.

## Step 1 — candidates

With a target, the candidate is that one PR (ignore the Step 2 marker only when the operator asks
for a re-review). Otherwise, for each repo in the table:

```bash
gh api "repos/$REPO/pulls?state=open&sort=updated&direction=desc&per_page=50" \
  --jq '.[] | select(.draft|not) | [.number, .head.sha, .head.ref, .user.login, ([.labels[].name]|join(",")), .title] | @tsv'
```

Drop a PR when its labels include `skip-review` or `no-bot-review`. Drop it when its head is in
a fork (`.head.repo.full_name` differs from `$REPO`): this skill pushes only to branches in the
repo itself.

## Step 2 — already handled?

Every comment this skill posts starts with a marker naming the commit it reviewed and the commit
it left the branch at:

```
<!-- pr-review-router reviewed=<sha> pushed=<sha or none> skill=<skill-name> -->
```

Skip a PR when its current head sha matches the `reviewed=` or the `pushed=` value of any marker:

```bash
gh api "repos/$REPO/issues/$N/comments" --paginate --jq '.[].body' \
  | grep -F '<!-- pr-review-router ' | grep -qF "=$HEAD_SHA " && echo handled
```

The `pushed=` check is what stops the loop. Without it, this skill's own push would make the PR
look new, and the next run would review and push again. A push by the author changes the head,
so the PR becomes a candidate again. Keep the first `--max` candidates, most recently updated
first, across all repos. Name the rest in the summary as "deferred to the next run".

## Step 3 — classify (the rubric)

```bash
gh api "repos/$REPO/pulls/$N/files" --paginate \
  --jq '.[] | [.filename, .status, (.additions+.deletions)] | @tsv' > "$SCRATCH/files-$N.tsv"
```

Take the **first** class that matches. Each row lists everything that runs on that PR.

| # | Class | Rule | Main review | Quality review | Blast radius | Fix passes (push) |
|---|---|---|---|---|---|---|
| 1 | Spec / design doc | Every changed file is Markdown under `docs/`, or named like `*spec*`, `*prd*`, `*design*`, `adr*`, **and** none is an instruction file | `Z0rd0nZords:zord-reasoned-review` on the changed docs | — | — | `babysit`, `unslop`, `make-pr-easy-to-review` |
| 2 | Large | More than 40 files, or more than 1500 changed lines | `Z0rd0nZords:zord-multi-agent-review pr <N> --no-loop --no-comment --adversarial` | `thermo-nuclear-code-quality-review` | `blast-radius` | `babysit`, `deslop`, `make-pr-easy-to-review` |
| 3 | VBE code | Repo is `VistaMarkets/vbe` | `vista-dw-review pr <N>` | `thermo-nuclear-code-quality-review` | `blast-radius` | `babysit`, `deslop`, `make-pr-easy-to-review` |
| 4 | Flutter code | Repo is `VistaMarkets/vfe` | `dw-review pr <N>`, plus Step 4b | `thermo-nuclear-code-quality-review` | `blast-radius` | `babysit`, `deslop`, `make-pr-easy-to-review` |

Skills without a namespace in the last three columns come from the lil-pstack plugin: call them as
`lil-pstack:<name>`. A skill that is not installed is reported as "not run (not installed)",
never silently dropped.

**What each lane owns.** The main review hunts bugs, security holes, and broken contracts. The
thermo-nuclear review owns structure: abstraction quality, giant files, spaghetti conditions, and
missed simplifications. `blast-radius` owns breakage outside the diff. Don't brief one lane to
repeat another's job.

**Instruction files** are `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `REVIEW.md`, and anything under
`.claude/`, `.agents/`, or `.codex/`. A PR that changes them is code-class (rows 2–4): the
dw-review lanes check instruction drift, but the reasoned-review lenses do not.

**Money add-on, classes 2–4:** if a changed non-test source file (`.kt`, `.kts`, `.sql`, `.dart`,
`.ts`, `.py`) matches money terms in its patch
(`price|qty|quantity|amount|fee|balance|notional|slippage|funding|pnl|margin|collateral|order`),
also run `audit-numeric-types` on the PR diff and attach its PASS/FAIL section.

Run every skill from inside that repo's checkout, so repo-local skills and `.claude/agents/`
resolve.

## Keep state on disk

Three PRs of reviews and fix passes will not fit in one context window, and compaction can drop
anything held only in conversation. So, per PR, keep everything under
`$SCRATCH/router/<repo-slug>-<N>/`:

- `state.md`: one line per finished step (`4a done verdict=… report=4a.md`), written as soon as
  the step ends. After a compaction, read `state.md` and carry on from the first step not listed.
- one file per output: `4a.md` (main report), `thermo/` (the thermo-nuclear layered report),
  `4d.md`, `analyze.txt`, `gate.log`, `pushed.txt`, `needs-author.md`.

Hold only verdict lines and file paths in context. Step 7 builds the comment from the files.

## Step 4 — review phase (read-only, at the PR head)

Record the head as `H0`. Brief each review skill with one sentence before its arguments:
*"Unattended run from pr-review-router: do not post to GitHub, push, or write a record file into
the repo; return the final report as your output."*

- **4a. Main review.** Run it. Keep its final report verbatim, verdict and author questions
  included.
- **4b. Flutter only: static analysis.** Run it once per Dart package the PR touches, in a
  throwaway worktree at `H0`. Not from the repo root: the root `analysis_options.yaml` excludes
  `vista/app`, which is its own package, so a root-level run reports "No issues found" without
  reading the changed files.

  ```bash
  W="$SCRATCH/review-$N"
  git -C "$CHECKOUT" fetch -q origin "pull/$N/head:pr-review-$N"
  git -C "$CHECKOUT" worktree add -q "$W" "pr-review-$N"
  : > "$SCRATCH/analyze-$N.txt"
  # nearest pubspec.yaml above each changed .dart file = the package to analyze
  for f in $(cut -f1 "$SCRATCH/files-$N.tsv" | grep '\.dart$'); do
    d=$(dirname "$f"); while [ "$d" != "." ] && [ ! -f "$W/$d/pubspec.yaml" ]; do d=$(dirname "$d"); done; echo "$d"
  done | sort -u > "$SCRATCH/packages-$N.txt"
  while read -r pkg; do
    echo "== flutter analyze in $pkg" >> "$SCRATCH/analyze-$N.txt"
    (cd "$W/$pkg" && flutter pub get >/dev/null 2>&1 && flutter analyze --no-fatal-infos) >> "$SCRATCH/analyze-$N.txt" 2>&1
    echo "exit=$?" >> "$SCRATCH/analyze-$N.txt"
  done < "$SCRATCH/packages-$N.txt"
  ```

  No `flutter` on PATH means writing "flutter analyze: not run (no SDK in this session)".
- **4c. Quality review.** Run `lil-pstack:thermo-nuclear-code-quality-review` against the 4b
  worktree (add one the same way for other repos), pointed at the PR's diff against its base
  branch, not "the current branch vs main". Have it write its layered report to
  `$SCRATCH/thermo-$N/`. The summary file goes into the comment; each detail file goes in its own
  collapsed section. It reviews only: its remediation plan is for the author, and it commits
  nothing.
- **4d. Blast radius.** Run `lil-pstack:blast-radius` on the same diff. It may run scripts to
  prove a fact; it edits nothing.
- **4e.** Run the money add-on from Step 3, if it applies. Then remove the review worktree.

## Step 5 — fix phase (writes, on the PR branch)

Skip this step with `--no-push` or `--dry-run`, or when 4a failed.

Check out the PR branch itself, not the `pull/N/head` ref, so commits land on it:

```bash
F="$SCRATCH/fix-$N"
git -C "$CHECKOUT" fetch -q origin "$HEAD_REF"
git -C "$CHECKOUT" worktree add -q -B "review-bot-$N" "$F" "origin/$HEAD_REF"
```

Run the class's fix passes in this order. Each one makes **one commit** with the message
`review-bot(<skill>): <one-line summary>`. A pass with nothing to change makes no commit.

1. **`lil-pstack:babysit`** — one pass, no loop: the next scheduled run is the next pass. Bring a
   conflicting base in with `git merge origin/$BASE_REF` (rule 2). Fix failing CI from its logs,
   read over REST (`gh api "repos/$REPO/actions/runs?head_sha=$H0"`, then
   `gh api repos/$REPO/actions/jobs/<job-id>/logs`). Apply review comments that have one
   mechanical answer. Anything that needs a design choice goes on a "Needs the author" list for
   the comment, undecided. Never mark the PR ready and never resolve a reviewer's thread.
2. **`lil-pstack:deslop`** (classes 2–4) — on the PR's diff against its base, not on files the PR
   doesn't touch.
3. **`lil-pstack:unslop`** (class 1) — on the changed prose files only. Leave quotes, code, and
   tables of data byte-identical, as unslop's own "do not rewrite" rule says.
4. **`lil-pstack:make-pr-easy-to-review`** — improve the PR description and add reviewer
   guidance. Write the description with
   `gh api -X PATCH "repos/$REPO/pulls/$N" -F "body=@$SCRATCH/pr-body-$N.md"`, keeping the
   author's text and adding to it, never deleting it. No history cleanup (rule 2).

## Step 6 — gate, then push

Run the repo's gate (Repos table) in `$F` on the final tree. For Flutter, run `flutter analyze`
and `flutter test` in each package from 4b (about 3–4 minutes for `vista/app`).

VBE's own `SessionStart` hook does not run in a multi-repo session: it only runs when
`vbe/` is the project directory, so nothing has started Docker. Start it before the
gate, clearing pidfiles a dead daemon left behind (the same steps as
`vbe/.claude/hooks/session-start-cloud.sh`):

```bash
if ! docker info >/dev/null 2>&1; then
  for p in /var/run/docker.pid /run/docker/containerd/containerd.pid; do
    [ -f "$p" ] && ! kill -0 "$(cat "$p" 2>/dev/null)" 2>/dev/null && rm -f "$p"
  done
  (dockerd >/tmp/dockerd.log 2>&1 &)
  for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
fi
docker info >/dev/null 2>&1 || echo "gate can't run: dockerd did not start (see /tmp/dockerd.log)"
```

`./gradlew build` takes 10–20 minutes, longer than a foreground Bash call is allowed to run
(600 s). Run it in the background from this session, writing to the PR's `gate.log` with the exit
code on its last line, and wait for the background task to finish before reading the verdict.
Never run it inside a subagent (rule 7), and never treat a timed-out gate as a pass.

```bash
( cd "$F" && ./gradlew build --console=plain --max-workers=2 > "$STATE_DIR/gate.log" 2>&1; echo "GATE_EXIT=$?" >> "$STATE_DIR/gate.log" )
```

Downloads go to Google's Maven Central mirror through `~/.gradle/init.d/maven-central-mirror.gradle`
(and a copy in `~/.gradle/vista-testkit/init.d/` for the nested TestKit builds), which the
environment's setup script writes. Maven Central itself answers cloud sessions' download bursts
with HTTP 429. A gate that fails with `Received status code 429` is an environment failure, not
the PR's: push no code commits, and say so in the comment. Never edit the repo's build files or
`gradle/verification-metadata.xml` to get past it.

No JDK 17 under `/usr/lib/jvm/`, or no Docker daemon, means the gate can't run: follow the
"Gate can't run" branch below.

- **Gate passes:** push fast-forward only.

  ```bash
  git -C "$F" push origin "HEAD:$HEAD_REF"
  ```

  A rejected push means the author pushed while this ran. Don't retry and don't force. Push
  nothing, and say in the comment that the prepared commits were dropped because the branch
  moved. Record the new head as `H1`.
- **Gate fails:** drop the newest fix commit locally (`git reset --hard HEAD~1`; this is the
  local worktree, never the remote) and run the gate again, until it passes or nothing is left.
  Push what passes. List each dropped commit and the gate error it caused.
- **Gate can't run** (no JDK 17, no Docker daemon, no Flutter SDK): push no code commits. The description edit from step 5.4 still stands. List the commits that weren't pushed
  and why.

Then remove the fix worktree and its local branch.

## Step 7 — post the comment

Compose one body in `$SCRATCH/review-$REPO_SLUG-$N.md`:

```markdown
<!-- pr-review-router reviewed=<H0> pushed=<H1 or none> skill=<skill-name> -->
## Automated review — <skill-name> @ <short H0>

### In plain English
<lil-pstack:bro applied to the main report: 3–6 short lines, verdict first>

<main review report, verbatim>

<details><summary>Structure (thermo-nuclear)</summary> <summary file, then one nested details per detail file> </details>
<details><summary>Blast radius</summary> … </details>
<details><summary>flutter analyze</summary> <each package's result, in a code fence> </details>   <!-- Flutter only -->
<audit-numeric-types section>                                                                     <!-- money add-on only -->

### Changes pushed by this run
<one line per pushed commit: short sha, skill, summary · the gate command and its result ·
 commits dropped or not pushed, and why · "PR description updated" when 5.4 changed it>

### Needs the author
<babysit's undecided items, or "Nothing.">

<sub>Routed by pr-review-router: <class> → <skill-name>. It never approves or merges; fix commits are fast-forward pushes the author can revert.</sub>

---
_Generated by [Claude Code](https://claude.ai/code)_
```

Apply `lil-pstack:unslop` to the router's own words only: the heading, the plain English summary,
the "Changes pushed" lines, and the footer. Leave every review report byte-identical: rewording a
finding changes what was reviewed.

GitHub caps a comment at 65,536 characters. Over that, keep every CRITICAL and HIGH finding in
full, shrink MEDIUM and LOW to a table of `file:line` and one-line summaries, collapse the
thermo-nuclear detail files to their headings, and say that you did.

With `--dry-run`, print the body and stop. Otherwise, post it:

```bash
gh api "repos/$REPO/issues/$N/comments" -F "body=@$SCRATCH/review-$REPO_SLUG-$N.md" --jq .html_url
```

## Step 8 — summary

End with one table: repo, PR, class, main skill, verdict, commits pushed, and the comment URL, or
`skipped (reason)`, `deferred`, or `failed (reason)`.

Two more sections may go under the table:

- **Daily digest.** In scan mode, when the run starts between 00:00 and 03:59 UTC, run
  `lil-pstack:what-did-i-get-done` for each repo over the previous UTC day and add its update
  under a "Yesterday" heading. The time window keeps it to one digest a day without stored state,
  given a 4-hourly schedule.
- **Reflect.** When any PR ended `failed`, a gate dropped a commit, or a sub-skill had to be
  re-run, run `lil-pstack:reflect`. It writes its skill edits on a new branch
  `reflect/<UTC date>` in the skill's own repo (my-skills, Z0rd0nZords, or lil-pstack), pushes
  it, and opens a draft PR there for the owner. Never push a skill edit straight to a default
  branch. Put the PR links under "Skill fixes proposed".

The table and those sections are the whole output of a scheduled run.
