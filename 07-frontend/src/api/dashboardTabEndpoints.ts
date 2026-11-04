// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11`/`P4.12`/
//          `P4.13`. Screen `3·1`, drawn on p036–p038, read as IMAGES per B14
//          rule 42.
// Rules:   CLAUDE.md hard rule 2 (money is a decimal STRING on the wire —
//          stored to 4, DISPLAYED at 2, and never a JavaScript number) ·
//          BR-REP-024 (an absent figure is a null WITH its reason)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: features/reports/ReportsDashboardPage.tsx and its five panels
// ───────────────────────────────────────────────────────
//
// `GET /reports/dashboard` — the ONE read screen `3·1` makes.
//
// ⚠ **EVERY MONEY FIGURE IS A `string` AND THAT IS NOT A CONVENIENCE.**
// CLAUDE.md hard rule 2: money is stored to four decimals and never a float.
// `"48221.1400"` through `JSON.parse` would become a binary fraction the
// moment it were typed `number`, and a dashboard is the screen a utility
// quotes from. The strings travel to `MoneyCell`, which is the product's one
// formatting path (BR-SHL-023).
//
// ⚠ **A `null` FIGURE ALWAYS HAS A `reason_code` BESIDE IT.** BR-REP-024: a
// tile renders the owner's published figure or it REPORTS BY NAME that it
// cannot answer — never `0`, which is a number a clerk would act on.
import type { ApiClient, ApiResponse } from "./client";

/** ⚠ **`ApiResponse.data` IS `T | null` — IT IS `null` ON A 204 AND A 304**, so
 *  a read that simply returned it would type this screen's whole payload as
 *  nullable and every field access below would be a maybe. `tsc` caught it; no
 *  runtime check would have, because this route always has a body. The same
 *  helper `scheduleEndpoints.ts` uses, for the same reason. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** A machine reason code. The SENTENCE lives in the catalogues (TD-16/B8 — the
 *  server sends keys, the UI renders language), so a code this build does not
 *  know renders the generic one rather than the server's engineering prose. */
export type DashboardReason = string;

/** One accounting period, as the server computed it (BR-TEN-022 — never stored).
 *
 *  ⚠ **`id` IS THE PERIOD'S START DATE AND NOT A ROW ID** (B14 rule 31). There
 *  IS no row: it rides in the URL as `?f.period=2026-09-01`, which is what lets
 *  a link pasted into a board pack open on the same month. */
export interface DashboardPeriod {
  id: string;
  start: string;
  end: string;
  fy_label?: string | null;
  period_no?: number | null;
}

/** One of the four tiles (p037 ④). `kind` says whether `value` is money. */
export interface DashboardKpi {
  id: "billed" | "collected" | "outstanding" | "days_to_collect";
  kind: "money" | "count";
  value: string | number | null;
  reason_code: DashboardReason | null;
  comparison: {
    value: string | number | null;
    /** A percentage to SIX decimals (hard rule 2), DISPLAYED at two. `null`
     *  against a comparison of zero — a change against nothing is undefined,
     *  and `+∞%` on a board pack is worse than a blank. */
    change_pct: string | null;
    reason_code: DashboardReason | null;
  };
}

/** One bar of `Revenue, 12 months`. A window whose report did not answer has a
 *  NULL value and a reason, never a zero: a missing month drawn as a floor
 *  reads as *we billed nothing*, which is the one lie a revenue chart tells. */
export interface RevenueBar {
  period_id: string;
  start: string;
  end: string;
  value: string | null;
  reason_code: DashboardReason | null;
  current: boolean;
}

export interface AgeingBandRow {
  band: string;
  value: string | null;
  /** To ONE decimal and **not forced to 100** (p037 ⑥) — redistributing a
   *  rounding remainder would show a share no band actually has. */
  share_pct: string | null;
}

export interface ServiceMixRow {
  /** `null` is the drawing's *Not attributable* — the NAMED remainder, kept
   *  last. Dropping it would make the rows fail to add to the report's own
   *  total, silently. */
  service_code: string | null;
  value: string | null;
}

export interface TieOutRow {
  check: string;
  ours: string | null;
  theirs: string | null;
  difference: string | null;
  result: string;
}

/**
 * One panel — *a saved report rendered small* (p037 DATASETS).
 *
 * ⚠ **`report_params` IS ABSENT RATHER THAN IGNORED WHEN THE PANEL HAS NO
 * DOOR.** A screen cannot draw a link by forgetting to check a flag if the
 * destination is simply not in the payload — which is stronger than a client
 * remembering not to, and is hard-won law 2's mirror answered at the source.
 */
export interface DashboardPanel {
  id:
    | "revenue_12_months"
    | "where_the_money_sits"
    | "service_mix"
    | "biggest_movers"
    | "month_closed";
  report_key: string;
  opens: boolean;
  report_params: Record<string, string> | null;
  reason_code: DashboardReason | null;
  bars?: readonly RevenueBar[];
  bands?: readonly AgeingBandRow[];
  services?: readonly ServiceMixRow[];
  movers?: readonly unknown[];
  checks?: readonly TieOutRow[];
  blocked?: boolean | null;
}

/** A gap the whole screen carries, named once at the top rather than repeated
 *  on nine surfaces (B14 rule 32 — one stated absence per section). */
export interface DashboardGap {
  code: string;
  br_ref?: string;
  detail?: string;
}

export interface ReportsDashboardResponse {
  period: DashboardPeriod | null;
  periods: readonly DashboardPeriod[];
  comparison: string;
  comparisons: readonly { id: string }[];
  comparison_period: DashboardPeriod | null;
  basis?: string | null;
  currency: string | null;
  kpis: readonly DashboardKpi[];
  panels: readonly DashboardPanel[];
  unavailable: readonly DashboardGap[];
}

export const reportsDashboardPath = () => "/reports/dashboard";

/**
 * Read screen `3·1`.
 *
 * ⚠ **THE PERIOD AND THE COMPARISON TRAVEL AS `f.` PARAMETERS**, which is
 * BR-SHL-011's grammar and the same spelling the URL carries — so the address
 * bar, the request and the panel handoffs are one vocabulary rather than three
 * that have to be kept in step.
 */
export async function getReportsDashboard(
  query: { period?: string; compare?: string },
  client: ApiClient,
): Promise<ReportsDashboardResponse> {
  const search = new URLSearchParams();
  if (query.period !== undefined && query.period !== "") search.set("f.period", query.period);
  if (query.compare !== undefined && query.compare !== "") search.set("f.compare", query.compare);
  const suffix = search.toString();
  return requireData(
    await client.get<ReportsDashboardResponse>(
      suffix === "" ? reportsDashboardPath() : `${reportsDashboardPath()}?${suffix}`,
    ),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 · P4.12 · P4.13 (05-prototype/09 Reports Build Brief.pdf pp36-38, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(types only) B✔ C✔ D=n/a E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module '@/api/dashboardTabEndpoints'` before this file existed.
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
