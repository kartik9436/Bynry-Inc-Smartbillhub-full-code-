// CR-165-BRC10 task 4 — the pure rules of the New tax or fee form.
//
// Each block names the problem it closes. Where today's `TaxWizard.tsx` has the
// same rule, the block's first case was run against it first and went RED (the
// figures are in the CR's round-2 record): today's `taxPayload` sends the rate
// AS TYPED, so `6.25` reached the server as 625 %, and it never sends a draft
// flag at all.
import { describe, expect, it } from "vitest";

import {
  BASIS_FLAT,
  emptyTaxFormDraft,
  enabledServiceOptions,
  exampleBill,
  fractionToPercent,
  isPercentShape,
  percentIsHigh,
  percentToFraction,
  stepGaps,
  taxFormPayload,
} from "./taxFormModel";
import type { TaxFormDraft } from "./taxFormModel";

function draft(over: Partial<TaxFormDraft> = {}): TaxFormDraft {
  return { ...emptyTaxFormDraft(), basis: "percent", ...over };
}

const NO_PLACE = { placeBoundaries: [] as string[] };

describe("P8/P17 · the rate is typed and shown as a PERCENT and stored as a fraction", () => {
  it("6.25 typed is 0.0625 on the wire", () => {
    expect(percentToFraction("6.25")).toBe("0.0625");
    expect(taxFormPayload(draft({ rate_percent: "6.25" }), { asDraft: false, ...NO_PLACE }).rate).toBe("0.0625");
  });

  it("converts on the STRING, never through a float", () => {
    // Number("0.07") / 100 is 0.0007000000000000001.
    expect(percentToFraction("0.07")).toBe("0.0007");
    expect(percentToFraction("150")).toBe("1.5");
    expect(percentToFraction("0.5")).toBe("0.005");
    expect(percentToFraction("20")).toBe("0.2");
    expect(percentToFraction("6.2500")).toBe("0.0625");
  });

  it("reads a stored fraction back as the percent it means", () => {
    expect(fractionToPercent("0.062500")).toBe("6.25");
    expect(fractionToPercent("1.500000")).toBe("150");
    expect(fractionToPercent("0.005000")).toBe("0.5");
    expect(fractionToPercent(null)).toBe("");
  });

  it("refuses a box that is not a percent rather than guessing", () => {
    expect(percentToFraction("6,25")).toBeNull();
    expect(percentToFraction("abc")).toBeNull();
    expect(percentToFraction("6.12345")).toBeNull(); // five places of a percent is seven of the fraction
    expect(isPercentShape("6.25")).toBe(true);
  });

  it("6.25 typed puts $3.75 on the $60.00 example bill", () => {
    expect(exampleBill(draft({ rate_percent: "6.25" })).effect).toBe("3.75");
    expect(exampleBill(draft({ rate_percent: "62.5" })).effect).toBe("37.50");
  });

  it("the after-discounts column taxes $55.00", () => {
    const bill = exampleBill(draft({ rate_percent: "6.25" }));
    expect(bill.taxedAfterDiscount).toBe("55.00");
    expect(bill.taxAfterDiscount).toBe("3.44");
  });

  it("taxing usage only taxes the $40.00 of usage", () => {
    expect(exampleBill(draft({ rate_percent: "10", base_includes_base: false })).effect).toBe("4.00");
  });

  it("a fixed amount adds itself, whatever the bill", () => {
    expect(exampleBill(draft({ basis: BASIS_FLAT, amount: "6.25" })).effect).toBe("6.25");
    const body = taxFormPayload(draft({ basis: BASIS_FLAT, amount: "6.25" }), { asDraft: false, ...NO_PLACE });
    expect(body.flat_amount).toBe("6.25");
    expect(body.rate).toBeUndefined();
  });

  it("allowance and late interest are percents too, and interest is per month", () => {
    const body = taxFormPayload(draft({ allowance_percent: "0.5", interest_percent: "1.5" }), {
      asDraft: false,
      ...NO_PLACE,
    });
    expect(body.collection_allowance_percent).toBe("0.005");
    expect(body.interest_penalty_percent).toBe("0.015");
    expect(body.interest_penalty_basis).toBe("monthly");
  });
});

