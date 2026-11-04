// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-41 "select payments and act on them", and the screen
//           half of CS-43 "total a selection". Both are listed in §0d.2 as NEW —
//           neither existed when CR-059 was written, and CS-43 is named there as
//           CS-41's prerequisite: *"build the toolbar first and it reads blank
//           the moment a clerk selects across two pages"*.
// Story:    US-PAY-004 (S33 Record payments)  Screens: S33 · S21 (the account
//           Payments tab draws the same table and therefore the same bar)
// Rules:    BR-SHL-025 (a control that cannot be honoured renders DISABLED WITH
//           its reason, never hidden) · BR-SHL-013 (the identity column can
//           never be hidden — the whole reason the tick rides in it) ·
//           BR-PAY-014 (a refund comes only from a real credit, and a cheque
//           refund needs its cheque number) · BR-PAY-011 (the reversal reasons,
//           their windows and their approval) · BR-PAY-021 (money that has not
//           cleared cannot be given back) · BR-PAY-028 (one submit token per
//           opened form) · BR-TEN-043 (the caller names the moment; nothing here
//           reads a clock) · CLAUDE.md hard rule 2 (money is a decimal string on
//           the NUMERIC(18,6) grid, never a float) · B14 rule 21 · B14 rule 31
//           (no database id is the visible value of a field) · B14 rule 32 (one
//           sentence per section) · B14 rule 33 (a refusal caps at six words)
// Defects:  DEF-3505 (CR-059's reason for excluding this toolbar, half expired)
// ───────────────────────────────────────────────────────
// ⚠ **B14 RULE 21, AND THIS PARAGRAPH STATED THE WRONG MECHANISM UNTIL
// 2026-09-22 (`DEF-GOV-5102`, PO ruling 2026-09-12: *"Yes correct it"*).**
// It read: *"`src/features/payments/` is NOT listed in
// `src/styles/route-b-migrated.txt`, so the Tailwind compiler emits nothing for
// a utility written here … it renders as NOTHING AT ALL"*. **IT RENDERS FINE.**
// `styles/tailwind.css` imports the utilities with `source(none)` and then
// declares `@source "../"`, so the compiler scans the WHOLE of `src/` and emits
// a utility for ANY file — measured, ten of ten.
//
// **THE LEDGER GATES THE CHECKS, NOT THE CSS.** `G31` skips a listed file and
// demands of an UNLISTED one that every class be declared by a stylesheet, so
// the real consequence of a utility here is a RED GATE at merge — and the fix
// is to ADD THE FILE TO THE LEDGER, never to reach for a stylesheet class,
// which is what rule 21 forbids. The wrong version taught the opposite reflex,
// which is why it is worth this much space.
//
// **What still holds, and it is why this file has not been migrated today:**
// every class below is one `payments.css` already declares, so this file adds
// nothing to G31's ceiling — and the stylesheets stand at **471** against rule
// 21's ceiling of 470, so one NEW stylesheet class fails the gate. `P1.8`'s new
// UI therefore lands as KIT COMPONENTS (`SelectionToolbar`,
// `SelectionRowPreview`, `ConsequenceBox`), each written in utilities and each
// listed on the ledger in its own commit. B14 rule 43 asked for that anyway.
//
// ═══════════════════════════════════════════════════════════════════════════
// WHY THIS TOOLBAR EXISTS NOW, WHEN CR-059 DELIBERATELY LEFT IT OUT
// ═══════════════════════════════════════════════════════════════════════════
// CR-059 excluded it and said why, verbatim: *"every action the prototype draws
// there (Reverse, Reapply, Send receipts, Refund) has no endpoint, and a
// checkbox column selecting rows for nothing is worse than none"*. **That was
// true when it was written and is now half wrong.** `POST /payments/{id}/reverse`
// is live, `POST /payments/{id}/correct-reference` is live, and the refund
// lifecycle is six live routes. **Reapply exists at no layer** — the only mention
// of `/reallocate` in the whole payments module is a comment — and there is **no
// receipts route at all**.
//
// So two of the four can be honoured and two cannot, which is the question
// `DEF-3505` put to the Product Owner rather than answering itself. **The Product
// Owner ruled it in on 2026-09-03.** The two that cannot be honoured render
// DISABLED WITH THEIR REASON, which is `S34`'s pattern and not a new one:
// `OutstandingsTab` draws six bulk actions and four are disabled with the reason
// they cannot run, because a clerk who expects to send a reminder needs to see
// that the product knows the button should be there.
//
// ═══════════════════════════════════════════════════════════════════════════
// A BULK ACTION IS N SEQUENTIAL PER-PAYMENT CALLS, AND EACH ONE CAN FAIL ALONE
// ═══════════════════════════════════════════════════════════════════════════
// **There is no bulk route.** Every mounted payments write takes exactly one
// payment id, so fifty selected payments are fifty requests. Four consequences,
// each a decision rather than an implementation detail:
//
//   1. **SEQUENTIAL, not parallel.** The server sees the order the clerk sees,
//      and fifty simultaneous writes against one tenant's ledger is a load
//      profile nobody signed up for by ticking a box.
//   2. **THE RUN NEVER ABORTS.** A refusal is RECORDED and the loop CONTINUES.
//      Nine successes thrown away by the tenth refusal is a worse outcome than
//      the refusal, and it is what an early `throw` or a `Promise.all` produces.
//   3. **EVERY ROW ENDS WITH ITS OWN VERDICT** — done, not sent (this screen
//      refused it before any request), or failed (the server refused it, in the
//      server's own words). A single *"3 of 5 worked"* leaves a clerk with no
//      way to find the two.
//   4. **SUCCESSES ARE DESELECTED AND FAILURES STAY SELECTED**, so pressing the
//      button again retries only what did not happen. **That is not a nicety.**
//      A second refund raised over a first is money out twice, and a retry that
//      re-ran the whole selection would do exactly that.
//
// ⚠ **AND EACH ROW'S IDEMPOTENCY KEY IS MINTED ONCE PER BULK SESSION AND REUSED
// ON A RETRY.** A network failure is ambiguous — the write may have landed and
// the answer been lost — so a retry carrying a NEW key would raise a second
// refund against the same overpayment and nothing could tell.
// `refunds.request_refund` dedupes on `idempotency_key` and answers 200 with the
// original; that only helps if the key is stable, which is `keyFor`'s whole job.
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, isApiError } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import {
  REFUND_METHODS,
  REVERSAL_REASONS,
  bulkReapplyHeld,
  bulkSendReceipt,
  requestRefund,
  reversePayment,
} from "@/api/endpoints";
import type { PaymentRow, RefundMethod, ReversalReason } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import type { RegionalDateFormat } from "@/components/DateCell";
import { CheckboxField, DatePickerField, FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { SelectionRowPreview } from "@/components/SelectionRowPreview";
import type { SelectionPreviewRow } from "@/components/SelectionRowPreview";
import { SelectionToolbar } from "@/components/SelectionToolbar";
import { GuardedButton, ROLE_SYSTEM_ADMIN } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { Money, sumDecimalStrings } from "./paymentsShared";
import { BANK_MEMO_MAX, BulkNsfFeeTable, NsfFeeChoice } from "./reverseNsfFee";

// ── The selection (pure — provable without a browser) ──────────────────────

/**
 * What is ticked, as a MAP FROM ID TO THE ROW ITSELF — not a list of ids.
 *
 * ⚠ **THAT IS THE WHOLE OF `CS-43`, AND IT IS WHY THIS TYPE IS NOT
 * `readonly string[]`.** `S34`'s bulk bar holds ids and then filters the CURRENT
 * PAGE by them (`rows.filter((row) => selected.includes(row.account_id))`), so a
 * row ticked on page one is simply absent from `rows` once page two is showing:
 * it drops out of the total, the figure SILENTLY SHRINKS, and nothing on screen
 * says a number just changed meaning. CR-059 §0d.2 names that exact failure —
 * *"the selection total is summed in the BROWSER today, so it cannot survive
 * pagination"*.
 *
 * Holding the ROW at tick time is what makes the COUNT survive a page turn — it
 * is the map's size and does not depend on which page is rendered.
 *
 * ⚠ **THE MONEY IS THE SERVER'S AND WAS BRIEFLY SUMMED HERE.** See the section
 * below `refreshSelection`: `POST /payments/selection-total` applies CS-35's
 * signed rule that the figure is the day's CASH, and a client sum of every
 * ticked row would include a credit and call it a total.
 *
 * The rows are still held because the bar and the run both need them — the
 * per-row refusals read `status` and `amount`, and `refundOne` sends each
 * payment's own account and amount. `refreshSelection` re-snapshots any selected
 * row that comes back on a later page.
 */
export type PaymentSelection = ReadonlyMap<string, PaymentRow>;

export const EMPTY_SELECTION: PaymentSelection = new Map<string, PaymentRow>();

/** Tick or untick one row, keeping the snapshot. */
export function toggleSelected(selection: PaymentSelection, row: PaymentRow): PaymentSelection {
  const next = new Map(selection);
  if (next.has(row.id)) {
    next.delete(row.id);
  } else {
    next.set(row.id, row);
  }
  return next;
}

/** Drop the rows a run got through, so a retry cannot re-send them. */
export function deselectMany(selection: PaymentSelection, ids: readonly string[]): PaymentSelection {
  const next = new Map(selection);
  for (const id of ids) {
    next.delete(id);
  }
  return next;
}

/**
 * Re-snapshot every selected row that is on the page now.
 *
 * A selection outlives a page, a sort and a refetch, so a held row can be older
 * than what the server would answer today. This costs nothing and closes the gap
 * for every row a clerk can actually see; a row on another page keeps the figures
 * it was ticked with, which is stated in this file rather than hidden.
 */
export function refreshSelection(
  selection: PaymentSelection,
  pageRows: readonly PaymentRow[],
): PaymentSelection {
  if (selection.size === 0) {
    return selection;
  }
  let changed = false;
  const next = new Map(selection);
  for (const row of pageRows) {
    if (next.has(row.id)) {
      next.set(row.id, row);
      changed = true;
    }
  }
  return changed ? next : selection;
}

// ═══════════════════════════════════════════════════════════════════════════
// THE SELECTION TOTAL IS THE SERVER'S, AND THE CLIENT SUM THAT STOOD HERE FOR
// ONE COMMIT IS DELETED RATHER THAN KEPT AS A FALLBACK
// ═══════════════════════════════════════════════════════════════════════════
// This file shipped a `selectionTotal(selection)` that added the ticked rows
// with `BigInt` on the NUMERIC(18,6) grid. It was exact, it survived paging, and
// **it was answering a different question from the one the bar asks.**
// `POST /payments/selection-total` landed hours later and applies `CS-35`'s
// signed rule: the figure is **the day's CASH and EXCLUDES credits and
// adjustments** — *"or it will not tie to the drawer"* — and reports
// `excluded_count` for the rows it left out. A client sum of every ticked row
// includes a goodwill credit and calls the result a total.
//
// ⚠ **SO THE CLIENT SUM IS GONE, NOT DEMOTED TO A FALLBACK, AND THAT IS
// HARD-WON LAW 5 IN CODE.** `selectors.selection_total`'s own docstring makes
// the argument: *"two ways of totalling payments would be two answers to one
// question on one screen"*. A fallback that quietly substitutes a different
// arithmetic under the same label is worse than a stated absence, because
// nothing on screen would say which of the two a clerk was reading.
//
// **WHAT THE BAR STILL COUNTS FOR ITSELF IS THE TICK COUNT, and that is not the
// same question either.** The map's size is *"how many did I tick"*, it is
// instant and it cannot flicker; the server's `count` is *"how many of those
// this tenant still has"*, which is legitimately smaller when a selection has
// gone stale. `sumDecimalStrings` keeps its other two callers (S34's bulk bar
// and S32's method-mix tie-out) and is no longer called from here.

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported, exactly as `bankRecEndpoints.ts` and
 *  `reportsEndpoints.ts` do, so this file adds no coupling to a 15,000-line
 *  module three lanes edit on any afternoon (hard-won law 11). */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** `POST /payments/selection-total`, as the server answers it. */
export interface SelectionTotalResponse {
  /** How many ids were sent. */
  requested: number;
  /** How many of them this tenant still has — legitimately smaller. */
  count: number;
  /** The exact stored decimal, `3918.440000`, or null with a reason below. */
  amount: string | null;
  /** The SAME figure at two places, `3918.44`. The client formats neither
   *  (DEF-364: a percent shipped as `0.015000` and a customer read it). */
  amount_display: string | null;
  currency: string | null;
  /** `no_rows` · `mixed_currencies` · `no_cash_rows` — the same three codes the
   *  filter totals line already groups on, so the two figures on this one
   *  screen speak one vocabulary. */
  amount_unavailable: string | null;
  /** How many matched rows the CASH figure left out (CS-35). */
  excluded_count: number;
}

/**
 * The query key for one selection.
 *
 * The ids are SORTED into it, so ticking A then B and ticking B then A are one
 * cache entry rather than two requests for one figure.
 */
export const selectionTotalKey = (ids: readonly string[]) =>
  ["payments", "selection-total", [...ids].sort().join(",")] as const;

/**
 * ⚠ **A `POST` THAT WRITES NOTHING, AND THE VERB IS THE CONSIDERED HALF.**
 * The route's own docstring gives the reason: a clerk may tick five hundred
 * rows, and five hundred uuids in a query string is 18,000 characters — which
 * meets a proxy's URL limit long before it meets the server. Nothing is created
 * and the same request may be sent twice with no consequence, which is why it
 * carries no idempotency token and needs none.
 */
export async function getSelectionTotal(
  paymentIds: readonly string[],
  client: ApiClient,
): Promise<SelectionTotalResponse> {
  return requireData(
    await client.post<SelectionTotalResponse>("/payments/selection-total", {
      payment_ids: [...paymentIds],
    }),
  );
}

// ── What one row can be refused for, before anything is sent ───────────────

/**
 * Why THIS payment cannot be reversed, or `null`.
 *
 * The same three branches `reverseBlockedReason` computes for the row action —
 * role, `processing`, and a row that is itself a reversal — because a bulk
 * Reverse must refuse exactly what the single Reverse refuses, or the two
 * controls disagree about one rule on one screen.
 */
export function bulkReverseRefusal(
  row: PaymentRow,
  role: string | null,
  t: Translator,
): string | null {
  if (role !== null && role !== ROLE_SYSTEM_ADMIN) {
    return t("payments.reverse.adminOnly");
  }
  if (row.status === "processing") {
    return t("payments.reverse.notCleared");
  }
  if (row.status === "reversed" || row.amount.trim().startsWith("-")) {
    return t("payments.reverse.isReversal");
  }
  return null;
}

/**
 * Why THIS payment cannot be refunded, or `null`.
 *
 * ⚠ **BOTH BRANCHES MIRROR A REFUSAL `refunds.request_refund` ALREADY MAKES,
 * AND NOTHING ELSE DOES.** `_source_payment` refuses a `processing` payment —
 * *"has not cleared, so there is no money to give back"* — and `_amount` refuses
 * anything not strictly positive, so a reversing row (a negative amount) has
 * nothing to refund either.
 *
 * ⚠ **THE CREDIT TEST IS NOT HERE AND CANNOT BE.** `BR-PAY-014` allows a refund
 * only out of a real credit balance, and the row carries no credit position, so
 * a guard built here would be a guess dressed as a rule. The same is true of the
 * cross-account offset, which refuses a refund outright while the customer owes
 * on a sibling account until `CS-8` lands. **Both come back per row from the
 * server, and reporting them per row is what the result panel is for.** The role
 * is not gated either: this door takes Admin OR Clerk, and the server's own gate
 * is the boundary — the `correct-reference` precedent.
 */
export function bulkRefundRefusal(row: PaymentRow, t: Translator): string | null {
  if (row.status === "processing") {
    return t("payments.bulk.refundNotCleared");
  }
  if (row.amount.trim().startsWith("-")) {
    return t("payments.bulk.refundNotPositive");
  }
  return null;
}

/**
 * Why THIS payment gets no receipt, or `null` — Q4 bulk *Send receipts*
 * (PO 2026-10-30, `DEF-PAY-10747`).
 *
 * Mirrors the one refusal the server makes before it looks at the queue
 * (`bulk_acts._send_receipt`): a credit, an adjustment or a reversing row is
 * not money received, so it has no receipt. Everything else — waiting, no
 * contact, already sent — is a per-row ANSWER the server gives, not a refusal.
 */
export function bulkReceiptRefusal(row: PaymentRow, t: Translator): string | null {
  if (row.type !== "payment" || row.amount.trim().startsWith("-")) {
    return t("payments.bulk.receiptNotMoney");
  }
  return null;
}

/**
 * Why THIS payment may not be reapplied, or `null` — Q4 bulk *Reapply*.
 *
 * The same refusals `bulk_acts._refuse_if_not_reappliable` makes, so a row the
 * clerk may not reapply is NAMED before anything is sent rather than skipped:
 * money that has not arrived, a payment that no longer stands (reversed,
 * cancelled, failed), a reversing row, and money held for a deposit or a plan.
 */
export function bulkReapplyRefusal(row: PaymentRow, t: Translator): string | null {
  if (row.status === "processing") {
    return t("payments.reverse.notCleared");
  }
  if (row.status === "reversed" || row.status === "cancelled" || row.status === "failed") {
    return t("payments.bulk.reapplyNotStanding");
  }
  if (row.amount.trim().startsWith("-")) {
    return t("payments.reverse.isReversal");
  }
  if (row.purpose === "deposit" || row.purpose === "plan_down") {
    return t("payments.bulk.reapplyHeldForPurpose");
  }
  return null;
}

/**
 * The reason the BUTTON is disabled, or `null` when at least one selected row
 * could go through.
 *
 * A button that would refuse every row it was given is a control over nothing,
 * which is CR-059's own argument for leaving this toolbar out in the first
 * place. One that would refuse SOME of them stays live, and the run reports each
 * refusal beside the payment it belongs to.
 *
 * ⚠ **WHEN EVERY ROW IS REFUSED FOR THE SAME REASON, THAT REASON IS WHAT THE
 * BUTTON SAYS.** The first draft always fell back to *"None of these can be
 * reversed"*, and its own test caught it: a Billing Clerk with three ordinary
 * cleared payments ticked was told *"none of these"*, which is true and useless
 * — nothing about the payments is wrong, the role is. `BR-SHL-025` asks a
 * disabled control to carry ITS reason, and *"Only an administrator can
 * reverse"* is a sentence a clerk can act on. The generic line survives for the
 * case it is actually about: rows refused for DIFFERENT reasons, where no single
 * sentence is true of the selection.
 */
export function bulkActionRefusal(
  rows: readonly PaymentRow[],
  refusalFor: (row: PaymentRow) => string | null,
  noneReason: string,
): string | null {
  if (rows.length === 0) {
    return noneReason;
  }
  const reasons = rows.map((row) => refusalFor(row));
  if (reasons.some((reason) => reason === null)) {
    return null;
  }
  const distinct = new Set(reasons);
  return distinct.size === 1 ? (reasons[0] as string) : noneReason;
}

// ── What the run will ACTUALLY do, before it is asked to do it ─────────────

/**
 * ⛔ **`P1.8` — THE SELECTION SPLIT IN TWO, AND IT IS THE WHOLE TASK.**
 *
 * §03 frame 2·1b files this as a GAP in terms: *"`bulkActionRefusal` returns
 * "allowed" if ANY selected row can be acted on. Select five payments where one
 * is reversible and four are not, and the button is live, bright, and says
 * nothing. The confirm that follows takes **only a count** — it asks "Reverse 5
 * payments?" when it is about to reverse one and silently refuse four. You find
 * out afterwards, per row."*
 *
 * And it names the fix: *"The product already knows which four …
 * **The fix is not new logic; it is showing what is already computed.**"*
 *
 * ⚠ **SO THIS CALLS THE SAME `refusalFor` THE RUN CALLS AND ADDS NO RULE.** A
 * second rule here would be a screen that says one thing before the button and
 * does another after it, over money, which is the one place that cannot be
 * allowed to drift. `runBulk` refuses each row with this identical predicate;
 * what changes is only WHEN the clerk is told.
 */
export interface SelectionSplit {
  /** The rows the run will act on — the number the BUTTON says. */
  eligible: readonly PaymentRow[];
  /** The rows the run will refuse, each with the reason it will be refused
   *  for. A pair rather than a count, because note ④ of 2·1b is *"Who is
   *  skipped, **and why**"*. */
  skipped: readonly { row: PaymentRow; reason: string }[];
}

export function splitSelection(
  rows: readonly PaymentRow[],
  refusalFor: (row: PaymentRow) => string | null,
): SelectionSplit {
  const eligible: PaymentRow[] = [];
  const skipped: { row: PaymentRow; reason: string }[] = [];
  for (const row of rows) {
    const reason = refusalFor(row);
    if (reason === null) {
      eligible.push(row);
    } else {
      skipped.push({ row, reason });
    }
  }
  return { eligible, skipped };
}

/**
 * ⑦ *"What it will do · in the customer's terms"* — the figures behind B14
 * rule 11's consequence box, computed over the ELIGIBLE rows only.
 *
 * ⚠ **THIS IS NOT A SECOND ANSWER TO THE BAR'S TOTAL, AND THE DISTINCTION IS
 * WORTH THE PARAGRAPH.** The bar's figure is `POST /payments/selection-total`,
 * which applies `CS-35`'s signed rule that the number is the day's CASH and
 * EXCLUDES credits and adjustments — *"or it will not tie to the drawer"*. This
 * one answers a different question: *how much money is about to move back to
 * customers*, over the rows the run will actually touch. The drawing shows both
 * on one screen and shows them differing — `3 selected · $1,080.53` on the bar
 * above `$278.10 goes back to 2 accounts` in the confirm — because one row of
 * the three is skipped.
 *
 * ⚠ **AND IT IS `sumDecimalStrings`, NOT ARITHMETIC WRITTEN HERE** (CLAUDE.md
 * hard rule 2: money is a decimal string on the storage grid, never a float).
 * `null` when any amount is not a decimal — the box then states what it can and
 * leaves out what it cannot, rather than printing `NaN` or a guess.
 */
export interface ReversalConsequence {
  amount: string | null;
  accounts: number;
  /** Distinct bills the eligible rows are applied to — each one re-opens when
   *  its payment is reversed. Read off `applied_to`, which the list already
   *  serves per row, so nothing is fetched to say this. */
  bills: number;
}

export function reversalConsequence(rows: readonly PaymentRow[]): ReversalConsequence {
  return {
    amount: sumDecimalStrings(rows.map((row) => row.amount)),
    accounts: new Set(rows.map((row) => row.account_id)).size,
    bills: new Set(rows.flatMap((row) => row.applied_to.map((entry) => entry.invoice_id))).size,
  };
}

// ── The run ────────────────────────────────────────────────────────────────

export type BulkActionId = "reverse" | "refund" | "receipts" | "reapply";

export type PerRowStatus = "done" | "refused" | "failed";

export interface PerRowOutcome {
  id: string;
  /** The payment NUMBER, or the stated absence. **Never the uuid** — B14 rule
   *  31, and this panel is read by the clerk who pressed the button. */
  label: string;
  status: PerRowStatus;
  /** What the server said happened, for a row that went through — the
   *  `outcome` of `bulk-receipt` / `bulk-reapply` (`sent`, `waiting`,
   *  `nothing_to_reapply` …). `null` for Reverse and Refund, whose "done" is
   *  the whole answer. */
  kind?: string | null;
  /** A plain sentence: this screen's own reason for a refusal, the server's for
   *  a failure, and null for a row that went through. */
  detail: string | null;
}

export interface BulkRun {
  action: BulkActionId;
  total: number;
  outcomes: PerRowOutcome[];
  running: boolean;
}

export function rowLabel(row: PaymentRow, t: Translator): string {
  return row.payment_no ?? t("payments.row.noNumber");
}

export function runTally(run: BulkRun): { done: number; failed: number; refused: number } {
  return {
    done: run.outcomes.filter((outcome) => outcome.status === "done").length,
    failed: run.outcomes.filter((outcome) => outcome.status === "failed").length,
    refused: run.outcomes.filter((outcome) => outcome.status === "refused").length,
  };
}

/** The ids a run got through — the set the caller must DESELECT. */
export function succeededIds(run: BulkRun): string[] {
  return run.outcomes.filter((outcome) => outcome.status === "done").map((outcome) => outcome.id);
}

/** The rows a run did NOT get through — what a retry is allowed to re-send. */
export function failedRows(run: BulkRun, selection: PaymentSelection): PaymentRow[] {
  const ids = new Set(
    run.outcomes.filter((outcome) => outcome.status === "failed").map((outcome) => outcome.id),
  );
  return [...selection.values()].filter((row) => ids.has(row.id));
}

/**
 * Send one request per row, in order, recording an outcome for every one.
 *
 * ⚠ **THE `await` IN THE LOOP IS THE DESIGN, NOT AN OVERSIGHT**, and a later
 * lane reaching for `Promise.all` would change three things at once: the server
 * would see fifty concurrent writes against one tenant's ledger, the order a
 * clerk sees would stop being the order the money moves in, and a rejection
 * would have to be re-associated with its row after the fact.
 *
 * ⚠ **NOTHING THROWS OUT OF HERE.** A row that refuses or fails is recorded and
 * the loop continues; the caller receives an outcome for every row whatever
 * happened. That is the whole reason nine successes are not lost to a tenth
 * refusal.
 */
export async function runPerRow(
  rows: readonly PaymentRow[],
  refusalFor: (row: PaymentRow) => string | null,
  labelFor: (row: PaymentRow) => string,
  call: (row: PaymentRow) => Promise<string | null | void>,
  failureText: (error: unknown) => string,
  onOutcome: (outcome: PerRowOutcome) => void,
): Promise<void> {
  for (const row of rows) {
    const refusal = refusalFor(row);
    if (refusal !== null) {
      // Refused BEFORE anything is sent: a request this screen already knows
      // will be turned down is a round trip that teaches the clerk nothing.
      onOutcome({ id: row.id, label: labelFor(row), status: "refused", detail: refusal });
      continue;
    }
    try {
      const kind = await call(row);
      onOutcome({
        id: row.id,
        label: labelFor(row),
        status: "done",
        kind: typeof kind === "string" ? kind : null,
        detail: null,
      });
    } catch (error) {
      onOutcome({ id: row.id, label: labelFor(row), status: "failed", detail: failureText(error) });
    }
  }
}

/**
 * One idempotency key per payment, minted once and kept for the bulk session.
 *
 * See this file's header: a retry MUST carry the key its first attempt carried,
 * or an ambiguous network failure becomes a second refund against the same
 * overpayment. `crypto.randomUUID` is what the single-payment forms use, for
 * exactly the reason BR-PAY-028 gives — one token per opened form, and a key the
 * server invented would differ on the second submit and dedupe nothing.
 */
export function keyFor(keys: Map<string, string>, paymentId: string): string {
  const existing = keys.get(paymentId);
  if (existing !== undefined) {
    return existing;
  }
  const minted = crypto.randomUUID();
  keys.set(paymentId, minted);
  return minted;
}

/** The failure sentence a per-row outcome carries. */
export function bulkFailureText(error: unknown, t: Translator): string {
  if (isApiError(error)) {
    return apiErrorText(error, t);
  }
  return t("api.error.unexpected");
}

// ── The two callers, so the page holds no request code ─────────────────────

/**
 * One reversal.
 *
 * ⚠ **THREE THINGS A BULK REVERSE DELIBERATELY DOES NOT SEND, AND EACH IS A
 * JUDGMENT RATHER THAN A GAP.**
 *
 *   · **No reversal PLAN is read.** `GET /payments/{id}/reversal-plan` is per
 *     payment, and reading fifty is fifty round trips before any work happens. A
 *     row whose plan would have refused is refused by the service anyway, in the
 *     same words, and lands in the result panel beside its payment number.
 *   · **No APPROVAL.** BR-PAY-011 asks for one when the payment is applied to an
 *     issued bill or the day falls in a closed period — a judgment about one
 *     bill in one period. A single approval string applied to fifty payments
 *     would be one person's note standing in for fifty decisions. A row that
 *     needs one FAILS here and the clerk reverses that one from its row action,
 *     where the plan is read and the approval is asked for.
 *   · **No BANK FEE.** Absent and `0.00` are different facts and the fee is per
 *     returned item; one figure spread over fifty is a number nobody can tie.
 */
export async function reverseOne(
  row: PaymentRow,
  body: {
    reason: ReversalReason;
    returnedOn: string;
    resumeCollections: boolean;
    /** `DEF-PAY-10698` — absent = charge the plan's NSF fee (the default). */
    chargeNsfFee?: boolean;
    nsfFeeWaiveReason?: string;
    /** LBX-04 — the bank's words, ONE PER PAYMENT, keyed by payment id. */
    bankMemos?: Record<string, string>;
  },
  key: string,
  client: ApiClient,
): Promise<void> {
  const memo = (body.bankMemos?.[row.id] ?? "").trim();
  await reversePayment(
    row.id,
    {
      returned_on: body.returnedOn,
      reason: body.reason,
      resume_collections: body.resumeCollections,
      idempotency_key: key,
      charge_nsf_fee: body.chargeNsfFee !== false,
      nsf_fee_waive_reason:
        body.chargeNsfFee === false ? (body.nsfFeeWaiveReason ?? "").trim() : null,
      bank_memo: memo === "" ? null : memo,
    },
    client,
  );
}

/**
 * One refund, for this payment's OWN amount, against this payment's OWN account.
 *
 * `POST /accounts/{id}/refunds` refuses a `payment_id` on another account BY
 * NAME — without that check the account in the URL would be a label — so sending
 * each row's own pair is what keeps the path honest for a bulk run.
 */
export async function refundOne(
  row: PaymentRow,
  method: RefundMethod,
  requestedAt: string,
  key: string,
  client: ApiClient,
): Promise<void> {
  await requestRefund(
    row.account_id,
    {
      payment_id: row.id,
      amount: row.amount,
      method,
      requested_at: requestedAt,
      idempotency_key: key,
    },
    client,
  );
}

/**
 * One payment's email receipt — the server decides whether it is SENT (no
 * receipt, or the last one failed) or left WAITING in the outbound table for
 * the email service. Never queued twice (decision log 2026-10-30, Q4 settled).
 * No idempotency key: a second press finds the row the first wrote, waiting.
 */
export async function receiptOne(row: PaymentRow, client: ApiClient): Promise<string> {
  return (await bulkSendReceipt(row.id, client)).outcome;
}

/**
 * One payment's HELD part onto its account's open bills, oldest first, through
 * the existing reapply (`bulk_acts.reapply_held`). `onDate` is the clerk's
 * business day (BR-TEN-043 — the server reads no clock). A second press finds
 * nothing held and answers *nothing to reapply*.
 */
export async function reapplyOne(
  row: PaymentRow,
  onDate: string,
  client: ApiClient,
): Promise<string> {
  return (await bulkReapplyHeld(row.id, { on_date: onDate }, client)).outcome;
}

/**
 * *"5 sent · 15 waiting for the email service"* — the run counted by what
 * HAPPENED, not by done/failed. One part per outcome, in the order they first
 * appeared, each through its own plural key; refused and failed rows count too.
 */
export function outcomeSummary(run: BulkRun, t: Translator): string {
  const counts = new Map<string, number>();
  for (const outcome of run.outcomes) {
    const key = outcome.status === "done" ? (outcome.kind ?? "done") : outcome.status;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([kind, count]) => t(`payments.bulk.kind.${kind}`, { count }))
    .join(" · ");
}

// ── The bar ────────────────────────────────────────────────────────────────

export interface PaymentsBulkBarProps {
  selection: PaymentSelection;
  role: string | null;
  currency: string | null;
  /** The SERVER's figure for this selection. `undefined` while the read is in
   *  flight or after it failed — the bar then states that it has no total
   *  rather than substituting a different arithmetic under the same label. */
  total: SelectionTotalResponse | undefined;
  running: BulkActionId | null;
  progress: { done: number; total: number } | null;
  onClear: () => void;
  onReverse: () => void;
  onRefund: () => void;
  /** Q4 (PO 2026-10-30) — one email receipt per ticked payment. */
  onSendReceipts: () => void;
  /** Q4 — each ticked payment's held credit onto its open bills. */
  onReapply: () => void;
}

/**
 * *"3 selected · 1,242.87"*, and the TWO actions this bar has.
 *
 * ⚠ **THIS DOCSTRING SAID `Reapply` AND `Send receipts` *"RENDER DISABLED WITH
 * THEIR REASON RATHER THAN BEING HIDDEN (BR-SHL-025)"* UNTIL 2026-09-22, AND
 * HALF OF ITS REASONING HAD STOPPED BEING TRUE.** It read: *"Neither exists at
 * any layer — `/reallocate` is `CS-11` and unbuilt, and there is no receipts
 * route at all"*. `POST /payments/{id}/reapply` **landed on 2026-09-03**, so
 * from that day the bar refused over a served endpoint and nothing re-checked
 * the refusal — hard-won law 2's mirror, a live engine behind a dead control.
 *
 * `BR-SHL-025` is not being overruled: it governs a control this DEPLOYMENT
 * cannot honour, and neither of these was that. **A bulk reapply and a bulk
 * receipt send do not exist as acts at all** — a reapply names ONE payment's
 * bills and a receipt is queued automatically on every recorded payment — so
 * there is no rule for a clerk to learn from a greyed button here. The
 * blueprint's 2·1b rules them off the bar in terms (*"Nothing else on the
 * bar"*), and the single-payment reapply is reached from the row overflow.
 *
 * ⚠ **THE TWO CATALOGUE KEYS ARE LEFT IN PLACE ON PURPOSE**, because the bar is
 * drawn to regain both controls when the bulk acts land, and retiring a string
 * eleven catalogues hold is the more expensive half of putting it back.
 *
 * ⚠ **SUPERSEDED 2026-10-30 — THE BULK ACTS LANDED AND BOTH CONTROLS ARE BACK.**
 * The PO ruled them in (decision log *"Q4 settled: bulk Send receipts AND bulk
 * Reapply are built"*), and `apps/payments/bulk_acts.py` is the bulk receipt
 * and the bulk reapply this paragraph was waiting for. So the bar now holds
 * FOUR actions: Reverse, Refund, Send receipts, Reapply. The two paragraphs
 * above are kept as the history of why they were off it.
 */
export function PaymentsBulkBar(props: PaymentsBulkBarProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const rows = [...props.selection.values()];
  const busy = props.running !== null;
  const total = props.total;
  const excluded = total?.excluded_count ?? 0;

  const reverseReason = bulkActionRefusal(
    rows,
    (row) => bulkReverseRefusal(row, props.role, translate),
    t("payments.bulk.noneReversible"),
  );
  const refundReason = bulkActionRefusal(
    rows,
    (row) => bulkRefundRefusal(row, translate),
    t("payments.bulk.noneRefundable"),
  );

  // `P1.8` — what can ACTUALLY happen, which the bar threw away for a yes/no.
  const reverseSplit = splitSelection(rows, (row) =>
    bulkReverseRefusal(row, props.role, translate),
  );
  const refundSplit = splitSelection(rows, (row) => bulkRefundRefusal(row, translate));
  const receiptReason = bulkActionRefusal(
    rows,
    (row) => bulkReceiptRefusal(row, translate),
    t("payments.bulk.noneReceipt"),
  );
  const reapplyReason = bulkActionRefusal(
    rows,
    (row) => bulkReapplyRefusal(row, translate),
    t("payments.bulk.noneReappliable"),
  );
  const receiptSplit = splitSelection(rows, (row) => bulkReceiptRefusal(row, translate));
  const reapplySplit = splitSelection(rows, (row) => bulkReapplyRefusal(row, translate));

  return (
    <SelectionToolbar
      label={t("payments.bulk.label")}
      // The TICK COUNT is the map's size, not the server's `count`. They are
      // different questions: this one is *"how many did I tick"*, it is instant
      // and it cannot flicker while a request is in flight.
      count={t("payments.bulk.selected", { count: props.selection.size })}
      // ⚠ `totalText` AND NOT `total`: the kit renamed it on 2026-09-22 so a
      // slot taking a `ReactNode` cannot be mistaken for one taking a decimal
      // string, which would render unformatted past `tsc` and every test.
      totalText={
        total?.amount != null ? (
          // The tenant's CHAR(3) read off the list response, exactly as every
          // other figure on this page reads it (BR-TEN-042's one-currency lock);
          // the server's own answer is the fallback.
          <Money amount={total.amount} currency={props.currency ?? total.currency} />
        ) : (
          // NEVER a blank and never a wrong number — CS-43's acceptance line is
          // *"not a blank"*. The three codes are the filter totals line's own,
          // so one screen does not explain the same absence in two vocabularies;
          // an in-flight read has no code yet and says *"no payments matched"*
          // is NOT true, so it falls to the honest one below.
          <span className="cus-awaits">
            {total === undefined
              ? t("payments.bulk.totalUnread")
              : t(`payments.totals.unavailable.${total.amount_unavailable ?? "no_rows"}`)}
          </span>
        )
      }
      /* ② **WHAT CAN ACTUALLY HAPPEN**, in the slot the filter chips vacated —
         *"because it is the same kind of fact"*, §03 frame 2·1b.

         ⚠ **ONLY WHEN SOMETHING IS ACTUALLY SKIPPED.** A permanent *"3 can be
         reversed · 0 cannot"* is B14 rule 32's noise on a bar a clerk reads
         before pressing a danger-tier button, and it is the same posture the
         `excluded > 0` line beside it already takes.

         ⚠ **AND IT IS THE REVERSE SPLIT, WHICH IS WHAT THE DRAWING DRAWS.**
         Refund's own eligibility rides on its button's count: two sentences of
         the same shape, side by side, is a bar a clerk has to parse rather than
         read. */
      eligibility={
        reverseSplit.skipped.length > 0 ? (
          <span data-bulk-eligibility="reverse">
            {t("payments.bulk.eligible.reverse", {
              can: reverseSplit.eligible.length,
              cannot: reverseSplit.skipped.length,
            })}
          </span>
        ) : excluded > 0 ? (
          // CS-35: how many ticked rows the CASH figure left out. Same slot,
          // same kind of fact, and the reversal split outranks it because it is
          // about the act the clerk is ABOUT to commit.
          <span data-bulk-eligibility="cash">
            {t("payments.bulk.notCash", { count: excluded })}
          </span>
        ) : undefined
      }
      note={
        props.progress !== null
          ? t("payments.bulk.progress", {
              done: props.progress.done,
              total: props.progress.total,
            })
          : undefined
      }
    >
      {/* ③ **THE BUTTON READS THE ELIGIBLE COUNT, NEVER THE TICK COUNT.** That
          is the whole outcome of `P1.8` — *"The button reads **Reverse 2**,
          never **Reverse 3**"* — and the figure comes from the SAME predicate
          the run uses, so the bar cannot promise something the run refuses.
          With nothing eligible the button is disabled with its reason anyway,
          and *Reverse 0* would be a number nobody needs to read. */}
      <GuardedButton
        label={
          reverseSplit.eligible.length > 0
            ? t("payments.bulk.action.reverseCount", { count: reverseSplit.eligible.length })
            : t("payments.bulk.action.reverse")
        }
        reason={busy ? t("payments.bulk.busy") : reverseReason}
        working={props.running === "reverse"}
        danger
        onClick={props.onReverse}
      />
      <GuardedButton
        label={
          refundSplit.eligible.length > 0
            ? t("payments.bulk.action.refundCount", { count: refundSplit.eligible.length })
            : t("payments.bulk.action.refund")
        }
        reason={busy ? t("payments.bulk.busy") : refundReason}
        working={props.running === "refund"}
        onClick={props.onRefund}
      />
      {/* Q4 (PO 2026-10-30, `DEF-PAY-10747`) — the two controls `CR-135` P1.7
          took off this bar *"until a BULK reapply and a BULK receipt exist"*.
          They exist now (`bulk_acts.py`), so they are back, in the bar's own
          button style and with the same eligible-count label. */}
      <GuardedButton
        label={
          receiptSplit.eligible.length > 0
            ? t("payments.bulk.action.receiptsCount", { count: receiptSplit.eligible.length })
            : t("payments.bulk.action.receipts")
        }
        reason={busy ? t("payments.bulk.busy") : receiptReason}
        working={props.running === "receipts"}
        onClick={props.onSendReceipts}
      />
      <GuardedButton
        label={
          reapplySplit.eligible.length > 0
            ? t("payments.bulk.action.reapplyCount", { count: reapplySplit.eligible.length })
            : t("payments.bulk.action.reapply")
        }
        reason={busy ? t("payments.bulk.busy") : reapplyReason}
        working={props.running === "reapply"}
        onClick={props.onReapply}
      />
      {/* `CR-135` `P1.7` — REAPPLY AND SEND RECEIPTS ARE OFF THIS BAR, and the
          blueprint says so twice. §03 frame 2·1b: *"Reverse, danger tier, with
          Refund beside it. **Nothing else on the bar**"*, and its GAP box is
          headed *"The two dead controls come off the bar; they do not stay
          greyed"*. They return when a BULK reapply and a BULK receipt exist.
          Removing them takes no capability with it — both were disabled with
          `onClick={() => undefined}`, so neither was ever a door (the
          `DEF-PAY-6199` check: what could the thing you are deleting DO?).
          Reapply now has a real door on the row overflow, which is where the
          drawing puts it — `paymentMoveReapply.tsx`, 2·3g.
          ⚠ SUPERSEDED 2026-10-30: the bulk acts exist and both are back above
          (Q4, PO ruling; `DEF-PAY-10747`). */}
      <GuardedButton
        label={t("payments.bulk.clear")}
        reason={busy ? t("payments.bulk.busy") : null}
        onClick={props.onClear}
      />
    </SelectionToolbar>
  );
}

// ── What the run did, row by row ───────────────────────────────────────────

/**
 * The per-row result panel — the control CR-059 §0d.2 says a bulk toolbar over
 * per-payment routes cannot ship without: *"a result panel saying which of the
 * fifty went through"*.
 *
 * Three verdicts, each named. A single *"3 of 5 worked"* would leave a clerk
 * with no way to find the two.
 */
export function BulkRunPanel(props: {
  run: BulkRun;
  refundsHref: string | null;
  onRetry: (() => void) | null;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const tally = runTally(props.run);
  const retryable = tally.failed > 0 && props.onRetry !== null && !props.run.running;
  return (
    <div className="pay-result">
      <div className="pay-result-head">
        <h3>{t(`payments.bulk.resultTitle.${props.run.action}`)}</h3>
        <Button variant="ghost" onClick={props.onDismiss}>
          {t("payments.bulk.dismiss")}
        </Button>
      </div>
      <p className="pay-result-ledger" data-bulk-summary="">
        {props.run.action === "receipts" || props.run.action === "reapply"
          ? outcomeSummary(props.run, translate)
          : t("payments.bulk.resultSummary", {
              done: tally.done,
              total: props.run.total,
            })}
      </p>
      <ul className="pay-failed-rows">
        {props.run.outcomes.map((outcome) => (
          <li key={outcome.id}>
            <span className="pay-id">{outcome.label}</span>
            <span>
              {outcome.status === "done" && outcome.kind
                ? t(`payments.bulk.row.${outcome.kind}`)
                : t(`payments.bulk.outcome.${outcome.status}`)}
            </span>
            {outcome.detail !== null && <span className="pay-sub">{outcome.detail}</span>}
          </li>
        ))}
      </ul>
      {props.run.action === "refund" && tally.done > 0 && props.refundsHref !== null && (
        <p className="pay-result-ledger">
          <a href={props.refundsHref}>{t("payments.bulk.openRefundQueue")}</a>
        </p>
      )}
      {retryable && (
        <p className="pay-result-ledger">
          <Button variant="secondary" onClick={() => props.onRetry?.()}>
            {t("payments.bulk.retryFailed", { count: tally.failed })}
          </Button>
        </p>
      )}
    </div>
  );
}

// ── Bulk refund: what it needs before it can send anything ─────────────────

export function bulkRefundSchema(t: Translator) {
  return z.object({
    requested_at: z.string().min(1, t("payments.refunds.dateRequired")),
  });
}

/**
 * Method and date for a run of refunds.
 *
 * ⚠ **IT OFFERS ACH AND NOT CHEQUE, AND THAT IS A SERVER RULE READ OFF THE
 * SERVICE RATHER THAN A SCOPE CUT.** `refunds.request_refund` refuses a cheque
 * refund carrying no cheque number, in its own words: *"a cheque refund needs its
 * cheque number ... without it the refund cannot be matched to the bank line when
 * it clears, and a payment out that bank rec can never find is how a
 * reconciliation stops tying"*. Three selected payments are three refunds and
 * therefore three cheques; one number cannot serve them, and a screen that
 * invented a run of numbers would be writing cheque numbers nobody wrote. So the
 * cheque path stays one-at-a-time on S58 and this form says so in one sentence.
 *
 * ⚠ **THE DATE IS COLLECTED AND NEVER DEFAULTED FROM A CLOCK (BR-TEN-043).**
 * `refunds._moment` refuses a request without one and says why: a refund dated by
 * whenever the request happened to be processed would let the server's load
 * decide which accounting period the money left in.
 */
export function BulkRefundModal(props: {
  /** The rows, not a count — see `BulkReverseModal`'s own note. */
  rows: readonly PaymentRow[];
  currency: string | null;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onConfirm: (values: { method: RefundMethod; requestedAt: string }) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [method, setMethod] = useState<RefundMethod>("ach");
  const [requestedAt, setRequestedAt] = useState("");

  // ⚠ **THE SAME SHAPE AS THE REVERSE CONFIRM, AND THE DRAWING DOES NOT DRAW
  // IT.** §03 frame 2·1b draws only the reversal's confirm, and this lane's
  // judgment is that the GAP box it files is about BOTH — *"a bulk reversal
  // writes money across several accounts and shows no 'what this will do' box
  // at all"* is true word for word of a bulk refund, and `bulkRefundRefusal`
  // computes a per-row reason that this form was throwing away exactly as the
  // reversal's did. Two forms one step apart, one asking per row and one asking
  // for a count, is a screen that teaches a clerk two different habits. The
  // judgment is recorded in the decision log so it can be overturned in a word.
  const split = splitSelection(props.rows, (row) => bulkRefundRefusal(row, translate));
  const willRun = split.eligible.length;

  return (
    <FormModal
      title={t("payments.bulk.refundTitle", { count: willRun })}
      schema={bulkRefundSchema(translate)}
      values={{ requested_at: requestedAt }}
      submitLabel={t("payments.bulk.refundSubmit", { count: willRun })}
      onClose={props.onClose}
      onSubmit={async (): Promise<FormSubmitOutcome> => {
        // The run happens on the PAGE, not in here: its outcomes are per row and
        // a modal can show one error. It closes, and the result panel says what
        // happened to each payment.
        props.onConfirm({ method, requestedAt });
        return { ok: true };
      }}
    >
      {split.skipped.length > 0 && (
        <p data-bulk-split="refund">
          {t("payments.bulk.willRefund", {
            run: willRun,
            total: props.rows.length,
            skipped: split.skipped.length,
          })}
        </p>
      )}

      <SelectionRowPreview
        caption={t("payments.bulk.previewCaption.refund")}
        columns={{
          label: t("payments.bulk.col.payment"),
          owner: t("payments.bulk.col.account"),
          amount: t("payments.bulk.col.amount"),
          outcome: t("payments.bulk.col.willHappen"),
        }}
        rows={previewRows(
          props.rows,
          split,
          translate,
          props.currency,
          t("payments.bulk.outcome.willRefund"),
        )}
      />

      <SelectField
        id="bulk_refund_method"
        label={t("payments.bulk.refundMethod")}
        value={method}
        onChange={(next) => setMethod(next as RefundMethod)}
        required
        options={REFUND_METHODS.filter((code) => code !== "check").map((code) => ({
          value: code,
          label: t(`payments.refunds.method.${code}`),
        }))}
        help={t("payments.bulk.refundChequeNote")}
      />
      <DatePickerField
        id="requested_at"
        label={t("payments.bulk.refundRequestedAt")}
        value={requestedAt}
        onChange={setRequestedAt}
        dateFormat={props.dateFormat}
        required
      />
    </FormModal>
  );
}

export function bulkReverseSchema(t: Translator) {
  return z
    .object({
      returned_on: z.string().min(1, t("payments.reverse.returnedOnRequired")),
      // DEF-PAY-10698 — unticking the NSF fee needs a reason (PO 2026-10-30).
      charge_nsf_fee: z.boolean().optional(),
      nsf_fee_waive_reason: z.string().optional(),
      // LBX-04 — each payment's Bank memo, at most 60 characters.
      bank_memos: z.record(z.string()).optional(),
    })
    .superRefine((values, ctx) => {
      if (values.charge_nsf_fee === false && (values.nsf_fee_waive_reason ?? "").trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["nsf_fee_waive_reason"],
          message: t("payments.reverse.nsfFee.waiveReasonRequired"),
        });
      }
      Object.values(values.bank_memos ?? {}).forEach((memo) => {
        if (memo.trim().length > BANK_MEMO_MAX) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["bank_memos"],
            message: t("payments.reverse.bankMemoTooLong"),
          });
        }
      });
    });
}

