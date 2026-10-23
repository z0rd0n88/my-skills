---
name: agenthub-plus
description: "Use when the user wants N agents to compete on one task in worktrees (best-of-N, tournament) and keep the most correct result, ranked by metric or by judges' Borda vote."
---

# agenthub-plus

A fork of agenthub (MIT, Alireza Rezvani) that works from a git worktree and adds judge voting, adapted from horse-race (MIT, qiao). Licenses are in the repo's `LICENSES/` folder. The scripts sit in `scripts/` next to this file; call them as `python3 <this skill's base directory>/scripts/<name>.py`. Run every script from the base branch's worktree root, since session state lives in `.agenthub/` there.

**The winner is the most correct entry.** In metric mode that means the best metric among entries whose eval passes. In judge mode it means correct, then proven, then safe, then simple. Speed, size of the change and finish order never count.

## 1. Init

Pick a mode:

- **Metric mode:** the task has a number. `--eval` must print `<metric>: <value>` and exit non-zero when the entry is broken (tests fail), so a broken entry can never rank.
- **Judge mode:** the task has no number. `--gate` is the correctness check, such as the test suite or the build.

```bash
python3 scripts/hub_init.py --task "<task>" --agents 3 \
  --eval "<cmd>" --metric <name> --direction higher|lower [--tiebreak-metric <name>] \
  | --gate "<cmd>" \
  --eval-timeout 1800 --worktrees-dir <repo>/.claude/worktrees
```

`--worktrees-dir` creates one worktree per agent on `hub/<session>/agent-<i>/attempt-1`, branched from the current branch. Pick a gitignored directory. Show the user the session ID and the worktree paths.

## 2. Baseline (metric mode)

Run the eval command once in the base worktree and record `baseline: <value>` in `.agenthub/sessions/<session>/config.yaml`.

## 3. Spawn

Launch every agent in **one message**, one Agent call each. Don't pass `isolation` (the worktrees already exist). Give each agent a different strategy. One that has worked: split the target into separate areas, one per agent. Each prompt states:

- its absolute worktree path, and that every command runs there and nothing touches other worktrees
- the task, the eval/gate command, the metric and the baseline
- the loop: find a gap, change it, run the eval or gate, keep the change only if the result improved and still passes, otherwise revert. Up to 10 iterations.
- staging by explicit path only (never `git add .` or `-A`), committing in a short call of its own, never pushing
- the repo's own rules for numerics, naming, forbidden directories and command wrappers
- writing its result to `.agenthub/board/results/agent-<i>-result.md` in the base worktree: final metric, what it changed, what it could not do and why, and any bugs it found but was not allowed to fix

## 4. Evaluate

**Metric mode.** Re-run the evals yourself; don't trust the agents' reports.

```bash
python3 scripts/result_ranker.py --session <id> --baseline <value>
```

Direction, tie-break metric and timeout come from the session config. An entry whose eval fails ranks last, shown as `FAILED`.

**Judge mode:**

1. `python3 scripts/borda.py prepare --session <id>` runs the gate in every worktree. Failing entries are disqualified and their gate output is kept as the reason. For the survivors it writes `candidate-<LABEL>.diff` under `.agenthub/board/judging/<id>/`, shuffled so labels carry no agent number, plus a different presentation order per judge. If fewer than 2 survive, there's no vote.
2. Spawn **3 fresh judges in one message**. They must not be the agents that wrote the entries. Give each the task, the path to the judging folder, its own `order-judge-<i>.txt`, and the read-only base checkout. Each `prepare` starts a fresh round and wipes earlier ballots. The label-to-agent map is in `.agenthub/sessions/<id>/judging-mapping.json`; never show it to a judge or name an agent to one. Judges write only their own ballot file; `tally` ignores any other `ballot*` file and reports it. Judge prompt:

   > You are Judge {i}. You wrote none of these solutions. Rank every candidate in `{dir}` (read them in the order in `order-judge-{i}.txt`) from best to worst for this task: {task}.
   > Rank on these criteria, in this order:
   > 1. **Correct**: does what the task asks, with no bugs; edge cases and failure paths handled; nothing outside the task broken.
   > 2. **Proven**: tests or other evidence actually exercise the claim. An assertion that cannot fail proves nothing.
   > 3. **Safe and fits the repo**: follows the repo's rules (read its CLAUDE.md/AGENTS.md); no weakened checks, suppressions or skipped tests.
   > 4. **Simple**: the smallest change that is correct.
   >
   > Speed, size of the change and finish order are not criteria. Read the code the diffs touch, not just the diffs. Write `{dir}/ballot-judge-{i}.json` as `{"ranking": ["B","A","C"], "evidence": {"B": "<file:line or test name that makes it the best>", ...}, "reasons": {"A": "...", ...}}`. A ballot with no evidence for its first choice is discarded.
3. `python3 scripts/borda.py tally --session <id>`. With N candidates, first place earns N-1 points and last earns 0. Ties on points break on first-place votes. **Exit 3** means the top is still tied: spawn one more fresh judge with only the tied diffs and the other judges' reasons, have it rank **only the tied labels** into `ballot-judge-tiebreak.json` (with evidence for its pick), and tally again. The tally that finds the tie records a one-time `"tie"."nonce"` in `judging-mapping.json` and deletes any tiebreak ballot already there. Give that nonce to the tiebreak judge only; its ballot must include `"nonce": "<value>"`. **Exit 2** means no valid ballot: re-run the judges.

## 5. Verify the winner

Before you offer a merge, run the full check (whole test suite or build) on the winning branch yourself. Agents' iteration loops usually run only a subset. If the winner fails, take the next entry.

## 6. Confirm and merge

Show the user the ranking: metric table, or Borda points with each judge's reasons. Include the disqualified entries and their reasons, and every bug the agents reported. **Ask before merging.** On a yes:

```bash
git merge --no-ff hub/<id>/<winner>/attempt-1 -m "<what the winner did>"
git tag hub/archive/<id>/<agent> hub/<id>/<agent>/attempt-1   # for each loser
git worktree remove <path> && git branch -D hub/<id>/<agent>/attempt-1   # for each agent
```

Opening a PR is a separate step and follows the repo's usual PR rules.

## Rules

- Never auto-merge, never push from an agent, never let an agent edit another worktree.
- Every agent is a Claude subagent. Don't start other vendors' CLIs.
- Report the agents' findings in full; a bug an agent found is a result even when its entry lost.
