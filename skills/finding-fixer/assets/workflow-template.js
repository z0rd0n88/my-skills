export const meta = {
  name: 'finding-fixer',
  description: 'Adjudicate review findings against the sources that decide them, then apply only the confirmed edits through a single writer',
  phases: [
    { title: 'Adjudicate', detail: 'read-only agents rule on each finding and propose byte-exact edits' },
    { title: 'Apply', detail: 'one writer applies the confirmed edits and re-runs the verification command' },
  ],
}

// Run-specific values arrive through `args`: cwd, houseRules, verify, groups. The skill's Step 1
// describes them; the guard below is the enforced version, so read it rather than a copy here.
// These args are authored by a model reading that doc, so a wrong shape is ordinary. Truthiness
// is not enough: a blank houseRules and a stringified groups both pass it.
if (!args || typeof args !== 'object' || Array.isArray(args)) {
  throw new Error(
    `finding-fixer: args must be a JSON object, not ${Array.isArray(args) ? 'an array' : args === null ? 'null' : typeof args}. ` +
    `Pass it as a real object, not a JSON-encoded string. See the skill's Step 3.`
  )
}

const { cwd, houseRules, verify, groups } = args

const blank = v => typeof v !== 'string' || !v.trim()
const problems = []
if (blank(cwd)) problems.push('cwd must be a non-blank string (the absolute worktree path)')
if (blank(houseRules)) problems.push('houseRules must be a non-blank string (the project invariants)')
if (blank(verify)) problems.push('verify must be a non-blank string (one shell command)')
if (!Array.isArray(groups)) problems.push(`groups must be an array, got ${typeof groups}`)
else if (!groups.length) problems.push('groups must contain at least one entry')
else groups.forEach((g, i) => {
  if (!g || typeof g !== 'object') return problems.push(`groups[${i}] must be an object`)
  for (const k of ['label', 'findings', 'sources']) {
    if (blank(g[k])) problems.push(`groups[${i}].${k} must be a non-blank string`)
  }
})

// Report every problem at once. A caller with two bad inputs should not need two launches.
if (problems.length) {
  throw new Error(
    `finding-fixer: bad args.\n  ${problems.join('\n  ')}\n` +
    `See the skill's Step 3 for the exact args shape.`
  )
}

const RULES = `
Working directory: ${cwd}. Stay inside it. Use absolute or repo-relative paths, never cd out.

${houseRules}
`

const ADJUDICATE_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          findingId: { type: 'string' },
          verdict: {
            type: 'string',
            enum: ['fix-here', 'real-but-decided-elsewhere', 'already-handled', 'refuted', 'unresolved'],
          },
          evidence: {
            type: 'string',
            description: 'Files, line numbers and quoted text that settle the verdict. Quote, do not paraphrase. No speculation.',
          },
          rejectsValidInput: {
            type: 'string',
            description: 'What correct input this fix now rejects, and which document teaches a human to produce that input. For an edit to instruction text an agent obeys: what legitimate behaviour the new wording now forbids or requires, and which other always-loaded instruction it now contradicts. "none" is a valid answer only after you checked. Verdicts carrying no edits answer "n/a - no fix proposed".',
          },
          testProof: {
            type: 'string',
            description: 'How a test proves this fix, named not run - you are read-only. For a behaviour change: the test file and the assertion, phrased so it FAILS against the code as it stands and passes after these edits. For a weak-test finding: the mutation the current test survives, which the replacement must catch. "n/a - <why>" when nothing executable changes: prose, comments, an annotation-only edit, or a verdict carrying no edits. A config value that a code path reads is a behaviour change: name the test, or say why no test can reach it. Instruction text an agent obeys (rules files, CLAUDE.md/AGENTS.md, SKILL.md, agent definitions, prompts) is a behaviour change no test reads: answer "ledger: " followed by every instruction, qualifier, exception and named entity in the text being replaced, each marked preserved, changed, dropped or added by the edit.',
          },
          edits: {
            type: 'array',
            description: 'Only fix-here and real-but-decided-elsewhere may carry edits, and edits on any other verdict are discarded before the writer sees them. Empty for refuted, already-handled and unresolved. For real-but-decided-elsewhere, a comment or annotation stating the decided behaviour, never a change to it.',
            items: {
              type: 'object',
              properties: {
                file: { type: 'string' },
                anchor: { type: 'string', description: 'Line number plus the symbol or path, e.g. 3624 OrderRequest.limitPrice' },
                current: { type: 'string', description: 'The exact current text, copied byte-for-byte out of the file including indentation. Read it with sed -n so you do not retype it.' },
                replacement: { type: 'string', description: 'The exact replacement, same indentation, house style.' },
                rationale: { type: 'string' },
              },
              required: ['file', 'anchor', 'current', 'replacement', 'rationale'],
            },
          },
        },
        required: ['findingId', 'verdict', 'evidence', 'rejectsValidInput', 'testProof', 'edits'],
      },
    },
  },
  required: ['verdicts'],
}

