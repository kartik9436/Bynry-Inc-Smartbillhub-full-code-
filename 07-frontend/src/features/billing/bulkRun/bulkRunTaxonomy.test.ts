// ── Trace ──────────────────────────────────────────────
// Plan:    15-bulk-bill-run-build-plan.md T4 (the grouping under the Check list)
// Story:   US-BIL-037 TC-1 (every problem on an account, each in its tag),
//          TC-12 (every code a clerk label — never a raw code)
// Defects: DEF-BIL-8216 (closed — the Check reads the server's grouping; this
//          table now names only Failed-to-draft breaks, and `groupFindings`
//          and its tests are deleted with it)
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";
import ja from "@/i18n/locales/ja-JP.json";

import { CATEGORIES, TAGS } from "./bulkRunTaxonomy";

const catalogues: Record<string, Record<string, string>> = { en, ja };

describe("the interim Check taxonomy", () => {
  it("draws the nine categories in the drawn order", () => {
    expect(CATEGORIES).toEqual(["payments", "readings", "meterHistory", "plans", "accounts", "master", "assets", "period", "setup"]);
  });

  it("gives every tag and category a clerk name and meaning in the catalogues (TC-12)", () => {
    for (const catalogue of Object.values(catalogues)) {
      for (const tag of TAGS) {
        expect(catalogue[`billing.bulkRun.tag.${tag.id}.name`], tag.id).toBeTruthy();
        expect(catalogue[`billing.bulkRun.tag.${tag.id}.meaning`], tag.id).toBeTruthy();
      }
      for (const category of CATEGORIES) {
        expect(catalogue[`billing.bulkRun.category.${category}`], category).toBeTruthy();
      }
    }
  });

  it("maps no engine code twice", () => {
    const codes = TAGS.flatMap((tag) => tag.codes);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it("carries the seven former auto cases as their own decision tags (changes rows 44–46)", () => {
    const decisions = new Set(TAGS.filter((tag) => tag.severity === "decision").map((tag) => tag.id));
    for (const id of ["readingNoUnit", "possibleRollover", "meterSwapped", "planNotPublished", "noPriceForService", "noChargeForType", "priceChangedMidPeriod"]) {
      expect(decisions.has(id), id).toBe(true);
    }
    // Stays blocked: no unit, master coverage, no size, pricing refused.
    for (const id of ["noUnit", "coverageUnknown", "noSize", "pricingRefused"]) {
      expect(TAGS.find((tag) => tag.id === id)?.severity, id).toBe("blocks");
    }
  });
});
