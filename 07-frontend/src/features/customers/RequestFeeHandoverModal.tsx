// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6376 — *Record what was handed over* on a service request
//           was not the Record-a-payment form. PO, on SR-26-0016, verbatim:
//           *"this screens takes the payment it should be similar to record
//           payment form so pasting date, type of payment , memo and it will
//           take only application fee"* ("pasting" is *posting*).
//           DEF-CUS-6374 — the same door took cash with no open till.
// Screens:  S84 (REQ-02) — the modal behind the Fees block's
//           `Record what was handed over`
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — this modal lived inline
//           in a 2,884-line page, importable by nothing) · rule 38 (what a form
//           CONTAINS is the drawing's; how it is BUILT is ours) · rule 33 (the
//           copy caps) · rule 31 (no database id on screen) · rule 21 (Tailwind
//           utilities, no stylesheet class) · CLAUDE.md hard rule 2 (money is a
//           decimal STRING end to end) · BR-TEN-081 (the posting date is the
//           TENANT's day) · BR-CUS-090 (the WHOLE fee or waived — a short
//           payment is refused, OQ-CUS-12624, DEF-CUS-6455) · BR-PAY-026 (the tenant's own method list) · PO 2026-09-23 §3.4 and
//           OQ-PAY-12601 (money through hands needs an open till)
// Tests:    src/features/customers/RequestFeeHandoverModal.dom.test.tsx ·
//           src/features/customers/ServiceRequestDetailPage.dom.test.tsx (the
//           Taken / Waived cases, unchanged) ·
//           src/features/customers/ServiceRequestDetailPage.test.tsx
//           (COLLECT_SCHEMA, re-exported from the page)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS NOT `RecordPaymentForm`, AND WHAT IT SHARES WITH IT
// ══════════════════════════════════════════════════════════════════════════
// `RecordPaymentForm` (payments/RecordPaymentPage.tsx) is a PAGE form built
// around an ACCOUNT: an account picker, `POST /accounts/{id}/payments`, four
// purposes, three types, an allocation choice, an open-bill picker, a plan
// strip and a consequence box that all read the account. **A service request
// has no account until it is approved** (decision log 2026-09-19, *OPTION A2 —
// the ledger posts at collection and the payment row is created when the
// account exists*), so the money goes to `POST /service-requests/{id}/
// fee-collection` and becomes a `counter_receipts` row, never a payment row.
// Serving this payer from `RecordPaymentForm` would have meant switching off
// seven of its blocks and replacing its submit — far more than a narrow prop
// on the payments module's main form.
//
// **So this SHARES THE FIELD SET rather than the block** — B14 rule 43's own
// words for two hosts that draw one block differently: *"share the FIELD SET
// and let each host own its construction (rule 38), never fork the block."*
// Concretely, and each is the payments module's own, not a copy:
//
//   * the SAME kit fields (`TextField`, `DatePickerField`, `SelectField`);
//   * the SAME catalogue keys for the five shared fields — `payments.form.
//     amount`, `.amountBrief`, `.postedAt`, `.postedAtBrief`, `.method`,
//     `.methodPlaceholder`, `.confirmation`, `.memo` — so the two screens say
//     the same word for the same fact and a fix to one reaches both;
//   * the SAME served method list — `GET /payments` `methods[]`, under the
//     same query key `RecordPaymentPage` reads it with, through
//     `paymentsShared.methodOptions` (BR-PAY-026: never a literal array);
//   * the SAME till banner — `RecordCounterBanner`, with the one narrow prop
//     this payer needs (`announceBatch={false}`, see below).
//
// And in Record-a-payment's ORDER (the PO's 2026-09-03 order: HOW MUCH → WHAT
// IT IS FOR → WHEN → HOW → the memo), with the fields that belong to an
// account left out: no account, no cleared date, no type, no apply-to.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IT IS FOR IS A FACT, NOT A PICKER
// ══════════════════════════════════════════════════════════════════════════
// *"it will take only application fee"*. Record a payment asks *what this
// money is for* with a select of four; here the answer is fixed, so it is
// SHOWN in the same position as a read-only field — `TextField`'s `readOnly`
// is the kit's shape for *"a value the user may READ but not set"* — and
// nothing about it is posted: the endpoint IS the application-fee door.
//
// ══════════════════════════════════════════════════════════════════════════
// THE RECEIPT NUMBER STAYS, AND IT IS NOT RECORD A PAYMENT'S REFERENCE
// ══════════════════════════════════════════════════════════════════════════
// Two numbers, opposite directions. **Reference** (`payments.form.
// confirmation`) is the number on the instrument THE CUSTOMER handed over — a
// check number, a card authorisation, a money-order serial. **Receipt
// number** is the number on the slip THE CLERK handed back (`RCP-26-4471`).
// BR-CUS-090 names the second (*"ONE receipt number"*), the server requires it
// and is idempotent on it (hard rule 6 — the desk is where a double-click
// happens), and `counter_receipts.receipt_no` is where finance reconciles the
// drawer against. Dropping it for the reference would lose the one number the
// counter itself wrote. So both are asked: the reference only where the
// method has one (not cash), the receipt always.
//
// ══════════════════════════════════════════════════════════════════════════
// THE WAIVE HALF MOVED HERE UNCHANGED
// ══════════════════════════════════════════════════════════════════════════
// PO ruling 2026-09-22 put *Taken* and *Waived* at the head of this modal; the
// waive branch, `WAIVE_SCHEMA` and their comments came across from the page
// as they were. Only the TAKEN branch was rebuilt.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError, UNEXPECTED_ERROR_KEY } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import { todayInZone } from "@/components/DateCell";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { RecordCounterBanner } from "@/features/payments/CounterDoors";
import { methodOptions, reasonOptions, useReasonCodes } from "@/features/payments/paymentsShared";

