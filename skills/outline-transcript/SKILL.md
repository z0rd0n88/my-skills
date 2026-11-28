---
name: outline-transcript
description: Summarizes the session transcript in a strict one-sentence back-and-forth format.
---

# outline-transcript

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Replays the current session as a strict alternating User/Agent outline, one
sentence per turn, in chronological order. Takes no options.

| Option | Values | Default | Effect |
|---|---|---|---|
| trigger | `/outline-transcript` | — | Outlines the session so far |

Related: `baton-pass` writes a handoff note for the *next* session; this one
just summarizes what already happened in this one.

---

When the user invokes this skill, read the conversation transcript and output a concise back-and-forth summary of the session.

## Rules
1. Alternate between the User's request and the Agent's response.
2. Each outline item (both User and Agent) must be exactly **one sentence** long.
3. Include specific actions taken by the Agent (e.g., file edits, commits, pushes, subagent invocations, and directory deletions).
4. When mentioning files or directories, always provide their full absolute paths.
5. Maintain chronological order from the beginning of the session to the current moment.
6. Style the two speakers differently so they can be told apart at a glance: wrap each User sentence in an inline code span (monospace font, highlighted background), and write each Agent sentence as plain text (normal font, no highlight). Start each label with a colored square so the speakers differ in color under any theme: 🟦 before **User:** and 🟧 before **Agent:**. A code span cannot hold a backtick, so drop backticks from User sentences.

## Example

1. 🟦 **User:** `Asked to rename /home/alex/Projects/app/src/old.ts to new.ts.`
2. 🟧 **Agent:** Renamed the file to /home/alex/Projects/app/src/new.ts and updated its two imports.
