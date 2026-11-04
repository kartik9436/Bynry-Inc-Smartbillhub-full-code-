# J76 — Charge codes: add, view and edit a base, a plan and an other code; a late fee by customer class; a fee entered when used

---
id: J76
tier: 2
rules: [BR-RAT-1048, BR-RAT-1049, BR-RAT-1050, BR-RAT-1051, BR-RAT-1052, BR-RAT-1053, BR-RAT-1054, BR-BIL-001, BR-BIL-020, BR-RAT-1011]
stories: [US-RAT-008]
change: CR-156-BRC10 (waves A, B, C)
depends_on_journeys: []
# WALKED 2026-10-01 at 1440 on PostgreSQL 16, build 2.435.x — spec
# `07-frontend/e2e/CR-156-charge-codes-wave-c.spec.ts` (all 83 states) and
# `07-frontend/e2e/CR-156-charge-codes-wave-b.spec.ts` (the dated-and-kept edit
# per kind). Shots: `08-qa/screens/charge-codes-waveC-2026-10-01/` with the
# comparison table in its README.
---

**Intent.** A clerk at a utility configures its charge codes on Plans & Rates › Charge codes. The codes
come from Settings (code and name only); this screen says what each one IS (base · plan · other), how it
bills, and what it costs FROM A DATE. Nothing saved is ever deleted: a changed price is closed the day
before the new one starts and kept.

**The PO's rulings it walks** — decision log rows whose last column reads *"charge-code redesign"*
(2026-10-01) and the GO on the 83-image build; CR-010 A2 (2026-08-17) for *entered per case*.

## What upstream leaves (handoff in)

* A tenant with its Settings charge codes minted (`charges` rows with code and name), its services enabled,
  each service's size classes (`service_size_classes`) and at least one rate schedule per metered service.
* For the late fee: a plan whose *late-fee charge code* names the code (BR-RAT-1011).
* For the fee bill: an account (any status) the One-time bill can raise a fee on, and a GL account on the code.

## Steps

1. **List** (images 01–05): Kind and Priced by columns, kind chips with counts, a search with no results.
2. **Add a base** (43, 51–57, 65): pick *Base charge*, the service, a free code; step 2 starts with one row
   per size of the service, in size order, and the schedules' minimum per size beside each where any
   schedule floors one (DEF-RAT-8752); Review; *Pick a date.* without Effective from (71); saved (72).
3. **Add a plan code** (44–47, 58–62, 66–68): one amount, by size, by customer class, a deposit by class,
   and **a penalty by customer class** — Residential **1.50% minimum $5.00**, Commercial **2.00% minimum
   $10.00** (46, 61, 67). The API then serves both classes' terms (`class_terms`).
4. **Add an other code** (48, 63–64, 69–70): one amount, and **entered when used** — no price is stored,
   `amount_rule = per_case` (64, 70).
5. **View details** (06–42): tiles and the scheduled band above the tabs; Overview · Prices · Plans · Audit
   (Other hides Plans); Prices by kind; Plans tab *Plan · Customer class · Accounts*; Audit lists versions.
6. **Edit** (73–83): a base size repriced from a future date; LATE's Commercial percent 2.00% → 2.50% from a
   future date (76–78) — the 2.00% row is kept and closed the day before, Residential untouched; an other
   code repriced; the reason refusal for a code in use (82); saved (83).
7. **Charge it** — the One-time bill's fee kind on a `per_case` code: an *Amount* box appears; the preview
   carries the entered **$1,250.00** on the fee and on the bill.

## What it leaves (handoff out)

* Dated, logically-killed price rows (`charge_code_amounts`) — amounts and per-class terms — read by every
  bill through `charge_prices.price_on_date` / `class_terms_on`.
* Late fees by class: `assess_late_fee_for_plan(…, customer_class=)` — Residential $200.00 overdue →
  **$5.00**, Commercial $2,000.00 → **$40.00** (tested on PostgreSQL 16 in
  `06-backend/tests/test_def_rat_8753_class_terms_and_per_case.py`; GT-8's $8.13 unchanged).

## Not covered here, named

* The deposit *Held* tile (image 26) — no read of deposits held by code (`DEF-RAT-8821`).
* *Save draft* and *Duplicate* are drawn disabled with their reasons (decision log, wave B (9)).
