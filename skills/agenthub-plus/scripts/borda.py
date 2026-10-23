#!/usr/bin/env python3
"""Judge mode for agenthub-plus: correctness gate, anonymised candidates, Borda tally.

Borda-count judging is adapted from qiao/horse-race (MIT); see LICENSES/horse-race.txt.
Unlike horse-race, entries that fail the gate command are disqualified before any judge
sees them, and a judge's ballot only counts if it cites evidence for its first choice.

    borda.py prepare --session SID [--gate CMD] [--judges 3]
    borda.py tally   --session SID [--format table|json]
    borda.py selftest

prepare: clears and refills .agenthub/board/judging/<SID>/ (a fresh round each time): runs the
  gate in each agent worktree, writes candidate-<LABEL>.diff per surviving agent (labels A, B,
  C ... shuffled so they carry no agent number) and order-judge-<i>.txt (a different
  presentation order per judge). The label -> agent mapping goes to
  .agenthub/sessions/<SID>/judging-mapping.json, outside the folder judges read.
tally: counts only ballot-judge-1..N.json (N from prepare) and ballot-judge-tiebreak.json, each
  {"ranking": ["B", "A", "C"], "evidence": {"B": "file:line or test name", ...}}
  and prints Borda scores. Exit 3 means the top is tied and a tiebreak judge is needed.
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from result_ranker import (get_hub_branches, get_session_config,  # noqa: E402
                           get_worktree_path, run_git)


SESSION_RE = re.compile(r"^[A-Za-z0-9_-]+$")
JUDGING_ROOT = os.path.join(".agenthub", "board", "judging")


def judging_dir(session_id):
    """The session's judging folder, refusing any id that could point outside JUDGING_ROOT
    (prepare deletes this folder)."""
    if not SESSION_RE.match(session_id):
        sys.exit(f"Error: invalid session id {session_id!r}")
    path = os.path.realpath(os.path.join(JUDGING_ROOT, session_id))
    if os.path.dirname(path) != os.path.realpath(JUDGING_ROOT):
        sys.exit(f"Error: judging folder {path} is outside {JUDGING_ROOT}")
    return path


def mapping_path(session_id):
    """Coordinator-only: kept out of the judging folder so judges never see who wrote what."""
    return os.path.join(".agenthub", "sessions", session_id, "judging-mapping.json")


def ballot_names(judges):
    return [f"ballot-judge-{i}.json" for i in range(1, judges + 1)] + ["ballot-judge-tiebreak.json"]


def run_gate(worktree, cmd, timeout):
    """Run the gate with stderr folded into stdout, so a failure's reason is kept."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=worktree, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return f"gate timed out after {timeout}s", 1


def borda(ballots, labels):
    """ballots: list of rankings (best first). Returns {label: points}; with N candidates
    first place earns N-1 points, last earns 0. Labels a ballot omits earn 0 from it."""
    n = len(labels)
    points = {l: 0 for l in labels}
    for ranking in ballots:
        for pos, label in enumerate(ranking):
            if label in points:
                points[label] += n - 1 - pos
    return points


def valid_ballot(ballot, labels):
    """A ballot counts only if it ranks every candidate exactly once and cites evidence for
    its first choice. Returns (ok, reason)."""
    ranking = ballot.get("ranking")
    if not isinstance(ranking, list) or sorted(ranking) != sorted(labels):
        return False, f"ranking must list each of {sorted(labels)} exactly once"
    evidence = (ballot.get("evidence") or {}).get(ranking[0], "")
    if not str(evidence).strip():
        return False, f"no evidence cited for first choice {ranking[0]}"
    return True, ""


def cmd_prepare(args):
    config = get_session_config(args.session)
    gate = args.gate or config.get("gate_cmd")
    timeout = int(config.get("eval_timeout", 1800))
    base = config.get("base_branch", "main")
    out = judging_dir(args.session)
    # A fresh round every time: stale ballots or diffs from an earlier round must never count.
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)

    survivors, disqualified = [], []
    for branch in get_hub_branches(args.session):
        agent = branch.split("/")[2]
        if gate:
            wt = get_worktree_path(branch)
            output, rc = run_gate(wt, gate, timeout) if wt else ("no worktree", 1)
            if rc != 0:
                disqualified.append({"agent": agent, "reason": output[-500:]})
                continue
        survivors.append((agent, branch))

    labels = [chr(ord("A") + i) for i in range(len(survivors))]
    random.shuffle(labels)
    mapping = {}
    for label, (agent, branch) in zip(labels, survivors):
        mapping[label] = agent
        with open(os.path.join(out, f"candidate-{label}.diff"), "w") as f:
            f.write(run_git("diff", f"{base}...{branch}"))
    with open(mapping_path(args.session), "w") as f:
        json.dump({"mapping": mapping, "judges": args.judges,
                   "disqualified": disqualified}, f, indent=2)
    for i in range(1, args.judges + 1):
        order = sorted(mapping)
        random.shuffle(order)
        with open(os.path.join(out, f"order-judge-{i}.txt"), "w") as f:
            f.write("\n".join(order) + "\n")

    print(f"Candidates: {len(mapping)}  Disqualified by gate: {len(disqualified)}")
    for d in disqualified:
        print(f"  DQ {d['agent']}: {d['reason'].splitlines()[-1] if d['reason'] else 'gate failed'}")
    print(f"Judging files: {out}")
    if len(mapping) < 2:
        print("Fewer than 2 candidates passed the gate; no vote needed.")


