// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-CWP-4009 — no digit grouping on the meter dial figure. The
//          wireframe draws `153,040`; the product drew `6462`.
//          (`13-wireframe-delta.md` row X2.)
// Rules:   CLAUDE.md hard rule 3 (a CONSUMPTION always carries an explicit
//          unit) · BR-MET-106 (an unread month is ABSENT, never a zero) ·
//          B14 rule 36 (the kit owns the one visual decision)
// Impacts: portal/components/primitives.tsx · portal/usage/Readings.tsx
// ─────────────────────────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS, AND IT IS NOT "THE HELPER LOOKED UNTESTED".
//
// `formatDialFigure` shipped with a correct implementation, a long docstring
// and **no test of any kind** — `grep -rl formatDialFigure` over the portal's
// test files returned nothing. That is exactly the state DEF-CWP-4009's own
// `escape_reason` describes: *"digit grouping is invisible to every check in
// the repo and was found by comparing the wireframe PNG with a screenshot."*
// A fix for a defect nothing can see is one refactor away from being undone,
// silently, with every suite green.
//
// ⚠ **THE TRAP IS NAMED IN THE HELPER'S OWN DOCSTRING AND IS ASSERTED HERE.**
// The docstring warns that the next lane must not "fix" the missing unit by
// routing a dial figure through `formatQuantity` — that helper REFUSES a bare
// number and returns `null`, so the screen would print a dash where the
// number used to be. A warning in a comment is not a guarantee (hard-won law
// 1); the last case below is the guarantee.
import { describe, expect, it } from "vitest";

import { formatDialFigure, formatQuantity } from "./primitives";

describe("the number on the dial is grouped (DEF-CWP-4009)", () => {
  it("groups thousands — the wireframe's own figure", () => {
    // `CWP-034.png` draws this exact value. It is the number a customer reads
    // off the box on their wall and compares, digit by digit, with the screen.
    expect(formatDialFigure("153040")).toBe("153,040");
  });

  it("groups the four-digit figure the defect was raised on", () => {
    // The product drew `6462`. Four digits is where grouping starts mattering
    // and where it is easiest to argue it does not.
    expect(formatDialFigure("6462")).toBe("6,462");
  });

  it("groups a figure past a million, so the rule is not one comma", () => {
    expect(formatDialFigure("12345678")).toBe("12,345,678");
  });

  it("leaves a figure under a thousand alone", () => {
    expect(formatDialFigure("962")).toBe("962");
  });

  it("carries NO unit — hard rule 3 is not engaged by a register index", () => {
    // A dial figure is not a consumption: it is the running index on the face
    // of the meter. `gal` after it would claim the meter has measured 153,040
    // gallons since it was made. The *Used since* column beside it is the
    // consumption and keeps its unit.
    expect(formatDialFigure("153040")).not.toMatch(/[a-z]/i);
  });

  it("an absent reading stays absent — never a zero (BR-MET-106)", () => {
    expect(formatDialFigure(null)).toBeNull();
    expect(formatDialFigure("")).toBeNull();
  });

  it("strips the storage column's trailing zeros rather than printing them", () => {
    // The wire can carry `NUMERIC(18,6)` straight through. `153040.000000` and
    // `153040` are the same number to the last bit (DEF-646).
    expect(formatDialFigure("153040.000000")).toBe("153,040");
  });

  it("keeps a significant decimal — grouping must not round a measurement", () => {
    expect(formatDialFigure("153040.25")).toBe("153,040.25");
  });

  it("⚠ THE TRAP — routing a dial figure through formatQuantity yields NULL", () => {
    // This is the "fix" the helper's docstring tells the next lane not to
    // make, asserted so that making it is a RED suite rather than a dash on a
    // customer's screen. `formatQuantity` refuses a bare number by design.
    expect(formatQuantity("153040", null)).toBeNull();
    expect(formatQuantity("153040", "")).toBeNull();
    // …and it is right to, for a real consumption, which is the pair.
    expect(formatQuantity("4820", "gal")).toBe("4,820 gal");
  });
});
