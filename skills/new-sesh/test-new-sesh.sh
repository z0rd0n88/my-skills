#!/usr/bin/env bash
# Checks for new-sesh.sh's validation gates. No claude sessions are spawned:
# every case here is expected to be refused before the spawn, plus one case
# proving the happy path still reaches it.
#
#   bash test-new-sesh.sh
#
# Exists because check_out_path is a security gate that was bypassed in five
# separate review rounds, each time by a case the previous fix did not cover.
set -uo pipefail

SUT=$(dirname -- "$(readlink -f -- "$0")")/new-sesh.sh
TD=$(mktemp -d) || exit 1
trap 'rm -rf -- "$TD"' EXIT
pass=0; fail=0

# expect <label> <pattern> -- <args...>   asserts the run's output matches
expect() {
  local label=$1 want=$2; shift 3
  local got
  got=$(bash "$SUT" "$@" 2>&1 | tail -1)
  if [[ $got == *"$want"* ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL %s\n  want: *%s*\n  got:  %s\n' "$label" "$want" "$got"
  fi
}

mkdir -p "$TD/work" "$TD/repo/.claude/agents" "$TD/repo/.git/hooks" "$TD/home/.ssh"
printf 'do a thing\n' > "$TD/p.md"

# --- injection and hostile paths -------------------------------------------
expect "quote in --dir"        "not a searchable directory" -- spawn --dir "$TD/w'; echo PWNED; #" --out "$TD/o" --prompt-file "$TD/p.md"
expect "control char in --out" "control character"          -- spawn --dir "$TD/work" --out "$(printf '%s/a\nb' "$TD")" --prompt-file "$TD/p.md"
expect "relative --dir"        "must be absolute"           -- spawn --dir ./rel --out "$TD/o" --prompt-file "$TD/p.md"
expect "dotdot is resolved"    "config directory"           -- spawn --dir "$TD/work" --out "$TD/repo/.git/../.git/hooks/x" --prompt-file "$TD/p.md"

# --- write targets that become instructions or keys ------------------------
expect "project .claude/"      "config directory"           -- spawn --dir "$TD/work" --out "$TD/repo/.claude/agents/x.md" --prompt-file "$TD/p.md"
expect "project .git/"         "config directory"           -- spawn --dir "$TD/work" --out "$TD/repo/.git/hooks/pre-commit" --prompt-file "$TD/p.md"
expect "CLAUDE.md basename"    "instruction or auto-loaded" -- spawn --dir "$TD/work" --out "$TD/repo/CLAUDE.md" --prompt-file "$TD/p.md"
expect "Makefile basename"     "instruction or auto-loaded" -- spawn --dir "$TD/work" --out "$TD/repo/Makefile" --prompt-file "$TD/p.md"

# HOME with a trailing slash used to disable every protected-location pattern
# at once, because they are built by concatenation.
for h in "$TD/home" "$TD/home/"; do
  got=$(HOME="$h" bash "$SUT" spawn --dir "$TD/work" --out "$TD/home/.ssh/k" --prompt-file "$TD/p.md" 2>&1 | tail -1)
  if [[ $got == *"protected location"* ]]; then pass=$((pass + 1)); else
    fail=$((fail + 1)); printf 'FAIL HOME=%s not protected\n  got: %s\n' "$h" "$got"
  fi
done

# --- symlinks --------------------------------------------------------------
ln -sf "$TD/definitely-missing" "$TD/dangling"
expect "dangling symlink --out" "already exists"            -- spawn --dir "$TD/work" --out "$TD/dangling" --prompt-file "$TD/p.md"
ln -sfn "$TD/home/.ssh" "$TD/sshlink"
expect "parent symlinks to .ssh" "config directory"          -- spawn --dir "$TD/work" --out "$TD/sshlink/k2" --prompt-file "$TD/p.md"

# --- prompt validation -----------------------------------------------------
: > "$TD/empty.md"; printf '   \n' > "$TD/ws.md"
expect "empty prompt file"     "empty"                      -- spawn --dir "$TD/work" --out "$TD/o2" --prompt-file "$TD/empty.md"
expect "whitespace-only"       "whitespace only"            -- spawn --dir "$TD/work" --out "$TD/o3" --prompt-file "$TD/ws.md"
expect "prompt is a directory" "not a readable regular"     -- spawn --dir "$TD/work" --out "$TD/o4" --prompt-file "$TD/work"
expect "both prompt forms"     "mutually exclusive"         -- spawn --dir "$TD/work" --out "$TD/o5" --prompt-file "$TD/p.md" --prompt-text hi

# --- recursion -------------------------------------------------------------
got=$(CLAUDE_NEW_SESSION_DEPTH=1 bash "$SUT" spawn --dir "$TD/work" --out "$TD/o6" --prompt-file "$TD/p.md" 2>&1 | tail -1)
if [[ $got == *"refusing to nest"* ]]; then pass=$((pass + 1)); else
  fail=$((fail + 1)); printf 'FAIL nested spawn not refused\n  got: %s\n' "$got"
fi

# --- scan ------------------------------------------------------------------
got=$(bash "$SUT" scan /nonexistent-xyz 2>&1 | tail -1)
[[ $got == *"not a directory"* ]] && pass=$((pass + 1)) || { fail=$((fail + 1)); printf 'FAIL missing dir must not scan clean\n  got: %s\n' "$got"; }

# A missing dir used to print only "absent" lines, identical to a pristine tree.
got=$(bash "$SUT" scan "$TD/work" 2>&1 | tail -1)
[[ $got == *"SCAN COMPLETE"*"tree=0"* ]] && pass=$((pass + 1)) || { fail=$((fail + 1)); printf 'FAIL clean dir should be tree=0\n  got: %s\n' "$got"; }

got=$(bash "$SUT" scan "$TD/repo" 2>&1 | tail -1)
[[ $got == *"tree=2"* ]] && pass=$((pass + 1)) || { fail=$((fail + 1)); printf 'FAIL repo with .claude+.git should count 2 tree findings\n  got: %s\n' "$got"; }

# --- the happy path must run end to end -----------------------------------
# A gate that refuses everything passes every test above; this is the case that
# tells a working validator from a broken one. `claude` is stubbed so the whole
# path runs -- validation, file creation, redirect, exit reporting -- without
# spawning a real session.
mkdir -p "$TD/fakebin"
printf '#!/bin/sh\necho FAKE-CHILD-RAN\n' > "$TD/fakebin/claude"
chmod +x "$TD/fakebin/claude"
got=$(PATH="$TD/fakebin:$PATH" bash "$SUT" spawn --dir "$TD/work" --out "$TD/legit.log" --prompt-file "$TD/p.md" 2>&1 | tail -1)
if [[ $got == "exit=0" ]] && [[ $(cat "$TD/legit.log" 2>/dev/null) == *FAKE-CHILD-RAN* ]]; then
  pass=$((pass + 1))
else
  fail=$((fail + 1))
  printf 'FAIL happy path\n  want: exit=0 and FAKE-CHILD-RAN in the output file\n  got:  %s / %s\n' \
    "$got" "$(cat "$TD/legit.log" 2>/dev/null)"
fi

# The output file must be private from creation, not chmod-ed afterwards.
mode=$(stat -c %a "$TD/legit.log" 2>/dev/null)
[[ $mode == 600 ]] && pass=$((pass + 1)) || { fail=$((fail + 1)); printf 'FAIL output mode want 600 got %s\n' "$mode"; }

# Defaults: omitting --dir and --out must produce an output path named for the
# session id the child actually received.
out=$(cd "$TD/work" && PATH="$TD/fakebin:$PATH" bash "$SUT" spawn --prompt-file "$TD/p.md" 2>&1)
sid=$(printf '%s' "$out" | sed -n 's/^sid=//p')
outfile=$(printf '%s' "$out" | sed -n 's/^out=//p')
if [[ -n $sid && $outfile == "/tmp/new-sesh-$sid" ]]; then
  pass=$((pass + 1)); rm -f -- "$outfile"
else
  fail=$((fail + 1)); printf 'FAIL default --out must be /tmp/new-sesh-<sid>\n  sid=%s out=%s\n' "$sid" "$outfile"
fi

# --- output contract ------------------------------------------------------
# sid=/out=/exit= print as one block after the last thing that can fail. A late
# failure used to emit sid= and out= and then no exit= at all, while the skill
# tells the caller to read exit= first.
got=$(bash "$SUT" spawn --dir "$TD/work" --out "$TD/o7" --prompt-file "$TD/ws.md" 2>&1)
if [[ $got != *"sid="* && $got != *"out="* && $got == *"whitespace only"* ]]; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); printf 'FAIL late failure must not emit a partial block\n  got: %s\n' "$got"
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ $fail -eq 0 ]]
