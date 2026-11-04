// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — step 2 *How much*, built from images 09–12
//           of `05-prototype/taxes-fees-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9277 P8 (the rate is TYPED as a percent) · P9 (over 20 %
//           warns) · P10 (Charged as and Rate side by side) · P11 (the two
//           ticks have room) · P12/P15 (no sentence repeating the heading) ·
//           P13 (the discount example is a table of one $60.00 bill) · P14
//           (rounding has no "leave blank") · P16 (exemptions are a link)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import { AffixField } from "@/components/AffixField";
import { formatDate } from "@/components/DateCell";
import { CheckboxField, DatePickerField, SelectField, TextField, useFieldError } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { FieldError } from "@/components/StateFrame";
import { PlainTable } from "@/components/Surfaces";

import {
  BASIS_PERCENT,
  BASIS_PER_UNIT,
  effectiveBasis,
  exampleBill,
  percentIsHigh,
} from "./taxFormModel";
import { LockNote, MONEY_COLUMNS, PAIR, SECTION_HEADING, isLocked, rateFigure } from "./taxFormShared";
import type { StepProps } from "./taxFormShared";

/**
 * The edit variations' changes to this step (CR-165 task 7, images 28–33) —
 * every one optional, so the New form mounts it exactly as before.
 *
 * `dates.lockedNote` — both dates locked: they are READ, not boxes (image 31,
 * *Fix a mistake*: *"Same dates as today."*). `dates.fromLabel`/`fromHelp` —
 * *New rate starts* and *Today's rate ends 10/31/2026.* (image 28).
 * `afterDates` — the *Reason* section *Fix a mistake* adds under the dates.
 */
export interface HowMuchStepProps extends StepProps {
  dates?: { fromLabel?: string; fromHelp?: string; lockedNote?: string };
  afterDates?: ReactNode;
}

