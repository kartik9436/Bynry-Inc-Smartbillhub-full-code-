// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-002 (S46 report viewer) · US-REP-003 (IS-11 download) ·
//           US-REP-005 (AR aging) · US-REP-006 (billing register · revenue by
//           service & rate) · US-REP-007 (payments by method)   Screens: S46
// Change:   CR-142-BRC07 Phase 2 — screen **2·1**, rebuilt on the shared
//           `DataTable`: P2.5 (toolbar · pager · column chooser · empty state)
//           · P2.6 (the class control) · P2.7 (real date fields) · P2.13 (a
//           tile with no number says so) · P2.23 (the grain line).
//           Built from `05-prototype/09 Reports Build Brief.pdf` pages **p024
//           (2·1a), p025 (2·1b + the field notes), p026 (2·1c and 2·1d), p027
//           (the screen's own FIELDS / TABLE CONTROLS table), p010–p013 (the
//           task rows) and p090–p092 (§08, the two read paths)** — every one of
//           them opened as a RENDERED IMAGE, per B14 rule 42.
// Rules:    BR-REP-001 (EVERY money KPI/report header labels its date basis) ·
//           BR-REP-002 (read-models; the screen computes nothing) · BR-REP-006
//           (filters enumerate LIVE vocabularies) · BR-REP-014 (a deposit is
//           never inside a collection figure) · BR-REP-018 (IS-11 downloads) ·
//           BR-REP-024 / BR-REP-033 (a figure that cannot be computed prints
//           its reason) · BR-SHL-011 (the URL grammar) · BR-SHL-023 (one money
//           formatting path) · BR-SHL-044 (one page header) · NFR-3 (universal
//           server pagination) · NFR-5 (no hard caps) · B14 rules 20 (one table
//           type), 21 (Tailwind only), 31, 33, 40, 43, 44 · CLAUDE.md rule 3
//           (a quantity with its unit).
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE SCREEN COMPUTES NOTHING. NOT ONE NUMBER.                            ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Every amount, every count, every percentage and every footer cell arrives
// formed from `apps/reports/queries.py`. There is no `reduce` over `rows` in
// this file and no `+` on a money value anywhere in it — and that survived the
// rebuild, which is the part worth checking: a footer summed in the browser is
// a fifth opinion, and it is the one that disagrees the moment a filter, a PAGE
// or a rounding rule changes on one side only (DEF-104). **A page is the new
// way to be wrong here**, and it is exactly why the footer below reads the
// server's `totals` and never sums `rows`.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  §8.2 — THE LEFT PATH NEVER FETCHES MORE THAN A PAGE                     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The brief draws the two read paths side by side (p091) and states the rule
// underneath: *"The left path never fetches more than a page; the right path
// never holds one. Building either the other way is the mistake this drawing
// exists to prevent."*
//
// ⚠ **THIS FILE WAS THE LEFT PATH BUILT THE OTHER WAY.** It sent `per: "all"`
// on every request, with a nine-line comment explaining that it had to, because
// it rendered one table with no pager. At the top of the ICP that is 38,412
// rows fetched to draw a screen, against a **sixty-second worker timeout**
// (`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`). The comment was honest and
// the design it defended was the defect.
//
// It asks for a PAGE now. `per: "all"` survives in exactly one place — the
// EXPORT — which is the right path, and which must never hold a page:
//
// ⚠ **THE EXPORT IS ASSERTED, NOT ASSUMED.** When the register started paging,
// its export silently inherited the screen's fifty rows: a clerk would have
// exported a 38,000-row register and received a valid-looking file of fifty.
// No error, no gate, no test. `reportExportFilters()` below is a pure function
// precisely so that *"the file asks for every row"* is a case and not a habit.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  ONE TABLE COMPONENT, BECAUSE THERE WERE FOUR                            ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// P2.5's own line: *"the component, not a second implementation. Today the
// module has four different table implementations."* This file held one of
// them — a bespoke `ReportTable` over `PlainTable` with its own header, its own
// numeric alignment and its own footer, and no search, sort, pager or column
// chooser, because each of those would have had to be written a fifth time.
// `DataTable` has all four and 905 lines of decided behaviour behind them.
//
// ⚠ **THE TOOLBAR IS DRAWN FROM THE CODE AND NOT FROM THE RULE** (p025 note
// ⑤). `DataTable.tsx:324-328` records that the filter-chip rows were
// DELIBERATELY REMOVED after a PO review, and that row one — search, spacer,
// export, ▦ Columns — *"is the whole toolbar"*. So the definition's parameters
// sit in the bar ABOVE the KPI band, where the drawing puts them, and the
// toolbar is left exactly as the kit ships it.
//
// ⚠ **AND THE EXPORT CONTROL IS THE KIT'S 36×36 ICON WITH NO LABEL**
// (`DownloadButton.tsx:49-51`), not the labelled button the wireframe draws.
// Drawing the labelled one would launder a violation into something that looks
// shipped.
import type { ReactNode } from "react";
import { RefusedTotalCell } from "./RefusedTotalCell";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  flatReportParams,
  runReport,
  requestReportExport,
  isRefusedTotal,
} from "@/api/reportsEndpoints";
// ── CR-142-BRC07 Phase 5 · `P5.3` · the builder ──────────────────────────
import type {
  ReportColumnMeta,
  ReportQuery,
  ReportResponse,
  ReportRow,
  ReportQuantity,
  ReportGroupRow,
} from "@/api/reportsEndpoints";
import { getReportLibrary, isReportGroupRow } from "@/api/reportsEndpoints";
import { DataTable } from "@/components/DataTable";
import { defaultRequestState, isPageSize } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { DateCell, todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DownloadButton } from "@/components/DownloadButton";
import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { ScheduleDoor } from "./ScheduleDoor";
import { PermissionDenied } from "@/components/StateFrame";
import { AbsentPanel, REPORTS_PERMISSION, gapSentence } from "@/features/ledger/financeShared";
import { Dash, isDenied, useAccessCell, useRegional } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useToast } from "@/components/Toast";
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { useTenantPath } from "@/routing/tenantPath";

import {
  REPORTS_ROUTE,
  ReportGapList,
  ReportParamBar,
  editorRouteFor,
  isNotProducible,
  keyForSegment,
  moneyDisplay,
  percentDisplay,
  refusalReasonCode,
  reportWord,
  trimQuantity,
  unavailableSentence,
  viewerRouteFor,
} from "./reportsShared";
import { ServiceChips } from "@/components/ServiceChips";
import { ReportKpiBand } from "./ReportKpiBand";
import { ReportGrainLine } from "./ReportGrainLine";
import { ReportSubjectHead } from "./ReportSubjectHead";
import { ReportPrintButton } from "./ReportPrintButton";
import { ReportRequiredInputs } from "./ReportRequiredInput";
import { ReportServicesLine, uniformServices } from "./ReportServicesLine";
import { ReportParameters, REPORT_FILTERS, reportRunnable } from "./ReportParameters";
import { CountedGapList, isCountedGap, useDeclaredInputs } from "./ReportInputs";
import { GroupLabelCell, GroupSubtotalCell } from "./ReportGroupRow";
// ── CR-142-BRC07 Phase 2 · `P2.24` · drill down in place ─────────────────
import {
  groupDisclosureKey,
  openableGroups,
  toggleGroup,
  visibleRows,
} from "./ReportGroupRow";
import { reportLibraryQueryKey } from "./ReportLibraryPage";

import "@/features/ledger/finance.css";

export const reportQueryKey = (key: string, search: string) =>
  ["reports", "run", key, search] as const;

/** Columns whose cells are MONEY, per report. Named rather than sniffed from
 *  the value, because "247.87" and "684" are both decimal strings and only one
 *  of them wants a currency symbol (BR-SHL-023 — one money formatting path). */
export const MONEY_COLUMNS: Readonly<Record<string, readonly string[]>> = {
  // `d1_30` is `BR-REP-030`'s fifth band, served since `P2.21` — this report
  // folded it into `current` until 2026-09-24 (`DEF-REP-6659`).
  ar_aging: ["current", "d1_30", "d31_60", "d61_90", "d90_plus", "total"],
  billing_register: ["amount"],
  revenue_by_service_rate: ["usage_revenue", "base", "tax", "total"],
  payments_by_method: ["amount"],
  // ⚠ **`BR-REP-038` — WITHOUT THIS ROW THE STATEMENT PRINTS STORAGE WIDTH AT
  // A CLERK.** Money leaves a read model as its EXACT decimal string (hard rule
  // 2: stored to 4 decimals, DISPLAYED at 2), and a column this map does not
  // name is rendered as that string — photographed at 1440 before this line:
  // `137.700000`, `0`, `195.190000` down the CHARGE, PAYMENT and BALANCE
  // columns, under KPI tiles reading a correct `$470.59`. The tiles are money
  // because the payload says so; a CELL is money only because it is listed
  // here, which is one map away from a report being right about its totals and
  // wrong about every row.
  statement: ["charge", "payment", "running_balance"],
  // ⚠ **`BR-REP-039` — THE SAME FAULT AS THE ROW ABOVE, SHIPPED AGAIN THREE
  // DAYS LATER AND CAUGHT THE SAME WAY (`DEF-REP-6965`).** R34's money columns
  // were declared to the EXPORT — `exports.DISCONNECT_RECONNECT` marks both
  // `export_kernel.MONEY` — and the viewer does not read that, so `balance`
  // fell past the money branch and rendered `318.6000`, `2410.0000`,
  // `1204.5000` at a clerk while the OWED tile above them read a correct
  // `$12,173.10`. Photographed at 1440 by `10-scripts/p6w2_shots.mjs`; the
  // backend was right, all seven tests passed, and `tsc` and every gate were
  // green. **`paid` is here although it is always NULL** — it renders as a
  // dash today, and the day a payments seam fills it the column must not print
  // storage width for one release before anyone notices.
  disconnect_reconnect: ["balance", "paid"],
  // ⚠ **`BR-REP-034` / `DEF-REP-6937` — AND R43 DOES NOT DEPEND ON THIS LINE.**
  // The trend pack's viewer publishes `column_meta` for every money column it
  // derives (`queries.TREND_PACK_COLUMN_META`), and `ReportCell` checks the
  // dataset's own type BEFORE this map — so `revenue`, `target` and `collected`
  // render at two places whether or not they are listed here. It is listed
  // anyway, for one reason: this map is what `NUMERIC_COLUMNS` below is built
  // from, and a money column absent from both would be LEFT-aligned under a
  // right-aligned figure. It has shipped wrong twice on this framework already
  // (`DEF-REP-6965` on R34, the statement three days before it) and both times
  // it was found in a browser and by no test at all.
  trend_pack: ["revenue", "target", "collected"],
  // ── R27 (`P6.11` wave 4) ─────────────────────────────────────────────────
  // ⚠ **`remaining` IS EMPTY ON TWO OF THE THREE PROGRAMMES BY RIGHT** (p061
  // draws em-dashes against level pay and assistance) and is declared money
  // anyway — so the day one of those rows acquires a figure it cannot print
  // `1612.600000` for a release first. `DEF-REP-6965` has now cost this
  // framework three reports, every time found in a browser and never by a test.
  plans_and_discounts: ["instalment", "remaining"],
};

