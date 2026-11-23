# hooks

`jev_route.py` is an optional `UserPromptSubmit` hook that suggests a workflow route for each
prompt before the agent reads it. It is not installed by adding the skill: nothing runs until
you add the snippet below to a settings file yourself.

It asks Jev, TypeSafe's classifier model, three questions in one call (`questions.json`): which
process workflow the prompt starts in, whether the user's own words ask for a multi-agent
workflow, and how well the work suits one. Jev answers with labels and confidences and writes no
text, which is why a call takes a fraction of a second.

## What it does to a session

- Adds a short note to the agent's context: the process workflow and its gate when Jev's
  confidence is at least 0.80, and a line about orchestration when the fit is probably strong
  (0.70 or more).
- Says nothing for prompts under 25 characters, slash commands, a `none` route, low confidence,
  a missing key or any error. It always exits 0 and never blocks a prompt.
- Never tells the agent that the user opted in to a workflow. A wrong "yes" there would start
  agents nobody asked for, so the note only says that running one needs the user's opt-in.
- The note is a guess from the prompt alone. The skill's own rules still decide the route.

## What it sends, and where

Every routed prompt goes to an outside service: the first 8,000 characters, after a short list
of secret patterns has been replaced with `[redacted]`. The pattern list is small; do not rely
on it to catch every secret. The destination follows the key: OpenRouter for an `sk-or-` key,
Vercel AI Gateway for a `vck_` key, otherwise TypeSafe's own API.

## Installing it

It needs `python3`, `curl`, and a key in `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY`. In a Claude
Code cloud session where the key is saved as a network secret, the proxy supplies the real key,
so set the variable to a placeholder such as `sk-or-proxy-injected`.

Add this to a `settings.json`, with the path pointing at wherever this skill is installed:

```json
{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"python3 \"${CLAUDE_PROJECT_DIR}/skills/workflow-router/hooks/jev_route.py\" hook","timeout":25}]}]}}
```

The path above is right inside a checkout of this repo. For a globally installed copy, use that
copy's path instead, for example `~/.claude/skills/workflow-router/hooks/jev_route.py`.

## Other modes

```bash
python3 hooks/jev_route.py ask 'Bump React from 17 to 19.'
```

```bash
python3 hooks/jev_route.py eval evals/process-judge/cases.jsonl process
```

Thresholds can be changed with `JEV_ROUTE_PROCESS_MIN`, `JEV_ROUTE_OPT_IN_MIN` and
`JEV_ROUTE_STRONG_MIN`. Results and limits are in
[../evals/jev-judge/README.md](../evals/jev-judge/README.md).
