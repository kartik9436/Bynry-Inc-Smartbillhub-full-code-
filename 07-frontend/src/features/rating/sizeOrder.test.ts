// DEF-RAT-8741 — sizes in the order of the size they name, not their spelling.
import { describe, expect, it } from "vitest";

import { compareSizeNames, sizeNumbers, sortBySize } from "./sizeOrder";

const names = (list: string[]) => sortBySize(list, (name) => name);

describe("DEF-RAT-8741 — size order", () => {
  it("puts Battery 5 kW before Battery 30 kW (the PO's screenshot)", () => {
    expect(
      names(["Battery 10 kW", "Battery 15 kW", "Battery 20 kW", "Battery 25 kW", "Battery 30 kW", "Battery 5 kW"]),
    ).toEqual(["Battery 5 kW", "Battery 10 kW", "Battery 15 kW", "Battery 20 kW", "Battery 25 kW", "Battery 30 kW"]);
  });

  it("reads fractions and vulgar halves on water sizes", () => {
    expect(
      names(['Water 1"', 'Water 1½"', 'Water 2"', 'Water 3"', 'Water 3/4"', 'Water 4"', 'Water 5"', 'Water 5/8"', 'Water 6"']),
    ).toEqual(['Water 5/8"', 'Water 3/4"', 'Water 1"', 'Water 1½"', 'Water 2"', 'Water 3"', 'Water 4"', 'Water 5"', 'Water 6"']);
  });

  it("compares every number in turn, and reads thousands separators", () => {
    expect(names(["Electric 3φ 200A", "Electric 1φ 400A", "Electric 1φ 100A", "Electric CT-metered"])).toEqual([
      "Electric 1φ 100A",
      "Electric 1φ 400A",
      "Electric 3φ 200A",
      "Electric CT-metered",
    ]);
    expect(sizeNumbers("Broadband 1,000 Mbps")).toEqual([1000]);
    expect(compareSizeNames("Broadband 500 Mbps", "Broadband 1,000 Mbps")).toBeLessThan(0);
  });

  it("keeps un-numbered names in the order they arrived", () => {
    expect(names(["Two-unit home", "Apartment building", "Single-family home"])).toEqual([
      "Two-unit home",
      "Apartment building",
      "Single-family home",
    ]);
  });
});
