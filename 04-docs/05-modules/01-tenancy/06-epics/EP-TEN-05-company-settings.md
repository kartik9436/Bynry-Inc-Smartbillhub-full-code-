# EP-TEN-05 — Settings → Company (profile · regional, formats & fiscal)

**Module:** tenancy · **Wave:** W0 · **Screens:** S8 (Settings → Company, 2 sub-tabs — A1 addenda 2026-08-07 "Settings module rework" + r7 tab order, split per module overview v4) · **Status:** draft

## Scope
**In:** the two Company sub-tabs. **Company profile**: Utility details (legal name, DBA, EIN, state utility ID, mailing address, support phone/email, website) · Brand (logo drop-zone, primary/bill-accent colors, letterhead preview) · Remittance (remit-to address, payable-to, customer-service hours) feeding the bill stub (A19 §1.8). **Regional, formats & fiscal calendar**: Location & language (country, state, timezone, language, first day of week) · Formats (currency, number/date/time format, live preview) · Fiscal calendar (FY start, accounting method, close cadence, close-by day, current-period card, lock-closed-periods toggle). Sticky Save/Discard footer per tab; "Changing these does not restate historical bills."
**Out:** Users & roles (identity module), Routes & Cycles (metering), Reference data (EP-TEN-07), Numbering (EP-TEN-08), Security, Notifications, Integrations, Billing plan (S107–S109, wave 8). Period-close *enforcement* (ledger module — gated by OQ-033).

## Capability matrix (list screens only — B9 conformance)
None — both sub-tabs are form panels, not lists.

## Stories

---
```yaml
id: US-TEN-005
epic: EP-TEN-05
module: tenancy
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001]
journeys: []
rules: [BR-TEN-016, BR-TEN-017, BR-TEN-018, BR-TEN-019, BR-TEN-024]
golden_tests: []
finance_calc: none
```
### US-TEN-005 — Company profile tab (utility details · brand · remittance)

**1 · Details** — As a System Admin, I want to maintain my utility's legal identity, brand, and remittance details, so that every bill, notice, statement, and email renders with the right name, logo, and "send checks here" stub. Entry: Settings → Company → Company profile (also deep-linked from the post-signup checklist, US-TEN-003). Exit: Save (toast + audit) or Discard. Footer shows "Last edited by {user} · {date}".

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-017 | Company identity/brand/remittance values are stamped onto documents **at issue time**; edits affect future documents only — issued invoices, notices, and statements are never re-rendered with new values | PROPOSED — derived from CLAUDE.md #4 financial immutability + the regional-tab principle "does not restate historical bills" (prototype-extracted) |
| BR-TEN-018 | EIN: input accepts `NN-NNNNNNN`; stored as 9 digits; v1 validation is format-only (9 digits, hyphen after 2) — no IRS verification; handled as PII under the B2 §6 encryption decision (OQ-016) | PROPOSED — standard US practice; verification service is out of v1 scope |
| BR-TEN-019 | ⚠ **SUPERSEDED 2026-10-27 (`DEF-TEN-10618`): PNG or JPG ≤ 2 MB; SVG refused in the browser and by the server; a stored SVG logo is served as its PNG copy — see `02-business-rules.md` BR-TEN-019.** Was: Logo: SVG or PNG, max 2 MB (prototype-extracted, S8 drop-zone copy); SVG is sanitized server-side and rasterized for PDF/print output; brand colors must be valid `#RRGGBB` hex; letterhead preview renders live from current unsaved values | PROPOSED — file constraints are design-stated; sanitization derived from standard SVG-XSS practice |
| BR-TEN-024 | Sticky Save/Discard footer: edits stage client-side; Save commits the whole tab atomically (one audit_log row with before/after); Discard reverts all; navigating away with unsaved changes prompts | PROPOSED — derived from prototype Save/Discard buttons + IS-6 confirm/toast/audit chain |
| BR-TEN-016 | Save writes `audit_log` (`settings.company_profile.updated`) | PROPOSED — see EP-TEN-03 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Fill all Utility-details fields for Brazos Bend and Save | Toast confirmation; values persist; footer shows "Last edited by Dana Whitfield · Aug 8, 2026"; audit row holds before/after |
| TC-2 | Upload 180 KB SVG logo, set colors #1B5E9E / #201E1D | Letterhead preview updates before saving; logo appears on the next generated bill PDF, not on previously issued ones |
| TC-3 | Edit remit-to to "PO Box 2210, Katy, TX 77492", Save, then issue a new bill | New bill stub shows the new remit-to; a bill issued yesterday re-downloaded shows the old remit-to (BR-TEN-017) |
| TC-4 (neg) | EIN entered as `74-31826` (8 digits) or `743182640X` | Inline validation error "Enter as NN-NNNNNNN"; Save blocked for the field |
| TC-5 (neg) | Upload 4.8 MB PNG, then an .svg containing `<script>` | 2 MB limit rejects the first; sanitizer strips/rejects the script payload on the second; neither is stored |
| TC-6 (neg) | Edit fields, click another Settings tab without saving | Unsaved-changes prompt (stay / discard); Discard restores server values |
| TC-7 (isolation) | Lone Star Ridge admin opens Company profile | Sees only Lone Star Ridge values; Brazos Bend's EIN/logo never readable cross-tenant |

