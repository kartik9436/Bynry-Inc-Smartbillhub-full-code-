// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the New tax or fee form draws its rate box
//           with a `%` box after it and its amount box with a `$` box before it
//           (images 09, 12, 13 of `05-prototype/taxes-fees-2026-10-03/images/`).
// Rules:    B14 rule 36 (where the kit lacks a piece, add it to the kit — the
//           field kit had no box that carries its unit) · CLAUDE.md hard rule 2
//           (the value is the typed STRING; nothing here parses it) · hard rule 3
//           (a figure is shown WITH its unit)
// ───────────────────────────────────────────────────────
//
// A text box that carries its unit in a fixed box beside it: `6.25 [%]`,
// `[$] 6.25`, `1.5 [% / month]`. The unit is part of the CONTROL, not of the
// label, so a clerk reads the figure and its meaning in one place — which is
// the point of P8 (*"Rate typed as a fraction"*): the box says what it holds.
import type { ReactNode } from "react";

import { FieldLabel, fieldErrorToShow, useFieldError } from "./FormModal";
import { FieldError, INVALID_INPUT_CLASS } from "./StateFrame";

export interface AffixFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** The unit, e.g. `%`, `$`, `% / month`. */
  affix: string;
  side: "start" | "end";
  required?: boolean;
  /** One line under the box — help, or a WARNING that is not an error. */
  help?: ReactNode;
  /** `warning` draws the help line and the border in the warning tone (a high
   *  rate warns, it does not refuse — image 10). */
  tone?: "plain" | "warning";
  placeholder?: string;
  disabled?: boolean;
  error?: string;
  /**
   * The label is announced and not drawn — for a box in a table cell whose
   * COLUMN HEADER is the label (`SelectField.labelHidden`'s shape). Added
   * 2026-10-05 under B14 rule 36 with its first caller, the move-in's
   * *Opening read* cell (`CR-171-BRC10` images 30 and 32). Absent renders
   * exactly what every existing caller renders.
   */
  labelHidden?: boolean;
}

export function AffixField(props: AffixFieldProps) {
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError);
  const warning = error === undefined && props.tone === "warning";
  const affix = (
    <span
      aria-hidden="true"
      className={
        "flex flex-none items-center bg-neutral-100 px-3 font-heading text-base font-semibold text-neutral-700 " +
        (props.side === "start" ? "border-r border-divider" : "border-l border-divider")
      }
    >
      {props.affix}
    </span>
  );
  const describedBy = [
    props.help !== undefined ? `${props.id}-help` : null,
    error !== undefined ? `${props.id}-error` : null,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={props.labelHidden === true ? "relative" : "field"}>
      <FieldLabel
        htmlFor={props.id}
        label={props.label}
        required={props.required === true}
        hidden={props.labelHidden}
      />
      <div
        className={
          "flex items-stretch border bg-field-fill " +
          (error !== undefined ? "border-danger-500" : warning ? "border-warning-500" : "border-field-border")
        }
        data-affix-field={props.id}
      >
        {props.side === "start" && affix}
        <input
          id={props.id}
          type="text"
          inputMode="decimal"
          className={`input input-num min-w-0 flex-1 border-0 ${error !== undefined ? INVALID_INPUT_CLASS : ""}`}
          value={props.value}
          placeholder={props.placeholder}
          disabled={props.disabled === true ? true : undefined}
          aria-required={props.required === true ? true : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          aria-describedby={describedBy === "" ? undefined : describedBy}
          onChange={(event) => props.onChange(event.target.value)}
        />
        {props.side === "end" && affix}
      </div>
      {props.help !== undefined && error === undefined && (
        <p
          className={`field-help mt-1.5 mb-0 ${warning ? "font-semibold text-warning-700" : ""}`}
          id={`${props.id}-help`}
          role={warning ? "status" : undefined}
        >
          {props.help}
        </p>
      )}
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}
