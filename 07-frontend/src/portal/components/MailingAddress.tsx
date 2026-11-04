// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-9163 — PO 2026-10-02, verbatim: *"Mailing Address is not
//          captured as part of the applicant/customer information."* Drawn on
//          wireframe s17 (*"Mailing address, if different"* · *"Same as the
//          service address"*) and recorded absent by CR-085 lane-3 finding 17.3.
// Rules:   CLAUDE.md hard rule 8 (a MAILING address is the named exception —
//          where the bill goes — and never a premises address) · B14 rule 43
//          (a component) · rule 36 (built from the portal kit: `FormField`,
//          `TextInput`, `SelectInput`) · rule 21 (utilities; `portal/` is on
//          the ledger) · rule 33
// Tests:   src/portal/guest/CheckAndSend.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * *Mailing address, if different* — a tick box and, under it when unticked,
 * the five parts of a US address in the order an envelope reads them.
 *
 * ⚠ **ONE RULE, NOT TWO, FOR EVERY PART OF THIS THAT ALREADY HAS ONE.** The
 * states are the kit's one list (`usStates.ts`, the codes the server accepts),
 * the ZIP check is the kit's `usZipIsValid`, and the five labels are the
 * catalogue's `common.usAddress.*` — the same words the staff side's
 * `UsAddressFields` prints. Only the CONTROLS are the portal's own, because the
 * portal kit draws its inputs at the customer's reading size (B14 rule 39's
 * note on `TextInput`).
 *
 * ⚠ **TICKED BY DEFAULT, BECAUSE THAT IS WHAT EVERY APPLICATION MEANT BEFORE
 * THE QUESTION WAS ASKED** — the bill goes to the service address. Unticking
 * opens the five boxes; ticking again hides them and the server stops reading
 * them (`mailing_same_as_service`).
 */
import type { FocusEvent } from "react";
import { useTranslation } from "react-i18next";

import { usZipIsValid } from "@/components/UsAddressFields";
import { US_STATE_OPTIONS } from "@/components/usStates";

import { FormSection } from "./FormSection";
import { FormField, SelectInput, TextInput } from "./primitives";

/** The block's value — `same` and the five parts (`""` is *not given*). */
export interface MailingValue {
  same: boolean;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
}

/** What a saved draft says, as the block's value. */
export function mailingFromDraft(draft: {
  mailing_same_as_service?: boolean;
  mailing_line1?: string | null;
  mailing_line2?: string | null;
  mailing_city?: string | null;
  mailing_state?: string | null;
  mailing_postal_code?: string | null;
} | null): MailingValue {
  return {
    same: draft?.mailing_same_as_service ?? true,
    line1: draft?.mailing_line1 ?? "",
    line2: draft?.mailing_line2 ?? "",
    city: draft?.mailing_city ?? "",
    state: draft?.mailing_state ?? "",
    postal_code: draft?.mailing_postal_code ?? "",
  };
}

/** The draft's own field names, ready to save. */
export function mailingPayload(value: MailingValue): Record<string, unknown> {
  return {
    mailing_same_as_service: value.same,
    mailing_line1: value.line1.trim() || null,
    mailing_line2: value.line2.trim() || null,
    mailing_city: value.city.trim() || null,
    mailing_state: value.state.trim() || null,
    mailing_postal_code: value.postal_code.trim() || null,
  };
}

/**
 * Is an unticked block complete enough to send? Everything but the unit line,
 * and a ZIP in the right shape — the browser's copy of the server's
 * `MAILING_REQUIRED` and `US_ZIP_RE`.
 */
export function mailingIsComplete(value: MailingValue): boolean {
  if (value.same) return true;
  const filled = [value.line1, value.city, value.state, value.postal_code].every(
    (part) => part.trim() !== "",
  );
  return filled && usZipIsValid(value.postal_code);
}

/** One line for a read-back — `PO Box 4417, Apt 2, Ottumwa, IA 52501`. */
export function mailingLine(value: MailingValue): string {
  const cityLine = [value.city.trim(), [value.state.trim(), value.postal_code.trim()].filter(Boolean).join(" ")]
    .filter(Boolean)
    .join(", ");
  return [value.line1.trim(), value.line2.trim(), cityLine].filter(Boolean).join(", ");
}

