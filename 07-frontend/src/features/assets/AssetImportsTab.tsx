// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 AST-W3-T4 (B16 §4.7: "The Imports tab itself (AST-04) is a
//           run-history table … a filtered view of the runner's import_runs
//           for the three assets targets"). Screens: AST-04.
// Rules:    BR-AST-046 (tab-named workflow imports — the three buttons) ·
//           BR-MET-090 (a run's figures are what it RECORDED — never
//           recounted here) · BR-AST-045's rollback callout, r10 verbatim:
//           "Meters already carrying reads are kept and reported" ·
//           BR-SHL-025 (disabled-with-reason) · B14 rule 4 (`↑` imports) ·
//           B14 rule 15 (icon row actions) · B14 rule 21 (Tailwind)
// Impacts:  AssetRegistryPage.tsx (mounts this on ?tab=imports) ·
//           GET /imports · GET /imports/{id} · POST /imports/{id}/rollback
// ───────────────────────────────────────────────────────
// AST-04 — the Imports tab of the Assets page.
//
// ⚠ **THE PRM-04 PATTERN, APPLIED TO AST-04 — deliberately the same shape as
// `PremisesImportsTab`** (columns, status tones, the capped in-flight polling
// with its two hard-won stopping rules, the ConfirmDialog'd rollback), with
// two differences and only two: the run list is FILTERED to the three assets
// targets, and the toolbar carries r10's THREE tab-named import buttons. The
// shared shape is a candidate for extraction into components/workflow the day
// a third module grows an imports tab — REPORTED rather than refactored here,
// because PremisesImportsTab is another story's file and CR-028's scope is
// the assets surface.
//
// ⚠ **THE ROLLBACK CALLOUT IS r10's OWN SENTENCE AND IT IS NOW TRUE**: the
// backend's assets rollback keeps a read-carrying meter and reports it by
// count on the receipt and by sentence on its row (AST-W3-T4's test walks
// exactly that).
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
} from "@/features/metering/importProgress";
import { GuardedButton, useRegional } from "@/features/metering/meteringShared";

import { ASSET_IMPORT_TARGETS } from "./AssetImportWorkflow";

/** The runner's statuses, toned exactly as PRM-04 tones them — one vocabulary
 *  for one runner (BR-MET-096 reaching the display layer). */
const STATUS_TONE: Record<string, StatusTone> = {
  extracted: "neutral",
  transformed: "neutral",
  validated: "warning",
  loaded: "success",
  failed: "danger",
  rolled_back: "neutral",
};

/** The three assets targets, in tab order — the list filter AND the buttons. */
const ASSETS_TARGETS = [
  ASSET_IMPORT_TARGETS.meters,
  ASSET_IMPORT_TARGETS.sub_meters,
  ASSET_IMPORT_TARGETS.behind_the_meter,
] as const;

const IN_FLIGHT_STATUSES = new Set(["extracted", "transformed", "validated"]);
const FINISHED_STATUSES = new Set(["loaded", "failed", "rolled_back"]);
/** PRM-04's cap, for PRM-04's reason: a list screen must not become a
 *  request storm over forty abandoned runs. */
const IN_FLIGHT_POLL_CAP = 3;
/** `run_list` serves at most 200 rows and no server paging. Stated. */
const SERVER_CAP = 200;

export interface AssetImportsTabProps {
  /** BR-SHL-025: null = allowed; a string disables the controls WITH it. */
  writeBlockedReason: string | null;
  /** Navigate to one target's workflow (the tab-named entry, BR-AST-046). */
  onImport: (target: string) => void;
  client?: ApiClient;
}