import { collectServiceRequestFee, waiveServiceRequestFee } from "./serviceRequestEndpoints";
import type { ServiceRequestFeesTab } from "./serviceRequestEndpoints";

/**
 * **BR-CUS-090 — THE SHAPE OF THE THREE MONEY FIELDS, AND NOT THE RULE ON THE
 * AMOUNT.**
 *
 * `amount` must be a non-empty decimal STRING and `receipt_no` must be present.
 * **The comparison against the fee owing is the SERVER's** (`collect_fee`,
 * `OQ-CUS-12624`, PO 2026-09-24: *"all or waived"*): an amount that is not the
 * whole fee still owing is refused, naming it — quoted $130.00, `25.00` →
 * *"Take the full $130.00. Or waive it."* It lives in one place so this form
 * and any other door cannot come to disagree about it; `submit` below only
 * formats the figure the refusal names.
 *
 * ⛔ SUPERSEDED 2026-09-24: this block read *"There is no comparison against
 * the quote, and its absence is the ruling"*, on BR-CUS-090's 2026-08-24 desk
 * clause *"we acept it and in finance we will reconcile"*.
 *
 * ⚠ **MOVED FROM `ServiceRequestDetailPage.tsx` UNCHANGED, AND RE-EXPORTED
 * THERE**, because `ServiceRequestDetailPage.test.tsx` imports it from the
 * page. The posting date is added by `feeHandoverSchema` below rather than
 * here, so this object still says exactly what it said.
 */
export const COLLECT_SCHEMA = z.object({
  // A STRING END TO END (rule 2). `.regex` rather than `z.coerce.number()`:
  // coercing here would put an IEEE double on the wire, which is the exact
  // thing `_money_field` refuses by name on the server.
  amount: z
    .string()
    .trim()
    .regex(/^-?\d+(\.\d{1,4})?$/),
  method: z.string().trim().min(1),
  receipt_no: z.string().trim().min(1),
});

/**
 * **THE TAKEN HALF, WITH RECORD A PAYMENT'S POSTING DATE — DEF-CUS-6376.**
 *
 * Required exactly as `recordPaymentSchema` requires it, with the same
 * sentence. It is PROPOSED as the tenant's today (`DatePickerField`'s
 * `prefill`), never read from a clock on submit.
 */
export function feeHandoverSchema(t: (key: string) => string) {
  return COLLECT_SCHEMA.extend({
    posted_at: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, t("payments.form.postedAtRequired")),
  });
}

/**
 * **WAIVING ASKS FOR A REASON AND FOR NOTHING ELSE — PO ruling 2026-09-22,
 * verbatim *"on modal you ahve to give Waive off button"*, then *"button or
 * options"*.**
 *
 * ⚠ **A SEPARATE SCHEMA, WHICH IS THE WHOLE REASON THE CHOICE IS AT THE HEAD
 * OF THE MODAL RATHER THAN A THIRD FOOTER BUTTON.** A waive has no amount, no
 * tender and no receipt; a footer button would leave `COLLECT_SCHEMA`'s three
 * REQUIRED money fields on screen with nothing a waive could lawfully put in
 * them, and a modal titled *what was handed over* cannot be submitted by
 * somebody stating that nothing was. The decision-log entry of 2026-09-22
 * records that judgment and why the PO's *"button or options"* was read as
 * options.
 */
