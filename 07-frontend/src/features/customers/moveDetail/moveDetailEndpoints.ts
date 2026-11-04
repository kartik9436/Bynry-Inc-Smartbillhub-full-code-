// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.04–P2.13 — the move-in details view's reads and
//           doors, typed as the server lanes wrote them into the CR's §9
//           (§9.LIST `GET /moves/{ref}`, §9.REQ the request doors, §9.FLOW the
//           committed move's doors and step 1's unit reads).
// Rules:    B14 rule 31 (ids ride in addresses; numbers are what a clerk reads)
//           · CLAUDE.md hard rule 2 (money arrives as a decimal STRING and is
//           displayed through MoneyCell, never re-rounded here)
// Screens:  S19.moveRecord (`/moves/:ref`) for a move-in, images 03–29
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/paginated";

import type { MoveAbsence, MoveRecordDetail } from "../MoveRecordPage";
import type { MoveInStatus } from "../moveRecordActions";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

const enc = encodeURIComponent;

// ══════════════════════════════════════════════════════════════════════════
// `GET /moves/{ref}` — the keys §9.LIST adds on a move-in (every status)
// ══════════════════════════════════════════════════════════════════════════
export interface MoveRef {
  id: string;
  label: string | null;
  /** `DEF-CUS-9763` — the tenant's unit number, drawn before the label. */
  unit_no?: string | null;
  line: string | null;
}
export interface MoveBuilding {
  id: string | null;
  premise_no: string | null;
  address: string | null;
}
export interface MovePlanRef {
  name: string | null;
  code: string | null;
  version: number | null;
  since: string | null;
}
export interface MoveServiceRef {
  code: string | null;
  name?: string | null;
  available?: boolean | null;
}
export interface MoveFactCell<T> {
  value: T | null;
  unavailable: MoveAbsence | null;
}

export interface RequestTiles {
  move_in_date: { value: string | null; basis: string };
  services: { count: number; codes: (string | null)[] };
  documents: {
    attached: number;
    outstanding: { key?: string; state?: string; params?: { verified?: number; total?: number } } | null;
  };
  unit: { vacant: boolean | null; unit_label: string | null; unit_no?: string | null };
}

export interface MoveTiles {
  opening_reads: {
    taken: number | null;
    of: number | null;
    recorded_on: string | null;
    unavailable: MoveAbsence | null;
  };
  fees: {
    total: string | null;
    currency: string | null;
    lines: number;
    paid: string | null;
    unavailable: MoveAbsence | null;
  };
  work_orders: { raised: number | null; open: number | null; unavailable: MoveAbsence | null };
  messages: { count: number | null; unavailable: MoveAbsence | null };
}

export interface RequestFacts {
  request: {
    request_no: string;
    channel: string | null;
    submitted_on: string | null;
    move_in_date: string | null;
    unit: MoveRef | null;
    building: MoveBuilding | null;
    unit_is_vacant: boolean | null;
    services: MoveServiceRef[];
    plan: MovePlanRef | null;
    customer_type: {
      account_type: string | null;
      account_type_name: string | null;
      account_subtype: string | null;
    };
  };
  who: {
    kind: "person" | "company";
    name: string | null;
    matched: { id: string; customer_no: string | null; name: string | null } | null;
    matched_absence: { code: string } | null;
    email: string | null;
    phone: string | null;
    mailing_same: boolean;
    mailing: { line1: string | null; city: string | null; state: string | null; postal_code: string | null } | null;
  };
}

export interface MoveDetailsFacts {
  details: {
    move_no: string | null;
    from_request: { id: string; request_no: string } | null;
    moved_in_on: string | null;
    customer: { id: string | null; customer_no: string | null; name: string | null } | null;
    account: { id: string; account_no: string } | null;
    plan: MovePlanRef | null;
    unit: MoveRef | null;
    building: MoveBuilding | null;
    services: MoveServiceRef[] | null;
    from_account: MoveFactCell<string> | null;
    earliest_legal_start: MoveFactCell<string> | null;
    committed_by: MoveFactCell<{ name: string | null; at: string | null }> | null;
  };
}

/** `move_in_reopen.serialize` — a move-in that REOPENED the returning
 *  customer's own account (CR-181-BRC10), and the clerk's balance choice. */