/**
 * The bank's day, the reason, and whether the ladder resumes — collected once
 * for the whole run.
 *
 * All four of `BR-PAY-011`'s reasons are offered because the service honours all
 * four since CS-31; the picker is the same list the single Reverse modal draws,
 * from the same catalogue keys, so the two cannot come to offer different
 * reasons for the same rule. What this form does NOT collect — the plan, the
 * approval and the bank fee — is `reverseOne`'s docstring, with a reason for
 * each.
 */
export function BulkReverseModal(props: {
  /** ⚠ **THE ROWS, NOT A COUNT — AND THAT CHANGE IS `P1.8`.** The blueprint's
   *  GAP box: *"The confirm that follows takes **only a count** — it asks
   *  'Reverse 5 payments?' when it is about to reverse one and silently refuse
   *  four."* A count cannot say which four, and this form cannot compute it
   *  from one. */
  rows: readonly PaymentRow[];
  /** The role the refusal ladder reads — the same one the bar and the run use,
   *  because three answers to one rule on one screen is the failure. */
  role: string | null;
  /** The tenant's CHAR(3), for the consequence figure. Null = no currency was
   *  read, and the box then states what it can without a money line. */
  currency: string | null;
  dateFormat: RegionalDateFormat;
  /** The quote reads (`DEF-PAY-10698`); the app's client when absent. */
  client?: ApiClient;
  onClose: () => void;
  onConfirm: (values: {
    reason: ReversalReason;
    returnedOn: string;
    resumeCollections: boolean;
    chargeNsfFee: boolean;
    nsfFeeWaiveReason: string;
    bankMemos: Record<string, string>;
  }) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const [reason, setReason] = useState<ReversalReason>("nsf");
  const [returnedOn, setReturnedOn] = useState("");
  const [resume, setResume] = useState(false);
  // DEF-PAY-10698 — ticked by default; unticking asks for the reason.
  const [chargeNsfFee, setChargeNsfFee] = useState(true);
  const [waiveReason, setWaiveReason] = useState("");
  // LBX-04 — the bank's words, one per payment, keyed by payment id.
  const [bankMemos, setBankMemos] = useState<Record<string, string>>({});

  const split = splitSelection(props.rows, (row) =>
    bulkReverseRefusal(row, props.role, translate),
  );
  const willRun = split.eligible.length;
  const consequence = reversalConsequence(split.eligible);

  return (
    <FormModal
      // ③ The title carries the figure that will actually run. *"The button
      // reads Reverse 2, never Reverse 3."*
      title={t("payments.bulk.reverseTitle", { count: willRun })}
      schema={bulkReverseSchema(translate)}
      values={{
        returned_on: returnedOn,
        charge_nsf_fee: reason === "nsf" ? chargeNsfFee : true,
        nsf_fee_waive_reason: waiveReason,
        bank_memos: bankMemos,
      }}
      submitLabel={t("payments.bulk.reverseSubmit", { count: willRun })}
      onClose={props.onClose}
      onSubmit={async (): Promise<FormSubmitOutcome> => {
        props.onConfirm({
          reason,
          returnedOn,
          resumeCollections: resume,
          chargeNsfFee: reason === "nsf" ? chargeNsfFee : true,
          nsfFeeWaiveReason: waiveReason,
          bankMemos,
        });
        return { ok: true };
      }}
    >
      {/* ④ **WHO IS SKIPPED, AND WHY — the sentence before the table.** Only
          when somebody IS skipped: *"3 of 3 will be reversed. 0 are skipped."*
          is B14 rule 32's noise on the common case. */}
      {split.skipped.length > 0 && (
        <p data-bulk-split="reverse">
          {t("payments.bulk.willRun", {
            run: willRun,
            total: props.rows.length,
            skipped: split.skipped.length,
          })}
        </p>
      )}

      {/* ⑤ **PER ROW — *a clerk reverses payments, not a number*.** */}
      <SelectionRowPreview
        caption={t("payments.bulk.previewCaption.reverse")}
        columns={{
          label: t("payments.bulk.col.payment"),
          owner: t("payments.bulk.col.account"),
          amount: t("payments.bulk.col.amount"),
          outcome: t("payments.bulk.col.willHappen"),
        }}
        rows={previewRows(
          props.rows,
          split,
          translate,
          props.currency,
          t("payments.bulk.outcome.willReverse"),
        )}
      />

      <SelectField
        id="bulk_reverse_reason"
        label={t("payments.reverse.reason")}
        value={reason}
        onChange={(next) => setReason(next as ReversalReason)}
        required
        options={REVERSAL_REASONS.map((code) => ({
          value: code,
          label: t(`payments.reverse.reason.${code}`),
        }))}
        // ⑥ *"One reason for all of them · said out loud, because the four
        // reasons do different things"*. It REPLACED `payments.bulk.
        // reverseNoApproval` (*"A payment needing approval is reversed on its
        // own row"*), which the drawing does not carry and which B14 rule 32
        // will not let stand beside it — one sentence per section. That key is
        // KEPT in the catalogues: it is a true fact about a path that still
        // exists, and retiring a string from eleven catalogues is the expensive
        // half of putting it back.
        help={t("payments.bulk.reverseWhyHelp")}
      />
      <DatePickerField
        id="returned_on"
        label={t("payments.reverse.returnedOn")}
        value={returnedOn}
        onChange={setReturnedOn}
        dateFormat={props.dateFormat}
        required
      />
      <CheckboxField
        id="bulk_resume_collections"
        label={t("payments.reverse.resume")}
        checked={resume}
        onChange={setResume}
      />
      {/* DEF-PAY-10698 · LBX-04 — each payment's own NSF fee, before Confirm,
          and its own Bank memo. The fee is billing's quote for that payment's
          plan; the tick and its reason apply to the whole run. */}
      {reason === "nsf" && (
        <NsfFeeChoice
          idPrefix="bulk_"
          charge={chargeNsfFee}
          onCharge={setChargeNsfFee}
          waiveReason={waiveReason}
          onWaiveReason={setWaiveReason}
        />
      )}
      <BulkNsfFeeTable
        rows={split.eligible}
        reason={reason}
        returnedOn={returnedOn}
        client={client}
        chargeFee={chargeNsfFee}
        memos={bankMemos}
        onMemo={(id, value) => setBankMemos((current) => ({ ...current, [id]: value }))}
        label={(row) => rowLabel(row, translate)}
      />

      {/* ⑦ **WHAT IT WILL DO, IN THE CUSTOMER'S TERMS** — B14 rule 11's
          consequence preview, which the blueprint files as a breach: *"A bulk
          reversal writes money across several accounts and shows no 'what this
          will do' box at all — the same gap as the three single-payment forms,
          one level up and multiplied by the selection."*

          ⚠ **DRAWN ONLY WHEN THERE IS SOMETHING TO SAY.** With nothing
          eligible the run does nothing, and a box promising that nothing will
          happen is worse than no box. */}
      {willRun > 0 && (
        <ConsequenceBox
          tone="check"
          data-consequence="bulk-reverse"
          title={
            consequence.amount === null || props.currency === null
              ? t("payments.bulk.consequence.accounts", { count: consequence.accounts })
              : t("payments.bulk.consequence.money", {
                  amount: formatMoney(consequence.amount, props.currency),
                  count: consequence.accounts,
                })
          }
          body={t("payments.bulk.consequence.bills", { count: consequence.bills })}
        />
      )}
    </FormModal>
  );
}

/**
 * The selection as rows this preview can draw, in the clerk's own order.
 *
 * ⚠ **EVERY ROW OF THE SELECTION IS DRAWN, NOT ONLY THE ELIGIBLE ONES.** The
 * skipped rows are the whole reason the table exists — note ④ of 2·1b is *"Who
 * is skipped, **and why**"* — and a table of survivors would answer the
 * question the count already answered.
 */
function previewRows(
  rows: readonly PaymentRow[],
  split: SelectionSplit,
  t: Translator,
  currency: string | null,
  willHappen: string,
): SelectionPreviewRow[] {
  const refusalById = new Map(split.skipped.map((entry) => [entry.row.id, entry.reason]));
  return rows.map((row) => {
    const refusal = refusalById.get(row.id) ?? null;
    return {
      id: row.id,
      // B14 rule 31: the payment NUMBER, or the stated absence. Never the uuid.
      label: rowLabel(row, t),
      owner: row.account_no ?? t("payments.row.noNumber"),
      amount: currency === null ? "—" : formatMoney(row.amount, row.currency ?? currency),
      outcome: refusal ?? willHappen,
      skipped: refusal !== null,
    };
  });
}
