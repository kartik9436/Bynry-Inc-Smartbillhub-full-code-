// ── Trace ──────────────────────────────────────────────
// Change:  CR-157-BRC10 wave B — the reads behind the rebuilt rate-schedule
//          screens: the List's Customer class / Base code / Sizes columns, the
//          Rates tab's Base charges table and the Plans tab.
// Server:  06-backend/apps/rating/schedule_reads.py · api.rate_schedule_rates ·
//          api.rate_schedule_plans
// ───────────────────────────────────────────────────────
/**
 * A file of its own so it adds no hunk to `endpoints.ts`, which several lanes
 * edit at once (the reason `bankRecEndpoints.ts` gives for the same shape).
 */
import type { ApiClient, ApiResponse } from "./client";
import { api } from "./client";
import type { ScheduleCard } from "./endpoints";
import type { Paginated } from "./paginated";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** The four list columns the drawing adds (`01-list-all.png`). Served by
 *  `schedule_reads.card_extras` on every card of `GET /rate-schedules`. */
export interface ScheduleCardExtras {
  /** `null` = every class — the screen says *Every class*. Never an id. */
  customer_class_name?: string | null;
  base_code?: string | null;
  /** DEF-RAT-9797 — live, names no base code, and its service has one. */
  base_code_to_choose?: boolean;
  /** *Sizes priced* — `priced of total`; `0 of 0` reads *One amount*. */
  sizes_priced?: number;
  sizes_total?: number;
}

export type ScheduleListRow = ScheduleCard & ScheduleCardExtras;

/** One row of the Rates tab's *Base charges* table. */
export interface ScheduleBaseRow {
  seq: number;
  /** `null` = the one *All sizes* row. */
  size_class: string | null;
  size_name: string | null;
  priced: boolean;
  amount: string | null;
  amount_display: string | null;
  version: number | null;
  effective_from: string | null;
  effective_to: string | null;
  /** DEF-RAT-8737 — the STORED minimum, shown as it is; nothing decided. */
  minimum: string | null;
  minimum_display: string | null;
  units: number;
  /** DEF-RAT-8833 — the base code and class this row is read for. */
  code?: string;
  /** `null` = every class. */
  customer_class?: string | null;
  /** DEF-RAT-8846 — a price scheduled after today, if any. */
  next_amount?: string | null;
  next_amount_display?: string | null;
  next_effective_from?: string | null;
}

/** DEF-RAT-8846 — the earliest scheduled base price on the schedule. */
export interface ScheduleBaseNextChange {
  code: string;
  customer_class: string | null;
  size_name: string | null;
  amount: string;
  amount_display: string;
  effective_from: string;
}

export interface ScheduleRates {
  base_code: { id: string; code: string; name: string } | null;
  sizes_priced: number;
  sizes_total: number;
  units_total: number;
  base_rows: ScheduleBaseRow[];
  /** DEF-RAT-8833 — every base code the tab shows (one per class when the schedule names none). */
  base_codes?: { id: string; code: string; name: string; customer_class: string | null }[];
  base_next_change?: ScheduleBaseNextChange | null;
}

export async function getScheduleRates(
  tariffId: string,
  client: ApiClient = api,
): Promise<ScheduleRates> {
  return requireData(
    await client.get<ScheduleRates>(`/rate-schedules/${encodeURIComponent(tariffId)}/rates`),
  );
}

/** One row of the Plans tab (`10-view-W-RES-plans.png`). */
export interface SchedulePlanRow {
  plan_id: string;
  plan_name: string;
  plan_code: string;
  /** `[]` = every class. Names, never ids. */
  customer_classes: string[];
  class_differs: boolean;
  status: string;
  units: number;
}

/** Paged FROM THE SERVER (`NFR-3`); `count` is the whole set. */
export async function getSchedulePlans(
  tariffId: string,
  params: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<Paginated<SchedulePlanRow>> {
  const query: Record<string, string> = {};
  if (params.page !== undefined) query.page = String(params.page);
  if (params.per !== undefined) query.per = String(params.per);
  return requireData(
    await client.get<Paginated<SchedulePlanRow>>(
      `/rate-schedules/${encodeURIComponent(tariffId)}/plans`,
      { query },
    ),
  );
}

/** *Sizes priced* as words — `5 of 5`, or `One amount` when the base is not
 *  priced by size. The list draws `—` for the second (`01-list-all.png`); the
 *  tile and the wizard's aside draw *One amount* (`13-view-SEWER-rates.png`). */
export function sizesPricedText(
  t: (key: string, params?: Record<string, unknown>) => string,
  priced: number | undefined,
  total: number | undefined,
): string | null {
  if (total === undefined || priced === undefined || total === 0) {
    return null;
  }
  return t("rating.rs.sizesOf", { priced, total });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-004@0b56fac (CR-157-BRC10 wave B)
// generated: 2026-10-01 by the CR-157-BRC10 wave B lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest RateScheduleDetail / RateSchedulesTable✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
