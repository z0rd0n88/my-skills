# Baton

Drives long-running, multi-phase code work — the "I have 5 specs to build sequentially, the context budget per session can't hold all of them, and I want disk-resumable state between phases" toolkit.

```
queue of specs
  → unit 1 (implement → review → fix)  → baton-pass note
  → unit 2 (implement → review → fix)  → baton-pass note
  → unit 3 ...
```

The orchestrator stays **out of per-unit context** — each implement / review / fix step runs in a fresh subagent. The manager only sees unit boundaries, gate checks, and the queue cursor. Disk artifacts (worktree state + baton-pass notes) let the next session pick up cold.

## The skill

| Skill | What it does | Command |
|---|---|---|
| [`zord-baton-runner`](./skills/zord-baton-runner/SKILL.md) | Drives an ordered queue of specs as sequential implement→review→fix work units in a single worktree. Each unit is a clean subagent dispatch. Per-unit gates (compile + test + lint) before advancing. | `/zord-baton-runner` |

## What makes baton-pass different

The note format is opinionated and small. Three hard rules:

1. **Append-only.** Never edit prior notes. The history is the audit trail.
2. **Timestamp-ordered filenames.** `YYYY-MM-DDTHHMMSS-<slug>.md`, monotonic per feature by wall-clock time — no shared counter for concurrent writers to race on. Legacy `NNN-YYYY-MM-DD-<slug>.md` entries from before this format stay valid and untouched.
3. **Feature/epic subdirectories.** `baton-pass/<feature>/YYYY-MM-DDTHHMMSS-…md`, not a flat directory. Browsing the directory should tell you the structure of the work.

Every entry also carries a `source`/`scope`/`parent_session` YAML frontmatter block, and `baton-pass/INDEX.md` is rebuilt by a packaged script (`scripts/regen-index.sh`) rather than hand-derived on every invocation — see the skill's own [Gotchas](./skills/baton-pass/SKILL.md#gotchas) for why.

The note body captures: what was decided this session, what's still open, where to look in the code, and the **explicit next step**. The format is optimized for an LLM-orchestrator to pick up cold — no implicit context.

## Composition

| Pattern | Skill | Plugin |
|---|---|---|
| Single spec → APPROVE | `zord-baton-runner` with a single spec | this plugin |
| Queue of specs, single-agent units | `zord-baton-runner` | this plugin |
| Session baton-pass notes (standalone) | `baton-pass` | this plugin |

## Install

```bash
claude plugin marketplace add z0rd0n88/z0rd0nlander
claude plugin install my-skills@z0rd0nlander
```

`/zord-baton-runner` and `/baton-pass` work standalone with no other plugins.

## Use

```bash
# Plain runner over a queue file:
/zord-baton-runner queue.md

# Write a standalone baton-pass note:
/baton-pass payment-replay
```

## Layout

```
zord-baton/
├── .claude-plugin/plugin.json
├── README.md
├── commands/
│   ├── zord-baton-runner.md
│   └── baton-pass.md
└── skills/
    ├── zord-baton-runner/
    │   ├── SKILL.md
    │   ├── REFERENCE.md
    │   └── scripts/
    │       └── gate.sh                 # compile + test + lint per-unit gate
    └── baton-pass/
        ├── SKILL.md
        └── scripts/
            └── regen-index.sh           # rebuilds baton-pass/INDEX.md from disk
```

## License

[MIT](../../LICENSE).
