// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-057 (EP-WRK-11) — *Send alert…* on an order: one alert to
//           the order's technician's handset (N25)
// Server:   POST /work/field-alerts — `{kind, work_order_id, message?, key}`
//           (`apps/work/field_alerts.send_alert`)
// Rules:    BR-FLD-00028 (an emergency must be answered within five minutes,
//           or dispatch is told — the server keeps that clock) ·
//           BR-FLD-00029 (dispatch messages only; a dispatch message needs
//           its words) · §0 rule 7 (idempotent on a key minted when the
//           dialog opens) · B14 rules 33 · 38/44 (FormModal) · 43
// ───────────────────────────────────────────────────────
//
// ⚠ **THE TECHNICIAN IS NOT PICKED HERE.** The server sends to the order's own
// technician and refuses, BY NAME, a job held by a crew and nobody — *"an
// alert rings ONE handset's owner, and choosing a crew member is dispatch's
// decision"*. That refusal arrives as the server's sentence on this form.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import { FIELD_ALERT_KINDS, newActKey, sendFieldAlert } from "./fieldDeskEndpoints";
import type { FieldAlertKind } from "./fieldDeskEndpoints";

export function SendAlertDialog(props: {
  orderId: string;
  orderNo: string;
  client: ApiClient;
  onClose: () => void;
  onSent: () => void;
}) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<FieldAlertKind>("urgent_assignment");
  const [message, setMessage] = useState("");
  const [key] = useState(newActKey);

  const schema = z
    .object({ kind: z.string().min(1), message: z.string() })
    .refine((v) => v.kind !== "dispatch_message" || v.message.trim().length > 0, {
      message: t("work.field.alertMessageRequired"),
      path: ["message"],
    });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await sendFieldAlert(
        {
          kind,
          work_order_id: props.orderId,
          message: message.trim() === "" ? undefined : message.trim(),
          key,
        },
        props.client,
      );
      props.onSent();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.field.alertTitle", { order: props.orderNo })}
      schema={schema}
      values={{ kind, message }}
      submitLabel={t("work.field.alertSubmit")}
      cancelLabel={t("work.field.back")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <SelectField
        id="kind"
        label={t("work.field.alertKind")}
        value={kind}
        onChange={(value) => setKind(value as FieldAlertKind)}
        options={FIELD_ALERT_KINDS.map((k) => ({ value: k, label: t(`work.field.kind.${k}`) }))}
        required
      />
      <TextField
        id="message"
        label={t("work.field.alertMessage")}
        value={message}
        onChange={setMessage}
        multiline
        required={kind === "dispatch_message"}
      />
    </FormModal>
  );
}
