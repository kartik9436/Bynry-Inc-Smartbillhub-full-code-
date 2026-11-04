// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W6 tasks 6.11 (S87 the wizard) · 6.13 (S88 the connection
//           detail) · 6.14 (the work-order surface) — the TRANSPORT half.
//           `worklistEndpoints.ts` holds `GET /connections` (the S86 list) and
//           is another lane's file; this one holds everything the DETAIL and
//           the WIZARD need, so two lanes are not editing one module.
// Rules:    BR-MET-112 (nothing is written until step 8 — so steps 1–7 make NO
//           request at all, which is why there is no draft endpoint below) ·
//           BR-MET-110 + BR-MET-115 (a person accepts the field's data, and
//           that press is the send) · BR-MET-113 (the owner gets an ACCOUNT,
//           OQ-367 CLOSED) · BR-MET-114 (outstanding work is human-marked) ·
//           CLAUDE.md hard rule 2 (money 4dp stored / 2dp displayed — every
//           money field below is the server's `{stored, display}` pair and is
//           NULLABLE) · B14 rule 21 (this file declares no class)
// Questions: OQ-379 (OPEN — the quote is four coded lines and billing's
//           one-time door takes one code with no amount, so `charges` is
//           nullable and the total is a recorded FIGURE) · OQ-376 (OPEN — the
//           platform has no `connection` source kind, so a queued letter can
//           come back `queued:false` with its reason) · OQ-371 (OPEN — the
//           list's segments; untouched here) · OQ-249 (the Work module is R5 —
//           `we_schedule` and the template CATALOGUE screens are not built)
// Tests:    07-frontend/src/features/customers/NewConnectWizard.test.tsx ·
//           ConnectionDetailPage.test.tsx
// Impacts:  ⛔ **06-backend/apps/metering/api.py SERVES NONE OF THIS YET** —
//           see the block below. REPORTED to the coordinator with the exact
//           view code; this lane does not own `api.py`.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ⛔ READ THIS FIRST — THE DOORS BELOW ARE NOT MOUNTED, AND SAYING SO IS THE
//    POINT (hard-won law 1: a comment claiming a guarantee is not the guarantee)
// ══════════════════════════════════════════════════════════════════════════
// Measured on the tree, 2026-08-25: `apps/metering/api.py`'s `urlpatterns` has
// exactly ONE connection path — `path("connections", connections)`, the S86
// list. `connections.py` is 2,680 lines and holds `create_connection`,
// `commit_connection`, `create_owner_account`, `submit_field_result`,
// `accept_field_result`, `dispatch_communication`, `mark_outstanding`,
// `close_outstanding` and `outstanding_work` — **every one of them reachable
// only from Python.**
//
// So the two screens this file serves are, until that lands, hard-won law 2 in
// its purest form: built and not wired. The shapes below are NOT invented —
// each field is the return value of a named function in `connections.py`, so
// wiring them is mechanical rather than a negotiation. Where the service layer
// reports an ABSENCE rather than a figure (`sub_meter_links`, the quote's
// lines) the type here is `null` plus a reason, because that absence IS the
// feature and a `0` would erase it.
//
// ⚠ **NOTHING IN THIS FILE FABRICATES A FALLBACK.** Every money field is
// `{stored: string | null, display: string | null}` and every count that the
// server cannot produce is `null`. A screen branches on the null and prints the
// reason; it never prints a zero, a dash-with-no-explanation or a figure this
// client computed for itself (DEF-088's second rounding path, DEF-127's
// fabricated `$0.00`).
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

import type { ServiceRequestCoApplicant } from "./serviceRequestEndpoints";
import type { WorklistAbsence, WorklistMoney } from "./worklistEndpoints";
import type { BuildHome } from "@/features/work/workEndpoints";

export type { WorklistAbsence, WorklistMoney };

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported — `worklistEndpoints` keeps its own copy for
 *  the same reason: no coupling between two files different lanes hold. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// THE VOCABULARIES — every one of them lifted from `connections.py`, not typed
// out from the drawing
// ══════════════════════════════════════════════════════════════════════════

/** `connections.py` lines 329-346. ⚠ The product word is `activated`, never
 *  `energised` (CR-032, PO 2026-08-25). B18 still DRAWS *"Partly energised"*
 *  and is stamped rather than rewritten. */
export const CONNECTION_STATES = [
  "draft",
  "requested",
  "in_progress",
  "partly_activated",
  "on_hold",
  "activated",
  "cancelled",
] as const;

/** `connections.py` — the per-service states. ⚠ `partly_activated` is NOT one
 *  of them and its absence is deliberate: a stored row is one service AT ONE
 *  UNIT and cannot be partly anything. "Partly" is a COUNT over rows. */
export const CONNECTION_SERVICE_STATES = [
  "pending",
  "in_progress",
  "on_hold",
  "activated",
  "cancelled",
] as const;

/** B18 §8.2, verbatim: *"A template declares `scope`: per-premise · per-unit ·
 *  per-asset."* All three appear in ONE connection (§5.4.9 fact 3). */
export const WORK_ORDER_SCOPES = ["per_premise", "per_unit", "per_asset"] as const;

/** B18 §8.3's three modes.
 *
 * ⚠ **`we_schedule` IS DEFERRED AND THE SCREEN GREYS IT OUT** — `_check_mode`
 * raises `NotImplementedError("OQ-249")` for it, and `NCT-03.2` draws exactly
 * that card disabled with *"coming with the Work module"*. The stub and the
 * drawing agree without either having seen the other (B18 §5.4.10 step 1). */
export const WORK_ORDER_MODES = ["we_schedule", "our_crew", "external"] as const;
export const MODE_WE_SCHEDULE = "we_schedule";

/** `connections.py` — the five outcomes. `failed` raises a follow-up AND puts
 *  the connection on hold (task 6.6, TC-NCT-5). */
export const WORK_ORDER_OUTCOMES = [
  "passed",
  "failed",
  "partially_done",
  "cancelled",
  "waiting_on_someone_else",
  // FB-013 (PO 2026-10-28) — the step stopped on a fresh cleared balance.
  "not_done_payment_received",
] as const;

export type ConnectionState = (typeof CONNECTION_STATES)[number];
export type WorkOrderScope = (typeof WORK_ORDER_SCOPES)[number];
export type WorkOrderMode = (typeof WORK_ORDER_MODES)[number];

// ══════════════════════════════════════════════════════════════════════════
// S88 · `GET /connections/{id}` — NCT-02, the connection detail
// ══════════════════════════════════════════════════════════════════════════

/**
 * One of `NCT-02.overview`'s side-by-side service blocks:
 *
 *     ELECTRIC   Activated   1 of 1 units · Aug 18
 *     WATER      Activated   1 of 1 units
 *
 * `connections.service_progress()` builds exactly this, and its `state` comes
 * from **the same derivation the connection's own state comes from**, fed this
 * service's rows — so a service and a build cannot disagree about what "partly"
 * means. `activated_at` is null while nothing has gone live; that is an
 * absence, not a date to invent.
 */
export interface ConnectionServiceBlock {
  service: string;
  state: string;
  units_energised: number;
  units_total: number;
  activated_at: string | null;
}

/**
 * One row of `NCT-02.orders` — `ORDER · SERVICE · SCOPE · MODE · WAITS FOR ·
 * OUTCOME · STATE`.
 *
 * ⚠ **`mode` IS NOT NULLABLE AND `is_gate` IS STAMPED**, both settled against
 * an earlier inference (B18 §5.4.9 fact 1, corrected 2026-08-25). A mode
 * describes WORK, some of which is finished; inheriting it from the connection
 * would relabel a March order in April with nothing recording the move.
 *
 * ⚠ **`accepted_at` IS THE WHOLE OF BR-MET-110.** A NULL here — on an order
 * that IS complete — is the only thing in the product that says *"the field
 * sent data and no person has accepted it yet"*. That gap is the review queue.
 */
