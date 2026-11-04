// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-054 (the performance tab — did the field keep its promises,
//           and what it cost) · US-WRK-053 (the cost lines it totals).
//           Screen: Work-027 (`wireframes/Work-027.png`)
// Rules:    BR-WRK-053 (arithmetic over completed orders; NO link, button or
//           note into Finance) · BR-WRK-004 (cost captured, posted NOWHERE) ·
//           CLAUDE.md hard rule 2 (4 stored, 2 displayed) · B14 rule 2 (one
//           page header) · rule 11 (the consequence box) · rule 20 (one table
//           type) · rule 21 (Tailwind; on route-b-migrated.txt) · rule 31 (no
//           database id is a visible value) · rule 32 (one sentence per
//           section; no rule id in clerk copy) · rule 34 (*Recorded*, never
//           *In the books*) · rule 36 (the shared component kit)
// Tests:    src/features/work/PerformancePage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · WorkShell.tsx (the
//           Performance tab) · src/routing/screenIds.ts (WRK-16)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THIS SCREEN IS ASSERTED FOR A LINK IT DOES NOT HAVE.**
//
// `wireframes/Work-027.png` says the total at the foot of this table *"feeds
// the O&M / labour line in Finance → Cost & Margin."* **That arrow is not
// built, and it is not an omission.** `OQ-WRK-1491` closed on 2026-09-04 in
// the Product Owner's own words — *"(a) captured, posted nowhere"* — and
// `CR-028` D3 is the same Product Owner removing exactly that sentence for
// asset maintenance a fortnight earlier.
//
// **The reason is worth carrying, because a later lane will read the drawing
// and think the link was simply forgotten: payroll already posts the hour.
// Posting field labour beside it would count the same hour twice.**
//
// So there is no `<a>` to Finance, no route, no account code, no button and no
// note — `US-WRK-054` TC-3 greps the rendered page for *Finance*, *Cost &
// Margin*, *O&M* and `5300`, and `G111` fails the build if one appears in the
// source. B14 rule 34's pair of words applies to the figure at the foot: it is
// **Recorded**, never *In the books*, because it is not in the books.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { SegmentedControl } from "@/components/SegmentedControl";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_AT_RISK_ROUTE, useWorkTabs } from "./WorkShell";
import { fetchPerformance } from "./workEndpoints";
import type { PerformancePayload, PerformanceRow } from "./workEndpoints";
import { RaiseAcrossBoard } from "./performance/RaiseAcrossBoard";
import { ScheduleBoard } from "./performance/ScheduleBoard";
import { fetchSlaSettings } from "./performance/performanceEndpoints";

/**
 * CR-168-BRC10 P5.3–P5.5 — the three boards the blueprint NAMES and does not
 * draw live on this tab as views of it, in the address (`?view=`), the way
 * Crews carries its three lists (image 25's segmented control).
 *
 * ⚠ **A VIEW, NOT A NEW TAB OR ROUTE — OUR JUDGMENT, PUT TO THE PO AS A
 * PHOTOGRAPH.** P5 is one phase (*"Protect the promise"*) and the strip is
 * shared with the lanes building beside this one; a fourth word in it, or a
 * minted badge, is a decision about the whole module. Decision log *"CR-168
 * ROUND 5 · PERFORMANCE"*.
 */
//
// ⚠ **AT RISK LEFT ON 2026-10-05 (`CR-168-BRC10` §30).** PO answer (1),
// verbatim: *"(b) Make At risk its own tab next to Orders, because the design
// says "a dispatcher opens it first". Schedule and Raise across buildings stay
// inside Performance."* So two boards remain views here and the third is
// `AtRiskPage` at `WORK_AT_RISK_ROUTE`; `?view=at-risk` forwards there.
export const PERFORMANCE_VIEWS = ["results", "schedule", "across"] as const;
/** The 2.514.0 address of the At risk board — forwarded, never a view. */
export const LEGACY_AT_RISK_VIEW = "at-risk";
export type PerformanceView = (typeof PERFORMANCE_VIEWS)[number];
const VIEW_PARAM = "view";

export function performanceViewFrom(value: string | null): PerformanceView {
  return (PERFORMANCE_VIEWS as readonly string[]).includes(value ?? "")
    ? (value as PerformanceView)
    : "results";
}

/** r10's own badge for the performance screen — Work-027 ↔ WRK-16. */
export const WORK_PERFORMANCE_SCREEN = "WRK-16";

/** The tenant currency this tab totals in — the same constant, and the same
 *  reasoning, as the parts register one screen along. */
const PERFORMANCE_CURRENCY = "USD";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * The by-job-type table — `Work-027`'s seven columns in the drawing's order.
 *
 * Exported so a test can read the column set with no DOM and assert that no
 * column, and no cell, carries a route into Finance.
 */
