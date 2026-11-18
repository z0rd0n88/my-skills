---
name: mattpocock-git-guardrails-claude-code
description: Set up Claude Code hooks to block dangerous git commands (push, reset --hard, clean, branch -D, etc.) before they execute. Use when user wants to prevent destructive git operations, add git safety hooks, or block git push/reset in Claude Code.
---

# Setup Git Guardrails

Sets up a PreToolUse hook that intercepts and blocks dangerous git commands before Claude executes them.

## What Gets Blocked

- `git push` (all variants including `--force`)
- `git reset --hard`
- `git clean` unless it has `-n` / `--dry-run`
- `git branch -D`, and `-d` combined with `-f`
- `git checkout .` / `git restore .` (also `:/` and `*`)

The command is split into words the way a shell would (Python `shlex`), so these are caught after `;`, `&&`, `|` or inside `( )`, `` ` ` `` and `$( )`; inside `sh -c '...'`, `bash -lc "..."` and `eval`; with quoted words (`git 'push'`), line continuations, git's global options (`-C <path>`, `-c <k=v>`, `--no-pager`), abbreviated long options (`--har`), and bundled or split flags (`-xdf`, `-d -f`). The body of every `` ` ` `` and `$( )` is checked too, even inside quotes. The hook also blocks inline aliases (`git -c alias.x=push x`), git global options it doesn't know, and any case where `python3` is missing, the guard crashes, the input can't be read, or the command has unbalanced quotes, rather than letting the command through.

When blocked, Claude sees `BLOCKED: <reason> The user has prevented you from doing this.` on stderr.

This is a speed bump, not a security boundary: a git alias defined in a config file, a script that calls git, or a command built from a variable at run time (`$CMD`) still gets through.

## Steps

### 1. Check python3, then ask scope

The hook requires `python3`. Run `command -v python3`. If it prints nothing, stop and tell the user to install `python3` first: the hook blocks every Bash call when `python3` is missing, not just git ones.

Ask the user: install for **this project only** (`.claude/settings.json`) or **all projects** (`~/.claude/settings.json`)?

### 2. Copy the hook script

The hook is two bundled files that must sit in the same folder: [scripts/block-dangerous-git.sh](scripts/block-dangerous-git.sh) (the entry point) and [scripts/block-dangerous-git.py](scripts/block-dangerous-git.py) (the checks).

Copy both to the target folder based on scope:

- **Project**: `.claude/hooks/`
- **Global**: `~/.claude/hooks/`

Make `block-dangerous-git.sh` executable with `chmod +x`.

### 3. Add hook to settings

Add to the appropriate settings file:

**Project** (`.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

**Global** (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

If the settings file already exists, merge the hook into the existing `hooks.PreToolUse` array. Don't overwrite other settings.

### 4. Ask about customization

Ask if user wants to add or remove any patterns from the blocked list. Edit `dangerous_git()` in the copied `block-dangerous-git.py` accordingly.

### 5. Verify

Run a quick test:

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | <path-to-script>
```

Should exit with code 2 and print a BLOCKED message to stderr.

Check the settings file still parses and holds the hook: `python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hooks"]["PreToolUse"])' <settings-file>` prints the array and exits 0.

Run the bundled self-check against the installed copy (paths are relative to this SKILL.md's folder): `bash scripts/test-block-dangerous-git.sh <path-to-installed-script>`. It prints `all checks pass`. A failure for a pattern the user removed on purpose in step 4 is expected.

If any check fails, fix the script or the settings file and re-run the checks until they pass.
