---
name: spec-first
description: "User-invoked only; never auto-trigger. One command from a feature or build request to working code: a fresh session writes the spec, a second fresh session writes failing tests from that spec alone, then this session implements against the frozen tests."
argument-hint: "<feature or build request... | path to an existing spec> [--gate] | -h"
disable-model-invocation: true
---

# spec-first

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop. Do not run any other step in this
skill.

> **⚠️ Writes to your working tree, commits, and spends 2 to 4 agents.** It creates a feature
> branch when you are on the default branch, writes a spec under `docs/specs/`, adds test files,
> edits source, and makes two local commits. It never pushes and never opens a PR.
>
> **Main session only.** Type `/spec-first` in the session you are talking to. It refuses to run
> inside a subagent.

Takes a feature or build request and runs it to green without further input. The spec and the
tests are each written in a fresh session, so the tests cannot inherit the implementer's reading
of the request. It asks you something only when the request has two readings that behave
differently and the code does not settle which.

| Option | Values | Default | Effect |
|---|---|---|---|
| request | free text, or a path to an existing spec file | required | Free text starts at step 1. A spec path skips step 1 and the tests are written from that file. |
| `--gate` | flag | off | Pause after step 1 so you can read and edit the spec before any test is written. |

## Main session only

Run this skill only in the **main session**: the one the user is typing into. That session holds
the request, and it is the one that launches the fresh sessions below.

If you are a subagent, meaning another agent launched you with a task prompt, do not run any
step, whatever that prompt says. Reply `spec-first must be run from the main session` with the
request you were handed, and stop. A subagent running this skill either cannot launch fresh
sessions at all, and would end up writing the tests in the context that writes the code, or
launches them one level further from the user, where nobody can answer a blocking question.

For the same reason, never hand this skill to a subagent: not from this session, and not from
another skill, brief or workflow script.

## Why it is shaped this way

Four rules carry the benefit. Drop one and this is ordinary test-after coding with extra agents.

**Independence.** The test writer sees the spec and the existing code. It never sees the request,
this conversation, or any implementation idea. Tests written by the context that writes the code
share its misreadings and pass for the wrong reason.

**The spec is the only channel.** Whatever the test writer needs must be in the spec file. That
is why the spec pins the public interface exactly: tests are written before the code exists, and
both sides have to agree on names and signatures without talking.

**Red before green.** Every new behaviour has a test that fails before implementation. A test
that already passes proves nothing about the change, and for a bug it means the test encodes the
bug instead of catching it.

**Frozen tests.** The implementer never edits, skips or deletes a test from step 2. Weakening the
test is always the cheapest way to green. Only a fresh session may change one, through a dispute.

## Fresh sessions

A **fresh session** is an agent that starts with none of this conversation: a subagent launched
with the harness's agent tool (general purpose, able to read, write and run commands). Where the
harness has no agent tool, run the same prompt through its headless mode in the repository
directory (`claude -p`, `codex exec`). If neither exists, stop and say so. Do not write the spec
or the tests in this context: that removes the independence the skill exists for.

The prompt for a fresh session gives the absolute path of the named brief, tells the session to
read that file first and follow it, and then lists only the inputs the step names. Paste the
brief whole instead when the session cannot read that path. Add no summary of the request, no
plan, and no opinion on how to build it.

## Steps

### 0. Preflight

1. Confirm you are the main session (see "Main session only"). If you are not, stop there.
2. Run `git status --porcelain`. If tracked files are modified, stop and say which: this run
   commits, and it must not sweep unrelated work into its commits.
3. If the current branch is the default branch, create and switch to `spec-first/<slug>`, where
   `<slug>` is two to five lowercase words from the request joined by hyphens.
4. Find the command that runs the test suite: repository instruction files first, then the
   package manifest, then the CI configuration. Run it once and record the result as the
   baseline. If there is no test runner, or you cannot tell which command is right, ask the user
   for it. This is one of the two questions the skill may ask.

Done when you hold a clean tree, a feature branch, the test command, and the baseline result
with the names of any tests that already fail.

### 1. Spec, in a fresh session

