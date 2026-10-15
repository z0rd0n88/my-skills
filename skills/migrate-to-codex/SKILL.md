---
name: migrate-to-codex
description: Migrate Claude Code config (CLAUDE.md, skills, agents, MCP servers) into ~/.codex or .codex/. Use when the user wants to port or migrate their Claude Code setup to Codex.
---

# Migrate to Codex

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Writes into your Codex config** — merges translated content into
> `.codex/config.toml` (or `~/.codex/config.toml`) and copies/overwrites files
> under `.codex/` or `~/.codex/`; the Claude Code source tree is never touched.

Migrates a Claude Code configuration — `CLAUDE.md`, skills, agents, and MCP
server entries — from `.claude/`/`~/.claude/` into the equivalent Codex layout
under `.codex/`/`~/.codex/`, merging into any existing config rather than
overwriting it wholesale. Use it when porting a Claude Code setup to Codex; it
never writes back into the Claude Code source.

| Option | Values | Default | Effect |
|---|---|---|---|
| `scope` (asked, not passed) | project-only, user-only, both | asked interactively in Step 1 when run inside a repo; otherwise whichever tree is present | Selects which config trees (`.claude/` vs `~/.claude/`) get migrated |

Source (`.claude/`, `~/.claude/`, `.mcp.json`, `.claude.json`) is **read-only** for this skill: every write lands under `.codex/` or `~/.codex/`, never back into the source tree. Track progress with the task list tool; skip writing a TODO file.

## Step 1: Fix scope

1. If running inside a project repo, ask the user: *"Also migrate your global user-level Claude configuration and skills from ~/.claude to ~/.codex?"*
2. Set scope from the answer:
   - **Yes** → migrate both `.claude/` → `.codex/` (project) and `~/.claude/` → `~/.codex/` (user).
   - **No**, or not inside a project repo → migrate only the tree actually present (project-only, or user-only when run outside a repo).

Done when scope is fixed to exactly one of: project-only, user-only, or both — no further steps proceed until this is set.

## Step 2: Migrate each artifact type

Existing unrelated entries already in `.codex/config.toml` / `~/.codex/config.toml` survive untouched — merge into them, never overwrite the file wholesale.

| Source | Target | Rule |
|---|---|---|
| `CLAUDE.md` | `AGENTS.md` | Carry over project facts, architecture rules, cross-agent constraints. Drop Claude-only mechanics: hooks, slash commands, UI settings. |
| `.claude/skills/` | `.codex/skills/` | Copy folder as-is — both ecosystems use the open Agent Skills standard. Verify each migrated `SKILL.md` still has valid YAML frontmatter with at least `name` and `description`. |
| `.mcp.json` | `.codex/config.toml` (merged) | Translate each server entry to TOML, carrying env vars and bearer tokens through unchanged. |
| `.claude/agents/*.md` | `.codex/agents/*.toml` | Translate YAML frontmatter to TOML fields. Map model aliases to Codex's naming. Map tool permissions to Codex equivalents (`sandbox_mode`, `web_search`, `prefix_rule`). |

Done when every file found in the source scope from Step 1 has a corresponding entry above either migrated or explicitly logged as skipped (with a reason) for the final report.

## Step 3: Report

Output a markdown report: scope used, what moved (per artifact type), what was skipped and why, and any manual step the user still owes (e.g. a secret that needs re-entry, a permission with no Codex equivalent).

Done when the report accounts for every file touched or skipped in Step 2 — nothing migrated silently.
