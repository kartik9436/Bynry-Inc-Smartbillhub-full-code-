// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-017 · US-SHL-018 (EP-SHL-05 addendum r2 — eleven locales)  Screens: S48, S6
// Rules:    BR-SHL-030 (data-driven catalogs — adding a language is data, never code) ·
//           BR-SHL-041 (the ELEVEN codes live in ONE registry the picker, the tenant default
//           and the per-user override all read) · BR-SHL-043 (machine translation is permitted
//           for staff-UI catalogs AND MARKED — `translation_status: human | machine_unverified`)
// ───────────────────────────────────────────────────────
// i18n bootstrap (FI-03, B13 §2).
// TD-16: UI strings live in these client-side catalogs — every user-visible
// string is a key (B8; no concatenated sentences). Customer DOCUMENTS (bills,
// notices, receipts) are rendered server-side and never use these catalogs.
//
// ── Why eleven, and why the registry below is the only list ────────────────
// The PO expanded the ratified five (`en · es · es-MX · de · hi`, PO LC-1..3
// 2026-08-08) to ELEVEN on 2026-08-10 from a picker mock-up: BR-SHL-041 names
// them `en-US · es-ES · es-419 · de-DE · hi-IN · fr-FR · id-ID · it-IT · ja-JP
// · ko-KR · pt-BR`. The six NEW ones land here under exactly those codes. The
// five EXISTING ones keep their pre-expansion codes (`en`/`es`/`es-MX`/`de`/
// `hi`) until US-SHL-018 runs BR-SHL-042's re-tag — that story owns rewriting
// `tenant_settings.default_language` and `accounts.preferred_language`, and
// renaming the files here without that migration would orphan every stored
// value. So this registry is deliberately mid-migration and says so; it is not
// an oversight and it is not a second naming scheme.
//
// ⚠ **`user_preferences` USED TO BE LISTED IN THAT SENTENCE AND DOES NOT
// BELONG THERE (corrected 2026-08-24 with DEF-647).** That table now genuinely
// holds rows — the column chooser's `table.<screen>.columns`, since the
// `GET|PUT /user-preferences/{key}` round trip landed — and NO row in it
// carries a language tag: nothing writes a `shell.language` key, in this file
// or anywhere else. Naming it here made the re-tag look larger than it is and,
// worse, implied a stored language preference that has never existed. If
// US-SHL-018 ever adds one, it is a `shell.*` key and it goes back on this
// list with the code that writes it — hard-won law 1: a comment claiming a
// mechanism is not the mechanism.
//
// ── `translationStatus` is BR-SHL-043's marking, and it is not decoration ──
// The PO ruled machine translation acceptable as a first pass ("machine for
// time being; later I will get it edited by human", 2026-08-10, ratified the
// same day). The rule's own words are that such a catalog is MARKED, so the
// marking lives here rather than in a comment somebody can contradict.
// Every catalog reads `machine_unverified` today, the five originals included:
// no human-translation review is recorded anywhere in this repo for ANY of
// them (they were produced lane by lane alongside the screens that needed the
// keys), and between claiming a review that did not happen and claiming one
// that may have, the fail-closed reading is the only honest one (hard-won law
// 3). A catalog moves to `human` when a reviewer signs it off in
// 12-governance, never because it looks finished.
//
// ⚠ NOT IMPLEMENTED HERE, stated so no reader mistakes this file for it (law
// 1): BR-SHL-040 requires the catalogs to load LAZILY, one locale at a time —
// they are static imports below, so every user still downloads all eleven.
// That is US-SHL-017's own work and it is not done; the rule is PROPOSED and
// the measurement that motivates it (824,000 of 1,546,871 bundle bytes were
// translation JSON at five) only grows here. Do not read the eleven-entry
// registry as evidence the lazy-chunk requirement was met.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// ⚠ **ONE EAGER GLOB, NOT ELEVEN `import … from "*.json"` — `DEF-DEP-10115`.**
// With `resolveJsonModule`, `tsc` builds a literal type for every key of every
// catalogue it is shown — about 400 MB of the image build's typecheck, which
// was killed (exit 137) on the PO's build host on 2026-10-13. Vite inlines an
// eager glob exactly as it inlines a static import, so the BUNDLE is the same
// eleven catalogues; only the typechecker stops inferring them. Lazy loading
// (BR-SHL-040 above) is still not done and this is not it.
const CATALOGS = import.meta.glob<Record<string, string>>("./locales/*.json", {
  eager: true,
  import: "default",
});

