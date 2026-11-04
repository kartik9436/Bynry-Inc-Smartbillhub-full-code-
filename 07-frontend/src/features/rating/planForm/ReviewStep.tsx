// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — step 5 *Review*, built from images
//           20–21 of `05-prototype/plans-2026-10-03/images/` (B14 rule 42).
// Rules:    ruling 9 (Review is TABLES) · ruling 11 (the SAME sections the
//           details tabs draw — `PlanSections`, mounted here first) · ruling 10
//           (Review ends *Save as draft* · *Publish plan*; the page puts them in
//           the footer) · ruling 14 (no *Try a bill*)
// ───────────────────────────────────────────────────────
import { DatePickerField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import type { PlanSections as PlanSectionsData } from "@/api/planFormEndpoints";

import { PlanSections, REVIEW_SECTIONS } from "../planSections/PlanSections";
import type { PlanSectionId } from "../planSections/PlanSections";
import { PAIR, SECTION_HEADING, isLocked } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";
import type { PlanStepId } from "./planFormModel";

/** Which step a section's *Edit* opens. */
export const SECTION_STEP: Readonly<Record<PlanSectionId, PlanStepId>> = {
  plan: "details",
  services: "services",
  servicesTotals: "services",
  charges: "charges",
  taxes: "charges",
  deposits: "billing",
  discounts: "billing",
  billingTerms: "billing",
};

export function ReviewStep(
  props: PlanStepProps & { sections: PlanSectionsData; onEdit: (step: PlanStepId) => void },
) {
  const { draft, lists, t } = props;
  return (
    <div className="flex flex-col gap-5" data-plan-step="review">
      <PlanSections
        sections={props.sections}
        show={REVIEW_SECTIONS}
        t={t}
        dateFormat={lists.dateFormat}
        timeZone={lists.timeZone}
        links={false}
        onEdit={(section) => props.onEdit(SECTION_STEP[section])}
      />
      <Panel as="section" aria-labelledby="plan-sec-dates">
        <h2 id="plan-sec-dates" className={SECTION_HEADING}>
          {t("rating.planForm.section.dates")}
        </h2>
        <div className={PAIR}>
          <DatePickerField
            id="plan-starts"
            label={t("rating.planForm.field.starts")}
            required
            value={draft.effective_from}
            dateFormat={lists.dateFormat}
            disabled={isLocked(props, "effective_from")}
            onChange={(effective_from) => props.onChange({ effective_from })}
          />
          <DatePickerField
            id="plan-ends"
            label={t("rating.planForm.field.ends")}
            value={draft.effective_to}
            dateFormat={lists.dateFormat}
            help={t("rating.planForm.help.ends")}
            disabled={isLocked(props, "effective_to")}
            onChange={(effective_to) => props.onChange({ effective_to })}
          />
        </div>
      </Panel>
    </div>
  );
}
