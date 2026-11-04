// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-015 · US-BIL-016 · US-BIL-017 · US-BIL-031 (corrections) ·
//           US-BIL-018 · US-BIL-019 · US-BIL-020 (budget billing) ·
//           US-BIL-021 (the bill-layout chooser) · US-BIL-022 (the document) ·
//           US-BIL-006 (the pending-billing queue)
//           Screens: S30 (Fix a bill · Budget Bills · the document panel ·
//           the pending queue) · S8 (Configure → Templates)
// Rules:    BR-BIL-014 (nothing money-bearing before approval) · BR-BIL-041
//           (the mechanism is DERIVED — this client never sends one) ·
//           BR-BIL-044 (approval binds the hashed artifact) · BR-BIL-017 ·
//           BR-BIL-021 · BR-BIL-026 · BR-BIL-030 · BR-BIL-027 · BR-SHL-011 ·
//           BR-SHL-023 (one money path) · CLAUDE.md rule 2 (every money figure
//           travels with its CHAR(3)) · rule 4 (a correction is NEW ROWS)
// ───────────────────────────────────────────────────────
// The typed wrappers for the fifteen billing routes mounted on 2026-08-16.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE AND NOT AN APPENDIX TO `endpoints.ts`
// ══════════════════════════════════════════════════════════════════════════
// `endpoints.ts` is 7,200 lines and every lane in this repo appends to it, so on
// any given afternoon it holds two or three lanes' half-finished work at once.
// The `bankRecEndpoints.ts` precedent, for the same reason and stated the same
// way: one family, one file, one lane's diff. Nothing here re-exports or
// shadows anything `endpoints.ts` already publishes.
//
// ══════════════════════════════════════════════════════════════════════════
// EVERY ROUTE BELOW IS SERVED
// ══════════════════════════════════════════════════════════════════════════
// `apps/billing/corrections_api.py`, `budget_api.py`, `documents_api.py` and
// `templates_api.py` mount them and `config/urls.py` includes all four, so these
// types describe a LIVE contract. They are read off the server's own payload
// builders field for field: a field the server does not send is not typed here.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TYPE DECISIONS THAT MATTER
// ══════════════════════════════════════════════════════════════════════════
//   · **Money is `string` and never `number`.** NUMERIC(18,6) does not survive
//     an IEEE double, and a screen that received `-19.92` as a float would print
//     a different correction from the one the approver signed.
//   · **`string | null` is not `?? "0"`.** `computed_level`, `net_delta` and
//     `bills` are nullable because the server can genuinely not know — an
//     account with no billing history has NO level, and `0.00` would read as
//     "this customer pays nothing". Each null rides beside its own
//     `*_unavailable` sentence, and callers render the sentence.
//   · **No wrapper sends a `mechanism`.** BR-BIL-041 derives it from the reason
//     and the server refuses one that is supplied; a client type with the field
//     would be an invitation to a silent underbilling.
import { acceptedJobId, api, pollJob } from "./client";
import type { ApiClient, ApiResponse, JobRecord, JobStatus } from "./client";
import type { DayShare } from "./endpoints";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported: `endpoints.ts` does not export it, and
 *  exporting it would be an edit to a file this lane is not committing. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** A gap the SERVER reports about itself. Rendered, never swallowed. */
export interface Unavailable {
  code: string;
  /** The rule for SUPPORT — rendered on `data-br-ref`, never as text. */
  br_ref: string;
  /** The catalogue key a clerk's sentence resolves through, in their own
   *  language (`DEF-BIL-5339`, 2026-09-15). OPTIONAL because six server lists
   *  feed `GapNotes` and only budget's carries it today; a gap without one
   *  still renders its `detail`, exactly as before. */
  message_key?: string;
  /** Plain English. On a gap WITH a `message_key` it is the id-free mirror of
   *  the `en` sentence (a backend test ties them); on one without, it is what
   *  the clerk reads. */
  detail: string;
}

// ══════════════════════════════════════════════════════════════════════════
// S30 FIX A BILL — /corrections (US-BIL-015 · 016 · 017 · 031)
// ══════════════════════════════════════════════════════════════════════════

/** BR-BIL-041's three classes, as the server names them. */
export const CORRECTION_CLASSES = ["restatement", "credit_only", "document"] as const;
export type CorrectionClass = (typeof CORRECTION_CLASSES)[number];

export interface CorrectionReason {
  code: string;
  correction_class: string;
  /** TC-1a — the mechanism in the OPERATOR's words, never as an enum value. */
  mechanism_in_words: string;
}

/** One of the five things people bring to a correction screen that are NOT
 *  corrections. EP-BIL-04 §1a asks the screen to say so BY NAME. */
export interface RoutedElsewhere {
  code: string;
  detail: string;
}

export interface CorrectionCatalog {
  reasons: CorrectionReason[];
  classes: { code: string; mechanism_in_words: string }[];
  routed_elsewhere: RoutedElsewhere[];
  scope_kinds: string[];
  approver_role: string;
  /** Tenant settings. NULL beside a reason when they cannot be read — never
   *  the ratified defaults, which would print figures no tenant chose. */
  approval_mode: string | null;
  approval_mode_unavailable: string | null;
  backbill_window_months: number | null;
  backbill_window_unavailable: string | null;
  unavailable: Unavailable[];
}

export interface CorrectionCaseRow {
  id: string;
  case_no: string | null;
  status: string;
  /** DEF-BIL-10100 — closed with a reason and no bill corrected. */
  closed_without_correcting?: boolean;
  correction_class: string;
  reason_codes: string[];
  scope_kind: string;
  scope: Record<string, unknown>;
  /** NULL, not 0 — a case with no stored aggregate is one nobody can total. */
  bills: number | null;
  net_delta: string | null;
  currency: string | null;
  posting_period: string | null;
  preview_hash: string | null;
  initiated_by: string | null;
  approved_by: string | null;
  approved_on: string | null;
  executed_on: string | null;
  closed_reason: string | null;
  created_at: string | null;
}

export interface CorrectionImpactLine {
  kind?: string;
  description?: string;
  before?: string;
  after?: string;
  delta?: string;
  moved?: boolean;
  service?: string | null;
}

export interface CorrectionBillRow {
  invoice_id: string;
  account_id: string | null;
  delta_amount: string | null;
  currency: string;
  direction: string;
  status: string;
  failure_reason: string | null;
  warnings: { code?: string; detail?: string }[];
  impact: Record<string, unknown>;
  credit_note_id: string | null;
  rebill_invoice_id: string | null;
  document_instance_id: string | null;
}

/** BR-BIL-044's nine sections. Typed loosely on purpose: the server owns the
 *  contract and `section_order` is what the screen iterates, so a section added
 *  server-side appears without a client edit. */
export type CorrectionSections = Record<string, Record<string, unknown>>;

/**
 * One bill the back-bill cap took OUT of a case (`p137`'s fifth row).
 *
 * PO ruling 2026-09-15, on seven months of which one is past the cap and would
 * charge more: *"in such sitution 6 bills only ; 7th is not valid case"*. The
 * case proceeds with the six and this says which month was left out, and by how
 * much it missed. Figures and a CODE, never a sentence — the words a clerk
 * reads are the eleven catalogues' (B14 rule 35) and carry no rule id (rule 32).
 */
export interface CorrectionExcludedBill {
  invoice_id: string;
  invoice_no: string | null;
  account_id: string;
  period_start: string;
  period_end: string;
  code: string;
  /** How many months before the judgment day the period ended. */
  months: number;
  /** The TENANT's window, served rather than assumed — B14 rule 37: the drawing's
   *  "12-month cap" is an illustration, and this is the real number. */
  window_months: number;
  delta: string;
  currency: string;
}

export interface CorrectionCaseDetail extends CorrectionCaseRow {
  bills_detail: CorrectionBillRow[];
  /**
   * The bills the cap removed. **Empty on every case opened before 2026-09-15
   * and on every case where nothing was capped** — which are the same thing to
   * a reader here, honestly: neither had a bill removed.
   */
  excluded?: CorrectionExcludedBill[];
  /** The sentence that goes where an "undo" button would have been. */
  no_rollback: string;
  sections?: CorrectionSections;
  section_order?: string[];
  chain?: Record<string, unknown>;
  aggregate?: Record<string, unknown>;
  unavailable: Unavailable[];
  result?: {
    case_id: string;
    status: string;
    succeeded: string[];
    failed: { invoice_id: string; reason: string }[];
    skipped_already_done: string[];
    summary: string;
  };
}

export async function getCorrectionCatalog(
  client: ApiClient = api,
): Promise<CorrectionCatalog> {
  return requireData(await client.get<CorrectionCatalog>("/corrections/reasons"));
}

export async function getCorrectionCases(
  client: ApiClient = api,
): Promise<{ results: CorrectionCaseRow[]; unavailable: Unavailable[] }> {
  return requireData(
    await client.get<{ results: CorrectionCaseRow[]; unavailable: Unavailable[] }>("/corrections"),
  );
}

export async function getCorrectionCase(
  caseId: string,
  client: ApiClient = api,
): Promise<CorrectionCaseDetail> {
  return requireData(
    await client.get<CorrectionCaseDetail>(`/corrections/${encodeURIComponent(caseId)}`),
  );
}

/**
 * Open a case — **a PREVIEW, and it writes no money** (BR-BIL-014). The 201
 * means *"here is what it would cost"*, never *"it is done"*.
 *
 * There is deliberately no `mechanism` field: BR-BIL-041 derives it from the
 * reason's class and the server refuses a supplied one, because answering
 * "wrong rate" with a reprint is a silent underbilling.
 */
