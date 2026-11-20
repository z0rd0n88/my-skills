#!/usr/bin/env bash
# Structural checks for a runbook a teammate's Claude runs unattended.
#
# Layer one is structural: it checks that every command parses, every placeholder is
# defined, every command has an Expected, every consumed file is produced, every path exists
# on --ref, and every live probe runs. A second, weaker layer greps for
# the mechanical defects in references/runbook-rules.md (TTY-only output, hard-coded counts,
# missing --no-edit, missing --limit). Rule ids in the output point at that file.
#
# usage: bash check-runbook.sh <runbook.md> [options]
#   --repo <dir>        git checkout used for path and probe checks (default: cwd)
#   --ref <a,b>         refs a path may exist on, comma-separated: the top piece's branch first
#                       (bare names resolve on it), then any branch a pointer names (default: origin/HEAD)
#   --prefix <dir>      directory a bare `lib/x.dart`-style path is tried under when it is
#                       missing at the repo root (the runbook's "all paths under X" sentence)
#   --probes <file>     shell file of read-only commands, one per line, each must exit 0
#   --created <a,b>     paths the runbook itself creates (skipped by the path check)
#   --allow <A,B>       extra ALLCAPS tokens that are not placeholders
#   --template          skip the unfilled {{slot}} check (for the template file itself)
#   -h, --help          this text
# exit 0 = CHECK: PASS, 1 = CHECK: FAIL, 2 = usage

set -u

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; }

RUNBOOK=""; REPO="$PWD"; REF="origin/HEAD"; PREFIX=""; PROBES=""; CREATED=""; ALLOW=""; TEMPLATE=0
while [ $# -gt 0 ]; do
  case "$1" in --repo|--ref|--prefix|--probes|--created|--allow) [ $# -ge 2 ] || { echo "$1 needs a value" >&2; usage >&2; exit 2; } ;; esac
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --repo) REPO="$2"; shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --probes) PROBES="$2"; shift 2 ;;
    --created) CREATED="$2"; shift 2 ;;
    --allow) ALLOW="$2"; shift 2 ;;
    --template) TEMPLATE=1; shift ;;
    -*) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) if [ -z "$RUNBOOK" ]; then RUNBOOK="$1"; shift; else echo "unexpected argument: $1" >&2; exit 2; fi ;;
  esac
done
[ -n "$RUNBOOK" ] && [ -f "$RUNBOOK" ] || { echo "runbook file required" >&2; usage >&2; exit 2; }
[ -d "$REPO/.git" ] || git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git checkout: $REPO" >&2; exit 2; }

RUNBOOK_PATH="$RUNBOOK" REPO_DIR="$REPO" REF_NAME="$REF" PATH_PREFIX="$PREFIX" PROBES_FILE="$PROBES" \
CREATED_PATHS="$CREATED" ALLOW_TOKENS="$ALLOW" TEMPLATE_MODE="$TEMPLATE" python3 - <<'PY'
import os, re, subprocess, sys, tempfile

P = os.environ["RUNBOOK_PATH"]; REPO = os.environ["REPO_DIR"]; REF = os.environ["REF_NAME"]
PREFIX = os.environ["PATH_PREFIX"]; PROBES = os.environ["PROBES_FILE"]
PROBES = os.path.abspath(PROBES) if PROBES else ""
CREATED = {c for c in os.environ["CREATED_PATHS"].split(",") if c}
ALLOW = {a for a in os.environ["ALLOW_TOKENS"].split(",") if a}
text = open(P, encoding="utf-8").read()
lines = text.split("\n")
fail = False
def ok(m): print(f"PASS {m}")
def bad(m):
    global fail; fail = True; print(f"FAIL {m}")

# fenced blocks: (info, start_line_index, end_line_index, body)
blocks = []
i = 0
while i < len(lines):
    m = re.match(r"^```(\S*)", lines[i])
    if m:
        info = m.group(1); start = i; j = i + 1
        while j < len(lines) and not lines[j].startswith("```"): j += 1
        blocks.append((info, start, j, "\n".join(lines[i+1:j])))
        i = j + 1
    else:
        i += 1
bash_blocks = [b for b in blocks if b[0] == "bash"]
in_fence = set()
for _, s, e, _ in blocks:
    in_fence.update(range(s, e + 1))
