#!/usr/bin/env bash
# Checks the validation gate in rekordbox-add.sh. Run: ./test_rekordbox-add.sh
set -uo pipefail
cd "$(dirname "$0")"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
export REKORDBOX_ADD_DRY_RUN=1 REKORDBOX_DJ_DIR="$tmp/DJ"
mkdir -p "$tmp/src" "$tmp/DJ/Existing Artist"
touch "$tmp/src/a.mp3" "$tmp/src/b.FLAC" "$tmp/src/notes.txt" "$tmp/DJ/Existing Artist/a.mp3"
mkdir -p "$tmp/src2"; touch "$tmp/src2/a.mp3"
fail=0

expect() { # expect <exit-code> <args...>
  local want=$1; shift
  ./rekordbox-add.sh "$@" >/dev/null 2>&1; local rc=$?
  [[ $rc -eq $want ]] || { echo "FAIL: expected exit $want, got $rc for [$*]"; fail=1; }
}

expect 0 "Artist" "$tmp/src/a.mp3"
expect 0 "Artist" "$tmp/src/a.mp3" "$tmp/src/b.FLAC"
expect 0 "Sade" "$tmp/src/a.mp3"
expect 2                                   # no args
expect 2 "Artist"                          # no files
expect 2 "" "$tmp/src/a.mp3"               # empty artist
expect 2 "AC/DC" "$tmp/src/a.mp3"          # path separator in artist
expect 2 "What?" "$tmp/src/a.mp3"          # Windows-illegal char
expect 2 "Artist." "$tmp/src/a.mp3"        # trailing dot is illegal on Windows
expect 2 ".." "$tmp/src/a.mp3"
expect 2 "Artist" "$tmp/src/missing.mp3"
expect 2 "Artist" "$tmp/src/notes.txt"     # not audio
expect 2 "Existing Artist" "$tmp/src/a.mp3"                 # would overwrite
expect 2 "Artist" "$tmp/src/a.mp3" "$tmp/src2/a.mp3"        # duplicate names
expect 2 "Artist" "$tmp/src/a.mp3" "$tmp/src/missing.mp3"   # one bad file rejects the batch

# an existing artist folder is reused whatever the case; a new artist gets a new folder
out=$(./rekordbox-add.sh "existing ARTIST" "$tmp/src/b.FLAC" 2>&1)
grep -qF "using existing folder: $tmp/DJ/Existing Artist" <<<"$out" || { echo "FAIL: existing folder not reused: $out"; fail=1; }
grep -qF "would move: $tmp/src/b.FLAC -> $tmp/DJ/Existing Artist/" <<<"$out" || { echo "FAIL: wrong destination: $out"; fail=1; }
out=$(./rekordbox-add.sh "New Artist" "$tmp/src/b.FLAC" 2>&1)
grep -qF "new folder: $tmp/DJ/New Artist" <<<"$out" || { echo "FAIL: new folder not planned: $out"; fail=1; }
expect 2 "EXISTING artist" "$tmp/src/a.mp3"   # overwrite check follows the reused folder

# dry run and rejections must never move anything
[[ -f $tmp/src/a.mp3 && -f $tmp/src/b.FLAC && ! -e $tmp/DJ/Artist ]] || { echo "FAIL: a file was moved"; fail=1; }

[[ $fail -eq 0 ]] && echo "all passed"
exit $fail
