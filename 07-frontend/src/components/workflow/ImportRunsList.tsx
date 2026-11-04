// ── Trace ──────────────────────────────────────────────
// Change:   `P1.5` of `05-prototype/06 Payments Page Blueprint.pdf` — §03 frame
//           4·1 *Batches*, whose §05 register row reads **"Reuse — the existing
//           imports list, target=payments"** and whose own page says
//           *"Three copies of this list exist — premises, assets and accounts —
//           each querying the same `import-runs` read. **Payments is a fourth
//           caller, not a fourth implementation.**"*
// Screens:  S35 (payments Imports) · S81 (accounts Imports) · PRM-04 · AST-04
// Rules:    BR-MET-096 (ONE ETL runner, `target` parameterised — so this is the
//           ONE `GET /imports` filtered, never a second run list) ·
//           BR-MET-090 (a run's figures are what it RECORDED — never recounted
//           here) · BR-SHL-025 (disabled WITH its reason) · B14 rule 4 ·
//           rules 12–17 · rule 21 (Tailwind utilities, no stylesheet class —
//           listed on `styles/route-b-migrated.txt` in the same commit) ·
//           rule 31 (no database id is the visible value of a field) ·
//           rule 36 (where the kit lacks a piece, ADD IT TO THE KIT) ·
//           rule 43 (a piece of UI is a COMPONENT — standalone code inside a
//           page is not reuse)
// Tests:    src/components/workflow/importRunsList.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THE RUN HISTORY, ONCE, FOR EVERY TARGET THE RUNNER HAS
// ══════════════════════════════════════════════════════════════════════════
// The kit has owned the RUNNER since CR-023 and never owned the LIST the runner
// writes to, so the list was instantiated three times in three screen files —
// `PremisesImportsTab` (PRM-04), `AssetImportsTab` (AST-04) and
// `AccountImportsTab` (S81). Each of those three carries the same paragraph in
// its own trailer saying the extraction is REPORTED rather than taken, because
// the other files belong to other stories. **That is how a repo ends up with
// three answers to one question: every author was right about their own scope.**
//
// The blueprint has now asked for the extraction in terms, so it is taken here
// rather than reported a fourth time.
//
// ⚠ **THIS COMPONENT IS `AccountImportsTab`'s BODY, MOVED — NOT A REDESIGN.**
// That copy was chosen over the other two for a stated reason: it is the one
// whose two known defects are already fixed. `DEF-CUS-5009` split the row
// actions (a run that LOADED something can be rolled back; a run with REJECTED
// rows can be fixed — the other two copies still make them mutually exclusive
// on a field the clerk does not read, so a run that lost four accounts offers
// no path to those four), and `DEF-CUS-5061` scoped the list ON THE SERVER, so
// a busy runner cannot push one target's whole history off the newest page.
//
// ⚠ **PRM-04 AND AST-04 ARE NOT MIGRATED IN THIS COMMIT, AND THAT IS A
// DELIBERATE STOP.** They have DIVERGED on purpose: PRM-04 lists every target
// and sends no scope at all, AST-04 lists three and filters in the browser, and
// both still carry the pre-`DEF-CUS-5009` row actions. Folding them here would
// either carry three behaviours as three flags — three implementations inside
// one file, which is no better — or change two live screens inside a task whose
// subject is payments. `CR-135`'s decision row names the follow-up.
//
// ⚠ **THE FIGURES DRAWN ON 4·1 ARE NOT ALL SERVABLE, AND NONE IS INVENTED
// HERE.** The wireframe draws SOURCE, LABEL and AMOUNT columns and four
// payments-shaped tiles (*Waiting · Applied today · Needs a person · Refused*).
// `ImportRunRow` carries none of those fields — no source card, no label, no
// money — and B14 rule 37 makes a figure in a wireframe an illustration rather
// than a fact to build to. The register's own row for this screen is the
// instruction that governs: *"Reuse — the existing imports list,
// target=payments"*. The gap is FILED, not drawn.
//
// ⚠ **THE COLUMN, STATUS AND ROW-ACTION WORDS ARE READ FROM `metering.imports.*`
// IN HERE, AND THE PER-MODULE SENTENCES ARE PROPS.** That is not a shortcut
// past `G15`: those nine headings and six status pills are the RUNNER's own
// vocabulary and all three existing tabs already read them from that one
// namespace, precisely so a status word cannot be spelled differently on one
// copy and silently answer *none* (`DEF-1702`). What legitimately differs per
// module is the empty state, the rollback sentence and the tiles — *"No account
// imports yet"* and *"No payment imports yet"* are different sentences about
// different nouns — and those arrive already translated from the caller.
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
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
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { formatDate } from "@/components/DateCell";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import { RollBackIcon, WrenchIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
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
} from "@/features/metering/importProgress";
import { useRegional } from "@/features/metering/meteringShared";

