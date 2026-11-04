// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the dialogs behind the header's acts:
//           Approve, Send back, Retire (with a date), Delete draft.
// Rules:    PO rulings 2026-10-03 (1) approval is the LAST act — the version
//           goes live by itself on its start date; (4) Retire asks for an end
//           date and after it nobody gets the discount · B14 rule 6 (danger
//           tier) · rule 33 (a consequence ≤ 6 words a sentence, at most two)
//           · BR-SHL-020 (the server's own refusal sentence)
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { retireDiscount, sendBackDiscount } from "@/api/discountDetailEndpoints";
import { todayInZone } from "@/components/DateCell";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Note } from "@/components/TextBits";

import type { DiscountRegional, Translator } from "./discountDetailModel";

async function outcomeOf(act: () => Promise<void>): Promise<FormSubmitOutcome> {
  try {
    await act();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

/** The retire date: required, and not before the utility's today — the server
 *  refuses a past date too (`rating.discounts.retire_in_past`), this says so
 *  before the round trip. ISO dates compare as strings. */
export function retireSchema(t: Translator, today: string) {
  return z.object({
    effective_to: z
      .string()
      .min(1, t("rating.taxDetail.retire.dateRequired"))
      .refine((value) => value >= today, t("rating.discountDetail.retire.notPast")),
  });
}

/**
 * Retire on a date (ruling 4). *Retire SENIOR on 12/31/2026* — the December
 * bill keeps −$9.00 off $60.00, January's has none, enrolled accounts included.
 */
export function RetireDiscountDialog(props: {
  discountId: string;
  name: string;
  client: ApiClient;
  regional: DiscountRegional;
  onClose: () => void;
  onDone: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const today = todayInZone(props.regional.timeZone);
  return (
    <FormModal
      title={t("rating.taxDetail.retire.title", { name: props.name })}
      schema={retireSchema(t, today)}
      values={{ effective_to: endDate }}
      submitLabel={t("rating.definition.action.retire")}
      submitVariant="danger"
      onSubmit={() =>
        outcomeOf(async () => {
          const body: { effective_to: string; reason?: string } = { effective_to: endDate };
          if (reason.trim() !== "") body.reason = reason.trim();
          await retireDiscount(props.discountId, body, props.client);
          props.onDone();
        })
      }
      onClose={props.onClose}
    >
      <DatePickerField
        id="effective_to"
        label={t("rating.discountDetail.retire.lastDay")}
        value={endDate}
        onChange={setEndDate}
        dateFormat={props.regional.dateFormat}
        required
      />
      <TextField id="reason" label={t("rating.taxDetail.retire.reason")} value={reason} onChange={setReason} />
      <Note>{t("rating.discountDetail.retire.consequence")}</Note>
    </FormModal>
  );
}

/** Send back — the approver returns the draft with a note (required). */
export function SendBackDialog(props: {
  discountId: string;
  name: string;
  client: ApiClient;
  onClose: () => void;
  onDone: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [note, setNote] = useState("");
  return (
    <FormModal
      title={t("rating.discountDetail.sendBack.title", { name: props.name })}
      schema={z.object({ note: z.string().trim().min(1, t("rating.discountDetail.sendBack.noteRequired")) })}
      values={{ note }}
      submitLabel={t("rating.discountDetail.act.sendBack")}
      onSubmit={() =>
        outcomeOf(async () => {
          await sendBackDiscount(props.discountId, { note: note.trim() }, props.client);
          props.onDone();
        })
      }
      onClose={props.onClose}
    >
      <TextField id="note" label={t("rating.discountDetail.sendBack.note")} value={note} onChange={setNote} multiline required />
    </FormModal>
  );
}
