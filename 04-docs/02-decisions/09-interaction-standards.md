# B9 — Interaction Standards (IS-1…IS-10)

> Cross-cutting UI behaviors defined ONCE. Screens declare conformance via a capability-matrix row in their epic file; stories never restate these. Owner: PM + Eng Lead; IS-5 pattern pending design ratification (OQ-013).

## IS-1 CRUD conventions
Create: guided full page for large flows, modal for quick adds (per design README). Update: audited, edit-in-place or modal. **Delete: deactivate-first** — hard delete only when `used_by = 0`; 🔒 audit-lock pattern (deactivate allowed, delete blocked) when referenced. Financial records never delete (corrections only, CLAUDE.md #4).

## IS-2 Tables & pagination
Server-side. ~~25/page default (50/100 options)~~ **Page-size options on screen = 50 / 100 / 200 / 500 / 1000, default 50 (PO ruling 2026-08-09, API batch Lane C); the `per` param clamps to this set.** Per-screen default sort from the capability matrix. Click-header single-column sort with direction toggle; stable secondary sort by id. Sorted column indicated visually.

## IS-3 Search
Per-list search box; server-side; debounced 300 ms; min 2 chars; searches only the fields declared in the capability matrix; clears via ✕.

## IS-4 Filters
Declared per screen; AND-combined; active filters shown as chips with clear-all; **state persisted in the URL** (shareable/bookmarkable, per the routing model).

**⚠ AMENDED 2026-08-21 (DEF-442) — THE CONTROL SHAPE IS NAMED NOW, BECAUSE NOT NAMING IT IS WHAT LET THE PRODUCT DIVERGE.** Every sentence above is about BEHAVIOUR, and the product satisfied all of it while drawing **one labelled `<select>` per dimension**, permanently in the toolbar, with the applied state visible only inside each closed control. Every IS-4 test passed on that drawing and on r10's, because none of them could tell the two apart — which is the defect's own `escape_reason`. The Product Owner reported it against the prototype: _"also look at Filter in Proto - it is panel and when you select somethibg it shows selection on screen ; look at filters you build"_.

**The drawing, from r10 (`SMARTBillHub.dc.html` line 763 · `table-tools.js` lines 106-177), which is the reference per the 2026-08-16 PO ruling:**

* **ONE `+ Filter ▾` button** (`btn-secondary btn-sm`) in the toolbar, whose tooltip names the declared dimensions — *"Filter by: Service, Structure, Status"* — before it is opened. Not one control per dimension.
* **It opens a PANEL** headed **`FILTER BY`**, with the declared options grouped by dimension as checkboxes.
* **Every applied filter is a REMOVABLE CHIP in the toolbar** — `Svc: Water ×` — sitting between the `All` chip and the button. This is the load-bearing half: *a list showing 1 of 7 rows must say WHY on screen, next to the control that undoes it.*
* **The `All` chip IS the clear-all.** It is inverted (`.fchip.active`) exactly while nothing is applied, and clears every filter when something is. There is no separate clear-all control, so read "with clear-all" above as satisfied by this chip.
* **Accessibility, which r10 does not supply and this standard now requires:** the panel must be keyboard-operable, each dimension's options must be grouped under a name a screen reader announces, and **each chip's remove control needs an accessible name identifying the filter it removes** — a bare `×` is not usable.

**Still one value per dimension.** BR-SHL-011 serialises one `f.<name>=<value>` and the server applies one per declared param; r10's panel multi-selects within a dimension and ours does not. **That divergence is OQ-304 and is NOT settled by this amendment.**

Implemented once, shared, in `07-frontend/src/components/FilterBar.tsx` — a screen never draws its own filter control.

## IS-5 Dynamic columns — UNIVERSAL requirement (PO-confirmed intent, Q&A R7)
PO rationale, recorded verbatim in spirit: every data table gives the user control of displayed columns so per-tenant column requests never require code changes. Server-persisted per user (BR-SHL-027).
Column-chooser menu per table: show/hide + reorder; per-user persisted (user preferences); identity column always visible; export follows the visible set. Interim spec: ⋮ menu top-right of table header.

## IS-6 Actions
Per-row dropdown (options vary by row state, per A2). Multi-select tables: header checkbox + dark inverted bulk-action bar with live selection count, plus running $ total on money tables. Every destructive or money action: modal → explicit confirm → toast → `audit_log` row. Role-forbidden actions render disabled-with-reason; enforcement is server-side (UI gating is convenience, A4).

## IS-7 States
Delegates to A18: empty list · zero-results-after-filter · loading skeleton · failed-with-retry (partial-success counts) · inline form validation · permission denied.

## IS-8 Language & formats
~~v1 ships English (US)… Spanish is v1.1 (shown disabled in design)~~ ~~**SUPERSEDED by PO ruling LC-1..3 (2026-08-08, BR-SHL-030/NFR-37): v1 ships FIVE data-driven language catalogs — en, es, es-MX, de, hi — extensible without code.**~~ **SUPERSEDED AGAIN by PO ruling 2026-08-10 (BR-SHL-041/042): ELEVEN region-qualified catalogs — `en-US · es-ES · es-419 · de-DE · hi-IN · fr-FR · id-ID · it-IT · ja-JP · ko-KR · pt-BR`. `es-MX` becomes `es-419`; catalogs load lazily, one locale at a time (BR-SHL-040).** Still true: all strings externalized; dates/numbers/currency render per tenant Regional settings; customer documents render server-side in the account's language (TD-16); tenant-authored template content is the tenant's own language already.

## IS-9 Export
CSV export respects current filters + visible columns; money 2dp; UTF-8; filename `<screen>-<tenant>-<YYYYMMDD>.csv`.

## IS-10 Accessibility basics
`:focus-visible` accent ring (design-system rule); modals trap focus and close on Esc/✕/backdrop; tables keyboard-navigable; toasts announced via aria-live.

## Capability-matrix row format (in each epic file)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |

## IS-11 Report downloads (PO-confirmed 2026-08-08)
Every report: **CSV always**; **PDF** where a formatted layout matters (finance/compliance/customer-facing). **No XLSX in v1** ("CSV please" — the A14 scheduled-reports "Excel" mention is corrected; XLSX v1.1 if asked). PDF skeleton: tenant letterhead · title · period · every active filter echoed · **date-basis label (BR-REP-001)** · generated-at (tenant TZ) + by whom · page X/Y · totals footer · IS-8 regional formats. CSV contract: UTF-8, comma, ONE header row, stable snake_case columns documented per report; money = plain 2dp, no symbols/separators; ISO dates; tenant-TZ timestamps w/ offset; NO metadata rows in the data — context in the filename `{tenant}_{report}_{period}_{basis}_{generated}.csv`. Guards per IS-9/BR-SHL-016 (streamed, RLS, 50k cap, money-export audit). Scheduled runs produce identical files; generated files retained **3 days, tenant-configurable** ("anyway we will email them"; email delivery W6 per BR-REP-017). Accounting handovers (IIF/Xero/QBO) are NOT reports — BR-LED-004 export batches.
