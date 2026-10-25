---
name: claude-md-trim
description: Use when always-loaded agent context files (CLAUDE.md/AGENTS.md/GEMINI.md, and rules files with no `paths:` frontmatter) are long, noisy, or stale and need trimming to invariants + pointers, or when session/git logs should be mined for missing guidance; one repo or many.
---

# CLAUDE.md Trim — Signal-to-Noise for Always-Loaded Context

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Commits and opens a pull request per repo** — rebases onto the remote
> default branch first, then trims context files, commits, and opens a PR in
> a dedicated worktree/branch for each repo processed; nothing lands on
> default directly, but git history and GitHub PRs are created. Pauses for
> your approval before committing when more than 3 context files change.

Relocates and compresses always-loaded agent context files
(`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`, and rules files with no `paths:`
frontmatter) down to invariants and pointers, moving procedures, config
detail, and status write-ups into linked docs without changing any
invariant's meaning, proven by an instruction ledger. It also mines git and
session logs for guidance the context file is missing, verifies every carried-forward fact
against ground truth, and delivers the result per repo as its own worktree,
branch, and PR.

| Option | Values | Default | Effect |
|---|---|---|---|
| `PROJECTS` | one or more repo paths | current repo | Repos to trim; multiple are processed sequentially, one worktree/branch/PR each |
| `CONTEXT_FILES` | discovered automatically | `git ls-files '*CLAUDE.md' '*AGENTS.md' '*GEMINI.md'` per repo, plus every rules file with no `paths:` frontmatter (`git ls-files ':(glob).claude/rules/**/*.md'`; also `':(glob)rules/**/*.md'` when the repo is itself a `~/.claude` config directory) | Which always-loaded files get trimmed |
| `DETAIL_HOMES` | doc-path convention | repo's own convention if declared, else `docs/guide/<topic>.md` / `docs/progress/<module>-status.md` | Where relocated content lands |
| `EXCLUSIONS` | deprecated/slated-for-deletion modules, third-party files | none | Listed with a reason in the summary and left unedited |

## Overview

Context files (CLAUDE.md / AGENTS.md / GEMINI.md, and rules files with no `paths:` frontmatter) load into every session's prompt budget. Target state: **invariants + pointers only** — rules every code change needs, cross-module contracts, short gotchas, and links. Everything else moves to linked docs. The operation is **relocation + compression, never deletion**, and never changes an invariant's meaning.

**The litmus test for every line:** *does every code change in this repo need this loaded?* If not, it moves behind a link.

## When to Use

- A CLAUDE.md exceeds ~150 lines or contains: step-by-step procedures, verbose config tables, incident write-ups, shipped-feature changelogs, "next steps" sections, code examples.
- Facts in a context file contradict the code or a status doc (drift).
- When NOT to use: files that are already invariants + pointers; third-party/vendored files. (Modules slated for deletion are still in scope — they're handled via the EXCLUSIONS rule below: identified, listed with a reason, and left unedited, not skipped by not running the skill.)

## Inputs

| Parameter | Default |
|---|---|
| PROJECTS | current repo. Multiple: user lists repo paths — process each **sequentially and completely** (own worktree, own trim, own PR) before starting the next. Never share a branch or PR across repos. |
| CONTEXT_FILES | `git ls-files '*CLAUDE.md' '*AGENTS.md' '*GEMINI.md'` per repo, plus every rules file with no `paths:` frontmatter, since a rules file without it loads every session: `git ls-files ':(glob).claude/rules/**/*.md'`, and `':(glob)rules/**/*.md'` too when the repo is itself a `~/.claude` config directory |
| DETAIL_HOMES | the repo's own convention if declared (read the root context file's doc-hygiene rule — it overrides these defaults); else `docs/guide/<topic>.md` (how-to/reference) and `docs/progress/<module>-status.md` (status that drifts), created as needed |
| EXCLUSIONS | deprecated/slated-for-deletion modules, third-party-owned files — list them in the summary with the reason; do not edit |

## Per-Repo Process

**1. Base freshness (do this FIRST).** `git fetch`, then resolve `<default>` — `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` (fallback: `git remote show origin | sed -n 's/.*HEAD branch: //p'`) — then `git rev-list --left-right --count HEAD...origin/<default>`. Fast-forward or rebase onto the current remote default branch. A stale base silently trims content that no longer exists. Check for prior trim attempts (`gh pr list --search "CLAUDE.md trim"`): read them for scope hints only; start from today's default branch and state in the PR that this supersedes them.

**2. Isolation.** Dedicated worktree, feature branch, absolute paths. Never edit the default branch.

**3. Discovery.** Enumerate CONTEXT_FILES; record per-file line counts, plus tokens when the repo has its own budget script (e.g. `scripts/context-budget/check.py`) — the PR needs a before/after table, including untouched and excluded files with reasons. Take the "before" numbers in the trim worktree at `origin/<default>`, never in a checkout that carries other branches' edits. Read every in-scope file fully; note recent history (`git log --oneline -- <CONTEXT_FILES>`) — recent rewrites/renames change what "current" means. Before cutting or rewording any line, check its age first. In a shallow clone (`git rev-parse --is-shallow-repository` prints `true`) deepen before anything else (`git fetch --shallow-since=60.days origin <default>`), or every line looks new. Then run `git blame -w -M -C --since=30.days origin/<default> -- <file>` once per file; lines without a leading `^` are recent. A line that reached `origin/<default>` in the last 30 days is a decision: leave its wording unchanged (moving it verbatim behind a pointer is fine) unless the user says otherwise. When the only recent commit is a bulk rewrite or rename, such as a prior trim, look past it with `git log --follow` before treating its lines as new.