export interface ConnectionWorkOrder {
  id: string;
  order_no: string | null;
  type: string;
  service: string | null;
  scope: WorkOrderScope | string;
  unit_label: string | null;
  mode: WorkOrderMode | string;
  state: string;
  outcome: string | null;
  is_gate: boolean;
  /** `blocked_by`, rendered as `NCT-02`'s chain `WO-4905 → WO-4904 → WO-4903`. */
  blocked_by_order_no: string | null;
  external_ref: string | null;
  completed_at: string | null;
  /** BR-MET-110 — who accepted the field's data, and when. Null = not yet. */
  accepted_at: string | null;
  accepted_by: string | null;
  /** What the crew sent back. Free-shaped per BR-MET-109: a utility's own
   *  template decides what a field return contains, so this is never a fixed
   *  column set. Null = nothing has come back. */
  field_data: Record<string, unknown> | null;
}

/** One row of `NCT-02.units` — `UNIT · TYPE · SERVICES · METERS · PLAN ·
 *  OCCUPANCY · ACCOUNT`. ⚠ A new connect ENDS with units vacant, service off
 *  and no account; that is the terminal state, not an incomplete one. */
export interface ConnectionUnitRow {
  id: string;
  label: string;
  unit_type: string | null;
  services: string[];
  meters: number;
  plan: string | null;
  occupancy: string | null;
  account_no: string | null;
  /** CR-070 wave B — `characteristic()` rides here rather than on a route of
   *  its own (`07-endpoints.md` §1's closing line). An EMPTY LIST means nothing
   *  has been recorded: it does not mean the unit refuses the service and it
   *  never means zero. */
  characteristics: ConnectionCharacteristic[];
}

/** One recorded fact about a unit's relationship to a service.
 *
 *  ⚠ **`unit_of_measure` IS ITS OWN FIELD AND IS NEVER FOLDED INTO `value`** —
 *  hard rule 3, and the reason `BR-MET-108` refused a column per service. A
 *  screen joins them for display; the wire keeps them apart so that a number
 *  can be validated and migrated. */
export interface ConnectionCharacteristic {
  service: string;
  key: string;
  value: string;
  unit_of_measure: string;
}

/** One row of `NCT-02.assets`. `parent` is the sub-meter link and is null on a
 *  directly-billing meter — *"A single unit has no sub-metering."* */
export interface ConnectionAssetRow {
  id: string;
  asset_no: string;
  service: string | null;
  kind: string | null;
  unit_label: string | null;
  size: string | null;
  multiplier: string | null;
  read_method: string | null;
  parent: string | null;
  status: string | null;
}

/**
 * One line of `NCT-02.charges` / `NCT-03.7`'s quote.
 *
 * ⛔ **THE WHOLE LIST IS NULLABLE AND OQ-379 IS WHY.** Step 6 draws four coded
 * lines with quantities; `billing.one_time.OneTimeRequest` takes a single
 * `connection_charge_code` and has **no `amount`, no `description` and no
 * `lines` member**. `commit_connection` therefore records the quote as a FIGURE
 * on the connection and posts nothing, and says so in `unavailable`. A screen
 * that rendered four lines out of one total would be inventing them.
 */
export interface ConnectionChargeLine {
  code: string;
  description: string;
  /** *"per unit"* · *"per unit, 5/8\""* · *"per meter"* · *"per premise"* —
   *  §5.4.9 calls the BASIS the load-bearing part of the table. */
  basis: string;
  rate: WorklistMoney;
  quantity: number;
  total: WorklistMoney;
}

/**
 * The `Deposits` panel, badged **`Policy, not a collection`**.
 *
 * ⚠ **EVERY FIELD IS NULLABLE AND `collected` IS NOT ALLOWED TO DEFAULT TO
 * ZERO IN THE CLIENT.** The drawn `Collected now $0.00` is *"the whole design in
 * one figure"* — but it is only true when a SERVER computed it. Printing `$0.00`
 * from an absent payload would say *"we checked and took nothing"* where the
 * truth is *"nobody has told us the policy"*, and those are different sentences
 * on a screen about somebody's money (DEF-127).
 */
export interface ConnectionDepositPolicy {
  per_unit: WorklistMoney;
  /** *"per residential unit"* — the words the figure is per. */
  basis: string | null;
  /** *"None — landlord-billed"* on the common area. */
  common_area: string | null;
  collected: WorklistMoney;
  due: string | null;
}

/** An `Outstanding work` item. BR-MET-114 (PO 2026-08-25, *"human will mark
 *  everything to start with"*): STORED and human-authored, never derived —
 *  because *"Left off, **because** common area has no water service"* is a
 *  reason somebody gave and no query can reconstruct a reason.
 *  ⚠ `blocks_creation` is always `false` and there is deliberately no flag that
 *  could say otherwise. */
export interface ConnectionTodo {
  id: string;
  title: string;
  detail: string | null;
  source: string;
  blocks_creation: boolean;
}

/** One `NCT-02.history` row — `WHEN · WHO · WHAT HAPPENED`. The actor is a
 *  person, a crew, or `System`; the system line is the interesting one
 *  (*"Electric activated — gate WO-4904 passed"*). */
export interface ConnectionHistoryRow {
  at: string;
  who: string;
  what: string;
}

/**
 * `GET /connections/{id}` — everything `NCT-02`'s six tabs draw.
 *
 * ⚠ **`state` IS THE DERIVATION** (`connections.connection_state()`), not the
 * cached column, for the reason `connection_reads` §1 states: a row is where a
 * person READS a state, and a drifted cache must not put the wrong badge on it.
 *
 * ⚠ **`mode` IS NULLABLE BECAUSE A BUILD CAN BE MIXED.** `connection_mode()`
 * derives it from the orders and returns nothing when they disagree — which
 * §8.3 calls *"the normal case, not the edge"*. A screen prints "mixed", never
 * one of the two modes picked arbitrarily.
 *
 * ⚠ **`quote_settled_at` IS NULLABLE AND TRACKS DEF-678.** `NCT-03.9` says the
 * quote is *"settled before energisation"*, and `derive_connection_state()`
 * reads ORDERS ONLY. Until that lands the field is null with an absence beside
 * it; the screen must not imply a settlement it cannot see.
 */
/**
 * **`DEF-CUS-6109` — the eleven answers the application already holds.**
 *
 * PO, verbatim, on 2026-09-21: *"why youa re saying request dont have owner -
 * we take details on customer when service request is created - that mean you
 * ahve both customer details and premises details"*. `null` on a build raised
 * directly, which is ordinary — `request_id` is PROVENANCE and never a
 * dependency (`BR-MET-1178`), so a build with no application behind it fills
 * the same wizard from an empty form and commits identically.
 */
