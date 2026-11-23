# Context-Aware Default Selection

Selection algorithm for the `multi-agent-review` reviewer roster. Used
**only when no explicit `--reviewers` roster is supplied**. Upgrades the "Default Roster
Selection" hierarchy in [`agent-catalog-lookup.md`](agent-catalog-lookup.md)
from a fixed baseline→overlay→lens list into a signal-driven, lane-diverse
selection with deterministic agent resolution.

Two components, cleanly divided:
- **This file** decides *which lanes are active* from context, and *how many*.
- [`lane-agent-table.md`](lane-agent-table.md) deterministically decides *which
  agent fills each lane*. The semantic matcher here is the fallback for lanes
  the table doesn't map or whose mapped agent isn't in the pool.

## 1. Selection precedence (highest wins)

1. Explicit `--reviewers` CSV → used verbatim (validated, then spawned).
2. **Context-aware selection** (this file) → the default when the roster flag is omitted.
   a. Active lanes come from §3 below.
   b. Each lane's agent comes from the deterministic table (per-repo → canonical),
      then the semantic matcher for anything unmapped.
3. Static safety-net roster → used whenever selection can't produce a real team:
   - **no signals resolvable** (context-aware selection can't run at all), OR
   - **signals resolve but no lane can be filled** — every active lane, including
     `L-BASELINE`, degrades to no pool agent (§6). A resolved lane set with an empty
     pool is not "selection succeeded with zero agents"; it's selection failing to
     produce a usable team, so it falls to the same safety net as the no-signal case.
   - review: `architect-reviewer, critical-thinking, silent-failure-hunter, security-reviewer, penetration-tester`
   - build: `code-reviewer, security-reviewer, tdd-guide, critical-thinking`
   - `penetration-tester` is the `L-REDTEAM` slot in the review net. It is the one
     name here allowed to be missing without hard-failing: if it is not in the pool,
     drop it and run the other four with a noted gap. The other four keep the §1
     rule-3 hard-fail. Rationale — the red-team lens is additive; the four original
     names are the net itself, and a net that silently shrinks to three is the
     failure this rule exists to prevent. **This carve-out does not weaken §6's
     "FORCED lanes hard-fail" rule** — it only applies on this rule-3 path, which is
     reached precisely when lane selection already failed wholesale, so no FORCED
     lane set exists to honour. A `L-REDTEAM` that is FORCED via the normal §5
     assembly path and cannot be covered still hard-fails.
   - If even the safety-net names aren't in the pool, that's a genuinely empty pool —
     hard-fail with the same message `--reviewers` uses for an unresolvable
     name, rather than emitting a zero-agent team silently.

## 2. Pool discovery (unchanged from agent-catalog-lookup)

Scan both tiers; match by the internal `name:` field, never filename:
- Project: `<repo>/.claude/agents/*.md`
- Parked: `~/.claude/agents-parked/CATALOG.md` (candidate; surfaced in a footnote,
  activated by the user with `activate <slug>` / `cp`).

Exclude the framework agents `code-explorer` and `code-architect` — they are
Phase-0 bootstrap deps, not selectable specialists. No tier penalty (Decision #13):
the best candidate wins regardless of activation status; parked picks get a footnote.

## 3. Cover lanes, not agents

A team is a set of **coverage lanes** with one best-fit agent each — this is what
makes "distinct lanes only" (Phase 3 Step C) structural rather than hoped-for.

**Floor lanes (always on):**
- `L-ADVERSARIAL` — challenge assumptions before committing (`critical-thinking`).
- `L-BASELINE` — stack-agnostic catch-all, owns whatever no specialist claims (`code-reviewer`).

**Signal-activated lanes:**

| Lane | Fires on |
|---|---|
| `L-REDTEAM` | attacker-mindset pass over the target: reachable attack surface, trust-boundary crossings, privilege escalation, guard/allowlist bypass. **Review teams only** — excluded from build teams by whichever mechanism forced it (§5 rule 1). Forced whenever any `risk_flag` fires, and the first FORCED lane to yield when the cap binds (§5 rule 2). Distinct from the `L-ADVERSARIAL` floor: that lane surfaces unstated assumptions, this one tries to break the system. |
| `L-APPSEC` | auth, user input, secrets, network I/O, deserialization, injection/SSRF |
| `L-CRYPTO` | private keys, signing, custody, wallet, on-chain submit, delegation |
| `L-FINANCE` | money movement, ledger, order/trade, notional, fees, regulatory/compliance |
| `L-WEB3` | programs, PDAs/CPIs, EVM/Solana, tx building, DEX/venue integration |
| `L-NUMERIC` | decimals, financial math, BigDecimal/Decimal, rounding, precision |
| `L-LANG` | the primary language(s) of the diff (Python, TS, Kotlin, SQL, …) |
| `L-ARCH` | new module, cross-cutting refactor, boundary/interface change |
| `L-DATA` | migrations, schema, ORM parity, query plans |
| `L-API` | REST/GraphQL/OpenAPI, WS, versioning, wire format |
| `L-PERF` | hot path, large N, memory, latency, streaming |
| `L-RESILIENCE` | error handling, fallbacks, retries, swallowed exceptions |
| `L-TEST` | new logic without tests, TDD discipline, flaky/e2e |
| `L-EXPLORE` | claims to verify against real code, legacy tracing. **Review-only lane** — excluded from build teams by whichever mechanism activated it (§5 rule 1), same as `L-REDTEAM`. (`code-explorer` is separately framework-excluded — use the mapped explorer specialist, not the bootstrap agent.) |
| `L-MOBILE` | iOS/Android, App-Store surface, mobile UX |
| `L-DOCS` | public API docs, reference material |

## 4. Signals

From the target and context, extract: `languages[]`; `domains[]` (finance, crypto,
web3, mobile, api, data); `layers[]` (db, api, ws, ui, infra); `change_type`
(feature / refactor / bugfix / spec); and `risk_flags[]` (moves money, touches
keys/signing, irreversible action, external I/O, data-loss).

Signal sources in priority order — stop when the picture is confident:
1. The resolved target/diff (`pr|dir|file|spec|diff|slices`) — changed paths, extensions, deps.
2. The task / spec / issue text (and any `--prompt-prelude` spec).
3. Repo invariants — `CLAUDE.md` / ADRs / `CONTEXT.md`. **These become forced lanes.**
4. Path & filename cues — `db/migration/`, `openapi.yaml`, `*.sol`, `signer`, `wallet`, `*.tsx`.

## 5. Scoring & assembly (mirrors Phase 3 Step B, generalized)

```
score(lane) = (# distinct signals hitting the lane)
              × 2   if any hitting signal is also a risk_flag
FLOORS  = {L-ADVERSARIAL, L-BASELINE}         # score → ∞, always kept
FORCED  = lanes made mandatory by a risk_flag or a repo invariant:
            keys/signing   → L-CRYPTO
            money/decimals → L-NUMERIC (+ L-FINANCE)
            on-chain       → L-WEB3
            db migration   → L-DATA
            ANY risk_flag  → L-REDTEAM   # subject to the two L-REDTEAM rules below
            + any lane the repo's CLAUDE.md/ADR demands
CAP     = review: soft 6 per slice     build: hard 4  (== --max-agents, [1,4])
```

**Review-only lanes: `L-REDTEAM` and `L-EXPLORE`.** Neither may appear in a build team, **regardless of which mechanism activated or forced it** — signal, risk flag, repo `FORCE:` line, or a `CLAUDE.md`/ADR invariant. This is a property of the lane class, not of any one trigger, and stating it that way is the whole point: attaching the restriction to the risk-flag trigger alone leaks, because the repo-invariant path (§4 source 3) and a bare `FORCE:` line in a per-repo `## LANE MAP` are both unqualified as to which lanes they may name. Either would otherwise drop an attacker-mindset or exploration agent into a 4-slot build team.

1. **Build teams never include a review-only lane.** Drop it during assembly whenever the team type is build, even when explicitly forced, and record the drop. An attacker pass belongs to review, not construction; so does spec-vs-reality tracing. A repo that genuinely wants red-teaming around a build should run `multi-agent-review` on the result, which is where the lane lives.

Rule 2 below applies to `L-REDTEAM` only — `L-EXPLORE` is not FORCED-eligible by any keyword trigger, so the cap-overflow ordering question does not arise for it.
2. **`L-REDTEAM` yields first when FORCED exceeds CAP — but only while the team still holds another security lane.** Check the condition, do not assume it:
   - **If `L-APPSEC` or `L-CRYPTO` is in the team**, `L-REDTEAM` is the first FORCED lane dropped, ahead of §6's "drop the lowest-risk optional lane" step. Here it is genuinely additive: another lens already covers the same code, and every other FORCED lane covers a risk nothing else does. Record the drop; never drop it silently.
   - **If neither is in the team, `L-REDTEAM` MUST NOT be dropped** — it *is* the team's security coverage, and dropping it is what §6's "≥1 security lane present whenever any `risk_flag` fired" repair exists to prevent. Fall through to the known CAP-overflow gap below and surface the overflow instead.

   > The condition is load-bearing because the obvious rationale — "any risk flag forces a security lane anyway" — is **false**. Only `keys/signing → L-CRYPTO` puts a security lane into FORCED; `L-APPSEC` appears nowhere in the FORCED formula and is asserted only by §6's post-assembly repair, which has no injection path once CAP is already exhausted. Reachable counterexample: `risk_flags = [money, on-chain, db-migration]` (no keys) forces `L-NUMERIC`, `L-FINANCE`, `L-WEB3`, `L-DATA`, `L-REDTEAM` = 5, plus 2 FLOORS = 7 against the review soft cap of 6. An unconditional yield-first rule drops the attacker lens and ships a money + on-chain + migration review with **no security lane at all** — precisely the diff that most needed one.

> **Known gap, pre-dating `L-REDTEAM` — FORCED alone can still exceed CAP.** `risk_flags=[keys, money, on-chain]` forces `L-CRYPTO`, `L-NUMERIC`, `L-FINANCE`, `L-WEB3` — four lanes, plus two FLOORS — against a build cap of 4, with no optional lane for §6's remedy to drop and no forced lane it is allowed to drop. Rule 2 above keeps `L-REDTEAM` from making this worse, but does not resolve it. Until a rule exists, surface the overflow explicitly rather than silently shipping a team that violates either the cap or the FORCED set.

Assembly:
1. Reserve FLOORS. Add all FORCED (priority: keys > money > data > api > perf; **within a priority tier that maps to more than one lane — "money" maps to both `L-NUMERIC` and `L-FINANCE` — order by lane name ascending**; lanes the list does not name at all — `L-WEB3`, `L-REDTEAM`, repo `FORCE:` lanes — follow the named tiers in lane-name ascending order, with `L-REDTEAM` always last). Apply the review-only-lane rule and the `L-REDTEAM` cap rule above before proceeding.
2. Rank remaining active lanes by score; add highest-first until CAP.
3. Resolve each chosen lane to an agent via [`lane-agent-table.md`](lane-agent-table.md):
   per-repo table → canonical table → semantic matcher (best role-text match in the
   pool for the lane + concrete signals). Cross-cutting baselines from Phase 3 still
   apply: a security lane scores +6 (not +4) when the task touches auth/input/secrets/APIs;
   `L-TEST` is baseline-present for build tasks (TDD is the default discipline).
4. One agent per lane; specialists beat generalists; ECC-flavored and project-scoped
   win ties (Phase 3 tie-breaker).

## 6. Safety repair (apply before emitting)

- ≥1 security lane (`L-APPSEC`/`L-CRYPTO`) present whenever any `risk_flag` fired.
- ≥1 `L-LANG`/domain specialist present when there is a clear primary language/domain.
- If CAP < FLOORS + FORCED, drop the lowest-risk **optional** lane only — never a
  floor or forced lane — and record what was dropped.
- **Degrade loudly.** If a chosen **optional** lane has no matching pool agent, fall
  back to `L-BASELINE` and say so in the rationale — the team still ships.
- **FORCED lanes hard-fail, they don't silently degrade.** A FORCED lane exists
  because a `risk_flag` or repo invariant made it mandatory (e.g. keys/signing →
  `L-CRYPTO`). If it's uncoverable, do **not** ship the team without it: stop and
  state the gap explicitly, the same way an unresolvable name in `--reviewers` hard-
  fails rather than silently dropping the reviewer. (If `L-BASELINE` itself — a
  floor, not a FORCED lane — is uncoverable, that's the empty-pool case in §1 rule 3,
  not this rule.)

## 7. Output contract

Emit, in priority order (floors + forced first):
1. The roster as a comma-separated agent-name list (validated against the pool).
2. A table: `agent | lane | one-line reason`.
3. A parked-alternatives footnote when a better candidate sits in `agents-parked`
   (per Decision #13), so the user can `activate <slug>` and re-run.

**What's actually deterministic:** lane→agent *resolution* (§lane-agent-table.md) is a
pure function of the active lane set and the discovered pool — same lanes + same pool
always resolve to the same roster. Lane *activation* (§4-5 above) is not a deterministic
function of the input; "stop when the picture is confident" and the domain/risk-flag
extraction are model judgment calls, so two runs against a genuinely identical diff
should usually agree but aren't guaranteed to bit-for-bit. Log the roster + reasons so
a human can see why this team was chosen and override with `--reviewers`
next run.