/** The catalogue for one file name; a missing file is a build fault, so it throws. */
function catalogFile(file: string): Record<string, string> {
  const catalog = CATALOGS[`./locales/${file}.json`];
  if (catalog === undefined) throw new Error(`i18n: no catalogue ./locales/${file}.json`);
  return catalog;
}

const de = catalogFile("de");
const en = catalogFile("en");
const esMX = catalogFile("es-MX");
const es = catalogFile("es");
const frFR = catalogFile("fr-FR");
const hi = catalogFile("hi");
const idID = catalogFile("id-ID");
const itIT = catalogFile("it-IT");
const jaJP = catalogFile("ja-JP");
const koKR = catalogFile("ko-KR");
const ptBR = catalogFile("pt-BR");

/** BR-SHL-043: how a catalog's strings were produced, and whether a human has read them. */
export type TranslationStatus = "human" | "machine_unverified";

export interface LocaleEntry {
  /** BCP-47 code. The value stored in tenant/account/user language columns. */
  readonly code: string;
  /**
   * The language named the way that language names itself, from the PO's S48
   * picker mock-up (2026-08-10). It lives here rather than in a catalog key
   * because an endonym reads the same in every language — G15 already
   * allowlists the five existing endonyms across all catalogues for exactly
   * that reason, so a catalog key would be eleven copies of one constant.
   *
   * TRANSITIONAL, stated so it is not mistaken for a design: the five
   * pre-expansion codes ALSO still have `settings.regional.language.<code>`
   * catalog entries from before this registry existed, and S8 still prefers
   * them where they exist so no shipped copy changes under anyone's feet.
   * US-SHL-018's re-tag is the story that consolidates the two.
   */
  readonly nativeLabel: string;
  readonly translationStatus: TranslationStatus;
  readonly catalog: Record<string, string>;
}

/**
 * BR-SHL-041's ONE registry. The picker (S48), the tenant default (S6) and the
 * per-user override all read this; `SettingsRegionalTab.LANGUAGE_OPTIONS` and
 * the server's `apps/tenancy/services.SEED_LANGUAGES` are its two mirrors, and
 * a code this list does not carry must never be offered by either.
 */
export const LOCALE_REGISTRY: readonly LocaleEntry[] = [
  { code: "en", nativeLabel: "English", translationStatus: "machine_unverified", catalog: en },
  { code: "es", nativeLabel: "Español", translationStatus: "machine_unverified", catalog: es },
  {
    code: "es-MX",
    nativeLabel: "Español (México)",
    translationStatus: "machine_unverified",
    catalog: esMX,
  },
  { code: "de", nativeLabel: "Deutsch", translationStatus: "machine_unverified", catalog: de },
  { code: "hi", nativeLabel: "हिन्दी", translationStatus: "machine_unverified", catalog: hi },
  // The six added 2026-08-11 under BR-SHL-041's own codes, first-pass machine
  // translation of en.json per BR-SHL-043.
  {
    code: "fr-FR",
    nativeLabel: "Français (France)",
    translationStatus: "machine_unverified",
    catalog: frFR,
  },
  {
    code: "id-ID",
    nativeLabel: "Indonesia (Indonesia)",
    translationStatus: "machine_unverified",
    catalog: idID,
  },
  {
    code: "it-IT",
    nativeLabel: "Italiano (Italia)",
    translationStatus: "machine_unverified",
    catalog: itIT,
  },
  {
    code: "ja-JP",
    nativeLabel: "日本語 (日本)",
    translationStatus: "machine_unverified",
    catalog: jaJP,
  },
  {
    code: "ko-KR",
    nativeLabel: "한국어 (대한민국)",
    translationStatus: "machine_unverified",
    catalog: koKR,
  },
  {
    code: "pt-BR",
    nativeLabel: "Português (Brasil)",
    translationStatus: "machine_unverified",
    catalog: ptBR,
  },
];

/** Just the codes, in registry order. */
export const LOCALE_CODES: readonly string[] = LOCALE_REGISTRY.map((entry) => entry.code);

/** The native label for a code, or the code itself when it is not registered. */
export function localeLabel(code: string): string {
  return LOCALE_REGISTRY.find((entry) => entry.code === code)?.nativeLabel ?? code;
}

