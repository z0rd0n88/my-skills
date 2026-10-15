#!/usr/bin/env bash
# Move audio files into the DJ library under an artist folder, then import that
# folder into the running rekordbox (File > Import > Import Folder).
# Usage: rekordbox-add.sh <artist> <file> [<file> ...]
# Env:   REKORDBOX_DJ_DIR          library root (default: /mnt/c/Users/sneak/Music/DJ)
#        REKORDBOX_ADD_DRY_RUN=1   validate and print the plan; move nothing, skip rekordbox (used by the tests)
set -uo pipefail

DJ_DIR="${REKORDBOX_DJ_DIR:-/mnt/c/Users/sneak/Music/DJ}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ $# -lt 2 ]]; then
  echo "error: need an artist and at least one file. usage: rekordbox-add.sh <artist> <file> [<file> ...]" >&2
  exit 2
fi

artist=$1; shift

# Reuse an existing artist folder whatever its case ("Charli XCX" -> "CHARLI XCX")
# so the library never grows a second folder for the same artist.
dest="$DJ_DIR/$artist"
if [[ -d $DJ_DIR ]]; then
  shopt -s nocasematch
  for d in "$DJ_DIR"/*/; do
    d=${d%/}
    if [[ ${d##*/} == "$artist" ]]; then dest=$d; break; fi
  done
  shopt -u nocasematch
fi

# Validate everything before touching anything: a bad sixth file should not
# leave five already moved.
bad=0
if [[ -z ${artist//[[:space:]]/} || $artist == . || $artist == .. || $artist =~ [\\/:*?\"\<\>|] || $artist =~ [.[:space:]]$ ]]; then
  echo "error: not a usable folder name for the artist: '$artist'" >&2
  bad=1
fi
declare -A seen=()
for f in "$@"; do
  name=$(basename -- "$f")
  if [[ ! -f $f ]]; then
    echo "error: file not found: $f" >&2; bad=1
  elif [[ ! ${name,,} =~ \.(mp3|m4a|aac|wav|aif|aiff|flac)$ ]]; then
    echo "error: not an audio file rekordbox imports: $f" >&2; bad=1
  elif [[ -e $dest/$name ]]; then
    echo "error: already in the library, would overwrite: $dest/$name" >&2; bad=1
  elif [[ -n ${seen[$name]:-} ]]; then
    echo "error: two files share the name $name" >&2; bad=1
  fi
  seen[$name]=1
done
[[ $bad -ne 0 ]] && { echo "       nothing was moved" >&2; exit 2; }

if [[ -d $dest ]]; then folder_msg="using existing folder: $dest"; else folder_msg="new folder: $dest"; fi

if [[ "${REKORDBOX_ADD_DRY_RUN:-}" == "1" ]]; then
  echo "$folder_msg"
  for f in "$@"; do echo "would move: $f -> $dest/"; done
  echo "would import: $dest"
  exit 0
fi

command -v powershell.exe >/dev/null || { echo "error: powershell.exe not reachable from WSL; this skill drives rekordbox on Windows" >&2; exit 127; }

if ! powershell.exe -NoProfile -Command 'if (Get-Process rekordbox -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }' >/dev/null 2>&1; then
  echo "error: rekordbox is not running. start it and re-run; nothing was moved" >&2
  exit 3
fi

echo "$folder_msg"
if [[ ! -d $dest ]]; then
  mkdir -- "$dest" || { echo "error: could not create $dest" >&2; exit 1; }
fi

moved=0; failed=()
for f in "$@"; do
  if mv -n -- "$f" "$dest/" && [[ -f $dest/$(basename -- "$f") && ! -e $f ]]; then
    echo "moved: $dest/$(basename -- "$f")"; moved=$((moved + 1))
  else
    failed+=("$f")
  fi
done

if [[ $moved -eq 0 ]]; then
  echo "error: no file could be moved; nothing imported:" >&2
  printf '  %s\n' "${failed[@]}" >&2
  exit 1
fi

if ! powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$HERE/import-folder.ps1")" -Folder "$(wslpath -w "$dest")"; then
  echo "error: files are in $dest but the rekordbox import failed; import it by hand (File > Import > Import Folder)" >&2
  exit 1
fi

if [[ ${#failed[@]} -gt 0 ]]; then
  echo "error: ${#failed[@]} of $# file(s) could not be moved and were not imported:" >&2
  printf '  %s\n' "${failed[@]}" >&2
  exit 1
fi
