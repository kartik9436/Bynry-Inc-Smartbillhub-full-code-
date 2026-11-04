// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-025 (S30 All-bills list: search, the prototype's status
//           segments, the bill_type filter, the capability row's columns and
//           its default issue-date-desc sort) ·
//           US-CUS-010 (the S21 Bills tab — the SAME list scoped to one account
//           through `f.account_id`, which is 11b §2.6's own account scoping of
//           `GET /invoices`, not a second endpoint)
//           Screens: S30 (AppShell sidebar → Billing) · S21 (Bills tab)
// Rules:    BR-BIL-004 (the list exposes immutable issued history — no edit
//           affordance exists on any issued row) · BR-BIL-063 (every bill carries a
//           number, drafts included) · BR-BIL-024 (the due date is
//           derived at issue, so a draft has none) · BR-BIL-018 (the six bill
//           types the list filters on) · BR-BIL-030 (the bill is locked at
//           issue — what the row's total means) · BR-SHL-010 (a capability not
//           declared is not rendered) · BR-SHL-011 (URL grammar + fallback
//           law) · BR-SHL-012 (the A18 states, composed) · BR-SHL-020
//           (plain-language failure) · BR-SHL-023 (one money path) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason) ·
//           BR-SHL-034 (one date formatter) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S30 — the Billing page. The billing TABLES landed on 2026-08-11 (`invoices`,
// `invoice_lines`, `credit_notes`, `adjustments`, all under RLS) with no read
// endpoint and no screen, so a bill that exists is invisible. This is the
// screen; `GET /invoices` is the endpoint it reads, and that endpoint is
// CONTRACTED (11b §2.8, PO-adopted 2026-08-09) AND NOT SERVED YET.
//
// HOW THIS SCREEN IS HONEST ABOUT THAT, AND WHY IT IS NOT A FLAG.
// `GET /invoices` is a COLLECTION route: a list endpoint that exists answers
// 200 with zero results when nothing matches — it never 404s. So a 404 from it
// says "this API serves no bills list", the screen says exactly that, and the
// sentence stops appearing the hour the route is registered with nothing here
// edited. A constant reading `INVOICES_API = false` would have been a comment
// claiming a fact about another lane's file (hard-won law 1), stale on the
// first commit that fixed it. Everything else on this page is wired: the query
// fires, the config is the ratified capability row, and the cells render real
// rows the moment rows exist (the account-scoped tab and the tests both drive
// them today).
//
// WHAT THE PROTOTYPE DRAWS AND THIS SCREEN DOES NOT, each named on screen
// rather than mimed:
//
//   · **No CSV export.** `POST /exports` registers no `bills` resource
//     (EXPORT_RESOURCES) — there is no `apps/billing/exports.py` at all — and
//     BR-SHL-010 says an undeclared capability does not render, so the download
//     glyph ships disabled with its reason. The blueprint's entry 01 legend 6
//     asks for it enabled; that needs the backend half and is not this lane's.
//     ⚠ **THE COLUMN-CHOOSER HALF OF THIS SENTENCE WAS FALSE AND IS DELETED
//     (2026-09-14).** It said IS-5's per-user column preference *"needs
//     US-SHL-013's preference service, which is not wired"*. It IS wired —
//     `config/urls.py` includes `apps.tenancy.preferences_api`, `DataTable`
//     calls `columnPreferenceKey(config)`, this table's `screenId` is `"S30"`,
//     and the chooser reads through `getUserPreference` on mount and writes
//     through `putUserPreference` on every toggle. Hard-won law 1: a comment
//     claiming a state the product left. Measured by the step-1 §02 diff, which
//     found the drawing's legend 8 already BUILT.
//   · **No cycle / run / date-range filters.** All three are declared in the
//     US-BIL-025 capability row and all three need something that does not
//     exist: a cycle lookup readable by a Billing Clerk, a runs list (EP-BIL-01),
//     and a date-range control the shared FilterBar does not have (it renders
//     option lists only). Offering an empty select would narrow nothing while
//     looking as though it had.
//   · **No delivery-status column and no correction-chain badge.** BR-BIL-016's
//     outbound queue (r10 #8) has no table, and the chain is served on the
//     DETAIL, not the row.
//   · **The status SEGMENTS render as the framework's declared filter**, not as
//     the prototype's bespoke radio strip: the segment is a server-side
//     question (past-due is derived) and BR-SHL-011's `f.status=` grammar is
//     how this app asks one. One filter implementation, one URL grammar.
import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getInvoices, getUserPreference, putUserPreference } from "@/api/endpoints";
import type { InvoiceRow, InvoicesRollup } from "@/api/endpoints";
import { ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DownloadButton } from "@/components/DownloadButton";
import { FilterBar } from "@/components/FilterBar";
import { EyeIcon, PrinterIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PAGE_SIZES, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import type { PageSize, TableConfig, TableRequestState } from "@/components/tableTypes";
import { AwaitsCell, accountDetailPath } from "@/features/customers/customersShared";
import {
  CELL_FULL,
  Dash,
  GuardedButton,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BudgetBillsTab } from "./BudgetBillsTab";
import { FixABillTab } from "./FixABillTab";
import { PastBillingRunsPanel } from "./PastBillingRunsPanel";
import { ONE_TIME_BILL_ROUTE } from "./oneTimeBill/OneTimeBillPage";
import { BILLING_PENDING_ROUTE, billDocumentPdfPath } from "./billingOpsShared";
import { BILL_RUN_ROUTE } from "./billRunShared";
import { count } from "./bulkRun/bulkRunShared";
import { BILLING_PRINT_ROUTE } from "./PrintBillsPage";
import {
  BILLING_PERMISSION,
  BILLING_TABS,
  BILLING_TAB_ALL,
  BILL_STATUS_SEGMENTS,
  BILL_TYPE_VALUES,
  BillNumber,
  DASHBOARD_ROUTE,
  billDetailPath,
  billStatusLabel,
  billStatusTone,
  billTypeLabel,
  billingTabFrom,
  billsForAccountPath,
  listRouteAbsent,
} from "./billingShared";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const billsQueryKey = (query: string) => ["invoices", query] as const;

/**
 * ══════════════════════════════════════════════════════════════════════════
 * CR-053 TASK 12 — "PAGE SIZE REMEMBERED", THE HALF OF B14 RULE 16 THAT WAS
 * WRITTEN DOWN AND BUILT BY NOTHING.
 * ══════════════════════════════════════════════════════════════════════════
 *
 * Rule 16 is *"Showing 1–50 of N · Rows per page 50/100/200/500/1000 · ⇤ ← Page
 * x of y → ⇥. **Page size remembered per table.**"* — and its "Enforced by"
 * column says `shared DataTable`. The FOOTER is the shared table's and has been
 * right all along; the REMEMBERING is not there at all. `DataTable` persists
 * one thing, `table.<screen>.columns`, and `parseTableParams` reads `per` from
 * the URL and falls back to `DEFAULT_PAGE_SIZE` on every single visit. A clerk
 * who works this list at 200 rows sets it to 200 again every morning.
 *
 * **IT IS DONE HERE AND NOT IN `DataTable` DELIBERATELY.** The page size lives
 * in the URL (BR-SHL-011), and the URL is the CONSUMER's — this screen owns
 * `state`/`onStateChange` and the shared table is handed both. A preference
 * hook inside `DataTable` would have to write the consumer's query string from
 * underneath it, on 27 lists at once, in a file three lanes are editing. This
 * is one screen's own state, restored by the screen that owns it.
 *
 * THREE RULES, AND THE FIRST IS THE ONE THAT MATTERS:
 *
 *  1. **A `per` IN THE URL ALWAYS WINS.** A shared link must open the page it
 *     names (BR-SHL-011); silently resizing somebody else's link to a size this
 *     browser once chose would make the link mean two different things.
 *  2. **A stored value that is not one of the five sizes is IGNORED**, never
 *     applied and never fatal — BR-SHL-024's "unknown reads as absent".
 *  3. **A failure is never surfaced.** A remembered page size is a convenience;
 *     a toast about it would be worse than forgetting.
 */
export const BILLS_PAGE_SIZE_PREFERENCE_KEY = "table.S30.pageSize";

/** Whatever came back from the store → a page size to use, or null. PURE, so
 *  the three states are provable without a browser or a network. */
export function pageSizeFromPreference(stored: unknown): PageSize | null {
  if (typeof stored !== "number") {
    return null;
  }
  return (PAGE_SIZES as readonly number[]).includes(stored) ? (stored as PageSize) : null;
}

function useRememberedPageSize(props: {
  state: TableRequestState;
  /** True when the URL names a `per` — an explicit request that always wins. */
  urlHasPer: boolean;
  onStateChange: (next: TableRequestState) => void;
  client: ApiClient;
}) {
  const { state, client } = props;
  // `state` and the callback are new objects on every render, so they are read
  // through refs rather than listed as effect dependencies — the same idiom
  // `DataTable`'s own `useColumnPreference` uses, and for the same reason.
  const latest = useRef(props);
  latest.current = props;
  const settledRef = useRef(false);
  const lastSeenRef = useRef<PageSize | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getUserPreference<unknown>(BILLS_PAGE_SIZE_PREFERENCE_KEY, client)
      .then((stored) => {
        if (cancelled || settledRef.current) {
          return;
        }
        settledRef.current = true;
        const remembered = pageSizeFromPreference(stored);
        const now = latest.current;
        if (remembered === null || now.urlHasPer || remembered === now.state.per) {
          return;
        }
        // Page 1: a remembered size of 200 makes "page 3 of 25" a different
        // page, so the restore lands the reader at the start of the list.
        now.onStateChange({ ...now.state, per: remembered, page: 1 });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [client]);

  useEffect(() => {
    const previous = lastSeenRef.current;
    lastSeenRef.current = state.per;
    // First render stores nothing: the size on screen is not yet a CHOICE.
    if (previous === null || previous === state.per) {
      return;
    }
    settledRef.current = true; // a choice made before the read lands wins
    void putUserPreference(BILLS_PAGE_SIZE_PREFERENCE_KEY, state.per, client).catch(
      () => undefined,
    );
  }, [state.per, client]);
}

/** The two column sets this one list serves — see `billsTableConfig`. */
export type BillsScope = "all" | "account";

export interface BillsCells {
  billNo: (row: InvoiceRow) => JSX.Element;
  cycle: (row: InvoiceRow) => JSX.Element;
  account: (row: InvoiceRow) => JSX.Element;
  customer: (row: InvoiceRow) => JSX.Element;
  issueDate: (row: InvoiceRow) => JSX.Element;
  dueDate: (row: InvoiceRow) => JSX.Element;
  subtotal: (row: InvoiceRow) => JSX.Element;
  tax: (row: InvoiceRow) => JSX.Element;
  total: (row: InvoiceRow) => JSX.Element;
  status: (row: InvoiceRow) => JSX.Element;
  billType: (row: InvoiceRow) => JSX.Element;
  templateVersion: (row: InvoiceRow) => JSX.Element;
  /** CR-053 task 11 — B14 rule 15's icon cell. */
  actions: (row: InvoiceRow) => JSX.Element;
}

/**
 * The US-BIL-025 capability row, as the shared table framework reads it
 * (BR-SHL-010: a capability that is not declared here is not rendered).
 *
 * Column keys are the SERVER's sort names where a column is sortable, so the
 * request stays the contract's (`INVOICE_SORTS`); the renderer bridges key and
 * field. `issue_date` is the key rather than `issued_at` because that is the
 * name the capability row sorts on.
 *
 * TWO COLUMN SETS, ONE CONFIG. `scope: "account"` is the S21 Bills tab
 * (US-CUS-010): the account and customer columns are dropped — every row on
 * that tab belongs to the account whose page it is — and subtotal/tax join the
 * default set, which is exactly the column list the prototype's Bills tab draws
 * (line 1339). Two configs would be two places to forget a rule.
 */
/**
 * WHAT THE BILLS SEARCH BOX REALLY MATCHES, IN THE BOX (DEF-979).
 *
 * `DataTable` renders `table.search.placeholder` — *"Search this list"* — when
 * a config declares none, and that is what BIL-01 shipped with. A clerk holding
 * a bill number, an account number or a customer's name could not tell from the
 * screen whether any of the three would work, and the other two of the three
 * are exactly the ones nobody guesses.
 *
 * ⚠ **THE SENTENCE NAMES FOUR FIELDS SINCE 2026-09-09 (`CR-089` wave K,
 * `PUJ-53`), AND THE RULE THAT LOOKED LIKE A BAN IS NOT ONE.** This paragraph
 * read *"NAMES THREE FIELDS AND MUST NEVER NAME A FOURTH"*, and what it was
 * actually about is DEF-950 on the reads list: a prompt promised an address the
 * query **could not search**, which is worse than the generic prompt it
 * replaced — it sends a clerk to type something that will never match and then
 * to conclude the bill is not there. The query searches an address NOW
 * (`billing/selectors.py::_apply_search` ORs the accounts at a matching
 * property), so naming it keeps the promise rather than breaking it — and
 * withholding the word would be the mirror defect: a live leg nobody is told
 * about. `searchFields` in the config below is the contract this sentence
 * describes; they are written next to each other so a change to one is a
 * visible omission in the other, which is exactly how `CR043BillsSurface`
 * caught this file the moment the copy moved.
 */
export const BILLS_SEARCH_PLACEHOLDER_KEY = "billing.bills.searchPlaceholder";

export function billsTableConfig(
  t: Translator,
  cells: BillsCells,
  scope: BillsScope = "all",
): TableConfig<InvoiceRow> {
  const accountScoped = scope === "account";
  return {
    screenId: accountScoped ? "S21.bills" : "S30",
    columns: [
      // BR-SHL-013: the identity column can never be hidden. Every bill now
      // carries a number, drafts included (BR-BIL-063, PO 2026-08-11) — but the
      // field is SERVED and a served field can be null, so the cell still
      // renders a stated absence rather than a blank that reads as a load
      // failure.
      {
        key: "invoice_no",
        label: t("billing.bills.col.billNo"),
        sortable: true,
        identity: true,
        cell: cells.billNo,
      },
      { key: "cycle", label: t("billing.bills.col.cycle"), cell: cells.cycle },
      ...(accountScoped
        ? []
        : [
            { key: "account", label: t("billing.bills.col.account"), cell: cells.account },
            { key: "customer", label: t("billing.bills.col.customer"), cell: cells.customer },
          ]),
      {
        key: "issue_date",
        label: t("billing.bills.col.issueDate"),
        sortable: true,
        cell: cells.issueDate,
      },
      {
        key: "due_date",
        label: t("billing.bills.col.dueDate"),
        sortable: true,
        cell: cells.dueDate,
      },
      // US-CUS-010's tab shows the split; S30's own row does not (its capability
      // row lists Total only, and the split is one click away on the detail).
      {
        key: "subtotal",
        label: t("billing.bills.col.subtotal"),
        numeric: true,
        defaultVisible: accountScoped,
        cell: cells.subtotal,
      },
      {
        key: "tax_total",
        label: t("billing.bills.col.tax"),
        numeric: true,
        defaultVisible: accountScoped,
        cell: cells.tax,
      },
      {
        key: "total",
        label: t("billing.bills.col.total"),
        sortable: true,
        numeric: true,
        cell: cells.total,
      },
      {
        key: "status",
        label: t("billing.bills.col.status"),
        sortable: true,
        cell: cells.status,
      },
      // Two of the capability row's four "available" columns. `run` and
      // `delivery status` are absent: the runs list is EP-BIL-01 and the
      // outbound queue (BR-BIL-016 / r10 #8) has no table, so both would be
      // permanently empty columns — a worse answer than none.
      {
        key: "bill_type",
        label: t("billing.bills.col.billType"),
        defaultVisible: false,
        cell: cells.billType,
      },
      {
        key: "template_version",
        label: t("billing.bills.col.templateVersion"),
        defaultVisible: false,
        cell: cells.templateVersion,
      },
      // ⚠ **CR-053 TASK 11 — B14 RULE 15, AND THIS LIST HAD NO ACTIONS CELL AT
      // ALL.** Every route into a bill from this screen was the bill-number
      // link, so *print this bill* — the capability CR-053 task 1 unlocks —
      // was three clicks and a tab change away from a list of 94 bills.
      //
      // **TWO ICONS, AND THAT IS THE WHOLE CELL.** Rule 15 caps the visible set
      // at two plus a `…` overflow, and this list has exactly two actions that
      // a row can honestly offer: open it, and print it. *Fix this bill* is the
      // obvious third and it is deliberately NOT here — it is a WRITE, it is
      // RBAC-gated, and it has its own tab on this very screen with its own
      // bill picker; a third icon would need the overflow menu, and no such
      // component exists in this product (see `DEF-2453`).
      {
        key: "actions",
        label: t("billing.bills.col.actions"),
        cell: cells.actions,
      },
    ],
    getRowId: (row) => row.id,
    // IS-3 / the capability row: bill #, account #, customer name, address —
    // server-side, all four.
    // VERIFIED AGAINST THE PREDICATE 2026-09-09 (`CR-089` wave K, `PUJ-53`):
    // `billing/selectors.py::_apply_search` ORs `invoice_no |
    // account__account_no` with the accounts `_account_ids_by_customer_name`
    // returns AND with `_account_ids_at_address`, which walks
    // *bill → account → property* through customers' published read. Its own
    // docstring makes the point this whole CR is about — *"a fifth silent leg
    // is a screen that lies about what it searched."*
    // ⚠ **`address` IS METERING'S OWN MATCH AND IS WIDER THAN THE WORD.** It is
    // the predicate the Properties screen searches with, so the town, the
    // property number and the owner reach it too — one definition of *does this
    // property match what I typed* for the product, rather than one per screen.
    searchFields: ["invoice_no", "account_no", "customer_name", "address"],
    // ⚠ **B14 rule 19, AND A DELIBERATE DIVERGENCE FROM r10 (DEF-1001).**
    // r10 line 1529 draws `Search bills or cycles…` and **the cycle half is a
    // promise nothing on this toolbar keeps**: `_apply_search` has exactly the
    // three legs above, and this config declares only `status` and `bill_type`
    // chips — so a clerk who types a cycle name here gets nothing, and there is
    // no chip to fall back to either. (The SERVER does accept `cycle_id`; no
    // screen offers it.) The prompt states the three that work and **DEF-1001
    // carries the gap** — printing r10's copy would have hidden it, which is
    // exactly the choice DEF-950 records one screen over.
    //
    // ⚠ **TWO LANES FIXED THIS INDEPENDENTLY AND THE MERGE KEEPS BOTH HALVES**
    // — CR-041 task 2 (the sentence above, verified against `_apply_search`)
    // and CR-043 finding 5 / `DEF-979` (the same defect, reported by the PO from
    // the Billing list). They chose the same key. The VALUE comes from the
    // exported constant so the guard in `CR043BillsSurface.test.tsx` and the
    // CR-041 gate cannot drift apart from the call site, and the constant's own
    // docstring carries the "no fourth field" rule both lanes wrote down.
    searchPlaceholder: BILLS_SEARCH_PLACEHOLDER_KEY,
    filters: billsFilters(t),
    // IS-2 / the capability row: issue date desc. The newest bill is the one a
    // clerk is looking at, and a draft run is the newest thing there is.
    defaultSort: { sort: "issue_date", dir: "desc" },
  };
}

/**
 * The prototype's segment strip and the r10 #12 bill_type filter, as DECLARED
 * filters (BR-SHL-011's `f.<name>=` grammar).
 *
 * `past_due` sits in the STATUS options beside the five stored statuses because
 * that is what the prototype's strip does — and it is the one option the server
 * must resolve rather than match: past-due is `issued ∧ unpaid ∧ due_date <
 * today`, derived and never stored (US-BIL-025 §5).
 */
export function billsFilters(t: Translator) {
  return [
    {
      name: "status",
      label: t("billing.bills.filter.status"),
      options: BILL_STATUS_SEGMENTS.map((code) => ({
        value: code,
        label: t(`billing.bills.status.${code}`),
      })),
    },
    {
      name: "bill_type",
      label: t("billing.bills.filter.billType"),
      options: BILL_TYPE_VALUES.map((code) => ({
        value: code,
        label: t(`billing.bills.type.${code}`),
      })),
    },
  ];
}

/**
 * The one sentence the table shows when the request failed (BR-SHL-020).
 *
 * Pure and exported so the distinction is PROVABLE without a browser: a 404
 * from a COLLECTION route means the API serves no bills list, and anything else
 * is the server's own `message_key` through the catalog. Nothing here is
 * conditional on a build flag, so the first sentence stops being reachable the
 * moment `GET /invoices` is registered.
 */
export function billsFailureReason(error: unknown, t: Translator): string {
  return listRouteAbsent(error) ? t("billing.bills.failed.noEndpoint") : apiErrorText(error, t);
}

/** The request state → the wrapper's params. One translation, one place. */
export function billsParamsFrom(
  state: TableRequestState,
  extraFilters: Record<string, string> = {},
) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: { ...state.filters, ...extraFilters },
  };
}

