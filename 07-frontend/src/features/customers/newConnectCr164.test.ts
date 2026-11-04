// ── Trace ──────────────────────────────────────────────
// Change:  CR-164-BRC10 (lane NC-C, 2026-10-02) — the PO's screen-by-screen
//          changes to the New Connection wizard. This file holds the cases that
//          are pure functions over the draft; the rendered ones sit beside the
//          step each belongs to.
// Defects: DEF-CUS-9195 (step 1's language never reached the account) ·
//          DEF-CUS-9197 (meters / behind-the-meter / work orders counted wrong)
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { PAYMENT_TERM_DAYS, paymentTermOptions } from "./NewConnectChargesStep";
import { commitPlanOf, emptyDraft, unitServiceKey } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { equipmentCounts, unitTypeChoices } from "./NewConnectUnitsStep";

const t = ((key: string, opts?: { defaultValue?: string; count?: number }) =>
  (opts?.defaultValue ?? key).replace("{{count}}", String(opts?.count ?? ""))) as never;

function build(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  const base = emptyDraft();
  return {
    ...base,
    owner: { ...base.owner, name: "Balcones Development LLC", partyKind: "company" },
    premise: { ...base.premise, address: "1400 Brazos Bend Drive", premiseType: "apartment_complex" },
    scope: "new_premise",
    pattern: { ...base.pattern, prefix: "Apt", from: "1", to: "2" },
    premiseServices: ["electric", "solar", "trash"],
    ...over,
  };
}

const ASSET_TYPES = [
  { code: "meter", name: "Meter", category: "meters" },
  { code: "sub_meter", name: "Sub-meter", category: "sub_meters" },
  { code: "pv", name: "Solar panels", category: "behind_the_meter" },
  { code: "battery", name: "Battery", category: "behind_the_meter" },
  { code: "container_cart", name: "Cart", category: "" },
];

describe("DEF-CUS-9197 — meters and behind-the-meter devices are counted apart", () => {
  it("counts each by the tenant's own category, per unit, with extra pieces", () => {
    const draft = build({
      unitServiceGrid: {
        [unitServiceKey("Apt 1", "trash")]: { taken: true, more: ["CART-64"] },
      },
    });
    const units = [
      { label: "Apt 1", isCommonArea: false },
      { label: "Apt 2", isCommonArea: false },
    ];
    // electric → meter ×2, solar → pv ×2, trash → cart ×2 plus one more piece.
    expect(equipmentCounts(draft, units, ASSET_TYPES)).toEqual({
      meters: 2,
      subMeters: 0,
      behindTheMeter: 2,
      other: 3,
    });
  });

  it("follows the clerk's own pick over the usual device", () => {
    const draft = build({
      premiseServices: ["electric"],
      unitServiceGrid: { [unitServiceKey("Apt 1", "electric")]: { taken: true, assetType: "battery" } },
    });
    const counts = equipmentCounts(draft, [{ label: "Apt 1", isCommonArea: false }], ASSET_TYPES);
    expect(counts.meters).toBe(0);
    expect(counts.behindTheMeter).toBe(1);
  });
});

describe("CR-164-BRC10 item 15 — the unit type travels", () => {
  it("offers the utility's own active types and never common_area", () => {
    expect(
      unitTypeChoices(
        [
          { code: "residential", name: "Residential" },
          { code: "common_area", name: "Common area" },
          { code: "retail", name: "Retail", active: false },
        ],
        t,
      ),
    ).toEqual([{ value: "residential", label: "Residential" }]);
  });

  it("sends each dwelling's type and none for a common area or an unanswered one", () => {
    const plan = commitPlanOf(
      build({
        pattern: { prefix: "Apt", from: "1", to: "2", includeCommonArea: true },
        unitTypes: { "Apt 1": "residential", "Apt 2": "" },
      }),
      null,
    );
    const byLabel = Object.fromEntries(plan.units.map((unit) => [unit.label, unit]));
    expect(byLabel["Apt 1"]).toMatchObject({ unit_type: "residential" });
    expect(byLabel["Apt 2"]).not.toHaveProperty("unit_type");
    const common = plan.units.find((unit) => unit.is_common_area);
    expect(common).toBeDefined();
    expect(common).not.toHaveProperty("unit_type");
  });
});

describe("DEF-CUS-9195 — step 1's Communication panel reaches the owner's account", () => {
  it("sends the language and both ticks on the owner block", () => {
    const plan = commitPlanOf(
      build({ communication: { language: "es-MX", paperlessBill: true, smsReminders: true } }),
      null,
    );
    expect(plan.owner).toMatchObject({
      preferred_language: "es-MX",
      paperless: true,
      sms_reminders: true,
    });
  });

  it("sends null for no language, never English", () => {
    const plan = commitPlanOf(build(), null);
    expect(plan.owner).toMatchObject({ preferred_language: null });
  });
});

describe("CR-164-BRC10 wave 2 — the owner's own customer fields travel", () => {
  it("sends them for a new owner, empty included, and never over a picked customer", () => {
    const fresh = commitPlanOf(build({ ownerCustomData: { loyalty_tier: "Gold" } }), null);
    expect(fresh.owner).toMatchObject({ customer_custom_data: { loyalty_tier: "Gold" } });
    expect(commitPlanOf(build(), null).owner).toMatchObject({ customer_custom_data: {} });
    const base = build({ ownerCustomData: { loyalty_tier: "Gold" } });
    const picked = commitPlanOf(
      { ...base, owner: { ...base.owner, matchedCustomerId: "c-1", matchedCustomerNo: "C-1" } },
      null,
    );
    expect(picked.owner).not.toHaveProperty("customer_custom_data");
  });
});

describe("CR-164-BRC10 item 19 — payment terms are a list", () => {
  it("offers 7, 15, 30, 60 and 90 days", () => {
    expect(PAYMENT_TERM_DAYS).toEqual(["7", "15", "30", "60", "90"]);
    expect(paymentTermOptions("", t).map((option) => option.label)).toEqual([
      "7 days",
      "15 days",
      "30 days",
      "60 days",
      "90 days",
    ]);
  });

  it("keeps a figure a parked draft holds that the list lacks", () => {
    expect(paymentTermOptions("45", t).at(-1)).toEqual({ value: "45", label: "45 days" });
  });
});
