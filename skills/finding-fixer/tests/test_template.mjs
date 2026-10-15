// Drives workflow-template.js end to end with stubbed agents.
//   node ~/.agents/skills/finding-fixer/tests/test_template.mjs
// The template is a workflow body, not a module: it uses top-level await, top-level
// return, and the runtime globals args/agent/parallel/phase/log. So it is wrapped in
// an async function and imported as a data: URL. Assertions only, no framework.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import assert from 'node:assert/strict'

const HERE = dirname(fileURLToPath(import.meta.url))
const TEMPLATE = join(HERE, '..', 'assets', 'workflow-template.js')

const src = readFileSync(TEMPLATE, 'utf8').replace(/^export const meta/m, 'const meta')
const { default: run } = await import(
  'data:text/javascript;base64,' +
    Buffer.from(
      `export default async function run(args, agent, parallel, phase, log) {\n${src}\n}`,
    ).toString('base64')
)

const parallel = (fns) => Promise.all(fns.map((f) => f()))
const phase = () => {}

const ARGS = {
  cwd: '/tmp/somewhere',
  houseRules: '1. No em dashes.',
  verify: 'SENTINEL-VERIFY-CMD',
  groups: [{ label: 'adjudicate:x', findings: 'F1 and F2 claim the guard is missing.', sources: 'src/x.ts' }],
}

const verdict = (id) => ({
  findingId: id,
  verdict: 'fix-here',
  evidence: `src/x.ts:12 has no null check (${id}).`,
  rejectsValidInput: 'none',
  testProof: `test/x.test.ts asserts parse(null) throws; fails today (${id}).`,
  edits: [{
    file: 'src/x.ts', anchor: `12 parse ${id}`, current: `return v // ${id}`,
    replacement: `if (v == null) throw new Error()\n  return v // ${id}`, rationale: 'close the null path',
  }],
})

// A run where the writer accounts for every finding it was handed.
function stubs({ applied, skipped = [], verdicts = ['F1', 'F2'], dead = false }) {
  const prompts = []
  const logs = []
  const agent = async (prompt, opts) => {
    prompts.push({ label: opts.label, phase: opts.phase, prompt })
    if (opts.phase === 'Adjudicate') return { verdicts: verdicts.map(verdict) }
    if (dead) return null
    return { applied, skipped, verification: 'suite green' }
  }
  return { agent, prompts, logs, log: (m) => logs.push(m) }
}

const applyOf = (id) => ({ findingId: id, file: 'src/x.ts', summary: `guard added (${id})`, red: `AssertionError: expected throw (${id})` })

// --- 1. the happy path still works -------------------------------------------------
{
  const s = stubs({ applied: [applyOf('F1'), applyOf('F2')] })
  const out = await run(ARGS, s.agent, parallel, phase, s.log)
  assert.ok(out && out.apply, 'valid args must produce an apply result')
  assert.equal(out.apply.applied.length, 2)
  assert.deepEqual(out.coverage.unreported, [], 'a complete report leaves nothing unreported')
  assert.ok(!s.logs.some((l) => l.startsWith('UNREPORTED:')), 'no UNREPORTED log on a clean run')
}

// --- 2. THE REGRESSION: the writer applies an edit and omits it from its report -----
// Observed on ClaudesMods PR 179: F9 was ruled fix-here, its edit landed on disk, and
// it appeared in neither applied nor skipped. A silently-applied edit and a silently-
// dropped one looked identical to the caller.
{
  const s = stubs({ applied: [applyOf('F1')] })   // F2 omitted entirely
  const out = await run(ARGS, s.agent, parallel, phase, s.log)
  assert.deepEqual(out.coverage.unreported, ['F2'],
    'a finding the writer never accounted for must surface in coverage.unreported')
  const line = s.logs.find((l) => l.startsWith('UNREPORTED:'))
  assert.ok(line, 'an unaccounted finding must be logged, not silently dropped')
  assert.ok(line.includes('F2'), 'the log line must name the finding')
  assert.ok(/git diff/.test(line), 'the log must say how to tell applied from dropped: read the tree')
}

// --- 3. a reported skip is accounted for, not unreported ---------------------------
{
  const s = stubs({ applied: [applyOf('F1')], skipped: [{ findingId: 'F2', reason: 'violates a house rule' }] })
  const out = await run(ARGS, s.agent, parallel, phase, s.log)
  assert.deepEqual(out.coverage.unreported, [], 'an explicit skip is an accounted-for outcome')
}

// --- 4. sub-ids (F1.1, F1.2) count as reporting F1 ---------------------------------
{
  const s = stubs({ applied: [{ ...applyOf('F1'), findingId: 'F1.1' }, { ...applyOf('F1'), findingId: 'F1.2' }, applyOf('F2')] })
  const out = await run(ARGS, s.agent, parallel, phase, s.log)
  assert.deepEqual(out.coverage.unreported, [], 'per-edit sub-ids still account for their finding')
}

// --- 5. a dead writer leaves every finding unreported, and says so -----------------
{
  const s = stubs({ applied: [], dead: true })
  const out = await run(ARGS, s.agent, parallel, phase, s.log)
  assert.equal(out.apply, null, 'a dead writer returns null, unchanged')
  assert.deepEqual(out.coverage.unreported, ['F1', 'F2'], 'a dead writer accounts for nothing')
  assert.ok(s.logs.some((l) => l.startsWith('INCOMPLETE:')), 'a dead writer is logged')
}

// --- 6. the adjudicator's proof and the verify command reach the prompts -----------
{
  const s = stubs({ applied: [applyOf('F1'), applyOf('F2')] })
  await run(ARGS, s.agent, parallel, phase, s.log)
  const adj = s.prompts.find((p) => p.phase === 'Adjudicate').prompt
  const apply = s.prompts.find((p) => p.label === 'apply:edits').prompt
  assert.ok(adj.includes('F1 and F2 claim the guard is missing.'), 'group findings reach the adjudicator')
  assert.ok(adj.includes('SENTINEL-VERIFY-CMD'), 'the adjudicator is shown the command its test must run under')
  assert.ok(apply.includes('test/x.test.ts asserts parse(null) throws'), 'testProof reaches the writer')
  assert.ok(!/Test proof to produce first:\s*(undefined|$)/m.test(apply), 'testProof never renders as undefined')
}

// --- 7. the arg guard still rejects bad input --------------------------------------
{
  const s = stubs({ applied: [] })
  for (const key of ['cwd', 'houseRules', 'verify']) {
    await assert.rejects(() => run({ ...ARGS, [key]: '' }, s.agent, parallel, phase, s.log),
      (e) => e.message.includes(key), `blank ${key} must be rejected`)
  }
  await assert.rejects(() => run('{"cwd":"x"}', s.agent, parallel, phase, s.log),
    /must be a JSON object/, 'a stringified args must be rejected')
}

console.log('test_template.mjs: all assertions passed')
