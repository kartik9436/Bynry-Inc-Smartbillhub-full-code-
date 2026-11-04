// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.9` · `P3.11` — screen 2·2 of
//           `05-prototype/06 Payments Page Blueprint.pdf`, and the three modals
//           2·3c, 2·3d and 2·3h. Read AS IMAGES at scale 2.0 (p035–p036,
//           p042–p044, p049–p050), B14 rule 42.
// Screens:  2·2 the payment detail (`S33` · `PAY-H`) · 2·3c Add a correction ·
//           2·3d Cancel (`PAY-P`) · 2·3h Resend (`PAY-E`)
// Rules:    CLAUDE.md hard rule 2 (money is a DECIMAL STRING on the wire, never
//           a JSON number) · hard rule 6 (idempotency — see `copy_no`) ·
//           hard rule 1 (the tenant is the URL's first segment; this file sends
//           none) · B14 rule 31 (no database id is a visible value) ·
//           BR-SHL-025 (a refusal is the SERVER's; `actions` carries it)
// ───────────────────────────────────────────────────────
// The typed wrappers for the four routes `P3.1`–`P3.4` landed in
// `apps/payments/detail_api.py` at `e9cc747c5`.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TYPES ARE READ OFF THE SERVER'S OWN PAYLOAD BUILDERS, NOT OFF THE DRAWING
// ══════════════════════════════════════════════════════════════════════════
// `apps/payments/payment_detail.py::detail_body`, `history_rows`,
// `action_availability`, `apps/payments/cancel.py::cancel_payment` and
// `apps/payments/receipt_resend.py::resend_receipt`. Where the drawing and the
// server disagree the SERVER wins here, because this file is a wire contract
// and not a screen — and each place they disagree is named below so the screen
// lane meets it as a fact rather than as a surprise.
//
// ⚠ **`detail_body` SPREADS `selectors.payment_row` VERBATIM**, which is the
// same builder the LIST uses. That is the guarantee that the page and the row
// can never print different figures, and it is why `PaymentDetail` extends
// `PaymentRow` rather than re-declaring eleven fields that would be free to
// drift (hard-won law 5's shape, one layer up).
//
// ⚠ **`unavailable[]` IS A CODE LIST AND NEVER CLERK COPY.** The server's own
// docstring says so and `P3.18` is why: B14 rule 33 puts RATIONALE at ZERO
// WORDS ON SCREEN, so `history_is_pruned_like_every_audit_row` is a fact a
// CALLER may reason about and is never rendered as a disclaimer. A screen that
// prints one of these codes, or a sentence derived from one, is the breach
// `P3.18` deleted from this module on 2026-09-23.
import type { ApiClient, ApiResponse } from "./client";
import type { PaymentRow, ReversedPayment } from "./endpoints";

/** A 2xx with no body where the contract promises one is a server bug (B12
 *  r1). Throwing beats handing a screen a silent `null` it renders as blank.
 *  Restated here rather than imported from `endpoints.ts`, which several lanes
 *  are editing on any given afternoon. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * What the address bar carries and what this client sends.
 *
 * ⚠ **THE SERVER TAKES THE `PMT-` NUMBER *OR* THE uuid, AND THE SCREEN SENDS
 * THE NUMBER.** `P3.1`'s row says so in as many words, and the reason is B14
 * rule 31: the drawing's agreed address is
 * `/:tenant/payments/PMT-2609-000418`, and **an address a clerk pastes into a
 * message is about as visible as a value gets**. The uuid still resolves, so a
 * link built before this rule existed does not break.
 */
export type PaymentRef = string;

// ── ⑤ SOURCE ──────────────────────────────────────────────────────────────
/**
 * *"Counter, Digital or Post, and who or which provider"* (p035 ⑤).
 *
 * ⚠ **THE STORED WORD TRAVELS, NEVER THE DRAWN ONE.** `origin` holds
 * `entry · webhook · import`; *Counter · Digital · Post* are LABELS that live
 * in the eleven catalogues. A screen that matched on the drawn word would
 * render nothing for every payment in the database.
 */
