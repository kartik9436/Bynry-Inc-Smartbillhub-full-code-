// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-017 · US-SHL-018 (EP-SHL-05 addendum r2 — eleven locales)  Screens: S48, S6
// Rules:    BR-SHL-030 (adding a language is DATA, never code) · BR-SHL-041 (the eleven codes
//           live in ONE registry the picker, the tenant default and the per-user override all
//           read) · BR-SHL-043 (machine translation permitted for staff-UI catalogs AND marked)
// ───────────────────────────────────────────────────────
// The catalogue-shape suite. G15 already compares every catalogue to en.json in
// the gate run; these tests exist because a gate that only runs in CI is found
// minutes later, and because two of the assertions below are ones G15 cannot
// make at all:
//
//   1. PLACEHOLDER SURVIVAL. G15 compares key SETS and flags values byte-equal
//      to English. A translation that drops `{{address}}` passes both checks and
//      renders a sentence with a hole in it, or — worse — prints the literal
//      braces on a customer-visible screen. Machine translation is exactly the
//      process that reorders and occasionally eats a token, so the guarantee has
//      to be asserted, not assumed (hard-won law 1).
//   2. WIRING. Eleven catalogues that no control can select are eleven dead
//      files: they render nothing, every test passes and the feature does not
//      exist (hard-won law 2). So the registry is checked against the codes S8
//      actually offers.
import { describe, expect, it } from "vitest";

import { LANGUAGE_OPTIONS } from "@/features/tenancy/SettingsRegionalTab";

import i18n, { LOCALE_CODES, LOCALE_REGISTRY, localeLabel } from "./index";
import en from "./locales/en.json";

/**
 * Every `{{interpolation}}` and every `{token}` the copy shows literally
 * (`{seq}`, `{floor}`, `{YYYY}`, the `{00000}` counter, the `{id}` in an API
 * path). Deliberately NOT "any pair of braces": `settings.numbering.problem.
 * unbalanced_braces` reads "A { is missing its }." — that is prose ABOUT
 * braces, and its words must be translated like any other sentence. Written
 * loosely, this regex called that string a placeholder, and the generator that
 * shared the definition shipped English inside the braces in all six new
 * catalogues. Both were tightened together.
 */
const TOKENS = /\{\{[^{}\s]+\}\}|\{[A-Za-z0-9_]+\}/g;

function tokensOf(value: string): string[] {
  return [...new Set(value.match(TOKENS) ?? [])].sort();
}

const ENGLISH = en as Record<string, string>;

describe("US-SHL-017 — BR-SHL-041's eleven locales come from one registry", () => {
  it("US-SHL-017: the registry is exactly the eleven codes BR-SHL-041 confirms", () => {
    // The five originals keep their pre-expansion spelling until US-SHL-018's
    // BR-SHL-042 migration rewrites the stored values; the six new ones carry
    // the region-qualified codes the rule confirms, having no earlier spelling.
    expect(LOCALE_CODES).toEqual([
      "en",
      "es",
      "es-MX",
      "de",
      "hi",
      "fr-FR",
      "id-ID",
      "it-IT",
      "ja-JP",
      "ko-KR",
      "pt-BR",
    ]);
    expect(LOCALE_REGISTRY).toHaveLength(11);
  });

  it("US-SHL-017: every registered locale is offered by the S8 Regional picker — a catalogue nothing can select is dead weight", () => {
    for (const code of LOCALE_CODES) {
      expect(LANGUAGE_OPTIONS).toContain(code);
    }
    // The converse does NOT hold and is not asserted as if it did: `en-US` is an
    // accepted server code with no catalogue of its own, offered since W0 and
    // resolved by i18next's `fallbackLng: "en"`. It is named here so the gap is
    // a recorded fact rather than a silent asymmetry.
    expect(LANGUAGE_OPTIONS.filter((code) => !LOCALE_CODES.includes(code))).toEqual(["en-US"]);
  });

  it("US-SHL-017: every locale resolves to a native label, never to its raw code", () => {
    for (const entry of LOCALE_REGISTRY) {
      expect(localeLabel(entry.code)).toBe(entry.nativeLabel);
      expect(localeLabel(entry.code)).not.toBe(entry.code);
    }
    // An unregistered code degrades to itself rather than throwing — a stored
    // value from before a rename must still render something.
    expect(localeLabel("kling-on")).toBe("kling-on");
  });

  it("US-SHL-017: the S8 option label expression resolves for every offered code — no raw key reaches the select", () => {
    // This is literally the expression SettingsRegionalTab passes to SelectField.
    // Asserting it here rather than only asserting the registry is the
    // difference between "the labels exist" and "the screen shows them": a
    // `t()` call whose key is absent renders the KEY, which is the shipped
    // defect G15 was written for, one control further along.
    for (const code of LANGUAGE_OPTIONS) {
      const label = i18n.t(`settings.regional.language.${code}`, {
        defaultValue: localeLabel(code),
      });
      expect(label).not.toBe(`settings.regional.language.${code}`);
      expect(label.length).toBeGreaterThan(0);
    }
    // The six new codes have no catalogue entry, so the registry answers.
    expect(i18n.t("settings.regional.language.fr-FR", { defaultValue: localeLabel("fr-FR") })).toBe(
      "Français (France)",
    );
    expect(i18n.t("settings.regional.language.ja-JP", { defaultValue: localeLabel("ja-JP") })).toBe(
      "日本語 (日本)",
    );
    // The five originals still answer from the catalogue, unchanged.
    expect(i18n.t("settings.regional.language.de", { defaultValue: localeLabel("de") })).toBe(
      "Deutsch",
    );
  });

  it("US-SHL-017: each of the eleven is registered as an i18next resource bundle", () => {
    for (const code of LOCALE_CODES) {
      expect(i18n.getResource(code, "translation", "app.name")).toBe("SMART360 Next");
    }
  });

  it("US-SHL-017 TC-6: a key absent from every catalogue falls back for that key only, not for the page", () => {
    expect(i18n.getResource("fr-FR", "translation", "no.such.key")).toBeUndefined();
    expect(i18n.getResource("fr-FR", "translation", "app.name")).toBe("SMART360 Next");
  });
});

