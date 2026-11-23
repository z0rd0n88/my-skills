---
name: finding-fixer
description: Use whenever review findings need fixing, especially about code written this session, or when a brief or plan names finding-fixer for the fix step, findings need SUPPORTED or REFUTED verdicts between review rounds, or a hand-run or inline reviewer fan-out returned a findings list. Read-only agents adjudicate each finding before one writer applies supported edits.
---

# finding-fixer

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop. Do not run any other step in this
skill.

> **⚠️ Writes to your working tree and spends 2 to 5 agents.** The apply phase
> edits files in place and may add a new test file. Run it on a feature branch
> with a clean tree so a bad run is one `git checkout` plus `git clean -fd` away.

Turns a list of review findings into applied edits without letting a wrong finding through.
Read-only agents rule on each finding against the real sources first, then one writer applies
only what survived, proving each behaviour change with a test that fails before the edit, or,
for instruction text, a ledger re-checked after it.

| Option | Values | Default | Effect |
|---|---|---|---|
| findings | the review output, pasted or a file path | required | What gets adjudicated. Findings need a stable id each (`F1`, `F2`, ...) so verdicts can be matched back. |

## When this fires

A review just handed back findings and someone wants them fixed. That is the trigger, whatever
produced them.

Always adjudicate findings about code you wrote in this session, including small mechanical
fixes. Independent adjudication checks the assumptions that produced the code before they
shape its repair.

For code you did not write in this session, fix directly only when either of these holds:

- Two or three findings, all mechanical, all in one file. Four agents to fix a typo is waste.
- You did the reviewing yourself and checked the deciding sources for each finding.

Reach for it when the reviewer did not have the whole picture: it read a diff, a spec, or a PR,
and its findings assert things about code it never opened. That gap is what this skill closes.

## Why it is shaped this way

Five decisions carry the whole thing. If you change one, you have a different and worse workflow.

**Adjudicate before writing.** A confident severity is not evidence. Reviewers reason from what
they were shown and routinely miss the mechanism that already makes the code safe. The
adjudicators' job is to go find that mechanism, and a finding that dies here costs one read-only
agent instead of a bad edit plus the session that undoes it.

**"Real but decided elsewhere" is a first-class verdict.** The most expensive failure is a valid
finding whose fix quietly overrules a decision someone already made. Without a verdict for it,
an agent must either call the finding invalid, which is dishonest, or overrule the decision,
which is worse. Give it the third door: annotate the risk, name who owns it, leave the decision
alone.

**Adjudicators propose byte-exact edits but never write.** They read the file, so they are the
ones who can copy the exact `current` text out of it. Handing that across as an exact string the
writer matches on means a stale or hallucinated anchor fails loudly instead of landing in the
wrong place.

**One writer, serially.** Three agents editing the same file concurrently corrupt it, and the
last one to write wins by accident. The writer also owns the re-verification, so there is exactly
one place that knows the final state of the tree.

**Behaviour changes are proved before they are made.** An edit that changes what the code does
gets a test that fails first: the adjudicator names it, the writer runs it and quotes the failure.
Without that, a fix is a claim — the suite was green before the edit and is green after, which is
exactly what a no-op looks like. Weak-test findings invert the move: apply the mutation the test
should catch, show it passing anyway, then show the replacement failing on it. Prose and
annotation edits get no test, and inventing one for them costs a run and proves nothing. A config
value a code path reads is a behaviour change and gets a test like any other.

Instruction text an agent obeys is not prose here: rules files, `CLAUDE.md`/`AGENTS.md`,
`SKILL.md`, agent definitions and prompts are behaviour that no test reads, so a green `verify`
proves nothing about them. Their proof is a **ledger**: every instruction, qualifier, exception
and named entity in the text the edit replaces, each marked preserved, changed or dropped, plus
every instruction the replacement adds, marked added, re-checked against the text as applied. Scope words ("when", "only when", "already", "and
others") are what a rewording drops without anyone noticing.

## Step 1. Collect four inputs

These are the four keys of the `args` object, in the order the script reads them. The workflow
validates all four and refuses to start on any that is missing, blank or the wrong shape, so a
mistake here costs a relaunch rather than a bad edit.

| Input | What it is | Why it matters |
|---|---|---|
| `cwd` | absolute path of the worktree every agent must stay inside | Interpolated into every prompt. Wrong or absent, and the writer resolves paths against the wrong tree |
| `houseRules` | the project invariants an edit must not break | Without them an agent "improves" a deliberate constraint |
| `verify` | one shell command that proves nothing broke **and that a correct input still passes** | A test command, a linter, a build — but one that drives at least one valid input through the changed path. Re-running the existing suite proves the new gates exist, not that anything can get past them. Not "check it looks right". When every finding is about instruction text, `verify` covers none of the changed paths; run the edited skill's evals as well if it has any (`skill-creator` runs `evals/evals.json`) |
| `groups` | findings batched by what decides them, each with `label`, `findings` and `sources` | Drives how many adjudicators run |

The findings text is not a top-level input. It lives on each group as `groups[].findings`, which
is where the adjudicator reads it from. Give every finding a stable id there (`F1`, `F2`, ...), the
repo-wide format in `refs/severity-scale.md`, so
verdicts can be matched back and reported. A review that used older labels
(`C1`/`H1`, Blocker/Should-fix/Minor, Nit) is renumbered `F1`... and its levels mapped with the
table in that file before grouping; keep each finding's reported level as written (CRITICAL /
HIGH / MEDIUM / LOW) and print it with its action in the final report.

