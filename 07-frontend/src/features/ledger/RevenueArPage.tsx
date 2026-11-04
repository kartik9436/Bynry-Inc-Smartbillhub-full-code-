// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-007 (S36 Revenue & AR — the KPI strip, Revenue by service,
//           the aging panel, the Adjustments & credits panel, the cash position
//           and the tie-out panel, every one of them dimension-derived and
//           basis-labeled)
//           Screens: S36 (AppShell sidebar → Finance → Revenue & AR)
// Rules:    BR-LED-016 (the strip is dimension-derived — revenue, collected,
//           AR, aging) · BR-LED-007 (the tie-out panel renders here; the
//           COMPARISON is US-LED-004 and is not built) · BR-REP-001 (every KPI
//           and panel header labels its date basis) · BR-REP-002 (read-models
//           over journal-line dimensions, never a side-maintained number) ·
//           BR-REP-006 (filters and vocabularies enumerate the LIVE set) ·
//           BR-REP-009 (collection % — cash applied to bills IN PERIOD) ·
//           BR-REP-011 (DSO) · BR-REP-014 (collections count BILL-purpose
//           payments only) · BR-TEN-022 (periods are COMPUTED from fiscal
//           settings, never stored) · BR-SHL-011 (the URL grammar) ·
//           BR-SHL-012 (the A18 shared states) · BR-SHL-020 (plain-language
//           failure) · BR-SHL-023 (one money formatting path) · BR-SHL-025 (a
//           control this deployment cannot honour renders disabled WITH its
//           reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S36 — Revenue & AR.
//
// `apps/ledger/reporting.py` landed on 2026-08-11: the trial balance foots
// 598.69 = 598.69 through the real posting service, LE-2's service slice
// reproduces verbatim, the four account-ledger closings sum to the 152.32 AR
// control — and its own Lifecycle trailer records `E=deferred(no-frontend-half
// — 07-frontend/src/features/ledger and .../reports are a README each)`. Every
// number in this product's books existed and **no human being could see one**.
// This is the screen.
//
// ══════════════════════════════════════════════════════════════════════════
// THE FOUR NULLS ARE THE FEATURE, NOT THE GAP
// ══════════════════════════════════════════════════════════════════════════
// The read model refuses four figures the prototype draws, each with a named
// reason, and this screen RENDERS THE REASON in the slot where the figure would
// have been. It never substitutes a computed stand-in:
//
//   · **Collection %** — the prototype's "87% of billed". BR-REP-009 defines the
//     numerator as *cash applied to bills IN PERIOD*, which US-LED-007 §7 works
//     to 401.37 and 72.49%. A payment entry credits AR in one lump, so the
//     ledger cannot say which bill the cash met. The ratio it COULD compute is
//     446.37 ÷ 553.69 = 80.62% — a different ratio wearing the ruled one's name.
//     Not rendered, at all.
//   · **DSO** — the prototype's "DSO 18.4d". BR-REP-011's formula is exact and
//     its twelve-month denominator is not, for a tenant three months old.
//   · **The aging buckets** — the prototype's whole "Who owes you" table. A
//     journal line carries no due date. The TOTAL those buckets must sum to IS
//     derivable and IS rendered, so the panel shows the real total and states
//     that the split is not available. Four confident zeros would have been the
//     alternative.
//   · **Per-service Tax and Collected** — two of the six columns of the Revenue
//     by service table. A tax line carries no `service` dimension and cash
//     carries no invoice attribution.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS SCREEN DIVERGES FROM `05-prototype/UtilityBilling.html`
// ══════════════════════════════════════════════════════════════════════════
// Hard-won law 6 says diff against the prototype and report BOTH directions.
//
//   · The prototype folds collection % into the Collected tile's detail line
//     and DSO into Still-owed's. Both are unavailable-with-a-reason, and a
//     reason does not fit in a detail line — so each gets its own tile. Six
//     tiles where the design draws four.
//     ⚠ **AND THE REASON IS NOW BEHIND A DISCLOSURE (2026-09-01, B14 rule 32).**
//     "A reason does not fit in a detail line" was true and the conclusion drawn
//     from it was wrong: three of the six tiles printed a three-sentence
//     paragraph inside a 180px tile, the strip went ragged, and the PO
//     photographed it — *"too much content - desctiption is too much for clark
//     to read"*. A closed tile now reads *Not available*; the sentence is one
//     click away and is shorter. Nothing was deleted.
//   · **No "Billed vs collected · last 12 months" chart.** It needs twelve
//     periods; this read model answers for ONE. The panel renders with the
//     reason rather than with a bar chart of one bar.
//   · **No "↑ 8.4% vs Jul" on Billed** and **no "0.4% of revenue" on Written
//     off**: both compare against a period the response does not carry.
//   · **The "Export →" link on Revenue by service** is replaced by a link to
//     the By-premises summary (S60) — the same query grouped by premises, which
//     is where a finance officer actually goes next. The export it pointed at is
//     `POST /reports/{key}/export`, which no deployment serves.
//   · **"Review 8 pending →" is disabled with its reason.** The count is a
//     billing-register read (things that have NOT reached the books), which is
//     by definition not a ledger question, and no endpoint serves it.
//   · **A cash-position panel the prototype does not draw.** PO ruling
//     2026-08-11 (OQ-143) splits receipts into 1000 Cash and 1010 Undeposited
//     and the read model returns them separately, never summed. A screen that
//     showed one "cash" number would tell a utility it has money in the bank
//     that is sitting in a drawer.
//   · **The page head's "August 2026 · Open · Hand off to your bookkeeper by
//     Sep 3" is real** — it is `GET /settings/regional`'s `current_period`, not
//     a client-side calendar month (BR-TEN-022).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  approveWriteOff,
  getRefunds,
  getRegionalSettings,
  getRevenueAr,
  getTieOuts,
} from "@/api/endpoints";
import type {
  CurrentPeriod,
  LedgerUnavailable,
  RevenueArResponse,
  ServiceRevenueRow,
  ShellDisplayPeriod,
  TieOutsResponse,
  TieOutState,
  WriteOffApproved,
} from "@/api/endpoints";
import { AbsentFigure, isFigureAbsent } from "@/components/AbsentFigure";
import { AgingView, agingConfig } from "./AgingView";
import { PeriodPackButton } from "./PeriodPackButton";
import { PremisesFilterField, usePremisesSearch } from "./financeShared";
import { getReportLibrary, runAgingReport, requestReportExport } from "@/api/reportsEndpoints";
import { dateRangeFilter, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { clientPage } from "@/components/clientTable";
import type { ClientTableSpec } from "@/components/clientTable";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { DateCell, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell, formatMoney, isAmountAbsent } from "@/components/MoneyCell";
import { sumAmounts } from "@/components/moneyMath";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { Panel } from "@/components/Panel";
import { InlineLink } from "@/components/Surfaces";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import {
  Dash,
  GuardedButton,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
// `DEF-LED-9120` — the ONE service word product-wide (`rating.service.*`,
// `DEF-763`), mounted rather than typed out again.
import { serviceLabel } from "@/features/assets/assetsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  AbsentPanel,
  FINANCE_PERMISSION,
  FINANCE_TABS,
  FINANCE_TAB_REVENUE,
  FactRow,
  financeTabFrom,
  financeTabPath,
  gapFor,
  gapSentence,
} from "./financeShared";
import { ViewStrip, withView } from "./financeViewStrip";
import { CUSTOMER_STATEMENT_ROUTE } from "@/features/reports/CustomerStatementPage";
import { BY_PREMISES_ROUTE } from "@/features/reports/reportsShared";
// CR-059 CS-26 (task 65). Payments owns the read (`apps/payments/bad_debt.py`)
// and BR-PAY-020 puts the REPORTING in Finance, which is why the component
// lives in `features/payments` and is drawn here — the same split
// `WriteOffQueuePanel` above already makes for the approval.
import { BadDebtPanel } from "@/features/payments/BadDebtPanel";
import { WriteOffQueueTable } from "@/features/payments/WriteOffQueuePage";
import { getWriteOffApprovalQueue } from "@/api/bankRecEndpoints";
// CR-060 C25 / T10, PO ruling 2026-09-03. Refunds STOPPED BEING A TAB and became
// a panel here — the same split again: payments owns the queue
// (`apps/payments/refunds.py`) and this is the Finance-area screen that draws
// it. The tab it landed in is `C25`'s own principle rather than a preference:
// write-offs folded here *"where the receivable it gives up already lives"*,
// and a refund gives back money the account holds as CREDIT.
import {
  RefundsQueuePanel,
  refundsQueuePanelQueryKey,
} from "@/features/payments/RefundsQueuePanel";

import "./finance.css";

// ── The gap codes this screen renders, named once ─────────────────────────
// These are `apps/ledger/reporting.py`'s own stable identifiers. Named as
// constants rather than typed inline so a rename on the server side is one
// failing test here, not four screens quietly rendering the fallback sentence.
export const GAP_COLLECTION_PCT = "which_bill_a_payment_met_is_not_in_the_books";
export const GAP_DSO = "dso_needs_twelve_months_of_billed";
export const GAP_AGING = "aging_buckets_need_invoice_due_dates_and_opening_buckets";
export const GAP_SERVICE_COLUMNS = "per_service_tax_and_collected_columns";
export const GAP_LATE_FEES = "late_fee_revenue_has_no_designation";
export const GAP_PENDING_APPROVAL = "pending_approval_count_is_not_a_ledger_fact";
/** DEF-151. `apps/ledger/wire.py`'s own identifier for the sixth tile's absence. */
export const GAP_WRITTEN_OFF_YTD = "written_off_ytd_window_was_not_stated_by_the_caller";

/**
 * Every gap code THIS SCREEN already states somewhere, so `UnclaimedGaps` does
 * not state it a second time at the foot of the page (B14 rule 32: one stated
 * absence appears ONCE on a screen).
 *
 * ⚠ **EXPORTED SO A TEST CAN PIN IT, AND THAT IS THE POINT.** It was an inline
 * array literal in the JSX and `GAP_WRITTEN_OFF_YTD` was never added to it when
 * DEF-151 gave that figure a tile — so the SAME 49-word sentence printed in the
 * KPI tile and again in a full-width panel at the bottom of `/finance`, and the
 * PO photographed it (2026-09-01). Nothing could have gone red: the list was a
 * literal inside a render tree no test mounts. `revenueArDemoTenant.test.tsx`
 * now asserts, against the RECORDED wire, that every code the server sends is
 * in this list — so the next gap that gets a tile and not a line here fails.
 */
export const S36_CLAIMED_GAPS = [
  GAP_COLLECTION_PCT,
  GAP_DSO,
  GAP_AGING,
  GAP_SERVICE_COLUMNS,
  GAP_WRITTEN_OFF_YTD,
  // The Adjustments panel states these two. They arrive on
  // `report.adjustments.unavailable` today rather than on `report.unavailable`,
  // so they are filtered from a list they are not in — deliberately: the day the
  // wire moves one up a level, this screen states it once instead of twice.
  GAP_LATE_FEES,
  GAP_PENDING_APPROVAL,
] as const;

export const revenueArQueryKey = (period: string) => ["finance", "revenue-ar", period] as const;

// ── `P2.18` — the view strip ───────────────────────────────────────────────

/**
 * **FIVE VIEWS, AND THE NUMBER WAS CONTESTED INSIDE THE BLUEPRINT ITSELF.**
 *
 * Finance blueprint p015 (`P2.18`) and p032 (tab 2's own screen-count and task
 * tables) both say FIVE — *"Views … TODAY 2 (the board, the refunds queue) …
 * PROPOSED 5"*, *"Tab 2 · 7 → 10"*, *"5 view names across all eleven
 * languages"*, and, in terms, *"**The three report screens stay in Reports
 * (0)**"*. A log entry on p006, dated the SAME DAY, says EIGHT instead — the
 * five below plus Account ledger, By premises and Statements returning from
 * the Reports tab, taking tab 2 from 7 screens to 13.
 *
 * ⚠ **THE PRODUCT OWNER WAS SHOWN BOTH READINGS OF THEIR OWN DOCUMENT AND
 * RULED, verbatim: *"5 is correct"* (2026-09-24).** So p006's eight is
 * superseded, the three report screens are NOT moved, and this list is five.
 * It is written out here rather than inferred so the next reader who lands on
 * p006 finds the answer in the code instead of re-opening the question.
 *
 * ⚠ **THE ORDER IS THE DRAWING'S AND IS NOT ALPHABETICAL.** p033, p034, p036
 * and p038 all draw the strip in exactly this sequence.
 *
 * ⚠ **`services` IS THE LANDING VIEW** — p033's own caption is *"END STATE ·
 * DASHED = NEW · **THE LANDING VIEW**"* and `P2.18` requires that
 * `/finance/revenue` opens on it.
 *
 * ⚠ **THE VALUES ARE THE BLUEPRINT'S OWN, INCLUDING THE TWO UNHYPHENATED
 * ONES.** Each screen entry prints its address: `?view=services`, `?view=aging`,
 * `?view=tieout`, `?view=writeoffs`, `?view=refunds`. `tieout` and `writeoffs`
 * are spelled without a hyphen there while the LABELS carry one, and the two
 * are deliberately allowed to differ — the label is copy in eleven catalogues
 * and the value is a URL that will end up in bookmarks and tickets.
 */
export const REVENUE_AR_VIEWS = [
  "services",
  "aging",
  "tieout",
  "writeoffs",
  "refunds",
] as const;
export type RevenueArView = (typeof REVENUE_AR_VIEWS)[number];

/** An unknown `?view=` falls back to the LANDING view and never 404s — the
 *  same posture `glViewFrom` takes on tab 1, for the same reason: a stale
 *  bookmark should open the screen, not an error page. */
export function revenueArViewFrom(raw: string | null): RevenueArView {
  return (REVENUE_AR_VIEWS as readonly string[]).includes(raw ?? "")
    ? (raw as RevenueArView)
    : "services";
}

/** A COLLECTION-shaped read that answers 404 does not exist on this deployment.
 *  DERIVED from the response, never declared — a constant reading
 *  `REVENUE_AR_API = false` would be a comment claiming a fact about another
 *  file, and would be wrong the day the endpoint landed (hard-won law 1). */
export function readRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

// ── The KPI strip (BR-LED-016 · BR-REP-001) ───────────────────────────────

/**
 * Six tiles: the prototype's four, plus the ruled KPIs that are absent.
 *
 * **Every money tile declares its basis** — `KpiTile`'s money variant makes the
 * field required, so an unlabeled money KPI is not expressible here (BR-REP-001).
 * An absent tile carries no `money`: two of them are not money at all (a ratio
 * and a day count) and the third, Written off YTD, is money the books will not
 * state — and a figure that cannot be stated is rendered by `AbsentFigure` with
 * its reason, never by the money path.
 *
 * ⚠ DEF-151 IS EXACTLY THE ONE CHARACTER THIS FILE'S OWN HEADER WARNS ABOUT.
 * `money()` was `(amount: string) => ({ amount, currency, basis, locale })` — a
 * pass-through with no null branch — and `written_off_ytd` has been served null
 * on every deployment since the endpoint landed. So the null walked through
 * `KpiTile`, through `KPIStrip`, into `MoneyCell`, missed its decimal-string
 * regex and came out of `formatMoney`'s verbatim fallback as the literal text
 * **`null USD`**, on a finance screen, beside five tiles that read *Not
 * available* with a sentence saying why. `money()` now REFUSES a null rather
 * than rendering one: the caller must have branched before it gets here.
 */
export function revenueArKpis(
  report: RevenueArResponse,
  t: Translator,
  locale: string | undefined,
): KpiTile[] {
  const { kpis, currency, basis } = report;
  const money = (amount: string) => ({ amount, currency, basis, locale });
  const collectionGap = gapFor(report.unavailable, GAP_COLLECTION_PCT);
  const dsoGap = gapFor(report.unavailable, GAP_DSO);
  const writtenOffGap = gapFor(report.unavailable, GAP_WRITTEN_OFF_YTD);
  return [
    {
      id: "billed",
      label: t("finance.kpi.billed"),
      money: money(kpis.billed),
      // The prototype's "↑ 8.4% vs Jul" compares against a period this response
      // does not carry. The window itself is the honest detail line.
      detail: t("finance.kpi.billed.detail", {
        from: report.period.start,
        to: report.period.end,
      }),
    },
    {
      id: "collected",
      label: t("finance.kpi.collected"),
      money: money(kpis.collected),
      // BR-REP-009: applied deposits count as collected. Both halves are served
      // and both are shown, formatted through the ONE money path — never summed
      // or re-derived here.
      detail: t("finance.kpi.collected.detail", {
        cash: formatMoney(kpis.collected_from_cash, currency, locale),
        deposits: formatMoney(kpis.collected_from_applied_deposits, currency, locale),
      }),
    },
    {
      id: "collection_pct",
      label: t("finance.kpi.collectionPct"),
      value:
        isFigureAbsent(kpis.collection_pct) ? (
          <AbsentFigure
            label={t("finance.absent")}
            // The rule behind this refusal is BR-REP-009 (the ruled numerator
            // is cash applied to bills IN PERIOD) and the server's own code is
            // `GAP_COLLECTION_PCT` above. NEITHER is passed to the sentence any
            // more: B14 rule 31 keeps a rule number off a utility's screen, and
            // this comment is where the provenance lives now.
            reason={
              collectionGap === null
                ? t("finance.gap.unknown")
                : gapSentence(collectionGap, t)
            }
          />
        ) : (
          t("finance.kpi.pctValue", { value: kpis.collection_pct })
        ),
    },
    {
      id: "still_owed",
      label: t("finance.kpi.stillOwed"),
      money: money(kpis.still_owed),
      detail: t("finance.kpi.stillOwed.detail", { count: kpis.accounts_owing }),
    },
    {
      id: "dso",
      label: t("finance.kpi.dso"),
      value:
        isFigureAbsent(kpis.dso) ? (
          <AbsentFigure
            label={t("finance.absent")}
            // BR-REP-011 owns the DSO formula and its twelve-month
            // denominator; the server's code is `GAP_DSO` above. Both stay
            // here and off the tile (B14 rule 31).
            reason={
              dsoGap === null
                ? t("finance.gap.unknown")
                : gapSentence(dsoGap, t)
            }
          />
        ) : (
          t("finance.kpi.daysValue", { value: kpis.dso })
        ),
    },
    isAmountAbsent(kpis.written_off_ytd)
      ? {
          id: "written_off",
          label: t("finance.kpi.writtenOff"),
          // No `detail`. "Since the start of the fiscal year" describes a window
          // this response could not establish — printing it under an absence
          // would restate the very claim the absence is refusing to make.
          value: (
            <AbsentFigure
              label={t("finance.absent")}
              // BR-TEN-022 — the accounting period is COMPUTED from fiscal
              // settings and this page reads ONE of them, so no year window
              // exists to total. Server code: `GAP_WRITTEN_OFF_YTD` above.
              // Neither id reaches the tile (B14 rule 31).
              reason={
                writtenOffGap === null
                  ? t("finance.gap.unknown")
                  : gapSentence(writtenOffGap, t)
              }
            />
          ),
        }
      : {
          id: "written_off",
          label: t("finance.kpi.writtenOff"),
          money: money(kpis.written_off_ytd),
          // The prototype's "0.4% of revenue" needs a revenue denominator this
          // response does not carry. What IS true is which window it covers.
          detail: t("finance.kpi.writtenOff.detail"),
        },
  ];
}

// ── Revenue by service — 2·1 Services (LE-2's slice) ──────────────────────
//
// ⚠ **THE TWO PERIOD PARAMS ARE THE ENDPOINT'S OWN WORDS (`DEF-LED-6719`).**
// `GET /finance/revenue-ar` takes `from` and `to` and has always REQUIRED both;
// this screen simply never offered a person a way to move them. They are named
// once, here, so the filter that writes them and the request that reads them
// cannot drift apart — the shape that produced `DEF-LED-6717` one panel over.
export const REVENUE_PERIOD_FROM = "from";
export const REVENUE_PERIOD_TO = "to";


/**
 * How the browser narrows and orders the service table (`P2.20`).
 *
 * ⚠ **THE FILTER OPTIONS ARE DERIVED FROM THE ROWS, NOT TYPED OUT.** p033's
 * criteria table names `GET /reference/services` as the Service filter's source
 * and adds *"never a literal array"* — the hazard being hard-won law 12's
 * eleventh service, which exists, is served, and never appears on screen
 * because two files list the ten by hand. Deriving the options from the rows
 * this table is already showing satisfies that in full and costs no second
 * request: a service with no revenue this period is absent from the options
 * because filtering to it would return nothing.
 */
export const SERVICE_REVENUE_SPEC: ClientTableSpec<ServiceRevenueRow> = {
  search: (row) => [row.service_code ?? ""],
  filter: (row, name, value) => (name === "service" ? (row.service_code ?? "") === value : true),
  sortValue: (row, key) => {
    // ⚠ **A BRANCH PER KEY, NOT `row[key]`.** A stringly-typed lookup returns
    // `undefined` for a column nobody mapped and then sorts every row equal —
    // the header cycles, the arrow moves and nothing reorders, which is
    // hard-won law 7's check that cannot fail. `clientPage`'s own header says
    // the same thing, and this is why the accessor is passed in.
    switch (key) {
      case "service":
        return row.service_code ?? null;
      case "usage":
        return Number(row.usage);
      case "base_and_fees":
        return Number(row.base_and_fees);
      case "total_billed":
        return Number(row.total_billed);
      // ⚠ **`tax` AND `collected` ARE ALWAYS NULL ON THE WIRE**, so they sort
      // as absent in both directions rather than as zero. They are still
      // sortable columns: the day the wire serves them, this needs no change.
      case "tax":
        return row.tax === null ? null : Number(row.tax);
      case "collected":
        return row.collected === null ? null : Number(row.collected);
      default:
        return null;
    }
  },
};

/**
 * **2·1 SERVICES — THE LANDING VIEW, ON THE SHARED TABLE (`P2.20`).**
 *
 * Blueprint p033. Its Today row reads *"A panel on the board with no toolbar"*
 * and the task is one sentence: *"Services and Tie-out on the shared table.
 * Both from `GET /finance/revenue-ar`. **Bounded** — at most eleven services
 * and three subledgers — so paging and search stay in the browser."*
 *
 * ⚠ **BOUNDED IS NOT AN `NFR-3` EXEMPTION CLAIMED, IT IS ONE THAT HOLDS.**
 * `clientPage`'s own header is emphatic that it is a STAND-IN for server paging
 * and *"not a way to satisfy NFR-3"*, because a browser handed 40,000 rows has
 * already paid the cost. This table is different in kind and p033 says so in
 * its Table-controls row: *"All six, in the browser — at most eleven rows,
 * **bounded by the service catalogue and not by tenant size**"*. Eleven
 * services is eleven services at 3,000 accounts and at 40,000. `ledger/api.py`
 * agrees in its own words — *"a resource, not a list: its `revenue_by_service`
 * table is bounded by the"* service catalogue. **So there is no backend task
 * owed here, and that is the one thing that distinguishes this from the four
 * reads `DEF-PAY-4221` names.**
 *
 * ⚠ **THE COLUMNS ARE THE ONES THE WIRE SERVES, AND THE DRAWING DRAWS FIVE
 * OTHERS.** p033's FIELDS row reads *"Service · Billed · Collected · Owed ·
 * Collection %"*. Of those five, `GET /finance/revenue-ar` serves TWO —
 * `service_code` and `total_billed`. `collected` is served as `null` on every
 * row for a stated reason (`GAP_SERVICE_COLUMNS`: cash carries no invoice
 * attribution), and per-service **Owed** and **Collection %** are not on the
 * wire at all, for the same reason one step on. So the drawn column set cannot
 * be built today, and building it would mean three columns of invented
 * arithmetic on a finance screen.
 *
 * **`P2.20` is *"onto the shared table"* and this is that and only that:** the
 * toolbar, the search, the filter, the column chooser, the ⇅ headers and the
 * pager arrive; the columns are unchanged, including the two that already
 * render a dash with their reason. **The mismatch is FILED rather than
 * silently built or silently dropped** — see this lane's report.
 */
export function RevenueByServiceTable(props: {
  report: RevenueArResponse;
  t: Translator;
  locale?: string;
  /** Handed over by a caller that owns the request state; absent = held here,
   *  which is what every existing test that mounts this bare relies on. */
  state?: TableRequestState;
  onStateChange?: (next: TableRequestState) => void;
  /**
   * ⚠ **THE PERIOD FILTER (`DEF-LED-6719`).** Product Owner, on deployed
   * v2.351.84: *"also in filter we will need period - start date and end
   * date."* The panel was locked to the tenant's current period, so a finance
   * officer could not ask this screen about any other window.
   *
   * It is OPTIONAL because it is not a client-side cut: the two ends are the
   * `from`/`to` of `GET /finance/revenue-ar`, so only a caller that owns the
   * REQUEST can offer it. Passing the tenant's date format is what declares it
   * — `dateRangeFilter` demands one, so a chip cannot render a date in a format
   * this tenant never chose. Absent, the filter is simply not offered and every
   * existing bare mount is unchanged.
   *
   * ⚠ **IT MOVES THE WHOLE SCREEN'S WINDOW, TILES INCLUDED, AND THAT IS THE
   * POINT.** The tiles state their basis as POSTING DATE and the rows are the
   * same aggregate windowed. A period control that moved only the rows would
   * put the Total and the Billed tile back on two different windows, which is
   * `DEF-LED-6717` returning in a new costume.
   */
  periodFilter?: { dateFormat: RegionalDateFormat };
}) {
  const { report, t } = props;
  const rows = report.revenue_by_service;
  const columnGap = gapFor(report.unavailable, GAP_SERVICE_COLUMNS);
  // BR-LED-001 — a tax line carries no `service` dimension and cash carries no
  // invoice attribution, which is why two of the six columns cannot be filled.
  // Server code: `GAP_SERVICE_COLUMNS` above. B14 rule 31 keeps both out of the
  // sentence a finance officer reads.
  const columnReason =
    columnGap === null
      ? t("finance.gap.unknown")
      : gapSentence(columnGap, t);
  const [ownState, setOwnState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "total_billed",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  const state = props.state ?? ownState;
  const setState = props.onStateChange ?? setOwnState;
  const page = clientPage(rows, state, SERVICE_REVENUE_SPEC);

  const money = (amount: string) => (
    <MoneyCell amount={amount} currency={report.currency} locale={props.locale} />
  );
  const moneyOrDash = (amount: string | null) =>
    isAmountAbsent(amount) ? <Dash /> : money(amount as string);

  const config: TableConfig<ServiceRevenueRow> = {
    screenId: "S36.services",
    getRowId: (row) => `${row.service_id ?? ""}|${row.service_code ?? ""}`,
    searchFields: ["service"],
    searchPlaceholder: "finance.revenue.searchPlaceholder",
    defaultSort: { sort: "total_billed", dir: "desc" },
    filters: [
      {
        name: "service",
        label: t("finance.revenue.col.service"),
        options: serviceFilterOptions(rows, t),
      },
      // `DEF-LED-6719` — start date and end date, in the panel's own filter,
      // through the kit's own two-ended range (B14 rules 43 and 44: this is
      // built once, in `FilterBar`, and every list in the product opens it the
      // same way). The two param names are the endpoint's own words.
      ...(props.periodFilter === undefined
        ? []
        : [
            dateRangeFilter({
              name: "period",
              label: t("finance.revenue.filter.period"),
              from: REVENUE_PERIOD_FROM,
              to: REVENUE_PERIOD_TO,
              dateFormat: props.periodFilter.dateFormat,
            }),
          ]),
    ],
    columns: [
      {
        key: "service",
        label: t("finance.revenue.col.service"),
        sortable: true,
        identity: true,
        cell: (row) =>
          row.service_code === null ? (
            // ⚠ **A DELIBERATE, LABELLED ABSENCE — NOT A LEFTOVER GROUP.**
            // The row is KEPT and labelled, never dropped: a bucket that named
            // no service still holds money, and dropping it would make the
            // table foot to less than the period's revenue.
            //
            // Until `DEF-LED-6718` this row was the ONLY thing the table drew
            // in a quiet month, so it did the right thing for the wrong reason
            // — it was what GROUPING happened to leave behind. Now every active
            // service is drawn beside it and this row means one thing only:
            // **money posted with no service dimension**, which a hand-typed
            // journal entry can be (`P1.16` captures none of the five).
            //
            // ⚠ **WHETHER THAT SHOULD BE ALLOWED AT ALL IS `OQ-LED-12629`,
            // OPEN AND WITH THE PRODUCT OWNER** — must a revenue line carry its
            // dimensions, and should the manual entry REFUSE one that does not?
            // Three options are on the register and none is chosen, so nothing
            // here picks one: the row is reported honestly and no rule about it
            // is implemented. B14 rule 33 keeps the reasoning off the screen —
            // a clerk reads four words, and the *why* lives here.
            <span className="met-muted">{t("finance.revenue.noService")}</span>
          ) : (
            // `DEF-LED-9120` — the service's own word (`Storm water`), never
            // the code (`storm_water`); an unknown tenant code shows as itself.
            serviceLabel(row.service_code, t)
          ),
      },
      {
        key: "usage",
        label: t("finance.revenue.col.usage"),
        sortable: true,
        numeric: true,
        cell: (row) => money(row.usage),
      },
      {
        key: "base_and_fees",
        label: t("finance.revenue.col.base"),
        sortable: true,
        numeric: true,
        cell: (row) => money(row.base_and_fees),
      },
      {
        // Tax and Collected: two of the prototype's six columns, and neither is
        // summable. The header stays so the table matches the design a finance
        // officer was shown; the cell says why it is empty instead of printing
        // a zero under it.
        //
        // ⚠ DEF-176 — THESE TWO CELLS TOOK THE WHOLE ROUTE DOWN. They branched
        // on `row.tax === null`, and `apps/ledger/wire.py` was not sending the
        // key at all, so the value was `undefined` and the test was false.
        // `undefined` reached `MoneyCell`, DEF-151's refusal threw, and React
        // Router replaced the entire Finance screen with `Unexpected
        // Application Error!` — no sidebar, no tabs, no page. Both halves are
        // fixed: the wire now serves `tax: null` / `collected: null`
        // explicitly, and the question asked here is *"did a figure arrive?"*,
        // which is the one `isAmountAbsent` exists to make unambiguous.
        key: "tax",
        label: t("finance.revenue.col.tax"),
        sortable: true,
        numeric: true,
        cell: (row) => moneyOrDash(row.tax),
      },
      {
        key: "total_billed",
        label: t("finance.revenue.col.total"),
        sortable: true,
        numeric: true,
        cell: (row) => money(row.total_billed),
      },
      {
        key: "collected",
        label: t("finance.revenue.col.collected"),
        sortable: true,
        numeric: true,
        cell: (row) => moneyOrDash(row.collected),
      },
    ],
  };

  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.revenue.title")}</h3>
      </div>
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        rows={page.page}
        totalRows={page.total}
        loading={false}
        empty={{
          title: t("finance.revenue.empty"),
          helper: t("finance.revenue.emptyHelper"),
        }}
      />
      {/* ⚠ **THE TOTAL IS A LINE, NOT A `<tfoot>`, AND THE DRAWING DRAWS A ROW.**
          p033 draws a **Total** row inside the table. `DataTable` has no footer
          slot, and adding one is a kit change that reaches ~25 lists and has no
          proof behind it in this lane — so the FIGURE survives where the
          ARRANGEMENT could not. BR-REP-001's basis label travels with it.

          ⚠⚠ **THIS LINE READ `report.kpis.billed` UNTIL 2026-09-25 AND WAS A
          DIFFERENT FIGURE FROM THE ROWS ABOVE IT (`DEF-LED-6717`).** Both are
          correct answers to two different questions. The rows sum movement on
          the tenant's REVENUE accounts; `kpis.billed` sums AR DEBITS from
          invoice-sourced entries. On books written entirely by the bill run the
          two agree to the cent, which is why every test passed over it. They
          part the moment money is posted by hand, and the Product Owner
          photographed a table whose one row read `$50.00` above a Total of
          `$0.00` and a Billed tile of `$0.00`.
          **A table whose rows do not add up to its own total is worse than an
          empty table**, so the Total is now summed FROM THE ROWS — over
          `page.matched`, the whole set the search and the filters kept, not the
          slice on screen. That is CLAUDE.md's `NFR-3` resolution of this exact
          shape: the total and the rows are ONE aggregate over ONE filtered set,
          one of them windowed. `sumAmounts` adds in `BigInt` ten-thousandths,
          because hard rule 2 gives a subtotal no exemption from "never float".
          The Billed TILE is untouched and still says what it always said. */}
      {page.total === 0 ? null : (
        <FactRow
          label={t("finance.revenue.total")}
          value={
            <MoneyCell
              amount={sumAmounts(page.matched.map((row) => row.total_billed))}
              currency={report.currency}
              // BR-REP-001 — still the POSTING basis: every row under it is a
              // sum over POSTED journal lines in the served window, so the
              // label is as true of the sum as it was of the KPI.
              basis={report.basis}
              locale={props.locale}
            />
          }
        />
      )}
      {/* B14 rule 32 — a stated absence is a disclosure CLOSED by default. The
          two columns still show a dash in every row and this line still says in
          words why; it no longer prints a paragraph under a table nobody asked
          it of. `AbsentFigure` is the one renderer for this (financeShared). */}
      <AbsentFigure label={t("finance.absent")} reason={columnReason} />
    </Panel>
  );
}

/**
 * The first day of the tenant's fiscal year, as `GET /finance/revenue-ar`'s
 * `ytd_start` (`DEF-LED-6720`).
 *
 * ⚠ **BR-TEN-022 STORES NO FISCAL YEAR, SO NOBODY CAN LOOK THIS UP — IT IS
 * COMPUTED FROM SETTINGS AND HANDED OVER.** `reporting.revenue_and_ar` takes it
 * as an INPUT and says so, and `api.py` serves `written_off_ytd: null` with its
 * reason attached rather than summing write-offs from the beginning of the
 * books and calling that a year to date. This is the one place the day is
 * worked out, from the two raw fields the Regional read already carries.
 *
 * **The year is chosen by the PERIOD being looked at, not by today.** A fiscal
 * year starting 1 October, read in September 2026, begins on 1 October 2025;
 * read in November 2026, on 1 October 2026. Taking the current calendar year
 * would report an October-to-September utility a year-to-date that starts in
 * the future for three months of every year, and the tile would read 0.00 with
 * nothing to say it was wrong.
 *
 * `null` when the tenant has set no fiscal year, and the tile then renders the
 * server's honest refusal exactly as it did before — an absent SETTING is a
 * different fact from an absent request, and only the second one was the bug.
 */
export function fiscalYearStart(
  regional: { fy_start_month: number | null; fy_start_day: number | null } | null,
  period: { start: string } | null,
): string | null {
  if (regional === null || period === null) {
    return null;
  }
  const { fy_start_month: month, fy_start_day: day } = regional;
  if (month === null || day === null) {
    return null;
  }
  const pad = (value: number) => String(value).padStart(2, "0");
  // The period's own start, as text — never `new Date()`, which would read this
  // in the browser's time zone and can put the answer a day either side of the
  // tenant's (IS-8). The wire's dates are calendar days and are compared as
  // strings, which is exactly what `YYYY-MM-DD` is ordered for.
  const periodYear = Number(period.start.slice(0, 4));
  const candidate = `${periodYear}-${pad(month)}-${pad(day)}`;
  return candidate <= period.start ? candidate : `${periodYear - 1}-${pad(month)}-${pad(day)}`;
}

/**
 * The Service filter's options, taken from the rows on screen.
 *
 * ⚠ **SORTED, DE-DUPLICATED, AND THE UNNAMED BUCKET IS EXCLUDED.** A row whose
 * `service_code` is null is the posting bucket that named no service; it is
 * kept in the TABLE (see the identity cell) because it holds money, and it is
 * not offered as a FILTER because *"filter to the one with no name"* is not a
 * question a finance officer asks.
 */
export function serviceFilterOptions(
  rows: readonly ServiceRevenueRow[],
  t: Translator,
): { value: string; label: string }[] {
  const codes = new Set<string>();
  for (const row of rows) {
    if (row.service_code !== null && row.service_code !== "") {
      codes.add(row.service_code);
    }
  }
  // `DEF-LED-9120` — the VALUE stays the code (it is what the filter matches
  // on); the LABEL is the word a finance officer reads. This parameter was
  // handed the translator from the day it was written and never used it.
  return [...codes].sort().map((code) => ({ value: code, label: serviceLabel(code, t) }));
}

// ── "Who owes you" — 2·2 Aging (`P2.21`) ──────────────────────────────────
//
// ⛔ **`AgingPanel` IS DELETED AND ITS VIEW IS `AgingView.tsx`.** It was a
// five-row fact list that rendered a STATED ABSENCE, because
// `GET /finance/revenue-ar` serves `aging: null` with its reason — a journal
// line carries no due date, so the BOOKS cannot split the receivable. That was
// honest and it was never the screen: the split comes from the `ar_aging`
// REPORT, which pages, filters and sorts in SQL since `DEF-REP-6607` was
// answered, and p034 rules *"Build the view over the report; do not copy the
// report into Finance."*
//
// It is DELETED rather than left unmounted: a component nothing renders is
// dead UI, which is hard-won law 2 in the direction `G13` can see.
// `GET /finance/revenue-ar` still serves `aging` and its gap — the STILL OWED
// tile is derived from the same response — and nothing about that read moved.

// ── "Adjustments & credits" (the prototype's second right-hand panel) ─────

export function AdjustmentsPanelView(props: {
  report: RevenueArResponse;
  t: Translator;
  locale?: string;
}) {
  const { report, t } = props;
  const panel = report.adjustments;
  const lateGap = gapFor(panel.unavailable, GAP_LATE_FEES);
  const pendingGap = gapFor(panel.unavailable, GAP_PENDING_APPROVAL);
  const money = (amount: string) => (
    <MoneyCell amount={amount} currency={report.currency} locale={props.locale} />
  );
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.adjustments.title")}</h3>
      </div>
      <FactRow label={t("finance.adjustments.credits")} value={money(panel.credits_issued)} />
      <FactRow label={t("finance.adjustments.debits")} value={money(panel.debits_posted)} />
      <FactRow
        label={t("finance.adjustments.lateFees")}
        value={
          isAmountAbsent(panel.late_fees_applied) ? (
            <AbsentFigure
              label={t("finance.absent")}
              // BR-LED-016 — this product reads the chart by DESIGNATION and
              // never by account number, and nothing designates the late-fee
              // account. Server code: `GAP_LATE_FEES` above; B14 rule 31 keeps
              // both off the row.
              reason={
                lateGap === null
                  ? t("finance.gap.unknown")
                  : gapSentence(lateGap, t)
              }
            />
          ) : (
            money(panel.late_fees_applied)
          )
        }
      />
      <FactRow label={t("finance.adjustments.net")} value={money(panel.net)} strong />
      {/* BR-SHL-025: the prototype's "Review 8 pending →" renders DISABLED with
          its reason rather than as a live button onto nothing, and the COUNT is
          absent rather than invented — an adjustment awaiting approval has not
          been posted, so the books cannot count it. */}
      {/* B14 rule 32 — closed by default, and the two lines say DIFFERENT
          things on purpose (rule 32's third clause: a row never repeats what
          its own control offers). This one is the fact about the books; the
          button's own reason is what the CONTROL cannot do.
          BR-REP-002 is the rule; the server's code is `GAP_PENDING_APPROVAL`
          above. Neither reaches the reader (B14 rule 31). */}
      <AbsentFigure
        label={t("finance.absent")}
        reason={
          pendingGap === null ? t("finance.gap.unknown") : gapSentence(pendingGap, t)
        }
      />
      <GuardedButton
        label={t("finance.adjustments.review")}
        reason={t("finance.adjustments.reviewUnavailable")}
        onClick={() => undefined}
      />
    </Panel>
  );
}

