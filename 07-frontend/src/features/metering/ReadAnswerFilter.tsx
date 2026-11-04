// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 13: *"filterable in Reads lists"*
//           (decision log 2026-10-24, *"SUMMARY CONFIRMED"*).
// Rules:    BR-MET-1218 (`answer[<key>]=<value>`, AND-ed by the server) ·
//           IS-4 (applied filters are removable chips, kept in the URL) ·
//           NFR-3 (the question is found by a SERVER search, never a list of
//           every question) · B14 rules 31, 33, 36/43 (kit pieces, a component)
// Tests:    ReadAnswerFilter.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The Reads list's ANSWER filter: `+ Answer` opens a small dialog — find a
 * question of a published format by typing (its format's name or its own
 * words), then pick or type the value — and each applied answer becomes a
 * removable chip beside the `+ Filter` chips.
 *
 * ⚠ **IT IS NOT A `TableConfig.filters` DIMENSION, AND CANNOT BE.** A declared
 * filter has a name the screen knows in advance; a question key is the
 * UTILITY's own (`readAnswersShared` says why the grammar is separate). Every
 * IS-4 behaviour is kept by hand: AND-ed on the server, one chip per applied
 * answer with a labelled ✕, and the state lives in the address bar.
 *
 * A dialog rather than a panel section, on the estimate precedent (B14 rule
 * 30 was declined; the instance rules): two fields, one outcome, back to the
 * list it was opened from.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { Chip } from "@/components/Chip";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  answerChoices,
  answerFilterValueText,
  answerQuestionsByKey,
  searchAnswerQuestions,
} from "./readAnswersShared";
import type { AnswerQuestion } from "./readAnswersShared";

export const answerQuestionsQueryKey = (term: string) => ["reads", "answer-questions", term] as const;

/** The option value of one question: its POSITION in the search's answer,
 *  because two formats may share a key and the clerk picked ONE of them. No
 *  id is put into any string (B14 rule 31; `G44` clause (c)). Never shown. */
function optionValue(index: number): string {
  return String(index);
}

export function ReadAnswerFilter(props: {
  answers: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  /** IS-8 — a date question's picker echoes the tenant's own format. */
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const [adding, setAdding] = useState(false);
  const keys = Object.keys(props.answers).sort();
  // The chips' words after a reload: the URL carries the key, the server the label.
  const labels = useQuery({
    queryKey: ["reads", "answer-questions", "keys", keys.join("\u0000")],
    queryFn: () => answerQuestionsByKey(keys, client),
    enabled: keys.length > 0,
    retry: false,
  });
  const labelOf = (key: string) =>
    (labels.data ?? []).find((question) => question.key === key)?.label ?? key;

  function remove(key: string) {
    const next = { ...props.answers };
    delete next[key];
    props.onChange(next);
  }

  return (
    <>
      {keys.map((key) => (
        <Chip
          key={key}
          data-answer-chip={key}
          onRemove={() => remove(key)}
          removeLabel={t("table.filters.remove", { label: labelOf(key) })}
        >
          {t("table.filters.chip", {
            label: labelOf(key),
            value: answerFilterValueText(props.answers[key] ?? "", translate),
          })}
        </Chip>
      ))}
      <Button size="sm" data-answer-filter-open="" onClick={() => setAdding(true)}>
        {t("metering.reads.answerFilter.open")}
      </Button>
      {adding && (
        <AnswerFilterDialog
          client={client}
          dateFormat={props.dateFormat}
          onClose={() => setAdding(false)}
          onApply={(key, value) => {
            setAdding(false);
            props.onChange({ ...props.answers, [key]: value });
          }}
        />
      )}
    </>
  );
}

export function AnswerFilterDialog(props: {
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onApply: (key: string, value: string) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [term, setTerm] = useState("");
  const [picked, setPicked] = useState("");
  const [value, setValue] = useState("");
  const search = useQuery({
    queryKey: answerQuestionsQueryKey(term),
    queryFn: () => searchAnswerQuestions(term, props.client),
    enabled: term.trim().length >= 1,
    retry: false,
  });
  const found = search.data ?? [];
  const question = picked === "" ? null : (found[Number(picked)] ?? null);
  const choices = question === null ? null : answerChoices(question, translate);

  async function submit(): Promise<FormSubmitOutcome> {
    if (question !== null && value.trim() !== "") {
      props.onApply(question.key, value.trim());
    }
    return { ok: true };
  }

  return (
    <FormModal
      title={t("metering.reads.answerFilter.title")}
      schema={z.object({
        question: z.string().min(1, t("metering.reads.answerFilter.questionRequired")),
        value: z.string().trim().min(1, t("metering.reads.answerFilter.valueRequired")),
      })}
      values={{ question: picked, value }}
      submitLabel={t("metering.reads.answerFilter.apply")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <RemoteSearchSelectField
        id="question"
        label={t("metering.reads.answerFilter.question")}
        term={term}
        onTermChange={(next) => {
          setTerm(next);
          setPicked("");
          setValue("");
        }}
        status={{
          idle: term.trim().length < 1,
          searching: search.isFetching,
          searched: search.isSuccess,
          failed: search.isError,
        }}
        options={found.map((row, index) => ({
          value: optionValue(index),
          label: row.label,
          kind: row.format_name,
        }))}
        value={picked}
        onChange={(next) => {
          setPicked(next);
          setValue("");
        }}
        words={{
          tooShort: t("metering.reads.answerFilter.search.tooShort"),
          searching: t("metering.reads.answerFilter.search.searching"),
          failed: t("metering.reads.answerFilter.search.failed"),
          noMatch: t("metering.reads.answerFilter.search.noMatch"),
        }}
        required
      />
      {question !== null &&
        (choices !== null ? (
          <SelectField
            id="value"
            label={t("metering.reads.answerFilter.value")}
            value={value}
            onChange={setValue}
            options={choices}
            placeholder={t("metering.reads.answerFilter.valuePick")}
            required
          />
        ) : question.data_type === "date" ? (
          // B14 rule 7 — a date is the date input; the server matches the
          // stored ISO day (`read_formats.coerce_answer`).
          <DatePickerField
            id="value"
            label={t("metering.reads.answerFilter.value")}
            value={value}
            onChange={setValue}
            dateFormat={props.dateFormat}
            required
          />
        ) : (
          <TextField
            id="value"
            label={t("metering.reads.answerFilter.value")}
            value={value}
            onChange={setValue}
            numeric={question.data_type === "number"}
            required
          />
        ))}
    </FormModal>
  );
}
