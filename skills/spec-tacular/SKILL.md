---
name: spec-tacular
description: "User-invoked only; never auto-trigger. Code-grounded engineering spec through gated phases: recon, blueprint-approval gate, draft with decision records and per-phase acceptance criteria."
argument-hint: "<concept or feature idea...>"
---

# Spec-tacular

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop — do not run any other step in this
skill.

> **⚠️ Multi-phase, multi-agent run** — dispatches several exploration and
> adversarial-review subagents and writes a spec file to disk under
> `docs/specs/`; expect a token/agent budget well beyond a single one-shot call.

Turns a concept into a code-grounded implementation spec through four gated
phases — reconnaissance, a blueprint-approval gate, a fully drafted
specification with decision records and acceptance criteria, and a
verification-and-handoff gate. Reach for it instead of writing a plan by hand
when the deliverable needs `path:line`-grounded citations, decision records,
and acceptance criteria a downstream builder skill (`baton-runner`,
`zord-multi-agent-developer`, `zord-code-rinse-repeat`) can execute without follow-up
questions — not for evaluating an existing proposal or generating candidate
ideas, which are separate skills.

| Option | Values | Default | Effect |
|---|---|---|---|
| `<concept or feature idea>` | free text (required) | — | The idea to turn into a spec; becomes the Phase 1 problem statement. |
| output path | any file path (optional, stated in the request) | `docs/specs/<slug>.md` | Where the spec file is created in Phase 3; the skill confirms the path if none is given. |

Drive a concept from a vague idea to a specification an implementation team —
human or agent — can execute **without a single clarifying question**. Phases 0
through 4, in order. **Do not advance until the current phase is fully resolved.**

**Write for this reader:** a skilled engineer who knows nothing about this
codebase, this toolset, or this problem domain, who will build each phase in
**fresh context** without seeing the others, and who cannot ask you anything.
Every gap they hit, they fill by guessing. That reader model is what separates a
spec that builds from a spec that reads well.

**User-invoked only — do NOT auto-trigger.** Run this skill only when the user
explicitly invokes it (`/spec-tacular`, or a direct request to spec something
out). Do not activate it just because a message mentions a spec, plan, or design.

## Ground rules

These hold in every phase; they are what makes the output *code-grounded* rather
than plausible-sounding.

1. **Cite or don't claim.** Every statement about code that already exists
   carries a `path:line` reference you actually read. No citation → either go
   read it, or restate it as an explicit assumption under Open Questions. A
   citation proves the line exists, not that it is where the value is decided:
   for an in-repo default the declaration site is only corroboration, and the
   composition root that resolves the value is the authority. A parameter
   defaulting to `false` settles nothing if the caller passes `true`.
2. **Verify every version, API, and dependency.** Check the docs or the
   lockfile. A version you did not look up is a guess, and a guess in a spec
   becomes a bug in the build.
   - **An absence claim needs the authority, not a proxy.** A search that
     returns nothing answers "is this written down", never "does this exist",
     so it can never carry a claim that something is missing. For a reachable
     third-party service the docs are corroboration and the live service is
     the authority — issue the request. Until you have, "X does not exist" is
     an Open Question, not a finding, and satisfying this rule with docs alone
     is what makes the wrong version of it credible.
3. **Persist before you polish.** The spec file exists on disk from the moment
   the blueprint is approved (Phase 3, step 1). A spec that lives only in the
   conversation is lost to compaction.
4. **Recommend, then ask.** On a real roadblock, stop — but never with a bare
   question. Give your professional recommendation, the reasoning, and the full
   option set. Prefer `AskUserQuestion` when the options are crisp.
5. **Write for the machine too.** The finished spec is fed to `baton-runner`,
   `zord-multi-agent-developer`, or `zord-code-rinse-repeat`. Meet
   [`references/handoff-contract.md`](references/handoff-contract.md) — it is a
   hard requirement, not a nicety.

## Phase 0 — Calibrate

Three cheap decisions before any exploration, each stated to the user in one
line. None is a gate.

- **Shape.** Is this net-new capability, or a change to something that already
  runs?
  - Net-new → [`references/spec-template.md`](references/spec-template.md)
  - Change / rewrite / fix to existing code →
    [`references/change-spec-template.md`](references/change-spec-template.md)
  - Genuinely both → change-spec shape, with a Target Design section that
    stands alone.
