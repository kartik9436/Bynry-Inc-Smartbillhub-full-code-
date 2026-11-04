// CR-167-BRC10 round 2 task 5 — the pure half of the New plan form.
import { describe, expect, it } from "vitest";

import { normalisePlanFormOptions } from "@/api/planFormEndpoints";

import { FORM_OPTIONS } from "./planFormOptions.fixture";
import {
  combinedTaxPercent,
  emptyPlanFormDraft,
  minimumBillDisplay,
  monthlyBaseTotal,
  planFormPayload,
  stepGaps,
  stillOffered,
  twoPlacesHalfUp,
  withOptionDefaults,
} from "./planFormModel";

const options = normalisePlanFormOptions(FORM_OPTIONS);
const context = {
  classLabel: (value: string) => options.customer_classes.find((row) => row.value === value)?.label ?? "",
  serviceLabel: (value: string) => options.services.find((row) => row.value === value)?.label ?? "",
};

describe("figures the form adds up — exact, never float (hard rule 2)", () => {
  it("rounds half-up to two places on the decimal string", () => {
    expect(twoPlacesHalfUp("8.250000")).toBe("8.25");
    expect(twoPlacesHalfUp("0.105")).toBe("0.11");
    expect(twoPlacesHalfUp("10")).toBe("10.00");
  });

  it("monthly base = each chosen service's smallest base, summed (J8: $10.00 + $9.00)", () => {
    const draft = {
      ...emptyPlanFormDraft(),
      services: [
        { key: "a", service: "water", schedule: "sch-w", surcharged: false },
        { key: "b", service: "sewer", schedule: "sch-s", surcharged: false },
      ],
    };
    expect(monthlyBaseTotal(draft, options)).toBe("19.00");
    expect(monthlyBaseTotal(emptyPlanFormDraft(), options)).toBeNull();
  });

  it("combined tax = 6.25% + 2% = 8.25%; none chosen is null, not 0%", () => {
    const draft = { ...emptyPlanFormDraft(), taxes: [{ key: "a", value: "tx-state" }, { key: "b", value: "tx-bexar" }] };
    expect(combinedTaxPercent(draft, options)).toBe("8.25%");
    expect(combinedTaxPercent(emptyPlanFormDraft(), options)).toBeNull();
  });

  it("DEF-RAT-9519 · combined is what the bill charges: a tax the classes do not pay is out, a split is no figure", () => {
    const draft = { ...emptyPlanFormDraft(), taxes: [{ key: "a", value: "tx-state" }, { key: "b", value: "tx-bexar" }] };
    const reach = (value: "all" | "some" | "none") =>
      normalisePlanFormOptions({
        ...FORM_OPTIONS,
        taxes: FORM_OPTIONS.taxes.map((row) => (row.ref.id === "tx-state" ? { ...row, reaches_plan_classes: value } : row)),
      });
    expect(combinedTaxPercent(draft, reach("none"))).toBe("2.00%");
    expect(combinedTaxPercent(draft, reach("some"))).toBeNull();
    expect(combinedTaxPercent(draft, reach("all"))).toBe("8.25%");
  });

  it("minimum bill shows two places, never 10.000000 (DEF-RAT-9287)", () => {
    expect(minimumBillDisplay({ ...emptyPlanFormDraft(), minimum_bill: "10" })).toBe("10.00");
    expect(minimumBillDisplay({ ...emptyPlanFormDraft(), minimum_bill: "" })).toBeNull();
  });
});

describe("DEF-RAT-9328 · the late fee is a row, never a silent default", () => {
  it("a new draft shows the utility's default codes as rows", () => {
    expect(withOptionDefaults(emptyPlanFormDraft(), options).charge_codes.map((row) => row.value)).toEqual(["cc-late"]);
  });

  it("a table the clerk has touched is never refilled", () => {
    const touched = { ...emptyPlanFormDraft(), charge_codes_touched: true };
    expect(withOptionDefaults(touched, options).charge_codes).toEqual([]);
  });

  it("the payload always carries charge_codes, [] included", () => {
    expect(planFormPayload({ ...emptyPlanFormDraft(), charge_codes_touched: true }, false, context).charge_codes).toEqual([]);
  });
});

describe("DEF-RAT-9285 · a note stores a class by its NAME", () => {
  it("customer_class is cls-res → Residential", () => {
    const draft = {
      ...emptyPlanFormDraft(),
      notes: [{ key: "n", attribute: "customer_class", operator: "is", value: "cls-res" }],
    };
    const details = planFormPayload(draft, false, context).details as { notes: unknown[] };
    expect(details.notes).toEqual([{ attribute: "customer_class", operator: "is", value: "Residential" }]);
  });
});

describe("table arrays", () => {
  it("a row offers what no OTHER row has picked, and keeps its own", () => {
    const rows = [{ value: "water" }, { value: "sewer" }];
    expect(stillOffered(rows, ["water", "sewer"], "water").map((row) => row.value)).toEqual(["water"]);
  });

  it("an empty service row and a surcharge with no percent are each refused by name", () => {
    const draft = {
      ...emptyPlanFormDraft(),
      outside_city: "yes" as const,
      services: [{ key: "a", service: "", schedule: "", surcharged: false }],
    };
    expect(stepGaps("services", draft)).toEqual({
      "plan-services": "rating.planForm.gap.serviceRow",
      "plan-surcharge": "rating.planForm.gap.surcharge",
    });
  });

  it("a start date is required to publish and not to save a draft", () => {
    expect(stepGaps("review", emptyPlanFormDraft(), true)).toEqual({ "plan-starts": "rating.planForm.gap.starts" });
    expect(stepGaps("review", emptyPlanFormDraft(), false)).toEqual({});
  });
});
