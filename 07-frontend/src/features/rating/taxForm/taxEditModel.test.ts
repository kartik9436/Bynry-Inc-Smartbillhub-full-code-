// CR-165-BRC10 task 7 — the pure rules of the edit form (images 24–33).
import { describe, expect, it } from "vitest";

import type { TaxEditRow } from "@/api/taxEditEndpoints";
import { taxRowDefaults } from "../taxRowFixture";

import {
  EDIT_STEPS,
  changedFields,
  correctionPayload,
  dayBefore,
  editModeOf,
  editStepGaps,
  infoPatchPayload,
  lockedFields,
  newRatePayload,
  storedAmount,
  taxFormDraftFromRow,
} from "./taxEditModel";

/** ann arbor City as the drawings show it: 150 %, 09/01/2026 – 11/10/2027. */
function annArbor(): TaxEditRow {
  return {
    ...taxRowDefaults(),
    id: "tax-aa",
    name: "ann arbor City",
    kind: "percent",
    rate: "1.500000",
    effective_from: "2026-09-01",
    effective_to: "2027-11-10",
    code: "AA-CITY",
    liability_gl_account_id: "gl-2200-01",
    filing_frequency: "monthly",
    due_date_rule: "20th_next_month",
    collection_allowance_percent: "0.005000",
    interest_penalty_percent: "0.015000",
    filing_reminder_recipient: "filings@ottumwawater.example",
    version: 1,
    authority_account: { id: "acct-ott", label: "City of Ottumwa Finance · OTT-0042" },
  } as TaxEditRow;
}

describe("the served row reads back as the New form's draft", () => {
  it("150 % stored as 1.500000 reads 150; allowance 0.005 reads 0.5", () => {
    const draft = taxFormDraftFromRow(annArbor());
    expect(draft.rate_percent).toBe("150");
    expect(draft.allowance_percent).toBe("0.5");
    expect(draft.interest_percent).toBe("1.5");
    expect(draft.boundary).toBe("everywhere");
    expect(draft.authority_account_id).toBe("acct-ott");
  });

  it("a stored amount drops zeros past the cents and never rounds", () => {
    expect(storedAmount("1.250000")).toBe("1.25");
    expect(storedAmount("12.000000")).toBe("12.00");
    expect(storedAmount("0.123400")).toBe("0.1234");
    expect(storedAmount(null)).toBe("");
  });
});

describe("the three choices", () => {
  it("?change= picks the flow, and anything else is Name and filing", () => {
    expect(editModeOf("change")).toBe("change");
    expect(editModeOf("correct")).toBe("correct");
    expect(editModeOf("info")).toBe("info");
    expect(editModeOf(null)).toBe("info");
    expect(editModeOf("nonsense")).toBe("info");
  });

  it("the drawn step lists — Name · Filing · Review; New rate · Review; Fix the rate · Review", () => {
    expect(EDIT_STEPS.info.map((s) => s.labelKey)).toEqual([
      "rating.taxEdit.step.name",
      "rating.taxForm.step.filing",
      "rating.taxForm.step.review",
    ]);
    expect(EDIT_STEPS.change.map((s) => s.labelKey)).toEqual(["rating.taxEdit.step.newRate", "rating.taxForm.step.review"]);
    expect(EDIT_STEPS.correct.map((s) => s.labelKey)).toEqual(["rating.taxEdit.step.fixRate", "rating.taxForm.step.review"]);
  });

  it("P46 — Name and filing locks rate, reach and dates; Fix a mistake locks the dates", () => {
    const info = lockedFields("info");
    for (const field of ["rate_percent", "basis", "boundary", "services", "customer_classes", "effective_from", "effective_to", "jurisdiction"] as const) {
      expect(info.has(field)).toBe(true);
    }
    expect(info.has("name")).toBe(false);
    expect(info.has("filing_reminder_recipient")).toBe(false);
    const correct = lockedFields("correct");
    expect(correct.has("effective_from")).toBe(true);
    expect(correct.has("effective_to")).toBe(true);
    expect(correct.has("rate_percent")).toBe(false);
  });

  it("CR-008 as amended — the liability account is locked in EVERY variation", () => {
    for (const mode of ["info", "change", "correct"] as const) {
      expect(lockedFields(mode).has("liability_gl_account_id")).toBe(true);
    }
  });
});