- **Depth.** Size the spec to the work: how many implementation phases, roughly
  how many files. One vertical slice touching ~3 files does not need ten
  sections — say so, and collapse the template accordingly. Dropping a section
  that does not apply is correct; leaving it as a placeholder is not.
- **Scope.** If the concept spans multiple independent subsystems, propose
  splitting it into one spec per subsystem, each producing working, testable
  software on its own. A spec covering three subsystems interleaves phases
  across boundaries no reviewer can gate.

If the concept is too vague to calibrate, that is Phase 1's first question.

## Phase 1 — Reconnaissance & Alignment

Build a complete mental model *before* proposing anything.

- **Explore.** Read the relevant code and docs. Map the domain, the existing
  architecture, and the hard constraints. For multi-file traces, dispatch
  exploration agents on **distinct angles** — similar existing features,
  architecture and conventions, test patterns — rather than one generic pass;
  each angle a pass misses is a pattern the draft later invents instead of
  follows. Record `path:line` as you go — those citations are the raw material
  for the spec, and re-deriving them later costs more than noting them now.
  Two checks while exploring:
  - **Prior decisions.** Scan `docs/adr/`, prior specs, and `CONTEXT.md` for
    settled decisions the concept touches. A new spec that silently
    contradicts a standing decision ships that contradiction into the build.
  - **Real vs. mocked.** When citing an integration, confirm the cited path is
    live code, not a stub or fixture — specifying against a mock specifies
    behaviour that does not exist.
- **Identify.** Primary goal, target users, and success metrics.
- **Research.** Only where facts are missing — vendor MCP servers and
  project-local vendor skills **first** (they are already configured for this
  repo and are routinely left untouched for whole runs), then library docs,
  prior art (`gh search`), standards, feasibility. When the fact is
  load-bearing, probe the live API rather than reading about it.
- **Clarify.** Where intent or outcome is ambiguous, ask **targeted, specific**
  questions. Resolve every gap here; an unresolved gap costs an order of
  magnitude more once it is baked into a draft.
  - **Triage fact vs. decision first.** A *fact* discoverable in code or docs
    gets looked up, never asked — asking pollutes Open Questions and Decision
    Records with guessed rationale for checkable things. A *decision* is the
    user's; put it to them and wait.
  - **Pin overloaded terms.** When a domain noun is ambiguous ("account" —
    Customer or User?), propose a canonical term and use only that form from
    then on. Each overloaded term that survives becomes a different concrete
    type in each phase that guesses it.

**Stopping rule.** Stop exploring when you can state the problem, the users, the
constraints, and the success metrics with no open unknowns — *not* when you have
read everything. If two more files would not change a single decision in the
spec, you are done. If you cannot reach that state by asking, the blocker is a
Phase 2 open question, not a reason to keep reading.

## Phase 2 — Strategic Blueprint (GATE)

Align on direction before writing the full spec. Present three things, then
**stop**:

1. **Executive summary** — the proposed solution in 2–4 sentences.
2. **Outline** — the section map, one line each. Not prose.
3. **Load-bearing decisions** — the forks where a different choice produces a
   materially different spec. For each: the option you recommend, the leading
   alternative it kills, and the one-line reason. This is the part worth the
   user's attention; an outline alone is weak signal, because a section list
   looks the same whichever way the hard calls went.

   Present them **in dependency order** — an upstream fork before every fork it
   gates. A decision settled before the one it depends on silently assumes a
   branch the user hasn't chosen yet, and the contradiction surfaces as
   incompatible phases in the draft.

Also list any open question you could not close in Phase 1, and say what each
one blocks.

**Hard stop.** Ask the user to **Approve** or **Adjust** — `AskUserQuestion`
when the choices are crisp. Do not draft Phase 3 until they approve. If they
adjust, revise and re-ask. Silence is not approval; neither is a question about
something else.

## Phase 3 — Comprehensive Specification

Only after approval.

1. **Create the file first.** Write the approved outline to disk as a skeleton —
   `docs/specs/<slug>.md` by default, or the path the user named. Confirm the
   path if none was given. Then fill it section by section with `Edit`. An
   interrupted run resumes from the file instead of restarting.
