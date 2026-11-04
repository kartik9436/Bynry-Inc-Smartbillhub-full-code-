// ── Trace ──────────────────────────────────────────────
// Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md F18
//           (client types and calls) · A1–A10 (served)
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/*.png + inventory.md
// Stories:  US-BIL-036 … US-BIL-041 (EP-BIL-01 §AMENDED 2026-09-30)
// Defects:  DEF-BIL-8216 (grouped findings read — closed: the server's) ·
//           DEF-BIL-8222 (one template)
// ───────────────────────────────────────────────────────
/**
 * THE BULK BILL RUN'S CLIENT — every read and write the redrawn four-step
 * screen makes, typed to the drawing.
 *
 *   * `GET /billing/runs/scope-preview` and `POST /billing/runs` — the Scope
 *     step, whole (`apps/billing/run_scope.py`, `run_scope_api.py`). Every
 *     refusal and warning arrives at once, each on its field, with its own
 *     `billing.runScope.*` key.
 *   * The Check (`apps/billing/check_api.py`): start it as a job and read its
 *     progress, the SERVER's grouped findings (categories → tags with account
 *     counts, one tag's accounts paged, one account, the Ready list), answer a
 *     tag, re-check named accounts, write an inline fix through the owning
 *     module, leave a ready account out and put it back, and the Check report.
 *   * Sign off's summary, Not in this run (paged), Leave for next cycle.
 *   * `GET /billing/runs/{id}`, `/summary`, `/calculate` (a background job
 *     with progress), `/release`, `/issue`, `/catch-up`, `GET /jobs/{id}` —
 *     re-exported or wrapped from their existing homes, never posted twice
 *     (law 5).
 *
 * ⚠ The grouped Check read used to be built IN THE BROWSER from `/findings`
 * and `/exceptions` (`groupFindings`, an interim client taxonomy) — the whole
 * run in one response, an NFR-3 breach at 40,000 accounts. It is deleted with
 * DEF-BIL-8216; the server owns the taxonomy (`apps/billing/check_taxonomy`).
 */
import { api } from "@/api/client";
import type { ApiClient, ApiResponse, JobRecord } from "@/api/client";
import type { BillRunCreated, BillRunHistoryRow } from "@/api/endpoints";
import { readListPage } from "@/api/paginated";
import type { PagedRows, Paginated } from "@/api/paginated";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// SCOPE — GET /billing/runs/scope-preview · POST /billing/runs (served)
// ══════════════════════════════════════════════════════════════════════════

/** The seven inputs of *What to bill*, as typed. Blank is sent as blank so the
 *  server answers the refusal for it (`run_scope.check_scope`). */
export interface ScopeFields {
  label: string;
  cycle_id: string;
  period_start: string;
  period_end: string;
  bill_date: string;
  due_days: string;
  template_id: string;
}

export const SCOPE_FIELD_NAMES = [
  "label",
  "cycle_id",
  "period_start",
  "period_end",
  "bill_date",
  "due_days",
  "template_id",
] as const;
export type ScopeFieldName = (typeof SCOPE_FIELD_NAMES)[number];

/** One refusal or warning, on its field (`null` = about the run as a whole). */
export interface ScopeProblem {
  code: string;
  severity: "refusal" | "warning";
  field: string | null;
  message_key: string;
  params: Record<string, unknown>;
}

/** Row 15 — every figure a COUNT, and `null` when a module did not answer. */
export interface ScopeCounts {
  units_in_cycle: number | null;
  accounts_to_bill: number | null;
  regular_accounts: number | null;
  master_accounts: number | null;
  meters: number | null;
  sub_meters: number | null;
  behind_the_meter: number | null;
  missing_meter: number | null;
  units_nobody_to_bill: number | null;
}

/** Row 30 — the previous run's three account counts, only where its saved
 *  bills prove them; `null` otherwise. */
export interface ScopeLastRunCounts {
  run_id: string;
  accounts_to_bill: number;
  regular_accounts: number;
  master_accounts: number;
}

export interface ScopeRunRef {
  run_id: string;
  run_no: string | null;
  label: string | null;
  period_start: string;
  period_end: string;
}

export type ContinuityState = "continuous" | "gap" | "overlap" | "first" | "unknown";

export interface ScopeContinuity {
  state: ContinuityState;
  run?: ScopeRunRef;
  from?: string;
  to?: string;
  days?: number;
}