export function HowMuchStep(props: HowMuchStepProps) {
  const { draft, lists, t } = props;
  const basis = effectiveBasis(draft);
  const percent = basis === BASIS_PERCENT;
  const high = percent && percentIsHigh(draft.rate_percent);
  const bill = exampleBill(draft);
  const rateLocked = isLocked(props, "rate_percent");
  const datesRead =
    props.dates?.lockedNote !== undefined && isLocked(props, "effective_from") && isLocked(props, "effective_to");
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  return (
    <div className="flex flex-col gap-5" data-tax-step="much">
      <Panel as="section" aria-labelledby="tax-sec-rate">
        <h2 id="tax-sec-rate" className={SECTION_HEADING}>
          {t("rating.taxForm.section.rate")}
        </h2>
        <div className="flex flex-col gap-5">
          <div className={PAIR}>
            <SelectField
              id="tax-basis"
              label={t("rating.taxForm.field.basis")}
              value={draft.basis}
              options={lists.bases}
              disabled={isLocked(props, "basis")}
              onChange={(next) => props.onChange({ basis: next })}
            />
            {percent ? (
              <AffixField
                id="tax-rate"
                label={t("rating.taxForm.field.rate")}
                required
                value={draft.rate_percent}
                affix="%"
                side="end"
                tone={high ? "warning" : "plain"}
                help={
                  high
                    ? t("rating.taxForm.rateHigh", { rate: rateFigure(draft) })
                    : t("rating.taxForm.help.ratePercent")
                }
                disabled={rateLocked}
                onChange={(rate_percent) => props.onChange({ rate_percent })}
              />
            ) : (
              <AffixField
                id="tax-rate"
                label={t("rating.taxForm.field.rate")}
                required
                value={draft.amount}
                affix="$"
                side="start"
                help={t("rating.taxForm.help.rateAmount")}
                disabled={rateLocked}
                onChange={(amount) => props.onChange({ amount })}
              />
            )}
          </div>
          {basis === BASIS_PER_UNIT && (
            <div className={PAIR}>
              <span />
              <TextField
                id="tax-uom"
                label={t("rating.taxForm.field.uom")}
                required
                value={draft.per_unit_uom}
                disabled={isLocked(props, "per_unit_uom")}
                onChange={(per_unit_uom) => props.onChange({ per_unit_uom })}
              />
            </div>
          )}
          {percent && (
            <fieldset className="m-0 border-0 p-0" id="tax-taxed" aria-describedby="tax-taxed-error">
              <legend className="mb-3 p-0 text-sm text-neutral-700">
                {t("rating.taxForm.field.taxed")}
                <span className="field-required" aria-hidden="true">*</span>
              </legend>
              <div className="flex flex-wrap gap-x-8 gap-y-2">
                <CheckboxField
                  id="tax-taxed-usage"
                  label={t("rating.taxForm.taxed.usage")}
                  checked={draft.base_includes_usage}
                  disabled={isLocked(props, "base_includes_usage")}
                  onChange={(base_includes_usage) => props.onChange({ base_includes_usage })}
                />
                <CheckboxField
                  id="tax-taxed-base"
                  label={t("rating.taxForm.taxed.base")}
                  checked={draft.base_includes_base}
                  disabled={isLocked(props, "base_includes_base")}
                  onChange={(base_includes_base) => props.onChange({ base_includes_base })}
                />
              </div>
              <TaxedError />
            </fieldset>
          )}
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="tax-sec-dates">
        <div className="mb-4 flex items-baseline justify-between gap-3">
          <h2 id="tax-sec-dates" className="m-0 font-heading text-h4">
            {t("rating.taxForm.section.dates")}
          </h2>
          {datesRead && <LockNote>{props.dates?.lockedNote}</LockNote>}
        </div>
        {datesRead ? (
          <dl className={`m-0 ${PAIR}`} data-tax-dates="locked">
            <div>
              <dt className="field-label">{t("rating.taxForm.field.from")}</dt>
              <dd className="m-0 mt-3 font-semibold tabular-nums">{day(draft.effective_from)}</dd>
            </div>
            <div>
              <dt className="field-label">{t("rating.taxForm.field.to")}</dt>
              <dd className="m-0 mt-3 font-semibold tabular-nums">
                {draft.effective_to === "" ? t("rating.taxForm.noEnd") : day(draft.effective_to)}
              </dd>
            </div>
          </dl>
        ) : (
          <div className={PAIR}>
            <DatePickerField
              id="tax-from"
              label={props.dates?.fromLabel ?? t("rating.taxForm.field.from")}
              required
              value={draft.effective_from}
              dateFormat={lists.dateFormat}
              help={props.dates?.fromHelp ?? t("rating.taxForm.help.from")}
              disabled={isLocked(props, "effective_from")}
              onChange={(effective_from) => props.onChange({ effective_from })}
            />
            <DatePickerField
              id="tax-to"
              label={t("rating.taxForm.field.to")}
              value={draft.effective_to}
              dateFormat={lists.dateFormat}
              help={t("rating.taxForm.help.to")}
              disabled={isLocked(props, "effective_to")}
              onChange={(effective_to) => props.onChange({ effective_to })}
            />
          </div>
        )}
      </Panel>

      {props.afterDates}

      <Panel as="section" aria-labelledby="tax-sec-discounts">
        <h2 id="tax-sec-discounts" className={SECTION_HEADING}>
          {t("rating.taxForm.section.discounts")}
        </h2>
        <div className="flex flex-col gap-5">
          <div className={PAIR}>
            <SelectField
              id="tax-discounts"
              label={t("rating.taxForm.field.discounts")}
              value={draft.discount_treatment}
              options={lists.discounts}
              disabled={isLocked(props, "discount_treatment")}
              onChange={(discount_treatment) => props.onChange({ discount_treatment })}
            />
            <SelectField
              id="tax-rounding"
              label={t("rating.taxForm.field.rounding")}
              value={draft.rounding_rule}
              options={lists.rounding}
              help={t("rating.taxForm.help.rounding")}
              disabled={isLocked(props, "rounding_rule")}
              onChange={(rounding_rule) => props.onChange({ rounding_rule })}
            />
          </div>
          {percent && (
            <div className="border border-divider" data-tax-example="discounts">
              <PlainTable className={MONEY_COLUMNS}>
                <thead>
                  <tr className="bg-neutral-100">
                    <th scope="col">{t("rating.taxForm.example.col.bill")}</th>
                    <th scope="col">{t("rating.taxForm.example.col.full")}</th>
                    <th scope="col">{t("rating.taxForm.example.col.after")}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{t("rating.taxForm.example.charges")}</td>
                    <td className="tabular-nums">${bill.taxedFull}</td>
                    <td className="tabular-nums">${bill.taxedFull}</td>
                  </tr>
                  <tr>
                    <td>{t("rating.taxForm.example.discount")}</td>
                    <td>—</td>
                    <td className="tabular-nums">−${bill.discount}</td>
                  </tr>
                  <tr>
                    <td>{t("rating.taxForm.example.taxed")}</td>
                    <td className="tabular-nums">${bill.taxedFull}</td>
                    <td className="tabular-nums">${bill.taxedAfterDiscount}</td>
                  </tr>
                  <tr className="bg-neutral-100 font-semibold">
                    <td>{t("rating.taxForm.example.taxAt", { rate: rateFigure(draft) ?? "—" })}</td>
                    <td className="tabular-nums">{bill.taxFull === null ? "—" : `$${bill.taxFull}`}</td>
                    <td className="tabular-nums">
                      {bill.taxAfterDiscount === null ? "—" : `$${bill.taxAfterDiscount}`}
                    </td>
                  </tr>
                </tbody>
              </PlainTable>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}

/** The "what is taxed" refusal reads off the same error scope as every box. */
function TaxedError() {
  const error = useFieldError("tax-taxed");
  return error === undefined ? null : <FieldError id="tax-taxed-error" message={error} />;
}
