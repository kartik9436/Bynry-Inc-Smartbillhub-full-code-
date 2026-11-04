// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11, the Settings → Reads screens for
//           utility-defined meter-read FORMATS. Typed wrappers over the routes
//           task 10 built (`apps/metering/read_formats_api.py`).
// Rules:    BR-MET-1210 … BR-MET-1214 · NFR-3 (the list is paged on the
//           server) · B14 rule 31 (every `id` here is an ADDRESS, never drawn)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ONE FAMILY, ONE FILE — `readCycleEndpoints.ts` gives the reason in its own
// header: `api/endpoints.ts` is shared by every lane on any afternoon.
//
// ⚠ **THE LIST TAKES `service`, `status` AND `q` BARE — NOT `f.<name>`.** The
// server reads `request.query_params.get("service")` (`read_formats_api.
// formats`), so the shared `listPage` serialiser, which prefixes every filter
// with `f.`, would send filters the server never reads and the list would
// look filtered while showing everything.
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

export type ReadFormatStatus = "draft" | "published" | "retired";

/** `ASKED_WHEN`, in the ruling's own order (`read_format_models.py`). */
export const ASKED_WHEN = ["every_reading", "out_of_range", "cant_read", "once_per_stop"] as const;
export type AskedWhen = (typeof ASKED_WHEN)[number];

/** The one type a question has that a custom field does not. */
export const PHOTO_TYPE = "photo";

export interface UsedBy {
  routes: number;
  cycles: number;
  services: number;
}

