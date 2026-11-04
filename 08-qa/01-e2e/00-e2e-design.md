# E2E Journey Catalog — Combinatorial Design (PO-directed, 2026-08-08)

> PO directive: "many E2E journeys; scenarios, combinations, variations — rates/plans, account types, read types, billing types, payments; positive path, break path, value changes x→y, upstream/downstream process changes, RBAC, reports/notifications/ledger/refunds/credits." This document is the DESIGN; journeys generate from it in tiers. Every money-bearing journey's expected values are MACHINE-COMPUTED (extending the 03-golden-verify.py pattern) — no hand math, ever.

## 1. The axes (all from ratified vocabularies — nothing invented)

| Axis | Values | n |
|---|---|---|
| A · Plan/tariff shape | flat · tiered · TOU · TOU+demand · seasonal · capacity-rider · multi-service mixed (the WE-1 shape) | 7 |
| B · Consumer category | Residential · Commercial · Industrial · Government | 4 |
| C · Read source | manual single · bulk import · estimated→true-up · assessed (theft) · supersede-corrected | 5 |
| D · Bill type | cycle · first · final · rebill · backbill · penalty · budget-presented | 7 |
| E · Payment outcome | full · partial · overpay→credit · NSF · none→collections ladder | 5 |
| F · Delivery path | print OK · email (W6-flagged) · returned→bad-address | 3 |
| G · Role executing | System Admin · Billing Clerk · Executive (view-only) | 3 |
| Full cartesian | 7×4×5×7×5×3×3 | **44,100** — which is why we design, not enumerate |

## 2. The tiers

| Tier | What | How many | Coverage logic |
|---|---|---|---|
| **T1 Spines** | J1–J6 (existing handoff-contract chains) | 6 | module handoffs |
| **T2 Feature journeys** | J7–J24 (first/final/budget/backbill/corrections/NSF/plans/lockbox/refund/catch-up/delivery/returned-mail/close/cutover/rate-change/template-life/isolation-sweep/localization) | 18 | one per ratified feature cluster |
| **T3 Combination journeys** | PAIRWISE covering array over axes A–F ≈ 60, PLUS **FULL money triples A×D×E** (PO 2026-08-08: "go deeper") — all 245 combinations machine-computed in expected/money-triples.csv; **145 authored as full journey files** (the money-critical prioritized set), remainder data-covered for engine testing | **~205 authored** | pairwise for breadth; FULL depth where money lives (80-20 per PO: heavy on meter-to-cash) |
| **T4 Transition journeys (x→y)** | the value-change catalog (§3) — each verifies UPSTREAM recompute + DOWNSTREAM effects (bill, ledger, reports, notifications, audit) | **~22** | every ratified mutable dimension |
| **T5 Break-path journeys** | the guard catalog (§4) — each proves a rule REFUSES correctly | **~28** | every hard rule + gate |
| **T6 RBAC journeys** | gated-action matrix: 3 roles × ~18 gated actions (approve correction, write-off, close, reopen, publish template, refund, reverse cross-period, unreconcile, currency set, reference-data edit…) packed into role-day journeys; every DENIAL asserted server-side | **~10** (54 checks) | positive + denial per role |
| **T7 Non-functional journeys** (PO: "include all — language, currency, config changes") | localization rides (per-language document rendering ×5, per-user UI language, es-MX bill end-to-end) · currency-locked tenant lifecycle + a CAD sample tenant · config-change journeys (grace calendar→business, allocation reorder, guardrail %, budget params, quiet hours, batch size — each proving future-only effect) | **~18** | every tenant knob proven safe to turn |
| **Total** | | **~307 journeys authored + 245-row expectation dataset** | |

