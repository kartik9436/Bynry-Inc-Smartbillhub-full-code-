// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-009 (EP-SHL-03 §Stories)  Screens: S12, S13, S16, S22, S114 (every form; quick-add modals per IS-1)
// Rules:    BR-SHL-017 (field kit + inline validation) · BR-SHL-033 (date-picker + searchable-long-list law — DatePickerField/SearchSelectField)
//           BR-PAY-033 (pre-filled posting-date default, refined PO 2026-08-09) · IS-1 (modal vs guided page) · IS-3 (ONE search debouncer)
//           IS-8 (regional date format) · IS-10 (Esc/✕/backdrop close, focus trap, aria)
// ───────────────────────────────────────────────────────
// FE-05 FormModal (B13 §1): the standard modal form frame — zod schema
// validation + server-error-envelope rendering (B12 §3: message_key + params).
// Three things live in this file as their ONE app-side definition:
//   1. ModalShell — the A12 "modal shell" (fixed overlay + card + header/body/
//      footer), ported shape from the prototype's settings modals; FE-04
//      ConfirmDialog composes it, never redefines it.
//   2. The US-SHL-009 form field kit (.field/.input/.seg/.radio, required
//      marking, help text; BR-SHL-033 adds DatePickerField + SearchSelectField,
//      and PasswordField closes the E1 gap S3/S114 were papering over locally)
//      — full-page forms (S12/S13/S16, guided per IS-1) compose these fields
//      directly, outside any modal.
//   3. FormModal — the frame wiring schema validation + envelope rendering to
//      the A18 §5 presentation kit (FieldError/FormErrorSummary — StateFrame's,
//      never reimplemented here).
// Client zod validation is UX only; the SERVER is authoritative (B8 forms).
// Money/quantity inputs carry raw strings end-to-end — the server owns parsing
// (CLAUDE.md rule 2); a consumption quantity never travels without its unit
// (CLAUDE.md rule 3, QuantityUnitField).
import { createContext, useContext, useEffect, useId, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ZodIssueCode } from "zod";
import type { ZodErrorMap, ZodTypeAny } from "zod";

import { refusalParams } from "@/api/refusalText";
import i18n from "@/i18n";

import { createSearchDebouncer } from "./DataTable";
import { CalendarIcon, ChevronDownIcon, CommitIcon } from "./icons";
import type { SearchDebouncer } from "./DataTable";
import {
  formatDate,
  nowInZone,
  parseRegionalDate,
  regionalDateEcho,
  regionalDateTimeEcho,
  sameDayBounds,
} from "./DateCell";
import type { RegionalDateFormat } from "./DateCell";
import { FieldError, FormErrorSummary, INVALID_INPUT_CLASS, WorkingButton } from "./StateFrame";
import type { CommitTier } from "./StateFrame";
import { RefusalStrip } from "./Surfaces";

import "./FormModal.css";
import { Button } from "@/components/Button";

// ── Validation (pure, testable without a browser) ──────────────────────────

export interface FormValidationResult {
  // One message per field key ("a.b" for nested paths) — A18 §5 renders it
  // directly under the offending field, so only the FIRST issue per field kept.
  errors: Record<string, string>;
  count: number; // invalid FIELD count — feeds "Fix N fields to continue."
  first: string | null; // scroll/focus target on submit (A18 §5)
}

// BR-SHL-017: submit re-validates on click. Messages inside the schema are the
// CONSUMER's, already localized (they call t with their catalog keys) — no
// concatenation here. Cross-field refinements must set a `path` so the message
// lands under a real field.
//
// ⚠ **`CR-168-BRC10` P3.51 — NO LIBRARY ENGLISH REACHES A CLERK.** A rule
// written with no message of its own used to put zod's sentence on screen —
// *String must contain at least 1 character(s)*, *Required*, *Invalid*. The
// map below is passed to the PARSE, which zod ranks BELOW a message bound in
// the schema: a rule that names its own sentence keeps it, and every other
// rule falls back to one of three catalogue sentences that already exist in
// all eleven languages (`errors.val-001/002/003`).
export const kitErrorMap: ZodErrorMap = (issue, ctx) => {
  const missing =
    (issue.code === ZodIssueCode.invalid_type &&
      (issue.received === "undefined" || issue.received === "null")) ||
    (issue.code === ZodIssueCode.too_small && issue.type === "string" && Number(issue.minimum) <= 1) ||
    (issue.code === ZodIssueCode.too_small && issue.type === "array" && Number(issue.minimum) <= 1) ||
    (issue.code === ZodIssueCode.invalid_enum_value && (ctx.data === "" || ctx.data == null));
  if (missing) return { message: i18n.t("errors.val-001") };
  if (issue.code === ZodIssueCode.too_small || issue.code === ZodIssueCode.too_big) {
    return { message: i18n.t("errors.val-003") };
  }
  return { message: i18n.t("errors.val-002") };
};

export function collectFormErrors(schema: ZodTypeAny, values: unknown): FormValidationResult {
  const parsed = schema.safeParse(values, { errorMap: kitErrorMap });
  if (parsed.success) {
    return { errors: {}, count: 0, first: null };
  }
  const errors: Record<string, string> = {};
  let first: string | null = null;
  for (const issue of parsed.error.issues) {
    const field = issue.path.join(".");
    if (field === "" || errors[field] !== undefined) {
      continue;
    }
    errors[field] = issue.message;
    first ??= field;
  }
  return { errors, count: Object.keys(errors).length, first };
}

// ── Server error envelope (B12 §3) ─────────────────────────────────────────
// `{code, message_key, params, field_errors[], br_ref, trace_id}`. B12 §3 does
// not pin the field_errors element shape — the shape below (field + its own
// message_key/params) is this file's working contract, flagged in the packet
// report for the A11 audit to ratify.

export interface ServerFieldError {
  field: string;
  message_key: string;
  params?: Record<string, unknown>;
}

export interface ServerErrorEnvelope {
  code: string;
  message_key: string;
  params?: Record<string, unknown>;
  field_errors?: ServerFieldError[];
  br_ref?: string;
  trace_id?: string;
}

export type FormSubmitOutcome = { ok: true } | { ok: false; error: ServerErrorEnvelope };

export type Translator = (key: string, params?: Record<string, unknown>) => string;

// B8 i18n: the server sends codes + params, the UI renders language — every
// message_key resolves through the catalog, never string-built client-side.
//
// ⚠ BR-SHL-020 r2 (PO 2026-08-19, DEF-322): the params handed to i18next go
// through `refusalParams`, which DROPS `params.detail` and adds the `ref` the
// system-error copy quotes. Before that, sixteen catalogue values interpolated
// `{{detail}}` and a clerk read the service's own engineering prose, BR-ids
// and all. `detail` still reaches the audit row and the server log — it moved,
// it was not deleted. Do NOT pass `envelope.params` straight to `t()` here or
// anywhere else; `refusalText()` in @/api/refusalText is the same rule for the
// screens that catch an ApiError without a FormModal around it.
export function envelopeErrors(
  envelope: ServerErrorEnvelope,
  t: Translator,
): { message: string; fields: Record<string, string> } {
  const fields: Record<string, string> = {};
  for (const fieldError of envelope.field_errors ?? []) {
    if (fields[fieldError.field] === undefined) {
      fields[fieldError.field] = t(
        fieldError.message_key,
        refusalParams(fieldError.params, envelope.trace_id),
      );
    }
  }
  return {
    message: t(envelope.message_key, refusalParams(envelope.params, envelope.trace_id)),
    fields,
  };
}

// ── Field-error wiring ─────────────────────────────────────────────────────
// Inside FormModal the frame supplies errors via context, so consumers just
// declare fields. Full-page forms (guided flows, IS-1) pass `error` directly.

const FieldErrorsContext = createContext<Record<string, string>>({});

export function useFieldError(fieldId: string): string | undefined {
  return useContext(FieldErrorsContext)[fieldId];
}

/**
 * The same context, for a full-page WIZARD that is not a `FormModal` or a
 * `FormPage` but renders kit fields that read their error from it — the
 * custom-field controls do (`CR-161-BRC10` W3). Without it a refused
 * `custom_data.<key>` on Add Premises named a field the clerk could not find.
 */
export function FieldErrorsScope(props: { errors: Record<string, string>; children: ReactNode }) {
  return (
    <FieldErrorsContext.Provider value={props.errors}>{props.children}</FieldErrorsContext.Provider>
  );
}

/**
 * **THE ONE PLACE A FIELD DECIDES WHETHER IT IS SHOWING AN ERROR
 * (`DEF-RAT-7800`).**
 *
 * Every field in this kit used to write `props.error ?? contextError` and then
 * branch on `error !== undefined` three times — for the danger border, for
 * `aria-invalid` and for the `FieldError` node. **`!== undefined` is TRUE for
 * an empty string**, so a message that arrives empty, whitespace, or resolved
 * to nothing paints a red box with nothing under it to read. A person then
 * sees a field marked wrong and no way to learn what is wrong with it — which
 * is worse than no marking at all, because they cannot act on it and cannot
 * dismiss it either.
 *
 * ⚠ **THAT IS A LATENT HAZARD RATHER THAN THE DEFECT THIS WAS FILED FOR, AND
 * SAYING SO IS THE POINT.** `DEF-RAT-7800`'s red box was the product's own
 * ACCENT FOCUS RING (`:focus-visible { outline: 2px solid var(--color-accent) }`
 * in `styles/global.css`, `#ec3013`) on a read-only box that was EMPTY —
 * measured in a browser, `borderColor` unchanged and no `input-invalid`
 * anywhere on the page. Nothing in the charge wizard can put an empty string
 * here today. This guard is written because the shape is one line away in any
 * screen that maps a server field error through `t()`, not because it fired.
 *
 * **Two rules, and the second is the one with a person behind it:**
 *
 *   1. **An empty or whitespace message is NO error.** No border, no
 *      `aria-invalid`, no empty `<p class="field-error">`.
 *   2. **A READ-ONLY field is never marked invalid.** A clerk cannot fix a box
 *      they cannot type in, so an error drawn on one is an instruction with no
 *      act attached. ⚠ **Nothing is hidden by this**: a server refusal still
 *      renders in full on the form's own refusal strip, which is where a
 *      message about a value the clerk did not enter belongs. Measured on the
 *      tip: 43 `TextField`/`MoneyTextField` call sites pass `readOnly`, 22 of
 *      them also pass `error`, and in every one of the 22 the read-only state
 *      is either a whole-panel permission mode (no save, so no field errors) or
 *      a value the server itself froze.
 *
 * `readOnly` is only offered by `TextField` — `SelectField`'s own note records
 * that HTML gives a `<select>` no such attribute — so rule 2 reaches exactly
 * one component and rule 1 reaches all of them.
 */
export function fieldErrorToShow(
  given: string | undefined,
  fromContext: string | undefined,
  readOnly = false,
): string | undefined {
  if (readOnly) {
    return undefined;
  }
  const message = given ?? fromContext;
  return message === undefined || message.trim() === "" ? undefined : message;
}

// ── The field kit (A12: .field + label + .input / select / .seg / .radio) ──

interface FieldOption {
  /** Extra text a type-to-filter box MATCHES on and never DRAWS — see
   *  `filterOptions`. Optional; omitting it matches on the label alone. */
  search?: string;
  value: string;
  label: string;
  /**
   * A muted fact drawn at the right of the option row in `SearchSelectField`'s
   * list — *Field technician · Invited* beside *T. Brooks* (`CR-168-BRC10`
   * image 26, lane CREWS). Opt-in under B14 rule 36: absent draws exactly what
   * every existing caller draws, and `SelectField` ignores it (a native
   * `<option>` has no second column).
   */
  detail?: string;
  // BR-SHL-025's shape one level down: an option the screen must SHOW but
  // cannot offer — a rule that is ratified-but-not-built (BR-RAT-041's
  // "Formula" charge), a value the server refuses. Present and unselectable
  // beats absent (the user would never learn it exists) and beats selectable
  // (they would only learn on submit). SelectField honours it; the option's
  // own label carries the reason.
  disabled?: boolean;
}

