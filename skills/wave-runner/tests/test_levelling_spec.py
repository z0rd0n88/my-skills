#!/usr/bin/env python3
"""Executable check of the wave-runner levelling and edge-derivation SPECIFICATION.

This does not test code. `wave-runner` is a prompt document, so there is no
implementation to exercise. What this file does instead:

  1. Implements the levelling formula **exactly as written** in
     REFERENCE.md § "Levelling into waves (Phase 5)", and the edge-proof rules
     exactly as written in § "Building the graph (Phase 4)".
  2. Runs them over hand-authored graphs whose expected waves were computed by
     hand, independently of the formula, and written down before running.
  3. Asserts three properties that the formula never states but must hold:
     soundness, maximality, totality.

A failing case means **the specification is wrong**, not that this file is.

The point of transcribing the spec literally rather than writing a correct
topological sort is that a correct implementation would prove nothing about the
document an agent actually reads.

Negative controls are mandatory and run every time (see NEGATIVE_CONTROLS).
Each is a deliberately broken input that a checker is *required* to reject. If
any negative control passes, the harness itself is broken and the run exits
non-zero regardless of how many positive cases succeeded — a suite that cannot
fail is the "empty result read as a pass" bug in test form.

    python3 test_levelling_spec.py

Exit 0 = spec upheld and harness proven able to fail. Exit 1 = otherwise.
"""

import sys


class StateCorrupt(Exception):
    """REFERENCE.md § Validate before trusting nodes.json -> STATE-CORRUPT."""


class CyclicGraph(Exception):
    """REFERENCE.md § Building the graph -> CYCLIC-GRAPH."""


class Diverged(Exception):
    """The recursion did not terminate. The spec claims acyclicity prevents this."""


# --------------------------------------------------------------------------
# The specification, transcribed literally.
# --------------------------------------------------------------------------


def validate(nodes):
    """REFERENCE.md: 'check the container parses, every blocked_by id exists,
    every node has an id and status, and the graph is still acyclic'."""
    for n in nodes:
        if "id" not in n or "status" not in n:
            raise StateCorrupt(f"node missing id or status: {n!r}")

    ids = {n["id"] for n in nodes}
    if len(ids) != len(nodes):
        raise StateCorrupt("duplicate node ids")

    for n in nodes:
        for b in n.get("blocked_by", []):
            if b not in ids:
                raise StateCorrupt(f"dangling blocked_by id {b!r} on node {n['id']!r}")

    # Kahn's algorithm, per REFERENCE.md § Building the graph.
    by_id = {n["id"]: n for n in nodes}
    indeg = {i: len(by_id[i].get("blocked_by", [])) for i in ids}
    queue = [i for i in ids if indeg[i] == 0]
    seen = 0
    while queue:
        cur = queue.pop()
        seen += 1
        for other in nodes:
            if cur in other.get("blocked_by", []):
                indeg[other["id"]] -= 1
                if indeg[other["id"]] == 0:
                    queue.append(other["id"])
    if seen != len(nodes):
        raise CyclicGraph(f"residue of {len(nodes) - seen} node(s)")


def level(nodes, run_validation=True):
    """REFERENCE.md, verbatim:

    Let B(n) = blocked_by(n) with every DONE id already stripped.

    wave(n) = null                       if status(n) == DONE
            = 0                          if B(n) is empty
            = 1 + max(wave(b) for b in B(n))
    """
    if run_validation:
        validate(nodes)

    by_id = {n["id"]: n for n in nodes}
    memo, in_progress = {}, set()

    def wave(nid):
        node = by_id[nid]
        if node["status"] == "DONE":
            return None
        if nid in memo:
            return memo[nid]
        if nid in in_progress:
            # Only reachable when validation is skipped; proves the spec's
            # claim that acyclicity is load-bearing for totality.
            raise Diverged(f"recursion re-entered {nid!r}")
        in_progress.add(nid)

        b_set = [b for b in node.get("blocked_by", []) if by_id[b]["status"] != "DONE"]
        result = 0 if not b_set else 1 + max(wave(b) for b in b_set)

        in_progress.discard(nid)
        memo[nid] = result
        return result

    return {n["id"]: wave(n["id"]) for n in nodes}


def derive_edges(nodes):
    """REFERENCE.md § Building the graph. Edge rule: B consumes X, A produces X
    => A -> B. A shared file is explicitly NOT an edge:

        'A shared file proves mutual exclusion, not order. It never creates an
         edge by itself; it makes the two nodes un-co-schedulable.'
    """
    edges = set()
    for consumer in nodes:
        for sym in consumer.get("consumes", []):
            for producer in nodes:
                if producer["id"] != consumer["id"] and sym in producer.get(
                    "produces", []
                ):
                    edges.add((producer["id"], consumer["id"]))
    return edges


