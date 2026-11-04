// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-019 (S7 / DSH-01 — the landing screen)   Screens: S7
// Change:   CR-012 (PO 2026-08-18 — "Please fix the dashbaord it should display
//           like this ; build all services, backend frontend")
// Rules:    BR-REP-024 (a dashboard tile never computes a figure) · BR-REP-025
//           (the TENANT's OWN services, all of them, seed order — PO 2026-08-19
//           d.1) · BR-REP-026 (bars are a share of the
//           LARGEST) · BR-REP-027 (the cycle status line, with NO set-up link —
//           PO 2026-08-19 d.5) · BR-REP-028 (regions
//           load, empty and FAIL independently) · BR-REP-029 (money and counts
//           arrive PRE-FORMATTED) · BR-REP-030 (five aging buckets) ·
//           BR-REP-031 (activity) · BR-REP-032 (to do) · BR-REP-033 (role-gated
//           actions; KPI cells do not navigate) · BR-REP-034 (the typed revenue
//           target) · BR-REP-001 (basis label) · BR-SHL-011 (URL grammar) ·
//           BR-SHL-012 (shared A18 states) · BR-SHL-020 (plain-language
//           failure) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S7 — THE FIRST SCREEN AFTER EVERY SINGLE SIGN-IN.
//
// It did not exist until 2026-08-16 (DEF-129: `/{tenant}/dashboard` fell through
// the router's catch-all and rendered the literal developer string
// `SMARTBillHub — W0 scaffold`). CR-012 is the second half of that story: the
// screen existed and was not the screen the PO had drawn.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO LAWS THIS FILE IS BUILT AROUND
// ══════════════════════════════════════════════════════════════════════════
// **1 · A TILE NEVER COMPUTES A FIGURE (BR-REP-024).** Every number here was
// produced by the module that owns it. This file performs no arithmetic on
// money of any kind — no sum, no percentage, no difference — and contains no
// `?? 0` over any served figure. DEF-104 is why: four surfaces disagreed about
// ONE customer's balance, the account screen saying **$0.00** while the ledger
// held an issued, unpaid **$108.88**.
//
// **2 · AND SINCE CR-012, IT DOES NOT FORMAT ONE EITHER (BR-REP-029).** The PO:
// *"Money and counts arrive pre-formatted as strings — no client-side currency
// math."* So there is no `Intl.NumberFormat` in this file, no `toFixed`, no
// division, and no `MoneyCell` on the served figures: the server rounds where
// the rounding rules live and this screen renders the string it was handed.
// (The tension with BR-SHL-023 — *one money formatting path* — is real, is
// stated in `apps/reports/dashboard_format.py`, and is reported rather than
// smoothed. The server's formatter reproduces `MoneyCell`'s en-US output byte
// for byte, so the two agree today.)
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS SCREEN IS SIX INDEPENDENT REGIONS (BR-REP-028)
// ══════════════════════════════════════════════════════════════════════════
// *"Per-section loading/empty/error states; one section failing must not blank
// the page."* Each region arrives with its own `state`, and `RegionFrame` below
// is the ONE place that decides what each state renders — so a region cannot
// quietly grow a private idea of "empty", and a failing owner costs one panel
// rather than the whole morning's figures.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT r10 DRAWS THAT THIS SCREEN STILL DOES NOT
// ══════════════════════════════════════════════════════════════════════════
//   · **No time-banded greeting.** *"Good morning"* needs three invented
//     boundary hours and a ruling on whose clock (**OQ-220**, still open). A
//     time-free greeting is the same sentence at 06:00 and at 23:00.
//   · **No "Assign" control on the To-do panel.** Nothing in this product
//     assigns work to a named person — no task table, no assignee (the
//     remaining half of **OQ-222**). A link that goes nowhere is hard-won law 2.
//   · **No amounts on the activity rows.** `audit_log` has no money column;
//     every row is the em-dash the requirement itself provides for.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getDashboardSummary, getMe } from "@/api/endpoints";
import type {
  DashboardActivityRow,
  DashboardAgingRow,
  DashboardCycleStatus,
  DashboardKpiTile,
  DashboardMixRow,
  DashboardPeriodFilter,
  DashboardPeriodOption,
  DashboardRegion,
  DashboardServiceMix,
  DashboardSummaryResponse,
  DashboardTodoRow,
  LedgerUnavailable,
} from "@/api/endpoints";
import { KPIStrip } from "@/components/KPIStrip";
import { WarningBox } from "@/components/WarningBox";
import { formatDate } from "@/components/DateCell";
import { getIntegrationsGrid } from "@/api/integrationsEndpoints";
import { useRegional } from "@/features/metering/meteringShared";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { Panel } from "@/components/Panel";
import type { StatusTone } from "@/components/StatusPill";
import { LoadingSkeleton } from "@/components/StateFrame";
import { DASHBOARD_STALE_MS, queryKeys } from "@/api/queryClient";
import { BILL_RUN_ROUTE } from "@/features/billing/billRunShared";
import { gapSentence } from "@/features/ledger/financeShared";
import { READS_UPLOAD_ROUTE } from "@/features/metering/readsShared";
import { ACCOUNTS_ROUTE } from "@/features/customers/customersShared";
import { FINANCE_ROUTE } from "@/features/ledger/financeShared";
import { revenueArViewPath } from "@/features/ledger/financeViewStrip";
import { BILLING_ROUTE } from "@/features/billing/billingShared";
import { PLANS_RATES_ROUTE } from "@/features/rating/ratingShared";
import { AUDIT_ROUTE } from "@/features/audit/AuditLogPage";
import { REPORTS_ROUTE } from "./reportsShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import "@/features/ledger/finance.css";
import { ButtonLink } from "@/components/Button";

/** The sidebar's own first path (SHELL_NAV `dashboard`, BR-SHL-001). */
export const DASHBOARD_ROUTE = "/dashboard";

/** The cache entry for ONE window.
 *
 *  ⚠ **THE PERIOD IS PART OF THE KEY AND HAS TO BE.** With a constant key, the
 *  five-minute `staleTime` ruled on 2026-08-19 would serve the previous window's
 *  figures under the new window's heading for up to five minutes — the exact
 *  "dashboard disagrees with Finance" failure the on-screen period statement
 *  exists to prevent, produced by the caching that was meant to be harmless. */
export const dashboardQueryKey = (period?: string | null) =>
  ["dashboard", "summary", period ?? "default"] as const;

/** BR-SHL-011's URL grammar spells a filter `f.<name>`. In the URL rather than
 *  in component state on purpose: the window a person is looking at is then
 *  SHAREABLE — they paste the link and the other person sees the same figures,
 *  which is the whole answer to the PO's *"there is now way user can see
 *  previous values and they will be confuse what is dashbaord is saying."* */
export const PERIOD_PARAM = "f.period";

/** The gap code the server names for each refusing tile. Spelled once, so the
 *  tile and the sentence it renders cannot drift apart. */
export const GAP_UNBILLED_READS = "unbilled_read_count_is_not_published_by_metering";
export const GAP_ACTIVE_CONNECTIONS = "active_connection_classes_are_not_published_by_customers";
export const GAP_FAILED_PAYMENTS = "failed_payment_count_is_not_published_by_payments";
export const GAP_REGION_FAILED = "region_read_failed";

