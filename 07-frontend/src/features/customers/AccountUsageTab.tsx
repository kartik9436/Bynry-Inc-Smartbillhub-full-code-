// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W3 task 3.8 — the ACC-01 **Usage** tab. Design:
//           04-docs/02-decisions/18-cr030-onboarding-design.md §5.2.2, Usage
//           row. Reference drawing: 05-prototype/r10-2026-08-16/
//           SMARTBillHub.dc.html, account detail (the `<!-- USAGE -->` block).
//           Screens: S21 (Usage tab)
// Story:    US-CUS-011 (the S21 operational tabs — Usage is the first of five)
// Rules:    BR-MET-106 (a month's usage is computed from reads, STORED and
//           DISPLAYED; an unread month is ABSENT, never `0`; estimates count
//           and are MARKED — PO 2026-08-24) · CLAUDE.md hard rule 3 (kWh and
//           kgal are never added together, so `All` is several series) ·
//           BR-SHL-010 (an undeclared capability is not rendered — why
//           `Compare to neighbors →` is NOT drawn) · BR-CUS-034 (customers
//           keeps no copy of another module's row — the figures come from
//           metering's own endpoint) · B14 rule 21 (Tailwind utilities; this
//           file adds NO class to any stylesheet) · B14 rule 20 (one table
//           type — none is used here)
// Tests:    07-frontend/src/features/customers/AccountUsageTab.test.tsx
// Impacts:  AccountDetailPage.tsx mounts it in place of the Usage tab's
//           `ArrivesWith` (ONE line — see the note below) ·
//           06-backend/apps/metering/api.py `GET /accounts/{id}/usage`
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT MOUNTING THIS COSTS — ONE LINE, AND IT IS NOT WRITTEN HERE.**
// `AccountDetailPage.tsx` belongs to another lane today, so the mount is owed
// rather than done. The block to replace is its `active === "usage"` branch,
// which today renders
//
//     <ArrivesWith title={…tab.usage} message={…arrives.usage} tracks="DEF-475" />
//
// and whose sentence is STALE twice over (hard-won law 1): it blames a reads
// filter CR-028 shipped, and DEF-475 is CLOSED. The replacement is
//
//     {active === "usage" && (
//       <AccountUsageTab accountId={detail.id} client={props.client} t={translate} />
//     )}
//
// Until that lands this component is DEAD UI and G40 will say so. That is the
// point of G40 (hard-won law 2, DEF-520): built is not wired.
//
// ────────────────────────────────────────────────────────────────────────────
// WHAT r10 DRAWS AND WHAT THIS RENDERS, DIFFERENCE BY DIFFERENCE
// ────────────────────────────────────────────────────────────────────────────
// r10's `<!-- USAGE -->` block is: a segment control (`Electric` `Water` `All`)
// with a `+ Filter ▾` titled *"Filter by: 12 months, 24 months"*, a panel headed
// `Electric usage · 24 months (kWh)` with a 24-bar chart, and a five-tile KPI
// strip — `Avg / month 628 kWh · last 12 months` · `Peak month 842 kWh · Jul
// 2026` · `Low month 412 kWh · Feb 2026` · `YoY change +8.2% · vs prior year` ·
// `Water avg 3.42 kgal · last 12 months`.
//
//   * **The segment vocabulary is the ACCOUNT's services, not a fixed pair.**
//     r10 hard-codes Electric and Water because its fixture has two. An account
//     with only electric gets one chip and `All`, never a Water chip that draws
//     an empty chart.
//   * **`All` draws EVERY service's series, side by side — never one summed
//     line.** kWh and kgal do not add (hard rule 3), so there is no single
//     "total usage" number and this screen does not invent one.
//   * **A month with no reading has NO BAR**, an empty slot with its own
//     tooltip, and the chart says how many such months there are. BR-MET-106:
//     *"zero usage and no read are different claims about a customer"*. A zero
//     bar is the claim we are forbidden to make.
//   * **A month that includes an estimate is MARKED** — a hatched bar and a
//     line under the chart. BR-MET-106: *"a customer looking at a 628 kWh month
//     is entitled to know part of it was estimated"*.
//   * **`Compare to neighbors →` IS NOT DRAWN.** B18 §5.2.2 records it as `D3`,
//     a feature nobody has specified; BR-MET-106 rules the chart and the strip
//     and says nothing about it. It is OMITTED rather than rendered disabled,
//     following the precedent one tab over — r10's read-log `Export` control is
//     not drawn either, because `POST /exports` registers no reads resource
//     (BR-SHL-010: an undeclared capability is not rendered). A disabled
//     control would need a reason to show a customer, and *"nobody has
//     specified this"* is our sentence, not theirs.
//   * **The `+ Filter ▾` control is a plain pair of window buttons.** r10 draws
//     a filter menu whose only contents are `12 months, 24 months`; a menu with
//     two mutually exclusive items is two buttons.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DateCell, formatMonthYear } from "@/components/DateCell";
import { SelectField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { formatQuantity } from "@/components/UnitCell";
import { useRegional } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The window options `GET /accounts/{id}/usage` accepts (r10's own filter). */
const WINDOWS = [12, 24] as const;

/** `All` is not a service — it is "draw every series". */
// ⚠ EXPORTED 2026-09-13: the Overview's `Usage trend` group draws every
// service at once (the blueprint's `MONTH · ELECTRIC · WATER` table), so it
// asks `readOuts` for the `All` shape rather than re-deriving one.
export const USAGE_ALL = "__all__";
const ALL = USAGE_ALL;

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
const CHART_HEIGHT = "h-[200px]";

// ── the payload, typed exactly as `monthly_usage_reads.usage_payload` serves ─
// Deliberately local rather than added to `api/endpoints.ts`: that file is
// another lane's today, and a type that describes a payload it does not wrap
// would be a second contract to keep in step (hard-won law 5).
export interface UsagePoint {
  month: string; // "2026-07"
  quantity: string | null; // stored precision; NULL = the month is ABSENT
  quantity_display: string | null; // 2 dp, trailing zeros stripped
  unit: string | null;
  absent: boolean;
  read_count: number;
  estimated_read_count: number;
  estimated: boolean;
  computed_at: string | null;
  /**
   * The readings behind the month (`monthly_usage_reads._reading_block`, PO
   * 2026-10-15). `null` on an absent month; optional because only the staff
   * endpoint serves it.
   */
  reading?: UsageReading | null;
}

/** `check` codes, worst first — `monthly_usage_reads.CHECK_RANK`. */
export type UsageCheck = "high" | "low" | "flagged" | "zero" | "estimated" | "ok";

export interface UsageReading {
  read_count: number;
  read_on: string; // "2026-09-28", the LATEST reading's date
  source: string; // ami | manual | import | estimated
  read_method: string | null;
  read_method_origin: string;
  previous_reading: string | null; // the EARLIEST reading's prior value
  previous_reading_display: string | null;
  current_reading: string | null; // the LATEST reading's current value
  current_reading_display: string | null;
  reading_unit: string | null;
  readings_absent_reason: string | null; // "several_registers"
  check: UsageCheck;
  status: string;
}

export interface UsageMetric {
  value: string | null;
  display: string | null;
  unit: string | null;
  month?: string | null;
  /**
   * Which service this figure is about — served ONLY on `water_avg`, the one
   * figure that is not part of any series. The screen uses it to decide
   * whether the figure belongs on screen at all, and it comes from the SERVER
   * so that no component has to type a service code (hard-won law 2).
   */
  service_code?: string;
  absent_reason: string | null;
  description?: string;
  months_counted?: number;
  months_absent?: number;
  this_year_total?: string | null;
  prior_year_total?: string | null;
}

export interface UsageServiceRef {
  id: string;
  code: string;
  name: string;
}

export interface UsageSeries {
  service: UsageServiceRef;
  unit: string | null;
  unit_absence: { reason: string; tracks: string } | null;
  points: UsagePoint[];
  months_present: number;
  months_absent: number;
  metrics: {
    avg_per_month: UsageMetric;
    peak: UsageMetric;
    low: UsageMetric;
    yoy: UsageMetric;
  };
}

export interface UsagePayload {
  account_id: string;
  window: { months: number; from: string; to: string; options: number[] };
  services: UsageServiceRef[];
  series: UsageSeries[];
  water_avg: UsageMetric;
  rule_ref: string;
}

export function accountUsageKey(accountId: string, months: number) {
  return ["account-usage", accountId, months] as const;
}

export async function getAccountUsage(
  accountId: string,
  months: number,
  client: ApiClient = api,
): Promise<UsagePayload> {
  const response = await client.get<UsagePayload>(
    `/accounts/${encodeURIComponent(accountId)}/usage`,
    { query: { months } },
  );
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export type UsageViewState = "loading" | "failed" | "ready";

/**
 * Which of the three frames the tab shows — extracted as a PURE function, and
 * that is not tidiness.
 *
 * ⚠ **THE FAILURE FRAME CANNOT BE REACHED THROUGH `renderToStaticMarkup`.**
 * Measured on react-query 5 in this repo: a query whose cached state is
 * `status: "error"` reports `pending / fetching` to a SERVER render, because
 * the server snapshot ignores a cached error and starts the query optimistically.
 * So a static first-paint suite — the repo's default `node` tier — renders the
 * LOADING frame for a broken endpoint and can assert nothing about the failure
 * one. Pulling the decision out here is what lets the case be tested at all
 * without opening a jsdom suite for one branch.
 *
 * ⚠ **`isError` IS CHECKED BEFORE `isPending`, AND IT MATTERS.** A query that
 * has errored and is retrying is BOTH errored and fetching; asking `isPending`
 * first tells the "still waiting" story about a call that has already failed.
 */
export function usageViewState(query: {
  isPending: boolean;
  isError: boolean;
  data: unknown;
}): UsageViewState {
  if (query.isError || (!query.isPending && query.data === undefined)) {
    return "failed";
  }
  if (query.isPending || query.data === undefined) {
    return "loading";
  }
  return "ready";
}

/**
 * The Usage tab. One prop set, no optional data prop that nothing passes.
 *
 * `client` mirrors `RecentBillsPanel`'s: optional, defaulted to the shared
 * client, and PASSED by the mount above so the test seam has a real caller
 * (G13 — an optional prop nothing passes is dead UI).
 */
export function AccountUsageTab(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  // ⛔ `defaultMonths` is DELETED (`DEF-GOV-10106`). It existed so the
  // Overview's `Usage trend` panel could open this on 12 months; that panel no
  // longer mounts this component, so no caller passed it and G13 named it dead
  // UI. The tab opens on 24, which is r10's own Usage screen
  // (`Electric usage · 24 months`), and the window buttons still switch it.
}) {
  const { t } = props;
  const [months, setMonths] = useState<number>(24);
  // `null` = the clerk has not chosen; the default is DERIVED from the payload
  // below, because the account's own services are not known until it arrives.
  const [segment, setSegment] = useState<string | null>(null);

  const query = useQuery({
    queryKey: accountUsageKey(props.accountId, months),
    queryFn: () => getAccountUsage(props.accountId, months, props.client ?? api),
    retry: false,
    enabled: props.accountId !== "",
  });

  const state = usageViewState(query);
  if (state !== "ready" || query.data === undefined) {
    return (
      <Panel as="section">
        <h3>{t("customers.account.usage.title")}</h3>
        <p className={`m-0 text-base ${MUTED}`}>
          {t(`customers.account.usage.${state === "failed" ? "failed" : "loading"}`)}
        </p>
      </Panel>
    );
  }

  const payload = query.data;
  // ⚠ **WHICH SERVICE IS ON SCREEN IS RESOLVED HERE, NOT IN `useState`.**
  // The tab opens on the account's FIRST service so it draws ONE trend
  // (PO 2026-09-07: *"can you do dropdown - for utility services - dyamically
  // so that user can see one data at a time"*). The account's services are
  // not known until the payload lands, so the state holds only what the clerk
  // CHOSE and the default is derived from the data on every render.
  const chosen = segment ?? payload.services[0]?.code ?? ALL;
  const shown =
    chosen === ALL ? payload.series : payload.series.filter((s) => s.service.code === chosen);

  return (
    /* `data-account-overview` and the per-group `data-overview-group` hooks are
       what the BROWSER census selects on (`10-scripts/render-checks/
       acc02-tab-conformance.mjs`): jsdom computes no layout, so no vitest case
       in this repo can say the screen LOOKS like the drawing. One column on
       this tab, because the drawing gives it one. */
    <div data-account-overview="">
      <div className="flex min-w-0 flex-col">
      {/* r10's toolbar: the service picker on the left, the window filter on
          the right. ⚠ **THE PICKER'S VOCABULARY IS `payload.services` — the
          account's own — and never a list of service names typed here.** That
          is how an eleventh service reaches a screen at all (hard-won law 2:
          `SignupWizard` and `ratingShared` each type the list out and an
          eleventh service silently never appeared). An account with ONE
          service is not asked to choose and gets no picker. */}
      <div className="mb-3 flex flex-wrap items-end gap-3">
        {payload.services.length > 1 && (
          <SelectField
            id="usage-service"
            label={t("customers.account.usage.segmentLabel")}
            value={chosen}
            onChange={setSegment}
            options={[
              ...payload.services.map((service) => ({
                value: service.code,
                label: service.name,
              })),
              { value: ALL, label: t("customers.account.usage.segment.all") },
            ]}
          />
        )}
        <div
          className="ml-auto flex gap-1"
          role="group"
          aria-label={t("customers.account.usage.windowLabel")}
        >
          {WINDOWS.map((option) => (
            <SegmentButton
              key={option}
              label={t("customers.account.usage.window", { months: option })}
              active={months === option}
              onClick={() => setMonths(option)}
            />
          ))}
        </div>
      </div>

      {payload.series.length === 0 ? (
        <Panel as="section">
          <h3>{t("customers.account.usage.title")}</h3>
          {/* NOT an `ArrivesWith`: nothing is missing from the product. No
              month has been calculated for this account yet, which is a state
              a customer can be told about plainly. */}
          <p className={`m-0 text-base ${MUTED}`}>{t("customers.account.usage.empty")}</p>
        </Panel>
      ) : (
        shown.map((series) => (
          <UsageChart key={series.service.id} series={series} months={months} t={t} />
        ))
      )}

      {payload.series.length > 0 && <ReadOutRow items={readOuts(shown, payload, chosen, t)} />}

      {/* ⚠ **`ACC-T06` DRAWS A SECOND THING ON THIS TAB AND IT WAS NEVER
          BUILT** — a `Month by month` table under the chart, one row per month
          with a column per service. The chart answers *what shape is this*;
          the table answers *what was it in May*, which is the question a
          customer disputing a bill actually asks, and there was no way to read
          a figure off this screen at all. */}
      {payload.series.length > 0 && (
        <UsageMonthsTable payload={payload} t={t} />
      )}
      </div>
    </div>
  );
}

/**
 * `ACC-T06`'s **Month by month** — the PO's 2026-10-15 table (decision log
 * *USAGE TAB "MONTH BY MONTH"*): **Month · Usage · Previous reading · Current
 * reading · Read on · Source · Check**, one row per month.
 *
 * Worked row the PO was shown: *Sep 2026 · 204,207 gal · 1,240,310 ·
 * 1,444,517 · 09/28/2026 · Manual (walk-by) · High*.
 *
 * ⚠ **EVERY CELL NOW HAS A SOURCE.** Until 2026-10-15 this docstring said
 * READ ON and SOURCE had none, because the monthly total stores no read date
 * or method, and the two cells stated *Not recorded* (`DEF-CUS-5146`). The
 * total does store the ids of the readings it summed (`source_read_ids`), and
 * `GET /accounts/{id}/usage` now serves each present month's `reading` block
 * built from them: the LATEST reading's date and source, the EARLIEST
 * reading's previous value, the LATEST reading's current value, and the
 * WORST stored status as `check` (`DEF-CUS-10162`). The server decides all of
 * that — this component only draws it.
 *
 * ⚠ **TWO OR MORE SERVICES → ONE ROW PER SERVICE PER MONTH, WITH A SERVICE
 * COLUMN.** Each service has its own meter, read date and readings, and kWh
 * beside gal in one row would invite adding them (hard rule 3). The service
 * names are `payload.series[].service.name` and are NEVER typed out here
 * (hard-won law 2: an eleventh service must appear without this file
 * changing). One service → no Service column.
 *
 * ⚠ **A MONTH WITH NO READING SAYS *No reading* AND NOTHING ELSE** (PO step 5).
 * The other cells are empty, not *Not recorded* — there is no reading to
 * describe, which is a different fact from a figure we failed to serve.
 * `BR-MET-106`: an unread month is never a zero.
 *
 * ⚠ **AN EMPTY READING CELL ON A PRESENT MONTH IS DELIBERATE TOO.** An
 * estimate has no current register value (`BR-MET-028`), and a month summed
 * over two meters serves no pair at all (two dials are not a before and an
 * after). Both are left blank; the Check chip already says *Estimated*.
 */
export function UsageMonthsTable(props: { payload: UsagePayload; t: Translator }) {
  const { payload, t } = props;
  const { timeZone, dateFormat } = useRegional({});
  const manyServices = payload.series.length > 1;

  // Every month any service has, newest first — the order the drawing lists
  // them in, and the order a person scans for "last month".
  const months = useMemo(() => {
    const seen = new Set<string>();
    for (const series of payload.series) {
      for (const point of series.points) {
        seen.add(point.month);
      }
    }
    return [...seen].sort().reverse();
  }, [payload.series]);

  const pointFor = (series: UsageSeries, month: string) =>
    series.points.find((point) => point.month === month) ?? null;

  return (
    <Panel
      as="section"
      tone="group"
      data-overview-group="usage-months"
      title={t("customers.account.usage.months.title")}
    >
      <div className="overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("customers.account.usage.col.month")}</th>
              {manyServices && <th>{t("customers.account.usage.col.service")}</th>}
              <th className="[&&]:text-right">{t("customers.account.usage.col.usage")}</th>
              <th className="[&&]:text-right">{t("customers.account.usage.col.previous")}</th>
              <th className="[&&]:text-right">{t("customers.account.usage.col.current")}</th>
              <th>{t("customers.account.usage.col.readOn")}</th>
              <th>{t("customers.account.usage.col.source")}</th>
              <th>{t("customers.account.usage.col.check")}</th>
            </tr>
          </thead>
          <tbody>
            {months.flatMap((month) =>
              payload.series.map((series) => (
                <UsageMonthRow
                  key={`${month}-${series.service.id}`}
                  month={month}
                  series={series}
                  point={pointFor(series, month)}
                  showService={manyServices}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                  t={t}
                />
              )),
            )}
          </tbody>
        </PlainTable>
      </div>
    </Panel>
  );
}

/** The chip tone per `check` — A12's semantic tones (PO 2026-10-15 step 3:
 *  High danger, Low warning). `flagged` is a reading to look at, so warning. */
const CHECK_TONE: Record<UsageCheck, StatusTone> = {
  high: "danger",
  low: "warning",
  flagged: "warning",
  zero: "neutral",
  estimated: "info",
  ok: "success",
};

/** One service's row for one month. */
function UsageMonthRow(props: {
  month: string;
  series: UsageSeries;
  point: UsagePoint | null;
  showService: boolean;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  t: Translator;
}) {
  const { point, t } = props;
  const absent = point === null || point.absent || point.quantity === null;
  const reading = absent ? null : (point.reading ?? null);

  return (
    <tr data-usage-month={props.month} data-usage-service={props.series.service.code}>
      <td>{formatMonthYear(`${props.month}-01`, "UTC")}</td>
      {props.showService && <td>{props.series.service.name}</td>}
      <td className="tabular-nums [&&]:text-right" data-cell="usage">
        {absent || point.quantity === null ? (
          <span className={MUTED}>{t("customers.account.usage.notRead")}</span>
        ) : (
          `${formatQuantity(point.quantity)}${point.unit === null ? "" : ` ${point.unit}`}`
        )}
      </td>
      <td className="tabular-nums [&&]:text-right" data-cell="previous">
        {reading?.previous_reading != null ? formatQuantity(reading.previous_reading) : null}
      </td>
      <td className="tabular-nums [&&]:text-right" data-cell="current">
        {reading?.current_reading != null ? formatQuantity(reading.current_reading) : null}
      </td>
      <td data-cell="read-on">
        {reading !== null && (
          <>
            <DateCell value={reading.read_on} timeZone={props.timeZone} dateFormat={props.dateFormat} />
            {reading.read_count > 1 && (
              <span className={`block text-sm ${MUTED}`}>
                {t("customers.account.usage.readingCount", { count: reading.read_count })}
              </span>
            )}
          </>
        )}
      </td>
      <td data-cell="source">{reading !== null && sourceLabel(reading, t)}</td>
      <td data-cell="check">
        {reading !== null && (
          <StatusPill
            tone={CHECK_TONE[reading.check]}
            // `Flagged` groups many validation rules; the hover names which
            // one, in the read log's own words (e.g. *Days since last read*).
            title={
              reading.check === "flagged"
                ? t(`metering.reads.status.${reading.status}`, { defaultValue: reading.status })
                : undefined
            }
          >
            {t(`customers.account.usage.check.${reading.check}`)}
          </StatusPill>
        )}
      </td>
    </tr>
  );
}

/** The read log's own two words — transport, then method — e.g.
 *  *Manual entry (Walk-by)*. An estimate has no method and says *Estimated*. */
export function sourceLabel(reading: UsageReading, t: Translator): string {
  const source = t(`metering.reads.source.${reading.source}`, { defaultValue: reading.source });
  if (reading.read_method === null) {
    return source;
  }
  const method = t(`metering.reads.readMethod.${reading.read_method}`, {
    defaultValue: reading.read_method,
  });
  return t("customers.account.usage.sourceWithMethod", { source, method });
}

/**
 * r10's segment chip, in utilities (B14 rule 21).
 *
 * ⚠ **THE STYLESHEET'S `.seg-opt` WAS TRIED FIRST AND IS WRONG FOR A BUTTON —
 * FOUND BY LOOKING AT THE SCREEN, BY NOTHING ELSE (hard-won law 6).**
 * `components/FormModal.css` styles the ACTIVE state as
 * `.seg-opt:has(input:checked)`, which needs r10's `<label><input
 * type="radio">` shape. A `<button className="seg-opt active">` matches
 * neither that selector nor any `.seg-opt.active` rule — **no such rule
 * exists** — so the chosen segment renders identical to the unchosen ones.
 * The first draft of this file did exactly that and the screenshot showed
 * three chips with nothing selected.
 *
 * ⚠ **AND IT IS NOT ONLY THIS FILE: `features/billing/BudgetBillsTab.tsx` and
 * `features/billing/PendingQueuePage.tsx` BOTH write `seg-opt active` on a
 * `<button>` today**, so their active filter is invisible too. That is another
 * lane's file and is REPORTED rather than changed here.
 */
// ⚠ EXPORTED 2026-09-13 — the Overview's `Usage trend` group carries the same
// `12 months / 24 months` control the blueprint draws on both surfaces. One
// component, one visual decision (B14 rule 36); a second copy is how the two
// window controls start disagreeing about their selected state, which is the
// bug this component's own docstring records.
export function SegmentButton(props: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`cursor-pointer border-0 px-3 py-[7px] text-sm ${
        props.active
          ? "bg-accent text-bg"
          : "bg-transparent text-text hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
      }`}
      aria-pressed={props.active}
      onClick={props.onClick}
    >
      {props.label}
    </button>
  );
}

