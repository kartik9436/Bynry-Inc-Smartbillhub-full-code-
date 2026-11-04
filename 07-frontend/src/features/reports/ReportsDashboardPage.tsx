// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11` (the
//          screen), `P4.12` (period and comparison) and `P4.13` (the
//          panel→report handoff). Screen `3·1`, drawn on p036 and annotated on
//          p037–p038, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 44 (the drawing says WHAT is on screen and how it is
//          arranged; our UI standard says how it is BUILT and wins every time,
//          including the frame) · rule 43 (every panel is a COMPONENT from the
//          first commit — p38 names this screen by name) · rule 40 (the
//          page-head title is 32px — `PageHeader` owns it) · rule 33 (a LABEL
//          ≤ 3 words · a FACT ≤ 6 words · RATIONALE is ZERO words on screen) ·
//          rule 32 (one sentence per section; a stated absence, CLOSED) ·
//          rule 31 (no database id is the visible value of a field) · rule 21
//          (Tailwind utilities only) · rule 12 (a grid of two) ·
//          CLAUDE.md hard rule 2 (money DISPLAY 2) · hard-won law 2's mirror
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: App.tsx (`/reports/dashboard` stops being a placeholder) ·
//          ReportsTabs.tsx (the LAST held tab is drawn — the hold expires) ·
//          runHistory.dom.test.tsx · phaseHolds.dom.test.tsx ·
//          routing/reportsReservedSegments.test.tsx (each loses its
//          `dashboard` case) · routing/screenIds.ts
// ───────────────────────────────────────────────────────
//
// SCREEN `3·1` — THE REPORTS **DASHBOARD** TAB.
//
// ════════════════════════════════════════════════════════════════════════════
// THIS IS A NEW SCREEN AND IT DOES NOT TOUCH THE ONE WE ALREADY HAVE
// ════════════════════════════════════════════════════════════════════════════
// PO ruling quoted on p036, verbatim: *"no i dont want to update existing
// dashboard … you can create a tab - dont replace existing one"*. The shell's
// dashboard at `/{tenant}/dashboard` — rail item 1, the screen after every
// sign-in — is untouched by every task in this plan. `DashboardPage.tsx` is not
// imported here and `apps/reports/dashboard.py` is not read.
//
// **Two dashboards is the right number because they answer different questions
// to different people** (p036): one is a clerk's morning glance, *what needs me
// today*; this is an owner's monthly read, *how are we doing*.
//
// ════════════════════════════════════════════════════════════════════════════
// THE TAB IS DRAWN IN THIS COMMIT, AND THAT IS THE HOLD EXPIRING
// ════════════════════════════════════════════════════════════════════════════
// ⚠ Until this file existed, `/reports/dashboard` resolved to `ReportsTabRoute`'s
// *"Arrives in a later release."* placeholder and `ReportsTabs` refused to draw
// a fourth nav word over it. THREE tests asserted that hold — in
// `runHistory.dom.test.tsx`, `phaseHolds.dom.test.tsx` and
// `routing/reportsReservedSegments.test.tsx` — and all three were RUN AND SEEN
// TO GO RED before any of them was touched, which is the whole reason for
// having written them. Each names the segment in its own failure message.
//
// The tab is added to `LIVE_REPORT_TABS` and the expired cases are deleted in
// the SAME commit: a hold test that outlives its hold is the next reader's
// false alarm, and a red nobody can act on is how a true red acquires the
// protective colouring of a known one (CLAUDE.md hard-won law 7).
//
// ════════════════════════════════════════════════════════════════════════════
// NOTHING ON THIS SCREEN COMPUTES ANYTHING
// ════════════════════════════════════════════════════════════════════════════
// p038, verbatim: *"**A second set of numbers.** Every figure here comes from a
// definition in the catalogue. ⚠ **Nothing on this screen computes anything.**
// The moment a panel does its own arithmetic, the dashboard and the report
// start disagreeing, and the utility stops trusting both."*
//
// Every figure below is a string this page received. There is no `+` on a money
// value in this file, no ratio and no comparison of two amounts.
//
// ════════════════════════════════════════════════════════════════════════════
// THE PERIOD RIDES IN THE URL AND NOTHING IS REMEMBERED
// ════════════════════════════════════════════════════════════════════════════
// p036 ④: *"Nothing. **No write of any kind**, not even a remembered period."*
// p038 ⓸: *"the period rides in the URL, so the link you copy opens on the same
// month — which is what makes this screen usable in a board pack at all."*
//
// So there is no preference, no cookie and no `localStorage` on this screen.
// Reload and it returns to the current period, exactly as p037's WRITE SURFACES
// row says it must.
//
// ════════════════════════════════════════════════════════════════════════════
// WHAT THIS TAB MUST NEVER BECOME, STATED HERE BECAUSE p038 STATES IT
// ════════════════════════════════════════════════════════════════════════════
// **Configurable panels.** *"Let each utility choose which reports appear here"*
// is a reasonable thing to want and it is **not in this plan**. It needs a
// layout store, a picker, a size model and a per-role default, and it turns a
// screen anyone can read into a screen that looks different at every customer.
// If a utility asks, it is a change request with a named requester and a figure.
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { DashboardKpi, DashboardPanel as PanelPayload } from "@/api/dashboardTabEndpoints";
import { getReportsDashboard } from "@/api/dashboardTabEndpoints";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
// ⚠ **THERE IS NO `StateFrame` COMPONENT AND A FIRST DRAFT IMPORTED ONE.**
// `components/StateFrame.tsx` is a MODULE of state blocks — `LoadingSkeleton`,
// `FailedWithRetry`, `EmptyList`, `ZeroResults` — and importing a component of
// the file's own name resolved to `undefined`, which React reports only at
// render time as *"Element type is invalid"*. `tsc` would have caught it; the
// suite caught it first. Named blocks, from the kit, as every other screen does.
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";

