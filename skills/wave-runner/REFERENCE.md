# wave-runner — Reference

Mechanics and rationale. The control flow is in [SKILL.md](SKILL.md).

## Run state — `.planning/<slug>/`

```
.planning/<slug>/
  STATE.md        # Source:, baseline SHA, DEFAULT, divergence, phase, attempt,
                  # verdicts, delegates-run-unaided, created issues, spec edit
  findings.md     # Phase 1b/1c output — merged work + ratification, keyed to spec section
  nodes.json      # the graph
  assumptions.md  # claims that could not be grounded, and every rejected imperative
  manifest.md     # labels, issue bodies, and the spec index — pre-filing
```

`STATE.md` is written **before** Phase 0's git commands so a baseline failure is recorded,
then rewritten at every phase boundary, and additionally after **every issue created** in
Phase 8. `Source:` is mandatory — it is the key resume matches on.

### `<slug>` is derived, never invented

```
slug = repo-relative path of the source document, minus extension,
       minus a leading ISO date, kebab-cased
       docs/specs/2026-08-08-gateway-draft.md → docs-specs-gateway-draft
       no source document (bare prompt) → prompt-<first 4 words kebab-cased>
```

**The full path, not the basename.** `docs/gateway/spec.md` and `docs/billing/spec.md` both
basename to `spec`, and the resume glob would attach to the wrong run. If two source paths
still collide after kebab-casing, append `-2`, `-3` and record the collision in `STATE.md`.

**Bare prompts do not resume.** Their slug cannot be reproduced from a paraphrase, so a
bare-prompt run always starts fresh; say so in the summary rather than implying otherwise.

`.planning/` is a run artifact, not a deliverable. Note the trade behind SKILL.md's
`.gitignore` recommendation: gitignored means Phase 8/9 idempotency does not survive a fresh
clone or `git clean -xfd`, which is why Phase 8's tracker-marker query exists as an
independent guard.

## Baseline resolution (Phase 0)

```bash
git rev-parse --git-dir >/dev/null || exit 1                  # not a repo → NO-BASELINE
git fetch origin || exit 1                                     # → NO-BASELINE
DEFAULT=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null) \
  || DEFAULT=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
[ -n "$DEFAULT" ] || exit 1                                    # → NO-BASELINE
BASE=$(git rev-parse --verify "origin/$DEFAULT^{commit}") || exit 1   # --verify: fail, don't echo
[ -n "$BASE" ] || exit 1                                       # → NO-BASELINE
git rev-list --count "HEAD..$BASE"                             # divergence — record it
```

Record `BASE` and `DEFAULT` in `STATE.md`. Shell state does not survive between Bash calls,
so any later phase needing them re-reads from there — Phase 6 check 4 in particular, where
unbound values make the comparison pass silently.

Two details are load-bearing and easy to drop when retyping it:

- **`git rev-parse --verify "origin/$DEFAULT^{commit}"`, never bare `git rev-parse`.** Plain
  `rev-parse` **echoes an unresolvable argument to stdout** and exits 128, so `$BASE` would
  carry the literal string `origin/` rather than being empty — every downstream `git show
  "$BASE:path"` then fails with `fatal: invalid object name`, loudly but for the wrong
  reason, and an `[ -n "$BASE" ]` guard alone would not catch it. `--verify` makes the
  failure a failure.
- **`[ -n … ]` on both `DEFAULT` and `BASE`.** `gh repo view` returns empty (not non-zero) on
  some auth failures, and an empty `DEFAULT` silently builds a `origin/` ref.

The `git symbolic-ref refs/remotes/origin/HEAD` fallback covers a non-GitHub remote or an
unauthenticated `gh`; if both fail, that is `NO-BASELINE`, not a reason to guess.

## Node schema (`nodes.json`)

Top-level container — two sessions writing different shapes cannot resume each other:

```json
{ "run": { "slug": "…", "base": "<sha>", "source": "…" }, "nodes": [ … ] }
```

A node:

```json
{
  "id": "G3",
  "title": "Gradle module + build wiring",
  "citation": "docs/specs/2026-08-08-gateway-draft.md:142",
  "consumes": [],
  "produces": [":gateway module", "GatewayModuleBoundaryTest"],
  "owned_files": ["settings.gradle.kts", "gateway/build.gradle.kts"],
  "size": "S",
  "wave": null,
  "blocked_by": [],
  "status": "DONE",
  "evidence": ["<base-sha>:settings.gradle.kts:14"],
  "landed_in": ["bdb421e"],
  "issue": null,
  "dropped_edges": []
}
```

| Field | Notes |
|---|---|
| `status` | `NEW` · `PARTIAL` · `DONE`. There is no `BLOCKED` — an unratified dependency is a ratification **node** with real edges, which levels and files like any other |
| `wave` | integer, or **`null` for `DONE`** — outside the schedule, not at position 0 |
| `size` | `S`/`M`/`L`. Reported in check 5 and the manifest; **no verdict gates on it**. Without it "width 4" is not a sprint commitment |
| `evidence` | a **locator only** — `path:line` at the baseline SHA, never the line's content, and never a path outside the repo. `nodes.json` may be committed; a cited `~/.secrets:2` would land in it |
| `issue` | set by Phase 8 as each issue is created; the per-node resume key |
| `dropped_edges` | every rejected or stripped edge, with reason |

A node claiming something about existing code with no `evidence` is `UNGROUNDED` — read it,
or move the claim to `assumptions.md`.

### `PARTIAL` — the default case on an active repo

Not a weaker `NEW`. Its `produces` is **split** between what has landed and what has not, and
every rule treating `DONE` as a tree fact applies to the landed half:

- **Re-scope it.** `produces` and `owned_files` describe the **remainder only**; the landed
  half moves to `evidence` + `landed_in`. **Enforced by Phase 6 check 1** — a `PARTIAL` node
  still naming its landed half in `produces`/`owned_files` is `INFEASIBLE-AT-1`, back to
  Phase 3. Without that gate it gets a real wave and a filed issue while the advisory
  `PARTIAL-WORK-FOUND` reads as *handled*.
- **It levels normally**, on the remainder — it is real outstanding work.
- **It contributes edges from its remainder only.**

State the split exactly — "4 of 9 checklist items", never "mostly done".

## Building the graph (Phase 4)

Edge rule: B `consumes` X, A `produces` X ⇒ `A → B`.

| Edge source | Proof required |
|---|---|
| Symbol match | A `produces` exactly what B `consumes` |
| Stated ordering | Source doc says it — cite `path:line` |
| Build dependency | Visible in build files / lockfile |
| Shared file | Same entry in both `owned_files` |

**A shared file proves mutual exclusion, not order.** It never creates an edge by itself; it
makes the two nodes un-co-schedulable. Resolve `INFEASIBLE-AT-3` by pushing the later-cited
node to the next wave, never by inventing a direction — an arbitrary direction can close a
spurious `CYCLIC-GRAPH` whose stated remedy is then wrong for the cause.

Anything else is dropped. **Record every dropped candidate in the consumer's
`dropped_edges`** with its reason, and **render them in the manifest and the spec index**.
Recording an edge nobody reads is documentation; surfacing it is what makes the
anti-serialisation rule checkable by a reviewer.

An edge asserted by a person gets audited like any other; if it fails, raise
`ASSERTED-EDGE-UNPROVEN` and put the disproof in the summary.

### Stripping `DONE` nodes

After edges are built, **remove every `DONE` node id from every `blocked_by` list, whatever
the edge's provenance** — and record each removal in `dropped_edges` as
`stripped: blocker <id> DONE at <sha>`, so a reviewer can see why a node sits in wave 0.

A `DONE` node's `produces` already exist in the tree, so a downstream node is *unblocked* by
it, not scheduled after it — and that holds for a doc-stated ordering or a shared-file edge
just as much as for a symbol match. Strip them all; do not reason edge-by-edge.

