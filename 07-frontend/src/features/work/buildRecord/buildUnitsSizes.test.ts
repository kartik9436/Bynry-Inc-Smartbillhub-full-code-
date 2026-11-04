// DEF-CUS-9218 — the request's Units tab shows EVERY size on a row, with its
// count. Found by the New Connection end-to-end walk (CON-26-0131): one 6-inch
// and two 2-inch fire lines read "FL-2 · 3", hiding the 6-inch line.
import { describe, expect, it } from "vitest";

import type { ActivationRow } from "@/features/customers/buildLifecycleEndpoints";
import type { Translator } from "@/features/customers/newConnectShared";
import { sizesText, unitTypeName } from "@/features/work/buildRecord/BuildUnitsTab";

const piece = (asset_no: string, size_class: string | null) =>
  ({ id: asset_no, asset_no, size_class, type_name: "Fire service line", status_name: "Inventory" }) as unknown as ActivationRow["assets"][number];

describe("sizesText", () => {
  it("names both sizes when a unit holds a 6-inch and two 2-inch lines", () => {
    expect(sizesText([piece("FS-1", "FL-2"), piece("FS-2", "FL-2"), piece("FS-3", "FL-6")])).toBe(
      "FL-2 × 2 · FL-6",
    );
  });
  it("prints one size bare when every piece shares it (Qty says how many)", () => {
    expect(sizesText([piece("C-1", "CART-96"), piece("C-2", "CART-96")])).toBe("CART-96");
  });
  // DEF-RAT-9321 — the utility's NAME for each size, never the code.
  it("prints each size's name, not its code, when the catalogue names it", () => {
    const names = new Map([
      ["FL-2", 'Fire line 2"'],
      ["FL-6", 'Fire line 6"'],
    ]);
    const shown = sizesText([piece("FS-1", "FL-2"), piece("FS-2", "FL-2"), piece("FS-3", "FL-6")], names);
    expect(shown).toBe('Fire line 2" × 2 · Fire line 6"');
    expect(shown).not.toContain("FL-");
  });
  it("is null when no piece carries a size (a meter)", () => {
    expect(sizesText([piece("M-1", null)])).toBeNull();
    expect(sizesText([])).toBeNull();
  });
});

// DEF-MET-9244 — a unit's TYPE in the utility's own words, never its code.
// Found by the walk: the Units tab read "residential_submetered".
describe("unitTypeName", () => {
  const t: Translator = (key, params) =>
    key === "metering.units.type.commercial"
      ? "Commercial"
      : String((params as { defaultValue?: string } | undefined)?.defaultValue ?? key);
  it("reads the utility's own lookup name first", () => {
    const names = new Map([["residential_submetered", "Residential (sub-metered)"]]);
    expect(unitTypeName("residential_submetered", names, t)).toBe("Residential (sub-metered)");
  });
  it("falls back to the catalogue's word for a seeded code", () => {
    expect(unitTypeName("commercial", new Map(), t)).toBe("Commercial");
  });
  it("says nothing for no type at all", () => {
    expect(unitTypeName(null, new Map(), t)).toBeNull();
  });
});
