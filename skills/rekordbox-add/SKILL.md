---
name: rekordbox-add
description: >
  Move audio files into the DJ library at Music/DJ/{artist} and import them into the
  running rekordbox. Use for "add these to rekordbox", "put the tracks in my DJ folder",
  or after yt-audio-fetcher downloads tracks meant for DJing.
---

# rekordbox-add

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Moves files and drives the rekordbox window** — each track is moved (not
> copied) into `/mnt/c/Users/sneak/Music/DJ/<artist>/`, then rekordbox is brought
> to the front and its File > Import > Import Folder dialog is operated for you.

Files audio tracks into the DJ library by artist and adds them to the rekordbox
collection, replaying the manual File > Import > Import Folder steps.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<artist>` (required) | a folder name, no `\ / : * ? " < > \|`, no trailing dot or space | — | The folder under `Music/DJ` the tracks go into. An existing folder with that name in any case is reused; otherwise it's created. |
| `<file> ...` (required) | one or more mp3 / m4a / aac / wav / aif / aiff / flac paths | — | Moved into the artist folder. One bad file rejects the whole batch before anything moves. |
| `REKORDBOX_DJ_DIR` (env) | any directory path | `/mnt/c/Users/sneak/Music/DJ` | The library root. |

## Stop conditions — output an error and exit

Print `error: <reason>` and stop, moving nothing, when either is true:

1. **rekordbox is not running.** The script checks this first (exit 3). Never
   launch rekordbox yourself or fall back to moving files only.
2. **You are not sure which tracks to add, or which artist one belongs to.**
   Certain means the user named the files, or this session just produced them
   (e.g. the paths `yt-audio-fetcher` reported saving). "The new stuff in
   Downloads", a folder with unrelated files mixed in, or a filename that doesn't
   make the artist clear (`Redbone.mp3`, `Kiss of Life.mp3`) are not certain —
   name the file(s) you're unsure about in the error. Never guess.

## Pick the artist folder

- Use the primary artist: `Future - Low Life ft. The Weeknd` → `Future`;
  `Gimme Sympathy - METRIC` → `Metric`; `BICEP | APRICOTS` → `Bicep`.
- If the artist already has a folder, the script moves the tracks into it and
  creates nothing — matched case-insensitively, so `Charli XCX` lands in an
  existing `CHARLI XCX`. Still list `/mnt/c/Users/sneak/Music/DJ/` first: a folder
  spelled differently (`Tyler The Creator` vs `Tyler, The Creator`) only matches if
  you pass its exact name.
- Group the files by artist and run the script once per artist.

## Run it

```bash
bash "$HOME/.agents/skills/rekordbox-add/scripts/rekordbox-add.sh" "<artist>" "<file>" ["<file>" ...]
```

Quote every argument; titles carry spaces, `$`, and brackets.

## What it does

1. Validates the artist name and every file (exists, is audio, name not already
   in the artist folder, no duplicate names). Any failure exits 2, nothing moved.
2. Confirms rekordbox is running (exit 3 if not, nothing moved).
3. Moves the files with `mv -n` into the artist's existing folder under
   `Music/DJ/` (any case), creating `Music/DJ/<artist>/` only when none exists.
4. Runs `scripts/import-folder.ps1`: brings rekordbox to the front, opens
   File > Import > Import Folder with clicks it confirms one at a time, types
   the folder's Windows path into the dialog's Folder box, reads it back, and
   only then clicks Select Folder. Tracks already in the collection from
   earlier runs are skipped by rekordbox.

Safety rails in step 4, each learned from a real misfire:

- Every click needs rekordbox in front **and** owning that exact pixel, so a
  window that grabs focus mid-run never receives a click.
- The main window is the largest visible rekordbox window, not
  `Process.MainWindowHandle`, which points at a short-lived window right after
  an import (clicks then landed at screen 0,0).
- A menu left open by a late click is closed with Esc before clicking File.
- Select Folder is pressed only when the Folder box provably holds the target
  path. With the box empty the dialog selects the folder it shows,
  `Music\DJ`, and rekordbox imports the whole library.

Nobody may use the PC while step 4 runs (~5 s per artist): Windows refuses to
hand rekordbox the foreground while someone is typing elsewhere, and the
script stops with exit 1 rather than click blind. Between artists, rekordbox
is busy analysing new tracks; the script retries for ~30 s before giving up.

## Errors

| Exit | Cause | What to tell the user |
|---|---|---|
| 2 | Bad artist name, missing/non-audio file, or name already in the folder | Relay the script's lines; nothing moved. |
| 3 | rekordbox not running | Start rekordbox and re-run. Nothing moved. |
| 127 | `powershell.exe` not reachable from WSL | The skill needs WSL interop. |
| 1 | Import dialog never opened / didn't accept the folder, or some moves failed | Files that moved are in `Music/DJ/<artist>/`; the user can import that folder by hand. If the dialog never opened, the File menu click missed — adjust `-MenuX`/`-MenuY` in `import-folder.ps1`. |

Report each moved path and the imported folder back to the user.

## Files

| Path | When |
|---|---|
| `scripts/rekordbox-add.sh` | Every run |
| `scripts/import-folder.ps1` | Called by `rekordbox-add.sh`; drives the rekordbox window |
| `scripts/test_rekordbox-add.sh` | After editing `rekordbox-add.sh` — checks the validation gate, no framework |
