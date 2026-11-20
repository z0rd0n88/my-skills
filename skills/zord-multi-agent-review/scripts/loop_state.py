#!/usr/bin/env python3
"""Round-state carrier for zord-multi-agent-review loop runs.

The loop coordinator persists one JSON file per loop at
`<git-root>/.claude/reviews/pr-<n>/loop-state.json` (§10.1). This script is the
only thing that turns that file into text a reviewer sees, so the carry-forward
is structural *by construction*: it renders which review shapes earlier rounds
used and which specific findings a verifier positively confirmed, and it never
renders a deferral or a fix outcome. Naming a finding to suppress it makes it
more salient, not less (measured; z0rd0n88/ThinkTime: ThinkTime/versus/fixtures/review-round2-carryforward).

    python3 loop_state.py check <loop-state.json> --pr <n> [--resume-stopped]
                          [--remote-head <oid>]
        Prints one line: RESUME round=<next>, COMPLETE <reason>, STOPPED
        <reason>, STALE <reason>, or NONE. Run from inside the repository.

        COMPLETE when `iterations_completed` already reached the stored
        `max_iterations` — the loop spent its budget, so there is no round to
        resume; a further round needs a fresh loop with a new budget.

        STALE also when a checkpoint written after a completed round is
        missing `prior_findings_fingerprints` — the coordinator cannot
        restore its regression-detection history from it, so a recurring
        finding would resume as a brand-new one.

        STALE when the recorded head is not the EXACT current HEAD (not merely
        an ancestor of it — commits landed since the checkpoint may have
        changed a location a verified/refuted entry claims settled) or the PR
        number differs.

        STALE when --remote-head <oid> is given and differs from the
        checkpoint: the local worktree can sit at the checkpoint commit while
        another actor moves the PR branch, so resume would run against stale
        code. The script never fetches — the coordinator passes the OID it
        already got from `gh pr view`, keeping this check offline and
        deterministic.

        STALE when the index or working tree is dirty, untracked files
        included except those under the state file's own directory — HEAD can
        match everywhere while an interrupted round left an applier's edits
        uncommitted, or left a new source or test file it never staged, and
        resuming would commit them under the next finding. A `git status`
        that cannot be read is STALE too: the guard fails closed. This check
        runs FIRST, ahead of the pr and head comparisons: a dirty tree is
        unsafe whatever else is stale, and a head-mismatch STALE sends the
        coordinator off to start a fresh mutating loop over those edits.

        COMPLETE when `status` is `"approved"` — the loop ended on an accepted
        APPROVE, which is terminal, not a round to redo.

        STOPPED when the state's `stop_reason` is set — the loop ended on a
        safety stop, not an interruption, and resuming without a human
        deciding it is safe would continue a mutating loop past a condition
        that exists precisely to get a human's judgment. Pass
        --resume-stopped only after that judgment has been made.

    python3 loop_state.py render-prelude <loop-state.json> --round <N>
                          [--caller-prelude <path>]
        Prints the markdown to pass as --prompt-prelude to round N's inner
        pass: the caller's prelude verbatim (if any), then `## ROUND STATE`,
        then the refuted-findings exclusion list when refutation ran.

        Exits 2 without printing when the render exceeds PRELUDE_CAP bytes —
        the inner pass hard-fails on an oversized --prompt-prelude, so the
        refusal must happen before the round is dispatched, not after.

    python3 loop_state.py stamp <loop-state.json> [--round-start <oid>]
        Binds every `verified_fixed` / `refuted` entry that has no
        `settled_head` yet, and rewrites the state file's top-level `head` to
        the current commit. Refuses (exit non-zero) when anything outside the
        checkpoint directory is dirty: binding an entry while uncommitted
        edits exist would record a fix at a commit that does not contain it.

        `verified_fixed` binds to the CURRENT commit — the fix was verified
        after it was applied, so the post-fix tree is the tree that was
        examined.

        `refuted` binds to --round-start, the HEAD the round's reviewers and
        refuters actually read (defaults to current HEAD when the flag is
        omitted). Refuters run BEFORE the round's fixes, so binding them to
        the post-fix commit would launder a refutation: a same-round fix can
        make a previously false claim true, yet the next round would receive
        it under DO NOT RE-RAISE. Bound to the round-start commit instead, a
        round that committed anything expires its own refutations into
        RE-EXAMINE, and a round that committed nothing (round start == HEAD)
        keeps them excluded.

        `blob` comes from that same commit (`git rev-parse <oid>:<file>`) —
        the file as COMMITTED, never the working-tree bytes; null when the
        file is absent there, which leaves the entry re-examined.

        Run this as the LAST step of a round, after the round's fix commits
        and push exist (§10.5 step 7). Stamping `verified_fixed` at
        verification time — before those commits — binds entries to the
        pre-fix HEAD, so the round's own commit immediately expires every fix
        it just landed.

        The checkpoint is written atomically (temp file, fsync, `os.replace`),
        so an interrupted write can never leave the loop's only resume record
        as half a JSON document.

    python3 loop_state.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = 1
KNOWN_AXES = ("code", "specs-docs", "tests", "config", "history")
# §11's `--prompt-prelude` limit; the inner pass hard-fails above it.
PRELUDE_CAP = 16384
# Keys the coordinator stores for its own resume; NEVER rendered to a reviewer.
COORDINATOR_ONLY = ("deferred", "fix_outcomes", "fix_totals", "refutation_totals")


class CorruptState(Exception):
    """The checkpoint on disk is not readable JSON — an explicit state.

    The loop's only resume record is one file. A truncated or mis-encoded one
    has to surface as a recoverable status, not as an uncaught parse error:
    the coordinator answers STALE by starting a fresh loop, and answers a
    traceback by dying.
    """


def save(path: Path, state: dict) -> None:
    """Replace `path` with `state` atomically.

    Write a sibling temp file in the same directory, fsync it, then
    `os.replace` — a rename within one directory is atomic, so an interrupt,
    a full disk, or an I/O error leaves the previous checkpoint intact instead
    of half a JSON document that the next `check` cannot parse.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CorruptState(
            f"checkpoint is corrupt ({exc}) — restore from git or start a fresh loop"
        ) from None
    if state.get("schema") != SCHEMA:
        sys.exit(
            f"loop_state: unsupported schema {state.get('schema')!r} (want {SCHEMA})"
        )
    return state