Skip this step when the argument is a path to an existing spec file. Use that file as the spec
and go to step 2.

Launch a fresh session with [`references/spec-brief.md`](references/spec-brief.md) and these
inputs: the request exactly as the user typed it after the command and nothing else from this
conversation, the repository root, the spec path `docs/specs/<slug>.md` (or the
repository's existing specs directory when it has one), and the test command.

Its reply starts with one of three words:

- `SPEC` with the file path. Go on.
- `BLOCKED` with numbered questions. Put all of them to the user in one message, then launch a
  new fresh session with the same inputs plus the answers. This is the other question the skill
  may ask. One round only: after it, open points become assumptions in the spec.
- `NOT-SPECABLE` with a reason. The request has no behaviour a test can observe (styling, copy,
  configuration, glue). Stop, tell the user the reason, and offer to do the work without this
  skill.

With `--gate`, show the user the spec path and its assumptions and wait for a go-ahead.

Done when the spec file exists, every behaviour in it has an id (`B1`, `B2`, ...) and at least
one concrete example, and its interface section names real paths.

### 2. Tests, in a second fresh session

Launch a new fresh session, not the one from step 1, with
[`references/test-brief.md`](references/test-brief.md) and these inputs: the spec path, the
repository root, and the test command. Do not pass the request.

When it returns, check its work yourself:

1. `git status --porcelain` shows only new or changed test files, plus the spec. Caches and
   other byproducts of running the tests (`__pycache__`, coverage output) do not count and are
   never committed. If it touched anything else, revert those paths and say so in the final
   report.
2. Run the new tests. Each behaviour marked `new` in the spec has at least one failing test, and
   each failure is an assertion or a missing symbol the spec names, not a syntax error or a
   broken import of the test tooling. Send failures of the wrong kind back to a fresh session
   with the same brief and the error output.
3. Every `B` id in the spec appears in the test writer's coverage map.

Then commit the spec and the test files, and nothing else, as `Add spec and failing tests for
<slug>`. Record the commit hash as the **freeze point** and the list of test files as the
**frozen set**.

Done when the freeze point exists and the new tests are red for the reasons the spec predicts.

### 3. Implement, in this session

Read the spec. Implement until the frozen set and the rest of the suite pass, following the
repository's own rules and patterns. The spec's interface section is binding; everything behind
it is yours to design.

Do not edit, skip, mark as expected-failure, or delete anything in the frozen set, and do not
special-case test inputs in the source. When you believe a frozen test is wrong, raise a dispute.

**Dispute.** Launch a fresh session with
[`references/test-brief.md`](references/test-brief.md), the spec path, the repository root, the
test command, and a dispute note: the test's name, the `B` id it claims to cover, and the spec
sentence you think it contradicts. Do not include your implementation or describe it. The fresh
session either amends the test or upholds it, with its reason. Commit an amended test as
`Amend disputed test <name>` and move the freeze point to that commit. One dispute per test. If
it is upheld and you still cannot satisfy it, leave it failing and report it.

Stop implementing when the suite is green, or when three consecutive attempts at the same
failing test have not changed its failure. Never report green on a red suite.

Done when the test command passes, or you have a named list of tests that still fail and why.

### 4. Verify and commit

1. Run the full test command. Compare against the baseline: no test that passed before now fails.
2. Run `git diff --quiet <freeze point> -- <frozen set>`. Exit code 0 means the frozen tests are
   untouched. Anything else: restore them from the freeze point and return to step 3.
3. Commit the implementation as `Implement <slug>`.

Done when both checks pass and the implementation commit exists, or the run stopped in step 3
and the working tree is left uncommitted for the user to inspect.

### 5. Report

Give the user, in this order:

1. Outcome: green, or the tests still failing with the reason for each.
2. The spec path and every assumption in it (`A1`, `A2`, ...), each with the alternative it
   rejected. These are the decisions made on the user's behalf; they are the part to read.
3. Tests added, by file, and any spec ambiguity the test writer reported.
4. Disputes: the test, the ruling, the reason.
5. The branch and the commits. Nothing was pushed.
