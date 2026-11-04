// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane PERFORMANCE — the reads and the one
//           write behind the three boards P5 names and does not draw: the
//           at-risk board (P5.3), the schedule board (P5.4) and the raise
//           across buildings (P5.5).
// Contract: CR-168 §20.2 — `GET /work/at-risk?page=&per=`, `GET
//           /work/settings/sla`; P5.11 — *"The three new screens read existing
//           endpoints"*: `GET /work/candidates?on=` (a day's load),
//           `GET /work-orders?technician=` (the queue), `POST /work-orders/bulk`
//           (the drop), `GET /assets` + `POST /work-orders/bulk-raise` (the
//           raise across buildings).
// Shapes:   every type below is checked by `tsc` against a RECORDING in
//           `../__fixtures__/server/` (`../recordedServerShapes.typecheck.ts`).
// ───────────────────────────────────────────────────────
//
// ⚠ **A FILE OF ITS OWN, NOT ROWS IN `workEndpoints.ts`.** Lane RULES writes
// Work's shared files in the same round, and a pathspec commit takes the whole
// file (hard-won law 11) — the same reason `raise/raiseEndpoints.ts` exists.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/paginated";

import type { WorkOrderDispatchRow } from "../workEndpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** What a job was promised, held time already added back (P5.2). `target` is
 *  `priority` when the job carries its own date, `default` when it is measured
 *  against the utility's default target (PO answer (1), 2026-10-04). */
export interface JobPromise {
  due_at: string;
  target: string;
  overdue: boolean;
  /** Whole minutes to the promise; NEGATIVE once it has passed. */
  minutes_left: number;
}

/** One row of `GET /work/at-risk` — the dispatcher's own row plus its promise. */
export interface AtRiskRow extends WorkOrderDispatchRow {
  promise: JobPromise;
}

export interface AtRiskPage extends Paginated<AtRiskRow> {
  /** The tenant's warning window in hours; `null` = only what has passed. */
  window_hours: number | null;
}

export async function fetchAtRisk(
  query: { page?: number; per?: number },
  client: ApiClient = api,
): Promise<AtRiskPage> {
  return requireData(
    await client.get<AtRiskPage>("/work/at-risk", { query: { page: query.page, per: query.per } }),
  );
}

/** `GET /work/settings/sla` — the default target an undated job is measured
 *  against (seeded Normal, 72 h) and the at-risk warning window. */
export interface SlaSettings {
  priority: { id: string; code: string; name: string } | null;
  hours: number | null;
  /** False while the seeded default stands — nobody has chosen one yet. */
  chosen: boolean;
  at_risk_window_hours: number | null;
}

export async function fetchSlaSettings(client: ApiClient = api): Promise<SlaSettings> {
  return requireData(await client.get<SlaSettings>("/work/settings/sla"));
}

/** Whole minutes as the board says them — `2 d 3 h`, `5 h 20 m`, `40 m`.
 *  Absolute: the caller says whether it is *left* or *late*. */
export function spanParts(minutes: number): { d: number; h: number; m: number } {
  const total = Math.abs(Math.trunc(minutes));
  return { d: Math.floor(total / 1440), h: Math.floor((total % 1440) / 60), m: total % 60 };
}