function describedBy(
  id: string,
  hasHelp: boolean,
  hasError: boolean,
  // `DEF-RAT-6164` — one more id to announce, ON TOP of the field's own help
  // and error and never instead of them. Absent, every existing call site
  // produces the byte-for-byte string it produced before this argument
  // existed. See `TextField`'s `describedBy` prop for why a sentence ever
  // lives outside the field it is about.
  extra?: string,
): string | undefined {
  const ids = [
    hasHelp ? `${id}-help` : null,
    hasError ? `${id}-error` : null,
    extra ?? null,
  ].filter((x): x is string => x !== null);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

/**
 * The REFUSED look, for a control that cannot act — `DEF-MET-4984`.
 *
 * ⚠ **A REFUSAL THAT LOOKS LIKE AN ORDINARY BOX IS NOT A REFUSAL.** The
 * add-asset wizard's *Opening read* was measured in Chromium at 1440 and 1280:
 * `background rgb(234,233,233)`, `colour rgb(32,30,29)`, `cursor text`,
 * `tabIndex 0` — byte for byte the same as every editable field beside it. A
 * clerk tabs in, types the meter's dial reading, and nothing appears.
 *
 * **It is `buttonKit`'s own string, character for character** (`BUTTON_BASE`,
 * line 127), because a disabled Button is this product's already-ratified answer
 * to *"this control cannot act"*. A second answer here would be a second look
 * for one idea, and the shared spelling is what makes the kinship visible to the
 * next reader.
 *
 * ⚠ **AND THE FIRST DRAFT OF THIS CONSTANT DID NOT WORK AT ALL, WHICH IS WHY IT
 * IS WRITTEN DOWN.** It dimmed the ground and the text with
 * `bg-[color-mix(…)] text-[color-mix(…)]`, mirroring `select.input:disabled`.
 * Measured in a browser: `cursor` changed and the COLOURS DID NOT — `.input`
 * declares `color` and `background` in an unlayered legacy stylesheet, and a
 * utility of equal specificity loses to whichever sheet the bundler emits last.
 * `tsc`, eslint and every `toContain` assertion passed on it, because the class
 * genuinely was in the DOM (B14 rule 21's own trap, one step sideways).
 * `opacity` is the one property `.input` does not set, so it is the one that
 * lands. A `hover:border-divider` went the same way and was removed rather than
 * left as decoration: `.input:hover` is 0-2-0 and the utility is 0-1-0, so it
 * could never have fired.
 */
const REFUSED_INPUT_CLASS = "disabled:opacity-45 disabled:cursor-not-allowed";

/**
 * The LOCKED look, for a value that is FIXED and must still be READ —
 * `DEF-RAT-9804` (PO, Edit charge code, 2026-10-06).
 *
 * ⚠ **NOT THE REFUSED LOOK ABOVE, AND THE DIFFERENCE IS THE DEFECT.** The
 * refused look dims a control that cannot ACT, and dimming is right there: the
 * clerk should look past it. A saved value the clerk cannot change — a charge
 * code's kind, its service, its code — is the opposite case: it is the thing
 * they came to check. Drawn refused, *Other charge* at 45% read as a
 * placeholder, and the one value drawn as a read-only text box (*Code*) read
 * as editable. Four locked values, two looks, neither right.
 *
 * So: full-strength text in a box flat with the page (`bg-bg`, the page's own
 * colour, where an editable field sits on `surface`), no chevron, default
 * cursor. Written WITHOUT `.input` on purpose — `.input` declares `color` and
 * `background` in an unlayered sheet that beats any utility (see the note
 * above), so the box restates `.input`'s geometry (36px, 6px × 10px, 14px,
 * 1px divider) in utilities instead of fighting it.
 */
const LOCKED_INPUT_CLASS =
  "block w-full min-h-9 border border-divider bg-bg px-2.5 py-1.5 font-body text-md text-text cursor-default focus-visible:border-accent";

/**
 * A locked value: an `<input readOnly>` holding the value's LABEL, never a
 * code behind it (B14 rule 31). `data-locked` names it for tests and walks.
 */
function LockedBox(props: { id: string; text: string; describedBy?: string; role?: "combobox" }) {
  return (
    <input
      id={props.id}
      type="text"
      readOnly
      aria-readonly
      role={props.role}
      aria-expanded={props.role === "combobox" ? false : undefined}
      className={LOCKED_INPUT_CLASS}
      value={props.text}
      aria-describedby={props.describedBy}
      data-locked=""
    />
  );
}

function inputClass(numeric: boolean, invalid: boolean, refused = false): string {
  // A18 §5: the offending input gets the danger border (INVALID_INPUT_CLASS —
  // StateFrame's, the ONE definition). A12: money/quantity inputs render
  // tabular numerals (.input-num).
  return [
    "input",
    numeric ? "input-num" : "",
    invalid ? INVALID_INPUT_CLASS : "",
    refused ? REFUSED_INPUT_CLASS : "",
  ]
    .filter(Boolean)
    .join(" ");
}

/**
 * ⚠ **`hidden` IS FOR A CONTROL INSIDE A TABLE CELL, WHERE THE COLUMN HEADER IS
 * THE LABEL — AND IT HIDES THE LABEL, IT NEVER REMOVES IT (`CR-096-BRC02`).**
 *
 * The Meter Reads blueprint draws the upload wizard's manual grid as five bare
 * cells under `METER · DATE · REGISTER · READING · NOTES`, and the drawing's own
 * note says they should be *"drawn to the kit"* — the register a `SelectField`
 * and the date the product's own date field — while the as-built hand-rolled
 * both. A field that prints its label a second time inside every cell is not
 * what is drawn, so the label goes `sr-only`: a screen reader still announces
 * it, `htmlFor` still binds, and nothing in the accessible tree moves.
 *
 * Opt-in, so every existing caller renders byte-for-byte what it rendered
 * before (B14 rule 38's own instruction for a piece the kit lacks).
 */
/**
 * **THE WRAPPER OF A `labelHidden` CONTROL IS POSITIONED, AND THAT ONE WORD IS
 * A LAYOUT FIX RATHER THAN A TIDY (`DEF-CUS-5480`).**
 *
 * `FieldLabel` renders a hidden label as `sr-only`, which is
 * `position: absolute`. An absolutely positioned box is clipped by an
 * ancestor's `overflow` ONLY when that ancestor is also its containing block —
 * so with no positioned ancestor at all, the label's containing block is the
 * INITIAL one, it escapes the screen scroller, and it enlarges the DOCUMENT
 * instead.
 *
 * ⚠ **WHAT THAT COSTS, MEASURED ON THE RUNNING PRODUCT.** New Connect step 4's
 * grid draws forty of these on a six-unit build. The lowest sat 1,782px down,
 * so `document.documentElement.scrollHeight` read **1,782 against a 1,000px
 * viewport**: the window grew a second scrollbar that scrolls 782px into empty
 * grey, the app shell — sidebar, top bar, grid and all — slid away with it, and
 * the panel simply ended mid-table with no border and no Back/Continue footer
 * anywhere. Every other long screen measured `scrollHeight === clientHeight`;
 * only the screen with hidden labels below the fold did not.
 *
 * ⚠ **NOTHING IN THIS REPOSITORY COULD SEE IT.** The rows were all in the DOM,
 * so every assertion that counts cells passed; the test environment does no
 * layout, so every element there is zero by zero; and no gate reads rendered
 * output. It was found by a person looking at the screen, which is hard-won
 * law 6 exactly.
 *
 * `relative` with no offsets moves nothing and paints nothing — it only makes
 * this wrapper the label's containing block, so the label is clipped by the
 * scroller it lives in. Proved on the running page before it was written:
 * injecting it took the document from 1,782px back to 1,000px with all
 * fourteen rows unchanged.
 *
 * ⚠ **THE SAME ESCAPE IS STILL LIVE ON `peer sr-only` INPUTS** — the visually
 * hidden radio and checkbox this kit draws — and it is `DEF-SHL-5492` rather
 * than something fixed in passing here.
 */
const HIDDEN_FIELD = "relative";

/**
 * ⚠ **EXPORTED SINCE 2026-09-23 (`CR-137-BRC07` `P3.11`), AND IT MOVES NO
 * PIXEL.** `ChipMultiSelect` renders its `label` as an `aria-label` on a
 * `role="group"` and draws NO VISIBLE LABEL of its own — every existing caller
 * supplies one from a surrounding `Panel title=…`. Inside a MODAL there is no
 * panel, so 2·3h's drawn **Send by \*** had nowhere to come from.
 *
 * **B14 rule 36's own mechanism decides it:** *"where the kit lacks a piece,
 * ADD IT TO THE KIT — one component, one visual decision, every screen —
 * rather than hand-rolling it in the screen."* Hand-rolling a `<label>` in the
 * modal would have been a SECOND way a field gets its name and its asterisk,
 * free to drift from this one (B14 rule 10's marker, `field-required`).
 *
 * Exporting changes nothing for the five variants that already compose it.
 * ⚠ The deeper gap — that `ChipMultiSelect` should carry its own label and
 * required marker — is filed as `DEF-SHL-6250` rather than fixed here, because
 * that component is on nine screens and moving it is its own work with its own
 * proof.
 */
export function FieldLabel(props: {
  htmlFor?: string;
  id?: string;
  label: string;
  required: boolean;
  hidden?: boolean;
}) {
  return (
    <label htmlFor={props.htmlFor} id={props.id} className={props.hidden === true ? "sr-only" : undefined}>
      {props.label}
      {props.required && (
        // BR-SHL-017: required fields are visibly marked. The convention is
        // PROPOSED (not shown in prototype) — accent asterisk until design
        // ratifies; aria-required on the control carries it to AT.
        <span className="field-required" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}

export function TextField(props: {
  id: string;
  label: string;
  value: string; // ALWAYS a string — money/quantities are never floats client-side (rule 2)
  onChange: (value: string) => void;
  required?: boolean;
  help?: string;
  placeholder?: string;
  numeric?: boolean; // money/quantity: tabular numerals + decimal keypad; raw string to server
  multiline?: boolean;
  // BR-SHL-025's shape for a value the user may READ but not set — a frozen
  // code, a rule with exactly one ratified value. `readOnly` rather than
  // `disabled` on purpose: the field stays focusable and its text stays
  // selectable, and the `help` line carries the reason.
  readOnly?: boolean;
  /**
   * BR-SHL-025 proper — a control that CANNOT ACT, with its reason in `help`.
   *
   * ⚠ **THIS IS NOT `readOnly` WITH A DIFFERENT SPELLING, AND THE DIFFERENCE IS
   * THE DEFECT (`DEF-MET-4984`).** `readOnly` is for a value the user may READ
   * but not set — it stays focusable and selectable on purpose, because there is
   * something there worth copying. `disabled` is for a box with NOTHING in it
   * that will not take what you type: the add-asset wizard's *Opening read*,
   * which is refused until a published seam lets assets write a meter read at
   * create time. It renders refused (`REFUSED_INPUT_CLASS`) so the sentence
   * under it is not the only thing saying so.
   */
  disabled?: boolean;
  /**
   * `DEF-TEN-4478` — the browser's own fill, refused BY NAME.
   *
   * A controlled input the browser fills writes the DOM and fires no React
   * change event, so the element and the state disagree and the SILENT half is
   * the one that gets submitted. That is not a hypothetical: the PO's
   * screenshot of the Add-an-area dialog showed a code and a parent nobody on
   * that screen had typed, above a sentence saying to leave it blank.
   *
   * Pass `"off"` on a field whose value is a record identifier rather than a
   * fact about the person — a lookup code, a tenant's own short name. It is
   * NOT the default: an address or a contact field SHOULD be fillable, and
   * turning that off across the kit would be a usability regression nobody
   * asked for.
   *
   * ⊕ **`DEF-CUS-10044` — A CONTACT FIELD NAMES ITS OWN PURPOSE.** `tel`,
   * `email`, `name` and `bday` tell the browser what the box IS, so a saved
   * LOGIN is never taken for it. New Connect's Phone showed the clerk's own
   * sign-in email because the box after it was a password input and the
   * browser read Phone as the username.
   */
  autoComplete?: "off" | "tel" | "email" | "name" | "bday";
  /**
   * The label is announced and not drawn — for a control in a table cell whose
   * COLUMN HEADER is the label. The same opt-in `SelectField` and
   * `DatePickerField` have carried since `CR-087`; see `FieldLabel`, and
   * `HIDDEN_FIELD` for why the wrapper is positioned.
   *
   * ⚠ **ADDED 2026-09-18 (`DEF-RAT-5734`) UNDER B14 RULE 36** — *where the kit
   * lacks a piece a drawing needs, ADD IT TO THE KIT as an opt-in, so nothing
   * existing moves.* The rate schedule's size table printed *"Minimum rate for
   * Solar panel 1 kW"* once per row beside a column already headed *Minimum
   * rate*, which is B14 rule 32 clause 3 — a row never repeats what its own
   * control offers — and the two sibling controls could express the fix while
   * this one could not. Absent renders byte-for-byte what every existing
   * caller renders today.
   */
  labelHidden?: boolean;
  /**
   * One more element id announced with this input, ON TOP of its own `help`
   * and its error — never instead of either.
   *
   * ⚠ **ADDED 2026-09-22 (`DEF-RAT-6164`) UNDER B14 RULE 38**, in the same
   * opt-in shape as `labelHidden` above and for the reason `DEF-RAT-5734`
   * recorded there: *where the kit lacks a piece a screen needs, ADD IT TO THE
   * KIT as an opt-in, so nothing existing moves.* Absent, this renders
   * byte-for-byte what every existing caller renders today.
   *
   * **WHY A SENTENCE WOULD EVER LIVE OUTSIDE ITS OWN FIELD.** `help` renders
   * INSIDE the field's box and makes that box taller. In a ROW of controls laid
   * out as a grid, a taller box is a control that no longer shares a baseline
   * with its neighbours: the rate schedule's tier ladder measured **43px** of
   * lift on `To` for exactly that reason, on every row of the ladder. Where one
   * sentence belongs to a whole ladder rather than to one box, it is written
   * ONCE outside the rows and pointed at from here — so the row keeps its
   * baseline and a screen reader still reaches the sentence from the input it
   * is about.
   */
  describedBy?: string;
  /**
   * ⊕ **`CR-164-BRC10` / `DEF-CUS-9194` — A SECRET THE CLERK TYPES BUT NO ONE
   * BEHIND THEM SHOULD READ** (a Social Security number, a driving licence).
   * PO ruling Q4 of 2026-10-02: *"SSN/DL masked"*. Opt-in in the shape
   * `labelHidden` set (B14 rule 38: add to the kit, move nothing): absent
   * renders byte-for-byte what every caller renders today. It is not
   * `PasswordField` because that one asks the browser to SAVE what is typed.
   */
  masked?: boolean;
  /**
   * ⊕ **`DEF-CUS-9826` (N6, PO 2026-10-06) — A MASKED BOX THE PERSON TYPING
   * CAN CHECK.** PO, verbatim: *"give the hide and view button with that fields
   * so user can view while entering"*. With `masked`, draws the kit's own
   * password Show/Hide (`passwordToggle`, the `.password-field` pair):
   * masked by default, *Show* reveals, *Hide* masks again. Nothing about what
   * is stored or sent moves — only what the screen shows. Opt-in (B14 rule
   * 38): absent renders byte-for-byte what every caller renders today.
   */
  revealable?: boolean;
  error?: string; // full-page forms pass it; inside FormModal context supplies it
}) {
  // ⊕ **`DEF-CUS-10044` — A MASKED BOX IS NEVER A SAVED LOGIN.** A masked
  // input is `type="password"`, and browsers IGNORE `autocomplete="off"` on a
  // password input: they fill the clerk's saved password into it and the
  // clerk's saved username into the text box before it. `new-password` is the
  // value every browser honours as *do not fill a stored credential here*; the
  // two `data-*` flags say the same to LastPass and 1Password. Shared by both
  // masked renders below, so no masked field can drift back.
  const maskedFill = {
    autoComplete: "new-password",
    "data-lpignore": "true",
    "data-1p-ignore": "true",
  } as const;
  const { t } = useTranslation();
  const [revealed, setRevealed] = useState(false);
  const toggle = passwordToggle(revealed);
  const canReveal = props.masked === true && props.revealable === true;
  const contextError = useFieldError(props.id);
  // `DEF-RAT-7800` — the third argument is what stops a box a clerk cannot type
  // in being marked wrong. `TextField` is the ONLY field in this kit that takes
  // `readOnly`, so it is the only one that passes it.
  const error = fieldErrorToShow(props.error, contextError, props.readOnly === true);
  const shared = {
    id: props.id,
    className: inputClass(props.numeric === true, error !== undefined, props.disabled === true),
    value: props.value,
    placeholder: props.placeholder,
    autoComplete: props.autoComplete,
    disabled: props.disabled === true ? true : undefined,
    readOnly: props.readOnly === true ? true : undefined,
    "aria-required": props.required === true ? true : undefined,
    "aria-invalid": error !== undefined ? true : undefined,
    "aria-readonly": props.readOnly === true ? true : undefined,
    // BR-SHL-017 / IS-10: the error is announced with the input it belongs to.
    "aria-describedby": describedBy(
      props.id,
      props.help !== undefined,
      error !== undefined,
      props.describedBy,
    ),
  };
  return (
    <div className={props.labelHidden === true ? HIDDEN_FIELD : "field"}>
      <FieldLabel
        htmlFor={props.id}
        label={props.label}
        required={props.required === true}
        hidden={props.labelHidden}
      />
      {props.multiline === true ? (
        <textarea {...shared} onChange={(e) => props.onChange(e.target.value)} />
      ) : canReveal ? (
        <div className="password-field">
          <input
            {...shared}
            type={toggle.inputType}
            {...maskedFill}
            inputMode={props.numeric === true ? "decimal" : undefined}
            onChange={(e) => props.onChange(e.target.value)}
          />
          {/* `type="button"` (the kit's Button) so revealing never submits a
              form; `aria-controls` + `aria-pressed` name what it acts on. */}
          <Button
            variant="ghost"
            className="password-toggle"
            aria-controls={props.id}
            aria-pressed={revealed}
            data-reveal={props.id}
            onClick={() => setRevealed(!revealed)}
          >
            {t(toggle.textKey)}
          </Button>
        </div>
      ) : (
        <input
          {...shared}
          type={props.masked === true ? "password" : "text"}
          {...(props.masked === true ? maskedFill : { autoComplete: props.autoComplete })}
          inputMode={props.numeric === true ? "decimal" : undefined}
          onChange={(e) => props.onChange(e.target.value)}
        />
      )}
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}

// ── PasswordField (E1 rider from the Settings lane, closed here) ───────────
// BR-SHL-017 lists a field kit but designed no password control, so S3 sign-in
// and the S114 owner step each grew their own input — two definitions of one
// control, which is precisely what the ONE kit exists to prevent. It lives here
// now with the same props shape, the same error wiring and the same a11y as
// every other field, plus the one thing a password input needs that none of the
// others do: a show/hide toggle.

export interface PasswordToggleState {
  inputType: "password" | "text";
  textKey: string; // the visible toggle copy
  labelKey: string; // its accessible name ("Show password" / "Hide password")
}

/**
 * The whole reveal law, pure: what the input renders as and what the toggle is
 * called. Provable without a browser; the component only holds the boolean.
 */
export function passwordToggle(revealed: boolean): PasswordToggleState {
  return revealed
    ? { inputType: "text", textKey: "forms.password.hide", labelKey: "forms.password.hideLabel" }
    : {
        inputType: "password",
        textKey: "forms.password.show",
        labelKey: "forms.password.showLabel",
      };
}

export function PasswordField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  help?: string;
  placeholder?: string;
  // The browser credential-manager hint — "current-password" when signing in,
  // "new-password" wherever one is being set. The only prop the rest of the kit
  // has no use for; everything else matches TextField exactly.
  autoComplete?: "current-password" | "new-password";
  error?: string; // full-page forms pass it; inside FormModal context supplies it
}) {
  const { t } = useTranslation();
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError);
  const [revealed, setRevealed] = useState(false);
  const toggle = passwordToggle(revealed);
  return (
    <div className="field">
      <FieldLabel htmlFor={props.id} label={props.label} required={props.required === true} />
      <div className="password-field">
        <input
          id={props.id}
          type={toggle.inputType}
          className={inputClass(false, error !== undefined)}
          value={props.value}
          placeholder={props.placeholder}
          autoComplete={props.autoComplete}
          aria-required={props.required === true ? true : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          aria-describedby={describedBy(props.id, props.help !== undefined, error !== undefined)}
          onChange={(e) => props.onChange(e.target.value)}
        />
        {/* A real button with a real accessible name — and `type="button"`, so
            revealing a password inside a <form> can never submit it. */}
        <Button
          variant="ghost"
          className="password-toggle"
          aria-label={t(toggle.labelKey)}
          aria-controls={props.id}
          aria-pressed={revealed}
          onClick={() => setRevealed(!revealed)}
        >
          {t(toggle.textKey)}
        </Button>
      </div>
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}

export function SelectField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: FieldOption[];
  /**
   * **Options in labelled groups, drawn after `options` as `<optgroup>`s.**
   *
   * ⚠ **ADDED 2026-10-03 (`CR-166-BRC10` task 4) UNDER B14 RULE 36** — the New
   * discount form's *Who qualifies* is one dropdown in TWO groups, *The system
   * checks* and *The customer shows proof* (PO 2026-10-03, README point 3), and
   * which group a choice is in decides whether Automatic may be picked. A
   * screen-local `<select>` would have been a second select style. Opt-in:
   * absent renders byte-for-byte what every existing caller renders today.
   */
  groups?: readonly { label: string; options: readonly FieldOption[] }[];
  required?: boolean;
  help?: string;
  placeholder?: string; // renders as the leading empty option
  error?: string;
  /**
   * The label is announced and not drawn — for a control in a table cell whose
   * COLUMN HEADER is the label. See `FieldLabel`, and `HIDDEN_FIELD` for why
   * the wrapper is positioned. Opt-in; absent renders exactly what every
   * existing caller renders today.
   */
  labelHidden?: boolean;
  /**
   * **BR-SHL-025 — a chooser that CANNOT ACT, with its reason in `help`.**
   *
   * ⚠ **ADDED 2026-09-21 (`DEF-CUS-6116`) UNDER B14 RULE 36** — *where the kit
   * lacks a piece a screen needs, ADD IT TO THE KIT as an opt-in, so nothing
   * existing moves.* Absent renders byte-for-byte what every existing caller
   * renders today.
   *
   * ⚠ **THERE IS NO `readOnly` HERE AND THAT IS HTML'S DOING, NOT A CHOICE.**
   * `TextField` carries both, and its own note draws the line: `readOnly` is a
   * value you may READ but not set, `disabled` is a control that cannot act.
   * **A `<select>` has no `readonly` attribute at all** — the browser ignores
   * it — so a chooser holding a value that is not the clerk's to change can
   * only be `disabled`. It keeps its value on screen (a disabled select still
   * draws its chosen option) and the `help` line says where that value came
   * from; `aria-disabled` is what a screen reader announces.
   *
   * ⚠ **A CONTROLLED SELECT IS NOT A FORM FIELD**, so nothing is dropped from
   * a submission by disabling it — the value lives in React state, which is
   * why this is safe where a native `<form>` would lose it.
   */
  disabled?: boolean;
  /**
   * **A FIXED VALUE TO BE READ, NOT A CONTROL THAT CANNOT ACT — OPT-IN, ADDED
   * 2026-10-06 (`DEF-RAT-9804`) UNDER B14 RULES 36 AND 43.** Draws the chosen
   * option's label in full-strength text in a locked box (`LockedBox`) instead
   * of a dimmed `<select>`. Use `disabled` when the clerk should look past the
   * control; use this when the value is the point. Absent renders exactly what
   * every existing caller renders today.
   */
  locked?: boolean;
}) {
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError, props.locked === true);
  if (props.locked === true) {
    const chosen =
      props.options.find((option) => option.value === props.value) ??
      props.groups?.flatMap((group) => group.options).find((option) => option.value === props.value);
    return (
      <div className={props.labelHidden === true ? HIDDEN_FIELD : "field"} data-locked-field={props.id}>
        <FieldLabel
          htmlFor={props.id}
          label={props.label}
          required={props.required === true}
          hidden={props.labelHidden}
        />
        <LockedBox
          id={props.id}
          text={chosen?.label ?? props.placeholder ?? ""}
          describedBy={describedBy(props.id, props.help !== undefined, false)}
        />
        {props.help !== undefined && (
          <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
            {props.help}
          </p>
        )}
      </div>
    );
  }
  return (
    <div className={props.labelHidden === true ? HIDDEN_FIELD : "field"}>
      <FieldLabel
        htmlFor={props.id}
        label={props.label}
        required={props.required === true}
        hidden={props.labelHidden}
      />
      <select
        id={props.id}
        className={inputClass(false, error !== undefined, props.disabled === true)}
        value={props.value}
        disabled={props.disabled === true ? true : undefined}
        aria-required={props.required === true ? true : undefined}
        aria-invalid={error !== undefined ? true : undefined}
        aria-describedby={describedBy(props.id, props.help !== undefined, error !== undefined)}
        onChange={(e) => props.onChange(e.target.value)}
      >
        {props.placeholder !== undefined && <option value="">{props.placeholder}</option>}
        {props.options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled === true}>
            {option.label}
          </option>
        ))}
        {props.groups?.map((group) => (
          <optgroup key={group.label} label={group.label}>
            {group.options.map((option) => (
              <option key={option.value} value={option.value} disabled={option.disabled === true}>
                {option.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}

/**
 * **THE FIELD RHYTHM — B14 RULE 39's `field → field 20px`, in one place
 * (`DEF-CUS-5098`).**
 *
 * PO 2026-09-11, on why this exists at all: *"have a proper padding for each
 * component on the screen. these padding should be universally fit for the
 * product… the components are too much close"*. Rule 39's field anatomy is
 * label → input **5px**, input → helper **6px**, field → field **20px** — a
 * ratio of ≈ 1 : 1 : 4 — and the 20 was ratified over the scale's 16 on
 * 2026-09-12: *"a) 20 everywhere — the anatomy wins"*.
 *
 * ⚠ **MEASURED, NOT ASSUMED, AND IT WAS ZERO.** A run of `.field`s dropped
 * straight into a `Panel` is `display: block` with `gap: normal`, so the fields
 * touch. In Chromium at 1280 AND 1440 on the new account wizard's step 1:
 * **eight adjacent pairs at 0px**, one at −0.01px. The new connect wizard's
 * step 1 measured **12px** on four pairs. **Zero of twelve adjacent pairs
 * across the five starting-service wizards were at 20px** — the same finding
 * `CR-092` step 1 recorded as *"zero of eleven"* on the asset screens.
 *
 * ⚠ **WHY A CONTAINER AND NOT `.field { margin-bottom: 20px }`.** `.field` is
 * used inside `.modal-body`, which already supplies the 20px as a flex `gap`
 * (see its own note) — a margin would ADD to that gap and every dialog in the
 * product would go to 40px. A margin also cannot tell *the next field* from
 * *the paragraph after the last field*, and rule 39 governs only the first.
 * The container states the layout exactly where the layout is decided.
 *
 * ⚠ **AND WHY NOT `Panel`'s OWN CLASS.** A panel holds headings, prose,
 * tables, KPI rows and figures across 149 call sites; 20px between a heading
 * and its own hint line is not rule 39 and would move every one of them. This
 * wraps THE FIELDS and nothing else.
 *
 * `gap-5` is `var(--space-5)` = 20px — the step rule 39's amendment added to
 * the scale, never an ad-hoc 20. It is the same string the four asset full-page
 * forms already carry from `CR-092` step 2 wave A (`d9fbffde4`); this names it
 * once so the fifth screen cannot spell it differently.
 */
export function FieldStack(props: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-5" data-field-stack="">
      {props.children}
    </div>
  );
}

// A12 `.seg` segmented radios — one visible choice among few.
/**
 * ⚠ **`required` EXISTS BECAUSE A GATED GROUP WITH NO MARK MAKES THE FRAME LIE
 * (`DEF-CUS-5082`).** This control hard-coded `required={false}` and had no prop
 * to say otherwise, so a wizard step gating `Continue` on it refused with
 * `WizardFrame`'s generic sentence — *"Fill in what's marked above"* — over a
 * screen carrying no mark at all. That is the exact case the frame warns about
 * in its own comment: *"the generic one is the FALLBACK — true whenever the
 * unmet condition is a marked field, and a lie whenever it is not."* Measured on
 * the service-request capture's step 1: the refusal rendered with
 * `[aria-invalid=true]` count **0** and error-class count **0**.
 *
 * It is the SAME prop the other five variants already take, threaded to the
 * same `FieldLabel` — not a second marking mechanism — so B14 rule 10 is one
 * rule with one implementation. `aria-required` goes on the `radiogroup` and not
 * on the individual radios, because the group is the thing that must be
 * answered; a required radio INPUT would tell a screen reader that each option
 * is separately obligatory.
 *
 * **Absent means `false`, which is what all eighteen existing call sites
 * render**, so nothing outside the one screen this was written for moves.
 */
export function SegmentedField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: FieldOption[];
  required?: boolean;
  error?: string;
  /**
   * The label is announced and not drawn — the move-in's *Person · Company*
   * (`CR-171-BRC10` image 33), where the two words ARE the question. Added
   * 2026-10-05 under B14 rule 36 as an opt-in, the same one `SelectField`,
   * `TextField` and `CheckboxField` carry; absent renders exactly what every
   * existing caller renders today.
   */
  labelHidden?: boolean;
}) {
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError);
  return (
    <div className="field">
      <FieldLabel
        id={`${props.id}-label`}
        label={props.label}
        required={props.required === true}
        hidden={props.labelHidden === true}
      />
      <div
        className="seg"
        role="radiogroup"
        aria-labelledby={`${props.id}-label`}
        aria-required={props.required === true ? true : undefined}
        aria-invalid={error !== undefined ? true : undefined}
      >
        {props.options.map((option) => (
          <label key={option.value} className="seg-opt">
            <input
              type="radio"
              name={props.id}
              value={option.value}
              checked={props.value === option.value}
              onChange={() => props.onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}

/** The multi-select checkbox — A SQUARE WITH A TICK, never the radio's circle.
 *
 * ⚠ DEF-569, and the reason this control does NOT reuse `.radio`. It did until
 * 2026-08-22: `<label class="radio">` + `<span class="dot">`, and
 * `FormModal.css` draws `.radio .dot` as a 16px circle with `border-radius:50%`
 * and an inset ring when checked — the RADIO affordance, on the control where
 * several boxes are ticked at once. Measured in Chromium on the running
 * product, sign-in and Settings → Security: `border-radius: 50%`, 16x16, and on
 * Security TWO of them filled solid accent at the same time. A round control
 * already ticked twice reads as a broken radio group, and a user's first
 * instinct is that ticking a second one unticks the first.
 *
 * **A control's shape is its promise about how many things can be chosen.** So
 * the mark is a square: same 16px, same 1.5px divider border, same accent fill
 * when checked, plus the vocabulary's ✓ inside it.
 *
 * `.radio` and `.dot` STAY in `FormModal.css` — `ChangePlanWizard` and
 * `BudgetBillsTab` draw genuine one-of-N radios with them, which is what those
 * rules were written for. Sharing them across two selection semantics was the
 * defect; deleting them would break the semantics that is correct.
 *
 * ROUTE B (PO ruling 2026-08-19), so no class name is added to a stylesheet and
 * this file joins `src/styles/route-b-migrated.txt`. The tick is `CommitIcon`
 * from the ONE icon vocabulary — a second tick glyph in `icons.tsx` under a
 * second name is DEF-348 exactly — scaled by its container rather than by a new
 * geometry constant: r10 draws its checklist tick at 14px in a 22px box
 * (`SMARTBillHub.dc.html:492`, stroke 3), so 10px in our 16px box is the same
 * 0.63 ratio, and stroke 3 in the 24-unit viewBox reproduces r10's 1.75px
 * rendered weight at our size (3 x 10/24 = 1.27px on a 16px box vs r10's
 * 3 x 14/24 = 1.75px on 22px — 0.079 of the box, both).
 *
 * The input is `sr-only` + `peer` rather than the `.radio input` opacity-0 trick:
 * it keeps the real checkbox as the focusable, screen-reader-announced control
 * (`peer-focus-visible` puts the ring on the mark) and the checked/hover states
 * come from the input itself, so nothing here can disagree with `props.checked`.
 */
export function CheckboxField(props: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  /**
   * BR-SHL-025 — a box that CANNOT be ticked, with its reason beside it.
   *
   * ⚠ **OPT-IN, ADDED 2026-09-15 UNDER B14 RULE 36** (`CR-101-BRC03` lane A, the
   * Fix a bill reason list): the blueprint draws five *"not a correction"* rows
   * as checkboxes that refuse and name their destination (p133). Absent renders
   * byte-for-byte what every existing caller renders today, so nothing moves.
   * A screen-local `<input type="checkbox" disabled>` would have been a second
   * checkbox style — which is how four screens acquire four different chips.
   */
  disabled?: boolean;
  /**
   * The label is announced and not drawn — for a box in a table cell whose
   * COLUMN HEADER is the label (the fee table's `Waive`, 2026-09-23). The same
   * opt-in `TextField`, `SelectField` and `DatePickerField` already carry, for
   * `tableTypes.ts`'s reason: *a table cell holds a value, and a control holds
   * a label*, and printing `Waive` beside every box in a column already headed
   * `WAIVE` is the same word twice a row. Absent renders byte-for-byte what
   * every existing caller renders today (B14 rule 36).
   */
  labelHidden?: boolean;
}) {
  const disabled = props.disabled === true;
  return (
    <label
      className={`inline-flex items-center gap-2 text-md ${disabled ? "cursor-not-allowed opacity-45" : "cursor-pointer"}`}
      htmlFor={props.id}
    >
      <input
        id={props.id}
        type="checkbox"
        className="peer sr-only"
        checked={props.checked}
        disabled={disabled}
        onChange={(e) => props.onChange(e.target.checked)}
      />
      <span
        aria-hidden="true"
        data-checkbox-mark=""
        className="flex size-4 flex-none items-center justify-center border-[1.5px] border-divider text-transparent peer-checked:border-accent peer-checked:bg-accent peer-checked:text-on-accent peer-hover:border-accent peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent [&_svg]:size-2.5 [&_svg]:stroke-[3]"
      >
        <CommitIcon />
      </span>
      <span className={props.labelHidden === true ? "sr-only" : undefined}>{props.label}</span>
    </label>
  );
}

// CLAUDE.md rule 3: a consumption quantity may never travel without its unit.
// Consumers put this inside their zod schema (superRefine on the unit path).
export function missingUnit(quantity: string, unit: string): boolean {
  return quantity.trim() !== "" && unit.trim() === "";
}

// ── BR-SHL-033 field-kit additions (PO 2026-08-09, batch item b rider) ─────
// Two controls the law demands app-wide, added to the ONE field kit:
//   · DatePickerField — every date field is a DATE PICKER with easy manual
//     entry (the native input takes both), regional format per IS-8, and the
//     BR-PAY-033 pre-filled-default behavior where a story rules one.
//   · SearchSelectField — any long dropdown (roughly >LONG_LIST_THRESHOLD
//     options: accounts, premises, plans, GL accounts, lookups…) is SEARCHABLE
//     (type-ahead), never a bare scroll list.

// BR-SHL-033: "roughly >10 options" as a named constant so consuming screens
// cite the law instead of hardcoding a magic number.
export const LONG_LIST_THRESHOLD = 10;

// BR-PAY-033 (refined PO 2026-08-09, API batch A-1): the UI ALWAYS proposes a
// pre-filled default date — an empty value renders the proposal; any
// user-entered value wins. Pure so both halves are provable without a browser.
export function resolveDateInputValue(value: string, prefill?: string): string {
  return value === "" && prefill !== undefined ? prefill : value;
}

export function DatePickerField(props: {
  id: string;
  label: string;
  value: string; // "YYYY-MM-DD" calendar date — raw string end-to-end (DateCell's calendar-date law)
  onChange: (value: string) => void;
  // BR-PAY-033: the consumer's proposed default (entry: today in tenant TZ;
  // import: from file data). Committed into the consumer's state once on mount
  // so what the user sees is exactly what posts; typing over it always wins.
  prefill?: string;
  // IS-8: tenant Regional date format (Settings → Company), REQUIRED like
  // DateCell's — the native picker's own display follows the BROWSER locale,
  // so the tenant-format rendering shows under the input via the ONE
  // formatting path (regionalDateEcho → formatDate; BR-SHL-023).
  dateFormat: RegionalDateFormat;
  required?: boolean;
  /**
   * **THE EARLIEST AND LATEST DATE THIS FIELD WILL ACCEPT** (`DEF-MET-4974`).
   *
   * B14 rule 7 is RATIFIED — a date field is the date input, with its calendar
   * affordance and keyed entry — and until 2026-09-12 this control had no
   * vocabulary for a bound at all, so no screen could express one even where
   * the rule that bounds it was already written down. Five date inputs across
   * the asset action screens rendered `min=null max=null`, and product-wide
   * there was exactly ONE `min=` on any date input.
   *
   * ⚠ **A BOUND A HELP SENTENCE PROMISES MUST ALSO BE PASSED HERE.** A helper
   * reading *"Cannot be in the future"* over an unbounded input is good copy to
   * every check this repo has and a lie to the clerk who types tomorrow.
   *
   * Both are optional and both are `YYYY-MM-DD`, the same calendar-date string
   * `value` uses — no timezone, ever. Absent means unbounded, so every existing
   * date field renders byte-for-byte what it rendered before.
   */
  min?: string;
  max?: string;
  help?: string;
  error?: string;
  /**
   * Shown, and not editable HERE — the same opt-in `TextField` has carried
   * since the kit was written, added to this control for CR-087's tax
   * correction form (B14 rule 38: *"if the kit genuinely lacks a piece the
   * drawing needs … ADD IT TO THE KIT as an opt-in, so nothing existing
   * moves"*). Absent means editable, so every existing date field renders
   * byte-for-byte what it rendered before.
   *
   * ⚠ **A DISABLED FIELD OWES THE READER ITS REASON** (BR-SHL-025). Pass
   * `help` beside it saying why, or the clerk meets a box that will not take
   * their typing and no sentence explaining it.
   */
  disabled?: boolean;
  /**
   * The label is announced and not drawn — for a control in a table cell whose
   * COLUMN HEADER is the label. See `FieldLabel`, and `HIDDEN_FIELD` for why
   * the wrapper is positioned. Opt-in; absent renders exactly what every
   * existing caller renders today.
   */
  labelHidden?: boolean;
  /**
   * **THE BOX ITSELF SHOWS THE UTILITY'S DATE FORMAT** — `01-Aug-26`, not the
   * browser's `01/08/2026` — with a calendar button beside it
   * (`DEF-CUS-6358`, PO 2026-09-23: pickers follow the utility's date format).
   *
   * ⚠ **OPT-IN, ADDED UNDER B14 RULE 36 — ABSENT RENDERS BYTE FOR BYTE WHAT
   * EVERY EXISTING CALLER RENDERS TODAY.** A native `<input type="date">` can
   * only draw the BROWSER's format, which is why the IS-8 echo line exists
   * under it; the PO read that as a date printed twice (*"01/08/2026"* in the
   * box, *"01-Aug-26"* under it). With this on, the box is a text input in the
   * tenant's format, parsed by `parseRegionalDate` — the mirror of
   * `formatDate`, in the same file — and the native picker is kept behind the
   * calendar button only for its calendar, so there is nothing to echo.
   */
  regional?: boolean;
  /**
   * **TODAY, AS A ONE-CLICK SHORTCUT** — `CR-142-BRC07` `P2.7`, drawn on 2·1a
   * (`09 Reports Build Brief.pdf` p024, note ②).
   *
   * The `YYYY-MM-DD` the CALLER calls today, in the TENANT's zone. Absent draws
   * no control at all, so every existing date field in the product renders
   * byte-for-byte what it rendered before. Present draws a small ghost button
   * under the input that writes exactly this value.
   *
   * ⚠ **IT IS NOT `prefill`.** `prefill` proposes a value the moment the field
   * mounts; this writes only when a person presses it, so a bookmarked report
   * carrying an as-of date is never quietly moved to today by being opened.
   */
  todayValue?: string;
}) {
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError);
  const { value, prefill, onChange } = props;
  // BR-PAY-033: propose ONCE on mount; never fight the user afterwards.
  const proposed = useRef(false);
  useEffect(() => {
    if (proposed.current) {
      return;
    }
    proposed.current = true;
    if (value === "" && prefill !== undefined) {
      onChange(prefill);
    }
  }, [value, prefill, onChange]);
  const shown = resolveDateInputValue(value, prefill);
  const echo = props.regional === true ? null : regionalDateEcho(shown, props.dateFormat);
  const [typedBadly, setTypedBadly] = useState(false);
  const translate = useTranslation().t;
  const formatError = translate("forms.date.useFormat", {
    format: props.dateFormat,
    defaultValue: "Use {{format}}.",
  });
  // B14 rule 33 — a LABEL, one word, no sentence.
  const todayLabel = translate("forms.date.today", { defaultValue: "Today" });
  const hasToday = props.todayValue !== undefined && props.disabled !== true;
  const shownError = error ?? (typedBadly ? formatError : undefined);
  return (
    <div className={props.labelHidden === true ? HIDDEN_FIELD : "field"}>
      <FieldLabel
        htmlFor={props.id}
        label={props.label}
        required={props.required === true}
        hidden={props.labelHidden}
      />
      {/* ⚠ **THE `Today` SHORTCUT SITS BESIDE THE BOX, NOT UNDER IT**
          (`DEF-REP-7012`). Under it, this field is one line taller than a
          `<select>`, and `.fin-params` aligns its children on `flex-end` — so
          on the billing register *From* and *To* pushed *Bill type* and
          *Service* down and the four labels sat on two baselines. The Product
          Owner asked for one row with the labels level and *"the shortcut not
          changing the row height"*, and beside the box is the only place that
          costs no height at all.

          ⚠ **BESIDE, AND NOT INSIDE, AND THE DRAWING SAYS INSIDE.** 2·1a and
          2·1b (p024/p025) both draw `Today` within the date box at its right
          edge — and a native `<input type="date">` already owns that inset
          with its own calendar glyph, which is browser chrome this product
          cannot move. B14 rule 44: the drawing says WHAT is on the screen and
          our standard says HOW it is built. The divergence is recorded in the
          decision log rather than silently taken.

          ⚠ **THE WRAPPER EXISTS ONLY WHEN THERE IS A BUTTON TO PUT IN IT**, so
          every one of the product's other date fields renders byte-for-byte
          what it rendered before — and `.field > label` is the only
          direct-child rule in the stylesheet, so the label is untouched
          either way. `RegionalDateInput` already uses exactly this shape for
          its own calendar button. */}
      <div className={hasToday ? "flex items-stretch gap-2" : "contents"}>
        {props.regional === true ? (
          <RegionalDateInput
            id={props.id}
            value={shown}
            onChange={props.onChange}
            onTypedBadly={setTypedBadly}
            dateFormat={props.dateFormat}
            min={props.min}
            max={props.max}
            disabled={props.disabled === true}
            required={props.required === true}
            invalid={shownError !== undefined}
            describedBy={describedBy(props.id, props.help !== undefined, shownError !== undefined)}
          />
        ) : (
          <input
            id={props.id}
            // BR-SHL-033: native date picker; the same input accepts manual typing.
            type="date"
            className={`${inputClass(false, error !== undefined)}${hasToday ? " min-w-0 flex-1" : ""}`}
            value={shown}
            aria-required={props.required === true ? true : undefined}
            aria-invalid={error !== undefined ? true : undefined}
            aria-describedby={describedBy(props.id, props.help !== undefined, error !== undefined)}
            // B14 rule 7 / DEF-MET-4974: absent stays absent — React omits the
            // attribute for `undefined`, so an unbounded field is unchanged.
            min={props.min}
            max={props.max}
            disabled={props.disabled === true}
            onChange={(e) => props.onChange(e.target.value)}
          />
        )}
        {hasToday && (
          // `CR-142-BRC07` `P2.7` — the one-click jump to today, drawn on 2·1a's
          // **As of** field (`09 Reports Build Brief.pdf` p024, note ②, read as
          // an image per B14 rule 42). It is a SHORTCUT and never a default: it
          // writes only when pressed, so a saved link carrying a date is not
          // quietly moved to today by being opened.
          //
          // ⚠ **THE CALLER SUPPLIES THE DATE.** `new Date()` here would read the
          // BROWSER's zone, and a clerk in Denver opening a Chicago utility's
          // report would get yesterday for six hours a day — the same
          // calendar-date law that keeps `Date` out of `isCalendarDate`.
          //
          // ⚠ **OPT-IN (B14 rule 36).** Absent renders byte-for-byte what every
          // existing date field renders today; nothing in the product moves.
          <Button
            variant="ghost"
            size="sm"
            onClick={() => props.onChange(props.todayValue ?? "")}
          >
            {todayLabel}
          </Button>
        )}
      </div>
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {echo !== null && (
        // ⛔ **IS-8 regional rendering, SHOWN ONLY WHEN IT SAYS SOMETHING THE
        // INPUT DOES NOT (CR-043 finding 15).** The native control renders in
        // the BROWSER's locale, not the tenant's, so this line is the only
        // place a tenant whose format differs ever sees theirs — and where the
        // two agree it printed the same eight characters twice, directly under
        // themselves. `regionalDateEcho` owns that decision, in the one date
        // formatting path (BR-SHL-023); this component only renders what it
        // returns. A calendar date never routes through a timezone.
        <p className="field-date-display" aria-hidden="true">
          {echo}
        </p>
      )}
      {shownError !== undefined && <FieldError id={`${props.id}-error`} message={shownError} />}
    </div>
  );
}

/**
 * `DatePickerField`'s `regional` box — a text input in the utility's own date
 * format and a calendar button (`DEF-CUS-6358`).
 *
 * ⚠ **WHAT IT HANDS ITS OWNER IS ALWAYS A REAL `YYYY-MM-DD` OR `""`.** Text
 * that is not a date in the format — `31-Feb-26`, `12-Au` half typed — clears
 * the value rather than keeping the last good one, so a required field refuses
 * on Continue instead of committing a date the box no longer shows. The words
 * stay in the box so nothing a person typed is lost, and on leaving the field
 * the format is named under it.
 *
 * ⚠ **THE NATIVE INPUT STAYS, FOR ITS CALENDAR ONLY.** It is zero-sized inside
 * a `relative` wrapper (so it is laid out against this field, never against
 * the page — `DEF-CUS-6366`'s lesson), out of the tab order and hidden from
 * assistive technology; the calendar button opens it with `showPicker()`, and
 * a browser without that method gets focus on it instead.
 */
export function RegionalDateInput(props: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onTypedBadly: (bad: boolean) => void;
  dateFormat: RegionalDateFormat;
  min?: string;
  max?: string;
  disabled: boolean;
  required: boolean;
  invalid: boolean;
  describedBy: string | undefined;
}) {
  const { t } = useTranslation();
  const native = useRef<HTMLInputElement>(null);
  const show = (iso: string): string => (iso === "" ? "" : formatDate(iso, "UTC", props.dateFormat));
  const [text, setText] = useState(() => show(props.value));
  const read = (typed: string): string | null =>
    parseRegionalDate(typed, props.dateFormat, { max: props.max });
  // A value set from OUTSIDE — a prefill, the calendar, a resumed draft —
  // redraws the box; the person's own half-typed text is never overwritten.
  useEffect(() => {
    const parsed = read(text);
    if ((parsed ?? "") !== props.value && !(props.value === "" && text !== "")) {
      setText(show(props.value));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.value, props.dateFormat]);
  return (
    <div className="relative flex items-stretch gap-2" data-regional-date={props.dateFormat}>
      <input
        id={props.id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        // Tabular figures, but LEFT-aligned like every other text box: a
        // right-aligned date in a full-width field sits a screen away from its
        // label (measured on the move-in's step 3, 2026-09-24).
        className={`${inputClass(false, props.invalid, props.disabled)} min-w-0 flex-1 tabular-nums`}
        value={text}
        placeholder={props.dateFormat}
        disabled={props.disabled}
        aria-required={props.required ? true : undefined}
        aria-invalid={props.invalid ? true : undefined}
        aria-describedby={props.describedBy}
        onChange={(e) => {
          const typed = e.target.value;
          setText(typed);
          const parsed = read(typed);
          props.onTypedBadly(false);
          props.onChange(parsed ?? "");
        }}
        onBlur={() => {
          const parsed = read(text);
          if (parsed !== null) {
            setText(show(parsed));
          }
          props.onTypedBadly(text.trim() !== "" && parsed === null);
        }}
      />
      <input
        ref={native}
        type="date"
        tabIndex={-1}
        aria-hidden="true"
        className="pointer-events-none absolute bottom-0 left-0 size-0 opacity-0"
        value={props.value}
        min={props.min}
        max={props.max}
        onChange={(e) => {
          props.onChange(e.target.value);
          setText(show(e.target.value));
          props.onTypedBadly(false);
        }}
      />
      <Button
        variant="secondary"
        aria-label={t("forms.date.openCalendar", { defaultValue: "Open calendar" })}
        title={t("forms.date.openCalendar", { defaultValue: "Open calendar" })}
        disabled={props.disabled}
        data-date-calendar=""
        onClick={() => {
          const el = native.current;
          if (el === null) return;
          try {
            el.showPicker();
          } catch {
            el.focus();
          }
        }}
      >
        <CalendarIcon />
      </Button>
    </div>
  );
}

/**
 * **A MOMENT A PERSON STATES — DATE AND TIME IN ONE CONTROL, PREFILLED WITH
 * NOW** (`CR-136-BRC07`, PO ruling 2026-09-23, verbatim: *"show date and time
 * pciker and deult should be as per date time format set by utility and
 * timezone - show the detault time"*).
 *
 * ⚠ **THE VALUE IS A WALL CLOCK IN THE TENANT'S ZONE, NOT AN INSTANT.**
 * `YYYY-MM-DDTHH:mm`, which is what `<input type="datetime-local">` holds and
 * what `nowInZone` proposes. It travels to the server naive and is anchored
 * there in the tenant's own zone (`apps/payments/api._moment`, BR-TEN-081 /
 * OQ-153: *"a time of day with no zone … came from a human in that utility"*).
 * Deriving the tenant's UTC offset in the browser would compute the same
 * answer a second time, in a second place, with DST in it.
 *
 * ⚠ **WHY IT IS IN THE KIT AND NOT IN THE ONE SCREEN THAT NEEDED IT.** B14
 * rule 43 — a piece of UI is built as a COMPONENT; standalone code inside a
 * page is not reuse — and rule 38's rider, *"if the kit genuinely lacks a
 * piece the drawing needs … ADD IT TO THE KIT as an opt-in, so nothing
 * existing moves"*. The kit had `DatePickerField` and no time of day at all;
 * this is the first `datetime-local` in the product. Nothing already built
 * changes by a pixel.
 *
 * Its shape is `DatePickerField`'s, deliberately and line for line: the same
 * BR-PAY-033 propose-once-on-mount default, the same native control that also
 * takes manual typing (BR-SHL-033), and the same IS-8 echo beneath it — the
 * only place a tenant whose format is not the browser's ever sees theirs.
 */
export function DateTimeField(props: {
  id: string;
  label: string;
  /** `YYYY-MM-DDTHH:mm` — the tenant's wall clock, a raw string end to end. */
  value: string;
  onChange: (value: string) => void;
  /** BR-PAY-033: the proposed default, committed into the consumer's state
   *  once on mount, so what the clerk sees is exactly what posts. Typing over
   *  it always wins. `nowInZone(timeZone)` is what a consumer passes. */
  prefill?: string;
  /** IS-8 — the tenant's Regional format (Settings → Company), REQUIRED like
   *  `DatePickerField`'s. The native picker renders in the BROWSER's locale. */
  dateFormat: RegionalDateFormat;
  required?: boolean;
  /**
   * **THE EARLIEST AND LATEST MOMENT THIS FIELD WILL ACCEPT**, both wall
   * clocks in the same zone as `value` — `sameDayBounds(timeZone)` is what a
   * counter screen passes (`BR-PAY-1191`).
   *
   * ⚠ **A BOUND HERE IS NOT THE RULE AND MUST NOT BE THE ONLY COPY OF IT.**
   * `DatePickerField`'s own note says a bound a help sentence promises must
   * also be passed; this is the other direction — a bound a SERVER enforces
   * must also be drawn, or the clerk meets a refusal the control gave them no
   * way to avoid. Absent means unbounded, so a later caller that has no such
   * rule renders exactly what it would have rendered.
   */
  min?: string;
  max?: string;
}) {
  // `DEF-RAT-7800` — through the shared resolver like every other field, so an
  // empty message cannot paint this box red with nothing under it to read.
  // This control takes no `error` prop of its own; the context is its only
  // source, which is why the first argument is `undefined`.
  const suppliedError = useFieldError(props.id);
  const contextError = fieldErrorToShow(undefined, suppliedError);
  const { value, prefill, onChange } = props;
  // BR-PAY-033: propose ONCE on mount; never fight the user afterwards.
  const proposed = useRef(false);
  useEffect(() => {
    if (proposed.current) {
      return;
    }
    proposed.current = true;
    if (value === "" && prefill !== undefined) {
      onChange(prefill);
    }
  }, [value, prefill, onChange]);
  // The same resolver the date picker uses: an empty value shows the proposal.
  const shown = resolveDateInputValue(value, prefill);
  const echo = regionalDateTimeEcho(shown, props.dateFormat);
  return (
    <div className="field">
      <FieldLabel htmlFor={props.id} label={props.label} required={props.required === true} />
      <input
        id={props.id}
        // BR-SHL-033: the native picker; the same input accepts manual typing.
        type="datetime-local"
        className={inputClass(false, contextError !== undefined)}
        value={shown}
        aria-required={props.required === true ? true : undefined}
        aria-invalid={contextError !== undefined ? true : undefined}
        aria-describedby={describedBy(props.id, false, contextError !== undefined)}
        // React omits an `undefined` attribute, so an unbounded field is
        // unchanged — the same posture `DatePickerField` takes (DEF-MET-4974).
        min={props.min}
        max={props.max}
        onChange={(e) => props.onChange(e.target.value)}
      />
      {echo !== null && (
        // ⛔ IS-8, and shown only when it says something the control does not —
        // CR-043 finding 15, which is why this is not an unconditional line.
        <p className="field-date-display" aria-hidden="true">
          {echo}
        </p>
      )}
      {contextError !== undefined && (
        <FieldError id={`${props.id}-error`} message={contextError} />
      )}
    </div>
  );
}

/** Re-exported so a consumer of this kit proposes its default and bounds it
 *  through the ONE formatting path rather than reaching for `Intl` itself
 *  (BR-SHL-023), and so the four counter screens cannot each derive the
 *  utility's day boundary their own way. */
export { nowInZone, sameDayBounds };

// BR-SHL-033: the type-ahead filter, pure and testable. Case-insensitive
// substring match on the option LABEL (the text the user reads — GL numbers,
// account numbers etc. live in labels like "4100 — Late fees").
/**
 * **WHAT A TYPE-TO-FILTER BOX MATCHES ON (`DEF-MET-4804`).**
 *
 * The label, and — when an option carries one — an extra `search` string that
 * is NOT drawn.
 *
 * ⚠ **THE EXTRA EXISTS BECAUSE A HELP LINE PROMISED SOMETHING THE LABEL COULD
 * NOT KEEP.** The add-units building picker says *"By address, property number
 * or parcel"* and its labels hold only the address and the number, so a clerk
 * typing a parcel got `No matching options` — not a slow search, not a wrong
 * result, but a permanent silent nothing on a promise the screen made in
 * writing.
 *
 * ⚠ **AND WIDENING THE LABEL WAS THE WRONG FIX.** The frame draws the label as
 * `412 Cypress Row`; a parcel key bolted onto it would put a reference nobody
 * reads in front of every clerk to make a minority of searches work. So the
 * searchable text and the readable text are two fields now, which is what they
 * always were in substance.
 *
 * Additive: every existing caller passes no `search` and behaves exactly as
 * before.
 */
export function filterOptions(options: FieldOption[], query: string): FieldOption[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") {
    return options;
  }
  return options.filter((option) => {
    const haystack = `${option.label} ${option.search ?? ""}`.toLowerCase();
    return haystack.includes(needle);
  });
}

// Keyboard stepping through the filtered list: wraps at both ends; from
// "nothing active" (-1) ArrowDown lands on the first option, ArrowUp the last.
export function stepActiveOption(active: number, delta: 1 | -1, count: number): number {
  if (count === 0) {
    return -1;
  }
  if (active === -1) {
    return delta === 1 ? 0 : count - 1;
  }
  return (active + delta + count) % count;
}

export function SearchSelectField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: FieldOption[]; // the long list — BR-SHL-033 mandates this control past LONG_LIST_THRESHOLD
  required?: boolean;
  help?: string;
  placeholder?: string;
  error?: string;
  /**
   * **SHOWN, AND NOT USABLE HERE** — the same opt-in `TextField` has carried
   * since the kit was written and `DatePickerField` gained for `CR-087`
   * (B14 rule 38: *"if the kit genuinely lacks a piece the drawing needs … ADD
   * IT TO THE KIT as an opt-in, so nothing existing moves"*). Absent means
   * usable, so every existing search picker renders byte-for-byte what it
   * rendered before.
   *
   * ⚠ **IT EXISTS SO A PICKER WHOSE LIST DID NOT LOAD STAYS A PICKER**
   * (`DEF-MET-4977`). The alternative the log-repair screen used for a month
   * was to swap the control for a bare text box holding a uuid — B14 rule 31
   * broken, and a task nobody could actually perform, since no screen in the
   * product shows a clerk a technician's uuid. A control that changes TYPE
   * under failure teaches a person the product is two different products.
   *
   * ⚠ **A DISABLED FIELD OWES THE READER ITS REASON** (`BR-SHL-025`, and
   * `BR-AST-534` extends it from role to state). Pass `help` beside it saying
   * why, or the clerk meets a box that will not take their typing and no
   * sentence explaining it.
   */
  disabled?: boolean;
  /**
   * **A SEARCHABLE DROPDOWN, NOT A SEARCH BOX — OPT-IN, ADDED 2026-10-01
   * (`DEF-RAT-8735`).** The PO, on the rate schedule's base charge code: *"can
   * you make it searable draop down"*. Without this the control is a text box
   * that opens its list only once something is typed, so a clerk who does not
   * already know a code has nothing to pick from.
   *
   * With it: the shared chevron is drawn, and a click or focus opens the WHOLE
   * list; typing still narrows it. Absent keeps every existing caller exactly as
   * it renders today (B14 rule 36: extend the kit as an opt-in).
   */
  dropdown?: boolean;
  /**
   * **THE LIST'S OWN WORDS FOR "NOTHING HERE" — OPT-IN, ADDED 2026-10-01
   * (`CR-156-BRC10`, the charge-code Add picker).** The drawing reads *"No
   * free code. Add one in Settings."* when the list is EMPTY and *"No code
   * found."* when a search matches nothing — two different facts the kit's one
   * generic sentence could not tell apart. Absent keeps every existing caller
   * on `forms.searchSelect.noMatches`, unchanged (B14 rule 36).
   */
  emptyText?: string;
  noMatchText?: string;
  /**
   * The label is announced and not drawn — for a picker in a table cell whose
   * COLUMN HEADER is the label, exactly as `SelectField.labelHidden`. Added
   * 2026-10-05 under B14 rule 36 with its first caller, the move-in's *Field
   * visit* *Work order* cell (`CR-171-BRC10` image 30). Absent renders exactly
   * what every existing search picker renders.
   */
  labelHidden?: boolean;
  /**
   * **THE SAME PICKER, HOLDING A VALUE THAT CANNOT CHANGE — OPT-IN, ADDED
   * 2026-10-06 (`DEF-RAT-9806`).** The Edit charge code's *Code* is the Add
   * form's searchable dropdown (PO: *"code field should be dropdown ; as per
   * add form"*), locked because the code is on sent bills (hard rule 4). It
   * stays a `combobox` that never opens, drawn in `SelectField.locked`'s look.
   * Absent renders exactly what every existing search picker renders.
   */
  locked?: boolean;
}) {
  const { t } = useTranslation();
  const contextError = useFieldError(props.id);
  const error = fieldErrorToShow(props.error, contextError, props.locked === true);
  const selected = props.options.find((option) => option.value === props.value);
  const dropdown = props.dropdown === true;

  const [open, setOpen] = useState(false);
  // What the input shows: the selected label at rest, the query while typing.
  const [text, setText] = useState(selected?.label ?? "");
  const [query, setQuery] = useState(""); // the debouncer-COMMITTED effective query
  const [active, setActive] = useState(-1);
  // `DEF-RAT-8835` — "the selected label at rest" HOLDS AFTER MOUNT TOO. The
  // state above is seeded once, and a caller whose value or options arrive
  // later (an Edit that loads the record and the code list) showed an EMPTY
  // field over a stored choice, or the old label after the value was reset by
  // the caller. While the list is closed the input is the selected label.
  const selectedLabel = selected?.label ?? "";
  useEffect(() => {
    if (!open) setText(selectedLabel);
    // `open` is read, not watched: closing already resets the text itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLabel]);

  // IS-3 mechanics (300 ms, min 2 chars) through the ONE createSearchDebouncer
  // — never re-implemented (DataTable/AppShell precedent).
  const commitRef = useRef<(q: string) => void>(() => undefined);
  commitRef.current = (q) => {
    setQuery(q);
    setActive(-1);
  };
  const debouncerRef = useRef<SearchDebouncer | null>(null);
  if (debouncerRef.current === null) {
    debouncerRef.current = createSearchDebouncer((q) => commitRef.current(q));
  }
  const debouncer = debouncerRef.current;
  useEffect(() => {
    const activeDebouncer = debouncerRef.current;
    return () => activeDebouncer?.clear(); // cancel a pending fire on unmount
  }, []);

  const filtered = filterOptions(props.options, query);
  const listId = `${props.id}-listbox`;
  const activeOption = open && active >= 0 && active < filtered.length ? filtered[active] : null;

  function closeAndReset(): void {
    setOpen(false);
    setQuery("");
    setActive(-1);
    debouncer.clear();
    setText(selected?.label ?? "");
  }

  function pick(option: FieldOption): void {
    props.onChange(option.value);
    setOpen(false);
    setQuery("");
    setActive(-1);
    debouncer.clear();
    setText(option.label);
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault(); // keyboard-navigable list, not caret movement
      setOpen(true);
      setActive(stepActiveOption(active, event.key === "ArrowDown" ? 1 : -1, filtered.length));
    } else if (event.key === "Enter" && activeOption !== null) {
      event.preventDefault(); // picking an option must not submit the form
      pick(activeOption);
    } else if (event.key === "Escape" && open) {
      // IS-10: the FIRST Esc closes the list only — it must not bubble to
      // ModalShell and close the whole modal; the next Esc does.
      event.stopPropagation();
      closeAndReset();
    }
  }

  if (props.locked === true) {
    return (
      <div className={props.labelHidden === true ? HIDDEN_FIELD : "field"} data-locked-field={props.id}>
        <FieldLabel
          htmlFor={props.id}
          label={props.label}
          required={props.required === true}
          hidden={props.labelHidden}
        />
        <LockedBox
          id={props.id}
          role="combobox"
          text={selectedLabel || (props.placeholder ?? "")}
          describedBy={describedBy(props.id, props.help !== undefined, false)}
        />
        {props.help !== undefined && (
          <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
            {props.help}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className={props.labelHidden === true ? HIDDEN_FIELD : "field"}>
      <FieldLabel
        htmlFor={props.id}
        label={props.label}
        required={props.required === true}
        hidden={props.labelHidden}
      />
      <div className="search-select">
        <input
          id={props.id}
          type="text"
          // BR-SHL-033 type-ahead: the ARIA combobox pattern over a listbox.
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            activeOption !== null ? `${props.id}-opt-${activeOption.value}` : undefined
          }
          autoComplete="off"
          className={inputClass(false, error !== undefined)}
          value={text}
          placeholder={props.placeholder}
          aria-required={props.required === true ? true : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          aria-describedby={describedBy(props.id, props.help !== undefined, error !== undefined)}
          // `DEF-MET-4977` — absent stays absent: React omits the attribute for
          // `undefined`, so an enabled picker is unchanged.
          disabled={props.disabled === true}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            debouncer.type(e.target.value);
          }}
          onBlur={closeAndReset}
          onKeyDown={handleKeyDown}
          // `DEF-RAT-8735` — a dropdown opens on a click or a tab-in, showing
          // every option; the selected label is highlighted so typing replaces it.
          onFocus={
            dropdown
              ? (e) => {
                  setOpen(true);
                  e.currentTarget.select();
                }
              : undefined
          }
          onClick={dropdown ? () => setOpen(true) : undefined}
        />
        {dropdown && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 right-2.5 flex -translate-y-1/2 text-neutral-700"
            data-search-select-chevron={props.id}
          >
            <ChevronDownIcon />
          </span>
        )}
        {/* The listbox stays in the DOM (hidden when closed) so the combobox
            wiring is inspectable and testable without a live browser. */}
        <ul className="search-select-list" role="listbox" id={listId} hidden={!open}>
          {filtered.map((option, index) => (
            <li
              key={option.value}
              id={`${props.id}-opt-${option.value}`}
              role="option"
              aria-selected={option.value === props.value}
              // A WHOLE LITERAL PER BRANCH, not `search-select-opt${…}`. Both
              // names are still FormModal.css's, and both spellings render the
              // same thing — but DEF-569 put this file in the Route B ledger,
              // and `routeBUtilities.test.ts` refuses an interpolation glued to
              // a class stem there because Tailwind's scanner cannot see a name
              // that only exists at runtime. Written this way it stays readable
              // to both readers.
              className={index === active ? "search-select-opt active" : "search-select-opt"}
              // Keep focus in the input so onBlur cannot swallow the click.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(option)}
            >
              {option.detail === undefined ? (
                option.label
              ) : (
                <span className="flex items-baseline justify-between gap-4">
                  <span>{option.label}</span>
                  <span data-option-detail="" className="text-sm italic text-neutral-600">
                    {option.detail}
                  </span>
                </span>
              )}
            </li>
          ))}
          {filtered.length === 0 && (
            <li role="presentation" className="search-select-empty" data-search-select-empty="">
              {props.options.length === 0 && props.emptyText !== undefined
                ? props.emptyText
                : (props.noMatchText ?? t("forms.searchSelect.noMatches"))}
            </li>
          )}
        </ul>
      </div>
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={`${props.id}-help`}>
          {props.help}
        </p>
      )}
      {error !== undefined && <FieldError id={`${props.id}-error`} message={error} />}
    </div>
  );
}

// ── ModalShell — the ONE A12 modal shell ───────────────────────────────────
// Fixed overlay + card + header/body/footer, ported shape from the prototype's
// settings modals. FE-04 ConfirmDialog composes this; consuming screens supply
// slot content only.

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// IS-10: focus stays inside the modal — Tab from the last control wraps to the
// first and Shift+Tab from the first wraps to the last.
function trapFocus(event: ReactKeyboardEvent<HTMLDivElement>, card: HTMLDivElement | null): void {
  if (card === null) {
    return;
  }
  const focusables = card.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
  if (focusables.length === 0) {
    return;
  }
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && (active === first || active === card)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

/**
 * ⚠ **THE 560px CARD IS CAPPED TOO, AND THIS OVERTURNS A SENTENCE ABOVE IT.**
 *
 * `DEF-SHL-5158`. When the wide variant was capped, the reasoning recorded for
 * leaving the default alone was that *"the 560px cards every other caller draws
 * are SHORT"*. **Measured in Chromium at 1440x900, they are not:** Record a
 * payment **1142px**, Write to customer **1329px**, Edit account **1199px** — in
 * a 900px window. The card grew past the screen, `.modal-overlay` scrolled the
 * whole thing, and the ✕ went off the top with it. A clerk could not close the
 * dialog without scrolling the page back up, which is the same fault the wide
 * variant was fixed for, one tier down. PO 2026-09-13: *"fix all 22 actions"*.
 *
 * **It is a no-op for every dialog that already fits**, which is what makes
 * sweeping the whole kit safe rather than a decision: `max-height` bites only
 * when the content exceeds it, so Add note (516px) and the rest render
 * identically to the pixel. Only a dialog that was already broken changes.
 *
 * The three utilities do one job each, and the middle one is load-bearing:
 * `min-h-0` on both the form and the body, because a flex child defaults to
 * `min-height: auto` and refuses to shrink below its content — without it the
 * cap changes nothing at all until the content gets tall, and then clips
 * instead of scrolling. That is hard-won law 7's *incapable of failing* wearing
 * CSS. The head keeps its natural height and the foot stays pinned, so the ✕
 * and the commit button are both always on screen and the FIELDS are what
 * scroll.
 *
 * `overflow-y-auto` on the card is the belt: a caller that draws no
 * `.modal-body` cannot clip, it scrolls. Every caller measured has one, so this
 * never engages today — it is there so the next one cannot lose content.
 */
const CAPPED =
  "modal-card flex max-h-[calc(100vh-64px)] flex-col overflow-y-auto " +
  "[&>form]:flex [&>form]:min-h-0 [&>form]:flex-1 [&>form]:flex-col " +
  "[&_.modal-body]:min-h-0 [&_.modal-body]:flex-1 [&_.modal-body]:overflow-y-auto";

/**
 * `DEF-SHL-10775` — the last element that took focus, its table row, and whether
 * it sat in a row's "More actions" menu, recorded when it took focus. A dialog
 * opened from that menu can find its way back to the row even when the table
 * re-rendered the menu before the dialog's own effect could ask the page.
 */
const lastFocus: { el: HTMLElement | null; row: HTMLElement | null; inMenu: boolean } = {
  el: null,
  row: null,
  inMenu: false,
};
if (typeof document !== "undefined") {
  document.addEventListener(
    "focusin",
    (event) => {
      if (!(event.target instanceof HTMLElement)) return;
      lastFocus.el = event.target;
      lastFocus.row = event.target.closest("tr");
      lastFocus.inMenu = event.target.closest("details") !== null;
    },
    true,
  );
}

export function ModalShell(props: {
  title: string;
  kicker?: string;
  onClose: () => void;
  role?: "dialog" | "alertdialog"; // alertdialog for FE-04 confirms
  /**
   * **A DIALOG WIDE ENOUGH TO HOLD A WHOLE SCREEN** — absent means the 560px
   * card every existing caller draws, so nothing already built moves by a
   * pixel.
   *
   * `CR-094-BRC01` wave L (`BR-CUS-1051`) mounts eight existing multi-step
   * screens over the account rather than re-typing them as forms, and a
   * six-step wizard inside a 560px card is not the same screen. The utility
   * carries `!` because `.modal-card` sets `width` as a class of equal
   * specificity and source order between a stylesheet and the compiled
   * utilities is not a thing to bet a layout on.
   *
   * ⚠ **AND A WIDE CARD IS CAPPED TO THE VIEWPORT AND SCROLLS ITS OWN BODY.**
   * Measured at 1440x900 before this change: the mounted screens rendered
   * **876px, 894px, 907px, 939px, 1113px and 1585px** tall inside a 900px
   * window, so the CARD grew past the screen and `.modal-overlay` scrolled the
   * whole thing — taking the ✕ off the top of the screen with it. That is what
   * reads as *"a near-full-screen panel"*: not the width, the height. A dialog
   * ends at the edge of the window; `max-h-[calc(100vh-64px)]` is the
   * overlay's own 32px inset top and bottom (B14 rule 39's scale) and the body
   * below scrolls inside it.
   *
   * **Only the wide variant takes this shape.** The 560px cards every other
   * caller draws are short, have scrolled the overlay since S12, and are not
   * what was reported — so they are not swept.
   */
  size?: "wide";
  /**
   * **THE HEAD CARRIES NO BAND AT ALL, AND `title` BECOMES THE ACCESSIBLE
   * NAME.**
   *
   * For a dialog hosting a screen that draws its OWN `PageHeader` — kicker,
   * 32px title (B14 rule 40), roll-up — a second heading in the dialog head is
   * two headings on one surface and spends the description budget B14 rule 32
   * caps at one sentence per section. The dialog is still NAMED: `aria-label`
   * carries exactly the string the visible head would have shown, so a screen
   * reader announces the same words either way.
   *
   * ⚠ **THAT REASONING WAS RIGHT AND THE RENDERING WAS NOT (`DEF-CUS-5151`).**
   * `titleHidden` emptied the head's TEXT and left the head's BOX: `.modal-head`
   * is `padding: 20px 24px` around a 36px icon button over a 2px rule, so six
   * of the eight account overlays drew **an 80px blank strip with a lone ✕**
   * above the screen they mounted, and the mounted heading began 181px down.
   * The Product Owner reported it off the running product. A head with nothing
   * in it is not a head: when there is no kicker AND no title the band is not
   * rendered at all, and the ✕ is positioned into the card's own top-right
   * corner where it costs no height.
   *
   * `kicker` still forces the band — a dialog naming its subject has something
   * to draw, and `issueCredit` is exactly that case.
   */
  titleHidden?: boolean;
  /**
   * **A COMMIT IS IN FLIGHT** (`DEF-SHL-6148`). `WorkingButton` disables the
   * submit while it is, and a focused control that becomes disabled loses
   * focus to `<body>` in every browser — outside the overlay whose `onKeyDown`
   * closes on Escape. So when `busy` goes back to false and focus is no longer
   * inside the card, it is returned to the card, the same call the open makes.
   * Absent means never busy: every caller that predates it is unchanged.
   */
  busy?: boolean;
  children: ReactNode; // .modal-body / .modal-foot blocks, supplied by the composer
}) {
  const { t } = useTranslation();
  const titleId = useId();
  const cardRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    /* ⚠ DEF-SHL-10686 — AND IT GOES BACK WHERE IT CAME FROM. The element that
       held focus when the dialog opened (the button that opened it) gets it
       back when the dialog closes, however it closes — Escape, Cancel, ✕ or
       a commit. Without this a keyboard user was dropped at the top of the
       page. Skipped when that element has left the page meanwhile. */
    const active =
      document.activeElement instanceof HTMLElement && document.activeElement !== document.body
        ? document.activeElement
        : null;
    // DEF-SHL-10775 — an opener inside a row's "More actions" menu. Two ways it
    // cannot take focus back, both seen on the Payments list: its <details> has
    // closed (a browser will not focus inside it), or the table re-rendered the
    // menu in the same render that opened this dialog, so the node — and with
    // it the page's focus — was gone before this effect ran. Either way focus
    // fell to the page. The menu's own summary takes it, found again in the
    // same table row when the old one has left.
    const fromMenu =
      active === null && lastFocus.el !== null && !lastFocus.el.isConnected && lastFocus.inMenu
        ? lastFocus
        : null;
    const opener = active ?? fromMenu?.el ?? null;
    const openerRow = active !== null ? active.closest("tr") : (fromMenu?.row ?? null);
    cardRef.current?.focus(); // IS-10: focus moves into the dialog on open
    return () => {
      if (opener === null) return;
      if (opener.isConnected) {
        const menu = opener.closest("details");
        const summary = menu !== null && !menu.open ? menu.querySelector("summary") : null;
        (summary ?? opener).focus();
        return;
      }
      if (opener.closest("details") !== null || fromMenu !== null) {
        if (openerRow !== null && openerRow.isConnected) {
          openerRow.querySelector<HTMLElement>("details > summary")?.focus();
        }
      }
    };
  }, []);
  const busy = props.busy === true;
  useEffect(() => {
    if (busy) return;
    const card = cardRef.current;
    // Only when focus was LOST — a field the refusal focused keeps it (A18 §5).
    if (card !== null && !card.contains(document.activeElement)) card.focus();
  }, [busy]);

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>): void {
    if (event.key === "Escape") {
      props.onClose(); // IS-10: modals close on Esc
      return;
    }
    if (event.key === "Tab") {
      trapFocus(event, cardRef.current);
    }
  }

  // **NOTHING TO PUT IN A HEAD MEANS NO HEAD.** The band exists to carry a
  // kicker and a title; with neither it is 80px of nothing over whatever the
  // dialog is hosting.
  const headIsBare = props.titleHidden === true && props.kicker === undefined;
  const closeButton = (
    <button
      type="button"
      className="btn btn-icon modal-close"
      aria-label={t("forms.close")}
      onClick={props.onClose}
    >
      ✕
    </button>
  );

  return (
    // IS-10: backdrop click closes; clicks inside the card never bubble out.
    <div className="modal-overlay" onClick={props.onClose} onKeyDown={handleKeyDown}>
      <div
        ref={cardRef}
        tabIndex={-1}
        className={
          props.size === "wide"
            ? "modal-card relative flex max-h-[calc(100vh-64px)] w-[min(1120px,100%)]! flex-col overflow-hidden"
            : `${CAPPED} ${headIsBare ? "relative" : ""}`
        }
        role={props.role ?? "dialog"}
        aria-modal="true"
        aria-labelledby={props.titleHidden === true ? undefined : titleId}
        aria-label={props.titleHidden === true ? props.title : undefined}
        onClick={(event) => event.stopPropagation()}
      >
        {headIsBare ? (
          // ⚠ **ABSOLUTE, SO IT RESERVES NO HEIGHT — and it stays on screen
          // because the wide card is capped to the window and the BODY is what
          // scrolls. 16px from both edges is the scale's `--space-4`; the
          // mounted `PageHeader` starts at the body's own 24px inset and its
          // top-right corner is empty on all seven screens (measured).
          // `z-20` clears the sticky step rails two wizards draw.
          <div className="absolute top-4 right-4 z-20">{closeButton}</div>
        ) : (
          <div className="modal-head">
            <div>
              {props.kicker !== undefined && <div className="modal-kicker">{props.kicker}</div>}
              {props.titleHidden !== true && (
                <h4 className="modal-title" id={titleId}>
                  {props.title}
                </h4>
              )}
            </div>
            {closeButton}
          </div>
        )}
        {props.size === "wide" ? (
          // `min-h-0` is load-bearing: a flex child defaults to `min-height:
          // auto`, which refuses to shrink below its content and would defeat
          // the cap above without changing one visible pixel until the content
          // got tall — law 7's *incapable of failing*, in CSS.
          <div className="min-h-0 flex-1 overflow-y-auto">{props.children}</div>
        ) : (
          props.children
        )}
      </div>
    </div>
  );
}

