// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3 (PO 2026-08-23) — B14 rule 16 for the FIVE list tables
//          that are not the shared DataTable: the SET-06 premises picker, the
//          SET-06 meter list, the SET-07 route picker, and the S26/S27 ops tabs.
// Defects: DEF-223 — *"two wizard list tables with no pagination footer"*,
//          measured in Chromium and open since 2026-08-17.
// Story:   US-MET-005 · US-MET-006  Screens: SET-06.2/.3 · SET-07.2 · S26 · S27
// Rules:   B14 rule 16 (*"Pagination footer on EVERY list table … Wizard SUMMARY
//          tables are exempt"*) · BR-SHL-010 (a screen renders what it declares)
// B13:     kit row — see 04-docs/02-decisions/13-component-registry.md
// ───────────────────────────────────────────────────────
/**
 * The pagination footer, for a list that is **not** the shared `DataTable`.
 *
 * ⚠ **WHY A SECOND THING THAT PAGES, WHEN `DataTable` ALREADY PAGES.** It does
 * not page the same lists. `DataTable` owns server-paginated screens: it takes a
 * `TableRequestState`, a total from the server and a config, and it owns the
 * toolbar, the sort and the column chooser too. The five tables above are
 * client-held arrays inside a wizard step or a read-only ops tab — no request
 * state, no server total, nothing to sort server-side — and putting them on
 * `DataTable` would hand a wizard picker a column chooser and hand S26 a search
 * box, which BR-MET-011's own suite reads as a mutating affordance.
 *
 * ⚠ **AND IT IS ONE IMPLEMENTATION, NOT A SIXTH.** This is lifted verbatim from
 * `RoutesCyclesWizards.WizardPager`, which was already the footer's second copy;
 * the four `table.pager.*` keys and the `table-pager*` classes are the SHARED
 * ones `DataTable` uses, so every footer in the product is one thing. DEF-348
 * counted four copies of one pencil — a pager is a bigger pencil.
 *
 * B14 rule 16's own exemption still holds: a wizard SUMMARY table (SET-06.4,
 * SET-07.4) shows a handful of rows about one thing and carries no footer.
 */
import { useTranslation } from "react-i18next";

import { PAGE_SIZES } from "./tableTypes";
import type { PageSize } from "./tableTypes";

export interface ListPagerProps {
  total: number;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
  /** The catalogue keys for the range and the size label when the list does
   *  NOT page in rows — the asset Reads tab pages in READ DATES (`AST-B-24`),
   *  so its footer says so rather than reading *1–4 of 4* under five rows
   *  (`DEF-AST-9691`). Default: the shared `table.pager.*` row words. */
  rangeKey?: string;
  sizeKey?: string;
}

export function ListPager(props: ListPagerProps) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(props.total / props.per));
  return (
    <div className="table-pager mt-2">
      <span className="table-pager-range">
        {t(props.rangeKey ?? "table.pager.range", {
          // A page of nothing reads "0–0 of 0", not "1–0 of 0": the first row
          // of an empty list does not exist and must not be numbered.
          from: props.total === 0 ? 0 : (props.page - 1) * props.per + 1,
          to: Math.min(props.page * props.per, props.total),
          total: props.total,
        })}
      </span>
      {/* ⚠ **B14 RULE 16 ASKS FOR `Page x of y` AND THIS FOOTER NEVER DREW IT**
          (added 2026-09-05 with `DEF-CWP-3977`). The rule's own text is
          *"Showing 1-50 of N · Rows per page 50/100/200/500/1000 · ⇤ ← Page x
          of y → ⇥"*, and the two arrows were the whole of it here — so a person
          could page and could not tell how far through they were. It is added
          in the SHARED footer rather than in the portal's caller for the reason
          the header of this file already gives: one footer, one look. The five
          staff lists that compose this gain the label with it, which is rule 16
          arriving where it was always owed. */}
      <span className="table-pager-range">{t("table.pager.pageOf", { page: props.page, pages })}</span>
      <label className="table-pager-size">
        {t(props.sizeKey ?? "table.pager.pageSize")}
        <select
          value={props.per}
          onChange={(event) => props.onPer(Number(event.target.value) as PageSize)}
        >
          {PAGE_SIZES.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="table-page-btn"
        disabled={props.page <= 1}
        aria-label={t("table.pager.prev")}
        onClick={() => props.onPage(Math.max(1, props.page - 1))}
      >
        ‹
      </button>
      <button
        type="button"
        className="table-page-btn"
        disabled={props.page >= pages}
        aria-label={t("table.pager.next")}
        onClick={() => props.onPage(Math.min(pages, props.page + 1))}
      >
        ›
      </button>
    </div>
  );
}

/** The window a `ListPager` describes — the ONE place a page is sliced, so a
 *  footer saying "51–100 of 320" and the rows under it cannot disagree. */
export function pageSlice<Row>(rows: readonly Row[], page: number, per: PageSize): Row[] {
  return rows.slice((page - 1) * per, page * per);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-029 RC-W3 (B17 §7) — B14 rule 16 on the five non-DataTable lists
// generated: 2026-08-23 by the RC-W3 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (ListPager.test.tsx)
// exceptions: E4 the `table-pager*` classes are DataTable.css's and are reused deliberately — one footer, one look; B14 rule 21 governs NEW classes and this file declares none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