import { AgeingBandsPanel } from "./dashboard/AgeingBandsPanel";
import { BiggestMoversPanel } from "./dashboard/BiggestMoversPanel";
import { DashboardPanel } from "./dashboard/DashboardPanel";
import { DashboardPeriodBar, periodLabel } from "./dashboard/DashboardPeriodBar";
import { MonthClosedPanel } from "./dashboard/MonthClosedPanel";
import { RevenueBarsPanel } from "./dashboard/RevenueBarsPanel";
import { ServiceMixPanel } from "./dashboard/ServiceMixPanel";
import { ReportsTabs } from "./ReportsTabs";
import { REPORTS_ROUTE, viewerRouteFor } from "./reportsShared";

export const DASHBOARD_TAB_SEGMENT = "dashboard";
export const DASHBOARD_TAB_ROUTE = `${REPORTS_ROUTE}/${DASHBOARD_TAB_SEGMENT}`;

export const reportsDashboardQueryKey = (search: string) =>
  ["reports", "dashboard-tab", search] as const;

/** The report each panel opens, by the name a person reads. The KEY comes from
 *  the payload, so a panel and its door can never name two different reports. */
const PANEL_TITLE: Record<PanelPayload["id"], string> = {
  revenue_12_months: "reports.dashboard.panel.revenue12",
  where_the_money_sits: "reports.dashboard.panel.whereMoneySits",
  service_mix: "reports.dashboard.panel.serviceMix",
  biggest_movers: "reports.dashboard.panel.biggestMovers",
  month_closed: "reports.dashboard.panel.monthClosed",
};

export interface ReportsDashboardPageProps {
  /** Injected in tests. Defaults to the app's own client — a screen that took
   *  a REQUIRED client would have to be threaded through the router, and a
   *  screen that took none could not be mounted against a server at all. */
  client?: ApiClient;
}

