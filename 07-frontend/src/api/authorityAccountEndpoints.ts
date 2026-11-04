// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 2 task 3 — Settings › Accounting › Authority
//           accounts (CR §7 item 1; the API contract is CR §9).
// Rules:    NFR-3 (every list pages on the server) · B14 rule 31 (an id is an
//           address, never a displayed value)
// ───────────────────────────────────────────────────────
//
// THE ACCOUNTS A UTILITY HOLDS WITH ITS TAX AUTHORITIES.
//
// PO 2026-10-02: *"Your account can come from settings we ahve configure
// accounts sections"*. One row is an authority's name and the number that
// authority knows the utility by (*TX Comptroller · 32-1180455*), typed once
// here and picked on every tax's *Account with the authority*.
//
// In its own file, like `runHistoryEndpoints.ts`, so the screens that read it
// do not have to share `endpoints.ts` with every lane editing it this week.

import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";
import type { PagedRows } from "./paginated";
import { readListPage } from "./paginated";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export const AUTHORITY_ACCOUNTS_PATH = "/settings/authority-accounts";

/** One row of `GET /settings/authority-accounts` — CR §9, verbatim. */
export interface AuthorityAccount {
  /** ⚠ NEVER RENDERED (B14 rule 31) — the address of the row. */
  id: string;
  authority_name: string;
  account_number: string;
  /** The tax authority it belongs to, where the utility said; else null. */
  jurisdiction_id: string | null;
  /** `false` = retired: kept on every tax that files under it, no longer offered. */
  active: boolean;
}

export interface AuthorityAccountQuery {
  page: number;
  per: number;
  q?: string;
  /** `f.active` — `"true"` lists only the accounts a new tax may pick. */
  active?: "true" | "false";
}

export async function getAuthorityAccountsPage(
  query: AuthorityAccountQuery,
  client: ApiClient = api,
): Promise<PagedRows<AuthorityAccount>> {
  return readListPage<AuthorityAccount>(
    AUTHORITY_ACCOUNTS_PATH,
    {
      page: query.page,
      per: query.per,
      q: query.q || undefined,
      "f.active": query.active,
    },
    client,
  );
}

export interface AuthorityAccountChanges {
  authority_name?: string;
  account_number?: string;
  jurisdiction_id?: string | null;
  active?: boolean;
}

export async function createAuthorityAccount(
  payload: AuthorityAccountChanges,
  client: ApiClient = api,
): Promise<AuthorityAccount> {
  return requireData(await client.post<AuthorityAccount>(AUTHORITY_ACCOUNTS_PATH, payload));
}

export async function updateAuthorityAccount(
  id: string,
  payload: AuthorityAccountChanges,
  client: ApiClient = api,
): Promise<AuthorityAccount> {
  return requireData(
    await client.patch<AuthorityAccount>(
      `${AUTHORITY_ACCOUNTS_PATH}/${encodeURIComponent(id)}`,
      payload,
    ),
  );
}
