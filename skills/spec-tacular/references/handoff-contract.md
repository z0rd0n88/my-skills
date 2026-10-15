# Handoff Contract

A spec-tacular spec is not only read by humans. It is fed directly to build
orchestrators that parse it. This file states what those consumers require, so
the spec is `READY` on arrival instead of being kicked back.

## Who consumes the spec

| Consumer | Invocation | What it does with the spec |
|---|---|---|
| `baton-runner` | `/baton-runner` with the spec's phase list | Splits it into phases, classifies each `READY` / `THIN` / `BLOCKED`, then runs implement → review → fix per phase |
| `multi-agent-developer` | `multi-agent-developer file <spec-path>` | Feeds the spec verbatim to its explorer and synthesizer; specialist briefs carry it as a compressed TARGET block (code blocks and identifiers preserved verbatim) |
| `code-rinse-repeat` | `code-rinse-repeat <spec-path>` | Builds it, then runs a round-1 conformance pre-pass: every acceptance criterion → PASS / FAIL / AMBIGUOUS with `file:line` evidence |
| `superpowers:writing-plans` | invoked with the spec | Expands each phase into typed, TDD-stepped tasks with literal test code |

## Where this spec stops

The spec states **what must be true**; the plan states **what to type**. So a
spec-tacular phase carries files, interfaces, and acceptance criteria — but not
literal test bodies, implementation snippets, or per-step commit choreography.

That boundary is deliberate. Test code in the spec would duplicate what the TDD
rounds produce, blow the 16 KB inject budget, and freeze implementation detail
before the implementer has seen the codebase. If a phase needs that level of
prescription, hand the finished spec to `superpowers:writing-plans` — it is
built for exactly that expansion, and it expects a spec of this shape as input.

What spec-tacular *does* owe that layer is the part a plan cannot recover on its
own: exact interfaces between phases — signatures *plus* the contract types
can't carry (error modes, invariants, call ordering, import paths) — the file
manifest, and the global constraints. Those are decisions, not detail.

## The three hard requirements

Each phase of the implementation plan needs all three, or `baton-runner`
classifies it `THIN` (criteria missing or weak) or `BLOCKED` (fundamental
ambiguity), and neither can start without a round-trip back to you.

1. **A clear outcome** — one sentence on what is true when the phase is done.
2. **Testable acceptance criteria** — numbered `AC-<phase>.<n>`, each a check
   that returns PASS or FAIL.
3. **Explicit scope and non-goals** — what the phase touches, and what it
   deliberately does not.

## Phase sizing

`baton-runner` right-sizes phases to **≤ ~5 acceptance criteria and ~10 files**
each; anything larger it splits into ordered sub-units, guessing at the seams.
Do the split yourself in the spec — you know where the seams are and it does
not. Prefer small vertical slices over big-bang phases.

## Why criteria live with the phase, not only with the requirements

A traceability matrix keyed to `FR-<n>` tells a reviewer that the spec is
internally consistent. It does not tell a build orchestrator what "done" means
for the unit of work it is about to spawn, because phases and requirements are
not one-to-one: one FR often spans three phases, and one phase often partly
satisfies several FRs.

So put the criteria **in the phase**, and keep the FR mapping as a matrix that
cross-references them. Both consumers are then served: the orchestrator reads
the phase, the reviewer reads the matrix.

## Keep the criteria extractable — the 16 KB budget

Spec injection over the prompt-prelude path is capped at **16 KB**. Not every
consumer is bound by it — `baton-runner` threads the spec by file path, with no
cap — but on the capped paths, over the cap the pipeline prefers **the
acceptance-criteria block alone** over the full spec, and if even that
overflows it fails loud rather than silently truncating criteria.

That makes extractability a requirement, not a formatting preference. Two rules
follow:

- **Stable IDs.** Every criterion is `AC-<phase>.<n>` — one greppable pattern,
  so the block can be lifted mechanically from phases scattered across §7.
- **The traceability matrix carries the criterion text, not just the ID.** The
  canonical extracted unit is the acceptance-criteria block; restating the text
  makes the matrix self-contained too, so it survives extraction if a consumer
  lifts it instead. A matrix of bare IDs pointing back into the body defeats
  this: extract it, and the reviewer receives labels with no content.

A long spec is fine. A long spec whose criteria cannot be lifted out of it is
not.

## Writing a criterion a conformance pass can grade

The conformance pre-pass answers PASS / FAIL / AMBIGUOUS per criterion and cites
`file:line`. `AMBIGUOUS` is the wasted outcome — the grader can return no
verdict on it, so the criterion protects nothing, and in `baton-runner`'s
per-phase review an ungradable criterion surfaces as an issue to chase rather
than a defect found. Avoid it by naming the observable.

| Instead of | Write |
|---|---|
| Error handling is robust | `AC-2.1`: a malformed payload returns HTTP 422 with `{"error": "..."}`; covered by a test in `tests/test_api.py` |
| Performance is acceptable | `AC-3.2`: p95 under 200 ms across 1k requests on the `bench/load.py` fixture |
| The old path is removed | `AC-4.1`: `grep -rn "legacy_sync(" src/` returns no hits and the suite passes |
| Config is documented | `AC-1.3`: every key in `config.schema.json` appears in `README.md` under Configuration |

The pattern: name the artifact, the command, or the observable value. If you
cannot say how someone would check it, it is a goal — move it to the goals
section and write the criterion that proves the goal was met.

Three phrasing rules on top of the pattern:

- **State the precondition.** A criterion has three parts — given <state>,
  when <action>, then <observable>. Naming only action and outcome leaves the
  setup to the grader's imagination, and two graders imagining different
  setups return different verdicts on the same code.
- **At least one negative-path criterion per phase** — what must NOT happen and
  what the caller sees instead. An AC set of happy paths only means every
  failure branch ships as the implementer's guess.
- **Mark `[cross-phase]` criteria** — ones only checkable after a later phase
  lands. The marker is advisory: no current grader parses it, but it tells a
  per-phase reader (human or future grader) that the missing evidence is a
  sequencing artifact, so a FAIL on it is not read as a defect.

## Closing the loop

End the run by telling the user the spec path and the command that consumes it:

```
docs/specs/<slug>.md is ready.
Build it:  /code-rinse-repeat docs/specs/<slug>.md
Or phase-by-phase:  /baton-runner  (phases 1-N from §7)
```

A spec with user-waived open questions is **partial**, never "ready" — report
it as such, naming the gated phases and the buildable subset:

```
docs/specs/<slug>.md is PARTIAL — phases <X>-<Y> gated on Q-<n>.
Build the buildable set:  /baton-runner  (phases 1-<X-1> from §7)
```

If any requirement above is unmet, say so explicitly and name the gap. A spec
that reports its own thinness is useful; one that claims readiness it lacks
burns a build cycle to discover the same thing.
