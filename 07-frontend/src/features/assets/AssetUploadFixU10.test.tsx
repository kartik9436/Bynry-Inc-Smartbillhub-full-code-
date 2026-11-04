/**
 * Plan U9 / U10 (PO 2026-09-30) — the asset screens and the upload picker
 * carry what the upload sheets carry.
 *
 *   * `sizeOptionsForService` — a size picker offers THIS service's sizes (and
 *     untagged ones), the set `AST.SIZE_FOR_SERVICE` accepts on upload;
 *   * `addPayload` — a device on a service sends its own unit of measure, and
 *     a blank unit sends nothing so the server stamps the service default;
 *   * `groupTargets` / `assetGroupKey` — the stage-2 picker shows the six
 *     plan groups, with the devices sheet's own words for two of them.
 *
 * RED first: before this change `sizeOptionsForService`, `groupTargets` and
 * `assetGroupKey` did not exist, and `addPayload` dropped a device's unit.
 */
import { describe, expect, it } from "vitest";

import { groupTargets, pickableTargets } from "@/components/workflow/MappingTable";
import { assetGroupKey } from "@/features/metering/ImportWorkflowPage";
import en from "@/i18n/locales/en.json";

import { addPayload, initialAddValues } from "./AssetAddWizard";
import { sizeOptionsForService } from "./assetsShared";

const SIZES = [
  { code: "W-58", name: 'Water 5/8"', active: true, service: { code: "water" } },
  { code: "CART-64", name: "Trash 64-gallon cart", active: true, service: { code: "trash" } },
  { code: "OWN-1", name: "Tenant's own size", active: true, service: null },
  { code: "CART-96", name: "Trash 96-gallon cart", active: false, service: { code: "trash" } },
];

describe("sizeOptionsForService", () => {
  it("offers the chosen service's active sizes and the untagged ones", () => {
    expect(sizeOptionsForService(SIZES, "trash").map((o) => o.value)).toEqual([
      "CART-64",
      "OWN-1",
    ]);
  });
  it("offers every active size before a service is chosen", () => {
    expect(sizeOptionsForService(SIZES, "").map((o) => o.value)).toEqual([
      "W-58",
      "CART-64",
      "OWN-1",
    ]);
  });
});

describe("addPayload — a device's unit of measure", () => {
  it("sends the unit a clerk typed for a device on a service", () => {
    const values = {
      ...initialAddValues("behind_the_meter"),
      type: "container_cart",
      service: "trash",
      unit: "cart",
    };
    expect(addPayload(values).unit).toBe("cart");
  });
  it("sends nothing for a blank unit, so the service default applies", () => {
    const values = {
      ...initialAddValues("behind_the_meter"),
      type: "container_cart",
      service: "trash",
      unit: "",
    };
    expect("unit" in addPayload(values)).toBe(false);
  });
});

describe("the stage-2 picker's six groups", () => {
  it("cuts the served list into runs of one group, flat when there are none", () => {
    const runs = groupTargets([
      { id: "asset_no", label: "Meter number", required: false, group: "Identity" },
      { id: "serial_no", label: "Serial number", required: false, group: "Identity" },
      { id: "unit_ref", label: "Unit", required: false, group: "Location" },
      { id: "custom_data.x", label: "Custom", required: false },
    ]);
    expect(runs.map(([group, members]) => [group, members.length])).toEqual([
      ["Identity", 2],
      ["Location", 1],
      [null, 1],
    ]);
  });
  it("offers the served '— ignore —' target once, not twice (DEF-AST-8361)", () => {
    // The server's list ends with its own ignore entry (BR-MET-088); the table
    // appends the one ignore option itself, so the served copy is dropped.
    const served = [
      { id: "asset_no", label: "Meter number", required: false, group: "Identity" },
      { id: "__ignore__", label: "— ignore —", required: false },
    ];
    expect(pickableTargets(served).map((target) => target.id)).toEqual(["asset_no"]);
  });
  it("uses the devices sheet's own words for details and dates", () => {
    const catalogue = en as Record<string, string>;
    expect(catalogue[assetGroupKey("details", "assets_devices")]).toBe("Device details");
    expect(catalogue[assetGroupKey("details", "assets_meters")]).toBe("Meter details");
    expect(catalogue[assetGroupKey("dates", "assets_devices")]).toBe("Dates and testing");
    expect(catalogue[assetGroupKey("service_billing", "assets_submeters")]).toBe(
      "Service and billing",
    );
  });
});