// ── FormModal — the frame ──────────────────────────────────────────────────

// A18 §5: submit re-validates and the viewport lands on the first error.
function scrollToFirstError(field: string | null): void {
  if (field === null || typeof document === "undefined") {
    return;
  }
  const input = document.getElementById(field);
  // ⚠ **OPTIONAL CALL, NOT A TIDY-UP — DO NOT "SIMPLIFY" IT BACK (`DEF-SHL-3938`).**
  // jsdom does not implement `scrollIntoView`, so the plain call THREW inside this
  // async submit path and took the `focus()` below with it — and the focus is the
  // requirement (A18 §5 lands the reader on the first error), while the scroll is
  // the nicety. It surfaced as an unhandled rejection that turned `vitest run` RED
  // at the branch tip for every form-modal test that submits an invalid form.
  input?.scrollIntoView?.({ block: "center" });
  input?.focus();
}

/**
 * **THE VALIDATE → POST → RENDER-THE-ENVELOPE WIRING, ONCE.**
 *
 * ⚠ **EXTRACTED 2026-09-23 (`DEF-PAY-6317`) AND `FormModal` NOW CALLS IT** —
 * it is not a second copy. The payments blueprint moves *Record a payment*
 * from a modal to a full page (p037, frame 2·3a), and a page needs exactly
 * this wiring with a different frame around it. Copying the submit handler
 * into a page component would have put B12 §3's envelope rendering, A18 §5's
 * first-error focus and `DEF-LED-6140`'s say-it-once rule in two places, and
 * the second copy is the one that stops being fixed.
 *
 * `FormModal`'s rendered output is byte-for-byte what it was before this hook
 * existed; the only change is where the code lives.
 */
