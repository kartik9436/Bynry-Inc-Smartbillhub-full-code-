// ── Trace ──────────────────────────────────────────────
// Story:    RAT-02 — the rate schedule VIEW DETAILS screen. Co-story US-RAT-004
//           (the list it opens from) · US-RAT-010 (the version chain).
//           Screens: S11 (A1) · RAT-02
// Change:   CR-157-BRC10 wave B — REBUILT FROM THE 2026-10-01 DRAWING
//           (`05-prototype/rate-schedules-2026-10-01/images/08–39`, eight
//           schedules × four tabs, read as IMAGES — B14 rule 42). Five tabs
//           become FOUR: Overview · Rates · Plans · Audit (decision log
//           2026-10-01, *"FOUR TABS: OVERVIEW HOLDS DETAILS AND BILLING RULES
//           TOGETHER, RATE MATRIX IS RENAMED RATES"*). The tier chart, the
//           rate matrix, the Billing rules tab, the Revenue absence band and the
//           Sample bill panel are GONE because the drawing the PO adopted does
//           not draw them; the PO left Revenue and Sample bill out on purpose
//           (*"until each can be calculated"*).
// Rules:    BR-RAT-088 (the CHARGE CODE owns the base; this screen reads it) ·
//           BR-RAT-031 (status is DERIVED; a dateless version is the draft) ·
//           BR-RAT-037 / BR-RAT-104 (a change is a new version; a correction
//           restates the same window) · BR-RAT-038 (the UoM gate is stated) ·
//           the MINIMUM is per meter size (PO 2026-10-01, option A) ·
//           BR-SHL-011 · BR-SHL-012 · BR-SHL-025 · BR-SHL-032 · BR-SHL-034 ·
//           BR-SHL-044 · B14 rules 6, 21, 31, 32, 33, 37, 41–44
// Tests:    src/features/rating/RateScheduleDetail.test.tsx ·
//           src/features/rating/rateScheduleView.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  archiveRateSchedule,
  duplicateRateSchedule,
  getMyPermissions,
  getRateSchedule,
  getTenantServices,
} from "@/api/endpoints";
import type { ScheduleDetail, VersionRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import type { ScheduleCardExtras } from "@/api/rateScheduleReads";
import { getScheduleRates, sizesPricedText } from "@/api/rateScheduleReads";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DateCell, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { formatMoney } from "@/components/MoneyCell";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { formatQuantity } from "@/components/UnitCell";
import {
  RefusalNotice,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DASHBOARD_ROUTE,
  GuardedButton,
  PLANS_RATES_ROUTE,
  RatingStatusPill,
  enumLabel,
  ratingAccess,
  ratingIsDenied,
  ratingIsReadOnly,
  scheduleStatusTone,
} from "./ratingShared";
import type { Translator } from "./ratingShared";
import { RateOverviewTab, RatePlansTab, RateRatesTab } from "./rateScheduleViewTabs";

// ── Routes ─────────────────────────────────────────────────────────────────

/** RAT-01, the card grid this screen exits to (B14 rule 1 — `←` names the exit). */
export const RATES_TAB_ROUTE = `${PLANS_RATES_ROUTE}/rates`;

/** RAT-03 in edit mode. The wizard used to own `…/rates/:tariffId` outright; it
 *  moves down one segment so the DETAIL can be what a schedule's name opens,
 *  which is what r10 draws and what CR-013 part 1 describes. */
export function scheduleEditRoute(tariffId: string): string {
  return `${RATES_TAB_ROUTE}/${tariffId}/edit`;
}

/** RAT-03 in create mode — `Duplicate`'s fallback destination (see below). */
export const NEW_SCHEDULE_ROUTE = `${RATES_TAB_ROUTE}/new`;

// ── The tab strip ──────────────────────────────────────────────────────────

/**
 * CR-157-BRC10 B — FOUR tabs, in the drawn order (`08-view-W-RES-overview.png`).
 * The active one is URL state (`?tab=`), so a link to a tab is shareable.
 */
export const RATE_DETAIL_TABS = ["overview", "rates", "plans", "audit"] as const;

export type RateDetailTab = (typeof RATE_DETAIL_TABS)[number];

export const RATE_DETAIL_TAB_PARAM = "tab";

/**
 * The FIVE-tab screen's addresses keep working (BR-SHL-011: an unknown value
 * falls back, it never errors): `?tab=matrix` lands on Rates, `?tab=versions`
 * on Audit, `?tab=billing-rules` on Overview — where those facts now live.
 */
const LEGACY_TABS: Record<string, RateDetailTab> = {
  matrix: "rates",
  versions: "audit",
  "billing-rules": "overview",
};

export function rateDetailTabFromParam(raw: string | null): RateDetailTab {
  const found = RATE_DETAIL_TABS.find((tab) => tab === raw);
  if (found !== undefined) {
    return found;
  }
  return (raw === null ? undefined : LEGACY_TABS[raw]) ?? RATE_DETAIL_TABS[0];
}

// ── The rate matrix's COLUMNS — this is where BR-RAT-088 becomes checkable ──

export interface MatrixColumn {
  key: string;
  labelKey: string;
  /**
   * Whether an edit mode may offer this column.
   *
   * ⚠ `base` IS `false` AND THAT IS THE WHOLE RULE. BR-RAT-088 (PO ruling
   * 2026-08-20, superseding BR-RAT-012 and BR-RAT-027): *"the CHARGE CODE owns
   * the base amount"*, and the design's §A3 adds *"one source, two surfaces"* —
   * the schedule's matrix shows it read-only and attributed and *"its edit mode
   * does not include it"*. The worked cost of getting it wrong, as shown to the
   * PO: a 5/8" residential water account where the plan, the schedule and
   * `BASE-W` each say $12.00 bills $24.00 if two of the three are charged, and
   * $23,069.50 a month across 1,247 connections — *"and no test catches it,
   * because both rows are individually correct."*
   */
  editable: boolean;
}

/**
 * The matrix's fixed columns, in r10's order (`size · base · min · … ·
 * accounts`, 07-r10-plans-rates-readout.md §4). Tier columns are DATA — one per
 * stored tier — so they are appended by the renderer, never listed here.
 */
export const MATRIX_COLUMNS: readonly MatrixColumn[] = [
  { key: "size", labelKey: "rating.rateDetail.matrix.col.size", editable: false },
  { key: "base", labelKey: "rating.rateDetail.matrix.col.base", editable: false },
  { key: "minimum", labelKey: "rating.rateDetail.matrix.col.minimum", editable: true },
  { key: "accounts", labelKey: "rating.rateDetail.matrix.col.accounts", editable: false },
];

/** What an inline editor may write. `base` is absent by BR-RAT-088. */
export function editableMatrixColumns(): readonly MatrixColumn[] {
  return MATRIX_COLUMNS.filter((column) => column.editable);
}

// ── The version chain (Versions & filings) ─────────────────────────────────

export type VersionState = "draft" | "active" | "scheduled" | "superseded" | "corrected";

/**
 * A version's state, derived WITHOUT A CLOCK.
 *
 * BR-TEN-043 keeps wall clocks off anything that decides money, and the server
 * has already done the dating: `current_version` is `in_force_version(today)`
 * (falling back to the latest), and a superseded window carries its
 * `effective_to`. So four rules, in order, and none of them reads `Date.now()`:
 *
 *   · no `effective_from`      → THE draft (BR-RAT-031: it has never been in
 *                                force, so it is not history and prices nothing)
 *   · `superseded_by` is set   → CORRECTED (see below)
 *   · it IS `current_version`  → active
 *   · it has an `effective_to` → superseded
 *   · otherwise                → scheduled (dated, not current, not ended)
 *
 * ⚠ **`DEF-RAT-5827` · THE CORRECTED ROW USED TO READ `Scheduled`, WHICH IS
 * THIS SCREEN'S WORD FOR A CHANGE STILL TO COME — the exact opposite of what
 * happened to it.** `BR-RAT-104`'s correction is a SECOND row over the SAME
 * window: `correct_version` copies `original.effective_to` onto the new row and
 * sets `original.superseded_by`. So the corrected row USED TO KEEP a NULL
 * `effective_to` — it was never ended, it was restated — and the last line
 * above therefore called it `scheduled`. On a schedule whose live price had
 * just been corrected the Audit tab said a version that no longer prices
 * anything was *about to start*.
 *
 * `superseded_by` is the only field that can tell them apart and it is set by
 * the same write that creates the pair, so it is true the instant the pair
 * exists. `PlanDetail.planVersionState` reads it for the identical reason and
 * records the identical argument.
 *
 * ⚠ **THE PARAGRAPH ABOVE IS NOW HISTORY ON ITS FIRST HALF, AND DELIBERATELY
 * KEPT: `BR-RAT-1044` (PO ruling 2026-09-29) GIVES A CORRECTED ROW AN END
 * DATE.** `correct_rate_schedule_version` stamps
 * `max(the correction date, effective_from)` onto the row it supersedes, so
 * the register shows *when the wrong version stopped being used* — PO,
 * verbatim, choosing option (a) of three: *"i will take this and use
 * superseded_by in filter - so that it is always unique and even if we see in
 * audit it is clear"*.
 *
 * **NOTHING IN THIS FUNCTION CHANGES, AND THE ORDER OF THE RULES IS WHY.**
 * `superseded_by` is tested BEFORE `effective_to`, so a corrected row reads
 * `Corrected` whether its end date is stamped (every correction from now on)
 * or NULL (every correction taken before this ruling — it is FORWARD-ONLY and
 * nothing is backfilled). Both shapes are on screen at once on a live tenant.
 * Had the order been the other way round, a stamped row would read
 * `Superseded` — the word for *a later rate replaced it*, which is a
 * different fact about a regulator-facing table.
 *
 * ⚠ **AND THE `Effective` CELL IS WHERE THE RULING BECOMES VISIBLE**, with no
 * code here at all: `EffectiveRangeCell` already renders a closed span as
 * `02/01/2026 – 03/01/2026` and an open one as `02/01/2026 →`, so a corrected
 * row stops saying *still running* the day it is corrected. That was the
 * PO's stated reason for choosing (a).
 */
export function versionState(version: VersionRow, currentId: string | null): VersionState {
  if (version.effective_from === null) {
    return "draft";
  }
  if (version.superseded_by !== null) {
    return "corrected";
  }
  if (currentId !== null && version.id === currentId) {
    return "active";
  }
  return version.effective_to === null ? "scheduled" : "superseded";
}

export function versionStateTone(state: VersionState) {
  if (state === "active") {
    return "success" as const;
  }
  // `corrected` wears `superseded`'s tone: both mean *this row no longer states
  // what the schedule says*, and a third colour would imply a third kind of
  // history where there are two.
  return state === "superseded" || state === "corrected"
    ? ("warning" as const)
    : ("neutral" as const);
}

/**
 * The rows of the Versions & filings table, ordered as §10 requires:
 * *"a draft future version is listed above the current one … the table is
 * ordered by effective date descending, not by status"*.
 *
 * `versions` arrives ASCENDING by `effective_from` (`selectors.tariff_versions`
 * orders by `effective_from, created_at`), so it is reversed, and the dateless
 * draft — which sorts against nothing — goes on top.
 *
 * ⚠ THE VERSION NUMBER IS DERIVED FROM THAT ORDER AND NOTHING STORES ONE.
 * `apps/billing/selectors.py:910` serves `tariff_version_label: None` with the
 * reason in its own docstring — *"rating stores no version LABEL: a version is
 * identified by its window"*. So `v3` here is this screen's ordinal over the
 * server's own ordering, not a filed identifier: if a utility files "v3" with a
 * regulator and a version is later back-dated into the chain, the two disagree.
 * Reported rather than papered over — the docket a regulator recognises is the
 * `FILED AS` column, which IS stored.
 */
export interface VersionLine {
  version: VersionRow;
  /** 1-based position in effective-date order; null for the dateless draft. */
  ordinal: number | null;
  state: VersionState;
}

/**
 * DEF-369 · what the VERSION column prints, and whether it is an IDENTIFIER or
 * a position.
 *
 * `version_label` is what the utility filed — the label a docket references —
 * and it wins whenever it exists. When it does not, the ordinal above is used
 * AND MARKED DERIVED, because it is this screen's count over the server's
 * effective-date order and not an identifier: back-date a version into the
 * chain and every ordinal after it moves, while the filed label does not.
 *
 * `derived` is what the cell uses to decide whether to print the "counted, not
 * filed" note. It is not styling — it is the difference between showing a
 * regulator a number we stand behind and one we do not.
 */
export function versionLabel(line: VersionLine): { text: string | null; derived: boolean } {
  const stored = line.version.version_label;
  if (stored !== null && stored.trim() !== "") {
    return { text: stored, derived: false };
  }
  return { text: null, derived: true };
}

/**
 * `DEF-RAT-5831` · **`current_version` IS A FALLBACK, AND THIS SCREEN READ IT
 * AS A FACT.**
 *
 * `selectors.schedule_card` serves `current = in_force_version(today) or
 * latest_version(tariff)`. On a schedule filed AHEAD OF TIME nothing is in
 * force, so the field arrives holding a FUTURE version — and every surface
 * keyed off it then said that version was live: the `IN FORCE` tile named
 * `v1 · 03/01/2027`, the eyebrow read `… · V1`, and the Audit table gave it the
 * green `Active` pill. In the same header the status pill read `Draft` and the
 * `NEXT CHANGE` tile read `03/01/2027`. **One screen, saying both.**
 *
 * The server has already answered the question, in a field of its own:
 * `schedule_state` sets `status` to `draft` in exactly the case
 * `in_force_version(today)` returned nothing. So the id is taken only when the
 * schedule says something IS in force — no clock is read here, which BR-TEN-043
 * requires, and the date arithmetic stays where it already lives.
 *
 * ⚠ `archived` deliberately keeps today's behaviour. `schedule_state` tests
 * `deleted_at` FIRST, so a retired schedule reports `archived` whether or not a
 * version is in force, and treating that as *nothing is in force* would strip
 * the `Active` pill off the history of every schedule a utility has ever
 * retired.
 */
export function inForceVersionId(detail: ScheduleDetail): string | null {
  return detail.status === "draft" ? null : (detail.current_version?.id ?? null);
}

/**
 * `DEF-RAT-8829` · **THE NUMBER A VERSION READS, ONE RULE FOR EVERY SURFACE.**
 *
 * A version's number is its POSITION in the served order — and a correction is
 * a version of its own: `15-view-SEWER-audit.png` draws `v1 · Corrected` and
 * `v2 · In force · Fixes v1`. The wizard used to count the rows NOT superseded
 * instead, which is the number of the LATEST version, so with a November change
 * already scheduled a correction of October's v1 read `v2 (corrected)`. It now
 * asks this, for the row being corrected (image 71: `v3 (corrected)`).
 */
export function versionOrdinal(versions: readonly (VersionRow | null)[], id: string | null | undefined): number | null {
  return savedOrder(versions).get(id ?? "") ?? null;
}

/**
 * `DEF-RAT-9003` (coordinator decision, law 13) — **A NUMBER, ONCE SHOWN, NEVER
 * CHANGES.** Versions are numbered in the order they were SAVED (`created_at`),
 * not by their dates: correcting October's v1 after November's v2 was saved
 * makes the correction v3 (*Fixes v1*) and November stays v2 — by date order
 * November became v3 the moment the correction slotted in before it. A row the
 * server sends without `created_at` keeps its served position.
 */
function savedOrder(versions: readonly (VersionRow | null)[]): Map<string, number> {
  const activated = versions.filter((row): row is VersionRow => row !== null);
  const ranked = activated
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      const ka = a.row.created_at ?? "";
      const kb = b.row.created_at ?? "";
      return ka !== "" && kb !== "" && ka !== kb ? (ka < kb ? -1 : 1) : a.index - b.index;
    });
  return new Map(ranked.map(({ row }, at) => [row.id, at + 1]));
}

