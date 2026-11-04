/**
 * A fake `ApiClient` answering the bulk run's reads from `bulkRunFixtures.ts`
 * and recording every call — shared by the component tests and the capture
 * harness. TEST AND HARNESS ONLY.
 */
import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";

import {
  RUN_ID,
  SERVICES,
  breaks,
  checkAccount,
  checkReady,
  checkReport,
  checkSummary,
  checkTagPage,
  checkTiles,
  cycleRow,
  notInRun,
  pricingShadow,
  readLock,
  runDetail,
  runTemplates,
  scopeMissingMeterRows,
  scopeNobodyRows,
  scopePreview,
  signOffSummary,
  summary,
  templateLibrary,
  totals,
} from "./bulkRunFixtures";
import type { PricingState, ScopeState } from "./bulkRunFixtures";

export interface Call {
  method: string;
  path: string;
  body: unknown;
  query?: Record<string, unknown>;
}

export interface FakeOptions {
  scope?: ScopeState;
  phase?: string;
  access?: string;
  /** The findings read fails the way a module that is down fails. */
  moduleDown?: boolean;
  /** Milliseconds each answer waits — the harness uses it, tests do not. */
  delay?: number;
  /** The Check job is still running (the Checking state, n of N). */
  checking?: boolean;
  /** The run has never been checked — the page starts the Check itself. */
  unchecked?: boolean;
  /** `POST …/check` never returns — the job running inline on a live stack
   *  (JOBS_EAGER), which is the window DEF-BIL-8417 showed 0 tiles in. */
  holdCheckStart?: boolean;
  /** This tag's page never arrives (DEF-BIL-8419: the pane before its page). */
  holdTagRead?: string;
  /** DEF-BIL-10709 — this tag's page read FAILS (a 500), every time. */
  failTagRead?: string;
  /** The summary read lags the saved Check: it still says `checked: false`
   *  while the run's own counts are in (DEF-BIL-8417's second window). */
  summaryBehind?: boolean;
  /** Another clerk has this run open (clerk check F4, DEF-BIL-8512). */
  otherClerk?: string;
  /** One bill broke at Send (clerk check F3, DEF-BIL-8421); a retry sends it. */
  sendFailure?: boolean;
  /** DEF-BIL-8747 — the Send job stops: the same fault on bill after bill. */
  sendStopped?: boolean;
  /** The Check job stopped part-way — its worker lost (DEF-BIL-8511). */
  checkStopped?: boolean;
  /** Two published templates, so the select must be chosen (DEF-BIL-8222). */
  twoTemplates?: boolean;
  /** A bill holds back part of a payment plan as not yet due (DEF-BIL-8720). */
  planLater?: boolean;
  /** DEF-BIL-8809 — the run read (`GET /billing/runs/{id}`) waits until the
   *  test calls `releaseRunRead()`, so a test can see what the page asked for
   *  BEFORE the run's phase was known. */
  holdRunRead?: boolean;
  /** DEF-BIL-9005 — account 1 has two unread meters (water AND electric). */
  twoUnreadMeters?: boolean;
  /** DEF-BIL-9010 — the run read names a Calculate job still running (in its
   *  preparing pass) until the job's second poll finishes it. */
  calculatingLive?: boolean;
  /** DEF-BIL-9004 — after *Check again* is posted, the Check read never
   *  answers: the ~2 s a 40,015-account `GET …/check` takes, held open. */
  holdCheckReadAfterStart?: boolean;
  /** DEF-BIL-10121 — the pricing check's answer (default: 0 differences). */
  pricing?: PricingState;
}