// ── The header roll-up (prototype line 2881's `.sub`) ──────────────────────

/**
 * "7,240 bills lifetime · $342,180 out this cycle · 3 unresolved from the last
 * run" as the server can actually answer it.
 *
 * LABEL·VALUE pairs rather than the prototype's sentence: the money figure must
 * go through MoneyCell (BR-SHL-023), and a translated fragment either side of a
 * component is the concatenated sentence B8 forbids — it also breaks in German
 * and Hindi word order. Each label is one whole key.
 *
 * Every member is rendered ABSENT-WITH-REASON when the server sends null. "3
 * unresolved from the last run" and "we have not counted" are different claims,
 * and the second one is the true one until `GET /invoices` answers.
 */
export function BillsRollupLine(props: {
  rollup: InvoicesRollup | undefined;
  t: Translator;
  /** `tenantPath` from the screen. Absent on a mount that has no router — the
   *  figure then renders as plain text rather than as a broken link. */
  pendingQueueHref?: string;
}) {
  const { t, rollup, pendingQueueHref } = props;
  const unresolved = rollup?.unresolved_from_last_run;
  return (
    <span className="inline-flex flex-wrap items-baseline gap-1">
      <span className="inline-flex items-baseline gap-1 not-first:before:mr-1 not-first:before:content-['·'] not-first:before:text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
        <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("billing.rollup.bills")}
        </span>
        <span className="font-heading font-bold [font-feature-settings:'tnum']">
          {rollup?.bills != null ? (
            count(rollup.bills) // DEF-BIL-9007 — 40,017, never 40017
          ) : (
            <AwaitsCell label={t("billing.rollup.awaiting")} why={t("billing.rollup.billsWhy")} />
          )}
        </span>
      </span>
      <span className="inline-flex items-baseline gap-1 not-first:before:mr-1 not-first:before:content-['·'] not-first:before:text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
        <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("billing.rollup.thisCycle")}
        </span>
        <span className="font-heading font-bold [font-feature-settings:'tnum']">
          {/* CLAUDE.md #2: the amount and its CHAR(3) code travel together —
              MoneyCell may not guess a currency, so an amount served without
              one renders as unknown rather than as dollars. */}
          {rollup?.billed_this_cycle != null && rollup.billed_currency != null ? (
            <MoneyCell amount={rollup.billed_this_cycle} currency={rollup.billed_currency} />
          ) : (
            <AwaitsCell
              label={t("billing.rollup.awaiting")}
              why={t("billing.rollup.thisCycleWhy")}
            />
          )}
        </span>
      </span>
      {/* ── LEGEND 3 — THE UNRESOLVED COUNT BECOMES THE DOOR ──────────────
          Billing blueprint entry 01, p007: *"the figure is already computed
          (`bill_run_exclusions` for the newest run, unresolved) and the screen
          it belongs to already exists · NEW (a link on an unchanged field)"*.
          The drawing renders the WHOLE item in accent — label, figure and the
          arrow — so the link is the item, not a second control beside it.

          ⚠ It does NOT replace the `Pending queue` header button. The drawing's
          own carry-over marks those three header actions `UNCHANGED ×3` and
          says of this one: *"③ adds a second route to the pending queue; it
          does not replace the button."*

          Without a router (`pendingQueueHref` absent) the figure renders as
          plain text. A link is not drawn as a link it cannot follow. */}
      <span className="inline-flex items-baseline gap-1 not-first:before:mr-1 not-first:before:content-['·'] not-first:before:text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]">
        {unresolved != null && pendingQueueHref !== undefined ? (
          <InlineLinkTo
            to={pendingQueueHref}
            className="inline-flex items-baseline gap-1"
            data-bil="unresolved-door"
          >
            <span>{t("billing.rollup.unresolved")}</span>
            <span className="font-heading font-bold [font-feature-settings:'tnum']">{unresolved}</span>
            <span aria-hidden="true">→</span>
          </InlineLinkTo>
        ) : (
          <>
            <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {t("billing.rollup.unresolved")}
            </span>
            <span className="font-heading font-bold [font-feature-settings:'tnum']">
              {unresolved != null ? (
                unresolved
              ) : (
                <AwaitsCell
                  label={t("billing.rollup.awaiting")}
                  why={t("billing.rollup.unresolvedWhy")}
                />
              )}
            </span>
          </>
        )}
      </span>
    </span>
  );
}

