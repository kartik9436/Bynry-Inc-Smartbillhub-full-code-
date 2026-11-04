// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — step 1 *Details*, built from images
//           05–14 of `05-prototype/discounts-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9289 D1 (three steps, not five) · D3/D6 (no "type the
//           amount exactly…" and no "blank means uncapped" paragraphs — one
//           short help line per box) · D4 (currency is the utility's, shown,
//           never typed) · D5 (caps and stacking in ONE section, closed by
//           default) · D8 (the code's help is an example, not a rule) · D12/D13
//           (exclusivity group and program owner are dropdowns)
// Rules:    decision log 2026-10-03, the 31-box map: Basics · Value · Limits
// ───────────────────────────────────────────────────────
//
// Three SECTIONS, each its own component so round 3's edit variations can
// mount any one of them alone (*New value from a date* is the Value section;
// *Name and details* is Basics with Value and Limits locked).
import { useState } from "react";

import { AffixField } from "@/components/AffixField";
import { CheckDropdown } from "@/components/CheckDropdown";
import { CheckboxField, FieldLabel, SelectField, TextField, useFieldError } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import {
  LIMIT_BOXES,
  SCOPE_NAMED_CODES,
  SCOPE_ONE_SERVICE,
  SCOPE_SPECIFIC_SERVICES,
  TYPE_ALLOWANCE,
  effectiveType,
  limitsSetCount,
  offeredTypes,
  valueBoxFor,
} from "./discountFormModel";
import { PAIR, SECTION_HEADING, currencyLine, isLocked, labelOf, typeOptionLabel } from "./discountFormShared";
import type { DiscountStepProps } from "./discountFormShared";

export function DetailsStep(props: DiscountStepProps) {
  return (
    <div className="flex flex-col gap-5" data-discount-step="details">
      <BasicsSection {...props} />
      <ValueSection {...props} />
      <LimitsSection {...props} />
    </div>
  );
}

export function BasicsSection(props: DiscountStepProps) {
  const { draft, lists, t } = props;
  return (
    <Panel as="section" aria-labelledby="discount-sec-basics">
      <h2 id="discount-sec-basics" className={SECTION_HEADING}>
        {t("rating.discountForm.section.basics")}
      </h2>
      <div className={PAIR}>
        {/* A LOCKED field is drawn as a FACT, never as a greyed box (the PO's
            *"we dont display it like this at other places"*, FactBlock's
            reason) — the Edit form's code and type (image 27). */}
        {isLocked(props, "code") ? (
          <ReadOnlyFact id="discount-code" label={t("rating.discountForm.field.code")} value={draft.code || "—"} />
        ) : (
          <TextField
            id="discount-code"
            label={t("rating.discountForm.field.code")}
            required
            value={draft.code}
            placeholder={t("rating.discountForm.placeholder.code")}
            help={t("rating.discountForm.help.code")}
            onChange={(code) => props.onChange({ code })}
          />
        )}
        <TextField
          id="discount-label"
          label={t("rating.discountForm.field.label")}
          required
          value={draft.name}
          placeholder={t("rating.discountForm.placeholder.label")}
          help={t("rating.discountForm.help.label")}
          disabled={isLocked(props, "name")}
          onChange={(name) => props.onChange({ name })}
        />
        <SelectField
          id="discount-owner"
          label={t("rating.discountForm.field.owner")}
          value={draft.program_owner}
          placeholder={t("rating.discountForm.placeholder.choose")}
          options={lists.programOwners}
          disabled={isLocked(props, "program_owner")}
          onChange={(program_owner) => props.onChange({ program_owner })}
        />
        {/* Drawn as a dropdown (image 05); the contract has no funding list
            (CR-166 §6 a: it stays free text), so it is a box until one exists. */}
        <TextField
          id="discount-funding"
          label={t("rating.discountForm.field.funding")}
          value={draft.funding_source}
          placeholder={t("rating.discountForm.placeholder.funding")}
          disabled={isLocked(props, "funding_source")}
          onChange={(funding_source) => props.onChange({ funding_source })}
        />
        {/* PO ruling 2026-10-03 (decision log, option b): a usage allowance is
            not OFFERED until free units come off the reading before pricing
            (BR-RAT-962). The server still serves the type, so a draft saved
            before the ruling reads its own type here as a fact; nothing else
            can choose it, and the server refuses it by name if sent. */}
        {isLocked(props, "discount_type") || draft.discount_type === TYPE_ALLOWANCE ? (
          <ReadOnlyFact
            id="discount-type"
            label={t("rating.discountForm.field.type")}
            value={labelOf(lists.types, draft.discount_type) || "—"}
          />
        ) : (
          <SelectField
            id="discount-type"
            label={t("rating.discountForm.field.type")}
            required
            value={draft.discount_type}
            options={offeredTypes(lists.types).map((option) => ({ value: option.value, label: typeOptionLabel(option, t) }))}
            onChange={(discount_type) => props.onChange({ discount_type, value: "" })}
          />
        )}
        <div className="flex items-end pb-2.5">
          <CheckboxField
            id="discount-assistance"
            label={t("rating.discountForm.field.assistance")}
            checked={draft.report_in_assistance_filing}
            disabled={isLocked(props, "report_in_assistance_filing")}
            onChange={(report_in_assistance_filing) => props.onChange({ report_in_assistance_filing })}
          />
        </div>
      </div>
    </Panel>
  );
}

