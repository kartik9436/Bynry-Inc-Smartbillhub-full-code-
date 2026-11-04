// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3-T4 (PO 2026-08-23) — **SET-07D, a NEW screen**: the
//          cycle detail the upgraded prototype added. Five tabs + a Facts rail.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3, §4
// Story:   US-MET-006 (EP-MET-02 §Stories)  Screens: SET-07D
// Rules:   the pre-CR PO ruling (start day · frequency · days to complete; the
//          window is DERIVED, never stored) · D9 (**bill day + due days are the
//          CYCLE's DEFAULTS and the RUN may override them**) · D13 (**no
//          account-level cycle assignment — it derives at bill-run time**) ·
//          BR-MET-076 (the Draft pill) · BR-MET-077 · BR-MET-078 (NO money) ·
//          BR-MET-080 (the coverage flag) · BR-AUD-010 (inline entity audit) ·
//          BR-SHL-011 (the open tab is URL state) · OQ-339 (month-end: UNRULED)
// B14:     rule 1 · 2 · 6 · 18 · 20 · 21 (Tailwind, NO stylesheet class)
// Tests:   RoutesCyclesDetail.test.tsx
// ───────────────────────────────────────────────────────
/**
 * SET-07D — what a cycle IS: three fields about time, the routes it groups, and
 * who it therefore bills.
 *
 * ⚠ **TWO THINGS HERE CONTRADICT THE DRAWING, AND BOTH ARE PO RULINGS**
 * (B17 §3):
 *
 *   · **D9 — the bill day and the due days STAY ON THE CYCLE.** Three screens
 *     in the upgraded prototype carry the footnote *"Bill and due dates belong
 *     to the run, not the cycle"* and that sentence is now **wrong**. The PO,
 *     verbatim: *"when we configure Cycle we are provideing default values;
 *     mostly it wil remain as it is but user can over ride them during
 *     billing"*. So the rail says DEFAULTS-OVERRIDABLE, and the old sentence is
 *     asserted ABSENT by the suite — a copy fix nobody can silently undo.
 *
 *   · **D13 — there is no "Assign a cycle →" and no account-level assignment
 *     anywhere.** The screenshot puts that action on every uncovered row. The
 *     PO ruled: *"Cycles are not directlya ssing to accounts it is derived and
 *     determined at the time of bill run"*. So the Coverage tab shows uncovered
 *     accounts with what they actually LACK — a route — and the remedy is to
 *     route them.
 *
 * ⚠ **THE SCHEDULE TAB DRAWS REAL WINDOWS NOW — AMENDED 2026-08-23 (RC-W3c).**
 * This docstring said the tab *"deliberately prints no date"* because *"nothing
 * serves an occurrence today"*. RC-W2 landed `period_engine` and RC-W3b serves
 * its result on every cycle payload — `proposed_windows`, `next_period`,
 * `next_cycle_date` — so the sentence was false and is gone. A comment claiming
 * a gap that has closed is hard-won law 1 read backwards, and it is exactly how
 * a shipped feature stays invisible.
 *
 * ⚠ **AND THE SCREEN STILL PRINTS NO DATE IT WAS NOT GIVEN.** Every date here
 * is a served one. The three fields (start day · frequency · days to complete)
 * are NOT turned into a window on this screen: `schedule.derive_read_window`'s
 * clamp is a rendering choice for a month somebody already picked, and reusing
 * it to say what a repeating cycle does would answer **OQ-339** by call site.
 * Where the engine refuses, `schedule_gap` says which silence it met and the
 * card renders that silence as a sentence — never a date, never a guess.
 *
 * ⚠ **B14 RULE 21** — Tailwind utilities; no class is added to any stylesheet.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  deleteCycle,
  getBillRuns,
  getCycleCoverage,
  getCycleDetail,
  getRoutes,
} from "@/api/endpoints";
import type {
  BillRunHistoryRow,
  CycleCoverage,
  CycleRow,
  RouteRow,
} from "@/api/endpoints";
import { Button, ButtonLink } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DateCell } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { AuditTab } from "@/features/metering/PremisesDetailPage";
import { premisesDetailPath, unitDetailPath, useRegional } from "@/features/metering/meteringShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ChipList,
  FactsRail,
  RC_DESC,
  RC_MUTED,
  ROUTES_CYCLES_PATH,
  StartDayCell,
  StatedAbsence,
  cycleWizardPath,
  effectiveStartDay,
  frequencyLabel,
  routeDetailPath,
  scheduleGapKey,
  scheduleWarningKey,
  startWindowLabel,
  windowSourceKey,
  windowStatusKey,
} from "./routesCyclesShared";
import { lifecycleTone, orDash } from "./SettingsRoutesCyclesTab";
import { CycleReadFormatPanel } from "@/features/metering/ReadFormatPointer";
import {
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** B17 §4 — the FIVE tabs, in the prototype's own order. */
export const CYCLE_DETAIL_TABS = ["schedule", "routes", "coverage", "runs", "audit"] as const;
export type CycleDetailTab = (typeof CYCLE_DETAIL_TABS)[number];

export function cycleTabFrom(raw: string | null | undefined): CycleDetailTab {
  return CYCLE_DETAIL_TABS.includes(raw as CycleDetailTab) ? (raw as CycleDetailTab) : "schedule";
}

