// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the reads and acts the discount
//           DETAILS page needs (images 19–26).
// Contract: CR-166-BRC10 §9 — `GET /discounts/{id}` (new shapes), `…/plans`,
//           `…/accounts`, `…/audit`, `…/submit`, `…/approve`, `…/send-back`,
//           `…/retire`, `POST /discount-enrolments/{id}/end`; and the
//           enrolment door `POST /accounts/{id}/discounts` (`DEF-RAT-9297`).
// Rules:    NFR-3 (every list is paged by the server) · B14 rule 31 (ids are
//           acted on, never shown) · BR-RAT-087 (the server's display strings)
// ───────────────────────────────────────────────────────
//
// ⚠ **A FILE OF ITS OWN, NOT MORE LINES IN `endpoints.ts`.** That file is
// 11,000 lines and the edit lane (round 3 task 7) works beside this one; a
// whole-file collision there is how work leaves a branch by subtraction
// (CLAUDE.md law 11). `taxDetailEndpoints.ts` made the same choice.
//
// ⚠ **THREE ROW KEYS CHANGED SHAPE IN 2.478.0 AND THIS TYPE SAYS SO.**
// `status` is the DERIVED six-value status, and `eligibility` and
// `exclusivity_group` are `{value, label}` objects (CR-166 §9 "Fields
// added"). `DiscountDetail` in `endpoints.ts` still types them as strings for
// the screens that predate the contract; this page reads them through
// `DiscountDetailRow` and never as strings.
import { api } from "./client";
import type { ApiClient } from "./client";
import type { DiscountDetail } from "./endpoints";
import { readListPage } from "./paginated";
import type { PagedRows } from "./paginated";

/** A per-utility list value as the contract serves it. */
export interface DiscountOptionValue {
  readonly value: string | null;
  readonly label: string;
  readonly checked_by?: "system" | "proof";
}

/** The six statuses the server derives from dates (CR-166 §9). */
export type DiscountDerivedStatus =
  | "draft"
  | "waiting_approval"
  | "scheduled"
  | "active"
  | "ended"
  | "retired";

/** `GET /discounts/{id}` as 2.478.0 serves it. Every §9 field is optional so
 *  a fixture written before the contract still type-checks; the page draws a
 *  dash for anything absent. */
export type DiscountDetailRow = Omit<DiscountDetail, "eligibility" | "exclusivity_group" | "status"> & {
  status: string;
  stored_status?: string | null;
  version?: number | null;
  program_owner?: DiscountOptionValue | null;
  exclusivity_group?: DiscountOptionValue | null;
  eligibility?: DiscountOptionValue | string | null;
  effective_to?: string | null;
  offered_to?: number | null;
  receiving?: number | null;
  /** NULL until `DEF-2430` records a grant at issue — never a zero. */
  granted_this_month?: string | null;
  scheduled_next?: { value_display: string | null; effective_from: string | null } | null;
  /** True once the version has been submitted (BR-RAT-1016). */
  version_submitted?: boolean;
  /** `DEF-RAT-9792` — the version in force today is Automatic: the nightly
   *  sync grants and ends it, so nobody enrols an account by hand. */
  enrolled_automatically?: boolean;
  /** `DEF-RAT-9833` (PO D2 (b), 2026-10-06) — what hides *+ Enroll an
   *  account*: an Automatic discount NO person may add (Municipal account).
   *  Autopay and Paperless are Automatic and addable by hand. */
  hand_enrolment_refused?: boolean;
  /** Added by round 3 task 6 (§9 "Fields added"): the money figures WITH the
   *  utility's symbol (`$4.00`), decided by the server beside its currency. */
  money_display?: Partial<Record<DiscountMoneyKey, string | null>>;
};

export type DiscountMoneyKey =
  | "cap_per_bill"
  | "cap_per_year"
  | "cap_lifetime"
  | "bill_floor_amount"
  | "budget_cap"
  | "budget_remaining";

/** One version of the discount, as `GET /discounts/{id}/versions` serves it. */
export interface DiscountVersionLine {
  readonly id: string;
  readonly version_no: number;
  readonly status: string;
  readonly value_display: string | null;
  readonly effective_from: string | null;
  /** Added by round 3 task 6 (§9 "Fields added"): image 19's *– 12/31/2026*. */
  readonly effective_to?: string | null;
}