2. **Fill each section** per the chosen template. Detailed, concise, technical.
3. **Record every decision.** At each design or technical junction, write a
   Decision Record: what was chosen, the forces at play, why (risk, feasibility,
   practicality, correctness), **what else was considered and why it lost**, and
   the consequences accepted. A decision with no rejected alternative is
   either not a decision or not finished.
4. **Lock the decomposition before phasing.** Write the file manifest first —
   every file created, modified, or deleted, and what each is responsible for.
   In the net-new template this is §5's manifest table; in a change spec, list
   the full file set at the top of §7 before drawing phases. Either way the
   phases fall out of the manifest, not the reverse.
5. **Give every phase its interface block.** `Consumes` and `Produces`, with
   exact names, parameter types, and return types. A dependency edge without
   signatures is how phases stop composing.
6. **Number the acceptance criteria.** Each implementation phase carries its own
   `AC-<phase>.<n>` criteria, and every functional requirement maps to at least
   one. This is the handoff contract — see
   [`references/handoff-contract.md`](references/handoff-contract.md).
7. **Fact-check as you write**, per Ground rule 2. Never propose a capability
   you have not confirmed exists.

## Phase 4 — Verify & Hand Off (GATE)

Run the checks against **the written file**, not your memory of it. State the
result; do not claim completion without it.

Two stages, in order: the mechanical checks below, then the **Phase 4b**
adversarial read once they pass. The gate is not cleared until both have run.

This is the second hard stop. A failed check does not downgrade the spec to
"done with caveats". A mechanical failure — a stale name, a missing
restatement — you fix and re-run Phase 4; a decision-shaped failure goes back
to the user.

**Retraction sweep before any re-run.** When a revision deletes or inverts a
decision record, every mention of the deleted design elsewhere becomes a
dangling pointer — that is a rename refactor, not an edit. Before re-running
the checks or re-dispatching a reviewer: grep every distinctive term of the
deleted design across all spec files, and open each disposition's named file to
confirm the claimed fix landed *there* and not in a sibling. A fix recorded as
applied is a claim like any other. This runs before the reviewer, not instead
of it.

- `grep -nE 'TBD|TODO|FIXME|\bXXX\b|<[A-Za-z][A-Za-z -]*>|\.\.\.' <spec>` — disposition
  every hit: a real placeholder to fill, a template token to remove, or a
  legitimate literal to keep (a generic like `Promise<void>`, an example
  payload like `{"error": "..."}`). Only the first two require action; state
  which each hit is.
- **Semantic placeholders too**, which no grep catches: "add appropriate error
  handling", "handle edge cases", "similar to Phase N", "decide during
  implementation". Each is a decision deferred to someone who cannot ask you.
- **Name and type consistency.** Every symbol a later phase `Consumes` matches
  what an earlier phase `Produces`, exactly. A function defined as
  `clear_layers()` in Phase 3 and called as `clearFullLayers()` in Phase 7 is a
  bug you shipped in the spec.
- **Nothing referenced but undefined.** Every type, function, and config key
  named in a phase appears in the file manifest or an earlier phase's
  `Produces`.
- Every `FR-<n>` (or `D<n>` in a change spec) appears in at least one
  acceptance criterion, and every file in the manifest appears in exactly one
  owning phase — the sanctioned exception being entries an
  expand → migrate → contract or prefactor phase group explicitly shares.
- **Both directions.** Every `AC-<phase>.<n>` cites at least one FR or `D<n>` —
  an orphan criterion is scope creep or a goal dressed as a check.
- **No phase contradicts a global constraint.** Read each phase's Files,
  Interfaces, and criteria against the Global Constraints block; symbols are
  covered by the type-consistency check, but a constraint violation (a version
  below the floor, a forbidden dependency) is not.
- Every DR's accepted negative consequence appears as a row in the Risks table.
- Every `AC-<phase>.<n>` is a check someone can run, phrased so it can come back
  PASS or FAIL — not a feeling, not "works correctly".
- Every `DR-<n>` names at least one rejected alternative.
- No implementation phase exceeds ~5 acceptance criteria or ~10 files (split it
  if it does — `baton-runner` will otherwise re-split it, guessing at the
  seams).
- Every implementation phase carries at least one negative-path criterion —
  what must NOT happen and what the caller sees instead — and each criterion
  states its precondition (given <state>, when <action>, then <observable>).
- The traceability matrix restates each criterion's text, keeping the matrix
  self-contained if a consumer lifts it (the canonical extracted unit is the
  acceptance-criteria block).
