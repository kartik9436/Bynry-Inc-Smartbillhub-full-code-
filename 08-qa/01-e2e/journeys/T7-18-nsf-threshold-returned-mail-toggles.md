# T7-18 — Config change: NSF privilege threshold + returned-mail paper suppression (forward-only, both)

---
id: T7-18
tier: 7
knob: nsf_privilege_n 2 → 1 · suppress_paper_on_bad_address on → off (S70 collections & notices rules, BR-TEN-041; keys per B2 r14 #5)
rules: [BR-PAY-013, BR-PAY-018, BR-TEN-016, BR-TEN-020]
stories: [US-TEN-010, US-PAY-009, US-PAY-016, US-NOT-014]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Two account-protection knobs, one discipline: a settings save writes settings and an audit row — NOTHING else. The NSF privilege threshold (BR-PAY-013: N NSFs → cash-only/no-autopay flag, default 2, config) governs evaluations at NSF EVENTS after the save; the paper-suppression toggle (BR-PAY-018) governs document GENERATION after the save. Neither save flips an account flag, regenerates a document, or touches a balance.

**Fixture.** Tenant brazos-bend · account ACC-1150: nsf_count=0, autopay enrolled · account ACC-1151: nsf_count=1 (one prior NSF: AR reinstated at original due date, outstanding 127.41 per money-triples `flat,cycle,nsf`), NOT flagged under N=2 · account ACC-1152: bad-address flagged (returned mail, BR-PAY-018), paper currently suppressed with suppression config ON · System Admin Alex Reed.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Alex sets `nsf_privilege_n` 2→1 and `suppress_paper_on_bad_address` on→off on the S70 card; atomic tab save | Toast → ONE audit row for the atomic save, before/after listing BOTH changed keys | BR-TEN-016 shape · BR-AUD-011: per-tab save = one row | BR-TEN-016 |
| 2 | Immediate re-read of all three accounts | ACC-1151 is NOT flagged by the save (nsf_count=1 ≥ new N, but a settings write is not an NSF event — no account state mutates on save); ACC-1150 unchanged; ACC-1152's bad-address flag unchanged (only address verification clears it, BR-PAY-018) | Zero account-row writes at save time; balances unaffected | BR-PAY-013 · BR-PAY-018 · BR-TEN-020 |
| 3 | ACC-1150 suffers its FIRST NSF after the change | Full BR-PAY-013 machinery: reversing row, allocations reversed, AR reinstated at ORIGINAL due date, NSF charge code added, nsf_count→1 — and the flag TRIPS at this event under N=1 (it would not have under the old N=2: the observable) | Cash-only/no-autopay flag set at the event, audited; autopay intents stop | BR-PAY-013 |
| 4 | ACC-1152's next bill generates (post-toggle-off) | Print/paper delivery rows QUEUE again for the bad-address account — suppression config is read at generation time; the still-set bad-address flag no longer suppresses because the config is off | Previously suppressed documents are NOT retroactively generated or sent; only the new document gets paper | BR-PAY-018 |
| 5 | Probe: flip `suppress_paper_on_bad_address` back ON (second audit row) and generate again | Paper suppressed again for ACC-1152 until address verified — the knob is symmetric and forward-only in both directions | Needs-attention queue entry and banner persist throughout (flag-driven, not config-driven) | BR-PAY-018 · BR-TEN-016 |
| 6 | INVARIANCE — sweep payments, reversals, documents, postings, flags across all saves | ACC-1151's prior NSF chain (reversing rows, 127.41 outstanding, original due date) byte-identical; no document regenerated; every flag transition traces to an EVENT row, never to a settings save; both saves audited | Forward-only proven for a money-adjacent knob and a delivery knob in one journey | BR-TEN-020 · NFR-22 · CLAUDE.md #4 |
