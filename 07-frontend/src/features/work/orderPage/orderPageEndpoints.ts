// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — one order, both shapes
//           (images 03–11). Tasks P1.2, P1.15–P1.24, P1.29, P1.32, P4.2, P4.3.
// Contract: CR-168-BRC10 §7.3 (the agreed API contract, lane WORK-SRV). Every
//           field below that is NEW in round 2 is OPTIONAL in its type, because
//           lane SRV-1 serves it in parallel: the screen draws what the server
//           sends and a dash for what it does not yet.
// ───────────────────────────────────────────────────────
//
// ⚠ **A SEPARATE FILE FROM `workEndpoints.ts` ON PURPOSE.** Two lanes of round
// 2 (ORDER-PAGE and ORDERS-LIST) build on Work at once; `workEndpoints.ts` is
// 2,800 lines that both read, and a whole-file write by either would revert the
// other (hard-won law 11). Everything the ORDER PAGE adds lives here.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1). */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** `GET /work-orders/{id}` — §7.3's additions to the dispatcher's row. */
export interface OrderCustomer {
  name: string | null;
  phone: string | null;
  account_no: string | null;
  /** `DEF-WRK-9678` — OUR customer number (*C-00001*), images 03/04's
   *  *Ana Alvarez · C-00001*. Absent on a server before 2.519. */
  customer_no?: string | null;
}

/** What the job is measured against (`dispatch._sla_of`): its own `due_at`
 *  (`target: priority`) or, on a job raised with no priority, the raise plus
 *  the tenant's default target (`target: default`). */
export interface OrderSla {
  due_at: string | null;
  target: "priority" | "default" | null;
  at_risk: boolean;
}

/** ⚠ THE SERVER'S SHAPE (`dispatch._location_of`): premises, unit and asset
 *  are OBJECTS. This read `unit: string | null` until `DEF-WRK-9600` — typed
 *  from the contract's prose before the server existed — and the page crashed
 *  on every job with a unit the day the server began answering. Render a
 *  unit's `label`, never the object. */
export interface OrderLocation {
  premises: { id: string; premise_no: string | null } | null;
  unit: { id: string; label: string | null } | null;
  asset: { id?: string; asset_no: string | null; serial: string | null } | null;
  address: string | null;
}

/** Served ONLY when `shape = completed` (rulings 15/17). `image_url` is a
 *  four-hour link (P1.23) — never stored, never put in anything that outlives
 *  it. */
export interface OrderSignatureMark {
  printed_name: string | null;
  signed_at: string | null;
  refused: boolean;
  decline_reason?: string | null;
  captured_by: { name: string } | null;
  image_url: string | null;
  /** A refusal's door-hanger photograph — the web's chosen attachment, or the
   *  phone's once its bytes have landed (`DEF-WRK-10625`). Builds the link
   *  only; never shown (B14 rule 31). Absent on a server before 2.605. */
  door_hanger_attachment_id?: string | null;
  /** The phone named a door-hanger photo whose bytes have not landed yet. */
  door_hanger_uploading?: boolean;
}

export interface OrderHold {
  reason: { code: string; name: string } | null;
  expected_return_on: string | null;
}

export interface OrderPageFields {
  /** `open | completed` — rulings 15 and 17: the page has two shapes. */
  shape?: "open" | "completed";
  customer?: OrderCustomer | null;
  location?: OrderLocation | null;
  signature?: OrderSignatureMark | null;
  hold?: OrderHold | null;
  accepted?: { by: string | { name: string } | null; at: string | null } | null;
  /** REQUIRED photos declared and still uploading — Accept waits for none
   *  (PO 2026-10-04, (a)). Absent on a server before 2.507. */
  photos_uploading?: number;
  closed?: {
    by: string | { name: string } | null;
    at: string | null;
    /** `BR-WRK-061` — where the close was made; `precise: false` reads
     *  *Location not precise* where the office accepts (PO 2026-10-04). */
    location?: {
      precise: boolean;
      missing?: boolean;
      accuracy_m?: string;
      threshold_m: number;
    } | null;
    /** `DEF-WRK-4127` — the technician's *Arrived* and *Finished*, which
     *  price the labour; null when the close carried none. */
    labour_time?: {
      arrived_at: string;
      finished_at: string;
      minutes: number;
    } | null;
    /** FB-014 (DEF-FLD-10639) — how far the phone's clock was off when it
     *  sent the close, `server − phone` in seconds (negative: the phone was
     *  fast). Every time above was already shifted by it. Null: no reading. */
    device_clock?: {
      offset_s: number;
      device_time: string;
    } | null;
  } | null;
  completed_at?: string | null;
  outcome?: string | null;
  /** `DEF-WRK-9677` — served on every row since 2.497.0 (SRV-1). */
  sla?: OrderSla | null;
  /** `DEF-WRK-9624` — the failed job this one follows (`BR-WRK-054`). */
  follows?: { order_no: string } | null;
  /** `DEF-WRK-9624` — the follow-ups raised when this one failed. */
  follow_ups?: readonly { order_no: string }[];
}

