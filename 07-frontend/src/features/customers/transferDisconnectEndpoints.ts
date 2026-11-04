// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 — the TRANSPORT half of `TRF-02.1`…`TRF-02.5` (B18
//           §5.7.7) and `DSC-02.1`…`DSC-02.5` (B18 §5.8.7).
//           `worklistEndpoints.ts` holds the two LIST reads (`GET /transfers`,
//           `GET /disconnects`) and is another lane's file; this one holds what
//           the two WIZARDS need, so two lanes are not editing one module.
// Rules:    BR-SHL-019 (ONE transactional commit per wizard) · BR-SHL-025 ·
//           BR-CUS-103/104/105 (the cut's money rules, PO 2026-08-25) ·
//           BR-BIL-007 (the reconnection fee is the tenant's own `CC-RECON`
//           charge code and is NEVER a literal) · CLAUDE.md hard rule 2 (money
//           4 dp stored / 2 dp displayed — every money field below is the
//           server's own pair and every one of them is NULLABLE) ·
//           B14 rule 21 (this file declares no class)
// Questions: OQ-374 · OQ-382 · OQ-383 · OQ-384 · OQ-385 — all OPEN
// Tests:    TransferWizard.test.tsx · DisconnectWizard.test.tsx
// Impacts:  ⛔ **06-backend/apps/customers/api.py SERVES NONE OF THIS** — see
//           the block below. REPORTED to the coordinator; this lane does not
//           own `api.py`, `transfers.py` or `disconnects.py`.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ⛔ READ THIS FIRST — NOT ONE OF THE DOORS BELOW IS MOUNTED
//    (hard-won law 1: a comment claiming a guarantee is not the guarantee)
// ══════════════════════════════════════════════════════════════════════════
// Measured on the tree, 2026-08-25. `apps/customers/api.py`'s `urlpatterns`
// holds exactly two paths on these two resources:
//
//     path("transfers",   transfers_list)     # GET, the S89 list
//     path("disconnects", disconnects_list)   # GET, the S90 list
//
// and nothing else. Meanwhile `transfers.py` holds `start_transfer`,
// `set_target_unit`, `set_dates`, `money_statement`, `elect_money`, `review`,
// `commit_transfer` and `cancel_transfer`, and `disconnects.py` holds
// `open_case`, `advance`, `record_notice`, `record_proof_of_service`,
// `protection_check`, `reconnection_terms`, `schedule_cut`, `commit_cut`,
// `mark_reconnecting` and `restore_service` — **every one of them reachable
// only from Python.**
//
// So both wizards are, until that lands, hard-won law 2 read from the other
// end: a complete engine with nothing that can call it. The shapes below are
// NOT invented — each field is the return value of a named function in one of
// those two modules, so wiring them is mechanical rather than a negotiation,
// and a type is the one form of contract the backend lane can diff.
//
// ⚠ **NOTHING IN THIS FILE FABRICATES A FALLBACK.** Every money field is
// `{stored, display}` with both halves nullable, and every count the server
// cannot produce is `null`. A screen branches on the null and prints the
// reason; it never prints a zero, a bare dash, or a figure this client computed
// (DEF-088's second rounding path, DEF-127's fabricated `$0.00`).
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

import type { WorklistAbsence, WorklistMoney } from "./worklistEndpoints";

export type { WorklistAbsence, WorklistMoney };

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported for the reason `newConnectEndpoints.ts` gives:
 *  no coupling between two files different lanes hold. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// TRF-02 · THE TRANSFER
// ══════════════════════════════════════════════════════════════════════════

/**
 * `transfers.MoneyStatement`, serialised — `TRF-02.4`'s whole step.
 *
 * ⛔ **`deposit_carried` IS NULL WHENEVER BR-CUS-057's INTEREST CANNOT BE READ,
 * AND THAT IS THE FEATURE.** `MoneyStatement.deposit_carried` returns `None`
 * when `deposit_interest is None` rather than falling back to the principal,
 * and ❄️ WE-7 / GT-23 is the frozen pair that says why: reading the unwired
 * interest as zero serves the PRINCIPAL as the carried amount and keeps the
 * customer's interest. The drawing's own worked figure is the principal plus
 * its interest; a screen that printed the principal alone would be $3.50 short
 * on the example B18 uses, every time, and would look completely correct.
 *
 * ⚠ **`sentences` IS THE SERVER'S OWN COPY** — *"deposit carried $…"*, *"arrear
 * follows $…"* — emitted only when its figure is readable. `unavailable`
 * carries up to five reasons and the screen renders them as visible text.
 */
