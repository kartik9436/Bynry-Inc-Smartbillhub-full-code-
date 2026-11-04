// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-020 (metering — the auto-archival job: 2-yr hot window →
//           cold storage, 7-yr retention, AUTOMATIC and never manual) ·
//           US-AUD-007 (audit — the same job over `audit_log`, "one mechanism,
//           two tables")   Screens: S61 (entered from the audit-log viewer)
// Rules:    BR-MET-055 (2 yr hot → archive, 7 yr total retention; an AUTOMATIC
//           scheduled job, NEVER manual, audited) · BR-AUD-012 (the identical
//           rule for `audit_log`; NFR-28 "matches reads pattern") · BR-AUD-002
//           (archival MOVES partitions; it never UPDATEs or DELETEs a row) ·
//           NFR-25 (financial tables are NEVER pruned) · BR-AUD-009 (System
//           Admin + Executive) · BR-SHL-012 (the A18 states, composed) ·
//           BR-SHL-034 (one date formatter) · CLAUDE.md law 1 (a field claiming
//           a guarantee is not the guarantee)
// Tests:    07-frontend/src/features/audit/RetentionRunsPage.test.tsx ·
//           06-backend/tests/test_us_met_020_tc_archival.py (the read half)
// ───────────────────────────────────────────────────────
// "Has data retention ever run?" — the question nobody could answer.
//
// The surface-debt register named it on 2026-08-16: US-MET-020's
// `archive_job_runs` ledger *"appears in `apps/audit/migrations/0004_archive_
// job_runs.py`, in `apps/audit/management/commands/archive_partitions.py` and
// in `core/archival.py`, and in no `api.py` anywhere: no selector, no endpoint,
// no viewer, so an operator cannot see whether retention has ever run."* A
// utility carrying a seven-year obligation had a job, a ledger, a schedule and
// no way to look at any of it.
//
// FOUR THINGS THIS SCREEN SAYS THAT A NAIVE ONE WOULD NOT:
//
//   1. **"Never run" is a finding, not a blank.** The server sends
//      `has_ever_run: false` with a reason, and this renders the reason. An
//      empty table would look like a screen that had not loaded.
//
//   2. **"Archived" does not mean off-site, and the screen says so.** Nothing
//      in this repo registers a cold-store shipper, so every run records
//      `shipped: false` with `shipper_absent`. Archived means DETACHED,
//      MANIFESTED and STILL QUERYABLE under RLS. Hard-won law 1: without this
//      line an operator could tell an auditor the data had left the building.
//
//   3. **There is no Run-now button, and the absence is explained.** BR-MET-055
//      and BR-AUD-012 both say "never manual" and the API defines a `get` and
//      nothing else. A screen that simply lacked the control would send someone
//      hunting for it; this one states that the schedule is the whole surface.
//
//   4. **It never sums row counts into a headline.** Each partition carries its
//      own count. "1,438,204 rows archived" implies a denominator this product
//      cannot state, and a compliance figure whose denominator is unknown is
//      worse than the per-partition list it replaced.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getRetentionRuns } from "@/api/endpoints";
import type { RetentionRun, RetentionTableStatus } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AUDIT_ROUTE, DASHBOARD_ROUTE, RETENTION_ROUTE } from "./AuditLogPage";
import { useRegional } from "@/features/metering/meteringShared";

// ── Pure pieces (provable without a browser or a network) ─────────────────

// `RETENTION_ROUTE` lives in AuditLogPage.tsx and is re-exported here so a
// caller can import the page and its path from one place. It is DECLARED there
// because this file already depends on that one, and a constant travelling back
// the other way is a module cycle — which rendered the whole audit screen blank
// in the bundled SPA while every unit test passed. See its docstring.
export { RETENTION_ROUTE };
export const retentionQueryKey = ["retention", "runs"] as const;

/** The friendly name of a table an operator is being told about. */
export function tableLabelKey(tableName: string): string {
  return `audit.retention.table.${tableName}`;
}

/**
 * One table's headline: the DATE it last ran, or the reason it never has.
 *
 * Returns a KEY plus params, never a sentence — the date itself renders through
 * the shared formatter (BR-SHL-034) beside it, so this answers only "which of
 * the two things is true".
 */