export interface ConnectionRequestPrefill {
  request_id: string;
  request_no: string | null;
  applicant_kind: string | null;
  applicant_name: string | null;
  applicant_email: string | null;
  applicant_phone: string | null;
  matched_customer_id: string | null;
  address_as_given: string | null;
  address_unit_as_given: string | null;
  plot_or_parcel: string | null;
  property_type: string | null;
  what_is_being_built: string | null;
  units_on_property: number | null;
  /** ⊕ `DEF-CUS-9074` — the services the applicant asked for, the class the
   *  clerk picked on the request, a person's date of birth, and a business's
   *  Tax ID as typed online (LAST FOUR only, `OQ-CWP-1560` (b)). Optional: a
   *  cached build may predate them. */
  service_codes?: string[];
  account_type_code?: string | null;
  date_of_birth?: string | null;
  tax_id_last4?: string | null;
  tax_id_present?: boolean;
  /** ⊕ `DEF-CUS-9828` (N2) — every other answer the request holds. Optional:
   *  a cached build may predate them. SSN and licence are LAST FOUR only. */
  address_city_as_given?: string | null;
  address_state_as_given?: string | null;
  address_postal_code_as_given?: string | null;
  /** ⊕ `DEF-CUS-9835` — the utility's own state (`TX`), for a request that
   *  gives none; `null` when the company profile holds none. */
  utility_state?: string | null;
  account_subtype_code?: string | null;
  mailing_address?: {
    line1?: string | null;
    line2?: string | null;
    city?: string | null;
    state?: string | null;
    postal_code?: string | null;
  } | null;
  account_custom_data?: Record<string, unknown>;
  customer_custom_data?: Record<string, unknown>;
  preferred_language?: string | null;
  co_applicant?: { name: string; email: string; phone: string } | null;
  ssn_last4?: string | null;
  driving_licence_last4?: string | null;
  /** The request's documents that hold a file, as its Documents tab serves
   *  them — LINKED by the build, never copied. */
  documents?: RequestPrefillDocument[];
  /** ⊕ lane CF-1 (2026-10-18) — the rest of the shared customer form. The
   *  cards carry each identifier as its LAST FOUR only; the server carries the
   *  numbers at Create. Optional: a cached build may predate them. */
  co_applicants?: ServiceRequestCoApplicant[];
  contact_by?: string | null;
  gov_id_last4?: string | null;
  paperless?: boolean;
  sms_reminders?: boolean;
}

/** One of the request's documents, as `prefill.documents` serves it. */
export interface RequestPrefillDocument {
  id: string;
  doc_type: string;
  what_it_proves: string | null;
  document_number: string | null;
  name: string | null;
  size_bytes: number | null;
  original_size_bytes: number | null;
  uploaded_at: string | null;
  uploaded_by_name: string | null;
  /** ⊕ `DEF-CUS-9834` — `applicant` for a file the portal stored. */
  uploaded_by_role?: "applicant" | null;
  file_present: boolean;
  content_type?: string | null;
  required: boolean;
  verification_state: string;
  reject_reason: string | null;
}

export interface ConnectionDetail {
  id: string;
  connection_no: string;
  state: string;
  /**
   * ⚠ **`null` WHILE A DRAFT HAS NO ADDRESS YET — `DEF-CUS-6109`.** A build
   * raised by approving an application whose address had not resolved carries
   * no premises until the wizard's last button writes one (`BR-MET-112`). The
   * whole block is withheld rather than four nulls served inside it, so a
   * screen can tell *there is no address yet* from *a property with no number*.
   */
  premises: {
    id: string;
    premise_no: string;
    name: string | null;
    address: string | null;
    /** ⊕ `DEF-CUS-10045` — the register's own town, state and ZIP, so New
     *  Connect's read-only boxes over a matched premises are not blank.
     *  Optional: a cached build may predate them. */
    city?: string | null;
    state?: string | null;
    postal_code?: string | null;
  } | null;
  prefill: ConnectionRequestPrefill | null;
  /** *"single unit · Rodriguez, M. · from request SR-26-0018"* — the header's
   *  own sub-line, served in three parts so the screen composes it. */
  unit_summary: string | null;
  applicant: string | null;
  request_no: string | null;
  mode: string | null;
  started_at: string | null;
  target_activation: string | null;
  waiting_on: string | null;
  units: number;
  orders: { done: number; total: number };
  services: ConnectionServiceBlock[];
  work_orders: ConnectionWorkOrder[];
  unit_rows: ConnectionUnitRow[];
  assets: ConnectionAssetRow[];
  sub_meter_links: number | null;
  quote_total: WorklistMoney;
  quote_settled_at: string | null;
  charges: ConnectionChargeLine[] | null;
  deposit: ConnectionDepositPolicy | null;
  outstanding: ConnectionTodo[];
  history: ConnectionHistoryRow[];
  owner_account_no: string | null;
  unavailable: WorklistAbsence[];
}

/**
 * `GET /connections/{id}`.
 *
 * ✔ **SERVED** — `connection_detail`, mounted by metering. This read *"NOT
 * SERVED TODAY … the call 404s"* until 2026-09-04, three weeks after the view
 * landed; the sentence beside it is still the right argument and is kept,
 * because it is why the screen was shipped calling a door that did not exist
 * yet rather than shipped over a fixture: *"a screen with a fixture in it looks
 * finished and is not"* (hard-won law 2). The claim was corrected, not the
 * reasoning (law 1: a comment claiming a guarantee is not the guarantee, and a
 * comment denying one long after it arrived is the same fault reversed).
 */
export async function getConnection(
  connectionId: string,
  client: ApiClient = api,
): Promise<ConnectionDetail> {
  return requireData(await client.get<ConnectionDetail>(`/connections/${connectionId}`));
}

// ══════════════════════════════════════════════════════════════════════════
// S87 · THE COMMIT — `POST /connections/{id}/commit`
// ══════════════════════════════════════════════════════════════════════════

/**
 * `connections.MANIFEST_KEYS`, **all twelve of them, in its order.**
 *
 * ⚠ `sub_meter_links` is `null` and NOT `0`: metering has no seam that writes
 * an assets relationship, and a zero would read as *"we made none"* where the
 * truth is *"we cannot make them from here"* — `commit_connection`'s own
 * sentence.
 *
 * ⚠ **THIS DECLARED SEVEN OF TWELVE UNTIL 2026-09-28 (`DEF-CUS-7681`).** It
 * had been missing `messages` and `one_time_charge_invoice_no` since
 * `CR-109` on 2026-09-16, and `one_time_charge_payment_no` and
 * `one_time_charge_paid` arrived with `BR-MET-1187` the day this was fixed.
 * **A TypeScript interface that declares fewer keys than the server sends is
 * not an error in TypeScript** — the extra keys are simply invisible to every
 * screen, `tsc` is green, every test is green, and the only symptom is a
 * value nobody can render. That is hard-won law 2 through a type instead of
 * through a prop, and it is why `newConnectManifestKeys.test.ts` now reads
 * the server's own `MANIFEST_KEYS` and fails when the two disagree.
 */
