// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10591 — no screen could assign a route's reader (MQ-033).
// Ruling:   PO 2026-10-24 — assign/reassign on Reads → cycle → Routes
//           (decision log "MQ-033: METER-READ FORMAT TEMPLATES (option B), AND
//           READER ASSIGNMENT ON THE CYCLE'S ROUTES TAB").
// Server:   06-backend/apps/metering/route_readers.py · api.route_reader ·
//           api.route_reader_choices
// Tests:    07-frontend/src/features/metering/AssignReaderModal.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// Its own file for the reason `readCycleEndpoints.ts` gives in its header:
// `api/endpoints.ts` is shared by every lane, so one family is one file.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/paginated";

/** A route's reader as `route_dict` serves it. `id` is the anchor the dialog
 *  posts back and is never drawn (B14 rule 31). */
export interface RouteReader {
  id: string;
  name: string;
}

/** One picker row: an ACTIVE field technician of this utility. */
export interface ReaderChoice {
  id: string;
  name: string;
  email: string | null;
}

export interface SetRouteReaderResult {
  updated: number;
  unchanged: number;
  routes: { id: string; code: string; reader: RouteReader | null }[];
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** `GET /routes/reader-choices?q=` — the technicians a route may be given. */
export async function searchRouteReaders(
  q: string,
  client: ApiClient = api,
): Promise<ReaderChoice[]> {
  const params = new URLSearchParams({ q, per: "50" });
  const page = requireData(
    await client.get<Paginated<ReaderChoice>>(`/routes/reader-choices?${params.toString()}`),
  );
  return page.results;
}

/** `POST /routes/reader` — one or many routes; `readerId: null` unassigns. */
export async function setRouteReader(
  routeIds: readonly string[],
  readerId: string | null,
  client: ApiClient = api,
): Promise<SetRouteReaderResult> {
  return requireData(
    await client.post<SetRouteReaderResult>("/routes/reader", {
      route_ids: [...routeIds],
      reader_id: readerId,
    }),
  );
}
