---
name: ci-parity-run
description: Use when asked to run a repo's CI checks locally or to confirm a branch or the base branch is green before a PR — "run what CI runs", "run the tests and analysis", "confirm the checks pass", "run the gate", "does main build here". Covers choosing the commit to test without moving the session's branch, using the repo's documented gate, running the exact CI commands, and reporting what was and wasn't covered. Not for fixing a failing GitHub check on an open PR.
---

# ci-parity-run

The goal is a result the user can trust as "CI would agree": same commands, same commit, and an honest list of what wasn't run.

## 1. Find the real gate

- Read the repo's agent docs (CLAUDE.md, AGENTS.md, CONTRIBUTING) first. If they name a local gate script ("use it, don't write another"), that is the command to run. It often does more than the `ci.yml` step that is easiest to find with grep: clean test runs with the cache off, shell tests, docs checks, smoke tests.
- Then read every job in `.github/workflows/*.yml` (or the repo's CI config), including steps after the main build: coverage floors, guard scripts, image builds, secrets scans. Note each job's working directory, toolchain version pins and required services.

## 2. Pick the commit without moving the session branch

- Check where the branch stands: `git fetch origin <base>`, then `git merge-base --is-ancestor origin/<base> HEAD` and `git rev-list --left-right --count origin/<base>...HEAD`. Do this *before* running any check that diffs against the base (guard scripts, "lockfile unchanged" checks); on a stale branch they compare the wrong range.
- To test the current base, use a detached checkout or a worktree: `git worktree add --detach ../<repo>-ci origin/<base>`. Don't fast-forward the session's working branch to do it. That creates "unpushed commits" for stop hooks to chase and leaves empty copies of the base on the remote.
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

One table: CI step → command → result, with counts (tests run, failed, skipped, and why the skips happened). After it, always list:

- **Not covered:** jobs or steps you didn't run, and why (secrets scan, image build, deploy, live-credential tests).
- **Drift:** version or environment differences from CI that could change a result.
- **Commit tested** and whether it is still the tip of the base.
