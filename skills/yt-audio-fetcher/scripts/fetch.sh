#!/usr/bin/env bash
# Download the audio track of one or more YouTube videos as mp3s.
# Usage: fetch.sh <youtube-url> [<youtube-url> ...]
# Env:   YT_AUDIO_OUT_DIR    override the destination (default: the Windows Downloads folder)
#        YT_AUDIO_DRY_RUN=1  print what would be fetched instead of running yt-dlp (used by the tests)
set -uo pipefail

OUT_DIR="${YT_AUDIO_OUT_DIR:-/mnt/c/Users/sneak/Downloads}"

# Accept only the URL shapes that carry a single video id. A playlist- or
# channel-only URL has no video to extract, so rejecting it up front gives a
# clearer error than yt-dlp's own failure a few seconds later.
valid_url() {
  local u=$1
  if [[ $u =~ ^https?://(www\.|m\.|music\.)?youtube\.com/watch\?([^[:space:]]*&)?v=[A-Za-z0-9_-]{11}([&#][^[:space:]]*)?$ ]]; then return 0; fi
  if [[ $u =~ ^https?://(www\.|m\.)?youtube\.com/(shorts|live|embed)/[A-Za-z0-9_-]{11}([?#][^[:space:]]*)?$ ]]; then return 0; fi
  if [[ $u =~ ^https?://youtu\.be/[A-Za-z0-9_-]{11}([?#][^[:space:]]*)?$ ]]; then return 0; fi
  return 1
}

if [[ $# -eq 0 ]]; then
  echo "error: no URL given. usage: fetch.sh <youtube-url> [<youtube-url> ...]" >&2
  exit 2
fi

# Validate every URL before downloading anything: a typo in the fifth URL is
# worth catching now rather than after four downloads have already run.
bad=0
for url in "$@"; do
  if [[ -z $url ]] || ! valid_url "$url"; then
    echo "error: not a valid YouTube video URL: ${url:-<empty>}" >&2
    bad=1
  fi
done
if [[ $bad -ne 0 ]]; then
  echo "       expected youtube.com/watch?v=..., youtu.be/..., or youtube.com/shorts|live|embed/..." >&2
  exit 2
fi

if [[ "${YT_AUDIO_DRY_RUN:-}" == "1" ]]; then
  for url in "$@"; do echo "would download: $url -> $OUT_DIR"; done
  exit 0
fi

command -v yt-dlp >/dev/null || { echo "error: yt-dlp is not installed or not on PATH" >&2; exit 127; }
command -v ffmpeg >/dev/null || { echo "error: ffmpeg is not installed; yt-dlp needs it to write mp3" >&2; exit 127; }

mkdir -p "$OUT_DIR"

# One yt-dlp call per URL so a single dead video doesn't abort the rest of the
# batch; --no-playlist keeps a mix/radio URL (…&list=RD…) from pulling the whole queue.
failed=()
for url in "$@"; do
  yt-dlp \
    --no-playlist \
    -x --audio-format mp3 --audio-quality 0 \
    --embed-thumbnail --embed-metadata \
    -P "$OUT_DIR" \
    -o '%(title)s.%(ext)s' \
    "$url" || failed+=("$url")
done

if [[ ${#failed[@]} -gt 0 ]]; then
  echo "error: ${#failed[@]} of $# download(s) failed:" >&2
  printf '  %s\n' "${failed[@]}" >&2
  exit 1
fi