// ── Cash position (PO ruling 2026-08-11, OQ-143) ──────────────────────────

export function CashPanel(props: { report: RevenueArResponse; t: Translator; locale?: string }) {
  const { report, t } = props;
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.cash.title")}</h3>
      </div>
      <FactRow
        label={t("finance.cash.realised")}
        value={
          <MoneyCell
            amount={report.cash.realised}
            currency={report.currency}
            // CLEARING, not posting — and the label says so on the figure.
            basis={report.cash.basis}
            locale={props.locale}
          />
        }
      />
      <FactRow
        label={t("finance.cash.undeposited")}
        value={
          <MoneyCell
            amount={report.cash.undeposited}
            currency={report.currency}
            basis={report.cash.basis}
            locale={props.locale}
          />
        }
      />
      {/* There is deliberately no total row. Adding these two would tell a
          utility it has money in the bank that is sitting in a drawer. */}
      <p className="fin-absent-reason" role="note">
        {t("finance.cash.note")}
      </p>
    </Panel>
  );
}

// ── The write-off approval queue (BR-PAY-020 · DEF-100) ───────────────────

export const writeOffQueueQueryKey = ["finance", "write-offs", "requested"] as const;

/**
 * S36's half of BR-PAY-020: **approved + reported in FINANCE**.
 *
 * ⚠ **THIS PANEL IS THE FIX FOR DEF-100 AND THE REASON IT MATTERS IS NOT THE
 * LIST.** The backend served `/write-offs` POST-only, so nothing in the product
 * could answer *"what is awaiting my approval?"* — and a browser could only
 * ever hold the id it had just created. The Approve button therefore lived on
 * S34 beside the request, which meant the person who asked for a write-off
 * approved it in the same breath. Moving the control here is what makes the
 * two-screen split real.
 *
 * **It is a SCREEN split, not a new authorisation rule.** BR-PAY-037 is
 * CONFIRMED: the same user holding the approver role MAY initiate AND approve
 * in v1, both acts recorded distinctly, with enforced separation-of-duties in
 * v2. Nothing here refuses a self-approval and nothing should — the server's
 * `@require_role(SYSTEM_ADMIN)` is the authorisation (BR-SHL-025) and a client
 * check would be a second copy of it, free to drift.
 *
 * ⚠ **RE-AFFIRMED BY THE PO ON 2026-09-23 AGAINST A DRAWING THAT SAID THE
 * OPPOSITE — `OQ-226` CLOSED, option (a).** Payments blueprint **p086**
 * (screen 7·3b) draws *"A second person decides."*, *"You cannot approve one
 * you asked for."* and a third row reading *"Yours — someone else decides"* in
 * place of the buttons. **PO, verbatim:** *"allow it - we are dealing with
 * smaller utilites they dont have too many people"* — a utility of 10–20 staff
 * may not HAVE a second approver, and a control that demands one stops the
 * work rather than protecting it. **So all three drawn elements are SUPERSEDED,
 * `BR-PAY-037` is `CONFIRMED-AS-RE-AFFIRMED`, and no person-level check is
 * added here or anywhere for v1.** The PDF cannot carry its own correction,
 * which is why it is written into this docstring.
 *
 * Every amount renders through `MoneyCell` with the ROW's own currency
 * (CLAUDE.md rule 2 / DEF-099). A **948.20** request shows as waiting and
 * `posted_to_ledger` false until it is approved — US-PAY-012 TC-1's control,
 * said on the screen rather than assumed.
 */
