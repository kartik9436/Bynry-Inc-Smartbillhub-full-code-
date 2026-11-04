// ── Trace ──────────────────────────────────────────────
// Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26): a
//           technician's working days, one-day exceptions and submitted
//           timesheet days, on the technician's page.
// Server:   apps/work/shifts_api.py — read from its code, not from a guess:
//             GET|PUT      /work/technicians/{slug}/working-days
//             GET|POST     /work/technicians/{slug}/exceptions   (paged)
//             PATCH|DELETE /work/technicians/{slug}/exceptions/{id}
//             GET          /work/technicians/{slug}/timesheets   (paged)
// Rules:    NFR-3 (every list paged by the server) · hard rule 1 (a slug of
//           another utility is a 404) · B14 rule 31 (the ids below are for the
//           wire and are never drawn)
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { readListPage } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";

/** Monday first — the order the server's `WEEKDAY_CODES` holds. */
export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Weekday = (typeof WEEKDAYS)[number];

export interface WorkingDays {
  weekdays: Weekday[];
  /** No row yet: Monday to Friday by default. */
  is_default: boolean;
  shift_start: string | null;
  shift_end: string | null;
}

export type ExceptionKind = "off" | "window";

export interface DayException {
  id: string;
  date: string;
  kind: ExceptionKind;
  start: string | null;
  end: string | null;
  note: string | null;
}

export interface ExceptionInput {
  date: string;
  kind: ExceptionKind;
  start?: string;
  end?: string;
  note?: string;
}

export interface SubmittedDay {
  date: string;
  jobs: number;
  labour_minutes: number;
  travel_minutes: number;
  lines: { order_id: string; order_no: string | null; labour_minutes: number; travel_minutes: number }[];
  submitted_at: string;
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) throw new Error(`empty ${response.status} body where the contract promises one`);
  return response.data;
}

const base = (slug: string) => `/work/technicians/${encodeURIComponent(slug)}`;

export async function getWorkingDays(slug: string, client: ApiClient = api): Promise<WorkingDays> {
  return requireData(await client.get<WorkingDays>(`${base(slug)}/working-days`));
}

export async function setWorkingDays(slug: string, weekdays: Weekday[], client: ApiClient = api): Promise<WorkingDays> {
  return requireData(await client.put<WorkingDays>(`${base(slug)}/working-days`, { weekdays }));
}

export async function listExceptions(
  slug: string,
  query: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<DayException>> {
  return readListPage<DayException>(`${base(slug)}/exceptions`, query, client);
}

export async function addException(slug: string, body: ExceptionInput, client: ApiClient = api): Promise<DayException> {
  return requireData(await client.post<DayException>(`${base(slug)}/exceptions`, body));
}

export async function editException(
  slug: string,
  id: string,
  body: ExceptionInput,
  client: ApiClient = api,
): Promise<DayException> {
  return requireData(await client.patch<DayException>(`${base(slug)}/exceptions/${id}`, body));
}

export async function removeException(slug: string, id: string, client: ApiClient = api): Promise<void> {
  await client.del<unknown>(`${base(slug)}/exceptions/${id}`);
}

export async function listTimesheets(
  slug: string,
  query: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<SubmittedDay>> {
  return readListPage<SubmittedDay>(`${base(slug)}/timesheets`, query, client);
}
