// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — the raise's pure decisions.
// Rulings:  19, 20, 25 · DEF-WRK-9582 (job type as a two-level picker).
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { assigneeFor, chooseOneUnits, dueFromPriority, jobCount, jobTypeChoices, unitsMissingAnAsset } from "./raiseModel";

const type = (id: string, name: string, parent: string | null) => ({
  id, code: id, name, parent_name: parent, default_priority_id: null,
});

describe("jobTypeChoices — DEF-WRK-9582", () => {
  it("a heading with sub-types is a group, never an option; a lone heading is an option", () => {
    const { options, groups } = jobTypeChoices([
      type("e", "Electrical Line", null),
      type("o", "Outage report", "Electrical Line"),
      type("t", "Transformer fault", "Electrical Line"),
      type("m", "Meter Change", null),
    ]);
    expect(options.map((o) => o.label)).toEqual(["Meter Change"]);
    expect(groups).toEqual([
      { label: "Electrical Line", options: [{ value: "o", label: "Outage report" }, { value: "t", label: "Transformer fault" }] },
    ]);
  });
});

describe("ruling 20 — an asset type chosen means the asset must be chosen", () => {
  const units = [{ id: "u-101", label: "Apt 101" }, { id: "u-102", label: "Apt 102" }, { id: "u-103", label: "Apt 103" }];
  const seen = [
    { id: "a-5040", unitKey: "u-101" },
    { id: "a-master", unitKey: "u-101" },
    { id: "a-5041", unitKey: "u-102" },
  ];
  const picked = (id: string, unitKey: string, unitLabel: string) => ({ id, assetNo: id, unitKey, unitLabel, where: null, lastRead: null });

  it("names a ticked unit whose assets are all unchosen; a unit with none read is not named", () => {
    expect(unitsMissingAnAsset(units, seen, [picked("a-5041", "u-102", "Apt 102")])).toEqual([units[0]]);
  });

  it("matches on the unit's label where the read names no unit id", () => {
    expect(unitsMissingAnAsset(units, [{ unitKey: "Apt 101" }], [picked("x", "Apt 101", "Apt 101")])).toEqual([]);
  });

  it("Choose one marks a unit with two assets and none ticked, and clears once one is", () => {
    expect([...chooseOneUnits(seen, [])]).toEqual(["u-101"]);
    expect([...chooseOneUnits(seen, [picked("a-5040", "u-101", "Apt 101")])]).toEqual([]);
  });

  it("one job per unit, or per asset once an asset type is chosen (ruling 19)", () => {
    expect(jobCount(false, 6, 0)).toBe(6);
    expect(jobCount(true, 6, 5)).toBe(5);
  });
});

describe("ruling 25 and the due date", () => {
  it("a technician posts technician_id; a crew or contractor posts crew_id; blank posts null", () => {
    expect(assigneeFor({ kind: "technician", id: "t1" })).toEqual({ technician_id: "t1" });
    expect(assigneeFor({ kind: "person", id: "t1" })).toEqual({ technician_id: "t1" });
    expect(assigneeFor({ kind: "crew", id: "c1" })).toEqual({ crew_id: "c1" });
    expect(assigneeFor({ kind: "contractor", id: "k1" })).toEqual({ crew_id: "k1" });
    expect(assigneeFor(null)).toBeNull();
  });

  it("the due date opens on the priority's promise: 72 h from 24 Sep 09:00 is 27 Sep", () => {
    expect(dueFromPriority(72, new Date(2026, 8, 24, 9, 0))).toBe("2026-09-27");
  });
});
