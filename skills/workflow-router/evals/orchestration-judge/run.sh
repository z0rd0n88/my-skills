#!/bin/bash
# usage: run.sh <model> <outdir>   — runs judge.md on every case in cases.jsonl, one isolated call per case.
# The reply is constrained to schema.json, so each <id>.out holds a valid JSON verdict (or is empty if the call failed).
cd "$(dirname "$0")"; p="$PWD"; mkdir -p "$2"
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line")
  ( msg=$(jq -r '"<task>\n"+.task+"\n</task>"+(if .context then "\n<context>\n"+.context+"\n</context>" else "" end)' <<<"$line")
    d=$(mktemp -d -p "${TMPDIR:-/tmp}"); cd "$d" && printf "%s" "$msg" | claude -p --model "$1" --system-prompt "$(cat "$p/judge.md")" --tools "" --json-schema "$(cat "$p/schema.json")" --output-format json 2> "$p/$2/$id.err" | jq '.structured_output // empty' > "$p/$2/$id.out" ) &
done < cases.jsonl
wait
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line"); exp=$(jq -r .expect <<<"$line")
  got=$(jq -r '.verdict // "UNPARSEABLE"' "$2/$id.out" 2>/dev/null); fit=$(jq -r '.fit // ""' "$2/$id.out" 2>/dev/null)
  [ -n "$got" ] || got=UNPARSEABLE
  [ "$got" = "$exp" ] && s=ok || s=MISS
  echo "$s $id expect=$exp got=$got fit=$fit"
done < cases.jsonl
