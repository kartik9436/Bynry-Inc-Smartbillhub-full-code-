// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — the plan edit form's Review, built
//           from images 39, 41, 42 and 44 of
//           `05-prototype/plans-2026-10-03/images/` (B14 rule 42).
// Rules:    ruling 11 (Review draws the SAME sections as the details tabs —
//           `PlanSections`) · ruling 10 (the buttons; the page puts them in the
//           footer) · BR-RAT-1066 (a new version ends today's the day before) ·
//           BR-RAT-1016 verb 2 (a correction keeps the number and the window)
// ───────────────────────────────────────────────────────
//
// Top to bottom, as drawn:
//   *What changes*     every field that moved, before → after, or
//                      *Nothing changed yet.* (images 39, 41, 44);
//   the plan           the shared sections — *Edit* only where this choice
//                      can change something (image 39: Plan only; images 41
//                      and 44: every priced section, not Plan);
//   *Dates*            facts, or the new version's window, and the *Reason*;
//   *How it is saved*  the version rows as they will stand, and one note
//                      (images 41, 44; *Name and details* draws none).
//
// ⚠ **A CORRECTION KEEPS ITS NUMBER — THE DRAWING'S *v2 · correction* IS AN
// ILLUSTRATION (B14 rule 37).** `services.correct_plan_version` copies
// `version_no` from the row it corrects (`DEF-RAT-5710`, `OQ-RAT-12409` A), so
// the rows read *v1 · today — Superseded, kept* and *v1 · correction —
// Replaces v1*: the figure the server will actually write.
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import type { PlanSections as PlanSectionsData } from "@/api/planFormEndpoints";

import { PlanSections, REVIEW_SECTIONS, moneyShown, noteText } from "../planSections/PlanSections";
import type { PlanSectionId } from "../planSections/PlanSections";
import { EditDatesSection } from "./EditPlanSteps";
import { SECTION_STEP } from "./ReviewStep";
import { changedFields, dayBefore, dayText } from "./planEditModel";
import type { PlanEditMode } from "./planEditModel";
import { chargeOf, depositOf, discountOf, minimumBillDisplay, taxOf } from "./planFormModel";
import type { PlanFormDraft, PlanStepId } from "./planFormModel";
import { SECTION_HEADING, optionLabel } from "./planFormShared";
import type { PlanFormLists, PlanStepProps, Translator } from "./planFormShared";

const TABLE_FRAME = "border border-divider";
const HEAD_ROW = "bg-neutral-100";
const NOTE_INFO = "m-0 bg-info-100 px-3 py-3 text-base text-info-700";
const NOTE_WARN = "m-0 bg-warning-100 px-3 py-3 text-base text-warning-700";

/** Literal keys, so G18 can see each one used. */
const FIELD_LABELS: Partial<Record<keyof PlanFormDraft, string>> = {
  name: "rating.planSections.plan.name",
  code: "rating.planSections.plan.code",
  customer_classes: "rating.planSections.plan.classes",
  description: "rating.planSections.plan.description",
  intended_for: "rating.planSections.plan.intended",
  notes: "rating.planSections.plan.notes",
  services: "rating.planForm.section.services",
  outside_city: "rating.planSections.terms.surcharge",
  outside_city_percent: "rating.planSections.terms.surcharge",
  charge_codes: "rating.planSections.charges.title",
  taxes: "rating.planSections.taxes.title",
  deposits: "rating.planSections.deposits.title",
  discounts: "rating.planSections.discounts.title",
  budget_billing: "rating.planSections.terms.budget",
  minimum_bill: "rating.planSections.terms.minimum",
};

const INTENDED = ["cap_proof", "min_demand_25kw", "owner_occupied"] as const;

