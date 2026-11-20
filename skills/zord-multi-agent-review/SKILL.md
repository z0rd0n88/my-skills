---
name: zord-multi-agent-review
description: 'This skill should be used when the user asks to "review this PR", "audit this dir", "review this spec", "review my diff", or "loop review until clean", or mentions multi-agent review. PR targets loop review→fix; not for one named reviewer.'
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Agent
  - Skill
  - TaskCreate
  - TaskUpdate
---

# zord-multi-agent-review

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ `pr` reviews loop and mutate by default** — they edit, commit, and push
> to the PR's branch (1 round by default, up to 8 with `--max-iterations`) unless
> `--no-loop` is passed; `--adversarial` verifies findings first, at ~4.3× the
> token cost.

Runs N reviewer agents in parallel over a PR, directory, file, spec, diff, or
slice set and merges their findings into one prioritized report. Every target
is read-only except `pr`, which by default runs one review→fix round;
`--max-iterations` adds re-review rounds until APPROVE, the cap, or a safety stop.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<target-type>` | `pr` \| `dir` \| `file` \| `spec` \| `diff` \| `slices` | required | What to review; `pr` loops (mutating) by default. |
| `<target-args>` | PR number/URL; dir path; one file; 1+ spec paths; none for `diff`; 2+ dirs for `slices` | required | The target(s). |
| `--reviewers <csv>` | agent names | context-aware selection (fallback: `architect-reviewer`, `critical-thinking`, `silent-failure-hunter`, `security-reviewer`, `penetration-tester`) | Replace the roster; unknown names hard-fail. |
| `--synthesizer <name>` | agent name | `knowledge-synthesizer` | Name the merging role; the synthesizer runs as a fork, so no agent definition loads (§8). |
| `--write-to <path>` | file path | `.claude/reviews/<date>-<slug>.md` in the primary checkout, git-ignored | Override the report path; a tracked path is the rare opt-in for committing a report. Refuses to overwrite without `--force`. |
| `--no-write` | flag | off | Print only, write no file; conflicts with `--write-to`. |
| `--no-comment` | flag, `pr` only | off | Skip the PR comment carrying the report. |
| `--force` | flag | off | Let `--write-to` overwrite an existing file. |
| `--max-files <n>` | integer | 50 | Per-slice file cap for `dir`/`slices`. |
| `--max-slices <n>` | integer | 6 | Slice cap for `slices`. |
| `--staged` | flag, `diff` only | off | Review staged changes instead of the working tree. |
| `--mode <name>` | preset name | none | Load a preset from `.claude/multi-agent-review-modes/<name>.md` or `<plugin-install-root>/modes/<name>.md`; none ship with the plugin. |
| `--prompt-prelude <path>` | file, ≤16 KB | none | Prepend project context to reviewer, refuter, and synthesizer briefs. |
| `--lenses <csv>` | up to 5 of `pre-mortem`, `inversion`, `first-principles`, `red-team`, `jobs-to-be-done` | none | Add one reasoning-lens reviewer per slug; hard-fails on a looping `pr` (pass `--no-loop`). |
| `--high-cap <n\|off>` | integer or `off` | 8; `off` in loop mode | Demote HIGH findings beyond the cap to MEDIUM. A caller that gates on a one-shot review passes `off` (§5.0 step 3c). |
| `--inline` | flag | off | Run a one-shot review in the caller's context. |
| `--no-report-audit` | flag | off | Skip the report-fidelity audit. |
| `--adversarial` | flag | off | Refute every finding before synthesis (~4.3× median cost). |
| `--no-adversarial` | flag | n/a | No-op restating the default; hard-fails with `--adversarial`. |
| `--refuters <n>` | integer 1–5 | 3 | Refuters per CRITICAL/HIGH finding; requires `--adversarial`. |
| `--max-refuters <n>` | integer ≥ 1 | 20 | Refuter budget per review pass; requires `--adversarial`. |
| `--no-loop` | flag | off | Make a `pr` review one-shot and read-only (no-op elsewhere). |
| `--yes` | flag, looping `pr` only | off | Skip the confirmation gate for unattended runs. |
| `--max-iterations <n>` | integer 1–8 | 1 | Cap review→fix→re-review rounds. |
| `--resume-stopped` | flag, looping `pr` only | off | Resume a `STOPPED_*` checkpoint after a human judged it safe. |
| `--high-and-up-only` | flag, looping `pr` only | off | Auto-defer MEDIUM/LOW; only CRITICAL/HIGH drive rounds. |
| `--no-smoke` | flag, looping `pr` only | off | Skip the live smoke test even when a fix touched smoke-covered code. |

## 1. Purpose

Run a fan-out/fan-in review: dispatch reviewers over the same materials in parallel, let refuters try to disprove each finding under `--adversarial` (§5A.5a), merge the survivors with a synthesizer, and audit the result with a report adversary (§5A.6a).

- **One-shot** (every non-`pr` target, and `pr --no-loop`): dispatch it to an orchestrator subagent (§5A.0) so worker transcripts stay out of the caller's context; `--inline` opts out.
- **Loop** (a `pr` target by default): pass the confirmation gate (§5.0; `--yes` skips it), then run each review round in a fresh subagent (§10.2), triage, apply fixes through a dispatched specialist or the coordinator itself (§10.4), verify each one (§10.4b, stricter for CRITICAL), commit, and push, until APPROVE, the round cap, or a safety stop. Run the coordinator inline, since it mutates and must stay watchable. Forward the caller's `--adversarial` choice to every round.

## 2. When to use

Use it for "review this PR", "audit PR <n>", "iterative review on PR #N", "loop the review until clean on PR #N", "review-fix-review PR #N", "review `core/`", "review this file", "review the spec and its amendment", "do a multi-agent review of …", or an explicit `zord-multi-agent-review …`.

- For a one-agent review, call that agent directly.
- For a PR that merges regardless of findings, run `--no-loop` instead of a loop.

## 2a. Hard rules

Apply these on every run except `-h`; each prevents a silently lost or corrupted run.

1. **Block on every dispatch.** Set `run_in_background: false` on every `Agent` call at every layer, with no exceptions and no list of roles to check: a backgrounded child reports to the top-level session, so its spawner's turn ends and nothing downstream runs.
2. **Mutate only in a looping `pr`.** Treat every other target and every `--no-loop` run as read-only, and state which mode applies before starting.
3. **Relay a one-shot report whole or by its file.** With a report file, a dispatched orchestrator returns only the §5A.0 summary, and a caller that must triage or fix findings reads the file. Otherwise print or return the synthesized report in full. When the report cannot fit in one message, or in one PR comment (GitHub caps a comment body at 65,536 characters), split it: every CRITICAL and HIGH finding verbatim, MEDIUM and LOW as tables anchored to `file:line`, and the report's file path always. The split moves findings out of the message, never out of the relay: nothing is dropped. End a loop with its §10.7 report instead.
4. **Never fake the roster.** When a one-shot orchestrator returns `DISPATCH-FAILED` or `INCOMPLETE:`, re-run inline with a one-line note (§11). In loop mode, stop with `STOPPED_DISPATCH_UNAVAILABLE` (§10.6) and never fall back to inline. Never accept one agent's report presented as a multi-lens review. Dispatching the reviewer agents yourself and skipping §5A.6 (synthesize) or §5A.6a (report audit) is faking the roster too; if the worry is the nested-subagent notification stall, the answer is `--inline`, which still owes both stages (`references/workflow.md` §5A.0).
5. **Never nest loops.** Never start loop mode inside another loop skill (`zord-baton-runner`): nesting loses a deterministic finish and multiplies agents.

## 2b. Load map

Load only what the current path needs.

| Path | Load before acting |
|---|---|
| `-h` / `--help` | nothing; print the block above |
| Every other run | [`references/flags.md`](references/flags.md) to parse, then [`references/workflow.md`](references/workflow.md) (§5) |
| Building any agent brief | [`references/agent-briefs.md`](references/agent-briefs.md) (§7, §8) |
| Mapping a request onto flags | [`examples/invocations.md`](examples/invocations.md) |
| Looping `pr` | also [`references/loop-coordinator.md`](references/loop-coordinator.md) (§10), [`references/defaults.md`](references/defaults.md) ("Loop defaults"), [`references/anti-patterns.md`](references/anti-patterns.md) (§12) |
| A hard-fail, warning, or degraded run | [`references/error-handling.md`](references/error-handling.md) (§11) |
| Recommending `--adversarial` or not | [`references/adversarial-rationale.md`](references/adversarial-rationale.md) |
| Changing a default or design | `references/defaults.md` (§4), [`references/resolved-decisions.md`](references/resolved-decisions.md) (§13) |

## 3. Invocation grammar

```
zord-multi-agent-review <target-type> <target-args...> [flags]
zord-multi-agent-review pr 42              # loop, after the confirmation gate
zord-multi-agent-review pr 42 --no-loop    # one-shot, read-only
```

> Maintainer note: after changing a flag, run `scripts/check_flag_tables.py` (the repo pre-commit hook also runs it); it fails when the `-h` table and `references/flags.md` list different flags.

## 4. Defaults

Treat the `-h` table as canonical for flag defaults; `references/defaults.md` holds §4 in full. Also apply:

- **Roster.** Use `--reviewers`, else the `--mode` preset, else context-aware selection (§15; soft cap 6 per slice), else the `-h` fallback roster. If `penetration-tester` (lane `L-REDTEAM`) is absent from the pool, drop it, note the gap, and run the other four. Absent means the lookup (`refs/multi-agent/agent-catalog-lookup.md`) ran and did not find it: a listing that failed is not a pool, so a lookup error is a hard-fail to fix before dispatch, never grounds to drop a lane.
- **Output.** A `pr` target's report goes to one PR comment, the primary destination, independent of the file. The file is a local copy, written per §5A.1 step 10 to `.claude/reviews/<date>-<slug>.md` (appending `-2`, `-3`, … on a same-day collision) in the primary checkout (`git rev-parse --git-common-dir`), never a linked worktree's top level, which dies with the worktree; checkpoints share that base. Both stay git-ignored (§5A.1 step 10); take any tracked-or-ignored claim from `git check-ignore`, never from memory. Committing a report is rare and always an explicit opt-in: `--write-to` a tracked path, then commit it yourself. The skill never commits a report. When a written file is not ignored and names unfixed CRITICAL/HIGH security findings, say so in the closing output (§5A.7 defines the line).

## 5. Workflow

Run these steps in order; when dispatched, the orchestrator subagent runs §5A.1–§5A.7:

- [ ] §5.0 Parse; choose `mode` (one-shot/loop) and `dispatch` (subagent/inline).
  On empty args, before the usage line, run `gh pr view --json number` for the current branch and *offer* `pr <N> --no-loop --no-comment` as a proposal only (never auto-run: a bare `pr <N>` loops and mutates); with no PR, print the one-line usage.
- [ ] §5A.0 Dispatch the orchestrator, or continue inline.
- [ ] §5A.1 Validate flags; hard-fail before any agent spawns.
- [ ] §5A.2 Resolve materials; §5A.3 build briefs (§7).
- [ ] §5A.4 Spawn all reviewers at once (§6); §5A.5 reconcile the returns.
- [ ] §5A.5a Refute (`--adversarial` only).
- [ ] §5A.6 Synthesize (§8); §5A.6a audit the report. Both stages are owed on every path, `--inline` included.
- [ ] §5A.7 Print the report (Hard rule 3).
- [ ] Loop mode: run §5B and §10 instead, where each round runs §5A.1–§5A.7 in a fresh subagent.

## 6. Parallelism rule

Emit every reviewer `Agent` call in ONE message; serial dispatch multiplies latency by the roster size. Dispatch refuters the same way, batched at the 16-per-turn ceiling in `../../refs/multi-agent/fanout-consolidation.md`: fill each turn, then start the next, never one turn per claim. Batch per this rule; block per Hard rule 1.

## 7. Agent brief templates

Build each brief from its exact template: §7 reviewer, §7a refuter, §7b report adversary, §7c orchestrator, §7d fix verifier, §7e fix applier.

## 8. Synthesizer brief

Merge reviewer and refuter output with the §8 template. Whenever refutation ran, state its arithmetic in the Executive Summary so `UNVERIFIED` never reads as validated.

Dispatch the synthesizer, and the §7b report adversary, with `subagent_type: fork` from the context that collected the reviewer returns. A fresh subagent sees reviewer output only as text retyped into its brief, and retyping silently truncates the material both roles exist to audit; a fork inherits the returns verbatim, so `{{REVIEWER_OUTPUTS}}` and §7b's `{{SYNTHESIZED_REPORT}}` expand to a pointer at them, never a copy. A fork carries no frontmatter restrictions, so each brief states its read-only rule inline. A fork also runs on the parent's model with no agent definition, so the §8 brief replaces the `--synthesizer` lookup, the way a lens directive replaces it for a lens slot (§7): `--synthesizer` and a mode's `synthesizer` still validate (§5A.1) but load nothing, and when either names a non-default agent, add a `## Notes` bullet saying its definition was not loaded.