export const WAIVE_SCHEMA = z.object({
  reason: z.string().trim().min(1),
});

/**
 * **THE AMOUNT STILL OWING, AS A CLERK WOULD TYPE IT — never through a float.**
 *
 * The server serves money at four places (`"70.0000"`). A counter takes whole
 * cents, so two trailing zeros are dropped — `"70.0000"` → `"70.00"` — and
 * anything else is left exactly as served (`"70.1250"` stays), because
 * rounding a figure here would be deciding somebody's money in a text box
 * (hard rule 2: round at display, never at entry). Nothing owing, a negative
 * figure (the counter took more than the quote) or an unreadable one proposes
 * nothing.
 */
export function owingAsTyped(outstanding: string | null | undefined): string {
  const text = (outstanding ?? "").trim();
  const match = /^(\d+)(?:\.(\d{1,4}))?$/.exec(text);
  if (match === null || /^0*(\.0*)?$/.test(text)) {
    return "";
  }
  const whole = match[1] ?? "0";
  const places = (match[2] ?? "").padEnd(4, "0");
  return places.endsWith("00") ? `${whole}.${places.slice(0, 2)}` : `${whole}.${places}`;
}

/** The refusal that names the whole fee — `OQ-CUS-12624`, `DEF-CUS-6455`. */
const TAKE_IN_FULL_KEY = "customers.serviceRequest.feeTakeInFull";

/**
 * **THE FEE A REFUSAL NAMES, AT TWO PLACES WITH ITS CURRENCY — hard rule 2.**
 *
 * The server names the fee still owing as it stores it (`"130.0000"`, `"USD"`)
 * because it cannot know the reader's locale; the catalogue sentence reads
 * `{{amount}}` as a person would say it. So that one refusal's `amount` is
 * rendered through `formatMoney` — *"Take the full $130.00. Or waive it."* —
 * and every other envelope passes through untouched.
 */
export function withTheFeeFormatted<T extends { message_key: string; params?: Record<string, unknown> }>(
  envelope: T,
): T {
  const params = envelope.params ?? {};
  const amount = params.amount;
  const currency = params.currency;
  if (envelope.message_key !== TAKE_IN_FULL_KEY || typeof amount !== "string" || typeof currency !== "string") {
    return envelope;
  }
  return { ...envelope, params: { ...params, amount: formatMoney(amount, currency) } };
}

/**
 * The one tender that carries no reference. A check has its number, a card
 * its authorisation, a money order its serial; cash has nothing to write.
 * It is the tenant's `payment_methods.code`, the same vocabulary the list is
 * served in.
 */
const CASH_CODE = "cash";

export interface RequestFeeHandoverModalProps {
  requestId: string;
  client?: ApiClient;
  /** The Fees block the page already holds — the amount still owing and, for
   *  the waive, which line. */
  fees: ServiceRequestFeesTab;
  /** The one fee row a waive lands on, or `null` — then `Waived` is not
   *  offered from here at all (`DEF-CUS-6096`). */
  waivableLineId: string | null;
  /** Which of the two the modal opens on: the head's door opens `taken`, a
   *  line's `Waive` opens `waived`. */
  initialKind: "taken" | "waived";
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  /** After a successful post — the page refetches the request. */
  onDone: () => Promise<unknown> | void;
}

