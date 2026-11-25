# Multi-Agent Review

Parallel multi-perspective code review with a synthesizer that dedupes findings across reviewer lenses. A `pr` target runs one review→fix round by default (`--max-iterations` adds re-review rounds, up to 8); everything else is a one-shot read-only report.

Built around the insight that **single-agent review is a thin filter** and **multi-agent review without coordination is noise** — what's needed is parallel fan-out plus a synthesis layer that catches what each reviewer missed without re-reporting what they all caught.

How to run it, its flags, the shared `refs/multi-agent/` primitives and how it composes with other skills are in [`SKILL.md`](SKILL.md) (the `-h` table, §3, §14, §15). The full decision history is in [`references/resolved-decisions.md`](references/resolved-decisions.md).

## What makes this different from "run a code reviewer agent"

Seven load-bearing properties most ad-hoc review setups miss:

1. **Parallel, not sequential.** Reviewers run as concurrent agent tool calls in a single dispatch. Sequential review lets later reviewers anchor to earlier findings instead of reasoning fresh.
2. **Synthesizer is a separate role.** Reviewers produce raw findings; a synthesizer agent dedupes and prioritizes. Reviewers don't see each other's output. The skill prints only the synthesized verdict — raw reviewer transcripts stay sandboxed, and since 2.2 they stay in a dispatched orchestrator subagent so they never touch your session's context at all.
3. **Adversarial refutation of every finding — opt-in via `--adversarial`.** Severity buckets reward manufacturing findings — any reviewer can produce a confident MEDIUM, and nothing in a plain fan-out punishes it. Before synthesis, each finding faces independent refuters on different lenses (does the cited line actually say that? is it in scope for this diff? is the failure path even reachable?). The lens mix adapts to the target: MEDIUM and LOW findings get the reachability lens on a risk-flagged diff — where "can this actually happen?" is the whole question — and the scope lens elsewhere, where the common false positive is instead a pre-existing pattern the diff never touched. Majority-refuted findings are dropped — into a **Refuted Findings** section with every refuter's reasoning, never silently — split verdicts are demoted, survivors are tagged verified. This matters most in loop mode, where the coordinator auto-fixes every CRITICAL and HIGH: without it, a plausible-but-wrong HIGH becomes a real commit pushed to your PR. It is **off by default as of 3.0** because it roughly quadruples a run's token cost, and that price only pays for itself where no human reads the findings before something irreversible happens — see "What's new in 3.0" below.
4. **Adversarial audit of the report itself — on by default (3.1).** Refutation attacks findings against the code; nothing attacked the *report* against its own inputs. Synthesis is where dedupe, the severity budget, refutation-outcome application, and the Executive Summary all get decided, so defects of that kind are created after the last reviewer finishes and are invisible to every earlier check. One agent, between synthesis and print, compares the finished document to the reviewer outputs and refutation verdicts: a DROPPED finding still sitting in a severity bucket, two distinct causes merged into one entry, a HIGH demoted to fit the cap rather than on merit, a summary whose arithmetic doesn't reconcile with its own sections. It appends a `## Report Audit` section and changes nothing else — the synthesized body stays verbatim, so you can overrule the auditor as easily as the synthesizer. One agent per pass whatever the report contains, which is why it is default-on where refutation is not. `--no-report-audit` skips it.
5. **Cross-axis severity budget.** If 4 reviewers each surface "one HIGH," that's not 4 blockers — it's noise that needs ranking. The budget demotes excess HIGHs to MEDIUM with explicit rationale. (In loop mode the budget is forced `off` so no HIGH is hidden from the iteration gate.) It runs on refutation survivors, so it never spends the cap ranking findings that are about to be dropped.
6. **Exclusion-list discipline.** Open tracker issues are injected verbatim into every reviewer's prompt under a "DO NOT report" heading. Recurring sweeps stay quiet on issues you've already triaged. In loop mode, findings refuted in an earlier round are carried forward through the same channel, so stateless reviewers stop rediscovering dead claims every round.
7. **Target taxonomy.** `pr`, `dir`, `file`, `spec`, `diff`, and `slices` (fan-out across N directories with cross-slice meta-synth). Most review tools cover only `pr` or only `diff`; the spec/slices forms are rare and load-bearing.

## Gating on a one-shot review

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
- **`--max-refuters` is per review pass, not per session** — now documented as such. A loop forwards it to every round, so budget `--max-iterations × --max-refuters`; at the default of one round that is 20, and a 3-round loop (`--max-iterations 3`) can dispatch 60. This was always the behavior; only the documentation changed.
