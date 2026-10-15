#!/usr/bin/env bash
# regen-index.sh — rebuild baton-pass/INDEX.md from scratch.
#
# Usage: ./regen-index.sh [path/to/baton-pass] [--source <human|runner>]
#
# Scans:
#   <root>/<scope>/*.md   — per-scope entries (filename starts with a digit)
#   <root>/*.md           — top-level cross-cutting entries (same rule),
#                           excluding INDEX.md and CLAUDE.md
#
# For each scope, the latest-sorting filename wins — a plain lexicographic
# sort suffices for the `YYYY-MM-DDTHHMMSS-<slug>.md` format, and legacy
# `NNN-YYYY-MM-DD-<slug>.md` entries numbered 000–202 correctly sort before
# any timestamp entry (NNN >= 203 would sort after — see SKILL.md's sort
# caveat; real legacy counters never got near 203).
#
# --source <human|runner> filters entries by YAML frontmatter `source:` field.
# Entries WITHOUT frontmatter are included only when no --source filter is
# given (unfiltered runs show everything; a filtered run treats "no
# frontmatter" as "unknown source" and excludes it rather than guessing).
#
# The script never patches INDEX.md in place — it is always regenerated from
# the current file listing, so running it twice with no underlying changes
# produces a byte-identical file (idempotent).
set -euo pipefail

# Byte-wise sort/collation regardless of the caller's locale — keeps the
# idempotency guarantee (byte-identical output) portable across machines.
export LC_ALL=C

ROOT="baton-pass"
SOURCE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      if [[ $# -lt 2 ]]; then
        echo "regen-index: --source requires a value (human|runner)" >&2
        exit 2
      fi
      SOURCE_FILTER="$2"
      case "$SOURCE_FILTER" in
        human|runner) ;;
        *)
          echo "regen-index: invalid --source '$SOURCE_FILTER' (expected human|runner)" >&2
          exit 2
          ;;
      esac
      shift 2
      ;;
    *)
      ROOT="$1"
      shift
      ;;
  esac
done

if [[ ! -d "$ROOT" ]]; then
  echo "regen-index: no such directory: $ROOT" >&2
  exit 2
fi

INDEX_FILE="$ROOT/INDEX.md"

# entry_filename_pattern: leading digit, .md suffix, excluding INDEX.md/CLAUDE.md.
is_entry_filename() {
  local name="$1"
  case "$name" in
    INDEX.md|CLAUDE.md) return 1 ;;
  esac
  [[ "$name" =~ ^[0-9].*\.md$ ]]
}

# Extract frontmatter `source:` value, empty string if no frontmatter/field.
extract_frontmatter_source() {
  local file="$1"
  awk '
    { sub(/\r$/, "") }                             # tolerate CRLF entries
    NR==1 && $0 ~ /^---[[:space:]]*$/ { infm=1; next }
    infm && $0 ~ /^---[[:space:]]*$/ { exit }
    infm && $0 ~ /^source:[[:space:]]*/ {
      sub(/^source:[[:space:]]*/, "");
      sub(/[[:space:]]+$/, "");
      print;
      exit
    }
  ' "$file"
}

# Extract "**Date:**" value from the file body.
extract_date_line() {
  local file="$1"
  awk '
    { sub(/\r$/, "") }                             # tolerate CRLF entries
    /^\*\*Date:\*\*/ {
      sub(/^\*\*Date:\*\*[[:space:]]*/, "");
      sub(/[[:space:]]+$/, "");
      print;
      exit
    }
  ' "$file"
}

# Extract the topic from the first "# Pass-Baton: <topic>" heading.
extract_topic() {
  local file="$1"
  awk '
    { sub(/\r$/, "") }                             # tolerate CRLF entries
    /^# Pass-Baton:[[:space:]]*/ {
      sub(/^# Pass-Baton:[[:space:]]*/, "");
      sub(/[[:space:]]+$/, "");
      print;
      exit
    }
  ' "$file"
}

