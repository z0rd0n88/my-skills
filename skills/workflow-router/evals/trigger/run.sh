#!/bin/bash
# usage: run.sh <model> <outdir>   — does the skill's description make a fresh session load it?
#   <outdir>  a plain name starting with out- (out-haiku, say): created beside this script, ignored by git.
#   JOBS      how many sessions run at once. Default 6: a cap against your rate limit, not a tuned value.
# Each case in cases.jsonl is sent as the only prompt of a new headless session, in an empty throwaway
# project that has this skill installed, and stopped after one turn. "load" means the session's first
# action was a Skill call naming workflow-router; "skip" means it was anything else.
# Exit: 0 every case matched, 1 a case missed or its session failed, 2 the run could not start, 64 wrong arguments.
usage() { echo "usage: run.sh <model> <outdir>   (outdir: a plain name starting with out-, such as out-haiku)" >&2; exit 64; }
[ $# -eq 2 ] || usage
case "$2" in */*|out-) usage ;; out-*) ;; *) usage ;; esac
max="${JOBS:-6}"
case "$max" in ''|*[!0-9]*|0) echo "error: JOBS must be a whole number of 1 or more" >&2; exit 64 ;; esac
for tool in claude jq; do
  command -v "$tool" >/dev/null || { echo "error: $tool is not installed or not on PATH" >&2; exit 2; }
done
cd "$(dirname "$0")" || exit 2; p="$PWD"; skill="$(cd ../.. && pwd)"
[ -r cases.jsonl ] && [ -r "$skill/SKILL.md" ] || { echo "error: cases.jsonl or the skill's SKILL.md is missing" >&2; exit 2; }
mkdir -p "$2" || { echo "error: cannot create $2" >&2; exit 2; }
proj=$(mktemp -d -p "${TMPDIR:-/tmp}") || exit 2
trap 'rm -rf "$proj"' EXIT
mkdir -p "$proj/.claude/skills/workflow-router" || exit 2
cp -R "$skill/SKILL.md" "$skill/references" "$skill/hooks" "$proj/.claude/skills/workflow-router/" || exit 2
n=0
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line")
  ( cd "$proj" && jq -r .prompt <<<"$line" | claude -p --model "$1" --max-turns 1 --output-format stream-json --verbose > "$p/$2/$id.jsonl" 2> "$p/$2/$id.err" ) &
  n=$((n + 1)); [ $((n % max)) -eq 0 ] && wait
done < cases.jsonl
wait
bad=0
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line"); exp=$(jq -r .expect <<<"$line")
  first=$(jq -rs '[.[] | select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | if .name=="Skill" then "Skill:"+(.input.skill // "?") else .name end] | join(",")' "$2/$id.jsonl" 2>/dev/null)
  if ! jq -es 'any(.[]; .type=="assistant")' "$2/$id.jsonl" >/dev/null 2>&1; then
    bad=$((bad + 1)); echo "ERROR $id expect=$exp session failed: $(head -c 160 "$2/$id.err" 2>/dev/null | tr '\n' ' ')"
    continue
  fi
  case ",$first," in *",Skill:workflow-router,"*) got=load ;; *) got=skip ;; esac
  if [ "$got" = "$exp" ]; then s=ok; else s=MISS; bad=$((bad + 1)); fi
  echo "$s $id expect=$exp got=$got first=${first:-text}"
done < cases.jsonl
[ "$bad" -eq 0 ]
