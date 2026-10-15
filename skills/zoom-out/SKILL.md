---
name: zoom-out
description: Ask the agent to zoom out a level and map the relevant modules and callers using the project's domain language.
disable-model-invocation: true
---

# Zoom Out

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Read-only orientation prompt for unfamiliar code. Asks for a map of the
relevant modules and their callers one level up, phrased in the project's own
domain vocabulary rather than file paths.

| Option | Values | Default | Effect |
|---|---|---|---|
| — | takes no arguments | — | Run `/zoom-out` in the area of code you're lost in |

User-invocable only (`disable-model-invocation`), so it never fires on its own —
you ask for it when *you* are the one who's lost.

---

I don't know this area of code well. Go up a layer of abstraction. Give me a map of all the relevant modules and callers, using the project's domain glossary vocabulary.

## Provenance

Originally authored by Matt Pocock in
[mattpocock/skills](https://github.com/mattpocock/skills). Removed upstream;
preserved here with the instruction unchanged — only this section and the help
block above were added.
