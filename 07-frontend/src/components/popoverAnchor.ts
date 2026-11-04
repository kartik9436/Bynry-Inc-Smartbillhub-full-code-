// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-1085 — the reads-list column picker opens OFF THE LEFT EDGE of
//           the viewport. PO verbatim: *"tool bar also not correct on this
//           screen"*, with the panel's "SHOW / HIDE · REORDER" heading
//           screenshotted as *"OW / HIDE"*.
// Rules:    B14 rule 14 (▦ opens show/hide with reorder and Reset) ·
//           hard-won law 6 (no gate in this repo reads rendered output)
// Impacts:  components/DataTable.tsx — the ONE column picker every list draws.
//           Any future popover anchored to a control belongs here too.
// ───────────────────────────────────────────────────────
//
// WHERE A POPOVER OPENS, AS ARITHMETIC RATHER THAN AS A CLASS NAME.
//
// The column picker was `absolute right-0`, unconditionally. That is correct
// while the ▦ sits at the right-hand end of a wide toolbar — which it does on
// every screen a developer looks at — and it is wrong the moment the toolbar
// WRAPS and the icon lands near the left margin, because the panel then extends
// 336px to the LEFT of a control that is 24px from the edge. The panel's own
// heading is the first thing cut off, so the control a clerk would use to
// relieve the crowding is the one made unreadable by it.
//
// ⚠ **THE REASON THIS IS A MODULE AND NOT THREE LINES IN THE COMPONENT.**
// DEF-1085 exists only in rendered output, and so does DEF-966 beside it. jsdom
// has no layout: `renderToStaticMarkup` cannot tell a clipped panel from a
// placed one, every `toContain("right-0")` assertion passes in both states, and
// no gate in this repo reads pixels (hard-won law 6). So the DECISION is pulled
// out of the DOM and into a function of four numbers, where it can be checked
// exhaustively and in both directions — `popoverAnchor.test.ts` is that check.
// The component keeps only what genuinely needs a browser: one
// `getBoundingClientRect()` and the class it is handed back.
//
// ⚠ **AND THE MIRRORED CASE IS CHECKED TOO.** DEF-1085's own row notes that the
// bill detail page shows the same bug flipped — a tooltip overflowing the RIGHT
// edge. A fix that only ever flips right→left would move the clip rather than
// remove it, so `align` is chosen from BOTH sides' available room and the losing
// side is never picked merely because the winning one failed.

/** What was measured in the browser, all in viewport pixels. */
export interface PanelMeasurement {
  /** The anchor control's left edge, from `getBoundingClientRect()`. */
  anchorLeft: number;
  /** The anchor control's right edge. */
  anchorRight: number;
  /** The panel's own width. */
  panelWidth: number;
  /** `document.documentElement.clientWidth` — the layout viewport. */
  viewportWidth: number;
  /**
   * The smallest gap the panel may leave between itself and a viewport edge.
   * Defaults to 8px, which is `--space-2` and is what every other floating
   * surface in the product already clears.
   */
  marginPx?: number;
  /**
   * `DEF-SHL-10643` — the left edge of the column the panel must stay inside,
   * in viewport pixels. The VIEWPORT is not the whole story: the app frame's
   * sidebar covers its first 240px, so a panel that clears the viewport can
   * still open behind it (the `+ Filter` panel on a toolbar with no search
   * box). Absent = 0, the viewport's own edge, which is DEF-1085's case.
   */
  boundsLeft?: number;
}

/**
 * `right` — the panel's RIGHT edge meets the anchor's right edge (the ratified
 * default, and what r10 draws). `left` — the panel's LEFT edge meets the
 * anchor's left edge.
 */
export type PanelAlign = "left" | "right";

export interface PanelAnchor {
  align: PanelAlign;
  /**
   * A horizontal nudge, in px, applied AFTER alignment, for the case where the
   * chosen side still leaves the panel outside the viewport. Positive moves it
   * right. Zero on every case that fits, which is nearly all of them.
   */
  shiftPx: number;
}