// ── The rows table, shared by S30 and the S21 Bills tab ────────────────────

export interface BillsTableProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /**
   * `f.account_id` when this table is the S21 Bills tab, absent on S30. Passing
   * it also switches the column set (see `billsTableConfig`) — one prop, both
   * consequences, so an account-scoped table can never render an Account column
   * repeating the account whose page it is on.
   */
  accountId?: string;
  /** URL state lives on the PAGE for S30; the account tab keeps its own. */
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  emptyCtaReason: string | null;
  onEmptyCta: () => void;
}

export function BillsTable(props: BillsTableProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const scope: BillsScope = props.accountId === undefined ? "all" : "account";

  const config = billsTableConfig(
    translate,
    billsCells(translate, tenantPath, timeZone, dateFormat),
    scope,
  );
  const extraFilters: Record<string, string> =
    props.accountId === undefined ? {} : { account_id: props.accountId };
  const params = billsParamsFrom(props.state, extraFilters);
  const listQuery = useQuery({
    queryKey: billsQueryKey(
      `${serializeTableParams(props.state, config).toString()}|${props.accountId ?? ""}`,
    ),
    queryFn: () => getInvoices(params, client),
    // A missing route is not a flaky network: retrying a 404 three times only
    // delays the honest answer.
    retry: false,
  });

  const rows = listQuery.data?.results ?? [];
  const failed = listQuery.isError && listQuery.data === undefined;
  // ⚠ DEF-967 (CR-043 finding 6), the half that replaces 47 repetitions with
  // one sentence. DERIVED FROM THE ROWS ON SCREEN, never declared: the note
  // renders only while at least one issued row really has no past-due answer,
  // so it deletes itself the hour `selectors.invoice_row` can compute one —
  // with nothing here edited, the same discipline `routeAbsent` above uses.
  //
  // It is NOT rendered when the answer is simply "none of these are past due":
  // `past_due === null` is *unknown*, and the pill already carries the answer
  // whenever the server sends one.
  const pastDueUnknown = rows.some((row) => row.status === "issued" && row.past_due === null);
  // DERIVED, never declared: a served collection route answers 200-with-zero,
  // so a 404 means this API has no bills list. The day it does, this is false
  // and the panel below stops rendering with nothing here edited.
  const routeAbsent = failed && listRouteAbsent(listQuery.error);
  // The marker and the disclosure it points at are ONE condition, derived from
  // the same rows. Putting `headerNote` in `billsTableConfig` would have made
  // the ⓘ permanent — a footnote marker with no footnote under it the day the
  // server can compute past-due, which is hard-won law 2's mirror in miniature.
  const tableConfig =
    pastDueUnknown && scope !== "account"
      ? {
          ...config,
          columns: config.columns.map((column) =>
            column.key === "status"
              ? { ...column, headerNote: t("billing.bills.pastDueSummary") }
              : column,
          ),
        }
      : config;

  return (
    <>
      {routeAbsent && (
        <ArrivesWith
          title={t("billing.bills.awaits.endpointTitle")}
          message={t("billing.bills.awaits.endpoint")}
        />
      )}
      <DataTable<InvoiceRow>
        config={tableConfig}
        state={props.state}
        onStateChange={props.onStateChange}
        rows={rows}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          failed
            ? {
                // BR-SHL-020: plain language, and the SERVER's own message when
                // it sent one. The route-absent case is the only sentence this
                // screen writes itself, because the server sent no message_key
                // for a route it does not have.
                reason: billsFailureReason(listQuery.error, translate),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar
            filters={config.filters ?? []}
            state={props.state}
            onStateChange={props.onStateChange}
          />
        }
        // ══════════════════════════════════════════════════════════════════
        // CR-053 TASK 10 — THE DOWNLOAD GLYPH, DISABLED WITH ITS REASON.
        // ══════════════════════════════════════════════════════════════════
        // B14 rule 12's toolbar is one search, one filter set and one download
        // glyph, and this list had the first two and an empty spacer where the
        // third belongs. The gap is REAL and was re-measured on this branch
        // before anything was drawn: `POST /exports` resolves a registry that
        // `assets`, `metering`, `rating`, `reports` and `ledger` populate, and
        // **there is no `apps/billing/exports.py` at all**, so no `bills`
        // resource exists to ask for.
        //
        // **SO IT IS BR-SHL-025 AND NOT A LIVE BUTTON.** A clerk who came to
        // this screen to hand a bookkeeper a CSV must be able to see that the
        // product knows about the file and why it did not arrive — a control
        // that is simply absent sends them hunting through Settings. This is
        // the shape `GeneralLedgerPage`, `RemittancePage`, `DepositsPage` and
        // the two report screens already use: FE-14's ONE download control,
        // disabled, with the reason on a wrapper the tooltip can reach (a
        // disabled button fires no mouse events of its own).
        //
        // ⚠ **IT DOES NOT RE-OPEN THE PANEL THE PO RULED OFF THIS SCREEN**
        // (CR-043 finding 10, *"you ahve to remove - Filters that arrive later
        // … Export and column choices"*). That ruling was about a paragraph
        // occupying the page on every visit; this is a 36px control in the slot
        // the toolbar already reserves for it, silent until hovered. `DEF-1063`
        // still carries the absence.
        downloadSlot={
          <span title={t("billing.bills.exportUnavailable")}>
            <DownloadButton disabled onDownload={() => undefined} />
          </span>
        }
        empty={{
          title: t("billing.bills.emptyTitle"),
          helper: t("billing.bills.emptyHelper"),
          ctaLabel: t("billing.action.runBills"),
          ctaReason: props.emptyCtaReason,
          onCta: props.onEmptyCta,
        }}
      />
      {/* ══════════════════════════════════════════════════════════════════
          LEGEND 1 — THE PAST-DUE NOTE, COLLAPSED AND MOVED.
          ══════════════════════════════════════════════════════════════════
          Billing blueprint entry 01, p007 (the REDESIGN, read as an image per
          B14 rule 42): *"same sentence, now a `<details>` closed by default at
          the foot of the table, with an ⓘ on the Status header where the fact
          actually bites"* — the ONLY element on this screen the drawing's
          carry-over marks `MOVED`, and it moves for B14 rule 32 (a stated
          absence is a disclosure CLOSED by default) and rule 33 (RATIONALE is
          zero words on screen).

          ⚠ **THE SENTENCE IS NOT SHORTENED AND NOT DELETED.** It shipped as 45
          words of open prose ABOVE the table on every visit, which is the
          *"too much content - desctiption is too much for clark to read"*
          shape. Rule 33 removes rationale FROM THE SCREEN; it does not licence
          cutting a true sentence to six words and keeping the breach. So the
          words are unchanged and the key is unchanged — what changed is that a
          clerk has to ask for them.

          ⚠ **STILL DERIVED FROM THE ROWS, never declared** (DEF-967): it
          renders only while an issued row really has no past-due answer, so it
          deletes itself the hour `selectors.invoice_row` can compute one, with
          nothing here edited. The ⓘ on the Status header is driven by the SAME
          condition — a marker that can outlive the thing it points at is the
          refusal-that-outlived-its-reason shape, one screen over.

          ⚠ **NOT ON THE ACCOUNT'S OWN BILLS TAB (B14 rule 33, PO 2026-09-13).**
          It stays on S30, the utility-wide list, where one sentence covers a
          page of bills belonging to people the clerk is not on the phone to.

          The shape is `billRunShared.RunGap`'s and `SettingsBillingPlanTab`'s
          `AbsenceDetails` — this is the THIRD site and the pattern is a kit
          candidate. Not promoted here: a kit component is its own work with its
          own proof, and the drawing wants the plain treatment rather than
          either of those two boxes. */}
      {pastDueUnknown && scope !== "account" && (
        <details className="mt-3 m-0" data-bil="past-due-unknown" data-rule-ref="DEF-967">
          <summary className={`cursor-pointer text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]`}>
            {t("billing.bills.pastDueSummary")}
          </summary>
          <p role="note" className={`m-0 mt-1 max-w-measure text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]`}>
            {t("billing.bills.pastDueListNote")}
          </p>
        </details>
      )}
    </>
  );
}