/** One row of the order's history — `GET /work-orders/{id}/audit` (§7.3). The
 *  union of the assignment rows and the order's own `audit_log` rows, in
 *  NAMES and WORDS, never ids. `who` is the person the act was done TO (the
 *  holder); `by` is the person who DID it (P1.17). */
export interface OrderHistoryRow {
  act: string;
  at: string | null;
  who?: { kind: string; name: string } | null;
  /** Today a plain name; §7.3 serves `{name}`. Both are read. */
  by?: string | { name: string } | null;
  scheduled_for?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  reason?: string | null;
  before_display?: string | null;
  after_display?: string | null;
}

export function historyBy(row: OrderHistoryRow): string | null {
  const by = row.by ?? null;
  if (by === null) return null;
  return typeof by === "string" ? by : by.name;
}

export async function getOrderHistory(
  orderId: string,
  client: ApiClient = api,
): Promise<{ order_no: string | null; rows: OrderHistoryRow[] }> {
  const data = requireData(
    await client.get<{ order_no: string | null; rows?: OrderHistoryRow[]; results?: OrderHistoryRow[] }>(
      `/work-orders/${orderId}/audit`,
    ),
  );
  // §7.3 pages this read (`{results, count, …}`); today it answers `{rows}`.
  return { order_no: data.order_no ?? null, rows: data.rows ?? data.results ?? [] };
}

/** `GET /work/hold-reasons` — the tenant's lookup (P0.4, J1). */
export interface HoldReason {
  code: string;
  name: string;
  /** ⚠ The server answers ACTIVE reasons only and does not send this flag
   *  (`DEF-WRK-9601`); a row is kept unless it says `active: false`. */
  active?: boolean;
  rank: number;
}

export async function listHoldReasons(client: ApiClient = api): Promise<HoldReason[]> {
  const data = requireData(
    await client.get<HoldReason[] | { results: HoldReason[] }>("/work/hold-reasons"),
  );
  const rows = Array.isArray(data) ? data : data.results;
  return rows.filter((row) => row.active !== false).sort((a, b) => a.rank - b.rank);
}

/** `POST /work-orders/{id}/hold` with §7.3's body — P4.3. */
export async function holdOrderWithReason(
  orderId: string,
  body: { reason_code: string; expected_return_on?: string | null; note?: string | null },
  client: ApiClient = api,
): Promise<{ id: string; dispatch_state: string }> {
  const payload: Record<string, string> = { reason_code: body.reason_code };
  if (body.expected_return_on) payload.expected_return_on = body.expected_return_on;
  if (body.note && body.note.trim() !== "") payload.note = body.note.trim();
  return requireData(
    await client.post<{ id: string; dispatch_state: string }>(`/work-orders/${orderId}/hold`, payload),
  );
}

/** `POST /work-orders/{id}/resume` — P4.3, *Resume once held*. */
export async function resumeOrder(
  orderId: string,
  client: ApiClient = api,
): Promise<{ id: string; dispatch_state: string }> {
  return requireData(
    await client.post<{ id: string; dispatch_state: string }>(`/work-orders/${orderId}/resume`, {}),
  );
}

/** `POST /work-orders/{id}/send-back {reason}` — P4.14, `DEF-WRK-9675`: a
 *  finished job back to the field, only before it is accepted. The server
 *  requires the reason (`work.order.send_back_reason_required`). */
export async function sendBackOrder(
  orderId: string,
  reason: string,
  client: ApiClient = api,
): Promise<{ id: string; state: string }> {
  return requireData(
    await client.post<{ id: string; state: string }>(`/work-orders/${orderId}/send-back`, {
      reason: reason.trim(),
    }),
  );
}

/** `POST /work-orders/{id}/duplicate` — `DEF-WRK-9690`: the same job raised
 *  again, on the same place, unassigned. Answers the new order. */
export async function duplicateOrder(
  orderId: string,
  client: ApiClient = api,
): Promise<{ id: string; order_no: string | null }> {
  return requireData(
    await client.post<{ id: string; order_no: string | null }>(`/work-orders/${orderId}/duplicate`, {}),
  );
}
