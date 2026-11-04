// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.28–P2.31 (lane MVI-WIZ-BILL) — the Billing step's
//           OWN state (images 41–44): the three ticks and what each opens,
//           the fees a clerk adds, and the payment. What it adds to Complete
//           (§9.MONEY), to a parked draft, and what holds Continue.
// Rules:    CLAUDE.md hard rule 2 (money is a 4-place STRING; the totals here
//           are `moneyMath.sumAmounts` — exact, never a float) · OQ-BIL-12788
//           CLOSED (a) (a move-in fee is never taxed at move-in — nothing here
//           carries a tax) · decision log 2026-10-05 *"FOUR PO RULINGS"* (2) (a
//           billing clerk records the discount and the exemption; nothing is
//           held for a System Admin) · BR-CUS-059 (autopay is capture-only)
// Change:   CR-171-BRC10 lane RULINGS-2 — PO ruling (7) of 2026-10-05
//           (decision log *"A CLERK CAN STILL WAIVE THE DEPOSIT"*): *"(a).
//           Clerks use it today, the server already supports it, and the fix
//           for 'waived deposit still billed' is already in place."* The
//           deposit row's waive (`depositWaive`), sent as the server's own.
// Tests:    07-frontend/src/features/customers/moveInWizard/StepBilling.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE TWO FIGURES THIS FILE WORKS OUT, AND WHY THEY ARE LAWFUL HERE.**
// The Fees *Total* and *"$115.00 goes on the first bill."* are sums and a
// difference of the SERVER's own 4-place strings, done by `sumAmounts` in
// BigInt — the same exact arithmetic `DEF-LED-6717` put in the kit so a table
// foots to its own rows. Nothing is priced, rounded or taxed here: every row's
// amount is rating's (`GET /move-ins/fees`, `/fees/quote`), and at Complete the
// server prices every row again and answers the real `on_first_bill`
// (`move_fees.take_payment`). The screen's figure is the same arithmetic on the
// same strings, shown before the commit so the clerk can say it at the counter.

import { amountScale, MoneyAmountUnaddable, scaledAmount, sumAmounts } from "@/components/moneyMath";
import type { MoveFeeRow } from "@/api/moveInMoneyEndpoints";

export type PaymentMode = "pay_now" | "add_to_bill";

/** One *Discounts* row — a discount the unit's plan carries (§9.MONEY). */
export interface DiscountRowForm {
  key: string;
  /** The plan discount's `ref.id`. ⚠ Posted, NEVER rendered (B14 rule 31). */
  discountId: string;
  note: string;
}

/** The certificate as it travels in the commit (§9.MONEY: base64 in the body,
 *  so a move-in whose certificate cannot be filed opens no account). */
export interface CertificateFile {
  name: string;
  contentType: string;
  base64: string;
}

export interface TaxForm {
  categoryId: string;
  certificateRef: string;
  issuedOn: string;
  expiresOn: string;
  file: CertificateFile | null;
}

/** A fee the clerk added by charge code (*+ Add fee*, image 43). */
export interface AddedFee {
  key: string;
  /** The code chosen — `""` while the row is still being searched. */
  code: string;
  /** What the cell shows once chosen: `RUSH · Same-day turn-on`. */
  label: string;
  /** Rating's quote, 4-place, or `null` (a `per_case` code, a refusal). */
  quoted: string | null;
  pricedBy: string | null;
  refusal: string | null;
  /** The clerk's figure — only for a `per_case` code. */
  typed: string;
  note: string;
}

export interface PaymentForm {
  mode: PaymentMode;
  methodCode: string;
  /** `""` = not touched, so the box shows the whole total (image 41). */
  amount: string;
  confirmation: string;
  receivedOn: string;
}

export interface StepBillingOwn {
  prefsOn: boolean;
  /** *Autopay from* — a payments instrument `ref`. */
  autopayFrom: string;
  discountsOn: boolean;
  discounts: DiscountRowForm[];
  taxOn: boolean;
  tax: TaxForm;
  /** The plan's own rows as `GET /move-ins/fees` served them; `null` until read. */
  planRows: MoveFeeRow[] | null;
  /** The note typed on a plan row, by code. */
  planNotes: Record<string, string>;
  added: AddedFee[];
  payment: PaymentForm;
  /**
   * ⚖️ The plan's deposit WAIVED by the clerk, with its required reason, or
   * `null` while it is charged (PO ruling (7), 2026-10-05). A waived deposit
   * adds nothing to the Total or the first bill and travels as the server's
   * existing waive — `deposit: {decision: "waived", amount, waive_reason}`,
   * exactly what the old Deposit step sent (`depositCapability.depositPayload`).
   */
  depositWaive: { reason: string } | null;
}

