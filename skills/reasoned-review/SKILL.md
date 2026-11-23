---
name: reasoned-review
description: Review a spec, PRD, or design doc through reasoning models rather than code-quality lenses. Selects an applicable lens set from what the document touches, then runs multi-agent-review with those lenses. Use when reviewing a written spec before implementing it.
---

# Reasoned review

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Reviews a spec, PRD, or design doc through reasoning models rather than
code-quality lenses. Picks the lens set from what the document touches —
`pre-mortem` and `inversion` always, `red-team` for money/auth/state-machine
content, a tool-permission grant, or caller text fanned into subagent briefs,
`first-principles` where the document asserts hard constraints,
`jobs-to-be-done` where it is user-facing — then runs `multi-agent-review` with
those lenses attached and relays the report.

```
reasoned-review <path-to-spec> [--lenses csv]
```

Pass `--lenses` to override the automatic selection. Lenses are document-shaped,
so on a `pr` target `multi-agent-review` requires `--no-loop`.

Runs `multi-agent-review` over a document with reasoning-model reviewer slots attached, choosing
the lens set automatically. The routing decision is the skill's whole job — the review itself is
`multi-agent-review`'s.

## Why this exists

The expensive defects in a spec are what it does not say, and a code-quality roster never asks
whether the reasoning holds. Running thinking models by hand *before* a fan-out review is
redundant with it and pays twice for the same conclusions — the models belong in the brief, not
a prior pass.

## Selection table

Read the target, then select:

| Condition | Lenses |
|---|---|
| Always, any non-trivial spec | `pre-mortem`, `inversion` |
| Touches money, auth, keys, or a state machine | `+ red-team` |
| Declares an `allowed-tools` grant, or any other tool/permission pre-approval | `+ red-team` |
| Interpolates caller-supplied text into subagent briefs | `+ red-team` |
| Asserts hard constraints ("must", "cannot exceed", "always") | `+ first-principles` |
| Product- or user-facing | `+ jobs-to-be-done` |

`pre-mortem` and `inversion` are unconditional because they are the omission-catchers, and
omissions are the defect class a line-by-line read cannot surface. A permission grant and an
untrusted-text fan-out are attack surface on their own, whatever the subject matter, so either
one selects `red-team`. Cap at 5.

## Steps

1. **Resolve the target set yourself.** A path to a spec/PRD/design doc, or any target
   `multi-agent-review` accepts. Unless `args` already names exact targets, enumerate the
   candidates before asking anything: `gh pr list --state open --json number,title,headRefName`
   and `git worktree list`. Ask only to disambiguate what is still ambiguous after that. If the
   target is a document, prefer `file <path>` over `spec <path>` unless the user named several
   documents that must be reviewed as one set.
2. **Read enough of the target to apply the table.** Scan for money/auth/state-machine subject
   matter, permission grants, caller text interpolated into briefs, constraint language, and
   user-facing framing. Do not review it yourself — you are choosing lenses, not finding defects.
3. **Announce the selection in one line**, naming the trigger:
   `lenses: pre-mortem, inversion, red-team — spec touches the signing path`
   The user may override; otherwise proceed without waiting.
4. **Resolve the originating spec, if any.** When the target is an implementation being reviewed
   against a spec, pass that spec via `--prompt-prelude <path>` per
   `refs/multi-agent/spec-injection.md`. When the target *is* the spec, omit the flag — do not
   pass the target to itself.
5. **Invoke:** `multi-agent-review <target> --lenses <set> [--prompt-prelude <path>]`
6. **Relay what the review returned** without re-summarising it. Report any lens named as failed
   to spawn — a missing lens is a silently weaker review.
7. **Hand off the unapplied findings.** A reasoned review is always read-only (`--lenses` forces
   `--no-loop` on a `pr` target; every other target is one-shot), so nothing it found has been
   applied. Say so in one line, name the merge risk for every CRITICAL and HIGH
   (`1 CRITICAL, 2 HIGH unapplied — merging now ships them`), and end on the handoff to
   `finding-fixer` as the next action, never on the report.

## Do not

- Run the thinking models yourself before invoking — that is the redundancy this skill exists to
  remove.
- Select all five lenses by default. Cost scales with the roster, and an unfocused lens returns
  generic findings.
- Add lenses for a target that is code rather than a document; the lens directives are written for
  documents.