- Every phase carries a one-sentence Outcome and explicit non-goals — with the
  criteria themselves, the three hard requirements `baton-runner` grades on.
- Every `WAIVED` open question names the phases it gates, and each gated phase
  carries a matching `Gated on: Q-<n>` line.
- Every dependency carries a version you verified.
- **Open Questions is empty** — see below.

### Phase 4b — Adversarial read

Run this **after every check above passes**, and **before** the handoff gate
below. One fresh subagent, once. It supersedes the old optional "dispatch a
subagent to read the spec cold" bullet, which was too weak to rely on.

**Why it exists.** Every check above compares the spec **to itself** — symbols
resolve, criteria trace to requirements, nothing is left `TBD`. None of them can
ask the only question that matters at handoff:

> Can this spec pass all of its own checks and still cause the wrong thing to be
> built?

It can, easily. Perfect `FR-<n>` → `AC-<phase>.<n>` traceability where the
criteria measure the wrong thing is *fully consistent and fully wrong*. That gap
is structural, not an oversight in the list — a self-comparison cannot detect it,
so it needs a reader whose job is to attack the document rather than verify it.

**Why here and nowhere else.**

- **Not before the mechanical checks.** They are cheap and catch stale names,
  placeholders, and orphan criteria. An adversary reading an unfiltered spec
  spends its attention on noise a grep would have caught for free.
- **Not after the handoff gate.** Phase 4 loops — a mechanical failure sends you
  back to fix and re-run, an unresolved question goes back to the user. An audit
  placed after the gate would judge a document that is still changing.
- **So: last thing inside Phase 4.** The spec it reads is already internally
  consistent, and its output feeds the gate decision instead of arriving after it.

**Dispatch.** One fresh subagent with **no prior context** — that is the whole
point. You wrote the spec, so you share the blind spots that produced its gaps;
re-reading your own work reliably confirms it. Give the subagent the spec path
and the Phase 1 problem statement, and **nothing else** — no file list, no
summary of what you already checked, no restating the spec's conclusions.
Enumerating what to check tells it what *not* to check, converting an
independent read into a consistency check against your own evidence set. Tell
it to **verify against primary sources** — read the code, query the live
service — not merely flag what looks doubtful. Ask for these seven, in this
order:

| # | What it attacks |
|---|---|
| 1 | **Passes-but-wrong.** Satisfy every acceptance criterion exactly as written — is the Phase 1 problem actually solved? Name any criterion that measures the wrong thing. |
| 2 | **Guessable gaps.** What must an implementer decide that this spec does not decide for them? Each one is a decision deferred to someone who cannot ask you. |
| 3 | **Strawman decisions.** Does each `DR-<n>`'s rejected alternative name something a competent engineer would genuinely have considered — or a placeholder chosen to satisfy the rule? The check above only tests that an alternative *exists*. |
| 4 | **Composition failure.** Phases individually sound but not composing: an ordering hazard, a phase whose `Consumes` is satisfied only by a later phase, a seam that leaves the system unbuildable mid-sequence. |
| 5 | **Intent drift.** Where does the spec contradict what was approved in Phases 1–2, without a Decision Record acknowledging the change? |
| 6 | **The missing top risk.** Not "is the Risks table populated" but "is the single largest risk in it at all?" |
| 7 | **Unverified capability claims.** Any assertion that a library, API, or platform does something — or **lacks** a capability — presented as fact without evidence. An absence claim needs a recorded probe attempt against the authority, or the concrete cost of attempting one; a search that found nothing is not evidence. |

**How to act on it.** Triage each item exactly as Phase 4 triages its own
failures: a **mechanical** gap you fix and re-run; a **decision-shaped** gap goes
to the user as an Open Question, which then blocks the handoff by the rule below.
Items 1, 5, and 6 are almost always decision-shaped — do not resolve them
yourself.

**Bounds.** The adversary advises; it does not rewrite. Do not let it edit the
spec, and do not audit the auditor — one pass, no loop. A subagent that fails or
returns nothing usable is reported as such and does not block the handoff; a
failed advisory check must not consume a finished spec. What it *cannot* do is
be skipped silently: if it did not run, say so when presenting the spec.

### Unanswered questions block the handoff