export interface PaymentSource {
  origin: string;
  /** The column was null and the value was worked out from the row's shape. */
  origin_is_derived: boolean;
  /**
   * Who took it: a payment agent's name, else the clerk who owns the till the
   * payment names (`DEF-PAY-10734`, L2-03 — this read *"`null` TODAY"* until
   * 2026-10-30, after `counter_session_id` had shipped). `null` when neither
   * exists: `entry` alone does not name a person, because a transfer leg and a
   * bounce are both `entry`.
   */
  taken_by: string | null;
  /** The till's code (`CTR-261021-BS-4`), or `null` for a payment with none. */
  counter_session_ref: string | null;
  /** `DEF-PAY-10734` — an imported payment's kind of import (`lockbox` · `csv`
   *  · `file`), the Source cell's label in place of the drawing's *Post*.
   *  `null` unless `origin` is `import`. */
  import_kind?: string | null;
  /** PO 2026-10-30 Q6 — the store network the file's Network column named
   *  (`Hy-Vee`): the Source cell reads *Store · Hy-Vee*. `null` otherwise. */
  store_network?: string | null;
  /** `CR-174-BRC10` — where an agent's customer stood (`kiosk · csr · web ·
   *  ivr · other`), which machine (`4471`), and on a reversing row the bank's
   *  own return code (`R01`). All three `null` on a payment no agent took. */
  channel?: string | null;
  terminal?: string | null;
  return_code?: string | null;
}

// ── ⑥ RECONCILED ──────────────────────────────────────────────────────────
/**
 * Where the bank matched it — *"the many-to-one match set"* (p035 ⑥).
 *
 * ⚠ **`reference` IS ALWAYS `null` AND THE DRAWING'S `BRM-2609-0041` IS AN
 * ILLUSTRATION.** `bank_rec_match_sets` has no code column and mints no series;
 * the only value there is a bare uuid, which B14 rule 31 forbids on a screen.
 * **B14 rule 37 settles it for the screen — a figure drawn in a wireframe is an
 * illustration, never a fact to build to** — so the cell shows the facts that
 * ARE established and states the absence. `OQ-PAY-12602` asks the PO whether a
 * match set should get a number series; nothing is blocked either way.
 */
export interface PaymentReconciliation {
  /** The deposit batch's own human-facing code — `DEP-260921-CHK`. */
  batch_code: string;
  batch_status: string;
  /** `null` = banked but not yet tied to a statement. A real state. */
  matched_at: string | null;
  /** COUNTS, not ids — the drawing's sub-line *"Three batches, one credit"*. */
  bank_line_count: number | null;
  batch_count: number | null;
  /** The bank's own date for the money (the latest line in the tie), or
   *  `null` while the batch is not tied. `DEF-PAY-10323`. */
  bank_posted_on: string | null;
  /** When the batch was reconciled — `null` while it is only matched. */
  reconciled_at: string | null;
  /** Always `null`. See this interface's own note. */
  reference: string | null;
}

// ── what the four header controls may do ──────────────────────────────────
/** `{allowed, reason}` — and the reason is a CODE; the sentence is ours. */
export interface ActionAvailability {
  allowed: boolean;
  reason: string | null;
}

/**
 * ⚠ **THE SERVER DECIDES AND THE SCREEN RENDERS THE DECISION** (BR-SHL-025).
 * `action_availability` calls `cancel.refusal_for`, which is the same pure
 * function the write path calls — so the reason a clerk is shown BEFORE the
 * click and the reason the service gives AFTER it can never be two different
 * answers. **A screen that worked the status rules out for itself would be a
 * second copy of them, free to drift** (the server's docstring says exactly
 * this, and it is why nothing below is computed here).
 */
export interface PaymentActions {
  /** Always allowed — the three amendable columns, in any status. */
  edit: ActionAvailability & {
    /**
     * ⚠ **THE FIELD IS NAMED, THE CONTROL IS NOT DISABLED.** The tender cannot
     * change once the payment is banked, because deposit batches group by day
     * AND tender — so `Edit` opens and the METHOD field inside it is locked.
     */
    tender_locked: boolean;
  };
  /** Always allowed — a correction is a NEW ROW and needs nothing of this one. */
  correction: ActionAvailability;
  /** `reason` is `cancel_refused_cleared_use_reverse` and friends. */
  cancel: ActionAvailability;
  /** Always allowed — Resend touches no money. */
  receipt: ActionAvailability;
  /**
   * CR-175-BRC10 — **Mark returned**, for an ACH payment the bank sent back.
   * `offered` is the TENDER (ACH only); `reason` is `not_cleared`,
   * `already_returned` or `is_reversal`. Who may press it is the ROLE's —
   * billing clerk or System Admin — and the service refuses everyone else.
   */
  mark_returned: ActionAvailability & { offered: boolean };
}

// ── the receipt rows behind 2·3h's ① ──────────────────────────────────────
/** `pdf_print · email · sms` — the three a receipt goes out on. */
export const RECEIPT_CHANNELS = ["pdf_print", "email", "sms"] as const;
export type ReceiptChannel = (typeof RECEIPT_CHANNELS)[number];

/** One receipt this payment has already had, on one channel. */
export interface ReceiptDelivery {
  channel: string;
  copy_no: number | null;
  /** When it went. `null` = queued and not yet sent. */
  sent_at?: string | null;
  created_at?: string | null;
  status?: string | null;
  to?: string | null;
}