export function RequestFeeHandoverModal(props: RequestFeeHandoverModalProps) {
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>) => t(key, params);
  const client = props.client ?? api;
  // BR-PAY-033 / BR-TEN-081 — PROPOSED as the tenant's today, never read on
  // submit from a clock: the field holds it from the moment the form opens.
  const today = todayInZone(props.timeZone);

  const [kind, setKind] = useState<"taken" | "waived">(props.initialKind);
  const [amount, setAmount] = useState(() => owingAsTyped(props.fees.outstanding.amount));
  const [postedAt, setPostedAt] = useState("");
  const [method, setMethod] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [receipt, setReceipt] = useState("");
  const [memo, setMemo] = useState("");
  const [waiveReason, setWaiveReason] = useState("");
  const needsReference = method !== "" && method !== CASH_CODE;

  // ⚠ **THE SAME READ, UNDER THE SAME KEY, AS `RecordPaymentPage`** — one
  // row of `GET /payments` for its `methods[]`, so the two forms share one
  // cache entry and cannot offer different lists of the same thing. p038:
  // *"value and options both served from GET /payments methods[] — never a
  // literal array"*. The list this replaced was typed by hand as three.
  const lookups = useQuery({
    queryKey: ["payments", "record-new-lookups"],
    queryFn: () => getPayments({ per: 1 }, client),
    retry: false,
  });
  // The tenant's own live reasons, read ONLY once a waive is being written.
  const reasonCodes = useReasonCodes(client, kind === "waived");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      if (kind === "waived") {
        await waiveServiceRequestFee(
          props.requestId,
          props.waivableLineId ?? "",
          waiveReason.trim(),
          client,
        );
      } else {
        await collectServiceRequestFee(
          props.requestId,
          {
            // ⚠ A STRING, ALWAYS. A JSON float arrives at Python as an IEEE
            // double — `25.10` becomes `25.099999999999998` — and on a counter
            // endpoint that is a customer's cash (rule 2). The server refuses a
            // float by name rather than coercing it.
            amount: amount.trim(),
            method,
            receipt_no: receipt.trim(),
            // BR-TEN-081: a calendar date, which the server reads as the
            // TENANT's day. The field proposed today in the tenant's zone.
            posted_at: postedAt === "" ? today : postedAt,
            // Sent only where it is drawn — a hidden field that keeps posting
            // is how a cash receipt acquires a check number nobody typed.
            confirmation: needsReference && confirmation.trim() !== "" ? confirmation.trim() : null,
            memo: memo.trim() === "" ? null : memo.trim(),
          },
          client,
        );
      }
      await props.onDone();
      props.onClose();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: withTheFeeFormatted(formErrorEnvelope(error)) };
      }
      return { ok: false, error: { code: "UNEXPECTED", message_key: UNEXPECTED_ERROR_KEY } };
    }
  }

  return (
    <FormModal
      /* ⚠ **THE `taken` TITLE IS THE KEY THAT WAS ALREADY THERE.** Minting a
         `.taken` twin of a string all eleven catalogues already hold would
         leave the original DEAD — a key nothing asks for, which is what `G18`
         counts — and two spellings of one sentence, which is what rule 34
         refuses. Only the waive needed new words. */
      title={t(
        kind === "waived"
          ? "customers.serviceRequest.collect.title.waived"
          : "customers.serviceRequest.collect.title",
      )}
      schema={kind === "waived" ? WAIVE_SCHEMA : feeHandoverSchema(translate)}
      values={
        kind === "waived"
          ? { reason: waiveReason }
          : {
              amount,
              method,
              receipt_no: receipt,
              posted_at: postedAt === "" ? today : postedAt,
            }
      }
      submitLabel={t(
        kind === "waived"
          ? "customers.serviceRequest.collect.submit.waived"
          : "customers.serviceRequest.collect.submit",
      )}
      onClose={props.onClose}
      onSubmit={submit}
    >
      {/* THE CHOICE, FIRST — everything below it follows from this. */}
      {props.waivableLineId !== null && (
        <fieldset className="m-0 min-w-0 border-0 p-0" data-handover-kind={kind}>
          <legend className="mb-2 p-0 text-xs font-semibold uppercase tracking-wide text-accent">
            {t("customers.serviceRequest.collect.whatHappened")}
          </legend>
          <div className="flex flex-wrap gap-2" role="radiogroup">
            {(["taken", "waived"] as const).map((option) => (
              <label
                key={option}
                data-handover-option={option}
                className={`flex cursor-pointer items-center gap-2 border px-3 py-2 ${
                  kind === option ? "border-accent bg-accent-100" : "border-divider"
                }`}
              >
                <input
                  type="radio"
                  name="handover-kind"
                  value={option}
                  checked={kind === option}
                  onChange={() => setKind(option)}
                />
                <span className="font-semibold">
                  {t(`customers.serviceRequest.collect.kind.${option}`)}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {kind === "waived" ? (
        <>
          <SelectField
            id="reason"
            label={t("customers.serviceRequest.collect.reason")}
            required
            value={waiveReason}
            onChange={setWaiveReason}
            placeholder={t("customers.serviceRequest.collect.pickAReason")}
            options={reasonOptions(reasonCodes.data?.reasons ?? [])}
          />
          {/* ⚠ **AN EMPTY PICKER SAYS SO.** A tenant with no live reason
              cannot waive from here, and a control that simply offers nothing
              reads as broken. `BR-SHL-025`: the refusal is in words beside the
              thing it is about. */}
          {(reasonCodes.data?.reasons ?? []).length === 0 && !reasonCodes.isFetching && (
            <p className="field-error" role="alert" data-no-reasons="">
              {t("customers.serviceRequest.collect.noReasons")}
            </p>
          )}
        </>
      ) : (
        <>
          {/* ── WHICH TILL — the same banner Record a payment draws ──────────
              It STATES the position and refuses nothing: the refusal is the
              endpoint's (`BR-SHL-025`, `DEF-CUS-6374`). Drawn only for the
              three tenders that pass through hands, with the door to start a
              till beside it.

              ⚠ **`announceBatch={false}` AND IT IS NOT COSMETIC.** With a till
              open, Record a payment says *"Goes into your counter batch …"* —
              true there, and FALSE here: under A2 a request fee is a
              `counter_receipts` row and joins no deposit batch until an
              account exists. **That half is unchanged and is still why this
              prop is `false`.**

              ⚠ **THE OTHER HALF IS FIXED — a fee now joins its counter's
              DRAWER COUNT (`OQ-PAY-12621`, PO 2026-09-24: *"p1 a"*).** This
              comment used to end *"`DEF-PAY-6375` carries that gap to the
              PO"*, over a clerk whose honest count came out over by the fee —
              and since 2026-09-23 an over POSTS, so the one fee was booked
              twice. A drawer and a deposit batch are different containers:
              `counter_receipts.counter_session_id` puts the cash in the
              first, and nothing puts it in the second. */}
          <RecordCounterBanner
            client={client}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            methodCode={method === "" ? null : method}
            announceBatch={false}
          />

          {/* ── HOW MUCH ─────────────────────────────────────────────────── */}
          <TextField
            id="amount"
            label={t("payments.form.amount")}
            required
            numeric
            value={amount}
            onChange={setAmount}
            help={t("payments.form.amountBrief")}
          />
          {/* ── WHAT IT IS FOR — fixed, so shown and not asked ─────────────── */}
          <TextField
            id="purpose"
            label={t("customers.serviceRequest.collect.purpose")}
            value={t("customers.serviceRequest.collect.purposeApplicationFee")}
            onChange={() => undefined}
            readOnly
          />
          {/* ── WHEN — BR-PAY-033: proposed as today, always overridable ─── */}
          <DatePickerField
            id="posted_at"
            label={t("payments.form.postedAt")}
            value={postedAt}
            onChange={setPostedAt}
            prefill={today}
            dateFormat={props.dateFormat}
            required
            help={t("payments.form.postedAtBrief")}
          />
          {/* ── HOW — the tenant's own list, and its reference ─────────────── */}
          <SelectField
            id="method"
            label={t("payments.form.method")}
            required
            value={method}
            onChange={(next) => {
              setMethod(next);
              // Switching to cash CLEARS the reference rather than hiding a
              // value that would still be sent.
              if (next === CASH_CODE) {
                setConfirmation("");
              }
            }}
            options={methodOptions(lookups.data?.methods ?? [])}
            placeholder={t("payments.form.methodPlaceholder")}
          />
          {needsReference && (
            <TextField
              id="confirmation"
              label={t("payments.form.confirmation")}
              value={confirmation}
              onChange={setConfirmation}
            />
          )}
          <TextField
            id="receipt_no"
            label={t("customers.serviceRequest.collect.receipt")}
            required
            value={receipt}
            onChange={setReceipt}
            help={t("customers.serviceRequest.collect.receiptBrief")}
          />
          <TextField id="memo" label={t("payments.form.memo")} value={memo} onChange={setMemo} />
          {/* ⚠ **`BR-CUS-090` IS NOT WEAKENED.** A short payment is still an
              OPEN BALANCE and still NOT a write-off. Two sentences of five
              words — an instruction and a fact, both inside rule 33's six. */}
          <p className="max-w-prose text-sm text-neutral-700">
            {t("customers.serviceRequest.collect.shortfallIsFine")}
          </p>
        </>
      )}
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6376 · DEF-CUS-6374 · decision log 2026-09-19 (A2) · PO
//   2026-09-23 §3.4 · B14 rules 21, 31, 33, 38, 43
// generated: 2026-09-23 by LANE REQ-FEE
// checklist: A✔ B✔(POST .../fee-collection takes posted_at, memo, confirmation;
//   refuses a hand tender with no till) C✔ D✔ E✔(mounted by
//   ServiceRequestDetailPage in place of its inline modal) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest RequestFeeHandoverModal.dom ·
//   ServiceRequestDetailPage.dom · ServiceRequestDetailPage · counterDoors.dom
//   · G31 (listed in route-b-migrated.txt) · routeBUtilities.test.ts
// exceptions: E3 the field set is SHARED (kit fields, catalogue keys, served
//   list) rather than extracted from `RecordPaymentForm` — extracting a
//   `RecordPaymentFields` both hosts mount would restructure the payments
//   module's main form and is left for that module's owner
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
