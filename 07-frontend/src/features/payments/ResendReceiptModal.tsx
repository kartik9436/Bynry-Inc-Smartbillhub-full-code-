// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.11` — screen **2·3h Resend** of
//           `05-prototype/06 Payments Page Blueprint.pdf`, **p049–p050 read AS
//           IMAGES at scale 2.0** (B14 rule 42).
// Screens:  2·3h Resend (`S35` · `PAY-E`) — NEW.
// Rules:    B14 rule 9 (multi-select renders as removable CHIPS + an add
//           control — never a wall of checkboxes) · rule 11 (a consequence
//           preview) · rule 33 · rule 43 (a component) · CLAUDE.md hard rule 6
//           (idempotency — `copy_no` is the whole guarantee) · hard rule 7
// ───────────────────────────────────────────────────────
// *"They lost the receipt and want another."*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE SMALLEST OF THE THREE, BECAUSE THE WHOLE MACHINE ALREADY EXISTS
// ══════════════════════════════════════════════════════════════════════════
// p050: *"**The receipt itself is live** — every recorded payment queues one on
// email and text, with a printed floor so a utility that switches every
// electronic channel off still gets paper. **What is missing is re-sending.**"*
// So this RE-QUEUES AN EXISTING DOCUMENT; it composes nothing. A channel this
// payment has no receipt on is refused BY NAME rather than composed here —
// building a second receipt path is what the PO ruled out on 2026-09-22.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ `copy_no` IS ECHOED, NEVER COMPUTED — AND THAT IS HARD RULE 6 ITSELF
// ══════════════════════════════════════════════════════════════════════════
// `GET /payments/{id}` serves `next_copy_no`, and this modal sends **that
// number back unchanged**. The round trip is the guarantee: a double-click
// resubmits the same number, collides with its own row in the DATABASE, and
// comes back `created: false` — **one copy reaches the customer, not two.**
//
// **An endpoint that allocated the number itself would hand out 1 and then 2
// and post two receipts, while looking perfectly correct** — the server's own
// `next_copy_no` docstring makes that argument in full. So this file does no
// arithmetic on it at all, and a `+ 1` appearing here later is a money defect
// wearing a tidy-up's clothes.
//
// ⚠ **AND `created: false` IS A REPLAY, NOT A FAILURE.** A screen that reported
// it as an error would teach a clerk to press Send again, which is the exact
// behaviour the guarantee exists to make harmless. It is reported as *already
// sent* and the modal closes.
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { RECEIPT_CHANNELS, resendReceipt } from "@/api/paymentDetailEndpoints";
import type { PaymentDetail, ResentReceipt } from "@/api/paymentDetailEndpoints";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FieldLabel, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

/** The three a receipt goes out on, in the drawn order. The words are the
 *  catalogue's — `pdf_print` is what the queue calls it and *Print* is what a
 *  clerk calls it (B14 rule 31). */
const CHANNEL_KEYS: Record<string, string> = {
  pdf_print: "payments.resend.channel.print",
  email: "payments.resend.channel.email",
  sms: "payments.resend.channel.sms",
};

export function resendReceiptSchema(t: (key: string) => string) {
  return z.object({
    // ② *Send by* · required. A resend with no channel is a form somebody
    // opened and did not fill.
    channels: z.array(z.string()).min(1, { message: t("payments.resend.channelRequired") }),
  });
}

export interface ResendReceiptModalProps {
  client: ApiClient;
  detail: PaymentDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSent: (result: ResentReceipt) => void;
}

