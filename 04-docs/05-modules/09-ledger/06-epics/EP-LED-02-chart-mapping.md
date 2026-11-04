# EP-LED-02 — Chart of accounts & GL mapping export codes (S56)

**Module:** ledger · **Wave:** W5 · **Screens:** S56 · **Status:** draft (BR-LED-001..016 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r13)

## Scope
**In:** the tenant **chart of accounts** — seeded at provisioning (seed content finalized with finance at GT freeze, r13 #7, closing B2 O-14), tenant-customizable, **audit-locked while in use** (IS-1 deactivate-first; referenced accounts never delete) — and the **export codes** (target-system account refs: qbo_ref, xero_ref per r13 #5) carried on the Finance account-mapping page (BR-LED-014; the mapping surface itself = US-BIL-009, BR-BIL-010).
**Out:** ~~the mapping-page sections owned by billing (service/tax/charge/designation mappings — US-BIL-009)~~ **— SUPERSEDED 2026-08-11 (OQ-106): those mappings are LEDGER-owned and IN scope here; US-BIL-009 SURFACES them, it does not own them** · seeded COA CONTENT (finance-owned at GT freeze, r13 #7) · export execution (US-LED-016) · exact DDL 🔒 (r13 #8).
**Tables (B2 + r13):** `ledger_accounts` (+ qbo_ref/xero_ref, r13 #5); **OWNS** `service_gl_map`/`tax_authority_gl_map`/designations (r10 #2). ⚠ **THIS LINE SAID "billing-owned" AND WAS SUPERSEDED 2026-08-11 by a PO ruling closing OQ-106.** B2 r16 #6 always assigned both maps to LEDGER ("surfaced by billing US-BIL-009"); this epic's §Scope said billing owned them, and two signed documents disagreeing is what blocked the posting service — it could not resolve "the AR account" without hardcoding 1200 while US-LED-005 makes the chart tenant-customizable. **The PO ruled: the LEDGER owns them**, configured *"during GL code mapping in settings"*, beside the chart of accounts the accountant already maintains. A designation is an **ATTRIBUTE (a field)** carried on ledger accounts **and on utility services** — *"we can derive how it sum up at Ledger"* — which is what makes service-wise revenue and cash collections computable without a second mapping table.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S56 · Chart of accounts panel | code, name | type (asset/liability/equity/revenue/expense), status (active/deactivated) | code asc | code, name, type | Code · Name · Type · Status · In use / +QBO ref, Xero ref, Created (IS-5) | Edit (label) · Deactivate/Reactivate · Delete (only if unreferenced, IS-1) | — | CSV (IS-9) |

## Stories

---
id: US-LED-005
epic: EP-LED-02
module: ledger
screens: [S56]
wave: 5
status: draft
blocked_by: []
depends_on: [US-TEN-010]
journeys: [J5]
rules: [BR-LED-014, BR-LED-015]
golden_tests: []
finance_calc: none
---
### US-LED-005 — Chart of accounts: seeded, tenant-customizable, audit-locked in use

**1 · Details** — As Finance/Owner staff, I want the tenant chart of accounts on the S56 General ledger tab: **seeded at provisioning** (seed rows incl. the r9 #3 "Accounts receivable" + "Opening balance clearing" designation targets; full seed CONTENT = finance + Eng Lead at GT freeze, r13 #7 — this story ships the mechanism, never the numbers), **tenant-customizable** (add accounts, edit names), and **audit-locked while in use**: an account referenced by journal lines, GL mappings, charge codes or designations can be **deactivated but never deleted** (IS-1 delete-deactivate-first; financial records never delete, CLAUDE.md #4), and its `code`/`type` are frozen once posted against — historical books are never restated ⚠ **AMENDED 2026-10-29 FOR `code` ONLY (`CR-196-BRC10`, BR-LED-040): a System Admin may change the CODE even when the account is used; it applies everywhere at once (past entries read the new code, "formerly <old>" kept on the account); `type` stays frozen** (BR-TEN-020 principle: changes are forward-only, stored history keeps its values). Account `type` drives the trial-balance Type column (S56, A14 r2). Every change audits (BR-LED-015). Entry: S56 chart panel. Exit: chart rows feeding mappings (US-BIL-009), stamping (BR-BIL-010), posting (EP-LED-01) and export codes (US-LED-006).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-014 | The GL mapping page context this chart feeds carries the export codes (US-LED-006). | CONFIRMED — PO LB-6, 2026-08-08 (LE-5) |
| B2 r13 #7 *(consumed)* | Seeded chart of accounts finalized with finance at GT freeze — closes O-14. | CONFIRMED — PO batch #6 approval, 2026-08-08 |
| IS-1 *(consumed)* | Deactivate-first; hard delete only when unreferenced; 🔒 audit-lock when referenced. | CONFIRMED — B9 |
| BR-TEN-020 *(consumed)* | Historical stored values are never restated by later config changes (applied here: code/type frozen once posted against). | CONFIRMED — B2 conventions + prototype footer copy |
| BR-LED-015 | Every chart change writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Tenant provisioned | Seeded chart present (incl. AR + opening-clearing rows per r9 #3); codes UNIQUE per tenant (B2 DDL); panel lists code · name · type · status · in-use |
| TC-2 | Finance adds account `6805 · Card processor fees` (expense) and renames `4130` label | Both saved; audit rows `ledger_account.created` / `.updated` with before/after |
| TC-3 | Deactivate an unused account | Allowed; row hidden from mapping/JE pickers; reactivate restores it |
| TC-4 *(negative)* | Delete attempted on 4100 (journal lines + service mapping reference it); code/type edit attempted on 4100 | Delete blocked with the reference count (IS-1 audit-lock); ~~code/type frozen once posted against — only the label edits~~ ⚠ AMENDED 2026-10-29 (`CR-196-BRC10`): TYPE frozen; the CODE changes for a System Admin (clerk refused by name), shows *"formerly 4100"*, and every past entry reads the new code; deactivate remains available but mapping validation (US-BIL-009 TC-5) flags the gap |
| TC-5 *(negative)* | Staff-role user opens the chart panel for edit | Server-side refusal — Finance/Owner surface (S56 per A1 r2, Owner/Finance roles) |
| TC-6 *(isolation)* | Lone Star Ridge chart | Its own rows only; Brazos Bend codes can repeat there (per-tenant UNIQUE); RLS everywhere |

**4 · Test Data** — Brazos Bend seed sample (WE-1 chart, content illustrative until GT freeze): 1000 Cash · 1200 AR · 1210 Unbilled AR · 2200–2203 tax payable (State/County/City/PUC) · 2300 Deposit liability · 3000 Opening balance equity/clearing · 4100/4105 electric · 4110/4115 water · 4120 sewer · 4130 trash · 4150 solar capacity · 4200 Late fees · 6800 Bank fees · 6900 Bad debt. New row: 6805 Card processor fees, added Aug 3, 2026 by Norma Reyes. Isolation: Lone Star Ridge (J. Okafor) with its own 4100.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Code | S56 chart | A14 r2 (GL account col) | `ledger_accounts.code` | text | user-input (seeded) | UNIQUE per tenant; ~~frozen once posted against~~ editable by System Admin even when used (`CR-196-BRC10`, 2026-10-29) |
| Name | S56 chart | A14 r2 | `ledger_accounts.name` | text | user-input | editable always; audited |
| Type | S56 chart | A14 r2 (Type col) | `ledger_accounts.type` | enum (full set = COA seed, r13 #7) | reference-data | frozen once posted against |
| Status | S56 chart | IS-1 | `ledger_accounts.deleted_at` (soft) + active flag pattern | enum | user-input | deactivate-first; delete only if unreferenced |
| In-use indicator | S56 chart | IS-1 | computed (journal_lines/mappings/charges/designations refs) | count | computed-display | drives the audit-lock |
| Seed rows | — | r13 #7 / r9 #3 | `ledger_accounts` seed at provisioning | rows | reference-data | content = finance at GT freeze |
| Audit | — | CLAUDE.md #7 | `audit_log` `ledger_account.*` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given provisioning, Then the seeded chart exists and every panel row ties to it.
- Given customization, Then adds/renames work with audit; given references, Then delete is impossible and TYPE is frozen; the CODE may be changed by a System Admin and applies to past entries too, with "formerly" kept (amended 2026-10-29, `CR-196-BRC10`).
- Given roles/tenants, Then edit is Finance/Owner-only and charts never cross.

**7 · Finance Calculation** — N/A (CRUD mechanism; no computation. Seed content = finance-owned at GT freeze, r13 #7).

**8 · Open Questions** — ~~None (COA seed content already routed to finance + Eng Lead via r13 #7 / B2 O-14 closure).~~ **AMENDED 2026-08-12 — three PO rulings reach the chart, and two of them ADD an account.**

- **TAX LIABILITY CODES ARE GENERATED IN THE 2200 SERIES, AND A RETIRED CODE IS NEVER RE-LET (BR-LED-023).** PO verbatim: _"Generated"_ (OQ-147). The tenant adds an authority and the product allocates the next code in the signed 2200 series; the tenant separately CHOOSES which account a tax points at (OQ-145, _"make them choose"_) — choosing and numbering are different acts, and a hand-typed code is how two authorities end up sharing one. **Worked (an Eng-Lead disposition, NOT shown to the PO):** a tenant holding **2200-01, 2200-02, 2200-03** who retires Harris County (**2200-02**) gets **2200-04** next — **not 2200-02, and that number is gone for good**, because `uq_ledger_accounts_code` counts soft-deleted rows and because a code that meant Harris County in March and City of Katy in June makes every earlier remittance report read wrong, silently. TC-4's "code frozen once posted against" is unchanged; this rules who NUMBERS a new one. ⚠ (2026-10-29, `CR-196-BRC10`: the code is no longer frozen; a renamed tax account keeps its minted number as its internal `seed_key`, and the allocator counts that key, so a renamed number is still never re-let.)
- **A GOODWILL CONCESSION NEEDS ITS OWN ACCOUNT, SEPARATE FROM BAD DEBT (BR-LED-022).** PO verbatim: _"a separate write-off account"_ (OQ-105/OQ-168) and _"Seperate them"_ (OQ-187). **Worked:** at year end the single write-off account showed **$4,200** — **$1,700** the utility CHOSE to give and **$2,500** it could not collect; a board reading one number cannot tell a decision to give from a failure to collect. **This MINTS A NEW ACCOUNT in the finance-signed chart and needs a finance RE-SIGN via HUMAN-GUIDE §6** (the route the 4160/4170 accounts took) — so §4's seed sample gains a concession account BESIDE `6900 Bad debt`, and until that signature exists `posting_seam.write_off_account_id` keeps resolving the existing bad-debt designation and concessions keep landing there.
- **THE GL MAPPING SURFACE LIVES UNDER SETTINGS → CONFIGURE, WITH LEDGER SETTINGS.** PO verbatim: _"Confirm they belong with ledger settings"_ (OQ-106) and _"Confirm: under Configure"_ (OQ-151) — not a ninth top-level tab. This ratifies the §Scope supersession recorded above and gives the same home to the per-authority remitting-basis setting (BR-LED-002) and to the tenant-defined fourth allocation class (OQ-123, payments-owned BR-PAY-038).

---
id: US-LED-006
epic: EP-LED-02
module: ledger
screens: [S56]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-005, US-BIL-009]
journeys: [J5]
rules: [BR-LED-014, BR-LED-004, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-006 — Export codes on the Finance account-mapping page (qbo_ref · xero_ref)

**1 · Details** — As Finance/Owner staff, I want each ledger account to carry its **target-system account refs** — `qbo_ref` (QuickBooks) and `xero_ref` (Xero) per B2 r13 #5 — surfaced and edited on the **Finance account-mapping page** (BR-LED-014: "the GL mapping page carries the export codes"; the page itself is US-BIL-009's surface — this story adds the export-code columns), so that S42's handover (BR-LED-004: summary JE "using export codes on the GL mapping page") can address the tenant's real ERP accounts. IIF/CSV targets use the account code+name (A14 §Accounting exports GL-summary columns); QBO/Xero rows require their ref. Missing refs are visible as gaps on the page; the S42 export validates against them (US-LED-016 TC — export blocked naming the unmapped account, the US-BIL-009 TC-5 atomic-fail pattern). Edits are forward-only: recorded export batches keep the refs they shipped with (BR-TEN-020 principle; batch content is hashed, BR-LED-004). Entry: S56 mapping panel. Exit: refs consumed by US-LED-016.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-014 | GL mapping page carries the export codes (target-system account refs). | CONFIRMED — PO LB-6, 2026-08-08 (LE-5) |
| BR-LED-004 *(consumed)* | Export uses the mapping-page export codes; batches recorded + idempotent (executed US-LED-016). | CONFIRMED — PO LF-4, 2026-08-08 (LE-5) |
| BR-BIL-010 *(consumed)* | The mapping surface + stamped-at-issue discipline (page owned by US-BIL-009). | CONFIRMED — PO Billing A-1 (a), 2026-08-08 |
| BR-LED-015 | Export-code edits write audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Mapping page renders (Brazos Bend) | Each chart row shows QBO ref + Xero ref columns beside the US-BIL-009 mappings; gaps render as visible empty states, not silently |
| TC-2 | Finance sets 4100 → qbo_ref `79`, 1200 → qbo_ref `84`; saves | Persisted on `ledger_accounts`; audit `ledger_account.export_code_updated` with before/after |
| TC-3 | LE-5 export consumes | Every one of the July summary rows carries its qbo_ref into the QBO payload (US-LED-016 TC-1 pair) |
| TC-4 | Ref edited AFTER batch EXP-2607-QBO recorded | The recorded batch (content hash) is unchanged; only future exports use the new ref |
| TC-5 *(negative)* | QBO export attempted while 6900 has no qbo_ref | Export blocked naming `6900 · Bad debt` (atomic-fail pattern) — nothing partial hands over; CSV/IIF (code-addressed) remain available |
| TC-6 *(negative)* | Staff-role edit attempt | Refused server-side — Owner/Finance surface |
| TC-7 *(isolation)* | Lone Star Ridge refs | Its own refs; Brazos Bend's QBO refs never visible or reused (RLS) |

**4 · Test Data** — Brazos Bend QBO refs (illustrative tenant data): 1000→`35`, 1200→`84`, 2200→`91`, 2300→`93`, 4100→`79`, 4110→`80`, 4200→`82`, 6900→`88`. Xero refs: `200`/`610`/`820` style codes. Fixture batch: EXP-2607-QBO (LE-5). Edit fixture: 4100 qbo_ref 79→101 on Aug 9, 2026 (after the July batch). Actors: Norma Reyes (Finance), Diana Chen (finance advisor). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| QBO ref | S56 mapping panel | BR-LED-014 / r13 #5 | `ledger_accounts.qbo_ref` | text | user-input | required for QBO sends (validated at export) |
| Xero ref | S56 mapping panel | BR-LED-014 / r13 #5 | `ledger_accounts.xero_ref` | text | user-input | required for Xero sends |
| Gap indicator | S56 mapping panel | BR-LED-004 | computed (rows missing the target ref) | flag | computed-display | mirrors the export validation |
| Ref usage in batch | S42 | BR-LED-004 | `export_batches` content hash (r13 #4) | hash | system-derived | recorded batches never re-ref |
| Audit | — | CLAUDE.md #7 | `audit_log` `ledger_account.export_code_updated` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the mapping page, Then every chart row exposes its QBO/Xero refs with gaps visible.
- Given LE-5, Then the July summary rows carry their refs verbatim into the payload, and a missing ref blocks that target atomically.
- Given a later ref edit, Then recorded batches are untouched; given tenants, refs never cross.

**7 · Finance Calculation** — CONFIRMED (LE-5 context; no arithmetic — ref lookup only). Worked: July QBO summary = 8 GL rows from LE-1's period deltas, each row `{code, qbo_ref, DR|CR}`, e.g. `{4100+4105+…, per-GL rows, refs 79/80/…}`; batch **EXP-2607-QBO** records who/when/hash (figures asserted in US-LED-016 §7).

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-15 (close-the-books lane, on BUILDING §1).** The backend half ships in `apps/ledger/services.py`: `set_export_codes` (the write), `export_code_row` / `export_code_map` (the page's read, with the per-target gap lists TC-1 wants visible). TC-1, TC-2, TC-3, TC-5, TC-6 and TC-7 are green — the refs ride into the July payload, a missing `qbo_ref` blocks the QBO send ATOMICALLY naming the account while CSV and IIF stay available, an `executive` is refused server-side, and another tenant's account id is a NOT-FOUND rather than a 403 (HR-1). Three residues:

- **TC-4 IS TRUE BY CONSTRUCTION RATHER THAN BY A GUARD**, and that is the stronger form: `apps/ledger/exports.py` STORES the payload it sent and hashes it, so a recorded batch keeps the refs it shipped with and a later edit reaches nothing. Nothing in this story has to look backwards, and nothing may.
- **`_UNSET` VERSUS `None` IS THE WHOLE SIGNATURE.** Omitting an argument leaves that ref alone; passing `None` CLEARS it. A page that saved both fields on every submit would wipe a Xero ref every time somebody typed a QuickBooks one, and the two are edited from different columns of the same row. A blank string stores as NULL — *"a ref of empty string"* and *"no ref"* are the same fact to an export, and two spellings would make the gap indicator wrong for one of them.
- **THE ROLE GATE IS THE OQ-175 READING** (System Admin + Billing Clerk), the same one the close and the export carry: the PO ruled those two roles about REVERSING a posted entry, and this product has no *Finance* and no *Owner*. Flagged, not treated as separately ratified. **NOT BUILT: the mapping PAGE itself** — BR-LED-014 places it under Settings → Configure (PO 2026-08-12, OQ-106 + OQ-151) and the API and frontend halves are another lane's; what exists is the read the page renders and the write it calls.