/**
 * The top of the value axis — the next round step above the tallest bar.
 *
 * `ACC-T06` draws `0 · 2,000 · 4,000 · 6,000 · 8,000` over a peak of 6,820, so
 * the axis top is 8,000 and not 6,820: a scale whose top IS the tallest bar
 * puts that bar flush against the frame and gives the reader no headroom to
 * judge it by. The step is the familiar 1 / 2 / 5 × 10ⁿ ladder, which is what
 * makes 8,000 the number a person would have picked.
 *
 * ⚠ **PURE, AND EXPORTED SO IT CAN BE CHECKED WITHOUT A BROWSER.** Every other
 * property of this chart needs rendered output to see; this one is arithmetic
 * and a vitest case can hold it to the drawing's own figures.
 */
export function axisTop(peak: number): number {
  if (!Number.isFinite(peak) || peak <= 0) {
    return 0;
  }
  // Four intervals, because the drawing has five labels.
  const rough = peak / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? magnitude * 10;
  return step * 4;
}

/**
 * How many bars there are between one month label and the next.
 *
 * `ACC-T06`'s window is twelve months and it labels every bar; the control
 * beside it offers 24, where twelve labels' worth of text does not fit the
 * same row. One label per bar up to twelve, then every second, then every
 * third — so the axis never holds more than twelve labels and none is cut.
 */
