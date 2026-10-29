# Checkpoint: <job title>

status: running
phase: 0 of N — <phase name>
step: <what is happening right now, one line>
updated: <UTC timestamp> by child <n> (session <id>)
worktree: <path> · branch <name> · HEAD <sha> · base <sha>
other worktrees: <path · branch · HEAD, or none>

## Next action
<one exact action the next session takes first>

## Phase plan
| # | Phase | Done when | Status |
|---|---|---|---|
| 0 | <name> | <acceptance> | done · commit <sha> |
| 1 | <name> | <acceptance> | in progress · step 2 of 4 |
| 2 | <name> | <acceptance> | pending |

## Current phase: <n> — <name>
**Will happen** (written when the phase starts)
1. <step> → verify: <check>
2. <step> → verify: <check>

**Progress** (one line per step as it lands, newest last)
- <UTC time> step 1 done: <result, with the command run>

## Completed phases (summary each, newest last)
### Phase 0 — <name>: <one paragraph: what now works, commands run and results, review rounds and open finding IDs, commit>

## Decisions (append only; source each)
| Decision | Why | Source |
|---|---|---|

## Open or blocked (append only)
- <item needing the owner, with the question and your recommendation>

## Pointers
- Phase reports and review ledgers: `<job-dir>/phases/phase-<n>.md`
- Review reports: <paths>
- Scratch files worth keeping: <paths>
