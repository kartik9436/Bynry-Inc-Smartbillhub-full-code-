// DEF-CUS-9220 — New Connection step 3 draws a service's sizes in SIZE order.
// Found by the New Connection end-to-end walk (2026-10-02): the utility's rows
// arrive sorted by name, so the dropdown read Fire line 10", 12", 2", 4"… and
// Water 1", 1½", 2", 3", 3/4", 4", 5", 5/8", 6".
import { describe, expect, it } from "vitest";

import { bySize, sizeMagnitude } from "./NewConnectUnitsStep";

const names = (rows: { name: string }[]) => rows.map((row) => row.name);
const of = (...list: string[]) => list.map((name, i) => ({ code: `C${i}`, name }));

describe("bySize (DEF-CUS-9220)", () => {
  it("orders fire lines 2, 4, 6, 8, 10, 12", () => {
    expect(
      names(bySize(of('Fire line 10"', 'Fire line 12"', 'Fire line 2"', 'Fire line 4"', 'Fire line 6"', 'Fire line 8"'))),
    ).toEqual(['Fire line 2"', 'Fire line 4"', 'Fire line 6"', 'Fire line 8"', 'Fire line 10"', 'Fire line 12"']);
  });
  it("puts water fractions where they belong", () => {
    expect(
      names(bySize(of('Water 1"', 'Water 1½"', 'Water 2"', 'Water 3"', 'Water 3/4"', 'Water 4"', 'Water 5"', 'Water 5/8"', 'Water 6"'))),
    ).toEqual(['Water 5/8"', 'Water 3/4"', 'Water 1"', 'Water 1½"', 'Water 2"', 'Water 3"', 'Water 4"', 'Water 5"', 'Water 6"']);
  });
  it("orders kW and keeps names with no number last, as served", () => {
    expect(names(bySize(of("Solar panel 10 kW", "Solar panel 1 kW", "Solar panel 2 kW")))).toEqual([
      "Solar panel 1 kW",
      "Solar panel 2 kW",
      "Solar panel 10 kW",
    ]);
    expect(names(bySize(of("Small commercial", "Apartment building", "Gas 1,000+ CFH")))).toEqual([
      "Gas 1,000+ CFH",
      "Small commercial",
      "Apartment building",
    ]);
  });
  it("reads the number a name carries", () => {
    expect(sizeMagnitude('Water 3/4"')).toBe(0.75);
    expect(sizeMagnitude('Water 1½"')).toBe(1.5);
    expect(sizeMagnitude("Gas 1,000+ CFH")).toBe(1000);
    expect(sizeMagnitude("Apartment building")).toBeNull();
  });
});
