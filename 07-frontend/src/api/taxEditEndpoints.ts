// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — the EDIT form's three saves (images 24–33).
// Contract: CR-165-BRC10 §9 / §10 — `PATCH /taxes/{id}` (name and filing only on
//           a live tax), `POST /taxes/{id}/new-rate`, `POST /taxes/{id}/corrections`,
//           and the tax read's added `version` / `authority_account`.
// ───────────────────────────────────────────────────────
//
// Kept beside `taxFormEndpoints.ts` rather than appended to `endpoints.ts`, so
// the edit lane and the details lane (which also reads the tax) do not both
// write the one 22,000-line file at once.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";
import type { TaxRow } from "./endpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** The tax read as round 2 serves it: `TaxRow` plus the fields CR-165 §9 added
 *  that the edit form reads. Optional, so an older fixture still type-checks. */
export interface TaxEditRow extends TaxRow {
  /** 1-based within the tax's chain (`v1`, `v2`). */
  version?: number;
  authority_account?: { id: string; label: string } | null;
}

/** `POST /taxes/{id}/new-rate` — *New rate from a date*. Ends the live version
 *  the day before `effective_from` and creates the next, in one transaction. */
export interface NewTaxRateResult extends TaxEditRow {
  ended_version?: { id: string; version: number; effective_to: string };
  issued_bills_unchanged?: boolean;
}

export async function newTaxRate(
  taxId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<NewTaxRateResult> {
  return requireData(
    await client.post<NewTaxRateResult>(`/taxes/${encodeURIComponent(taxId)}/new-rate`, payload),
  );
}
