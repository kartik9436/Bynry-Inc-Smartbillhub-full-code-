// ── Trace ──────────────────────────────────────────────
// Change:   CR-038 · ADDITION 2026-08-26 — **W5 task 8, the METER half** of
//           trailing-12-month consumption. PO verbatim: *"We ahve to calcualet
//           last 12 month consumption from these readings and display it on
//           account and meters"*. The account half is
//           `features/customers/AccountUsageTab.tsx`; this is the meter half
//           CR-038 measured as the gap.
//           Screens: S50 (asset detail — the Reads tab)
// Story:    US-AST-005 (the S50 Reads tab)
// Rules:    BR-MET-106 (a month is computed from reads; an unread month is
//           ABSENT, never 0; estimates count and are MARKED) · BR-MET-135
//           (`generation` is never summed with consumption) · BR-AST-029
//           (`export` likewise) · BR-RAT-014 (demand measures kW, not kWh) ·
//           CLAUDE.md hard rule 3 (an explicit unit, ALWAYS) · B14 rule 21
//           (Tailwind utilities; this file adds NO class to any stylesheet)
// Defects:  DEF-798 (the monthly figure summed across registers unit-blind —
//           684 + 14 = 698 kWh where the truth is 684 kWh)
// Tests:    07-frontend/src/features/assets/AssetUsageStrip.test.tsx
// Impacts:  AssetDetailPage.tsx mounts it at the head of the Reads tab ·
//           06-backend/apps/metering/api.py `GET /assets/{id}/usage`
// ───────────────────────────────────────────────────────
//
// ────────────────────────────────────────────────────────────────────────────
// WHY THIS IS SEVERAL CHARTS AND NEVER ONE — DEF-798, ON SCREEN
// ────────────────────────────────────────────────────────────────────────────
// The account tab draws one series per SERVICE, because kWh and kgal do not
// add. This draws one series per REGISTER, for the same reason one level down:
// a demand register's figure is a delta between two maxima in kW (BR-RAT-014),
// a net meter's `export` is energy that went the other way (BR-AST-029) and a
// device's `generation` is production BR-MET-135 says is *"never summed with
// consumption"*. DEF-798 is what happens when they are added anyway — a
// measured 698 kWh on an account that used 684.
//
// **A meter is exactly where several registers live**, so this screen is where
// that defect is most visible, and it is built so that there is no code path
// that could produce a blended total. There is no "meter total" tile.
//
// **A non-consumption register is DRAWN and LABELLED, not hidden.** Hiding the
// demand register would leave a clerk looking at a demand meter an empty chart
// — the honest thing is to show the peak and say plainly that it is not usage.
//
// ⚠ **THE FIGURES ARE COMPUTED SERVER-SIDE, NOT READ FROM THE STORED MONTHLY
// ROW** — `monthly_usage` is keyed (account, service, month) and has no asset
// grain, so it cannot answer for one meter. The payload says so itself
// (`source` + `stored_source_absent`), the screen repeats it in one line rather
// than implying the two surfaces read the same row, and **OQ-421** is the
// question that would close the gap. Hard-won law 1: the claim travels.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Disclosure } from "@/components/Disclosure";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import type { Translator } from "@/features/tenancy/settingsShared";

import { channelLabel } from "./assetsShared";

/** The windows `GET /assets/{id}/usage` accepts. 12 is the PO's own word for
 *  this task (*"last 12 month consumption"*); 24 is the comparison a clerk
 *  reaches for and the axis is free. */
const WINDOWS = [12, 24] as const;

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
const CHART_HEIGHT = "h-[140px]";

// ── the payload, typed exactly as `asset_usage.asset_usage_payload` serves ──
// Declared LOCALLY, following `AccountUsageTab`'s own precedent and for its
// reason: `api/endpoints.ts` is a shared file, and a wrapper there plus a type
// here would be two contracts to keep in step (hard-won law 5).
export interface AssetUsagePoint {
  month: string; // "2026-07"
  quantity: string | null; // stored precision; NULL = the month is ABSENT
  quantity_display: string | null; // 2 dp, trailing zeros stripped
  unit: string | null;
  absent: boolean;
  read_count: number;
  estimated_read_count: number;
  estimated: boolean;
}

