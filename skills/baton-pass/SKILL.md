---
name: baton-pass
description: Write a short "pass baton" note to baton-pass/ for the next session on this feature/epic. Triggers - "pass the baton", "write a baton-pass". NOT for a fresh-agent handoff document — see body.
---

# baton-pass

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Writes a short, append-only "pass baton" note to `baton-pass/<scope>/` so the
next session on this feature or epic can pick up cold. Use "pass baton" /
"baton-pass" phrasing for this, not "handoff" — a fresh-agent handoff document
that compacts an entire conversation is a different, separate skill.

| Option | Values | Default | Effect |
|---|---|---|---|
| `[feature-slug]` | kebab-case scope slug | derived from the current branch/phase name, or confirmed with the user | Selects the `baton-pass/<scope>/` subdirectory the note is filed under; an existing close match is reused rather than a new one created. |
| variant | `phase-closure` \| `mid-investigation` \| `blocked-on-external` | `phase-closure` | Chosen by the kind of work being closed out; selects which of the three note templates is used. |
| "commit it" / "save and push" | absent (default) or stated in the request | absent — write-only, no git action | When stated, stages and commits (and pushes, if asked) the new note + regenerated `INDEX.md` together instead of leaving them uncommitted. |

Sole authorized writer to `baton-pass/`. Enforces the directory's three hard
rules (see `baton-pass/CLAUDE.md`): timestamp-ordered filenames per
directory, feature/epic subdirectories, append-only.

**Vocabulary: "pass baton," never "handoff."** Use "pass baton" / "baton-pass"
in trigger phrases, filenames, and headings — never "handoff." If a request
uses the word "handoff" (e.g. "write a handoff", "hand off to a fresh agent"),
check first whether a dedicated handoff skill is installed and enabled for
this session (its own trigger vocabulary uses "handoff") — that is very
likely the better match, since a handoff document compacts an entire
conversation for a fresh agent with no prior context, whereas a baton-pass
entry is a short, scoped note in *this* repo's `baton-pass/` directory for
the next session working the same feature/epic. Only fall back to baton-pass
if no handoff skill is available. Do not let "handoff" phrasing leak into a
baton-pass entry's filename or `# Pass-Baton: ...` heading even then — the
skill's own vocabulary stays "pass baton" regardless of what the request said.

## Workflow

**Pre-step.** If `baton-pass/` does not exist at the repo root, create it
(`mkdir -p baton-pass`) before proceeding.

### 1. Determine scope

- **Feature/epic baton-pass** → goes in `baton-pass/<slug>/`.
  - **Slug derivation rule:** strip the task-specific suffix from the branch
    or phase name; keep the *module + category*, pluralized where natural.
    Examples: `feat/phase-3-domain-models` → `phase-3-domain` (drop the
    `-models` task suffix). The point is so a single subdirectory accumulates
    all baton-passes for that scope over its lifetime — never one subdirectory
    per task.
  - **List existing subdirectories first:** `ls baton-pass/ | grep -v '\.md$'`.
    If a close match already exists (case- or hyphen-insensitive), USE IT.
    Inventing `phase3-domain` when `phase-3-domain` already exists is the
    most common drift failure.
  - Only create a new subdirectory when no existing one matches. Confirm
    the name with the user if it's not derivable from a branch/phase.
- **Cross-cutting baton-pass** → goes at the top level of `baton-pass/`. Rare;
  reserved for seed entries, retrospectives spanning multiple features,
  and the like. The same `YYYY-MM-DDTHHMMSS-<slug>.md` filename format
  applies at the top level — only the location (no enclosing scope dir)
  differs.

If `baton-pass/CLAUDE.md` is absent (rare; the rules normally live there),
fall back to the three hard rules: timestamp-ordered filenames per
directory, feature/epic subdirectories, append-only.

### 2. Pick a template

