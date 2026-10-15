# Specification Template — Change to Existing Code

For rewrites, refactors, migrations, and defect-driven redesigns — anything
where working code already exists and the spec must respect it. Net-new work
uses [`spec-template.md`](spec-template.md).

A change spec must establish **what is true today** before it can justify what
should be true tomorrow, and the diff between those two states is the actual
deliverable. Sections 2 and 3 below are the load-bearing ones; they have no
equivalent in the net-new template.

Drop what doesn't apply. **Never leave a section as a placeholder.**

H1: `# Spec — <Component> <Change>`.

## 1. Context & Problem Statement
- What the component is for, in two sentences.
- **Observed behaviour** — what it actually does today, with evidence: log
  lines, measurements, reproductions, `path:line`. Not "it feels slow".
- Why this matters — the cost of leaving it alone.

## 2. Current Architecture
The map a reader needs before any proposed change makes sense.

- **Files** — each one, one line on its job, cited `path:line`.
- **Call flow** — trace one representative execution end to end.
- **Data shapes** — for every entity or config the change touches, the
  field-level facts verbatim from the code, cited `path:line`: types,
  constraints (nullable, unique, length, default), and **every** value of any
  enum or status field. A value the spec omits is a case the new code drops.
- **Real vs. mocked** — for each dependency or integration cited, note whether
  the cited code path is a live integration or a stub/mock (fixture data,
  `*.mock.*` files, hardcoded returns). A spec that cites a mock as a working
  integration specifies against behaviour that does not exist.
- **External contracts that must not break** — public APIs, on-disk formats,
  env vars, hook interfaces, anything with a consumer you don't control.
  Everything listed here becomes a constraint in §4 and a regression test
  in §8.

Read this before you write it. A current-architecture section reconstructed
from memory is where change specs go wrong: the plan is then correct about a
system that does not exist.

## 3. Root Cause Analysis
One block per defect or deficiency driving the change:

```
### D<n> — <short name> *(critical | high | medium | low)*
- Symptom: <what is observed>
- Mechanism: <why it happens, cited path:line>
- Evidence: <the log line, measurement, or repro that proves it>
```

Severities set the order of §7 where dependencies leave room (§7 states the
precedence). A defect with a symptom but no mechanism is a hypothesis — mark
it as one, or go find the mechanism.

## 4. Design Constraints
What the solution may not do, split into:

- **Established empirically** — what you tested and observed about the platform
  or environment, with how you observed it. These are facts with a shelf life;
  say what would invalidate them.
- **Imposed** — compatibility, performance budgets, the contracts from §2, and
  anything the user ruled in or out at the Phase 2 gate.

### Global constraints
The subset every phase inherits — version floors, dependency limits, naming
rules, platform requirements — one line each, **with exact values, verbatim**.
Not "keep it compatible"; `hook must exit 0 within 2 s on a cold cache`.

When the spec is too large to send whole, the pipeline extracts **the
acceptance-criteria block alone** — this block is not guaranteed to travel
with it. Restate every must-hold constraint as an acceptance criterion in each
phase it binds; a constraint that lives only in §4 prose will not reach the
implementer.

## 5. Target Design
The end state, structured to mirror §2 so the reader can diff them. For each
subsystem: what it becomes, and which `D<n>` from §3 that closes.

Include the data or decision model (schema, state machine, decision matrix) and
the interfaces after the change.

## 6. Decision Records
One block per major decision:

```
### DR-<n>: <decision title>
- Decision: <what was chosen>
- Context: <forces at play — constraints from §4, defects from §3>
- Rationale: <why — risk, feasibility, practicality, correctness>
- Alternatives considered:
  - <option A> — rejected because <reason>
  - <option B> — rejected because <reason>
- Consequences: <trade-offs accepted, follow-ups incurred>
```

For a change spec, **"leave it as is" is always an alternative** — record why
the status quo lost. If it didn't lose clearly, the change may not be worth it.

**What counts as major** — a choice earns a DR when all three hold: hard to
reverse, surprising without the context, and at least one alternative was
genuinely viable. **Name the decisive blocker** in each rejection — a vague
drawback invites the implementer to reopen the alternative mid-build. A
negative consequence a DR accepts appears as a row in §10; a risk named only
inside a DR gets no mitigation.

## 7. Implementation Plan
Open with the **file manifest**: every file the change creates, modifies, or
deletes, one line each with its responsibility — the full set, before any
phasing. The phases below fall out of it, not the reverse, and Phase 4 checks
that every manifest entry lands in exactly one owning phase (entries an
expand → migrate → contract or prefactor phase group explicitly shares are the
sanctioned exception).

Then the phases, organized by file or module — the shape a change actually
lands in. "By file or module" names each phase's scope, not its sequence:
order the phases by dependency first, then by §3 severity (highest first)
where dependencies leave room. Each phase is a unit of work a build
orchestrator will spawn:

```
### Phase <n> — <file or module>
- Outcome: <one sentence: what is true when this phase is done>
- Changes:
  - Modify: <path:line> — <what changes>
  - Create: <path> — <responsibility>
  - Delete: <path or symbol> — <why it is now dead>
  - Test:   <tests/path>
- Interfaces:
  - Consumes: <exact signatures this phase relies on from earlier phases,
    with the import path each symbol lives at>
  - Produces: <exact names, parameter and return types later phases will call —
    plus error modes, invariants, and ordering constraints callers must honor>
  - Unchanged: <the §2 contracts this phase must not break>
- Gotchas: <known pitfalls at this exact point, or omit the line>
- Complexity: <mechanical | integration | design-judgment — or omit>
- Non-goals: <what this phase deliberately leaves alone>
- Depends on: <earlier phase, or "none">
- Gated on: <Q-<n> of a waived open question this phase cannot build
  without — or omit the line>
- Acceptance criteria:
  - AC-<n>.1: <a check that returns PASS or FAIL>
  - AC-<n>.2: …
```

