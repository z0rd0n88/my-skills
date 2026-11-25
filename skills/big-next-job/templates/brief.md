# Job brief: <title> (<repo> <issue refs>)

You are a fresh Claude Code session running an owner-authorized job. Everything you need is in
this file and in `checkpoint.md` beside it. Do not ask the owner for feedback after you start:
make the best supported, reversible choice and record it. If a new mandatory approval, a file
outside the target set, or an undecided safety or product policy appears, leave that part
blocked, finish the independent work, and record it under "Open or blocked".

## 1. Objective
<the outcome, 2-4 concrete related deliverables; what is out of scope; who owns adjacent work>

## 2. Owner decisions (binding; do not loosen)
| # | Decision | Choice |
|---|---|---|
| D1 | <question> | <owner's answer or accepted recommendation> |

## 3. Context pack (verified <date> at <sha>)
Built-versus-wired state; governing specs, ADRs, PRD rows, contracts, issues. Verified facts
marked as such; dated claims and inference marked as such.

### 3.1 Project map (only the areas this job touches)
**<module> (`<path>/`)**: <purpose>. Key files: <list>. Pattern: <how errors, money, auth, persistence are done here>.

### 3.2 Per-phase relevant files (a child loads only its own phase's list)
**Phase 1**: modify <files>; tests <files>; copy the pattern in <file:lines>; types <files>.
**Phase 2**: ...

### 3.3 Known gotchas
- <hook that trips, flaky test, command needing Docker, output limit, file that looks live but is not>

### 3.4 Conflicts found while scoping (each resolved by an owner decision in §2)
- <spec says X, code does Y> → D<n>

## 4. Preflight and authorization
- Worktree(s) and branch(es): <paths, names, base sha>
- Target set (the only tracked files this job may change): <exact paths or globs>
- Safety defaults that stay on: <dry-run flags, no-merge, no-deploy, no new dependency, ...>
- External actions allowed: <push, draft PR, none, ...>
- Stop condition: a change outside the target set, or a policy the owner has not decided, blocks that part.

## 5. Phases (in order; each has a "done when")
| # | Phase | Done when |
|---|---|---|
| 0 | <e.g. spec> | <reviewed, N rounds, closed> |
| 1 | tracer bullet | <the thinnest end-to-end slice works: red test, then green> |
| 2 | <slice> | <...> |
| N-1 | full gate | <exact command(s) green> |
| N | delivery | <commit of reviewed paths; draft PR if allowed; final report in checkpoint> |

## 6. Tests and gates
<exact commands; what counts as evidence; "unrun is not passed">

## 7. Review/fix loop (per phase)
<the review tooling to use and its invocation; the fixer; max rounds; stop rule; what counts as clean.
If the named tooling is unavailable, record the phase as "review blocked" rather than substituting a
single self-review and calling it clean.>

## 8. Delivery
<commit rules; PR body contents; what links to what; no merge, no deploy, no attribution lines>

## 9. Child protocol
Every session in this job follows this, in order:

1. **Resume.** Read `checkpoint.md`. The `Next action` line is where you start. If a phase is
   `in progress`, continue it from its `Progress` list; do not restart it. Verify the worktree,
   branch and HEAD match the checkpoint before changing anything. Then load only your phase's
   context: §3.1 for the modules it touches, its own §3.2 list, §3.3, and the spec sections §3
   names for it. Do not read other phases' files or whole documents; the pack exists so you do
   not have to.
2. **Announce the phase.** When a phase starts, write its "Will happen" list into the checkpoint's
   `Current phase` section (numbered `step → verify: check` lines, with a rough time estimate) and
   print the same list as your reply's first lines: `Phase N of M: <name>`.
3. **Checkpoint as you go.** After every landed step, every test run, every review round and every
   commit, update `step:`, `updated:` and the `Progress` list, and append decisions to `Decisions`.
   Phase-level detail (review ledgers, finding IDs, dispositions) goes to `phases/phase-<n>.md`,
   not the checkpoint. The checkpoint stays under about 150 lines so a successor reads it in one go.
4. **Close the phase.** Move it to `Completed phases` with its summary, mark its row done, set
   `phase:` and `Next action` to the next phase, then end your turn with the summary printed. A new
   session picks up the next phase; that is deliberate, it keeps each phase on a fresh context.
5. **Hand back early if heavy.** If your context use passes about a third mid-phase, finish the step
   you are on, checkpoint, set `Next action` to the exact next step, and end your turn. Before
   ending any turn, stop background processes and monitors you started (a dev server, a watcher):
   the runner treats a turn that leaves background work running as unfinished, waits for it up to
   `JOB_BG_WAIT` (30 min by default), then closes your session. Don't end a turn while a subagent
   still works; wait for its result first, so the checkpoint records it.
6. **Finish or block.** When the last phase is done, write the final report into `Completed phases`
   and set `status: done`. If the job cannot proceed without the owner, write what is needed under
   `Open or blocked` and set `status: blocked`. Never leave `status: running` with nothing left to do.
7. **Build in thin vertical slices.** Invoke `addyosmani-incremental-implementation` when it is
   installed; either way: each slice is one complete path through the stack (entry point to system
   boundary), implemented, tested, verified and committed before the next starts, never more than
   about 100 lines before a test runs. The build and existing tests stay green between slices.
   Incomplete user-visible work sits behind a flag or safe default. Riskiest slice first when
   unsure. The phase table's rows are slices or groups of slices, never horizontal layers.
8. **Route each slice to the right discipline.** Once the slice plan for a phase is set and before the
   first line of code, pick from this table; invoke the skill when it is installed, follow the
   fallback when it is not. Record the pick in the phase's "Will happen" list.
   | Slice is… | Skill | Fallback when not installed |
   |---|---|---|
   | UI work (screens, components, layouts) | `addyosmani-frontend-ui-engineering` | accessible, responsive, production-quality; design tokens, no hardcoded styles; every control has a working result or a clear unavailable state |
   | API or interface work (endpoints, contracts, module boundaries) | `addyosmani-api-and-interface-design` | contract first; stable names; explicit error shapes; versioned, additive changes |
   | Code that must match library or framework docs | `addyosmani-source-driven-development` | verify the API against the official docs or the installed package source before using it; cite the source in the checkpoint |
   | High stakes (money, auth, migrations, irreversible ops) or unfamiliar code | `addyosmani-doubt-driven-development` | before the slice stands, a fresh-context read-only subagent cross-examines its assumptions; record what it challenged |
   | Writing tests (every slice) | `addyosmani-test-driven-development` | red first, then green, then refactor; a behavior change without a failing test first is not done |
   | Tests that run in a browser | `addyosmani-browser-testing-with-devtools` | drive a real browser (DevTools MCP or Playwright); capture console errors and network failures as evidence |
   After the phase's code is written and before its review round: `addyosmani-code-simplification`
   (fallback: one pass that removes duplication, dead flexibility and anything the slice did not
   need, behavior unchanged, tests still green). Then the review loop in §7.
9. **Write like caveman.** Checkpoint text, phase announcements, reports and chat replies: terse,
   fragments fine, drop articles, filler, pleasantries and hedging; `[thing] [action] [reason].
   [next step].` Technical terms exact, code blocks unchanged, errors quoted exact. Drop it only
   for a security warning, an irreversible-action confirmation, or a multi-step sequence whose
   order matters. Invoke `caveman` when installed.
10. **Never** ask the owner a question in chat, stage or commit the job directory, loosen a D-decision,
    or report a check you did not run.