export function AssetImportsTab(props: AssetImportsTabProps) {
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

  // CR-045 wave D · D.13 — one vocabulary, shared with S81 and PRM-04
  // (`importProgress.tsx`), so a status word cannot be spelled differently on
  // one of the three copies of this table and silently answer "none".
  const statusOptions = useMemo(() => importStatusFilterOptions(t), [t]);
  const targetOptions = useMemo(
    () => importTargetFilterOptions(t, ASSETS_TARGETS),
    [t],
  );

  const config: TableConfig<ImportRunRow> = {
    // AST-04 is r10's own badge; A1 allocates no id for the tab (the S61–S90
    // range is reserved) — the same posture PRM-04's config records.
    screenId: "AST-04",
    getRowId: (row) => row.id,
    // ── CR-045 wave D · D.13 (DEF-1702) ──────────────────────────────────
    // ⚠ **APPLIED BY `run_list`, IN THE QUERYSET, BEFORE ITS 200-ROW CAP.**
    // This tab pages in the browser over whatever the endpoint returns, so a
    // status narrowed HERE would narrow the newest 200 runs of every target
    // rather than the tenant's assets runs — a subset of a subset. The
    // endpoint has taken a `params` argument since CR-023 and ignored it;
    // this wave gave it the leg, and this is the half that uses it.
    //
    // The Target group offers THIS TAB'S THREE targets and not all six:
    // B16 §4.7 scopes AST-04 to the assets targets, so offering `premises`
    // would be a checkbox that can only ever return nothing.
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
        // ⛔ DEF-3158 — was `row.run_no ?? row.id.slice(0, 8)`, so a run whose
        // number had not been minted showed eight characters of its database id
        // in the RUN column. B14 rule 31, ratified 2026-08-31: a truncation is
        // the same breach as a full uuid — it is still the database's value and
        // a person still cannot use it. Where no human-facing number exists the
        // field says so in words, and the internal value rides on `title` as
        // the evidence a support engineer needs.
        cell: (row) =>
          row.run_no ?? <span title={row.id}>{t("metering.imports.runNotNumbered")}</span>,
      },
      {
        key: "file_name",
        label: t("metering.imports.col.source"),
        // The SOURCE cell carries the target beneath the file name so a
        // meters run and a devices run are tellable apart at a glance.
        cell: (row) => (
          <>
            <span>{row.file_name ?? "—"}</span>
            <span className="block text-xs text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
              {t(`assets.imports.target.${row.target}`)}
            </span>
          </>
        ),
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
            {/* r10's two row actions, exactly as PRM-04 draws them: `↺ Roll
                back` LIVE on a loaded run (through the ConfirmDialog, IS-6),
                `🔧 Fix rows` disabled with its reason on the rest (the runner
                has no resume path — the inline fix lives on the workflow's
                own stage 3). */}
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

  // ⚠ **`state.filters` IS IN THE KEY, AND IT HAS TO BE.** react-query caches
  // on the key alone: without it, ticking a status would edit the request
  // state, re-render, and serve the previous unfiltered response from cache —
  // a filter that visibly does nothing. Same law as `routesPageKeyFor`.
  const runs = useQuery<ImportRunListResult>({
    queryKey: ["import-runs", "assets", state.filters],
    queryFn: () => getImportRuns(client, state.filters),
    retry: false,
  });

  /** The server serves EVERY target's runs in one list; AST-04 is the
   *  filtered view B16 §4.7 names — the filter is this line and nothing
   *  else, so the one runner keeps one list endpoint. */
  const rows = useMemo(
    () =>
      (runs.data?.rows ?? []).filter((row) =>
        (ASSETS_TARGETS as readonly string[]).includes(row.target),
      ),
    [runs.data],
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
   *  stage deferred YET) or `done` (only that STAGE is over). */
  const details = useQueries({
    queries: inFlightIds.map((runId) => ({
      queryKey: ["import-run", runId, "assets-table"],
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
    // `runs` is a stable query object; re-running on it would refetch on
    // every list answer — the loop `settled` exists to prevent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedMarks]);

  const from = (state.page - 1) * state.per;
  const page = rows.slice(from, from + state.per);

  return (
    <>
      {/* r10 AST-04's ROLLBACK callout, verbatim in the catalogue: a run
          rolls back as one unit for 30 days, and meters already carrying
          reads are KEPT and reported. True since this lane's backend half. */}
      <div
        className="mb-3 border border-l-[3px] border-divider border-l-accent-500 bg-surface px-3 py-2 text-base"
        role="note"
        data-tracks="BR-AST-045"
      >
        {t("assets.imports.rollbackCallout")}
      </div>

      {/* BR-AST-046: the THREE tab-named entries onto the one runner —
          meters PRIMARY (the tab's own noun leads, r10's emphasis). */}
      <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
        <GuardedButton
          label={t("assets.action.import.behind_the_meter")}
          reason={props.writeBlockedReason}
          onClick={() => props.onImport(ASSET_IMPORT_TARGETS.behind_the_meter)}
        />
        <GuardedButton
          label={t("assets.action.import.sub_meters")}
          reason={props.writeBlockedReason}
          onClick={() => props.onImport(ASSET_IMPORT_TARGETS.sub_meters)}
        />
        <GuardedButton
          label={t("assets.action.import.meters")}
          reason={props.writeBlockedReason}
          variant="primary"
          onClick={() => props.onImport(ASSET_IMPORT_TARGETS.meters)}
        />
      </div>

      <DataTable<ImportRunRow>
        config={config}
        // CR-045 wave D · D.13 — the slot G45 counts against the declaration
        // above. Declared-and-unrendered is DEF-1701, a different defect and
        // one this wave must not create while closing DEF-1702.
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
          title: t("assets.imports.empty.title"),
          helper: t("assets.imports.empty.helper"),
          ctaLabel: t("assets.action.import.meters"),
          ctaReason: props.writeBlockedReason,
          onCta: () => props.onImport(ASSET_IMPORT_TARGETS.meters),
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
          consequence={t("assets.imports.rollback.consequence", {
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

export default AssetImportsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-028/B16@2026-08-22 §4.7 (AST-04) · BR-AST-045/046 · AST-W3-T4
// generated: 2026-08-22 by the CR-028 AST-W3 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetRegistry.test.tsx — the imports-tab cases) · g37 (icon row actions with accessible names)
// exceptions: E2 this is deliberately PRM-04's shape re-instantiated (same columns, same poll caps and stopping rules, same rollback dialog) rather than an extraction of PremisesImportsTab into the shared kit — that file is another story's and CR-028's scope is the assets surface; the extraction is REPORTED as the third-consumer trigger · E3 the run list is the ONE `GET /imports` filtered client-side to the three assets targets (B16 §4.7 calls AST-04 "a filtered view"); a server-side `?target=` filter on the list endpoint is REPORTED, not invented · E3 `Fix rows` stays disabled-with-reason on non-loaded runs: the runner's inline fix (PATCH /imports/{run}/rows/{n}) lives on the workflow's stage 3, and a table row cannot re-enter a stage · E3 regional formatting uses the SEED defaults (meteringShared's stated posture)
// ──────────────────────────────────────────────────────────
