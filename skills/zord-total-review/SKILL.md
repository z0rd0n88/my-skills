---
name: zord-total-review
description: Shared multi-agent codebase review workflow library. Project wrappers at .claude/skills/<slug>-total-review/ delegate to this skill's REFERENCE.md with a sibling config.yml declaring layer slices, agent picks, and tracker commands.
---

# zord-total-review

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Writes reports, files tracker issues, and posts PR comments by default**
> — every mode writes a Markdown report to `report_dir` (usually a committed
> path) and most modes also file a tracker issue and comment on an open PR;
> opt out per-run with `--no-write` / `--no-comment`.

Shared multi-agent codebase review library invoked through a per-repo
`<slug>-total-review` wrapper skill, which supplies a `config.yml` of layer
slices, agent picks, and tracker commands. It runs one of eight canonical
review modes (`code`, `cleanup`, `security`, `architecture`, `test`, `perf`,
`docs`, `pre-pr`, plus `all`) as parallel specialised-agent fan-out along a
repo's own layer boundaries.

| Option | Values | Default | Effect |
|---|---|---|---|
| `mode` (positional) | `code`, `cleanup`, `security`, `architecture`, `test`, `perf`, `docs`, `pre-pr`, `all` | required | Selects which review lens(es) run |
| `--against <base-ref>` | a git ref, e.g. `origin/main` | unset (full sweep) | Scopes review to slices touched in the diff against that ref |
| `--all-slices` | flag | off | Forces a full sweep even when `--against` is set |
| `--spec <path>` | file path | none | `pre-pr` mode only — injects the originating spec/issue for intent-conformance checks |
| `--no-write` | flag | off | Skips writing the Markdown report |
| `--no-comment` | flag | off | Skips posting the report as a PR comment |

Library skill, not invoked directly. Each owned repo gets its own thin wrapper at `<repo>/.claude/skills/<slug>-total-review/` that delegates to this skill's [`REFERENCE.md`](REFERENCE.md) using a sibling `config.yml`.

## The pattern

Parallel multi-agent code review tailored to a repo's specific layer layout. Each mode fans out specialised agents along clean layer seams so reviewer outputs are complementary, not duplicated.

The design insight: **clean `domain → application → adapters`-style layer boundaries let reviewers divide work along those seams with minimal overlap, and pairing a *correctness* lens (e.g. `code-reviewer`) with an *idiom* lens (e.g. `python-reviewer` / `kotlin-reviewer`) surfaces complementary findings on the same file without duplication.**

The #1 lever against duplicate work is the **exclusion list**: before fan-out, fetch open-issue findings from the tracker and inject them verbatim into every reviewer prompt under a "DO NOT report" heading. Validated against a real multi-pass review where consecutive passes were re-reporting the same 3–4 findings; injecting prior-pass issues as exclusions eliminated the duplicates without losing genuinely new findings.

## Modes (canonical eight)

| Mode | Purpose | Files issue? |
|---|---|---|
| `code` | Correctness + atomicity + idiom + typing | yes |
| `cleanup` | Dead code + duplication + unused helpers | yes |
| `security` | Input/output + money flow + OWASP framing | yes |
| `architecture` | Hexagonal boundaries + deepening + silent-failure ladder | yes |
| `test` | Coverage + fake parity + mock-spec adequacy | yes |
| `perf` | N+1 + DB contention + hot-path numerics | yes |
| `docs` | ARCH.md / ADR / baton-pass drift | no (report file, plus a minimal patch when drift is small) |
| `pre-pr` | Diff-only sanity check before opening a PR | no (report file only) |

`all` runs every mode except `pre-pr` and files one tracker issue per mode.

**Every mode writes a report** to `config.output.report_dir` (default `docs/reviews/<YYYY-MM-DD>-<slug>.md`), and a PR target additionally gets one comment — both by default, `--no-write` / `--no-comment` to opt out. "Files issue? no" means no *tracker* issue; it never means no artifact.

## How wrappers consume this

A project's wrapper looks like:

```
<repo>/.claude/skills/<slug>-total-review/
  SKILL.md     # short trigger; description names the project; body says
               # "follow ~/.claude/skills/zord-total-review/REFERENCE.md using ./config.yml"
  config.yml   # slices, modes overrides, tracker commands, invariants
```

A project's config.yml declares:
- **Slices** — `(slug, path, lenses)` per slice; the layer map of the project.
- **Mode overrides** — per-canonical-mode agent overrides, per-mode disables, and project-specific add-on modes.
- **Tracker** — shell commands for exclusion query and issue filing; title template; cross-ref phrase.
- **Output** — `report_dir` for the Markdown report every mode writes; optional, defaults to `docs/reviews`.
- **Invariants** — project rules every reviewer must respect (e.g. money type, datetime tz, key shape).

See [`REFERENCE.md`](REFERENCE.md) for the workflow steps, default agent matrix per stack, config schema, and issue body template. See the sibling `zord-total-review-scaffold` skill to bootstrap a wrapper in a fresh repo.