export function lastRunKey(row: RetentionTableStatus): string {
  return row.has_ever_run ? "audit.retention.lastRan" : "audit.retention.neverRan";
}

/**
 * The two figures a compliance question actually turns on, per table.
 *
 * PARTITIONS, not rows. Each partition's row count is on its own line below;
 * adding them into one number would state a total whose denominator — of how
 * many rows were eligible? — this product cannot compute, and an unanchored
 * compliance figure is worse than the list it summarises.
 */
export function retentionTiles(tables: readonly RetentionTableStatus[], t: Translator): KpiTile[] {
  return tables.map((row) => ({
    id: row.table_name,
    label: t(tableLabelKey(row.table_name)),
    value: row.has_ever_run ? row.partitions_archived : "—",
    detail: row.has_ever_run
      ? t("audit.retention.tile.archived", { runs: row.runs })
      : t("audit.retention.tile.never"),
  }));
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface RetentionRunsPageProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

export function RetentionRunsPage(props: RetentionRunsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  // DEF-SHL-3964 — this used to spell its own copy of the seed default, one
  // layer below the resolver. Same defect, same cure: the tenant's own setting.
  // (The first wording of this comment named a prop in backtick-quoted code and
  // G13's scanner read the COMMENT as a prop reference — ten false positives.
  // A comment that contains code-shaped text is code to anything that greps.)
  const { timeZone, dateFormat } = useRegional(props);

  const query = useQuery({
    queryKey: retentionQueryKey,
    queryFn: () => getRetentionRuns(client),
  });

  if (query.data === undefined && query.isError) {
    if (isPermissionDenied(query.error)) {
      // Same gate as the rest of the module (BR-AUD-009: System Admin +
      // Executive). A18 §6 renders INSTEAD of the screen.
      return (
        <PermissionDenied
          helper={t("audit.retention.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    return (
      <FailedWithRetry
        title={t("audit.retention.failedTitle")}
        reason={apiErrorText(query.error, translate)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(AUDIT_ROUTE))}
      />
    );
  }

  const status = query.data?.status;
  const runs = query.data?.runs ?? [];

  return (
    <div className="px-4 pt-6 pb-8">
      <PageHeader
        title={t("audit.retention.title")}
        secondaryActions={
          <Button variant="secondary" onClick={() => navigate(tenantPath(AUDIT_ROUTE))}>
            {t("audit.retention.backToLog")}
          </Button>
        }
      />

      {query.isPending || status === undefined ? (
        <LoadingSkeleton variant="kpi" />
      ) : (
        <>
          {/* The law an operator is being held to, from the server. Printed
              rather than hardcoded: a run in 2031 must still be readable
              against the bound that applied when it ran. */}
          <p className="mt-1 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("audit.retention.law", {
              hot: status.hot_window_months,
              years: status.retention_years,
            })}
          </p>

          <KPIStrip kpis={retentionTiles(status.tables, translate)} />

          {/* Per table, in words: ran on this date, or has never run and why. */}
          <ul className="m-0 mt-3 flex list-none flex-col gap-1 p-0 text-md leading-prose">
            {status.tables.map((row) => (
              <li key={row.table_name}>
                <strong>{t(tableLabelKey(row.table_name))}</strong>{" "}
                {row.has_ever_run && row.last_run_date !== null ? (
                  <>
                    {t(lastRunKey(row))}{" "}
                    <DateCell
                      value={row.last_run_date}
                      timeZone={timeZone}
                      dateFormat={dateFormat}
                    />
                    {row.last_run_note !== null && ` — ${row.last_run_note}`}
                  </>
                ) : (
                  <span className="font-semibold text-warning-700">{t(lastRunKey(row))}</span>
                )}
              </li>
            ))}
          </ul>

          {/* CLAUDE.md law 1, on the screen. Without it a green "archived"
              column reads as "the data is off-site", which it is not. */}
          {!status.off_site_shipping && (
            <p
              className="m-0 mt-3 max-w-[78ch] border-l-[3px] border-l-warning-700 px-3 py-2 text-base leading-prose"
              role="status"
            >
              {t("audit.retention.notOffSite")}
            </p>
          )}

          {/* BR-MET-055 / BR-AUD-012 "never manual". The absence of a Run-now
              control is a RULE, so it is explained rather than left as a gap
              somebody files a defect about. */}
          <p className="met-panel-hint">
            {t("audit.retention.neverManual", { schedule: status.schedule })}
          </p>

          <RunHistory runs={runs} t={translate} timeZone={timeZone} dateFormat={dateFormat} />
        </>
      )}
    </div>
  );
}