// ══════════════════════════════════════════════════════════════════════════
// THE SERVER'S TOKENS, AND THE ONE RULE ABOUT THEM — DEF-2417 · B14 rule 31
// ══════════════════════════════════════════════════════════════════════════
//
// This screen renders five families of server-chosen token: a KPI tile id, a
// service code, an aging bucket, an audit action class and a to-do code. The
// split is TD-16/B8's and it is right: **the server sends a stable key and the
// client renders language.** The ids are the contract and none of them is ever
// renamed to suit a screen.
//
// ⚠ **WHAT WENT WRONG WAS THE OTHER HALF OF THAT SENTENCE (DEF-2417).** Every
// one of these labels was asked for as `t(<built key>, { defaultValue: <the
// token> })`, so a token with no copy NAMED ITSELF — and on the front page of
// the product, for every one of the five KPI tiles at once, because the five
// catalogue entries were spelled `dashboard.kpi.arOutstanding` while the
// server has always sent `ar-outstanding`. A billing clerk's first screen
// after every sign-in read **AR-OUTSTANDING** (upper-cased by the tile's own
// kicker), **UNBILLED-READS**, and three more.
//
// **The fallback was written deliberately and its reasoning was sound** — a
// tile should name itself rather than render blank, and that reasoning is
// recorded in `dashboard.test.tsx`. It is also exactly why nothing looked
// broken: the screen rendered, no key echoed as a raw dotted path, tsc and
// eslint passed and every assertion passed.
//
// **So the fallback stays and its VALUE changes.** `serverTokenLabel` below
// renders plain words for a token this app has no copy for — never the token.
//
// ⚠ **ONE TOKEN FALLBACK IS LEFT ON THIS SCREEN ON PURPOSE, AND IT IS NAMED
// HERE SO NOBODY HAS TO REDISCOVER IT.** `MixRow` still renders
// `row.service_code` when `MIX_LABEL_KEYS` has no entry, and that branch is
// UNREACHABLE today: the map covers all ten platform services BR-RAT-024
// declares, and `dashboard.test.tsx` asserts the exact ten and that every one
// has copy — so a served code with no label cannot arrive without that test
// going red first. It is left rather than given a fallback because the fix
// would be an eleventh-language string for a state the product cannot enter,
// and the assertion is the stronger guard. **If BR-RAT-024 ever gains a
// service, that test fails and this line is what it is telling you to fix.**
// The lists here are what the server can emit, mirrored so a test can ask "is
// there copy for every one of these"; `06-backend/tests/test_def2417_dashboard_labels.py`
// is what keeps the mirrors true, because it reads the backend constants and
// this app's catalogue in one place.

/** The five KPI tile ids, in the SERVER's order — `apps/reports/dashboard.KPI_ORDER`.
 *
 *  Mirrored for the label check ONLY. The screen still renders the tiles the
 *  server sent, in the order it sent them; nothing here re-orders or filters.
 *
 *  ⚠ **`mtd-revenue` IS THE BEST ARGUMENT IN THIS FILE FOR WHY AN ID IS NOT A
 *  LABEL.** r10 draws that tile as *"MTD revenue"* and its catalogue entry
 *  reads **"Revenue this period"** — deliberately, and it is not a divergence
 *  from the design so much as a ruling that arrived after it: CR-015 gave this
 *  screen a period picker, so the window can be *Last 30 days* or *Last
 *  period*, and a tile headed *MTD* would then be stating something FALSE
 *  beside dates that say otherwise. The ID keeps saying `mtd-revenue` because
 *  it is the contract and renaming it would break the server; the LABEL says
 *  what is true today. Do not "correct" the copy back to r10's without moving
 *  the picker with it. */
export const KPI_ORDER: readonly string[] = [
  "ar-outstanding",
  "unbilled-reads",
  "failed-payments",
  "mtd-revenue",
  "active-connections",
];

/** The audit action CLASSES the activity feed can show —
 *  `apps/reports/dashboard_regions.OPERATOR_ACTIONS`, whose keys are prefixes
 *  (`payment.`) and whose class is the part before the first dot. The PO named
 *  six kinds of work; nine prefixes carry them. */
export const ACTIVITY_CLASSES: readonly string[] = [
  "bill_run",
  "invoice",
  "correction",
  "payment",
  "refund",
  "collection",
  "notice",
  "read_batch",
  "account",
];

/** The onboarding steps a new tenant's To-do panel can show —
 *  `apps.tenancy.selectors.CHECKLIST_ITEMS`, S62's checklist (BR-TEN-015). */
export const TODO_ONBOARDING_CODES: readonly string[] = [
  "company_profile",
  "services_uom",
  "rates_taxes",
  "fiscal_billing",
  "numbering_documents",
  "invite_team",
];

/**
 * The catalogue sentence for one server-chosen token, or plain words when this
 * app has no copy for it — **never the token itself** (B14 rule 31, DEF-2417).
 *
 * The `defaultValue: ""` probe is how "no copy" is detected without i18next
 * printing the built key at a clerk; it is `gapSentence`'s shape in
 * `features/ledger/financeShared.tsx`, which was given it the same day and for
 * the same rule.
 *
 * **The token is not lost, it stops being READ ALOUD.** It is still the React
 * key, still on the wire, still in the response fixtures and still in the
 * network tab — everything support and engineering had, they keep.
 */
export function serverTokenLabel(
  key: string,
  t: Translator,
  unnamedKey: string,
  params?: Record<string, unknown>,
): string {
  const copy = t(key, { ...(params ?? {}), defaultValue: "" });
  return copy === "" ? t(unnamedKey) : copy;
}

/** BR-RAT-024's ELEVEN platform services — mirrored here ONLY to label them.
 *
 *  ⚠ **This map used to hold five** (electric, water, sewer, trash, gas), which
 *  was fine while the SERVER drew exactly those five. The PO's ruling of
 *  2026-08-19 made the row set the tenant's own configured services, so a
 *  broadband utility's row would have fallen through to the raw code
 *  `broadband` on screen — the label map has to cover everything the server can
 *  now send. The order itself is still the server's; this object never sorts. */
export const MIX_LABEL_KEYS: Record<string, string> = {
  electric: "dashboard.service.electric",
  water: "dashboard.service.water",
  gas: "dashboard.service.gas",
  sewer: "dashboard.service.sewer",
  trash: "dashboard.service.trash",
  storm_water: "dashboard.service.storm_water",
  solar: "dashboard.service.solar",
  broadband: "dashboard.service.broadband",
  thermal_heat: "dashboard.service.thermal_heat",
  battery: "dashboard.service.battery",
  // CR-063 — the ELEVENTH service (2026-09-02). ⚠ **THIS ENTRY IS `DEF-3091`
  // AND IT IS THE SAME FAILURE THE PARAGRAPH ABOVE DESCRIBES, ONE SERVICE ON.**
  // The row set is the tenant's own configured services, so a fire utility's
  // service-mix row would have fallen through to the raw code `fire` printed on
  // the landing page — exactly what happened to broadband before 2026-08-19.
  // CR-063's own step 0 named TWO hand-written service lists in the front end;
  // this was a third and `newConnectShared.TEN_SERVICES` a fourth.
  // ⚠ **THE FOURTH IS GONE (PO ruling 2026-09-21, *"here filter only active
  // Utility services for that Tenant"*)** — New Connect step 4 reads the
  // tenant's enabled set through `queryKeys.tenantServices` and the constant is
  // DELETED. This map and the two CR-063 named are still written by hand.
  fire: "dashboard.service.fire",
};

/** BR-REP-030's five bands. Same rule: labels only, never a re-order. */
export const AGING_LABEL_KEYS: Record<string, string> = {
  current: "dashboard.aging.bucket.current",
  "1-30": "dashboard.aging.bucket.b1_30",
  "31-60": "dashboard.aging.bucket.b31_60",
  "61-90": "dashboard.aging.bucket.b61_90",
  "90+": "dashboard.aging.bucket.b90plus",
};