**4. Mine session + git logs for missing signal.** The trim removes noise; this step finds what the context files *should* say but don't. Sources:
- **Git log:** repeated fix subjects (`git log --pretty='%s' | grep -iE 'fix|revert' | sort | uniq -c | sort -rn`) — a defect fixed twice is a regression class worth a gotcha. Most-churned files (`git log --name-only --pretty=format: -150 | sort | uniq -c | sort -rn`) show where guidance drifts or is missing.
- **Session logs / transcripts** (e.g. `~/.claude/projects/<project>/*.jsonl`): aggregate tool errors (`is_error` results), user rejections, and correction-shaped user messages; also read any distilled auto-memory index. Aggregate with a script — never page raw transcripts into context.
- **Landing filter — a mined candidate is added only if it passes all three:** (a) verified against ground truth (read the actual fix commits / code before writing the gotcha); (b) not already documented at its point of use (a trap covered in the relevant skill/guide/tracked issue does not get re-added); (c) placed per the hygiene rule — gotcha/guide docs by default, the context file itself only if every code change needs it loaded.

**5. Classify each section (KEEP or MOVE), verifying everything carried forward:**
- **KEEP** (possibly compressed): invariants, safety rules, cross-module contracts, short gotchas, links. Compression must not change meaning. Scope words and qualifiers ("when", "only when", "already", "and others") carry the meaning: compress around them, never through them.
- **MOVE** to DETAIL_HOMES: procedures, setup, config detail, code examples, incident narratives, status sections. Create the target doc if missing; leave a one-line pointer + link.
- **VERIFY** everything before carrying it forward — check claims against ground truth (code, status docs, referenced files). Stale facts get corrected or dropped **with an explicit note in the PR**, never silently relocated or silently deleted. Dead links are never carried into new docs.

**6. Relocate, never delete.** Before dropping a section as "duplicated elsewhere," open the alleged duplicate and confirm it contains *every* fact — a file table's one-line purposes are not in an auto-generated tree; a summary is not the incident narrative. Anything the duplicate lacks moves there first. Preserve incident narratives and security-adjacent reasoning verbatim in their new home.

**7. Verify links.** Script a resolver over every touched file's relative links; it must print positive OK/MISS per link — an empty grep is not proof.

**8. Prove no invariant changed.** A fresh read-only subagent, given the old and new text of every changed or created file (including the DETAIL_HOMES docs that received moved text) and not your intent, builds an **instruction ledger**: every instruction, qualifier, exception and named entity in the old text, marked preserved, reworded, moved (with its new home), changed or dropped, plus every instruction in the new text with no source in the old, marked added. It then reads each new or reworded sentence without the old text in view: one that parses two ways is restored or rewritten. Restore every changed, dropped or added entry, except a stale fact corrected under step 5, which the PR lists with its evidence. When more than 3 CONTEXT_FILES change, show the user the ledger and the proposed cuts and wait for approval before committing.

**9. Regenerate derived artifacts** (architecture maps, catalogs, indexes) if the repo auto-generates them and you added/moved files.

**10. Deliver.** Commit; open a PR whose body contains: the ledger, and "no invariant changed, relocation only" only when the ledger has no changed, dropped or added entry other than step-5 corrections; the before/after size table (lines, plus tokens where step 3 measured them); sections moved + new homes (linked); mined additions with their evidence (commits/log aggregates); stale facts corrected with evidence; superseded-attempt note. Then move to the next repo, if any.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Dropping a section because "ARCH.md/openapi has this" without opening it | Verify the duplicate holds every fact; move the delta first |
| Trimming on a stale local base | Step 1 is mandatory, first, every repo |
| Fixing drift silently | Every correction is itemized in the PR with evidence |
| Moving a section, forgetting the pointer | Add pointer + link before touching the next section |
| Compressing an incident narrative "to its lesson" | The narrative moves verbatim; only the in-place stub is compressed |
| One mega-branch/PR across multiple repos | One worktree + branch + PR per repo, sequential |
| Trusting an empty grep as link verification | Positive per-link OK/MISS output required |
| Claiming "no invariant changed" from a skim of the diff | Step 8's ledger, built by an agent that did not write the trim |
| Compressing a qualifier away ("when implementing new features" → gone, so the rule now covers every task) | Keep scope words; the ledger catches the ones you miss |
| Rewording a line someone added on purpose last week | `git blame --since=30.days` each file before cutting, after deepening a shallow clone (step 3) |
| Measuring "before" in a checkout that carries another branch's edits | Measure at `origin/<default>` in the trim worktree |
| Trusting an empty grep during log mining | Verify the filter matches the log format on a known-present sample first — a false negative that confirms "nothing to find" is invisible |
| Relative paths in multi-repo/worktree shells | Shell cwd drifts between calls; use absolute paths and `git -C <abs-path>` for every mining and verification command |
| Re-adding a mined trap already documented at point of use | Check the relevant skill/guide/tracked issue before writing; mining output must pass the landing filter in step 4 |

## Multi-Project Runs

For N repos: complete steps 1–10 for repo 1 before opening repo 2. Emit one final cross-repo summary: per-repo PR links, size deltas, and any repo skipped (with reason). If a repo has no doc-hygiene convention, note that its PR introduces `docs/guide/` + `docs/progress/` so reviewers see the convention is new.