**4 · Test Data** — Legal name "Brazos Bend Utility District No. 1" · DBA "Brazos Bend Utilities" · EIN 74-3182640 · Utility ID (state) "TX CCN 13148 / PUCT 10238" · Mailing "9410 FM 1093 Rd, Katy, TX 77494" · Support +1 (281) 555-0164 / help@brazosbendutilities.com · Website brazosbendutilities.com · Logo `bbu-logo.svg` 180 KB · Primary #1B5E9E · Bill accent #201E1D · Remit-to "PO Box 2210, Katy, TX 77492" · Payable to "Brazos Bend Utilities" · Hours "Mon–Fri 8–5 CT".

**5 · Data Fields / Mapping** (all origin **user-input** unless noted; B2 `tenants` today has only name/subdomain/state/currency/tax_region — the rest are proposed columns)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Legal name | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.legal_name | text | user-input | required for checklist-complete |
| Doing business as | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.dba_name | text | user-input | optional |
| Tax ID (EIN) | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.ein (PII — OQ-016 policy) | text (9 digits) | user-input | BR-TEN-018 |
| Utility ID (state) | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.state_utility_id | text | user-input | free text ≤40 |
| Mailing address | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.mailing_address | text | user-input | required for checklist-complete |
| Support phone / email | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.support_phone / tenants.support_email | text / citext | user-input | phone loose; email format |
| Website | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.website | text | user-input | hostname-ish |
| Logo | S8 Company | ~~prototype-extracted ("SVG or PNG, max 2MB")~~ PNG or JPG, max 2 MB (DEF-TEN-10618, 2026-10-27) | **PROPOSED-SCHEMA:** tenants.logo_file_id (object-store ref) | file | user-input | BR-TEN-019 |
| Primary color / Bill accent | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.brand_primary_hex / tenants.brand_accent_hex | char(7) | user-input | `#RRGGBB` |
| Letterhead preview | S8 Company | prototype-extracted | — | — | computed-display | — |
| Remit-to address | S8 Company | prototype-extracted ("printed on the bill stub") | **PROPOSED-SCHEMA:** tenants.remit_to_address | text | user-input | required for checklist-complete |
| Payable to | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.remit_payable_to | text | user-input | defaults to DBA |
| Customer service hours | S8 Company | prototype-extracted | **PROPOSED-SCHEMA:** tenants.service_hours | text | user-input | free text ≤60 |
| Last edited by/at | S8 Company | prototype-extracted | audit_log (latest `settings.company_profile.updated`) | — | computed-display | — |

