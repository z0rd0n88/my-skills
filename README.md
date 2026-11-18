# my-skills

Personal agent skills. Install: `npx skills add z0rd0n88/my-skills -g -a claude-code -a codex -a antigravity`

`skills/addyosmani-*` are copies of [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), renamed with an `addyosmani-` prefix so they never collide with same-named skills from other sources. MIT licensed; notice in `LICENSES/addyosmani-agent-skills.txt`.

`skills/branch-off` is a fork of [agenthub](https://github.com/alirezarezvani/claude-skills) with judge voting adapted from [horse-race](https://github.com/qiao/horse-race). Both are MIT; notices are in `LICENSES/agenthub.txt` and `LICENSES/horse-race.txt`.

`skills/iron-ham-split` is a copy of [Iron-Ham/split](https://github.com/Iron-Ham/split) (MIT), renamed with an `iron-ham-` prefix. Its README names the source commit; the notice is in `LICENSES/iron-ham-split.txt`.

`skills/mattpocock-*` are copies of [mattpocock/skills](https://github.com/mattpocock/skills) at commit `c55ee46`, by Matt Pocock, renamed with a `mattpocock-` prefix (cross-skill references updated to match). MIT licensed; notice in `LICENSES/mattpocock-skills.txt`. One local change: `mattpocock-git-guardrails-claude-code/scripts/block-dangerous-git.sh` fails closed and matches git's global options and combined flags, with a self-check in `test-block-dangerous-git.sh`.

Claude Code mods moved to [claude-mod-ity](https://github.com/z0rd0n88/claude-mod-ity).
