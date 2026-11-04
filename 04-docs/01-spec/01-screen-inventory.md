# A1 — Screen Inventory

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Every screen/modal/drawer/state, entry & exit, roles, v1 flag.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


| ID | Screen name | Purpose | Entry points | Exit points | Roles | v1? |
|---|---|---|---|---|---|---|
| S1 | Pricing / packages | Show 3 plans, pick one | Public landing | → Welcome | Public | v1 |
| S2 | Welcome gateway | "First time / Sign in" fork | From Pricing | → Setup wizard, → Dashboard (sign-in) | Public | v1 |
| S3 | Sign-in | Email + password | Welcome | → Dashboard | Public | v1 |
| S4 | Setup wizard Step 1 — Utility & services | Name, subdomain, state, services | Welcome (Create) | → Step 2 / back to Welcome | Self-signup Owner | v1 |
| S5 | Setup wizard Step 2 — How you bill | Rate style, cycle, bill day, tax region, currency, load-defaults | Step 1 | → Step 3 / Step 1 | Owner | v1 |
| S6 | Setup wizard Step 3 — Create login | Owner name/email/password/mobile, recap, terms | Step 2 | → Dashboard (go live) | Owner | v1 |
| S7 | Dashboard (**DSH-01**) | **A PERIOD FILTER heads the screen (BR-REP-035, CR-015 2026-08-19; ⚠ AMENDED 2026-09-26, `CR-142-BRC07` `P0.15` / `DEF-REP-6808` — this row read *"four windows … defaulting to the LAST COMPLETED CYCLE"* for a month after the PO withdrew that window. `CR-029` `D8①`, 2026-08-23, verbatim: *"dont build it"*, closing `OQ-268` WITHDRAWN. The code has been right ever since — `apps/reports/dashboard_period.OPTION_ORDER` offers three and `default_option_id` returns `last_30_days`. `last_cycle` survives as a TOKEN only, so a link somebody shared while the option existed still resolves; it is never offered and never built)**: **THREE** windows — last 30 days · this accounting period · last accounting period — **defaulting to the LAST 30 DAYS**, and the two accounting windows are not OFFERED at all to a tenant with no fiscal calendar (`fiscal_period_not_configured`), and **the selected window is STATED IN DATES above the figures**, not buried in the control, because once a user may pick a window the dashboard can differ from Finance while both are correct. The choice rides in the URL as `f.period` (BR-SHL-011), so a window is shareable. **`as_of` is the READ moment clamped into that window (BR-REP-036)** — it read `2026-08-31` on 2026-08-19 until DEF-299 · **Six regions, each loading/empty/failing independently (BR-REP-028)**: greeting + cycle status, which **states the configured state and offers no set-up link** (BR-REP-027, amended 2026-08-19) · KPI band of five, fixed order, display-only; a tile whose owner publishes no count reads **"Not counted yet"** with the reason in its support text (BR-REP-033/024) · recent activity, last 24h max 6 from the audit log, **and the panel says "last 24 hours"** (BR-REP-031) · service mix MTD, **the TENANT'S OWN configured services, all of them, in BR-RAT-024's **ELEVEN**-service seed order (⚠ this read *ten* until 2026-09-26, `DEF-REP-6809`; `BR-RAT-024` was CONFIRMED-AS-AMENDED at eleven on 2026-09-02 when `CR-063` appended `fire` at position 11)**, bars proportional to the LARGEST service, plus a named remainder for revenue no service row can hold (BR-REP-025/026, amended 2026-08-19) · AR aging, five buckets, share rounded and need not total 100% (BR-REP-030) · to do, max 4 from owning modules, **a row nobody could count showing no number** (BR-REP-032, amended 2026-08-19). Page actions `Import reads` + `Run billing →`, hidden for read-only roles | Sidebar | any module | All staff | v1 |
| S8 | Settings (tabbed) | Lookup tables + system settings + users | Sidebar | — | Owner/Admin | v1 |
| S9 | Plans & Rates (tabbed) | Plans, Rates, Charge Codes, Taxes & Fees | Sidebar | → New Plan/Rate/Charge/Tax wizards | Owner/Admin | v1 |
| S10 | New Plan wizard | Guided plan creation | Plans tab | → Plans list | Owner/Admin | v1 |
| S11 | New Rate wizard | Guided rate schedule creation | Rates tab | → Rates list | Owner/Admin | v1 |
| S12 | New Charge Code form | Add charge code | Charge Codes tab | → list | Owner/Admin | v1 |
| S13 | New Tax/Fee form | Add tax or fee | Taxes & Fees tab | → list | Owner/Admin | v1 |
| S14 | Premises (tab) | List premises | Sidebar → Premises | → Add Premises, Unit detail | Staff | v1 |
| S15 | Units (tab) | List units within premises | Premises page | → Add Unit | Staff | v1 |
| S16 | Add Premises & Unit form | Single or bulk create; assign meter/sub-meter/plan to unit | Premises/Units tabs | → list | Staff | v1 |
| S17 | Accounts list | All accounts | Sidebar | → New/Move-in/Move-out/Detail | Staff | v1 |
| S18 | New Account wizard | Guided; stage 3 picks premises+unit | Accounts | → Account detail | Staff | v1 |
| S19 | Move-In wizard | Guided move-in | Accounts | → detail | Staff | v1 |
| S20 | Move-Out wizard | Guided move-out (final bill) | Accounts / Account detail action | → detail | Staff | v1 |
| S21 | Account detail | Header + actions + tabs | Accounts list, various links | action modals/wizards | Staff | v1 |
| S22 | Account action modals | Record payment, Adjust, Statement, Print bill, Issue credit, Disconnect notice, Add note | Account detail | close → detail | Staff | v1 |
| S23 | Change Plan wizard | 3-step w/ proration | Account detail | → detail | Staff | v1 |
| S24 | Payment Plan wizard | 3-step installments | Account detail / Payments bulk | → detail | Staff | v1 |
| S25 | Reads (tab: Reads) | Readings list + rules flags | Sidebar | → Upload wizard, Read detail | Staff | v1 |
| S26 | Reads (tab: Routes) | Routes | Reads page | — | Staff | v1 |
| S27 | Reads (tab: Cycles) | Cycles | Reads page | — | Staff | v1 |
| S28 | Read upload wizard | CSV upload, tag, run rules, review, compliance | Reads | → Reads list | Staff | v1 |
| S29 | Read detail drawer | One reading + compliance | Reads list | close | Staff | v1 |
| S30 | Billing (tab: Bills) | All bills | Sidebar | → Run Bills, correction, single, budget | Staff | v1 |
| S31 | Run Bills wizard | Multi-step guided billing run | Billing | → Bills | Staff | v1 |
| S31.2 | Run Bills Step 2 — "Check what we found" | Sub-tabs: Consumers/Plans/Reads/Balances/Credits/Overcharges | Run Bills | Step 3 | Staff | v1 |
| S31.3 | Run Bills Step 3 — exception cases | Per-case tables + bulk actions | Run Bills | Step 4 | Staff | v1 |
| S32 | Payments (tab: Summary) | Today, method mix, failed, collections | Sidebar | tabs | Staff | v1 |
| S33 | Payments (tab: Record payments) | Ledger of payments/credits/adjustments + bulk | Payments | modals | Staff | v1 |
| S34 | Payments (tab: Outstandings) | AR high→low + bulk actions | Payments | modals/wizards | Staff | v1 |
| S35 | Payment modals | Record, Credit, Adjust, Lockbox, Reverse, Reminder, Notice, Write-off, Reapply, Receipts, QuickBooks, Field visit | Payments bulk/row | close | Staff | v1 |
| S36 | Finance (tab: Revenue & AR) | Revenue by service, billed vs collected, aging | Sidebar | — | Owner/Finance | v1 |
| S37 | Finance (tab: Deposits & Bank) | Deposit batches vs bank | Finance | → Bank import, Batch detail | Owner/Finance | v1 |
| S38 | Bank import wizard | 3-step reconcile | Deposits tab | → Deposits | Owner/Finance | v1 |
| S39 | Batch detail | Payments in batch vs bank side + trail | Deposits (batch link) | back | Owner/Finance | v1 |
| S40 | Finance reconcile modal | Explain deposit difference | Deposits/Batch | close | Owner/Finance | v1 |
| S41 | Finance (tab: Taxes & Remittance) | Collected by authority, filings | Finance | — | Owner/Finance | v1 |
| S42 | Finance (tab: Export to accounting) | GL summary, QuickBooks/CSV/IIF/Xero | Finance | → Sync modal | Owner/Finance | v1 |
| S43 | Finance QuickBooks sync modal | Send period to QBO | Finance/Export | close | Owner/Finance | v1 |
| S44 | Reports library | Cards by Financial/Operations/Compliance | Sidebar | → viewer, builder, scheduled | Staff | v1 |
| S45 | Reports scheduled & history | Scheduled + recent runs | Reports | back | Staff | v1 |
| S46 | Report viewer | Param bar + KPIs + table | Report card | back | Staff | v1 |
| S47 | Report builder | Dataset/columns/filters | Reports (+Build) | → viewer | Staff | v1 |
| S48 | User menu popover | Profile/password/logout etc | Sidebar user block | modals/routes | All | `PARTIAL` — designed but not built |