export interface TransferMoneyStatement {
  currency: string;
  deposit_carried: WorklistMoney;
  arrear_following: WorklistMoney;
  sentences: string[];
  gaps: string[];
  unavailable: WorklistAbsence[];
}

/** `transfers._serialize` — the row both the list and this wizard read. */
export interface TransferRecord {
  id: string;
  state: string;
  step: number;
  step_of: number;
  step_label: string | null;
  /** The SELLER's customer — NULL where the account had nobody linked
   *  (`DEF-CUS-6387`, migration 0067); `seller_name` then names them. */
  customer_id: string | null;
  seller_name?: string | null;
  from_account_id: string;
  from_account_no: string | null;
  to_account_id: string | null;
  to_account_no: string | null;
  /** Two STRINGS the server builds, `A-10650` and `→ A-11940` — or `→ —` while
   *  there is no incoming account. ⚠ **THE DASH IS THE SERVER'S** and this
   *  screen produces none of its own: *"a blank second line and an absent one
   *  are indistinguishable once rendered"* (`transfers._serialize`). */
  from_cell: string[];
  to_unit_id: string | null;
  out_date: string | null;
  in_date: string | null;
  /** `null` until both dates are set. §5.7.4's same-day rule is RECORDED here
   *  and enforced as a billing consequence by nothing in this module. */
  same_day: boolean | null;
  /** ⚠ Both are `false` on every sale and are kept only because the stored row
   *  still has the columns. `acknowledge_money` elects nothing — `OQ-1252` was
   *  answered on 2026-09-01 (*the debt follows the property*) — so a screen
   *  that read either of these as a clerk's choice would be reading a column
   *  nobody writes. */
  deposit_carry_elected: boolean;
  arrears_follow_elected: boolean;
  committed_at: string | null;
  cancelled_at: string | null;
  money?: TransferMoneyStatement;
  /** What `reassign_account` actually did, and the figures AS THEY STOOD at the
   *  moment of sale — so what the buyer took on is on the record (hard rule 4:
   *  nothing already issued to the seller is touched). Optional because a
   *  transfer read back before its commit has none. */
  reassignment?: {
    account_no: string | null;
    to_customer_id: string | null;
    to_customer_name: string | null;
    sold_on: string | null;
    balance_at_sale?: { stored: string | null; display: string | null };
    deposit_at_sale?: { stored: string | null; display: string | null };
    unit_changed: boolean;
    account_number_changed: boolean;
    account_closed: boolean;
    accounts_created: number;
  } | null;
  /** ⊕ 2026-09-23 — what the commit wrote onto the account for the buyer:
   *  `contact`, `mailing_address` / `mailing_address_removed`,
   *  `autopay_removed`, `co_applicant`, `preferred_language` (T3, T4). */
  buyer_carried?: { written: string[]; not_written: string[] } | null;
  /** ⊕ T2 (`DEF-CUS-6394`) — the property's owner after the sale. */
  premises_owner?: TransferOwnerOutcome | null;
  /** The messages the commit QUEUED — queued is not sent (`BR-NOT-013`). */
  messages?: TransferMessageOutcome[];
  /** ⊕ `DEF-CUS-6392` — the work orders the commit raised from the field-visit
   *  table, in the order the rows were sent (`FieldVisitOrders` `live`). */
  work_orders?: { id: string; order_no: string | null }[];
  /** *No visit needed* was the answer. */
  field_visit_declined?: boolean;
}

/** T2 — `unchanged` for a regular account (the ruling, not a gap), `moved`
 *  for a master account metering moved, `not_moved` with the reason. */
export interface TransferOwnerOutcome {
  state: "unchanged" | "moved" | "not_moved" | string;
  is_master: boolean;
  reason?: string | null;
}

/** One queued message off a sale (`notifications_seam._transfer_outcome`). */
export interface TransferMessageOutcome {
  code: string;
  template_code: string | null;
  party: "buyer" | "seller" | string | null;
  channels: string[];
  address: string | null;
}

/** A refusal the COMMIT would raise, served early on the step where its cause
 *  is picked (`DEF-CUS-6395`). The same `message_key` + `params` shape the
 *  commit's own error carries, so one sentence serves both. */
export interface TransferRefusal {
  code: string;
  br_ref: string;
  message_key: string;
  params: Record<string, unknown>;
}

/** `POST /transfers/account-preview` — step 1's answer (writes nothing). */
export interface TransferAccountPreview {
  account_no: string | null;
  refusal: TransferRefusal | null;
  seller: { customer_no: string | null; name: string; kind: string } | null;
  seller_name: string | null;
  is_master: boolean;
  billing_cycle: { code: string; name: string | null; bill_day: number | null } | null;
  current_period: { start: string; end: string | null } | null;
  next_bill_on: string | null;
  ledger_since: string | null;
}

