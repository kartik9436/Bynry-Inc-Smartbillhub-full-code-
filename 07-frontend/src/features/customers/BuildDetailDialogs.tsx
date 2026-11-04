// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · the New Connect BUILD DETAIL page — task 14, the
//           two dialogs: `Resend` and `Take payment`.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/08-resend.png` and
//           `09-take-payment.png`, opened with the Read tool and LOOKED AT
//           before a line of this file (B14 rule 42).
// Rules:    B14 rule 38/44 (what a form CONTAINS is the drawing's; HOW it is
//           built is our UI standard's, and the standard wins) · rule 11 (a
//           form writing money shows what it will do before its commit) ·
//           rule 33 (a CONSEQUENCE is ≤ 6 words per sentence, at most two) ·
//           rule 34 (one pair of words for *in the books*) · rule 43 (a piece
//           of UI is a COMPONENT) · BR-PAY-026 (the tenant's OWN method list,
//           never a literal array) · BR-PAY-033 / BR-TEN-081 (the posting date
//           is PROPOSED as the tenant's today and never read from a clock on
//           submit) · BR-BIL-024 (payment terms keep NO default anywhere —
//           which is why this form has no terms field at all) · CLAUDE.md
//           hard rule 2 (money is a decimal STRING end to end; never a float,
//           never a client-side rounding) · hard rule 4 (a posted payment is
//           not editable — corrections are new rows).
// Tests:    src/features/customers/BuildDetailDialogs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// BOTH DIALOGS ARE BUILT AGAINST A REAL DOOR, AND WHERE ONE IS MISSING THE
// SUBMIT IS REFUSED BY NAME RATHER THAN FAKED
// ══════════════════════════════════════════════════════════════════════════
//   * **Take payment** posts `POST /accounts/{id}/payments` — `recordPayment`,
//     which has existed since the payments module landed. It needs the OWNER
//     ACCOUNT's id, which neither read on this page serves; the page derives
//     it and hands it down, and a `null` refuses the commit BY NAME instead of
//     posting somebody's money at a guess.
//   * **Resend** posts `POST /outbound/{id}/resend` — `resendOutbound`, the
//     one resend door in this product, which takes the outbound message's id
//     AND its copy number and *"will not allocate one"*. A build's
//     communication rows carry neither today, because no message has ever been
//     filed for a connection (`OQ-NOT-12521`, OPEN) — so the row's control is
//     already refused from the payload, and this dialog refuses the same way
//     if it is ever reached without them.
//
// ⚠ **THAT IS NOT A HOLD WITH NO TEST BEHIND IT.** `BuildDetailDialogs.dom.
// test.tsx` asserts both directions on each dialog — refused with its named
// reason when the door's arguments are absent, and POSTING to the real address
// when they are there. The day the wire carries an outbound id the control
// opens by itself and the test says so.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError, UNEXPECTED_ERROR_KEY } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPayments, recordPayment } from "@/api/endpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoneyInput } from "@/components/MoneyCell";
import { methodOptions } from "@/features/payments/paymentsShared";
import {
  PossibleDuplicateNotice,
  possibleDuplicateOf,
  useDuplicateWarning,
} from "@/features/payments/PossibleDuplicate";

import type { Translator } from "./newConnectShared";

/** A `<dl>` of read-only facts at the head of a dialog — the drawn two-column
 *  meta block on both PNGs. Facts, so ≤ 6 words each (B14 rule 33). */