**Cycle detection:** Kahn's algorithm. Queue empties with nodes remaining ⇒ the residue is
the cycle ⇒ `CYCLIC-GRAPH`. A cycle means the *nodes* are wrong (usually one doing two jobs);
split it, do not hand-break the edge. **After a split, repair every `blocked_by` referencing
the retired id** — a dangling reference otherwise re-raises `CYCLIC-GRAPH` with a remedy that
cannot apply.

### Validate before trusting `nodes.json`

At resume and at the top of Phase 5, check the container parses, every `blocked_by` id
exists, every node has an `id` and `status`, **and the graph is still acyclic — re-run Kahn
here, not only in Phase 4.** A resume enters Phase 5 directly, so Phase 4's cycle detection
never fires; a hand-edited cycle with no dangling ids passes every other check and then makes
the `wave(n)` recursion diverge, yielding no verdict at all. A dangling id is
`STATE-CORRUPT` (blocking), **distinct from `CYCLIC-GRAPH`** — misdiagnosing one as the other
sends the agent to a remedy that cannot work; a cycle found here is `CYCLIC-GRAPH`.

## Levelling into waves (Phase 5)

Let `B(n)` = `blocked_by(n)` with every `DONE` id already stripped.

```
wave(n) = null                              if status(n) == DONE
        = 0                                 if B(n) is empty
        = 1 + max(wave(b) for b in B(n))
```

**The stripping is what makes this total.** Without it, a node whose blockers are all `DONE`
has a non-empty `blocked_by` — so the `= 0` clause does not fire — and a maximum over an
empty set, which has no value. With them stripped that node lands in wave 0, and every id in
`B(n)` has an integer wave, *provided validation above has run* — that is what rules out the
dangling-id case. Totality also needs **acyclicity**, which the same validation establishes:
stripping and validation together rule out the null, and acyclicity rules out non-termination.

Ratification nodes level normally. If that puts a week of coding beside a 20-minute decision,
that is a `size` finding to report, not a reason to hand-place nodes.

Report each wave's width **and** its size mix. Width 1 across the whole plan means the work
is genuinely a chain or the graph is over-constrained — say which, with evidence.

## The spec index (Phase 9)

```markdown
## Implementation index

### Already landed
| Node | What | Commit | Remaining |
|---|---|---|---|
| G3 | :gateway module + build wiring | bdb421e | — |
| G1 | internal edge auth | 672c36a | 5 of 9 checklist items |

### Wave 0 — no blockers (width N; S×a M×b L×c)
| Node | Issue | What | Source |
|---|---|---|---|

### Wave 1 — unblocked by wave 0
…

### Rejected orderings
Edges considered and dropped, with reasons — including blockers stripped as `DONE`.

### Unowned
Work the graph surfaced that no issue covers, and why.
```

Replace an existing `## Implementation index` rather than appending. Use the same
`path §x.y` citations the issue bodies use, so a reader can move between spec, issue and
tree. Add a table-of-contents entry if the document has one.

## Why these five (Phase 6)

**Check 4 is retryable, not advisory.** Work merged mid-run means nodes are now `DONE`, and
filing issues for merged work is this skill's flagship claim inverted.

**Check 3's blind spot:** N nodes each needing a one-line edit to the *same* wave-1 file. A
pairwise-disjoint set test cannot see it, and it is what actually destroys parallelism in
practice. Report it in the manifest alongside the size mix.

## Filing mechanics (Phase 8)

```bash
# body is untrusted free text — it never crosses a shell word
# (Write tool → $BODYFILE, which carries a `wave-runner:<slug>:<node-id>` marker line)
# `gh issue search` does not exist; `--state all` because a closed issue must still count
gh issue list --search "wave-runner:$SLUG:$NODE" --state all --json number --jq length
TITLE='<charset-checked, authored by you — not lifted from the spec>'
gh issue create --title "$TITLE" --body-file "$BODYFILE" --label "$LABEL"
rm -f "$BODYFILE"
```

