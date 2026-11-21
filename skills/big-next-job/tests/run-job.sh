#!/usr/bin/env bash
# Tests for scripts/run-job with a fake claude (tests/fake-bin/claude). Needs tmux and python3, no
# Claude account. Runs on a private tmux server and runtime dir; touches nothing else.
# Usage: skills/big-next-job/tests/run-job.sh        (about a minute)
# shellcheck disable=SC2015  # `ok` always succeeds, so `test && ok || bad` is a safe if/else here
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RUNJOB="${RUNJOB:-$HERE/../scripts/run-job}"
WORK=$(mktemp -d)
export TMUX_TMPDIR="$WORK/tmux" XDG_RUNTIME_DIR="$WORK/run" PATH="$HERE/fake-bin:$PATH"
mkdir -p "$TMUX_TMPDIR" "$XDG_RUNTIME_DIR"
unset TMUX CLAUDE_FLAGS
pass=0; fail=0
ok()  { echo "  ok   $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }
# every job gets its own tmux server (tmux -L run-job-<name>); stop them all
cleanup() { local s; for s in "$TMUX_TMPDIR"/tmux-*/*; do tmux -S "$s" kill-server 2>/dev/null; done; rm -rf "$WORK"; }
trap cleanup EXIT

# job <name> <plan...>: a fresh job dir under its own workdir; sets J (job dir).
job() {
  local name=$1; shift
  J="$WORK/$name/.big-next-job"; mkdir -p "$J"
  printf 'the brief\n' > "$J/brief.md"
  printf 'status: active\n\n## Next action\nstart\n' > "$J/checkpoint.md"
  echo "$*" > "$J/plan"
}
# run [env...]: run-job on $J in the foreground; sets RC and SECS.
run() {
  local t0=$SECONDS
  env FAKE_PLAN="$J/plan" "$@" "$RUNJOB" "$J" > "$J/out" 2>&1; RC=$?
  SECS=$((SECONDS - t0))
}
has() { grep -q -- "$1" "$J/run.log"; }

echo "finishing"
job finish finish; run
[ "$RC" = 0 ] && has "job done" && ok "a child that sets done ends the job (exit 0)" || bad "done (rc $RC)"

echo "a crashed child is noticed at once, not after the timeout"
job crash crash finish; run JOB_CHILD_TIMEOUT=600
[ "$RC" = 0 ] && [ "$SECS" -lt 30 ] && ok "crash seen, next child finished, ${SECS}s with a 600s timeout" || bad "crash (rc $RC, ${SECS}s)"
has "exited without finishing its turn after .* (exit 3)" && ok "logs the exit code" || bad "logs the exit code"
has "child's last screen" && has "fake child 1: crash" && ok "logs the dead child's last screen" || bad "logs the last screen"

echo "API errors back off and are not stalls"
job overloaded overloaded finish; run JOB_API_BACKOFF=2 JOB_CHILD_TIMEOUT=600
[ "$RC" = 0 ] && [ "$SECS" -lt 30 ] && ok "overloaded: next child after the backoff (${SECS}s)" || bad "overloaded (rc $RC, ${SECS}s)"
has "API error overloaded; next child in 2s" && ok "logs the error and the wait" || bad "logs the overloaded wait"
job ratelimit rate_limit rate_limit rate_limit finish; run JOB_LIMIT_BACKOFF=1
[ "$RC" = 0 ] && ok "three rate limits in a row are not two stalls (exit 0)" || bad "rate limits (rc $RC)"
has "not counted as a stall" && ok "says why they are not stalls" || bad "not-a-stall line"
job exit75 exit75 finish; run JOB_LIMIT_BACKOFF=1
[ "$RC" = 0 ] && has "exit 75 is a usage limit" && ok "claude exit 75 is treated as a usage limit" || bad "exit 75 (rc $RC)"

echo "timeouts, stalls, caps"
job hang hang finish; run JOB_CHILD_TIMEOUT=3
[ "$RC" = 0 ] && has "child 1 timed out after 3s of work" && ok "a hung child is killed at the timeout" || bad "hang (rc $RC)"
job stall noop noop; run
[ "$RC" = 5 ] && ok "two children with no progress stop the chain (exit 5)" || bad "stall (rc $RC)"
job cap progress progress progress; run JOB_MAX_CHILDREN=2
[ "$RC" = 4 ] && ok "the child cap stops the run (exit 4)" || bad "cap (rc $RC)"
run JOB_MAX_CHILDREN=1
has "child 3 launched" && ok "child numbers continue across runs" || bad "numbering across runs"
job badnum finish; run JOB_CHILD_TIMEOUT=010
[ "$RC" = 1 ] && grep -q "not a whole number" "$J/out" && ok "a number with a leading zero is refused" || bad "bad number (rc $RC)"

echo "robustness"
job badjson badjson finish; run
[ "$RC" = 0 ] && has "hook payload is not a JSON object" && ok "a garbled Stop payload is logged, not fatal" || bad "bad json (rc $RC)"

echo "trust dialog"
job trustearly truststart finish; run
[ -s "$J/keys-1" ] && ok "answered while the child starts" || bad "trust dialog at start was not answered"
job trustlate trustlate finish; run JOB_TRUST_SECONDS=2
[ ! -e "$J/keys-1" ] && ok "no keys typed when the text shows up later in a working child" || bad "keys typed into a working child"

echo "each job has its own tmux server, with this run's environment"
job envcheck finish; run
tmux -L run-job-envcheck has-session 2>/dev/null && bad "server left running after the job" || ok "its tmux server is gone after the job"

echo "one runner per job, and stopping it closes the child"
job lock hang; FAKE_PLAN="$J/plan" JOB_CHILD_TIMEOUT=60 "$RUNJOB" "$J" > "$J/out1" 2>&1 & first=$!
for _ in $(seq 1 50); do has "child 1 launched" 2>/dev/null && break; sleep 0.2; done
run
[ "$RC" = 1 ] && grep -q "already drives" "$J/out" && ok "a second run-job on the same job is refused" || bad "lock (rc $RC)"
kill -TERM "$first"; wait "$first"; rc1=$?
[ "$rc1" = 143 ] && ok "TERM stops run-job (exit 143)" || bad "TERM exit (rc $rc1)"
tmux -L run-job-lock list-windows -a 2>/dev/null | grep -q 'child-' && bad "child window left behind" || ok "its child and tmux server are closed"
ls "$XDG_RUNTIME_DIR"/run-job-*.lock >/dev/null 2>&1 && bad "lock file left behind" || ok "its lock is removed"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