// FI-06 harness hook: no language-switcher UI exists yet (FI-03's switcher
// lands with the S48/user-profile packet, BR-SHL-030) — until then the E2E
// smoke drives changeLanguage through this window handle (e2e/W0-smoke.spec.ts).
// Browser only: the vitest node environment has no window. Retire the handle
// when the real switcher ships.
declare global {
  interface Window {
    __SMARTBILLHUB_I18N__?: typeof i18n;
  }
}

/**
 * `<html lang>` follows the catalogue (WCAG 3.1.1, `DEF-CWP-10561`; decision
 * log 2026-10-23, *"Group D"*).
 *
 * ⚠ **ONE PLACE, AND IT IS HERE, BECAUSE EVERY SWITCH PASSES THROUGH HERE.**
 * `index.html` declares `lang="en"` and nothing updated it, so after a switch
 * to Español a screen reader went on reading Spanish words with an English
 * voice — on the portal AND the staff app, since both change language only
 * through this one i18n instance. The listener is registered BEFORE `init`,
 * whose own first `changeLanguage` fires the event, so the first load is
 * covered without a second code path.
 *
 * The value is the catalogue's own code (`es`, `es-MX`, `fr-FR`, …), which is
 * already BCP-47.
 */
export function syncDocumentLanguage(code: string | undefined): void {
  if (typeof document === "undefined" || !code) return;
  document.documentElement.lang = code;
}
i18n.on("languageChanged", syncDocumentLanguage);

void i18n.use(initReactI18next).init({
  resources: Object.fromEntries(
    LOCALE_REGISTRY.map((entry) => [entry.code, { translation: entry.catalog }]),
  ),
  lng: "en",
  fallbackLng: "en",
  // Catalog keys are flat opaque IDs ("app.name") — dots are literal, not nesting.
  keySeparator: false,
  interpolation: {
    // React already escapes rendered strings.
    escapeValue: false,
  },
});

// Belt and braces for the first load: `init` with inline resources resolves
// synchronously, so this reads the language it settled on.
syncDocumentLanguage(i18n.language);

if (typeof window !== "undefined") {
  window.__SMARTBILLHUB_I18N__ = i18n;
}

export default i18n;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-017@d39c862 (story+rules snapshot hash — EP-SHL-05 addendum r2; co-packet US-SHL-018@d39c862)
// generated: 2026-08-11 by story-coder v1 (eleven-locale lane — PO ruling 2026-08-10, B12 addendum r7)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 858 passed / 183 todo across 58 files✔ (831 passed / 180 todo across 57 files was the pre-lane baseline — this lane adds 27 passing + 3 todo and dropped nothing) · G15 i18n-parity PASS: 10 catalogue(s) carry the same 3087 key(s) as en.json; 30870 value(s) translated or allowlisted (4 catalogues × 3086 keys was the pre-lane baseline) · G15 RED-proved four ways before trusting it green (law 7): a key deleted from ja-JP.json, an extra key added to it, an English value pasted into it, and — for the in-suite placeholder test — {{address}} dropped from fr-FR's tenancy.signup.utility.available; each named its own defect and each went green on restore · run_gates 13 PASS · 2 FAIL · 1 SKIP — the two FAILs are G1 and G7 on SEVEN 06-backend files of a CONCURRENT r17 custom-fields lane (apps/{assets,customers,metering}/migrations/*_r17_custom_data.py, apps/billing/custom_snapshot.py, apps/billing/migrations/0009_w2_custom_snapshot.py, db/rls_tenancy_custom_field.sql, core/idempotency.py); none belongs to this lane, whose only backend touch is apps/tenancy/services.SEED_LANGUAGES · backend pytest tests/test_us_ten_005_006_settings.py tests/test_us_cus_003_account_write.py 63 passed✔
// exceptions: E1 BR-SHL-040 (lazy per-locale chunks) is NOT implemented — the eleven catalogs are static imports and the bundle carries all of them; that is US-SHL-017's remaining half and is reported, not silently skipped · E1 BR-SHL-042's re-tag of the five existing codes to `en-US`/`es-ES`/`es-419`/`de-DE`/`hi-IN` is US-SHL-018's data migration and is NOT done here, so this registry is mid-migration by design
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
