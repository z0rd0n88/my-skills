# jev-judge

Cases and results for the Jev router in [../../hooks/](../../hooks/README.md). It answers the
same two questions as the LLM judges next door, with one fast classifier call instead of a
model writing JSON. The Haiku and Sonnet judges stay the reference; this folder measures how
closely Jev agrees with their labels.

- `holdout-process.jsonl` (12 cases) and `holdout-orch.jsonl` (6 cases) were written after the
  Jev questions were fixed, so they are the only cases the questions were not tuned against.
- The existing `../process-judge/cases.jsonl` (27) and `../orchestration-judge/cases.jsonl` (14)
  are reused as they are.

Run from the skill folder, with a key set as described in the hooks README:

```bash
python3 hooks/jev_route.py eval evals/process-judge/cases.jsonl process
```

```bash
python3 hooks/jev_route.py eval evals/orchestration-judge/cases.jsonl orchestration
```

```bash
python3 hooks/jev_route.py eval evals/jev-judge/holdout-process.jsonl process
```

```bash
python3 hooks/jev_route.py eval evals/jev-judge/holdout-orch.jsonl orchestration
```

For orchestration the verdict is worked out in code from two answers: opt-in of 0.85 or more
gives `run_workflow`; otherwise a strong-fit probability of 0.70 or more gives `offer_workflow`;
otherwise `no_workflow`.

## Results

Jev through OpenRouter, model reported as `typesafe/jev-1.14-20261014`.

| Case file | Author's session | One run from this repo | Three more runs, after the redaction fix |
|---|---|---|---|
| Process, 27 existing cases | 27/27, three rounds, identical each time | 27/27 | 27/27 each |
| Orchestration, 14 existing cases | 14/14, three rounds, identical each time | 14/14 | 14/14 each |
| Process holdout, 12 cases | 11/12 on the first run | 12/12 | 11/12, 12/12, 12/12 |
| Orchestration holdout, 6 cases | 6/6 | 6/6 | 6/6 each |

One case is unstable: `h-node-bump` ("Move us from Node 18 to Node 22"). Three repeat calls from
this repo gave `none` at 0.37, `dependency_upgrade` at 0.60 and `none` at 0.47, and the three
later runs gave `none` at 0.53 and `dependency_upgrade` at 0.56 and 0.39. A pass in the table
is luck. At those confidences the hook stays silent on it.

A call took about 0.2 to 0.25 seconds in the author's session, and about half a second end to
end here including Python start-up. A small test call cost $0.0000135; the three-question call
is larger and its cost was not recorded.

## Known limits

- The questions were written with the 41 existing cases in view, so those scores show fit, not
  accuracy. The 18 holdout cases are the only unseen ones, and the same author wrote them.
- Margins behind the three thresholds, over the three later runs of all 59 cases:
  - Process (0.80): apart from `h-node-bump`, every correct pick scored 0.80 or more. The lowest,
    `fix-didnt-fix`, ranged 0.80 to 0.85, so it sits on the line.
  - Opt-in (0.85): real opt-ins scored 0.94 or more. The highest score for anything else was
    0.45, on the holdout case `h-o-second-opinion`; among the 14 existing cases it was 0.09.
  - Strong fit (0.70): cases labelled `offer_workflow` scored 0.99 or more and cases labelled
    `no_workflow` 0.13 or less. `migration-library`, a process case with no orchestration
    label, scored 0.69 in the author's session and 0.72 to 0.75 here, so the hook may or may
    not add its offer line for that prompt.
- The hook was tested by piping events to the script, not inside a live Claude Code session.
- Jev returns a label and a confidence only, so the reasoning, `shape`, `then` and `open` fields
  of the LLM judges have no equivalent here.
