// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3 (PO 2026-08-23) — Routes & Cycles, the screens wave.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §2, §3, §4
// Story:   US-MET-006  Screens: S8 · SET-05 · SET-05.cycles · SET-06D · SET-07D
// Rules:   the pre-CR PO ruling (three fields about time, eight one-word
//          frequencies) · D9 (bill day + due days are CYCLE DEFAULTS the run may
//          override) · D11 (walking order is PER PREMISES) · D13 (a cycle is
//          DERIVED at bill-run time; no account-level assignment) ·
//          BR-MET-078 (no money on this surface)
// ───────────────────────────────────────────────────────
/**
 * The pure half of the RC-W3 screens, driven without a browser.
 *
 * ⚠ **FOUR OF THESE CASES EXIST BECAUSE THE SCREENSHOT IS WRONG** (B17 §3).
 * The PO rebuilt the prototype and then ruled thirteen decisions, and four of
 * the rulings contradict their own drawing. A lane that matches the drawing in
 * those four places has built the wrong thing, and no gate in this repo reads a
 * drawing — so the ruling is asserted here, by name, with the case number.
 */
import { describe, expect, it } from "vitest";

import type { RouteMember } from "@/api/endpoints";

import { LEGACY_SETTINGS_TAB_PATHS } from "./SettingsPage";

import {
  CYCLE_FREQUENCY_WORDS,
  ROUTES_CYCLES_PATH,
  cycleDetailPath,
  cycleWizardPath,
  frequencyKey,
  premisesStops,
  reorderStops,
  routeDetailPath,
  routeWizardPath,
  stopSequenceOf,
  walkOrderPayload,
} from "./routesCyclesShared";

const MEMBERS: RouteMember[] = [
  // 1408 Elm — a three-unit building. D11: ONE stop, not three.
  { unit_id: "u1", unit_label: "Apt 1", premises_id: "p1", premise_no: "1408 Elm", walk_order: 1 },
  { unit_id: "u2", unit_label: "Apt 2", premises_id: "p1", premise_no: "1408 Elm", walk_order: 2 },
  { unit_id: "u3", unit_label: "Apt 3", premises_id: "p1", premise_no: "1408 Elm", walk_order: 3 },
  { unit_id: "u4", unit_label: "House", premises_id: "p2", premise_no: "22 Cedar Ct", walk_order: 4 },
  { unit_id: "u5", unit_label: "House", premises_id: "p3", premise_no: "7 Birch Ln", walk_order: null },
];

describe("B17 §2 — the frequency vocabulary is EIGHT one-word business names", () => {
  it("carries all eight, in the design's order, and no fewer", () => {
    expect(CYCLE_FREQUENCY_WORDS).toEqual([
      "Daily",
      "Weekly",
      "Fortnightly",
      "Monthly",
      "Bimonthly",
      "Quarterly",
      "Semiannual",
      "Annual",
    ]);
  });

  it('"biweekly" is NOT a word here — it means two things, which is what the vocabulary exists to prevent', () => {
    expect(CYCLE_FREQUENCY_WORDS as readonly string[]).not.toContain("Biweekly");
    expect(CYCLE_FREQUENCY_WORDS as readonly string[]).not.toContain("biweekly");
  });

  it("keys off the SERVER's capitalised business word, case-insensitively", () => {
    // `apps/metering/schedule.FREQUENCIES` serves "Monthly", not "monthly" —
    // the shipped screen keyed `…frequency.monthly` and rendered the raw key.
    expect(frequencyKey("Monthly")).toBe("settings.cycles.frequency.monthly");
    expect(frequencyKey("monthly")).toBe("settings.cycles.frequency.monthly");
    expect(frequencyKey("Fortnightly")).toBe("settings.cycles.frequency.fortnightly");
    expect(frequencyKey("Semiannual")).toBe("settings.cycles.frequency.semiannual");
  });

  it("a legacy stored value still resolves — a shipped row must not render a raw key", () => {
    expect(frequencyKey("bi_monthly")).toBe("settings.cycles.frequency.bimonthly");
    expect(frequencyKey("biweekly")).toBe("settings.cycles.frequency.fortnightly");
  });

  it("an unknown word resolves to NULL — never a guessed key and never an invented word", () => {
    expect(frequencyKey("Sporadic")).toBeNull();
    expect(frequencyKey(null)).toBeNull();
    expect(frequencyKey("")).toBeNull();
  });
});