export function ReportsDashboardPage(props: ReportsDashboardPageProps = {}) {
  const { t, i18n } = useTranslation();
  const { tenant } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = props.client ?? api;

  const period = searchParams.get("f.period") ?? "";
  const compare = searchParams.get("f.compare") ?? "";

  const dashboard = useQuery({
    queryKey: reportsDashboardQueryKey(`${period}|${compare}`),
    queryFn: () => getReportsDashboard({ period, compare }, client),
    retry: false,
    // The report stays on screen while the reader changes a period, exactly as
    // the viewer does: blanking four tiles to a skeleton and back is what makes
    // a period picker feel broken.
    placeholderData: (previous) => previous,
  });

  const data = dashboard.data;

  /** ⚠ **THE ADDRESS IS BUILT HERE AND NOT IN A PANEL, BECAUSE ONLY THIS FILE
   *  KNOWS THE TENANT.** A component composing `/reports/ar_aging` produces a
   *  protocol-relative `//reports/…` when the tenant is undefined — a broken
   *  link that reads as a perfectly good string to `toContain`, which is the
   *  fixture fault CLAUDE.md records under hard-won law 2. */
  const doorFor = useMemo(
    () =>
      (panel: PanelPayload): string | null => {
        if (!panel.opens || panel.report_params === null || tenant === undefined) return null;
        const search = new URLSearchParams(panel.report_params);
        const suffix = search.toString();
        const route = `/${tenant}${viewerRouteFor(panel.report_key)}`;
        return suffix === "" ? route : `${route}?${suffix}`;
      },
    [tenant],
  );

  const tiles: readonly KpiTile[] = (data?.kpis ?? []).map((kpi: DashboardKpi) => {
    // ⚠ **A COMPARISON IS THE TILE'S `detail` LINE AND NEVER A SECOND TILE**
    // (p37 ④: *"Each carries its comparison underneath"*).
    const detail =
      kpi.comparison.change_pct !== null
        ? t("reports.dashboard.vsPrevious", {
            // DISPLAY 2 — hard rule 2. The server sends SIX decimals and the
            // rounding to two happens here, at display, and nowhere earlier.
            pct: Number(kpi.comparison.change_pct).toFixed(2),
          })
        : t("reports.dashboard.noComparison");
    const label = t(`reports.dashboard.kpi.${kpi.id}`);
    if (kpi.value === null) {
      // BR-REP-024 — *"A tile whose owner publishes no count reads **Not
      // counted yet** with its reason."* Never a 0, which is a figure a reader
      // would act on.
      return { id: kpi.id, label, value: t("reports.dashboard.notCountedYet"), detail: undefined };
    }
    if (kpi.kind === "money") {
      return {
        id: kpi.id,
        label,
        money: {
          amount: String(kpi.value),
          currency: data?.currency ?? "USD",
          basis: (data?.basis ?? "posting") as KpiTile extends { money: infer M }
            ? M extends { basis: infer B }
              ? B
              : never
            : never,
          locale: i18n.language,
        },
        detail,
      } as KpiTile;
    }
    return { id: kpi.id, label, value: String(kpi.value), detail };
  });

  const byId = useMemo(() => {
    const map = new Map<PanelPayload["id"], PanelPayload>();
    for (const panel of data?.panels ?? []) map.set(panel.id, panel);
    return map;
  }, [data]);

  function frame(id: PanelPayload["id"], body: React.ReactNode, absence?: string) {
    const panel = byId.get(id);
    if (panel === undefined) return null;
    return (
      <DashboardPanel
        title={t(PANEL_TITLE[id])}
        reportName={t(`reports.dashboard.report.${panel.report_key}`, {
          defaultValue: panel.report_key,
        })}
        to={doorFor(panel)}
        absence={absence}
      >
        {body}
      </DashboardPanel>
    );
  }

  const currency = data?.currency ?? null;
  const locale = i18n.language;
  const revenue = byId.get("revenue_12_months");
  const ageing = byId.get("where_the_money_sits");
  const mix = byId.get("service_mix");
  const movers = byId.get("biggest_movers");
  const closed = byId.get("month_closed");

  return (
    <div data-reports-tab="dashboard">
      <PageHeader
        title={t("reports.tab.dashboard.title")}
        // ⚠ **THE SUB-LINE NAMES THE TENANT AND THE PERIOD IN WORDS** (p37 ①,
        // verbatim: *"so a screenshot pasted into a board pack still says what
        // it is"*). It is the one thing on this screen that has to survive
        // being photographed.
        kicker={
          data?.period == null
            ? undefined
            : t("reports.dashboard.subLine", {
                period: periodLabel(data.period, locale),
              })
        }
        secondaryActions={
          data?.period == null ? undefined : (
            <DashboardPeriodBar
              periods={data.periods}
              selected={data.period}
              comparison={data.comparison}
              comparisons={data.comparisons}
              onPeriod={(id) => {
                const next = new URLSearchParams(searchParams);
                next.set("f.period", id);
                setSearchParams(next, { replace: false });
              }}
              onComparison={(id) => {
                const next = new URLSearchParams(searchParams);
                next.set("f.compare", id);
                setSearchParams(next, { replace: false });
              }}
            />
          )
        }
      />
      <ReportsTabs active="dashboard" />
      {dashboard.isLoading && <LoadingSkeleton variant="kpi" />}
      {dashboard.isError && (
        <FailedWithRetry
          title={t("reports.dashboard.failed")}
          reason={t("reports.dashboard.failedReason")}
          onRetry={() => void dashboard.refetch()}
        />
      )}
      {!dashboard.isLoading && !dashboard.isError && (
        data?.period == null ? (
          // B14 rule 32 — ONE stated absence for the whole screen rather than
          // the same sentence repeated on nine surfaces. Six words, no reason
          // (rule 33: RATIONALE is zero words on screen).
          <Panel>
            <p className="m-0 text-body text-text">{t("reports.dashboard.noPeriod")}</p>
          </Panel>
        ) : (
          <>
            <KPIStrip kpis={tiles} />
            {/* B14 rule 12 — a grid of two at 1440, ONE column below it.
                The drawing's own arrangement: the chart beside the ageing, the
                mix beside the movers, the tie-outs full width at the bottom.

                ⚠ **`2xl:` AND NOT `xl:`, AND THIS PROJECT'S `2xl` IS 1440px.**
                `styles/tailwind.css` redefines the whole scale — `xl` here is
                **1100px**, not Tailwind's 1280 — so `xl:grid-cols-2` put two
                columns at 1280, and photographed there the ageing rows WRAPPED:
                every money figure dropped onto its own line under its bar,
                costing half the panel's height. `ContributionBars` needs about
                490px (a 200px label, a 180px track, a 110px figure) and half of
                1280 is not that. One column at 1280 is the honest answer and
                the build width is exactly the breakpoint the project already
                ratified. Found by photographing at 1280 — no gate looks. */}
            <div className="mt-6 grid grid-cols-1 gap-6 2xl:grid-cols-2">
              {revenue !== undefined &&
                frame(
                  "revenue_12_months",
                  <RevenueBarsPanel bars={revenue.bars ?? []} currency={currency} locale={locale} />,
                )}
              {ageing !== undefined &&
                frame(
                  "where_the_money_sits",
                  <AgeingBandsPanel bands={ageing.bands ?? []} currency={currency} locale={locale} />,
                )}
              {mix !== undefined &&
                frame(
                  "service_mix",
                  <ServiceMixPanel services={mix.services ?? []} currency={currency} locale={locale} />,
                )}
              {movers !== undefined &&
                frame(
                  "biggest_movers",
                  <BiggestMoversPanel absence={t("reports.dashboard.moversAbsent")} />,
                )}
            </div>
            <div className="mt-6">
              {closed !== undefined &&
                frame(
                  "month_closed",
                  <MonthClosedPanel
                    checks={closed.checks ?? []}
                    currency={currency}
                    locale={locale}
                  />,
                )}
            </div>
          </>
        )
      )}
    </div>
  );
}

export default ReportsDashboardPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 · P4.12 · P4.13 (05-prototype/09 Reports Build Brief.pdf pp36-38, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the three hold cases in runHistory.dom.test.tsx, phaseHolds.dom.test.tsx and routing/reportsReservedSegments.test.tsx were each run and seen RED, naming the `dashboard` segment, before any of them was edited. reportsDashboard.dom.test.tsx reported `Cannot find module './ReportsDashboardPage'` before this file existed. G31: this file and its six panel components are listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) `Biggest movers` draws no rows and keeps its door — no definition publishes a period-over-period per-account usage comparison, and deriving one is the arithmetic p38 forbids. REPORTED · (2) `days to collect` is a tile with no figure and its reason, for the same cause · (3) the two period controls are the kit's `select` where p36 draws pill buttons with chevrons — B14 rule 44 · (4) the download control p36 draws beside them is NOT built: this screen composes five reports and there is no one file to produce. REPORTED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
