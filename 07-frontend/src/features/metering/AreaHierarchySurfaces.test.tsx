// ── Trace ──────────────────────────────────────────────
// Change:  CR-039 wave E task 22 — "seed sub-areas"
//          PO 2026-08-26: *"Why you dont have sub areas below - Areas metering
//          4 North district · Downtown · East district · Industrial corridor"*
// Rules:   BR-MET-066c (three sub-areas ARE seeded; two districts deliberately
//          have none) · BR-MET-066b (depth exactly two — unchanged) ·
//          BR-MET-072 / BR-MET-138 (a district covers its sub-areas, and S14
//          can finally be filtered by one)
// Defects: DEF-836 (S14 had no area filter; the check that was supposed to
//          prove DEF-220 closed passed vacuously against it)
// Screens: S14 (premises list — the Area filter) · S8 (Areas & sub-areas card)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **A PICKER THAT FLATTENS A TREE SILENTLY IS HOW SOMEBODY FILTERS — OR
 * TAGS — THE WRONG DISTRICT.** Until fixture V2.48.0.1 every tenant had four
 * flat areas, so a filter that dropped the hierarchy on the floor was
 * indistinguishable from one that honoured it and nothing in the suite could
 * tell the difference. These assertions are about what the CONTROLS SHOW, and
 * each one is written so that flattening the tree makes it RED.
 */
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LookupEntry } from "@/api/endpoints";

import { subAreaCountText } from "../tenancy/SettingsReferenceData";
import { areaFilterOptions } from "./meteringShared";
import { premisesTableConfig } from "./PremisesListPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function area(code: string, name: string, over: Partial<LookupEntry> = {}): LookupEntry {
  return {
    id: `a-${code}`,
    code,
    name,
    active: true,
    is_system: true,
    used_by: 0,
    parent_code: null,
    parent_name: null,
    is_sub_area: false,
    sub_area_count: 0,
    ...over,
  };
}

function subArea(code: string, name: string, parent: LookupEntry): LookupEntry {
  return area(code, name, {
    parent_code: parent.code,
    parent_name: parent.name,
    is_sub_area: true,
  });
}

// The SEEDED estate exactly as fixture V2.48.0.1 delivers it — four districts,
// three sub-areas, two districts deliberately childless (BR-MET-066c).
const NORTH = area("NORTH", "North district", { sub_area_count: 2 });
const DTWN = area("DTWN", "Downtown");
const EAST = area("EAST", "East district", { sub_area_count: 1 });
const IND = area("IND", "Industrial corridor");
const NORTH_NE = subArea("NORTH-NE", "NE", NORTH);
const NORTH_NW = subArea("NORTH-NW", "NW", NORTH);
const EAST_SE = subArea("EAST-SE", "SE", EAST);
const RETIRED = subArea("NORTH-OLD", "Old quarter", NORTH);
RETIRED.active = false;

const SEEDED: LookupEntry[] = [NORTH, NORTH_NE, NORTH_NW, DTWN, EAST, EAST_SE, IND];

