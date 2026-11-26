---
name: weekly-wrapup
description: Builds the weekly wrapup from the persisted /insights report plus a cross-project standup, compares to last week, and files new proposal rows as ClaudeConfig issues. User-invoked ONLY via /weekly-wrapup or the weekly schedule.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash
  - Agent
  - Skill
---

# Weekly Wrapup

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Writes files, files GitHub issues, and can spawn a `wrapup-specs` run** — every
> invocation writes `/home/alex/Projects/WeeklyWrapup/<isodate>/wrapup.md`, files each new
> proposal-table row as a `z0rd0n88/ClaudeConfig` issue (label `from-wrapup`, deduped
> against open ones), runs the `improve-me` harness audit (which writes
> `~/Projects/Improvements/<isodate>/report.md`), and, via the `wrapup-specs` skill, writes one
> improvement-spec file per flagship project with improvement items — no confirmation prompt,
> no dry-run.

Generates a weekly wrapup from the persisted `/insights` report plus a
cross-project `/standup`, compares it against last week, and appends a
critical GitHub-issues table and next-steps section. It only runs when the
user invokes `/weekly-wrapup` directly or a scheduled weekly routine triggers
it — never from general talk about progress or retros.

| Option | Values | Default | Effect |
|---|---|---|---|
| (none — takes no arguments) | — | reads `/home/alex/.claude/usage-data/report.html` plus the repos listed in `projects.json` | Runs the full wrapup: insights + standup → `wrapup.md` → week-over-week comparison → harness audit → issues table → next steps → per-project specs |

> [!IMPORTANT]
> **User-invoked only.** Run this skill ONLY when the user runs `/weekly-wrapup` or a
> scheduled routine invokes it. Never auto-trigger from general talk about progress or retros.

## How insights data reaches this skill

`/insights` is a native CLI command — it cannot be called from inside a skill. It does not
need to be: every run persists a self-contained report to
`/home/alex/.claude/usage-data/report.html` (an always-latest copy). **This skill reads
that file** — it does not depend on `/insights` output being injected into context.