export function ValueSection(props: DiscountStepProps) {
  const { draft, lists, t } = props;
  const box = valueBoxFor(effectiveType(draft));
  const valueLocked = isLocked(props, "value");
  return (
    <Panel as="section" aria-labelledby="discount-sec-value">
      <h2 id="discount-sec-value" className={SECTION_HEADING}>
        {t("rating.discountForm.section.value")}
      </h2>
      <div className="flex flex-col gap-5">
        <div className={PAIR}>
          {box === "percent" && (
            <AffixField
              id="discount-value"
              label={t("rating.discountForm.field.percentOff")}
              required
              value={draft.value}
              affix="%"
              side="end"
              placeholder="15"
              help={t("rating.discountForm.help.percent")}
              disabled={valueLocked}
              onChange={(value) => props.onChange({ value })}
            />
          )}
          {box === "money" && (
            <AffixField
              id="discount-value"
              label={t("rating.discountForm.field.amountOff")}
              required
              value={draft.value}
              affix="$"
              side="start"
              disabled={valueLocked}
              onChange={(value) => props.onChange({ value })}
            />
          )}
          {box === "units" && (
            <AffixField
              id="discount-value"
              label={t("rating.discountForm.field.freeUnits")}
              required
              value={draft.value}
              affix={lists.allowanceUnit ?? t("rating.discountForm.unit.units")}
              side="end"
              disabled={valueLocked}
              onChange={(value) => props.onChange({ value })}
            />
          )}
          {box === "schedule" && (
            // Image 08 draws *Bill from schedule*. BR-RAT-961 (PO 2026-08-31)
            // ruled the schedule-swap mechanism away and no column holds a
            // schedule, so the box is drawn and cannot act (BR-SHL-025) rather
            // than taking a choice nothing would keep. CR-166 §11.
            <SelectField
              id="discount-value"
              label={t("rating.discountForm.field.schedule")}
              value=""
              placeholder={t("rating.discountForm.placeholder.schedule")}
              options={[]}
              disabled
              onChange={() => undefined}
            />
          )}
          {box === "whole" && (
            <ReadOnlyFact
              id="discount-value"
              label={t("rating.discountForm.field.amountOff")}
              value={t("rating.discountForm.wholeCharge")}
            />
          )}
          <ReadOnlyFact
            id="discount-currency"
            label={t("rating.discountForm.field.currency")}
            value={currencyLine(lists.currency, lists.language)}
            help={t("rating.discountForm.help.currency")}
          />
        </div>
        <div className={PAIR}>
          <SelectField
            id="discount-applies"
            label={t("rating.discountForm.field.appliesTo")}
            value={draft.applies_to}
            options={lists.appliesTo}
            disabled={isLocked(props, "applies_to")}
            onChange={(applies_to) => props.onChange({ applies_to })}
          />
          {draft.applies_to === SCOPE_ONE_SERVICE && (
            <SelectField
              id="discount-service"
              label={t("rating.discountForm.field.service")}
              required
              value={draft.applies_to_service}
              placeholder={t("rating.discountForm.placeholder.choose")}
              options={lists.services.map((row) => ({ value: row.value, label: row.label }))}
              disabled={isLocked(props, "applies_to_service")}
              onChange={(applies_to_service) => props.onChange({ applies_to_service })}
            />
          )}
          {draft.applies_to === SCOPE_SPECIFIC_SERVICES && (
            <CheckDropdown
              id="discount-services"
              label={t("rating.discountForm.field.services")}
              required
              mode="pick"
              allLabel=""
              placeholder={t("rating.discountForm.placeholder.choose")}
              options={lists.services}
              selected={draft.applies_to_services}
              disabled={isLocked(props, "applies_to_services")}
              onChange={(applies_to_services) => props.onChange({ applies_to_services })}
            />
          )}
        </div>
        {draft.applies_to === SCOPE_NAMED_CODES && (
          <CheckDropdown
            id="discount-codes"
            label={t("rating.discountForm.field.codes")}
            required
            mode="pick"
            allLabel=""
            placeholder={t("rating.discountForm.placeholder.choose")}
            options={lists.chargeCodes}
            selected={draft.applies_to_charge_codes}
            disabled={isLocked(props, "applies_to_charge_codes")}
            onChange={(applies_to_charge_codes) => props.onChange({ applies_to_charge_codes })}
          />
        )}
      </div>
    </Panel>
  );
}

/**
 * D5 — caps, floor, stacking and exclusivity in ONE section, CLOSED by default
 * and reading *No limits* or *N set* (images 05–07). A box marked by a refusal
 * opens it, so a marked box is never hidden behind its summary.
 */
