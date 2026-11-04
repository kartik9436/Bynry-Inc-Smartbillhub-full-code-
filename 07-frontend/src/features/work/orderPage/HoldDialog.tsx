// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — image 10, *Put WO-0043 on
//           hold* (P4.3 *Hold reason and resume*).
// Rules:    J1 (a hold reason is the tenant's LOOKUP row — `GET
//           /work/hold-reasons` — never a list typed here) · B14 rule 38/44
//           (the form is built from the kit; the drawing decides what it
//           contains: Reason*, Back on, Note, one consequence line) · rule 33
//           (the consequence is ≤ 6 words) · BR-PAY-033 (a date field proposes
//           nothing it cannot defend — *Back on* is optional and starts empty)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ELLIPSIS ON *Put on hold…* PROMISED THIS DIALOG FOR A YEAR.** The
// button posted `{}` at once (`a10-put-on-hold`); a job was held with no reason
// and nothing ever said why or until when. The reason is required by the
// SERVER (`work.hold.reason_required`); the schema below is the courtesy.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { todayInZone } from "@/components/DateCell";

import { holdOrderWithReason, listHoldReasons } from "./orderPageEndpoints";

export function HoldDialog(props: {
  orderId: string;
  orderNo: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client: ApiClient;
  onClose: () => void;
  onHeld: () => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  const [backOn, setBackOn] = useState("");
  const [note, setNote] = useState("");

  const reasons = useQuery({
    queryKey: ["work", "hold-reasons"],
    queryFn: () => listHoldReasons(props.client),
    retry: false,
  });
  const options = (reasons.data ?? []).map((row) => ({ value: row.code, label: row.name }));

  const schema = z.object({
    reason_code: z.string().min(1, t("work.order.hold.reasonRequired")),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await holdOrderWithReason(
        props.orderId,
        { reason_code: reason, expected_return_on: backOn || null, note },
        props.client,
      );
      props.onHeld();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.order.hold.title", { order: props.orderNo })}
      schema={schema}
      values={{ reason_code: reason }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("work.order.hold.submit")}
      cancelLabel={t("work.order.hold.back")}
    >
      <SelectField
        id="reason_code"
        label={t("work.order.hold.reason")}
        value={reason}
        onChange={setReason}
        options={options}
        placeholder={t("work.order.hold.reasonPick")}
        required
      />
      <DatePickerField
        id="expected_return_on"
        label={t("work.order.hold.backOn")}
        value={backOn}
        onChange={setBackOn}
        dateFormat={props.dateFormat}
        min={todayInZone(props.timeZone)}
      />
      <TextField id="note" label={t("work.order.hold.note")} value={note} onChange={setNote} multiline />
      <p className="m-0 text-md" data-consequence="work-order-hold">
        {t("work.order.hold.consequence")}
      </p>
    </FormModal>
  );
}