export function performanceTableConfig(
  t: Translate,
  cells: {
    costPerJob: (row: PerformanceRow) => React.ReactNode;
    totalCost: (row: PerformanceRow) => React.ReactNode;
  },
): TableConfig<PerformanceRow> {
  return {
    screenId: WORK_PERFORMANCE_SCREEN,
    getRowId: (row) => row.job_type,
    // ⚠ **ABSENT, NOT EMPTY** (`DEF-WRK-4393`). `DataTable` renders the search
    // box on `config.searchFields !== undefined`, so `searchFields: []` drew a
    // LIVE search field over `GET /work/performance`, which reads `period` and
    // nothing else — a clerk could type into it all day and the list would
    // never move. `AwaitingApprovalPage` had already met this and wrote the
    // rule down in its own test ("ABSENT, not empty"); this screen shipped the
    // empty array anyway. G43 caught it on the day and said so as a missing
    // `searchPlaceholder`, which reads like a copy nit rather than a dead
    // control, and it sat among 37 red gates for a day.
    // The server fixes the order (volume, descending) — the drawing's own
    // default sort, and this only seeds `defaultRequestState`.
    defaultSort: { sort: "volume", dir: "desc" },
    columns: [
      {
        key: "job_type",
        label: t("work.performance.col.jobType"),
        identity: true,
        sortable: true,
        cell: (row) => <span>{row.job_type}</span>,
      },
      {
        key: "volume",
        label: t("work.performance.col.volume"),
        numeric: true,
        sortable: true,
        cell: (row) => <span className="tabular-nums">{row.volume}</span>,
      },
      {
        key: "sla_met_pct",
        label: t("work.performance.col.slaMet"),
        numeric: true,
        sortable: true,
        // A percentage the SERVER rounded to one place. Re-rounding it here
        // would give two answers to one question (hard rule 2's shape for a
        // figure that is not money).
        cell: (row) => <span className="tabular-nums">{row.sla_met_pct}%</span>,
      },
      {
        key: "first_time_fix_pct",
        label: t("work.performance.col.firstTimeFix"),
        numeric: true,
        sortable: true,
        cell: (row) => <span className="tabular-nums">{row.first_time_fix_pct}%</span>,
      },
      {
        key: "cost_per_job",
        label: t("work.performance.col.costPerJob"),
        numeric: true,
        cell: cells.costPerJob,
      },
      {
        key: "total_cost",
        label: t("work.performance.col.totalCost"),
        numeric: true,
        sortable: true,
        cell: cells.totalCost,
      },
    ],
  };
}

export interface PerformancePageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  period?: string;
}

/** `Work-027` — four tiles, the by-job-type table, and no way into Finance;
 *  and, as views of the same tab, the three boards P5 names. */
export function PerformancePage(props: PerformancePageProps) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = performanceViewFrom(searchParams.get(VIEW_PARAM));
  const forwardToAtRisk = searchParams.get(VIEW_PARAM) === LEGACY_AT_RISK_VIEW;

  function chooseView(next: string) {
    const params = new URLSearchParams(searchParams);
    if (next === "results") params.delete(VIEW_PARAM);
    else params.set(VIEW_PARAM, next);
    setSearchParams(params, { replace: true });
  }

  // B14 rule 32 — one sentence for the view in hand, carried as the TAB's
  // explainer so rule 18's 80% cap applies.
  const strip = useWorkTabs(
    view === "results" ? t("work.performance.description") : t(`work.performance.view.${view}.description`),
  );

  // A link or bookmark made under 2.514.0 lands on the At risk TAB (§30).
  if (forwardToAtRisk) return <Navigate replace to={tenantPath(WORK_AT_RISK_ROUTE)} />;

  return (
    <section aria-label={t("work.performance.title")} data-performance-view={view}>
      <PageHeader title={t("work.performance.title")} {...strip} />

      <SegmentedControl
        className="mb-4"
        name="performance-view"
        label={t("work.performance.views")}
        active={view}
        onSelect={chooseView}
        segments={PERFORMANCE_VIEWS.map((id) => ({ id, label: t(`work.performance.view.${id}.label`) }))}
      />

      {view === "results" && <PerformanceResults client={props.client} period={props.period} />}
      {view === "schedule" && <ScheduleBoard client={props.client} />}
      {view === "across" && <RaiseAcrossBoard client={props.client} />}
    </section>
  );
}

/** Image 65 — the tiles, the table PAGED ON THE SERVER (NFR-3, P5.6) and the
 *  total line.
 *
 *  ⚠ **P5.1 · THE HEADLINE IS ITS ROWS' SUM, AND SAYS SO.** The SLA tile reads
 *  *23 of 23 kept* — `tiles.sla_met` of `tiles.sla_measured`, which the server
 *  computes over the same annotated set as the rows (`DEF-WRK-9586`), so the
 *  tile and the column add up on every page. A job with no due date is
 *  measured against the default target (PO answer (1), 2026-10-04; seeded
 *  Normal, 72 h), and the tile names that figure from `GET /work/settings/sla`
 *  rather than printing a number this screen typed. */