prose = [l if n not in in_fence else "" for n, l in enumerate(lines)]

# 0. no unfilled {{slot}} (--template skips this) and every platform marker is closed (D8)
if os.environ["TEMPLATE_MODE"] != "1":
    slots = [n+1 for n, l in enumerate(lines) if re.search(r"(?<!\$)\{\{(?!-?\s*(?:[.$]|(?:range|if|with|define|template|block)\s+[.$\"(]|(?:else|end)\s*-?\}\}))", l)]   # a Go/gh template action is not a slot
    if slots: bad("unfilled {{slot}} at lines " + str(slots))
    else: ok("no unfilled {{slot}}")
depth = 0; opened = 0; unpaired = []   # a marker is a line of its own; a prose mention is not one
for n, l in enumerate(lines):
    if re.fullmatch(r"\s*<!-- platform: \S+ -->\s*", l):
        if depth: unpaired.append(n+1)
        depth += 1; opened += 1
    elif re.fullmatch(r"\s*<!-- /platform -->\s*", l):
        if not depth: unpaired.append(n+1)
        depth = max(depth - 1, 0)
if depth or unpaired: bad(f"platform marker opened inside another, closed before it opens, or never closed (D8) at lines {unpaired or ['end of file']}")
else: ok(f"platform markers paired ({opened})")
inline_markers = [n+1 for n, l in enumerate(prose) if re.search(r"<!-- /?platform", l) and not re.fullmatch(r"\s*<!-- (platform: \S+|/platform) -->\s*", l) and not re.search(r"`[^`]*<!-- /?platform[^`]*`", l)]
if inline_markers: bad(f"platform marker not on a line of its own (D8) at lines {inline_markers}")

# inline commands in prose (`git ...`, `gh ...`) get the same parse, placeholder and grep checks
# a bare name (`git commit`, `gh pr list`) is a mention in a sentence, not a command, and is skipped
inline = [("inline", n, n + 1, span) for n, l in enumerate(prose) for span in re.findall(r"`((?:git|gh|bash|node|flutter|xcrun) [^`]+)`", l)
          if not re.fullmatch(r"(?:gh [a-z-]+|git|bash|node|flutter|xcrun) [a-z][a-z-]*", span)]
cmd_blocks = bash_blocks + inline

# 1. every bash block parses (placeholders become words, <...> become a word)
tmp = tempfile.mkdtemp()
for k, (_, s, _, body) in enumerate(cmd_blocks):
    src = re.sub(r"<[A-Za-z.][^>\n]*>", "PLACEHOLDER", body)   # <...> slots; a redirect like </dev/null is left alone
    f = os.path.join(tmp, f"block{k}.sh"); open(f, "w").write(src + "\n")
    r = subprocess.run(["bash", "-n", f], capture_output=True, text=True)
    if r.returncode: bad(f"bash -n on the block at line {s+1}: {r.stderr.strip().splitlines()[-1] if r.stderr else 'parse error'}")
ok(f"bash -n on {len(bash_blocks)} bash blocks and {len(inline)} inline commands")

# 2. every bash block is followed by an Expected (D4); the launch line is the one exemption
missing = []
for _, s, e, body in bash_blocks:
    if "claude --dangerously-skip-permissions" in body: continue
    nxt = next((l for l in lines[e+1:e+4] if l.strip()), "")
    if not re.match(r"\s*[*_]*Expected", nxt): missing.append(s + 1)
if missing: bad(f"bash block without an Expected line right after it (D4) at lines {missing}")
else: ok("every bash block is followed by an Expected block")

# 3. placeholders used in commands are defined in the substitution sentence (D3)
subst = next((n for n, l in enumerate(lines) if "Substitute before running:" in l), None)
if subst is None: bad("no 'Substitute before running:' sentence (D3)"); defs = ""
else:
    defs = "\n".join(lines[subst:subst+6])
    if "<...>" not in defs: bad("the substitution sentence does not say to fill every <...> field (D3)")
    else: ok("substitution sentence names the <...> fields")
