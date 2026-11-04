// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — step 3 *Filing*, built from images 13–14 of
//           `05-prototype/taxes-fees-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9277 P19 (code, bill label and filing are taken at
//           creation) · P20 (Due and Account with the authority are dropdowns)
//           · DEF-RAT-10027 (PO 2026-10-09, option (a): the field is the tax
//           registration number with the authority — *Tax registration no.*;
//           the chosen one is said back under it; with none held, the note
//           names the authority and *Add one* opens Tax filing accounts)
// Rules:    PO ruling 2026-10-03, README point 3 (*"Filing is taken during
//           creation (step 3) … Due and Account with the authority are
//           dropdowns; the accounts come from Settings › Accounting"*) ·
//           CR-165 §7 item 2 (the liability account is CHOSEN here from the
//           chart; it is still edited only in Settings — CR-008)
// ───────────────────────────────────────────────────────
import { Link } from "react-router-dom";

import { AffixField } from "@/components/AffixField";
import { SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { PAIR, SECTION_HEADING, isLocked, labelOf } from "./taxFormShared";
import type { StepProps } from "./taxFormShared";

export function FilingStep(props: StepProps) {
  const { draft, lists, t } = props;
  const chosenNumber = labelOf(lists.authorityAccounts, draft.authority_account_id);
  return (
    <div className="flex flex-col gap-5" data-tax-step="filing">
      <Panel as="section" aria-labelledby="tax-sec-bill">
        <h2 id="tax-sec-bill" className={SECTION_HEADING}>
          {t("rating.taxForm.section.onBill")}
        </h2>
        <div className={PAIR}>
          <TextField
            id="tax-code"
            label={t("rating.taxForm.field.code")}
            value={draft.code}
            help={t("rating.taxForm.help.code")}
            disabled={isLocked(props, "code")}
            onChange={(code) => props.onChange({ code })}
          />
          <TextField
            id="tax-bill-label"
            label={t("rating.taxForm.field.billLabel")}
            value={draft.bill_label}
            placeholder={draft.name.trim() === "" ? undefined : draft.name.trim()}
            help={t("rating.taxForm.help.billLabel")}
            disabled={isLocked(props, "bill_label")}
            onChange={(bill_label) => props.onChange({ bill_label })}
          />
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="tax-sec-filing">
        <h2 id="tax-sec-filing" className={SECTION_HEADING}>
          {t("rating.taxForm.section.filing")}
        </h2>
        <div className="flex flex-col gap-5">
          <div className={PAIR}>
            <SelectField
              id="tax-liability"
              label={t("rating.taxForm.field.liability")}
              required
              value={draft.liability_gl_account_id}
              placeholder={t("rating.taxForm.placeholder.liability")}
              options={lists.liabilityAccounts}
              help={
                // A live tax's liability account is changed in Settings ›
                // Accounting only (PO 2026-10-03 on CR-008); the edit form
                // locks the box and says where its door is.
                isLocked(props, "liability_gl_account_id")
                  ? t("rating.taxEdit.help.liabilityLocked")
                  : t("rating.taxForm.help.liability")
              }
              disabled={isLocked(props, "liability_gl_account_id")}
              onChange={(liability_gl_account_id) => props.onChange({ liability_gl_account_id })}
            />
            <SelectField
              id="tax-filed"
              label={t("rating.taxForm.field.filed")}
              value={draft.filing_frequency}
              options={lists.filingFrequencies}
              disabled={isLocked(props, "filing_frequency")}
              onChange={(filing_frequency) => props.onChange({ filing_frequency })}
            />
          </div>
          <div className={PAIR}>
            <SelectField
              id="tax-due"
              label={t("rating.taxForm.field.due")}
              value={draft.due_date_rule}
              placeholder={t("rating.taxForm.placeholder.due")}
              options={lists.dueRules}
              disabled={isLocked(props, "due_date_rule")}
              onChange={(due_date_rule) => props.onChange({ due_date_rule })}
            />
            <div>
              <SelectField
                id="tax-authority-account"
                label={t("rating.taxForm.field.authorityAccount")}
                value={draft.authority_account_id}
                placeholder={t("rating.taxForm.placeholder.authorityAccount")}
                options={lists.authorityAccounts}
                disabled={isLocked(props, "authority_account_id")}
                onChange={(authority_account_id) => props.onChange({ authority_account_id })}
              />
              {chosenNumber !== "" ? (
                // DEF-RAT-10027 — the chosen authority and number, said back.
                <p className="field-help mt-1.5 mb-0 font-semibold" data-tax-authority-account-chosen="">
                  {chosenNumber}
                </p>
              ) : (
                <p className="field-help mt-1.5 mb-0" data-tax-add-account="">
                  {lists.authorityAccountsHeld > 0
                    ? t("rating.taxForm.help.authorityAccount")
                    : lists.authorityName !== ""
                      ? t("rating.taxForm.help.authorityAccountNone", { authority: lists.authorityName })
                      : t("rating.taxForm.help.authorityAccountNoneYet")}{" "}
                  <Link
                    to={lists.authorityAccountsHref}
                    className="font-heading font-semibold text-accent-700 underline"
                  >
                    {t("rating.taxForm.addOne")}
                  </Link>
                </p>
              )}
            </div>
          </div>
          <div className={PAIR}>
            <AffixField
              id="tax-allowance"
              label={t("rating.taxForm.field.allowance")}
              value={draft.allowance_percent}
              affix="%"
              side="end"
              disabled={isLocked(props, "allowance_percent")}
              onChange={(allowance_percent) => props.onChange({ allowance_percent })}
            />
            <AffixField
              id="tax-interest"
              label={t("rating.taxForm.field.interest")}
              value={draft.interest_percent}
              affix={t("rating.taxForm.perMonth")}
              side="end"
              disabled={isLocked(props, "interest_percent")}
              onChange={(interest_percent) => props.onChange({ interest_percent })}
            />
          </div>
          <TextField
            id="tax-reminder"
            label={t("rating.taxForm.field.reminder")}
            value={draft.filing_reminder_recipient}
            disabled={isLocked(props, "filing_reminder_recipient")}
            onChange={(filing_reminder_recipient) => props.onChange({ filing_reminder_recipient })}
          />
        </div>
      </Panel>
    </div>
  );
}
