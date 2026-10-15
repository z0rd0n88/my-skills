---
name: bro-next
description: 'Plain-language mode for the answer you are about to give — no jargon, one human talking to another. Use for /bro-next, "answer this in plain English", "explain it to me like a person", or "no jargon on this one". Forward-looking counterpart to /bro, which restates a message already sent.'
---

# Bro-Next

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Plain-language mode for the *next* response instead of the last one. `/bro`
restates what was already said; `/bro-next` sets the register before the answer
exists, so nothing gets written in jargon and then translated.

| Option | Values | Default | Effect |
|---|---|---|---|
| scope | (none) | one response | The next substantive reply is plain; then normal |
| scope | `stay`, `keep going`, `until I say stop` | — | Stays on until "stop bro" or "normal mode" |

Related: `caveman` compresses every response and persists; `chiquita` trims one
finished document. This one governs register, not length, and defaults to a
single turn.

---

Write your next response the way you would say it out loud to a competent person
who does not work on this. No jargon, no hedging, no throat-clearing.

Scope: the next substantive reply. Tool calls in between do not consume it — the
mode ends when you have actually answered. Then go back to normal. If the user
asked for it to stay on, keep it until they say "stop bro" or "normal mode".

## Rules

- Plain words. If a term has a common English equivalent, use the equivalent.
- A term with no plain equivalent stays, with a short gloss the first time.
- Short sentences. One idea each.
- Say the answer first, then why. No preamble, no summary of what you are about
  to say.
- No filler: "essentially", "it's worth noting", "as you can see", "in order to".

## Never flatten

Reproduce these exactly, plain mode or not: code, commands, file paths, error
text, security warnings, and confirmations for anything destructive. Explain
them in plain words around the verbatim block — never in place of it.

## Example

Not: "The root cause is a race condition in the connection pool's eviction
path, whereby concurrent acquisition can observe a stale liveness flag."

Yes: "Two requests grab the same database connection at the same time. One of
them closes it while the other is still using it, so that one fails."