If Open Questions is non-empty, **the spec is not done and you do not present it
as done.** Stop and put the questions to the user — each one with what it
blocks, your recommendation, and the option set (Ground rule 4). Then loop:
answer lands → fold it into the spec → re-run Phase 4.

**Stated impossibility is an Open Question.** Any sentence asserting a
verification could not be performed — "no undocumented endpoint was probed, and
none could be without live credentials" — blocks the handoff until it names the
concrete cost of attempting it: which request, which credential, which account.
A justification for skipping a check is itself an untested claim, and because it
reads as diligence nobody else will audit it.

**The one escape: an explicit user waiver.** The user may deliberately defer a
question — it depends on something external, or they want to start anyway.
That is their call to make, not yours to assume. When they waive one:

1. Keep it in Open Questions, marked `WAIVED — <date>: <what it blocks>`.
2. Name the phases it blocks in §7: add `Gated on: Q-<n>` to each gated
   phase's block, and prefix that phase's criteria with `[gated: Q-<n>]` so
   the gate also survives the acceptance-criteria-block lift.
3. Report the spec as **partial**, not ready: state which phases are buildable
   now and which are gated on the waived question.

Never waive on the user's behalf, and never let a waiver quietly disappear from
the document — a downstream orchestrator grades an unresolvable ambiguity
`BLOCKED`, and the marked waiver is what makes that visible up front.

### Handoff

Only once Open Questions is empty (or every entry is explicitly waived): tell
the user the spec path and the one command that consumes it — see
[`references/handoff-contract.md`](references/handoff-contract.md).

## Checklist

- [ ] Phase 0: shape, depth, and scope-split chosen and stated
- [ ] Phase 1: problem, users, constraints, metrics — all known
- [ ] Phase 1: claims about existing code carry `path:line`
- [ ] Phase 1: prior decisions scanned; cited integrations confirmed real;
      facts looked up, decisions asked; overloaded terms pinned
- [ ] Phase 2: exec summary + outline + load-bearing decisions presented
- [ ] Phase 2: user explicitly approved (not assumed)
- [ ] Phase 3: file written to disk before drafting prose
- [ ] Phase 3: file manifest written before phases were drawn
- [ ] Phase 3: every major decision has reasoning + rejected alternatives
- [ ] Phase 3: every phase has `Consumes`/`Produces` with exact signatures
- [ ] Phase 3: per-phase `AC-<phase>.<n>` criteria; every FR mapped
- [ ] Phase 4: verification commands run, results stated
- [ ] Phase 4: names and types consistent across phase boundaries
- [ ] Phase 4: every phase has ≥1 negative-path criterion
- [ ] Phase 4b: adversarial read dispatched after the checks passed, its seven
      answers triaged (mechanical → fix and re-run; decision-shaped → Open
      Question), or its absence stated
- [ ] Phase 4: Open Questions empty — or every entry explicitly waived by the
      user, marked in the spec, and reported as partial

## Anti-patterns

- Skipping straight to drafting. Phases 1 and 2 are not optional.
- Treating the Phase 2 gate as a formality. Wait for real approval.
- Gating on the outline alone, hiding the hard calls inside Phase 3.
- Describing existing code from memory instead of reading it.
- Stating a version or capability you did not verify — including a capability
  you claim is *missing* on the strength of a search that came back empty.
- Listing a decision without its rejected alternatives.
- Acceptance criteria that read as goals ("performance is good") instead of
  checks ("p95 under 200 ms on the fixture in `bench/load.py:12`").
- Happy-path-only criteria — every failure branch then ships as the
  implementer's guess.
- Asking the user a question the codebase can answer, or answering a question
  only the user can.
- Phases wired by `Depends on:` alone, with no signatures — the implementer
  invents names and the phases don't compose.
- Signatures without their contract — no error modes, no invariants, no call
  ordering. The types compile; the behaviour is still a guess.
- Drawing phase boundaries before the file manifest exists.
- Deferring a decision into the spec ("add appropriate error handling") instead
  of making it. That is not concision; it is handing the call to someone with
  less context than you.
- Declaring the spec done without running Phase 4 against the file.
- Shipping a spec with live open questions, or answering one yourself to empty
  the section. Both defeat the gate; ask the user.
- Treating a waiver as something you can grant. Only the user waives, and it
  gets marked in the spec.
- Holding the whole spec in the conversation and writing it out at the end.
