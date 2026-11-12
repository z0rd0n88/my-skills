---
name: skill-sheriff-cc
description: Audits a skill against Anthropic's official skill docs, fetched fresh each run, citing a doc quote for every finding. Use to evaluate, review or audit a skill, or fact-check another skill reviewer.
argument-hint: "[skill-dir] [claims to fact-check]"
---

# Skill Sheriff (Claude Code)

The official docs are the only law. Every rule you apply and every finding you report stands on a **quote**: words copied exactly from a page fetched in this run, with its URL. A point you cannot quote is not reported. The docs define no score or grade, so the report has none.

`scripts/sheriff.py` (next to this file) does the mechanical work. Run it with `python3 -I`. Use the scratchpad, or another temp folder, as `<workdir>`, never the target repo.

## Steps

1. **Fetch the law.** Run `sheriff.py fetch <workdir>`. Done when it exits 0. When any page fails, stop and report the failure: an audit from memory is exactly what this skill replaces. If a core page has moved, find its new URL in the index list the command prints and re-run with that URL appended.
2. **Check for new law.** Read the "Other skill pages" list the fetch printed. When the target ships through a channel one of those pages governs (a plugin, the API, the Agent SDK), fetch that page with `sheriff.py fetch <workdir> <url>...`. When nothing in the target's files says how it ships, fetch nothing extra and judge by the core pages.
3. **Write the ledger.** Read every fetched page in `<workdir>/docs/`, in chunks when a page is long. Write `<workdir>/ledger.md` as a table: `id | kind | surface | rule | quote | source URL § heading`. One row per rule the docs address to skill authors; a rule stated on several pages is one row with one quote. **kind** is *Required* (a validation limit or "must": "Maximum", "Must contain", "Cannot", "requires") or *Recommended* ("should", "consider", a best practice, a checklist item). **surface** is *platform*, *Claude Code* or *both*, after the page the rule comes from.
   Rules on the best-practices page are Recommended unless they restate a validation limit. Sections about something other than authoring a skill (installing, loading, API calls, analytics), or about a feature the target does not use, go at the foot of the ledger as `skipped: <headings> — <why>`; one line may cover several headings. Done when every heading of every fetched page is either a source of rows or on a skipped line.
4. **Measure the target.** Run `sheriff.py measure <skill-dir>` for character counts, line counts, fields, file references and their existence. Read the target's SKILL.md and every file it links.
5. **Judge every ledger row** against the target: **Pass**, **Fail** (Required rule broken), **Gap** (Recommended rule not met), **N/A** (rule does not apply, say why), or **Can't verify** (only a rule about something outside the files, such as "Tested with Haiku, Sonnet, and Opus"). Anything the files could show but don't is a Gap or Fail: no evaluations in the skill folder is a Gap against "At least three evaluations created". Each verdict names its evidence: a measurement or `file:line`. When the platform and Claude Code docs disagree on a row, give one verdict per surface on that row.
6. **Write the report** to `<workdir>/report.md` in the format below, then run `sheriff.py quotes <workdir> <workdir>/report.md`. When you cannot write files (some subagents can't), pipe the report text to `sheriff.py quotes <workdir> -` instead. Done when it exits 0. For each quote it cannot find, copy the exact text from the doc or drop the finding.
7. **Deliver** the report to the user. Each finding carries its quote and link, and the Fails come first.

## Where the docs differ

The platform docs and the Claude Code docs set different rules for the same field. Quote both, and say which applies where. For example, the platform frontmatter "requires `name` and `description`", while Claude Code says "All fields are optional". The platform caps `description` at 1,024 characters, while Claude Code truncates `description` plus `when_to_use` at 1,536 characters in the skill listing. Judge a skill by the surface it ships to. A skill under a `.claude/skills/` directory, directly or through a symlink, ships to Claude Code. A skill uploaded to claude.ai or the API ships to the platform. When nothing shows the surface, judge by both. A row whose verdict differs by surface is filed under its worse verdict, with the split written in its Evidence line.

## Fact-checking another reviewer

When the user hands over claims from another evaluator and no skill to audit, run steps 1–3 with the ledger limited to rules on the claims' topics, skip steps 4–5, and give each claim one verdict: **Supported** (quote the rule), **Contradicted** (quote the rule that says otherwise), or **Not in the docs** (quote the nearest real rule on that topic and name the pages searched). A rule another tool invented is "Not in the docs", however sensible it sounds. The report has one `## Claim: <claim>` section per claim with its verdict and quotes, the summary counts verdicts, and step 6's quote check still applies.

## Report format

Every ledger row appears exactly once, Pass rows included, and each carries its quote on a line starting `> "` so `sheriff.py quotes` checks all of them. Summary counts are ledger rows. Sources are full URLs.

```markdown
# Skill Sheriff: <skill-name>
Docs fetched <date>: <list of URLs>
Summary: <n> Fail, <n> Gap, <n> Pass, <n> N/A, <n> Can't verify (of <n> ledger rows)

## Fail
### <rule in a few words> (Required)
Evidence: <measurement or file:line>
> "<exact words from the doc>" — <url> § <heading>
Fix: <the smallest change that satisfies the quote>

## Gap
(same block shape as Fail)

## Pass
- <rule>: <evidence>
  > "<exact words>" — <url> § <heading>

## N/A and Can't verify
- <rule>: <reason>
  > "<exact words>" — <url> § <heading>
```
