# EP-NOT-02 — Template designers & the rendering engine (every document from a versioned, pinned template)

**Module:** notifications · **Wave:** W3 · **Screens:** S8 (Settings → Reference data → Document & message templates), S94–S96 (printable notice/receipt designers), S97–S102 (email designers), S103–S106 (SMS designers) · **Status:** draft (rules ratified: A19 r8 rules 1–6 + addenda; BR-BIL-025/026/027 applied to every designer S91+ per A19 addendum b; BR-NOT-001..004)

## Scope
**In:** the **rendering engine** — template version + typed merge context → rendered artifact (PDF / subject+preheader+body / SMS text), money 2dp, dates per tenant Regional settings (A19 header), identity stamped at render, issued documents never re-rendered (BR-TEN-017); **merge-variable catalogs per template type** (A19 token sets + variable palette, A19 addendum r8); the **version lifecycle** draft→published→archived with the ratified **rights split**, **pinning contract** and **undeletable-pinned audit-lock generalized to every designer S91+** (BR-BIL-026/027 via A19 addendum b) + effective-dated contract versions (BR-NOT-002); **category assignment + account-override consumption** (BR-BIL-025 resolution, BR-TEN-041 templates-card upgrade); designers **S94 disconnect · S95 dunning · S96 receipt** (printable), **S97–S102 email**, **S103–S106 SMS** with live segment counter; **send-test flows**.
**Out:** bill/statement designers S91–S93 + bill pinning at issue (billing — US-BIL-021/022) · contract designers S67 content + generation (EP-NOT-03/US-NOT-012 — lifecycle rules here apply to them) · when-to-send triggers (A15 owners: billing/payments/customers) · queue + dispatch (EP-NOT-01) · exact template-version DDL (Eng-Lead 🔒).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Templates card (notice/email/SMS/contracts groups) | template name | group (printable/email/SMS/contracts), category, status (draft/published/archived) | group, then name asc | name, group, updated | Name · Group · Channel · Category · Published vN · Draft? · Updated / +pinned-by count (IS-5) | Design (→ S94–S106, S67) · Publish (Admin) · Archive · History · Send test | — | — |

## Stories

---
id: US-NOT-005
epic: EP-NOT-02
module: notifications
screens: [S8]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-021, US-BIL-022]
journeys: [J2]
rules: [BR-BIL-026, BR-TEN-017]
golden_tests: []
finance_calc: none
---
### US-NOT-005 — The rendering engine + merge-variable catalogs per template type