export function WriteOffQueuePanel(props: {
  t: Translator;
  locale?: string;
  client: ApiClient;
  /** The business day the approval is dated — BR-TEN-043, never a clock. */
  asOf: string;
}) {
  const { t } = props;
  const queryClient = useQueryClient();
  const [approvals, setApprovals] = useState<Record<string, WriteOffApproved>>({});
  const queue = useQuery({
    queryKey: writeOffQueueQueryKey,
    // ⚠ **THE WIDER READ, NOT THE NARROWER ONE.** `endpoints.getWriteOffs`
    // types `WriteOffQueueRow`; `bankRecEndpoints.getWriteOffApprovalQueue`
    // types `WriteOffApprovalRow`, which is the SAME server rows plus the two
    // NAMES the approval screen needs — `requested_by_name` and
    // `approved_by_name`. The `<ul>` this panel used to draw could not show
    // who had asked, so it did not need them; the table the drawing draws puts
    // **ASKED BY** in its fourth column, and a queue that cannot say who asked
    // is a two-person control with one name in it.
    queryFn: () => getWriteOffApprovalQueue({ status: "requested" }, props.client),
    // A missing route or a refused role is not a flaky network.
    retry: false,
  });

  const approve = useMutation({
    mutationFn: (writeOffId: string) =>
      approveWriteOff(
        writeOffId,
        { approved_on: props.asOf, posted_at: props.asOf },
        props.client,
      ),
    onSuccess: (result) => {
      setApprovals((current) => ({ ...current, [result.id]: result }));
      void queryClient.invalidateQueries({ queryKey: writeOffQueueQueryKey });
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
    },
  });

  if (queue.isError) {
    return (
      <AbsentPanel
        title={t("finance.writeOffs.title")}
        reason={apiErrorText(queue.error, props.t)}
      />
    );
  }
  // ⚠ **IT RETURNS THE ENVELOPE SINCE 2026-09-24 (`P2.19`).** This comment used
  // to warn that `getWriteOffApprovalQueue` returned the ROWS while
  // `endpoints.getWriteOffs` returned `{rows}`, and that `?.rows` on an array
  // read as `undefined` rather than failing loudly. Both wrappers follow the
  // envelope now, and the body carries `pending` beside the rows so the view
  // label can state the true total.
  const rows = queue.data?.rows ?? [];
  const decided = Object.values(approvals);
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.writeOffs.title")}</h3>
      </div>
      {/* ══════════════════════════════════════════════════════════════════
          ⚠ **SCREEN 7·3b — `CR-138-BRC07` `P4.9`, AND IT CLOSES A DEAD-UI
          DEFECT ON THE WAY (`DEF-PAY-6265`).**

          This was a `<ul>` of rows with one control on each. The blueprint
          draws a TABLE at p086 — ACCOUNT · CUSTOMER · REASON · ASKED BY ·
          ASKED ON · AMOUNT, with ⇅ on four of them, a search box, `+ Filter`,
          `▦ Columns` and a `Showing 1–3 of 3` footer.

          ⚠ **AND THAT TABLE ALREADY EXISTED AND NOTHING RENDERED IT.**
          `features/payments/WriteOffQueuePage.tsx` is **670 lines**, declares
          `WriteOffQueueTable` with **all three** decisions — Approve, Reject
          and Reverse, each disabled WITH its reason — and the page is
          **registered on no route**: a `grep` for it outside its own file
          found one importer, its test. Hard-won law 2, dead UI, on a money
          path, for weeks.

          So the panel renders the COMPONENT rather than a fourth hand-rolled
          list (B14 rule 43), and `P4.9`'s toolbar and paging arrive with it —
          for every caller of that component at once rather than for this one.
          The `<ul>` offered ONE act; this offers the three the rules already
          permit. ══════════════════════════════════════════════════════════ */}
      {queue.isPending ? (
        <LoadingSkeleton variant="kpi" />
      ) : (
        <WriteOffQueueTable
          rows={rows}
          // ⚠ BR-PAY-037 is CONFIRMED and was RE-AFFIRMED by the PO on
          // 2026-09-23 (`OQ-226` closed, option (a)): the same user holding
          // the approver role MAY initiate AND approve in v1, both acts
          // recorded distinctly. The table draws *"your request"* beside a row
          // a clerk raised — a WARNING that makes it deliberate, never a
          // block, and now the ratified shape. `null` here means
          // this panel does not yet know who is looking; the server's
          // `@require_role(SYSTEM_ADMIN)` is the authorisation either way.
          currentUserId={null}
          t={t}
          locale={props.locale}
          onDecide={(row, kind) => {
            // Only APPROVE has a mutation on this panel today. Reject and
            // reverse render disabled WITH their reason through
            // `decisionBlockedReason`, which is the component's own contract —
            // so nothing here silently swallows a click.
            if (kind === "approve") {
              approve.mutate(row.id);
            }
          }}
        />
      )}
      {/* WHAT AN APPROVAL DID, said as facts rather than as a toast that
          disappears: whether it reached the books, and whether it closed a
          payment plan (PO 2026-08-12, OQ-171). A finance officer who thinks a
          customer is still on a plan would chase the wrong thing. */}
      {decided.map((result) => (
        <div key={result.id} role="status">
          <FactRow
            label={t("payments.writeOff.status.approved")}
            value={t("payments.writeOff.approvedToast")}
          />
          <p className="fin-absent-reason">
            {result.posted_to_ledger
              ? t("payments.writeOff.posted")
              : t("payments.writeOff.notPosted")}
          </p>
          <p className="fin-absent-reason">
            {result.plan_closed === null
              ? t("payments.writeOff.noPlanToClose")
              : t("payments.writeOff.planClosed")}
          </p>
        </div>
      ))}
      {approve.isError && (
        <div role="alert">
          <FactRow
            label={t("payments.writeOff.approveFailedTitle")}
            value={apiErrorText(approve.error, props.t)}
          />
        </div>
      )}
    </Panel>
  );
}

