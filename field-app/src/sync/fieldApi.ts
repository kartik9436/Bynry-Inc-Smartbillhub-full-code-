/**
 * THE SERVER'S ONLINE DOORS — every field route that is not the job sync, the
 * reads sync, the photo link or the change feed (`transport.ts` has those).
 * Each wave's screens keep the port they were built against
 * (`theDay/nearbyApi.ts`, `me/services.tsx` alerts, `onSite/money.ts`, …); the
 * adapters in `fieldDoors.ts` map this API onto those ports, so no screen
 * learns the wire.
 *
 * READ FROM THE SERVER'S CODE ON 2026-10-21 (lane INTEGRATE-2):
 *
 *   GET  work/mobile/nearby?lat=&lng=&radius_mi=&scope=&page=&per=   `field_find.nearby` (N11)
 *        → {count, page, pages, per, next, previous, results:[NearbyCard],
 *           unassigned, without_location, complete, radius_mi, scope}
 *   POST work/mobile/jobs/{id}/claim                                  `field_dispatch.claim` (N15)
 *        → {order_id, order_no, dispatch_state, technician, already_yours, advice, against_advice}
 *        refused `work.claim.already_taken` · `not_open` · `pending_office`
 *   GET  work/mobile/alerts?page=&per=                                `field_alerts.my_alerts` (N25)
 *   POST work/mobile/alerts/{id}/ack                                  `field_alerts.acknowledge`
 *   POST work/mobile/jobs/{id}/reopen  {reason, note?, key?}          `field_reopen.technician_reopen` (N21)
 *   GET  work/mobile/jobs/{id}/money                                  `work/money.money_read` (N13)
 *        — PER JOB, not `accounts/{id}/money` as the handset's hold named it.
 *   GET  work/mobile/jobs/{id}                                         `mobile.bundle` (the job bundle)
 *   POST work/mobile/jobs/{id}/acts    {act: depart|arrive, key?}     `mobile.field_act` — `duplicate: true` on a replayed key
 *   PUT  work/mobile/jobs/{id}/labour  {depart_at?, arrive_at?, start_at?, end_at?, technician_id?}
 *        `field_labour.record_time` (N17) — `technician_id` only from the lead (FF-29 *Correct their time*)
 *   POST work/mobile/jobs/{id}/crew    {technician_id, key?}          `field_labour.add_technician`
 *        {act: 'leave', technician_id, ended_at?}                     `field_labour.member_leaves` (FF-29's ×)
 *   POST work/mobile/jobs/{id}/hand-back {reason, note?, key?}        `field_dispatch.hand_back` (N20) — `duplicate: true` on a replayed key
 *   POST work/mobile/jobs/{id}/accept  {capture_token?}               `mobile.accept_job` — idempotent (DEF-FLD-10579)
 *   POST work/mobile/jobs/{id}/decline {reason, note?, capture_token?} `mobile.decline_job` — before accepting only
 *   POST work/mobile/orders            {key, template_id, …}          `field_raise.raise_from_field` (N16)
 *   GET  work/mobile/assets/search?q=&page=&per=                      `field_find.search_assets` (N9)
 *   GET  work/mobile/templates?q=&page=&page_size=                    `field_raise.templates_catalogue` (N8)
 *        → the product envelope {count, next, previous, results}
 *   GET  work/mobile/findings/options                                  `route_findings.finding_options` (BR-WRK-067)
 *   GET  work/mobile/findings/{key}                                    `route_findings.mobile_finding` — the reader's own
 *   POST work/mobile/findings/{key}/work-order {template_id, priority_id?}  `route_findings.mobile_create`
 *        → the finding, `duplicate: true` when it already had a job (by rule or an earlier press)
 *
 * ⚠ THE OWN DOORS TAKE THE CAPTOR'S TOKEN (lane S-GAPS, `mobile.door_actor`).
 * Acts, labour, crew, hand-back, accept, decline and raise read `capture_token` from the body
 * and write the act as its CAPTOR, whoever is signed in (BR-WRK-059) — so an
 * outbox item goes through them under its captor's credential exactly as a
 * sync item does, and no longer waits for its captor to be the one signed in.
 * An expired or forged token is refused 403 by name
 * (`work.mobile.capture_token_*`) and the item waits for that captor's next
 * sign-in (`outbox.sendThroughDoor`). The online-only doors (nearby, claim,
 * alerts, money, …) are still answered as whoever is signed in.
 */
import { TransportError } from './transport';

