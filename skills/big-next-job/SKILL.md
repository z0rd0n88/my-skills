---
name: big-next-job
description: Scope, brief and run a multi-phase job unattended in any repo as a chain of checkpointed Claude sessions. Use for "big next job", "next big job", "run this overnight", "write a job brief"; not quick edits.
---

# Big Next Job

Turn a substantial, related set of outcomes into a job that runs without mid-run feedback and
survives a crash, a timeout, or a closed terminal. Works in any git repo. Needs only `claude`,
`tmux`, `python3` and `flock` (util-linux, on every Linux and WSL); no Orca, no plugin. The job's whole state lives in two files a fresh
session can read in one go, so every phase starts on a clean context and nothing depends on
a hand-written handoff.

Files in this skill: `scripts/run-job` (the session chain), `templates/brief.md` (the job brief
with the child protocol), `templates/checkpoint.md` (the state file).

## Pick the mode

- **Suggest** (no target named): propose three ranked, distinct next jobs from the roadmap, open
  issues, blockers and code. For each: outcome, why now, rough scope, main blocker. Mark the best
  one and offer "use my recommendation" or a choice of 1/2/3. Never launch an unchosen job.
- **Prompt only** ("write/revise the brief"): produce the brief and stop. No worktree, no edits, no
  checkpoint. With no target named, scope as for Suggest and write the brief for the top job. The
  owner has not answered anything yet, so §2 holds your recommendations marked as such; a child
  treats them as binding until the owner edits them.
- **Run** ("do/start the job"): scope read-only, settle decisions up front, write the brief and
  checkpoint, launch `run-job`, report how to watch it, and end your turn. The chain does the rest.

Prefer one coherent job with a few linked deliverables over a sprawl of loosely related tasks.

## Scope it read-only

Read what the repo says about itself before deciding anything: `AGENTS.md`/`CLAUDE.md`, `ARCH.md`
if present, the roadmap, PRD, specs, ADRs and progress notes under `docs/`, and the open issues
and PRs when remote access works (say so when it does not). Name the exact documents that govern
the job in the brief. Treat dated progress text and issue counts as leads: check them against the
current code, build wiring and tests. Do not infer that something is live because its code exists.

If the repo has `.claude/big-next-job.md`, read it first. It is the project's notes for this
skill: source-of-truth documents, invariants that never loosen, the gate commands, the review
tooling, the usual phase names. Without it, tooling the repo's own instruction files name
(reviewer agents, a review command, a gate script) counts the same way, and you derive the rest
from the repo. The first run in a repo is a good moment to offer that notes file as a deliverable.

Keep every safety default on: dry-run flags, no live submission, no merge, no deploy, no new
dependency, no invented fee, limit, tolerance or policy. A financial or release-gating value the
docs leave undecided is an owner decision, never a guess.

## Build the context pack

Before any decision packet or brief, and never after building has started, assemble the context a
child will work from. Invoke `addyosmani-context-engineering` when it is installed; either way
produce, for brief §3:

1. **Project map**, scoped to the areas the job touches: one block per module with its purpose, key
   files, and the pattern it follows (how errors, money, auth, persistence are done there). Not the
   whole repo; only what a phase will read or change.
2. **Per-phase relevant files**: for each phase, the files it will modify, their tests, one existing
   example of the same pattern to copy, and the types or interfaces involved. A child loads only its
   own phase's list, nothing more.
3. **Known gotchas**: hooks that trip, flaky tests, commands that need Docker, output limits, files
   that look live but are not.
4. **Conflicts surfaced, not resolved silently**: where a spec, a doc and the code disagree, write the
   conflict with its options and put it in the decision packet. A child must not ask the owner
   mid-run, so every ambiguity you can find now is one the job will not block on later.

Rank what you read: the repo's instruction files, then the spec or ADR sections the job needs, then
the source files above, in that order; skip whole-document dumps. The pack is what makes the brief
stand alone and what keeps each child's context small enough to finish a phase in one session.

## Settle decisions before launch

List the outcomes, the exact tracked-file target set, affected systems, acceptance evidence, and
any owner or external-action choices. The brief's §4 target set is the restated set the
scope-confirmation rule asks for: in Run mode the owner confirms it before launch (in the decision
packet when there is one), and a child never widens it.

If questions remain, send **one decision packet**: short numbered choices, your recommendation and
why, and an "accept all recommendations" option. Do not re-ask what the owner already answered.
After launch nobody asks the owner anything; the brief says what to do instead (block that part,
finish the rest, record it).

## Write the brief and the checkpoint

Copy `templates/brief.md` and fill every section; write `not applicable` with a reason rather than
inventing UI, deployment or tests. The brief stands alone: no "as discussed", no reference to this
chat. Owner decisions go in §2 as a numbered table so a child can quote them. The phase table in §5
is the backbone; every phase has a "done when" a child can verify. A typical shape is
spec → tracer bullet → one vertical slice per phase → full gate → delivery, but the job decides.

Keep §9 (Child protocol) verbatim. It is what makes the chain work: resume from the checkpoint,
announce the phase, checkpoint after every step, close the phase and stop, hand back early when
context is heavy, finish with `status: done` or `status: blocked`. It also fixes how children
build and write: thin vertical slices, each tested and committed before the next
(`addyosmani-incremental-implementation` when installed, the inline rule otherwise), so the phase
table lists slices, not layers; a routing table that picks the discipline per slice (frontend UI,
API and interface design, source-driven, doubt-driven for high stakes or unfamiliar code, TDD for
every test, browser testing with DevTools for browser tests) and code simplification between
writing and review; and caveman prose (`caveman` when installed, the inline rule
otherwise) for every checkpoint, announcement, report and reply, except security warnings,
irreversible-action confirmations and order-sensitive sequences. Write your own replies to the
owner the same way.