/** BR-REP-031's action classes → the sentence a person reads. The server sends
 *  a stable code and the UI renders language (TD-16/B8).
 *
 *  ⚠ **THE FALLBACK USED TO BE THE ACTION STRING ITSELF (DEF-2417)**, so a
 *  class with no copy printed `read_batch.imported` in bold on the landing
 *  page. It now reads *Other activity*: an action class this app has no copy
 *  for still says SOMETHING rather than going blank, which was the original
 *  and correct intention — it just may not say it in machine. */
export function activityLabel(action: string, t: Translator): string {
  const klass = action.split(".")[0] ?? action;
  return serverTokenLabel(`dashboard.activity.class.${klass}`, t, "dashboard.activity.unnamed");
}

/** The server's stable to-do `target` tokens → this app's own route constants.
 *
 *  ⚠ **DEF-305 — TWO OF THESE FOUR IMPORTS WERE DEAD** — `ACCOUNTS_ROUTE` and `PLANS_RATES_ROUTE`
 *  were imported and never read, and eslint had been failing on this file for
 *  it. The reason they LOOKED fine is worse than the lint: `todoHref` built its
 *  URL by string surgery (`/${target}`) and the tokens happen to spell the same
 *  paths, so every link worked by coincidence and a route rename would have
 *  broken four dashboard links silently. Mapping them makes the coincidence a
 *  declaration: rename a route and this file moves with it. */
/** ⚠ **`DEF-REP-6345` — THE BARE `FINANCE_ROUTE` IS THE TRIAL BALANCE**, since
 *  `CR-060` T10 moved `/finance` onto it. Two doors here still pointed at it and
 *  landed a reader one screen away from what they had just looked at:
 *
 *  * the AR-aging panel's link — the aging detail (`AgingPanel`) is on
 *    Revenue & AR (S36), so that is where it goes;
 *  * the finance to-do — its one code is `finance_close`, which is done on
 *    Close & export (S42/S43). LATENT today: `open_finance_close()` publishes
 *    nothing yet, so no row carries `target: "finance"`.
 *
 *  Both are asserted by DESTINATION in `dashboardFinanceDoors.dom.test.tsx`:
 *  the href is read off the rendered anchor and handed to `APP_ROUTES`. */
/** ⚠ **`P2.23` — IT NOW NAMES THE VIEW, BECAUSE `/finance/revenue` STOPPED
 *  BEING ONE SCREEN ON 2026-09-24.** `P2.18` split Revenue & AR into five views
 *  and made **Services** the landing one, so this link — which promises the
 *  reader the aging detail they are looking at — would have opened the
 *  revenue-by-service table instead. **No 404 and no red test:** the wrong view
 *  is a real working screen, which is `DEF-PAY-6329`'s exact shape one door
 *  over and the reason `P2.23` exists as a task at all.
 *
 *  `revenueArViewPath` composes `financeTabPath`, so this carries no literal
 *  and moves if the tab moves. */
export const AGING_DOOR_ROUTE = revenueArViewPath("aging");
export const FINANCE_CLOSE_ROUTE = `${FINANCE_ROUTE}/export`;

/** The AR-aging panel's link, as its own component so a test can drive the
 *  anchor the page renders and read its href (`DEF-REP-6345`). */
export function AgingDoor(props: { t: Translator }) {
  const tenantPath = useTenantPath();
  return (
    <Link
      className="text-sm text-accent-700 no-underline whitespace-nowrap hover:underline focus-visible:underline"
      to={tenantPath(AGING_DOOR_ROUTE)}
    >
      {props.t("dashboard.aging.openFinance")}
    </Link>
  );
}

const TODO_TARGET_ROUTES: Record<string, string> = {
  billing: BILLING_ROUTE,
  accounts: ACCOUNTS_ROUTE,
  "plans-rates": PLANS_RATES_ROUTE,
  finance: FINANCE_CLOSE_ROUTE,
};

/** Where a to-do row's `target` token lands. The SERVER sends a stable token
 *  and the CLIENT owns the URL — the same split every other screen uses, so a
 *  route rename is a frontend change and never a migration. */
export function todoHref(target: string | null): string {
  if (target === null || target === "") {
    return BILLING_ROUTE;
  }
  if (target.startsWith("/")) {
    return target;
  }
  return TODO_TARGET_ROUTES[target] ?? `/${target}`;
}

/**
 * The catalogue sentence for one gap code, or an honest fallback naming it.
 *
 * `gapSentence` (financeShared) is the ONE renderer of a refusal in this app and
 * is reused rather than reimplemented, so a gap reads identically on S7, S36,
 * S59 and S60.
 */
export function reasonFor(
  gaps: readonly LedgerUnavailable[] | undefined,
  code: string,
  t: Translator,
): string {
  const found = (gaps ?? []).find((gap) => gap.code === code);
  return found === undefined
    ? t("finance.gap.unknown", { code, brRef: "BR-REP-024" })
    : gapSentence(found, t);
}

// ══════════════════════════════════════════════════════════════════════════
// THE REGION FRAME — BR-REP-028, in one place
// ══════════════════════════════════════════════════════════════════════════
/**
 * One panel: its header, its link, and whichever of the three states it is in.
 *
 * **THE ERROR BRANCH IS THE POINT.** A region that failed renders a sentence
 * keyed on the server's stable code and NOTHING ELSE — no zero, no empty table,
 * no skeleton that never resolves — and the five regions beside it are
 * untouched. This is written once so no panel can invent a fourth state or a
 * quieter version of failure.
 */