**6 · Acceptance** — Given a System Admin on the Company profile tab, When they edit any panel and Save, Then all values persist atomically with one audit row, the letterhead preview matched the entry live, newly issued documents carry the new identity/remittance while previously issued documents are untouched, and invalid EIN/logo inputs are rejected inline.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None (EIN verification depth judged derivable: format-only v1, BR-TEN-018; logo constraints are design-stated).

---
```yaml
id: US-TEN-006
epic: EP-TEN-05
module: tenancy
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001]
journeys: [J5]
rules: [BR-TEN-016, BR-TEN-020, BR-TEN-021, BR-TEN-022, BR-TEN-023, BR-TEN-024]
golden_tests: []
finance_calc: none
```
### US-TEN-006 — Regional, formats & fiscal calendar tab

**1 · Details** — As a System Admin, I want to set where and how my utility operates — location/language, display formats with a live preview, and the fiscal calendar — so that every date, amount, and accounting period in the app renders and closes correctly. Entry: Settings → Company → Regional, formats & fiscal calendar. Exit: "Save regional & fiscal settings" / Discard; footer note: "Changing these does not restate historical bills."

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-020 | Regional/format settings are **display-time transforms only**: storage stays UTC timestamptz, NUMERIC(18,6) + CHAR(3); changing them re-renders screens and future documents but never restates historical bills or stored values | CONFIRMED — prototype-extracted footer copy + IS-8 + B2 conventions |
| BR-TEN-080 | **Money DISPLAYS to 2 decimals, the API SERVES 4, storage stays NUMERIC(18,6).** One formatter; no component rounds for itself. A tax line computing to **8.2985** travels as 8.2985 and renders **$8.30**. Storage does NOT move and needs no re-sign | **CONFIRMED — PO 2026-08-12 (OQ-159 · OQ-186)**; the UI showing 4 decimals today is **DEF-088** |
| BR-TEN-081 | **A typed posting DATE becomes midnight in the utility's OWN timezone** — a Houston clerk (UTC−5 in August) recording a payment on **22 August** stores **22 Aug 00:00 Central** and every person in that utility reads it as 22 August. ⚠ **The timezone field this depends on does not exist in Company settings yet (DEF-082); `tenant_settings.timezone` below is still PROPOSED-SCHEMA, so the rule cannot be honoured until it ships** | **CONFIRMED — PO 2026-08-12 (OQ-153)**; blocked on DEF-082 |
| BR-TEN-021 | Currency is forward-only: issued invoices/payments keep their stored CHAR(3); changing tenant currency once financial records exist shows an explicit warning and affects new records only | PROPOSED — derived from BR-TEN-020 + CLAUDE.md #2/#4 (money + immutability) |
| BR-TEN-042 | **A financial record LOCKS the currency — and a DRAFT bill counts (PO 2026-08-12, OQ-181: _"currency locked"_). ⚠ OVERTURNS the drafts-do-not-lock behaviour shipped 2026-08-11.** A draft already carries amounts stamped USD; move the currency under it and the run's figures and the setting disagree until somebody notices. **Deleting the draft releases the lock again** — the probe is a live existence question, not a latch | CONFIRMED — PO LC-6(a), 2026-08-08; DRAFT clause CONFIRMED — PO 2026-08-12 (DEF-075) |
| BR-TEN-022 | Fiscal calendar (FY start month+day, accounting method accrual/cash, close cadence monthly/quarterly, close-by day) drives period derivation; the "Current period" card (FY label, period number, open/close dates) is computed, never stored per-period by this module | PROPOSED — derived from prototype fiscal panel + Finance header "Open · Hand off by Sep 3" (A13) |
| BR-TEN-023 | "Lock periods once closed": what happens to money events dated into a closed period (backdated adjustment, payment reversal, bill correction) — reject vs. auto-post to earliest open period, and who may reopen | OPEN — OQ-033; the toggle is stored per this story, enforcement lives in the ledger posting service and must not be built on a guess |
| BR-TEN-024 | Sticky Save/Discard + unsaved-changes guard (as US-TEN-005) | PROPOSED |
| BR-TEN-016 | Save writes `audit_log` (`settings.regional_fiscal.updated`) | PROPOSED |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Set TX defaults (America/Chicago, English US, Sunday, USD, 1,234.56, MM/DD/YYYY, 12-hour) and Save | Live preview showed "Aug 8, 2026 · 2:30 PM · $1,234.56 · Week starts Sunday · America/Chicago (CT)" before save; app-wide rendering matches after |
| TC-2 | Change date format to YYYY-MM-DD | All screens re-render (e.g. 2026-08-08); a bill PDF issued last month re-downloaded is byte-identical (BR-TEN-020) |
| TC-3 | Set FY start October 1, close cadence Monthly, close by 3rd business day | Current-period card computes "FY2026 · Period 11 — Aug 1 to Aug 31 · Open · closes Sep 3, 2026" |
| TC-4 (neg) | Attempt currency change USD → CAD with 1,240 issued invoices | **REFUSED — 409 BIZ-LOCKED (BR-TEN-042).** The currency is LOCKED once a financial record exists; it is not a warning-and-proceed. Measured on the live stack, a tenant holding issued bill **BL-2606-000001, 108.88 USD** answered **200** and changed currency (DEF-075) because only payments had authored the probe |
| TC-4b (neg — PO 2026-08-12, OQ-181) | Attempt currency change USD → CAD with **no issued bill and one DRAFT** on the run; then delete the draft and retry | First attempt **REFUSED** — a draft already carries amounts stamped USD, so it locks. After the draft is deleted the change is **allowed again**: the lock releases, which is what makes the ruling livable for a tenant still setting itself up |
| TC-4c (PO 2026-08-12, OQ-153) | Save the Regional tab with the utility's timezone | ⚠ **NOT EXECUTABLE TODAY — DEF-082: there is no timezone control on Company settings.** The rule (BR-TEN-081) is confirmed and its storage column is still PROPOSED-SCHEMA; this TC is written so the gap fails loudly instead of being assumed shipped |
| TC-5 (neg) | FY start "February 30" (invalid month/day combination) | Inline validation error; Save blocked |
| TC-6 (neg) | Select "Español — coming soon" | Option is disabled (IS-8: Spanish v1.1); cannot be submitted |
| TC-7 (isolation) | Brazos Bend sets 24-hour time; Lone Star Ridge stays 12-hour | Each tenant's sessions render their own formats only |

