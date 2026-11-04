// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-1085 — the reads-list column picker opens OFF THE LEFT EDGE of
//           the viewport; its "SHOW / HIDE · REORDER" heading reads as
//           "OW / HIDE" in the Product Owner's screenshot.
// Rules:    B14 rule 14 (the column selector) · hard-won law 6 (no gate in this
//           repo reads rendered output)
// ───────────────────────────────────────────────────────
// ⚠ **THIS FILE IS THE POINT OF THE FIX, NOT THE FIX.**
//
// DEF-1085 lives ONLY in rendered output: a `right-0` panel on an anchor near
// the left margin clips, and the markup is byte-identical whether it clips or
// not. jsdom has no layout, so no render assertion in this repo can see it and
// none ever will (`DEF-966` is the same sentence about the page header).
//
// So the anchoring DECISION is lifted out of the component into a pure function
// of four numbers, and THAT is checked exhaustively here. The component keeps
// only the measurement (`getBoundingClientRect`) and the class it is told to
// use. A check that cannot see the pixels can still see the reasoning, and the
// reasoning is where the bug was.
import { describe, expect, it } from "vitest";

import { resolvePanelAnchor } from "./popoverAnchor";

/** The measured live case: the reads column icon at the far left of a wrapped
 *  second toolbar row, with the 21rem (336px) panel DataTable draws. */
const READS_CLIPPED = {
  anchorLeft: 24,
  anchorRight: 56,
  panelWidth: 336,
  viewportWidth: 1280,
} as const;

describe("resolvePanelAnchor", () => {
  it("DEF-1085: flips to left-anchored when right-anchoring would clip the viewport's left edge", () => {
    const anchor = resolvePanelAnchor(READS_CLIPPED);
    // Right-anchored would put the panel's left edge at 56 - 336 = -280.
    expect(anchor.align).toBe("left");
    expect(anchor.shiftPx).toBe(0);
  });

  it("keeps the ratified right-anchoring when the panel fits to the left of the anchor", () => {
    // The unwrapped toolbar: the icon sits at the far right of a wide row.
    const anchor = resolvePanelAnchor({
      anchorLeft: 1200,
      anchorRight: 1232,
      panelWidth: 336,
      viewportWidth: 1280,
    });
    expect(anchor.align).toBe("right");
    expect(anchor.shiftPx).toBe(0);
  });

  it("does not flip into a RIGHT-edge clip — the mirrored bug", () => {
    // ⚠ **THE FIRST VERSION OF THIS TEST DID NOT BITE, AND THE MUTATION FOUND
    //    IT** (DEF-182: a check whose output cannot distinguish pass from fail
    //    is worse than none). It used a 1280px viewport with the anchor at the
    //    right, where right-anchoring FITS — so it never reached the flip at
    //    all and passed against a naive `if (!rightFits) return "left"`.
    //
    //    This is the case that actually exercises it: a 320px viewport where
    //    NEITHER side fits. Right-anchored spans [-24, 312]; left-anchored
    //    spans [280, 616] and puts three quarters of the panel off the right
    //    edge. The naive flip picks left, which is the clip mirrored rather
    //    than removed. The rule takes the side with more room and nudges the
    //    LEADING edge back in, so the heading is readable either way.
    const anchor = resolvePanelAnchor({
      anchorLeft: 280,
      anchorRight: 312,
      panelWidth: 336,
      viewportWidth: 320,
      marginPx: 8,
    });
    expect(anchor.align).toBe("right");
    expect(anchor.shiftPx).toBe(32);
  });

  it("respects the edge margin rather than sitting flush against the viewport", () => {
    // Right-anchored left edge would be 340 - 336 = 4, inside the 8px margin.
    const anchor = resolvePanelAnchor({
      anchorLeft: 308,
      anchorRight: 340,
      panelWidth: 336,
      viewportWidth: 1280,
      marginPx: 8,
    });
    expect(anchor.align).toBe("left");
  });

  it("shifts a panel wider than the space on EITHER side back inside the viewport", () => {
    // 360px viewport, 336px panel, anchor hard right: neither side fits, so the
    // panel is nudged until its left edge sits on the margin.
    const anchor = resolvePanelAnchor({
      anchorLeft: 320,
      anchorRight: 352,
      panelWidth: 336,
      viewportWidth: 360,
      marginPx: 8,
    });
    expect(anchor.align).toBe("right");
    // Right-anchored left edge = 352 - 336 = 16 … which fits (>= 8). Nothing to do.
    expect(anchor.shiftPx).toBe(0);
  });

  it("shifts when the panel cannot fit on either side of a hard-left anchor", () => {
    // 300px viewport, 336px panel: the panel is WIDER than the viewport minus
    // margins. It cannot be made to fit, so it is pinned to the left margin and
    // never to a position that hides its heading.
    const anchor = resolvePanelAnchor({
      anchorLeft: 8,
      anchorRight: 40,
      panelWidth: 336,
      viewportWidth: 300,
      marginPx: 8,
    });
    expect(anchor.align).toBe("left");
    // Left-anchored spans [8, 344]; the viewport ends at 300. It overflows the
    // RIGHT by 44, but pulling it left would hide the heading, which is the
    // whole defect. So it stays pinned at the left margin.
    expect(anchor.shiftPx).toBe(0);
  });

  it("is total: a zero-width measurement (jsdom, or a panel not yet laid out) keeps the ratified default", () => {
    const anchor = resolvePanelAnchor({
      anchorLeft: 0,
      anchorRight: 0,
      panelWidth: 0,
      viewportWidth: 0,
    });
    expect(anchor.align).toBe("right");
    expect(anchor.shiftPx).toBe(0);
  });

  it("DEF-SHL-10643: the left bound is the CONTENT column's edge when one is given, not the viewport's", () => {
    // The walk's WRK-26 case: `+ Filter` at x 313–384, a 320px panel, the
    // sidebar ending at 240. Right-anchored the panel starts at 64 — inside
    // the viewport and behind the sidebar.
    const measured = { anchorLeft: 313, anchorRight: 384, panelWidth: 320, viewportWidth: 1440 };
    expect(resolvePanelAnchor(measured).align).toBe("right");
    const anchor = resolvePanelAnchor({ ...measured, boundsLeft: 240 });
    expect(anchor.align).toBe("left");
    expect(anchor.shiftPx).toBe(0);
  });

  it("DEF-SHL-10643: a content bound that the right-anchored panel clears changes nothing", () => {
    const anchor = resolvePanelAnchor({ anchorLeft: 900, anchorRight: 971, panelWidth: 320, viewportWidth: 1440, boundsLeft: 240 });
    expect(anchor.align).toBe("right");
    expect(anchor.shiftPx).toBe(0);
  });
});
