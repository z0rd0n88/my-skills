#!/usr/bin/env python3
"""Persist a dw-review Workflow result and print the manager's slice of it.

Usage: extract-dw-review.py <workflow-output.json> <dest.json>
       extract-dw-review.py --selftest

<workflow-output.json> is whatever the Workflow tool handed back, saved to a
file. The payload is nested differently depending on how the result is
captured, so this finds it wherever it sits, stamps a stable `F<n>` id on every
confirmed finding (finding-fixer addresses them by id), writes it verbatim to
<dest.json>, and prints ONLY what baton-runner-managed's golden rule 2 lets the
manager read: the verdict, per-lens counts, confirmed findings as
`F<n> [SEVERITY] title (location)`, refuted titles, any reviewer claim the
skeptic found wrong, and a grouping hint for the finding-fixer run.

`verdict: NO-FINDINGS` means the skeptic never ran. It is not an approval.
"""

import contextlib
import io
import json
import os
import posixpath
import sys
import tempfile


def find_payload(node):
    """Depth-first search for the object the workflow script returned."""
    if isinstance(node, dict):
        if "verified" in node or node.get("verdict") == "NO-FINDINGS":
            return node
        for value in node.values():
            hit = find_payload(value)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for value in node:
            hit = find_payload(value)
            if hit is not None:
                return hit
    elif isinstance(node, str):
        # The result often arrives as an embedded JSON string.
        text = node.strip()
        if text[:1] in ("{", "["):
            try:
                return find_payload(json.loads(text))
            except ValueError:
                return None
    return None


def stamp_ids(payload):
    """Give every confirmed finding a stable id, in the skeptic's own order."""
    confirmed = (payload.get("verified") or {}).get("confirmed") or []
    for index, finding in enumerate(confirmed, start=1):
        finding["id"] = "F{}".format(index)
    return confirmed


def group_by_dir(confirmed):
    """Bucket ids by the directory in `location` — the seed for finding-fixer groups."""
    groups = {}
    for finding in confirmed:
        directory = posixpath.dirname(finding.get("location", "").split(":")[0]) or "."
        groups.setdefault(directory, []).append(finding["id"])
    return groups


def report_no_findings(payload):
    print("verdict: NO-FINDINGS — the skeptic never ran. NOT an approval.")
    print("ref: {}   sha: {}".format(payload.get("ref"), payload.get("sha")))
    for review in payload.get("reviews") or []:
        checked = review.get("checked") or []
        not_examined = review.get("notExamined") or []
        print(
            "  lens {}: checked={} notExamined={}".format(
                review.get("lens"), len(checked), len(not_examined)
            )
        )
        if not checked:
            print(
                "    ^ empty `checked` is the tell that the scope was wrong "
                "(a lane whose git diff failed still returns a clean result)"
            )


def report_verified(payload):
    verified = payload["verified"]
    print(
        "verdict: {}   ref: {}   sha: {}".format(
            verified["verdict"], payload.get("ref"), payload.get("sha")
        )
    )
    by_lens = ", ".join(
        "{}={}".format(b["lens"], b["n"]) for b in payload.get("byLens") or []
    )
    print("raw: {} across {}".format(payload.get("rawCount"), by_lens or "?"))

    confirmed = verified.get("confirmed") or []
    print("confirmed: {}".format(len(confirmed)))
    for finding in confirmed:
        print(
            "  {} [{}]{} {}  ({})".format(
                finding["id"],
                finding["severity"],
                " BEFORE-MERGE" if finding.get("beforeMerge") else "",
                finding["title"],
                finding["location"],
            )
        )

    refuted = verified.get("refuted") or []
    print("refuted: {}".format(len(refuted)))
    for finding in refuted:
        print("  {}".format(finding["title"]))

    wrong = verified.get("checkedClaimsThatAreWrong") or []
    print("checkedClaimsThatAreWrong: {}".format(len(wrong)))
    for claim in wrong:
        print("  {}".format(claim))

    residual = verified.get("residualRisk") or []
    print(
        "residualRisk: {} entries — in the JSON; the closing unit copies them "
        "verbatim into the review record".format(len(residual))
    )

    if confirmed:
        groups = group_by_dir(confirmed)
        print(
            "grouping hint ({} dirs — merge down to 2-4 finding-fixer groups):".format(
                len(groups)
            )
        )
        for directory, ids in sorted(groups.items()):
            print("  {}  {}".format(", ".join(ids), directory))