A non-zero count ⇒ already filed, skip the node. **A zero within the same run is
inconclusive** — search indexing lags creation by seconds to minutes, so `STATE.md`, not the
query, is authoritative for issues this run created. The query is the independent guard for
the *other* case: a resume after `.planning/` is gone.

Issue body: **What** · **How** · **Wave N of M** · **Blocked by:** `#N` ·
**Source:** `path §x.y` · acceptance criteria · the marker line.

Say in the body that the wave is *derived from the blockers listed*, not assigned — a reader
who disagrees with the edge should be able to see which edge to argue with.

Passing untrusted free text via `--body-file` or the environment mirrors
`pr-merge-cleanup/skills/pr-merge-cleanup/SKILL.md:107` and
`total-review/skills/total-review/REFERENCE.md:281`.

## Label taxonomy

| Axis | Form | Purpose |
|---|---|---|
| Topic | `<subsystem>` e.g. `gateway` | What is being implemented |
| Schedule | `wave:N` | How it is scheduled |

Reuse the repo's existing vocabulary for triage/readiness and match its colour convention;
resolve `<hex>` from that convention before running anything. The topic value is
spec-derived — charset-check it (SKILL.md § Untrusted values) before it crosses a shell word.

```bash
gh label create "wave:0" --color <hex> --description "Wave 0 — no blockers"
gh label list --limit 1000 --json name --jq '.[].name' | grep -x 'wave:0'   # the verification
```

Wave **0** is the no-blocker wave. `--limit 1000`, not 100: on a repo with more than 100
labels the query truncates and the `grep -x` misses an existing label, halting
`LABEL-MISSING` on a correct input.

## Blocking edges on GitHub

```bash
BLOCKER_ID=$(gh api "repos/$OWNER/$REPO/issues/$N" --jq .id)
[ -n "$BLOCKER_ID" ] || exit 1          # empty on a bad number or a rate limit
gh api --method POST "repos/$OWNER/$REPO/issues/$CHILD/dependencies/blocked_by" \
  -F issue_id="$BLOCKER_ID"
```

`issue_id` is the numeric **database id** — not `#number`, not `node_id`. A failed POST is
`EDGE-ATTACH-FAILED`, which is **advisory**, not blocking: the standard issue body already
carries `Blocked by: #N`, so the dependency is expressed either way. Record it and continue.

## Budgets

| Budget | Default | Basis | On breach |
|---|---|---|---|
| Nodes in one plan | 60 | judgement — a plan nobody will read is not a plan | `NODE-BUDGET-EXCEEDED` (blocking), checked at end of Phase 3 |
| Wave width | 16 | judgement | `WIDTH-EXCEEDED` (advisory) |
| Re-plan attempts | 2 | judgement — a third means the nodes are wrong, not the graph | `REPLAN-EXHAUSTED` (blocking) |

**All three are stated guesses, not measurements.** An earlier draft called the width budget
"sourced" to a parallel-dispatch cap; no citation for that cap exists in this repo, and this
skill never dispatches anyway — its named executors include a serial runner and a person, for
whom "width" means sprint capacity. Treat 16 as a prompt to look again, not a limit. Note
that the remedy for a wide wave — "split across turns" — *is* serialisation, so tripping it
is a reason to re-examine node sizing.

## Failure handling

