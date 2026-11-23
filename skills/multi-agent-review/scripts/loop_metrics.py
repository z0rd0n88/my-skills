#!/usr/bin/env python3
"""Convergence scorer for multi-agent-review loop runs.

Answers one question: across a loop's rounds, is the review converging on the
code, or walking randomly over it?

Reads round artifacts a run already persists — no instrumentation, and it works
retroactively on historical runs, so a "before" baseline costs nothing.

    python3 loop_metrics.py <dir> [<dir> ...] [--json]

Accepted per directory (first shape that matches wins):
  - .claude/reviews/pr-<n>/round-<N>.json   (§10.3 step 0a checkpoints)
  - review-phase-<P>-iter-<N>.md            (baton-runner reports; grouped per phase)
  - round<N>*/*.md  |  round<N>-*.md        (layouts from the retired code-rinse-repeat)

The matcher is the point. Findings are matched across rounds by token-Jaccard
over (file basename + summary words), not by hashing the reviewer's exact
wording. The skill's own fingerprint (§10.3 step 2) hashes a normalized summary
string, which independent LLM reviewers never reproduce verbatim — measured
carry-forward under exact matching is ~0% even between rounds that are plainly
discussing the same defect. Anything built on exact-string identity reports a
random walk whether or not one is happening. Treat this matcher as the reference
implementation for what that fingerprint should be.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
# Jaccard over content tokens, set from the measured separation in selftest():
# genuine restatements of one defect score 0.42-0.53, distinct defects score
# 0.00-0.11 (0.11 being two unrelated findings in the SAME file, the hardest
# negative). 0.30 sits in that gap with margin on both sides. Re-run
# `--selftest` after changing it; it is a knob, not a law, but an unmeasured
# knob here silently turns every run into RANDOM_WALK.
MATCH_THRESHOLD = 0.30

STOPWORDS = frozenset(
    """
a an the and or but if then than that this these those is are was were be been being
of in on at to for from with without by as it its it's not no nor so such use uses used
can could may might must should would will shall do does did done has have had having
when where which who whom what why how all any both each few more most other some only
own same too very just also into over under again further once here there
""".split()
)

# Tokens that appear in nearly every review sentence and therefore carry no
# discriminating signal. Without this, two unrelated findings in the same file
# match on boilerplate alone.
BOILERPLATE = frozenset(
    """
