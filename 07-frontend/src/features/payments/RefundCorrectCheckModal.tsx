// ── Trace ──────────────────────────────────────────────
// Change:   CR-141-BRC07 — a refund's check number may be corrected, the same
//           way a payment's can (OQ-PAY-12614, CLOSED 2026-09-23, option b).
// Story:    US-PAY-011 (refunds) · Screens: S58
// Rules:    B14 rule 15 (the row action is an ICON — `RefundRowActions`) ·
//           rule 11 (a consequence before the commit) · rule 33 (rationale is
//           ZERO words on screen) · rule 38 (the kit builds the form) · rule 43
//           (a piece of UI is a COMPONENT) · BR-SHL-025 (a control that cannot
//           act is drawn DISABLED WITH ITS REASON, never hidden) · BR-PAY-1071
//           (who issues a refund, and so who corrects its number)
// Ruling:   PO, verbatim, 2026-09-23: *"One thing needs your sign-off, because
//           it is a money record: (b) Allow a correction, the same way you
//           allowed it for payments on 2 September"*. SHOWN: *Dana sends a
//           refund of $91.60 by check #10241 but types #10214; as built it can
//           never be changed.*
// Server:   POST /refunds/{id}/correct-reference · apps/payments/refunds.py
//           `correct_refund_reference` · apps/payments/migrations/0043
// ───────────────────────────────────────────────────────
//
// CORRECT CHECK NUMBER — one field that matters, one reason, one box.
//
// ⚠ **ITS OWN COMPONENT, AND NOT `CorrectReferenceModal` REUSED — THE RULE 43
// QUESTION WAS ASKED FIRST, AND THIS IS ITS ANSWER.** The payment door's form
// (`PaymentsPage.CorrectReferenceModal`, exported and already mounted from two
// hosts) offers the reference, the MEMO and the TENDER. For a refund only the
// check number was put to the PO, so mounting that form here would OFFER two
// fields the server refuses by name — a form that invites a refusal. Rule 43's
// own escape hatch is the reading: *"where two hosts legitimately draw the same
// block differently, share the FIELD SET and let each host own its
// construction, never fork the block."* The field set IS shared — the same
// note field under the same catalogue key, the same Save label, the same
// consequence-box component — and the block that differs is this one.
//
// ⚠ **NOTHING ON THIS SCREEN SAYS HOW LONG THE OLD NUMBER IS KEPT, AND THE
// SILENCE IS THE BUILD.** The replaced number lives only in the audit trail,
// which is pruned on its one schedule (`OQ-1340`, CLOSED 2026-09-23: *"when
// audit log is delete - it is deleted thats okay"*). B14 rule 33 puts
// RATIONALE at ZERO WORDS on screen, so a sentence explaining retention would
// break rule 33 while trying to obey the ruling — which is exactly why the
// payment door's `CorrectionRetentionNote` was DELETED (`P3.18`). This form
// simply never claims permanence. The server's `unavailable[]` entry says it
// for a machine, and nothing here renders it.
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { correctRefundReference } from "@/api/endpoints";
import type { CorrectedRefundReference, RefundRow } from "@/api/endpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome, Translator } from "@/components/FormModal";
import { ROLE_BILLING_CLERK, ROLE_SYSTEM_ADMIN } from "@/features/metering/meteringShared";

/**
 * Why *Correct check number* cannot run on this row, or `null`.
 *
 * PURE, and **every branch mirrors a refusal the SERVICE already makes**
 * (`refunds.correct_refund_reference`) rather than inventing one — BR-SHL-025's
 * whole content:
 *
 *   · the ROLE first — Admin or Billing Clerk, `BR-PAY-1071` as amended: who
 *     writes the check corrects its number. A null role (the permissions read
 *     has not answered) OFFERS the control; the service's own `@require_role`
 *     is the boundary either way.
 *   · a CANCELLED refund is closed — `payments/0006`'s VOID guard, untouched.
 *   · a refund with NO NUMBER has nothing to correct — the first number is the
 *     ISSUE act's, which is where the money moves.
 *
 * ⚠ **NO STATUS GATE AT `issued`, DELIBERATELY.** A CLEARED refund is where a
 * typo is usually FOUND — the bank line reads #10241 and the row says #10214 —
 * so the service corrects either, and this does too.
 */
