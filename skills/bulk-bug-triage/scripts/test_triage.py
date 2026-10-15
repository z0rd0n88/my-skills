#!/usr/bin/env python3
"""Self-check: python3 test_triage.py — asserts the pure logic, no network."""

import contextlib
import io
import json
import subprocess
import tempfile
from pathlib import Path

import triage


def cfg_for(tmp, **over):
    raw = {
        "repo": "Acme/Widget",
        "checkout": str(tmp),
        "sha": "a" * 40,
        "label": "bug",
        "date": "2026-09-19",
        "triageLabels": ["needs-triage", "ready-for-agent", "ready-for-human"],
        "inventoryCutoff": "2026-09-19T00:00:00Z",
        "decisions": "d.json",
    }
    rows = over.pop("_rows", [])
    raw.update(over)
    (tmp / "c.json").write_text(json.dumps(raw))
    (tmp / "d.json").write_text(json.dumps(rows))
    return triage.Config(tmp / "c.json")


ROW = {
    "number": 7,
    "status": "valid",
    "system": "Gateway",
    "labels": ["bug", "ready-for-agent"],
    "reason": "Still reproduces.",
    "evidence": [{"path": "src/a b.kt", "line": 12, "end": 20}],
    "history": "Filed in June.",
    "nextStep": "Add a guard.",
}

with tempfile.TemporaryDirectory() as d:
    tmp = Path(d)
    cfg = cfg_for(tmp, _rows=[ROW])

    # marker keys on the pinned sha alone, so editing `date` cannot change it
    assert cfg.marker == "<!-- bug-triage:aaaaaaaa -->"
    assert cfg_for(tmp, date="2026-09-20", _rows=[ROW]).marker == cfg.marker

    body = triage.comment_body(cfg, ROW)
    assert cfg.marker in body
    assert "Still valid — keep open" in body
    # spaces in paths must be percent-encoded, slashes must not be
    assert (
        "https://github.com/Acme/Widget/blob/" + "a" * 40 + "/src/a%20b.kt#L12-L20"
        in body
    )
    # same input -> same body, which is what makes re-publishing a no-op
    assert triage.comment_body(cfg, ROW) == body

    # single-line evidence omits the end anchor
    solo = dict(ROW, evidence=[{"path": "x.kt", "line": 3}])
    assert "#L3)" in triage.comment_body(cfg, solo)

    # fingerprint ignores fields we never touch, reacts to ones we do
    base = {
        "title": "t",
        "body": "b",
        "state": "open",
        "labels": [{"name": "bug"}],
        "updated_at": "whenever",
    }
    assert triage.fingerprint(base) == triage.fingerprint(
        dict(base, updated_at="later")
    )
    assert triage.fingerprint(base) != triage.fingerprint(dict(base, state="closed"))
    # label order must not matter
    two = dict(base, labels=[{"name": "bug"}, {"name": "ui"}])
    assert triage.fingerprint(two) == triage.fingerprint(
        dict(base, labels=[{"name": "ui"}, {"name": "bug"}])
    )

    # duplicate issue numbers are rejected before anything is sent
    dupe = cfg_for(tmp, _rows=[ROW, dict(ROW)])
    try:
        dupe.rows()
        raise AssertionError("duplicate numbers should have been rejected")
    except SystemExit:
        pass

    # plan(): the mutation half of publish, isolated from the network
    live = {"labels": [{"name": "bug"}, {"name": "needs-triage"}, {"name": "ui"}]}
    labels, patch = triage.plan(cfg, ROW, live)
    # the stale triage label goes, the row's replaces it, unrelated labels stay
    assert labels == {"bug", "ui", "ready-for-agent"}
    assert patch == {"labels": ["bug", "ready-for-agent", "ui"]}

    # removeLabels drops a label the issue carries today
    assert "ui" not in triage.plan(cfg, dict(ROW, removeLabels=["ui"]), live)[0]

    # a closure strips every triage label and carries the state reason
    shut = dict(ROW, status="fixed", closureReason="completed")
    assert triage.plan(cfg, shut, live)[1] == {
        "labels": ["bug", "ui"],
        "state": "closed",
        "state_reason": "completed",
    }

    # a reassignment or a milestone move between read and PATCH counts as an edit
    assert triage.fingerprint(base) != triage.fingerprint(
        dict(base, assignees=[{"login": "someone"}])
    )
    assert triage.fingerprint(base) != triage.fingerprint(
        dict(base, milestone={"number": 3})
    )

    # a missing config key dies in the tool's error style, not as a KeyError
    for absent in ("repo", "sha", "inventoryCutoff"):
        raw = json.loads((tmp / "c.json").read_text())
        del raw[absent]
        (tmp / "broken.json").write_text(json.dumps(raw))
        try:
            triage.Config(tmp / "broken.json")
            raise AssertionError(f"a config with no {absent} should have been rejected")
        except SystemExit:
            pass

    # rereviewed keys survive JSON's string-only object keys
    rr = cfg_for(tmp, _rows=[ROW], rereviewed={"531": "2026-09-19T10:00:00Z"})
    assert rr.rereviewed[531] == "2026-09-19T10:00:00Z"


