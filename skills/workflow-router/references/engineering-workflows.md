# Process lane: the eleven engineering workflows

Each workflow is a shape of work with a gate that must not be skipped. Read the section for the
workflow the router picked, follow its steps in order, and stop at its gate until it is met.
Each step list is a checklist: for work that runs past one reply, copy the bold step names and
the gate line into your reply as `- [ ]` lines, and tick each one when it is done.
"Carry out with" names skills in this repo that do the step; a skill that is not installed is
skipped, and the steps here still apply.

## Contents

Building: 1. Feature Implementation · 2. Bug Fix · 3. Spike / Prototype · 4. TDD-Ralph
Changing: 5. Refactor · 6. Migration · 7. Dependency Upgrade
Understanding: 8. Debugging · 9. Onboarding / Code Archaeology
Operating and collaborating: 10. Incident Response · 11. Code Review (as reviewer)
Then: 12. Composing workflows · 13. Anti-patterns · 14. Least privilege per step · 15. Heuristics

---

## 1. Feature Implementation

Adds new, intended behaviour. The heaviest workflow, and the wrong default for everything else.

**Use when** the change adds capability that did not exist and is large enough to justify a plan.
**Not when** fixing broken behaviour (Bug Fix), answering a viability question (Spike), changing
structure only (Refactor), or production is down (Incident Response).

**Gate: the plan is approved before any code is written.**

- [ ] 1. **Research and reuse.** Search existing code and proven libraries first, then verify against
   vendor docs and package registries. Adopt or port before inventing.
- [ ] 2. **Plan.** Requirements, design, a task list, dependencies and risks, split into phases. A
   person approves it.
- [ ] 3. **TDD, one cycle per task.** Failing test that states the intended behaviour, minimum code to
   pass, clean up while green.
- [ ] 4. **Review.** A separate reviewer. Fix every critical and high finding and the medium ones
   where possible, then review again.
- [ ] 5. **Commit and ship.** Conventional commit, CI green, branch up to date, PR with a summary and
   a test plan.

**Mistakes:** skipping research; coding before the plan is approved; tests written after the
code, which only confirm what the code does; treating medium findings as optional.

**Carry out with:** `addyosmani-spec-driven-development`, `addyosmani-planning-and-task-breakdown`,
`addyosmani-test-driven-development`, `addyosmani-incremental-implementation`,
`addyosmani-code-review-and-quality` (`dw-review` instead only when the user asks for a
multi-agent review), `addyosmani-git-workflow-and-versioning`.

## 2. Bug Fix

Repairs specific broken behaviour whose intended behaviour is known. The goal is to converge on
existing intent, not to discover new intent.

**Use when** there is a reported defect or failing test, the right behaviour is known, and the
fix is bounded.
**Not when** you cannot reproduce it (Debugging), it is really a missing feature (Feature), the
fix needs structural change (a Refactor PR, then a Bug Fix PR), or production is affected now
(Incident Response first).

**Gate: a reliable reproduction, then a failing test, before the fix.**

- [ ] 1. **Reproduce** with a script, test or step list that triggers it every time. No reproduction
   means you have a hypothesis, not a bug: switch to Debugging.
- [ ] 2. **Locate** with `git bisect`, binary search or instrumented logging. Don't guess from which
   file feels related.
- [ ] 3. **Root cause.** Write down the symptom, the immediate cause and the underlying cause. Fix the
   underlying cause when feasible.
- [ ] 4. **Failing test first.** A test that fails because of the bug. It stays as regression cover.
- [ ] 5. **Minimal fix.** No adjacent refactoring, renaming or style changes in this PR.
- [ ] 6. **Verify, then look for twins.** The test passes, related tests pass, and the same pattern
   elsewhere is fixed or covered in separate PRs.

| Symptom | Possible underlying cause |
|---|---|
| Null error at a line | Upstream returns null when it shouldn't; missing validation; race between init and use |
| Wrong total | Off-by-one; rounding direction; rule applied to the wrong subset; stale cache |
| Slow page | N+1 query; missing index; synchronous I/O on a hot path; cold cache |
| Intermittent test failure | Order dependence; time dependence; shared mutable state; flaky external dependency |

**Mistakes:** fixing the symptom (a null check at the crash site); fixing without a
reproduction; mixing the fix with refactoring; no regression test; not searching for twins.

