# T7-02 — Language ride: es (customer documents in Spanish, staff UI untouched)

---
id: T7-02
tier: 7
language: es
rules: [BR-CUS-064, BR-NOT-006, BR-SHL-030, BR-TEN-042, TD-16, IS-11]
stories: [US-CUS-003, US-NOT-005, US-NOT-006, US-BIL-022, US-PAY-025, US-SHL-013]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** One account's preferred language (es) drives every customer-facing document — bill, receipt, reminder notice — through the ONE server-side renderer (TD-16 #2), while the clerk who triggers each of them keeps working in her own UI language. Assertions are structural (which variant was selected, what the pin records) — never copy text.

**Fixture.** Tenant brazos-bend, default language en · account ACC-1042 Maria Delgado, Residential, preferred_language=es (BR-CUS-064) · es variants published for bill, receipt, and reminder classes (BR-NOT-006 tuple type × category × language) · money-triples row `flat,cycle,partial60`: total 97.41, payment 58.45, outstanding 38.96 · clerk Dana Kim, UI language en.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Preferred language set to es on ACC-1042 (account edit; also provable via S19 move-in and the import-template column) | `accounts.preferred_language='es'` stored; change audited | Field on account detail; import template carries the column (BR-CUS-064) | BR-CUS-064 |
| 2 | Bill run issues BL-2608-0214 ($97.41) for ACC-1042 | Renderer selects variant (bill, Residential, **es**); invoice pin = template + version + language=es | Delivery rows queue; the es selection is a data fact on the pin, not a render-time lookup | BR-NOT-006 · BR-BIL-026 · TD-16 |
| 3 | Partial payment 58.45 posts → receipt queues; later the outstanding 38.96 draws a payment-reminder (S34 bulk action) | Receipt variant (receipt, Residential, es) and reminder variant (reminder, Residential, es) selected; each outbound_messages row records its resolved language | Three document classes, one account, one language — all es; queue statuses progress normally (BR-NOT-005) | BR-NOT-006 · US-PAY-025 |
| 4 | Dana Kim (UI en) is the actor for every step above | Staff UI stays en throughout — client-side platform catalog (TD-16 #1); nothing about the ACCOUNT's language leaks into the STAFF surface | Simultaneously, a second clerk with UI es sees es chrome over the same data (BR-SHL-030 per-user) | BR-SHL-030 · TD-16 |
| 5 | Dana exports S30 filtered to ACC-1042 | CSV identical in structure to T7-01 step 5: snake_case headers, 97.41 / 58.45 / 38.96 plain 2dp, ISO dates — language never reaches the file | IS-11 byte contract; filename contract holds | IS-11 · TD-16 #4 |
| 6 | INVARIANCE — ACC-1042's preferred language later changes es→en; reprint BL-2608-0214 | Reprint renders pinned language=es FOREVER (BR-NOT-006); only future documents pick en; no posting, balance, or history row changes on the language edit | Preferred-language change audited; ledger and AR untouched by a display-language edit | BR-NOT-006 · BR-TEN-020 · NFR-22 |
