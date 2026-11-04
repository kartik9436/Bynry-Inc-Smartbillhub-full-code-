/* ══════════════════════════════════════════════════════════════════════════
 * THE DAY ONE OF THE TEN LANDS, THIS GOES RED AND NAMES WHAT TO RELEASE.
 *
 * ── Trace ────────────────────────────────────────────────────────────────
 * Defect:  DEF-CWP-3988 — ten screens the drawing describes have no address
 *          in the product; three are already pointed at by LIVE controls, and
 *          "when any of the ten lands, somebody must go and release the
 *          control pointing at it — the exact fault DEF-CWP-3925 cost a week."
 * Rules:   CLAUDE.md hard-won law 2, mirror clause · CR-068 R3
 *
 * ⚠ **WHY THIS IS NOT `G103` AGAIN.** `G103` is keyed by a hold's i18n REASON
 * key, so it can only see a screen something REFUSES to open. Seven of these
 * ten have no control pointing at them at all — no refusal, no reason key, no
 * row it could hold. This file is keyed by the SCREEN, so an absence is a row
 * rather than a silence.
 *
 * ⚠ **AND IT IS THE ONLY PLACE THE THREE MECHANISMS MEET.** The three
 * live-controlled screens are covered by a Python gate reading `holds.ts`, a
 * Django test reading `ERRAND_HELD_UNTIL`, and a vitest case reading
 * `messagesRoute()`. Each is sound; none knows about the other two; and so
 * "are all three covered" was a question nobody could answer without reading
 * three codebases. It is one assertion now.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

import { PORTAL_HOLDS } from "./holds";
import { PORTAL_SCREENS } from "./screenIds";
import { DRAWN_BUT_UNBUILT, UNPOINTED_COUNT } from "./unbuiltScreens";

const registered = new Set(PORTAL_SCREENS.map((s) => s.id));

describe("the drawn-but-unbuilt screens (DEF-CWP-3988)", () => {
  it("is the nine left of the ten the audit counted — a register that emptied itself would pass by accident", () => {
    // The guard on the guard. Every assertion below is over this list, so a
    // truncated or mis-parsed register makes them all vacuously true.
    // ⚠ TEN UNTIL 2026-10-17 — `CWP-035` landed (`DEF-CWP-10175`) and its
    // row left in the same commit, which is the release this file exists for.
    expect(DRAWN_BUT_UNBUILT).toHaveLength(9);
    expect(new Set(DRAWN_BUT_UNBUILT.map((s) => s.id)).size).toBe(9);
  });

  it("⚠ FIRES THE DAY A SCREEN LANDS, and names the control to release", () => {
    // This is the whole file. When one of the ten gains a row in
    // PORTAL_SCREENS, this goes red and prints the pointer — so the second
    // act (releasing the control) cannot be forgotten the way it was on the
    // front page, the requests hub, the bills list and Settings in one week.
    const landed = DRAWN_BUT_UNBUILT.filter((s) => registered.has(s.id)).map(
      (s) => `${s.id} (${s.drawnAs}) — RELEASE: [${s.pointer.kind}] ${s.pointer.note}`,
    );
    expect(
      landed,
      "these screens are now BUILT and are still listed as unbuilt. Go and " +
        "release whatever points at them, then delete their rows from " +
        "unbuiltScreens.ts. A hold with no test that fires when it expires is " +
        "a promise nobody is keeping.",
    ).toEqual([]);
  });

  it("a `hold` pointer names a real row in PORTAL_HOLDS, of kind screen, for THIS screen", () => {
    // The two registers cannot drift apart: a pointer naming a reason key that
    // holds.ts does not carry, or carries for a different screen, is a
    // citation that looks checked and is not.
    for (const screen of DRAWN_BUT_UNBUILT) {
      if (screen.pointer.kind !== "hold") continue;
      const row = PORTAL_HOLDS[screen.pointer.reasonKey];
      expect(row, `${screen.id} names ${screen.pointer.reasonKey}, absent from PORTAL_HOLDS`).toBeDefined();
      expect(row.kind).toBe("screen");
      expect(row.kind === "screen" ? row.screen : null).toBe(screen.id);
    }
  });

  it("and it runs the other way — every `screen` hold is a screen this register knows", () => {
    // The half that keeps this file from silently stopping covering the holds.
    // A lane adding a hold on an unbuilt screen has to add a row here too.
    const known = new Set(DRAWN_BUT_UNBUILT.map((s) => s.id));
    const orphans = Object.entries(PORTAL_HOLDS)
      .filter(([, v]) => v.kind === "screen")
      .map(([k, v]) => [k, (v as { screen: string }).screen] as const)
      .filter(([, screenId]) => !known.has(screenId))
      .map(([key, screenId]) => `${key} holds on ${screenId}, which unbuiltScreens.ts does not list`);
    expect(orphans).toEqual([]);
  });

  it("nothing in this register is already served — it would be a lie about the product", () => {
    // Distinct from the expiry case above: that one is about the day it
    // CHANGES, this one is about the register being true when it was written.
    for (const screen of DRAWN_BUT_UNBUILT) {
      expect(registered.has(screen.id), `${screen.id} IS registered`).toBe(false);
    }
  });

  it("counts the promises nobody is keeping, so the number can only fall on purpose", () => {
    // ⚠ NOT A TARGET AND NOT A FAILURE. Seven of the ten have no control
    // pointing at them, so no check anywhere can notice the day they land.
    // That is the residual risk DEF-CWP-3988 asks to be read for, and it is
    // asserted rather than described so that changing it is a deliberate act.
    expect(UNPOINTED_COUNT).toBe(7);
  });

  it("the three that ARE pointed at are covered, each by a named mechanism", () => {
    // DEF-CWP-3988's own words: "THREE ARE ALREADY POINTED AT BY LIVE CONTROLS
    // — Messages in the header, the three held Start cards on the requests
    // screen, and the Send a reading action the readings screen does not
    // draw." This is that sentence, as an assertion.
    const covered = Object.fromEntries(
      DRAWN_BUT_UNBUILT.filter((s) => s.pointer.kind !== "none").map((s) => [s.id, s.pointer.kind]),
    );
    expect(covered).toEqual({
      // `CWP-035` stood here as `hold` until it landed 2026-10-17.
      "CWP-048": "server", // ERRAND_HELD_UNTIL → test_cwp_holds_expire.py
      "CWP-053": "self-releasing", // messagesRoute() → PortalShell.test.tsx
    });
  });
});