**PARTIAL screens:** S48 (user menu) exists as a spec proposal only. Dashboard KPI drill-downs, Routes (S26) and Cycles (S27) tabs are lightly stubbed. Settings sub-tabs vary in fidelity — see Document 9.

---


## Addendum — Settings module (reworked 2026-08-07)
Settings (S8) is a tabbed page with full CRUD. Tabs:
1. **Company** — utility details, brand, **Regional & Formats** (country, state, timezone, currency, language, date/time/number format, first day of week, live preview), and **Fiscal calendar**.
2. **Services & UoM** — enable/disable available services + edit UoM. New service *types* are provider/backend-added (not user CRUD).
3. **Routes & Cycles** — configurable: Add/Edit/Delete routes and billing cycles (read window, bill date, due day).
4. **Lookup tables** — card grid → per-list management view (table + **Add** modal, per-row **Edit / Deactivate / Delete**, 🔒 audit-lock when Used-by > 0: deactivate allowed, delete blocked). Lists: UoM, charge codes, reason codes, tax jurisdictions, payment methods, meter types, account statuses, document templates.
5. **Numbering** — number formats + document templates.
6. **Users & roles** — user CRUD (invite / edit role / deactivate / resend / remove) + read-only **Roles & Permissions** matrix.
7. **Notifications** — customer + staff toggles.
8. **Integrations** — see A15/B7; includes **Connect your email** (BYO mailbox).
9. **Security** — password policy, 2FA requirement, session timeout, IP allowlist, audit-log access.
10. **Billing plan** — current package, usage, invoices.

New modals: lookup add/edit, invite user, add route, add cycle, connect email. All fire a confirmation toast.


## Addendum — Integrations are connectable (2026-08-07)
Every integration card in Settings → Integrations has a working **Connect** (or **Manage** when already connected) action opening a connect modal: method (OAuth sign-in / API key / SFTP-file), key/token field, environment (Production/Sandbox), sync cadence, test-connection toggle, and a **Disconnect** action for connected ones. Applies to Accounting (QuickBooks Online, Xero), Payments (Stripe, Plaid), Meters (Itron MDM, Sensus FlexNet), Communications (Twilio SMS), Print (Lob/DocPrint), SSO (Okta/Azure AD), plus the BYO-email cards (Google/Microsoft OAuth, custom SMTP).


## Addendum — User account menu (2026-08-07)
The sidebar footer user block (avatar · name · role) is now a button opening an upward **user menu**: My profile, Change password, Two-factor authentication, and **Sign out** (returns to the public Pricing/sign-in screen). Each of the first three opens a modal:
- **Change password** — current / new / confirm + policy hint + "sign out other sessions".
- **Two-factor** — Authenticator app or SMS, QR + 6-digit code.
- **My profile** — name, email, phone, role (read-only).
S48 (previously PARTIAL "user menu") is now built.