/**
 * `POST /transfers/account-preview` — **the refusal where its cause is
 * picked, and the facts step 1 used to hard-code** (`DEF-CUS-6395`,
 * `DEF-CUS-5182`). Asked the moment the clerk picks the account; writes
 * nothing, starts no transfer.
 */
export async function previewTransferAccount(
  fromAccountId: string,
  client: ApiClient = api,
): Promise<TransferAccountPreview> {
  return requireData(
    await client.post<TransferAccountPreview>("/transfers/account-preview", {
      from_account_id: fromAccountId,
    }),
  );
}

/**
 * What `TRF-02.5` commits.
 *
 * ⚠ **ONE PAYLOAD TO ONE DOOR, AND THE FIVE-WRITE SEQUENCE BEHIND IT IS THE
 * SERVER'S.** `transfers.py` exposes five separate writes — `start_transfer`,
 * `set_target_unit`, `set_dates`, `elect_money`, `commit_transfer` — and each
 * takes the id the previous one produced. A frontend firing five sequential
 * POSTs would be inventing four half-committed states that `TRF-02`'s own
 * footer forbids (*"both halves commit together at the end"*) and that
 * BR-SHL-019 forbids in general, and any one of the five failing would leave a
 * `scheduled` transfer row nobody can see, because **no transfer detail screen
 * exists** (US-CUS-027 §8). So the wizard sends the whole election once and the
 * orchestration is REPORTED as owed on the server side.
 *
 * ⚠ **`final_reads` AND `opening_reads` ARE STILL NOT HERE — BUT THE REASON
 * CHANGED ON 2026-08-26 AND THE OLD ONE IS NOW FALSE (CR-038 W9 task 5).**
 *
 * This block read: *"`transfers.py` writes no meter read at all — its own
 * docstring: 'this module writes no bill and no meter read'. Sending reads to a
 * door that discards them would make the screen claim a capture that did not
 * happen."* Half of that is no longer true. `transfers.commit_transfer` takes
 * `payload.reads` and carries them to the metering event door ONCE — event
 * `transfer`, dated the OUT date, ONE committed row serving both accounts
 * (BR-MET-128, B18 §5.7.4's *"the same reading"*). A screen sending them today
 * would NOT be claiming a capture that did not happen.
 *
 * ⚠ **AND THE OTHER REASON IS NOW FALSE TOO — `DEF-CUS-5076`, 2026-09-12.**
 * This header said **`POST /transfers/commit` IS NOT MOUNTED. Every call
 * 404s.** Measured against a running server on this date: it answers **422**
 * with a named field refusal, which is a mounted door rejecting a payload.
 * `transfer_disconnect_api.py` mounted it on **2026-09-01**, eleven days before
 * this sentence was read. ⚠ **`reads` IS STILL ABSENT AND FOR A THIRD REASON
 * THAT DOES NOT EXPIRE: a sale closes no account and opens none**, so there is
 * no final read and no opening read — the meter keeps running on one unbroken
 * account (`BR-CUS-1030`). A lane that adds `reads` back here is re-creating
 * the second account that ruling removed.
 *
 * ⚠ **THE SAME SHAPE ON THE OTHER TWO DOORS, REPORTED HERE BECAUSE NOTHING
 * ELSE NAMES IT:** `disconnects.commit_cut(final_reads=…)` (event `disconnect`)
 * and `metering.connections.accept_field_result` (event `new_connect`) both
 * take readings server-side and NEITHER HAS A FRONTEND CALLER anywhere in
 * `07-frontend/src` — the disconnect wizard schedules a cut and never performs
 * one (`screenIds.ts` says so in as many words), and no screen accepts a field
 * result. Three doors, one owed surface each.
 */
/**
 * ⚠ **REWRITTEN 2026-09-12 TO THE SHAPE THE DOOR HAS READ SINCE 2026-09-01 —
 * `DEF-CUS-5075`.** It declared `to_unit_id`, `out_date`, `in_date`,
 * `deposit_carry` and `arrears_follow`; `transfer_commit` reads
 * `from_account_id`, `customer`, `sold_on` and `field_visit`. Five keys ignored,
 * three never sent, and the commit answered `422 VAL-001
 * customers.transfer.buyer_required` at the second of five staged writes —
 * naming a field that appeared on none of the five screens.
 *
 * **A transfer is a SALE** (`BR-CUS-1030`, PO 2026-09-01): the account, its
 * unit, its meters, its plan and its ledger stay put and the CUSTOMER changes.
 * There is no target unit, there is one date, and nothing is elected.
 */
