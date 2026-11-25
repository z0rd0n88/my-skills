# Lane → Agent Table (deterministic resolver)

Companion to [`context-aware-selection.md`](context-aware-selection.md). The
selection algorithm decides **which lanes are active**; this table
deterministically decides **which agent fills each lane** — no model judgment,
stable across runs. The semantic matcher is used only for a lane this table does
not map, or when a mapped agent is absent from the pool.

## Resolution order per lane

1. **Per-repo override table** (if present) — `<repo>/.claude/agent-lanes.md`, or a
   `## LANE MAP` block injected via `--prompt-prelude`, or a `lane_map:` key in the
   project's `config.yml`. Highest precedence; lets each repo bind lanes to its own
   agent names.
2. **Canonical default table** (below) — the ecosystem-standard names.
3. **Semantic matcher** — best role-text match in the pool (from
   `context-aware-selection.md` §5, Assembly step 3). Only reached when neither table
   resolves to a pool agent.

For any lane, walk the ordered candidate list and pick the **first name that exists
in the discovered pool** (project ∪ activated-parked). If none exist, degrade to the
lane's fallback lane (usually `L-BASELINE`) and flag the gap loudly.

**One agent fills at most one lane.** Several chains deliberately overlap at their
tails — `L-APPSEC`, `L-CRYPTO`, and `L-REDTEAM` all end in `security-reviewer`,
and `L-DATA` and `L-LANG:sql` both end in `postgres-pro` — so a naive walk can hand
the same agent two lanes and ship an N-lane team with N-1 distinct agents. When a
lane's best candidate is **already assigned**, continue down that lane's chain to the
next unassigned name.

*Chain exhausted* (every candidate absent from the pool or already assigned) resolves
by lane class, and the two classes behave oppositely:

- **Optional lane** → degrades to `L-BASELINE` per the rule above. The rationale must
  distinguish the two causes: *"chain exhausted (all candidates already assigned)"* vs
  the generic no-pool-agent message. They need different fixes — one needs an agent
  installed, the other needs a distinct one bound via the per-repo `## LANE MAP`.
- **FLOOR or FORCED lane** → **hard-fails; it does not degrade.** This is
  `context-aware-selection.md` §6's rule (*"FORCED lanes hard-fail, they don't silently
  degrade"*) and it governs exhaustion-by-assignment exactly as it governs
  exhaustion-by-absence. The failure message must say the lane was uncoverable
  *because its candidates were taken by higher-priority lanes*, and name them —
  otherwise the operator installs an agent that was already present. Reachable case:
  a repo invariant forces `L-APPSEC` and `risk_flags=[keys]` forces `L-CRYPTO`, while
  the pool holds only `security-reviewer`. `L-CRYPTO` resolves first (named
  priority tier) and claims it; `L-APPSEC` then walks
  `security-reviewer` (taken) → `security-reviewer` (absent) →
  `penetration-tester` (absent), exhausts, and **hard-fails** — it is FORCED, and no
  exception covers it.
- **Exception — `L-REDTEAM` drops instead of hard-failing when, and only when, the
  team still holds another security lane** (`L-APPSEC` or `L-CRYPTO`). In that case it
  is additive rather than gap-filling. **This is the common collision, not a rare
  one** — pool holds `security-reviewer` but neither `penetration-tester` nor
  `security-engineer`; `risk_flags=[keys]` forces both `L-CRYPTO` and `L-REDTEAM`;
  `L-CRYPTO` resolves first and takes `security-reviewer`, leaving `L-REDTEAM`
  exhausted by assignment. `L-CRYPTO` claiming that tail is exactly what a
  keys-flagged review *should* do, and hard-failing there would block every such
  review on an uninstalled `penetration-tester`. Drop the lane, record it, continue.
  **If no other security lane is in the team, the hard-fail stands** — `L-REDTEAM` is
  then the only security coverage, and silently dropping it produces a risk-flagged
  review with none. Same
  condition as the cap-pressure rule (`context-aware-selection.md` §5 rule 2); the
  lane's droppability is conditional at both pressure points, and identically so, or
  the two rules contradict.
