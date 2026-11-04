// CR-166-BRC10 round 2 task 4 — the pure rules of the New discount form.
import { describe, expect, it } from "vitest";

import type { DiscountEligibilityOption } from "@/api/discountFormEndpoints";

import {
  NEW_DISCOUNT_STEPS,
  automaticRefused,
  discountFormPayload,
  emptyDiscountFormDraft,
  exampleReduction,
  limitsSetCount,
  stepGaps,
  stepOfField,
  withListDefaults,
} from "./discountFormModel";
import type { DiscountFormDraft } from "./discountFormModel";

const ELIGIBILITY: DiscountEligibilityOption[] = [
  { value: "autopay_on", label: "Autopay is on", checked_by: "system" },
  { value: "age_65", label: "Age 65 or over", checked_by: "proof" },
];

function draft(patch: Partial<DiscountFormDraft> = {}): DiscountFormDraft {
  return {
    ...emptyDiscountFormDraft(),
    code: "senior",
    name: "Senior discount",
    discount_type: "percentage",
    applies_to: "whole_bill",
    value: "15",
    eligibility: "age_65",
    enrolment_mode: "apply_and_approve",
    effective_from: "2026-11-01",
    ...patch,
  };
}

describe("the percent a clerk types is the percent the API stores", () => {
  it("15 typed is sent as \"15\" — percentage POINTS, never the fraction 0.15", () => {
    const body = discountFormPayload(draft({ value: "15" }), { currency: "USD", eligibility: ELIGIBILITY });
    expect(body.value).toBe("15");
    expect(body.discount_type).toBe("percentage");
  });

  it("15 takes $9.00 off the $60.00 example bill", () => {
    expect(exampleReduction(draft({ value: "15" }))).toBe("9.00");
    expect(exampleReduction(draft({ value: "0.5" }))).toBe("0.30");
  });

  it("over 100 is refused on the box, 100 itself is not (image 14)", () => {
    expect(stepGaps("details", draft({ value: "150" }), ELIGIBILITY)["discount-value"]).toBe(
      "rating.discountForm.gap.over100",
    );
    expect(stepGaps("details", draft({ value: "100" }), ELIGIBILITY)["discount-value"]).toBeUndefined();
  });
});

describe("currency is the utility's own, or absent — never anything else", () => {
  it("sends the utility's code and nothing a clerk typed", () => {
    const body = discountFormPayload(draft(), { currency: "CAD", eligibility: ELIGIBILITY });
    expect(body.currency).toBe("CAD");
  });

  it("leaves the key out when the utility's code is not known yet, rather than guessing USD", () => {
    const body = discountFormPayload(draft(), { currency: null, eligibility: ELIGIBILITY });
    expect("currency" in body).toBe(false);
  });

  it("the draft has no currency field a screen could fill", () => {
    expect("currency" in emptyDiscountFormDraft()).toBe(false);
  });
});

describe("ruling 3 — a proof condition cannot be Automatic", () => {
  it("Automatic with a proof condition is a gap on the Enrollment box", () => {
    const d = draft({ eligibility: "age_65", enrolment_mode: "automatic" });
    expect(automaticRefused(d, ELIGIBILITY)).toBe(true);
    expect(stepGaps("eligibility", d, ELIGIBILITY)["discount-enrollment"]).toBe(
      "rating.discountForm.gap.automaticProof",
    );
  });

  it("Automatic with a system condition is allowed", () => {
    const d = draft({ eligibility: "autopay_on", enrolment_mode: "automatic" });
    expect(automaticRefused(d, ELIGIBILITY)).toBe(false);
    expect(stepGaps("eligibility", d, ELIGIBILITY)["discount-enrollment"]).toBeUndefined();
  });

  it("proof_required follows the condition, never a box", () => {
    expect(discountFormPayload(draft({ eligibility: "age_65" }), { currency: null, eligibility: ELIGIBILITY }).proof_required).toBe(true);
    expect(discountFormPayload(draft({ eligibility: "autopay_on" }), { currency: null, eligibility: ELIGIBILITY }).proof_required).toBe(false);
  });
});