function PerformanceResults(props: { client?: ApiClient; period?: string }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const translate: Translate = (key, params) => t(key, params);

  const config = useMemo(
    () =>
      performanceTableConfig(translate, {
        // Money crosses the boundary as a STRING and MoneyCell is the one place
        // it becomes `$186.00`. Parsing it into a number here is the float hard
        // rule 2 forbids.
        costPerJob: (row) => (
          <MoneyCell amount={row.cost_per_job} currency={PERFORMANCE_CURRENCY} />
        ),
        totalCost: (row) => <MoneyCell amount={row.total_cost} currency={PERFORMANCE_CURRENCY} />,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  // ⚠ `DEF-WRK-9656` — THE PAGE, THE SORT AND THE DIRECTION REACH THE SERVER.
  // Until round 5 this read `by_job_type` with no page: the pager drew
  // `1–N of N` over whatever one page held and moved nothing (law 2's mirror).
  const query = useQuery({
    queryKey: ["work", "performance", props.period ?? "", state.page, state.per, state.sort, state.dir],
    queryFn: () =>
      fetchPerformance(
        { period: props.period, page: state.page, per: state.per, sort: state.sort, dir: state.dir },
        client,
      ),
  });
  const data: PerformancePayload | undefined = query.data;
  const sla = useQuery({ queryKey: ["work", "settings", "sla"], queryFn: () => fetchSlaSettings(client) });
  const defaultHours = sla.data?.hours ?? null;

  const tiles: readonly KpiTile[] = useMemo(() => {
    const tilesData = data?.tiles;
    return [
      {
        id: "sla",
        label: t("work.performance.tile.slaMet"),
        value: tilesData ? `${tilesData.sla_met_pct}%` : "—",
        detail: tilesData ? (
          <span className="flex flex-col" data-sla-detail="">
            <span data-sla-kept="">
              {t("work.performance.tile.slaKept", { met: tilesData.sla_met, measured: tilesData.sla_measured })}
            </span>
            {defaultHours !== null && (
              <span data-sla-default="">{t("work.performance.tile.slaDefault", { hours: defaultHours })}</span>
            )}
          </span>
        ) : undefined,
      },
      {
        id: "ftf",
        label: t("work.performance.tile.firstTimeFix"),
        value: tilesData ? `${tilesData.first_time_fix_pct}%` : "—",
      },
      {
        id: "cost",
        label: t("work.performance.tile.costPerJob"),
        value: tilesData ? (
          <MoneyCell amount={tilesData.cost_per_job} currency={PERFORMANCE_CURRENCY} />
        ) : (
          "—"
        ),
        // ⚠ B14 rule 34 — ONE pair of words for *held here* and *in the books*,
        // in all eleven catalogues. This figure is **Recorded**. It is not *in
        // the books*, and saying so would be false as well as inconsistent.
        detail: t("work.performance.tile.recorded"),
      },
      {
        id: "volume",
        label: t("work.performance.tile.volume"),
        value: tilesData ? tilesData.volume : "—",
      },
    ];
  }, [data, defaultHours, t]);

  return (
    <div data-performance-results="">
      <KPIStrip kpis={tiles} loading={query.isPending} />

      <DataTable<PerformanceRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={data?.results ?? []}
        totalRows={data?.count ?? null}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: t("work.performance.loadFailed"), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          // ⚠ `US-WRK-054` TC-6 — *zeros drawn as zeros*. A utility with no
          // completed work should learn that it has none, not meet a blank.
          title: t("work.performance.empty.title"),
          helper: t("work.performance.empty.helper"),
          // B14 rule 17 wants the action that fills the list, and this
          // screen's is not this screen's: rows appear when the FIELD closes
          // jobs. So the button names where the work happens and is disabled
          // with that reason rather than opening nothing (`BR-SHL-025`) — the
          // same shape the approvals queue already uses.
          ctaLabel: t("work.performance.empty.cta"),
          ctaReason: t("work.performance.empty.ctaReason"),
          onCta: () => undefined,
        }}
      />

      {/* `Work-027`'s total line — *740 · $56,337*.
          ⚠ It sits BELOW the table rather than inside it because `DataTable`
          has no footer row and growing one for a single screen is how a shared
          component acquires a prop nobody else passes (hard-won law 2's first
          half, and B14 rule 20's one table type). */}
      {data ? (
        <p
          className="mt-3 flex items-center justify-end gap-4 text-body text-neutral-800"
          data-total-row=""
        >
          <span className="font-bold">{t("work.performance.total")}</span>
          <span className="tabular-nums">{data.total.volume}</span>
          <span className="tabular-nums font-bold">
            <MoneyCell amount={data.total.total_cost} currency={PERFORMANCE_CURRENCY} />
          </span>
        </p>
      ) : null}

      {/* ⚠ B14 rule 11's box, and what it does NOT say is the point. The
          wireframe's version ends *"feeds the O&M / labour line in Finance →
          Cost & Margin"*; that clause is stripped (rule 32 strips the CR-028
          citation with it — a rule id is never clerk copy). What is left is
          true: the figure is recorded here and it goes nowhere. */}
      <ConsequenceBox
        tone="check"
        title={t("work.performance.consequence.title")}
        body={t("work.performance.consequence.body")}
      />
    </div>
  );
}
