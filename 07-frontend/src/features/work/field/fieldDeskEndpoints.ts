// ── Trace ──────────────────────────────────────────────
// Stories:  US-WRK-055 · US-WRK-056 · US-WRK-057 · US-WRK-058 · US-WRK-059
//           (EP-WRK-11 — the office side of the native field app,
//           CR-187-BRC10, Walkthrough §4 / `18-field-app/07-endpoints.md` §7)
// Server:   06-backend/apps/work/field_orders_api.py (acceptance queue,
//           outcome, come-back(s), field-raised queue and decision) ·
//           06-backend/apps/work/field_api.py (field alerts) ·
//           06-backend/apps/work/api.py (`technician_devices`,
//           `technician_device_sign_out`)
// Rules:    NFR-3 (every list is server-paged; no cap is written here) ·
//           B14 rule 31 (ids travel, they are never shown) · hard rule 2
//           (money is a decimal STRING, never a number)
// ───────────────────────────────────────────────────────
//
// ⚠ **IN ITS OWN FILE, NOT APPENDED TO `../workEndpoints.ts`.** That file is
// 3,000+ lines several lanes edit in the same week; a pathspec commit takes
// the whole file (hard-won law 11, mechanism two). Everything the five office
// surfaces read or write is here and nowhere else.
//
// ⚠ **EVERY SHAPE BELOW WAS TYPED FROM THE SERVER FUNCTION THAT BUILDS THE
// REPLY, NOT FROM THE SELECTOR'S DICT.** `_envelope` renames `rows` → `results`
// and `total` → `count` and DISCARDS every other key, so the three lists that
// carry extras (`tally`, `counts`) are read through `readListPageWith`, which
// hands back the same body the rows came out of (`DEF-WRK-4119`'s lesson).
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { readListPage, readListPageWith } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";

import { WORK_ORDERS_ROUTE } from "../WorkShell";

/** The order page's address, tenant-relative — `Work-008` at
 *  `/work/orders/{id}`. Built from `WorkShell`'s constant rather than imported
 *  from `OrderDetailPage`, because that page mounts `OrderFieldPanels` and an
 *  import cycle in ES modules hands the other side `undefined` (WorkShell's
 *  own note, `DEF-WRK-3955`). The id is in the ADDRESS, never on the page. */