export interface OpenCorrectionBody {
  scope_kind: string;
  invoice_id?: string;
  invoice_ids?: string[];
  reason_codes: string[];
  as_of: string;
  posting_period?: string | null;
  /** DECIMAL STRING. A JSON number is a float by the time it lands and the
   *  server refuses one (rule 2). */
  goodwill_amount?: string;
  balance_before?: string;
  bill_run_id?: string;
  cycle_id?: string;
  /** The `plan` scope, or the plan NARROWING another kind — `corrections_api.py`
   *  has read `payload.get("plan_id")` since the bulk scope shipped; the field
   *  was simply missing from this type until `CR-101-BRC03` lane A (2026-09-15). */
  plan_id?: string;
  service_code?: string;
  period_start?: string;
  period_end?: string;
  corrected_payload?: Record<string, string>;
}

export async function openCorrectionCase(
  body: OpenCorrectionBody,
  client: ApiClient = api,
): Promise<CorrectionCaseDetail> {
  return requireData(await client.post<CorrectionCaseDetail>("/corrections", body));
}

// ── CR-101-BRC03 §06 · step 1 — the bills a scope resolves to ────────────
// p133 of the Billing blueprint: `BILL · PERIOD · AMOUNT · PAID · STATE`, a
// totals row over the WHOLE scope, and *"Only an issued or paid bill can be
// corrected."* Served by `GET /corrections/resolve` (`bulk_corrections.
// scope_table`), paged by the standard envelope — a run at T5 is 40,000 bills.

/** p133's STATE column. `null` when payments could not be asked — the seam
 *  never answers zero, so a bill is never drawn `unpaid` on a guess. */
export type CorrectionScopeBillState = "paid" | "part_paid" | "unpaid";

export interface CorrectionScopeBill {
  invoice_id: string;
  invoice_no: string | null;
  account_id: string;
  period_start: string;
  period_end: string;
  /** What the bill ASKED for (BR-BIL-072) — the LEVEL on a budget bill. DECIMAL STRING. */
  amount: string;
  /** What the bill totals — the same figure except on a budget bill. DECIMAL STRING. */
  total: string;
  /** Payments' net allocation against this bill; `null` when unreachable. */
  paid: string | null;
  state: CorrectionScopeBillState | null;
  /** The lifecycle column (`issued` / `paid`) — a different fact from `state`. */
  bill_status: string;
  currency: string;
}

export interface CorrectionScopeTotals {
  /** Every bill in the scope, not the page. */
  bills: number;
  amount: string;
  paid: string | null;
  /** `null` when the scope spans more than one currency (a problem names it). */
  currency: string | null;
}

/** The selector vocabulary is the POST's (`OpenCorrectionBody`), minus the reason. */
export interface ResolveCorrectionScopeQuery {
  scope_kind: string;
  invoice_id?: string;
  invoice_ids?: string[];
  bill_run_id?: string;
  cycle_id?: string;
  plan_id?: string;
  service_code?: string;
  period_start?: string;
  period_end?: string;
  page?: number;
  per?: number;
}

export interface CorrectionScopeResolution {
  count: number;
  next: string | null;
  previous: string | null;
  results: CorrectionScopeBill[];
  totals: CorrectionScopeTotals;
  /** p133's closing sentence as a FACT: `["issued", "paid"]`. */
  correctable_statuses: string[];
  problems: Unavailable[];
  scope_kind: string;
}

export async function resolveCorrectionScope(
  query: ResolveCorrectionScopeQuery,
  client: ApiClient = api,
): Promise<CorrectionScopeResolution> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const one of value) params.append(key, String(one));
    } else {
      params.set(key, String(value));
    }
  }
  return requireData(
    await client.get<CorrectionScopeResolution>(`/corrections/resolve?${params.toString()}`),
  );
}

export async function approveCorrectionCase(
  caseId: string,
  body: { preview_hash: string; approved_on: string },
  client: ApiClient = api,
): Promise<CorrectionCaseDetail> {
  return requireData(
    await client.post<CorrectionCaseDetail>(
      `/corrections/${encodeURIComponent(caseId)}/approve`,
      body,
    ),
  );
}

export async function executeCorrectionCase(
  caseId: string,
  body: { issued_at: string; on_date: string },
  client: ApiClient = api,
): Promise<CorrectionCaseDetail> {
  return requireData(
    await client.post<CorrectionCaseDetail>(
      `/corrections/${encodeURIComponent(caseId)}/execute`,
      body,
    ),
  );
}

export async function abandonCorrectionCase(
  caseId: string,
  body: { reason: string; on_date: string },
  client: ApiClient = api,
): Promise<CorrectionCaseDetail> {
  return requireData(
    await client.post<CorrectionCaseDetail>(
      `/corrections/${encodeURIComponent(caseId)}/abandon`,
      body,
    ),
  );
}

// ── CR-180-BRC10 · Fix a bill, revamped (Bills · Fix · Check · Send) ──────
// The contract is `12-governance/change-requests/CR-180-BRC10-fix-a-bill-revamp.md`
// §"The contract between server and screen" and its additions A1–A6. Every
// money figure is a DECIMAL STRING (hard rule 2); the screen formats, never
// computes.

/** The two options' four sub-options, as the server names the scope. */
export type CorrectionScopeKindV2 = "account" | "run" | "price_mistake";

export interface CorrectionScope {
  scope_kind: CorrectionScopeKindV2;
  account_id?: string;
  /** One or many of that account's bills; absent on `resolve` = all of them. */
  invoice_ids?: string[];
  bill_run_id?: string;
  service_code?: string;
  plan_id?: string;
  period_start?: string;
  period_end?: string;
  wrong_kind?: "rate" | "tax" | "charge";
  wrong_id?: string;
}

/** One row of the *What was wrong* table. `bill_ids: null` = every bill. */
export interface CorrectionItem {
  reason: string;
  item: string;
  act?: "add" | "remove";
  value?: string;
  value2?: string;
  bill_ids: string[] | null;
}

/** A1 — a bill left out of a scope, and why (`draft` · `open_case`). */
export interface CorrectionScopeExcluded {
  invoice_id: string;
  invoice_no: string | null;
  period_start: string;
  period_end: string;
  code: string;
}

/** A1 — the account-scoped and bulk resolve rows carry who, beside what. */
export interface CorrectionScopeBillV2 extends CorrectionScopeBill {
  account_no?: string | null;
  customer_name?: string | null;
}

export interface CorrectionScopeResolutionV2 {
  count: number;
  results: CorrectionScopeBillV2[];
  totals: CorrectionScopeTotals & { accounts?: number };
  excluded?: CorrectionScopeExcluded[];
  problems?: Unavailable[];
}

function scopeParams(scope: CorrectionScope, extra: Record<string, string | number> = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...scope, ...extra })) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const one of value) params.append(key, String(one));
    } else {
      params.set(key, String(value));
    }
  }
  return params.toString();
}

/** `GET /corrections/resolve` with the CR-180 scope kinds (A1). */
export async function resolveCorrectionScopeV2(
  scope: CorrectionScope,
  paging: { page: number; per: number },
  client: ApiClient = api,
): Promise<CorrectionScopeResolutionV2> {
  return requireData(
    await client.get<CorrectionScopeResolutionV2>(
      `/corrections/resolve?${scopeParams(scope, paging)}`,
    ),
  );
}

export interface CorrectionVersionOption {
  id: string;
  label: string;
  effective_from: string | null;
}

/** A2 — what the *What was wrong* row selects offer. */
export interface CorrectionFixOptions {
  plans: { id: string; name: string; versions: CorrectionVersionOption[] }[];
  rate_schedules: {
    id: string;
    name: string;
    service_code: string | null;
    versions: CorrectionVersionOption[];
  }[];
  /** `rate` is a PERCENT string — "2.000000" is 2%. */
  taxes: { code: string; name: string; rate: string | null }[];
  charge_codes: { code: string; name: string; amount: string | null }[];
  discounts: { id: string; name: string; version_label: string | null }[];
  price_targets: { kind: "rate" | "tax" | "charge"; id: string; label: string }[];
  meters?: {
    asset_id: string;
    label: string;
    service_code: string | null;
    unit: string | null;
    billed_reading: string | null;
  }[];
  bill_lines?: { key: string; label: string }[];
  billed?: {
    plan_id: string | null;
    plan_version_id: string | null;
    tax_rates: Record<string, string>;
    deposit: string | null;
    fields: Record<string, string | null>;
  } | null;
}

/** `GET /corrections/options` (A2) — writes nothing. */
export async function getCorrectionOptions(
  scope: CorrectionScope | null,
  client: ApiClient = api,
): Promise<CorrectionFixOptions> {
  const query = scope === null ? "" : `?${scopeParams(scope)}`;
  return requireData(await client.get<CorrectionFixOptions>(`/corrections/options${query}`));
}

/** One line of a bill as the old/new comparison draws it (A3). */
export interface CorrectionDocLine {
  /** Stable across `was` and `becomes` — the rows line up by it. */
  key: string;
  label: string;
  qty: string | null;
  unit: string | null;
  unit_price: string | null;
  base: string | null;
  percent: string | null;
  amount: string;
}

export interface CorrectionDocSection {
  key: string;
  kind: "service" | "charges" | "discounts" | "deposits";
  service_code: string | null;
  /** `flat` · `tiered` · `seasonal` · `tou` · `tou_demand` · `demand` ·
   *  `percent_of` · `flat_per_unit` — a code, worded by the catalogue. */
  rate_type: string | null;
  total: string;
  lines: CorrectionDocLine[];
}

