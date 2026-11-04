# Handoff: SMARTBillHub — All-in-one Utility Billing Platform

## Overview
SMARTBillHub is a multi-tenant, self-serve SaaS billing platform for **North American utilities of up to 40,000 accounts, run by at most 10–20 staff** — the PO's tiers **T7 (≤3,000) · T6 (3–10K) · T5 (10–40K)**, all three in scope now, with **T4 (40–80K) and T3 (80–160K) explicitly later** and needing only that the architecture stay free of per-tenant caps and unpaginated lists (`NFR-5`, `NFR-3`). It bills **eleven services per account**, in seed order — Electric · Water · Gas · Sewer · Trash · Storm water · Solar · Broadband · Thermal/Heat · Battery · Fire (BR-RAT-024). ⚠ **The customer profile in this sentence read *"small utilities and sub-metering companies (under 3,000 connections, typically run by 1–2 people)"* until 2026-09-06** — the connection ceiling was the BOTTOM tier rather than an error (T7 is still in scope, so the ceiling moved 3,000 → 40,000), while the *1–2 people* half was false and is now **10–20 staff**, ruled. The PO's words and every consequence are in `12-governance/02-decision-log.md`, 2026-09-06, *"THE ICP, CORRECTED THE SAME HOUR"*. ⚠ **The Pricing page below still tops out at 3,000 deliberately** — a dated deferral until the pricing-model work (`DEF-TEN-4222`), not an omission. ⚠ **The service list named only six until 2026-08-25**; storm water, solar, thermal/heat and battery were missing, and each is a whole billing surface. The copy in `05-prototype/.../design_handoff_smartbillhub/README.md` still reads six and is deliberately NOT edited — that folder is the design artefact stored verbatim, and editing it would destroy the record of what was handed over. This package documents a complete hi-fi clickable prototype covering signup/onboarding, the app shell, and every operational module.