export interface CommitManifest {
  customers: number;
  premises: number;
  units: number;
  meters: number;
  sub_meter_links: number | null;
  plan_assignments: number;
  /**
   * **What the build's one-time charges came to**, as the server's own
   * 4-decimal string (hard rule 2 — nothing here rounds it).
   *
   * ⚠ **THE SENTENCE HERE READ *"recorded, posted by nothing — OQ-379"* UNTIL
   * 2026-09-28 AND IT HAD BEEN FALSE FOR TWELVE DAYS.** `OQ-379` was answered
   * on 2026-09-16: `_post_connection_quote` raises the quote as a real
   * receivable. Under `BR-MET-1187` it is stronger still — a build whose
   * charges cannot reach the books **is not created at all**. Deleted rather
   * than reworded: a stated absence that outlives its cause is a lie the
   * product tells about itself (hard-won law 1).
   */
  one_time_charges: string;
  /**
   * How many work orders the commit ACTUALLY RAISED — `DEF-MET-5428`.
   *
   * ⚠ **READ THIS RATHER THAN COUNTING THE PROPOSAL AGAIN.** Step 8 promised a
   * number and step 9 recomputed it in the browser from the same list, so the
   * two agreed by construction and neither of them was the server's answer.
   * From wave E until 2026-09-16 the server raised NONE and said nothing, and
   * the screen went on reporting nine. **A figure the server never returns
   * cannot be wrong on screen and cannot be right either.**
   */
  work_orders: number;
  /** How many messages the commit QUEUED — `DEF-MET-5428`'s lesson again, and
   *  the reason the server carries this key at all: step 8 drew *"Three
   *  messages are queued to the owner"* and the browser used to recompute it
   *  from ticks it still held. */
  messages: number;
  /** The invoice the quote was raised as — a NUMBER a clerk can look up, never
   *  a row id (B14 rule 31). `null` on every path that posted nothing; never
   *  `""`, because an absence says so. */
  one_time_charge_invoice_no: string | null;
  /** The receipt for the payment taken at the counter — `BR-MET-1187`. **A
   *  receipt number and never the payment's row id** (B14 rule 31). `null`
   *  where no payment was taken, which is the drawn default: `0` would read as
   *  *"they paid nothing"* where the truth is *"nobody was asked to"*. */
  one_time_charge_payment_no: string | null;
  /** What was actually taken, as the server's stored 4-decimal string — the
   *  same shape as `one_time_charges` beside it. `null`, never `"0"`, where no
   *  payment was taken. */
  one_time_charge_paid: string | null;
}

export interface CommitResult {
  id: string;
  connection_no: string;
  manifest: CommitManifest;
  /**
   * Where the completion screen's *Open this connection* goes — CR-070 wave O.
   *
   * `/connections/<uuid>` stopped being a destination on 2026-09-04, and the
   * answer is known the moment the row exists, so it travels WITH the commit
   * rather than being fetched afterwards: a spinner on a completion screen over
   * a fact the server already had is a round trip for nothing.
   */
  home: BuildHome | null;
  unavailable: WorklistAbsence[];
  br_ref: string;
  /**
   * Which of the two things happened to the address — `BR-MET-1024`,
   * `DEF-MET-5441`.
   *
   * `true` means this press CREATED the property; `false` means the clerk
   * named one already on file. **OPTIONAL because only the no-id door can
   * answer it**: `POST /connections/{id}/commit` is handed a draft whose
   * address was written by somebody else, and `DEF-2961` is the defect from
   * the last time a manifest reported a premises it had not made. The door
   * that did it is the door that says so.
   */
  premises_created?: boolean;
  /** The address this build stands on, whichever way it got there. */
  premises_id?: string | null;
}

/**
 * What step 8 sends. Every key from `units` down is one `commit_connection`
 * already reads out of its `plan`; the four above them are what the wizard
 * collects in steps 1–3 and **had nowhere to put until the commit door
 * existed** (`DEF-MET-5441`, 2026-09-16).
 *
 * ⚠ **THE `premises` AND `mode` KEYS ARE HERE BECAUSE OF A REAL TENSION
 * BETWEEN A RULE AND A SIGNATURE — AND THE SERVER HAS NOW RESOLVED IT.**
 * `BR-MET-112` is *"nothing is written until step 8"* — so at step 8 there is
 * no connection row and, on the `new_premise` scope, **no premises row either**.
 * But `create_connection(actor, payload)` REQUIRES an existing `premises_id`
 * (it refuses `premises_required` without one) and `commit_connection(actor,
 * connection_id, plan)` requires a `Draft` connection that already exists. So
 * the two functions between them assume rows the ruling says do not exist yet,
 * and `commit_connection`'s manifest reports `premises: 1` for a premises it
 * never created.
 *
 * **This screen does not choose a way out of that, and it no longer has to.**
 * It sends ONE payload to ONE door, which is what BR-SHL-019 (*"exactly one
 * transactional commit"*) and BR-MET-112 together describe, and the
 * orchestration behind that door is now written: `commit_new_connect` creates
 * the premises where the scope needs one, allocates the connection and runs
 * `commit_connection`, all in one transaction. A frontend that fired three
 * sequential POSTs would be inventing a half-committed state the rules forbid.
 *
 * ⚠ **FOUR OF THESE KEYS ARE SPELLED DIFFERENTLY ON THE SERVER AND THE DOOR
 * TRANSLATES THEM** — `address` → `address_line`, `premise_type` →
 * `premises_type`, `read_route` → `route`, and `parcel_ref` → `external_ref`,
 * which is where a premises' parcel key already lives (`BR-INT-048`). A key
 * added here that the door does not know is REFUSED BY NAME rather than
 * dropped, which is `DEF-MET-4715`'s lesson.
 *
 * ⚠ **`scope` AND `units_prefix` ARE SENT AND READ BY NOTHING** (`DEF-CUS-5435`
 * — `connections` has no column for either). The commit says so on
 * `unavailable` rather than dropping them in silence.
 */
