---
name: wrapup-specs
description: Turns a weekly wrapup's recommendations, issue rows, and next steps into one implementation-ready improvement spec per project, written beside the wrapup.
argument-hint: "[isodate|folder]"
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
---

# Wrapup Specs

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Overwrites existing specs** — writes `<Project>-spec.md` files beside the
> wrapup, silently overwriting any spec already written for that week.

Converts a weekly wrapup's recommendations, issue rows, and next-step items into
one implementation-ready spec per project, written beside the wrapup it came
from. Runs non-interactively as part of `weekly-wrapup` (or via `/wrapup-specs`
directly) — not for general planning conversation or an ad hoc improvement idea.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<folder-or-date>` | absolute wrapup folder path, or a bare isodate (`YYYY-MM-DD`) | today's date | Selects which week's `wrapup.md` to convert into per-project specs |

> [!IMPORTANT]
> **Invoked by `weekly-wrapup` (step 9) or by `/wrapup-specs` directly.** Never auto-trigger
> from general talk about improvements or planning. This skill deliberately does **not** set
> `disable-model-invocation` — that flag would block the chained `Skill` call from
> `weekly-wrapup` — so the restraint is enforced here in prose instead.

Converts the diagnosis a wrapup produces into work a person or an agent can execute. The
wrapup says what is wrong; this says what to do about it, per project, in a form that
survives the session.

## Non-interactive by contract

This skill runs inside a headless `claude -p` cron invocation. It has **no approval gate and
asks no questions** — it makes the call and writes the file. This is why it does not delegate
to `spec-tacular`, whose Phase 2 is a hard human stop that would hang the scheduled run
forever. Ambiguity goes in the spec's *Open Questions* section, never back to the user.

## Steps

### 1. Resolve the target folder

- Argument may be a folder path (`/home/alex/WeeklyWrapup/2026-07-26`), a bare isodate
  (`2026-07-26`), or nothing. Nothing → use today's date (`date +%F`).
- The target file is `<folder>/wrapup.md`.
- Missing → report "no wrapup found at `<path>`" and **stop**. Do not fabricate a wrapup, and
  do not fall back to a different week.

**Done when:** an existing `wrapup.md` path is resolved, or its absence is reported and the
skill has stopped.

### 2. Extract improvement items

Read the wrapup completely. Pull work items from **exactly these three sources**:

1. The `**Recommendations:**` bullets under each of the four `## Week-over-Week Comparison`
   axes (Velocity, Code-quality signals, Friction points, Tool/skill usage).
2. Every row of the `## Potential GitHub Issues` table. The heading carries a parenthetical
   suffix naming the filing repo — `## Potential GitHub Issues (ClaudeConfig)`. Match the
   heading by prefix, and **ignore the suffix for attribution**: it says where an issue would
   be *filed*, not which project the work belongs to. Route every row through step 3 like any
   other item.
3. Every numbered item in `## Next Steps`.

Ignore `## Insights`, `## Standup`, `## Harness Audit`, and the `**Positives:**` /
`**Negatives:**` bullets. Harness-audit findings reach you as issue-table rows already —
reading the section too would file each one twice.
Those are *evidence* — quote them as justification later, but they are not work items.

A wrapup with no `## Week-over-Week Comparison` section (the first-ever run) still yields
items from sources 2 and 3.

**Done when:** every item from all three sources is captured with its source location.

### 3. Attribute each item to exactly one project

**Primary rule — the commit-target test.** For each item ask: *if I implemented this, which
repository would the resulting commit land in?* That repo is the project.

Judge by the **deliverable** — the thing being changed. Specifically **not**:

- **Not the instrument.** *"Run `zord-multi-agent-review pr 272 --yes` on BotHaus and force a
  merge/park decision"* → **BotHaus**. `zord-multi-agent-review` is the tool used, not the thing
  changed. A first-tool-name-wins scan would wrongly say Z0rd0nZords.
- **Not the evidence.** An issue row whose Body states a cross-repo policy but whose Evidence
  column cites specific PRs belongs to the repo the *policy* lands in, not the cited repos.
  The concrete per-PR actions are separate items belonging to those repos.

When the commit target is genuinely unclear, fall through these in order, first match wins:

| # | Deliverable touches | → Project |
|---|---|---|
| 1 | `CLAUDE.md`, `rules/`, `guides/`, `agents/`, hooks, `settings.json`, issue labels, `~/.claude/**` | ClaudeConfig |
| 2 | A skill, plugin, `SKILL.md`, command shim, or a named Z0rd0nZords plugin | Z0rd0nZords |
| 3 | Nothing identifiable — a process or habit item naming no artifact and no repo | ClaudeConfig |

Rule 3 is deliberate, not a dumping ground: ClaudeConfig is the process-of-record repo, so a
durable fix for a habit item lands there anyway. Do **not** invent a fifth "Process" project —
it would produce a spec no repo can consume.

