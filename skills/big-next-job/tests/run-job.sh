#!/usr/bin/env bash
# Tests for scripts/run-job with a fake claude (tests/fake-bin/claude). Needs tmux and python3, no
# Claude account. Runs on a private tmux server and runtime dir; touches nothing else.
# Usage: skills/big-next-job/tests/run-job.sh        (about four minutes)
# shellcheck disable=SC2015  # `ok` always succeeds, so `test && ok || bad` is a safe if/else here
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RUNJOB="${RUNJOB:-$HERE/../scripts/run-job}"
WORK=$(mktemp -d)
export TMUX_TMPDIR="$WORK/tmux" XDG_RUNTIME_DIR="$WORK/run" PATH="$HERE/fake-bin:$PATH"
mkdir -p "$TMUX_TMPDIR" "$XDG_RUNTIME_DIR"
unset TMUX CLAUDE_FLAGS
export FAKE_TAG="runjob-$$"   # names this run's fake background shells, so a parallel suite's are not touched
pass=0; fail=0
ok()  { echo "  ok   $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }
# every job gets its own tmux server (tmux -L run-job-<name>-<hash>); stop them all
cleanup() {
  local s; for s in "$TMUX_TMPDIR"/tmux-*/*; do tmux -S "$s" kill-server 2>/dev/null; done
  pkill -f "snapshot-bash-$FAKE_TAG" 2>/dev/null; rm -rf "$WORK"
}
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
has() { grep -q -- "$1" "$J/run.log" 2>/dev/null; }
# sock: the tmux server name run-job logged for $J
sock_of() { sed -n 's/.*(watch: tmux -L \([^ ]*\) attach.*/\1/p' "$1/run.log" | head -1; }
sock() { sock_of "$J"; }

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

echo "status"
"$RUNJOB" status > "$WORK/status.out" 2>&1; rc=$?
[ "$rc" = 1 ] && grep -q "usage: run-job status <job-dir>" "$WORK/status.out" && ok "status with no job dir prints usage (exit 1)" || bad "status with no job dir (rc $rc: $(cat "$WORK/status.out"))"
mkdir -p "$WORK/nojob"; "$RUNJOB" status "$WORK/nojob" > "$WORK/status.out" 2>&1; rc=$?
[ "$rc" = 1 ] && grep -q "no $WORK/nojob/checkpoint.md" "$WORK/status.out" && ok "status on a dir with no checkpoint says so (exit 1)" || bad "status with no checkpoint (rc $rc: $(cat "$WORK/status.out"))"
job status finish; "$RUNJOB" status "$J" > "$J/status.out" 2>&1; rc=$?
[ "$rc" = 0 ] && [ "$(cat "$J/status.out")" = "status: active" ] && ok "status on a job dir prints the checkpoint header (exit 0)" || bad "status on a job dir (rc $rc: $(cat "$J/status.out"))"

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
[ -n "$(sock)" ] && ! tmux -L "$(sock)" has-session 2>/dev/null && ok "its tmux server is gone after the job" || bad "server $(sock) left running, or no server name logged"
# F12: the child must get this run's environment, not that of a server an earlier run left behind.
# F14: and the screens of the windows that earlier run kept (JOB_KEEP_WINDOWS) are saved, not lost.
job envstale finish finish; run RUNJOB_PROBE=old JOB_KEEP_WINDOWS=1
tmux -L "$(sock)" has-session 2>/dev/null || bad "setup: the kept server is not running"
printf 'status: active\n' > "$J/checkpoint.md"; run RUNJOB_PROBE=new
[ "$(cat "$J/env-2" 2>/dev/null)" = new ] && ok "a child gets this run's environment, not a leftover server's" || bad "child 2 saw RUNJOB_PROBE='$(cat "$J/env-2" 2>/dev/null)'"
sed -n '/earlier run left/,$p' "$J/run.log" | grep -q 'fake child 1: finish' && ok "an earlier run's kept windows have their screens saved to run.log" || bad "kept window screens lost on restart"
job 'odd name.x' hang; FAKE_PLAN="$J/plan" JOB_CHILD_TIMEOUT=60 "$RUNJOB" "$J" > "$J/out1" 2>&1 & bg=$!
for _ in $(seq 1 50); do has "child 1 launched" 2>/dev/null && break; sleep 0.2; done
[[ $(sock) =~ ^run-job-odd_name_x-[0-9a-f]{8}$ ]] && tmux -L "$(sock)" has-session -t job-odd_name_x 2>/dev/null && ok "server and session are named run-job-<name>-<hash> / job-<name>, odd characters as _" || bad "server name ($(sock); $(ls "$TMUX_TMPDIR"/tmux-*/))"
kill -TERM "$bg"; wait "$bg" 2>/dev/null

echo "two jobs whose workdirs share a name do not touch each other"
job one/api hang; A="$J"
FAKE_PLAN="$A/plan" JOB_CHILD_TIMEOUT=60 "$RUNJOB" "$A" > "$A/out1" 2>&1 & first=$!
for _ in $(seq 1 50); do grep -q "child 1 launched" "$A/run.log" 2>/dev/null && break; sleep 0.2; done
job two/api finish; run
[ "$RC" = 0 ] && ok "the second job (two/api) finished (exit 0)" || bad "second job (rc $RC)"
J="$A"
[ "$(sock)" != "$(sock_of "$WORK/two/api/.big-next-job")" ] && ok "each got its own tmux server" || bad "shared server $(sock)"
sleep 2   # run-job notices a dead child within two polls
! has "exited without finishing\|timed out" && tmux -L "$(sock)" list-windows -t job-api 2>/dev/null | grep -q child-1 \
  && ok "the first job's child is still running" || bad "first job's child was disturbed: $(grep -v '^fake' "$A/run.log" | tail -3)"
kill -TERM "$first"; wait "$first" 2>/dev/null

echo "one runner per job, and stopping it closes the child"
job lock hang; FAKE_PLAN="$J/plan" JOB_CHILD_TIMEOUT=60 "$RUNJOB" "$J" > "$J/out1" 2>&1 & first=$!
for _ in $(seq 1 50); do has "child 1 launched" 2>/dev/null && break; sleep 0.2; done
run
[ "$RC" = 1 ] && grep -q "already drives" "$J/out" && ok "a second run-job on the same job is refused" || bad "lock (rc $RC)"
kill -TERM "$first"; wait "$first"; rc1=$?
[ "$rc1" = 143 ] && ok "TERM stops run-job (exit 143)" || bad "TERM exit (rc $rc1)"
tmux -L "$(sock)" list-windows -a 2>/dev/null | grep -q 'child-' && bad "child window left behind" || ok "its child and tmux server are closed"
printf 'status: active\n' > "$J/checkpoint.md"; echo finish > "$J/plan"; run
[ "$RC" = 0 ] && ok "its lock is released: the next run starts" || bad "rerun after TERM (rc $RC)"

# F14: a lock left by a dead runner must not let two new runners both start.
job race hang hang hang hang hang hang hang hang hang hang hang hang ; LOCKF="$XDG_RUNTIME_DIR/run-job-$(printf '%s' "$J" | sha256sum | cut -c1-16).lock"
won=0
for try in 1 2 3 4 5; do
  echo "999999 1" > "$LOCKF"   # a dead runner's lock (pid 999999 does not exist)
  rm -f "$J/run.log" "$J/out-a" "$J/out-b"; printf 'status: active\n' > "$J/checkpoint.md"
  FAKE_PLAN="$J/plan" JOB_CHILD_TIMEOUT=60 "$RUNJOB" "$J" > "$J/out-a" 2>&1 & a=$!
  FAKE_PLAN="$J/plan" JOB_CHILD_TIMEOUT=60 "$RUNJOB" "$J" > "$J/out-b" 2>&1 & b=$!
  sleep 3
  n=$(grep -c ' launched ' "$J/run.log" 2>/dev/null); refused=$(cat "$J/out-a" "$J/out-b" | grep -c "already drives")
  kill -TERM $a $b 2>/dev/null; wait $a $b 2>/dev/null
  [ "$n" = 1 ] && [ "$refused" = 1 ] || { won=$try; break; }
done
[ "$won" = 0 ] && ok "two runners racing for a dead runner's lock: exactly one starts (5 tries)" || { bad "race try $won: $n children launched, $refused refused"; head -3 "$J/out-a" "$J/out-b" "$J/run.log"; }


echo "background work"
for mode in background bglate bgtree bgfooter; do
  job "bg-$mode" "$mode" finish
  run JOB_CHILD_TIMEOUT=60 JOB_BG_SETTLE=4
  case $mode in
    background) what="a turn that leaves a background shell is waited through to the turn it starts, not a stall" ;;
    bglate) what="... also when the shell ends before the Stop and the turn follows it" ;;
    bgtree) what="... also when only the process tree shows the shell" ;;
    *) what="... also when only the status line shows the shell" ;;
  esac
  [ "$RC" = 0 ] && grep -q "progress by child 1" "$J/checkpoint.md" && ! has "stall" && ok "$what" || { bad "$what (rc $RC)"; cat "$J/run.log"; }