# --- end to end: all three phases against a fake tracker, still no network ---
# The guards live inside preflight() and publish(), so these call the real
# functions over a stub rather than testing their pieces.

REPO_LABELS = ["bug", "stale", "ui", "needs-triage", "ready-for-agent", "ready-for-human"]
CUTOFF = "2026-09-19T10:17:00Z"
ME = "triage-bot"

KEEP = {
    "number": 7,
    "title": "Gateway retries twice on a 503",
    "status": "valid",
    "system": "Gateway",
    "labels": ["bug", "ready-for-agent"],
    "removeLabels": ["stale"],
    "reason": "Still reproduces.",
    "evidence": [{"path": "src/Gateway.kt", "line": 12}],
    "history": "Filed in June.",
    "nextStep": "Add a guard.",
}
SHUT = {
    "number": 9,
    "title": "Order state machine lacks COMPLETE",
    "status": "fixed",
    "closureReason": "completed",
    "system": "Merchant",
    "labels": ["bug"],
    "reason": "Fixed in the pinned tree.",
    "evidence": [{"path": "src/Order.kt", "line": 40}],
    "history": "Filed in May.",
    "nextStep": "None.",
}


def issue(number, title, labels, state="open", updated="2026-09-19T09:00:00Z", **extra):
    return dict(
        number=number,
        title=title,
        body="b",
        state=state,
        labels=[{"name": x} for x in labels],
        updated_at=updated,
        createdAt="2026-06-01T00:00:00Z",
        **extra,
    )


class FakeGitHub:
    """Enough of gh's surface to run preflight, publish and verify for real."""

    def __init__(self, *issues):
        self.issues = {i["number"]: i for i in issues}
        self.comments = {n: [] for n in self.issues}
        self.patches = 0

    def comment(self, number, body, login=ME):
        url = f"https://github.com/Acme/Widget/issues/{number}#c{len(self.comments[number])}"
        c = {"body": body, "user": {"login": login}, "url": url, "html_url": url}
        self.comments[number].append(c)
        return c

    def _number(self, path):
        return int(path.split("/issues/")[1].split("/")[0].split("?")[0])

    def __call__(self, cfg, *args, payload=None):
        if args[:2] == ("label", "list"):
            return [{"name": x} for x in REPO_LABELS]
        if args[:2] == ("issue", "list"):
            return [
                {"number": n, "createdAt": i["createdAt"]}
                for n, i in self.issues.items()
                if i["state"] == "open"
            ]
        if args == ("api", "user"):
            return {"login": ME}
        if args[:2] == ("api", "graphql"):
            return {
                "data": {
                    "repository": {
                        f"i{n}": {
                            "number": n,
                            "state": i["state"].upper(),
                            "stateReason": (i.get("state_reason") or "").upper() or None,
                            "labels": {"nodes": i["labels"]},
                            "comments": {"nodes": self.comments[n]},
                        }
                        for n, i in self.issues.items()
                    }
                }
            }
        path = args[1]
        number = self._number(path)
        if "--method" in args:
            if path.endswith("/comments"):
                return self.comment(number, payload["body"])
            self.patches += 1
            live = self.issues[number]
            live["labels"] = [{"name": x} for x in payload["labels"]]
            if "state" in payload:
                live["state"] = payload["state"]
                live["state_reason"] = payload["state_reason"]
            return live
        if "/comments" in path:
            return [self.comments[number]]
        return self.issues[number]


def git_ok(cmd, **kw):
    if cmd[:3] == ["git", "remote", "get-url"]:
        out = "git@github.com:Acme/Widget.git\n"
    elif cmd[:2] == ["git", "ls-remote"]:
        out = "a" * 40 + "\trefs/heads/main\n"
    else:  # git cat-file -e: every cited path resolves at the pinned sha
        out = ""
    return subprocess.CompletedProcess(cmd, 0, out, "")