## 3. T4 transition catalog (x→y — upstream/downstream verified in each)
plan change mid-cycle (split-period bill) · plan change across category (deposit differential = none v1, BR-CUS-062 asserted) · unit plan override while occupied · status Active→Vacation-hold mid-cycle→Active · Active→Marked-disconnect→pay→Active · →Closed (final) · rate version publish mid-history (old bills reprice on old) · template publish v2→v3 (pinning) · template language variant added · account preferred-language change · tax-exempt ON mid-cycle (next bill, not restated) · exemption cert expiry → warning not auto-untag · autopay enroll/cancel (intents appear/stop) · address change → bad-address flag clears · meter swap (asset reassign w/ final read) · sub-meter independent move · master-account link change (transfer path re-routes) · late-fee % config change (next assessment only) · grace mode calendar→business · allocation order reconfigure · budget level override ±30% · currency change attempt AFTER first financial record (MUST refuse — also in T5).

## 4. T5 break-path catalog (the system says NO, correctly)
edit issued invoice/payment/posted JE (append-only) · delete pinned template version · currency unlock attempt · cross-tenant access on every T1–T3 flow (the J23 sweep folded in) · duplicate bill run (idempotency key) · duplicate webhook/import file (file+tags) · double export same period · export open period · post into closed period (auto-forward proves) · reversal outside window w/o approval · correction execute without approval · negative-usage auto-fix attempt (hard error stands) · TOU incomplete channel set (completeness gate) · billing without plan snapshot · unit picker on occupied unit · read on retired meter · estimate 3rd consecutive (field-visit force) · demand estimate attempt (never) · hand-typed bill amount (no path exists) · 50k export cap · 10k import cap · pattern >3,000 · quiet-hours violation (queue holds) · dispatch burst (pacing proof at 10k) · self-lockout IP rule · last-admin demotion · tie-out drift injection → red flag + blocker · ~~malware upload rejection~~ (T5-28 now asserts upload guards with NO malware scan — SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload)).

## 5. Expected-value generation
A `04-e2e-expected-gen.py` harness (extends 03-golden-verify.py) computes every T3/T4 money expectation from the fixture rates — half-up 2dp per line, per the frozen B4. Generated journey files cite their computed values; the harness re-runs in CI so a rule change that shifts any expectation FAILS loudly. Fixture families extend Brazos Bend (add a Commercial-TOU-demand and an Industrial-seasonal account set).

## 6. Format & wiring
Each journey: one file in 08-qa/01-e2e/journeys/ (T-tier prefix in frontmatter), step table with per-step handoff contract + downstream assertions (ledger balanced, report delta, queue rows, audit rows — the PO's "upstream and downstream" requirement is a COLUMN, present in every journey). Story frontmatter `journeys:` wiring updated in the same commits; trace_lint extended to validate journey↔story links both ways.

## 7. PO sizing rulings (2026-08-08)
80-20 heavy on meter-to-cash CORE (T3 full money triples); non-functionals get their own tier (T7) so language/currency/config are TESTED, not assumed; authoring priority T5 break-paths → T4 transitions → T3 combinations → T6 RBAC → T7 (interleaved where fixtures overlap); build ALL.

## §6-as-amended (wiring, 2026-08-08): T-tier wiring = the GENERATED index (01-journey-story-index.md, script 07) — one re-runnable source instead of 227 frontmatter edits; J1–J6 frontmatter wiring unchanged. §2-as-executed: T3P = 53 journeys proving all 394 pairs (T3P-00 coverage matrix, generated + asserted); T3P agent died silently — replaced by deterministic generator (06-e2e-pairwise.py).

## CATALOG COMPLETE (2026-08-08 final): 300 journeys — 6 spines (J1–J6) + 16 lifecycle (J07–J22; J23/J24 absorbed → T5-04/T7-01..08) + 53 pairwise (all 394 pairs proven) + 147 money-triples + 22 transitions + 28 break-paths + 10 RBAC (~110 checks) + 18 non-functional; + 245-row expectation dataset, coverage matrix, generated wiring index (121 stories / 189+ rules exercised). Engine-computed figure gaps consolidated for the §5 harness fixture backlog.
