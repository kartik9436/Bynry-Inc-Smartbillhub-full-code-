// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 — the bill detail, built to the Billing blueprint's §02
// Rules:    G15 (eleven catalogues hold one key set) · B14 rule 32 (no internal
//           code in clerk-facing copy) · CLAUDE.md hard-won law 2
// ───────────────────────────────────────────────────────
//
// ⚠ WHY THIS FILE EXISTS, AND IT IS NOT A HYPOTHETICAL
//
// Building this screen minted 52 keys and MISSED ONE. The Sent tab's second
// group label rendered as **`BILLING.BILL.PANEL.HOWTHEYHEAR`** — the raw key,
// uppercased by the accent-label style — on a live screen, and:
//
//   * `tsc` passed,
//   * every case in `BillDetailPage.test.tsx` passed,
//   * `BillChargesTab.test.tsx` and `CR053BillSurface.test.tsx` passed,
//   * the i18n parity gate passed, because parity is about the ELEVEN agreeing
//     with each other and they agreed perfectly about a key none of them had.
//
// It was found by opening the screen in a browser and reading it — which is the
// only check in this repository that reads rendered output, and it is a person.
// This file is the part of that a machine can keep doing.
//
// ⚠ **AND IT IS A TIER-2 CHECK, WHICH MEANS IT CANNOT TELL YOU THE SENTENCE IS
// RIGHT — only that it EXISTS.** A key present in eleven files with the wrong
// words in it passes here and always will. The walkthrough is still the check.
//
// **What would make this pass wrongly?** Two things, and both are closed below:
// a key built by template (`t(`prefix.${code}`)`) is invisible to the scan, so
// every such prefix on this screen is listed by hand and asserted to hold at
// least one key; and a scan that found NO keys at all would pass vacuously, so
// the count itself is asserted.
import { describe, expect, it } from "vitest";

// ⚠ **READ THROUGH VITE'S OWN `?raw` AND JSON IMPORTS, NOT THROUGH `node:fs`**
// — the precedent `DataTable.test.tsx` and `regionalReachesTheScreen.dom.test.
// tsx` both record: this app's `tsconfig` does not carry Node's type
// declarations, so a `node:fs` import is a red `tsc` over a green test.
import SOURCE from "./BillDetailPage.tsx?raw";
import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import es from "@/i18n/locales/es.json";
import esMX from "@/i18n/locales/es-MX.json";
import frFR from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import idID from "@/i18n/locales/id-ID.json";
import itIT from "@/i18n/locales/it-IT.json";
import jaJP from "@/i18n/locales/ja-JP.json";
import koKR from "@/i18n/locales/ko-KR.json";
import ptBR from "@/i18n/locales/pt-BR.json";

/** All eleven, NAMED — never globbed. A glob that silently found ten would
 *  leave one language unchecked and say nothing, which is the shape of the
 *  defect this file exists for. */
const CATALOGUES: Record<string, Record<string, string>> = {
  en, de, es, "es-MX": esMX, "fr-FR": frFR, hi,
  "id-ID": idID, "it-IT": itIT, "ja-JP": jaJP, "ko-KR": koKR, "pt-BR": ptBR,
};
const LANGS = Object.keys(CATALOGUES);

function catalogue(lang: string): Record<string, string> {
  return CATALOGUES[lang];
}

/** Every `t("literal")` on the screen. */
const literalKeys = [...(SOURCE as string).matchAll(/t\(\s*"([a-zA-Z0-9_.]+)"/g)].map((m) => m[1]);

/** Every key built from a CODE at runtime. Invisible to the scan above, so the
 *  prefixes are named here and each is asserted to hold values — which is what
 *  `DEF-BIL-5237` was: two prefixes with zero keys in eleven catalogues, and a
 *  `defaultValue` fallback printing `pdf_print` at a clerk instead. */
const TEMPLATE_PREFIXES = [
  "billing.bill.tab",
  "billing.bill.kind",
  "billing.bill.direction",
  "billing.bill.channel",
  "billing.bill.delivery",
  "billing.fix.reason",
  "rating.service",
];

describe("CR-101-BRC03 — every word the bill detail asks for exists, in all eleven languages", () => {
  it("the scan found the screen's keys at all (a vacuous pass is a pass)", () => {
    expect(literalKeys.length).toBeGreaterThan(150);
  });

  for (const lang of LANGS) {
    it(`${lang} holds every key the screen asks for by name`, () => {
      const words = catalogue(lang);
      const missing = [...new Set(literalKeys)].filter((key) => !(key in words)).sort();
      expect(missing).toEqual([]);
    });
  }

  for (const prefix of TEMPLATE_PREFIXES) {
    it(`${prefix}.* is not an empty namespace in any language`, () => {
      const empty = LANGS.filter(
        (lang) => !Object.keys(catalogue(lang)).some((key) => key.startsWith(`${prefix}.`)),
      );
      expect(empty).toEqual([]);
    });
  }
});