import { WORKFLOW_KINDS, rollbackControlIsOffered } from "./kinds";
import type { WorkflowKindId } from "./kinds";

/** The runner's statuses, toned once for every tab that draws them — one
 *  vocabulary for one runner (BR-MET-096 reaching the display layer). */
const STATUS_TONE: Record<string, StatusTone> = {
  extracted: "neutral",
  transformed: "neutral",
  validated: "warning",
  loaded: "success",
  failed: "danger",
  rolled_back: "neutral",
};

const IN_FLIGHT_STATUSES = new Set(["extracted", "transformed", "validated"]);
const FINISHED_STATUSES = new Set(["loaded", "failed", "rolled_back"]);

/** PRM-04's cap, for PRM-04's reason: a list screen must not become a request
 *  storm over forty abandoned runs. */
const IN_FLIGHT_POLL_CAP = 3;

/**
 * Does the SERVER let this run be rolled back at all?
 *
 * ⚠ **ASKED OF THE KIT'S OWN RULE (`P1.22`) RATHER THAN ANSWERED HERE**, so the
 * row action and the runner's stage-5 panel cannot come to disagree about one
 * fact. `import_runs.rollback` refuses `payments` BY NAME and
 * `_load_payments_rows` creates no rollback point, so a `↺` on a payments run
 * would be a live danger-tier button over a door the server keeps shut —
 * hard-won law 2's mirror, and the exact shape that cost the customer portal
 * six of its eight front doors.
 *
 * An unknown target answers `false`: a control offered over a rule we cannot
 * read is the worse of the two failures.
 */
function runCanRollBack(target: string): boolean {
  const kind = WORKFLOW_KINDS[target as WorkflowKindId];
  return kind !== undefined && rollbackControlIsOffered(kind);
}

/**
 * How many rows this list draws before it says it is showing a window.
 *
 * ⚠ **THE SERVER'S OWN 200-ROW SLICE IS GONE (`DEF-CUS-5061`) AND THIS LIST
 * STILL PAGES IN THE BROWSER**, at the top IS-2 page size. The number below is
 * therefore the point at which the KPI tiles stop being totals, which is why it
 * is the same number that silences them. Converting to server paging is its own
 * piece of work: the tiles SUM `rows`, so paging on the server would turn them
 * from totals over every run into totals over one page — a wrong figure where
 * there is currently a truncated list, which is worse than the defect.
 */
const SERVER_CAP = 200;

/** The four tiles, when a tab draws them. Omitted = no strip, which is what
 *  PRM-04 and AST-04 draw today. */
export interface ImportRunsKpiCopy {
  runs: string;
  runsDetail: string;
  rowsLoaded: string;
  rowsLoadedDetail: string;
  rejected: string;
  rejectedDetail: string;
  lastRun: string;
}