export function versionLines(detail: ScheduleDetail): VersionLine[] {
  const currentId = inForceVersionId(detail);
  const activated = detail.versions.filter((row): row is VersionRow => row !== null);
  const order = savedOrder(activated);
  const numbered: VersionLine[] = activated.map((version, index) => ({
    version,
    ordinal: order.get(version.id) ?? index + 1,
    state: versionState(version, currentId),
  }));
  numbered.reverse();
  const draft = detail.draft_version;
  if (draft === null) {
    return numbered;
  }
  return [{ version: draft, ordinal: null, state: versionState(draft, currentId) }, ...numbered];
}

// ── The screen ─────────────────────────────────────────────────────────────

const PART_SEPARATOR = " · ";

export interface RateScheduleDetailProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

/** The ordinal the NEXT change will carry — the scheduled row of the chain. */
export function nextChangeOrdinal(lines: readonly VersionLine[], on: string | null): number | null {
  if (on === null) {
    return null;
  }
  return (
    lines.find((line) => line.version.effective_from === on && line.state === "scheduled")
      ?.ordinal ?? null
  );
}

export function RateScheduleDetail(props: RateScheduleDetailProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional(props);
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const tariffId = params.tariffId ?? "";
  const activeTab = rateDetailTabFromParam(searchParams.get(RATE_DETAIL_TAB_PARAM));
  const [pendingRetire, setPendingRetire] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  // BR-SHL-025: the caller's own A4 `plans_rates` cell decides whether the
  // write controls are live. The server still refuses a forged write.
  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const detailQuery = useQuery({
    queryKey: queryKeys.rateSchedule(tariffId),
    queryFn: () => getRateSchedule(tariffId, client),
    enabled: tariffId !== "",
    retry: false,
  });
  // DEF-RAT-8846 — the Rates tab's read (same cache key), for a base price
  // scheduled after today: the Next change tile shows it.
  const ratesQuery = useQuery({
    queryKey: ["rate-schedules", "rates", tariffId],
    queryFn: () => getScheduleRates(tariffId, client),
    enabled: tariffId !== "",
    retry: false,
  });
  // The GL account is a DISPLAY (BR-BIL-067): Settings maps service → account.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  // DEF-370 · a duplicate is a NEW schedule carrying a DRAFT copy; success
  // opens the copy, because landing back on the source makes a clerk click twice.
  const duplicate = useMutation({
    mutationFn: () => duplicateRateSchedule(tariffId, {}, client),
    onSuccess: (copy) => {
      setRefusal(null);
      fireToast(t("rating.rateDetail.toast.duplicated", { name: copy.name }));
      void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
      navigate(tenantPath(scheduleEditRoute(copy.id)));
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  const retire = useMutation({
    mutationFn: () => archiveRateSchedule(tariffId, client),
    onSuccess: (saved) => {
      setPendingRetire(false);
      setRefusal(null);
      fireToast(t("rating.rateDetail.toast.retired", { name: saved.name }));
      void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
    },
    onError: (error: unknown) => {
      // "referenced by N plans — detach first" arrives with its own count.
      setPendingRetire(false);
      setRefusal(refusalOf(error, translate));
    },
  });

  if (permissionsQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    // BR-SHL-003: a role with "—" on plans_rates never sees the surface at all.
    return (
      <PermissionDenied
        helper={t("rating.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);

  if (detailQuery.data === undefined && detailQuery.isError) {
    if (isPermissionDenied(detailQuery.error)) {
      return (
        <PermissionDenied
          helper={t("rating.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    // A18 §4 — Retry re-issues the IDENTICAL query.
    return (
      <FailedWithRetry
        title={t("rating.rateDetail.failedTitle")}
        reason={apiErrorText(detailQuery.error, translate)}
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(RATES_TAB_ROUTE))}
      />
    );
  }

  const served = detailQuery.data;
  if (served === undefined) {
    return <LoadingSkeleton variant="card" />;
  }
  const detail: ScheduleDetail & ScheduleCardExtras = served;

  const version = detail.current_version ?? detail.draft_version;
  const lines = versionLines(detail);
  const currentOrdinal = lines.find((line) => line.state === "active")?.ordinal ?? null;
  const service = (servicesQuery.data ?? []).find((row) => row.service === detail.service);
  const glAccount =
    service?.revenue_account === null || service?.revenue_account === undefined
      ? null
      : [service.revenue_account.code, service.revenue_account.name].filter(Boolean).join(" — ");

  // `RATE SCHEDULE · WATER · TIERED · V3` — the drawn eyebrow, four parts.
  const kickerParts = [
    t("rating.rateDetail.kicker.object"),
    detail.service_name,
    enumLabel(translate, "rating.model", detail.structure),
    currentOrdinal === null
      ? t("rating.rateDetail.kicker.draft")
      : t("rating.rateDetail.kicker.version", { n: currentOrdinal }),
  ].filter((part) => part !== "—" && part !== "");

  const tabs = RATE_DETAIL_TABS.map((id) => ({ id, label: t(`rating.rs.tab.${id}`) }));
  const nextOrdinal = nextChangeOrdinal(lines, detail.scheduled_change);
  const baseNext = ratesQuery.data?.base_next_change ?? null;
  const sizes = sizesPricedText(translate, detail.sizes_priced, detail.sizes_total);

  // The four drawn tiles: IN FORCE · UNITS · SIZES PRICED · NEXT CHANGE.
  const kpis: readonly KpiTile[] = [
    {
      id: "inForce",
      label: t("rating.rateDetail.kpi.inForce"),
      value:
        currentOrdinal === null
          ? t("rating.rateDetail.kpi.inForceNone")
          : t("rating.rateDetail.kicker.version", { n: currentOrdinal }),
      detail:
        detail.effective_from === null ? undefined : (
          <span className="inline-flex gap-1">
            {t("rating.rs.kpi.since")}
            <DateCell value={detail.effective_from} timeZone={timeZone} dateFormat={dateFormat} />
          </span>
        ),
    },
    {
      id: "units",
      label: t("rating.rateDetail.kpi.units"),
      // `applied_to_accounts` counts UNITS (DEF-RAT-4664); the word is right.
      value: formatQuantity(String(detail.applied_to_accounts)),
      detail: t("rating.rs.kpi.onPlans", { count: detail.used_by_plans }),
    },
    {
      id: "sizes",
      label: t("rating.rs.kpi.sizesPriced"),
      value: sizes ?? t("rating.rs.oneAmount"),
    },
    {
      id: "nextChange",
      label: t("rating.rateDetail.kpi.nextChange"),
      value:
        detail.scheduled_change === null ? (
          baseNext ? (
            // DEF-RAT-8846 — a base price scheduled on the code. DEF-RAT-9011 — the
            // amount alone is the value; "from <date>" is the detail line below it,
            // as IN FORCE's "since", so the date is never cut at 1440.
            <span data-next-base-price="">{formatMoney(baseNext.amount, version?.currency ?? "USD")}</span>
          ) : (
            t("rating.rs.none")
          )
        ) : (
          <span className="inline-flex gap-1">
            {nextOrdinal !== null && (
              <span>
                {t("rating.rateDetail.kicker.version", { n: nextOrdinal })}
                {PART_SEPARATOR}
              </span>
            )}
            <DateCell value={detail.scheduled_change} timeZone={timeZone} dateFormat={dateFormat} />
          </span>
        ),
      detail:
        detail.scheduled_change === null && baseNext ? (
          <span className="inline-flex gap-1" data-next-base-from="">
            {t("rating.rs.kpi.from")}
            <DateCell value={baseNext.effective_from} timeZone={timeZone} dateFormat={dateFormat} />
            {/* DEF-RAT-9011 — whose price, when the tab lists more than one base code. */}
            {(ratesQuery.data?.base_codes?.length ?? 0) > 1 && (
              <span>
                {PART_SEPARATOR}
                {baseNext.code}
              </span>
            )}
          </span>
        ) : undefined,
    },
  ];

  return (
    <div className="pt-6 px-4 pb-8" data-screen="rate-schedule-view">
      <PageHeader
        backTo={{ to: tenantPath(RATES_TAB_ROUTE), label: t("rating.rateDetail.back") }}
        kicker={kickerParts.join(PART_SEPARATOR)}
        title={detail.name}
        rollup={<InForceLine detail={detail} timeZone={timeZone} dateFormat={dateFormat} />}
        status={
          <RatingStatusPill
            tone={scheduleStatusTone(detail.status)}
            stem="rating.schedule.status"
            value={detail.status}
          />
        }
        secondaryActions={
          <>
            {/* CR-087 E1 (PO 2026-09-08): Duplicate · Edit · Retire, the same
                three in the same order on every detail screen — top-right in
                the shared page head on every tab (B14 rule 2; DEF-RAT-9101,
                decision log 2026-10-02, superseding DEF-RAT-8824's bottom bar). */}
            <GuardedButton
              readOnly={readOnly}
              readOnlyReason={t("rating.readOnlyReason")}
              onClick={() => {
                setRefusal(null);
                duplicate.mutate();
              }}
            >
              {t("rating.rateDetail.action.duplicate")}
            </GuardedButton>
            <GuardedButton
              readOnly={readOnly}
              readOnlyReason={t("rating.readOnlyReason")}
              onClick={() => navigate(tenantPath(scheduleEditRoute(detail.id)))}
            >
              {t("rating.rateDetail.action.edit")}
            </GuardedButton>
            <GuardedButton
              readOnly={readOnly}
              readOnlyReason={t("rating.readOnlyReason")}
              variant="danger"
              onClick={() => {
                setRefusal(null);
                setPendingRetire(true);
              }}
            >
              {t("rating.rateDetail.action.retire")}
            </GuardedButton>
          </>
        }
        // `08-view-W-RES-overview.png` draws the band and the four tiles ABOVE
        // the tab strip: they describe the schedule, not the tab.
        aboveTabs={
          <div className="mt-6">
            {detail.scheduled_change !== null && (
              // `08-view-W-RES-overview.png` — two FACTS, under the header.
              <p
                className="m-0 mb-4 flex flex-wrap gap-x-3 bg-warning-100 px-4 py-3 text-base text-warning-700"
                role="status"
                data-scheduled-change=""
              >
                <strong>{t("rating.rs.changeScheduled")}</strong>
                <span className="inline-flex gap-1">
                  {t("rating.rs.newPricesStart")}
                  <DateCell
                    value={detail.scheduled_change}
                    timeZone={timeZone}
                    dateFormat={dateFormat}
                  />
                </span>
              </p>
            )}

            {/* DEF-RAT-8004 · PO 2026-10-01 (option A): where two live versions
                are in force together, bills use the newest — the server lists
                them winner first. Stated here, never silently resolved. */}
            {(detail.versions_overlap ?? []).map((stretch) => {
              const names = stretch.versions.map(
                (one) => one.label ?? formatDate(one.effective_from, timeZone, dateFormat),
              );
              return (
                <p
                  key={stretch.on}
                  className="m-0 mb-4 flex flex-wrap gap-x-3 bg-warning-100 px-4 py-3 text-base text-warning-700"
                  role="status"
                  data-versions-overlap=""
                >
                  <strong>{t("rating.rateDetail.overlap.title")}</strong>
                  <span>
                    {t("rating.rateDetail.overlap.body", { versions: names.join(", "), used: names[0] })}
                  </span>
                </p>
              );
            })}

            <KPIStrip kpis={kpis} />
          </div>
        }
        tabs={tabs}
        activeTabId={activeTab}
        tabsLabel={t("rating.rateDetail.tabsLabel")}
        onTabSelect={(tab) => {
          const next = new URLSearchParams(searchParams);
          next.set(RATE_DETAIL_TAB_PARAM, tab.id);
          setSearchParams(next, { replace: true });
        }}
      />

      <RefusalNotice refusal={refusal} />

      {/* BR-RAT-038: the gate is STATED, never silently converted. */}
      {!detail.uom_gate.satisfied && (
        <p
          role="note"
          className="m-0 mb-4 text-base px-2 py-1 border-l-[3px] border-l-accent-500 bg-surface"
        >
          {t("rating.uom.mismatch_no_factor", {
            schedule_uom: detail.uom_gate.schedule_uom ?? "—",
            billed_uom: detail.uom_gate.priced_against ?? detail.uom_gate.billed_uom ?? "—",
          })}
        </p>
      )}

      {activeTab === "overview" && (
        <RateOverviewTab
          detail={detail}
          version={version}
          customerClass={detail.customer_class_name ?? null}
          baseCode={detail.base_code ?? null}
          glAccount={glAccount}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}
      {activeTab === "rates" && (
        <RateRatesTab
          detail={detail}
          version={version}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}
      {activeTab === "plans" && <RatePlansTab detail={detail} client={client} />}
      {activeTab === "audit" && (
        <AuditTab lines={lines} timeZone={timeZone} dateFormat={dateFormat} />
      )}

      {pendingRetire && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): retire a rate schedule — rule 6's own example.
          confirmVariant="danger"
          title={t("rating.rateDetail.confirm.retire.title", { name: detail.name })}
          consequence={t("rating.rateDetail.confirm.retire.body", {
            name: detail.name,
            plans: detail.used_by_plans,
          })}
          confirmLabel={t("rating.rateDetail.confirm.retire.verb")}
          working={retire.isPending}
          onConfirm={() => retire.mutate()}
          onCancel={() => setPendingRetire(false)}
        />
      )}
    </div>
  );
}

/** `In force from 01/01/2026 · no end` — the line beside the status pill. */
function InForceLine(props: {
  detail: ScheduleDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const version = props.detail.current_version;
  if (props.detail.status === "draft" || version === null || version.effective_from === null) {
    return <span>{t("rating.rateDetail.noVersion")}</span>;
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {t("rating.rateDetail.effectiveFrom")}
      <DateCell
        value={version.effective_from}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
      />
      <span aria-hidden="true">·</span>
      {version.effective_to === null ? (
        <span>{t("rating.rs.noEndLower")}</span>
      ) : (
        <DateCell
          value={version.effective_to}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
    </span>
  );
}

// ── Audit — the version chain (§10) ────────────────────────────────────────

/**
 * The drawn seven columns (`11-view-W-RES-audit.png`, `15-view-SEWER-audit.png`):
 * Version · Effective from · Effective to · Filed as · What changed · By ·
 * Status. **This is the OBJECT'S OWN RECORD, not a view on `audit_log`** — a
 * version row is billing input; an audit row is never read by the engine.
 *
 * The status words are the drawing's: *In force · Scheduled · Ended ·
 * Corrected · Draft*, over `versionState`'s clock-free derivation.
 */
export const AUDIT_STATUS_TONE: Record<VersionState, "success" | "warning" | "neutral"> = {
  active: "success",
  scheduled: "warning",
  corrected: "warning",
  superseded: "neutral",
  draft: "neutral",
};

/**
 * What the WHAT CHANGED cell prints. A correction prints its own reason
 * (`DEF-RAT-5827`); the first version with no note reads *Created*, as drawn;
 * any other version with no note is a dash.
 */
export function auditChangeText(t: Translator, line: VersionLine, lines: readonly VersionLine[] = []): string {
  const reason = correctionRowReason(line.version);
  // `DEF-RAT-9003` — a correction says which version it fixes (image 15:
  // *Fixes v1: $6.2500*), since its own number is the next free one.
  const fixes = line.version.corrects === null
    ? null
    : (lines.find((other) => other.version.id === line.version.corrects)?.ordinal ?? null);
  if (fixes !== null) {
    return t("rating.rs.audit.fixes", { n: fixes, reason: reason ?? "—" });
  }
  if (reason !== null) {
    return reason;
  }
  if (line.version.corrects === null && line.ordinal === 1) {
    return t("rating.rs.audit.created");
  }
  return "—";
}

function AuditTab(props: {
  lines: readonly VersionLine[];
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const date = (value: string | null) =>
    value === null ? (
      "—"
    ) : (
      <DateCell value={value} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );
  return (
    <Panel as="section" title={t("rating.rateDetail.panel.versions")} data-rs-tab="audit">
      {props.lines.length === 0 ? (
        <p className="m-0 text-base text-neutral-700">{t("rating.rateDetail.versions.empty")}</p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("rating.rateDetail.versions.col.version")}</th>
              <th scope="col">{t("rating.rs.fact.effectiveFrom")}</th>
              <th scope="col">{t("rating.rs.fact.effectiveTo")}</th>
              <th scope="col">{t("rating.rateDetail.versions.col.filedAs")}</th>
              <th scope="col">{t("rating.rateDetail.versions.col.change")}</th>
              <th scope="col">{t("rating.rateDetail.versions.col.by")}</th>
              <th scope="col">{t("rating.rateDetail.versions.col.status")}</th>
            </tr>
          </thead>
          <tbody>
            {props.lines.map((line) => (
              <tr key={line.version.id} data-audit-row={line.state}>
                {/* DEF-369 — a FILED label wins over the counted position. */}
                <td className="tabular-nums">
                  {versionLabel(line).text ??
                    (line.ordinal === null
                      ? t("rating.rateDetail.kicker.draft")
                      : t("rating.rateDetail.kicker.version", { n: line.ordinal }))}
                </td>
                <td>{date(line.version.effective_from)}</td>
                <td>{date(line.version.effective_to)}</td>
                <td>{line.version.regulator_ref ?? "—"}</td>
                <td>{auditChangeText(translate, line, props.lines)}</td>
                {/* DEF-367 — WHO FILED IT, never a uuid. */}
                <td>{line.version.submitted_by?.name ?? "—"}</td>
                <td>
                  <StatusPill tone={AUDIT_STATUS_TONE[line.state]}>
                    {t(`rating.rs.audit.status.${line.state}`)}
                  </StatusPill>
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Panel>
  );
}

/**
 * `DEF-RAT-5827` — which sentence the WHAT CHANGED cell prints: a correction
 * row prints `correction_reason`, everything else `change_reason`. A
 * correction carries the corrected row's filing note forward unchanged, so
 * printing `change_reason` on it would repeat the sentence beneath it.
 */
export function correctionRowReason(version: VersionRow): string | null {
  const reason = version.corrects === null ? version.change_reason : version.correction_reason;
  return reason === null || reason.trim() === "" ? null : reason;
}

export default RateScheduleDetail;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-013 PART 1 + 04-docs/05-modules/06-rating/09-screen-inventory.md
//         §2 · §10 — AMENDED 2026-10-01 by CR-157-BRC10 wave B (the 71-image
//         redesign: four tabs, the drawn tiles, the scheduled-change band)
// screens: RAT-02 (r10) / S11 (A1)
// generated: 2026-08-20 by the CR-013 RAT-02 lane · REBUILT 2026-10-01 by the
//            CR-157-BRC10 wave B lane from images 08–39
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc --noEmit✔ · vitest src/features/rating/✔ · routeBUtilities✔ · G31✔
// exceptions:
//   E3 Duplicate · Edit · Retire keep CR-087 E1's weights (Edit secondary,
//      Retire danger) where the drawing paints Edit as the filled primary —
//      CR-087 E1 is a PO ruling that all five detail screens look alike, and
//      B14 rule 44 gives our UI standard the say over how a button is built.
//   E3 the drawing's Demand *Power factor below* column is not drawn — no
//      stored field holds a threshold (see `UsageChargesTable`).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