export interface CorrectionDocTax {
  key: string;
  label: string;
  /** A percent string — "1.000000" is 1%. */
  rate: string;
  base: string;
  amount: string;
}

export interface CorrectionDocument {
  invoice_no: string | null;
  plan_name: string | null;
  plan_version: string | null;
  currency: string;
  sections: CorrectionDocSection[];
  subtotal: string;
  taxes: CorrectionDocTax[];
  tax_total: string;
  total: string;
}

export interface CorrectionPreviewBill {
  invoice_id: string;
  invoice_no: string | null;
  account_id: string;
  account_no: string | null;
  customer_name: string | null;
  period_start: string;
  period_end: string;
  was: CorrectionDocument | null;
  becomes: CorrectionDocument | null;
  credit_note: { lines: { key: string; label: string; amount: string }[]; total: string } | null;
  was_total: string;
  becomes_total: string;
  delta: string;
  paid: string | null;
  moves_to_new_bill: string | null;
  still_owed: string | null;
  /** `YYYY-MM`. */
  posting_period: string | null;
  new_due_date: string | null;
  /**
   * PO 2026-10-13 — the services whose usage was SHARED BY DAYS (a shortened
   * period with no reading on its new end). Optional: older servers omit it.
   */
  usage_shared_by_days?: string[];
}

export interface CorrectionPreview {
  correction_class: CorrectionClass | null;
  scope_kind: CorrectionScopeKindV2;
  currency: string;
  count: number;
  accounts: number;
  bills: CorrectionPreviewBill[];
  totals: {
    was: string;
    becomes: string;
    net: string;
    up: { count: number; amount: string };
    down: { count: number; amount: string };
    unchanged: number;
  };
  customer: {
    name: string | null;
    account_no: string | null;
    owes_before: string;
    owes_after: string;
    refund: string | null;
    credit_notes: number;
    new_bills: number;
    reprints: number;
    channels: string[];
    new_due_date: string | null;
  } | null;
  bulk: {
    credit_notes: number;
    new_bills: number;
    reprints: number;
    refunds: string | null;
    payments_moved: string;
    channels: string[];
  } | null;
  finance: {
    entries: { entry: "credit_notes" | "new_bills" | "goodwill"; amount: string }[];
    net: string;
    accounts: { code: string; name: string; change: string }[];
    closed_through: string | null;
    earliest_open: string | null;
  };
  page_changes: { field: string; was: string | null; becomes: string }[];
  approver: { role_name: string; user_name: string | null };
  preview_hash: string;
  problems: Unavailable[];
  /**
   * Q3 (decision log 2026-10-13) — a Wrong plan row whose plan bills one of
   * the account's services at $0.00: ONE entry per row and service. A
   * WARNING beside that row's choice, never a refusal. Optional: a server
   * before 2.574 omits it.
   */
  plan_warnings?: { position: number; service_code: string; amount: string; bills: number }[];
}

export interface CorrectionPreviewBody {
  scope: CorrectionScope;
  items: CorrectionItem[];
  as_of: string;
  page?: number;
  per?: number;
}

/** `POST /corrections/preview` — **writes nothing** (BR-BIL-014, CR-180 B7). */
export async function previewCorrection(
  body: CorrectionPreviewBody,
  client: ApiClient = api,
): Promise<CorrectionPreview> {
  return requireData(await client.post<CorrectionPreview>("/corrections/preview", body));
}

/** A4/A5 — the case, as the revamped screen reads it. */
export interface CorrectionCaseV2 extends CorrectionCaseDetail {
  items?: CorrectionItem[];
  preview?: CorrectionPreview | null;
  approval?: {
    role_name: string;
    approver_name: string | null;
    initiated_by_name: string | null;
    sent_on: string | null;
    approved_by_name: string | null;
  };
  viewer_can_approve?: boolean;
  /** DEF-BIL-10535 — the approval step's *Email · Paper · Both* (one customer
   *  only; null on a bulk case or one past approval). */
  delivery?: CorrectionDeliveryOffer | null;
  bills_detail: (CorrectionBillRow & {
    invoice_no?: string | null;
    credit_note_no?: string | null;
    rebill_invoice_no?: string | null;
  })[];
}

/** `POST /corrections` AT SEND — the case is opened here and nowhere earlier. */
export async function sendCorrectionForApproval(
  body: CorrectionPreviewBody & { preview_hash: string },
  client: ApiClient = api,
): Promise<CorrectionCaseV2> {
  return requireData(await client.post<CorrectionCaseV2>("/corrections", body));
}

/** DEF-BIL-10535 (PO 2026-10-22, Q1) — what the clerk sends a corrected bill
 *  on. Paper is always the floor, so `email` queues print as well. */
export const CORRECTION_DELIVERIES = ["email", "paper", "email_and_paper"] as const;
export type CorrectionDelivery = (typeof CORRECTION_DELIVERIES)[number];

export interface CorrectionDeliveryOffer {
  choices: CorrectionDelivery[];
  /** The ORIGINAL bill's channels — what the step starts on. */
  preselected: CorrectionDelivery | null;
  /** False greys Email and Both; the server refuses them by name too. */
  email_on_file: boolean;
}

/** `POST /corrections/{id}/approve-and-issue` — approve and execute as one act. */
export async function approveAndIssueCorrection(
  caseId: string,
  body: {
    preview_hash: string;
    on_date: string;
    issued_at: string;
    delivery?: CorrectionDelivery;
  },
  client: ApiClient = api,
): Promise<CorrectionCaseV2> {
  return requireData(
    await client.post<CorrectionCaseV2>(
      `/corrections/${encodeURIComponent(caseId)}/approve-and-issue`,
      body,
    ),
  );
}

// ── DEF-BIL-10091 · BULK RUNS AS A BACKGROUND JOB ──────────────────────────
// A bulk preview, Send and Approve-and-issue answer 202 + a job id. The screen
// polls `/jobs/{id}` (the client's ONE poller) for "Working out 38 bills · 12
// done", then reads the act's answer from `GET /corrections/jobs/{id}` — a
// preview a page at a time (NFR-3), a case, or a refusal by `message_key`.

/** A 2xx that is either the answer itself or a job to follow. */
export type CorrectionAnswer<T> = { kind: "done"; data: T } | { kind: "job"; jobId: string };

function answerOrJob<T>(response: ApiResponse<T>): CorrectionAnswer<T> {
  const jobId = acceptedJobId(response);
  return jobId === null ? { kind: "done", data: requireData(response) } : { kind: "job", jobId };
}

export type CorrectionJobStage = "pricing" | "checking" | "sending" | "issuing";

export interface CorrectionJobProgress {
  done: number;
  total: number | null;
  stage?: CorrectionJobStage;
}

export interface CorrectionJobResult {
  case_id: string;
  status: string;
  succeeded: string[];
  failed: { invoice_id: string; reason: string }[];
  skipped_already_done: string[];
  summary: string;
}

export interface CorrectionJobState {
  job_id: string;
  act: "preview" | "send" | "approve_issue";
  status: JobStatus;
  progress: CorrectionJobProgress | null;
  error: string | null;
  /** The act's refusal, by catalogue key — *"Figures changed. Check again."* */
  refusal: { message_key: string; params?: Record<string, unknown>; detail?: string } | null;
  preview: (CorrectionPreview & { page: number; per: number }) | null;
  case: (CorrectionCaseV2 & { result?: CorrectionJobResult }) | null;
}

/** `POST /corrections/preview`, answered either way: one customer in the
 *  request, bulk as a job. */
export async function startCorrectionPreview(
  body: CorrectionPreviewBody,
  client: ApiClient = api,
): Promise<CorrectionAnswer<CorrectionPreview>> {
  return answerOrJob(await client.post<CorrectionPreview>("/corrections/preview", body));
}

/** `POST /corrections` at Send — bulk names the preview job it opens from. */
export async function startCorrectionSend(
  body: CorrectionPreviewBody & { preview_hash: string; preview_job_id?: string },
  client: ApiClient = api,
): Promise<CorrectionAnswer<CorrectionCaseV2>> {
  return answerOrJob(await client.post<CorrectionCaseV2>("/corrections", body));
}

/** `POST /corrections/{id}/approve-and-issue` — bulk answers with a job. */
export async function startApproveAndIssue(
  caseId: string,
  body: {
    preview_hash: string;
    on_date: string;
    issued_at: string;
    delivery?: CorrectionDelivery;
  },
  client: ApiClient = api,
): Promise<CorrectionAnswer<CorrectionCaseV2>> {
  return answerOrJob(
    await client.post<CorrectionCaseV2>(
      `/corrections/${encodeURIComponent(caseId)}/approve-and-issue`,
      body,
    ),
  );
}

/** `POST /corrections/{id}/execute` (Try again) — bulk answers with a job. */
export async function startCorrectionResume(
  caseId: string,
  body: { issued_at: string; on_date: string },
  client: ApiClient = api,
): Promise<CorrectionAnswer<CorrectionCaseDetail>> {
  return answerOrJob(
    await client.post<CorrectionCaseDetail>(
      `/corrections/${encodeURIComponent(caseId)}/execute`,
      body,
    ),
  );
}