/** One page as `field_find._page` answers it. */
export interface WirePage<T> {
  count: number;
  page?: number;
  pages?: number;
  per?: number;
  next: number | string | null;
  previous?: number | string | null;
  results: T[];
}

export interface WirePremise {
  id: string;
  premise_no?: string | null;
  address?: string | null;
}

export interface WireNearbyCard {
  id: string;
  order_no: string | null;
  type: string | null;
  premise: WirePremise | null;
  distance_mi: string | null;
  due_at: string | null;
  est_minutes: number | null;
  priority: { code?: string | null; rank?: number | null } | null;
  holder: 'unassigned' | 'mine' | 'taken';
  taken_by: string | null;
  claimable: boolean;
}

export interface WireAlert {
  id: string;
  kind: string;
  work_order_id: string | null;
  order_no: string | null;
  premise: WirePremise | null;
  message: string | null;
  sent_at: string;
  ack_required: boolean;
  ack_due_at: string | null;
  acknowledged_at: string | null;
  late?: boolean;
  dispatch_told?: boolean;
  seconds_to_ack?: number | null;
}

/** A figure as `payments/field_money.money` sends it: 4 places to store, 2 to show. */
export interface WireMoney {
  amount: string;
  display: string;
  currency: string | null;
}

export interface WireJobMoney {
  order_no: string | null;
  as_at: string;
  fresh_minutes: number;
  withheld: string | null;
  account_no: string | null;
  owing: WireMoney | null;
  balance: WireMoney | null;
  currency: string | null;
  latest_payment: (WireMoney & { state?: string; posted_at?: string | null; cleared_at?: string | null; method?: string | null }) | null;
  charges: Array<{ charge_code: string; charged?: WireMoney | null; still_open?: WireMoney | null; paid?: boolean | null; charged_on?: string | null }>;
  /** FB-023 F5 — on a DISCONNECT job only (null elsewhere, absent on an older server). */
  disconnect?: {
    plan: { status: 'on_track' | 'behind' | string; missed?: number } | null;
    notice: { tier: string; issued_on: string; amount: WireMoney | null } | null;
  } | null;
  /** FB-028 — on a job RAISED ON SITE only (null elsewhere, absent on an older
   *  server): the notice's end and whether the account is protected. */
  field_gate?: {
    raised_on_site?: boolean;
    reconnect_limit?: WireMoney | null;
    notice: { tier: string; issued_on: string; ends_on: string | null } | null;
    notice_open: boolean;
    protected: boolean;
  } | null;
  unavailable: Array<{ code?: string | null }>;
}

/** FB-028 — `POST jobs/{id}/step-stopped`: a raised job's gated step stopped. */
export interface WireStepStopped {
  reason: 'owes_over_limit' | 'balance_cleared' | 'notice_open' | 'protected';
  owing?: string | null;
  limit?: string | null;
  money_as_at?: string | null;
  ends_on?: string | null;
}

export interface WireBundleTask {
  id: string;
  seq: number;
  title: string;
  instruction?: string | null;
  photo_required?: boolean;
  is_mandatory?: boolean;
  ticked_at?: string | null;
  /** FB-013 / R18 — the step's payment check, as the job copied it from its
   *  template: how fresh the money must be (minutes; null = no check) and a
   *  fee's charge code (R111). */
  money_fresh_minutes?: number | null;
  money_charge_code?: string | null;
}

/**
 * One help entry as `mobile._help_row` sends it (`work_order_help`, BR-WRK-038).
 * `document`: `ref` is the stored document's id and `url` a four-hour
 * pre-signed link (null when the server could not resolve it — listed, never
 * dropped). `link`: `ref` and `url` are its https address. `phone`: `ref` is
 * the number. `note`: `ref` is its words, if any.
 */
export interface WireHelp {
  id: string;
  seq: number;
  kind: 'document' | 'phone' | 'link' | 'note' | string;
  label: string;
  ref: string | null;
  url: string | null;
  /** FB-031 — a document row: is there a stored file at all. `false` is
   *  *No file attached.*, never *Downloads at next sync*. Absent: an older server. */
  has_file?: boolean;
  /** FB-031 — our own route for the bytes (`/work/mobile/jobs/{id}/help/{hid}/content`),
   *  fetched with the technician's credential; it never expires. */
  content_path?: string | null;
  file_name?: string | null;
  file_bytes?: number | null;
  content_type?: string | null;
}

