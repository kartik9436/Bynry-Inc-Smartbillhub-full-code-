// ── Trace ──────────────────────────────────────────────
// Change:   CR-161-BRC10 wave W7 — the utility's own questions on the customer
//           portal's new-service form (CWP-047 steps 2 and 3, CWP-009 step 4).
// Rulings:  PO 2026-10-02, Part 2 row 16, verbatim: *"Portal new-service form
//           (applicant) · Staff Request detail · Customer → clerk · Off by
//           default per field; a utility turns each one on"*; the Rules table:
//           *"Required means required only where it's typed in"* · *"One
//           utility only … including on the portal"*.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — the steps only mount
//           it) · rule 36/44 (the portal kit: `FormField`, `TextInput`,
//           `SelectInput`, `SectionTitle`, `KVList`) · rule 33 (a heading ≤ 3
//           words, an instruction ≤ 6, no rationale on screen) · rule 31 (no
//           id on screen) · rule 21 (Tailwind utilities only) · BR-TEN-048 (an
//           answer is shown as typed — a number is never money-formatted) ·
//           `22-product-maintenance-process.md` §6 (the eight accessibility
//           questions — answered in the CR file's W7 close)
// Tests:    src/portal/guest/ApplicationCustomFields.dom.test.tsx ·
//           06-backend/tests/test_cr161_w1_custom_field_settings.py (pairs
//           every `<ApplicationCustomFields entity=… screen=…>` below with the
//           slot list, exactly as it pairs the staff `<CustomFields…>`)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SERVER DECIDES WHICH QUESTIONS EXIST AND THIS FILE DECIDES NONE.**
// `draft.custom_fields` holds ONLY the fields this utility switched to *Ask the
// customer*, told only what drawing a box needs (key, label, help, type,
// options, required) — never an id and never the screens a field sits on
// inside the utility. A utility that asks nothing draws NOTHING here: no
// heading, no empty section (US-SHL-015 TC-4's posture).
//
// ⚠ **IT IS NOT THE STAFF `CustomFieldsInput`, DELIBERATELY.** That component
// reads the authenticated registry endpoint, which a stranger cannot call and
// must not: it serves placements. The portal is told its questions on the
// draft it already reads, and draws them with the portal's own kit.
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  PortalCustomAnswers,
  PortalCustomEntity,
  PortalCustomField,
} from "../api/guestClient";
import {
  FormField,
  SectionTitle,
  SelectInput,
  TextInput,
  fieldErrorId,
} from "../components/primitives";

/** The one screen these questions are typed on (`custom_fields.SLOTS`). */
export type PortalCustomScreen = "PORTAL_NEW_SERVICE";

/** A box's id: one per record type and key, because two record types may
 *  share a key (*Gate code* on the applicant and on the property). */
export function questionId(entity: PortalCustomEntity, key: string): string {
  return `cf-${entity}-${key}`;
}

/** The path the server names a refused answer by — `custom_data.<entity>.<key>`. */
export function questionErrorPath(entity: PortalCustomEntity, key: string): string {
  return `custom_data.${entity}.${key}`;
}

export function isBlankAnswer(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    (typeof value === "string" && value.trim() === "") ||
    (Array.isArray(value) && value.length === 0)
  );
}

/** Is any REQUIRED asked question still blank? — the screen's copy of
 *  `tenancy_seam.application_unanswered`, per record type. */
export function hasUnanswered(
  fields: readonly PortalCustomField[] | undefined,
  values: PortalCustomAnswers | undefined,
): boolean {
  return (fields ?? []).some((field) => field.is_required && isBlankAnswer(values?.[field.key]));
}

/** An answer as the applicant reads it back on Check and send. */
export function answerText(
  field: PortalCustomField,
  value: unknown,
  t: (key: string) => string,
): string {
  if (isBlankAnswer(value)) return "—";
  if (field.data_type === "boolean") {
    return value === true || value === "true" ? t("portal.apply.questions.yes") : t("portal.apply.questions.no");
  }
  if (Array.isArray(value)) return value.map(String).join(", ");
  return String(value);
}