export function emptyStepBillingOwn(): StepBillingOwn {
  return {
    prefsOn: true,
    autopayFrom: "",
    discountsOn: false,
    discounts: [],
    taxOn: false,
    tax: { categoryId: "", certificateRef: "", issuedOn: "", expiresOn: "", file: null },
    planRows: null,
    planNotes: {},
    added: [],
    payment: { mode: "pay_now", methodCode: "", amount: "", confirmation: "", receivedOn: "" },
    depositWaive: null,
  };
}

let nextKey = 0;
/** A row key — never posted and never rendered. */
export function rowKey(prefix: string): string {
  nextKey += 1;
  return `${prefix}-${nextKey}`;
}

/** An amount typed in a money box: digits, at most four places, nothing else. */
const TYPED_MONEY = /^\d+(\.\d{1,4})?$/;

export function typedMoneyOk(text: string): boolean {
  return TYPED_MONEY.test(text.trim());
}

/** The figure an added row charges, or `null` while it has none. */
export function addedAmount(row: AddedFee): string | null {
  if (row.code === "" || row.refusal !== null) return null;
  if (row.pricedBy === "per_case") {
    return typedMoneyOk(row.typed) ? row.typed.trim() : null;
  }
  return row.quoted;
}

/** Every amount the table charges, plan rows first. Unpriced rows add nothing
 *  — and they hold Continue (`billingProblems`), so a total never stands for
 *  a table that is not whole. */
export function feeAmounts(own: StepBillingOwn): string[] {
  const plan = chargedPlanRows(own)
    .map((row) => row.amount)
    .filter((a): a is string => a !== null);
  const added = own.added.map(addedAmount).filter((a): a is string => a !== null);
  return [...plan, ...added];
}

/** The table's Total — exact, from the rows (`moneyMath.sumAmounts`). */
export function feesTotal(own: StepBillingOwn): string {
  return sumAmounts(feeAmounts(own));
}

/** What Pay now takes: the typed amount, or the whole total while untouched. */
export function paidNow(own: StepBillingOwn): string {
  if (own.payment.mode !== "pay_now") return "0.0000";
  const typed = own.payment.amount.trim();
  return typed === "" ? feesTotal(own) : typed;
}

/** Image 43's sentence: what is left for the first bill. `null` when the typed
 *  amount is not a figure (the field says why). */
export function onFirstBill(own: StepBillingOwn): string | null {
  const paid = paidNow(own);
  if (own.payment.mode === "pay_now" && !typedMoneyOk(paid)) return null;
  try {
    return sumAmounts([feesTotal(own), `-${paid}`]);
  } catch (error) {
    if (error instanceof MoneyAmountUnaddable) return null;
    throw error;
  }
}

/** `a > b`, exactly, for two fixed-point strings. */
export function moreThan(a: string, b: string): boolean {
  const scale = Math.max(amountScale(a), amountScale(b), 4);
  return scaledAmount(a, scale) > scaledAmount(b, scale);
}

/** `a == 0`, exactly. */
export function isZero(a: string): boolean {
  return scaledAmount(a, Math.max(amountScale(a), 4)) === 0n;
}

/** The field each problem belongs to — a field id on this step. */
export type BillingProblem =
  | "fees_unread"
  | "fee_row"
  | "payment_method"
  | "payment_amount"
  | "payment_more"
  | "payment_received"
  | "discount_row"
  | "tax_category"
  | "tax_ref"
  | "tax_expires"
  | "tax_file";

/**
 * What holds Continue. Each mirrors a refusal the SERVER makes at Complete
 * (§9.MONEY) so the clerk meets it on this step, not as a refusal after the
 * whole move-in; the server's refusal is what actually holds.
 *
 * ⚠ **AUTOPAY FROM IS NOT HERE** although image 41 marks it required: no read
 * serves a customer's saved payment methods to this step (`DEF-CUS-9739`), so a
 * required box with nothing to choose would hold every move-in with autopay on.
 */