SHELL_WORDS = {"PASS","FAIL","GATE","CHECK","PUT","POST","GET","DELETE","PATCH","SHA","URL","HEAD","FETCH_HEAD","MERGE_HEAD",
    "ORIG_HEAD","CRITICAL","HIGH","MEDIUM","LOW","ID","TZ","PATH","HOME","EOF","OK","UNKNOWN","MERGEABLE","CONFLICTING",
    "APPROVED","MERGED","OPEN","CLOSED","CI","API","REST","JSON","YAML","TODO","FIXME","IFS","PWD","TTY","UDID","ERROR",
    "BASH_DEFAULT_TIMEOUT_MS","BASH_MAX_TIMEOUT_MS","CLAUDE_PLUGIN_ROOT","GIT_EDITOR","GH_TOKEN","PR_NUMBER"}
allowed = SHELL_WORDS | ALLOW
used = set()
for _, _, _, body in cmd_blocks:
    body = re.sub(r"<[^>\n]*>", " ", body)
    body = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", " ", body)   # $VAR is a shell variable
    body = re.sub(r"'[^'\n]*'", " ", body)                        # single-quoted text is literal
    body = re.sub(r"^[A-Z_]+=[^ ]*", lambda m: " ", body, flags=re.M)  # VAR=value assignments
    for tok in re.findall(r"(?<![\w./-])[A-Z][A-Z_]+(?![\w./-])", body):
        if tok not in allowed: used.add(tok)
undefined = sorted(t for t in used if f"`{t}`" not in defs)
for t in sorted(used - set(undefined)): ok(f"placeholder {t} defined")
if undefined: bad(f"placeholders used in a command but not in the substitution sentence (D3): {undefined}")

# 4. every file handed to --body-file (other than stdin) is produced somewhere in the runbook
for f in sorted(set(re.findall(r"--body-file\s+([^\s`'\"]+)", text))):
    if f == "-": continue
    n = len(re.findall(re.escape(f), text))
    if n >= 2: ok(f"{f} has a producer and a consumer ({n} mentions)")
    else: bad(f"{f} is consumed by --body-file but never written (1 mention, D11)")

# 5. every backticked relative path with an extension exists at REF (D5), trying PREFIX when given
def exists(path):
    return any(subprocess.run(["git", "-C", REPO, "cat-file", "-e", f"{r}:{path}"], capture_output=True).returncode == 0
               for r in REF.split(","))
paths = sorted(set(re.findall(r"`((?!https?:)(?!/)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]+)`", text)))
checked = 0
for p in paths:
    if p in CREATED or p.startswith(("tmp/", "build/")): continue
    checked += 1
    if exists(p): continue
    if PREFIX and exists(f"{PREFIX.rstrip('/')}/{p}"): continue
    bad(f"path not found on {REF}: {p} (D5)")
ok(f"{checked} backticked paths checked against {REF}")
bare = sorted(set(re.findall(r"`([a-z_][a-z0-9_]*\.[a-z]+)`", text)))
if bare and PREFIX:
    tree = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "--name-only", REF.split(",")[0], "--", PREFIX], capture_output=True, text=True).stdout.split()
    for b in bare:
        n = sum(1 for t in tree if t.endswith("/" + b))
        if n == 1: ok(f"bare name {b} resolves to one file under {PREFIX}")
        else: bad(f"bare name {b} resolves to {n} files under {PREFIX} (D5)")

