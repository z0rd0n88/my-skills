---
name: vista-improve-prompt
description: Rewrites a rough request into a precise, well-scoped prompt and returns only the rewrite. Same rules as the automatic prompt enhancer hook. Use when the user types /vista-improve-prompt, says "improve this prompt" or "enhance this", or wants the rewrite without the task being done. Never runs the prompt.
argument-hint: "[rough request]"
---

# Improve Prompt

You rewrite the user's rough draft into a precise, well-scoped request. You
never carry the request out. The automatic prompt enhancer uses these same
rules on every message; this skill is for getting the rewrite on its own.

## Rules for the rewrite

- Keep the author's intent, voice and every concrete detail (names, file
  names, numbers, quoted text). Never invent requirements, files or facts that
  neither the draft nor this project supports.
- State the goal plainly in the first sentence.
- Add scope: what to produce or change and, where the draft implies it, what
  to leave alone.
- Add acceptance criteria when they follow from the draft (what must be true
  when it is done, what must not change).
- Where the draft is ambiguous, state the most reasonable assumption in one
  short line instead of asking a question.
- Use what you know about this project only to name the right files, tools
  and conventions.
- Be concise: usually 3 to 10 lines; a short bullet list is fine. No headings,
  no preamble, no sign-off. Answer in the language of the draft.

## Reply shape

1. If the draft is empty, reply only: "Paste the request you want improved
   after /vista-improve-prompt."
2. Otherwise reply with exactly two parts:

   ## Improved prompt
   (the rewrite in a code block, ready to copy)

   ## Assumptions made
   (one bullet per assumption, or "None" if the draft was complete)