export function billingProblems(own: StepBillingOwn): BillingProblem[] {
  const out: BillingProblem[] = [];
  if (own.planRows === null) out.push("fees_unread");
  if (own.added.some((row) => addedAmount(row) === null)) out.push("fee_row");
  const total = own.planRows === null ? null : feesTotal(own);
  if (own.payment.mode === "pay_now" && total !== null && !isZero(total)) {
    if (own.payment.methodCode === "") out.push("payment_method");
    const paid = paidNow(own);
    if (!typedMoneyOk(paid) || isZero(paid)) out.push("payment_amount");
    else if (moreThan(paid, total)) out.push("payment_more");
    if (own.payment.receivedOn === "") out.push("payment_received");
  }
  if (own.discountsOn && own.discounts.some((row) => row.discountId === "")) out.push("discount_row");
  if (own.taxOn) {
    if (own.tax.categoryId === "") out.push("tax_category");
    if (own.tax.certificateRef.trim() === "") out.push("tax_ref");
    if (own.tax.expiresOn === "") out.push("tax_expires");
    if (own.tax.file === null) out.push("tax_file");
  }
  return out;
}

/** The plan rows the move-in CHARGES: every one, less a waived deposit. */
export function chargedPlanRows(own: StepBillingOwn): MoveFeeRow[] {
  const rows = own.planRows ?? [];
  return own.depositWaive === null ? rows : rows.filter((row) => row.kind !== "deposit");
}

/** The deposit row the plan asks, priced, or `null`. */
export function planDeposit(own: StepBillingOwn): MoveFeeRow | null {
  return (own.planRows ?? []).find((row) => row.kind === "deposit" && row.amount !== null) ?? null;
}

/**
 * What this step adds to `POST …/move-in` (§9.MONEY). Merged LAST over the
 * wizard's body, so `deposit` and `tax_exempt*` here REPLACE the wizard's old
 * Deposit/Preferences values — on purpose: the new form decides them.
 *
 * `autopay` itself and paperless / text reminders / portal language stay the
 * wizard's (`ctx.preferences`), written by this step's dropdowns.
 */
export function billingPayload(own: StepBillingOwn): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (own.planRows !== null) {
    // A waived deposit writes NO deposit line — the server refuses a deposit
    // row beside a waive (`move_fees.DEPOSIT_NOT_OWED`).
    const fees: Record<string, unknown>[] = chargedPlanRows(own)
      .filter((row) => row.amount !== null)
      .map((row) => {
        const fee: Record<string, unknown> = { kind: row.kind, source: "plan", code: row.code, amount: row.amount };
        const note = (own.planNotes[row.code] ?? "").trim();
        if (note !== "") fee.note = note;
        return fee;
      });
    for (const row of own.added) {
      const amount = addedAmount(row);
      if (amount === null) continue;
      const fee: Record<string, unknown> = { kind: "fee", source: "charge_code", code: row.code, amount };
      if (row.note.trim() !== "") fee.note = row.note.trim();
      fees.push(fee);
    }
    out.fees = fees;
    const deposit = planDeposit(own);
    if (deposit !== null && own.depositWaive !== null) {
      // The server's existing waive (BR-CUS-1050): a reason, kept on the
      // account; the first bill then skips it (`DEF-BIL-9709`).
      out.deposit = { decision: "waived", amount: deposit.amount, waive_reason: own.depositWaive.reason.trim() };
    } else if (deposit !== null) {
      // `required` with no `take_now` — the money is `payment`'s (§9.MONEY).
      out.deposit = { decision: "required", amount: deposit.amount };
    }
    if (fees.length > 0) {
      out.payment =
        own.payment.mode === "add_to_bill"
          ? { mode: "add_to_bill" }
          : {
              mode: "pay_now",
              method_code: own.payment.methodCode,
              amount: paidNow(own),
              ...(own.payment.confirmation.trim() === "" ? {} : { confirmation: own.payment.confirmation.trim() }),
              received_on: own.payment.receivedOn,
            };
    }
  }
  // The step clears `autopayFrom` the moment Autopay is set Off, so a source
  // never travels without autopay on (the server refuses that pair too).
  if (own.prefsOn && own.autopayFrom !== "") {
    out.autopay_instrument_id = own.autopayFrom;
  }
  if (own.discountsOn) {
    const claims = own.discounts
      .filter((row) => row.discountId !== "")
      .map((row) => (row.note.trim() === "" ? { discount_id: row.discountId } : { discount_id: row.discountId, note: row.note.trim() }));
    if (claims.length > 0) out.discount_claims = claims;
  }
  // ⚖️ `DEF-CUS-9724` (PO 2026-10-05: *"An exemption removes only the tax
  // named on its certificate. The church pays $6.25."*). The account's BLANKET
  // flag zeroes every authority at once, so this step never sets it: it sends
  // `false` (replacing the old Preferences form's value) and the certificate
  // block alone carries the exemption. The server drops the blanket columns
  // beside a certificate too (`move_in_preferences.merge_account_values`).
  out.tax_exempt = false;
  if (own.taxOn) {
    const exemption: Record<string, unknown> = {
      category_id: own.tax.categoryId,
      certificate_ref: own.tax.certificateRef.trim(),
    };
    if (own.tax.issuedOn !== "") exemption.issued_on = own.tax.issuedOn;
    if (own.tax.expiresOn !== "") exemption.expires_on = own.tax.expiresOn;
    if (own.tax.file !== null) {
      exemption.certificate = {
        name: own.tax.file.name,
        content_type: own.tax.file.contentType,
        content_base64: own.tax.file.base64,
      };
    }
    out.tax_exemption = exemption;
  }
  return out;
}

