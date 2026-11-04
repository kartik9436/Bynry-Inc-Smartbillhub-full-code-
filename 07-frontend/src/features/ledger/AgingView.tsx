// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint `P2.21` — *"The Aging view over the `ar_aging`
//           report, and the report's paging and filters"*, full stack, and the
//           last buildable task of Finance phases 0–5.
// Drawing:  05-prototype/07 Finance Blueprint.pdf — **p034** carries the view's
//           own header (`2·2 Aging`, `/:tenant/finance/revenue?view=aging`) and
//           the box that rules *"Build the view over the report; do not copy
//           the report into Finance"*; **p035** is the wireframe, the five
//           numbered notes, the binding FILTER CRITERIA table, the COMPONENTS
//           TO USE table and the FOR / DOORS / PRIMARY ACTION rows; **p036**
//           carries FIELDS, TABLE CONTROLS, WRITE SURFACES and RULES.
//           Built from the RENDERED IMAGES (B14 rule 42), never from the text
//           layer — which for this document is scrambled.
// Defect:   `DEF-REP-6607` — the task was HANDED BACK rather than half-built,
//           because the report could not be paged or filtered at all and doing
//           it naively would have made the tie-out accuse the books of not
//           footing. That handback is this file's specification.
// Rules:    B14 rule 2 (one page header — the page owns it, not this panel) ·
//           rule 12 (search + filter chips) · rule 13 (sortable headers) ·
//           rule 14 (the shared ColumnChooser) · rule 16 (a pagination footer) ·
//           rule 20 (ONE table type) · rule 21 (Tailwind utilities, no new
//           stylesheet class — this file is on
//           `07-frontend/src/styles/route-b-migrated.txt`) · rule 31 (no
//           database id is ever a visible value) · rule 32/33 (the copy budget;
//           RATIONALE is zero words on screen) · rule 43 (a piece of UI is a
//           COMPONENT, not 120 lines inside a page) · rule 44 (our spacing,
//           sizes, type scale, tokens and component kit decide HOW it is built,
//           on every screen including the frame) ·
//           BR-REP-001 (every money surface labels its basis) · BR-REP-008 (the
//           ageing foots to the AR tie-out) · BR-REP-030 (FIVE bands) ·
//           BR-PAY-032 (days late = as_of − the oldest unpaid due date) ·
//           BR-SHL-011 (the URL grammar) · BR-SHL-023 (one money path) ·
//           BR-SHL-025 (a control this deployment cannot honour is not offered)
// ───────────────────────────────────────────────────────
//
// 2·2 AGING — *"who owes you"*, one row per debtor.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS HERE BEFORE, AND WHY THIS IS A NEW FILE
// ══════════════════════════════════════════════════════════════════════════
// `?view=aging` mounted `AgingPanel` — a five-row fact list that rendered a
// STATED ABSENCE, because `GET /finance/revenue-ar` serves `aging: null` with
// its reason (a journal line carries no due date, so the books cannot split
// the receivable). That panel was honest and it was not the screen: p036's own
// TODAY row reads *"No Finance screen. The `ar_aging` report and a Dashboard
// panel only"*.
//
// The data is the `ar_aging` REPORT and this view is built OVER it — p034's
// box, verbatim: *"Build the view over the report; do not copy the report into
// Finance."* So there is no new endpoint, no second aging arithmetic, and
// nothing here re-derives a band.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ROWS ARE THE SERVER'S PAGE. NOTHING HERE SLICES, SORTS OR FILTERS THEM
// ══════════════════════════════════════════════════════════════════════════
// `totalRows` is the report's own `page.total`, which is a SQL `COUNT` over the
// whole FILTERED set. A screen that re-sorted the page it was handed would
// silently disagree with the pager beside it — which is the defect `P2.21`
// exists to remove, not to move one layer up.
//
// ⚠ **AND THE FOOTER FIGURES ARE THE SERVER'S TOO, FOR THE REASON THE TASK WAS
// HANDED BACK.** `totals` is a SQL aggregate over the whole filtered set, so it
// foots to the rows whether a page is cut or not; the tie-out is struck by the
// server against the UNFILTERED population, so no chip and no search can make
// this screen say the general ledger is broken.
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import type { ReportResponse, ReportRow } from "@/api/reportsEndpoints";
import { isReportGroupRow } from "@/api/reportsEndpoints";
import { DataTable } from "@/components/DataTable";
import { DownloadButton } from "@/components/DownloadButton";
import { FilterBar } from "@/components/FilterBar";
import { AmountCell } from "@/features/reports/ReportViewerPage";
import { Panel } from "@/components/Panel";
import { ReportGapList } from "@/features/reports/reportsShared";
import { gapSentence } from "./financeShared";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/metering/meteringShared";
import { InlineLinkTo } from "@/components/Surfaces";
import { debtorDetailPath } from "@/features/payments/debtorsTable";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

