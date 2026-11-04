// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-6119 — a build's commit carried only METERED services, so
//           trash, fire, sewer and the sized equipment of solar and battery
//           reached the server on no key at all.
// Change:   CR-159-BRC10 (a portal request carried to an active customer, PO
//           2026-10-01) — the six-service utility the PO named that day.
// Server:   06-backend/tests/test_portal_request_to_active.py (`unit_services`)
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import type { UnitServiceCell } from "./newConnectDraft";
import { commitPlanOf, draftFromRaisedBuild, emptyDraft, unitServiceKey } from "./newConnectDraft";
import { ownerIdentityShortfall } from "./NewConnectOwnerStep";

const SIX = ["water", "trash", "sewer", "fire", "solar", "battery"];

function sixServiceDraft() {
  const draft = emptyDraft();
  const grid: Record<string, UnitServiceCell> = {
    // What the units step PINS when its catalogues arrive — the defaults the
    // row shows (`NewConnectUnitsStep`). Fire's device is the FIRE LINE by PO
    // ruling 2026-10-02 (`OQ-1361`); the step offers it as it offers a cart.
    [unitServiceKey("Unit 1", "trash")]: { assetType: "container_cart", sizeClass: "CART-96" },
    [unitServiceKey("Unit 1", "fire")]: { assetType: "fire_line", sizeClass: "FL-4" },
    [unitServiceKey("Unit 1", "solar")]: { assetType: "pv", sizeClass: "SOL-P5" },
    [unitServiceKey("Unit 1", "battery")]: { assetType: "battery", sizeClass: "BAT-10" },
  };
  return {
    ...draft,
    premiseServices: SIX,
    pattern: { prefix: "Unit", from: "1", to: "1", includeCommonArea: false },
    unitServiceGrid: grid,
  };
}

describe("DEF-MET-6119 — every service a build sells reaches the commit, with its size", () => {
  it("sends one unit_services row per non-metered service, sized where it is sized", () => {
    const plan = commitPlanOf(sixServiceDraft(), null, []);
    const byService = Object.fromEntries(plan.unit_services.map((row) => [row.service, row]));
    expect(Object.keys(byService).sort()).toEqual(["battery", "fire", "sewer", "solar", "trash"]);
    expect(byService.trash.equipment).toEqual([
      { type: "container_cart", size_class: "CART-96", count: 1 },
    ]);
    expect(byService.fire.equipment).toEqual([{ type: "fire_line", size_class: "FL-4", count: 1 }]);
    expect(byService.solar.equipment).toEqual([{ type: "pv", size_class: "SOL-P5", count: 1 }]);
    expect(byService.battery.equipment).toEqual([
      { type: "battery", size_class: "BAT-10", count: 1 },
    ]);
    // Sewer is a share of water (`BR-RAT-015`): recorded, nothing to size.
    expect(byService.sewer.equipment).toEqual([]);
    expect(plan.unit_services.every((row) => row.unit_label === "Unit 1")).toBe(true);
  });

  it("leaves water on `meters` and never sends a meter as sized equipment", () => {
    const draft = sixServiceDraft();
    draft.unitServiceGrid[unitServiceKey("Unit 1", "sewer")] = {
      assetType: "meter",
      sizeClass: "W-58",
    };
    const plan = commitPlanOf(draft, null, []);
    expect(plan.meters.map((row) => row.service)).toContain("water");
    expect(plan.unit_services.find((row) => row.service === "water")).toBeUndefined();
    expect(plan.unit_services.find((row) => row.service === "sewer")?.equipment).toEqual([]);
  });

  it("a dropped service is not sent", () => {
    const draft = sixServiceDraft();
    draft.unitServiceGrid[unitServiceKey("Unit 1", "fire")] = { taken: false };
    const plan = commitPlanOf(draft, null, []);
    expect(plan.unit_services.map((row) => row.service)).not.toContain("fire");
  });
});

describe("OQ-1361 / DEF-MET-9037 — fire lines are counted per size, and solar fits no meter (PO 2026-10-02)", () => {
  it("a 6\" fire line and two 2\" lines go as FL-6 × 1 and FL-2 × 2 — the $84.00 build", () => {
    // *"A · A fire service gets a "fire line" item with a size (2" to 10"),
    // like a trash cart."* One row per piece, counted here, never typed.
    const draft = sixServiceDraft();
    draft.unitServiceGrid[unitServiceKey("Unit 1", "fire")] = {
      assetType: "fire_line",
      sizeClass: "FL-6",
      more: ["FL-2", "FL-2"],
    };
    const plan = commitPlanOf(draft, null, []);
    const fire = plan.unit_services.find((row) => row.service === "fire");
    expect(fire?.equipment).toEqual([
      { type: "fire_line", size_class: "FL-6", count: 1 },
      { type: "fire_line", size_class: "FL-2", count: 2 },
    ]);
  });

  it("three 4 kW panels go as SOL-P4 × 3, and no meter is fitted for solar or battery", () => {
    // *"The net meter doesn't count toward capacity. Capacity is the panels or
    // battery only."* 3 × 4 kW = 12 kW is what the bill sums.
    const draft = sixServiceDraft();
    draft.unitServiceGrid[unitServiceKey("Unit 1", "solar")] = {
      assetType: "pv",
      sizeClass: "SOL-P4",
      more: ["SOL-P4", "SOL-P4"],
    };
    const plan = commitPlanOf(draft, null, []);
    expect(plan.unit_services.find((row) => row.service === "solar")?.equipment).toEqual([
      { type: "pv", size_class: "SOL-P4", count: 3 },
    ]);
    expect(plan.meters.map((row) => row.service)).toEqual(["water"]);
  });
});

