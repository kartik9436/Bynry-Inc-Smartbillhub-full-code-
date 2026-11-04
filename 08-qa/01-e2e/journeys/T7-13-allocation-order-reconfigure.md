# T7-13 — Config change: allocation order reconfigure (future payments only; past allocations stand)

---
id: T7-13
tier: 7
knob: allocation order oldest-invoice-first → newest-invoice-first (S66; BR-PAY-010 tenant-configurable)
rules: [BR-PAY-010, BR-BIL-021, BR-TEN-016, BR-TEN-020]
stories: [US-TEN-010, US-PAY-006, US-PAY-008]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Allocation order is tenant-configurable (BR-PAY-010 / OQ-010 closure: "Tenant may reconfigure the order"). The order in force at PAYMENT time governs that payment's allocation rows forever; a reconfigure must never re-spread money already allocated — the only door to move past allocations is the reapply story (US-PAY-008: reversing rows + new rows, reason + audit), never a settings save.

**Fixture.** Tenant brazos-bend, allocation order = default oldest-invoice-first, within-invoice usage+base → taxes → fees · account ACC-1120 with open bills: BL-2606-0101 (June, 97.41) and BL-2607-0101 (July, 97.41), both money-triples `flat,cycle` totals · payments of 97.41 each (the `flat,cycle,full` amount) arriving before and after the change · Billing Clerk Dana Kim; System Admin Alex Reed.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Payment A (97.41) posts under the default order | Allocates to the OLDEST open invoice: June's BL-2606-0101 closes; July stays open at 97.41 | Allocation rows reference payment A ↔ June invoice; within-invoice order usage+base → taxes → fees | BR-PAY-010 |
| 2 | Alex reconfigures the order key to newest-invoice-first on S66 (within-invoice sequence unchanged); atomic save | Toast → ONE audit row `billing_settings.updated` with before/after of the allocation-order key (r10 #6 family) | BR-TEN-016 shape · BR-AUD-011 one row | BR-TEN-016 · BR-BIL-021 |
| 3 | August run issues BL-2608-0101 (97.41); account now has July + August open | No allocation activity fires on the settings save or on issue — config change is not a money event | Payment A's rows untouched by both events | BR-TEN-020 |
| 4 | Payment B (97.41) posts under the new order | Allocates to the NEWEST open invoice: August closes; July remains outstanding at 97.41 — observably different from what oldest-first would have done | Allocation rows reference payment B ↔ August invoice; order-in-force-at-payment-time is a provable data fact | BR-PAY-010 |
| 5 | Probe: does anything re-spread payment A after the change? | NO — past allocations never move on config change; the only path is US-PAY-008 reapply (reversing allocation rows + new rows, reason + audit), which nobody invoked | Payment A still fully on June; no reversing rows exist; overpayment/credit logic untouched | US-PAY-008 · BR-TEN-020 |
| 6 | INVARIANCE — sweep allocations, invoices, postings, balances before/after step 2 | Every pre-change row byte-identical; account balance arithmetic consistent under both orders (sum allocated = sum paid); documents/history never restate | Aging report reflects July outstanding — a FORWARD consequence, not a restatement | BR-TEN-020 · NFR-22 |
