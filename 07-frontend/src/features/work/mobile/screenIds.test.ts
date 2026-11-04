import { describe, expect, it } from "vitest";

import { MOBILE_ROUTE_PATHS } from "./routePaths";
import { MOBILE_SCREENS } from "./screenIds";

describe("the phone's own screen register", () => {
  it("names exactly the routes MobileApp mounts — no more, no fewer", () => {
    // The staff map is trusted because it mirrors App.tsx row for row; this is
    // the same property for the phone. A route mounted with no badge is a screen
    // a bug report cannot name (CR-016 addendum); a badge with no route is a
    // register entry that outlived its screen (DEF-524's shape).
    expect(MOBILE_SCREENS.map((s) => s.path)).toEqual([...MOBILE_ROUTE_PATHS]);
  });

  it("uses only badges minted in g29_allocated_badges.txt", () => {
    for (const screen of MOBILE_SCREENS) {
      // ⚠ WIDENED TO WRK-23 BY WAVE K (2026-09-05), IN THE COMMIT THAT MINTED
      // IT in `10-scripts/gates/g29_allocated_badges.txt`. The pattern is
      // deliberately narrow rather than `/^WRK-\d+$/`: a typo'd badge that
      // still matched the shape would put an id on screen that no register
      // explains, and a bug report naming it would lead nowhere (`DEF-524`'s
      // shape — a reference that outlived the thing it named).
      // DEF-WRK-9583 (2026-10-04): the field app's sign-in IS the staff sign-in
      // (S3) mounted with the `mobile` surface, so it carries S3's own r10
      // badge rather than a minted one — and only that path may.
      if (screen.path === "signin") {
        expect(screen.badge).toBe("ONB-03");
        continue;
      }
      expect(screen.badge, `${screen.path} carries an unminted badge`).toMatch(/^WRK-2[123]$/);
    }
  });
});