const APPLY_SCHEMA = {
  type: 'object',
  properties: {
    applied: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          findingId: { type: 'string' },
          file: { type: 'string' },
          summary: { type: 'string' },
          red: {
            type: 'string',
            description: 'The verbatim failing output captured BEFORE this edit was applied, proving the test the adjudicator named does fail. Not a description of it. "n/a - <why>" only where testProof was n/a. Where testProof was a "ledger:", the ledger re-checked against the text as applied: each entry with its applied wording quoted.',
          },
        },
        required: ['findingId', 'file', 'summary', 'red'],
      },
    },
    skipped: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          findingId: { type: 'string' },
          reason: { type: 'string' },
        },
        required: ['findingId', 'reason'],
      },
    },
    verification: {
      type: 'string',
      description: 'Verbatim output of the verification command. Not a summary of it.',
    },
  },
  required: ['applied', 'skipped', 'verification'],
}

phase('Adjudicate')
log(`Adjudicating ${groups.length} finding group(s) against the sources`)

const rulings = await parallel(
  groups.map(g => () => agent(
    `You are adjudicating review findings. Your job is VERIFICATION, not fixing. Do NOT edit any file.

${RULES}

FINDINGS UNDER REVIEW:
${g.findings}

Read these before ruling, and anything else they lead you to:
${g.sources}

Rule each finding honestly against what the sources actually say.

- "fix-here" means the claim holds and this repo is where it gets fixed. Propose the smallest
  edit that closes it. A larger restructure is only right if the small edit genuinely cannot
  express the rule, and then say why.
- "real-but-decided-elsewhere" means the risk is real but a spec, ADR or owner already decided
  the behaviour. Do not redesign around a decision you were not asked to revisit. The edit is a
  comment or annotation naming the risk and who owns it, or prose stating the decided behaviour
  and its consequence plainly.
- "already-handled" means the existing code or text already covers it. Quote the line that does.
- "refuted" means the sources contradict the claim. Quote the text that contradicts it.
- "unresolved" means you could not settle it from the sources available. Say in the evidence what
  you read and what you would still need. Return no edits: a guess you could not justify is worth
  less than an honest gap, and edits on this verdict are discarded before the writer sees them.

A finding that sounds severe is not thereby true. Reviewers reason from the diff alone and
routinely miss the mechanism that makes the code safe. Go find that mechanism before you accept
a severity.

Every verdict answers one more question, in "rejectsValidInput": WHAT CORRECT INPUT DOES THIS FIX
NOW REJECT? Every finding you were handed asks whether bad input can slip through; none of them
asks what the new gate costs. A tool that survived real use gets hardened into one that refuses
the very inputs it used to accept, and the run still reports every finding closed. Name the valid
input the fix rejects, or state there is none - after checking, not by default. Then answer the
second half: DOES ANY DOCUMENT TELL A HUMAN HOW TO PRODUCE THAT INPUT? A gate tightened without
its producing procedure means every correctly-followed run of that procedure now fails. Name the
document. For an edit to instruction text an agent obeys, the same question reads: WHAT LEGITIMATE
BEHAVIOUR DOES THE NEW WORDING NOW FORBID OR REQUIRE, AND WHICH OTHER ALWAYS-LOADED INSTRUCTION
DOES IT NOW CONTRADICT? A verdict proposing no edits answers "n/a - no fix proposed".

Every verdict also answers "testProof": HOW WOULD A TEST PROVE THIS? You are
read-only, so you name it rather than run it. For a behaviour change, name the test file and the
assertion, phrased so it fails against the code as it stands now and passes once your edits land.
For a finding about a WEAK TEST, name the mutation the current test survives - delete the guard,
flip the comparison, return a constant - the thing it should have caught and does not. The writer
executes what you name, so name something runnable, never "add a test for this". Tests here are
run with: ${verify} - name a test that command reaches, and one whose named assertion fails
before the edit; a whole green suite is not a proof. Answer "n/a - <why>" when nothing executable
changes: prose, comments, an annotation for real-but-decided-elsewhere. A config value that a code
path reads is a behaviour change: name the test, or say in the "n/a - <why>" why no test can reach
it. Do not invent a test for a documentation edit; a test that cannot fail is worse than no test.
Instruction text an agent obeys (rules files, CLAUDE.md/AGENTS.md, SKILL.md, agent definitions,
prompts) is the exception: it is behaviour that no test reads. Answer "ledger: " followed by every
instruction, qualifier, exception and named entity in the text being replaced, each marked
preserved, changed, dropped or added by your edit. Scope words ("when", "only when", "already",
"and others") are what a rewording drops without anyone noticing.
A verdict carrying no edits answers "n/a - no fix proposed".

Return exactly one verdict object per finding listed above, carrying that finding's own id. A
finding you cannot settle is "unresolved" with no edits, never a guess dressed as a verdict.
Nothing downstream can tell a finding you omitted from one that was never raised. An omission does
not read as still open; it disappears from the report entirely.

For every edit, copy "current" byte-for-byte out of the file with sed -n 'N,Mp' rather than
retyping it. A single wrong space makes the edit unappliable.`,
    { label: g.label, phase: 'Adjudicate', schema: ADJUDICATE_SCHEMA, effort: 'high' }
  ))
)

