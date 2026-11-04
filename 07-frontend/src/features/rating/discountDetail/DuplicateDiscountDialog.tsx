// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 follow-up (§18, 2026-10-03) — More ▾ *Duplicate*
//           (image 23) is LIVE.
// Defect:   DEF-RAT-9310 (Duplicate had no door)
// Rules:    B14 rules 31, 33 (a fact of six words, no rationale) · rule 43 (a
//           component) · BR-SHL-020 (a refusal is the server's own sentence)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SERVER COPIES; THE DIALOG ONLY ASKS FOR THE TWO THINGS IT MAY NOT.**
// `POST /discounts/{id}/duplicate {code, name}` copies every value, condition,
// limit and list of the version in force into a NEW DRAFT, with no dates, on no
// plan and received by nobody (`discount_services.duplicate_discount`). A new
// code and bill line label are required, so those are the dialog's two boxes;
// everything else is changed afterwards on the draft's own *Edit*.
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { duplicateDiscount } from "@/api/discountDetailEndpoints";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import type { Translator } from "./discountDetailModel";

export function DuplicateDiscountDialog(props: {
  discountId: string;
  name: string;
  client: ApiClient;
  onClose: () => void;
  onDone: (copy: { id: string; name: string }) => void;
  t: Translator;
}) {
  const { t } = props;
  const [code, setCode] = useState("");
  const [name, setName] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const copy = await duplicateDiscount(
        props.discountId,
        { code: code.trim().toUpperCase(), name: name.trim() },
        props.client,
      );
      props.onDone({ id: copy.id, name: copy.name });
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("rating.discountDetail.duplicate.title", { name: props.name })}
      schema={z.object({
        code: z.string().trim().min(1, t("rating.discountDetail.duplicate.codeRequired")),
        name: z.string().trim().min(1, t("rating.discountDetail.duplicate.nameRequired")),
      })}
      values={{ code, name }}
      submitLabel={t("rating.definition.action.duplicate")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <p className="mb-4 text-base" data-discount-duplicate-fact="">
        {t("rating.discountDetail.duplicate.fact")}
      </p>
      <TextField id="code" label={t("rating.discountForm.field.code")} value={code} onChange={setCode} required />
      <TextField id="name" label={t("rating.discountForm.field.label")} value={name} onChange={setName} required />
    </FormModal>
  );
}
