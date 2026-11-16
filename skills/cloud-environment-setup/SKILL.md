---
name: cloud-environment-setup
description: Checks to run before changing a cloud environment and while editing repos in a multi-repo cloud session. Use before changing a Claude Code cloud environment (setup script, environment variables, network) or making a tool, service or cache available in every cloud session — Docker for Testcontainers, a JDK or SDK, packages, warmed build caches. Also when a cloud session lacks something a repo normally sets up, when a session holding several checkouts is about to edit one, when the container disagrees with its setup script, or before saving config that names repos or folders. Triggers include "add it to the setup script", "make X start every session", get_environment / update_environment / create_environment.
---

# cloud-environment-setup

For writing a SessionStart hook that is committed to a repo, use the built-in startup-hook skill instead.

## 1. Find out what the repo's own config is doing in this session

If the container lacks something a repo normally provides (a running daemon, a toolchain, generated config), assume first that the repo's own setup *didn't run*, not that nobody wrote it.

- **What loads depends on where the session is rooted.** In a *parent-rooted* session (rooted in the folder above several checkouts), each repo's `CLAUDE.md` and skills still load, so the session looks fully configured. Its committed hooks (`.claude/settings.json`) do not. Hook commands written as `"$CLAUDE_PROJECT_DIR/.claude/hooks/…"` would point at the wrong folder anyway.
- **That switches off the guards, not just the setup.** PreToolUse and Stop hooks that block dangerous edits, secrets or unsafe commands are inert too. Test one in 30 seconds: feed a command the guard should refuse to the hook script directly (`echo '{"tool_name":"Bash","tool_input":{"command":"…"}}' | python3 <repo>/.claude/hooks/<guard>.py; echo $?`), then run the same harmless command through the Bash tool. If the script blocks it and the session doesn't, the guard is off.
- **Git hooks are usually off too:** cloud checkouts don't set `core.hooksPath`, so a repo's `.githooks/` won't run.
- **Environment variables can switch a repo hook off.** Check `get_environment` variable names against the flags the hook reads before concluding it is broken.
- **Hooks that do run** come from the platform's launcher settings and from enabled plugins. Whether hooks in a user-level `~/.claude/settings.json` run in cloud sessions is untested; don't rely on it either way.

**Edit a guarded repo only from a session rooted in that repo**, where its guards load. From a parent-rooted session, review it, test it and run its build. Tell the user when a session they started is parent-rooted.

When a repo's hook already does the setup, the usual fix is to root the session in that repo (the user starts a new session; an agent can't re-root one), not a second mechanism. A hook that starts daemons or writes to `CLAUDE_ENV_FILE` can't be called from a setup script. If a parallel copy is unavoidable, call it a stopgap and record the duplication where the repo tracks work.

## 2. Diagnose before editing

When the container contradicts the setup script (a pinned version is not the one installed, a step's output is absent), explain why before changing the script. If the current script didn't take effect, your edited one probably won't either. Possible causes to rule out: the container was restored rather than built fresh, a step's guard skipped it, or the image already shipped something.

## 3. Config that depends on names

Before saving a script, variable or brief that names repos or folders:

- Confirm current names: `list_repos`, each checkout's `git remote get-url origin`, the repo links in loaded CLAUDE.md / AGENTS.md, and recent `git log` for renames.
- Accept both the old and new spelling of a renamed repo: `for d in new-name Old-Name; do [ -d "$d" ] && { X=$d; break; }; done`.
- Read the environment again with `get_environment` right before every write. The user can rename it or change it from another session in between.

## 4. Writing the setup script

- The setup script runs as root before the session starts and must not leave daemons running. A service a session needs (e.g. Docker) is started on demand: by the repo's own hook where it runs, otherwise by an idempotent starter triggered from the build tool (e.g. a Gradle init script on test tasks). The second is a stopgap whenever the repo already has a starter.
- An idempotent starter checks the service first, removes stale pidfiles only when the PID they name is dead (restored containers keep pidfiles but not processes), then starts the service and waits for it.
- Keep failures loud for anything the session can't work without. Use `|| echo WARN` only for true conveniences such as cache warm-ups.
- Never put secrets in the script or in variables. They are stored in plain text.

## 5. Testing it

- Run the whole script from the folder that holds the checkouts, the way a fresh session does, with `bash -x`, and check each step *ran*. A step that skipped also exits 0.
- Test name variants in a scratch parent folder of symlinks (`old-layout/`, `new-layout/`), never by renaming real checkouts.
- Running the script in the working container changes it: it can replace a toolchain your earlier results ran on, and it installs whatever it copies (draft skills included) in a way a later run may not refresh. Prefer a child session or scratch container for steps that delete or replace things. If you did run it here, say which earlier results are now stale, and rerun them.

## 6. Proving a mechanism works

A check proves nothing if something else could have produced the same result. Before verifying, switch off or rule out every competing path (a repo hook that also starts the service, a cached container that already has it), and name the evidence that only your mechanism leaves behind: its own log file, its timestamps, a process started during the build. Report which path acted, and say plainly what stays unproven until a fresh session runs the script.
