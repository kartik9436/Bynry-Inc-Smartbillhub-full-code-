// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave I — `ACC-S8`. The kit had no file input,
//           and B14 rule 36 says what to do about that: *"Where the kit lacks a
//           piece, ADD IT TO THE KIT — one component, one visual decision,
//           every screen — rather than hand-rolling it in the screen, which is
//           how four screens acquire four different chips."*
// Rules:    B14 rule 39 (label → input → helper, 5 / 6 / 20) · B14 rule 21
//           (Tailwind utilities; this file adds NO class to a stylesheet and is
//           registered in `styles/route-b-migrated.txt`) · BR-SHL-017 (required
//           fields are visibly marked) · A18 §5 (the offending input takes the
//           danger border).
// ───────────────────────────────────────────────────────
/**
 * One file input, built like every other field in this product.
 *
 * ⚠ **WHY IT IS ITS OWN FILE AND NOT A SIXTH VARIANT IN `FormModal.tsx`.** That
 * file is where `TextField`, `SelectField` and the rest live, and it is the
 * obvious home. It was being edited by another lane in this shared tree when
 * this was written, and `CLAUDE.md` law 11 is unambiguous about what happens
 * when two lanes write one file: the second to commit silently reverts the
 * first, with a correct file count and every check green. A new file collides
 * with nobody. **If a later lane folds this into `FormModal.tsx`, nothing here
 * resists it** — the markup below is that file's own, class for class.
 *
 * ⚠ **THE ANATOMY IS RULE 39's AND IT IS THE WHOLE REASON THIS IS A COMPONENT.**
 * label → input → helper, `mt-1.5` under the control, and the field's own
 * `.field` container carries the 20px to the next one. A screen hand-rolling an
 * `<input type="file">` gets the browser's default rhythm, which is none of
 * those numbers.
 *
 * ⚠ **THERE IS NO `value` PROP, AND THAT IS THE DOM's RULE RATHER THAN A
 * CHOICE.** A file input cannot be a controlled React input: its value may only
 * be set by the user, so a `value` prop would throw. The consumer holds the
 * chosen `File` in its own state and this reports changes through `onChange`.
 */
import type { ChangeEvent } from "react";

import { buttonClasses } from "./buttonKit";
import { useFieldError } from "./FormModal";

export function FileField(props: {
  id: string;
  label: string;
  /** The MIME/extension hint the browser filters on. **A convenience, never the
   *  guard** — `BR-SHL-031`'s allowlist is enforced by the server (415), and a
   *  clerk can defeat `accept` in any file picker. */
  accept?: string;
  required?: boolean;
  help?: string;
  onChange: (file: File | null) => void;
  /** The chosen file's name, so the field can say what is selected. */
  fileName?: string | null;
  error?: string;
}) {
  const contextError = useFieldError(props.id);
  const error = props.error ?? contextError;
  const describedBy = [
    props.help !== undefined ? `${props.id}-help` : null,
    error !== undefined ? `${props.id}-error` : null,
  ]
    .filter((value): value is string => value !== null)
    .join(" ");

  function handleChange(event: ChangeEvent<HTMLInputElement>): void {
    const chosen = event.target.files;
    props.onChange(chosen !== null && chosen.length > 0 ? chosen[0] : null);
  }

  return (
    <div className="field">
      <label htmlFor={props.id}>
        {props.label}
        {props.required === true && (
          // BR-SHL-017, and the same marker `FieldLabel` draws — one convention.
          <span className="field-required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      <input
        id={props.id}
        type="file"
        className={["input", error !== undefined ? "input-invalid" : ""].filter(Boolean).join(" ")}
        accept={props.accept}
        aria-required={props.required === true ? true : undefined}
        aria-invalid={error !== undefined ? true : undefined}
        aria-describedby={describedBy === "" ? undefined : describedBy}
        onChange={handleChange}
      />
      {props.help !== undefined && (
        // Rule 39: the helper reads as attached to the INPUT ABOVE IT, which is
        // what the 6px is for. `mt-1.5` is the figure the kit already uses.
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && (
        <p className="field-error" id={`${props.id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * **A FILE PICKER THAT LOOKS LIKE THE KIT'S SMALL BUTTON** — *Upload* in a
 * table cell (`CR-171-BRC10` images 33, 39: the move-in's Documents table).
 *
 * ⚠ **ADDED 2026-10-05 UNDER B14 RULE 36**, because `FileField` is a whole
 * field (label, native input, help) and a table cell holds a control whose
 * COLUMN HEADER is its label. The native input stays the control — focusable,
 * keyboard-operable, announced by `label` — and is visually hidden; the
 * `<label>` wearing `buttonClasses("secondary","sm")` is what a sighted clerk
 * presses. `accept` is a convenience and never the guard (the server's 415 is).
 */
export function UploadButton(props: {
  id: string;
  /** The button's word — *Upload*. */
  label: string;
  /** The accessible name of the input — *Upload Tenancy or deed*. */
  name: string;
  accept?: string;
  disabled?: boolean;
  onFile: (file: File) => void;
}) {
  const look = buttonClasses(
    "secondary",
    "sm",
    props.disabled === true
      ? "cursor-not-allowed opacity-45"
      : "cursor-pointer peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent",
  );
  return (
    <span className="inline-flex">
      <input
        id={props.id}
        type="file"
        className="peer sr-only"
        accept={props.accept}
        aria-label={props.name}
        disabled={props.disabled === true}
        onChange={(event) => {
          const chosen = event.target.files;
          if (chosen !== null && chosen.length > 0) props.onFile(chosen[0]);
          // The same file chosen twice in a row must fire again.
          event.target.value = "";
        }}
      />
      <label
        htmlFor={props.id}
        aria-hidden="true"
        className={look}
      >
        {props.label}
      </label>
    </span>
  );
}