/** Row 31 — the cycle's own facts. */
export interface ScopeCycle {
  id: string;
  code: string | null;
  name: string | null;
  frequency: string | null;
  reads_start_day: number | null;
  days_to_complete: number | null;
  bill_day: number | null;
  due_days: number | null;
  routes: number;
  first_run_date: string | null;
  runs_so_far: number;
  status: string | null;
}

export interface ScopePreview {
  refusals: ScopeProblem[];
  warnings: ScopeProblem[];
  can_start: boolean;
  counts: ScopeCounts | null;
  last_run_counts: ScopeLastRunCounts | null;
  continuity: ScopeContinuity;
  previous_run: ScopeRunRef | null;
  cycle: ScopeCycle | null;
  /** Paged (NFR-3), newest first, through the one run-list read. */
  previous_runs: Paginated<BillRunHistoryRow> | null;
}

export const scopePreviewKey = (fields: ScopeFields, page: number, per: number) =>
  ["billing", "bulk-run", "scope-preview", fields, page, per] as const;

export async function getScopePreview(
  fields: ScopeFields,
  page: number,
  per: number,
  client: ApiClient = api,
): Promise<ScopePreview> {
  return requireData(
    await client.get<ScopePreview>("/billing/runs/scope-preview", {
      query: { ...fields, page, per },
    }),
  );
}

/** One row of Scope's *Nobody to bill* panel (DEF-BIL-8221). */
export interface ScopeNobodyRow {
  unit_id: string;
  address: string | null;
  unit: string | null;
  services: string[];
  /** `account_id` — record links (PO 2026-10-19), an address ingredient only. */
  last_account: { account_no: string; account_id?: string; moved_out: string | null } | null;
}

/** One row of Scope's *Missing meter* panel (DEF-BIL-8221). */
export interface ScopeMissingMeterRow {
  unit_id: string;
  address: string | null;
  unit: string | null;
  service: string | null;
  account_no: string | null;
  /** Record links (PO 2026-10-19) — builds the account's address only. */
  account_id?: string | null;
}

export type ScopeListName = "nobody" | "missing_meter";

export const scopeListKey = (cycleId: string, list: ScopeListName, page: number, per: number) =>
  ["bulk-run", "scope-list", cycleId, list, page, per] as const;

/** `GET /billing/runs/scope-list` — the rows behind a Scope count, paged. */
export function getScopeList<Row extends ScopeNobodyRow | ScopeMissingMeterRow>(
  cycleId: string,
  list: ScopeListName,
  page: number,
  per: number,
  client: ApiClient = api,
): Promise<PagedRows<Row>> {
  return readListPage<Row>("/billing/runs/scope-list", { cycle_id: cycleId, list, page, per }, client);
}

/** A bill template a run may start on — it has a published version (DEF-BIL-8222). */
export interface RunTemplateRow {
  id: string;
  name: string;
  version_no: number;
  category: string | null;
}

/**
 * `GET /billing/runs/scope-templates` — every bill template with a published
 * version, by name. The select asks for the largest page; a utility with more
 * templates than that pages them like any list (NFR-3).
 */
export function getRunTemplates(client: ApiClient = api): Promise<PagedRows<RunTemplateRow>> {
  return readListPage<RunTemplateRow>("/billing/runs/scope-templates", { page: 1, per: 200 }, client);
}

/** What `POST /billing/runs` answers on a 201: the run and its warnings. */
export interface BulkRunCreated extends BillRunCreated {
  warnings: ScopeProblem[];
}

/**
 * Start the run. **Run name and template are always sent** — the new screen
 * never relies on the server deriving them, which is why the TEMPORARY
 * derive-for-the-old-wizard path could be removed with `BillRunWizard`.
 * A refusal answers 422 (or 409 for a duplicate) with EVERY problem in
 * `field_errors` and the warnings in `params.warnings`.
 */
export async function createBulkRun(
  fields: ScopeFields,
  client: ApiClient = api,
): Promise<BulkRunCreated> {
  const body = {
    label: fields.label,
    cycle_id: fields.cycle_id,
    period_start: fields.period_start,
    period_end: fields.period_end,
    bill_date: fields.bill_date,
    due_days: fields.due_days === "" ? null : fields.due_days,
    template_id: fields.template_id,
  };
  return requireData(await client.post<BulkRunCreated>("/billing/runs", body));
}

