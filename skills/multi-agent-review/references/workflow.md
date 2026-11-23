# multi-agent-review — Full step-by-step workflow

> Reference file for [`../SKILL.md`](../SKILL.md) (multi-agent-review) — the one-shot and loop dispatch procedures.

## 5. Workflow

### 5.0 Parse, validate, and select mode

Execute this step first on every invocation:

1. Parse positional args + flags per §3.
2. **Determine `mode`:** if `<target-type>` is `pr` AND `--no-loop` is absent AND `--in-loop` is absent → `mode = loop`; else `mode = oneshot`.
   **Recursion backstop — two independent, parser-visible layers.** *Belt:* the loop's inner self-call passes `--no-loop`, which forces the inner pass to `oneshot`. *Suspenders:* the inner self-call **also** passes an explicit `--in-loop` token in its `args`, and this step reads `--in-loop` from its **own** `args` and **hard-refuses loop mode (forces `oneshot`) if present** — so the refusal is structural even if `--no-loop` were ever dropped from the self-call. (Both channels are real command tokens this skill's own arg parser sees; there is no env var or out-of-band brief marker, because this step only reads its parsed `args`.)
3. **Validate loop-only-flag exclusivity (parse-time hard-fail):** `--max-iterations`, `--high-and-up-only`, `--no-smoke`, `--resume-stopped` are valid only when `mode == loop`. Passing any of them together with `--no-loop`, or with a non-`pr` target, is a hard-fail with a clear message (e.g. `--max-iterations is only valid on a looping pr target; it conflicts with --no-loop`). `--yes` and `--no-loop` are accepted no-ops where they don't apply (see §3) — they never hard-fail on their own.
3a. **Determine `refute`, and validate its tuning flags (parse-time hard-fail):**
   - `refute = true` if and only if `--adversarial` is present. **Absence means off** — there is no inference from any other flag, and no target type or mode turns it on by itself (§4).
   - `--adversarial` together with `--no-adversarial` → hard-fail (§11). `--no-adversarial` alone is an accepted no-op that leaves `refute = false`.
   - `--refuters` or `--max-refuters` present while `refute == false` → hard-fail (§11). They tune a stage that is not running, and a tuning flag must never switch the stage on.
   - Validate `--refuters` (integer 1–5) and `--max-refuters` (integer ≥ 1) only when `refute == true`; both hard-fail on out-of-range values per §11.
   - When `mode == loop` AND `--yes` is present AND `refute == false`, emit this recommendation note to stderr **once**, here, before the loop starts (§4): `note: refutation is off; unattended auto-fix will act on unchallenged findings — pass --adversarial to verify them first`. It is a note, never a gate.
   - `reportAudit = true` unless `--no-report-audit` is present. Independent of `refute` in both directions: the audit runs on an unrefuted report (failure classes 1 and 7 simply do not apply, and §7b's verdicts block is stripped), and `--adversarial` does not imply it. Nothing about this flag hard-fails — it takes no value and conflicts with nothing.
3b. **Validate `--lenses` against a looping `pr` target (parse-time hard-fail):** `--lenses` is not valid when `mode == loop` (from step 2) — a lens brief describes the target as "the document under review" (§5A.3), which a diff cannot supply, and a looping `pr` auto-fixes and commits on the coordinator's own reading, so a document-shaped lens directive could drive real edits with no human in between. Hard-fail with a clear message directing the caller to `--no-loop` (e.g. `--lenses is not valid on a looping pr target; pass --no-loop to review the PR as a document, or drop --lenses to loop normally`). `--lenses` remains valid on `pr --no-loop` and on every non-`pr` target (§3) — this check fires only for `mode == loop`, so it never touches the inner self-call, which always carries `--no-loop`.
3c. **A gate passes `--high-cap off` itself.** Nothing in the args says whether the caller will gate on the result, so in one-shot mode this step never infers it and applies whatever cap it receives, an explicit `--high-cap <n>` included. A caller that gates on a one-shot review (an upstream pipeline's per-phase `VERDICT`, or a `spec`/`diff`/`dir` review it treats as a phase gate) passes `--high-cap off`, as `baton-runner` does. (Loop mode forces it `off` itself, §4.) When the cap stays on, any summary or handoff built from the report lists each demoted finding at its original severity, from the orchestrator's `Demoted:` line (§7c) or the synthesizer's `_(demoted from HIGH by severity budget; <reason>)_` marker, never under a softer label: a phase gate run at the default cap 8 once demoted 10 HIGH findings, and the handoff then described them as "spec clarifications".

4. **Determine `dispatch`:** if `--inline` is absent AND `--in-subagent` is absent AND `--in-loop` is absent → `dispatch = subagent`; else `dispatch = inline`. Applies to `mode == oneshot` only; the loop coordinator (§5B) always runs inline in the caller's session.

   **Recursion backstop — the same two parser-visible layers loop mode uses, plus a third condition.**
   - *Belt:* §5A.0's dispatch passes `--inline`, forcing the inner pass to run in place.
   - *Suspenders:* it **also** passes `--in-subagent`, and this step reads that token from its **own** `args` and forces `inline` when present — structural even if `--inline` were ever dropped from the self-call.
   - *Third condition — `--in-loop` forces `inline`, and it is load-bearing.* A loop round already runs inside a fresh subagent (§10.2). Letting its inner call spawn an orchestrator too would stack caller → round subagent → orchestrator subagent → workers, and each added layer is another chance for §10.2 step 3's precondition to fail. See §5A.0's two-layer contract.
5. If `mode == oneshot` AND `dispatch == subagent` → go to §5A.0 (orchestrator dispatch) and stop. §5A.1 onward execute **inside the dispatched subagent**, not here.
6. If `mode == oneshot` AND `dispatch == inline` → continue at §5A.1. Steps 7–9 below apply only to `mode == loop`.
7. **Loop preconditions** (hard-fail on any miss — never guess):
   - `--max-iterations`, if present, parses as an integer 1–8.
   - `gh` is on PATH (`command -v gh`) — fail with install instructions if not.
   - The PR exists and is open: `gh pr view <ref> --json state,headRefName,baseRefName,url`. Hard-fail on `state != OPEN` (closed/merged PRs can't be iterated).
   - The working directory is a git worktree on the PR's `headRefName` (or `cd` into one if a worktree for that branch exists locally). If neither: hard-fail with `multi-agent-review loops by default on a PR and needs a worktree on <headRefName>. Create one, or pass --no-loop for a one-shot read-only report.` **Never silently mutate the wrong branch.**
   - **The tree is clean and local `HEAD` is the live PR head** — `git status --porcelain --untracked-files=all` is empty apart from paths under `checkpointDir`, AND `git rev-parse HEAD` equals `gh pr view <ref> --json headRefOid --jq .headRefOid`. Hard-fail on either miss, before anything is dispatched. This is the precondition a `STALE` resume falls back to (§10.1), so it cannot be weaker than the resume check it replaces: a dirty tree means an interrupted round's edits are still uncommitted and the loop's own commits would sweep them up under a finding that never mentions them, and a local `HEAD` behind or ahead of the PR head means the loop would review the remote's code while applying fixes over different local commits. Tell the human what to inspect; never `git stash`, `reset`, or `pull` on their behalf.
8. **Confirmation gate.** When loop mode was entered **implicitly** (no `--yes`), prompt and wait before mutating: `Looping will edit/commit/push on <headRef> across up to N rounds; proceed? (pass --no-loop for a read-only report)`. Do not start the loop until the user confirms. This is a hard gate, not a fire-and-forget notice — it is the guard against a caller who expected the pre-2.0 read-only `multi-agent-review pr 42`. `--yes` skips the gate for unattended/automated runs (the only way to loop without the interactive prompt). **Non-interactive contexts hard-fail, never hang:** if the gate is reached with no attached human and no `--yes`, exit with `multi-agent-review pr loops by default and needs confirmation; pass --yes to run unattended` rather than blocking forever on an unanswerable prompt — a forgotten `--yes` fails loudly, not silently deadlocks. If the user declines the gate interactively, abort the loop cleanly with no mutation (offer `--no-loop` as the read-only alternative).
9. Continue at §5B (loop machinery). The loop coordinator runs **inline in the caller's session**, never dispatched: it edits files, commits, and pushes, and a mutating loop a human cannot watch is a worse default than a full context window. Step 8's confirmation gate would also have nothing to prompt from inside a subagent.

### 5A. One-shot machinery (read-only)

Reached when `mode == oneshot` (any `--no-loop` run, any `--in-loop` inner pass, or any non-`pr` target). §5A.0 decides *where* the rest runs; §5A.1–5A.7 are the work itself and are identical either way.

### 5A.0 Orchestrator subagent dispatch (the default)

Reached from §5.0 step 5 when `dispatch == subagent` — every one-shot invocation not already inside a subagent this skill created.

**All targets, no threshold.** `file SPEC.md` dispatches exactly as `slices` does. A uniform rule is predictable; a size or target-type threshold makes a caller guess which context their review is about to land in, and the saving on a small target is small but never negative.

**What it buys.** §5A.1–5A.7 spawn N reviewers, then — under `--adversarial` — up to `--max-refuters` refuters, then a synthesizer, and every one of those returns lands in whatever context runs them. Inline, that is the caller's session: a 5-reviewer `--adversarial` run over 20 distinct claims drops ~50 refuter transcripts plus 5 full reviewer reports into a window meant to hold a conversation. Dispatched, the caller receives a summary and the report's path. The saving is still real with refutation off (5 reviewer reports plus a synthesizer transcript), which is why dispatch stays default-on independently of the refutation default.

#### Dispatch

Spawn **one** `Agent` call:

- `subagent_type`: `general-purpose`
- `description`: `"Multi-agent review: orchestrate <target-label>"`
- `prompt`: the [orchestrator brief](agent-briefs.md#7c-orchestrator-subagent-brief-template) (§7c), expanded
- `run_in_background`: **`false`** — per SKILL.md Hard rule 1. This dispatch carries the entire review; backgrounded, the caller's turn ends here, the orchestrator's return notifies the top-level session instead of the caller, and the integrity gate below never runs. The "Early return" shape at the end of this section is what that looks like from the caller's side.

The brief instructs the subagent to invoke this skill with the caller's original args **plus `--inline --in-subagent`**. Never forward a bare arg string — a bare self-call re-enters §5.0 with `dispatch = subagent` and spawns another orchestrator.

#### The two-layer contract

This skill dispatches at exactly **two** layers, and the count is deliberate:

| Layer | Who runs it | What it spawns |
|---|---|---|
| **1 — orchestrator** | one-shot: §5A.0's subagent · loop: §10.2's per-round subagent | the reviewer / refuter / synthesizer fan-out |
| **2 — workers** | reviewers, refuters, synthesizer | nothing |

A loop round *is already* layer 1 — that is precisely why `--in-loop` forces `inline` (§5.0 step 4). Without it a round inserts a third layer between itself and its reviewers, and the harness does not guarantee subagent-of-subagent dispatch (§10.2 step 3). **Two layers is the contract. Do not add a third.**

#### Precondition check — degrade loudly, never silently

Extends §10.2 step 3's check to the one-shot orchestrator, for the same reason and with the same failure mode in view. The brief requires the subagent to verify the `Agent` tool is available to it **before** invoking the skill. If it is not, layer 2 is impossible: the run would quietly collapse into one agent role-playing the entire roster, producing a report that *looks* like a five-lens review with none of the independence that makes fan-out worth anything — and a refutation stage whose refuters are the same author as the findings, which is worse than no refutation at all.

On that precondition failing, the subagent must return exactly:

```
DISPATCH-FAILED: Agent tool unavailable in subagent context
```

and nothing else. On receiving it the caller sets `dispatch = inline`, continues at §5A.1 in its own context, and states in one line that orchestrator dispatch was unavailable so the review is running inline. **Do not retry the dispatch** — a missing tool does not appear on a second attempt. **Do not accept a report from a subagent that could not spawn workers**; a self-attested multi-lens review from a single agent is the failure §12 names, and it must be visible, not absorbed.

The asymmetry with loop mode is deliberate: here the fallback is safe because the *caller* is the top-level session and can dispatch real reviewer subagents itself — `--inline` moves where the fan-out runs, not whether it happens. §10.2's equivalent fallback had the round subagent role-play the lanes with no fan-out at all, in a mode that then commits and pushes, and is withdrawn for that reason.

**The check is self-reported, not proof — same posture as the coverage gate (decision #28).** The caller cannot observe the subagent's tool calls, so an orchestrator that ignored Step 1 and fabricated a roster would return something the structural integrity check below passes. What the spec buys is an honest path that is unambiguous and cheap to take, plus deterministic tells that a fan-out collapsed:

- **`## Reviewer Disagreements` empty while every reviewer is reported engaged.** One author cannot genuinely disagree with itself; §12's rule against taking an inline-fallback round's "no disagreements" at face value applies here unchanged.
- **Refutation totals implausible for the settings** — `--adversarial` passed but zero refuter verdicts reported, or a large finding set with every item UPHELD and nothing CONTESTED or DROPPED. (Not a tell when refutation is off: zero verdicts is then the correct output, so this check is skipped entirely rather than firing on every default run.)

Neither is conclusive. Treat a report tripping either as a collapsed fan-out: weight it lower, say so in the output, and prefer an `--inline` re-run when the stakes justify it.

#### Returning the result — full text, never a summary

**With a report file (the default), the return is a summary and the file is the report.** The return is the `Wrote:` line, the title, the Executive Summary, `Counts:`, `Top:`, `Cap:`, `Demoted:` and `Failed:` lines, any `Comment:` URL and any security notes (§7c). This keeps a long report out of the caller's context, and the file keeps every finding. A caller that must triage or fix findings reads the file.

**With no file (`--no-write`, or a failed write), the subagent's return value IS the report.** A subagent's default instinct is to compress what it returns, and a compressed review report is a different, worse artifact than the one the synthesizer produced.

Stated as a shape rather than a prohibition (§7c carries the binding wording):

- The return **begins** with `# Multi-Agent Review:` and **ends** with the last line of the report's final section.
- Every section the synthesizer emitted appears in full — Executive Summary, Critical Findings, High Findings, Medium and Low Findings, Refuted Findings, Coverage Report, Unstated Assumptions, Reviewer Disagreements, Recommended Changes, Open Questions, Cross-Slice Patterns where applicable, and Notes whenever one was emitted. `## Notes` is the section a compressing subagent is likeliest to judge unimportant, and it is the only record that a reviewer or lens slot failed to spawn — dropping it turns a degraded run into one that reads as clean.
- Every finding keeps its title, location, description, suggested fix, attribution, and severity tag. Every refuter rationale under Refuted Findings is verbatim.
- Nothing precedes it, nothing follows it — no cover note, no "here is the report", no closing commentary.

**Caller-side integrity check — a mandatory gate, not advice.** Run it the moment the subagent returns, before printing anything and before waiting on anything. Confirm the return:

1. opens with a single `Wrote: <absolute path>` line immediately followed by `# Multi-Agent Review:` and then `## Executive Summary`, and that file exists; **or**, with no file, opens with `# Multi-Agent Review:`. Anything else before those lines fails the check. **and**
2. contains, **in the file when there is one, otherwise in the return**, a `## Coverage Report` heading (plus `## Report Audit` when §5A.6a ran, and `## Refuted Findings` when refutation ran), **and**
3. that Coverage Report opens with a `Reviewers: <returned>/<dispatched> returned` line (§5A.5) in which the two numbers are **equal**, **and**
4. that the next line is `Reviewed at: <oid>` (§5A.6), carrying a 40-character hex OID — the commit captured before dispatch, never one re-derived when the report is read.

Check 3 is the one that catches a collapsed fan-out. Checks 1 and 2 are structural and a single agent writing a plausible report passes both — the caller cannot observe the subagent's tool calls, so shape is all it has. A count is not proof either (an orchestrator that fabricated its roster will fabricate the ratio too), but it converts the most common real failure — workers dispatched and silently lost — from invisible into a mismatch on the face of the report. A missing `Reviewers:` line fails the gate: it means the return came from a pass that predates this contract or from one that skipped §5A.5's reconciliation. Check 4 fails for the same reason rather than a new one — a report that cannot say which commit it read cannot be checked for staleness afterwards, and "which commit did this review actually cover" is the one question a merge gate asks of it.

Anything else fails the gate. There are three distinct failure shapes, and all take the same action:

- **Early return (the common one).** The return says the reviewers are still running — *"waiting on the remaining three reviewers"*, *"notifications will arrive as each completes"*, or similar. This is **not** a progress report and there is nothing to wait for: the orchestrator's turn is over, its background children now notify the **top-level session** instead of it, and §5A.5/§5A.6/§5A.6a will never run. This is what `run_in_background: false` exists to prevent, and a return of this shape means **some** dispatch omitted it. Check both layers, not just the workers: the orchestrator dispatch above (§5A.0) and the worker dispatches (§5A.4) are equally capable of producing this shape, and the orchestrator is the likelier culprit precisely because it is the one dispatch a reader thinks of as "the run" rather than as a subagent.
- **Compression.** A summary, an abstract, or "the key findings" in place of the document.
- **Short count.** The report is well-formed but `Reviewers:` shows fewer returned than dispatched. The fan-out was paid for and partly lost. Do not read the findings as a full review and do not patch the gap by re-running only the missing lanes — the synthesis, dedupe, and severity budget were all computed over an incomplete set.

**Action for all three: re-run immediately with `--inline`.** Do not wait for notifications, do not resume the subagent to ask whether it is done, and do not hand-assemble a report from reviewer notifications that arrive afterward — a hand-assembly skips the dedupe, the cross-axis severity budget, and the report audit, and it silently drops any reviewer whose notification you never saw. Say in one line that the dispatched run returned before synthesizing and the review is re-running inline.

**The caller relays; it never re-summarizes, and it never substitutes its own consolidation for the synthesizer's.**

**The report file is the durable copy.** A report path is always set unless `--no-write` was passed, and the subagent performs the write itself and reports the absolute path. The file is authoritative and complete even if the returned text were truncated in transit, so treat it as the artifact of record — especially for very large reviews, where the returned text is the likeliest thing to be truncated.

### 5A.1 Parse and validate

1. Parse positional args + flags per §3.
2. Hard-fail with a clear error and exit if:
   - `<target-type>` is missing or not one of `pr|dir|file|spec|diff|slices`.
   - `<target-args>` don't match the type (e.g., `pr` with no number/URL; `file` with more than one path; `diff` with any positional arg other than nothing; `slices` with fewer than two paths).
   - `--reviewers` is present but empty.
   - `--staged` is present and `<target-type>` is not `diff`.
   - `--prompt-prelude` is present and the resolved path does not exist OR exceeds the 16 KB cap.
   - `<target-type>` is `slices` and the number of paths exceeds `--max-slices` (default 6).
   - `--lenses` is present but empty.
   - `--lenses` contains a slug outside {`pre-mortem`, `inversion`, `first-principles`, `red-team`, `jobs-to-be-done`}.
   - `--lenses` contains a duplicate slug after whitespace stripping.
   - `--lenses` resolves to more than 5 slugs.
3. **Validate `--reviewers` CSV.** Split on `,`, then strip surrounding
   whitespace from each token (natural inputs like `a, b, c` are
   accepted). Reject only if a token is empty after stripping (consecutive
   commas) or contains internal whitespace (`a b` inside a single token).
3a. **Validate `--lenses` CSV.** Split on `,`, strip surrounding whitespace
    from each slug, drop empty elements produced by a trailing comma. Compare
    each against the fixed slug set — this set is closed and is NOT resolved
    against the agent catalog, because lens slugs are not agent names.
    Preserve caller order; it determines dispatch order in §5A.4. Hard-fail
    on unknown slug, duplicate, or count > 5, naming the offending value.
    **If the trailing-comma tolerance drops every element** (e.g. `--lenses
    ,`), the result is zero slugs — treat this as step 2's "`--lenses` is
    present but empty" hard-fail, not as a silently satisfied "no lenses
    requested."
4. **Resolve `--mode <name>` (if present).** Scan for the mode file in this
   order, stopping at the first hit:
   1. `<repo-root>/.claude/multi-agent-review-modes/<name>.md` (project scope;
      `<repo-root>` = `git rev-parse --show-toplevel`, skipped when not
      inside a git repo).
   2. `<plugin-install-root>/modes/<name>.md` (user scope).

   Unknown mode → hard-fail with the union of mode-file stems found across
   both scopes (use this list to make the error actionable; if both
   directories are absent, say so).

   Parse the mode file's YAML frontmatter (the leading `---`-delimited
   block). Required keys: `name` (string; must equal the filename stem —
   mismatch is a hard-fail to prevent renamed-without-rewrite drift),
   `reviewers` (YAML list of strings, or a CSV string parsed per step 3).
   Optional key: `synthesizer` (single agent name). The body after the
   frontmatter is human-facing documentation and is ignored by the parser.
5. **Apply mode defaults.** If `--mode` was set:
   - When `--reviewers` is absent, use the mode's `reviewers` as the
     roster.
   - When `--synthesizer` is absent AND the mode declares one, use the
     mode's `synthesizer`.
   Explicit `--reviewers` / `--synthesizer` flags always win over the mode.
6. If `--reviewers` is still unset → use the default roster from §4.
7. If `--synthesizer` is still unset → use `knowledge-synthesizer`.
8. Validate every reviewer name AND the synthesizer name against `.claude/agents/*.md` (project) and the parked library `~/.claude/agents-parked/*.md` (activation required), resolving each per `refs/multi-agent/agent-catalog-lookup.md` — **a name matches on either the filename stem or the file's internal `name:` field**, since the two routinely differ and this skill's own §4 roster uses both shapes. Matching on one shape alone rejects valid names: `architect-review` and `security-reviewer` carry the internal names `architect-reviewer` and `security-reviewer`, so an internal-name-only check fails on the documented default roster. Unknown name → hard-fail before spawning anything, with the list of known agent names. (This step catches typos in mode files for free — the mode's reviewer list is validated by the same union.)
9. **Resolve `--prompt-prelude <path>` (if present).** Resolve `<path>` to
   absolute (relative to `git rev-parse --show-toplevel` when not already
   absolute). Hard-fail if the path does not exist, is not a regular file,
   or exceeds 16 KB (`stat -c%s` / `wc -c`). On success, read the file's
   contents into the `{{PROJECT_PRELUDE}}` placeholder string used by the
   reviewer brief (§5A.3, §7) and the synthesizer brief (§5A.6, §8). When
   `--prompt-prelude` is absent, `{{PROJECT_PRELUDE}}` resolves to the
   empty string AND the surrounding `## PROJECT PRELUDE` block is stripped
   from the brief template before dispatch (no orphan heading).
10. **Resolve the report path (early).** This step defines path resolution for
   the whole skill; every later stage reads the resolved value and none
   re-derives it. It runs here for a one-shot pass, and is invoked verbatim by
   §5B step 1 for a loop run (the coordinator never enters §5A, so it must
   reach this step from there — see that step).
   **`<git-root>` is the primary checkout:** the parent of
   `git rev-parse --path-format=absolute --git-common-dir`. It is the base for
   the default report path below and every `.claude/reviews/` checkpoint
   directory. Never use `--show-toplevel` for these: inside a linked worktree
   it is the worktree, and a recycled worktree takes the report and its
   checkpoints with it. `--write-to` keeps its own resolution below.

   **Inside a git repo, keep `<git-root>/.claude/reviews/` ignored**, `--no-write` included (it
   still writes checkpoints). If `git check-ignore -q` on it fails, append
   `/.claude/reviews/` to `<git-common-dir>/info/exclude` (local to this
   clone, shared by every worktree, never committed), then re-check. If it is
   still not ignored (a tracked `.gitignore` negation outranks `info/exclude`),
   write anyway and say so in the closing output; never claim it is ignored.

   Skip the rest of this step if `--no-write` was passed. If both `--write-to`
   and `--no-write` were passed → hard-fail at parse time (§11).

   - **`--write-to <path>` set** → resolve `<path>` to absolute (relative to
     `git rev-parse --show-toplevel` if not already absolute), then
     **canonicalize it and require the result to sit inside the git root** —
     reject a path that escapes via `..`, an absolute path outside the repo, or
     a symlink pointing out of it. The flag names where a report goes, not an
     arbitrary write primitive, and the invoking flags are often composed by an
     agent from text it read (a PR body, an issue) rather than typed by a human.
     If the destination file exists AND `--force` is NOT set → hard-fail HERE.
   - **otherwise (the default)** → derive a slug from the target:

     | Target | Slug |
     |---|---|
     | `pr <n>` | `pr-<n>-review` |
     | `dir <path>` | `dir-` + the path with any trailing slash dropped + `-review` |
     | `file <path>` | `file-` + the basename without its extension + `-review` |
     | `spec <paths…>` | `spec-` + the first basename + `-review`, plus `-plus-<n-1>` when more than one path |
     | `diff` | `working-tree-review`, or `staged-review` with `--staged` |
     | `slices a/ b/ …` | `slices-<first>-<last>-review` |

     The target type is part of the slug deliberately: `dir api/` and
     `file api.py` would otherwise both reduce to `api-review`, and with the
     date prefix as the only discovery mechanism, two same-named reports
     distinguished by nothing but a `-2` are unfindable.

     Then normalize, in this order: lowercase; collapse every run of
     non-alphanumerics to a single `-`; trim leading and trailing `-`;
     truncate to 60 chars on a `-` boundary. **Normalization is derivation, not
     rewriting** — the strings above are computed from the target, never typed
     by a caller (there is no `--slug` flag), so there is nothing to reject.
     If the result is empty or a bare `-` — possible when a path is entirely
     punctuation — fall back to `<target-type>-review` rather than failing; a
     completed review must never be discarded over its filename. Sanity-check
     the final value against `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`; a miss means
     the normalization above was applied wrongly, so re-apply it rather than
     aborting. The path is
     `<git-root>/.claude/reviews/$(date +%Y-%m-%d)-<slug>.md`. If that file
     already exists, append `-2` (then `-3`, …) until it does not — do NOT
     refuse, and do NOT require `--force`, for a path the caller never chose.
     Give up after `-20` and fall back to appending `$(date +%H%M%S)`, so a
     pathological directory can't spin the search forever.
   - **Not in a git repo** (`git rev-parse --show-toplevel` fails) → resolve
     against `$PWD` and warn once on stderr: `warning: not in a git repo;
     writing report under <cwd>/.claude/reviews/`. Do not hard-fail — a missing
     canonical root is not a reason to discard a review.

   Both branches run before any reviewer agent is spawned: discovering an
   overwrite conflict at write time would waste N reviewer + 1 synthesizer
   agent calls.

**Mode-file shape** (one file per preset, frontmatter-only parser):

```yaml
---
name: security
description: Security-focused review using boundary, money-flow, and OWASP lenses.
reviewers:
  - security-reviewer
  - security-reviewer
  - silent-failure-hunter
synthesizer: knowledge-synthesizer   # optional; omit to inherit the §4 default
---

Free-text body — rationale, when to use, caveats. The parser only reads
frontmatter; the body is purely human-facing.
```

`reviewers` accepts a YAML list (shown above) or a single CSV string
(`reviewers: "a, b, c"`). Both forms feed the same validation as
`--reviewers`.

### 5A.2 Resolve materials per target type

Each branch produces a **materials block** — a self-contained string that every reviewer brief will embed verbatim. Reviewers receive NO shared conversation state, so the materials block is the only way they see the target.

| Target type | Resolution steps |
|---|---|
| `pr <n\|url>` | If `gh` is not on PATH → hard-fail with install instructions. Run `gh pr view <ref> --json number,title,body,headRefName,baseRefName,files,author,url`. Run `gh pr diff <ref> --patch` (the `--patch` flag pins unified-diff output; do not rely on the default format) — if `gh pr diff` exits non-zero or emits an empty diff, hard-fail with the `gh` error output (do not proceed with an empty materials block). From the JSON, extract each changed file's path and resolve to absolute (relative to `git rev-parse --show-toplevel`). For fork PRs, files in the PR's file list may not exist in the local checkout; for any such file, include only its diff hunk in the materials block and note "file not available locally; review from diff only" — do NOT instruct reviewers to `Read` a path that does not exist on disk. If the diff exceeds 100 KB, emit a single-line warning to stderr and proceed without truncation. Materials block contains: PR metadata table, full diff, and the file list with absolute paths and an explicit instruction to read each in full. |
| `dir <path>` | Resolve to absolute. **Verify the path exists and is a directory** before invoking `git ls-files` — if it does not exist or is not a directory, hard-fail with the missing/invalid path. (An absent path silently produces an empty `git ls-files` output, which would yield a vacuous review.) Run `git ls-files <path>` (respects `.gitignore`). If the file count exceeds the cap (default 50, override via `--max-files`), abort with a message listing the count, the cap, **and the `--max-files <n>` override flag**; do not proceed. Materials block contains: the directory's absolute path, the file list with absolute paths, and an instruction to read each in full. |
| `file <path>` | Resolve to absolute. Verify the file exists and is readable. Reject if more than one path is given. Materials block contains: the absolute path and an instruction to read it in full. |
| `spec <p1> [<p2> ...]` | Resolve each path to absolute. Verify each exists and is readable. Materials block contains: the list of absolute paths and an instruction to read each in full. |
| `diff` (no paths) | Verify the cwd is inside a git repo (`git rev-parse --show-toplevel`). Run `git diff` (or `git diff --staged` if `--staged` was passed) — capture stdout. If the diff is empty, hard-fail with: `diff target has no changes` (or `... --staged hunks` when `--staged`). If the diff exceeds 100 KB, emit a warning to stderr (same threshold as PR diff) and proceed without truncation. Also enumerate changed files via `git diff --name-only` (with `--staged` when applicable) and resolve to absolute paths. Materials block contains: the diff mode label (`working-tree` or `staged`), the full diff, and the file list with absolute paths plus an instruction to read each in full (reviewers may want full-file context, not just hunks). |
| `slices <p1> <p2> [<p3> ...]` | **Fan-out target.** Each path is treated as its own `dir`-style sub-target — resolve each to absolute, verify each is a directory, run `git ls-files` per slice, enforce the same `--max-files` cap per slice (not globally). Reject if slice count exceeds `--max-slices` (default 6). Build one materials block PER SLICE (same shape as a `dir` materials block), labelled with the slice's relative path from `git rev-parse --show-toplevel`. The dispatch step (§5A.4) and synthesis step (§5A.6) treat slices specially: every reviewer runs once per slice in parallel, and a single cross-slice synthesizer merges all `len(roster) × len(slices)` outputs into one report organised by slice. |

> **Reviewer tool requirements:** For `dir`, `file`, and `spec` targets, the materials block delegates file reads to the reviewer agents. **Reviewer agents must therefore have `Read` (and `Glob`/`Grep` for `dir`) in their own `allowed-tools` frontmatter.** The skill's `allowed-tools` governs only the orchestrator. If a reviewer lacks `Read`, it will return an empty or hallucinated report; verify each rostered reviewer's `allowed-tools` before opting an unfamiliar agent into the roster. Alternative: embed the file contents directly into the materials block (this skill currently does not, to keep brief size bounded).

### 5A.3 Build reviewer briefs

For each reviewer in the roster, expand the [Reviewer brief template](agent-briefs.md#7-reviewer-brief-template) with the values resolved above. The brief must be self-contained — the agent will not see this skill's conversation.

**Placeholder values to fill in:**

| Placeholder | Source |
|---|---|
| `{{REVIEWER_NAME}}` | The reviewer's agent name (the current entry in the roster). For a lens slot, `{{REVIEWER_NAME}}` is `lens:<slug>` (e.g. `lens:pre-mortem`) — `subagent_type` still dispatches as `general-purpose`; only the brief's self-identification and every downstream reference that keys off it (the §5A.4 dispatch description, the §5A.5 output-collection key, the §8 `### Reviewer:` heading, and per-finding attribution) use the `lens:<slug>` form. |
| `{{TARGET_TYPE}}` | The resolved target type from §5A.1 (`pr` / `dir` / `file` / `spec` / `diff` / `slices`). |
| `{{MATERIALS_BLOCK}}` | The materials block from §5A.2 (verbatim, same for every reviewer in a non-`slices` invocation; per-slice for `slices`). |
| `{{REVIEWER_ROLE_DESCRIPTION}}` | The reviewer's role description (see resolution rule below). |
| `{{REASONING_STANCE}}` | The verbatim steel-man preamble from `refs/multi-agent/reasoning-lenses.md` ("The steel-man preamble"). Present only when `--lenses` is non-empty — in that case injected into every brief this pass builds, lens slots and ordinary code reviewers alike. When `--lenses` is absent, strip the entire `## REASONING STANCE` block (heading + body) from the template before dispatch — no orphan heading. |
| `{{PROJECT_PRELUDE}}` | The contents of the `--prompt-prelude` file from §5A.1 step 9. Empty string when the flag is absent — in that case strip the entire `## PROJECT PRELUDE` block (heading + body) from the template before dispatch. |
| `{{SLICE_LABEL}}` | For `slices` only: the slice's relative path from repo root (e.g., `src/foo/domain/`). For all other targets, strip the `## SLICE` block from the template. |

When expanding the template, **strip every line that begins with `#` from
the body of the template itself** — those `#`-prefixed lines are
annotations to the skill author about where each placeholder comes from
and should not be sent verbatim to the agent. (Lines beginning with `##`
that are real markdown section headings in the brief are kept; only the
single-`#` annotation lines that immediately follow a placeholder are
stripped.)

For `{{REVIEWER_ROLE_DESCRIPTION}}`:
1. Attempt to read `.claude/agents/<reviewer-name>.md` (project scope).
2. If absent, try `~/.claude/agents/<reviewer-name>.md` (user scope).
3. If both absent (e.g., built-in agent) → use the literal fallback string: `"Apply your standard review lens to the materials above."`
4. If found → extract the first non-empty, non-heading block of the agent
   definition's body. "Body" = everything after the closing `---` of the
   frontmatter. **Skip any lines matching `^#+ ` (markdown headings)**
   when locating the first paragraph, since many agent files open with
   a `# <Name>` heading that is not the role description. The first
   paragraph is the first run of consecutive non-empty, non-heading
   lines after the frontmatter, terminated by a blank line.

**Reasoning lenses.** When `--lenses` is non-empty, build one additional brief per slug, in
caller order, on top of the roster briefs. Each lens brief is the standard template with two
differences: `## YOUR ROLE` is the slug's verbatim directive from
`refs/multi-agent/reasoning-lenses.md` (replacing the agent-definition lookup), and the target
is described as the document under review rather than a diff to critique. Independently, inject
`## REASONING STANCE` — the steel-man preamble — into **every** brief this pass builds,
including the ordinary code reviewers, because the stance governs the whole pass and not just
the lens slots. When `--lenses` is absent, strip the stance block from every brief.

### 5A.4 Spawn reviewers IN PARALLEL

> ⚠️ **PARALLELISM RULE — DO NOT SERIALIZE**
>
> All reviewer `Agent` tool calls MUST be issued in a SINGLE assistant message containing N parallel tool invocations. Do NOT spread them across multiple turns. If the roster has N reviewers, the orchestrator message contains exactly N `Agent` tool uses, all dispatched together.
>
> **Before issuing the batch, write down `dispatched` — the number of `Agent` calls this message
> contains.** Not the planned width `(N + L) × M`, which diverges from it whenever a lens or
> reviewer was re-dispatched or a safety-net name was dropped from the roster (§4): count the calls
> you are actually about to issue, and add to that count on any later re-dispatch in this pass.
> §5A.5 compares this number against what came back, and it cannot be reconstructed afterwards —
> recomputing the formula gives the planned width, and counting the collected map gives equality
> unconditionally. Capture it here or the check downstream is decorative.
>
> Each call MUST set:
> - `subagent_type` to the reviewer's agent name.
> - `description` to `"Multi-agent review: <reviewer-name>"` (for `slices`, append ` (<slice-label>)`).
> - `prompt` to the fully-expanded reviewer brief (see §7).
> - **`run_in_background` to `false`.** Not optional, and the single most load-bearing field on this call.
>
> **⚠️ PARALLEL DOES NOT MEAN BACKGROUND — `run_in_background: false` on every worker dispatch.**
>
> The Agent tool runs subagents in the **background by default**, and a background child's completion notification is delivered to the **top-level session**, not to the agent that spawned it. So an orchestrator that dispatches background reviewers has nothing left to do the moment the dispatch message is sent: its turn ends, it returns something like *"waiting on the reviewers to report back"*, and it is **never re-invoked**. §5A.5 (collect), §5A.6 (synthesize), and §5A.6a (report audit) then never run at all. The caller receives no report, the reviewers' findings land in the caller's context one notification at a time, and the entire fan-out is paid for with no consolidation.
>
> Observed failure rate before this was specified: **3 of 4** one-shot runs. It presents as the orchestrator "hanging" or "dying"; it is neither. It ran exactly once, correctly, and stopped — because nothing told it to wait.
>
> `run_in_background: false` is what makes the orchestrator's turn survive until every reviewer has returned. It does **not** serialize anything: N blocking calls issued in one message still run concurrently. Parallelism comes from the single-message rule above; blocking comes from this flag. Both are required.
>
> **Note:** `subagent_type` must match an available agent type at runtime (as registered by the Claude Code Agent tool — typically derived from the canonical filename of an active `.claude/agents/*.md` or `~/.claude/agents/*.md` file). If an invalid value is passed, the Agent tool will reject the call. The parse-time validation in §5A.1 reads the same on-disk agent files and is meant to catch this before dispatch, but the Agent tool's live schema is the ultimate authority.
>
> **`slices` dispatch shape.** For a `slices` invocation with roster size N and slice count M, the single dispatch message contains **N × M** `Agent` tool uses, one per (reviewer, slice) pair, all issued together. Build one fully-expanded brief per pair using the slice's per-slice materials block (§5A.2) and the slice's label as `{{SLICE_LABEL}}`. Do not serialise slices: a 3-reviewer × 5-slice review must spawn 15 agents in one assistant message, not 5 sequential 3-agent messages. The `--max-slices` cap (default 6, override per §3) bounds the explosion.

**Lens slots spawn in the same parallel batch as the roster reviewers** — they are reviewers,
not a separate stage, and serialising them would add a barrier for no benefit. Every lens slot
dispatches with `subagent_type: general-purpose`; lens slugs are never resolved against the
agent catalog.

> ⚠️ **A LENS SLOT THAT FAILS TO SPAWN IS NOT A DEGRADED RUN — IT IS A DIFFERENT RUN**
>
> `--lenses` is requested capability, not roster padding. A run that produces zero lens slots
> emits a report that is **byte-for-byte shaped like a normal review**: correct sections, real
> findings, nothing missing that a reader would notice. That is precisely the silent no-op this
> whole feature exists to eliminate, reappearing inside it. A `## Notes` bullet at the bottom of
> a 400-line report is not sufficient loudness for it.
>
> **Observed, 2026-08-20:** all four lens slots in an 8-agent batch were refused with
> `Concurrent subagent limit reached… Do not retry.` The batch was well under the documented
> 16-agent ceiling — the harness counts concurrency **session-wide**, not per message, and other
> agents held the slots. Retrying after the roster returned succeeded on the first attempt.
>
> On a refused lens spawn:
>
> 1. **Re-dispatch the refused lens slots once**, in a second single-message batch, after the
>    first batch returns, **each with `run_in_background: false`** exactly as the first batch. This
>    is not a retry against a full pool — the roster returning is what frees the slots, so the
>    precondition has materially changed. Do not spin: exactly one re-dispatch, no backoff loop.
> 2. **If any lens slot is still refused after that re-dispatch, HARD-FAIL the run.** Emit no
>    report. The message names each lens that could not spawn and tells the caller to re-run with
>    fewer concurrent agents. A caller who asked for `pre-mortem` and got a normal code review is
>    strictly worse off than a caller who got an error.
> 3. **If some lenses ran and others did not** — only reachable when step 2's hard-fail is
>    deliberately overridden — the **first line of the Executive Summary** names which lenses ran
>    and which did not, in addition to the `## Notes` bullet. Bottom-of-report is where this
>    information goes to die.
>
> **A rostered code reviewer that fails to spawn gets the same treatment — steps 1 and 2 apply to
> it unchanged.** This used to be carved out as "a genuine degraded run" whose right weight was a
> `## Notes` bullet. That carve-out was wrong and is withdrawn. The argument for it was that the
> review still happened and one lane is merely thinner, but the reasoning in the callout above
> does not depend on the slot being a *lens*: a run that silently loses `security-reviewer` also
> emits a report byte-for-byte shaped like a normal review, and a reader who is not diffing the
> roster against the Coverage Report will never notice. That is the same silent no-op, and it has
> shipped — PR #53 lost 3 of 5 rostered reviewers to name-resolution failures with nothing in the
> output saying so.
>
> Re-dispatch the refused reviewers once after the first batch returns, then hard-fail naming each
> reviewer that could not spawn. The one case that is genuinely a degraded run rather than a
> failed one is `penetration-tester` missing from the pool entirely (§4's safety-net carve-out) —
> that is a roster-resolution outcome settled at parse time in §5A.1, not a refused dispatch, and
> it is unaffected by this rule.

**Check the dispatch width against live capacity before issuing the batch.** The single-message
rule above has no ceiling of its own, and `(N + L) × M` reaches 66 at documented defaults
(roster 6, lenses 5, slices 6) against a session-wide cap of 16. The cap is shared with every
other agent running in the session, so the usable budget is unknowable at authoring time and
routinely smaller than the nominal limit. If the computed width exceeds the ceiling, hard-fail at
parse time (§5A.1) naming the width and the cap — do not discover it one refused `Agent` call at
a time, which is how a partial batch turns into a report that reads as complete.

**On a `slices` target, a lens slot runs once per slice, exactly like any other reviewer** — the
dispatch shape stays `(N + L) × M` for `N` roster reviewers, `L` lens slots, and `M` slices, built
from the same per-slice materials block and `{{SLICE_LABEL}}` as the rest of that slice's batch.

### 5A.5 Collect outputs

After all reviewers return, capture each reviewer's output verbatim, keyed by reviewer name in the order they appeared in the roster. Do not edit, summarize, reformat, or filter at this stage.

#### Reconcile the count before doing anything else

> ⚠️ **DISPATCHED AND RETURNED ARE TWO NUMBERS. COMPARE THEM.**
>
> Take `dispatched` from the count §5A.4 recorded before issuing the batch — including any
> re-dispatch it added. Then count `returned`. These two numbers are the only evidence the run has
> that its fan-out actually happened.
>
> Collection is keyed by reviewer name, so a reviewer that never returns produces a **missing
> key, not an error**. Every downstream stage reads the map it is handed and reports confidently
> on whatever is in it. That is how a run that dispatched six reviewers and heard back from one
> produces a report indistinguishable from a clean six-reviewer review.
>
> **`returned` counts pairs that produced a result — empty or not. It never counts a pair you
> filled in yourself.** Two different things can leave a lane with no findings, and conflating
> them defeats this entire step:
>
> | Lane state | Counts toward `returned`? |
> |---|---|
> | Agent ran and returned a report | **Yes** |
> | Agent ran and returned successfully but empty | **Yes** — the lane ran and found nothing, which is a real outcome |
> | Agent was refused at dispatch | **No** |
> | Agent accepted the dispatch and never returned | **No** |
>
> **Compare the two numbers now, before writing anything into the map.** Filling holes first and
> counting afterwards makes `returned == dispatched` true by construction and turns this gate into
> a no-op — it would reproduce, one layer down, the exact silent-loss failure the step exists to
> stop.
>
> | Condition | Action |
> |---|---|
> | `returned == dispatched` | Proceed to §5A.5a / §5A.6. |
> | `returned < dispatched`, and the missing agents were **refused at dispatch** | §5A.4's re-dispatch-once-then-hard-fail rule already governs; you should not reach here. |
> | `returned < dispatched`, missing agents **accepted the dispatch and never returned** | **HARD-FAIL the run.** Emit no report. Name each missing reviewer and slice. The correct response is to fix the dispatch, not to synthesize around the hole. |
> | `returned > dispatched` | Hard-fail. You are collecting output from something this pass did not dispatch — most likely notifications from a previous run's background children leaking into this turn. |
>
> **Only after the comparison passes**, write the sentinel — exactly `[FAILED — no output]` — into
> the map for any lane that returned *empty*. Those are the only lanes that reach the synthesizer
> without content, because every other hole has already hard-failed the run above. The sentinel is
> a label on a lane that ran and produced nothing, never a placeholder for a lane that went
> missing.
>
> **Carry both numbers forward.** Pass `dispatched` and `returned` to the synthesizer alongside
> `{{N_REVIEWERS}}`, and require the Coverage Report to open with the line
> `Reviewers: <returned>/<dispatched> returned`. A count in the report is what makes the next
> failure of this kind visible in the artifact instead of only in a transcript nobody re-reads.

**Checkpoint each output to disk as it is collected (R12, ClaudeConfig#172).** For every reviewer, write `<git-root>/.claude/reviews/<slug>/<reviewer-name>.json` (same `<git-root>` and `<slug>` as the report path, §5A.1 step 10 — the primary checkout, never a linked worktree) with `{"agent", "target", "round": null, "collected_at", "output"}` where `output` is the verbatim return text. Write each file the moment that reviewer's output is in hand — not after synthesis — so a failed synthesizer, a dead orchestrator, or a "background agents are finished" standoff loses nothing. These are working artifacts, not deliverables: never `git add` them, and they are exempt from `--no-write` (which governs the *report*). If the directory cannot be created, note it once and continue — checkpointing must never fail the run.

For `slices` targets, key each output by `(slice-label, reviewer-name)` so the synthesizer can render findings under per-slice subheadings. Preserve slice order from the command line and reviewer order from the roster — both are deterministic inputs to the cross-slice synthesis.

### 5A.5a Adversarial refutation stage

Runs after §5A.5 and before §5A.6, on every target, **only when `--adversarial` was passed**. Skip this entire section otherwise and go straight to §5A.6 — that is the default path. Its job is to make each finding survive an attack on its *truth*, independently of the synthesizer's later judgment about its *priority*.

**Boundary against the synthesizer.** This stage does not consolidate, rank, or apply the severity budget — `refs/multi-agent/fanout-consolidation.md` assigns that to the synthesizer, and the orchestrator must not do dedupe in user-facing chat. The grouping in step 1 is internal bookkeeping used only to decide how many refuters to spawn and on what; it is never emitted as a report. The synthesizer still receives every reviewer's verbatim output (§5A.6) and remains the sole authority on the final consolidation.

#### Step 1 — Enumerate and group claims (internal)

Walk every reviewer's `### Findings` section and extract each finding as a **claim**: `(severity, file, line, one-line summary, cited evidence, suggested fix)`.

Group claims by `(file, line, root cause)` — the same key `fanout-consolidation.md` rule 1 uses. Each group is **one claim** for refutation purposes: three reviewers raising the same call site for the same reason get **one** refuter set, not three. Record which reviewers contributed to each group; that attribution travels to the synthesizer, not to the refuters.

Exclusions — these never enter refutation:
- **`critical-thinking` output.** Its items are assumptions and open questions, not severity-tagged claims (§9). There is nothing to refute: "the author hasn't stated how retries interact with the idempotency key" is a question, and attacking it produces noise. Its section passes through to the synthesizer untouched.
- **Anything already dropped by the exclusion list** (`--prompt-prelude`) — already suppressed upstream, per `exclusion-list.md` rule 5.
- **Findings from a reviewer that returned `[FAILED — no output]`** — there is nothing to extract.

When a group's severity differs across reviewers, use the **highest** (matching `fanout-consolidation.md` rule 2) to decide the refuter count.

#### Step 2 — Compute the refuter budget

```
refuters(CRITICAL) = refuters(HIGH) = --refuters          # default 3, range 1-5
refuters(MEDIUM)   = refuters(LOW)  = 2                   # fixed
planned = Σ over claim groups of refuters(severity)
```

If `planned > --max-refuters` (default 20), degrade **lowest-severity-first**: drop LOW groups from refutation, then MEDIUM, then HIGH, until `planned ≤ budget`. **CRITICAL groups are never skipped** — if CRITICAL alone exceeds the budget, run them all anyway and note the overrun rather than leaving a CRITICAL unverified.

**Within a tier, skip the most-corroborated groups first**, then break ties by `(file path, line)` ascending. Concretely: order the tier's groups by descending count of distinct reviewers that raised the group, and skip from the top until the budget clears. A tier is rarely cut whole — 40 LOW groups needing 39 refuters' worth of savings means 20 specific groups lose refutation, and *which* 20 must not be arbitrary or the same review run twice gives different reports.

The direction is deliberate and is the opposite of the severity budget's ranking. There, distinct-reviewer count is a tiebreak for *keeping* a finding (`fanout-consolidation.md` rule 3). Here it selects what to *skip verifying*, and the reasoning inverts: a claim three lenses independently reached is the one least likely to be a hallucination, so it is the cheapest to leave unchallenged. A claim exactly one reviewer raised is the likeliest false positive in the set — it is the last thing to give up refuters for.

Every skipped group is marked `UNVERIFIED` and passed to the synthesizer with that tag. **Never silently drop a group from verification** — an unverified finding and an upheld finding must be distinguishable in the report, or the stage's guarantee becomes a lie by omission. Emit one stderr line naming the counts: `refutation budget <n> exceeded (planned <p>); <k> LOW and <j> MEDIUM findings left UNVERIFIED`.

#### Step 3 — Assign lenses and dispatch refuters IN PARALLEL

Each refuter for a claim gets a **different lens**. Assign in this order, cycling if `--refuters` exceeds the lens count:

| # | Lens | The question it attacks | Technique (optional — see below) |
|---|---|---|---|
| 1 | **Evidence** | Does the cited `file:line` actually say what the finding claims? Read the real code. Quoting a line that does not exist, misreading a guard's polarity, or attributing behavior to the wrong branch all die here. | `thinking-skills:thinking-map-territory` — the claim is the map, the code is the territory; when they disagree the territory wins. |
| 2 | **Scope** | Is this in scope for *this* target? A pre-existing pattern untouched by the diff, a deliberate project convention, or a concern the prelude already excludes is not a finding against this change. | `thinking-skills:thinking-kepner-tregoe` — map what IS vs IS-NOT covered by this target; the boundary is exactly the scope question. |
| 3 | **Reachability** | Can the failure actually occur? Trace whether an attacker- or user-controlled path reaches the code, or whether an upstream validator, type constraint, or caller invariant already forecloses it. | `thinking-skills:thinking-red-team` when any `risk_flag` fired — it demands a *concrete reproducible path*, which is the reachability bar. Otherwise `thinking-skills:thinking-thought-experiment`, since red-team self-scopes to security/correctness and returns little on a non-risk finding. |
| 4 | **Severity** *(only at `--refuters` ≥ 4)* | Granting the finding is true and reachable — does the claimed severity hold, or is the real blast radius a tier lower? | `thinking-skills:thinking-second-order` — severity *is* a claim about downstream consequence; walk the chain rather than accepting the filed tier. |
| 5 | **Fix** *(only at `--refuters` 5)* | Would the suggested fix actually resolve it, or introduce a worse problem? A finding whose only fix is a regression is not actionable as stated. | `thinking-skills:thinking-via-negativa` — ask whether removal beats addition before crediting a fix that only adds. |

At the default `--refuters 3`, CRITICAL/HIGH get evidence + scope + reachability — no conditional, they always get all three.

**The Technique column is a sharpener, not a dependency.** Each lens names a `thinking-skills` skill that supplies an actual method for the question, instead of leaving the refuter to improvise one from a one-line prompt. Three rules govern it, and the third is load-bearing:

1. **The lens question is authoritative; the technique is optional.** A refuter that cannot load its skill still has a complete, self-sufficient brief. Nothing in the verdict arithmetic depends on the technique running.
2. **`thinking-skills` is a separate plugin** (`thinking-skills@thinking-skills-marketplace`) and is **not** a declared dependency of this one. Assume it may be absent — the reference is by name, resolved at refuter runtime, never preloaded here.
3. **A missing skill must not change a verdict.** If the skill will not load, the refuter proceeds on the lens question alone and rules normally. It must **not** return `UNCERTAIN`, and must not report tooling trouble as a finding-level result. This matters because `UNCERTAIN` upholds (§4): a refuter that downgraded itself over a missing plugin would silently bias the whole stage toward keeping findings, converting an environment gap into a review outcome. §7a states this to the refuter directly.

The mapping is per-lens, not per-finding — every refuter on a given lens gets the same technique regardless of severity or target.

**The MEDIUM/LOW pair is signal-dependent.** Both slots are 2, but which second lens joins evidence depends on the run's `risk_flags[]`, extracted per `refs/multi-agent/context-aware-selection.md` §4:

| Run's signals | MEDIUM/LOW lenses | Why |
|---|---|---|
| **any `risk_flag` fired** (keys/signing, money movement, irreversible action, external I/O, data-loss) | **evidence + reachability** | On a risk-flagged target, "is this path actually reachable?" *is* the question. Scope is near-useless here — a finding against a diff that moves money or touches keys is essentially always in scope, so the scope lens burns a slot to return UPHELD. |
| **no `risk_flag` fired** | **evidence + scope** | Off the risk path, the dominant false positive is the out-of-scope finding: a pre-existing pattern the diff never touched, or a project convention filed as a defect. Reachability rarely discriminates when nothing dangerous is reachable either way. |

Extract the signals per §4 of that ref **whether or not context-aware selection drove the roster** — the extraction reads the target, not the roster, so it is available even when `--reviewers` was passed explicitly. If signal extraction cannot run at all, **default to evidence + reachability**: missing a reachable vulnerability is a worse outcome than leaving an out-of-scope nit in the report, so the ambiguous case takes the security-leaning pair.

This costs no extra agents — it swaps which lens fills the second slot, never adds a third. `--refuters` does not affect it; that flag governs the CRITICAL/HIGH tier only.

Dispatch rules:
- **One message, N `Agent` calls**, same parallelism discipline as §5A.4, batched at the 16-per-turn ceiling.
- **`run_in_background: false` on every refuter**, for the reason spelled out in §5A.4: a background child notifies the top-level session rather than the agent that spawned it, so the dispatching turn ends immediately and step 4's tally never runs. Blocking does not serialize — the batch still runs concurrently.
- `subagent_type` = `critical-thinking` unless the roster's own resolution supplies a better skeptic; `description` = `"Refute: <severity> <file>:<line> (<lens>)"`.
- `prompt` = the fully-expanded refuter brief (§7a). `{{LENS_NAME}}` and `{{LENS_QUESTION}}` come from the step 3 table's Lens and question columns; `{{LENS_SKILL}}` comes from its Technique column — resolve the reachability row against the run's `risk_flags[]` exactly as the MEDIUM/LOW pair is resolved. When a lens has no mapped technique, strip the `## YOUR TECHNIQUE` block rather than expanding it empty (no orphan heading).
- **Refuters are mutually blind.** No refuter sees another refuter's verdict, and none sees the other lenses' briefs. A shared verdict stream would collapse three independent samples into one anchored one.
- **Reviewer attribution is withheld.** The brief never names which agent raised the claim, and never says how many did. Both are authority signals that bias a skeptic toward upholding — "three reviewers found this" is social proof, not evidence.

#### Step 4 — Tally verdicts

Each refuter returns exactly one verdict: `REFUTED`, `UPHELD`, or `UNCERTAIN` (§7a). For each claim group, let `R` = refuters dispatched and `k` = count of `REFUTED`.

**`UNCERTAIN` counts as not-refuted.** See §4 — ambiguity fails toward keeping the finding.

The drop threshold is a **strict majority with a floor of two**:

```
drop_threshold(R) = max(2, ceil((R + 1) / 2))

R = 1 → 2   (unreachable: a lone refuter can never drop)
R = 2 → 2   (both must refute)
R = 3 → 2   (default tier)
R = 4 → 3   (a 2-2 tie contests, it does not drop)
R = 5 → 3
```

Two properties are load-bearing and neither survives the more obvious `k ≥ ceil(R/2)`: **no single refuter can ever delete a finding** (the floor of 2 — `ceil(2/2)` is 1, which would let one lens kill a MEDIUM), and **a tied panel contests rather than drops** (the `R+1` — `ceil(4/2)` is 2, which would drop on a 2-2 split).

| Condition | Outcome | Effect on the report |
|---|---|---|
| `k ≥ drop_threshold(R)` | **DROPPED** | Removed from the severity buckets. Rendered in full in the **Refuted Findings** section with every refuter's reasoning. |
| `0 < k < drop_threshold(R)` | **CONTESTED** | Kept, **demoted one level** (CRITICAL→HIGH, HIGH→MEDIUM, MEDIUM→LOW; LOW stays LOW), tagged `_(contested: k/R refuters refuted; demoted)_`. |
| `k = 0` | **UPHELD** | Kept at original severity, tagged `_(verified: R/R refuters upheld)_`. |
| group skipped in step 2 | **UNVERIFIED** | Kept at original severity, tagged `_(unverified: refuter budget exhausted)_`. |
| every refuter for the group failed or returned an unparseable verdict (§11) | **UNVERIFIED** | Kept at original severity, tagged `_(unverified: all refuters failed)_`. |

The two UNVERIFIED causes carry **different tags on purpose**. Budget exhaustion is a choice the run made and can be undone by raising `--max-refuters`; total refuter failure is a malfunction that says nothing about cost and may recur on a re-run. Collapsing them into one tag would tell a reader to raise a budget that was never the problem.

**CRITICAL is dropped by the same rule as any other severity — but never silently.** A majority-refuted CRITICAL leaves the Critical Findings section and appears, in full, under Refuted Findings with its refuters' evidence, and the Executive Summary must state the count. This is the one place where "dropped" is a rendering decision rather than a deletion: the human still reads it, one section lower, with the reason it lost. Note that a CRITICAL that *survives* refutation is never demoted by anything downstream either — `fanout-consolidation.md` rule 3 already exempts CRITICAL from the severity budget.

#### Step 5 — Hand off

Pass to the synthesizer (§5A.6) as `{{REFUTATION_VERDICTS}}`: one entry per claim group with its outcome, tag, per-lens verdicts and one-line reasoning, and contributing-reviewer attribution. The synthesizer applies the outcomes when rendering — it does **not** re-adjudicate them. Reviewer severity still wins over synthesizer opinion on individual findings (`fanout-consolidation.md` failure modes); refutation outcomes are the one exception, because they are evidence, not opinion.

### 5A.6 Invoke synthesizer

Expand the [Synthesizer brief template](agent-briefs.md#8-synthesizer-brief-template) with:
- `{{SYNTHESIZER_NAME}}` = the resolved synthesizer (default `knowledge-synthesizer`) — a role label only; the fork loads no definition (SKILL.md §8).
- `{{N_REVIEWERS}}` = the roster size.
- `{{DISPATCHED}}` / `{{RETURNED}}` = the two counts reconciled in §5A.5, passed through unchanged. The synthesizer renders them as the Coverage Report's first line; it never derives them from the reports it was handed, which cannot show it what is absent. On a `slices` target these are the `(N + L) × M` totals, not per-slice.
- `{{REVIEWED_AT}}` = the commit the review actually read, captured before the first reviewer is dispatched (`git rev-parse HEAD`, or the PR's `headRefOid` on a `pr` target). The synthesizer renders it on the Coverage Report's second line as `Reviewed at: <oid>` followed by `Any commit after this one is unreviewed.`

  **Why a report states the commit it read.** A review's findings get fixed, and the fixing moves the code. Some later agent then reads "all findings resolved" as "this code was reviewed" — and if the fix rounds, a refactor and a cleanup pass have landed since, nothing it is about to merge was reviewed by anything but CI. The report cannot prevent that, but naming its own subject makes the staleness checkable instead of invisible. A fix round is not a review of the fixes: the agent that applied them is not a second pair of eyes on them.
- `{{HIGH_CAP}}` = the resolved `--high-cap` value (default `8`; literal `off` when the caller passed `--high-cap off`). Parsed in §5A.1; values other than a positive integer or the literal `off` hard-fail before any agent is spawned.
- `{{TARGET_TYPE}}` = the resolved target type.
- `{{REFUTATION_VERDICTS}}` = the per-claim-group outcome table from §5A.5a step 5. When `--adversarial` was **not** passed — the default — this is the empty string AND the entire `## REFUTATION VERDICTS` block plus the `## Refuted Findings` section spec are stripped from the synthesizer brief before dispatch (no orphan headings, and no instruction to render a section that will always be empty).
- `{{PROJECT_PRELUDE}}` = the contents of the `--prompt-prelude` file (§5A.1 step 9). Empty string when absent — in that case strip the entire `## PROJECT PRELUDE` block from the synthesizer brief before dispatch (no orphan heading).
- `{{MATERIALS_BLOCK}}` = the same materials block from §5A.2. For `slices`, expand to the concatenation of every per-slice materials block, each preceded by a `### Slice: <slice-label>` heading and a `---` separator.
- `{{REVIEWER_OUTPUTS}}` = one line pointing at the reviewer returns the fork already holds verbatim (SKILL.md §8), never a retyped copy. Where returns must be written out as text (§5A.7's synthesizer-failure file), concatenate them: for non-`slices` targets, for each reviewer in roster order, insert a block of exactly this shape (literal text, no templating):

  ```
  ---
  ### Reviewer: <reviewer-name>
  <reviewer's verbatim output>
  ---
  ```

  For `slices` targets, group by slice first, then by reviewer:

  ```
  ===
  ## Slice: <slice-label>
  ===
  ---
  ### Reviewer: <reviewer-name>
  <reviewer's verbatim output for this slice>
  ---
  ### Reviewer: <next-reviewer-name>
  <…>
  ---
  ```

  Concatenate all blocks into a single string before substitution.
- `{{TARGET_LABEL}}` = a human-readable label for the target (e.g., `PR #42: <title>`, `directory core/`, `file SPEC.md`, `spec set: SPEC.md + SPEC-UPDATE-001-foo.md`, `working-tree diff`, `staged diff`, `slices: src/foo/domain/ + src/foo/application/ + …`).
- `{{SLICE_LIST}}` = for `slices` only, a comma-separated list of slice labels. For other targets, strip the `## SLICES IN SCOPE` block from the template.

Spawn the synthesizer as a single `Agent` tool call with `subagent_type: fork` (SKILL.md §8), `description` = `"Multi-agent review: synthesize"`, and **`run_in_background: false`** (§5A.4 — a background synthesizer returns its report to the top-level session instead of to this run, which is precisely the report this run exists to produce).

### 5A.6a Report adversary (on by default; `--no-report-audit` opts out)

Runs after §5A.6 and before §5A.7, on every target. **One agent, exactly once, never a fan-out.**

**This stage attacks the report, not the findings.** §5A.5a asks "is this claim true?" of each finding, against the code. This stage asks "is this document an honest rendering of what the reviewers and refuters actually produced?" — against the reviewer outputs and refutation verdicts. They are different questions with different evidence, and the second is unreachable before synthesis exists.

**Why here and nowhere else.** Every defect this stage catches is *introduced by synthesis itself* — dedupe, the `--high-cap` severity budget, refutation-outcome application, and Executive Summary composition all happen in §5A.6. Before that, there is no artifact to audit; after §5A.7, the report is already the user's. It is also the only check positioned to see a `--high-cap` demotion, since §5A.6 applies the budget and nothing downstream re-examines it.

**What it attacks** — synthesis fidelity, not code:

| # | Failure it hunts |
|---|---|
| 1 | **Refutation outcomes not applied.** A `DROPPED` group still sitting in a severity bucket, a `CONTESTED` one not demoted a level, an `UNVERIFIED` item rendered as though it were verified. |
| 2 | **Dedupe damage.** Two distinct root causes merged into one finding (one is now invisible), or one root cause split across entries so the count inflates. |
| 3 | **Severity-budget distortion.** A HIGH demoted to fit `--high-cap` rather than on merit — and, in loop mode, whether the cap was correctly forced `off` at all. |
| 4 | **Executive Summary drift.** Arithmetic that does not reconcile with the sections; a recommended action that contradicts the findings (e.g. "merge-with-fixes" above an unresolved CRITICAL). `merge` recommended while any `## Open Questions for the Author` entry is PENDING is drift; `merge-with-fixes` withheld solely because of a PENDING entry is not. |
| 5 | **Coverage inflation.** `Confirmed` entries with no citation, or contradicted by the same report's `Not examined` list. |
| 6 | **Attribution and loss.** A finding credited to a reviewer that did not raise it, or a reviewer finding that reached no section at all. |
| 7 | **Tag honesty.** `UNVERIFIED` presented as validated — the specific misreading §8's arithmetic rule exists to prevent. |

**Hard boundaries.** Violating any of these makes the stage worse than absent:

- **It does not re-adjudicate truth.** Whether a finding is real belongs to §5A.5a, which read the code; this agent has the report and the reviewer outputs, not a mandate to re-review. An audit item saying "I don't think this bug is real" is out of scope and must be discarded.
- **It adds no new code findings.** A defect it notices in the code is not its output; it is evidence the roster missed something, and it says so as a coverage observation, not as a new severity-tagged finding.
- **It never edits the report.** The synthesized body is relayed verbatim per decision #42. This stage only *appends* the `## Report Audit` section defined below. No re-ranking, no re-wording, no severity changes, no deletions.
- **It runs once.** No loop, no second pass, and nothing audits the auditor — a regress this stage deliberately does not open.

**Dispatch:** one `Agent` call; `subagent_type: fork` (SKILL.md §8), with the §7b brief as its whole role; `description` = `"Audit report: <target-label>"`; `prompt` = the expanded §7b brief; **`run_in_background: false`** (§5A.4). It receives the synthesized report, the verbatim reviewer outputs, and the refutation verdicts — the same inputs §5A.6 had, so it can check the transformation rather than take it on trust.

**Output** — append to the report, after its final section:

```
## Report Audit
```

One entry per issue: what the report says, what the source material says, and which failure class above it falls under. **Advisory only** — nothing here changes a severity or removes a finding; a reader decides. When the audit is clean, emit exactly one line: `No synthesis defects found.` — never an empty section.

**Failure handling.** If the audit agent fails or returns unparseable output, emit `## Report Audit` containing `Not run (audit agent failed).` and print the report normally. A failed audit **never** blocks the report — the review is the deliverable, and withholding it over a failed advisory check would trade a real artifact for a missing one.

### 5A.7 Print verbatim

Print the synthesized report verbatim as the final assistant message, with §5A.6a's `## Report Audit` section appended as its last section. Unless
`--no-write` was passed, prepend exactly one line — `Wrote: <absolute path>` —
followed by the verbatim report; otherwise emit no preamble and no
postscript. Closing lines are also defined, only for a written report file
that `git check-ignore` does not ignore (a `--write-to` tracked path, or §5A.1
step 10's ignore step failing): end with exactly `note: git does not ignore
<absolute path>`, and when the report names an unfixed CRITICAL or HIGH
security finding, follow it with exactly `note: this report names unfixed
security findings; keep the file out of a commit until they are fixed` (§4).

**"Verbatim" governs the synthesized body, not the artifact's length.** The audit section is part of the document this stage assembles, not commentary wrapped around it. Everything §5A.6 produced still appears unedited and in order; the no-preamble/no-postscript rule continues to forbid any text of your own outside these defined parts.

**When this pass is the dispatched orchestrator** (`--in-subagent` present),
"print" means *return*: with a report file, the return is the §7c summary and
the file holds this text; with no file, this text is the return, verbatim,
complete, no preamble, no postscript. The caller relays either unchanged (§5A.0).

When a report path is set (§5A.1 step 10 — the default; skipped only by
`--no-write`):
1. The path is already resolved and known writable at this point. (If an
   explicit `--write-to` destination existed and `--force` was not set, the
   skill exited early with no reviewer agents spawned; a default-path
   collision was already suffixed `-2`.)
2. Create parent directories as needed (`mkdir -p`).
3. Write the synthesizer's output to `<path>`.
4. Print the `Wrote: <absolute path>` line, then the synthesizer's output verbatim.

**Synthesizer-failure fallback:** if the synthesizer fails (see §11) AND a
report path was set, still write a file at `<path>`
containing a single header line noting the synth failure, followed by
each reviewer's verbatim output with delimiters. Better to persist the
raw reviewer outputs than to discard them by silently skipping the
write. Then print the same content to stdout (with the leading
`Wrote: <absolute path>` line).

**PR comment (one-shot `pr` target).** When the target is `pr` and
`--no-comment` was not passed, post exactly one comment carrying the same
report. Mechanics are §10.7 step 1's, unchanged — including `--body-file` with
the body written to a temp file first, **never** inlined into a shell argument.

One-shot-specific policy, which §10.7 does not cover: retry once on failure
(rate limit, permissions, network); if it still fails, print the comment body
with a note that it could not be posted, so the record isn't lost. This applies
to `--no-loop` runs and to any `pr` target that reached §5A rather than §5B; a
looping run comments once via §10.7 instead, and an `--in-loop` inner pass never
comments (§4). `--no-write` suppresses only the file; `--no-comment` only the
comment.

### 5B. Loop machinery (mutating; `pr` target, default mode)

Reached when `mode == loop` — the preconditions and confirmation gate in §5.0 have already passed. The coordinator (you, the agent running this skill) runs a bounded review→fix→re-review loop against the open PR.

**The per-round protocol is [`loop-coordinator.md`](loop-coordinator.md) §10.1–§10.7. Load it and follow it exactly.** It is not restated here — an outline of §10 kept in this file is a second copy that drifts from the first, and the inner self-call grammar in particular must have exactly one authoritative statement (§10.2 step 2, with its fallback forms at step 2's last bullet).

Two things belong to §5B rather than §10, because they are the seam between the two:

1. **Resolve the report path before round 1**, by running §5A.1 step 10 exactly as written against the `pr` target. The coordinator never enters §5A (that section is `mode == oneshot` only) and every inner pass is forced to `--no-write`, so this is the *only* point in a loop run where the path gets resolved. Do it now, not at §10.7: a collision or an unwritable destination should surface before three rounds of fixes, for the same reason step 10 runs before the fan-out in one-shot mode. Skip if the caller passed `--no-write`.

2. **The pre-2.0 fallback chain is deleted, not deprecated.** `args="<n>"` → `args="PR <n>"` → no-args carried no `--no-loop`/`--in-loop`, so under the current default every one of those forms would recurse. The old chain assumed the inner skill was one-shot by default; that assumption is now false and inverted. §10.2 defines what the self-call must carry instead — the point here is only that a form which *looks* like a reasonable fallback is now a recursion bug.