**4 · Test Data** — Brazos Bend: Country United States · State Texas · Timezone America/Chicago (CT) · Language English (US) · First day Sunday · Currency USD · Number 1,234.56 · Date MM/DD/YYYY · Time 12-hour · FY start October 1 · Method Accrual · Close cadence Monthly · Close by 3rd business day · Lock closed periods ON. Reference date 2026-08-08 → FY2026 Period 11 (FY Oct–Sep).

**5 · Data Fields / Mapping** (all settings columns proposed — B2 has no tenant-settings storage beyond the confirmed `late_grace_mode`/`late_grace_days` note; proposal: new 1:1 table `tenant_settings`)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Country / State | S8 Regional | prototype-extracted | tenants.state (exists) + **PROPOSED-SCHEMA:** tenant_settings.country | text | user-input | US/CA; state per country |
| Timezone | S8 Regional | prototype-extracted + A1 addendum (8 US zones) | **PROPOSED-SCHEMA:** tenant_settings.timezone | IANA tz | user-input | valid tz name. ⚠ **NOT BUILT — DEF-082 (PO, 2026-08-12: _"you did not fix time zone drop down in company settings"_). BR-TEN-081 (a typed posting date = midnight in the utility's own timezone) depends on this field and cannot be honoured until it ships** |
| Language | S8 Regional | prototype-extracted + IS-8 | **PROPOSED-SCHEMA:** tenant_settings.language | BCP-47 | user-input | en-US only in v1 |
| First day of week | S8 Regional | prototype-extracted | **PROPOSED-SCHEMA:** tenant_settings.first_day_of_week | enum sun/mon | user-input | — |
| Currency | S8 Regional | prototype-extracted | tenants.currency (exists) | CHAR(3) | user-input | USD/CAD; BR-TEN-021 warning |
| Number / Date / Time format | S8 Regional | prototype-extracted | **PROPOSED-SCHEMA:** tenant_settings.number_format / date_format / time_format | text | user-input | from the 3 offered patterns each |
| Live preview | S8 Regional | prototype-extracted | — | — | computed-display | — |
| Fiscal year start | S8 Regional | prototype-extracted | **PROPOSED-SCHEMA:** tenant_settings.fy_start_month + fy_start_day | int + int | user-input | valid month/day |
| Accounting method | S8 Regional | prototype-extracted | **PROPOSED-SCHEMA:** tenant_settings.accounting_method | enum accrual/cash | user-input | — |
| Close cadence / Close by | S8 Regional | prototype-extracted | **PROPOSED-SCHEMA:** tenant_settings.close_cadence / close_day | enum / text | user-input | monthly/quarterly; offered values |
| Lock periods once closed | S8 Regional | prototype-extracted | **PROPOSED-SCHEMA:** tenant_settings.lock_closed_periods | boolean | user-input | enforcement gated by OQ-033 |
| Current period card | S8 Regional | prototype-extracted | — | — | computed-display | derived from fiscal fields |

**6 · Acceptance** — Given a System Admin on the Regional tab, When they change any setting and Save, Then the live preview reflected entries before saving, all rendering follows the new settings after, stored data and previously issued documents are bit-for-bit unchanged, the current-period card recomputes from the fiscal fields, and the lock toggle persists while its ledger enforcement remains stubbed `NotImplementedError("OQ-033")`.

**7 · Finance Calculation** — N/A (period derivation is calendar arithmetic, no money math; close enforcement is ledger-module scope).

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-033 | With "Lock periods once closed" on: are money events dated into a closed period rejected, or auto-posted to the earliest open period? Who can reopen a closed period, and is reopening audit-gated? | Ledger posting enforcement (wave 5) + BR-TEN-023; NOT this tab's storage | Product Owner (chat session) | **CLOSED — PO R6: auto-post to the earliest open period with an audit note; System Admin reopens (BR-TEN-038)**; the ledger enforcement is still owed |
| OQ-153 | A clerk types a posting DATE and the column is a TIMESTAMP — which instant does "22 August" become, and in whose timezone? | Payment posting/clearing dates; every date a clerk types | Product Owner (chat session) | **CLOSED 2026-08-12 — _"The utility's own timezone at midnigh"_ → BR-TEN-081. ⚠ Unimplementable until DEF-082 puts the timezone control on this tab** |
| OQ-159 / OQ-186 | At which boundary does money become a 2-decimal figure — the API or the cell? And does "save 4 decimal at server" mean the wire or the column? | Every money cell in the product | Product Owner / finance | **CLOSED 2026-08-12 — display 2, API 4, storage stays NUMERIC(18,6) → BR-TEN-080. The UI showing 4 today is DEF-088** |
| OQ-181 | Does a DRAFT bill lock a tenant's currency? | The currency control on this tab (BR-TEN-042) | Product Owner (chat session) | **CLOSED 2026-08-12 — _"currency locked"_: YES, a draft locks it; deleting the draft releases it. ⚠ OVERTURNS what shipped 2026-08-11** |

---

## Story added 2026-08-27 — S107 had no owner, and the tables behind it had no screen (DEF-1092)

`10-scripts/gates/screen_story_coverage.txt` has carried S107 since 2026-08-16
with the reason *"Wave 8 per B10 and OQ-015 (provision-only v1, no Stripe), so
no story exists yet by sequencing rather than by oversight."* That reason was
true when it was written and stopped being true on **2026-08-27**, when CR-039
wave F landed `implementation_orders`, `addons` and `tenant_addons` beside the
`subscriptions` that had been seeded since `tenancy/0005` — **four tables, a
migration, a numbering series and a signup writer, and nothing anywhere that
renders one of them.** DEF-1092 is that sentence; the PO's own words are *"wave
F has models and numbering but no screen (DEF-1092) — Can you build this
screen?"*

**This story is authored from A1's S107 row, `04-docs/01-spec/11b-api-audit.md`
§2.16, the four models' own docstrings and `05-prototype/r10-2026-08-16` line
7927 (SET-15), and from nothing else.** It is written BEFORE the screen, which
is hard-won law 8's whole point — for the fourth time (DEF-006 S1, DEF-129 the
dashboard, DEF-137 S113).

