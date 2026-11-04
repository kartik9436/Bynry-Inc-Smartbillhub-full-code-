// ── Trace ──────────────────────────────────────────────
// Story:    CR-060 **C11**, task **T12** — the vocabulary sweep
// Rules:    B14 rule 34 (ONE pair of words for *held here* and *in the books*)
// ───────────────────────────────────────────────────────
/**
 * **B14 RULE 34, ASSERTED OVER THE CATALOGUE ITSELF.**
 *
 * C11's finding, verbatim: *"The product has SIX different phrasings for 'held
 * here but not in the books' — posts nowhere · moves no books ·
 * register-derived · kept apart from the totals · nothing reached the books.
 * Pick one pair and use it everywhere."* The pair is `CR-060` §8b's own —
 * **Recorded** and **In the books**.
 *
 * ⚠ **THIS IS THE ONLY THING IN THE REPO THAT CAN FAIL ON THIS RULE, AND ITS
 * REACH IS SMALL — SAY SO RATHER THAN IMPLY MORE (hard-won law 1).** It reads
 * the ENGLISH catalogue for the five retired phrasings and nothing else. It
 * cannot tell whether a sentence is TRUE — `DEF-2365` was a sentence that had
 * gone false while every gate passed on it — and it cannot see a new phrasing
 * nobody has thought of yet. What it does catch is the exact regression this
 * sweep was done to prevent: a sixth spelling coming back.
 *
 * ⚠ **PROVED RED FIRST (law 7).** Run against the catalogue before the sweep,
 * it failed on four of the five phrasings, naming each key — verbatim:
 *
 *     AssertionError: expected [ 'assets.maintenance.costHelp' ] to deeply
 *     equal []
 *     AssertionError: expected [ 'finance.cost.postsNothing' ] to deeply
 *     equal []
 *     AssertionError: expected [ 'finance.export.costTotal' ] to deeply
 *     equal []
 *     AssertionError: expected [ 'payments.writeOff.notPosted',
 *     'payments.writeOff.nothingMoved' ] to deeply equal []
 */
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

const CATALOGUE = en as Record<string, string>;

/** Every catalogue key whose English contains `needle`, case-insensitively. */
function keysSaying(needle: string): string[] {
  return Object.entries(CATALOGUE)
    .filter(([, value]) => typeof value === "string" && value.toLowerCase().includes(needle))
    .map(([key]) => key)
    .sort();
}

describe("B14 rule 34 — one pair of words for held-here and in-the-books", () => {
  // Each of these is one of the six phrasings C11 counted, with the key it was
  // found on so a reader can see what was swept rather than take it on trust.
  it.each([
    ["posts nowhere", "assets.maintenance.costHelp"],
    ["moves no books", "finance.cost.postsNothing"],
    ["kept apart from the totals", "finance.export.costTotal"],
    ["reached the books", "payments.writeOff.notPosted · payments.writeOff.nothingMoved"],
    ["register-derived", "the accounting export's cost section"],
  ])("no screen says %s any more (was: %s)", (phrasing) => {
    expect(keysSaying(phrasing)).toEqual([]);
  });

  it("still says both halves of the pair, so the sweep deleted no meaning", () => {
    // The failure this guards against is the lazy version of the sweep:
    // deleting the sentences instead of rewording them, which passes every
    // assertion above and leaves a clerk with no idea where their money is.
    expect(keysSaying("in the books").length).toBeGreaterThan(5);
    expect(keysSaying("recorded").length).toBeGreaterThan(5);
  });

  it("the Costs screen names BOTH states, because both are reachable now", () => {
    // DEF-2365 — this key claimed a captured purchase reaches no trial balance,
    // which stopped being true when CR-060 T6 made a settled cost post.
    const costs = CATALOGUE["finance.cost.postsNothing"];
    expect(costs).toContain("Recorded");
    expect(costs).toContain("in the books");
    expect(costs).not.toContain("trial balance");
  });
});
