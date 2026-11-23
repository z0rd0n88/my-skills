#!/bin/bash
# usage: run.sh <model> <outdir>   — runs judge.md on every case in cases.jsonl, one isolated call per case.
#   <outdir>  a plain name starting with out- (out-haiku, say): created beside this script, ignored by git.
#   JOBS      how many calls run at once. Default 6: a cap so a run is not one burst of calls against
#             your rate limit, not a tuned value. Raise it if your limit allows.
# The reply is constrained to schema.json, so each <id>.out holds a valid JSON verdict, or is empty when the
# call failed; <id>.err then holds what the claude CLI printed.
# Exit: 0 every case matched, 1 a case missed or its call failed, 2 the run could not start, 64 wrong arguments.
usage() { echo "usage: run.sh <model> <outdir>   (outdir: a plain name starting with out-, such as out-haiku)" >&2; exit 64; }
[ $# -eq 2 ] || usage
case "$2" in */*|out-) usage ;; out-*) ;; *) usage ;; esac
max="${JOBS:-6}"
case "$max" in ''|*[!0-9]*|0) echo "error: JOBS must be a whole number of 1 or more" >&2; exit 64 ;; esac
for tool in claude jq; do
  command -v "$tool" >/dev/null || { echo "error: $tool is not installed or not on PATH" >&2; exit 2; }
done
cd "$(dirname "$0")" || exit 2; p="$PWD"
for f in judge.md schema.json cases.jsonl; do
  [ -r "$f" ] || { echo "error: $f is missing beside run.sh" >&2; exit 2; }
done
mkdir -p "$2" || { echo "error: cannot create $2" >&2; exit 2; }
n=0
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line")
  ( msg=$(jq -r '"<task>\n"+.task+"\n</task>"+(if .context then "\n<context>\n"+.context+"\n</context>" else "" end)' <<<"$line")
    d=$(mktemp -d -p "${TMPDIR:-/tmp}"); cd "$d" && printf "%s" "$msg" | claude -p --model "$1" --system-prompt "$(cat "$p/judge.md")" --tools "" --json-schema "$(cat "$p/schema.json")" --output-format json 2> "$p/$2/$id.err" | jq '.structured_output // empty' > "$p/$2/$id.out" ) &
  n=$((n + 1)); [ $((n % max)) -eq 0 ] && wait
done < cases.jsonl
wait
bad=0
while IFS= read -r line; do
  id=$(jq -r .id <<<"$line"); exp=$(jq -r .expect <<<"$line")
  if [ ! -s "$2/$id.out" ]; then
    bad=$((bad + 1)); echo "ERROR $id expect=$exp call failed: $(head -c 160 "$2/$id.err" 2>/dev/null | tr '\n' ' ')"
    continue
  fi
  got=$(jq -r '.verdict // "UNPARSEABLE"' "$2/$id.out" 2>/dev/null); more=$(jq -r '.fit // ""' "$2/$id.out" 2>/dev/null)
  [ -n "$got" ] || got=UNPARSEABLE
  if [ "$got" = "$exp" ]; then s=ok; else s=MISS; bad=$((bad + 1)); fi
  echo "$s $id expect=$exp got=$got fit=$more"
done < cases.jsonl
[ "$bad" -eq 0 ]