def validate(state: dict) -> str | None:
    """Field-level integrity of a checkpoint; a reason string or None."""
    if int(state.get("iterations_completed", 0)) >= 1 and not isinstance(
        state.get("prior_findings_fingerprints"), list
    ):
        return (
            "STALE prior_findings_fingerprints missing — a checkpoint written "
            "after a completed round must carry the regression-detection "
            "history; without it a recurring finding resumes as new and the "
            "loop mutates again instead of stopping for a human"
        )
    return None


def _repo_root() -> Path | None:
    """Absolute path of the repository root, or None outside a git worktree."""
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def blob_of(file: str, rev: str = "HEAD") -> str | None:
    """Blob hash of `file` as COMMITTED IN `rev`, or None if absent there.

    Deliberately not `git hash-object` on the working-tree path: the settled
    bindings claim a committed-tree guarantee, so a post-commit hook, an
    external editor, or an interrupted round must not be able to get its
    uncommitted bytes recorded as the state a finding was verified against.
    The path is resolved from the repository root (`<rev>:<path>` is always
    root-relative), so the result does not depend on the caller's cwd. `rev`
    defaults to HEAD; `stamp` passes the round-start commit for refutations,
    which were examined against that tree.
    """
    if not file:
        return None
    rel = Path(file)
    if rel.is_absolute():
        root = _repo_root()
        if root is None:
            return None
        try:
            rel = rel.resolve().relative_to(root.resolve())
        except ValueError:
            return None
    r = subprocess.run(
        ["git", "rev-parse", f"{rev}:{rel.as_posix()}"], capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def current_head() -> str | None:
    """Current HEAD oid, or None outside a git worktree."""
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def partition_by_blob(
    entries: list[dict], *, head: str | None
) -> tuple[list[dict], list[dict]]:
    """Split entries into (still bound, expired).

    An entry stays settled only while BOTH bindings hold: the file it was
    settled against still hashes to the recorded `blob`, and it was settled on
    the current commit (`settled_head`). The blob binds one cited file, but a
    finding's validity depends on files it never cites — middleware, config, a
    caller — and a commit touching one of those leaves the cited blob
    untouched. Those dependency sets are not knowable here, so an entry
    settled on any other commit is reopened. The binding is per entry, not per
    checkpoint: the coordinator rewrites the state's global `head` every round
    while keeping older entries, so a global compare would keep a round-1
    exclusion alive through every later round.

    A missing `blob` or `settled_head` (legacy entry) never counts as bound —
    an unbound claim would silence a later round forever.
    """
    bound: list[dict] = []
    expired: list[dict] = []
    for e in entries:
        recorded = e.get("blob")
        settled = e.get("settled_head")
        ok = bool(recorded) and recorded == blob_of(e.get("file", ""))
        ok = ok and bool(settled) and bool(head) and settled == head
        (bound if ok else expired).append(e)
    return bound, expired


def _checkpoint_prefix(state_path: Path) -> str | None:
    """`git status` path prefix of the directory the state file lives in.

    The loop's own checkpoint artifacts are untracked by design and always
    present; everything else untracked is an interrupted round's work. None
    when the directory is the repo root or outside it — nothing to exempt.
    """
    root = _repo_root()
    if root is None:
        return None
    try:
        rel = state_path.resolve().parent.relative_to(root.resolve())
    except ValueError:
        return None
    return None if rel.as_posix() == "." else f"{rel.as_posix()}/"


def dirty_paths(state_path: Path) -> list[str] | None:
    """`git status` lines for everything dirty outside the checkpoint dir.

    None when `git status` cannot be read at all — callers fail closed on it.
    Shared by `check()` (resume) and `stamp()` (binding): both record or trust
    a committed-tree claim, and neither is safe over an interrupted round's
    uncommitted edits.
    """
    r = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    skip = _checkpoint_prefix(state_path)
    return [
        ln
        for ln in r.stdout.splitlines()
        if ln.strip() and not (skip and ln[3:].lstrip('"').startswith(skip))
    ]


def check(
    path: Path, pr: str, *, resume_stopped: bool = False, remote_head: str | None = None
) -> str:
    if not path.exists():
        return "NONE"
    # FIRST, before any head or pr comparison: a dirty tree is unsafe however
    # else the checkpoint is stale. A head mismatch that returned early here
    # was reported as a generic STALE, and the coordinator answers STALE by
    # starting a fresh mutating loop — over the interrupted round's edits.
    paths = dirty_paths(path)
    if paths is None:
        return (
            "STALE cannot read git status — the dirty-tree guard could not "
            "run, and resuming past an unreadable tree would commit an "
            "interrupted round's edits under the next finding"
        )
    if paths:
        return (
            f"STALE working tree or index is dirty ({len(paths)} paths, "
            "untracked included) — an interrupted round left uncommitted "
            "edits, possibly a new source or test file never staged; inspect "
            "and commit or discard them, then start a fresh loop"
        )
    try:
        state = load(path)
    except CorruptState as exc:
        return f"STALE {exc}"
    if str(state.get("pr")) != str(pr):
        return f"STALE pr mismatch: file has {state.get('pr')!r}, run is {pr!r}"
    head = state.get("head")
    if not head:
        return "STALE no head recorded"
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    )
    if current.returncode != 0:
        return "STALE cannot resolve current HEAD (not a git worktree?)"
    current_head = current.stdout.strip()
    if current_head != head:
        return (
            f"STALE recorded head {head[:12]} does not exactly match current "
            f"HEAD {current_head[:12]} — commits landed since the checkpoint "
            "may have changed what a verified-fixed or refuted entry claims "
            "is settled; start a fresh loop rather than trust stale scope"
        )
    if remote_head and remote_head != head:
        return (
            f"STALE remote PR head {remote_head[:12]} differs from checkpoint "
            f"{head[:12]} — the PR branch moved (fetch/force-push by another "
            "actor); start a fresh loop"
        )
    invalid = validate(state)
    if invalid:
        return invalid
    stop_reason = state.get("stop_reason")
    if stop_reason and not resume_stopped:
        return (
            f"STOPPED {stop_reason} — resume refused. This loop ended on a "
            "safety stop, not an interruption; auto-resuming would continue "
            "a mutating loop past a condition that exists to get a human "
            "decision. Re-run with --resume-stopped only after confirming "
            "it is safe to continue, or start a fresh loop instead."
        )
    done = int(state.get("iterations_completed", 0))
    if state.get("status") == "approved":
        return (
            f"COMPLETE approved at round {done} — nothing to resume; the loop "
            "ended on an accepted APPROVE, not an interruption"
        )
    max_it = int(state.get("max_iterations", 1))
    if done >= max_it:
        return (
            f"COMPLETE max_iterations={max_it} reached — nothing to resume; "
            "start a fresh loop (new budget) if more rounds are wanted"
        )
    return f"RESUME round={done + 1}"


