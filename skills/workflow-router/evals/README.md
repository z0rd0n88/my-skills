# workflow-router evals

LLM judges for the router's decisions, each with labelled cases and a runner.

| Folder | Judges | Cases |
|---|---|---|
| [orchestration-judge/](orchestration-judge/README.md) | Whether to run a multi-agent workflow, offer one, or work inline | 14 |
| [process-judge/](process-judge/README.md) | Which of the eleven process workflows a task starts in, or none | 27 |
| [jev-judge/](jev-judge/README.md) | Both questions again, answered by the Jev classifier behind the optional hook | 18 holdout, plus the 41 above |

The durable lane has no judge. No judge has been run against the router's own output yet: the
cases check the judges, not the router.

The two LLM judge runners need the `claude` CLI and `jq`: `./run.sh <model> <outdir>`, with
`<outdir>` a relative name starting `out-` (created next to the script, ignored by git). The
Jev runner is `hooks/jev_route.py eval`; see the jev-judge README.
