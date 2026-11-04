// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-6342 — returned post reached nobody: no banner, no
//           needs-attention list, no way to clear the flag.
// Rules:    BR-PAY-018 · BR-TEN-043 (the business date is typed) · B14 rule 31
//           (the ids below are the ACTION's keys and never a visible value)
// ───────────────────────────────────────────────────────
// `GET /returned-mail` and `POST /returned-mail/clear` — payments'
// `apps/payments/returned_mail_api.py`.
//
// Its own file rather than more lines in `endpoints.ts`, which several lanes
// edit on any given afternoon (the `counterEndpoints.ts` precedent).
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";
import { readListPage } from "./paginated";
import type { PagedRows } from "./paginated";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** WHICH address a returned letter was posted to — the snapshot's own word.
 *  `null` is a letter queued before the service-address fallback, which
 *  carried no address at all. */
export type ReturnedLetterWentTo = "mailing_address" | "service_address" | null;

/** One open return on the needs-attention list, oldest first. */
export interface ReturnedPostRow {
  event_id: string;
  account_id: string;
  account_no: string | null;
  customer_name: string | null;
  returned_on: string;
  source_type: string;
  went_to: ReturnedLetterWentTo;
  address: string | null;
}

export const RESOLUTION_ADDRESS_CORRECTED = "address_corrected";
export const RESOLUTION_VERIFIED_CURRENT = "verified_current";
export type ReturnedPostResolution =
  | typeof RESOLUTION_ADDRESS_CORRECTED
  | typeof RESOLUTION_VERIFIED_CURRENT;

export interface ReturnedPostClearResult {
  account_id: string;
  resolution: ReturnedPostResolution;
  resolved_on: string;
  returns_resolved: number;
  flag_cleared: boolean;
  balances_affected: boolean;
}

export const returnedPostQueryKey = (accountId: string | null) =>
  ["returned-mail", accountId ?? "all"] as const;

/** The needs-attention list — narrowed to one account when `accountId` is given. */
export function getReturnedPost(
  params: { accountId?: string; page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<ReturnedPostRow>> {
  return readListPage<ReturnedPostRow>(
    "/returned-mail",
    { "f.account_id": params.accountId, page: params.page, per: params.per },
    client,
  );
}

/** Every open return on the account closed, then its bad-address flag lowered. */
export async function clearReturnedPost(
  body: { account_id: string; resolution: ReturnedPostResolution; resolved_on: string },
  client: ApiClient = api,
): Promise<ReturnedPostClearResult> {
  return requireData(
    await client.post<ReturnedPostClearResult>("/returned-mail/clear", body),
  );
}
