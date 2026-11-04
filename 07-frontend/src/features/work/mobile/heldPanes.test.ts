// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040 — the shell, and the panes waves K and L will add
// Rules:    CLAUDE.md hard-won law 2 AND ITS MIRROR (DEF-CWP-3925, 2026-09-05):
//           *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD
//           EXPIRES, in the same commit — assert the destination by ADDRESS and
//           by the screen id it opens, so the day the screen lands the suite
//           goes red and names it."*
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { HELD_PANES } from "./heldPanes";
import { MOBILE_ROUTE_PATHS } from "./routePaths";

/**
 * **This file is the alarm on a hold, and it is written to go off.**
 *
 * On 2026-09-05 the customer portal's front page had two working doors out of
 * eight: five cards, the sign-in bar and three of four nav words were all still
 * refusing over screens that had shipped days earlier. Every check passed — 42
 * test files, 391 cases, `tsc`, every gate — because each wave tested its own
 * screen at its own address and the question *has the door started pointing at
 * it* belonged to nobody.
 *
 * So the assertion below is deliberately the opposite of the usual one. It does
 * not check that a held pane is greyed; a lane would happily edit the grey. It
 * checks **that the route is still absent**, so the moment wave K mounts
 * `jobs/:orderId/readings`, THIS test fails and its message names the pane, the
 * wave, the story and the file to edit. The lane landing the screen is told;
 * nobody has to remember.
 */
describe("the panes held for waves K and L", () => {
  it("are not mounted yet — and this test is what fires when one lands", () => {
    for (const pane of HELD_PANES) {
      expect(
        MOBILE_ROUTE_PATHS,
        `"${pane.route}" is now mounted, so wave ${pane.wave}'s ${pane.screen} has ` +
          `landed and the held control for "${pane.id}" on JobPage.tsx is stale. ` +
          `Release it: link it, and delete the row from heldPanes.ts. ` +
          `(${pane.story}; hard-won law 2's mirror, DEF-CWP-3925.)`,
      ).not.toContain(pane.route);
    }
  });

  it("each name a wave, a screen and a story, so the failure above is actionable", () => {
    // A hold whose message cannot tell the next lane what to do is the same
    // shape as the greyed card nobody released: technically present, useless.
    for (const pane of HELD_PANES) {
      expect(pane.wave, `${pane.id} names no wave`).toMatch(/^[KL]$/);
      expect(pane.screen, `${pane.id} names no screen`).toMatch(/^Work-\d+$/);
      expect(pane.story, `${pane.id} names no story`).toMatch(/^US-WRK-\d+$/);
      expect(pane.route, `${pane.id}'s route is not an address`).toContain("jobs/:orderId/");
    }
  });
});