describe("BR-MET-138 — the S14 Area filter shows the tree, not a flat list", () => {
  it("labels every sub-area with its parent, in the server's own path form", () => {
    // The filter panel takes `{value,label}[]` and cannot indent, so the
    // hierarchy has to live in the LABEL — and the label it lives in is the one
    // the server already publishes for every tagged premises (`area_path`).
    // A bare "NE" in a list beside "North district" and "East district" tells a
    // person nothing about which district it belongs to.
    expect(areaFilterOptions(SEEDED)).toEqual([
      { value: "NORTH", label: "North district" },
      { value: "NORTH-NE", label: "North district · NE" },
      { value: "NORTH-NW", label: "North district · NW" },
      { value: "DTWN", label: "Downtown" },
      { value: "EAST", label: "East district" },
      { value: "EAST-SE", label: "East district · SE" },
      { value: "IND", label: "Industrial corridor" },
    ]);
  });

  it("puts each sub-area immediately under its own parent", () => {
    // Order is the other half of not-flattening. Sorted by code alone,
    // `EAST-SE` lands between `EAST` and `IND` only by accident of spelling,
    // and one renamed code scatters the tree.
    const codes = areaFilterOptions(SEEDED).map((option) => option.value);
    expect(codes.indexOf("NORTH-NE")).toBe(codes.indexOf("NORTH") + 1);
    expect(codes.indexOf("EAST-SE")).toBe(codes.indexOf("EAST") + 1);
  });

  it("never offers a deactivated sub-area", () => {
    // BR-TEN-034 — a retired district stops appearing on new work while the
    // premises already tagged to it keep their tag.
    const codes = areaFilterOptions([...SEEDED, RETIRED]).map((o) => o.value);
    expect(codes).not.toContain("NORTH-OLD");
  });

  it("is EMPTY for a tenant with no areas, so no dead control is declared", () => {
    expect(areaFilterOptions([])).toEqual([]);
  });
});

describe("DEF-836 — the filter is DECLARED on the list, or it does nothing", () => {
  const cells = {
    premiseNo: () => <span />,
    address: () => <span />,
    type: () => <span />,
    services: () => <span />,
    owner: () => <span />,
    // CR-089 `DEF-4740` — the ninth column joined `premisesTableConfig`'s
    // cells contract on 2026-09-10; this file stubs every cell and cares
    // about none of them.
    onTheMap: () => <span />,
    status: () => <span />,
    actions: () => <span />,
  };

  it("declares `area` as an f.<name> filter the server will honour", () => {
    // Hard-won law 2 in its exact shape: `_area_predicate` existed, BR-MET-072
    // was ruled, and S14's config named `type` and `status` — so the screen
    // could not ask, `parse_list_params` dropped the name it never asked with,
    // and every area chip returned the whole tenant.
    const config = premisesTableConfig(t, [], areaFilterOptions(SEEDED), cells);
    const names = (config.filters ?? []).map((filter) => filter.name);
    expect(names).toContain("area");
    const areaFilter = (config.filters ?? []).find((f) => f.name === "area");
    expect(areaFilter?.options.map((o) => o.label)).toContain("North district · NW");
  });

  it("declares NO area filter when the tenant has no areas", () => {
    // A filter group with no options is a control that opens onto nothing.
    const config = premisesTableConfig(t, [], [], cells);
    const names = (config.filters ?? []).map((filter) => filter.name);
    expect(names).not.toContain("area");
  });
});

describe("BR-MET-066c — the S8 card counts its sub-areas again", () => {
  it("shows the count on a district that HAS sub-areas", () => {
    // r10 SET-04's own card text. CR-010 stripped these counts out of the
    // seeded NAMES because they *"claimed sub-areas no tenant has"*; the rows
    // exist now, so the count is a computed fact rather than an assertion.
    expect(subAreaCountText(NORTH, t)).toBe("2 sub-areas");
    expect(subAreaCountText(EAST, t)).toBe("1 sub-area");
  });

  it("shows NOTHING on a district that has none", () => {
    // Downtown and Industrial corridor are childless on purpose (BR-MET-066c),
    // and "· 0 sub-areas" is noise on every row of every flat list.
    expect(subAreaCountText(DTWN, t)).toBe("");
    expect(subAreaCountText(IND, t)).toBe("");
  });

  it("shows NOTHING on a sub-area, because there is no third level", () => {
    // Depth is exactly two (BR-MET-066b). "NE · 0 sub-areas" would advertise a
    // level the product refuses to create.
    expect(subAreaCountText(NORTH_NE, t)).toBe("");
  });

  it("shows NOTHING for a list that publishes no count at all", () => {
    // Every OTHER hosted list is flat and sends no `sub_area_count`; absent is
    // "this list has no levels", which is not the same fact as zero.
    const flat = area("W-58", 'Water 5/8"');
    delete flat.sub_area_count;
    expect(subAreaCountText(flat, t)).toBe("");
  });
});
