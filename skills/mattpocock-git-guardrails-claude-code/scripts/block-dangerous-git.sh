#!/bin/bash
# ponytail: regex speed bump, not a security boundary. A git call hidden in
# `sh -c`, `eval` or an alias still gets through; a full shell parser would close that.
set -o pipefail

# exit 2 = Claude Code's PreToolUse hook blocks the tool call and shows stderr to Claude.
block() { echo "BLOCKED: $1 The user has prevented you from doing this." >&2; exit 2; }

command -v jq >/dev/null || block "jq is missing, so the command could not be checked."
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty') || block "the hook input could not be parsed."
[ -n "$COMMAND" ] || block "the command was empty."

# `git`, then any global options (-C <path>, -c <k=v>, --git-dir=<d>, --no-pager, -p ...), then the subcommand.
G='git([[:space:]]+(-C|-c|--git-dir|--work-tree|--namespace)([[:space:]]+|=)[^[:space:]]+|[[:space:]]+--?[a-zA-Z][a-zA-Z-]*(=[^[:space:]]+)?)*[[:space:]]+'
ARGS='([[:space:]]+[^;&|]*)?[[:space:]]+'   # other arguments before the flag, same command only
END='([[:space:]]|$)'

DANGEROUS_PATTERNS=(
  "${G}push"
  "${G}reset${ARGS}--hard"
  "${G}clean${ARGS}(-[a-zA-Z]*f[a-zA-Z]*|--force)${END}"
  "${G}branch${ARGS}(-[a-zA-Z]*D[a-zA-Z]*${END}|--delete${ARGS}--force|--force${ARGS}--delete)"
  "${G}checkout${ARGS}\.${END}"
  "${G}restore${ARGS}\.${END}"
  "push[[:space:]]+(.*[[:space:]])?--force"
  "reset[[:space:]]+(.*[[:space:]])?--hard"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if printf '%s' "$COMMAND" | grep -qE "$pattern"; then
    block "'$COMMAND' matches a dangerous git pattern."
  fi
done

exit 0
