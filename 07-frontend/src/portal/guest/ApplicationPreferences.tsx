// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-10250 — PO 2026-10-18, verbatim: *"we should consider these
//           field also consistently - Autopay, paperless, text reminders,
//           language"*; decision log the same day: Paperless, Text reminders
//           and Language on every screen including the portal, Autopay only
//           where a payment method can be saved — so NOT here. Image
//           04-portal.png draws the panel.
// Rules:    B14 rule 43 · rule 44 · rule 33 (labels ≤ 3 words) · the portal
//           accessibility questions
// Tests:    src/portal/guest/AboutYouMoveInFields.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { FormField, SelectInput } from "../components/primitives";
import { FormSection, ThreeUp } from "../components/FormSection";
import { languageName } from "../components/languageName";
import { offeredLocales } from "../components/language";

export interface PreferencesValue {
  /** The header tick — *Set preferences*. Unticked sends all three as unset. */
  on: boolean;
  paperless: boolean;
  text_reminders: boolean;
  language: string;
}

export function preferencesFromDraft(draft: {
  paperless?: boolean | null;
  text_reminders?: boolean | null;
  preferred_language?: string | null;
} | null): PreferencesValue {
  const set =
    (draft?.paperless ?? null) !== null ||
    (draft?.text_reminders ?? null) !== null ||
    (draft?.preferred_language ?? "") !== "";
  return {
    on: set,
    paperless: draft?.paperless === true,
    text_reminders: draft?.text_reminders === true,
    language: draft?.preferred_language ?? "",
  };
}

/** The draft's own field names. An unticked panel says nothing (`null`). */
export function preferencesPayload(value: PreferencesValue): Record<string, unknown> {
  if (!value.on) {
    return { paperless: null, text_reminders: null, preferred_language: null };
  }
  return {
    paperless: value.paperless,
    text_reminders: value.text_reminders,
    preferred_language: value.language || null,
  };
}

export function ApplicationPreferences(props: {
  value: PreferencesValue;
  /** The portal's language offer (`PORTAL_LOCALES`), off the draft. */
  locales: readonly string[];
  onCommit: (next: PreferencesValue) => void;
}) {
  const { t, i18n } = useTranslation();
  const value = props.value;
  const commit = (part: Partial<PreferencesValue>) => props.onCommit({ ...value, ...part });
  const onOff = [
    { value: "on", label: t("portal.apply.preferences.on") },
    { value: "off", label: t("portal.apply.preferences.off") },
  ];
  const languages = offeredLocales(props.locales, value.language).map((code) => ({
    value: code,
    label: languageName(code),
    // Each language is named in itself, so it is marked as such (DEF-CWP-10561).
    lang: code,
  }));
  return (
    <FormSection
      title={t("portal.apply.preferences.title")}
      testId="preferences"
      tick={{
        id: "preferences_on",
        label: t("portal.apply.preferences.tick"),
        checked: value.on,
        // Ticking opens the panel on the language the page is being read in,
        // which is the only choice we can see them make already.
        onChange: (checked) =>
          commit({ on: checked, language: value.language || (checked ? (i18n.language ?? "").split("-")[0] : "") }),
      }}
    >
      {value.on ? (
        <ThreeUp>
          <FormField id="pref_paperless" label={t("portal.apply.preferences.paperless")}>
            <SelectInput
              id="pref_paperless"
              value={value.paperless ? "on" : "off"}
              options={onOff}
              onChange={(next) => commit({ paperless: next === "on" })}
            />
          </FormField>
          <FormField id="pref_text_reminders" label={t("portal.apply.preferences.textReminders")}>
            <SelectInput
              id="pref_text_reminders"
              value={value.text_reminders ? "on" : "off"}
              options={onOff}
              onChange={(next) => commit({ text_reminders: next === "on" })}
            />
          </FormField>
          <FormField id="pref_language" label={t("portal.apply.preferences.language")}>
            <SelectInput
              id="pref_language"
              value={value.language}
              options={languages}
              onChange={(language) => commit({ language })}
            />
          </FormField>
        </ThreeUp>
      ) : null}
    </FormSection>
  );
}