/**
 * The body of `GET /payments/{id}`.
 *
 * ⚠ **THE HISTORY IS NOT IN HERE.** It is the one member that has to be
 * paginated (`NFR-3` — no unpaginated list anywhere, at any tier), so it is its
 * own route. A page that folded it in would be serving an unbounded array on
 * the read a clerk opens most.
 */
export interface PaymentDetail extends PaymentRow {
  source: PaymentSource;
  /** `null` is the ORDINARY answer: most payments are in no batch. */
  reconciled: PaymentReconciliation | null;
  actions: PaymentActions;
  /** `DEF-PAY-10016` — the reason CODE this payment was taken back for
   *  (`nsf`), or `null`. Its own status stays as it was (hard rule 4). */
  reversed_for?: string | null;
  /** `DEF-PAY-10698` · LBX-04 — this payment's reversal as a clerk reads it:
   *  the bank memo and the NSF penalty (charged, or unticked with a reason). */
  reversal?: PaymentReversalFacts | null;
  receipts: ReceiptDelivery[];
  /** The number 2·3h submits back. See `resendReceipt` — it is the guarantee. */
  next_copy_no: number;
  /** Codes, never sentences. Never rendered. See this file's header. */
  unavailable: string[];
  /** CR-161-BRC10 W5 — the utility's own payment fields, as typed on Record
   *  payment. Read-only: nothing on S33 sends them back (hard rule 4). */
  custom_data: Record<string, unknown>;
}

/** One row of ⑦ the history panel — `WHEN · WHAT · WHO · NOTE` (p035). */
/** `DEF-PAY-10698` · LBX-04 — what a reversal said about the bank's words
 *  and the NSF penalty. Every member may be null: an audit row is pruned
 *  like every other (PO 2026-09-23), and the fee BILL stays regardless. */
export interface BounceFacts {
  bank_memo?: string | null;
  nsf_fee_status?: string | null;
  nsf_fee_amount?: string | null;
  nsf_fee_currency?: string | null;
  nsf_fee_invoice_no?: string | null;
  nsf_fee_waived_reason?: string | null;
}

export interface PaymentReversalFacts extends BounceFacts {
  reversal_no: string | null;
  reason: string | null;
}

export interface PaymentHistoryRow extends BounceFacts {
  at: string;
  /**
   * ⚠ **THE AUDIT CODE, NEVER A SENTENCE** — `payment.recorded`,
   * `payment.cancelled`. **The screen holds the words in all eleven
   * catalogues** (B14 rule 35: a catalogue is written in its own language, not
   * translated from English), so a trail cannot end up half in English for a
   * Spanish-speaking clerk.
   */
  what: string;
  /** A NAME, never a user id (B14 rule 31). `null` when the actor is unknown. */
  who: { kind: string | null; name: string | null } | null;
  note: string | null;
  /** `DEF-PAY-10017` — a catalogue KEY when the note is a closed reason code
   *  (`nsf`), so the screen prints *Returned by the bank*, never the code.
   *  Optional: an older server does not send it. */
  note_key?: string | null;
}

export interface PaymentHistoryPage {
  results: PaymentHistoryRow[];
  count: number;
  next: string | null;
  previous: string | null;
}

// ── the writes ────────────────────────────────────────────────────────────
/**
 * 2·3d's four reasons.
 *
 * ⚠ **NOT `REVERSAL_REASONS`, AND NEVER FOLDED INTO THEM.** The server's own
 * comment is the one to keep: *"a cancel is a staff correction on money that
 * never arrived and shares none of them. Conflating the two vocabularies is the
 * exact confusion this whole phase exists to undo, and it would put
 * `wrong_account` in a filter labelled* why the bank returned it*"*.
 */
export const CANCEL_REASONS = [
  "wrong_account",
  "wrong_amount",
  "duplicate",
  "not_taken",
] as const;
export type CancelReason = (typeof CANCEL_REASONS)[number];

export interface CancelPaymentBody {
  reason: CancelReason;
  /** 2·3d's *Note* — *"What happened, in your words."* Optional. */
  note?: string;
  /** The day the cancel counts from. ISO date. */
  cancelled_on: string;
}

export interface CancelledPayment {
  payment_id: string;
  payment_no: string | null;
  /**
   * ⚠ **`false` IS A REPLAY, NOT A FAILURE.** The STATUS is the idempotency key
   * (hard rule 6), so a double-click answers `200` with `created: false` and the
   * customer's account moves once. A screen that treated this as an error would
   * teach a clerk to cancel twice.
   */
  created: boolean;
  status: string;
  amount: string;
  currency: string;
  /** B14 rule 31 — the NUMBER a clerk reads; the id rides beside it for the
   *  screen's own navigation and is never the value of a field. */
  reversing_payment_no: string | null;
  reversing_payment_id: string | null;
  reason: string;
  problems: { code: string; detail?: string }[];
}

