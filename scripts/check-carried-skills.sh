#!/usr/bin/env bash
# Checks carried over from Z0rd0nZords (check-skill-help.sh + check-skill-size.sh),
# scoped to the skills that came from it (listed in CARRIED below):
#   1. every carried skill's SKILL.md has a "## `-h` / `--help`" section
#   2. multi-agent-review's SKILL.md body (after frontmatter) stays under 800 lines;
#      any other carried skill over the ceiling only warns.
# Exit: 0 ok, 1 violation, 2 nothing found (misconfigured).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

HEADING='## `-h` / `--help`'
CEILING=800
MUST_PASS="skills/multi-agent-review/SKILL.md"
CARRIED="baton-runner multi-agent-review multi-agent-review-codex reasoned-review reasoned-review-codex teammate-handoff total-review total-review-scaffold"
fail=0
n=0

for s in $CARRIED; do
  f="skills/$s/SKILL.md"
  if [ ! -f "$f" ]; then
    echo "missing carried skill: $f" >&2
    fail=1
    continue
  fi
  n=$((n + 1))
  if ! grep -qF "$HEADING" "$f"; then
    echo "missing -h/--help section: $f" >&2
    fail=1
  fi
  body=$(awk 'NR==1 && $0=="---" {fm=1; next} fm && $0=="---" {fm=0; next} !fm' "$f" | wc -l)
  if [ "$body" -gt "$CEILING" ]; then
    if [ "$f" = "$MUST_PASS" ]; then
      echo "oversized: $f body is $body lines (ceiling $CEILING)" >&2
      fail=1
    else
      echo "warn: $f body is $body lines (ceiling $CEILING)" >&2
    fi
  fi
done

[ "$n" -gt 0 ] || { echo "error: no carried skills found" >&2; exit 2; }
[ "$fail" -eq 0 ] && echo "ok: $n carried skills checked"
exit "$fail"
