# EP-RAT-07 — Tenant-authored calculation rules (the `formula` charge amount rule) 🔒

> **Authored 2026-08-10 against the PO request:** *"how do we allow business users to define some calculation rules that are very common and can change utility to utility — so that we don't have to do code changes every time"*.
> **⚠ UNBLOCKED 2026-08-10 — this header's original text is kept below for the record and is NO LONGER the state (amended 2026-08-15, DEF-104).** OQ-095 is **CLOSED(→BR-RAT-046)**: *PO 2026-08-10: **"YES, enable it."** `formula` becomes a fourth amount rule; the three existing shapes are unchanged. The screen already renders the option disabled, so this switches on a control the spec always drew.* All four stories therefore moved from `status: blocked, blocked_by: [OQ-095]` to `status: draft, blocked_by: []` — **the questions closed on 2026-08-10 and only the registry was updated**, so for five days this epic told every agent that reads it to stub a question that had been answered. That is the exact shape DEF-104 registers, and a gate clause in G8 now fails on it.
>
> **The original text, as written 2026-08-10 before the ruling:** *"This epic is BLOCKED in its entirety on a PO ruling.* It amends **BR-RAT-041**, which is **CONFIRMED** (PO OQ-053) and says: charge amount rules v1 = flat / percent / percent-with-minimum, **"Formula" visible but disabled**. The extension point the PO is asking for already exists in the spec and was deliberately switched off. Turning it on is an **amendment**, not an interpretation — so it is written here as a proposed amendment (BR-RAT-046) with its rationale, *and every story ships `status: blocked`, `blocked_by: [OQ-095]`. Nothing here contradicts BR-RAT-041 while it stands."*

**Module:** rating (product name: Plans & Rates) · **Wave:** W8 (v1.1 unlock — derived from B12 r3, "W8 · v1.1/v2 unlocks"; placement is part of OQ-095) · **Screens:** S9 (Charge codes tab · History view), S12 (New Charge Code step 2 — the existing "Formula" radio) · **Status:** draft — **blocked**

## Scope

**In:** the fourth charge **amount rule** — a tenant-authored expression that computes a charge line's amount (BR-RAT-046, amending BR-RAT-041). It plugs into the amount-rule interface US-RAT-015/BR-RAT-045 already defines, so the engine gains a module and no stage changes. Specifically: a **declared, versioned variable vocabulary** (BR-RAT-047) · a **safe evaluator** with a closed grammar, no code execution, no I/O, `Decimal` arithmetic and hard failure on error (BR-RAT-048) · a **single evaluation point** in the pipeline with a total order and no chaining (BR-RAT-049) · **versioning exactly like a tariff**, with `formula_version_id` stamped on every line it prices (BR-RAT-050) · **test-before-publish** with the sample set stored on the version (BR-RAT-051) · **audit on every write** (BR-RAT-052, CLAUDE.md #7) · the **`custom_data` boundary proven by gate** (BR-RAT-053) · and the **blast-radius path** when a published formula is found wrong after bills issued (BR-RAT-054), which reuses the ratified correction workflow and invents nothing.

**Out:** **tenant-authored expressions anywhere except a charge amount** — usage pricing (pipeline stage 3), the minimum-bill adjustment, and tax computation (stage 5) stay closed to tenant expressions in this epic; extending there is a separate ruling with a separate risk review (candidate **OQ-097**), because that is the code path GT-1..61 measure · the pricing-model plugin interface itself (EP-RAT-05 / US-RAT-015 — this epic consumes it) · the bill-run pipeline (EP-BIL-01 / BR-BIL-037) · corrections execution (EP-BIL-04 — reused, not rebuilt) · any change to **B4/B5**, which are ❄ finance-signed and out of reach of every rule in this epic (BR-RAT-055 makes that testable) · **custom fields** (EP-TEN-09 / BR-TEN-048 / DB-17), which are a different feature with an absolute money ban and must never be confused with this one · a new screen ID (BR-TEN-047 precedent: a capability that fits an existing settings surface does not mint one).

## The distinction this epic turns on (read before designing anything here)

Three categories that look alike and are not:

| Category | May it drive money? | Shape | Governing rule |
|---|---|---|---|
| **Tenant-configured rating objects** — plans, tariffs, tiers, TOU windows, seasons, charge codes, taxes | **Yes — that is the product.** This is already how a utility configures itself without code | **Parameters** in reviewed tables with validation rules | BR-RAT-012..043, B2 r5 |
| **Tenant-defined custom fields (B2 r17)** | **Never.** Capture, display, search, sort, export only | Arbitrary tenant **keys and values** on non-money entities | BR-TEN-048 · DB-17 · merge-blocking G6 |
| **Tenant-authored FORMULA** (this epic) | Yes in principle — it is rating configuration | An **expression**, not a parameter — a *different risk class*, because its shape is not fixed by a reviewed schema | BR-RAT-046..055; and a formula must **never** be able to reach `custom_data` (BR-RAT-053) |

## What already needs no code — the parameterised catalogue (extraction, not proposal)

Before any new mechanism is built, this is what a business user can already change without a deploy. The governing principle is B4's PO Q&A round 6: *"every utility differs — validation/estimation/fee mechanics ship as TENANT SETTINGS with our derived values as seeded defaults, not hardcoded constants."*

| # | Already tenant-definable, no code | Rule |
|---|---|---|
| 1 | **Plans** as bundles — services, per-service base charge, per-service minimum, plan floor, category targeting, lifecycle | BR-RAT-012/025/027/028/030 |
| 2 | **Seven pricing models** per service: flat · tiered (pure tiers, any number of tiers and prices) · TOU (3 windows × 2 seasons × day-types + tenant holiday calendar) · demand · seasonal · capacity (tenant-named unit + rate) · percent-of-service (sewer % of water) | BR-RAT-019/021/026/034 · B2 r5 #16 |
| 3 | **Charge codes** — any number, per service or Any, with flat / percent / percent-with-minimum amounts, per-plan amount override, recurrence, taxable flag, own GL, auto-apply / waivable / separate-line behaviour | BR-RAT-035/041 · US-RAT-008 |
| 4 | **Discounts** — negative-amount charge rules on the plan (paperless, autopay, senior…) | BR-RAT-043 |
| 5 | **Taxes** — tenant-entered jurisdictions, percent-of-subtotal / flat-per-bill / per-unit forms, marginal "applies above" threshold, per-plan rate override, account-level exemption | BR-RAT-036/042 · BR-TEN-037 |
| 6 | **Deposits** per consumer category | BR-RAT-020/023 |
| 7 | **Penalty rules per plan** — late %, minimum, grace days, grace mode (calendar/business) | B2 r5 #10 · BR-BIL-001/002/008 |
| 8 | **Minimum bill**, both modes — per-service and plan floor | BR-RAT-028 |
| 9 | **Tenant billing settings** — cycle due-days, late %/min/grace, minimum-bill amounts, budget parameters, overcharge-guardrail %, correction-approval threshold, allocation order, numbering format, template set, bill messages/footer, tax authorities | BR-BIL-021 |
| 10 | **Read validation + estimation parameters** — high/low/zero thresholds, days window, trailing-average method, consecutive-estimate cap | B4 PO R6 (OQ-002/OQ-003 closures) |
| 11 | **Billing cycles** and their recurrence, read windows, due-days | BR-MET-009/010 (OQ-094 closure) |
| 12 | **Budget billing** — level basis, drift %, re-level cadence, settle-up month, off-budget trigger, per-account override band | BR-BIL-017 |
| 13 | **Bill format and documents** — standalone vs balance-forward, templates + versions per consumer category, messages | BR-BIL-025/026/035 |
| 14 | **UoM per service** + conversion factor; **holiday calendar** | BR-RAT-038 · BR-RAT-021 |