export const cycleDetailQueryKey = (cycleId: string) => ["cycles", "detail", cycleId] as const;
export const cycleCoverageQueryKey = (cycleId: string) =>
  ["cycles", "coverage", cycleId] as const;
export const cycleRoutesQueryKey = (cycleId: string) => ["routes", "of-cycle", cycleId] as const;
export const cycleRunsQueryKey = (cycleId: string) => ["billing", "runs", "of-cycle", cycleId] as const;

/**
 * ⚠ **`monthEndUnruled` WAS DELETED HERE, AND ITS DELETION IS THE POINT.**
 *
 * It was a client-side predicate — *"a start day of 29 or more is affected by
 * OQ-339"* — written when nothing served the engine's verdict. It is exactly
 * the shape this repo has filed before: **a screen constant no server
 * enforces.** It was also WRONG in both directions. A 29th-anchored cycle whose
 * next three windows all fall in months with 29 days is proposed perfectly well
 * by the engine, and the flag would have cried wolf over three real dates; a
 * cycle whose FIRST RUN disagrees with its start day (OQ-340) or whose windows
 * would overlap (OQ-341) proposes nothing at all, and the flag could not see
 * either.
 *
 * The server answers the question now — `schedule_gap.code` names WHICH silence
 * the engine met — and `scheduleGapKey` turns that into a sentence. One
 * authority, and it is the one that owns the calendar.
 */

// ── The screen ─────────────────────────────────────────────────────────────

export interface CycleDetailPageProps {
  client?: ApiClient;
  readOnly?: boolean;
}

