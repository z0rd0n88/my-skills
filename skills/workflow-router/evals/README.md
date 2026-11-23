# workflow-router evals

LLM judges for the router's decisions, each with labelled cases and a runner.

| Folder | Judges | Cases |
|---|---|---|
| [orchestration-judge/](orchestration-judge/README.md) | Whether to run a multi-agent workflow, offer one, or work inline | 14 |
| [process-judge/](process-judge/README.md) | Which of the eleven process workflows a task starts in, or none | 27 |

The durable lane has no judge. Neither judge has been run against the router's own output yet:
the cases check the judges, not the router.

Both runners need the `claude` CLI and `jq`: `./run.sh <model> <outdir>`, with `<outdir>` a
relative name starting `out-` (created next to the script, ignored by git).
