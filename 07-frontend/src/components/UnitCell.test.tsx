// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories)  Screens: every consumption display (S25, S28, S30, …)
// Rules:    BR-SHL-023 (explicit unit — CLAUDE.md #3)
// ───────────────────────────────────────────────────────
// TC tests for FE-12 UnitCell: a consumption number can never render bare.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { UnitCell, formatQuantity } from "./UnitCell";

describe("US-SHL-013 — UnitCell (FE-12): consumption always carries its explicit unit", () => {
  it("US-SHL-013 (CLAUDE.md #3): quantity renders WITH its unit, non-breaking — '1247' kWh → '1,247 kWh'", () => {
    const html = renderToStaticMarkup(<UnitCell quantity="1247" unit="kWh" />);
    expect(html).toContain("1,247");
    expect(html).toContain("kWh");
    expect(html).toContain("1,247</span> "); // the unit never wraps away
  });

  it("US-SHL-013 (HR-3 by construction): the unit prop is REQUIRED — a bare quantity does not compile", () => {
    // @ts-expect-error — CLAUDE.md rule 3: consumption without an explicit unit is a type error
    const bare = <UnitCell quantity="1247" />;
    expect(bare).toBeDefined(); // the assertion above is the compile-time gate
  });

  // ⚠ **SUPERSEDED IN PART, 2026-08-27 (DEF-1120).** This case asserted that
  // the SERVED precision passes through untouched, which was right while no
  // signed rule said otherwise — `formatQuantity`'s own comment said so. The
  // PO ruled BR-MET-144 on 2026-08-27 (*"2 decimals max, trailing zeros
  // trimmed - this is correct"*), so a quantity now rounds HALF-UP to two
  // places first. What survives from the original case is the half that is
  // still true and still worth pinning: Intl's 3-digit default never applies,
  // and no zero is ever invented.
  it("US-SHL-013 · BR-MET-144: at most TWO decimals, no Intl 3-digit default, no invented zeros", () => {
    expect(formatQuantity("12.345")).toBe("12.35"); // was "12.345" pre-BR-MET-144
    expect(formatQuantity("0.123456")).toBe("0.12"); // was "0.123456"
    expect(formatQuantity("1247")).toBe("1,247"); // integers gain no fraction
    expect(formatQuantity("-3.5")).toBe("-3.5"); // under two places: untouched
  });

  // ── BR-MET-144, BOTH HALVES, AT THE BOUNDARY (DEF-1120) ──────────────────
  //
  // ⚠ **THE HALF A CARELESS FIX WOULD MISS IS THE TRIM**, and BR-MET-144 says
  // so in as many words: reaching two decimals and stopping satisfies a
  // careless reading of the rule and is still wrong, because `8.00 kgal` is
  // noise where `$8.00` is right — a quantity's precision is what the meter
  // measured. So these assert `"8"` and explicitly NOT `"8.00"`, exactly as
  // `06-backend/tests/test_def_894_quantity_display.py` does for the server
  // composer this must agree with.
  it("BR-MET-144 (DEF-1120): more than two decimals rounds HALF-UP, then trims", () => {
    expect(formatQuantity("26.243700")).toBe("26.24"); // the PO's own figure
    expect(formatQuantity("8.126")).toBe("8.13"); // above the tie → up
    expect(formatQuantity("8.125")).toBe("8.13"); // AT the tie → away from zero
    expect(formatQuantity("8.124")).toBe("8.12"); // below the tie → down
    expect(formatQuantity("-8.125")).toBe("-8.13"); // half-up = away from zero
    expect(formatQuantity("8.000000")).toBe("8"); // and NOT "8.00"
    expect(formatQuantity("8.996")).toBe("9"); // rounds to 9.00, then trims
    expect(formatQuantity("9.999")).toBe("10"); // the carry walks the whole
    expect(formatQuantity("0.000001")).toBe("0"); // rounds to 0.00, then trims
  });

  // The two implementations of BR-MET-144 that must agree, on the figures
  // `test_def_894_quantity_display.py` pins for the server (BR-SHL-250 §4 —
  // one rule, one implementation per runtime, and a test where there are two).
  it("BR-MET-144 (DEF-1120): the client agrees with apps/metering/quantity_display.py", () => {
    expect(formatQuantity("684.000000")).toBe("684"); // r10 draws "684 kWh"
    expect(formatQuantity("3.720000")).toBe("3.72"); // r10 draws "3.72 kgal"
    expect(formatQuantity("26.240000")).toBe("26.24"); // r10 draws "26.24 kgal"
    expect(formatQuantity("1008.000000")).toBe("1,008"); // DEF-1086's own figure
  });

  it("DEF-646: a trailing zero is an artefact of NUMERIC(18,6), not a measurement — it is stripped", () => {
    // PO 2026-08-24, on the deployed Meters tab: "meter reads are whole
    // numbers - youa re shoiwing 4 decimal". The read column showed
    // `1016.000000`, usage `8.000000 kgal` and the multiplier `1.000000`.
    expect(formatQuantity("1016.000000")).toBe("1,016");
    expect(formatQuantity("8.000000")).toBe("8");
    expect(formatQuantity("1.000000")).toBe("1");
    expect(formatQuantity("0.000000")).toBe("0");
  });

  it("DEF-646 (the safety property): a SIGNIFICANT digit is never reached — this rounds nothing", () => {
    // The distinction the fix turns on. Dropping a trailing zero changes no
    // value; dropping a non-zero digit would change what a clerk reads in a
    // billing dispute, and this must never do that.
    expect(formatQuantity("1016.250000")).toBe("1,016.25");
    // ⚠ **AMENDED 2026-08-27 (DEF-1120)** — these two used to assert
    // `"1,016.250001"` and `"0.000001"`, i.e. that a significant digit BEYOND
    // the second place survives. BR-MET-144 rules otherwise: two places is the
    // display ceiling and the sixth decimal of a meter read is not something a
    // clerk reads off a screen. **The safety property this case exists for is
    // unchanged and is the line above and the two below**: a significant digit
    // WITHIN the two places is never dropped, and `1,016.25` never becomes
    // `1,016`.
    expect(formatQuantity("1016.250001")).toBe("1,016.25");
    expect(formatQuantity("0.000001")).toBe("0");
    expect(formatQuantity("-3.500000")).toBe("-3.5");
    // A zero INSIDE the fraction is significant and stays.
    expect(formatQuantity("1016.010000")).toBe("1,016.01");
  });

  it("US-SHL-013 (CLAUDE.md #2-adjacent): the quantity never passes through Number()/float", () => {
    // 17 significant digits before the point — more than a double holds, so a
    // single `Number()` anywhere in the path corrupts the integer part and this
    // assertion catches it. The FRACTION now rounds to two places
    // (BR-MET-144); the WHOLE is byte-exact, which is what this case is for.
    expect(formatQuantity("12345678901234567.891234")).toBe("12,345,678,901,234,567.89");
    // The carry crossing the whole number, at a width no float can represent.
    expect(formatQuantity("12345678901234567.999")).toBe("12,345,678,901,234,568");
  });

  it("US-SHL-013 (negative): a malformed quantity renders verbatim — never NaN", () => {
    expect(formatQuantity("pending")).toBe("pending");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