Three variants — choose by the *kind* of baton-pass this is, not the project
phase. See [Templates](#templates) below.

| Variant | Use when |
|---|---|
| **phase-closure** | A clean unit of work just finished; next session picks up the next phase. Most common. |
| **mid-investigation** | Paused mid-debug; the next session needs your hypothesis tree, what was ruled out, what to try next. |
| **blocked-on-external** | Waiting on CI / review / external answer / a human decision. Short; mostly "what we're waiting for and why." |

### 3. Get the timestamp

```bash
date +%Y-%m-%dT%H%M%S
```

This emits `YYYY-MM-DDTHHMMSS` (e.g. `2026-07-26T143022`) — the exact form
used in the filename. Always run this — never rely on the session's
recollection of the date/time or on the model's pretrained "current date."
Long sessions go stale.

Timestamp filenames replace the old `NNN` sequential counter. Lexicographic
sort on `YYYY-MM-DDTHHMMSS` is chronological sort, so `ls` ordering is
preserved with no per-directory counter to compute or race on — this is
what makes concurrent writers (e.g. `/baton-runner-multi-agent` writing
several entries in parallel) safe: each writer's own wall-clock timestamp
is independent, unlike a shared `max + 1` counter that two writers can read
identically and then collide on.

- **Collision handling:** if a file with that exact second-resolution
  timestamp already exists in the target directory (two invocations within
  the same wall-clock second), increment the seconds field until the name
  is free — `...T143022` taken → try `...T143023`, then `...T143024`. This
  keeps plain lexicographic sort = chronological sort. (Do NOT append a
  `-2`-style ordinal before the slug: digits sort below letters, so
  `...T143022-2-beta.md` would sort BEFORE `...T143022-alpha.md` and the
  index would pick the older entry as latest.) This is the only case where
  you check for an existing file before writing.
- Existing legacy `NNN-YYYY-MM-DD-<slug>.md` entries are untouched and stay
  valid. Sort caveat: a lexicographic string sort places `000`–`202` before
  any `20xx-...` timestamp, but `203`–`999` would sort AFTER it (`"203" >
  "2026-"`). In practice legacy counters started at `000` and never
  approached 203, so timestamp entries sort last as intended; if a scope
  ever does carry a legacy entry ≥ 203, the index will keep showing it as
  latest — flag it to the user rather than renaming. Do not renumber or
  rename old entries — append-only applies to the directory as a whole,
  not just file contents.

### 4. Compose the filename

`YYYY-MM-DDTHHMMSS-<slug>.md` where `<slug>` is a 2–5 word kebab-case topic
identifier. The file slug names the topic of this specific entry; it is not
a verbatim repeat of the subdirectory name. (Overlap is fine — e.g.
`phase-3-kickoff` inside `phase-3-domain/` — but the file slug should add
information beyond the scope itself.)

### 5. Determine frontmatter fields

Before gathering state, derive the three frontmatter values that go at the
top of the file (see [Templates](#templates)):

- **`source`** — `human` if a person invoked this skill directly in an
  interactive turn this session (typed a trigger phrase, ran the skill
  themselves). `runner` if the invocation came from an automated
  multi-phase runner (`/baton-runner`, `/baton-runner-multi-agent`, or
  similar) acting on a queue without direct human interaction this turn.
  When in doubt, check whether the current call stack traces back to a
  runner skill's work-unit loop rather than a raw user message — if so,
  it's `runner`.
- **`scope`** — the same scope slug from [Step 1](#1-determine-scope): the
  feature/epic subdirectory name (e.g. `phase-3-domain`), or `top-level`
  for cross-cutting entries written directly under `baton-pass/`. Must
  match the directory the file is actually written into — never derive
  this independently.
- **`parent_session`** — the invoking session/conversation identifier if
  known (e.g. a runner's session ID or job ID passed down to this
  invocation). If no such identifier is available, use an empty string —
  do not guess or fabricate one.

### 6. Gather state

Before composing content, collect from the live repo (don't recall from
memory — verify):

- Current branch: `git branch --show-current`
- Worktree path: `git rev-parse --show-toplevel`
- HEAD: `git log -1 --format='%h %s'`
- Open PRs in scope: `gh pr list --state open --head 'feat/<scope-prefix>*'`
  (the `--search` flag matches PR title/body text, NOT branch names — use
  `--head` with a glob to filter by branch prefix when the scope maps to a
  branch convention; otherwise `--search` is acceptable but document that
  it searches title/body)
- Issues referenced: `gh issue view <n>` for each
- Verification results if any gate ran this session — paste actual output,
  not a description of what should have happened.

### 7. Write the file

Use the matching template from [Templates](#templates). Keep baton-pass entries
under ~150 lines — they are quick context, not full docs.

### 8. Regenerate `baton-pass/INDEX.md` via script

After writing the baton-pass file, **regenerate** `baton-pass/INDEX.md` by
running the packaged script instead of hand-rebuilding it in-context:

```bash
# Installed via `npx skills` (canonical copy in ~/.agents/skills/):
bash "$HOME/.agents/skills/baton-pass/scripts/regen-index.sh" baton-pass
```


Moving the regen procedure into a deterministic script — rather than having
the model re-derive the index by reasoning over `ls` output on every single
invocation — is what keeps this cheap: the script is idempotent (same
on-disk state → byte-identical `INDEX.md`) and can also be run standalone
(`baton-pass --reindex`-style, i.e. just invoke the script directly) without
going through the full skill workflow, e.g. after a bulk import or a manual
edit to `baton-pass/`. The script always rebuilds from scratch — never
patches in place — so no scope's row is ever silently truncated by a
partial update. It creates `INDEX.md` if it doesn't exist, and handles both
legacy `NNN-...` and new `YYYY-MM-DDTHHMMSS-...` filenames when finding each
scope's latest entry.

### 9. Completeness check

Before reporting "done," **re-read the file you just wrote** and verify
each item below against the actual file contents — never check from
memory of what you intended to write:

- [ ] HEAD short SHA + subject (from `git log -1 --format='%h %s'`)
- [ ] Branch name (current, even if not yet pushed)
- [ ] At least one link: PR, issue, or doc path
- [ ] At least one concrete next step with a file path or command
- [ ] Absolute date in `YYYY-MM-DD` form — no relative phrases
- [ ] Filename uses the full `YYYY-MM-DDTHHMMSS` timestamp, not a truncated
      or hand-typed one
- [ ] YAML frontmatter block present at the top of the file with `source`,
      `scope`, and `parent_session` all populated — `parent_session` may
      legitimately be an empty string; that is not a failure, only a
      missing/malformed `source` or `scope`, or a missing frontmatter block
      entirely, is
- [ ] `INDEX.md` updated (via `scripts/regen-index.sh`, not hand-edited)
- [ ] **Negative check:** content does NOT self-reference this skill,
      mention `baton-pass/`'s directory rules, or describe baton-pass
      meta-architecture — those belong in `baton-pass/CLAUDE.md`, not in
      individual entries.

A baton-pass missing the SHA or PR link is half-useful. The check costs ten
seconds.

### 10. Stop — do not commit by default

By default the skill **writes only** — it does not stage, commit, or push.
The user controls when baton-pass entries land.

**Exception:** if the user explicitly says "commit it", "include in the
commit", "save and push", or similar, commit (and push if requested) the
new baton-pass file + the `INDEX.md` update together as a single commit with
a message like `docs(baton-pass): <scope> — <one-line topic>`.

Never edit existing baton-pass entries — they are append-only.

## Templates

### phase-closure

```markdown
---
source: <human|runner>
scope: <scope>
parent_session: <id-or-empty>
---
# Pass-Baton: <one-line topic>

**Date:** YYYY-MM-DD
**Scope:** <scope>
**Branch:** <branch-name>
**Worktree:** <path>
**HEAD:** <short-sha> <commit subject>

## Where things stand

<One paragraph. What was accomplished, what is currently waiting, and on
whom or what. End with the literal current blocking state.>

## Next steps

1. <Concrete next action with file paths and/or commands.>
2. <...>

## Open questions / risks

- <Items the next session must resolve before proceeding, if any.>

## References

- PRs: #<n>
- Issues: #<n>
- Docs: `docs/<file>.md` §<section>
- Code: `src/<path>:<line>`
```

### mid-investigation

```markdown
---
source: <human|runner>
scope: <scope>
parent_session: <id-or-empty>
---
# Pass-Baton: <one-line bug or behavior under investigation>

**Date:** YYYY-MM-DD
**Scope:** <scope>
**Branch:** <branch-name>
**Worktree:** <path>
**HEAD:** <short-sha> <commit subject>

## Symptom

<What is failing or behaving unexpectedly. Paste the actual error / output.>

## Hypothesis tree

- [ ] **H1:** <hypothesis> — <status: ruled out / partially confirmed / untested>
  - Evidence: <what we observed>
- [ ] **H2:** ...
- [ ] **H3:** ...

## What's been ruled out

- <Things that were tried and did not change the symptom.>

## Best next probe

1. <The single most informative experiment to run next, and why.>
2. <Fallback if the first probe is inconclusive.>

## References

- PRs: #<n>
- Failing test / repro: `<path>` or `<command>`
- Related code: `src/<path>:<line>`
```

### blocked-on-external

```markdown
---
source: <human|runner>
scope: <scope>
parent_session: <id-or-empty>
---
# Pass-Baton: Waiting on <what>

**Date:** YYYY-MM-DD
**Scope:** <scope>
**Branch:** <branch-name>
**Worktree:** <path>
**HEAD:** <short-sha> <commit subject>

## Blocking signal

<What we're waiting for: a CI run, a review, an external answer, a
decision. Include the URL / PR number / person if applicable.>

## What's done and ready

<One paragraph: the work that's complete and parked, so the next session
can verify nothing has rotted before unblocking.>

## What to do when unblocked

1. <First action once the block clears.>
2. <...>

## Fallback if the block doesn't clear

- <Acceptable degraded path, if any.>

## References

- PRs: #<n>
- Issues: #<n>
- External: <URL / channel / person>
```

## Index format

`baton-pass/INDEX.md` structure — regenerated from disk by
`scripts/regen-index.sh` on every skill invocation (see Step 8; never
patched in place):

```markdown
# Pass-Baton Index

Latest entry per scope. Read the linked file for full context. New sessions
should start here.

| Scope | Latest | Date | Topic |
|---|---|---|---|
| phase-2-config | [2026-05-15T091500](./phase-2-config/2026-05-15T091500-pr7-ready.md) | 2026-05-15 | PR #7 ready for review |
| phase-3-domain | [2026-05-15T140212](./phase-3-domain/2026-05-15T140212-phase-3-kickoff.md) | 2026-05-15 | Phase 3 kickoff |

*(top-level seed: [2026-05-15T083000-start-baton-pass.md](./2026-05-15T083000-start-baton-pass.md))*
```

One row per scope, pointing at the *latest-sorting* file in that
subdirectory (legacy `NNN-...` and new `YYYY-MM-DDTHHMMSS-...` filenames
both sort correctly as plain strings). Older baton-pass entries in the same
scope are not listed in the index (they remain on disk and are reachable by
reading the latest one and following its `## References` upward). Pass
`--source human` or `--source runner` to the script to render a
writer-filtered index instead of the default unfiltered one.

## Gotchas

- **Scope ≠ branch.** Subdirectory slug is the *feature/epic* identifier,
  which may outlive a single branch. `phase-3-domain` covers both
  `feat/phase-3-domain-models` and any later `fix/phase-3-followup`.
- **No skill self-reference in baton-pass content.** Pass-Batons are for the
  next *engineering* session — never mention this skill, the `baton-pass/`
  directory rules, or meta-architecture. Those belong in
  `baton-pass/CLAUDE.md`.
- **Filenames are per-directory and timestamp-ordered.**
  `baton-pass/phase-2-config/...` and `baton-pass/phase-3-domain/...` each
  sort independently; there is no cross-directory counter. Legacy `NNN-...`
  entries from before this change stay in place and keep sorting correctly
  — do not renumber or rename them.
- **Frontmatter enables filtering without SQLite.** Every entry carries a
  `source`/`scope`/`parent_session` YAML frontmatter block so
  `scripts/regen-index.sh` can filter or split runner-written vs.
  human-written entries without a database — runner-driven automation
  writes far more frequently and can otherwise drown out human entries in a
  flat `ls`. The frontmatter `scope` must match the subdirectory the file
  is actually written into (or `top-level` for cross-cutting entries) —
  never let it drift from the real path. Legacy entries predate this field
  and simply have no frontmatter block; the script treats that as "unknown
  source" and only excludes them from a `--source`-filtered index, never
  from the default unfiltered one.