export interface TransferCommitPlan {
  from_account_id: string;
  /** Who is buying it. `identity` carries ONLY the identifiers that belong to
   *  the stated kind — `ssn` / `driving_licence` / `phone` for a person,
   *  `tax_id` for a company (`BR-CUS-1022`). The server validates this block
   *  TWICE, at `set_new_customer` and again inside `reassign_account`, because
   *  a service-layer caller does not pass through step 2. */
  customer: {
    display_name: string;
    kind: string;
    identity: Record<string, string>;
    email?: string;
    /** T1 — the customer the clerk FOUND and LINKED on step 2. It IS the
     *  buyer; no identifier is re-typed (`DEF-CUS-6386`). */
    customer_id?: string;
  };
  /** ONE date. `set_sale_date` writes it to both stored columns so `same_day`
   *  is true by construction — a sale closes no account and opens none. */
  sold_on: string;
  /** ⊕ `DEF-CUS-10255` — the buyer's own panels (image `07-transfer.png`):
   *  co-buyer cards, staged documents, Tax, Discounts and Preferences, in the
   *  MOVE-IN's own shapes (`transfers.BUYER_ACCOUNT_KEYS`). Absent = unchanged. */
  buyer_account?: Record<string, unknown>;
  /** CR-070 wave P — the changeover-read jobs a clerk ticked, raised on this
   *  account. It raises WORK and captures no reading: there is no final read
   *  at a sale, because nothing closes. */
  /** ⊕ `DEF-CUS-6392` — the shared `FieldVisitOrders` answer
   *  (`fieldVisitPayload`): `{orders: [...]}` or `{none: true}`. The server
   *  reads it through `services._field_visit`, as the move-in does, and still
   *  accepts the older `{template_ids}` tick. */
  field_visit?: Record<string, unknown>;
}

/**
 * `POST /transfers/commit` — `TRF-02.5`'s `Complete transfer ✓`.
 *
 * ✅ **MOUNTED SINCE 2026-09-01, AND THE PAYLOAD BELOW IS THE WRONG ONE** —
 * `DEF-CUS-5075`. It answers `422 VAL-001 customers.transfer.buyer_required`
 * on the shipped shape, because the door was rewritten the day the PO ruled a
 * transfer is a SALE and this plan was not. See `TransferCommitPlan`.
 */
export async function commitTransfer(
  plan: TransferCommitPlan,
  client: ApiClient = api,
): Promise<TransferRecord> {
  return requireData(await client.post<TransferRecord>("/transfers/commit", plan));
}

/**
 * **`POST /transfers/buyer-preview` — the drawn feedback line on p127**, and
 * the thing `TRF-02.2` was missing: *"Matched an existing customer. C-00902 ·
 * Vasquez, M., on the phone number."*
 *
 * ⚠ **A POST THAT WRITES NOTHING, AND THE METHOD IS THE POINT.** A government
 * identifier may not travel in a query string — a URL is logged by every proxy,
 * appears in browser history and lands in the next request's referer header,
 * and `BR-CUS-092`(c) is about exactly that class of leak. A `GET` would put an
 * SSN in three of them at once. It creates no transfer row either
 * (`uq_transfers_open_from` allows one open transfer per account, and a preview
 * that started a job would leave an account that can never be sold again).
 *
 * ⚠ **IT REFUSES WHAT THE COMMIT REFUSES, SO THE SCREEN MAY NOT TREAT A
 * REFUSAL AS A MATCH.** `BR-CUS-1081` §4: a preview that accepted a block the
 * commit rejects would be worse than no preview, because the clerk would trust
 * it. A half-typed `customer_id` answers `will_create: true`, never an error —
 * so this is safe to call on every keystroke.
 *
 * ⚠ **ADVISORY, AND IT REFUSES NOTHING** — `BR-CUS-019`, *the duplicate check
 * is ADVISORY; staff decides*. Nothing here may become a gate.
 */
export async function previewTransferBuyer(
  customer: Record<string, unknown>,
  client: ApiClient = api,
  fromAccountId?: string,
): Promise<BuyerPreview> {
  return requireData(
    await client.post<BuyerPreview>("/transfers/buyer-preview", {
      customer,
      // ⊕ `DEF-CUS-6395` — with the account, the preview also answers the
      // commit's buyer-is-the-seller refusal, on step 2.
      ...(fromAccountId !== undefined && fromAccountId !== ""
        ? { from_account_id: fromAccountId }
        : {}),
    }),
  );
}

/** What that door answers — `BR-CUS-1081` §4. `named` is NOT `matched`: it
 *  means the clerk POINTED at a customer, so no evidence was weighed and
 *  `tier` is null. */
