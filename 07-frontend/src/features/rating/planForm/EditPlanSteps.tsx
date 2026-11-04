// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — the pieces only the plan EDIT form
//           has, built from images 38–44 of
//           `05-prototype/plans-2026-10-03/images/` (B14 rule 42). Every box in
//           them is the New form's own section component (rule 43); this file
//           adds only what the New form never draws.
// ───────────────────────────────────────────────────────
//
//   EditInfoDetailsStep  image 38 — *Plan* (the code a fact) + *Intended for* +
//                        *Services, charges and billing* READ, locked,
//                        *🔒 Change from a date.*
//   EditDatesSection     image 41 — *New version starts* * and *Ends*, with
//                        the day today's version ends; image 44 — the dates
//                        as facts (a correction keeps the window); image 39 —
//                        a live plan's dates as facts
//   ReasonField          images 41, 42, 44 — *Reason* *, *Shown in Audit.*
import { formatDate } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import { DatePickerField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { ReadOnlyFact } from "../discountForm/DetailsStep";
import { LockNote } from "../discountForm/discountFormShared";
import { IntendedForSection, PlanSection } from "./DetailsStep";
import { dayBefore } from "./planEditModel";
import type { PlanEditMode } from "./planEditModel";
import { optionLabel, PAIR, SECTION_HEADING } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";

/** *Services, charges and billing*, READ — three facts and the door that
 *  changes them (image 38). */
export function PricedFactsLocked(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const services = draft.services
    .map((row) => optionLabel(lists.options.services, row.service) || row.service)
    .filter((name) => name !== "");
  const facts = [
    {
      id: "services",
      label: t("rating.planEdit.facts.services"),
      value: services.length === 0 ? "—" : services.join(", "),
    },
    {
      id: "charges",
      label: t("rating.planEdit.facts.chargesTaxes"),
      value: `${draft.charge_codes.length} · ${draft.taxes.length}`,
    },
    { id: "discounts", label: t("rating.planEdit.facts.discounts"), value: String(draft.discounts.length) },
  ];
  return (
    <Panel as="section" aria-labelledby="plan-sec-priced-locked">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 id="plan-sec-priced-locked" className="m-0 font-heading text-h4">
          {t("rating.planEdit.section.priced")}
        </h2>
        <LockNote>{t("rating.planEdit.lock.priced")}</LockNote>
      </div>
      <FactBlock name="plan-priced-locked" variant="strip" columns={3} facts={facts} />
    </Panel>
  );
}

/** Step 1 of *Name and details* on a live plan (image 38). */
export function EditInfoDetailsStep(props: PlanStepProps) {
  return (
    <div className="flex flex-col gap-5" data-plan-step="edit-details">
      <PlanSection {...props} />
      <IntendedForSection {...props} />
      <PricedFactsLocked {...props} />
    </div>
  );
}

/** *Reason* * — why this change or this fix (images 41, 44). */
export function ReasonField(props: { reason: string; onReason: (reason: string) => void; t: PlanStepProps["t"] }) {
  const { t } = props;
  return (
    <TextField
      id="plan-reason"
      label={t("rating.planEdit.field.reason")}
      required
      value={props.reason}
      placeholder={t("rating.planEdit.placeholder.reason")}
      help={t("rating.planEdit.help.reason")}
      onChange={props.onReason}
    />
  );
}

/** Review's *Dates* for an edit: a new window (change), the same window as
 *  facts (correct, live info), or a draft's own boxes (the New form's). */
export function EditDatesSection(
  props: PlanStepProps & {
    mode: PlanEditMode;
    /** The window of the version in force. */
    liveFrom: string;
    liveTo: string;
    reason: string;
    onReason: (reason: string) => void;
  },
) {
  const { draft, lists, t, mode } = props;
  const day = (value: string) => formatDate(value, lists.timeZone, lists.dateFormat);
  const facts = mode !== "change";
  // A start on or before today's start is refused, so "today's version ends
  // 12/31/2026" would describe a save that cannot happen (the tax form's rule).
  const startsHelp =
    draft.effective_from === "" || draft.effective_from <= props.liveFrom
      ? t("rating.planEdit.help.newFrom")
      : t("rating.planEdit.help.todayEnds", { date: day(dayBefore(draft.effective_from)) });
  return (
    <Panel as="section" aria-labelledby="plan-sec-dates">
      <h2 id="plan-sec-dates" className={SECTION_HEADING}>
        {t("rating.planForm.section.dates")}
      </h2>
      <div className="flex flex-col gap-5">
        {facts ? (
          <div className={PAIR}>
            <ReadOnlyFact
              id="plan-starts"
              label={t("rating.planForm.field.starts")}
              value={props.liveFrom === "" ? "—" : day(props.liveFrom)}
            />
            <ReadOnlyFact
              id="plan-ends"
              label={t("rating.planForm.field.ends")}
              value={props.liveTo === "" ? t("rating.planEdit.noEnd") : day(props.liveTo)}
            />
          </div>
        ) : (
          <div className={PAIR}>
            <DatePickerField
              id="plan-starts"
              label={t("rating.planEdit.field.newFrom")}
              required
              value={draft.effective_from}
              dateFormat={lists.dateFormat}
              help={startsHelp}
              onChange={(effective_from) => props.onChange({ effective_from })}
            />
            <DatePickerField
              id="plan-ends"
              label={t("rating.planForm.field.ends")}
              value={draft.effective_to}
              dateFormat={lists.dateFormat}
              help={t("rating.planForm.help.ends")}
              onChange={(effective_to) => props.onChange({ effective_to })}
            />
          </div>
        )}
        {mode !== "info" && <ReasonField reason={props.reason} onReason={props.onReason} t={t} />}
      </div>
    </Panel>
  );
}
