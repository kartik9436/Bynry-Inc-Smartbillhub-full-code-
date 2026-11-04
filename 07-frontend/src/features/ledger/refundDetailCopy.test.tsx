// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect: `DEF-LED-6624` — the refund detail head read *"NO CHEQUE WRITTEN
//         YET"* over a chip that read *"Check"*, on the screen a clerk opens
//         from a queue whose own words are *"Check not written yet"*. One
//         feature, two spellings, and the picture went to the PO.
// Rules:  the catalogue sweep's rule — this product writes US English.
// Screen: S58.detail (`RefundDetailPage.tsx`)
// Tests:  this file. It reads `en.json` itself.
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ **WHY THIS ASKS ABOUT A PREFIX AND NOT ABOUT TWO KEYS.**
 *
 * The check that should have caught `DEF-LED-6624` exists — it is in
 * `features/payments/refundCorrectCheck.dom.test.tsx` and it walks a
 * HAND-WRITTEN LIST of seven `payments.refunds.correct.*` keys. A list is only
 * ever right about the day it was written: two new keys landed in a different
 * namespace and the sweep could not see them, truthfully reporting nothing
 * wrong over a scope it silently excluded (CLAUDE.md hard-won law 7, fifth
 * shape).
 *
 * So this one takes **every English string the refund screen can render** — the
 * whole `finance.refundDetail.` prefix, whatever it holds next month — and the
 * next key is covered on the day it is added rather than on the day somebody
 * remembers to extend an array.
 *
 * ⚠ **ONLY `en` IS ASKED.** `Cheque` is the ordinary Spanish and Portuguese
 * noun and `Chèque` the French one; G15 already allow-lists them by name. A
 * check that swept all eleven would be asking ten catalogues to stop speaking
 * their own language.
 */
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

afterEach(cleanup);

const PREFIX = "finance.refundDetail.";

function refundDetailStrings(): [string, string][] {
  return Object.entries(en as Record<string, string>).filter(([key]) => key.startsWith(PREFIX));
}

describe("DEF-LED-6624 · the refund screen's own words are US English", () => {
  it("has strings to check at all — an empty sweep is not a passing one", () => {
    // Without this, renaming the prefix turns every case below into a loop over
    // nothing, which reports green forever.
    expect(refundDetailStrings().length).toBeGreaterThan(10);
  });

  it("never writes *cheque*, in any casing, on any key the screen renders", () => {
    const offenders = refundDetailStrings().filter(([, text]) => /cheque/i.test(text));
    expect(offenders).toEqual([]);
  });

  it("says *check* on the two keys the head is built from", () => {
    const map = Object.fromEntries(refundDetailStrings());
    expect(map[`${PREFIX}noReference`]).toBe("No check written yet");
    expect(map[`${PREFIX}reference`]).toBe("Check {{reference}}");
  });
});
