/**
 * `CR-171-BRC10` P1.03 — a seven-step move-in draft resumes in the four-step
 * wizard on the CR's map, every value kept; and the HOLD on wiring it.
 *
 * ⚠ **THE LAST CASE IS A HOLD-EXPIRY TEST (CLAUDE.md law 2).** Today
 * `MOVE_IN_STEPS` is the seven-step list (it drives the live wizard), so the
 * map must NOT be wired — a seven-step resume through it would land a clerk on
 * the wrong body. The day the list is four (P2.15, lane WIZ), the same case
 * demands the map IS wired, and goes red until it is.
 */
import { describe, expect, it } from "vitest";

import {
  MOVE_IN_SEVEN_STEP_TO_FOUR,
  MOVE_IN_STEPS,
  MOVE_IN_STEP_SHAPE_FOUR,
  MOVE_IN_STEP_SHAPE_KEY,
  moveInStoredStep,
} from "./moveShared";
import { WIZARD_PARK_FLOW_SURFACE } from "./parkedDrafts";

describe("moveInStoredStep — the seven-step draft in four steps", () => {
  it.each([
    [1, 1],
    [2, 1],
    [3, 2],
    [4, 1],
    [5, 3],
    [6, 3],
    [7, 4],
  ])("old step %i opens on step %i", (stored, expected) => {
    const values = { customer: { full_name: "kept" }, deposit: { amount: "150.00" } };
    expect(moveInStoredStep(stored, { subject_ref: {}, values })).toBe(expected);
    expect(values).toEqual({ customer: { full_name: "kept" }, deposit: { amount: "150.00" } });
  });

  it("never remaps a draft the four-step form wrote", () => {
    expect(
      moveInStoredStep(2, { values: { [MOVE_IN_STEP_SHAPE_KEY]: MOVE_IN_STEP_SHAPE_FOUR } }),
    ).toBe(2);
    expect(moveInStoredStep(3, { subject_ref: { service_request_id: "r-1" } })).toBe(3);
  });

  it("is the server's map, key for key", () => {
    // `move_reads.MOVE_IN_SEVEN_STEP_TO_FOUR` — the Python suite pins the same.
    expect(MOVE_IN_SEVEN_STEP_TO_FOUR).toEqual({ 1: 1, 2: 1, 3: 2, 4: 1, 5: 3, 6: 3, 7: 4 });
  });

  it("HOLD: wired exactly when the declared list is four steps", () => {
    const wired = WIZARD_PARK_FLOW_SURFACE.move_in.storedStep;
    if (MOVE_IN_STEPS.length === 4) {
      expect(wired).toBe(moveInStoredStep);
    } else {
      expect(MOVE_IN_STEPS.length).toBe(7);
      expect(wired).toBeUndefined();
    }
  });
});
