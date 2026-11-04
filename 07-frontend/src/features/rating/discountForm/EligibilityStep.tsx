// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — step 2 *Eligibility*, built from
//           images 15–16 of `05-prototype/discounts-2026-10-03/images/` (B14
//           rule 42).
// Defects:  DEF-RAT-9289 D7 (no "Available, not granted. Saving enrolls
//           nobody." under the heading) · D10 (no explanations under headings)
//           · D11 (who qualifies is a dropdown, not a text area)
// Rules:    ruling 3 (PO 2026-10-03): *"A 'customer shows proof' condition
//           cannot be Automatic"* · decision log 2026-10-03, the 31-box map:
//           *Who qualifies* and *Dates and budget*
// ───────────────────────────────────────────────────────
import { AffixField } from "@/components/AffixField";
import { formatDate } from "@/components/DateCell";
import { CheckboxField, DatePickerField, SelectField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { ENROLLMENT_AUTOMATIC, isProofCondition } from "./discountFormModel";
import { ReadOnlyFact } from "./DetailsStep";
import { PAIR, SECTION_HEADING, isLocked } from "./discountFormShared";
import type { DiscountStepProps } from "./discountFormShared";

export function EligibilityStep(props: DiscountStepProps & { startsLockedHelp?: string }) {
  return (
    <div className="flex flex-col gap-5" data-discount-step="eligibility">
      <WhoQualifiesSection {...props} />
      <DatesBudgetSection {...props} />
    </div>
  );
}

export function WhoQualifiesSection(props: DiscountStepProps) {
  const { draft, lists, t } = props;
  const proof = isProofCondition(draft, lists.eligibility);
  const asOption = (row: { value: string; label: string }) => ({ value: row.value, label: row.label });
  const system = lists.eligibility.filter((row) => row.checked_by === "system").map(asOption);
  const shown = lists.eligibility.filter((row) => row.checked_by === "proof").map(asOption);
  return (
    <Panel as="section" aria-labelledby="discount-sec-who">
      <h2 id="discount-sec-who" className={SECTION_HEADING}>
        {t("rating.discountForm.section.who")}
      </h2>
      <div className="flex flex-col gap-5">
        <SelectField
          id="discount-who"
          label={t("rating.discountForm.field.who")}
          required
          value={draft.eligibility}
          placeholder={t("rating.discountForm.placeholder.choose")}
          options={[]}
          groups={[
            { label: t("rating.discountForm.group.system"), options: system },
            { label: t("rating.discountForm.group.proof"), options: shown },
          ].filter((group) => group.options.length > 0)}
          help={t("rating.discountForm.help.who")}
          disabled={isLocked(props, "eligibility")}
          onChange={(eligibility) => props.onChange({ eligibility })}
        />
        <div className={PAIR}>
          {/* RULING 3 — Automatic is OFFERED only under a condition the system
              checks. Under a proof condition it is drawn and cannot be picked;
              a draft already holding the pair is marked, never silently
              changed (the form keeps what the clerk chose). */}
          <SelectField
            id="discount-enrollment"
            label={t("rating.discountForm.field.enrollment")}
            value={draft.enrolment_mode}
            options={lists.enrollmentModes.map((row) => ({
              value: row.value,
              label: row.label,
              disabled: proof && row.value === ENROLLMENT_AUTOMATIC,
            }))}
            disabled={isLocked(props, "enrolment_mode")}
            onChange={(enrolment_mode) => props.onChange({ enrolment_mode })}
          />
          <SelectField
            id="discount-verification"
            label={t("rating.discountForm.field.verification")}
            value={draft.verification_method}
            options={lists.verification}
            help={t("rating.discountForm.help.verification")}
            disabled={isLocked(props, "verification_method")}
            onChange={(verification_method) => props.onChange({ verification_method })}
          />
        </div>
        {/* Only a condition the customer proves has a proof to wait for. */}
        {proof && (
          <CheckboxField
            id="discount-proof-before"
            label={t("rating.discountForm.field.proofBefore")}
            checked={draft.proof_before_first_reduction}
            disabled={isLocked(props, "proof_before_first_reduction")}
            onChange={(proof_before_first_reduction) => props.onChange({ proof_before_first_reduction })}
          />
        )}
        <div className={PAIR}>
          <AffixField
            id="discount-recertify"
            label={t("rating.discountForm.field.recertify")}
            value={draft.recertification_months}
            affix={t("rating.discountForm.unit.months")}
            side="end"
            help={t("rating.discountForm.help.recertify")}
            disabled={isLocked(props, "recertification_months")}
            onChange={(recertification_months) => props.onChange({ recertification_months })}
          />
          <SelectField
            id="discount-lapse"
            label={t("rating.discountForm.field.lapse")}
            value={draft.lapse_behaviour}
            options={lists.lapse}
            disabled={isLocked(props, "lapse_behaviour")}
            onChange={(lapse_behaviour) => props.onChange({ lapse_behaviour })}
          />
          <AffixField
            id="discount-notice"
            label={t("rating.discountForm.field.notice")}
            value={draft.recertification_notice_days}
            affix={t("rating.discountForm.unit.days")}
            side="end"
            disabled={isLocked(props, "recertification_notice_days")}
            onChange={(recertification_notice_days) => props.onChange({ recertification_notice_days })}
          />
          <AffixField
            id="discount-grace"
            label={t("rating.discountForm.field.grace")}
            value={draft.recertification_grace_days}
            affix={t("rating.discountForm.unit.days")}
            side="end"
            disabled={isLocked(props, "recertification_grace_days")}
            onChange={(recertification_grace_days) => props.onChange({ recertification_grace_days })}
          />
        </div>
      </div>
    </Panel>
  );
}

export function DatesBudgetSection(props: DiscountStepProps & { startsLockedHelp?: string }) {
  const { draft, lists, t } = props;
  return (
    <Panel as="section" aria-labelledby="discount-sec-dates">
      <h2 id="discount-sec-dates" className={SECTION_HEADING}>
        {t("rating.discountForm.section.dates")}
      </h2>
      <div className="flex flex-col gap-5">
        <div className={PAIR}>
          {/* Locked on a live discount's *Name and details* (image 28): the
              start is a fact, and the help names the door that moves it. */}
          {isLocked(props, "effective_from") ? (
            <ReadOnlyFact
              id="discount-starts"
              label={t("rating.discountForm.field.starts")}
              value={draft.effective_from === "" ? "—" : formatDate(draft.effective_from, lists.timeZone, lists.dateFormat)}
              help={props.startsLockedHelp}
            />
          ) : (
            <DatePickerField
              id="discount-starts"
              label={t("rating.discountForm.field.starts")}
              required
              value={draft.effective_from}
              dateFormat={lists.dateFormat}
              onChange={(effective_from) => props.onChange({ effective_from })}
            />
          )}
          <DatePickerField
            id="discount-ends"
            label={t("rating.discountForm.field.ends")}
            value={draft.effective_to}
            dateFormat={lists.dateFormat}
            help={t("rating.discountForm.help.ends")}
            disabled={isLocked(props, "effective_to")}
            onChange={(effective_to) => props.onChange({ effective_to })}
          />
          <AffixField
            id="discount-budget"
            label={t("rating.discountForm.field.budgetCap")}
            value={draft.budget_cap}
            affix="$"
            side="start"
            help={t("rating.discountForm.help.budget")}
            disabled={isLocked(props, "budget_cap")}
            onChange={(budget_cap) => props.onChange({ budget_cap })}
          />
          <SelectField
            id="discount-budget-period"
            label={t("rating.discountForm.field.budgetPeriod")}
            value={draft.budget_period}
            options={lists.budgetPeriods}
            disabled={isLocked(props, "budget_period")}
            onChange={(budget_period) => props.onChange({ budget_period })}
          />
        </div>
        <SelectField
          id="discount-budget-out"
          label={t("rating.discountForm.field.budgetOut")}
          value={draft.exhaustion_behaviour}
          options={lists.budgetOut}
          disabled={isLocked(props, "exhaustion_behaviour")}
          onChange={(exhaustion_behaviour) => props.onChange({ exhaustion_behaviour })}
        />
      </div>
    </Panel>
  );
}
