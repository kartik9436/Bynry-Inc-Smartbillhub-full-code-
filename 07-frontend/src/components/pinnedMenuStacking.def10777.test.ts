// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-10777 — a row's More actions menu opened UNDER the next row's
//           pinned Actions cell (position: sticky makes each cell a stacking
//           context), so a click on Reverse landed on the row below.
// Proof in a browser: elementFromPoint at the menu item's centre returns the
// item, not the next row's cell (lane FINAL-WALK-2 walk, Payments list 4103).
// jsdom paints nothing, so this pins the class that lifts the cell.
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { PINNED_ACTIONS_CELL } from "./DataTable";

describe("DEF-SHL-10777 · the pinned cell holding an open menu is lifted", () => {
  it("raises its stacking only while a menu in it is open", () => {
    expect(PINNED_ACTIONS_CELL.split(" ")).toContain("[&:has(details[open])]:z-10");
    // and carries no z-index otherwise
    expect(PINNED_ACTIONS_CELL.split(" ").filter((c) => /(^|:)z-/.test(c))).toEqual([
      "[&:has(details[open])]:z-10",
    ]);
  });
});