export function CycleDetailPage(props: CycleDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const cycleId = params.cycleId ?? "";
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const tab = cycleTabFrom(search.get("tab"));
  const readOnly = props.readOnly ?? false;
  const readOnlyTitle = readOnly ? t("settings.readOnlyReason") : undefined;

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  // ⚠ **`GET /cycles/{id}` EXISTS NOW (RC-W3b), AND THIS STOPPED SCANNING THE
  // WHOLE LIST.** The id route was PATCH+DELETE only, so the detail fetched
  // every cycle in the tenant and picked its row out of the array — correct,
  // and one request that grew with the tenant. The endpoint serves the same
  // `cycle_dict` the list serves, schedule proposal included, so nothing else
  // on this screen changed the day the call moved.
  //
  // A 404 is ABSENT (`null`), not a failure: a deleted cycle and a mistyped id
  // are one answer and A18 §5's "not in this list" state is the honest one.
  const cycleQuery = useQuery({
    queryKey: cycleDetailQueryKey(cycleId),
    queryFn: async (): Promise<CycleRow | null> => {
      try {
        return await getCycleDetail(cycleId, client);
      } catch (error: unknown) {
        if (isApiError(error) && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
    enabled: cycleId !== "",
  });

  const routesQuery = useQuery({
    queryKey: cycleRoutesQueryKey(cycleId),
    queryFn: async (): Promise<RouteRow[]> => {
      const rows = await getRoutes(client);
      return rows.filter((row) => row.cycle_id === cycleId);
    },
    enabled: cycleId !== "" && tab === "routes",
  });

  // BR-MET-080 — how many accounts sit on NO cycle, counting this cycle's
  // routes as covered. The same endpoint SET-07 step 3 uses.
  const coverageQuery = useQuery({
    queryKey: cycleCoverageQueryKey(cycleId),
    queryFn: () => getCycleCoverage(cycleQuery.data?.route_ids ?? [], client),
    enabled: cycleId !== "" && cycleQuery.data != null && tab === "coverage",
  });

  // B17 §4's Runs tab — SERVED since RC-W4b. Scoped to this cycle server-side,
  // and fetched only on the tab that draws it.
  const runsQuery = useQuery({
    queryKey: cycleRunsQueryKey(cycleId),
    queryFn: () => getBillRuns(cycleId, client),
    enabled: cycleId !== "" && tab === "runs",
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCycle(cycleId, client),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cycles"] });
      setConfirmDelete(false);
      fireToast(t("settings.cycles.deleted", { code: cycleQuery.data?.code ?? "" }));
      navigate(tenantPath(ROUTES_CYCLES_PATH));
    },
    onError: (error: unknown) => {
      setConfirmDelete(false);
      setRefusal(refusalOf(error, translate));
    },
  });

  if (cycleQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  if (cycleQuery.data === undefined) {
    if (isPermissionDenied(cycleQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.routes.failedTitle")}
        reason={apiErrorText(cycleQuery.error, translate)}
        onRetry={() => void cycleQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(ROUTES_CYCLES_PATH))}
      />
    );
  }
  const cycle = cycleQuery.data;
  if (cycle === null) {
    // A18 §5 — the row is not in this tenant's list. Not an error state: the
    // list answered, and this id is not in it.
    return (
      <StatedAbsence
        title={t("settings.cycles.detail.notFoundTitle")}
        body={t("settings.cycles.detail.notFoundBody")}
        action={
          <ButtonLink variant="secondary" to={tenantPath(ROUTES_CYCLES_PATH)}>
            {t("settings.tab.routesCycles")}
          </ButtonLink>
        }
      />
    );
  }

  const dash = t("settings.unwiredCount");

  // ── The Facts rail (B17 §4) ──────────────────────────────────────────────
  const facts = [
    { label: t("settings.cycles.detail.fact.cycleNo"), value: cycle.code },
    {
      label: t("settings.cycles.col.frequency"),
      value: frequencyLabel(cycle.frequency, translate, dash),
    },
    // ⚠ OQ-340 — the EFFECTIVE day. A rail that printed `start_day` would
    // disagree with the Schedule tab two panes to its left on exactly the
    // cycles where the difference matters.
    {
      label: t("settings.cycles.col.startDay"),
      value: <StartDayCell cycle={cycle} t={translate} dash={dash} />,
    },
    {
      label: t("settings.cycles.col.daysToComplete"),
      value: orDash(cycle.days_to_complete, dash),
    },
    {
      label: t("settings.cycles.col.routes"),
      value: <ChipList items={cycle.routes} empty={<span className={RC_MUTED}>{dash}</span>} />,
    },
    { label: t("settings.cycles.col.accounts"), value: cycle.accounts },
    // ⚠ D9 — the two DEFAULTS live on the cycle and the run may override them.
    // W5-T2: the second is `due_days`, a COUNT of days after the bill date
    // (BR-BIL-024) — which is the fact billing reads and the one S31 step 1
    // overrides. It was `due_day`, a day-of-month whose column is dropped.
    { label: t("settings.cycles.wizard.billDay"), value: orDash(cycle.bill_day, dash) },
    { label: t("billing.run.field.dueDays"), value: orDash(cycle.due_days, dash) },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        backTo={{ to: tenantPath(ROUTES_CYCLES_PATH), label: t("settings.tab.routesCycles") }}
        kicker={t("settings.cycles.wizard.headKicker")}
        title={cycle.name === null ? cycle.code : `${cycle.code} · ${cycle.name}`}
        status={
          <StatusPill tone={lifecycleTone(cycle.lifecycle_status)}>
            {t(`settings.routes.status.${cycle.lifecycle_status}`)}
          </StatusPill>
        }
        secondaryActions={
          <>
            <Button
              variant="secondary"
              disabled={readOnly}
              title={readOnlyTitle}
              onClick={() => navigate(tenantPath(cycleWizardPath(cycle.id)))}
            >
              {t("settings.cycles.detail.edit")}
            </Button>
            <Button
              variant="danger"
              disabled={readOnly}
              title={readOnlyTitle}
              onClick={() => setConfirmDelete(true)}
            >
              {t("settings.reference.delete")}
            </Button>
          </>
        }
        tabs={CYCLE_DETAIL_TABS.map((id) => ({
          id,
          label: t(`settings.cycles.detail.tab.${id}`),
        }))}
        activeTabId={tab}
        tabsLabel={t("settings.cycles.detail.tabsLabel")}
        onTabSelect={(next) => {
          const params2 = new URLSearchParams(search);
          params2.set("tab", next.id);
          setSearch(params2, { replace: true });
        }}
      />

      <RefusalNotice refusal={refusal} />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <div className="min-w-0 flex-1">
          {tab === "schedule" && <ScheduleTab cycle={cycle} t={translate} dash={dash} />}
          {tab === "routes" && (
            <RoutesTab
              routes={routesQuery.data ?? []}
              loading={routesQuery.isPending}
              t={translate}
              tenantPath={tenantPath}
            />
          )}
          {tab === "coverage" && (
            <CoverageTab
              cycle={cycle}
              coverage={coverageQuery.data ?? null}
              loading={coverageQuery.isPending}
              t={translate}
            />
          )}
          {tab === "runs" && (
            <RunsTab
              runs={runsQuery.data ?? []}
              loading={runsQuery.isPending}
              t={translate}
              tenantPath={tenantPath}
            />
          )}
          {tab === "audit" && (
            // BR-AUD-010 — the change log RENDERS here, cycle-scoped and
            // inline, and links to S61. System and Migration are first-class
            // actors on it: `actorLabel` names a null actor as the system job
            // it is rather than blanking the cell.
            <AuditTab entityType="cycle" entityId={cycle.id} t={translate} regional={{}} />
          )}
        </div>
        <FactsRail
          title={t("settings.cycles.detail.factsTitle")}
          facts={facts}
          // ⚠ D9 — AMENDED so it does not deny the cycle's own date defaults.
          // B17 §4's row for this rail keeps *"Charges and taxes live on the
          // plan, never here"* (BR-MET-078) and drops the screenshot's *"Bill
          // and due dates belong to the run, not the cycle"*, which the PO
          // reversed on the day it was drawn.
          footnote={t("settings.cycles.detail.defaultsFootnote")}
        />
      </div>

      {/* CR-192-BRC10 (MQ-033 task 11) — the cycle's own read format. A cycle
          overrides the service default; a route overrides the cycle. */}
      <CycleReadFormatPanel cycleId={cycle.id} readOnly={readOnly} client={client} />

      {confirmDelete && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete a cycle.
          confirmVariant="danger"
          title={t("settings.cycles.deleteTitle", { code: cycle.code })}
          consequence={t("settings.cycles.deleteBody", { code: cycle.code })}
          confirmLabel={t("settings.cycles.deleteAction", { code: cycle.code })}
          working={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate()}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}

// ── Schedule ───────────────────────────────────────────────────────────────

function ScheduleTab(props: { cycle: CycleRow; t: Translator; dash: string }) {
  const { t, cycle, dash } = props;
  const { timeZone, dateFormat } = useRegional({});
  const startDay = effectiveStartDay(cycle);
  const warningKey = scheduleWarningKey(cycle.schedule_warning?.code);
  return (
    <section className="flex flex-col gap-4">
      <div className="grid gap-4 border border-divider p-4 sm:grid-cols-4">
        {/* ⚠ **OQ-340 — WHAT THE CYCLE DOES, NOT WHAT IS STORED.** PO,
            verbatim: *"A: first window 15–17 Sep (start day becomes
            decorative)"*. The engine follows the first run and does not
            rewrite the column, so on such a cycle this fact reads the
            effective day and the note NAMES the stored one as unused —
            silently swapping the number would hide that the operator's own
            field is being ignored. */}
        <ScheduleFact
          label={t("settings.cycles.detail.starts")}
          value={orDash(startDay.day, dash)}
          note={
            startDay.decorative
              ? t("settings.cycles.startDay.decorative", {
                  effective: startDay.day,
                  stored: startDay.stored,
                })
              : undefined
          }
        />
        <ScheduleFact
          label={t("settings.cycles.detail.daysToComplete")}
          value={orDash(cycle.days_to_complete, dash)}
        />
        <ScheduleFact
          label={t("settings.cycles.detail.window")}
          value={startWindowLabel(cycle, dash)}
          // *"Derived, not stored"* — the upgraded prototype's own product copy
          // (SET-07D.schedule), and it is literally true: `cycle_dict` computes
          // the window from start day + days to complete whenever no legacy
          // date pair is stored, and `read_window_source` says which happened.
          note={t(windowSourceKey(cycle.read_window_source))}
        />
        {/* ⚠ BR-SHL-034 — through `DateCell`, like every other displayed date.
            It rendered the raw ISO string until RC-W3c, which is the one place
            on this screen a date was not the tenant's own format. */}
        <div className="flex flex-col gap-0.5">
          <span className="font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
            {t("settings.cycles.detail.firstRun")}
          </span>
          <span className="text-h4">
            {cycle.first_run_date === null ? (
              dash
            ) : (
              <DateCell
                value={cycle.first_run_date}
                timeZone={timeZone}
                dateFormat={dateFormat}
              />
            )}
          </span>
        </div>
      </div>

      {/* THE FROM-NEXT RULE — B17 §4, verbatim. It is the sentence that stops a
          schedule edit from reading as a threat to bills already issued. */}
      <p className="m-0 border border-divider px-3 py-2.5 text-base" role="note">
        <b>{t("settings.cycles.detail.fromNextTag")}</b>{" "}
        {t("settings.cycles.detail.fromNext")}
      </p>

      {/* ⚠ **THE NEXT THREE WINDOWS — B17 §4, and every date here is SERVED.**
          `period_engine` derives them from start day + frequency + days to
          complete + first run and `cycle_dict` carries the result; this screen
          does no calendar arithmetic of its own, which is what keeps OQ-339 out
          of a call site. Exactly as many rows as the server sent — never a
          fourth, never a placeholder for a window it declined to propose. */}
      {/* ⚠ **OQ-341 — A WARNING BESIDE THE WINDOWS, NEVER INSTEAD OF THEM.**
          The PO amended their own option B inside the ruling: *"you give
          warning and if user override; let them do it"*. So the cycle is
          saved, the overlapping windows below are real, and this says why they
          overlap. Keyed on the server's CODE — its `detail` is English prose
          from a Python module and ten of our eleven locales would not be
          served by it. */}
      {cycle.schedule_warning !== null && warningKey !== null && (
        <p
          className="m-0 border border-divider px-3 py-2.5 text-base"
          role="note"
          data-rc="schedule-warning"
        >
          {t(warningKey, {
            frequency: frequencyLabel(cycle.schedule_warning.frequency, t, dash),
            days: cycle.schedule_warning.days_to_complete,
          })}
        </p>
      )}

      <NextWindows cycle={cycle} t={t} />

      {/* D9 — the two defaults, said as defaults (W5-T2: due DAYS, not a due
          day — see the Facts rail above for why). */}
      <div className="flex flex-col gap-1">
        <p className="m-0 text-base">
          <b>{t("settings.cycles.wizard.billDay")}</b> {orDash(cycle.bill_day, dash)}
          {" · "}
          <b>{t("billing.run.field.dueDays")}</b> {orDash(cycle.due_days, dash)}
        </p>
        <p className={RC_DESC}>{t("settings.cycles.detail.defaultsFootnote")}</p>
      </div>
    </section>
  );
}

function ScheduleFact(props: { label: string; value: string; note?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
        {props.label}
      </span>
      <span className="text-h4">{props.value}</span>
      {props.note !== undefined && <span className={`text-sm ${RC_MUTED}`}>{props.note}</span>}
    </div>
  );
}

// ── The proposal · RC-W2's engine, rendered ────────────────────────────────

/**
 * The **Next three windows** card, and the three silences that replace it.
 *
 * Three states, in the order they are checked, and each is a different sentence
 * about a different thing:
 *
 *   1. **A GAP** — the engine met a case nobody has ruled and proposed nothing.
 *      The card is replaced by one sentence naming the decision the product is
 *      missing. ⚠ **NEVER A DATE HERE.** A cycle anchored on the 31st has no
 *      31 February, and clamp / skip / roll produce different bills; printing
 *      one of them would settle OQ-339 by call site, which is the single thing
 *      the whole stub exists to prevent. The screen never refuses to draw the
 *      cycle — the rest of the tab is untouched by the silence.
 *   2. **NO PROPOSAL AND NO GAP** — a cycle with no first run or no length.
 *      Nothing is wrong and nothing is undecided; there is simply nothing to
 *      propose, and the remedy is an edit.
 *   3. **WINDOWS** — the served occurrences, with the server's own statuses.
 *
 * ⚠ **THE DATES GO THROUGH `DateCell` (BR-SHL-034).** A date-only value put
 * through a browser `Date` shifts by a day for half the world; a second
 * formatter in this file would be the drift that rule exists to stop.
 */
function NextWindows(props: { cycle: CycleRow; t: Translator }) {
  const { t, cycle } = props;
  const { timeZone, dateFormat } = useRegional({});

  if (cycle.schedule_gap !== null) {
    return (
      <StatedAbsence
        title={t("settings.cycles.gap.title")}
        // ⚠ KEYED ON THE CODE, NEVER ON THE SERVER'S `detail`. That field is
        // English prose from a Python module and this product ships eleven
        // languages; rendering it would leave ten of them unserved (G28 also
        // forbids its provenance reaching a utility user).
        body={t(scheduleGapKey(cycle.schedule_gap.code))}
      />
    );
  }

  if (cycle.proposed_windows.length === 0) {
    return (
      <StatedAbsence
        title={t("settings.cycles.detail.noWindowsTitle")}
        body={t("settings.cycles.detail.noWindowsBody")}
      />
    );
  }

  return (
    <section className="flex flex-col gap-2" data-rc="next-windows">
      <p className="m-0 font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
        {t("settings.cycles.detail.nextWindows")}
      </p>
      <div className="overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("settings.cycles.detail.col.occurrence")}</th>
              <th>{t("settings.cycles.detail.col.window")}</th>
              <th>{t("settings.cycles.detail.col.windowStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {cycle.proposed_windows.map((window) => {
              const statusKey = windowStatusKey(window.status);
              return (
                <tr key={`${window.occurrence}-${window.period_start}`} data-rc="window">
                  <td className="tabular-nums">{window.occurrence}</td>
                  <td>
                    <DateCell
                      value={window.period_start}
                      timeZone={timeZone}
                      dateFormat={dateFormat}
                    />
                    {" – "}
                    <DateCell
                      value={window.period_end}
                      timeZone={timeZone}
                      dateFormat={dateFormat}
                    />
                  </td>
                  <td>
                    {/* A status outside the server's two words renders as
                        nothing rather than through a default key — a ninth
                        status is a fact about the data (`frequencyKey`'s own
                        posture, argued there). */}
                    {statusKey === null ? (
                      <span className={RC_MUTED}>{t("settings.unwiredCount")}</span>
                    ) : (
                      <StatusPill tone={window.status === "Next" ? "success" : "neutral"}>
                        {t(statusKey)}
                      </StatusPill>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      </div>
      {/* D8② — the date the dashboard's *"closes in N days"* counts to, shown
          where a person can check it. SERVED, never derived here. */}
      {cycle.next_cycle_date !== null && (
        <p className="m-0 text-base">
          <b>{t("settings.cycles.detail.nextCycleDate")}</b>{" "}
          <DateCell
            value={cycle.next_cycle_date}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
        </p>
      )}
    </section>
  );
}

// ── Routes ─────────────────────────────────────────────────────────────────

function RoutesTab(props: {
  routes: readonly RouteRow[];
  loading: boolean;
  t: Translator;
  tenantPath: (path: string) => string;
}) {
  const { t } = props;
  return (
    <section className="flex flex-col gap-3">
      {/* B17 §4, verbatim — BR-MET-010's consequence, said before it happens.
          ⚠ ABOVE THE LOADING BRANCH, DELIBERATELY. The rule this sentence
          states is true of the tab, not of the rows: hiding it behind a
          skeleton means the one reader who most needs it — someone about to
          move a route — is the one who does not see it. */}
      <p className={RC_DESC}>{t("settings.cycles.detail.moveFootnote")}</p>
      {props.loading ? (
        <LoadingSkeleton variant="table" />
      ) : props.routes.length === 0 ? (
        <StatedAbsence
          title={t("settings.cycles.detail.noRoutesTitle")}
          body={t("settings.cycles.detail.noRoutesBody")}
        />
      ) : (
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th>{t("settings.routes.col.routeNo")}</th>
                <th>{t("settings.routes.col.name")}</th>
                <th>{t("settings.routes.col.members")}</th>
                <th>{t("settings.routes.col.meters")}</th>
                <th>{t("settings.routes.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {props.routes.map((route) => (
                <tr key={route.id}>
                  <td>
                    <InlineLinkTo to={props.tenantPath(routeDetailPath(route.id))}>
                      {route.code}
                    </InlineLinkTo>
                  </td>
                  <td>{route.name ?? ""}</td>
                  <td>
                    {t("settings.routes.membersCell", {
                      premises: route.premises,
                      units: route.units,
                    })}
                  </td>
                  <td>{route.meters}</td>
                  <td>
                    <StatusPill tone={lifecycleTone(route.status)}>
                      {t(`settings.routes.status.${route.status}`)}
                    </StatusPill>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
    </section>
  );
}

// ── Coverage · D13 ─────────────────────────────────────────────────────────

function CoverageTab(props: {
  cycle: CycleRow;
  coverage: CycleCoverage | null;
  loading: boolean;
  t: Translator;
}) {
  const { t, cycle, coverage } = props;
  // Record links (PO 2026-10-19) — each uncovered account's records open.
  const tenantPath = useTenantPath();
  const rows = coverage?.uncovered ?? [];
  return (
    <section className="flex flex-col gap-4">
      {/* The KPI trio. Three counts, no money — a cycle is grouping only.
          ⚠ THE UNCOVERED KPI READS THE COUNT, NEVER `rows.length`: the row list
          is bounded server-side, so a KPI derived from it would stop growing at
          the cap and quietly under-report a utility's real exposure. */}
      <div className="grid gap-4 border border-divider p-4 sm:grid-cols-3">
        <ScheduleFact
          label={t("settings.cycles.detail.kpi.accounts")}
          value={String(cycle.accounts)}
        />
        <ScheduleFact
          label={t("settings.cycles.detail.kpi.routes")}
          value={String(cycle.routes.length)}
        />
        <ScheduleFact
          label={t("settings.cycles.detail.kpi.uncovered")}
          value={
            coverage === null ? t("settings.unwiredCount") : String(coverage.uncovered_accounts)
          }
        />
      </div>

      {/* ⚠ D13 — THE REMEDY IS A ROUTE, NOT AN ASSIGNMENT. The screenshot puts
          an *"Assign a cycle →"* action on every uncovered row. The PO ruled
          that a cycle is DERIVED account → unit → route → cycle at bill-run
          time, so no such action exists and the row names the real lack.

          ── `DEF-MET-5854` · THE LIST IS UTILITY-WIDE AND NOW SAYS SO ───────
          ⚠ **THE DATA WAS NEVER WRONG; THE SCREEN NEVER STATED ITS SCOPE.**
          The human QA team reported *"accounts that were not selected still
          appear"*, and they are right about what they saw: `GET /cycles/
          coverage` asks `derivation.covered_unit_ids`, which walks EVERY
          active route on EVERY non-draft cycle, so this list is *"accounts
          that reach no cycle at all"* — the tenant's whole exposure, and
          BR-MET-080's own question (*"47 accounts unscheduled"*). Measured on
          the demo utility 2026-09-19: `CY-007` (5 routes, 28 accounts) and
          `CY-001` (0 routes, 0 accounts) drew the SAME 26 rows, and so does
          every other cycle. Nothing on the screen said so — two tiles read
          *on this cycle* and the table under them carried no heading at all,
          so a reader takes the rows for this cycle's business.

          ⚠ **A HEADING AND FIVE WORDS REPLACE A 37-WORD PARAGRAPH, AND THE
          DELETION IS THE OTHER HALF OF THE FIX.** `uncoveredLack` opened with
          *"An account reaches a cycle through its unit's route, and that is
          worked out when the bill run happens"* — RATIONALE, which B14 rule 33
          puts at ZERO WORDS ON SCREEN, in two sentences of 18 and 20 words
          against a cap of six. It explained the mechanism and never named the
          scope, which is why a clerk could read it and still misread the
          table. The heading borrows the KPI tile's own wording so the two
          cannot drift apart, and the line under it is one fact and one
          instruction, six words and five. */}
      <div className="flex flex-col gap-0.5">
        <span className="font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
          {t("settings.cycles.detail.uncoveredTitle")}
        </span>
        <p className={RC_DESC}>{t("settings.cycles.detail.uncoveredScope")}</p>
      </div>

      {props.loading ? (
        <LoadingSkeleton variant="table" />
      ) : rows.length === 0 ? (
        <StatedAbsence
          title={t("settings.cycles.detail.allCoveredTitle")}
          body={t("settings.cycles.detail.allCoveredBody")}
        />
      ) : (
        <div className="flex flex-col gap-2">
          <div className="overflow-x-auto">
            <PlainTable>
              <thead>
                <tr>
                  <th>{t("settings.cycles.detail.col.account")}</th>
                  <th>{t("settings.cycles.detail.col.customer")}</th>
                  <th>{t("settings.routes.wizard.col.premise")}</th>
                  <th>{t("settings.routes.detail.col.unit")}</th>
                  {/* ⚠ THE LAST COLUMN IS A FACT, NOT AN ACTION (D13). It names
                      what the account lacks; there is no control beside it and
                      the suite asserts none appears. */}
                  <th>{t("settings.cycles.detail.col.lacks")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.account_id} data-rc="uncovered">
                    <td>
                      {row.account_no === null ? (
                        t("settings.unwiredCount")
                      ) : (
                        <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>{row.account_no}</InlineLinkTo>
                      )}
                    </td>
                    <td>{row.customer_name ?? t("settings.unwiredCount")}</td>
                    <td>
                      {row.premise_no === null ? (
                        t("settings.unwiredCount")
                      ) : (
                        <InlineLinkTo to={tenantPath(premisesDetailPath(row.premises_id))}>{row.premise_no}</InlineLinkTo>
                      )}
                    </td>
                    <td>
                      <InlineLinkTo to={tenantPath(unitDetailPath(row.unit_id))}>{row.unit_label}</InlineLinkTo>
                    </td>
                    <td>
                      <span className={RC_MUTED}>
                        {row.lacks === "route"
                          ? t("settings.cycles.detail.lacks.route")
                          : t("settings.unwiredCount")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
          {/* The server bounds the list. Saying so beats a reader assuming the
              KPI and the table disagree by accident. */}
          {coverage?.truncated === true && (
            <p className={RC_DESC}>
              {t("settings.cycles.detail.uncoveredTruncated", { count: rows.length })}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

// ── Runs ───────────────────────────────────────────────────────────────────

/**
 * B17 §4 — *"Runs (run history, Open in Billing →)"*, and it is a real list now.
 *
 * ⚠ **THIS TAB SAID `GET /billing/runs` DID NOT EXIST UNTIL THE HOUR IT DID.**
 * RC-W4b landed the endpoint on this branch while this screen was shipping, so
 * the stated absence became a false claim — the exact shape this whole wave
 * exists to close, on the screen closing it (hard-won law 1).
 *
 * ⚠ **TWO SERVED FIELDS ARE DELIBERATELY NOT RENDERED**, and following the
 * obvious path with either would ship a visible falsehood:
 *
 *   · **`status` IS A DEAD COLUMN (DEF-602).** `runs.create_run` writes
 *     `"draft"` and nothing in the billing module ever advances it — not issue,
 *     not release, not the pipeline — so every run in the database reads
 *     "draft" for ever, including runs whose bills went out months ago. The
 *     displayed status is COMPOSED here from `issued_at` and `held`, the two
 *     fields with evidence behind them, which is also exactly what the PO's
 *     screenshot draws: *"Issued"*, *"Issued · 5 held"*. The field is served so
 *     the defect stays VISIBLE, not so a screen prints it.
 *   · **`run_no` IS ALWAYS NULL AND STAYS VISIBLY ABSENT (OQ-342).** The
 *     screenshot reads `RUN-0814`; `bill_runs` has no number column and no
 *     bill-run series exists. Deriving one from the date, a per-cycle ordinal
 *     or the uuid would mint a naming grammar by call site — the same refusal
 *     the backend made. The run is identified by its PERIOD ("Jul 2026") until
 *     the PO rules.
 *
 * ⚠ **AND NO MONEY, ANYWHERE** (BR-MET-078). The release total is one join away
 * server-side and is deliberately not exposed; nothing here could print it.
 */
/**
 * The run's status **as this screen composes it**, never as the server stored it.
 *
 * DEF-602: `bill_runs.status` is written `"draft"` at creation and no writer in
 * the billing module ever advances it, so the stored word is the same on a run
 * whose bills went out in March as on one nobody has started. These two served
 * fields DO have evidence behind them — `issued_at` exists only because an
 * invoice was issued, `held` counts unresolved exclusions — and the sentence
 * they compose is the PO's own screenshot: *"Issued"*, *"Issued · 5 held"*.
 */
export function runStatusLabel(run: BillRunHistoryRow, t: Translator): string {
  if (run.issued_at === null) {
    return t("settings.cycles.detail.runStatus.notIssued");
  }
  return run.held > 0
    ? t("settings.cycles.detail.runStatus.issuedHeld", { held: run.held })
    : t("settings.cycles.detail.runStatus.issued");
}

function RunsTab(props: {
  runs: readonly BillRunHistoryRow[];
  loading: boolean;
  t: Translator;
  tenantPath: (path: string) => string;
}) {
  const { t } = props;
  const { timeZone, dateFormat } = useRegional({});
  const openInBilling = (
    <ButtonLink variant="secondary" to={props.tenantPath("/billing/run")}>
      {t("settings.cycles.detail.openInBilling")}
    </ButtonLink>
  );

  if (props.loading) {
    return <LoadingSkeleton variant="table" />;
  }
  if (props.runs.length === 0) {
    return (
      <StatedAbsence
        title={t("settings.cycles.detail.noRunsTitle")}
        body={t("settings.cycles.detail.noRunsBody")}
        action={openInBilling}
      />
    );
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex justify-end">{openInBilling}</div>
      <div className="overflow-x-auto">
        <PlainTable>
          <thead>
            <tr>
              <th>{t("settings.cycles.detail.col.run")}</th>
              <th>{t("settings.cycles.detail.col.period")}</th>
              <th>{t("settings.cycles.detail.col.issued")}</th>
              <th>{t("settings.cycles.detail.col.accounts")}</th>
              <th>{t("settings.cycles.detail.col.runStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {props.runs.map((run) => (
              <tr key={run.id} data-rc="run">
                {/* ⚠ THE RUN IS NAMED BY ITS PERIOD, NOT BY A NUMBER (OQ-342).
                    `run_no` is null on every row and there is no source for
                    one; "Jul 2026" is a real fact about this run and is what a
                    clerk looks a run up by. */}
                <td>
                  {run.period_start === null ? (
                    <span className={RC_MUTED}>{t("settings.unwiredCount")}</span>
                  ) : (
                    <DateCell
                      value={run.period_start}
                      timeZone={timeZone}
                      dateFormat={dateFormat}
                      monthYear
                    />
                  )}
                </td>
                <td>
                  {run.period_start === null || run.period_end === null ? (
                    <span className={RC_MUTED}>{t("settings.unwiredCount")}</span>
                  ) : (
                    <>
                      <DateCell
                        value={run.period_start}
                        timeZone={timeZone}
                        dateFormat={dateFormat}
                      />
                      {" – "}
                      <DateCell
                        value={run.period_end}
                        timeZone={timeZone}
                        dateFormat={dateFormat}
                      />
                    </>
                  )}
                </td>
                <td>
                  {/* ⚠ NOT YET ISSUED IS A STATE, NOT A BLANK. A run that has
                      sent nothing is a run somebody has to finish. */}
                  {run.issued_at === null ? (
                    <span className={RC_MUTED}>{t("settings.cycles.detail.notIssued")}</span>
                  ) : (
                    <DateCell value={run.issued_at} timeZone={timeZone} dateFormat={dateFormat} />
                  )}
                </td>
                {/* Both served counts, so neither is a dark field: how many of
                    the run's accounts actually got a bill. */}
                <td className="tabular-nums">
                  {t("settings.cycles.detail.runBills", {
                    issued: run.bills_issued,
                    accounts: run.accounts,
                  })}
                </td>
                <td>{runStatusLabel(run, t)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </div>
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-029 RC-W3-T4 (B17 §7) — SET-07D, a new screen
// generated: 2026-08-23 by the RC-W3 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (RoutesCyclesDetail.test.tsx)
// [CR-029 RC-W3c 2026-08-23] AMENDED — **THREE OF THE FOUR ABSENCES BELOW CLOSED ON SOMEBODY ELSE'S COMMIT AND ARE DELETED RATHER THAN LEFT STANDING.** RC-W2 landed `period_engine` and RC-W3b mounted the routes: `GET /cycles/{id}` exists (this screen stopped fetching the whole list to find one row), `proposed_windows`/`next_period`/`next_cycle_date`/`schedule_gap` are served, and `/cycles/coverage` returns the uncovered ROWS as well as the count. So the Next-three-windows card is REAL, the uncovered list is REAL, and `monthEndUnruled` — a screen constant no server enforced, wrong in both directions — is DELETED in favour of the engine's own `schedule_gap`. `first_run_date` now renders through `DateCell` (BR-SHL-034); it was the one raw ISO string on this screen.
// [CR-029 RC-W3c follow-up 2026-08-23] AMENDED AGAIN, ONE HOUR LATER: `GET /billing/runs` LANDED (RC-W4b) and the trailer line below said it "does not exist". The Runs tab lists real runs now — Run · Period · Issued · Accounts · Status — and the last stated absence on this screen is gone.
// [CR-029 RC-W6b 2026-08-23] AMENDED — **OQ-340 AND OQ-341 ARE RULED, AND BOTH RULINGS LAND ON THIS SCREEN AS HONESTY WORK.** OQ-340 (*"A: first window 15–17 Sep (start day becomes decorative)"*): the engine anchors on the FIRST RUN and deliberately does NOT rewrite `cycles.start_day`, so the stored day can describe nothing the product does. The Facts rail, the Schedule tab's STARTS fact and its WINDOW fact all render `effective_start_day` (SERVED — `period_engine.effective_start_day`; nothing here computes a day) and SAY that the saved number is not the one used, rather than silently swapping it: hiding the swap would hide that the operator's own field is being ignored. OQ-341 (*"you give warning and if user override; let them do it"* — the PO amended their own option B inside the ruling): `schedule_warning` is rendered as a translated sentence keyed on its CODE, BESIDE the real overlapping windows and never instead of them. RED-first proven by breaking each: `effectiveStartDay` returning the stored day fails four assertions (*expected 'Starts…1…' to contain '15'*, *expected '1–3' to be '15–17'*), and `scheduleWarningKey` returning null fails the warning's.
// exceptions: E3 ⚠ **THE SERVED `status` IS NOT RENDERED, AND THAT IS DELIBERATE (DEF-602).** `runs.create_run` writes `"draft"` and nothing in the module ever advances it, so every run in the database reads "draft" for ever — a Status column drawn from it would title a year of finished work Draft. The displayed status is COMPOSED from `issued_at` and `held`, the two fields with evidence behind them, which is also exactly what the PO's screenshot draws ("Issued", "Issued · 5 held"). The field is served so the defect stays visible, not so a screen prints it · E3 ⚠ **`run_no` IS ALWAYS NULL AND IS LEFT VISIBLY ABSENT (OQ-342).** The screenshot reads `RUN-0814`; `bill_runs` has no number column and no bill-run series exists, and deriving one from the date, an ordinal or the uuid would mint a naming grammar by call site. The run is identified by its PERIOD until the PO rules · E3 the `schedule_gap` codes are rendered as SENTENCES keyed on the code and never as the server's own `detail`, which is untranslated English — ⚠ **and OQ-339/340/341 no longer STAY OPEN: all three were ruled 2026-08-23, `schedule_gap` is served `null` for every cycle a human can save, and what replaced it is `schedule_warning` (rendered) plus `effective_start_day` (rendered). The gap branch is kept as the contract's, not as a statement of silence** · E3 the KPI's uncovered figure reads `uncovered_accounts` and never `uncovered.length`, because the row list is bounded server-side · E3 NO browser walkthrough has happened for this screen (hard-won law 6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
