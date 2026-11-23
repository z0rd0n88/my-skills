# trigger

Does the skill's `description` make a fresh session load it? A skill that is never loaded routes
nothing, and one that loads on every prompt costs context for no gain.

- `cases.jsonl` has 21 prompts: 12 real tasks labelled `load` and 9 labelled `skip` (typos,
  comments, a version string, questions, an email, requests to run a command, a "go ahead").
- `run.sh <model> <outdir>` sends each prompt as the only message of a new headless session
  (`claude -p --max-turns 1`) in an empty throwaway project that has this skill installed. A
  case counts as `load` when the session's first action is a `Skill` call naming
  `workflow-router`, and as `skip` otherwise.

```bash
./run.sh claude-sonnet-5-5 out-sonnet
```

## Results

Run in a session whose skill list held 161 skills, this one included.

| Description | Model | Tasks loaded (of 12) | Non-tasks skipped (of 9) |
|---|---|---|---|
| Before: "Use at the start of an engineering task, and whenever a task needs or would be improved by a workflow, …" | Haiku 5.5 | 0 | 9 |
| | Sonnet 5.5 | 1 | 9 |
| Current: "Use first, before reading code or running any command, whenever a task will change or investigate how software behaves, such as …" | Haiku 5.5 | 2, 3 (two runs) | 9, 9 |
| | Sonnet 5.5 | 9, 6 (two runs) | 9, 9 |

The one task the old description loaded on was "Which workflow should I follow …". Where a
session did not load the skill, its first action was usually a shell command to look at the
repository. On Sonnet the tasks missed in both runs were `feasibility`, `library-swap` and
`new-feature`.

Two wordings tried in between are left out: each had a colon inside the description, which made
the frontmatter invalid as strict YAML, so their numbers do not measure a description that could
ship.

## What this does and does not show

- The old description was not loading the skill too often. On these cases it almost never
  loaded it. The current wording loads it for half to three quarters of the tasks on Sonnet and
  for two or three of twelve on Haiku, and neither wording loaded it for a non-task.
- Two runs of the same wording differed by three tasks on Sonnet, so read these as rough rates.
- The project is empty, so a session's first move is to look for code that is not there. A real
  repository may give different numbers in either direction.
- The result depends on the other skills installed: 160 others competed here.
- Only the first action counts. A skill loaded on the second turn is scored as `skip`; a spot
  check of six Sonnet tasks over four turns found no later loads.
- The current description was chosen by trying wordings against these same 21 cases, so its
  score shows fit to them, not accuracy on new prompts.
- This checks loading only. Whether the route the skill then gives is right is not tested.
- Where the skill must be consulted on every task, do not rely on the description: the optional
  hook in [../../hooks/](../../hooks/README.md) puts a suggested route in context, and a line in
  the project's `CLAUDE.md` can name the skill outright.
