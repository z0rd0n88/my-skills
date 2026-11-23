# my-skills

Personal agent skills. Install: `npx skills add z0rd0n88/my-skills -g -a claude-code -a codex -a antigravity`

## Plugins

The repo is also a plugin marketplace named `my-skills` (`.claude-plugin/marketplace.json`). It splits the skills into five plugins, so you can turn each group on or off:

| Plugin | Skills |
|---|---|
| `zord-review` | 16: the `zord-*` review skills, `dw-review`, `finding-fixer`, `pr-review-router`, `code-cleaver`, `audit-numeric-types`, `ci-parity-run`, `skill-sheriff-cc`, `drift-status-check`, plus the `zord-total-review-init` command |
| `zord-workflow` | 30: `workflow-router`, build runners, spec-to-test development, batons and handoffs, branch and PR wrap-up, specs and weekly wrap-ups, session and cloud-environment helpers, writing modes (`chiquita`, `bro-*`, `i-have-adhd`, `vista-improve-prompt`) and tools (`vercel-*`, `rekordbox-add`) |
| `zord-lateral` | 9: `lateral` and its eight thinking techniques |
| `zord-addyosmani` | 26: the vendored `addyosmani-*` skills and `addy-code` |
| `zord-mattpocock` | 9: the vendored `mattpocock-*` skills |

- claude.ai (syncs to Claude Code and cloud sessions): Customize > Plugins > Add > Add marketplace, enter `z0rd0n88/my-skills`, and give the Claude GitHub App access to the repo when asked, because it is private. Then add the plugins you want.
- Claude Code, one line per plugin you want:

```
/plugin install zord-review --marketplace z0rd0n88/my-skills
/plugin install zord-workflow --marketplace z0rd0n88/my-skills
/plugin install zord-lateral --marketplace z0rd0n88/my-skills
/plugin install zord-addyosmani --marketplace z0rd0n88/my-skills
/plugin install zord-mattpocock --marketplace z0rd0n88/my-skills
```

A plugin namespaces its skills, so `dw-review` runs as `zord-review:dw-review`. Skills call across plugins: the review skills use `baton-pass`, `spec-tacular`, `pr-merge-cleanup` and `zord-baton-runner` from `zord-workflow`, and `daily-loop`, `big-next-job` and `baton-runner-managed` use the `addyosmani-*` skills. Enable those plugins together.

Every plugin's `source` is the repo root, so each lists its skill folders. A new skill under `skills/` loads in no plugin until it is added to one list in `marketplace.json`; `scripts/check-marketplace.sh` fails CI until it is. Commands live in `refs/commands/`, because every plugin would load a root `commands/` folder.

`skills/addyosmani-*` are copies of [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), renamed with an `addyosmani-` prefix so they never collide with same-named skills from other sources. MIT licensed; notice in `LICENSES/addyosmani-agent-skills.txt`.

`skills/branch-off` is a fork of [agenthub](https://github.com/alirezarezvani/claude-skills) with judge voting adapted from [horse-race](https://github.com/qiao/horse-race). Both are MIT; notices are in `LICENSES/agenthub.txt` and `LICENSES/horse-race.txt`.

`skills/iron-ham-split` is a copy of [Iron-Ham/split](https://github.com/Iron-Ham/split) (MIT), renamed with an `iron-ham-` prefix. Its README names the source commit; the notice is in `LICENSES/iron-ham-split.txt`.

`skills/mattpocock-*` are copies of [mattpocock/skills](https://github.com/mattpocock/skills) at commit `c55ee46`, by Matt Pocock, renamed with a `mattpocock-` prefix (cross-skill references updated to match). MIT licensed; notice in `LICENSES/mattpocock-skills.txt`. One local change: `mattpocock-git-guardrails-claude-code` checks commands with a Python `shlex` parser (`scripts/block-dangerous-git.py`) instead of regexes, fails closed, and has a self-check in `test-block-dangerous-git.sh`.

`skills/zord-*`, `refs/multi-agent/` and `refs/commands/zord-total-review-init.md` came from [z0rd0n88/Z0rd0nZords](https://github.com/z0rd0n88/Z0rd0nZords) at `8f28f91`, which is now retired. `scripts/check-zord-skills.sh` carries over its `-h`/`--help` and size checks.

Findings from every review, audit or critique skill use one severity scale: CRITICAL (fix now), HIGH (fix before merge), MEDIUM (fix when convenient), LOW (optional), with ids `F1`, `F2`, .... It is defined once in `refs/severity-scale.md`, which also maps older labels (Blocker / Should-fix / Minor, `C1`/`H1`, Nit). The vendored `addyosmani-code-review-and-quality` keeps its upstream text and carries a one-line mapping note; no other vendored skill was changed.

`skills/workflow-router` picks a workflow in three lanes. The durable lane (`references/durable-workflows.md`, `references/sharp-edges.md`) is written from the workflow-automation guide in [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills/blob/main/skills/workflow-automation/references/detailed-guide.md) at `4b1fe9d` (MIT; notice in `LICENSES/agentic-awesome-skills.txt`). That guide's own skill file names its source as "vibeship-spawner-skills (Apache 2.0)" with no link, so no notice from that project is included here. It keeps the guide's patterns, platform notes and sharp edges, reworded as a routing procedure, and leaves out its code samples, which the guide itself marks as version-mixed. The process and orchestration lanes are condensed from the guide *Engineering Workflows & Agent Orchestration* v2.0 (not in this repo). That guide's TDD-Ralph section derives from Geoffrey Huntley's [Ralph post](https://ghuntley.com/ralph/) and Clayton Farr's [Ralph Playbook](https://github.com/ghuntley/how-to-ralph-wiggum#workflow), and its six orchestration shapes come from Anthropic's dynamic-workflows guide by way of Mark Kashef's [walkthrough](https://www.youtube.com/watch?v=g9b9G8dcS8Y).

This repo is the only place `skills/workflow-router` is edited. [z0rd0n88/JevDev](https://github.com/z0rd0n88/JevDev) carries an exact copy under `vendor/workflow-router/`, pinned by a lock file that its `vendor_sync.py` checks. After a change here, bring that copy up to date from a checkout of this repo: `python3 vendor_sync.py sync --source <this checkout>`.

Claude Code mods moved to [claude-mod-ity](https://github.com/z0rd0n88/claude-mod-ity).
