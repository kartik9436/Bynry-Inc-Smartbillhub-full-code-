// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 (`P3.1`, `P3.2`,
//          `P3.4`). Drawing p39 (screen `5·1`) and p42–p43 (screen `5·2`),
//          read as images per B14 rule 42.
// Rules:   NFR-3 (universal server pagination) · B14 rule 31 (no database id
//          is the visible value of a field) · BR-REP-018 (3-day retention)
// Tests:   07-frontend/src/features/reports/runHistory.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// THE TWO READS BEHIND `5·1` AND `5·2`, AND THE ONE WRITE BEHIND RE-RUN.
//
// ⚠ **RE-RUN GOES BACK THROUGH `POST /exports`, WHICH IS §8.2'S RIGHT PATH.**
// The brief is explicit that the right path never holds a page, and that all
// three async calls already work: 202 + a job id at once, then the poll, then
// the file. Re-run is therefore not a fourth call — it is the FIRST one again,
// with the parameters the original run stored. Measured on the running product
// on 2026-09-27: `POST /api/exports` answered **202 in 0.117s** with
// `{"job_id": "…", "status_url": "/api/jobs/…"}`.
import { api } from "./client";
import type { AcceptedJob, ApiClient, ApiResponse } from "./client";
import type { ExportResource } from "./endpoints";
import type { PagedRows } from "./paginated";
import { readListPageWith } from "./paginated";

// `endpoints.ts`'s own `requireData` is module-private, so the same two lines
// live here rather than widening that module's surface for one caller. A 2xx
// with no body where the contract promises one is a server bug (B12 r1);
// throwing beats handing a screen a silent `null` it renders as blank.
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** The five things a run can say on `5·1`. Four are `core.jobs.STATUSES`;
 *  `expired` is derived on read from the run's own timestamp and is never
 *  stored — see `apps/reports/run_history.py`. */
export type RunStatus = "queued" | "running" | "ready" | "failed" | "expired";

/** One part of a run's summary: a label already in the tenant's words, or a
 *  catalogue word (`label_key`, with its params — a plural by `count`). */
export type RunSummaryPart =
  | { text: string }
  | { label_key: string; params?: Record<string, string | number> };

/** One typed figure of a modelled row, at its STORED precision. */
export interface RunSummaryFigure {
  label_key: string;
  kind: "money" | "unit_price";
  value: string;
}

/** One line of a run's summary (`apps/reports/run_history.summary`). */
export interface RunSummaryLine {
  parts: RunSummaryPart[];
  figures?: RunSummaryFigure[];
}

export interface ReportRun {
  /** ⚠ **NEVER RENDERED** (B14 rule 31). It is the address of `5·2` and of the
   *  file, and the row a clerk reads says the report's name and the time. */
  id: string;
  report: string;
  ran_at: string | null;
  /** A person's NAME, or `null` — which the screen renders as *Schedule*. The
   *  server never sends an id here. */
  started_by: string | null;
  filters: Record<string, string>;
  /** The run's parameters IN WORDS, where its report describes them (B14 rule
   *  31: the filters can hold ids — Rate Impact's `rows` does). `null` or
   *  absent → the screen reads the plain filters. */
  summary?: RunSummaryLine[] | null;
  status: RunStatus;
  progress: { done?: number | null; total?: number | null };
  rows: number | null;
  error: string | null;
  expires_at: string | null;
  /** The download address, **or `null` when there is no file to download.**
   *  ⚠ The screen draws a control if and only if this is a string. Drawing one
   *  over `null` is the same defect as a toast pointing at a screen that does
   *  not exist, which is what this phase exists to fix. */
  file: string | null;
}

/**
 * The two selects' options, which ride BESIDE the page.
 *
 * ⚠ **THERE IS NO `ReportRunPage` INTERFACE AND THERE MUST NOT BE ONE.** The
 * first draft declared `{rows, total, page, per, pages, reports, statuses}` —
 * the SELECTOR's dict, transcribed onto the wire — and `G114` refused it. It
 * was right, and the cost of the mistake is on record: three shipped Work
 * screens drew their own *no results* state over rows the API had just
 * returned, because `data.rows` was `undefined` and `undefined ?? []` is a
 * legal empty array. `tsc` cannot see it — a generic on `client.get<T>()` is
 * an ASSERTION about JSON nothing compares at runtime.
 *
 * `paginated.ts` is the ONE description of `{count, next, previous, results}`
 * and `readListPageWith` asserts it at runtime, so a reply that is not the
 * envelope throws by name instead of rendering as empty.
 */
export interface ReportRunExtras {
  /** The *All reports* select's options — the same registry the rows are
   *  filtered by, so a filter cannot offer a report no row can have. */
  reports: string[];
  statuses: RunStatus[];
  /** `CR-142-BRC07` `P5.12` — how long THIS utility keeps a generated file.
   *  Served with the page so the retention SENTENCE and the EXPIRY of the rows
   *  above it are one number: the screen used to type `3` into its own
   *  catalogue while the server had already made retention tenant-settable. */
  retention_days: number;
}

export interface ReportRunQuery {
  q?: string;
  report?: string;
  status?: string;
  page?: number;
  per?: number;
}

export async function getReportRuns(
  query: ReportRunQuery = {},
  client: ApiClient = api,
): Promise<PagedRows<ReportRun> & { body: ReportRunExtras }> {
  // BR-SHL-011's grammar, passed straight through — `readListPageWith` drops
  // the `undefined`s and describes none of it.
  return readListPageWith<ReportRun, ReportRunExtras>(
    "/reports/history",
    {
      q: query.q || undefined,
      "f.report": query.report || undefined,
      "f.status": query.status || undefined,
      page: query.page && query.page > 1 ? query.page : undefined,
      per: query.per,
    },
    client,
  );
}

export async function getReportRun(id: string, client: ApiClient = api): Promise<ReportRun> {
  return requireData(await client.get<ReportRun>(`/reports/history/${id}`));
}

/**
 * `P3.4` — re-run a finished run with its ORIGINAL parameters, unchanged.
 *
 * ⚠ **THE PARAMETERS COME OFF THE RUN, NEVER OFF THE SCREEN.** The drawing's
 * outcome is *"last quarter's report reproduces exactly"*, and the only way
 * that is true is if the window the original run stored is the window the new
 * one asks for — not the screen's current filters, and not a default the
 * server would supply for an absent one. `5·2` renders `filters` read-only for
 * the same reason: a run is a historical fact and is never editable.
 *
 * ⚠ **IT IS A NEW ROW, NOT A REPLACEMENT.** The drawing's callout ④: *"a new
 * row at the top of `5·1`; the old run and its file are untouched. Two figures
 * may differ, because the data moved — which is the point of keeping both runs
 * rather than replacing one."*
 */
export async function rerunReport(run: ReportRun, client: ApiClient = api): Promise<AcceptedJob> {
  return requireData(
    await client.post<AcceptedJob>("/exports", {
      resource: run.report as ExportResource,
      filters: { ...run.filters },
      sort: null,
      dir: null,
      q: "",
    }),
  );
}