describe("D11 — the walking order's grain is PER PREMISES, not per unit", () => {
  it("a three-unit building is ONE stop carrying its three units", () => {
    const stops = premisesStops(MEMBERS);
    expect(stops).toHaveLength(3);
    expect(stops[0].premises_id).toBe("p1");
    expect(stops[0].units).toBe(3);
    expect(stops[0].unit_ids).toEqual(["u1", "u2", "u3"]);
  });

  it("the sequence number is the STOP's position — 1, 2, 3 — never the unit's", () => {
    const stops = premisesStops(MEMBERS);
    expect(stops.map((stop) => stopSequenceOf(stops, stop))).toEqual([1, 2, 3]);
    // The superseded per-unit column ran 1..4 across those same premises; the
    // sequence a reader carries must not.
    expect(stopSequenceOf(stops, stops[1])).not.toBe(4);
  });

  it("orders by the stored per-unit walk order first, then by premise number", () => {
    const stops = premisesStops(MEMBERS);
    expect(stops.map((stop) => stop.premise_no)).toEqual([
      "1408 Elm",
      "22 Cedar Ct",
      "7 Birch Ln",
    ]);
  });

  it("a premises with no order at all still gets a stop — it is not dropped", () => {
    const stops = premisesStops([MEMBERS[4]]);
    expect(stops).toHaveLength(1);
    expect(stops[0].premise_no).toBe("7 Birch Ln");
  });
});

describe("drag-to-reorder — walk_order's first writer, as a pure move", () => {
  it("moving the last stop to the front renumbers every stop", () => {
    const stops = premisesStops(MEMBERS);
    const moved = reorderStops(stops, 2, 0);
    expect(moved.map((stop) => stop.premises_id)).toEqual(["p3", "p1", "p2"]);
    expect(walkOrderPayload(moved)).toEqual([
      { premises_id: "p3", walk_order: 1 },
      { premises_id: "p1", walk_order: 2 },
      { premises_id: "p2", walk_order: 3 },
    ]);
  });

  it("moving down keeps the intervening stop above it", () => {
    const stops = premisesStops(MEMBERS);
    expect(reorderStops(stops, 0, 2).map((stop) => stop.premises_id)).toEqual(["p2", "p3", "p1"]);
  });

  it("an out-of-range index is a NO-OP, never a dropped or duplicated stop", () => {
    const stops = premisesStops(MEMBERS);
    expect(reorderStops(stops, 0, 9)).toEqual(stops);
    expect(reorderStops(stops, -1, 0)).toEqual(stops);
    expect(reorderStops(stops, 1, 1)).toEqual(stops);
  });

  it("the payload is 1-based and dense — a route sheet has no stop zero and no gaps", () => {
    const payload = walkOrderPayload(premisesStops(MEMBERS));
    expect(payload.map((row) => row.walk_order)).toEqual([1, 2, 3]);
  });
});

describe("the addressable paths — refresh-safe, per W3-T5", () => {
  it("every screen has a URL, so a refresh mid-wizard lands where it left", () => {
    expect(ROUTES_CYCLES_PATH).toBe("/settings/reference-data/routes-cycles");
    expect(routeDetailPath("r1")).toBe("/settings/reference-data/routes-cycles/routes/r1");
    expect(cycleDetailPath("c1")).toBe("/settings/reference-data/routes-cycles/cycles/c1");
    expect(routeWizardPath(null)).toBe("/settings/reference-data/routes-cycles/routes/new");
    expect(routeWizardPath("r1")).toBe("/settings/reference-data/routes-cycles/routes/r1/edit");
    expect(cycleWizardPath(null)).toBe("/settings/reference-data/routes-cycles/cycles/new");
    expect(cycleWizardPath("c1")).toBe("/settings/reference-data/routes-cycles/cycles/c1/edit");
  });

  /**
   * ⚠ **THE LITERAL IS CHECKED AGAINST THE TAB REGISTRY, NOT IMPORTED FROM IT.**
   * `SettingsPage` imports the landing, which imports this module, so reading
   * `CONFIGURE_TAB` here would close an import cycle — the DEF-175 shape, where
   * two files in one feature folder blanked the whole S61 screen in the bundled
   * SPA while tsc, eslint and 1,223 tests all passed. A test has no such
   * constraint, so the drift guard lives here instead: the day the Configure
   * tab's segment moves, this fails and every path above moves with it.
   */
  it("the base path IS the Configure tab's own segment — the registry decides it", () => {
    expect(LEGACY_SETTINGS_TAB_PATHS["routes-cycles"]).toBe(ROUTES_CYCLES_PATH);
  });

  it("an id is URL-encoded — a path is built by ONE helper, never by concatenation", () => {
    expect(routeDetailPath("a/b")).toBe("/settings/reference-data/routes-cycles/routes/a%2Fb");
  });
});