export function labelStep(points: number): number {
  return Math.max(1, Math.ceil(points / 12));
}

/** The five labels the axis draws, TOP FIRST — the order they are read in. */
export function axisLabels(top: number): number[] {
  if (top <= 0) {
    return [0];
  }
  return [4, 3, 2, 1, 0].map((i) => (top / 4) * i);
}

/**
 * One service's chart. `ACC-T06`'s header is `Electric · Sep 2025 — Aug 2026`.
 *
 * ⚠ **THE BAR HEIGHTS ARE INLINE STYLES AND THEY HAVE TO BE.** A bar's height
 * is a number computed from the data; there is no class for `61.7%` and
 * inventing 100 utility classes to cover the range would be worse. r10 does the
 * same thing (`style="flex:1;height:44%"`). Everything that is NOT data —
 * the row, the gap, the axis rule — is a utility.
 */
function UsageChart(props: { series: UsageSeries; months: number; t: Translator }) {
  const { series, t } = props;
  const { i18n } = useTranslation();
  const present = series.points.filter((p) => !p.absent);
  const peak = present.reduce((max, p) => Math.max(max, Number(p.quantity ?? 0)), 0);
  const estimatedMonths = present.filter((p) => p.estimated).length;

  // ⚠ **THE AXIS IS ROUNDED UP TO A ROUND NUMBER, WHICH IS WHAT MAKES THE
  // LABELS READABLE.** `ACC-T06` draws `0 · 2,000 · 4,000 · 6,000 · 8,000` over
  // a peak of 6,820 — five gridlines on a scale whose top is the next round
  // step above the tallest bar, never the tallest bar itself. Rounding to a
  // 1/2/5 × 10ⁿ step is the one arithmetic decision here and it is the reason
  // the drawing's numbers are the ones a person would have chosen.
  const top = axisTop(peak);
  const first = series.points[0]?.month ?? null;
  const last = series.points[series.points.length - 1]?.month ?? null;

  return (
    <Panel as="section" tone="group" data-overview-group="usage-chart"
      title={
        // `ACC-T06` heads the chart `Electric · Sep 2025 — Aug 2026` — the
        // service and the WINDOW ITSELF, rather than a month count. The window
        // is the fact a person needs to place the bars; `24 months` makes them
        // work it out. `BR-SHL-034` — the ONE date path, one month formatter.
        first === null || last === null
          ? series.service.name
          : t("customers.account.usage.chartRange", {
              service: series.service.name,
              from: formatMonthYear(`${first}-01`, "UTC"),
              to: formatMonthYear(`${last}-01`, "UTC"),
            })
      }
    >

      {series.unit_absence !== null && (
        <p className={`m-0 mb-2 text-sm ${MUTED}`} data-tracks={series.unit_absence.tracks}>
          {t("customers.account.usage.mixedUnits")}
        </p>
      )}

      {/* ⚠ **THE UNIT IS ITS OWN LINE NOW AND NOT PART OF THE TITLE.**
          `ACC-T06` writes `kWh a month` against the value axis, where a reader
          looking at a bar's height is already looking. Hard rule 3 — a
          consumption figure is never drawn without its unit — is satisfied
          either way; this is where the drawing puts it. */}
      <p className={`m-0 mb-1 text-xs uppercase tracking-kicker ${MUTED}`} data-usage-axis-unit="">
        {t("customers.account.usage.axisUnit", {
          unit: series.unit ?? t("customers.account.usage.unitUnknown"),
        })}
      </p>

      <div className="flex gap-2">
        {/* The value axis. Five labels, top to bottom, on a scale whose top is
            `axisTop(peak)` — the drawing's own `8,000 · 6,000 · 4,000 · 2,000
            · 0` over a 6,820 peak. `justify-between` puts each label on its
            own gridline rather than at an arbitrary offset. */}
        <div
          className={`flex shrink-0 flex-col justify-between py-3 text-right text-xs tabular-nums ${MUTED}`}
          data-usage-axis=""
          aria-hidden="true"
        >
          {axisLabels(top).map((value) => (
            <span key={value}>{value.toLocaleString(i18n.language)}</span>
          ))}
        </div>
      <div className="min-w-0 flex-1">
      <div
        className={`flex items-end gap-1 border-b border-[var(--color-divider)] py-3 ${CHART_HEIGHT}`}
        role="img"
        // ⚠ **A THIRD CALL WITH THE WRONG ARGUMENT NAMES, AND THE ONLY ONE
        // NOBODY COULD SEE** (`DEF-CUS-4624`). All eleven catalogues read
        // `Monthly {{service}} usage in {{unit}}`; this passed `service` and
        // `months`, so the chart's accessible name has always ended
        // *"usage in {{unit}}"*. The Product Owner found the two VISIBLE
        // placeholders by looking at the screen — hard-won law 6 — and this
        // one is invisible to exactly that method, because it is only ever
        // read aloud. It was found by asserting that no `{{` reaches the
        // markup at all.
        aria-label={t("customers.account.usage.chartAria", {
          service: series.service.name,
          unit: series.unit ?? t("customers.account.usage.unitUnknown"),
        })}
      >
        {series.points.map((point) => (
          <UsageBar key={point.month} point={point} peak={top} unit={series.unit} t={t} />
        ))}
      </div>

      {/* ⚠ **THE MONTH LABELS ARE DRAWN AND WERE NOT BUILT.** `ACC-T06` writes
          `Sep 25 … Aug 26` under the bars; the chart carried a single range
          caption instead, so a reader could see a winter peak and not say which
          month it was. One label per bar, in the SAME flex track as the bars so
          each sits under its own column. `BR-SHL-034` — one month formatter,
          `Sep 2025`, rather than a fourth date shape invented for an axis. */}
      <div className="flex gap-1" data-usage-months="">
        {series.points.map((point, index) => (
          <span
            key={point.month}
            // ⚠ **NOT `truncate`, AND THE SCREENSHOT IS WHY (hard-won law 6).**
            // One slot is one bar wide, and `Oct 2024` does not fit one bar at
            // 24 months — with `truncate` the whole row read `Oct 2… Dec …
            // Feb 2…`, which is worse than no label at all. A labelled slot
            // starts at its own bar and runs right across the blank slot beside
            // it, which is what a person drawing this axis by hand would do.
            className={`min-w-0 flex-1 overflow-visible whitespace-nowrap text-left text-xs ${MUTED}`}
          >
            {/* ⚠ **EVERY LABEL AT TWELVE MONTHS, EVERY SECOND OR THIRD AT
                TWENTY-FOUR — MEASURED, NOT ASSUMED.** `ACC-T06` draws a
                twelve-month window and labels every bar. At 24 the same
                twelve labels do not fit the same width: the first build of
                this axis rendered `Oct 2…` `Nov …` `Dec …` across the whole
                row, which is a label a person cannot read at all. Thinning
                keeps every drawn label INTACT and drops some of them, which
                is the choice a person would make with a pencil; truncating
                keeps all of them and makes none of them legible. */}
            {index % labelStep(series.points.length) === 0
              ? formatMonthYear(`${point.month}-01`, "UTC")
              : ""}
          </span>
        ))}
      </div>
      </div>
      </div>

      {/* r10 draws no axis labels; the window is stated instead, which is what
          the reader actually needs to place the bars.
          ⚠ **THE STRING SAID `{{low}} to {{high}} {{unit}}` AND THIS CALL HAS
          ALWAYS PASSED `from` AND `to`** (`DEF-CUS-4621`) — not one name
          matched, so i18next substituted nothing and all eleven catalogues
          printed their own braces on screen. The CALL was right and the
          strings were the leftovers of a VALUE axis this screen never drew:
          a low-to-high range would only restate the two read-outs below, so
          the eleven strings moved to the window the comment already
          describes. */}
      {/* BR-MET-106, on screen: an unread month is stated, never drawn as 0.
          ⚠ **THE NAME MUST BE `months` AND NOTHING ELSE** (`DEF-CUS-4622`).
          All eleven catalogues interpolate `{{months}}`; this call passed
          `absent` and `total`, so i18next substituted NOTHING and the screen
          printed the placeholder at a clerk. The total is not passed because
          the panel heading above already states the window. */}
      {series.months_absent > 0 && (
        <p className={`m-0 mt-1 text-sm ${MUTED}`}>
          {t("customers.account.usage.absentMonths", { months: series.months_absent })}
        </p>
      )}

      {/* BR-MET-106, on screen: the estimate is counted AND recorded. */}
      {estimatedMonths > 0 && (
        <p className={`m-0 mt-1 text-sm ${MUTED}`}>
          {t("customers.account.usage.estimatedMonths", { months: estimatedMonths })}
        </p>
      )}
    </Panel>
  );
}