export interface BuyerPreview {
  buyer_name?: string | null;
  buyer_kind?: string | null;
  buyer_identifiers_presented?: string[];
  buyer_capture_presented?: string[];
  buyer_mailing_presented?: boolean;
  buyer_match?: {
    verdict: "named" | "matched" | "candidates" | "none";
    matched?: string | null;
    tier?: "strong" | "weak" | null;
    basis?: string | null;
    candidates?: { customer_no?: string | null; display_name?: string | null }[];
    missing_for_strong?: string[];
    will_create?: boolean;
  } | null;
  /** ⊕ `DEF-CUS-6395` — the commit's buyer-side refusal, asked early. */
  refusal?: TransferRefusal | null;
}

/**
 * `GET /transfers/{id}/money` — `transfers.money_statement`, a pure read.
 *
 * ✅ **MOUNTED. THE SECOND REASON IS THE ONE THAT STILL BITES, AND IT DOES NOT
 * EXPIRE:** it is keyed by a TRANSFER ID, and under the one-door commit above
 * there is no transfer row until the commit succeeds. So `TRF-02.4`'s figures
 * cannot be read before the thing they describe exists, and the step says so
 * rather than printing the drawing's numbers. Measured 2026-09-12: an unknown
 * id answers **404** from `_transfer_or_refuse`, which is the route working.
 */
