// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-002 (S17) · US-PAY-004 (S33) · US-BIL-025/026 (S30)
// Change:   CR-089 wave K — PUJ-51/52/53, an address finds the accounts, the
//           payments and the bills at it
// Rules:    B14 rule 19 (a list's prompt names what THIS list searches) ·
//           B14 rule 35 (a catalogue is written in its own language, never
//           translated from English) · BR-SHL-030 (a language is DATA) ·
//           hard-won law 1 (a comment claiming a guarantee is not the
//           guarantee — and a placeholder is a PROMISE about the search)
// ───────────────────────────────────────────────────────
// THE PROMPT AND THE PREDICATE MUST AGREE, IN ELEVEN LANGUAGES.
//
// Wave K taught three server searches to walk *row → account → property*. The
// screen half of that is one word in a prompt, and it is the half a clerk
// actually sees: nobody types a street into a box that does not offer to search
// one. The reverse is the failure hard-won law 1 is about — a prompt naming a
// leg the server does not perform, which `AccountsListPage`'s own header
// records being withheld for a fortnight on exactly that principle
// (*"Do not ship the placeholder before the column"*).
//
// So this file pins the promise, per language, for all three lists. It goes RED
// if somebody rewords a prompt back, and it goes red in the language they broke
// rather than in English.
//
// ⚠ IT DOES NOT ASSERT THE SERVER. The predicate is asserted where it lives —
// `06-backend/tests/test_cr089_wave_k_address_search.py` — and a screen test
// that claimed to prove a search would be the very thing this file exists to
// forbid.
import { describe, expect, it } from "vitest";

import { BILLS_SEARCH_PLACEHOLDER_KEY } from "@/features/billing/BillsListPage";

import de from "./locales/de.json";
import en from "./locales/en.json";
import es from "./locales/es.json";
import esMX from "./locales/es-MX.json";
import frFR from "./locales/fr-FR.json";
import hi from "./locales/hi.json";
import idID from "./locales/id-ID.json";
import itIT from "./locales/it-IT.json";
import jaJP from "./locales/ja-JP.json";
import koKR from "./locales/ko-KR.json";
import ptBR from "./locales/pt-BR.json";

/** The eleven, each with the word IT uses for an address — not a translation of
 * "address", the word already standing in that catalogue's own copy for the
 * units list and the move-out worklist. */
const CATALOGUES: ReadonlyArray<[string, Record<string, string>, string]> = [
  ["en", en as Record<string, string>, "address"],
  ["de", de as Record<string, string>, "Adresse"],
  ["es", es as Record<string, string>, "dirección"],
  ["es-MX", esMX as Record<string, string>, "dirección"],
  ["fr-FR", frFR as Record<string, string>, "adresse"],
  ["hi", hi as Record<string, string>, "पता"],
  ["id-ID", idID as Record<string, string>, "alamat"],
  ["it-IT", itIT as Record<string, string>, "indirizzo"],
  ["ja-JP", jaJP as Record<string, string>, "住所"],
  ["ko-KR", koKR as Record<string, string>, "주소"],
  ["pt-BR", ptBR as Record<string, string>, "endereço"],
];

/** The three prompts wave K makes a promise in. The bills key is IMPORTED from
 * the screen rather than retyped, so a rename moves this test with it. */
const PROMPTS = [
  ["accounts (S17)", "customers.accounts.searchPlaceholder"],
  ["payments (S33)", "payments.list.searchPlaceholder"],
  ["bills (S30)", BILLS_SEARCH_PLACEHOLDER_KEY],
] as const;

describe("CR-089 wave K — the three prompts offer to search an address", () => {
  for (const [screen, key] of PROMPTS) {
    for (const [lang, catalogue, word] of CATALOGUES) {
      it(`${screen} names the address in ${lang}`, () => {
        const prompt = catalogue[key];
        expect(prompt, `${key} missing from ${lang}.json`).toBeTruthy();
        expect(prompt.toLowerCase()).toContain(word.toLowerCase());
      });
    }
  }

  it("adds no key — the three prompts were reworded, not invented", () => {
    // G18 counts locale keys nothing calls. Wave K changed three VALUES and
    // created nothing, so every key here has a call site above it in this file.
    for (const [, key] of PROMPTS) {
      expect(Object.keys(en as Record<string, string>)).toContain(key);
    }
  });
});