export function refundCorrectBlockedReason(
  row: RefundRow,
  role: string | null,
  t: Translator,
): string | null {
  const mayCorrect = role === null || role === ROLE_SYSTEM_ADMIN || role === ROLE_BILLING_CLERK;
  if (!mayCorrect) {
    return t("payments.refunds.adminOrClerkOnly");
  }
  if (row.status === "void") {
    return t("payments.refunds.correct.closed");
  }
  if ((row.reference ?? "").trim() === "") {
    return t("payments.refunds.correct.noNumber");
  }
  return null;
}

/**
 * Client validation is UX only — the server refuses every one of these again.
 *
 * The number is required and must DIFFER from the one on the row: the service
 * refuses a correction to the same number (*"an audit row saying a number was
 * corrected to itself is noise in the one place the old number lives"*), and
 * saying so before the round trip names the field to touch. The note mirrors
 * the payment door's rule under the payment door's own key.
 */
export function refundCorrectSchema(t: Translator, current: string) {
  return z.object({
    reference: z
      .string()
      .refine((value) => value.trim() !== "", {
        message: t("payments.refunds.correct.numberRequired"),
      })
      .refine((value) => value.trim() === "" || value.trim() !== current.trim(), {
        message: t("payments.refunds.correct.sameNumber"),
      }),
    note: z.string().refine((value) => value.trim() !== "", {
      message: t("payments.correct.noteRequired"),
    }),
  });
}

/**
 * S58's *Correct check number* — the new number and why, nothing else.
 *
 * The field OPENS on the number the row holds, so a clerk fixing two
 * transposed digits edits them in place rather than retyping the whole
 * number — the payment door's choice, for the same reason.
 */
export function RefundCorrectCheckModal(props: {
  client: ApiClient;
  refund: RefundRow;
  onClose: () => void;
  onCorrected: (result: CorrectedRefundReference) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const current = props.refund.reference ?? "";
  const [reference, setReference] = useState(current);
  const [note, setNote] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await correctRefundReference(
        props.refund.id,
        { reference: reference.trim(), note },
        props.client,
      );
      props.onCorrected(result);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("payments.refunds.action.correct")}
      kicker={t("payments.refunds.correct.kicker", { number: current })}
      schema={refundCorrectSchema(translate, current)}
      values={{ reference, note }}
      submitLabel={t("payments.correct.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <TextField
        id="reference"
        label={t("payments.refunds.correct.number")}
        value={reference}
        onChange={setReference}
        required
      />
      {/* The payment door's own field and key: one vocabulary for one act. */}
      <TextField
        id="note"
        label={t("payments.correct.note")}
        value={note}
        onChange={setNote}
        required
      />
      {/* B14 rule 11 — what the commit does NOT touch is what a clerk needs
          before Save: **no money moves.** A correction that reads as though it
          might is one a clerk avoids, and they cancel the refund instead —
          which reverses a posting and raises a second refund for a typo.
          Drawn ALWAYS, not gated on a change, for the payment form's reason:
          it is a fact about this FORM, which cannot move money whatever is
          typed into it, because `payments/0043` opens one column. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.consequence.tag")}
        data-consequence="correct-check"
        title={t("payments.refunds.correct.consequence.title")}
        body={t("payments.refunds.correct.consequence.body")}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: OQ-PAY-12614 (CLOSED 2026-09-23, option b) · apps/payments/refunds.py
//         `correct_refund_reference` · apps/payments/refunds_api.py ·
//         PaymentsPage.CorrectReferenceModal (the payment precedent, and why it
//         is not mounted here — see the header)
// generated: 2026-09-23 by lane REFUND-CORRECT
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
