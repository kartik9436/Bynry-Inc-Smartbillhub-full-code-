// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — *Name and filing*, step *Name*, built from
//           image 24 of `05-prototype/taxes-fees-2026-10-03/images/`
//           (B14 rule 42).
// Defects:  DEF-RAT-9273 P46 (rate and reach are NOT editable on a live tax —
//           they are read here, locked, with the door that changes them)
// ───────────────────────────────────────────────────────
//
// Two sections: the name box, and *Rate and reach* READ — six facts and the
// lock note *Change with a new rate.* Nothing about rate or reach is a box on
// this step, so nothing about it can be typed and refused.
import { checkDropdownSummary } from "@/components/CheckDropdown";
import { formatDate } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import { TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { LockNote, PAIR, SECTION_HEADING, isLocked, labelOf, rateFigure, rateUnitKey } from "./taxFormShared";
import type { StepProps } from "./taxFormShared";

export function EditNameStep(props: StepProps) {
  const { draft, lists, t } = props;
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  const rate = rateFigure(draft);
  const facts = [
    { id: "authority", label: t("rating.taxForm.field.authority"), value: labelOf(lists.authorities, draft.jurisdiction) || "—" },
    { id: "boundary", label: t("rating.taxForm.field.boundary"), value: labelOf(lists.boundaries, draft.boundary) || "—" },
    {
      id: "services",
      label: t("rating.taxForm.field.services"),
      value: checkDropdownSummary(lists.services, draft.services, t("rating.taxForm.allServices")),
    },
    {
      id: "classes",
      label: t("rating.taxForm.field.classes"),
      value: checkDropdownSummary(lists.classes, draft.customer_classes, t("rating.taxForm.allClasses")),
    },
    { id: "rate", label: t("rating.taxForm.field.rate"), value: rate === null ? "—" : `${rate} ${t(rateUnitKey(draft))}` },
    {
      id: "dates",
      label: t("rating.taxEdit.facts.dates"),
      value: `${day(draft.effective_from)} – ${draft.effective_to === "" ? t("rating.taxForm.noEnd") : day(draft.effective_to)}`,
    },
  ];
  return (
    <div className="flex flex-col gap-5" data-tax-step="name">
      <Panel as="section" aria-labelledby="tax-sec-name">
        <h2 id="tax-sec-name" className={SECTION_HEADING}>
          {t("rating.taxEdit.section.name")}
        </h2>
        <div className={PAIR}>
          <TextField
            id="tax-name"
            label={t("rating.taxForm.field.name")}
            required
            value={draft.name}
            help={t("rating.taxForm.help.name")}
            disabled={isLocked(props, "name")}
            onChange={(name) => props.onChange({ name })}
          />
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="tax-sec-locked">
        <div className="mb-4 flex items-baseline justify-between gap-3">
          <h2 id="tax-sec-locked" className="m-0 font-heading text-h4">
            {t("rating.taxEdit.section.rateReach")}
          </h2>
          <LockNote>{t("rating.taxEdit.lock.rateReach")}</LockNote>
        </div>
        <FactBlock name="tax-rate-reach" variant="strip" columns={3} facts={facts} />
      </Panel>
    </div>
  );
}
