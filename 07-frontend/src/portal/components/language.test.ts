// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-CWP-4440 — the customer portal never applied a language.
// Rules:   BR-CWP-105 (the order, and whose language wins) · BR-SHL-041 (the
//          eleven catalogues are one registry)
// ─────────────────────────────────────────────────────────────────────────
//
// `BR-CWP-105`'s chain, branch by branch, as arithmetic — no mount, no query,
// no DOM. The wire is asserted in `PortalLanguage.dom.test.tsx`; this file
// asserts the RULE, so a lane that changes the order has to change a test that
// says the order out loud.
import { describe, expect, it } from "vitest";

import { LOCALE_CODES } from "@/i18n";

import { offeredLocales, resolvePortalLanguage, supportedLocale } from "./language";

/** All four absent — a real state on a fresh tenant with a plain browser. */
const NONE = { account: null, guestChoice: null, tenant: null, browser: null };

describe("supportedLocale — can this build DRAW it", () => {
  it("takes a catalogue code as it stands", () => {
    expect(supportedLocale("es-MX")).toBe("es-MX");
    expect(supportedLocale("en")).toBe("en");
  });

  it("falls to the BASE language for a region this build has no catalogue for", () => {
    // ⚠ THE CASE THAT MADE THIS FUNCTION NECESSARY. `en-US` is one of the
    // server's twelve `SEED_LANGUAGES`, is saveable on Settings → Regional
    // today, and has NO catalogue among the eleven. Handed to i18next raw it
    // would land on the `en` fallback and look like it worked.
    expect(supportedLocale("en-US")).toBe("en");
    expect(supportedLocale("es-419")).toBe("es");
  });

  it("finds the one catalogue whose base matches a bare browser code", () => {
    // `navigator.language` is `fr` on plenty of machines and there is exactly
    // one French catalogue to mean.
    expect(supportedLocale("fr")).toBe("fr-FR");
    expect(supportedLocale("pt")).toBe("pt-BR");
  });

  it("answers nothing for a language this build cannot draw", () => {
    expect(supportedLocale("cy")).toBeNull();
    expect(supportedLocale("zz-ZZ")).toBeNull();
  });

  it("treats an empty or absent value as no choice at all", () => {
    // `tenant_settings.language` is a bare TEXT column and `""` reaching
    // `changeLanguage` is a language switch to nothing.
    expect(supportedLocale("")).toBeNull();
    expect(supportedLocale("   ")).toBeNull();
    expect(supportedLocale(null)).toBeNull();
    expect(supportedLocale(undefined)).toBeNull();
  });

  it("only ever answers with a code the app actually carries", () => {
    for (const probe of ["en-US", "fr", "pt", "es-419", "es-MX", "hi"]) {
      const answer = supportedLocale(probe);
      if (answer !== null) expect(LOCALE_CODES).toContain(answer);
    }
  });
});

describe("resolvePortalLanguage — BR-CWP-105's order", () => {
  it("gives a signed-in customer THEIR OWN account language over everything", () => {
    // PO 2026-09-07: *"a signed-in customer will get their account's own
    // preferred language - Signed customer should get their own references."*
    expect(
      resolvePortalLanguage({
        account: "de",
        guestChoice: "ja-JP",
        tenant: "es-MX",
        browser: "fr-FR",
      }),
    ).toBe("de");
  });

  it("does NOT let the utility's default overrule a customer who stated one", () => {
    // The single sentence of the PO's ruling, isolated: tenant set, account
    // set, they differ, and the ACCOUNT is what comes back.
    expect(
      resolvePortalLanguage({ ...NONE, account: "de", tenant: "es-MX" }),
    ).toBe("de");
  });

  it("gives a guest their own dropdown choice over the utility's default", () => {
    expect(
      resolvePortalLanguage({ ...NONE, guestChoice: "de", tenant: "es-MX" }),
    ).toBe("de");
  });

  it("starts a guest in the UTILITY's language when they have chosen nothing", () => {
    expect(resolvePortalLanguage({ ...NONE, tenant: "es-MX", browser: "fr-FR" })).toBe("es-MX");
  });

  it("falls to the browser only when nobody has stated anything", () => {
    expect(resolvePortalLanguage({ ...NONE, browser: "fr-FR" })).toBe("fr-FR");
  });

  it("applies NOTHING when no source names a language this build can draw", () => {
    // ⚠ `null` means *apply nothing*, NOT *fall back to English*. Applying
    // English over a tenant whose setting has not loaded is `DEF-SHL-3964`'s
    // plausible-default trap, and the customer would see it as a flicker.
    expect(resolvePortalLanguage(NONE)).toBeNull();
    expect(resolvePortalLanguage({ ...NONE, tenant: "cy", browser: "zz" })).toBeNull();
  });

  it("steps PAST a source it cannot draw rather than stopping there", () => {
    // A tenant on a language with no catalogue must not black-hole the chain:
    // the browser behind it is still a better answer than English.
    expect(resolvePortalLanguage({ ...NONE, tenant: "cy", browser: "de" })).toBe("de");
  });

  it("clamps every step, not only the first", () => {
    // The tenant's `en-US` is lawful and undrawable; it must arrive as `en`.
    expect(resolvePortalLanguage({ ...NONE, tenant: "en-US" })).toBe("en");
    expect(resolvePortalLanguage({ ...NONE, account: "en-US" })).toBe("en");
  });

  it("falls to the tenant when a login's accounts DISAGREE", () => {
    // The server folds that case to `null` in `selectors.account_language` —
    // *what the accounts agree on, and nothing when they do not* — so a
    // landlord with four languages on four accounts reads the utility's own
    // language rather than whichever an ordering put first.
    expect(resolvePortalLanguage({ ...NONE, account: null, tenant: "es-MX" })).toBe("es-MX");
  });
});