**The honest gap this leaves.** Only two shapes a small utility commonly needs are *not* expressible above, and both are one expression wide:
- a **cap** on a percent charge — "3% of usage, but never more than $12" (v1 has percent-with-*minimum*, never percent-with-*maximum*; a `charges.max_amount` column is even mapped as PROPOSED-SCHEMA in US-RAT-008 §5 with no rule to apply it);
- a **threshold-and-rate** charge — "$0.85 per kgal above 10 kgal" as a *charge* rather than a tariff tier (BR-RAT-042 already ruled the marginal semantics for the tax equivalent).

Everything else the PO listed as "very common, changes utility to utility" is already a setting. That is the measure of how much of this request needs no new mechanism at all — and the measure of how small the new mechanism should be.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no new list screen and no new screen ID — BR-TEN-047 precedent. Formulas are authored inside S12 step 2 and listed in the S9 Charge codes tab (EP-RAT-03 capability row, Amount column renders the expression); formula versions appear in the S9 **History** view owned by EP-RAT-04 with entity type `formula` added to its existing entity-type filter)* | | | | | | | |

## Stories

---
id: US-RAT-016
epic: EP-RAT-07
module: rating
screens: [S12, S9]
wave: 8
status: draft            # was `blocked`; the ruling arrived 2026-08-10
blocked_by: []           # was [OQ-095]; CLOSED 2026-08-10 (→BR-RAT-046, "YES, enable it"). Cleared 2026-08-15 (DEF-104)
depends_on: [US-RAT-008, US-RAT-015, US-RAT-012, US-RAT-013]
journeys: [J2]
rules: [BR-RAT-041, BR-RAT-046, BR-RAT-047, BR-RAT-048, BR-RAT-049, BR-RAT-053, BR-RAT-055]
golden_tests: [GT-1, GT-2, GT-5, GT-8, GT-10, GT-13]
finance_calc: proposed
---
### US-RAT-016 — The `formula` amount rule: declared variable vocabulary + safe evaluator (S12 step 2)

**1 · Details** — As an Owner/Admin of a utility whose board just adopted a drought surcharge, I want to define the charge myself — pick **Formula** in S12 step 2, compose an expression from a **published list of variables** the system offers me (each with its unit and a one-line meaning), and save it against a charge code — so that a pricing rule that differs from utility to utility does not need a release. Entry: S9 Charge codes → **+ New charge code** → step 2 "How is the amount computed?" → **Formula** (the radio the prototype already draws and BR-RAT-041 disables). Exit: a draft formula on the charge code; it prices nothing until it is tested (US-RAT-018) and published (US-RAT-017).