## Addendum — Finance & Reports additions (2026-08-07 r2)
- Finance gains a **General ledger** tab (5th): read-only **trial balance** (GL account · type · debit · credit · balanced), period + **premises** filter, **account-mapping** panel, and **+ Journal entry** / **+ Record refund** / **Export trial balance** actions.
- New **Manual journal entry** modal (balanced debit/credit lines, type: standard/accrual/reversing, memo, add-line, audit-log required).
- New **Record refund** modal (outbound: account, amount, method check/ACH, check#/trace, reason, status Issued/Cleared/Void, GL post).
- Reports gains an **Account ledger** report: account + **premises** + date range → dated charges/payments/adjustments with running balance → **PDF/CSV download**; also reachable as "Download ledger" intent from Account detail.


## Addendum — Assets module (2026-08-07 r4)
New sidebar item **Assets** (after Plans & Rates). Registry of all metering + behind-the-meter assets, assignable to Units, with lifecycle.
- **Assets list** — 3 tabs: **Meters** · **Sub-meters** · **Devices**. Search + filter (All/Active/Needs repair/Retired/Unassigned). Bulk import + single Add. Row actions: View/Edit/Reassign/Log repair/Retire/(Delete if unreferenced).
- **Asset detail** — header (asset #, type, status, assignment) + tabs Overview (specs) · Reads (incl. net-metering import/export) · Assignment history · Maintenance & repairs · Audit.
- **Modals:** Add asset, Bulk import, Log repair/maintenance (repair/inspection/test + status), Retire (reason, retire date, replaced-by — retire not delete), Reassign (move to unit/inventory + final read).

## Addendum — Assets tab rename (2026-08-07 r5)
The third Assets tab is labeled **Behind the meter** (was "Devices"): net meters, backflow preventers, communication endpoints, PV/solar, battery, EV charger, transformer, generator.

## Addendum — Settings rename (2026-08-07 r6)
"Lookup tables" tab renamed to **Reference data** (clearer for business users). Routes & Cycles, Numbering, and Security remain their own tabs (they are configuration/security, not editable reference lists).
> **SUPERSEDED IN PART by r9 (2026-08-11, CR-001)** — the second sentence no longer holds for Routes & Cycles and Numbering, which now nest under the renamed **Configure** tab. **Security is unaffected and remains its own tab, for exactly the reason r6 gives.** r6's objection was to the words "Reference data", not to the grouping, and the rename is what dissolves it — see r9.

## Addendum — Settings: "Configure" (2026-08-11 r9, CR-001)
**PO change request, from the running app.** Verbatim: *"Rooutes and Cycle, Numbering, templates - move under Reference data - we can call Reference data = Configure."*

The **Reference data** tab is relabelled **Configure** and carries a second-level strip: **Reference data · Routes & Cycles · Numbering · Templates**. The Settings strip goes from eleven top-level tabs to eight — Company · Users & roles · Services & UoM · **Configure** · Notifications · Integrations · Security · Billing plan.

**Why this is a sound reversal of r6, not a contradiction of it.** r6 refused to file Routes & Cycles and Numbering under a heading promising *editable reference lists*, and it was right to. The rename removes the promise: "Configure" describes all four accurately — reference lists, read routes and billing cycles, number formats and document templates are every one of them things a tenant sets up once and changes rarely. The rename and the move are one decision; the move alone would have been r6's mistake.

**Security deliberately does not move.** r6 named Routes & Cycles, Numbering and **Security**; the PO named Routes & Cycles, Numbering and **Templates**. The lists differ by one, on purpose — a password policy is not filed beside a list of meter types, and r6's reason for that stands untouched.

**Supporting case:** eleven tabs wrapped onto a second row at 1920px (the PO's screenshot shows "Billing plan" alone underneath); the three tabs moved are the three a tenant touches least, while the weekly ones keep top-level position; and the second level already exists and is proved — Company has carried Profile · Regional since it was built.

**URLs are unchanged.** Configure keeps the id `reference-data`, and the three moved tabs keep their own segments one level down. `/settings/routes-cycles`, `/settings/number-series` and `/settings/templates` REDIRECT rather than 404, because all three are live deep links today — `settings/number-series` is a checklist target the SERVER sends (US-TEN-003) and the Reference data screen links to `/settings/templates` for the BR-TEN-033 pointer. A tab move that broke a checklist link would be this change request causing a defect.

**Known cost, recorded not hidden:** the prototype still draws the eleven-tab strip and knows no label "Configure", so G14 (prototype conformance) sees a divergence. The prototype is not edited — it is the design of record and rewriting it to match the product destroys the only thing that catches drift. This is the third prototype-vs-ruling divergence in two days (DEF-018 nav order, DEF-033 draft bill numbers, this one); the pattern is that **the prototype is older than every ruling made since, and when they disagree the ruling wins and the divergence is written down.** Full case: `12-governance/11-change-requests.md` CR-001.

## Addendum — Settings order + Billing plan (2026-08-07 r7)
Settings tab order: **Company → Users & roles → …**. Billing plan tab: invoices are **from Bynry** (SMARTBillHub subscription) with per-invoice **Pay now** (unpaid) / **Receipt download** (paid) and **Manage payment method**.


## Addendum — Templates settings tab (2026-08-07 r8)
New **Settings → Templates** tab (after Numbering). Three groups — **Printable** (bill res/comm, statement, disconnect 1st/2nd/final, dunning, receipt), **Email** (bill-ready, receipt, reminder, plan-change, credit, statement), **Text/SMS** (bill-ready, reminder, disconnect, payment received). Each row → **template editor** modal: subject + body, variable palette ({first_name}/{account}/{balance}/{due_date}/{pay_link}/{utility_name}), send-test, reset-to-default, save; versioned + audit-logged. Numbering keeps number formats; its document-template list now points to Templates.


### Added 2026-08-07 — template designers (16 modals)

| ID | Screen | Purpose | Entry | Roles | v1 |
|---|---|---|---|---|---|
| S91 | Template designer · Bill residential | Paper preview + variables + options | Settings → Reference data → Document & message templates → Design | System Admin | v1 |
| S92 | Template designer · Bill commercial | Per-meter, demand, PO/tax-ID layout | same | System Admin | v1 |
| S93 | Template designer · Statement | Ledger-over-range layout | same | System Admin | v1 |
| S94 | Template designer · Disconnect notice | 3 tiers + regulatory footer | same | System Admin | v1 |
| S95 | Template designer · Dunning | 3 stages | same | System Admin | v1 |
| S96 | Template designer · Receipt | Single-transaction layout | same | System Admin | v1 |
| S97–S102 | Email designers (6) | Subject, preheader, body, merge fields | same | System Admin | v1 |
| S103–S106 | SMS designers (4) | Body + segment counter | same | System Admin | v1 |

All 16 close via ✕, backdrop click, or Cancel. Footer actions: Cancel / Preview PDF (printable) or Send test (email, SMS) / Save version.


### Added 2026-08-07 — Settings → Billing plan split into two tabs

| ID | Screen | Purpose | Entry | Roles | v1 |
|---|---|---|---|---|---|
| S107 | Billing plan · Plan tab | Current subscription, entitlements, payment method on file, next invoice, billing details | Settings → Billing plan | System Admin (Owner) | v1 |
| S108 | Billing plan · Invoices tab | Full table of Bynry subscription invoices with status and per-row action | Settings → Billing plan → Invoices | System Admin (Owner) | v1 |
| S109 | Manage payment method (modal) | Capture/replace the card or ACH method used for the SMARTBillHub subscription | Plan tab → Manage payment method / Update card | System Admin (Owner) | v1 |

**Plan tab** — plan name and price, renewal date and contract type, entitlement counters (active connections vs band, users, services enabled of 6), an "Included in Growth" feature line, and actions Change plan / Manage payment method / Cancel subscription. Right column: payment-method card (brand, last 4, expiry, cardholder, auto-charge note) and next-invoice summary (amount, issue and due dates, billing contact, billing address, tax ID).

**Invoices tab** — KPI strip (Outstanding, Paid this year, Lifetime, Next charge) then a table: Invoice · Period · Issued · Due · Plan · Amount · Method · Status · Action. Status values: **Unpaid** (accent-highlighted row, action = Pay now) and **Paid** (action = Receipt ↓). Filter segment All / Unpaid / Paid, search by invoice number, Export all. History spans plan changes (Starter $1,000 → Growth $5,000) and method changes (ACH → Visa), so the table must render the plan and method as they were at issue time, not current values.

**Manage payment method modal** — method segment (Credit card / ACH bank debit / Invoice-wire), card number, expiry, CVC, ZIP, name on card, billing address, plus toggles for auto-charge on the 1st and use-for-overages. Shows the current method at the top. Copy states card data is processed by Bynry's payment provider and is never stored by SMARTBillHub, and that this affects only the utility's own subscription — not how their customers pay them.

**Boundary to preserve:** these invoices are what the *tenant pays Bynry*. They are a different entity from customer bills and must never appear in Billing, Payments, Finance, or Reports.


### Revised 2026-08-08 — self-serve onboarding expanded from 3 steps to 5

Entry unchanged: Pricing → Welcome gateway → **Create your utility** (or Sign in). Five steps with a clickable progress rail.

| ID | Step | Purpose | Required fields | v1 |
|---|---|---|---|---|
| S110 | 1 · Your utility | Name, web address, country, state, services billed | Utility name only | v1 |
| S111 | 2 · How you bill | Starting rate style, cycle, bill-on day, tax region, currency, load-reference-data toggle | None — all defaulted, has **Skip — use defaults** | v1 |
| S112 | 3 · Plan & setup | Subscription tier + implementation package, with a running cost line | None — both pre-selected | v1 |
| S113 | 4 · Review | Read-only summary of steps 1–3 with per-block Edit links, and a due-today / then-monthly panel | None | v1 |
| S114 | 5 · Create login | Owner name, email, password, optional mobile, terms | Name, email, password | v1 |

**Step 3 — plan selection.** Connection count is a **range picker** (Under 300 / 300–1,000 / 1,000–3,000 / Not sure yet), explicitly advisory and not contractual. Plan cards: Starter $1,000/mo (up to 300), Growth $5,000/mo (300–1,000, pre-selected, badged Recommended), Scale $8,000/mo (1,000–3,000).

**Step 3 — implementation packages (one-time fee).**

⚠ **SUPERSEDED IN PART, 2026-08-27 — THE UNIT IS MONTHS, NOT WEEKS (`DEF-1222`).**
The table below prices four packages at *~4 weeks*, *~8 weeks* and *~12 weeks*.
The Product Owner ruled on 2026-08-27, verbatim, *"it is duration of
implmentation project"*, and named **6, 9 and 12 — months** — with a fourth
case, *"youc anhave 0 month implmentaiton"*, which is self-serve. What the
product stores is `implementation_orders.duration_months`, an integer of MONTHS
with a database CHECK that it is not negative (`tenancy/0021`), and the only
order any tenant holds today is **0 months at $0.00**. **The four package NAMES
and their three PRICES were never re-stated by the PO either** and are carried
here as the 2026-08-08 draft, not as signed figures — S107 renders the stored
duration and the stored price and offers no package picker, because a picker
would BE the vocabulary. The rows below are left verbatim rather than edited,
which is this document's house style for a superseded statement.


| Package | Duration | Price | Includes |
|---|---|---|---|
| Self-serve | Live today | $0 | Guided checklist, help docs, email support |
| Guided | ~4 weeks | $5,000 | We configure with you, import accounts and meters, one training session |
| Standard | ~8 weeks | $9,000 | Guided + data cleanup, rate build, whole-team training |
| Full | ~12 weeks | $12,000 | Standard + historical bill migration, parallel-run validation before go-live |

Self-serve pre-selected. Running-total bar: "Growth $5,000/mo · Self-serve setup $0 — Due today $0.00, then $5,000/mo after your 14-day trial."

**Step 4 — review.** Three blocks (Your utility / How you bill / Plan & setup) each with an **Edit** link back to that step. Values that came from defaults rather than user choice are marked `default` in small grey type. Dark footer panel: **Due today $0.00** and "Then $5,000.00/month from Aug 22, 2026 · Cancel any time during the trial · no card required now".

**Billing decision: no card at signup.** The 14-day trial starts without payment details; the card is captured later in Settings → Billing plan → Manage payment method.

#### Data deliberately kept OUT of onboarding
Legal name, EIN, state utility ID, mailing address, logo, brand colours, remittance address. Users rarely have these at signup. They live in Settings → Company and are prompted by the post-signup checklist.

#### Dropdown coverage (expanded 2026-08-08)

| Control | Coverage |
|---|---|
| Country | United States, Canada |
| State | All 50 states + DC + Puerto Rico as a **searchable type-ahead** (`<input list>` + `<datalist>`), not a short select |
| Timezone | 8 US zones incl. Phoenix (no DST), Anchorage, Honolulu, Puerto Rico |
| Billing cycle | Monthly, Bi-monthly, Quarterly, **Semi-annual**, **Annual** |
| Bill-on day | 1st–28th plus **Last day of the month** |
| Tax region | Derived from the selected state; includes "I'll configure this later" |
| Currency | USD, CAD |
| Language | English (US); Spanish shown disabled as a v1.1 gap |

#### Friction controls
- Web address auto-suggested from the utility name with a live availability check.
- Step 2 carries a **Skip — use defaults** button alongside Continue.
- Every step states what can be changed later and where.
- Rate style labelled a *starting default*, noting per-service styles are set in Plans & Rates.
- Mobile number explicitly marked optional.

## Addendum — Provisional screen IDs S49–S60 (PM, 2026-08-08; design to ratify)
The r2–r4 additions shipped without S-numbers, and A1 jumps S48→S91. Assigned into that range so tickets have canonical IDs; **provisional until the design session ratifies** (tracked as an open question).

| ID | Screen | | ID | Screen |
|---|---|---|---|---|
| S49 | Assets list (Meters / Sub-meters / Behind the meter) | | S55 | Reassign asset (modal) |
| S50 | Asset detail (5 tabs) | | S56 | Finance → General ledger tab |
| S51 | Add asset (modal) | | S57 | Manual journal entry (modal) |
| S52 | Asset bulk import | | S58 | Record refund (modal) |
| S53 | Log repair/maintenance (modal) | | S59 | Report — Account ledger |
| S54 | Retire asset (modal) | | S60 | Report — By-premises summary |

S61–S90 remain reserved for design.

## Addendum — S61 Audit log viewer (PM design for OQ-029, 2026-08-08; provisional)
Read-only, System Admin + Executive. Entry: Settings → Security "View audit log →" and Account detail → Audit tab "full log" link.
- **Filter bar:** date range · actor (user select) · module · entity type/id · action type (create/update/status/money/approval/auth).
- **Table (IS-2/3/4 conformant):** When (tz per Regional) · Actor · Action · Entity (linked) · Summary (before → after, one line) · Source (UI/API/job).
- **Row → detail drawer:** full before/after values (JSON diff view), request metadata, related OQ/approval reference if any.
- **Export CSV** (IS-9); no edit/delete anywhere (append-only, CLAUDE.md #7).
- **Tenant-scoped only** (CONFIRMED PO Q&A R4): the viewer shows the current tenant's audit log exclusively — RLS-enforced, no cross-tenant view even for support.

## Addendum — S62 Post-signup checklist (2026-08-08, PO-confirmed)
Dashboard surface listing Company-profile gaps after onboarding (legal name, EIN, remittance, logo…), each linking to its Settings tab; dismissible per item; completes when all filled.

## Addendum — S63–S67 Reference-data additions (PO-approved 2026-08-08, R2)
| ID | Screen | Home |
|---|---|---|
| S63 | Holiday calendar (list + add/remove dates) | Settings → Reference data |
| S64 | Read validation & estimation rules (thresholds + estimation params, seeded defaults) | Settings → Reference data |
| S65 | Account types & sub-types (4 fixed types, tenant sub-type CRUD) | Settings → Reference data |
| S66 | Billing defaults (late-fee min/%, grace days/mode, allocation order — tenant fallbacks) | Settings → Reference data |
| S67 | Contract template designers (Contracts group: payment-plan agreement, service agreement, deposit agreement — list pending PO confirm) | Reference data → Document & message templates |
| S68 | Account onboarding import wizard (upload → stage → value-map → review → commit) | S17 → Import accounts (EP-CUS-07) — PM-assigned per OQ-063 closure 2026-08-08 |
| S69 | Budget billing rules (eligibility months, level rounding, re-level ±%/cadence, settle-up month, drop-off count, override bound) | Settings → Reference data — PM-assigned per PO settings audit 2026-08-08 |
| S70 | Collections & notices rules (reminder cadence, notice tier days, plan-notice days, plan-void misses, NSF privilege threshold, returned-mail suppression) | Settings → Reference data — PM-assigned per PO settings audit 2026-08-08 |
| S71 | Finance controls (bank auto-match tolerance, write-off threshold, correction-approval mode, back-bill cap + theft exemption, overcharge guardrail %) | Settings → Reference data — PM-assigned per PO settings audit 2026-08-08 |
> A1 addendum 2026-08-08 (reports audit): S32 adds "Autopay scheduled" panel + returned-mail chip · S30 adds pending-billing queue chip + bill_type filter · S36 adds tie-out panel + full KPI strip · S41 = dual-basis remittance · S42 = idempotent export batches · S67 row correction: FOUR contract types CONFIRMED incl. Autopay authorization/NACHA (BR-NOT-004 — "pending PO confirm" note stale). Home for new ops chips = RQ-7 with PO.
> A1 addendum 2026-08-08 (integrations pack): Settings → Integrations grid gains two cards the CL-1 matrix made v1-real but the prototype predates — **Transactional ESP** (volume sending, OQ-074) and **Bank & lockbox file profiles** (BAI2/CSV/OFX, BR-INT-009); connect-modal pattern per the existing addendum. Print-vendor (Lob/DocPrint) card placement = IN-1 with PO.

## Addendum — S73–S74 Cost of service, RATIFIED (CR-060 C27, 2026-09-03; OQ-204 first half)

**These two ids were PROVISIONAL from 2026-08-15 and they are ratified here.** They were
assigned by `EP-LED-06` out of the reserved **S61–S90** band, **skipping S72 deliberately**
(EP-IDN-01 carries S72 as a *proposal* riding OQ-078, and taking it would be the collision
G17 exists to stop). Nothing is renumbered — CLAUDE.md: *"Use A1 as the ticket vocabulary;
never renumber."*

**Ratified by the route OQ-034/S62 and OQ-063/S68 took**, which OQ-204's own registry row
names: the authoring lane did not hand-edit A1 (HUMAN-GUIDE §6 — *"corrections land as
dated addenda"*), it wrote the addendum text into its epic and left the id provisional
until the question closed. S68's row records the same procedure in its own Home cell —
*"PM-assigned per OQ-063 closure 2026-08-08"*. This is that step for S73 and S74.

| ID | Screen | Home | Owning story |
|---|---|---|---|
| S73 | **Finance → Cost of service** — the captured supplier-invoice register, with its Capture, Correct and Void modals. A capture posts NOTHING to the books (BR-LED-028, OQ-200 ruled 2026-08-16) | Sidebar → Finance, tab **Cost of service** | US-LED-017 · US-LED-018 · US-LED-019 (`EP-LED-06`) |
| S74 | **Bought vs billed** — the unaccounted-for percentage per service per period, and the ABSENT-with-reason case that protects it (all-or-nothing per service per premises per period, BR-LED-031) | S73 → **Reconciliation** — a sub-view of the Cost of service tab, which is where it has shipped since 2026-08-16. ⚠ This records where the screen IS; it does not settle the download contract, which is OQ-204's remaining half — see below | US-LED-020 (`EP-LED-06`) |

**WHY THEY ARE RATIFIED RATHER THAN LEFT PROVISIONAL, and it is not tidiness.** Both
screens have shipped and been reachable since 2026-08-16. `App.tsx` carries the comment
`// S73·S74` on the route, several frontend files name the ids in their trace headers, and
`07-frontend/src/routing/screenIds.ts` had to record the gap in its own note: *"⚠ NO A1 ID,
AND App.tsx's OWN COMMENT CLAIMS ONE … Two ids used in code that the inventory does not
allocate. Reported, and NOT minted here."* **An id no authority defines is an id nobody can
look up when it appears in a bug report** — which is G29's own refusal, and it was true of
these two for eighteen days.

⚠ **WHAT IS RATIFIED HERE IS THE ID AND THE HOME. THE DOWNLOAD IS NOT, AND IT IS OQ-204's
REMAINING HALF.** `GET /finance/cost-reconciliation/download` raises
`NotImplementedError("OQ-204")` and the screen renders its Download control DISABLED with
that reason (BR-SHL-025 — a forbidden control renders disabled WITH its reason, never
absent). The choice it waits on is a BUILD CONTRACT, not a place: **a Finance sub-view
downloads through the platform export registry, a report beside S59/S60 downloads through
the IS-11 report pipeline under a report key.** Nothing in this addendum picks one, and
`apps/ledger/cost_api.py`'s named refusal stays exactly as it is until the owning lane
builds it. **OQ-204 is therefore PARTIALLY CLOSED, not CLOSED** — and that state is load-
bearing: G8 clause A fails any stub citing a CLOSED question, so closing the row here would
turn a gate red on a file this addendum does not touch and cannot fix.

⚠ **THE VISIBLE BADGE IS UNTOUCHED AND IS SOMEBODY ELSE'S DECISION.** By PO ruling
2026-08-19 the bottom-right tag draws **r10's** id and not A1's, and r10 draws no badge for
this screen at all — the prototype holds zero occurrences of *supplier*, *vendor* or
*purchased power*, because it predates the OQ-188 ruling of 2026-08-12 that created the
capability. So `screenIds.ts` may now carry `a1: "S73"` where it carries `ids: NONE`, and it
still has no r10 half to carry. **That edit is the frontend map's own, in its own commit,
with G29's ratchet lowered in the same commit** (`screens_without_a1` falls by one when it
lands) — this addendum moves no count, because G29's ratchet reads the frontend map and not
this file.

## Addendum — S75–S80 Reference-data lists from prototype r10 SET-04 (CR-004, 2026-08-16)

**Source: `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`, screen SET-04** (Settings
→ Configure → Reference data). r10 builds a sub-screen id per list as
`'SET-04.' + refList` (line 9277), so each row below names the r10 sub-screen it
was extracted from. r10 is THE reference by PO ruling 2026-08-16 (*"for this
session we will be refering to r10 - as default"*); A1's own screen descriptions
were extracted from r9 and do not draw these lists at all.

**Where these numbers come from, and what was NOT taken.** The reserved block is
**S61–S90** (this file, S49–S60 addendum). S61–S71 were assigned by the A1 addenda
of 2026-08-08. **S72 is deliberately skipped** — EP-IDN-01 carries it as a
*proposal* riding OQ-078, and taking it would be the collision G17 exists to stop.
**S73 and S74 are taken** by EP-LED-06 (Finance → Cost of service and its
reconciliation). ⚠ **AMENDED 2026-09-03 (CR-060 C27): "taken" was as far as this
file ever went, and a prose mention is not an allocation — G29's A1 parser reads
table cells and addendum headings, so it never saw either id and
`routing/screenIds.ts` had to record two ids "used in code that the inventory does
not allocate". Both are now RATIFIED in their own addendum above (OQ-204 first
half).** So this addendum starts at **S75**. Nothing existing is
renumbered. ~~**S81–S90 remain reserved.**~~ ⚠ **AMENDED 2026-08-24 (CR-030 W1):
S81 IS ALLOCATED AND BUILT — S82–S90 remain reserved.**

> **S81 · Accounts → Imports tab.** This line said *"S81–S90 remain reserved"*
> and was written before B18. **B18 §4 allocates S81** to the Imports tab of the
> Accounts screen — the ETL run history, KPI strip, rollback and fix row actions
> that replace the deprecated three-step upload modal — and **CR-030 W1 built
> it**: `07-frontend/src/features/customers/AccountImportsTab.tsx` carries
> `TableConfig.screenId: "S81"` (task 1.10). So the ID is in the product and the
> reserved block was one number wider than the truth.
> **Nothing is renumbered** (CLAUDE.md: *"never renumber"*): S82–S90 stay
> reserved exactly as they were, S80 keeps Import mappings, and the six-row
> addendum table below is untouched — S81 is not one of its reference-data
> lists, it is a tab on S17. Ticket vocabulary for the Accounts tabs is B18 §4.

| ID | Screen | r10 sub-screen | Backend list code | Home |
|---|---|---|---|---|
| S75 | Areas & sub-areas — districts and routes premises are grouped by | `SET-04.areas` | `areas` | Settings → Configure → Reference data (Platform-wide group) |
| S76 | Utility service size classes — 5/8"–6" water · 1φ/3φ electric · gas CFH · carts & dumpsters · storm-water ERU · solar kW · broadband Mbps · cooling tons (**renamed and grown 9 → 40 on 2026-08-27, BR-TEN-170 + BR-TEN-171**; r10 and this row said *"Meter size classes — 5/8"–4" water"* and four of the five services the ruling added have no meter) | `SET-04.sizes` | `service_size_classes` | Settings → Configure → Reference data (Plans & Rates group) |
| S77 | Occupancy statuses — occupied, vacant, owner-, tenant- and landlord-billed | `SET-04.occupancy` | `occupancy_statuses` | Settings → Configure → Reference data (Premises group) |
| S78 | Device types (BTM) — backflow, inverter, EV charger, battery, endpoint | `SET-04.devicetypes` | `device_types` | Settings → Configure → Reference data (Assets group) |
| S79 | Certification types — crew certifications and their test cadence | `SET-04.certtypes` | `certification_types` | Settings → Configure → Reference data (Assets group) |
| S80 | Import mappings — saved ETL column mappings reused by every run | `SET-04.importmaps` | `import_mappings` | Settings → Configure → Reference data (Finance group) |

**The r10 key and the backend list code differ for four of the six** (`sizes` ↔
`service_size_classes`, `occupancy` ↔ `occupancy_statuses`, `devicetypes` ↔
`device_types`, `certtypes` ↔ `certification_types`, `importmaps` ↔
`import_mappings`), which is why both are printed here: a ticket citing S76 and a
grep of `referenceDataConfig.ts` must land on the same list without guessing.

**No new stories, and that is deliberate.** All six are ordinary lists on the ONE
reference-data surface (S8), so they inherit **US-TEN-009** (card grid),
**US-TEN-010** (view/search/add/edit) and **US-TEN-011** (delete/deactivate)
unchanged, and the rules that already govern every list — BR-TEN-030
(code unique per tenant, immutable once used), BR-TEN-031 (framework is
tenancy's, content belongs to the owning module), BR-TEN-034 (audit-lock),
BR-TEN-036 (seeded defaults, tenant may extend). Their per-list vocabulary rules
are **BR-MET-066..070** (the five metering-owned lists) and **BR-LED-043**
(import mappings). CR-004 states this: *"A new list inherits all three and does
not need its own CRUD story."*

**The four Work cards get NO screen ID.** r10's SET-04 also draws `SET-04.skills`,
`SET-04.safety`, `SET-04.priorities` and `SET-04.partcat`. They ship as declared
placeholders only. **OQ-249 is OPEN** and says in terms that a reference default
*"does not authorise building nine Work tabs, minting their S-IDs from the
reserved S61–S90 range, or adding tables no module owns."* They are not numbered
here and must not be numbered until the PO rules.

**Shapes r10 hints at that no screen may render yet.** r10's own row text carries
data these lists do not hold: *"Water 5/8" · base $12.00"* (a base charge — money,
B4-governed), *"Confined space · 3-yr validity"* (a cadence), *"North district ·
3 sub-areas"* (a hierarchy). **The shape is UNSPECIFIED, not missing** — no
document defines any of the three, so the columns are deliberately absent and a
screen that invented one would be inventing a rating input, a compliance cadence
or a parent-child model. See BR-MET-066/067/070.

## Addendum — S7 becomes r10's DSH-01 (CR-012, PO 2026-08-18)

**The S7 row above was rewritten on 2026-08-18 and this note says what changed
and why, because A1 is an EXTRACTION from r9 and a reader has to know which
sentences are still r9's.** The PO's request, verbatim: *"Next CR on Dashboard -
Please fix the dashbaord it should display like this ; build all services,
backend frontend ; you can find UI details in r10 - - update all 04 doc and user
stories br etc"*, followed by the full DSH-01 requirements (both recorded in
`12-governance/11-change-requests.md` §CR-012).

**What the row used to say:** *"KPIs + activity + quick actions"*. True and
useless — it named three of the six regions, said nothing about which figures,
and could not tell a lane whether a service with no revenue is drawn or omitted.
That single sentence is the reason the shipped screen omitted unsold services
for two days and nobody could point at a document it contradicted.

**The six regions and their rules are now named in the row itself**, each
carrying the BR that governs it (BR-REP-025..033, all CONFIRMED 2026-08-18).
Three of them REVERSE or NARROW something a lane could otherwise re-derive from
r10's own markup, and each reversal is recorded at its BR rather than here:

* **BR-REP-026** — bars are a share of the LARGEST service. r10's file computes
  a share of the TOTAL (70/22/8 = 238/342, 76/342, 28/342). The requirement
  wins; r10 is layout, copy, flows and states, and is not a signed statement of
  arithmetic.
* **BR-REP-025** — *"build all services"* means the FIVE named ones, not the ten
  of BR-RAT-024. Storm water, Solar, Broadband, Thermal/Heat and Battery do not
  appear on this panel.
* **BR-REP-029** — money and counts arrive pre-formatted from the server, which
  is in stated tension with BR-SHL-023 and is reported rather than resolved.

**The endpoint did NOT move.** The PO's spec names `GET /api/dashboard?tenantId
&asOf`; A11's own S7 row contracts `GET /dashboard/summary` and that is a signed
interface, so the route is unchanged and gained an optional `asOf` only. The
tenant is never a query parameter (hard rule 1) — it comes from the request
context. The rename is UNRESOLVED and is reported, not taken.

## Addendum — S17.2 · parked wizard drafts, on each flow's own tab (CR-035, 2026-08-26)

> ⛔ **RE-POINTED THE SAME DAY IT WAS WRITTEN — CR-035 · AMENDMENT 1, PO
> 2026-08-26.** This addendum was written hours before the ruling and described
> a **ninth Accounts tab**. Verbatim: *"We dont need seperate tab for this - this
> will be directly on each request Request, Connect, Move IN move Out, Trasnfr,
> Disconnect - seperate queue not reequired"*, then **"yyes"**.
>
> **`S17.2` IS NOT DELETED AND IS NOT RENUMBERED.** The behaviour it names is
> shipped and unchanged — the reason, the note, the reminder date, the age,
> `Resume` and `Discard`. Only its HOME moved: from one queue to **a pinned
> panel on the tab for the work it belongs to** (`ParkedDraftsPanel`, mounted on
> Move-ins · Move-outs · Transfers · Disconnects · New connects). On
> **Requests** nothing was needed — a parked service request is the same
> numbered row with its `waiting_on` column beside it (B19 §12.2). The tab strip
> is back to the **eight** B18 §4 draws.
>
> **Three things in the row below are now WRONG and are corrected here rather
> than rewritten away:**
> 1. **The entry point.** Not `/{tenant}/accounts?tab=waiting-on` — that route
>    is gone and falls back to the Accounts tab. It is
>    `/{tenant}/accounts?tab=move-ins` (and the four siblings), one per flow.
> 2. **`?mine=1`.** Withdrawn. The ruling *"dissolves the mine-versus-everyone's
>    question entirely"*: BR-SHL-048's *"the clerk's own list"* meant **there and
>    nowhere else**, not a filter. The panel shows every parked draft for its
>    flow and names **who parked it** on the row.
> 3. **"Every parked wizard draft in the tenant"** — in ONE place. There is no
>    such place any more, and that loss is knowing: a clerk covering the desk
>    opens five tabs, not one. If it proves to matter the honest home is the
>    **Dashboard**, not a ninth tab, and it is not being built now.
>
> **What did NOT change:** the store, the service, the API, the port, resume and
> discard; BR-SHL-048 (a)'s no-foreign-key rule and everything it forbids; and
> the sub-id argument below, which is why the id survives the move.


| ID | Screen | Purpose | Entry points | Exit points | Roles | v1? |
|---|---|---|---|---|---|---|
| S17.2 | **Parked wizard drafts** — a panel pinned on each flow's own worklist tab (⛔ was *"Accounts → Waiting on (tab)"* until CR-035 · AMENDMENT 1, same day) | Every **parked wizard draft** for THIS tab's flow — the reason it is waiting, the note, the reminder date and **how long it has been sitting** — one panel each on move-in · move-out · transfer · disconnect · new connect. ⚠ **It is not a list of accounts, and it is not rows of the list it sits above.** BR-SHL-048 (a) forbids a parked draft any foreign key to the record it names, so **nothing here is joined to an account, a unit or a premises**; the cells print the values the clerk saw when they parked. It renders **outside the tab's table**, so the list's count stays the server's record count and the parked figure is stated separately on the panel (*"1 parked · not started yet"*). It renders **nothing at all** when that flow has nothing parked. ⛔ **No `?mine=1`** (withdrawn by amendment 1) — every parked draft for the flow, with **who parked it** on the row. `Resume` reopens the flow's OWN wizard at the parked step; `Discard` confirms first and deletes the draft | S17 tab strip → `/{tenant}/accounts?tab=move-ins` · `?tab=move-outs` · `?tab=transfers` · `?tab=disconnects` · `?tab=new-connects` (⛔ **not** `?tab=waiting-on` — that value is gone and falls back to Accounts) | → the five wizards' own routes with `?parked=&step=` · Discard → back to the same tab | Staff (System Admin · Billing Clerk) | v1 |

**WHY A SUB-ID AND NOT A NEW NUMBER — argued from this file, not from convenience.**

1. **There is no number to take, and taking one is not a lane's call.** The reserved
   band is **S61–S90** and it is exhausted: S61–S71 (addenda 2026-08-08) · S72
   deliberately skipped (EP-IDN-01 rides OQ-078) · S73–S74 (EP-LED-06) · S75–S80
   (CR-004) · **S81 allocated and built** (CR-030 W1) · S82–S90 reserved *and already
   proposed* by B18 §3 for CR-030's own screens. S91–S114 are design r8+. B18's
   decision **D1** states the consequence in terms: *"the next free ground is S115.
   Allocation is the PO's, never a lane's."* Minting S82 here would collide with a
   number B18 has already promised — the collision G17 exists to stop and the reason
   S72 was skipped.
2. **A1 already has this grammar, and it was minted for exactly this shape.**
   `S31.2` and `S31.3` are rows in the main table above for **sub-surfaces of an
   allocated screen that are not routes of their own** (Run Bills step 2 and its
   exception cases). A dotted sub-id consumes no reserved number, renumbers nothing
   (CLAUDE.md: *"never renumber"*), and is read by `g25_screen_coverage.py`'s own
   `S\d+(?:\.\d+)?` — so the id is **enforced** rather than decorative.
3. **But it is not plain S17 either, and that is the substantive half.** S17 is
   *"Accounts list — All accounts"*. This tab lists **drafts that are not accounts and
   cannot become rows of that list** — a parked move-in has no account by
   construction. Claiming plain `S17` would file it under EP-CUS-01, whose story is
   about the account register, and law 8's *"every screen needs a story"* would be
   satisfied by a story that does not describe it. That is DEF-006 with better
   paperwork.
4. **S81 is the precedent for the other direction, and it is distinguishable.** The
   Imports tab is also a tab of S17 and holds a whole number — but it was allocated by
   **B18 §3 while the band still had room**, under a PO-ruled CR, and it owns a
   detail surface of its own (`S82 · WFL-01.accounts`). This tab owns no detail
   screen: a row resumes into another screen's wizard.

**TWO NAMES, BOTH PRINTED, NEITHER INVENTED** — the same discipline as the S75–S80
addendum, so a ticket and a grep land on the same surface:

| Where | The string | Why it is that string |
|---|---|---|
| Tickets, `screens:` frontmatter, G25 | **`S17.2`** | A1's own sub-id grammar (S31.2/S31.3) |
| Column-preference key, in the shipped product | ⛔ **`table.S17.waiting-on.columns` — SHIPPED, THEN ORPHANED (CR-035 · AMENDMENT 1, 2026-08-26). LEFT IN PLACE, UNREAD.** | The panel that replaced the tab has **no table, no paging, no sort control and no column chooser**, so it declares no `screenId` and reads no column preference. Any `user_preferences` row already saved under this key is now inert. It is **not deleted and not renamed**, on the same reasoning that kept it from being renamed to `S17.2` in the first place: deleting a stored preference destroys a user's saved column set, and renaming one silently orphans it either way. An inert row costs a `jsonb` value and is the only outcome that is reversible if the surface ever regains a table. **Reported rather than decided silently** — a lane with a preferences-cleanup mandate can retire it |
| The visible bottom-right badge | **`ACC-01`** | the r10 badge of the route it is a tab of. r10 predates CR-035 and draws no Waiting-on sub-screen, so **no new r10 id is minted** (`routing/screenIds.ts`' standing refusal) |

**Owning story: US-CUS-031** (`04-docs/05-modules/03-customers/06-epics/EP-CUS-11-waiting-on.md`).

## Addendum — S141–S146 Integrations (CR-069 §9, PO-signed 2026-09-03; recorded here by the wave D build lane)

**These six ids were allocated by `CR-069` §9** — the change request the PO signed on
2026-09-03 — which re-mapped the design document's `S116`–`S121` onto the next free ground
above the portal's block. **Nothing is renumbered** (CLAUDE.md: *"Use A1 as the ticket
vocabulary; never renumber"*), and nothing is minted here: this addendum records an
allocation that already existed in the CR so that G29 can see it, exactly as the S73–S74
addendum above did. The module's own layouts file,
`04-docs/05-modules/13-integrations/08-screen-layouts.md`, maps each id to its wireframe
frames and is the visual authority (PO ruling 2026-09-03 — the pack, then r10).

| ID | Screen | Home | Owning story |
|---|---|---|---|
| S141 | **Connect / Manage** — one modal over the Integrations grid, six field sets rendered from the manifest | S8 Integrations → *Connect* / *Manage* on a card | US-INT-019 · US-INT-002 (`EP-INT-01`, `EP-INT-05`) |
| S142 | **Connection detail** — living with a connection: its operations, recent activity, one run opened | S8 Integrations → *Manage* → detail | US-INT-020 · US-INT-021 (`EP-INT-06`) |
| S143 | **Mappings** — their words for our things (the *Their words* tab), and the GIS queue *Waiting for a decision* (second tab, wave Q) | S8 Integrations → *Mappings* on a card whose manifest ships words · `/settings/integrations/:key/mappings` | US-INT-037 · US-INT-043 (`EP-INT-10`, `EP-INT-12`) |
| S144 | **Who has been reading** — the serve surface: an access log, not a run history; the issued key, masked | S142 → *Who has read* | US-INT-040 · US-INT-041 (`EP-INT-11`) — blocked `OQ-INT-1481` |
| S145 | **Consent, the staff view** — who this customer has allowed, and *Stop it* | an account's detail | US-INT-046 (`EP-INT-13`) — conditional `OQ-INT-1482` |
| S146 | **Consent, the customer decides** — the portal's allow / no-thanks | the customer portal | US-INT-046 (`EP-INT-13`) — conditional `OQ-INT-1482` |

## Addendum — S147 Connector set-up (`CR-110-BRC04` §4, PO ruling 2026-09-16; recorded here by the wave A build lane)

**One id, and it takes the number the Runbooks addendum below reserves.** That addendum
states in as many words that ***`S147` remains the next free `S`***; this allocation takes
it. **Nothing is renumbered** (CLAUDE.md: *"Use A1 as the ticket vocabulary; never
renumber"*), and nothing is minted in `screenIds.ts` — the row there cites this table,
because `G29` refuses an `a1:` id A1 does not declare. That is the same order the
`S141`–`S146` addendum above followed.

⚠ **THE SCREEN IS ONE SCREEN, NOT TWENTY-EIGHT.** The Integration Blueprint draws it
twenty-eight times, once per vendor, as `CFG-01`…`CFG-28`; those are FRAMES of one form
rendered from a manifest, which is `BR-INT-037` — *adding an API is data, not code*. A
twenty-ninth connector consumes no further `S` number and no further screen code.

⚠ **AND `r10` DRAWS NO SUCH SCREEN**, which is why it needed an id at all. In the
prototype, setting a connector up was a dialog over the Integrations grid (`S141`), and a
dialog has no address. The blueprint gives it one on every frame —
`/:tenant/settings/connectors/<key>/configure` — and the PO ruled on 2026-09-16 that for
any module with a blueprint, the blueprint owns layout, copy, flows and states.

| ID | Screen | Home | Owning story |
|---|---|---|---|
| S147 | **Connector set-up** — the form a clerk fills to connect a vendor: its fields, its API list, the key we give a partner. One component, twenty-eight renderings, no vendor named in front-end code | S8 Integrations → *Set up* on a card · `/settings/connectors/:providerKey/configure` | `CR-110-BRC04` wave A (`EP-INT-05`) |

## Addendum — the `RBS-nnn` series, Runbooks (`CR-075`, PO ruling 2026-09-06; recorded here by the `CR-075` write-back lane)

**Eight screens, and they consume no `S` number.** The Product Owner ruled the series on
2026-09-06, verbatim: *"Screens S147–S154 - this should be RBS-nnn"* — reversing this
lane's own earlier recommendation that runbook screens take the next eight `S` ids on the
argument that Runbooks is a section of the staff app rather than a new surface. **The
pattern of 2026-09-03 is a rule about MODULES, not about size**, and that reading is the
one that keeps `S` meaning one thing forever, as `CWP-nnn` and `Work-nnn` already do.

⚠ **THIS ADDENDUM ALLOCATES NO `S` NUMBER AT ALL.** ⚠ **IT READ *"`S147` REMAINS THE NEXT
FREE `S`"* UNTIL 2026-09-16, WHEN `CR-110-BRC04` TOOK IT** for the connector set-up screen
in the addendum above. **The next free `S` is now `S148`.** The sentence was true when it
was written and the number moved under it, which is this repo's most-repeated failure —
amended here in the same commit as the allocation rather than left to rot. The eight ids
below are a separate vocabulary; nothing is renumbered (*"Use A1 as the ticket
vocabulary; never renumber"*). The source documents number these screens `S147`–`S154`
and **are not renamed** — re-lettering them would break every cross-reference — so the
mapping is load-bearing and is carried in the module's own layouts file,
`04-docs/05-modules/17-runbooks/08-screen-layouts.md`, which is the visual authority for
all eight and pairs each with its wireframe frames. This addendum records the allocation
so that a ticket and a grep land on the same surface, exactly as the `S141`–`S146`
addendum above does.

| ID | Screen | Home | Owning story |
|---|---|---|---|
| RBS-001 | **Runbooks home** — is anything waiting on me · what is running now · what can I run. 3 states | sidebar → `/{tenant}/operations` | US-RBS-003 · US-RBS-012 (`EP-RBS-01`, `EP-RBS-04`) |
| RBS-002 | **Templates** — the library we ship, with the category filter and *What it can touch*. 2 states | RBS-001 → *Templates →* · `…/operations/templates` | US-RBS-002 · US-RBS-018 (`EP-RBS-01`) |
| RBS-003 | **My runbooks** — what is set up, when it runs, what it left behind. 3 states | sidebar · `…/operations/runbooks` | US-RBS-018 · US-RBS-038 · US-RBS-040 (`EP-RBS-01`) |
| RBS-004 | **Runbook detail** — **seven tabs** (Overview · Steps · Scope · Guards · Limits · Runs · Activity), and the SETUP RENDERER over any definition. 7 states | RBS-002 / RBS-003 → a runbook · `…/operations/runbooks/{key}` | US-RBS-015 · US-RBS-040 (`EP-RBS-01`) |
| RBS-005 | **Run wizard** — **six steps plus two refusals** (Scope · Checking · Review · Approve · Applying · Done; a Check skips Approve and Applying). 8 states | RBS-001 / RBS-004 → *Run ▶* · `…/{key}/run` | US-RBS-001 · US-RBS-010 · US-RBS-011 (`EP-RBS-01`, `EP-RBS-04`) |
| RBS-006 | **Run result** — the REPORT RENDERER over a run's frozen block list; a past run reopens exactly as it drew. 3 states | RBS-005 → Done · `…/{key}/runs/{run}` | US-RBS-016 · US-RBS-012 (`EP-RBS-01`, `EP-RBS-04`) |
| RBS-007 | **Work list** — findings, exceptions and human tasks in ONE list, heaviest first. 2 states | RBS-001 → *Work list →* · `…/operations/work` | US-RBS-006 (`EP-RBS-03`) |
| RBS-008 | **Run history** — every run across every runbook, newest first, and who started it. 1 state | RBS-001 → *History →* · `…/operations/runs` | US-RBS-007 · US-RBS-014 (`EP-RBS-03`, `EP-RBS-04`) |

**Why eight screens covers thirty-four runbooks.** `RBS-004` and `RBS-006` are
**renderers, not pages**: one draws a runbook's *definition*, the other a run's *report*,
and neither knows anything about a particular runbook. So adding a runbook needs **no new
screen and no frontend code at all** — one Python module, and it appears on Templates,
sets up on `RBS-004` and reports on `RBS-006`. That is the claim the eight-screen count
rests on.

**THREE FORMS, ALL PRINTED, NONE INVENTED** — the same discipline as the `S17.2` and
`S75`–`S80` addenda above:

| Where | The string | Why it is that string |
|---|---|---|
| A screen | **`RBS-001`** … **`RBS-008`** | the PO's ruling of 2026-09-06 |
| A state of a screen | **`RBS-005.3`** | A1's own sub-id grammar (`S31.2`, `S31.3`), dotted |
| A per-runbook renderer instance | **`RBS-004-R8`** · **`RBS-006-R8`** | the runbook's number after the screen — `R8` is runbook 8, and there is no `R7` because the runbooks are numbered 1 to 35 with no 7 |

⚠ **THE SEARCH PATTERN FOR A RUNBOOK SCREEN IS `(?<![A-Z]-)RBS-\d{3,5}(?!\d)`, AND BOTH
ASSERTIONS ARE LOAD-BEARING.** The module code is also `RBS`, so a screen is `RBS-001`
while a rule is `BR-RBS-001`, a story `US-RBS-001` and a test case `TC-RBS-001`. **Without
the lookbehind a screen search returns rules, stories and tests** — the same id inside
four families. **Without the lookahead `RBS-\d{3}` returns `RBS-001` for `RBS-0012`**,
which is `DEF-2804` exactly, one family along: a three-digit pattern read `OQ-1190` as
`OQ-119` and put a stub against the wrong question for two days.

⚠ **NO GATE IN THIS REPOSITORY READS THE `RBS-` SERIES.** `G25`'s row pattern and `G29`'s
cell and heading patterns both key on `S` followed by digits, so none of the eight is
counted, coverage-checked or badge-checked here — deliberately, since they consume no `S`
number, and stated so that a lane does not read a green `G25` as evidence that these eight
have stories. **The stories are the column above**, and every one of them carries a
`screens: [RBS-…]` frontmatter claim in its own epic.

---

## Addendum — `S148` Put service back on (PO drawings 2026-09-25; recorded here by lane RECONNECT)

**`S148` IS ALLOCATED AND THE NEXT FREE `S` IS NOW `S149`.** The `S147` addendum
above says in its own words that *"the next free `S` is now `S148`"*; this takes
it. The runbooks addendum's `S148`–`S155` are the SOURCE DOCUMENT's numbering and
that addendum states of itself that it **allocates no `S` number at all** — every
one of those screens is `RBS-00n` here — so none of the eight was ever taken.

| S | What it is | Where it is reached from | Story |
|---|---|---|---|
| S148 | **Put service back on** — reconnection as a SCREEN of two steps (*Choose* · *Confirm*): the account and its TYPE, a table array of which services go back on with a work order raised per row, then the money as a table with a still-owed total, the deposit, and what happens when service returns. A master account's units come back TOGETHER and its transferred-up residue is its own money line | the disconnect case record, `/disconnects/:ref` → `/disconnects/:ref/reconnect` | `US-CUS-032` (`EP-CUS-10`) |

⚠ **THE ACCOUNTS BLUEPRINT DRAWS NOTHING HERE, MEASURED RATHER THAN ASSUMED.**
`05-prototype/02 Accounts Menu Blueprint.pdf` is **283 pages**; the word
*reconnect* appears on **five** of them — 143, 146, 248, 249, 250 — and every one
is a FEE, a JOB TYPE or prose. p143 was rendered and read AS AN IMAGE (B14 rule
42): it draws the case record with three actions, `Hold the case`, `Open the
account` and `Mark as cut`, and no reconnection screen. So the four PNGs of
2026-09-25 are this screen's only drawn specification.

⚠ **`S148` REPLACES A DIALOG THAT STAYS MOUNTED FOR NOW.**
`ReconnectDialog.tsx` on the case record belongs to another lane; the door from
the case to this address is OWED and is FILED (`DEF-CUS-6743`) rather than
quietly left. `ReconnectPage.dom.test.tsx` asserts the address AND the screen id
it opens, so the day that control moves the suite already names where it must go
(hard-won law 2's mirror).