def collisions(nodes, waves):
    """Phase 6 check 3: within a wave, owned_files must be pairwise disjoint."""
    hits = set()
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if waves.get(a["id"]) is None or waves[a["id"]] != waves.get(b["id"]):
                continue
            if set(a.get("owned_files", [])) & set(b.get("owned_files", [])):
                hits.add(tuple(sorted((a["id"], b["id"]))))
    return hits


# --------------------------------------------------------------------------
# Properties the formula never states but must satisfy.
# --------------------------------------------------------------------------


def check_soundness(nodes, waves):
    """For every live edge A -> B, wave(A) < wave(B)."""
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        if n["status"] == "DONE":
            continue
        for b in n.get("blocked_by", []):
            if by_id[b]["status"] == "DONE":
                continue
            if not waves[b] < waves[n["id"]]:
                return f"edge {b} -> {n['id']} violated: {waves[b]} !< {waves[n['id']]}"
    return None


def check_maximality(nodes, waves):
    """No node sits later than it must: every node at wave w>0 has a blocker at w-1,
    and every node with no live blockers is at wave 0."""
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        w = waves[n["id"]]
        if w is None:
            continue
        live = [b for b in n.get("blocked_by", []) if by_id[b]["status"] != "DONE"]
        if not live:
            if w != 0:
                return f"{n['id']} has no live blockers but sits at wave {w}"
            continue
        if w == 0:
            return f"{n['id']} has live blockers but sits at wave 0"
        if not any(waves[b] == w - 1 for b in live):
            return f"{n['id']} at wave {w} has no blocker at wave {w - 1} (slack)"
    return None


def check_totality(nodes, waves):
    """Every non-DONE node has an integer wave; every DONE node has null."""
    for n in nodes:
        w = waves[n["id"]]
        if n["status"] == "DONE":
            if w is not None:
                return f"DONE node {n['id']} has wave {w!r}, expected null"
        elif not isinstance(w, int):
            return f"live node {n['id']} has wave {w!r}, expected an integer"
    return None


PROPERTIES = [
    ("soundness", check_soundness),
    ("maximality", check_maximality),
    ("totality", check_totality),
]


def N(i, blocked_by=(), status="NEW", **kw):
    return {"id": i, "status": status, "blocked_by": list(blocked_by), **kw}


# --------------------------------------------------------------------------
# Fixtures. `expected` was computed by hand, before running anything.
# --------------------------------------------------------------------------

LEVELLING_CASES = [
    (
        "diamond",
        [N("A"), N("B", ["A"]), N("C", ["A"]), N("D", ["B", "C"])],
        # A has no blockers -> 0. B,C blocked by A -> 1. D -> 1+max(1,1) = 2.
        {"A": 0, "B": 1, "C": 1, "D": 2},
    ),
    (
        "multi-blocker spanning waves",
        [N("A"), N("B", ["A"]), N("C", ["B"]), N("D", ["A", "C"])],
        # D is blocked by a wave-0 AND a wave-2 node: 1+max(0,2) = 3, not 1.
        # The case a hand-drawn plan gets wrong.
        {"A": 0, "B": 1, "C": 2, "D": 3},
    ),
    (
        "all blockers DONE",
        [N("X", status="DONE"), N("Y", ["X"])],
        # Stripping X empties B(Y), so the '= 0' clause fires. Without
        # stripping this is max() over an empty set -- the bug the spec's
        # totality argument exists to rule out.
        {"X": None, "Y": 0},
    ),
    (
        "DONE and live blockers mixed",
        [N("D1", status="DONE"), N("L"), N("Z", ["D1", "L"])],
        {"D1": None, "L": 0, "Z": 1},
    ),
    (
        "DONE in the middle of a chain",
        [N("A", status="DONE"), N("B", ["A"]), N("C", ["B"])],
        {"A": None, "B": 0, "C": 1},
    ),
    (
        "disconnected components",
        [N("A"), N("B", ["A"]), N("P"), N("Q", ["P"])],
        {"A": 0, "B": 1, "P": 0, "Q": 1},
    ),
    (
        "wide wave 0",
        [N("A"), N("B"), N("C"), N("D", ["A", "B", "C"])],
        {"A": 0, "B": 0, "C": 0, "D": 1},
    ),
]

RAISING_CASES = [
    ("dangling blocked_by id", [N("P", ["ghost"])], StateCorrupt),
    ("two-node cycle", [N("M", ["N"]), N("N", ["M"])], CyclicGraph),
    ("three-node cycle", [N("M", ["O"]), N("N", ["M"]), N("O", ["N"])], CyclicGraph),
    (
        "dangling id inside an otherwise valid graph",
        [N("A"), N("B", ["A"]), N("C", ["nope"])],
        StateCorrupt,
    ),
]

