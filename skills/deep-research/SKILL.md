---
name: deep-research
description: Run a cost-guardrailed deep-research report — fan-out web search, adversarial claim verification, cited synthesis — with a mid-tier model on the bulk stages and a token-budget ceiling.
argument-hint: <research question>
user-invocable: true
---

# Deep Research (guardrailed)

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Spends a real multi-agent budget** — even the guardrailed `standard` depth
> fans out dozens of search/fetch/verify subagents per run, and the spend can't be
> undone once started.

Runs a cost-guardrailed deep-research report — fan-out web search, adversarial
claim verification, and cited synthesis — via the Workflow tool's
`deep-research.workflow.js` script. It keeps the high-volume stages on a mid-tier
model and enforces a token/agent budget ceiling, unlike the bare workflow, which
can fan out 80–95 uncapped subagents.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<question>` (required) | free text | — | The research question, passed as the `args` string to the Workflow script |
| `depth` | `quick` \| `standard` \| `deep` | `standard` | Preset fetch/claims/votes caps (5/6/2, 8/12/3, 15/25/3) |
| `maxFetch` | integer | preset value | Overrides number of sources fetched |
| `maxClaims` | integer | preset value | Overrides number of claims verified |
| `votes` | integer | 3 | Adversarial votes per claim |
| `models` | `{ verify, synthesize }` | `{ verify: sonnet, synthesize: opus }` | Overrides the model used per stage |

Produces a multi-source, adversarially fact-checked research report by running the
`deep-research.workflow.js` orchestration script via the **Workflow** tool. This skill's
instructions are the explicit opt-in that authorizes the Workflow call.

## Why this exists

The bare deep-research workflow fans out ~80–95 subagents per run (5 search + up to 15
fetch + up to 25×3 adversarial verify + synthesis) with **every agent inheriting the session
model** and **no token ceiling** — it can cost a fortune from an Opus session. This skill runs
a guardrailed port that keeps the adversarial rigor but controls the spend.

## Guardrails (built into the script)

- **Mid-tier model on the high-volume stages.** Scope / search / fetch / verify all run on
  `sonnet`; only final synthesis uses `opus`. This is the biggest cost lever — the mechanical,
  schema-constrained stages don't need a frontier model.
- **Token-budget ceiling.** The script reads the turn's `budget` global. If a `+N` budget
  was set, it trims the fetch/claim/vote caps up front and hard-gates the verify fan-out so a
  large claim pool can't blow the ceiling. Trimmed items are logged, never silently dropped.
- **Depth presets** (default `standard`): `quick` (5 fetch / 6 claims / 2 votes),
  `standard` (8 / 12 / 3), `deep` (15 / 25 / 3) — `deep` matches the old fixed cap exactly
  (it's the ceiling, unchanged); `quick`/`standard` are the new, cheaper defaults.
- **Upfront cost estimate.** Logs the worst-case agent count and active caps before spending.

## Before invoking

1. **Is the question specific enough?** If underspecified (e.g. "what car to buy" with no
   budget/use-case/region), ask 2–3 clarifying questions first, then weave the answers into
   the question you pass.
2. **Pick a depth.** Default to `standard`. Use `quick` for a fast sanity check, `deep` only
   when the user wants exhaustive coverage and accepts the cost.

## How to run

Call the Workflow tool with the script path and the question as `args`:

```
Workflow({
  scriptPath: "$HOME/.agents/skills/deep-research/deep-research.workflow.js",
  args: "<the refined research question>"
})
```

To override the guardrails, pass an **object** instead of a string:

```
Workflow({
  scriptPath: "$HOME/.agents/skills/deep-research/deep-research.workflow.js",
  args: {
    question: "<question>",
    depth: "quick" | "standard" | "deep",   // preset; default "standard"
    maxFetch: 8,                              // override sources fetched
    maxClaims: 12,                            // override claims verified
    votes: 3,                                 // adversarial votes per claim
    models: { verify: "sonnet", synthesize: "opus" }  // override any stage's model
  }
})
```

The Workflow tool does not expand `$HOME`: pass the absolute path (e.g. `/home/<user>/.agents/skills/deep-research/deep-research.workflow.js`).

## After it returns

The workflow returns a structured object: `summary`, `findings` (each with confidence +
sources), `refuted` and `unverified` claims (for transparency), `sources`, and a `stats` block
(agent count, caps hit, claims dropped to the cap). Relay the summary and findings to the user
with citations; surface the caveats and anything the cost cap left unverified.

**Persist the report.** A research report is expensive to produce and easy to lose once it
scrolls out of context. Write the returned object to
`docs/deep-research/<slug>.md` (slug derived from the question — short, kebab-case), formatted
as a Markdown report: title, summary, findings with confidence/sources, refuted/unverified
sections, and the stats block. Create `docs/deep-research/` if it doesn't exist. Mention the
saved path to the user.