describe("step validation", () => {
  it("an empty Details step names code, label and value (image 13: Fix 3 things first)", () => {
    const empty = { ...emptyDiscountFormDraft(), discount_type: "percentage", applies_to: "whole_bill" };
    expect(Object.keys(stepGaps("details", empty, ELIGIBILITY)).sort()).toEqual([
      "discount-code",
      "discount-label",
      "discount-value",
    ]);
  });

  it("Eligibility names who qualifies and an end before the start (image 16: Fix 2 things first)", () => {
    const d = draft({ eligibility: "", effective_from: "2026-11-01", effective_to: "2026-01-01" });
    expect(stepGaps("eligibility", d, ELIGIBILITY)).toEqual({
      "discount-who": "rating.discountForm.gap.who",
      "discount-ends": "rating.discountForm.gap.endsBefore",
    });
  });

  it("a scope that names a target needs one", () => {
    expect(stepGaps("details", draft({ applies_to: "one_service" }), ELIGIBILITY)["discount-service"]).toBeDefined();
    expect(stepGaps("details", draft({ applies_to: "named_codes" }), ELIGIBILITY)["discount-codes"]).toBeDefined();
    expect(stepGaps("details", draft({ applies_to: "specific_services" }), ELIGIBILITY)["discount-services"]).toBeDefined();
  });

  it("a charge waiver asks for no value", () => {
    expect(stepGaps("details", draft({ discount_type: "charge_waiver", value: "" }), ELIGIBILITY)["discount-value"]).toBeUndefined();
  });

  // DEF-RAT-9318 (CR-166 web walk step 1.6): the server requires `value` on
  // every version and refused a waiver the form had sent none for — so a
  // charge waiver could never be saved. A waiver's value is never read by
  // pricing (it removes the whole charge) and is served as a dash, so the body
  // carries 0; a rate override likewise.
  it("a charge waiver and a rate override send a value the server keeps (0), never none", () => {
    for (const type of ["charge_waiver", "rate_override"]) {
      const body = discountFormPayload(draft({ discount_type: type, value: "" }), { currency: "USD", eligibility: ELIGIBILITY });
      expect(body.value).toBe("0");
    }
  });
});

describe("limits, defaults and the step array", () => {
  it("counts caps, floor and a group — not the stacking order", () => {
    expect(limitsSetCount(draft({ stacking_precedence: "40" }))).toBe(0);
    expect(limitsSetCount(draft({ cap_per_bill: "25", cap_per_year: "300", bill_floor_amount: "5", exclusivity_group: "low_income" }))).toBe(4);
    expect(limitsSetCount(draft({ exclusivity_group: "none" }))).toBe(0);
  });

  it("the cap per bill trims the example", () => {
    expect(exampleReduction(draft({ value: "50", cap_per_bill: "10" }))).toBe("10.00");
  });

  it("list defaults fill once and never overwrite a choice", () => {
    const lists = {
      types: [{ value: "percentage", label: "P" }],
      applies_to: [{ value: "whole_bill", label: "W" }],
      enrollment_modes: [{ value: "automatic", label: "A" }],
      verification: [],
      lapse: [],
      budget_periods: [{ value: "annual", label: "Annual" }],
      budget_out: [],
      exclusivity_groups: [{ value: "none", label: "None" }],
    };
    expect(withListDefaults(emptyDiscountFormDraft(), lists).enrolment_mode).toBe("automatic");
    // The select shows its first row; the draft holds it, so Review agrees.
    expect(withListDefaults(emptyDiscountFormDraft(), lists).exclusivity_group).toBe("none");
    expect(withListDefaults(draft({ enrolment_mode: "apply_and_approve" }), lists).enrolment_mode).toBe("apply_and_approve");
  });

  it("three steps, one word each, and Review's Edit links open the right one", () => {
    expect(NEW_DISCOUNT_STEPS.map((s) => s.id)).toEqual(["details", "eligibility", "review"]);
    expect(stepOfField("cap_per_bill", NEW_DISCOUNT_STEPS)).toBe(1);
    expect(stepOfField("budget_cap", NEW_DISCOUNT_STEPS)).toBe(2);
  });
});