// ══════════════════════════════════════════════════════════════════════════
// SEVERITY — the served taxonomy's three (`check_taxonomy.SEVERITIES`)
// ══════════════════════════════════════════════════════════════════════════

export type Severity = "blocks" | "decision" | "warning";

// ══════════════════════════════════════════════════════════════════════════
// CHECK — the SAVED check (served: apps/billing/check_api.py, plan A3–A6)
// ══════════════════════════════════════════════════════════════════════════
//
// The engine lane's routes. Each result is SAVED per account with the time it
// was checked (OQ-843 option C), so these read what was found rather than
// re-computing it on every view.

/** The Check's tiles, as the server counts them over its saved results. */
export interface CheckTiles {
  accounts: number;
  ready: number;
  /** DEF-BIL-8554 — the accounts Calculate will actually price: Ready minus
   *  the ones an answer holds, the waived ones and the ones still waiting on a
   *  must-answer case. *Price N* is this, never `ready`. */
  to_price?: number;
  held?: number;
  waived?: number;
  undecided?: number;
  decisions: number;
  blocked: number;
  silent: number;
  warnings: number;
  problem_types: number;
  stale: number;
  checked_from: string | null;
  checked_at: string | null;
}

/** `GET …/check` — the tiles, plus the running check job when there is one. */
export interface RunCheckState {
  bill_run_id: string;
  counts: CheckTiles;
  stop: Record<string, unknown> | null;
  job: {
    id: string;
    status: string;
    progress: { done: number; total: number } | null;
    error: unknown;
    /** The server handed a worker-less job back to the billing worker on this read (DEF-BIL-8511). */
    resumed?: boolean;
  } | null;
}

/** `POST …/presence` — the screen's heartbeat, answered with who else has the
 *  run open (DEF-BIL-8512, clerk check F4). A courtesy, never a lock. */
export async function touchRunPresence(
  runId: string,
  client: ApiClient = api,
): Promise<{ others: { name: string }[]; heartbeat_seconds: number }> {
  return requireData(
    await client.post<{ others: { name: string }[]; heartbeat_seconds: number }>(
      `/billing/runs/${encodeURIComponent(runId)}/presence`,
      {},
    ),
  );
}

/** `POST …/check/resume` — hand a stopped Check back to the billing worker
 *  (DEF-BIL-8511). `resumed: false` with `why` when nothing was done: the job
 *  is still being worked, already waiting, or finished. */
export async function resumeCheck(
  runId: string,
  client: ApiClient = api,
): Promise<{ resumed: boolean; why?: string; job_id?: string }> {
  return requireData(
    await client.post<{ resumed: boolean; why?: string; job_id?: string }>(checkPath(runId, "/resume"), {}),
  );
}

const checkPath = (runId: string, rest = "") =>
  `/billing/runs/${encodeURIComponent(runId)}/check${rest}`;

export async function getRunCheck(runId: string, client: ApiClient = api): Promise<RunCheckState> {
  return requireData(await client.get<RunCheckState>(checkPath(runId)));
}

/** `POST …/check/recheck` — re-check NAMED accounts only (DEF-BIL-8219);
 *  `categories` re-runs only those Check categories and what is downstream
 *  of them (DEF-BIL-8286). */