function UsageBar(props: { point: UsagePoint; peak: number; unit: string | null; t: Translator }) {
  const { point, t } = props;
  if (point.absent) {
    // No bar. An empty slot that says what it is, and nothing that could be
    // read as "this customer used nothing".
    return (
      <div
        className="h-full flex-1 self-stretch"
        data-month={point.month}
        data-absent="true"
        title={t("customers.account.usage.absentMonth", { month: point.month })}
      />
    );
  }
  const value = Number(point.quantity ?? 0);
  // A floor of 2% so a very small month is still visible as a mark rather than
  // disappearing into the axis and reading as an absence.
  const height = props.peak > 0 ? Math.max(2, (value / props.peak) * 100) : 2;
  return (
    <div
      // ⚠ **`justify-end` AND A COLUMN, BECAUSE THE FIGURE SITS ABOVE THE BAR.**
      // `ACC-T06` writes each month's number over its own column — the reason a
      // person can read a value off this chart at all without hovering, which
      // is the only way the figure was reachable before (a `title` is invisible
      // on a touch screen and to anyone not holding a mouse still).
      className="flex min-w-0 flex-1 flex-col justify-end self-stretch"
      data-month={point.month}
      data-absent="false"
      data-estimated={point.estimated ? "true" : "false"}
      title={t(
        point.estimated
          ? "customers.account.usage.barTitleEstimated"
          : "customers.account.usage.barTitle",
        { month: point.month, value: point.quantity_display ?? "", unit: point.unit ?? "" },
      )}
    >
      <span className="mb-0.5 truncate text-center text-xs tabular-nums">
        {point.quantity_display ?? ""}
      </span>
      <div
        style={{
          height: `${height}%`,
          background: "var(--color-accent)",
          // The estimated month is MARKED, not hidden and not equal-looking.
          opacity: point.estimated ? 0.55 : 1,
          outline: point.estimated ? "1px dashed var(--color-accent)" : undefined,
          outlineOffset: point.estimated ? "-1px" : undefined,
        }}
      />
    </div>
  );
}

