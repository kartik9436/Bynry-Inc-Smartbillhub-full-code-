// ── Trace ──────────────────────────────────────────────
// Story:    (none yet — hard-won law 8 is REPORTED here, see the trailer)
//           Change:  CR-023 P0 (the tab) · CR-023 W2 (the run table) ·
//           CR-026 (an in-flight run made legible on the come-back-later
//           surface)
//           Screens: PRM-04 (r10 badge; A1 allocates no id — reported)
// Rules:    BR-SHL-044 (the page head belongs to the shell, not to a tab) ·
//           BR-SHL-025 (a control this role may not use is DISABLED with its
//           reason, never hidden) · BR-MET-090 (a run's figures are what it
//           RECORDED — this table never recounts) · BR-MET-099 (rollback
//           deactivates, skips the occupied, and never deletes) ·
//           B14 rule 4 (`↑` is the import verb) · B14 rule 15 (row actions are
//           ICONS with tooltips) · B14 rule 21 (Tailwind, no new stylesheet) ·
//           BR-MET-085 (the counts on screen are the SERVER's) · BR-MET-102
//           (a running import cannot be cancelled — no cancel action is
//           offered on a row either)
// ───────────────────────────────────────────────────────
// PRM-04 — the Imports tab.
//
// ⚠ **THE RUN TABLE IS BUILT, AND THE STATED ABSENCE CAME OFF IN THE SAME
// COMMIT (G38).** This file carried an `ArrivesWith` note tracking `DEF-520`
// that said, correctly, that a nine-column list of recorded runs needs a run to
// record and the product recorded none. `GET /imports` now serves
// `import_runs.run_list` — nine columns, newest first — so the note is gone and
// the table is here. **A note that outlives its reason is the same defect as an
// empty table pretending to be data** (`DEF-445`), which is why G38 counts them.
//
// ⚠ **THE ROLLBACK ACTION IS DRAWN AND DISABLED, AND IT SAYS WHY
// (`DEF-541`).** r10 puts a `↺` on every row and prints *"A run can be rolled
// back as one unit for 30 days"* — and today NO run can be rolled back at all:
// `import_runs._run()` refuses every run whose status is `loaded`, which is the
// only status a rollback applies to, so `rollback()`'s own guard is dead code.
// The route is mounted and correct; the engine beneath it refuses. So the icon
// is present with its reason (BR-SHL-025) rather than deleted — a missing
// control teaches the operator nothing, and a live one that always 409s teaches
// them the product is broken. The day `DEF-541` lands, this becomes a call.
//
// ⚠ **THE DEFINITION LINE IS r10's AND IT IS NOW TRUE.** It used to be replaced
// by a "what an import does today" note, because the sentence promises a
// receipt and a 30-day rollback that nothing could honour. Stage 4 records both
// (`import_runs.ROLLBACK_DAYS`), so r10's own words go back — except the
// rollback half, which stays out until `DEF-541` makes it honest. Copy what is
// true; state what is not.
//
// ⚠ **THE TWO BUTTONS ARE DUPLICATED ON PURPOSE.** The page head already
// carries `↑ Import premises` on this tab, and r10 draws BOTH import buttons
// again in this toolbar with the emphasis reversed — units secondary, premises
// PRIMARY (`SMARTBillHub.dc.html` line 673). B15 §9.8: *"Do not 'fix' r10's
// duplicated import buttons."* Copy it; do not tidy it.
//
// ⚠ **CR-026 — THIS IS THE COME-BACK-LATER SURFACE, AND UNTIL NOW IT COULD NOT
// SAY WHETHER ANYTHING WAS STILL HAPPENING.** A 50,000-row file leaves the
// browser and runs for minutes in a worker; the operator is told, on the
// workflow screen, that they may close the page and look here. What they found
// was a row reading *"File read"* — because `import_runs` writes the new status
// when a stage COMMITS, and the stage holds that row locked for its whole
// duration. So the gauge is read per run from `GET /imports/{id}` and drawn
// under the status pill.
//
// ⚠ **AND IT STOPS ASKING, TWO DIFFERENT WAYS.** A run whose `progress` comes
// back `null` was never deferred and is asked exactly once; a run whose gauge
// reaches `done` or `failed` has nothing left to say. Neither bound is a timer
// or a poll count — a list screen that polls forever is the defect this shape
// is most likely to introduce, so the stopping condition is the SERVER's own
// terminal state and the candidate set is capped at the newest three.
//
// ⚠ **NO CANCEL ROW ACTION, AND NOT A DISABLED ONE (`BR-MET-102`, PO
// 2026-08-22, verbatim: *"No"*).** The row's two actions are still r10's `↺
// Roll back` and `🔧 Fix rows`. Rollback IS the answer to a wrong file — it is
// what the ruling points at — and it is already live here.
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getImportRun,
  getImportRuns,
  isImportStageFinished,
  rollbackImport,
} from "@/api/endpoints";
import type {
  ImportProgress,
  ImportRunListResult,
  ImportRunRow,
  ImportValidateResult,
} from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { formatDate } from "@/components/DateCell";
import { RollBackIcon, WrenchIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";

import {
  IMPORT_POLL_INTERVAL_MS,
  ImportProgressCell,
  importStatusFilterOptions,
  importTargetFilterOptions,
} from "./importProgress";
import { GuardedButton, useRegional } from "./meteringShared";

/**
 * The five statuses `models.IMPORT_RUN_STATUSES` allows, toned.
 *
 * ⚠ `rolled_back` IS NOT A FAILURE and is not toned as one. A rollback is a
 * deliberate act by a System Admin that the product supports; colouring it red
 * beside `failed` would tell an operator they broke something.
 */
const STATUS_TONE: Record<string, StatusTone> = {
  extracted: "neutral",
  transformed: "neutral",
  validated: "warning",
  loaded: "success",
  failed: "danger",
  rolled_back: "neutral",
};

/** `run_list` serves at most 200 rows and no server paging, so the page is cut
 *  here. Stated rather than silent: a utility with 201 runs sees 200. */
const SERVER_CAP = 200;

/**
 * **CR-026 — the statuses a run can still be MOVING in.** `models.
 * IMPORT_RUN_STATUSES` has six; `loaded`, `failed` and `rolled_back` are ends.
 *
 * ⚠ A run's STATUS does not change while a deferred stage runs — the stage
 * holds `SELECT … FOR UPDATE` on that row for its whole duration and writes the
 * new status at commit. That is precisely why `import_run_progress` is a
 * separate table on a separate connection, and it is why an in-flight run looks
 * *"extracted"* here for the two minutes it is being mapped. The gauge is the
 * only thing that can say otherwise, so these three statuses are the rows worth
 * asking about.
 */
const IN_FLIGHT_STATUSES = new Set(["extracted", "transformed", "validated"]);

/** The mirror set, named separately because it is what STOPS the polling. */
const FINISHED_STATUSES = new Set(["loaded", "failed", "rolled_back"]);

/**
 * How many non-terminal runs this tab will poll at once.
 *
 * ⚠ **A CAP, BECAUSE A LIST SCREEN MUST NOT BECOME A REQUEST STORM.** A tenant
 * that abandoned forty half-finished runs would otherwise open this tab and
 * issue forty detail reads. Three is the newest three, which is every run a
 * person can plausibly be waiting on — `BR-MET-096`'s runner is one workflow
 * per operator, and the list is newest-first.
 *
 * The second bound is in the query itself and it is the RUN, not the gauge: a
 * poll stops when the run's own status becomes terminal.
 *
 * ⚠ **AND IT MAY NOT STOP ON AN ABSENT OR A FINISHED GAUGE, WHICH IS WHAT THE
 * FIRST DRAFT DID AND WHAT A BROWSER FOUND.** Both stops look right and both
 * are wrong for the same reason — the gauge is written PER STAGE, one row per
 * run, overwritten in place. A run sitting at `extracted` with the Imports tab
 * already open has NO gauge yet; stopping there means the tab never notices the
 * transform that starts four seconds later, and that is exactly what happened
 * on the walkthrough: three runs polled once each, `progress: null`, and a
 * 6,000-row import ran to completion beside a table that never moved. The
 * mirror mistake is stopping on `done`, which would freeze the tab on
 * *transform · 100%* for the whole of validate. Only the RUN can say it has
 * finished.
 */
const IN_FLIGHT_POLL_CAP = 3;

export interface PremisesImportsTabProps {
  /** BR-SHL-025: null = allowed; a string disables the control WITH it. */
  writeBlockedReason: string | null;
  onImportPremises: () => void;
  onImportUnits: () => void;
  client?: ApiClient;
}

export function PremisesImportsTab(props: PremisesImportsTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;

  // DEF-SHL-3964 — was the SEED pair ("UTC" + "MM/DD/YYYY"), on the honest
  // reasoning that nothing passes this tab regional props and an unwired prop is
  // dead UI. Both halves were right; the conclusion was a plausible wrong date
  // on every import row. The shell publishes the tenant's own pair now, so the
  // tab needs no prop and no default.
  const { timeZone, dateFormat } = useRegional({});
  const when = (iso: string | null) =>
    iso === null ? "—" : formatDate(iso, timeZone, dateFormat, true);

  // DEF-552 — the row's `↺ Roll back` commits ONLY through the ConfirmDialog
  // (IS-6): the dialog asks with the run's own figures, the mutation commits,
  // and the table re-reads so the row shows the SERVER's new status.
  const [rollbackTarget, setRollbackTarget] = useState<ImportRunRow | null>(null);
  const rollback = useMutation({
    mutationFn: (runId: string) => rollbackImport(runId, client),
    onSuccess: () => {
      setRollbackTarget(null);
      void runs.refetch();
    },
    onError: () => setRollbackTarget(null),
  });

  /**
   * **CR-026 — the live gauge per run, filled in below and READ by the STATUS
   * cell.** A ref rather than state because it is derived, every render, from
   * queries declared further down: the cell closures below do not run until
   * `DataTable` renders them, which is after the assignment.
   *
   * A run with no entry draws exactly what it drew before this change.
   */
  const progressByRun = useRef(new Map<string, ImportProgress>());

  // CR-045 wave D · D.15 — the shared vocabulary (`importProgress.tsx`), one
  // definition across all three copies of this table.
  const statusOptions = useMemo(() => importStatusFilterOptions(t), [t]);
  const targetOptions = useMemo(() => importTargetFilterOptions(t), [t]);

  const config: TableConfig<ImportRunRow> = {
    // A1 allocates no id for PRM-04 (hard-won law 8, reported in the trailer),
    // so the column preference is keyed on r10's own badge.
    screenId: "PRM-04",
    getRowId: (row) => row.id,
    // ── CR-045 wave D · D.15 (DEF-1702) ──────────────────────────────────
    // ⚠ **THIS TAB IS THE ONE THAT LISTS ALL SIX TARGETS, SO ITS TARGET GROUP
    // OFFERS ALL SIX.** AST-04 offers its own three and S81 offers none; the
    // difference is what each tab actually shows, not a preference.
    //
    // And it matters MOST here, for the reason the comment on the query below
    // gives: `run_list` caps at 200 and this tab pages in the browser, so on a
    // tenant with a busy runner the older half of any one target was simply
    // not on the page. Filtering in the queryset is what makes the cap mean
    // "the newest 200 PREMISES runs" instead of "the newest 200 runs, of which
    // some are premises".
    filters: [
      { name: "status", label: t("metering.imports.col.status"), options: statusOptions },
      { name: "target", label: t("metering.imports.filter.target"), options: targetOptions },
    ],
    defaultSort: { sort: "started", dir: "desc" },
    columns: [
      {
        key: "run_no",
        label: t("metering.imports.col.run"),
        identity: true,
        // ⛔ DEF-3158 — was `row.run_no ?? row.id.slice(0, 8)`. B14 rule 31: a
        // truncated database id is the same breach as a full uuid. The absence
        // is stated in words and the id moves to `title` as evidence.
        cell: (row) =>
          row.run_no ?? <span title={row.id}>{t("metering.imports.runNotNumbered")}</span>,
      },
      {
        key: "file_name",
        label: t("metering.imports.col.source"),
        cell: (row) => row.file_name ?? "—",
      },
      {
        key: "started",
        label: t("metering.imports.col.started"),
        cell: (row) => when(row.started_at),
      },
      { key: "run_by", label: t("metering.imports.col.by"), cell: (row) => row.run_by ?? "—" },
      { key: "rows_in", label: t("metering.imports.col.in"), numeric: true },
      { key: "loaded", label: t("metering.imports.col.loaded"), numeric: true },
      { key: "rejected", label: t("metering.imports.col.rejected"), numeric: true },
      {
        key: "status",
        label: t("metering.imports.col.status"),
        // ⚠ **CR-026 PUTS THE GAUGE UNDER THE PILL RATHER THAN IN A TENTH
        // COLUMN.** r10 draws nine columns here and B15 §9.8 says copy them
        // rather than tidy them, so an in-flight run is made legible INSIDE the
        // column that is already about where the run has got to. The pill still
        // reads "File read" for two minutes while a 50,000-row file is mapped
        // — the status is written when the stage COMMITS — and the line beneath
        // it is the only thing on this screen that can say otherwise.
        cell: (row) => {
          const progress = progressByRun.current.get(row.id) ?? null;
          return (
            <>
              <StatusPill tone={STATUS_TONE[row.status] ?? "neutral"}>
                {t(`metering.imports.status.${row.status}`)}
              </StatusPill>
              {progress !== null && (
                <span className="mt-1 block text-xs">
                  <ImportProgressCell progress={progress} />
                </span>
              )}
            </>
          );
        },
      },
      {
        key: "actions",
        label: t("metering.imports.col.actions"),
        cell: (row) => (
          <RowActions>
            {/* r10 draws `↺ Roll back` on a loaded run and `🔧 Fix rows` on a
                failed one — two different actions on two different states,
                copied rather than collapsed into one. The rollback is LIVE
                since `DEF-552` (its disabled reason outlived the `DEF-541`
                fix by a day); it commits only through the ConfirmDialog
                (IS-6). Fix rows stays disabled with its reason: a run cannot
                be re-entered at stage 3 (no resume path — reported). */}
            {row.status === "loaded" ? (
              <RowAction
                label={t("metering.imports.action.rollback")}
                icon={<RollBackIcon />}
                danger
                onClick={() => setRollbackTarget(row)}
              />
            ) : (
              <RowAction
                label={t("metering.imports.action.fixRows")}
                icon={<WrenchIcon />}
                reason={t("metering.imports.fixRowsBlocked")}
                onClick={() => undefined}
              />
            )}
          </RowActions>
        ),
      },
    ],
  };

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  // ⚠ `state.filters` IN THE KEY — react-query caches on the key alone, so
  // without it a ticked box would re-render and be served the previous
  // unfiltered response: a control that visibly does nothing.
  const runs = useQuery<ImportRunListResult>({
    queryKey: ["import-runs", state.filters],
    queryFn: () => getImportRuns(client, state.filters),
    retry: false,
  });

  /**
   * ⚠ **THE SERVER SORTS AND DOES NOT PAGE, SO THE PAGE IS CUT HERE.**
   * `run_list` answers the newest 200 runs in one array with no `q`, no `sort`
   * and no page window — it is a nine-column list, not a list ENDPOINT in the
   * BR-SHL-011 sense. Rather than pretend otherwise, this slices what arrived
   * and hands `DataTable` the real total, so the pager reads truthfully over
   * what the product actually has. A screen that asked for `?page=3` would get
   * page 1 three times.
   */
  const rows = runs.data?.rows ?? [];

  /* ── CR-026 · the come-back-later surface, made live ────────────────────── */

  /**
   * The runs worth asking *"how far?"* about — non-terminal, newest first,
   * capped. `GET /imports` serves no `progress` (it is `run_list`, nine
   * columns), so the gauge has to be read one run at a time from the poll
   * surface `GET /imports/{id}`.
   */
  const inFlightIds = useMemo(
    // `runs.data` and not `rows`: the `?? []` fallback is a NEW array on every
    // render, so memoising on it would rebuild the query list every time and
    // `react-hooks/exhaustive-deps` says so out loud.
    () =>
      (runs.data?.rows ?? [])
        .filter((row) => IN_FLIGHT_STATUSES.has(row.status))
        .slice(0, IN_FLIGHT_POLL_CAP)
        .map((row) => row.id),
    [runs.data],
  );

  /**
   * ⚠ **EACH OF THESE STOPS WHEN THE RUN SAYS IT IS FINISHED, AND ON NOTHING
   * ELSE.** Not a poll count, not a timeout, and — see `IN_FLIGHT_POLL_CAP` —
   * not on the gauge, whose `null` means *"no stage has deferred YET"* and
   * whose `done` means *"this STAGE is over"*. Both were tried and both made
   * the table stop watching a run that was still going.
   */
  const details = useQueries({
    queries: inFlightIds.map((runId) => ({
      // Not the workflow page's key: that one is scoped to a stage this tab
      // knows nothing about, and sharing it would let one screen's cache
      // answer the other screen's question.
      queryKey: ["import-run", runId, "table"],
      retry: false,
      refetchInterval: (query: { state: { data?: ImportValidateResult } }) => {
        const status = query.state.data?.status;
        return status !== undefined && FINISHED_STATUSES.has(status)
          ? false
          : IMPORT_POLL_INTERVAL_MS;
      },
      queryFn: () => getImportRun(runId, client),
    })),
  });

  const liveProgress = new Map<string, ImportProgress>();
  inFlightIds.forEach((runId, index) => {
    const progress = details[index]?.data?.progress ?? null;
    if (progress !== null) liveProgress.set(runId, progress);
  });
  progressByRun.current = liveProgress;

  /**
   * When a stage finishes, the RUN ROW has changed — its status, its counts —
   * and the list is a snapshot taken before that. So the list is re-read, ONCE
   * per finished stage: `settled` remembers which `run:stage:state` marks have
   * already triggered a refetch, so the effect cannot loop on its own result.
   */
  const settled = useRef(new Set<string>());
  const finishedMarks = inFlightIds
    .map((runId, index) => {
      const progress = details[index]?.data?.progress ?? null;
      return progress !== null && isImportStageFinished(progress)
        ? `${runId}:${progress.stage}:${progress.state}`
        : null;
    })
    .filter((mark): mark is string => mark !== null)
    .join("|");

  useEffect(() => {
    if (finishedMarks === "") return;
    let fresh = false;
    for (const mark of finishedMarks.split("|")) {
      if (settled.current.has(mark)) continue;
      settled.current.add(mark);
      fresh = true;
    }
    if (fresh) void runs.refetch();
    // `runs` is a stable query object; re-running on it would refetch on every
    // list answer, which is the loop `settled` exists to prevent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedMarks]);

  const from = (state.page - 1) * state.per;
  const page = rows.slice(from, from + state.per);

  return (
    <>
      {/* ⚠ **r10's DEFINITION LINE IS NOT DRAWN HERE, AND THE FIRST DRAFT DREW
          IT TWICE.** `premisesStripTabs` already hands the page head
          `metering.premises.explainer.imports` — *"Every bulk load of premises
          and units, with the receipt."* — so a second copy in the tab body put
          the same sentence on the screen twice in slightly different words.
          BR-SHL-044: the head belongs to the shell. Found by reading the
          RENDERED markup (hard-won law 6); tsc, vitest and every gate were
          green over it. */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <GuardedButton
          label={t("metering.units.action.import")}
          reason={props.writeBlockedReason}
          onClick={props.onImportUnits}
        />
        {/* PRIMARY here and SECONDARY in the head — r10's reversed emphasis,
            copied rather than tidied (B15 §9.8). */}
        <GuardedButton
          label={t("metering.premises.action.import")}
          reason={props.writeBlockedReason}
          variant="primary"
          onClick={props.onImportPremises}
        />
      </div>

      <DataTable<ImportRunRow>
        config={config}
        // CR-045 wave D · D.15 — G45's other half (see the declaration above).
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(config.filters ?? [])}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={page}
        totalRows={runs.isSuccess ? rows.length : null}
        loading={runs.isPending}
        error={runs.isError ? { onRetry: () => void runs.refetch() } : null}
        empty={{
          // BR-SHL-012 + B14 rule 17: what is missing, and the action that
          // fills it. ⚠ This empty state is now HONEST — it appears when the
          // tenant has run no import, which is a fact the product can now
          // establish. Before the run table existed it would have been a claim.
          title: t("metering.imports.empty.title"),
          helper: t("metering.imports.empty.helper"),
          ctaLabel: t("metering.premises.action.import"),
          ctaReason: props.writeBlockedReason,
          onCta: props.onImportPremises,
        }}
      />

      {rows.length >= SERVER_CAP && <Note>{t("metering.imports.cap", { cap: SERVER_CAP })}</Note>}

      {rollbackTarget !== null && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): roll back an import.
          confirmVariant="danger"
          title={t("metering.imports.rollback.title", {
            run: rollbackTarget.run_no ?? rollbackTarget.id,
          })}
          consequence={t("metering.imports.rollback.consequence", {
            loaded: rollbackTarget.loaded,
          })}
          confirmLabel={t("metering.import.rollbackConfirm")}
          working={rollback.isPending}
          onConfirm={() => rollback.mutate(rollbackTarget.id)}
          onCancel={() => setRollbackTarget(null)}
        />
      )}
    </>
  );
}

export default PremisesImportsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-023 P0 (B15 §3.3 · §7A · §8 Q1 · §9.8) + CR-023 W2 (B15 §12 row
//         10, the run list; r10 PRM-04 screenshot supplied by the PO 2026-08-21)
// generated: 2026-08-21 by the CR-023 P0-P2 lane · AMENDED 2026-08-22 by the
//         CR-023 W2 stage-4/5 lane (the run table; the DEF-520 stated absence
//         removed in the same commit, G38)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest PremisesPage.test.tsx (the imports-tab cases)✔ · g31 (no
//         new stylesheet class) · g37 (both row actions are icons with
//         accessible names, from rule 15's vocabulary) · g38 (the DEF-520
//         stated absence is REMOVED here, not re-tracked)
// exceptions: E3 **NO STORY OWNS THIS SCREEN — hard-won law 8, reported rather
//         than invented.** CR-023 §11 lists PRM-04 as new and the epics have not
//         been re-authored; A1 allocates no id for it either · E3 the table's
//         SEARCH, filter chips and column chooser come from the shared
//         DataTable while `GET /imports` supports none of `q`, `sort` or paging
//         — the rows are sliced on the client and the total is the real one, so
//         the pager cannot lie; a server-side list contract for this endpoint is
//         REPORTED, not invented here · E3 both row actions are DISABLED WITH
//         THEIR REASON: rollback by `DEF-541` (no run can be rolled back at
//         all), Fix rows because the runner has no resume path · E3 regional
//         formatting uses the SEED defaults (`meteringShared`'s stated posture)
//         because nothing passes this tab regional props and an unwired prop is
//         dead UI (G13) · E2 r10's duplicated import buttons are reproduced
//         verbatim including the reversed emphasis (B15 §9.8) · E3 **CR-026's
//         gauge is drawn UNDER r10's STATUS pill rather than in a tenth
//         column**, because r10 draws nine columns and B15 §9.8 says copy them
//         rather than tidy them — the fact belongs to the column that is
//         already about where the run has got to · E3 `GET /imports` serves no
//         `progress`, so the gauge costs one detail read per in-flight run,
//         capped at the newest three; a `progress` field on the list payload
//         would remove the cap entirely and is REPORTED, not built here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
