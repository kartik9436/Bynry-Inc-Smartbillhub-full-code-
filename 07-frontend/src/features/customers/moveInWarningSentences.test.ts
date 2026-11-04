// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9749 — Move-in completed printed the raw server code
//          `deposit_payment_has_not_cleared` under *What the server could not
//          do*: `warningText` falls back to the code when no catalogue key
//          exists, and the key is built at runtime, so no gate saw it missing.
// ───────────────────────────────────────────────────────
//
// Every warning code the move-in's money path can raise (`move_fees.py`,
// `deposit.py`) must have a sentence in all eleven catalogues, so the
// `defaultValue` fallback never reaches a clerk. The list is the server's;
// a code added there without a sentence here is the defect again.
import { describe, expect, it } from "vitest";

import de from "../../i18n/locales/de.json";
import en from "../../i18n/locales/en.json";
import esMX from "../../i18n/locales/es-MX.json";
import es from "../../i18n/locales/es.json";
import frFR from "../../i18n/locales/fr-FR.json";
import hi from "../../i18n/locales/hi.json";
import idID from "../../i18n/locales/id-ID.json";
import itIT from "../../i18n/locales/it-IT.json";
import jaJP from "../../i18n/locales/ja-JP.json";
import koKR from "../../i18n/locales/ko-KR.json";
import ptBR from "../../i18n/locales/pt-BR.json";

const CATALOGUES: Record<string, Record<string, string>> = {
  en, de, es, "es-MX": esMX, "fr-FR": frFR, hi, "id-ID": idID, "it-IT": itIT,
  "ja-JP": jaJP, "ko-KR": koKR, "pt-BR": ptBR,
};

/** `move_fees.PAYMENTS_UNWIRED`, `deposit.PAYMENTS_UNWIRED` and
 * `deposit_register_not_moved` — the codes `warnings.append` writes.
 * `deposit_payment_has_not_cleared` is RETIRED (DEF-CUS-10324, CR-186-BRC10):
 * a deposit is posted and held at entry, so nothing raises it any more. */
const MOVE_IN_WARNING_CODES = [
  "deposit_payment_path_unwired",
  "move_in_payment_path_unwired",
  "deposit_register_not_moved",
];

describe("DEF-CUS-9749 — every move-in warning code has a sentence", () => {
  for (const code of MOVE_IN_WARNING_CODES) {
    it(code, () => {
      const key = `customers.account.warning.${code}`;
      const missing = Object.entries(CATALOGUES)
        .filter(([, catalogue]) => !(catalogue[key] ?? "").trim() || catalogue[key] === code)
        .map(([lang]) => lang);
      expect(missing).toEqual([]);
    });
  }
});
