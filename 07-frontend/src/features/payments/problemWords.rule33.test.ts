// ── Trace ──────────────────────────────────────────────
// Defects: DEF-PAY-6327 (29 of 40 `payments.problem.*` strings over B14 rule 33's cap)
//          DEF-PAY-6328 (a raw dotted key rendered at a clerk)
//          DEF-PAY-6330 (two refusals whose stated reason had stopped being true)
// Rules:   B14 rule 33 (on-screen text is capped by what it is FOR; rationale is zero words)
//          B14 rule 32 (no internal code in clerk-facing copy)
//          B14 rule 35 (a catalogue is written in its own language, not translated from English)
// Screens: S32 Payments Summary · S34 Outstandings/Collections · the debtor page ·
//          the bad-debt report · the move and reapply plans — every caller of `ProblemList`
// ───────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS, AND WHY IT IS THREE CHECKS RATHER THAN ONE
// ================================================================
// The Product Owner read the "What is missing" panel on 2026-09-23 and asked why
// we were showing it, quoting two of its bullets back at us. Measured that hour:
// the family is 40 keys and **29 carried at least one sentence over rule 33's
// six-word cap**, the longest at 30 words. Rule 33 is RATIFIED and, for its five
// kinds, UNENFORCED — B14's own status column says so — so no gate in this repo
// has ever counted a word in this family. This is that gate, for one family.
//
// **A word count alone would have been the wrong instrument, twice over**, and
// each of the other two checks here exists because the sweep found a fault a
// word count is structurally unable to see:
//
//   2. A DEAD KEY WITH A FALSE SENTENCE (`DEF-PAY-6330`). `no_receipt_queued`
//      told a clerk that sending receipts "is not built" for five weeks after
//      `receipts.queue_receipt_for_recorded_payment` started running on every
//      payment; `grouped_bank_credits_not_matchable` told them deposits "will
//      stay unmatched" on the same page as the control that matches them. Both
//      were SHORT. Both passed every parity check, because the key was present
//      in all eleven catalogues. The only tests that touched them asserted the
//      sentence renders — off a FIXTURE that invents the code, so they pass
//      forever after the server stops sending it. So the second check below
//      asserts the deletions STAY deleted, by name.
//
//   3. A RAW DOTTED KEY AT A CLERK (`DEF-PAY-6328`). `i18n` is configured
//      `keySeparator: false`, so a missing key returns the key: a clerk reads
//      the literal text `payments.problem.receipt_queued`. Three of the five
//      render sites of this family passed no fallback. A word count cannot see
//      this either — there is no string to count. So the third check reads what
//      `ProblemList` actually RENDERS and refuses a dotted key in it.
//
// HOW THE CAP IS MEASURED IN ELEVEN LANGUAGES — B14 RULE 35
// =========================================================
// **A six-word English cap is not a six-word cap in Japanese.** Rule 35 says a
// catalogue is written in its own language rather than translated from English,
// and a whitespace word count is meaningless in a script that does not put
// spaces between words. Counting English words and calling it a rule would
// enforce translationese: the way to pass would be to write English with the
// words swapped, which is precisely what rule 35 forbids.
//
// So the cap is expressed per script, in the unit that language actually
// counts, and each budget is the six-word English cap carried across rather
// than relaxed. The numbers are MEASURED against what the eleven catalogues do
// today (the medians below), not guessed:
//
//   | script                                  | unit            | budget | median today |
//   |-----------------------------------------|-----------------|--------|--------------|
//   | en de es es-MX fr-FR id-ID it-IT pt-BR  | whitespace word |   6    | 13 – 16      |
//   | hi (Devanagari, space-delimited)        | whitespace word |   8    | 15           |
//   | ko-KR (spaced 어절)                      | 어절            |   6    | 9            |
//   | ja-JP (unspaced)                        | character       |  20    | 30           |
//
// Hindi gets eight because its postpositions and compound verbs are separate
// tokens — "में", "नहीं है" — so the same fact costs more tokens than in English
// and a six-token Hindi line would have to drop a postposition to fit, which is
// not shorter, it is wrong. Korean 어절 carry their particles attached, which is
// why Korean is already the tersest catalogue and six is a real tightening
// rather than a formality. Japanese is counted in characters because it has no
// word boundary to count; twenty characters is about what a six-word English
// fact becomes in natural Japanese.
//
// ⚠ **PROVED RED BEFORE A WORD WAS CHANGED**, in the harness that runs it
// (`npx vitest run`, not by hand — hard-won law 7's second half). On the
// catalogues as they stood on 2026-09-23 this file reported 29 English keys over
// the cap and the same shape in all eleven, worst case 30 words (en), 49
// characters (ja-JP), 18 어절 (ko-KR).
import { describe, expect, it } from "vitest";

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

import { PROBLEM_KEY_PREFIX, PROBLEM_CODES_DELETED_ON_PURPOSE } from "./paymentsShared";

type Catalogue = Record<string, string>;

/** All eleven, in `LOCALE_CODES` order. */
const CATALOGUES: ReadonlyArray<readonly [string, Catalogue]> = [
  ["en", en as Catalogue],
  ["es", es as Catalogue],
  ["es-MX", esMX as Catalogue],
  ["de", de as Catalogue],
  ["hi", hi as Catalogue],
  ["fr-FR", frFR as Catalogue],
  ["id-ID", idID as Catalogue],
  ["it-IT", itIT as Catalogue],
  ["ja-JP", jaJP as Catalogue],
  ["ko-KR", koKR as Catalogue],
  ["pt-BR", ptBR as Catalogue],
];