def stamp(path: Path, round_start: str | None = None) -> str:
    """Bind every not-yet-stamped settled entry to the commit it was judged at.

    The coordinator records `verified_fixed` / `refuted` entries at
    verification time (§10.4b), which is BEFORE the round's fix commits exist.
    So the entries are written unbound and this subcommand binds them
    afterwards, as the round's final operation — but the two kinds were judged
    against different trees, and they bind to different commits:

    * `verified_fixed` → current HEAD. The verifier ran after the fix, so the
      post-fix tree is the tree it examined. Binding these at verification
      time instead would stamp the pre-fix HEAD, and the round's own commit
      would expire every fix it just landed.
    * `refuted` → `round_start`, the HEAD the reviewers and refuters read
      (current HEAD when not given). Refutation happens before any fix, so
      binding a refutation to the post-fix commit would launder it: a
      same-round fix can make a previously false claim true, and the next
      round would still receive it under DO NOT RE-RAISE. Bound to the
      round-start commit, partition_by_blob reopens it as RE-EXAMINE the
      moment the round commits anything, and keeps it excluded when the round
      committed nothing.

    `blob` is read from that commit, not from the working tree, and a dirty
    tree refuses the stamp outright — otherwise an edit that never reached the
    commit would be recorded as the state the finding was judged against. A
    file missing there leaves `blob` null, which partition_by_blob treats as
    unbound — the entry is re-judged rather than silently excluded.
    """
    state = load(path)
    dirty = dirty_paths(path)
    if dirty is None:
        sys.exit(
            "loop_state: cannot read git status — refusing to stamp; the "
            "bindings claim a committed tree and that cannot be confirmed"
        )
    if dirty:
        sys.exit(
            f"loop_state: refusing to stamp with a dirty working tree "
            f"({len(dirty)} paths, untracked included). Stamping binds each "
            "entry to HEAD, so uncommitted edits would be recorded as fixed "
            "at a commit that does not contain them. Commit or discard them "
            "(§10.5 step 7 runs stamp AFTER the round's commits), then re-run."
        )
    head = current_head()
    if not head:
        sys.exit("loop_state: cannot resolve HEAD (not a git worktree?)")
    start = head
    if round_start:
        r = subprocess.run(
            ["git", "rev-parse", f"{round_start}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0 or not r.stdout.strip():
            sys.exit(
                f"loop_state: --round-start {round_start!r} does not resolve to "
                "a commit in this repository; pass the OID the round started "
                "from, not a branch name that has since moved"
            )
        start = r.stdout.strip()
    stamped = 0
    for key, rev in (("verified_fixed", head), ("refuted", start)):
        for e in state.get(key) or []:
            if e.get("settled_head"):
                continue
            e["settled_head"] = rev
            e["blob"] = blob_of(e.get("file", ""), rev)
            stamped += 1
    state["head"] = head
    save(path, state)
    return (
        f"STAMPED {stamped} entries (fixes at {head[:12]}, refutations at {start[:12]})"
    )


def render(state: dict, round_no: int, caller_prelude: str | None) -> str:
    head = current_head()
    out: list[str] = []
    if caller_prelude:
        out.append(caller_prelude.rstrip("\n"))
        out.append("")
    pr = state.get("pr", "?")
    out += [
        "## ROUND STATE (carried from earlier rounds: scope, never answers)",
        "",
        f"This is round {round_no} of an iterative review loop on PR #{pr}. Earlier "
        "rounds reviewed earlier states of the code and applied fixes; HEAD is the "
        "result. Judge the code as it stands now. A fix an earlier round claimed is "
        "not evidence that it worked, and a change it made can itself have "
        "introduced a new defect.",
        "",
        "### Shapes already used",
    ]
    rounds = state.get("rounds", [])
    if not rounds:
        out.append("- none recorded")
    for r in rounds:
        axes = [a for a in r.get("axes", []) if a in KNOWN_AXES]
        files = r.get("files_read", [])
        line = f"- Round {r.get('round')}: roster {', '.join(r.get('roster', [])) or 'unknown'}"
        line += f"; axes read: {', '.join(axes) or 'unknown'}"
        if files:
            line += f"; files opened: {', '.join(files)}"
        out.append(line)
    out += [
        "",
        "This round MUST use a shape no earlier round ran, and MUST state it in the "
        "report's `## Shape` block. Rotation is not a reshuffle of the same roster. "
        "Prefer, in order: (a) merge two axes earlier rounds read separately, so a "
        "claim made on one can be checked against the other; a defect visible only "
        "as a contradiction between two sources is invisible to every lens that "
        "reads one of them alone. (b) Hunt by defect class, not by instance: every "
        "fix an earlier round landed is a hypothesis that the same class exists at "
        "that site's analogues, so check the analogues rather than the fixed site.",
        "",
        "### Verifier output",
        "",
        "An automated verifier ran against each round's fixes. It confirms only what "
        "it could prove; anything not listed remains unverified.",
        "",
    ]
    verified, stale = partition_by_blob(state.get("verified_fixed", []), head=head)

    def line(v: dict, tag: str) -> str:
        return (
            f"{tag}   {v.get('symbol')}   {v.get('file')}   "
            f"finding: {v.get('finding', '(not recorded)')}   "
            f"evidence: {v.get('evidence', '')}   (round {v.get('round')})"
        )

    if verified:
        out.append("```")
        for v in verified:
            out.append(line(v, "VERIFIED-FIXED"))
        out.append("```")
        out += [
            "",
            "Only the EXACT finding named on each line above is out of scope for "
            "this round. Verification confirms that one claim, never every "
            "invariant in its symbol — a different defect in the same function, "
            "class, or file is still in scope even when it sits beside a "
            "VERIFIED-FIXED line. Everything else is in scope regardless of "
            "whether an earlier round touched it.",
        ]
    else:
        out.append(
            "No finding has been verifier-confirmed. Nothing is out of scope; "
            "everything an earlier round touched is in scope."
        )
    if stale:
        out += [
            "",
            "### Re-verify (file changed since verification)",
            "",
            "Each entry below was confirmed fixed against a file state that no "
            "longer exists — the file changed, or was never bound to one. The "
            "verification no longer holds, so these EXACT findings are back IN "
            "scope: a later fix can reintroduce a defect an earlier round "
            "closed. Re-check each one from the current code; do not treat the "
            "earlier evidence as settling it.",
            "",
            "```",
        ]
        for v in stale:
            out.append(line(v, "RE-VERIFY"))
        out.append("```")
    refuted, reopened = partition_by_blob(state.get("refuted", []), head=head)

    def refuted_line(f: dict) -> str:
        return (
            f"- {f.get('severity')} {f.get('location')} — {f.get('claim')} "
            f"(round {f.get('round')}; refuters: {f.get('rationale')})"
        )

    if refuted:
        out += ["", "## REFUTED IN EARLIER ROUNDS — DO NOT RE-RAISE", ""]
        out += [refuted_line(f) for f in refuted]
        out += [
            "",
            "Raise one of these again only if the code under it has changed since "
            "the round that dropped it.",
        ]
    if reopened:
        out += [
            "",
            "## REFUTATIONS THAT NO LONGER HOLD — RE-EXAMINE",
            "",
            "Each claim below was refuted against a file state that no longer "
            "exists — the file changed, or the entry was never bound to one. A "
            "later fix can have changed or reintroduced the behaviour the "
            "refuters disproved, so these are NOT excluded: judge each one "
            "against the current code, not against the earlier rationale.",
            "",
        ]
        out += [refuted_line(f) for f in reopened]
    return "\n".join(out) + "\n"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)


def _check_selftest() -> dict[str, bool]:
    """check()'s git-dependent branches, against a throwaway repo."""
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _run(["git", "init", "-q"], repo)
        _run(["git", "config", "user.email", "t@example.com"], repo)
        _run(["git", "config", "user.name", "t"], repo)
        (repo / "f").write_text("1")
        _run(["git", "add", "f"], repo)
        _run(["git", "commit", "-q", "-m", "one"], repo)
        head1 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
        (repo / "f").write_text("2")
        _run(["git", "add", "f"], repo)
        _run(["git", "commit", "-q", "-m", "two"], repo)
        head2 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

        ckpt = repo / ".claude" / "reviews" / "pr-1"
        ckpt.mkdir(parents=True)

        def check_in(state: dict, run_pr=None, **kw) -> str:
            p = ckpt / "loop-state.json"
            p.write_text(json.dumps(state))
            import os

            cwd = os.getcwd()
            os.chdir(repo)
            try:
                return check(
                    p, run_pr if run_pr is not None else state.get("pr", 1), **kw
                )
            finally:
                os.chdir(cwd)

        r = check(repo / "nope.json", 1)
        checks["missing file is NONE"] = r == "NONE"

        base = {
            "schema": SCHEMA,
            "pr": 1,
            "head": head2,
            "max_iterations": 3,
            "iterations_completed": 1,
            "prior_findings_fingerprints": [
                {"fingerprint": "abc", "claimed_fixed": True, "round": 1}
            ],
        }

        r = check_in(base)
        checks["exact head match resumes"] = r == "RESUME round=2"

        r = check_in({**base, "head": head1})
        checks["ancestor-but-not-exact head is STALE, not RESUME"] = (
            r.startswith("STALE") and "does not exactly match" in r
        )

        r = check_in({"schema": SCHEMA, "pr": 2, "head": head2}, run_pr=1)
        checks["pr mismatch is STALE"] = r.startswith("STALE pr mismatch")

        stopped = {
            **base,
            "max_iterations": 5,
            "iterations_completed": 3,
            "stop_reason": "STOPPED_CRITICAL_UNFIXABLE",
        }
        r = check_in(stopped)
        checks["terminal stop blocks resume by default"] = r.startswith("STOPPED")

        r = check_in(stopped, resume_stopped=True)
        checks["--resume-stopped overrides the block"] = r == "RESUME round=4"

        r = check_in({**base, "iterations_completed": 1, "max_iterations": 1})
        checks["cap-exhausted default loop is COMPLETE, not RESUME"] = r.startswith(
            "COMPLETE max_iterations=1 reached"
        )

        r = check_in({**base, "iterations_completed": 1, "max_iterations": 3})
        checks["budget left still resumes"] = r == "RESUME round=2"

        r = check_in(base, remote_head=head2)
        checks["--remote-head matching the checkpoint resumes"] = r == "RESUME round=2"

        r = check_in(base, remote_head=head1)
        checks["--remote-head that moved under us is STALE"] = r.startswith(
            "STALE remote PR head"
        )

        no_fps = {k: v for k, v in base.items() if k != "prior_findings_fingerprints"}
        r = check_in(no_fps)
        checks["missing prior_findings_fingerprints is STALE"] = r.startswith(
            "STALE prior_findings_fingerprints missing"
        )

        r = check_in({**base, "status": "in_progress"})
        checks["status in_progress still resumes"] = r == "RESUME round=2"

        r = check_in({**base, "status": "approved"})
        checks["approved checkpoint is COMPLETE, not RESUME"] = r.startswith(
            "COMPLETE approved at round 1"
        )

        # A dirty tracked file refuses resume even when every head matches.
        (repo / "f").write_text("uncommitted edit from a dead round")
        r = check_in(base)
        checks["dirty working tree refuses resume"] = r.startswith(
            "STALE working tree or index is dirty"
        )
        # The head mismatch must NOT short-circuit the dirty check: a generic
        # head-mismatch STALE tells the coordinator to start a fresh mutating
        # loop, which would then run over these uncommitted edits.
        r = check_in({**base, "head": head1})
        checks["dirty tree is reported ahead of a head mismatch"] = (
            r.startswith("STALE working tree or index is dirty")
            and "does not exactly match" not in r
        )
        _run(["git", "checkout", "--", "f"], repo)
        r = check_in(base)
        checks["clean tree resumes again"] = r == "RESUME round=2"

        # An applier created a new source/test file and the session died
        # before it was staged: invisible to --untracked-files=no.
        (repo / "NewThingTest.kt").write_text("class NewThingTest")
        r = check_in(base)
        checks["untracked source file refuses resume"] = r.startswith(
            "STALE working tree or index is dirty"
        )
        (repo / "NewThingTest.kt").unlink()

        # The loop's own checkpoint artifacts are untracked by design and must
        # not refuse the resume they exist to enable.
        (ckpt / "prelude-round-2.md").write_text("## ROUND STATE")
        r = check_in(base)
        checks["untracked checkpoint artifacts still resume"] = r == "RESUME round=2"

        # render(): a verified entry is bound to the blob it was verified against.
        import os

        cwd = os.getcwd()
        os.chdir(repo)
        try:
            blob = blob_of("f")
            entry = {
                "symbol": "s",
                "file": "f",
                "finding": "round-1 defect",
                "evidence": "e",
                "round": 1,
                "blob": blob,
                "settled_head": head2,
            }
            st = {"schema": SCHEMA, "pr": 1, "head": head2, "verified_fixed": [entry]}
            same = render(st, 2, None)
            checks["entry settled at current HEAD stays VERIFIED-FIXED"] = (
                "VERIFIED-FIXED   s" in same
                and "Only the EXACT finding" in same
                and "RE-VERIFY" not in same
            )
            older = {**st, "verified_fixed": [{**entry, "settled_head": head1}]}
            checks["entry settled on an older commit is reopened"] = (
                "RE-VERIFY   s" in render(older, 2, None)
                and "VERIFIED-FIXED" not in render(older, 2, None)
            )
            legacy = {k: v for k, v in entry.items() if k != "settled_head"}
            checks["entry with no settled_head is reopened"] = (
                "RE-VERIFY   s" in render({**st, "verified_fixed": [legacy]}, 2, None)
            )

            # Round 3's view: round 2 committed a file the finding never
            # cites, leaving the cited blob untouched. The checkpoint's global
            # `head` is rewritten to head3 every round, so only the per-entry
            # settled_head can reopen this.
            (repo / "dep").write_text("uncited middleware")
            _run(["git", "add", "dep"], repo)
            _run(["git", "commit", "-q", "-m", "round 2: uncited dependency"], repo)
            head3 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            r3 = render({**st, "head": head3}, 3, None)
            checks["round-2 commit to an uncited file reopens a round-1 entry"] = (
                blob_of("f") == blob
                and head3 != head2
                and "RE-VERIFY   s" in r3
                and "VERIFIED-FIXED" not in r3
            )

            # refuted entries expire on the same two bindings as verified
            # ones. Every file state below is COMMITTED: blob_of reads HEAD,
            # so an uncommitted edit is invisible to the binding by design.
            (repo / "g").write_text("g1")
            _run(["git", "add", "g"], repo)
            _run(["git", "commit", "-q", "-m", "add g"], repo)
            head4 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            ref = {
                "severity": "HIGH",
                "location": "g:1",
                "claim": "c",
                "rationale": "r",
                "round": 1,
                "file": "g",
                "blob": blob_of("g"),
                "settled_head": head4,
            }
            rst = {"schema": SCHEMA, "pr": 1, "head": head4, "refuted": [ref]}
            t = render(rst, 2, None)
            checks["refuted + unchanged file at settled head stays excluded"] = (
                "DO NOT RE-RAISE" in t and "RE-EXAMINE" not in t and "HIGH g:1" in t
            )
            t = render({**rst, "refuted": [{**ref, "settled_head": head3}]}, 2, None)
            checks["refuted settled on an older commit is reopened"] = (
                "RE-EXAMINE" in t and "DO NOT RE-RAISE" not in t
            )
            (repo / "g").write_text("g2")
            _run(["git", "add", "g"], repo)
            _run(["git", "commit", "-q", "-m", "change g"], repo)
            head5 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            t = render({**rst, "refuted": [{**ref, "settled_head": head5}]}, 2, None)
            checks["refuted expires when its committed file changes"] = (
                "RE-EXAMINE" in t and "DO NOT RE-RAISE" not in t and "HIGH g:1" in t
            )
            unbound = {k: v for k, v in ref.items() if k != "blob"}
            t = render({"schema": SCHEMA, "pr": 1, "refuted": [unbound]}, 2, None)
            checks["refuted with no blob is re-examined, not excluded"] = (
                "RE-EXAMINE" in t and "DO NOT RE-RAISE" not in t
            )

            # An uncommitted rewrite of a cited file does NOT move the blob —
            # the binding is to the committed tree, not to the editor's buffer.
            (repo / "f").write_text("uncommitted scratch")
            checks["blob_of ignores uncommitted working-tree bytes"] = (
                blob_of("f") == blob
            )
            _run(["git", "add", "f"], repo)
            _run(["git", "commit", "-q", "-m", "round 2 rewrote f"], repo)
            head6 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            changed = render(
                {**st, "verified_fixed": [{**entry, "settled_head": head6}]}, 3, None
            )
            checks["committed rewrite reopens the finding for re-verification"] = (
                "RE-VERIFY   s" in changed
                and "round-1 defect" in changed
                and "VERIFIED-FIXED" not in changed
                and "Nothing is out of scope" in changed
            )
            (repo / "f").unlink()
            _run(["git", "add", "-u", "f"], repo)
            _run(["git", "commit", "-q", "-m", "delete f"], repo)
            head7 = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            gone = render(
                {**st, "verified_fixed": [{**entry, "settled_head": head7}]}, 3, None
            )
            checks["deleted file reopens the finding too"] = "RE-VERIFY   s" in gone
        finally:
            os.chdir(cwd)
    return checks


def _stamp_selftest() -> dict[str, bool]:
    """The real round lifecycle: fix in a dirty tree -> commit -> stamp.

    This is the case the old fixture missed by handing the entry a
    settled_head that was already the post-commit HEAD. Here nothing is
    pre-bound, exactly as §10.4b now records it.
    """
    import os

    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _run(["git", "init", "-q"], repo)
        _run(["git", "config", "user.email", "t@example.com"], repo)
        _run(["git", "config", "user.name", "t"], repo)
        (repo / "f").write_text("buggy")
        (repo / "h").write_text("doomed")
        _run(["git", "add", "f", "h"], repo)
        _run(["git", "commit", "-q", "-m", "base"], repo)
        ckpt = repo / ".claude" / "reviews" / "pr-1"
        ckpt.mkdir(parents=True)
        p = ckpt / "loop-state.json"
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            # Round 1: the applier edits f; the tree is dirty when §10.4b runs.
            (repo / "f").write_text("fixed")
            entry = {
                "symbol": "s",
                "file": "f",
                "finding": "round-1 defect",
                "evidence": "e",
                "round": 1,
            }
            p.write_text(
                json.dumps({"schema": SCHEMA, "pr": 1, "verified_fixed": [entry]})
            )
            # §10.5: commit the fix, then stamp as the round's last operation.
            _run(["git", "add", "f"], repo)
            _run(["git", "commit", "-q", "-m", "fix(s): round 1"], repo)
            stamp(p)
            st = load(p)
            head_after_fix = current_head()
            checks["stamp binds the entry to the post-commit HEAD"] = (
                st["verified_fixed"][0]["settled_head"] == head_after_fix
                and st["head"] == head_after_fix
                and st["verified_fixed"][0]["blob"] == blob_of("f")
            )
            r2 = render(st, 2, None)
            checks["committed fix renders VERIFIED-FIXED in round 2"] = (
                "VERIFIED-FIXED   s" in r2 and "RE-VERIFY" not in r2
            )
            # A later round's commit to an unrelated file still reopens it.
            (repo / "other").write_text("round 2 work")
            _run(["git", "add", "other"], repo)
            _run(["git", "commit", "-q", "-m", "round 2"], repo)
            r3 = render(st, 3, None)
            checks["a later commit still reopens a stamped entry"] = (
                "RE-VERIFY   s" in r3 and "VERIFIED-FIXED" not in r3
            )
            # A file deleted before the stamp gets a null blob -> re-verify.
            (repo / "h").unlink()
            _run(["git", "add", "-u", "h"], repo)
            _run(["git", "commit", "-q", "-m", "delete h"], repo)
            p.write_text(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "pr": 1,
                        "verified_fixed": [{**entry, "file": "h"}],
                    }
                )
            )
            stamp(p)
            gone = load(p)
            checks["stamp leaves a deleted file's blob null"] = (
                gone["verified_fixed"][0]["blob"] is None
            )
            checks["deleted-file entry renders RE-VERIFY"] = "RE-VERIFY   s" in render(
                gone, 2, None
            )
            # Refuted entries stamp on the same pass; already-stamped ones
            # keep the head they were bound to.
            p.write_text(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "pr": 1,
                        "refuted": [
                            {
                                "severity": "HIGH",
                                "location": "f:1",
                                "claim": "c",
                                "rationale": "r",
                                "round": 1,
                                "file": "f",
                            },
                            {
                                "severity": "LOW",
                                "location": "f:2",
                                "claim": "old",
                                "rationale": "r",
                                "round": 1,
                                "file": "f",
                                "settled_head": head_after_fix,
                                "blob": "keepme",
                            },
                        ],
                    }
                )
            )
            stamp(p)
            ref = load(p)["refuted"]
            checks["stamp binds unstamped refuted entries"] = (
                ref[0]["settled_head"] == current_head()
            )
            checks["stamp never rebinds an already-stamped entry"] = (
                ref[1]["settled_head"] == head_after_fix and ref[1]["blob"] == "keepme"
            )

            def fresh_verified() -> None:
                p.write_text(
                    json.dumps(
                        {"schema": SCHEMA, "pr": 1, "verified_fixed": [dict(entry)]}
                    )
                )

            head_blob = _run(["git", "rev-parse", "HEAD:f"], repo).stdout.strip()
            fresh_verified()
            stamp(p)
            checks["stamp records the blob HEAD has, not hash-object"] = (
                load(p)["verified_fixed"][0]["blob"] == head_blob
            )
            # A post-commit hook (or any external edit) between the commit and
            # the stamp must not get its bytes recorded as VERIFIED-FIXED at a
            # commit that never contained them.
            (repo / "f").write_text("post-commit hook rewrote this")
            fresh_verified()
            try:
                stamp(p)
                refused = ""
            except SystemExit as exc:
                refused = str(exc)
            checks["stamp refuses a dirty non-checkpoint tree"] = (
                "dirty working tree" in refused
            )
            _run(["git", "add", "f"], repo)
            _run(["git", "commit", "-q", "-m", "commit the external edit"], repo)
            fresh_verified()
            stamp(p)
            checks["stamp after committing binds the new HEAD blob"] = (
                load(p)["verified_fixed"][0]["blob"]
                == _run(["git", "rev-parse", "HEAD:f"], repo).stdout.strip()
                != head_blob
            )

            # Refutations are judged BEFORE the round's fixes, so they bind to
            # the round-start tree. A same-round fix to the refuted path must
            # reopen the claim, not ship it as settled.
            def fresh_refuted() -> None:
                p.write_text(
                    json.dumps(
                        {
                            "schema": SCHEMA,
                            "pr": 1,
                            "refuted": [
                                {
                                    "severity": "HIGH",
                                    "location": "f:1",
                                    "claim": "c",
                                    "rationale": "r",
                                    "round": 1,
                                    "file": "f",
                                }
                            ],
                        }
                    )
                )

            start = current_head()
            fresh_refuted()
            (repo / "f").write_text("round fix landed after the refuters ran")
            _run(["git", "add", "f"], repo)
            _run(["git", "commit", "-q", "-m", "fix(f): same round"], repo)
            stamp(p, start)
            st = load(p)
            checks["refutation binds to round start, not the post-fix HEAD"] = (
                st["refuted"][0]["settled_head"] == start
                and st["refuted"][0]["blob"] == blob_of("f", start)
                and st["head"] == current_head() != start
            )
            t = render(st, 2, None)
            checks["a same-round fix reopens its own refutation"] = (
                "RE-EXAMINE" in t and "DO NOT RE-RAISE" not in t
            )
            # A round that committed nothing: round start IS HEAD, so the
            # refutation stays excluded.
            fresh_refuted()
            stamp(p, current_head())
            t = render(load(p), 2, None)
            checks["a no-commit round keeps its refutation excluded"] = (
                "DO NOT RE-RAISE" in t and "RE-EXAMINE" not in t
            )
            checks["stamp leaves no .tmp sibling behind"] = not list(
                ckpt.glob("*.tmp")
            ) and isinstance(load(p), dict)

            # An interrupted write: a recoverable status, never a parse crash.
            p.write_text('{"schema": 1, "pr": 1, "head": "dea')
            checks["truncated checkpoint is STALE corrupt, not a crash"] = check(
                p, 1
            ).startswith("STALE checkpoint is corrupt")
            try:
                stamp(p)
                corrupt_raised = False
            except CorruptState:
                corrupt_raised = True
            checks["stamp on a corrupt checkpoint raises CorruptState"] = corrupt_raised
        finally:
            os.chdir(cwd)
    return checks


