# Match intent to invocation

Read this file when choosing options for [the skill](../SKILL.md). These are
instruction invocations in Codex, not shell executables. Replace PR numbers
and paths with the actual target; all file and directory examples assume the
named target exists. The contract checker validates syntax and combinations,
not file existence, remote PR access, model quality, or host agent availability.

For "review PR 42, do not change anything or publish anything":

```text
multi-agent-review-codex pr 42 --no-loop --no-write --no-comment
```

For "fix PR 42 and review the fixes", allow one fix cycle and its post-fix
review. Use an open PR and its clean feature worktree:

```text
multi-agent-review-codex pr 42
```

For authorized unattended fixes with independent refutation, allow at most two
fix cycles. The final post-fix review still runs at the cap:

```text
multi-agent-review-codex pr 42 --yes --adversarial --max-iterations 2 --high-and-up-only
```

For staged changes, or an assumption review of a spec:

```text
multi-agent-review-codex diff --staged --no-write
multi-agent-review-codex spec SPEC.md --lenses pre-mortem,inversion --no-write
```

For a file, directory, or cross-directory review:

```text
multi-agent-review-codex file src/parser.py --no-write
multi-agent-review-codex dir src/auth/ --adversarial --refuters 3 --max-refuters 30 --no-write
multi-agent-review-codex slices src/domain/ src/adapters/ --max-files 80 --max-slices 2 --high-cap off --no-write
```

For an explicit report path, or a quick one-shot review with both optional
adversarial stages disabled (the report-fidelity audit and finding refutation
are separate stages):

```text
multi-agent-review-codex pr 42 --no-loop --write-to docs/reviews/pr-42.md --force --no-comment
multi-agent-review-codex diff --inline --no-adversarial --no-report-audit --no-write
```

The following named agents are examples, not guaranteed capabilities. Use
them only when the host exposes these roles, or replace them with actual
callable names. Quote a CSV argument if it contains spaces:

```text
multi-agent-review-codex diff --reviewers security-reviewer,silent-failure-hunter --synthesizer knowledge-synthesizer --no-write
```

No presets ship with this skill. The following requires a user-created
`.claude/multi-agent-review-modes/security.md` in the target project, or
`modes/security.md` under the installed plugin root. Project presets take
precedence. Store free-form prelude context outside the preset directory:

```text
multi-agent-review-codex pr 42 --no-loop --mode security --prompt-prelude docs/review-context.md --no-comment --no-write
```

Example preset frontmatter, again requiring those agents to exist on the host:

```yaml
---
reviewers:
  - security-reviewer
  - silent-failure-hunter
synthesizer: knowledge-synthesizer
---
```

Compatibility example: `--yes` with `--no-loop` has no effect and does not
authorize fixes or skip required gates:

```text
multi-agent-review-codex pr 42 --no-loop --yes --no-write --no-comment
```

Loop-only controls on a one-shot target, refuter tuners without adversarial
mode, unknown flags or agents, unavailable presets, and unsupported checkpoint
resume all fail before dispatch. See the help table for values and scopes.
