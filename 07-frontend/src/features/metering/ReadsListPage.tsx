// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-012 (S25 reads list — flags, filters, server pagination) ·
//           US-MET-013 (S29 detail — reached from this screen's rows)
//           Screens: S25
//           Blueprint: Meter Reads entry 02, commitments MR-04 · MR-26 · MR-27 · MR-31
// Rules:    BR-MET-016 (consumers see lineage HEADS — a corrected read appears ONCE) ·
//           BR-MET-021 (the flag vocabulary, one primary status per read) ·
//           BR-MET-055 (server pagination + the 2-year hot window + explicit archive
//           search; there is deliberately no unbounded read endpoint) ·
//           BR-MET-059 (the register model — `channel` is the column, Register is the
//           word) · BR-MET-060 (SUPERSEDED 2026-09-12 — see below) ·
//           BR-MET-144 (a figure displays at two decimals, trailing zeros trimmed) ·
//           BR-SHL-010 (an undeclared capability is not rendered) · BR-SHL-011 (URL
//           grammar) · BR-SHL-012 (the six A18 states, composed not rebuilt) ·
//           BR-SHL-025 (a control this role/release cannot offer renders disabled WITH
//           its reason) · BR-SHL-034 (one date formatter) · BR-SHL-044 (one page header) ·
//           B14 rules 12 · 14 · 15 · 16 · 19 · 31 · 33 · 40
// ───────────────────────────────────────────────────────
// S25 — every committed reading.
//
// This screen exists because the reads ENGINE shipped without it: validation,
// flagging, estimation, supersession and the import pipeline are all served and
// none of it was reachable. That is hard-won law 2 at feature scale, and it is
// the reason three things here are deliberately plain:
//
//   1. **IT LANDS ON `All reads`, ON EVERY OPEN — AND IT LANDED ON `Needs
//      attention` UNTIL 2026-09-14.** `BR-MET-060` ruled the old landing and is
//      stamped **SUPERSEDED 2026-09-12** on the PO's own words: *"Need Attention
//      — does not add any value."* The tab and its three tiles are withdrawn and
//      `US-MET-019`, the story that built the counts, is retired.
//
//      **Two of the three counts survive as a filter click on this list** —
//      Flagged is the `status` filter and Disputed the `disputed` filter, each
//      counting with the predicate its tile used. **Missing does not and never
//      had one**: the server cannot slice the reads list that way, and the
//      number moves to the cycle detail, where a window and an expected set make
//      it mean something. **The tenant-wide all-clear is genuinely lost** and is
//      recorded as a cost of the ruling rather than rebuilt somewhere else.
//
//      The tab is still URL state, so a shared link keeps its tab; a bookmarked
//      `?tab=attention` falls back to the readings rather than opening nothing.
//
//   2. **It renders only what the server sends.** Since CR-038 W5 (2026-08-26,
//      DEF-045 closed) that INCLUDES the prototype's Cycle · Route · Service ·
//      Premise columns: `read_dict` serves them joined server-side, so the
//      table draws all ten of RDS-01's columns and the route/cycle/service
//      filters finally narrow facts the screen can confirm.
//
//   3. **Every quantity carries its unit** (CLAUDE.md rule 3). Previous,
//      Current and Usage all render a SERVER-COMPOSED string — `usage_display`
//      and its two siblings — and none of the three cells has a prop that could
//      take a bare number. That is also where the PO's 2026-09-14 ruling *"as
//      drawn"* is already satisfied: `BR-MET-144` composes at two decimals with
//      trailing zeros trimmed, so `45910.000000` reaches this screen as
//      `45910`, and nothing here rounds, scales or reformats a quantity.
//
// ⚠ **THE REGISTER IS THE COLUMN A CLERK NEEDS AND IT IS CALLED `Register`.**
// The stored column is `meter_reads.channel` and the word on screen was
// "Channel" until 2026-09-14. One word for one thing: `Register` is the
// clerk's, and a reading filed against the wrong register is PERMANENT —
// `supersede_read` takes only a value and a reason, and migration `0007`'s
// trigger freezes the channel. `DEF-797` is what that costs when the units
// differ: 412 kW billed as 14 kWh, **$154 against $4,532** on one commercial
// account in one month. This screen cannot prevent the mistake and does not
// try; what it does is make the register **legible on the way out**, as a
// column beside the value. Nothing here chooses a rounding, a unit or an
// estimate — B4/B5 are ❄️ FROZEN and the PO declined to classify the trap.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  READ_CHANNELS,
  READ_SOURCES,
  READ_STATUS_ESTIMATED,
  READ_STATUS_FLAGGED,
  READ_STATUS_OK,
  getCycles,
  getReads,
  getRoutes,
  getTenantServices,
} from "@/api/endpoints";
import type { CycleRow, ReadRow, RouteRow, TenantServiceRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import {
  FormModal,
  LONG_LIST_THRESHOLD,
  SearchSelectField,
  SegmentedField,
  SelectField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";

import { PermissionDenied } from "@/components/StateFrame";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { ListExportButton } from "@/features/exports/ListExportButton";
import { enabledServiceRows } from "./ServicesAvailableField";
// ONE badge component for the whole product (CR-023 §9.7, DEF-439) — the same
// coloured letter square every premises/units service cell draws.
import { ServiceTags as ServiceSquares } from "@/features/rating/ratingShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DASHBOARD_ROUTE,
  Dash,
  GuardedButton,
  PREMISES_PERMISSION,
  isDenied,
  premisesDetailPath,
  readCycleDetailPath,
  unitDetailPath,
  useRegional,
  useAccessCell,
} from "./meteringShared";
import { routeReadsPath } from "./RouteReadsPage";
import { RecordLink } from "@/components/RecordLink";
import type { RegionalProps } from "./meteringShared";
import {
  READS_ARCHIVE_PARAM,
  READS_TAB_ALL,
  READS_TAB_CYCLES,
  READS_TAB_PARAM,
  READS_UPLOAD_ROUTE,
  READ_PARAM,
  ReadStatusCell,
  UsageCell,
  readDetailPath,
  readsTabFromParam,
} from "./readsShared";
import type { ReadsTab } from "./readsShared";
// CR-038 W5 task 7 (bulk operations) and task 6 (the counter read).
import { ReadsBulkBar, bulkSelectable } from "./ReadsBulkBar";
import { QuickReadButton, QuickReadModal } from "./QuickReadModal";
// DEF-897 (PO 2026-08-27, *"this can be modal - instead of page"*): the
// estimate form joins its three siblings as a dialog; `/reads/estimate` and
// its `READS_ESTIMATE_ROUTE` constant are gone with the page.
import { EstimateReadModal } from "./EstimateReadModal";
// The cycles TAB is the Meter Reads blueprint's **entry 15** since 2026-09-14 —
// see `headerTabs` below. It used to render `CyclesOpsPage`, the screen that
// already existed at `/:tenant/reads/cycles`.
import { ReadCyclesTab } from "./ReadCyclesTab";
import { ReadAnswerFilter } from "./ReadAnswerFilter";
import { answerFilterEntries, answerFiltersFrom, writeAnswerFilters } from "./readAnswersShared";

import "./reads.css";

// ── Pure pieces (provable without a browser or a network) ─────────────────

export const readsQueryKey = (query: string) => ["reads", "list", query] as const;
export const readsRoutesQueryKey = ["routes", "reads-filter"] as const;
export const readsCyclesQueryKey = ["cycles", "reads-filter"] as const;

/**
 * US-MET-012's status control, in the SERVED vocabulary. `flagged` is the
 * server's composite ("neither ok nor estimated"), which is exactly the set the
 * Flagged chip counts — so the chip and the filter cannot drift.
 *
 * The prototype's fourth choice, **Pending**, is absent: BR-MET-049 derives it
 * from the plan-required record set, `GET /reads` has no such filter, and an
 * undeclared `f.` param is ignored rather than refused — a "Pending" option
 * would silently return every read. Reported rather than rendered.
 */
export function readStatusFilterOptions(t: Translator): { value: string; label: string }[] {
  return [
    { value: READ_STATUS_OK, label: t("metering.reads.filter.statusOk") },
    { value: READ_STATUS_FLAGGED, label: t("metering.reads.filter.statusFlagged") },
    { value: READ_STATUS_ESTIMATED, label: t("metering.reads.filter.statusEstimated") },
  ];
}

/** BR-MET-059's channel enum — extensible by a value, never a schema change. */
export function channelFilterOptions(t: Translator): { value: string; label: string }[] {
  return READ_CHANNELS.map((channel) => ({
    value: channel,
    label: t(`metering.reads.channel.${channel}`),
  }));
}

/** `models.READ_SOURCES` — how the row entered, not how the register was read. */
export function sourceFilterOptions(t: Translator): { value: string; label: string }[] {
  return READ_SOURCES.map((source) => ({
    value: source,
    label: t(`metering.reads.source.${source}`),
  }));
}

export function routeFilterOptions(
  rows: readonly RouteRow[] | undefined,
): { value: string; label: string }[] {
  return (rows ?? []).map((route) => ({
    value: route.id,
    label: route.name === null ? route.code : `${route.code} · ${route.name}`,
  }));
}

export function cycleFilterOptions(
  rows: readonly CycleRow[] | undefined,
): { value: string; label: string }[] {
  return (rows ?? []).map((cycle) => ({ value: cycle.id, label: cycle.code }));
}

/**
 * The service filter — RENDERED as of CR-038 W5. `f.service` was served from
 * the first day and deliberately not offered, because `GET /settings/services`
 * was System-Admin-only then and a Billing Clerk would have got an empty
 * dropdown. That endpoint is AnyTenantRole now (US-TEN-007 TC-4: clerks read
 * it read-only — BillRunWizard step 1 and the Units list already rely on it),
 * so the vocabulary is the tenant's ENABLED set, exactly as the Units filter
 * builds it. The VALUE is the service CODE — the server filters
 * `service__code` (selectors.read_list).
 */
export function serviceFilterOptions(
  rows: readonly TenantServiceRow[] | undefined,
): { value: string; label: string }[] {
  return enabledServiceRows(rows).map((row) => ({ value: row.service, label: row.name }));
}

/**
 * **BATCH — B14 RULE 31, AND THIS CELL WAS THE BREACH.**
 *
 * It rendered `import_batch_id` — a raw uuid — because that was the only thing
 * `read_dict` served, and it said so in a tooltip. Rule 31's own sentence names
 * this exact case: *"where the reference is genuinely what a user needs — a
 * batch number, a premise number — it has a HUMAN-FACING number and that is
 * what is shown … the internal value may ride on `title` as evidence."*
 *
 * The server serves `import_batch_no` now. **Three states, and the middle one is
 * why the id is still served rather than replaced:**
 *   · a NUMBER — shown, with the uuid on `title` as evidence;
 *   · a batch its SERIES NEVER NUMBERED — `batch_no` is NULLABLE, so this is a
 *     real state said in WORDS, id still on `title`;
 *   · NO BATCH at all — the em dash. A read written by hand or arriving on the
 *     AMI feed belongs to no import batch, which is the common case.
 *
 * ⚠ **IT IS EXPORTED SO A TEST CAN EXERCISE THE REAL RENDERER.** The suite's
 * `readsTableConfig` is built with STUB cells (`() => <span />`), which is right
 * for asserting the column SET — and means an assertion aimed at a cell through
 * that config tests the stub and passes on anything. Two cases here did exactly
 * that before this was lifted out, and they only showed it by failing on the
 * empty span.
 */
export function ReadBatchCell(props: { row: ReadRow; t: Translator }) {
  const { row, t } = props;
  if (row.import_batch_id === null) {
    return <Dash />;
  }
  return (
    <span className="rd-batch" title={row.import_batch_id}>
      {row.import_batch_no === null || row.import_batch_no === ""
        ? t("metering.reads.batchUnnumbered")
        : row.import_batch_no}
    </span>
  );
}

export function readsTableConfig(
  t: Translator,
  options: {
    routes: { value: string; label: string }[];
    cycles: { value: string; label: string }[];
    services: { value: string; label: string }[];
  },
  /** **THE WHOLE ROW OPENS THE READING** — the blueprint's entry 02 moves the
   *  affordance off the meter cell. It is handed in rather than built here for
   *  the same reason every cell is: this function is pure and knows nothing
   *  about the tenant path. */
  rowHref: (row: ReadRow) => string,
  cells: {
    // CR-038 W5 task 7 — the multi-select that drives the bulk actions.
    // DataTable has no built-in selection, so the checkbox is a CELL in this
    // config, exactly as `AssetRegistryPage` already does it (B14: one table
    // type, never a second table grown for one screen).
    select: (row: ReadRow) => JSX.Element;
    meter: (row: ReadRow) => JSX.Element;
    readAt: (row: ReadRow) => JSX.Element;
    cycle: (row: ReadRow) => JSX.Element;
    route: (row: ReadRow) => JSX.Element;
    service: (row: ReadRow) => JSX.Element;
    premise: (row: ReadRow) => JSX.Element;
    usage: (row: ReadRow) => JSX.Element;
    status: (row: ReadRow) => JSX.Element;
    channel: (row: ReadRow) => JSX.Element;
    source: (row: ReadRow) => JSX.Element;
    days: (row: ReadRow) => JSX.Element;
    batch: (row: ReadRow) => JSX.Element;
    // ⚠ **TWO NAMED RENDERERS, NOT ONE INDEXED BY A VARIABLE (DEF-1086).**
    // This was `value: (row, field) => …` and the body was `row[field]`. A
    // renderer that does not KNOW which field it holds cannot know whether the
    // value is money, a quantity or a key, and therefore cannot format it —
    // whatever the rule turns out to be. Naming the field is the precondition
    // for having a treatment at all, which is why `G44` clause (a) is a hard
    // invariant at baseline zero rather than a ratchet.
    priorValue: (row: ReadRow) => JSX.Element;
    currentValue: (row: ReadRow) => JSX.Element;
  },
): TableConfig<ReadRow> {
  return {
    screenId: "S25",
    columns: [
      { key: "select", label: t("metering.reads.col.select"), cell: cells.select },
      {
        key: "meter",
        label: t("metering.reads.col.meter"),
        sortable: true,
        identity: true, // BR-AST-026's sibling: the asset NUMBER, never the uuid
        cell: cells.meter,
      },
      // NOT in the prototype's ten columns, and added on purpose: the list is
      // sorted by read date and a reading without its date cannot be checked
      // against a bill. Reported as a deliberate divergence.
      {
        key: "read_at",
        label: t("metering.reads.col.readAt"),
        sortable: true,
        cell: cells.readAt,
      },
      // RDS-01's four middle columns — SERVED as of CR-038 W5 (DEF-045
      // closed): Cycle · Route · Service · Premise, in the artboard's order.
      // None is sortable, because `selectors.READ_SORTS` declares no sort for
      // them and a dead header is DEF-044's shape (BR-SHL-010).
      { key: "cycle", label: t("metering.reads.col.cycle"), cell: cells.cycle },
      { key: "route", label: t("metering.reads.col.route"), cell: cells.route },
      { key: "service", label: t("metering.reads.col.service"), cell: cells.service },
      { key: "premise", label: t("metering.reads.col.premise"), cell: cells.premise },
      {
        key: "prior_value",
        label: t("metering.reads.col.previous"),
        numeric: true,
        cell: cells.priorValue,
      },
      {
        key: "current_value",
        label: t("metering.reads.col.current"),
        numeric: true,
        cell: cells.currentValue,
      },
      // CLAUDE.md rule 3: the server's `usage_display`, unit included, always.
      { key: "usage", label: t("metering.reads.col.usage"), sortable: true, cell: cells.usage },
      { key: "source", label: t("metering.reads.col.source"), cell: cells.source },
      { key: "status", label: t("metering.reads.col.status"), sortable: true, cell: cells.status },
      // ── The AVAILABLE-not-default columns (B2 r8), in the DRAWN ORDER ──
      //
      // Register · Batch · Days since prior, which is the order the column
      // picker lists them in, because the picker renders `columns` as declared.
      // `days_since_prior` used to sit between the first two and the drawing
      // puts it last.
      {
        key: "channel",
        // **`Register`, WAS `Channel` — RELABELLED 2026-09-14.** The stored
        // column is `meter_reads.channel` (BR-MET-059) and the key still names
        // it, because that is the fact a developer needs; `Register` is the
        // word a clerk uses and the one that goes on screen. B14 rule 31's own
        // discipline, one level up from an id: the internal name stays in the
        // code, the human-facing name is what is shown.
        label: t("metering.reads.col.channel"),
        sortable: true,
        defaultVisible: false,
        cell: cells.channel,
      },
      {
        key: "import_batch_id",
        label: t("metering.reads.col.batch"),
        defaultVisible: false,
        cell: cells.batch,
      },
      {
        key: "days_since_prior",
        label: t("metering.reads.col.days"),
        numeric: true,
        defaultVisible: false,
        cell: cells.days,
      },
    ],
    getRowId: (row) => row.id,
    // IS-3 — **THE METER NUMBER AND THE PREMISE ADDRESS, AND THE SERVER
    // SEARCHES BOTH.** This read `["meter"]` alone until 2026-09-14 and the
    // placeholder said so on purpose: `selectors.read_list` filtered
    // `asset__asset_no__icontains` and nothing else, and naming a field the
    // endpoint ignores is the DEF-950 trap. The predicate is widened now (one
    // OR, along the same asset → service_point → unit → premises chain the
    // Premise cell is composed from), so the box and the query agree again.
    searchFields: ["meter", "premise"],
    // ⚠ **B14 rule 19, AND THE DIVERGENCE FROM r10 IS OVER (DEF-950 CLOSED).**
    // The box read `Search meter #…` because that was the truth: r10 RDS-01
    // draws `Meter #, address…` and the address half would have been a promise
    // the server did not keep. The server keeps it as of 2026-09-14, so the
    // copy names both — *"A clerk on a phone call has an address"* is the
    // blueprint's own reason for widening it.
    searchPlaceholder: "metering.reads.searchPlaceholder",
    filters: [
      {
        name: "status",
        label: t("metering.reads.filter.status"),
        options: readStatusFilterOptions(t),
      },
      { name: "route", label: t("metering.reads.filter.route"), options: options.routes },
      { name: "cycle", label: t("metering.reads.filter.cycle"), options: options.cycles },
      // RENDERED as of CR-038 W5 — see `serviceFilterOptions` for why it could
      // not be offered before (no role-safe vocabulary endpoint existed).
      {
        name: "service",
        label: t("metering.reads.filter.service"),
        options: options.services,
      },
      {
        // The same relabel as the column above, for the same reason: one word
        // for one thing. A clerk who filters by register and then shows the
        // column must see the same word in both places.
        name: "channel",
        label: t("metering.reads.filter.channel"),
        options: channelFilterOptions(t),
      },
      { name: "source", label: t("metering.reads.filter.source"), options: sourceFilterOptions(t) },
      // Declared 2026-08-16 with the dispute writer. It has to be HERE and not
      // only in the chip's click handler: `parseTableParams` restores only
      // DECLARED filters and `serializeTableParams` writes only declared ones,
      // so an undeclared `disputed` would vanish from the URL on the next
      // interaction and the drill-in would quietly widen back to every read.
      {
        name: "disputed",
        label: t("metering.reads.filter.disputed"),
        options: [{ value: "true", label: t("metering.reads.filter.disputedOnly") }],
      },
    ],
    // The capability row's "read_at desc". The SERVER ignores `dir` on this
    // endpoint today (`selectors.read_list` takes no direction) — reported; the
    // request carries the declared default so nothing has to change here when
    // the server honours it.
    defaultSort: { sort: "read_at", dir: "desc" },
    // ⚠ **THE ROW IS THE TARGET, AND THE IDENTITY CELL STILL IS TOO.** The
    // affordance used to be the meter cell alone, and this file's own exception
    // list said why: *"DataTable has no row-click contract to add one to"*. It
    // has one now — `TableConfig.rowHref`, added to the shared kit rather than
    // hand-rolled here (B14 rule 36: where the kit lacks a piece, add it to the
    // kit). The link in the Meter cell is unchanged and is still what a
    // keyboard reaches; a `<tr>` cannot be focused, so a row click can only
    // ever be a MOUSE convenience on top of a real link.
    rowHref,
  };
}

export function readsParamsFrom(
  state: TableRequestState,
  archive: boolean,
  answers: Record<string, string> = {},
) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: state.filters,
    // BR-MET-055: default OFF. Only an explicit opt-in reaches beyond the
    // 2-year hot window, and it travels as its own param, not as a filter.
    archive,
    // MQ-033 (`CR-192-BRC10` task 13) — `answer[<key>]=<value>`, AND-ed.
    answers,
  };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface ReadsListPageProps extends RegionalProps {
  client?: ApiClient;
}