**1 · Details** — As the system, I want ONE rendering engine: `render(template code, pinned version, context)` → artifact — PDF for printable classes, subject + preheader + HTML body for email, plain text for SMS — with a **typed merge-variable catalog per template type** (A19 token sets: bill meta/summary/per-service tokens; disconnect {balance}/{cut_date}/{reconnect_fee}/{state_puc_ref}; receipt {amount}/{confirmation}/{balance}; reminder/receipt preview tokens per A13) surfaced as the designers' **variable palette** (A19 addendum r8). Rendering rules from ratified spec: all money renders **2dp**, dates render per tenant **Regional settings** (A19 header); utility identity/brand/remittance values are **stamped at render** and issued documents are **never re-rendered** (BR-TEN-017); every render at dispatch/reprint uses the row's **pinned version** (BR-BIL-026 — applies to every designer S91+ per A19 addendum b); the statement class always carries the "nothing is due" disclaimer (A19 rule 1); dunning carries no regulatory footer (A19 rule 2). Entry: dispatcher (US-NOT-002), reprint/re-send actions, test flows. Exit: rendered artifact per channel.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-026 *(generalized)* | Every render uses the pinned template version — applies to every designer S91+ (A19 reports-audit addendum b). | CONFIRMED — PO Lane B-7 + A19 addendum, 2026-08-08 |
| BR-TEN-017 | Identity values stamped at issue/render; edits affect future documents only — issued documents never re-rendered. | CONFIRMED — PO R2-A1 |
| A19 header | Money 2dp; dates per tenant Regional settings. | CONFIRMED — A19 (ratified spec) |
| A19 rules 1–2 | Statement ≠ bill ("nothing is due" line mandatory); dunning ≠ disconnect notice (no regulatory footer on dunning). | CONFIRMED — A19 r8 "rules that fall out" |
| Token-catalog validation | A template body may only use tokens from its type's catalog (the variable palette IS the catalog). | PROPOSED — derived from A19 addendum "variable palette" + A19 typed token lists |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Render receipt for PMT-2608-0455 ($247.30, conf RCT-2608-0455) | PDF shows one transaction — amount $247.30 (2dp), method, confirmation, applied-to bill, balance before/after, processed-by; NO usage, NO rates, NO due date (A19 r8 receipt row) |
| TC-2 | Render disconnect tier 2 for A-11024 | "FINAL REMINDER… reconnect fee of $45.00" — {balance}, {cut_date} Aug 18 2026, {reconnect_fee} from the tenant charge code, dates in the tenant's format |
| TC-3 | Tenant Regional format = DD/MM/YYYY | Same template renders 18/08/2026 — format from Settings, never hardcoded |
| TC-4 | Identity change after issue | Documents rendered before the change keep their stamped identity on reprint; new renders carry the new identity (BR-TEN-017; US-TEN-005/TC-3 pair) |
| TC-5 *(negative)* | Draft saved with token {meter_no} in the receipt body | Save/test-render rejects — {meter_no} is not in the receipt type's catalog (palette-enforced, server-validated) |
| TC-6 *(negative)* | Render requested "on latest version" for an issued document | No such path — pinned version only (BR-BIL-026; US-BIL-022 TC-4 pair) |
| TC-7 *(isolation)* | Render for Lone Star Ridge | Uses its own templates, identity and formats; Brazos Bend template versions unreachable (RLS) |

