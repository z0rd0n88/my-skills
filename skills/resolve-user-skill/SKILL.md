---
name: resolve-user-skill
description: Use when the user asks you to use, run, load or apply a skill, agent, command or workflow by name ("use Finding Fixer", "run the reflect skill from lil-pstack", "/dw-review", "use my review skill") and that name is not in this session's available-skills list or agent types. Finds it, including in the user's own GitHub repos, before you substitute anything else or say it doesn't exist. Use it even when the name is misspelled or only roughly matches.
---

# resolve-user-skill

Find a skill the user named before doing anything in its place.

Why this exists: people keep their own skills in GitHub repos (`my-skills`, a plugin repo) that a
cloud or fresh session has not installed. An agent that searches only the local catalog concludes
the skill is missing. It then runs a generic agent instead and does the work the wrong way, and
the user has to say which repo holds the skill. Every step below is cheap compared with that
detour.

## Search, in this order

Stop at the first step that finds the skill, then read its `SKILL.md` in full and follow it.

1. **This session's lists.** The available-skills list, the agent types, slash commands. Compare
   loosely: case, spaces against hyphens ("Finding Fixer" is `finding-fixer`), and typos
   ("reeflect" is `reflect`). A name the user qualified with a source ("reflect from lil-pstack")
   still counts as found here if a listed skill matches both parts.
2. **Local skill folders.** `~/.claude/skills/`, `~/.agents/skills/`, the project's
   `.claude/skills/` and `.agents/skills/`, and any repo already cloned into the session. Run
   `find <dir> -maxdepth 4 -iname SKILL.md` and match on the folder name and the `name:` field.
3. **The plugin catalog.** Run `SearchPlugins` with the name and a few synonyms. A hit there is
   installable, but the user's own repo (step 4) usually holds the version they mean, so check
   it before suggesting an install.
4. **The user's GitHub repos.** Call `list_repos` (claude-code-remote MCP). Query first with the
   source the user named, if any ("lil-pstackc" → try `pstack`), then with the skill name, then
   with `skill`. Repo names are substring-matched, so query with fragments. For each candidate:
   `add_repo`, then one shallow clone with a long timeout (`git clone --depth 1 <url>
   /home/user/<repo>`, about 10 minutes, never two clones of the same repo at once), then
   `register_repo_root`. Then `find /home/user/<repo> -iname SKILL.md` and match as in step 1.
   That clone fetches only the default branch; to push a branch from it, first run `git remote
   set-branches origin '*'`, or the pushed branch gets no `origin/<branch>` ref and looks unpushed.
   Skills often sit deep, e.g. `plugins/<plugin>/skills/<name>/SKILL.md`.

Paths the skill refers to (`$HOME/.agents/skills/<name>/assets/...`) assume an installed copy. In
a cloned repo, resolve them relative to the `SKILL.md` you read.

## When nothing matches

Only after all four steps, tell the user what you searched (each step, the queries used, and the
closest near-misses) and ask where the skill lives. Do not swap in a generic agent or your own
version of the workflow without the user's go-ahead. A substitute that looks like the real skill
hides that the real one was never run.

## When several match

Several candidates (a catalog skill and a repo skill with the same name, or two repos): prefer
the user's own repo, and say which one you used and what else matched. Ask only when the
candidates would do visibly different things.