export interface ReadFormatRow {
  id: string;
  name: string;
  service: { code: string; name: string };
  status: ReadFormatStatus;
  current_version: { id: string; version_no: number; published_at: string | null } | null;
  draft_version_id: string | null;
  used_by: UsedBy;
  retired_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** An answer a `show_if` or a `raise_work` names: a word, a yes/no, a number. */
export type AnswerValue = string | number | boolean;

export interface ReadFormatQuestion {
  id: string;
  seq: number;
  key: string;
  label: string;
  help_text: string | null;
  data_type: string;
  options: string[] | null;
  is_required: boolean;
  asked_when: AskedWhen;
  show_if: { question_key: string; answer: AnswerValue } | null;
  raise_work: {
    on_answer: AnswerValue;
    template_id: string | null;
    template: { name: string; template_no: string | null } | null;
  } | null;
}

export interface ReadFormatVersion {
  id: string;
  read_format_id: string;
  state: "draft" | "published";
  version_no: number | null;
  change_note: string | null;
  published_at: string | null;
  published_by: string | null;
  created_at: string | null;
  questions?: ReadFormatQuestion[];
}

export interface ReadFormatDetail extends ReadFormatRow {
  current: ReadFormatVersion | null;
  draft: ReadFormatVersion | null;
}

export interface ReadFormatListQuery {
  service?: string;
  status?: string;
  q?: string;
  page?: number;
  per?: number;
}

const BASE = "/settings/read-formats";

export async function listReadFormats(
  query: ReadFormatListQuery,
  client: ApiClient = api,
): Promise<PagedRows<ReadFormatRow>> {
  return readListPage<ReadFormatRow>(
    BASE,
    {
      service: query.service || undefined,
      status: query.status || undefined,
      q: query.q === undefined || query.q.trim() === "" ? undefined : query.q.trim(),
      page: query.page,
      per: query.per,
    },
    client,
  );
}

export async function createReadFormat(
  body: { name: string; service: string },
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  return requireData(await client.post<ReadFormatDetail>(BASE, body));
}

export async function getReadFormat(id: string, client: ApiClient = api): Promise<ReadFormatDetail> {
  return requireData(await client.get<ReadFormatDetail>(`${BASE}/${id}`));
}

export async function updateReadFormat(
  id: string,
  body: { name?: string },
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  return requireData(await client.patch<ReadFormatDetail>(`${BASE}/${id}`, body));
}

export async function listReadFormatVersions(
  id: string,
  query: { page?: number; per?: number },
  client: ApiClient = api,
): Promise<PagedRows<ReadFormatVersion>> {
  return readListPage<ReadFormatVersion>(`${BASE}/${id}/versions`, query, client);
}

/** The body a question add/edit sends — the server's own field names. */
export interface QuestionBody {
  label: string;
  help_text: string;
  data_type: string;
  options?: string[];
  is_required: boolean;
  asked_when: AskedWhen;
  show_if: { question_key: string; answer: AnswerValue } | null;
  raise_work: { on_answer: AnswerValue; template_id: string } | null;
}

export async function addQuestion(
  id: string,
  body: QuestionBody,
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  return requireData(await client.post<ReadFormatDetail>(`${BASE}/${id}/questions`, body));
}

export async function updateQuestion(
  id: string,
  key: string,
  body: QuestionBody,
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  return requireData(
    await client.patch<ReadFormatDetail>(`${BASE}/${id}/questions/${encodeURIComponent(key)}`, body),
  );
}

export async function deleteQuestion(
  id: string,
  key: string,
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  return requireData(
    await client.del<ReadFormatDetail>(`${BASE}/${id}/questions/${encodeURIComponent(key)}`),
  );
}

export async function reorderQuestions(
  id: string,
  keys: string[],
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  return requireData(await client.post<ReadFormatDetail>(`${BASE}/${id}/questions/reorder`, { keys }));
}

export async function publishReadFormat(
  id: string,
  changeNote: string,
  client: ApiClient = api,
): Promise<ReadFormatDetail> {
  const body = changeNote.trim() === "" ? {} : { change_note: changeNote.trim() };
  return requireData(await client.post<ReadFormatDetail>(`${BASE}/${id}/publish`, body));
}

export async function newReadFormatDraft(id: string, client: ApiClient = api): Promise<ReadFormatDetail> {
  return requireData(await client.post<ReadFormatDetail>(`${BASE}/${id}/new-draft`, {}));
}

export async function retireReadFormat(id: string, client: ApiClient = api): Promise<ReadFormatDetail> {
  return requireData(await client.post<ReadFormatDetail>(`${BASE}/${id}/retire`, {}));
}

// ── Pointers: route → cycle → service ───────────────────────────────────────

export interface FormatPointer {
  id: string;
  name: string;
}

export interface ServiceDefaultRow {
  service: { code: string; name: string };
  read_format: FormatPointer | null;
}

/** One row per ENABLED service — bounded by the eleven-service catalogue. */
export async function getServiceDefaults(client: ApiClient = api): Promise<ServiceDefaultRow[]> {
  return requireData(
    await client.get<{ count: number; results: ServiceDefaultRow[] }>(`${BASE}/defaults`),
  ).results;
}

export async function setServiceDefault(
  service: string,
  readFormatId: string | null,
  client: ApiClient = api,
): Promise<ServiceDefaultRow[]> {
  return requireData(
    await client.put<{ count: number; results: ServiceDefaultRow[] }>(
      `${BASE}/defaults/${encodeURIComponent(service)}`,
      { read_format_id: readFormatId },
    ),
  ).results;
}

export async function getCycleReadFormat(
  cycleId: string,
  client: ApiClient = api,
): Promise<{ cycle_id: string; read_format: FormatPointer | null }> {
  return requireData(await client.get(`/cycles/${cycleId}/read-format`));
}

export async function setCycleReadFormat(
  cycleId: string,
  readFormatId: string | null,
  client: ApiClient = api,
): Promise<{ cycle_id: string; read_format: FormatPointer | null }> {
  return requireData(
    await client.put(`/cycles/${cycleId}/read-format`, { read_format_id: readFormatId }),
  );
}

export async function setRoutesReadFormat(
  routeIds: string[],
  readFormatId: string | null,
  client: ApiClient = api,
): Promise<{ route_ids: string[]; read_format: FormatPointer | null; updated: number }> {
  return requireData(
    await client.put("/routes/read-format", { route_ids: routeIds, read_format_id: readFormatId }),
  );
}

/** Where a route's format comes from — `null` is the plain reading. */
export type FormatSource = "route" | "cycle" | "service" | null;

export interface RouteResolution {
  route_id: string;
  route_read_format_id: string | null;
  results: {
    service: string;
    source: FormatSource;
    read_format: { id: string; name: string; version_id: string; version_no: number | null } | null;
  }[];
}

export async function getRouteReadFormat(
  routeId: string,
  client: ApiClient = api,
): Promise<RouteResolution> {
  return requireData(await client.get<RouteResolution>(`/routes/${routeId}/read-format`));
}

// ── Query keys ──────────────────────────────────────────────────────────────

export const readFormatKeys = {
  all: ["read-formats"] as const,
  list: (query: ReadFormatListQuery) => ["read-formats", "list", query] as const,
  detail: (id: string) => ["read-formats", "detail", id] as const,
  versions: (id: string, page: number, per: number) =>
    ["read-formats", "versions", id, page, per] as const,
  defaults: ["read-formats", "defaults"] as const,
  published: (service: string | null) => ["read-formats", "published", service ?? "*"] as const,
  cycle: (cycleId: string) => ["read-formats", "cycle", cycleId] as const,
  route: (routeId: string) => ["read-formats", "route", routeId] as const,
};
