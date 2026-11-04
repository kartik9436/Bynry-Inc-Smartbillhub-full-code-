// CR-166-BRC10 round 3 task 7 — the pure half of the discount EDIT form.
import { describe, expect, it } from "vitest";

import type { DiscountEditRow } from "@/api/discountEditEndpoints";

import {
  correctionPayload,
  discountDraftFromRow,
  discountEditModeOf,
  editFieldHome,
  editStepGaps,
  infoPatchPayload,
  lockedFields,
  newValuePayload,
  storedMoney,
  storedPoints,
} from "./discountEditModel";
import { limitsSetCount } from "./discountFormModel";

const ELIGIBILITY = [
  { value: "everyone", label: "Everyone on the plan", checked_by: "system" as const },
  { value: "age_65_or_over", label: "Age 65 or over", checked_by: "proof" as const },
];

function row(extra: Partial<Record<keyof DiscountEditRow, unknown>> = {}): DiscountEditRow {
  return {
    id: "d",
    code: "SENIOR",
    name: "Senior discount",
    type: "percentage",
    value: "15.000000",
    status: "active",
    applies_to: "whole_bill",
    effective_from: "2026-08-01",
    effective_to: null,
    bill_floor_amount: "0.000000",
    stacking_precedence: 10,
    stacks_with_others: true,
    exclusivity_group: { value: "none", label: "None" },
    eligibility: { value: "age_65_or_over", label: "Age 65 or over", checked_by: "proof" },
    program_owner: { value: "billing", label: "Billing" },
    programme_owner: "billing",
    verification: "annual_recertification",
    ...extra,
  } as unknown as DiscountEditRow;
}

describe("the served row, read back into the New form's draft", () => {
  it("percentage POINTS are read as typed — never divided (BR-RAT-087)", () => {
    expect(storedPoints("15.000000")).toBe("15");
    expect(storedPoints("1.500000")).toBe("1.5");
    expect(discountDraftFromRow(row()).value).toBe("15");
  });

  it("money keeps two places and drops only trailing zeros past them", () => {
    expect(storedMoney("25.000000")).toBe("25.00");
    expect(storedMoney("12312.500000")).toBe("12312.50");
    expect(storedMoney(null)).toBe("");
    expect(discountDraftFromRow(row({ type: "fixed_amount", value: "25.000000" })).value).toBe("25.00");
  });

  it("the §9 objects are read by CODE — never [object Object]", () => {
    const draft = discountDraftFromRow(row());
    expect([draft.eligibility, draft.exclusivity_group, draft.program_owner]).toEqual(["age_65_or_over", "none", "billing"]);
  });

  it("a zero floor is the stored default, so an untouched discount reads No limits (image 31)", () => {
    const draft = discountDraftFromRow(row());
    expect(draft.bill_floor_amount).toBe("");
    expect(limitsSetCount(draft)).toBe(0);
  });
});

describe("which choice an address opens", () => {
  it("?change= names it; the old Fix door's ?correct=1 is Fix a mistake; nothing is Name and details", () => {
    expect(discountEditModeOf(new URLSearchParams("change=change"))).toBe("change");
    expect(discountEditModeOf(new URLSearchParams("correct=1"))).toBe("correct");
    expect(discountEditModeOf(new URLSearchParams(""))).toBe("info");
  });
});

describe("README point 7 — what each choice locks", () => {
  it("Name and details locks value, limits and the start; a draft locks nothing", () => {
    const live = lockedFields("info", false);
    for (const field of ["value", "cap_per_bill", "exclusivity_group", "effective_from", "code", "discount_type"] as const) {
      expect(live.has(field), field).toBe(true);
    }
    expect(live.has("effective_to")).toBe(false);
    expect(live.has("name")).toBe(false);
    expect(lockedFields("info", true).has("value")).toBe(false);
  });

  it("Fix a mistake locks the dates; New value from a date does not", () => {
    expect(lockedFields("correct", false).has("effective_from")).toBe(true);
    expect(lockedFields("correct", false).has("effective_to")).toBe(true);
    expect(lockedFields("change", false).has("effective_from")).toBe(false);
  });
});