/** One figure under the chart: what it is, and what it says. */
export interface ReadOut {
  id: string;
  label: string;
  value: string;
  /**
   * The line UNDER the figure — `ACC-T06` draws `Average · 5,140 kWh · a
   * month` and `Highest · 6,820 kWh · Dec 25` as three lines, not two.
   *
   * ⚠ **THIS REPLACES FOLDING THE MONTH INTO THE VALUE.** `Highest` used to
   * read *"6,820 kWh in 2026-12"* on one line, which is a sentence where the
   * drawing has a figure and its context. Optional, so a read-out with no
   * context (the percentage's operands, say, when they are absent) draws the
   * figure alone rather than an empty second line.
   */
  detail?: string;
}

/**
 * `ACC-T06`'s fourth read-out — **this month against last**, `+8.4%` over
 * `5,510 against 5,083`.
 *
 * ⚠ **IT IS NOT THE `yoy` FIGURE THE SERVER SENDS, AND THAT IS THE DRAWING'S
 * DECISION RATHER THAN A PREFERENCE.** `metrics.yoy` compares this YEAR with
 * the prior year; the drawing compares the newest month with the one before
 * it, and shows both operands so the arithmetic is checkable on the row. The
 * two answer different questions — *is this customer using more than they used
 * to* versus *did something change last month* — and it is the second one a
 * clerk has a customer on the phone about.
 *
 * ⚠ **IT IS DERIVED FROM TWO SERVED QUANTITIES AND NOTHING ELSE.** Both are
 * `monthly_usage_reads`' own stored figures at their own precision; the only
 * thing done here is the division, and it is DISPLAYED at 2 decimals
 * (CLAUDE.md hard rule 2's display law). Absent months, a zero prior month and
 * a series shorter than two months each answer `null` rather than a figure —
 * a percentage against nothing is the invented number this whole screen is
 * written against.
 */
