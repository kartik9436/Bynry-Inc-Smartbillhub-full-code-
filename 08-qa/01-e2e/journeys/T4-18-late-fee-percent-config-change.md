# T4-18 — Late-fee % config change (x = 1.5% min $5 → y = new % ; NEXT assessment only, existing fees untouched)

---
id: T4-18
tier: 4
rules: [BR-BIL-021, BR-BIL-001, BR-BIL-008, BR-BIL-004, BR-TEN-016, BR-TEN-041]
stories: [US-TEN-010, US-PAY-014, US-BIL-026]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = tenant late-fee config 1.5% / min $5.00 (Settings → Billing defaults, the S66 family per BR-TEN-041); y = the percentage changed. The boundary is the config-over-constant law read together with financial immutability: the late-fee parameters are tenant CONFIG consumed at ASSESSMENT time (BR-BIL-001/021) — changing them affects only fees assessed AFTER the change; every LATE line already on an issued bill is an immutable invoice line that no settings edit may touch. If a config change re-derived old fees, settings would become a retroactive money lever.

**Fixture.** Tenant brazos-bend · pre-change assessment on the WE-15(a) fixture: overdue **$400.00** → 1.5% = **$6.00** LATE line (issued) · Admin changes the late-fee % on Aug 12 · post-change assessment on the next overdue account — its dollar value derives from the NEW config and is engine-computed per 00-e2e-design.md §5 (no worked figure exists in the frozen workbooks for a non-1.5% rate).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Baseline: grace expires on an overdue $400 account; ladder assesses the fee | Fee = max($5, 1.5% × overdue portion) = **$6.00**; LATE charge-code line on the account, non-taxable (fees never taxed, B4.2) | LATE line issued + GL-stamped; audit; AR +6.00 | BR-BIL-001 · BR-BIL-008 |
| 2 | System Admin edits Settings → Billing: late-fee percentage 1.5% → new value (min $5 and grace unchanged) | Tenant config row updates — nothing else recomputes at save time; no job re-walks past assessments | audit row with before/after (every Settings write audited); settings UI reflects the new %; zero bill/ledger movement at save | BR-BIL-021 · BR-TEN-016 · BR-TEN-041 |
| 3 | Harness re-reads every existing LATE line after the save | — | all previously assessed fees byte-identical ($6.00 stays $6.00); no credit notes, no re-derivations; account balances unmoved | BR-BIL-004 · hard rule 4 |
| 4 | NEXT assessment fires (another account passes grace after Aug 12) | Fee computes on the NEW percentage against that account's overdue portion, min $5 floor still applying (engine-computed dollar, §5 harness) | new LATE line reflects the new config; audit names the assessment; AR moves by the new fee only | BR-BIL-001 · BR-BIL-021 |
| 5 | Waiver contrast: staff waive the step-1 fee for a first-time-late customer | Manual, never automatic — a human decision with audit; unrelated to the config change | waiver recorded as its own append-only correction path; the original assessment history stands | BR-BIL-003 |
| 6 | **INVARIANCE** — what must NOT have changed | Every fee assessed before the config change; every issued invoice carrying a LATE line; the grace days + mode (untouched in this journey — T4-19 owns that axis) | issued lines immutable; config history audited both directions; reports of period fee revenue for closed periods identical before/after | BR-BIL-004 · BR-BIL-021 · hard rule 4 |
