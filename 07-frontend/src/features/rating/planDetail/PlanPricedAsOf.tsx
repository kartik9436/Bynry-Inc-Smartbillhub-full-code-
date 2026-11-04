// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — ruling 13's *"Priced as of" a date*
//           (images 26–30; image 28 reads water v5 on 01/15/2027), with *Today*,
//           and on Services the *Expand all* / *Collapse all* toggle.
// Rules:    BR-SHL-011 (the date is URL state — `?as_of=`) · B14 rule 7 (a date
//           field is the kit's date input) · rule 44 (the kit's field, label
//           above the box, where the drawing puts it beside)
// ───────────────────────────────────────────────────────
import { DatePickerField } from "@/components/FormModal";

import type { PlanRegional, Translator } from "./planDetailModel";

export function PlanPricedAsOf(props: {
  value: string;
  today: string;
  onChange: (value: string) => void;
  /** Services only — *Expand all* opens every service, *Collapse all* folds them. */
  expand?: { allOpen: boolean; onToggle: () => void };
  regional: PlanRegional;
  t: Translator;
}) {
  const { t } = props;
  return (
    <div className="flex items-end justify-between gap-4" data-plan-as-of="">
      <div className="w-80">
        <DatePickerField
          id="plan-priced-as-of"
          label={t("rating.planDetail.asOf")}
          value={props.value}
          onChange={props.onChange}
          dateFormat={props.regional.dateFormat}
          regional
          todayValue={props.today}
        />
      </div>
      {props.expand !== undefined && (
        <button
          type="button"
          className="mb-2 whitespace-nowrap bg-transparent p-0 font-semibold text-accent underline hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          aria-expanded={props.expand.allOpen}
          onClick={props.expand.onToggle}
          data-plan-expand-all=""
        >
          {props.expand.allOpen ? t("rating.planDetail.collapseAll") : t("rating.planDetail.expandAll")}{" "}
          <span aria-hidden="true">{props.expand.allOpen ? "▴" : "▾"}</span>
        </button>
      )}
    </div>
  );
}
