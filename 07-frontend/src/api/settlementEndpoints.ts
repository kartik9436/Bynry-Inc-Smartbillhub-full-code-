// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.7` — the two Settlements screens of
//           `05-prototype/06 Payments Page Blueprint.pdf` §03 tab 5, frames
//           5·1 and 5·2, read AS IMAGES at scale 2.0 (p069–p072). The PDF IS
//           on this branch.
// Screens:  5·1 Settlements (`S-NEW · PAY-P`) · 5·2 Settlement (`S-NEW · PAY-P`)
// Rules:    CLAUDE.md hard rule 2 (money is a DECIMAL STRING on the wire and
//           never a JSON number) · hard rule 1 (the tenant is the URL's first
//           segment; this file sends none) · BR-SHL-011 (the list URL grammar)
//           · B14 rule 31 (a payout is named by the provider's own reference)
// ───────────────────────────────────────────────────────
// The typed wrappers for the three READ routes tab 5 needs.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE READ WAS NOT ON THE BOARD, AND THIS LANE BUILT IT — `DEF-PAY-6286`
// ══════════════════════════════════════════════════════════════════════════
// The drawing's own *To build* row for 5·1 (p070) reads *"`settlements` and
// its members · a provider settlement feed in the integration framework (§04)
// · one new number series · `GET /settlements`"*. `CR-139-BRC07` §4 carries a
// task for each of those but the last. So `apps/payments/settlements_api.py`
// ships in the same commit as these screens rather than leaving them mounted
// over an endpoint nobody owned — which is hard-won law 2's dead UI, and the
// precedent one phase back (`P2.6` shipped the Counter tab against an unserved
// `GET /counters` and said so in an exception line) is the shape being avoided
// rather than repeated.
//
//   `GET /settlements`                  5·1 p070 *To build*
//   `GET /settlements/{code}`           5·2 p071, the head and its four figures
//   `GET /settlements/{code}/members`   5·2 p071, the payments inside it
//
// **There is no fourth route and no write verb.** p072's step 3 is titled *"What
// you can do to it — Nothing, and that is the design"*: a payout is a statement
// of fact from a provider, and if one is wrong the provider issues another.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE ADDRESS SEGMENT IS THE PROVIDER'S OWN REFERENCE, NEVER A uuid
// ══════════════════════════════════════════════════════════════════════════
// p071 draws the address as `/:tenant/payments/settlements/STL-260921-CARD`.
// B14 rule 31 keeps a database id out of the most visible field a screen has,
// and `settlement_models.py` already records why that reference is the
// PROVIDER'S own string rather than a number this product mints: the clerk is
// reading the processor's statement, and a second number would give one payout
// two names.
import type { ApiClient, ApiResponse } from "./client";

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

/** What the address bar carries and what this client sends — the payout's
 *  provider-issued reference, never its primary key. See the header. */
export type SettlementRef = string;

/** `settlement_models.SETTLEMENT_STATUSES`, and there is no third value.
 *
 *  `received` — the payout message arrived and its members are written; the
 *  utility's bank has not been shown to hold the money yet (`OQ-143`, PO
 *  2026-08-11: *"until bank record and reconcilaition confirm it it is not
 *  realised"*).
 *  `matched` — the bank credit for this payout has been identified.
 *
 *  ⚠ The status and the bank reference are ONE fact by CHECK constraint
 *  (`ck_settlements_matched_has_line`), so a screen never has to reconcile
 *  them and must never render them as though they could disagree. */
export const SETTLEMENT_STATUSES = ["received", "matched"] as const;
export type SettlementStatus = (typeof SETTLEMENT_STATUSES)[number];

/** One row of 5·1's list — p070's eight columns.
 *
 *  ⚠ **NO `id` FIELD, DELIBERATELY.** The row's identity is `code`, which is
 *  also the segment 5·2 opens at, so a screen cannot accidentally render the
 *  key it would otherwise have had to carry (B14 rule 31). */
export interface SettlementRow {
  /** `STL-260921-CARD` — the provider's own reference. */
  code: SettlementRef;
  /** The `provider_key` of the tenant's integration connection. **Never a
   *  vendor name written in our code** (`BR-INT-037`, `G77`): which processor
   *  this is belongs to the tenant's connection, and this string is data. */
  provider: string;
  /** When the PROVIDER says it paid out. Their clock, not ours. */
  paid_out_at: string;
  /** How many payments are inside it — `settlement_members`, counted in SQL. */
  payments: number;
  /** What the customers paid, before the provider kept anything. */
  gross: string;
  /** What the provider kept. POSITIVE, and zero is real (a free ACH rail). */
  fees: string;
  /** What reached the utility's bank. `gross - fees`, and the database refuses
   *  a row where those do not tie (`ck_settlements_net_ties`). */
  net: string;
  currency: string;
  status: SettlementStatus;
  /** The bank statement line's own reference — `BRM-2609-0044`. `null` while
   *  the payout is `received`, and `null` where the line carries no reference
   *  at all: rule 31 forbids falling back to its key. */
  bank_reference: string | null;
}

