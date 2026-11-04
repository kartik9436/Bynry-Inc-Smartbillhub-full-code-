// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 8, lane FIX-8B — `DEF-WRK-9675`: images 04 and
//           06 draw *Send back…* beside *Accept ✓* on a finished job, and
//           `POST /work-orders/{id}/send-back` (P4.14) had been served since
//           2.500.0 with no door on the page.
// Rules:    BR-MET-110 (the field completes, the office accepts — or sends it
//           back, only BEFORE accepting; judgment J9) · B14 rules 38/44 (the
//           form is built from the kit) · 11 (a consequence before the act) ·
//           33 (the consequence ≤ 6 words) · 43 (a component)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE REASON IS REQUIRED BY THE SERVER** (`work.order.send_back_reason_
// required`); the schema below is the courtesy and reads the SAME catalogue
// sentence, so the two can never say different things.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import { sendBackOrder } from "./orderPageEndpoints";

export function SendBackDialog(props: {
  orderId: string;
  orderNo: string;
  client: ApiClient;
  onClose: () => void;
  onSent: () => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");

  const schema = z.object({
    reason: z.string().trim().min(1, t("work.order.send_back_reason_required")),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await sendBackOrder(props.orderId, reason, props.client);
      props.onSent();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.order.sendBack.title", { order: props.orderNo })}
      schema={schema}
      values={{ reason }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("work.order.sendBack.submit")}
      cancelLabel={t("work.order.sendBack.back")}
    >
      <TextField
        id="reason"
        label={t("work.order.sendBack.reason")}
        value={reason}
        onChange={setReason}
        multiline
        required
      />
      <p className="m-0 text-md" data-consequence="work-order-send-back">
        {t("work.order.sendBack.consequence")}
      </p>
    </FormModal>
  );
}