/**
 * Every cell on the list, in one place so S30 and the S21 tab cannot render the
 * same column two ways. Each of the four honesty rules the epic names is one
 * cell here, and each is asserted by a test.
 */
export function billsCells(
  t: Translator,
  tenantPath: (path: string) => string,
  timeZone: string,
  dateFormat: RegionalDateFormat,
): BillsCells {
  return {
    // The prototype's row opens the bill, and that screen exists (US-BIL-026) —
    // so the identity cell is a LINK. It wraps the number, and it still wraps a
    // stated absence when one arrives: a draft is exactly what a clerk opens,
    // and hiding its only affordance because a field is null would make the
    // newest bills the unreachable ones. The link is built from the invoice ID,
    // never from the number, so it works either way.
    billNo: (row) => (
      <InlineLinkTo to={tenantPath(billDetailPath(row.id))}>
        <BillNumber row={row} t={t} />
      </InlineLinkTo>
    ),
    // The cycle label is read through metering (B1). A single/ad-hoc bill has no
    // run and therefore no cycle — that is an answer, so it is a dash.
    cycle: (row) => (row.cycle_label !== null ? <span>{row.cycle_label}</span> : <Dash />),
    account: (row) =>
      row.account_no !== null ? (
        <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>
          {row.account_no}
        </InlineLinkTo>
      ) : (
        <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>
          {t("billing.bills.noAccountNo")}
        </InlineLinkTo>
      ),
    // BR-CUS-054's `customers` entity is unbuilt, so the server sends the
    // primary CONTACT's name; null means no contact has been recorded.
    customer: (row) =>
      row.customer_name !== null ? (
        <span>{row.customer_name}</span>
      ) : (
        <Dash>{t("billing.bills.noCustomer")}</Dash>
      ),
    // A DRAFT has not been issued, so it has no issue date — and none of the
    // three date columns may show a placeholder that reads like one.
    issueDate: (row) =>
      row.issued_at !== null ? (
        <DateCell value={row.issued_at} timeZone={timeZone} dateFormat={dateFormat} />
      ) : (
        <Dash>{t("billing.bills.notIssued")}</Dash>
      ),
    // BR-BIL-024: the due date is DERIVED at issue and never typed, so a draft
    // has none. "—" alone would read as "no due date was set", which is a
    // different claim from "this bill has not been issued".
    dueDate: (row) =>
      row.due_date !== null ? (
        <DateCell value={row.due_date} timeZone={timeZone} dateFormat={dateFormat} />
      ) : (
        <Dash>{t("billing.bills.notIssued")}</Dash>
      ),
    // CLAUDE.md #2: the decimal STRING and its CHAR(3) code travel together from
    // the database to the pixel; nothing here parses, sums or rounds one.
    subtotal: (row) => <MoneyCell amount={row.subtotal} currency={row.currency} />,
    tax: (row) => <MoneyCell amount={row.tax_total} currency={row.currency} />,
    total: (row) => <MoneyCell amount={row.total} currency={row.currency} />,
    // The pill carries the DERIVED past-due state when the server computed one,
    // and the stored status otherwise. A null past_due is "not computed" — it
    // never becomes "not past due", which is a claim about a customer's money.
    // ⚠ DEF-967 (CR-043 finding 6). This cell used to render an `AwaitsCell`
    // — *"Past-due unknown"* — beside the pill whenever `status === "issued"`
    // and `past_due === null`. Both are true of EVERY issued bill this server
    // serves (`selectors.invoice_row` stamps `past_due: None` on every row),
    // so the note printed on all 47 rows of the live deployment and became the
    // column's content, crowding out the status that is really there.
    //
    // **The note was CORRECT per row and WRONG as a list.** An absence that is
    // true of every row is a fact about the LIST, and it is now stated once,
    // above the table, by `pastDueUnknownNote` below. Repeating a constant 47
    // times is not honesty; it is noise that trains a clerk to stop reading the
    // column. The pill itself is unchanged and still takes `past_due` into its
    // tone, so the day the server can answer, this cell needs no edit.
    status: (row) => (
      <StatusPill tone={billStatusTone(row.status, row.past_due)}>
        {billStatusLabel(row, t)}
      </StatusPill>
    ),
    billType: (row) => <span>{billTypeLabel(row.bill_type, t)}</span>,
    // r10 #3 / BR-BIL-026: the template pinned AT ISSUE. A draft pins nothing
    // yet, so this is absent rather than "v1".
    templateVersion: (row) =>
      row.template_version !== null ? (
        <span>{t("billing.bills.templateVersionValue", { version: row.template_version })}</span>
      ) : (
        <Dash>{t("billing.bills.notIssued")}</Dash>
      ),
    // ══════════════════════════════════════════════════════════════════════
    // CR-053 TASK 11 — TWO ICONS, EACH WITH ITS TOOLTIP (B14 rule 15).
    // ══════════════════════════════════════════════════════════════════════
    // The vocabulary is rule 15's own: 👁 view, 🖨 print. Both glyphs come from
    // `components/icons.tsx` — G37 clause 3 allows no `<svg` anywhere else —
    // and both carry an accessible NAME, which is the half of rule 15 that a
    // text-absence check can never see.
    //
    // ⚠ **PRINT REFUSES ON A DRAFT, WITH THE REASON, RATHER THAN VANISHING**
    // (BR-SHL-025). `template_version` is the pin BR-BIL-026 stamps AT ISSUE,
    // so a null is precisely "this bill has not been issued" — the same fact
    // the detail's print control branches on, read off the field this list
    // already serves rather than off a second request per row.
    //
    // ⚠ **IT IS A BUTTON AND NOT A LINK, AND THAT IS G37's DOING.** `<a>` would
    // give middle-click and *open in new tab* for free, but G37 clause 1 admits
    // only `<RowAction>` and `<RowActionLink>` inside a `<RowActions>` cell,
    // and `RowActionLink` is a ROUTER link — it cannot address `/api/…`, which
    // is not a route of this app. `window.open(…, "_blank", "noopener")` is the
    // same idiom `ReadsListPage` uses for the identical problem.
    actions: (row) => (
      <RowActions>
        <RowActionLink
          label={t("billing.bills.rowAction.view")}
          icon={<EyeIcon />}
          to={tenantPath(billDetailPath(row.id))}
        />
        <RowAction
          label={t("billing.bill.action.reprint")}
          icon={<PrinterIcon />}
          reason={
            row.template_version === null ? t("billing.bill.action.reprintDraft") : null
          }
          onClick={() =>
            window.open(apiHref(tenantPath(billDocumentPdfPath(row.id))), "_blank", "noopener")
          }
        />
      </RowActions>
    ),
  };
}

