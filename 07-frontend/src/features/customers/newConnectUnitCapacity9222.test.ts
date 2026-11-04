// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-9222 — a thermal tonnage or a storm-water class picked on
//           step 3 never reached the commit, and step 5 counted a thermal
//           METER the commit never fits (S2: review 6 meters, created 4).
// Found:    the New Connection end-to-end web walk, 2026-10-02 / 03
//           (08-qa/screens/nc-e2e-walk-2026-10-03/RESULTS.md).
// Server:   06-backend/tests/test_def_met_9222_unit_capacity_at_commit.py
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import type { UnitServiceCell } from "./newConnectDraft";
import { commitPlanOf, draftUnits, emptyDraft, unitServiceKey } from "./newConnectDraft";
import { equipmentCounts } from "./NewConnectUnitsStep";

const ASSET_TYPES = [
  { code: "meter", name: "Meter", category: "meters" },
  { code: "sub_meter", name: "Sub-meter", category: "sub_meters" },
  { code: "container_cart", name: "Cart", category: "behind_the_meter" },
  { code: "fire_line", name: "Fire line", category: "behind_the_meter" },
  { code: "pv", name: "PV panel", category: "behind_the_meter" },
  { code: "battery", name: "Battery", category: "behind_the_meter" },
];

function twoUnitDraft(services: string[], grid: Record<string, UnitServiceCell> = {}) {
  return {
    ...emptyDraft(),
    premiseServices: services,
    pattern: { prefix: "Unit ", from: "1", to: "2", includeCommonArea: false },
    unitServiceGrid: grid,
  };
}

describe("DEF-MET-9222 — thermal tonnage and the storm-water class travel, and no thermal meter is counted", () => {
  it("sends the size step 3 shows for thermal and storm water on their unit_services rows", () => {
    const draft = twoUnitDraft(["electric", "storm_water", "thermal_heat"], {
      [unitServiceKey("Unit 1", "storm_water")]: { sizeClass: "SW-APT" },
      [unitServiceKey("Unit 2", "storm_water")]: { sizeClass: "SW-SF" },
      [unitServiceKey("Unit 1", "thermal_heat")]: { sizeClass: "TH-T10" },
      [unitServiceKey("Unit 2", "thermal_heat")]: { sizeClass: "TH-T25" },
    });
    const plan = commitPlanOf(draft, null, []);
    const sized = Object.fromEntries(
      plan.unit_services.map((row) => [`${row.unit_label}|${row.service}`, row.size_class]),
    );
    expect(sized).toEqual({
      "Unit 1|storm_water": "SW-APT",
      "Unit 2|storm_water": "SW-SF",
      "Unit 1|thermal_heat": "TH-T10",
      "Unit 2|thermal_heat": "TH-T25",
    });
    // Neither is a device: nobody installs an ERU or a ton.
    expect(plan.unit_services.every((row) => row.equipment.length === 0)).toBe(true);
  });

  it("a service whose capacity is on equipment sends no size_class of its own", () => {
    const draft = twoUnitDraft(["trash"], {
      [unitServiceKey("Unit 1", "trash")]: { assetType: "container_cart", sizeClass: "CART-96" },
    });
    const plan = commitPlanOf(draft, null, []);
    expect(plan.unit_services.find((row) => row.unit_label === "Unit 1")?.size_class).toBeUndefined();
  });

  it("S2's shape: the review counts exactly the meters the commit fits — 4, not 6", () => {
    const draft = twoUnitDraft(["electric", "water", "fire", "solar", "battery", "thermal_heat"]);
    const counted = equipmentCounts(draft, draftUnits(draft), ASSET_TYPES);
    const plan = commitPlanOf(draft, null, []);
    expect(plan.meters).toHaveLength(4);
    expect(counted.meters + counted.subMeters).toBe(plan.meters.length);
  });
});