**Carry out with:** `addyosmani-debugging-and-error-recovery`, `addyosmani-test-driven-development`.

## 3. Spike / Prototype

Answers one technical question with throwaway code. The product is a decision and its evidence.

**Use when** you can't plan with confidence, a claim needs testing ("will this handle 10k
req/s?"), or two approaches can only be separated by trying them.
**Not when** you already know how to build it, the docs answer the question, or production
quality is expected at the end (that is Feature work).

**Gate: a time box, and the code is thrown away.**

- [ ] 1. **Write the question:** one sentence, falsifiable.
- [ ] 2. **Time-box.** Four hours is a long spike. More than a day means the question is too broad.
- [ ] 3. **Minimum code.** No tests, no config, hardcoded values, marked as a prototype.
- [ ] 4. **Run it and record** numbers, logs and screenshots.
- [ ] 5. **Write the answer:** question, answer, evidence, what it means for the design.
- [ ] 6. **Delete the branch.** Keep the document.

**Mistakes:** productionising the spike because "it works"; keeping the code "just in case".
Either delete it within two days or rebuild it properly as a Feature.

**Carry out with:** `mattpocock-prototype`; `mattpocock-research` when the docs can answer it.

## 4. TDD-Ralph (autonomous loop)

Builds a large feature through an unattended loop where tests are the gate. Each iteration
starts with a fresh context, reads the prompt, `AGENTS.md` and `specs/*`, takes one task from
`IMPLEMENTATION_PLAN.md`, implements it, runs the tests, commits if green and exits. A shell
loop restarts it. The person writes specs and tests; the loop writes code.

**Use when** the scope splits into many small spec files, failing tests can state intent before
implementation, the tests are fast and deterministic, and a sandbox is available.
**Not when** there is no sandbox, tests are slow or flaky, the desired behaviour is still
unknown (Spike), the change is one file, or the spec is too loose to test.

**Gate: a sandbox, and failing tests written by a person, before the loop runs.** The loop needs
permission prompts turned off, so the sandbox is the only security boundary. Never run it on a
host with credentials, SSH keys or browser sessions. Ask the user before starting one.

- [ ] 1. **Define requirements** in an ordinary conversation: jobs to be done, then topics, then one
   spec file per topic. A topic that needs "and" to describe is two topics.
- [ ] 2. **Write the failing tests by hand.** If the loop writes the tests it then satisfies, that
   proves self-consistency, not correctness.
- [ ] 3. **Plan loop.** Compare `specs/*` with the code and write a prioritised
   `IMPLEMENTATION_PLAN.md`. No code. One or two iterations.
- [ ] 4. **Build loop.** Per iteration: orient, read the plan, pick one task, check the code for an
   existing implementation, implement, test, commit and update the plan if green, exit.
- [ ] 5. **Tune from outside.** When it drifts, fix the prompt, `AGENTS.md` or a utility in the source
   so the next iteration picks it up. Stop it, reset, or regenerate the plan if the direction is wrong.

| File | Owner | Purpose |
|---|---|---|
| `PROMPT_plan.md`, `PROMPT_build.md` | Person | The loop's only instructions, re-read every iteration; keep them short |
| `AGENTS.md` | Person; the loop appends notes | Build and test commands, conventions, lessons |
| `specs/*.md` | Person | One file per topic |
| `IMPLEMENTATION_PLAN.md` | Loop | Shared state between iterations |
| Tests | Person writes failing; loop refines to pass | The gate |
| Source | Loop | The output |

**Mistakes:** letting the loop write the failing tests; no sandbox; nudging mid-iteration;
long prompts, paid for on every iteration; skipping the plan loop; trusting a green run without
reading the test diff (it can hardcode a value, stub a function or mark a test as expected-fail).

## 5. Refactor

Improves structure with no change in observable behaviour.

**Use when** the structure is slowing feature work, duplication has a clear unifying shape, or a
coming change doesn't fit the current shape.
**Not when** the area has no test cover (add tests first), you want to fix a bug on the way
(separate PR), or you can't say what is better about the new shape.

**Gate: tests cover the area before any structural change.**

- [ ] 1. **Lock down behaviour.** Run the suite. Where cover is thin, write characterisation tests of
   what the code does today, bugs included.
