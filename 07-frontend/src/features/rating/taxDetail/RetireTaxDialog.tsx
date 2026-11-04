// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — *Retire* from More ▾ (image 21).
// Rules:    CR-165 §7 item 4 (our judgment, decision log 2026-10-03): retire
//           ENDS THE WINDOW on a date — `POST /taxes/{id}/retire` — never
//           `deleted_at` · B14 rule 6 (danger tier) · rule 33 (a consequence
//           before an irreversible act ≤ 6 words a sentence, at most two) ·
//           BR-SHL-020 (the server's own refusal sentence)
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { retireTax } from "@/api/taxDetailEndpoints";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Note } from "@/components/TextBits";

import type { TaxRegional, Translator } from "./taxDetailModel";

export function retireSchema(t: Translator) {
  return z.object({
    effective_to: z.string().min(1, t("rating.taxDetail.retire.dateRequired")),
  });
}

/**
 * Ask for the LAST day the tax charges, then end its window there. *Retire the
 * 2% Bexar tax on 12/31/2026* — a December bill still carries it, a January
 * bill carries no Bexar line (CR-165 §7 item 4's worked case). The server
 * refuses a date no version is in force on, and a date a later version starts
 * after, each by name; the refusal is shown as the server words it.
 */
export function RetireTaxDialog(props: {
  taxId: string;
  taxName: string;
  client: ApiClient;
  regional: TaxRegional;
  onClose: () => void;
  onRetired: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const body: { effective_to: string; reason?: string } = { effective_to: endDate };
      if (reason.trim() !== "") body.reason = reason.trim();
      await retireTax(props.taxId, body, props.client);
      props.onRetired();
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
      title={t("rating.taxDetail.retire.title", { name: props.taxName })}
      schema={retireSchema(t)}
      values={{ effective_to: endDate }}
      submitLabel={t("rating.definition.action.retire")}
      submitVariant="danger"
      onSubmit={submit}
      onClose={props.onClose}
    >
      <DatePickerField
        id="effective_to"
        label={t("rating.taxDetail.retire.lastDay")}
        value={endDate}
        onChange={setEndDate}
        dateFormat={props.regional.dateFormat}
        required
      />
      <TextField id="reason" label={t("rating.taxDetail.retire.reason")} value={reason} onChange={setReason} />
      <Note>{t("rating.taxDetail.retire.consequence")}</Note>
    </FormModal>
  );
}
