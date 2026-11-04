// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — step 2, *Schedule & crew*
//           (image 16).
// Rulings:  23 (the due date is a date picker — the 23 Sep *Expected Date*,
//           asked once) · 24 (NO Area: the job takes its building's) · 25 (a
//           job can be assigned when it is raised, or left blank —
//           technicians, crews and contractors) · 2 (the skill match ADVISES
//           and never blocks).
// Rules:    B14 rules 7 (a date field is the date input), 8 (a long list is
//           searchable — the candidates are a SERVER page, NFR-5: no cap),
//           21, 31, 33, 39, 43 (the ASSIGN lane's `CandidatePicker` is the one
//           picker; this step feeds it the raise's candidates), 44.
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE AREA FIELD IS GONE, NOT HIDDEN.** Ruling 24 is *"area should not be
// needed as we are attaching premises"*, and the server walks the area from
// the premises (§7.3, P2.17). A hidden field would still post a value the
// rule says nobody chooses.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DatePickerField, SelectField } from "@/components/FormModal";
import { useRegional } from "@/features/metering/meteringShared";

import { CANDIDATE_PAGE_SIZE, CandidatePicker } from "../CandidatePicker";
import type { CandidatesState } from "../CandidatePicker";
import { bestFitFirst } from "../candidateAdvice";

import { listRaiseCandidates } from "./raiseEndpoints";
import type { RaiseForm, RaiseUpdate } from "./raiseForm";
import { useDebouncedTerm } from "./raiseModel";

/** The candidates for a job not yet raised — the same state `CandidatePicker`
 *  reads for an order, from `GET /work/candidates` instead (§7.3). */
function useRaiseCandidates(
  query: { templateId: string; premisesId: string; unitIds: readonly string[]; on: string },
  client: ApiClient,
): CandidatesState {
  const [term, setTerm] = useState("");
  const settled = useDebouncedTerm(term.trim());
  const q = settled.length >= 2 ? settled : "";
  const read = useQuery({
    queryKey: ["work", "raise", "candidates", query.templateId, query.premisesId, query.unitIds.join(","), query.on, q],
    queryFn: () =>
      listRaiseCandidates(
        { ...query, q, page: 1, per: CANDIDATE_PAGE_SIZE },
        client,
      ),
  });
  const candidates = useMemo(() => bestFitFirst(read.data?.results ?? []), [read.data]);
  return {
    term,
    setTerm,
    candidates,
    complete: read.data?.next === null,
    searching: read.isFetching,
    failed: read.isError,
    loaded: read.isSuccess,
  };
}

export function RaiseScheduleStep(props: {
  form: RaiseForm;
  update: RaiseUpdate;
  /** The hours the chosen priority promises — the due date's help line. */
  slaHours: number | null;
  templateId: string;
  premisesId: string;
  unitIds: readonly string[];
  client?: ApiClient;
}) {
  const client = props.client ?? api;
  const { t } = useTranslation();
  const { dateFormat } = useRegional({});
  const { form, update } = props;
  const candidates = useRaiseCandidates(
    { templateId: props.templateId, premisesId: props.premisesId, unitIds: props.unitIds, on: form.visitDay },
    client,
  );

  return (
    <div className="flex flex-col gap-4" data-raise-step="schedule">
      <div className="max-w-xs">
        <DatePickerField
          id="raise-due"
          label={t("work.raise.due")}
          value={form.due}
          onChange={(value) => update({ due: value })}
          dateFormat={dateFormat}
          help={props.slaHours === null ? undefined : t("work.raise.dueHelp", { hours: props.slaHours })}
        />
      </div>

      <div className="flex flex-wrap items-start gap-2" data-raise-visit="">
        <div className="w-64">
          <DatePickerField
            id="raise-visit"
            label={t("work.raise.visit")}
            value={form.visitDay}
            onChange={(value) => update({ visitDay: value })}
            dateFormat={dateFormat}
            help={t("work.raise.visitHelp")}
          />
        </div>
        <div className="w-64 pt-6">
          <SelectField
            id="raise-window"
            label={t("work.raise.window")}
            labelHidden
            value={form.visitWindow}
            onChange={(value) => update({ visitWindow: value as RaiseForm["visitWindow"] })}
            options={[
              { value: "any", label: t("work.edit.window.any") },
              { value: "morning", label: t("work.edit.window.morning") },
              { value: "afternoon", label: t("work.edit.window.afternoon") },
            ]}
          />
        </div>
      </div>

      <CandidatePicker
        id="raise-assignee"
        label={t("work.raise.assignTo")}
        state={candidates}
        value={form.assignee?.id ?? ""}
        current={form.assignee}
        allowNobody
        placeholder={t("work.raise.assignNobody")}
        help={t("work.raise.assignHelp")}
        helpKey="raise-assignee"
        onPick={(candidate) =>
          update({ assignee: candidate === null ? null : { kind: candidate.kind, id: candidate.id, name: candidate.name } })
        }
      />
    </div>
  );
}