describe("info → PATCH /taxes/{id}: the CHANGED name and filing keys only", () => {
  it("a new reminder address sends that key and nothing else", () => {
    const original = taxFormDraftFromRow(annArbor());
    const current = { ...original, filing_reminder_recipient: "tax@ottumwawater.example" };
    expect(infoPatchPayload(original, current)).toEqual({ filing_reminder_recipient: "tax@ottumwawater.example" });
  });

  it("never sends liability_gl_account_id, even if the draft's box somehow moved", () => {
    const original = taxFormDraftFromRow(annArbor());
    const current = { ...original, name: "Ann Arbor City", liability_gl_account_id: "gl-other" };
    const body = infoPatchPayload(original, current);
    expect(body).toEqual({ name: "Ann Arbor City" });
    expect("liability_gl_account_id" in body).toBe(false);
  });

  it("a rate typed under Name and filing is not a change it can send", () => {
    const original = taxFormDraftFromRow(annArbor());
    expect(changedFields("info", original, { ...original, rate_percent: "6.25" })).toEqual([]);
  });

  it("a cleared reminder is sent as null, so the server clears it", () => {
    const original = taxFormDraftFromRow(annArbor());
    expect(infoPatchPayload(original, { ...original, filing_reminder_recipient: "" })).toEqual({
      filing_reminder_recipient: null,
    });
  });
});

describe("change → POST /taxes/{id}/new-rate", () => {
  it("6.25 % from 11/01/2026 sends the fraction, its form and the new window", () => {
    const original = taxFormDraftFromRow(annArbor());
    const body = newRatePayload({ ...original, rate_percent: "6.25", effective_from: "2026-11-01" });
    expect(body).toEqual({
      kind: "percent",
      rate: "0.0625",
      flat_amount: null,
      per_unit_amount: null,
      per_meter_amount: null,
      effective_from: "2026-11-01",
      effective_to: "2027-11-10",
    });
  });

  it("image 28 · what is taxed, discounts and rounding are open on a new rate and sent only when changed", () => {
    const change = lockedFields("change");
    for (const field of ["base_includes_usage", "base_includes_base", "discount_treatment", "rounding_rule"] as const) {
      expect(change.has(field)).toBe(false);
    }
    expect(change.has("services")).toBe(true);
    const original = taxFormDraftFromRow(annArbor());
    const untouched = newRatePayload({ ...original, rate_percent: "6.5", effective_from: "2026-11-01" }, original);
    expect(Object.keys(untouched)).not.toContain("discount_treatment");
    expect(Object.keys(untouched)).not.toContain("rounding_rule");
    const flip = original.discount_treatment === "after" ? "before" : "after";
    const changed = newRatePayload(
      { ...original, rate_percent: "6.5", effective_from: "2026-11-01", base_includes_usage: false, discount_treatment: flip, rounding_rule: "half_even" },
      original,
    );
    expect(changed).toMatchObject({ base_includes_usage: false, discount_treatment: flip, rounding_rule: "half_even" });
    expect(Object.keys(changed)).not.toContain("base_includes_base");
  });

  it("Today's rate ends the day before: 11/01/2026 → 10/31/2026, across a year too", () => {
    expect(dayBefore("2026-11-01")).toBe("2026-10-31");
    expect(dayBefore("2027-01-01")).toBe("2026-12-31");
    expect(dayBefore("2028-03-01")).toBe("2028-02-29");
  });

  it("image 29 — a start on or before today's start is marked: Must be after 09/01/2026", () => {
    const original = taxFormDraftFromRow(annArbor());
    const ctx = { placeBoundaries: [], liveFrom: "2026-09-01", reason: "" };
    expect(editStepGaps("change", "much", { ...original, effective_from: "2026-08-01" }, ctx)["tax-from"]).toEqual({
      key: "rating.taxEdit.gap.startAfter",
      params: { date: "2026-09-01" },
    });
    expect(editStepGaps("change", "much", { ...original, effective_from: "2026-09-01" }, ctx)["tax-from"]).toBeDefined();
    expect(editStepGaps("change", "much", { ...original, effective_from: "2026-11-01" }, ctx)).toEqual({});
  });
});

describe("correct → POST /taxes/{id}/corrections", () => {
  it("150 → 6.25 sends the rate and the reason, never the window", () => {
    const original = taxFormDraftFromRow(annArbor());
    const body = correctionPayload(original, { ...original, rate_percent: "6.25" }, " Rate typed as 150%. ");
    expect(body).toEqual({
      kind: "percent",
      rate: "0.0625",
      flat_amount: null,
      per_unit_amount: null,
      per_meter_amount: null,
      reason: "Rate typed as 150%.",
    });
    expect("effective_from" in body).toBe(false);
  });

  it("image 32 — no reason is marked: Enter the reason.", () => {
    const original = taxFormDraftFromRow(annArbor());
    const gaps = editStepGaps("correct", "much", { ...original, rate_percent: "6.25" }, { placeBoundaries: [], liveFrom: "2026-09-01", reason: " " });
    expect(gaps).toEqual({ "tax-reason": { key: "rating.taxEdit.gap.reason" } });
  });
});
