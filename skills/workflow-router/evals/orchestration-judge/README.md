# orchestration-judge

An LLM judge for one question: should this task be run as a scripted multi-agent workflow?
It covers the orchestration lane of `workflow-router` only. It was written in a separate
session that had not seen the router, so it is an independent check on that lane's "when to
orchestrate" and opt-in rules. It says nothing about the process or durable lanes.

- `judge.md` is the system prompt. Input: the task in `<task>` tags and optional background in
  `<context>` tags. Output: one JSON object with `fit` (strong, marginal, poor), `opt_in`, and
  `verdict` (`run_workflow`, `offer_workflow`, `no_workflow`), plus a suggested `shape`.
- `cases.jsonl` holds 14 labelled cases. The labels are the judge author's own judgement.
- `schema.json` is the JSON schema of the reply.
- `run.sh <model> <outdir>` runs every case as an isolated `claude -p` call with no tools, with
  the reply constrained to `schema.json`, and prints `ok` or `MISS` per case. It needs the
  `claude` CLI and `jq`. Give `<outdir>` a relative name starting `out-`; it is created next to
  the script and ignored by git.

## Results

With the reply constrained to the schema:

| Model | Result |
|---|---|
| Sonnet 5.5, author's session | 42/42 over 3 rounds |
| Haiku 5.5, author's session | 42/42 over 3 rounds |
| Sonnet 5.5, one round from this repo | 14/14 |
| Haiku 5.5, one round from this repo | 14/14 |

Before the schema, with the reply as free-text JSON: Sonnet 5.5 scored 42/42 in the author's
session and 13/14 here (one unparseable reply with the right verdict). Haiku 5.5 scored 80/84:
one unparseable reply, and `research-noopt` rated marginal instead of strong three times. That
flip did not recur in the schema runs, which is too few rounds to call it gone.

## Known limits

- A caller without schema support depends on `judge.md`'s own output instructions, and both
  models have then produced an unparseable reply at least once.
- Not tested on larger models, with long real conversation context, or against labels from a
  second person.
- `shape` is free text; it does not name one of the router's six shapes.
