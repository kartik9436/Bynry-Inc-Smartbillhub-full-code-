// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave E · E2 — the SMS segment counter and the cost it warns
//          about.
// Screens: SET-10 · the SMS designers (S103–S106)
// ───────────────────────────────────────────────────────
// The arithmetic, without a DOM. The boundary CR-048 names is 160 and the four
// interesting cases all sit within two characters of it, which is exactly the
// kind of thing a rendered assertion states badly: a `toHaveTextContent("2")`
// cannot tell a segment count from a character count that happens to contain a
// two.
//
// ⚠ **THE LAST CASE IS A GUARD ON AN ABSENCE, AND IT IS THE IMPORTANT ONE.**
// `smsSegments.ts` deliberately does NOT write GSM-7's 153-character
// concatenated part: it is a fact about the standard, no signed rule of this
// product states it, nothing serves it, and there is no SMS provider adapter in
// this release. The counter is therefore OPTIMISTIC beyond about 306
// characters, and that is asserted rather than left as a comment — so a lane
// that later implements the real concatenation rule has to change a red test,
// with the module note in front of it, instead of quietly changing behaviour.
import { describe, expect, it } from "vitest";

import { smsCost } from "./smsSegments";

/** What `templates_api.py` actually serves. Passed in everywhere rather than
 *  hardcoded in the module, which is why the server sends it. */
const SEGMENT = 160;

describe("CR-048 E2 — one message, and what a second one costs", () => {
  it("an empty body is ONE message, never zero", () => {
    // "0 messages" reads as "this costs nothing to send" rather than as "there
    // is nothing here", and those are different statements.
    expect(smsCost(0, SEGMENT)).toEqual({
      length: 0,
      segments: 1,
      remaining: 160,
      overSegment: false,
    });
  });

  it("the four seeded SMS bodies are all one message", () => {
    // A19 r8 records them at 99–138 characters and states no cap, which is why
    // this is a COUNTER and not a limit.
    for (const length of [99, 103, 130, 138]) {
      expect(smsCost(length, SEGMENT).segments).toBe(1);
      expect(smsCost(length, SEGMENT).overSegment).toBe(false);
    }
  });

  it("150 characters leaves 10, still one message", () => {
    expect(smsCost(150, SEGMENT)).toEqual({
      length: 150,
      segments: 1,
      remaining: 10,
      overSegment: false,
    });
  });

  it("EXACTLY 160 is still one message — the boundary is inclusive", () => {
    // CR-048's words are *"passing 160 characters splits the message"*, so 160
    // itself does not. An off-by-one here charges twice for a body that fits.
    const cost = smsCost(160, SEGMENT);
    expect(cost.segments).toBe(1);
    expect(cost.remaining).toBe(0);
    expect(cost.overSegment).toBe(false);
  });

  it("⚠ 161 is TWO messages — the doubling CR-048 is worried about", () => {
    // *"Passing 160 characters splits the message into two segments and doubles
    // the per-message cost — on a 2,000-account run that is real money."*
    const cost = smsCost(161, SEGMENT);
    expect(cost.segments).toBe(2);
    expect(cost.overSegment).toBe(true);
    // …and 159 characters of room before a third.
    expect(cost.remaining).toBe(159);
  });

  it("a segment size of zero answers honestly instead of dividing by it", () => {
    // It cannot arrive from this server. "One message, nothing left" is the
    // only answer that is not a lie if it ever does.
    expect(smsCost(200, 0)).toEqual({
      length: 200,
      segments: 1,
      remaining: 0,
      overSegment: false,
    });
  });

  it("⚠ IS OPTIMISTIC PAST ~306 CHARACTERS, and that is recorded, not hidden", () => {
    // In GSM-7 a concatenated message spends six bytes per part on a header, so
    // each part carries 153 characters and 320 characters is really THREE
    // parts. This counter says TWO, because 153 is a fact about the standard
    // and NOT a signed rule of this product — nothing serves it and there is no
    // provider adapter in this release for it to be true of. Writing it would
    // be resolving an open question by choosing a value.
    //
    // This assertion exists so the limit is visible in a test run rather than
    // only in a docstring: when the concatenation rule is ruled and served,
    // this case goes RED and the module note is the first thing its author
    // reads.
    expect(smsCost(320, SEGMENT).segments).toBe(2);
  });
});