/** Right-aligned numeric columns — money plus the plain counts beside them. */
export const NUMERIC_COLUMNS: Readonly<Record<string, readonly string[]>> = {
  ar_aging: [...MONEY_COLUMNS.ar_aging, "days_late"],
  billing_register: [...MONEY_COLUMNS.billing_register],
  revenue_by_service_rate: [...MONEY_COLUMNS.revenue_by_service_rate, "accounts"],
  payments_by_method: [...MONEY_COLUMNS.payments_by_method, "count", "share_pct"],
  statement: [...MONEY_COLUMNS.statement],
  // `earlier_cases` is a COUNT and right-aligned with the money beside it. It
  // is deliberately NOT in `MONEY_COLUMNS`: it is how many previous times, and
  // a currency symbol on it would be a wrong answer rather than a wrong font.
  disconnect_reconnect: [...MONEY_COLUMNS.disconnect_reconnect, "earlier_cases"],
  // `rate` and `dso` are figures and `accounts`/`rebills` are counts; all four
  // are right-aligned with the money beside them and NONE is money. A currency
  // symbol on a number of DAYS would be a wrong answer rather than a wrong
  // font, which is why they are here and not one map up.
  trend_pack: [...MONEY_COLUMNS.trend_pack, "rate", "dso", "accounts", "rebills"],
  // ── R4 (`P6.11` wave 4) ──────────────────────────────────────────────────
  // ⚠ **R4 HAS NO MONEY COLUMN AT ALL AND IS THEREFORE ABSENT FROM
  // `MONEY_COLUMNS` ABOVE, ON PURPOSE.** It lists the accounts the run could
  // NOT draft; a currency symbol anywhere on it would be a wrong answer rather
  // than a wrong font. `usage` is a QUANTITY and is right-aligned here so that
  // the day `OQ-REP-12768` fills it, it is not LEFT-aligned under the figures
  // beside it for one release before anyone notices — which is exactly how
  // `DEF-REP-6965` reached a clerk on R34.
  bill_run_readiness: ["usage"],
  // `terms_months` is a COUNT and `terms_percent` a FIGURE; both are
  // right-aligned with the money beside them and NEITHER is money. A currency
  // symbol on a number of months would be a wrong answer rather than a wrong font.
  plans_and_discounts: [
    ...MONEY_COLUMNS.plans_and_discounts,
    "terms_months",
    "terms_percent",
  ],
};

export { REPORT_FILTERS };

/** The run controls the RUNNER reads bare (`runner._RUN_CONTROLS`), as opposed
 *  to the `f.<name>` list filters. Named once so the two halves of the URL
 *  round trip below cannot disagree about which is which — `DEF-131`'s shape. */
const BARE_PARAMS = [
  "q",
  "sort",
  "dir",
  "page",
  "per",
  "group_by",
  "columns",
  // `BR-REP-038` — see `ReportQuery.subject` for why these are bare and for
  // what the screen looked like before they were read.
  "subject",
  "subject_id",
];

/** The fixed list filters `ReportQuery` names — `f.<name>` in the URL. */
const FILTER_PARAMS = ["from", "to", "bill_type", "service", "purpose", "class"] as const;

/** The bare run controls the URL carries back (`per` never — see below). */
const BARE_READ = [
  "q",
  "sort",
  "dir",
  "page",
  "group_by",
  "columns",
  "subject",
  "subject_id",
] as const;

type FixedParam = (typeof FILTER_PARAMS)[number] | (typeof BARE_READ)[number];

/**
 * ⚠ **A RUN'S FLAT PARAMETERS BACK INTO A QUERY — THE INVERSE OF
 * `flatReportParams`** (`CR-179-BRC10`, PO 2026-10-12: history's *Open in
 * report*). A run is recorded with every parameter BARE, so the fixed names
 * go back where `ReportQuery` keeps them and EVERY OTHER NAME is a declared
 * input — no report's input names are listed here. `page` and `per` are
 * dropped: a re-opened report starts at its first page.
 */
export function queryFromRunParams(params: Readonly<Record<string, unknown>>): ReportQuery {
  const query: ReportQuery = {};
  const inputs: Record<string, string> = {};
  const fixed = new Set<string>([...FILTER_PARAMS, ...BARE_READ]);
  for (const [name, raw] of Object.entries(params)) {
    if (raw === null || raw === undefined || name === "page" || name === "per") continue;
    const value = String(raw);
    if (value === "") continue;
    if (fixed.has(name)) {
      query[name as FixedParam] = value;
    } else {
      inputs[name] = value;
    }
  }
  if (Object.keys(inputs).length > 0) query.inputs = inputs;
  return query;
}

export function paramsFrom(search: URLSearchParams): ReportQuery {
  const query: ReportQuery = {};
  for (const name of FILTER_PARAMS) {
    const value = search.get(`f.${name}`);
    if (value !== null && value !== "") {
      query[name] = value;
    }
  }
  // ⚠ `per` is deliberately NOT read from the URL. The page size is the kit's,
  // and a hand-edited `?per=40000` is the row cap coming back in through the
  // front door — `NFR-5` forbids a ceiling, it does not invite one.
  // ⚠ **`group_by` JOINS THE BARE FOUR WITH `P2.17`.** Without it the levels
  // never leave the browser: the screen rebuilds its request from THIS
  // function, so a `?group_by=` a clerk or a bookmark carries would be dropped
  // silently and the report would answer the ungrouped question under a URL
  // that says otherwise. Measured on the running product before it was added —
  // the screen requested `/api/{tenant}/reports/ar_aging` with no `group_by`
  // at all while the address bar carried one.
  // ⚠ `columns` JOINS THE BARE SET WITH `P5.3`, for exactly the reason
  // `group_by` did: the screen rebuilds its request from THIS function, so a
  // ticked column list that is not read here never leaves the browser and the
  // table answers the old question under a URL that says otherwise.
  // ⚠ **`subject` AND `subject_id` JOIN THE BARE SET WITH `BR-REP-038`**, for
  // exactly the reason `group_by` and `columns` each did: the screen rebuilds
  // its request from THIS function, so a subject the URL carries and this loop
  // does not read never leaves the browser. Measured in a browser at 1440
  // before they were added — `/reports/statement?subject_id=<uuid>` drew four
  // empty tiles reading *Choose an account first* over a URL naming an account.
  for (const name of BARE_READ) {
    const value = search.get(name);
    if (value !== null && value !== "") {
      query[name] = value;
    }
  }
  // ⚠ **`CR-179-BRC10` — EVERY `in.<param>` IS A SERVER-DECLARED INPUT, READ
  // WITHOUT KNOWING ITS NAME.** The response that declares the inputs arrives
  // after this function runs, so it cannot be asked which names to read; the
  // prefix is what says *this one is a declared input*. A report link
  // therefore reopens with its inputs, and no report's names are written here.
  const inputs: Record<string, string> = {};
  for (const [name, value] of search.entries()) {
    if (name.startsWith(INPUT_PREFIX) && name.length > INPUT_PREFIX.length && value !== "") {
      inputs[name.slice(INPUT_PREFIX.length)] = value;
    }
  }
  if (Object.keys(inputs).length > 0) {
    query.inputs = inputs;
  }
  return query;
}

/** The URL prefix of a server-declared input (`controls.inputs`). */
export const INPUT_PREFIX = "in.";

export function searchFrom(query: ReportQuery): URLSearchParams {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(query)) {
    if (name === "inputs") continue;
    if (value !== undefined && value !== "") {
      search.set(BARE_PARAMS.includes(name) ? name : `f.${name}`, String(value));
    }
  }
  for (const [name, value] of Object.entries(query.inputs ?? {})) {
    if (value !== "") {
      search.set(`${INPUT_PREFIX}${name}`, value);
    }
  }
  return search;
}

/**
 * The filters an EXPORT of this report carries.
 *
 * ⚠ **IT DROPS THE PAGE AND KEEPS EVERYTHING ELSE, AND THAT IS THE WHOLE
 * POINT** (§8.2, p091). A file is the whole FILTERED set: the clerk's search,
 * their class, their window and their sort all travel, and `page` does not —
 * because a file made of page three is not a smaller file, it is a wrong one.
 *
 * Pure and exported so the case can be written. When the billing register
 * started paging, its export silently inherited the screen's fifty rows and
 * nothing anywhere went red.
 */
/**
 * The unit a quantity or count column names through `unit_from`, read off the
 * row — but only when that unit column is not itself one of the drawn columns,
 * so a report that already shows its unit beside the figure is untouched.
 */
export function servedUnit(
  report: ReportResponse | undefined,
  row: ReportRow,
  column: string,
): string | undefined {
  const from = report?.column_meta?.[column]?.unit_from;
  if (from === undefined || from === null || (report?.columns ?? []).includes(from)) {
    return undefined;
  }
  const unit = row[from];
  return typeof unit === "string" && unit !== "" ? unit : undefined;
}

export function reportExportFilters(query: ReportQuery): Record<string, string> {
  const filters: Record<string, string> = {};
  // Declared inputs are flattened in BARE, exactly as the run sends them.
  for (const [name, value] of Object.entries(flatReportParams(query))) {
    if (value !== undefined && value !== "" && name !== "page" && name !== "per") {
      filters[name] = String(value);
    }
  }
  return filters;
}

/**
 * A money figure WITH its currency code, or the bare decimal when the report
 * could not derive one.
 *
 * DEF-081 / DEF-099: a money figure never wears a currency code it did not come
 * from. When a window holds bills in two currencies the read model serves
 * `currency: null` — the per-row amounts are still real, so they are shown, and
 * the missing footer says why underneath. Formatting them with the tenant's
 * DECLARED code would print a wrong symbol on a customer's money.
 */
export function AmountCell(props: {
  amount: string;
  currency: string | null;
  basis?: ReportResponse["basis"];
  locale?: string;
}) {
  if (props.currency === null) {
    // ⚠ **NO CODE, BUT STILL TWO DECIMALS** (`DEF-REP-6902`). This branch is
    // `DEF-081`/`DEF-099`: a window holding two currencies serves
    // `currency: null`, the amounts are real, and formatting them with the
    // tenant's DECLARED code would print a wrong symbol on a customer's money.
    // It said nothing about PRECISION, so every money figure on a report with
    // no derivable currency reached the screen at storage width — the tax
    // remittance printed `531.140000` in its cell, its footer AND its tile,
    // all three, after every other money column in the product had been fixed.
    // CLAUDE.md hard rule 2 is about the number of digits a person reads and
    // is not conditional on a currency code being available.
    return <span className="cell-money">{moneyDisplay(props.amount)}</span>;
  }
  return (
    <MoneyCell
      amount={props.amount}
      currency={props.currency}
      basis={props.basis}
      locale={props.locale}
    />
  );
}

// ── One cell ──────────────────────────────────────────────────────────────

