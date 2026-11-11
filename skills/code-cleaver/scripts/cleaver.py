#!/usr/bin/env python3
"""Deterministic helpers for the code-cleaver skill. Stdlib only.

Every number the audit plan states comes from one of these subcommands, so the
plan can be re-measured by re-running them. All paths are from the repo root.

    cleaver.py measure  [--root DIR] [--only PATH] [--budget N] [--json FILE]
    cleaver.py overlap  --units FILE [--root DIR]
    cleaver.py secrets  [--root DIR]
    cleaver.py stamp    REPORT.md OUT.md
    cleaver.py verify   --worktree DIR --plan REL --audit-dir REL
                        [--stage plan|final] [--only PATH] [--frozen FILE]
    cleaver.py selftest
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

CODE_EXT = {
    ".dart", ".kt", ".kts", ".java", ".swift", ".m", ".mm", ".py", ".rb", ".go", ".rs",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".c", ".h", ".cc",
    ".cpp", ".hpp", ".cs", ".php", ".scala", ".ex", ".exs", ".sol", ".sql", ".sh", ".lua",
}
# Build files are platform, not product code: they go to the platform slice by file count.
BUILD_RE = re.compile(r"(^|/)((build|settings)\.gradle(\.kts)?|Package\.swift)$|^setup\.py$")
TEST_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|integration_test|androidTest|testFixtures|e2e|testdata"
    r"|fixtures)(/|$)"
    r"|(_test|\.test|\.spec|_spec)\.[a-z]+$|(^|/)(test_[^/]+|conftest)\.py$"
    r"|Tests?\.(kt|java|swift|cs)$"
)
GENERATED_RE = re.compile(
    r"(^|/)(vendor|third_party|node_modules|generated|\.dart_tool|Pods)(/|$)"
    r"|\.(g|freezed|gr|mocks)\.dart$|\.pb\.(go|dart)$|_pb2(_grpc)?\.py$|\.min\.(js|css)$"
    r"|(^|/)(gradlew|mvnw)$"
)
SECRET_PATTERNS = {
    "AWS access key id": ("-E", r"AKIA[0-9A-Z]{16}"),
    "PEM private key": ("-E", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": ("-E", r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "Slack token": ("-E", r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "Stripe live key": ("-E", r"[sr]k_live_[A-Za-z0-9]{16,}"),
    "Google API key": ("-E", r"AIza[0-9A-Za-z_-]{35}"),
    "JWT": ("-E", r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "Telegram bot token": ("-E", r"[0-9]{8,10}:[A-Za-z0-9_-]{35}"),
    "hard-coded credential assignment": (
        "-iE", r"(api[_-]?key|secret|(auth|access|bearer|bot|api|refresh)[_-]?token|passw(or)?d|private[_-]?key|mnemonic)[a-z_]*[\"']?"
               r"([[:space:]]*:[[:space:]]*|[^=]{0,20}=[[:space:]]*)[\"'][A-Za-z0-9_/+=:.-]{20,}[\"']"),
    "64-hex key assignment": (
        "-iE", r"(key|secret|seed)[a-z_]*[\"']?[^=:]{0,20}[:=][[:space:]]*[\"']?(0x)?[0-9a-f]{64}"),
}
KEY_FILE_RE = re.compile(
    r"(^|/)(\.env(\..+)?|id_(rsa|ed25519|ecdsa)|google-services\.json|GoogleService-Info\.plist)$"
    r"|\.(pem|p12|pfx|jks|keystore|key)$"
)
PLACEHOLDER_RE = re.compile(r"\.(example|sample|template|dist)$")
MAX_FILES_DEFAULT = 50  # the review tool's per-directory cap before --max-files is needed
PRELUDE_CAP = 16 * 1024  # the review tool's --prompt-prelude cap
SLOT_RE = re.compile(r"<<[A-Za-z\"][\s\S]{0,1200}?>>")
ROW_RE = re.compile(r"^\|\s*([A-Z]{1,3}\d+)\s*\|")


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def toplevel(root):
    r = git(root, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        sys.exit(f"cleaver: not a git repository: {root}")
    return r.stdout.strip()


def tracked(root):
    out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


def line_count(path):
    try:
        with open(path, "rb") as f:
            return f.read().count(b"\n")
    except OSError:
        return 0


def has_shebang(path):
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def classify(path, root):
    """Return 'code', 'test', 'generated' or 'other' for one tracked path."""
    ext = os.path.splitext(path)[1].lower()
    is_code = ext in CODE_EXT or (not ext and has_shebang(os.path.join(root, path)))
    if not is_code or BUILD_RE.search(path):
        return "other"
    if GENERATED_RE.search(path):
        return "generated"
    if TEST_RE.search(path):
        return "test"
    return "code"


def scan(root, only=None):
    """Classify every tracked file. Returns (code {path: lines}, tests {path: lines}, all paths, totals)."""
    pre = (only.strip("/") + "/") if only else ""
    code, tests, everything = {}, {}, []
    totals = {"code": [0, 0], "test": [0, 0], "generated": [0, 0], "other": [0, 0]}
    for p in tracked(root):
        if pre and not p.startswith(pre):
            continue
        everything.append(p)
        kind = classify(p, root)
        n = line_count(os.path.join(root, p)) if kind != "other" else 0
        totals[kind][0] += 1
        totals[kind][1] += n
        if kind == "code":
            code[p] = n
        elif kind == "test":
            tests[p] = n
    return code, tests, everything, totals


def ext_of(p):
    return os.path.splitext(p)[1].lower() or "(no ext)"


def measure(root, budget, only=None):
    """Cut the code tree into units: the shallowest directories whose code fits the budget."""
    root = toplevel(root)
    files, tests, everything, totals = scan(root, only)
    auto = budget <= 0
    if auto:
        budget = min(7000, max(1500, totals["code"][1] // 8))
    by_ext = {}
    for p, n in files.items():
        e = by_ext.setdefault(ext_of(p), [0, 0])
        e[0] += 1
        e[1] += n

    def under(d, pool):
        pre = d + "/" if d else ""
        return {p: n for p, n in pool.items() if p.startswith(pre)}

    units = []

    def split(d):
        sub = under(d, files)
        if not sub:
            return
        pre = d + "/" if d else ""
        children = sorted({p[len(pre):].split("/")[0] for p in sub if "/" in p[len(pre):]})
        if sum(sub.values()) <= budget or not children:
            exts = {}
            for p, n in sub.items():
                exts[ext_of(p)] = exts.get(ext_of(p), 0) + n
            units.append({"path": d or ".", "kind": "dir", "files": len(sub),
                          "lines": sum(sub.values()), "ext": max(exts, key=exts.get),
                          "tracked": sum(1 for p in everything if p.startswith(pre))})
            return
        loose = {p: n for p, n in sub.items() if "/" not in p[len(pre):]}
        if loose:
            units.append({"path": d or ".", "kind": "loose", "files": len(loose),
                          "lines": sum(loose.values()), "names": sorted(loose),
                          "ext": ext_of(sorted(loose)[0]), "tracked": len(loose)})
        for c in children:
            split(pre + c)

    split(only.strip("/") if only else "")
    for u in units:
        u["over_file_cap"] = u["kind"] == "dir" and u["tracked"] > MAX_FILES_DEFAULT
        u["over_budget"] = u["lines"] > budget

    trees = []
    for top in sorted({p.split("/")[0] for p in files if "/" in p}):
        sub = under(top, files)
        names, last = sorted(sub), ""
        for i in range(0, len(names), 400):
            last = max(last, git(root, "log", "-1", "--format=%cs", "--", *names[i:i + 400]).stdout.strip())
        trees.append({"path": top, "files": len(sub), "lines": sum(sub.values()),
                      "last_code_change": last or "unknown"})
    test_roots = {}
    for p in tests:
        m = TEST_RE.search(p)
        key = p[:m.end()].rstrip("/") if m and m.group(2) else os.path.dirname(p) or "."
        test_roots[key] = test_roots.get(key, 0) + 1
    other = {}
    for p in everything:
        if p not in files and p not in tests and classify(p, root) == "other":
            other[ext_of(p)] = other.get(ext_of(p), 0) + 1
    return {"budget": budget, "budget_auto": auto, "units": units, "totals": totals,
            "by_ext": by_ext, "trees": trees, "test_roots": test_roots, "other_by_ext": other}


def print_measure(m):
    t = m["totals"]
    print(f"code: {t['code'][0]} files, {t['code'][1]} lines (tests, generated and build files excluded)")
    print(f"tests: {t['test'][0]} files, {t['test'][1]} lines")
    print(f"generated or vendored: {t['generated'][0]} files, {t['generated'][1]} lines")
    print(f"other tracked files (docs, config, build files, assets): {t['other'][0]}")
    exts = sorted(m["by_ext"].items(), key=lambda kv: -kv[1][1])
    print("code by extension: " + ", ".join(f"{e} {v[0]} files {v[1]} lines" for e, v in exts))
    top_other = sorted(m["other_by_ext"].items(), key=lambda kv: -kv[1])[:10]
    print("other by extension: " + ", ".join(f"{e} {n}" for e, n in top_other))
    roots = sorted(m["test_roots"].items(), key=lambda kv: -kv[1])[:12]
    print("test files by location: " + (", ".join(f"{d} {n}" for d, n in roots) or "none"))
    print("\ntop-level code trees:\n")
    print("| Tree | Code files | Code lines | Last code change |")
    print("|---|---|---|---|")
    for tr in m["trees"]:
        print(f"| `{tr['path']}` | {tr['files']} | {tr['lines']} | {tr['last_code_change']} |")
    how = "auto: an eighth of the code, between 1,500 and 7,000" if m["budget_auto"] else "given"
    print(f"\nunits at a budget of {m['budget']} lines ({how}): {len(m['units'])}\n")
    print("| Unit | Kind | Code files | Code lines | Tracked files | Main ext | Note |")
    print("|---|---|---|---|---|---|---|")
    for u in m["units"]:
        note = []
        if u["over_file_cap"]:
            note.append(f"needs --max-files {u['tracked']}")
        if u["over_budget"]:
            note.append("over budget, no subdirectory to split on")
        if u["kind"] == "loose":
            note.append("files directly in this directory: " + ", ".join(
                os.path.basename(n) for n in u["names"][:8]) + (" ..." if u["files"] > 8 else ""))
        print(f"| `{u['path']}` | {u['kind']} | {u['files']} | {u['lines']} | {u['tracked']} | "
              f"{u['ext']} | {'; '.join(note)} |")


def overlap(root, units):
    """Map each unit to the open PRs that change files inside it."""
    root = toplevel(root)
    r = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--limit", "200", "--json",
         "number,isDraft,headRefName,files"], capture_output=True, text=True, cwd=root)
    if r.returncode != 0:
        said = (r.stderr.strip().splitlines() or ["no output"])[0]
        print(f"overlap: UNKNOWN. gh pr list failed, and gh said: {said}")
        print("Write `unknown` in every In flight cell. Do not substitute a guess.")
        return 0
    prs = json.loads(r.stdout or "[]")
    print(f"open PRs: {len(prs)}")
    capped = [p["number"] for p in prs if len(p.get("files") or []) >= 100]
    if capped:
        print("file list may be cut at 100 for: " + ", ".join(f"#{n}" for n in capped)
              + " (check these with gh pr diff <n> --name-only)")
    print("\n| Unit | Open PRs (files changed inside the unit) |")
    print("|---|---|")
    hit_any = set()
    for u in units:
        pre = "" if u["path"] == "." else u["path"] + "/"
        names = set(u.get("names") or [])
        hits = []
        for p in sorted(prs, key=lambda p: p["number"]):
            paths = [f["path"] for f in p.get("files") or []]
            n = sum(1 for f in paths if (f in names if u["kind"] == "loose" else f.startswith(pre)))
            if n:
                hit_any.add(p["number"])
                hits.append(f"#{p['number']}{' draft' if p.get('isDraft') else ''} ({n})")
        print(f"| `{u['path']}`{' (loose)' if u['kind'] == 'loose' else ''} | "
              f"{', '.join(hits) or 'none'} |")
    rest = [p for p in sorted(prs, key=lambda p: p["number"]) if p["number"] not in hit_any]
    if rest:
        print("\nopen PRs that touch no code unit (docs, config, build, CI):")
        for p in rest:
            paths = [f["path"] for f in p.get("files") or []]
            print(f"- #{p['number']}: " + ", ".join(paths[:5]) + (" ..." if len(paths) > 5 else ""))
    return 0


def secrets(root):
    """Name where a secret shape matches, as file:line and kind. Never prints a matched value."""
    root = toplevel(root)
    found = False
    for kind, (flag, pat) in SECRET_PATTERNS.items():
        r = git(root, "grep", "-n", "-I", flag, "-e", pat)
        hits = [":".join(l.split(":", 2)[:2]) for l in r.stdout.splitlines() if l.count(":") >= 2]
        hits = [h + (" (test file)" if TEST_RE.search(h.rsplit(":", 1)[0]) else "") for h in hits]
        hits.sort(key=lambda h: h.endswith("(test file)"))
        for h in hits[:20]:
            found = True
            print(f"{kind}: {h}")
        if len(hits) > 20:
            print(f"{kind}: and {len(hits) - 20} more")
    for p in tracked(root):
        if KEY_FILE_RE.search(p) and not PLACEHOLDER_RE.search(p):
            found = True
            print(f"tracked key-shaped file: {p}")
    print("patterns checked: " + ", ".join(SECRET_PATTERNS) + "; plus key-shaped file names "
          "(names ending .example, .sample, .template or .dist are skipped)")
    print("secret scan: " + ("LEADS FOUND. Read each line yourself to rule out a test value or "
                             "placeholder; record file:line and kind only" if found else "nothing matched"))
    print("this is a short pattern list, not a secret scanner")
    return 0


def stamp(report, out):
    """Give every finding in a multi-agent review report a stable id (F1, F2, ...)."""
    lines = open(report, encoding="utf-8").read().split("\n")
    blocks, index, n, section, cur = [], [], 0, None, None
    for line in lines:
        if line.startswith("## "):
            title = line[3:].strip().lower()
            section = ("critical" if title.startswith("critical") else
                       "high" if title.startswith("high") else
                       "table" if title.startswith("medium") else None)
            cur = None
            continue
        if section in ("critical", "high"):
            if line.startswith("### "):
                n += 1
                cur = f"F{n}"
                sev = section.upper()
                blocks.append(f"\n### FINDING {cur} (reported {sev}): {line[4:].strip()}")
                index.append(f"{cur} {sev} {line[4:].strip()}")
            elif cur:
                blocks.append(line)
        elif section == "table":
            m = re.match(r"^\|\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*\|", line)
            if m:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                n += 1
                title = cells[1] if len(cells) > 1 else ""
                blocks.append(
                    f"\n### FINDING F{n} (reported {m.group(1)}): {title}\n"
                    f"- Location: {cells[2] if len(cells) > 2 else ''}\n"
                    f"- Raised by: {cells[3] if len(cells) > 3 else ''}\n"
                    f"- Description: {' | '.join(cells[4:])}")
                index.append(f"F{n} {m.group(1)} {title}")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Findings from {os.path.basename(report)}, with ids\n" + "\n".join(blocks) + "\n")
    print(f"{n} findings stamped -> {out}")
    print("\n".join(index))
    return 0 if n else 1


def section_without(text, heading):
    """Return text with the `## heading` section removed."""
    out, skip = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            skip = line[3:].strip().lower().startswith(heading.lower())
        if not skip:
            out.append(line)
    return "\n".join(out)


def slice_rows(text):
    """Parse slice-table rows: id, backticked paths in the Paths cell, and the Code lines cell."""
    rows, lines_col = [], None
    for line in text.split("\n"):
        if re.match(r"^\|\s*ID\s*\|", line):
            head = [c.strip().lower() for c in line.strip().strip("|").split("|")]
            lines_col = next((i for i, c in enumerate(head) if c in ("code lines", "lines")), None)
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        paths = [p.rstrip("/") for p in re.findall(r"`([^`]+)`", cells[2] if len(cells) > 2 else "")
                 if not re.search(r"[*{<>\s]", p)]
        cell = cells[lines_col].replace(",", "") if lines_col is not None and len(cells) > lines_col else ""
        rows.append({"id": m.group(1), "paths": paths, "lines": int(cell) if cell.isdigit() else None})
    return rows


def verify(worktree, plan, audit_dir, frozen, stage="plan", only=None):
    """Check the plan after an edit pass. A correct plan passes; exit 1 on any failure."""
    fail = False

    def report(ok, name, detail=""):
        nonlocal fail
        fail = fail or not ok
        print(f"{'PASS' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")

    plan_path = os.path.join(worktree, plan)
    if not os.path.isfile(plan_path):
        report(False, "plan", f"missing {plan_path}")
        print("VERIFY: FAIL")
        return 1
    text = open(plan_path, encoding="utf-8").read()

    audit_pre = audit_dir.rstrip("/") + "/"
    status = git(worktree, "status", "--porcelain", "--untracked-files=all").stdout
    changed = [l[3:].strip('"') for l in status.splitlines()]
    stray = [c for c in changed if c != plan and not c.startswith(audit_pre)]
    report(not stray, "scope", "only the plan and the audit folder differ" if not stray
           else "unexpected changes: " + ", ".join(stray[:10]))

    base = os.path.dirname(plan_path)
    bad = []
    for t in re.findall(r"\]\(([^)]+)\)", text):
        t = t.split(' "')[0].strip()
        if re.match(r"^[a-z]+://|^#|^mailto:|^<<", t):
            continue
        if not os.path.exists(os.path.join(base, t.split("#")[0])):
            bad.append(t)
    report(not bad, "links", "every relative link resolves" if not bad else ", ".join(bad))

    rows = [r for r in slice_rows(text) if r["paths"]]
    missing = [f"{r['id']}: {p}" for r in rows for p in r["paths"]
               if not os.path.exists(os.path.join(worktree, p))]
    report(bool(rows) and not missing, "slice paths",
           f"{len(rows)} rows with paths, every path exists" if rows and not missing
           else ("no slice row names a path" if not rows else "missing " + ", ".join(missing[:10])))

    code, _, _, totals = scan(worktree, only)
    owners = {p: [] for p in code}
    for r in rows:
        for sp in r["paths"]:
            for p in code:
                if sp == "." or p == sp or p.startswith(sp + "/"):
                    if r["id"] not in owners[p]:
                        owners[p].append(r["id"])
    orphan = sorted(p for p, o in owners.items() if not o)
    doubled = sorted(p for p, o in owners.items() if len(o) > 1)
    detail = f"all {len(code)} code files ({totals['code'][1]} lines) sit in exactly one row"
    if orphan:
        dirs = sorted({os.path.dirname(p) or "." for p in orphan})
        detail = f"{len(orphan)} code files in no row, under: " + ", ".join(dirs[:8])
    elif doubled:
        detail = f"{len(doubled)} code files in two rows, e.g. " + ", ".join(
            f"{p} ({'+'.join(owners[p])})" for p in doubled[:5])
    report(not orphan and not doubled, "coverage", detail)
    wrong = []
    for r in rows:
        got = sum(n for p, n in code.items() if r["id"] in owners[p])
        if r["lines"] is not None and r["lines"] != got:
            wrong.append(f"{r['id']} says {r['lines']}, measured {got}")
    report(not wrong, "slice sizes", "every Code lines cell matches the tree" if not wrong
           else "; ".join(wrong[:8]))

    plan_body = section_without(text, "Tracer result") if stage == "plan" else text
    left = SLOT_RE.findall(plan_body)
    report(not left, "plan slots", "none left" if not left else f"{len(left)} unfilled, first: {left[0][:60]}")

    adir = os.path.join(worktree, audit_dir)
    shared = os.path.join(adir, "checklist.md")
    if not os.path.isfile(shared):
        report(False, "checklist", f"missing {shared}")
    else:
        left = SLOT_RE.findall(section_without(open(shared, encoding="utf-8").read(), "This run"))
        report(not left, "checklist slots", "none left outside This run" if not left
               else f"{len(left)} unfilled, first: {left[0][:60]}")
        for name in sorted(os.listdir(adir)):
            if not name.endswith("checklist.md"):
                continue
            path = os.path.join(adir, name)
            size = os.path.getsize(path)
            ok = size <= PRELUDE_CAP
            if name != "checklist.md" and SLOT_RE.search(open(path, encoding="utf-8").read()):
                ok = False
                size = f"{size} bytes, This run not filled in"
            report(ok, f"{name} size", f"{size}, cap {PRELUDE_CAP} bytes")

    if frozen:
        drift = []
        for line in open(frozen, encoding="utf-8").read().splitlines():
            if not line.strip():
                continue
            digest, name = line.split(None, 1)
            name = name.lstrip("*").strip()
            try:
                actual = hashlib.sha256(open(name, "rb").read()).hexdigest()
            except OSError:
                actual = "missing"
            if actual != digest:
                drift.append(name)
        report(not drift, "frozen files", "unchanged" if not drift else "changed: " + ", ".join(drift))

    print(f"plan lines: {text.count(chr(10))}")
    print("VERIFY: " + ("FAIL" if fail else "PASS"))
    return 1 if fail else 0


def selftest():
    with tempfile.TemporaryDirectory() as d:
        d = os.path.realpath(d)

        def w(rel, body):
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(body)
        run = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, check=True)
        run("init", "-q")
        w("src/main.py", "x\n" * 5)
        w("src/pay/a.py", "x\n" * 30)
        w("src/pay/b.py", "x\n" * 30)
        w("src/pay/logo.png", "binary")
        w("src/ui/c.py", "x\n" * 10)
        w("src/ui/c_test.py", "x\n" * 99)
        w("src/testFixtures/f.kt", "x\n" * 3)
        w("tests/test_a.py", "x\n" * 7)
        w("vendor/lib.py", "x\n" * 500)
        w("build.gradle.kts", "x\n" * 40)
        w("bin/run", "#!/bin/sh\necho\n")
        w(".env.example", "KEY=changeme\n")
        w("README.md", "hi\n")
        run("add", "-A")
        m = measure(d, 50)
        got = {(u["path"], u["kind"]): (u["files"], u["lines"], u["tracked"]) for u in m["units"]}
        assert got == {("bin", "dir"): (1, 2, 1), ("src", "loose"): (1, 5, 1),
                       ("src/pay", "dir"): (2, 60, 3), ("src/ui", "dir"): (1, 10, 2)}, got
        assert m["totals"]["code"] == [5, 77] and m["totals"]["test"] == [3, 109], m["totals"]
        assert m["totals"]["generated"] == [1, 500], m["totals"]
        assert [u["path"] for u in m["units"] if u["over_budget"]] == ["src/pay"]
        assert measure(d, 0)["budget"] == 1500
        assert [u["path"] for u in measure(d, 50, only="src/pay")["units"]] == ["src/pay"]

        w("r.md", "# R\n## Critical Findings\n### Leak\n- a\n## High Findings\n### Bug\n- b\n"
                  "## Medium and Low Findings\n| Severity | Title | Location | Reviewer(s) | D |\n"
                  "|---|---|---|---|---|\n| MEDIUM | Slow | x:1 | CR | d |\n| LOW | Typo | y:2 | CR | e |\n"
                  "## Coverage Report\n### not a finding\n")
        assert stamp(os.path.join(d, "r.md"), os.path.join(d, "f.md")) == 0
        out = open(os.path.join(d, "f.md")).read()
        assert out.count("### FINDING") == 4 and "F1 (reported CRITICAL): Leak" in out, out
        assert "F4 (reported LOW): Typo" in out and "not a finding" not in out
        os.remove(os.path.join(d, "r.md"))
        os.remove(os.path.join(d, "f.md"))
        run("commit", "-q", "-m", "x", "--no-verify")

        good = ("[c](audit/checklist.md)\n| ID | Slice | Paths | Code files | Code lines |\n"
                "|---|---|---|---|---|\n| S0 | Baseline | whole repo | | |\n"
                "| A1 | Pay | `src/pay` | 2 | 60 |\n| A2 | UI and entry | `src/ui`, `src/main.py` | 2 | 15 |\n"
                "| X1 | Left out: launcher | `bin` | 1 | 2 |\n## Tracer result\n<<filled by the tracer>>\n")
        w("docs/reviews/plan.md", good)
        w("docs/reviews/audit/checklist.md", "## This run\n- Slice: <<id>>\n## The code\nlenses\n")
        args = (d, "docs/reviews/plan.md", "docs/reviews/audit", None)
        assert verify(*args) == 0
        assert verify(*args, stage="final") == 1          # tracer slot still open
        w("docs/reviews/plan.md", good.replace("| X1 | Left out: launcher | `bin` | 1 | 2 |\n", ""))
        assert verify(*args) == 1                         # bin/run sits in no row
        w("docs/reviews/plan.md", good.replace("`src/pay` | 2 | 60", "`src` | 2 | 60"))
        assert verify(*args) == 1                         # src overlaps A2
        w("docs/reviews/plan.md", good.replace("| 2 | 60 |", "| 2 | 61 |"))
        assert verify(*args) == 1                         # wrong size
        w("docs/reviews/plan.md", good + "<<unfilled slot>>\n[x](a b.md)\n")
        assert verify(*args) == 1                         # slot left, broken link with a space
        w("docs/reviews/plan.md", good)
        w("docs/reviews/audit/A1-checklist.md", "## This run\n- Slice: <<id>>\n")
        assert verify(*args) == 1                         # per-slice copy not filled in
        os.remove(os.path.join(d, "docs/reviews/audit/A1-checklist.md"))
        w("docs/reviews/audit/checklist.md", "## The code\n- <<One of: \"<n> tests fail\" or "
          + "long " * 120 + "(<reason>)>>\n")
        assert verify(*args) == 1                         # long slot with inner angle brackets
        w("docs/reviews/audit/checklist.md", "## This run\n- Slice: <<id>>\n## The code\nlenses\n")
        assert verify(*args) == 0
        w("src/main.py", "edited\n")
        assert verify(*args) == 1                         # tracked file changed
    print("selftest: PASS")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("measure")
    s.add_argument("--root", default=".")
    s.add_argument("--only", help="limit to this path, from the repo root")
    s.add_argument("--budget", type=int, default=0, help="lines per unit; 0 picks one from the repo's size")
    s.add_argument("--json")
    s = sub.add_parser("overlap")
    s.add_argument("--root", default=".")
    s.add_argument("--units", required=True, help="JSON file written by measure --json")
    s = sub.add_parser("secrets")
    s.add_argument("--root", default=".")
    s = sub.add_parser("stamp")
    s.add_argument("report")
    s.add_argument("out")
    s = sub.add_parser("verify")
    s.add_argument("--worktree", required=True)
    s.add_argument("--plan", required=True, help="plan path, from the repo root")
    s.add_argument("--audit-dir", required=True, help="audit folder, from the repo root")
    s.add_argument("--stage", choices=["plan", "final"], default="plan",
                   help="plan: the Tracer result section may still hold slots; final: no slot anywhere")
    s.add_argument("--only", help="the same path limit given to measure, if any")
    s.add_argument("--frozen", help="sha256sum-format file of files that must not change")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "measure":
        m = measure(os.path.abspath(a.root), a.budget, a.only)
        if a.json:
            json.dump(m, open(a.json, "w"), indent=1)
        print_measure(m)
        return 0
    if a.cmd == "overlap":
        return overlap(os.path.abspath(a.root), json.load(open(a.units))["units"])
    if a.cmd == "secrets":
        return secrets(os.path.abspath(a.root))
    if a.cmd == "stamp":
        return stamp(a.report, a.out)
    if a.cmd == "verify":
        return verify(toplevel(os.path.abspath(a.worktree)), a.plan, a.audit_dir, a.frozen, a.stage, a.only)
    return selftest()


if __name__ == "__main__":
    sys.exit(main())
