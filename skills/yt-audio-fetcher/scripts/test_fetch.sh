#!/usr/bin/env bash
# Checks the URL gate in fetch.sh. Run: ./test_fetch.sh
set -uo pipefail
cd "$(dirname "$0")"
export YT_AUDIO_DRY_RUN=1
fail=0

expect() { # expect <accept|reject> <url> [url ...]
  local want=$1; shift
  local out rc
  out=$(./fetch.sh "$@" 2>&1); rc=$?
  if [[ $want == accept && $rc -ne 0 ]] || [[ $want == reject && $rc -eq 0 ]]; then
    echo "FAIL: expected $want for [$*] (exit $rc)"; fail=1
  fi
  if [[ $want == accept ]]; then
    local n; n=$(grep -c '^would download:' <<<"$out")
    if [[ $n -ne $# ]]; then echo "FAIL: expected $# download(s) for [$*], planned $n"; fail=1; fi
  fi
}

# single URL
expect accept "https://www.youtube.com/watch?v=W50HtcPAeSs"
expect accept "https://www.youtube.com/watch?v=W50HtcPAeSs&list=RDW50HtcPAeSs"
expect accept "https://youtu.be/W50HtcPAeSs?t=42"
expect accept "https://youtube.com/shorts/W50HtcPAeSs"
expect accept "https://music.youtube.com/watch?v=W50HtcPAeSs"

# multiple URLs
expect accept "https://youtu.be/W50HtcPAeSs" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
expect accept "https://youtu.be/W50HtcPAeSs" "https://youtu.be/dQw4w9WgXcQ" "https://youtube.com/shorts/aaaaaaaaaaa"

# a bad URL anywhere in the list fails the whole batch
expect reject "https://youtu.be/W50HtcPAeSs" "https://vimeo.com/123456789"
expect reject "https://vimeo.com/123456789" "https://youtu.be/W50HtcPAeSs"

# no URL at all
expect reject

# invalid single URLs
expect reject ""
expect reject "not a url"
expect reject "https://vimeo.com/123456789"
expect reject "https://www.youtube.com/playlist?list=RDW50HtcPAeSs"
expect reject "https://www.youtube.com/@somechannel"
expect reject "https://www.youtube.com/watch?v=tooshort"
expect reject "youtube.com/watch?v=W50HtcPAeSs"

[[ $fail -eq 0 ]] && echo "all URL-gate checks passed"
exit $fail
