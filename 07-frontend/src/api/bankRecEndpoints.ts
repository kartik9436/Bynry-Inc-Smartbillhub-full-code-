// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-020 (S37) · US-PAY-021 (S38) · US-PAY-022 (S40) ·
//           US-PAY-023 (S39) · US-PAY-015 / US-PAY-018 / US-PAY-019 (the
//           collections position) · US-PAY-012 (the write-off approval queue's
//           two extra name fields)
//           Screens: S37 · S38 · S39 · S40 · S34 · S21
// Rules:    BR-PAY-004 · BR-PAY-016 · BR-PAY-017 · BR-PAY-019 · BR-PAY-020 ·
//           BR-PAY-025 · BR-PAY-028 · BR-PAY-035 · BR-PAY-037 · BR-PAY-040 ·
//           BR-CUS-043 · BR-SHL-011 (the URL grammar) · BR-TEN-043 ·
//           CLAUDE.md rule 2 (every money figure travels with its CHAR(3))
// ───────────────────────────────────────────────────────
// The typed wrappers for the eleven routes the payments SURFACE lane mounted.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE AND NOT AN APPENDIX TO `endpoints.ts`
// ══════════════════════════════════════════════════════════════════════════
// `endpoints.ts` is 6,800 lines and every lane in this repo appends to it, so
// on any given afternoon it holds two or three lanes' half-finished work at
// once. This block was written into it first and taken back out: committing the
// file would have shipped another lane's mid-edit chart-of-accounts types along
// with these wrappers. One family, one file, one lane's diff — and nothing here
// re-exports or shadows anything `endpoints.ts` already publishes.
//
// ══════════════════════════════════════════════════════════════════════════
// ALL ELEVEN ROUTES ARE SERVED
// ══════════════════════════════════════════════════════════════════════════
// `apps/payments/api.py` mounts them and `config/urls.py` already includes that
// module, so unlike the `GET /invoices` family these types describe a LIVE
// contract rather than a proposed one. They are read off the server's own
// payload builders (`apps/payments/bankrec_read.py` and `collections_read.py`),
// field for field: a field the server does not send is not typed here.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE TYPE DECISION THAT MATTERS: `string | null` IS NOT `?? "0"`
// ══════════════════════════════════════════════════════════════════════════
// `bank_total` and `difference` are nullable because a batch the bank has not
// shown carries NO bank figure at all — the prototype's "pending" column.
// Typing them `string` would invite exactly the DEF-127 defect this release is
// named after: a figure nobody filled rendering as a figure somebody counted.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Throwing beats handing a screen a silent `null` it will render as blank —
 *  the same rule `endpoints.ts` keeps, restated here rather than exported from
 *  there so this file adds no coupling to a file three lanes are editing. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// S37 · S38 · S39 · S40 — deposits and bank reconciliation (US-PAY-020..023)
// and the collections POSITION (US-PAY-015 · US-PAY-018 · US-PAY-019)
// ══════════════════════════════════════════════════════════════════════════
// ALL ELEVEN ROUTES BELOW ARE SERVED. `apps/payments/api.py` mounts them and
// `config/urls.py` already includes that module, so unlike the `GET /invoices`
// family these types describe a live contract rather than a proposed one.
//
// THE ONE TYPE DECISION THAT MATTERS HERE: `bank_total` and `difference` are
// `string | null`, and the null is NOT an optional that a screen may `?? "0"`.
// A batch the bank has not shown carries no bank figure at all — that is the
// prototype's "pending" column — and typing them `string` would invite exactly
// the DEF-127 defect this release is named after: a figure nobody filled
// rendering as a figure somebody counted.

/** One named thing a payments read model cannot answer, with the rule behind
 *  it. Same shape as `LedgerUnavailable` and as `PaymentsProblem`; kept as its
 *  own name so a payments gap is never rendered through a ledger catalogue. */
export interface BankRecGap {
  code: string;
  br_ref: string;
  detail: string;
}

/** `apps.payments.bankrec_models.BATCH_STATUSES`, in the order the engine
 *  declares them — cut → the bank spoke → tied → LOCKED. */
export const DEPOSIT_BATCH_STATUSES = ["in_transit", "unmatched", "matched", "reconciled"] as const;
export type DepositBatchStatus = (typeof DEPOSIT_BATCH_STATUSES)[number];

export interface DepositBatchRow {
  id: string;
  /** `DEP-260808-CHK` — year-bearing since the PO's ruling of 2026-08-12
   *  (OQ-162, *"Add the year + Date is important"*). It is a LABEL: the banking
   *  date is `deposited_on`, a field in its own right, and nothing may parse a
   *  date back out of this string. */
  code: string;
  method_code: string | null;
  method_name: string | null;
  /** `CR-186-BRC10` (PO 2026-10-21): one batch per till or provider per day,
   *  ALL tenders together. True on every batch made since; its per-tender
   *  totals are on the detail (`tender_totals`). Optional for an older server. */
  all_tenders?: boolean;
  /** The provider or channel a system till banks — `invoice_cloud`,
   *  `paymentus`, `lockbox`, `office` — or null for a person's till. */
  channel?: string | null;
  deposited_on: string | null;
  recorded_total: string | null;
  /** NULL until a statement line is tied — *the bank has not shown us this
   *  money yet*. Never render it as 0. */
  bank_total: string | null;
  /** NULL for the same reason: it is `bank − recorded` and there is no bank
   *  side yet. A zero here would draw a perfectly reconciled deposit. */
  difference: string | null;
  currency: string;
  payment_count: number | null;
  status: DepositBatchStatus | string;
  /** BR-PAY-004's lock, SERVED rather than derived on the client from
   *  `status === "reconciled"`. A screen that computed the rule would be a
   *  second copy of it, free to drift the day a fifth status arrives. */
  locked: boolean;
}

export interface DepositBatchKpis {
  deposited_total: string | null;
  batch_count: number;
  matched_total: string;
  matched_count: number;
  reconciled_total: string;
  reconciled_count: number;
  unmatched_total: string;
  unmatched_count: number;
  /** Its OWN tile. Money we believe we banked and money the bank agrees we
   *  banked are different facts; adding them makes one confident wrong number. */
  in_transit_total: string;
  in_transit_count: number;
  currency: string;
}

/** A drawer day with cleared money nobody has banked yet. The list is computed
 *  from the payments themselves because BR-TEN-043 forbids the server reading a
 *  clock to pick "today" — so an EMPTY list means everything is banked, which is
 *  a different sentence from "we could not work out what day it is". */
export interface CuttableDay {
  day: string | null;
  unbatched_total: string | null;
  currency: string;
}

/** The GL account S40 pre-selects for a processor fee, by DESIGNATION. The
 *  NUMBER never crosses the wire: the chart is tenant-customisable (US-LED-005)
 *  and the prototype's "6200 Merchant Fees" is in no signed chart (DEF-067) —
 *  the signed one has 6800 Bank fees. `available: false` means the tenant has
 *  designated none, and the form then ASKS rather than substituting. */
export interface BankFeeAccount {
  available: boolean;
  gl_account_id: string | null;
  designation: string;
}

export interface StatementImportRow {
  id: string;
  bank_account_name: string | null;
  period_start: string | null;
  period_end: string | null;
  file_name: string | null;
  line_count: number;
  imported_at: string | null;
}

/** `P2.10` — the money this list is deliberately NOT showing: batches whose
 *  counter is still open. Since phase 0's re-key a batch exists from the moment
 *  its till opens, and a drawer still taking money is not bankable (blueprint
 *  p059: the batch *"becomes bankable"* at Close). The server holds those rows
 *  back and serves this COUNT beside the ones it kept, because a declared blind
 *  spot with no number attached reads exactly like an empty one. */
export interface StillOpenCounters {
  batch_count: number;
  recorded_total: string;
  currency: string;
}

/** A chip the SERVER offers, rather than one the screen typed out (`P1.4`).
 *
 *  ⚠ **TWO SHAPES, AND THE DIFFERENCE IS WHOSE WORD IT IS.** A STATUS is an
 *  enum this product owns, so it travels as a value plus a catalogue key the
 *  browser resolves — a server does not speak a clerk's language
 *  (BR-SHL-023). A METHOD is a tenant's own row, so its label IS the tenant's
 *  text: there is no catalogue key for *Cheque* on a utility that calls it
 *  something else. */