export interface WireBundle {
  order_id: string;
  order_no: string | null;
  template_id: string | null;
  template_version: number | null;
  safety: Array<{ id: string; seq: number; text: string; is_mandatory?: boolean; ticked_at?: string | null }>;
  tasks: WireBundleTask[];
  readings: Array<{
    id: string;
    seq: number;
    prompt: string;
    unit_of_measure: string | null;
    min_value: string | null;
    max_value: string | null;
    photo_required?: boolean;
    kind?: string | null;
    /** FB-030 — what was captured (a refilled closed job's record shows it). */
    value?: string | null;
    value_text?: string | null;
    unable_to_read?: boolean;
    captured_at?: string | null;
  }>;
  materials: Array<{ id: string; part_no?: string | null; part_name?: string | null; planned_qty?: string | null; unit_of_measure?: string | null; unplanned?: boolean }>;
  /** The job's help, copied from its template at creation (DEF-FLD-10581). */
  help?: WireHelp[];
  /** DEF-MET-10609 — the utility's ONE can't-read list (switched-on reasons,
   *  in its order), so FF-20's *Unable to read* picks from it offline. */
  cant_read_reasons?: Array<{ code: string; name: string }>;
  /** FB-023 — the job's account (`money.account_id_of`); kept beside the job,
   *  never used to read money (that door is per job). */
  account_id?: string | null;
  /** The job's copy of its template's *What the technician sees on the job*
   *  ticks (`checklist.checklist` → `details`; F6, and F4's fifth) — and, since
   *  FB-028, `reconnect_limit`, `raised_on_site` and `skill_advice`. */
  details?: WireJobDetails | null;
  /** FB-030 — a CLOSED job's record (`mobile._closed_record`); null while open. */
  record?: WireClosedRecord | null;
  [more: string]: unknown;
}

/** FB-030 — what a closed job's record carries beyond its checklist. No money, no speed. */
export interface WireClosedRecord {
  completed_at?: string | null;
  outcome?: string | null;
  problem?: string | null;
  done?: string | null;
  signature?: { kind: 'signed' | 'refused'; name?: string | null; reason?: string | null; at?: string | null } | null;
  photos?: Array<{ photo_id: string; task_id?: string | null; reading_id?: string | null; taken_at?: string | null }>;
}

/** The ticks as `checklist.py` sends them; an absent tick reads as shown. */
export interface WireJobDetails {
  show_account_summary?: boolean;
  show_asset_card?: boolean;
  show_access_notes?: boolean;
  show_appointment?: boolean;
  /** FB-023 F4 — Balance & payments. Display only: FB-013's stop ignores it. */
  show_balance_payments?: boolean;
  /** FB-028 — the template's Reconnect limit, copied onto the job (4 places). */
  reconnect_limit?: string | null;
  /** FB-028 — the job was raised on site (its steps gate themselves). */
  raised_on_site?: boolean;
  /** FB-028 — the job's unit, sent with a raise carried from it. */
  unit_id?: string | null;
  /** FB-028 W3 = C — the template's skill and whether this technician holds it. */
  skill_advice?: { skill: { name: string } | null; has_skill: boolean } | null;
}

export interface WireAssetHit {
  id: string;
  asset_no: string | null;
  serial: string | null;
  type: string | null;
  model: string | null;
  size_class: string | null;
  sub_meter: boolean;
  place: { premises?: WirePremise | null; unit_label?: string | null } | null;
}

/** A named reference as the server sends it (`metering_seam._template_row`). */
export interface WireNamedRef {
  id: string;
  code?: string;
  name: string;
}

/**
 * One row of `GET work/mobile/templates` (`field_raise.templates_catalogue`).
 * ⚠ `service` and `job_type` are OBJECTS, not names (DEF-FLD-10613, MQ-034):
 * this type said `string` and the phone printed the object. The real row is
 * `tests/sync/support/serverTemplate.json`, locked to the server by
 * `06-backend/tests/test_def_fld_10613_template_shape.py`.
 */
export interface WireTemplate {
  id: string;
  name: string;
  version: number | string;
  service: WireNamedRef | string | null;
  job_type?: WireNamedRef | null;
  steps?: number;
  safety_checks?: number;
  readings?: number;
  materials?: number;
  help?: number;
  last_used_at?: string | null;
  recent?: boolean;
}

/** One route finding as the server answers it (`route_findings.answer`). */
export interface WireFinding {
  key: string;
  kind: string;
  status: 'open' | 'work_order_created';
  conversion: 'by_rule' | 'by_hand' | null;
  work_order: { id: string; order_no: string | null } | null;
  duplicate?: boolean;
}