// ── The tie-out panel (BR-LED-007 · US-LED-004 — RELEASE BLOCKER) ─────────

export const tieOutsQueryKey = (period: string) => ["finance", "tie-outs", period] as const;

/** One row's verdict as a CSS class. Three states, three classes — never a
 *  boolean, because "nobody could compute this" is not a shade of green. */
function tieOutClass(state: TieOutState): string {
  if (state === "agreed") return "fin-tieout-agreed";
  if (state === "drifting") return "fin-tieout-drifting";
  return "fin-tieout-unverifiable";
}

/** One tie-out figure, or its honest absence.
 *
 *  `null` reaches here for a side the server could not read, and it renders as
 *  an ABSENCE with a reason — never `$0.00`, which in this panel would be the
 *  claim "the register holds nothing" over a book that might hold thousands.
 *  The currency is required with the amount (rule 2's pair), so a figure whose
 *  CHAR(3) is missing is absent too rather than printed bare. */
function TieOutFigure(props: {
  amount: string | null;
  currency: string | null;
  basis: string;
  t: Translator;
  locale?: string;
}) {
  // `== null` and NOT `=== null`, deliberately — it catches `undefined` too.
  // DEF-176 is what the strict comparison costs: MoneyCell RAISES on a nullish
  // amount (rightly — DEF-151 shipped a tile reading "null USD"), and an
  // uncaught raise in one cell takes the WHOLE Finance screen down with an
  // error boundary. A key the server omits arrives as `undefined`, which
  // `=== null` waves through and `formatMoney` then throws on.
  if (props.amount == null || props.currency == null) {
    return (
      <AbsentFigure
        label={props.t("finance.absent")}
        reason={props.t("finance.tieOut.sideUnreadable")}
      />
    );
  }
  // ⚠ **THE `basis` PROP WAS PASSED HERE UNTIL 2026-09-25, AND EVERY MONEY
  // CELL IN THE TIE-OUT PRINTED *POSTING DATE* BESIDE ITS FIGURE — FIFTEEN
  // TIMES ON ONE SCREEN (`DEF-LED-6620`).**
  //
  // **BR-REP-001 IS NOT BEING REVERSED — IT IS BEING READ.** The signed rule,
  // verbatim: *"every KPI/report HEADER labels its basis — no unlabeled money
  // number anywhere"*. It asks for a label on the HEADER, once. This passed it
  // to every cell, so one report-level fact was repeated once per figure, and
  // `tie_out.BASIS` is a module CONSTANT (`BASIS_POSTING`) — the same value on
  // every row of every tenant, so there was never a per-row fact to tell.
  //
  // The Finance blueprint p036 draws this table with clean figures and puts
  // the basis caption on the KPI strip above it, which is the same reading. The
  // strip is unchanged and still labels every money tile (`revenueArKpis`
  // makes it un-omittable), so no money number on this screen is unlabelled.
  //
  // It was four figures in a plain two-column panel when it was written and is
  // four columns of a real table now, which is how a defensible choice became
  // fifteen repetitions without anyone changing it (`DEF-LED-6620`'s own
  // escape reason). `props.basis` is still taken and still says which basis
  // the row is on, for a caller that wants it.
  return <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />;
}