export function RegionFrame<TData>(props: {
  region: DashboardRegion<TData> | undefined;
  title: string;
  t: Translator;
  /** Rendered to the right of the title — r10's accent "see" link. */
  link?: ReactNode;
  /** What an EMPTY region says. Keeps its header and its link, per the PO's
   *  *"Empty states keep header and link"*. */
  emptyText: string;
  children: (data: TData) => ReactNode;
}) {
  const { region, t } = props;
  return (
    <Panel className="min-w-0" as="section" data-dash="region">
      <div className="fin-panel-head">
        <h3>{props.title}</h3>
        {props.link}
      </div>
      {region === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : region.state === "error" ? (
        <p className="fin-absent-reason" role="note">
          {region.error === null
            ? t("finance.gap.unknown", { code: GAP_REGION_FAILED, brRef: "BR-REP-028" })
            : gapSentence(region.error, t)}
        </p>
      ) : region.data === null || region.state === "empty" ? (
        <p className="fin-absent-reason" role="note">
          {props.emptyText}
        </p>
      ) : (
        props.children(region.data)
      )}
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE PERIOD BAR — CR-015
// ══════════════════════════════════════════════════════════════════════════
/**
 * One calendar day in the reader's own language.
 *
 * Formatted HERE and not on the server, and that is NOT an exception to
 * BR-REP-029: that rule is about MONEY AND COUNTS, whose rounding must not
 * happen twice. A date is language — this product ships eleven catalogues, and
 * a server-rendered "19 Aug 2026" would be English on every one of them.
 */
export function periodDay(iso: string, locale?: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** The window, spelled out: `12 Aug 2026 – 19 Aug 2026`. */
export function periodRange(option: DashboardPeriodOption, locale?: string): string {
  return `${periodDay(option.start, locale)} – ${periodDay(option.end, locale)}`;
}

/**
 * What one option is CALLED in the picker.
 *
 * The cycle option names its cycle, and that is most of why the default is a
 * cycle at all: *"Last cycle · 08-B"* is a window an operator recognises where
 * *"12 Aug – 19 Aug"* alone is an arbitrary week. The label comes from the
 * catalogue keyed on the server's stable id (TD-16/B8); an id this app has no
 * copy for still NAMES itself rather than rendering blank.
 */
export function periodOptionLabel(option: DashboardPeriodOption, t: Translator): string {
  const base = t(`dashboard.period.option.${option.id}`, { defaultValue: option.id });
  if (option.cycle_code !== null && option.cycle_code !== "") {
    // ⚠ A WHOLE SENTENCE PER LANGUAGE, NOT A `{{label}} · {{code}}` TEMPLATE.
    // The template version was written first and is worth naming: it carries no
    // translatable word, so all eleven catalogues held the identical string and
    // G15 counted a new value "left in English" in every one of them. Worse, it
    // fixes the separator and the ORDER for languages that would not choose
    // either. A named cycle gets a real sentence in each catalogue; anything
    // without one falls back to the plain label.
    return t(`dashboard.period.optionNamed.${option.id}`, {
      code: option.cycle_code,
      defaultValue: `${base} · ${option.cycle_code}`,
    });
  }
  return base;
}

/**
 * How old the figures on screen are, in whole minutes — or `null` while fresh.
 *
 * ⚠ **THIS IS THE PO'S OWN CONDITION, APPLIED TO THE CACHE THAT ACTUALLY
 * EXISTS**: *"where cached, state cache age rather than disagree with
 * Finance."* The SERVER-side cache authorised on 2026-08-19 is NOT built (see
 * `DASHBOARD_STALE_MS` for why, and the CR-015 closure record). But the
 * five-minute client `staleTime` ruled the same day IS built and is real
 * caching: a clerk returning to this screen can be shown figures read five
 * minutes ago while Finance recomputes on arrival, and until now nothing said
 * so. `dataUpdatedAt` is react-query's own record of when this entry was
 * fetched, so the age is measured rather than asserted.
 *
 * Under a minute it returns null and the bar says the figures are current: "0
 * minutes ago" reads as a fault where "just now" reads as the truth.
 */
export function figureAgeMinutes(updatedAt: number, now: number): number | null {
  const minutes = Math.floor((now - updatedAt) / 60000);
  return minutes >= 1 ? minutes : null;
}

/**
 * ⚠ **THE PERIOD IS STATED ON SCREEN, NOT BURIED IN THE CONTROL** — CR-015's
 * own condition, and it is the PO's consistency rule surviving contact with a
 * user-chosen window.
 *
 * *"A KPI must agree with its owning module for the same as-of moment."* Once a
 * user may pick an arbitrary window the dashboard can differ from Finance
 * **because they are looking at different periods** — both correct, and it
 * reads as a bug. So the dates are spelled out in full beside the picker, in
 * the reader's own locale, at the top of the page: not `Last cycle` in a
 * dropdown a person has to open, but **`12 Aug 2026 – 19 Aug 2026`** where the
 * figures can be compared against it.
 *
 * The as-of moment is stated with it, because that is the OTHER half of the
 * same rule and it is the half DEF-299 broke: this screen said `as of 31 Aug`
 * on the 19th, so the two labels could not be compared at all.
 */
export function PeriodBar(props: {
  filter: DashboardPeriodFilter | undefined;
  asOf: string | null;
  ageMinutes: number | null;
  onSelect: (id: string) => void;
  t: Translator;
  locale?: string;
}) {
  const { filter, t } = props;
  if (filter === undefined || filter.options.length === 0) {
    return null;
  }
  const selectedId = filter.selected ?? filter.default ?? filter.options[0].id;
  const selected = filter.options.find((option) => option.id === selectedId) ?? filter.options[0];
  return (
    // ⚠ **ONE LINE, CENTRED — `DEF-2369` (PO 2026-09-02).** *"Period and Text
    // infornt of it not aligned … all should be in 1 line and aligned centrally
    // - horizontal"*.
    //
    // The cause was not a missing alignment rule; it was that `.fin-params-field`
    // is `flex-direction: column` — a label STACKED OVER its control. That is
    // right where the class comes from (the S59/S60 report viewers put several
    // fields side by side, and stacking keeps each label with its own control),
    // and wrong here, where there is ONE field and a sentence beside it. A
    // two-line field has no line for a one-line sentence to sit on, so no value
    // of `align-items` could ever have fixed it.
    //
    // Laid out here rather than by changing `.fin-params-field`, because that
    // class is shared with two screens where the stack is correct. B14 rule 21
    // is satisfied: `DashboardPage.tsx` is on `route-b-migrated.txt`, checked
    // before these utilities were written.
    <div className="fin-params flex-wrap items-center" data-dash="period-bar">
      <label className="m-0 inline-flex flex-row items-center gap-2 whitespace-nowrap text-base">
        {t("dashboard.period.label")}
        {/* B14 rule 8 — the shared `.input` select, so the chevron is the one
            chevron every dropdown in the product uses. At most THREE options,
            so it is NOT type-to-filter (rule 8's threshold is five). ⚠ This
            read "Four options" until 2026-09-26 (`CR-142-BRC07` `P0.15`) — the
            fourth was the completed-cycle window `CR-029` `D8①` withdrew. The
            conclusion never changed; the count did, and a count nobody rechecks
            is how the same line comes to say five. */}
        <select
          className="input"
          value={selectedId}
          onChange={(event) => props.onSelect(event.target.value)}
          aria-label={t("dashboard.period.label")}
        >
          {filter.options.map((option) => (
            <option key={option.id} value={option.id}>
              {periodOptionLabel(option, t)}
            </option>
          ))}
        </select>
      </label>
      <p className="m-0 flex min-w-0 flex-wrap items-center gap-3">
        <strong className="text-body font-semibold text-text whitespace-nowrap" data-dash="period-range">
          {t("dashboard.period.showing", { range: periodRange(selected, props.locale) })}
        </strong>
        {props.asOf !== null && (
          <span className="text-sm whitespace-nowrap text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]" data-dash="period-asof">
            {t("dashboard.period.asOf", { day: periodDay(props.asOf, props.locale) })}
          </span>
        )}
        {props.ageMinutes !== null && (
          <span className="text-sm whitespace-nowrap text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
            {t("dashboard.period.age", { count: props.ageMinutes })}
          </span>
        )}
      </p>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 1 · THE CYCLE STATUS LINE — BR-REP-027
// ══════════════════════════════════════════════════════════════════════════
/**
 * `{weekday} · {month day} · Cycle {code} closes in {n} days`, in four states.
 *
 * The weekday and the date are formatted HERE and not on the server, and that
 * is not an exception to BR-REP-029: that rule is about MONEY AND COUNTS, whose
 * rounding must not happen twice. A weekday name is language, this product ships
 * eleven catalogues, and a server-rendered "Wednesday" would be English on every
 * one of them.
 */
export function CycleStatusLine(props: {
  region: DashboardRegion<DashboardCycleStatus> | undefined;
  asOf: string | null;
  t: Translator;
  locale?: string;
}) {
  const { region, t } = props;
  const when =
    props.asOf === null
      ? null
      : new Date(`${props.asOf}T00:00:00`).toLocaleDateString(props.locale, {
          weekday: "long",
          month: "short",
          day: "numeric",
        });

  if (region === undefined || region.state === "error" || region.data === null) {
    // The date alone. A countdown that could not be read is not replaced by a
    // guess at one — the head still says what day it is.
    return when === null ? null : <span className="fin-rollup-item">{when}</span>;
  }

  const data = region.data;
  const code = data.cycle_code ?? "";
  return (
    <span className="fin-rollup">
      {when !== null && <span className="fin-rollup-item">{when}</span>}
      {data.state === "not_configured" ? (
        // PO 2026-08-19, decision 5, verbatim: *"no provide any link"*. The line
        // STATES the configured state and does not prompt an errand: cycle
        // set-up lives in Settings → Routes & Cycles (CR-006's surface), which
        // is in the sidebar of every screen in the product.
        <span className="fin-rollup-item">{t("dashboard.cycle.notConfigured")}</span>
      ) : (
        <span className="fin-rollup-item">
          {data.state === "closes_today"
            ? t("dashboard.cycle.closesToday", { code })
            : data.state === "closed_pending_run"
              ? t("dashboard.cycle.closedPendingRun", { code })
              : t("dashboard.cycle.closesIn", { code, count: data.days ?? 0 })}
        </span>
      )}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 2 · THE KPI BAND — BR-REP-033 / BR-REP-034
// ══════════════════════════════════════════════════════════════════════════
/**
 * The five tiles, in the SERVER's order, each rendering the string it was given.
 *
 * **No tile carries a link, a button or an onClick** — *"KPI cells do not
 * navigate in v1"* (PO verbatim). That is enforced by there being nowhere in
 * this function to put one.
 *
 * **The MTD tile's sub-line is present only when a target is typed**
 * (BR-REP-034). `sub === null` is the RULED state, not a missing feature: with
 * no target the tile is the figure alone, and a new tenant on day one sees
 * nothing rather than a wrong denominator.
 */
export function dashboardKpis(
  tiles: readonly DashboardKpiTile[],
  gaps: readonly LedgerUnavailable[] | undefined,
  t: Translator,
): KpiTile[] {
  return tiles.map((tile) => {
    // DEF-2417 — the tile's LABEL, never its id. See `serverTokenLabel` and
    // the block above it for what this line used to do to the front page.
    const label = serverTokenLabel(`dashboard.kpi.${tile.id}`, t, "dashboard.kpi.unnamed");
    const detail: ReactNode =
      tile.sub === null ? (
        tile.basis === null ? undefined : (
          <span>{t(`cells.basis.${tile.basis}`)}</span>
        )
      ) : (
        <span>
          {t("dashboard.kpi.sub.target", {
            percent: tile.sub.percent_display,
            target: tile.sub.target_display ?? "",
          })}
        </span>
      );

    if (tile.display === null) {
      // ⚠ PO 2026-08-19, decision 4 — **PLAIN LANGUAGE IN THE TILE, THE
      // ARCHITECTURE SENTENCE IN THE SUPPORT LINE.** These three tiles used to
      // read *"Not available — metering publishes no unbilled-read count"*: a
      // sentence about OUR module boundaries, put to a utility clerk.
      //
      // The PO suggested **"reads not received"** and that wording was ruled
      // AGAINST, deliberately, and the reason must survive every future edit of
      // this block: *"reads not received"* asserts a fact about the UTILITY'S
      // DATA — that no reads arrived. The true fact is about OUR PRODUCT: we
      // cannot count them. **A clerk who has just imported 400 reads would be
      // told something false**, which is the same false-zero failure in plainer
      // clothes. So the tile says what is true in plain words — *"Not counted
      // yet"* — without claiming the reading did not happen.
      //
      // The specific reason is NOT deleted: it moves to the tile's SUPPORT
      // text, where somebody diagnosing a problem can reach it and a clerk
      // reading the screen is not made to.
      return {
        id: tile.id,
        label,
        value: <span className="inline-block max-w-[32ch] font-body text-base font-normal leading-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
        {t("dashboard.kpi.notCounted")}
      </span>,
        // ⚠ **CLOSED BY DEFAULT — B14 RULE 32, AND THIS TILE IS WHY THE PO
        // RAISED IT A SECOND TIME (`DEF-2375`, 2026-09-02).**
        //
        // The comment above already said the right thing — the reason *"moves
        // to the tile's SUPPORT text, where somebody diagnosing a problem can
        // reach it and a clerk reading the screen is not made to"* — and then
        // rendered it as a bare `<span>` that is always on screen. So a clerk
        // WAS made to read it: three tiles side by side, each carrying a
        // three-line paragraph about which module publishes which counter.
        //
        // Rule 32 (RATIFIED 2026-08-31, after the PO said *"too much content -
        // desctiption is too much for clark to read"* four times in twenty
        // minutes) names the shape exactly: **a stated absence is a `<details>`
        // CLOSED by default**. The reason is not deleted and not shortened —
        // it is the honest explanation of a figure we refuse to guess at, and
        // support needs it. It is simply not in a clerk's way.
        //
        // Built on `billRunShared.RunGap`'s markup rather than a new idiom:
        // rule 32's own status note records that RunGap *"is structurally a
        // `<details>` and holds by construction"*, which is the property worth
        // copying — the copy cannot leak onto the screen by accident, because
        // being closed is what a `<details>` IS.
        detail: (
          <details className="fin-absent-reason">
            <summary className="cursor-pointer text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
              {t("dashboard.kpi.whyNotCounted")}
            </summary>
            <span className="mt-1 block" role="note">
              {reasonFor(gaps, tile.unavailable_code ?? "", t)}
            </span>
          </details>
        ),
      };
    }
    // The SERVER's string, rendered verbatim. There is deliberately no
    // `MoneyCell` here: it would round a second time, on the client, with the
    // client's rules (BR-REP-029).
    return {
      id: tile.id,
      label,
      value: <span className="tabular-nums">{tile.display}</span>,
      detail,
    };
  });
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 4 · SERVICE MIX — BR-REP-025 / BR-REP-026
// ══════════════════════════════════════════════════════════════════════════
/**
 * Five rows, always, and a bar whose width is the integer the SERVER rounded.
 *
 * ⚠ **THE WIDTH IS NOT COMPUTED HERE AND MUST NOT BE.** `bar_pct` is already a
 * share of the LARGEST service (BR-REP-026 — Electric 100, Water 32, Sewer 12
 * on the PO's own figures, a column that sums to 144 and is meant to). r10's
 * markup hardcodes 70/22/8, which is a share of the TOTAL; the requirement
 * reversed that, and the number and the bar use the SAME rounded figure so they
 * can never disagree.
 *
 * An unsold or unbilled service renders `display` — which the server already
 * made an em-dash — and a zero-width bar. **`$0.00` never appears in this
 * column**: a printed zero and an absent service look identical to a reader and
 * mean opposite things.
 */
export function MixRow(props: { row: DashboardMixRow; t: Translator }) {
  const { row, t } = props;
  const labelKey = MIX_LABEL_KEYS[row.service_code];
  return (
    <div
      className="grid grid-cols-[5.5rem_1fr_auto] max-lg:grid-cols-[4.5rem_1fr_auto] items-center gap-2 border-t border-t-divider py-2 first-of-type:border-t-0"
      data-dash="mix-row"
    >
      <span className="text-sm text-text" data-dash="mix-label">
        {labelKey === undefined ? row.service_code : t(labelKey)}
      </span>
      <span className="block h-1.5 min-w-0 bg-neutral-200">
        <span
          className="block h-full bg-accent"
          data-dash="mix-fill"
          style={{ width: `${row.bar_pct}%` }}
        />
      </span>
      <span
        className="text-right text-sm tabular-nums whitespace-nowrap"
        data-dash="mix-value"
      >
        {row.display}
      </span>
    </div>
  );
}

export function ServiceMixBody(props: { data: DashboardServiceMix; t: Translator }) {
  const { data, t } = props;
  return (
    <>
      {data.rows.map((row) => (
        <MixRow key={row.service_code} row={row} t={t} />
      ))}
      {data.remainder !== null && (
        // BR-REP-025: revenue the five rows cannot hold is NAMED, so the panel
        // cannot foot to less than the period's revenue. Not folded into one of
        // the five (a wrong figure), not dropped (a silent shortfall).
        <p className="fin-absent-reason" role="note">
          {t("dashboard.serviceMix.remainder", {
            amount: data.remainder.display ?? "",
            count: data.remainder.services,
          })}
        </p>
      )}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 5a · AR AGING — BR-REP-030
// ══════════════════════════════════════════════════════════════════════════
/**
 * Five buckets with accounts, amount and share of AR.
 *
 * Every figure is `payments.outstandings`' own, pre-formatted by the server.
 * **The shares are allowed not to total 100%** (PO verbatim: *"rounded, need not
 * total 100%"*) and there is no balancing row anywhere in this component — a
 * fudge row would make the column add up by describing money nobody owes.
 *
 * The 90+ row alone carries the danger emphasis, which is r10's own `.tot` on
 * the oldest bucket and nothing else. The server decides it (`emphasis`), so a
 * screen cannot start colouring a different row.
 */
export function AgingTable(props: {
  rows: readonly DashboardAgingRow[];
  totalDisplay: string | null;
  t: Translator;
}) {
  const { t } = props;
  return (
    <div className="max-w-full overflow-x-auto">
      <table className="w-full border-collapse text-table">
        <thead>
          <tr>
            <th scope="col" className="px-1 py-2 font-normal uppercase tracking-table-header text-table-header text-neutral-600 text-left">
              {t("dashboard.aging.col.bucket")}
            </th>
            <th
              scope="col"
              className="px-1 py-2 font-normal uppercase tracking-table-header text-table-header text-neutral-600 text-right whitespace-nowrap"
            >
              {t("dashboard.aging.col.accounts")}
            </th>
            <th
              scope="col"
              className="px-1 py-2 font-normal uppercase tracking-table-header text-table-header text-neutral-600 text-right whitespace-nowrap"
            >
              {t("dashboard.aging.col.amount")}
            </th>
            <th
              scope="col"
              className="px-1 py-2 font-normal uppercase tracking-table-header text-table-header text-neutral-600 text-right whitespace-nowrap"
            >
              {t("dashboard.aging.col.share")}
            </th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => {
            const labelKey = AGING_LABEL_KEYS[row.bucket];
            return (
              <tr
                key={row.bucket}
                className={row.emphasis === "danger" ? "text-danger-700" : undefined}
              >
                <th scope="row" className="border-t border-t-divider px-1 py-2 font-normal text-left">
                  {labelKey === undefined ? row.bucket : t(labelKey)}
                </th>
                <td className="border-t border-t-divider px-1 py-2 font-normal text-right tabular-nums whitespace-nowrap">{row.accounts_display ?? "—"}</td>
                <td className="border-t border-t-divider px-1 py-2 font-normal text-right tabular-nums whitespace-nowrap">{row.amount_display ?? "—"}</td>
                {/* A share of nothing is NULL, never 0% — a tile reading "0%"
                    when a utility has no debtors is a claim. */}
                <td className="border-t border-t-divider px-1 py-2 font-normal text-right tabular-nums whitespace-nowrap">{row.share_display ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
        {/* DEF-283 — THE TOTAL THE BANDS ADD UP TO. This prop was declared, was
            genuinely passed from the page, and was rendered NOWHERE: hard-won
            law 2 in its purest form, and invisible to tsc, to eslint and even
            to a grep for the name, because the caller really does exist. Only
            rendering the component and looking for the value could see it.

            It goes in a `tfoot` rather than a fifth row so a screen reader
            announces it as a summary and not as a fifth ageing band — the four
            buckets are the data, and this is their sum. `null` draws nothing at
            all rather than an em-dash: a total is either known or the region
            had no rows to total, and in the second case the table is empty and
            a lone dash under it would be the only thing on screen. */}
        {props.totalDisplay === null ? null : (
          <tfoot>
            <tr>
              <th scope="row" className="border-t-2 border-t-divider px-1 py-2 font-semibold tabular-nums text-left">
                {t("dashboard.aging.total")}
              </th>
              <td className="border-t-2 border-t-divider px-1 py-2 font-semibold tabular-nums text-right whitespace-nowrap" />
              <td className="border-t-2 border-t-divider px-1 py-2 font-semibold tabular-nums text-right whitespace-nowrap">{props.totalDisplay}</td>
              <td className="border-t-2 border-t-divider px-1 py-2 font-semibold tabular-nums text-right whitespace-nowrap" />
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 3 · RECENT ACTIVITY — BR-REP-031
// ══════════════════════════════════════════════════════════════════════════
export function ActivityRows(props: {
  rows: readonly DashboardActivityRow[];
  t: Translator;
  locale?: string;
}) {
  const { t } = props;
  return (
    <>
      {props.rows.map((row, index) => (
        <div
          className="grid grid-cols-[3.75rem_1fr_auto] max-lg:grid-cols-[3rem_1fr_auto] items-baseline gap-2 border-t border-t-divider py-2 first-of-type:border-t-0"
          key={`${row.at}-${index}`}
        >
          <span className="text-xs tabular-nums text-neutral-600">
            {new Date(row.at).toLocaleTimeString(props.locale, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
          <span className="min-w-0 text-sm">
            {/* ⚠ **THE ` · {entity_type}` FRAGMENT IS GONE (DEF-2417).** It
                printed the audit row's own table name — `read_batch`,
                `bill_run`, `account` — beside the class label, in
                lower_snake_case, at a billing clerk. Two rules, one line:
                B14 rule 31 (nothing internal is ever visible to a utility
                user) and rule 32's clause that a row never repeats what it
                already offers, because `audit_log` writes the entity type
                and the action from the same event and the two say the same
                word on almost every row — after this fix the feed read
                *"Meter reads · read_batch"*.

                **The value is not lost.** It is still on the wire, still in
                `audit_log`, and still the S61 audit screen's own filter
                (`?f.entity_type=…`), which is where somebody looking for a
                record goes. What it is not any more is the second half of a
                sentence on the landing page. */}
            <strong>{activityLabel(row.action, t)}</strong>
          </span>
          {/* `amount` is ALWAYS null: audit_log has no money column, and reading
              one out of a stored diff would make this screen a second opinion on
              money. The em-dash is the server's own string. */}
          <span className="text-right text-sm tabular-nums whitespace-nowrap">{row.amount_display}</span>
        </div>
      ))}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// REGION 5b · TO DO — BR-REP-032
// ══════════════════════════════════════════════════════════════════════════
/**
 * At most four rows, each generated by the module that owns the work.
 *
 * The kind chip reuses the shared `.pill` tiers (`.pill.past` = action,
 * `.pill.warn` = review, `.pill.draft` = draft), which is r10's own mapping and
 * B14 rule 5's existing kit rather than a fourth pill this screen invents.
 *
 * There is no "Assign" control: nothing in this product assigns work to a named
 * person (OQ-222), and a link that goes nowhere is hard-won law 2.
 */
// ⚠ THE SHARED COMPONENT, NOT RAW MARKUP. The tones used to live in
// `StatusPill.css`, imported by `StatusPill.tsx` and by NOTHING ELSE — so a
// screen that hand-wrote a pill-and-tone class pair without rendering a
// `StatusPill` shipped a chip with no stylesheet behind it: DEF-244's shape
// for the seventh time, invisible to tsc, to eslint and to vitest. CR-018
// Route B moved the tones onto the component as utilities, which closes that
// trap by construction — but the component is still the one place a tone's
// styling is spelled, so mapping to tones and rendering it stays the rule.
const TODO_TONE: Record<string, StatusTone> = {
  action: "danger", // r10's `pill past`
  review: "warning", // r10's `pill warn`
  draft: "neutral", // r10's `pill draft`
  onboarding: "success",
};

export function TodoRows(props: { rows: readonly DashboardTodoRow[]; t: Translator }) {
  const { t } = props;
  const tenantPath = useTenantPath();
  return (
    <ul className="m-0 mt-3 grid list-none gap-2 p-0">
      {props.rows.map((row) => (
        <li
          className="flex items-baseline gap-2 border-t border-t-divider pt-2 text-sm first:border-t-0 first:pt-0"
          key={`${row.kind}-${row.code ?? row.module}`}
        >
          <StatusPill tone={TODO_TONE[row.kind] ?? "neutral"}>
            {t(`dashboard.todo.kind.${row.kind}`)}
          </StatusPill>
          <Link
            className="text-text no-underline hover:underline focus-visible:underline"
            to={tenantPath(todoHref(row.target))}
          >
            {/* ⚠ ALL THREE COLUMNS FELL BACK TO `row.code` UNTIL 2026-09-01
                (DEF-2417): a to-do the product had no copy for read
                `finance_close` to a clerk, and the SIX onboarding steps a new
                tenant sees had no copy at all, so every one of them did. The
                fallback is now words. */}
            {row.kind === "onboarding"
              ? serverTokenLabel(
                  `dashboard.todo.onboarding.${row.code ?? ""}`,
                  t,
                  "dashboard.todo.unnamed",
                )
              : row.count === null
                ? // ⚠ PO 2026-08-19, decision 3, verbatim: *"I will start with -
                  // Show 'Review billing exceptions' with no number"*. THIS is the
                  // line the ruling is about: `row.count ?? 0` rendered a **0** for
                  // a row whose owning module could not answer, and a zero tells
                  // the operator *nothing needs my attention* — which is false. A
                  // countless row gets its own sentence, not the counted one with a
                  // blank where the digit goes. Covers all six emittable codes.
                  serverTokenLabel(
                    `dashboard.todo.itemNoCount.${row.code ?? ""}`,
                    t,
                    "dashboard.todo.unnamed",
                  )
                : serverTokenLabel(
                    `dashboard.todo.item.${row.code ?? ""}`,
                    t,
                    "dashboard.todo.unnamed",
                    { count: row.count, countDisplay: row.count_display ?? "" },
                  )}
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface DashboardPageProps {
  client?: ApiClient; // test seam
  locale?: string;
}

/**
 * S7's attention strip for a credential about to lapse (`US-INT-027`).
 *
 * `BR-INT-042` asks for the warning *"on the dashboard and by email"*, and this
 * is the dashboard half. It is the same sentence S142 shows, from the same
 * server-settled `expiry` block, so the two screens cannot disagree about which
 * side of the boundary a date falls on — nothing here subtracts dates.
 *
 * ⚠ **IT DRAWS NOTHING AT ALL WHEN NOTHING IS DUE**, and that is B14 rule 32:
 * a stated absence is CLOSED by default. A dashboard that says *"no connection
 * needs attention"* every morning is a line people stop reading, and the one
 * they skip is the one that mattered.
 *
 * ⚠ **A FAILED READ IS ALSO SILENCE, DELIBERATELY.** If the integrations grid
 * cannot be fetched, this strip shows nothing rather than an error: the
 * dashboard's own regions already report their failures, and a second error
 * banner about a panel that is not the point of this screen would push the
 * numbers a utility came here for below the fold. The connection's own screen
 * is where that failure is worth reporting.
 */
function ConnectionAttention(props: { client: ApiClient }) {
  const { t } = useTranslation();
  const { timeZone, dateFormat } = useRegional({});
  const tenantPath = useTenantPath();

  const grid = useQuery({
    queryKey: queryKeys.integrations,
    queryFn: () => getIntegrationsGrid(props.client),
    retry: false,
    staleTime: DASHBOARD_STALE_MS,
  });

  const due = (grid.data?.providers ?? []).flatMap((provider) =>
    (provider.connection === null ? [] : [provider.connection])
      .filter(
        (connection) =>
          connection.expiry.state === "warning" || connection.expiry.state === "lapsed",
      )
      .map((connection) => ({ provider, connection })),
  );
  if (due.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-3" data-attention="credentials">
      {due.map(({ provider, connection }) => {
        const lapsed = connection.expiry.state === "lapsed";
        const when =
          connection.expiry.expires_at === null
            ? null
            : formatDate(connection.expiry.expires_at, timeZone, dateFormat);
        const name = t(`integrations.provider.${provider.key}.name`, {
          defaultValue: provider.display_name,
        });
        return (
          <WarningBox
            key={provider.key}
            tone={lapsed ? "now" : "soon"}
            data-warning={lapsed ? "lapsed" : "expiring"}
            sentence={
              lapsed || when === null
                ? t("integrations.expiry.attentionLapsed", { provider: name })
                : t("integrations.expiry.attention", { provider: name, date: when })
            }
            action={
              <Link
                className="text-sm text-accent-700 no-underline whitespace-nowrap hover:underline focus-visible:underline"
                to={tenantPath(`/settings/integrations/${provider.key}`)}
                data-attention-link={provider.key}
              >
                {t("integrations.expiry.reauthorise")}
              </Link>
            }
          />
        );
      })}
    </div>
  );
}


export function DashboardPage(props: DashboardPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();

  // The signed-in user's own name for the greeting. `queryKeys.me` is the SAME
  // key ShellWithSession reads, so the shell's footer block and this greeting
  // are one cache entry and can never name two different people.
  const meQuery = useQuery({ queryKey: queryKeys.me, queryFn: () => getMe(client), retry: false });

  // CR-015 — the chosen window lives in the URL (BR-SHL-011's `f.<name>`), so
  // it is shareable and survives a reload. Absent ⇒ nothing is sent and the
  // SERVER's ruled default applies; the client never spells the default itself.
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedPeriod = searchParams.get(PERIOD_PARAM);

  const summaryQuery = useQuery({
    queryKey: dashboardQueryKey(requestedPeriod),
    queryFn: () => getDashboardSummary(client, undefined, requestedPeriod ?? undefined),
    retry: false,
    // PO 2026-08-19, decision 2: five minutes, not the 30 s default. See
    // `DASHBOARD_STALE_MS` for the arithmetic the PO's *"is time enough"* was
    // answered with, and for why the SERVER half of that ruling is reported as
    // not built rather than half-built.
    staleTime: DASHBOARD_STALE_MS,
  });

  // A minute hand for the freshness line, and nothing else. Without it the age
  // would be computed once per render and a screen left open would keep saying
  // "2 minutes ago" for an hour — a stale claim about staleness, which is worse
  // than no claim at all.
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setTick(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const ageMinutes =
    summaryQuery.dataUpdatedAt > 0 ? figureAgeMinutes(summaryQuery.dataUpdatedAt, tick) : null;

  const selectPeriod = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set(PERIOD_PARAM, id);
    setSearchParams(next, { replace: true });
  };

  const name = meQuery.data?.full_name ?? null;
  const summary: DashboardSummaryResponse | undefined = summaryQuery.data;
  const failed = summaryQuery.isError && summary === undefined;
  const regions = summary?.regions;
  // BR-REP-033: the SERVER says whether this role may act. Absent (still
  // loading, or a failed fetch) means NEITHER action renders — fails closed,
  // which is hard-won law 3 applied to a permission.
  const mayAct = summary?.page_actions ?? { import_reads: false, run_billing: false };
  // How far back Recent activity looked. The SERVER's figure; the fallback is
  // the same 24 hours the server publishes, so a panel still loading does not
  // silently claim a different window.
  const activityHours = regions?.activity.data?.window_hours ?? 24;

  return (
    <div className="fin-page min-w-0" data-dash="page">
      <PageHeader
        title={name === null ? t("dashboard.greeting.anon") : t("dashboard.greeting", { name })}
        rollup={
          <CycleStatusLine
            region={regions?.cycle_status}
            // ⚠ `read_on`, NOT `as_of` (CR-015). This line is the page HEADER's
            // "what day is it, what closes next" — a statement about NOW. Fed
            // the clamped as-of of a closed window it would head the page with
            // last month's date and count down from it.
            asOf={summary?.read_on ?? null}
            t={translate}
            locale={props.locale}
          />
        }
        secondaryActions={
          // B14 rule 5's two tiers exactly — `.btn btn-secondary` and
          // `.btn btn-primary`. HIDDEN, not disabled, for a read-only role: the
          // PO's word is "hidden", and a disabled control still advertises a
          // capability the role does not have.
          mayAct.import_reads ? (
            <ButtonLink variant="secondary" to={tenantPath(READS_UPLOAD_ROUTE)}>
              {t("dashboard.action.importReads")}
            </ButtonLink>
          ) : undefined
        }
        primaryAction={
          mayAct.run_billing ? (
            <ButtonLink variant="primary" to={tenantPath(BILL_RUN_ROUTE)}>
              {t("dashboard.action.runBilling")}
            </ButtonLink>
          ) : undefined
        }
      />

      {/* S7's attention strip (US-INT-027 · BR-INT-042). ABOVE the period bar
          and the numbers: a utility whose mailbox lapses on Saturday needs to
          see that before this month's receivables, and it draws nothing at all
          when nothing is due (B14 rule 32). */}
      <ConnectionAttention client={client} />

      <PeriodBar
        filter={summary?.period_filter}
        asOf={summary?.as_of ?? null}
        ageMinutes={ageMinutes}
        onSelect={selectPeriod}
        t={translate}
        locale={props.locale}
      />

      {failed ? (
        <Panel role="alert">
          <h3>{t("dashboard.error.title")}</h3>
          {/* BR-SHL-020: the failure in plain language, derived from the
              response — never a status code shown to a billing clerk. */}
          <p className="fin-absent-reason">{apiErrorText(summaryQuery.error, translate)}</p>
        </Panel>
      ) : summary === undefined || regions === undefined ? (
        <LoadingSkeleton variant="kpi" />
      ) : (
        <>
          {regions.kpi_band.state === "error" || regions.kpi_band.data === null ? (
            <p className="fin-absent-reason" role="note">
              {regions.kpi_band.error === null
                ? t("dashboard.newTenant")
                : gapSentence(regions.kpi_band.error, translate)}
            </p>
          ) : (
            <KPIStrip
              kpis={dashboardKpis(regions.kpi_band.data.tiles, summary.unavailable, translate)}
            />
          )}

          <div className="fin-two-col">
            <RegionFrame
              region={regions.activity}
              // PO 2026-08-19: *"yes it shoudl state the window"*. The panel
              // reads 24 hours and caps at six rows, so its heading SAYS 24
              // hours — and the hours are the SERVER's figure, not a number
              // frozen into eleven catalogues, so changing
              // `ACTIVITY_WINDOW_DAYS` changes every translation with it.
              title={t("dashboard.panel.activity", { hours: activityHours })}
              t={translate}
              // ⚠ THE EMPTY SENTENCE IS THE REASON THE RULING EXISTS. It used
              // to read *"Nothing has happened here yet"*, which on a utility's
              // first Monday says something enormous and false — the true
              // statement is that nothing happened in the last 24 HOURS.
              emptyText={t("dashboard.activity.empty", { hours: activityHours })}
              link={
                <Link className="text-sm text-accent-700 no-underline whitespace-nowrap hover:underline focus-visible:underline" to={tenantPath(AUDIT_ROUTE)}>
                  {t("dashboard.activity.viewAll")}
                </Link>
              }
            >
              {(data) => <ActivityRows rows={data.rows} t={translate} locale={props.locale} />}
            </RegionFrame>

            <RegionFrame
              region={regions.service_mix}
              title={t("dashboard.panel.serviceMix")}
              t={translate}
              emptyText={t("dashboard.serviceMix.empty")}
              link={
                <Link className="text-sm text-accent-700 no-underline whitespace-nowrap hover:underline focus-visible:underline" to={tenantPath(REPORTS_ROUTE)}>
                  {t("dashboard.serviceMix.details")}
                </Link>
              }
            >
              {(data) => <ServiceMixBody data={data} t={translate} />}
            </RegionFrame>
          </div>

          <div className="fin-two-col">
            <RegionFrame
              region={regions.aging}
              title={t("dashboard.panel.aging")}
              t={translate}
              emptyText={t("dashboard.aging.empty")}
              link={<AgingDoor t={translate} />}
            >
              {(data) => (
                <AgingTable rows={data.rows} totalDisplay={data.total_display} t={translate} />
              )}
            </RegionFrame>

            <RegionFrame
              region={regions.todo}
              title={t("dashboard.panel.todo")}
              t={translate}
              emptyText={t("dashboard.todo.empty")}
            >
              {(data) => <TodoRows rows={data.rows} t={translate} />}
            </RegionFrame>
          </div>
        </>
      )}
    </div>
  );
}

export default DashboardPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-012 (12-governance/11-change-requests.md §CR-012 — the screenshot enumerated, r10's markup quoted, the PO's build spec and the FULL DSH-01 requirements, all verbatim; plus §"THE BAR RULE, WORKED") · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-024..034 · 04-docs/05-modules/12-reports/06-epics/EP-REP-05-dashboards.md §US-REP-019 + its CR-012 AMENDMENT · 12-governance/02-decision-log.md 2026-08-18 (both rulings) · 04-docs/01-spec/01-screen-inventory.md S7 · 05-prototype/r10-2026-08-16/SMARTBillHub.dc.html lines 560-626
// screens: S7   (DEF-137's screen-id stamp — see 10-scripts/gates/g25_screen_coverage.py)
// generated: 2026-08-16 by story-coder (DEF-129 lane) · REBUILT 2026-08-18 by story-coder (CR-012 DSH-01 lane — six independent regions, five fixed service rows, the cycle status line, role-gated page actions, and no client-side currency math) · AMENDED 2026-08-19 by story-coder (CR-012 closing lane — the five PO rulings of the design review: the tenant's own services with a ten-code label map, a 5-minute staleTime, no zero on a countless To-do row, "Not counted yet" in place of the architecture sentence, the cycle line's link removed, and Recent activity stating its window)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — every case in dashboard.test.tsx failed before its region existed; the failures are quoted in the test file. tsc✔ eslint --max-warnings 0✔ vitest✔ (vite build and Playwright are the coordinator's — this lane was asked not to run them)
// exceptions: AMENDED 2026-08-19 — (0) the SERVER half of the caching ruling is NOT BUILT and is reported rather than half-shipped: a tenant+as-of cache was authorised on condition the screen states the cache AGE, and doing that honestly needs a shared cache backend this deployment does not configure. The client half (`DASHBOARD_STALE_MS`) stands alone and asserts nothing · (0b) the To-do panel still has no "Assign" control (OQ-222) · (1) NO `MoneyCell` on any served figure — BR-REP-029 moves formatting to the server, which is in stated tension with BR-SHL-023 and is REPORTED, not resolved · (2) the weekday/date and the activity TIME are formatted client-side and that is not an exception to BR-REP-029: a weekday name is language, this product ships eleven catalogues, and a server-rendered "Wednesday" would be English in all of them · (3) NO time-banded greeting (OQ-220) and NO "Assign" control (OQ-222, remaining half) — two r10 details whose rules do not exist · (4) activity amounts are the server's em-dash on every row: audit_log has no money column · (5) the page actions are HIDDEN rather than disabled for a read-only role, which is the PO's own word, and the decision is the SERVER's (`page_actions`) so a hidden control is a permission rather than a suggestion
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