export interface CommitPlan {
  /** Step 2. Sent whole because on the `new_premise` scope it does not exist
   *  yet; on the other two scopes `id` names the one that does. */
  premises: {
    id: string | null;
    /** `premises.name` — the building's own name (`DEF-CUS-5468`). A warehouse
     *  or a campus has one; a house does not, and NULL says so. */
    name: string | null;
    address: string;
    /**
     * **The town, and it is three fields rather than one box (`DEF-CUS-5468`).**
     *
     * ⚠ **`_validate_premises` HAS ACCEPTED ALL THREE SINCE `US-MET-001` AND
     * THIS DOOR'S TRANSLATION TABLE CARRIED NONE OF THEM (`DEF-MET-5469`).**
     * `PREMISES_BLOCK_FIELDS` named five keys and refused every other one BY
     * NAME, so a screen that collected a city would have had its whole commit
     * refused — which is why the field was absent rather than broken, and why
     * nothing ever went red over it. Every property this wizard built held
     * NULL for all three, and `accountDetailHeader`'s `Austin, TX 78704` line
     * walks to the premises for them, so it was blank forever.
     */
    city: string | null;
    state: string | null;
    postal_code: string | null;
    premise_type: string | null;
    parcel_ref: string | null;
    read_route: string | null;
    /** `CR-161-BRC10` W3 — the new property's own field answers. */
    custom_data?: Record<string, unknown>;
    /**
     * **What this address offers — step 4's own ticks (`DEF-MET-5465`).**
     *
     * ⚠ **IT WAS COLLECTED AND DISCARDED, AND WITHOUT IT NO BUILD COULD EVER
     * FIT A METER.** `BR-MET-003`'s inner bound (`DEF-772`, PO verbatim:
     * *"Refuse it; if they want that servcie then they ahve to provision it on
     * that unit or premise first"*) refuses a meter for a service the PREMISES
     * does not list, and a property created without this arrives with
     * `services_available` NULL — which reads as *"nobody has been asked"* and
     * refuses everything. A clerk ticked Electric and Water at step 4 and the
     * commit answered 422 about the services at step 4.
     *
     * NULL where the clerk named an address already on file: this door creates
     * no property then, and a premises' service list is not the wizard's to
     * rewrite on the way past.
     */
    services_available: string[] | null;
  };
  /** Step 1. `we_schedule` is never sent — the card is disabled (OQ-249). */
  mode: WorkOrderMode | string;
  /**
   * Step 1's **Scope** — `new_premise` · `multi_unit` · `common_area_only`.
   *
   * ⚠ **IT DECIDED THE SHAPE OF EVERY OTHER MEMBER OF THIS PAYLOAD AND WAS
   * NEVER SENT** (`DEF-CUS-5435`). How many units the pattern makes, whether a
   * common area exists, whether the premises is new or named — all downstream
   * of this one answer, and the server received the consequences without the
   * choice. **`connections` has no column for it**, so this is the contract
   * asking for one rather than a field the server reads today.
   */
  scope: string;
  /**
   * Step 1's **Prefix** — `BAL`, the word that names this build's units.
   *
   * ⚠ **ITS EFFECT ALREADY TRAVELLED AND THE VALUE DID NOT.**
   * `expandUnitPattern` builds `Apt 1 … Apt 26`, so `units[].label` carries the
   * prefix twenty-six times over and the build lands with no record of what it
   * WAS. Sending it once means a unit added to the same building next year can
   * be named the same way without a person re-reading a label and guessing.
   * NULL when the clerk left it blank, because "" and "no prefix" are one fact.
   */
  units_prefix: string | null;
  target_activation: string | null;
  service_request_id: string | null;
  /**
   * **`DEF-CUS-6109` — the DRAFT this press finishes, where one was raised for
   * it.** `null` on a build a clerk started directly, and that path is
   * untouched: `commit_new_connect` creates the row and the address together
   * exactly as it did.
   *
   * ⚠ **IT IS A BUILD ID AND NEVER AN APPLICATION ID.** Approving an
   * application raises the build (PO ruling 2026-09-21) and hands the clerk
   * this wizard; from here on the build is the subject and the application is
   * provenance on it (`BR-MET-1178`). Sending the application instead would be
   * the dependency that ruling removed.
   */
  connection_id: string | null;
  /**
   * **`BR-SHL-048 (d)` — the parked draft this press was typed into.**
   *
   * PO ruling 2026-09-21: *"this is big problem - we cannot create two build -
   * you can update the existing build"*. The draft was only ever HOLDING the
   * typing, so once the build is committed it holds nothing; leaving the row
   * behind draws a second line on the New connects tab for one piece of work.
   * The server discards it inside the commit's own transaction, so a refusal
   * leaves the clerk's typing exactly where it was.
   *
   * `null` whenever the wizard was not resumed from a park, which is most
   * presses. A draft already discarded is not an error and never refuses the
   * build.
   */
  wizard_park_id: string | null;
  /**
   * **`DEF-CUS-8021` — the submit token CLAUDE.md hard rule 6 keys this press
   * on.** Minted ONCE per build by `NewConnectWizard` and sent unchanged by
   * every press of *Create connection*, so the second press returns the first
   * press's answer instead of building a second connection, a second account,
   * a second customer, a second property and a second $250.00 payment.
   *
   * The server folds it into `"new-connect|<token>"`
   * (`core.idempotency.new_connect_commit_key`) against
   * `UNIQUE (tenant_id, commit_key)` on `connections`. `null` is a caller that
   * has no build identity to offer — a test, a seeder — and the server reports
   * that absence rather than pretending the guarantee holds.
   */
  commit_token: string | null;
  units: { label: string; is_common_area: boolean }[];
  /** ⊕ `DEF-MET-9221` — `size_class` is the size step 3 shows on the
   *  meter's row (*Water 1"*), absent when the row holds none. */
  meters: { unit_label: string; service: string; asset_no: string | null; size_class?: string }[];
  /** `DEF-MET-6119` — every taken service a METER does not carry (sewer,
   *  trash, fire, storm water, broadband, thermal) and the sized equipment of
   *  the capacity ones (solar panels, batteries), one row per unit × service.
   *  `equipment` is what the bill COUNTS or SUMS (`BR-RAT-090`): a device type
   *  and its ratified size, created numbered and not installed. */
  unit_services: {
    unit_label: string;
    service: string;
    equipment: { type: string; size_class: string; count: number }[];
    /** ⊕ `DEF-MET-9222` — storm water's class and thermal's tonnage: the size
     *  step 3 shows on the row, for the two services whose capacity is a UNIT
     *  fact (`connections.UNIT_CAPACITY_CHARACTERISTIC`). Absent when none. */
    size_class?: string;
  }[];
  plan_assignments: { unit_label: string; tariff_id: string | null }[];
  create_owner_account: boolean;
  owner: Record<string, unknown>;
  /** Step 6's total as a STRING. Never a number: money is 4-dp text end to end
   *  and a float here is the bug hard rule 2 forbids. */
  quote_total: string | null;
  /** Step 8's four-way radio. `vacant_service_off` is the drawn default. */
  occupancy: string;
  /**
   * CR-070 wave E (`US-WRK-017`) — the work orders step 6 proposed and the
   * clerk left standing, each with the template VERSION it is raised from.
   *
   * ⚠ **THE VERSION TRAVELS BECAUSE OF `BR-WRK-008` — *copy, never link*.** An
   * order takes its own copies of the template's rows when it is raised, and
   * the version number is what says WHICH copy; publishing v2 afterwards
   * leaves the order reading v1, which is the whole demonstration on
   * `Work-022`'s Versions tab.
   *
   * ✔ **THE SERVER READS THIS NOW, AND SO DOES THE DOOR IT POSTS TO.** This read
   * *"THE SERVER DOES NOT READ THIS YET AND NEITHER DID IT READ THE REST …
   * today step 8 has nowhere to write to"*. `DEF-MET-5428` closed the first
   * half on 2026-09-16 and `DEF-MET-5441` closed the second the same day: the
   * orders are raised inside the build's own transaction, and the count comes
   * back on the manifest so the screen reads the server's answer rather than
   * its own proposal a second time.
   */
  work_orders: {
    template_id: string;
    template_version: number;
    /** ⊕ `DEF-MET-9223` — the unit the clerk put the job on; absent = the
     *  whole build. */
    unit_label?: string;
    /** ⊕ `DEF-MET-9223` — the service point's service, where the job is one. */
    service?: string;
  }[];
  /**
   * Step 6 · *Who is billed* — `owner_account` · `each_unit_first_bill` ·
   * `connection`, read by `metering.connections._quote_payer`.
   *
   * The last two are REFUSED there with their real reasons: the unit accounts
   * do not exist at commit and dividing a quote across them is money arithmetic
   * no signed document contains, and a charge on a build is a debt owed by
   * nobody. The screen refuses them too rather than sending a choice the server
   * will decline.
   */
  quote_payer: "owner_account" | "each_unit_first_bill" | "connection";
  /**
   * Step 6 · payment terms in days, read as `quote_due_days`.
   *
   * ⚠ **SENT FOR THE FIRST TIME (`DEF-CUS-5485`).** Absent, the server reports
   * `quote_payment_terms_not_captured` and raises NO charge, which is what
   * every commit this product has ever made did. `null` is lawful and is not a
   * zero: `BR-BIL-024` derives a due date from a cycle's days and a build's
   * bill has no cycle, so the PO ruled on 2026-08-23 that a clerk captures the
   * terms and nobody guesses them.
   */
  quote_due_days: number | null;
  /** Step 6 · *Posting date* — the day the charge counts from. An EVENT date,
   *  never a clock (`BR-TEN-043`, `G6`). `null` lets the server use the day of
   *  the commit, which is its own documented fallback. */
  quote_posting_date: string | null;
  /**
   * Step 6 · **THE BUILD'S OWN CHARGE LINES — `BR-MET-1178`, PO ruling
   * 2026-09-21.** Verbatim: *"…this request is new work and recognized
   * seperately from applcaition and hence we should not make it dependent on
   * applciation #"*.
   *
   * ⚠ **READ ONLY WHEN THE BUILD HAS NO APPLICATION.** A build that came from
   * an approved request still takes that request's quote — the ruling removes
   * a REQUIREMENT, not a source — so these lines are the second source and not
   * an override.
   *
   * ⚠ **A COUNT, NEVER A FIGURE.** There is deliberately no amount field:
   * billing reads the price off the tenant's own charge row and multiplies
   * (`BR-BIL-007`, `BR-BIL-020`), and `CLAUDE.md` hard rule 2 rounds once, on
   * the server.
   *
   * ⚠ **`basis` IS SPELLED WITH SPACES BECAUSE THAT IS WHAT BILLING KEYS ON**
   * (`fee_bill.BASIS_UNITS`: `"per unit"` · `"per meter"` · `"per premise"`).
   * An underscored spelling is refused, by name, at the metering door.
   */
  quote_lines: { charge_code: string; quantity: number; basis: string }[];
  // ── `BR-MET-1187` · THE PAYMENT TAKEN AT THE COUNTER ────────────────────
  //
  // `connections.PAYMENT_FIELDS`, whose own note says why each is spelled the
  // way it is. **Every one is optional** — the drawn default is *No payment
  // now*, a build committed with an invoice and no receipt — so each is
  // declared optional here and `paymentTakenOf` sends the block or nothing.
  /**
   * **A TENANT METHOD CODE, NEVER A DRAWN LABEL** (`BR-PAY-026`).
   *
   * The drawing's *Cheque* is the code `check` and its *Bank transfer* is
   * `ach` or `wire`. The screen offers `GET /payments` `methods[]` and never a
   * list typed into a file: a hand-typed catalogue fails SILENTLY the day the
   * tenant adds or retires one, which is `SignupWizard`'s eleventh service in
   * CLAUDE.md. A code this tenant does not have is refused at the payments
   * door and reaches the clerk on the charges step.
   */
  payment_method?: string | null;
  /** **THE CLERK'S OWN STRING, UNPARSED.** A float is refused rather than
   *  converted — `Decimal(str(...))` on the wire's number is the only lossless
   *  reading the server has — and nothing in the browser sums, multiplies or
   *  rounds it (hard rule 2). */
  payment_amount?: string | null;
  /** The day the payment COUNTS FROM — the posting date the charges step
   *  already collects. Absent, the server falls back to that same date
   *  (`BR-TEN-043`, `G6`): they are one event. */
  payment_date?: string | null;
  // ⛔ NO `payment_cleared_date` (DEF-CUS-10324, CR-186-BRC10): the payment is
  // `posted` at entry and only bank reconciliation clears it.
  /** The cheque or confirmation number, as typed. `null` rather than `""` —
   *  `payments.confirmation` is nullable and a blank string reads as *"the
   *  cheque had no number"* where the truth is *"nobody typed one"*. */
  payment_reference?: string | null;
  /** The clerk's note. **No box on the charges step collects one**, so
   *  `paymentTakenOf` never sends it; the key is declared because the server
   *  takes it and the day the drawing asks for a memo the type is ready. */
  payment_memo?: string | null;
  /** DEF-PAY-9263 · BR-PAY-1199 — the clerk's *Record anyway* after step 4's
   *  card or ACH payment was answered "Looks like a duplicate". Sent only
   *  then; the server reads only a literal `true`. */
  payment_duplicate_confirmed?: boolean;
  /**
   * **STEP 5's MESSAGES TABLE — `step5-review.png`, `CR-150-BRC09` task 13.**
   *
   * ⚠ **THE SERVER HAS TAKEN THIS SINCE THE MESSAGES WERE BUILT AND THE
   * WIZARD SENT NOTHING.** `commit_connection` passes `data["messages"]`
   * straight into `connection_messages.queue_on_commit`, whose own signature
   * is `choices: {send, templates}` and whose docstring calls it *"step 7's
   * slice of the commit payload — the clerk's ticks and their template
   * picks"*. **There was no such slice**, so the step drew three ticks it
   * rendered DISABLED, correctly reasoning that nothing a clerk chose could
   * travel. The door was open the whole time; the wire was the missing half.
   * That is hard-won law 2 — an engine nothing passes anything to is not a
   * feature.
   *
   * ⚠ **`send` CARRIES ONLY WHAT THE CLERK TOOK OFF**, and an absent code
   * means the occasion's own `send_by_default`. `_fire_one` reads it exactly
   * that way — *"A clerk in front of the build outranks a default"* — and
   * records `not_asked` / `clerk_unticked` rather than skipping silently,
   * because *we did not send it* and *they asked us not to* are different
   * facts.
   *
   * ⚠ **IT DOES NOT MAKE ANYTHING GO OUT.** `OQ-376` is open — the platform
   * has no `connection` source kind — so every occasion is still refused BY
   * NAME and the queue still holds zero rows. What this changes is that the
   * clerk's choice is RECORDED against the build instead of discarded in a
   * browser, which is a real act with a real audit row.
   */
  messages?: {
    send?: Record<string, boolean>;
    templates?: Record<string, string>;
  };
}

