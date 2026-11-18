#!/bin/bash
# PreToolUse hook. The checking lives in block-dangerous-git.py next to this file;
# this wrapper makes a missing python3 or a crash block instead of allowing.
# exit 2 = Claude Code's PreToolUse hook blocks the tool call and shows stderr to Claude.
block() { echo "BLOCKED: $1 The user has prevented you from doing this." >&2; exit 2; }

command -v python3 >/dev/null || block "python3 is missing, so the command could not be checked."
python3 -I "$(dirname "$0")/block-dangerous-git.py"
status=$?
[ "$status" = 0 ] || [ "$status" = 2 ] || block "the git guard crashed (exit $status)."
exit "$status"
