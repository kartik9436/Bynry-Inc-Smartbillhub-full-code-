// ── Trace ──────────────────────────────────────────────
// Change:   CR-194-BRC10 — refused field work, kept for the office (PO
//           2026-10-26, *"store on both"*)
// Server:   06-backend/apps/work/refused_items_api.py ·
//           06-backend/apps/work/refused_items.py (`answer`, `office_detail`)
// Rules:    NFR-3 (server-paged, no cap) · B14 rule 31 (ids travel, never shown)
// ───────────────────────────────────────────────────────
//
// In its own file for `fieldDeskEndpoints.ts`'s reason (hard-won law 11): the
// shapes are typed from the server function that builds the reply, and the
// list's extras (`counts`, `facets`) are read through `readListPageWith`
// because `_envelope` discards every key it does not know.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { readListPageWith } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";

/** `STATUSES` in `refused_models.py`, in the order the filter offers them. */
export const REFUSED_STATUSES = ["open", "reviewed", "applied", "applied_later"] as const;
export type RefusedStatus = (typeof REFUSED_STATUSES)[number];
export type RefusedCounts = Record<RefusedStatus, number>;

/** One copy as `refused_items.answer` builds it. `id`, `technician_id` and
 *  `work_order.id` are ADDRESSES and never drawn (rule 31). */
export interface RefusedRow {
  id: string;
  door: "job" | "reads";
  kind: string;
  status: RefusedStatus;
  reason: string;
  message_key: string;
  params: Record<string, unknown>;
  technician: string | null;
  technician_id: string | null;
  work_order: { id: string; order_no: string | null } | null;
  captured_at: string | null;
  first_refused_at: string;
  last_refused_at: string;
  refusal_count: number;
  photographs: number;
  note: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  applied_by: string | null;
  applied_at: string | null;
}

export interface RefusedFacets {
  reasons: { reason: string; message_key: string }[];
  kinds: string[];
  technicians: { id: string; name: string }[];
}

export interface RefusedPhoto {
  state: "uploaded" | "on_phone";
  attachment_id?: string;
  work_order_id?: string;
}

/** The payload as its kind's fields — `refused_items._work_of`. */
export interface RefusedWork {
  kind: string;
  note?: string;
  reading?: {
    prompt?: string | null;
    meter_no?: string | null;
    value?: string | null;
    unit?: string | null;
    value_text?: string | null;
    unable_to_read?: boolean;
    unable_reason?: string | null;
    flagged?: boolean;
    reader_status?: string | null;
    cant_read_reason?: string | null;
  };
  task?: { title: string | null };
  safety?: { text: string | null };
  material?: { part: string | null; qty: string | null; unit: string | null };
  close?: { outcome: string | null };
}

export interface RefusedDetail extends RefusedRow {
  work: RefusedWork;
  photos: RefusedPhoto[];
  can_apply: boolean;
}

export interface RefusedQuery {
  status?: string;
  reason?: string;
  technician?: string;
  kind?: string;
  q?: string;
  page: number;
  per: number;
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("refused work: the server answered no body");
  }
  return response.data;
}

/** `GET /work/refused-items` — a cleared status filter sends `all`, because the
 *  server's own default is `open` (the posture of the findings pane). */
export async function listRefusedWork(
  query: RefusedQuery,
  client: ApiClient = api,
): Promise<PagedRows<RefusedRow> & { body: { counts?: RefusedCounts; facets?: RefusedFacets } }> {
  const blankToUndefined = (value: string | undefined) => (value === undefined || value === "" ? undefined : value);
  return readListPageWith<RefusedRow, { counts?: RefusedCounts; facets?: RefusedFacets }>(
    "/work/refused-items",
    {
      status: query.status === undefined || query.status === "" ? "all" : query.status,
      reason: blankToUndefined(query.reason),
      technician: blankToUndefined(query.technician),
      kind: blankToUndefined(query.kind),
      q: blankToUndefined(query.q),
      page: query.page,
      per: query.per,
    },
    client,
  );
}

export async function getRefusedWork(itemId: string, client: ApiClient = api): Promise<RefusedDetail> {
  return requireData(await client.get<RefusedDetail>(`/work/refused-items/${itemId}`));
}

/** *Mark reviewed* — `{note?}`. */
export async function markRefusedReviewed(
  itemId: string,
  note: string,
  client: ApiClient = api,
): Promise<RefusedDetail> {
  return requireData(await client.post<RefusedDetail>(`/work/refused-items/${itemId}/review`, { note }));
}

/** *Apply to the job* — the kind's normal path, as the office person. */
export async function applyRefusedWork(itemId: string, client: ApiClient = api): Promise<RefusedDetail> {
  return requireData(await client.post<RefusedDetail>(`/work/refused-items/${itemId}/apply`, {}));
}