/**
 * How the browser narrows and orders the tie-out (`P2.20`). Three rows, and the
 * toolbar is there anyway — p037 gives the reason in its own box: *"Every list
 * in the product carries the same six controls, so a clerk who learns them once
 * never finds them missing. **Not because three rows need filtering.**"*
 */
export const TIE_OUT_SPEC: ClientTableSpec<TieOutsResponse["rows"][number]> = {
  // p037's Search criterion: *subledger name*. The CODE is deliberately not a
  // haystack — B14 rule 31 keeps it off the screen, and a search that matches
  // text nobody can see finds rows for reasons the clerk cannot explain.
  search: (row) => [row.subledger],
  filter: (row, name, value) => (name === "state" ? row.state === value : true),
  sortValue: (row, key) => {
    switch (key) {
      case "subledger":
        return row.subledger;
      case "register":
        return row.register === null ? null : Number(row.register);
      case "gl":
        return row.gl === null ? null : Number(row.gl);
      case "drift":
        return row.drift === null ? null : Number(row.drift);
      case "state":
        return row.state;
      default:
        return null;
    }
  },
};

/**
 * BR-LED-007's three comparisons, side by side, with the drift red flag.
 *
 * ⚠ **THIS PANEL USED TO SAY IT COULD NOT BE COMPUTED.** It rendered the AR
 * control total and a sentence explaining that nothing had compared it against
 * anything, because US-LED-004 was unbuilt — and its own comment said why a
 * green badge would have been the worst possible lie in the product: this is
 * the one control that catches a posting-service bypass. `GET /finance/tie-outs`
 * exists now, so the panel states the comparison instead of apologising for it.
 *
 * **What a red row must show, and this is the whole design brief:** BOTH
 * figures, their currency, the delta, and the name of the subledger that
 * disagrees. A bare "tie-out failed" tells a finance officer nothing they can
 * act on; "the books say $0.00, the customer register says $153.50, difference
 * $153.50" tells them exactly where to look.
 *
 * **A null figure renders as an absence, never as 0.00.** The server sends
 * `null` for a side it could not read, and `$0.00` in that slot would be a
 * claim about a register nobody managed to open.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * `P2.20` — ONTO THE SHARED TABLE, AND THE COLUMNS MOVED WITH IT
 * ══════════════════════════════════════════════════════════════════════════
 * Blueprint p036 draws the columns **SUBLEDGER · REGISTER · GENERAL LEDGER ·
 * DIFFERENCE · STATE** and p037's FIELDS row repeats them in that order. This
 * panel drew *Subledger · General ledger · Register · Difference* with the
 * state as a second line inside the subledger cell. Two changes, both the
 * drawing's (B14 rule 44 — the drawing says WHAT is on the screen and how it is
 * arranged):
 *
 *   · **Register now precedes General ledger.** The drawn order reads as the
 *     question actually asked — *what does the register say, and do the books
 *     agree?*
 *   · **State is its own column.** It was a `<span>` under the subledger name,
 *     which made it invisible to the ⇅ header and to the `+ Filter` panel the
 *     shared table brings. p037's criteria table declares `f.state` with values
 *     *Agrees · Differs · Not checked*, and a filter over a value that is not a
 *     column is not expressible.
 *
 * ⚠ **THE PER-ROW COLOUR CLASS SURVIVES THE MOVE.** `tieOutClass` put
 * `fin-tieout-drifting` on the `<tr>`; `DataTable` owns its own rows, so the
 * verdict now travels on the STATE CELL instead. That is not a downgrade — the
 * state was already spelled out in words beside the name precisely so the row
 * is readable without colour, and it still is. **A red flag nobody can see is
 * not a flag**, and that sentence is why the words, not the colour, were the
 * load-bearing half all along.
 */