/**
 * A QUANTITY OR A COUNT AS A PERSON READS IT — `114,500 kWh`, `1,100`.
 *
 * The walk of 2026-10-12 (`CR-179-BRC10`) read `114500 kWh` with the unit
 * wrapped onto a second line, and a group's ACCOUNTS `1100`. The whole part
 * takes the locale's grouping; the fraction is `trimQuantity`'s — trailing
 * zeros dropped and NOTHING ROUNDED (`DEF-REP-6903`: a demand of `0.125`
 * reads `0.125`). Done on the STRING, never through a float (hard rule 2's
 * reasoning: a `NUMERIC(18,6)` can exceed a double). Anything that is not a
 * plain decimal string comes back as it arrived.
 */
export function quantityText(value: string, locale?: string): string {
  const trimmed = trimQuantity(value);
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(trimmed);
  if (match === null) return trimmed;
  const format = new Intl.NumberFormat(locale ?? "en-US");
  const whole = format.format(BigInt(match[2]));
  if (match[3] === undefined) return `${match[1]}${whole}`;
  const point = format.formatToParts(1.5).find((part) => part.type === "decimal")?.value ?? ".";
  return `${match[1]}${whole}${point}${match[3]}`;
}

export function countText(value: string, locale?: string): string {
  return /^-?\d+$/.test(value) ? quantityText(value, locale) : value;
}

/** The figure and its unit on ONE line — the unit never wraps away from it. */
function WithUnit(props: { figure: string; unit: string }) {
  return (
    <span className="whitespace-nowrap">
      {props.figure}
      {props.unit}
    </span>
  );
}

function isQuantityList(value: unknown): value is ReportQuantity[] {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === "object" && entry !== null && "quantity" in entry && "unit" in entry,
    )
  );
}

