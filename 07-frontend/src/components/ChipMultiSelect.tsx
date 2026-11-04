// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 36 (PO 2026-09-04) — ⚠ breach **(e)**, named in the rule:
//           *"the portal's Branding screen drew* Services shown on the front
//           page *as a **WALL OF CHECKBOXES**, which r10 rule 9 forbids by
//           name"*. The remedy is the rule's own: add the missing piece to the
//           KIT so one component holds one visual decision.
// Rules:    r10 rule 9 / B14 rule 9 (**a multiple-choice field renders as
//           removable chips + an add control — never a wall of checkboxes**) ·
//           rule 8 (a list of 5+ options is searchable — the add control is a
//           `select`, which every browser type-filters) · rule 36 ·
//           BR-SHL-025 (disabled WITH its reason)
// Tests:    src/components/ChipMultiSelect.test.tsx ·
//           src/components/ChipMultiSelectField.dom.test.tsx (the visible
//           label and its required marker, `DEF-SHL-6250`, 2026-09-28)
// Impacts:  features/tenancy/SettingsCustomerPortalTab.tsx (the services) ·
//           SettingsServiceCentres.tsx (what a centre can do, and what it takes)
// ───────────────────────────────────────────────────────
//
// A MULTIPLE-CHOICE FIELD, ONCE: the chosen values as removable chips, and one
// control that adds the next one.
//
// ⚠ **THE CHIP CARRIES ITS OWN REMOVE, AND THAT IS THE RULE'S POINT.** A
// checkbox says *"this is a list of everything, some of it ticked"*; a chip row
// says *"this is what you chose"* and is read in one glance at a width a table
// cell can hold. The options that are NOT chosen belong in the add control,
// where they cost no vertical space at all.

import { useId } from "react";

import { Button } from "./Button";
import { FieldLabel, SearchSelectField } from "./FormModal";
import { FieldError } from "./StateFrame";

export interface ChipOption {
  value: string;
  label: string;
  /**
   * ⚠ **AN OPTION THAT IS PRESENT AND NOT CHOOSABLE — ADDED 2026-09-10 FOR THE
   * PLAN WIZARD'S STEP 2, AND IT IS AN OPT-IN THAT MOVES NOTHING EXISTING.**
   *
   * B14 rule 9 forbids a wall of checkboxes and this component is the remedy,
   * but the plan's service list carries a fact no chip row could hold: the
   * services this utility has switched OFF are **named inside the list**,
   * greyed, with where to switch them on — `BR-RAT-024`'s restored clause and
   * the PO's ruling of 2026-09-08, verbatim: *"the switched-off services are
   * named INSIDE the list, greyed, with where to switch them on"*. A component
   * that could only list choosable options would have forced that screen to
   * keep its checkbox grid or to drop a ratified behaviour.
   *
   * So this is rule 36's own instruction followed rather than worked around —
   * *"compose the kit; where the kit lacks a piece, ADD IT TO THE KIT"* — and
   * rule 38's caveat honoured: it is OPTIONAL, absent on every existing call
   * site, and a `ChipOption` without it renders byte-for-byte what it rendered
   * before.
   *
   * ⚠ **COLOUR IS NEVER THE ONLY SIGNAL (B14).** A disabled option carries its
   * `reason` as a WORD in the list, so the state survives a monochrome screen
   * and a screen reader — which is why `reason` is not optional-in-practice
   * here even though the type allows it, and why the option is not simply
   * hidden.
   */
  disabled?: boolean;
  /** Why this option cannot be chosen — five or six words (B14 rule 33), shown
   *  beside the label rather than on a tooltip nobody reaches by keyboard. */
  reason?: string;
}