Canonical project names, used verbatim in filenames, come from the `projects.json` read in
`weekly-wrapup` step 2.1 (`$WEEKLY_WRAPUP_PROJECTS`, default
`/home/alex/WeeklyWrapup/projects.json`) — never from a list written here. A repo named in a
wrapup but absent from that file still gets
a spec under its own name — do not force it into one of the four.

**Splitting.** An item whose deliverable genuinely spans **two or more** projects splits into
one requirement per project, each scoped to that project's slice. Never copy a whole item into
two specs. Example: *"file the issue rows … consider extending the `weekly-wrapup` plugin with
an opt-in filing pass"* → the filing habit becomes a ClaudeConfig FR, the plugin change a
Z0rd0nZords FR. A bundled item may split three or more ways, and two of its slices may both
land in the *same* spec as separate FRs — both are fine.

**Alternatives are not splits.** *"Add a CLAUDE.md rule **or** a `daily-loop` step"* offers two
competing implementations of **one** deliverable, not two deliverables. Do not split it —
attribute it to the first-listed option's project and note the alternative in that spec's
Implementation Plan. Splitting an either/or duplicates work that will only be done once.

**A tentative mechanism does not decide attribution.** When the alternatives are hedged —
prefixed `candidate:`, `consider`, `possibly`, or the row is labelled `needs-triage` — the
mechanism is explicitly unsettled while the *policy* is the actual deliverable. Attribute by
the policy (the fallback table), not by the first-named tool, and record the unsettled
mechanism as an Open Question. Only an unhedged alternatives list routes by first-listed
option.

**Done when:** every extracted item belongs to exactly one project, or has been split by
deliverable into per-project slices.

### 4. Consolidate per project

The same improvement recurs across all three sources by design — the Recommendations bullet,
the issue row, and the next-step item are usually one piece of work described three times.

- Merge them into **one** requirement carrying **all** of its citations.
- Do not pad the count by keeping near-duplicates separate.

**Consolidate descriptions, not actions.** The target is one FR per *piece of work*, not one FR
per source item and not one FR per project. Two sources describing the same deliverable merge;
two distinct actions stay separate FRs even when they arrive in the same sentence, share a
citation, or share a carry marker. A requirement covering five different PRs is not a testable
statement — it is a list wearing an FR's clothes, and its acceptance check degenerates into a
compound. Sharing a carry marker is never a reason to bundle: the marker rule above already
handles within-spec bundles.

**Carry markers.** A carried item is a repeat failure — rank it above new items and say so in
the Executive Summary. Take the count from either source:

1. An explicit `*(carried Nx)*` marker in the issues table, or
2. A carry claim in prose anywhere in the item's source text — *"This is the third time this
   exact recommendation appears"* → `Carried 2x`; *"half of last week's next-step #4 still
   open"* → `Carried 1x`.

Source 2 is required, not optional: the issues table is scoped to one repo, so items belonging
to other projects can only ever get a count from prose. Omit the marker entirely when the item
is new this week.

When a split (step 3) divides a carried item, **only the slice that actually recurred inherits
the count.** If the wrapup's carry claim covers the whole item, put the marker on the slice the
claim describes and leave the other slice unmarked — two `Carried 2x` markers for one
recurrence overstates the evidence. Slices that stay within one spec are one bundle for this
purpose: they share a single marker, they do not each get one.

**When prose and the table disagree, prose wins** — but say so. The table's silence is weak
evidence even for an item in its own scope: a row can be new while the friction it addresses
is old. If prose claims a recurrence the table does not mark, apply the prose count and note
the disagreement in Open Questions rather than dropping the marker.

**Done when:** each project's list has no two requirements describing the same work, and every
carry marker traces to an explicit marker or a prose carry claim.

### 5. Write one spec per project

For every project with **≥1** requirement, write `<folder>/<Project>-spec.md` following
`references/improvement-spec-template.md` (read it — it defines the 7 sections, the H1, and
the FR citation format).

- **A project with zero items gets no file.** Do not emit an empty or placeholder spec, and
  do not invent items to justify one.
- **Specs may reference each other by filename**, and should whenever step 3 split an item:
  name the sibling slice in the Non-goals (*"not the plugin half — see `Z0rd0nZords-spec.md`"*).
  This is what stops split work being done twice by two agents that each see only one spec.
- Re-running overwrites an existing spec for that week. Specs are derived artifacts; the
  wrapup is the source of truth.
- Never write a spec outside the target folder.

**Done when:** every project with items has a spec on disk, and no project without items does.

### 6. Report

State the spec paths written, and **explicitly name the projects skipped for having no
items** — a silent skip is indistinguishable from a bug. If step 1 stopped early, say that
instead.

**Done when:** the user can see which specs exist and which projects were deliberately
skipped.
