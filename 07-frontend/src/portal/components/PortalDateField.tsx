// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-10250 — PO 2026-10-18, verbatim: *"any date field in
//           artifact should be date picker"*; decision log the same day:
//           *"every date on these screens … is the product's date picker in
//           the tenant's date format (MM/DD/YYYY), never a typed text box —
//           including the portal (today a native browser date box)"*.
// Rules:    B14 rule 43 (ONE date box for every portal form) · rule 36 (the
//           kit's own picker, `RegionalDateInput`, not a second one) · the
//           portal accessibility questions (a label, the error tied to the
//           box, keyboard: the text box takes typing, the button the calendar)
// Tests:    src/portal/guest/AboutYouMoveInFields.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { RegionalDateFormat } from "@/components/DateCell";
import { RegionalDateInput } from "@/components/FormModal";
import { useTenantRegional } from "@/components/TenantRegional";

import { useFieldWiring } from "./a11y";
import { FormField, fieldErrorId } from "./primitives";

/**
 * The format the drawing names (`MM/DD/YYYY`) when the utility has set none.
 *
 * ⚠ **A PICKER HAS TO SHOW SOME FORMAT, AND THIS IS THE RULING'S OWN.** The
 * date *display* helpers decline to invent a format (`usePortalDate`), which
 * is right for a read; a box a person types into cannot decline. The ruling of
 * 2026-10-18 names `MM/DD/YYYY` in as many words, so that is the fallback.
 */
const RULED_FORMAT: RegionalDateFormat = "MM/DD/YYYY";

/** The format a portal date box shows: the utility's own, else the ruling's. */
export function usePortalDateFormat(): RegionalDateFormat {
  return useTenantRegional()?.dateFormat ?? RULED_FORMAT;
}

/**
 * The portal's one date BOX — the kit's `RegionalDateInput`: typed in the
 * utility's format, or picked from the calendar button. For a box that sits in
 * a `FormField` its caller already draws; `PortalDateField` below is the whole
 * field. `value` is the calendar date `YYYY-MM-DD`, raw end to end.
 */
export function PortalDateBox(props: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onTypedBadly?: (bad: boolean) => void;
  invalid?: boolean;
  max?: string;
  min?: string;
  required?: boolean;
}) {
  // F-03 (`DEF-CWP-10548`): the field it sits in marks it, like every kit box.
  const wired = useFieldWiring(props.id, props);
  return (
    <RegionalDateInput
      id={props.id}
      value={props.value}
      onChange={props.onChange}
      onTypedBadly={props.onTypedBadly ?? (() => undefined)}
      dateFormat={usePortalDateFormat()}
      min={props.min}
      max={props.max}
      disabled={false}
      required={wired["aria-required"] === true}
      invalid={wired["aria-invalid"] === true}
      describedBy={wired["aria-describedby"] ?? fieldErrorId(props.id)}
    />
  );
}

/**
 * The portal's one date FIELD — label, box, helper, and the error tied to the
 * box. Half-typed text hands `""` and, on leaving, names the format under it.
 */
export function PortalDateField(props: {
  id: string;
  value: string;
  label: string;
  onChange: (value: string) => void;
  helper?: string;
  /** A refusal from elsewhere (the server) — wins over the format line. */
  error?: string | null;
  max?: string;
  min?: string;
  required?: boolean;
}) {
  const { t } = useTranslation();
  const format = usePortalDateFormat();
  const [typedBadly, setTypedBadly] = useState(false);
  const error =
    props.error ??
    (typedBadly ? t("forms.date.useFormat", { format, defaultValue: "Use {{format}}." }) : null);
  return (
    <FormField id={props.id} label={props.label} required={props.required} helper={props.helper} error={error}>
      <PortalDateBox
        id={props.id}
        value={props.value}
        onChange={props.onChange}
        onTypedBadly={setTypedBadly}
        invalid={error !== null}
        min={props.min}
        max={props.max}
        required={props.required}
      />
    </FormField>
  );
}