// A failed agent resolves to null rather than rejecting, so a whole group can vanish silently.
const failedGroups = rulings.map((r, i) => (r ? null : groups[i].label)).filter(Boolean)
const verdicts = rulings.filter(Boolean).flatMap(r => r.verdicts || [])

// The verdict decides what reaches the writer, not the mere presence of edits. An adjudicator
// that refutes a finding and still proposes a change does not get that change applied.
const CAN_EDIT = new Set(['fix-here', 'real-but-decided-elsewhere'])
const actionable = verdicts.filter(v => CAN_EDIT.has(v.verdict) && v.edits && v.edits.length > 0)
const discarded = verdicts.filter(v => !CAN_EDIT.has(v.verdict) && v.edits && v.edits.length > 0)

log(`${verdicts.length} verdicts from ${rulings.filter(Boolean).length}/${groups.length} groups: ` +
  verdicts.map(v => `${v.findingId}=${v.verdict}`).join(', '))
if (failedGroups.length) {
  log(`INCOMPLETE: ${failedGroups.length}/${groups.length} adjudicator(s) returned nothing (${failedGroups.join(', ')}). Findings in those groups were never ruled on.`)
}
if (discarded.length) {
  log(`Discarded edits from ${discarded.length} verdict(s) that may not carry them: ` +
    discarded.map(v => `${v.findingId}=${v.verdict}`).join(', '))
}
const coverage = { failedGroups, unreported: [] }

if (actionable.length === 0) {
  log('No finding produced an appliable edit. Nothing to apply.')
  return { verdicts, coverage, apply: { applied: [], skipped: [], verification: 'not run, no edits proposed' } }
}

phase('Apply')

const editBlocks = actionable.map(v =>
  `### ${v.findingId}, verdict: ${v.verdict}\nEvidence: ${v.evidence}\n` +
  `Test proof to produce first: ${v.testProof}\n\nEdits:\n` +
  v.edits.map((e, i) =>
    `--- edit ${v.findingId}.${i + 1} in ${e.file}\nanchor: ${e.anchor}\nrationale: ${e.rationale}\n` +
    `CURRENT:\n<<<\n${e.current}\n>>>\nREPLACEMENT:\n<<<\n${e.replacement}\n>>>`
  ).join('\n\n')
).join('\n\n')