/** RW-21's lists and *Create work order*'s priorities (`finding_options`). */
export interface WireFindingOptions {
  kinds: { code: string; label_key: string }[];
  urgencies: { code: string; label_key: string }[];
  priorities: { id: string; code: string; name: string; rank: number }[];
}

export type LabourMoments = Partial<Record<'depart_at' | 'arrive_at' | 'start_at' | 'end_at', string>>;

/**
 * What an outbox item adds to an own-door call (lane S-GAPS): its key (minted
 * at capture, `07-endpoints.md` §0 rule 7), its captor's capture token, and —
 * for the lead correcting a helper — whose clocks they are. The transport puts
 * them in the JSON body as `key`, `capture_token` and `technician_id`; each is
 * left out when absent, so an online call that has none sends what it always
 * sent.
 */
export interface DoorExtra {
  key?: string;
  captureToken?: string | null;
  technicianId?: string;
}

export interface FieldApi {
  nearby(q: { lat: number; lng: number; radiusMi: number; page: number; per?: number }): Promise<WirePage<WireNearbyCard> & { unassigned?: number }>;
  claim(jobId: string): Promise<{ order_id: string; already_yours?: boolean }>;
  alerts(page: number): Promise<WirePage<WireAlert>>;
  acknowledgeAlert(alertId: string): Promise<WireAlert>;
  reopen(jobId: string, body: { reason: string; note?: string | null; key: string }): Promise<unknown>;
  jobMoney(jobId: string): Promise<WireJobMoney>;
  /** FB-028 — tell the office a raised job's step stopped. Optional: an older
   *  transport (and the test fakes) have no such door. */
  stepStopped?(jobId: string, body: WireStepStopped): Promise<unknown>;
  jobBundle(jobId: string): Promise<WireBundle>;
  /**
   * FB-031 — where and how to fetch one of OUR OWN paths outside a JSON call
   * (a help document's bytes): the tenant's address and the headers every
   * call carries, `Authorization` among them. Null with no sign-in.
   */
  fileRequest?(path: string): { url: string; headers: Record<string, string> } | null;
  jobAct(jobId: string, act: 'depart' | 'arrive', extra?: DoorExtra): Promise<unknown>;
  recordLabour(jobId: string, moments: LabourMoments, extra?: DoorExtra): Promise<unknown>;
  addCrew(jobId: string, body: { technician_id: string; key: string }, extra?: DoorExtra): Promise<unknown>;
  /** FF-29's × — the lead stops a helper's labour at `ended_at` (`member_leaves`). */
  leaveCrew(jobId: string, body: { technician_id: string; ended_at: string | null }, extra?: DoorExtra): Promise<unknown>;
  handBack(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<unknown>;
  /** *Start* on a job not yet accepted (DEF-FLD-10579). Idempotent on the server. */
  acceptJob(jobId: string, extra?: DoorExtra): Promise<unknown>;
  /** *Decline* before starting, with a reason (DEF-FLD-10579). */
  declineJob(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<unknown>;
  raiseOrder(body: Record<string, unknown>, extra?: DoorExtra): Promise<{ order_id?: string; order_no?: string | null; duplicate?: boolean }>;
  searchAssets(q: string, page: number): Promise<WirePage<WireAssetHit>>;
  templates(page: number): Promise<WirePage<WireTemplate>>;
  findingOptions(): Promise<WireFindingOptions>;
  finding(key: string): Promise<WireFinding>;
  findingWorkOrder(key: string, body: { template_id: string; priority_id?: string }): Promise<WireFinding>;
}

/** The transport the app builds is also the field API (`HttpTransport`); a fake may not be. */
export function asFieldApi(x: unknown): FieldApi | null {
  return x && typeof (x as FieldApi).jobBundle === 'function' && typeof (x as FieldApi).raiseOrder === 'function'
    ? (x as FieldApi)
    : null;
}

/** The server's machine words for a refusal — `{message_key, params}` from the error envelope. */
export function refusalOf(err: unknown): { messageKey: string | null; params: Record<string, unknown> } | null {
  if (!(err instanceof TransportError) || err.kind !== 'http') return null;
  const body = (err.body ?? {}) as { message_key?: unknown; params?: unknown };
  return {
    messageKey: typeof body.message_key === 'string' ? body.message_key : null,
    params: body.params && typeof body.params === 'object' ? (body.params as Record<string, unknown>) : {},
  };
}