describe("each save sends exactly what its door accepts", () => {
  const original = discountDraftFromRow(row());

  it("PATCH carries the changed keys only; a cleared box is null, not absent", () => {
    const current = { ...original, verification_method: "one_time_proof", budget_cap: "" };
    expect(infoPatchPayload({ ...original, budget_cap: "500.00" }, current, { eligibility: ELIGIBILITY, isDraft: false })).toEqual({
      verification_method: "one_time_proof",
      budget_cap: null,
    });
  });

  it("a new who-qualifies travels with the proof flag it implies (ruling 3)", () => {
    const current = { ...original, eligibility: "everyone" };
    expect(infoPatchPayload(original, current, { eligibility: ELIGIBILITY, isDraft: false })).toEqual({
      eligibility: "everyone",
      proof_required: false,
      proof_before_first_reduction: false,
    });
  });

  it("a cleared floor is 0, the stored no-floor — never null (BR-RAT-074)", () => {
    const before = { ...original, bill_floor_amount: "10.00" };
    const body = correctionPayload(before, { ...before, bill_floor_amount: "" }, "Floor typed by mistake.", { eligibility: ELIGIBILITY });
    expect(body).toEqual({ bill_floor_amount: "0", reason: "Floor typed by mistake." });
  });

  it("a new value always sends the value and the start, and the end only when typed", () => {
    const current = { ...original, value: "12", effective_from: "2027-01-01" };
    expect(newValuePayload(original, current, { eligibility: ELIGIBILITY })).toEqual({ value: "12", effective_from: "2027-01-01" });
    expect(newValuePayload(original, { ...current, effective_to: "2027-06-30" }, { eligibility: ELIGIBILITY })).toEqual({
      value: "12",
      effective_from: "2027-01-01",
      effective_to: "2027-06-30",
    });
  });

  it("the scope travels as one group, so a stale service never stays behind", () => {
    const before = { ...original, applies_to: "one_service", applies_to_service: "water" };
    const body = correctionPayload(before, { ...before, applies_to: "whole_bill" }, "Wrong scope chosen.", { eligibility: ELIGIBILITY });
    expect(body).toEqual({
      applies_to: "whole_bill",
      applies_to_service: null,
      applies_to_services: [],
      applies_to_charge_codes: [],
      reason: "Wrong scope chosen.",
    });
  });
});

describe("validation and where a refusal lands", () => {
  const original = discountDraftFromRow(row());

  it("image 32 · a new start on or before today's start is a gap naming that date", () => {
    const gaps = editStepGaps("change", "value", { ...original, effective_from: "2026-08-01" }, {
      eligibility: ELIGIBILITY,
      isDraft: false,
      liveFrom: "2026-08-01",
      reason: "",
    });
    expect(gaps["discount-starts"]).toEqual({ key: "rating.discountEdit.gap.startAfter", params: { date: "2026-08-01" } });
  });

  it("image 35 · a fix with no reason is a gap on the reason box", () => {
    const gaps = editStepGaps("correct", "value", original, { eligibility: ELIGIBILITY, isDraft: false, liveFrom: "", reason: " " });
    expect(Object.keys(gaps)).toEqual(["discount-reason"]);
  });

  it("a refusal for a box this choice does not draw goes to the strip, never to a hidden box", () => {
    expect(editFieldHome("correct", "effective_from")).toBeUndefined();
    expect(editFieldHome("change", "effective_from")).toEqual({ box: "discount-starts", step: "value" });
    expect(editFieldHome("correct", "reason")).toEqual({ box: "discount-reason", step: "value" });
    expect(editFieldHome("info", "verification_method")).toEqual({ box: "discount-verification", step: "eligibility" });
  });
});