The mechanism is deliberately small, because it is a 🔒 money path: **a closed vocabulary** (BR-RAT-047 — the author picks names, never types a path), **a closed grammar** (BR-RAT-048 — literals, the listed variables, `+ − × ÷`, parentheses, `min`, `max`; nothing else parses), **`Decimal` end to end** (CLAUDE.md #2), **one evaluation point** in the pipeline after usage/base/minimum and before tax (BR-RAT-049), and **hard failure** on every error — an unbound name, a division by zero or a non-finite result blocks the charge and raises an S31.3 exception rather than quietly producing `0.00`. A formula adds a charge line and can do nothing else: it cannot reach usage pricing, the minimum-bill adjustment or tax (BR-RAT-055), and it cannot reach `custom_data` (BR-RAT-053).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-046 | Adds `formula` as the fourth `charges.amount_rule`, enabling the S12 radio BR-RAT-041 disabled. Everything else in BR-RAT-041 is unchanged. | **PROPOSED — AMENDMENT to a CONFIRMED rule; needs PO ratification (OQ-095)** |
| BR-RAT-041 | Charge amount rules v1 = flat / percent / percent-with-minimum; "Formula" visible but disabled. **Stands until the amendment is ratified** — TC-1 asserts it. | CONFIRMED — PO OQ-053 |
| BR-RAT-047 | Closed, versioned variable allow-list; every name is an existing engine quantity with an explicit unit; an unknown name is a save-time error echoing the token. | PROPOSED — derived per name from BR-RAT-001/012/015/018/022/027/028/032/038, B4.1/B4.3 (contents = OQ-096) |
| BR-RAT-048 | Safe evaluator: closed grammar, function set `{min, max}`, AST stored and walked (source never executed), `Decimal`/NUMERIC(18,6), no I/O, no imports, no `eval`, no clock, no rounding function; every error blocks. | PROPOSED — derived from CLAUDE.md 🔒 + #2/#3 + BR-RAT-003 (B4.4) + hard-won law 3 |
| BR-RAT-049 | One evaluation point (pipeline stage 4, after the minimum adjustment, before tax); no chaining; multiple formulas evaluate in `charges.code` ascending order. | PROPOSED — derived from B4.2 + BR-RAT-005/028 + BR-BIL-037 |
| BR-RAT-053 | A formula cannot reach `custom_data`: positive allow-list, no attribute/index operator in the grammar, G6 ban under `apps/rating/`, resolver provenance test. | PROPOSED — BR-TEN-048 · DB-17 · B2 r17.2 |
| BR-RAT-055 | A formula can only add a charge line; GT-1..61 evaluate identically with the subsystem loaded — proven by running the suite both ways. | PROPOSED — B5 ❄ freeze + BR-RAT-005/041 |
| BR-RAT-005 | *(bound)* fees and charge lines are never in the tax base — a formula amount therefore cannot enter it. | CONFIRMED — B4.2; GT-10 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(negative — the amendment gate)* | S12 step 2, **Formula** selected, with BR-RAT-046 unratified | Continue is blocked exactly as US-RAT-008 TC-8 specifies today ("formula charges pending definition"), now naming OQ-095; no schema write path exists. This TC stays green forever if the PO declines |
| TC-2 | Dana opens the formula editor | A picker lists **only** the allow-list (BR-RAT-047), each entry showing name, unit/currency and a one-line meaning; free-typing `rebate_pct` blocks save with `UNKNOWN_VARIABLE: rebate_pct` |
| TC-3 | Dana saves DROUGHT = `0.85 × max(0, consumption.water − 10)` and it evaluates for ACC-3020 (water 26.24 kgal) | AST + hash stored; evaluation = 0.85 × 16.24 = 13.804 → line **$13.80** at finalization (BR-RAT-003), unit-bearing quantity echoed in the description |
| TC-4 | FRANCH = `min(12.00, 0.03 × usage_amount.total)` on two bills | usage 128.10 → 3.843 → **$3.84**; usage 500.00 → min(12.00, 15.00) = **$12.00** — the cap binds. This is the "percent with maximum" shape the three v1 rules cannot express |
| TC-5 *(negative — grammar)* | Saves attempted: `__import__("os")` · `account.custom_data.ssn` · `tiers[0]` · `x = 1` · `while` · `"text"` · `lambda` | Each fails to **parse**, naming the offending token; no evaluation is attempted and nothing is stored. The grammar has no attribute operator, no index operator, no assignment, no strings, no functions beyond `{min, max}` |
| TC-6 *(negative — arithmetic failure)* | `100 ÷ (days_in_period − 30)` on a 30-day period | Blocks with `DIVIDE_BY_ZERO`; the charge raises an S31.3 exception naming the formula and the account; **no line, and never `0.00`** |
| TC-7 *(negative — precision)* | `0.1 + 0.2` evaluated; and a patch introducing `float` into the evaluator | Result is exactly `0.300000`; the patch fails the type test — NUMERIC(18,6)/`Decimal` only (CLAUDE.md #2) |
| TC-8 *(negative — the hard boundary, BR-TEN-048/DB-17)* | (a) expression names `custom_data.rebate_pct` or `account.custom_data.service_class`; (b) a patch adds `custom_data` to `apps/rating/`; (c) resolver provenance audit | (a) `UNKNOWN_VARIABLE` echoing the token — the name is unreachable, not merely refused; (b) **G6 merge-blocking FAIL** naming BR-TEN-048; (c) every allow-list entry maps to a B2 column or an engine-computed quantity and **none** is sourced from `custom_data` |
| TC-9 *(negative — no second rounding law)* | `round_half_up(consumption.water, 0)` | `UNKNOWN_FUNCTION` naming the closed set `{min, max}`; the line still finalizes half-up 2dp exactly once (BR-RAT-003, B4.4) |
| TC-10 | A bill carries both DROUGHT and FRANCH | Both evaluate in stage 4 **after** the minimum-bill adjustment and **before** tax, in `charges.code` order (DROUGHT then FRANCH); neither joins the taxable base (BR-RAT-005); neither can read the other's amount (no chaining, BR-RAT-049) |
| TC-11 *(GT invariance)* | Full **GT-1..61** run twice: formula subsystem absent, then loaded with DROUGHT + FRANCH published on the tenant | Identical output both times — same lines, same totals, same postings. GT-1/2/5 (usage), GT-8 (late), GT-10/13 (tax base, minimum) are unchanged because a formula can only add a charge line (BR-RAT-055) |
| TC-12 *(negative — determinism)* | Same inputs evaluated twice, in two processes, on two days; then a patch introducing `datetime.now()` / `random` | Byte-identical results; the patch fails the determinism property test (BR-RAT-048) |
| TC-13 *(isolation)* | Lone Star Ridge publishes COOPMIN = `max(8.00, 0.02 × bill_subtotal_pre_tax)` | It prices only Lone Star Ridge bills; Brazos Bend's editor never lists it and its bills never evaluate it; a forged charge id from the other tenant 404s (RLS) |

**4 · Test Data** — **Brazos Bend MUD**, actor Dana Whitfield (Owner/Admin). Charge codes: **DROUGHT** "Drought surcharge" (Water, Recurring, GL 4910) = `0.85 × max(0, consumption.water − 10)` · **FRANCH** "Franchise pass-through" (Any, Recurring, GL 4910) = `min(12.00, 0.03 × usage_amount.total)` · **LATECAP** "Late fee, capped" (Any, Penalty, GL 4200) = `min(25.00, max(5.00, 0.015 × overdue_portion))`. Evaluation fixtures: ACC-3020 water **26.24 kgal** (the US-BIL-002 overcharge fixture) · WE-1 ACC-1042 usage total **128.10** (electric 88.60 + water 39.50) and a 500.00 variant · overdue **542.10** (the GT-8 fixture) and **2,400.00**. Rejected-expression fixtures per TC-5. **Lone Star Ridge Co-op**, actor J. Okafor: COOPMIN = `max(8.00, 0.02 × bill_subtotal_pre_tax)`.
*(Note: GT-8 itself continues to price through the built-in percent-with-minimum rule — LATECAP is a tenant's own charge that happens to reproduce the same arithmetic when its cap does not bind. A formula never becomes the implementation of a golden test, BR-RAT-055.)*

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Amount rule = Formula | S12 step 2 | prototype-extracted (radio, no fields) + BR-RAT-046 | **PROPOSED-SCHEMA** `charges.amount_rule` gains value `formula` (B2 today implies the rule from which of `amount`/`percent`/`min_amount` is filled) | enum | user-input | only when OQ-095 ratified; else blocked (TC-1) |
| Expression source | S12 step 2 | **GAP** — no artefact today (this story creates it) | **PROPOSED-SCHEMA** `charge_formula_versions.expression text NOT NULL` | text | user-input | parses under BR-RAT-048; ≤ a bounded length |
| Parsed AST + hash | — | BR-RAT-048 | **PROPOSED-SCHEMA** `charge_formula_versions.ast jsonb NOT NULL`, `.ast_hash text NOT NULL` | jsonb/text | system-derived | evaluation walks the AST; source never executed |
| Vocabulary version | — | BR-RAT-047 | **PROPOSED-SCHEMA** `charge_formula_versions.vocabulary_version int NOT NULL` | int | system-derived | stamped at save; a later vocabulary change cannot alter an existing formula's meaning |
| Variable allow-list | S12 step 2 (picker) | BR-RAT-047 | **code-only map, no table** — name → (source column or engine quantity, unit) | — | reference-data | provenance test (TC-8c); `custom_data` unreachable |
| Referenced services | S12 step 2 | derived (a `consumption.<service>` name binds a service) | **PROPOSED-SCHEMA** `charge_formula_versions.referenced_names text[]` | text[] | system-derived | must be ⊆ the plan's services at evaluation, else exception (TC-6 pattern) |
| Formula-priced line | S31.2 / bill | BR-RAT-050 | `invoice_lines.amount` + **PROPOSED-SCHEMA** `invoice_lines.formula_version_id uuid NULL` (stamped like `gl_account_id`, DB-8) | numeric(18,6) | system-derived | half-up 2dp at finalization only; `taxable = false` (charge line, BR-RAT-005) |
| Evaluation failure | S31.3 | BR-RAT-048 + billing model §2 | run exception record (no rating write) | — | system-derived | names formula, version, account, error code; blocks the bill for that account |

**6 · Acceptance**
- **Given** the BR-RAT-046 amendment is **not** ratified, **when** an admin picks Formula on S12, **then** Continue is blocked and no formula can be stored — BR-RAT-041 is honoured exactly as written.
- **Given** the amendment is ratified, **when** Dana composes `0.85 × max(0, consumption.water − 10)` from the picker and it evaluates for ACC-3020, **then** the charge line is **$13.80**, the AST and vocabulary version are stored, and the line carries `formula_version_id`.
- **Given** any expression that names an unknown variable, an unknown function, a tenant key, an attribute path, or that divides by zero, **then** it is refused at save or blocks at evaluation with the token named — and no code path returns `0.00` on failure.
- **Given** the full GT-1..61 suite, **then** it produces identical output with and without a published tenant formula in the same process.
- **Given** two tenants, **then** neither can see, list or evaluate the other's formulas.

**7 · Finance Calculation** — **PROPOSED (mechanism unratified — OQ-095; every input quantity is CONFIRMED).**
`amount = eval(AST, bound_variables)` in NUMERIC(18,6), evaluated once at pipeline stage 4 (BR-RAT-049), finalized half-up 2dp exactly once by the caller (BR-RAT-003 / B4.4).
Worked examples: **DROUGHT** — `0.85 × max(0, 26.24 − 10)` = 0.85 × 16.24 = 13.8040 → **$13.80**; at 8.00 kgal → `0.85 × max(0, −2)` = **0.00** (line emission at exactly zero = candidate OQ-101). **FRANCH** — `min(12.00, 0.03 × 128.10)` = min(12.00, 3.8430) = **$3.84**; on 500.00 → min(12.00, 15.00) = **$12.00** (cap binds). **LATECAP** — `min(25.00, max(5.00, 0.015 × 542.10))` = min(25.00, 8.1315) = **$8.13**; on 2,400.00 → min(25.00, 36.00) = **$25.00**.
**GT ref: none, and that is the point** — by BR-RAT-055 no formula charge appears in GT-1..61, so no signed figure moves. The suite is run *around* this feature (TC-11), never *through* it.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-095 *(candidate — not yet in the registry)* | **Amend BR-RAT-041 to enable the "Formula" charge amount rule?** BR-RAT-041 is CONFIRMED (PO OQ-053) with Formula *visible but disabled*; the PO's 2026-08-10 request ("let business users define calculation rules without code changes") is answered by exactly that switch, so enabling it contradicts a confirmed rule and needs an explicit amendment ruling. Also needed: wave placement (derived proposal **W8**, v1.1 unlock per B12 r3) | **All of EP-RAT-07** (US-RAT-016..019) and BR-RAT-046..055 | Product Owner (chat session) | **OPEN** |
| OQ-096 *(candidate)* | **What exactly may a formula name — the variable vocabulary and the function set?** (a) Is the BR-RAT-047 list of 13 variable families right, too wide, or missing something a real tenant needs? (b) Does the PO want **conditionals** (if/then) in v1? They are excluded here because they double the test surface and invite tier logic the tariff models already own. (c) **A pre-existing gap this makes load-bearing:** BR-RAT-041's `percent` rule never says which subtotal it takes a percent of (US-RAT-008 §7 says "percent × base_amount" and never defines `base_amount`); `bill_subtotal_pre_tax` must be defined before either the percent rule or a formula that names it is trustworthy | The resolver allow-list, the S12 variable picker — **and the existing `percent` amount rule's basis** | Product Owner (chat session) | **OPEN** |
| OQ-097 *(candidate)* | **Does "business-user-definable calculation rules" stop at charge amounts?** The extension point that exists (BR-RAT-041) is a charge **amount** rule — it can add a charge line and nothing else. The PO's words could also mean usage pricing (pipeline stage 3) or tax (stage 5). Extending there puts a tenant expression inside the exact code path GT-1..61 measure, which BR-RAT-055 currently guarantees is untouched. Recommendation: v1.1 = charge amounts only; anything wider is a separate ruling with its own risk review | EP-RAT-07's scope boundary and BR-RAT-055's structural guarantee | Product Owner (chat session) | **OPEN** |
| OQ-100 *(candidate)* | **Are formula variables unit-tagged, and does the evaluator reject unit-incoherent expressions?** CLAUDE.md #3 requires consumption to carry an explicit unit and BR-RAT-038 gates UoM at rating input, but nothing stops an author writing `consumption.water + prior_balance` (kgal + USD). Options: (a) tag every variable with unit/currency and reject incoherent operations at save; (b) currency-only checking; (c) no checking, author's responsibility. Only (a) fails closed (hard-won law 3) | The validator's strength; the picker's ability to warn before save | Product Owner (chat session) | **OPEN** |
| OQ-101 *(candidate)* | **Does a formula evaluating to exactly 0 emit a `$0.00` line or no line?** No rule in A19/BR-BIL/BR-RAT covers zero-amount invoice lines. Emitting is honest but noisy on a customer document; suppressing is cleaner but makes a mis-authored formula invisible. Proposal offered, not taken: suppress the line, record the evaluation on the run so it is visible to staff | The line-emission branch in US-RAT-016 §7 and the S31.2 preview count | Product Owner (chat session) | **OPEN** |

---
id: US-RAT-017
epic: EP-RAT-07
module: rating
screens: [S12, S9]
wave: 8
status: draft            # was `blocked`; the ruling arrived 2026-08-10
blocked_by: []           # was [OQ-095]; CLOSED 2026-08-10 (→BR-RAT-046, "YES, enable it"). Cleared 2026-08-15 (DEF-104)
depends_on: [US-RAT-016, US-RAT-010]
journeys: [J2]
rules: [BR-RAT-007, BR-RAT-017, BR-RAT-037, BR-RAT-050, BR-RAT-052]
golden_tests: []
finance_calc: none
---
### US-RAT-017 — A formula versions like a tariff: publish, stamp, never re-price history, audit every write

**1 · Details** — As an Owner/Admin, I want a formula to behave exactly like a rate change, because that is what it is: **publishing** writes an immutable version row with an effective window; **editing** a published formula creates a new version and closes the old one the day before, never an in-place update (BR-RAT-037 discipline, B2's non-overlap EXCLUDE precedent); every invoice line the formula prices **stamps `formula_version_id`**, the same move the schema already makes for `gl_account_id` (DB-8) and `template_id` (DB-9); and an issued bill is never re-priced when the formula changes (BR-BIL-004/030, BR-RAT-007). So that a bill can always answer "which rule produced this number?", the answer survives seven years (BR-RAT-017), and the compliance trail is the **same** trail as rate changes — the S9 History view with entity type `formula` (EP-RAT-04), not a second one. Every create, edit, publish, supersede, suspend and test-run writes `audit_log` with a required reason on publish/supersede/suspend (BR-RAT-052, CLAUDE.md #7). Entry: S12 step 3 Review & save → Publish; S9 → History. Exit: a published version priced against from its effective date forward.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-050 | Publish writes an immutable version with an effective window; windows never overlap; in-force versions are never edited in place; lines stamp `formula_version_id`; a formula change never re-prices an issued bill or history. | PROPOSED — derived from BR-RAT-037 + BR-RAT-007/017 + BR-BIL-004/030 + DB-8/DB-9 |
| BR-RAT-037 | *(shared)* every change = a new version row + an append-only log row with before/after, actor and **required reason**. | CONFIRMED — PO R5-9 |
| BR-RAT-007 | Historical bills reprice against the version in force on the **service date** — for formulas exactly as for tariffs. | CONFIRMED (schema) — A8 §Versioning |
| BR-RAT-017 | 7-year reproducibility applies to formula versions identically. | CONFIRMED — PO Q&A R1 Q12 |
| BR-RAT-052 | Every formula write is audited with source, AST hash, vocabulary version, actor; reason required on publish / supersede / suspend. | PROPOSED — CLAUDE.md #7 + BR-RAT-037 |
| BR-BIL-030 | *(bound)* the bill is locked at issue — a later formula edit cannot change what an issued bill says or shows. | CONFIRMED — PO 2026-08-10 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana publishes DROUGHT v1 effective Jun 1, 2026, reason "Board drought order 2026-05" | `charge_formula_versions` row v1 (effective_from Jun 1, effective_to NULL), status published; History row entity `formula`, before → after, reason, actor; `audit_log` `rating.formula.published` |
| TC-2 | Dana changes the threshold 10 → 8 effective Sep 1, 2026, reason "Stage 3 restriction" | v1 gets effective_to Aug 31; **v2** opens Sep 1 with its own AST/hash; v1's row is byte-unchanged; both resolvable |
| TC-3 | A July bill priced under v1; a September bill priced under v2 | July line stamps v1's `formula_version_id` and re-renders forever as $13.80; September prices on v2 — the service date selects the version (BR-RAT-007), never "the current formula" |
| TC-4 | Reprint of the July bill after v2 exists | Identical to the original — the document renders from the stamped payload (BR-BIL-030) and the line still names v1 |
| TC-5 *(negative)* | Publish attempted with effective_from Aug 15 while v1's window is still open-ended | Refused by the non-overlap constraint with the inline message "windows may not overlap — close the current version first" (the BR-RAT-037/US-RAT-010 TC-5 pattern) |
| TC-6 *(negative)* | API `UPDATE` on published v1's `expression` / `ast` | Rejected — published versions are immutable; corrections are new versions (BR-RAT-037); the attempt is audited |
| TC-7 *(negative)* | Publish submitted with the reason blank | Blocked: "reason is required for every rate change" (BR-RAT-037 / `rate_change_log.reason NOT NULL`); nothing written |
| TC-8 *(negative)* | A formula version referenced by ≥ 1 issued invoice line, then deleted | Audit-locked (IS-1 pattern, and BR-BIL-027's precedent for pinned template versions): deactivate/supersede only, delete never |
| TC-9 | Seven-year drill: resolve a 2019-dated service date against its formula version | Version, AST and vocabulary version all still resolvable; the stored AST — not a re-parse of the source under today's grammar — is what evaluates (BR-RAT-017/050) |
| TC-10 *(isolation)* | Lone Star Ridge publishes and supersedes COOPMIN | Its versions and History rows are invisible to Brazos Bend under every filter permutation; a Brazos Bend version id in its request 404s (RLS) |

**4 · Test Data** — Brazos Bend DROUGHT: **v1** `0.85 × max(0, consumption.water − 10)` effective 2026-06-01, reason "Board drought order 2026-05", published by Dana Whitfield; **v2** `0.85 × max(0, consumption.water − 8)` effective 2026-09-01, reason "Stage 3 restriction". Bills: ACC-3020 July 2026 (v1, line $13.80) and September 2026 (v2, `0.85 × max(0, 26.24 − 8)` = 0.85 × 18.24 = 15.504 → **$15.50**). Overlap fixture: attempted effective_from 2026-08-15. Seven-year drill: service date 2019-08-15. Lone Star Ridge: COOPMIN v1 effective 2026-07-01, superseded 2026-10-01.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Formula header (charge, name, status) | S12 / S9 | **GAP** — created by this epic | **PROPOSED-SCHEMA** `charge_formulas` (tenant_id, charge_id, name, status draft\|published\|suspended\|superseded) | rows | user-input | one active formula per charge code |
| Version + effective window | S12 step 3 | BR-RAT-050 (BR-RAT-037 pattern) | **PROPOSED-SCHEMA** `charge_formula_versions.version`, `.effective_from`, `.effective_to` + non-overlap EXCLUDE | int/date | user-input | windows never overlap (TC-5) |
| Reason | publish flow | BR-RAT-037 / B2 r5 #14 | `rate_change_log.reason` (NOT NULL) with `entity = formula` | text | user-input | required on publish / supersede / suspend |
| Before/after diff | S9 History | B2 r5 #14 | `rate_change_log.entity` + before/after jsonb (expression + AST hash) + actor | jsonb | system-derived | append-only |
| Published-by / at | S12 step 3 | BR-RAT-052 | **PROPOSED-SCHEMA** `charge_formula_versions.published_by`, `.published_at` | uuid/ts | system-derived | A4 Plans & Rates write permission (second-person approval = OQ-098) |
| Line stamp | bill detail (S30) | BR-RAT-050 · DB-8/DB-9 precedent | **PROPOSED-SCHEMA** `invoice_lines.formula_version_id uuid NULL` | uuid | system-derived | frozen at issue; never re-mapped |
| In-force selection | — | BR-RAT-007 | window join on `invoices.service_date` (the `ix_tariff_versions_lookup` pattern) | — | system-derived | never "the current formula" |
| Audit | — | CLAUDE.md #7 + BR-RAT-052 | `audit_log` `rating.formula.created` / `.published` / `.superseded` / `.suspended` / `.tested` | jsonb | system-derived | append-only |

**6 · Acceptance**
- **Given** a published formula, **when** it is changed, **then** a new version opens, the old one closes the day before, neither overlaps, and the old row is byte-unchanged.
- **Given** bills issued under two versions, **then** each line names the version that priced it and a reprint of the older bill is identical to its original.
- **Given** a blank reason, an overlapping window, an in-place update, or a delete of a referenced version, **then** each is refused with the stated message and audited.
- **Given** a seven-year-old service date, **then** its formula version and stored AST are still resolvable.
- **Given** two tenants, **then** version chains and History rows never cross.

**7 · Finance Calculation** — N/A (version selection and stamping, not arithmetic; the priced example is US-RAT-016 §7. The one arithmetic figure used here is the v2 fixture, `0.85 × max(0, 26.24 − 8)` = **$15.50**, which exists only to show that a version change prices *forward* and never re-prices July's $13.80).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-095 *(candidate — see US-RAT-016 §8)* | The BR-RAT-041 amendment. | This whole story | Product Owner (chat session) | **OPEN** |
| OQ-098 *(candidate)* | **Who publishes a formula, and does it need a second person?** A4 already makes Plans & Rates writes Admin-only (US-RAT-011 TC-7), so authoring/publishing **derives** to System Admin. What is *not* determined: whether publishing a money-affecting **expression** needs a second-person approval like corrections do (BR-BIL-014: v1 = ALL corrections require System Admin approval), or whether a single admin publishing alone is acceptable for a 1–2-staff utility — the same tension BR-RAT-031 resolved for rate schedules by moving board approval **outside** the system | Whether `charge_formula_versions` needs an `approved_by` column and an awaiting-approval state | Product Owner (chat session) | **OPEN** |

---
id: US-RAT-018
epic: EP-RAT-07
module: rating
screens: [S12]
wave: 8
status: draft            # was `blocked`; the ruling arrived 2026-08-10
blocked_by: []           # was [OQ-095]; CLOSED 2026-08-10 (→BR-RAT-046, "YES, enable it"). Cleared 2026-08-15 (DEF-104)
depends_on: [US-RAT-016, US-RAT-017]
journeys: [J2]
rules: [BR-RAT-048, BR-RAT-051, BR-RAT-052]
golden_tests: []
finance_calc: proposed
---
### US-RAT-018 — Test before publish: sample inputs, the stored result, and a diff on every later version

**1 · Details** — As an Owner/Admin about to make a rule that touches every customer's bill, I want to **try it before it is real**: the editor asks me for a sample value for each variable my expression uses, evaluates it in front of me, and refuses to publish until it has evaluated cleanly (BR-RAT-051). The passing sample set, its result, who ran it and when are stored **on the version row**, so "what did we test?" is answerable years later — and because they are stored, they re-run automatically against every later version of the same formula and any changed result is shown as a **diff I must acknowledge** before publishing. So that the failure mode this feature could otherwise introduce — a rule that silently mis-prices 1,124 bills — is caught by the author, at the desk, before anything issues. A formula that has never been evaluated cannot be published, and the gate is **server-side**, not a UI courtesy. Entry: S12 step 2, "Test this formula" panel beneath the expression. Exit: a tested draft that Publish (US-RAT-017) will accept.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-051 | Publish is refused until every referenced variable has a sample value and every sample evaluates without error; the passing set + result + actor + timestamp are stored on the version; stored samples re-run on later versions and a changed result is shown as a diff before publish. | PROPOSED — derived from IS-6 (confirm before a money action) + PO requirement 2026-08-10 + hard-won law 7 (regression-set scope = OQ-099) |
| BR-RAT-048 | *(shared)* every evaluation error blocks with a named code — the test panel surfaces exactly what the bill run would do. | PROPOSED |
| BR-RAT-052 | *(shared)* a test run is audited like any other formula write. | PROPOSED — CLAUDE.md #7 |
| IS-6 *(cited)* | Confirm-before-money-action pattern: the preview a user must see before an irreversible step. | CONFIRMED — A9 interaction standards |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana writes DROUGHT and opens the test panel | The panel asks for exactly the referenced variables — `consumption.water` — with its unit (kgal) shown; unreferenced vocabulary is not asked for |
| TC-2 | Sample `consumption.water = 26.24` | Result **13.804 → $13.80 at finalization** is displayed with the arithmetic shown step by step (`26.24 − 10 = 16.24`; `max(0, 16.24) = 16.24`; `× 0.85 = 13.8040`) |
| TC-3 | Dana adds boundary samples 10.00 and 8.00 kgal | Results **0.00** and **0.00** — the author sees the threshold behave before a customer does (line-emission at exactly zero = OQ-101) |
| TC-4 *(negative)* | Publish attempted with no sample set | Refused: "test this formula before publishing" — and the refusal is **server-side**, so a direct API publish is refused identically (TC-8) |
| TC-5 *(negative)* | Sample set where `days_in_period = 30` against `100 ÷ (days_in_period − 30)` | The test panel shows `DIVIDE_BY_ZERO` at the desk; publish stays blocked; the author fixes it before any bill run meets it |
| TC-6 | Dana edits DROUGHT to v2 (threshold 8) and re-publishes | The three stored samples re-run automatically: 26.24 → **15.50** (was 13.80), 10.00 → **1.70** (was 0.00), 8.00 → **0.00** (unchanged); the diff is displayed and must be acknowledged with the publish reason before v2 goes live |
| TC-7 *(negative)* | A stored sample names a variable v2 no longer references | Flagged as stale rather than silently dropped; the author confirms removal — a shrinking test set is never invisible |
| TC-8 *(negative)* | `POST` publish with a forged `tested: true` flag / bypassing the panel | Refused — the gate reads the stored version row, not the request; no client-supplied field can satisfy it |
| TC-9 *(isolation)* | J. Okafor tests COOPMIN with Lone Star Ridge samples | Samples, results and audit rows belong to Lone Star Ridge only; a Brazos Bend formula id in the test request 404s (RLS) |

**4 · Test Data** — DROUGHT v1 sample set: `consumption.water` = **26.24** (→ 13.80), **10.00** (→ 0.00), **8.00** (→ 0.00), stored 2026-05-28 by Dana Whitfield. v2 (threshold 8) re-run: 26.24 → **15.50**, 10.00 → `0.85 × max(0, 2) = 1.70`, 8.00 → **0.00**. FRANCH sample set: `usage_amount.total` = **128.10** (→ 3.84) and **500.00** (→ 12.00, cap binds). Error fixture per TC-5. Lone Star Ridge: COOPMIN sample `bill_subtotal_pre_tax` = **300.00** → `max(8.00, 6.00)` = **8.00**.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Sample input set | S12 step 2 test panel | BR-RAT-051 | **PROPOSED-SCHEMA** `charge_formula_versions.sample_inputs jsonb NOT NULL DEFAULT '{}'` | jsonb (name → numeric) | user-input | one value per referenced variable; numeric only |
| Sample result(s) | S12 step 2 test panel | BR-RAT-051 | **PROPOSED-SCHEMA** `charge_formula_versions.sample_results jsonb` | jsonb (inputs → numeric(18,6)) | system-derived | recomputed, never client-supplied (TC-8) |
| Tested by / at | S12 step 2 | BR-RAT-051 | **PROPOSED-SCHEMA** `charge_formula_versions.tested_by`, `.tested_at` | uuid/ts | system-derived | publish gate reads these (TC-4/TC-8) |
| Step-by-step trace | S12 step 2 | derived (A18 explain-the-number pattern; IS-6 preview) | not persisted — rendered from the AST walk | — | computed-display | shows the same arithmetic the run will do |
| Version diff | S12 step 3 | BR-RAT-051 | computed: stored samples × previous result vs new result | — | computed-display | must be acknowledged before publish |
| Test-run audit | — | BR-RAT-052 · CLAUDE.md #7 | `audit_log` `rating.formula.tested` (inputs, results, actor) | jsonb | system-derived | append-only |

**6 · Acceptance**
- **Given** a draft formula, **when** the author opens the test panel, **then** exactly the referenced variables are requested with their units, and the result is shown with its arithmetic.
- **Given** no stored passing sample set, **then** publish is refused — through the UI and through the API alike.
- **Given** a later version, **then** the stored samples re-run and every changed result is shown as a diff the author must acknowledge.
- **Given** an erroring sample or a stale sample variable, **then** the author is told at the desk, not by a customer.
- **Given** two tenants, **then** sample sets and results never cross.

**7 · Finance Calculation** — **PROPOSED (rides OQ-095; arithmetic is the evaluator's, BR-RAT-048).**
`sample_result = round_half_up(eval(AST, sample_inputs), 2)` — shown at 2dp exactly as a line would finalize (BR-RAT-003), with the unrounded NUMERIC(18,6) value stored.
Worked: DROUGHT v1 at 26.24 kgal → `26.24 − 10 = 16.24` → `max(0, 16.24) = 16.24` → `× 0.85 = 13.8040` → **$13.80**. At 10.00 → `max(0, 0) = 0` → **$0.00**. v2 (threshold 8) at 26.24 → `× 18.24 = 15.5040` → **$15.50**, and the diff against v1 (**+1.70**) is what the author must acknowledge. FRANCH at 500.00 → `min(12.00, 15.00)` = **$12.00**. **GT ref: none** — no golden fixture contains a formula charge (BR-RAT-055).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-095 *(candidate — see US-RAT-016 §8)* | The BR-RAT-041 amendment. | This whole story | Product Owner (chat session) | **OPEN** |
| OQ-099 *(candidate)* | **Are stored samples a one-time pre-publish check or a permanent regression set?** BR-RAT-051 proposes the stronger form — stored samples re-run against every later version with a diff to acknowledge (TC-6). That is materially safer and materially more work. Also unresolved: a **minimum count or coverage** requirement — one sample? one per referenced variable? at least one boundary case, which is where the DROUGHT threshold bug would hide? | The strength of the publish gate and the shape of `sample_inputs` | Product Owner (chat session) | **OPEN** |
| OQ-101 *(candidate — see US-RAT-016 §8)* | Zero-result line emission (TC-3 shows the author two zeros; whether a `$0.00` line reaches the bill is unruled). | The test panel's "what the customer will see" preview | Product Owner (chat session) | **OPEN** |

---
id: US-RAT-019
epic: EP-RAT-07
module: rating
screens: [S9, S31.3]
wave: 8
status: draft            # was `blocked`; the ruling arrived 2026-08-10
blocked_by: []           # was [OQ-095]; CLOSED 2026-08-10 (→BR-RAT-046, "YES, enable it"). Cleared 2026-08-15 (DEF-104)
depends_on: [US-RAT-016, US-RAT-017, US-BIL-015, US-BIL-016, US-BIL-017]
journeys: [J2, J6]
rules: [BR-RAT-050, BR-RAT-053, BR-RAT-054, BR-RAT-055, BR-BIL-004, BR-BIL-014, BR-BIL-030]
golden_tests: [GT-1, GT-2, GT-5, GT-10, GT-13]
finance_calc: confirmed
---
### US-RAT-019 — Blast radius: a published formula found wrong after bills have issued

**1 · Details** — As a System Admin who has just discovered that the drought surcharge published in June has been over-charging every water customer since, I want the recovery path to be one I already know, and I want it to name every affected bill exactly. So: (1) **suspend** the formula, and the next run raises an S31.3 exception for that charge on every affected account rather than repeating the error — never a silent skip (billing model §2); (2) **supersede** it with a corrected version and a reason — the wrong version is never edited (BR-RAT-037); (3) **the issued bills are not re-priced** — a bill is locked at issue (BR-BIL-004/030) and corrections are new rows (CLAUDE.md #4); (4) repair runs through the **existing** approval-gated correction workflow, single or bulk by run/cycle/plan/service/date-range, with impact preview and System-Admin approval (BR-BIL-014) — this epic adds **no new repair path**; (5) the impacted set is **derived, not guessed**, because every affected line stamps `formula_version_id` (BR-RAT-050): the query is "lines where `formula_version_id` = the bad version". Entry: S9 charge code → Suspend / New version; then S30 → Corrections (EP-BIL-04). Exit: corrected bills, an audited trail, and a formula that cannot repeat the error.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-054 | Wrong-after-issue path: suspend → supersede (never edit) → issued bills untouched → repair via the ratified correction workflow → impacted set derived from the stamped `formula_version_id`. | PROPOSED — derived from BR-RAT-037 + BR-BIL-004/014/030 + billing model §2 |
| BR-BIL-004 | Issued invoices and lines are immutable; corrections are new rows (credit note / rebill). | CONFIRMED — B2 §billing, CLAUDE.md #4 |
| BR-BIL-030 | The bill is locked at issue — the stamped instance is what a reprint renders, so a later formula change cannot alter what a historical bill *looks* like either. | CONFIRMED — PO 2026-08-10 |
| BR-BIL-014 | Corrections are an approval-gated workflow, single or BULK by scope, with impact preview, System-Admin approval and staged idempotent execution; **no money-bearing write before approval**. | CONFIRMED — PO A-5, 2026-08-08 |
| BR-RAT-050 | Every formula-priced line stamps `formula_version_id`, which is what makes the impacted set exact. | PROPOSED |
| BR-RAT-055 | A formula can only add a charge line — so a wrong formula can never have corrupted usage, minimum or tax computation on those same bills. | PROPOSED — B5 ❄ freeze + BR-RAT-005/041 |
| BR-RAT-053 | *(bound)* nothing in the recovery path may reach `custom_data`; the correction preview reads stamped lines, not master data. | PROPOSED — BR-TEN-048 · DB-17 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | DROUGHT v1 published without the `max(0, …)` guard — `0.85 × consumption.water` — has priced 412 issued bills; the error is found Aug 9 | Impacted set = `invoice_lines WHERE formula_version_id = v1` → exactly **412 lines**, listed with account, bill, amount charged and amount that should have been charged; the count is derived, never estimated |
| TC-2 | Admin suspends DROUGHT | Status `suspended` with a required reason + audit; the next run does **not** price it and raises an S31.3 exception naming the formula for each affected account — never a silent skip |
| TC-3 | Admin publishes v2 with the guard restored, effective Aug 1, reason "missing floor guard — DEF" | v1 closes Jul 31 and is byte-unchanged; v2 prices forward only; July's bills keep v1's stamp forever (BR-RAT-007/050) |
| TC-4 | Repair: bulk correction scoped to cycle 07-A + charge DROUGHT | The **existing** BR-BIL-014 workflow runs: reason code → scope → impact preview (credit notes, GL reversals, balance deltas, re-allocation plan) → System-Admin approval → staged idempotent execution; no money-bearing write happens before approval |
| TC-5 *(negative)* | An "auto-reprice issued bills" action is looked for anywhere in the product | It does not exist. Issued bills are immutable (BR-BIL-004) and locked at issue (BR-BIL-030); the only path is a correction, which is a new document |
| TC-6 *(negative — the hard boundary under stress)* | The correction impact preview is built for 412 bills; a patch tries to enrich it by joining live account master data / `custom_data` | Preview reads the **stamped** lines and `bill_payload` only (BR-BIL-030); the `custom_data` join fails G6 under `apps/rating/` absolutely and under `apps/billing/` outside `custom_snapshot.py` (BR-TEN-048 / DB-17) |
| TC-7 *(GT invariance under failure)* | Full **GT-1..61** re-run while v1 is suspended and v2 published | Identical to the baseline — a broken, suspended, or superseded tenant formula cannot move a signed figure, because no golden fixture routes through a formula (BR-RAT-055) |
| TC-8 *(negative)* | An admin edits v1's expression "to fix it quickly" | Rejected — published versions are immutable; the attempt is audited and the UI offers New version instead (BR-RAT-037) |
| TC-9 *(isolation)* | Lone Star Ridge's COOPMIN is also wrong in the same week | Its impacted set, suspension, supersede and corrections touch only Lone Star Ridge rows; the two remediation batches never see each other (RLS) |

**4 · Test Data** — Brazos Bend: **DROUGHT v1 (defective)** = `0.85 × consumption.water`, effective 2026-06-01, priced into cycles 06-A and 07-A → **412 issued invoice lines**. Representative account **ACC-3020** (water 26.24 kgal): charged `0.85 × 26.24` = 22.304 → **$22.30**, correct amount `0.85 × max(0, 26.24 − 10)` = **$13.80**, per-bill delta **$8.50** credit. **v2 (corrected)** effective 2026-08-01, reason "missing floor guard". Correction batch: cycle 07-A + charge DROUGHT, reason code "Billing error — rate rule", approver Alex Reed (System Admin), executed 2026-08-12; the batch total is the correction preview's sum of per-bill deltas (BR-BIL-014), computed from stamped lines — not from a formula re-run. Lone Star Ridge: COOPMIN v1 defective, 37 lines, own batch.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Impacted-line query | S9 → impact list; S30 corrections scope | BR-RAT-050/054 | `invoice_lines WHERE formula_version_id = :version` (**PROPOSED-SCHEMA** column) | rows | system-derived | exact set; indexed on `formula_version_id` |
| Suspend action + reason | S9 charge code | BR-RAT-054 / BR-RAT-052 | **PROPOSED-SCHEMA** `charge_formulas.status = suspended` + `audit_log` `rating.formula.suspended` | enum/jsonb | user-input | reason required |
| Suspended-formula exception | S31.3 | billing model §2 + BR-RAT-054 | run exception record (no rating write) | — | system-derived | one per affected account; blocks silent skip |
| Corrected version | S12 step 3 | BR-RAT-037/050 | new `charge_formula_versions` row (**PROPOSED-SCHEMA**) | rows | user-input | non-overlapping window; reason required |
| Correction batch | S30 corrections | BR-BIL-014 | existing corrections tables (EP-BIL-04) — **reused, nothing new** | rows | user-input | approval before any money-bearing write |
| Credit note / rebill lines | S30 | BR-BIL-004/014 | new `invoices` + `invoice_lines` rows (append-only) | rows | system-derived | originals untouched |
| Impact preview totals | S30 corrections | BR-BIL-014 | computed from stamped lines + `bill_payload` (BR-BIL-030) | numeric(18,6) | computed-display | never joins live master data (TC-6) |

**6 · Acceptance**
- **Given** a defective published formula, **when** the admin asks "which bills did this touch?", **then** the answer is an exact list derived from `formula_version_id` — 412 lines in the fixture — not an estimate.
- **Given** suspension, **then** the next run refuses that charge with a named exception per account and never repeats the error, and never silently omits it either.
- **Given** the corrected version, **then** it prices forward only and the issued bills are untouched, byte-for-byte, including what a reprint renders.
- **Given** the repair, **then** it runs entirely inside the ratified BR-BIL-014 correction workflow with approval before any money-bearing write — no new repair mechanism exists.
- **Given** the full golden suite during and after the incident, **then** every GT-1..61 figure is unchanged.

**7 · Finance Calculation** — **CONFIRMED for the correction mechanics (BR-BIL-014 / WE-9 path); the defective/corrected amounts are the evaluator's (BR-RAT-048).**
`per-bill delta = charged_amount − corrected_amount`, credited as a new document (never an edit): ACC-3020 charged `0.85 × 26.24` = 22.3040 → **$22.30**; corrected `0.85 × max(0, 26.24 − 10)` = 13.8040 → **$13.80**; delta **$8.50** credit. Batch total = Σ per-bill deltas over the 412 impacted lines, computed by the BR-BIL-014 impact preview from **stamped** line amounts — this story states the method, not a number it cannot source. Tax is not restated: a formula charge was never in the tax base (BR-RAT-005), so no tax line is affected and GT-10's math is untouched. **GT refs: GT-1, GT-2, GT-5, GT-10, GT-13** — cited as the invariance check of TC-7, not as fixtures this story computes.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-095 *(candidate — see US-RAT-016 §8)* | The BR-RAT-041 amendment. | This whole story | Product Owner (chat session) | **OPEN** |
| OQ-097 *(candidate — see US-RAT-016 §8)* | Whether formulas ever extend beyond charge amounts. If they do, this story's blast-radius argument changes materially: a wrong formula inside usage pricing or tax would corrupt the same figures GT-1..61 pin, and TC-7 could no longer be green by construction. | The scope of BR-RAT-054/055 | Product Owner (chat session) | **OPEN** |