def cmd_tally(args):
    out = judging_dir(args.session)
    with open(mapping_path(args.session)) as f:
        meta = json.load(f)
    mapping, judges = meta["mapping"], int(meta["judges"])
    labels = sorted(mapping)
    expected = ballot_names(judges)
    regular, tiebreak_name = expected[:-1], expected[-1]
    ignored = sorted(n for n in os.listdir(out) if n.startswith("ballot") and n not in expected)

    def load(name):
        try:
            with open(os.path.join(out, name)) as f:
                return json.load(f), ""
        except FileNotFoundError:
            return None, ""
        except (OSError, ValueError) as e:
            return None, f"unreadable: {e}"

    ballots, rejected, firsts = [], [], {l: 0 for l in labels}
    for name in regular:
        ballot, err = load(name)
        if ballot is None:
            if err:
                rejected.append((name, err))
            continue
        ok, reason = valid_ballot(ballot, labels)
        if not ok:
            rejected.append((name, reason))
            continue
        ballots.append(ballot["ranking"])
        firsts[ballot["ranking"][0]] += 1

    points = borda(ballots, labels)
    # Ties on points break on first-place votes; anything still tied goes to the tiebreak judge,
    # who ranks only the tied candidates.
    order = sorted(labels, key=lambda l: (points[l], firsts[l]), reverse=True)
    top = (points[order[0]], firsts[order[0]]) if order else None
    tied = [l for l in order if (points[l], firsts[l]) == top]
    tiebreak_used = False
    if len(tied) > 1 and ballots:
        # The tiebreak ballot counts only if this tie was already recorded by an earlier tally
        # and the ballot was written after that, so a regular judge cannot pre-write it.
        tie = meta.get("tie") or {}
        tb_path = os.path.join(out, tiebreak_name)
        tb, err = load(tiebreak_name)
        if tb is not None:
            if sorted(tie.get("labels", [])) != sorted(tied):
                rejected.append((tiebreak_name, "written before this tie was recorded by tally"))
            elif os.stat(tb_path).st_mtime_ns <= int(tie.get("recorded_ns", 0)):
                rejected.append((tiebreak_name, "older than the recorded tie"))
            else:
                ok, reason = valid_ballot(tb, tied)
                if ok:
                    winner = tb["ranking"][0]
                    order = [winner] + [l for l in order if l != winner]
                    tied, tiebreak_used = [winner], True
                else:
                    rejected.append((tiebreak_name, reason))
        elif err:
            rejected.append((tiebreak_name, err))
        if not tiebreak_used and sorted(tie.get("labels", [])) != sorted(tied):
            meta["tie"] = {"labels": tied, "recorded_ns": time.time_ns()}
            with open(mapping_path(args.session), "w") as f:
                json.dump(meta, f, indent=2)
    result = {
        "tiebreak_used": tiebreak_used,
        "ballots_ignored": ignored,
        "ballots_counted": len(ballots),
        "ballots_rejected": [{"file": n, "reason": r} for n, r in rejected],
        "ranking": [{"label": l, "agent": mapping[l], "points": points[l],
                     "first_place_votes": firsts[l]} for l in order],
        "tiebreak_needed": len(tied) > 1,
        "tied": [mapping[l] for l in tied] if len(tied) > 1 else [],
    }
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Ballots counted: {len(ballots)}  rejected: {len(rejected)}  ignored: {len(ignored)}")
        for n, r in rejected:
            print(f"  rejected {n}: {r}")
        for n in ignored:
            print(f"  ignored {n}: not one of the {judges} judge ballots or the tiebreak ballot")
        print(f"{'RANK':<6} {'LABEL':<7} {'AGENT':<10} {'POINTS':<8} {'1ST':<4}")
        for i, r in enumerate(result["ranking"], 1):
            print(f"{i:<6} {r['label']:<7} {r['agent']:<10} {r['points']:<8} {r['first_place_votes']:<4}")
        if not ballots:
            print("No valid ballots: no winner. Re-run the judges.")
        elif result["tiebreak_needed"]:
            print(f"TIE between {', '.join(result['tied'])}: spawn one tiebreak judge.")
        else:
            print(f"Winner: {mapping[order[0]]}" + (" (decided by the tiebreak judge)" if tiebreak_used else ""))
    if not ballots:
        sys.exit(2)
    if result["tiebreak_needed"]:
        sys.exit(3)


def cmd_selftest(_args):
    labels = ["A", "B", "C"]
    assert borda([["A", "B", "C"]], labels) == {"A": 2, "B": 1, "C": 0}
    assert borda([["A", "B", "C"], ["B", "A", "C"], ["B", "C", "A"]], labels) == {"A": 3, "B": 5, "C": 1}
    assert valid_ballot({"ranking": ["B", "A", "C"], "evidence": {"B": "Foo.kt:12"}}, labels)[0]
    assert not valid_ballot({"ranking": ["B", "A"], "evidence": {"B": "x"}}, labels)[0]
    assert not valid_ballot({"ranking": ["B", "B", "C"], "evidence": {"B": "x"}}, labels)[0]
    assert not valid_ballot({"ranking": ["B", "A", "C"], "evidence": {"A": "x"}}, labels)[0]
    assert not valid_ballot({"ranking": ["B", "A", "C"], "evidence": {"B": "  "}}, labels)[0]
    print("selftest: ok")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("prepare")
    pr.add_argument("--session", required=True)
    pr.add_argument("--gate", help="Correctness gate run in each worktree (default: session gate_cmd)")
    pr.add_argument("--judges", type=int, default=3)
    t = sub.add_parser("tally")
    t.add_argument("--session", required=True)
    t.add_argument("--format", choices=["table", "json"], default="table")
    sub.add_parser("selftest")
    args = p.parse_args()
    {"prepare": cmd_prepare, "tally": cmd_tally, "selftest": cmd_selftest}[args.cmd](args)


if __name__ == "__main__":
    main()
