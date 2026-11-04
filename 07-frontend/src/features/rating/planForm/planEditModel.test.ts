// CR-167-BRC10 round 3 task 8 — the pure half of the plan EDIT form. Each case
// names the image or the rule it holds (images 37–44 of
// `05-prototype/plans-2026-10-03/images/`).
import { describe, expect, it } from "vitest";

import { normalisePlanEditRow } from "@/api/planEditEndpoints";
import { normalisePlanFormOptions } from "@/api/planFormEndpoints";

import {
  EDIT_STEPS,
  changedFields,
  correctionPayload,
  editFieldHome,
  editStepGaps,
  editSteps,
  lockedFields,
  newVersionPayload,
  nextVersionNumber,
  openingDraft,
  patchPayload,
  planDraftFromRow,
  planEditModeOf,
  planEditPath,
  stepFromParams,
  withPlanItems,
} from "./planEditModel";
import { FORM_OPTIONS } from "./planFormOptions.fixture";
import { PUBLISHED_PLAN } from "./planEdit.fixture";

const options = normalisePlanFormOptions(FORM_OPTIONS);
const row = normalisePlanEditRow(PUBLISHED_PLAN);
const merged = withPlanItems(options, row.sections);
const original = planDraftFromRow(row, merged);
const ctx = { classLabel: (v: string) => (v === "cls-res" ? "Residential" : ""), serviceLabel: (v: string) => v };

describe("the three choices and their steps (images 38, 40, 43)", () => {
  it("Name and details is Details · Review; the other two are Services · Charges · Billing · Review", () => {
    expect(EDIT_STEPS.info.map((s) => s.id)).toEqual(["details", "review"]);
    expect(EDIT_STEPS.change.map((s) => s.id)).toEqual(["services", "charges", "billing", "review"]);
    expect(EDIT_STEPS.correct.map((s) => s.id)).toEqual(["services", "charges", "billing", "review"]);
  });

  it("a draft has the New form's five steps and locks nothing", () => {
    expect(editSteps("change", true).map((s) => s.id)).toEqual(["details", "services", "charges", "billing", "review"]);
    expect(lockedFields("change", true).size).toBe(0);
  });

  it("the address PLAN-DETAIL links to: ?change=…&step=n, step kept inside the list", () => {
    expect(planEditPath("p 1", "change", 2)).toBe("/plans-rates/plans/p%201/edit?change=change&step=2");
    expect(planEditPath("p1", null, 3)).toBe("/plans-rates/plans/p1/edit?step=3");
    expect(planEditModeOf(new URLSearchParams("change=correct"))).toBe("correct");
    expect(planEditModeOf(new URLSearchParams(""))).toBe("info");
    expect(stepFromParams(new URLSearchParams("step=2"), EDIT_STEPS.change)).toBe(2);
    expect(stepFromParams(new URLSearchParams("step=9"), EDIT_STEPS.change)).toBe(1);
  });

  it("Name and details locks every price, the window and the code; the other two lock the details", () => {
    const info = lockedFields("info", false);
    expect(info.has("services")).toBe(true);
    expect(info.has("code")).toBe(true);
    expect(info.has("name")).toBe(false);
    expect(lockedFields("change", false).has("name")).toBe(true);
    expect(lockedFields("change", false).has("effective_from")).toBe(false);
    expect(lockedFields("correct", false).has("effective_from")).toBe(true);
  });
});

describe("the plan read back into the form", () => {
  it("every table opens on what the plan carries, the minimum and surcharge as typed", () => {
    expect(original.services.map((r) => [r.service, r.schedule, r.surcharged])).toEqual([
      ["water", "sch-w", true],
      ["sewer", "sch-s", false],
    ]);
    expect(original.charge_codes.map((r) => r.value)).toEqual(["cc-late", "cc-recon"]);
    expect(original.taxes.map((r) => r.value)).toEqual(["tx-state", "tx-bexar"]);
    expect(original.deposits.map((r) => r.value)).toEqual(["dep-1"]);
    expect(original.minimum_bill).toBe("10.00");
    expect(original.outside_city).toBe("yes");
    expect(original.outside_city_percent).toBe("25");
    expect(original.customer_classes).toEqual(["cls-res"]);
  });

  it("the minimum and the surcharge are the VERSION's (sections), never the plan columns that mirror the head", () => {
    const head = normalisePlanEditRow({ ...PUBLISHED_PLAN, minimum_bill_amount: "12.0000", outside_city_percent: "50.000000" });
    const draft = planDraftFromRow(head, merged);
    expect(draft.minimum_bill).toBe("10.00");
    expect(draft.outside_city_percent).toBe("25");
  });

  it("DEF-RAT-9328 (Edit half): the late fee is a row, and the New form's default is never added over the plan's own answer", () => {
    expect(original.charge_codes_touched).toBe(true);
    const none = planDraftFromRow(normalisePlanEditRow({ ...PUBLISHED_PLAN, charge_codes: [] }), merged);
    expect(none.charge_codes).toEqual([]);
    expect(none.charge_codes_touched).toBe(true);
  });

  it("a note stored by the class NAME opens on that class (DEF-RAT-9285)", () => {
    expect(original.notes.map((n) => n.value)).toEqual(["cls-res"]);
  });

  it("the plan's own items join the lists, so a retired code still opens on its row", () => {
    const retired = withPlanItems({ ...options, charge_codes: [] }, row.sections);
    expect(retired.charge_codes.map((c) => c.ref.id)).toEqual(["cc-late", "cc-recon"]);
  });

  it("Change from a date opens with an empty window (image 41); the others keep today's", () => {
    expect(openingDraft(original, "change", false).effective_from).toBe("");
    expect(openingDraft(original, "correct", false).effective_from).toBe("2026-09-01");
  });

  it("the next version is one past the highest the plan has", () => {
    expect(nextVersionNumber(row)).toBe(2);
  });
});