export function ReportCell(props: {
  reportKey: string;
  column: string;
  value: ReportRow[string];
  currency: string | null;
  /** ⚠ **WHAT KIND OF THING THIS COLUMN IS, FROM THE DATASET THAT DECLARES
   *  IT** (`DEF-REP-6902` · `DEF-REP-6903`). Optional because three viewers
   *  answer through their own read models and declare none; where it is absent
   *  this cell behaves exactly as it did before, which is what keeps the
   *  forty-six that were already right from moving. */
  meta?: ReportColumnMeta;
  /** ⚠ **THE UNIT A `unit_from` COLUMN NAMES, WHEN THAT COLUMN IS NOT DRAWN
   *  ON ITS OWN** (`CR-179-BRC10`, hard rule 3) — `66,000 kgal`, `820 carts`.
   *  Absent renders exactly what every existing report rendered. */
  unit?: string;
  t: Translator;
  locale?: string;
  // `P6.11` — REQUIRED by the timestamp branch below, and required rather than
  // optional on purpose: the compiler then names every call site that has to
  // decide, instead of one of them silently printing a UTC instant in a
  // tenant that keeps its books in Boise.
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { value, t } = props;
  const unitSuffix = props.unit === undefined || props.unit === "" ? "" : ` ${props.unit}`;
  if (value === null || value === "") {
    return <Dash />;
  }
  if (isQuantityList(value)) {
    // CLAUDE.md rule 3 — the unit is rendered WITH the number, and two units on
    // one bill stay two figures. They are never added.
    const shown = measuresWorthShowing(value);
    if (shown.length === 0) {
      return <Dash />;
    }
    return (
      <>
        {shown.map((entry, index) => (
          <span key={`${entry.unit}`}>
            {index > 0 ? " · " : ""}
            {/* `DEF-REP-6903` — `684.000000 kWh` is not a reading anybody
                takes. See `trimQuantity`: it drops trailing zeros and rounds
                nothing. */}
            {trimQuantity(entry.quantity)} {entry.unit}
          </span>
        ))}
      </>
    );
  }
  // ── `DEF-REP-7010` · A SERVICE LIST IS CHIPS, NOT WORDS JOINED BY DOTS ────
  //
  // ⚠ **THE COLUMN NAME DECIDES, AND IT IS THE ONLY LIST IN THIS FILE.** The
  // dataset types `services` as `text`, so the meta branch above cannot tell
  // a service set from any other array — `SERVICE_COLUMNS` is the same shape
  // as `VOCABULARY_COLUMNS` beneath it and for the same reason. It names
  // COLUMNS and holds NO service codes, so an eleventh — or twelfth — service
  // needs nothing here (the skill's §12; hard-won law 2's silent failure).
  // Serving `services` as its own dataset TYPE would make this one decision
  // for all forty-six reports at once and is `DEF-REP-7014`.
  if (SERVICE_COLUMNS.has(props.column) && Array.isArray(value)) {
    return <ServiceChips services={value.map(String)} t={t} />;
  }
  if (Array.isArray(value)) {
    return <>{value.join(" · ")}</>;
  }
  // ── `DEF-REP-6902` / `DEF-REP-6903` · THE COLUMN SAYS WHAT KIND IT IS ─────
  //
  // ⚠ **THIS BRANCH IS WHY THE FIX IS ONE DECISION AND NOT THIRTY-THREE.** The
  // map below names FIVE reports; the dataset declares a type for every column
  // of all forty-six, so money is money, a percentage is a percentage and a
  // quantity is a quantity on every report at once — including the ones that
  // do not exist yet, which is the half a hand-typed map can never buy.
  //
  // ⚠ **IT IS CHECKED BEFORE `MONEY_COLUMNS` AND THAT ORDER IS DELIBERATE.**
  // The map is kept, not deleted: the three ledger-owned viewers answer through
  // their own read models and declare no dataset columns, so it is still the
  // only answer for them. Where both speak they agree — asserted in
  // `reportCentre.test.tsx` rather than left to be believed (hard-won law 1).
  if (props.meta !== undefined && typeof value !== "boolean") {
    if (props.meta.type === "money") {
      return (
        <AmountCell amount={String(value)} currency={props.currency} locale={props.locale} />
      );
    }
    if (props.meta.type === "percent") {
      return <>{percentDisplay(value as string | number)}</>;
    }
    if (props.meta.type === "quantity") {
      return <WithUnit figure={quantityText(String(value), props.locale)} unit={unitSuffix} />;
    }
    if (props.meta.type === "count") {
      return <WithUnit figure={countText(String(value), props.locale)} unit={unitSuffix} />;
    }
  }
  if ((MONEY_COLUMNS[props.reportKey] ?? []).includes(props.column)) {
    return <AmountCell amount={String(value)} currency={props.currency} locale={props.locale} />;
  }
  // ⚠ **`P6.11` ADDS SIX COLUMNS TO THIS BRANCH, AND THE REASON IS ON A
  // SCREENSHOT.** R32 rendered `manual`, `walk_by` and `posted` — the stored
  // vocabulary codes — in front of a clerk, and R23 rendered `opened` and
  // `transferred_in`. They are live vocabularies exactly as `bill_type` is, so
  // they take the same path: the tenant's own word where a catalogue holds one,
  // the code itself where it does not, and never silently dropped.
  if (VOCABULARY_COLUMNS.has(props.column)) {
    // A live vocabulary VALUE, rendered in the tenant's language and shown raw
    // when the catalogue has no word for it — never silently dropped.
    const branded = brandedReadMethod(props.column, String(value));
    if (branded !== null) {
      // ⚠ **`BR-REP-045` — A MANUFACTURER IS DATA, NEVER VOCABULARY.** The
      // words are translated; the company name is printed beside them as the
      // value it is. See `brandedReadMethod` for why there is no list here.
      return (
        <>
          {t(`reports.value.${props.column}.${branded.method}`, { defaultValue: branded.method })}
          {" · "}
          {branded.manufacturer}
        </>
      );
    }
    return (
      <>{t(`reports.value.${props.column}.${String(value)}`, { defaultValue: String(value) })}</>
    );
  }
  if (props.column === "flag") {
    return (
      <StatusPill tone="warning">
        {t(`reports.flag.${String(value)}`, { defaultValue: String(value) })}
      </StatusPill>
    );
  }
  if (props.column === "share_pct") {
    return <>{String(value)}%</>;
  }
  // ── `P6.11` · A BOOLEAN IS A WORD, NEVER `true` ───────────────────────────
  // ⚠ **R36's APPROVES MONEY IS THE FIRST BOOLEAN ANY REPORT HAS SERVED**, and
  // until this branch existed the column rendered the literal `true` and
  // `false` in front of a compliance officer — found by photographing the
  // screen, not by any test (hard-won law 6). Decided by TYPE rather than by
  // column name, so it is right for every boolean a later report serves and
  // adds no seventh hand-typed column map (`P0.7` deleted six).
  if (typeof value === "boolean") {
    return <>{t(value ? "reports.value.yes" : "reports.value.no")}</>;
  }
  // ── `P6.11` · AN ISO TIMESTAMP IS NOT A DATE A CLERK READS ────────────────
  // ⚠ **`2026-09-27T12:32:27.923853+00:00` REACHED THE SCREEN.** R36's LAST
  // ACTIVE is the first TIMESTAMP column any report has served — every other
  // date column is a calendar date — and microseconds with a UTC offset on
  // them are not a date.
  //
  // ⚠ **THE MATCH IS DELIBERATELY NARROW: A TIMESTAMP, NEVER A PLAIN
  // `YYYY-MM-DD`.** Calendar dates render as stored on every one of the 46
  // reports today. Routing them through `DateCell` as well would change how
  // every report prints a date, product-wide, on one lane's authority — which
  // is the thing B14 rule 44's own reasoning warns about. It is REPORTED
  // instead, so somebody can decide it for all 46 at once.
  if (typeof value === "string" && ISO_TIMESTAMP.test(value)) {
    return (
      <DateCell value={value} timeZone={props.timeZone} dateFormat={props.dateFormat} withTime />
    );
  }
  return <>{String(value)}</>;
}

/**
 * A stored read-method code that carries a MANUFACTURER after its method, split
 * into the part that is words and the part that is a company's name.
 *
 * ⚠ **`BR-REP-045`, ruled by the PO on 2026-09-27: a brand name never enters a
 * translatable value.** `ami_itron` and `ami_sensus` were catalogue VALUES —
 * `AMI · Itron` and `AMI · Sensus`, identical in all eleven languages, and
 * correctly so, because *Itron* and *Sensus* are companies. `G15` counted all
 * twenty non-English copies as untranslated (`DEF-REP-6931`).
 *
 * ⚠ **AND THERE IS DELIBERATELY NO LIST OF MANUFACTURERS HERE.** The PO was
 * offered the obvious alternative — naming the two values in the translation
 * check's hand-curated exception list — and refused it, in as many words:
 * somebody would have to remember to edit that list the day a utility buys from
 * a third manufacturer, and nothing would remind them. So the name is taken
 * from the stored code itself and capitalised. `ami_badger` reads
 * **AMI feed · Badger** on the day it first arrives, with nothing edited
 * anywhere — which is the whole difference between data and vocabulary.
 *
 * The method half IS vocabulary and stays in the catalogues: `ami` is
 * *AMI feed* in English, *Flux AMI* in French, *AMI-Datenstrom* in German —
 * the same words `metering.reads.sourceDetail.*` already uses for this concept
 * (B14 rule 34), minus the brand.
 */
const BRANDED_METHODS = ["ami"];

/**
 * ⚠ **ONE COLUMN, BY NAME, AND THE REASON IS A REAL VALUE ONE COLUMN OVER.**
 * `source_kind` stores `ami_replay`, whose second half is not a company — it is
 * how the read arrived. Split generically across every vocabulary column it
 * would render **AMI feed · Replay**, inventing a manufacturer out of a word.
 * `source_detail` is the only column whose values name a maker, so it is the
 * only column this applies to. A second such column is one line here and a
 * catalogue key, deliberately, because that is a change somebody makes on
 * purpose rather than one that happens to them.
 */
const BRANDED_COLUMNS = new Set(["source_detail"]);

function brandedReadMethod(
  column: string,
  code: string,
): { method: string; manufacturer: string } | null {
  if (!BRANDED_COLUMNS.has(column)) return null;
  for (const method of BRANDED_METHODS) {
    const prefix = `${method}_`;
    if (code.startsWith(prefix) && code.length > prefix.length) {
      const stored = code.slice(prefix.length);
      return { method, manufacturer: stored.charAt(0).toUpperCase() + stored.slice(1) };
    }
  }
  return null;
}

/**
 * **WHICH OF THIS BILL'S MEASURES ARE WORTH A CLERK'S EYES** (`DEF-REP-7010`).
 *
 * ⚠ **THE PRODUCT OWNER'S RULE, AND IT IS A RULE ABOUT TWO KINDS OF ZERO:**
 * *"Show only what was actually used… A zero that MEANS something (a meter
 * read of zero) is not the same as a measure that does not apply — do not
 * collapse the two."*
 *
 * The live register drew **`0 cart · 0 connection · 0 kW · 15.2 kgal`** on
 * every row: three zeros and one figure, and a clerk reading four numbers to
 * find the one that moved. `0 cart` is a COUNT of the unit's assets
 * (`BR-RAT-090`) and says *nobody has a cart here*; `0 kgal` is a meter that
 * was read and read zero, which is news. Both are `"0"` on the wire.
 *
 * ⚠ **SO THE DECIDER IS `measured`, WHICH ONLY THE READ MODEL CAN SET**, and
 * a zero is dropped ONLY when the server has said it is a count. A screen
 * sniffing the UNIT instead would be a hand-typed list and would be wrong the
 * first time a utility called its carts something else.
 *
 * ⚠ **AN ABSENT `measured` KEEPS THE FIGURE.** Every report served before
 * this flag existed, and every deployment whose tenancy lane declares no
 * capacity basis, renders byte-for-byte what it rendered yesterday.
 *
 * ⚠ **A NON-ZERO COUNT STAYS.** `1 cart` is exactly what the bill charged
 * for; only the count of NOTHING is noise.
 *
 * Pure and exported, so both halves of the PO's sentence are a property with
 * a test rather than a thing somebody looked at once.
 */
export function measuresWorthShowing(
  entries: readonly ReportQuantity[],
): readonly ReportQuantity[] {
  return entries.filter(
    (entry) => entry.measured !== false || Number(entry.quantity) !== 0,
  );
}

/**
 * The columns whose value is a list of SERVICE CODES (`DEF-REP-7010`).
 *
 * ⚠ **IT NAMES COLUMNS AND HOLDS NO SERVICE CODES, WHICH IS THE WHOLE POINT.**
 * Adding a twelfth service to the platform needs no edit here, in
 * `ServiceChips`, or anywhere else on this path — the skill's §12 and
 * hard-won law 2, where the front end typed the eleven out by hand in two
 * places and an eleventh service failed in silence.
 */
const SERVICE_COLUMNS = new Set(["services"]);

/**
 * The columns whose VALUE is a stored vocabulary code rather than free text.
 * A code not in the catalogues renders as itself, which is the established
 * posture: a value we have no word for is shown, never dropped.
 */
const VOCABULARY_COLUMNS = new Set([
  "bill_type",
  "purpose",
  "source_kind",
  "source_detail",
  "read_method",
  "status",
  "event",
  "premises_absence",
  // `CR-184-BRC10` — the class row a line naming no service lands on
  // (`taxes`, `fees`, `usage_base`, `tenant_defined`, `other`).
  "charge_class",
  // ⚠ **`DEF-REP-6903` — THE CLOSE PACK'S TIE-OUT NAMES.** Its CHECK column
  // read `accounts_receivable`, `deposit_liability`, `tax_payable` and
  // `cost_of_service` in front of a bookkeeper: four stored codes, a closed
  // vocabulary of exactly four, and no words anywhere. They are
  // `reports.value.check.*` in all eleven catalogues now.
  "check",
]);

/**
 * A full ISO INSTANT — a date, a `T`, and a time. A plain `YYYY-MM-DD` does
 * NOT match, and that is the point: see `ReportCell` for why.
 */
const ISO_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

/**
 * The columns of one report, as a `TableConfig`.
 *
 * ⚠ **`sortable` IS THE SERVER'S ANSWER AND NEVER THIS FILE'S GUESS** (`P2.2`).
 * A caret over a column the query does not order by is hard-won law 2's mirror
 * — a live screen behind a dead control — and the account ledger DECLINES sort
 * on purpose, because ordering a running balance by amount destroys the column.
 * A report that declares no `controls` gets no carets and no search box at all.
 *
 * ⚠ **AND NO COLUMN IS `identity`.** `identity` locks a column against the
 * chooser, and it carries the claim that the cell is a LINK to the record. A
 * report row is inert text today (p027: *"a row opens its record in the owning
 * module (NEW; today a row is inert text)"*), so declaring one would be a
 * promise the cell does not keep.
 */
export function reportTableConfig(
  report: ReportResponse | undefined,
  reportKey: string,
  t: Translator,
  renderCell: (row: ReportRow | ReportGroupRow, column: string) => ReactNode,
  /**
   * ⚠ **COLUMNS THE SCREEN HAS SAID ONCE, ABOVE THE TABLE** (`DEF-REP-7010`).
   *
   * Empty for every report and every caller that passes nothing, so the table
   * is byte-for-byte what it was. The ONE thing that goes in here today is a
   * `services` column whose every row is identical — the PO's own rule, and
   * see `ReportServicesLine` for why the same report is two different screens
   * depending on its data.
   *
   * ⚠ **THE COLUMN IS NOT DELETED FROM THE REPORT — IT IS MOVED.** The fact
   * is still on screen, the export still carries the column (a file is the
   * whole filtered set and is not built from this config), and a report whose
   * rows differ still draws it per row.
   */
  omitColumns: readonly string[] = [],
): TableConfig<ReportRow | ReportGroupRow> {
  const columns = (report?.columns ?? []).filter((column) => !omitColumns.includes(column));
  const sorts = report?.controls?.sorts ?? [];
  return {
    // BR-SHL-013 — the stored column choice is PER REPORT, not per screen: a
    // clerk who hides *Class* on the ageing has said nothing at all about the
    // billing register, and one key for all forty-six would make every report
    // inherit the last one's shape.
    screenId: `S46.${reportKey}`,
    columns: columns.map((column) => ({
      key: column,
      // ⚠ **ONE FUNCTION, SHARED WITH SCREEN 2·2** (`DEF-REP-7070`). This
      // expression WAS the naming path and the editor could only have had
      // words by writing it a second time — which is how a heading and its own
      // checkbox come to disagree. `reportWord` also falls through to the
      // parameter catalogue, which a column name never needed and a filter
      // name always did.
      label: reportWord(column, t),
      sortable: sorts.includes(column),
      cell: (row: ReportRow | ReportGroupRow) => renderCell(row, column),
    })),
    // ⚠ **B14 rule 31 — NO DATABASE ID IS EVER VISIBLE, AND THIS IS NOT ONE.**
    // `getRowId` feeds React keys and the expanded-row set; it is never drawn.
    // ⚠ **A GROUP ROW HAS NO RECORD ID AND MUST NOT SHARE ONE** (`P2.18`). Every
    // fact row's id comes from its record; a subtotal has none, so without this
    // branch every group row on a page would return the same empty string,
    // React would collapse them onto one key, and a report grouped to three
    // levels would draw one subtotal where it should draw a dozen.
    // B14 rule 31 is untouched: `getRowId` feeds keys and is never drawn.
    getRowId: (row: ReportRow | ReportGroupRow) => {
      // ⚠ **THE SAME STRING `P2.24`'s OPEN SET USES, FROM ONE FUNCTION.** The
      // React key and the open/closed key must never drift apart, or a clerk
      // opens one group and a different one redraws.
      if (isReportGroupRow(row)) return groupDisclosureKey(row);
      const fact = row as ReportRow;
      return String(
        fact.invoice_id ?? fact.account_id ?? fact.payment_id ?? fact.service_id ?? "",
      );
    },
    searchFields: report?.controls?.searchable === true ? [...columns] : undefined,
    // B14 rule 19 — a list's search box says WHAT it matches, and the generic
    // *Search this list* says nothing. It is ONE key rather than forty-six,
    // deliberately: the columns a report searches are the DATASET's declared
    // searchable ones and they differ per report, so a per-report sentence
    // would be forty-six strings in eleven catalogues that no lane can keep
    // true. *Search this report* is what this box honestly is.
    searchPlaceholder: "reports.search.placeholder",
    defaultSort: {
      sort: report?.controls?.sort ?? "",
      dir: report?.controls?.dir ?? "asc",
    },
  };
}

/**
 * WHAT THE PAGER IS COUNTING (`DEF-REP-6891`).
 *
 * ⚠ **`page.total` IS A COUNT OF *FACT* ROWS AND A COLLAPSED ANSWER SERVES
 * *GROUP* ROWS.** Walked at 1440 on the trend pack grouped three deep: the
 * table drew **three lines under "1–36 of 36"**. The two numbers were each
 * correct about a different thing and nothing compared them —
 * `DEF-REP-6875` fixed the same mismatch inside the SUBTOTALS a week earlier
 * and nobody asked the question about the pager.
 *
 * ⚠ **AND THERE IS NO PAGE TO TURN ON A COLLAPSED ANSWER.** Every group's Σ
 * covers the WHOLE filtered set — that is what `collapsed` means — so the rows
 * served are all of them and their own count is both the honest number and the
 * complete one.
 *
 * ⚠ **THE UNCOLLAPSED PATH IS UNTOUCHED AND MUST BE.** `ar_aging` interleaves
 * FACT rows, so `page.total` and the rows on screen are the same kind of thing
 * and the pager has to go on describing the REPORT: defaulting it to
 * `rows.length` would print "1–50 of 50" over a receivable of any size, which
 * is the defect this one is the mirror of.
 *
 * ⚠ **`null` UNTIL THE SERVER SAYS, AND `rows.length` ONLY WHERE THE REPORT
 * DOES NOT PAGE.** A report with no `page` member is saying *this is all of
 * it* — never *page one*.
 *
 * A pure function, exported, because it is arithmetic and deserves a test that
 * does not mount a router — the reason `ReportTotalsRow` is a component.
 */
export function pagerTotal(report: ReportResponse | undefined): number | null {
  if (report === undefined) return null;
  if (report.collapsed === true) return report.rows.length;
  return report.page?.total ?? report.rows.length;
}

/**
 * The totals row, under the page of rows.
 *
 * ⚠ **IT IS THE SERVER'S `totals` AND NEVER A SUM OF `rows` — AND PAGING IS
 * WHAT MAKES THAT MATTER NOW.** Before `P2.1` the screen held every row, so a
 * browser-side sum would at least have footed to what was on screen. It holds
 * FIFTY rows now, so a summed footer would print the total of page one under a
 * report of 38,412 — a number that is wrong, plausible, and different on every
 * page. The case that catches it renders two rows against a three-row total.
 *
 * ⚠ **IT TAKES THE VISIBLE COLUMNS, IN ORDER** (`P2.5`). The column chooser
 * moves them, and a footer built from the declared set puts its figures under
 * the wrong headings the moment a clerk hides one.
 *
 * A component rather than a closure inside the page: B14 rule 43, and because
 * *"the screen computes nothing"* is the single most important property of this
 * module and it deserves a test that does not mount a router.
 */
export function ReportTotalsRow(props: {
  reportKey: string;
  columns: readonly string[];
  totals: ReportResponse["totals"];
  currency: string | null;
  /** ⚠ **WHAT KIND EACH COLUMN IS** (`DEF-REP-6902`). The footer is the
   *  surface the defect was photographed on: `15816.000000` sat directly under
   *  a tile reading `$15,816.00` for the same figure, so the number a finance
   *  officer quoted depended on where on the screen they looked. */
  columnMeta?: Record<string, ReportColumnMeta>;
  t: Translator;
  locale?: string;
}) {
  const numeric = NUMERIC_COLUMNS[props.reportKey] ?? [];
  const money = MONEY_COLUMNS[props.reportKey] ?? [];
  // ⚠ **THE REASON IS SAID ONCE PER ROW, NOT ONCE PER CELL (B14 rule 32).**
  // Walked on the running product at 1440: the ageing grouped by month refuses
  // SIX money columns for the same reason, and a per-cell sentence printed
  // *Balances do not sum across time* six times across one row, wrapping to
  // three lines in each — a footer taller than eight rows of data. Rule 32
  // gives a screen a description budget of one sentence per section, and six
  // copies of one sentence is what it exists to stop.
  //
  // ⚠ **DISTINCT reasons, not "the first one".** A footer can refuse two
  // columns for two different reasons — a balance across time beside a DSO
  // that may never be averaged — and collapsing those to one sentence would
  // state something false about one of them.
  const reasons: string[] = [];
  for (const column of props.columns) {
    const total = props.totals[column];
    if (!isRefusedTotal(total)) continue;
    const key = `reports.totals.${total.reason_code}`;
    const sentence = props.t(key) === key ? total.reason : props.t(key);
    if (!reasons.includes(sentence)) reasons.push(sentence);
  }
  return (
    <tr className="fin-total-row">
      {props.columns.map((column, index) => {
        const cellClass = numeric.includes(column) ? "fin-num" : undefined;
        if (index === 0) {
          return (
            <td key={column}>
              {props.t("reports.totals")}
              {reasons.length === 0 ? null : (
                <span className="mt-1 block text-xs font-normal text-neutral-600">
                  {reasons.join(" · ")}
                </span>
              )}
            </td>
          );
        }
        const total = props.totals[column];
        if (total === undefined || total === null) {
          return <td key={column} className={cellClass} />;
        }
        // ⚠ **`P2.22` — A TOTAL THAT MAY NOT BE SUMMED NEVER REACHES
        // `AmountCell`.** It is checked FIRST, before the money branch,
        // because `String(total)` on the refusal object renders
        // `[object Object]` and `AmountCell` would parse it to `NaN` — two
        // ways of putting something that is not a number on screen while
        // still not saying WHY, which is the one thing p85 forbids.
        if (isRefusedTotal(total)) {
          return (
            <td key={column} className={cellClass}>
              {/* The em-dash alone HERE; the reason is on the row's label cell
                  above, once per distinct reason. `RefusedTotalCell` still
                  renders both together and is what a GROUP SUBTOTAL uses,
                  where there is one cell and no row to hang a sentence on. */}
              <RefusedTotalCell total={total} t={props.t} showReason={false} />
            </td>
          );
        }
        // ⚠ **THE DATASET'S OWN TYPE FIRST, THE HAND-TYPED MAP SECOND** —
        // the same precedence, in the same order, as `ReportCell`. The map
        // names five reports; the trend pack, the account census and the
        // close pack are not among them, which is exactly why their footers
        // printed storage width.
        const kind = props.columnMeta?.[column]?.type;
        const isMoney = kind === "money" || (kind === undefined && money.includes(column));
        return (
          <td key={column} className={cellClass}>
            {isMoney ? (
              <AmountCell
                amount={String(total)}
                currency={props.currency}
                locale={props.locale}
              />
            ) : kind === "percent" ? (
              percentDisplay(total as string | number)
            ) : kind === "quantity" ? (
              quantityText(String(total), props.locale)
            ) : kind === "count" ? (
              countText(String(total), props.locale)
            ) : (
              String(total)
            )}
          </td>
        );
      })}
    </tr>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface ReportViewerPageProps {
  client?: ApiClient; // test seam
  locale?: string;
  /** Test seam: the route param, when this page is rendered without a router
   *  path. Production always takes it from the URL. */
  reportKey?: string;
  /** Test seam: the tenant's zone, when no shell has published one. */
  timeZone?: string;
  /** Test seam: today in the tenant's zone. Production derives it from the
   *  published zone, never from the browser's clock. */
  today?: string;
}

export function ReportViewerPage(props: ReportViewerPageProps) {
  const { t } = useTranslation();
  // Stable across renders (it changes only when `t` does), so the table
  // config below can list it as a dependency without rebuilding every render.
  const translate: Translator = useCallback((key, params) => t(key, params), [t]);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const routeParams = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);
  const today = props.today ?? todayInZone(timeZone);

  const key = props.reportKey ?? keyForSegment(routeParams.reportKey ?? "");
  const query = paramsFrom(searchParams);
  const cell = useAccessCell(REPORTS_PERMISSION, client);

  // ── PO ruling 2026-09-28 · 2·2 HAS LEFT THIS SCREEN ────────────────────
  //
  // ⚠ **THE BUILDER USED TO BE `?edit=1` ON THIS PAGE AND IS NOW ITS OWN
  // ADDRESS.** PO, verbatim: *"the report editor — panel or its own page - own
  // page"*, superseding the `panel` ruling of 2026-09-26 with its cost stated
  // (decision log, 2026-09-28). Everything the panel owned — the draft, the
  // dataset registry, `Save as`, the preview — moved to `ReportEditorPage`
  // whole, so this file went back to being ONE screen: the report, being read.
  //
  // ⚠ **THE OLD ADDRESS STILL ANSWERS, AND THAT IS NOT POLITENESS.** `?edit=1`
  // was the builder's address for two days; it is in bookmarks, in two
  // walkthrough scripts and in the Product Owner's own screenshots. An address
  // that silently drops its meaning and renders the plain report is the worst
  // of the three possible behaviours — the clerk sees a screen that looks
  // right and is not the one they asked for. It redirects, and `replace`
  // keeps the back button pointing where the clerk came from.
  const legacyEditFlag = searchParams.get("edit") === "1";


  // BR-REP-006 — the filter vocabularies are the TENANT's, read live from the
  // same call the library uses (so opening a report from the library costs no
  // extra request) and never a list compiled into this file.
  const libraryQuery = useQuery({
    queryKey: reportLibraryQueryKey,
    queryFn: () => getReportLibrary(client),
    retry: false,
  });

  // ⚠ **`enabled` IS `P2.10`, AND IT IS THE WHOLE OF IT.** A window that is
  // half typed or inverted issues NO request — not a request whose failure is
  // handled prettily. Two keystrokes used to cost two 422s and an error panel,
  // the first of them fired by a *From* with no *To* yet.
  const runnable = key !== "" && reportRunnable(key, query);
  // ⚠ **`columns` IS STILL READ FROM THE URL AND IS STILL HONOURED HERE.**
  // The builder has moved to its own page, but a clerk who leaves it with a
  // column list in the address — or who bookmarks one — is asking this viewer
  // for that shape, and `paramsFrom` carries the parameter for exactly that
  // reason. Nothing on this screen WRITES it any more.
  const runQuery: ReportQuery = query;
  const reportRun = useQuery({
    queryKey: reportQueryKey(key, searchFrom(runQuery).toString()),
    queryFn: () => runReport(key, runQuery, client),
    retry: false,
    enabled: runnable,
    // ⚠ **THE REPORT STAYS ON SCREEN WHILE THE CLERK CHANGES A PARAMETER.**
    // Without this, turning a page or mistyping a date blanks the table to a
    // skeleton and back — and on the inverted range, where nothing is fetched
    // at all, the report simply VANISHED behind the refusal. 2·1b draws the
    // message under *To* over a table that is still showing its rows, which is
    // also the humane version: the clerk can see what they are correcting.
    placeholderData: (previous: ReportResponse | undefined) => previous,
  });

  // The export must carry the window the clerk can SEE, which the server may
  // have defaulted — so it reads `applied` (computed below, after the response
  // is in hand) through a ref rather than closing over the URL's parameters.
  const appliedRef = useRef<ReportQuery>(query);
  const exportRequest = useMutation({
    // §8.2's right path — the WHOLE filtered set, never this page.
    //
    // ⚠ **IT CARRIES THE APPLIED SELECTION, NOT THE URL'S.** Walked on
    // 2026-09-26: a clerk opening the register from the catalogue and pressing
    // export sent `filters: {}` — because the window they could SEE had been
    // defaulted by the server and was in no parameter. The file would have been
    // the server's default window, which is the same window today and a
    // different one on the first of next month.
    mutationFn: () => requestReportExport(key, reportExportFilters(appliedRef.current), client),
    // US-SHL-012: a toast fires on a COMMITTED action and never on a failure.
    onSuccess: () => toast(t("reports.export.queued")),
    // ⚠ **A FAILURE IS SAID OUT LOUD, AND UNTIL 2026-09-27 THIS MUTATION HAD
    // NO `onError` AT ALL** (`DEF-REP-6899`). Pressing Download CSV on a report
    // with no registered export answered 404 and **the screen did not change
    // in any way** — no toast, no panel, no message a clerk could see. Silence
    // by construction, on a money-path control.
    //
    // ⚠ **IT IS AN INLINE STATE AND DELIBERATELY NOT A TOAST.** `Toast.tsx`'s
    // own contract: *"Failures never fire a toast — they render A18 §4/§5
    // states"* (US-SHL-012 TC-4). A toast also disappears, and the one thing a
    // clerk needs after pressing a button that did nothing is something that
    // is still there when they look again.
    //
    // ⚠ **IT COVERS EVERY FAILURE AND NOT ONLY THE UNREGISTERED ONE.** Hiding
    // the control where no resource exists (below) removes today's 404; this
    // is what makes a registered export that fails at run time visible too,
    // which is the half that cannot be designed away.
    onError: () => undefined,
  });

  const report = reportRun.data;
  const currency = report?.currency ?? null;

  // ── `CR-179-BRC10` · INPUTS THE REPORT DECLARES ────────────────────────
  // ⚠ **DRAWN BY KIND, NEVER BY NAME.** The server lists what it needs in
  // `controls.inputs`; this screen draws a dropdown, a tick-box dropdown or a
  // table for each and writes the values back to the URL as `in.<param>`.
  // A report that declares none gets nothing, so every existing report is
  // drawn exactly as before. PO 2026-10-12: *"dont create custom report"*.
  const declared = useDeclaredInputs({
    inputs: report?.controls?.inputs ?? [],
    values: query.inputs ?? {},
    onCommit: (next) => update({ inputs: next }),
    currency,
    timeZone,
    dateFormat,
    t: translate,
  });


  // ── `P2.24` · DRILL DOWN IN PLACE ──────────────────────────────────────
  //
  // ⚠ **THE STATE IS WHICH GROUPS ARE OPEN, AND IT IS NOT IN THE URL.** Every
  // other control on this screen lives in the query string (`BR-SHL-011`) so a
  // bookmark reopens the same page, sort and search. A disclosure is different
  // in kind: it changes NOTHING about the question asked of the server, and
  // putting it in the URL would push a history entry for every triangle — which
  // is a page load in the only sense a clerk cares about, and the task's own
  // words are *"without leaving the report … no page load"*.
  //
  // ⚠ **THE REPORT SERVED IS NEVER RE-REQUESTED BY ANY OF THIS.** `served` is
  // the payload already in hand; `shown` is a pure filter over it. There is no
  // query, no `refetch` and no effect in this block that can reach the network.
  const [openGroups, setOpenGroups] = useState<ReadonlySet<string>>(() => new Set());
  const served = useMemo(() => report?.rows ?? [], [report]);
  // ⚠ **A NEW REPORT FORGETS WHICH GROUPS WERE OPEN.** Group keys are built
  // from a dimension and a value, so two reports can mint the same string and a
  // level would open on arrival with nothing asking it to.
  useEffect(() => setOpenGroups(new Set()), [key]);
  const openable = useMemo(() => openableGroups(served), [served]);
  const shown = useMemo(() => visibleRows(served, openGroups), [served, openGroups]);

  // ── `DEF-REP-7010` · SAID ONCE ABOVE THE TABLE, OR ONCE PER ROW ──────────
  //
  // ⚠ **ASKED OF THE ROWS ON SCREEN, NEVER OF THE REPORT KEY.** A six-service
  // utility bills all six on every account and the column repeats itself
  // forty-one times; a mixed book does not, and there the column is the whole
  // question the register is being read for. Same report, two screens — so
  // the answer comes from the data, every page, and a clerk who filters down
  // to one service sees the line appear.
  //
  // ⚠ **`served`, NOT `shown`.** `shown` is the disclosure — the rows whose
  // group is open — and collapsing on it would make the line appear and
  // vanish as a clerk opened a level, over a report that had not changed.
  const collapsedServices = useMemo(
    () =>
      (report?.columns ?? []).includes("services")
        ? uniformServices(served, "services")
        : null,
    [report, served],
  );

  const config = useMemo(
    () =>
      reportTableConfig(report, key, translate, (row, column) => {
        // ⚠ **`P2.18` — A GROUP ROW IS NOT A FACT ROW AND MUST NOT BE READ AS
        // ONE.** Before this branch the server's subtotal rows were handed
        // straight to `ReportCell`, which looked up `row["account_no"]` on an
        // object that holds `__kind__`, `value`, `rows` and `subtotals` — so a
        // grouped report drew a line of em-dashes where its subtotal belongs.
        // Every check in the module passed over it, because nothing rendered a
        // grouped payload at all.
        if (isReportGroupRow(row)) {
          const group = row as unknown as ReportGroupRow;
          // The FIRST visible column carries the label and the door out; every
          // other carries its own measure's subtotal, under its own heading,
          // which is what makes the figure checkable at all.
          if (column === (report?.columns ?? [])[0]) {
            return (
              <GroupLabelCell
                row={group}
                reportHref={tenantPath(viewerRouteFor(key))}
                search={searchParams}
                expandable={openable.has(groupDisclosureKey(group))}
                open={openGroups.has(groupDisclosureKey(group))}
                onToggle={() =>
                  setOpenGroups((held) => toggleGroup(held, groupDisclosureKey(group)))
                }
                t={translate}
              />
            );
          }
          return (
            <GroupSubtotalCell
              total={group.subtotals[column]}
              currency={currency}
              t={translate}
              // ⚠ **A SUBTOTAL IS THE SAME KIND OF THING AS THE COLUMN IT
              // SITS UNDER** (`DEF-REP-6902`). Every subtotal went through
              // the money renderer before this, so a COUNT under a grouped
              // report wore a currency symbol and a percentage printed six
              // places — the footer fault one row up, in the group rows.
              renderMoney={(amount) => {
                const kind = report?.column_meta?.[column]?.type;
                if (kind === "percent") return <>{percentDisplay(amount)}</>;
                if (kind === "quantity") return <>{quantityText(amount, props.locale)}</>;
                // The walk of 2026-10-12: a group's ACCOUNTS read `$47.00`
                // because the server declared no kind for the column; it now
                // declares `count`, read here as a whole number.
                if (kind === "count") return <>{countText(amount, props.locale)}</>;
                if (kind !== undefined && kind !== "money") return <>{amount}</>;
                return <AmountCell amount={amount} currency={currency} locale={props.locale} />;
              }}
            />
          );
        }
        return (
          <ReportCell
            reportKey={key}
            column={column}
            value={(row as ReportRow)[column] ?? null}
            currency={currency}
            // `DEF-REP-6902` — what KIND this column is, straight from the
            // dataset that declares it. `undefined` for a column no dataset
            // declared, which renders exactly as it did before.
            meta={report?.column_meta?.[column]}
            unit={servedUnit(report, row as ReportRow, column)}
            t={translate}
            locale={props.locale}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
        );
      },
      // `DEF-REP-7010` — a services column every row agrees on is stated once,
      // above the table, and is not drawn in it.
      collapsedServices === null ? [] : ["services"],
      ),
    // `translate` is memoised on `t` above, so listing it (and the two
    // regional settings the cells format with) rebuilds the config only when
    // one of them actually changes.
    // ⚠ `openGroups` AND `openable` ARE LISTED AND MUST BE. The cell renderer
    // closes over both, so without them a click would change the set and the
    // table would redraw the OLD closure — the triangle would flip and nothing
    // else on the row would move.
    [
      report,
      key,
      currency,
      props.locale,
      searchParams,
      tenantPath,
      openGroups,
      openable,
      collapsedServices,
      translate,
      timeZone,
      dateFormat,
    ],
  );

  // The table's request state lives in the URL, so a bookmark opens on the same
  // page, sort and search (BR-SHL-011). `per` is the kit's default — see
  // `paramsFrom` for why it is not in the URL.
  const defaults = defaultRequestState(config);
  const state: TableRequestState = {
    ...defaults,
    q: query.q ?? "",
    sort: query.sort ?? report?.controls?.sort ?? defaults.sort,
    dir: query.dir === "asc" || query.dir === "desc" ? query.dir : (report?.controls?.dir ?? "asc"),
    // ⚠ **CLAMPED TO THE LAST REAL PAGE.** A bookmark carrying `page=2` over a
    // report that has shrunk to 45 rows drew *"51–45 of 45"* — a range that
    // counts backwards, over the rows of page one. The server already clamps
    // what it SERVES; the pager was reading the URL.
    page: Math.min(
      Math.max(1, Number(query.page ?? 1) || 1),
      report?.page?.pages ?? Number.MAX_SAFE_INTEGER,
    ),
    // The server echoes the page size it actually cut with. It is the kit's
    // own `PageSize` in practice; anything else falls back rather than widening
    // the union, because a hand-edited `per` must not become the row cap
    // `NFR-5` deleted.
    per: report?.page !== undefined && isPageSize(report.page.per) ? report.page.per : defaults.per,
    filters: {},
  };

  function update(next: Partial<ReportQuery>): void {
    // ⚠ **ANY CHANGE OF WHAT IS BEING ASKED RETURNS TO PAGE ONE.** Narrowing a
    // 769-page register while sitting on page 40 otherwise lands the clerk on a
    // page that no longer exists, and an empty result reads as *no matches*.
    const changesSelection = Object.keys(next).some((name) => name !== "page");
    const merged: ReportQuery = { ...query, ...next };
    if (changesSelection && next.page === undefined) {
      delete merged.page;
    }
    // ⚠ **`DEF-REP-7073` LIVED HERE AND IS NOW STRUCTURALLY GONE.**
    // `searchFrom` rebuilds the whole query string from the report's own
    // parameters, so anything it does not carry is DELETED by an update rather
    // than left alone — and while the builder was `?edit=1` on this screen,
    // every control on it therefore closed the editor. Typing one character
    // into the account chooser took the URL from `/reports/statement?edit=1`
    // to `/reports/statement`. The one-line re-set that fixed it was a thing
    // every future caller of this function had to remember; the builder's own
    // ADDRESS is a path now, and `searchFrom` cannot touch a path.
    setSearchParams(searchFrom(merged), { replace: true });
  }

  // ── `DEF-REP-6907` · ONE REPORT REFUSED IS NOT THE MODULE REFUSED ───────
  // ⚠ **THE TWO REFUSALS ARRIVE AT THE SAME BRANCH AND THEY ARE NOT THE SAME
  // FACT.** `cell` is the MODULE permission — this person may not open Reports
  // at all, and *"Your role cannot run reports"* is true of them. The other is
  // `P5.9`'s per-report floor (`BR-REP-023`): the server refuses ONE key with
  // `reports.viewer.role_refused`, and the clerk it refuses is drawing 44 of
  // the 45 cards two clicks earlier. Telling that clerk they cannot run
  // reports is false on its face, and they had just been running them.
  //
  // The server already sends the six-word sentence, so the fix is to STOP
  // REPLACING IT with a fixed helper rather than to author new copy.
  // ⚠ **THE LEGACY `?edit=1` LANDS ON THE BUILDER, CARRYING EVERYTHING ELSE
  // IN THE ADDRESS WITH IT.** A statement bookmarked at
  // `?edit=1&subject_id=<uuid>` must open the builder ON that account, so the
  // rest of the query string travels and only the retired flag is dropped.
  if (legacyEditFlag) {
    const carried = new URLSearchParams(searchParams);
    carried.delete("edit");
    const rest = carried.toString();
    return (
      <Navigate
        replace
        to={`${tenantPath(editorRouteFor(key))}${rest === "" ? "" : `?${rest}`}`}
      />
    );
  }

  const runRefused = reportRun.isError && isPermissionDenied(reportRun.error);
  if (isDenied(cell) || runRefused) {
    return (
      <PermissionDenied
        helper={runRefused ? apiErrorText(reportRun.error, translate) : t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const failed = reportRun.isError && report === undefined;
  // ── `DEF-REP-6898` · A REFUSAL IS NOT A FAULT ──────────────────────────
  // ⚠ **TWENTY-SEVEN OF THE FORTY-SIX REPORTS DREW THE ERROR PANEL BELOW,
  // AND NONE OF THEM HAD FAILED.** The server knew exactly why each could not
  // be produced, the catalogue card two clicks earlier printed that reason,
  // and `api.report` threw it away — so a clerk opening a METER READS report
  // read *"The finance figures could not be loaded. Something went wrong on
  // our side. Nothing was saved."* Nothing had gone wrong and nothing had been
  // saved because nothing was ever being written.
  //
  // The two states are now told apart by the SERVER's own `message_key`, not
  // by a status code: a 422 is also what an inverted date range answers, and
  // that one IS the clerk's to fix.
  const notProducible = reportRun.isError && isNotProducible(reportRun.error);
  const vocab = libraryQuery.data?.vocabularies;
  // The window the REPORT ran over, which is the clerk's when they typed one
  // and the tenant's accounting period when they did not (BR-TEN-022).
  //
  // ⚠ **BOTH BOUNDS TRAVEL, EVEN ON A POSITION REPORT, AND THIS IS NOT
  // COSMETIC (`DEF-REP-6844`).** `apps/reports/api` refuses a half window with
  // `reports.viewer.param_required` before any report code runs, so an AR
  // ageing asked with `to` and no `from` answers **422**. The ageing reads only
  // `to` — a receivable is a POSITION at a date and the lower bound reaches no
  // figure in it — but the handler does not know that. So `from` falls back to
  // the as-of day as well: same day, same answer, and the request is lawful.
  // The screen used to send NEITHER, which is why nothing had ever hit this;
  // the first filter a clerk applied would have.
  // ⚠ **THE EXPORT CARRIES THE TICKED COLUMNS TOO.** A file that ignored them
  // would be a different report from the one on screen, which is exactly the
  // fault `reportExportFilters` was written for one parameter along.
  const applied: ReportQuery = {
    ...query,
    columns: query.columns,
    from: query.from ?? report?.window.start ?? report?.window.as_of,
    to: query.to ?? report?.window.as_of ?? report?.window.end,
  };
  appliedRef.current = applied;

  return (
    <div className="fin-page">
      <PageHeader
        // ⚠ **THE EYEBROW SAYS `EDITING` WHILE THE PANEL IS OPEN** — p31
        // callout ⑥ puts the unsaved marker in the rollup *"where state
        // belongs"* (B14 rule 2), not on the button and not in a banner.
        // ⚠ **NO KICKER WHILE THE REPORT IS SIMPLY BEING READ** — `DEF-REP-7011`,
        // PO on the deployed `v2.380.3`: the register put FOUR stacked lines
        // above the first row — `REPORT`, the title, the window, the grain —
        // and asked for two. The word `REPORT` is the one of the four that
        // says nothing a clerk did not already know: they arrived from the
        // report library, by clicking a report, and the frame's own breadcrumb
        // reads *← Reports*.
        //
        // ⚠ **IT STAYS WHILE EDITING, AND THAT IS NOT AN EXCEPTION — IT IS
        // WHAT THE KICKER IS FOR.** B14 rule 2 puts a record's STATE in the
        // kicker, and p31 callout ⑥ puts the unsaved marker there rather than
        // on a button or in a banner. Dropping it in the editing branch too
        // would delete a state signal to save a line nobody was reading.
        kicker={undefined}
        // ⚠ **`P5.3`'s DOOR, AND IT IS THE ONLY ONE** — p32's DOORS row:
        // *"One: the Edit button on 2·1. Nothing else reaches it, deliberately
        // — you always edit a report you are already looking at."*
        // ⚠ **`DEF-REP-6913`'s DOOR, AND IT IS THE ONLY ONE** — p034's DOORS
        // row: *"One: the Schedule button on 2·1."* `4·1` deliberately has no
        // create control, so if this is not here nobody in the product can
        // schedule a report — which is precisely what shipped: the dialog was
        // built, tested and mounted by nothing but its own test.
        // ⚠ **IT IS DISABLED OVER A REFUSAL, NOT HIDDEN** (p034: *"you cannot
        // schedule a refusal"*). `notProducible` and `failed` are computed
        // below this line in source order but read at RENDER, when both are
        // settled.
        // ⚠ **`secondaryActions`, SO IT DRAWS LEFT OF `Edit`** — p028 draws the
        // row as *Schedule · Edit · Save as*, and `PageHeader` renders
        // secondaries before the primary. B14 rule 44: the drawing says what is
        // on screen and how it is arranged; the kit says how it is built.
        secondaryActions={
          <ScheduleDoor
            definitionKey={key}
            // Declared inputs flattened in, as the run sends them.
            params={flatReportParams(applied)}
            disabled={notProducible || failed || report === undefined}
            client={client}
          />
        }
        primaryAction={
          (
            <Button
              variant="secondary"
              // ⚠ **THE DOOR NOW NAVIGATES AND NO LONGER SETS A FLAG** (PO
              // ruling 2026-09-28). It is still the ONLY door onto 2·2 —
              // p032's DOORS row: *"One: the Edit button on 2·1. Nothing else
              // reaches it, deliberately — you always edit a report you are
              // already looking at."* The address is built by `editorRouteFor`,
              // which `App.tsx`'s route and the tests read too, so the door and
              // the destination cannot drift.
              //
              // ⚠ **IT CARRIES THE ADDRESS THE CLERK CAN SEE.** A statement
              // opened on an account, a register narrowed to a window — the
              // builder must open on the SAME question, or its preview
              // describes a report nobody asked for.
              onClick={() => {
                const rest = searchParams.toString();
                navigate(
                  `${tenantPath(editorRouteFor(key))}${rest === "" ? "" : `?${rest}`}`,
                );
              }}
            >
              {/* ⚠ **`Edit`, NOT `EDITING`** (`DEF-REP-6925`). One key was
                  doing two jobs: `reports.edit.eyebrow` is a STATE word and is
                  right as the page-head kicker while the panel is open, and the
                  same expression rendered it as this BUTTON's label while the
                  panel is SHUT — so the header read *Schedule · EDITING* over a
                  report nobody was editing. p028 draws it as *Edit*, and a
                  button label names the ACT a person is about to perform, not
                  the state they are not yet in. The Schedule door beside it
                  took its own key for exactly this reason. */}
              {t("reports.edit.action")}
            </Button>
          )
        }
        // ⚠ **THE ROW'S NAME WINS OVER THE CATALOGUE KEY, AND WITHOUT IT A
        // REPORT A UTILITY WROTE IS TITLED WITH ITS SLUG** — `overdue-60` on
        // screen, which is B14 rule 31 (`DEF-REP-6867`). A shipped report has
        // no `name` on its payload and still reads from the catalogue, so all
        // forty-five are byte-for-byte what they were.
        // ⚠ **THE THIRD SOURCE IS THE CATALOGUE ROW, AND WITHOUT IT A REFUSED
        // REPORT IS TITLED WITH ITS SLUG** (`DEF-REP-6898`, found by walking
        // all 46 at 1440). A refused report has no payload, so `report?.name`
        // is undefined, and only nine of the forty-six keys have an authored
        // `reports.card.<key>.name` — so thirty-odd screens drew **`read_
        // completeness`** as their page-head title. That is B14 rule 31's
        // fault (a database id as the visible value) reached by a fallback
        // rather than by a field. The catalogue is already loaded on this
        // screen for the vocabularies, it carries the row's resolved name, and
        // it is the same name the card the clerk just clicked was showing.
        title={
          report?.name ??
          libraryQuery.data?.cards.find((one) => one.key === key)?.name ??
          t(`reports.card.${key}.name`, { defaultValue: key })
        }
        backTo={{ to: tenantPath(REPORTS_ROUTE), label: t("reports.library.title") }}
        rollup={
          report === undefined ? undefined : (
            <span className="fin-rollup">
              {/* ⚠ **WHOSE MONEY THIS IS, AND IT GOES FIRST** (`DEF-REP-7052`).
                  A statement had never named the account it was about — not
                  this one and not the `CustomerStatementPage` it replaced —
                  so a clerk printed a page of somebody's charges with the
                  report's name above it and nothing else. The brief draws it
                  (p69 `100244 · Ruiz, Marisol`) and p71 states it: *"The head
                  reads 1408 Elm Street · Unit 3."*

                  ⚠ **FIRST BECAUSE IT IS THE SUBJECT OF THE SENTENCE.** The
                  window, the basis and the grain are all facts ABOUT this
                  report; the head is WHAT it is about, and a reader scanning
                  the line needs it before any of them.

                  ⚠ **IN THE ROLL-UP AND NOT ON A LINE OF ITS OWN**
                  (`DEF-REP-7011`): the Product Owner counted four stacked
                  lines above the register's first row and asked for two.

                  ⚠ **THIS FILE NAMES NO SUBJECT.** The server composes the
                  parts from the subject's own declaration, so the customer and
                  premises subjects appear here with no change to this page. */}
              <ReportSubjectHead head={report.head} />
              <span className="fin-rollup-item">
                {report.window.as_of === undefined
                  ? t("reports.rollup", { from: report.window.start, to: report.window.end })
                  : t("reports.asOf", { date: report.window.as_of })}
              </span>
              {/* BR-REP-001 — on the page head, before any figure is read. */}
              <span className="fin-rollup-item">{t(`cells.basis.${report.basis}`)}</span>
              {/* ⚠ **`P2.23`'s GRAIN JOINS THE ROLL-UP INSTEAD OF SITTING ON
                  ITS OWN LINE** (`DEF-REP-7011`). The brief already wanted one
                  line — p025 note ⑩: *"Grain · calendar · basis, IN ONE LINE
                  under the title"* — and the product had drawn two. They are
                  the same KIND of thing: three facts a report cannot be
                  trusted without, none of them rationale, and `.fin-rollup`
                  already puts the middot between them. `ReportGrainLine` is
                  still the component that decides WHICH facts and in what
                  order; only where it renders has moved. */}
              <ReportGrainLine grain={report.grain} t={translate} inline />
            </span>
          )
        }
      />

      <ReportParamBar actions={declared.run}>
        <ReportParameters
          reportKey={key}
          dataset={report?.dataset}
          // ⚠ **THE CONTROL SHOWS WHAT WAS APPLIED, NOT WHAT WAS TYPED.** Until
          // 2026-09-26 the As-of box read `mm/dd/yyyy` while the page head read
          // *As of 2026-09-30* — the server had defaulted the window to the
          // tenant's period and the control said nothing about it. A control
          // that does not state what it applied is the same fault as one that
          // does not apply what it states.
          query={applied}
          // …and because the box now SHOWS the applied bound, changing the
          // other one must carry it into the URL, or the first edit would
          // silently drop a window the clerk could see.
          onChange={(next) => update({ ...applied, ...next })}
          vocab={vocab}
          dateFormat={dateFormat}
          timeZone={timeZone}
          today={today}
          t={translate}
          client={client}
        />
        {/* `CR-185-BRC10` — a report about ONE OWNER asks for the owner HERE,
            in the viewer, rather than only in the builder: the Owner summary
            is run by a clerk who has never opened the builder, and a viewer
            that cannot name its owner opens on an empty table. Drawn only for
            a kind the viewer can find WITHOUT the builder (`owner`); the
            account statement's chooser stays the builder's, as built. */}
        {(report?.controls?.requires ?? []).some((one) => one.finds === "owner") ? (
          <ReportRequiredInputs
            requires={report?.controls?.requires?.filter((one) => one.finds === "owner")}
            values={{ subject_id: query.subject_id ?? "" }}
            onChange={(param, value) => update({ [param]: value === "" ? undefined : value })}
            client={client}
            t={translate}
          />
        ) : null}
        {declared.fields}
      </ReportParamBar>

      {declared.tables}

      {notProducible ? (
        /* ⚠ **THE SAME SENTENCE THE CARD RENDERS, FROM THE SAME FUNCTION.**
            B14 rule 33: the heading is three words, the fact is six, and the
            RATIONALE — grain, datasets, which wave builds it — is ZERO words
            on screen. The server sends that prose in `params.detail` and
            `refusalParams` drops it before i18next ever sees it (PO ruling
            2026-08-19), which is the behaviour this panel depends on rather
            than a coincidence. */
        <AbsentPanel
          title={t("reports.premises.unavailableTitle")}
          reason={unavailableSentence(refusalReasonCode(reportRun.error), translate)}
        />
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("finance.error.title")}</h3>
          {/* The SERVER's refusal, in the user's language. An inverted range no
              longer reaches here at all — it is refused at the control. */}
          <p className="fin-absent-reason">{apiErrorText(reportRun.error, translate)}</p>
        </Panel>
      ) : (
        <>
          {/* P2.13 — a tile with no number says so, with the reason that is
              actually true and no internal code beside it. */}
          <ReportKpiBand
            kpis={report?.kpis ?? []}
            currency={currency}
            basis={report?.basis ?? "posting"}
            t={translate}
            locale={props.locale}
          />

          {/* ⚠ **THE TABLE HAS THE WHOLE MEASURE AGAIN** (PO ruling
              2026-09-28). This was a two-column flex row with the builder's
              panel beside it; the builder is its own page now, so the report a
              clerk is READING is not one column narrower than it needs to be. */}
          {/* `DEF-REP-7010` — said ONCE when every row agrees, and nothing at
              all when they do not. It sits above the table rather than inside
              the toolbar because it is a FACT about the report and the toolbar
              is a row of things a person can press (B14 rule 15). */}
          <ReportServicesLine services={collapsedServices} t={translate} />

          <div className="min-w-0">
          {/* ── `DEF-REP-7070` · AN EMPTY ANSWER SAYS WHY, AT THE TOP ────────
              ⚠ **THE REASON WAS ALREADY ON THE PAGE AND IT WAS FOUR SCROLL-
              LENGTHS DOWN.** `ReportGapList` renders every refusal the read
              model attached, correctly, at the bottom — under the table, the
              subtotals and the additivity panel. On a report that returned
              NOTHING that is the wrong end of the page: the clerk reads *No
              rows match — Widen the dates or filters*, an instruction that
              cannot work, and never reaches *A statement opens on one account*.

              ⚠ **IT IS MOVED, NOT COPIED.** The same list, the same sentences,
              the same component — above the table when there are no rows and
              below it when there are. Saying it twice would be two places to
              keep true, which is the shape of half the defects in this wave. */}
          {report !== undefined && report.rows.length === 0 ? (
            <ReportGapList
              gaps={report.unavailable.filter((gap) => !isCountedGap(gap))}
              title={t("finance.gap.title")}
              render={(gap) => gapSentence(gap, translate)}
            />
          ) : null}
          <DataTable<ReportRow | ReportGroupRow>
            config={config}
            state={state}
            onStateChange={(next) =>
              update({
                q: next.q === "" ? undefined : next.q,
                sort: next.sort === "" ? undefined : next.sort,
                dir: next.dir,
                page: next.page <= 1 ? undefined : String(next.page),
              })
            }
            // ⚠ **`P2.24` — THE ROWS WHOSE ANCESTORS ARE OPEN, NEVER A SHORTER
            // REPORT.** `shown` filters what is DRAWN and changes nothing about
            // what was SERVED: `totalRows` below still reads the server's own
            // count, so the pager keeps describing the report rather than the
            // disclosure. A collapsed level is a level not drawn, not rows the
            // report does not have.
            rows={shown}
            // ⚠ **`null` UNTIL THE SERVER SAYS, AND `rows.length` ONLY WHEN THE
            // REPORT DOES NOT PAGE.** A report with no `page` member is saying
            // *this is all of it* — never *page one* — so its own row count IS
            // the total. Defaulting a paging report to `rows.length` would draw
            // "1–50 of 50" over 38,412 rows.
            totalRows={pagerTotal(report)}
            loading={runnable && reportRun.isLoading}
            // `DEF-SHL-6915`. The `failed` branch above replaces this table on a
            // FIRST failure; this covers a REFETCH that failed over rows already
            // on screen, which `placeholderData` would otherwise go on showing.
            error={reportRun.isError ? { onRetry: () => void reportRun.refetch() } : null}
            empty={{
              title: t("reports.empty.title"),
              helper: t("reports.empty.helper"),
            }}
            downloadSlot={
              // ⚠ **DRAWN ONLY WHERE IT WORKS** (`DEF-REP-6899`). The server
              // asks the export registry `POST /exports` itself consults, and
              // an absent flag is read as NO — see `exportable` on the wire.
              // B14 rule 32: the absence is CLOSED and says nothing, and rule
              // 33 puts RATIONALE at zero words on screen, so there is no
              // greyed control explaining itself. A report that cannot be
              // downloaded simply does not offer it.
              report?.exportable !== true ? null : (
                <>
                  <DownloadButton
                    // IS-11: CSV always; PDF only where a formatted layout
                    // exists, and none does on this deployment — so the `pdf`
                    // prop is not passed and the control offers what the
                    // product can produce.
                    disabled={exportRequest.isPending}
                    onDownload={() => exportRequest.mutate()}
                  />
                  {/* `CR-185-BRC10` — Print, only where the SERVER says the
                      report is a document (`controls.printable`). */}
                  {report?.controls?.printable === true ? <ReportPrintButton /> : null}
                  {/* B14 rule 33 — a FACT of six words, and an instruction of
                      six. Two short sentences beat one long one. */}
                  {exportRequest.isError ? (
                    <span className="ml-2 text-sm text-danger-700" data-export-failed>
                      {t("reports.export.failed")}
                    </span>
                  ) : null}
                </>
              )
            }
            renderFooterRow={
              report === undefined || Object.keys(report.totals).length === 0
                ? undefined
                : (visible) => (
                    <ReportTotalsRow
                      reportKey={key}
                      columns={visible}
                      totals={report.totals}
                      columnMeta={report.column_meta}
                      currency={report.currency}
                      t={translate}
                      locale={props.locale}
                    />
                  )
            }
          />
          </div>

          {/* BR-REP-014 made visible: a deposit is shown AS a deposit, on its
              own line, outside every collection figure. */}
          {report === undefined ||
          report.purposes === undefined ||
          report.purposes.length === 0 ? null : (
            <Panel>
              <div className="fin-panel-head">
                <h3>{t("reports.purposes.title")}</h3>
              </div>
              <PlainTable>
                <tbody>
                  {report.purposes.map((entry) => (
                    <tr key={entry.purpose}>
                      <td>
                        {t(`reports.value.purpose.${entry.purpose}`, {
                          defaultValue: entry.purpose,
                        })}
                      </td>
                      <td className="fin-num">{entry.count}</td>
                      <td className="fin-num">
                        {entry.amount === null ? (
                          <Dash />
                        ) : (
                          <AmountCell
                            amount={entry.amount}
                            currency={report.currency}
                            locale={props.locale}
                          />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </PlainTable>
            </Panel>
          )}

          {/* Every refusal the read model attached, listed under the report it
              belongs to. None of them is a silent omission. */}
          {report === undefined || report.rows.length === 0 ? null : (
            <ReportGapList
              gaps={report.unavailable.filter((gap) => !isCountedGap(gap))}
              title={t("finance.gap.title")}
              render={(gap) => gapSentence(gap, translate)}
            />
          )}

          {/* `CR-179-BRC10` — *Not worked out* (the gaps that COUNT accounts)
              beside *Proposed figures used* (the committed table rows), as
              05-result.png draws them under the total. Both render nothing
              for a report that serves neither. */}
          <div className="grid gap-4 lg:grid-cols-2">
            <CountedGapList gaps={report?.unavailable ?? []} t={translate} />
            {declared.used}
          </div>
        </>
      )}
    </div>
  );
}

export default ReportViewerPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-REP-002@c6c35b2 · CR-142-BRC07 Phase 2 (05-prototype/09 Reports Build Brief.pdf p024/p025/p026/p027/p010-p013/p090-p092, read as RENDERED IMAGES per B14 rule 42)
// screens: S46 (2·1)
// generated: 2026-08-16 by story-coder · REBUILT 2026-09-26 by lane REP-P2-VIEWER; amended 2026-09-28 by lane REP-STMT-SCREEN (`DEF-REP-7052` — the page head names the record the report is about, through `ReportSubjectHead`, and this file names no subject; `DEF-REP-7072` — `columnChoices` is passed through to the panel)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — see the lane report for each guard's failure text
// exceptions: (1) THIS FILE COMPUTES NOTHING — no reduce over rows, no `+` on a money value; the totals row is the server's `totals` and never a sum of the PAGE (BR-REP-002 / DEF-104) · (2) a KPI whose value is null renders **Not counted yet** with its reason, closed (BR-REP-033) · (3) the parameter bar offers only the filters the CHOSEN report accepts · (4) DownloadButton is used WITHOUT its `pdf` prop, and as the kit's unlabelled 36×36 icon rather than the wireframe's labelled button · (5) of the prototype's ☆ Favorite / Schedule / Save as header actions, SCHEDULE IS NOW DRAWN — `ScheduleDoor`, `P4.4`, phase FOUR, p034's DOORS row (*"One: the Schedule button on 2·1"*). ⚠ THIS TRAILER READ *"Schedule is phase 5"* AND THAT WAS WRONG AGAINST THE BRIEF, WHICH IS HOW `ScheduleReportDialog` SHIPPED WITH NO DOOR AT ALL (`DEF-REP-6913`): the lane that built the dialog and the lane that owned the header each wrote a different phase in its own file and nothing compares one file's prose with another's. Save as is 2·4 / `P5.4` and still absent; ☆ Favorite is unbuilt; and a control that opens onto nothing is the defect this phase removes, which is why Schedule is DISABLED rather than hidden where the report cannot be produced · (6) `+ Filter · 9 more`, the applied-filter chips and the Route slicer are P2.26/P2.17 and belong to lane REP-P2-MODEL — deliberately absent rather than drawn inert · (7) no column is declared `identity`: a report row is inert text today, and `identity` carries the claim that the cell links to the record
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
