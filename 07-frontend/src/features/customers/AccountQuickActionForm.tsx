// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-003 (POST /accounts/{id}/activate — BR-CUS-018's resume half)
//           Screens: S21 · S22
// Change:   CR-094-BRC01 step 2 wave J — `ACC-S14`: *"Every quick action on an
//           account opens as a form over the account, with all of its fields
//           and a recap before it commits."*
// Rules:    BR-CUS-018 (activate a draft) · BR-SHL-025 (a control this
//           deployment cannot honour renders DISABLED WITH ITS REASON) ·
//           B14 rule 11 (a consequence preview before a commit that changes
//           service state) · B14 rule 33 (on-screen text capped by what it is
//           for) · B14 rule 38 (the UI rules win on how a form is BUILT) ·
//           B14 rule 39 (label → input → helper, field → field 20px)
// Tests:    AccountQuickActionForm.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ONE COMPONENT, THIRTEEN FORMS
// ══════════════════════════════════════════════════════════════════════════
// Everything that differs between the thirteen quick actions is a row in
// `accountQuickActions.ts`. This file renders any of them and knows about none
// of them by name — the one exception is `submit`, which has to speak to a real
// endpoint, and which therefore takes the write as a prop rather than choosing
// one.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THE DRAWING LOSES, AND IT IS B14 RULE 38 BY NAME
// ══════════════════════════════════════════════════════════════════════════
// Rule 38 lists the disagreements this exact drawing has with the kit and rules
// every one of them for the kit, **naming two of them verbatim**:
//
//   · R4 lays every section out as TWO COLUMNS of fields.       → ONE column.
//   · R4 puts `Save & exit` on the LEFT of the footer.          → kit footer.
//   · R4 draws a `✕` close and a header sub-line.               → `ModalShell`.
//
// *"So the drawing loses, the divergence is RECORDED in the conformance file,
// and nothing is built for it."* It is recorded in
// `04-docs/05-modules/03-customers/conformance/CR-094-wave-J-quick-actions-step2.md` §4.
//
// **What the drawing still decides and what is taken from it unchanged:** which
// fields, in which order, under which headings, with which helper sentence, and
// which rows the recap reads back. That is rule 38's own last clause.
//
// ⚠ **THE SECTION HEADING IS NOT A KIT COMPONENT AND DELIBERATELY SO.** One
// component renders it — this one — so putting it in `components/` would claim
// a shared decision nobody else has made yet. `RecapBox` went to the kit
// instead, because this repo already holds THREE private answers to that one
// shape and a fourth is how a product stops looking like one product.
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DatePickerField, FieldStack, FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { RecapBox } from "@/components/RecapBox";
import type { RecapRow } from "@/components/RecapBox";

import type { QuickForm, QuickRecapSource, QuickSection } from "./accountQuickActions";

/** The facts the recap reads back, resolved by the caller from the account the
 *  form is open over.
 *
 *  ⚠ **EVERY ONE IS `string | null` AND `null` MEANS ABSENT, NEVER EMPTY.** A
 *  recap that prints a blank where a plan should be reads as *"no plan"*, and
 *  on `ACC-Q03` that is the difference between an account that inherits a
 *  tariff and one that will not bill. The renderer prints the absence sentence
 *  the caller supplies, never a dash it invented. */
export interface QuickRecapFacts {
  statusName: string | null;
  openedAt: string | null;
  unitPlan: string | null;
  outcomeSentence: string | null;
}

export interface AccountQuickActionFormProps {
  form: QuickForm;
  /** `ModalShell`'s sub-line — the account this is open over, so a clerk who
   *  opened it from the wrong row can see that before they commit. */
  kicker: string;
  facts: QuickRecapFacts;
  /** Tenant Regional format, REQUIRED like every other date control's. An
   *  optional one nothing passed would render the browser's locale and pass
   *  every test (hard-won law 2). */
  dateFormat: RegionalDateFormat;
  /** Today in the tenant's timezone, as the date field's proposed default. */
  today: string;
  /** The write. Receives exactly the values the form collected, keyed by the
   *  server's own field names. */
  onSubmit: (values: Record<string, string>) => Promise<FormSubmitOutcome>;
  onClose: () => void;
  /** What a missing fact prints — one catalogue string, supplied rather than
   *  chosen here, because the sentence differs per action. */
  absentText: string;
}

