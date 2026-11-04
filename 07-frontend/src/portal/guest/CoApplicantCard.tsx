// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-10250 — the portal had no co-applicant (decision log
//           2026-10-18, *"Portal apply asks no SSN/licence and has no
//           co-applicant"*); image 04-portal.png draws the tick panel and the
//           folding card: full name, relationship, phone, email, date of birth.
// Rules:    B14 rule 43 (a component, not code inside a page) · rule 44 · rule
//           31 (no id on screen) · rule 33 · the portal's accessibility
//           questions (labels, errors tied to inputs, keyboard, 44px targets)
// Tests:    src/portal/guest/AboutYouMoveInFields.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { FocusEvent } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { RELATIONSHIPS } from "@/features/customers/CoOwnerCards";

import { FormField, SelectInput, TextInput, TwoUp, fieldErrorId } from "../components/primitives";
import { FormSection, ThreeUp } from "../components/FormSection";
import { PortalDateField } from "../components/PortalDateField";

/** The card's five fields, as the draft names them. */
export interface CoApplicantValue {
  on: boolean;
  name: string;
  relationship: string;
  phone: string;
  email: string;
  date_of_birth: string;
}

export function coApplicantFromDraft(draft: {
  co_applicant?: boolean;
  co_applicant_name?: string | null;
  co_applicant_relationship?: string | null;
  co_applicant_phone?: string | null;
  co_applicant_email?: string | null;
  co_applicant_date_of_birth?: string | null;
} | null): CoApplicantValue {
  return {
    on: draft?.co_applicant === true,
    name: draft?.co_applicant_name ?? "",
    relationship: draft?.co_applicant_relationship ?? "",
    phone: draft?.co_applicant_phone ?? "",
    email: draft?.co_applicant_email ?? "",
    date_of_birth: draft?.co_applicant_date_of_birth ?? "",
  };
}

/** The draft's own field names, ready to save. */
export function coApplicantPayload(value: CoApplicantValue): Record<string, unknown> {
  return {
    co_applicant: value.on,
    co_applicant_name: value.name.trim() || null,
    co_applicant_relationship: value.relationship.trim() || null,
    co_applicant_phone: value.phone.trim() || null,
    co_applicant_email: value.email.trim() || null,
    co_applicant_date_of_birth: value.date_of_birth || null,
  };
}

/** The server's rule (`missing_before_submit` → `co_applicant`): a ticked
 *  card must name the person. */
export function coApplicantIsComplete(value: CoApplicantValue): boolean {
  return !value.on || value.name.trim() !== "";
}

/**
 * *Someone else on the account* — the tick panel and the one folding card.
 *
 * ⚠ **ONE CARD, NOT A LIST.** Move-in's co-owner panel holds several; the
 * portal drawing draws one co-applicant and the request has one set of
 * co-applicant columns, so a second card would be typing nobody keeps.
 */
