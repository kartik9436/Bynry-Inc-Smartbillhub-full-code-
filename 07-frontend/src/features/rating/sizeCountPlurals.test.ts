// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2355 — the charge code review step printed *"1 connection sizes
//          listed, 0 priced"* (Product Owner, walking Plans & Rates on the
//          deployed build, 2026-09-03). Two sibling screens said the same.
// Screens: S12 / CHG-02 (charge code wizard, step 3) · S11 (plan definition
//          detail) · S9 / RAT-03 (rate schedule wizard, review)
// Rules:   B14 rule 32 (clerk-facing copy) · BR-SHL-030 (a user-visible string
//          is a key; sentences are never concatenated)
// Note:    Proved RED against the single-form keys — the failure is quoted
//          below (hard-won law 7).
// ───────────────────────────────────────────────────────
/**
 * **ONE DEFECT ON THREE SCREENS, SO ONE FILE.**
 *
 * All three sentences count connection sizes, all three were written as a
 * single string with `{{count}}` in it, and a key with no `_one` / `_other`
 * suffix is a key i18next never pluralises — it resolves, it renders, and it
 * says *"1 connection sizes"*. That is why `G15`, `G18` and `G27` all pass on
 * it: every one of them asks whether a key EXISTS, and none asks whether it
 * agrees with its own `count` argument.
 *
 * ⚠ **THE REASON NOBODY SAW IT IS WORTH MORE THAN THE FIX.** Every fixture in
 * these suites prices SEVERAL sizes, because that is what a real water utility
 * looks like — so the many case is the only one anything ever rendered. Fire is
 * what made it visible: a utility can genuinely price one connection size, and
 * `CR-063` put one on a screen the Product Owner then opened.
 *
 * **WHY THIS ASSERTS THROUGH `i18n.t` AND NOT THROUGH RENDERED MARKUP.** The
 * three call sites already pass `{ count }`; nothing in the components changed
 * and nothing needed to. The defect was entirely in the catalogue, and this is
 * the exact resolution path the screens take — `ReviewStep` calls
 * `t("rating.chargeWizard.perSize.reviewCount", { count, served })` with these
 * arguments, so a case that calls it the same way fails when the screen would.
 */
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import en from "@/i18n/locales/en.json";

const CATALOGUE = en as Record<string, string>;

/** The three sentences that count connection sizes, and their screens. */
const COUNTING_KEYS = [
  "rating.chargeWizard.perSize.reviewCount",
  "rating.definition.charge.perSizeCount",
  "rating.rate.review.sizeRows",
] as const;

describe("DEF-2355 · a size count reads correctly at one and at many", () => {
  /**
   * ⚠ **PROVED RED FIRST.** Against the single-form keys this case failed with:
   *
   *     AssertionError: expected '1 connection sizes listed, 0 priced' to be
   *     '1 connection size listed, 0 priced' // Object.is equality
   *
   * — which is the Product Owner's sentence, character for character. All five
   * cases in this file fail against the single-form keys; the red was produced
   * by putting the three old keys back through `10-scripts/i18n_fanin.py` and
   * retiring the six new ones, then reversing it.
   */
  it("the charge code review step says SIZE at one and SIZES at more", () => {
    expect(i18n.t("rating.chargeWizard.perSize.reviewCount", { count: 1, served: 0 })).toBe(
      "1 connection size listed, 0 priced",
    );
    expect(i18n.t("rating.chargeWizard.perSize.reviewCount", { count: 6, served: 6 })).toBe(
      "6 connection sizes listed, 6 priced",
    );
  });

  it("the plan definition's charge panel says the same thing the same way", () => {
    expect(i18n.t("rating.definition.charge.perSizeCount", { count: 1, served: 1 })).toBe(
      "1 connection size listed, 1 priced",
    );
    expect(i18n.t("rating.definition.charge.perSizeCount", { count: 6, served: 2 })).toBe(
      "6 connection sizes listed, 2 priced",
    );
  });

  it("the rate schedule review step does too", () => {
    expect(i18n.t("rating.rate.review.sizeRows", { count: 1 })).toBe(
      "1 connection size priced separately",
    );
    expect(i18n.t("rating.rate.review.sizeRows", { count: 6 })).toBe(
      "6 connection sizes priced separately",
    );
  });

  /**
   * ⚠ **THE BARE KEYS ARE RETIRED, AND THIS CASE IS WHY IT MATTERED.** A
   * catalogue entry BEATS a code `defaultValue`, and i18next falls back to the
   * suffix-less key. Leaving the old singles in place would have let the
   * ungrammatical sentence keep winning while all six new keys sat unused and
   * every assertion above still passed — a fix that is present and inert,
   * which is this repo's most-repeated failure shape (hard-won law 2).
   */
  it("the single-form keys are GONE, so nothing can resolve to the old sentence", () => {
    for (const key of COUNTING_KEYS) {
      expect(CATALOGUE[key]).toBeUndefined();
      expect(CATALOGUE[`${key}_one`]).toBeTruthy();
      expect(CATALOGUE[`${key}_other`]).toBeTruthy();
    }
  });

  /**
   * The many form is the sentence that was already on screen, unchanged. This
   * defect is a MISSING SINGULAR, and re-wording the plural at the same time
   * would hide that inside a translation diff across eleven catalogues.
   */
  it("the many form is byte-identical to the sentence that shipped", () => {
    expect(CATALOGUE["rating.chargeWizard.perSize.reviewCount_other"]).toBe(
      "{{count}} connection sizes listed, {{served}} priced",
    );
    expect(CATALOGUE["rating.definition.charge.perSizeCount_other"]).toBe(
      "{{count}} connection sizes listed, {{served}} priced",
    );
    expect(CATALOGUE["rating.rate.review.sizeRows_other"]).toBe(
      "{{count}} connection sizes priced separately",
    );
  });
});