function DialogFacts(props: { id: string; rows: { label: string; value: React.ReactNode }[] }) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2" data-dialog-facts={props.id}>
      {props.rows.map((row) => (
        <div key={row.label} className="border-l-2 border-l-divider pl-3">
          <dt className="font-heading text-xs font-semibold uppercase tracking-label text-neutral-700">
            {row.label}
          </dt>
          <dd className="m-0">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// RESEND — RETIRED 2026-10-02 (`CR-163-BRC10` item 26)
// ══════════════════════════════════════════════════════════════════════════
// `BuildResendDialog` lived here and refused BY NAME on every row, because the
// record carried no outbound id and no copy number — nothing had ever been
// filed for a connection. The Messages tab now owns *Send now* / *Resend*
// (`features/work/buildRecord/BuildMessagesTab.tsx`, `BuildSendMessageDialog`)
// over the ruled `connection` kind, and the next copy is numbered by the
// SERVER. Deleted rather than left mounted nowhere: a component nothing
// renders is hard-won law 2's dead UI.

// ══════════════════════════════════════════════════════════════════════════
// TAKE PAYMENT — recorded against the ACCOUNT, which is where money lives
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE REFERENCE BOX FOLLOWS THE TYPE AND CASH ASKS FOR NONE.** A cheque
// has its number, a card its authorisation, a transfer its reference; cash has
// nothing to write. Switching TO cash CLEARS the box rather than hiding a
// value that would still be posted — which is how a cash receipt acquires a
// cheque number nobody typed.
//
// ⚠ **THERE IS NO TERMS FIELD, AND THAT IS `BR-BIL-024`.** Payment terms keep
// NO default anywhere; a dialog that proposed one would be a default in the
// one place the rule says there may not be one. The drawn `TERMS 30 days` on
// the Charges tab is the INVOICE's own stated term, not this form's.

/** The one tender that carries no reference — the tenant's own
 *  `payment_methods.code`, the same vocabulary the list is served in. */
const CASH_CODE = "cash";

const TAKE_PAYMENT_SCHEMA = z.object({
  // A STRING END TO END (hard rule 2). `.regex` rather than `z.coerce.number()`:
  // coercing here puts an IEEE double on the wire, which the server's
  // `_money_field` refuses by name rather than accepting.
  amount: z
    .string()
    .trim()
    .regex(/^-?\d+(\.\d{1,4})?$/),
  method: z.string().trim().min(1),
  posted_at: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
});

/** metering's `connections.PAYMENT_KEY_PREFIX` — the build's own namespace on
 *  a payment key (`DEF-MET-9224`). Spelled once on each side of the wire; the
 *  payments read (`payments_for_bills`) matches it by prefix. */
export const NEW_CONNECT_PAYMENT_KEY_PREFIX = "new-connect:";

export interface BuildTakePaymentDialogProps {
  t: Translator;
  /** The owner account the money is recorded against. `null` refuses by name. */
  accountId: string | null;
  /** The account NUMBER a clerk reads, and the owner's name beside it. */
  accountNo: string | null;
  ownerName: string | null;
  /** The bill this build raised — its NUMBER. `money` carries no invoice id. */
  invoiceNo: string | null;
  /** What is still owed, as the SERVER states it: `{stored, display}`. */
  outstanding: { stored: string | null; display: string | null } | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  /** ⊕ `DEF-MET-9224` — the build this money is taken for. It rides on the
   *  payment's idempotency key (`new-connect:<id>:take:<token>`), which is how
   *  the request's *Paid so far* finds a cheque that has not cleared and so
   *  meets no bill yet. Absent keeps the bare token. */
  connectionId?: string;
  onClose: () => void;
  onDone?: () => void;
}

export function BuildTakePaymentDialog(props: BuildTakePaymentDialogProps) {
  const { t } = props;
  const client = props.client ?? api;
  // BR-PAY-033 / BR-TEN-081 — PROPOSED as the tenant's today, held from the
  // moment the form opens and never read off a clock at submit.
  const today = todayInZone(props.timeZone);
  // ⚠ **FILLED WITH WHAT IS OUTSTANDING AND EDITABLE**, which is the drawing's
  // own instruction. `formatMoneyInput` is the kit's wire-safe spelling — two
  // decimals, no grouping, pinned to the wire's locale so `de-DE` cannot turn
  // `2410.00` into `2410,00` and have the serializer refuse it.
  const [amount, setAmount] = useState(() => formatMoneyInput(props.outstanding?.stored));
  const [method, setMethod] = useState("");
  const [postedAt, setPostedAt] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [memo, setMemo] = useState("");
  const needsReference = method !== "" && method !== CASH_CODE;
  // ⚠ **MINTED ONCE PER OPENED FORM, AND THE SERVER REFUSES WITHOUT IT**
  // (hard rule 6). A key the SERVER generated would differ on the second
  // submit and would dedupe nothing while looking as though it had — so a
  // double click on a counter posts one payment, not two. Same spelling as
  // `RecordPaymentPage`'s own `submitToken`.
  const [submitToken] = useState(() =>
    props.connectionId === undefined
      ? crypto.randomUUID()
      : `${NEW_CONNECT_PAYMENT_KEY_PREFIX}${props.connectionId}:take:${crypto.randomUUID()}`,
  );

  // ⚠ **THE SAME READ, UNDER THE SAME KEY, AS `RecordPaymentPage`** — one row
  // of `GET /payments` for its `methods[]`, so the two forms share one cache
  // entry and cannot offer different lists of the same thing (BR-PAY-026).
  const duplicate = useDuplicateWarning();
  const lookups = useQuery({
    queryKey: ["payments", "record-new-lookups"],
    queryFn: () => getPayments({ per: 1 }, client),
    retry: false,
  });

  async function submit(): Promise<FormSubmitOutcome> {
    if (props.accountId === null) {
      return {
        ok: false,
        error: {
          code: "UNAVAILABLE",
          message_key: "customers.build.takePayment.noAccount",
        },
      };
    }
    // DEF-PAY-9263 — read once: true only when *Record anyway* was pressed.
    const confirmDuplicate = duplicate.takeConfirm();
    duplicate.clear();
    try {
      await recordPayment(
        props.accountId,
        {
          ...(confirmDuplicate ? { confirm_duplicate: true } : {}),
          amount: amount.trim(),
          posted_at: postedAt === "" ? today : postedAt,
          method,
          // Sent only where it is drawn — a hidden field that keeps posting is
          // how a cash receipt acquires a cheque number nobody typed.
          confirmation: needsReference && confirmation.trim() !== "" ? confirmation.trim() : null,
          memo: memo.trim() === "" ? null : memo.trim(),
          idempotency_key: submitToken,
        },
        client,
      );
      props.onDone?.();
      props.onClose();
      return { ok: true };
    } catch (error) {
      // DEF-PAY-9263 — "Looks like a duplicate": nothing was saved. The panel
      // below names the earlier payment; the form stays open with no error.
      const earlier = possibleDuplicateOf(error);
      if (earlier !== null) {
        duplicate.warn(earlier);
        return { ok: true };
      }
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "UNEXPECTED", message_key: UNEXPECTED_ERROR_KEY } };
    }
  }

  return (
    <FormModal
      title={t("customers.build.takePayment.title", { defaultValue: "Take payment" })}
      schema={TAKE_PAYMENT_SCHEMA}
      values={{ amount, method, posted_at: postedAt === "" ? today : postedAt }}
      submitLabel={t("customers.build.takePayment.title", { defaultValue: "Take payment" })}
      onClose={props.onClose}
      onSubmit={submit}
    >
      <DialogFacts
        id="take-payment"
        rows={[
          {
            label: t("customers.build.takePayment.against", { defaultValue: "Against" }),
            value: props.invoiceNo,
          },
          {
            label: t("customers.build.made.account", { defaultValue: "Account" }),
            value:
              props.accountNo === null
                ? null
                : props.ownerName === null
                  ? props.accountNo
                  : `${props.accountNo} · ${props.ownerName}`,
          },
          {
            label: t("customers.build.fact.outstanding", { defaultValue: "Outstanding" }),
            value: <span className="tabular-nums">{props.outstanding?.display}</span>,
          },
        ]}
      />
      {/* ── HOW MUCH ─────────────────────────────────────────────────────── */}
      <TextField
        id="amount"
        label={t("payments.form.amount")}
        required
        numeric
        value={amount}
        onChange={setAmount}
        help={t("payments.form.amountBrief")}
      />
      {/* ── HOW — the tenant's own list, and the reference that follows it ── */}
      <SelectField
        id="method"
        label={t("payments.form.method")}
        required
        value={method}
        onChange={(next) => {
          setMethod(next);
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
      {/* ── WHEN — proposed as today, always overridable ─────────────────── */}
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
      <TextField id="memo" label={t("payments.form.memo")} value={memo} onChange={setMemo} />
      {duplicate.earlier !== null && (
        <PossibleDuplicateNotice
          earlier={duplicate.earlier}
          onGoBack={duplicate.clear}
          onRecordAnyway={duplicate.confirmNext}
          submits
        />
      )}
      {/* B14 rule 34 — ONE pair of words for *in the books*. Rule 33's
          consequence cap: two sentences, three and five words. */}
      <ConsequenceBox
        tone="publish"
        title={t("customers.build.takePayment.consequenceTitle", {
          defaultValue: "In the books",
        })}
        body={t("customers.build.takePayment.consequence", {
          defaultValue: "It cannot be edited after.",
        })}
        data-consequence="build-take-payment"
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 task 14 · `08-resend.png` · `09-take-payment.png`, read
//   as IMAGES (B14 rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//   H=deferred(PO)
// exceptions:
//   (1) **THE DRAWN `DUE` FACT IS NOT ON THE TAKE-PAYMENT DIALOG.** The build
//       record's `money` block carries no due date for the quote bill, so the
//       fact is omitted rather than dashed for ever. REPORTED.
//   (2) **THE DRAWN HELP SENTENCE UNDER THE REFERENCE BOX IS NOT BUILT** —
//       *"The reference box follows the type: cheque number, card reference,
//       or transfer reference. Cash asks for none."* is RATIONALE, and B14
//       rule 33 puts rationale at ZERO WORDS ON SCREEN, removed rather than
//       shortened. The behaviour it describes IS built.
//   (3) **`Resend` COMMITS THROUGH `POST /outbound/{id}/resend` AND NEEDS TWO
//       VALUES THE BUILD RECORD DOES NOT CARRY** — the outbound row's id and
//       its copy number. Refused BY NAME rather than faked; the row's own
//       control is already refused from the payload for the same reason.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