⚠ **IT CLAIMS S107 AND NOT S108/S109.** Those two are the subscription INVOICES
and the payment METHOD, and neither has a table, a column or a route on the
platform side of this product. They keep their register lines, with the reason
corrected: the blocker is no longer *sequencing*, it is that **the invoice
entity does not exist and OQ-015 ruled v1 takes no card at all**.

---
```yaml
id: US-TEN-022
epic: EP-TEN-05
module: tenancy
screens: [S107]
wave: 8
status: ready
blocked_by: []
depends_on: [US-TEN-001, US-TEN-006, US-IDN-008]
journeys: []
rules: [BR-TEN-002, BR-TEN-014, BR-TEN-240, BR-SHL-020, BR-SHL-023, BR-SHL-025, BR-SHL-034, BR-SHL-044]
golden_tests: []
finance_calc: none
```
### US-TEN-022 — S107 Billing plan · Plan tab: see what this utility pays Bynry, and what it bought to get set up

**1 · Details** — As a **System Admin at a 1–2 staff utility**, I want one page
that tells me what I am paying Bynry, what I bought to get set up and what my
reference number for it is, so that I can quote it, check it against an invoice
that arrives by email, and know when my trial ends. Entry: Settings → Billing
plan. Exit: nowhere — **nothing on this screen writes**.