export interface AssetUsageMetric {
  value: string | null;
  display: string | null;
  unit: string | null;
  month?: string | null;
  absent_reason: string | null;
  months_counted?: number;
  months_absent?: number;
}

export interface AssetUsageSeries {
  channel: string;
  /** DEF-798's fact, on the wire: is this register CONSUMPTION at all? */
  is_consumption: boolean;
  unit: string | null;
  unit_absence: { reason: string; tracks: string } | null;
  points: AssetUsagePoint[];
  months_present: number;
  months_absent: number;
  metrics: {
    avg_per_month: AssetUsageMetric;
    peak: AssetUsageMetric;
    low: AssetUsageMetric;
    yoy: AssetUsageMetric;
  };
}

export interface AssetUsagePayload {
  asset_id: string;
  asset_no: string;
  window: { months: number; from: string; to: string; options: number[] };
  series: AssetUsageSeries[];
  rule_ref: string;
  source: string;
  stored_source_absent: { reason: string; tracks: string } | null;
}

export function assetUsageKey(assetId: string, months: number) {
  return ["asset-usage", assetId, months] as const;
}

export async function getAssetUsage(
  assetId: string,
  months: number,
  client: ApiClient = api,
): Promise<AssetUsagePayload> {
  const response = await client.get<AssetUsagePayload>(
    `/assets/${encodeURIComponent(assetId)}/usage`,
    { query: { months } },
  );
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export type UsageStripState = "loading" | "failed" | "ready";

/**
 * Which frame the strip shows — a PURE function, and not for tidiness.
 *
 * ⚠ `isError` is checked BEFORE `isPending`, and it matters: a query that has
 * errored and is retrying is BOTH, and asking `isPending` first tells the
 * "still waiting" story about a call that has already failed. Same reasoning,
 * same shape as `AccountUsageTab.usageViewState` — deliberately not shared,
 * because a helper imported across two feature folders is a coupling neither
 * screen asked for.
 */
export function usageStripState(query: {
  isPending: boolean;
  isError: boolean;
  data: unknown;
}): UsageStripState {
  if (query.isError || (!query.isPending && query.data === undefined)) {
    return "failed";
  }
  if (query.isPending || query.data === undefined) {
    return "loading";
  }
  return "ready";
}

/**
 * The trailing-12-month strip for one meter.
 *
 * `client` mirrors every other panel on this page: optional, defaulted, and
 * PASSED by the mount (G13 — an optional prop nothing passes is dead UI, and
 * DEF-520 is what that costs).
 */
export function AssetUsageStrip(props: { assetId: string; client?: ApiClient; t: Translator }) {
  const { t } = props;
  const [months, setMonths] = useState<number>(12);

  const query = useQuery({
    queryKey: assetUsageKey(props.assetId, months),
    queryFn: () => getAssetUsage(props.assetId, months, props.client ?? api),
    retry: false,
    enabled: props.assetId !== "",
  });

  const state = usageStripState(query);
  if (state !== "ready" || query.data === undefined) {
    return (
      <section className="mb-4">
        <h3>{t("assets.usage.title")}</h3>
        <p className={`m-0 text-base ${MUTED}`}>
          {t(`assets.usage.${state === "failed" ? "failed" : "loading"}`)}
        </p>
      </section>
    );
  }

  const payload = query.data;

  return (
    <section className="mb-4">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
        <h3>{t("assets.usage.title")}</h3>
        <div
          className="flex gap-1"
          role="group"
          aria-label={t("assets.usage.windowLabel")}
        >
          {WINDOWS.map((option) => (
            <button
              key={option}
              type="button"
              className={`cursor-pointer border-0 px-3 py-[7px] text-sm ${
                months === option
                  ? "bg-accent text-bg"
                  : "bg-transparent text-text hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
              }`}
              aria-pressed={months === option}
              onClick={() => setMonths(option)}
            >
              {t("assets.usage.window", { months: option })}
            </button>
          ))}
        </div>
      </div>

      {payload.series.length === 0 ? (
        // NOT an `ArrivesWith`: nothing is missing from the product. This meter
        // has no committed reads, which is a state a clerk can be told plainly.
        <p className={`m-0 text-base ${MUTED}`}>{t("assets.usage.empty")}</p>
      ) : payload.series.length === 1 ? (
        // ONE register — the plain panel screen 09's Figure 13 draws. A
        // disclosure over a list of one is a control that does nothing.
        <RegisterChart series={payload.series[0]} months={months} t={t} />
      ) : (
        <RegisterList series={payload.series} months={months} t={t} />
      )}

      {/* Hard-won law 1: the account tab reads a STORED row and this does not.
          The claim travels rather than being left in a docstring nobody on the
          screen can read. */}
      {payload.stored_source_absent !== null && (
        <p
          className={`m-0 mt-2 text-sm ${MUTED}`}
          data-tracks={payload.stored_source_absent.tracks}
        >
          {t("assets.usage.computedNote")}
        </p>
      )}
    </section>
  );
}

/**
 * Every register of a multi-register meter — the FIRST open, the rest closed.
 *
 * ⚠ **WHY THIS EXISTS: THE READ LOG STARTED 2.6 SCREENS BELOW THE FOLD**
 * (`DEF-MET-4970`). One full panel per register — chart, date range, gap
 * sentence and three tiles — put the readings a clerk opened the Reads tab for
 * at **y = 2,324px against a 900px viewport** on a five-register time-of-use
 * meter, and repeated *"N of 12 months have no reading."* five times on one
 * screen. Screen 09's own drawing (Figure 13) shows ONE panel.
 *
 * ⚠ **AND `DEF-798` SURVIVES IT INTACT, WHICH IS THE CONSTRAINT THAT SHAPED
 * THIS RATHER THAN A TAB STRIP OR A PICKER.** `Disclosure`'s own law is that
 * *collapsing never hides a number*: the closed row still carries the
 * register's NAME, its own UNIT and its own average, and still says *not
 * consumption* where that is true. So every register is named and figured on
 * arrival, nothing is blended, and there is still no code path that could
 * produce a meter total. A picker would have hidden the other registers'
 * existence behind a click; this hides only their derivation.
 *
 * The first is open because a clerk's first question is about the register the
 * bill is computed from, and the server serves `total` first.
 */
function RegisterList(props: {
  series: readonly AssetUsageSeries[];
  months: number;
  t: Translator;
}) {
  const { t } = props;
  return (
    // ⚠ A WITNESS, NOT A STYLE HOOK. A walkthrough has to be able to count the
    // register rows without matching the app shell's own `aria-expanded`
    // controls — the first draft of `DEF-MET-4970`'s browser check did exactly
    // that and reported *"5 registers"* on a four-register meter.
    <div
      className="border border-divider bg-surface"
      data-register-list={props.series.length}
      // A reader arriving here with a keyboard meets N expand controls with no
      // sentence saying what they are a list OF — the same reason the window
      // control above carries one.
      role="group"
      aria-label={props.t("assets.usage.registerLabel")}
    >
      {props.series.map((series, index) => (
        <Disclosure
          key={series.channel}
          variant="row"
          defaultOpen={index === 0}
          title={channelLabel(series.channel, t) ?? series.channel}
          summary={series.unit ?? t("assets.usage.unitUnknown")}
          // The figure that must stay readable with the row closed.
          value={registerAverage(series, t)}
          status={
            series.is_consumption ? undefined : (
              <span data-consumption="false">{t("assets.usage.notConsumption")}</span>
            )
          }
        >
          <RegisterChart series={series} months={props.months} t={t} chrome={false} />
        </Disclosure>
      ))}
    </div>
  );
}

/** The closed row's number — avg per month, with its own unit, or the served
 *  absence sentence. Exactly `registerTiles`' Avg tile, so the two can never
 *  disagree about the same register. */
function registerAverage(series: AssetUsageSeries, t: Translator): string {
  const metric = series.metrics.avg_per_month;
  return metric.display === null
    ? t(`assets.usage.absent.${metric.absent_reason ?? "unavailable"}`)
    : `${metric.display}${metric.unit === null ? "" : ` ${metric.unit}`}`;
}

/**
 * ONE register's chart. Never a blend of two.
 *
 * ⚠ **THE BAR HEIGHTS ARE INLINE STYLES AND HAVE TO BE.** A bar's height is a
 * number computed from data; there is no class for `61.7%`, and inventing a
 * hundred utilities to cover the range would be worse. Everything that is NOT
 * data — the row, the gap, the axis rule — is a utility (B14 rule 21).
 */
function RegisterChart(props: {
  series: AssetUsageSeries;
  months: number;
  t: Translator;
  /** `false` when a `Disclosure` header already carries the register's name,
   *  its unit and its not-consumption marker — drawing them twice would be the
   *  same fact said twice on one screen (`AST-R-09`'s own rule). */
  chrome?: boolean;
}) {
  const { series, t } = props;
  const chrome = props.chrome ?? true;
  const present = series.points.filter((p) => !p.absent);
  const peak = present.reduce((max, p) => Math.max(max, Number(p.quantity ?? 0)), 0);
  const estimatedMonths = present.filter((p) => p.estimated).length;

  return (
    <div
      className={chrome ? "mb-4 border border-divider bg-surface p-3" : ""}
      data-register-chart={series.channel}
    >
      {chrome && (
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        {/* The unit is in the title because it is the whole chart's unit —
            hard rule 3, on screen.
            ✅ DEF-MET-4969 (2026-09-12) — the register is NAMED now. This read
            `channel: series.channel` and printed `tou_on` to a clerk, under a
            comment claiming no vocabulary existed; `metering.reads.channel.*`
            ships all seven words in all eleven catalogues and six files in the
            neighbouring module already resolve them. */}
        <h4 className="m-0 text-base">
          {t("assets.usage.chartTitle", {
            channel: channelLabel(series.channel, t) ?? series.channel,
            months: props.months,
            unit: series.unit ?? t("assets.usage.unitUnknown"),
          })}
        </h4>
        {/* DEF-798, on screen: a register nobody consumed says so, right next
            to its own figures, so no reader totals it into usage. */}
        {!series.is_consumption && (
          <span className={`text-sm ${MUTED}`} data-consumption="false">
            {t("assets.usage.notConsumption")}
          </span>
        )}
      </div>
      )}

      {series.unit_absence !== null && (
        <p className={`m-0 mb-2 text-sm ${MUTED}`} data-tracks={series.unit_absence.tracks}>
          {t("assets.usage.mixedUnits")}
        </p>
      )}

      <div
        className={`flex items-end gap-1 border-b border-divider py-3 ${CHART_HEIGHT}`}
        role="img"
        aria-label={t("assets.usage.chartAria", {
          channel: channelLabel(series.channel, t) ?? series.channel,
          months: series.months_present,
        })}
      >
        {series.points.map((point) => (
          <UsageBar key={point.month} point={point} peak={peak} t={t} />
        ))}
      </div>

      <p className={`m-0 mt-2 text-sm ${MUTED}`}>
        {t("assets.usage.axis", {
          from: series.points[0]?.month ?? "",
          to: series.points[series.points.length - 1]?.month ?? "",
        })}
      </p>

      {/* BR-MET-106, on screen: an unread month is STATED, never drawn as 0. */}
      {series.months_absent > 0 && (
        <p className={`m-0 mt-1 text-sm ${MUTED}`}>
          {t("assets.usage.absentMonths", {
            absent: series.months_absent,
            total: series.points.length,
          })}
        </p>
      )}

      {/* BR-MET-106, on screen: the estimate is counted AND recorded. */}
      {estimatedMonths > 0 && (
        <p className={`m-0 mt-1 text-sm ${MUTED}`}>
          {t("assets.usage.estimatedMonths", { months: estimatedMonths })}
        </p>
      )}

      <div className="mt-3">
        <KPIStrip kpis={registerTiles(series, t)} />
      </div>
    </div>
  );
}

function UsageBar(props: { point: AssetUsagePoint; peak: number; t: Translator }) {
  const { point, t } = props;
  if (point.absent) {
    // No bar. An empty slot that says what it is, and nothing a reader could
    // take as "this meter measured nothing".
    return (
      <div
        className="h-full flex-1 self-stretch"
        data-month={point.month}
        data-absent="true"
        title={t("assets.usage.absentMonth", { month: point.month })}
      />
    );
  }
  const value = Number(point.quantity ?? 0);
  // A 2% floor so a very small month reads as a mark rather than disappearing
  // into the axis, where it would look like an absence.
  const height = props.peak > 0 ? Math.max(2, (value / props.peak) * 100) : 2;
  return (
    <div
      className="flex-1 self-end"
      data-month={point.month}
      data-absent="false"
      data-estimated={point.estimated ? "true" : "false"}
      title={t(point.estimated ? "assets.usage.barTitleEstimated" : "assets.usage.barTitle", {
        month: point.month,
        value: point.quantity_display ?? "",
        unit: point.unit ?? "",
      })}
      style={{
        height: `${height}%`,
        background: "var(--color-accent)",
        // The estimated month is MARKED, not hidden and not equal-looking.
        opacity: point.estimated ? 0.55 : 1,
        outline: point.estimated ? "1px dashed var(--color-accent)" : undefined,
        outlineOffset: point.estimated ? "-1px" : undefined,
      }}
    />
  );
}

/** Avg · peak · low for ONE register. Every tile carries the register's own
 *  unit, so two strips on one page can never be read as one number. */
function registerTiles(series: AssetUsageSeries, t: Translator): readonly KpiTile[] {
  const value = (metric: AssetUsageMetric) =>
    metric.display === null
      ? t(`assets.usage.absent.${metric.absent_reason ?? "unavailable"}`)
      : `${metric.display}${metric.unit === null ? "" : ` ${metric.unit}`}`;

  return [
    {
      id: `${series.channel}-avg`,
      label: t("assets.usage.kpi.avg"),
      value: value(series.metrics.avg_per_month),
      detail: t("assets.usage.kpi.basis.last12"),
    },
    {
      id: `${series.channel}-peak`,
      label: t("assets.usage.kpi.peak"),
      value: value(series.metrics.peak),
      detail: series.metrics.peak.month ?? undefined,
    },
    {
      id: `${series.channel}-low`,
      label: t("assets.usage.kpi.low"),
      value: value(series.metrics.low),
      detail: series.metrics.low.month ?? undefined,
    },
  ];
}

export default AssetUsageStrip;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-038 ADDITION 2026-08-26 (W5 task 8, meter half) + BR-MET-106 + DEF-798
// generated: 2026-08-26 by the CR-038 W5 tasks 6/7/8 lane · AMENDED 2026-09-12 by the CR-092-BRC01 step 2 lane 2 (`DEF-MET-4969` — the register is NAMED through `assetsShared.channelLabel`, because `metering.reads.channel.*` had shipped the words in all eleven catalogues all along; `DEF-MET-4970` — a meter with MORE THAN ONE register draws ONE chart panel and the rest as `Disclosure` rows, measured 1,214px → 907px at 1280 and 884px at 1440 for the read log below it. `DEF-798` survives intact and one half of it got stronger: a collapsed row still carries its register's name, its own unit, its own average and its *not consumption* marker, which the old layout never had to prove)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint✔ · vitest (AssetUsageStrip.test.tsx) · g31 (utilities only — NO new stylesheet class) · g13 (`client` is optional and the mount passes it) · g40 (mounted from AssetDetailPage's Reads tab) · 2026-09-12: tsc✔ eslint✔ vitest src/features/assets 208 passed/12 todo/0 failed across 10 files, rebased onto the tip · 38 of 38 browser checks at 1280 AND 1440 (`10-scripts/cr092_lane2_asset_detail_walkthrough.mjs`)
// exceptions: ✅ **E3 IS RETIRED AND WAS NEVER TRUE (`DEF-MET-4969`, 2026-09-12).** It read *"the register renders as the SERVED CODE (`total` · `demand`) — no signed vocabulary maps a channel to a display word … inventing one here would be a rule this screen does not get to write"*, and `metering.reads.channel.*` had already shipped SEVEN keys in ALL ELEVEN catalogues, resolved by six files in the neighbouring module. So a clerk read `tou_on` and `tou_mid` off this screen for as long as it has existed, under a comment asserting an ABSENCE — hard-won law 1 in its quietest form, and the reason it hid is that an exception in a lifecycle block reads as a DECISION rather than as something that went stale. The register is named through `assetsShared.channelLabel` now. **The lesson generalises past this file: an exception that claims nothing exists has to be re-checked, because nothing ages worse than an absence** · E3 there is NO "meter total" tile and no code path that could produce one (DEF-798) · E3 the figures are COMPUTED server-side rather than read from the stored monthly row: `monthly_usage` has no asset grain, the payload says so, and the screen repeats it in one line naming OQ-421 · E3 bar HEIGHTS are inline styles because they are data; every non-data style is a utility
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