export function ResendReceiptModal(props: ResendReceiptModalProps) {
  const { t } = useTranslation();
  const { detail } = props;

  // The channels this payment ALREADY has a receipt on — which is both what ①
  // reports and what the server will accept. Pre-selected, because *"send it
  // again"* means the same way it went, and a clerk who wants a different
  // channel deselects.
  const sentOn = [...new Set(detail.receipts.map((one) => one.channel))].filter((one) =>
    (RECEIPT_CHANNELS as readonly string[]).includes(one),
  );
  const [channels, setChannels] = useState<string[]>(sentOn);
  const [to, setTo] = useState("");

  const lastSentAt = detail.receipts
    .map((one) => one.sent_at ?? one.created_at ?? null)
    .filter((one): one is string => one !== null)
    .sort()
    .at(-1);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const result = await resendReceipt(props.client, detail.payment_no ?? detail.id, {
        channels,
        // ⚠ ECHOED. See this file's header — a `+ 1` here is a money defect.
        copy_no: detail.next_copy_no,
      });
      props.onSent(result);
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
      // p049 draws the kicker as the payment AND the customer — the two facts a
      // clerk confirms before sending somebody else's receipt.
      kicker={t("payments.resend.kicker", {
        number: detail.payment_no ?? t("payments.row.noNumber"),
        customer: detail.customer_name ?? t("payments.row.noCustomer"),
      })}
      title={t("payments.resend.title")}
      schema={resendReceiptSchema((key) => t(key))}
      values={{ channels }}
      submitLabel={t("payments.resend.submit")}
      /* ⚠ **NOT DANGER TIER, AND p050 ③ SAYS WHY IN ITS OWN WORDS:** *"It
         touches no money · the reassurance this screen exists to give"*.
         Reddening a send would spend rule 6's meaning on an act that moves
         nothing. */
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* ① **IT ALREADY WENT** — *"so the clerk knows this is a repeat, not a
          first send"* (p050 ①). ⚠ **AND AN EMPTY `receipts[]` IS A DIFFERENT
          FACT, SAID DIFFERENTLY.** A payment recorded while the utility had
          the receipt election switched OFF genuinely has no rows; claiming a
          first send there would be a sentence the product cannot support. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.resend.alreadyTag")}
        data-consequence="resend-already"
        title={
          sentOn.length === 0
            ? t("payments.resend.neverSentTitle")
            : t("payments.resend.alreadyTitle")
        }
        body={
          sentOn.length === 0 ? (
            t("payments.resend.neverSentBody")
          ) : (
            <>
              {lastSentAt !== undefined && (
                <DateCell
                  value={lastSentAt}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              )}{" "}
              {sentOn.map((channel) => t(CHANNEL_KEYS[channel] ?? "")).join(" · ")}
            </>
          )
        }
      />

      {/* ② **Send by — CHIPS, B14 rule 9**, which the drawing already draws:
          `Email ×` `Text ×` `+ Add a channel ▾`. Not checkboxes: rule 9 says a
          multi-select is removable chips plus an add control, and the kit owns
          both halves so this screen invents neither. */}
      {/* ⚠ **THE VISIBLE LABEL AND THE ASTERISK COME FROM THE KIT'S OWN
          `FieldLabel`, NOT FROM MARKUP WRITTEN HERE.** `ChipMultiSelect` puts
          its `label` on `aria-label` and draws nothing a sighted clerk reads;
          every other caller supplies one from a surrounding `Panel title=…`,
          and a modal has no panel. The drawing draws **Send by \*** — a name
          and a required marker (B14 rule 10) — so the kit's one label
          component provides both. `DEF-SHL-6250` is the deeper fix. */}
      <FieldLabel label={t("payments.resend.channels")} required />
      <ChipMultiSelect
        label={t("payments.resend.channels")}
        options={RECEIPT_CHANNELS.map((code) => ({
          value: code,
          label: t(CHANNEL_KEYS[code]),
        }))}
        selected={channels}
        onChange={setChannels}
        addLabel={t("payments.resend.addChannel")}
        emptyLabel={t("payments.resend.noChannel")}
        removeLabel={t("payments.resend.removeChannel")}
        testKey="resend-channels"
      />

      {/* *To* — the drawn field, read from the account. It is `readOnly`
          because the recipient lives on the CUSTOMER and changing it here
          would put a second copy of an address in a place nothing reads back
          (the drawing's own helper says so: *"From the account. Change it on
          the customer."*). */}
      <TextField
        id="resend-to"
        label={t("payments.resend.to")}
        value={to === "" ? (detail.customer_name ?? "") : to}
        onChange={setTo}
        readOnly
        help={t("payments.resend.toHelp")}
      />

      {/* ③ **WHAT IT WILL DO — B14 rule 11**, and p050 ③'s *"it touches no
          money"* is the half a clerk actually needs before pressing Send on
          somebody else's receipt. Two sentences, six words each. */}
      <ConsequenceBox
        tone="check"
        tag={t("payments.consequence.tag")}
        data-consequence="resend"
        title={t("payments.resend.consequence.title", { count: channels.length })}
        body={t("payments.resend.consequence.body")}
      />
    </FormModal>
  );
}
