// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 9 — the SHARED *Preferences* panel,
//           lifted out of Move-in's Billing step (`moveInWizard/BillingExtras.
//           tsx` `PreferencesSection`) so every create screen draws one
//           (customer-forms drawing set, images 02 and 03 — read as IMAGES).
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"*, *Same day, PO rulings on Move-in's
//           Billing-step sections* — *"we should consider these field also
//           consistently - Autopay, paperless, text reminders, language"*, and
//           the judgment put back to the PO and confirmed with the billing
//           table (*"this is correct"*): Paperless, Text reminders and Language
//           on EVERY screen; **Autopay only where a payment method can be
//           saved** (Move-in, New connect, Transfer) — never on a request.
// Rules:    BR-CUS-028 (the preference set) · BR-CUS-059 (autopay is
//           capture-only) · BR-BIL-036 (print is the floor; paperless and text
//           ADD a channel) · B14 rules 21, 33, 36, 43, 44
// Tests:    customerForm/customerForm.dom.test.tsx · moveInWizard/StepBilling.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import { CheckboxField, SelectField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import type { Translator } from "@/features/tenancy/settingsShared";

import { PortalLanguageField } from "../PortalLanguageField";

/** The four elections — `PreferencesForm`'s subset. */
export interface PreferencesValue {
  paperless: boolean;
  sms_reminders: boolean;
  autopay: boolean;
  preferred_language: string;
}

/** `On` / `Off` — a preference drawn as a dropdown (images 02, 03). */
export function OnOffField(props: {
  id: string;
  label: string;
  value: boolean;
  onChange: (on: boolean) => void;
  t: Translator;
}) {
  return (
    <SelectField
      id={props.id}
      label={props.label}
      value={props.value ? "on" : "off"}
      onChange={(value) => props.onChange(value === "on")}
      options={[
        { value: "on", label: props.t("customers.moveIn.prefs.on") },
        { value: "off", label: props.t("customers.moveIn.prefs.off") },
      ]}
    />
  );
}

/**
 * *Preferences* with *Set preferences* ticked on its heading row. Unticked, the
 * heading alone (image 44's state on Move-in).
 *
 * ⚠ **UNTICKING IS THE HOST'S TO INTERPRET** (`onTick`): Move-in sets every
 * election back to Off and drops a paired discount; a request does the first
 * half only. The language is never reset — it is the utility's default, not an
 * election.
 */
export function PreferencesPanel(props: {
  on: boolean;
  onTick: (on: boolean) => void;
  value: PreferencesValue;
  onChange: (patch: Partial<PreferencesValue>) => void;
  /** Autopay — only where a payment method can be saved (PO 2026-10-18). */
  showAutopay: boolean;
  /** Drawn after the four when autopay is On — Move-in's *Autopay from*. */
  autopayFrom?: ReactNode;
  /** The tick's id — two panels on one page must not share one. */
  tickId?: string;
  t: Translator;
  client?: ApiClient;
}) {
  const { t, value } = props;
  // A REQUIRED prop, read once: every host says yes or no out loud.
  const showAutopay = props.showAutopay;
  const columns = showAutopay ? "grid-cols-4" : "grid-cols-3";
  return (
    <Panel
      as="section"
      title={t("customers.moveIn.prefs.title")}
      trailing={
        <CheckboxField
          id={props.tickId ?? "move_in_prefs_on"}
          label={t("customers.moveIn.prefs.tick")}
          checked={props.on}
          onChange={props.onTick}
        />
      }
      data-billing-section="preferences"
      data-billing-section-open={props.on ? "true" : "false"}
    >
      {props.on ? (
        <div className={`grid ${columns} gap-x-6 gap-y-5`}>
          {showAutopay ? (
            <OnOffField
              id="autopay"
              label={t("customers.moveIn.prefs.autopay")}
              value={value.autopay}
              onChange={(autopay) => props.onChange({ autopay })}
              t={t}
            />
          ) : null}
          <OnOffField
            id="paperless"
            label={t("customers.moveIn.prefs.paperless")}
            value={value.paperless}
            onChange={(paperless) => props.onChange({ paperless })}
            t={t}
          />
          <OnOffField
            id="sms_reminders"
            label={t("customers.moveIn.prefs.sms")}
            value={value.sms_reminders}
            onChange={(sms_reminders) => props.onChange({ sms_reminders })}
            t={t}
          />
          <PortalLanguageField
            value={value.preferred_language}
            onChange={(preferred_language) => props.onChange({ preferred_language })}
            t={t}
            client={props.client}
          />
          {showAutopay && value.autopay ? props.autopayFrom : null}
        </div>
      ) : null}
    </Panel>
  );
}