describe("US-SHL-017 — catalogue parity and placeholder survival (the G15 contract, asserted in-suite)", () => {
  const catalogues = LOCALE_REGISTRY.filter((entry) => entry.code !== "en");

  it.each(catalogues.map((entry) => entry.code))(
    "US-SHL-017: %s carries exactly en.json's key set",
    (code) => {
      const catalogue = LOCALE_REGISTRY.find((entry) => entry.code === code)!.catalog;
      expect(Object.keys(catalogue).sort()).toEqual(Object.keys(ENGLISH).sort());
    },
  );

  it.each(catalogues.map((entry) => entry.code))(
    "US-SHL-017: %s keeps every interpolation placeholder the English value carries, and invents none",
    (code) => {
      const catalogue = LOCALE_REGISTRY.find((entry) => entry.code === code)!.catalog;
      const broken: string[] = [];
      for (const [key, english] of Object.entries(ENGLISH)) {
        const wanted = tokensOf(english);
        if (wanted.length === 0) continue;
        const got = tokensOf(catalogue[key] ?? "");
        if (JSON.stringify(wanted) !== JSON.stringify(got)) {
          broken.push(`${key}: expected ${wanted.join(",")} got ${got.join(",") || "none"}`);
        }
      }
      expect(broken).toEqual([]);
    },
  );
});

describe("US-SHL-018 — BR-SHL-043: a machine-translated catalogue says so", () => {
  it("US-SHL-018 TC-5: every catalogue carries a translation_status, and the marking is metadata rather than a banner", () => {
    for (const entry of LOCALE_REGISTRY) {
      expect(["human", "machine_unverified"]).toContain(entry.translationStatus);
    }
    // The six added 2026-08-11 are first-pass machine translation of en.json.
    // The five originals read the same because NO human translation review is
    // recorded for them either — claiming `human` where no sign-off exists is
    // the failure hard-won law 1 is about, and law 3 says the unsafe option is
    // the one you have to type.
    expect(LOCALE_REGISTRY.every((entry) => entry.translationStatus === "machine_unverified")).toBe(
      true,
    );
    // The marking does not reach the rendered UI: a machine_unverified catalogue
    // renders exactly like any other.
    expect(i18n.getResource("ja-JP", "translation", "app.name")).toBe("SMART360 Next");
  });

  it.todo(
    "US-SHL-018 TC-1: the S48 profile picker lists all eleven with native labels — S48's language control is not built yet (the registry it will read is)",
  );
  it.todo(
    "US-SHL-018 TC-3: BR-SHL-042's es-MX→es-419 migration over stored language values — server/data scope, and the five codes here still carry their pre-expansion spelling until it runs",
  );
  it.todo(
    "US-SHL-017 TC-1/TC-3: BR-SHL-040's lazy per-locale chunks — the eleven catalogues are static imports today, so no chunk assertion would be honest",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-017@d39c862 (story+rules snapshot hash — EP-SHL-05 addendum r2; co-packet US-SHL-018@d39c862)
// generated: 2026-08-11 by story-coder v1 (eleven-locale lane — PO ruling 2026-08-10, B12 addendum r7)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 858 passed / 183 todo across 58 files✔ (831 passed / 180 todo across 57 files was the pre-lane baseline — this lane adds 27 passing + 3 todo and dropped nothing) · G15 i18n-parity PASS: 10 catalogue(s) carry the same 3087 key(s) as en.json; 30870 value(s) translated or allowlisted (4 catalogues × 3086 keys was the pre-lane baseline) · G15 RED-proved four ways before trusting it green (law 7): a key deleted from ja-JP.json, an extra key added to it, an English value pasted into it, and — for the in-suite placeholder test — {{address}} dropped from fr-FR's tenancy.signup.utility.available; each named its own defect and each went green on restore · run_gates 13 PASS · 2 FAIL · 1 SKIP — the two FAILs are G1 and G7 on SEVEN 06-backend files of a CONCURRENT r17 custom-fields lane (apps/{assets,customers,metering}/migrations/*_r17_custom_data.py, apps/billing/custom_snapshot.py, apps/billing/migrations/0009_w2_custom_snapshot.py, db/rls_tenancy_custom_field.sql, core/idempotency.py); none belongs to this lane, whose only backend touch is apps/tenancy/services.SEED_LANGUAGES · backend pytest tests/test_us_ten_005_006_settings.py tests/test_us_cus_003_account_write.py 63 passed✔
// exceptions: E1 the placeholder assertion is written against the SET of tokens per value, not their multiplicity — Japanese and Korean legitimately repeat a subject, so `{{name}} … {{name}}` is a correct rendering of a one-placeholder English sentence and interpolates fine; a MISSING or INVENTED token is the failure and is what goes red · E4 US-SHL-018 TC-1's real assertion needs the S48 language control, which is not built — recorded as an it.todo rather than faked against the registry alone
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