/**
 * What rides in a parked draft. ⚠ **THE CERTIFICATE'S BYTES DO NOT** — a draft
 * is a JSON row a week old, and a file belongs in the commit or nowhere; the
 * clerk who resumes picks it again. The plan's rows are not parked either:
 * they are re-read, because a plan edited in the meantime is the plan Complete
 * will price.
 */
export function billingPark(own: StepBillingOwn): Record<string, unknown> {
  const parked: Record<string, unknown> = { ...own, tax: { ...own.tax, file: null } };
  delete parked.planRows;
  return parked;
}

/** A parked draft back — distrusted field by field, as `hydrateForm` does. */
export function billingHydrate(parked: unknown): StepBillingOwn {
  const base = emptyStepBillingOwn();
  if (parked === null || typeof parked !== "object") return base;
  const p = parked as Record<string, unknown>;
  const bool = (v: unknown, d: boolean) => (typeof v === "boolean" ? v : d);
  const str = (v: unknown) => (typeof v === "string" ? v : "");
  const obj = (v: unknown) => (v !== null && typeof v === "object" ? (v as Record<string, unknown>) : {});
  const tax = obj(p.tax);
  const pay = obj(p.payment);
  const waive = obj(p.depositWaive);
  const notes = obj(p.planNotes);
  return {
    ...base,
    prefsOn: bool(p.prefsOn, base.prefsOn),
    autopayFrom: str(p.autopayFrom),
    discountsOn: bool(p.discountsOn, false),
    discounts: Array.isArray(p.discounts)
      ? p.discounts.map((row) => {
          const r = obj(row);
          return { key: rowKey("discount"), discountId: str(r.discountId), note: str(r.note) };
        })
      : [],
    taxOn: bool(p.taxOn, false),
    tax: {
      categoryId: str(tax.categoryId),
      certificateRef: str(tax.certificateRef),
      issuedOn: str(tax.issuedOn),
      expiresOn: str(tax.expiresOn),
      file: null,
    },
    planNotes: Object.fromEntries(Object.entries(notes).map(([k, v]) => [k, str(v)])),
    added: Array.isArray(p.added)
      ? p.added.map((row) => {
          const r = obj(row);
          return {
            key: rowKey("fee"),
            code: str(r.code),
            label: str(r.label),
            quoted: typeof r.quoted === "string" ? r.quoted : null,
            pricedBy: typeof r.pricedBy === "string" ? r.pricedBy : null,
            refusal: typeof r.refusal === "string" ? r.refusal : null,
            typed: str(r.typed),
            note: str(r.note),
          };
        })
      : [],
    payment: {
      mode: pay.mode === "add_to_bill" ? "add_to_bill" : "pay_now",
      methodCode: str(pay.methodCode),
      amount: str(pay.amount),
      confirmation: str(pay.confirmation),
      receivedOn: str(pay.receivedOn),
    },
    depositWaive: str(waive.reason).trim() === "" ? null : { reason: str(waive.reason) },
  };
}