The weekly routine refreshes the file by running `/insights` in a separate headless call
*before* this one (see the plugin README's cron recipe). If the file is stale or absent,
this skill still runs — it just notes the report's age and proceeds with what it has.

## Steps

### 1. Load this week's insights
- Read `/home/alex/.claude/usage-data/report.html`. Extract the rendered narrative — the
  "At a Glance" summary (what's working / what's hindering / quick wins), the "What You
  Work On" project areas, "Where Things Go Wrong", tool/language/session stats, and any
  suggestions. Strip HTML; keep the substance.
- Record the report's date (from its filename/header) and message/session counts.
- File missing → note "no insights report found" and continue to step 2; do not fabricate.

**Done when:** the insights narrative and its date are captured, or its absence is recorded.

### 2. Gather cross-project standup

#### 2.1 The project list — never hardcode it
Read `$WEEKLY_WRAPUP_PROJECTS`, defaulting to `/home/alex/Projects/WeeklyWrapup/projects.json`. Every
project's canonical `name`, local `path`, and `aliases` come from that file and nowhere else.
`wrapup-specs` reads the same file for spec filenames, so the two can never disagree.

File missing or unparseable → say so in the wrapup, scan nothing, and continue to step 3. A
wrapup that silently scanned four repos because a config failed to load is worse than one that
reports the failure.

#### 2.2 Git activity
Invoke the `standup` skill (`engineering:standup`) over every project in that list, pulling the
last 7 days of git activity (commits, PRs opened/reviewed/merged) from each `path`. Read the
full standup output. If the Skill tool cannot resolve `engineering:standup`, gather the same
`git`/`gh` data directly and record the substitution as a finding.

#### 2.3 Cross-tool activity
The insights report in step 1 covers Claude Code sessions only. Work done in other agentic
tools is invisible to it, so collect that here — otherwise a week's effort shows up as commits
with no account of what produced them.

```bash
python3 - <<'PY'
import sqlite3, os, json, glob, collections, datetime
cfg = os.environ.get("WEEKLY_WRAPUP_PROJECTS", "/home/alex/Projects/WeeklyWrapup/projects.json")
projects = json.load(open(cfg))["projects"]
alias = {a.lower(): p["name"] for p in projects
         for a in [p["name"], os.path.basename(p["path"]), *p["aliases"]]}
cut = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

# Antigravity: one row per conversation, already summarized.
db = os.path.expanduser("~/.gemini/antigravity-cli/conversation_summaries.db")
if os.path.exists(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    agg = collections.defaultdict(lambda: [0, 0, []])
    q = "select workspace_uris, step_count, last_modified_time, title from conversation_summaries"
    for ws, steps, ts, title in con.execute(q):
        if not ts or ts[:10] < cut:
            continue
        try:
            dirs = [os.path.basename(u.rstrip("/")) for u in json.loads(ws or "[]")]
        except ValueError:
            dirs = []
        name = next((alias[d.lower()] for d in dirs if d.lower() in alias), "(unlisted)")
        a = agg[name]
        a[0] += 1
        a[1] += steps or 0
        if title:
            a[2].append(title)
    for name, (n, steps, titles) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        print(f"antigravity\t{name}\t{n} convs\t{steps} steps\t{'; '.join(titles[:8])}")
else:
    print("antigravity\tno data")

# Codex: sessions are filed under sessions/YYYY/MM/DD/.
days = [(datetime.date.today() - datetime.timedelta(days=d)).strftime("%Y/%m/%d")
        for d in range(8)]
n = sum(len(glob.glob(os.path.expanduser(f"~/.codex/sessions/{d}/*.jsonl"))) for d in days)
print(f"codex\t{n} sessions in the last 7 days")
PY
```

Report per project: conversation count, step count, and conversation titles. A project with
cross-tool activity but no git activity is itself a finding — effort that produced no commits.
Rows landing in `(unlisted)` name a workspace absent from `projects.json`; surface them so the
list can be corrected, and never invent a canonical name for one.

**Done when:** a per-project activity summary exists for every project in the list, or an
explicit "no activity this week" note for the quiet ones, and cross-tool counts are captured
for each tool or its absence recorded.

### 3. Write the base wrapup file
- Get today's ISO date (`date +%F`); `mkdir -p /home/alex/Projects/WeeklyWrapup/<isodate>`.
- Write `/home/alex/Projects/WeeklyWrapup/<isodate>/wrapup.md` with `## Insights` (full extracted
  narrative + report date) and `## Standup` (full cross-project summary). Under `## Standup`,
  the git activity comes first and `### Cross-Tool Activity` closes the section.

**Done when:** both sections exist in the new file, in full, and `### Cross-Tool Activity` is
present with either per-project numbers or a recorded reason there are none.

### 4. Load last week's wrapup
- List `/home/alex/Projects/WeeklyWrapup/*/wrapup.md`, excluding the file just created; take the
  most recent by the date in its parent directory's name.
- Found → read it completely.
- Not found → skip step 5; go to step 6.

**Done when:** the prior wrapup is fully loaded, or its absence is confirmed.

### 5. Compare weeks (skip if step 4 found nothing)
Critical, professional, unsparing — do not soften findings. For each axis (velocity,
code-quality signals, friction points, tool/skill usage):

- **Positives** — what genuinely improved, cited to this week's data.
- **Negatives** — what regressed or stayed stuck, cited to this week's data.

Cross-tool activity is evidence like any other: cite it in every axis it bears on. Effort that
produced no commits belongs under Negatives, and a project whose work moved to another tool
explains a velocity drop that git alone reads as idleness.
- **Recommendations** — each names a specific tool, skill, plugin, or article that closes
  the gap. A recommendation naming nothing is a no-op; cut it.

Append as `## Week-over-Week Comparison`.

**Done when:** every axis has an entry in each subsection, or an explicit "no signal" note.

### 6. Harness audit (`improve-me`)
Insights and the standup measure *activity*. This step measures *conformance and friction* —
where your own rules, hooks and permissions fought you this week — so the issues table below
has evidence about the harness, not only about the work.

Invoke the `ThinkTime:improve-me` skill via the `Skill` tool with `--days 7`: the wrapup's window, not
the skill's monthly default. **Block until it returns.** It runs its signal collector over the
week's session transcripts and writes `~/Projects/Improvements/<isodate>/report.md`.

**If the `Skill` tool cannot resolve `ThinkTime:improve-me`** — a paste-invoked headless run resolves no
skills — read its SKILL.md from disk and follow it directly. It lives in the ThinkTime plugin
(ClaudeConfig#240), so try, in order: the source checkout
`/home/alex/Projects/ThinkTime/ThinkTime/improve-me/skills/improve-me/SKILL.md`, then the
newest installed copy, `ls ~/.claude/plugins/cache/*/ThinkTime/*/improve-me/skills/improve-me/SKILL.md | sort -t/ -k9,9V | tail -1`.

Append `## Harness Audit` holding the report's path, its executive summary, and each ranked
finding condensed to one line (evidence → harm → change). Do not restate the full report — the
file has it.

`improve-me` is diagnostic only: it proposes harness changes and never edits config, rules or
hooks. That boundary holds here too — its proposals become rows in step 7, not edits.

The audit is downstream of the wrapup and must not invalidate it. Collector failure, unresolved
skill, or no report → write `harness audit unavailable: <reason>` under the heading and continue
to step 7. Never let it break the run.

**Done when:** `## Harness Audit` holds the report path and its ranked findings, or a recorded
reason it is unavailable.

### 7. Potential GitHub issues (always runs)
Append `## Potential GitHub Issues (ClaudeConfig)` with a table:

| Title | Body | Labels | Evidence | Issue |
|---|---|---|---|---|

Every row cites the specific insights, standup, or harness-audit finding it's drawn from —
including cross-tool rows — no speculative issues. Stay critical: surface what needs to change, do not flatter the user.

Then **file each row as a real issue** — six weeks of proposals-only tables produced zero
filed issues, so the table alone is a proven no-op:

1. Ensure the label exists (idempotent):
   `gh label create from-wrapup --repo z0rd0n88/ClaudeConfig --description "Filed by weekly-wrapup" --color BFD4F2 2>/dev/null; true`
2. Dedupe against what is already open:
   `gh issue list --repo z0rd0n88/ClaudeConfig --state open --label from-wrapup --json number,title`.
   A row whose title matches an open issue (same work, wording may drift) is **not refiled** —
   put `#N (existing)` in its Issue column. This is what keeps carried items from
   accumulating duplicates week after week.
3. File every remaining row:
   `gh issue create --repo z0rd0n88/ClaudeConfig --title <Title> --label from-wrapup --body <Body + Evidence + path to this wrapup.md>`
   (plus the row's other labels only if they already exist in the repo). Record the created
   number in the Issue column.
4. `gh` failure (auth, network, unknown label) → keep the table, write `filing failed:
   <reason>` in the Issue column, and continue — the wrapup itself still stands. Never let
   filing break the run, and never file the same row twice in one run.

**Done when:** every recurring friction point or regression in the week's data has a row
(or an explicit note that none warranted one), and every row's Issue column holds a new
issue number, an `#N (existing)` reference, or a recorded filing failure.

### 8. Next steps
Append `## Next Steps` — a prioritized list for the coming week, each item traceable to a
finding in steps 5–7, not generic advice.

**Done when:** every item traces back to a specific finding above it.

### 9. Save the wrapup
Ensure the file holds every section in order: Insights, Standup, [Week-over-Week
Comparison], Harness Audit, Potential GitHub Issues, Next Steps.

**Done when:** the on-disk file contains every section produced above, in that order.

### 10. Generate per-project improvement specs
Invoke the `wrapup-specs` skill via the `Skill` tool, passing this week's folder
(`/home/alex/Projects/WeeklyWrapup/<isodate>`). **Block until it returns.** It reads the wrapup just
written and emits one `<Project>-spec.md` per project that has improvement items, into the
same folder.

**If the `Skill` tool cannot resolve `wrapup-specs`** — this skill's body may have been pasted
into a headless run where the plugin is on disk but not installed — fall back to reading
`<plugin-root>/weekly-wrapup/skills/wrapup-specs/SKILL.md` plus its
`references/improvement-spec-template.md` and following them directly. Instructions are
instructions whether loaded by the Skill tool or read from disk.

Spec generation is downstream of the wrapup and must not invalidate it: if both routes fail,
note it and continue to step 11 — the wrapup itself still stands.

**Done when:** `wrapup-specs` has returned and its spec paths are captured, or its failure is
recorded.

### 11. Report
Report the wrapup's file path, the harness-audit report path, the spec files written
alongside the wrapup, and any project skipped for having no improvement items.

**Done when:** the user has the wrapup path and the list of generated specs.
