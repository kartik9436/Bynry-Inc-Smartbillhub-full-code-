// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.4` (screen
//          `2·3`) and `P4.5` (screens `4·1`, `4·2`). Drawings p34, p40, p41,
//          read as IMAGES per B14 rule 42.
// Rules:   BR-REP-020 CONFIRMED (internal staff only) · B14 rule 31 (no
//          database id is the visible value of a field) · BR-SHL-011 (the
//          list/URL grammar)
// ───────────────────────────────────────────────────────
// The `/reports/schedules` wrappers, in their own module beside
// `runHistoryEndpoints.ts` — the precedent this follows.
//
// ⚠ **THERE IS NO `email` FIELD IN ANY TYPE IN THIS FILE, AND THAT IS THE
// RULING RATHER THAN AN OMISSION.** `BR-REP-020` is CONFIRMED: recipients are
// this tenant's own staff, and external recipients arrive at W6 with an
// explicit confirm step because an external send means data leaves the tenant.
// A `recipients: string[]` of EMAIL ADDRESSES would type-check, compile, pass
// every test and break a signed ruling silently. These are USER IDS, and the
// server refuses anything that is not one of its own users by name.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** The four SIGNED cadences, rendered as WORDS and never as a cron string
 *  (p40 callout ①). `monthly_on_cycle_close` is *"the one a utility actually
 *  wants and the one a generic cron picker loses"* (p34 callout ②). */
export type Cadence = "daily" | "weekly" | "monthly" | "monthly_on_cycle_close";

/** ⚠ **ONE VALUE, AND THE HOLE IS SIGNED** (p34 callout ③): CSV only, because
 *  no PDF renderer is declared anywhere in this product. A `"pdf"` member here
 *  would put a control on screen that produces nothing. */
export type ScheduleFormat = "csv";

/** `4·1`'s status column — On · Paused · Failing. DERIVED on the server from
 *  `enabled` and the job `last_job_id` points at, never stored: a stored one
 *  gets stuck saying *failing* because the run that would have cleared it never
 *  wrote back. */
export type ScheduleStatus = "on" | "paused" | "failing";

export interface ReportSchedule {
  /** ⚠ **NEVER RENDERED** (B14 rule 31). It is the address of `4·2` and the
   *  target of pause / run now / delete. */
  id: string;
  /** The report's NAME, resolved by the server. The screen does not re-derive
   *  it from a key: `P1.1` records what that cost on the catalogue — a utility
   *  that renamed a report could never see its own name, because it cannot
   *  edit our locale catalogues. */
  report: string;
  report_key: string;
  cadence: Cadence;
  format: ScheduleFormat;
  /** ISO instant, or `null` — and `null` on an ENABLED schedule is not
   *  "unknown", it is a schedule that will never fire. The server renders that
   *  as `failing`; this type keeps the null so the *Next* cell can draw an
   *  em-dash rather than the string "null". */
  next_run_at: string | null;
  /** User ids — see this file's header. They travel because `4·2` has to
   *  re-open the picker with the right people ticked. */
  recipients: string[];
  /** What `4·1`'s *Send to* column actually draws (B14 rule 31). */
  recipient_names: string[];
  status: ScheduleStatus;
  params: Record<string, unknown>;
}

export interface SchedulePage {
  rows: ReportSchedule[];
  total: number;
  page: number;
  per: number;
  /** The selects' options, SERVED — never typed out on this side. An
   *  eleventh service existed, was served, and *"simply never appeared on the
   *  sign-up screen"* because two files typed the list by hand (B14 rule 2's
   *  worked case). */
  cadences: Cadence[];
  formats: ScheduleFormat[];
  statuses: ScheduleStatus[];
  /** The recipients picker's options: this tenant's own users, and nobody
   *  else. This is what makes `BR-REP-020` a control rather than a comment. */
  staff: { id: string; name: string }[];
}

export interface ScheduleQuery {
  q?: string;
  status?: ScheduleStatus;
  page?: number;
  per?: number;
}

export async function getSchedules(
  query: ScheduleQuery = {},
  client: ApiClient = api,
): Promise<SchedulePage> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.status) params.set("f.status", query.status);
  if (query.page !== undefined && query.page > 1) params.set("page", String(query.page));
  if (query.per !== undefined) params.set("per", String(query.per));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return requireData(await client.get<SchedulePage>(`/reports/schedules${suffix}`));
}

/** `2·3` commits. The report and its parameters are INHERITED from the screen
 *  behind (p34: *"The report, its parameters and its name are inherited from
 *  the screen behind"*), which is why they are in the body beside the three
 *  fields a person actually filled in. */
export interface CreateSchedule {
  definition_key: string;
  cadence: Cadence;
  format: ScheduleFormat;
  recipients: string[];
  params: Record<string, unknown>;
}

export async function createSchedule(
  body: CreateSchedule,
  client: ApiClient = api,
): Promise<ReportSchedule> {
  return requireData(await client.post<ReportSchedule>("/reports/schedules", body));
}

export async function updateSchedule(
  id: string,
  body: Partial<Pick<ReportSchedule, "cadence" | "format" | "recipients">> & {
    enabled?: boolean;
  },
  client: ApiClient = api,
): Promise<ReportSchedule> {
  return requireData(
    await client.patch<ReportSchedule>(`/reports/schedules/${id}`, body),
  );
}

export async function deleteSchedule(id: string, client: ApiClient = api): Promise<void> {
  // ⚠ **`del`, NOT `delete`.** `ApiClient`'s verb is named `del` because
  // `delete` is a reserved word in JavaScript and cannot be a method name on
  // an object literal without quoting. Reaching for `client.delete` compiles
  // to `undefined is not a function` at runtime with nothing in `tsc` to
  // catch it on a loosely-typed client — it was caught here by reading the
  // interface rather than by assuming the obvious spelling.
  await client.del(`/reports/schedules/${id}`);
}

/** `4·1`'s ▶ row action. ⚠ **It does NOT advance the schedule** (p41 ④) — a
 *  clerk checking that a schedule works must not thereby cancel Monday's run. */
export async function runScheduleNow(
  id: string,
  client: ApiClient = api,
): Promise<{ job_id: string; schedule: ReportSchedule }> {
  return requireData(
    await client.post<{ job_id: string; schedule: ReportSchedule }>(
      `/reports/schedules/${id}/run-now`,
      {},
    ),
  );
}