export function LimitsSection(props: DiscountStepProps) {
  const { draft, lists, t } = props;
  const [open, setOpen] = useState(false);
  const marked = useLimitMarked();
  const shown = open || marked;
  const count = limitsSetCount(draft);
  return (
    <Panel as="section" aria-labelledby="discount-sec-limits" data-discount-limits={shown ? "open" : "closed"}>
      <button
        type="button"
        className="flex w-full cursor-pointer items-center justify-between gap-3 border-0 bg-transparent p-0 text-left"
        aria-expanded={shown}
        aria-controls="discount-limits-body"
        onClick={() => setOpen((was) => !was)}
      >
        <h2 id="discount-sec-limits" className="m-0 font-heading text-h4">
          {t("rating.discountForm.section.limits")}
        </h2>
        <span className="text-base text-neutral-700" data-discount-limits-count={count}>
          {count === 0 ? t("rating.discountForm.limits.none") : t("rating.discountForm.limits.set", { count })}{" "}
          <span aria-hidden="true">▾</span>
        </span>
      </button>
      {shown && (
        <div id="discount-limits-body" className="mt-4 flex flex-col gap-5 border-t border-divider pt-5">
          <div className={PAIR}>
            <AffixField
              id="discount-cap-bill"
              label={t("rating.discountForm.field.capBill")}
              value={draft.cap_per_bill}
              affix="$"
              side="start"
              help={t("rating.discountForm.help.noCap")}
              disabled={isLocked(props, "cap_per_bill")}
              onChange={(cap_per_bill) => props.onChange({ cap_per_bill })}
            />
            <AffixField
              id="discount-cap-year"
              label={t("rating.discountForm.field.capYear")}
              value={draft.cap_per_year}
              affix="$"
              side="start"
              help={t("rating.discountForm.help.noCap")}
              disabled={isLocked(props, "cap_per_year")}
              onChange={(cap_per_year) => props.onChange({ cap_per_year })}
            />
            <AffixField
              id="discount-cap-lifetime"
              label={t("rating.discountForm.field.capLifetime")}
              value={draft.cap_lifetime}
              affix="$"
              side="start"
              help={t("rating.discountForm.help.noCap")}
              disabled={isLocked(props, "cap_lifetime")}
              onChange={(cap_lifetime) => props.onChange({ cap_lifetime })}
            />
            <AffixField
              id="discount-floor"
              label={t("rating.discountForm.field.floor")}
              value={draft.bill_floor_amount}
              affix="$"
              side="start"
              help={t("rating.discountForm.help.floor")}
              disabled={isLocked(props, "bill_floor_amount")}
              onChange={(bill_floor_amount) => props.onChange({ bill_floor_amount })}
            />
            <TextField
              id="discount-stacking"
              label={t("rating.discountForm.field.stacking")}
              numeric
              value={draft.stacking_precedence}
              help={t("rating.discountForm.help.stacking")}
              disabled={isLocked(props, "stacking_precedence")}
              onChange={(stacking_precedence) => props.onChange({ stacking_precedence })}
            />
            <SelectField
              id="discount-exclusivity"
              label={t("rating.discountForm.field.exclusivity")}
              value={draft.exclusivity_group}
              placeholder={lists.exclusivityGroups.length === 0 ? t("rating.discountForm.placeholder.choose") : undefined}
              options={lists.exclusivityGroups}
              help={t("rating.discountForm.help.exclusivity")}
              disabled={isLocked(props, "exclusivity_group")}
              onChange={(exclusivity_group) => props.onChange({ exclusivity_group })}
            />
          </div>
          <CheckboxField
            id="discount-stacks"
            label={t("rating.discountForm.field.stacks")}
            checked={draft.stacks_with_others}
            disabled={isLocked(props, "stacks_with_others")}
            onChange={(stacks_with_others) => props.onChange({ stacks_with_others })}
          />
        </div>
      )}
    </Panel>
  );
}

/** Whether any box inside Limits is marked right now — read off the same
 *  error scope every box reads, one hook per box (never a hook in a loop). */
function useLimitMarked(): boolean {
  const marks = [
    useFieldError(LIMIT_BOXES[0]),
    useFieldError(LIMIT_BOXES[1]),
    useFieldError(LIMIT_BOXES[2]),
    useFieldError(LIMIT_BOXES[3]),
    useFieldError(LIMIT_BOXES[4]),
    useFieldError(LIMIT_BOXES[5]),
    useFieldError(LIMIT_BOXES[6]),
  ];
  return marks.some((mark) => mark !== undefined);
}

/** A value shown, never typed — the currency (PO 2026-10-03: *"user cannot
 *  change it"*) and a charge waiver's *The whole charge*. */
export function ReadOnlyFact(props: { id: string; label: string; value: string; help?: string }) {
  return (
    <div className="field" data-read-only-fact={props.id}>
      <FieldLabel id={`${props.id}-label`} label={props.label} required={false} />
      <p
        id={props.id}
        className="m-0 py-2.5 font-heading text-md font-semibold"
        aria-labelledby={`${props.id}-label`}
      >
        {props.value}
      </p>
      {props.help !== undefined && <p className="field-help mt-1.5 mb-0">{props.help}</p>}
    </div>
  );
}
