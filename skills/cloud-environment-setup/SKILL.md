---
name: cloud-environment-setup
description: Use before changing a Claude Code cloud environment (its setup script, environment variables or network) or making a tool, service or cache available in every cloud session — Docker for Testcontainers, a JDK or SDK, package installs, warmed build caches. Also use when a cloud session is missing something a repo normally sets up for itself, when the container disagrees with its own setup script, or before saving anything that depends on repo or folder names. Triggers include "save the setup", "add it to the setup script", "make X start every session", "why isn't Docker running", "set up the environment", get_environment / update_environment / create_environment.
---

# cloud-environment-setup

A cloud session runs in a container built from an environment: a setup script, environment variables, a network policy and the repositories attached to it. Changes to an environment touch every future session that uses it, so a wrong change fails quietly and repeatedly. This skill is the order of checks that keeps that from happening.

## 1. Before adding anything, find out why it's missing

If the container lacks something a repo normally provides (a running daemon, a toolchain, generated config), assume first that the repo's own setup *didn't run*, not that nobody wrote it.

- List each checkout's committed hooks: `.claude/settings.json` (and any `hooks/` it points at), for every repo in the session.
- Compare the session's working directory with each repo root. Project hooks load for the project the session is rooted in. A session rooted in the folder *above* several checkouts loads none of them.
- That disables the repo's **guard hooks** too (PreToolUse checks, Stop checks), not just its setup. Tell the user which guards are inert in this layout; that is usually more important than the missing tool.
- Whether user-level SessionStart hooks run in cloud sessions has been reported as "no". Check it on this platform before relying on it either way.

Prefer reusing the repo's own setup logic (call its script from the setup script, or root the session in that repo) over writing a parallel mechanism. Two mechanisms for the same job drift apart, and you will have to switch one off to test the other.

## 2. Diagnose before editing

When the container contradicts the setup script (a pinned version is not the one installed, a step's output is absent), explain why before changing the script. If the current script didn't take effect, your edited one probably won't either. Common causes: the container was cached or restored rather than built fresh, a step's guard skipped it, or the image already shipped something.

## 3. Config that depends on names

Before saving a script, variable or brief that names repos or folders:

- Confirm current names: `list_repos`, each checkout's `git remote get-url origin`, the repo links in loaded CLAUDE.md / AGENTS.md, and recent `git log` for renames.
- Accept every live spelling of each repo (renamed name, old name, lowercase clone name): `for d in new-name Old-Name old-name; do [ -d "$d" ] && { X=$d; break; }; done`.
- A silent `[ -d repo ] && …` guard cannot tell "repo not attached" from "repo renamed". End the script with a short ran/skipped line per step so a skip is visible in the session log.
- Read the environment again with `get_environment` right before every write. The user can rename it or change it from another session in between.

## 4. Writing the setup script

- The setup script runs as root before the session starts and must not leave daemons running. For a service a session needs (e.g. Docker), install an idempotent starter and trigger it on demand, from the build tool (a Gradle init script on test tasks, a test-runner hook) or the repo's own hook.
- An idempotent starter checks the service first, removes stale pidfiles only when the PID they name is dead (restored containers keep pidfiles but not processes), then starts the service and waits for it.
- Keep failures loud for anything the session can't work without. Use `|| echo WARN` only for true conveniences such as cache warm-ups.
- Never put secrets in the script or in variables. They are stored in plain text.

## 5. Testing it

- Run the whole script from the folder that holds the checkouts, the way a fresh session does, with `bash -x`, and check each step *ran*. A step that skipped also exits 0.
- Test name variants in a scratch parent folder of symlinks (`old-layout/`, `new-layout/`), never by renaming real checkouts.
- Prefer a child session or scratch container for steps that delete or replace things (`rm -rf` an SDK, reinstall a toolchain). Running them in the working container invalidates results you already reported. If you did, say which earlier results ran on what the script replaced, and rerun them or mark them stale.

## 6. Proving a mechanism works

A check proves nothing if something else could have produced the same result. Before verifying, switch off or rule out every competing path (a repo hook that also starts the service, a cached container that already has it), and name the evidence that only your mechanism leaves behind: its own log file, its timestamps, a process started during the build. Report which path acted, and say plainly what stays unproven until a fresh session runs the script.