EDGE_CASES = [
    (
        "symbol match creates a directed edge",
        [N("A", produces=["EdgeClient"]), N("B", consumes=["EdgeClient"])],
        {("A", "B")},
    ),
    (
        "shared owned_files creates NO edge",
        # The bug that shipped: golden rule 4 listed shared owned_files as edge
        # proof while REFERENCE said it proves mutual exclusion, not order.
        [N("A", owned_files=["Routes.kt"]), N("B", owned_files=["Routes.kt"])],
        set(),
    ),
    (
        "no relation at all creates no edge",
        [N("A", produces=["X"]), N("B", consumes=["Y"])],
        set(),
    ),
    (
        "symbol match is directional, not symmetric",
        [N("A", produces=["X"], consumes=[]), N("B", consumes=["X"], produces=[])],
        {("A", "B")},
    ),
]


def run_positive():
    failures = []

    for name, nodes, expected in LEVELLING_CASES:
        try:
            waves = level(nodes)
        except Exception as exc:
            failures.append(f"[levelling/{name}] raised {type(exc).__name__}: {exc}")
            continue
        if waves != expected:
            failures.append(f"[levelling/{name}] got {waves}, hand-computed {expected}")
            continue
        for prop_name, fn in PROPERTIES:
            problem = fn(nodes, waves)
            if problem:
                failures.append(f"[levelling/{name}] {prop_name}: {problem}")

    for name, nodes, exc_type in RAISING_CASES:
        try:
            level(nodes)
        except exc_type:
            pass
        except Exception as exc:
            failures.append(
                f"[raises/{name}] raised {type(exc).__name__}, expected {exc_type.__name__}"
            )
        else:
            failures.append(f"[raises/{name}] did not raise {exc_type.__name__}")

    for name, nodes, expected in EDGE_CASES:
        got = derive_edges(nodes)
        if got != expected:
            failures.append(
                f"[edges/{name}] got {got or 'no edges'}, expected {expected or 'no edges'}"
            )

    # Phase 6 check 3: a shared file must surface as a same-wave collision,
    # which is the constraint that replaces the edge it must not create.
    shared = [N("A", owned_files=["R.kt"]), N("B", owned_files=["R.kt"])]
    waves = level(shared)
    if waves != {"A": 0, "B": 0}:
        failures.append(f"[collision] expected both at wave 0, got {waves}")
    if collisions(shared, waves) != {("A", "B")}:
        failures.append(
            "[collision] shared owned_files in one wave not reported as INFEASIBLE-AT-3"
        )

    return failures


# --------------------------------------------------------------------------
# Negative controls. Each MUST be rejected. A suite that cannot fail is worthless.
# --------------------------------------------------------------------------


def nc_wrong_expectation():
    nodes = [N("A"), N("B", ["A"])]
    return level(nodes) == {"A": 0, "B": 99}


def nc_unsound_schedule():
    nodes = [N("A"), N("B", ["A"])]
    return check_soundness(nodes, {"A": 5, "B": 1}) is None


def nc_slack_schedule():
    nodes = [N("A"), N("B", ["A"])]
    return check_maximality(nodes, {"A": 0, "B": 7}) is None


def nc_missing_wave():
    nodes = [N("A"), N("B", ["A"])]
    return check_totality(nodes, {"A": 0, "B": None}) is None


def nc_cycle_without_validation():
    """The spec claims validation is what makes the recursion total. Skip
    validation on a cycle: if this does NOT diverge, the claim is untested."""
    try:
        level([N("M", ["N"]), N("N", ["M"])], run_validation=False)
    except Diverged:
        return False
    return True


def nc_shared_file_as_edge():
    """The confirmed historical bug, asserted the wrong way round."""
    nodes = [N("A", owned_files=["R.kt"]), N("B", owned_files=["R.kt"])]
    return derive_edges(nodes) == {("A", "B")}


NEGATIVE_CONTROLS = [
    ("a wrong hand-computed expectation is accepted", nc_wrong_expectation),
    ("an unsound schedule passes the soundness check", nc_unsound_schedule),
    ("a schedule with slack passes the maximality check", nc_slack_schedule),
    ("a missing wave passes the totality check", nc_missing_wave),
    ("an unvalidated cycle terminates anyway", nc_cycle_without_validation),
    ("a shared file is treated as an edge", nc_shared_file_as_edge),
]


def run_negative():
    return [
        f"[negative-control] {name} -- HARNESS IS BROKEN"
        for name, fn in NEGATIVE_CONTROLS
        if fn()
    ]


def main():
    positive = run_positive()
    negative = run_negative()

    total = len(LEVELLING_CASES) + len(RAISING_CASES) + len(EDGE_CASES) + 1
    print(f"levelling/edge cases : {total - len(positive)}/{total} passed")
    print(f"properties           : {', '.join(n for n, _ in PROPERTIES)}")
    print(
        f"negative controls    : {len(NEGATIVE_CONTROLS) - len(negative)}/{len(NEGATIVE_CONTROLS)} correctly rejected"
    )

    for line in positive + negative:
        print(f"  FAIL {line}")

    if negative:
        print(
            "\nnegative controls did not all fail as required; results above are not trustworthy"
        )
        return 1
    if positive:
        print("\nthe SPECIFICATION is wrong, not this file")
        return 1
    print("\nspec upheld; harness proven able to fail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
