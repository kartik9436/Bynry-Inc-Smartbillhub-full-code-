// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — the EDIT discount form's read and its
//           three saves (images 27–36 of `05-prototype/discounts-2026-10-03/`).
// Contract: CR-166-BRC10 §9 — `GET /discounts/{id}`, `PATCH /discounts/{id}`
//           (name and details; value, limits and start refused by name on a
//           live discount), `POST /discounts/{id}/new-value` (the live version
//           ends the day before), `POST /discounts/{id}/corrections` (same
//           window, a reason, the old row kept and superseded).
// ───────────────────────────────────────────────────────
//
// Kept beside `discountFormEndpoints.ts` rather than appended to `endpoints.ts`,
// so this lane and the details lane (which also reads the discount) do not both
// write the one 22,000-line file at once — the tax edit's own reason.
//
// ⚠ **THREE KEYS OF THE DISCOUNT READ CHANGED SHAPE IN ROUND 2 (§9 *"Two
// existing row keys changed SHAPE"*), AND `DiscountDetail` STILL TYPES THE OLD
// ONES.** `eligibility`, `exclusivity_group` and `program_owner` are
// `{value, label}` objects now (eligibility also carries `checked_by`), and
// `status` is the DERIVED six-value status. `DiscountEditRow` restates those
// three keys, so this form reads the CODE out of each object; reading them as
// strings would put `[object Object]` into a dropdown that matches nothing.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";
import type { DiscountDetail } from "./endpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** A `{value, label}` pair as §9 serves it. `value` is `null` for a version
 *  saved before the lists existed and never mapped (its words only). */
export interface DiscountOptionValue {
  value: string | null;
  label: string;
  checked_by?: "system" | "proof";
}

/** The discount read as round 2 serves it. Every added key is optional or
 *  nullable, so a fixture written before §9 still type-checks. */
export interface DiscountEditRow extends Omit<DiscountDetail, "eligibility" | "exclusivity_group"> {
  /** 1-based number of the version shown (`v1`, `v2`). */
  version?: number | null;
  /** `draft · waiting_approval · scheduled · active · ended · retired`. */
  status: string;
  /** The STORED discount status, beside the derived one. */
  stored_status?: string;
  program_owner?: DiscountOptionValue | null;
  exclusivity_group?: DiscountOptionValue | string | null;
  eligibility?: DiscountOptionValue | string | null;
  /** A mixed read across two eras: the version's own `verification_method`
   *  is served as `verification` on the row. */
  verification: string | null;
}

/** The code inside a §9 `{value, label}` pair, or a pre-§9 plain string. */
export function optionCode(raw: DiscountOptionValue | string | null | undefined): string {
  if (raw === null || raw === undefined) return "";
  if (typeof raw === "string") return raw;
  return raw.value ?? "";
}

export async function getDiscountForEdit(discountId: string, client: ApiClient = api): Promise<DiscountEditRow> {
  return requireData(await client.get<DiscountEditRow>(`/discounts/${encodeURIComponent(discountId)}`));
}

/** `PATCH /discounts/{id}` — *Name and details*, saved on this version. */
export async function updateDiscountDetails(
  discountId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<DiscountEditRow> {
  return requireData(
    await client.patch<DiscountEditRow>(`/discounts/${encodeURIComponent(discountId)}`, payload),
  );
}

/** One version as the version writes return it (`version_row`). */
export interface DiscountVersionResult {
  id: string;
  version_no: number;
  status: string;
  effective_from: string | null;
  effective_to: string | null;
}

/** `POST /discounts/{id}/new-value` — *New value from a date*. The version in
 *  force ends the day before `effective_from`; 201 with the new version. */
export async function newDiscountValue(
  discountId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<DiscountVersionResult> {
  return requireData(
    await client.post<DiscountVersionResult>(`/discounts/${encodeURIComponent(discountId)}/new-value`, payload),
  );
}

/** `POST /discounts/{id}/corrections` — *Fix a mistake*: the same window, a
 *  reason, the corrected row kept and marked superseded. Answers the NEW
 *  version (the correction), which names the row it `corrects`. */
export interface DiscountCorrectionResult extends DiscountVersionResult {
  corrects?: string | null;
  issued_bills_unchanged?: boolean;
}

export async function correctDiscount(
  discountId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<DiscountCorrectionResult> {
  return requireData(
    await client.post<DiscountCorrectionResult>(
      `/discounts/${encodeURIComponent(discountId)}/corrections`,
      payload,
    ),
  );
}
