// ── Trace ──────────────────────────────────────────────
// Change:  **PO drawings of 2026-09-25** — `Reconnect1` · `Reconnect2` ·
//          `MasterReconnect1` · `MasterReconnect2`. `DEF-CUS-6743`.
// Story:   `US-CUS-032` (`S148`) — *Put service back on*.
// Serves:  `GET /disconnects/{ref}/reconnect` and
//          `POST /disconnects/{ref}/reconnect/work-orders`, both
//          `06-backend/apps/customers/reconnect_read.py`.
// Rules:   B14 rule 31 (no database id is ever a visible value — the address
//          is the CASE NUMBER) · hard rule 2 (money arrives as strings,
//          displays at 2, is never parsed into a float here).
// ───────────────────────────────────────────────────────
/**
 * The wire shape of `S148`, and the one place this screen's address is spelled.
 *
 * ⚠ **THE LEADING SLASH IS LOAD-BEARING** — `DEF-CUS-4010`. Without it
 * `apiPath` joins the tenant and the path with nothing between them and every
 * request goes to `/api/brazosbenddisconnects/…`: a 404 on every case,
 * invisible because a 404 and a stated absence look identical on screen.
 */
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

export const RECONNECT_SCREEN = "S148.reconnect";

/**
 * `/disconnects/{ref}/reconnect` — **the case record's address plus one
 * segment**, which is 4.8's whole answer.
 *
 * The clerk arrives from `/disconnects/dsc-26-0005`, so this is where they go,
 * and the back link writes itself. `ref` is the CASE NUMBER and never a uuid
 * (B14 rule 31) — `DSC-26-0005` is what a clerk reads back to a customer.
 */
export function reconnectPath(reference: string): string {
  return `/disconnects/${encodeURIComponent(reference)}/reconnect`;
}

export const RECONNECT_ROUTE = "/disconnects/:ref/reconnect";

/** Why a figure is not on the screen — the shape every absence here carries. */
export interface ReconnectAbsence {
  code: string;
  br_ref?: string;
  detail: string;
}

/** Rule 2's two strings. `stored` is 4dp, `display` is 2dp, both STRINGS. */
export interface ReconnectMoney {
  stored: string | null;
  display: string | null;
  currency?: string | null;
  unavailable?: ReconnectAbsence | null;
}

/** One row of *Which services go back on*. */
export interface ReconnectServiceRow {
  service: string | null;
  /** `common_supply` · `unit_meters` · null. A PLACE, never a second service. */
  scope: string | null;
  /** Hard rule 8 — walked to the premises by the server. Never a column here. */
  service_point: string | null;
  point_known: boolean;
  meter: string | null;
  meter_absence: ReconnectAbsence | null;
  how_options: string[];
  how_default: string;
  instruction: string | null;
  /** `DEF-CUS-9630` — the job raised for this row, read back on every load;
   *  `done` = the field closed it, `accepted` = a person accepted it. */
  work_order: { reference: string; assignee: string | null; done?: boolean; accepted?: boolean } | null;
  /** `all_occupants` · `each_unit` · null on a regular account. */
  reaches: string | null;
}

/** One line of *What is still owed*. */
export interface ReconnectOwedLine {
  code: string;
  from_code: string;
  amount: ReconnectMoney | null;
  unavailable?: ReconnectAbsence | null;
  when: string | null;
  /** Drawn with a leading minus — a payment or an applied deposit. */
  negative: boolean;
}

export interface ReconnectDetail {
  case_no: string | null;
  account: {
    account_no: string | null;
    customer_name: string | null;
    address: string | null;
    /** `master` · `regular` — 4.3's second half, on no reconnect surface before. */
    account_kind: "master" | "regular";
    account_class: string | null;
    cut_on: string | null;
    balance: ReconnectMoney;
  };
  master: { is_master: boolean; units: number | null; unit_accounts: number | null };
  services: {
    rows: ReconnectServiceRow[];
    unavailable: ReconnectAbsence | null;
    addable: { service: string; service_point: string | null }[];
  };
  owed: {
    lines: ReconnectOwedLine[];
    still_owed: ReconnectMoney;
    total_is_the_ledger: ReconnectAbsence;
    plan_label: string | null;
  };
  deposit: {
    held_before_the_cut: ReconnectMoney | null;
    disposition: string | null;
    new_deposit_required: boolean | null;
  };
  consequences: { code: string }[];
  /** `BR-CUS-1097` on screen: a figure and four words, or nothing at all. */
  warning: { code: string; amount: ReconnectMoney } | null;
  /**
   * ⛔ **WHAT THE ENGINE WOULD REFUSE TODAY** — asked of the server, never
   * restated here. `not_settled` is the one that should not be there
   * (`BR-CUS-1097`, `DEF-CUS-6742`); when that clause goes this answers `null`
   * with nothing on this side edited.
   */
  commit_refused_by: { code: string; br_ref: string } | null;
  step: "mark_reconnecting" | "restore_service" | null;
  restore_on: string;
}

export async function readReconnect(
  reference: string,
  client: ApiClient = api,
): Promise<ReconnectDetail> {
  const response = await client.get<ReconnectDetail>(reconnectPath(reference));
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One row's visit, raised from the row (4.5) — `BR-WRK-055`: it never fails the flow. */
export async function raiseReconnectWorkOrder(
  reference: string,
  body: { template_ids: string[] } | { service: string },
  client: ApiClient = api,
): Promise<{
  work_orders: { order_no?: string | null; work_order_no?: string | null; assignee?: string | null }[];
  warnings: { code: string; detail?: string }[];
}> {
  const response = await client.post<{
    work_orders: { order_no?: string | null; work_order_no?: string | null; assignee?: string | null }[];
    warnings: { code: string; detail?: string }[];
  }>(`${reconnectPath(reference)}/work-orders`, body);
  return response.data ?? { work_orders: [], warnings: [] };
}

/**
 * `DEF-CUS-10657` — PO C1 2026-10-29, *"Restore = Reconnect request"*.
 *
 * Confirm on a CUT case is the RECONNECT REQUEST: the case moves to
 * `reconnecting` and one reconnect job is raised per service in `services`
 * (the rows still on *Work order* with no job). Nothing is restored yet and
 * an unpaid balance never refuses it (`BR-CUS-1097`).
 */
export async function requestReconnect(
  reference: string,
  body: { on_date: string; services: string[] },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(`${reconnectPath(reference)}/request`, body);
}

/**
 * Confirm on a RECONNECTING case COMPLETES the request: service is restored,
 * the account goes back to its status and *Service restored* is queued once.
 * The clerk's explicit act (`BR-PAY-036`) — a closed field job never does this.
 */
export async function completeReconnect(
  reference: string,
  body: { on_date: string },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(`${reconnectPath(reference)}/complete`, body);
}

/** The query key, exported so a test seeds the same one the page reads. */
export function reconnectKey(reference: string): [string, string] {
  return ["reconnect", reference];
}