- **Exception — `L-WEB3` degrades instead of hard-failing, even when FORCED.** Vista
  Phase 1 is Solana-only (VBE ADR-0004), these skills ship no agents, and the usual
  pools (vista-dev's included) hold no Solana program or venue specialist; the EVM
  agent that used to end this chain was removed. A chain exhausted by either cause
  degrades to `L-BASELINE` like an optional lane, and the rationale says *"L-WEB3: no
  on-chain specialist in pool; on-chain correctness rides on L-CRYPTO + L-NUMERIC and
  the `solana-dev` skill"*. That is VBE's own stance (VBE `.claude/agent-lanes.md`).
  Never pull an EVM agent in to fill it.

**Resolution order is a total order** — the dedup rule above is order-dependent, so
"whoever resolves first wins the shared agent" only yields a reproducible roster if
the order is fully pinned. Resolve in exactly this sequence:

1. **FLOORS**, in the fixed order `L-ADVERSARIAL`, `L-BASELINE`.
2. **FORCED lanes**, by the risk priority in `context-aware-selection.md` §5
   (`keys > money > data > api > perf`), then any FORCED lane that priority list does
   not name — including `L-WEB3`, `L-REDTEAM`, and repo-mandated `FORCE:` lanes — in
   **lane-name ascending** order. `L-REDTEAM` resolves **last among FORCED lanes**
   regardless (see `context-aware-selection.md` §5), because its chain is the one that
   most often collides with an already-assigned security agent and it is the most
   droppable of the security lanes.
3. **Optional lanes**, by descending selection score; ties broken by **lane name
   ascending**.

Without step 3's name tiebreak, two runs over an identical diff and pool could hand a
shared-tail agent (e.g. `postgres-pro`, wanted by both `L-DATA` and `L-LANG:sql`) to
different lanes and produce different rosters — which would falsify the determinism
guarantee `context-aware-selection.md` §7 makes for lane→agent resolution.

## Canonical default table

Names are the Z0rd0nZords-native canonical `name:` values. `→` marks the ordered
preference chain; earlier wins if present in the pool.

| Lane | Candidate agents (ordered) | Trigger keywords |
|---|---|---|
| `L-ADVERSARIAL` | `critical-thinking` | (floor — always) |
| `L-BASELINE` | `code-reviewer` → `code-reviewer` | (floor — always) |
| `L-REDTEAM` | `penetration-tester` → `security-engineer` → `security-reviewer`* | attack surface, exploit, trust boundary, privilege, untrusted input, bypass (*review-only lane — excluded from build teams by any activation path, incl. repo `FORCE:`) |
| `L-APPSEC` | `security-reviewer` → `security-reviewer` → `penetration-tester` | auth, input, secrets, ssrf, injection, token |
| `L-CRYPTO` | `crypto-security-reviewer` → `smart-contract-auditor` → `security-reviewer` | key, sign, wallet, custody, delegation, kms |
| `L-FINANCE` | `fintech-engineer` → `payment-integration` → `compliance-auditor` → `quant-analyst` | payment, ledger, order, notional, fee, settlement |
| `L-WEB3` | `web3-integration-specialist` → `smart-contract-specialist`* | onchain, pda, cpi, evm, solana, tx, dex, venue (*no shipped agent covers this lane, so it usually degrades; see the `L-WEB3` exception above) |
| `L-NUMERIC` | `numeric-precision-reviewer` | decimal, bigdecimal, rounding, precision, float |
| `L-LANG:python` | `python-reviewer` → `python-pro` → `code-reviewer` | `.py`, python, pip, pytest |
| `L-LANG:typescript` | `typescript-reviewer` → `typescript-pro` → `react-specialist` | `.ts`, `.tsx`, node, npm |
| `L-LANG:kotlin` | `kotlin-specialist` → `kotlin-reviewer` | `.kt`, ktor, gradle, coroutine |
| `L-LANG:sql` | `sql-pro` → `postgres-pro` | `.sql`, query, index, schema |
| `L-ARCH` | `architect-reviewer` → `code-architect` | module, boundary, refactor, layering |
| `L-DATA` | `database-optimizer` → `postgres-pro` → `database-reviewer` | migration, schema, orm, query-plan |
| `L-API` | `api-architect` → `api-designer` → `websocket-engineer` | rest, graphql, openapi, endpoint, ws |
| `L-PERF` | `performance-optimizer` → `performance-optimizer` → `chaos-engineer` | latency, throughput, memory, hotpath |
| `L-RESILIENCE` | `silent-failure-hunter` → `silent-failure-hunter` → `error-detective` | fallback, retry, swallow, error-handling |
| `L-TEST` | `tdd-guide` → `test-automator` → `qa-expert` | tdd, coverage, e2e, flaky |
| `L-EXPLORE` | `code-explorer`* → `code-tour` | trace, legacy, spec-vs-reality (*review-only lane — excluded from build teams by any activation path, incl. repo `FORCE:`) |
| `L-MOBILE` | `mobile-app-developer` → `react-specialist` | ios, android, app-store, mobile |
| `L-DOCS` | `api-documenter` → `technical-writer` | docs, reference, changelog |

`L-LANG:<language>` is selected by the diff's primary language; if the language has
no row, `L-LANG` degrades to `L-BASELINE` and the rationale notes "no <lang>
specialist in pool".

**`L-ADVERSARIAL` ≠ `L-REDTEAM` — do not collapse them.** They sound
interchangeable and are not:

| | `L-ADVERSARIAL` (`critical-thinking`) | `L-REDTEAM` (`penetration-tester`) |
|---|---|---|
| Question asked | "What is the author assuming without saying?" | "How do I make this code do something it must not?" |
| Output shape | Assumptions / open questions — **no severity tags** | Severity-tagged findings, same rubric as every other lane |
| Consumed as | Its own report section (`multi-agent-review` §9) | Ordinary findings, merged into the severity buckets |
| Status | Floor lane — always on | Signal-activated; forced whenever any `risk_flag` fires |

A repo that rebinds `L-ADVERSARIAL` to an attacker-mindset agent loses the
assumptions lens entirely and gets two red teams. Rebind `L-REDTEAM` instead.

Neither lane is the **refutation stage** — that is a separate pipeline step that
attacks *the findings*, not the target, and spawns no lane. See
`multi-agent-review` §5A.5a.

## Per-repo override format

Drop this at `<repo>/.claude/agent-lanes.md` (auto-read during pool discovery) or
inject it via `--prompt-prelude`. Only list the lanes you want to rebind — unlisted
lanes fall through to the canonical table.

```markdown
## LANE MAP
L-ARCH: architect-reviewer          # this repo renamed architect-review
L-LANG:kotlin: kotlin-specialist, kotlin-reviewer
L-NUMERIC: numeric-precision-reviewer
L-DATA: flyway-exposed-parity-reviewer, database-reviewer
L-CRYPTO: crypto-security-reviewer
# forced lanes this repo mandates regardless of signals:
FORCE: L-NUMERIC, L-CRYPTO          # e.g. Prime Directive §1 + custody
```

Format: one `L-*: name[, fallback...]` per line; an optional `FORCE:` line adds
repo-mandated forced lanes. Names are validated against the pool at parse time
(unknown → hard-fail, same as `--reviewers`).

## Worked instantiation — a Kotlin/Solana custody repo (e.g. VistaMobileBE)

Its pool renamed `architect-review`→`architect-reviewer` and carries
`numeric-precision-reviewer`, `crypto-security-reviewer`,
`flyway-exposed-parity-reviewer`, `kotlin-specialist`. Its `## LANE MAP` (above)
plus `FORCE: L-NUMERIC, L-CRYPTO` means a task touching a signing executor with
BigDecimal amounts deterministically yields, for a build team (cap 4):

| Agent | Lane | Source |
|---|---|---|
| `crypto-security-reviewer` | `L-CRYPTO` | forced (repo) + keys signal → table |
| `numeric-precision-reviewer` | `L-NUMERIC` | forced (repo) + decimals → table |
| `critical-thinking` | `L-ADVERSARIAL` | floor |
| `kotlin-specialist` | `L-LANG:kotlin` | per-repo override |

`L-BASELINE` (`code-reviewer`) is the first thing dropped at cap 4 because both
forced security/numeric lanes plus the adversarial floor already consume 3 slots and
the language specialist outscores a generic catch-all here — recorded in the drop
note per §6.

## Worked instantiation — the user's Python crypto example (no per-repo table)

`languages=[python]`, `risk_flags=[keys, money]`, review cap 6. Canonical table only:

| Agent | Lane | Source |
|---|---|---|
| `crypto-security-reviewer` | `L-CRYPTO` | forced (keys) → canonical |
| `numeric-precision-reviewer` | `L-NUMERIC` | forced (money) → canonical |
| `web3-integration-specialist` | `L-WEB3` | on-chain signal → canonical |
| `critical-thinking` | `L-ADVERSARIAL` | floor |
| `code-reviewer` | `L-BASELINE` | floor |
| `python-reviewer` *(or `python-pro`)* | `L-LANG:python` | language → canonical; if absent, note gap |

The last row is the deterministic answer to "is language expertise covered?" — the
table names the exact agent, and if neither `python-reviewer` nor `python-pro` is in
the pool it degrades loudly to the baseline instead of silently pretending.
