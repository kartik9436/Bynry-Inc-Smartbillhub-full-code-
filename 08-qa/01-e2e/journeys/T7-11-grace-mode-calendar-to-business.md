# T7-11 — Config change: late-fee grace mode calendar → business (next evaluation shifts; assessed fees stand)

---
id: T7-11
tier: 7
knob: late_grace_mode calendar → business (S66 Billing defaults)
rules: [BR-BIL-002, BR-BIL-008, BR-BIL-021, BR-TEN-016, BR-TEN-020]
stories: [US-TEN-010, US-PAY-014]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Grace mode is calendar OR business days, a tenant setting (BR-BIL-002; B4.1 counts grace from the due date). Flipping calendar→business must move only the NEXT fee-eligibility evaluation — weekends now stretch the runway — while every already-assessed fee, issued bill, and posting stands untouched. A mode flip that re-dated past assessments would be a silent restatement; this journey makes that impossible to ship.

**Fixture.** Tenant brazos-bend, `late_grace_mode=calendar`, `late_grace_days=5` (BR-BIL-008 default) · account ACC-1101: bill BL-2607-0155 already past its grace, late fee 5.00 ASSESSED under calendar mode (money-triples `flat,cycle,none`: 97.41 outstanding, next_late_fee 5.00) · account ACC-1102: bill BL-2608-0270 (97.41) due **Fri 2026-08-14**, unpaid, not yet fee-eligible · System Admin Alex Reed.

**Fixture amendment (2026-08-22, CR-014 / DEF-556).** **ACC-1101 arrives** with an issued, unpaid August 97.41 bill (Unit 4D, MTR-0452, same run as ACC-2042). **The PRE-ASSESSED 5.00 late fee does NOT arrive**: assessing it at seed time needs a bill already past grace before September, and every such period posts its journal entry inside the finance-signed July window (measured: 553.69 → 748.51). The journey assesses the fee at its own evaluated date instead (BR-TEN-043). **ACC-1102's Fri-due bill does not arrive either** (same window arithmetic — a bill due Fri 2026-08-14 must issue from a pre-August period); its WE-15e weekday shape needs OQ-333's resolution or a journey-time act, recorded here rather than faked.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Baseline check under calendar mode | ACC-1102's grace expires after due + 5 CALENDAR days = 2026-08-19 (Wed); fee-eligibility evaluates from then | ACC-1101's assessed 5.00 fee exists as an issued line; ACC-1102 not yet eligible | BR-BIL-002 · BR-BIL-008 |
| 2 | Alex flips `late_grace_mode` calendar→business on S66 Billing defaults (staged edit → atomic tab save) | Save succeeds → toast → ONE audit row `billing_settings.updated` with before/after `{late_grace_mode: calendar→business}` (changed fields only) | BR-TEN-016 shape; BR-AUD-011 one row per atomic save | BR-TEN-016 · BR-TEN-024 |
| 3 | Harness re-evaluates ACC-1102's fee eligibility | Grace now counts 5 BUSINESS days from the due date: Sat 08-15/Sun 08-16 skipped → expiry 2026-08-21 (Fri); no fee may assess in the 08-19→08-21 gap the flip opened | Server-side evaluation (collections engine) uses the mode in force at evaluation time; both modes implemented (B4.1) | BR-BIL-002 |
| 4 | Clock passes the new expiry with ACC-1102 still unpaid | Fee assesses per the formula on the overdue portion — the minimum applies at this balance (5.00, matching the triples `next_late_fee`); assessed under BUSINESS mode | New fee line is a NEW row; assessment date consistent with business-day expiry, provably later than calendar would have fired | BR-BIL-002 · B4 §Late fee |
| 5 | Probe: ACC-1101 (assessed pre-flip) re-checked | The 5.00 calendar-mode fee is UNTOUCHED — not re-dated, not re-computed, not reversed by the config save; its invoice line and posting immutable | Settings writes never touch money rows; corrections would be new rows only (CLAUDE.md #4) | BR-TEN-020 · BR-TEN-017 |
| 6 | INVARIANCE — full sweep after the flip | Zero changes to any issued invoice, fee line, journal entry, or history row from the settings save itself; only FUTURE evaluations differ; reprints render pinned documents unchanged | The IS-8/BR-TEN-020 principle executable: changing settings does not restate history | BR-TEN-020 · NFR-22 |