# Parse filename -> label + fallback date. Prints "label<TAB>date".
parse_filename() {
  local base="$1" # filename without directory, with .md
  local stem="${base%.md}"
  if [[ "$stem" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6})-(.+)$ ]]; then
    local label="${BASH_REMATCH[1]}"
    local date_part="${label%%T*}"
    printf '%s\t%s\n' "$label" "$date_part"
  elif [[ "$stem" =~ ^([0-9]+)-([0-9]{4}-[0-9]{2}-[0-9]{2})-(.+)$ ]]; then
    printf '%s\t%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
  else
    # Unrecognized format; best-effort: whole leading numeric token, no date.
    local label="${stem%%-*}"
    printf '%s\t%s\n' "$label" ""
  fi
}

# Returns 0 (pass) if the file satisfies the --source filter.
passes_source_filter() {
  local file="$1"
  if [[ -z "$SOURCE_FILTER" ]]; then
    return 0
  fi
  local src
  src="$(extract_frontmatter_source "$file")"
  [[ -n "$src" && "$src" == "$SOURCE_FILTER" ]]
}

# Finds the latest (highest-sorting) qualifying entry file in a directory
# (non-recursive). Prints its full path, or nothing if none qualify.
latest_entry_in_dir() {
  local dir="$1"
  local best=""
  local name
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    is_entry_filename "$name" || continue
    local full="$dir/$name"
    [[ -f "$full" ]] || continue
    passes_source_filter "$full" || continue
    if [[ -z "$best" || "$name" > "$best" ]]; then
      best="$name"
    fi
  done < <(ls -1 "$dir" 2>/dev/null | sort)
  if [[ -n "$best" ]]; then
    printf '%s\n' "$dir/$best"
  fi
}

# --- Build scope rows -------------------------------------------------------

declare -a SCOPE_NAMES=()
declare -a SCOPE_ROWS=()

if [[ -d "$ROOT" ]]; then
  while IFS= read -r scope_dir; do
    [[ -z "$scope_dir" ]] && continue
    scope_dir="${scope_dir%/}"
    scope_name="$(basename "$scope_dir")"

    latest="$(latest_entry_in_dir "$scope_dir")"
    [[ -z "$latest" ]] && continue

    filename="$(basename "$latest")"
    parsed="$(parse_filename "$filename")"
    label="${parsed%%$'\t'*}"
    fname_date="${parsed#*$'\t'}"

    date="$(extract_date_line "$latest")"
    [[ -z "$date" ]] && date="$fname_date"

    topic="$(extract_topic "$latest")"

    SCOPE_NAMES+=("$scope_name")
    SCOPE_ROWS+=("| ${scope_name} | [${label}](./${scope_name}/${filename}) | ${date} | ${topic} |")
  done < <(ls -d "$ROOT"/*/ 2>/dev/null | sort)
fi

# Sort scope rows by scope name (SCOPE_NAMES/SCOPE_ROWS built in sorted-dir
# order already since `ls -d ... | sort` sorts directory names).

# --- Top-level seed entry ---------------------------------------------------

TOP_SEED_LINE=""
if [[ -d "$ROOT" ]]; then
  best_top=""
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    is_entry_filename "$name" || continue
    full="$ROOT/$name"
    [[ -f "$full" ]] || continue
    passes_source_filter "$full" || continue
    if [[ -z "$best_top" || "$name" > "$best_top" ]]; then
      best_top="$name"
    fi
  done < <(ls -1 "$ROOT" 2>/dev/null | sort)

  if [[ -n "$best_top" ]]; then
    # NOTE: if multiple top-level entries exist, only the latest is listed
    # as the seed; older ones remain reachable via that file's own
    # back-references (not enumerated here).
    TOP_SEED_LINE="*(top-level seed: [${best_top}](./${best_top}))*"
  fi
fi

# --- Render ------------------------------------------------------------------

{
  echo "# Pass-Baton Index"
  echo ""
  echo "Latest entry per scope. Read the linked file for full context. New sessions"
  echo "should start here."
  echo ""
  echo "| Scope | Latest | Date | Topic |"
  echo "|---|---|---|---|"
  for row in "${SCOPE_ROWS[@]+"${SCOPE_ROWS[@]}"}"; do
    echo "$row"
  done
  if [[ -n "$TOP_SEED_LINE" ]]; then
    echo ""
    echo "$TOP_SEED_LINE"
  fi
} > "$INDEX_FILE"
