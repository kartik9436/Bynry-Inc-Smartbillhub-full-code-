// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — step 1 *Details*, built from images
//           04–07 of `05-prototype/plans-2026-10-03/images/` (B14 rule 42).
// Rules:    ruling 4 (*"Customer classes * - Drop down - all or multiple
//           selections"*: one tick dropdown, *Every customer class* first) ·
//           ruling 5 (intended-for: the three ticks AND the notes stay,
//           reminders only, never enforced — BR-RAT-043) · ruling 3 (the notes
//           are a table array) · DEF-RAT-9285 (a note names a class by NAME)
// ───────────────────────────────────────────────────────
//
// Two SECTIONS, each its own component so round 3's *Name and details* can
// mount them alone.
import { CheckDropdown } from "@/components/CheckDropdown";
import { CheckboxField, TextField, useFieldError } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { CellSelect, CellText, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";

import { ReadOnlyFact } from "../discountForm/DetailsStep";
import { NOTE_OPERATORS, newNoteRow } from "./planFormModel";
import type { PlanNoteRow } from "./planFormModel";
import { PAIR, SECTION_HEADING, isLocked } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";

export function DetailsStep(props: PlanStepProps) {
  return (
    <div className="flex flex-col gap-5" data-plan-step="details">
      <PlanSection {...props} />
      <IntendedForSection {...props} />
    </div>
  );
}

export function PlanSection(props: PlanStepProps) {
  const { draft, lists, t } = props;
  return (
    <Panel as="section" aria-labelledby="plan-sec-plan">
      <h2 id="plan-sec-plan" className={SECTION_HEADING}>
        {t("rating.planForm.section.plan")}
      </h2>
      <div className="flex flex-col gap-5">
        <div className={PAIR}>
          <TextField
            id="plan-name"
            label={t("rating.planForm.field.name")}
            required
            value={draft.name}
            placeholder={t("rating.planForm.placeholder.name")}
            help={t("rating.planForm.help.name")}
            readOnly={isLocked(props, "name")}
            onChange={(name) => props.onChange({ name })}
          />
          {isLocked(props, "code") ? (
            // Edit › *Name and details* draws the code as a fact (image 38):
            // one code names one plan (CR-167 round 3 task 8).
            <ReadOnlyFact id="plan-code" label={t("rating.planForm.field.code")} value={draft.code} />
          ) : (
            <TextField
              id="plan-code"
              label={t("rating.planForm.field.code")}
              required
              value={draft.code}
              placeholder={t("rating.planForm.placeholder.code")}
              onChange={(code) => props.onChange({ code })}
            />
          )}
        </div>
        <CheckDropdown
          id="plan-classes"
          label={t("rating.planForm.field.classes")}
          required
          allLabel={t("rating.planForm.classes.every")}
          options={lists.classOptions}
          selected={draft.customer_classes}
          disabled={isLocked(props, "customer_classes")}
          onChange={(customer_classes) => props.onChange({ customer_classes })}
        />
        <TextField
          id="plan-description"
          label={t("rating.planForm.field.description")}
          value={draft.description}
          placeholder={t("rating.planForm.placeholder.description")}
          help={t("rating.planForm.help.description")}
          readOnly={isLocked(props, "description")}
          onChange={(description) => props.onChange({ description })}
        />
      </div>
    </Panel>
  );
}

const INTENDED = ["cap_proof", "min_demand_25kw", "owner_occupied"] as const;

export function IntendedForSection(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const notesError = useFieldError("plan-notes");
  const locked = isLocked(props, "notes");
  const valuesFor = (attribute: string) => lists.noteAttributes.find((row) => row.key === attribute)?.values ?? [];

  function setRow(index: number, patch: Partial<PlanNoteRow>): void {
    props.onChange({ notes: draft.notes.map((row, i) => (i === index ? { ...row, ...patch } : row)) });
  }

  const columns: TableArrayColumn<PlanNoteRow>[] = [
    {
      key: "attribute",
      label: t("rating.planForm.col.attribute"),
      cell: (row, index) => (
        <CellSelect
          name="note-attribute"
          label={t("rating.planForm.col.attribute")}
          value={row.attribute}
          placeholder={t("rating.planForm.placeholder.choose")}
          options={lists.noteAttributes.map((option) => ({ value: option.key, label: option.label }))}
          onChange={(attribute) => setRow(index, { attribute, value: "" })}
        />
      ),
    },
    {
      key: "operator",
      label: t("rating.planForm.col.operator"),
      cell: (row, index) => (
        <CellSelect
          name="note-operator"
          label={t("rating.planForm.col.operator")}
          value={row.operator}
          placeholder={t("rating.planForm.placeholder.choose")}
          options={NOTE_OPERATORS.map((value) => ({ value, label: t(`rating.plan.eligibility.operator.${value}`) }))}
          onChange={(operator) => setRow(index, { operator })}
        />
      ),
    },
    {
      key: "value",
      label: t("rating.planForm.col.value"),
      cell: (row, index) => {
        const values = valuesFor(row.attribute);
        return values.length > 0 ? (
          <CellSelect
            name="note-value"
            label={t("rating.planForm.col.value")}
            value={row.value}
            placeholder={t("rating.planForm.placeholder.choose")}
            options={values}
            onChange={(value) => setRow(index, { value })}
          />
        ) : (
          <CellText
            name="note-value"
            label={t("rating.planForm.col.value")}
            value={row.value}
            blockedReason={row.attribute === "" ? t("rating.planForm.reason.attributeFirst") : undefined}
            onChange={(value) => setRow(index, { value })}
          />
        );
      },
    },
  ];

  return (
    <TableArray<PlanNoteRow>
      title={t("rating.planForm.section.intended")}
      collection="plan-notes"
      lead={
        <div className="flex flex-wrap gap-x-8 gap-y-2" data-plan-intended="">
          {INTENDED.map((key) => (
            <CheckboxField
              key={key}
              id={`plan-intended-${key}`}
              label={t(`rating.planForm.intended.${key}`)}
              checked={draft.intended_for[key]}
              disabled={isLocked(props, "intended_for")}
              onChange={(checked) => props.onChange({ intended_for: { ...draft.intended_for, [key]: checked } })}
            />
          ))}
        </div>
      }
      columns={columns}
      rows={draft.notes}
      rowKey={(row) => row.key}
      emptyText={t("rating.planForm.none")}
      note={notesError}
      onChange={(notes) => props.onChange({ notes })}
      removeLabel={t("rating.planForm.remove")}
      actions={
        locked
          ? []
          : [
              {
                key: "add-note",
                label: t("rating.planForm.add.note"),
                onClick: () => props.onChange({ notes: [...draft.notes, newNoteRow()] }),
              },
            ]
      }
    />
  );
}