describe("only what moved travels", () => {
  it("an untouched plan moves nothing", () => {
    for (const mode of ["info", "change", "correct"] as const) {
      expect(changedFields(mode, false, original, openingDraft(original, mode, false)).filter((f) => !f.startsWith("effective"))).toEqual([]);
    }
  });

  it("a re-ordered table is not a change", () => {
    const reordered = { ...original, taxes: [...original.taxes].reverse() };
    expect(changedFields("change", false, original, reordered)).toEqual([]);
  });

  it("Name and details sends `details` with the moved key only (BR-RAT-1067)", () => {
    expect(patchPayload(false, original, { ...original, name: "Residential — City" }, ctx)).toEqual({
      details: { name: "Residential — City" },
    });
  });

  it("DEF-RAT-9514: a DRAFT edited only on a priced step still sends `details` — the contract's marker", () => {
    // The server tells the new body from the old 8-step one by `details`
    // (`plan_writes.is_contract_body`); without it `taxes` was refused as an
    // unknown field and a draft's Save as draft / Publish plan never saved.
    const current = { ...original, taxes: original.taxes.slice(1), effective_from: "2026-11-01" };
    const body = patchPayload(true, original, current, ctx);
    expect(body.details).toEqual({});
    expect(Object.keys(body)).toContain("taxes");
  });

  it("Change from a date: the moved content, the window, the reason, publish — and NO untouched table", () => {
    const current = { ...openingDraft(original, "change", false), minimum_bill: "12", effective_from: "2027-01-01" };
    const body = newVersionPayload(original, current, " New floor ", true, ctx);
    expect(body).toEqual({
      minimum_bill_amount: "12",
      effective_from: "2027-01-01",
      reason: "New floor",
      publish: true,
    });
  });

  it("DEF-RAT-9328 (Edit half): removing the late-fee row sends the list without it", () => {
    const current = { ...openingDraft(original, "change", false), charge_codes: original.charge_codes.slice(1), effective_from: "2027-01-01" };
    expect(newVersionPayload(original, current, "x", false, ctx).charge_codes).toEqual([{ charge: "cc-recon" }]);
  });

  it("a cleared minimum bill is sent as null, never omitted", () => {
    const body = correctionPayload(original, { ...original, minimum_bill: "" }, "typo", 1, ctx);
    expect(body).toEqual({ minimum_bill_amount: null, reason: "typo", version: 1 });
  });

  it("switching the surcharge off re-sends the services with their ticks cleared", () => {
    const body = correctionPayload(original, { ...original, outside_city: "no" }, "typo", 1, ctx);
    expect(body.outside_city_percent).toBeNull();
    expect(body.services).toEqual([
      { service: "water", schedule: "sch-w", surcharged: false },
      { service: "sewer", schedule: "sch-s", surcharged: false },
    ]);
  });
});

describe("what each choice refuses", () => {
  const live = { isDraft: false, liveFrom: "2026-09-01", reason: "", publish: true };

  it("image 42: a new version needs a start after today's and a reason", () => {
    const gaps = editStepGaps("change", "review", { ...original, effective_from: "" }, live);
    expect(Object.keys(gaps).sort()).toEqual(["plan-reason", "plan-starts"]);
    const early = editStepGaps("change", "review", { ...original, effective_from: "2026-09-01" }, { ...live, reason: "x" });
    expect(early["plan-starts"]).toEqual({ key: "rating.planEdit.gap.startAfter", params: { date: "2026-09-01" } });
  });

  it("image 44: a fix needs a reason and nothing else on Review", () => {
    expect(Object.keys(editStepGaps("correct", "review", original, live))).toEqual(["plan-reason"]);
    expect(editStepGaps("info", "review", original, live)).toEqual({});
  });

  it("a server refusal lands on its box only where the choice draws it", () => {
    expect(editFieldHome("charge_codes[0].charge", EDIT_STEPS.change)).toEqual({ box: "plan-charges", step: "charges" });
    expect(editFieldHome("reason", EDIT_STEPS.correct)).toEqual({ box: "plan-reason", step: "review" });
    expect(editFieldHome("charge_codes[0].charge", EDIT_STEPS.info)).toBeUndefined();
  });
});
