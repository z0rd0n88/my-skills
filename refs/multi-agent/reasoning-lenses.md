# Reasoning lenses

Shared primitive for reviewing a document's *reasoning* rather than its form. Cited by
`zord-multi-agent-review` (`--lenses`) and `zord-reasoned-review`.

## The failure this prevents

A reviewer roster tuned for code quality critiques how a spec is written, never whether its
reasoning holds. Omissions — the requirement nobody wrote down — are invisible to a
line-by-line read and the most expensive class of spec defect.

## Why the directives are inlined

The obvious implementation is to brief a reviewer to invoke `thinking-skills:thinking-<model>`.
It does not work reliably, and its failures are **silent**:

1. A `Skill(...)` call can return a pointer instead of the thing you asked for. Where a skill
   ships alongside a same-named *command*, the call resolves to the command file — "invoke the
   skill and follow it exactly" plus a flag list — and the skill's body never loads. Nothing
   errors. Observed against `Skill(ClaudesMods:multi-agent-review)` and
   `Skill(ClaudesMods:reasoned-review)` on 2026-08-20, and during the VistaMobileBE#66 loop
   (2026-07-17).
2. `critical-thinking` has no Skill tool at all; its list is `Read, Grep, Glob, Bash`.

Either way the reviewer returns a plausible report having never run its model. Reading the
upstream `SKILL.md` instead avoids that but pins a version path
(`.../thinking-skills/1.0.0/...`) that breaks on upgrade and adds a third-party dependency this
plugin cannot guarantee is installed.

> **Corrected 2026-08-20.** Item 1 previously read *"the Skill tool no-ops inside an inner review
> pass — it returns the skill's summary, not its body"*, cited to "the PR #66 loop". That is
> false: a `lens:first-principles` slot running inside an inner review pass called
> `Skill(thinking-skills:thinking-first-principles)` and got the complete 167-line body. The bare
> `#66` also pointed at the wrong repository. The inlining decision is unaffected — items 1 and 2
> above and the version-path/dependency objection each rule out the Skill-call implementation on
> their own.

So the directives below are inlined as brief text — the brief *is* the instruction, and nothing
remains that can silently not fire.

## Injection contract

The steel-man preamble is injected into **every** reviewer brief (lens slots and code reviewers
alike) whenever lenses are active, under a fixed heading, as its own segment — never inside
`## PROJECT PRELUDE`, which is claimed by content and capped at 16 KB:

```markdown
## REASONING STANCE
<steel-man preamble, verbatim>
```

Each lens slot's directive is injected as its `## YOUR ROLE` body, replacing the agent-definition
lookup that block normally performs.

## The steel-man preamble

> Before reporting any fault, state the strongest case for the design as written: what job is
> each contested choice doing, and what would make it the right call? Only then report faults.
> Do not report a finding that amounts to a preference for a different approach — a finding must
> identify something that is wrong, missing, or ambiguous, not merely different from what you
> would have written.

Steel-manning is a stance, not a slot: a steel-man reviewer produces *defenses*, which have
nothing to report in a severity rubric.

## The lens directives

### `pre-mortem`

> Assume this spec was implemented exactly as written, shipped, and failed. Working backward from
> that failure, enumerate the causes. Concentrate on what the spec does **not** say — missing
> requirements, unhandled states, undefined behaviour at boundaries, absent error paths. An
> omission is a finding; grade it by the severity of the failure it permits.

### `inversion`

> Find implementations that satisfy the literal text of this spec while producing a broken or
> dangerous system. For each, quote the specific language that permits it. Every such path is an
> underspecified requirement — report it as a finding against the sentence that allowed it, not
> as a hypothetical.

### `first-principles`

> For every hard constraint the spec asserts — "must use X", "cannot exceed Y", "always Z" — ask
> whether it is a real constraint or inherited convention. Report as a finding any constraint
> that is unjustified, unsourced, or contradicted elsewhere in the document. Do not report
> constraints that are correct but merely unexplained unless the lack of justification would
> plausibly cause an implementer to violate them.

### `red-team`

Applicable to money, auth, or state-machine specs.

> Adopt an attacker's mindset against the system this spec describes. Enumerate the attack
> surface it creates and report only findings with a concrete, reproducible attack path — state
> the path explicitly. Include paths opened by what the spec leaves to implementer discretion.

### `jobs-to-be-done`

Applicable to product or user-facing specs.

> Identify the job the user is hiring this for and the progress they are trying to make. Report
> as a finding any requirement that does not serve that job, and any part of the job the spec
> leaves unserved. This is the "built the wrong thing" axis.

## Slug set

`pre-mortem`, `inversion`, `first-principles`, `red-team`, `jobs-to-be-done`. Any other value is
a parse-time hard-fail. Cap: 5 lenses per run.

## Dispatch

Lens slots dispatch to `general-purpose` (`Tools: *`). Two reasons: inlined directives need no
special tools, and `general-purpose` sidesteps the `--reviewers` name-resolution trap, where
names validate against agent *filenames* but the Agent tool registers frontmatter `name:`.

The read-only constraint on a lens slot (as on every reviewer, §7's `## HOW TO REVIEW` block) is
**brief-enforced, not tool-enforced**: `general-purpose` carries `Tools: *`, so nothing at the
harness layer stops a lens agent from calling `Edit`/`Write`/`Bash` — the prohibition holds only
because the brief states it and the agent complies.

## Failure modes

- **A lens returns code-quality findings.** The directive did not take. Check that `## YOUR ROLE`
  was replaced rather than appended, and that the agent-definition lookup did not overwrite it.
- **Lens findings dominate the severity budget.** They pass through the existing cross-axis HIGH
  cap unchanged; tune `--high-cap` rather than special-casing lenses.
- **Directives drift from upstream thinking-skills.** Accepted: these models are stable, and this
  file distils their operative core rather than tracking their text.
