#!/usr/bin/env python3
"""Judge mode for agenthub-plus: correctness gate, anonymised candidates, Borda tally.

Borda-count judging is adapted from qiao/horse-race (MIT); see LICENSES/horse-race.txt.
Unlike horse-race, entries that fail the gate command are disqualified before any judge
sees them, and a judge's ballot only counts if it cites evidence for its first choice.

    borda.py prepare --session SID [--gate CMD] [--judges 3]
    borda.py tally   --session SID [--format table|json]
    borda.py selftest

prepare: runs the gate in each agent worktree, writes one diff per surviving agent under
  .agenthub/board/judging/<SID>/candidate-<LABEL>.diff (labels A, B, C ... shuffled so they
  carry no agent number), mapping.json (label -> agent, for the coordinator only) and
  order-judge-<i>.txt (a different presentation order per judge).
tally: reads ballot-judge-<i>.json files, each
  {"ranking": ["B", "A", "C"], "evidence": {"B": "file:line or test name", ...}}
  and prints Borda scores. Exit 3 means the top is tied and a tiebreak judge is needed.
"""

import argparse
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from result_ranker import (get_hub_branches, get_session_config,  # noqa: E402
                           get_worktree_path, run_git)


def judging_dir(session_id):
    return os.path.join(".agenthub", "board", "judging", session_id)


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
    os.makedirs(out, exist_ok=True)

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
    with open(os.path.join(out, "mapping.json"), "w") as f:
        json.dump({"mapping": mapping, "disqualified": disqualified}, f, indent=2)
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
    with open(os.path.join(out, "mapping.json")) as f:
        mapping = json.load(f)["mapping"]
    labels = sorted(mapping)
    ballots, rejected, firsts = [], [], {l: 0 for l in labels}
    for name in sorted(os.listdir(out)):
        if not (name.startswith("ballot-judge-") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(out, name)) as f:
                ballot = json.load(f)
        except (OSError, ValueError) as e:
            rejected.append((name, f"unreadable: {e}"))
            continue
        ok, reason = valid_ballot(ballot, labels)
        if not ok:
            rejected.append((name, reason))
            continue
        ballots.append(ballot["ranking"])
        firsts[ballot["ranking"][0]] += 1

    points = borda(ballots, labels)
    # Ties on points break on first-place votes; anything still tied needs a tiebreak judge.
    order = sorted(labels, key=lambda l: (points[l], firsts[l]), reverse=True)
    top = (points[order[0]], firsts[order[0]]) if order else None
    tied = [l for l in order if (points[l], firsts[l]) == top]
    result = {
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
        print(f"Ballots counted: {len(ballots)}  rejected: {len(rejected)}")
        for n, r in rejected:
            print(f"  rejected {n}: {r}")
        print(f"{'RANK':<6} {'LABEL':<7} {'AGENT':<10} {'POINTS':<8} {'1ST':<4}")
        for i, r in enumerate(result["ranking"], 1):
            print(f"{i:<6} {r['label']:<7} {r['agent']:<10} {r['points']:<8} {r['first_place_votes']:<4}")
        if not ballots:
            print("No valid ballots: no winner. Re-run the judges.")
        elif result["tiebreak_needed"]:
            print(f"TIE between {', '.join(result['tied'])}: spawn one tiebreak judge.")
        else:
            print(f"Winner: {mapping[order[0]]}")
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
