---
name: bro
description: Restate the last message in plain human language, with no jargon. Use when the user invokes /bro, asks to "say it plainly", "explain like I'm five", "in plain English", or wants jargon-free conversational speech.
menu-description: restate the last message in plain human language, no jargon
---

# Bro — Plain Human Language Restatement

When `/bro` is invoked or when asked to speak plainly:

## Instructions

1. **Target Content**:
   - If user input accompanies `/bro` (e.g., `/bro <topic or snippet>`), explain that specific text or concept plainly.
   - If invoked alone (`/bro`), restate the **immediately preceding assistant message** in the conversation.

2. **Strip All Jargon**:
   - Remove dense engineering buzzwords, complex academic phrasing, convoluted acronyms, and unnecessary abstraction.
   - If a technical term is unavoidable, immediately clarify it with a simple analogy.

3. **Speak Like a Human**:
   - Tone: Direct, concise, conversational, and grounded — like an experienced colleague explaining things over coffee.
   - Focus on what actually matters:
     - **The Big Picture**: What are we actually talking about?
     - **What Happened / What Changed**: Plain summary of the action or concept.
     - **Why It Matters**: The practical takeaway or impact.
     - **What's Next**: The next step in plain terms.
   - Avoid fluff, avoid robotic disclaimers, and keep it punchy.