export function TieOutPanel(props: {
  report: TieOutsResponse;
  t: Translator;
  locale?: string;
  /** Handed over by a caller that owns the request state; absent = held here,
   *  so every existing test that mounts this bare is unaffected. */
  state?: TableRequestState;
  onStateChange?: (next: TableRequestState) => void;
}) {
  const { report, t } = props;
  const [ownState, setOwnState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "subledger",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  const state = props.state ?? ownState;
  const setState = props.onStateChange ?? setOwnState;
  const page = clientPage(report.rows, state, TIE_OUT_SPEC);

  const figure = (row: TieOutsResponse["rows"][number], amount: string | null) => (
    <TieOutFigure
      amount={amount}
      currency={row.currency}
      basis={row.basis}
      t={t}
      locale={props.locale}
    />
  );

  const config: TableConfig<TieOutsResponse["rows"][number]> = {
    screenId: "S36.tieout",
    getRowId: (row) => row.subledger,
    searchFields: ["subledger"],
    searchPlaceholder: "finance.tieOut.searchPlaceholder",
    defaultSort: { sort: "subledger", dir: "asc" },
    filters: [
      {
        name: "state",
        label: t("finance.tieOut.col.state"),
        // p037's three values. NOT a literal typed out here: `TieOutState` is
        // the wire's own union and these are its members, so a fourth state on
        // the server is a typecheck failure here rather than a filter that
        // silently cannot reach the new rows.
        options: (["agreed", "drifting", "unverifiable"] satisfies TieOutState[]).map(
          (value) => ({ value, label: t(`finance.tieOut.state.${value}`) }),
        ),
      },
    ],
    columns: [
      {
        key: "subledger",
        label: t("finance.tieOut.col.subledger"),
        sortable: true,
        identity: true,
        cell: (row) => t(`finance.tieOut.subledger.${row.subledger}`),
      },
      {
        key: "register",
        label: t("finance.tieOut.col.register"),
        sortable: true,
        numeric: true,
        cell: (row) => figure(row, row.register),
      },
      {
        key: "gl",
        label: t("finance.tieOut.col.gl"),
        sortable: true,
        numeric: true,
        cell: (row) => figure(row, row.gl),
      },
      {
        key: "drift",
        label: t("finance.tieOut.col.drift"),
        sortable: true,
        numeric: true,
        cell: (row) =>
          isAmountAbsent(row.drift) ? (
            // No delta is computed against an absence — a subtraction one side
            // of which is unknown is a fabricated number wearing a precise
            // one's clothes.
            <Dash />
          ) : (
            figure(row, row.drift)
          ),
      },
      {
        key: "state",
        label: t("finance.tieOut.col.state"),
        sortable: true,
        // Three states, three classes — never a boolean, because "nobody could
        // compute this" is not a shade of green. `DEF-LED-6524` is the shape
        // this avoids one report along: `balanced` has three values and a
        // client that read it as a boolean accused the books of not footing.
        cell: (row) => (
          <span className={`fin-tieout-state ${tieOutClass(row.state)}`}>
            {t(`finance.tieOut.state.${row.state}`)}
          </span>
        ),
      },
    ],
  };

  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.tieOut.title")}</h3>
        {report.release_blocked ? (
          <span className="fin-tieout-blocker" role="alert">
            {t("finance.tieOut.releaseBlocked")}
          </span>
        ) : (
          <span className="fin-tieout-ok">{t("finance.tieOut.allAgree")}</span>
        )}
      </div>
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        rows={page.page}
        totalRows={page.total}
        loading={false}
        empty={{
          title: t("finance.tieOut.empty"),
          helper: t("finance.tieOut.emptyHelper"),
        }}
      />
      {/* Every non-green row says what the server thinks happened. These are
          the server's own sentences (BR-LED-007's causes), not copy written
          here — a rule quoted into a UI string is a rule that drifts.

          ⚠ **DRAWN FROM THE WHOLE REPORT AND NOT FROM THE PAGE.** A cause that
          vanishes because a clerk typed into the search box is a cause nobody
          reads, and this is the tie-out — the one panel where a filter hiding a
          disagreement is the worst outcome available. Same reason the blocker
          badge above reads `report.release_blocked` rather than the page's. */}
      {report.rows
        .filter((row) => row.causes.length > 0)
        .map((row) => (
          <p key={row.subledger} className="fin-absent-reason" role="note">
            <strong>{t(`finance.tieOut.subledger.${row.subledger}`)}</strong>{" "}
            {row.causes.map((cause) => gapSentence(cause, t)).join(" ")}
          </p>
        ))}
      {report.release_blocked ? (
        // US-LED-004 TC-5 — there is no dismiss control here and there must
        // never be one. Drift clears when the explaining entry posts through
        // the service, and the panel says so instead of offering a button.
        //
        // ⚠ **NINETEEN WORDS UNTIL 2026-09-25 (`DEF-LED-6603`).** It read
        // *"There is no way to dismiss this. It clears when the entry that
        // explains the difference is posted."* — two sentences, every word of
        // it RATIONALE, on a note a clerk cannot dismiss and therefore reads
        // every single time. B14 rule 33 caps a FACT at six words.
        //
        // **THE NEW WORDS ARE NOT THIS LANE'S.** The Finance blueprint p036
        // draws this note and names its length in the same breath — *"The
        // undismissable note · **three words**; it clears when the entry that
        // explains the difference posts"* — and the drawn screen itself reads
        // **"Clears when explained."** That is what the catalogue now holds, in
        // all eleven languages.
        <p className="fin-absent-reason" role="note">
          {t("finance.tieOut.noDismiss")}
        </p>
      ) : null}
    </Panel>
  );
}

/** The same panel, fetching its own row. Split from `TieOutPanel` so the
 *  rendering can be tested against a fixture in the same style as every other
 *  panel on this screen — and so the release blocker is exercised by a test
 *  that does not need a live server to go red. */
export function TieOutPanelView(props: {
  client?: ApiClient;
  period: CurrentPeriod;
  t: Translator;
  locale?: string;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const query = useQuery({
    queryKey: tieOutsQueryKey(`${props.period.start}|${props.period.end}`),
    queryFn: () => getTieOuts({ from: props.period.start, to: props.period.end }, client),
    // A missing route or a refused role is not a flaky network.
    retry: false,
  });

  if (query.isError) {
    // The panel that CANNOT be read says so — it never falls back to the old
    // "here is the control total, nothing has compared it" reassurance, which
    // is the shape this whole story replaced.
    return <AbsentPanel title={t("finance.tieOut.title")} reason={apiErrorText(query.error, t)} />;
  }
  if (query.data === undefined) {
    return <LoadingSkeleton variant="table" />;
  }
  return <TieOutPanel report={query.data} t={t} locale={props.locale} />;
}

// ── The screen ────────────────────────────────────────────────────────────

export interface RevenueArPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /** The tenant's number-format locale (IS-8). Arrives with US-SHL-013's
   *  formatting service; passed through to every MoneyCell meanwhile. */
  locale?: string;
}