finding issue bug code line lines file files fix fixes fixed change changes changed
review reviewer severity critical high medium low pr diff commit test tests
should must never always ensure add adds added remove removes removed
""".split()
)

FINDING_RE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{2,5}\s+|\|\s*)?"
    r"(?:\*\*)?\[?(CRITICAL|HIGH|MEDIUM|LOW)\b",
    re.IGNORECASE,
)
PATH_RE = re.compile(
    r"[\w./-]+\.(?:kt|kts|java|py|ts|tsx|js|jsx|go|rs|rb|sql|ya?ml|json|toml|md|sh)\b"
)
ROUND_JSON_RE = re.compile(r"round-(\d+)\.json$")
ITER_MD_RE = re.compile(r"review-phase-(\d+)-iter-(\d+)\.md$")
ROUND_MD_RE = re.compile(r"round-?(\d+)")


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return {
        w for w in words if len(w) > 2 and w not in STOPWORDS and w not in BOILERPLATE
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Finding:
    __slots__ = ("severity", "paths", "toks", "text")

    def __init__(self, severity: str, text: str):
        self.severity = severity.upper()
        self.text = text.strip()[:300]
        self.paths = {Path(p).name for p in PATH_RE.findall(text)}
        self.toks = tokens(text) | self.paths

    def matches(self, other: "Finding") -> bool:
        # A shared file is strong evidence but not sufficient; a shared file with
        # overlapping content words is the actual signal. With no path on either
        # side, fall back to content alone at a stricter bar.
        sim = jaccard(self.toks, other.toks)
        if self.paths and other.paths:
            if not (self.paths & other.paths):
                return False
            return sim >= MATCH_THRESHOLD
        return sim >= MATCH_THRESHOLD + 0.15


def parse_findings(text: str) -> list[Finding]:
    """Pull severity-tagged findings out of a report, one per anchor line.

    Continuation lines are folded into the preceding finding so that a
    file:line citation on the next line still counts as evidence for it.
    """
    out: list[Finding] = []
    buf: list[str] = []
    sev: str | None = None
    for raw in text.splitlines():
        m = FINDING_RE.match(raw)
        if m:
            if sev:
                out.append(Finding(sev, " ".join(buf)))
            sev, buf = m.group(1), [raw]
        elif sev is not None:
            if raw.strip():
                buf.append(raw)
            elif len(buf) > 1:
                out.append(Finding(sev, " ".join(buf)))
                sev, buf = None, []
    if sev:
        out.append(Finding(sev, " ".join(buf)))
    # A bare severity heading ("## HIGH") with no body is a section marker, not
    # a finding. Require some substance beyond the severity word itself.
    return [f for f in out if len(f.toks) >= 3]


def load_rounds(target: Path) -> list[tuple[str, list[Finding]]]:
    """Return [(round_label, findings)] ordered by round, for one run."""
    runs: list[tuple[str, list[Finding]]] = []

    jsons = sorted(
        (p for p in target.rglob("round-*.json") if ROUND_JSON_RE.search(p.name)),
        key=lambda p: int(ROUND_JSON_RE.search(p.name).group(1)),
    )
    if jsons:
        for p in jsons:
            try:
                blob = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  ! skipping {p.name}: {exc}", file=sys.stderr)
                continue
            body = blob.get("output") or blob.get("report") or json.dumps(blob)
            runs.append((f"r{blob.get('round', p.stem)}", parse_findings(body)))
        return runs

    iters = sorted(
        (
            p
            for p in target.rglob("review-phase-*-iter-*.md")
            if ITER_MD_RE.search(p.name)
        ),
        key=lambda p: tuple(int(g) for g in ITER_MD_RE.search(p.name).groups()),
    )
    if iters:
        # One "run" per phase; phases are independent targets, so never compare
        # across them.
        by_phase: dict[str, list[tuple[int, Path]]] = defaultdict(list)
        for p in iters:
            phase, it = ITER_MD_RE.search(p.name).groups()
            by_phase[phase].append((int(it), p))
        for phase in sorted(by_phase, key=int):
            for it, p in sorted(by_phase[phase]):
                runs.append(
                    (f"p{phase}.i{it}", parse_findings(p.read_text(encoding="utf-8")))
                )
        return runs

    mds = [
        p
        for p in target.rglob("*.md")
        if ROUND_MD_RE.search(p.name) or ROUND_MD_RE.search(p.parent.name)
    ]
    grouped: dict[int, list[Path]] = defaultdict(list)
    for p in mds:
        m = ROUND_MD_RE.search(p.name) or ROUND_MD_RE.search(p.parent.name)
        grouped[int(m.group(1))].append(p)
    for rnd in sorted(grouped):
        merged: list[Finding] = []
        for p in sorted(grouped[rnd]):
            merged.extend(parse_findings(p.read_text(encoding="utf-8")))
        runs.append((f"r{rnd}", merged))
    return runs


def score(runs: list[tuple[str, list[Finding]]]) -> dict:
    rows = []
    prev: list[Finding] | None = None
    for label, fs in runs:
        sev_counts = {s: sum(1 for f in fs if f.severity == s) for s in SEVERITIES}
        carried = 0
        # `is not None`, not truthiness: a round that found nothing is still a
        # round, and the next one's carry rate is a real 0% rather than absent.
        if prev is not None:
            for f in fs:
                if any(f.matches(g) for g in prev):
                    carried += 1
        rows.append(
            {
                "round": label,
                "total": len(fs),
                "blocking": sev_counts["CRITICAL"] + sev_counts["HIGH"],
                **{s.lower(): sev_counts[s] for s in SEVERITIES},
                "carried": carried if prev is not None else None,
                "carry_rate": round(carried / len(fs), 3)
                if prev is not None and fs
                else None,
                "evidence_rate": round(sum(1 for f in fs if f.paths) / len(fs), 3)
                if fs
                else None,
            }
        )
        prev = fs

    paired = [r for r in rows if r["carry_rate"] is not None]
    mean_carry = (
        round(sum(r["carry_rate"] for r in paired) / len(paired), 3) if paired else None
    )

    totals = [r["total"] for r in rows]
    blocking = [r["blocking"] for r in rows]
    trend = (totals[-1] - totals[0]) if len(totals) > 1 else 0
    block_trend = (blocking[-1] - blocking[0]) if len(blocking) > 1 else 0

    if mean_carry is None:
        verdict, why = "SINGLE_ROUND", "only one round — nothing to compare"
    elif mean_carry < 0.10:
        verdict, why = (
            "RANDOM_WALK",
            f"{mean_carry:.0%} of findings carry between rounds — rounds are not "
            "discussing the same code problems",
        )
    elif block_trend > 0:
        verdict, why = (
            "DIVERGING",
            f"blocking findings rose by {block_trend} across the run",
        )
    elif trend >= 0:
        verdict, why = "FLAT", "findings are carrying forward but total is not falling"
    else:
        verdict, why = "CONVERGING", f"carry {mean_carry:.0%}, total fell by {-trend}"

    return {
        "rounds": rows,
        "mean_carry_rate": mean_carry,
        "total_trend": trend,
        "blocking_trend": block_trend,
        "verdict": verdict,
        "why": why,
    }


def render(name: str, res: dict) -> None:
    print(f"\n=== {name} ===")
    print(
        f"{'round':<10}{'total':>6}{'blk':>5}{'C':>4}{'H':>4}{'M':>4}{'L':>4}{'carry':>8}{'evid':>7}"
    )
    for r in res["rounds"]:
        carry = "—" if r["carry_rate"] is None else f"{r['carry_rate']:.0%}"
        evid = "—" if r["evidence_rate"] is None else f"{r['evidence_rate']:.0%}"
        print(
            f"{r['round']:<10}{r['total']:>6}{r['blocking']:>5}{r['critical']:>4}"
            f"{r['high']:>4}{r['medium']:>4}{r['low']:>4}{carry:>8}{evid:>7}"
        )
    mc = res["mean_carry_rate"]
    print(
        f"  mean carry-forward : {'—' if mc is None else f'{mc:.0%}'}   (higher = rounds agree on what is wrong)"
    )
    print(f"  total trend        : {res['total_trend']:+d}")
    print(f"  blocking trend     : {res['blocking_trend']:+d}   (C+H; must not rise)")
    print(f"  VERDICT            : {res['verdict']} — {res['why']}")


def selftest() -> int:
    """Discrimination gate. A scorer that matches nothing reports RANDOM_WALK on
    every input, including a genuinely converging run — the failure mode is
    silent and it invalidates every number this script prints. Run this before
    trusting a result, and after any change to the matcher or its threshold.
    """
    # Same defect, independently reworded by two reviewers — MUST match.
    same = [
        (
            "- CRITICAL SignerProvider.kt:83 — live signer resolves under dryRun, "
            "so a dry run can sign a real transaction",
            "- CRITICAL signing/SignerProvider.kt:91 — the dryRun flag does not prevent "
            "resolving a live signer; a dry run is able to sign real transactions",
        ),
        (
            "- HIGH JupiterExecutor.kt:210 — mint decimals hardcoded to 6 instead of "
            "read from getMint, a 10x overspend on any 9-decimal asset",
            "- HIGH JupiterExecutor.kt:214 — hardcoded decimal constant rather than the "
            "authoritative getMint lookup; overspends 10x when the mint has 9 decimals",
        ),
    ]
    # Genuinely different defects — MUST NOT match, including two in one file.
    diff = [
        (
            "- CRITICAL SignerProvider.kt:83 — live signer resolves under dryRun",
            "- CRITICAL SignerProvider.kt:140 — the API key is written to the debug log "
            "on every boot, leaking a credential into shipped logs",
        ),
        (
            "- HIGH OrderService.kt:44 — slippage cap is compared with equals not compareTo",
            "- HIGH PriceBus.kt:12 — stale price events are never evicted so the cache "
            "grows without bound",
        ),
    ]

    failures = []
    for a, b in same:
        fa, fb = parse_findings(a)[0], parse_findings(b)[0]
        if not fa.matches(fb):
            failures.append(
                f"MISS (should match, sim={jaccard(fa.toks, fb.toks):.2f}): {fa.text[:60]}"
            )
    for a, b in diff:
        fa, fb = parse_findings(a)[0], parse_findings(b)[0]
        if fa.matches(fb):
            failures.append(
                f"FALSE MATCH (should differ, sim={jaccard(fa.toks, fb.toks):.2f}): {fa.text[:60]}"
            )

    # An end-to-end converging run must not score RANDOM_WALK.
    r1 = parse_findings(same[0][0] + "\n\n" + same[1][0] + "\n\n" + diff[1][1])
    r2 = parse_findings(same[0][1] + "\n\n" + same[1][1])
    res = score([("r1", r1), ("r2", r2)])
    if res["verdict"] == "RANDOM_WALK":
        failures.append(
            f"end-to-end: converging run scored RANDOM_WALK (carry={res['mean_carry_rate']})"
        )

    for f in failures:
        print(f"  FAIL {f}")
    print(
        f"selftest: {'PASS' if not failures else f'{len(failures)} FAILURE(S)'} "
        f"(threshold={MATCH_THRESHOLD}, e2e carry={res['mean_carry_rate']}, verdict={res['verdict']})"
    )
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    if not args:
        print(__doc__)
        return 2

    report = {}
    for arg in args:
        target = Path(arg).expanduser()
        if not target.exists():
            print(f"! no such path: {target}", file=sys.stderr)
            continue
        runs = load_rounds(target)
        if not runs:
            print(f"! no round artifacts found under {target}", file=sys.stderr)
            continue
        # Findings from separate phases are separate targets; only score a phase
        # against itself.
        by_run: dict[str, list[tuple[str, list[Finding]]]] = defaultdict(list)
        for label, fs in runs:
            by_run[label.split(".")[0] if "." in label else "run"].append((label, fs))
        for run_key, seq in by_run.items():
            if len(seq) < 2:
                continue
            name = f"{target.name}:{run_key}" if run_key != "run" else target.name
            res = score(seq)
            report[name] = res
            if not as_json:
                render(name, res)

    if as_json:
        print(json.dumps(report, indent=2))
    elif report:
        walks = [k for k, v in report.items() if v["verdict"] == "RANDOM_WALK"]
        print(
            f"\n{len(report)} run(s) scored — {len(walks)} RANDOM_WALK, "
            f"{sum(1 for v in report.values() if v['verdict'] == 'CONVERGING')} CONVERGING"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