export interface ServedChip {
  value: string;
  label_key?: string;
  label?: string;
}

export interface DepositBatchesResponse {
  /** The four keys every list in this product serves. `count` is over the
   *  FILTERED SET, from a `COUNT(*)` — never `results.length`. */
  count: number;
  next: string | null;
  previous: string | null;
  results: DepositBatchRow[];
  /** ⚠ **OVER THE FILTERED SET, NEVER OVER THE PAGE** (`DEF-PAY-6554`). Folding
   *  the page would make *In transit* shrink as a clerk walked forward. */
  kpis: DepositBatchKpis;
  /** `P1.4` — the chips, so a status added server-side appears on screen with
   *  no front-end change. */
  statuses: ServedChip[];
  methods: ServedChip[];
  still_open: StillOpenCounters;
  unavailable: BankRecGap[];
  cuttable_days: CuttableDay[];
  fee_account: BankFeeAccount;
  statement_imports: StatementImportRow[];
}

/** `GET /deposit-batches` — one PAGE of screen 3·1's list, its KPI strip, its
 *  chip vocabularies and both of its controls.
 *
 *  ⚠ **THIS SERVED EVERY BATCH THE TENANT HELD UNTIL 2026-09-24, AND THIS
 *  COMMENT CARRIED THAT AS A DECISION (`DEF-PAY-6554` · `NFR-3` · `P1.2`).** It
 *  read *"Unpaginated by design: a utility under 3,000 connections cuts a
 *  handful of batches a day, and a page of a reconciliation list is a list that
 *  lies about how much is unmatched."* The ceiling moved to 40,000 accounts on
 *  2026-09-06; the second half is answered rather than overruled, because
 *  `kpis` describes the whole filtered set on every page.
 *
 *  `q` is `P1.7` — batch code, bank reference or cheque number, two characters
 *  minimum (IS-3). */
export async function getDepositBatches(
  params: {
    status?: string;
    method?: string;
    q?: string;
    sort?: string;
    dir?: string;
    page?: number;
    per?: number;
  } = {},
  client: ApiClient = api,
): Promise<DepositBatchesResponse> {
  const query: Record<string, string> = {};
  if (params.status !== undefined && params.status !== "") {
    query["f.status"] = params.status;
  }
  if (params.method !== undefined && params.method !== "") {
    query["f.method"] = params.method;
  }
  if (params.q !== undefined && params.q !== "") {
    query.q = params.q;
  }
  if (params.sort !== undefined && params.sort !== "") {
    query.sort = params.sort;
  }
  if (params.dir !== undefined && params.dir !== "") {
    query.dir = params.dir;
  }
  if (params.page !== undefined && params.page > 1) {
    query.page = String(params.page);
  }
  if (params.per !== undefined) {
    query.per = String(params.per);
  }
  return requireData(await client.get<DepositBatchesResponse>("/deposit-batches", { query }));
}

export interface CutDepositBatchesBody {
  /** The POSTING day — the physical drawer day (BR-PAY-025 / PO ruling RQ-5),
   *  never the day the bank credits it. Chosen by the clerk from
   *  `cuttable_days`, never defaulted to a clock. */
  day: string;
  /** BR-TEN-043 — the caller names the moment. A resumed run and a replay must
   *  stamp the SAME instant rather than two. */
  occurred_at: string;
}

export interface CutDepositBatchesResult {
  day: string;
  payments_batched: number;
  batches: {
    id: string;
    code: string;
    method_code: string;
    deposited_on: string;
    recorded_total: string;
    currency: string;
    payment_count: number;
    status: string;
    created: boolean;
  }[];
  /** Cleared money that could NOT be batched, each with its reason. Never
   *  dropped — a payment nobody banked is a real thing to look at. */
  skipped: { payment_id: string; payment_no: string | null; reason: string; detail: string }[];
}

export async function cutDepositBatches(
  body: CutDepositBatchesBody,
  client: ApiClient = api,
): Promise<CutDepositBatchesResult> {
  return requireData(await client.post<CutDepositBatchesResult>("/deposit-batches/cut", body));
}

export interface DepositBatchMember {
  payment_id: string;
  payment_no: string | null;
  /** The cheque number the prototype prints as "#4021". NULL for cash — an
   *  absence the screen states, never an empty string that reads as a missing
   *  cheque number. */
  confirmation: string | null;
  /** `P3.10` — this row is a CORRECTION'S SOURCE, not only its subject.
   *  `POST /payments/{id}/correct-reference` takes the cheque number AND the
   *  memo, so a form opened from this row pre-fills both; without it the memo
   *  box would open blank over a sentence that exists, and the first thing a
   *  clerk typed would replace it. */
  memo: string | null;
  account_id: string;
  account_no: string | null;
  amount: string | null;
  /** `P3.11` — how much of this payment has COME BACK, positive, `"0.000000"`
   *  when none of it has (`BR-PAY-884`'s Σ). Never absent: the server looked at
   *  every member, so zero here is a measurement rather than a gap.
   *
   *  ⚠ **IT IS SERVED BECAUSE IT CANNOT BE DERIVED ON THIS SIDE**
   *  (`DEF-PAY-6651`). A reversing row is created with no `deposit_batch_id`,
   *  and hard rule 4 forbids moving the original's amount or status, so **no
   *  member row changes when a member is reversed** — Σ`amount` is identically
   *  `recorded_total` for ever. */
  reversed_amount: string | null;
  currency: string;
  status: string;
  posted_at: string | null;
  cleared_at: string | null;
}

export interface BankLinePanel {
  bank_line_id: string;
  posted_on: string | null;
  reference: string | null;
  amount: string | null;
  currency: string;
  line_no: number | null;
  bank_account_name: string | null;
  bank_account_mask: string | null;
  statement_import_id: string | null;
  period_start: string | null;
  period_end: string | null;
}

/** One append-only row of the S39 reconciliation trail (US-PAY-023 TC-4 — it is
 *  kept forever, and Unreconcile does not truncate it). `detail` is forwarded
 *  whole by the server rather than cherry-picked, so a new event's payload
 *  arrives intact. */
export interface BatchTrailRow {
  id: string;
  event: string;
  occurred_at: string | null;
  actor_id: string | null;
  detail: Record<string, unknown>;
}

export interface BatchResolutionRow {
  id: string;
  reason_code: string;
  gl_account_id: string | null;
  amount: string | null;
  currency: string;
  note: string | null;
  journal_entry_id: string | null;
  actor_id: string | null;
}

export interface DepositBatchTenderTotal {
  method_code: string | null;
  method_name: string | null;
  amount: string | null;
  count: number;
}

export interface DepositBatchDetail {
  batch: DepositBatchRow;
  /** `P3.11` — what the members STILL STAND FOR: Σ(`amount` − `reversed_amount`),
   *  summed server-side on the `NUMERIC(18,6)` grid.
   *
   *  It equals `batch.recorded_total` until a payment inside the batch is
   *  reversed. A reversal inside a LOCKED batch is lawful — the frozen total is
   *  right, because the bank statement it was agreed against did not change —
   *  so the two figures legitimately part company and **no screen said so**
   *  (Finance blueprint p049). Showing the pair changes no rule. */
  live_total: string | null;
  /** `CR-186-BRC10` ruling 3 — a batch carries a total PER TENDER. Dana ·
   *  14 Oct: cash 300.00 + cheques 500.00 = 800.00. Optional for an older server. */
  tender_totals?: DepositBatchTenderTotal[];
  members: DepositBatchMember[];
  /** NULL, not an object of nulls: "the bank has not shown us this deposit" is
   *  a STATE the screen draws as its own sentence, and a panel of empty fields
   *  reads as data that failed to load. */
  bank_line: BankLinePanel | null;
  trail: BatchTrailRow[];
  resolutions: BatchResolutionRow[];
  unavailable: BankRecGap[];
}

export async function getDepositBatch(
  batchId: string,
  client: ApiClient = api,
): Promise<DepositBatchDetail> {
  return requireData(await client.get<DepositBatchDetail>(`/deposit-batches/${batchId}`));
}

