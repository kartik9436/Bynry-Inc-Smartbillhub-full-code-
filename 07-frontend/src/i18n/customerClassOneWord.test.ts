// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9662 — the account category *Commercial* read *광고*
//          ("advertisement") in Korean and *コマーシャル* (a TV commercial) in
//          Japanese, and the same customer class was written two or three ways
//          inside one catalogue (Rating's list said one word, the account's
//          category another, and Rating's own picker printed English in five).
//          DEF-MET-9663 — the same misreading in a unit type and the Settings
//          sample: Korean *석사* (a master's DEGREE) for a master meter.
// Rule:    B14 rule 35 — a catalogue is written in its own language; CR-168-BRC10
//          §25 (lane I18N) — one term per concept within a catalogue.
// ───────────────────────────────────────────────────────
//
// `G15` only sees a value byte-identical to English. A value translated into
// the WRONG word passes it, and so does a class written three ways — which is
// how *광고* reached the account screen. This asks the question G15 cannot:
// does each catalogue call each customer class by ONE word everywhere it is
// shown?
//
// ⚠ SCOPE, STATED (law 7): the four classes every list carries — residential,
// commercial, industrial, government — on the four lists that name a customer
// class: Rating's customer-class picker (`rating.customerClass.*`), the tax
// wizard's classes (`rating.taxWiz.classes.*`, the reference), the account
// category (`customers.accounts.category.*`). A unit's TYPE
// (`metering.units.type.*`) is a dwelling, not a customer — German *Wohnen*
// is right there and *Privatkunden* would not be — so it is checked only for
// the wrong-sense words in `MISREAD`, which are looked for in EVERY value whose
// English carries the word (`DEF-MET-9663`: a key-shaped check missed a
// compound key and a sample sentence). The notification audience words
// (`notifications.rules.planClass.*`) and template audiences are NOT checked:
// they name who a message is FOR (*Hogares*, *Particuliers*), a different
// concept that a catalogue may word for the reader.
import { describe, expect, it } from "vitest";

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

type Catalogue = Record<string, string>;

const CATALOGUES: Record<string, Catalogue> = {
  de,
  es,
  "es-MX": esMX,
  "fr-FR": frFR,
  hi,
  "id-ID": idID,
  "it-IT": itIT,
  "ja-JP": jaJP,
  "ko-KR": koKR,
  "pt-BR": ptBR,
};

const CLASSES = ["residential", "commercial", "industrial", "government"] as const;
const REFERENCE = "rating.taxWiz.classes.";
const MUST_MATCH = ["rating.customerClass.", "customers.accounts.category."];
/** Words a machine pass chose for the wrong SENSE of an English word: an
 *  ADVERTISEMENT for "commercial", a MASTER'S DEGREE for "master" (meter). Each
 *  is looked for in every value whose English carries that word. */
const MISREAD: Record<string, Array<[RegExp, string[]]>> = {
  "ko-KR": [
    [/commercial/i, ["광고"]],
    [/master/i, ["석사"]],
  ],
  "ja-JP": [[/commercial/i, ["コマーシャル"]]],
};

describe("each catalogue calls a customer class by one word (DEF-CUS-9662)", () => {
  it("every list this test reads exists in English", () => {
    for (const cls of CLASSES) {
      for (const prefix of [REFERENCE, ...MUST_MATCH]) {
        expect((en as Catalogue)[prefix + cls], prefix + cls).toBeTruthy();
      }
    }
  });

  for (const [lang, cat] of Object.entries(CATALOGUES)) {
    it(`${lang}: the picker and the account category use the tax wizard's word`, () => {
      const off: string[] = [];
      for (const cls of CLASSES) {
        const word = cat[REFERENCE + cls];
        for (const prefix of MUST_MATCH) {
          if (cat[prefix + cls] !== word) off.push(`${prefix}${cls} = ${cat[prefix + cls]} (want ${word})`);
        }
      }
      expect(off).toEqual([]);
    });

    it(`${lang}: no value says "advertisement" for commercial, or "master's degree" for a master meter`, () => {
      const off: string[] = [];
      for (const [english, words] of MISREAD[lang] ?? []) {
        for (const [key, value] of Object.entries(cat)) {
          const source = (en as Catalogue)[key] ?? "";
          if (english.test(source) && words.some((word) => value.includes(word))) off.push(`${key} = ${value}`);
        }
      }
      expect(off).toEqual([]);
    });
  }
});
