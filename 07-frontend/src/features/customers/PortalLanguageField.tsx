// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6364 — *Preferred language* was a free-text box with a
//           rationale under it, on the move-in's Account preferences step.
// Rulings:  PO 2026-09-23, verbatim: *"prefered language shoud be dropdown ;it
//           should come from setting; default should be utilities default
//           language ;langiage prefrence for portal only"* · `OQ-CUS-12619`
//           CLOSED (a) — SUPERSEDED FOR MESSAGES 2026-10-29 (PO option B,
//           *"Question: which language should messages be sent in? - B"*): the
//           field drives the portal AND every message, so it is labelled
//           *Preferred language*, the account screen's own words.
// Rules:    BR-CUS-064 (`accounts.preferred_language`, validated against the
//           utility's language set) · BR-SHL-041 (the twelve accepted codes) ·
//           B14 rules 21 (Tailwind; this file adds no class), 33, 43
// Tests:    PortalLanguageField.dom.test.tsx · MoveInWizard.test.tsx ·
//           NewAccountWizard.test.tsx
// Hosts:    MoveInWizard.tsx (step 4) · NewAccountWizard.tsx (preferences)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE LIST IS THE SETTINGS PAGE'S OWN.** `LANGUAGE_OPTIONS` is what
// Settings → Regional offers as the utility's language and is the server's
// `SEED_LANGUAGES` verbatim, so nothing is offered that the account write would
// refuse. There is no per-utility subset of languages anywhere in the product;
// if one is ever built, it replaces this import and nothing else.
//
// ⚠ **THE DEFAULT IS WRITTEN INTO THE FORM, NOT MERELY SHOWN.** A select that
// displays the utility's language while the form holds `""` would save
// nothing — the screen and the payload would disagree. So an empty value takes
// the utility's language the moment it is known, and the clerk sees exactly
// what will be saved.
//
// ⛔ **NOTHING HERE TOUCHES NOTIFICATIONS.** The value saved here is read by
// the server, which sends each message in it where the utility published that
// wording (`BR-NOT-006` as amended 2026-10-29); this file only collects it.
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getShellDisplay } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { SelectField } from "@/components/FormModal";
import { localeLabel } from "@/i18n";
import { LANGUAGE_OPTIONS } from "@/features/tenancy/SettingsRegionalTab";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The options, with a stored code the list does not hold kept rather than
 *  silently replaced (a legacy value is a fact about the data). */
export function portalLanguageOptions(value: string, t: Translator): { value: string; label: string }[] {
  const trimmed = value.trim();
  const codes =
    trimmed === "" || LANGUAGE_OPTIONS.includes(trimmed) ? LANGUAGE_OPTIONS : [...LANGUAGE_OPTIONS, trimmed];
  return codes.map((code) => ({
    value: code,
    label: t(`settings.regional.language.${code}`, { defaultValue: localeLabel(code) }),
  }));
}

export function PortalLanguageField(props: {
  value: string;
  onChange: (value: string) => void;
  t: Translator;
  client?: ApiClient;
}) {
  const { t, value, onChange } = props;
  const client = props.client ?? api;
  // `GET /shell/display` — the read every role may make (`DEF-SHL-4272`); the
  // shell has already fetched it, so this is a cache hit.
  const display = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const utilityDefault = display.data?.regional?.language ?? null;

  useEffect(() => {
    if (value === "" && utilityDefault !== null && utilityDefault !== "") {
      onChange(utilityDefault);
    }
  }, [value, utilityDefault, onChange]);

  return (
    <SelectField
      id="preferred_language"
      label={t("customers.account.field.preferredLanguage")}
      value={value.trim()}
      options={portalLanguageOptions(value, t)}
      placeholder={t("settings.regional.choose")}
      onChange={onChange}
    />
  );
}
