---
name: addy-code
description: Disciplined coding workflow for any task in this session - interview, planning files, context pack, vertical slices routed to the right skill, review loop, draft PR. Use for "addy-code", "code it up", or any non-trivial build.
---

# Addy Code

One session, one task, the full discipline: understand it, plan it on disk, pack the context,
build it in thin slices with the right skill per slice, review until clean, deliver a draft PR.
Each step names the skill to invoke when it is installed and the rule to follow when it is not,
so the workflow runs on any machine. Work on a feature-branch worktree per the repo's rules.

## 0. Interview if anything is vague

Vague means: no "for whom", no "why now", two readings of the ask, or a success condition you
would have to invent. Invoke `addyosmani-interview-me` (fallback: one question at a time until
you can state the intent, the user and the done-condition in three sentences the user agrees
with). Skip it when the task is already concrete; do not interview to look thorough.

## 1. Plan on disk

Invoke `planning-with-files`. Keep `task_plan.md`, `findings.md`, `progress.md` in the project
directory (never staged). Update them at every step below, not at the end: `task_plan.md` holds
phases with status and the decisions table, `progress.md` the step log with commands and results,
`findings.md` what you learned about the code. After a compaction or a new session, these files
are the resume point; the first action is to read them.

## 2. Build the context pack (before any decision or code)

Invoke `addyosmani-context-engineering` when installed; inline rule otherwise. Read in rank
order: the repo's instruction files, then only the spec or ADR sections the task needs, then
the source files below. No whole-document dumps. Write the pack into `findings.md`.

## 3. Produce the brief (in `task_plan.md`)

1. **Project map**, only the modules the task touches: purpose, key files, the pattern each
   follows (errors, money, auth, persistence).
2. **Per-phase relevant files**: for each phase, the files to modify, their tests, one existing
   example of the pattern to copy, the types or interfaces involved.
3. **Known gotchas**: hooks that trip, flaky tests, commands that need Docker, output limits,
   files that look live but are not.
4. **Conflicts** between spec, docs and code, each written as options with a recommendation.
   Put them to the user in one decision packet before building; never resolve one silently.

The brief also fixes the exact tracked-file target set and the phase table: each phase has one
"done when" and, directly after it, its own review row. The target set is the scope-confirmation
set: confirm it before touching more than three files.

## 4. Build in thin vertical slices

Invoke `addyosmani-incremental-implementation` when installed. Either way: each slice is one
complete path through the stack, implemented, tested, verified and committed before the next;
never more than about 100 lines before a test runs; build and existing tests green between
slices; incomplete user-visible work behind a flag or safe default; riskiest slice first when
unsure.

**Route each slice before the first line of code** and record the pick in the phase's
will-happen list in `task_plan.md`:

| Slice is… | Skill | Fallback when not installed |
|---|---|---|
| UI work (screens, components, layouts) | `addyosmani-frontend-ui-engineering` | accessible, responsive, production-quality; design tokens, no hardcoded styles; every control has a working result or a clear unavailable state |
| API or interface work (endpoints, contracts, module boundaries) | `addyosmani-api-and-interface-design` | contract first; stable names; explicit error shapes; additive, versioned changes |
| Code that must match library or framework docs | `addyosmani-source-driven-development` | verify the API against the official docs or installed package source before using it; cite the source in `findings.md` |
| High stakes (money, auth, migrations, irreversible ops) or unfamiliar code | `addyosmani-doubt-driven-development` | before the slice stands, a fresh-context read-only subagent cross-examines its assumptions; record what it challenged |
| Writing tests (every slice) | `addyosmani-test-driven-development` | red first, then green, then refactor; a behavior change without a failing test first is not done |
| Tests that run in a browser | `addyosmani-browser-testing-with-devtools` | drive a real browser (DevTools MCP or Playwright); capture console errors and network failures as evidence |
| Plain logic, CLI or data code with no UI or API surface | none beyond the tests row | the slice rules above are enough |

Invoke only the rows that match; a loaded skill you do not need costs context and adds nothing.
The same goes for steps 0 to 3: scale them to the task. A one-file change still gets planning
files and a brief, but each can be a few lines.

After the phase's code is written and before its review: `addyosmani-code-simplification`
(fallback: one pass removing duplication, dead flexibility and anything the slice did not need;
behavior unchanged, tests still green).

## 5. Review loop (per phase)

Pick the reviewer: the first rule whose skill is installed **and can run here** (its tools and
targets exist). One that matches but cannot run is recorded as blocked in `progress.md` with the
reason, and you fall through to the next. Record the final pick.

1. `vista-dw-review` when the repo ships it and the target is a committed branch or PR there.
2. `dw-review` for a committed branch or PR in any repo (findings are adversarially refuted
   before you see them).
3. `Z0rd0nZords:zord-multi-agent-review` for a staged or working diff, a spec, or a directory,
   or when the user asked to loop review and fix.
4. `addyosmani-code-review-and-quality` (single-agent, multi-axis) when nothing above can run.

Give every finding a stable ID. For anything above low, run `finding-fixer` (fallback: adjudicate
each finding yourself in writing, fix the supported in-scope ones with a failing-then-passing
check for every behavior change, record the rest as refuted or out of scope with the reason),
then re-review. At most five rounds; anything above low still open after the fifth stops the run
for the user. A round with nothing above low closes the phase. Its lows
you may still fix after closing without another round when the fix is small and a test covers
it; log each as `post-review low fix, test-covered` in the ledger, and leave the rest listed as
open. Only when the whole ladder is blocked is the phase's review recorded as blocked; never
replace it with a self-review called clean. Report findings to the user in full, verbatim,
before your own take.

**Phase close.** In unattended runs too, the next phase's first edit comes after `git status --short`
lists no target-set path, the closing review ran on that committed work (or the review is recorded
as blocked), and `task_plan.md` and `progress.md` show the phase closed and name the commit it
closed at.

## 6. Delivery

Deliver only the reviewed paths, one logical change per commit, no attribution lines. Push and open
a **draft** PR: summary, decisions table, test plan as checkboxes with the exact commands run,
the review ledger (rounds, finding IDs, dispositions, open lows), `Closes #N` when an issue
exists. No merge, no deploy. Final `progress.md` entry: what now works, how to try it, what is
open. Tell the user the PR link and the one next action.
