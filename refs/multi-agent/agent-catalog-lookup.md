# Agent catalog lookup

Shared primitive for any multi-agent skill that picks specialists from the project's active agents plus the user-scoped parked catalog. Cited by `zord-total-review`, `zord-multi-agent-review`.

## The two catalogs

| Location | Scope | Loaded into context? |
|---|---|---|
| `<repo>/.claude/agents/` | project — recursively scanned | yes, every session |
| `~/.claude/agents-parked/` | user-scope library | no — discoverable, not loaded |

The parked tier exists so user-scope `~/.claude/agents/` can stay empty (no global agent prompts in every session). Specific agents are *activated* per-project by `git mv`-ing them from `agents-parked/` into `<repo>/.claude/agents/`.

## Lookup procedure

When a multi-agent skill needs to resolve an agent name (e.g. `python-reviewer`):

**A name may be given in either of two shapes, and both are legitimate:** the
**filename stem** (`security-reviewer`) or the **internal `name:` field**
(`security-reviewer`). They frequently differ — `ecc-`-prefixed files usually carry
an unprefixed `name:`, and `architect-reviewer.md` carries `name: architect-reviewer`.
**Match on either.** Resolving by one shape alone silently fails on names written in
the other, and this skill's own documented default roster mixes them: of
`architect-reviewer`, `critical-thinking`, `silent-failure-hunter`,
`security-reviewer`, `penetration-tester`, three resolve only by filename stem
and two only by internal name.

1. **Try the active project catalog first**, filename stem then internal name.
   ```bash
   # by filename stem
   ls <repo>/.claude/agents/**/<name>.md 2>/dev/null | head -1
   # by internal name
   grep -lE "^name: <name>$" <repo>/.claude/agents/**/*.md 2>/dev/null | head -1
   ```
   If found, use the active agent directly.

2. **Fall back to the parked catalog as a candidate** (not an automatic activation),
   using the same two-shape match.
   ```bash
   ls ~/.claude/agents-parked/<name>.md 2>/dev/null | head -1
   grep -lE "^name: <name>$" ~/.claude/agents-parked/*.md 2>/dev/null | head -1
   ```
   If found here but not in `(1)`, surface it as a parked candidate. **Do not silently copy it into the project** — agent activation is a deliberate user act (it edits the project's tracked `.claude/agents/`). Either ask for activation, or hard-fail with the activation command pasted (`cp ~/.claude/agents-parked/<file>.md <repo>/.claude/agents/`).

3. **If the two shapes resolve to different files, hard-fail** with both paths. A
   repo holding `code-reviewer.md` *and* `ecc-code-reviewer.md` (the latter carrying
   `name: code-reviewer`) makes the bare name genuinely ambiguous; picking either is
   a coin toss the caller cannot see. Make them disambiguate.

4. **If neither catalog has it, hard-fail.** Do not auto-pick a similar name. Reviewer rosters must be explicit; degraded coverage from a missing lens is worse than refusing to start.

**Whichever shape matched, the `subagent_type` you dispatch with is the resolved
file's filename stem** — that is what the Agent tool registers, per
`zord-multi-agent-review` §5A.4 and the user-scope `CLAUDE.md` § Agent Roster. Resolution
accepts two shapes; dispatch emits exactly one.

## Selection heuristics (when the skill picks the roster)

When a skill auto-selects specialists (no explicit roster flag), it runs the
**context-aware selector** in `context-aware-selection.md`, which resolves each
active lane through `lane-agent-table.md`. The legacy hierarchy below is retained
as the selector's semantic-matcher ordering when a lane is unmapped:

1. Generic baseline (`code-reviewer`) — lane `L-BASELINE`
2. Stack overlay (`python-reviewer`, `typescript-reviewer`, …) — lane `L-LANG:*`
3. Domain lenses (`sql-pro`, `security-reviewer`, …) — the signal-activated lanes
4. Roster caps — hard 4 build / soft 6 per slice review (unchanged)

## Failure modes

- **Name collision.** Two `agents/disabled/<name>.md` and `agents/<name>.md` both have the same `name:` field. Harness loads one silently and drops the other. Audit project agents with `grep -rh ^name: <repo>/.claude/agents/ | sort | uniq -d`.
- **Parked agent depended on by a wrapper that doesn't activate it.** A `<slug>-total-review/config.yml` references a lens that's parked but not activated → reviewer fan-out runs with degraded coverage. The orchestrator MUST warn loudly (not silently skip) and ask the user to activate before retrying.
- **Filename ≠ internal name — and resolving by *either* one alone silently fails.** By filename only, `python-reviewer` misses an agent living as `python-reviewer.md` with `name: python-reviewer`. By `^name:` only, `architect-reviewer` and `security-reviewer` — both in this skill's own default roster — match nothing, because their files carry `architect-reviewer` and `security-reviewer`. Match on both shapes (Lookup procedure step 1), and hard-fail when they disagree.
- **A roster name that resolves under no rule.** The symptom is a hard-fail at parse time, which is the good case. The dangerous variant is a lane whose absence is *tolerated* — `penetration-tester` is explicitly allowed to be missing without hard-failing (`zord-multi-agent-review` §4), so a mis-shaped name in that slot degrades the roster silently instead of stopping. Audit a roster by resolving every name before trusting a run that reports fewer lanes than expected.