// ══ What the picker may OFFER — DEF-CWP-4442 ══════════════════════════════
//
// ⚠ **A DIFFERENT QUESTION FROM EVERY CASE ABOVE, AND `BR-CWP-105` FORBIDS
// FOLDING THE TWO.** `supportedLocale` answers *can this build DRAW it*;
// this answers *what does this picker put in front of THIS reader*. The
// Product Owner ruled the offer on 2026-09-07 — *"currently in drop down show
// only 2 elnglish and spanish"* — and ruled nothing about stored values, so
// the reading recorded in the decision log of that day is what these assert.

describe("offeredLocales — what THIS reader is shown", () => {
  it("offers the two, and only the two, to a reader already on one of them", () => {
    expect(offeredLocales(["en", "es"], "en")).toEqual(["en", "es"]);
    expect(offeredLocales(["en", "es"], "es")).toEqual(["en", "es"]);
  });

  it("adds the reader's OWN language when it is neither", () => {
    // ⚠ **THIS IS THE WHOLE OF `DEF-CWP-4442`.** A `<select>` whose value is
    // not among its options renders BLANK — no error, no warning, and every
    // `toContain` assertion still passes, because the failure is an absence.
    // A customer whose account says German must see German, named as German.
    expect(offeredLocales(["en", "es"], "de")).toEqual(["en", "es", "de"]);
    expect(offeredLocales(["en", "es"], "hi")).toEqual(["en", "es", "hi"]);
    // `es-MX` is Spanish and is still not one of the two: the ruling named
    // codes, not language families, and a reader on it keeps it until they
    // choose away.
    expect(offeredLocales(["en", "es"], "es-MX")).toEqual(["en", "es", "es-MX"]);
  });

  it("is ONE-WAY: the old language stops being offered once they leave it", () => {
    // The PO ruled the offer, not a migration. A customer keeps German until
    // they change it and cannot come back to it here, which is the whole cost
    // of the ruling stated in one assertion rather than left to be discovered.
    expect(offeredLocales(["en", "es"], "es")).not.toContain("de");
  });

  it("offers nothing extra when the reader has stated nothing", () => {
    // A login whose accounts disagree folds to `null` on the server, and a
    // guest has no stored value at all.
    expect(offeredLocales(["en", "es"], null)).toEqual(["en", "es"]);
    expect(offeredLocales(["en", "es"], undefined)).toEqual(["en", "es"]);
    expect(offeredLocales(["en", "es"], "")).toEqual(["en", "es"]);
  });

  it("keeps a stored code EXACTLY as stored rather than normalising it", () => {
    // ⚠ `en-US` is lawful on `accounts.preferred_language` (twelve
    // `SEED_LANGUAGES`, eleven catalogues) and the picker's value is the
    // STORED string. Offering the normalised `en` instead would leave the
    // control blank over `en-US` — the same defect one code along — and
    // saving from it would rewrite a value nobody asked us to touch.
    expect(offeredLocales(["en", "es"], "en-US")).toEqual(["en", "es", "en-US"]);
  });

  it("refuses a code this build cannot draw, because it could not honour it", () => {
    // Offering a language nothing renders is the failure B14 rule 35's whole
    // family is about — the picker would say Welsh and the page would be
    // English. `null` from `supportedLocale` is the one gate.
    expect(offeredLocales(["en", "es"], "cy")).toEqual(["en", "es"]);
    expect(offeredLocales(["en", "es"], "zz-ZZ")).toEqual(["en", "es"]);
  });

  it("never repeats a code, whatever order the offer arrives in", () => {
    expect(offeredLocales(["en", "es", "de"], "de")).toEqual(["en", "es", "de"]);
  });
});
