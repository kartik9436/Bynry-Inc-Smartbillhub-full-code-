// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.11` — screen **2·3d Cancel** of
//           `05-prototype/06 Payments Page Blueprint.pdf`, **p043–p044 read AS
//           IMAGES at scale 2.0** (B14 rule 42).
// Screens:  2·3d Cancel (`S35` · `PAY-P`) — NEW, the only genuinely missing
//           logic in the module.
// Rules:    B14 rule 6 (danger tier on a destructive commit — the drawn
//           *Primary action* row says **"Cancel payment, danger tier"**) ·
//           rule 10 (required fields carry the asterisk) · rule 11 (a
//           consequence preview before a commit that writes money) · rule 33
//           (a CONSEQUENCE is ≤ 6 words per sentence, at most two) · rule 43
//           (a component, not 120 lines inside a page) · BR-PAY-021 (cancel
//           and reverse are two acts) · BR-SHL-025 (a refused control says why)
// ───────────────────────────────────────────────────────
// *"I just took that from the wrong person. Undo it."*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ CANCEL IS NOT REVERSE, AND THE WHOLE SCREEN EXISTS TO KEEP THEM APART
// ══════════════════════════════════════════════════════════════════════════
// p044, verbatim: *"Cancel and Reverse are the same word to a clerk and two
// different acts to the ledger. **Cancel** is for money that never cleared —
// the mistake is minutes old, in an open batch, and nothing has reached the
// bank. **Reverse** is for money that arrived and went back: a bounce, a
// chargeback. Hard rule 4 means neither deletes anything; both write new rows."*
//
// And the drawing's ruling on what a clerk should SEE: *"So the clerk should
// see one control and the product should choose. Drawn that way on 2·2: one
// Cancel in the danger tier, behaving by status, with the history panel making
// whichever happened legible afterwards."*
//
// ⚠ **THE PRODUCT CHOOSES ON THE SERVER, NOT HERE.** `actions.cancel.reason` is
// `cancel.refusal_for`'s own code — the SAME pure function the write path calls
// — so the reason a clerk reads before the click and the reason the service
// gives after it can never be two different answers (BR-SHL-025). **A screen
// that worked the status rules out for itself would be a second copy of them,
// free to drift**, which is this repository's most expensive recurring shape.
// So this file contains no status arithmetic at all.
//
// ⚠ **AND THE REFUSAL ON A CLEARED PAYMENT MUST NAME REVERSE.** That is
// `BR-PAY-021` and it is the one refusal with a next step — the clerk is not
// stuck, they are on the wrong door. `payments.cancel.refused.cleared` says so
// in all eleven catalogues, and `P3.13` is the test that holds it.
//
// ⚠ **`OQ-PAY-12603` IS OPEN AND NOTHING HERE IS STUBBED.** Cancel is
// `processing`-only, and a counter CASH payment is `cleared` the same minute —
// so *"I just took that from the wrong person"* at a window reaches Reverse
// rather than Cancel. That is a collision between two frames of one drawing and
// it is the PO's to settle; this screen renders whatever the server allows and
// says why when it does not.
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { cancelPayment } from "@/api/paymentDetailEndpoints";
import type { CancelReason, CancelledPayment, PaymentDetail } from "@/api/paymentDetailEndpoints";
import { CANCEL_REASONS } from "@/api/paymentDetailEndpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { todayInZone } from "@/components/DateCell";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import { formatMoney } from "@/components/MoneyCell";

import { appliedBills } from "./paymentsShared";

/** The drawn *Why* list, in the drawn order. Four, and they are the SERVER's
 *  `CANCEL_REASONS` — a fifth typed here would be refused by name. */
const REASON_KEYS: Record<CancelReason, string> = {
  wrong_account: "payments.cancel.reason.wrongAccount",
  wrong_amount: "payments.cancel.reason.wrongAmount",
  duplicate: "payments.cancel.reason.duplicate",
  not_taken: "payments.cancel.reason.notTaken",
};

export function cancelPaymentSchema(t: (key: string) => string) {
  return z.object({
    // ② *Why* · required · B14 rule 10. The server refuses without one; this
    // says so before the round trip rather than instead of it.
    reason: z.enum(CANCEL_REASONS, { message: t("payments.cancel.reasonRequired") }),
    note: z.string().optional(),
  });
}

export interface CancelPaymentModalProps {
  client: ApiClient;
  detail: PaymentDetail;
  timeZone: string;
  /** The money locale — the same one every other payments surface formats
   *  with, so one figure cannot read two ways on one screen. */
  locale: string;
  onClose: () => void;
  onCancelled: (result: CancelledPayment) => void;
}

/**
 * 2·3d, as drawn: a banner that says WHY this is cancellable, a required
 * reason, a free-text note, and what it will do in the customer's terms.
 */
