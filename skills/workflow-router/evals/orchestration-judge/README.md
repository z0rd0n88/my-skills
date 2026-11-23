# orchestration-judge

An LLM judge for one question: should this task be run as a scripted multi-agent workflow?
It covers the orchestration lane of `workflow-router` only. It was written in a separate
session that had not seen the router, so it is an independent check on that lane's "when to
orchestrate" and opt-in rules. It says nothing about the process or durable lanes.

- `judge.md` is the system prompt. Input: the task in `<task>` tags and optional background in
  `<context>` tags. Output: one JSON object with `fit` (strong, marginal, poor), `opt_in`, and
  `verdict` (`run_workflow`, `offer_workflow`, `no_workflow`), plus a suggested `shape`.
- `cases.jsonl` holds 14 labelled cases. The labels are the judge author's own judgement.
- `run.sh <model> <outdir>` runs every case as an isolated `claude -p` call with no tools and
  prints `ok` or `MISS` per case. It needs the `claude` CLI and `jq`. Give `<outdir>` a relative
  name starting `out-`; it is created next to the script and ignored by git.

## Results

| Model | Result | Misses |
|---|---|---|
| Sonnet 5.5, author's session | 42/42 over 3 rounds | none |
| Haiku 5.5, author's session | 80/84 over 6 rounds | `research-noopt`: three rated marginal instead of strong, one invalid JSON |
| Sonnet 5.5, one round from this repo | 13/14 | `coupled-refactor`: right verdict, invalid JSON (a stray closing quote) |

## Known limits

- The reply is free-text JSON, and both models have produced an unparseable reply at least once.
  Structured output has not been tried.
- Not tested on larger models, with long real conversation context, or against labels from a
  second person.
- `shape` is free text; it does not name one of the router's six shapes.