/** 5·1's four tiles, folded SERVER-side over the same rows the table filters —
 *  never computed in the browser off one page of a paginated list. */
export interface SettlementListTotals {
  currency: string;
  /** Every `provider_key` in the filtered set — the PROVIDER filter's options
   *  and the first tile's detail line, so a two-item dropdown costs no second
   *  call. */
  providers: readonly string[];
  /**
   * ⚠ **THE TWO DAY-SHAPED TILES ANSWER `null` WITHOUT AN `as_of`, AND THE
   * NULL IS NOT A ZERO.** Nothing under `apps/payments/` may read a wall clock
   * (`BR-TEN-043`), because a server clock decides a business day in the
   * SERVER's timezone. `?? "0"` here would turn *"we cannot answer"* into
   * *"nothing was paid out today"* — `DEF-127`'s shape, which reached a real
   * screen on the Counter tab this month.
   */
  paid_out_today: string | null;
  paid_out_today_providers: number | null;
  fees_this_month: string | null;
  /** A percentage as a STRING — `"1.9"`. Rendered, never arithmetic'd. */
  fees_share_of_takings: string | null;
  /** `"as_of_missing"` when the three above are null, so a screen can say
   *  WHICH absence it is rather than guessing. */
  totals_unavailable: string | null;
  /**
   * ⚠ **THE THIRD STATE, AND IT IS A FACT ABOUT THE TENDER.** *Taken, not yet
   * paid out* — a card, ACH or tap payment that is in no payout. Cash, a
   * cheque, a money order, a wire and a lockbox row are **never settled**
   * rather than awaiting one, because nobody pays the utility out for its own
   * till. Decided by `settlements_read.PROVIDER_SETTLED_TENDERS` and recorded
   * in the decision log of 2026-09-23 with its worked figure.
   */
  awaiting_settlement: string;
  awaiting_settlement_payments: number;
  /** Payouts still reading `received` — the drawing's fourth tile, *"every
   *  payout tied to a credit"*. Always answerable: it is not day-shaped. */
  unmatched: number;
}

export interface SettlementsResponse {
  rows: SettlementRow[];
  count: number;
  totals: SettlementListTotals;
}

/** 5·2's head and its four figures — GROSS · FEES · NET · BANK. */
export interface SettlementDetail {
  code: SettlementRef;
  provider: string;
  paid_out_at: string;
  payments: number;
  gross: string;
  fees: string;
  net: string;
  currency: string;
  status: SettlementStatus;
  bank_reference: string | null;
  /** This payout's own `fees / gross`, as a percentage STRING — p071 draws
   *  `1.91%` under FEES. `null` when the gross is zero. */
  fee_share: string | null;
}

/** One payment inside one payout — p071's seven columns. */
export interface SettlementMemberRow {
  /** The `PMT-` series number a clerk reads out. `null` where a legacy import
   *  could not reach the series, which the screen states in words. */
  payment_no: string | null;
  /** When the customer paid — `payments.posted_at`, the column billing reads
   *  and the one a clerk entered (`BR-PAY-021`, `BR-PAY-033`). */
  taken_at: string;
  account_no: string;
  /** Record links (PO 2026-10-19) — builds the account's address only, never
   *  shown (B14 rule 31). Optional so an older server reads as "no link". */
  account_id?: string;
  customer_name: string | null;
  /** What a person read off a device or a statement — `payments.confirmation`,
   *  one of the exactly three columns a correction may fix. */
  reference: string | null;
  /**
   * ⚠ **THE PAYMENT'S OWN AMOUNT, AND NEVER THE NETTED FIGURE.** A $100.00
   * card payment with a $2.90 fee is a $100.00 payment and a $2.90 expense —
   * the customer paid the gross, and the fee is the utility's cost of
   * collecting it. `ingest_payout` refuses a member whose gross is not the
   * payment's amount, so the wrong version cannot reach this field.
   */
  gross: string;
  /** What the provider kept on this one payment. Positive, and zero is real. */
  fee: string;
  currency: string;
}

export interface SettlementMembersResponse {
  rows: SettlementMemberRow[];
  count: number;
}

export function getSettlements(
  client: ApiClient,
  query: Record<string, string | number | undefined>,
): Promise<SettlementsResponse> {
  return client
    .get<SettlementsResponse>("/settlements", { query })
    .then((response) => requireData(response));
}

export function getSettlement(
  client: ApiClient,
  ref: SettlementRef,
): Promise<SettlementDetail> {
  return client
    .get<SettlementDetail>(`/settlements/${encodeURIComponent(ref)}`)
    .then((response) => requireData(response));
}

export function getSettlementMembers(
  client: ApiClient,
  ref: SettlementRef,
  query: Record<string, string | number | undefined>,
): Promise<SettlementMembersResponse> {
  return client
    .get<SettlementMembersResponse>(`/settlements/${encodeURIComponent(ref)}/members`, { query })
    .then((response) => requireData(response));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.7` · blueprint p069–p072 as images at 2.0
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/settlementScreens.dom.test.tsx
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