export interface MoveInReopened {
  account_id: string;
  account_no: string;
  previous_opened_at: string | null;
  previous_closed_at: string;
  balance_choice: "pay_first" | "carry" | null;
  /** The ledger's figure at Complete — a decimal STRING, `null` = unreadable. */
  balance_at_complete: string | null;
  currency: string | null;
}

export type StillOpenRow =
  | {
      kind: "work_order";
      order: { order_no: string; done?: boolean; accepted?: boolean; state?: string | null; label?: string | null };
    }
  | { kind: "opening_read"; register: string | null };

/** The redesign's view of `GET /moves/{ref}` on a move-in. */
export type MoveInDetail = Omit<MoveRecordDetail, "state" | "step" | "chips"> & {
  status: MoveInStatus;
  reference: string | null;
  actions: string[];
  step: { reached: number | null; of: number; id: string | null; name: string | null } | number | null;
  tab_counts: Record<string, number | null>;
  still_open: StillOpenRow[];
  /** CR-181-BRC10 F3 — the account this move-in reopened, or null/absent. */
  reopened?: MoveInReopened | null;
} & (
    | {
        state: "request";
        chips: { requested_on: string | null; moves_in_on: string | null };
        tiles: RequestTiles;
        facts: RequestFacts;
      }
    | {
        state: "completed" | "in_flight" | "approved";
        chips: MoveRecordDetail["chips"];
        tiles: MoveTiles;
        facts: MoveDetailsFacts;
      }
  );

export type RequestDetail = Extract<MoveInDetail, { state: "request" }>;
export type JobDetail = Exclude<MoveInDetail, { state: "request" }>;

export function isRequestDetail(detail: MoveInDetail): detail is RequestDetail {
  return detail.state === "request";
}

// ══════════════════════════════════════════════════════════════════════════
// §9.REQ — the request's doors and tabs
// ══════════════════════════════════════════════════════════════════════════
export async function resendTheAsk(requestId: string, client: ApiClient = api): Promise<unknown> {
  return requireData(await client.post(`/service-requests/${enc(requestId)}/resend-ask`, {}));
}

export async function reopenRequest(
  requestId: string,
  reason: string,
  client: ApiClient = api,
): Promise<unknown> {
  return requireData(await client.post(`/service-requests/${enc(requestId)}/reopen`, { reason }));
}

/** One letter queued to the applicant (image 22) — the queue's own `status`,
 *  never a delivery claim (BR-NOT-013). */
export interface RequestMessageRow {
  id: string;
  template_code: string | null;
  to_name: string | null;
  to_address: string | null;
  channel: string;
  status: string;
  queued_at: string | null;
  sent_at: string | null;
}

export async function getRequestMessages(
  requestId: string,
  page: number,
  per: number,
  client: ApiClient = api,
): Promise<Paginated<RequestMessageRow>> {
  return requireData(
    await client.get<Paginated<RequestMessageRow>>(`/service-requests/${enc(requestId)}/messages`, {
      query: { page: String(page), per: String(per) },
    }),
  );
}

/** One timeline row (image 23) — `history_tab`'s shape. */
export interface RequestAuditRow {
  id: string;
  at: string;
  actor_name: string | null;
  actor_kind: "staff" | "customer" | "system" | string;
  kind: string;
  from_state: string | null;
  to_state: string | null;
  note: string | null;
  note_type: string | null;
}