**4 · Test Data** — Brazos Bend: receipt fixture PMT-2608-0455 $247.30 / RCT-2608-0455, balance $412.80 → $165.50; disconnect fixture A-11024 Ridge Coffee, balance $1,842.10, cut date Aug 18 2026, RECON charge code $45.00. Regional fixtures: en-US `Mon D, YYYY` vs DD/MM/YYYY. Identity-change fixture: support phone updated Sep 1. Isolation: Lone Star Ridge receipt v1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Render inputs (code, version, context) | — | BR-BIL-026 + A19 | template version rows (r10 #4 pattern for all designer classes — DDL Eng-Lead 🔒) | ref | system-derived | pinned version only |
| Merge-variable catalog per type | S94–S106 palette | A19 token lists + addendum ("variable palette") | typed catalog per template class | list | reference-data | tokens outside catalog rejected |
| Money rendering | rendered artifact | A19 header ("all money 2dp") | display formatting at render (CLAUDE.md #2 — round at display) | text | computed-display | 2dp |
| Date rendering | rendered artifact | A19 header + S8 Regional & Formats | tenant Regional settings read | text | computed-display | tenant format |
| Identity stamp | rendered artifact | BR-TEN-017 | company identity values at render; issued docs keep theirs | text | system-derived | never re-rendered |
| Statement disclaimer | rendered artifact | A19 rule 1 | statement-class content requirement | text | reference-data | mandatory on the class |

**6 · Acceptance**
- Given a render, Then the pinned version + typed context produce the artifact with 2dp money and tenant-format dates.
- Given an issued document, Then reprints render byte-stable — pinned version + stamped identity.
- Given a token outside the type's catalog, Then save/test-render fails with a clear error.
- Given tenants, Then templates, identity and formats never cross.

**7 · Finance Calculation** — N/A — no money math (templates render money; they never compute it — US-BIL-021 §7 principle).

**8 · Open Questions** — None.

---
id: US-NOT-006
epic: EP-NOT-02
module: notifications
screens: [S8, S67]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-021, US-TEN-010]
journeys: [J2]
rules: [BR-BIL-025, BR-BIL-026, BR-BIL-027, BR-NOT-002]
golden_tests: []
finance_calc: none
---
### US-NOT-006 — Version lifecycle, publish rights, pinning + category assignment — for EVERY designer S91+

**1 · Details** — As a Billing Clerk I create/edit **draft** versions of any notification-owned template (notices S94–S95, receipt S96, email S97–S102, SMS S103–S106, contracts S67) and run test renders; as a System Admin I **publish** (one published version per template) and archive — the ratified rights split (BR-BIL-027) applied to every designer S91+ (A19 addendum b). Every edit = a new **append-only** version (draft→published→archived, audited — A19 rule 6: versioned + audit-logged, header shows version + last-edited date); a version **pinned by any issued document, sent message or signed contract can never be deleted** (audit-lock, BR-BIL-027 + BR-NOT-002); publishing affects only FUTURE renders (BR-BIL-026). **Contract templates are effective-date versioned** (BR-NOT-002): generation picks the version in effect on the generation date; a signed contract permanently references the exact version used. **Category assignment** on the templates card (BR-TEN-041 upgrade; BR-BIL-025 pattern): defaults by consumer category (residential/commercial/industrial/govt), account-override consumed at resolution (r12 #14 D-4). Entry: S8 templates card → designers. Exit: published versions available to render resolution (US-NOT-005) and generation (EP-NOT-03).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-026 *(generalized)* | Edit = new version; version pinned at issue/send; publishing affects only future renders — applies to every designer S91+. | CONFIRMED — PO Lane B-7 + A19 addendum b |
| BR-BIL-027 *(generalized)* | Clerk drafts + test-renders; System Admin publishes; a pinned version can never be deleted (audit-lock). | CONFIRMED — PO Lane B-8 + A19 addendum b |
| BR-NOT-002 | Contract templates effective-date versioned; a generated/signed contract permanently references the exact template version used. | CONFIRMED — PO 2026-08-08 |
| BR-BIL-025 | Assignment defaults by consumer category, overridable per account. | CONFIRMED — PO Lane B-6, 2026-08-08 |
| A19 rule 6 | Every template versioned + audit-logged; header shows version + last-edited date. | CONFIRMED — A19 r8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya edits "Past-due reminder" email | New draft v3 append-only (v2 published untouched); designer header shows "v3 · edited Aug 9, 2026"; save audited |
| TC-2 | Priya attempts Publish; Alex publishes | Clerk publish server-rejected; Admin publish → v3 published, v2 auto-archived (one published per template); only renders AFTER see v3 |
| TC-3 | Contract effective-dating (BR-NOT-002) | Service-agreement v2 effective Sep 1; generation Aug 20 renders v1, generation Sep 2 renders v2; a contract signed on v1 references v1 forever |
| TC-4 | Category assignment + override | Service-agreement default variant by category; ACC-9001 override → commercial resolution order account-override → category default (BR-BIL-025) |
| TC-5 *(negative)* | Delete attempted on receipt v1 (pinned by 3,412 sent receipts) | Blocked forever — audit-lock; archive allowed (US-BIL-021 TC-4 pair); an unpinned draft deletes fine |
| TC-6 *(negative)* | Direct UPDATE of a published version's body | Rejected — versions are append-only rows; edits create drafts |
| TC-7 *(isolation)* | Lone Star Ridge template list | Its own versions only; Brazos Bend's invisible (RLS) |

**4 · Test Data** — Brazos Bend: "Past-due reminder" email v2 published / v3 draft; receipt v1 pinned by 3,412 sends; service agreement v1 (effective Jan 1 2026) / v2 (effective Sep 1 2026); category map + override fixture ACC-9001 → commercial. Actors: Priya Menon (drafts), Alex Reed (publishes). Isolation: Lone Star Ridge "Receipt" v1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Template + group + channel + category | S8 card | A19 r8 (16 templates) + BR-NOT-004 (+4 contracts) + BR-BIL-025 | notification template registry (base `notification_templates` — r8 designer extension, DDL Eng-Lead 🔒; see field-map discrepancy D-1) | rows | user-input | groups per A19/S67 |
| Version rows + status | designers | BR-BIL-026 + A19 rule 6 | append-only version rows draft\|published\|archived (r10 #4 pattern) | rows | user-input | edit = new row; one published |
| Effective date (contracts) | S67 | BR-NOT-002 | effective_from on contract template versions | date | user-input | generation picks version in effect |
| Publish action | S8 | BR-BIL-027 | status transition, Admin-gated | enum | user-input | server-enforced role |
| Pin refs (audit-lock) | — | BR-BIL-027 + BR-NOT-002 | pinned-by refs: `invoices.template_version`, `outbound_messages` version ref, signed contracts | — | system-derived | delete blocked while pinned |
| Account override consumption | resolution | BR-BIL-025 + r12 #14 (D-4) | `accounts.template_override_id` (customers-owned read) | uuid | reference-data | override → category default |
| Version audit | — | A19 rule 6 + CLAUDE.md #7 | `audit_log` `template.saved/published/archived` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given any designer S91+, Then edits create append-only drafts, only Admins publish, and exactly one version is published per template.
- Given a pinned version (bill, sent message, or signed contract), Then delete is impossible forever.
- Given contract generation on date D, Then the version in effect on D renders, and signing freezes that reference permanently.
- Given category defaults + account overrides, Then resolution picks override → category default, tenant-scoped.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-NOT-007
epic: EP-NOT-02
module: notifications
screens: [S8, S94, S95, S96]
wave: 3
status: draft
blocked_by: []
depends_on: [US-NOT-005, US-NOT-006]
journeys: [J4]
rules: [BR-BIL-027, BR-CUS-039, BR-REP-016]
golden_tests: []
finance_calc: none
---
### US-NOT-007 — Printable designers: S94 disconnect (3 tiers + regulatory footer) · S95 dunning (3 stages) · S96 receipt

**1 · Details** — As a Billing Clerk, I want the three notification-owned **printable designers** — paper preview + variable palette + per-template options, each with true-to-life distinct content (A19 r8): **S94 Disconnect notice** — tier banner (10-day / 5-day / **48-hour final**), certified-mail number block, "how to stop this" 3-column block, and the **regulatory rights footer** (dispute rights, medical hold physician-certified 60-day renewable, weather suppression <32°F / >100°F, weekend/holiday suppression, PUC complaint line) with tier content per A19 §2 ({balance}, {pay_by_date}, {cut_date}, {reconnect_fee}, {state_puc_ref}); **S95 Dunning 1/2/3** — a **reminder, not a legal notice**: stage banner (day 7 friendly / day 14 firm / day 30 final — **seeded defaults of the tenant-config cadence**, BR-REP-016), unpaid-bill table with days-late, late-fee line, payment-plan offer, NO regulatory footer (A19 rule 2); **S96 Receipt** — one transaction: amount, method, confirmation number, applied-to bill, balance before/after, processed-by — no usage, no rates, no due date — plus **test-print** with sample data (Clerk right, BR-BIL-027). Entry: S8 templates card → Design. Exit: published versions consumed by notice generation (EP-NOT-03).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-039 *(content source)* | Disconnect tiers render A19 §2 content; certified mail on final; reconnect fee from tenant charge codes (BR-BIL-007), never hardcoded. | CONFIRMED — PO closure batch, 2026-08-08 |
| BR-REP-016 | Dunning 1/2/3 = reminder stages of the BR-PAY-017 sequence; day numbers 7/14/30 are SEEDED DEFAULTS of the tenant-config cadence. | CONFIRMED — PO RQ-8, 2026-08-08 |
| A19 rule 2 | Dunning is a courtesy reminder with no regulatory footer; the disconnect notice is regulated and tiered. | CONFIRMED — A19 r8 |
| BR-BIL-027 *(generalized)* | Clerk drafts + test-prints; Admin publishes (A19 addendum b). | CONFIRMED — PO Lane B-8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open S94 designer | Tier selector renders all 3 banners; final tier preview shows certified-mail block, medical/critical-care line, {state_puc_ref} + full regulatory footer (dispute rights · medical hold 60-day renewable · <32°F/>100°F · weekend/holiday · PUC line) |
| TC-2 | Open S95 designer | Stage banners read from the tenant cadence config (seeded 7/14/30); unpaid-bill table with days-late + late-fee line + plan offer in preview |
| TC-3 | Tenant cadence changed (S70 collections rules) | S95 stage banners re-render from config — day numbers are seeds, not constants (BR-REP-016) |
| TC-4 | S96 receipt preview | One transaction only; balance before/after; processed-by staff name; NO due date/usage/rates (A19 r8) |
| TC-5 | Test-print (Priya) | Sample-data render; no delivery row, no money event (US-BIL-021 TC-1 pattern) |
| TC-6 *(negative)* | Regulatory footer removed from the dunning draft — fine; regulatory footer removed from the DISCONNECT draft | Dunning: allowed (rule 2 — it never has one). Disconnect: save rejected — the footer is a mandatory block of the regulated notice class (A19 r8 disconnect row) |
| TC-7 *(isolation)* | Lone Star Ridge designers | Its own template set; Brazos Bend previews/versions unreachable (RLS) |

**4 · Test Data** — Brazos Bend: disconnect v2 (TX {state_puc_ref} fixture), dunning v1 (cadence seeded 7/14/30; changed-fixture 10/20/35), receipt v1. Sample data: A-11024 Ridge Coffee $1,842.10, cut date Aug 18 2026, RECON $45.00; receipt sample PMT-2608-0455 $247.30. Actors: Priya Menon, Alex Reed. Isolation: Lone Star Ridge.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Disconnect tier content blocks | S94 | A19 §2 + A19 r8 row | template body per tier (version rows, US-NOT-006) | text | user-input | 3 tiers; footer mandatory |
| Regulatory footer block | S94 | A19 r8 (disconnect row) | mandatory block on the disconnect class | text | reference-data | non-removable on this class |
| Certified-mail number block | S94 | A19 r8 | token block ({certified_no} at dispatch — provider response, r10 #8) | text | integration | final tier |
| Dunning stage banners + day numbers | S95 | BR-REP-016 | render from tenant cadence config (S70, r14 #5 keys) | int/text | reference-data | seeded 7/14/30 |
| Unpaid-bill table + late-fee line | S95 | A19 r8 (dunning row) | merge tokens over open invoices context | table | computed-display | days-late per context |
| Receipt fields | S96 | A19 r8 (receipt row) | receipt token catalog (US-NOT-005) | tokens | reference-data | no due date/usage/rates |
| Test-print | S94–S96 | BR-BIL-027 | rendered preview only | pdf | computed-display | no delivery row |

**6 · Acceptance**
- Given the three designers, Then each opens with its distinct A19 r8 content and a true-to-life preview.
- Given the dunning designer, Then stage day numbers come from tenant config (seeds 7/14/30) and no regulatory footer exists on the class.
- Given the disconnect designer, Then tiers, certified block and the regulatory footer are present and the footer cannot be removed.
- Given test-print, Then a sample render appears with no delivery or money effect.

**7 · Finance Calculation** — N/A — no money math (late-fee/balance amounts arrive in the merge context from billing/payments).

**8 · Open Questions** — None.

---
id: US-NOT-008
epic: EP-NOT-02
module: notifications
screens: [S8, S97–S102, S103–S106]
wave: 3
status: draft
blocked_by: []
depends_on: [US-NOT-005, US-NOT-006]
journeys: [J2, J4]
rules: [BR-BIL-026, BR-CUS-039]
golden_tests: []
finance_calc: none
---
### US-NOT-008 — Email designers (S97–S102) + SMS designers with segment counter (S103–S106) + send-test

**1 · Details** — **Deferred-wave note: the designers, previews and rendering are v1; live send-test over email defers → W6 (connected mailbox), over SMS → v1.1 (Twilio seam) — v1 send-test = rendered preview, no provider call.** As a Billing Clerk, I want the six **email designers** — subject + preheader + rendered body + merge fields, each with A19 r8 distinct content: Bill ready (usage breakdown, **year-over-year comparison**, pay button + PDF link, autopay reminder), Payment receipt (confirmation, applied-to, balance now, next bill date — shortest), Past-due reminder (**three tones friendly/firm/final selected at send time**, plan offer), Plan change confirmation (before/after table, base-rate delta, estimated bill impact, deposit change, "did not request this?" line), Credit issued (**clerk's memo as the customer-visible reason**, reference number), Statement email (period summary table, statement PDF attach, explicit "not a bill" line — A19 rule 1) — and the four **SMS designers** — phone-bubble preview + **live character/segment counter with the 160-character segment limit surfaced (going over doubles the per-message cost — A19 rule 5)**: Bill ready (amount, due date, short pay link, STOP opt-out; skipped on autopay), Past-due (amount, days late, link **plus phone number**), Disconnect (**leads with URGENT**, service address + cut date; **supplements the mailed notice, never replaces it** — A19 rule 3), Payment received (shortest). Entry: S8 templates card → Design. Exit: published versions for W6/v1.1 dispatch + v1 rendering.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| A19 r8 (email/SMS tables) | Six email + four SMS templates, each with the distinct content listed — not variations of one layout. | CONFIRMED — A19 r8 revision |
| A19 rule 5 | 160-character segment limit surfaced live in the SMS editor. | CONFIRMED — A19 r8 |
| A19 rule 3 / BR-CUS-039 | SMS never stands alone for disconnection — the certified letter is the legal instrument; SMS supplements. | CONFIRMED — A19 r8 + PO closure batch |
| A19 rule 1 | Statement email must say nothing is due. | CONFIRMED — A19 r8 |
| BR-BIL-026 *(generalized)* | Versioning/pinning per US-NOT-006 applies to all ten designers. | CONFIRMED — A19 addendum b |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open Bill-ready email designer | Subject/preheader/body panes + merge fields; preview shows usage breakdown + YoY line ("12% more electricity") + pay button/PDF link + autopay reminder |
| TC-2 | Credit-issued designer | Preview renders the clerk memo token as the customer-visible reason + reference number (A19 r8) |
| TC-3 | SMS counter live | Past-due body at 138 chars → "1 segment"; typing to 161 → "2 segments — doubles per-message cost" warning, live (A19 rule 5) |
| TC-4 | Disconnect SMS preview | Leads URGENT, names {service_address} + {cut_date}, carries the supplements-the-letter note on the designer (rule 3) |
| TC-5 | Send-test pre-W6 | Rendered preview with sample data; NO mailbox/ESP/Twilio call (deferred-wave note); at W6, send-test emails via the tenant's connected mailbox |
| TC-6 *(negative)* | Statement-email draft saved without the "not a bill" line | Rejected — mandatory class content (A19 rule 1); customers must never pay twice |
| TC-7 *(negative)* | Bill-ready SMS for an autopay customer in a render context | Skip signal per A19 r8 ("skipped when the customer is on autopay") — no queue row requested by the trigger owner |
| TC-8 *(isolation)* | Lone Star Ridge designers | Own versions/previews only (RLS) |

**4 · Test Data** — Brazos Bend samples straight from A19 r8: "Your Silver Creek Water bill is ready — $247.30 due Aug 25" subject pattern adapted to tenant; past-due $412.80; credit $15.00 with memo "Overcharge on July bill — apologies"; SMS bodies 103/138/156/99 chars; 161-char overflow fixture. Actors: Priya Menon, Alex Reed. Isolation: Lone Star Ridge SMS "Payment received" v1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Subject + preheader + body | S97–S102 | A19 r8 (email table) | email template version rows (US-NOT-006) | text | user-input | subject required |
| Tone variants (past-due) | S99-class designer | A19 r8 ("three tones selected at send time") + BR-PAY-035 | tone-variant bodies on the past-due template | text | user-input | 3 tones, no free text (US-NOT-010) |
| SMS body + counter | S103–S106 | A19 rule 5 | SMS template version rows; counter computed | text/int | user-input / computed-display | segment math live |
| STOP opt-out line | S103 | A19 r8 (SMS table) | body content requirement | text | reference-data | on customer SMS classes |
| Statement "not a bill" line | statement email | A19 rule 1 | mandatory class content | text | reference-data | save-blocked without it |
| Autopay-skip signal | — | A19 r8 (bill-ready SMS) | render-context flag (customers-owned autopay read) | flag | reference-data | trigger owner skips the row |
| Send-test | designers | A19 addendum (test email on connect) + OQ-073 closure | v1 preview; W6 via connected mailbox | pdf/html | computed-display / integration | no provider call pre-W6 |

**6 · Acceptance**
- Given the ten designers, Then each opens with its A19 r8 distinct content and live preview; SMS editors show live segment counts with the 160-char limit surfaced.
- Given the statement email, Then the "not a bill" line is mandatory; given disconnect SMS, Then it supplements the mailed notice, never replaces it.
- Given send-test in v1, Then a rendered preview appears and no provider is called; at W6 email send-test uses the tenant's own mailbox.
- Given tenants, Then designers and versions never cross.

**7 · Finance Calculation** — N/A — no money math (YoY %, bill impact etc. arrive computed in the merge context from their owner modules).

**8 · Open Questions** — None.

---
```yaml
id: US-NOT-016
epic: EP-NOT-02
module: notifications
screens: [S91, S92]
wave: 3
status: draft
blocked_by: []           # was [OQ-075]; CLOSED 2026-08-10. Cleared 2026-08-15 (DEF-104)
depends_on: [US-BIL-028, US-TEN-015]
journeys: []
rules: [BR-NOT-012]
golden_tests: []
finance_calc: none
```
### US-NOT-016 — Custom fields as template variables (rendered from the snapshot)

**1 · Details** — As a System Admin authoring a bill or notice template, I want to place my own fields in the document, so that our bills carry the reference numbers our customers actually quote back to us. The variable picker offers `{{account.custom.<key>}}` alongside the platform's variables. **Rendering resolves against the invoice's stamped snapshot (US-BIL-028), never against live master data** — that is what keeps a reprint identical to the original.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-NOT-012 | Custom-field variables resolve **only** from `invoices.custom_snapshot` (or the notification's own stored render context for non-invoice notices). A missing or deactivated key renders the **empty string** — never `None`, never `undefined`, and never a leaked `{{…}}`: a customer-facing document must not show a template artifact. Values are escaped on render like any tenant-authored text, in HTML and in PDF alike | PROPOSED — derives from BR-NOT-006 (pinned template+version+language), DB-9, CLAUDE.md #4 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Template contains `{{account.custom.service_class}}`; bill issued with snapshot "Commercial" | Document renders "Commercial" |
| TC-2 | Master data edited to "Irrigation" after issue; **reprint** the same bill | Still "Commercial" — reprint reproducibility holds (BR-NOT-006) |
| TC-3 | Template references a key absent from the snapshot | Renders empty. No `{{…}}`, no "None", no exception, and the rest of the document is unaffected |
| TC-4 | Field deactivated after the bill was issued | Historical reprint still renders the snapshotted value |
| TC-5 (neg) | Custom value containing `<script>alert(1)</script>` | Escaped in HTML and PDF output; no executable content in either |
| TC-6 (neg) | Template author references a key from another entity's namespace | Picker does not offer it; a hand-typed one renders empty rather than reaching across |
| TC-7 | Non-invoice notice (e.g. a reminder) | Resolves from the notification's stored render context, fixed at send |
| TC-8 (isolation) | Lone Star Ridge template referencing a Brazos Bend key | Renders empty. No cross-tenant resolution path exists |

**4 · Test Data** — Brazos Bend bill template v3 with `{{account.custom.service_class}}` in the header block; invoice `INV-2026-09-0042` snapshot `{"account.service_class": "Commercial"}`. XSS fixture: an account whose `site_note` holds `<script>alert(1)</script>`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Variable token | S91/S92 designer | GAP — PO 2026-08-10 | `notification_templates` body (existing) | text | user-input | `{{<entity>.custom.<key>}}`; key must exist in the tenant registry at author time |
| Resolved value | rendered document | GAP | `invoices.custom_snapshot ->> '<entity>.<key>'` | text | computed-display | missing → empty string; always escaped |

**6 · Acceptance** — **Given** a published template referencing a custom field and an invoice issued while that field held "Commercial", **when** the account's value is later changed and the bill is reprinted, **then** the reprint still reads "Commercial" — and a template referencing a key that no longer exists renders an empty space rather than a broken token.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-075 | Deactivating a field a **published** template references: warn (listing affected templates) or block? Historical documents are safe either way; new ones would render empty | the deactivate branch in US-TEN-017 | Product Owner | **OPEN** |