const notApplied = verdicts.filter(v => !actionable.includes(v))
  .map(v => `${v.findingId}: ${v.verdict}. ${v.evidence}`).join('\n') || '(none)'

const applied = await agent(
  `Apply the adjudicated edits below. You are the ONLY writer in this run, so apply them one at a
time and keep every file you touch valid throughout.

${RULES}

Ruled on already, with nothing for you to apply. Context only, do not act on these:
${notApplied}

APPLY THESE EDITS:

${editBlocks}

How to apply:
1. TEST FIRST, wherever the adjudicator named one. For every edit block whose "Test proof" begins
   with neither "n/a" nor "ledger:": write or adjust that test BEFORE touching the code it
   covers, run it, and copy its verbatim failing output into "red" for that finding. A weak-test
   finding proves
   it the other way round - apply the mutation the adjudicator named, show the current test
   passing anyway, then write the replacement and show it failing on that same mutation, and
   revert the mutation before moving on.
   A test that passes on its first run has proved nothing. Do not paper over it: either the
   finding is wrong or the test does not exercise what the finding is about. Say which in
   "skipped" and leave that code alone.
   Authoring that test, and the temporary mutation above that you revert in the same step, are
   the only reasons to create or edit a file the edit blocks do not list. Nothing else.
   A "Test proof" that begins with "ledger:" is checked after the edit instead: re-read the
   changed text, check every ledger entry against it, and quote each entry with its applied
   wording in "red". If any entry does not hold - a qualifier the ledger kept is gone, a scope
   widened or narrowed - restore the original text and record the finding in "skipped".
2. Work in the order given. Locate CURRENT by exact string match and replace it with REPLACEMENT.
   A short python3 heredoc that asserts exactly one match before replacing is the safest tool.
   If CURRENT does not match byte-for-byte, do not guess: re-read the file around the anchor and
   adapt the match while preserving the intended change.
3. If two edits touch overlapping text, merge them into one coherent result rather than applying
   both blindly.
4. If an edit would violate a house rule above, do not apply it. Record it in "skipped" with the
   reason. Skipping a bad edit is the right outcome, not a failure.
5. An edit that adds a required field, a new constructor parameter, or anything else callers must
   supply is not done until every caller, example and fixture is updated too. Grep for them.

Then run the verification command and put its raw output in the "verification" field:
  ${verify}

If it fails, fix what your own edits broke and run it again. Report the final output verbatim,
including a failure you could not fix. A summary of the output is not the output. The same holds
for "red": it is the failing run you captured before the edit, quoted, and a green suite at the
end does not stand in for it.

Every finding id in the edit blocks above must appear in exactly one of "applied" or "skipped".
Nothing downstream can tell an edit you applied and forgot to report from one you never made. The
run reconciles both lists against what you were handed and flags the difference, so an omission
does not disappear - it becomes a gap someone has to resolve by reading the tree.`,
  { label: 'apply:edits', phase: 'Apply', schema: APPLY_SCHEMA, effort: 'high' }
)

// The writer self-reports, so an edit it applied but left out of both lists is invisible: a
// silently-applied finding and a silently-dropped one read identically to the caller. Reconcile
// what it was handed against what it accounted for. Sub-ids (F1.1, F1.2) still account for F1.
const reported = new Set([
  ...((applied && applied.applied) || []).map(a => String(a.findingId).split('.')[0]),
  ...((applied && applied.skipped) || []).map(s => String(s.findingId)),
])
coverage.unreported = actionable.map(v => v.findingId).filter(id => !reported.has(id))

if (!applied) {
  log('INCOMPLETE: the apply agent returned nothing. Edits may already be on disk - run git diff and the verification command by hand before trusting this run.')
}
if (coverage.unreported.length) {
  log(`UNREPORTED: the writer accounted for neither applying nor skipping ${coverage.unreported.join(', ')}. ` +
    `Those edits may still be on disk - run git diff on the files those findings name. Nothing else ` +
    `separates an edit that landed from one that was never made.`)
}

return { verdicts, coverage, apply: applied }