def _packaged_path_selftest() -> dict[str, bool]:
    """The documented invocation path, run as the docs spell it.

    `CLAUDE_PLUGIN_ROOT` is the my-skills plugin root, so the script is three
    directories below it (`<root>/skills/zord-multi-agent-review/scripts/`). Docs that
    drop the skills directory exit 2 before the loop ever starts.
    """
    checks: dict[str, bool] = {}
    root = Path(__file__).resolve().parents[3]
    script = root / "skills" / "zord-multi-agent-review" / "scripts" / "loop_state.py"
    checks[
        "packaged layout: script sits under <plugin root>/skills/zord-multi-agent-review"
    ] = script.is_file()
    if not script.is_file():
        return checks
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "loop-state.json"
        r = subprocess.run(
            [sys.executable, str(script), "check", str(state), "--pr", "1"],
            capture_output=True,
            text=True,
        )
        checks["packaged layout: check runs and reports NONE"] = (
            r.returncode == 0 and r.stdout.strip() == "NONE"
        )
        state.write_text(json.dumps({"schema": SCHEMA, "pr": 1}), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(script), "render-prelude", str(state), "--round", "2"],
            capture_output=True,
            text=True,
        )
        checks["packaged layout: render-prelude runs"] = (
            r.returncode == 0 and "## ROUND STATE" in r.stdout
        )
        # The cap is the mechanical backstop for §10.2's "render and validate
        # BEFORE dispatching": an oversized prelude must fail here, loudly,
        # not inside the round subagent that was already spawned.
        caller = Path(tmp) / "big-prelude.md"
        caller.write_text("x" * (PRELUDE_CAP + 1), encoding="utf-8")
        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "render-prelude",
                str(state),
                "--round",
                "2",
                "--caller-prelude",
                str(caller),
            ],
            capture_output=True,
            text=True,
        )
        checks["render-prelude refuses an over-cap render"] = (
            r.returncode != 0 and "cap is" in r.stderr and r.stdout == ""
        )
        # A half-written checkpoint must exit with the message, not a traceback.
        state.write_text('{"schema": 1, "pr": 1', encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(script), "render-prelude", str(state), "--round", "2"],
            capture_output=True,
            text=True,
        )
        checks["corrupt checkpoint exits 2 with the message, no traceback"] = (
            r.returncode == 2
            and "checkpoint is corrupt" in r.stderr
            and "Traceback" not in r.stderr
        )
    return checks