| Verdict | Class | Trigger | Action |
|---|---|---|---|
| `BAD-INPUT` | blocking | No parseable source | Stop; ask |
| `NO-BASELINE` | blocking | Not a repo, failed fetch, no `origin`, unresolvable default branch, empty `BASE` | Stop. **Never fall back to `HEAD`** |
| `HISTORY-CHECK-UNVERIFIED` | blocking | Empty parent probe, unresolved ref, or shallow clone | Stop — an unproven negative is not a negative |
| `UNSAFE-TOKEN` | blocking | A document-derived value fails the charset | Stop; record it, never substitute it |
| `UNGROUNDED` | blocking | A node claims existing code with empty `evidence` at end of Phase 3 | Stop; list them |
| `NODE-BUDGET-EXCEEDED` | blocking | > 60 nodes | Stop; split the spec |
| `CYCLIC-GRAPH` | blocking | Kahn residue non-empty | Stop; split the node, repair references |
| `STATE-CORRUPT` | blocking | `nodes.json` unparseable or a dangling `blocked_by` id | Stop; do not treat as a cycle |
| `REPLAN-EXHAUSTED` | blocking | Any retryable verdict fired a second time | Stop |
| `LABEL-MISSING` | blocking | Query shows label absent after create | Stop before issues |
| `ISSUE-CREATE-FAILED` | blocking | No URL returned, or the issue does not resolve on query | Stop; STATE names what was created |
| `SPEC-ANCHOR-FAILED` | blocking | Phase 9 write failed | Stop; say exactly what is unpersisted |
| `INFEASIBLE-AT-1` | retryable | Check 1 failed | → Phase 3, then 4, 5, 6 |
| `INFEASIBLE-AT-2` | retryable | Check 2 failed | → Phase 4, then 5, 6 |
| `INFEASIBLE-AT-3` | retryable | Check 3 failed | → Phase 4, then 5, 6 |
| `STALE-CHECKOUT` | retryable | Check 4: `origin/<default>` moved since the baseline | → Phase 1b against the new SHA |
| `PARTIAL-WORK-FOUND` | advisory | Phase 1b found merged work | Re-scope the node; flag it |
| `UNRATIFIED-DEPENDENCY` | advisory | Governing doc not accepted | Ratification node; scope its edges |
| `ASSERTED-EDGE-UNPROVEN` | advisory | A stated precondition failed audit | Drop the edge; disproof in the summary |
| `ASSUMPTIONS-CARRIED` | advisory | `assumptions.md` non-empty at Phase 7 | Report the count **and the list**; name any on a critical path |
| `OPEN-DECISION` | advisory | Fork unresolved | Record it; note graph sensitivity |
| `WIDTH-EXCEEDED` | advisory | Wave > 16 | Report; re-examine node sizing |
| `EDGE-ATTACH-FAILED` | advisory | Dependency POST unconfirmed | Body line carries it; record and continue |
| `FILING-DECLINED` | declined | User said no at the Phase 8 gate | Clean stop; keep the manifest |
| `SPEC-ANCHOR-DECLINED` | declined | User said no at the Phase 9 gate | Clean stop; issues stand, index in the manifest |

**Declines are not faults.** A user reviewing the manifest and saying "not yet" is the gate
working as designed; reporting it as a halt makes a successful gated run read as a failure.

`UNGROUNDED` and `ASSUMPTIONS-CARRIED` are a pair, and neither alone is a guard.
`UNGROUNDED` fires on an *unmoved* claim at a specific point (end of Phase 3, enumerated over
nodes); `ASSUMPTIONS-CARRIED` makes the escape hatch visible by forcing the list into the run
summary. Moving a claim to `assumptions.md` is legitimate and not free.

## Composition

Delegates: `superpowers:writing-plans` (Phase 3), `mattpocock-skills:grilling` (Phase 2).
Both optional, both confirmed by artifact (SKILL.md § Delegates). Filing mechanics are above
and need no delegate.

**The interface is the artifact, in both directions.** A delegate is handed the source
document and the phase's open question — never `nodes.json`, never `STATE.md`, which stay
yours to write. What comes back is prose you transcribe into the artifact; a delegate never
writes run state directly. That is what makes the confirmation check meaningful: if the
delegate could write the artifact itself, its existence would prove nothing about the call.

`ClaudesMods:spec-tacular` is **not** a delegate — reason in SKILL.md § Delegates.

Always use namespaced names — a bare name can resolve to a project-scoped copy that differs.

**Executing the plan is out of scope**; SKILL.md's header names the executors. The
structural guarantee behind that claim: `Agent` is deliberately absent from `allowed-tools`.