/**
 * Step 8's one transactional commit — BR-MET-112, *"nothing is written until
 * step 8"*, and BR-SHL-019's single-flight rule on the frame above it.
 *
 * ✔ **SERVED SINCE 2026-09-16 (`DEF-MET-5441`).** This comment read *"STILL NOT
 * SERVED"* until then and it was telling the truth: `POST /connections/commit`
 * answered **404** on the running server, so **no build made through this
 * wizard had ever reached the database** — eight finished steps behind a button
 * that went nowhere. It is now `metering.api.connection_commit_new` over
 * `connections.commit_new_connect`, which creates the address (`BR-MET-1024`),
 * allocates the draft and runs the whole commit **inside one transaction**.
 *
 * ⚠ **THE GAP LIVED IN THIS COMMENT AND ON NO REGISTER, WHICH IS WHY IT
 * SURVIVED.** Hard-won law 1: *a comment claiming a gap is not a plan*. Nothing
 * counted it, no burndown showed it, and both halves stayed green — this
 * module is MOCKED by the front-end suite and the backend suite calls
 * `commit_connection` directly with an id the browser never has.
 * `06-backend/tests/test_def_met_5441_the_commit_door.py` resolves this exact
 * address against the mounted urlpatterns, which is the one question nobody
 * was asking.
 */
// ══════════════════════════════════════════════════════════════════════════
// 6.13a · WHAT THIS BUILD WILL COST — `POST /connections/quote-preview`
// ══════════════════════════════════════════════════════════════════════════

/** CLAUDE.md hard rule 2's two shapes, as the server states them: `stored` is
 *  the 4-decimal string that would be written and `display` is the 2-decimal
 *  string the SERVER rounded, once. A client that re-rounded `stored` would be
 *  the second rounding path `DEF-088` removed, so nothing here does arithmetic
 *  of any kind. `{null, null}` is an absence and is never drawn as `$0.00`. */
export interface QuoteMoney {
  stored: string | null;
  display: string | null;
}

export interface QuotePreviewLine {
  charge_code: string;
  /** The charge's own name, as billing resolved it. B14 rule 31 — no uuid. */
  description: string;
  basis: string | null;
  /** A COUNT, as a string. Not money, and not a number to multiply with. */
  quantity: string | null;
  /** `unit` · `meter` · `premise` — hard rule 3, a quantity with its unit. */
  unit: string | null;
  unit_price: QuoteMoney;
  amount: QuoteMoney;
}

/**
 * **WHAT STEP 6 COSTS, PRICED BY THE SERVER, WRITTEN NOWHERE.**
 *
 * ⚠ **IT EXISTS BECAUSE A MONEY SCREEN SHOWED NO MONEY (`DEF-CUS-6115`).**
 * Step 6 counted quantities correctly and printed no unit price, no line total
 * and no total, so the CR-126 §9 acceptance walk committed six builds **without
 * the clerk ever seeing a figure** — and the commit then raised `7 x $45.00 =
 * $315.00`.
 *
 * ⚠ **`priced: false` IS NOT `$0.00`.** A build nobody has charged, a billing
 * module that publishes no door, and a charge code the catalogue cannot price
 * are three different absences with three different codes, and every figure
 * comes back `{null, null}` for all of them. A zero on a money line reads as
 * *free*; the truth is *not priced*. That is already the law on the build
 * record's own tiles and this matches it.
 */
