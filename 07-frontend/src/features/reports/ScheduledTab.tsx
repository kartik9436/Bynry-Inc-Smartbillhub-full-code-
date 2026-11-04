// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.5`. Drawing
//          p40 (screen `4·1`) and p41 (screen `4·2` and the consequence
//          block), read as IMAGES per B14 rule 42: the six columns, their
//          order, the toolbar, the pager and the three row actions are taken
//          from those pages and not from a task summary.
// Rules:   B14 rule 44 (the drawing says WHAT and HOW ARRANGED; our UI
//          standard says how it is BUILT and wins) · rule 43 (component, not
//          inline) · rule 40 (page-head title 32px — `PageHeader` owns it) ·
//          rule 33 (LABEL ≤ 3 words · FACT ≤ 6 · RATIONALE zero words) ·
//          rule 31 (no database id is the visible value of a field) · rule 15
//          (row actions are ICONS, capped at two plus an overflow) · rule 16
//          (every list pages — no small-list exemption) · rule 21 (Tailwind
//          only) · NFR-3 (server pagination) · NFR-5 (no hard caps)
// Tests:   07-frontend/src/features/reports/scheduledTab.dom.test.tsx
// Impacts: App.tsx (`/reports/scheduled` stops being a placeholder) ·
//          ReportsTabs.tsx (the tab appears — the hold expires) ·
//          runHistory.dom.test.tsx (its hold case loses `scheduled`)
// ───────────────────────────────────────────────────────
//
// SCREEN `4·1` — *"What goes out on its own, and to whom."*
//
// ════════════════════════════════════════════════════════════════════════════
// THE SIX COLUMNS ARE THE DRAWING'S, IN THE DRAWING'S ORDER
// ════════════════════════════════════════════════════════════════════════════
// p40: **REPORT · HOW OFTEN · NEXT · SEND TO · STATUS · actions**. The task
// summary that sent this lane here said *"Scheduled tab and a schedule opened
// — pause, edit, run now, delete"*, which names the ACTIONS and none of the
// columns — the brief's own warning that a task line is an INDEX and the
// drawing is the specification, proved again.
//
// ════════════════════════════════════════════════════════════════════════════
// THERE IS NO `+ New schedule` BUTTON, AND THAT IS A DECISION
// ════════════════════════════════════════════════════════════════════════════
// p40 PRIMARY ACTION, verbatim: *"None. ⚠ There is deliberately **no + New
// schedule** button here — you schedule FROM the report you are looking at, so
// a create button on this screen would need a report picker that `2·3` gets for
// free."* The server route exists and is what `2·3` calls; what is absent is a
// control HERE. Stated in this file because a route existing is the usual
// reason somebody adds a button to reach it.
//
// ⚠ **SO THE EMPTY STATE MUST NOT OFFER ONE EITHER.** The kit's empty block
// takes a title and a helper and no action, which is the right shape: the
// helper says where schedules come from, in six words (B14 rule 33).
//
// ════════════════════════════════════════════════════════════════════════════
// `HOW OFTEN` IS A WORD AND NEVER A CRON STRING
// ════════════════════════════════════════════════════════════════════════════
// p40 callout ①: *"How often · SIGNED, four values · ⚠ rendered as words,
// never a cron string — 'monthly, on cycle close', not `0 0 1 * *`."* The
// server sends the machine token and the catalogue renders the sentence, in
// eleven languages (TD-16/B8).
//
// ════════════════════════════════════════════════════════════════════════════
// `STATUS` IS DERIVED ON THE SERVER AND THIS SCREEN DOES NOT RE-DERIVE IT
// ════════════════════════════════════════════════════════════════════════════
// p40 callout ③: *"Status · On · Paused · Failing · ⚠ a schedule whose report
// now errors stays in the list marked failing and is not silently dropped."*
// The cell renders `row.status` and asks nothing else. A screen that computed
// *failing* from, say, `next_run_at === null` would be a second opinion about a
// job it cannot see — DEF-104's shape, where four surfaces disagreed about one
// balance.
//
// ⚠ **AND THE PAUSE CONTROL READS `row.status`, NOT A LOCAL `paused` FLAG.**
// After a PATCH the row is refetched and the icon flips because the SERVER
// changed. Keeping a local copy is how a control comes to say *Pause* over a
// schedule the server has already paused.
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ReportSchedule, ScheduleStatus } from "@/api/scheduleEndpoints";
import { getSchedules, runScheduleNow, updateSchedule } from "@/api/scheduleEndpoints";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
// ⚠ **THE GLYPHS COME FROM THE KIT, NOT FROM THIS PAGE.** `G37` refused the
// first draft, which declared both inline: *"The B14 rule 15 vocabulary lives
// in components/icons.tsx and nowhere else — that is DEF-348, where the same
// pencil existed four times under two names."* Neither existed, so both were
// ADDED to the kit, which is what the gate asks for and what B14 rule 43 means
// by a component.
import { PauseIcon, PlayIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { defaultRequestState, isPageSize } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

import { ReportsTabs, SCHEDULED_SEGMENT } from "./ReportsTabs";

/** The three statuses → the kit's semantic tones (A12).
 *
 * ⚠ **STATUS MEANING, NEVER DECORATION.** `paused` is `muted` because `muted`
 * is the kit's *finished, and nothing is owed* — it is not "the grey one" —
 * and `failing` is `danger` because a month-end pack that is not going out is
 * the one thing on this screen somebody has to act on. */
const TONES: Record<ScheduleStatus, StatusTone> = {
  on: "success",
  paused: "muted",
  failing: "danger",
};

const EM_DASH = "—";

export function ScheduledTab(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const toast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [busy, setBusy] = useState<string | null>(null);

  // BR-SHL-011 — the request state lives in the URL, so a bookmark opens on
  // the same page, search and filter. `5·1`'s own posture.
  const query = {
    q: searchParams.get("q") ?? "",
    status: searchParams.get("f.status") ?? "",
    page: Math.max(1, Number(searchParams.get("page") ?? 1) || 1),
  };

  const schedules = useQuery({
    queryKey: ["report-schedules", query.q, query.status, query.page],
    queryFn: () =>
      getSchedules(
        {
          q: query.q,
          status: (query.status || undefined) as ScheduleStatus | undefined,
          page: query.page,
        },
        client,
      ),
    retry: false,
    // The table stays on screen while a filter changes rather than blanking to
    // a skeleton and back — `5·1`'s own reason.
    placeholderData: (previous) => previous,
  });
  const page = schedules.data;

  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["report-schedules"] });

  const pauseOrResume = useMutation({
    mutationFn: (row: ReportSchedule) =>
      updateSchedule(row.id, { enabled: row.status === "paused" }, client),
    onMutate: (row: ReportSchedule) => setBusy(row.id),
    onSettled: () => setBusy(null),
    onSuccess: (updated) => {
      // ⚠ **BOTH DIRECTIONS.** A toast that only ever says *Paused* leaves a
      // clerk who pressed Resume with a sentence contradicting the screen —
      // the defect this phase's proof brief names: a message that stayed on
      // screen after the clerk fixed it.
      toast(
        updated.status === "paused"
          ? t("reports.schedule.paused")
          : t("reports.schedule.resumed"),
      );
      refresh();
    },
  });

  const runNow = useMutation({
    mutationFn: (row: ReportSchedule) => runScheduleNow(row.id, client),
    onMutate: (row: ReportSchedule) => setBusy(row.id),
    onSettled: () => setBusy(null),
    onSuccess: () => {
      // p41 ④ — *"Run now writes a job row, which appears on `5·1` within a
      // second"*. The toast points at HISTORY, because that is where the file
      // will be. `P3.3` fixed exactly this class of toast on the export path.
      toast(t("reports.schedule.runStarted"));
      refresh();
    },
  });

  const config = useMemo<TableConfig<ReportSchedule>>(
    () => ({
      screenId: "4.1",
      getRowId: (row) => row.id,
      searchFields: ["report"],
      searchPlaceholder: "reports.scheduled.search",
      defaultSort: { sort: "next_run_at", dir: "asc" },
      filters: [
        {
          name: "status",
          label: t("reports.scheduled.filter.status"),
          options: (page?.statuses ?? []).map((value) => ({
            value,
            label: t(`reports.scheduled.status.${value}`),
          })),
        },
      ],
      // ⚠ **THE ORDER IS p40's.** It reads as a sentence: what · how often ·
      // when next · to whom · how it is going · and what you can do about it.
      columns: [
        {
          key: "report",
          label: t("reports.scheduled.column.report"),
          locked: true,
          identity: true,
          // ⚠ **THE NAME THE SERVER RESOLVED, NOT `t("reports.card.<key>.name")`.**
          // `P1.1` records what the catalogue lookup cost: a utility that
          // renamed a report could never see its own name, because it cannot
          // edit our locale catalogues.
          cell: (row) => <strong>{row.report}</strong>,
        },
        {
          key: "cadence",
          label: t("reports.scheduled.column.howOften"),
          cell: (row) => <>{t(`reports.schedule.cadence.${row.cadence}`)}</>,
        },
        {
          key: "next_run_at",
          label: t("reports.scheduled.column.next"),
          sortable: true,
          // ⚠ **`null` IS AN EM-DASH AND NEVER THE STRING "null".** A
          // production defect on 2026-08-16 rendered the literal text `null
          // USD` on a tile, which is what a template does with an absent
          // figure. An enabled schedule with no date is ALSO the `failing`
          // row beside it, so the dash is never the only thing said.
          cell: (row) => <>{row.next_run_at === null ? EM_DASH : formatNext(row.next_run_at)}</>,
        },
        {
          key: "recipient_names",
          label: t("reports.scheduled.column.sendTo"),
          // p40 draws *"Dana W. +1"* and *"Finance (4)"* — NAMES, never ids
          // (B14 rule 31). Two names and a count is the drawing's own shape:
          // a cell listing twelve people is a cell nobody reads.
          cell: (row) => <>{describeRecipients(row.recipient_names, t)}</>,
        },
        {
          key: "status",
          label: t("reports.scheduled.column.status"),
          locked: true,
          cell: (row) => (
            <StatusPill tone={TONES[row.status]}>
              {t(`reports.scheduled.status.${row.status}`)}
            </StatusPill>
          ),
        },
        {
          key: "actions",
          label: t("reports.scheduled.column.actions"),
          // p40 callout ④: *"Row actions · pause · edit · run now · B14 rule
          // 15 — icons, capped at two plus an overflow."*
          //
          // ⚠ **TWO ARE DRAWN AND `edit` IS THE ROW ITSELF.** Rule 15 caps a
          // row at two icons plus an overflow; the drawing shows three glyphs
          // and B14 rule 44 gives our standard the win on how a screen is
          // BUILT. Opening `4·2` is what the row already does (`rowHref`), so
          // pause and run-now are the two that need a control of their own and
          // nothing is lost. DIVERGENCE FROM p40, REPORTED.
          cell: (row) => (
            // ⚠ **THE KIT'S OWN `RowActions` / `RowAction`, NOT A HAND-ROLLED
            // `<button>` — AND `G37` IS WHY, TWICE.** The first draft drew two
            // inline `<svg>` elements; the gate refused them and the glyphs
            // moved into `components/icons.tsx`. The SECOND draft imported the
            // glyphs correctly and still put them in plain `<button>`s, and the
            // gate refused that too, by a different clause: a rule-15 glyph in
            // a plain button is the shape the PO ruled on 2026-08-20. Measured:
            // the second draft took G37 from 14 problems to 15 — **the fix made
            // it worse**, which is only visible if you re-run the gate after
            // fixing it rather than assuming the first repair was the repair.
            //
            // `RowAction` brings what the hand-rolled version was quietly
            // missing: `size="row"` geometry, `aria-label` AND `title` from one
            // string, `BR-SHL-025`'s disabled-with-a-reason, and `working`.
            <RowActions>
              <RowAction
                label={
                  row.status === "paused"
                    ? t("reports.scheduled.action.resume")
                    : t("reports.scheduled.action.pause")
                }
                icon={row.status === "paused" ? <PlayIcon /> : <PauseIcon />}
                testId={`schedule-pause-${row.id}`}
                working={busy === row.id}
                onClick={() => pauseOrResume.mutate(row)}
              />
              <RowAction
                label={t("reports.scheduled.action.runNow")}
                icon={<PlayIcon />}
                testId={`schedule-run-${row.id}`}
                working={busy === row.id}
                onClick={() => runNow.mutate(row)}
              />
            </RowActions>
          ),
        },
      ],
      // p41 WRITE SURFACES: *"Detail `4·2` · **Add NOTHING here, by design** —
      // `2·3` · Edit row ✎ → `4·2` · Update pause/resume in place."*
      rowHref: (row) => `?${withOpen(searchParams, row.id)}`,
    }),
    [t, page?.statuses, busy, searchParams, pauseOrResume, runNow],
  );

  /** The ONE writer of this screen's URL state — the table and the filter bar
   *  both go through it, because two copies drift the moment a param is
   *  renamed and only one of them would be tested (`5·1`'s own note). */
  function applyState(next: TableRequestState): void {
    const params = new URLSearchParams();
    if (next.q !== "") params.set("q", next.q);
    if (next.filters.status) params.set("f.status", next.filters.status);
    // A filter change moves the clerk back to page one: page 4 of an
    // unfiltered list is rarely page 4 of a filtered one.
    if (next.page > 1) params.set("page", String(next.page));
    setSearchParams(params);
  }

  const defaults = defaultRequestState(config);
  const state: TableRequestState = {
    ...defaults,
    q: query.q,
    page: query.page,
    // ⚠ **`PageSize` IS A UNION OF FIVE, NOT A NUMBER.** The server's echoed
    // `per` is accepted only when it IS one of them; a cast would compile and
    // put an unlisted size into a control that offers five (`5·1`'s note).
    per: page !== undefined && isPageSize(page.per) ? page.per : defaults.per,
    filters: query.status === "" ? {} : { status: query.status },
  };

  return (
    <div data-screen="4.1">
      <PageHeader kicker={t("reports.kicker")} title={t("reports.scheduled.title")} />
      <p className="mb-6 mt-0 text-body text-neutral-600">{t("reports.scheduled.grain")}</p>
      <ReportsTabs active={SCHEDULED_SEGMENT} />
      <DataTable<ReportSchedule>
        config={config}
        state={state}
        onStateChange={applyState}
        // ⚠ **DECLARING `config.filters` DRAWS NOTHING ON ITS OWN.**
        // `DataTable` renders `filterBarSlot` and never `config.filters` —
        // `5·1`'s first draft declared both filters correctly, `tsc` passed, 24
        // DOM cases passed, and the screenshot showed no filters at all.
        filterBarSlot={
          <FilterBar
            filters={config.filters ?? []}
            state={state}
            onStateChange={(next) => applyState(next)}
          />
        }
        rows={page?.rows ?? []}
        totalRows={page === undefined ? null : page.total}
        loading={schedules.isLoading}
        // ⚠ **A FAILURE MUST NOT RENDER AS AN EMPTINESS — `DEF-REP-6914`,
        // REPRODUCED IN A BROWSER ON THIS SCREEN.** `GET /reports/schedules`
        // answered **500** and this screen drew *"No results match these
        // filters."* over a **Clear filters** link, on a tenant with no
        // filters applied — so a clerk is told their utility has no schedules
        // when the server never answered, and offered a control that clears
        // nothing. `DataTable` has carried a `FailedWithRetry` block
        // (`BR-SHL-020`, A18 §4) since it was written and **this screen never
        // passed it one**: hard-won law 2, and the mirror the register keeps
        // filing — a failure and an absence look identical, and only one of
        // them is worth a clerk's time.
        //
        // ⚠ **MEASURED, BECAUSE A NUMBER IS WHAT MAKES THIS A FINDING AND NOT
        // A TIDY-UP: 3 of the 95 files that mount `DataTable` pass `error`.**
        // The other 92 draw *no results* over a server that failed. This lane
        // fixes its own phase's screen and REPORTS the rest rather than
        // touching 92 files it did not measure one by one.
        error={
          schedules.isError
            ? { onRetry: () => void schedules.refetch() }
            : null
        }
        empty={{
          // Six words, a FACT and not a rationale (B14 rule 33). It says where
          // schedules come from and offers no control, because there is none
          // here to offer (p40 PRIMARY ACTION).
          title: t("reports.scheduled.empty.title"),
          helper: t("reports.scheduled.empty.helper"),
        }}
      />
    </div>
  );
}

