# Multi-Agent Review

Parallel multi-perspective code review with a synthesizer that dedupes findings across reviewer lenses. A `pr` target loops review → fix → re-review by default until the PR is clean; everything else is a one-shot read-only report.

Built around the insight that **single-agent review is a thin filter** and **multi-agent review without coordination is noise** — what's needed is parallel fan-out plus a synthesis layer that catches what each reviewer missed without re-reporting what they all caught.

## The skill

| Skill | What it does | Command |
|---|---|---|
| [`multi-agent-review`](./skills/multi-agent-review/SKILL.md) | Parallel review over a target (PR/dir/file/spec/diff/slice set): N reviewer agents fan out, a synthesizer merges the reports into one prioritized verdict. A `pr` target **loops review→fix→re-review by default** (`--no-loop` for a one-shot read-only report); each round runs the review in a fresh subagent so reviewer transcripts never bloat the coordinator's context. Read-only for all non-`pr` targets and with `--no-loop`. | `/multi-agent-review` |

## Bundled shared primitives

The `refs/multi-agent/` directory ships the contracts this skill (and any future multi-agent skill in your toolkit) builds on:

| Ref | What it codifies |
|---|---|
| [`fanout-consolidation.md`](./refs/multi-agent/fanout-consolidation.md) | Parallel-fan-out contract, dedupe rules, cross-axis severity budget (caps total HIGH so N reviewers each finding "one HIGH" doesn't = N blockers). |
| [`agent-catalog-lookup.md`](./refs/multi-agent/agent-catalog-lookup.md) | How `--reviewers <csv>` names resolve against the project active catalog + user-scope parked tier. |
| [`context-aware-selection.md`](./refs/multi-agent/context-aware-selection.md) | Signal-driven lane activation used when `--reviewers` is omitted — which coverage lanes a target needs, and how many. |
| [`lane-agent-table.md`](./refs/multi-agent/lane-agent-table.md) | Deterministic lane→agent resolver, including the `L-REDTEAM` vs `L-ADVERSARIAL` distinction and the one-agent-one-lane rule. |
| [`exclusion-list.md`](./refs/multi-agent/exclusion-list.md) | The "DO NOT report findings already tracked" discipline that prevents recurring sweeps from re-reporting open issues. |
| [`spec-injection.md`](./refs/multi-agent/spec-injection.md) | How to inject the originating spec/issue into reviewer briefs so they can raise CRITICAL if the diff fails to satisfy the originating intent. |
| [`reasoning-lenses.md`](./refs/multi-agent/reasoning-lenses.md) | The inlined reasoning-model directives behind `--lenses` (and `reasoned-review`) — why they're inlined rather than invoked as skills, the steel-man stance, and the per-slug directive text. |

## What makes this different from "run a code reviewer agent"

Seven load-bearing properties most ad-hoc review setups miss:

1. **Parallel, not sequential.** Reviewers run as concurrent agent tool calls in a single dispatch. Sequential review lets later reviewers anchor to earlier findings instead of reasoning fresh.
2. **Synthesizer is a separate role.** Reviewers produce raw findings; a synthesizer agent dedupes and prioritizes. Reviewers don't see each other's output. The skill prints only the synthesized verdict — raw reviewer transcripts stay sandboxed, and since 2.2 they stay in a dispatched orchestrator subagent so they never touch your session's context at all.
3. **Adversarial refutation of every finding — opt-in via `--adversarial`.** Severity buckets reward manufacturing findings — any reviewer can produce a confident MEDIUM, and nothing in a plain fan-out punishes it. Before synthesis, each finding faces independent refuters on different lenses (does the cited line actually say that? is it in scope for this diff? is the failure path even reachable?). The lens mix adapts to the target: MEDIUM and LOW findings get the reachability lens on a risk-flagged diff — where "can this actually happen?" is the whole question — and the scope lens elsewhere, where the common false positive is instead a pre-existing pattern the diff never touched. Majority-refuted findings are dropped — into a **Refuted Findings** section with every refuter's reasoning, never silently — split verdicts are demoted, survivors are tagged verified. This matters most in loop mode, where the coordinator auto-fixes every CRITICAL and HIGH: without it, a plausible-but-wrong HIGH becomes a real commit pushed to your PR. It is **off by default as of 3.0** because it roughly quadruples a run's token cost, and that price only pays for itself where no human reads the findings before something irreversible happens — see "What's new in 3.0" below.
4. **Adversarial audit of the report itself — on by default (3.1).** Refutation attacks findings against the code; nothing attacked the *report* against its own inputs. Synthesis is where dedupe, the severity budget, refutation-outcome application, and the Executive Summary all get decided, so defects of that kind are created after the last reviewer finishes and are invisible to every earlier check. One agent, between synthesis and print, compares the finished document to the reviewer outputs and refutation verdicts: a DROPPED finding still sitting in a severity bucket, two distinct causes merged into one entry, a HIGH demoted to fit the cap rather than on merit, a summary whose arithmetic doesn't reconcile with its own sections. It appends a `## Report Audit` section and changes nothing else — the synthesized body stays verbatim, so you can overrule the auditor as easily as the synthesizer. One agent per pass whatever the report contains, which is why it is default-on where refutation is not. `--no-report-audit` skips it.
5. **Cross-axis severity budget.** If 4 reviewers each surface "one HIGH," that's not 4 blockers — it's noise that needs ranking. The budget demotes excess HIGHs to MEDIUM with explicit rationale. (In loop mode the budget is forced `off` so no HIGH is hidden from the iteration gate.) It runs on refutation survivors, so it never spends the cap ranking findings that are about to be dropped.
6. **Exclusion-list discipline.** Open tracker issues are injected verbatim into every reviewer's prompt under a "DO NOT report" heading. Recurring sweeps stay quiet on issues you've already triaged. In loop mode, findings refuted in an earlier round are carried forward through the same channel, so stateless reviewers stop rediscovering dead claims every round.
7. **Target taxonomy.** `pr`, `dir`, `file`, `spec`, `diff`, and `slices` (fan-out across N directories with cross-slice meta-synth). Most review tools cover only `pr` or only `diff`; the spec/slices forms are rare and load-bearing.

## Install

```bash
claude plugin marketplace add z0rd0n88/z0rd0nlander
claude plugin install my-skills@z0rd0nlander
```

## Use

Iterate until clean on PR 42 (the default for a `pr` target — prompts before mutating):

```bash
/multi-agent-review pr 42
```

One-shot read-only review of an open PR:

```bash
/multi-agent-review pr 42 --no-loop
```

Loop unattended (skip the confirmation gate), capped at 5 rounds:

```bash
/multi-agent-review pr 42 --yes --max-iterations 5
```

Layer-sliced review of a hex-arch repo with project-defined skip-list:

```bash
/multi-agent-review slices src/foo/domain/ src/foo/application/ src/foo/adapters/ \
  --mode code --prompt-prelude .claude/multi-agent-review-modes/skip-list.md
```

Turn on adversarial refutation — worth it on an unattended loop that auto-fixes what it finds:

```bash
/multi-agent-review pr 42 --yes --adversarial
```

Raise the refuter budget above the default 20 on a finding-rich target, so fewer findings come back `UNVERIFIED`:

```bash
/multi-agent-review pr 42 --adversarial --max-refuters 40
```

## Plugin 3.1.0 (#218)

A caller that gates on a one-shot review passes `--high-cap off` itself, and the orchestrator's summary reports the cap and lists budget-demoted findings on `Cap:` and `Demoted:` lines.

## What's new in 3.1

Two additions, both backward-compatible. Nothing that worked in 3.0 changes meaning.

**1. A report adversary (§5A.6a), on by default.** One agent between synthesis and print that attacks the *report* instead of the findings — see design property 4 above. Placement is the whole point: it runs after synthesis because the artifact doesn't exist before then, and before print because the orchestrator must return a single document. It appends `## Report Audit`, never edits the body, and never blocks — a failed audit prints `Not run (audit agent failed).` and the report goes out anyway. In loop mode the coordinator reads audit items but never actions them; they're statements about a document, not defects in your code. `--no-report-audit` opts out.

**2. Refuter lenses now name a technique.** Each lens in §5A.5a maps to a `thinking-skills` skill that supplies a method, rather than leaving the refuter to improvise one from a one-line prompt:

| Lens | Technique |
|---|---|
| Evidence | `thinking-map-territory` — the claim is the map, the code is the territory |
| Scope | `thinking-kepner-tregoe` — what IS vs IS-NOT covered by this target |
| Reachability | `thinking-red-team` on a risk-flagged target, else `thinking-thought-experiment` |
| Severity | `thinking-second-order` — walk the consequence chain |
| Fix | `thinking-via-negativa` — does removal beat addition? |

Strictly optional. `thinking-skills` is a separate plugin and **not** a dependency; the lens question stays authoritative, and a refuter whose skill won't load rules normally. It is explicitly forbidden from returning `UNCERTAIN` over a missing skill — `UNCERTAIN` upholds findings, so that would quietly turn an uninstalled plugin into a bias toward keeping them.

## What's new in 3.0

**Adversarial refutation is now opt-in.** It was default-on in 2.1–2.2; it is off unless you pass `--adversarial`. This is the only breaking change, and the migration is one flag.

Why it changed — measured across real transcripts after 2.1 shipped:

| | before refutation | after (default-on) |
|---|---|---|
| median session | 10.0M billable tokens | **43.2M (~4.3×)** |
| subagent share of spend | 59% | **84%** |

Refuters alone accounted for **57.8% of all subagent tokens**, at ~**0.38M tokens each**. One session dispatched **163** of them.

The stage still does exactly what 2.1 claimed. The reversal is about *where the guarantee is load-bearing*: refutation earns its cost when a false finding causes an irreversible action with no human in between — the loop's auto-fix path. On a read-only report you were going to read anyway, you are already the refuter, and pre-filtering that list at 4× is a bad trade.

- **Migration:** add `--adversarial` to any invocation that relied on the 2.1/2.2 default. `--no-adversarial` still parses (accepted no-op), so existing scripts don't break — they just now state the default.
- **`--refuters` / `--max-refuters` require `--adversarial`** and hard-fail without it, rather than silently doing nothing. They never *imply* it — a flag that reads like "spend less" must not switch on the expensive path.
- **Unattended loops still get nudged.** A looping `pr` with `--yes` and no `--adversarial` prints one note at loop start saying auto-fix will act on unchallenged findings. A note, not a block.
- **`--max-refuters` default lowered `60` → `20`.** A live verification run on a single 135-line file produced 13 finding groups needing 28 refuters, 22 of them for MEDIUM/LOW — at 60 the budget never bound, so a routine one-file review would have spawned all 28. Trade-off, stated plainly: degradation starts sooner, so finding-rich reviews now carry a visible `UNVERIFIED` tail. `UNVERIFIED` means *nobody challenged this*, not *this survived challenge*; the Executive Summary always states the arithmetic. Raise the flag when a run needs full coverage.
- **`--max-refuters` is per review pass, not per session** — now documented as such. A loop forwards it to every round, so budget `--max-iterations × --max-refuters`; at the new defaults that is 60, not 20. This was always the behavior; only the documentation changed.

## What's new in 2.2

**One-shot reviews run in a dispatched orchestrator subagent by default**, on every target. Your session gets a summary and the report's path; the reviewer, refuter, and synthesizer transcripts stay in the orchestrator's window. This matters more since 2.1 — a 5-reviewer run over 20 claims spawns ~50 refuters, and inline that was ~50 transcripts landing in a context meant to hold a conversation.

- **Since 2.3 the executive summary, counts and report path come back**, and the file holds every section, finding and refuter rationale. With `--no-write` the report comes back in full. The caller checks the file or return actually holds a complete report before printing anything.
- **`--inline`** runs it in place, as before 2.2.
- **The loop coordinator is never dispatched.** It edits, commits, and pushes, so it stays visible in your session. Loop *rounds* already had their own subagent — that's the same layer, now documented as a deliberate two-layer contract (orchestrator → workers, never deeper).
- **Depth failures are loud.** If the orchestrator can't spawn workers it returns `DISPATCH-FAILED` and the review re-runs inline. It will not quietly let one agent impersonate a five-lens roster — that produces a report shaped like multi-perspective review with none of the independence, and refuters sharing an author with the findings.

## What's new in 2.1

**Adversarial refutation** (§5A.5a) runs by default on every target, between fan-out and synthesis. Additive and non-breaking — no flag changes meaning, and `--no-adversarial` restores exactly the 2.0 pipeline. *(Superseded in 3.0: the stage is unchanged, but it is now opt-in via `--adversarial`.)*

What changes in practice:

- Reports gain a **Refuted Findings** section (with an *Unverified (budget exhausted)* subsection) and per-finding `_(verified: …)_` / `_(contested: …)_` tags. The Executive Summary states the refutation arithmetic.
- Findings you'd previously have seen as HIGH may now appear as MEDIUM (contested) or under Refuted Findings — with the reasoning attached, so you can overrule any drop.
- The default roster gains `penetration-tester` in a new `L-REDTEAM` lane. It's the one safety-net name allowed to be missing without hard-failing: if it isn't in your pool, the other four run with a noted gap.
- Loop mode: the coordinator no longer fixes refuted findings, and carries them into later rounds' exclusion prelude so reviewers stop rediscovering them.
- Runs cost more agents. Budget with `--max-refuters` (default 60, per review pass). *(In 3.0 the stage is off unless `--adversarial` is passed, and the default budget is 20.)*

## Migrating from 1.x

v2.0.0 is a breaking release, on two counts:

1. **The default on a `pr` target flipped read-only → mutating.** `multi-agent-review pr 42` now loops review→fix→re-review (edits files, commits, pushes on the PR's head branch), behind a confirmation gate — pass `--yes` to skip the gate for unattended runs, or `--no-loop` to get the 1.x one-shot read-only report. Non-`pr` targets (`dir`/`file`/`spec`/`diff`/`slices`) are unchanged: always one-shot read-only.
2. **`/multi-agent-review-loop` is removed** (both the command and the skill — no alias). Replace any `multi-agent-review-loop <ref>` / `/multi-agent-review-loop <ref>` invocation with `multi-agent-review pr <ref>` (add `--yes` for unattended/orchestrated callers). The loop's flags (`--max-iterations`, `--high-and-up-only`, `--no-smoke`) carry over unchanged and are valid only on a looping `pr` target.

## Composition with other skills

This plugin pairs with the rest of the multi-agent stack:

| Layer | Skill | Where it lives |
|---|---|---|
| Code → findings / Findings → APPROVE on existing PR | **`multi-agent-review`** | this plugin |
| Queue of specs → APPROVE | `baton-runner` | [sibling skill in my-skills](../baton-runner) |
| Pattern library for repo-wide review sweeps | [`total-review`](../total-review) | sibling skill in my-skills |

`total-review` and `multi-agent-review` share the same `refs/multi-agent/` primitives. If you install both, the refs are duplicated in each plugin (intentional — each plugin stays self-contained). When you edit a primitive (e.g. the severity budget formula), keep the two copies in sync.

## Layout

```
multi-agent-review/
├── .claude-plugin/plugin.json
├── README.md
├── commands/
│   └── multi-agent-review.md
├── refs/
│   └── multi-agent/
│       ├── fanout-consolidation.md
│       ├── agent-catalog-lookup.md
│       ├── context-aware-selection.md
│       ├── lane-agent-table.md
│       ├── exclusion-list.md
│       ├── spec-injection.md
│       └── reasoning-lenses.md
└── skills/
    └── multi-agent-review/
        ├── SKILL.md
        └── references/
            ├── agent-briefs.md
            ├── anti-patterns.md
            ├── error-handling.md
            ├── loop-coordinator.md
            ├── resolved-decisions.md
            └── workflow.md
```

## License

[MIT](../../LICENSE).
