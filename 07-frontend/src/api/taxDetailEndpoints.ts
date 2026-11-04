// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax DETAILS page.
// Contract: CR-165-BRC10 §9 (names fixed there, never renamed here) and §10
//           (what the back end shipped in 2.472.0).
// ───────────────────────────────────────────────────────
//
// The reads and writes the details page needs that `endpoints.ts` does not
// carry. Kept in their own file for the reason `taxFormEndpoints.ts` gives: the
// list, form, edit and details lanes all build at once, and none of them should
// be appending to the one 22,000-line file in the same hour.
import { api } from "./client";
import type { ApiClient } from "./client";
import type { TaxPlanReach, TaxRow } from "./endpoints";
import { readListPage } from "./paginated";
import type { PagedRows } from "./paginated";

/**
 * `GET /taxes/{id}` as round 2 serves it (§9). The six fields are on every
 * reply since 2.472.0; they are typed optional here, as the list lane typed
 * them, so a fixture written before the contract still compiles and an absent
 * value renders a dash rather than a guess.
 */
export type TaxDetailRow = TaxRow & {
  /** 1-based within the tax's chain — *V2*. */
  version?: number | null;
  /** The Settings › Accounting row this tax files under. Render `label`. */
  authority_account?: { id: string; label: string } | null;
  /** ISO date — the next filing due date. Shown only on an ACTIVE tax. */
  next_filing_due?: string | null;
  /** The next saved version that starts after today. */
  scheduled_next?: { rate_display: string | null; effective_from: string | null } | null;
  premises_reached?: number | null;
  premises_total?: number | null;
};

/** One `GET /taxes/{id}/plans` row: `accounts` (open accounts) beside `units`.
 *  `null` means the customers module could not answer — a dash, never a zero. */
export type TaxPlanRow = TaxPlanReach & { readonly accounts?: number | null };

export async function getTaxPlanRows(taxId: string, client: ApiClient = api): Promise<TaxPlanRow[]> {
  const response = await client.get<TaxPlanRow[]>(`/taxes/${encodeURIComponent(taxId)}/plans`);
  return Array.isArray(response.data) ? response.data : [];
}

/**
 * The audit module's own actor shape (§9 clarification): `{id, name}` for a
 * person, `{kind, name, version}` for an automation, `null` for an unnamed
 * system job. The screen renders `name` and never `id` (B14 rule 31).
 */
export interface TaxAuditActor {
  readonly id?: string | null;
  readonly name?: string | null;
  readonly kind?: string | null;
}

/** One `GET /taxes/{id}/audit` row. On an update `before` and `after` carry
 *  only the fields that changed; a create carries `before: null`. */
export interface TaxAuditEntry {
  readonly at: string | null;
  readonly actor: TaxAuditActor | null;
  readonly action: string;
  readonly before: Record<string, unknown> | null;
  readonly after: Record<string, unknown> | null;
  readonly reason: string | null;
}

/** `GET /taxes/{id}/audit`, ONE page (NFR-3 — the server pages, newest first). */
export function getTaxAuditPage(
  taxId: string,
  paging: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<TaxAuditEntry>> {
  return readListPage<TaxAuditEntry>(
    `/taxes/${encodeURIComponent(taxId)}/audit`,
    { page: paging.page, per: paging.per },
    client,
  );
}

/** `POST /taxes/{id}/retire` — ends the window on `effective_to`. A retired
 *  tax prices every bill dated up to that day and nothing after it. */
export async function retireTax(
  taxId: string,
  body: { effective_to: string; reason?: string },
  client: ApiClient = api,
): Promise<TaxDetailRow> {
  const response = await client.post<TaxDetailRow>(
    `/taxes/${encodeURIComponent(taxId)}/retire`,
    body,
  );
  return response.data as TaxDetailRow;
}

/** `POST /plans/{id}/taxes` — attach this tax to one plan (BR-RAT-113). A
 *  PUBLISHED plan requires `reason` (BR-RAT-037); the server says so by name. */
export async function attachTaxToPlan(
  planId: string,
  body: { tax: string; reason?: string },
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/plans/${encodeURIComponent(planId)}/taxes`, body);
}

/** `DELETE /plans/{plan}/taxes/{tax}` — remove an EXPLICIT attachment. A tax
 *  the plan's authority brings is refused by name; the screen never offers it. */
export async function detachTaxFromPlan(
  planId: string,
  taxId: string,
  body: { reason?: string },
  client: ApiClient = api,
): Promise<void> {
  await client.request(
    `/plans/${encodeURIComponent(planId)}/taxes/${encodeURIComponent(taxId)}`,
    { method: "DELETE", body },
  );
}