## 9. Critical-thinking integration

Report `critical-thinking` output (assumptions, missing context, questions) in its own "Unstated Assumptions and Open Questions (from critical-thinking)" section, never in the severity buckets. Omit the section when that agent is not in the roster, and exempt its output from refutation (§5A.5a step 1): a question makes no claim to disprove.

## 10. Loop coordinator

Run each round in order: §10.1 state → §10.2 round subagent → §10.3 triage → §10.4 fixes (§10.4a parallel, §10.4b verify) → §10.5 commit and push → §10.6 stop checks → §10.7 final report (§10.7a per-round detail).

## 11. Error handling

Word every hard-fail, warning, and degraded-run message exactly as the §11 table does.

## 12. Anti-patterns

Check the §12 list before triaging or fixing in loop mode.

## 13. Resolved decisions

Check the §13 log, which also maps design choices to external evidence, before reopening a settled question.

## 14. Composition with other skills

- Inside loop mode, use the project's TDD, debugging, or language-review skills and agents when they help apply a fix, and run a one-shot `--no-loop` review as a sanity check after a contested fix.
- Embed one-shot mode anywhere, including inside other loop skills; loop mode never nests (Hard rule 5).

## 15. Shared primitives

Reuse the primitives in `../../refs/multi-agent/`, shared with `zord-total-review`: `fanout-consolidation.md` (fan-out, dedupe, severity budget), `agent-catalog-lookup.md` (name resolution), `exclusion-list.md` and `spec-injection.md` (both via `--prompt-prelude`; one prelude file may concatenate both under their headings), `reasoning-lenses.md` (`--lenses` directives), `context-aware-selection.md` and `lane-agent-table.md` (roster selection).