`houseRules` is the input people skip, and it is the one that prevents the worst edits. Pull it
from `CLAUDE.md`, the ADRs, the style rules in the file header. State the decided things as
decided. A real example:

```
1. Specs under docs/specs/ named in an accepted ADR are decided. Reproduce them, never improve
   them. A finding asking to change decided behaviour gets an annotation naming the risk and its
   owner, not a redesign.
2. Every financial value on the wire is a JSON string, never a JSON number.
3. No em dashes, no curly quotes, sentence-case headings.
4. Every object schema is closed. Adding a required property means updating every example of
   that schema in both files, or the contract self-invalidates.
```

Rule 4 in that list was written after a run added a required field and silently broke the
examples. That is the shape of a good house rule: a real failure, stated as a constraint.

When the findings are about instruction files, the rest of the always-loaded instructions (the
root `CLAUDE.md`/`AGENTS.md` and every rules file without `paths:` frontmatter) are what an edit
must not contradict. Name them in each group's `sources`, and put only the specific lines that
could conflict into `houseRules`, which every agent prompt repeats, plus by default: rewrite the
wrong sentence in place, add no net sentences, and state each rule once and point to it elsewhere. Add one rule: a line that
reached `origin/<default>` in the last 30 days through a commit outside the change under review
is a decision, so a finding that removes it is `real-but-decided-elsewhere` with no edit unless
the user says otherwise. An always-loaded file is not annotated; every session would pay for the
annotation. Check age with `git blame --since=30.days`, after deepening a shallow clone
(`git fetch --shallow-since=60.days origin <default>`), or every line looks new.

## Step 2. Group the findings

Batch by **which sources settle the finding**, not one agent per finding and not by severity.
Findings that are settled by the same ADR or the same module belong in one prompt, because the
agent reads those sources once and rules on all of them with that context loaded.

Two to four groups. Past that you are paying for agents that read the same files.

**Severity is the wrong axis for scoping too, not just for batching.** A severity table is a
merge filter — it says what blocks a merge, not what is worth fixing. Adjudicating a MEDIUM
costs exactly what adjudicating a CRITICAL costs, so offering "criticals and highs only"
under-scopes the pass and the user comes back for the rest. Default the offer to every finding
the review produced, and let the user cut it down.

Every adjudicator brief carries one more question: **what correct input does this fix now
reject?** Every finding asks whether bad input can slip through; none asks what the new gate
costs. A tool that survived real use can be hardened into one that refuses the very manifests
it used to accept, and the run still reports every finding closed. The verdict names the valid
input the fix rejects, or states there is none. Ask the second half too — **does any document
tell a human how to produce this input?** A gate tightened without its producing procedure
means every correctly-followed run of that procedure now fails. For instruction files the same
question reads: **what legitimate behaviour does the new wording forbid or require, and which
other always-loaded instruction does it now contradict?**

And one more: **how would a test prove this?** The adjudicator is the one that read the file, so
it is the one that can name the test that fails before the edit and passes after — or, for a weak
test, the mutation the current one survives. It never runs that test; naming it is the whole job,
and the writer executes what it named. A finding that changes no executable behaviour answers
"n/a", and a named test that turns out to pass on its first run stops the fix rather than hiding
in it. An edit to instruction text answers with a `ledger:` instead, which the writer re-checks
against the applied text and reverts on any mismatch. A verdict that changes both code and
instruction text names the test, then appends the `ledger:`.

Each group needs a `label` (`adjudicate:<what>`), the `findings` text verbatim, and `sources`:
the specific files, ADRs and symbols to read before ruling. Be concrete. "Read the relevant
code" produces a shallow verdict; naming the ADR and the class produces evidence.

## Step 3. Run the workflow

Copy the template out of the skill so the run script is editable, then fill in `args`:

```bash
cp "<directory of the SKILL.md you read>/assets/workflow-template.js" \
   "<scratchpad>/finding-fixer-run.js"
```

Call `Workflow` with `scriptPath` pointing at that copy and `args` carrying the four inputs:

```json
{
  "cwd": "/abs/path/to/worktree",
  "houseRules": "1. ...\n2. ...",
  "verify": "cd /abs/path && ./run-tests.sh",
  "groups": [
    {
      "label": "adjudicate:auth-boundary",
      "findings": "FINDING F1 (claimed critical), src/auth/Session.kt:88. Claim: ...",
      "sources": "docs/adr/0011-identity.md in full, src/auth/Session.kt, every caller of resolvePrincipal"
    }
  ]
}
```

Pass `args` as a real JSON object, not a string. A stringified list breaks `groups.map` inside
the script.

The template is plain JavaScript and `meta` must stay a pure literal, so run-specific values go
through `args` and never get interpolated into `meta`. `Date.now()` and `Math.random()` throw
inside a workflow, since they would break resume.

The adjudicators run under `parallel()`, which is a barrier: the writer needs every verdict
before it starts, and there is only one writer, so `pipeline()` would buy nothing here.

## Step 4. Check the work yourself

The apply agent reports on its own work. Read the diff before you believe it.

- `git diff` and read every hunk. Edits that landed somewhere unintended look fine in a summary.
- Re-run `verify` yourself. The agent may have reported output from before its last edit.
- **Read `red` before `verification`.** A finding whose `testProof` named a real test but whose
  `red` says "n/a" was applied without proof: the writer skipped the test-first step, and a green
  suite at the end says nothing about that finding. A `ledger:` proof whose `red` is not the
  ledger quoted against the applied wording was applied without proof too.
- **A fix that ships a because-clause ships an assertion for it.** A rationale nobody tested is
  as likely to be wrong as the bug it justifies, and it will outlive the session as a comment
  or a commit message that future readers trust. If the test disproves the reason, the change
  itself goes back on the table: rewriting the comment and keeping the code leaves behind code
  whose only remaining justification was written after the fact. Decide keep or delete, and say
  which.
- **Re-check every claim the fix ships.** Re-measure each number where it claims to be measured
  ("before" on `origin/<default>`, "after" on the head) and quote the output; back a "no
  behaviour change" with the ledger or a test. A claim measured on the wrong checkout looks
  exactly like a correct one.
- **For instruction edits, get a second ledger after every fix pass, including the last before
  merge; a later review round does not replace it.** Have a fresh read-only agent
  rebuild the ledger from `git diff` alone, without the adjudicator's, and compare. Then read each changed sentence
  on its own, as someone who never saw the old text: a sentence that parses two ways is a new
  finding.
- Grep for anything a house rule bans. It is cheap and it catches the edit that slipped through.
- Read the `skipped` list. A skip with a good reason is the workflow working. A skip that reads
  like "could not find the text" means a stale anchor, and that finding is still open.
- **Check `coverage.unreported`.** It names every finding the writer was handed and accounted for
  in neither list. Those edits may still be on disk: `git diff` on the files those findings name
  is the only thing that separates an edit that landed from one that was never made. The run
  cannot tell them apart for you - it can only refuse to let the gap pass unnoticed.

## Step 5. Report

One line per finding, in the reviewer's own ids:

```
F1  fix-here                    applied   OrderRequest.limitPrice now rejects a MARKET price bound
F2  real-but-decided-elsewhere  applied   annotated; auth spec D16 owns the deletion precondition
F3  refuted                     no edit   JupiterMints keys are unique; collision is unreachable
```

Then the failing `red` run for every finding that named a test, the re-checked ledger for every
instruction edit, and the verbatim `verify` output, labelled as not covering the changed paths,
never as a pass, when it touched none of them.
Say plainly which findings are still open and why, including any the writer skipped and anything
`coverage.unreported` names. A finding
ruled `refuted` is a result worth stating, not a gap. A finding skipped because its test passed
without the fix is still open: the adjudicator's evidence stands and only the writer's own test
failed, so the skip reason has to say whether the finding or the test is the thing to re-examine.

## Iterating

If the verification fails in a way the writer could not fix, do not re-run from scratch. Edit the
copied script and pass `resumeFromRunId` with the prior run id: unchanged `agent()` calls replay
from cache and only what you edited runs again. Stop the prior run with `TaskStop` first. A
worker restart moves the scratchpad, and `Workflow` refuses a `scriptPath` in the old one: after a
restart, copy the script into the current scratchpad before resuming.

Adjudication verdicts are usually the part worth keeping. It is the apply prompt that needs
another pass.