**The Interfaces block is not optional.** Each phase is built in **fresh
context** — its implementer sees that phase and little else. `Depends on:
Phase 2` conveys ordering, not that Phase 2 changed `classify()` to return
`(verdict: str, confidence: float)`. Without exact names and types, the next
phase calls the old signature. In a change spec the `Unchanged` line matters
just as much: it is how an implementer who cannot see §2 learns what they are
forbidden to break.

A signature alone is not the whole contract — state error modes, invariants,
call-ordering constraints, and the exact import path: the guesses a
type-checker never catches. `Gotchas:` pins a known pitfall to the phase that
will step on it. `Complexity:` is an advisory effort signal: `mechanical` =
the spec pins nearly everything, transcription suffices; `integration` = the
pieces are pinned, the judgment is in wiring them together; `design-judgment`
= real decisions remain. Today's consumers pin their own model choice — the
field exists so an orchestrator that does route effort can read it.

Name deletions explicitly — dead code left behind is the most common silent
failure of a change spec.

### Sizing a phase

Two rules, and a phase must satisfy both:

- **Numeric** — ≤ ~5 acceptance criteria and ~10 files, or `baton-runner`
  re-splits it and guesses at the seams.
- **Semantic** — the smallest unit that carries its own test cycle and is worth
  a fresh reviewer's gate. Fold setup, config, and docs into the phase whose
  deliverable needs them; split only where a reviewer could meaningfully reject
  one phase while approving its neighbor.

See [`handoff-contract.md`](handoff-contract.md).

Two exceptions to the vertical-slice default — both common in change specs:

- **Wide refactor** — one mechanical change (rename a shared symbol, retype a
  column) whose blast radius fans across the codebase. Phase it **expand →
  migrate in batches → contract**: add the new form beside the old, move
  callers in bounded batches, delete the old form as its own final phase.
- **Prefactor** — when the current shape fights the change, an explicit first
  phase that reshapes with no behaviour change ("make the change easy, then
  make the easy change"). Its acceptance criterion is the untouched suite
  still passing.

### No placeholders in a phase

Spec failures, not stylistic preferences — each becomes a decision the
implementer makes without you, in fresh context, at build time:

- "Add appropriate error handling" / "handle edge cases" — say *which* errors
  and what the caller sees for each.
- "Similar to Phase 2" — restate it. Phases are read out of order, in isolation.
- Any type, function, or config key referenced but defined in no phase.
- "TBD" / "decide during implementation" — that is a decision record or an open
  question, and either way it is not done.

## 8. Test Strategy
- **A regression test per `D<n>`** — the test that fails on today's code and
  passes after. Name it. This is the strongest evidence a change spec can
  carry, and the cheapest thing to forget.
- **Contract tests** for every item in §2's must-not-break list.
- **Boundary and replay tests** where behaviour changed at a threshold.
- **Derive the criteria you didn't think of** — run each phase's AC list
  against: empty input, maximum-size input, invalid types, concurrent access,
  dependency failure, permission denied; at least **one negative-path
  criterion per phase**; an observability check where the component is a
  service. Each applicable miss becomes a new `AC-<phase>.<n>`.
- Mark criteria that can only pass after a later phase lands as
  `[cross-phase]` — an advisory marker (no current grader parses it) telling a
  per-phase reader the missing evidence is a sequencing artifact, not a
  defect.

Then the traceability matrix:

| D`<n>` / FR | Criterion | Check | Test |
|---|---|---|---|
| D1 | AC-2.1 | classifier returns within 2 s under a held lock | `tests/test_hook.py::test_no_deadlock` |

**Restate the criterion text here**, not only its ID — restated text keeps
the matrix self-contained, so it survives extraction if a consumer lifts it
(the canonical extracted unit is the acceptance-criteria block; bare IDs
extract to nothing either way). See
[`handoff-contract.md`](handoff-contract.md).

## 9. Rollout & Verification
- **Sequence** — the order changes land, and what is safe to ship alone.
- **Backward compatibility** — migrations, shims, and when each is removed.
- **Rollback** — the trigger and the procedure.
- **Post-cutover gates** — what is measured after shipping, when, and the
  number that says it worked. Distinct from §8: these run against production
  behaviour, not the suite.

## 10. Risks & Open Questions

| Risk | Likelihood / Impact | Mitigation or contingency |
|---|---|---|

Then open questions, each with **what it blocks**.

**The bar for a finished spec is the open-questions list being empty, and a
non-empty list blocks the handoff.** Every entry is a clarifying question the
implementation team would otherwise have to ask — take it back to the user
rather than shipping around it or answering it yourself.

The sole exception is a question the user explicitly waives. Keep it here,
marked, and name what it gates:

```
- Q-<n>: <question> — blocks: <phase / defect>
  WAIVED <date> by user: <why deferred, and what would close it>
  Options considered: <A — pros/cons; B — pros/cons>
  Recommendation: <A or B, with the reason>
  Impact of waiting: <what is built differently or not at all meanwhile>
```

The recorded options are what an implementer falls back on if they hit the
waived question mid-build — instead of re-deriving the decision from scratch,
which is the guess the waiver exists to prevent.

A waived question makes the spec **partial**: the phases it gates are not
buildable yet, and each such phase says so with a `Gated on: Q-<n>` line in
its §7 block and a `[gated: Q-<n>]` prefix on its criteria.