describe("DEF-MET-9221 — a meter carries the size its row shows (New Connection end-to-end walk)", () => {
  it("water's row at Water 1\" sends the meter with that size; a row with none sends none", () => {
    const draft = sixServiceDraft();
    draft.unitServiceGrid[unitServiceKey("Unit 1", "water")] = { assetType: "meter", sizeClass: "W-1" };
    expect(commitPlanOf(draft, null, []).meters).toEqual([
      { unit_label: "Unit 1", service: "water", asset_no: null, size_class: "W-1" },
    ]);
    delete draft.unitServiceGrid[unitServiceKey("Unit 1", "water")];
    expect(commitPlanOf(draft, null, []).meters).toEqual([
      { unit_label: "Unit 1", service: "water", asset_no: null },
    ]);
  });
});

describe("DEF-CUS-9074 — a build raised from a portal request starts with what the request holds", () => {
  function raised(over: Record<string, unknown>) {
    return {
      id: "con-1",
      connection_no: "CON-26-0131",
      request_no: "SR-26-0020",
      mode: null,
      target_activation: null,
      premises: null,
      prefill: {
        request_id: "sr-1",
        request_no: "SR-26-0020",
        applicant_kind: "business",
        applicant_name: "Juniper Foods Co",
        applicant_email: "ap@juniperfoods.test",
        applicant_phone: "(281) 555-0312",
        matched_customer_id: null,
        address_as_given: "83 Juniper Bend",
        address_unit_as_given: null,
        plot_or_parcel: null,
        property_type: null,
        what_is_being_built: null,
        units_on_property: null,
        service_codes: ["water", "sewer", "trash", "solar", "battery", "fire"],
        account_type_code: "industrial",
        date_of_birth: null,
        tax_id_last4: "0012",
        tax_id_present: true,
        ...over,
      },
    } as unknown as Parameters<typeof draftFromRaisedBuild>[1];
  }

  it("the services the applicant ticked, the class and the date of birth arrive on the draft", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), raised({ date_of_birth: "1990-01-15" }));
    expect([...draft.premiseServices].sort()).toEqual([...SIX].sort());
    expect(draft.owner.category).toBe("industrial");
    expect(draft.owner.dateOfBirth).toBe("1990-01-15");
  });

  it("a new business whose Tax ID is on the application is NOT held for retyping it", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), raised({}));
    expect(draft.owner.partyKind).toBe("company");
    expect(draft.owner.taxId).toBe("");
    expect(ownerIdentityShortfall(draft.owner)).toBeNull();
  });

  it("with no Tax ID on the application, a new business is still held (BR-CUS-1024)", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), raised({ tax_id_present: false, tax_id_last4: null }));
    expect(ownerIdentityShortfall(draft.owner)).toBe("customers.account.identity_required_company");
  });

  it("what the clerk already typed on a resumed draft is never overwritten", () => {
    const resumed = emptyDraft();
    resumed.premiseServices = ["water"];
    resumed.owner = { ...resumed.owner, category: "commercial" };
    const draft = draftFromRaisedBuild(resumed, raised({}));
    expect(draft.premiseServices).toEqual(["water"]);
    expect(draft.owner.category).toBe("commercial");
  });
});

describe("DEF-CUS-9047 — step 1's Customer category reaches the owner's account", () => {
  it("the category the clerk picked travels as the owner's account_type", () => {
    const draft = sixServiceDraft();
    draft.owner = { ...draft.owner, name: "Kestrel Energy Co-op", category: "agricultural" };
    const plan = commitPlanOf(draft, null, []);
    expect(plan.owner.account_type).toBe("agricultural");
  });

  it("no category picked sends none, so the request's class (or the door's default) decides", () => {
    const draft = sixServiceDraft();
    draft.owner = { ...draft.owner, name: "Kestrel Energy Co-op", category: "" };
    const plan = commitPlanOf(draft, null, []);
    expect(plan.owner).not.toHaveProperty("account_type");
  });
});