export interface ImportRunsListProps {
  /**
   * The targets this list shows.
   *
   * ⚠ **ONE TARGET IS SENT TO THE SERVER AS A SCOPE; MORE THAN ONE IS FILTERED
   * HERE AS WELL.** `DEF-CUS-5061`'s correctness argument, kept: a tenant
   * importing premises heavily could otherwise push every payments run off the
   * newest page, and the tab would read *"you have never imported payments"*
   * while its runs sat in a table the server declined to send.
   */
  targets: readonly string[];
  /** A1's id for the tab. The column preferences are keyed on it, so two tabs
   *  sharing one id would share one clerk's hidden columns. */
  screenId: string;
  /** Distinguishes this tab's react-query cache from its siblings'. */
  cacheScope: string;
  /** Offer a Target filter group over these codes. Omitted on a single-target
   *  tab, where the group would hold one option that changes nothing — B14
   *  rule 9's own objection, and the reason S81 offers none. */
  offerTargets?: readonly string[];
  /** The empty state (B14 rule 17: what is missing, and what fills it). */
  empty: { title: string; helper: string; ctaLabel: string };
  /**
   * What the rollback dialog states as its consequence, already translated with
   * the run's own loaded count.
   *
   * ⚠ **`null` MEANS THIS LIST'S TARGET REFUSES A ROLLBACK AT THE SERVER**, and
   * it is a SECOND lock rather than the lock: `runCanRollBack` reads the kit's
   * own per-target rule and is what actually decides. Two checks, because the
   * cost of getting this wrong is a live danger button over a shut door.
   */
  rollbackConsequence: ((loaded: number) => string) | null;
  kpiCopy?: ImportRunsKpiCopy;
  /** r10's rollback sentence for this module, above the table, and the rule it
   *  tracks. It is a CALLOUT rather than a fifth tile because the window is
   *  policy — no endpoint answers it, and a tile would be a figure nobody
   *  measured. */
  callout?: { text: string; tracks: string };
  /** The tab's own import entries, already guarded by the caller. PRM-04 draws
   *  two, AST-04 three; S81 and S35 draw none, because theirs live in the page
   *  header (one primary per page — B14 rule 4). */
  toolbar?: ReactNode;
  /** BR-SHL-025: null = allowed; a string disables the write controls WITH it. */
  writeBlockedReason: string | null;
  /** The ONE door onto the runner, called by the empty state's action. */
  onImport: () => void;
  client?: ApiClient;
}

