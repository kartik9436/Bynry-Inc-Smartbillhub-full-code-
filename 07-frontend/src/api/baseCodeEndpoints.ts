// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-9797 (a rate schedule names exactly one base code — the
//           live schedules naming none are listed for a System Admin) ·
//           DEF-RAT-9799 (the step-1 clash warning — retired by DEF-RAT-10026)
// Rulings:  PO 2026-10-06, decision log "PO RULINGS — BASE CHARGES…"
// ───────────────────────────────────────────────────────
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// `getBaseCodeClash` (`GET /charges/base-clash`, DEF-RAT-9799) stood here and
// is RETIRED with its route — DEF-RAT-10026, PO 2026-10-09: a service may hold
// two or more base codes for one customer class.

export interface ScheduleToNameABase {
  id: string;
  name: string;
  service: string;
}

/** `GET /rate-schedules/base-to-choose` — live schedules naming no base code. */
export async function getSchedulesBaseToChoose(
  client: ApiClient = api,
): Promise<{ count: number; results: ScheduleToNameABase[] }> {
  return requireData(
    await client.get<{ count: number; results: ScheduleToNameABase[] }>("/rate-schedules/base-to-choose"),
  );
}