export function CancelPaymentModal(props: CancelPaymentModalProps) {
  const { t } = useTranslation();
  const { detail } = props;
  const [reason, setReason] = useState<string>("");
  const [note, setNote] = useState("");

  const bills = appliedBills(detail);
  // p044 ③ — *"What it will do · in the customer's terms, not the ledger's"*.
  // ONE bill is named when there is exactly one; several are counted, because a
  // list of bill numbers in a consequence box is not a sentence a clerk reads.
  const singleBill = bills.length === 1 ? bills[0] : null;

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await cancelPayment(props.client, detail.payment_no ?? detail.id, {
        reason: reason as CancelReason,
        note: note.trim() === "" ? undefined : note.trim(),
        // The day the cancel counts from is the tenant's day, never the
        // browser's UTC one — `isoToday()` stamps a 17:05 shift into tomorrow
        // (the module's own `Settings is in payments` finding).
        cancelled_on: todayInZone(props.timeZone),
      });
      props.onCancelled(result);
      return { ok: true };
    } catch (error) {
      // BR-SHL-020: the server's refusal is SHOWN. A cancel that failed
      // silently leaves a clerk believing the money came back.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      // The drawn kicker is the payment, its amount and when it was taken —
      // three facts a clerk checks before an irreversible act, and B14 rule 31
      // keeps them to the NUMBER rather than the uuid.
      kicker={t("payments.cancel.kicker", {
        number: detail.payment_no ?? t("payments.row.noNumber"),
      })}
      title={t("payments.cancel.title")}
      schema={cancelPaymentSchema((key) => t(key))}
      values={{ reason, note }}
      submitLabel={t("payments.cancel.submit")}
      /* ⚠ **B14 rule 6, AND THE DRAWING SAYS IT IN WORDS.** p044's *Primary
         action* row: **"Cancel payment, danger tier."** This is the act that
         takes money back off a customer's account, and `P3.12` moved the
         reversal commit here an hour earlier for the same reason: the warning
         belongs on the ACT and not only on the door. */
      submitVariant="danger"
      /* ⚠ **THE DRAWING WRITES *Keep it*, AND IT IS NOT A FLOURISH.** With the
         kit's default this footer reads **Cancel · Cancel payment** — two
         buttons whose first word is the same, meaning opposite things, on the
         one form in this module that takes money back off a customer. p044
         draws **Keep it**, and `FormModal.cancelLabel` was added for exactly
         this: optional, so no other form in the product moves. */
      cancelLabel={t("payments.cancel.keepIt")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ① **WHY THIS IS CANCELLABLE — state and age, SAID FIRST**, because
          *"the control behaves differently by status"* (p044 ①). It is a FACT
          at B14 rule 33's six-word cap, not an explanation of the rule: a
          clerk acts on *nothing has cleared*, and cannot act on a paragraph
          about `ck_payments_status`. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.cancel.stateTag")}
        data-consequence="cancel-state"
        title={t("payments.cancel.stateTitle")}
        body={t("payments.cancel.stateBody")}
      />

      {/* ② **Why · required · B14 rule 10.** The asterisk is the kit's. */}
      <SelectField
        id="cancel-reason"
        label={t("payments.cancel.reason")}
        value={reason}
        onChange={setReason}
        required
        placeholder={t("payments.cancel.reasonPlaceholder")}
        options={CANCEL_REASONS.map((code) => ({
          value: code,
          label: t(REASON_KEYS[code]),
        }))}
        /* ⚠ **THE DRAWN HELPER IS *"This is the only record of the reason."* —
           EIGHT WORDS, AND A FACT'S CAP IS SIX (B14 rule 33).** B14 rule 38
           gives the UI rules the how of a form and leaves the drawing what it
           CONTAINS, so the meaning is kept and the sentence is cut to the cap.
           ⚠ **AND IT IS NOT A RETENTION CLAIM.** The reason is written to
           `audit_log` on both rows and `OQ-PAY-12604` asks whether it deserves
           a column of its own; **this sentence must never grow into an
           explanation of how long it survives** — rule 33 puts rationale at
           ZERO words on screen, and `P3.18` deleted exactly that from the
           Correction path on 2026-09-23. */
        help={t("payments.cancel.reasonHelp")}
      />

      {/* The drawn *Note* — *"What happened, in your words."* Optional: the
          vocabulary above is what the register needs, and a required essay is
          what makes a clerk pick whichever reason clears the form fastest. */}
      <TextField
        id="cancel-note"
        label={t("payments.cancel.note")}
        value={note}
        onChange={setNote}
        multiline
        help={t("payments.cancel.noteHelp")}
      />

      {/* ③ **WHAT IT WILL DO, IN THE CUSTOMER'S TERMS — B14 rule 11.**
          Two sentences, six words each at most (rule 33's consequence cap),
          and **never cut below clarity**: the money leaving the account and the
          bill re-opening are two different facts and a clerk needs both.

          ⚠ **DRAWN ALWAYS, NOT GATED ON A CHOSEN REASON.** It is a statement
          about the ACT, not about the current form state — gating it would hide
          it in the state the modal OPENS in, which is the only state a
          hesitating clerk is ever looking at. (`P0.12` learned that one screen
          over and this is the same mistake, pre-empted.) */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.consequence.tag")}
        data-consequence="cancel"
        /* ⚠ **`formatMoney`, NOT `<Money>`, AND THE TYPE IS WHY.**
           `ConsequenceBox.title` is a `string` — deliberately, so a heading
           cannot grow a paragraph — so the figure is formatted rather than
           rendered. It is the SAME formatter `<Money>` composes, so the
           sentence and the facts above it can never round differently (hard
           rule 2: display 2, whatever it is stored to). */
        title={t("payments.cancel.consequence.title", {
          amount: formatMoney(detail.amount, detail.currency, props.locale),
          customer: detail.customer_name ?? t("payments.row.noCustomer"),
        })}
        body={
          singleBill !== null && singleBill.invoiceNumber !== null
            ? t("payments.cancel.consequence.oneBill", { bill: singleBill.invoiceNumber })
            : bills.length > 1
              ? t("payments.cancel.consequence.manyBills", { count: bills.length })
              : // A payment that met no bill is a REAL outcome — a carried
                // credit — and p036 already ruled that it is said in words
                // rather than left as a blank.
                t("payments.cancel.consequence.noBill")
        }
      />
    </FormModal>
  );
}