export async function getDiscountDetail(discountId: string, client: ApiClient = api): Promise<DiscountDetailRow> {
  const response = await client.get<DiscountDetailRow>(`/discounts/${encodeURIComponent(discountId)}`);
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export async function getDiscountVersionLines(
  discountId: string,
  client: ApiClient = api,
): Promise<DiscountVersionLine[]> {
  const response = await client.get<DiscountVersionLine[]>(`/discounts/${encodeURIComponent(discountId)}/versions`);
  return Array.isArray(response.data) ? response.data : [];
}

// ── Plans ─────────────────────────────────────────────────────────────────

/** One `GET /discounts/{id}/plans` row (§9 + "Fields added"). */
export interface DiscountPlanRow {
  readonly plan_id: string;
  readonly plan: string;
  readonly plan_code?: string | null;
  readonly available_from: string | null;
  readonly available_to: string | null;
  readonly units: number;
  readonly accounts: number | null;
  /** Service CODES the plan covers — the screen words them. */
  readonly services?: readonly string[];
  /** Class NAMES; `[]` means every class. */
  readonly customer_classes?: readonly string[];
}

export function getDiscountPlanPage(
  discountId: string,
  paging: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<DiscountPlanRow>> {
  return readListPage<DiscountPlanRow>(
    `/discounts/${encodeURIComponent(discountId)}/plans`,
    { page: paging.page, per: paging.per },
    client,
  );
}

// ── Accounts ──────────────────────────────────────────────────────────────

export const DISCOUNT_ACCOUNT_STATUSES = ["receiving", "proof_pending", "renewal_due"] as const;
export type DiscountAccountStatus = (typeof DISCOUNT_ACCOUNT_STATUSES)[number];

/** One `GET /discounts/{id}/accounts` row. `enrolment_id` and `account_id`
 *  are what the screen ACTS on and links to; neither is ever printed. */
export interface DiscountAccountRow {
  readonly enrolment_id: string;
  readonly account_id: string;
  readonly account_number: string | null;
  readonly customer_name: string | null;
  readonly premises_address: string | null;
  readonly plan: string | null;
  readonly enrolled_on: string;
  readonly renew_by: string | null;
  /** NULL until `DEF-2430` records a grant at issue. */
  readonly this_month: string | null;
  readonly status: string;
  /** `DEF-CUS-9780` — the account document that is this enrolment's proof,
   *  served to a System Admin only (BR-RAT-079); null for every other role
   *  and for an enrolment with none. Acted on, never shown (B14 rule 31). */
  readonly proof_document_id?: string | null;
}

export interface DiscountAccountQuery {
  q?: string;
  status?: string;
  plan?: string;
  sort?: string;
  dir?: "asc" | "desc";
  page: number;
  per: number;
}

export function getDiscountAccountPage(
  discountId: string,
  query: DiscountAccountQuery,
  client: ApiClient = api,
): Promise<PagedRows<DiscountAccountRow>> {
  const params: Record<string, string | number> = { page: query.page, per: query.per };
  if (query.q !== undefined && query.q.trim() !== "") params.q = query.q.trim();
  if (query.status !== undefined && query.status !== "") params["f.status"] = query.status;
  if (query.plan !== undefined && query.plan !== "") params["f.plan"] = query.plan;
  if (query.sort !== undefined) params.sort = query.sort;
  if (query.dir !== undefined) params.dir = query.dir;
  return readListPage<DiscountAccountRow>(
    `/discounts/${encodeURIComponent(discountId)}/accounts`,
    params,
    client,
  );
}

/** `POST /discount-enrolments/{id}/end {ended_on, reason}` — one account stops
 *  receiving it from that date. */
export async function endDiscountEnrolment(
  enrolmentId: string,
  body: { ended_on: string; reason: string },
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/discount-enrolments/${encodeURIComponent(enrolmentId)}/end`, body);
}

/** `POST /discount-enrolments/{id}/verify` — the proof is on file: a *Proof
 *  pending* enrollment becomes *Receiving* (DEF-RAT-9325). */
export async function verifyDiscountEnrolment(enrolmentId: string, client: ApiClient = api): Promise<void> {
  await client.post(`/discount-enrolments/${encodeURIComponent(enrolmentId)}/verify`, {});
}

/** `POST /accounts/{id}/discounts {programme_id}` — enrol one account. The
 *  server refuses an account whose plan does not carry it (ruling 2). */
export async function enrolAccountInDiscount(
  accountId: string,
  discountId: string,
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/accounts/${encodeURIComponent(accountId)}/discounts`, { programme_id: discountId });
}

// ── Audit ─────────────────────────────────────────────────────────────────

export interface DiscountAuditEntry {
  readonly at: string | null;
  readonly actor: { readonly name?: string | null } | null;
  readonly action: string;
  readonly before: Record<string, unknown> | null;
  readonly after: Record<string, unknown> | null;
  readonly reason: string | null;
}

export function getDiscountAuditPage(
  discountId: string,
  paging: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<DiscountAuditEntry>> {
  return readListPage<DiscountAuditEntry>(
    `/discounts/${encodeURIComponent(discountId)}/audit`,
    { page: paging.page, per: paging.per },
    client,
  );
}

// ── Lifecycle (PO rulings 2026-10-03) ─────────────────────────────────────

/** Draft → Waiting approval. */
export async function submitDiscount(discountId: string, client: ApiClient = api): Promise<void> {
  await client.post(`/discounts/${encodeURIComponent(discountId)}/submit`, {});
}

/** The LAST act — the version goes live by itself on its start date. */
export async function approveDiscount(discountId: string, client: ApiClient = api): Promise<void> {
  await client.post(`/discounts/${encodeURIComponent(discountId)}/approve`, {});
}

/** Waiting approval → Draft, with the approver's note. */
export async function sendBackDiscount(
  discountId: string,
  body: { note: string },
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/discounts/${encodeURIComponent(discountId)}/send-back`, body);
}

/** After `effective_to` nobody gets it, enrolled accounts included. */
export async function retireDiscount(
  discountId: string,
  body: { effective_to: string; reason?: string },
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/discounts/${encodeURIComponent(discountId)}/retire`, body);
}

// ── The follow-up acts (CR-166 §18, 2026-10-03) ───────────────────────────

/** `POST /discounts/{id}/duplicate {code, name}` — a NEW DRAFT discount copied
 *  from the version in force (`DEF-RAT-9310`). Answers the new discount's row. */
export async function duplicateDiscount(
  discountId: string,
  body: { code: string; name: string },
  client: ApiClient = api,
): Promise<{ id: string; name: string; code: string }> {
  const response = await client.post<{ id: string; name: string; code: string }>(
    `/discounts/${encodeURIComponent(discountId)}/duplicate`,
    body,
  );
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** `POST /discounts/{id}/plans {plan, reason}` — the plan offers it from the
 *  utility's today (`DEF-478`). */
export async function addDiscountToPlan(
  discountId: string,
  body: { plan: string; reason: string },
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/discounts/${encodeURIComponent(discountId)}/plans`, body);
}

/** `DELETE /discounts/{id}/plans/{plan} {reason}` — ruling 2: stops from the
 *  next bill, and the enrollments of accounts on that plan end (`DEF-478`). */
export async function removeDiscountFromPlan(
  discountId: string,
  planId: string,
  body: { reason: string },
  client: ApiClient = api,
): Promise<void> {
  await client.request(
    `/discounts/${encodeURIComponent(discountId)}/plans/${encodeURIComponent(planId)}`,
    { method: "DELETE", body },
  );
}

/** `?format=csv` — the WHOLE filtered Accounts set, streamed by the server
 *  (`DEF-1005`, NFR-3: never a page, never capped). */
export async function getDiscountAccountsCsv(
  discountId: string,
  query: Omit<DiscountAccountQuery, "page" | "per">,
  client: ApiClient = api,
): Promise<string> {
  const params: Record<string, string> = { format: "csv" };
  if (query.q !== undefined && query.q.trim() !== "") params.q = query.q.trim();
  if (query.status !== undefined && query.status !== "") params["f.status"] = query.status;
  if (query.plan !== undefined && query.plan !== "") params["f.plan"] = query.plan;
  if (query.sort !== undefined) params.sort = query.sort;
  if (query.dir !== undefined) params.dir = query.dir;
  const response = await client.get<string>(`/discounts/${encodeURIComponent(discountId)}/accounts`, {
    query: params,
    accept: "text/csv",
  });
  return typeof response.data === "string" ? response.data : "";
}

/** `?format=csv` — every Audit row, streamed by the server (`DEF-1005`). */
export async function getDiscountAuditCsv(discountId: string, client: ApiClient = api): Promise<string> {
  const response = await client.get<string>(`/discounts/${encodeURIComponent(discountId)}/audit`, {
    query: { format: "csv" },
    accept: "text/csv",
  });
  return typeof response.data === "string" ? response.data : "";
}