export interface ResendReceiptBody {
  channels: string[];
  /**
   * ⚠ **REQUIRED, AND IT IS THE WHOLE IDEMPOTENCY GUARANTEE (hard rule 6).**
   * `GET /payments/{id}` serves `next_copy_no`, so **the number the clerk
   * submits is the number the server just showed them**; a double-click
   * resubmits it, collides with its own row in the DATABASE and comes back
   * `created: false`. **An endpoint that allocated the number itself would hand
   * out 1 and then 2 and post two receipts, while looking perfectly correct.**
   * So this is never computed in the browser — it is echoed.
   */
  copy_no: number;
}

export interface ResentReceipt {
  payment_id: string;
  payment_no: string | null;
  copy_no: number;
  /** `created: false` on a channel is a REPLAY: one copy, not two. */
  queued: { channel: string; message_id?: string | null; created: boolean }[];
  problems: { code: string; detail?: string }[];
}

// ── the four calls ────────────────────────────────────────────────────────
/** `GET /payments/{id}` — `P3.1`. The read whose absence WAS why a payment had
 *  no address. */
export function getPaymentDetail(client: ApiClient, ref: PaymentRef): Promise<PaymentDetail> {
  return client
    .get<PaymentDetail>(`/payments/${encodeURIComponent(ref)}`)
    .then((response) => requireData(response));
}

/** `GET /payments/{id}/history` — `P3.4`, paginated in SQL. What makes Cancel
 *  honest: a cancelled payment does not vanish. */
export function getPaymentHistory(
  client: ApiClient,
  ref: PaymentRef,
  params: { page?: number; page_size?: number } = {},
): Promise<PaymentHistoryPage> {
  // The client builds the query string itself and drops `undefined` — a
  // hand-rolled `URLSearchParams` here would be a second encoder free to
  // disagree with the one every other read uses.
  return client
    .get<PaymentHistoryPage>(`/payments/${encodeURIComponent(ref)}/history`, {
      query: { page: params.page, page_size: params.page_size },
    })
    .then((response) => requireData(response));
}

/** `POST /payments/{id}/cancel` — `P3.2`, the only genuinely missing logic in
 *  the module. Refused on `cleared`, and the refusal NAMES Reverse. */
export function cancelPayment(
  client: ApiClient,
  ref: PaymentRef,
  body: CancelPaymentBody,
): Promise<CancelledPayment> {
  return client
    .post<CancelledPayment>(`/payments/${encodeURIComponent(ref)}/cancel`, body)
    .then((response) => requireData(response));
}

// ── CR-175-BRC10 — a billing clerk marks an ACH payment returned ────────────
/** The two reasons a BANK return carries. The two staff corrections stay a
 *  System Admin's Reverse (decision log 2026-10-07, CR-175-BRC10 (2)). */
export const ACH_RETURN_REASONS = ["nsf", "bank_chargeback"] as const;
export type AchReturnReason = (typeof ACH_RETURN_REASONS)[number];

/** A Nacha return code: `R` and two characters (`R01`, `R1B`). The SERVER's
 *  `_NACHA_RETURN_CODE`, mirrored so the box can say so before the click; the
 *  service still judges it. */
export const NACHA_RETURN_CODE = /^R[0-9A-Z]{2}$/;

export interface MarkReturnedBody {
  /** The BANK's return date, `YYYY-MM-DD` — never a clock. */
  returned_on: string;
  reason: AchReturnReason;
  return_code: string;
  memo?: string;
  /** One per opened dialog (hard rule 6). */
  idempotency_key: string;
}

/** `POST /payments/{id}/mark-returned` — PO 2026-10-07: *"Let billing clerks
 *  mark an ACH payment returned, any day, with a reason and the bank code."* */
export function markReturned(
  client: ApiClient,
  paymentId: string,
  body: MarkReturnedBody,
): Promise<ReversedPayment> {
  return client
    .post<ReversedPayment>(`/payments/${encodeURIComponent(paymentId)}/mark-returned`, body)
    .then((response) => requireData(response));
}

/** `POST /payments/{id}/receipt` — `P3.3`, re-queues the EXISTING document. */
export function resendReceipt(
  client: ApiClient,
  ref: PaymentRef,
  body: ResendReceiptBody,
): Promise<ResentReceipt> {
  return client
    .post<ResentReceipt>(`/payments/${encodeURIComponent(ref)}/receipt`, body)
    .then((response) => requireData(response));
}