type Translator = (key: string, params?: Record<string, unknown>) => string;

/** B14 rule 14 — the chooser persists per user under this id. */
export const AGING_SCREEN_ID = "finance.aging";

/**
 * p035's `f.band` values — **FIVE**, and they are the server's own spellings.
 *
 * `BR-REP-030` is PO-confirmed at five (*"Current / 1–30 / 31–60 / 61–90 /
 * 90+"*) and the report served four until 2026-09-24, folding `current` and
 * `1-30` into one column (`DEF-REP-6659`). A local array is what makes a
 * vocabulary drift — the eleventh service went missing on screen exactly this
 * way (hard-won law 2) — so these are written once here, asserted against the
 * report's own `columns` by `agingBands.test`, and never re-typed per cell.
 */
export const AGING_BANDS = ["current", "1-30", "31-60", "61-90", "90+"] as const;

/** The band's `f.band` value → the report column that holds its money. */
export const BAND_COLUMN: Record<string, string> = {
  current: "current",
  "1-30": "d1_30",
  "31-60": "d31_60",
  "61-90": "d61_90",
  "90+": "d90_plus",
};

/**
 * ⚠ **TWO SORTS, AND THE ABSENCE IS THE POINT (`DEF-REP-6660`).** p035 draws a
 * `⇅` on ACCOUNT as well as on TOTAL. `account_no` and the customer's name live
 * on CUSTOMERS' table, which the ageing statement does not join (`B1` /
 * `BR-TEN-013`), so the server cannot order by either — and offering the caret
 * anyway would sort the fifty rows that were already cut, which is the defect
 * this whole task exists to remove. `BR-SHL-025`: the control is not offered.
 */
export const AGING_SORTS = ["total", "days_late"] as const;

/** A band cell. */
function bandCell(row: ReportRow, key: string, currency: string | null, locale?: string) {
  const amount = row[key];
  // p035's COMPONENTS table, verbatim: *"A dash means **nothing owed in this
  // band** — never an unknown."* `$0.00` in four of five columns is a wall of
  // zeros a reader has to subtract; a dash is the fact.
  if (amount === null || amount === undefined || Number(amount) === 0) {
    return <Dash />;
  }
  // `AmountCell` is S46's own money cell and is reused rather than re-written:
  // it is the one renderer that already answers a NULL currency honestly (a
  // tenant whose open bills are in more than one currency has a footer that is
  // not a number, so the report serves `currency: null`).
  return <AmountCell amount={String(amount)} currency={currency} locale={locale} />;
}

