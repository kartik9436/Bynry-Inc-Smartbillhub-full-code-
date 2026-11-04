# EP-INT-03 — File channels (bank/lockbox import connection profiles · accounting export target profiles)

**Module:** integrations · **Wave:** W4 (bank/lockbox profiles pair US-PAY-003) / W5 (accounting targets pair US-LED-016; bank rec US-PAY-021) · **Screens:** S8 Settings → Integrations (profile cards + management lists); consumer surfaces S35 (lockbox import), S38 (bank wizard), S42/S43 (export) · **Status:** draft (BR-INT-009/010 + lifecycle law CONFIRMED)

## Scope
**In:** **bank/lockbox import connection profiles** — one profile per bank/source: label, file format (**BAI2 / CSV / OFX / QBO / QFX** — B7 bank rows + NFR-20), column-mapping choice for CSV variants, source **upload (v1 live) or SFTP** (A1 addendum method; pull execution = provision, discrepancy I-8) — CONSUMED by US-PAY-003 (S35 lockbox) and US-PAY-021 (S38 bank statement wizard); **accounting export target profiles** — QBO-file / Xero-file / CSV / IIF targets with the export-code hand-off pointer (codes LIVE on the Finance mapping page per BR-LED-014 — never here) — CONSUMED by US-LED-016 (S42/S43); **profile lifecycle + guardrails** — IS-1 deactivate-first when referenced by recorded batches, idempotency alignment (imports file+tags BR-PAY-028/OQ-044; exports BR-LED-004; NFR-16), Failed · Retry surfacing.
**Out:** the FLOWS — lockbox staged import, bank auto-match/reconcile, export batch creation (payments/ledger own them: BR-PAY-019/023, BR-LED-004; this pack is CONNECTION surface only per CL-1) · Plaid direct bank feed (W7 — EP-INT-04; payments P-6) · QBO/Xero LIVE sync (v2 — EP-INT-04, BR-LED-020) · generic modal/secret/audit mechanics (EP-INT-01).

## Capability matrix (list screens only — B9 conformance)
Profile management lists follow the ratified S8 management-view pattern (A1 Settings rework item 4: table + Add modal, per-row Edit/Deactivate, 🔒 audit-lock when Used-by > 0).
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 Integrations → Bank & lockbox profiles | profile label | format · status | label A→Z | label, format, last-used | label · bank/source · format · source (upload/sftp) · status · used-by (batches) / +created-by, last-used | Edit · Deactivate (🔒 delete blocked when used-by > 0, IS-1) | — | — |
| S8 Integrations → Accounting export targets | target label | target type · status | label A→Z | label, target, last-export | label · target (QBO-file/Xero-file/CSV/IIF) · export-code status (mapping-page link) · status · used-by (export batches) | Edit · Deactivate (🔒 IS-1) | — | — |

## Stories

---
id: US-INT-008
epic: EP-INT-03
module: integrations
screens: [S8, S35, S38]
wave: 4
status: draft
blocked_by: []
depends_on: [US-INT-002, US-SHL-006, US-PAY-003, US-PAY-021]
journeys: [J5]
rules: [BR-INT-009, BR-INT-004, BR-INT-003]
golden_tests: []
finance_calc: none
---
### US-INT-008 — Bank & lockbox import connection profiles: per-bank format profile, upload-or-SFTP source

