# Severity scale for findings

The one scale every skill in this repo uses to label a finding: from a code review, a security or
numeric audit, a spec or doc critique, or a runbook check. A skill that reports or consumes findings
points here instead of defining its own levels.

## The four levels

| Level | What the owner does | Use it for |
|---|---|---|
| **CRITICAL** | **Fix now.** Stop other work on this change until it is fixed. | A security hole, data loss or corruption, money or another irreversible harm, or a broken contract that fails real users today. |
| **HIGH** | **Fix before merge.** Or write down why it stays. | A real bug, a broken invariant or safety rule, or a design flaw that is hard to undo once merged. |
| **MEDIUM** | **Fix when convenient.** It does not block the merge. | A maintainability problem, a narrow defect with a workaround, or an unclear or incomplete spec section. |
| **LOW** | **Optional.** Fix it if it is cheap. | Style, naming, wording, or a small suggestion. |

The same four levels cover every domain:

| Domain | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| Code review | Data loss on retry | Off-by-one in pagination | Duplicated parsing logic | Inconsistent variable name |
| Security or audit | Secret written to a log; a float in an order price | Missing authorization check on an internal route | Weak input validation behind auth | Outdated comment about a hash choice |
| Spec or doc critique | Spec contradicts an accepted decision, so the build would be wrong | An acceptance criterion cannot be tested | A section is ambiguous; two readings are possible | Typo or wording |

Not a severity: an **open question** for the author (the critical-thinking reviewer's output),
and the tags **refuted**, **contested** and **unverified**. Those are listed beside the four levels and
never replace them.

## How a finding is written

Every finding shown to the owner carries the level **and** its action, then its id:

```
- **HIGH (fix before merge) · F3** — Session token compared with `==` leaks timing. Fix: use a
  constant-time compare. — `src/auth/session.py:42`
```

- **Level word.** One of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, always spelled out. Never a bare
  letter (`C`, `H`, `M`, `B`, `S`) and never a level from another scale.
- **Action.** In parentheses right after the level, word for word from the table above:
  `(fix now)`, `(fix before merge)`, `(fix when convenient)`, `(optional)`. A section heading may
  carry it once instead (`## High Findings (fix before merge)`). Counts and machine-read fields
  (JSON `severity`, table cells, `CRITICAL 1 · HIGH 2 · MEDIUM 0 · LOW 3`) use the bare word.
- **Id.** `F1`, `F2`, ... (F for finding), numbered once per report in severity order, CRITICAL
  first. One sequence for the whole report: it never restarts per section, and it never encodes the
  level. `finding-fixer` matches its verdicts back by this id.
- **Level first.** Start the line or heading with the level, as above (a heading reads
  `### HIGH (fix before merge) · F3 — <title>`). `multi-agent-review`'s `loop_metrics.py`
  counts findings by a level word at the start of a line, and `code-cleaver`'s `stamp` strips the
  level-and-id prefix when it renumbers.

Parsers accept the level word in any case. Do not invent another scale (Blocker / Should-fix /
Minor, Major, Nit, P1 ...). When a source uses one, map it with the table below and say you did.

## Reading older reports

| Old label | Now |
|---|---|
| Blocker, B1, must-fix, must-fix-before-merge, Required, P0/P1 | HIGH; CRITICAL when it is a security hole or data loss (P0 is always CRITICAL) |
| Major | HIGH |
| Claude Code `/code-review` and `/ship`: Important, Pre-existing (`pre_existing`), Nit | Important (a bug the change adds or makes worse): HIGH, or CRITICAL when it meets that definition. Nit: LOW. Pre-existing means the bug was there before the change; that is not a level: give it the level the defect earns. Keep the source label in brackets after the dash (`— [Pre-existing] …`). `[Pre-existing]` is the written reason a HIGH may stay; a CRITICAL still stops work |
| Should-fix, S1, Important (from anything except Claude Code `/code-review` or `/ship`; assume this row when the source is unknown), can-fix-after, P2 | MEDIUM |
| Minor, M1 when it meant minor, Nit, Optional, Consider, Suggestion, P3 | LOW |
| FYI | Not a finding; a note |
| `C1` / `H1` / `M1` / `L1` ids (old `total-review` issues) | The letter was the level: CRITICAL / HIGH / MEDIUM / LOW. Renumber as `F1`... before handing them to `finding-fixer` |
| BLOCK / WARN / INFO verdicts | Unchanged: BLOCK means any CRITICAL, WARN means any HIGH, INFO means neither |

## Deliberate exceptions

- `audit-numeric-types` uses CRITICAL, HIGH and MEDIUM only. It has no LOW because a match too minor
  for MEDIUM is not reported.
- `inventory` ranks suggestions by **Priority** (Low / Medium / High). That is a to-do order for
  setup ideas, not a finding severity.
- Vendored `addyosmani-*` skills keep their upstream wording; `addyosmani-code-review-and-quality`
  carries a one-line mapping to this file.
