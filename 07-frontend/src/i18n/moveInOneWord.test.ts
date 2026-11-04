// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9747 — the move-in screens spoke two or three vocabularies
//          per language: Italian called the move-in *ingresso*, *trasloco* and
//          *subentro* on one flow, Hindi *प्रवेश*, *गृह-प्रवेश* (a housewarming)
//          and *मूव-इन*, Indonesian *penghunian masuk* beside *pindah masuk*;
//          the opening read had three names in Japanese, Korean, French and
//          Indonesian; co-owner, unit, work order and plan had two in several.
//          DEF-CUS-9745 — the Customer step said *Registered in* (a retired
//          word) where the Review step says *State of formation*.
// Rule:    B14 rule 35 — a catalogue is written in its own language, and a
//          clerk who speaks only that language uses ONE word for one thing.
//          CR-171-BRC10 P2.37 (lane MVI-I18N) — the words chosen are recorded
//          in the decision log; each is the module's own nav word where one
//          exists (Units, Work orders, Plans & Rates).
// ───────────────────────────────────────────────────────
//
// `G15` sees only a value byte-identical to English. A value written with the
// OTHER screen's word passes it, which is how three Italian words for one
// move-in reached three screens. This asks the question G15 cannot.
//
// ⚠ SCOPE, STATED (law 7): the move-in's own key families —
// `customers.moveIn.*`, `customers.moveDetail.*`, `customers.moveIns.*` — plus
// the doors that name the move-in from elsewhere (`DOORS`). Other flows (the
// move-out, the transfer, the service request's type list) are NOT read: each
// pairs its words with its own opposite (*Entrada/Saída*) and is another
// lane's to word. The test prints how many values it read, so an empty scope
// cannot pass silently.
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

const DOORS = new Set([
  "customers.account.action.moveIn",
  "customers.accounts.action.moveIn",
  "customers.accounts.tab.moveIns",
  "customers.waitingOn.flow.moveIn",
]);

const inScope = (key: string) => /^customers\.(moveIn|moveDetail|moveIns)\./.test(key) || DOORS.has(key);

/**
 * The words each catalogue no longer uses on the move-in screens, with the one
 * it uses instead in the comment. A hit names the key, so the fix is one line.
 */
const RETIRED: Record<string, { pattern: RegExp; instead: string }[]> = {
  "it-IT": [
    { pattern: /ingress|traslo|trasferi/i, instead: "subentro (the move-in)" },
    { pattern: /comproprietari/i, instead: "cointestatario" },
    { pattern: /(?<!\{\{)\baccount\b/i, instead: "conto" },
  ],
  hi: [
    { pattern: /प्रवेश/, instead: "मूव-इन" },
    { pattern: /यूनिट/, instead: "इकाई (the Units nav word)" },
    { pattern: /सह-स्वामी/, instead: "सह-मालिक" },
    { pattern: /कार्य आदेश/, instead: "वर्क ऑर्डर (the Work orders title)" },
  ],
  "id-ID": [
    { pattern: /penghunian|perpindahan|pemindahan/i, instead: "pindah masuk" },
    { pattern: /unit hunian/i, instead: "Unit (the Units nav word)" },
    { pattern: /\bbaca(an)? (awal|terakhir)|angka awal/i, instead: "pembacaan awal / pembacaan terakhir" },
    { pattern: /rekening/i, instead: "akun" },
  ],
  "pt-BR": [
    { pattern: /\bentradas?\b/i, instead: "mudança" },
    { pattern: /coproprietári/i, instead: "cotitular" },
  ],
  es: [{ pattern: /copropietari/i, instead: "cotitular" }],
  "es-MX": [{ pattern: /copropietari/i, instead: "cotitular" }],
  "fr-FR": [
    { pattern: /logement/i, instead: "unité (the Units nav word)" },
    { pattern: /copropriétaire/i, instead: "cotitulaire" },
    { pattern: /relevés? initia/i, instead: "relevé d’entrée" },
    { pattern: /(?<![’'])\boffre\b|\bformule\b|(?<!\{\{)\bplan\b/i, instead: "forfait (the Plans & Rates nav word; n’offre is the verb)" },
    { pattern: /(?<!d[’'])entrée\b/i, instead: "emménagement (an opening read stays relevé d’entrée)" },
  ],
  "ja-JP": [
    { pattern: /初回検針|開始検針|入居時の検針/, instead: "入居時検針" },
    { pattern: /物件|住戸/, instead: "ユニット (the Units nav word)" },
    { pattern: /共同所有者/, instead: "共同名義人" },
    { pattern: /引っ越/, instead: "入居" },
  ],
  "ko-KR": [
    { pattern: /초기 검침|개시 검침/, instead: "입주 검침" },
    { pattern: /유닛|호실/, instead: "세대 (the Units nav word)" },
    { pattern: /공동 소유자/, instead: "공동 명의자" },
    { pattern: /전입/, instead: "입주" },
  ],
  de: [{ pattern: /Mitinhaber/, instead: "Miteigentümer" }],
};

describe("DEF-CUS-9747 — one word per concept on the move-in screens, in every catalogue", () => {
  const keys = Object.keys(en as Catalogue).filter(inScope);

  it("reads a real scope (an empty one cannot pass)", () => {
    expect(keys.length).toBeGreaterThan(700);
  });

  for (const [locale, rules] of Object.entries(RETIRED)) {
    it(`${locale}: no move-in value uses a retired word`, () => {
      const catalogue = CATALOGUES[locale];
      const hits = keys.flatMap((key) =>
        rules
          .filter(({ pattern }) => pattern.test(catalogue[key] ?? ""))
          .map(({ instead }) => `${key} = ${catalogue[key]}  (use ${instead})`),
      );
      expect(hits).toEqual([]);
    });
  }
});

describe("DEF-CUS-9745 — the company's state has one name on the Customer and Review steps", () => {
  it("en: both steps say State of formation", () => {
    const catalogue = en as Catalogue;
    expect(catalogue["customers.moveIn.customer.registeredIn"]).toBe("State of formation");
    expect(catalogue["customers.moveIn.review.registeredIn"]).toBe("State of formation");
  });

  for (const [locale, catalogue] of Object.entries(CATALOGUES)) {
    it(`${locale}: the Customer step's word is the Review step's word`, () => {
      expect(catalogue["customers.moveIn.customer.registeredIn"]).toBe(catalogue["customers.moveIn.review.registeredIn"]);
    });
  }
});