/** `GET /corrections/jobs/{id}` — the act's state and answer, a page at a time. */
export async function getCorrectionJob(
  jobId: string,
  paging: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<CorrectionJobState> {
  return requireData(
    await client.get<CorrectionJobState>(`/corrections/jobs/${encodeURIComponent(jobId)}`, {
      query: paging,
    }),
  );
}

/** How long a bulk act is followed: a T5 run is thousands of bills, so the
 *  poller's five-minute default would give up on work that is still going. */
export const CORRECTION_JOB_MAX_POLLS = 6 * 60 * 60;

/** Follow a job to its end, reporting progress, then read its answer. */
export async function followCorrectionJob(
  jobId: string,
  onProgress: (progress: CorrectionJobProgress | null) => void,
  client: ApiClient = api,
  paging: { page?: number; per?: number } = {},
): Promise<CorrectionJobState> {
  await pollJob(client, jobId, {
    maxPolls: CORRECTION_JOB_MAX_POLLS,
    onProgress: (job: JobRecord) => onProgress(job.progress as CorrectionJobProgress | null),
  });
  return getCorrectionJob(jobId, paging, client);
}

/** `GET /corrections/{id}` typed with the A4 additions. */
export async function getCorrectionCaseV2(
  caseId: string,
  client: ApiClient = api,
): Promise<CorrectionCaseV2> {
  return requireData(
    await client.get<CorrectionCaseV2>(`/corrections/${encodeURIComponent(caseId)}`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S30 BUDGET BILLS — /budget-billing (US-BIL-018 · 019 · 020)
// ══════════════════════════════════════════════════════════════════════════

export interface BudgetStatusRow {
  account_id: string;
  /**
   * The account's HUMAN-FACING number — served since 2026-09-02 (DEF-3158).
   *
   * ⚠ **The tab's first column used to print `account_id.slice(0, 8)` with no
   * fallback**, so a truncated database id was the visible value on every row.
   * B14 rule 31 requires the human-facing number where one exists; nothing was
   * serving it. Nullable because the column is (an import path that cannot
   * reach the series must fail loudly rather than collide), and the screen
   * states that absence in words rather than falling back to the id again.
   */
  account_no: string | null;
  status: string;
  /** The COMPUTED level and the OVERRIDE travel separately and `effective_level`
   *  is a third member, not a replacement: BR-BIL-017 measures the ±30% bound
   *  against the computed one, so collapsing them would leave the screen unable
   *  to say what the next override is validated against. */
  level: string | null;
  level_override: string | null;
  level_override_reason: string | null;
  effective_level: string | null;
  /** SIGNED. Negative is money the customer has under-paid against actuals. */
  variance_balance: string | null;
  currency: string;
  settle_up_month: number | null;
  enrolled_on: string | null;
  last_leveled_at: string | null;
  /** The customer's own name, under the account number — blueprint §05 screen
   *  25 draws both in one cell. Served through customers' published read,
   *  which REFUSES rather than answering null when it is unpublished. */
  customer_name: string | null;
  /** What the meter has actually said since enrolment — the sum of the
   *  account's budget events. **NULL is ABSENT, never `0.00`:** an account
   *  enrolled this week has had no bill, which is not the same statement as a
   *  meter reading zero. */
  actual_to_date?: string | null;
  actual_months?: number;
  /** The month a re-level is next due, from `last_leveled_at` + the tenant's
   *  own cadence. Null when either is unreadable. */
  relevel_due_on?: string | null;
  relevel_is_due?: boolean | null;
  /** ⚠ WHY THIS COLUMN CARRIES NO DRIFT PERCENTAGE. The drawing puts
   *  *"Drifted 14%"* here; drift is `|recomputed − current| ÷ current` and
   *  every figure of it costs a fresh twelve-month invoice read per account.
   *  Nothing stores a recomputed level, so it is a NEW READ rather than a
   *  rendering, and the server says so on every row instead of leaving the
   *  cell blank. */
  relevel_drift_unavailable?: string;
}

/** §05 screen 25's four KPI tiles. Every member is null-with-a-reason rather
 *  than a substituted 0 — a tile reading `0` says *nobody*, and one reading a
 *  dash says *nobody could ask*. */
export interface BudgetSummary {
  enrolled: number;
  accounts_total: number | null;
  accounts_total_unavailable: string | null;
  shortfall_accounts: number;
  /** One currency or none: a tenant whose enrolled accounts carry two gets the
   *  COUNT and no total, because adding 100 USD to 100 CAD is not 200. */
  shortfall_amount: string | null;
  shortfall_currency: string | null;
  shortfall_currencies: string[];
  relevel_due: number | null;
  relevel_cadence_months: number | null;
  /** ⚠ ALWAYS NULL TODAY, WITH ITS REASON. A level-pay ask is raised as an
   *  ORDINARY service request (BR-CWP-066) carrying no route, no kind and no
   *  account, so the queue cannot be counted without matching English prose. */
  asks_waiting: number | null;
  asks_waiting_unavailable: string | null;
}

export interface BudgetEventRow {
  id: string;
  event: string;
  occurred_on: string;
  level: string | null;
  actual: string | null;
  movement: string | null;
  balance_after: string | null;
  currency: string;
  reason: string | null;
  invoice_id: string | null;
}

export interface BudgetListResponse {
  results: BudgetStatusRow[];
  count?: number;
  /** The tenant's own S69 figures, or NULL with the reason — never the
   *  ratified defaults (BR-BIL-021). */
  parameters: Record<string, unknown> | null;
  /** WHY `parameters` is null, in the same shape as an `unavailable[]` gap —
   *  a `message_key` for the clerk and the rule on `br_ref` for support. It
   *  was the settings seam's own sentence (a dotted module path and a rule id)
   *  until `DEF-BIL-5339`, 2026-09-15. */
  parameters_unavailable: Unavailable | null;
  statuses: string[];
  summary?: BudgetSummary;
  unavailable: Unavailable[];
}

export interface BudgetEligibility {
  account_id: string;
  months_of_history: number;
  bills_read: number;
  trailing_actuals: string[];
  currency: string | null;
  required_months: number | null;
  required_months_unavailable: string | null;
  /** NULL, never "0.00" — see this file's header. */
  computed_level: string | null;
  computed_level_unavailable: string | null;
  /** OQ-237 — always null today, WITH the reason. */
  eligible: boolean | null;
  eligible_unavailable: string;
  already_enrolled: boolean;
  /**
   * CR-044 §2.5 — what this customer ALREADY owes, beside the level.
   *
   * ⚠ `null` IS NOT `"0.00"`. Zero means the customer owes nothing from
   * before; null means nobody could ask, and the screen renders a dash with
   * `open_balance_problems` as the reason. A `0.00` on an unreachable seam
   * would tell a clerk that a customer in arrears is square.
   *
   * A decimal STRING at the column's own scale — never a number. A Decimal
   * through JSON comes back a float and CLAUDE.md rule 2 forbids it.
   */
  open_balance: string | null;
  /**
   * CLAUDE.md rule 2 — the amount's OWN CHAR(3), not `currency` above. They
   * differ on exactly the account this figure exists for: one migrated in
   * owing money has never been billed, so the billed `currency` is null while
   * the arrears figure is real and carries its opening bucket's currency.
   */
  open_balance_currency: string | null;
  /** How many still-open earlier BILLS stand behind it. 0 with a non-zero
   *  balance is real and readable: an account MIGRATED in owing money. */
  open_balance_bills: number;
  /** Which window the figure was read over — OQ-217, ruled 2026-10-01: the whole account since the last bill. */
  open_balance_basis: string;
  open_balance_basis_oq: string;
  open_balance_problems: Unavailable[];
  unavailable: Unavailable[];
}

export interface BudgetAccountDetail extends BudgetStatusRow {
  variance_balance_recomputed: string;
  events: BudgetEventRow[];
  unavailable: Unavailable[];
}

/**
 * One row of §05 entry 25.2 — the settle-up forecast.
 *
 * ⚠ **`balance_signed` IS THE DRAWN COLUMN AND `variance_balance` IS NOT.** They
 * are the same fact with opposite signs, and both are the engine's: screen 25
 * shows the POSITION a budget account is in (`variance_balance`, negative when
 * the customer has under-paid), and this screen shows the TRANSACTION that is
 * coming (`budget.SettleUp.signed` — *"+ collects, − credits"*). The server
 * serves both halves so the browser never negates anything.
 *
 * Every money member is a DECIMAL STRING. Storage is 4dp and display is 2
 * (CLAUDE.md rule 2), and `Number(...)` on any of them is the defect that rule
 * exists to prevent — so nothing here is typed `number`.
 */
export interface SettleUpForecastRow {
  /** For the LINK only. B14 rule 31 — never a visible value. */
  account_id: string;
  account_no: string | null;
  customer_name: string | null;
  /** 1–12, and the YEAR it next falls in — the drawn `Nov 2026`. */
  settles_in_month: number;
  settles_in_year: number;
  months_away: number;
  settles_this_month: boolean;
  /** Σ of the levels billed inside the CURRENT settle-up period. **NULL is
   *  ABSENT, never `0.00`** — an account with no bill since its last true-up
   *  has had nothing asked of it, which is not the same as being asked zero. */
  paid_on_level: string | null;
  /** Σ of the actuals over the same period. Absent on the same terms. */
  actual_so_far: string | null;
  months_billed: number;
  /** `actual_so_far − paid_on_level`, signed: **+ collects, − credits**. */
  balance_signed: string | null;
  /** Always POSITIVE; `settle_up_direction` carries the sign. Null when there
   *  is nothing to true up at all. */
  settle_up_amount: string | null;
  /** `collect` | `credit` | null. */
  settle_up_direction: string | null;
  /** ❄️ B4.2 — AR-timing, never revenue, so never taxed. Always false. */
  settle_up_taxable: boolean;
  currency: string;
}

export interface SettleUpForecastSummary {
  settling_this_month: number;
  settling_month: number;
  settling_year: number;
  /** POSITIVE magnitudes. **One currency or none** (CLAUDE.md rule 2): a tenant
   *  whose settling accounts carry two gets the COUNTS and no totals. */
  to_collect_amount: string | null;
  to_collect_accounts: number;
  to_credit_amount: string | null;
  to_credit_accounts: number;
  currency: string | null;
  currencies: string[];
  later_accounts: number;
  later_months: number;
  /** Enrolled, but the tenant published no settle-up month, so they never true
   *  up. Counted so the screen can STATE it rather than quietly omitting them. */
  no_settle_month: number;
}

export interface SettleUpForecastResponse {
  results: SettleUpForecastRow[];
  count?: number;
  as_of: string;
  directions: string[];
  summary: SettleUpForecastSummary;
  unavailable: Unavailable[];
}

/**
 * `GET /budget-billing/settle-up-forecast` — READ ONLY, and there is no sibling
 * write. The cycle run posts every settle-up on the account's own bill,
 * idempotently per invoice; a second caller would be a second writer for the
 * same money, which is why the blueprint withdrew the bulk button it first drew.
 */
export async function getSettleUpForecast(
  params: {
    q?: string;
    month?: string;
    direction?: string;
    asOf?: string;
    page?: number;
    per?: number;
  } = {},
  client: ApiClient = api,
): Promise<SettleUpForecastResponse> {
  const query: Record<string, string> = {};
  if (params.month !== undefined && params.month !== "") {
    query["f.month"] = params.month;
  }
  if (params.direction !== undefined && params.direction !== "") {
    query["f.direction"] = params.direction;
  }
  if (params.q !== undefined && params.q !== "") {
    query.q = params.q;
  }
  // The horizon is the SERVER's today unless a caller names one. The screen
  // does not send it: a browser clock and a server clock disagree across a
  // timezone, and which month is "this month" decides a whole tile.
  if (params.asOf !== undefined && params.asOf !== "") {
    query.as_of = params.asOf;
  }
  // Cut in SQL (`NFR-3`) — 37 rows today and one per enrolled account at the
  // top of the ICP.
  if (params.page !== undefined) {
    query.page = String(params.page);
  }
  if (params.per !== undefined) {
    query.per = String(params.per);
  }
  return requireData(
    await client.get<SettleUpForecastResponse>("/budget-billing/settle-up-forecast", { query }),
  );
}

export async function getBudgetEnrollments(
  params: {
    status?: string;
    q?: string;
    relevel?: string;
    page?: number;
    per?: number;
  } = {},
  client: ApiClient = api,
): Promise<BudgetListResponse> {
  const query: Record<string, string> = {};
  if (params.status !== undefined && params.status !== "") {
    query["f.status"] = params.status;
  }
  // §05 screen 25's toolbar. The page and size travel because the list is cut
  // in SQL (`NFR-3`) — a screen that asked for every row would be correct at
  // 218 accounts and 13x short of the top of the ICP.
  if (params.relevel !== undefined && params.relevel !== "") {
    query["f.relevel"] = params.relevel;
  }
  if (params.q !== undefined && params.q !== "") {
    query.q = params.q;
  }
  if (params.page !== undefined) {
    query.page = String(params.page);
  }
  if (params.per !== undefined) {
    query.per = String(params.per);
  }
  return requireData(await client.get<BudgetListResponse>("/budget-billing", { query }));
}

/**
 * §05 entry 25.3's row — a customer's ask, as staff read it.
 *
 * ⚠ **`account_id` IS ON THE ROW AND IS RENDERED BY NOTHING** (B14 rule 31).
 * It is what the `Enrol →` door puts in its address; what a clerk SEES is
 * `account_no`, the number printed on the paper bill, and `reference`, the
 * number they quote down the telephone.
 *
 * ⚠ **`level_shown` AND `level_now` ARE TWO FIELDS ON PURPOSE.** p127, in
 * capitals: *"THE TWO LEVEL COLUMNS ARE NOT A DUPLICATE"* — a month passes, a
 * bill lands, and the figure the customer was quoted stops being correct.
 * Collapsing them either breaks a promise silently or enrols at a stale figure.
 * Both are 4-decimal STRINGS (CLAUDE.md rule 2; never a JS number).
 */
export interface BudgetAskRow {
  reference: string;
  asked_on: string;
  account_id: string;
  account_no: string;
  customer_name: string | null;
  level_shown: string | null;
  level_now: string | null;
  currency: string | null;
  /** `null` is the THIRD state — nothing could read the plan's flag (OQ-237). */
  eligible: boolean | null;
  not_eligible_because: string | null;
}

/** The four tiles above the queue. Three are absences today; one is real. */
export interface BudgetAsksSummary {
  waiting: number | null;
  waiting_unavailable: string | null;
  eligible_now: number | null;
  eligible_now_unavailable: string | null;
  not_eligible: number | null;
  not_eligible_unavailable: string | null;
  enrolled_this_month: number | null;
  enrolled_from_portal: number | null;
  enrolled_from_portal_unavailable: string | null;
}

/**
 * ⚠ **`count` IS `number | null` AND THE NULL IS LOAD-BEARING.** `0` says *six
 * people asked and none of them qualifies*; `null` says *nobody could ask*. A
 * clerk who reads the first closes the tab while the customers wait.
 */
export interface BudgetAsksResponse {
  count: number | null;
  results: BudgetAskRow[];
  page: number;
  per: number;
  /** A sentence while the rows cannot be read; `null` once they can. */
  rows_unavailable: string | null;
  summary: BudgetAsksSummary;
  unavailable: { code: string; br_ref: string; detail: string }[];
}

/** `GET /budget-billing/asks` — §05 entry 25.3. Paged at the SERVER (NFR-3). */
export async function getBudgetAsks(
  params: { page?: number; per?: number },
  client: ApiClient = api,
): Promise<BudgetAsksResponse> {
  const query: Record<string, string> = {};
  if (params.page !== undefined) {
    query["page"] = String(params.page);
  }
  if (params.per !== undefined) {
    query["per"] = String(params.per);
  }
  return requireData(await client.get<BudgetAsksResponse>("/budget-billing/asks", { query }));
}

export async function getBudgetEligibility(
  accountId: string,
  client: ApiClient = api,
): Promise<BudgetEligibility> {
  return requireData(
    await client.get<BudgetEligibility>(
      `/budget-billing/${encodeURIComponent(accountId)}/eligibility`,
    ),
  );
}

export async function getBudgetAccount(
  accountId: string,
  client: ApiClient = api,
): Promise<BudgetAccountDetail> {
  return requireData(
    await client.get<BudgetAccountDetail>(`/budget-billing/${encodeURIComponent(accountId)}`),
  );
}

/** `plan_offers_budget` is REQUIRED and has no default here for the same reason
 *  it has none server-side (OQ-237): BR-RAT-043 puts it on the rate plan, no
 *  endpoint publishes it, and enrolling on an assumed `true` puts a customer on
 *  a flat amount their tariff never promised. */
export async function enrollInBudgetBilling(
  body: { account_id: string; plan_offers_budget: boolean; on_date: string },
  client: ApiClient = api,
): Promise<BudgetStatusRow & { trailing_actuals: string[] }> {
  return requireData(
    await client.post<BudgetStatusRow & { trailing_actuals: string[] }>(
      "/budget-billing/enrollments",
      body,
    ),
  );
}

export async function relevelBudgetAccount(
  accountId: string,
  body: { on_date: string },
  client: ApiClient = api,
): Promise<BudgetStatusRow & { changed: boolean }> {
  return requireData(
    await client.post<BudgetStatusRow & { changed: boolean }>(
      `/budget-billing/${encodeURIComponent(accountId)}/relevel`,
      body,
    ),
  );
}

export async function overrideBudgetLevel(
  accountId: string,
  /** `override` is a DECIMAL STRING (rule 2) — the server refuses a float. */
  body: { override: string; reason: string; on_date: string },
  client: ApiClient = api,
): Promise<BudgetStatusRow> {
  return requireData(
    await client.post<BudgetStatusRow>(
      `/budget-billing/${encodeURIComponent(accountId)}/override`,
      body,
    ),
  );
}

export async function removeFromBudgetBilling(
  accountId: string,
  body: { reason: string; on_date: string },
  client: ApiClient = api,
): Promise<BudgetStatusRow & { variance_balance_carried: string }> {
  return requireData(
    await client.post<BudgetStatusRow & { variance_balance_carried: string }>(
      `/budget-billing/${encodeURIComponent(accountId)}/remove`,
      body,
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S30 THE DOCUMENT — /invoices/{id}/document (US-BIL-022)
// ══════════════════════════════════════════════════════════════════════════

export interface DocumentAbsence {
  field: string;
  why: string;
  br_ref: string;
}

export interface DocumentField {
  label: string;
  value: string;
  /** The absence attached to THIS field, so the viewer can badge the exact
   *  line rather than printing an em-dash and leaving the clerk to guess. */
  absent: DocumentAbsence | null;
}

export interface DocumentGroup {
  heading: string;
  absent: DocumentAbsence | null;
  lines: { description: string; quantity: string; unit_price: string; amount: string }[];
}

/** One month on A19 §1.7's twelve-month axis, as the bill FROZE it.
 *
 *  ⚠ `absent` IS NOT `quantity === "0"`. `BR-MET-106` stores a month only when
 *  something was measured, so an absent month is one nobody read — drawing it
 *  as a zero bar would tell a customer their meter read zero, which is a claim
 *  this utility never made. Nothing here fills a gap with a default.
 *
 *  `quantity` is the exact stored decimal as a string and is what a bar's
 *  HEIGHT is computed from; `quantity_display` is the text to print. A
 *  quantity, never money — it carries its `unit` (CLAUDE.md rule 3). */
export interface DocumentUsageMonth {
  label: string;
  quantity: string;
  quantity_display: string;
  unit: string | null;
  absent: boolean;
  /** `BR-MET-106` — *"estimates count and are marked"*. */
  estimated: boolean;
}

/** One service's twelve frozen months (A19 §1.7, CR-052 task 9).
 *
 *  Served ONLY from `bill_payload.usage_history`, which `issue._stamp_usage_history`
 *  froze at issue with the axis ending at the BILL's own period end. There is no
 *  client-side alternative and there must not be one: reading the account's live
 *  usage instead is the join `BR-BIL-030` forbids, and a 2026 bill reprinted in
 *  2033 would then draw 2033's twelve months (`DEF-2714`). */
export interface DocumentUsageSeries {
  /** The service NAME. No identifier is served — B14 rule 31. */
  heading: string;
  unit: string | null;
  months_present: number;
  absent: DocumentAbsence | null;
  months: DocumentUsageMonth[];
}

/** A problem with a bill that ISSUED ANYWAY — addressed to whoever ran the run,
 *  not to whoever is holding the page (OQ-117 / OQ-150, both PO 2026-08-12). */
export interface DocumentProblem {
  code: string;
  invoice_id: string;
  invoice_no: string | null;
  br_ref: string;
  detail: string;
}

/** One artefact kept in the document store — **never a storage key.**
 *
 *  A key is how the server finds bytes; handing one to a browser would let a
 *  caller ask for a key it composed (`CR-049` step 5d(e) decision 4). What a
 *  screen gets is the record: what it is called, how big it is, when it was
 *  sealed, and the checksum that proves it is unchanged. */
export interface FrozenBillDocument {
  id: string;
  kind: string;
  display_name: string;
  content_type: string;
  /** Re-computed and matched on THIS read. A mismatch never reaches a screen as
   *  data — it is a refusal (`billing.document.hashMismatch`). */
  content_hash: string;
  byte_length: number;
  stored_at: string;
  storage_backend: string;
}

/** One platform layout's switches, as `documents.LayoutSpec` declares them.
 *
 *  Every member is *"draw this"*, never *"hide this"* — a negative switch read
 *  through an optional-chained `undefined` would silently mean *draw it*, and
 *  the failure this type exists to stop is a band drawn on a layout that
 *  suppresses it. `reserve_rows` is paper geometry and the screen ignores it;
 *  it is carried because the printed page uses it and a partial copy of a
 *  contract is how two readers start disagreeing. */
export interface BillDocumentLayout {
  key: string;
  masthead: boolean;
  services_band: boolean;
  detail_columns: boolean;
  summary_first: boolean;
  stub: boolean;
  reserve_rows: number;
}

export interface RenderedBillDocument {
  invoice_id: string;
  invoice_no: string | null;
  template_id: string | null;
  template_version: number;
  payload_version: number;
  /** `platform-layout-<key>` for a tenant's chosen layout, `registered-layout-v1`
   *  for a bill pinned before the library existed. On every document, so nobody
   *  has to take an assertion's word for which page they are looking at. */
  layout_source: string;
  /** WHAT the layout named above actually does — `DEF-2826`.
   *
   *  ⚠ **THE NAME WITHOUT THE SWITCHES IS A CLAIM, NOT A RENDERING.** The
   *  viewer carried `layout_source` from the day the library landed and drew
   *  every band regardless, so a utility on `compact-letter-v1` was shown a
   *  page announcing compact and looking standard, directly above a link to
   *  the real compact page. These are the layout's own declaration, served, so
   *  the screen branches on the same switches the printed page was built from
   *  rather than on a second copy of the rule. */
  layout: BillDocumentLayout;
  currency: string;
  content_type: string;
  body: string;
  pdf_content_type: string;
  pdf_page_count: number;
  pdf_url: string;
  masthead: DocumentField[];
  meta: DocumentField[];
  services: DocumentField[];
  groups: DocumentGroup[];
  summary: DocumentField[];
  /** US-BIL-028 — the tenant's OWN custom fields, as the one remark/note
   *  section the PO ruled on 2026-08-12 (*"in remark or note section on bill"*).
   *  `[]` when the tenant has defined none; the band is then omitted whole
   *  rather than drawn empty. Values are display strings frozen at stamp time —
   *  nothing on this side formats, parses or computes with one (BR-TEN-048). */
  remarks: DocumentField[];
  /** A19 §1.7 — the twelve months this bill FROZE (CR-052 task 9). `[]` on
   *  every bill issued before task 8 stamped one, and the panel is then omitted
   *  whole rather than drawn empty. */
  usage: DocumentUsageSeries[];
  footer: DocumentField[];
  stub: DocumentField[];
  absent: DocumentAbsence[];
  pdf_unrepresentable: DocumentAbsence[];
  problems: DocumentProblem[];
  unavailable: Unavailable[];

  // ── CR-049 task 4 · BR-NOT-027 — is this the bill, or a rebuild of it? ────
  /** `"original"` or `"re_rendered_from_data_not_the_original"`. **There is no
   *  third value and none that means "probably".** A screen that draws the
   *  rebuild without drawing `message_key`'s sentence has produced the defect
   *  the whole change request exists to remove (`DEF-2553`). */
  provenance: "original" | "re_rendered_from_data_not_the_original";
  /** The sentence for this state, chosen by the SERVER. The backend and this
   *  screen must not describe one state in two different ways. */
  message_key: string;
  provenance_detail: string;
  /** `document_not_stored` when no copy was kept; null when one was. */
  unavailable_reason: string | null;
  /** The kept HTML, byte for byte, hash-verified on this read — **null on any
   *  answer that is not the original**, so there is nothing to draw by mistake. */
  original_html: string | null;
  frozen_document: FrozenBillDocument | null;
  frozen_page: FrozenBillDocument | null;
}

export async function getBillDocument(
  invoiceId: string,
  client: ApiClient = api,
): Promise<RenderedBillDocument> {
  return requireData(
    await client.get<RenderedBillDocument>(
      `/invoices/${encodeURIComponent(invoiceId)}/document`,
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S8 BILL LAYOUT — /bill-templates (US-BIL-021, PO ruling 2026-08-16)
// ══════════════════════════════════════════════════════════════════════════

export interface PlatformLayoutRow {
  key: string;
  label: string;
  /** Written for the person CHOOSING, not for the schema. */
  summary: string;
  template_type: string;
  /** FALSE when the platform lists a layout it cannot render. Served rather
   *  than hidden, so the screen disables it WITH the reason. */
  renders: boolean;
  is_current: boolean;
  is_platform_default: boolean;
  /** WHERE TO SEE IT (`DEF-BIL-4458`) — the path that renders this layout on
   *  one of the tenant's own issued bills, as `application/pdf`.
   *
   *  ⚠ **NULL WHEN THE PLATFORM CANNOT RENDER THE LAYOUT** (`renders: false`),
   *  because a frame pointed at a route that will refuse is worse than a named
   *  absence — the card says why instead (BR-SHL-020). */
  preview_url: string | null;
  /** …and the one reason NONE of them can be drawn — this utility has never
   *  issued a bill, so there is no real document to borrow. Served on every
   *  layout so a caller reading one does not have to know the library holds it
   *  too; `null` when previews work. */
  preview_unavailable: string | null;
}

export interface BillTemplateVersionRow {
  id: string;
  version_no: number;
  status: string;
  layout_key: string;
  published_on: string | null;
  /** BR-BIL-027's audit-lock number: how many issued bills print on it. */
  pinned_bills: number;
  options: Record<string, unknown>;
}

export interface BillTemplateLibrary {
  /** NULL when provisioning's seeder has not run — a repairable state, and a
   *  different one from an empty library (which would be a build defect). */
  template: { id: string; name: string; template_type: string; is_fallback: boolean } | null;
  current: {
    version_no: number;
    layout_key: string;
    published_on: string | null;
    options: Record<string, unknown>;
  } | null;
  versions: BillTemplateVersionRow[];
  layouts: PlatformLayoutRow[];
  publish_role: string;
  published_status: string;
  unavailable: Unavailable[];
}

export interface ChooseLayoutOutcome extends BillTemplateLibrary {
  changed: boolean;
  version_no: number;
  layout_key: string;
  previous_version_no?: number | null;
  previous_layout_key?: string | null;
  reason: string;
}

export async function getBillTemplateLibrary(
  client: ApiClient = api,
): Promise<BillTemplateLibrary> {
  return requireData(await client.get<BillTemplateLibrary>("/bill-templates"));
}

export async function chooseBillLayout(
  body: { layout_key: string; on_date: string },
  client: ApiClient = api,
): Promise<ChooseLayoutOutcome> {
  return requireData(await client.post<ChooseLayoutOutcome>("/bill-templates/layout", body));
}

// ══════════════════════════════════════════════════════════════════════════
// S30 THE PENDING-BILLING QUEUE — /billing/pending (US-BIL-006)
// ══════════════════════════════════════════════════════════════════════════
// *"Hold ≠ forget."* This route has been SERVED since the queue landed and
// nothing called it, so an account a run did not bill was invisible: the door
// back existed and there was no handle on it.

export interface PendingQueueRow {
  id: string;
  account_id: string;
  account_no: string | null;
  bill_run_id: string | null;
  parent_run_id: string | null;
  period_start: string;
  period_end: string;
  reason_code: string;
  detail: string | null;
  /** WHICH DOOR it came through — a phase-1 hold (never calculated) reads
   *  differently from a phase-3 mark-for-later (calculated, broke at a stage).
   *  The first is fixed by entering a read; the second usually by fixing
   *  configuration. */
  origin: string;
  stage: string | null;
  held_on: string;
  /** Measured against the `as_of` on the envelope, NEVER a browser clock. */
  age_days: number;
  escalated: boolean;
  resolved_by_run_id: string | null;
  resolved_on: string | null;
}

export interface PendingQueueResponse {
  items: PendingQueueRow[];
  counts: Record<string, number>;
  /** The day the ages were computed AGAINST. It travels with them so a screen
   *  can never show an age without showing what it is an age at (BR-TEN-043). */
  as_of: string;
  escalation_days: number;
  unavailable: Unavailable[];
}

export async function getPendingQueue(
  params: { as_of: string; include_resolved?: boolean },
  client: ApiClient = api,
): Promise<PendingQueueResponse> {
  const query: Record<string, string> = { as_of: params.as_of };
  if (params.include_resolved === true) {
    query.include_resolved = "true";
  }
  return requireData(
    await client.get<PendingQueueResponse>("/billing/pending", { query }),
  );
}

export async function startCatchUpRun(
  runId: string,
  body: { account_ids: string[] },
  client: ApiClient = api,
): Promise<{ id: string; parent_run_id: string; status: string }> {
  return requireData(
    await client.post<{ id: string; parent_run_id: string; status: string }>(
      `/billing/runs/${encodeURIComponent(runId)}/catch-up`,
      body,
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE ONE-TIME BILL, REDRAWN — Account · Services · Review · Send (2026-09-30)
//
// Built to `04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md`
// field for field, while the backend builds to the same file in parallel. A
// field the contract does not name is not typed here.
//
// ⚠ **MONEY IS A 4-DECIMAL STRING BESIDE ITS `currency`, AND A QUANTITY ALWAYS
// CARRIES ITS UNIT** (CLAUDE.md rules 2 and 3). A clerk-facing sentence is a
// catalogue key plus params, never server prose.
// ══════════════════════════════════════════════════════════════════════════

/** The six kinds, as the server spells them. `backbill` is drawn *Catch-up*. */
export const ONE_TIME_BILL_KINDS = [
  "interim",
  "first",
  "final",
  "backbill",
  "penalty",
  "fee",
] as const;
export type OneTimeBillKind = (typeof ONE_TIME_BILL_KINDS)[number];

export interface OneTimeBillPeriod {
  period_start: string;
  period_end: string;
}

/** A value typed on step 2 and not yet saved — priced as provisional (§2).
 *  Role `estimate` (DEF-BIL-8562) carries NO value: the clerk asks for the
 *  meter's own estimate, which the server takes from Meter Reads. */
export interface OneTimeBillReadingInput {
  asset_id: string;
  read_at: string;
  value: string;
  role: "current" | "move_in" | "last_period" | "estimate";
  /** The meter's service — set on an `estimate` row only. */
  service?: string;
}

/** §2's request. `bill_date` and `due_days` are required on every kind; the
 *  screen still SENDS an empty one as `null` so the server names it on its
 *  field in the same pass as every other problem (A3). */
export interface OneTimeBillRequest {
  account_id: string;
  kind: OneTimeBillKind;
  period_start?: string;
  period_end?: string;
  sub_periods?: OneTimeBillPeriod[];
  reason_code?: string;
  charge_code?: string;
  /** DEF-RAT-8753 — the amount for a code priced *entered when used*
   *  (`per_case`); refused beside any other code (BR-BIL-020). */
  entered_amount?: string;
  bill_date: string | null;
  due_days: number | null;
  readings?: OneTimeBillReadingInput[];
  /** §6 · DB2/DB3 — three WORDS the draft records in its snapshot; none is
   *  money. Sent on the DRAFT only (the preview prices nothing from them):
   *  a final bill's chosen settlement path, a penalty's evidence text, a fee's
   *  note printed on the bill. */
  settlement_path?: "collect" | "payment_plan" | "transfer";
  evidence?: string;
  note?: string;
  /** DEF-BIL-9077 — the services whose meter ROLLED OVER inside the period
   *  and whose rollover the clerk accepted; any other is held by name
   *  (`possible_rollover`). Sent on the preview and the draft alike. */
  accepted_rollovers?: string[];
}

export type OneTimeBillServiceStatus =
  | "billed"
  | "follows_basis"
  | "not_in_service"
  | "not_taken"
  | "billed_base_zero";

export interface OneTimeBillAccount {
  id: string;
  account_no: string | null;
  name: string | null;
  address: string | null;
  plan: string | null;
  status_name: string;
  balance: string | null;
  currency: string;
  cycle_due_days: number | null;
  /** DEF-BIL-8329 — the cycle's own name; null when the unit is on no cycle.
   *  Optional so an older server's answer still types. */
  cycle_name?: string | null;
  last_bill_on: string | null;
  moved_in_on: string | null;
}

export interface OneTimeBillServiceRow {
  service: string;
  assets: { asset_id: string; label: string }[];
  /** DEF-BIL-8316 — what one asset IS: a `meter`, or a thing priced by COUNT
   *  in `count_unit` (`cart`); null for a %-of-service. */
  asset_kind?: "meter" | "count" | null;
  count_unit?: string | null;
  /** `DEF-BIL-10221` — the INSTALLED CAPACITY this tariff bills (`57.84` `kW`)
   *  for a service priced per the unit its sizes sum in; `count_unit` is then
   *  null, because two panels are not "2 KW". Absent/null everywhere else. */
  installed?: { quantity: string; unit: string } | null;
  status: OneTimeBillServiceStatus;
  basis_service: string | null;
  count: number;
  on_bill: string;
}

export interface OneTimeBillRateRow {
  service: string;
  asset_id: string | null;
  asset_label: string | null;
  rate_type:
    | "tiered"
    | "flat"
    | "per_asset"
    | "percent_of_service"
    | "time_of_use"
    | "demand"
    | "capacity"
    | null;
  /** `tiers` for a tiered rate; the contract draws only that shape, so any
   *  other rate type carries its price in `price` + `unit`, or a percent. */
  usage_rate: {
    tiers?: { up_to: string | null; unit: string; price: string }[];
    price?: string;
    unit?: string;
    percent?: string;
    basis_service?: string;
  } | null;
  base_charge: {
    amount: string;
    code: string | null;
    set: boolean;
    per_asset: boolean;
    prorated: string | null;
  } | null;
  minimum: string | null;
  /** `from` is the day the version took effect (DEF-BIL-8316). */
  versions: { label: string; from: string | null }[];
  amount: string;
  /** DEF-BIL-10067 — a service cut at its own rate change: one part per
   *  stretch, oldest first, with its dates, rate, usage share and amount.
   *  Absent or empty for a service that was not cut. */
  parts?: OneTimeBillRatePart[];
}

export interface OneTimeBillRatePart {
  period_start: string;
  period_end: string;
  days: number;
  usage_rate: OneTimeBillRateRow["usage_rate"];
  quantity: string | null;
  unit: string | null;
  amount: string;
  version_label: string;
  version_from: string | null;
}

export type OneTimeBillReadingStatus =
  | "waiting"
  | "accepted"
  | "refused"
  | "estimated"
  | "assessed"
  | "actual";

export interface OneTimeBillReadingRow {
  asset_id: string;
  label: string;
  unit: string;
  previous: { value: string | null; read_at: string | null; on_file: boolean };
  current: { value: string | null; read_at: string | null; fixed_date: boolean };
  usage: string | null;
  status: OneTimeBillReadingStatus;
  refusal_key: string | null;
  period_index: number | null;
}

export type OneTimeBillReadingsNeeded =
  | "every_meter"
  | "move_in_and_new"
  | "final"
  | "last_period"
  | "none";

export interface OneTimeBillPeriodRow {
  period_start: string;
  period_end: string;
  days: number;
  versions: string[];
  /** DEF-BIL-8328 — `waiting` while a meter in the period has no reading yet. */
  reading: "actual" | "estimated" | "assessed" | "waiting";
  split_on: string | null;
}

export interface OneTimeBillMoveInCharges {
  moved_in_on: string;
  deposit_asked: string;
  deposit_paid: string;
  lines: { kind: "deposit" | "fee"; code?: string; label: string; amount: string }[];
}

export interface OneTimeBillSettlement {
  this_bill: string;
  prior_balance: string;
  deposit: string;
  interest: string;
  remainder: string;
  automatic: "write_off" | "refund" | null;
  paths: string[];
}

export interface OneTimeBillCharge {
  code: string;
  label: string;
  amount: string;
  taxable: boolean;
}

export type OneTimeBillLineCharge =
  | "usage"
  | "base"
  | "per_asset"
  | "percent"
  | "deposit"
  | "fee"
  | "minimum"
  | "discount";

export interface OneTimeBillLine {
  service: string;
  asset_label: string | null;
  charge: OneTimeBillLineCharge;
  quantity: string | null;
  unit: string | null;
  /** `tiered`, or a decimal string. */
  rate: string | null;
  amount: string;
  flags: string[];
  /** DEF-BIL-8312 — a fee or deposit line's charge code (`RECON`). */
  code?: string | null;
  /** DEF-BIL-8315 — the unit a counted service's line is per (`cart`). */
  per_unit?: string | null;
  /** PO 2026-10-01 — the size × count × base a capacity line was priced
   *  from (`one_time_answer.size_breakdown`); `[]` on every other line. */
  breakdown?: {
    size: string | null;
    size_label?: string | null;
    count: number | null;
    base_each: string | null;
    price_each?: string | null;
    base_priced?: boolean;
  }[];
  /** DEF-BIL-8744 — the days this line's amount was cut down by
   *  (`{days: 19, of: 30}`); null on every line that foots without it. */
  day_share?: DayShare | null;
}

export interface OneTimeBillGroup {
  label: string;
  period_start: string | null;
  period_end: string | null;
  subtotal: string;
  lines: OneTimeBillLine[];
}

export interface OneTimeBillDocument {
  groups: OneTimeBillGroup[];
  /** NULL — never `0.00` — while a meter still waits for its reading
   *  (DEF-BIL-8300): a zero on a bill preview says the customer owes nothing. */
  subtotal: string | null;
  tax: { label: string; rate: string; amount: string }[];
  /** DEF-BIL-8565 — a first bill's deposit and connection charge, a penalty's
   *  tamper charge: their own footer line, so Subtotal + Tax + this = Total.
   *  Null where there are none, and on a fee bill (its charge is the subtotal). */
  one_time_charges?: string | null;
  total: string | null;
  currency: string;
}

/** A catalogue key and its params — never server prose. */
export interface OneTimeBillWarning {
  key: string;
  params: Record<string, unknown>;
}

/** Who billed this period already — §4's `409` params. The preview carries
 *  the same object as `duplicate`, which is how the banner stands on step 2
 *  where it is drawn. `invoice_id` is not in §4's params list; it is read when
 *  present so the banner's link can open the bill itself. */
export interface OneTimeBillDuplicate {
  invoice_no: string | null;
  run_id: string;
  invoice_id?: string | null;
  ran_by_name: string | null;
  ran_at: string | null;
  /** DEF-BIL-10068 — the colliding bill's status. `draft` → step 1 offers
   *  Open draft / Discard draft; anything else is *Already billed*. Optional
   *  so an older server's answer still types (absent reads as billed). */
  status?: string | null;
}

/** DEF-BIL-10068 / 10069 — `POST /billing/one-time/period-check`: what step 1
 *  says the moment the period is picked. Writes nothing, prices nothing. */
export interface OneTimeBillPeriodCheck {
  duplicate: OneTimeBillDuplicate | null;
  /** The closed fiscal period the bill's date falls in, and the earliest open
   *  one its entry will be booked in (BR-TEN-038). Null when the month is open. */
  closed_month: { requested_period: string[]; posted_period: string[] } | null;
}

export async function checkOneTimePeriod(
  body: OneTimeBillRequest,
  client: ApiClient = api,
): Promise<OneTimeBillPeriodCheck> {
  return requireData(await client.post<OneTimeBillPeriodCheck>("/billing/one-time/period-check", body));
}

/** §2's answer. A section a kind does not have is `null`. */
export interface OneTimeBillPreview {
  kind: OneTimeBillKind;
  account: OneTimeBillAccount;
  defaults: { bill_date: string; due_days: number | null };
  due_date: string | null;
  services: OneTimeBillServiceRow[] | null;
  rates: OneTimeBillRateRow[] | null;
  readings: { needed: OneTimeBillReadingsNeeded; rows: OneTimeBillReadingRow[] } | null;
  periods: OneTimeBillPeriodRow[] | null;
  move_in_charges: OneTimeBillMoveInCharges | null;
  settlement: OneTimeBillSettlement | null;
  charge: OneTimeBillCharge | null;
  bill: OneTimeBillDocument;
  warnings: OneTimeBillWarning[];
  duplicate: OneTimeBillDuplicate | null;
  /** DEF-BIL-8300 — present when the preview could not price yet because a
   *  meter is still waiting for its reading. */
  waiting_for?: { reason: string | null; service_code: string | null };
}

/** §4 — the draft's `201`. */
export interface OneTimeBillDraft {
  run_id: string;
  invoice_id: string;
  invoice_no: string | null;
  total: string;
  currency: string;
  due_date: string | null;
  bill: OneTimeBillDocument;
  warnings: OneTimeBillWarning[];
}

export const ONE_TIME_BILL_DELIVERIES = ["email", "paper", "email_and_paper"] as const;
export type OneTimeBillDelivery = (typeof ONE_TIME_BILL_DELIVERIES)[number];

/** §5's body. PO 2026-09-30, option B: the FIVE release confirmations a cycle
 *  release asks, each as the clerk ticked it — the server refuses unless every
 *  one is literal `true`, naming each on `confirmations.<name>`. (Was a single
 *  `acknowledged` tick recorded as all five.) */
export interface OneTimeBillSendBody {
  confirmations: {
    compliance: boolean;
    email_mandate: boolean;
    sms_mandate: boolean;
    autopay_mandate: boolean;
    final: boolean;
  };
  delivery: OneTimeBillDelivery;
  sent_at: string;
  /** A penalty's approver, RECORDED and never required (PO 2026-09-30): a
   *  staff user or a typed name. Omitted when nobody is named. */
  approved_by?: { user_id: string } | { name: string };
}

/** §5's answer. */
export interface OneTimeBillSent {
  invoice_no: string | null;
  total: string;
  currency: string;
  due_date: string | null;
  delivery: "queued";
  reads: "locked";
}

/** `GET /billing/one-time/accounts/{id}` — step 1's account card, read from
 *  the ACCOUNT the moment it is chosen and never waiting on a preview
 *  (DEF-BIL-8281). The same shape as the preview's `account`. */
export async function getOneTimeAccount(
  accountId: string,
  client: ApiClient = api,
): Promise<OneTimeBillAccount> {
  return requireData(
    await client.get<OneTimeBillAccount>(`/billing/one-time/accounts/${encodeURIComponent(accountId)}`),
  );
}

/** `POST /billing/one-time/preview` — writes nothing. */
export async function previewOneTime(
  body: OneTimeBillRequest,
  client: ApiClient = api,
): Promise<OneTimeBillPreview> {
  return requireData(await client.post<OneTimeBillPreview>("/billing/one-time/preview", body));
}

/** `POST /billing/one-time` — the draft. A `409 BIZ-IDEMPOTENT` names who
 *  billed the period already. */
export async function draftOneTime(
  body: OneTimeBillRequest,
  client: ApiClient = api,
): Promise<OneTimeBillDraft> {
  return requireData(await client.post<OneTimeBillDraft>("/billing/one-time", body));
}

/** `POST /billing/one-time/{run_id}/send` — authorise and issue this run's one
 *  draft. Idempotent: a second call answers the same bill. */
export async function sendOneTime(
  runId: string,
  body: OneTimeBillSendBody,
  client: ApiClient = api,
): Promise<OneTimeBillSent> {
  return requireData(
    await client.post<OneTimeBillSent>(
      `/billing/one-time/${encodeURIComponent(runId)}/send`,
      body,
    ),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-015@a71c4e2 (sources: 04-docs/05-modules/07-billing/06-epics/EP-BIL-04-corrections.md · EP-BIL-05-budget-billing.md · EP-BIL-06-templates-delivery.md · EP-BIL-01-bill-run.md US-BIL-006 · 07-billing/02-business-rules.md · the four server payload builders in 06-backend/apps/billing/{corrections_api,budget_api,documents_api,templates_api}.py; co-packets US-BIL-016, US-BIL-017, US-BIL-018, US-BIL-019, US-BIL-020, US-BIL-021, US-BIL-022, US-BIL-031, US-BIL-006)
// [One-time bill lane 2026-08-16 — US-BIL-010..014]
// packet: US-BIL-012@f0a3c21 (sources: EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md BR-BIL-012/013/018/019/020/023 · 06-backend/apps/billing/one_time.py's own payload builders; co-packets US-BIL-010, US-BIL-011, US-BIL-013, US-BIL-014)
// exceptions: E3 NO one-time body type carries an `amount`, `description` or `lines` member — BR-BIL-020 forbids the concept and the server has no parameter to receive one · E3 `OneTimePreview` has NO `total`: a prepare pass prices nothing and a zero would be a money claim · E3 `OneTimeSettlement.recorded` is typed and is always false — there is no `final_settlements` table, and omitting the field would let a screen imply the settlement was saved
// generated: 2026-08-16 by story-coder (billing SURFACE lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: E3 THIS FILE IS SEPARATE FROM `endpoints.ts` on purpose — that file is 7,200 lines and holds two or three lanes' half-finished work on any afternoon (the bankRecEndpoints.ts precedent) · E3 NO wrapper carries a `mechanism` field: BR-BIL-041 derives it and the server refuses a supplied one, so a client type with the field would be an invitation to a silent underbilling · E3 every money member is a decimal STRING beside a `currency`, never a number · E3 `computed_level`, `net_delta`, `bills`, `parameters` and `backbill_window_months` are all nullable and NONE may be defaulted by a caller — each null is a distinct fact the server means, and each rides beside its own `*_unavailable` sentence · E3 `requireData` is restated here rather than imported: `endpoints.ts` does not export it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