**1 · Details** — As Finance/Owner staff (BR-PAY-019 roles) or a System Admin, I want **import connection profiles** under the Bank & lockbox card (grid addition per CL-1 v1-REAL — field map I-3): one profile per bank/source carrying **label** (e.g. "Chase Operating ••4021", the S38 select's vocabulary — payments P-10), **file format** — BAI2 · CSV · OFX · QBO · QFX (B7 "bank statement import … build seam · v1" + lockbox "Chase BAI2 · BofA CSV" + NFR-20 bank side), **CSV mapping choice** where a bank's CSV layout needs it (validate-then-accept pattern per OQ-040 closure — no mapping memory beyond the profile itself), and **source** — upload (v1 live path: S35 drop zone, S38 step 1) or SFTP (recordable per the A1 addendum method set; credentials via US-INT-002 secrets; scheduled-pull execution = seam provision, I-8) — so that **US-PAY-003** (lockbox staged import) and **US-PAY-021** (bank statement wizard) consume a named, tested profile instead of re-describing the bank each time. The profile parses NOTHING itself — payments owns validation/matching/commit (BR-PAY-023, BR-PAY-019); idempotency stays the flows' law (file+tags, BR-PAY-028/OQ-044). Profile lists render through the shared table framework (US-SHL-006, matrix above). Entry: Bank & lockbox card → profile list. Exit: profiles selectable in S35/S38.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-009 | Bank side v1 = FILE import (BAI2/CSV/OFX/QBO/QFX) via per-bank connection profiles; flows live in payments (BR-PAY-019/023); integrations owns the profile/connection surface only; Plaid direct feed excluded v1. | CONFIRMED — B7 rows (bank import · v1; lockbox seam) + NFR-20 + BR-PAY-019/023 + CL-1 v1-REAL (Plaid → W7 per CL-1/TD-9; payments P-6) |
| BR-INT-004 | File-format parsers sit behind the seam; no bank hardcoded. | CONFIRMED — B7 design rule |
| BR-INT-003 | SFTP credentials on a profile = encrypted secrets, masked refs. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Norma creates "Chase Operating ••4021 · BAI2 · upload" and "BofA Lockbox · CSV (+mapping) · upload" | Profiles listed per the capability matrix; S35 drop-zone copy and S38 "Bank account" select now offer them (prototype vocabulary preserved) |
| TC-2 | US-PAY-003 consumes the Chase profile for `lockbox_2026-08-06_chase.csv` | The lockbox flow runs UNCHANGED (batch → validate → preview → commit, 38 committed · 2 failed per its TC-1); the batch records which profile parsed it; idempotency file+tags untouched (BR-PAY-028) |
| TC-3 | US-PAY-021 consumes it on S38 step 1 | Statement upload parses per the profile's format; auto-match/reconcile stay payments law (BR-PAY-019) — no integrations logic in the flow |
| TC-4 | SFTP source recorded on a profile | Host/path stored, credentials encrypted; profile flagged "source: SFTP (provision)" — upload remains the working v1 path (I-8); no phantom pull job pretends to run |
| TC-5 *(negative)* | File imported against the wrong profile (BofA CSV dropped on the Chase BAI2 profile) | Parse failure surfaces in the flow's per-row validation ("Failed · Retry" family / error report per US-PAY-003) — never a silent mis-parse |
| TC-6 *(negative)* | Priya (Billing Clerk) opens S38 profile management | S37–S40 + finance profiles are Owner/Finance (BR-PAY-019); Settings writes Admin-gated — blocked server-side |
| TC-7 *(secret-handling)* | SFTP profile payloads/logs/audit | Host/path visible; password/key = masked ref only, never echoed (BR-INT-003) |
| TC-8 *(isolation)* | Lone Star Ridge profile list | Its profiles only; Brazos Bend's Chase profile invisible (RLS) |

**4 · Test Data** — Brazos Bend: profiles "Chase Operating ••4021" (BAI2, upload) + "BofA Lockbox" (CSV + saved column mapping, upload) + SFTP fixture sftp.chase.example:/outbox (key ••••K204, provision). Files: `lockbox_2026-08-06_chase.csv` (US-PAY-003 fixture), S38 July statement (US-PAY-021 fixture). Actors: Norma Reyes (Finance), Alex Reed, Priya Menon (negative), J. Okafor (isolation).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Profile label | S8 list / S38 select | prototype S38 ("Chase Operating ••4021") — payments P-10 | bank profile row (r12 #10 family; anchoring = I-2/P-10) | text | user-input | unique per tenant; account numbers masked ••last4 (BR-CUS-045 pattern) |
| File format | S8 list | B7 (BAI2/CSV/OFX/QBO/QFX) + prototype S35/S38 copy | `.format` | enum | user-input | one per profile |
| CSV mapping choice | S8 modal | OQ-040 closure pattern (validate-then-accept) | mapping config jsonb | jsonb | user-input | CSV-format profiles only |
| Source upload/SFTP | S8 modal | A1 addendum method (SFTP-file) + prototype upload zones | `.source` (+ SFTP host/path; creds → secret store) | enum/text | user-input | upload = v1 live; sftp = recorded provision (I-8) |
| Consumption refs | S35/S38 | US-PAY-003/021 §5 | `payment_import_batches` ↔ profile ref (r12 #3/#10) | uuid | system-derived | batch records its profile |
| Used-by count | S8 list | IS-1 audit-lock input | computed over batches | int | computed-display | drives deactivate-only lock (US-INT-010) |

**6 · Acceptance**
- Given profiles, Then S35/S38 flows consume them by name and run exactly as their own stories ratify — integrations added a surface, not behavior.
- Given a wrong-format file or a non-finance role, Then the failure/denial is explicit; given SFTP, credentials are secrets and nothing pretends to pull.
- Given tenants, Then profiles never cross.

**7 · Finance Calculation** — N/A — no money math (the profiles describe files; payments owns every dollar).

**8 · Open Questions** — None.

---
id: US-INT-009
epic: EP-INT-03
module: integrations
screens: [S8, S42, S43]
wave: 5
status: draft
blocked_by: []
depends_on: [US-INT-002, US-LED-016, US-LED-006]
journeys: [J5]
rules: [BR-INT-010, BR-INT-004]
golden_tests: []
finance_calc: none
---
### US-INT-009 — Accounting export target profiles: QBO-file / Xero-file / CSV / IIF + the export-code hand-off

**1 · Details** — As Finance/Owner staff or a System Admin, I want **export target profiles** behind the QuickBooks Online and Xero cards (v1-REAL as FILE targets per CL-1; BR-LED-020 file-v1) plus the generic CSV / IIF targets: each profile = target type (**QBO-file · Xero-file · CSV · IIF** — BR-LED-004's four), label, and the **export-code hand-off pointer** — a readiness readout of the target's codes (`qbo_ref` / `xero_ref` per r13 #5) which LIVE on the Finance account-mapping page (BR-LED-014; ledger D-2: "Settings → Accounting" is superseded — this surface links there, never edits codes) — so that **US-LED-016** (S42/S43) addresses a named target and the S42 Connections panel state (D-7) reads from the connection read-model (US-INT-004 TC-3). The profile changes NOTHING in the handover: one summary JE per period per GL, recorded idempotent batches, missing-ref atomic block all stay BR-LED-004/US-LED-016 law. The card's "Live sync — v2" badge is EP-INT-04's story. Entry: Accounting cards → target list (matrix above). Exit: targets addressable from S43; Connections panel truthful.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-010 | Accounting v1 = FILE/batch export targets (QBO/Xero/CSV/IIF) addressed by mapping-page export codes; direct connect (QBO/Xero OAuth live sync) = v2; integrations owns target/connection profiles only — flows live in ledger. | CONFIRMED — BR-LED-020 (PO L-5 + L-2, 2026-08-08) + BR-LED-004/014 + TD-10 + CL-1 |
| BR-INT-004 | Target types behind the seam; no ERP hardcoded. | CONFIRMED — B7 design rule + NFR-20 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Norma sets up the QBO file target | Profile listed; code-readiness readout shows "42/44 accounts carry qbo_ref — 2 missing" linking to the Finance mapping page (BR-LED-014); no code editable here (D-2 supersession holds) |
| TC-2 | US-LED-016 exports July to the QBO target | Handover runs exactly per its TC-1: batch EXP-2607-QBO recorded, 598.69 balanced, idempotent re-run block — the profile only named the target |
| TC-3 | S42 Connections panel | Reads QBO "Connected (file target)" / Xero "Set up" from the US-INT-004 read-model — D-7 resolved as a read, not a live sync |
| TC-4 *(negative)* | Export attempted to the Xero target with xero_refs missing | Blocked naming the accounts (US-LED-016 TC-5 / US-LED-006 pair) — readiness readout had already shown the gap |
| TC-5 *(negative)* | Attempt to enable "live sync" on the QBO card in v1 | Refused with the v2 label (BR-LED-020; gating law = US-INT-011/012) |
| TC-6 *(secret-handling)* | File targets in v1 | No ERP credential exists to store (files only) — any credential POST against a file target is rejected; nothing to leak, verified in payloads/logs |
| TC-7 *(isolation)* | Lone Star Ridge targets | Its own profiles + its own EXP- series (US-LED-016 TC-7 pair); RLS |

**4 · Test Data** — Brazos Bend: QBO file target (readiness 42/44 → 44/44 after mapping fix), Xero target unconfigured; July export → EXP-2607-QBO, 598.69 (US-LED-016 fixture verbatim). Actors: Norma Reyes, Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Target profile (type + label) | S8 list / S43 | BR-LED-004 four targets + prototype S43 buttons | target profile row (anchoring I-2; export request r13 #4 consumes) | enum/text | user-input | QBO-file \| Xero-file \| CSV \| IIF |
| Export-code readiness | S8 readout | BR-LED-014 + r13 #5 (`qbo_ref`/`xero_ref`) | computed over `ledger_accounts` export-code columns | count | computed-display | read-only pointer to the Finance mapping page (D-2) |
| Connections-panel state | S42 | ledger D-7 + US-INT-004 read-model | service-function read | status | computed-display | file-target truth, no live sync v1 |
| Export batch linkage | S42 history | BR-LED-004 (r13 #4) | `export_batches.target` ↔ profile | enum/uuid | system-derived | idempotency = ledger law, untouched |
| Live-sync badge | S8 card | BR-LED-020 ("direct connect v2") | catalog disposition (US-INT-001) | enum | reference-data | coming-soon v2 |

**6 · Acceptance**
- Given targets, Then S43 addresses them by name, readiness points at the mapping page, and every handover behavior remains ledger law verbatim.
- Given missing codes or a live-sync attempt, Then the block/refusal is explicit with the right pointer (mapping page / v2 label).
- Given tenants, Then targets, readiness and histories never cross.

**7 · Finance Calculation** — N/A — no money math here (the 598.69 worked example is US-LED-016 §7's, consumed unchanged).

**8 · Open Questions** — None.

---
id: US-INT-010
epic: EP-INT-03
module: integrations
screens: [S8]
wave: 5
status: draft
blocked_by: []
depends_on: [US-INT-008, US-INT-009]
journeys: [J5]
rules: [BR-INT-009, BR-INT-010, BR-INT-014, BR-INT-015]
golden_tests: []
finance_calc: none
---
### US-INT-010 — File-channel profile lifecycle: IS-1 deactivate-first, idempotency alignment, audited edits

**1 · Details** — As a System Admin, I want profile lifecycle guardrails on both file-channel lists: **edits are audited** (BR-TEN-016 pattern via US-INT-004 events) and format/mapping changes are **forward-only** — committed import batches and recorded export batches keep the profile version that produced them (append-only law NFR-15/16; a profile edit never restates history); **IS-1 deactivate-first** — a profile with used-by > 0 (referenced by `payment_import_batches` / `export_batches`) can be deactivated (vanishes from S35/S38/S43 pickers) but never deleted (🔒 audit-lock, A1 Settings item 4 law); **idempotency alignment** — deactivate/reactivate/edit NEVER resets the flows' idempotency (file+tags BR-PAY-028/OQ-044; period+target BR-LED-004): a blocked duplicate stays blocked through any profile change; and parse/handover failures keep surfacing in the owning flow with **Failed · Retry** (B7). Entry: profile lists (EP-INT-03 matrix). Exit: safe lifecycle under live financial flows.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-009/010 *(lifecycle extension)* | Profiles referenced by recorded batches deactivate, never delete; history keeps its producing profile ref. | CONFIRMED — IS-1 deactivate-first + A1 Settings item 4 audit-lock + NFR-15 append-only |
| BR-INT-014 | Profile CRUD writes audit_log. | CONFIRMED — BR-TEN-016 + CLAUDE.md #7 principle |
| NFR-16 *(consumed)* | Import/export idempotency records are law and survive any connection/profile change. | CONFIRMED — B6 (BR-PAY-028, BR-LED-004, OQ-044) |
| BR-INT-015 | Flow failures surface Failed · Retry in the owning flow. | CONFIRMED — B7 design rule |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Edit the BofA CSV mapping after 3 committed batches | Edit audited with before/after mapping; the 3 batches keep their original parse record; only FUTURE imports use the new mapping |
| TC-2 | Deactivate "Chase Operating ••4021" (used-by 12) | Deactivated: gone from S35/S38 pickers, history intact, 🔒 delete blocked with the used-by count (IS-1); reactivation restores it |
| TC-3 *(negative — idempotency)* | Deactivate → reactivate the Chase profile, then re-import `lockbox_2026-08-06_chase.csv` with the same tags | STILL blocked with who/when/link (BR-PAY-028/OQ-044) — profile lifecycle never launders a duplicate; same for a July re-export after target-profile edits (BR-LED-004 block holds) |
| TC-4 *(negative)* | Delete attempted on a used profile via direct API | Rejected server-side (IS-1 enforcement is server-side per IS-6 principle) |
| TC-5 | Unused profile (used-by 0) | Hard delete allowed per IS-1; audited |
| TC-6 *(secret-handling)* | Audit rows for SFTP-profile edits | Host/path/mapping in before/after; credential = masked ref only (BR-INT-003) |
| TC-7 *(isolation)* | Lifecycle actions on Brazos Bend profiles | Zero effect on Lone Star Ridge lists/batches (RLS) |

**4 · Test Data** — Brazos Bend: BofA CSV profile mapping edit Aug 12 (3 prior batches); Chase profile used-by 12 → deactivate/reactivate cycle; duplicate re-import fixture = US-PAY-003's file + tags; unused fixture "Frost Bank · OFX" (used-by 0, deleted). Actors: Alex Reed, Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Profile status active/inactive | S8 lists | IS-1 + A1 Settings item 4 | `.status` on profile rows (🔒 I-2) | enum | user-input | deactivate always; delete only used-by = 0 |
| Used-by count | S8 lists | IS-1 audit-lock input | computed over batch references | int | computed-display | drives the lock |
| Producing-profile ref on history | S35/S42 histories | NFR-15 append-only | batch rows keep profile ref + version | uuid | system-derived | never restated by edits |
| Idempotency records | — | BR-PAY-028 / BR-LED-004 / OQ-044 (NFR-16) | flows' unique keys — untouched by this module | — | system-derived | survive all profile lifecycle |
| CRUD audit | — | BR-TEN-016 | `audit_log` `integration.updated` family | jsonb | system-derived | before/after, masked |

**6 · Acceptance**
- Given a referenced profile, Then it deactivates but never deletes, and every recorded batch keeps its producing profile.
- Given any lifecycle churn, Then no duplicate import/export that idempotency blocked becomes possible.
- Given edits, Then audit shows before/after with masked credentials only.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.