export function agingConfig(
  report: ReportResponse | null,
  t: Translator,
  locale: string | undefined,
  options: { services: { value: string; label: string }[] },
  tenantPath: (path: string) => string = (path) => path,
): TableConfig<ReportRow> {
  const currency = report?.currency ?? null;
  const money = (key: string) => ({
    key,
    label: t(`finance.aging.col.${key}`),
    numeric: true,
    cell: (row: ReportRow) => bandCell(row, key, currency, locale),
  });
  return {
    screenId: AGING_SCREEN_ID,
    // B14 rule 31 — `account_id` keys React and the preference store and
    // reaches NO cell. The identity column is the ACCOUNT NUMBER, which is the
    // string a finance officer says out loud.
    getRowId: (row) => String(row.account_id ?? row.account_no ?? ""),
    searchFields: ["account_no", "customer_name"],
    // p035 note 2 — *"Search account or customer…"*, which is what the server
    // matches and nothing wider.
    searchPlaceholder: "finance.aging.searchPrompt",
    defaultSort: { sort: "total", dir: "desc" },
    filters: [
      {
        name: "band",
        label: t("finance.aging.filter.band"),
        options: AGING_BANDS.map((value) => ({
          value,
          label: t(`finance.aging.band.${value}`),
        })),
      },
      {
        // p035's `f.service` — the tenant's OWN services from
        // `GET /reference/services`, eleven of them including Fire. The drawing
        // authorises no literal array and this file holds none.
        name: "service",
        label: t("finance.aging.filter.service"),
        options: options.services,
      },
    ],
    columns: [
      {
        key: "account_no",
        label: t("finance.aging.col.account"),
        identity: true,
        // Record links (PO 2026-10-19): the number opens the DEBTOR page — the
        // door the Outstandings list and the collections screens open.
        cell: (row: ReportRow) => {
          if (row.account_no === null) {
            return <Dash />;
          }
          const href = debtorDetailPath(String(row.account_no));
          return href === null ? (
            String(row.account_no)
          ) : (
            <InlineLinkTo to={tenantPath(href)}>{String(row.account_no)}</InlineLinkTo>
          );
        },
      },
      {
        key: "customer_name",
        label: t("finance.aging.col.customer"),
        cell: (row: ReportRow) =>
          row.customer_name === null ? <Dash /> : String(row.customer_name),
      },
      money("current"),
      money("d1_30"),
      money("d31_60"),
      money("d61_90"),
      money("d90_plus"),
      {
        key: "total",
        label: t("finance.aging.col.total"),
        numeric: true,
        sortable: true,
        cell: (row: ReportRow) => (
          <AmountCell amount={String(row.total ?? "0")} currency={currency} locale={locale} />
        ),
      },
      {
        // IS-5's "+days-late", offered through the ▦ chooser and OFF by
        // default — p035 draws eight columns and this is the ninth.
        key: "days_late",
        label: t("finance.aging.col.days_late"),
        numeric: true,
        sortable: true,
        defaultVisible: false,
        // BR-PAY-032. Empty when nothing is past due — a 0 would read as "due
        // today", which is a different and false statement.
        cell: (row: ReportRow) =>
          row.days_late === null || row.days_late === undefined ? (
            <Dash />
          ) : (
            String(row.days_late)
          ),
      },
    ],
  };
}

export interface AgingViewProps {
  report: ReportResponse | null;
  loading: boolean;
  error?: { reason?: string; onRetry: () => void } | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  locale?: string;
  /** The tenant's OWN services — `GET /reports`' live vocabulary (BR-REP-006),
   *  never a literal array. p035: *"eleven, incl. Fire"*. */
  services: { value: string; label: string }[];
  /** The position's date, already formatted by the page. p035 draws it as a
   *  chip; the DATE is the Finance page's own period and is shown as a FACT
   *  rather than as a second control that would disagree with the page head. */
  asOfLabel: string;
  /** The property criterion's picker, built by the page from the shared field. */
  premisesSlot?: React.ReactNode;
  onDownload: () => void;
}

/**
 * The whole of 2·2 — the panel, the toolbar, the table and the footer.
 *
 * The KPI strip p035 draws above this view belongs to the PAGE and is not
 * repeated here (B14 rule 2 — one page header, one strip).
 */