export function MailingAddressFields(props: {
  value: MailingValue;
  onChange: (next: MailingValue) => void;
  /** Called when a part is LEFT, or the box or the state changes — the
   *  moment to save, the same rhythm as every other box on the form. */
  onCommit: (next: MailingValue) => void;
  /** ⊕ `DEF-CUS-10250` — the service address, shown on one line while *Same
   *  as service address* is ticked (image `04-portal.png`). */
  serviceAddress?: string;
}) {
  const { t } = useTranslation();
  const value = props.value;
  const set = (part: Partial<MailingValue>): MailingValue => {
    const next = { ...value, ...part };
    props.onChange(next);
    return next;
  };
  // A part is saved when it is LEFT. The DOM's value is read, not React's —
  // `DEF-CWP-3705`'s reason, recorded on `useApplicationForm`.
  const leave = (part: keyof MailingValue) => (event: FocusEvent<HTMLElement>) => {
    const typed = (event.target as HTMLInputElement | null)?.value;
    props.onCommit(typed === undefined ? value : { ...value, [part]: typed });
  };
  const zipWrong = !value.same && !usZipIsValid(value.postal_code);
  return (
    // ⊕ **`DEF-CUS-10250` — MOVE-IN'S MAILING BLOCK, IN THE PORTAL LOOK**
    // (image `04-portal.png`): a boxed section titled *Mailing address* with
    // the *Same as service address* tick in its header; ticked, the service
    // address on one line; unticked, the address card with Apt / Unit and the
    // state from a list. The tick keeps its `id` (`mailing_same`).
    <div data-mailing-address="">
      <FormSection
        title={t("portal.apply.mailingAddress")}
        testId="mailing"
        tick={{
          id: "mailing_same",
          label: t("portal.apply.mailingSameShort"),
          checked: value.same,
          onChange: (checked) => props.onCommit(set({ same: checked })),
        }}
      >
      {value.same ? (
        props.serviceAddress !== undefined ? (
          <p
            className="m-0 flex flex-wrap gap-2 border border-neutral-200 px-3 py-2 text-body text-neutral-900"
            data-mailing-service-line=""
          >
            <span className="font-semibold">{t("portal.apply.serviceAddress")}</span>
            <span>{props.serviceAddress}</span>
          </p>
        ) : null
      ) : (
        <div className="flex flex-col gap-3" data-mailing-fields="">
          <FormField id="mailing_line1" label={t("common.usAddress.line1")} required>
            <span onBlur={leave("line1")}>
              <TextInput id="mailing_line1" value={value.line1} onChange={(line1) => set({ line1 })} />
            </span>
          </FormField>
          <FormField id="mailing_line2" label={t("common.usAddress.line2")}>
            <span onBlur={leave("line2")}>
              <TextInput id="mailing_line2" value={value.line2} onChange={(line2) => set({ line2 })} />
            </span>
          </FormField>
          <div className="grid grid-cols-3 gap-x-6 gap-y-3 max-md:grid-cols-1">
            <FormField id="mailing_city" label={t("common.usAddress.city")} required>
              <span onBlur={leave("city")}>
                <TextInput id="mailing_city" value={value.city} onChange={(city) => set({ city })} />
              </span>
            </FormField>
            <FormField id="mailing_state" label={t("common.usAddress.state")} required>
              <SelectInput
                id="mailing_state"
                value={value.state}
                options={US_STATE_OPTIONS}
                placeholder={t("common.usAddress.statePick")}
                onChange={(state) => props.onCommit(set({ state }))}
              />
            </FormField>
            <FormField
              id="mailing_postal_code"
              label={t("common.usAddress.zip")}
              required
              error={zipWrong ? t("common.usAddress.zipFormat") : null}
            >
              <span onBlur={leave("postal_code")}>
                <TextInput
                  id="mailing_postal_code"
                  value={value.postal_code}
                  onChange={(postal_code) => set({ postal_code })}
                />
              </span>
            </FormField>
          </div>
        </div>
      )}
      </FormSection>
    </div>
  );
}
