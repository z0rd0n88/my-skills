# Specification Template — New Capability

For net-new work. Changing something that already runs? Use
[`change-spec-template.md`](change-spec-template.md) instead.

Drop sections that genuinely don't apply — a three-file feature does not need
ten of them. **Never leave a section as a placeholder.**

H1: `# Spec — <Title>`.

## 1. Executive Summary
2–4 sentences: what is being built, for whom, and the outcome it delivers.

## 2. Problem & Goals
- **Problem statement** — the pain being solved.
- **Goals** — measurable objectives.
- **Non-goals** — explicitly out of scope, to bound the work.
- **Success metrics** — how "done and working" is judged.

## 3. Users & Context
Target users, their jobs-to-be-done, and the environment and constraints the
solution runs in.

## 4. Requirements
- **Functional** — numbered, testable statements (`FR-1`, `FR-2`, …). One
  behaviour per requirement; if it needs an "and", it is two. Prefix each with an
  RFC 2119 keyword — **MUST / MUST NOT / SHOULD / MAY** — so an implementer can
  tell a non-negotiable from a discretionary trade-off without asking.
- **Interdependencies** — conditional couplings between fields, states, or
  requirements ("selecting A restricts B") listed explicitly, separate from the
  independent FR list. Branching logic left implicit is branching logic the
  implementer invents.
- **Non-functional** — performance, security, scale, accessibility, compliance.
  Give numbers, not adjectives — and with every number, the **measurement
  method**: the tool, the query or fixture, and the time window. A target nobody
  can measure is an adjective wearing digits.
- **Terminology** — every domain noun used in an FR or an interface signature
  resolves to one canonical term. "Account" meaning Customer in FR-2 and User in
  FR-7 becomes two different types at build time. Where a term is overloaded,
  define it once here and use only that form.

### Global constraints
Project-wide rules every phase inherits — version floors, dependency limits,
naming and copy rules, platform requirements — one line each, **with exact
values, verbatim**. Not "use a recent Python"; `python >= 3.11`.

Every phase's requirements implicitly include this block. But when a spec is
too large to send whole, the pipeline extracts **the acceptance-criteria block
alone** — this block is not guaranteed to travel with it. So restate every
must-hold constraint as an acceptance criterion in each phase it binds (a
version floor becomes a check: `AC-2.3: lockfile pins python >= 3.11`). A
constraint stated only in prose does not survive that trip and will be
violated.

## 5. Architecture & Design
- Component map (diagram-in-prose or ASCII is fine).
- Data model / schema — **a field-level table per entity**: field, type,
  constraints (nullable, unique, length, format, default). For any enum or
  status field, enumerate **every** value and its meaning; a value the spec
  omits is a case the implementer omits. Give constraints exact values, the same
  discipline as global constraints.
- Interfaces & contracts (APIs, events, function signatures).
- Dependencies with **pinned, verified** versions. Cite where each was
  confirmed — a lockfile line or the docs page.
- Where the new code attaches to what already exists, cited `path:line`.

### File manifest
Before phasing the work, map every file the change creates or modifies and what
each is responsible for. **This is where decomposition gets locked in** — the
phases in §7 fall out of it, not the other way around.

| File | Create / Modify | Responsibility |
|---|---|---|
| `src/sync/client.py` | Create | S3 transport; retry and backoff |
| `src/sync/index.py:40-95` | Modify | Add manifest diffing |

Design rules:

- One clear responsibility per file. Prefer small, focused files — both a human
  and an agent reason better about a file they can hold in context at once, and
  edits to focused files are more reliable.
- Files that change together live together. Split by responsibility, not by
  technical layer.
- In an existing codebase, follow its established patterns. Don't unilaterally
  restructure — though splitting a file you're already modifying, if it has
  grown unwieldy, is fair to put in the spec.
- Boundary self-test, per file and interface: can someone understand what it
  does without reading its internals, and can the internals change without
  breaking consumers? Two noes → the boundary is wrong; fix the manifest, not
  the prose.
- No speculative seams: an interface with one adapter is a hypothesis. Introduce
  a seam only where something actually varies across it (a second adapter
  exists or is a named phase of this spec); otherwise call the thing directly.

## 6. Decision Records
One block per major decision:

```
### DR-<n>: <decision title>
- Decision: <what was chosen>
- Context: <forces at play — constraints, requirements>
- Rationale: <why — risk, feasibility, practicality, correctness>
- Alternatives considered:
  - <option A> — rejected because <reason>
  - <option B> — rejected because <reason>
- Consequences: <trade-offs accepted, follow-ups incurred>
```

A "decision" with no rejected alternative is a description. Cut it or find the
fork it actually sat at.

**What counts as major** — a choice earns a DR when all three hold: it is hard
to reverse, it would surprise a future reader without the context, and at least
one alternative was genuinely viable. Everything else is a line of §5 prose,
not a record; padding §6 with trivial calls buries the ones that matter.

**Name the decisive blocker.** "Rejected because <vague drawback>" invites the
implementer to reopen the alternative mid-build the moment the drawback looks
surmountable. State the specific reason it lost. If a DR accepts a known
negative consequence, that consequence appears as a row in §8 — a risk named
only inside a DR gets no mitigation.

## 7. Implementation Plan
Phased, smallest vertical slice first. **Each phase is a unit of work a build
orchestrator will spawn**, so give every one of them this shape:

```
### Phase <n> — <name>
- Outcome: <one sentence: what is true when this phase is done>
- Files:
  - Create: <exact/path/to/file.py> — <responsibility>
  - Modify: <exact/path/to/existing.py:123-145> — <what changes>
  - Test:   <tests/exact/path/to/test.py>
- Interfaces:
  - Consumes: <exact signatures this phase relies on from earlier phases,
    with the import path each symbol lives at>
  - Produces: <exact function/class names, parameter and return types that
    later phases will call — plus error modes, invariants, and ordering
    constraints callers must honor>
- Gotchas: <known pitfalls at this exact point — a racy API, a version quirk,
  an off-by-one trap — or omit the line>
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
Phase 2` conveys ordering, not that Phase 2 produced
`SyncClient.put(key: str, body: bytes) -> ETag`. Without exact names and types,
Phase 3 invents its own and the phases don't compose.

A signature alone is not the whole contract — state error modes, invariants,
call-ordering constraints, and the exact import path: the guesses a
type-checker never catches. `Gotchas:` pins a known pitfall to the phase that
will step on it; the §8 Risks table is too far away to save an implementer
mid-file. `Complexity:` is an advisory effort signal: `mechanical` = the spec
pins nearly everything, transcription suffices; `integration` = the pieces
are pinned, the judgment is in wiring them together; `design-judgment` = real
decisions remain. Today's consumers pin their own model choice — the field
exists so an orchestrator that does route effort can read it.

### Sizing a phase

Two rules, and a phase must satisfy both:

- **Numeric** — ≤ ~5 acceptance criteria and ~10 files, or `baton-runner`
  re-splits it and guesses at the seams.
- **Semantic** — a phase is the smallest unit that carries its own test cycle
  and is worth a fresh reviewer's gate. Fold setup, configuration, scaffolding,
  and docs into the phase whose deliverable needs them. Split only where a
  reviewer could meaningfully reject one phase while approving its neighbor.

Each phase ends with an independently testable deliverable. See
[`handoff-contract.md`](handoff-contract.md) for how to phrase a criterion so a
conformance pass can grade it.

Two exceptions to the vertical-slice default:

- **Wide refactor** — one mechanical change (rename a shared symbol, retype a
  column) whose blast radius fans across the codebase. Slicing it vertically
  breaks the build between slices. Phase it **expand → migrate in batches →
  contract** instead: add the new form alongside the old, move callers over in
  bounded batches, then delete the old form as its own final phase.
- **Prefactor** — when the current shape fights the change, make an explicit
  phase 1 that reshapes with no behaviour change ("make the change easy, then
  make the easy change"), rather than letting every later phase pay the
  friction. Its acceptance criterion is the untouched test suite still passing.

### No placeholders in a phase

These are spec failures, not stylistic preferences. Each one becomes a
decision the implementer makes without you, in fresh context, at build time:

- "Add appropriate error handling", "add validation", "handle edge cases" —
  say *which* errors, and what the caller sees for each.
- "Similar to Phase 2" — restate it. Phases are read out of order and in
  isolation; a cross-reference resolves to nothing.
- Any type, function, or config key referenced but defined in no phase and no
  file manifest entry.
- "TBD" / "TODO" / "decide during implementation" — that is a decision record
  or an open question, and either way it is not done.

## 8. Risks & Mitigations

| Risk | Likelihood / Impact | Mitigation or contingency |
|---|---|---|

## 9. Testing & Validation
The test strategy — unit, integration, E2E — and how the suite is run.

**Derive the criteria you didn't think of.** Before Phase 4, run every phase's
AC list against this checklist; each hit that applies and is missing becomes a
new `AC-<phase>.<n>`:

- empty input · maximum-size input · invalid types
- concurrent access · dependency/network failure · permission denied
- at least **one negative-path criterion per phase** — what must NOT happen,
  and what the caller sees instead
- for services: an observability check (the log line, metric, or alert that
  proves the thing is alive in production)

Mark any criterion that can only pass after a *later* phase also lands as
`[cross-phase]` — an advisory marker (no current grader parses it) telling a
per-phase reader the missing evidence is a sequencing artifact, so a FAIL on
it is not read as a defect.

Then the traceability matrix, so no requirement ships unproven:

| FR | Criterion | Check | Test |
|---|---|---|---|
| FR-1 | AC-1.2 | `POST /sync` with a stale token returns 401 | `tests/test_auth.py::test_stale_token` |

Every `FR-<n>` appears at least once. Every `AC-<n>.<m>` from §7 appears at
least once — **and in both directions**: an AC citing no FR is either scope
creep or a goal dressed as a check; cut it or write the requirement it proves.
**Restate the criterion text here** rather than only its ID — restated text
keeps the matrix self-contained, so it survives extraction if a consumer lifts
it (the canonical extracted unit is the acceptance-criteria block; bare IDs
extract to nothing either way). See
[`handoff-contract.md`](handoff-contract.md).

## 10. Open Questions
Anything still unresolved, and **what each one blocks**.

**The bar for a finished spec is this section being empty, and a non-empty
section blocks the handoff.** Every entry is a clarifying question the
implementation team would otherwise have to ask. If one survives to the end, it
means Phase 1 or the Phase 2 gate did not close it — take it back to the user,
don't ship around it and don't answer it yourself.

The sole exception is a question the user explicitly waives. Keep it here,
marked, and name what it gates:

```
- Q-<n>: <question> — blocks: <phase / requirement>
  WAIVED <date> by user: <why deferred, and what would close it>
  Options considered: <A — pros/cons; B — pros/cons>
  Recommendation: <A or B, with the reason>
  Impact of waiting: <what is built differently or not at all meanwhile>
```

The options and recommendation are not decoration. An implementer who hits the
waived question mid-build falls back on this recorded option set instead of
re-deriving the decision from scratch — which is the exact guess the waiver
mechanism exists to prevent.

A waived question makes the spec **partial**: the phases it gates are not
buildable yet, and each such phase says so with a `Gated on: Q-<n>` line in
its §7 block and a `[gated: Q-<n>]` prefix on its criteria.