export function monthOnMonth(series: UsageSeries | undefined): {
  percent: string;
  now: string;
  before: string;
} | null {
  const present = (series?.points ?? []).filter((point) => !point.absent);
  if (present.length < 2) {
    return null;
  }
  const now = present[present.length - 1];
  const before = present[present.length - 2];
  const nowValue = Number(now.quantity ?? Number.NaN);
  const beforeValue = Number(before.quantity ?? Number.NaN);
  if (!Number.isFinite(nowValue) || !Number.isFinite(beforeValue) || beforeValue === 0) {
    return null;
  }
  const change = ((nowValue - beforeValue) / beforeValue) * 100;
  const rounded = change.toFixed(2).replace(/\.?0+$/, "");
  return {
    percent: `${change > 0 ? "+" : ""}${rounded}%`,
    now: now.quantity_display ?? String(nowValue),
    before: before.quantity_display ?? String(beforeValue),
  };
}

/**
 * The five figures under the chart — **READ-OUTS, NOT KPIs** (PO 2026-09-07,
 * decision log *"A CHART'S READ-OUTS ARE NOT KPIs"*).
 *
 * ⚠ **THIS USED TO BE `components/KPIStrip` AND THAT WAS THE WRONG COMPONENT.**
 * PO verbatim, after being offered a font change instead: *"I dont think KPi
 * component is the right component for this … you need to think something
 * else"*, and on the fix: *"in your screenshot the summary numbers are
 * visually stronger than the data they are summarising"*. A KPI answers *how
 * is the business doing* and stands alone; these describe the bars directly
 * above and change the moment the service or the window changes. At
 * `--text-metric` (26px) against `--text-base` (13px) they were set at exactly
 * twice the surrounding text, which inverts the page.
 *
 * ⚠ **NO TOKEN MOVED AND NO OTHER SCREEN CHANGED — that is the whole point of
 * solving it here.** `KPIStrip` is right on the eight screens that use it,
 * where the numbers really are headline counts; it simply stopped being used
 * for a job it was never for. Do not "restore consistency" by putting it back.
 *
 * **`Highest` and `Lowest` fold their month INTO the value** — *"842 kWh in
 * 2026-07"* is one fact, where a big number with an orphaned date beneath it
 * is two.
 *
 * With `All` chosen there is no single service to average, so the four
 * per-service figures read the FIRST series shown and name it — printing an
 * unlabelled 628 over two services would be a number about nothing.
 *
 * ⚠ **THE FIFTH FIGURE IS `payload.water_avg` AND IT SITS OUTSIDE THE
 * PICKER.** It is a top-level served field, not part of any series, so it
 * cannot follow the chosen service and never could. Whether it should show at
 * all when water is not the chosen service is with the Product Owner and is
 * NOT settled — it stays until they rule.
 */
