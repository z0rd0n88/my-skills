# process-judge

An LLM judge for one question: which engineering process should this task follow? It returns
the single primary workflow a task should start in (one of the router's eleven, or `none`), the
workflow it will probably hand off to (`then`), and the one missing fact that would change the
route (`open`).

Unlike the orchestration judge, this one was not written blind. Its criteria come from the
first-match table in `SKILL.md` Step 2 and the use-when and not-when lines in
`references/engineering-workflows.md`, so it checks that a route follows the router's rules, not
whether the rules are right. When either file changes, check the judge still agrees.

- `judge.md` is the system prompt. Input: the task in `<task>` tags and optional background in
  `<context>` tags.
- `cases.jsonl` holds 27 labelled cases. The labels are the judge author's own judgement.
- `schema.json` is the JSON schema of the reply.
- `run.sh <model> <outdir>` runs every case as an isolated `claude -p` call with no tools, with
  the reply constrained to `schema.json`, and prints `ok` or `MISS` per case.

## Results

| Model | Result |
|---|---|
| Sonnet 5.5, author's session | 81/81 over 3 rounds |
| Haiku 5.5, author's session | 81/81 over 3 rounds |
| Sonnet 5.5, one round from this repo | 27/27 |
| Haiku 5.5, one round from this repo | 27/27 |

A clean sweep from the first draft on suggests the cases are on the easy side. Treat this as a
smoke test.

## Known limits

- Not tested on larger models, with long real conversation context, or against labels from a
  second person.
- Two boundaries have one case each: an upgrade whose breaking changes touch many files
  (Dependency Upgrade, then Migration), and a one-line fix to wrong behaviour (Bug Fix, not
  `none`).
