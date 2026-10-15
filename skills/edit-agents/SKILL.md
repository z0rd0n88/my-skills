---
name: edit-agents
description: Enable/disable/list Claude Code agents by moving `.md` files between `agents/` and a sibling `agents-parked/` — `agents/` is scanned recursively so `agents/disabled/` fails to hide them.
allowed-tools: Bash
---

# Edit Agents

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Moves agent `.md` files on disk** — and, inside a git repo, may commit that
> rename; parked/enabled state only takes effect on the next session restart.

Enables, disables, or lists Claude Code agents by moving their `.md` file between
`agents/` (loaded at session start) and a sibling `agents-parked/` directory,
since `agents/` is scanned recursively and a nested `disabled/` folder would not
actually hide them. Supports single agents or whole user-configured categories,
and can commit the resulting rename when run inside a git repo.

| Option | Values | Default | Effect |
|---|---|---|---|
| `list` | — | — | Show enabled and parked agents in the resolved root |
| `list enabled` / `list parked` | — | — | Filter to one bucket |
| `enable <name>...` | agent basename(s), no `.md` | — | Move from `<root>-parked/` → `<root>/` |
| `disable <name>...` | agent basename(s), no `.md` | — | Move from `<root>/` → `<root>-parked/` |
| `enable-category <cat>` | category name | — | Enable every agent in a configured category |
| `disable-category <cat>` | category name | — | Disable every agent in a configured category |
| `categories` | — | — | Print configured categories + members |
| `--scope project\|user` / `--dir <path>` | — | auto-detected | Overrides which root the command targets |

Toggle Claude Code agents on/off by moving their `.md` file between `<root>/` (enabled — loaded at session start) and `<root>-parked/` (parked — sibling dir **outside** `<root>`, ignored by the scanner).

**Why a sibling dir, not a subfolder:** Claude Code scans `<root>` **recursively**. A `<root>/disabled/` subfolder still loads its contents into the roster and burns context. Parking therefore moves the file *out* of the `agents/` tree entirely. (This is opposite to skills, which are scanned one level deep — `skills/disabled/` works for skills but does **not** work for agents.)

The mechanics live in `edit-agents.sh` alongside this file. The skill exists so future sessions reach for the script instead of hand-rolling `mv` commands and putting parked agents in a still-scanned subfolder.

## When to use

- User asks to enable/disable a specific agent by name
- User asks to enable/disable a **category** of agents (only after they've configured categories — see below)
- User asks "what agents are available?" / "list my agents"
- User wants to reduce context overhead by parking unused agents

## When NOT to use

- Installing new agents from a repo or marketplace → different tooling
- Editing the *contents* of an agent's `.md` file → use `Edit`/`Write` directly
- Creating a brand-new agent → use whatever agent-authoring skill you prefer

## Default behavior (ambiguous invocation)

If the user says "manage agents" / "show my agents" without a specific op, default to listing **both** scopes so they see the full picture before deciding:

```bash
bash "$HOME/.agents/skills/edit-agents/edit-agents.sh" list
bash "$HOME/.agents/skills/edit-agents/edit-agents.sh" --scope user list
```

If the project and user roots resolve to the same directory (no project-specific `.claude/agents/`), show only one block. Then prompt: "What would you like to do?"

The script lives in the installed skill dir (`$HOME/.agents/skills/edit-agents/`).

## Step 1: Pick the scope

The script auto-detects: project-scoped (`$PWD/.claude/agents`) if that dir exists, else user-scoped (`~/.claude/agents`). Override with `--scope project|user` or `--dir <path>`.

If intent is ambiguous (user says "enable kotlin-specialist" while inside a project that has its own agents), default to **project** scope and say which scope was chosen.

## Step 2: Run a command

```bash
bash "$HOME/.agents/skills/edit-agents/edit-agents.sh" <command> [args]
```

| Command | Effect |
|---|---|
| `list` | Show enabled and parked agents in the resolved root |
| `list enabled` / `list parked` | Filter to one bucket |
| `enable <name>...` | Move from `<root>-parked/` → `<root>/` |
| `disable <name>...` | Move from `<root>/` → `<root>-parked/` |
| `enable-category <cat>` | Enable every agent in a category (requires config — see below) |
| `disable-category <cat>` | Disable every agent in a category (requires config) |
| `categories` | Print configured categories + members |
| `--help` | Full usage |

The `--help` row above is `edit-agents.sh`'s own usage output for running it directly in a shell; `-h`/`--help` as a skill invocation (e.g. `/edit-agents -h`) is documented in the `-h` / `--help` section near the top of this file.

Names are passed without the `.md` suffix.

## Step 3: (Optional) categories

Categories are **user-configured** — the plugin ships no built-in list because agent rosters vary per install. `enable`/`disable`/`list` never require this; only the category commands do.

Create a config file at `$XDG_CONFIG_HOME/edit-agents/categories` (or `~/.config/edit-agents/categories` if `XDG_CONFIG_HOME` is unset), or point `$CLAUDE_EDIT_AGENTS_CATEGORIES` at a file of your choice.

Format:

```
review:   architect-review code-explorer commit-guardian
security: penetration-tester crypto-security-reviewer
impl:     backend-developer kotlin-specialist
```

Blank lines and `#` comments are ignored. Names must match agent file basenames (without `.md`). An example lives at `examples/categories` in this skill dir.

An agent may legitimately appear in two categories (e.g., `crypto-security-reviewer` in both `review` and `security`) — enabling a category that names an already-enabled agent is a no-op with a friendly message.

## Step 4: Commit if in a git repo

If the resolved root is inside a git working tree (check with `git -C "$ROOT" rev-parse --is-inside-work-tree 2>/dev/null`), the rename shows as an unstaged change. Surface `git status` — the user may want to commit. If the root is not tracked (typical for a bare `~/.claude/agents/`), skip this step.

```bash
git status .claude/agents
git add .claude/agents
git commit -m "chore: enable kotlin-specialist + crypto-security-reviewer"
```

## Step 5: Inform about restart

Agent definitions are loaded at session start. **The current session's tool list does not change.** New/parked agents take effect the next time Claude Code starts. Say this out loud so the user isn't confused when `subagent_type: kotlin-specialist` still works (or doesn't) in the same session.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running `mv` by hand and dropping into `disabled/` | Use the script — sibling-dir convention is encoded |
| Reporting "enabled" without warning about session restart | Always mention the restart caveat (Step 5) |
| Renaming inside a tracked repo without committing | Surface `git status` so the user sees the unstaged change |
| Confusing project vs user scope when both exist | Run `list` first, show the resolved root, then act |
| Passing full filename like `kotlin-specialist.md` | Bare name only; script appends `.md` |
| Running `enable-category` before configuring one | Config file is user-supplied — see Step 3 |