# 6. live probes
if PROBES:
    r = subprocess.run(["bash", "-eo", "pipefail", PROBES], cwd=REPO, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    if r.returncode == 0: ok(f"probes in {os.path.basename(PROBES)} ran clean")
    else: bad(f"probes in {os.path.basename(PROBES)} exited {r.returncode}: {' | '.join(tail)}")

# 7. mechanical rules (the weaker layer)
def grep_prose(pattern, msg, flags=0, skip=()):
    hits = [n+1 for n, l in enumerate(prose) if n not in skip and re.search(pattern, l, flags)]
    if hits: bad(f"{msg} at lines {hits}")
    else: ok(msg.split(" (")[0] + ": none")
def grep_bash(pattern, msg, flags=0):
    hits = []
    for _, s, e, body in cmd_blocks:
        for k, l in enumerate(body.split("\n")):
            if re.search(pattern, l, flags): hits.append(e - body.count("\n") + k)   # first body line, fence or inline span
    if hits: bad(f"{msg} at lines {hits}")
    else: ok(msg.split(" (")[0] + ": none")
def require(pattern, msg):
    if re.search(pattern, text): ok(msg)
    else: bad(msg + " (missing)")

grep_prose(r"[—–]", "em or en dash (D10)")
ntj = next((n for n, l in enumerate(lines) if re.match(r"#+ Not this job", l)), len(lines))
not_this_job = range(ntj, next((n for n in range(ntj + 1, len(lines)) if lines[n].startswith("#")), len(lines)))
grep_prose(r"\b(from|via|in|on|open|use|using|through) (the |a )?(PR's |GitHub's |GitHub )?(web (page|ui)|browser)\b|(?<![\w-])click\b","web-page step an unattended run cannot do (A11)", re.I, skip=not_this_job)
grep_prose(r"\b(moved|behind|ahead)( by)? [0-9]+ commits?\b|\b[0-9]+ commits? (ahead|behind|since)\b|\b([2-9]|[0-9]{2,}) (new )?commits?\b(?! ago)|\b[0-9]{2,} (tests? )?(pass|passed|passing)\b", "hard-coded count that goes stale (D1)")
grep_prose(r"✓ Merged|Merged pull request|Ready for review|Approved pull request|Deleted (local|remote) branch", "TTY-only gh output named in prose (A3)")
grep_bash(r"\bgh pr list\b(?!.*--limit)", "gh pr list without --limit (A8)")
grep_bash(r"^(?!.*GIT_EDITOR=).*(\bgit commit(?![-\w])(?!.*(--no-edit|-[a-z]*m[ \"']|-F |--file|--message))|\bgit merge(?![-\w])(?!.*(--no-edit|-[a-z]*m[ \"']|-F |--file|--message|--abort|--squash|--ff-only))|\bgit revert(?![-\w])(?!.*(--no-edit|--abort|--no-commit|-n )))", "git commit/merge without --no-edit or a message, or git revert without --no-edit (A6)")
grep_bash(r"\bgrep -c[a-zA-Z]*\b(?!.*\|\| true)", "grep -c without || true (A7)")
def jq_backslash_outside_string(prog):
    # jq allows a backslash only inside a string literal; a \( interpolation is code again
    st = [0]   # top: -1 inside a string, otherwise the open-paren count of this code level
    i = 0
    while i < len(prog):
        c = prog[i]
        if st[-1] < 0:
            if prog.startswith("\\(", i): st.append(0); i += 2; continue
            if c == "\\": i += 2; continue
            if c == '"': st.pop()
        elif c == "\\": return True
        elif c == '"': st.append(-1)
        elif c == "(": st[-1] += 1
        elif c == ")":
            if st[-1] == 0 and len(st) > 1: st.pop()
            else: st[-1] -= 1
        i += 1
    return False
jq_hits = [e - body.count("\n") + k for _, _, e, body in cmd_blocks for k, l in enumerate(body.split("\n"))
           if any(jq_backslash_outside_string(p) for p in re.findall(r"--jq '([^']*)'", l))]
if jq_hits: bad(f"backslash-escaped quote outside a jq string, which jq rejects (A3) at lines {jq_hits}")
else: ok("backslash-escaped quote outside a jq string: none")
require(r"gh api user --jq \.login", "author-is-not-approver check present (C6)")
require(r"--jq \.permissions\.push", "push-access probe present (C6)")
require(r"BASH_DEFAULT_TIMEOUT_MS=\d+ BASH_MAX_TIMEOUT_MS=\d+ claude --dangerously-skip-permissions", "launch line with both timeout variables (A1)")
require(r"git fetch --prune origin", "git fetch --prune in the paste prompt (A9)")
require(r"merge-base --is-ancestor", "base-unchanged proof before the merge (C4)")
require(r"--diff-filter=U", "conflict rule decided by the conflicted files (C5)")
require(r"\.stack == null", "GitHub-stack probe present (C9)")
require(r"mergeCommit", "merge decided by a mergeCommit probe, not by output (A3)")
require(r"TaskStop", "timed-out call bounded with TaskStop (A2)")
require(r"<!-- platform: ", "platform markers present (D8)")

import shutil; shutil.rmtree(tmp, ignore_errors=True)
print("----")
print("CHECK: FAIL" if fail else "CHECK: PASS")
sys.exit(1 if fail else 0)
PY
