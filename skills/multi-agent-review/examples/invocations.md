# multi-agent-review — Invocation examples

> Examples file for [`../SKILL.md`](../SKILL.md) (multi-agent-review). Load it when mapping a caller's request onto flags. Per-flag scope and hard-fail rules: [`../references/flags.md`](../references/flags.md).
>
> Named agents in these examples (`penetration-tester`, `python-reviewer`, `code-reviewer`) must be active in the project's `.claude/agents/`. A name found only in `~/.claude/agents-parked/` asks for activation or hard-fails (`../../../refs/multi-agent/agent-catalog-lookup.md` step 2); substitute an active agent otherwise.

## From intent to invocation

Pick the row whose intent matches the request. The first row is the one most often gotten wrong: a bare `pr` target loops, edits, commits, and pushes.

| Caller intent | Invocation | Why |
|---|---|---|
| "Review PR 42 — don't change anything" | `multi-agent-review pr 42 --no-loop` | `pr` loops and mutates by default; `--no-loop` is the read-only report |
| "Review PR 42 and fix what you find" | `multi-agent-review pr 42` | Loops after the confirmation gate |
| "Fix PR 42 unattended (CI, overnight)" | `multi-agent-review pr 42 --yes --adversarial` | `--yes` skips the gate; `--adversarial` refutes findings before they become commits |
| "Check my uncommitted work before I open a PR" | `multi-agent-review diff` | Add `--staged` to review only staged hunks |
| "Security pass over `src/auth/`" | `multi-agent-review dir src/auth/ --reviewers security-reviewer, penetration-tester` | Explicit roster replaces context-aware selection |
| "Stress-test this spec's assumptions" | `multi-agent-review spec SPEC.md --lenses pre-mortem, inversion` | Lenses are one-shot only; a looping `pr` rejects them |
| "Review, but don't leave a file behind" | add `--no-write` | The report is otherwise copied to the git-ignored `.claude/reviews/` |
| "Commit this review to the repo" (rare) | add `--write-to docs/reviews/<name>.md`, then commit it yourself | The default file is git-ignored and the skill never commits a report |
| "Quick read, keep it cheap" | leave refutation off (the default); add `--no-report-audit` | Skips the one-agent fidelity audit too |

## Command examples

```
multi-agent-review pr 42                      # LOOPS by default: one review→fix round (confirmation gate; mutating)
multi-agent-review pr 42 --yes                # loop without the confirmation gate (unattended runs)
multi-agent-review pr 42 --no-loop            # one-shot read-only report
multi-agent-review pr https://github.com/owner/repo/pull/42
multi-agent-review pr 42 --max-iterations 5   # loop, cap at 5 rounds
multi-agent-review pr 42 --high-and-up-only   # loop, auto-defer MEDIUM/LOW
multi-agent-review pr 42 --no-smoke           # loop, skip the live smoke gate
multi-agent-review dir core/
multi-agent-review file SPEC.md
multi-agent-review spec SPEC.md SPEC-UPDATE-001-foo.md PRD.md

# Execution locus (one-shot runs dispatch an orchestrator subagent by default):
multi-agent-review dir core/ --inline           # run in the caller's context; watch the fan-out live

# Adversarial refutation (OFF by default — opt in; the tuners require --adversarial):
multi-agent-review pr 42 --adversarial                    # refute findings before synthesis
multi-agent-review pr 42 --yes --adversarial              # the case it is built for: unattended auto-fix loop
multi-agent-review pr 42 --adversarial --refuters 5       # 5 refuters per CRITICAL/HIGH instead of 3
multi-agent-review dir core/ --adversarial --max-refuters 40  # raise the budget on a finding-rich target
multi-agent-review diff                       # uncommitted working-tree changes (git diff)
multi-agent-review diff --staged              # staged-but-uncommitted changes
multi-agent-review slices src/foo/ src/bar/   # fan-out per slice + cross-slice synth

# Reviewer override (comma-separated; surrounding whitespace around names is trimmed):
multi-agent-review pr 42 --reviewers architect-reviewer, security-reviewer, python-reviewer

# Reasoning lenses (comma-separated; each becomes its own reviewer slot, additive to the roster):
multi-agent-review spec SPEC.md --lenses pre-mortem, inversion
multi-agent-review spec SPEC.md --lenses pre-mortem, inversion, red-team

# Synthesizer override:
multi-agent-review dir core/ --synthesizer code-reviewer

# A pr target's report goes to a PR comment; the file is a git-ignored local copy at
# .claude/reviews/<YYYY-MM-DD>-<derived-slug>.md in the primary checkout.
# Commit a report (rare, explicit), or opt out of the file / the PR comment:
multi-agent-review pr 42 --no-loop --write-to docs/reviews/pr-42-review.md
multi-agent-review dir src/ --no-write
multi-agent-review pr 42 --no-loop --no-comment

# Prompt prelude (project-defined context / skip-list / exclusion notes prepended to every reviewer brief):
multi-agent-review pr 42 --prompt-prelude .claude/multi-agent-review-modes/skip-list.md
```

Example with a mode. No presets ship with the plugin: `--mode <name>` hard-fails unless a preset exists at `.claude/multi-agent-review-modes/<name>.md` or `<plugin-install-root>/modes/<name>.md` (file shape: [`../references/workflow.md`](../references/workflow.md) §5A.1). The `security`, `architecture`, `code`, and `pre-pr` names below are such user-created presets.

```
multi-agent-review pr 42 --mode security
multi-agent-review dir core/ --mode architecture --synthesizer code-reviewer
```

Example with a slice fan-out + project prelude:

```
multi-agent-review slices src/foo/domain/ src/foo/application/ src/foo/adapters/ \
  --mode code --prompt-prelude .claude/multi-agent-review-modes/skip-list.md
```

Example with the uncommitted-diff target (pre-PR sanity check on the working tree):

```
multi-agent-review diff --mode pre-pr
multi-agent-review diff --staged --reviewers security-reviewer, silent-failure-hunter
```