/** The four states S38 step 2 draws as its KPI tiles. `matched_off_by` is the
 *  prototype's "Off by $100" / "Fees?" — linked by a human and still owed an
 *  explanation, which is the S40 modal's whole job. */
export const BANK_LINE_STATES = [
  "auto",
  "matched_off_by",
  "needs_a_look",
  "not_in_our_system",
  // ── CR-059 W8 · the two states the server has served since 2026-09-01 ──
  // `set_matched` is CS-17's many-to-one tie and `explained` is CS-16's
  // reason-and-GL on a LINE. They were absent from this list while
  // `_statement_line_row` had been returning both, so every such row fell
  // through `state: BankLineState | string` and rendered as its raw code.
  "set_matched",
  "explained",
] as const;
export type BankLineState = (typeof BANK_LINE_STATES)[number];

export interface StatementLineRow {
  bank_line_id: string;
  posted_on: string | null;
  reference: string | null;
  amount: string | null;
  currency: string;
  line_no: number | null;
  batch_id: string | null;
  batch_code: string | null;
  recorded_total: string | null;
  difference: string | null;
  state: BankLineState | string;
  /** CS-17 — a line the bank posted as part of ONE combined credit. `batch_id`
   *  and `batch_code` stay null on such a row because a set has no single
   *  batch; the SET is what the row names, and serving one of its several
   *  batches would be a half-truth a screen would render as the whole answer. */
  match_set_id?: string | null;
  match_set_batch_codes?: string[];
  match_set_total?: string | null;
  /** CS-16 — what a person said this line is, and where it posts. `posted` is
   *  TRUE for a returned line matched to its payment and for a bank-fee line
   *  (LBX-05, G3 ruled 2026-10-30) and false for an ordinary explanation,
   *  which still posts nothing. */
  reason_code?: string | null;
  gl_account_id?: string | null;
  explained_amount?: string | null;
  note?: string | null;
  posted?: boolean;
  /** LBX-05 — the payment a matched return reversed. */
  returned_payment_no?: string | null;
  returned_cheque?: string | null;
  /** P1 a1-3 (PO 2026-10-31) — whose cheque came back: the account NUMBER
   *  (never an id, B14 rule 31) and the customer's name. */
  returned_account_no?: string | null;
  returned_customer_name?: string | null;
  /** P1 a2-3 — the cheque number in the line's own words, which Match to
   *  payment's search opens on. Null when the text carries none. */
  search_hint?: string | null;
  /** LBX-05 — what this line offers: a money-out line can be matched to the
   *  payment it returns, or posted as the bank's fee. */
  actions?: ("match_return" | "bank_fee")[];
}

export interface StatementReview {
  statement: {
    id: string;
    bank_account_name: string | null;
    bank_account_mask: string | null;
    period_start: string | null;
    period_end: string | null;
    file_name: string | null;
    line_count: number;
    imported_at: string | null;
    imported_by: string | null;
    /** CS-14 — the bank's OWN figures, or null. NEVER `?? "0.00"`: a statement
     *  imported before 2026-09-01 carries no balances and nothing backfills
     *  them, so a zero here would print a bank balance for a live account
     *  nobody read. */
    opening_balance?: string | null;
    closing_balance?: string | null;
  };
  rows: StatementLineRow[];
  tiles: {
    lines: number;
    auto: number;
    matched_off_by: number;
    needs_a_look: number;
    not_in_our_system: number;
    /** CR-059 W8 — each its OWN tile, never folded into a count that already
     *  meant something else. Optional because a deployment serving the
     *  pre-W8 body has neither, and `?? 0` on a tile is a count nobody made. */
    set_matched?: number;
    explained?: number;
  };
  /** The batches a human may pair a line with by hand. Empty is an honest
   *  "there is nothing of ours left to tie". */
  open_batches: DepositBatchRow[];
  currency: string;
  unavailable: BankRecGap[];
}

export interface BankAccountOption {
  id: string;
  name: string;
  mask: string | null;
}

export async function getBankAccounts(client: ApiClient = api): Promise<BankAccountOption[]> {
  return requireData(await client.get<{ rows: BankAccountOption[] }>("/bank-accounts")).rows;
}

export interface ImportBankStatementBody {
  bank_account_id: string;
  period_start: string;
  period_end: string;
  /** The file's bytes, base64. JSON end to end: a multipart branch here would
   *  be a second request shape for one operation, and nothing in the API layer
   *  parses a bank file — `lockbox.py` is the only parser. */
  file_base64: string;
  file_name?: string;
  imported_at: string;
  /** W3 (`DEF-PAY-10767`) — the statement's own opening and closing balance,
   *  as printed (CS-14). Decimal strings; the server stores them on the import. */
  opening_balance?: string;
  closing_balance?: string;
}

export async function importBankStatement(
  body: ImportBankStatementBody,
  client: ApiClient = api,
): Promise<{ statement_import_id: string; line_count: number; review: StatementReview }> {
  return requireData(
    await client.post<{
      statement_import_id: string;
      line_count: number;
      review: StatementReview;
    }>("/bank-statements", body),
  );
}

export async function getStatementReview(
  statementImportId: string,
  client: ApiClient = api,
): Promise<StatementReview> {
  return requireData(await client.get<StatementReview>(`/bank-statements/${statementImportId}`));
}

/** A HUMAN naming a pairing the exact rule could not make. **It is not a force
 *  match** — nothing reconciles, and the difference it returns is what S40 must
 *  then explain to zero (BR-PAY-035 keeps "Force match anyway" superseded). */
export async function matchBankLine(
  batchId: string,
  body: { bank_line_id: string; occurred_at: string },
  client: ApiClient = api,
): Promise<{ batch_id: string; difference: string; currency: string }> {
  return requireData(
    await client.post<{ batch_id: string; difference: string; currency: string }>(
      `/deposit-batches/${batchId}/match`,
      body,
    ),
  );
}

/** One explanation of one part of a difference — BR-PAY-019's *reason AND GL*.
 *  `amount` is a SIGNED decimal string: the card day's processor fee is
 *  `"-147.50"`. The server checks the sum against the difference and refuses
 *  anything that leaves a residual. */
export interface BankRecResolutionInput {
  reason_code: string;
  gl_account_id: string;
  amount: string;
  note?: string;
}

export interface ReconcileBatchBody {
  posted_at: string;
  resolutions: BankRecResolutionInput[];
  /** Defaults SERVER-side to the bank's own posting day, because that is the
   *  day the bank confirmed the money and the PO's ruling makes confirmation
   *  the event that realises it. Stated only when a clerk means a different
   *  book date (OQ-107). */
  entry_date?: string;
  note?: string;
}

export interface ReconcileBatchResult {
  batch_id: string;
  code: string;
  recorded_total: string;
  bank_total: string;
  difference: string;
  explained: string;
  currency: string;
  journal_entry_id: string;
  posting_key: string;
  created: boolean;
  resolutions: Record<string, string>[];
  unavailable: BankRecGap[];
}

export async function reconcileDepositBatch(
  batchId: string,
  body: ReconcileBatchBody,
  client: ApiClient = api,
): Promise<ReconcileBatchResult> {
  return requireData(
    await client.post<ReconcileBatchResult>(`/deposit-batches/${batchId}/reconcile`, body),
  );
}