export async function getRequestAudit(
  requestId: string,
  page: number,
  per: number,
  client: ApiClient = api,
): Promise<Paginated<RequestAuditRow>> {
  return requireData(
    await client.get<Paginated<RequestAuditRow>>(`/service-requests/${enc(requestId)}/audit`, {
      query: { page: String(page), per: String(per), "f.kind": "all" },
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// §9.FLOW — the committed move-in's doors (all take the move NUMBER)
// ══════════════════════════════════════════════════════════════════════════
export interface CancelPreview {
  kind: "not_started" | "committed";
  move_no: string;
  allowed: boolean;
  refusal: { code: string; message_key: string; question?: string; deposit_held?: string } | null;
  reverses:
    | { job: string }
    | {
        account: { account_no: string; closes_on: string };
        refund: { amount: string | null; currency: string | null };
        /** `DEF-CUS-9789` — uncleared counter payments the press calls off. */
        called_off?: { payment_no: string | null; amount: string; currency: string | null }[];
        work_orders: string[];
        reads_kept: number;
        unit_after: string;
      };
}

export async function getCancelPreview(moveNo: string, client: ApiClient = api): Promise<CancelPreview> {
  return requireData(await client.get<CancelPreview>(`/moves/${enc(moveNo)}/cancel-preview`));
}

export async function cancelMoveIn(
  moveNo: string,
  body: { note?: string },
  client: ApiClient = api,
): Promise<unknown> {
  return requireData(await client.post(`/moves/${enc(moveNo)}/cancel`, body));
}

export async function changeMoveInDate(
  moveNo: string,
  openedAt: string,
  client: ApiClient = api,
): Promise<{ move_no: string; opened_at: string; was: string; visits_to_reschedule: string[] }> {
  return requireData(
    await client.post<{ move_no: string; opened_at: string; was: string; visits_to_reschedule: string[] }>(
      `/moves/${enc(moveNo)}/move-in-date`,
      { opened_at: openedAt },
    ),
  );
}

export interface OpeningReadInput {
  meter_no: string;
  value?: string;
  estimate?: boolean;
  /** DEF-CUS-10167 — the day the register was read (`YYYY-MM-DD`). */
  read_at?: string;
}

export async function postOpeningReads(
  moveNo: string,
  reads: readonly OpeningReadInput[],
  client: ApiClient = api,
): Promise<{ move_no: string; posted_reads: unknown[]; warnings: { row_no: number; meter_no: string }[] }> {
  return requireData(
    await client.post<{ move_no: string; posted_reads: unknown[]; warnings: { row_no: number; meter_no: string }[] }>(
      `/moves/${enc(moveNo)}/opening-reads`,
      { reads },
    ),
  );
}

export async function addMoveWorkOrders(
  moveNo: string,
  body: Record<string, unknown>,
  client: ApiClient = api,
): Promise<{ move_no: string; work_orders: unknown[] }> {
  return requireData(
    await client.post<{ move_no: string; work_orders: unknown[] }>(`/moves/${enc(moveNo)}/work-orders`, body),
  );
}

// ── step 1's unit reads, reused for the Unit & reads tab (image 24) ─────────
export interface UnitMoveInFacts {
  unit: {
    id: string;
    unit_no: string | null;
    label: string | null;
    unit_type: string | null;
    floor_label: string | null;
    occupancy: "vacant" | "occupied";
    address: { line1: string | null; city: string | null; state: string | null; postal_code: string | null } | null;
  };
  building: {
    premise_no: string | null;
    name: string | null;
    area_name: string | null;
    parcel: string | null;
    routes: { code: string; name: string | null; cycle_code: string | null; cycle_name: string | null }[];
  };
  owner: { name: string | null; account_no: string | null } | null;
}

export async function getUnitMoveInFacts(unitId: string, client: ApiClient = api): Promise<UnitMoveInFacts> {
  return requireData(await client.get<UnitMoveInFacts>(`/units/${enc(unitId)}/move-in-facts`));
}

export interface UnitMeterRow {
  asset_no: string;
  kind: "meter" | "sub_meter" | "behind_the_meter";
  type_name: string | null;
  location_note: string | null;
  size_class: string | null;
  /** The size's NAME (`Water 5/8"`), served since 2.538.0 — what a clerk reads; `size_class` is the code (`DEF-CUS-9728`). */
  size_name?: string | null;
  unit: string | null;
  last_read: { value: string; unit: string | null; read_at: string | null } | null;
  needs_opening_read: boolean;
  children: UnitMeterRow[];
}

export interface UnitMoveInMeters {
  unit_id: string;
  services: { service: string; metered: boolean; meters: UnitMeterRow[] }[];
  unplaced: UnitMeterRow[];
}

export async function getUnitMoveInMeters(unitId: string, client: ApiClient = api): Promise<UnitMoveInMeters> {
  return requireData(await client.get<UnitMoveInMeters>(`/units/${enc(unitId)}/move-in-meters`));
}
