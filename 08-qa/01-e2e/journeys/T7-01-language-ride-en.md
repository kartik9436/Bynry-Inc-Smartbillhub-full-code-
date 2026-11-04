# T7-01 — Language ride: en (tenant-default identity case — the pin is always explicit)

---
id: T7-01
tier: 7
language: en
rules: [BR-CUS-064, BR-NOT-006, BR-SHL-030, BR-TEN-042, TD-16, IS-11]
stories: [US-CUS-003, US-NOT-005, US-NOT-006, US-BIL-022, US-PAY-025, US-SHL-013]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The degenerate-but-load-bearing case: account preferred language en on a tenant whose default is en. Every document must still record an EXPLICIT language on its pin (BR-NOT-006 — the pinning tuple includes the language variant; "same as default" is never stored as an absence), no fallback fires, and the seams that must stay language-neutral (server codes, CSV) are proven neutral here so the es/de/hi rides (T7-02..05) diff against a clean baseline.

**Fixture.** Tenant brazos-bend, default language en (BR-TEN-042 seed set en/es/es-MX/de/hi) · account ACC-1008 John Miller, Residential, preferred_language=en (set in the S18 wizard per BR-CUS-064) · flat plan · money-triples row `flat,cycle,full`: taxable 89.00 + tax 8.41 = 97.41, paid in full · clerk Dana Kim, UI language en.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | S18 New Account wizard sets preferred language en | `accounts.preferred_language = 'en'` stored (B2 r15 #2) — an explicit value, not null | Account detail shows the language; audit row for account create | BR-CUS-064 |
| 2 | Bill run issues BL-2608-0201 ($97.41) | Server-side renderer (TD-16 #2) selects the bill-template variant tuple (type=bill, category=Residential, language=en); pin on the invoice records template_id + version + **language=en** | Document renders; pin tuple complete — language never inferred at reprint time; delivery rows queue (BR-NOT-005) | BR-NOT-006 · BR-BIL-026 |
| 3 | Payment PMT-2608-0117 (97.41, full) clears → receipt auto-queues; a reminder notice is generated on a sibling account | Receipt and notice select their en variants the same way; every queued document row carries its resolved language | Zero fallback events recorded anywhere in this journey (en variants exist for all classes) | BR-NOT-006 · US-PAY-025 |
| 4 | Dana Kim works S30/S33 while the account renders | Staff UI strings come from the platform en catalog CLIENT-side (TD-16 #1); UI language = the USER's setting, independent of any account's preferred language | Catalog source = platform i18n asset (BR-SHL-030), not template variants | BR-SHL-030 · TD-16 |
| 5 | Dana exports the S30 bills list to CSV | CSV is language-neutral: snake_case English headers, plain 2dp money (97.41 — no symbol), ISO dates — identical bytes to what any language ride produces | IS-11 contract holds; UTF-8; no translated headers, ever | IS-11 · TD-16 #4 |
| 6 | INVARIANCE — reprint BL-2608-0201 after tenant default language is toggled en→es→en (settings only, then restored) | Reprint renders the PINNED tuple (…language=en) forever; the settings excursion restates nothing — no document, posting, or history row changes | Byte-stable rendering inputs; each settings save audited (BR-TEN-016); ledger untouched | BR-NOT-006 · BR-TEN-020 · NFR-22 |
