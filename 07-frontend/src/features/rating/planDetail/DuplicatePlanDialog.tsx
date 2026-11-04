// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 follow-up (lane PLAN-FIXES) — *Duplicate* from More ▾
//           (image 25): a new name and code, then the server copies.
// Defect:   DEF-RAT-9352 (Duplicate had no copy act; the hold is released)
// Rules:    BR-RAT-030 (the copy lands as a DRAFT — nothing billable until a
//           human publishes it) · B14 rule 33 (a fact ≤ 6 words) · BR-SHL-020
//           (the server's own refusal, under the box it names)
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { copyPlan } from "@/api/planDetailEndpoints";
import type { PlanDetailRead } from "@/api/planDetailEndpoints";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Note } from "@/components/TextBits";

import type { Translator } from "./planDetailModel";

export function duplicatePlanSchema(t: Translator) {
  return z.object({
    name: z.string().trim().min(1, t("rating.planDetail.duplicate.nameRequired")),
    code: z.string().trim().min(1, t("rating.planDetail.duplicate.codeRequired")),
  });
}

/**
 * The copy is the SERVER's (`POST /plans/{id}/duplicate`): it reads the
 * version in force today and writes a new draft plan — services, schedules,
 * charge codes, taxes, deposits, discounts and terms; never units, history or
 * dates. The name and code must be new, so the boxes start EMPTY rather than
 * pre-filled with a near-duplicate a clerk would have to notice and change.
 */
export function DuplicatePlanDialog(props: {
  planId: string;
  planName: string;
  client: ApiClient;
  onClose: () => void;
  onCopied: (copy: PlanDetailRead) => void;
  t: Translator;
}) {
  const { t } = props;
  const [name, setName] = useState("");
  const [code, setCode] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const copy = await copyPlan(props.planId, { name: name.trim(), code: code.trim() }, props.client);
      props.onCopied(copy);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("rating.planDetail.duplicate.title", { name: props.planName })}
      schema={duplicatePlanSchema(t)}
      values={{ name, code }}
      submitLabel={t("rating.planDetail.action.duplicate")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <TextField id="name" label={t("rating.planSections.plan.name")} value={name} onChange={setName} required />
      <TextField id="code" label={t("rating.planSections.plan.code")} value={code} onChange={setCode} required />
      <Note>{t("rating.planDetail.duplicate.note")}</Note>
    </FormModal>
  );
}
