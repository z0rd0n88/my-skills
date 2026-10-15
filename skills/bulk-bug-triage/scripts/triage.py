#!/usr/bin/env python3
"""Publish and verify a reviewed issue-triage manifest against GitHub.

Three subcommands, always run in this order:

    triage.py preflight --config triage.config.json
    triage.py publish   --config triage.config.json
    triage.py verify    --config triage.config.json

Issue bodies and source code are never modified: the tool posts one comment per
issue, adjusts labels, and closes the issues the manifest marks for closure.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

OUTCOMES = {
    "valid": "Still valid — keep open",
    "partial": "Partially addressed — keep open",
    "fixed": "Completed — close",
    "obsolete": "Obsolete — close",
    "superseded": "Superseded — close",
}
CLOSE_REASONS = {"completed", "not_planned"}
CLOSING = {"fixed", "obsolete", "superseded"}

# Drop every env token so a bulk write is signed by the account `gh auth status`
# names, not by whatever a session happens to export.
ENV = {
    k: v
    for k, v in os.environ.items()
    if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN")
}


class Config:
    def __init__(self, path):
        raw = json.loads(Path(path).read_text())
        base = Path(path).resolve().parent
        absent = [
            k
            for k in (
                "repo",
                "checkout",
                "sha",
                "label",
                "date",
                "triageLabels",
                "inventoryCutoff",
            )
            if k not in raw
        ]
        if absent:
            die(f"config is missing {absent}")
        self.repo = raw["repo"]  # "owner/name"
        if self.repo.count("/") != 1 or not all(
            c.isalnum() and c.isascii() or c in "._-/" for c in self.repo
        ):
            die(f"repo must be owner/name: {self.repo!r}")
        self.owner, self.name = self.repo.split("/")
        self.checkout = raw["checkout"]  # primary checkout path
        self.sha = raw["sha"]  # commit the evidence cites
        self.label = raw["label"]
        self.branch = raw.get("branch", "main")  # branch the sha must still be at
        self.date = raw["date"]  # YYYY-MM-DD, shown in the comment
        self.triage_labels = set(raw["triageLabels"])
        self.inventory_cutoff = ts(raw["inventoryCutoff"])  # required, ISO8601 + offset
        try:
            self.rereviewed = {int(k): v for k, v in raw.get("rereviewed", {}).items()}
        except ValueError:
            die("rereviewed keys must be issue numbers")
        self.decisions = base / raw.get("decisions", "triage-decisions.json")
        # sha only: `date` is hand-edited, and a changed marker double-posts.
        self.marker = f"<!-- bug-triage:{self.sha[:8]} -->"

    def rows(self):
        rows = json.loads(self.decisions.read_text())
        for r in rows:
            if type(r.get("number")) is not int:
                die(f"issue number must be an integer, got {r.get('number')!r}")
        numbers = [r["number"] for r in rows]
        if len(set(numbers)) != len(numbers):
            die(f"duplicate issue numbers in {self.decisions.name}")
        return rows


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def ts(value):
    """ISO8601 -> aware datetime. A naive timestamp is rejected, not assumed UTC."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        die(f"not an ISO8601 timestamp: {value!r}")
    if parsed.tzinfo is None:
        die(f"timestamp needs a UTC offset: {value!r}")
    return parsed


def git(cfg, *args):
    """Read-only git inside the checkout being triaged."""
    return subprocess.run(
        ["git", *args], cwd=cfg.checkout, capture_output=True, text=True, timeout=60
    )


