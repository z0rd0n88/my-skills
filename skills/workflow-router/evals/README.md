# workflow-router evals

Labelled cases for the router's decisions and for its description, each with a runner.

| Folder | Judges | Cases |
|---|---|---|
| [orchestration-judge/](orchestration-judge/README.md) | Whether to run a multi-agent workflow, offer one, or work inline | 14 |
| [process-judge/](process-judge/README.md) | Which of the eleven process workflows a task starts in, or none | 27 |
| [jev-judge/](jev-judge/README.md) | Both questions again, answered by the Jev classifier behind the optional hook | 18 holdout, plus the 41 above |
| [trigger/](trigger/README.md) | Whether a fresh session loads the skill from its description | 21 |

The durable lane has no judge. No judge has been run against the router's own output yet: the
judge cases check the judges, and the trigger cases check only whether the skill is loaded, not
the route it then gives.

When a routing rule changes, add or change the labelled case first and the rule second, so the
case is not written to fit the wording.

The two LLM judge runners and the trigger runner need the `claude` CLI and `jq`:
`./run.sh <model> <outdir>`. `<outdir>` must be a plain name starting `out-` (created next to the
script, ignored by git); anything else is refused. `JOBS` sets how many calls run at once
(default 6). The Jev runner is `hooks/jev_route.py eval`; see the jev-judge README.

Every runner exits 0 when all cases match, 1 when a case misses or its call fails (printed as
`MISS` or `ERROR`), 2 when it cannot start, and 64 on wrong arguments, so a run can gate CI.
