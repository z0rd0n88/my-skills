# Improvement Spec Template

Structure every generated `<Project>-spec.md` with these sections, in this order.
Trimmed from `spec-tacular`'s general template — *Users & Context*, *Architecture &
Design*, and *Decision Records* are dropped because self-improvement work has no
distinct persona and rarely a new architecture. **Never leave a section as a
placeholder**: if a section genuinely has no content, the spec should not exist.

The H1 is `# <Project> — Improvement Spec (<isodate>)`.

## 1. Executive Summary

2–4 sentences: what this project must improve this week, and the outcome. Name the
single highest-priority item explicitly. If any item is carried from a prior week,
say so here — a repeat is the most important fact about the week.

## 2. Problem & Goals

- **Problem statement** — the friction or regression this week's findings expose.
- **Goals** — measurable objectives.
- **Non-goals** — explicitly out of scope, to bound the work.
- **Success metrics** — how "done and working" is judged next week. Prefer a metric
  the next wrapup can actually read (a counter, a PR state, a file existing).

## 3. Requirements

Numbered, testable, one per consolidated improvement item. Highest carried-count
first, then priority.

```
FR-<n>: <single testable statement of what must be true when done>
  *(Source: <section path>; <section path>. Carried <N>x.)*
```

Citation rules:

- Cite **every** source section the item was drawn from — an item appearing in all
  three sources gets all three citations. Section paths look like
  `W-o-W → Friction points → Recommendations`, `Issues row 3`, `Next Steps #1`.
- When a source item bundles several unrelated deliverables, **qualify the citation
  with the clause** so it resolves to the right fragment: `Next Steps #7 (feasibility-gate
  clause)`. A bare number pointing at a paragraph that mostly covers another project's
  work is not traceable.
- Omit `Carried Nx` when the item is new this week.
- **Every FR must carry at least one citation.** An FR citing nothing was invented
  rather than extracted — cut it.

## 4. Implementation Plan

Phased, smallest vertical slice first. For each phase: scope, deliverables, and
dependencies. Order by FR priority. Name the concrete file, command, or PR each
phase touches — a plan that names no path is not actionable.

## 5. Risks & Mitigations

| Risk | Likelihood / Impact | Mitigation |
|---|---|---|

Include the risk of *not* doing the work when an item is carried — that is the
observed-failure case, not a hypothetical.

## 6. Testing & Acceptance

Acceptance criteria mapping back to each numbered FR. Every FR gets a row; a
criterion is a check someone can run, not a feeling.

| FR | Acceptance check |
|---|---|

## 7. Open Questions

Anything unresolved that blocks execution.

**The "empty section" bar from `spec-tacular` is deliberately inverted here.** That
template governs an interactive, human-gated spec, where an open question should have
been asked and answered before shipping. This skill is non-interactive by contract —
it cannot ask. An ambiguity the wrapup does not settle **must** land here instead of
being resolved by invention.

So a populated Open Questions section is a correct outcome, not an unfinished one.
The failure mode is the opposite: an ambiguity resolved *silently*, stated in section
3 with a confidence the source does not support. Prefer a question here over a guess
there.

Name what is unresolved **and what it blocks**, so a reader can tell whether it gates
the work or merely qualifies it.
