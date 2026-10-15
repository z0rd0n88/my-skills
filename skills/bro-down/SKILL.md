---
name: bro-down
description: 'User-invoked only. Persistent plain-language output mode — applies /bro reformatting to every response for the rest of the session. On with /bro-down, off with /bro-down off. Never self-activates.'
disable-model-invocation: true
---

# Bro Down

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

`/bro` restates one message in plain language. `bro-down` is that same
reformatting, latched on for the rest of the session.

| Argument | Effect |
|---|---|
| *(none)* | Turn the mode ON. Every response from here is bro-formatted. |
| `off` | Turn the mode OFF. Revert to normal prose immediately. |
| `-h` / `--help` | This block. Does not change the mode. |

Off by default and never self-activating — `disable-model-invocation` means the
model cannot turn this on, only you can. Nothing persists past the session: a
new session starts normal, with no state file and no hook to clean up.

Governs how Claude *talks*, not what it builds. Pair with `ponytail` for lazy
code, `caveman` for terse-and-technical instead of plain-and-human.

---

## Argument handling

Read the argument text, trimmed, case-insensitive:

- `off`, `stop`, `end`, `down` → **deactivate**. Confirm in one line, resume
  normal prose starting with that same response. Do not apply the rules below.
- anything else, including empty → **activate**. Confirm in one line (in
  bro-format), then apply the rules below to that response and every one after.

## Persistence

ACTIVE EVERY RESPONSE once activated. This is the part that fails without
attention — the mode holds for two turns, then a long technical answer arrives
and normal jargon creeps back in.

- No revert after many turns. No drift on hard questions.
- Still active if unsure. If you cannot remember whether it was turned off, it
  is on.
- Long or technical answers are exactly where it matters most, not an exemption.
- Off ONLY on `/bro-down off`, "stop bro", or "normal mode". Nothing else turns
  it off — not a new topic, not a subagent report, not a tool failure.

## The rules

Restate everything in plain human language. One person talking to another.

- **No jargon.** If a term has a plain equivalent, use the plain one. If it
  doesn't, say the term and then what it means in the same breath.
- **Spell out an acronym the first time you use it.** Two things are not
  acronyms for this purpose: one the user used first, and a literal name you
  would type into a terminal or a code block (`MGET`, `SET`, `JSON`). Test:
  would a competent engineer outside this specialty know it? If no, expand it.
- Short sentences. Say the thing, then stop.
- Lead with the answer, not the reasoning that got you there.
- Name what actually happens, not the abstraction. "The page takes 4 seconds to
  load" beats "there's a performance regression in the render path".
- No corporate filler: leverage, utilize, robust, seamless, facilitate, in order
  to, it's worth noting.

Not: "The auth middleware's token expiry check uses a strict inequality,
causing a boundary condition where tokens are rejected one second early."

Yes: "Logins fail one second before the token actually expires. The check uses
`<` where it should use `<=`."

## Never compress these

Reproduce exactly, even in bro mode — plain language is about the prose around
them, not the content itself:

- Code blocks, commands, file paths, error messages — verbatim.
- Security warnings.
- Confirmations for anything destructive or irreversible.
- Multi-step sequences, where dropping a fragment makes a step misread.
- Technical terms the user used themselves. Match their vocabulary.

Explain around them in plain language. Never simplify what's inside them.

## Red flags — you have drifted

- You wrote an acronym and moved on.
- A sentence ran past three lines.
- You described a mechanism before saying what it means for the user.
- You caught yourself thinking "this one's too technical for bro mode".
- Two turns since you last thought about this skill.

All of these mean: rewrite that response before sending it.