export interface QuotePreview {
  priced: boolean;
  /** The TENANT's `CHAR(3)`, or `null` where it could not be read. Never
   *  invented on the client: money travels with its currency (hard rule 2). */
  currency: string | null;
  lines: QuotePreviewLine[];
  total: QuoteMoney;
  unavailable: { field: string; code: string; tracks: string; detail?: string }[];
}

/** The refusal code the server sends when a code a clerk PICKED cannot be
 *  priced (`DEF-MET-6110` — `TAP`, `IMPACT` and `DAMAGE` carry no amount, and
 *  picking one used to cost the whole build a 500 after eight steps). */
export const QUOTE_LINE_CANNOT_BE_PRICED = "quote_line_cannot_be_priced";

/**
 * Ask the pricing engine what the commit will raise — **before the commit.**
 *
 * ⚠ **IT SENDS `CommitPlan["quote_lines"]` UNCHANGED, AND THAT IS THE WHOLE
 * DESIGN.** The same shape, read by the same server-side check, priced by the
 * same `charge_code_line` the commit prices with. A preview assembled any other
 * way would be a screen showing a figure the commit will not raise, which is
 * `DEF-MET-5428` on a money path.
 */
export async function previewConnectionQuote(
  quoteLines: CommitPlan["quote_lines"],
  client: ApiClient = api,
): Promise<QuotePreview> {
  return requireData(
    await client.post<QuotePreview>("/connections/quote-preview", {
      quote_lines: quoteLines,
    }),
  );
}

export async function commitNewConnect(
  plan: CommitPlan,
  client: ApiClient = api,
): Promise<CommitResult> {
  return requireData(await client.post<CommitResult>("/connections/commit", plan));
}

// ══════════════════════════════════════════════════════════════════════════
// 6.14 · THE ACCEPTANCE — `POST /work-orders/{id}/accept`
// ══════════════════════════════════════════════════════════════════════════

/**
 * What `accept_field_result` returns — and `communication` is the half that
 * matters.
 *
 * **BR-MET-115 (PO 2026-08-25, closing OQ-372):** *"When Utility user mark it
 * as complete using button on screen"*. The system never ranks a build's
 * orders; **a person presses a button and that press IS the send.**
 *
 * ⚠ **`queued` CAN BE `false` WITH A REASON, AND THE SCREEN MUST SAY SO.**
 * `notifications.queue_document` takes its `source_type` from a platform
 * CONSTANT — `invoice · payment · notice · plan · report · ledger · test ·
 * bulk_action` — and `connection` is not in it (**OQ-376, OPEN**). So the
 * trigger is ruled, built, and refused at the queue today. A screen that
 * reported *"customer notified"* over that refusal would be the exact defect
 * `queue_document`'s docstring was written against.
 */
export interface WorkOrderAcceptResult {
  id: string;
  accepted_at: string;
  /**
   * ⚠ **NULLABLE, AND IT SAID `string` UNTIL CR-070 WAVE L's LEFTOVERS.**
   * `accept_field_result` re-derives a build's state only when there IS a
   * build: *"an order with no connection re-derives nothing, and `None` is the
   * answer rather than a guess"* (`DEF-WRK-3635`). A one-off leak
   * investigation therefore answers `null` here, and a type promising a string
   * is a type that would have let a screen print the word `null` at a clerk.
   */
  connection_state: string | null;
  communication: {
    queued: boolean;
    already_sent?: boolean;
    /**
     * ⚠ **TRUE WHEN THE JOB HAS NO BUILD, AND THIS FIELD WAS MISSING FROM THE
     * TYPE.** `dispatch_communication` returns before it ever reaches the
     * queue when `order.connection_id is None` — *"a leak investigation on a
     * meter that has been in the ground for years has no such moment"*
     * (`DEF-WRK-3635`). That is a DIFFERENT answer from the queue's refusal
     * below and a screen that conflates the two tells a supervisor the
     * platform is broken when the job simply had no new connection on it.
     */
    no_connection?: boolean;
    reason?: string;
    /**
     * ⛔ **THE PLATFORM'S OWN WORDS, AND THEY ARE NOT CLERK COPY.** The queue
     * refuses an unknown source kind with a paragraph that names the
     * `SOURCE_TYPES` constant and its whole vocabulary — written for whoever
     * reads a log, and B14 rule 32 forbids an internal code in clerk-facing
     * copy. **So a screen reads the SHAPE of this answer and renders its own
     * sentence; it never prints this string.**
     */
    unavailable?: string;
    tracks?: string;
    br_ref?: string;
  };
  br_ref: string;
}

/**
 * *"Mark complete"* — one press, three consequences (BR-MET-110): the field's
 * data is accepted, the service goes live, and the customer is told.
 *
 * ✔ **SERVED.** `POST /work-orders/{id}/accept` is mounted by metering and has
 * been since CR-030 W6; this docstring said *"NOT SERVED TODAY"* until
 * 2026-09-04, which was the comment and not the product (hard-won law 1). It is
 * the door the Awaiting-approval queue's drawer presses too — one acceptance,
 * one place, whichever screen a supervisor reached it from.
 */