export function ChipMultiSelect(props: {
  /** The accessible name of the whole field. */
  label: string;
  options: readonly ChipOption[];
  selected: readonly string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  reason?: string | null;
  /** The add control's own prompt, e.g. *"Add a service…"*. */
  addLabel: string;
  /** What the field says when nothing is chosen yet — never an empty box. */
  emptyLabel: string;
  /** Per-chip remove label, e.g. *"Remove"* — the chip's accessible name is
   *  built as `${removeLabel} ${chip label}` so a screen reader says which. */
  removeLabel: string;
  testKey?: string;
  /**
   * ⚠ **THE ADD CONTROL BECOMES A TYPE-TO-FILTER BOX — OPT-IN, ADDED
   * 2026-09-19 FOR CHG-02's CUSTOMER CLASS, AND IT MOVES NOTHING EXISTING.**
   *
   * The PO walked the charge code wizard in the beta and asked for it in their
   * own words: *"make customer class drop down multi select"*. It was already
   * multi-select — chips, this component — so what they were actually looking
   * at is the ADD control, a bare `<select>` whose only search is the
   * browser's first-letter jump.
   *
   * ⚠ **AND THE LIST STOPPED BEING A FIXED EIGHT ON 2026-09-17.**
   * `account_types` became a TENANT table that day, so the options are now
   * however many classes a utility has written — the PO's own already has
   * NINE. `BR-SHL-033` puts the threshold for a searchable control at
   * `LONG_LIST_THRESHOLD` (10), which a tenant-extensible list crosses by
   * growing rather than by anyone deciding to, so this is the rule arriving
   * rather than a preference.
   *
   * **WHY A PROP AND NOT A NEW CONTROL DRAWN ON THE SCREEN.** B14 rule 36:
   * *"compose the kit; where the kit lacks a piece, ADD IT TO THE KIT"* — a
   * second chip-and-search drawn inside one wizard is the rule's own named
   * breach (four screens, four chips). And rule 38's caveat is honoured the
   * way `disabled` above honours it: **absent on all ten existing call sites,
   * which keep the `<select>` byte-for-byte.** `ChipMultiSelect.test.tsx`
   * asserts that default so a later lane cannot flip every screen at once.
   */
  searchable?: boolean;
  /**
   * ⚠ **A VISIBLE LABEL AND ITS REQUIRED MARKER — `DEF-SHL-6250`, FIXED
   * 2026-09-28. OPT-IN, AND IT MOVES NOTHING EXISTING.**
   *
   * The register row states the defect and its remedy: *"ChipMultiSelect
   * renders its label only as an aria-label, so a chips field inside a modal
   * has no visible name and no required marker … Give ChipMultiSelect an
   * optional visible label and required marker of its own, composing the kit's
   * FieldLabel, so the name and the asterisk are one visual decision rather
   * than nine surrounding containers. P3.11 worked around it by exporting
   * FieldLabel and placing it above the chips, which is correct for one screen
   * and is not the fix."* This is the fix.
   *
   * It is wanted here because `step2-premise.png` draws **Utility services \***
   * — a label AND an asterisk — over the multi-select, and a New Connect step
   * hand-rolling that `<label>` would be the tenth surrounding container.
   *
   * ⚠ **THE LABEL NAMES THE GROUP, NOT THE ADD CONTROL**, through
   * `aria-labelledby`. The chips and the adder together are the field; the
   * adder keeps its own `sr-only` name (*Add a service…*), which is a
   * different sentence about a different control.
   *
   * Absent on all ten existing call sites, which render byte-for-byte what
   * they rendered before — the same contract `disabled` and `searchable` were
   * added under.
   */
  showLabel?: boolean;
  /** B14 rule 10 — the asterisk rides on the label. Only drawn with
   *  `showLabel`; `aria-required` is not set on a group, which has no
   *  required state to announce. */
  required?: boolean;
  /** The HELPER, under the control (B14 rule 39). Needs `showLabel`, because a
   *  helper with no label is a sentence about nothing. */
  help?: string;
  /** A refusal about this field. Needs `showLabel`, for the same reason. */
  error?: string;
}) {
  const blocked = props.disabled === true || (props.reason ?? null) !== null;
  const byValue = new Map(props.options.map((one) => [one.value, one.label]));
  const remaining = props.options.filter((one) => !props.selected.includes(one.value));
  // ⚠ `useId` and not `testKey`: `testKey` is OPTIONAL, so two unlabelled
  // fields on one screen would both point `aria-labelledby` at `chips-label`
  // and the second name would win for both. React's id is unique per instance.
  const uid = useId();
  const labelled = props.showLabel === true;
  const labelId = `${uid}-label`;
  const helpId = `${uid}-help`;
  const errorId = `${uid}-error`;
  const described = [
    labelled && props.help !== undefined ? helpId : null,
    labelled && props.error !== undefined ? errorId : null,
  ].filter((one): one is string => one !== null);

  const group = (
    <div
      data-chip-select={props.testKey}
      role="group"
      // The visible label wins when there is one: two names on one group is a
      // name that depends on which the reader's software prefers.
      aria-label={labelled ? undefined : props.label}
      aria-labelledby={labelled ? labelId : undefined}
      aria-describedby={described.length > 0 ? described.join(" ") : undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        {props.selected.length === 0 ? (
          <p className="text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]" data-chip-empty="">
            {props.emptyLabel}
          </p>
        ) : (
          props.selected.map((value) => (
            <span
              key={value}
              data-chip={value}
              className="inline-flex items-center gap-1 border border-divider px-2 py-1 text-md"
            >
              {byValue.get(value) ?? value}
              <Button
                variant="ghost"
                size="row"
                aria-label={`${props.removeLabel} ${byValue.get(value) ?? value}`}
                title={props.reason ?? props.removeLabel}
                disabled={blocked}
                onClick={() => props.onChange(props.selected.filter((one) => one !== value))}
                data-chip-remove={value}
              >
                ×
              </Button>
            </span>
          ))
        )}
      </div>
      {remaining.length > 0 && props.searchable === true ? (
        <div className="mt-2" data-chip-add-search={props.testKey}>
          <SearchSelectField
            /* REMOUNTED ON EVERY ADD. `SearchSelectField` is a picker: it keeps
               the chosen label in the box. An ADD control must go back to empty
               instead, and the selection count changing is exactly the moment
               it should. */
            key={`${props.testKey ?? "chips"}-${props.selected.length}`}
            id={`${props.testKey ?? "chips"}-add`}
            label={props.addLabel}
            value=""
            options={remaining.map((one) => ({
              value: one.value,
              // Same rule as the `<option>` below: the reason is a WORD in the
              // list, never `title` alone.
              label:
                one.disabled === true && one.reason !== undefined
                  ? `${one.label} — ${one.reason}`
                  : one.label,
              disabled: one.disabled,
            }))}
            onChange={(value) => {
              if (value !== "") props.onChange([...props.selected, value]);
            }}
            disabled={blocked}
            help={props.reason ?? undefined}
            placeholder={props.addLabel}
          />
        </div>
      ) : remaining.length > 0 ? (
        <label className="mt-2 block">
          <span className="sr-only">{props.addLabel}</span>
          <select
            className="h-9 border border-field-border bg-bg px-2 text-md"
            value=""
            disabled={blocked}
            title={props.reason ?? props.addLabel}
            onChange={(e) => {
              if (e.target.value !== "") props.onChange([...props.selected, e.target.value]);
            }}
            data-chip-add={props.testKey}
          >
            <option value="">{props.addLabel}</option>
            {remaining.map((one) => (
              <option
                key={one.value}
                value={one.value}
                disabled={one.disabled === true}
                // The reason rides in the visible text, never on `title` alone:
                // a `<option title>` is a mouse-only affordance and B14 says
                // colour — or its absence — is never the only signal.
                label={undefined}
              >
                {one.disabled === true && one.reason !== undefined
                  ? `${one.label} — ${one.reason}`
                  : one.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );

  // ⚠ NOT `labelled ? <div className="field">…` INLINE: `.field > label` is a
  // CHILD selector, so the label has to be a direct child of `.field` or it
  // renders inline and unstyled — the same descendant-selector trap
  // `DEF-MET-4959` records one control over.
  if (!labelled) return group;
  return (
    <div className="field">
      <FieldLabel id={labelId} label={props.label} required={props.required === true} />
      {group}
      {props.help !== undefined && (
        <p className="field-help mt-1.5 mb-0" id={helpId}>
          {props.help}
        </p>
      )}
      {props.error !== undefined && <FieldError id={errorId} message={props.error} />}
    </div>
  );
}