export function orderAddress(orderId: string): string {
  return `${WORK_ORDERS_ROUTE}/${orderId}`;
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** An idempotency key minted when a dialog OPENS, so a retried press is the
 *  same act (`07-endpoints.md` §0 rule 7). Never shown. */
export function newActKey(): string {
  const cryptoApi = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
  return `act-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

// ══════════════════════════════════════════════════════════════════════════
// The outcome record — `field_outcomes.outcome_record`
// ══════════════════════════════════════════════════════════════════════════

/** BR-FLD-00004's four words — the server's `R4_WORDS` KEYS, which are also
 *  what `?outcome=` accepts. The stored tokens are metering's and never reach
 *  a label here. */
export const FIELD_OUTCOME_WORDS = [
  "passed",
  "partly_done",
  "failed",
  "waiting_on_someone",
  // FB-013 (PO ruling (b) 2026-10-28) — the fifth: *Not done — payment received*.
  "not_done_paid",
] as const;
export type FieldOutcomeWord = (typeof FIELD_OUTCOME_WORDS)[number];

/** R4: *"blocked by a person, a part or access"*. Anything else the handset
 *  sent is served AS SENT with `blocker_known: false` and drawn as sent. */
export const FIELD_BLOCKERS = ["person", "part", "access"] as const;

export interface FieldCost {
  /** `true` once Accept has frozen the report; before that a PREVIEW from the
   *  same costing function the report will use (`BR-WRK-051`). */
  frozen: boolean;
  report_version: number | null;
  /** Two decimals, a string (hard rule 2). Posted nowhere (`OQ-WRK-1491`). */
  total: string;
}

export interface FieldOutcomeRecord {
  outcome: string | null;
  word: FieldOutcomeWord | null;
  kind: "done" | "partial" | "failure" | "blocked" | "paid" | null;
  is_failure: boolean;
  reason: string | null;
  reason_missing: boolean;
  blocker: string | null;
  blocker_known: boolean | null;
  steps_done: number;
  steps_total: number;
  remaining_steps: { seq: number; title: string; is_mandatory: boolean }[];
  photographs: number;
  completed_at: string | null;
  accepted_at: string | null;
  /** FB-013 — the technician's own Arrived and Finished, or null. */
  times?: { arrived_at: string | null; finished_at: string | null } | null;
  /** FB-013 — a paid close's money: what the phone SAW and what the server
   *  READ at the close. Amounts are decimal STRINGS (hard rule 2). */
  payment_received?: PaymentReceived | null;
}

/** A figure as the server's money read sends it: 4 places stored, 2 shown. */
export interface MoneyFigure {
  amount: string;
  display: string;
  currency: string | null;
}

export interface PaymentReceived {
  phone: {
    balance: string;
    currency: string | null;
    as_at: string;
    checked_at: string | null;
    latest_payment: { amount: string | null; at: string | null } | null;
  };
  server: {
    as_at: string;
    owing: MoneyFigure | null;
    balance: MoneyFigure | null;
    currency: string | null;
    latest_payment: (MoneyFigure & { posted_at?: string | null; cleared_at?: string | null }) | null;
    unavailable: string[];
  };
  fresh_minutes: number;
  task_title: string | null;
}

export interface PremiseRef {
  id: string;
  premise_no: string | null;
  address: string | null;
}

// ══════════════════════════════════════════════════════════════════════════
// US-WRK-055 · the acceptance queue — `GET work/acceptance-queue`
// ══════════════════════════════════════════════════════════════════════════

export interface AcceptanceRow extends FieldOutcomeRecord {
  id: string;
  order_no: string | null;
  type: string | null;
  premise: PremiseRef | null;
  technician: string | null;
  raised_in_field: boolean;
  waiting_days: number | null;
  cost: FieldCost;
}

/** Counted over the WHOLE queue (accepted=false), never the page. */
export type AcceptanceTally = Record<FieldOutcomeWord | "none", number>;

export async function listAcceptanceQueue(
  query: { outcome?: string; page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<AcceptanceRow> & { body: { tally?: AcceptanceTally } }> {
  return readListPageWith<AcceptanceRow, { tally?: AcceptanceTally }>(
    "/work/acceptance-queue",
    {
      outcome: query.outcome === undefined || query.outcome === "" ? undefined : query.outcome,
      accepted: "false",
      page: query.page,
      per: query.per,
    },
    client,
  );
}

export interface OrderOutcome extends FieldOutcomeRecord {
  id: string;
  order_no: string | null;
  cost: FieldCost;
}

/** `GET /work-orders/{id}/outcome` — one job's outcome and its cost. */
export async function getOrderOutcome(orderId: string, client: ApiClient = api): Promise<OrderOutcome> {
  return requireData(await client.get<OrderOutcome>(`/work-orders/${orderId}/outcome`));
}

// ══════════════════════════════════════════════════════════════════════════
// US-WRK-055 / 059 · reopen and follow-on — `field_reopen`
// ══════════════════════════════════════════════════════════════════════════

export type ComeBackDecision = "reopen" | "follow_on";

export interface ComeBackBody {
  decision: ComeBackDecision;
  reason: string;
  note?: string;
  template_id?: string;
  key?: string;
}

export interface ComeBackAnswer {
  id: string;
  order_id: string;
  order_no: string | null;
  kind: "technician_reopen" | "office_reopen" | "follow_on";
  reason: string;
  follow_on: { id: string; order_no: string | null } | null;
  duplicate: boolean;
}

/** `POST /work-orders/{id}/come-back` — the office decides which (E2E-17/18). */
export async function postComeBack(
  orderId: string,
  body: ComeBackBody,
  client: ApiClient = api,
): Promise<ComeBackAnswer> {
  return requireData(await client.post<ComeBackAnswer>(`/work-orders/${orderId}/come-back`, body));
}

export interface ComeBackEvent {
  id: string;
  kind: "technician_reopen" | "office_reopen" | "follow_on";
  /** A technician's reason is one of FF-36's three tokens; the office's is
   *  free text and is shown as written. */
  reason: string;
  note: string | null;
  at: string;
  by: string | null;
  follow_on: { id: string; order_no: string | null } | null;
}

export interface ComeBackHistory {
  order_id: string;
  order_no: string | null;
  followed_on_from: { id: string; order_no: string | null } | null;
  events: ComeBackEvent[];
}

/** `GET /work-orders/{id}/come-backs` — every reopen and follow-on, oldest first. */
export async function getComeBacks(orderId: string, client: ApiClient = api): Promise<ComeBackHistory> {
  return requireData(await client.get<ComeBackHistory>(`/work-orders/${orderId}/come-backs`));
}

// ══════════════════════════════════════════════════════════════════════════
// US-WRK-056 · orders raised on site — `field_raise`
// ══════════════════════════════════════════════════════════════════════════

export const FIELD_RAISE_STATUSES = ["pending", "accepted", "refused"] as const;
export type FieldRaiseStatus = (typeof FIELD_RAISE_STATUSES)[number];

export interface FieldRaisedRow {
  order_id: string;
  order_no: string | null;
  status: FieldRaiseStatus;
  dispatch_state: string | null;
  assigned: boolean;
  /** FB-028 — who holds the order now (the raiser at first). A name. */
  assigned_to?: { id: string; name: string | null } | null;
  template: {
    id: string;
    name: string;
    version_stamped: number | null;
    version_picked: number | null;
    version_moved: boolean;
  } | null;
  carried_from: { id: string; order_no: string | null } | null;
  premise: PremiseRef | null;
  account: { id: string; account_no: string | null } | null;
  customer: { name: string | null; customer_no: string | null } | null;
  position: { lat: string; lng: string; accuracy_m: string } | null;
  need: string | null;
  urgency: string | null;
  is_reconnect: boolean;
  note: string | null;
  captured_at: string | null;
  raised_by: string | null;
  raised_at: string;
  photographs: number;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
}

export type FieldRaiseCounts = Record<FieldRaiseStatus, number>;

/** `GET /work/field-raised?status=` — `status` absent reads `all` here, because
 *  the server's own default is `pending` and a cleared filter must mean
 *  *every status*, never silently the default. */
export async function listFieldRaised(
  query: { status?: string; page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<FieldRaisedRow> & { body: { counts?: FieldRaiseCounts } }> {
  return readListPageWith<FieldRaisedRow, { counts?: FieldRaiseCounts }>(
    "/work/field-raised",
    {
      status: query.status === undefined || query.status === "" ? "all" : query.status,
      page: query.page,
      per: query.per,
    },
    client,
  );
}

/** `POST /work-orders/{id}/field-raise` — `{decision: accept | refuse, reason?}`. */
export async function decideFieldRaise(
  orderId: string,
  body: { decision: "accept" | "refuse"; reason?: string },
  client: ApiClient = api,
): Promise<FieldRaisedRow> {
  return requireData(await client.post<FieldRaisedRow>(`/work-orders/${orderId}/field-raise`, body));
}

// ══════════════════════════════════════════════════════════════════════════
// US-WRK-057 · field alerts — `field_alerts`
// ══════════════════════════════════════════════════════════════════════════

/** The server's `alert_models.ALERT_KINDS`, in its order. */
export const FIELD_ALERT_KINDS = [
  "urgent_assignment",
  "emergency",
  "schedule_change",
  "dispatch_message",
] as const;
export type FieldAlertKind = (typeof FIELD_ALERT_KINDS)[number];

/** `?state=` — `all` is what an absent filter sends. */
export const FIELD_ALERT_STATES = ["awaiting_ack", "overdue"] as const;

export interface FieldAlertRow {
  id: string;
  kind: FieldAlertKind;
  work_order_id: string | null;
  order_no: string | null;
  premise: PremiseRef | null;
  technician: string | null;
  message: string | null;
  sent_at: string;
  ack_required: boolean;
  ack_due_at: string | null;
  acknowledged_at: string | null;
  late: boolean;
  dispatch_told: boolean;
  escalated_at: string | null;
}

export async function listFieldAlerts(
  query: { state?: string; page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<FieldAlertRow>> {
  return readListPage<FieldAlertRow>(
    "/work/field-alerts",
    {
      state: query.state === undefined || query.state === "" ? "all" : query.state,
      page: query.page,
      per: query.per,
    },
    client,
  );
}

export interface SendAlertBody {
  kind: FieldAlertKind;
  work_order_id: string;
  message?: string;
  key: string;
}

/** `POST /work/field-alerts` — to the order's own technician (the server's
 *  default); a job held by a crew and nobody is refused by name there. */
export async function sendFieldAlert(body: SendAlertBody, client: ApiClient = api): Promise<FieldAlertRow> {
  return requireData(await client.post<FieldAlertRow>("/work/field-alerts", body));
}

// ══════════════════════════════════════════════════════════════════════════
// US-WRK-058 · a technician's handsets — `mobile.devices_page`
// ══════════════════════════════════════════════════════════════════════════

export interface TechnicianDeviceRow {
  /** The registration's row id — for the sign-out ADDRESS only (rule 31). */
  device_id: string;
  /** The handset's own identifier. Never shown (rule 31). */
  device_uid: string | null;
  name: string | null;
  platform: string | null;
  active: boolean;
  signed_out: boolean;
  signed_out_at: string | null;
  push_registered: boolean;
  last_four: string | null;
  registered_at: string | null;
  last_seen_at: string | null;
}

export async function listTechnicianDevices(
  slug: string,
  query: { page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<TechnicianDeviceRow>> {
  return readListPage<TechnicianDeviceRow>(
    `/work/technicians/${encodeURIComponent(slug)}/devices`,
    { page: query.page, per: query.per },
    client,
  );
}

/** `POST /work/technicians/{slug}/devices/{device_id}/sign-out` — signs the
 *  HANDSET out, for everybody on it; nothing captured is thrown away (R113). */
export async function signOutTechnicianDevice(
  slug: string,
  deviceId: string,
  client: ApiClient = api,
): Promise<TechnicianDeviceRow> {
  return requireData(
    await client.post<TechnicianDeviceRow>(
      `/work/technicians/${encodeURIComponent(slug)}/devices/${deviceId}/sign-out`,
      {},
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// BR-WRK-067 · route findings — `apps/work/route_findings.py`
// ══════════════════════════════════════════════════════════════════════════

/** The server's `route_finding_models.FINDING_KINDS`, in RW-21's order. */
export const ROUTE_FINDING_KINDS = [
  "leak",
  "damaged_meter",
  "broken_seal",
  "suspected_tamper",
  "unsafe_access",
  "something_else",
  "meter_mismatch",
] as const;
export type RouteFindingKind = (typeof ROUTE_FINDING_KINDS)[number];

/** `FINDING_STATUSES` — open until a job exists, then `work_order_created`. */
export const ROUTE_FINDING_STATUSES = ["open", "work_order_created"] as const;
export type RouteFindingStatus = (typeof ROUTE_FINDING_STATUSES)[number];

/** One finding as `route_findings.answer` builds it. `id` is an ADDRESS for
 *  the convert call and is never drawn (rule 31). `capture_point` is where the
 *  PHONE was — never the property's place (BR-MET-1202). */
export interface RouteFindingRow {
  id: string;
  key: string;
  kind: RouteFindingKind;
  urgency: "now" | "this_week" | "routine" | null;
  note: string | null;
  status: RouteFindingStatus;
  conversion: "by_rule" | "by_hand" | null;
  rule: string | null;
  work_order: { id: string; order_no: string | null } | null;
  meter_no: string | null;
  stop: { premise_no: string | null; address: string | null } | null;
  route: string | null;
  technician: string | null;
  photographs: number;
  capture_point: { lat: string; lng: string; accuracy_m: string | null } | null;
  captured_at: string | null;
  received_at: string | null;
  converted_by: string | null;
  converted_at: string | null;
}

export type RouteFindingCounts = Record<RouteFindingStatus, number>;

/** `GET /work/route-findings?status=` — a cleared filter sends `all`, because
 *  the server's own default is `open` (the same posture as the raised pane). */
export async function listRouteFindings(
  query: { status?: string; page: number; per: number },
  client: ApiClient = api,
): Promise<PagedRows<RouteFindingRow> & { body: { counts?: RouteFindingCounts } }> {
  return readListPageWith<RouteFindingRow, { counts?: RouteFindingCounts }>(
    "/work/route-findings",
    {
      status: query.status === undefined || query.status === "" ? "all" : query.status,
      page: query.page,
      per: query.per,
    },
    client,
  );
}

/** `POST /work/route-findings/{id}/work-order` — `{template_id, priority_id?}`.
 *  Once per finding: a second press answers the job it has, `duplicate`. */
export async function createFindingWorkOrder(
  findingId: string,
  body: { template_id: string; priority_id?: string },
  client: ApiClient = api,
): Promise<RouteFindingRow & { duplicate: boolean }> {
  return requireData(
    await client.post<RouteFindingRow & { duplicate: boolean }>(`/work/route-findings/${findingId}/work-order`, body),
  );
}
