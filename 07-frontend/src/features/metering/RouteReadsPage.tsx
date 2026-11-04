// ── Trace ──────────────────────────────────────────────
// Screen:  Meter Reads blueprint entry 21 — **A ROUTE, THE DETAIL**, a screen
//          that did not exist. `/:tenant/reads/routes/:routeId?window=YYYY-MM`.
// Change:  PO ruling 2026-09-13, verbatim: *"in this Route Tab - what if User
//          click on Route link - we will have to give a details view of Route.
//          this view should be similar to details view of Cycle. in Cycle you
//          will need to add a tab - all reads and same in route details also."*
//          **OPTION A** — its own address with the window in the header, not a
//          panel nested under the cycle page.
// Drawing: blueprint pages 49–53, read AS IMAGES (B14 rule 42).
// Rules:   BR-MET-010 (a route is on exactly one cycle AT A TIME — the history
//          therefore spans more than one) · BR-MET-011 CONFIRMED-AS-NARROWED
//          2026-09-14 (route configuration is DEFINITION and stays in Settings;
//          the reading WORK is the operational screen's) · BR-MET-026 (a demand
//          register is never estimated) · BR-MET-049 (the plan drives the
//          required register set) · BR-MET-055 (server pagination, no unbounded
//          read endpoint) · BR-MET-057 (the read window drives expectations —
//          completeness + chase list) · BR-MET-073 (a route carries a service,
//          an area, a reader and notes) · BR-MET-075 (a meter may be EXCLUDED
//          and stays on its premises) · CR-029 D11 (the walk is numbered PER
//          PREMISES, never per unit) · BR-SHL-011 (the open tab is URL state) ·
//          BR-SHL-020 (the A18 states) · NFR-3 (server pagination).
// B14:     rule 1 (the ← names where it EXITS to) · 2 (one page header) ·
//          12 (one toolbar row) · 15 (icon row actions — none on this screen) ·
//          16 (a pagination footer on every list table) · 21 (Tailwind, and
//          this file adds NO class to any stylesheet — it is on
//          `styles/route-b-migrated.txt`) · 31 (no database id on screen —
//          `RT-005`, never a uuid) · 32 (one sentence per section) ·
//          33 (on-screen text capped by what it is for; RATIONALE is zero
//          words) · 36 (compose the kit) · 37 (a drawn figure is an
//          illustration) · 38 (the UI rules build the form) · 39 (one spacing
//          scale) · 40 (the page-head title is 32px, which is why this screen
//          composes the shared `PageHeader` and not `meteringShared.PageHead`).
// ───────────────────────────────────────────────────────
/**
 * **WHY A ROUTE NEEDS A PAGE, AND WHY IT NEEDS A WINDOW WITH IT.**
 *
 * A route can be walked on MORE THAN ONE CYCLE. `"0 of 11 collected"` has no
 * denominator until a window is named, so the window this page is measured
 * against rides in the header and in the address — which is the one control the
 * cycle page does not need, and the whole reason option A was chosen. A ticket
 * can link straight at `?window=2026-09`; the old Routes tab had no address
 * anybody could paste and that is how it became an orphan.
 *
 * ⚠ **WHAT THIS SCREEN DELIBERATELY DOES NOT WRITE, AND THE RULING FOR EACH.**
 *
 *   · **THE WALK ORDER IS READ-ONLY HERE.** `BR-MET-011` was narrowed by the PO
 *     on 2026-09-14 and the narrowing was put the other way round for routes,
 *     verbatim: *"Settings only"* — route configuration is DEFINITION. The
 *     Settings route detail (`features/tenancy/RouteDetailPage.tsx`) already
 *     writes it through `PUT /routes/{id}/premises-order`, so honouring this
 *     costs nothing: the Stops tab prints the ruled order and points at the one
 *     screen that sets it.
 *
 *   · **NO *Send someone out* CONTROL.** It is drawn on the Still-to-read bulk
 *     bar and drawn DISABLED. `BR-WRK-055` requires metering's own disposition
 *     to be written BEFORE anything is raised, and a chase row is DERIVED — it
 *     carries no id and there is no record to write a disposition on. The door
 *     that does exist is the one the upload wizard opens on the stage-3
 *     shortfall, over staged rows that do have one.
 *
 *   · **NO *Estimate these* BULK CONTROL, AND THEREFORE NO TICK COLUMN.** The
 *     blueprint's own annotation calls it *"the same control as entry 20"*, so
 *     it belongs to the cycle page and a second one here is hard-won law 5. A
 *     dead tick column would be hard-won law 2, so it goes with it.
 *
 * ⚠ **THREE THINGS THE DRAWING SHOWS THAT ARE NOT BUILT, EACH BECAUSE A SIGNED
 * RULING SAYS OTHERWISE OR BECAUSE NOTHING SERVES THEM. They are reported, not
 * silently dropped** (B14 rule 41: a drawing that contradicts a signed rule is
 * the one thing that reaches the PO).
 *
 *   1. **THE READER — drawn three times, ruled away twice.** `CR-029` D6 (PO
 *      2026-08-23, *"not required"*) records that `routes.assigned_to` *"keeps
 *      its value, no control writes it, and no row renders it"*; `OQ-343` the
 *      same day, PO verbatim: *"B: no reader anywhere, correct the screenshot
 *      and drop the stored name"* — and `read_windows.reader` was dropped by
 *      migration, so the History tab's Reader column has no column behind it.
 *      The blueprint draws a reader chip in the header, a Reader row in The
 *      walk and a Reader column in History. **None is built.**
 *      ⚠ 2026-10-24 (PO, MQ-033, `DEF-MET-10591`): D6 and `OQ-343` are
 *      SUPERSEDED FOR THE CYCLE'S ROUTES TAB ONLY — the reader is shown and
 *      assigned there (`ReadCycleDetailPage`, `AssignReaderModal`), so
 *      `routes.assigned_to` IS written now. This page was not in that ruling
 *      and is unchanged; the History Reader stays dropped. Whether the header
 *      chip and The walk's Reader row follow is not ruled — not built here.
 *   2. **`REGISTERS COLLECTED · 0 of 11`.** `completeness.cycle_coverage`
 *      computes `expected_channels` per meter and `chase_list` does not
 *      serialise it, so there is no route-scoped denominator on any endpoint.
 *      The tile therefore states the number that IS served and IS the one a
 *      supervisor acts on — the registers still SHORT — rather than inventing a
 *      denominator (`collected_read_count`'s own posture: *"the tab renders
 *      '—', never a fabricated 0"*).
 *   3. **`LAST READ` per stop and `PLAN` / `LAST ACTUAL` on the shortfall.**
 *      A chase row carries neither, and a per-meter last read would be one
 *      request per meter. The route's own last completion is served and is in
 *      the header line, where it is true.
 */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getCycleChaseList,
  getCycles,
  getReads,
  getRouteDetail,
  getRouteMeterPicker,
  getRouteReadWindows,
} from "@/api/endpoints";
import type {
  CycleRow,
  ReadChaseRow,
  ReadRow,
  RouteDetail,
  RoutePickerMeter,
  RouteReadWindowRow,
} from "@/api/endpoints";
import { ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { SelectField, SearchSelectField, LONG_LIST_THRESHOLD } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { frequencyLabel, routeDetailPath } from "@/features/tenancy/routesCyclesShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DASHBOARD_ROUTE,
  Dash,
  PREMISES_PERMISSION,
  isDenied,
  useAccessCell,
  useRegional,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";
import { READS_ROUTE, READS_UPLOAD_ROUTE, readDetailPath } from "./readsShared";

// ── Addresses ──────────────────────────────────────────────────────────────

/** The route's own operational address — **option A**. Tenant-relative. */
export const ROUTE_READS_ROUTE_PATTERN = `${READS_ROUTE}/routes/:routeId`;

/** ⚠ THE ID IN THE PATH IS NOT ON SCREEN (B14 rule 31). The title is the route
 *  CODE; the uuid only ever addresses the row. */
export function routeReadsPath(routeId: string, window?: string | null): string {
  const suffix = window === undefined || window === null || window === "" ? "" : `?window=${window}`;
  return `${READS_ROUTE}/routes/${encodeURIComponent(routeId)}${suffix}`;
}

/** `?window=YYYY-MM` — the period this whole page is measured against. */
export const WINDOW_PARAM = "window";
/** `?tab=` — BR-SHL-011: the open tab is URL state, so a tab is linkable. */
export const TAB_PARAM = "tab";

/** The query keys, EXPORTED so a test seeds exactly what the screen reads —
 *  a test that seeds a key the screen does not use is green over a screen that
 *  fetched nothing (hard-won law 7's *incapable of failing* shape). */
export const routeReadsDetailKey = (routeId: string) =>
  ["route-reads", "detail", routeId] as const;
export const routeReadsWindowsKey = (routeId: string) =>
  ["route-reads", "windows", routeId] as const;
export const routeReadsCyclesKey = ["route-reads", "cycles"] as const;
export const routeReadsChaseKey = (cycleId: string, period: string) =>
  ["route-reads", "chase", cycleId, period] as const;
// ⚠ **THE UNIT-ID SEGMENT IS GONE (`CR-131-BRC07`).** It existed because the
// meter list was asked for BY UNIT, so two different member sets had to be two
// cache entries. The question is now *"this route's meters"*, which the route
// id alone identifies — and a key carrying a value nothing varies is a key
// that looks like it caches per selection and does not.
export const routeReadsMetersKey = (routeId: string) =>
  ["route-reads", "meters", routeId] as const;
export const routeReadsListKey = (routeId: string, state: string) =>
  ["route-reads", "reads", routeId, state] as const;

export const ROUTE_READS_TABS = ["overview", "stops", "short", "reads", "history"] as const;
export type RouteReadsTab = (typeof ROUTE_READS_TABS)[number];

export function routeReadsTabFrom(raw: string | null): RouteReadsTab {
  const found = ROUTE_READS_TABS.find((tab) => tab === raw);
  return found ?? "overview";
}

// ── Pure pieces, so every one of them is provable without a browser ────────

/** `2026-09-01` → `2026-09`. The window param is a MONTH, because that is what
 *  `GET /cycles/{id}/chase-list?period=` takes. */
export function monthOf(isoDate: string | null): string | null {
  if (isoDate === null || isoDate.length < 7) return null;
  return isoDate.slice(0, 7);
}

/** One selectable window — a period, and the cycle it was walked for. */
export interface WindowOption {
  /** `YYYY-MM` — what rides in the address. */
  month: string;
  cycleId: string | null;
  periodStart: string;
  periodEnd: string;
}

/**
 * The windows a person may measure this route against: the OPEN one (from the
 * cycle's own coverage) plus every closed one on record, newest first.
 *
 * ⚠ **DEDUPED BY MONTH, NOT BY ROW.** A route walked on two cycles has two
 * records for one calendar month only if both cycles ran that month, and the
 * selector must not offer the same month twice with no way to tell them apart.
 * The OPEN window wins the tie because it is the one the page defaults to.
 */
export function windowOptions(
  open: { month: string; cycleId: string | null; periodStart: string; periodEnd: string } | null,
  history: readonly RouteReadWindowRow[],
): WindowOption[] {
  const byMonth = new Map<string, WindowOption>();
  if (open !== null) {
    byMonth.set(open.month, open);
  }
  for (const row of history) {
    const month = monthOf(row.period_start);
    if (month === null || byMonth.has(month)) continue;
    byMonth.set(month, {
      month,
      cycleId: row.cycle_id,
      periodStart: row.period_start,
      periodEnd: row.period_end,
    });
  }
  return [...byMonth.values()].sort((a, b) => b.month.localeCompare(a.month));
}

/** One stop of the walk — the ruled PER-PREMISES grain (CR-029 D11). */
export interface RouteStopRow {
  /** The walk position. `null` for a premises the walk skips entirely. */
  stopNo: number | null;
  premisesId: string;
  /** The premises' own address, walked to rather than composed (hard rule 8). */
  address: string | null;
  unitLabels: string[];
  meters: { assetId: string; meterNo: string | null; excluded: boolean; reason: string | null }[];
  services: string[];
  /** The registers this stop still owes, BY NAME — never a bare count. */
  shortChannels: string[];
}

/**
 * Fold the three served payloads into one row per premises.
 *
 * `premises_order` gives the ruled walk; `membership` says which units hang off
 * each premises; the meter picker says which meters those units bring and which
 * are EXCLUDED (BR-MET-075); the chase rows say what is still short.
 *
 * ⚠ **A PREMISES THE ROUTE SKIPS KEEPS ITS ROW.** A stop that vanishes from a
 * walk is a stop a reader will look for, so an all-excluded premises is drawn
 * with no stop number rather than dropped.
 */
export function stopRows(
  detail: RouteDetail,
  meters: readonly RoutePickerMeter[],
  chase: readonly ReadChaseRow[],
): RouteStopRow[] {
  const orderByPremises = new Map<string, number>();
  for (const stop of detail.premises_order) {
    orderByPremises.set(stop.premises_id, stop.walk_order);
  }
  const shortByAsset = new Map<string, string[]>();
  for (const row of chase) {
    if (row.asset_id === null) continue;
    shortByAsset.set(row.asset_id, row.missing_channels);
  }
  const unitsByPremises = new Map<string, string[]>();
  const addressByPremises = new Map<string, string | null>();
  for (const member of detail.membership) {
    const labels = unitsByPremises.get(member.premises_id) ?? [];
    if (!labels.includes(member.unit_label)) labels.push(member.unit_label);
    unitsByPremises.set(member.premises_id, labels);
  }
  const metersByPremises = new Map<string, RouteStopRow["meters"]>();
  const servicesByPremises = new Map<string, string[]>();
  for (const meter of meters) {
    addressByPremises.set(meter.premises_id, meter.address_line);
    const list = metersByPremises.get(meter.premises_id) ?? [];
    list.push({
      assetId: meter.id,
      meterNo: meter.asset_no,
      excluded: meter.excluded,
      reason: meter.exclusion_reason,
    });
    metersByPremises.set(meter.premises_id, list);
    if (meter.service_code !== null) {
      const services = servicesByPremises.get(meter.premises_id) ?? [];
      if (!services.includes(meter.service_code)) services.push(meter.service_code);
      servicesByPremises.set(meter.premises_id, services);
    }
  }

  const premisesIds = [...new Set(detail.membership.map((member) => member.premises_id))];
  for (const stop of detail.premises_order) {
    if (!premisesIds.includes(stop.premises_id)) premisesIds.push(stop.premises_id);
  }

  return premisesIds
    .map((premisesId): RouteStopRow => {
      const stopMeters = metersByPremises.get(premisesId) ?? [];
      const short = stopMeters
        .filter((meter) => !meter.excluded)
        .flatMap((meter) => shortByAsset.get(meter.assetId) ?? []);
      return {
        stopNo: orderByPremises.get(premisesId) ?? null,
        premisesId,
        address: addressByPremises.get(premisesId) ?? null,
        unitLabels: unitsByPremises.get(premisesId) ?? [],
        meters: stopMeters,
        services: servicesByPremises.get(premisesId) ?? [],
        shortChannels: [...new Set(short)],
      };
    })
    .sort((a, b) => {
      // A skipped stop has no position in the walk, so it sorts to the end
      // rather than to the front, which a null-as-zero comparison would do.
      if (a.stopNo === null && b.stopNo === null) return 0;
      if (a.stopNo === null) return 1;
      if (b.stopNo === null) return -1;
      return a.stopNo - b.stopNo;
    });
}

export type StopState = "excluded" | "short" | "walked" | "no_meter";

/** What a stop's STATUS cell says, and it is derived rather than stored. */
export function stopState(row: RouteStopRow): StopState {
  if (row.meters.length === 0) return "no_meter";
  if (row.meters.every((meter) => meter.excluded)) return "excluded";
  return row.shortChannels.length > 0 ? "short" : "walked";
}

const STOP_TONE: Record<StopState, StatusTone> = {
  excluded: "neutral",
  short: "warning",
  walked: "success",
  no_meter: "neutral",
};

/** The window's own state word, from the served window rather than from a clock
 *  in the browser: `before_open` · `open` · `closed`. */
export function windowStateKey(state: string | null | undefined): string {
  if (state === "before_open" || state === "open" || state === "closed") return state;
  return "unknown";
}

/** A closed window's verdict, or *in progress* while it is still open. */
export function historyStatus(row: RouteReadWindowRow): { key: string; tone: StatusTone } {
  if (row.closed_at === null) return { key: "in_progress", tone: "warning" };
  if (row.result === "Complete") return { key: "complete", tone: "success" };
  if (row.result === "Incomplete") return { key: "incomplete", tone: "warning" };
  return { key: "closed", tone: "neutral" };
}

// ── Small shared bits of markup ────────────────────────────────────────────

const FACT_ROW = "flex items-baseline justify-between gap-3 border-b border-divider py-2 last:border-0";
const FACT_LABEL = "text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
const FACT_VALUE = "text-sm font-medium tabular-nums";
const PANEL_NOTE = "m-0 mt-3 max-w-measure text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

function Fact(props: { label: string; value: ReactNode }) {
  return (
    <div className={FACT_ROW}>
      <span className={FACT_LABEL}>{props.label}</span>
      <span className={FACT_VALUE}>{props.value}</span>
    </div>
  );
}

/** The register names, translated, joined — never a bare count (hard rule 3's
 *  spirit: a quantity carries its meaning). */
function channelWords(channels: readonly string[], t: Translator): string {
  return channels
    .map((channel) => t(`metering.reads.channel.${channel}`, { defaultValue: channel }))
    .join(" · ");
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface RouteReadsPageProps extends RegionalProps {
  client?: ApiClient;
}

export function RouteReadsPage(props: RouteReadsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const [searchParams, setSearchParams] = useSearchParams();
  const routeId = useParams().routeId ?? "";
  const cell = useAccessCell(PREMISES_PERMISSION, client);

  const tab = routeReadsTabFrom(searchParams.get(TAB_PARAM));
  const windowParam = searchParams.get(WINDOW_PARAM);

  const detailQuery = useQuery({
    queryKey: routeReadsDetailKey(routeId),
    queryFn: () => getRouteDetail(routeId, client),
    enabled: routeId !== "",
  });
  const historyQuery = useQuery({
    queryKey: routeReadsWindowsKey(routeId),
    queryFn: () => getRouteReadWindows(routeId, client),
    enabled: routeId !== "",
  });
  const cyclesQuery = useQuery({
    queryKey: routeReadsCyclesKey,
    queryFn: () => getCycles(client),
  });

  const detail = detailQuery.data;
  const history = historyQuery.data ?? [];
  const cycleById = useMemo(() => {
    const map = new Map<string, CycleRow>();
    for (const cycle of cyclesQuery.data ?? []) map.set(cycle.id, cycle);
    return map;
  }, [cyclesQuery.data]);

  // The window the page is measured against. `?window=` wins; absent, the page
  // opens on the route's own cycle — *"defaulting to the cycle you arrived
  // from"* — and the chase list answers which period that currently is.
  const historyOption = history.find((row) => monthOf(row.period_start) === windowParam) ?? null;
  const chaseCycleId = historyOption?.cycle_id ?? detail?.cycle_id ?? null;
  const chaseQuery = useQuery({
    queryKey: routeReadsChaseKey(chaseCycleId ?? "", windowParam ?? ""),
    queryFn: () =>
      getCycleChaseList(
        chaseCycleId ?? "",
        windowParam === null ? {} : { period: windowParam },
        client,
      ),
    enabled: chaseCycleId !== null,
  });

  const chase = chaseQuery.data ?? null;
  const openWindow =
    chase?.window == null
      ? null
      : {
          month: monthOf(chase.window.period_start) ?? "",
          cycleId: chase.cycle_id,
          periodStart: chase.window.period_start,
          periodEnd: chase.window.period_end,
        };
  const options = windowOptions(openWindow, history);
  const selectedMonth = windowParam ?? openWindow?.month ?? options[0]?.month ?? "";
  const selected = options.find((option) => option.month === selectedMonth) ?? null;

  // The shortfall, narrowed to THIS route. The chase list is the cycle's and is
  // bounded by the cycle's own membership (BR-MET-055's posture); the route is a
  // subset of it, so no unbounded request is made to narrow it.
  const routeChase = useMemo<ReadChaseRow[]>(() => {
    if (chase === null || detail === undefined) return [];
    return chase.rows.filter((row) => row.route === detail.code);
  }, [chase, detail]);

  // ⚠ **THE ROUTE IS ASKED ABOUT ITSELF (`CR-131-BRC07` step 5).** This sent
  // one `unit_id` per member and the URL outgrew the server's limit on any
  // real property; and it was `enabled` only once the membership had arrived,
  // so a route whose detail call failed drew an empty stop list rather than
  // saying anything. Both go with the unit ids.
  const metersQuery = useQuery({
    queryKey: routeReadsMetersKey(routeId),
    queryFn: () => getRouteMeterPicker({ routeId, per: "all" }, client),
    enabled: routeId !== "",
  });

  const stops = useMemo(
    () =>
      detail === undefined ? [] : stopRows(detail, metersQuery.data?.meters ?? [], routeChase),
    [detail, metersQuery.data, routeChase],
  );

  function writeParam(name: string, value: string | null): void {
    const next = new URLSearchParams(searchParams);
    if (value === null || value === "") next.delete(name);
    else next.set(name, value);
    setSearchParams(next, { replace: true });
  }

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.reads.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (detailQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  if (detail === undefined) {
    if (isPermissionDenied(detailQuery.error)) {
      return (
        <PermissionDenied
          helper={t("metering.reads.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    return (
      <FailedWithRetry
        title={t("metering.routeReads.failedTitle")}
        reason={apiErrorText(detailQuery.error, translate)}
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void detailQuery.refetch()}
      />
    );
  }

  const shortChannelCount = routeChase.reduce((sum, row) => sum + row.missing_channels.length, 0);
  const shortMeterCount = new Set(routeChase.map((row) => row.asset_id ?? row.unit_id)).size;
  const cycleCode =
    (selected?.cycleId === null || selected?.cycleId === undefined
      ? null
      : (cycleById.get(selected.cycleId)?.code ?? null)) ?? detail.cycle_code;

  // Every cycle this route has been walked on: the one it is assigned to today
  // (BR-MET-010 — exactly one AT A TIME) plus every cycle its closed windows
  // name. That list only exists at this level; a cycle page can never show it.
  const walkedCycleIds = [
    ...new Set(
      [detail.cycle_id, ...history.map((row) => row.cycle_id)].filter(
        (id): id is string => id !== null,
      ),
    ),
  ];

  const tabs = [
    { id: "overview", label: t("metering.routeReads.tab.overview") },
    { id: "stops", label: t("metering.routeReads.tab.stops"), count: stops.length },
    {
      id: "short",
      label: t("metering.routeReads.tab.short"),
      count: routeChase.length,
    },
    { id: "reads", label: t("metering.routeReads.tab.reads") },
    { id: "history", label: t("metering.routeReads.tab.history"), count: history.length },
  ];

  const sheetHref = apiHref(tenantPath(`/routes/${routeId}/route-sheet`));

  return (
    <div className="px-4 pb-8 pt-6">
      <PageHeader
        // B14 rule 1 — the ← names where it EXITS to, and that is the cycle the
        // person arrived from, not the previous tab.
        backTo={{
          to: tenantPath(`${READS_ROUTE}/cycles`),
          label: cycleCode ?? t("metering.routeReads.backCycles"),
          testId: "route-reads-back",
        }}
        kicker={t("metering.routeReads.kicker", { name: detail.name ?? detail.code })}
        // B14 rule 31 — the route's issued CODE, never its uuid.
        title={detail.code}
        status={
          <StatusPill tone={windowStateTone(chase?.window?.state ?? null)}>
            {t(`metering.routeReads.window.${windowStateKey(chase?.window?.state)}`)}
          </StatusPill>
        }
        rollup={
          <>
            {t("metering.routeReads.rollup", {
              stops: stops.length,
              meters: detail.meters,
              short: shortChannelCount,
            })}
            {detail.last_completion !== null && (
              <>
                {" · "}
                {t("metering.routeReads.lastRead")}{" "}
                <DateCell
                  value={detail.last_completion}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                />
              </>
            )}
          </>
        }
        secondaryActions={
          <ButtonLink variant="secondary" to={sheetHref} target="_blank" rel="noreferrer">
            {t("metering.routeReads.sheet")}
          </ButtonLink>
        }
        primaryAction={
          <ButtonLink to={tenantPath(READS_UPLOAD_ROUTE)}>
            {t("metering.routeReads.upload")}
          </ButtonLink>
        }
        tabs={tabs}
        activeTabId={tab}
        onTabSelect={(next) => writeParam(TAB_PARAM, next.id === "overview" ? null : next.id)}
        tabsLabel={t("metering.routeReads.tabsLabel")}
      />

      {/* ⚠ **THE ONE CONTROL A CYCLE PAGE DOES NOT NEED.** B14 rule 38 — where a
          drawing and our UI rules disagree about how a FORM is built, the UI
          rules win: the blueprint draws this label inline to the left of the
          selector and the kit puts a label above its input, so it is a field. */}
      <div className="mb-6 max-w-sm">
        <WindowPicker
          options={options}
          value={selectedMonth}
          onChange={(month) => writeParam(WINDOW_PARAM, month)}
          cycleById={cycleById}
          timeZone={timeZone}
          dateFormat={dateFormat}
          t={translate}
        />
      </div>

      {tab === "overview" && (
        <OverviewTab
          shortChannels={shortChannelCount}
          shortMeters={shortMeterCount}
          meters={detail.meters}
          stops={stops.length}
          excludedMeters={detail.meters_excluded}
          windowState={chase?.window?.state ?? null}
          periodStart={selected?.periodStart ?? null}
          periodEnd={selected?.periodEnd ?? null}
          chaseRows={routeChase}
          walkedCycleIds={walkedCycleIds}
          cycleById={cycleById}
          loading={chaseQuery.isPending}
          onOpenStops={() => writeParam(TAB_PARAM, "stops")}
          settingsHref={tenantPath(routeDetailPath(routeId))}
          timeZone={timeZone}
          dateFormat={dateFormat}
          t={translate}
        />
      )}

      {tab === "stops" && (
        <StopsTab rows={stops} loading={metersQuery.isPending} t={translate} />
      )}

      {tab === "short" && (
        <ShortTab
          rows={routeChase}
          stops={stops}
          loading={chaseQuery.isPending}
          t={translate}
        />
      )}

      {tab === "reads" && (
        <AllReadsTab
          routeId={routeId}
          routeCode={detail.code}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          t={translate}
        />
      )}

      {tab === "history" && (
        <HistoryTab
          rows={history}
          loading={historyQuery.isPending}
          cycleById={cycleById}
          timeZone={timeZone}
          dateFormat={dateFormat}
          t={translate}
        />
      )}
    </div>
  );
}

function windowStateTone(state: string | null): StatusTone {
  if (state === "open") return "warning";
  if (state === "closed") return "neutral";
  if (state === "before_open") return "info";
  return "muted";
}

// ── The window picker ──────────────────────────────────────────────────────

function WindowPicker(props: {
  options: readonly WindowOption[];
  value: string;
  onChange: (month: string) => void;
  cycleById: Map<string, CycleRow>;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { t } = props;
  const options = props.options.map((option) => ({
    value: option.month,
    label:
      (option.cycleId === null ? null : (props.cycleById.get(option.cycleId)?.code ?? null)) === null
        ? `${option.periodStart} – ${option.periodEnd}`
        : `${props.cycleById.get(option.cycleId ?? "")?.code ?? ""} · ${option.periodStart} – ${option.periodEnd}`,
  }));
  // B14 rule 8 / BR-SHL-033 — past the kit's own threshold the control is the
  // searchable one. A route walked monthly for two years has twenty-four.
  const Field = options.length > LONG_LIST_THRESHOLD ? SearchSelectField : SelectField;
  return (
    <Field
      id="route-reads-window"
      label={t("metering.routeReads.measuredAgainst")}
      value={props.value}
      onChange={props.onChange}
      options={options}
      placeholder={t("metering.routeReads.windowNone")}
    />
  );
}

// ── Overview ───────────────────────────────────────────────────────────────

function OverviewTab(props: {
  shortChannels: number;
  shortMeters: number;
  meters: number;
  stops: number;
  excludedMeters: number;
  windowState: string | null;
  periodStart: string | null;
  periodEnd: string | null;
  chaseRows: readonly ReadChaseRow[];
  walkedCycleIds: readonly string[];
  cycleById: Map<string, CycleRow>;
  loading: boolean;
  onOpenStops: () => void;
  settingsHref: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { t } = props;
  return (
    <>
      <Panel title={t("metering.routeReads.collection")}>
        <KPIStrip
          loading={props.loading}
          kpis={[
            {
              id: "short-registers",
              label: t("metering.routeReads.kpi.shortRegisters"),
              value: props.shortChannels,
            },
            {
              id: "short-meters",
              label: t("metering.routeReads.kpi.shortMeters"),
              value: props.shortMeters,
              detail: t("metering.routeReads.kpi.ofMeters", { total: props.meters }),
            },
            {
              id: "window",
              label: t("metering.routeReads.kpi.window"),
              value: t(`metering.routeReads.window.${windowStateKey(props.windowState)}`),
              detail:
                props.periodStart === null || props.periodEnd === null ? undefined : (
                  <>
                    <DateCell
                      value={props.periodStart}
                      timeZone={props.timeZone}
                      dateFormat={props.dateFormat}
                    />
                    {" – "}
                    <DateCell
                      value={props.periodEnd}
                      timeZone={props.timeZone}
                      dateFormat={props.dateFormat}
                    />
                  </>
                ),
            },
          ]}
        />
        {props.chaseRows.length > 0 && (
          <p className={PANEL_NOTE}>
            {t("metering.routeReads.shortRegisters")}{" "}
            {props.chaseRows
              .map(
                (row) =>
                  `${channelWords(row.missing_channels, t)} · ${row.meter ?? ""}`.trim(),
              )
              .join(" · ")}
          </p>
        )}
      </Panel>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title={t("metering.routeReads.theWalk")}>
          <Fact label={t("metering.routeReads.fact.stops")} value={props.stops} />
          <Fact label={t("metering.routeReads.fact.meters")} value={props.meters} />
          <Fact label={t("metering.routeReads.fact.excluded")} value={props.excludedMeters} />
          {/* ⚠ **THE WALK IS SET IN SETTINGS AND THIS SCREEN DOES NOT SET IT** —
              PO 2026-09-14, verbatim: *"Settings only"*. The pointer is the
              whole of what belongs on screen; WHY it is there is rationale and
              rationale is zero words (B14 rule 33). */}
          <p className={PANEL_NOTE}>
            {t("metering.routeReads.walkNote")}{" "}
            <button type="button" className="text-accent underline" onClick={props.onOpenStops}>
              {t("metering.routeReads.seeStops")}
            </button>
            {" · "}
            <Link className="text-accent underline" to={props.settingsHref}>
              {t("metering.routeReads.manageInSettings")}
            </Link>
          </p>
        </Panel>

        <Panel title={t("metering.routeReads.cycles")}>
          {props.walkedCycleIds.length === 0 ? (
            <p className={PANEL_NOTE}>{t("metering.routeReads.noCycles")}</p>
          ) : (
            props.walkedCycleIds.map((cycleId) => {
              const cycle = props.cycleById.get(cycleId);
              return (
                <Fact
                  key={cycleId}
                  label={cycle?.code ?? t("metering.routeReads.cycleUnknown")}
                  value={
                    cycle === undefined ? (
                      <Dash />
                    ) : (
                      frequencyLabel(cycle.frequency, t, "—")
                    )
                  }
                />
              );
            })
          )}
          <p className={PANEL_NOTE}>{t("metering.routeReads.cyclesNote")}</p>
        </Panel>
      </div>
    </>
  );
}

// ── A table of things already in memory ────────────────────────────────────

/**
 * The state every one of the three in-memory tables carries.
 *
 * ⚠ **NFR-3 IS NOT BENT HERE AND THE DISTINCTION MATTERS.** `GET /routes/{id}`,
 * `GET /routes/{id}/read-windows` and `GET /cycles/{id}/chase-list` are each
 * BOUNDED BY THE ROUTE OR ITS CYCLE and each answers in one request — they are
 * not list endpoints and have no `page` parameter to pass. The pager below
 * pages what has already arrived, which is exactly what `RoutesOpsPage` records
 * about its own. The ONE list endpoint this screen calls, `GET /reads`, is
 * server-paged, and its table passes its state straight through.
 */
function useLocalTableState(sort: string): [TableRequestState, (next: TableRequestState) => void] {
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort,
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  return [state, setState];
}

/** Search, filter, sort and page an in-memory list the way the server would. */
function applyLocally<Row>(
  rows: readonly Row[],
  state: TableRequestState,
  match: (row: Row, q: string) => boolean,
  filter: (row: Row, filters: Record<string, string>) => boolean,
): { page: Row[]; total: number } {
  const q = state.q.trim().toLowerCase();
  const found = rows.filter(
    (row) => (q === "" || match(row, q)) && filter(row, state.filters),
  );
  const from = (state.page - 1) * state.per;
  return { page: found.slice(from, from + state.per), total: found.length };
}

// ── Stops ──────────────────────────────────────────────────────────────────

function StopsTab(props: { rows: readonly RouteStopRow[]; loading: boolean; t: Translator }) {
  const { t } = props;
  const [state, setState] = useLocalTableState("stop");
  const { page, total } = applyLocally(
    props.rows,
    state,
    (row, q) =>
      (row.address ?? "").toLowerCase().includes(q) ||
      row.unitLabels.some((label) => label.toLowerCase().includes(q)) ||
      row.meters.some((meter) => (meter.meterNo ?? "").toLowerCase().includes(q)),
    () => true,
  );

  const config: TableConfig<RouteStopRow> = {
    screenId: "MR-21.stops",
    getRowId: (row) => row.premisesId,
    searchFields: ["premises", "unit", "meter"],
    searchPlaceholder: "metering.routeReads.stops.search",
    defaultSort: { sort: "stop", dir: "asc" },
    columns: [
      {
        key: "stop",
        label: t("metering.routeReads.col.stop"),
        numeric: true,
        identity: true,
        cell: (row) => (row.stopNo === null ? <Dash /> : row.stopNo),
      },
      {
        key: "premises",
        label: t("metering.routeReads.col.premises"),
        cell: (row) => row.address ?? <Dash />,
      },
      {
        key: "unit",
        label: t("metering.routeReads.col.unit"),
        cell: (row) => (row.unitLabels.length === 0 ? <Dash /> : row.unitLabels.join(" · ")),
      },
      {
        key: "meter",
        label: t("metering.reads.col.meter"),
        cell: (row) =>
          row.meters.length === 0 ? (
            <Dash />
          ) : (
            <>
              {row.meters.map((meter, index) => (
                <span key={meter.assetId}>
                  {index > 0 && " · "}
                  {/* BR-MET-075 — an excluded meter says so in place, with the
                      reason the exclusion carries, on `title` where a long
                      sentence cannot set the row's height. */}
                  <span
                    className={meter.excluded ? "line-through" : undefined}
                    title={meter.reason ?? undefined}
                  >
                    {meter.meterNo ?? ""}
                  </span>
                </span>
              ))}
            </>
          ),
      },
      {
        key: "service",
        label: t("metering.reads.col.service"),
        cell: (row) => (row.services.length === 0 ? <Dash /> : row.services.join(" · ")),
      },
      {
        key: "short",
        label: t("metering.routeReads.col.shortRegisters"),
        cell: (row) =>
          row.shortChannels.length === 0 ? <Dash /> : channelWords(row.shortChannels, t),
      },
      {
        key: "status",
        label: t("metering.reads.col.status"),
        cell: (row) => {
          const key = stopState(row);
          return <StatusPill tone={STOP_TONE[key]}>{t(`metering.routeReads.stop.${key}`)}</StatusPill>;
        },
      },
    ],
  };

  return (
    <DataTable
      config={config}
      state={state}
      onStateChange={setState}
      rows={page}
      totalRows={total}
      loading={props.loading}
      empty={{
        title: t("metering.routeReads.stops.emptyTitle"),
        helper: t("metering.routeReads.stops.emptyHelper"),
      }}
    />
  );
}

// ── Still to read ──────────────────────────────────────────────────────────

function ShortTab(props: {
  rows: readonly ReadChaseRow[];
  stops: readonly RouteStopRow[];
  loading: boolean;
  t: Translator;
}) {
  const { t } = props;
  const [state, setState] = useLocalTableState("days");

  // CR-029 D11 — the stop number, which is the one column the cycle-level chase
  // list cannot have and the only one that tells a reader the order to walk.
  const stopOfAsset = new Map<string, number | null>();
  for (const stop of props.stops) {
    for (const meter of stop.meters) stopOfAsset.set(meter.assetId, stop.stopNo);
  }

  const registerOptions = [
    ...new Set(props.rows.flatMap((row) => row.missing_channels)),
  ].map((channel) => ({
    value: channel,
    label: t(`metering.reads.channel.${channel}`, { defaultValue: channel }),
  }));

  const { page, total } = applyLocally(
    props.rows,
    state,
    (row, q) =>
      (row.meter ?? "").toLowerCase().includes(q) ||
      (row.premises ?? "").toLowerCase().includes(q),
    (row, filters) =>
      filters.register === undefined ||
      filters.register === "" ||
      row.missing_channels.includes(filters.register),
  );

  const config: TableConfig<ReadChaseRow> = {
    screenId: "MR-21.short",
    getRowId: (row) => `${row.asset_id ?? row.unit_id}`,
    searchFields: ["meter", "premises"],
    searchPlaceholder: "metering.routeReads.short.search",
    // ⚠ A DECLARED FILTER, NOT A SECOND ROW OF CHIPS. DEF-1700 (PO 2026-08-27)
    // ruled that a dimension control duplicating a declared filter goes away:
    // row one is B14 rule 12's set and it is the whole toolbar.
    filters: [
      {
        name: "register",
        label: t("metering.routeReads.filter.register"),
        options: registerOptions,
      },
    ],
    defaultSort: { sort: "days", dir: "asc" },
    columns: [
      {
        key: "stop",
        label: t("metering.routeReads.col.stop"),
        numeric: true,
        cell: (row) => {
          const stop = row.asset_id === null ? null : (stopOfAsset.get(row.asset_id) ?? null);
          return stop === null ? <Dash /> : stop;
        },
      },
      {
        key: "meter",
        label: t("metering.reads.col.meter"),
        identity: true,
        cell: (row) => row.meter ?? <Dash />,
      },
      {
        key: "premises",
        label: t("metering.routeReads.col.premises"),
        cell: (row) => row.premises ?? <Dash />,
      },
      {
        key: "unit",
        label: t("metering.routeReads.col.unit"),
        cell: (row) => row.unit ?? <Dash />,
      },
      {
        key: "missing",
        label: t("metering.cycles.chase.col.missing"),
        cell: (row) => channelWords(row.missing_channels, t),
      },
      {
        key: "days",
        label: t("metering.cycles.chase.col.daysLeft"),
        numeric: true,
        sortable: true,
        cell: (row) => row.days_left,
      },
    ],
  };

  return (
    <>
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={page}
        totalRows={total}
        loading={props.loading}
        empty={{
          title: t("metering.routeReads.short.emptyTitle"),
          helper: t("metering.routeReads.short.emptyHelper"),
        }}
      />
      {/* BR-MET-026/062 — a refusal the product already makes and no screen
          stated. Two sentences of six beat one of twelve (B14 rule 33). */}
      <p className={PANEL_NOTE}>{t("metering.routeReads.demandNote")}</p>
    </>
  );
}

// ── All reads ──────────────────────────────────────────────────────────────

/**
 * The same reads table again, filtered by `f.route` — the sixth of the six
 * filters `GET /reads` declares. Three tabs of this screen say what is MISSING;
 * this is the only one that says what ARRIVED, which is where a supervisor
 * checks a reader's work rather than chasing them.
 */
function AllReadsTab(props: {
  routeId: string;
  routeCode: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "read_at",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: { route: props.routeId },
  });

  const listQuery = useQuery({
    queryKey: routeReadsListKey(props.routeId, JSON.stringify(state)),
    queryFn: () =>
      getReads(
        {
          q: state.q,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
          filters: state.filters,
        },
        props.client,
      ),
  });

  const config: TableConfig<ReadRow> = {
    screenId: "MR-21.reads",
    getRowId: (row) => row.id,
    searchFields: ["meter", "premise"],
    searchPlaceholder: "metering.routeReads.reads.search",
    defaultSort: { sort: "read_at", dir: "desc" },
    columns: [
      {
        key: "meter",
        label: t("metering.reads.col.meter"),
        identity: true,
        cell: (row) => (
          <Link className="text-accent underline" to={tenantPath(readDetailPath(row.id))}>
            {row.meter ?? ""}
          </Link>
        ),
      },
      {
        key: "read_at",
        label: t("metering.reads.col.readAt"),
        sortable: true,
        cell: (row) =>
          row.read_at === null ? (
            <Dash />
          ) : (
            <DateCell value={row.read_at} timeZone={props.timeZone} dateFormat={props.dateFormat} />
          ),
      },
      {
        key: "route",
        label: t("metering.reads.col.route"),
        cell: (row) => row.route ?? <Dash />,
      },
      {
        key: "premise",
        label: t("metering.reads.col.premise"),
        cell: (row) => (
          <>
            {row.premise ?? <Dash />}
            {row.unit_label !== null && ` · ${row.unit_label}`}
          </>
        ),
      },
      {
        key: "previous",
        label: t("metering.reads.col.previous"),
        numeric: true,
        cell: (row) => row.prior_value_display ?? <Dash />,
      },
      {
        key: "current",
        label: t("metering.reads.col.current"),
        numeric: true,
        cell: (row) => row.current_value_display ?? <Dash />,
      },
      {
        // CLAUDE.md hard rule 3 — the usage NEVER reaches the screen without its
        // unit, and a dash is the honest answer when the server sent neither.
        key: "usage",
        label: t("metering.reads.col.usage"),
        numeric: true,
        cell: (row) => row.usage_display ?? <Dash />,
      },
      {
        key: "channel",
        label: t("metering.reads.col.channel"),
        cell: (row) => t(`metering.reads.channel.${row.channel}`, { defaultValue: row.channel }),
      },
      {
        key: "source",
        label: t("metering.reads.col.source"),
        cell: (row) => t(`metering.reads.source.${row.source}`, { defaultValue: row.source }),
      },
      {
        key: "status",
        label: t("metering.reads.col.status"),
        cell: (row) => (
          <StatusPill tone={row.status === "flagged" ? "warning" : "success"}>
            {t(`metering.reads.status.${row.status}`, { defaultValue: row.status })}
          </StatusPill>
        ),
      },
    ],
  };

  return (
    <>
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        empty={{
          title: t("metering.routeReads.reads.emptyTitle"),
          helper: t("metering.routeReads.reads.emptyHelper"),
        }}
      />
      {/* ⚠ `GET /reads` declares no DATE filter, so this list is the route's
          whole hot window rather than the period named in the header. Saying so
          is a FACT a clerk needs to read the table correctly (B14 rule 33). */}
      <p className={PANEL_NOTE}>
        {t("metering.routeReads.reads.allWindows")}{" "}
        <Link className="text-accent underline" to={tenantPath(READS_ROUTE)}>
          {t("metering.routeReads.reads.widen")}
        </Link>
      </p>
    </>
  );
}

// ── History ────────────────────────────────────────────────────────────────

/**
 * The route's windows across BOTH its cycles — the view that only exists at
 * this level, because a cycle page can never show a July quarterly window
 * beside an August monthly one for the same route.
 *
 * ⚠ **A ROW EXISTS ONLY ONCE A WINDOW HAS BEEN CLOSED.** `read_windows` is
 * written by the closer (`read_windows.close_read_window`), so the window the
 * header is measuring is absent from this list until it closes. That is why the
 * header carries the open window's figures and this tab does not invent a row
 * for it.
 */
function HistoryTab(props: {
  rows: readonly RouteReadWindowRow[];
  loading: boolean;
  cycleById: Map<string, CycleRow>;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { t } = props;
  const [state, setState] = useLocalTableState("window");
  const { page, total } = applyLocally(props.rows, state, () => true, () => true);

  const config: TableConfig<RouteReadWindowRow> = {
    screenId: "MR-21.history",
    getRowId: (row) => row.id,
    defaultSort: { sort: "window", dir: "desc" },
    columns: [
      {
        key: "window",
        label: t("metering.routeReads.col.window"),
        identity: true,
        cell: (row) => (
          <>
            <DateCell
              value={row.period_start}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
            {" – "}
            <DateCell
              value={row.period_end}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          </>
        ),
      },
      {
        // B14 rule 31 — the cycle's CODE, resolved from the id the row carries.
        key: "cycle",
        label: t("metering.reads.col.cycle"),
        cell: (row) =>
          row.cycle_id === null ? <Dash /> : (props.cycleById.get(row.cycle_id)?.code ?? <Dash />),
      },
      {
        key: "collected",
        label: t("metering.routeReads.col.collected"),
        numeric: true,
        cell: (row) =>
          row.collected === null || row.expected === null ? (
            <Dash />
          ) : (
            t("metering.routeReads.ofTotal", { count: row.collected, total: row.expected })
          ),
      },
      {
        key: "skips",
        label: t("metering.routeReads.col.skipped"),
        numeric: true,
        cell: (row) => (row.skips === null ? <Dash /> : row.skips),
      },
      {
        key: "completed",
        label: t("metering.routeReads.col.completed"),
        cell: (row) =>
          row.read_on === null ? (
            <Dash />
          ) : (
            <DateCell value={row.read_on} timeZone={props.timeZone} dateFormat={props.dateFormat} />
          ),
      },
      {
        key: "status",
        label: t("metering.reads.col.status"),
        cell: (row) => {
          const verdict = historyStatus(row);
          return (
            <StatusPill tone={verdict.tone}>
              {t(`metering.routeReads.result.${verdict.key}`)}
            </StatusPill>
          );
        },
      },
    ],
  };

  return (
    <DataTable
      config={config}
      state={state}
      onStateChange={setState}
      rows={page}
      totalRows={total}
      loading={props.loading}
      empty={{
        title: t("metering.routeReads.history.emptyTitle"),
        helper: t("metering.routeReads.history.emptyHelper"),
      }}
    />
  );
}

export default RouteReadsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: Meter Reads blueprint entry 21 (pages 49–53, read as images per B14
//         rule 42) + the nine PO rulings of 2026-09-14 in
//         12-governance/02-decision-log.md
// screens: MR-21 (the blueprint's own entry number; no S-id is minted here —
//          A1's range is not a lane's to extend)
// exceptions:
//   (1) THE READER IS NOT RENDERED anywhere on this screen, against the
//       drawing, because CR-029 D6 and OQ-343 both rule it out by name and
//       OQ-343's own words are *"correct the screenshot"*. REPORTED to the PO.
//   (2) `REGISTERS COLLECTED · N of M` is built as REGISTERS SHORT: no endpoint
//       serves a route-scoped expected-register denominator
//       (`cycle_coverage` computes `expected_channels` and `chase_list` drops
//       it). Reported rather than fabricated.
//   (3) The Stops tab carries no LAST READ column and the shortfall carries no
//       PLAN or LAST ACTUAL column — none of the three is served for a route
//       without one request per meter.
//   (4) NO *Send someone out* and NO *Estimate these*: the first needs a
//       metering-side disposition a DERIVED row cannot have (BR-WRK-055) and is
//       built by the upload wizard's stage-3 lane; the second is the blueprint's
//       own *"the same control as entry 20"*.
//   (5) The `…` overflow drawn beside Route sheet is NOT built — the drawing
//       names nothing in it, and a menu with nothing in it is hard-won law 2.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
