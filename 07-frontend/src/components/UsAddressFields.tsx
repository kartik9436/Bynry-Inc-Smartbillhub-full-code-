// ── Trace ──────────────────────────────────────────────
// Change:   PO report 2026-09-23 on `New request` step 3, verbatim: *"if
//           customer want put billing address then it should full address
//           line, unit, city, zip it shoould be match how address taken in USA
//           ;do'nt make it mandatory"* — `DEF-CUS-6408`. The same fields were
//           then asked for on the move-in and New account mailing address, so
//           this is ONE kit component and not a block inside a page.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT) · rule 38 (how a form is
//           built is the UI rules') · rule 8 / BR-SHL-033 (a long list is a
//           searchable type-ahead) · rule 21 (Tailwind utilities; this file is
//           on `src/styles/route-b-migrated.txt`) · rule 33 (a label ≤ 3 words,
//           an instruction ≤ 6) · CLAUDE.md hard rule 8 (this is a MAILING
//           address — the one place besides `premises` an address may live)
// Tests:    src/components/UsAddressFields.dom.test.tsx
// Impacts:  src/features/customers/ServiceRequestCapturePage.tsx (step 3's
//           billing address); offered to the move-in / New account mailing
//           block (lane MOVEIN-WIZ)
// ───────────────────────────────────────────────────────
//
// A US ADDRESS, IN THE ORDER AN AMERICAN ENVELOPE READS
// ─────────────────────────────────────────────────────
//
//     Street address
//     Apt, suite or unit
//     City · State · ZIP code
//
// ⚠ **NOTHING HERE IS REQUIRED, AND NOTHING CARRIES A REQUIRED MARK.** The PO
// said so for the billing address (*"do'nt make it mandatory"*) and a mailing
// block is optional on every door that has one (no mailing row means *the bill
// goes to the service address*, B2 §2). A caller that needs a part to be
// present says so at ITS OWN gate; this component never does.
//
// ⚠ **THE ZIP'S FORMAT IS CHECKED, ITS PRESENCE IS NOT.** Five digits or ZIP+4
// (`12345`, `12345-6789`). An empty box is always fine; `7866` is a slip, caught
// on the field before it is printed on an envelope. `usZipIsValid` is exported
// so a caller's `Continue` can hold on the same rule the field shows.
//
// ⚠ **`State` IS A SEARCHABLE PICKER OVER THE KIT'S ONE LIST** (`usStates.ts`,
// the codes `apps/tenancy/selectors.US_STATES` accepts). The stored value is the
// two-letter CODE; the label is the state's name.
//
// ⚠ **THE WORDS ARE THE CATALOGUE'S (`common.usAddress.*`), IN US ENGLISH** —
// `ZIP code`, `Apt, suite or unit`, `State` — and this file spells none of them
// (`G15`).
import { useTranslation } from "react-i18next";

import { SearchSelectField, TextField } from "./FormModal";
import { US_STATE_OPTIONS } from "./usStates";

/** The five parts, each a string (`""` is *not given*). `state` is a code. */
export interface UsAddressValue {
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
}

export function emptyUsAddress(): UsAddressValue {
  return { line1: "", line2: "", city: "", state: "", postal_code: "" };
}

/** Five digits, or ZIP+4. */
export const US_ZIP = /^\d{5}(-\d{4})?$/;

/** `true` for an empty box and for a well-formed ZIP — the FORMAT of what was
 *  typed, never whether anything was. */
export function usZipIsValid(value: string): boolean {
  const typed = value.trim();
  return typed === "" || US_ZIP.test(typed);
}

export function UsAddressFields(props: {
  /** Prefixes every input id — `billing` gives `billing_line1` … */
  idPrefix: string;
  value: UsAddressValue;
  onChange: (next: UsAddressValue) => void;
  /** Shown and not usable — e.g. under a ticked *Same as the service address*.
   *  The caller owes the reader the reason beside it (BR-SHL-025). */
  disabled?: boolean;
  /** ⊕ Optional (lane CF-2, 2026-10-18, image `08-edit.png`): mark Street,
   *  City, State and ZIP required — the asterisk and `aria-required`. The
   *  caller's schema still decides what is refused; this only says so on the
   *  boxes. Apt / Unit is never required. Absent = as before. */
  required?: boolean;
}) {
  const { t } = useTranslation();
  const value = props.value;
  const disabled = props.disabled === true;
  const required = props.required === true;
  const set = (part: Partial<UsAddressValue>): void => props.onChange({ ...value, ...part });
  const id = (part: string): string => `${props.idPrefix}_${part}`;
  return (
    // One column of 20px steps (B14 rule 39, field → field), the last row three
    // across: City · State · ZIP. The same utilities `FieldGrid` uses, written
    // here because the kit may not import a feature's layout helper.
    <div className="flex flex-col gap-5" data-us-address={props.idPrefix}>
      <TextField
        id={id("line1")}
        label={t("common.usAddress.line1")}
        value={value.line1}
        onChange={(line1) => set({ line1 })}
        disabled={disabled}
        required={required}
      />
      <TextField
        id={id("line2")}
        label={t("common.usAddress.line2")}
        value={value.line2}
        onChange={(line2) => set({ line2 })}
        disabled={disabled}
      />
      <div className="grid grid-cols-3 gap-x-6 gap-y-5 max-lg:grid-cols-1">
        <TextField
          id={id("city")}
          label={t("common.usAddress.city")}
          value={value.city}
          onChange={(city) => set({ city })}
          disabled={disabled}
          required={required}
        />
        <SearchSelectField
          id={id("state")}
          label={t("common.usAddress.state")}
          value={value.state}
          onChange={(state) => set({ state })}
          options={US_STATE_OPTIONS}
          placeholder={t("common.usAddress.statePick")}
          disabled={disabled}
          required={required}
        />
        <TextField
          id={id("postal_code")}
          label={t("common.usAddress.zip")}
          value={value.postal_code}
          onChange={(postal_code) => set({ postal_code })}
          disabled={disabled}
          required={required}
          error={
            disabled || usZipIsValid(value.postal_code)
              ? undefined
              : t("common.usAddress.zipFormat")
          }
        />
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6408 · PO report 2026-09-23 · B14 rules 8, 21, 33, 38, 43
// generated: 2026-09-23 by lane REQ-FIX
// checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E✔(ServiceRequestCapturePage step 3) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/UsAddressFields.dom.test.tsx · G31 (on route-b-migrated.txt)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
