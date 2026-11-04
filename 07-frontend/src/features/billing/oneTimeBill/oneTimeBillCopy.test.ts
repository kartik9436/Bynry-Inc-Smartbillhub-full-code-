/**
 * The one-time bill's words, in all eleven catalogues.
 *
 * The server answers with catalogue KEYS (contract §2, §5) and the screen
 * renders them — so a key the backend lane starts sending that no catalogue
 * holds reaches a clerk as the raw key, which no other check here can see
 * until the backend is live. Contract §2 names every key it will send; they
 * are asserted here by name, in every language, and each refusal against B14
 * rule 33's six words per sentence.
 */
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

const CATALOGUES: Record<string, Record<string, string>> = {
  en,
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

/** Contract §2's refusal keys and §5's send refusals, verbatim.
 *  `approvalRequired` LEFT this list on 2026-09-30: the PO ruled a penalty's
 *  approval is recorded and never refuses Send, and the key was retired from
 *  all eleven catalogues. The four at the end are the API lane's own. */
const SERVER_REFUSALS = [
  "billing.oneTime.err.periodEndsBeforeStart",
  "billing.oneTime.err.periodRequired",
  "billing.oneTime.err.reasonRequired",
  "billing.oneTime.err.reasonUnknown",
  "billing.oneTime.err.chargeRequired",
  "billing.oneTime.err.billDateRequired",
  "billing.oneTime.err.dueDaysRequired",
  "billing.oneTime.err.dueDaysInvalid",
  "billing.oneTime.err.accountRequired",
  "billing.oneTime.err.notFirstBill",
  "billing.oneTime.err.moveInReadingRequired",
  // PO 2026-09-30 option B — five confirmations; `ackRequired` is retired.
  "billing.oneTime.err.confirmRequired",
  "billing.oneTime.err.notPriced",
  "billing.oneTime.err.settlementPathUnknown",
  "billing.oneTime.err.deliveryUnknown",
  "billing.oneTime.err.approverInvalid",
];

/** Contract §2's three warnings (`estimated` is plural, so it travels as two). */
const SERVER_WARNINGS = [
  "billing.oneTime.warn.baseNotSet",
  "billing.oneTime.warn.noAgreements",
  "billing.oneTime.warn.estimated_one",
  "billing.oneTime.warn.estimated_other",
];

describe("the one-time bill's catalogue", () => {
  it("holds every key the contract says the server will send, in all eleven languages", () => {
    for (const [lang, catalogue] of Object.entries(CATALOGUES)) {
      for (const key of [...SERVER_REFUSALS, ...SERVER_WARNINGS]) {
        expect(catalogue[key], `${lang} :: ${key}`).toBeTruthy();
      }
    }
  });

  it("holds the same one-time-bill keys in every language", () => {
    const english = Object.keys(en).filter((key) => key.startsWith("billing.oneTimeBill.")).sort();
    expect(english.length).toBeGreaterThan(200);
    for (const [lang, catalogue] of Object.entries(CATALOGUES)) {
      const keys = Object.keys(catalogue).filter((key) => key.startsWith("billing.oneTimeBill.")).sort();
      expect(keys, lang).toEqual(english);
    }
  });

  it("keeps every English refusal to six words a sentence (B14 rule 33)", () => {
    const english = en as Record<string, string>;
    for (const key of SERVER_REFUSALS) {
      for (const sentence of english[key].split(/[.!?]\s*/).filter(Boolean)) {
        expect(sentence.split(/\s+/).length, key).toBeLessThanOrEqual(6);
      }
    }
  });

  it("writes the review kicker without a doubled word — `First bill · draft`", () => {
    expect((en as Record<string, string>)["billing.oneTimeBill.bill.kicker"]).toBe("{{kind}} · draft");
  });
});