Target stack (customer's intent): **React front end, Django/Python API, PostgreSQL**. Multi-tenant with tenant isolation; self-serve onboarding; three fixed price packages.

## About the Design Files
The prototype in this bundle — `UtilityBilling.reference.html.txt` — is a **design reference**, not production code. It is authored as a "Design Component" (a single HTML file with an inline template + a small state class) purely to make the prototype clickable. **Do not port the runtime, its `{{ }}` template holes, `<sc-if>`/`<sc-for>` tags, or the `Component`/`DCLogic` class** into the real app. Instead, **recreate these screens in the target codebase** (React + your component library) using its established patterns, router, data layer, and styling system. Treat the HTML as the source of truth for **layout, copy, flows, states, and visual design** only.

**To run it locally:** open `05-prototype/UtilityBilling.html` in a browser — the `05-prototype/` folder is self-contained (ships `styles.css`, `_ds_bundle.js`, `support.js`, `ds-base.js` with local relative paths). The top-level `UtilityBilling.reference.html.txt` is the readable source and references the design-system files by their in-project paths, so it will **not** render on its own outside the project — use the `05-prototype/` copy to view.

## Canonical source of truth
This package is organized as a `/docs` tree Claude Code reads directly:
```
CLAUDE.md              ← repo-root operating file, read every session
/docs
  /spec        A1–A17  (extraction — what to build, from the design)
  /decisions   B1–B8   (human/finance judgment — how to build)
  /contracts   the fixed interfaces (API A11, schema B2, enums A5, glossary A16)
/prototype             ← runnable clickable reference
UtilityBilling.reference.html.txt  ← readable prototype source
```
- **`/04-docs/spec`** — the 17 extraction docs. Screen IDs (S1…S48) are defined in `spec/01-screen-inventory.md` — use this numbering for tickets.
- **`/04-docs/decisions`** — the 8 judgment docs. **`04-money-math-rules.md` (B4) and `05-golden-tests.md` (B5) contain `PLACEHOLDER`/`UNVERIFIED` lines — finance must sign them off before any billing code.**
- **`/04-docs/03-contracts`** — the stable interfaces everything builds against.
- **`CLAUDE.md`** — condensed operating rules for Claude Code.
- **`05-prototype/`** — runnable; **`UtilityBilling.reference.html.txt`** — readable source.
- (The earlier monolithic `BUILD_SPEC.md` and `DATABASE_SCHEMA.md` have been split into `/04-docs/spec` and `/04-docs/02-decisions/02-database-design-brief.md` respectively and removed, so there is one source of truth.)

## Fidelity
**High-fidelity.** Final colors, typography, spacing, copy, and interaction patterns are all intended as shown. Recreate pixel-faithfully using the codebase's existing component library. The visual language comes from the attached **"Modernist" design system** (see Design Tokens) — map every token to the equivalent in your app's theme rather than hardcoding hex where a token exists.

## Global Layout & Navigation

**App shell** (after login):
- **Collapsible left sidebar** (~240px expanded, ~64px collapsed) with a toggle. Sections in this order, each with sub-items shown as an expandable submenu:
  1. **Dashboard**
  2. **Settings** (lookup tables, system settings, user management)
  3. **Plans & Rates** — *(note: sits ABOVE Premises)* — Plans, Rates, Charge Codes, Taxes & Fees
  4. **Premises** — two tabs: **Premises** and **Units**
  5. **Accounts**
  6. **Reads** — tabs: Reads, Routes, Cycles
  7. **Billing** — tabbed page (no submenu)
  8. **Payments** — tabs: Summary, Record payments, Outstandings
  9. **Finance** — tabs: Revenue & AR, Deposits & Bank, Taxes & Remittance, Export to accounting
  10. **Reports**
- **Top bar**: breadcrumb/title, global search, notifications, and a **user block** in the sidebar footer (avatar + "Alex Reed" + "Owner") that opens an account menu (profile, change password, 2FA, theme, sign out).
- **Toasts**: transient confirmation messages bottom-center after any committed action.

**Routing model**: the prototype uses one `module` value plus per-module sub-state (tab, view, wizard step, selected id, open modal). In React, model this as nested routes, e.g. `/billing`, `/billing/run` (wizard with `?step=`), `/accounts/:id` (detail with `?tab=`), `/finance/deposits/:batchId`, `/reports/:reportName`.

## Screens / Views

### 1. Pricing / package selection
Public marketing-style page. Three fixed packages (annual connection tiers):
- **Starter** — up to 300 accounts — **$1,000/mo**
- **Growth** — 300–1,000 accounts — **$5,000/mo** (highlighted "most popular")
- **Scale** — 1,000–3,000 accounts — **$8,000/mo**
Each card: plan name, price, connection range, feature list, "Choose plan" button → Welcome gateway. "Choose" carries the selected plan forward.

### 2. Welcome gateway
Large centered section with two paths side by side:
- **First time here? → Create your utility** (primary) → 3-step setup wizard
- **Already a customer? → Sign in** (secondary) → dashboard

### 3. Create-your-utility wizard (self-serve onboarding, low-friction)
Progress rail 1-2-3, clickable steps, Back/Continue, "migration happens separately in Settings" reassurance. **No account/meter data migration here — configuration only.**
- **Step 1 — Your utility & services**: utility name; web address (subdomain preview `x.smartbillhub.app`); state; **service chips** (Electric, Water, Gas, Sewer, Trash, Broadband — multi-select, each color-coded).
- **Step 2 — How you bill**: rate style (Flat / Tiered-inclining / Time-of-use); billing cycle; bill-on day; tax region; currency; "Load standard charge codes & lookup tables" toggle (pre-checked). Everything pre-filled so the user can accept defaults.
- **Step 3 — Create your login**: owner name/email/password/mobile; a "you're setting up" recap block; terms checkbox → **Create utility & go live** → dashboard + welcome toast.

### 4. Dashboard
KPI strip + panels: cash today, method mix, outstanding/collections, billing status, exceptions to action, recent activity. All KPIs the customer asked for are present.

### 5. Settings
Tabbed: lookup tables (services, rate components, charge codes, tax authorities, meter types, reason codes, etc.), system settings, and **user management** (invite users, roles: Owner/Finance/Operator, permissions).

### 6. Plans & Rates
**Uniform action placement** — primary actions in the page header only (not duplicated in the body). Sub-areas: **Plans**, **Rates**, **Charge Codes**, **Taxes & Fees**. Each has an add form that opens as a **full page guided workflow** (not a modal):
- **New Plan** — guided: plan identity → attach services & rate schedules → base charges → review/publish.
- **New Rate** — guided: rate identity/service → structure (flat/tiered/TOU/demand) → tiers/prices → review/publish.
- **New Charge Code** and **New Taxes & Fees** — add forms (full page, not modal), consistent with the above.

### 7. Premises
Two tabs: **Premises** and **Units** (units live within premises). **Add is guided** and supports **single OR bulk creation** (bulk is critical — 100–3,000 units at once, e.g. an apartment complex). Unit creation assigns **Meter(s), Sub-meters, and Plan** to the unit; after selection the assigned resources are displayed for confirmation.

### 8. Accounts
- **List** with search/filter, services shown together per account (color-coded service tags).
- **New Account / Move-In / Move-Out** — all guided workflows. New Account step 3 takes **Premises + Unit** and displays the already-attached plan & resources (meters etc.) — you do NOT re-attach the plan there.
- **Account detail view** — header (account #, status, autopay, customer, service address, service tags), balance/plan/last-activity summary, action buttons, and **tabs**: Overview, Bills, Payments, Usage, Meters, Adjustments, Documents, Notes, Audit.
- **Detail actions** — each opens the right surface:
  - **Modals**: Record payment, Adjust, Send statement, Print bill (with preview), Issue credit, Disconnect notice (with letter preview), Add note.
  - **Redirect**: Move-out → the Move-out wizard prefilled at step 2.
  - **Guided full-page wizards**: Change plan (pick plan → effective date & proration preview → confirm & notify) and Payment plan (amount & term → editable installment schedule → send agreement).

### 9. Reads
Tabs: **Reads / Routes / Cycles**. **CSV upload wizard** (guided): upload & map → tag every reading to **month, route, cycle, meter, service, source** → run validation rules (**high / low / zero / mismatch / days-threshold / meter-factor**) → detailed per-read review → capture compliance metadata (who uploaded, when) → commit. Includes **estimated-reading logic** when reads aren't received (trailing-3-cycle average, true-up on next real read).

### 10. Billing (tabbed page; no submenu)
Default view lists all bills. Tabs include **Run bills**, plus **Bill correction**, **Single bill**, **Budget Bills** (even monthly / level-pay). Language is **business-user friendly and low cognitive load** with guidance copy throughout.

**Run Bills — guided workflow:**
- **Step 1** — pick cycle, date, template.
- **Step 2 — "Check what we found"** — primary **sub-tabs** with nested sub-tabs:
  - **Consumers** (filters: all/residential/commercial/excluded)
  - **Plans & Rates** (plans in use, base charges, referenced rate schedules)
  - **Meter reads** — nested tabs: All / Missing / Estimated / High / Low / Days threshold / Meter factor — each row has an inline **Fix** dropdown; bulk actions per tab.
  - **Open balances** (aging KPI strip + account rows, roll/payment-plan actions)
  - **Credits** (source per credit, apply/keep/skip)
  - **Over charges** — nested tabs: All / Late payment fees / Service charges — apply/waive actions.
- **Step 3 — case review** — one section per case (Used more than usual, No usage, Estimated, Owes a lot, Way past due, Late fee due, Extra charges). **Each case shows a data table with row checkboxes, a bulk-action toolbar, and per-row action dropdowns.**
- Then: generate bills → **summary** → capture compliance data → complete → offer **Print / Email / SMS**.

### 11. Payments
- **Summary tab**: today's total, method mix (ACH/Card/Check/Cash), failed payments, collections rollup (accounts owed, DSO, write-offs YTD).
- **Record payments tab**: single-column transaction table (Payment/Credit/Adjustment types; ACH/Card/Check/Cash/Lockbox methods). **Dark inverted bulk-action bar** with selection count + running total: Reverse, Reapply to bill, Send receipts, Post to QuickBooks, Export. Per-row action dropdown. Header actions: Import lockbox, Post adjustment, Issue credit, Record payment (visible on all tabs).
- **Outstandings tab**: 184 accounts sorted **high→low balance**; aging KPI strip; filters (age bucket, class); dark bulk-action bar: Send reminder, Disconnect notice, Payment plan, Field visit, Write off, Export; per-row dropdown including **Write off**. Wrapped in horizontal scroll so the wide table never breaks page layout.
- **Every bulk/row action opens a working modal** (Record, Credit, Adjust, Lockbox import with auto-match preview, Reverse, Reminder with tone + channel + preview, Disconnect notice with tier + delivery, Write-off with reason + GL + approval, Reapply, Send receipts, Post-to-QuickBooks, Schedule field visits).

### 12. Finance (sized for a 1–2 person shop)
Header: period + "hand off to bookkeeper by" date; actions Download period pack, Send to QuickBooks. Four tabs:
- **Revenue & AR** — billed/collected/owed/written-off KPIs; revenue by service (usage vs base vs tax vs collected); 12-month billed-vs-collected bar chart; AR aging rollup; adjustments & credits summary; pending-approvals.
- **Deposits & Bank** — daily deposit batches by method with **our-total vs bank-shows vs difference**; unmatched batches highlighted. **Bank import & reconcile wizard** (Upload statement / connect via Plaid → Review matches (auto/amber) → Confirm & lock). **Every batch ID is clickable → batch detail page** (payments in batch with bounced-check flag, bank-side posting, reconciliation trail/audit log). A **Resolve modal** diagnoses discrepancies (e.g. bounced check #4021 = the exact $100 gap → reverse + NSF fee + notify + audit note).
- **Taxes & Remittance** — collected by authority (rate, taxable base, filing period, due date, status); "coming up" deadline callout; filing history with confirmations/receipts.
- **Export to accounting** — balanced GL summary in plain English; one-click **QuickBooks Online** push (one summary journal entry per month, not per bill); CSV / IIF / Xero exports; connection status; pre-send checklist; export history.

### 13. Reports
- **Report library** tab: cards grouped Financial / Operations / Compliance; each card is clickable.
- **Scheduled & history** tab: scheduled reports (frequency, delivery, recipients, next run) + recent-runs log with re-download.
- **Report viewer** (full page): back link, parameter bar (date range, service, class, group-by, Run), KPI strip, data table (fully built for AR aging, Revenue by service & rate, Billing register; generic viewer for others), actions Favorite/Schedule/Export/Print.
- **Build your own**: dataset → columns (chips) → filter → group-by → date range → sort → Run/Save & schedule.

## Interactions & Behavior
- **Wizards**: numbered step rail; steps are clickable to jump back; Back/Continue in a right-aligned action row; final step has a confirm/commit button with a ✓ and fires a toast.
- **Guided pages vs modals**: creation/large flows are **full pages** (New Plan/Rate, Change plan, Payment plan, Bank import, Report viewer). Quick single actions are **modals** (record payment, adjust, credit, notices, notes). Move-out is a **redirect** into its wizard.
- **Bulk actions**: tables that support multi-select show a header checkbox + per-row checkboxes and a bulk-action bar (dark inverted style in Payments) with a live selection count and total.
- **Tabs**: horizontally scrollable on narrow viewports (never wrap/overflow the page).
- **Toasts**: appear after every committed action; ~2.5s auto-dismiss.
- **Collapsible sidebar**: persists collapsed/expanded.

## State Management
Per-module state to model (React: URL params + local/query state; server data via your API):
- Global: `module` (route), sidebar collapsed, current tenant, current user/role, toast queue.
- Accounts: `acctDetailId`, `acctDetailTab`, open action modal, Change-plan step, Payment-plan step.
- Billing: run-bills step, step-2 primary sub-tab + nested (reads/overcharges) sub-tab, step-3 selected case + row selections.
- Payments: `payTab`, open payment modal, row selections.
- Finance: `finTab`, `finView` (tabs/import/batch), bank-import step, `batchId`, open finance modal.
- Reports: `repTab`, `repView` (grid/viewer/builder), `repName`.
- Reads: reads tab, upload-wizard step.
- Premises: premises/units tab, add mode (single/bulk).
Data fetching: list endpoints with server-side filter/sort/pagination; detail endpoints; wizard submits are transactional (esp. billing run, reconciliation, write-offs — all need audit records).

## Design Tokens ("Modernist" design system)
Pull exact values from the project's `styles.css` at the design-system root. Key CSS variables used throughout:
- **Color**: `--color-bg`, `--color-surface`, `--color-text`, `--color-divider`, `--color-accent`, `--color-accent-700`, `--color-accent-300`. Accent is used for emphasis, primary buttons, and alert/attention states (via `color-mix` tints). Service colors: Electric/Water/Gas/Sewer/Trash/Broadband each have a distinct swatch (see `.svc-E/.svc-W/.svc-G/.svc-S/.svc-T/.svc-B`).
- **Type**: `--font-heading` (display/headings, weight 800, negative letter-spacing) and the body font; tabular numerals via `font-feature-settings:tnum` on all money/quantity cells.
- **Shape/ђedth**: mostly square/low-radius surfaces; 2px dividers as structural rules; `--shadow-lg` for modals/popovers.
- **Status pills**: `.pill.ok` (green), `.pill.warn` (amber), `.pill.past` (accent/red), `.pill.draft` (muted).
- **Components referenced**: `.btn` (`.btn-primary/.btn-secondary/.btn-ghost/.btn-icon`), `.card`, `.panel`, `.kpi-grid/.kpi`, `.table`, `.field/.input`, `.seg` (segmented radios), `.radio` (checkbox+dot), `.settings-tabs`, `.br-steps/.br-step` (wizard rail), `.wizard/.wizard-actions`, `.toolbar`, `.service-chip`, `.rep-grid/.rep`, `.two-col`, `.page-head/.page-actions/.kicker/.sub`.
Map these to your app's theme/components; don't hardcode hex where a token exists.

## Assets
No raster assets required. All icons are inline SVG (sidebar, service chips, close buttons). Logo is a text/lockup placeholder — swap for the customer's brand mark. Charts are CSS/flexbox bars (no chart lib) — replace with your charting library.

## Files
- `CLAUDE.md` — repo-root operating file for Claude Code.
- `04-docs/01-spec/` — A1–A17 extraction docs (`01-screen-inventory.md` … `17-open-questions.md`).
- `04-docs/02-decisions/` — B1–B8 (`architecture-decisions`, `database-design-brief` (=B2), `tenancy-and-security`, `money-math-rules`, `golden-tests`, `non-functional-requirements`, `integrations`, `coding-conventions`).
- `04-docs/03-contracts/` — pointer to the fixed interfaces.
- `05-prototype/` — self-contained runnable prototype (`UtilityBilling.html` + `styles.css` + `_ds_bundle.js` + `support.js` + `ds-base.js`).
- `UtilityBilling.reference.html.txt` — readable prototype source (use `05-prototype/` to run).
- `README.md` — this file.

## Known gaps — real design/product work still outstanding
The prototype is deliberately "happy path." Status as of 2026-08-07 (see `CHANGELOG.md`):
1. ~~Empty / loading / skeleton / error states~~ — **RESOLVED**: six shared patterns documented in `spec/18-empty-loading-error-states.md` (A18). Still to be *built* per screen.
2. ~~Semantic color tokens~~ — **RESOLVED**: success/warning/danger tokens added to `styles.css` + status pills bound to them (`spec/12-design-system.md` addendum).
3. **Mobile / small-screen** — explicitly **out of scope** in this prototype; responsive breakpoints stop at 1024px and below ~700px is undefined. If field/customer mobile use is needed, it is a separate design effort (the app is designed desktop-first for 1–2 back-office staff).
4. Remaining `UNKNOWN`/`INFERRED` items — see `spec/17-open-questions.md` (A17) and `decisions/02-database-design-brief.md` §6, ranked blocking/important/deferrable.

## Recommended build order
1. App shell (sidebar/topbar/routing) + design tokens mapping.
2. Settings + lookup tables (everything else depends on these).
3. Plans & Rates → Premises/Units → Assets (meters) → Accounts (data model backbone; Assets added per PO 2026-08-09 — meters must exist before reads).
4. Reads (+ estimation) → Billing run → Payments → Finance → Reports.
5. Public: Pricing → Welcome → Create-your-utility onboarding + tenant provisioning.