- [ ] 2. **Name one transform:** "extract `validatePayment` from `processOrder`", not "clean up
   `processOrder`".
- [ ] 3. **Apply it mechanically,** with refactoring tools where they exist, and nothing else.
- [ ] 4. **Verify** every test still passes with the same output and side effects. If not, revert and
   go smaller.
- [ ] 5. **Commit.** One transform per commit, named in the message.
- [ ] 6. **Repeat or stop** and open the PR.

Transforms worth knowing: Extract Method (a comment explains a block), Inline Method (the
indirection adds nothing), Rename (the name misleads), Introduce Parameter Object (the same
parameters travel together), Replace Conditional with Polymorphism (the same type switch in
several places), Move Method (it uses another module's data more than its own), Split Phase
(parse-then-process in one function).

**Mistakes:** refactoring without tests; mixing in behaviour changes; one big-bang commit;
refactoring to avoid starting the feature.

**Carry out with:** `addyosmani-code-simplification`.

## 6. Migration

Replaces pattern X with pattern Y across the codebase. Mechanical at most call sites, with edge
cases, and not finished until the old pattern is gone.

**Use when** swapping one library for another, standardising where two patterns co-exist, or
fixing up a version's breaking change across many files. That last case starts as a Dependency
Upgrade and is handed off here for the hop that needs it.
**Not when** it is one version bump with no API change (Dependency Upgrade), a change inside one
module (Refactor), or a replacement in one place (just do it).

**Gate: an inventory before any estimate.**

- [ ] 1. **Inventory.** Every call site, by text search or syntax-aware search, counted and grouped by
   shape. Estimates from memory undercount several times over.
- [ ] 2. **Pilot.** Migrate the one or two simplest sites by hand and write down the before and after.
- [ ] 3. **Automate the bulk** with a codemod for the dominant pattern, then run the tests.
- [ ] 4. **Hand-fix the edges,** the 10–30% the codemod misses, one PR per cluster.
- [ ] 5. **Stateful systems go in phases,** one deploy each, each with a rollback, none skipped or merged:
   write old and new, read old (back-fill) → write both, read new with fallback to old → write new only.
- [ ] 6. **Remove the old path** and add a lint rule or CI check that stops it coming back.

**Mistakes:** no inventory; no pilot; stopping at "95% migrated"; one unreviewable PR; mixing
in refactoring.

**Carry out with:** `addyosmani-deprecation-and-migration`. For many call sites, the Migrate
combination in [agent-orchestration.md](agent-orchestration.md).

## 7. Dependency Upgrade

Moves one dependency to a newer version. Small surface, but failures can hide in transitive
behaviour.

**Use when** a new version has wanted fixes, features or security patches, or for routine upkeep.
**Not when** replacing the dependency (Migration) or responding to a live incident.

**Gate: the full changelog is read, and majors are taken one at a time.**

- [ ] 1. **Read the changelog** for every version between current and target: breaking changes,
   deprecations that became errors, quiet behaviour changes, advisories.
- [ ] 2. **Plan the hops:** v2 → v3 → v4 → v5, not v2 → v5.
- [ ] 3. **One hop at a time:** bump, install, test, fix, commit with both versions in the message.
- [ ] 4. **Test and exercise by hand** the paths that use the dependency. Defaults that changed
   (sort stability, time zones, timeouts) rarely have tests.
- [ ] 5. **Fix** import and type errors first, then test failures, then runtime behaviour. When one
   hop's breaking change touches many call sites, run that fix-up as a Migration, then come back.
- [ ] 6. **Check transitive impact** with integration tests, smoke tests or a staging deploy.

| Case | Care needed |
|---|---|
| Major | Plan hops, read everything, expect code changes |
| Minor | Should be safe; run the tests; watch for behaviour tweaks |
| Patch or security patch | Usually safe; a faster path is fine; confirm the version really fixes the advisory |
| End-of-life dependency | Treat as a Migration |

**Mistakes:** jumping majors; skimming the changelog; trusting tests alone; bundling several
dependencies in one PR. Stop for the user at each major-version boundary.

**Carry out with:** `addyosmani-source-driven-development` for the changelog and docs.

## 8. Debugging

Builds an accurate model of what the system is doing when your current model predicts something
else. Bug Fix is for when you know what is wrong; this is for when you don't.

**Use when** behaviour can't be explained, failures are intermittent or environment-dependent,
a fix didn't fix it, or performance is bad for no visible reason.
**Not when** you know the cause (Bug Fix), production is degraded now (Incident Response), or
you haven't tried to reproduce yet (do that first).

**Gate: reproduce before theorising, and keep a written hypothesis log.**

Loop: observe → hypothesise → predict → test → update, until the model matches reality.

- [ ] 1. **Record what you see** exactly: the error text, the steps, the values.
- [ ] 2. **State what you expected** and why. The gap is where the bug lives.
- [ ] 3. **Form a falsifiable hypothesis.** List two or three before testing any.
- [ ] 4. **Predict** what you would see if it were true.
- [ ] 5. **Run the smallest experiment,** one change at a time.
- [ ] 6. **Update:** confirmed, refuted or refined.
- [ ] 7. **Log** each hypothesis, its test and its result.

```
Bug: <one line>            Reproduction: <exact steps>
Expected: <…>              Observed: <verbatim>
H1: <hypothesis> · Predicted: <…> · Test: <…> · Result: REFUTED — <why>
H2: <hypothesis> · Predicted: <…> · Test: <…> · Result: CONFIRMED — <evidence>
Conclusion: <what is now believed>   Next: <Bug Fix | wider investigation | ticket>
```

**Mistakes:** trying fixes before understanding; no log, so ruled-out ideas get re-tested;
anchoring on the first plausible explanation; trusting the code over logs and traces. When they
disagree, the data is right. Hand off to Bug Fix with the log attached.

**Carry out with:** `addyosmani-debugging-and-error-recovery`.

## 9. Onboarding / Code Archaeology

Builds a working understanding of an unfamiliar codebase. The output is a mental model and a map.

**Use when** joining, returning after months away, inheriting a system, or shipping in another
team's code.
**Not when** you need one specific change (read just enough for it) or a ticket is due tomorrow
(learn while building).

**Gate: one small real contribution, early.**

- [ ] 1. **Entry points:** main files, routes, workers, cron jobs, CLI commands. List them.
- [ ] 2. **One canonical trace:** follow the simplest user operation end to end without branching off.
- [ ] 3. **Data model:** the 5–15 core entities, how they relate and where they live.
- [ ] 4. **Seams:** every place the system talks to another. Most incidents start there.
- [ ] 5. **Read tests before docs.** Tests say what the code does today; docs say what someone hoped.
- [ ] 6. **Make one small contribution** to learn the dev loop, the pipeline and the review path.

Report: entry points with `file:line`, an architecture sketch, the trace, the data model, the
seams, and candidates for a first PR.

**Mistakes:** trying to read every file; asking for an overview before reading anything;
putting off the first PR.

**Carry out with:** `zoom-out`. For a large codebase, the Understand combination in
[agent-orchestration.md](agent-orchestration.md).

## 10. Incident Response

Restores service when production is broken now. The one workflow where you act before you
understand.

**Use when** production is degraded or down, customers are or soon will be affected, data
integrity is at risk, or there is a security incident.
**Not when** the bug is real but harming no one (Bug Fix), it can be investigated at leisure
(Debugging), or it is planned downtime.

**Gate: mitigate before diagnosing, and always write the postmortem.**

- [ ] 1. **Stop the bleeding:** revert the last deploy, turn off the flag, rate-limit.
- [ ] 2. **Triage** the severity and who owns it. Name one incident commander when several people respond.
- [ ] 3. **Communicate** on the status page and internal channel. "We're investigating" is a fine first update.
- [ ] 4. **Mitigate properly:** fail over, scale up, route around, restore. The goal is service, not a fix.
- [ ] 5. **Stabilise, then stand down.** No root-cause work at 3 a.m.
- [ ] 6. **Root cause later,** rested, using Debugging.
- [ ] 7. **Postmortem:** timeline, impact, contributing factors, what went well and badly, and action
   items that each have an owner and a date.

| Mitigation, during | Fix, after |
|---|---|
| Revert the deploy | Remove the bad change properly, with a regression test |
| Turn off the feature flag | Fix the code path, then re-enable gradually |
| Fail over to a replica | Repair the primary and find out why it failed |
| Scale up | Profile the hot path and right-size |
| Restore from backup | Fix whatever caused the data loss |
| Block a bad client at the edge | Add rate limiting or abuse detection upstream |

**Mistakes:** diagnosing while customers are down; rushed code fixes mid-incident; nobody
coordinating; no postmortem; action items with no owner.

As an agent: propose the mitigation and wait for the person's go-ahead before any revert, flag
change, failover or restore. Those act on production.

## 11. Code Review (as reviewer)

Judges someone else's change for correctness, safety and fit.

**Use when** you are asked to review, own the code being changed, or have expertise in the area.
**Not when** you lack the context (say so and decline; don't rubber-stamp), or it is your own
change (that is the review step of Feature Implementation).

**Gate: understand the intent before commenting, and triage every comment.**

- [ ] 1. **Intent.** Read the description. If the purpose is unclear, that is the first and only comment.
- [ ] 2. **Pass 1, shape.** Is the approach sound, and is the PR the right size? No style comments yet.
- [ ] 3. **Pass 2, correctness.** Edge cases, empty and maximum values, concurrency, failure and
   timeout paths, input validation, authorisation, secrets.
- [ ] 4. **Pass 3, maintainability.** Names, tests, docs, where the abstractions sit.
- [ ] 5. **Triage:** `[blocking]`, `[non-blocking]` or `[nit]` on every comment.

**Mistakes:** reviewing without the intent; untriaged or all-blocking comments; style nits a
linter should catch; approving without reading; a hostile tone.

**Carry out with:** `addyosmani-code-review-and-quality` by default. Use another only on its
condition: `pr-review-router` when the PR is in a repo it covers; `dw-review` when the user asks
for a multi-agent review; `zord-multi-agent-review` when they ask for a review that loops
review → fix until clean. Post comments only after the user confirms.

---

## 12. Composing workflows

1. **Workflows nest, but one is primary.** A small refactor inside a feature is a sub-step: put
   it in the plan and in its own commit, and stay in Feature. When the sub-task starts to
   dominate, ship what you have and start the other workflow fresh.
2. **Hand-offs are written.** The conclusion of one workflow is the input to the next.
3. **Keep every gate** of every workflow in play, even when it feels redundant.

Usual hand-offs: Incident Response → Debugging → Bug Fix. Onboarding → Spike → Feature
Implementation, with Refactor as a sub-step or TDD-Ralph as the large-scope variant, then Code
Review. Dependency Upgrade → Migration when the new version has no drop-in equivalent or a
breaking change touches many files.

## 13. Anti-patterns

- **One command that does everything.** Research, plan, code, review and ship in one run loses
  every gate, and the first wrong assumption runs through all of it.
- **Feature Implementation for everything.** A typo needs no plan; a debugging session should
  not end in a PR.
- **The unsupervised agent.** Full tool access and no checkpoints produces plausible, wrong output.
- **Safety by prompt only.** "Do not write files" in prose fails under long contexts. Back it
  with a tool allowlist, which fails closed.
- **The missing postmortem,** **the spike that never dies,** **the review where everything blocks.**

## 14. Least privilege per step

When a workflow is turned into commands or agents, make it one command per step with the
smallest tool set for that step, so each gate is structural.

| Step | May read | May change |
|---|---|---|
| Research, plan, review, debug, onboard, postmortem | Files, docs, search, logs | Nothing but its own output document |
| TDD, bug fix, refactor | Files | Source, test runs, commits |
| Ship | Files, diff | Commit, push, open the PR |
| Spike | Files, sandboxed runs | A scratch directory only; no commits |
| Ralph loop | Prompt, specs, plan, tests, source | Source, tests, a commit per iteration; sandbox only |
| Migrate, upgrade | Files, registries, changelogs | Source, lockfile, codemod runs, commits |
| Review a PR | PR and files | Post comments, after confirmation |

## 15. Heuristics

- If you can't reproduce it, you can't fix it.
- The first plausible explanation is usually wrong; list at least three.
- The bug rarely lives where the symptom appears.
- Tests describe current behaviour; docs describe past hopes.
- Mitigate before you diagnose.
- A migration isn't done until the old path is deleted.
- Spike code that survives is technical debt.
- Refactors and behaviour changes never share a commit.
- An action item without an owner is not an action item.
