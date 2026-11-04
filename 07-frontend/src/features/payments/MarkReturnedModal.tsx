// ── Trace ──────────────────────────────────────────────
// Change:   CR-175-BRC10 — a billing clerk marks an ACH payment returned, on
//           any day, with a reason and the bank code (PO 2026-10-07, option (a)).
// Rules:    BR-PAY-1070 (as amended 2026-10-07 for this one case) · BR-PAY-013 ·
//           BR-PAY-021 (the BANK's date, never a clock) · hard rules 2, 6 ·
//           B14 rules 6 (danger tier on the commit), 11 (consequence box),
//           33 (text caps), 35 (eleven catalogues), 43 (a component)
// Tests:    07-frontend/src/features/payments/markReturned.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **Mark returned** — the bank sent an ACH payment back and a clerk records it.
 *
 * PO, verbatim: *"(a) Let billing clerks mark an ACH payment returned, any day,
 * with a reason and the bank code. The same effect follows: balance restored,
 * fee and notice."* So the dialog asks for exactly three things — WHY, the
 * BANK'S CODE and the BANK'S DATE — and nothing the general Reverse carries
 * (a partial amount, bills to target, our bank's fee, the ladder switch): those
 * stay on the System Admin's Reverse, and offering them here would promise a
 * clerk a reach the service does not give.
 *
 * ⚠ **A COMPONENT IN ITS OWN FILE, NOT A BRANCH OF `ReversePaymentModal`**
 * (B14 rule 43). That modal is the Admin's general Reverse with four reasons,
 * windows and approvals; folding a clerk mode into it would put two rules in
 * one form and make every future change to either a change to both.
 *
 * The reason defaults to *Returned by the bank*, as on the existing Reverse —
 * the one a bank return almost always is, and the one that needs no approval.
 */
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ReversedPayment } from "@/api/endpoints";
import { ACH_RETURN_REASONS, NACHA_RETURN_CODE, markReturned } from "@/api/paymentDetailEndpoints";
import type { AchReturnReason, PaymentDetail } from "@/api/paymentDetailEndpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";

export function markReturnedSchema(t: (key: string) => string) {
  return z.object({
    returned_on: z.string().min(1, { message: t("payments.reverse.returnedOnRequired") }),
    return_code: z
      .string()
      .trim()
      .min(1, { message: t("payments.markReturned.codeRequired") })
      .refine((value) => NACHA_RETURN_CODE.test(value.toUpperCase()), {
        message: t("payments.markReturned.codeInvalid"),
      }),
  });
}

export interface MarkReturnedModalProps {
  client: ApiClient;
  detail: PaymentDetail;
  dateFormat: RegionalDateFormat;
  locale: string;
  onClose: () => void;
  onReturned: (result: ReversedPayment) => void;
}

export function MarkReturnedModal(props: MarkReturnedModalProps) {
  const { t } = useTranslation();
  const { detail } = props;
  const [reason, setReason] = useState<AchReturnReason>("nsf");
  const [returnCode, setReturnCode] = useState("");
  // BR-PAY-021 — the BANK's date. Not pre-filled: a return arrives on a
  // statement days later, and a pre-filled today would be accepted unread.
  const [returnedOn, setReturnedOn] = useState("");
  const [memo, setMemo] = useState("");
  // Hard rule 6 — ONE token per opened dialog, so a double click returns once.
  const [submitToken] = useState(() => crypto.randomUUID());

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await markReturned(props.client, detail.id, {
        returned_on: returnedOn,
        reason,
        return_code: returnCode.trim().toUpperCase(),
        memo: memo.trim() === "" ? undefined : memo.trim(),
        idempotency_key: submitToken,
      });
      props.onReturned(result);
      return { ok: true };
    } catch (error) {
      // Every refusal is the SERVER's (BR-SHL-025) and is shown, never guessed.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      kicker={t("payments.reverse.kicker", {
        number: detail.payment_no ?? t("payments.row.noNumber"),
      })}
      title={t("payments.markReturned.title")}
      schema={markReturnedSchema((key) => t(key))}
      values={{ returned_on: returnedOn, return_code: returnCode }}
      submitLabel={t("payments.markReturned.submit")}
      // B14 rule 6 — it takes money back off a customer's account.
      submitVariant="danger"
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <SelectField
        id="mark-returned-reason"
        label={t("payments.reverse.reason")}
        value={reason}
        onChange={(value) => setReason(value as AchReturnReason)}
        required
        options={ACH_RETURN_REASONS.map((code) => ({
          value: code,
          label: t(`payments.reverse.reason.${code}`),
        }))}
      />
      <TextField
        id="return_code"
        label={t("payments.markReturned.code")}
        value={returnCode}
        onChange={setReturnCode}
        required
        help={t("payments.markReturned.codeHelp")}
      />
      <DatePickerField
        id="returned_on"
        label={t("payments.reverse.returnedOn")}
        value={returnedOn}
        onChange={setReturnedOn}
        dateFormat={props.dateFormat}
        required
        help={t("payments.reverse.returnedOnHelp")}
      />
      <TextField
        id="mark-returned-memo"
        label={t("payments.reverse.memo")}
        value={memo}
        onChange={setMemo}
      />
      {/* B14 rule 11 — what the commit does, before the button. Two short
          sentences (rule 33's consequence cap), drawn always. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.consequence.tag")}
        data-consequence="mark-returned"
        title={t("payments.markReturned.consequence.title", {
          amount: formatMoney(detail.amount, detail.currency, props.locale),
        })}
        body={t("payments.markReturned.consequence.body")}
      />
    </FormModal>
  );
}
