# CR-197-BRC10 · GL mapping becomes one list (add, edit, disable), with customer-class revenue and a refund account

**Raised:** 2026-10-29 by the Product Owner, in chat.

**Requester's words, verbatim:** *"we neeed to create one single tabl on list view ; we should allow to user to add, edit, update, disable functionality should be there"* — then *"Mapped for, start"*, *"Build the product screens based on images not on the content"* and *"use gl maping artifacts-https://claude.ai/artifact/Ue5p1oSzgQquUva1KZjf8Y"*.

**Design source:** the claude.ai artifact **https://claude.ai/artifact/Ue5p1oSzgQquUva1KZjf8Y** (version 4, "GL Mapping Redesign"), rendered to images and built to the images (B14 rule 42). Our UI standard decides spacing, sizes and components (rule 44).

**Ruling record:** decision log 2026-10-29 — *"GL mapping becomes one list: four questions ruled"* (Q1–Q4 all **A**), *"GL mapping types rationalised by accounting practice"*, *"the 'create it where it lives' links go INSIDE the Add form"*, and *"'Mapped for', start; build from the IMAGES"* (which also records our five judgments).

## 1 · Classification (step 1 of `13-change-process.md`)
A **change**: a live screen (Settings › Accounting › GL mapping, seven tables) is redrawn as one list with new acts (add, disable/enable) and two new capabilities (a revenue account per customer class; a refund account). Not the fast path — it touches the 🔒 GL resolution at issue, a payment posting, a migration and a new tenant table.

## 2 · What signed statement moves, and what stands
**Amended:** BR-LED-014 (the page's shape) — new BR-LED-800 · 801 · 802 · 803. **Stands, quoted:** BR-BIL-010 *"service → revenue GL with an optional usage/base split"* — the class row is consulted FIRST and the existing usage/base fallback is unchanged beneath it; an issued line keeps its stamp (hard rule 4). BR-PAY-014 *"DR customer-credit / CR cash"* stands whenever no account carries `refunds_payable`. B4/B5 ❄️ untouched — no figure moves.

## 3 · Impact
Ledger (list read, save, class table, designation, migration), billing (class passed to the revenue read at issue), payments (refund credit leg), rating and tenancy (published read/disable callables only — each owner still writes its own rows), web (one list component replacing seven tables), eleven catalogues, Plans & Rates / bill-run links into the filtered list.

## 4 · Already built and now wrong
The seven-table mapping panel in `SettingsAccountingTab.tsx` — replaced. Nothing written to data is wrong: the change is additive (no override rows exist; no account carries `refunds_payable`).

## 5 · Tasks (as approved)
Phase 0 this file + BR rows · Phase 1 server (1.1 list, 1.2 class override, 1.5 refund, 1.6 add/edit save, 1.7 disable/enable, 1.8 new-only proof, 1.9 audit, 1.10 tests red first) · Phase 2 web (one list, Add/Edit/Disable, eleven catalogues) · Phase 3 links · Phase 4 tests, PostgreSQL, browser walk, close.

## 6 · What is built
**Server.** `apps/ledger/gl_mapping_list.py` (rows, search, filters, pages of 50, counts, add/edit/disable/enable, audit) · `gl_mapping_api.py` (`GET/POST /ledger/gl-mappings/rows`, `…/add-options`, `…/edit-options`, `…/disable`, `…/enable`; any role reads, System Admin writes) · `gl_mapping_seams.py` (call-time seams onto rating's and tenancy's own new `gl_mapping_reads.py`, and customers' class list — no cross-module write) · migration **`ledger/0022`** (class-revenue table, RLS FORCE via `db/rls_ledger_class_revenue.sql`; `refunds_payable` in the designation CHECK) · `selectors.revenue_account_id_for_service(…, customer_class=)` · `billing/issue.py` (the bill's class reaches the revenue read; a discount's own account — `DEF-BIL-10648`) · `billing/posting_seam.py` (a discounts-only bucket is the signed contra-revenue debit) · `payments/ledger_seam.py` (refund credit → `refunds_payable` when set).
**Web.** `features/ledger/GlMappingList.tsx` + `glMappingEndpoints.ts` replace the seven tables (`SettingsAccountingTab.tsx` mounts it; a deep link `?type=&status=&q=` opens it filtered) · Phase 3 doors: the bill run's Not-sent panel ("Fix on GL mapping ›") and a charge code with no account ("Map it ›") · 108 keys in all eleven catalogues.
**Commits.** `49f2a6fee` phase 0 · `8875477a9` DEF-BIL-10648 filed · `ea14df8c3` server · `ec9d19b6c` web · `c32ddd2d7` web tests (⚠ its message repeats the web commit's — an amend slip; the CONTENT is the tests and the retired cases) · `f67db393b` phase 3 · `b6172538c` walk fixes (`DEF-LED-10661`, row order, muted disabled rows).
**Tests, red first.** `tests/test_cr197_gl_mapping_list.py` 14 cases — 4 FAILED against the pre-change money paths (`TypeError: … unexpected keyword argument 'customer_class'` ×2; refund credited cash; discount stamped the designation), then green; the audit case FAILED (`badly formed hexadecimal UUID string`) before `DEF-LED-10661`'s fix. With the designation, DEF-536, DEF-714 and CR-060 C10 suites: **86 passed, 2 skipped** (SQLite). **On PostgreSQL 16** (`-o DJANGO_SETTINGS_MODULE=config.settings.local`, a scratch cluster, `ledger/0022` and its RLS applied by migrate): `test_cr197_gl_mapping_list.py` **14 passed**. The run's role is the superuser, so it proves the migration and the money paths on the real database, not the isolation policy itself (that is the isolation probe's job). Web: `glMappingList.dom.test.tsx` 7 — 6 FAILED against the seven-table tab, then green; affected web suites 589 passed (2 rating wizard cases time out only under machine load and pass alone). 26 cases of `SettingsAccountingTab.test.tsx` that drew the superseded tables are retired with a note.
**Walk** (`/tmp/claude-0/-home-user-SMARTBillHub/485cfb0b-d736-50f8-b16f-919564c4d0d6/scratchpad/walk-glmap/`): Solar · Usage · Commercial → 4152 added in the browser; billed through the real issue service a commercial bill's Solar line stamped **4152**, a residential bill's **4151**; RECON → 4620, NSF → 4651, SENIOR → 4765 mapped; NSF disabled (cannot be charged: `charge_by_code('NSF')` is None); LATE 4200 → 4641 — the October bill keeps **4200**, the November bill stamps **4641**; refund $57.13 posted DR 2400 / CR **2450**. Design images `design/`, built images `built/`.
**Visible differences from the design, kept because our standard wins (B14 rule 44):** the toolbar is the kit's search + filter chips rather than three drawn selects; read-only fields in Edit are the kit's read-only inputs, not grey panels; the dialog notes are the kit's `Note`, not a tinted callout; the Disable button is the kit's danger tier (outlined). The Settings tab's own lede above the sub-tabs is unchanged (four tabs stay).
**Not done.** The correction preview (`billing/correction_answer.py`) still previews the every-class account for a class-overridden line (issue itself is right) — filed `DEF-BIL-10662`, open.

## 7 · Version and rollback
**No version bump in this lane** (coordinator's instruction). **Rollback:** revert the commits; the ledger migration reverses by dropping the class table and narrowing the designation CHECK back (refused only if an account already carries `refunds_payable`, which the revert would then have to clear by hand).

**Status:** DONE 2026-10-29 (no version bump in this lane). Open beside it: `DEF-BIL-10662`; the review-ledger row's three unshown decisions await the PO.
