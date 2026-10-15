#!/usr/bin/env bash
# new-sesh — spawn a headless Claude Code session, with validation in one place.
#
# Values arrive as argv and are never re-parsed by a shell, so a quote or
# semicolon in a path is data, not code. That is the whole reason this is a
# script and not a snippet in the skill body.
#
#   new-sesh.sh scan <dir>
#   new-sesh.sh prompt-info <file>
#   new-sesh.sh spawn --dir D --out O (--prompt-file F | --prompt-text T)
#
set -uo pipefail

die() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# Global, not local: the EXIT trap fires after cmd_spawn's frame is gone, so a
# local would expand empty there and the cleanup would silently do nothing.
tmp=''

# Reject paths that are not absolute, or whose resolved form escapes into a
# location where a written file becomes instructions or credentials rather than
# data. Resolution matters: /home/u/reports may be a symlink to ~/.ssh.
check_out_path() {
  local out=$1 parent resolved
  [[ $out == /* ]] || die "--out must be absolute: $out"
  # argv already makes metacharacters inert here. This is for downstream: the
  # path is reported back and may end up in a log line or another command, and
  # a newline in a filename can forge a second line of output.
  [[ $out == *[[:cntrl:]]* ]] && die "--out contains a control character"
  parent=$(dirname -- "$out")
  [[ -d $parent ]] || die "--out parent does not exist: $parent"
  # Must be fatal. A failed cd used to leave resolved as "/<basename>", which
  # matches no pattern below, so every check that follows silently passed.
  resolved=$(cd -- "$parent" && pwd -P) || die "--out parent is not searchable: $parent"
  resolved=${resolved%/}/$(basename -- "$out")
  # ${HOME%/} because a trailing slash on HOME is a legitimate value that would
  # otherwise put "//" in every pattern below and disable all of them at once.
  local home=${HOME%/}
  case $resolved in
    "$home"/.ssh/*|"$home"/.claude/*|"$home"/.config/*|"$home"/.local/bin/*|"$home"/bin/*)
      die "--out resolves into a protected location: $resolved" ;;
    "$home"/.*) die "--out resolves to a dotfile: $resolved" ;;
  esac
  # Component check, not a $HOME denylist: a project-scoped .claude/ or .git/ is
  # loaded as instructions or executed just as surely as the user-scope one, and
  # lives nowhere near $HOME.
  case $resolved in
    */.claude/*|*/.git/*|*/.vscode/*|*/.idea/*|*/.ssh/*)
      die "--out resolves inside a config directory: $resolved" ;;
  esac
  case $(basename -- "$resolved") in
    .*|*.mcp.json|CLAUDE.md|CLAUDE.local.md|AGENTS.md|Makefile|conftest.py)
      die "--out would create an instruction or auto-loaded file: $resolved" ;;
  esac
  # -e is false for a symlink to a missing target, which > would then create.
  [[ -e $out || -L $out ]] && die "--out already exists: $out"
  return 0
}

# One line saying what is actually risky about a finding, so the caller reads a
# digest instead of the files. "Read every PRESENT file" is unsatisfiable: on a
# normal box $HOME/.claude alone is tens of thousands of files.
describe() {
  local p=$1
  case $(basename -- "$p") in
    settings.json|settings.local.json)
      # Only the keys that change what the child may do or run.
      local keys
      keys=$(command grep -oE '"(hooks|env|permissions|defaultMode|enableAllProjectMcpServers)"' "$p" 2>/dev/null \
             | sort -u | tr -d '"' | tr '\n' ' ')
      printf '    risky-keys: %s\n' "${keys:-none}" ;;
    .mcp.json)
      printf '    mcp-servers: %s\n' "$(command grep -coE '"command"' "$p" 2>/dev/null || echo '?')" ;;
    CLAUDE.md|AGENTS.md|CLAUDE.local.md)
      printf '    %s bytes, @-imports: %s\n' "$(wc -c < "$p" 2>/dev/null || echo '?')" \
        "$(command grep -c '^@' "$p" 2>/dev/null || echo 0)" ;;
    config)  # .git/config
      local k
      k=$(command grep -oE '(fsmonitor|sshCommand|pager|hooksPath|insteadOf)' "$p" 2>/dev/null \
          | sort -u | tr '\n' ' ')
      printf '    exec-keys: %s\n' "${k:-none}" ;;
    hooks|skills|agents|commands)
      printf '    entries: %s\n' "$(ls -A -- "$p" 2>/dev/null | head -20 | tr '\n' ' ')" ;;
    envrc|.envrc)
      printf '    %s lines (not loaded by claude -p; presence only)\n' "$(wc -l < "$p" 2>/dev/null || echo '?')" ;;
  esac
}

cmd_scan() {
  local dir=${1:-}
  [[ -n $dir ]] || die "scan needs a directory"
  # Control characters in a path would let a directory name forge output lines,
  # including the SCAN COMPLETE sentinel the caller gates on.
  [[ $dir == *[[:cntrl:]]* ]] && die "--dir contains a control character"
  [[ -d $dir ]] || die "not a directory: $dir"
  [[ -x $dir && -r $dir ]] || die "not readable/searchable: $dir"
  local root home
  root=$(cd -- "$dir" && pwd -P) || die "cannot resolve: $dir"
  [[ $root == *[[:cntrl:]]* ]] && die "resolved path contains a control character"
  home=${HOME%/}

  # Two scopes, counted separately. User-scope config under $HOME/.claude applies
  # to every session on this machine and is the caller's own -- reporting it as a
  # risk makes the gate fire on 100% of runs, including on an empty directory,
  # which trains the caller to click through it. Only tree findings gate.
  local d=$root tree=0 user=0 scope
  while :; do
    case $d in "$home"|"$home"/.claude*) scope=user ;; *) scope=tree ;; esac
    for p in CLAUDE.md CLAUDE.local.md AGENTS.md .mcp.json .envrc \
             .claude/settings.json .claude/settings.local.json \
             .claude/hooks .claude/skills .claude/agents .claude/commands \
             .git/hooks .git/config; do
      if [[ -e $d/$p || -L $d/$p ]]; then
        printf '%s %s\n' "$scope" "$d/$p"
        describe "$d/$p"
        [[ $scope == tree ]] && tree=$((tree + 1)) || user=$((user + 1))
      fi
    done
    [[ $d == / || $d == "$home" ]] && break
    d=$(dirname -- "$d")
  done
  # A worktree has .git as a FILE, so the .git/* probes above find nothing while
  # the real hooks still run. Resolve and report it rather than scoring 0.
  if [[ -f $root/.git ]]; then
    printf 'tree %s\n    git-dir: %s\n' "$root/.git" "$(command grep -oE 'gitdir:.*' "$root/.git" 2>/dev/null)"
    tree=$((tree + 1))
  fi
  printf 'SCAN COMPLETE root=%s tree=%d user=%d\n' "$root" "$tree" "$user"
}

cmd_prompt_info() {
  local f=${1:-}
  [[ -n $f ]] || die "prompt-info needs a file"
  [[ -f $f ]] || die "not a regular file: $f"
  [[ -r $f ]] || die "not readable: $f"
  local lines bytes
  lines=$(wc -l < "$f") || die "cannot read: $f"
  bytes=$(wc -c < "$f") || die "cannot read: $f"
  [[ $bytes -gt 0 ]] || die "prompt is empty: $f"
  # Read truncates on volume and on long lines, so report both. A 4MB one-liner
  # is 0 lines and still exceeds what the caller can actually see.
  printf 'lines=%s bytes=%s\n' "$lines" "$bytes"
  if [[ $bytes -gt 40000 ]]; then
    printf 'OVERSIZE: read it in offsets before gating; do not spawn on a prefix\n'
  fi
}

cmd_spawn() {
  local dir='' out='' pfile='' ptext='' have_text=0 sid claude_bin
  while [[ $# -gt 0 ]]; do
    case $1 in
      --dir)         dir=${2:?--dir needs a value}; shift 2 ;;
      --out)         out=${2:?--out needs a value}; shift 2 ;;
      --prompt-file) pfile=${2:?--prompt-file needs a value}; shift 2 ;;
      --prompt-text) ptext=${2:?--prompt-text needs a value}; have_text=1; shift 2 ;;
      *) die "unknown argument: $1" ;;
    esac
  done
  # The session id comes first because the default --out is named after it. Any
  # other order makes the documented default impossible: the filename would
  # carry a uuid unrelated to the id the child is actually given.
  # `read` is a builtin, so the fallback survives a stripped PATH -- unlike a
  # `cat` or `python3` subprocess, which is what the first two versions used.
  sid=$(uuidgen 2>/dev/null) || read -r sid < /proc/sys/kernel/random/uuid 2>/dev/null \
    || die "cannot generate session id"
  [[ $sid =~ ^[0-9a-fA-F-]{36}$ ]] || die "generated session id is malformed: $sid"

  : "${dir:=$PWD}"                    # default: current directory
  : "${out:=/tmp/new-sesh-$sid}"      # default: named for the real session id
  [[ -n $pfile || $have_text -eq 1 ]] || die "one of --prompt-file / --prompt-text is required"
  [[ -n $pfile && $have_text -eq 1 ]] && die "--prompt-file and --prompt-text are mutually exclusive"
  [[ -n ${CLAUDE_NEW_SESSION_DEPTH:-} ]] && die "refusing to nest: already inside a spawned session"

  [[ $dir == /* ]] || die "--dir must be absolute: $dir"
  [[ -d $dir && -x $dir ]] || die "--dir is not a searchable directory: $dir"
  check_out_path "$out"

  # Resolve claude before cd, so an executable named `claude` inside an
  # untrusted $dir cannot win via PATH.
  claude_bin=$(command -v claude) || die "claude not found on PATH"
  [[ -x $claude_bin ]] || die "claude is not executable: $claude_bin"

  umask 077
  if [[ $have_text -eq 1 ]]; then
    # Written by us, in our own private temp file -- never beside $out, where
    # the path is predictable and may be a symlink planted by someone else.
    tmp=$(mktemp) || die "cannot create temp file"
    # Without the trap the file leaks on every die() below -- 0600 in /tmp,
    # containing whatever the user pasted into the prompt.
    trap 'rm -f -- "$tmp"' EXIT INT TERM
    printf '%s' "$ptext" > "$tmp" || die "cannot write prompt"
    pfile=$tmp
  else
    [[ -f $pfile && -r $pfile ]] || die "--prompt-file is not a readable regular file: $pfile"
    [[ -s $pfile ]] || die "--prompt-file is empty: $pfile"
  fi

  local prompt status
  prompt=$(cat -- "$pfile") || die "cannot read prompt: $pfile"
  [[ -n ${prompt//[[:space:]]/} ]] || die "prompt is whitespace only"

  # Open the target ONCE and write through the descriptor. noclobber refuses an
  # existing file but not creation through a parent directory swapped after
  # check_out_path resolved it; reopening by path for the write would reopen
  # whatever is there by then. One open, then every check and the child's whole
  # output go through that same descriptor.
  set -C
  exec 3> "$out" || die "cannot create output file: $out"
  set +C
  # -f on /dev/fd/3 tests the object actually opened, not the path -- so a fifo
  # or device swapped in during the window fails here rather than silently
  # receiving the entire session.
  [[ -f /dev/fd/3 ]] || die "output is not a regular file: $out"

  cd -- "$dir" || die "cannot enter: $dir"

  # sid=/out=/exit= are printed as one block, after the last thing that can
  # fail. Previously sid= and out= printed before the prompt was validated, so a
  # late failure emitted both and then no exit= line -- and step 5 of the skill
  # tells the caller to read exit= first. Now the three appear together or not
  # at all, and their absence unambiguously means "refused before starting".
  printf 'sid=%s\n' "$sid"
  printf 'out=%s\n' "$out"

  CLAUDE_NEW_SESSION_DEPTH=1 "$claude_bin" -p --session-id "$sid" -- "$prompt" \
    >&3 2>&3 < /dev/null
  status=$?
  exec 3>&-
  printf 'exit=%d\n' "$status"
  return "$status"
}

case ${1:-} in
  scan)         shift; cmd_scan "$@" ;;
  prompt-info)  shift; cmd_prompt_info "$@" ;;
  spawn)        shift; cmd_spawn "$@" ;;
  *) printf 'usage: new-sesh.sh {scan <dir>|prompt-info <file>|spawn --dir D --out O (--prompt-file F|--prompt-text T)}\n' >&2; exit 2 ;;
esac