// ── The S21 Bills tab (US-CUS-010) ─────────────────────────────────────────

/**
 * The account's Bills tab: the SAME list, scoped by `f.account_id`. It is not a
 * second endpoint and not a second table — 11b §2.6 scopes `GET /invoices`, and
 * a per-tab read model would be a second place for BR-BIL-063's draft rule and
 * the past-due derivation to go wrong.
 *
 * Its table state lives in the tab's own URL params rather than the page's, so
 * paging the Bills tab does not disturb S21's `?tab=` and a link into a filtered
 * Bills tab stays shareable (BR-SHL-011).
 */
export function AccountBillsTab(props: RegionalProps & { accountId: string; client?: ApiClient }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  const config = billsTableConfig(
    translate,
    billsCells(translate, tenantPath, timeZone, dateFormat),
    "account",
  );
  const state = parseTableParams(searchParams, config);
  function setState(next: TableRequestState): void {
    // The tab param is the account page's, not the table's — it must survive a
    // sort click, so the table's params are merged onto the existing search.
    const merged = new URLSearchParams(searchParams);
    const serialized = serializeTableParams(next, config);
    for (const key of ["q", "sort", "dir", "page", "per"]) {
      merged.delete(key);
    }
    for (const filter of config.filters ?? []) {
      merged.delete(`f.${filter.name}`);
    }
    for (const [key, value] of serialized.entries()) {
      merged.set(key, value);
    }
    setSearchParams(merged, { replace: true });
  }

  return (
    <>
      <div className="mb-2 flex justify-end text-sm">
        {/* The prototype's "All bills →" exit from the account's bills panel. */}
        <InlineLinkTo to={tenantPath(billsForAccountPath(props.accountId))}>
          {t("billing.bills.allBillsLink")}
        </InlineLinkTo>
      </div>
      <BillsTable
        client={props.client}
        accountId={props.accountId}
        state={state}
        onStateChange={setState}
        // DEF-2421 — this said the run could not be started; it can. The
        // account's own empty Bills tab opens the same wizard the Billing
        // screen's primary does.
        emptyCtaReason={null}
        onEmptyCta={() => navigate(tenantPath(BILL_RUN_ROUTE))}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
      />
      {/* ⚠ **THE FACT STAYS AND THE EXPLANATION GOES (B14 rule 33, PO
          2026-09-13).** This block was headed *"Columns this tab cannot show"*
          over 31 words explaining why the usage behind a bill is not summed,
          and the Product Owner pasted both back out of the running product as
          copy they do not want a clerk reading. Rule 33 is exact about which
          half goes: a stated absence is a FACT and gets six words; the reason
          for it is RATIONALE and gets zero. The two keys now read *Usage not
          shown* and *Usage is not summed yet.* — three words and five.

          **The reason, which is what belongs here.** The blueprint draws the
          usage each bill was raised on. Usage is summed from meter reads and no
          module publishes that summary per bill, so the drawn table has eight
          columns and none of them is usage — a zero there would read as *they
          used nothing*. */}
      <ArrivesWith
        title={t("billing.bills.awaits.accountTabTitle")}
        message={t("billing.bills.awaits.accountTab")}
      />
    </>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface BillsListPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function BillsListPage(props: BillsListPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const active = billingTabFrom(routeParams.tab);
  const cell = useAccessCell(BILLING_PERMISSION, client);
  // BR-SHL-025: "Full" writes; anything else renders the control disabled WITH
  // the reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("billing.rbac.readOnly");
  // ⚠ **THIS COMMENT SAID `POST /billing/runs` IS NOT REGISTERED, AND IT
  // STOPPED BEING TRUE — THE PRIMARY ACTION ON THE BILLING SCREEN WAS DEAD FOR
  // THAT REASON ALONE (DEF-2421, PO 2026-09-01: *"Bills are not generated
  // during tenant creation process"*).** `apps/billing/api.py` registers
  // `path("billing/runs", bill_runs)` under `@api_view(["GET", "POST"])` —
  // US-BIL-001, S31 step 1 — and `/billing/run` has routed to `BillRunWizard`
  // since 2026-08-11. So the only screen-level way to start a run was greyed
  // out, wearing a sentence about our own routing table, while the tab six
  // pixels away opened the working wizard. Hard-won law 1: a comment claiming a
  // state the product has left, with a disabled button attached to it.
  //
  // The ONLY lawful reason to disable this now is BR-SHL-025's — the clerk may
  // not write. `null` means allowed.
  const runReason = writeBlockedReason;
  const openRunWizard = () => navigate(tenantPath(BILL_RUN_ROUTE));

  const config = billsTableConfig(
    translate,
    billsCells(translate, tenantPath, "UTC", "MM/DD/YYYY"),
    "all",
  );
  const state = parseTableParams(searchParams, config);
  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }
  // CR-053 task 12 / B14 rule 16. Declared BEFORE the early returns below,
  // because hooks run unconditionally — and reading the raw param rather than
  // `state.per` is what tells a shared link (`?per=200`) apart from this
  // browser's remembered choice.
  useRememberedPageSize({
    state,
    urlHasPer: searchParams.get("per") !== null,
    onStateChange: setState,
    client,
  });

  // The roll-up rides on the list request, exactly as S17's does: there is no
  // roll-up resource of its own, and recomputing counts here would answer a
  // different question from the one the header asks.
  //
  // ⚠ **THIS CARRIED `enabled: active === BILLING_TAB_ALL` UNTIL 2026-09-14 AND
  // THAT IS `DEF-BIL-5231`.** The header is drawn ABOVE the tab strip and
  // belongs to the SCREEN, not to a tab — so a clerk on `/billing` read
  // *"Bills lifetime 92"* and the same header one click away on `/billing/fix`
  // read *"Not counted yet"*, on a tenant with 92 real bills. Worse than the
  // blank: `AwaitsCell`'s sentence made a claim about the SERVER (*"nothing
  // serves that list yet"*) when what had happened is that the CLIENT never
  // asked. `GET /invoices` answers `count: 92` on request, from every tab.
  //
  // **Nothing tested it and nothing could**, because each tab's suite mounts
  // its own tab: the question *does this header still say the same thing one
  // click away* belonged to nobody. `CR101Entry01.dom.test.tsx` now mounts
  // `/billing/fix` with a RECORDING client and asserts both halves — that the
  // request went out, and that the served figure reached the screen. ⚠ Seeding
  // the query cache instead would have passed on the BROKEN code, because
  // `useQuery({ enabled: false })` still returns whatever the cache holds.
  const rollupQuery = useQuery({
    queryKey: billsQueryKey(`${serializeTableParams(state, config).toString()}|`),
    queryFn: () => getInvoices(billsParamsFrom(state), client),
    retry: false,
  });

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (rollupQuery.isError && isPermissionDenied(rollupQuery.error)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  return (
    <div className="px-4 pt-6 pb-8">
      {/* US-SHL-020 / BR-SHL-044: this screen DECLARES a header, it does not
          draw one. The prototype's Billing head is an H1 plus its roll-up
          `.sub`, one page action and the six-tab strip — no kicker. */}
      <PageHeader
        title={t("billing.title")}
        rollup={
          <BillsRollupLine
            rollup={rollupQuery.data?.rollup}
            t={translate}
            pendingQueueHref={tenantPath(BILLING_PENDING_ROUTE)}
          />
        }
        secondaryActions={
          <>
            {/* THE PENDING-BILLING QUEUE's entry point (US-BIL-006, *"hold ≠
                forget"*). `GET /billing/pending` has been served since the queue
                landed and nothing called it, so an account a run did not bill was
                invisible.
                ⚠ **THE REASON GIVEN HERE WAS WRONG TWICE OVER AND IS REPLACED
                (2026-09-14).** It read *"It is a LINK rather than a seventh tab:
                the prototype's Billing strip has six labels and G14 compares the
                shipped ones against it."* **G14 does not read a single billing
                tab label** — grep `billing.tab` across `10-scripts/gates/`:
                nothing. And the strip IS seven labels now, by PO ruling
                2026-09-12 #10. This stays a BUTTON because the drawing keeps it
                one and its own carry-over marks the three header actions
                `UNCHANGED ×3`; the roll-up's unresolved figure adds a second
                route to the same screen without replacing it. */}
            <ButtonLink variant="secondary" to={tenantPath(BILLING_PENDING_ROUTE)}>
              {t("billing.action.pendingQueue")}
            </ButtonLink>
            {/* CR-053 task 13 — PRINT BILLS. ⚠ **IT IS NOW ALSO THE SEVENTH
                TAB** (PO ruling 2026-09-12 #10, *"We will need Print bills as
                tab at Billing level"*) and the button STAYS: the blueprint's
                entry 01 draws both, and its carry-over marks these three header
                actions `UNCHANGED ×3`. Adding the tab is what was ruled;
                removing the button was not.

                The old note here said this was a link rather than a tab because
                *"the Billing strip has six labels G14 checks against the
                prototype"*. **G14 checks no billing tab label** — see the note
                on the pending-queue button above. What is still true, and is
                the reason this is not a toolbar control: B14 rule 12 (with rule
                32) gives the TABLE toolbar one search, one filter set and one
                download glyph and nothing else. That glyph is the bills-list
                CSV, a different artefact for a different reader; handing a
                bookkeeper a zip of PDFs from that slot is how one control ends
                up meaning two things. */}
            <ButtonLink variant="secondary" to={tenantPath(BILLING_PRINT_ROUTE)}>
              {t("billing.action.printBills")}
            </ButtonLink>
          </>
        }
        primaryAction={
          <GuardedButton
            label={t("billing.action.runBills")}
            reason={runReason}
            variant="primary"
            onClick={openRunWizard}
          />
        }
        tabs={BILLING_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId={active}
        tabsLabel={t("billing.tabsLabel")}
        onTabSelect={(tab) =>
          navigate(tenantPath(tab.id === BILLING_TAB_ALL ? "/billing" : `/billing/${tab.id}`))
        }
      />

      {active === "fix" ? (
        // S30's Fix-a-bill tab. Hard-won law 2: the correction ENGINE has been
        // complete and golden-verified since 2026-08-15 and this is the first
        // thing in the product that can reach a line of it.
        <FixABillTab
          client={client}
          readOnly={writeBlockedReason !== null}
          readOnlyReason={writeBlockedReason ?? undefined}
        />
      ) : active === "budget" ? (
        // S30's Budget Bills tab — `budget_service.enroll` had no caller
        // outside tests until this commit.
        <BudgetBillsTab
          client={client}
          readOnly={writeBlockedReason !== null}
          readOnlyReason={writeBlockedReason ?? undefined}
        />
      ) : active === "history" ? (
        // ⚠ **THIS BRANCH REPLACES A GREY PANEL THAT REFUSED OVER A WORKING
        //    READ — `DEF-BIL-5351`, hard-won law 2's MIRROR.** The tab rendered
        //    *"…It arrives with the billing run work."* while `GET /billing/runs`
        //    had answered since `CR-029` and `bill_runs.run_by` had been
        //    populated and on the wire since screen 16's BY column landed. `G13`
        //    asks whether a prop is PASSED; nothing asks whether a REFUSAL IS
        //    STILL TRUE, so every suite and every gate passed over it.
        //
        //    The blueprint says it about this screen in its own words (p145):
        //    the blocker the screen named on itself is *"false in both halves
        //    that matter"*.
        <PastBillingRunsPanel client={client} />
      ) : active === "one-time" ? (
        // ⚠ **THE ONE-TIME BILL IS ITS OWN PAGE FROM 2026-09-30 AND THIS BRANCH
        // IS NOT A DOOR.** `/billing/one-time` is a static route declared above
        // `billing/:tab` in `App.tsx`, so the router mounts `OneTimeBillPage`
        // there and never this list (`OneTimeBillDoor.test.tsx` asserts it by
        // address). The branch exists only so a bare mount of this component at
        // that tab does not fall through to the *"arrives with …"* note below —
        // a refusal over a screen that is live (hard-won law 2's mirror).
        <ButtonLink to={tenantPath(ONE_TIME_BILL_ROUTE)}>{t("billing.tab.oneTime")}</ButtonLink>
      ) : active === BILLING_TAB_ALL ? (
        <>
          <BillsTable
            client={client}
            state={state}
            onStateChange={setState}
            emptyCtaReason={runReason}
            onEmptyCta={openRunWizard}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
          {/* ⚠ TWO `ArrivesWith` PANELS STOOD HERE UNTIL 2026-08-27 AND THE
              PRODUCT OWNER RULED THEM OFF THE SCREEN (CR-043 finding 10),
              verbatim: *"you ahve to remove - Filters that arrive later …
              Export and column choices"*.

              **THIS DOES NOT REPEAL HARD-WON LAW 2.** The ruling is about
              WHERE an unbuilt feature is stated, not whether it is stated.
              Two kinds of emptiness had been rendered the same way:

                · A FEATURE WE HAVE NOT BUILT — cycle/run/date filters, export
                  and column choices. A clerk cannot act on it, did not ask for
                  it, and it occupied the screen on every single visit. It is
                  stated in the REGISTER instead: `DEF-1062` (the three filters)
                  and `DEF-1063` (export and column choices) now carry those two
                  absences, and `G38`'s `UNTRACKED_BASELINE` fell 71 → 69 in the
                  same commit. **That drop is a MOVE, not a payment** — G38
                  cannot tell a paid debt from a deleted notice, so the register
                  rows are what keep the fact alive.

                · A SECTION WITH NO DATA IN IT — the PO's other sentence,
                  *"if there are nothing to report we have to show nothing to
                  report"*. That one STAYS, and the Corrections tab's *"No
                  credit note or replacement bill is recorded against this
                  bill"* is its model. */}
        </>
      ) : (
        <ArrivesWith
          title={t(BILLING_TABS.find((tab) => tab.id === active)?.labelKey ?? "billing.tab.all")}
          message={t(`billing.arrives.${active === "one-time" ? "oneTime" : active}`)}
        />
      )}
    </div>
  );
}

export default BillsListPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-025@f4c9d21 (story+rules snapshot — EP-BIL-07 lead story; co-packets US-BIL-026/027 same epic · US-CUS-010 EP-CUS-03 · billing 03-field-map §2)
// generated: 2026-08-11 by story-coder (W3 billing FRONTEND lane — S30 All bills + the S21 Bills tab, the screens the billing tables landed without)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices is contracted at 11b §2.8 and unserved; 06-backend is another lane's and this packet is frontend-only) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 738 passed / 174 todo across 53 files✔ (702 passed / 168 todo across 51 files was the pre-lane baseline — this lane adds 36 passing + 6 todo across 2 new files and dropped nothing) · vite build✔ · run_gates 15 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2628 keys, identical sets)
// exceptions: E2 [law 6, prototype diff] RESOLVED 2026-08-11 IN THE PROTOTYPE'S FAVOUR, and left here because a reversal is worth reading. This screen shipped rendering a stated absence where a draft's number goes, diverging from the prototype's own numbered Draft rows (`BL-2608-018320` … `BL-2608-018322`, all three pilled "Draft", prototype line 2899) on the reading that BR-BIL-022 mints the number AT ISSUE. BR-BIL-022 says no such thing — it names the SOURCE and FORMAT of a number and is silent on timing; "at issue only" lived in an epic field-map row and was never a numbered rule. The PO ruled the timing on 2026-08-11 (BR-BIL-063): a number is allocated when the DRAFT is created and an unused one is lost, weighed explicitly against the wasted numbers — *"if not use thats okay we will lose it; its okay; dont over complicate, keep it simple."* So the prototype was right, DEF-033 is REVERSED, and the divergence is gone. `BillNumber`'s absence branch is KEPT for the SERVED null (an older row, a partial response), not for drafts
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
