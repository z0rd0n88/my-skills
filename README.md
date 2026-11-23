# my-skills

Personal agent skills. Install: `npx skills add z0rd0n88/my-skills -g -a claude-code -a codex -a antigravity`

`skills/addyosmani-*` are copies of [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), renamed with an `addyosmani-` prefix so they never collide with same-named skills from other sources. MIT licensed; notice in `LICENSES/addyosmani-agent-skills.txt`.

`skills/branch-off` is a fork of [agenthub](https://github.com/alirezarezvani/claude-skills) with judge voting adapted from [horse-race](https://github.com/qiao/horse-race). Both are MIT; notices are in `LICENSES/agenthub.txt` and `LICENSES/horse-race.txt`.

`skills/iron-ham-split` is a copy of [Iron-Ham/split](https://github.com/Iron-Ham/split) (MIT), renamed with an `iron-ham-` prefix. Its README names the source commit; the notice is in `LICENSES/iron-ham-split.txt`.

`skills/mattpocock-*` are copies of [mattpocock/skills](https://github.com/mattpocock/skills) at commit `c55ee46`, by Matt Pocock, renamed with a `mattpocock-` prefix (cross-skill references updated to match). MIT licensed; notice in `LICENSES/mattpocock-skills.txt`. One local change: `mattpocock-git-guardrails-claude-code` checks commands with a Python `shlex` parser (`scripts/block-dangerous-git.py`) instead of regexes, fails closed, and has a self-check in `test-block-dangerous-git.sh`.

`skills/zord-*`, `refs/multi-agent/` and `commands/zord-total-review-init.md` came from [z0rd0n88/Z0rd0nZords](https://github.com/z0rd0n88/Z0rd0nZords) at `8f28f91`, which is now retired. `scripts/check-zord-skills.sh` carries over its `-h`/`--help` and size checks.

`skills/workflow-router` picks a workflow in three lanes. The durable lane (`references/durable-workflows.md`, `references/sharp-edges.md`) is written from the workflow-automation guide in [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills/blob/main/skills/workflow-automation/references/detailed-guide.md) at `4b1fe9d` (MIT; the guide credits vibeship-spawner-skills, Apache 2.0). It keeps the guide's patterns, platform notes and sharp edges, reworded as a routing procedure, and leaves out its code samples, which the guide itself marks as version-mixed. The process and orchestration lanes are condensed from the guide *Engineering Workflows & Agent Orchestration* v2.0 (not in this repo). That guide's TDD-Ralph section derives from Geoffrey Huntley's [Ralph post](https://ghuntley.com/ralph/) and Clayton Farr's [Ralph Playbook](https://github.com/ghuntley/how-to-ralph-wiggum#workflow), and its six orchestration shapes come from Anthropic's dynamic-workflows guide by way of Mark Kashef's [walkthrough](https://www.youtube.com/watch?v=g9b9G8dcS8Y).

Claude Code mods moved to [claude-mod-ity](https://github.com/z0rd0n88/claude-mod-ity).
