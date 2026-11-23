#!/bin/bash
# usage: run.sh <model> <outdir>   — runs judge.md on every case in cases.jsonl, one isolated call per case
cd "$(dirname "$0")"; p="$PWD"; mkdir -p "$2"
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line")
  ( msg=$(jq -r '"<task>\n"+.task+"\n</task>"+(if .context then "\n<context>\n"+.context+"\n</context>" else "" end)' <<<"$line")
    d=$(mktemp -d -p "${TMPDIR:-/tmp}"); cd "$d" && printf "%s" "$msg" | claude -p --model "$1" --system-prompt "$(cat "$p/judge.md")" --tools "" > "$p/$2/$id.out" 2> "$p/$2/$id.err" ) &
done < cases.jsonl
wait
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line"); exp=$(jq -r .expect <<<"$line")
  json=$(sed -e '/^```/d' "$2/$id.out")
  got=$(jq -r .verdict <<<"$json" 2>/dev/null || echo UNPARSEABLE); fit=$(jq -r .fit <<<"$json" 2>/dev/null)
  [ "$got" = "$exp" ] && s=ok || s=MISS
  echo "$s $id expect=$exp got=$got fit=$fit"
done < cases.jsonl