def gh(cfg, *args, payload=None):
    cmd = ["gh", *args]
    if payload is not None:
        cmd += ["--input", "-"]
    p = subprocess.run(
        cmd,
        input=None if payload is None else json.dumps(payload),
        cwd=cfg.checkout,
        env=ENV,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if p.returncode:
        die(f"gh failed ({p.returncode}): {p.stderr.strip()}")
    if "--method" in args:
        time.sleep(1)  # GitHub's secondary limit is on the rate of writes
    return json.loads(p.stdout) if p.stdout.strip() else None


def viewer(cfg, _cache={}):
    """The account gh is authenticated as. One call, reused for the run."""
    if "login" not in _cache:
        _cache["login"] = gh(cfg, "api", "user")["login"]
    return _cache["login"]


def fingerprint(issue):
    """Detect concurrent edits between reading an issue and mutating it."""
    fields = {k: issue.get(k) for k in ("title", "body", "state")}
    fields["labels"] = sorted(x["name"] for x in issue["labels"])
    fields["assignees"] = sorted(a["login"] for a in issue.get("assignees") or [])
    fields["milestone"] = (issue.get("milestone") or {}).get("number")
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def comment_body(cfg, row):
    links = []
    for e in row["evidence"]:
        anchor = f"#L{e['line']}" + (f"-L{e['end']}" if e.get("end") else "")
        url = f"https://github.com/{cfg.repo}/blob/{cfg.sha}/{quote(e['path'], safe='/')}{anchor}"
        links.append(f"[{e['path']}:{e['line']}]({url})")
    body = (
        f"**Bug backlog triage — {cfg.date}**\n\n"
        f"**System:** {row['system']}  \n**Outcome:** {OUTCOMES[row['status']]}\n\n"
        f"{row['reason']}\n\n"
        f"**Current implementation evidence** (main `{cfg.sha[:8]}`): "
        + "; ".join(links)
        + ".\n\n"
        f"**Origin / history:** {row['history']}\n\n"
        f"**Next step:** {row['nextStep']}\n\n"
        "Current source was checked independently of historical comments and session status. "
        "A cited test is source evidence unless a fresh run is explicitly reported.\n\n"
        + cfg.marker
    )
    if len(body) > 65536:
        die(f"#{row['number']}: comment is {len(body)} chars; GitHub caps at 65536")
    return body


def check_row(cfg, row, known):
    """Everything that must be true of one decision record. Any failure stops the run."""
    n = row["number"]
    if row["status"] not in OUTCOMES:
        die(f"#{n}: unknown status {row['status']!r}")
    if not row.get("title"):
        die(f"#{n}: no issue title recorded — re-run the inventory")
    if not row.get("evidence"):
        die(f"#{n}: no evidence cited")
    for e in row["evidence"]:
        if git(cfg, "cat-file", "-e", f"{cfg.sha}:{e['path']}").returncode:
            die(f"#{n}: evidence path {e['path']!r} is not in {cfg.sha[:8]}")

    add, drop = set(row["labels"]), set(row.get("removeLabels", []))
    if not add | drop <= known:
        die(f"#{n}: labels not in the repo: {sorted((add | drop) - known)}")
    if add & drop:
        die(f"#{n}: {sorted(add & drop)} is in both labels and removeLabels")

    for f in ("system", "reason", "history", "nextStep"):
        if "@" in str(row.get(f, "")):
            die(f"#{n}: {f} contains '@' — a bulk comment must not ping; reword it")

    if bool(row.get("closureReason")) != (row["status"] in CLOSING):
        die(
            f"#{n}: status {row['status']!r} and closureReason "
            f"{row.get('closureReason')!r} disagree about closing"
        )
    if row.get("closureReason"):
        if row["closureReason"] not in CLOSE_REASONS:
            die(f"#{n}: closureReason must be one of {sorted(CLOSE_REASONS)}")
    elif len(add & cfg.triage_labels) != 1:
        die(f"#{n}: retained issues need exactly one triage label")

    try:
        comment_body(cfg, row)  # rendered here so a missing field cannot die mid-run
    except KeyError as missing:
        die(f"#{n}: record is missing {missing}")


def coverage(cfg, rows):
    """(issues open at the inventory that no manifest row accounts for, live count).

    An issue filed after the inventory was never in scope; demanding it be in
    the manifest would wedge every remaining row for nothing.
    """
    live = gh(
        cfg,
        "issue",
        "list",
        "--repo",
        cfg.repo,
        "--state",
        "open",
        "--label",
        cfg.label,
        "--limit",
        "1000",
        "--json",
        "number,createdAt",
    )
    if len(live) >= 1000:
        die(f"1000+ open {cfg.label} issues; the coverage check cannot see them all")
    open_at_inventory = {
        x["number"] for x in live if ts(x["createdAt"]) <= cfg.inventory_cutoff
    }
    return open_at_inventory - {r["number"] for r in rows}, len(live)


def preflight(cfg, rows):
    """Every check that can fail before a single mutation is sent."""
    origin = git(cfg, "remote", "get-url", "origin")
    want = cfg.repo.lower()
    url = origin.stdout.strip().removesuffix(".git").lower()
    if origin.returncode or not url.endswith((f"/{want}", f":{want}")):
        die(f"checkout's origin is {url or origin.stderr.strip()!r}, not {cfg.repo}")

    remote = git(cfg, "ls-remote", "origin", f"refs/heads/{cfg.branch}")
    if remote.returncode or not remote.stdout.split():
        die(f"no {cfg.branch} on the checkout's origin: {remote.stderr.strip()!r}")
    live = remote.stdout.split()[0]
    if live != cfg.sha:
        die(
            f"{cfg.branch} is now {live[:8]}, evidence cites {cfg.sha[:8]}"
            " — re-review before publishing"
        )

    label_page = gh(
        cfg, "label", "list", "--repo", cfg.repo, "--limit", "500", "--json", "name"
    )
    if len(label_page) >= 500:
        die("repo has 500+ labels; the label check would reject valid ones")
    known = {x["name"] for x in label_page}
    if cfg.label not in known:
        die(f"label {cfg.label!r} is not in the repo; coverage would pass vacuously")

    for row in rows:
        check_row(cfg, row, known)

    missing, _ = coverage(cfg, rows)
    if missing:
        die(f"open {cfg.label} issues absent from the manifest: {sorted(missing)}")

    stale = cfg.triage_labels - known
    if stale:
        die(f"triageLabels not in the repo: {sorted(stale)}")

    print(
        json.dumps(
            {
                "reviewed": len(rows),
                "close": [r["number"] for r in rows if r.get("closureReason")],
                "keep_open": sum(1 for r in rows if not r.get("closureReason")),
                "preflight": "PASS",
            },
            indent=2,
        )
    )


def plan(cfg, row, current):
    """The label set and PATCH body for one row. Pure, so it is testable alone."""
    want_closed = bool(row.get("closureReason"))
    labels = (
        ({x["name"] for x in current["labels"]} - cfg.triage_labels)
        - set(row.get("removeLabels", []))
    ) | set(row["labels"])
    if want_closed:
        labels -= cfg.triage_labels
    patch = {"labels": sorted(labels)}
    if want_closed:
        patch.update(state="closed", state_reason=row["closureReason"])
    return labels, patch


def publish(cfg, rows):
    for row in rows:
        number = row["number"]
        endpoint = f"repos/{cfg.repo}/issues/{number}"
        current = gh(cfg, "api", endpoint)
        # The number is the only join key, and /issues/N resolves pull requests
        # too. Refuse unless the row names the thing it was written about.
        if "pull_request" in current:
            die(f"#{number} is a pull request, not an issue")
        if current["title"] != row["title"]:
            die(
                f"#{number} is {current['title']!r}, the manifest says "
                f"{row['title']!r} — the row does not describe this issue"
            )
        want_closed = bool(row.get("closureReason"))

        pages = gh(
            cfg, "api", endpoint + "/comments?per_page=100", "--paginate", "--slurp"
        )
        existing = [
            c
            for page in pages
            for c in page
            if cfg.marker in c.get("body", "")
            and c.get("user", {}).get("login") == viewer(cfg)
        ]
        body = comment_body(cfg, row)

        # plan() reads the pre-comment snapshot, so it doubles as the "already
        # applied" test: a comment without its PATCH is still a pending mutation.
        labels, patch = plan(cfg, row, current)
        applied = bool(
            existing
            and {x["name"] for x in current["labels"]} == labels
            and (current["state"] == "closed") == want_closed
        )

        # Already in the planned state: re-PATCHing spends a write to change nothing.
        if applied:
            print(
                json.dumps(
                    {
                        "number": number,
                        "state": current["state"],
                        "status": row["status"],
                        "comment": existing[0]["html_url"],
                        "skipped": "already published",
                    }
                ),
                flush=True,
            )
            continue

        # Resuming after a partial run is fine; a surprise state change is not.
        if current["state"] != "open" and not (want_closed and existing):
            die(f"#{number} state changed outside this review")
        if (
            not applied
            and ts(current["updated_at"]) > cfg.inventory_cutoff
            and current["updated_at"] != cfg.rereviewed.get(number)
        ):
            die(
                f"#{number} changed after inventory ({current['updated_at']}); "
                f"re-read it, then add it to config.rereviewed with that timestamp"
            )

        before = fingerprint(current)
        if not existing:
            published = gh(
                cfg,
                "api",
                endpoint + "/comments",
                "--method",
                "POST",
                payload={"body": body},
            )
        elif len(existing) == 1 and existing[0]["body"] == body:
            published = existing[0]  # idempotent re-run
        else:
            die(f"#{number} already carries a conflicting triage comment")

        if fingerprint(gh(cfg, "api", endpoint)) != before:
            die(
                f"#{number} changed concurrently; the comment posted but labels/state did not"
            )

        changed = gh(cfg, "api", endpoint, "--method", "PATCH", payload=patch)
        if (
            changed["state"] != ("closed" if want_closed else "open")
            or {x["name"] for x in changed["labels"]} != labels
        ):
            die(f"#{number} result does not match the plan")

        print(
            json.dumps(
                {
                    "number": number,
                    "state": changed["state"],
                    "status": row["status"],
                    "comment": published["html_url"],
                }
            ),
            flush=True,
        )


def verify(cfg, rows, batch_size):
    """Read-only. One GraphQL call per batch instead of ~3 REST calls per issue."""
    results = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        fields = " ".join(
            f"i{r['number']}:issue(number:{r['number']})"
            "{number state stateReason labels(first:100){nodes{name}}"
            " comments(last:20){nodes{body url}}}"
            for r in batch
        )
        data = gh(
            cfg,
            "api",
            "graphql",
            payload={
                "query": f'query{{repository(owner:"{cfg.owner}",name:"{cfg.name}"){{{fields}}}}}'
            },
        )
        for row in batch:
            got = data["data"]["repository"][f"i{row['number']}"]
            if len(got["labels"]["nodes"]) >= 100:
                die(f"#{row['number']} has 100+ labels; verify cannot see them all")
            labels = {x["name"] for x in got["labels"]["nodes"]}
            mine = [c for c in got["comments"]["nodes"] if cfg.marker in c["body"]]
            want_closed = bool(row.get("closureReason"))
            wanted_triage = (
                set() if want_closed else set(row["labels"]) & cfg.triage_labels
            )
            ok = (
                got["state"] == ("CLOSED" if want_closed else "OPEN")
                and labels & cfg.triage_labels == wanted_triage
                and set(row["labels"]) - cfg.triage_labels <= labels
                and not set(row.get("removeLabels", [])) & labels
                and len(mine) == 1
                and mine[0]["body"] == comment_body(cfg, row)
            )
            if want_closed:
                ok = ok and got["stateReason"] == row["closureReason"].upper()
            results.append(
                {
                    "number": row["number"],
                    "verified": ok,
                    "state": got["state"],
                    "stateReason": got["stateReason"],
                    "labels": sorted(labels),
                    "comment": mine[0]["url"] if mine else None,
                }
            )
        print(
            json.dumps(
                {
                    "batch": start // batch_size + 1,
                    "verified": sum(r["verified"] for r in results),
                    "checked": len(results),
                }
            ),
            flush=True,
        )

    bad = [r for r in results if not r["verified"]]
    if bad:
        die(json.dumps({"mismatches": bad}, indent=2))

    unreviewed, open_labelled = coverage(cfg, rows)
    if unreviewed:
        die(f"unreviewed open {cfg.label} issues: {sorted(unreviewed)}")

    print(
        json.dumps(
            {
                "verified": len(results),
                "closed": sum(r["state"] == "CLOSED" for r in results),
                "open": sum(r["state"] == "OPEN" for r in results),
                f"open_{cfg.label}_labels": open_labelled,
                "results": results,
            }
        )
    )


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("command", choices=["preflight", "publish", "verify"])
    ap.add_argument("--config", default="triage.config.json")
    ap.add_argument(
        "--batch-size", type=int, default=24, help="verify: issues per GraphQL call"
    )
    args = ap.parse_args()
    if not 1 <= args.batch_size <= 50:
        ap.error("--batch-size must be between 1 and 50")

    cfg = Config(args.config)
    rows = cfg.rows()
    if args.command == "preflight":
        preflight(cfg, rows)
    elif args.command == "publish":
        preflight(cfg, rows)
        publish(cfg, rows)
    else:
        verify(cfg, rows, args.batch_size)


if __name__ == "__main__":
    main()