function RunHistory(props: {
  runs: readonly RetentionRun[];
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = props;
  if (props.runs.length === 0) {
    return (
      <p
        className="text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] italic"
        data-audit="empty"
        role="status"
      >
        {t("audit.retention.noRuns")}
      </p>
    );
  }
  return (
    <div className="mt-4">
      <h2>{t("audit.retention.historyTitle")}</h2>
      {props.runs.map((run) => (
        <section key={run.id} className="mb-3 border-b border-b-divider pb-3">
          <p className="m-0 mb-1 flex flex-wrap items-baseline gap-2">
            <strong>{t(tableLabelKey(run.table_name))}</strong>{" "}
            {run.run_date !== null && (
              <DateCell
                value={run.run_date}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            )}{" "}
            <span className="text-sm tracking-label uppercase text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {t(`audit.retention.status.${run.status}`, { defaultValue: run.status })}
            </span>
          </p>
          {run.note !== null && <p className="met-panel-hint">{run.note}</p>}
          {run.archived.length === 0 && run.purged.length === 0 ? (
            // A no-op run is a LAWFUL outcome (US-MET-020 TC-5) and is recorded
            // on purpose. Rendering it as an empty section would make a correct
            // run look like a broken one.
            <p className="met-panel-hint">{t("audit.retention.noOp")}</p>
          ) : (
            <ul className="m-0 pl-4 text-base leading-note [font-feature-settings:'tnum'_1]">
              {run.archived.map((entry) => (
                <li key={`a-${entry.partition}`}>
                  {t("audit.retention.archivedLine", {
                    partition: entry.partition ?? "—",
                    rows: entry.row_count ?? "—",
                  })}
                  {/* The one thing this tenant may learn about who else was in
                      the partition: whether THEY were. The list itself never
                      leaves the server (see apps/audit/selectors). */}
                  {entry.includes_this_tenant === true && (
                    <span className="font-semibold"> {t("audit.retention.includedYou")}</span>
                  )}
                </li>
              ))}
              {run.purged.map((entry) => (
                <li key={`p-${entry.partition}`} className="text-danger-700">
                  {t("audit.retention.purgedLine", {
                    partition: entry.partition ?? "—",
                    rows: entry.row_count ?? "—",
                  })}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-020@f4a1c02 (EP-MET-03 archival story; co-packet US-AUD-007@6b3d915 — EP-AUD-03)
// generated: 2026-08-16 by story-coder v1 (surface-debt lane — the audit line's unreachable story)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(N/A — not a 🔒 path: this screen READS a run record and can trigger nothing; the partition DDL stays in core/archival.py, which is HUMAN-REVIEW-PENDING in its own right)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (see the lane report) · G15 11 catalogues, identical key sets✔ · G13 unwired-props✔
// exceptions: E3 there is deliberately NO "Run now" control and NO way to skip or bring a run forward — BR-MET-055 and BR-AUD-012 both say "never manual", `core.archival.run_archival` refuses any caller without the scheduler token, and `GET /retention/runs` defines a `get` and nothing else so every write verb 405s structurally. The screen EXPLAINS the absence rather than leaving it as a gap somebody files a defect about · E3 row counts are shown PER PARTITION and are never summed into a headline: a total implies a denominator ("of how many eligible rows?") this product cannot state, and an unanchored compliance figure is worse than the list it replaces · E3 the "not off-site" caveat is rendered from the SERVER's `off_site_shipping: false` rather than hardcoded — the day a deployment registers a cold-store shipper the caveat disappears on its own · E4 the run history is not paginated: `archive_job_runs` gains at most one row per table per month, so seven years of a two-table obligation is under 200 rows · E4 this is a ROUTE (`/audit-log/retention`) rather than a tab on S61, because a compliance answer is a thing an operator sends as a link into an audit ticket
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