/** One field of the draft in words — the same words on both sides of a row. */
export function fieldWords(field: keyof PlanFormDraft, draft: PlanFormDraft, lists: PlanFormLists, t: Translator): string {
  const options = lists.options;
  const joined = (parts: string[]) => (parts.length === 0 ? t("rating.planSections.none") : parts.join(", "));
  switch (field) {
    case "customer_classes":
      return draft.customer_classes.length === 0
        ? t("rating.planForm.classes.every")
        : joined(draft.customer_classes.map((value) => optionLabel(options.customer_classes, value) || value));
    case "intended_for":
      return joined(INTENDED.filter((key) => draft.intended_for[key]).map((key) => t(`rating.planForm.intended.${key}`)));
    case "notes":
      return joined(
        draft.notes
          .filter((row) => row.attribute !== "" && row.value.trim() !== "")
          .map((row) => {
            const list = lists.noteAttributes.find((one) => one.key === row.attribute)?.values ?? [];
            return noteText(
              { attribute: row.attribute, operator: row.operator, value: optionLabel(list, row.value) || row.value },
              t,
            );
          }),
      );
    case "services":
      return joined(
        draft.services
          .filter((row) => row.service !== "")
          .map((row) => {
            const name = optionLabel(options.services, row.service) || row.service;
            const schedule = options.schedules.find((one) => one.ref.id === row.schedule)?.ref.name;
            return schedule === undefined ? name : `${name} · ${schedule}`;
          }),
      );
    case "outside_city":
    case "outside_city_percent": {
      if (draft.outside_city !== "yes" || draft.outside_city_percent.trim() === "") return t("rating.planSections.none");
      const names = draft.services
        .filter((row) => row.surcharged)
        .map((row) => optionLabel(options.services, row.service) || row.service);
      return t("rating.planSections.terms.surchargeOn", {
        percent: `${draft.outside_city_percent.trim()}%`,
        services: joined(names),
      });
    }
    case "charge_codes":
      return joined(draft.charge_codes.map((row) => chargeOf(options, row.value)?.ref.code ?? "").filter(Boolean));
    case "taxes":
      return joined(draft.taxes.map((row) => taxOf(options, row.value)?.ref.name ?? "").filter(Boolean));
    case "deposits":
      return joined(draft.deposits.map((row) => depositOf(options, row.value)?.ref.code ?? "").filter(Boolean));
    case "discounts":
      return joined(draft.discounts.map((row) => discountOf(options, row.discount)?.ref.code ?? "").filter(Boolean));
    case "budget_billing":
      return draft.budget_billing ? t("rating.planSections.terms.offered") : t("rating.planSections.terms.notOffered");
    case "minimum_bill": {
      // `DEF-RAT-9365` — money reads with its currency, as the summary panel
      // and the plan's sections draw it ($12.00, never 12.00; hard rule 2).
      const minimum = minimumBillDisplay(draft);
      return minimum === null ? t("rating.planSections.none") : moneyShown(minimum, lists.currency);
    }
    default: {
      const value = draft[field];
      return typeof value === "string" && value.trim() !== "" ? value.trim() : "—";
    }
  }
}

/** The rows of *What changes* — one per field that moved, never the new
 *  version's window (*How it is saved* states it). */
export function changedPlanRows(
  mode: PlanEditMode,
  isDraft: boolean,
  original: PlanFormDraft,
  draft: PlanFormDraft,
  lists: PlanFormLists,
  t: Translator,
): { id: string; label: string; before: string; after: string }[] {
  const seen = new Set<string>();
  return changedFields(mode, isDraft, original, draft)
    .filter((field) => field !== "effective_from" && field !== "effective_to")
    .flatMap((field) => {
      const labelKey = FIELD_LABELS[field];
      if (labelKey === undefined || seen.has(labelKey)) return [];
      seen.add(labelKey);
      return [{ id: field, label: t(labelKey), before: fieldWords(field, original, lists, t), after: fieldWords(field, draft, lists, t) }];
    });
}

export interface EditPlanReviewProps extends PlanStepProps {
  mode: PlanEditMode;
  original: PlanFormDraft;
  sections: PlanSectionsData;
  /** The version in force today and its window. */
  version: number;
  nextVersion: number;
  liveFrom: string;
  liveTo: string;
  /** Units on the plan today — *N units move to v2* (image 41). */
  units: number | null;
  reason: string;
  onReason: (reason: string) => void;
  onEdit: (step: PlanStepId) => void;
}