export async function unreconcileDepositBatch(
  batchId: string,
  body: { reason: string; posted_at: string; entry_date?: string },
  client: ApiClient = api,
): Promise<Record<string, unknown>> {
  return requireData(
    await client.post<Record<string, unknown>>(`/deposit-batches/${batchId}/unreconcile`, body),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-059 wave W8 — the four reconciliation routes (tasks 43 · 44 · 45 · 46)
// ══════════════════════════════════════════════════════════════════════════
// All four are mounted in `apps/payments/api.py` and all four were unreachable
// from the product until the statement screen was built: four finished
// backends behind one screen nobody had drawn, which is hard-won law 2 at
// feature scale for the second time in this module.
//
// ⚠ **THE ONE TYPE DECISION HERE, AND IT IS THE SAME ONE THIS FILE ALREADY
// MADE ONCE.** `bank_closing_balance`, `book_cash_balance` and
// `difference_bank_less_books` are `string | null` and the null is NOT an
// optional a screen may `?? "0.00"`. A statement imported before the balance
// columns existed carries no bank figure, and a chart with no designated cash
// account has no book figure — so "we could not do the sum" and "the two
// agree" are different answers, and only one of them is good news.

/** One reconciling item — a deposit still in transit, an outstanding refund
 *  cheque, or a statement line nobody has explained.
 *
 *  ⚠ **NO `sign` AND NO `signed_amount`, DELIBERATELY.** The PO's ruling of
 *  2026-09-02 makes these items the EXPLANATION of the difference and never
 *  addends to either side, so nothing the server sends says which way an item
 *  would move a balance — because nothing moves one. */
export interface ReconcilingItemRow {
  /** A deposit batch or an issued refund. Absent on a statement-line row. */
  id?: string;
  /** `DEP-260808-CHK` — the LABEL a clerk reads (B14 rule 31). */
  code?: string;
  deposited_on?: string | null;
  reference?: string | null;
  issued_on?: string | null;
  bank_line_id?: string;
  line_no?: number | null;
  posted_on?: string | null;
  amount: string | null;
  /** Measured from the STATEMENT's own period end and never from a clock, so
   *  re-printing March's reconciliation in June shows the ages the person who
   *  signed it saw. Null when either date is missing — an age nobody can
   *  compute is not zero days old. */
  age_days: number | null;
  /** P2 = A (PO 2026-10-31) — an unexplained line the bank took OUT offers
   *  Match to payment and Bank fee here too; a credit offers neither. */
  actions?: ("match_return" | "bank_fee")[];
  search_hint?: string | null;
}

export const RECONCILING_ITEM_CODES = [
  "deposits_in_transit",
  "outstanding_refunds",
  "unexplained_lines",
] as const;
export type ReconcilingItemCode = (typeof RECONCILING_ITEM_CODES)[number];

export interface ReconcilingItem {
  code: ReconcilingItemCode | string;
  amount: string | null;
  count: number;
  as_of: string | null;
  oldest_age_days: number | null;
  rows: ReconcilingItemRow[];
}

/** `GET /bank-statements/{id}/reconciliation` — CS-14's period statement.
 *
 *  It states TWO FACTS and explains the gap; it adjusts neither side. There is
 *  deliberately no adjusted balance anywhere on this body. */
export interface ReconciliationStatement {
  statement: {
    id: string;
    bank_account_name: string | null;
    bank_account_mask: string | null;
    period_start: string | null;
    period_end: string | null;
    opening_balance: string | null;
    closing_balance: string | null;
  };
  reconciling_items: ReconcilingItem[];
  /** Lines carrying a reason and a GL account from which NOTHING was posted
   *  (batch decision G3, unruled). Its own line, never folded into the
   *  tie-out: the books have not caught up and pretending otherwise hides a
   *  real difference. */
  explained_not_posted: { amount: string | null; count: number };
  /** LBX-05 — lines that ARE in the books: a returned cheque matched to its
   *  reversal and the bank's fee. Already inside `book_cash_balance`. */
  posted_lines?: {
    amount: string | null;
    count: number;
    rows: PostedStatementLine[];
  };
  bank_closing_balance: string | null;
  book_cash_balance: string | null;
  /** Bank LESS books. The key says which way round the subtraction runs so a
   *  screen cannot render it with the sign reversed. */
  difference_bank_less_books: string | null;
  /** A FACT, not a verdict. A period with legitimate deposits in transit is
   *  properly reconciled and reads `false` here, so no screen may label it
   *  "not reconciled". Null — never false — when the comparison could not be
   *  made at all. */
  bank_equals_books: boolean | null;
  currency: string;
  unavailable: BankRecGap[];
}

export async function getReconciliationStatement(
  statementImportId: string,
  client: ApiClient = api,
): Promise<ReconciliationStatement> {
  return requireData(
    await client.get<ReconciliationStatement>(
      `/bank-statements/${statementImportId}/reconciliation`,
    ),
  );
}

/** One of this utility's own difference reasons — the explain form's picker
 *  (CS-18).
 *
 *  An EMPTY list is not a broken screen: the reason list is discretionary
 *  reference data, every tenant provisioned before 2026-09-01 has none, and
 *  the server still accepts any non-blank reason from them. */
export interface DifferenceReasonOption {
  code: string;
  name: string;
  default_gl_account_id: string | null;
  is_system: boolean;
}

export interface DifferenceReportRow {
  reason_code: string;
  gl_account_id: string;
  /** The ledger's own CODE and NAME beside the id, so no database id is ever
   *  the visible value of a field (B14 rule 31). Null when the chart could not
   *  name the account, and the row then renders a stated absence. */
  gl_account_code: string | null;
  gl_account_name: string | null;
  /** SIGNED, exactly as stored: a −30.00 bank charge and a +12.40 interest
   *  credit report as −17.60 and never as 42.40. */
  total: string | null;
  count: number;
  batch_count: number;
  line_count: number;
  posted_count: number;
}

export interface DifferenceReport {
  period_start: string | null;
  period_end: string | null;
  rows: DifferenceReportRow[];
  total: string | null;
  resolution_count: number;
  currency: string;
  unavailable: BankRecGap[];
  /** The picker's own vocabulary, riding with the report so the explain form
   *  offers exactly what the report groups by (G13 / hard-won law 2: an
   *  optional prop nothing passes is a control that does not exist). */
  reasons: DifferenceReasonOption[];
}

/** `GET /bank-rec/differences?from=&to=` — CS-18's report. Both dates are
 *  REQUIRED: a period defaulting to "everything" answers a question nobody
 *  asked and keeps answering it as the register grows. */
export async function getDifferenceReport(
  params: { from: string; to: string },
  client: ApiClient = api,
): Promise<DifferenceReport> {
  return requireData(
    await client.get<DifferenceReport>("/bank-rec/differences", {
      query: { from: params.from, to: params.to },
    }),
  );
}

export interface ResolveBankLineBody {
  reason_code: string;
  gl_account_id: string;
  /** A SIGNED decimal string, and the sign is the clerk's to state. */
  amount: string;
  /** BR-TEN-043 — the caller names the moment; this layer reads no clock. */
  occurred_at: string;
  note?: string;
}

export interface BankLineResolution {
  resolution_id: string;
  bank_line_id: string;
  reason_code: string;
  gl_account_id: string;
  amount: string;
  currency: string;
  /** `false` on a replay of the SAME explanation, which answers 200 with the
   *  row that already exists. A red error for a button that worked is a wrong
   *  answer a clerk would act on. */
  created: boolean;
  /** ALWAYS null and ALWAYS false — batch decision G3 is unruled, so an
   *  explanation records why the bank moved money we did not and posts
   *  nothing. Typed as the literal so no screen can render it as settled. */
  journal_entry_id: null;
  posted: false;
  unavailable: BankRecGap[];
}

/** `POST /bank-lines/{id}/resolve` — CS-16's S40, opened from a LINE. */
// ── LBX-05 (G3 ruled 2026-10-30) — a line the bank took OUT ───────────────

export interface PostedStatementLine {
  bank_line_id: string;
  line_no: number | null;
  posted_on: string | null;
  reference: string | null;
  amount: string | null;
  kind: "returned_item" | "bank_fee" | string;
  payment_no: string | null;
  cheque: string | null;
  /** P1 a1-3 — the account NUMBER and customer a returned line matched. */
  account_no?: string | null;
  customer_name?: string | null;
}

export interface ReturnCandidate {
  payment_id: string;
  payment_no: string | null;
  cheque: string | null;
  account_id: string;
  account_no: string | null;
  amount: string;
  posted_on: string;
  already_reversed: boolean;
  reversal_id: string | null;
  reversed_on: string | null;
  reference_match: boolean;
}

export interface FeeCandidate {
  payment_id: string;
  payment_no: string | null;
  cheque: string | null;
  amount: string;
  reversed_on: string;
  journal_entry_id: string;
}

export interface LinePostingResult {
  resolution_id: string;
  bank_line_id: string;
  reason_code: string;
  amount: string;
  currency: string;
  created: boolean;
  journal_entry_id: string | null;
  posted: boolean;
  reversal_payment_id: string | null;
  original_payment_id: string | null;
  reversed_now: boolean;
}

export async function getReturnCandidates(
  bankLineId: string,
  query: string,
  client: ApiClient = api,
): Promise<ReturnCandidate[]> {
  const suffix = query.trim() === "" ? "" : `?q=${encodeURIComponent(query.trim())}`;
  const body = requireData(
    await client.get<{ rows: ReturnCandidate[] }>(
      `/bank-lines/${bankLineId}/return-candidates${suffix}`,
    ),
  );
  return body.rows;
}

export async function matchReturnedLine(
  bankLineId: string,
  body: {
    payment_id: string;
    occurred_at: string;
    nsf_fee_waived?: boolean;
    nsf_fee_waive_reason?: string;
    /** P1 a2-2 — the clerk's Bank memo (≤ 60; blank is none). Absent keeps
     *  the line's own words. */
    bank_memo?: string;
  },
  client: ApiClient = api,
): Promise<LinePostingResult> {
  return requireData(
    await client.post<LinePostingResult>(`/bank-lines/${bankLineId}/match-return`, body),
  );
}

export async function getFeeCandidates(
  bankLineId: string,
  client: ApiClient = api,
): Promise<FeeCandidate[]> {
  const body = requireData(
    await client.get<{ rows: FeeCandidate[] }>(`/bank-lines/${bankLineId}/fee-candidates`),
  );
  return body.rows;
}

export async function explainBankFeeLine(
  bankLineId: string,
  body: { occurred_at: string; payment_id?: string },
  client: ApiClient = api,
): Promise<LinePostingResult> {
  return requireData(
    await client.post<LinePostingResult>(`/bank-lines/${bankLineId}/bank-fee`, body),
  );
}

export async function resolveBankLine(
  bankLineId: string,
  body: ResolveBankLineBody,
  client: ApiClient = api,
): Promise<BankLineResolution> {
  return requireData(
    await client.post<BankLineResolution>(`/bank-lines/${bankLineId}/resolve`, body),
  );
}

export interface MatchSetBody {
  bank_line_ids: string[];
  batch_ids: string[];
  occurred_at: string;
  note?: string;
}

export interface MatchSetResult {
  match_set_id: string;
  matched_total: string;
  currency: string;
  bank_line_ids: string[];
  batch_ids: string[];
  /** The batch LABELS, so the confirmation names `DEP-260808-CHK` rather than
   *  a uuid (B14 rule 31). */
  batch_codes: string[];
  created: boolean;
  unavailable: BankRecGap[];
}

/** `POST /bank-rec/match-set` — CS-17's many-to-one tie.
 *
 *  The PO's own case (2026-08-12, OQ-161): $2,840.00 of cheques and $14,280.00
 *  of ACH banked the same afternoon and posted by the bank as ONE credit of
 *  $17,120.00 — money nobody could ever reconcile under the 1:1 link.
 *
 *  The two sides must foot EXACTLY. The server refuses a set that does not tie
 *  and names both sums; nothing here apportions a difference, because nothing
 *  rules how to apportion one across five members. */
export async function createMatchSet(
  body: MatchSetBody,
  client: ApiClient = api,
): Promise<MatchSetResult> {
  return requireData(await client.post<MatchSetResult>("/bank-rec/match-set", body));
}

// ── The collections position (US-PAY-015 · US-PAY-018 · US-PAY-019) ────────

export interface LadderBoardRow {
  /** ⚠ NEVER RENDER THIS. `account_id` is a database primary key, and B14 rule
   *  31 (ratified 2026-08-30, PO verbatim *"no Databse ID on screen - that is a
   *  rule"*) forbids one reaching a utility user. It is here to key rows and to
   *  address the API, nothing else. The visible reference is `account_no`
   *  below. This screen DID render it — a clerk read
   *  `01a046dd-d809-7e20-81a3-87b1eddc1b64` where the sibling Outstandings tab
   *  read `AC-2026-00048` — which is DEF-2580, fixed 2026-09-01 under CR-059. */
  account_id: string;
  /** The HUMAN-FACING account reference, e.g. `AC-2026-00048` — the value a
   *  screen may show. `null` when the account genuinely has no number, which
   *  the screen states in words; it never falls back to `account_id` and never
   *  draws an empty cell. Blank is normalised to `null` in the read model
   *  because `Account.account_no` is a `TextField()`, so an unnumbered account
   *  holds `""` rather than NULL and `""` would slip past a `??` fallback. */
  account_no: string | null;
  balance: string;
  currency: string;
  oldest_due_on: string | null;
  /** The rung ALREADY SENT and the day it went — US-PAY-015 TC-4's *"tier
   *  already sent Jul 30"*, which is what stops a manual send doubling one. */
  current_tier: string | null;
  tier_sent_on: string | null;
  last_notice_on: string | null;
  plan_paused: boolean;
  plan_pause_reason: string;
  plan_id: string | null;
  medical_hold: boolean;
  /** THREE-VALUED ON PURPOSE. `true` = the ladder steps this account today;
   *  `false` = a rule stopped it and `skip_reason` says which; **`null` = this
   *  deployment cannot say**, because no balance floor could be read. "We
   *  cannot say" and "it will not run" are different answers and a screen must
   *  not draw them the same. */
  runs: boolean | null;
  next_rung: string | null;
  next_step_on: string | null;
  skip_reason: string | null;
  /** null, never 0, when no unpaid bill carries a due date — a bill nobody can
   *  place in time cannot be chased on a schedule anchored to time. */
  days_late: number | null;
  detail_code: string;
}

export interface LadderBoardResponse {
  as_of: string;
  rows: LadderBoardRow[];
  rungs: string[];
  /** False when the ladder's balance floor could not be read. The board still
   *  lists every account, balance and tier already sent; only the NEXT step is
   *  absent, with its reason on `problems`. */
  next_step_available: boolean;
  intervals: { reminder_days?: number; tier_days?: number[]; final_hours?: number };
  tiles: {
    accounts: number;
    at_tier: Record<string, number>;
    not_started: number;
    paused: number;
    due_today: number;
  };
  problems: BankRecGap[];
}

/** `GET /collections/ladder` — a PREVIEW that steps nothing.
 *
 *  `POST /collections/run` sends: it writes the notice, advances the tier and
 *  records a history row even for a skip. This is the look-before-you-send that
 *  did not exist. */
export async function getCollectionsLadder(
  params: { as_of: string; balance_floor?: string; partial_pause_percent?: string },
  client: ApiClient = api,
): Promise<LadderBoardResponse> {
  const query: Record<string, string> = { as_of: params.as_of };
  if (params.balance_floor !== undefined && params.balance_floor !== "") {
    query.balance_floor = params.balance_floor;
  }
  if (params.partial_pause_percent !== undefined && params.partial_pause_percent !== "") {
    query.partial_pause_percent = params.partial_pause_percent;
  }
  return requireData(await client.get<LadderBoardResponse>("/collections/ladder", { query }));
}

// ═══════════════════════════════════════════════════════════════════════════
// CR-138-BRC07 · P4.14 — SEND ONE RUNG BY HAND, OVER A SELECTION (7·3d)
// ═══════════════════════════════════════════════════════════════════════════

/** One account the send reached. `tier_from`/`tier_to` are the ladder state it
 *  MOVED — a hand send advances the same state the nightly engine does
 *  (`BR-PAY-017`), which is what makes *"no double-send"* possible at all. */
export interface NoticeSentRow {
  /** ⚠ B14 rule 31 — a React key, never a visible value. */
  account_id: string;
  /** The HUMAN-FACING reference, e.g. `AC-2026-00048`. `null` when the account
   *  genuinely has no number, which the screen states in words. */
  account_no: string | null;
  rung: string;
  tier_from: string | null;
  tier_to: string | null;
  queued_message_ids: string[];
}

/**
 * One account the send did NOT reach, **and why**.
 *
 * ⚠ **EVERY SKIP IS RECORDED AND SHOWN — `P4.16`'s assertion, and the
 * blueprint calls it *"the one thing a collections trail may not contain"*.**
 * `notices_by_hand.send` writes a `notice_history` row on every path out,
 * skips included: *"There is no `continue` in this file that does not write
 * first."* An account excluded for a medical hold and one nobody ever chased
 * must never read the same.
 */
export interface NoticeSkippedRow {
  account_id: string;
  account_no: string | null;
  rung: string | null;
  /** One of `ladder`'s reason codes. ⚠ **NEVER RENDERED RAW** — rule 31 keeps
   *  an internal string off a clerk's screen; the screen maps it to a
   *  catalogue sentence and draws the code for none it does not know. */
  reason: string | null;
  detail: string | null;
}

export interface NoticeSendResult {
  as_of: string;
  rung: string;
  tone: string | null;
  rungs: string[];
  sent: NoticeSentRow[];
  skipped: NoticeSkippedRow[];
  problems: BankRecGap[];
}

export interface SendNoticesBody {
  account_ids: string[];
  /** **EXACTLY ONE of `tone` and `rung`.** A clerk's picker sends a TONE; a
   *  caller that already knows the rung names it. Both absent, or both given,
   *  is a refusal rather than a precedence rule nobody would remember.
   *
   *  ⚠ **THERE ARE FOUR RUNGS AND THREE TONES, AND THE ASYMMETRY IS RULED
   *  RATHER THAN A GAP** (`OQ-PAY-12607`, CLOSED 2026-09-23 — PO, verbatim,
   *  *"(b) Leave it — use Final to escalate"*). The four rungs are the sequence
   *  a utility walks automatically; the three tones are what a person may
   *  choose by hand. **Nobody should 'fix' this by minting a fourth tone** —
   *  that would widen `BR-PAY-035`'s ratified table on an implementer's
   *  authority. */
  tone?: string;
  rung?: string;
  /** The clerk's business day — REQUIRED, and never a clock (`BR-TEN-043`). */
  as_of: string;
  cut_date?: string;
  channels?: string[];
  balance_floor?: string;
  partial_pause_percent?: string;
  medical_hold_account_ids?: string[];
  /** The form's submit token (hard rule 6). One per opened wizard: a key the
   *  server invented would differ on the second submit and dedupe nothing. */
  idempotency_key: string;
}

/**
 * `POST /collections/notices` — the route two live buttons pointed at for weeks
 * and never reached (`P4.13`, mounted 2026-09-23).
 *
 * **A PER-ACCOUNT REFUSAL IS NOT A REQUEST FAILURE.** 200 with `sent` and
 * `skipped` beside each other: a selection of twelve where one is on a medical
 * hold sends eleven and says why the twelfth did not. A 4xx would make one hold
 * cancel a morning's chase.
 *
 * **THE CLERK CHOOSES THE RUNG; THE LADDER CHOOSES WHETHER.** An account below
 * the floor, on a medical hold, on a paused plan, partly paid, not overdue, or
 * already written to today is skipped **exactly as the nightly engine would
 * skip it**. A hand send that could step past a medical hold would put this
 * product in front of a regulator.
 *
 * **NOTHING IS SENT HERE OR ANYWHERE** (`BR-NOT-005`): every notice is a write
 * to `outbound_messages` and the dispatcher sends.
 */
export async function sendCollectionsNotices(
  body: SendNoticesBody,
  client: ApiClient = api,
): Promise<NoticeSendResult> {
  return requireData(await client.post<NoticeSendResult>("/collections/notices", body));
}

export interface AccountCollectionsPosition {
  account_id: string;
  as_of: string;
  pause: {
    paused: boolean;
    reason: string;
    plan_id: string | null;
    /** What the pause covers, and — just as importantly — what it does NOT.
     *  BR-CUS-043's pause is scoped to the ARREARS A PLAN SPREADS; this month's
     *  bill is chased normally (PO 2026-08-11), and a screen that said "paused"
     *  without saying over what would let a clerk tell a customer otherwise. */
    covers: string;
    not_covered: string;
    detail: string;
  };
  disconnect_blocked: boolean;
  disconnect_detail: string;
  late_fee_suspended: boolean;
  /** null means *there is no plan*, never *unknown*. */
  plan: {
    id: string;
    status: string;
    missed: number;
    suspend_late_fees: boolean;
    suspend_disconnect: boolean;
  } | null;
  state: {
    tier: string | null;
    tier_sent_on: string | null;
    last_notice_on: string | null;
    next_step_due: string | null;
  };
  /** Sends AND skips. An account excluded for a medical hold and one nobody
   *  ever chased must never read the same (J4 step 2). */
  notices: {
    id: string;
    account_id: string;
    notice_type: string;
    tier: string | null;
    channel: string | null;
    outcome: string;
    skip_reason: string | null;
    detail: Record<string, unknown>;
    occurred_on: string | null;
  }[];
  rungs: string[];
  problems: BankRecGap[];
}

export async function getAccountCollections(
  accountId: string,
  params: { as_of: string },
  client: ApiClient = api,
): Promise<AccountCollectionsPosition> {
  return requireData(
    await client.get<AccountCollectionsPosition>(`/accounts/${accountId}/collections`, {
      query: { as_of: params.as_of },
    }),
  );
}

// ── The write-off approval queue's two extra fields (US-PAY-012) ───────────

/**
 * `endpoints.WriteOffQueueRow` plus the two NAMES this lane added server-side.
 *
 * Declared here as an EXTENSION rather than by widening the shared type,
 * because the shared file is under concurrent edit and because the fields are
 * this lane's: `writeoffs._people_by_id` resolves them through identity's
 * published selector, by name, at call time.
 *
 * **Why they exist at all.** The queue carried bare UUIDs, and a Finance
 * approver reading `0198c3a1-…` cannot tell whether they are about to approve
 * their OWN request. **BR-PAY-037 permits exactly that in v1** — *"the SAME
 * user holding the approver role MAY initiate AND approve … both acts recorded
 * distinctly; enforced separation-of-duties = v2"* — so the product may not
 * BLOCK it, and naming the requester is what makes a self-approval deliberate
 * instead of accidental. null when identity cannot name the user; never the
 * UUID dressed up as a name.
 */
export interface WriteOffApprovalRow {
  id: string;
  account_id: string;
  account_no: string | null;
  amount: string;
  currency: string;
  reason: string;
  note: string | null;
  status: string;
  requested_on: string | null;
  requested_by: string | null;
  requested_by_name: string | null;
  approved_on: string | null;
  approved_by: string | null;
  approved_by_name: string | null;
  /** DERIVED from `journal_entry_id`, NOT from the status: the status says what
   *  a human decided, the entry id says what the books actually carry, and
   *  US-PAY-012 TC-1's whole control is that those are different facts until an
   *  approval posts. */
  posted_to_ledger: boolean;
  journal_entry_id: string | null;
  // ── CR-059 CS-25 — served by `writeoffs._queue_row` since 2026-09-01 and
  // typed by nothing, so a rejected row read as a request nobody had answered.
  /** Who refused it, when, and why. A queue row that said only `rejected`
   *  would send the same request back tomorrow, which is the problem CS-25
   *  opens with wearing a different hat. */
  rejected_on?: string | null;
  rejected_by?: string | null;
  rejected_by_name?: string | null;
  rejection_reason?: string | null;
  /** On a REVERSING row: which approved write-off it corrects. `null` on every
   *  other row, so *"was this reversed?"* stays a question about the existence
   *  of another row and never a flag on this one. */
  reverses_write_off_id?: string | null;
  reversal_reason?: string | null;
}

/**
 * `GET /write-offs`'s body — the queue, and what is waiting across all of it.
 *
 * ⚠ **`pending` IS NOT `rows.length`, AND THE DIFFERENCE IS THE WHOLE REASON
 * IT EXISTS (Finance `P2.19`).** The server counts `status='requested'` over
 * the WHOLE population, ignoring every filter, every search term and every
 * page. The Revenue & AR view label reads it, so the badge cannot be made to
 * lie by a clerk narrowing the list — which is the blueprint's answer (p038)
 * to this endpoint's own objection that *"a page of an approval queue is a
 * queue that lies about what is pending"*.
 *
 * OPTIONAL, because a deployment that has not taken `P2.19`'s server half
 * answers without it, and a badge that draws nothing is the honest outcome
 * there — `CountBadge` renders an absent count as nothing at all.
 */
export interface WriteOffApprovalQueueResponse {
  rows: WriteOffApprovalRow[];
  pending?: number;
}

/** `GET /write-offs` — the Finance approval queue, with its people named.
 *
 *  ⚠ **IT RETURNED A BARE ARRAY UNTIL 2026-09-24 AND NOW RETURNS THE
 *  ENVELOPE**, so `pending` can reach the view label at all. All three call
 *  sites moved in the same commit. `getRefunds` one file over has always
 *  followed the envelope, and the two shapes disagreeing is exactly what the
 *  warning comment this replaces existed to warn about. */
export async function getWriteOffApprovalQueue(
  params: { status?: string; q?: string } = {},
  client: ApiClient = api,
): Promise<WriteOffApprovalQueueResponse> {
  const query: Record<string, string> = {};
  if (params.status !== undefined && params.status !== "") {
    query["f.status"] = params.status;
  }
  if (params.q !== undefined && params.q !== "") {
    query["q"] = params.q;
  }
  return requireData(
    await client.get<WriteOffApprovalQueueResponse>("/write-offs", { query }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-059 CS-25 (task 62) — the two write-off doors nothing could reach
// ══════════════════════════════════════════════════════════════════════════
// `POST /write-offs/{id}/reject` and `POST /write-offs/{id}/reverse` have been
// mounted since 2026-09-01 and no screen called either, so **an approved
// write-off could not be undone by anybody** and a request an approver did not
// want could only be ignored — which is how an approval queue fills with rows
// nobody will action, the problem CS-25 opens with.
//
// THE TWO ACTS ARE DIFFERENT SHAPES ON PURPOSE (BR-PAY-1120), and a screen that
// blurred them would be wrong in both directions:
//
//   · a `requested` write-off has posted NOTHING — no journal entry, no balance
//     movement, no plan closed — so there is nothing to correct and only a
//     decision to record. `reject` is a STATUS MOVE on that row, carrying who
//     refused it, when, and why. It is not a deletion and the row stands.
//   · an `approved` write-off HAS reduced receivables, so hard rule 4 applies in
//     full and `reverse` writes a NEW ROW at status `reversed`, linked back
//     through `reverses_write_off_id`. *"Has this been reversed?" is a question
//     about the existence of another row, never a flag on this one.*
//
// Both are System-Admin on the SERVICE as well as the route (BR-PAY-1120), so
// the screen renders them for everyone and lets the server refuse — a hidden
// control is not an authorisation (BR-SHL-025).

export interface RejectWriteOffBody {
  /** The business date of the decision — REQUIRED, never a clock read here
   *  (BR-TEN-043). */
  rejected_on: string;
  /** REQUIRED. It is the only thing the requester will be shown, and an
   *  approval queue whose refusals say nothing sends the same request back
   *  tomorrow. */
  reason: string;
}

export interface ReverseWriteOffBody {
  reversed_on: string;
  /** The posting instant for the ledger's own mirror. */
  posted_at: string;
  reason: string;
}

/** One named thing a write-off decision could not do, in the server's own
 *  words. Same shape as `BankRecGap`; kept under its own name so a write-off
 *  gap is never rendered through the bank-rec catalogue. */
export interface WriteOffProblem {
  code: string;
  br_ref: string;
  detail: string;
}

export interface WriteOffDecision {
  id: string;
  status: string;
  account_id: string;
  /** FOUR decimals beside its CHAR(3) code, and never re-rounded on the way
   *  here (hard rule 2) — the display half is `MoneyCell`'s. */
  amount: string;
  posted_to_ledger: boolean;
  journal_entry_id: string | null;
  /** On a REVERSING row: which approved write-off it corrects. Null on every
   *  other row. */
  reverses_write_off_id: string | null;
  plan_closed: string | null;
  plan_reopened: string | null;
  problems: WriteOffProblem[];
}

/** `POST /write-offs/{id}/reject` — the approver's other answer.
 *
 *  200 on the decision AND on a replay, the replay carrying `already_rejected`
 *  in `problems` with the first refusal's date. Nothing money-bearing happens
 *  on this path at all and the response says so rather than leaving a screen to
 *  infer it. */
export async function rejectWriteOff(
  writeOffId: string,
  body: RejectWriteOffBody,
  client: ApiClient = api,
): Promise<WriteOffDecision> {
  return requireData(
    await client.post<WriteOffDecision>(`/write-offs/${writeOffId}/reject`, body),
  );
}

/** `POST /write-offs/{id}/reverse` — put a wrongly-approved one back.
 *
 *  201 on a new reversing row, 200 on a replay. Worked on US-PAY-012 TC-2's own
 *  figure: a **948.20** write-off approved in August reverses to a **948.20**
 *  row at status `reversed`, the books post DR accounts receivable 948.20 / CR
 *  write-off 948.20, and bad debt for the year nets to **0.00**.
 *
 *  ⚠ THE ORIGINAL IS NOT TOUCHED AND NO ROUTE COULD TOUCH IT. There is
 *  deliberately no PUT, PATCH or DELETE on a write-off anywhere in this
 *  product; hard rule 4 is the reason and a database trigger is its other half. */
export async function reverseWriteOff(
  writeOffId: string,
  body: ReverseWriteOffBody,
  client: ApiClient = api,
): Promise<WriteOffDecision> {
  return requireData(
    await client.post<WriteOffDecision>(`/write-offs/${writeOffId}/reverse`, body),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-059 CS-26 (task 65) — the bad-debt report nothing could open
// ══════════════════════════════════════════════════════════════════════════
// `GET /bad-debt` and `GET /bad-debt/accounts` have been mounted since
// 2026-09-01 (`apps/payments/writeoffs_api.py`, `apps/payments/bad_debt.py`)
// and **no screen called either**, so the third verb of BR-PAY-020 — *"payments
// owns the transaction record, ledger posts, FINANCE REPORTS"* — was reachable
// only by a developer with a terminal. It was the LAST of seven finished
// backends shipping with no door under this CR.
//
// THE WINDOW IS THE CALLER'S AND HAS NO DEFAULT (BR-TEN-043, gate G6). The
// server refuses to invent one: a board pack produced at 23:58 and re-run at
// 00:02 must be the same document, and a default of *"this year"* computed on
// the server would be a clock read in the server's timezone. Both dates are
// required here for the same reason — a wrapper that filled one in would put
// the clock back one layer up.
//
// ⚠ **`share_percent` IS A STRING AND IT IS NULLABLE, AND NEITHER IS AN
// ACCIDENT.** Six decimals (hard rule 2, percentages 6dp) never survive a
// JavaScript number, and a share of nothing is `null` rather than
// `0.000000` — *"the ledger could not be read"* and *"the ledger says zero"*
// are opposite answers, and the same distinction runs through `ledger` below.

/** One reason's line in the report. Money at 4dp, the share at 6dp, both as
 *  strings beside the row's own `CHAR(3)`. The screen displays 2 (hard rule 2). */
export interface BadDebtReasonRow {
  reason: string;
  written_off: string;
  reversed: string;
  net: string;
  /** 6dp, or null when the net is zero or negative — never `"0.000000"`. */
  share_percent: string | null;
  count: number;
  currency: string | null;
}

/** One month's line, chronological — a trend read backwards is not a trend. */
export interface BadDebtMonthRow {
  period: string; // "YYYY-MM"
  written_off: string;
  reversed: string;
  net: string;
  count: number;
  currency: string | null;
}

/** The BOOKS' own answer for the same window, computed independently.
 *
 *  `available: false` is a REPORTED state and never a zero: *"the ledger could
 *  not be read"* and *"the ledger says nothing was written off"* are opposite
 *  answers and a screen must be able to tell them apart. */
export interface BadDebtLedgerTieOut {
  available: boolean;
  account_code: string | null;
  net: string | null;
  agrees: boolean;
}

export interface BadDebtReport {
  start: string;
  end: string;
  /** BR-REP-001 — a money report labels its basis. Always `"approved_on"`. */
  basis: string;
  currency: string | null;
  written_off: string;
  reversed: string;
  net: string;
  count: number;
  by_reason: BadDebtReasonRow[];
  by_month: BadDebtMonthRow[];
  /** Every reason the database allows, so a zero row can be DRAWN rather than
   *  a category silently dropped because nobody used it this year. */
  reasons: string[];
  ledger: BadDebtLedgerTieOut;
  problems: { code: string; br_ref?: string; detail?: string }[];
}

/** One write-off behind a bar — who, how much, and whether it was put back. */
export interface BadDebtAccountRow {
  id: string;
  account_id: string;
  /** B14 rule 31 — this is what a screen may print. `account_id` never is. */
  account_no: string | null;
  amount: string;
  currency: string;
  reason: string;
  note: string | null;
  status: string;
  approved_on: string | null;
  /** Set on a CS-25 reversing row. A chart that could not tell them apart
   *  would double-count the very rows the report nets. */
  reverses_write_off_id: string | null;
  reversal_reason: string | null;
}

export interface BadDebtAccounts {
  start: string;
  end: string;
  reason: string | null;
  rows: BadDebtAccountRow[];
}

/** `GET /bad-debt?f.start=&f.end=` — CS-26's report (S36 Revenue & AR). */
export async function getBadDebtReport(
  params: { start: string; end: string },
  client: ApiClient = api,
): Promise<BadDebtReport> {
  return requireData(
    await client.get<BadDebtReport>("/bad-debt", {
      query: { "f.start": params.start, "f.end": params.end },
    }),
  );
}

/** `GET /bad-debt/accounts?f.start=&f.end=&f.reason=` — the rows behind a bar.
 *
 *  The SAME window and the SAME statuses as the report, so the two reads can
 *  never disagree about what is in a total. `reason` is optional and, when
 *  given, must be one of the four the report serves in `reasons` — the server
 *  refuses a fifth by name rather than answering an empty report, because an
 *  empty report and an unanswerable one look identical on a screen. */
export async function getBadDebtAccounts(
  params: { start: string; end: string; reason?: string },
  client: ApiClient = api,
): Promise<BadDebtAccounts> {
  const query: Record<string, string> = { "f.start": params.start, "f.end": params.end };
  if (params.reason !== undefined && params.reason !== "") {
    query["f.reason"] = params.reason;
  }
  return requireData(await client.get<BadDebtAccounts>("/bad-debt/accounts", { query }));
}

// ══════════════════════════════════════════════════════════════════════════
// CR-059 CS-31 (task 35) — what a reversal will do, BEFORE it is done
// ══════════════════════════════════════════════════════════════════════════
// `BR-PAY-011`'s fourth clause is *"consequence message shown before confirm"*,
// and CS-31 says where it is composed in terms: *"It must be computed by the
// service, not assembled on the screen, or the warning and the outcome can
// disagree."* So S35 READS this before it offers Confirm rather than adding up
// allocation rows itself.
//
// ⚠ **THE WINDOW ARRIVES IN PARTS, NOT AS A BOOLEAN, AND THAT IS THE POINT.**
// CS-31 asks for it *"returned to the screen as a reason rather than a boolean
// so it can be shown"*, because the sentence a clerk needs is *"this ACH cleared
// 74 days ago — outside the 60-day window"* and a `false` cannot say that.

/** BR-PAY-011's window for one tender, and where this payment sits in it. */
export interface ReversalWindow {
  /** The `payment_methods` code — `ach`, `card`, `check`, … or null. */
  tender: string | null;
  /** The clearing date where there is one, otherwise the posting date. */
  measured_from: string;
  days_elapsed: number;
  /** `null` means UNLIMITED. Whether the RULE said so is `named_by_the_rule`. */
  limit_days: number | null;
  unlimited: boolean;
  /** False for a tender BR-PAY-011 never mentioned. It is still unlimited —
   *  inventing a limit would be a refusal nobody agreed to — but the screen
   *  says so rather than implying the rule covered it. */
  named_by_the_rule: boolean;
  within: boolean;
}

/** Whether somebody has to sign for this, and which trigger asked. */
export interface ReversalApproval {
  required: boolean;
  /** `applied_to_an_issued_bill` · `falls_in_a_closed_accounting_period`. */
  reasons: string[];
  problems: { code: string; br_ref?: string; detail?: string }[];
}

/** Every bill that re-opens and by how much, and what the credit becomes. */
export interface ReversalConsequences {
  currency: string;
  amount: string;
  /** B14 rule 31 — by NUMBER. No `invoice_id` is in this payload at all. */
  bills_reopening: { bill_no: string | null; amount: string; currency: string }[];
  bills_reopening_total: string;
  credit_taken_back: string;
  credit_after: string | null;
  /** The PO's own figure (2026-08-11, *"Yes, it's a real debt"*): a credit that
   *  has already been refunded goes BELOW zero, and nothing floors it. */
  credit_goes_negative: boolean;
  problems: { code: string; br_ref?: string; detail?: string }[];
}

export interface ReversalPlan {
  reason: string;
  is_staff_correction: boolean;
  on: string;
  /** CR-059 CS-33 — Σ of every reversal already standing against this payment,
   *  POSITIVE. `0.0000` on a payment nothing has come back off yet. */
  already_reversed: string;
  /** What the payment still stands for, BEFORE this reversal — `amount` minus
   *  `already_reversed`.
   *
   *  ⚠ **THE AMOUNT FIELD'S REMAINDER IS MEASURED OFF THIS AND NEVER OFF
   *  `PaymentRow.amount`.** After one partial reversal the two differ, and a
   *  screen doing its own subtraction would show a clerk a figure the service
   *  is about to refuse — at the exact moment they are deciding. The service
   *  serves `still_stands` after the act for the same reason. */
  stands_for: string;
  window: ReversalWindow;
  /** False for a bounce: a returned item is the bank's decision, arriving when
   *  the bank says it arrives, so there is no window to be outside of. */
  window_applies: boolean;
  approval: ReversalApproval;
  consequences: ReversalConsequences;
  /** SERVED rather than derived from three fields on this side — the same
   *  argument CS-31 makes for the consequence message. */
  can_reverse: boolean;
  problems: { code: string; br_ref?: string; detail?: string }[];
}

/** `GET /payments/{id}/reversal-plan?reason=&on=` — BR-PAY-011's fourth clause.
 *
 *  `on` is the caller's business day and is REQUIRED (BR-TEN-043, gate G6): a
 *  window that expired at midnight in the server's timezone would refuse a
 *  correction a clerk started before closing time. */
export async function getReversalPlan(
  paymentId: string,
  params: { reason: string; on: string },
  client: ApiClient = api,
): Promise<ReversalPlan> {
  return requireData(
    await client.get<ReversalPlan>(
      `/payments/${encodeURIComponent(paymentId)}/reversal-plan`,
      { query: { reason: params.reason, on: params.on } },
    ),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-020@5b2e814 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020/021/022/023 §5 field maps · EP-PAY-04 US-PAY-014/015 · EP-PAY-05 US-PAY-018/019 · 06-backend/apps/payments/bankrec_read.py + collections_read.py payload builders; co-packets US-PAY-021, US-PAY-022, US-PAY-023, US-PAY-015, US-PAY-018, US-PAY-019, US-PAY-012)
// generated: 2026-08-16 by story-coder (payments SURFACE lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// status: VERIFIED-UNRATIFIED
// exceptions: (1) THIS FILE IS SEPARATE FROM `endpoints.ts` ON PURPOSE — that file is 6,800 lines and holds two or three lanes' half-finished work on any afternoon; this block was written into it first and taken back out rather than ship another lane's mid-edit types · (2) `bank_total`, `difference`, `days_late` and `runs` are all nullable and NONE of them may be defaulted by a caller — each null is a distinct fact the server means (the bank has not spoken / no due date exists / this deployment cannot say) · (3) `WriteOffApprovalRow` EXTENDS rather than widens `endpoints.WriteOffQueueRow`, for the same concurrency reason · (4) `requireData` is restated here rather than imported: `endpoints.ts` does not export it, and exporting it would be an edit to a file this lane is deliberately not committing
// ──────────────────────────────────────────────────────────