**What renders, and each figure's source.** The **subscription plan** — name,
`price_month` and `currency` from `subscription_plans` (the three SKUs seeded by
`tenancy/0005`), and the `min_accounts`–`max_accounts` band. The
**subscription's own state** — `trial` with its `trial_ends_at`, which
BR-TEN-014 sets to provisioning + 14 days. The **implementation order** —
`order_no` (`IMPL-26-0001`, the platform series of CR-039 task 27),
`duration_months`, `price`, `instalments` and `status`. The **add-ons** this
tenant holds, each at the price that actually applies (a null
`tenant_addons.price_month` means *whatever the catalogue says today*).

⚠ **THE BOUNDARY IS THE POINT AND IT IS ON THE SCREEN.** A1's own sentence on
these rows: *"these invoices are what the tenant pays Bynry. They are a
different entity from customer bills and must never appear in Billing,
Payments, Finance, or Reports."* The lede says so in the operator's own words,
because somebody reading `$5,000.00` on a screen inside their billing product
is entitled to know whose money it is.

⚠ **FOUR THINGS r10 SET-15 DRAWS ARE NOT BUILT, AND EACH IS A REFUSAL RATHER
THAN A GAP.** r10 was drawn on 2026-08-16; the commercial model was ruled by the
PO on 2026-08-26, ten days later. **(a)** `$0.85 / connection` × `1,247` =
`$1,059.95` — no per-connection rate column exists and the ruled model is
banded (`DEF-1220`). **(b)** the entitlement COUNT — *connection* is defined in
no glossary and no contract, accounts / units / service points / meters are four
different figures on one tenant, and the band boundary it decides is `$5,000`
against `$8,000` (`OQ-660`, OPEN). **(c)** three Bynry invoices (`S108`).
**(d)** *"card on file ending 4242"* (`S109`, and OQ-015 ruled no card at all).

