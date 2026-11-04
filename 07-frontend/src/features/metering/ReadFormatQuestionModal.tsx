// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11: add / edit ONE question on a read
//           format's draft. PO, verbatim: *"this will be similar to custom
//           fields"*, and *"this is correct"* to the three behaviours — asked
//           when · follow-ups · raise a work order — all in the first release.
// Rules:    BR-MET-1211 (typed like a custom field, plus Photo) · BR-MET-1214
//           (asked when · a follow-up names an EARLIER question) · BR-MET-1217
//           (an answer raises a job from a published template) · B14 rule 38
//           (a form is built to our UI rules) · B14 rule 43 (the type half is
//           IMPORTED from the custom-field editor, never redrawn)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SERVER IS THE AUTHORITY ON EVERY RULE HERE.** "Earlier" means a lower
// position in the draft, and the server refuses a follow-up on a later question
// (`metering.readFormats.show_if_earlier`); this form OFFERS only earlier ones
// so the refusal is the exception, never the way a clerk learns the rule. A
// photo question takes no answer a follow-up or a job could test, so it is
// never offered as a parent and cannot raise a job.
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { CheckboxField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import {
  DefinitionTypeFields,
  SELECT_DATA_TYPES,
  definitionSchema,
  parseOptions,
  previewKey,
} from "@/features/tenancy/SettingsCustomFields";
import type { DefinitionTypeValues } from "@/features/tenancy/SettingsCustomFields";
import { PublishedTemplateField } from "@/features/work/PublishedTemplateField";

import { ASKED_WHEN, PHOTO_TYPE, addQuestion, updateQuestion } from "./readFormatsEndpoints";
import type {
  AnswerValue,
  AskedWhen,
  QuestionBody,
  ReadFormatDetail,
  ReadFormatQuestion,
} from "./readFormatsEndpoints";

/** The questions a follow-up may name: EARLIER ones that can take an answer. */
export function showIfCandidates(
  questions: readonly ReadFormatQuestion[],
  editing: ReadFormatQuestion | null,
): ReadFormatQuestion[] {
  const before =
    editing === null ? questions : questions.filter((q) => q.seq < editing.seq);
  return before.filter((q) => q.data_type !== PHOTO_TYPE);
}

/** An answer as the select holds it (a string) → the JSON type the server tests. */
export function answerFromText(dataType: string, text: string): AnswerValue {
  if (dataType === "boolean") {
    return text === "true";
  }
  return text;
}

export function answerToText(value: AnswerValue | undefined | null): string {
  return value === undefined || value === null ? "" : String(value);
}

interface QuestionForm extends DefinitionTypeValues {
  label: string;
  asked_when: AskedWhen;
  show_if_key: string;
  show_if_answer: string;
  raise: boolean;
  raise_answer: string;
  raise_template: string;
}

function formFrom(q: ReadFormatQuestion | null): QuestionForm {
  return {
    label: q?.label ?? "",
    data_type: q?.data_type ?? "text",
    options: (q?.options ?? []).join("\n"),
    help_text: q?.help_text ?? "",
    is_required: q?.is_required ?? false,
    asked_when: q?.asked_when ?? "every_reading",
    show_if_key: q?.show_if?.question_key ?? "",
    show_if_answer: answerToText(q?.show_if?.answer),
    raise: q?.raise_work != null,
    raise_answer: answerToText(q?.raise_work?.on_answer),
    raise_template: q?.raise_work?.template_id ?? "",
  };
}

/** The ANSWER control for a question of `dataType` — a list where the answers
 *  are a list, free text otherwise (the server checks the value either way). */
function AnswerField(props: {
  id: string;
  label: string;
  dataType: string;
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  if (props.dataType === "boolean") {
    return (
      <SelectField
        id={props.id}
        label={props.label}
        value={props.value}
        onChange={props.onChange}
        required
        placeholder={t("settings.readFormats.answer.pick")}
        options={[
          { value: "true", label: t("settings.readFormats.answer.yes") },
          { value: "false", label: t("settings.readFormats.answer.no") },
        ]}
      />
    );
  }
  if (SELECT_DATA_TYPES.includes(props.dataType)) {
    return (
      <SelectField
        id={props.id}
        label={props.label}
        value={props.value}
        onChange={props.onChange}
        required
        placeholder={t("settings.readFormats.answer.pick")}
        options={props.options.map((option) => ({ value: option, label: option }))}
      />
    );
  }
  return (
    <TextField id={props.id} label={props.label} value={props.value} onChange={props.onChange} required />
  );
}

export function ReadFormatQuestionModal(props: {
  formatId: string;
  /** The draft's questions, in order — the follow-up candidates come from it. */
  questions: readonly ReadFormatQuestion[];
  existing: ReadFormatQuestion | null;
  client: ApiClient;
  onClose: () => void;
  onSaved: (detail: ReadFormatDetail) => void;
}) {
  const { t } = useTranslation();
  const creating = props.existing === null;
  const [form, setForm] = useState<QuestionForm>(() => formFrom(props.existing));

  function set<K extends keyof QuestionForm>(key: K, value: QuestionForm[K]): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  const candidates = showIfCandidates(props.questions, props.existing);
  const parent = candidates.find((q) => q.key === form.show_if_key) ?? null;
  const ownOptions = parseOptions(form.options);
  const canRaise = form.data_type !== PHOTO_TYPE;

  async function submit(): Promise<FormSubmitOutcome> {
    const body: QuestionBody = {
      label: form.label.trim(),
      help_text: form.help_text.trim(),
      data_type: form.data_type,
      is_required: form.is_required,
      asked_when: form.asked_when,
      show_if:
        parent === null
          ? null
          : {
              question_key: parent.key,
              answer: answerFromText(parent.data_type, form.show_if_answer),
            },
      raise_work:
        form.raise && canRaise
          ? {
              on_answer: answerFromText(form.data_type, form.raise_answer),
              template_id: form.raise_template,
            }
          : null,
    };
    if (SELECT_DATA_TYPES.includes(form.data_type)) {
      body.options = ownOptions;
    }
    try {
      const saved =
        props.existing === null
          ? await addQuestion(props.formatId, body, props.client)
          : await updateQuestion(props.formatId, props.existing.key, body, props.client);
      props.onSaved(saved);
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
      title={t(creating ? "settings.readFormats.question.addTitle" : "settings.readFormats.question.editTitle")}
      // The custom-field schema, minus the one field a question does not have.
      schema={definitionSchema(t, form.data_type).omit({ entity: true })}
      values={form}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t(creating ? "settings.readFormats.question.add" : "settings.readFormats.question.save")}
    >
      <TextField
        id="label"
        label={t("settings.customFields.field.label")}
        value={form.label}
        onChange={(value) => set("label", value)}
        required
      />
      <TextField
        id="key"
        label={t("settings.customFields.field.key")}
        value={props.existing === null ? previewKey(form.label) : props.existing.key}
        onChange={() => undefined}
        readOnly
      />
      <DefinitionTypeFields
        values={form}
        onChange={(key, value) => setForm((current) => ({ ...current, [key]: value }))}
        requiredLabel={t("settings.readFormats.question.required")}
        extraTypes={[{ value: PHOTO_TYPE, label: t("settings.readFormats.type.photo") }]}
      />
      <SelectField
        id="asked_when"
        label={t("settings.readFormats.question.askedWhen")}
        value={form.asked_when}
        onChange={(value) => set("asked_when", value as AskedWhen)}
        required
        options={ASKED_WHEN.map((code) => ({
          value: code,
          label: t(`settings.readFormats.asked.${code}`),
        }))}
      />
      <SelectField
        id="show_if"
        label={t("settings.readFormats.question.showIf")}
        value={form.show_if_key}
        onChange={(value) => {
          set("show_if_key", value);
          set("show_if_answer", "");
        }}
        options={[
          { value: "", label: t("settings.readFormats.question.always") },
          ...candidates.map((q) => ({ value: q.key, label: q.label })),
        ]}
      />
      {parent !== null && (
        <AnswerField
          id="show_if_answer"
          label={t("settings.readFormats.question.answerIs")}
          dataType={parent.data_type}
          options={parent.options ?? []}
          value={form.show_if_answer}
          onChange={(value) => set("show_if_answer", value)}
        />
      )}
      {canRaise && (
        <CheckboxField
          id="raise"
          label={t("settings.readFormats.question.raise")}
          checked={form.raise}
          onChange={(checked) => set("raise", checked)}
        />
      )}
      {canRaise && form.raise && (
        <>
          <AnswerField
            id="raise_work"
            label={t("settings.readFormats.question.onAnswer")}
            dataType={form.data_type}
            options={ownOptions}
            value={form.raise_answer}
            onChange={(value) => set("raise_answer", value)}
          />
          <PublishedTemplateField
            id="raise_template"
            label={t("settings.readFormats.question.template")}
            value={form.raise_template}
            onChange={(value) => set("raise_template", value)}
            initialName={props.existing?.raise_work?.template?.name}
            required
            client={props.client}
          />
        </>
      )}
    </FormModal>
  );
}