/** The red caps heading R4 draws above each group of fields. */
function SectionHeading(props: { children: ReactNode }) {
  return (
    <p
      className="m-0 mb-4 border-b border-b-divider pb-2 text-xs font-bold uppercase tracking-tag text-accent"
      data-quick-section=""
    >
      {props.children}
    </p>
  );
}

/**
 * The zod schema, built from the configuration rather than hand-written per
 * action — so a field marked `required` in one place cannot be optional in the
 * other. `FormModal` validates against this before it calls `onSubmit`.
 */
function schemaFor(form: QuickForm) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const section of form.sections) {
    for (const field of section.fields) {
      if (field.kind === "readonly") {
        continue; // nothing is collected, so nothing is validated
      }
      shape[field.id] =
        field.required === true ? z.string().min(1) : z.string().optional();
    }
  }
  return z.object(shape);
}

/** The values a form starts holding — the date fields prefilled with today, the
 *  rest empty. Read-only fields hold nothing because they send nothing. */
function initialValues(form: QuickForm, today: string): Record<string, string> {
  const values: Record<string, string> = {};
  for (const section of form.sections) {
    for (const field of section.fields) {
      if (field.kind === "date") {
        values[field.id] = today;
      }
    }
  }
  return values;
}

export function AccountQuickActionForm(props: AccountQuickActionFormProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState(() => initialValues(props.form, props.today));

  function set(id: string, value: string) {
    setValues((previous) => ({ ...previous, [id]: value }));
  }

  function factFor(source: QuickRecapSource): ReactNode {
    const value = props.facts[source];
    return value === null ? props.absentText : value;
  }

  /**
   * The value a recap row reads back.
   *
   * A row naming a `fromField` reads the LIVE form state, so changing the date
   * above moves the recap below it — which is the whole of *"reads back a
   * recap"*. A date is rendered through `formatDate`, the ONE formatting path
   * (BR-SHL-023), so the recap and the echo under the input cannot disagree
   * about what day it is.
   */
  function rowValue(row: { source?: QuickRecapSource; fromField?: string }): ReactNode {
    if (row.fromField === undefined) {
      // ⚠ A row with NEITHER is a configuration mistake, not an absent value,
      // and it prints the absence sentence rather than throwing — a recap that
      // crashes takes the whole dialog with it, and the clerk loses what they
      // typed. `accountQuickActions.test.ts` is where such a row is caught.
      return row.source === undefined ? props.absentText : factFor(row.source);
    }
    const typed = values[row.fromField] ?? "";
    if (typed === "") {
      return props.absentText;
    }
    return formatDate(typed, "UTC", props.dateFormat);
  }

  const recapRows: RecapRow[] = props.form.recapRows.map((row) => ({
    label: t(row.labelKey),
    value: rowValue(row),
    testId: row.source,
  }));

  return (
    <FormModal
      title={t(props.form.titleKey)}
      kicker={props.kicker}
      schema={schemaFor(props.form)}
      values={values}
      submitLabel={t(props.form.commitLabelKey)}
      commitBlocked={
        props.form.commitBlockedKey === undefined
          ? undefined
          : t(props.form.commitBlockedKey)
      }
      onSubmit={() => props.onSubmit(values)}
      onClose={props.onClose}
    >
      {/* B14 rule 33: a CONSEQUENCE before an irreversible act is six words a
          sentence, at most two — and the RATIONALE for it is zero words on
          screen, which is why the reasoning lives in this file's header. */}
      {props.form.leadKey !== undefined && (
        <p className="mb-4 text-sm text-neutral-700" data-quick-lead="">
          {t(props.form.leadKey)}
        </p>
      )}

      {props.form.sections.map((section: QuickSection) => (
        <div className="mb-6" key={section.headingKey} data-quick-group={section.headingKey}>
          <SectionHeading>{t(section.headingKey)}</SectionHeading>
          {/* ⚠ `FieldStack` AND NOT A GRID — it is the kit's own 20px field →
              field rhythm (B14 rule 39 as amended 2026-09-12, *"20 everywhere
              — the anatomy wins"*), and it is the ONE column rule 38 settles
              against the drawing's two. */}
          <FieldStack>
            {section.fields.map((field) => {
              if (field.kind === "readonly") {
                // A fact, not an input. It is rendered as a field so it keeps
                // the label → value → helper rhythm of the boxes around it,
                // and as a `<p>` rather than a disabled `<input>` because a
                // disabled input invites a clerk to try to type in it.
                return (
                  <div className="field" key={field.id}>
                    <label className="block" htmlFor={`${field.id}-value`}>
                      {t(field.labelKey)}
                    </label>
                    <p
                      className="m-0 mt-[5px] text-sm font-semibold text-neutral-900"
                      id={`${field.id}-value`}
                      data-quick-readonly={field.id}
                    >
                      {factFor("unitPlan")}
                    </p>
                    {field.helpKey !== undefined && (
                      <p className="field-help mt-1.5">{t(field.helpKey)}</p>
                    )}
                  </div>
                );
              }
              return (
                <DatePickerField
                  key={field.id}
                  id={field.id}
                  label={t(field.labelKey)}
                  value={values[field.id] ?? ""}
                  onChange={(value) => set(field.id, value)}
                  prefill={props.today}
                  dateFormat={props.dateFormat}
                  required={field.required === true}
                  help={field.helpKey === undefined ? undefined : t(field.helpKey)}
                />
              );
            })}
          </FieldStack>
        </div>
      ))}

      <SectionHeading>{t("customers.account.quick.section.review")}</SectionHeading>
      <RecapBox
        title={t(props.form.recapTitleKey)}
        rows={recapRows}
        outcome={
          props.form.recapOutcome === undefined
            ? undefined
            : {
                label: t(props.form.recapOutcome.labelKey),
                value: rowValue(props.form.recapOutcome),
                testId: props.form.recapOutcome.source,
              }
        }
        data-recap="quick-action"
      >
        {/* R4's own box — *"Two things the server will not manage, and says so
            now rather than after"*. It is COMPOSED from the kit's
            `ConsequenceBox`, not re-implemented: two shapes under one name is
            what DEF-CWP-3655 cost. */}
        {props.form.caveatHeadingKey !== undefined &&
          props.form.caveatBulletKeys !== undefined && (
            <ConsequenceBox
              heading={t(props.form.caveatHeadingKey)}
              bullets={props.form.caveatBulletKeys.map((key) => t(key))}
            />
          )}
      </RecapBox>
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave J · ACC-S14 (accounts blueprint p208) · R4 p154–174 · 14-ui-conventions.md rules 11, 33, 38, 39
// generated: 2026-09-12 by the CR-094 wave J build lane
// checklist: A✔ B✔ C✔ D✔(POST /accounts/{id}/activate) E✔(AccountDetailPage opens it) F✔ G✔ H=n/a
// gates: tsc · vitest AccountQuickActionForm.dom.test.tsx · routeBUtilities (listed on src/styles/route-b-migrated.txt)
// exceptions: E3 the readonly branch resolves its value from `facts.unitPlan` rather than from a per-field source, because ACC-Q03 is the only wired form and it has exactly one readonly field; widening that to a lookup before a second caller exists would be an unused code path (LAW 0) · E3 R4's two-column layout and its left-hand `Save & exit` are NOT built — B14 rule 38 names both verbatim as form CONSTRUCTION where the UI rules win
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
