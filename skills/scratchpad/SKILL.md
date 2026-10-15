---
name: scratchpad
description: User-invoked only; never auto-trigger. Adds/ticks-off items on a configured GitHub checkbox issue (the "scratchpad" backlog). Invoke ONLY when the user explicitly runs /scratchpad or says "scratchpad".
argument-hint: "[item text]  |  done: <item text>  |  uncheck: <item text>"
---

# Scratchpad

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Writes to GitHub** — every add or check-off rewrites the target issue's
> entire body via `gh issue edit`.

Adds or checks off items on a configured GitHub checkbox issue — a living
experiment-and-research backlog. Default action is adding a new item; text like
"done: ..." or "uncheck ..." instead checks or unchecks an existing one.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<item text>` | free text | — | Adds a new item as `- [ ] **<Title>**` under the best-matching section |
| `done: <item>` / "check off/mark \<item\>" | free text | — | Checks off the matching `- [ ]` item |
| `uncheck: <item>` / "reopen/undo \<item\>" | free text | — | Unchecks a matching `- [x]` item |
| `$SCRATCHPAD_TARGET` (env var) | `owner/repo#N` | unset | Highest-precedence target issue override |
| `.scratchpad.json` `{"target": "..."}` | `owner/repo#N` | — | Per-project target config |
| `~/.config/scratchpad/config.json` | `owner/repo#N` | — | User-scope target config (lowest precedence) |

> [!IMPORTANT]
> **User-invoked only.** Run this skill ONLY when the user explicitly types `/scratchpad`
> or says "scratchpad". Never trigger it autonomously or by inferring it from general talk
> about ideas/things to try — if you got here by inference, stop and don't edit the issue.

Quick capture for an **experiment & research backlog** — a living checkbox issue.
Default action is **add a new item**; also supports **checking items off**.

## Quick start

- `/scratchpad obsidian dual-mind plugin`
  → append `- [ ] **Obsidian dual-mind plugin**` to the configured issue under the best-fitting section.
- `/scratchpad done: figure out how npx works`
  → flip that item's box from `- [ ]` to `- [x]`.

## Target resolution (do this FIRST, every invocation)

The scratchpad target is a GitHub issue in `OWNER/REPO#NUMBER` form. Resolve it in
this precedence order — stop at the first hit:

1. **Env var:** `$SCRATCHPAD_TARGET` (e.g. `z0rd0n88/ClaudeConfig#19`).
2. **Per-project config:** if `./.scratchpad.json` exists in the current repo,
   read `{"target": "owner/repo#N"}` from it.
3. **User-scope config:** if `~/.config/scratchpad/config.json` exists, read
   `{"target": "owner/repo#N"}` from it.

If none of those resolve, **stop and tell the user how to configure**:

```
No scratchpad target configured. Pick one:

  # one-shot (this shell only):
  export SCRATCHPAD_TARGET=owner/repo#N

  # per-project (committed):
  echo '{"target": "owner/repo#N"}' > .scratchpad.json

  # user-scope (all projects, default):
  mkdir -p ~/.config/scratchpad
  echo '{"target": "owner/repo#N"}' > ~/.config/scratchpad/config.json

Then re-run /scratchpad.
```

Parse the resolved `OWNER/REPO#N` into `$repo` (`owner/repo`) and `$issue` (`N`)
for the commands below. Do not hardcode any value.

## Workflow

1. **Verify auth:** `gh auth status` (expect "Logged in"). If not, tell the user to run `gh auth login` and stop.
2. **Fetch the live body** — never reconstruct from memory:
   ```bash
   gh issue view "$issue" --repo "$repo" --json body --jq '.body'
   ```
3. **Decide intent** from the user's text:
   - "done / finished / check off / mark <X>" → **check off** (4b)
   - "uncheck / reopen / undo <X>" → **uncheck** (4b)
   - otherwise → **add** (4a)
4. **Edit the body** (see below), then write the whole thing back:
   ```bash
   gh issue edit "$issue" --repo "$repo" --body "$(cat <<'EOF'
   <full edited body>
   EOF
   )"
   ```
5. **Report:** `Added: <item>` / `Checked off: <item>` plus the issue URL.

### 4a. Add an item (smart placement by content)
- Format: `- [ ] **<Title>** — <short note if it adds clarity>`. Keep the title close to
  the user's wording; don't over-expand or guess at ambiguous shorthand.
- Read the existing `##` section headers and place the item under the section whose theme
  best matches it.
- No clear fit → put it under `## New ideas (append below)`. If that section doesn't
  exist yet, create it at the bottom of the body.
- A clear new theme covering 2+ items → add a new `## <Theme>` section.
- Skip items already present (case-insensitive match) — tell the user it's a dup.
- Multiple items in one call → add them all in a single edit.

### 4b. Check off / uncheck an item
- Find the `- [ ]` (or `- [x]`) line whose text best matches the user's phrase.
- Check off: `- [ ]` → `- [x]`. Uncheck: `- [x]` → `- [ ]`.
- Ambiguous match (2+ candidates) → ask which one; do not guess.

## Rules
- **Preserve the entire body.** Fetch it, change only the relevant line(s)/section, write it
  back whole. Never drop any header or existing items.
- Use the single-quoted heredoc (`<<'EOF'`) so backticks and `$` inside the body aren't expanded.
- This issue stays **open** — never close it.

## One-time setup (for new users)

1. Create the target issue in any GitHub repo you have write access to. A good
   starting body:
   ```markdown
   > [!NOTE]
   > Living backlog of experiments / ideas. Add via `/scratchpad <item>`, check off via `/scratchpad done: <item>`.

   ## New ideas (append below)
   ```
2. Note its `owner/repo#N` (e.g. `you/notes#42`).
3. Save it (one of the three options in **Target resolution** above).
4. Run `/scratchpad test item` to verify.