/**
 * The budget table above, as code. `unit` is what a failure message prints, so
 * a reader who has never seen this file can tell what went wrong without
 * reading it — hard-won law 7's third habit.
 */
const BUDGET: Record<string, { readonly cap: number; readonly unit: string }> = {
  en: { cap: 6, unit: "words" },
  es: { cap: 6, unit: "words" },
  "es-MX": { cap: 6, unit: "words" },
  de: { cap: 6, unit: "words" },
  hi: { cap: 8, unit: "words" },
  "fr-FR": { cap: 6, unit: "words" },
  "id-ID": { cap: 6, unit: "words" },
  "it-IT": { cap: 6, unit: "words" },
  "ja-JP": { cap: 20, unit: "characters" },
  "ko-KR": { cap: 6, unit: "어절" },
  "pt-BR": { cap: 6, unit: "words" },
};

/** The 3-word LABEL cap — a heading is a name and never a sentence. */
const LABEL_CAP = 3;

/**
 * Sentence ends in every script this product ships. `।` is the Devanagari
 * danda and `。！？` are the CJK full-width stops; a splitter that knew only
 * `.` would read a whole Hindi or Japanese string as one sentence and measure
 * the wrong thing — which is a check looking at the wrong thing, and it would
 * have passed wrongly rather than failed.
 */
const SENTENCE_END = /(?<=[.!?。！？।])\s*/;

function sentencesOf(value: string): string[] {
  return value
    .split(SENTENCE_END)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

/** Japanese is measured in characters; punctuation is not content. */
function lengthOf(sentence: string, locale: string): number {
  if (locale === "ja-JP") {
    return sentence.replace(/[\s。、！？「」『』・]/gu, "").length;
  }
  return sentence.split(/\s+/u).filter((token) => token.length > 0).length;
}

function familyOf(catalogue: Catalogue): Record<string, string> {
  return Object.fromEntries(
    Object.entries(catalogue).filter(([key]) => key.startsWith(PROBLEM_KEY_PREFIX)),
  );
}

describe("DEF-PAY-6327 — B14 rule 33: every `payments.problem.*` string is inside its cap, in all eleven catalogues", () => {
  it.each(CATALOGUES)(
    "%s: no sentence in the family exceeds the budget for its script",
    (locale, catalogue) => {
      const { cap, unit } = BUDGET[locale];
      const over: string[] = [];
      for (const [key, value] of Object.entries(familyOf(catalogue))) {
        for (const sentence of sentencesOf(value)) {
          const measured = lengthOf(sentence, locale);
          if (measured > cap) {
            over.push(`${key} — ${measured} ${unit} (cap ${cap}): "${sentence}"`);
          }
        }
      }
      // The message carries the count AND the offenders, because a reader of a
      // red suite needs to know whether this is one string or twenty-nine.
      expect(over, `${locale}: ${over.length} sentence(s) over rule 33's cap\n${over.join("\n")}`).toEqual([]);
    },
  );

  it.each(CATALOGUES)("%s: the panel heading is a label, not a sentence", (locale, catalogue) => {
    const heading = catalogue["payments.problems.title"];
    expect(heading, `${locale} has no heading for the problems panel`).toBeTruthy();
    expect(heading).not.toMatch(/[.!?。！？।]/u);
    const measured = lengthOf(heading, locale);
    const cap = locale === "ja-JP" ? 10 : LABEL_CAP;
    expect(
      measured,
      `${locale}: heading "${heading}" is ${measured}, over the ${cap} label cap`,
    ).toBeLessThanOrEqual(cap);
  });

  it("no string in the family carries an internal reference (B14 rule 32)", () => {
    // Rule 31/32 in this family's own terms: a `BR-`, `DEF-`, `OQ-`, `US-` or a
    // dotted key must never be the thing a clerk reads.
    const internal = /\b(?:BR|DEF|OQ|US|EP|GT|CR)-[A-Z]*-?\d|payments\.problem\./u;
    for (const [locale, catalogue] of CATALOGUES) {
      for (const [key, value] of Object.entries(familyOf(catalogue))) {
        expect(value, `${locale} ${key} carries an internal reference`).not.toMatch(internal);
      }
    }
  });
});

describe("DEF-PAY-6330 — a retired code does not leave a false sentence behind", () => {
  it("the codes deleted on purpose are absent from all eleven catalogues", () => {
    // ⚠ THIS IS THE CHECK A WORD COUNT CANNOT MAKE, and it is the one that would
    // have caught the actual harm. Both deleted sentences were SHORT and both
    // were FALSE. Asserting them absent BY NAME is what stops a later lane
    // restoring one because a fixture still mentions it.
    for (const [locale, catalogue] of CATALOGUES) {
      for (const code of PROBLEM_CODES_DELETED_ON_PURPOSE) {
        expect(
          catalogue[`${PROBLEM_KEY_PREFIX}${code}`],
          `${locale} still carries ${PROBLEM_KEY_PREFIX}${code}, deleted on purpose`,
        ).toBeUndefined();
      }
    }
  });

  it("the eleven catalogues hold exactly the same keys in this family", () => {
    // Parity is the one thing that WAS green through all of this, and it stays
    // asserted here so a shortening that reaches ten catalogues and not the
    // eleventh goes red in this file rather than in a gate somebody runs later.
    const english = Object.keys(familyOf(en as Catalogue)).sort();
    expect(english.length).toBeGreaterThan(0);
    for (const [locale, catalogue] of CATALOGUES) {
      expect(Object.keys(familyOf(catalogue)).sort(), `${locale} is out of parity`).toEqual(english);
    }
  });
});