export function ImportRunsList(props: ImportRunsListProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;

  // DEF-SHL-3964 — the tenant's own pair, published by the shell. It was the
  // SEED pair ("UTC" + "MM/DD/YYYY") on the honest reasoning that nothing
  // passed these tabs regional props; both halves were right and the conclusion
  // was a plausible wrong date on every import row.
  const { timeZone, dateFormat } = useRegional({});
  const when = (iso: string | null) =>
    iso === null ? "—" : formatDate(iso, timeZone, dateFormat, true);

  const [rollbackTarget, setRollbackTarget] = useState<ImportRunRow | null>(null);
  const rollback = useMutation({
    mutationFn: (runId: string) => rollbackImport(runId, client),
    onSuccess: () => {
      setRollbackTarget(null);
      void runs.refetch();
    },
    onError: () => setRollbackTarget(null),
  });

  const progressByRun = useRef(new Map<string, ImportProgress>());

  // `DEF-1702`'s shared vocabulary (`importProgress.tsx`), one definition for
  // every copy of this table.
  const statusOptions = useMemo(() => importStatusFilterOptions(t), [t]);
  const offerTargets = props.offerTargets;
  const targetOptions = useMemo(
    () => (offerTargets === undefined ? [] : importTargetFilterOptions(t, offerTargets)),
    [t, offerTargets],
  );

  const config: TableConfig<ImportRunRow> = {
    screenId: props.screenId,
    getRowId: (row) => row.id,
    filters: [
      { name: "status", label: t("metering.imports.col.status"), options: statusOptions },
      ...(targetOptions.length > 0
        ? [
            {
              name: "target",
              label: t("metering.imports.filter.target"),
              options: targetOptions,
            },
          ]
        : []),
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
        // ONE target on a scoped tab, so the SOURCE cell is the file name
        // alone. AST-04 folds a target beneath it because three targets share
        // its table and a meters run must be tellable from a devices run —
        // that variant comes with AST-04 when it migrates.
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
        // COLUMN.** The pill still reads *File read* for two minutes while a
        // 50,000-row file is mapped — the status is written when the stage
        // COMMITS — and the line beneath it is the only thing on this screen
        // that can say otherwise.
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
        /**
         * ⛔ **`DEF-CUS-5009` — THE TWO ACTIONS ANSWER TWO DIFFERENT QUESTIONS
         * AND MUST NOT GO BACK TO BEING ONE TERNARY.**
         *
         * They read `row.status === "loaded" ? rollback : fixRows`, so the two
         * were mutually exclusive on a field the clerk does not read, and the
         * `rejected` COUNT — the only thing *Fix the rejected rows* is about —
         * played no part. A run finishes `loaded` whether or not it rejected
         * anything, so a clerk looking at the run that lost four rows was
         * offered no path to those four.
         *
         * Each action asks its own question of its own field: roll back is for
         * a run that LOADED something, the fix is for a run with REJECTED rows.
         * A loaded run with four rejects is offered both — reverse all of it,
         * or repair the four — and an in-flight run with nothing rejected is
         * offered neither, because there is nothing to do to it yet.
         *
         * ⏳ The fix itself is still HELD: reopening a finished run is
         * `PATCH /imports/{run}/rows/{n}` on the workflow's own stage 3, which
         * a table row cannot re-enter. It renders disabled WITH its reason.
         */
        cell: (row) => (
          <RowActions>
            {row.status === "loaded" &&
              props.rollbackConsequence !== null &&
              runCanRollBack(row.target) && (
                <RowAction
                  label={t("metering.imports.action.rollback")}
                  icon={<RollBackIcon />}
                  danger
                  reason={props.writeBlockedReason}
                  onClick={() => setRollbackTarget(row)}
                />
              )}
            {row.rejected > 0 && (
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

  const targets = props.targets;
  const scopedTarget = targets.length === 1 ? targets[0] : undefined;

  const runs = useQuery<ImportRunListResult>({
    // ⚠ `state.filters` IN THE KEY — react-query caches on the key alone, so
    // without it a ticked box would re-render and be served the previous
    // unfiltered response: a control that visibly does nothing.
    queryKey: ["import-runs", props.cacheScope, state.filters],
    queryFn: () =>
      getImportRuns(
        client,
        scopedTarget === undefined ? state.filters : { ...state.filters, target: scopedTarget },
      ),
    retry: false,
  });

  /** The server serves EVERY target's runs in one list; a tab is the filtered
   *  view of it, so the one runner keeps one list endpoint (BR-MET-096).
   *
   *  ⚠ **THIS FILTER STAYS EVEN ON A SERVER-SCOPED TAB.** It is a no-op over an
   *  already-scoped list, and it is what keeps the tab honest if the param is
   *  ever dropped — `BR-SHL-011` ignores an undeclared `f.<name>` SILENTLY. */
  const rows = useMemo(
    () => (runs.data?.rows ?? []).filter((row) => targets.includes(String(row.target))),
    [runs.data, targets],
  );

  const inFlightIds = useMemo(
    () =>
      rows
        .filter((row) => IN_FLIGHT_STATUSES.has(row.status))
        .slice(0, IN_FLIGHT_POLL_CAP)
        .map((row) => row.id),
    [rows],
  );

  /** PRM-04's two stopping rules, kept verbatim: only the RUN's own terminal
   *  status stops a poll — never a poll count, never the gauge's `null` (no
   *  stage deferred YET) or `done` (only that STAGE is over). Both were tried
   *  and both made the table stop watching a run that was still going. */
  const details = useQueries({
    queries: inFlightIds.map((runId) => ({
      queryKey: ["import-run", runId, props.cacheScope],
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
    // list answer — the loop `settled` exists to prevent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedMarks]);

  // ── The KPI strip ─────────────────────────────────────────────────────────
  // Counted ONLY over a run list that both ARRIVED and is COMPLETE. A failed
  // read leaves `rows` empty and "0 runs" is a claim; a list at the window cap
  // is a partial sum and "1,645 rows loaded" would be a floor printed as a
  // total. Either way every tile shows the quiet dash instead.
  const kpisComplete = runs.isSuccess && rows.length < SERVER_CAP;
  const dash = <span data-kpi-absent="true">—</span>;
  const count = (value: number) => (kpisComplete ? <span>{value.toLocaleString()}</span> : dash);
  // BR-MET-090: `loaded` and `rejected` are what each run RECORDED. Summed,
  // never recounted against today's rows.
  const totalLoaded = rows.reduce((sum, row) => sum + row.loaded, 0);
  const totalRejected = rows.reduce((sum, row) => sum + row.rejected, 0);
  // `run_list` orders newest-first, so the most recent run is the head of the
  // filtered list — no re-sorting, and no date arithmetic in this file.
  const lastRun = rows.length > 0 ? rows[0] : null;

  const from = (state.page - 1) * state.per;
  const page = rows.slice(from, from + state.per);

  return (
    <>
      {props.kpiCopy !== undefined && (
        <div className="mb-5">
          <KPIStrip
            loading={runs.isPending}
            kpis={[
              {
                id: "runs",
                label: props.kpiCopy.runs,
                value: count(rows.length),
                detail: props.kpiCopy.runsDetail,
              },
              {
                id: "rows_loaded",
                label: props.kpiCopy.rowsLoaded,
                value: count(totalLoaded),
                detail: props.kpiCopy.rowsLoadedDetail,
              },
              {
                id: "rejected",
                label: props.kpiCopy.rejected,
                value: count(totalRejected),
                detail: props.kpiCopy.rejectedDetail,
              },
              {
                id: "last_run",
                label: props.kpiCopy.lastRun,
                value:
                  kpisComplete && lastRun !== null ? <span>{when(lastRun.started_at)}</span> : dash,
                detail:
                  kpisComplete && lastRun !== null && lastRun.file_name !== null
                    ? lastRun.file_name
                    : undefined,
              },
            ]}
          />
        </div>
      )}

      {props.callout !== undefined && (
        <div
          className="mb-3 border border-l-[3px] border-divider border-l-accent-500 bg-surface px-3 py-2 text-base"
          role="note"
          data-tracks={props.callout.tracks}
        >
          {props.callout.text}
        </div>
      )}

      {props.toolbar}

      <DataTable<ImportRunRow>
        config={config}
        // G45's other half: a filter DECLARED and not rendered is DEF-1701, a
        // different defect from the one the declaration closes.
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
          // fills it.
          title: props.empty.title,
          helper: props.empty.helper,
          ctaLabel: props.empty.ctaLabel,
          ctaReason: props.writeBlockedReason,
          onCta: props.onImport,
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
          consequence={props.rollbackConsequence?.(rollbackTarget.loaded) ?? ""}
          confirmLabel={t("metering.import.rollbackConfirm")}
          working={rollback.isPending}
          onConfirm={() => rollback.mutate(rollbackTarget.id)}
          onCancel={() => setRollbackTarget(null)}
        />
      )}
    </>
  );
}

export default ImportRunsList;

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p14 `P1.5` · §03 frame 4·1 (p061–p062) and §05's register row, both rendered at 2.0
// generated: 2026-09-22 by LANE P1-C
// checklist: A✔ B=n/a(no new endpoint) C✔ D=n/a E✔(two callers on its first commit — S81 and S35) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/components/workflow/importRunsList.dom.test.tsx · G31 (listed on src/styles/route-b-migrated.txt in this commit) · routeBUtilities.test.ts · G37 (icon row actions with accessible names)
// exceptions: E3 PRM-04 and AST-04 are NOT migrated onto this component in this commit — they have diverged on purpose and both predate `DEF-CUS-5009`; the follow-up is named in CR-135's decision row · E3 the SOURCE cell draws the file name alone: the per-target sub-line AST-04 folds beneath it arrives with AST-04 · E3 the 4·1 wireframe's SOURCE, LABEL and AMOUNT columns and its four payments-shaped tiles are NOT drawn — `ImportRunRow` serves none of those fields and the register's own row for this screen says *"Reuse — the existing imports list, target=payments"*; the gap is filed rather than invented
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
