// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 — temporary stop (PO rulings B1–B4, 2026-10-14).
// Rules:    BR-CUS-1120 · BR-CUS-1121 · B14 rule 31 (numbers on screen, ids
//           only for the controls)
// Server:   06-backend/apps/customers/temporary_stop_api.py
// ───────────────────────────────────────────────────────
// The four staff doors onto a temporary stop, and the shapes they answer.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

import type { ServiceRequestDetail } from "./serviceRequestEndpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export type TemporaryStopStatus =
  | "requested"
  | "scheduled"
  | "on_hold"
  | "ended"
  | "refused"
  | "cancelled";

/** One hold, as the server serves it (`temporary_stop.view`). */
export interface TemporaryStopView {
  id: string;
  account_id: string;
  account_no: string;
  status: TemporaryStopStatus;
  channel: "customer_portal" | "staff";
  stop_from: string;
  restart_on: string | null;
  days: number | null;
  reason: string | null;
  field_visit_needed: boolean;
  shutoff_order_no: string | null;
  turnon_order_no: string | null;
  ended_early: boolean;
  /** B1 — always `base_only`; the catalogue writes the words. */
  billed_during_hold: "base_only";
  request_no: string | null;
  request_id: string | null;
  restart_request_no: string | null;
  restart_request_id: string | null;
  restart_request_state: string | null;
}

export interface TemporaryStopLimits {
  min_days: number;
  max_months: number;
}

/** A reason the dates cannot be approved — the server's list (B3). */
export interface TemporaryStopProblem {
  code: string;
  message_key: string;
  params: Record<string, unknown>;
}

/** `detail.temporary_stop` — present only on a temporary-stop or restart ask. */
export interface TemporaryStopForRequest {
  kind: "temporary_stop" | "restart_now";
  stop: TemporaryStopView;
  limits: TemporaryStopLimits;
  problems: TemporaryStopProblem[];
  /** `restart_now` only — the day billing returns to normal (today). */
  restart_from?: string;
}

export interface TemporaryStopWarning {
  code: string;
  message_key: string;
}

export interface AccountTemporaryStop {
  current: TemporaryStopView | null;
  limits: TemporaryStopLimits;
  billed_during_hold: "base_only";
  warnings?: TemporaryStopWarning[];
}

export async function approveTemporaryStop(
  requestId: string,
  body: { stop_from?: string; restart_on?: string; field_visit_needed: boolean },
  client: ApiClient = api,
): Promise<ServiceRequestDetail & { temporary_stop_result: { warnings: TemporaryStopWarning[] } }> {
  return requireData(
    await client.post<
      ServiceRequestDetail & { temporary_stop_result: { warnings: TemporaryStopWarning[] } }
    >(`/service-requests/${encodeURIComponent(requestId)}/temporary-stop/approve`, body),
  );
}

export async function getAccountTemporaryStop(
  accountId: string,
  client: ApiClient = api,
): Promise<AccountTemporaryStop> {
  return requireData(
    await client.get<AccountTemporaryStop>(
      `/accounts/${encodeURIComponent(accountId)}/temporary-stop`,
    ),
  );
}

export async function startTemporaryStop(
  accountId: string,
  body: { stop_from: string; restart_on: string; reason?: string; field_visit_needed: boolean },
  client: ApiClient = api,
): Promise<AccountTemporaryStop> {
  return requireData(
    await client.post<AccountTemporaryStop>(
      `/accounts/${encodeURIComponent(accountId)}/temporary-stop`,
      body,
    ),
  );
}

export async function changeTemporaryStop(
  stopId: string,
  body: { stop_from?: string; restart_on?: string },
  client: ApiClient = api,
): Promise<{ stop: TemporaryStopView }> {
  return requireData(
    await client.patch<{ stop: TemporaryStopView }>(
      `/temporary-stops/${encodeURIComponent(stopId)}`,
      body,
    ),
  );
}

export async function endTemporaryStop(
  stopId: string,
  client: ApiClient = api,
): Promise<{ stop: TemporaryStopView }> {
  return requireData(
    await client.post<{ stop: TemporaryStopView }>(
      `/temporary-stops/${encodeURIComponent(stopId)}/end`,
      {},
    ),
  );
}