def run(fake, rows, phase="publish", **cfg_over):
    """One phase against `fake`, with gh, git and the write pause stubbed out."""
    with tempfile.TemporaryDirectory() as d:
        cfg = cfg_for(Path(d), inventoryCutoff=CUTOFF, _rows=rows, **cfg_over)
        real_gh, real_run, real_sleep = triage.gh, subprocess.run, triage.time.sleep
        triage.gh, subprocess.run, triage.time.sleep = fake, git_ok, lambda _: None
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                if phase == "verify":
                    triage.verify(cfg, cfg.rows(), 24)
                else:
                    triage.preflight(cfg, cfg.rows())
                    if phase == "publish":
                        triage.publish(cfg, cfg.rows())
            return cfg, out.getvalue()
        finally:
            triage.gh, subprocess.run, triage.time.sleep = real_gh, real_run, real_sleep


def refuses(fake, rows, phase="publish", **cfg_over):
    try:
        run(fake, rows, phase, **cfg_over)
    except SystemExit:
        return True
    raise AssertionError(f"{phase} should have refused these rows")


# the happy path reaches the tracker and does exactly what the manifest says
gh = FakeGitHub(
    issue(7, KEEP["title"], ["bug", "stale", "needs-triage"]),
    issue(9, SHUT["title"], ["bug", "needs-triage"]),
)
run(gh, [KEEP, SHUT])
assert gh.issues[7]["state"] == "open"
# the row's labels replace the stale triage label, removeLabels drops `stale`
assert {x["name"] for x in gh.issues[7]["labels"]} == {"bug", "ready-for-agent"}
assert gh.issues[9]["state"] == "closed"
assert gh.issues[9]["state_reason"] == "completed"
# a closed issue keeps no triage label
assert {x["name"] for x in gh.issues[9]["labels"]} == {"bug"}
assert len(gh.comments[7]) == len(gh.comments[9]) == 1
run(gh, [KEEP, SHUT], phase="verify")  # verify agrees, and does not die

# re-running is the documented way to resume: no second comment, nothing moves
before = gh.patches
run(gh, [KEEP, SHUT])
assert len(gh.comments[7]) == len(gh.comments[9]) == 1
assert gh.patches == before, "an already-applied row must not be PATCHed again"

# a maintainer adds an unrelated label after the run finished. plan() is
# additive over the live label set, so the row is still satisfied: the resume
# leaves the new label alone rather than PATCHing a stale plan over it.
gh.issues[7]["labels"].append({"name": "ui"})
gh.issues[7]["updated_at"] = "2026-09-19T23:30:00Z"
before = gh.patches
run(gh, [KEEP, SHUT])
assert {x["name"] for x in gh.issues[7]["labels"]} == {"bug", "ready-for-agent", "ui"}
assert gh.patches == before

# but a maintainer putting a triage label back is a disagreement with the
# manifest, and the post-inventory guard must refuse rather than re-strip it
gh.issues[7]["labels"].append({"name": "needs-triage"})
refuses(gh, [KEEP, SHUT])
assert {x["name"] for x in gh.issues[7]["labels"]} == {
    "bug",
    "ready-for-agent",
    "ui",
    "needs-triage",
}
gh.issues[7]["labels"] = [{"name": x} for x in ("bug", "ready-for-agent")]
gh.issues[7]["updated_at"] = "2026-09-19T09:00:00Z"

# a reply from a human does not make verify report a correct run as failed
gh.comment(7, "thanks!", login="someone-else")
run(gh, [KEEP, SHUT], phase="verify")

# C1: the comment says keep open, the closure says close. One of them is wrong.
refuses(FakeGitHub(issue(7, KEEP["title"], ["bug"])), [dict(KEEP, closureReason="not_planned")], phase="preflight")

# C2: the row does not describe the issue it names, or names a pull request
refuses(FakeGitHub(issue(7, "Some unrelated issue", ["bug"])), [KEEP])
refuses(FakeGitHub(issue(7, KEEP["title"], ["bug"], pull_request={"url": "..."})), [KEEP])

# C4: a maintainer edits an issue between a half-finished run and its retry.
# The comment is already there, so the old guard skipped the cutoff check.
half = FakeGitHub(
    issue(7, KEEP["title"], ["bug", "stale", "needs-triage"], updated="2026-09-19T23:00:00Z")
)
with tempfile.TemporaryDirectory() as d:
    half.comment(7, triage.comment_body(cfg_for(Path(d), inventoryCutoff=CUTOFF), KEEP))
refuses(half, [KEEP])
# ...and the same issue untouched since the inventory publishes fine, so the
# guard is discriminating between edits, not just refusing every retry
fine = FakeGitHub(issue(7, KEEP["title"], ["bug", "stale", "needs-triage"]))
with tempfile.TemporaryDirectory() as d:
    fine.comment(7, triage.comment_body(cfg_for(Path(d), inventoryCutoff=CUTOFF), KEEP))
run(fine, [KEEP])
assert fine.issues[7]["state"] == "open"
assert len(fine.comments[7]) == 1

print("ok")