export async function recheckAccounts(
  runId: string,
  accountIds: readonly string[],
  client: ApiClient = api,
  categories?: readonly string[],
): Promise<{ rechecked?: number; background: boolean }> {
  return requireData(
    await client.post<{ rechecked?: number; background: boolean }>(checkPath(runId, "/recheck"), {
      account_ids: [...accountIds],
      ...(categories === undefined ? {} : { categories: [...categories] }),
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CALCULATE — the job's progress (served: GET /jobs/{id})
// ══════════════════════════════════════════════════════════════════════════

export function jobProgress(job: JobRecord | null): { done: number; total: number } | null {
  return job?.progress ?? null;
}

// ══════════════════════════════════════════════════════════════════════════
// CHECK — THE SERVED GROUPED READ (DEF-BIL-8216 closed · plan A4–A6, A9)
// ══════════════════════════════════════════════════════════════════════════
//
// `GET …/check/findings` answers the categories → tags with ACCOUNT counts; a
// tag's accounts are ONE page of `?tag=` (NFR-3 — never the whole run in the
// browser); one account's every problem is `?account=`; Ready to bill is
// `?list=ready`. The taxonomy is the SERVER's (`apps/billing/check_taxonomy`):
// a tag is one engine code, named by its `label_key`.

export type CheckSeverity = "blocks" | "decision" | "warning" | null;

/** The inline fix the Check can write for a row, through the owning module
 *  (`POST …/check/fix`, DEF-BIL-8218). `null` → the row links to its screen. */
export type FixHere = "set_plan" | "set_size" | "set_city_limits" | null;

export interface CheckTag {
  code: string;
  category: string;
  severity: CheckSeverity;
  fix: string;
  fix_action: { kind?: string; screen?: string };
  label_key: string;
  suggests: boolean;
  count: number;
  choices: string[];
  default_choice: string | null;
  answer_for_all: string | null;
  fix_here: FixHere;
}

export interface CheckCategoryGroup {
  category: string;
  label_key: string;
  count: number;
  tags: CheckTag[];
}

export interface CheckSummary {
  bill_run_id: string;
  checked: boolean;
  tiles: CheckTiles & { left_out?: number };
  categories: CheckCategoryGroup[];
  unmapped: string[];
  stop: Record<string, unknown> | null;
  unavailable: { code: string; reason: string }[];
  units_with_nobody_to_bill: number | null;
}

export interface CheckTagRow {
  account_id: string;
  account_no: string;
  customer_name: string | null;
  address: string | null;
  unit_label: string | null;
  unit_id: string | null;
  service_code: string | null;
  /** DEF-BIL-8701 — the in-service meters' NUMBERS on this row's service, as
   *  Meter Reads serves them (never an id, B14 rule 31); [] when none. */
  meters?: string[];
  message_key: string | null;
  params: Record<string, unknown>;
  also_has: string[];
  fix_here: FixHere;
  /** The answers THIS row may take (DEF-BIL-8472) — narrower than the tag's
   *  where the row's facts say so (an overlap: Investigate only). */
  choices?: string[];
  answer: string | null;
  /** DEF-BIL-10200 — `default`: the answer the run takes when nobody answered
   *  (a late fee bills unless it is waived on that account). */
  answer_source: "account" | "tag" | "default" | null;
  /** DEF-BIL-8551 — an Estimate's recorded quantity and unit (both or neither). */
  answer_quantity?: string | null;
  answer_unit?: string | null;
  /** The account's own average month (metering's figure, DEF-2859) — what the
   *  estimate box starts from; null when there is no history. */
  basis?: { quantity: string; unit: string; high: string | null; low: string | null; months: number } | null;
  stale: boolean;
}

export interface CheckTagPage {
  tag: CheckTag;
  results: CheckTagRow[];
  count: number;
  page: number;
  per: number;
  /** DEF-BIL-10200 — the late-fee tag only: the fees this run ADDS over the
   *  WHOLE tag (never the page), less the accounts waived. `total` is a
   *  2-place decimal string. */
  late_fees?: { accounts: number; total: string; waived: number; currency: string | null };
}

export interface CheckAccountFinding {
  code: string;
  category: string;
  severity: CheckSeverity;
  service_code: string | null;
  message_key: string | null;
  params: Record<string, unknown>;
  tag: { code: string; label_key: string; fix_action: { screen?: string } };
  choices: string[];
  fix_here: FixHere;
  answer: string | null;
}

export interface CheckAccount {
  account_id: string;
  account_no: string;
  account_kind: string | null;
  customer_name: string | null;
  address: string | null;
  unit_label: string | null;
  status: string;
  findings: CheckAccountFinding[];
}

export interface CheckReadyRow {
  account_id: string;
  account_no: string;
  account_kind: string | null;
  left_out: boolean;
  customer_name: string | null;
  address: string | null;
  unit_label: string | null;
  /** DEF-BIL-8414 — image 21's three columns, served per page. */
  services: string[];
  plan_name: string | null;
  all_read: boolean;
}

export interface CheckReadyPage {
  results: CheckReadyRow[];
  count: number;
  left_out: number;
  page: number;
  per: number;
}

export const checkSummaryKey = (runId: string) => ["bulk-run", runId, "check", "summary"] as const;
export const checkTagKey = (runId: string, code: string, page: number, per: number, q: string) =>
  ["bulk-run", runId, "check", "tag", code, page, per, q] as const;
export const checkAccountKey = (runId: string, accountId: string) =>
  ["bulk-run", runId, "check", "account", accountId] as const;
export const checkReadyKey = (runId: string, page: number, per: number, q: string, kind: string) =>
  ["bulk-run", runId, "check", "ready", page, per, q, kind] as const;
/** Every Check read at once — what an answer, a fix or a re-check refreshes. */
export const checkReadsKey = (runId: string) => ["bulk-run", runId, "check"] as const;

export async function getCheckSummary(runId: string, client: ApiClient = api): Promise<CheckSummary> {
  return requireData(await client.get<CheckSummary>(checkPath(runId, "/findings")));
}

export async function getCheckTag(
  runId: string,
  code: string,
  page: number,
  per: number,
  q: string,
  client: ApiClient = api,
  /** `DEF-BIL-10709` — false sends `sweep=0`: a pane sweeps once, when it opens. */
  sweep: boolean = true,
): Promise<CheckTagPage> {
  const query = sweep ? { tag: code, page, per, q } : { tag: code, page, per, q, sweep: 0 };
  return requireData(await client.get<CheckTagPage>(checkPath(runId, "/findings"), { query }));
}

export async function getCheckAccount(runId: string, accountId: string, client: ApiClient = api): Promise<CheckAccount> {
  return requireData(await client.get<CheckAccount>(checkPath(runId, "/findings"), { query: { account: accountId } }));
}

export async function getCheckReady(
  runId: string,
  params: { page: number; per: number; q: string; kind: string },
  client: ApiClient = api,
): Promise<CheckReadyPage> {
  return requireData(
    await client.get<CheckReadyPage>(checkPath(runId, "/findings"), {
      query: { list: "ready", page: params.page, per: params.per, q: params.q, kind: params.kind },
    }),
  );
}

/**
 * `POST …/issue` asking for the WORKER (DEF-BIL-8422): the issue pass reports
 * done/total after every bill (`issue_run`'s `on_progress`), so Send can show
 * *n of N* like Calculate. The server decides — with no worker it issues
 * inline and answers without a job, and Send then has nothing to count.
 */
export async function issueRunMaybeBackground(
  runId: string,
  body: { issued_at: string },
  client: ApiClient = api,
): Promise<{ background: true; job_id: string } | { background: false }> {
  const response = await client.post<Record<string, unknown>>(`/billing/runs/${encodeURIComponent(runId)}/issue`, {
    ...body,
    background: true,
  });
  const data = (response.data ?? {}) as Record<string, unknown>;
  if (response.status === 202 && data.background === true && typeof data.job_id === "string") {
    return { background: true, job_id: data.job_id };
  }
  return { background: false };
}

/** `GET …/issue/progress?job=` — the Send's *n of N* (DEF-BIL-8710). Unlike
 *  `GET /jobs/{id}`, this read hands a Send whose worker died back to the
 *  billing worker, as the Check's own read does (DEF-BIL-8511); `resumed`
 *  says it did. `job: null` when the job named is not this run's Send. */
export interface RunIssueState {
  bill_run_id: string;
  job: {
    id: string;
    status: string;
    progress: { done: number; total: number } | null;
    error: unknown;
    resumed?: boolean;
    /** DEF-BIL-8747 — a Send STOPPED by the same fault on bill after bill:
     *  the catalogue key the screen shows and its params. Null otherwise. */
    stopped?: { code: string; message_key: string; params: Record<string, unknown> } | null;
  } | null;
}

export async function getIssueProgress(runId: string, jobId: string, client: ApiClient = api): Promise<RunIssueState> {
  return requireData(
    await client.get<RunIssueState>(`/billing/runs/${encodeURIComponent(runId)}/issue/progress`, {
      query: { job: jobId },
    }),
  );
}

/** `POST …/check` — start (or re-run) the Check as a job; its progress is
 *  `GET …/check`'s `job.progress` (*Checking accounts — n of N*, DEF-BIL-8224). */
export async function startCheck(
  runId: string,
  client: ApiClient = api,
): Promise<{ job_id?: string; background: boolean }> {
  return requireData(
    await client.post<{ job_id?: string; background: boolean }>(checkPath(runId), { background: true }),
  );
}

/** `POST …/check/decisions` — one tag, for all (`scope: "all"`) or named accounts. */
export async function decideCheck(
  runId: string,
  body: {
    case: string;
    choice: string;
    scope: "all" | "accounts";
    account_ids?: string[];
    service_code?: string | null;
    reason?: string;
    /** An Estimate's typed quantity and its unit (DEF-BIL-8551). */
    amount?: string;
    unit?: string;
  },
  client: ApiClient = api,
): Promise<unknown> {
  return requireData(await client.post<unknown>(checkPath(runId, "/decisions"), body));
}

/** `POST …/check/fix` — the fact written by its OWNING module, then that one
 *  account re-checked (DEF-BIL-8218). */
export async function fixCheck(
  runId: string,
  body: { account_id: string; fix: Exclude<FixHere, null>; plan_id?: string; size_class?: string; service_code?: string | null; inside_city_limits?: boolean },
  client: ApiClient = api,
): Promise<{ account: CheckAccount }> {
  return requireData(await client.post<{ account: CheckAccount }>(checkPath(runId, "/fix"), body));
}

/** Leave READY accounts out of this run, or put them back (DEF-BIL-8217). */
export async function leaveOutAccounts(
  runId: string,
  accountIds: readonly string[],
  back: boolean,
  client: ApiClient = api,
): Promise<{ counts: CheckTiles }> {
  return requireData(
    await client.post<{ counts: CheckTiles }>(checkPath(runId, back ? "/put-back" : "/leave-out"), {
      account_ids: [...accountIds],
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// SIGN OFF — `GET …/sign-off-summary` (DEF-BIL-8220 · plan A8)
// ══════════════════════════════════════════════════════════════════════════

export interface SignOffSummary {
  bill_run_id: string;
  sent: boolean;
  run_summary: {
    bills: number;
    accounts_to_bill: number;
    this_run_charges: string;
    payments_applied: number | null;
    /** DEF-BIL-8682 — how many payments make up `payments_applied` below;
     *  null where the run has no payments/credits split. */
    payments_count?: number | null;
    amount_due: string | null;
  };
  who_is_billed: {
    accounts: {
      to_bill: number;
      billed: number;
      regular: number;
      master: number;
      not_billed: number;
      blocked: number;
      held: number;
      nothing_to_bill: number;
      left_out: number;
      /** DEF-BIL-8416 — waived by the clerk: not billed, never "failed". */
      waived?: number;
      failed_to_draft: number;
      reconciles: boolean;
    };
    units: {
      in_cycle: number | null;
      billed: number;
      own_account: number;
      through_master: number;
      not_billed: number;
      account_not_billed: number;
      nothing_to_bill: number;
      nobody_to_bill: number;
      reconciles: boolean;
    };
  };
  usage_and_charges: {
    services: {
      service_code: string;
      bills: number;
      usage: { quantity: string; unit: string }[];
      usage_charges: string;
      base_charges: string;
      total: string;
    }[];
    services_subtotal: string;
    other: { taxes: string; fees: string; credits_and_adjustments: string };
    this_run_charges: string;
    reconciles: boolean;
  };
  payments_and_balances: {
    previous_balance: string | null;
    payments_and_credits_applied: string | null;
    accounts_with_payments_applied: number | null;
    /** DEF-BIL-8682 — the figure above parted by payments' own type column
     *  (payments + credits = it, exactly); all four null where any bill fell
     *  back to the open-bills window, which has no such split. */
    payments_applied?: string | null;
    payments_count?: number | null;
    credits_applied?: string | null;
    credits_count?: number | null;
    this_run_charges: string;
    /** DEF-BIL-8720 — what the bills hold back as a payment plan's part not
     *  yet due (BR-BIL-1061); already taken off `amount_due`. */
    plan_not_yet_due?: string | null;
    amount_due: string | null;
    reconciles: boolean;
    how_paid: Record<"credit_covers" | "level_pay" | "autopay" | "plan_instalment" | "by_due_date", { bills: number; amount: string }> | null;
    /** DEF-BIL-8242 — each drafted bill the account's credit covers in full; one page. */
    credit_covers_bills?: {
      results: { account_id: string; account_no: string | null; bill_total: string; credit: string; left_after: string; currency: string | null }[];
      count: number;
    };
  };
  by_customer_type: { category: string | null; bills: number; amount: string }[];
  /** `account_id` — record links (PO 2026-10-19); absent on a summary saved
   *  before the field existed, and the number then stays text. */
  waived: { account_no: string; account_id?: string | null; amount: string; currency: string }[];
  waived_total: string | null;
  currency: string | null;
}

export const signOffSummaryKey = (runId: string) => ["bulk-run", runId, "sign-off-summary"] as const;

export async function getSignOffSummary(runId: string, client: ApiClient = api): Promise<SignOffSummary> {
  return requireData(
    await client.get<SignOffSummary>(`/billing/runs/${encodeURIComponent(runId)}/sign-off-summary`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// NOT IN THIS RUN — `GET …/not-in-run` (plan B20 · A9)
// ══════════════════════════════════════════════════════════════════════════

export type NotInRunGroup = "blocked" | "held" | "nothing" | "left_out" | "waived" | "nobody";

export interface ServedNotInRunRow {
  key: string;
  kind: "account" | "unit";
  group: NotInRunGroup;
  reason: string | null;
  also: number;
  account_id: string | null;
  account_no: string | null;
  account_kind: string | null;
  unit_id: string | null;
  customer_name: string | null;
  address: string | null;
  unit_label: string | null;
  queue: {
    reason_code: string;
    held_on: string;
    next_cycle: boolean;
    resolved_by_run_id: string | null;
    age_days?: number;
  } | null;
}

export interface ServedNotInRun {
  bill_run_id: string;
  sent: boolean;
  counts: Record<NotInRunGroup, number> & { accounts: number; units: number };
  results: ServedNotInRunRow[];
  count: number;
  page: number;
  per: number;
}

export const notInRunKey = (runId: string, group: string, page: number, per: number) =>
  ["bulk-run", runId, "not-in-run", group, page, per] as const;

export async function getNotInRun(
  runId: string,
  params: { group: string; page: number; per: number; as_of?: string },
  client: ApiClient = api,
): Promise<ServedNotInRun> {
  const query: Record<string, string | number> = { page: params.page, per: params.per };
  if (params.group !== "" && params.group !== "all") query.group = params.group;
  if (params.as_of !== undefined) query.as_of = params.as_of;
  return requireData(
    await client.get<ServedNotInRun>(`/billing/runs/${encodeURIComponent(runId)}/not-in-run`, { query }),
  );
}

/** *Leave for next cycle* on accounts this run left in Pending billing. */
export async function leaveForNextCycle(
  runId: string,
  accountIds: readonly string[],
  at: string,
  client: ApiClient = api,
): Promise<{ marked: number }> {
  return requireData(
    await client.post<{ marked: number }>(
      `/billing/runs/${encodeURIComponent(runId)}/not-in-run/leave-for-next-cycle`,
      { account_ids: [...accountIds], at },
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE CHECK REPORT — `GET …/check/report` (a sent run's Check, as at Send)
// ══════════════════════════════════════════════════════════════════════════

export interface CheckReport {
  bill_run_id: string;
  sent: boolean;
  tiles: CheckTiles;
  categories: CheckCategoryGroup[];
  accounts: {
    results: {
      account_id: string;
      account_no: string;
      status: string;
      checked_at: string;
      problems: { code: string; severity: CheckSeverity; service_code: string | null }[];
      /** DEF-BIL-8555 · clerk check A6 — who answered what, when. */
      decisions?: CheckReportDecision[];
    }[];
    count: number;
    page: number;
    per: number;
  };
}

export interface CheckReportDecision {
  case: string;
  choice: string;
  /** `account` — answered on the row; `all` — the tag's *Answer for all*. */
  scope: "account" | "all";
  reason: string | null;
  quantity: string | null;
  unit: string | null;
  service_code: string | null;
  decided_by: string | null;
  decided_at: string;
}

export const checkReportKey = (runId: string, page: number, per: number, status: string) =>
  ["bulk-run", runId, "check-report", page, per, status] as const;

export async function getCheckReport(
  runId: string,
  params: { page: number; per: number; status: string },
  client: ApiClient = api,
): Promise<CheckReport> {
  const query: Record<string, string | number> = { page: params.page, per: params.per };
  if (params.status !== "") query.status = params.status;
  return requireData(await client.get<CheckReport>(checkPath(runId, "/report"), { query }));
}
