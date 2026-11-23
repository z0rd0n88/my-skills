# Why adversarial refutation exists, and why it's opt-in

### Why refutation exists

Every other quality guard in this skill defends against **false negatives** — the `### Validated` coverage report (§7), the engagement check (§8), `[DID NOT ENGAGE]` tagging, the empty-coverage APPROVE gate (§10.3). Nothing defended against **false positives**, and `--high-cap` is not that guard: it ranks and demotes surplus HIGHs by *count*, never asking whether any individual finding is true.

That asymmetry is most expensive in loop mode, where §10.3 auto-actions every CRITICAL and HIGH: a plausible-but-wrong HIGH becomes a real edit committed and pushed to someone's PR. Severity buckets reward manufacturing findings — any reviewer can produce a confident MEDIUM — and nothing in a fan-out punishes it. Refutation is the missing half: it makes a finding pay for its severity with evidence that survives attack.

### Why it is opt-in

Refutation is the single most expensive thing this skill can do. Measured across real transcripts after the stage shipped default-on: the median review session went from **10.0M to 43.2M billable tokens (~4.3×)**, the subagent share of that spend rose from **59% to 84%**, and refuter agents alone accounted for **57.8% of all subagent tokens** at a mean of **~0.38M tokens per refuter**. One session dispatched **163 refuters**.

Refutation pays for itself exactly where a wrong finding causes an irreversible action without a human in between — that is loop mode's auto-fix path (§10.3), where a false HIGH becomes a real commit. On a read-only one-shot report the reader *is* the refuter: a false finding costs one paragraph of attention, not a bad commit, and paying 4× to pre-filter what a human is about to read anyway is a poor trade.

- **Reaching for `--adversarial`:** looping a `pr` with `--yes`, any unattended or automated run, a merge gate whose verdict feeds a pipeline, a large roster where cross-reviewer noise is likely, or a diff on a money / keys / migration path where findings will be acted on without a re-read.
- **Leaving it off:** read-only one-shot reports the caller will read directly, a small or single-reviewer roster, exploratory sweeps, and anything where an over-inclusive list is preferable to paying to trim it.

### What outside evidence says

- **The design is a known pattern.** Anthropic's [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (Dec 2024) gives vulnerability review by several *differently prompted* reviewers as its example of parallel voting, and notes that vote thresholds trade false positives against false negatives. Refuter lenses (diversity by prompt, not by copies) and severity-scaled majorities are that pattern.
- **Debate is not a free win.** Multi-agent debate improved factuality and reasoning in [Du et al.](https://proceedings.mlr.press/v235/du24e.html) (ICML 2024), but did not reliably beat cheaper ensembling such as self-consistency and was sensitive to configuration in [Smit et al.](https://proceedings.mlr.press/v235/smit24a.html) (ICML 2024). That supports keeping refutation opt-in and spending it where a false finding becomes a commit.
- **Refute from evidence, never from re-reasoning alone.** Without external feedback, models asked to self-correct turn correct answers wrong more often than the reverse ([Huang et al.](https://arxiv.org/abs/2310.01798), ICLR 2024). The §7a brief therefore makes each refuter open the cited code before ruling, and counts "found nothing" as `UNCERTAIN`, which upholds the finding.
- **Same-model refuters are not independent votes.** Errors correlate across similar models ([Goel et al.](https://arxiv.org/abs/2502.04313), ICML 2025; [Kim et al.](https://arxiv.org/abs/2506.07962), ICML 2025), and mixing providers only partly helps for strong models. Lens diversity is this skill's partial answer; model diversity across refuters is untested here.

`--refuters` and `--max-refuters` still tune the stage; both require `--adversarial` and hard-fail without it (§11) rather than silently doing nothing.