// ⚠ EXPORTED 2026-09-13 — see `ReadOutRow`. The Overview keeps the same five
// read-outs under its table that this tab draws under its chart.
export function readOuts(
  shown: UsageSeries[],
  payload: UsagePayload,
  chosen: string,
  t: Translator,
): readonly ReadOut[] {
  const series = shown[0];
  const metrics = series?.metrics;
  // ⚠ **A COMPUTED KEY, AND EVERY SUFFIX IT CAN TAKE MUST EXIST**
  // (`DEF-CUS-4623`). `absent_reason` is minted by the server, so no scanner
  // that reads call sites can see which keys this needs; when the sentences
  // were missing, i18next returned the key and the tile printed
  // `customers.a…`. G121 now fails a namespace with nothing under it.
  const value = (metric: UsageMetric | undefined) =>
    metric?.display === null || metric?.display === undefined
      ? t(`customers.account.usage.absent.${metric?.absent_reason ?? "unavailable"}`)
      : `${metric.display}${metric.unit === null ? "" : ` ${metric.unit}`}`;
  // ⚠ **THE MONTH IS THE READ-OUT'S SECOND LINE, NOT PART OF ITS VALUE.**
  // `ACC-T06` draws `Highest · 6,820 kWh · Dec 25`; folding it into the figure
  // produced *"6,820 kWh in 2026-12"*, which is a sentence where the drawing
  // has a number. `BR-SHL-034` — the one month formatter, so `2026-12` never
  // reaches a screen as itself.
  const inMonth = (metric: UsageMetric | undefined): string | undefined =>
    metric?.display === null || metric?.display === undefined || !metric?.month
      ? undefined
      : formatMonthYear(`${metric.month}-01`, "UTC");
  const change = monthOnMonth(series);

  return [
    {
      id: "avg",
      label: t("customers.account.usage.kpi.avg"),
      value: value(metrics?.avg_per_month),
      detail: t("customers.account.usage.kpi.perMonth"),
    },
    {
      id: "peak",
      label: t("customers.account.usage.kpi.peak"),
      value: value(metrics?.peak),
      detail: inMonth(metrics?.peak),
    },
    {
      id: "low",
      label: t("customers.account.usage.kpi.low"),
      value: value(metrics?.low),
      detail: inMonth(metrics?.low),
    },
    {
      // ⚠ **`ACC-T06` DRAWS *THIS MONTH VS LAST* WHERE THE SCREEN DREW
      // *AGAINST LAST YEAR*, AND THEY ARE DIFFERENT FACTS.** See
      // `monthOnMonth`: the drawing compares the two newest months and prints
      // both operands beneath the percentage. `metrics.yoy` is still served
      // and is not deleted anywhere; it is simply not what this read-out is.
      //
      // ⚠ **THE LABEL IS `Vs last month`, THREE WORDS, AND THE DRAWING'S IS
      // FOUR.** B14 rule 33 caps a LABEL at three words with no sentence, and
      // rule 38 says our own rules win on how a thing is constructed. The
      // difference is reported rather than taken silently in either direction.
      id: "monthOnMonth",
      label: t("customers.account.usage.kpi.monthOnMonth"),
      value:
        change === null
          ? t("customers.account.usage.absent.no_prior_reads")
          : change.percent,
      detail:
        change === null
          ? undefined
          : t("customers.account.usage.kpi.against", {
              now: change.now,
              before: change.before,
            }),
    },
    // ⚠ **THE FIFTH FIGURE IS ABOUT A DIFFERENT SERVICE, so it is on screen
    // only when that service is** (`DEF-CUS-4626`, PO 2026-09-07). r10 drew it
    // unconditionally because r10's fixture is an electric-and-water account;
    // on a real electric account it read *"Average water month · 15 kgal"*
    // beside four electric figures, and it could never follow the picker
    // because it is `payload.water_avg`, a top-level field outside every
    // series. **Nothing was deleted server-side** — the field is still served,
    // this is a display decision. Neither `monthly_usage_reads`'s docstring
    // nor BR-MET-106 states a reason it must always show; the only reason on
    // record is that r10 drew five tiles.
    ...(chosen === ALL || chosen === payload.water_avg.service_code
      ? [
          {
            id: "water",
            label: t("customers.account.usage.kpi.waterAvg"),
            value: value(payload.water_avg),
          },
        ]
      : []),
  ];
}

