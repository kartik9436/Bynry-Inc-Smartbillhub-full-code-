// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-3984 (layout audit `D9`) — `TwoCol` was DECLARED TWICE
//           UNDER ONE NAME, once in `primitives.tsx` and once in
//           `content.tsx`, one directory apart. Third time for this shape:
//           `DEF-CWP-3655` folded `Panel` and `Chip` out of the same two
//           files, and `DEF-CWP-4003` folded `formatQuantity`.
// Rules:    B14 rule 36 (compose the kit; a missing piece is ADDED to it) ·
//           hard-won law 5 (one source, never two copies that drift)
// Cases:    no component name is exported by more than one portal kit file
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **NOTHING ELSE IN THE REPO CAN SEE THIS, AND THAT IS THE WHOLE POINT.**
// `tsc` cannot: each screen imports its own, and both are valid. eslint cannot:
// they are in different modules. A rendering check cannot: both render. The
// only place the two are ever side by side is a listing of what each file
// exports — so that is what this reads.
//
// ⚠ **IT COMPARES NAMES, NOT IMPLEMENTATIONS.** Two components that happen to
// agree today are still two components tomorrow: `Panel`'s two copies
// disagreed about whether a tone changes the border or the fill, and
// `TwoCol`'s about whether the main column is spaced — each a small divergence
// nobody chose, found only by reading both.
import { describe, expect, it } from "vitest";

import * as content from "./content";
import * as primitives from "./primitives";

/** The portal's kit, file by file. A third file joins this list, not a
 *  private copy of something already on it. */
const KIT: { name: string; module: Record<string, unknown> }[] = [
  { name: "primitives.tsx", module: primitives },
  { name: "content.tsx", module: content },
];

describe("the portal kit declares each name exactly once (DEF-CWP-3984)", () => {
  it("has no name exported by two files", () => {
    const seen = new Map<string, string>();
    const clashes: string[] = [];
    for (const file of KIT) {
      for (const name of Object.keys(file.module)) {
        const first = seen.get(name);
        if (first === undefined) {
          seen.set(name, file.name);
        } else {
          clashes.push(`${name} — declared in ${first} AND in ${file.name}`);
        }
      }
    }
    expect(
      clashes,
      "Two portal kit files export the same name. That is B14 rule 36's breach and it " +
        "is invisible to tsc, because a screen importing one cannot see the other. Fold " +
        "them: keep the one with more callers, take the behaviour that is CORRECT rather " +
        "than the one that is incumbent, and delete the name — do not redraw anything.",
    ).toEqual([]);
  });
});