const DEFAULT_MARGIN_PX = 8;

/**
 * Which side a popover should hang from, given where its anchor actually is.
 *
 * The rule, in order, and each clause exists because a case in the test file
 * fails without it:
 *
 *  1. **Prefer `right`.** It is the ratified drawing and it is right whenever
 *     the anchor is at the end of a row, which is the normal case.
 *  2. **Flip to `left` only when `right` would cross the left margin AND `left`
 *     clears the right margin.** Flipping into the opposite clip is the
 *     mirrored bug, not a fix.
 *  3. **When neither side fits, take the side with more room** and shift the
 *     panel back to the margin — but never so far that its LEADING edge goes
 *     out, because the heading is what the Product Owner could not read.
 *  4. **A degenerate measurement answers the default.** jsdom returns zeros for
 *     every rect, and a component that is measured before layout gets the same;
 *     neither is a reason to move a panel that is drawn correctly.
 */
export function resolvePanelAnchor(m: PanelMeasurement): PanelAnchor {
  const margin = m.marginPx ?? DEFAULT_MARGIN_PX;

  // (4) Nothing measurable — do not move what we cannot see.
  if (m.viewportWidth <= 0 || m.panelWidth <= 0) {
    return { align: "right", shiftPx: 0 };
  }

  // Where each alignment would put the panel.
  const rightAligned = { left: m.anchorRight - m.panelWidth, right: m.anchorRight };
  const leftAligned = { left: m.anchorLeft, right: m.anchorLeft + m.panelWidth };

  const minLeft = (m.boundsLeft ?? 0) + margin;
  const maxRight = m.viewportWidth - margin;

  const rightFits = rightAligned.left >= minLeft && rightAligned.right <= maxRight;
  const leftFits = leftAligned.left >= minLeft && leftAligned.right <= maxRight;

  // (1) The ratified default, whenever it is honest.
  if (rightFits) {
    return { align: "right", shiftPx: 0 };
  }
  // (2) Flip ONLY into a side that actually fits.
  if (leftFits) {
    return { align: "left", shiftPx: 0 };
  }

  // (3) Neither fits. Take the side with more room, then pull the panel back
  //     inside by its LEADING edge — the edge the heading is printed against.
  const roomIfRight = m.anchorRight - minLeft;
  const roomIfLeft = maxRight - m.anchorLeft;
  const align: PanelAlign = roomIfRight >= roomIfLeft ? "right" : "left";
  const placed = align === "right" ? rightAligned : leftAligned;

  // The leading edge is the LEFT edge in both alignments: text starts there.
  // Push right if it is outside; never pull left to chase the trailing edge,
  // because that is exactly the move that produced "OW / HIDE".
  const shiftPx = placed.left < minLeft ? Math.round(minLeft - placed.left) : 0;
  return { align, shiftPx };
}

/**
 * The Tailwind class that expresses an alignment.
 *
 * ⚠ Both tokens are STATIC strings and neither is built by concatenation. The
 * Tailwind compiler reads source text, so `` `${side}-0` `` compiles to nothing
 * at all and renders as no rule — DEF-974's failure mode exactly, in a file
 * (`DataTable.tsx`) that IS on `src/styles/route-b-migrated.txt` and therefore
 * relies on the compiler for every class it names.
 */
export function panelAlignClass(align: PanelAlign): string {
  return align === "left" ? "left-0" : "right-0";
}

/**
 * `DEF-SHL-10643` — where the content column starts, for `boundsLeft`: the left
 * edge of the `<main>` the anchor sits in (the app frame's view, right of the
 * sidebar), or 0 when there is none. One function so every popover measures
 * the same thing.
 */
export function contentBoundsLeft(anchor: Element): number {
  const column = anchor.closest("main");
  return column === null ? 0 : column.getBoundingClientRect().left;
}