⚠ **AND NO CONTROL WRITES, WHICH IS A DECISION AND NOT A STAGE.** r10 offers
*Compare plans* and *Contact sales*; A1's S107 row adds *Change plan*, *Manage
payment method* and *Cancel subscription*. **Not one of the five has an
endpoint, a rule or a ruling.** A plan change moves money between a utility and
Bynry, and the implementation order's editability is the still-open half of
`OQ-610`. A disabled button with no rule behind it implies a capability that is
merely gated, so the screen carries a sentence naming who to talk to instead.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-TEN-002 *(consumed)* | Connection counts are commercial tiers, NEVER enforced technically — so the band renders as a SIZING and the screen says in as many words that nothing stops working past it. | CONFIRMED |
| BR-TEN-014 *(consumed)* | Provisioning creates the subscription `trial`, `trial_ends_at` = provisioned_at + 14 days, no payment method required — which is why the trial line says no card is needed. | CONFIRMED |
| BR-TEN-240 *(consumed)* | The signup transaction writes the zero-month self-serve implementation order, so a tenant cannot exist without its commercial record. This screen is the first thing that can show it. | CONFIRMED |
| BR-SHL-023 *(consumed)* | One money formatting path; every amount renders with its currency. Stored 4dp, displayed 2 — and **nothing on this screen performs arithmetic on money**, which is also why there is no "your monthly total" line adding the plan to its add-ons. | CONFIRMED |
| BR-SHL-025 *(consumed)* | Server-authoritative RBAC. A4's `settings_lookups` cell governs: System Admin Full, Executive View, Billing Clerk no cell — enforced by the endpoint, not by a client role check. | CONFIRMED |
| BR-SHL-034 *(consumed)* | Dates only through `DateCell`, in the tenant's own zone and format. | CONFIRMED |
| BR-SHL-044 *(consumed)* | ONE page header. This is a TAB BODY and mints no second `<h1>`. | CONFIRMED |

**No BR is minted by this story.** Every rule it needs was already signed, which
is the honest state: this is a screen over a model somebody else ruled.

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A tenant provisioned today opens Settings → Billing plan | **`IMPL-26-0001`** renders, with **Self-serve**, **$0.00** and *Paid in full up front* |
| TC-2 | The same tenant, Growth plan | **$5,000.00** and *per month* — the CATALOGUE figure, at two decimals with its currency. `5000.000000` never reaches the screen |
| TC-3 *(negative — DEF-1220)* | Anywhere on the screen | **`0.85`, `1,059.95` and `1,247` never appear.** Nothing multiplies a rate by a count, because no rate column exists |
| TC-4 *(negative — OQ-660)* | The band | Renders **300 to 1,000 accounts** with *"Nothing stops working if you go past it"*. **No connection count is drawn**; the absence carries `OQ-660` on `data-tracks` and NOT in the sentence |
| TC-5 | A nine-month engagement at $9,000 in two instalments | **9 months**, **$9,000.00**, *Paid in two instalments*, status **Under way** — and the word *Self-serve* is absent |
| TC-6 *(negative — DEF-1222)* | The duration | Rendered in **months**, never weeks. A1 still tabulates four packages in weeks; the screen renders the COLUMN |
| TC-7 *(negative)* | An add-on whose catalogue row is `priced = false` | **"Price not set yet"** — the PO's `$1.00` placeholder never renders as a price |
| TC-8 | An add-on with a negotiated `tenant_addons.price_month` | The negotiated figure at two decimals, marked *agreed for you* |
| TC-9 *(negative)* | No add-ons | **Two different sentences**: *"There are no add-ons to choose from yet"* when the catalogue is empty (it is, by ruling), *"You have not taken any add-ons"* when it is not |
| TC-10 *(negative)* | Invoices and payment method | **ONE stated absence**, not two empty panels — an empty invoice table would read as *you have no invoices*, which is false. Carries `S108` and `S109` |
| TC-11 *(negative)* | Any control | **No `<form>`, no `<input>`, no primary button**, and none of *Compare plans* / *Change plan* / *Cancel subscription* |
| TC-12 | An Executive | Reads the page; the foot says their role can read and not change it. A **Billing Clerk is refused by the SERVER** (403), not hidden by the client |
| TC-13 *(isolation)* | Two tenants on the SAME plan | Each reads its own `order_no`. The plan would look right either way, so the ORDER NUMBER is what the test asserts |
| TC-14 *(negative)* | `GET /subscription` with POST / PUT / PATCH / DELETE | **405** on all four. There is no write route on this resource |

