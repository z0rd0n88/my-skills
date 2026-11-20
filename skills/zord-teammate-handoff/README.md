# zord-teammate-handoff

Packages a job as a runbook that a teammate's plain Claude Code executes unattended on their own
machine, then critiques the runbook until an independent reviewer finds nothing. Generalised from
the 2026-11-04 job that landed the Vista sign-in stack (VistaMarkets/Flutter-mobile-app PRs 73 to
80): eight critique rounds, scores 15/22 to 22/22, every defect they caught is now a rule.

## Layout

| File | Role |
|---|---|
| `skills/zord-teammate-handoff/SKILL.md` | The eleven phases, each with its verify. Control flow only. |
| `skills/zord-teammate-handoff/references/runbook-rules.md` | The rules, each with the defect it prevents. The critique cites them by id; the check script enforces the mechanical ones. |
| `skills/zord-teammate-handoff/references/runbook-template.md` | The section shape with the generic commands and the rule-bearing sentences already in place. `{{slots}}` are filled by the author; `N`, `PR`, `BRANCH`, `NEXT_PR` and `<...>` fields by the runner. |
| `skills/zord-teammate-handoff/references/critique-prompt.md` | The self-contained prompt for the independent reviewer: 22 binary criteria, claim ledger, relaunch walk, literal-executor read, failure-scenario list, log location. |
| `skills/zord-teammate-handoff/scripts/check-runbook.sh` | The structural verifier: `bash -n` on every block, every placeholder defined, an Expected after every command, consumed files produced, paths present on a `--ref` branch, live probes green, then the mechanical greps. |

## Invocation

User-invoked (`disable-model-invocation: true`). "Hand this off" already routes to
`session-switcher` and `orca-cli`, so a model-facing description would collide; type
`/zord-teammate-handoff <source>`.

Skills and agents the phases dispatch, all Claude Code: `AskUserQuestion` (intake),
`general-purpose` subagents (critique, ledger rebuild), the `finding-fixer` skill (first fix pass,
user-scope install; the skill says what to do when it is absent). No Codex tooling anywhere.

## Check script

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/zord-teammate-handoff/scripts/check-runbook.sh" <runbook.md> \
  --repo <checkout> --ref origin/<top piece branch>,origin/<branch a pointer names> --prefix <paths prefix> \
  --probes <probes.sh> --created <ledger file>
```

Measured on the reference job from a VistaMarkets/Flutter-mobile-app checkout, with
`--repo . --ref origin/feat/41-vista-sign-in-8-oauth --prefix vista/app`: the first draft (commit
44f6817) prints 17 FAIL lines; the finished runbook on `main`, with `--created .landing-ledger.md`
added, prints 3: two mutating blocks with no Expected (D4, lines 300 and 384; rule D4 came later),
the approvals probe's `\"APPROVED\"` escape, which gh 2.101.0 refuses to parse (A3, line 322), and
the platform markers it predates (D8). `--help` prints the options.

## Versions

- **v1 (this)**: Mac teammate. Platform-only steps and their setup checks sit inside
  `<!-- platform: <os> -->` markers (rule D8), in both directions: a Mac-only smoke, or a
  Linux-only gate script with its Mac form beside it. SKILL.md's commands take values as `<...>`
  fields the runner shell-quotes; Z0rd0nZords AGENTS.md ("Don't write shell in prose") asks for
  a script that takes them as `argv`, not built in v1.
- **v2 (not built)**: Linux executor. The switch lives at those markers: skip the Mac-only step
  and record the waiver in the piece's review comment, or substitute the Linux equivalent (an
  Android emulator smoke for an iOS simulator smoke). Everything else in the reference job (gate,
  guard, tests, `gh`, `git`) already ran on Linux.
- **Windows**: out of scope; the same markers are its seam.

## Testing

Per `superpowers:writing-skills`, on VistaMarkets/VistaMobileBE PRs 1120 to 1122: one baseline
subagent wrote a runbook without the skill, one followed Phases 2 and 3 with the references.
Check script as of commit 0517b2c: baseline 14 FAIL lines, with-skill `CHECK: PASS`. Rule misses the script cannot see,
baseline only: author self-approval downgraded to a comment instead of a stop (C6), only
CRITICAL and HIGH findings fixed, long builds detached with `&` and polled (A2). The with-skill
run surfaced five reference gaps, all folded in: the jq escape (A3), the linked-worktree merge
case (A4), the repo's own Claude hooks shaping the loop (A12), platform markers in both
directions (D8), and the PR stacked above the job's last piece (template step 8). One rep each,
below the five the skill's micro-test guidance asks for.

Not yet run end to end (intake, critique loop, an unattended run of the produced runbook, a
relaunch mid-run): z0rd0n88/Z0rd0nZords issue 213 has the sandbox and the test plan.
