---
name: ci-parity-run
description: Runs a repo's CI job list locally on the commit CI would test and reports what was and wasn't covered. Use when asked to run a repo's CI checks locally, or to confirm locally before a PR that a branch or its base would pass CI — "run what CI runs", "would CI pass on this", "does main build here". Not for fixing or checking a GitHub check on an open PR, and not for a workflow's own gate step.
---

# ci-parity-run

The goal is a result the user can trust as "CI would agree": the CI job list, run on the commit CI would test, with an honest list of what wasn't run.

## 1. Find what CI runs, and what the repo calls its gate

- Read every job in `.github/workflows/*.yml` (or the repo's CI config), including steps after the main build: coverage floors, guard scripts, docs checks, image builds, secrets scans. Note each job's working directory, toolchain version pins and required services. This list is the definition of "what CI runs".
- Read the repo's agent docs (CLAUDE.md, AGENTS.md, CONTRIBUTING) for a documented local gate script. A gate is usually broader than one CI step and narrower than all of CI. Diff its checks against the CI job list before trusting it as a stand-in, and run the CI checks it doesn't cover.

## 2. Pick the commit without moving the session branch

- Check where the branch stands: `git fetch origin <base>`, then `git merge-base --is-ancestor origin/<base> HEAD` and `git rev-list --left-right --count origin/<base>...HEAD`. Do this *before* running any check that diffs against the base (guard scripts, "lockfile unchanged" checks); on a stale branch they compare the wrong range.
- PR CI tests the branch merged into the base. When the branch is behind, test that merge: make a detached worktree, merge the base into it there, and run the checks on that. To test the base alone, check out `origin/<base>` detached.
- Put the worktree where the repo's conventions say (some repos keep them under a gitignored `.claude/worktrees/`), otherwise in the scratchpad. A worktree has no installed dependencies, so install them as CI does. Remove it with `git worktree remove` when done.
- Leave the session's own branch where it is; moving it to test something else creates "unpushed commits" for stop hooks to chase. When a hook fires on a branch with no changes against its base, tell the user why it fired; push only real changes.
- Record the commit you tested. If the base moves while you work, say which results are now stale.

## 3. Match the environment

- Compare local toolchain versions with CI's pins (SDK, JDK, Node) and either switch or report the difference.
- Start required services first. Testcontainers needs a running Docker daemon (`docker info`); without it, tests fail on setup, not on real bugs.
- Install dependencies the way CI does (e.g. lockfile-enforcing flags), so a drifted lockfile fails here too.

## 4. Run and judge

- Run long steps in the background with output going to a log file, and come back when they finish.
- Judge each step by its exit status (`${PIPESTATUS[0]}` when piping), not by the last lines of output. Banners, "newer versions available" lists and warnings can push the real verdict off the tail.
- Count results from the reports the tools write (JUnit XML, coverage files), not from scrolling output.

## 5. Report

One table: CI job/step → command → result, with counts (tests run, failed, skipped, and why the skips happened). Mark which rows came from the CI file and which from the gate. After it, always list:

- **Not covered:** jobs or steps you didn't run, and why (secrets scan, image build, deploy, live-credential tests).
- **Drift:** version or environment differences from CI that could change a result.
- **Commit tested:** the branch tip, the base, or the merge of the two, and whether the base has moved since.