Copy `templates/checkpoint.md`, fill the header, phase table and first `Next action`, and leave
`status: running`. The checkpoint is the single place a successor looks; its `phases/` directory
holds the long ledgers so the checkpoint itself stays short.

Put both in `<worktree>/.big-next-job/` and keep that directory out of git with
`echo .big-next-job/ >> .git/info/exclude` (local, nothing tracked changes). The worktree is a
dedicated feature-branch worktree created for the job; a job that spans repos keeps its job
directory in the primary worktree and lists the others in the checkpoint header.

## Launch and report

Run the chain in the background from the job's worktree, so it outlives this session:

```bash
cd <worktree> && CLAUDE_FLAGS="<flags the owner authorized for unattended tools>" \
  nohup <skill-dir>/scripts/run-job .big-next-job > .big-next-job/run.out 2>&1 &
```

Unattended children can only use tools the owner allowed; pass that through `CLAUDE_FLAGS`
exactly as the owner stated it. `run-job` starts one child, waits for its turn to end, reads the
checkpoint, and starts the next, until `status:` is `done` or `blocked`. A child that crashes is
seen within seconds and one that exceeds `JOB_CHILD_TIMEOUT` is killed; either way the next one
resumes from the last checkpoint. A child whose turn leaves work running in the background (a shell
running the tests, a monitor, a subagent) is waited on until the turn Claude starts when that work
finishes has ended. The work is read from Claude Code's status line (`· 1 shell ·`, `· 1 shell,
1 monitor ·`, `· 3 background tasks ·` while a subagent runs), the `◯` subagent rows under it, and,
between turns, the process tree; once some was seen, a Stop counts only after `JOB_BG_SETTLE` (10 s)
quiet, since the follow-up turn starts about a second after the work ends, even when it ended just
before the Stop. Work that never ends (a dev server, a monitor with no end) is waited on up to
`JOB_BG_WAIT` (1800 s, time held by `session-airspace` excluded; `JOB_CHILD_TIMEOUT` still applies
and may come first); that child is then closed, even with `JOB_KEEP_WINDOWS`, and counts as a stall
if it made no progress. The brief's child protocol tells children to stop background processes and
monitors before ending a turn, and not to end one while a subagent still works. A child stopped by an API error waits `JOB_API_BACKOFF` (600 s)
before the next, or `JOB_LIMIT_BACKOFF` (1800 s) for a rate or usage limit; those children are not
counted as stalls. Two children in a row that leave the checkpoint untouched stop the chain
(exit 5), as does the child cap (exit 4), so a confused job cannot spin. Only one `run-job` can
drive a job at a time (a second exits 1), and stopping it closes its child.

Then tell the owner, in this order: the phase table with the first phase's "will happen" list;
`tail -f <worktree>/.big-next-job/run.log` for the chain's log and each child's closing summary;
the `tmux -L run-job-<name>-<hash> attach -t job-<name>` command from the `child N launched` line
of `run.log` to watch a child in a terminal (each job runs on its own tmux server, named after the
job dir so two jobs never share one); `<skill-dir>/scripts/run-job status <worktree>/.big-next-job`
for the current phase and next action. If `session-relay` and `session-airspace`
(z0rd0n88/session-stickler) are on PATH and list run-job children, also mention `session-relay list`
(works from Claude Desktop) and, when several jobs run at once, `session-airspace guard` in a spare
terminal: it holds the largest child when RAM passes 85% and releases it as memory frees up, and
held time does not count toward `JOB_CHILD_TIMEOUT`. End your turn.

For a multi-phase coding job that must end in tested, committed, CI-green pull requests and should
survive usage limits on its own, recommend blast-off (z0rd0n88/blast-off) instead: it is this same
chain under systemd, with receipts, CI checks and automatic resume. `run-job` stays the light
choice: no systemd, no GitHub token, any job shape.

To resume after anything stopped the chain, run the same command again; it reads the checkpoint
and continues. Nothing is re-done.

## Reviews inside the job

Each phase ends with a review of its deliverable and a bounded fix loop (the brief's §7 sets the
tooling, the round limit and the stop rule). The project notes name the reviewer and fixer to use.
Without them, the child dispatches two independent read-only reviewer subagents (one for
correctness and tests, one for spec compliance and scope), gives findings stable IDs, fixes the
supported in-scope ones with a failing-then-passing check for behavior changes, and re-reviews;
at most three rounds, and a round that finds nothing above low closes the phase. A review that could
not run is recorded as blocked, never replaced by a self-review called clean.

## Project notes file

Optional `<repo>/.claude/big-next-job.md`, read before scoping. Keep it short:

```markdown
# Big Next Job notes for <repo>
- Sources of truth: <paths, in reading order>
- Invariants: <the rules a job never loosens>
- Gates: <exact commands that must be green before delivery>
- Review: <reviewer invocation> · fixer: <fixer invocation> · max rounds: 3
- Phases usually: <e.g. spec → tracer → backend → client → gate → delivery>
- Delivery: <draft PR rules, body contents, what never happens here>
```
