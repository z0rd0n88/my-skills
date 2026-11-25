---
name: audit-numeric-types
description: Use when a diff or directory touches financial code (prices, quantities, fees, balances, orders) to prove no Float/Double/number reached a money path; returns a deterministic PASS/FAIL.
---

# Audit Numeric Types — Financial Precision Gate

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

Audits a diff or directory for forbidden numeric types (Float/Double/number) on
financial values — prices, quantities, fees, balances, orders — across Kotlin,
TypeScript, and Python financial code paths. It returns a deterministic
PASS/FAIL verdict and is strictly read-only: it never edits code or writes
report files.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<diff range \| directory>` | a git ref range (e.g. `main...HEAD`) or a directory path | `git diff main...HEAD --name-only`, falling back to `HEAD~1` if `main` isn't the integration branch or the range is empty | Selects the file set to scan for forbidden numeric types on financial values |

## Overview

A PR that touches order submission can pass every test and still smuggle a `Double` into a price calculation. CI does not catch every case, and human review is fatigue-prone. This skill is the mechanical gate: it scans a change set for forbidden numeric types on financial values and returns a deterministic verdict.

**This is the canonical contract.** The `financial-precision-auditor` agent implements the same rules for context-isolated runs. It has two homes: ClaudeConfig `agents-parked/` (activated per `total-review-scaffold`), and, in Vista repos, the vista-dev plugin's `vista-dev:financial-precision-auditor`. If this file and an agent copy ever disagree, this file wins — update each agent copy to match.

## Read-Only Mandate

**Never modify anything.** No `Write`, `Edit`, no report files, no mutating shell commands (`git add`, `git commit`, `sed -i`, `>` redirection, formatters, codemods). Shell access is for read-only `git` (`diff`, `log`, `show`, `ls-files`) and search only.

If asked to fix what you find, output the suggested replacement as text and stop. A fix belongs in a separate, explicitly-requested step — patching mid-audit is how a "quick fix" ships unreviewed into a money path.

## Scope

| Repo | Language | Correct type | Forbidden |
|---|---|---|---|
| VistaTrader | Kotlin / Ktor | `java.math.BigDecimal` | `Float`, `Double` |
| VBE | Kotlin + TS wire layer | `BigDecimal` / `Decimal` (decimal.js) | `Double`, `number` |
| TradingBots (Bot 0 risk core) | Python | `decimal.Decimal`, explicit rounding mode | `float`, binary FP literals |

Do not hardcode one repo's module names. Discover the financial module roots first (VistaTrader: `Aggro/`, `Traitor/`, `core/`; TradingBots: the Bot 0 deterministic risk core; VBE: server + wire modules), then apply the contract to whatever roots exist.

## The Forbidden-Arithmetic Contract

- All monetary values: `java.math.BigDecimal` in Kotlin. Never `Float`, never `Double`.
- Wire format: JSON **strings** with `x-format: bigdecimal`. Never JSON numbers.
- TypeScript: `Decimal` from decimal.js. Never `number`, never `parseFloat`, never `parseInt`.
- Arithmetic operators (`*`, `+`, `-`, `/`) on financial values are **forbidden** in TypeScript.
- When uncertain: **refuse** rather than estimate.
- `dryRun=true` is the default; live submission requires explicit opt-in.

## Workflow

Enumerate the changed files:

```bash
git diff main...HEAD --name-only
```

If `main` is not the integration branch or the range is empty, fall back to `git diff --name-only HEAD~1` or the explicit range the caller supplied — and state which range you audited. If the caller names a directory instead of a diff, audit it in full and say so.

### Phase A — Kotlin scan

For each `.kt` file under `Aggro/`, `Traitor/`, or `core/`, grep for: `Float`, `Double`, `.toDouble()`, `.toFloat()`

Apply the same patterns to the equivalent financial module roots in any other repo.

### Phase B — TypeScript scan

For each `.ts` file under any `src/` folder, grep for: `": number"`, `parseFloat`, `parseInt`, `BigInt`

Additionally flag arithmetic operators applied to financial values.

### Phase C — Wire format scan

For each new or modified JSON schema, look for `"type": "number"` without `"x-format": "bigdecimal"`.

### Phase D — Python (TradingBots extension)

Not part of the original contract; applies only to Python financial code. Grep for `float(`, bare FP literals in money/qty expressions, `round(`, and `Decimal` built from a float (`Decimal(0.1)` — must be `Decimal("0.1")`). Flag any `Decimal` quantization without an explicit rounding mode.

## Refusal Rule (non-negotiable)

**Refuse to mark PASS if any hit exists in code paths under: `order/`, `submit/`, `sign/`, `sor/`, `fee/`.**

No exception for "it's only a log line", "it's a test helper", "the value is validated upstream", or caller insistence. A hit in those paths is FAIL. If you cannot tell whether a hit is on a financial value, treat it as a hit and FAIL.

## Output Contract

Deterministic — the same input must always produce the same verdict.

```
VERDICT: PASS | FAIL
Range audited: <git range or directory>
Files scanned: <n>   Hits: <n> (CRITICAL <n> / HIGH <n> / MEDIUM <n>)
```

Then a one-paragraph summary, then findings grouped by severity and, within each, by file:

```
### CRITICAL
<path/to/File.kt>
  - L142  val price: Double = ...
          → java.math.BigDecimal
  - L207  qty.toDouble()
          → keep BigDecimal; drop the conversion
```

Severity is mechanical, not judgement:

| Condition | Severity |
|---|---|
| Any hit under `order/`, `submit/`, `sign/`, `sor/`, `fee/` | CRITICAL (fix now) — forces FAIL |
| Hit on a value reaching a price/qty/fee/balance field elsewhere | HIGH (fix before merge) |
| Hit in test/fixture/telemetry code with no path to a financial value | MEDIUM (fix when convenient) |
| Match on a clearly non-financial value (see heuristics) | Not reported |

`PASS` requires zero CRITICAL **and** zero HIGH. Any CRITICAL → FAIL. Zero CRITICAL with HIGH present → FAIL, HIGH list is the blocking set. MEDIUM alone → PASS with the list attached as advisory. The levels are the repo-wide scale in
`refs/severity-scale.md`; this audit has no LOW, because a match too minor for MEDIUM is not reported.

Close every FAIL with the minimum set of changes required to reach PASS.

## Heuristics — Confirm Before Flagging

Read the surrounding lines first. Ordinarily **not** findings:

- `Double`/`Float` on latency, durations, display-only percentages, scores, or ML features with no path to an order field.
- `parseInt` on a page size, retry count, array index, or port.
- `BigInt` for a chain-native integer amount (wei, satoshi) where the integer *is* the exact representation — flag only if mixed with fractional arithmetic.
- `"type": "number"` for a timestamp, sequence number, or count.
- A `Double` inside a comment, string literal, or KDoc block.

Always findings regardless of context: any `.toDouble()`/`.toFloat()` applied to a `BigDecimal`; any `Decimal`-to-`number` narrowing before serialization; any float round-trip through JSON on a money field.

When context is ambiguous, the refusal rule wins — record the hit and let the verdict fail.

## Where This Fits

This is the REVIEW-phase gate for financial repos. Run it **before** reading a diff for logic — a numeric-type failure invalidates any correctness judgement made downstream of it.

---

**A missed `Double` in the submit path is an irreversible loss of real money.** Verify every finding, never edit, and never soften a FAIL because the caller wants a merge.