export async function getTransferMoney(
  transferId: string,
  client: ApiClient = api,
): Promise<TransferRecord> {
  return requireData(
    await client.get<TransferRecord>(`/transfers/${encodeURIComponent(transferId)}/money`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// DSC-02 · THE DISCONNECT
// ══════════════════════════════════════════════════════════════════════════

/** One row of `disconnects.protection_check`'s `checks`. ⚠ `outcome` is a
 *  THREE-valued vocabulary and the third value is the important one:
 *  `"unavailable"` means the product cannot answer, which is NOT `pass`. */
export interface ProtectionCheckRow {
  check: string;
  outcome: "pass" | "fail" | "unavailable" | string;
  lifetime: string | null;
  reason: string;
  effective_from: string | null;
  expires_on: string | null;
}

/**
 * `disconnects.protection_check(account_id, as_of=…)`.
 *
 * ⚠ **`all_clear` IS COMPUTED OVER THE THREE PROTECTIONS THAT EXIST**, not over
 * `DSC-02.2`'s ten. The screen must NOT render it as the drawn `All clear`
 * chip: six of the ten are unbuilt (DEF-691 / BR-CUS-101) and a green summary
 * over six unasked questions is a fabricated clearance on the screen that
 * authorises a cut.
 */
export interface ProtectionCheckResult {
  account_id: string;
  as_of: string;
  checks: ProtectionCheckRow[];
  all_clear: boolean;
  protections_in_force: string[];
}

/** `disconnects.LadderState.as_dict` — `DSC-02.3`'s ladder panel. */
export interface LadderStateResult {
  account_id: string;
  runs: boolean;
  halt_code: string | null;
  detail: string;
  /** `TIER 1 · REMINDER` … and `TIER_UNMAPPED` for payments' `second_5_day`
   *  rung, which B18 gives no chip. ⚠ Mapping it onto a tier would tell a
   *  regulator a certified letter went out; `tier_for_rung` refuses to. */
  tier: string | null;
  next_tier: string | null;
  balance: WorklistMoney;
  sequence: string;
  /** `disconnects.NO_SCHEDULER` — DEF-320, carried on every ladder answer:
   *  nothing in this product reads a date and acts on it. */
  scheduler: { advances_on_a_schedule: boolean; tracks: string; detail: string };
  /** `OQ-CUS-1810` — added to this payload 2026-09-12. It rides on the LADDER
   *  rather than on a route of its own because the ladder is the resource that
   *  owns notices, and step 3 needs the tier, the served dates and the floor
   *  together. Optional in the type because a tenant on an older build serves
   *  a payload without it, and a screen must state that absence rather than
   *  read `undefined` as *no floor*. */
  cut_floor?: CutFloor | null;
  /** `DEF-CUS-7680` — added 2026-09-28. The four refusals `POST
   *  /disconnects/schedule` would give that the CASE already decides, so the
   *  wizard's step 1 can say them instead of costing a clerk four steps.
   *
   *  ⚠ **OPTIONAL FOR THE REASON `cut_floor` IS.** A tenant on an older build
   *  serves a payload without it, and `undefined` is *not asked* rather than
   *  *nothing wrong* — the screen must let the clerk through rather than
   *  invent a refusal, which is what `schedulePreflight` below does. */
  schedule_readiness?: ScheduleReadiness | null;
}

/**
 * `disconnect_reads.schedule_readiness` — a PREVIEW of `schedule_cut`, run
 * read-only in the commit's own order.
 *
 * ⚠ **IT DECIDES NOTHING AND NO SCREEN MAY TREAT `ready: true` AS PERMISSION.**
 * `POST /disconnects/schedule` re-runs every one of these inside its
 * transaction, plus the payload checks, the ladder halt and the certified
 * proof — days pass between a screen being drawn and a button being pressed.
 *
 * ⚠ **`detail` IS CARRIED AND NEVER RENDERED** (`BR-SHL-020` r2). The clerk's
 * sentence comes from the catalogue, keyed by `code` — see
 * `disconnect/disconnectRefusal.ts`, which is the one place that maps it.
 */
export interface ScheduleReadiness {
  account_id: string;
  as_of: string;
  ready: boolean;
  blockers: DisconnectPreflightBlocker[];
  /** The FIRST blocker — the sentence the commit would really have given. */
  refusal: DisconnectPreflightBlocker | null;
}

export interface DisconnectPreflightBlocker {
  code: string;
  br_ref: string;
  detail: string;
}

/**
 * `disconnects.reconnection_terms` — `DSC-02.4`'s quote.
 *
 * ⛔ **`fee` IS NULLABLE AND NO SCREEN MAY SUBSTITUTE A NUMBER FOR IT.**
 * BR-BIL-007: the amount is the tenant's own `CC-RECON` charge code, and
 * `reconnection_terms` answers `None` with a reason when that code is not
 * configured or is not a flat amount. **DEF-700 is the state of the tree
 * today** — no seed in this repository creates `CC-RECON`, so on every tenant
 * here the answer really is absent, and a screen printing a literal would be
 * quoting a price the product cannot charge.
 *
 * ⚠ **`timing` IS BR-CUS-104 AND IT IS NOT DECORATION.** The fee becomes owed
 * AT THE CUT, so what a customer must clear to be reconnected is their arrears
 * PLUS the fee. `posting` says the fee reaches AR through nothing today, which
 * is DEF-708 — the reconnection gate reads AR only and lets a customer through
 * short by exactly the fee.
 */
export interface ReconnectionTerms {
  account_id: string;
  charge_code: string;
  /** ⛔ **`null` — THE WHOLE FIELD, NOT A PAIR OF NULLS (DEF-2131, 2026-08-28).**
   *  `reconnection_terms` returns `fee: None` when `CC-RECON` is unconfigured or
   *  is not a flat amount, and `DEF-700` records that no seed in this repository
   *  creates that code — so on every tenant here the value really is `null`.
   *  This was typed `WorklistMoney` while the block above said in as many words
   *  that it is nullable: hard-won law 1 inside a type declaration. It could not
   *  be caught until 2026-08-28 because the route was not mounted, and a
   *  hand-written type over a 404 cannot be contradicted by anything. */
  fee: WorklistMoney | null;
  fee_absence: WorklistAbsence | null;
  deposit: {
    on_file: WorklistMoney;
    election: string | null;
    new_deposit_required: boolean | null;
    detail: string;
    posting: WorklistAbsence;
  };
  posting: WorklistAbsence;
  timing: WorklistAbsence;
}

/** `disconnects.case_payload` — the open case behind `DSC-02.3` and `DSC-02.5`. */
export interface DisconnectCaseRecord {
  case_id: string;
  account_id: string;
  sequence: string;
  state: string;
  tier: string | null;
  tier_reached_on: string | null;
  amount_owed_at_open: WorklistMoney;
  currency: string;
  opened_on: string;
  cut_scheduled_for: string | null;
  cut_on: string | null;
  stopped_on: string | null;
  stopped_reason: string | null;
  scheduler: { advances_on_a_schedule: boolean; tracks: string; detail: string };
  /** `DELIVERY_UNAVAILABLE` — DEF-692, on every case this module writes. */
  delivery: WorklistAbsence;
}

/**
 * The earliest date a cut may lawfully happen — `OQ-CUS-1810`, closed by the PO
 * on 2026-09-12. The FINAL notice's SERVED date plus the tenant's own period
 * (`BR-PAY-017`'s `final_notice_hours`), counted in BUSINESS days and rolled
 * past that tenant's own holiday calendar. Computed server-side in
 * `apps/customers/cut_date.py`; nothing is counted in a browser.
 *
 * ⚠ **`enforced` IS ALWAYS `false` AND IT IS ON THE WIRE ON PURPOSE.** PO,
 * verbatim: *"give a message but allow it"*. A screen shows the date and warns;
 * it must NOT set a `min` on the input, which would silently prevent a clerk
 * typing an earlier date at all, and no validator may read this.
 *
 * ⚠ `earliest_lawful_cut` is `null` whenever the floor could not be worked out,
 * and `unavailable_reason` is then a CODE (`notice_not_served` · `no_open_case`
 * · `no_notice_at_this_tier`) and never a sentence — the screen owns the words
 * (`B14` rule 31).
 */
export interface CutFloor {
  earliest_lawful_cut: string | null;
  unavailable_reason: string | null;
  notice_served_on: string | null;
  business_days: number;
  tenant_configured: boolean;
  enforced: boolean;
  final_notice_hours?: number;
}

/**
 * What `DSC-02.5`'s `Schedule the disconnection ✓` sends — `schedule_cut`'s own
 * keyword arguments, in its own vocabulary.
 *
 * ⚠ **`cut_on` IS SENT AND IS NOT COMPUTED HERE.** `DSC-02.3` chips the date
 * *"Computed, then chosen"* and says the earliest lawful cut *"cannot be
 * typed"*: it is the notice date plus the statutory period, **rolled forward
 * past weekends and public holidays**. Nothing in this product computes that
 * roll, and B18's own fixture cannot prove it (Aug 22 2026 is a Saturday and
 * Aug 24 the Monday, so the drawn case needs no roll at all). A client that
 * added 48 hours would be implementing *"+2 days"*, which is a different rule
 * that agrees with the drawing by luck. The field is therefore DISABLED on the
 * screen with that reason, and this key is here for the day a server computes
 * it.
 *
 * ⚠ **`services` IS `{service_code: treatment}`**, the drawn table's own shape,
 * *"so a caller cannot pass a bare list of services and leave the treatment
 * implied"*. A `restrictor` value is refused BY NAME (OQ-385).
 */
export interface ScheduleCutPlan {
  account_id: string;
  cut_on: string;
  reason: string | null;
  services: Record<string, string>;
  deposit: string | null;
  /** `DEF-CUS-9631` — step 3's *Who goes: Work order* rows. Each becomes a
   *  job on the account, raised by *Disconnection* (`BR-CUS-1098`). Omitted
   *  when the clerk sends nobody. */
  visits?: { service: string | null; instruction: string }[];
}

/**
 * `POST /disconnects/schedule` — `DSC-02.5`'s commit.
 *
 * ✅ **MOUNTED — measured 422 on an empty payload, 2026-09-12** (`DEF-CUS-5076`;
 * this said NOT SERVED for fifteen days after it landed). Note what the door
 * does: it SCHEDULES. `DSC-02`'s footer is on all five steps — *"nothing is cut until
 * the scheduled date"* — and `commit_cut` is a separate call on the day. The
 * button says `Schedule the disconnection ✓` and not *Cut* for that reason.
 */
export async function scheduleCut(
  plan: ScheduleCutPlan,
  client: ApiClient = api,
): Promise<DisconnectCaseRecord> {
  return requireData(await client.post<DisconnectCaseRecord>("/disconnects/schedule", plan));
}

/** `GET /accounts/{id}/protections` — `disconnects.protection_check`.
 *
 *  ✅ **MOUNTED 2026-08-28 (`8700efbb9`), MEASURED 200 ON 2026-09-12, AND WIRED
 *  INTO STEP 2 THE SAME DAY — `DEF-CUS-5076`.** This wrapper said `⛔ NOT
 *  SERVED` for fifteen days after the route landed, and step 2 of the
 *  disconnect wizard read that note rather than the route: it rendered `—`
 *  against *Medical equipment on site* under the sentence *"no endpoint serves
 *  its finding to a screen yet"*, **on the most safety-critical step in this
 *  product**, while the server was answering with the finding, its lifetime and
 *  its dates. Hard-won law 1 in its most expensive form: a comment claiming an
 *  absence is not the absence, and the backend lane that mounts a route has no
 *  reason to grep the frontend for prose about it. */
export async function getProtectionCheck(
  accountId: string,
  client: ApiClient = api,
): Promise<ProtectionCheckResult> {
  return requireData(
    await client.get<ProtectionCheckResult>(
      `/accounts/${encodeURIComponent(accountId)}/protections`,
    ),
  );
}

/** `GET /accounts/{id}/reconnection-terms` — `disconnects.reconnection_terms`.
 *  ✅ MOUNTED; measured 200 on 2026-09-12 (`DEF-CUS-5076`). No screen calls it
 *  yet, which is a different and honest statement from *not served*. */
export async function getReconnectionTerms(
  accountId: string,
  client: ApiClient = api,
): Promise<ReconnectionTerms> {
  return requireData(
    await client.get<ReconnectionTerms>(
      `/accounts/${encodeURIComponent(accountId)}/reconnection-terms`,
    ),
  );
}

/**
 * `POST /accounts/{id}/protections` — `disconnects.record_protection`.
 *
 * ⚠ **THE ACT THAT STOPS A CUT, AND NO SCREEN COULD PERFORM IT —
 * `CR-125-BRC07`.** The route has been mounted and answering `201` since
 * 2026-08-28; step 2 of the disconnect wizard was READ-ONLY over it for three
 * weeks. **A clerk could not record a medical certificate anywhere in this
 * product** — on the step whose own drawn sentence is *"cutting service to a
 * protected household is the most serious thing this product does"*.
 *
 * ⚠ **THE DATES ARE THE CALLER'S AND NEVER THE SERVER'S.** `effective_from` is
 * REQUIRED; `expires_on` is optional because a protection with no stated end is
 * a real thing, and the check payload's `lifetime` is what says which of the
 * three shapes each kind has. A medical certificate is the only one that
 * carries its own date.
 */
export interface RecordProtectionPlan {
  kind: string;
  effective_from: string;
  expires_on: string | null;
  set_by: string | null;
  reference_id: string | null;
  note: string | null;
}

export async function recordProtection(
  accountId: string,
  plan: RecordProtectionPlan,
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(`/accounts/${encodeURIComponent(accountId)}/protections`, plan);
}

/**
 * `POST /accounts/{id}/disconnect-case/stop` — `disconnects.stop_by_hand`.
 *
 * ⚠ **THE MANUAL OVERRIDE ON A PROCESS THAT ENDS IN A HOUSEHOLD LOSING
 * SUPPLY**, and it also had no door. `on_date` and `reason` are both required
 * and neither is defaulted, because the record of who stopped it, when and why
 * is the whole point of the act (hard rule 7, widened — a disconnection is a
 * service action against a named customer).
 *
 * ⛔ **THE THREE REASONS ARE A CLOSED SET.** `disconnects.STOP_REASONS` holds
 * `clerk_error`, `dispute` and `regulator_instruction`, and its own comment
 * says a fourth *"is a fourth way to stop chasing a real debt, and it needs a
 * ruling, not a string"*. A screen must not offer one.
 */
export const STOP_LADDER_REASONS = [
  { code: "clerk_error", en: "Clerk error", sub: "It should never have been started." },
  { code: "dispute", en: "Disputed", sub: "The customer is contesting the bill." },
  {
    code: "regulator_instruction",
    en: "The regulator told us to",
    sub: "An instruction from outside.",
  },
] as const;

export async function stopLadderByHand(
  accountId: string,
  body: { on_date: string; reason: string },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(`/accounts/${encodeURIComponent(accountId)}/disconnect-case/stop`, body);
}

/** `GET /accounts/{id}/ladder` — `disconnects.ladder_state` + the open case.
 *  ✅ MOUNTED; measured 200 on 2026-09-12 (`DEF-CUS-5076`). No screen calls it
 *  yet. ⚠ Its payload carries `NO_SCHEDULER` on every answer — nothing in this
 *  product reads a date and acts on it (`DEF-320`) — so a screen that shows a
 *  scheduled cut must not imply anything will perform it. */
export async function getLadderState(
  accountId: string,
  client: ApiClient = api,
): Promise<LadderStateResult> {
  return requireData(
    await client.get<LadderStateResult>(`/accounts/${encodeURIComponent(accountId)}/ladder`),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: B18 §5.7.7 · §5.8.7 · apps/customers/transfers.py ·
//         apps/customers/disconnects.py · BR-SHL-019 · BR-SHL-025 ·
//         BR-BIL-007 · BR-CUS-057 · BR-CUS-100 · BR-CUS-103 · BR-CUS-104 ·
//         BR-CUS-105 · ❄️ WE-7 / GT-23 · DEF-691 · DEF-692 · DEF-700 · DEF-708
// generated: 2026-08-25 by lane W7WIZ
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E1 ⛔ **NONE OF THESE ROUTES IS MOUNTED.** `apps/customers/api.py` serves
//      `GET /transfers` and `GET /disconnects` and nothing else on either
//      resource, while both service modules hold every write path behind them.
//      Wrapped anyway, on the `GET /invoices` precedent, and because a type is
//      what the backend lane can diff.
//   E3 `commitTransfer` posts ONE payload with no id in the path, against a
//      service layer that exposes five sequential writes. The orchestration in
//      one transaction is the server's; REPORTED.
//   E3 every money field is `{stored, display}` with both halves nullable, and
//      `fee` is additionally absent on every tenant in this tree (DEF-700).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