export function RevenueArPage(props: RevenueArPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const { timeZone, dateFormat } = useRegional(props);

  // ⛔ **THIS READ `financeTabFrom(useParams().tab)` AND THAT PARAM HAS NOT
  // EXISTED SINCE CR-060 T10 (`DEF-LED-4638`).** Until T10 the route was
  // `/finance/:tab` and EVERY tab rendered this component, so the strip's
  // selection came from the URL and the four tabs with no screen fell to an
  // `ArrivesWith` panel below. T10 gave all six tabs a screen of their own and
  // gave this one the STATIC path `/finance/revenue` — at which point there is
  // no `:tab` to read, `financeTabFrom(undefined)` returns its documented
  // fallback `gl`, and the consequences were both invisible to every check
  // this repo has: the strip highlighted **General ledger** while rendering
  // Revenue & AR, and `active !== FINANCE_TAB_REVENUE` was permanently TRUE,
  // so the whole of S36 — the KPI strip, Revenue by service, the aging panel,
  // the write-off and refund queues, the tie-out — was replaced by an
  // arrives-with panel headed *General ledger* whose message was the raw key
  // `finance.arrives.gl`. `tsc`, eslint and every suite were green over it,
  // because no test mounted this screen at its own address.
  //
  // **This component IS the Revenue & AR tab, so it says so as a fact rather
  // than deriving it from a URL it no longer varies with.** The arrives-with
  // branch is gone with it: all six tabs have a screen, so a Finance tab that
  // "arrives with its own story" is a state the product left behind — which is
  // why no `finance.arrives.*` copy was written to replace it. A sentence
  // there would have made a dead screen look deliberate.
  const active = FINANCE_TAB_REVENUE;
  const cell = useAccessCell(FINANCE_PERMISSION, client);

  // ── `P2.18` — which of the five views is on screen ──────────────────────
  //
  // `?view=` is URL STATE and not component state, so a view is linkable into a
  // ticket and a browser Back leaves it — the same posture tab 1 takes
  // (BR-SHL-011). An unknown value opens the landing view rather than an error.
  const [searchParams, setSearchParams] = useSearchParams();
  const view = revenueArViewFrom(searchParams.get("view"));

  // ── The two pending counts that ride in the labels ──────────────────────
  //
  // ⚠ **FETCHED ON EVERY VIEW, DELIBERATELY.** The blueprint draws the counts
  // on all five drawings (p033, p034, p036, p038), and p038 says why in terms:
  // *"`Write-offs · 2` states the true total on every page, so paging can no
  // longer hide anything."* A count that appears only once you are already
  // looking at the queue answers a question nobody still has.
  //
  // ⚠ **THE KEYS ARE THE PANELS' OWN, WHICH IS WHAT MAKES THIS FREE.** Both
  // are the exact `queryKey`/`queryFn` pairs `WriteOffQueuePanel` and
  // `RefundsQueuePanel` already use, so react-query serves one request between
  // them and approving a row invalidates the badge in the same breath as the
  // list. A second key would be a second copy of the queue, free to disagree
  // with the first about what is waiting.
  //
  // ⚠ **`rows.length` OF AN UNPAGINATED READ IS THE WHOLE POPULATION TODAY, AND
  // THAT IS THE HALF `P2.19` HAS TO KEEP TRUE.** `GET /write-offs` and
  // `GET /refunds` are unpaginated, so counting what arrived counts everything
  // that is pending. The moment either grows a page parameter this becomes the
  // lie the badge exists to end — which is exactly why `P2.19`'s server half is
  // *"a pending count returned beside the page"* and not a client count.
  const writeOffCount = useQuery({
    queryKey: writeOffQueueQueryKey,
    queryFn: () => getWriteOffApprovalQueue({ status: "requested" }, client),
    retry: false,
  });
  const refundCount = useQuery({
    queryKey: refundsQueuePanelQueryKey,
    queryFn: () => getRefunds({ status: "requested" }, client),
    retry: false,
  });

  // BR-TEN-022: the accounting period is COMPUTED from the tenant's fiscal
  // settings and never stored. `GET /settings/regional` serves it; this screen
  // does not compute a month from the browser's clock, because a report headed
  // "August" that is not the tenant's August is worse than one that will not run.
  //
  // ⚠ **THIS IS ONE OF EXACTLY TWO SCREENS LEFT ON THE ADMIN-ONLY READ, AND IT
  // IS A STATED HOLD RATHER THAN AN OVERSIGHT (`DEF-SHL-4283`, 2026-09-06).**
  // Seven screens moved to `GET /shell/display` that day because a Billing
  // Clerk reaches them and `GET /settings/regional` answers a clerk `403`.
  // This screen (S36 Revenue & AR) and the `BadDebtPanel` it mounts stay,
  // because between them they need two things `/shell/display` deliberately
  // does not carry — `current_period.close_by` (the hand-off deadline, which is
  // `close_day` in another shape) and `fy_start_month` / `fy_start_day` (raw
  // calendar configuration). **Both are gated on A4's `finance_reconcile_export`
  // cell, which is `{System Admin, Executive}` — exactly the two roles
  // `SettingsReadAnyWriteSystemAdmin` serves** — so no role that can open this
  // screen is refused this read.
  // **THE HOLD HAS AN EXPIRY TEST**: `src/api/adminOnlyReads.test.ts` fails the
  // day a third file joins the allow-list, and fails the day `BadDebtPanel` is
  // mounted anywhere but here. Do not widen it by hand; move the screen.
  const regionalQuery = useQuery({
    queryKey: queryKeys.regionalSettings,
    queryFn: () => getRegionalSettings(client),
    retry: false,
  });
  const period: CurrentPeriod | null = regionalQuery.data?.current_period ?? null;

  // ── The Services window (`DEF-LED-6719`) ─────────────────────────────
  // The Revenue-by-service panel owns its table state HERE rather than inside
  // the component, because two of its filter values are the REQUEST's `from`
  // and `to` and only the page can issue a request. The tenant's current period
  // is the default and remains what the screen opens on; a person who sets
  // either end moves the whole screen — tiles and rows together, one window,
  // one basis (see the component's `periodFilter` note).
  const [servicesState, setServicesState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "total_billed",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  const chosenFrom = servicesState.filters[REVENUE_PERIOD_FROM] ?? "";
  const chosenTo = servicesState.filters[REVENUE_PERIOD_TO] ?? "";
  // ⚠ BOTH ENDS OR NEITHER. `GET /finance/revenue-ar` refuses a half window on
  // purpose — a KPI strip over an unstated bound is BR-REP-001's whole subject
  // — so a half-typed range keeps showing the period it was showing, and the
  // one end already typed stays in the box. Requesting on a half window would
  // trade a readable screen for an error while somebody is still typing.
  const windowFrom = chosenFrom !== "" && chosenTo !== "" ? chosenFrom : period?.start ?? "";
  const windowTo = chosenFrom !== "" && chosenTo !== "" ? chosenTo : period?.end ?? "";

  // ⚠ **`ytd_start` (`DEF-LED-6720`) — THE *WRITTEN OFF YTD* TILE READ "NOT
  // AVAILABLE" BECAUSE THIS CLIENT NEVER ASKED FOR IT.**
  // `apps/ledger/api.py` states in its own docstring that *"the screen passes
  // the day it reads off S8's Regional tab and the KPI fills in"*. It did not,
  // and never had: the request carried `from` and `to` only, so `wire.py`
  // attached `written_off_ytd_window_unstated` and served `null` — a correct
  // refusal for a window nobody stated. That is hard-won law 1 exactly: a
  // comment claiming a guarantee is not the guarantee, and every reader who
  // checked stopped at the docstring. The fiscal year's first day is already on
  // this very response (`fy_start_month` / `fy_start_day`), which is why the
  // Bad debt panel below could show write-offs while the tile above said the
  // figure was unavailable.
  const ytdStart = fiscalYearStart(regionalQuery.data ?? null, period);

  const reportQuery = useQuery({
    queryKey: revenueArQueryKey(`${windowFrom}|${windowTo}|${ytdStart ?? ""}`),
    queryFn: () =>
      getRevenueAr(
        windowFrom === ""
          ? {}
          : {
              from: windowFrom,
              to: windowTo,
              ...(ytdStart === null ? {} : { ytd_start: ytdStart }),
            },
        client,
      ),
    // A missing route is not a flaky network: retrying a 404 three times only
    // delays the honest answer.
    retry: false,
    enabled: windowFrom !== "",
  });

  // ── 2·2 Aging (`P2.21`) ──────────────────────────────────────────────
  // ⚠ **THE VIEW IS BUILT OVER THE `ar_aging` REPORT AND COPIES NOTHING INTO
  // FINANCE** — p034's box, verbatim. The report pages, filters and sorts in
  // SQL since `DEF-REP-6607` was answered, so everything below is state and
  // nothing below is arithmetic.
  //
  // The request state rides in the SAME query string as `?view=`, so a link to
  // a filtered ageing keeps its filters (BR-SHL-011). It is parsed with the
  // AGEING's own config, because `parseTableParams` validates `sort` against
  // the columns it is given and the trial balance's would silently fall back.
  const agingConfigForParams = agingConfig(null, translate, props.locale, { services: [] });
  const agingState = parseTableParams(searchParams, agingConfigForParams);
  function setAgingState(next: TableRequestState): void {
    const params = serializeTableParams(next, agingConfigForParams);
    params.set("view", "aging");
    if (agingPremisesId !== "") {
      params.set("f.premises", agingPremisesId);
    }
    setSearchParams(params, { replace: true });
  }
  // `""` means EVERY property, which is the unfiltered ageing and the default —
  // the same two-piece state the General ledger's property filter uses, and the
  // same remote-search field, because the values are the tenant's premises and
  // that is an unbounded list (`NFR-5`).
  const [agingPremisesId, setAgingPremisesId] = useState(searchParams.get("f.premises") ?? "");
  const [agingPremisesTerm, setAgingPremisesTerm] = useState("");
  const agingPremisesSearch = usePremisesSearch(agingPremisesTerm, client, "aging");
  // BR-REP-006 — the tenant's LIVE services, never a literal array. The
  // eleventh service (`fire`) exists, is served, and is invisible on any screen
  // that types the list out by hand (hard-won law 2).
  const reportVocab = useQuery({
    queryKey: ["reports", "library", "aging-vocab"],
    queryFn: () => getReportLibrary(client),
    retry: false,
    enabled: view === "aging",
  });
  const agingParams = {
    // BOTH bounds: the handler refuses a half window for every report, even
    // one that reads only the upper bound (see `AgingReportQuery`).
    from: period === null ? "" : period.start,
    to: period === null ? "" : period.end,
    "f.band": agingState.filters.band ?? "",
    "f.service": agingState.filters.service ?? "",
    "f.premises": agingPremisesId,
    q: agingState.q,
    sort: agingState.sort,
    dir: agingState.dir,
    page: String(agingState.page),
    per: String(agingState.per),
  };
  const agingQuery = useQuery({
    queryKey: ["reports", "ar_aging", JSON.stringify(agingParams)],
    queryFn: () => runAgingReport(agingParams, client),
    retry: false,
    enabled: view === "aging" && period !== null,
  });
  const agingExport = useMutation({
    mutationFn: () =>
      requestReportExport(
        "ar_aging",
        {
          from: period?.start,
          to: period?.end,
          service: agingState.filters.service,
        },
        client,
      ),
    onSuccess: () => toast(t("reports.export.queued")),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (reportQuery.isError && isPermissionDenied(reportQuery.error)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const report = reportQuery.data;
  const failed = reportQuery.isError && report === undefined;
  const routeAbsent = failed && readRouteAbsent(reportQuery.error);

  return (
    <div className="fin-page">
      {/* US-SHL-020 / BR-SHL-044: this screen DECLARES a header, it does not
          draw one. The prototype's Finance head is an H1 plus its `.sub`
          roll-up, its two page actions and the five-tab strip. */}
      <PageHeader
        title={t("shell.nav.finance")}
        rollup={<PeriodRollup period={period} t={translate} timeZone={timeZone} dateFormat={dateFormat} />}
        secondaryActions={
          // The prototype's "↓ Download period pack" and "↗ Send to QuickBooks".
          //
          // ⚠ **THE PACK IS RELEASED (`DEF-LED-6662`).** This comment used to
          // end *"minting either control now would be a button onto nothing"*
          // and the control rendered disabled, titled *"The period pack is not
          // built."* — on ALL FIVE Revenue & AR views, because it sits on the
          // page HEAD. The pack was built underneath it: `US-LED-016`'s export
          // batch, `GET /finance/export/batches` and `.../{id}/file`, the
          // Close & export hand-over, and four real files downloaded from it
          // on 2026-09-24. The refusal outlived what it was waiting for, which
          // is hard-won law 2's mirror and which no gate here can see, because
          // none reads a rendered `title`.
          //
          // `PeriodPackButton` now DERIVES both states from the books: a real
          // `<a download>` when a handed-over batch covers the open period,
          // and *"No month has been handed over yet."* when none does.
          // "↗ Send to QuickBooks" stays absent — BR-LED-020 / BR-INT-010 make
          // live sync v2, and that refusal is still true.
          <PeriodPackButton period={period} client={client} />
        }
        tabs={FINANCE_TABS.map((tab) => ({
          id: tab.id,
          label: t(tab.labelKey),
          explainer: tab.id === FINANCE_TAB_REVENUE ? t("finance.explainer.revenue") : undefined,
        }))}
        activeTabId={active}
        tabsLabel={t("finance.tabsLabel")}
        onTabSelect={(tab) => navigate(tenantPath(financeTabPath(financeTabFrom(tab.id))))}
      />

      {period === null ? (
        // BR-TEN-022 again: no configured period, no report. Said in words.
        <ArrivesWith
          title={t("settings.regional.currentPeriod")}
          message={t("settings.regional.noPeriod")}
        />
      ) : routeAbsent ? (
        <ArrivesWith
          title={t("finance.awaits.endpointTitle")}
          message={t("finance.awaits.endpoint")}
        />
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("finance.error.title")}</h3>
          <p className="fin-absent-reason">{apiErrorText(reportQuery.error, translate)}</p>
        </Panel>
      ) : report === undefined ? (
        <LoadingSkeleton variant="kpi" />
      ) : (
        <>
          {/* ⚠ **THE KPI STRIP SITS ABOVE THE VIEW STRIP ON EVERY VIEW** —
              `P2.18`'s own words, and the blueprint draws it that way on all
              five pages (p033, p034, p036, p038). It is OUTSIDE the switch
              below for exactly that reason: a strip rendered per-view is a
              strip four lanes can forget on the fifth. */}
          <KPIStrip kpis={revenueArKpis(report, translate, props.locale)} />
          <ViewStrip
            label={t("finance.revenue.viewsLabel")}
            active={view}
            items={REVENUE_AR_VIEWS.map((candidate) => ({
              id: candidate,
              label: t(`finance.revenue.view.${candidate}`),
              // Only two of the five carry a number, which is the drawing's
              // own arrangement: Services, Aging and Tie-out are reads with
              // nothing waiting on a person.
              count:
                candidate === "writeoffs"
                  ? (writeOffCount.data?.pending ?? null)
                  : candidate === "refunds"
                    ? (refundCount.data?.pending ?? null)
                    : null,
              countLabel:
                candidate === "writeoffs" || candidate === "refunds"
                  ? t("finance.revenue.view.pending")
                  : undefined,
            }))}
            onSelect={(candidate) => setSearchParams(withView(searchParams, candidate))}
          />
          {/* ══════════════════════════════════════════════════════════════
              `P2.18` — THE BOARD IS RETIRED AND EACH CATEGORY IS A VIEW
              ══════════════════════════════════════════════════════════════
              What stood here was `fin-two-col`: ten panels in two columns,
              which the blueprint calls *"the board"* and `P2.11` was written
              to lay out. p006 retires it — *"2·1 The board → **retired**"* —
              and `P2.11` with it: *"replaced by P2.18; there is no board to
              lay out"*.

              ⚠ **FOUR PANELS AND TWO LINKS HAVE NO VIEW OF THEIR OWN, AND
              THEY ARE KEPT ON THE LANDING VIEW RATHER THAN DELETED.** The
              board carried more than the five categories: the 12-month chart's
              stated absence, Adjustments & credits, the cash position, bad
              debt, and the two links out to the by-premises and customer-
              statement reports. p006's map sent the LINKS to views 2·6–2·8 —
              **and those three views are exactly the ones the PO removed when
              they ruled *"5 is correct"***, so that destination no longer
              exists and the blueprint has no other.

              **Deleting them would destroy doors to figures that exist nowhere
              else in Finance**, which is hard-won law 2's mirror and precisely
              the fault `P2.23` is written to catch. Keeping them on Services
              costs nothing a clerk can see going wrong: `/finance/revenue`
              opens here, so everything reachable yesterday is reachable today
              at the same address. **It is a judgment this lane took, it is
              recorded in the decision log with an open question for the PO
              about where they belong now, and reversing it is a move of this
              one block.** */}
          {view === "services" ? (
            <>
              <RevenueByServiceTable
                report={report}
                t={translate}
                locale={props.locale}
                state={servicesState}
                onStateChange={setServicesState}
                periodFilter={{ dateFormat }}
              />
              {/* The prototype's 12-month bar chart. This read model answers for
                  ONE period; a chart of one bar labelled "last 12 months" is a
                  claim about eleven periods nobody read.

                  B14 rule 32 — NOT `AbsentPanel` here. This is a permanent gap
                  rather than a failed read, so the heading stays in plain sight
                  (the reader has to know WHICH thing is missing) and the
                  sentence goes behind the closed disclosure `AbsentFigure`
                  draws. `AbsentPanel`'s own docstring carries the distinction. */}
              <Panel className="fin-absent-panel">
                <div className="fin-panel-head">
                  <h3>{t("finance.chart.title")}</h3>
                </div>
                <AbsentFigure
                  label={t("finance.absent")}
                  reason={t("finance.chart.unavailable")}
                />
              </Panel>
              <AdjustmentsPanelView report={report} t={translate} locale={props.locale} />
              <CashPanel report={report} t={translate} locale={props.locale} />
              {/* CR-059 CS-26 (task 65) — BR-PAY-020's THIRD verb. *"Payments
                  owns the transaction record, ledger posts, FINANCE REPORTS"*,
                  and until this panel the third one had a finished read
                  (`GET /bad-debt`, mounted 2026-09-01) that no screen called. */}
              <BadDebtPanel
                t={translate}
                locale={props.locale}
                client={client}
                period={period}
              />
              <Panel>
                <div className="fin-panel-head">
                  <h3>{t("finance.revenue.byPremisesTitle")}</h3>
                </div>
                <InlineLink
                  type="button"
                  onClick={() => navigate(tenantPath(BY_PREMISES_ROUTE))}
                >
                  {t("finance.revenue.byPremises")}
                </InlineLink>
              </Panel>
              {/* CR-060 C16 / T17 — the customer statement, reached from the
                  screen that already asks *who owes you*. **A screen only a
                  typed URL can open is a screen that does not exist** (hard-won
                  law 2, five times in this module), and the two reports beside
                  it are reached from exactly here for the same reason.

                  ⚠ **AND THAT IS WHY THESE TWO LINKS SURVIVED `P2.18`.** The
                  ruling that removed views 2·6–2·8 left the three report
                  screens in Reports — p032, verbatim: *"The three report
                  screens stay in Reports (0)"* — and these are the doors
                  Finance has to them. */}
              <Panel>
                <div className="fin-panel-head">
                  <h3>{t("reports.statement.title")}</h3>
                </div>
                <InlineLink
                  type="button"
                  onClick={() => navigate(tenantPath(CUSTOMER_STATEMENT_ROUTE))}
                >
                  {t("finance.revenue.customerStatement")}
                </InlineLink>
              </Panel>
            </>
          ) : view === "aging" ? (
            /* `P2.21` — 2·2 Aging. The table, its toolbar and its pager are
               `AgingView`'s (B14 rule 43: a piece of UI is a COMPONENT, not a
               hundred lines inside a page). Everything this page hands it is
               STATE or a live vocabulary; not one figure is computed here. */
            <AgingView
              report={agingQuery.data ?? null}
              loading={agingQuery.isLoading}
              error={
                agingQuery.isError
                  ? { reason: apiErrorText(agingQuery.error, t), onRetry: () => agingQuery.refetch() }
                  : null
              }
              state={agingState}
              onStateChange={setAgingState}
              locale={props.locale}
              services={(reportVocab.data?.vocabularies?.services ?? []).map((row) => ({
                value: row.code,
                label: row.name,
              }))}
              asOfLabel={
                period === null ? "" : formatDate(period.end, timeZone, dateFormat)
              }
              premisesSlot={
                <PremisesFilterField
                  term={agingPremisesTerm}
                  onTermChange={setAgingPremisesTerm}
                  search={agingPremisesSearch}
                  value={agingPremisesId}
                  onChange={(id) => {
                    setAgingPremisesId(id);
                    // A criterion change returns to page one — page 7 of a
                    // narrower list is a screen with nothing on it and no
                    // explanation (BR-SHL-011).
                    setAgingState({ ...agingState, page: 1 });
                  }}
                  t={translate}
                />
              }
              onDownload={() => agingExport.mutate()}
            />
          ) : view === "tieout" ? (
            <TieOutPanelView
              client={client}
              period={period}
              t={translate}
              locale={props.locale}
            />
          ) : view === "writeoffs" ? (
            /* BR-PAY-020 puts the write-off APPROVAL in Finance. The panel is
               PAYMENTS' code shown as a view here — p038, verbatim: *"This is
               not Finance code … Mount the component; do not rebuild it. Any
               change is a Payments change."* */
            <WriteOffQueuePanel
              t={translate}
              locale={props.locale}
              client={client}
              asOf={period.end}
            />
          ) : (
            /* ⚠ **THE REFUNDS VIEW IS THE QUEUE — A READ — AND THE ACTS STAY
               AT `/payments/refunds`, WHICH IS A COLLISION THIS LANE DID NOT
               RESOLVE.** p041 puts the whole refunds screen here as view 2·5,
               *"the same screen, as a view"*, with Approve on the row. **The
               PAYMENTS blueprint ruled the opposite one day earlier**
               (`CR-138-BRC07` `P4.10`, 2026-09-23): `REFUNDS_ROUTE` moved to
               `/payments/refunds`, the screen draws the payments strip, and
               `/finance/refunds` redirects there — with a written supersedes
               chain ending *"Finance keeps reporting money out, **which is a
               read**"*.

               Both are dated and signed, and hard-won law 13 puts a ruling
               that collides with a signed rule in front of the PO rather than
               letting a lane pick. **So this view is the half both documents
               agree on** — Finance REPORTS what is waiting, the five acts stay
               in one place — and the door to the acts is the panel's own link.
               Mounting a second copy of five role-gated controls is what B14
               rule 43 forbids and what this panel's own `E1` already refuses.
               **Reversing to p041 is one component swap on this line.** */
            <RefundsQueuePanel t={translate} locale={props.locale} client={client} />
          )}
          {/* ⚠ **ON THE LANDING VIEW ONLY, AND THAT IS B14 RULE 32.** This is
              the safety net for a gap NO panel has claimed, and it used to sit
              under a single scrolling board where it appeared once. With five
              views it would print the same paragraph five times — one stated
              absence, five appearances — which is the exact defect the PO
              photographed on 2026-09-01 when `GAP_WRITTEN_OFF_YTD` was stated
              in a tile AND again at the foot of the page. Services is where it
              belongs because Services is where the other unclaimed board
              content now lives, and it is the view `/finance/revenue` opens. */}
          {view === "services" ? (
            <UnclaimedGaps
              gaps={report.unavailable}
              claimed={S36_CLAIMED_GAPS}
              t={translate}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

/**
 * The prototype's `.sub`: "August 2026 · Open · Hand off to your bookkeeper by
 * Sep 3" — every part of it SERVED (BR-TEN-022), none of it computed here.
 *
 * **The copy is the Settings screen's own**, key for key: `periodLabel`,
 * `periodStatus.<status>` and `periodCloses` already exist and already render
 * this exact card on S8 Regional. Minting a second set of finance-flavoured
 * period strings would give one fact two vocabularies, and the day a tenant read
 * "Open" on Settings and something else on Finance, one of them would be wrong.
 */
export function PeriodRollup(props: {
  period: ShellDisplayPeriod | CurrentPeriod | null;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  if (props.period === null) {
    return <span className="met-muted">{props.t("settings.regional.noPeriod")}</span>;
  }
  const { period } = props;
  const status = props.t(`settings.regional.periodStatus.${period.status}`, {
    defaultValue: period.status,
  });
  // ⚠ **THE HAND-OFF DATE IS ADMIN-ONLY AND ITS ABSENCE IS AN OLD STATE, NOT A
  // NEW ONE (`DEF-SHL-4283`).** This card is drawn from two payloads now: this
  // screen's `GET /settings/regional` (Admin/Executive, `CurrentPeriod`, with
  // `close_by`) and the seven Finance-frame screens' `GET /shell/display`
  // (every signed-in role, `ShellDisplayPeriod`, without it). `close_by` is
  // `close_day` in another shape — a finance-close deadline belonging to A4's
  // `finance_reconcile_export` cell — so a Billing Clerk on `Payments →
  // Refunds` gets the label, the window and the status and not the deadline.
  // The branch below is unchanged: it has rendered exactly this since the card
  // was written, for a tenant that has set no close day.
  const closeBy = "close_by" in period ? period.close_by : null;
  return (
    <span className="fin-rollup">
      <span className="fin-rollup-item">
        {props.t("settings.regional.periodLabel", {
          fy: period.fy_label,
          period: period.period,
        })}
      </span>
      <span className="fin-rollup-item">
        <DateCell
          value={period.start}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
        {" – "}
        <DateCell value={period.end} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      </span>
      <span className="fin-rollup-item">
        {closeBy === null
          ? status
          : props.t("settings.regional.periodCloses", {
              status,
              date: formatDate(closeBy, props.timeZone, props.dateFormat),
            })}
      </span>
    </span>
  );
}

/** Gaps the server named that no panel on this screen has already explained. */
export function UnclaimedGaps(props: {
  gaps: readonly LedgerUnavailable[];
  claimed: readonly string[];
  t: Translator;
}) {
  const rest = props.gaps.filter((gap) => !props.claimed.includes(gap.code));
  if (rest.length === 0) {
    return null;
  }
  return (
    <div className="fin-notes">
      {rest.map((gap) => (
        <ArrivesWith
          key={gap.code}
          title={props.t("finance.gap.title")}
          message={gapSentence(gap, props.t)}
        />
      ))}
    </div>
  );
}

export default RevenueArPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-007@a1f04c9 (story+rules snapshot — EP-LED-03 US-LED-007; 09-ledger/02-business-rules.md BR-LED-007/016; 12-reports/02-business-rules.md BR-REP-001/002/006/009/011/014; 11b §2.10; 05-prototype/UtilityBilling.html lines 3678-3800)
// generated: 2026-08-11 by story-coder (W5 finance SCREENS lane — the S36 read model shipped 2026-08-11 with `E=deferred(no-frontend-half)` in its own trailer)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the whole test file failed to resolve `./RevenueArPage` before this file existed; the verbatim failure is in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) SIX KPI tiles where the prototype draws FOUR — collection % and DSO are unavailable-with-a-reason and a reason does not fit in a detail line · (2) NO 12-month billed-vs-collected chart: the read model answers for ONE period and a one-bar chart labelled "last 12 months" claims eleven periods nobody read · (3) the Billed tile drops "↑ 8.4% vs Jul" and Written-off drops "0.4% of revenue" — both compare against a denominator the response does not carry · (4) the Revenue-by-service panel's "Export →" is replaced by a link to the S60 by-premises report; the export it pointed at is `POST /reports/{key}/export`, served by nothing · (5) "Review N pending →" renders DISABLED with its reason and carries NO count — a pending adjustment has not been posted, so the books cannot count it · (6) a cash-position panel the prototype does not draw, because PO ruling 2026-08-11 (OQ-143) splits receipts into realised and undeposited and they are never summed · (7) "↗ Send to QuickBooks" is not rendered at all: BR-LED-020/BR-INT-010 make live sync v2 and the connector matrix disables it at UI AND API · (8) the Tax and Collected columns of the Revenue-by-service table render "—" with the reason under the table, never 0.00
// amended:   2026-08-15 by story-coder (payments FRONTEND visible-half lane) — ONE panel added, and no figure touched: BR-PAY-020 (US-PAY-012) puts the write-off APPROVAL in Finance and `apps/payments/api.py` declares `/write-offs` POST-only, so this page cannot list the pending ones. The gap is stated on screen instead of leaving a Finance page that silently has no queue; the approval ACTION is live on S34, beside the request that mints the id. REPORTED: a `GET /write-offs` route turns this panel into the real queue.
// amended:   2026-09-01 by the finance-copy lane (live content defects the PO photographed on `/silver-creek-water/finance` at v2.123.0). NO figure and NO refusal was removed. (a) THE DUPLICATED PARAGRAPH: `GAP_WRITTEN_OFF_YTD` was absent from `UnclaimedGaps`' `claimed` list, so the Written-off tile and the foot-of-page panel printed the identical 49-word sentence — the tile keeps it, the panel filters it, and the other two claimed codes were added with it. (b) THE ESSAYS: `AbsentFigure` is a `<details>` CLOSED by default (B14 rule 32, `RunGap`'s shape); the three bare `<p className="fin-absent-reason">` absences on this screen and the twelve-month-chart panel now go through it too, so there is ONE renderer for a stated absence here. `AbsentPanel` is left OPEN on purpose — its two remaining call sites here carry `apiErrorText`, a failed read rather than a permanent gap, and closing an error behind a working-looking heading is hard-won law 1 aimed at the reader. (c) THE RULE IDS: seven hardcoded `brRef:` arguments (BR-REP-009 · BR-REP-011 · BR-TEN-022 · BR-LED-001 · BR-CUS-048 · BR-LED-016 · BR-REP-002) and the server `code` no longer reach `finance.gap.unknown` — B14 rule 31, and each id is in the code comment beside the call site it came from.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
