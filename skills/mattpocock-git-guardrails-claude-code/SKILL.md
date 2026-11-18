---
name: mattpocock-git-guardrails-claude-code
description: Set up Claude Code hooks to block dangerous git commands (push, reset --hard, clean, branch -D, etc.) before they execute. Use when user wants to prevent destructive git operations, add git safety hooks, or block git push/reset in Claude Code.
---

# Setup Git Guardrails

Sets up a PreToolUse hook that intercepts and blocks dangerous git commands before Claude executes them.

## What Gets Blocked

- `git push` (all variants including `--force`)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git checkout .` / `git restore .`

These match with any spacing, after git's global options (`-C <path>`, `-c <k=v>`, `--git-dir=`, `--no-pager`), and with combined flags (`git clean -xdf`, `git branch --delete --force`). The hook also blocks when `jq` is missing or the input can't be read, rather than letting the command through.

When blocked, Claude sees `BLOCKED: <reason> The user has prevented you from doing this.` on stderr.

This is a speed bump, not a security boundary: a git call hidden inside `sh -c`, `eval` or a shell alias still gets through.

## Steps

### 1. Check jq, then ask scope

The hook requires `jq`. Run `command -v jq`. If it prints nothing, stop and tell the user to install `jq` first: the hook blocks every Bash call when `jq` is missing, not just git ones.

Ask the user: install for **this project only** (`.claude/settings.json`) or **all projects** (`~/.claude/settings.json`)?

### 2. Copy the hook script

The bundled script is at: [scripts/block-dangerous-git.sh](scripts/block-dangerous-git.sh)

Copy it to the target location based on scope:

- **Project**: `.claude/hooks/block-dangerous-git.sh`
- **Global**: `~/.claude/hooks/block-dangerous-git.sh`

Make it executable with `chmod +x`.

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

Ask if user wants to add or remove any patterns from the blocked list. Edit the copied script accordingly.

### 5. Verify

Run a quick test:

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | <path-to-script>
```

Should exit with code 2 and print a BLOCKED message to stderr.

Check the settings file still parses and holds the hook: `jq -e '.hooks.PreToolUse' <settings-file>` prints the array and exits 0.

Run the bundled self-check against the installed copy (paths are relative to this SKILL.md's folder): `bash scripts/test-block-dangerous-git.sh <path-to-installed-script>`. It prints `all checks pass`. A failure for a pattern the user removed on purpose in step 4 is expected.

If any check fails, fix the script or the settings file and re-run the checks until they pass.