export async function acceptWorkOrder(
  workOrderId: string,
  client: ApiClient = api,
): Promise<WorkOrderAcceptResult> {
  return requireData(
    await client.post<WorkOrderAcceptResult>(`/work-orders/${workOrderId}/accept`, {}),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE B · THE ACTION ROW'S DOORS (US-WRK-002)
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THE E1 EXCEPTION IN THIS FILE'S TRAILER IS NOW HALF FALSE, AND THAT IS
// THE POINT OF THE WAVE.** It read *"NONE OF THESE ROUTES IS MOUNTED"* —
// written honestly on 2026-08-25, when this module wrapped write paths the
// server did not serve so that a type could be diffed against them. Since
// CR-070 wave B the thirteen connection writers and the raise ARE mounted, and
// each function below calls a route that exists. The trailer says which half
// still stands (`POST /connections/commit`, the wizard's own door).
//
// Every one is a POST with a small body and no computation on this side: the
// screen sends what the clerk typed, the service applies the rule, and the
// answer carries the RE-DERIVED state so the header never has to guess.

/** What every one of these doors answers with: the id and the state the build
 *  is in AFTER the act, derived server-side. */
export interface ConnectionActResult {
  id: string;
  state: string;
  waiting_on?: string | null;
}

/** *Hold…* — `BR-MET-104`. The reason is REQUIRED: an unattributed hold is half
 *  a hold, and the reason is what the WAITING ON column then carries. */
export async function holdConnection(
  connectionId: string,
  reason: string,
  client: ApiClient = api,
): Promise<ConnectionActResult> {
  return requireData(
    await client.post<ConnectionActResult>(`/connections/${connectionId}/hold`, { reason }),
  );
}

/** *Release…* — the state goes back to whatever the SERVICES say it is.
 *
 *  `waitingOn` is passed rather than assumed: a build can come off hold and
 *  still be waiting for materials. `null` clears it, which is the usual case
 *  and is still stated rather than defaulted. */
export async function releaseConnection(
  connectionId: string,
  waitingOn: string | null,
  client: ApiClient = api,
): Promise<ConnectionActResult> {
  return requireData(
    await client.post<ConnectionActResult>(`/connections/${connectionId}/release`, {
      waiting_on: waitingOn,
    }),
  );
}

/** *Cancel…* — the destructive one (B14 rule 6's danger tier). Every other door
 *  on the build refuses afterwards. */
export async function cancelConnection(
  connectionId: string,
  reason: string,
  client: ApiClient = api,
): Promise<ConnectionActResult> {
  return requireData(
    await client.post<ConnectionActResult>(`/connections/${connectionId}/cancel`, { reason }),
  );
}

/** *Waiting on…* — on a build that is NOT held. Two independent axes. */
export async function setWaitingOn(
  connectionId: string,
  waitingOn: string | null,
  client: ApiClient = api,
): Promise<ConnectionActResult> {
  return requireData(
    await client.post<ConnectionActResult>(`/connections/${connectionId}/waiting-on`, {
      waiting_on: waitingOn,
    }),
  );
}

/** *Add service* — one service, at one unit or at the premise (step 4's door). */
export async function addConnectionService(
  connectionId: string,
  body: { service: string; unit_id?: string | null },
  client: ApiClient = api,
): Promise<{ id: string; service: string; state: string; created: boolean }> {
  return requireData(await client.post(`/connections/${connectionId}/services`, body));
}

/** *Mark outstanding work* — `BR-MET-114`. A person writes it; it NEVER blocks. */
export async function markOutstandingWork(
  connectionId: string,
  body: { title: string; detail?: string | null },
  client: ApiClient = api,
): Promise<ConnectionTodo> {
  return requireData(await client.post(`/connections/${connectionId}/outstanding-work`, body));
}

/** *Close* on a to-do — and **only a person may**, which the server enforces by
 *  refusing without a named user (`BR-MET-114`'s other half). */
export async function closeOutstandingWork(
  connectionId: string,
  todoId: string,
  client: ApiClient = api,
): Promise<{ id: string; closed_at: string; already_closed: boolean }> {
  return requireData(
    await client.post(`/connections/${connectionId}/outstanding-work/${todoId}/close`, {}),
  );
}

/** *Raise order* — `POST /work-orders`, the ONE raise every door in the product
 *  uses (`07-endpoints.md` §1 row 14). `BR-MET-109`: this adds ONE, and a clerk
 *  may add as many as they want — the system never decides the grouping. */
export async function raiseWorkOrder(
  body: {
    connection_id?: string | null;
    premises_id?: string | null;
    account_id?: string | null;
    asset_id?: string | null;
    type: string;
    service?: string | null;
    scope?: string | null;
    unit_id?: string | null;
    mode?: string | null;
    /** A PUBLISHED template — the order takes its own copy (`BR-WRK-008`). */
    template_id?: string | null;
    /** `YYYY-MM-DD` — the target the clerk promised (`BR-WRK-018` override). */
    due_at?: string | null;
  },
  client: ApiClient = api,
): Promise<{ id: string; order_no: string | null; connection_id: string | null }> {
  return requireData(await client.post("/work-orders", body));
}

/** The query key both screens page on. Exported so a test names the same key
 *  the component does rather than a copy of it. */
export function connectionDetailQueryKey(connectionId: string): readonly unknown[] {
  return ["connection", connectionId];
}

// ══════════════════════════════════════════════════════════════════════════
// THE PICKER'S ROWS — a READ, and it takes no connection id
// ══════════════════════════════════════════════════════════════════════════

/**
 * One variant of one of step 7's three classes, as `GET /connections/
 * message-templates` lists it.
 *
 * ⚠ **`template_id` IS DELIBERATELY NOT IN THIS TYPE.** B14 rule 31 — no
 * database id is ever the visible value of a field — and this screen picks
 * nothing, so it has no use for one. The key a row needs is its own columns.
 */
export interface ConnectTemplateRow {
  code: string;
  /** The tenant-facing name — *Connection quote* — never the code. */
  name: string;
  group: string;
  channel: string;
  /** The drawn `VARIANT` column is this pair, rendered in the reader's own
   *  language by the catalogue (B14 rule 35). */
  category: string;
  language: string;
  version: number;
  status: string;
  pickable: boolean;
}

export interface ConnectTemplateChoices {
  rows: ConnectTemplateRow[];
  unavailable: { field: string; code: string; detail: string }[];
}

/**
 * Step 7's picker rows. **A READ, and it takes no connection id** — `BR-MET-112`
 * means seven steps run before anything is written, so there is no build to
 * hang it on.
 *
 * ⚠ **IT WAS FIRST WRITTEN BESIDE THE STEP THAT RENDERS IT, AND `G93` REFUSED
 * THAT — CORRECTLY.** Five lanes share this file and colocating looked like the
 * safer trade (law 11's mechanism two is the second lane to commit reverting the
 * first). But `G93` exempts `*Endpoints.ts` **as a class** and says why in its
 * own docstring: *"a file that is not an endpoints module and writes that path
 * is either navigating or has put an API call somewhere it does not belong"*.
 * An API path in a screen file is indistinguishable, to that gate, from a link
 * to the retired `/connections/<id>` destination — so the shared-file risk is
 * handled by `push_paths.sh`, which is what it is for, rather than by hiding a
 * path where a gate cannot read it.
 */
export async function getConnectTemplates(
  search: string,
  client: ApiClient = api,
): Promise<ConnectTemplateChoices> {
  const response = await client.get<ConnectTemplateChoices>(
    "/connections/message-templates",
    search.trim() === "" ? undefined : { query: { search: search.trim() } },
  );
  return response.data ?? { rows: [], unavailable: [] };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W6 tasks 6.11 · 6.13 · 6.14 · B18 §5.4.6 (the endpoint table) ·
//         §5.4.9 · §5.4.10 · BR-MET-110 · BR-MET-112 · BR-MET-113 ·
//         BR-MET-114 · BR-MET-115 · OQ-376 · OQ-379
// generated: 2026-08-25 by lane W6-SCREENS
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E1 ✔ **RESOLVED 2026-09-04 (CR-070 wave B, US-WRK-002).** This read
//      *"NONE OF THESE ROUTES IS MOUNTED — `apps/metering/api.py` serves `GET
//      /connections` and nothing else on this resource, while `connections.py`
//      holds every write path behind it."* True when written on 2026-08-25 and
//      false since wave B: the thirteen connection writers and `POST
//      /work-orders` are mounted and each function above calls a route that
//      exists. Corrected here rather than left standing, because a stale
//      exception is the comment hard-won law 1 is about — the next lane reads
//      it as a live constraint and builds around a hole that has been filled.
//   E2 ✔ **RESOLVED 2026-09-16 (`DEF-MET-5441`).** This read *"`POST
//      /connections/commit` IS STILL UNSERVED"*, and it was true: the address
//      answered 404 while the two beside it answered 401, so no build made
//      through this wizard had ever reached the database. `commit_new_connect`
//      now creates the address, allocates the draft and commits the build in
//      ONE transaction. Corrected here rather than left standing, for the same
//      reason E1 was: a stale exception is read as a live constraint and the
//      next lane builds around a hole that has been filled.
//   E3 ✔ **RESOLVED 2026-09-16, and it was the design question rather than a
//      gap.** `commitNewConnect` still posts with NO id in the path — that is
//      `BR-MET-112`, not a preference — and the orchestration is now written
//      where this comment always said it belonged: on the server, in one
//      transaction. Two round trips were considered and refused, because a
//      refusal on the second leaves a Draft connection and possibly a new
//      address that no screen in this product can find. The reasoning is in
//      the decision log of 2026-09-16.
//   E3 `charges`, `deposit`, `sub_meter_links` and `quote_settled_at` are all
//      nullable and each has a REASON in its own docstring. None is defaulted.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