def selftest():
    payload = {
        "ref": "origin/main",
        "sha": "abc1234",
        "rawCount": 9,
        "byLens": [{"lens": "api", "n": 9}],
        "verified": {
            "verdict": "MERGE-WITH-FIXES",
            "confirmed": [
                {
                    "severity": "HIGH",
                    "title": "a",
                    "location": "src/a/One.kt:12",
                    "beforeMerge": True,
                },
                {"severity": "LOW", "title": "b", "location": "src/a/Two.kt:3"},
                {"severity": "MEDIUM", "title": "c", "location": "CLAUDE.md:9"},
            ],
            "refuted": [{"title": "r1"}],
            "checkedClaimsThatAreWrong": ["w1"],
        },
    }
    confirmed = stamp_ids(payload)
    assert [f["id"] for f in confirmed] == ["F1", "F2", "F3"], confirmed
    # A root-level file has no directory: the `or "."` fallback keeps it a key.
    assert group_by_dir(confirmed) == {"src/a": ["F1", "F2"], ".": ["F3"]}
    # An id must survive the round trip: it is what finding-fixer addresses.
    assert json.loads(json.dumps(payload))["verified"]["confirmed"][0]["id"] == "F1"
    # The payload arrives nested, and often as an embedded JSON string.
    assert find_payload({"a": ['{"verified": {"confirmed": []}}']}) == {
        "verified": {"confirmed": []}
    }
    # NO-FINDINGS carries no `verified` key at all; find_payload must still find it.
    assert find_payload({"a": {"verdict": "NO-FINDINGS"}}) == {"verdict": "NO-FINDINGS"}
    assert stamp_ids({"verdict": "NO-FINDINGS"}) == []

    # The printed slice is the ONLY thing golden rule 2 lets the manager read, so
    # assert on it: a print path that silently stops printing is the failure here.
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        report_verified(payload)
    text = out.getvalue()
    assert "verdict: MERGE-WITH-FIXES" in text, text
    assert "  F1 [HIGH] BEFORE-MERGE a  (src/a/One.kt:12)" in text, text
    assert "  F3 [MEDIUM] c  (CLAUDE.md:9)" in text, text
    assert "refuted: 1" in text and "checkedClaimsThatAreWrong: 1" in text, text
    assert "grouping hint (2 dirs" in text and "  F1, F2  src/a" in text, text

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        report_no_findings(
            {"verdict": "NO-FINDINGS", "reviews": [{"lens": "api", "checked": []}]}
        )
    text = out.getvalue()
    assert "NOT an approval" in text, text
    assert "empty `checked` is the tell" in text, text

    # A dead skeptic must exit, not crash and not print a report. The raw payload
    # is still written first, so the run is recoverable.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump({"verified": None, "ref": "feat/x"}, handle)
        source = handle.name
    dest = source + ".out"
    try:
        main(["extract", source, dest])
    except SystemExit as exc:
        assert "skeptic returned nothing" in str(exc), exc
    else:
        raise AssertionError("a null `verified` must exit, not report")
    assert json.load(open(dest))["verified"] is None, "raw payload must still be saved"
    os.remove(source)
    os.remove(dest)

    print("selftest ok")


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) != 3:
        sys.exit(__doc__)
    source, dest = argv[1], argv[2]

    with open(source) as handle:
        raw = json.load(handle)

    payload = find_payload(raw)
    if payload is None:
        sys.exit(
            "no review payload in {} — check the workflow's journal.jsonl "
            "before assuming the run returned nothing".format(source)
        )

    stamp_ids(payload)

    with open(dest, "w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    if isinstance(payload.get("verified"), dict):
        report_verified(payload)
    elif "verified" in payload:
        # A dead skeptic resolves to null and dw-review returns it unguarded.
        sys.exit(
            "the skeptic returned nothing (`verified: null`) — the Verify phase "
            "failed, so there is no verdict. The raw payload IS saved at {}. "
            "Resume the dw-review Workflow with resumeFromRunId; this is not a "
            "clean phase.".format(dest)
        )
    else:
        report_no_findings(payload)
    print("written: {}".format(dest))


if __name__ == "__main__":
    main(sys.argv)