**4 · Test Data** — the demo tenant exactly as provisioning leaves it: **Growth**,
`$5,000.000000` USD, band **300–1,000**, subscription `trial` ending
provisioning + 14 days; implementation order **`IMPL-26-0001`**, **0 months**,
**$0.0000**, 1 instalment, `delivered` with **no `delivered_on`**; **zero**
add-ons and a **zero-row** catalogue.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB source (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan name · price · currency | S107 | A1 §S107 · 11b §2.16 | `subscription_plans.name / price_month / currency` | text · numeric · CHAR(3) | reference-data | read-only; displayed at 2dp |
| Account band | S107 | A1 §S107 | `subscription_plans.min_accounts / max_accounts` | int | reference-data | BR-TEN-002 — never enforced |
| Subscription status · trial end | S107 | BR-TEN-014 | `subscriptions.status / trial_ends_at` | text · timestamptz | system-derived | read-only |
| Order reference | S107 | CR-039 task 27 | `implementation_orders.order_no` | text | system-allocated | `IMPL-{YY}-{0000}` |
| Duration | S107 | PO 2026-08-27 | `implementation_orders.duration_months` | int **months** | user-input (sales) | ⚠ A1 says weeks — `DEF-1222` |
| Setup fee · instalments | S107 | CR-039 task 25 | `implementation_orders.price / instalments` | numeric(18,4) + CHAR(3) · int | user-input (sales) | DB CHECK: 1 or 2 |
| Add-on name · price · source | S107 | CR-039 task 26 | `tenant_addons` ⋈ `addons` | text · numeric(18,4) | reference-data | null price = catalogue price |
| Connection count | S107 | r10 7946 | — | int | **UNAVAILABLE — `OQ-660`** | not drawn; the band is stated instead |
| Subscription invoices | S107 | A1 §S108 | — | — | **UNAVAILABLE — no entity** | stated absence |
| Payment method | S107 | A1 §S109 | — | — | **UNAVAILABLE — OQ-015** | stated absence |

**6 · Acceptance**
- Given a provisioned tenant, Then `IMPL-26-0001` is on the screen — which is the whole of DEF-1092.
- Given the plan, Then its CATALOGUE price renders at two decimals with its currency, and nothing on the screen multiplies anything.
- Given r10's per-connection panel, Then it is NOT ported, and no rate, count or estimated invoice appears anywhere.
- Given the invoices and the payment method, Then ONE stated absence names both, each carrying the screen id that closes it.
- Given any role, Then the SERVER decides: Full and View read, a Billing Clerk is refused.

**7 · Finance Calculation** — **N/A, and deliberately so.** Every figure is a
stored value rendered at two decimals. The one arithmetic r10 performs —
`rate × connections` — is the defect this story refuses (`DEF-1220`), and a
"total monthly" line adding the plan to its add-ons would be money arithmetic on
a client, which CLAUDE.md hard rule 2 forbids.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-660 | What is a "connection" for the subscription band — accounts, units, service points or meters? The two prices either side of a band boundary are $5,000 and $8,000 | The entitlement COUNT only. Everything else on S107 ships | Product Owner | **OPEN — routed 2026-08-27** |
| OQ-610 | Is the implementation order editable after signup, and by whom? | Any WRITE on this resource. The read ships | Product Owner | **OPEN (the editable-order half)** |
