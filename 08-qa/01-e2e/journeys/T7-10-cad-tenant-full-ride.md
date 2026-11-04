# T7-10 — Non-USD tenant full ride: CAD bill → payment → ledger → report, coherent everywhere

---
id: T7-10
tier: 7
knob: currency=CAD (whole meter-to-cash chain on a non-USD tenant)
rules: [BR-TEN-042, IS-8, IS-11, BR-BIL-007, BR-PAY-010, NFR-22]
stories: [US-BIL-005, US-BIL-007, US-PAY-001, US-PAY-006, US-PAY-025, US-REP-003]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** One currency per tenant means the WHOLE chain — invoice, lines, allocation, journal entry, trial balance, report files — carries CHAR(3)='CAD' with no USD assumption hiding anywhere: no hardcoded `$`-means-USD, no symbol in a CSV, no mixed-currency aggregate. The CAD sample tenant from T7-09 rides the full meter-to-cash spine and every money surface is checked for coherence.

**Fixture.** Tenant maple-creek (currency CAD, locked per T7-09) · account ACC-2001 Marie Gagnon, Residential, flat plan · money-triples row `flat,cycle,full`: taxable 89.00 + tax 8.41 = 97.41, paid in full · USD tenant brazos-bend live in the same database as the coherence control.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Bill run issues BL-2608-0002 for ACC-2001 ($97.41 CAD) | Invoice + every invoice_line row: NUMERIC(18,6) amounts + currency 'CAD'; GL stamped; template pinned | Screen shows CAD formatting per tenant Regional settings (IS-8); document PDF likewise, server-side | BR-TEN-042 · IS-8 |
| 2 | Payment PMT-2608-0001 (97.41, full) recorded and cleared | Payment row CAD; allocation engine allocates per tenant order (BR-PAY-010); receipt queues | Account balance 0.00 CAD; allocations reference invoice + payment in the same currency — mixed-currency allocation is structurally impossible (one currency per tenant) | BR-PAY-010 |
| 3 | Posting lands | ONE balanced journal entry; every journal_line CAD; debits = credits (97.41 both sides across the line set) | Only the ledger posting service wrote lines; dimensions carried (DB-11) | BR-BIL-007 · CLAUDE.md #5 |
| 4 | Trial balance (S56) for the period | TB computes entirely in CAD and balances; no cross-tenant, cross-currency aggregation anywhere — brazos-bend's USD figures unreachable and unmixed | Drill-down rows tie to the journal lines; RLS isolation holds | BR-TEN-042 · IS-11 |
| 5 | Download TB + billing register: CSV + PDF | CSV: plain 2dp decimals `97.41`, NO currency symbols/separators, ISO dates, snake_case headers — identical file grammar to a USD tenant; PDF: CAD formatting per IS-8 with basis label, filters echoed | IS-11 byte contract is currency-agnostic; filename contract holds; money-export audited | IS-11 · IS-8 |
| 6 | INVARIANCE — harness sweeps every money row written in this journey plus a settings no-op save cycle on S8 | 100% of money rows carry 'CAD' (zero 'USD' defaults leaked); the settings save cycle restates nothing — documents, postings, history identical before/after | Any hardcoded-USD default anywhere in the chain fails this sweep | BR-TEN-042 · BR-TEN-020 · NFR-22 |
