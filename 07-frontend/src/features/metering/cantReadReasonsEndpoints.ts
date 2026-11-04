// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10609 — Settings → Reference data → Readings →
//           Can't-read reasons (decision log 2026-10-26, PO *"yes do it"*).
//           Typed wrappers over `apps/metering/cant_read_reasons_api.py`.
// Rules:    NFR-3 (the list is paged on the server) · B14 rule 31 (a reason's
//           `code` is an ADDRESS, never drawn)
// Tests:    src/features/metering/cantReadReasons.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **`status` AND `q` GO BARE — NOT `f.<name>`.** The server reads
// `request.query_params.get("status")`, the read formats' reason
// (`readFormatsEndpoints.ts` header).
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { readListPage } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export interface CantReadReasonRow {
  /** Minted from the name at creation and fixed for life — readings name it. */
  code: string;
  name: string;
  sort_order: number;
  /** A starting reason: switched off, never deleted. */
  is_system: boolean;
  active: boolean;
  /** Route readings + job readings that named it. */
  used: number;
}

export interface CantReadReasonListQuery {
  status?: string;
  q?: string;
  page?: number;
  per?: number;
}

const BASE = "/settings/cant-read-reasons";

function at(code: string): string {
  return `${BASE}/${encodeURIComponent(code)}`;
}

export async function listCantReadReasons(
  query: CantReadReasonListQuery,
  client: ApiClient = api,
): Promise<PagedRows<CantReadReasonRow>> {
  return readListPage<CantReadReasonRow>(
    BASE,
    {
      status: query.status || undefined,
      q: query.q === undefined || query.q.trim() === "" ? undefined : query.q.trim(),
      page: query.page,
      per: query.per,
    },
    client,
  );
}

export async function addCantReadReason(name: string, client: ApiClient = api): Promise<CantReadReasonRow> {
  return requireData(await client.post<CantReadReasonRow>(BASE, { name }));
}

export async function updateCantReadReason(
  code: string,
  body: { name?: string; active?: boolean },
  client: ApiClient = api,
): Promise<CantReadReasonRow> {
  return requireData(await client.patch<CantReadReasonRow>(at(code), body));
}

export async function moveCantReadReason(
  code: string,
  direction: "up" | "down",
  client: ApiClient = api,
): Promise<CantReadReasonRow> {
  return requireData(await client.post<CantReadReasonRow>(`${at(code)}/move`, { direction }));
}

export async function deleteCantReadReason(code: string, client: ApiClient = api): Promise<void> {
  await client.del(at(code));
}

export const cantReadReasonKeys = {
  all: ["cant-read-reasons"] as const,
  list: (query: CantReadReasonListQuery) => ["cant-read-reasons", "list", query] as const,
};