export function AgingView(props: AgingViewProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const tenant = useTenant();
  const config = useMemo(
    () =>
      agingConfig(props.report, translate, props.locale, { services: props.services }, (path) =>
        tenantPathFrom(tenant, path),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.report, props.locale, props.services, t, tenant],
  );

  return (
    <Panel>
      {/* B14 rule 44 — the gap is `--space-4` from the scale and the heading is
          the kit's panel heading. The page head's 32px title (rule 40) belongs
          to the PAGE. */}
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="m-0 font-heading text-h5 leading-heading">
          {t("finance.aging.title")}
        </h3>
        <div className="flex items-center gap-3">
          {/* B14 rule 33 — a FACT, four words, no sentence. The receivable is a
              POSITION at a date and a reader who cannot see which date is
              reading an unlabelled number. */}
          {/* ⚠ **`text-sm`, NOT `text-body-sm` (`DEF-LED-6696`).** There is no
              `--text-body-sm` on the scale — the steps are `xs · sm · base ·
              md · body` — and `tokens.css` sets `--text-*: initial`, which
              deletes Tailwind's OWN scale, so `text-body-sm` compiled to NO
              RULE AT ALL and this line rendered at the browser default while
              `tsc`, eslint and every `toContain` assertion passed on it,
              because the class genuinely IS in the DOM. `text-sm` is the step
              the scale calls *"dense table body, captions"* and is what
              `AccrualsWorkbench.tsx` uses for the same kind of note. */}
          <span className="text-sm text-neutral-700">
            {t("finance.aging.asOf", { date: props.asOfLabel })}
          </span>
          <DownloadButton onDownload={() => props.onDownload()} />
        </div>
      </div>
      <DataTable<ReportRow>
        config={config}
        state={props.state}
        onStateChange={props.onStateChange}
        // ⚠ **THE GROUP ROWS ARE EXCLUDED BY TYPE AND BY FACT** (`P2.18`,
        // 2026-09-27). `ReportResponse.rows` became `(ReportRow |
        // ReportGroupRow)[]` when the server began inserting subtotals; THIS
        // screen never sends `group_by`, so it never receives one, and the
        // narrowing below is a type-level statement of that rather than a
        // silent drop. If this screen ever gains a grouping control the filter
        // starts hiding real rows, so it is written to be found: the predicate
        // names the kind it removes.
        rows={(props.report?.rows ?? []).filter(
          (row): row is ReportRow => !isReportGroupRow(row),
        )}
        // The server's COUNT over the whole filtered set — never `rows.length`,
        // which is the page and would make the pager describe itself.
        totalRows={props.report?.page?.total ?? null}
        loading={props.loading}
        error={props.error}
        filterBarSlot={
          <div className="flex flex-wrap items-end gap-3">
            <FilterBar
              filters={config.filters ?? []}
              state={props.state}
              onStateChange={props.onStateChange}
            />
            {props.premisesSlot}
          </div>
        }
        empty={{
          title: t("finance.aging.noMatchTitle"),
          helper: t("finance.aging.noMatchHelper"),
          ctaLabel: t("finance.aging.clearSearch"),
          ctaVariant: "secondary",
          onCta: () => props.onStateChange({ ...props.state, q: "", filters: {}, page: 1 }),
        }}
      />
      {/* ⚠⚠ **THE SERVER'S OWN REFUSALS, AND LEAVING THEM OUT WAS THIS VIEW'S
          WORST BUG — CAUGHT BY LOOKING AT A SCREENSHOT AND BY NOTHING ELSE.**
          `GET /reports/ar_aging` attaches every absence it found, and on the
          seeded utility that is TWO: the imported opening buckets nobody has
          built, and — the one that matters — **the ageing does not foot to the
          ledger's AR control**, `9,598.15` against `24,992.65`. The first
          version of this file rendered neither, so a finance officer read a
          receivable that the report itself was saying is short by fifteen
          thousand dollars, with nothing on the page to tell them.

          ⚠ **AND THE WALKTHROUGH'S OWN CHECK PASSED OVER IT VACUOUSLY.** It
          asserted that searching does not make the screen say the books do not
          foot — which was true because the screen could not say it at all.
          That is hard-won law 7's *check that cannot fail*, in this lane's own
          test, and the walk now asserts the sentence is PRESENT and quotes the
          whole-population figure.

          B14 rule 32 — a stated absence is a disclosure, and `ReportGapList` is
          the ONE renderer for it (rule 43: the component is reused, not
          rebuilt; it is what S46 draws for this same report). */}
      <ReportGapList
        gaps={props.report?.unavailable ?? []}
        title={t("finance.gap.title")}
        render={(gap) => gapSentence(gap, t)}
      />
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: Finance blueprint `P2.21` (p034–p036) · `DEF-REP-6607`'s handback
// screens: S36 `?view=aging` (2·2)
// generated: 2026-09-24 by lane FIN-AGING
// gates: tsc✔ eslint --max-warnings 0✔ vitest✔
// exceptions: (1) ACCOUNT and CUSTOMER carry no sort caret — the server cannot
//   order by a column it does not join (`DEF-REP-6660`) · (2) the PROPERTY
//   criterion is passed in as a slot rather than declared as a chip: its values
//   are the tenant's premises, which is an unbounded list, so it uses the
//   remote-search field the General ledger already owns · (3) this view writes
//   nothing — p036's WRITE SURFACES row reads *"None here"*
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