export function fakeClient(options: FakeOptions = {}) {
  const calls: Call[] = [];
  let phase = options.phase ?? "draft";
  let jobPolls = 0;
  let issuePolls = 0;
  let checkPolls = 0;
  let checkStarted = false;
  let checked = options.unchecked !== true;
  let checkJob: "none" | "running" | "done" | "failed" =
    options.checking === true ? "running" : options.checkStopped === true ? "failed" : "none";
  let sendRetried = false;
  // DEF-BIL-8677 — an account fixed on its row is re-checked by the server and
  // LEAVES the tag, as it does on a live stack.
  const fixedAccounts = new Set<string>();
  const heldRunReads: (() => void)[] = [];
  let runReadReleased = options.holdRunRead !== true;
  function releaseRunRead() {
    runReadReleased = true;
    heldRunReads.splice(0).forEach((resolve) => resolve());
  }

  function ok(data: unknown, status = 200) {
    const value = { status, data, etag: null, notModified: false };
    return options.delay === undefined
      ? Promise.resolve(value)
      : new Promise((resolve) => setTimeout(() => resolve(value), options.delay));
  }

  function answer(method: string, path: string, body: unknown, query?: Record<string, unknown>): Promise<unknown> {
    calls.push({ method, path, body, query });
    const run = `/billing/runs/${RUN_ID}`;
    if (path === "/me/permissions") {
      return ok({ permissions: [{ code: "reads_billing_runs", access: options.access ?? "Full" }] });
    }
    if (path === "/cycles" || path.startsWith("/cycles?")) return ok({ count: 1, next: null, previous: null, results: [cycleRow()] });
    if (path === "/bill-templates") return ok(templateLibrary());
    if (path === "/settings/services") return ok(SERVICES);
    if (path === "/billing/runs/scope-preview") return ok(scopePreview(options.scope ?? "continuous"));
    if (path === "/billing/runs/scope-list") {
      const rows = query?.list === "nobody" ? scopeNobodyRows() : scopeMissingMeterRows();
      return ok({ count: rows.length, next: null, previous: null, results: rows });
    }
    if (path === "/billing/runs/scope-templates") {
      const rows = options.twoTemplates === true ? runTemplates() : runTemplates().slice(0, 1);
      return ok({ count: rows.length, next: null, previous: null, results: rows });
    }
    if (path === "/billing/runs" && method === "POST") return ok({ id: RUN_ID, job_id: null, status: "draft", warnings: [] }, 201);
    if (path === run) {
      // DEF-BIL-9010 — a Calculate still live when the run is re-opened.
      if (options.calculatingLive === true && jobPolls < 2) {
        return ok({
          ...runDetail(phase),
          calculating: { id: "job-1", status: "running", progress: { done: 3000, total: 40009, stage: "preparing" } },
        });
      }
      if (runReadReleased) return ok(runDetail(phase));
      return new Promise<void>((resolve) => heldRunReads.push(resolve)).then(() => ok(runDetail(phase)));
    }
    // ── the Check (apps/billing/check_api.py) ────────────────────────────
    if (path === `${run}/check` && method === "POST") {
      if (options.holdCheckStart === true) return new Promise(() => undefined);
      checkJob = "running";
      checkPolls = 0;
      checkStarted = true;
      return ok({ job_id: "job-check", status_url: "/api/jobs/job-check", bill_run_id: RUN_ID, background: true }, 202);
    }
    if (path === `${run}/check`) {
      if (options.holdCheckReadAfterStart === true && checkStarted) return new Promise(() => undefined);
      let job = null;
      if (checkJob === "running") {
        checkPolls += 1;
        const done = options.checking !== true && checkPolls >= 2;
        if (done) {
          checkJob = "done";
          checked = true;
        }
        job = { id: "job-check", status: done ? "succeeded" : "running", progress: { done: done ? 1406 : 400, total: 1406 }, error: null };
      }
      if (checkJob === "failed") {
        job = { id: "job-check", status: "failed", progress: { done: 400, total: 1406 }, error: "the machine working on this stopped before it finished" };
      }
      return ok({ bill_run_id: RUN_ID, counts: checkTiles(checked), stop: null, job });
    }
    if (path === `${run}/check/resume`) {
      checkJob = "running";
      checkPolls = 0;
      return ok({ job_id: "job-check", status_url: "/api/jobs/job-check", resumed: true }, 202);
    }
    if (path === `${run}/presence`) {
      return ok({ others: options.otherClerk === undefined ? [] : [{ name: options.otherClerk }], heartbeat_seconds: 30 });
    }
    if (path === `${run}/check/findings`) {
      if (options.moduleDown === true) {
        return Promise.reject(
          // The SERVER's stop envelope (check_api._stop_response, DEF-BIL-8510, DEF-BIL-8580):
          // what is down, who fixes it, and the stop's own reference.
          new ApiError(503, {
            code: "SYS-PROVIDER",
            message_key: "billing.bulkRun.check.down.meter_reads",
            params: { module: "meter_reads", who: "support", ref: "SBH-73FBC9D7" },
            trace_id: "73fbc9d7",
          }),
        );
      }
      if (query?.tag !== undefined && query.tag === options.holdTagRead) return new Promise(() => undefined);
      if (query?.tag !== undefined && query.tag === options.failTagRead) {
        return Promise.reject(
          new ApiError(500, { code: "SYS-INTERNAL", message_key: "api.error.unexpected", params: {}, trace_id: "t-10709" }),
        );
      }
      if (query?.tag !== undefined) {
        const served = checkTagPage(String(query.tag));
        // DEF-BIL-9005 — an account with TWO unread meters is two rows.
        if (options.twoUnreadMeters === true && String(query.tag) === "missing_read") {
          served.results = [...served.results, { ...served.results[0], service_code: "electric" }];
        }
        const results = served.results.filter((row) => !fixedAccounts.has(row.account_id));
        return ok({ ...served, results, count: results.length });
      }
      if (query?.account !== undefined) return ok(checkAccount(String(query.account)));
      if (query?.list === "ready") return ok(checkReady(String(query.kind ?? "")));
      return ok(checkSummary(options.summaryBehind === true ? false : checked));
    }
    // DEF-BIL-10121 — the pricing check (apps/billing/api.py `run_pricing_shadow`).
    if (path === `${run}/pricing-shadow`) {
      const state = options.pricing ?? "none";
      if (state === "hold") return new Promise(() => undefined);
      if (state === "failed") {
        return Promise.reject(new ApiError(500, { code: "SYS-500", message_key: "errors.server", trace_id: "5aa0c1e2" }));
      }
      // A one-off run: the server refuses the comparison on purpose (409).
      if (state === "no_cycle") {
        return Promise.reject(
          new ApiError(409, { code: "BIL-409", message_key: "billing.oneTime.notACycleRun", trace_id: "5aa0c1e3" }),
        );
      }
      // A server that predates the endpoint answers the generic empty list.
      if (state === "unreadable") return ok({ count: 0, next: null, previous: null, results: [] });
      return ok(pricingShadow(state));
    }
    if (path === `${run}/check/report`) return ok(checkReport(String(query?.status ?? "")));
    if (path === `${run}/check/decisions`) return ok({ recorded: 1 }, 201);
    if (path === `${run}/check/recheck`) return ok({ rechecked: 1, background: false, counts: checkTiles() });
    if (path === `${run}/check/fix`) {
      fixedAccounts.add(String((body as { account_id?: unknown } | undefined)?.account_id ?? ""));
      return ok({ fix: "set_plan", written: {}, account: checkAccount("acc-2") });
    }
    if (path === `${run}/check/leave-out` || path === `${run}/check/put-back`) return ok({ counts: checkTiles() });
    if (path === `${run}/sign-off-summary`) return ok(signOffSummary({ planLater: options.planLater === true }));
    if (path === `${run}/not-in-run/leave-for-next-cycle`) return ok({ marked: 1 });
    if (path === `${run}/not-in-run`) return ok(notInRun(String(query?.group ?? ""), phase === "issued"));
    // ── Calculate · Sign off · Send ──────────────────────────────────────
    if (path === `${run}/calculate`) {
      return ok({ job_id: "job-1", status_url: "/jobs/job-1", bill_run_id: RUN_ID, unavailable: [] }, 202);
    }
    if (path === "/jobs/job-1") {
      jobPolls += 1;
      const done = jobPolls >= 2;
      if (done) phase = "calculated";
      const progress =
        options.calculatingLive === true && !done
          ? { done: 3000, total: 40009, stage: "preparing" }
          : { done: done ? 1371 : 754, total: 1371 };
      return ok({ id: "job-1", kind: "bill_run_calculate", status: done ? "succeeded" : "running", progress, result_link: null, error: null });
    }
    if (path === `${run}/summary`) return ok(summary());
    if (path === `${run}/totals`) return ok(totals());
    if (path === `${run}/read-lock`) return ok(readLock(phase));
    if (path.startsWith(`${run}/breaks`)) {
      if (path.endsWith("/retry")) return ok({ bill_run_id: RUN_ID, account_id: "acc-20", invoice_id: "inv-9", invoice_no: null, resolution: "retried" });
      if (options.sendFailure === true && phase === "issued" && !sendRetried) {
        const served = breaks();
        return ok({
          ...served,
          breaks: [
            ...served.breaks,
            { id: "b9", account_id: "acc-8", account_no: "AC-2026-00008", stage: "send", reason: "line_has_no_gl_account", detail: "", retryable: true, resolution: null, job_id: null, raised_at: null, updated_at: null },
          ],
        });
      }
      return ok(breaks());
    }
    if (path === `${run}/release`) {
      if (phase === "issued" && options.sendFailure === true) sendRetried = true;
      phase = phase === "issued" ? phase : "authorised";
      return ok({ id: "rel-1", created: true, bill_run_id: RUN_ID, confirmed_at: "2026-10-01T09:42:00-05:00", released_at: null, account_count: 1371, bill_count: 1371, total_amount: "214386.5200", currency: "USD" }, 201);
    }
    if (path === `${run}/issue` && (body as { background?: unknown } | undefined)?.background === true) {
      // DEF-BIL-8422 — the issue pass as a job, with its n of N.
      return ok({ job_id: "job-issue", status_url: "/jobs/job-issue", bill_run_id: RUN_ID, background: true, unavailable: [] }, 202);
    }
    if (path === `${run}/issue/progress`) {
      // DEF-BIL-8710 — the Send polls its own read (it hands a dead worker's
      // Send back), never `GET /jobs/{id}`.
      issuePolls += 1;
      if (options.sendStopped === true && issuePolls >= 2) {
        return ok({
          bill_run_id: RUN_ID,
          job: {
            id: "job-issue",
            status: "failed",
            progress: { done: 0, total: 1371 },
            error: "IssuePassStopped: the issue pass stopped",
            resumed: false,
            stopped: { code: "same_fault_on_bill_after_bill", message_key: "billing.bulkRun.send.stoppedSameFault", params: { count: 10 } },
          },
        });
      }
      const done = issuePolls >= 3;
      if (done) phase = "issued";
      return ok({ bill_run_id: RUN_ID, job: { id: "job-issue", status: done ? "succeeded" : "running", progress: { done: done ? 1369 : 612, total: 1371 }, error: null, resumed: false } });
    }
    if (path === `${run}/issue`) {
      phase = "issued";
      if (options.delay !== undefined) {
        return new Promise((resolve) => setTimeout(() => resolve({ status: 202, data: {}, etag: null, notModified: false }), 1500));
      }
      return ok({}, 202);
    }
    // DEF-BIL-9255 — Discard a draft run.
    if (path === `${run}/discard` && method === "POST") return ok({ id: RUN_ID, status: "abandoned", drafts_removed: 1371 });
    if (path === `${run}/catch-up`) return ok({ id: "run-child", parent_run_id: RUN_ID, status: "draft", period_start: "2026-09-01", period_end: "2026-09-30" }, 201);
    if (path === "/plans") return ok({ count: 2, next: null, previous: null, results: [{ id: "plan-1", code: "RES", name: "Residential Standard" }, { id: "plan-2", code: "COM", name: "Commercial" }], rollup: {} });
    return ok({ count: 0, next: null, previous: null, results: [] });
  }

  const client = {
    get: (path: string, opts?: { query?: Record<string, unknown> }) => answer("GET", path, undefined, opts?.query),
    post: (path: string, body?: unknown) => answer("POST", path, body),
    request: (path: string, opts?: { body?: unknown; method?: string }) => answer(opts?.method ?? "GET", path, opts?.body),
  } as unknown as ApiClient;
  return { client, calls, releaseRunRead };
}