export function ReadsListPage(props: ReadsListPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  const tab = readsTabFromParam(searchParams.get(READS_TAB_PARAM));
  const archive = searchParams.get(READS_ARCHIVE_PARAM) === "true";
  const openReadId = searchParams.get(READ_PARAM);
  const [pickingRouteSheet, setPickingRouteSheet] = useState(false);
  // DEF-897 — the estimate form is a DIALOG now, mounted only while open
  // (IS-10: a permanently-rendered modal is a focus trap waiting to happen).
  const [estimating, setEstimating] = useState(false);
  // CR-038 W5 task 7 — the bulk selection, by read id. Held on the PAGE rather
  // than inside the bar so that a filter, tab or page change can clear it: a
  // selection that survives a filter change is a clerk accepting rows they can
  // no longer see.
  const [selected, setSelected] = useState<string[]>([]);
  // CR-038 W5 task 6 — the quick single-reading modal, mounted only while open
  // (IS-10: a permanently-rendered modal is a focus trap waiting to happen).
  const [quickEntry, setQuickEntry] = useState(false);
  const cell = useAccessCell(PREMISES_PERMISSION, client);

  const routesQuery = useQuery({
    queryKey: readsRoutesQueryKey,
    queryFn: () => getRoutes(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const cyclesQuery = useQuery({
    queryKey: readsCyclesQueryKey,
    queryFn: () => getCycles(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // BR-MET-003's shape, borrowed from the Units filter: the vocabulary is the
  // TENANT's enabled set, never a list derived from whichever rows happen to
  // be on this page. Reference data — shared staleness, no retry spinner.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const config = readsTableConfig(
    translate,
    {
      routes: routeFilterOptions(routesQuery.data),
      cycles: cycleFilterOptions(cyclesQuery.data),
      services: serviceFilterOptions(servicesQuery.data),
    },
    (row) => tenantPath(readDetailPath(row.id)),
    {
      // CR-038 W5 task 7. BR-SHL-025: a row this action cannot touch renders a
      // DISABLED checkbox WITH its reason — never a missing one, which would
      // leave a clerk wondering where the control went.
      select: (row) => {
        const selectable = bulkSelectable(row);
        return (
          <input
            type="checkbox"
            aria-label={t("metering.reads.selectRow", { meter: row.meter ?? row.id })}
            checked={selected.includes(row.id)}
            disabled={!selectable.ok}
            title={
              selectable.ok
                ? undefined
                : t(`metering.reads.bulk.notSelectable.${selectable.reason ?? "unavailable"}`)
            }
            onChange={(event) =>
              setSelected(
                event.target.checked
                  ? [...selected, row.id]
                  : selected.filter((id) => id !== row.id),
              )
            }
          />
        );
      },
      // The row's affordance into S29 — a PAGE as of CR-038 W5 (PO 2026-08-26:
      // "i want page to be open for consitency - we dont open side panel").
      // The identity cell is the link, as on every other list (S49, S14, S15),
      // and it is a REAL router link now, so open-in-new-tab works.
      meter: (row) => (
        <InlineLinkTo
          className="rd-open"
          to={tenantPath(readDetailPath(row.id))}
          aria-label={t("metering.reads.openDrawer", { meter: row.meter ?? row.id })}
        >
          {row.meter ?? <Dash>{t("metering.reads.meterUnknown")}</Dash>}
        </InlineLinkTo>
      ),
      readAt: (row) =>
        row.read_at === null ? (
          <Dash />
        ) : (
          // ⚠ **NO `withTime`, AND ITS ABSENCE IS THE FIX (`DEF-MET-4101`).**
          // A read's `read_at` is a CALENDAR DATE — metering stamps every one
          // at `00:00:00Z` of the read day so the per-date uniqueness key
          // works — so there has never been a clock time here to show. While
          // the server sent the raw instant this column drew
          // `08/13/2026 19:00` for a read taken on 14 August: the wrong day,
          // and 19:00 invented out of the Chicago offset. The server now sends
          // the date, `DateCell` takes its calendar-date path, and `withTime`
          // would be a prop that silently does nothing.
          <DateCell value={row.read_at} timeZone={timeZone} dateFormat={dateFormat} />
        ),
      // RDS-01's four middle cells (DEF-045 closed). Each dashes its honest
      // absence — a stock meter has no route to claim.
      //
      // Record links (PO 2026-10-19): the cycle opens its reading-work page
      // (entry 20 — not Settings' definition), the route its reads.
      cycle: (row) =>
        row.cycle === null ? (
          <Dash />
        ) : (
          <RecordLink to={row.cycle_id ? tenantPath(readCycleDetailPath(row.cycle_id)) : null}>{row.cycle}</RecordLink>
        ),
      route: (row) =>
        row.route === null ? (
          <Dash />
        ) : (
          <RecordLink to={row.route_id ? tenantPath(routeReadsPath(row.route_id)) : null}>{row.route}</RecordLink>
        ),
      // The ONE badge component (CR-023 §9.7): the same coloured letter square
      // every premises/units service cell draws — never a second vocabulary.
      service: (row) =>
        row.service === null ? <Dash /> : <ServiceSquares services={[row.service]} />,
      // RDS-01 draws "1408 Elm · A" — the address and the unit label, one cell.
      premise: (row) =>
        row.premise === null ? (
          <Dash />
        ) : (
          // Record links: the address opens the premises, the label the unit.
          <span>
            <RecordLink to={row.premises_id ? tenantPath(premisesDetailPath(row.premises_id)) : null}>
              {row.premise}
            </RecordLink>
            {row.unit_label !== null && (
              <span className="met-qualifier">
                {" · "}
                <RecordLink to={row.unit_id ? tenantPath(unitDetailPath(row.unit_id)) : null}>{row.unit_label}</RecordLink>
              </span>
            )}
          </span>
        ),
      // ── PREVIOUS · CURRENT — DEF-1086, and the fix was already on this row ──
      //
      // These two cells printed the STORED register value with no formatter of
      // any kind: `row[field]` straight into a span, so the Product Owner read
      // **`1008.000000`** on the live deployment. Two columns to the right, the
      // USAGE cell read `8 kgal` — because the SERVER composes `usage_display`
      // and this cell renders that sibling instead of the raw number.
      //
      // So the house pattern was on the same row of the same table the whole
      // time, and the only thing missing was a sibling for these two fields.
      // `read_dict` composes them now (BR-SHL-250: a quantity is composed by
      // the side that holds its UNIT), through the SAME
      // `quantity_display.quantity_with_unit` the usage cell already used, so
      // the three cells cannot drift: `1008 kWh`, at BR-MET-144's two decimals
      // with the trailing zeros trimmed, and CLAUDE.md hard rule 3's unit.
      //
      // A null reading still dashes — `quantity_with_unit` returns null for an
      // absent quantity AND for a reading whose unit was never recorded, which
      // is BR-MET-106's *an unread month is ABSENT, never a zero* and hard rule
      // 3's refusal to print a bare number, both held here rather than by this
      // cell having to know either rule.
      priorValue: (row) =>
        row.prior_value_display === null ? (
          <Dash />
        ) : (
          <span>{row.prior_value_display}</span>
        ),
      currentValue: (row) =>
        row.current_value_display === null ? (
          <Dash />
        ) : (
          <span>{row.current_value_display}</span>
        ),
      days: (row) =>
        row.days_since_prior === null ? <Dash /> : <span>{row.days_since_prior}</span>,
      batch: (row) => <ReadBatchCell row={row} t={translate} />,
      usage: (row) => <UsageCell row={row} />,
      status: (row) => <ReadStatusCell status={row.status} t={translate} />,
      channel: (row) => (
        <span>{t(`metering.reads.channel.${row.channel}`, { defaultValue: row.channel })}</span>
      ),
      // ONE COLUMN, TWO FACTS, IN THE ORDER A CLERK ASKS THEM (CR-038 W3):
      // the METHOD first — how the reading was collected, the thing they came
      // to this column for — then the transport it arrived by, qualified. A
      // read whose method is not stated says so rather than showing a blank.
      //
      // ⚠ **TWO THINGS LEFT THIS CELL ON 2026-08-27 AND BOTH ARE BR-MET-160**
      // (DEF-895). PO, on the live app: *"you dont have to provide sub text in
      // bracket"*. r10 RDS-01 draws this column as ONE word — `AMI`, `Walk`.
      // What it drew instead, on EVERY row:
      //
      //     Walk-by (from the old source tag) · Manual entry · Walk-by
      //
      //   1. `readMethod.derivedSuffix` — the bracket. It explains OUR OWN
      //      migration (BR-MET-142's legacy `source_detail` translation) to a
      //      clerk who has never had an "old source tag". Provenance is detail
      //      for a reader who has ASKED for detail, so it lives on S29, which
      //      states it in the same words beside the method tag. The key is NOT
      //      deleted — the detail page still uses it.
      //   2. `source_detail` — the third part, and it was printing the SAME
      //      WORD as the method. A derived method IS derived from
      //      `source_detail`, so on every legacy row the cell said "Walk-by"
      //      twice. Also on S29, also unchanged there.
      //
      // What is left is BR-MET-123's two genuine facts: the METHOD and the
      // TRANSPORT it arrived by.
      source: (row) => (
        <span>
          {row.read_method === null
            ? t("metering.reads.readMethod.notStated")
            : t(`metering.reads.readMethod.${row.read_method}`, {
                defaultValue: row.read_method,
              })}
          <span className="met-qualifier">
            {" · "}
            {t(`metering.reads.source.${row.source}`, { defaultValue: row.source })}
          </span>
        </span>
      ),
    },
  );

  const state = parseTableParams(searchParams, config);
  // MQ-033 (`CR-192-BRC10` task 13) — the Answer filter, in the address bar
  // under the server's own spelling, `answer[<key>]=<value>`.
  const answers = answerFiltersFrom(searchParams);
  // ⚠ **THE TABLE MUST KNOW AN ANSWER FILTER IS APPLIED.** `DataTable` swaps
  // the whole region for the first-use empty state (no toolbar) when a list
  // has no rows AND no `q`/`filters` — so an answer that matched nothing hid
  // the very chip that would remove it (caught by `ReadAnswerFilter.dom.test`).
  // The entries ride in `filters` under the server's spelling: undeclared, so
  // `serializeTableParams` never writes them as `f.`, and the export body
  // carries them to `read_formats.answer_filters` unchanged.
  const tableState: TableRequestState = {
    ...state,
    filters: { ...state.filters, ...answerFilterEntries(answers) },
  };

  // The RETIRED drawer's `?read=<id>` deep links live in tickets — that
  // linkability was the param's whole point — so they forward to the S29 PAGE
  // instead of silently opening nothing (the LEGACY_SETTINGS_TAB_PATHS
  // posture, one param over).
  useEffect(() => {
    if (openReadId !== null && openReadId !== "") {
      navigate(tenantPath(readDetailPath(openReadId)), { replace: true });
    }
  }, [openReadId, navigate, tenantPath]);

  function writeParams(
    next: TableRequestState,
    over: { tab?: ReadsTab; archive?: boolean; answers?: Record<string, string> },
  ): void {
    const params = serializeTableParams(next, config);
    writeAnswerFilters(params, over.answers ?? answers);
    params.set(READS_TAB_PARAM, over.tab ?? tab);
    if (over.archive ?? archive) {
      params.set(READS_ARCHIVE_PARAM, "true");
    }
    setSearchParams(params, { replace: true });
  }

  function setState(next: TableRequestState): void {
    writeParams(next, {});
  }

  const listQuery = useQuery({
    // The answer filters join the key only when there are any, so a list with
    // none keeps the key it always had (and every cache seeded with it).
    queryKey: readsQueryKey(
      `${serializeTableParams(state, config).toString()}|${archive}` +
        (Object.keys(answers).length > 0 ? `|${JSON.stringify(answers)}` : ""),
    ),
    queryFn: () => getReads(readsParamsFrom(state, archive, answers), client),
    // The list is the LANDING tab now, so this fires on every open — which is
    // the point of the ruling. It is still gated on the tab, because the cycles
    // tab beside it must not pull a page of readings nobody is looking at.
    enabled: tab === READS_TAB_ALL,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.reads.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (listQuery.data === undefined && listQuery.isError && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("metering.reads.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  // BR-SHL-025: a control this release cannot offer renders DISABLED WITH ITS
  // REASON rather than vanishing (the user would never learn it exists) or
  // being live onto nothing (they would learn by clicking).
  //
  // "↑ Upload reads" WAS one of those, and that was DEF-115: the read-import
  // pipeline shipped served and unit-tested, this button said so honestly, and
  // `meter_reads` held 0 rows on a fully seeded stack because no screen could
  // add one — so no bill in this product had ever come from a meter reading.
  // S28 exists as of 2026-08-15 and this button is now a real navigation.
  // "Route sheet PDF" went LIVE with CR-038 W5 (2026-08-26): the server
  // renders the sheet from the D11 walk order, and the button opens the
  // route picker below.
  const openUpload = () => navigate(tenantPath(READS_UPLOAD_ROUTE));
  const openEstimate = () => setEstimating(true);

  // ⚠ **NEITHER TAB CARRIES A PROSE DESCRIPTION (DEF-896, and now B14 rule 32).**
  // PO, on the live app: *"on this screen ui is not correct for search, filter,
  // colume selection, description"*. r10 RDS-01 draws NO paragraph over this
  // list — the toolbar starts at the top of the content — and the blueprint's
  // entry 02 draws none either.
  //
  // The retired `Needs attention` tab had one, and it went with the tab.
  const headerTabs = [
    {
      id: READS_TAB_ALL,
      label: t("metering.reads.tab.all"),
    },
    {
      // **THE CYCLES TAB — A DOOR ONTO A SCREEN THAT ALREADY EXISTED.**
      // `/:tenant/reads/cycles` has been routed and built since CR-006 and
      // nothing in the product linked to it: hard-won law 2's mirror, a live
      // screen behind no control at all. This tab is that control.
      //
      // ⚠ **AND IT RENDERS THE REDRAWN TABLE FROM 2026-09-14.** This comment
      // used to end *"the blueprint's entry 15 redraws that table and is a
      // separate piece of work, deliberately not done here"*. That work is
      // done: `ReadCyclesTab` is entry 15 — seven of its nine drawn columns,
      // search, filter, the ▦ chooser, three sortable headers and a SERVER
      // pager where the old table had none and paged in the browser over a
      // fetch-everything read (`NFR-3`). Its two undrawn columns are
      // `DEF-MET-5206` and the reason is in that file's own opening note.
      id: READS_TAB_CYCLES,
      label: t("metering.reads.tab.cycles"),
    },
  ];

  return (
    <div className="met-page rd-page">
      <PageHeader
        title={t("metering.reads.title")}
        secondaryActions={
          <>
            {/* CR-038 W5 task 6 — the counter case. PO 2026-08-26: *"we will
                need modpage to load single reading, if it is simple then
                modal"*. A clerk with ONE reading should not walk the
                five-stage wizard "↑ Upload reads" opens, and the modal is the
                PO's own conditional applied: one meter, one date, one value,
                one register. It stages through the SAME pipeline as a file. */}
            <QuickReadButton onOpen={() => setQuickEntry(true)} t={translate} />
            {/* US-MET-014/015 (2026-08-16). The estimation engine and
                `POST /reads/estimate` shipped correct and unreachable — a clerk
                with an unreadable meter could not fill the gap, so that
                customer could not be billed. This is the entry point that makes
                the engine reachable from the running app; without a caller the
                screen would be dead UI, which is the law-2 defect it was
                written to close. */}
            <GuardedButton
              label={t("metering.reads.action.estimate")}
              reason={null}
              onClick={openEstimate}
            />
            {/* LIVE as of CR-038 W5. The label keeps r10's own copy ("Route
                sheet PDF"); what the server answers is print-ready HTML — the
                browser's Print / Save as PDF is the PDF, because no PDF
                library is a backend dependency (route_sheet.py's docstring
                records the decision). */}
            <GuardedButton
              label={t("metering.reads.action.routeSheet")}
              reason={null}
              onClick={() => setPickingRouteSheet(true)}
            />
          </>
        }
        primaryAction={
          <GuardedButton
            label={t("metering.reads.action.upload")}
            reason={null}
            variant="primary"
            onClick={openUpload}
          />
        }
        tabs={headerTabs}
        activeTabId={tab}
        tabsLabel={t("metering.reads.tabsLabel")}
        onTabSelect={(next) => writeParams(state, { tab: readsTabFromParam(next.id) })}
      />

      {tab === READS_TAB_CYCLES ? (
        <ReadCyclesTab client={client} {...props} />
      ) : (
        <>
          {/* CR-038 W5 task 7 — the bulk bar, above the table it acts on. It
              renders NOTHING until something is selected: a permanent empty
              toolbar over every list is chrome nobody reads. */}
          <ReadsBulkBar
            selected={selected}
            rows={listQuery.data?.results ?? []}
            onClear={() => setSelected([])}
            client={client}
            t={translate}
          />
          <DataTable<ReadRow>
            config={config}
            state={tableState}
            // A sort, a page or a filter change CLEARS the selection. Keeping
            // it would let a clerk accept forty rows they can no longer see —
            // and the reason they typed would be about the rows in front of
            // them, not the ones the click reaches.
            onStateChange={(next) => {
              setSelected([]);
              setState(next);
            }}
            rows={listQuery.data?.results ?? []}
            totalRows={listQuery.data?.count ?? null}
            loading={listQuery.isPending}
            error={
              listQuery.isError && listQuery.data === undefined
                ? {
                    reason: apiErrorText(listQuery.error, translate),
                    onRetry: () => void listQuery.refetch(),
                  }
                : null
            }
            // ⚠ **THIS WAS A `met-filters` GRID AT `width: 100%` AND THAT IS
            //    WHAT BROKE THE TOOLBAR (DEF-896).** A full-width grid cell
            //    inside `.table-toolbar`'s flex row consumed the whole line, so
            //    the `All` pill and `+ Filter` dropped BELOW the search box, the
            //    archive checkbox floated into the middle as a grid column, and
            //    Download CSV plus the column icon wrapped to a SECOND row far
            //    right. r10 RDS-01 draws ONE compact row.
            //
            //    ⚠ **AND THE WRAPPING FLEX THAT REPLACED IT WAS NOT ENOUGH
            //    EITHER (DEF-1085).** It fixed the CONTAINER and nothing
            //    measured the CONTENTS: the row still carried search · All ·
            //    + Filter · archive · four route chips · four status chips ·
            //    Download CSV · ▦, which is ~1,360px against the ~1,150px a
            //    1,440px laptop leaves once the shell takes its sidebar. So it
            //    wrapped anyway, after the status chips, and stranded Download
            //    CSV and the ▦ alone on a second line — where the ▦'s panel
            //    then opened off the left edge of the screen.
            //
            //    ⚠ **AND DEF-1085's ANSWER — A SECOND ROW — WAS OVERTURNED BY
            //    THE PRODUCT OWNER THE SAME WEEK (DEF-1700, 2026-08-27):**
            //    *"as per our stadard first raw of tookkit is more than
            //    suficient"*. Both segments are GONE, not moved: `route` and
            //    `status` were already declared `TableConfig.filters` reading
            //    the same option sources (`routeFilterOptions`,
            //    `readStatusFilterOptions`) and writing the same `f.route` /
            //    `f.status` params, so the two chip groups were duplicating the
            //    `+ Filter` panel a few pixels to their left. That is what
            //    resolves DEF-896 and DEF-1085 together rather than trading one
            //    for the other: DEF-896 wanted the two dimensions ONE CLICK
            //    away, and a `+ Filter` panel that opens on a click IS one
            //    click. The ~1,360px row loses ~600px of chips with it, so the
            //    archive opt-in comes back onto row one and row one still fits
            //    the ~1,150px a 1,440px laptop leaves.
            filterBarSlot={
              <>
                <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
                {/* MQ-033 (`CR-192-BRC10` task 13) — *"filterable in Reads
                    lists"*: a question of a published format, then a value.
                    A change clears the selection, as every filter does. */}
                <ReadAnswerFilter
                  answers={answers}
                  dateFormat={dateFormat}
                  client={client}
                  onChange={(next) => {
                    setSelected([]);
                    writeParams({ ...state, page: 1 }, { answers: next });
                  }}
                />
                {/* BR-MET-055: the archive is an EXPLICIT opt-in, and the
                    default view says what window it is showing rather than
                    implying it shows everything. It is NOT a `TableConfig`
                    filter and cannot become one — it rides on its own
                    `?archive=` param outside BR-SHL-011's `f.` namespace,
                    because US-MET-012 TC-10 deliberately keeps it OFF the
                    export state — so unlike the two segments DEF-1700 deleted,
                    this control duplicates nothing in the panel beside it. */}
                <label className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm">
                  <input
                    type="checkbox"
                    checked={archive}
                    onChange={(event) =>
                      writeParams({ ...state, page: 1 }, { archive: event.target.checked })
                    }
                  />
                  {t("metering.reads.archive.label")}
                </label>
              </>
            }
            empty={{
              title: t("metering.reads.emptyTitle"),
              helper: t("metering.reads.emptyHelper"),
              ctaLabel: t("metering.reads.action.upload"),
              ctaReason: null,
              onCta: openUpload,
            }}
            // IS-9 — the capability row's "Export: CSV", live as of CR-038 W5:
            // `reads` is a REGISTERED resource now (the DEF-034 shape closed),
            // and the button posts the table's CURRENT request state, so the
            // file is the list the clerk is looking at (BR-SHL-011). The archive
            // opt-in deliberately does not travel: the export is scoped to the
            // 2-yr hot window (US-MET-012 TC-10).
            //
            // ⚠ **THE TWO SEGMENTS USED TO BE IN HERE AND THAT IS WHY THE ROW
            //    OVERFLOWED (DEF-1085).** The comment they carried said so in
            //    its own words — *"they ride in `downloadSlot` because that is
            //    the only slot the shared toolbar renders AFTER its spacer"* —
            //    and Premises and Units each wrote the same sentence. DEF-1085
            //    moved them to a second row; **DEF-1700 removed them outright**
            //    on the Product Owner's ruling, because both dimensions were
            //    already in `+ Filter`. This slot is the IS-9 export and
            //    nothing else, which is what B14 rule 12 always said.
            //
            // MQ-033 — the answer filters ride in the body's `filters` under
            // the URL's own spelling; the server reads them with the same
            // parser the list uses, so the file is the list on screen.
            downloadSlot={
              <ListExportButton
                resource="reads"
                state={tableState}
                client={client}
              />
            }
          />
          <p className="met-panel-hint">
            {archive ? t("metering.reads.archive.on") : t("metering.reads.archive.off")}
          </p>
        </>
      )}

      {/* S29 is a PAGE now (CR-038 W5) — rows link to it; the legacy
          `?read=<id>` URLs redirect above. The drawer is retired. */}

      {pickingRouteSheet && (
        <RouteSheetModal
          routes={routesQuery.data ?? []}
          cycles={cyclesQuery.data ?? []}
          buildHref={(scope, id) => apiHref(tenantPath(`/${scope}/${id}/route-sheet`))}
          onClose={() => setPickingRouteSheet(false)}
        />
      )}

      {/* CR-038 W5 task 6 — the counter read. Mounted here, at the page's own
          level, so it is a peer of the route-sheet modal rather than something
          the table owns. On a successful post the list is already invalidated
          by the modal's mutation, so the new reading appears behind it. */}
      {/* DEF-897 — three of the four S25 actions opened a dialog and the fourth
          navigated away. It is the fourth dialog now, a peer of the other two. */}
      {estimating && (
        <EstimateReadModal
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onClose={() => setEstimating(false)}
        />
      )}

      {quickEntry && (
        <QuickReadModal
          client={client}
          t={translate}
          dateFormat={dateFormat}
          timeZone={timeZone}
          onClose={() => setQuickEntry(false)}
          onPosted={() => setQuickEntry(false)}
        />
      )}
    </div>
  );
}

// ── The route-sheet picker (CR-038 W5 — RDS-01's header button) ────────────

/** What a sheet can be asked for. The word is also the URL segment. */
export type SheetScope = "routes" | "cycles";

/**
 * **THE ONE PICKER THE ROUTE SHEET ASKS WITH, AND IT BECOMES SEARCHABLE WHEN
 * THE TENANT IS BIG ENOUGH TO NEED IT (`MR-06`, blueprint entry 17).**
 *
 * `MR-06` is one sentence — *"a clerk with hundreds of routes finds one by
 * typing"* — and the blueprint's own read of this branch is that
 * `SearchSelectField` appears in **none** of `UploadReadsWizard.tsx`,
 * `ReadsListPage.tsx`, `EstimateReadModal.tsx` or `RoutesCyclesPage.tsx`. This
 * closes that for the two pickers this dialog owns.
 *
 * ⚠ **THE THRESHOLD IS THE KIT'S OWN CONSTANT AND IS NOT A NUMBER CHOSEN
 * HERE.** `BR-SHL-033` puts it at `LONG_LIST_THRESHOLD = 10`; **B14 rule 8 asks
 * for type-to-filter from FIVE**, and the blueprint names the disagreement as a
 * finding of its own (its row `7-07`) rather than resolving it. A lane may not
 * resolve it either, so this composes the constant the kit declares and the
 * divergence is REPORTED. The practical effect is the one `MR-06` asks for: the
 * six-route tenant sees exactly what it saw before, and a utility at the top of
 * this product's stated range (40,000 accounts — the ICP ceiling moved on
 * 2026-09-06) gets a type-ahead instead of a scroll list.
 *
 * ⚠ **THE `id` IS FIXED AT `target` ON BOTH BRANCHES, DELIBERATELY.**
 * `routeSheetSchema` validates a single `target` key because the field's
 * MEANING depends on the segment beside it (BR-MET-162), and a per-scope id
 * would leave `useFieldError` looking for a field the schema never names.
 */
function TargetPicker(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
  help: string;
}) {
  const shared = {
    id: "target",
    label: props.label,
    required: true,
    value: props.value,
    onChange: props.onChange,
    options: props.options,
    placeholder: props.placeholder,
    help: props.help,
  };
  return props.options.length > LONG_LIST_THRESHOLD ? (
    <SearchSelectField {...shared} />
  ) : (
    <SelectField {...shared} />
  );
}

/**
 * **A SHEET IS PRINTED FOR A ROUTE *OR* FOR A CYCLE (BR-MET-162, DEF-898).**
 *
 * PO 2026-08-27, on the live app: *"allow route of Cycle - both"*. Until today
 * this dialog offered a single required `Choose a route…` and nothing else —
 * while the generated sheet ALREADY printed its cycle in the header (`Cycle
 * SCW-M · System (auto-pull) · 41 stop(s)`). So the cycle was a first-class
 * fact of the artefact with no way to ask for one, and a clerk who works a
 * monthly walk by cycle had to know which routes were on it and print them one
 * at a time.
 *
 * ⚠ **NOTHING CAUGHT IT BECAUSE THE FEATURE WORKS PERFECTLY FOR THE CASE IT
 * WAS BUILT FOR.** Every test asks for a route sheet by route and gets one; a
 * missing ENTRY POINT is invisible to any test that only exercises the entry
 * point that exists.
 *
 * The scope is a segmented choice rather than two buttons, because it is one
 * question with two answers — *what are you holding?* — and the picker below it
 * changes with the answer. Choosing a scope CLEARS the other one's selection,
 * so the schema can never see a route id and a cycle id at once and the sheet
 * that opens is always the one on screen.
 *
 * The href stays same-origin (`/api/{tenant}/{routes|cycles}/{id}/route-sheet`,
 * DEF-532's tenantPath discipline via the caller's `buildHref`), so the session
 * cookie rides along — the same pattern as the bill document's PDF anchor.
 */
export function RouteSheetModal(props: {
  routes: readonly RouteRow[];
  cycles: readonly CycleRow[];
  buildHref: (scope: SheetScope, id: string) => string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [scope, setScope] = useState<SheetScope>("routes");
  const [routeId, setRouteId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const chosen = scope === "routes" ? routeId : cycleId;

  function submit(): Promise<FormSubmitOutcome> {
    // Opened from a user gesture (the modal's submit), so no popup heuristics
    // fire; `noopener` because the sheet needs no handle back into the app.
    window.open(props.buildHref(scope, chosen), "_blank", "noopener");
    return Promise.resolve({ ok: true });
  }

  return (
    <FormModal
      title={t("metering.reads.routeSheet.title")}
      kicker={t("metering.reads.kicker")}
      schema={routeSheetSchema(translate)}
      values={{ scope, target: chosen }}
      submitLabel={t("metering.reads.routeSheet.open")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <SegmentedField
        id="scope"
        label={t("metering.reads.routeSheet.scopeLabel")}
        value={scope}
        onChange={(next) => {
          setScope(next as SheetScope);
          // One question, one answer: switching scope drops the other side's
          // choice so the schema can never hold both.
          setRouteId("");
          setCycleId("");
        }}
        options={[
          { value: "routes", label: t("metering.reads.routeSheet.scopeRoute") },
          { value: "cycles", label: t("metering.reads.routeSheet.scopeCycle") },
        ]}
      />
      {scope === "routes" ? (
        <TargetPicker
          label={t("metering.reads.routeSheet.route")}
          value={routeId}
          onChange={setRouteId}
          options={props.routes.map((route) => ({
            value: route.id,
            label: route.name === null ? route.code : `${route.code} · ${route.name}`,
          }))}
          placeholder={t("metering.reads.routeSheet.pick")}
          help={t("metering.reads.routeSheet.help")}
        />
      ) : (
        <TargetPicker
          label={t("metering.reads.routeSheet.cycle")}
          value={cycleId}
          onChange={setCycleId}
          options={props.cycles.map((cycle) => ({ value: cycle.id, label: cycle.code }))}
          placeholder={t("metering.reads.routeSheet.pickCycle")}
          // BR-MET-162 (3)/(5): what a cycle sheet IS, said before it prints —
          // one section per ACTIVE route, each in its own walk order. A clerk
          // expecting one merged sequence should learn that here, not from the
          // page that comes back.
          help={t("metering.reads.routeSheet.cycleHelp")}
        />
      )}
    </FormModal>
  );
}

/**
 * The one refusal the picker can make: nothing chosen.
 *
 * ⚠ It validates the CHOSEN TARGET, not a named `route` field, because the
 * field's meaning now depends on the scope beside it (BR-MET-162). A schema
 * with one required `route` key could not express "a cycle is also an answer",
 * and adding a second optional key would let a caller submit neither.
 */
export function routeSheetSchema(t: Translator) {
  return z.object({
    scope: z.enum(["routes", "cycles"]),
    target: z.string().min(1, t("metering.reads.routeSheet.required")),
  });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-012@34f14b6 (story+rules snapshot hash — EP-MET-04 list story; co-stories US-MET-019@34f14b6 · US-MET-013@34f14b6)
// generated: 2026-08-11 by story-coder v1 (W2 reads frontend lane — S25/S29, the first screens over the shipped reads engine) · AMENDED 2026-08-27 (DEF-895 the SOURCE cell loses its bracket and its duplicated word · DEF-896 the toolbar becomes r10 RDS-01's ONE row, with a real search placeholder, r10's two right-aligned segments and the stale two-line prose removed · DEF-897 the estimate form is a dialog mounted here · DEF-898 the sheet picker offers route OR cycle)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest 784 passed / 180 todo across 56 files✔ (753 passed / 175 todo across 54 files was the pre-lane baseline — this lane adds 31 passing + 5 todo and dropped nothing) · vite build✔ · G15 5 locales × 2828 keys, identical sets, 11312 values translated or allowlisted✔ · G13 unwired-props 68 components✔ · G10 all 106 Trace-cited stories have TC-named tests✔ · run_gates 14 PASS · 1 FAIL · 1 SKIP — the one FAIL is G1 on SIX 06-backend files from a CONCURRENT ledger lane (apps/ledger/{chart,selectors,services,tenancy_seam}.py, apps/ledger/migrations/0003_gl_designations.py, apps/tenancy/migrations/0006_service_gl_attributes.py) whose Lifecycle trailers carry no `packet:` line. None belongs to this lane and 06-backend is outside this territory, so it is REPORTED rather than touched. (A G8 failure on apps/billing/issue.py:816 citing the unregistered OQ-114 appeared and cleared during this session — also another lane's.) Baseline at the start of this lane: 15 PASS · 0 FAIL · 1 SKIP over 233 traced files; 246 now
// exceptions: [US-MET-013 dispute lane 2026-08-16] the **Disputed chip DRILLS IN** and a `Dispute` filter is declared. Both were absent for one reason and it was the right one at the time: `GET /reads` declared six filters, none of them a dispute marker, and BE-05 IGNORES an undeclared `f.` param — so the button would have returned the WHOLE list while looking like a filtered slice. The server declares `disputed` as of this date. RED-PROVED by disabling the server clause: the TC-4 slice came back 4 rows against a count of 1 (`AssertionError: assert 1 == 4`) · E3 FOUR of the prototype's ten S25 columns are NOT rendered — Cycle, Route, Service and Premise: `selectors.read_dict` builds none of them, and joining raw rows client-side would break BR-MET-016's lineage-head guarantee. The FILTERS for route and cycle ARE served and are offered, so the screen filters on facts it cannot display — reported as the backend's first debt to this screen · E2 a **Read date** column is ADDED, which the prototype's ten do not carry: the list's own default sort is `read_at` and a reading with no date cannot be checked against a bill. Deliberate divergence, reported · E3 the status filter offers OK/Flagged/Estimated and NOT the prototype's fourth choice **Pending**: BR-MET-049 derives Pending from the plan-required record set, `GET /reads` declares no such filter, and BE-05 IGNORES an undeclared `f.` param — a Pending option would silently return every read · E3 the **Service** filter is served (`f.service`) and is NOT rendered: no role-safe endpoint lists the tenant's enabled service codes (`GET /settings/services` is System-Admin-only), so a Billing Clerk would get an empty dropdown. S15 and S49 render that empty dropdown and report it; this screen omits the control per BR-SHL-010. The two postures disagree and the PO should pick one — reported · E3 there is NO Download/export control: `POST /exports` resolves a registered resource and metering registers premises · units · routes · cycles and no `reads`, so the IS-9 export the capability row declares has no backend — reported rather than drawn onto a 404 · E3 both header actions render DISABLED WITH THEIR REASON (BR-SHL-025): "↑ Upload reads" is S28, which this lane did not build, and "Route sheet PDF" is a W6 documents story · E3 the server IGNORES `dir` on `GET /reads` (`selectors.read_list` takes no direction argument) and its effective default ordering is read_at ASCENDING, not the `read_at desc` its own `READ_DEFAULT_SORT` and the capability row declare — the request carries the declared sort so nothing changes here when the server honours it; REPORTED as a defect · E4 the row's affordance into S29 is the identity cell, not the whole row as in the prototype: every other list in this app (S14/S15/S49) opens its detail from the identity cell, and DataTable has no row-click contract to add one to
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