def selftest() -> int:
    state = {
        "schema": SCHEMA,
        "pr": 42,
        "head": "deadbeef",
        "iterations_completed": 1,
        "rounds": [
            {
                "round": 1,
                "roster": ["kotlin-reviewer"],
                "axes": ["code"],
                "files_read": ["src/OrderPricing.kt"],
            }
        ],
        "verified_fixed": [
            {
                "symbol": "computeSubtotal",
                "file": "src/OrderPricing.kt",
                "finding": "unit price rounded before multiplying, compounding error",
                "evidence": "rounding applied once",
                "round": 1,
            }
        ],
        "deferred": [
            {
                "severity": "MEDIUM",
                "location": "src/X.kt:9",
                "reason": "SECRET-DEFERRAL-TEXT",
            }
        ],
        "fix_outcomes": [
            {
                "location": "src/Y.kt:3",
                "outcome": "FIX_FAILED",
                "reason": "SECRET-OUTCOME-TEXT",
            }
        ],
        "refuted": [],
    }
    text = render(state, 2, "## PROJECT PRELUDE\ncaller text")
    checks = {
        "caller prelude first": text.startswith("## PROJECT PRELUDE\ncaller text"),
        "round 1 shape rendered": "- Round 1: roster kotlin-reviewer; axes read: code; files opened: src/OrderPricing.kt"
        in text,
        "entry with no blob is re-verify, not out of scope": (
            "RE-VERIFY   computeSubtotal" in text
            and "VERIFIED-FIXED" not in text
            and "unit price rounded before multiplying" in text
        ),
        "deferral never rendered": "SECRET-DEFERRAL-TEXT" not in text
        and "src/X.kt" not in text,
        "fix outcome never rendered": "SECRET-OUTCOME-TEXT" not in text
        and "src/Y.kt" not in text,
        "no refuted section when empty": "DO NOT RE-RAISE" not in text,
    }
    empty = render({"schema": SCHEMA, "pr": 42}, 2, None)
    checks["empty state says nothing out of scope"] = "Nothing is out of scope" in empty
    checks["empty state lists no shapes"] = "- none recorded" in empty
    with_ref = render(
        {
            **state,
            "refuted": [
                {
                    "severity": "HIGH",
                    "location": "a.kt:1",
                    "claim": "c",
                    "rationale": "r",
                    "round": 1,
                }
            ],
        },
        2,
        None,
    )
    checks["unbound refuted entry is re-examined, never excluded"] = (
        "RE-EXAMINE" in with_ref
        and "HIGH a.kt:1" in with_ref
        and "DO NOT RE-RAISE" not in with_ref
    )
    checks.update(_check_selftest())
    checks.update(_stamp_selftest())
    checks.update(_packaged_path_selftest())
    ok = all(checks.values())
    for name, passed in checks.items():
        print(f"  {'ok ' if passed else 'FAIL'} {name}")
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if argv == ["--selftest"]:
        return selftest()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("state", type=Path)
    c.add_argument("--pr", required=True)
    c.add_argument("--resume-stopped", action="store_true")
    c.add_argument(
        "--remote-head",
        help="live PR head OID (from `gh pr view <n> --json headRefOid`); "
        "resume requires it to equal the checkpoint head and local HEAD",
    )
    s = sub.add_parser("stamp")
    s.add_argument("state", type=Path)
    s.add_argument(
        "--round-start",
        help="OID this round's reviewers and refuters read (the HEAD before "
        "the round's fix commits). Refuted entries bind here, not to the "
        "post-fix HEAD, so a same-round fix cannot launder a refutation. "
        "Defaults to current HEAD.",
    )
    r = sub.add_parser("render-prelude")
    r.add_argument("state", type=Path)
    r.add_argument("--round", type=int, required=True)
    r.add_argument("--caller-prelude", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "check":
        print(
            check(
                args.state,
                args.pr,
                resume_stopped=args.resume_stopped,
                remote_head=args.remote_head,
            )
        )
        return 0
    if args.cmd == "stamp":
        if not args.state.exists():
            sys.stderr.write(f"loop_state: no state file at {args.state}\n")
            return 2
        try:
            print(stamp(args.state, args.round_start))
        except CorruptState as exc:
            sys.stderr.write(f"loop_state: {exc}\n")
            return 2
        return 0
    try:
        state = load(args.state) if args.state.exists() else {"schema": SCHEMA}
    except CorruptState as exc:
        sys.stderr.write(f"loop_state: {exc}\n")
        return 2
    prelude = (
        args.caller_prelude.read_text(encoding="utf-8") if args.caller_prelude else None
    )
    text = render(state, args.round, prelude)
    size = len(text.encode("utf-8"))
    if size > PRELUDE_CAP:
        sys.stderr.write(
            f"loop_state: rendered prelude is {size} bytes; cap is "
            f"{PRELUDE_CAP}. Drop `files opened` lists oldest-round-first "
            "until it fits; never drop the verifier block. Nothing written — "
            "do not dispatch the round with a prelude the inner pass rejects.\n"
        )
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
