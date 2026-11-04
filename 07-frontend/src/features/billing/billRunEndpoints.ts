// ── Trace ──────────────────────────────────────────────
// Change:   CR-051 tasks 2, 3, 7 and 12 — the FRONT half of the run screens
//           on the background worker. The backend landed the same day: task 1
//           (`GET /billing/runs/{id}`), tasks 5/6 (`bill_run_breaks` +
//           `GET /billing/runs/{id}/breaks`) and tasks 8/9/10 (the three verbs
//           answer 202 with a job id, and the job record carries `done`/`total`).
// Story:    US-BIL-001 (a run is resumable) · US-BIL-004 (phase 2)
// Screens:  S31 step 1 (Past billing runs · re-open) · S31 step 4 (the breaks,
//           and the progress of the pass that produced them)
// Defects:  DEF-106 (a started bill run cannot be returned to — the run id is
//           in the URL and nowhere else, and S30's history tab is a
//           placeholder) · DEF-2557 (`runs.retry_account` is reachable from no
//           route, so no retry control may be drawn as live)
// Rules:    BR-BIL-050 (a run is RESUMABLE at the phase its status names) ·
//           BR-BIL-051 (phase 2 is a BACKGROUND batch; the clerk is not held
//           at the screen) · BR-BIL-053 (the break list, before the totals) ·
//           BR-SHL-011 (URL grammar — `f.<name>` on a list) · hard-won law 1
//           (a comment claiming a guarantee is not the guarantee — every shape
//           below was read off the server's own selector and then fetched over
//           real HTTP before this file was written)
// ───────────────────────────────────────────────────────
//
// FOUR TYPED READS FOR ONE FAMILY, AND WHY THEY ARE NOT IN `api/endpoints.ts`.
//
// `billChainEndpoints.ts` wrote the reason on the same branch and it has not
// changed: `api/endpoints.ts` is the file every lane appends to and on any
// afternoon it holds two or three lanes' half-finished work (CLAUDE.md law 11 —
// a pathspec commit takes the WHOLE file). One family, one file, one lane's
// diff. Nothing here re-exports or shadows anything `endpoints.ts` publishes:
// `BillRunCalculated` and `BillRunBreak` still come from there, and this file
// imports them rather than declaring a second copy (law 5).
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS MEASURED BEFORE ANY OF THIS WAS TYPED (2026-08-30, real HTTP,
// a private database seeded by this lane — the shared one is being reseeded)
// ══════════════════════════════════════════════════════════════════════════
//   GET  /billing/runs/{id}          → 200, phase "issued", counts.accounts 46,
//                                      counts.breaks 1, run_no "RUN-0002"
//   GET  /billing/runs/{id}/breaks   → 200, break_count 1, resolution null
//   POST /billing/runs/{id}/calculate {"background": true}
//                                    → 202, job_id + status_url
//                                      "/api/jobs/{id}" + `unavailable` ×2
//   GET  /api/jobs/{id}              → 200, status "succeeded",
//                                      progress {done: 47, total: 47}
//
// ⚠ **THE STATUS CODE IS THE DISCRIMINATOR AND THE BODY IS NOT.** The server's
// own `CALCULATE_UNAVAILABLE` says it in as many words: *"if `background: true`
// is asked for on a deployment where nothing would run the job, the run
// executes INLINE and this response says so on `background: false` with a 201
// rather than a 202"*. So `calculateBillRunMaybeBackground` reads
// `response.status` and returns a DISCRIMINATED UNION — a caller cannot reach
// for `job_id` on the inline branch, because on that branch there is no
// `job_id` in the type. Guessing from a truthy `job_id` would have been the
// same class of bug as coercing `background: "yes"` to true, which is exactly
// what `_wants_background` refuses to do on the other side of the wire.
import { api, JOBS_PATH } from "@/api/client";
import type { ApiClient, ApiResponse, JobRecord } from "@/api/client";
import type { BillRunBreak, BillRunCalculated } from "@/api/endpoints";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported from `endpoints.ts` so this file adds no
 *  coupling to a file three lanes are editing — `billChainEndpoints`' rule. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

function runPath(runId: string, suffix = ""): string {
  return `/billing/runs/${encodeURIComponent(runId)}${suffix}`;
}

// ══════════════════════════════════════════════════════════════════════════
// GET /billing/runs/{id} — ONE RUN (CR-051 task 1)
// ══════════════════════════════════════════════════════════════════════════

/**
 * The FOUR phase words `selectors._run_phase` can answer, in the order it
 * derives them — furthest point first.
 *
 * ⚠ **THESE ARE NOT `billRunShared.RUN_PHASES`.** That list is the FIVE phases
 * of the PO's 2026-08-11 description (`prepare · calculate · breaks · summary ·
 * release`) and it describes the WORK. This list is the four words the SERVER
 * answers on `run_detail_dict.phase` and it describes EVIDENCE — drafts exist,
 * a release row exists, a bill is out. Naming one from the other would be a
 * screen re-deriving a fact the server already resolved.
 */
export const SERVED_RUN_PHASES = ["draft", "calculated", "authorised", "issued"] as const;
export type ServedRunPhase = (typeof SERVED_RUN_PHASES)[number];

/** The run's scope as it was recorded at creation — `bill_runs`' own columns. */
export interface BillRunScope {
  cycle_id: string | null;
  period_start: string | null;
  period_end: string | null;
  bill_date: string | null;
  due_days: number | null;
  bill_type: string | null;
  services: string[] | null;
  account_id: string | null;
  parent_run_id: string | null;
}

/** What the run has, counted server-side in five grouped queries. */
export interface BillRunCounts {
  accounts: number;
  drafts: number;
  bills_issued: number;
  /** OUTSTANDING breaks — the gate's number (BR-BIL-053). */
  breaks: number;
  /** Everything that ever broke on this run, resolved ones included. */
  breaks_total: number;
  breaks_by_stage: Record<string, { total: number; outstanding: number }>;
  held: number;
}

/** What the last BACKGROUND findings pass counted, or null when none has run. */
export interface BillRunFindingsSummary {
  job_id: string | null;
  accounts: number | null;
  ready: number | null;
  blocked: number | null;
  decisions: number | null;
  blocked_by_reason?: Record<string, number>;
}

/**
 * `GET /billing/runs/{id}` — one run, re-openable.
 *
 * ⚠ **`phase` AND `status` ARE DIFFERENT FACTS AND ONLY ONE OF THEM IS TRUE.**
 * The server serves both and says why: `bill_runs.status` is written `"draft"`
 * at creation and *nothing in the billing module ever moves it*, so a screen
 * rendering `status` would title a year of finished work **Draft**. `phase` is
 * derived from evidence — drafts, a release row, an issued bill — and is what a
 * screen reads. `status` is typed here because it is served and hiding it would
 * hide the defect, and it is rendered NOWHERE.
 */
export interface BillRunDetail {
  id: string;
  run_no: string | null;
  /** DEF-BIL-8680 — the run's name as the clerk typed it on Scope; optional
   *  because a server before 2.418.2 does not serve it. */
  label?: string | null;
  /** DEF-BIL-8685 — who signed the run off and when (the newest release row). */
  signed_off?: { by: string | null; at: string | null } | null;
  /** One of `SERVED_RUN_PHASES` — typed `string` because a server that grows a
   *  fifth word must not make this type a lie. `servedRunPhase()` narrows it. */
  phase: string;
  /** DEF-BIL-9010 — a Calculate job still queued or running; `phase` reads
   *  `calculated` as soon as one draft exists, so the page shows this job's
   *  progress while it is set. Optional: a server before 2.437.6 omits it. */
  calculating?: {
    id: string;
    status: string;
    progress: { done: number; total: number | null; stage?: string } | null;
  } | null;
  /** DEF-BIL-9004 / 9010 — a whole-run Check job still queued or running
   *  (Check again on a run that already holds drafts included). */
  checking?: {
    id: string;
    status: string;
    progress: { done: number; total: number | null } | null;
  } | null;
  /** The STORED column. Served, never rendered — see the note above. */
  status: string;
  scope: BillRunScope;
  decisions: { taken: number; by_case: Record<string, number> };
  counts: BillRunCounts;
  findings_summary: BillRunFindingsSummary | null;
  issued_at: string | null;
  created_at: string | null;
}

export const billRunDetailKey = (runId: string) => ["billing", "run", runId, "detail"] as const;

/** DEF-BIL-8685 — of the reads a SENT run's bills priced, how many Meter
 *  Reads holds BILLED. */
export interface BillRunMeterReads {
  state: "locked" | "partly" | "open" | "none";
  reads: number;
  locked: number;
}

/**
 * `GET /billing/runs/{id}/read-lock` — the Sent card's *Meter reads* row.
 *
 * DEF-BIL-8809: it rode `GET /billing/runs/{id}` and was ~1.1 s of that read's
 * 1.2 s on a sent 40,008-bill run, so every screen of the bulk run page waited
 * for a row only the Sent card draws. `meter_reads` is null before the run is
 * sent or when Meter Reads cannot say. Keyed UNDER the run's detail key, so
 * anything that refreshes the run refreshes it too.
 */
export interface BillRunReadLock {
  bill_run_id: string;
  meter_reads: BillRunMeterReads | null;
}

export const billRunReadLockKey = (runId: string) => [...billRunDetailKey(runId), "read-lock"] as const;

export async function getBillRunReadLock(runId: string, client: ApiClient = api): Promise<BillRunReadLock> {
  return requireData(await client.get<BillRunReadLock>(runPath(runId, "/read-lock")));
}

export async function getBillRun(
  runId: string,
  client: ApiClient = api,
): Promise<BillRunDetail> {
  return requireData(await client.get<BillRunDetail>(runPath(runId)));
}

/** `POST /billing/runs/{id}/discard` — DEF-BIL-9255. A DRAFT run is thrown
 *  away: its draft bills go and its row stays `abandoned`, so it stops blocking
 *  an overlapping run. The server refuses a run with a bill out or a sign-off. */
export interface BillRunDiscarded {
  id: string;
  status: string;
  drafts_removed: number;
}

export async function discardBillRun(runId: string, client: ApiClient = api): Promise<BillRunDiscarded> {
  return requireData(await client.post<BillRunDiscarded>(runPath(runId, "/discard"), {}));
}

/** The served phase word, or `null` when the server named one this build does
 *  not know. `null` is answered rather than a guess: a screen that mapped an
 *  unknown phase onto a step would put a clerk somewhere nobody decided. */
export function servedRunPhase(phase: string): ServedRunPhase | null {
  return (SERVED_RUN_PHASES as readonly string[]).includes(phase)
    ? (phase as ServedRunPhase)
    : null;
}

// ══════════════════════════════════════════════════════════════════════════
// GET /billing/runs/{id}/breaks — THE DURABLE BREAK LIST (CR-051 tasks 5/6/7)
// ══════════════════════════════════════════════════════════════════════════

/**
 * `GET /billing/runs/{id}/breaks`.
 *
 * ⚠ **THIS IS WHY THE LIST NOW SURVIVES A REFRESH, A LOGOUT AND A SHIFT
 * CHANGE, AND IT IS A PROPERTY OF WHERE THE ROWS LIVE — NOT OF THIS FILE.**
 * Until billing migration 0026 the breaks existed only in
 * `runs.CalculatedRun.breaks`, so the only copy a clerk ever had was the
 * response to the POST that produced them: navigating away lost the exception
 * list while keeping the drafts. `bill_run_breaks` is a real table now, so the
 * list is the SERVER's — which is also the whole of why TWO PEOPLE CAN WORK
 * IT: both see the same rows and the same resolutions, and neither is looking
 * at a copy that went stale when the other fixed something.
 *
 * There is no claim, lock or assignment on a row, and this wrapper invents
 * none: that would be a rule nobody has given.
 *
 * OUTSTANDING BY DEFAULT (`resolution: null`), because that is the work list
 * and BR-BIL-053's own word. `includeResolved` adds `?f.resolved=all` for the
 * supervisor's question — *"what did this run struggle with?"* — after it is
 * over. `f.` is BR-SHL-011's list grammar and the server compares it with `=`.
 */
/**
 * One STORED break row — `BillRunBreak` plus the five columns only a table can
 * have.
 *
 * ⚠ **IT EXTENDS RATHER THAN REPLACES, AND THAT IS THE POINT.**
 * `api/endpoints.ts`'s `BillRunBreak` types what `POST .../calculate` returns
 * — `runs.Break`, an in-memory dataclass with no id, no resolution and no
 * timestamps, because until migration 0026 a break HAD none of those. The
 * stored row has all five. Widening the shared type would make every existing
 * reader of the POST response claim fields that response does not send; a
 * second, unrelated type would let the two drift. `extends` says exactly what
 * is true: every stored break is a break, and it carries more.
 *
 * `resolution === null` means OUTSTANDING. That is the work list, and it is
 * BR-BIL-053's own word — not "unresolved", not "open", and not a boolean.
 */
export interface BillRunBreakRow extends BillRunBreak {
  id: string;
  /** NULL = outstanding. A later pass that drafted the account writes here. */
  resolution: string | null;
  /** The background job that raised it, when one did (CR-051 task 8). */
  job_id: string | null;
  raised_at: string | null;
  updated_at: string | null;
}

export interface BillRunBreaksPayload {
  bill_run_id: string;
  breaks: BillRunBreakRow[];
  break_count: number;
  breaks_by_stage: Record<string, string[]>;
  includes_resolved: boolean;
}

export const billRunBreaksKey = (runId: string, includeResolved: boolean) =>
  ["billing", "run", runId, "breaks", includeResolved ? "all" : "outstanding"] as const;

export async function getBillRunBreaks(
  runId: string,
  includeResolved = false,
  client: ApiClient = api,
): Promise<BillRunBreaksPayload> {
  const query = includeResolved ? "?f.resolved=all" : "";
  return requireData(await client.get<BillRunBreaksPayload>(runPath(runId, `/breaks${query}`)));
}

// ══════════════════════════════════════════════════════════════════════════
// BR-BIL-053's TWO WAYS OUT — *"retry immediately by fixing the issue or mark
// for later"* (DEF-2856, and DEF-2557 for the control that could not act)
//
// Both engines shipped on 2026-08-11 with their tests and no HTTP caller, so
// the panel drew a Retry that was disabled on every branch and offered no hold
// at all. These are the two routes that give it something to send to.
// ══════════════════════════════════════════════════════════════════════════

/** A retry that produced a bill. `resolution` is what closed the break row. */
export interface BreakRetried {
  bill_run_id: string;
  account_id: string;
  invoice_id: string;
  /** BR-BIL-063 — a draft carries its number from creation. */
  invoice_no: string | null;
  resolution: string;
}

/** A hold that queued the account for a catch-up sub-run (BR-BIL-055). */
export interface BreakHeld {
  bill_run_id: string;
  account_id: string;
  exclusion_id: string;
  /** Carries the failing STAGE, so the queue groups the way this list does. */
  reason_code: string;
  resolution: string;
}

export async function retryBillRunBreak(
  runId: string,
  accountId: string,
  client: ApiClient = api,
): Promise<BreakRetried> {
  return requireData(
    await client.post<BreakRetried>(
      runPath(runId, `/breaks/${encodeURIComponent(accountId)}/retry`),
      {},
    ),
  );
}

export async function holdBillRunBreak(
  runId: string,
  accountId: string,
  client: ApiClient = api,
): Promise<BreakHeld> {
  return requireData(
    await client.post<BreakHeld>(
      runPath(runId, `/breaks/${encodeURIComponent(accountId)}/hold`),
      {},
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// GET /billing/runs/{id}/summary — WHAT THE RUN ADDS UP TO (DEF-2853)
//
// The four figures the PO named on 2026-08-11: *"how many accounts, how many
// bills generated, how much consumption and how much bill amount and various
// categories"*. Every one of them was computed server-side from the day that
// was said and reached no screen, so steps 4 and 5 drew "Not worked out" over
// a working implementation for three weeks.
//
// ⚠ **IT RECALCULATES, AND THE STORED ROW DOES NOT.** The PO chose that on
// their own worked figure: approve 480 bills at $52,847.19, void two next
// week, and re-opening the run must read 478. So this read is never cached
// across a mutation and never filled in from the release response — those are
// two different questions with two different right answers.
// ══════════════════════════════════════════════════════════════════════════

/** One service's usage, in ONE unit. `service` is null when the bill lines do
 *  not say which service a quantity belongs to — NOT ATTRIBUTED, never "no
 *  service", and never inferred from the unit (water and sewer both meter in
 *  kgal). The quantity is a decimal string and is never parsed into a float. */
export interface RunConsumptionFigure {
  service: string | null;
  quantity: string;
  unit: string;
}

/** One row of one breakdown. The AXIS travels on the row rather than being a
 *  key, because which axes exist is the open half of BR-BIL-057 — a shape that
 *  made them structural would have to change the day the PO rules. */
export interface RunCategoryFigure {
  axis: string;
  key: string | null;
  bills: number;
  amount: string;
  currency: string;
}

/**
 * What one sign-off confirmation is shown against.
 *
 * ⚠ **`covered: null` IS NOT ZERO AND MUST NEVER RENDER AS ZERO.** "Nobody
 * holds an email address" and "we could not count them" are different facts,
 * and the second one is about to sit under a person's signature.
 * `unavailable_reason` is the sentence to show in that case.
 */
export interface RunMandateCoverage {
  mandate: string;
  covered: number | null;
  not_covered: number | null;
  accounts: number;
  amount: string | null;
  unavailable_reason: string | null;
}

/** One thing the summary cannot answer, or one caveat on what it did. `code`
 *  is a support-line string the screen groups on and never prints (CR-016). */
export interface RunSummaryProblem {
  code: string;
  br_ref: string;
  detail: string;
}

export interface BillRunSummary {
  bill_run_id: string;
  /** Every account the run TOUCHED — billed plus held — so "480 of 500" is
   *  honest rather than a count of whoever happened to produce a bill. */
  accounts: number;
  bills: number;
  consumption: RunConsumptionFigure[];
  /** What these customers owe NOW, net of credit notes with no replacement.
   *  Money is a decimal string with its currency beside it; `currency` is null
   *  on a run with no bills, because there is no currency to name. */
  amount: string;
  currency: string | null;
  gross_amount: string;
  credits_applied: string;
  /** CR-059 CS-37 — how many credit notes made up `credits_applied`, and up to
   *  five of them NAMED so the sign-off sentence can say which.
   *
   *  ⚠ **EVERY ENTRY IS A `CM-` NUMBER, OR THE BILL AND DATE OF A HISTORIC ROW
   *  THAT HAS NONE. NEVER A DATABASE ID.** Until 2026-09-02 the server composed
   *  this list as `number or pk`, and because no credit note had ever been
   *  numbered the `pk` branch was the only one that ever ran — so a finance
   *  user signing off a run read a raw UUID, which B14 rule 31 forbids
   *  outright. CS-37 numbers the notes and removes the fallback; its rollback
   *  note says in terms that restoring it is not an option. */
  credit_count: number;
  credits_named: string[];
  by_category: RunCategoryFigure[];
  /** "PROPOSED" while the PO has not enumerated the axes. */
  axes_status: string;
  coverage: RunMandateCoverage[];
  problems: RunSummaryProblem[];
}

export const billRunSummaryKey = (runId: string) =>
  ["billing", "run", runId, "summary"] as const;

/**
 * `GET /billing/runs/{id}/totals` — the summary's HEADLINE alone: bills, and
 * the amount these customers owe now (net of credit notes) with its currency.
 *
 * DEF-BIL-8809: the bulk run page draws exactly these two figures from the
 * summary (the Sent card's total, Send's bill count) and was asking for the
 * whole panel — ~1.1 s at 40,008 bills, 3.1 s beside the page's other reads.
 * The server computes them with the same functions as `/summary`, live.
 */
export interface BillRunTotals {
  bill_run_id: string;
  bills: number;
  amount: string;
  currency: string | null;
  gross_amount: string;
  credits_applied: string;
  credit_count: number;
}

export const billRunTotalsKey = (runId: string) => ["billing", "run", runId, "totals"] as const;

export async function getBillRunTotals(runId: string, client: ApiClient = api): Promise<BillRunTotals> {
  return requireData(await client.get<BillRunTotals>(runPath(runId, "/totals")));
}

export async function getBillRunSummary(
  runId: string,
  client: ApiClient = api,
): Promise<BillRunSummary> {
  return requireData(await client.get<BillRunSummary>(runPath(runId, "/summary")));
}

// ══════════════════════════════════════════════════════════════════════════
// POST /billing/runs/{id}/calculate — 202 OR 201, AND THE CALLER CAN TELL
// ══════════════════════════════════════════════════════════════════════════

/** One entry of the server's own `unavailable` list. Rendered as prose, never
 *  matched on: the `code` is a support-line string and CR-016 keeps internal
 *  references off a utility's screen, so the SCREEN prints `detail`. */
export interface RunVerbUnavailable {
  code: string;
  br_ref: string;
  detail: string;
}

/** 202 — the pass is a worker's now and the clerk may close the tab. */
export interface RunVerbAccepted {
  background: true;
  job_id: string;
  /** `/api/jobs/{id}`, composed by the framework. Kept as served and never
   *  parsed: the poll goes through `getJobRecord`, which builds the same path
   *  from `JOBS_PATH` — two readers of one address, and this one is the
   *  server's own answer, recorded so a divergence is visible. */
  status_url: string;
  bill_run_id: string;
  unavailable: RunVerbUnavailable[];
}

/** 201 — nothing would have RUN the job, so the pass ran INLINE and this is the
 *  finished result. Never queued into a void (CLAUDE.md law 3). */
export interface RunVerbRanInline {
  background: false;
  result: BillRunCalculated;
  unavailable: RunVerbUnavailable[];
}

export type RunCalculateOutcome = RunVerbAccepted | RunVerbRanInline;

/**
 * `POST /billing/runs/{id}/calculate` with `{"background": true}`.
 *
 * ⚠ **IT ASKS, AND THE SERVER DECIDES.** `background: true` is a REQUEST, not
 * an assertion: `run_jobs.would_run()` answers whether anything would actually
 * execute the job, and on a deployment with no worker the pass runs inline and
 * answers 201. Both outcomes are honest and the screen must render the
 * difference rather than pretending it queued — which is the whole reason this
 * returns a union instead of a `job_id | null`.
 *
 * SAFE TO PRESS TWICE, on either branch. The enqueue carries the scope key
 * `billing:calculate:<run id>`, so a second click while the job is active
 * returns THE EXISTING RECORD (NFR-16); and a second PASS converges because
 * stage 6 replaces an account's draft rather than adding a second (BR-BIL-052).
 */
export async function calculateBillRunMaybeBackground(
  runId: string,
  client: ApiClient = api,
): Promise<RunCalculateOutcome> {
  const response = await client.post<Record<string, unknown>>(runPath(runId, "/calculate"), {
    background: true,
  });
  const body = requireData(response);
  const unavailable = Array.isArray(body.unavailable)
    ? (body.unavailable as RunVerbUnavailable[])
    : [];
  if (response.status === 202) {
    return {
      background: true,
      job_id: String(body.job_id ?? ""),
      status_url: String(body.status_url ?? ""),
      bill_run_id: String(body.bill_run_id ?? runId),
      unavailable,
    };
  }
  return {
    background: false,
    result: body as unknown as BillRunCalculated,
    unavailable,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// GET /api/jobs/{id} — THE PROGRESS THE SCREEN DRAWS (CR-051 tasks 10/12)
// ══════════════════════════════════════════════════════════════════════════

/**
 * One poll of the BE-07 job record.
 *
 * ⚠ **NOT `client.pollJob`, AND THE DIFFERENCE MATTERS TO THE SCREEN.**
 * `pollJob` is an imperative loop that resolves once, at the terminal status —
 * perfect for a caller that only wants the answer, and useless for a progress
 * line, which needs a RE-RENDER on every reading. This is one read; the screen
 * repeats it through `refetchInterval` and re-renders each time, which is also
 * what makes the readout resumable: the job id lives in the URL, so a reload
 * or a second person on the same link picks the poll up mid-pass.
 *
 * ⚠ **`progress` CAN BE `null` AND A NULL IS NOT A ZERO.** `job_progress_
 * default()` is `{done: 0, total: null}` before a body has reported anything,
 * and the run reports every 25 accounts (`run_jobs.PROGRESS_EVERY`) and always
 * on the last one. A screen that read a missing total as 0 would draw
 * "0 of 0" over a running pass; `RunProgressLine` draws the count with no
 * denominator instead, and no bar at all.
 */
export const jobRecordKey = (jobId: string) => ["jobs", jobId] as const;

export async function getJobRecord(
  jobId: string,
  client: ApiClient = api,
): Promise<JobRecord> {
  return requireData(await client.get<JobRecord>(`${JOBS_PATH}/${encodeURIComponent(jobId)}`));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-051 tasks 2/3/7/12 (12-governance/11-change-requests.md §CR-051) · source reads apps/billing/selectors.py::run_detail_dict + run_breaks_dict · apps/billing/api.py::run_item / run_breaks / run_calculate · apps/tenancy/selectors.py::job_poll
// generated: 2026-08-30 by the CR-051 run-screens FRONT lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · every route here was called over real HTTP before the file was written — the four responses are quoted in the header block above
// exceptions: E3 `BillRunDetail.phase` is typed `string` and narrowed by `servedRunPhase()` rather than typed as the four-word union: a server that grows a fifth phase must make the screen SAY SO, not make this type false · E3 `BillRunDetail.status` is typed and rendered nowhere — served because `run_detail_dict` serves it, and the server's own comment explains that rendering it would title every historical run "Draft" · E3 no wrapper exists here for `POST .../findings` or `POST .../issue`, both of which now take `background: true` — neither has a caller on the run screens this lane owns (LAW 0: an unused wrapper is not coverage), and step 6's issue goes through `commitRelease`, which is another change · E3 there is deliberately NO retry wrapper: `POST /billing/runs/{id}/breaks/{account_id}/retry` does not exist (DEF-2557), and wrapping a path nobody serves is how a screen invents an API
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