describe("P9 · over 20 % warns", () => {
  it("150 typed is flagged", () => {
    expect(percentIsHigh("150")).toBe(true);
  });
  it("62.5 is flagged and 20 itself is not", () => {
    expect(percentIsHigh("62.5")).toBe(true);
    expect(percentIsHigh("20")).toBe(false);
    expect(percentIsHigh("20.01")).toBe(true);
    expect(percentIsHigh("6.25")).toBe(false);
  });
});

describe("DEF-RAT-9275 · Save draft & exit asks for a draft BY NAME", () => {
  it("as_draft: true on the draft exit", () => {
    expect(taxFormPayload(draft({ name: "x" }), { asDraft: true, ...NO_PLACE }).as_draft).toBe(true);
  });
  it("absent — not false — on Save tax, so the body is the one the server always saw", () => {
    expect("as_draft" in taxFormPayload(draft({ name: "x" }), { asDraft: false, ...NO_PLACE })).toBe(false);
  });
});

describe("P1 · only the services this utility has switched on", () => {
  it("drops every row with enabled: false and keeps the tenant's own name", () => {
    const rows = [
      { service: "electric", name: "Electric", enabled: true },
      { service: "water", name: "Water", enabled: true },
      { service: "gas", name: "Gas", enabled: false },
      { service: "fire", name: "Fire lines", enabled: false },
    ];
    expect(enabledServiceOptions(rows)).toEqual([
      { value: "electric", label: "Electric" },
      { value: "water", label: "Water" },
    ]);
  });
  it("an absent list offers nothing, never the platform's eleven", () => {
    expect(enabledServiceOptions(undefined)).toEqual([]);
  });
  it("an empty selection is sent as [] — which the server reads as ALL services", () => {
    expect(taxFormPayload(draft(), { asDraft: false, ...NO_PLACE }).applies_to_services).toEqual([]);
  });
});

describe("step validation — each missing box is named, by box", () => {
  it("step 1 names the name and the authority (image 08: Fix 2 things first)", () => {
    expect(Object.keys(stepGaps("what", draft(), NO_PLACE))).toEqual(["tax-name", "tax-authority"]);
  });
  it("a named place asks for its place name (image 07)", () => {
    const gaps = stepGaps("what", draft({ name: "x", jurisdiction: "j", boundary: "named" }), {
      placeBoundaries: ["named"],
    });
    expect(Object.keys(gaps)).toEqual(["tax-place"]);
  });
  it("step 2 names an empty rate (image 11: Fix 1 thing first)", () => {
    expect(Object.keys(stepGaps("much", draft({ effective_from: "2026-10-01" }), NO_PLACE))).toEqual(["tax-rate"]);
  });
  it("step 2 refuses nothing being taxed, and an end before the start", () => {
    const gaps = stepGaps(
      "much",
      draft({
        rate_percent: "6.25",
        base_includes_usage: false,
        base_includes_base: false,
        effective_from: "2026-10-01",
        effective_to: "2026-09-01",
      }),
      NO_PLACE,
    );
    expect(Object.keys(gaps)).toEqual(["tax-taxed", "tax-to"]);
  });
  it("step 3 names the liability account and a bad email (image 14: Fix 2 things first)", () => {
    expect(Object.keys(stepGaps("filing", draft({ filing_reminder_recipient: "bad" }), NO_PLACE))).toEqual([
      "tax-liability",
      "tax-reminder",
    ]);
  });
  it("a complete step has no gaps", () => {
    expect(stepGaps("what", draft({ name: "State sales tax", jurisdiction: "j" }), NO_PLACE)).toEqual({});
    expect(stepGaps("much", draft({ rate_percent: "6.25", effective_from: "2026-10-01" }), NO_PLACE)).toEqual({});
    expect(stepGaps("filing", draft({ liability_gl_account_id: "a" }), NO_PLACE)).toEqual({});
  });
});
