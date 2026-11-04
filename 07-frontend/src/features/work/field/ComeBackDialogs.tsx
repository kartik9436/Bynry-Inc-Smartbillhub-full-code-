// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-055 (EP-WRK-11) — the office decides: REOPEN the same
//           order, or RAISE a linked follow-on (E2E-17, E2E-18)
// Server:   POST /work-orders/{id}/come-back — `{decision, reason, note?,
//           template_id?, key?}` (`apps/work/field_reopen.office_decide`)
// Rules:    BR-FLD-00021 (a reconnect is always a NEW order — the server
//           refuses a reopen naming one, and its sentence is what reaches the
//           clerk) · BR-FLD-00022 + PO ruling 2026-10-21 (the office MAY
//           reopen a job it has already accepted) · NFR-3 (the template is
//           FOUND by typing — the screen never lists every template) ·
//           B14 rules 33 (consequence ≤ 6 words a sentence) · 38/44 (forms
//           are built with the kit's FormModal) · 43 (one component, every
//           host)
// ───────────────────────────────────────────────────────
//
// ⚠ **NEITHER DIALOG CHECKS ACCEPTANCE.** The PO ruled on 2026-10-21 that the
// office may reopen an accepted job, and the server is where that is decided
// (another lane is removing the old refusal). A screen that pre-refused would
// be a second opinion about a rule the server owns; whatever the server says,
// the form shows in its own words.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";

import { listTemplates } from "../workEndpoints";
import { newActKey, postComeBack } from "./fieldDeskEndpoints";
import type { ComeBackAnswer } from "./fieldDeskEndpoints";

const TEMPLATE_SEARCH_PER = 20;

async function submitted(run: () => Promise<void>): Promise<FormSubmitOutcome> {
  try {
    await run();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

interface ComeBackProps {
  orderId: string;
  orderNo: string;
  client: ApiClient;
  onClose: () => void;
  onDone: (answer: ComeBackAnswer) => void;
}

/** *Reopen…* — the same order goes back to the field; every reading, tick and
 *  photograph stays (metering's send-back, recorded beside it). */
export function ReopenDialog(props: ComeBackProps) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [key] = useState(newActKey);
  return (
    <FormModal
      title={t("work.field.reopenTitle", { order: props.orderNo })}
      schema={z.object({ reason: z.string().trim().min(1, t("work.field.reasonRequired")) })}
      values={{ reason }}
      submitLabel={t("work.field.reopenSubmit")}
      cancelLabel={t("work.field.back")}
      onSubmit={() =>
        submitted(async () => {
          const answer = await postComeBack(
            props.orderId,
            {
              decision: "reopen",
              reason: reason.trim(),
              note: note.trim() === "" ? undefined : note.trim(),
              key,
            },
            props.client,
          );
          props.onDone(answer);
        })
      }
      onClose={props.onClose}
    >
      <TextField id="reason" label={t("work.field.reason")} value={reason} onChange={setReason} multiline required />
      <TextField id="note" label={t("work.field.note")} value={note} onChange={setNote} multiline />
      <p className="m-0 text-md" data-consequence="work-field-reopen">
        {t("work.field.reopenConsequence")}
      </p>
    </FormModal>
  );
}

/** *Raise follow-on…* — a NEW order from a template, on the original's own
 *  anchors, linked to it. Allowed before or after acceptance. */
export function FollowOnDialog(props: ComeBackProps) {
  const { t } = useTranslation();
  const [term, setTerm] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [key] = useState(newActKey);
  const search = useQuery({
    queryKey: ["work", "field", "follow-on", "templates", term],
    queryFn: () => listTemplates({ q: term, page: 1, per: TEMPLATE_SEARCH_PER }, props.client),
    enabled: term.trim().length >= 1,
    retry: false,
  });
  // Only a PUBLISHED template raises an order (`BR-WRK-011`: a draft is not a
  // version), so a draft is never offered rather than offered and refused.
  const options = (search.data?.results ?? [])
    .filter((row) => row.status === "published")
    .map((row) => ({ value: row.id, label: row.name }));
  return (
    <FormModal
      title={t("work.field.followOnTitle", { order: props.orderNo })}
      schema={z.object({
        template: z.string().min(1, t("work.field.templateRequired")),
        reason: z.string().trim().min(1, t("work.field.reasonRequired")),
      })}
      values={{ template: templateId, reason }}
      submitLabel={t("work.field.followOnSubmit")}
      cancelLabel={t("work.field.back")}
      onSubmit={() =>
        submitted(async () => {
          const answer = await postComeBack(
            props.orderId,
            {
              decision: "follow_on",
              reason: reason.trim(),
              note: note.trim() === "" ? undefined : note.trim(),
              template_id: templateId,
              key,
            },
            props.client,
          );
          props.onDone(answer);
        })
      }
      onClose={props.onClose}
    >
      <RemoteSearchSelectField
        id="template"
        label={t("work.field.template")}
        term={term}
        onTermChange={(next) => {
          setTerm(next);
          setTemplateId("");
        }}
        status={{
          idle: term.trim().length < 1,
          searching: search.isFetching,
          searched: search.isSuccess,
          failed: search.isError,
        }}
        options={options}
        value={templateId}
        onChange={setTemplateId}
        words={{
          tooShort: t("work.field.templateSearch.tooShort"),
          searching: t("work.field.templateSearch.searching"),
          failed: t("work.field.templateSearch.failed"),
          noMatch: t("work.field.templateSearch.noMatch"),
        }}
        required
      />
      <TextField id="reason" label={t("work.field.reason")} value={reason} onChange={setReason} multiline required />
      <TextField id="note" label={t("work.field.note")} value={note} onChange={setNote} multiline />
      <p className="m-0 text-md" data-consequence="work-field-follow-on">
        {t("work.field.followOnConsequence")}
      </p>
    </FormModal>
  );
}