export function ApplicationCustomFields(props: {
  entity: PortalCustomEntity;
  screen: PortalCustomScreen;
  fields: readonly PortalCustomField[];
  values: PortalCustomAnswers;
  heading: string;
  /** Mark every blank required box — set once the applicant has tried to go
   *  on, or the server held Send on this step. */
  showRequired: boolean;
  /** The server's sentence per refused box, keyed by `questionErrorPath`. */
  errors: Readonly<Record<string, string>>;
  /** The box changed — held in the form, not yet saved. */
  onChange: (key: string, value: unknown) => void;
  /** The box was left (or a choice made) — save the form. */
  onCommit: (key: string, value: unknown) => void;
}) {
  const { t } = useTranslation();
  const [touched, setTouched] = useState<ReadonlySet<string>>(() => new Set());
  if (props.fields.length === 0) return null;

  const leave = (key: string, value: unknown) => {
    setTouched((was) => new Set(was).add(key));
    props.onCommit(key, value);
  };

  return (
    <section className="flex flex-col gap-4" data-portal-questions={props.entity}>
      <SectionTitle>{props.heading}</SectionTitle>
      {props.fields.map((field) => {
        const id = questionId(props.entity, field.key);
        const value = props.values[field.key];
        const serverError = props.errors[questionErrorPath(props.entity, field.key)];
        const requiredError =
          field.is_required && isBlankAnswer(value) && (props.showRequired || touched.has(field.key))
            ? t("portal.apply.questions.required")
            : null;
        const error = serverError ?? requiredError;
        const helper = field.help_text ? field.help_text : undefined;
        const describedBy =
          [helper !== undefined ? `${id}-help` : null, fieldErrorId(id)].filter(Boolean).join(" ");

        if (field.data_type === "multi_select") {
          const chosen = Array.isArray(value) ? value.map(String) : [];
          return (
            <fieldset
              key={field.key}
              className="m-0 flex flex-col gap-2 border-0 p-0"
              data-question={field.key}
              aria-describedby={describedBy}
              aria-invalid={error ? true : undefined}
              aria-required={field.is_required ? true : undefined}
            >
              <legend className="mb-1.25 p-0 text-base font-semibold text-neutral-800">
                {field.label}
                {field.is_required ? (
                  <span className="text-accent-text" aria-hidden="true">
                    {" *"}
                  </span>
                ) : null}
              </legend>
              {helper !== undefined ? (
                <p id={`${id}-help`} className="text-base text-neutral-600">
                  {helper}
                </p>
              ) : null}
              {field.options.map((option) => (
                <label key={option} className="flex items-center gap-2 text-body text-neutral-900">
                  <input
                    type="checkbox"
                    checked={chosen.includes(option)}
                    onChange={(event) => {
                      const next = field.options.filter((one) =>
                        one === option ? event.target.checked : chosen.includes(one),
                      );
                      props.onChange(field.key, next);
                      leave(field.key, next);
                    }}
                  />
                  {option}
                </label>
              ))}
              <p
                id={fieldErrorId(id)}
                aria-live="polite"
                className={error ? "text-base font-semibold text-danger-700" : "sr-only"}
                data-field-error={error ? id : undefined}
              >
                {error ?? ""}
              </p>
            </fieldset>
          );
        }

        const choice =
          field.data_type === "select"
            ? field.options.map((option) => ({ value: option, label: option }))
            : field.data_type === "boolean"
              ? [
                  { value: "true", label: t("portal.apply.questions.yes") },
                  { value: "false", label: t("portal.apply.questions.no") },
                ]
              : null;

        return (
          <div key={field.key} data-question={field.key}>
            {/* The helper gets its own id so the box can name it as well as the
                error; `FormField` draws it as the kit always has. */}
            <FormField
              id={id}
              label={field.label}
              required={field.is_required}
              helper={helper}
              error={error}
            >
              {choice !== null ? (
                <SelectInput
                  id={id}
                  value={
                    field.data_type === "boolean"
                      ? value === true || value === "true"
                        ? "true"
                        : value === false || value === "false"
                          ? "false"
                          : ""
                      : typeof value === "string"
                        ? value
                        : ""
                  }
                  options={choice}
                  placeholder={t("portal.apply.questions.choose")}
                  invalid={Boolean(error)}
                  describedBy={fieldErrorId(id)}
                  required={field.is_required}
                  onChange={(raw) => {
                    const next = field.data_type === "boolean" ? (raw === "" ? null : raw === "true") : raw;
                    props.onChange(field.key, next);
                    leave(field.key, next);
                  }}
                  onBlur={() => setTouched((was) => new Set(was).add(field.key))}
                />
              ) : (
                <span
                  className="block"
                  onBlur={(event) => {
                    const input = event.target as HTMLInputElement;
                    leave(field.key, input?.value ?? "");
                  }}
                >
                  <TextInput
                    id={id}
                    type={field.data_type === "date" ? "date" : "text"}
                    inputMode={field.data_type === "number" ? "decimal" : undefined}
                    value={typeof value === "string" || typeof value === "number" ? String(value) : ""}
                    invalid={Boolean(error)}
                    describedBy={fieldErrorId(id)}
                    required={field.is_required}
                    onChange={(next) => props.onChange(field.key, next)}
                  />
                </span>
              )}
            </FormField>
          </div>
        );
      })}
    </section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-161-BRC10 §R6 Part 2 row 16 · decision log 2026-10-02 (W7) · B14 rules 21, 31, 33, 36, 43, 44
// generated: 2026-10-02 by lane CF-W7
// checklist: A✔ B✔ C✔ D✔(the server decides which questions) E✔(ApplyForService mounts it) F✔ G✔ H✔(a11y §6)
// gates: tsc · vitest ApplicationCustomFields.dom.test.tsx · W1 pairing test · routeBUtilities