done
job bgnofollow bgnofollow finish
run JOB_CHILD_TIMEOUT=60 JOB_BG_SETTLE=4
[ "$RC" = 0 ] && has "child 1 left checkpoint.md unchanged (stall 1/2)" && [ "$SECS" -lt 25 ] \
  && ok "a shell that ends with no turn after it is waited on only JOB_BG_SETTLE seconds (${SECS}s)" || { bad "no follow-up turn (rc $RC, ${SECS}s)"; cat "$J/run.log"; }
job bgforever bgforever finish
run JOB_CHILD_TIMEOUT=60 JOB_BG_WAIT=3 JOB_BG_SETTLE=2 JOB_KEEP_WINDOWS=1
[ "$RC" = 0 ] && has "child 1 still has background work after 3s; taking its last reply and closing it" && has "child 1 left checkpoint.md unchanged (stall 1/2)" \
  && ok "a background shell that never ends is capped by JOB_BG_WAIT, then counts as a stall" || { bad "never-ending background shell (rc $RC)"; cat "$J/run.log"; }
sleep 1; ! pgrep -f "snapshot-bash-$FAKE_TAG.sh 2>/dev/null; sleep 60" >/dev/null && ok "that child is closed even with JOB_KEEP_WINDOWS, its shell with it" || bad "the capped child or its shell was left running"
# Time held by session-airspace does not count toward JOB_BG_WAIT (a held shell cannot finish).
job bgheld bgforever finish
FAKE_PLAN="$J/plan" JOB_CHILD_TIMEOUT=60 JOB_BG_WAIT=4 JOB_BG_SETTLE=2 "$RUNJOB" "$J" > "$J/out" 2>&1 & rj=$!
for _ in $(seq 1 50); do has "child 1 ended its turn with background work" && break; sleep 0.2; done
cpid=$(pgrep -P "$(tmux -L "$(sock)" display -p -t job-bgheld:child-1 '#{pane_pid}' 2>/dev/null)" | head -1)
kill -STOP "$cpid" 2>/dev/null; sleep 6; kill -CONT "$cpid" 2>/dev/null
wait "$rj"; RC=$?
t1=$(sed -n 's/^\(.\{20\}\) child 1 ended its turn with background work.*/\1/p' "$J/run.log"); t2=$(sed -n 's/^\(.\{20\}\) child 1 still has background work.*/\1/p' "$J/run.log")
gap=$(( $(date -d "${t2:-x}" +%s 2>/dev/null || echo 0) - $(date -d "${t1:-x}" +%s 2>/dev/null || echo 0) ))
[ "$RC" = 0 ] && [ -n "$t1" ] && [ -n "$t2" ] && [ "$gap" -ge 8 ] && [ "$gap" -le 30 ] && ok "time held does not count toward JOB_BG_WAIT (capped after ${gap}s: 4s + 6s held)" || { bad "held time and JOB_BG_WAIT (rc $RC, gap ${gap}s)"; cat "$J/run.log"; }
for mode in bgagent bgagentlate bgmonitor bgmonfooter; do
  job "bg-$mode" "$mode" finish
  run JOB_CHILD_TIMEOUT=60 JOB_BG_SETTLE=4
  case $mode in
    bgagent) what="a turn that leaves a background subagent is waited through to the turn it starts" ;;
    bgagentlate) what="... also when the subagent ends before the Stop" ;;
    bgmonitor) what="... and a background monitor" ;;
    *) what="... also when only the status line shows the monitor" ;;
  esac
  { [ "$mode" = bgagentlate ] || has "child 1 ended its turn with background work running"; } \
    && [ "$RC" = 0 ] && grep -q "progress by child 1" "$J/checkpoint.md" && ! has "stall" && ok "$what" || { bad "$what (rc $RC)"; cat "$J/run.log"; }
done
run JOB_BG_WAIT=07
[ "$RC" = 1 ] && grep -q "JOB_BG_WAIT=07 is not a whole number" "$J/out" && ok "JOB_BG_WAIT is validated like the other numbers" || bad "JOB_BG_WAIT validation (rc $RC)"
run JOB_BG_SETTLE=x
[ "$RC" = 1 ] && grep -q "JOB_BG_SETTLE=x is not a whole number" "$J/out" && ok "so is JOB_BG_SETTLE" || bad "JOB_BG_SETTLE validation (rc $RC)"

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
