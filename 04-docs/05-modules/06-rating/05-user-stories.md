# rating (Plans & Rates) — User Stories (INDEX)

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-RAT-001 | Plans list tab | [EP-RAT-01-plans.md](06-epics/EP-RAT-01-plans.md) | draft | W1 |
| US-RAT-002 | New Plan guided wizard (identity → services & schedules → per-service bases → plan rules → review/publish) | [EP-RAT-01-plans.md](06-epics/EP-RAT-01-plans.md) | draft | W1 |
| US-RAT-003 | Plan lifecycle, versioning & category targeting maintenance | [EP-RAT-01-plans.md](06-epics/EP-RAT-01-plans.md) | draft | W1 |
| US-RAT-004 | Rate schedules list tab (cards with structure preview) | [EP-RAT-02-rate-schedules.md](06-epics/EP-RAT-02-rate-schedules.md) | draft | W1 |
| US-RAT-005 | New Rate wizard: basics, flat & tiered (pure tiers) structures | [EP-RAT-02-rate-schedules.md](06-epics/EP-RAT-02-rate-schedules.md) | draft | W1 |
| US-RAT-006 | New Rate wizard: TOU Option B (windows × seasons × day-types + holiday calendar) | [EP-RAT-02-rate-schedules.md](06-epics/EP-RAT-02-rate-schedules.md) | draft | W1 |
| US-RAT-007 | New Rate wizard: demand, seasonal, capacity & %-of-water structures | [EP-RAT-02-rate-schedules.md](06-epics/EP-RAT-02-rate-schedules.md) | draft | W1 |
| US-RAT-008 | Charge codes tab + New Charge Code (S12) + plan attachment rules | [EP-RAT-03-charges-taxes.md](06-epics/EP-RAT-03-charges-taxes.md) | draft | W1 |
| US-RAT-009 | Taxes & fees tab + New Tax/Fee (S13) with tenant-entered jurisdictions + plan tax rules | [EP-RAT-03-charges-taxes.md](06-epics/EP-RAT-03-charges-taxes.md) | draft | W1 |
| US-RAT-010 | Effective-dated versioning & single rate update (7-year reproducibility) | [EP-RAT-04-versioning-bulk.md](06-epics/EP-RAT-04-versioning-bulk.md) | draft | W1 |
| US-RAT-011 | Bulk rate update (rate_change_batches + per-entity log, reason required) | [EP-RAT-04-versioning-bulk.md](06-epics/EP-RAT-04-versioning-bulk.md) | draft | W1 |
| US-RAT-012 | Usage pricing: consumption → priced lines (multiplier, tiers, TOU, %-of-water, proration, UoM gate) | [EP-RAT-05-engine.md](06-epics/EP-RAT-05-engine.md) | draft | W3 |
| US-RAT-013 | Totals: tax base + account exemption + minimum bill (per-service first, then plan floor) | [EP-RAT-05-engine.md](06-epics/EP-RAT-05-engine.md) | draft | W3 |
| US-RAT-014 | Capacity-charge lines: account_capacities × capacity_rates, calendar-day prorated, taxable like base | [EP-RAT-06-capacity-charges.md](06-epics/EP-RAT-06-capacity-charges.md) | draft | W3 |
| US-RAT-015 | Rule-type plugins: one interface per pricing model, one per charge amount rule | [EP-RAT-05-engine.md](06-epics/EP-RAT-05-engine.md) | draft | W3 |
| US-RAT-016 | The `formula` amount rule: declared variable vocabulary + safe evaluator (S12 step 2) | [EP-RAT-07-tenant-formulas.md](06-epics/EP-RAT-07-tenant-formulas.md) | **blocked** (OQ-095) | W8 |
| US-RAT-017 | A formula versions like a tariff: publish, stamp, never re-price history, audit every write | [EP-RAT-07-tenant-formulas.md](06-epics/EP-RAT-07-tenant-formulas.md) | **blocked** (OQ-095) | W8 |
| US-RAT-018 | Test before publish: sample inputs, the stored result, and a diff on every later version | [EP-RAT-07-tenant-formulas.md](06-epics/EP-RAT-07-tenant-formulas.md) | **blocked** (OQ-095) | W8 |
| US-RAT-019 | Blast radius: a published formula found wrong after bills have issued | [EP-RAT-07-tenant-formulas.md](06-epics/EP-RAT-07-tenant-formulas.md) | **blocked** (OQ-095) | W8 |

**19 stories · 7 epics.** Rules: [`02-business-rules.md`](02-business-rules.md) · Fields: [`03-field-map.md`](03-field-map.md) · Traceability: [`../../10-traceability-matrix.md`](../../10-traceability-matrix.md)

> **EP-RAT-07 is blocked as a whole.** It amends **BR-RAT-041** (CONFIRMED, PO OQ-053 — "Formula" visible but *disabled*) via the proposed amendment **BR-RAT-046**. Candidate **OQ-095** is not yet in `12-governance/01-open-questions.md`; its full text is in EP-RAT-07 · US-RAT-016 §8, awaiting merge.
