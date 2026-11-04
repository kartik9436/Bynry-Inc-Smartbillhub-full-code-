// ── Trace ──────────────────────────────────────────────
// Screen:   Meter Reads blueprint **entry 20 — "A cycle — the detail"**,
//           `/:tenant/reads/cycles/:cycleId`, opened by a row on entry 15.
//           Drawings read AS IMAGES (B14 rule 42): p042 (the frame and the
//           Overview tab), p043 (its annotations), p044 (Routes), p045 (Still
//           to read), p046 (History, and All reads), p047 (All reads and the
//           control table), p048 (what is deliberately absent, and the
//           field-by-field source table).
// Why:      the second half of the PO's ruling *"within that we should show
//           Routes and their completion"*. Retiring entry 14 moved nine columns
//           with nowhere to go; this is where they went.
// Rules:    BR-MET-010 (a route belongs to exactly one cycle) · **BR-MET-011
//           CONFIRMED-AS-NARROWED 2026-09-14** (all CRUD of a cycle's
//           DEFINITION stays in Settings — frequency, start day, window length;
//           the reading WORK is writable here) · BR-MET-049/057 (the
//           plan-driven required register set, and the chase list over it) ·
//           BR-MET-055 (no unbounded read) · BR-SHL-011 (URL grammar; the open
//           tab is URL state) · BR-SHL-020/025 (the six states; a control that
//           cannot act is disabled WITH its reason) · BR-SHL-034 (one date
//           formatter) · NFR-3 (server pagination) · NFR-5 (no hard caps)
// B14:      2 (one page header) · 12 (one toolbar row) · 15 (row actions are
//           icons with tooltips) · 16 (a pagination footer on every list table)
//           · 17 (an empty state on every list) · 20 (one table type) · 21
//           (Tailwind utilities; this file adds NO class to any stylesheet and
//           IS on `styles/route-b-migrated.txt`, added in the same commit) · 31
//           (no database id on screen — a cycle is `CY-001`, a meter is
//           `MTR-0463`) · 32/33 (the description budget and the word caps) ·
//           36 (compose the kit) · 39 (the one spacing scale) · 40 (the
//           page-head title is 32px, which `PageHeader` emits) · 41/42 (the
//           drawing is the specification, read as an image)
// Tests:    ReadCycleDetailPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ⛔ TWO DRAWN FIGURES ARE **NOT BUILT**, AND IT IS A PO RULING RATHER THAN A
//    GAP — `DEF-MET-5206`, filed 2026-09-14, PO verbatim: ***"Settle first."***
// ══════════════════════════════════════════════════════════════════════════
// **Two derivations of *"the current window"* give different answers.** Measured
// on one day, the cycle row printed **August** while the completeness engine
// answered **September**. Everything computed by comparing a COLLECTED count
// against an EXPECTED count over that window therefore disagrees with the dates
// printed beside it, and the blueprint says so in its own words: *"Build these
// two on the fork and you get a screen that disagrees with itself … Everything
// else on this drawing is safe to build now."*
//
// **So these are drawn and are absent here:**
//
//   * **the Window pill** — the drawn `Window closed 9 days ago` chip beside the
//     status, and the `WINDOW · Closed · 9 days ago` figure in the Collection
//     panel, which are the same derivation twice;
//   * **Registers collected**, WHEREVER IT APPEARS — the roll-up line's
//     *"0 of 18 registers"*, the Collection panel's `REGISTERS COLLECTED 0 of 18`
//     with its *"5 meters × their plan's registers"* denominator, the Routes
//     panel's `REGISTERS` column, the Routes tab's `REGISTERS COLLECTED` column
//     and the History tab's column of the same name.
//
// ⚠ **THE WIDER READING OF *"Registers collected"* IS DELIBERATE AND IT IS ALSO
// WHAT THE DATA SAYS.** The ruling names the figure, not one drawing of it, and
// there is no window-scoped register count served per route at all:
// `route_dict`'s `collected` is `collected_read_count(route_id=…)`, which counts
// every committed head read on that route **for all time**. Drawing it under the
// floor note *"Measured against this cycle's window."* would be a sentence
// promising something the number does not do (hard-won law 1), so the column is
// absent rather than approximate.
//
// **WHAT IS BUILT, and why it is safe.** `METERS SHORT`, the short-register line
// and the whole Still-to-read tab come from ONE `chase-list` call that is handed
// **the window this page is itself printing** (`?period=<window_start>`) — the
// workaround `RoutesCyclesPage` already records: *"passing the window this row
// is ITSELF printing makes the two halves of one line describe one period"*. So
// every figure on this screen describes the window in its own roll-up line. That
// settles CONSISTENCY, not the fork; the fork is `DEF-MET-5206`'s and the PO's.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT ELSE IS DELIBERATELY NOT HERE (p048, verbatim)
// ══════════════════════════════════════════════════════════════════════════
// *"no Close the window, no Reopen, no Bill this cycle. The window is derived
// from dates and cannot be closed by hand; billing is the billing module's run
// and putting a trigger here would be a second way to start it."*
//
// And **no create, edit or delete of the cycle itself** — `BR-MET-011` as
// narrowed. This file imports no cycle mutation wrapper at all; the escape is
// `Manage in Settings →` on the panel it configures.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getCycleChaseList,
  getCycleDetail,
  getReadingSheetSummary,
  getReads,
  getRoutesPage,
} from "@/api/endpoints";
import type {
  CycleRow,
  ReadChaseRow,
  ReadRow,
  RouteRow,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { Kicker, Note } from "@/components/TextBits";
import { DownloadIcon, PrinterIcon, SwapIcon } from "@/components/icons";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { ListExportButton } from "@/features/exports/ListExportButton";
import { assetDetailPath } from "@/features/assets/assetsShared";
import { frequencyLabel } from "@/features/tenancy/routesCyclesShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AssignReaderModal } from "./AssignReaderModal";
import type { ReaderTarget } from "./AssignReaderModal";
import { BulkEstimateModal } from "./BulkEstimateModal";
import { READ_CYCLES_TAB_PATH } from "./ReadCyclesTab";
import { SendSomeoneOutModal } from "./SendSomeoneOutModal";
import type { FieldVisitMeter } from "./SendSomeoneOutModal";
import {
  DASHBOARD_ROUTE,
  Dash,
  GuardedButton,
  PREMISES_PERMISSION,
  isDenied,
  useAccessCell,
  useRegional,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";
import { routeReadsPath } from "./RouteReadsPage";
import { READS_UPLOAD_ROUTE } from "./readsShared";

// ── Address, tabs, keys ────────────────────────────────────────────────────

/** The child segment `App.tsx` nests under the tenant layout. */
export const READ_CYCLE_DETAIL_ROUTE = "reads/cycles/:cycleId";

// ⚠ **`readCycleDetailPath` IS NOT DECLARED HERE — IT IS `meteringShared`'s.**
// This file wrote its own, byte-identical, in the same hour entry 15's lane put
// one there for its row link. Two copies of one address are hard-won law 5 in
// TypeScript: identical today and free to drift the first time the route moves,
// with the LIST pointing one way and the screen answering at the other. One
// composer, imported by both, and this note is why it is not local.

/**
 * **FIVE TABS, AND THE DRAWING IS WHY IT IS FIVE.**
 *
 * ⚠ **THE BLUEPRINT SAYS "FOUR" IN PROSE AND DRAWS FIVE IN EVERY FRAME.** Its
 * summary row reads *"Four — Overview · Routes 2 · Still to read 5 · History"*,
 * and the tab strip on p042, p044, p045, p046 and p047 draws
 * **Overview · Routes · Still to read · All reads · History** every time, with
 * All reads carrying its own page of annotations (*"the reads list of entry 02,
 * pre-filtered to this cycle and nothing else"*). The prose is the count before
 * that tab was added. **B14 rule 41 makes the drawing the specification**, and
 * five frames agreeing outrank one sentence; reported rather than resolved
 * silently.
 */
export const READ_CYCLE_TABS = ["overview", "routes", "still", "reads", "history"] as const;
export type ReadCycleTab = (typeof READ_CYCLE_TABS)[number];

/** BR-SHL-011: an unknown tab falls back to the first, never errors. */
export function readCycleTabFromParam(raw: string | null | undefined): ReadCycleTab {
  return READ_CYCLE_TABS.includes(raw as ReadCycleTab) ? (raw as ReadCycleTab) : "overview";
}

export const READ_CYCLE_TAB_PARAM = "tab";
export const readCycleQueryKey = (cycleId: string) => ["read-cycle", cycleId] as const;
/** One key per cycle AND per window, so changing the window asks again rather
 *  than showing the previous window's shortfall (`RoutesCyclesPage`'s own rule). */
export const readCycleChaseKey = (cycleId: string, window: string) =>
  ["read-cycle-chase", cycleId, window] as const;
export const readCycleRoutesKey = (cycleId: string, state: string) =>
  ["read-cycle-routes", cycleId, state] as const;
export const readCycleReadsKey = (cycleId: string, state: string) =>
  ["read-cycle-reads", cycleId, state] as const;
export const readCycleSheetKey = (cycleId: string, window: string) =>
  ["read-cycle-sheet", cycleId, window] as const;

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";
const FLOOR_NOTE = `mt-3 text-sm ${MUTED}`;
const FIGURE_LABEL = `text-xs uppercase tracking-label ${MUTED}`;
const FIGURE_VALUE = "font-heading text-metric-sm";

// ── Pure pieces (exported so the suite can assert them without a mount) ────

/**
 * The window this whole page is scoped to, as the server's own `YYYY-MM-DD`.
 *
 * ⚠ **IT IS THE CYCLE ROW'S OWN `window_start` AND NOTHING ELSE.** Every figure
 * on this screen is asked for THIS period, so the roll-up line and the shortfall
 * beneath it cannot describe two different months — see this file's header for
 * the fork that makes saying so necessary.
 */
export function cycleWindowAnchor(cycle: CycleRow | undefined): string {
  return cycle?.window_start ?? "";
}

/**
 * `In progress` · `Billed` · `Scheduled` — the OPERATIONAL status of the current
 * period (`CycleRow.status`), never the lifecycle. The same tones S27's list
 * uses, so one word is one colour across both screens.
 */
export function cycleStatusTone(status: string): "success" | "warning" | "neutral" {
  if (status === "billed") return "success";
  if (status === "in_progress") return "warning";
  return "neutral";
}

/**
 * How many meters on this route still owe a register, from the ONE chase answer.
 *
 * ⚠ **ONE CHASE ROW IS ONE METER, NOT ONE REGISTER**, which is the split the
 * drawing labels *"Short · meters, not registers — the two questions kept
 * apart"*. A TOU meter owing three windows is ONE short meter.
 */
export function shortMetersByRoute(rows: readonly ReadChaseRow[]): Record<string, number> {
  const tally: Record<string, number> = {};
  for (const row of rows) {
    if (row.route !== null && row.route !== "") {
      tally[row.route] = (tally[row.route] ?? 0) + 1;
    }
  }
  return tally;
}

/** One entry of the drawn short-register line: the register, how many meters
 *  owe it, and — only when exactly one does — that meter's number.
 *
 *  ⚠ **THE NUMBER RIDES ONLY WHEN IT IS THE ONLY ONE.** Naming one of five
 *  reads as *the* one; listing five is an unbounded list wearing a summary's
 *  clothes. */
export interface ShortRegister {
  channel: string;
  meters: number;
  meter: string | null;
}

export function shortRegisters(rows: readonly ReadChaseRow[]): ShortRegister[] {
  const seen = new Map<string, ShortRegister>();
  for (const row of rows) {
    for (const channel of row.missing_channels) {
      const held = seen.get(channel);
      if (held === undefined) {
        seen.set(channel, { channel, meters: 1, meter: row.meter });
      } else {
        held.meters += 1;
        held.meter = null;
      }
    }
  }
  return [...seen.values()];
}

/** A Routes-tab row as the reader dialog takes it (MQ-033): the code it names
 *  and the reader it has, `null` when nobody reads it. */
export function readerTarget(row: RouteRow): ReaderTarget {
  return { id: row.id, code: row.code, reader: row.reader ?? null };
}

/** Every register a set of chase rows owes, deduplicated — the filter chips. */
export function shortChannels(rows: readonly ReadChaseRow[]): string[] {
  return [...new Set(rows.flatMap((row) => row.missing_channels))];
}

/**
 * The targets `POST /reads/bulk-estimate` takes for one ticked meter: one per
 * register it still owes, because a record is `(meter, channel, date)` and a
 * meter short of three windows is three missing records.
 */
export function estimateTargetsFor(
  rows: readonly ReadChaseRow[],
  pickedAssetIds: readonly string[],
  readAt: string,
): { asset_id: string; meter_no: string | null; channel: string; read_at: string }[] {
  return rows
    .filter((row) => row.asset_id !== null && pickedAssetIds.includes(row.asset_id))
    .flatMap((row) =>
      row.missing_channels.map((channel) => ({
        asset_id: row.asset_id as string,
        meter_no: row.meter,
        channel,
        read_at: readAt,
      })),
    );
}

/**
 * `BR-MET-026` refuses an estimate with no actual reading to average, and the
 * drawn floor note says so BEFORE the clerk ticks it rather than after.
 *
 * ⚠ `days_left` is not what decides this — `last_actual` is, and the chase row
 * does not carry one. What it DOES carry is the meter's own name, so the screen
 * names the meters the SERVER will refuse only where it can know: it cannot, so
 * this returns the ticked rows that have never been read as far as this page can
 * see, which is exactly `null` on both value columns of `/reads`. That is why
 * the refusal is rendered from the SERVER's answer instead (see
 * `BulkEstimateModal`) and this helper only counts what was ticked.
 */
export function tickedMeters(
  rows: readonly ReadChaseRow[],
  pickedAssetIds: readonly string[],
): FieldVisitMeter[] {
  return rows
    .filter((row) => row.asset_id !== null && pickedAssetIds.includes(row.asset_id))
    .map((row) => ({ assetId: row.asset_id as string, meterNo: row.meter ?? "" }));
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface ReadCycleDetailPageProps extends RegionalProps {
  client?: ApiClient;
}

export function ReadCycleDetailPage(props: ReadCycleDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const cycleId = params.cycleId ?? "";
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = readCycleTabFromParam(searchParams.get(READ_CYCLE_TAB_PARAM));
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(PREMISES_PERMISSION, client);

  const cycleQuery = useQuery({
    queryKey: readCycleQueryKey(cycleId),
    queryFn: () => getCycleDetail(cycleId, client),
    enabled: cycleId !== "",
  });
  const cycle = cycleQuery.data;
  const windowAnchor = cycleWindowAnchor(cycle);

  // ⚖️ **ONE CHASE CALL FOR THE WHOLE SCREEN, AND IT CARRIES THE PAGE'S OWN
  //    WINDOW.** Overview's shortfall figures, the Routes tab's SHORT column and
  //    the Still-to-read table are three readings of ONE answer — two calls
  //    would be two chances to disagree about one period (hard-won law 5).
  const chaseQuery = useQuery({
    queryKey: readCycleChaseKey(cycleId, windowAnchor),
    queryFn: () =>
      getCycleChaseList(cycleId, { period: windowAnchor === "" ? undefined : windowAnchor }, client),
    enabled: cycleId !== "" && cycle !== undefined,
    staleTime: 30_000,
  });
  const chaseRows: readonly ReadChaseRow[] = chaseQuery.data?.rows ?? [];

  const sheetQuery = useQuery({
    queryKey: readCycleSheetKey(cycleId, windowAnchor),
    queryFn: () =>
      getReadingSheetSummary(
        cycleId,
        { period: windowAnchor === "" ? undefined : windowAnchor },
        client,
      ),
    enabled: cycleId !== "" && cycle !== undefined,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.ops.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (cycleQuery.isError && isPermissionDenied(cycleQuery.error)) {
    return (
      <PermissionDenied
        helper={t("metering.ops.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  // A18 §3 — the BAND skeleton first (p048: *"Loading band skeleton, then each
  // section"*). The sections below each carry their own state, so a broken chase
  // list does not take the page down with it.
  if (cycleQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (cycle === undefined) {
    return (
      <FailedWithRetry
        title={t("metering.cycleDetail.failedTitle")}
        reason={apiErrorText(cycleQuery.error, translate)}
        onRetry={() => void cycleQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(READ_CYCLES_TAB_PATH))}
      />
    );
  }

  function openTab(next: ReadCycleTab): void {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set(READ_CYCLE_TAB_PARAM, next);
    setSearchParams(nextParams, { replace: true });
  }

  const shortCount = chaseQuery.data?.count ?? null;
  const routeCount = cycle.routes.length;

  return (
    <div className="px-4 pb-8 pt-6">
      <PageHeader
        // ⚠ **THE BACK LINK GOES TO THE TAB, NOT TO `/reads/cycles`.** That
        //    address is entry 14's REDIRECT now and forwards here-ish; pointing
        //    a back link at a `<Navigate>` is a door to a door, and the tab is
        //    where the list actually lives (entry 15).
        backTo={{
          to: tenantPath(READ_CYCLES_TAB_PATH),
          label: t("metering.cycleDetail.back"),
        }}
        kicker={
          cycle.frequency === null
            ? t("metering.cycleDetail.kickerPlain")
            : t("metering.cycleDetail.kicker", {
                frequency: frequencyLabel(cycle.frequency, translate, cycle.frequency),
              })
        }
        // B14 rule 31 — the cycle CODE, never its uuid. B14 rule 40 — the size
        // is `PageHeader`'s, set on the element, and this screen does not
        // second-guess it.
        title={cycle.code}
        status={
          // ⛔ **THE DRAWN `Window closed 9 days ago` PILL IS ABSENT** —
          // `DEF-MET-5206`, PO *"Settle first."* See this file's header.
          <StatusPill tone={cycleStatusTone(cycle.status)}>
            {t(`metering.cycles.status.${cycle.status}`, { defaultValue: cycle.status })}
          </StatusPill>
        }
        rollup={
          <CycleRollup
            cycle={cycle}
            routeCount={routeCount}
            timeZone={timeZone}
            dateFormat={dateFormat}
            t={t}
          />
        }
        secondaryActions={
          <>
            <ReadingSheetButton
              cycleId={cycleId}
              window={windowAnchor}
              rows={sheetQuery.data?.rows ?? null}
              absentReason={sheetQuery.data?.window_absent_reason ?? null}
              loading={sheetQuery.isPending}
              error={sheetQuery.isError ? apiErrorText(sheetQuery.error, translate) : null}
              t={translate}
            />
            {/* p047: *"Route sheet · The printed walk, scoped to this cycle"*.
                The dialog on S25 exists to ask WHICH cycle; this page is one
                cycle, so the only question it asks is already answered. Same
                same-origin href the dialog builds, so the session cookie rides
                along (DEF-532's tenantPath discipline). */}
            <Button
              variant="secondary"
              onClick={() =>
                window.open(apiHref(tenantPath(`/cycles/${cycleId}/route-sheet`)), "_blank", "noopener")
              }
            >
              {t("metering.cycleDetail.action.routeSheet")}
            </Button>
          </>
        }
        primaryAction={
          // p043 item 5 — *"↑ Upload reads, pre-scoped to this cycle · MOVED
          // from entry 02, where it asks you which cycle"*.
          <Button
            variant="primary"
            onClick={() =>
              navigate(`${tenantPath(READS_UPLOAD_ROUTE)}?cycle=${encodeURIComponent(cycle.code)}`)
            }
          >
            {t("metering.reads.action.upload")}
          </Button>
        }
        tabs={[
          { id: "overview", label: t("metering.cycleDetail.tab.overview") },
          { id: "routes", label: t("metering.cycleDetail.tab.routes"), count: routeCount },
          {
            id: "still",
            label: t("metering.cycleDetail.tab.still"),
            count: shortCount ?? undefined,
          },
          { id: "reads", label: t("metering.cycleDetail.tab.reads") },
          { id: "history", label: t("metering.cycleDetail.tab.history") },
        ]}
        activeTabId={tab}
        tabsLabel={t("metering.cycleDetail.tabsLabel")}
        onTabSelect={(next) => openTab(readCycleTabFromParam(next.id))}
      />

      {tab === "overview" && (
        <OverviewTab
          cycle={cycle}
          cycleId={cycleId}
          window={windowAnchor}
          chase={{
            rows: chaseRows,
            count: chaseQuery.data?.count ?? null,
            loading: chaseQuery.isPending,
            error: chaseQuery.isError ? apiErrorText(chaseQuery.error, translate) : null,
            onRetry: () => void chaseQuery.refetch(),
          }}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          translate={translate}
          t={t}
        />
      )}
      {tab === "routes" && (
        <RoutesTab
          cycleId={cycleId}
          window={windowAnchor}
          shortByRoute={shortMetersByRoute(chaseRows)}
          chaseKnown={chaseQuery.data !== undefined}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          translate={translate}
          t={t}
        />
      )}
      {tab === "still" && (
        <StillToReadTab
          cycleCode={cycle.code}
          rows={chaseRows}
          loading={chaseQuery.isPending}
          error={chaseQuery.isError ? apiErrorText(chaseQuery.error, translate) : null}
          onRetry={() => void chaseQuery.refetch()}
          onChanged={() => void chaseQuery.refetch()}
          client={client}
          dateFormat={dateFormat}
          windowAnchor={windowAnchor}
          t={t}
        />
      )}
      {tab === "reads" && (
        <AllReadsTab
          cycleId={cycleId}
          cycleCode={cycle.code}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          translate={translate}
          t={t}
        />
      )}
      {tab === "history" && <HistoryTab t={t} />}
    </div>
  );
}

// ── The roll-up line ───────────────────────────────────────────────────────

/**
 * *"Read window 09/01 – 09/03/2026 · billed 11/05/2026, due 11/25 · 2 routes ·
 * 5 meters"* — the facts a person reads before deciding anything (p043 item 4).
 *
 * ⛔ **THE DRAWN `· 0 of 18 registers` CLAUSE IS ABSENT** — `DEF-MET-5206`.
 */
export function CycleRollup(props: {
  cycle: CycleRow;
  routeCount: number;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { cycle, t } = props;
  const parts: React.ReactNode[] = [];
  if (cycle.window_start !== null && cycle.window_end !== null) {
    parts.push(
      <span key="window">
        {t("metering.cycleDetail.rollup.window")}{" "}
        <DateCell
          value={cycle.window_start}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
        {" – "}
        <DateCell value={cycle.window_end} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      </span>,
    );
  } else {
    // BR-SHL-020: an absence says what is missing, never a zero or an em-dash
    // that could mean either. A FACT, three words (B14 rule 33).
    parts.push(<span key="window">{t("metering.cycleDetail.rollup.noWindow")}</span>);
  }
  if (cycle.bill_date !== null) {
    parts.push(
      <span key="billed">
        {t("metering.cycleDetail.rollup.billed")}{" "}
        <DateCell value={cycle.bill_date} timeZone={props.timeZone} dateFormat={props.dateFormat} />
        {cycle.due_date !== null && (
          <>
            {", "}
            {t("metering.cycleDetail.rollup.due")}{" "}
            <DateCell
              value={cycle.due_date}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          </>
        )}
      </span>,
    );
  }
  parts.push(
    <span key="routes">{t("metering.cycleDetail.rollup.routes", { count: props.routeCount })}</span>,
  );
  parts.push(
    <span key="meters">{t("metering.cycleDetail.rollup.meters", { count: cycle.expected })}</span>,
  );
  return (
    <span data-cycle="rollup">
      {parts.map((part, index) => (
        <span key={index}>
          {index > 0 && " · "}
          {part}
        </span>
      ))}
    </span>
  );
}

// ── Overview ───────────────────────────────────────────────────────────────

function OverviewTab(props: {
  cycle: CycleRow;
  cycleId: string;
  window: string;
  chase: {
    rows: readonly ReadChaseRow[];
    count: number | null;
    loading: boolean;
    error: string | null;
    onRetry: () => void;
  };
  client: ApiClient;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  translate: Translator;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { cycle, chase, t } = props;
  const tenantPath = useTenantPath();
  const registers = useMemo(() => shortRegisters(chase.rows), [chase.rows]);

  return (
    <div className="grid grid-cols-1 gap-x-4 lg:grid-cols-3">
      {/* ⚖️ **A `Panel`, NOT A KPI BAND** — p043 item 7, and the PO's ruling of
          2026-09-12: *"in detail section use Panel to information groups"*. */}
      <Panel as="section" title={<Kicker>{t("metering.cycleDetail.panel.collection")}</Kicker>} className="lg:col-span-3">
        {chase.error !== null ? (
          <SectionFailure reason={chase.error} onRetry={chase.onRetry} t={t} />
        ) : (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-4">
              {/* ⛔ `REGISTERS COLLECTED` and `WINDOW` are drawn beside this one
                  and are NOT built — `DEF-MET-5206`, PO *"Settle first."* */}
              <Figure
                label={t("metering.cycleDetail.figure.metersShort")}
                value={
                  chase.loading ? (
                    t("metering.cycles.completeness.loading")
                  ) : chase.count === null ? (
                    <Dash />
                  ) : (
                    String(chase.count)
                  )
                }
                qualifier={
                  chase.count === null
                    ? null
                    : t("metering.cycleDetail.figure.ofMeters", { count: cycle.expected })
                }
                tone={chase.count !== null && chase.count > 0 ? "warning" : "plain"}
                testId="meters-short"
              />
            </div>
            {registers.length > 0 && (
              <p className={FLOOR_NOTE} data-cycle="short-registers">
                {t("metering.cycleDetail.shortRegisters")}{" "}
                {registers.map((entry, index) => (
                  <span key={entry.channel}>
                    {index > 0 && " · "}
                    <strong>
                      {t(`metering.reads.channel.${entry.channel}`, {
                        defaultValue: entry.channel,
                      })}
                    </strong>{" "}
                    {entry.meter === null
                      ? t("metering.cycleDetail.onMeters", { count: entry.meters })
                      : t("metering.cycleDetail.onMeter", { meter: entry.meter })}
                  </span>
                ))}
              </p>
            )}
          </>
        )}
      </Panel>

      <div className="lg:col-span-2">
        <Panel as="section" title={<Kicker>{t("metering.cycleDetail.panel.routes")}</Kicker>}>
          <RoutesTable
            cycleId={props.cycleId}
            window={props.window}
            screenId="S27D.overview.routes"
            columns="overview"
            shortByRoute={{}}
            chaseKnown={false}
            client={props.client}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            translate={props.translate}
            t={t}
          />
        </Panel>
      </div>

      <div className="lg:col-span-1">
        <Panel as="section" title={<Kicker>{t("metering.cycleDetail.panel.schedule")}</Kicker>}>
          <FactRow label={t("metering.cycles.col.frequency")}>
            {cycle.frequency === null ? (
              <Dash />
            ) : (
              frequencyLabel(cycle.frequency, props.translate, cycle.frequency)
            )}
          </FactRow>
          <FactRow label={t("metering.cycles.col.startDay")}>
            {/* ⚠ `effective_start_day` and NOT `start_day`: `OQ-340` made the
                stored day decorative whenever a first run disagrees with it, and
                a field that lies to the operator is the defect this repo files
                most often. */}
            {cycle.effective_start_day === null ? (
              <Dash />
            ) : (
              t("metering.cycleDetail.dayOfMonth", { day: cycle.effective_start_day })
            )}
          </FactRow>
          <FactRow label={t("metering.cycles.col.daysToComplete")}>
            {cycle.days_to_complete === null ? <Dash /> : cycle.days_to_complete}
          </FactRow>
          <FactRow label={t("metering.cycleDetail.nextWindow")}>
            {cycle.next_period === null ? (
              <Dash />
            ) : (
              <>
                <DateCell
                  value={cycle.next_period.period_start}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
                {" – "}
                <DateCell
                  value={cycle.next_period.period_end}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              </>
            )}
          </FactRow>
          {/* p043 item 12 — *"the config escape, on the panel it configures"*.
              `BR-MET-011` as narrowed: the DEFINITION is Settings'. */}
          <p className="mt-4 mb-0">
            <InlineLinkTo to={tenantPath(`/settings/reference-data/routes-cycles`)}>
              {t("metering.ops.manageInSettings")}
            </InlineLinkTo>
          </p>
        </Panel>

        <Panel as="section" title={<Kicker>{t("metering.cycleDetail.panel.billing")}</Kicker>}>
          <FactRow label={t("metering.cycles.col.billDate")}>
            {cycle.bill_date === null ? (
              <Dash />
            ) : (
              <DateCell
                value={cycle.bill_date}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            )}
          </FactRow>
          <FactRow label={t("metering.cycleDetail.dueDate")}>
            {cycle.due_date === null ? (
              <Dash />
            ) : (
              <DateCell
                value={cycle.due_date}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            )}
          </FactRow>
          <FactRow label={t("metering.cycleDetail.accounts")}>{cycle.accounts}</FactRow>
          {chase.count !== null && chase.count > 0 && (
            // A CONSEQUENCE before bill day, ≤6 words per sentence and at most
            // two (B14 rule 33, and the 2026-09-14 five-to-six-word ruling).
            <p className={FLOOR_NOTE} data-cycle="billing-warning">
              {t("metering.cycleDetail.shortBeforeBill", { count: chase.count })}
            </p>
          )}
        </Panel>
      </div>
    </div>
  );
}

/** One figure in the Collection panel: label, number, qualifier. */
export function Figure(props: {
  label: string;
  value: React.ReactNode;
  qualifier: string | null;
  tone?: "plain" | "warning";
  testId: string;
}) {
  return (
    <div data-figure={props.testId}>
      <div className={FIGURE_LABEL}>{props.label}</div>
      <div
        className={
          props.tone === "warning" ? `${FIGURE_VALUE} text-accent` : FIGURE_VALUE
        }
      >
        {props.value}
      </div>
      {props.qualifier !== null && <div className={`text-sm ${MUTED}`}>{props.qualifier}</div>}
    </div>
  );
}

/** One label/value line inside a panel — the shape the drawing gives Schedule
 *  and Billing (the label left, the value right-aligned on the same row). */
function FactRow(props: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className={`text-base ${MUTED}`}>{props.label}</span>
      <span className="text-base font-semibold">{props.children}</span>
    </div>
  );
}

/** A18 §4 — one SECTION failed, and the page did not (p048's States row). */
function SectionFailure(props: {
  reason: string;
  onRetry: () => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  return (
    <div role="alert">
      <p className="m-0 mb-2 text-base">{props.reason}</p>
      <Button variant="secondary" size="sm" onClick={props.onRetry}>
        {props.t("states.failed.retry")}
      </Button>
    </div>
  );
}

// ── Routes ─────────────────────────────────────────────────────────────────

function RoutesTab(props: {
  cycleId: string;
  /** The cycle's own window — it rides on the route link so entry 21's screen
   *  opens with a denominator (PO 2026-09-13, option A). */
  window: string;
  shortByRoute: Record<string, number>;
  chaseKnown: boolean;
  client: ApiClient;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  translate: Translator;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  return (
    <RoutesTable
      cycleId={props.cycleId}
      window={props.window}
      screenId="S27D.routes"
      columns="full"
      shortByRoute={props.shortByRoute}
      chaseKnown={props.chaseKnown}
      client={props.client}
      timeZone={props.timeZone}
      dateFormat={props.dateFormat}
      translate={props.translate}
      t={props.t}
    />
  );
}

/**
 * The routes on this cycle, in two column sets: the Overview panel's seven and
 * the Routes tab's fuller one with its toolbar.
 *
 * ⛔ **THE DRAWN `REGISTERS COLLECTED` COLUMN IS ABSENT FROM BOTH** —
 * `DEF-MET-5206`, and see this file's header for why `route.collected` cannot
 * stand in for it.
 */
function RoutesTable(props: {
  cycleId: string;
  window: string;
  screenId: string;
  columns: "overview" | "full";
  shortByRoute: Record<string, number>;
  chaseKnown: boolean;
  client: ApiClient;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  translate: Translator;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const full = props.columns === "full";
  // MQ-033 — the ticked routes, and the routes the reader dialog is open over.
  const [picked, setPicked] = useState<string[]>([]);
  const [assigning, setAssigning] = useState<ReaderTarget[] | null>(null);
  const config = useMemo<TableConfig<RouteRow>>(
    () => ({
      screenId: props.screenId,
      getRowId: (row) => row.id,
      defaultSort: { sort: "code", dir: "asc" },
      // ⚠ **THE PROMPT IS WRITTEN FROM THE ENDPOINT'S OWN PREDICATE, NOT FROM
      //    THE DRAWING (B14 rule 19, `CR-041`'s method).** The drawing writes
      //    *"Search route or reader…"* and `routes_queryset` matches
      //    `code__icontains` and `name__icontains` and NOTHING ELSE — the
      //    assignee is a user id it never searches. A prompt promising reader
      //    search is `DEF-1001`'s shape, so the sentence names what is matched
      //    and the divergence is reported.
      searchFields: full ? ["code", "name"] : undefined,
      searchPlaceholder: full ? "metering.cycleDetail.routes.search" : undefined,
      filters: full
        ? [
            {
              name: "status",
              label: t("metering.routes.col.status"),
              options: [
                { value: "active", label: t("settings.routes.status.active") },
                { value: "draft", label: t("settings.routes.status.draft") },
                { value: "inactive", label: t("settings.routes.status.inactive") },
              ],
            },
          ]
        : undefined,
      columns: [
        // MQ-033 — tick routes for the bulk *Assign reader* (Routes tab only).
        ...(full
          ? [
              {
                key: "select",
                label: t("metering.reads.col.select"),
                cell: (row: RouteRow) => (
                  <input
                    type="checkbox"
                    checked={picked.includes(row.id)}
                    aria-label={t("metering.routeReader.select", { route: row.code })}
                    onChange={() =>
                      setPicked((held) =>
                        held.includes(row.id)
                          ? held.filter((id) => id !== row.id)
                          : [...held, row.id],
                      )
                    }
                  />
                ),
              },
            ]
          : []),
        {
          key: "code",
          label: t("metering.routes.col.route"),
          sortable: true,
          identity: true, // B14 rule 31 — the route CODE, never its uuid
          // PO ruling 2026-09-13, verbatim: *"what if User click on Route
          // link — we will have to give a details view of Route"*. It opens the
          // OPERATIONAL detail, not Settings, and carries THIS cycle's window
          // so the figures there have the denominator they need — a route can
          // be walked on more than one cycle, which is why entry 21 gave it an
          // address of its own rather than nesting it here.
          cell: (row) => (
            <InlineLinkTo to={tenantPath(routeReadsPath(row.id, props.window))}>
              {row.code}
            </InlineLinkTo>
          ),
        },
        {
          key: "name",
          label: t("metering.cycleDetail.routes.name"),
          cell: (row) => (row.name === null ? <Dash /> : <span>{row.name}</span>),
        },
        // ✅ **THE DRAWN `READER` COLUMN IS BUILT ON THIS TAB — PO 2026-10-24
        //    (MQ-033, `DEF-MET-10591`), *"i have given you a screen from where
        //    assign/reassign should be done"*.** It read *⛔ NOT BUILT* until
        //    then, held by `CR-029` **D6** (*"not required"*) and `OQ-343`
        //    (*"B: no reader anywhere"*, both 2026-08-23); the 2026-10-24 ruling
        //    SUPERSEDES both FOR THIS TAB ONLY (decision log, same date). The
        //    Overview panel's seven columns and Settings → Routes stay
        //    reader-free, and the historical *who walked a window* stays
        //    dropped. B14 rule 31: the NAME, never the id.
        ...(full
          ? [
              {
                key: "reader",
                label: t("metering.routeReader.col"),
                cell: (row: RouteRow) =>
                  row.reader == null ? (
                    <Dash>{t("metering.routeReader.notAssigned")}</Dash>
                  ) : (
                    <span>{row.reader.name}</span>
                  ),
              },
            ]
          : []),
        ...(full
          ? [
              {
                key: "premises",
                label: t("metering.cycleDetail.routes.premises"),
                numeric: true,
                cell: (row: RouteRow) => <span>{row.premises}</span>,
              },
            ]
          : []),
        {
          key: "meters",
          label: t("metering.routes.col.meters"),
          numeric: true,
          cell: (row) => <span>{row.meters}</span>,
        },
        ...(full
          ? [
              {
                key: "short",
                label: t("metering.cycleDetail.routes.short"),
                cell: (row: RouteRow) => {
                  if (!props.chaseKnown) {
                    // BR-SHL-020: unknown is NOT zero, and a zero here would
                    // read as "this route is complete".
                    return <Dash>{t("metering.ops.notCollected")}</Dash>;
                  }
                  const short = props.shortByRoute[row.code] ?? 0;
                  return short === 0 ? (
                    <span>{t("metering.cycleDetail.routes.noneShort")}</span>
                  ) : (
                    <StatusPill tone="warning">
                      {t("metering.cycleDetail.routes.shortMeters", { count: short })}
                    </StatusPill>
                  );
                },
              },
            ]
          : []),
        {
          key: "last_completion",
          label: t("metering.cycleDetail.routes.lastRead"),
          sortable: false,
          cell: (row) =>
            row.last_completion === null ? (
              <Dash />
            ) : (
              <DateCell
                value={row.last_completion}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            ),
        },
        {
          key: "status",
          label: t("metering.routes.col.status"),
          cell: (row) => (
            <StatusPill tone={row.status === "active" ? "success" : "neutral"}>
              {t(`settings.routes.status.${row.status}`, { defaultValue: row.status })}
            </StatusPill>
          ),
        },
        ...(full
          ? [
              {
                key: "actions",
                label: t("metering.cycleDetail.routes.actions"),
                cell: (row: RouteRow) => (
                  // B14 rule 15 — ICONS with tooltips, max two visible, then
                  // `…`. p044 item 4 draws upload · print · reassign. REASSIGN
                  // IS BUILT since PO 2026-10-24 (MQ-033) — it read *ABSENT*
                  // under `CR-029` D6 / `OQ-343` until then. Who READS a route
                  // is reading work, not route configuration, so `BR-MET-011`
                  // as narrowed and `Q3`'s walk order stay Settings' and this
                  // is not a second door to either. Three actions: upload on
                  // the row, print and assign in the overflow.
                  <RowActions>
                    <RowAction
                      label={t("metering.cycleDetail.routes.uploadFor", { route: row.code })}
                      icon={<DownloadIcon />}
                      onClick={() =>
                        navigate(
                          `${tenantPath(READS_UPLOAD_ROUTE)}?route=${encodeURIComponent(row.code)}`,
                        )
                      }
                    />
                    <RowActionsMore label={t("table.rowActions.more")}>
                      <RowMenuAction
                        label={t("metering.cycleDetail.routes.printSheet", { route: row.code })}
                        icon={<PrinterIcon />}
                        onClick={() =>
                          window.open(
                            apiHref(tenantPath(`/routes/${row.id}/route-sheet`)),
                            "_blank",
                            "noopener",
                          )
                        }
                      />
                      <RowMenuAction
                        label={
                          row.reader == null
                            ? t("metering.routeReader.assign")
                            : t("metering.routeReader.reassign")
                        }
                        icon={<SwapIcon />}
                        testId={`assign-reader-${row.code}`}
                        onClick={() => setAssigning([readerTarget(row)])}
                      />
                    </RowActionsMore>
                  </RowActions>
                ),
              },
            ]
          : []),
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.screenId, full, props.shortByRoute, props.chaseKnown, picked, t],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: readCycleRoutesKey(props.cycleId, JSON.stringify(state)),
    queryFn: () =>
      getRoutesPage(
        // The cycle rides as a filter the SERVER already declares
        // (`routes_queryset`'s `cycle`), never as a chip a clerk could remove:
        // a cycle's routes page that could be widened to every route is a
        // different screen.
        { ...state, filters: { ...state.filters, cycle: props.cycleId } },
        props.client,
      ),
    enabled: props.cycleId !== "",
  });

  const pageRows = query.data?.rows ?? [];
  const pickedTargets = pageRows.filter((row) => picked.includes(row.id)).map(readerTarget);

  return (
    <>
      {/* The bulk bar renders only when something is ticked — the Still-to-read
          tab's own rule, followed rather than re-decided. */}
      {full && picked.length > 0 && (
        <div
          className="mb-4 flex flex-wrap items-center gap-3 border border-divider bg-surface p-3"
          data-cycle="routes-bulk"
        >
          <span className="text-base font-semibold">
            {t("metering.routeReader.routesPicked", { count: picked.length })}
          </span>
          <Button variant="secondary" size="sm" onClick={() => setAssigning(pickedTargets)}>
            {t("metering.routeReader.bulkAssign")}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setPicked([])}>
            {t("metering.cycleDetail.chase.clear")}
          </Button>
        </div>
      )}
      <DataTable<RouteRow>
        config={config}
        state={state}
        onStateChange={(next) => {
          setState(next);
          setPicked([]);
        }}
        rows={pageRows}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError && query.data === undefined
            ? {
                reason: apiErrorText(query.error, props.translate),
                onRetry: () => void query.refetch(),
              }
            : null
        }
        empty={{
          title: t("metering.cycleDetail.routes.emptyTitle"),
          helper: t("metering.cycleDetail.routes.emptyHelper"),
        }}
        downloadSlot={
          full ? (
            <ListExportButton
              resource="routes"
              state={{ ...state, filters: { ...state.filters, cycle: props.cycleId } }}
              client={props.client}
            />
          ) : undefined
        }
      />
      {full && (
        // A FACT, five meaningful words (B14 rule 33 and the 2026-09-14
        // five-to-six-word ruling). The drawing writes eight.
        <p className={FLOOR_NOTE} data-cycle="routes-floor-note">
          {t("metering.cycleDetail.routes.floorNote")}
        </p>
      )}
      {assigning !== null && (
        <AssignReaderModal
          routes={assigning}
          client={props.client}
          onClose={() => setAssigning(null)}
          onSaved={() => {
            setPicked([]);
            void query.refetch();
          }}
        />
      )}
    </>
  );
}

// ── Still to read ──────────────────────────────────────────────────────────

/**
 * The shortfall, and the one place on this screen a clerk WRITES.
 *
 * `BR-MET-011` as narrowed (PO 2026-09-14): a cycle's DEFINITION is Settings',
 * and **the reading WORK is writable here** — which is what a clerk does all day.
 *
 * ⛔ **SERVER PAGINATION IS OWED AND IS NOT BUILT HERE — see `DEF-MET-5210`.**
 * `GET /cycles/{id}/chase-list` answers the whole shortfall in one payload and
 * sorts it in Python; the blueprint's own source table marks it
 * **SERVED · NEEDS A PAGER**. Adding the pager is a BACKEND change and the
 * backend suite cannot be run in this container at all (`djangorestframework` is
 * not installed and every CI workflow is `.disabled`), so shipping one would
 * break hard-won law 7's second half — *prove it RED in the harness that will
 * run it*. The footer below is therefore a CLIENT slice over a server answer
 * that is bounded by the cycle's own membership, and the debt is filed rather
 * than hidden.
 */
function StillToReadTab(props: {
  cycleCode: string;
  rows: readonly ReadChaseRow[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onChanged: () => void;
  client: ApiClient;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  windowAnchor: string;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const [picked, setPicked] = useState<string[]>([]);
  const [channel, setChannel] = useState<string>("");
  const [estimating, setEstimating] = useState(false);
  const [visiting, setVisiting] = useState(false);
  const [page, setPage] = useState(1);

  const channels = useMemo(() => shortChannels(props.rows), [props.rows]);
  const filtered = useMemo(
    () =>
      channel === "" ? props.rows : props.rows.filter((row) => row.missing_channels.includes(channel)),
    [props.rows, channel],
  );

  const config = useMemo<TableConfig<ReadChaseRow>>(
    () => ({
      screenId: "S27D.chase",
      getRowId: (row) => row.asset_id ?? row.unit_id,
      defaultSort: { sort: "days_left", dir: "asc" },
      columns: [
        {
          key: "select",
          label: t("metering.reads.col.select"),
          cell: (row) => {
            const id = row.asset_id;
            const checked = id !== null && picked.includes(id);
            return (
              <input
                type="checkbox"
                checked={checked}
                disabled={id === null}
                aria-label={t("metering.cycleDetail.chase.select", { meter: row.meter ?? "" })}
                onChange={() => {
                  if (id === null) return;
                  setPicked((held) =>
                    held.includes(id) ? held.filter((held_id) => held_id !== id) : [...held, id],
                  );
                }}
              />
            );
          },
        },
        {
          key: "meter",
          label: t("metering.cycles.chase.col.meter"),
          identity: true,
          cell: (row) =>
            row.meter === null || row.asset_id === null ? (
              <Dash />
            ) : (
              // p048 Write surfaces — *"meter → the asset"*. B14 rule 31: the
              // meter NUMBER is what is shown; the uuid is only the address.
              <InlineLinkTo to={tenantPath(assetDetailPath(row.asset_id))}>{row.meter}</InlineLinkTo>
            ),
        },
        {
          key: "premises",
          label: t("metering.cycles.chase.col.premises"),
          cell: (row) => (row.premises === null ? <Dash /> : <span>{row.premises}</span>),
        },
        {
          key: "unit",
          label: t("metering.cycles.chase.col.unit"),
          cell: (row) => (row.unit === null ? <Dash /> : <span>{row.unit}</span>),
        },
        {
          key: "missing",
          label: t("metering.cycles.chase.col.missing"),
          cell: (row) => (
            <span>
              {row.missing_channels.map((name, index) => (
                <span key={name}>
                  {index > 0 && ", "}
                  <strong>{t(`metering.reads.channel.${name}`, { defaultValue: name })}</strong>
                </span>
              ))}
            </span>
          ),
        },
        {
          key: "route",
          label: t("metering.reads.col.route"),
          cell: (row) => (row.route === null ? <Dash /> : <span>{row.route}</span>),
        },
        {
          key: "days_left",
          label: t("metering.cycles.chase.col.daysLeft"),
          numeric: true,
          // p045 item 4 — *"Days left, negative once the window shuts"*. The
          // as-built printed 0 nine days after close, which reads as "today".
          cell: (row) => (
            <span className={row.days_left < 0 ? "text-accent" : undefined}>{row.days_left}</span>
          ),
        },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [picked, t],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const per = state.per;
  const visible = filtered.slice((page - 1) * per, page * per);
  const pickedRows = tickedMeters(props.rows, picked);

  return (
    <>
      {/* B14 rule 12 — ONE toolbar row. The register chips are the rate-type
          filter p045 item 1 draws, counted by what is missing. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button
          variant={channel === "" ? "primary" : "secondary"}
          size="sm"
          onClick={() => {
            setChannel("");
            setPage(1);
          }}
        >
          {t("metering.cycleDetail.chase.all", { count: props.rows.length })}
        </Button>
        {channels.map((name) => (
          <Button
            key={name}
            variant={channel === name ? "primary" : "secondary"}
            size="sm"
            onClick={() => {
              setChannel(name);
              setPage(1);
            }}
          >
            {t(`metering.reads.channel.${name}`, { defaultValue: name })} (
            {props.rows.filter((row) => row.missing_channels.includes(name)).length})
          </Button>
        ))}
      </div>

      {/* The bulk bar renders only when something is ticked — a permanent empty
          toolbar over every list is chrome nobody reads (`ReadsBulkBar`'s own
          rule, followed rather than re-decided). */}
      {picked.length > 0 && (
        <div
          className="mb-4 flex flex-wrap items-center gap-3 border border-divider bg-surface p-3"
          data-cycle="chase-bulk"
        >
          <span className="text-base font-semibold">
            {t("metering.cycleDetail.chase.selected", { count: picked.length })}
          </span>
          <GuardedButton
            label={t("metering.cycleDetail.chase.estimate")}
            reason={null}
            onClick={() => setEstimating(true)}
          />
          {/* p047's control table puts *Send someone out* on the shortfall, and
              the door exists since the PO reversed `Q2` on 2026-09-14 (*"please
              build this"*). This mounts the dialog the upload wizard already
              mounts — one door, two surfaces. */}
          <GuardedButton
            label={t("metering.fieldVisit.title")}
            reason={null}
            onClick={() => setVisiting(true)}
          />
          <Button variant="ghost" size="sm" onClick={() => setPicked([])}>
            {t("metering.cycleDetail.chase.clear")}
          </Button>
        </div>
      )}

      <DataTable<ReadChaseRow>
        config={config}
        state={{ ...state, page }}
        onStateChange={(next) => {
          setState(next);
          setPage(next.page);
          setPicked([]);
        }}
        rows={visible}
        totalRows={filtered.length}
        loading={props.loading}
        error={
          props.error === null ? null : { reason: props.error, onRetry: props.onRetry }
        }
        empty={{
          title: t("metering.cycleDetail.chase.emptyTitle"),
          helper: t("metering.cycleDetail.chase.emptyHelper"),
        }}
      />
      {/* A FACT before the tick, not after it (`BR-MET-026` refuses an estimate
          with no actual to average). Two sentences, each under six words. */}
      <p className={FLOOR_NOTE} data-cycle="chase-floor-note">
        {t("metering.cycleDetail.chase.floorNote")}
      </p>

      {estimating && (
        <BulkEstimateModal
          rows={props.rows}
          pickedAssetIds={picked}
          dateFormat={props.dateFormat}
          windowEnd={props.windowAnchor}
          client={props.client}
          onClose={() => setEstimating(false)}
          onEstimated={() => {
            setPicked([]);
            props.onChanged();
          }}
        />
      )}
      {visiting && (
        <SendSomeoneOutModal
          meters={pickedRows}
          client={props.client}
          onClose={() => setVisiting(false)}
          // ⚠ **NOTHING TO RECORD HERE, AND THAT IS THE HONEST ANSWER RATHER
          //    THAN A STUB.** On the upload wizard this writes a row DISPOSITION
          //    — *these staged rows are not posting, somebody is going out* —
          //    because rows are staged and must be stopped. On a cycle's
          //    shortfall nothing is staged: the meters simply have not been read,
          //    so there is no row whose posting a decision could change.
          //    `BR-WRK-055`'s ordering still holds — this resolves before the
          //    raise, and a failed raise costs the clerk nothing.
          onRecordDecision={() => Promise.resolve()}
        />
      )}
    </>
  );
}

// ── All reads ──────────────────────────────────────────────────────────────

/**
 * Entry 02's reads list, pre-filtered to this cycle (p047).
 *
 * ⚠ **ITS OWN `screenId`, AND ITS OWN COLUMN SET.** The blueprint's prose says
 * *"same table, same toolbar, same columns"* and then DRAWS eleven columns where
 * `S25` declares fifteen. B14 rule 41 makes the drawing the specification, so
 * the drawn eleven are what is built — and the column preference is keyed
 * separately so a clerk hiding a column here does not move S25 (the
 * `SET-05` / `SET-05.cycles` precedent).
 *
 * ⚠ **`readsTableConfig` IS NOT REUSED, DELIBERATELY.** It is `ReadsListPage`'s
 * and takes fifteen cell renderers built inside that component's body from its
 * own state; lifting them would be a refactor of a live screen another lane
 * rebuilt this week, for four columns this drawing does not show.
 */
function AllReadsTab(props: {
  cycleId: string;
  cycleCode: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  translate: Translator;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const config = useMemo<TableConfig<ReadRow>>(
    () => ({
      screenId: "S27D.reads",
      getRowId: (row) => row.id,
      defaultSort: { sort: "read_at", dir: "desc" },
      // `reads_queryset` matches the meter number and the premises address.
      searchFields: ["meter", "premise"],
      searchPlaceholder: "metering.cycleDetail.reads.search",
      columns: [
        {
          key: "meter",
          label: t("metering.reads.col.meter"),
          sortable: true,
          identity: true,
          cell: (row) =>
            row.meter === null ? (
              <Dash />
            ) : (
              <InlineLinkTo to={tenantPath(`/reads/${row.id}`)}>{row.meter}</InlineLinkTo>
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
              <DateCell
                value={row.read_at}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            ),
        },
        {
          key: "route",
          label: t("metering.reads.col.route"),
          cell: (row) => (row.route === null ? <Dash /> : <span>{row.route}</span>),
        },
        {
          key: "premise",
          label: t("metering.reads.col.premise"),
          cell: (row) =>
            row.premise === null ? (
              <Dash />
            ) : (
              <span>
                {row.premise}
                {row.unit_label !== null && (
                  <span className={MUTED}> · {row.unit_label}</span>
                )}
              </span>
            ),
        },
        {
          key: "previous",
          label: t("metering.reads.col.previous"),
          numeric: true,
          // ⚠ **THE SERVER'S OWN `<value> <unit>` (hard rule 3, `G44` clause
          //    (b)).** The raw `prior_value` is `NUMERIC(18,6)` and printing it
          //    put `1008.000000` on screen two cells from a usage reading
          //    `8 kgal` (`DEF-1086`).
          cell: (row) =>
            row.prior_value_display === null ? <Dash /> : <span>{row.prior_value_display}</span>,
        },
        {
          key: "current",
          label: t("metering.reads.col.current"),
          numeric: true,
          cell: (row) =>
            row.current_value_display === null ? (
              <Dash />
            ) : (
              <span>{row.current_value_display}</span>
            ),
        },
        {
          key: "usage",
          label: t("metering.reads.col.usage"),
          numeric: true,
          sortable: true,
          // hard rule 3 — a quantity NEVER reaches the screen without its unit,
          // and a dash is the honest answer when there is no quantity at all.
          cell: (row) =>
            row.usage_display === null ? (
              <Dash>{t("metering.reads.usageUnknown")}</Dash>
            ) : (
              <span>{row.usage_display}</span>
            ),
        },
        {
          key: "channel",
          label: t("metering.reads.col.channel"),
          sortable: true,
          cell: (row) => (
            <span>{t(`metering.reads.channel.${row.channel}`, { defaultValue: row.channel })}</span>
          ),
        },
        {
          key: "source",
          label: t("metering.reads.col.source"),
          cell: (row) => (
            <span>{t(`metering.reads.source.${row.source}`, { defaultValue: row.source })}</span>
          ),
        },
        {
          key: "status",
          label: t("metering.reads.col.status"),
          sortable: true,
          cell: (row) => (
            <StatusPill tone={row.status === "verified" ? "success" : "warning"}>
              {t(`metering.reads.status.${row.status}`, { defaultValue: row.status })}
            </StatusPill>
          ),
        },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: readCycleReadsKey(props.cycleId, JSON.stringify(state)),
    queryFn: () =>
      getReads(
        {
          q: state.q,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
          filters: { ...state.filters, cycle: props.cycleId },
        },
        props.client,
      ),
    enabled: props.cycleId !== "",
  });

  return (
    <>
      {/* p047 item 1 — the cycle chip, already applied. It is NOT removable
          here: a cycle's readings list that could be widened to every reading is
          entry 02, and that screen already exists one click away. */}
      <div className="mb-4">
        <StatusPill tone="neutral">
          {t("metering.cycleDetail.reads.scoped", { cycle: props.cycleCode })}
        </StatusPill>
      </div>
      <DataTable<ReadRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.results ?? []}
        totalRows={query.data?.count ?? null}
        loading={query.isPending}
        error={
          query.isError && query.data === undefined
            ? {
                reason: apiErrorText(query.error, props.translate),
                onRetry: () => void query.refetch(),
              }
            : null
        }
        empty={{
          title: t("metering.cycleDetail.reads.emptyTitle"),
          helper: t("metering.cycleDetail.reads.emptyHelper"),
        }}
        downloadSlot={
          <ListExportButton
            resource="reads"
            state={{ ...state, filters: { ...state.filters, cycle: props.cycleId } }}
            client={props.client}
          />
        }
      />
    </>
  );
}

// ── History ────────────────────────────────────────────────────────────────

/**
 * **THE ONE TAB NOTHING SERVES, DRAWN AS AN HONEST ABSENCE AND NOT AS A TABLE.**
 *
 * p046 draws twelve windows of this cycle with a `REGISTERS COLLECTED` and an
 * `ESTIMATED` column per window, over a warning panel reading *"NOTHING SERVES
 * THIS YET"*. The blueprint's own source table agrees — ⑥ `History · last three
 * windows` · **NOT SERVED** — and its note says the tab *"is drawn in its own
 * tab precisely so it can be dropped from wave one without moving anything
 * else"*.
 *
 * **So the table is not drawn over invented rows.** A list filled with
 * placeholder data is this repo's most expensive habit, and `completeness`
 * answers ONE window at a time, so twelve rows would be twelve calls to an
 * engine whose window derivation is exactly what `DEF-MET-5206` blocks.
 *
 * ⚠ **THE DRAWN SENTENCE IS NOT THE ONE RENDERED, AND THAT IS `B14` RULE 33.**
 * The drawing writes *"This tab needs one endpoint that does not exist.
 * Everything else on this page is served today."* — twenty-one words, and the
 * first half is RATIONALE, which rule 33 puts at **zero words on screen**. What
 * a clerk needs is the FACT and what to do instead.
 */
function HistoryTab(props: { t: (key: string, params?: Record<string, unknown>) => string }) {
  const { t } = props;
  return (
    <Panel as="section" tone="warning" title={<Kicker>{t("metering.cycleDetail.history.title")}</Kicker>}>
      <Note>{t("metering.cycleDetail.history.body")}</Note>
    </Panel>
  );
}

// ── The reading sheet ──────────────────────────────────────────────────────

/**
 * *"Reading sheet · The blank sheet to walk with, scoped to this cycle"* (p047).
 *
 * `BR-SHL-025` — a control this cycle cannot honour renders DISABLED WITH ITS
 * REASON, in the SERVER's own words where the server has them. `ReadingSheetButton`
 * on the upload wizard says the same three things; this one has no *"no cycle
 * tagged"* case, because the cycle is the page.
 */
function ReadingSheetButton(props: {
  cycleId: string;
  window: string;
  rows: number | null;
  absentReason: string | null;
  loading: boolean;
  error: string | null;
  t: Translator;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const reason =
    props.error !== null
      ? props.error
      : props.loading
        ? t("metering.cycleDetail.action.sheetLoading")
        : props.absentReason !== null
          ? t("metering.read.reason.cycle_window_not_set")
          : props.rows === 0
            ? t("metering.cycleDetail.action.sheetEmpty")
            : null;
  return (
    <GuardedButton
      label={t("metering.cycleDetail.action.readingSheet")}
      reason={reason}
      onClick={() =>
        window.open(
          apiHref(
            `${tenantPath(`/cycles/${props.cycleId}/reading-sheet`)}${
              props.window === "" ? "" : `?period=${encodeURIComponent(props.window)}`
            }`,
          ),
          "_blank",
          "noopener",
        )
      }
    />
  );
}

export default ReadCycleDetailPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: Meter Reads blueprint entry 20 (p042–p048, read as images) · PO
//   rulings of 2026-09-14 (`Q1` BR-MET-011 narrowed · `Q2` reversed, the
//   Reads→Work door is built · `Q3` walk order is Settings-only · `Q4`
//   DEF-MET-5206 "Settle first" · `Q6` a permanent refusal is removed)
// generated: 2026-09-14 by the Meter Reads entry-20 lane
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest ReadCycleDetailPage.test.tsx · G31 (this file is on
//   styles/route-b-migrated.txt, added in the commit that created it)
// exceptions:
//   E1 the drawn **Window pill** and **Registers collected** (roll-up clause,
//      Collection figure + denominator, Routes panel column, Routes tab column,
//      History column) are NOT built — `DEF-MET-5206`, PO *"Settle first."*
//   E1 **History's twelve-window table** is NOT built — ⑥ NOT SERVED on the
//      blueprint's own source table; the honest absence is rendered instead
//   E3 the Still-to-read table's pager is a CLIENT slice — `DEF-MET-5210`, the
//      chase endpoint has no pager and the backend suite cannot run here
//   E3 the Routes tab's search prompt names CODE and NAME, not the reader: the
//      server searches neither the assignee nor anything but those two columns
//      (`DEF-MET-5211`), and B14 rule 19's prompt is written from the predicate
//   E4 **five tabs, not the four the blueprint's prose counts** — every frame
//      draws five and All reads carries its own annotated page (rule 41)
//   E4 ~~the Routes tab's third row action (*reassign*) is ABSENT~~ —
//      SUPERSEDED 2026-10-24 (PO, MQ-033, `DEF-MET-10591`): the Reader column,
//      the *Assign / Reassign reader* row action (in the `…` overflow, rule 15)
//      and a bulk *Assign reader* are BUILT on this tab, superseding `CR-029`
//      D6 and `OQ-343` here only. The walk order stays Settings' (`Q3`).
// amended: 2026-10-24 by the MQ-033 task-9 lane (reader assignment)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