export function EditPlanReviewStep(props: EditPlanReviewProps) {
  const { mode, original, draft, lists, t } = props;
  const day = (value: string) => dayText(value, lists.timeZone, lists.dateFormat);
  const span = (from: string, to: string) => `${day(from)} – ${to === "" ? t("rating.planEdit.noEnd") : day(to)}`;
  const rows = changedPlanRows(mode, false, original, draft, lists, t);
  const v = props.version;
  const planEditable = mode === "info";
  const rest = REVIEW_SECTIONS.filter((id) => id !== "plan");
  const openSection = (section: PlanSectionId) => props.onEdit(SECTION_STEP[section]);

  const versions =
    mode === "change"
      ? [
          {
            id: "today",
            label: t("rating.planEdit.version.today", { v }),
            dates: span(
              props.liveFrom,
              draft.effective_from === "" ? props.liveTo : dayBefore(draft.effective_from),
            ),
            after: t("rating.planEdit.after.endDate"),
            strong: false,
          },
          {
            id: "next",
            label: t("rating.planEdit.version.new", { v: props.nextVersion }),
            dates: draft.effective_from === "" ? "—" : span(draft.effective_from, draft.effective_to),
            after: t("rating.planEdit.after.newVersion"),
            strong: true,
          },
        ]
      : mode === "correct"
        ? [
            {
              id: "today",
              label: t("rating.planEdit.version.today", { v }),
              dates: span(props.liveFrom, props.liveTo),
              after: t("rating.planEdit.after.superseded"),
              strong: false,
            },
            {
              id: "next",
              label: t("rating.planEdit.version.correction", { v }),
              dates: span(props.liveFrom, props.liveTo),
              after: t("rating.planEdit.after.replaces", { v }),
              strong: true,
            },
          ]
        : [];

  return (
    <div className="flex flex-col gap-5" data-plan-step="edit-review">
      <Panel as="section" aria-labelledby="plan-sec-changes">
        <h2 id="plan-sec-changes" className={SECTION_HEADING}>
          {t("rating.planEdit.section.changes")}
        </h2>
        {rows.length === 0 ? (
          <p className={NOTE_INFO} data-plan-change="none">
            {t("rating.planEdit.noChanges")}
          </p>
        ) : (
          <div className={TABLE_FRAME}>
            <PlainTable>
              <thead>
                <tr className={HEAD_ROW}>
                  <th scope="col">{t("rating.planEdit.col.field")}</th>
                  <th scope="col">{t("rating.planEdit.col.before")}</th>
                  <th scope="col">{t("rating.planEdit.col.after")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} data-plan-change={row.id}>
                    <td>{row.label}</td>
                    <td className="text-neutral-700">{row.before}</td>
                    <td className="font-semibold">{row.after}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
        )}
      </Panel>

      <PlanSections
        sections={props.sections}
        show={["plan"]}
        t={t}
        dateFormat={lists.dateFormat}
        timeZone={lists.timeZone}
        links={false}
        onEdit={planEditable ? openSection : undefined}
      />
      <PlanSections
        sections={props.sections}
        show={rest}
        t={t}
        dateFormat={lists.dateFormat}
        timeZone={lists.timeZone}
        links={false}
        onEdit={planEditable ? undefined : openSection}
      />

      <EditDatesSection
        {...props}
        mode={mode}
        liveFrom={props.liveFrom}
        liveTo={props.liveTo}
        reason={props.reason}
        onReason={props.onReason}
      />

      {versions.length > 0 && (
        <Panel as="section" aria-labelledby="plan-sec-saved-as">
          <h2 id="plan-sec-saved-as" className={SECTION_HEADING}>
            {t("rating.planEdit.section.saved")}
          </h2>
          <div className={TABLE_FRAME} data-plan-versions="">
            <PlainTable>
              <thead>
                <tr className={HEAD_ROW}>
                  <th scope="col">{t("rating.planEdit.col.version")}</th>
                  <th scope="col">{t("rating.planEdit.col.dates")}</th>
                  <th scope="col">{t("rating.planEdit.col.afterSaving")}</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((row) => (
                  <tr key={row.id} data-plan-version={row.id} className={row.strong ? "font-semibold" : undefined}>
                    <td>{row.label}</td>
                    <td className="tabular-nums">{row.dates}</td>
                    <td>{row.after}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
          {mode === "change" && draft.effective_from !== "" && props.units !== null && props.units > 0 && (
            <p className={`${NOTE_INFO} mt-4`} data-plan-saved-note="change">
              {t("rating.planEdit.note.unitsMove", {
                count: props.units,
                v: props.nextVersion,
                date: day(draft.effective_from),
              })}
            </p>
          )}
          {mode === "correct" && (
            <p className={`${NOTE_WARN} mt-4`} role="status" data-plan-saved-note="correct">
              {t("rating.planEdit.note.issuedKeep", { v })}
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}