export function CoApplicantCard(props: {
  value: CoApplicantValue;
  onChange: (next: CoApplicantValue) => void;
  /** A part was LEFT, or the tick changed — the moment to save. */
  onCommit: (next: CoApplicantValue) => void;
  /** Refusals from the server, keyed by the draft's field name. */
  errors?: Partial<Record<"co_applicant_phone" | "co_applicant_email", string>>;
  /** Today, `YYYY-MM-DD` — a date of birth is never later. */
  today?: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(true);
  const value = props.value;
  const set = (part: Partial<CoApplicantValue>): CoApplicantValue => {
    const next = { ...value, ...part };
    props.onChange(next);
    return next;
  };
  // The DOM's value, never React's — `DEF-CWP-3705`'s reason.
  const leave = (part: keyof CoApplicantValue) => (event: FocusEvent<HTMLElement>) => {
    const typed = (event.target as HTMLInputElement | null)?.value;
    props.onCommit(typed === undefined ? value : { ...value, [part]: typed });
  };
  // DEF-CUS-10257 — the relationship is Move-in's CODE; the summary names it.
  const relationshipLabel = (RELATIONSHIPS as readonly string[]).includes(value.relationship)
    ? t(`customers.moveIn.customer.relationship.${value.relationship}`)
    : "";
  const summary = [relationshipLabel, value.phone.trim()].filter(Boolean).join(" · ");
  const nameMissing = value.on && value.name.trim() === "";
  return (
    <FormSection
      title={t("portal.apply.coApplicant.title")}
      testId="co-applicant"
      tick={{
        id: "co_applicant",
        label: t("portal.apply.coApplicant.tick"),
        checked: value.on,
        onChange: (checked) => props.onCommit(set({ on: checked })),
      }}
    >
      {value.on ? (
        <div className="flex flex-col border border-neutral-200" data-co-applicant-card="">
          <button
            type="button"
            className="flex min-h-11 w-full items-center gap-3 bg-[white] px-3 text-left"
            aria-expanded={open}
            aria-controls="co-applicant-fields"
            data-co-applicant-toggle=""
            onClick={() => setOpen((was) => !was)}
          >
            <span className="text-body font-semibold text-neutral-900">
              {value.name.trim() || t("portal.apply.coApplicant.unnamed")}
            </span>
            {summary !== "" ? <span className="text-base text-neutral-600">{summary}</span> : null}
            <span className="ml-auto text-neutral-900" aria-hidden="true">
              {open ? "▼" : "▶"}
            </span>
          </button>
          {open ? (
            <div id="co-applicant-fields" className="flex flex-col gap-3 px-3 pb-3">
              <TwoUp>
                <FormField
                  id="co_applicant_name"
                  label={t("portal.apply.coApplicant.fullName")}
                  required
                  error={nameMissing ? t("portal.apply.held.coApplicant") : null}
                >
                  <span onBlur={leave("name")}>
                    <TextInput
                      id="co_applicant_name"
                      value={value.name}
                      required
                      invalid={nameMissing}
                      describedBy={fieldErrorId("co_applicant_name")}
                      autoComplete="off"
                      onChange={(name) => set({ name })}
                    />
                  </span>
                </FormField>
                {/* ⊕ DEF-CUS-10257 — Move-in's own four (`RELATIONSHIPS`), in
                    Move-in's own words. Free text reached Move-in's co-owner
                    card as a raw catalogue key. */}
                <FormField id="co_applicant_relationship" label={t("portal.apply.coApplicant.relationship")}>
                  <SelectInput
                    id="co_applicant_relationship"
                    value={value.relationship}
                    placeholder={t("portal.apply.questions.choose")}
                    options={RELATIONSHIPS.map((code) => ({
                      value: code,
                      label: t(`customers.moveIn.customer.relationship.${code}`),
                    }))}
                    onChange={(relationship) => props.onCommit(set({ relationship }))}
                  />
                </FormField>
              </TwoUp>
              <ThreeUp>
                <FormField
                  id="co_applicant_phone"
                  label={t("portal.apply.coApplicant.phone")}
                  error={props.errors?.co_applicant_phone ?? null}
                >
                  <span onBlur={leave("phone")}>
                    <TextInput
                      id="co_applicant_phone"
                      type="tel"
                      value={value.phone}
                      invalid={props.errors?.co_applicant_phone !== undefined}
                      describedBy={fieldErrorId("co_applicant_phone")}
                      onChange={(phone) => set({ phone })}
                    />
                  </span>
                </FormField>
                <FormField
                  id="co_applicant_email"
                  label={t("portal.apply.coApplicant.email")}
                  error={props.errors?.co_applicant_email ?? null}
                >
                  <span onBlur={leave("email")}>
                    <TextInput
                      id="co_applicant_email"
                      type="email"
                      value={value.email}
                      invalid={props.errors?.co_applicant_email !== undefined}
                      describedBy={fieldErrorId("co_applicant_email")}
                      onChange={(email) => set({ email })}
                    />
                  </span>
                </FormField>
                <PortalDateField
                  id="co_applicant_date_of_birth"
                  label={t("portal.apply.coApplicant.dateOfBirth")}
                  value={value.date_of_birth}
                  max={props.today}
                  onChange={(date_of_birth) => props.onCommit(set({ date_of_birth }))}
                />
              </ThreeUp>
            </div>
          ) : null}
        </div>
      ) : null}
    </FormSection>
  );
}