/**
 * The read-out row: body size, in the chart's own width, under the chart.
 *
 * The model is the two caption lines the chart already carries — the window
 * and the unread-month count. Those are the right weight for information that
 * describes the drawing above it, and this row is deliberately built to look
 * like them rather than like a dashboard.
 *
 * ⚠ **UTILITIES, AND THIS FILE IS ON `styles/route-b-migrated.txt`** (B14
 * rule 21). A utility written in a file NOT on that list is emitted by
 * nothing and renders as **no styling at all**, while `tsc` and every
 * `toContain` assertion pass because the class IS in the DOM. `tracking-`
 * uses the NAMED `kicker` step, never a bracket value — G34 refuses
 * `tracking-[0.1em]` with zero tolerance.
 */
// ⚠ EXPORTED 2026-09-13 — the Product Owner asked for the Overview's usage
// trend as a TABLE rather than bars and said the read-out row STAYS. It is
// composed there rather than copied: a second implementation is where the
// `All`-series rule and the unit rule would drift apart one panel at a time.
export function ReadOutRow(props: { items: readonly ReadOut[]; basis?: string }) {
  return (
    <div
      // `mb-6` matches the gap a `group` Panel leaves below itself (B14 rule
      // 39's 24px step), so the read-outs and the table below them are spaced
      // like every other pair of groups on this screen rather than touching.
      className="mt-3 mb-6 border-t border-[var(--color-divider)] pt-3"
      data-testid="usage-readouts"
    >
      {/* ⚠ **OPTIONAL SINCE 2026-09-13, AND THE USAGE TAB NO LONGER PASSES
          IT.** The row used to state its own window once — *"Across the last
          12 months"* — because the chart's title said only *24 months*. The
          title now names the window itself (`Electric · Sep 2025 — Aug 2026`,
          `ACC-T06`), so this line restates it, and B14 rule 32 gives a section
          ONE sentence. It stays a prop because the Overview's own trend group
          composes this row under a table with no such title. */}
      {props.basis !== undefined && <p className={`m-0 mb-2 text-sm ${MUTED}`}>{props.basis}</p>}
      <div className="flex flex-wrap gap-x-8 gap-y-3">
        {props.items.map((item) => (
          <div key={item.id} className="flex min-w-0 flex-col gap-1" data-readout={item.id}>
            <span className={`text-xs uppercase tracking-kicker ${MUTED}`}>{item.label}</span>
            <span className="text-base font-medium">{item.value}</span>
            {/* `ACC-T06`'s third line — the month a peak fell in, the two
                figures behind a percentage, or *a month* under an average. */}
            {item.detail !== undefined && (
              <span className={`text-sm ${MUTED}`}>{item.detail}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default AccountUsageTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-011@a1fbf3f (the S21 operational tabs; BR-MET-106 snapshot 2026-08-24)
// generated: 2026-08-24 by the CR-030 W3 task 3.8 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (AccountUsageTab.test.tsx)✔ · g37 (no row action here) · g38 (no stated absence: every absence on this screen is an ordinary empty state with no register row behind it, so no `ArrivesWith` is used and the untracked count does not move) · g13 (`client` is optional and the mount passes it) · ⚠ g40 will report this component as UNMOUNTED until AccountDetailPage.tsx's one-line change lands — see the note at the top; that is the gate working, not a false positive · g31 PASS (0 undeclared, baseline 0): the file IS registered in `src/styles/route-b-migrated.txt`, so `src/styles/routeBUtilities.test.ts` compiles every utility it names — 9/9 green
// exceptions: E3 `Compare to neighbors →` (B18 D3) is OMITTED, not disabled-with-a-reason: it is unspecified, and BR-SHL-010's precedent one tab over is that an undeclared capability is not rendered · E3 `All` draws every series side by side rather than one summed line (hard rule 3) and the four per-service KPI tiles then read the FIRST series and NAME it · E3 the payload types live here rather than in `api/endpoints.ts`: that file is another lane's today, and a wrapper there plus a type here would be two contracts (hard-won law 5) · E3 bar HEIGHTS are inline styles because they are data; every non-data style is a utility · E3 the segment chip is written in UTILITIES rather than reusing the stylesheet's `.seg-opt`: that class styles its ACTIVE state as `.seg-opt:has(input:checked)` and there is NO `.seg-opt.active` rule, so a `<button className="seg-opt active">` renders with no selected state at all — found by screenshotting the first draft, by nothing else (hard-won law 6). ⚠ `features/billing/BudgetBillsTab.tsx` and `features/billing/PendingQueuePage.tsx` have that exact bug today and are REPORTED, not changed here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