/** `2026-10-01T06:00:00Z` → *1 Oct*, the drawing's own shape (p40).
 *
 * ⚠ **NO TIME OF DAY, BECAUSE THE DRAWING SHOWS NONE.** The firing hour is a
 * server-side constant (`schedules.FIRE_AT_HOUR`); putting it on this screen
 * would be a figure the drawing never asked for and one this file would then
 * own a second copy of. */
function formatNext(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime())
    ? EM_DASH
    : when.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** *"Dana W. +1"* — p40's own shape. Two names would not fit the column and
 *  twelve would not be read, so it is ONE name and a count. */
function describeRecipients(
  names: string[],
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const real = names.filter((name) => name !== "");
  if (real.length === 0) return EM_DASH;
  if (real.length === 1) return real[0];
  return t("reports.scheduled.sendToMore", { name: real[0], count: real.length - 1 });
}

/** `4·2` is an ADDRESS and not local state, for `5·2`'s reason: a `<tr>` is
 *  not focusable, so a row whose only affordance is a click is unreachable
 *  without a mouse — and a row a clerk sends a colleague must open the same
 *  schedule. */
function withOpen(params: URLSearchParams, id: string): string {
  const next = new URLSearchParams(params);
  next.set("open", id);
  return next.toString();
}

export default ScheduledTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.5 (05-prototype/09 Reports Build Brief.pdf p40, p41, read as images per B14 rule 42)
// screens: 4·1
// generated: 2026-09-27 by lane REP-P4
// checklist: A=n/a(the backend half is schedules_api.py) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — scheduledTab.dom.test.tsx was run before this file existed and reported `Cannot find module './ScheduledTab'`. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (0) `PauseIcon` and `PlayIcon` were declared INLINE in the first draft and G37 refused them by name; both are now in components/icons.tsx, which is B14 rule 15's vocabulary and rule 43's component · (1) TWO row-action icons are drawn where p40 shows three — B14 rule 15 caps a row at two plus an overflow and rule 44 gives our standard the win on how a screen is BUILT; `edit` is the row itself. DIVERGENCE FROM p40, REPORTED · (2) screen `4·2` (a schedule opened) is NOT built by this lane — see the lane report; the row carries `?open=<id>` so the dialog is an address the day it lands
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