/**
 * The value a field id names, as a comparable string (`DEF-SHL-9615`,
 * `DEF-PAY-10704`).
 *
 * A field id is the zod path joined with `.` — `resolutions.1.amount` is row
 * 2's amount — so the walk follows the same dots into objects AND arrays. A
 * path that leads nowhere reads as `undefined`, and two `undefined` reads are
 * equal, so an error on a field the values do not carry is simply kept.
 */
function valueAtField(values: unknown, field: string): string | undefined {
  let at: unknown = values;
  for (const segment of field === "" ? [] : field.split(".")) {
    if (at === null || typeof at !== "object") {
      return undefined;
    }
    at = (at as Record<string, unknown>)[segment];
  }
  return at === undefined ? undefined : JSON.stringify(at);
}

/** What each errored field held when its error was raised. */
function fieldValueSnapshot(
  values: unknown,
  fields: readonly string[],
): Record<string, string | undefined> {
  return Object.fromEntries(fields.map((field) => [field, valueAtField(values, field)]));
}

function useFormCommit(
  schema: ZodTypeAny,
  values: unknown,
  onSubmit: () => Promise<FormSubmitOutcome>,
) {
  const { t } = useTranslation();
  const [allFieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  // `DEF-SHL-9615` / `DEF-PAY-10704` — what each errored field held when its
  // error was raised, by the press (schema) or by the server.
  const [refusedValues, setRefusedValues] = useState<Record<string, string | undefined>>({});
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  // ⚠ **AN ERROR IS ABOUT THE VALUE IT WAS RAISED ON (`DEF-SHL-9615`, then
  // `DEF-PAY-10704`).** *"MTR-W34 is already in the register."* stayed under
  // Part number after the clerk retyped it VLV-GT1, until the next press — a
  // sentence about nothing on the screen. So a field's error is shown only
  // while the field still holds the value it was raised on; type it back and
  // it returns. A field `values` does not carry keeps its error (both reads
  // are `undefined`).
  //
  // ⚠ **THIS USED TO COVER SERVER REFUSALS ONLY, AND READ *"Schema errors are
  // untouched"*.** The S40 form then kept *"Enter an amount, using a period
  // for decimals."* under a perfectly good `-0.01` (lockbox audit LBX-02) and
  // could not clear it: its commit is disabled until the residual is zero
  // (`commitBlocked`), so the press BR-SHL-017 relies on to re-validate was
  // the one press the clerk could not make. The press still re-validates
  // everything, exactly as before; what changed is that a field the clerk has
  // since edited stops carrying a sentence about its old value. The match is
  // by the error's own PATH, so editing row 2 leaves row 1's error alone.
  const fieldErrors: Record<string, string> = {};
  for (const [field, message] of Object.entries(allFieldErrors)) {
    if (field in refusedValues && refusedValues[field] !== valueAtField(values, field)) continue;
    fieldErrors[field] = message;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (working) {
      return; // A18 §3: one submit in flight — double-clicks are harmless
    }
    // BR-SHL-017: submit stays enabled and re-validates on click; errors clear
    // per-field because the map is rebuilt from the current values each time.
    const result = collectFormErrors(schema, values);
    setFieldErrors(result.errors);
    setRefusedValues(fieldValueSnapshot(values, Object.keys(result.errors)));
    setFormMessage(null);
    if (result.count > 0) {
      scrollToFirstError(result.first);
      return; // the form stays put; nothing is posted (US-SHL-009 TC-1)
    }
    setWorking(true);
    try {
      const outcome = await onSubmit();
      if (!outcome.ok) {
        // B12 §3: the envelope renders via message_key + params — the server is
        // authoritative; its field errors land under their fields like zod's.
        const mapped = envelopeErrors(outcome.error, (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
        setRefusedValues(fieldValueSnapshot(values, Object.keys(mapped.fields)));
        // ⚠ **ONE SENTENCE, ONCE (`DEF-LED-6140`, 2026-09-22).** A refusal that
        // names a field is carried TWICE in the envelope — once as the
        // top-level `message_key` and once inside `field_errors` — and that is
        // deliberate, so a screen with no form around it still has something to
        // print. The house pattern is `metering.premises.external_ref_taken`:
        // the same key in both halves. Rendering both puts the identical
        // sentence under the input AND above the buttons, which spends B14 rule
        // 32's description budget saying one thing twice and reads like two
        // different problems.
        //
        // So the form-level line is dropped ONLY when a field is already
        // showing that exact sentence. A refusal whose message differs from
        // every field's — the ordinary case, and every caller that existed
        // before this — renders exactly as it did. A whole-payload refusal that
        // names no field still renders here, which is what this slot is for.
        const alreadyUnderAField = Object.values(mapped.fields).includes(mapped.message);
        setFormMessage(alreadyUnderAField ? null : mapped.message);
      }
    } finally {
      setWorking(false);
    }
  }

  return { fieldErrors, formMessage, working, handleSubmit };
}

/**
 * **THE PAGE EQUIVALENT OF `FormModal` — `DEF-PAY-6317`, 2026-09-23.**
 *
 * Same schema validation, same envelope rendering, same field-error context,
 * same footer grammar. **What it does NOT have is a title, a kicker or a close
 * control**, and that is B14 rule 2 rather than an omission: a page already has
 * exactly one page header, and a frame that drew a second one would put two
 * titles on the screen.
 *
 * ⚠ **ADDED UNDER B14 RULE 36** — *where the kit lacks a piece a screen needs,
 * ADD IT TO THE KIT as an opt-in, so nothing existing moves.* This file's own
 * header has said since US-SHL-009 that *"full-page forms (S12/S13/S16, guided
 * per IS-1) compose these fields directly, outside any modal"*, and until now
 * each such page hand-rolled the validate/post/render-the-refusal loop and
 * passed `error` to every field by hand. The blueprint's move of *Record a
 * payment* to a page (p037) is the first caller.
 *
 * ⚠ **THE FOOTER'S ORDER AND TIERS ARE OURS, NOT THE DRAWING'S** — B14 rule
 * 38: *"if youa re doing a form - go as per our UI rules"*. What the form
 * CONTAINS is the drawing's to decide.
 */
export function FormPage(props: {
  schema: ZodTypeAny; // the consumer's zod schema, mirroring server VAL codes (B8)
  values: unknown; // the consumer's raw form values — money/quantities stay strings
  onSubmit: () => Promise<FormSubmitOutcome>;
  /** What `Cancel` does. A page has somewhere to go BACK to, where a modal
   *  merely closed — the consumer owns that navigation. */
  onCancel: () => void;
  submitLabel: ReactNode; // consumer catalog copy
  /** B14 rule 6's danger tier — see `FormModal.submitVariant`. */
  submitVariant?: CommitTier;
  /** BR-SHL-025 — see `FormModal.commitBlocked`. Same contract, same slot. */
  commitBlocked?: string;
  cancelLabel?: ReactNode;
  children: ReactNode; // fields from the kit above — errors arrive via context
}) {
  const { t } = useTranslation();
  const { fieldErrors, formMessage, working, handleSubmit } = useFormCommit(
    props.schema,
    props.values,
    props.onSubmit,
  );

  return (
    <form noValidate onSubmit={(event) => void handleSubmit(event)} data-form-page="">
      <FieldErrorsContext.Provider value={fieldErrors}>
        {props.children}
      </FieldErrorsContext.Provider>
      {formMessage !== null && (
        <p className="form-message" role="alert">
          {formMessage}
        </p>
      )}
      {/* A18 §5: ">3 errors" summary line renders above the actions. */}
      <FormErrorSummary count={Object.keys(fieldErrors).length} />
      {/* BR-SHL-025 — rendered as text and announced, never as a `title`
          nobody on a phone call can read. */}
      {props.commitBlocked !== undefined && (
        <RefusalStrip role="alert" data-commit-blocked="">
          {props.commitBlocked}
        </RefusalStrip>
      )}
      {/* B14 rule 39's `--sp-6` between sections, and the same Cancel-then-
          commit order `FormModal` has. */}
      <div className="mt-6 flex gap-2 border-t-2 border-divider pt-4">
        <Button variant="ghost" onClick={props.onCancel}>
          {props.cancelLabel ?? t("forms.cancel")}
        </Button>
        {props.commitBlocked === undefined ? (
          <WorkingButton working={working} type="submit" variant={props.submitVariant}>
            {props.submitLabel}
          </WorkingButton>
        ) : (
          <Button variant={props.submitVariant ?? "primary"} disabled>
            {props.submitLabel}
          </Button>
        )}
      </div>
    </form>
  );
}

export function FormModal(props: {
  title: string;
  kicker?: string;
  schema: ZodTypeAny; // the consumer's zod schema, mirroring server VAL codes (B8)
  values: unknown; // the consumer's raw form values — money/quantities stay strings
  onSubmit: () => Promise<FormSubmitOutcome>; // consumer posts; on ok it fires its A13 toast + closes
  onClose: () => void;
  submitLabel: ReactNode; // consumer catalog copy
  /**
   * B14 rule 6's danger tier, for a DESTRUCTIVE commit — the same OPTIONAL
   * pass-through `ConfirmDialog.confirmVariant` is (DEF-718), for the same
   * reason: `WorkingButton` has taken a `CommitTier` since DEF-712 and this
   * frame hard-coded the default, so a form that commits something
   * irreversible could not obey rule 6 at all.
   *
   * ⚠ ABSENT MEANS `primary`, so every existing FormModal renders byte-for-byte
   * as before; only a form that DECLARES its commit destructive changes tier.
   *
   * First caller: `MoveUnitModal` (CR-089 wave J) — a move re-attributes where
   * the unit's next bill lands and cannot be undone by moving it back, because
   * the second move carries its own date and reason and both then read wrong.
   */
  submitVariant?: CommitTier;
  /**
   * **THE REASON THIS FORM CANNOT BE COMMITTED ON THIS DEPLOYMENT** — absent
   * means it can, which is every existing caller, so nothing already built
   * moves by a pixel.
   *
   * `BR-SHL-025` says a control this deployment cannot honour renders DISABLED
   * WITH ITS REASON rather than hidden. Until now this frame had no way to say
   * that, so a form with no write behind it had two options and both were
   * wrong: leave the commit live and fail at the server, or refuse to open the
   * form at all — which is what `Adjust` did, as a header button whose
   * `onClick` was `() => undefined`. **A control that opens nothing is dead UI**
   * (CLAUDE.md hard-won law 2), and its mirror — a live screen behind a dead
   * control — is the more expensive half.
   *
   * `ACC-S14`'s acceptance sentence is what this prop serves, verbatim: *"…and
   * commits — or reads why it cannot be committed, on the button itself."*
   *
   * ⚠ **THE REASON RENDERS AS TEXT, NEVER AS A `title` TOOLTIP.** `GuardedButton`
   * puts its reason in `title`, which is unreachable by keyboard, invisible on
   * touch and unread by a clerk who is on the phone — the exact reader B14
   * rule 33 writes its caps for. It goes in the form-message slot this frame
   * already owns, beside the error summary, where a `role="alert"` announces it.
   *
   * ⚠ **AND IT DOES NOT DISABLE THE FORM'S FIELDS.** R4 draws every blocked
   * action with its whole form live and only the commit refused — *"A control
   * the deployment cannot honour keeps its FORM and disables its COMMIT with
   * the reason on it"* — because the form is the specification of the endpoint
   * that does not exist yet, and a clerk reading it learns what will be asked.
   */
  commitBlocked?: string;
  /**
   * **WHAT NOT COMMITTING MEANS, WHERE *Cancel* WOULD NOT SAY IT.**
   *
   * ⚠ **ADDED 2026-09-23 (`CR-136-BRC07` `P2.6`) UNDER B14 RULE 36** — *where
   * the kit lacks a piece a screen needs, ADD IT TO THE KIT as an opt-in, so
   * nothing existing moves.* Absent means `forms.cancel`, which is every
   * caller that existed before this line.
   *
   * It exists because the payments blueprint draws two dialogs where the
   * dismiss is a STATEMENT ABOUT THE TILL rather than a way out of a form:
   * 3·3b's *Keep it open* and 3·3c's *Leave it open* (p056, p057). On a close
   * dialog *Cancel* is ambiguous in the one direction that costs money — a
   * clerk reads it as *cancel the close* or as *cancel the shift* — and the
   * drawing answers it in three words. What the form CONTAINS is the
   * drawing's (B14 rule 38); the footer's ORDER and tiers stay ours.
   *
   * ⚠ **IT IS STILL CAPPED BY B14 RULE 33** — a LABEL is ≤ 3 words and carries
   * no sentence. Nothing here enforces that and nothing in this repository
   * can: no gate reads rendered output.
   */
  cancelLabel?: ReactNode;
  children: ReactNode; // fields from the kit above — errors arrive via context
}) {
  const { t } = useTranslation();
  // ⚠ **ONE COPY OF THE WIRING, SHARED WITH `FormPage` (`DEF-PAY-6317`).**
  // This was `FormModal`'s own state and its own `handleSubmit`; that body
  // moved into `useFormCommit` above, UNCHANGED, when the payments blueprint
  // needed the same loop inside a PAGE. Two copies of B12 §3's envelope
  // rendering, A18 §5's first-error focus and `DEF-LED-6140`'s say-it-once
  // rule is one copy too many — the second is the one that stops being fixed.
  // Every existing caller renders byte-for-byte as it did before.
  const { fieldErrors, formMessage, working, handleSubmit } = useFormCommit(
    props.schema,
    props.values,
    props.onSubmit,
  );

  return (
    <ModalShell title={props.title} kicker={props.kicker} onClose={props.onClose} busy={working}>
      <form noValidate onSubmit={(event) => void handleSubmit(event)}>
        <div className="modal-body">
          <FieldErrorsContext.Provider value={fieldErrors}>
            {props.children}
          </FieldErrorsContext.Provider>
          {formMessage !== null && (
            <p className="form-message" role="alert">
              {formMessage}
            </p>
          )}
          {/* A18 §5: ">3 errors" summary line renders above the actions. */}
          <FormErrorSummary count={Object.keys(fieldErrors).length} />
          {/* BR-SHL-025 — see `commitBlocked` above. Rendered as text and
              announced, never as a `title` nobody on a phone call can read. */}
          {props.commitBlocked !== undefined && (
            <RefusalStrip role="alert" data-commit-blocked="">
              {props.commitBlocked}
            </RefusalStrip>
          )}
        </div>
        <div className="modal-foot">
          <Button variant="ghost"  onClick={props.onClose}>
            {props.cancelLabel ?? t("forms.cancel")}
          </Button>
          {props.commitBlocked === undefined ? (
            <WorkingButton working={working} type="submit" variant={props.submitVariant}>
              {props.submitLabel}
            </WorkingButton>
          ) : (
            <Button variant={props.submitVariant ?? "primary"} disabled>
              {props.submitLabel}
            </Button>
          )}
        </div>
      </form>
    </ModalShell>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-009@b9eb83e (story+rules snapshot hash — EP-SHL-03; regenerated for PasswordField, the BR-SHL-017 E1 rider; amended for the disabled-option rider by US-RAT-008@7d1a8ef)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-09 by story-coder (W1 Plans & Rates lane: FieldOption.disabled)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope)
// exceptions: E1 CLOSED — the kit had no password control, so S3 and S114 each carried their own input; PasswordField now owns it and both compose it. Its `autoComplete` prop has no counterpart on the other kit fields (it is the browser credential-manager hint a password input cannot do without) — reported with this packet · E1 rider (2026-08-09) SelectField had no way to render an option that must be SHOWN but not offered, so BR-RAT-041's "Formula" charge rule would have rendered as a live choice the server refuses; `FieldOption.disabled` closes that in the ONE kit rather than growing a second select in the rating feature — reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
