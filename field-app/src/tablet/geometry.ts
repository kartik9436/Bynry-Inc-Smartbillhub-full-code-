/**
 * The tablet frames' arithmetic (T-27; R121, R122). The ONE file in
 * `src/tablet/` allowed to hold a width, and every figure in it is a rule's or
 * the shell's, never a pixel read off a board.
 *
 *   R121 — *"A pane has a measured width, and content is designed to that
 *          number — not to the screen's. A 1024 tablet with a 220 px sidebar
 *          and a 300 px context pane leaves 464 px of content, and 40 of that
 *          is padding."*
 *   R122 — *"Every frame states its usable width, and a check measures
 *          against it. Sidebar + one pane is 764. Sidebar + context + content
 *          is 464. Sidebar + list + detail is 424. A fixed-width child that
 *          leaves its flexible sibling under 260 px is a broken screen, and
 *          that is arithmetic rather than judgment, so a script finds it."*
 *
 * The four frames (canvas note, *"Four frames do all 55"*):
 *   T1 — a centred column before you are signed in, no sidebar;
 *   T2 — sidebar + a 320–360 list pane + a detail pane that keeps the list
 *        visible;
 *   T3 — sidebar + a ~300 job (or route) context pane + content;
 *   T4 — sidebar + one wide pane.
 *
 * ⚠ THE BOARDS ARE DRAWN ONLY AT 1024 × 768 LANDSCAPE. Held upright, a 768
 * tablet leaves T2's detail 168 wide and T3's content 208 — R122's "broken
 * screen" by its own arithmetic. So a two-pane frame that cannot keep its
 * flexible pane at 260 COLLAPSES to one pane (the list or the detail; the
 * content without its context) rather than ship a pane nobody can use. That
 * fallback is OUR JUDGMENT — the design draws no portrait tablet — recorded
 * here and reported, not ruled.
 */
import { space } from '../tokens';
import { SIDEBAR_WIDTH } from '../navigation/layout';

export type FrameId = 'T1' | 'T2' | 'T3' | 'T4';

export const FRAME_IDS: readonly FrameId[] = ['T1', 'T2', 'T3', 'T4'];

export const GEOMETRY = {
  /** FF-09 T: *"It is the 220px column on the left, always there"* — the shell's own constant. */
  sidebar: SIDEBAR_WIDTH,
  /** T2's list pane: *"a 320–360 px list pane"* (T-27). 340 is the figure R122's 424 is computed with. */
  listPane: { min: 320, preferred: 340, max: 360 },
  /** T3's context pane: *"a 300 px context pane"* (R121). */
  contextPane: 300,
  /** The content gutter, each side: R121's *"40 of that is padding"*, on the spacing scale (space 5). */
  gutter: space[5],
  /** R122: a flexible pane under this is a broken screen. */
  minFlexible: 260,
  /**
   * T1's column. ⚠ OUR JUDGMENT: no rule names a width for the centred column;
   * the tablet sign-in board draws its card a little over half the 1024 width.
   * Rule 37 makes that an illustration, so this is the shape (a column well
   * wider than a phone and well short of the screen), not a measured fact.
   */
  centredColumn: 560,
  /** The board every T-figure is quoted at. */
  designWidth: 1024,
} as const;

/** The pane that holds still beside the flexible one. */
export type FixedPaneKind = 'list' | 'context';

export interface FrameGeometry {
  frame: FrameId;
  /** The window width this was resolved for. */
  windowWidth: number;
  /** What sits at the left edge and never moves: 220 for T2–T4, 0 for T1. */
  sidebar: number;
  /** The list or context pane, or null when the frame has none or collapsed. */
  fixed: { kind: FixedPaneKind; width: number } | null;
  /** The flexible pane's outer width. */
  flexibleOuter: number;
  /** R121's "usable": the flexible pane less its two gutters. Content is designed to THIS. */
  usable: number;
  /** True when a two-pane frame dropped its fixed pane to keep the flexible one ≥ 260. */
  collapsed: boolean;
}

/** T2's list width at a given window: the drawn proportion (340 at 1024), held to 320–360. */
export function listPaneWidth(windowWidth: number): number {
  const { min, preferred, max } = GEOMETRY.listPane;
  const scaled = Math.round((windowWidth * preferred) / GEOMETRY.designWidth);
  return Math.min(max, Math.max(min, scaled));
}

function single(frame: FrameId, windowWidth: number, sidebar: number, collapsed: boolean): FrameGeometry {
  const flexibleOuter = windowWidth - sidebar;
  return {
    frame,
    windowWidth,
    sidebar,
    fixed: null,
    flexibleOuter,
    usable: flexibleOuter - 2 * GEOMETRY.gutter,
    collapsed,
  };
}

/**
 * The frame as DRAWN — the fixed pane at its figure whatever the window — with
 * no fallback. This is what R122's check measures to find a broken frame, and
 * it is deliberately allowed to be broken.
 */
export function drawnFrame(frame: FrameId, windowWidth: number, fixedOverride?: number): FrameGeometry {
  if (frame === 'T1') {
    const column = Math.min(GEOMETRY.centredColumn, windowWidth - 2 * GEOMETRY.gutter);
    return { frame, windowWidth, sidebar: 0, fixed: null, flexibleOuter: column, usable: column, collapsed: false };
  }
  const sidebar = GEOMETRY.sidebar;
  if (frame === 'T4') return single(frame, windowWidth, sidebar, false);
  const kind: FixedPaneKind = frame === 'T2' ? 'list' : 'context';
  const width = fixedOverride ?? (frame === 'T2' ? GEOMETRY.listPane.preferred : GEOMETRY.contextPane);
  const flexibleOuter = windowWidth - sidebar - width;
  return {
    frame,
    windowWidth,
    sidebar,
    fixed: { kind, width },
    flexibleOuter,
    usable: flexibleOuter - 2 * GEOMETRY.gutter,
    collapsed: false,
  };
}

/**
 * The frame as MOUNTED at a window width: T2's list scales within 320–360, and
 * a two-pane frame whose flexible pane would fall under 260 collapses to one.
 */
export function resolveFrame(frame: FrameId, windowWidth: number): FrameGeometry {
  if (frame === 'T1' || frame === 'T4') return drawnFrame(frame, windowWidth);
  const fixed = frame === 'T2' ? listPaneWidth(windowWidth) : GEOMETRY.contextPane;
  const split = drawnFrame(frame, windowWidth, fixed);
  if (split.usable >= GEOMETRY.minFlexible) return split;
  return single(frame, windowWidth, GEOMETRY.sidebar, true);
}

/**
 * A two-pane frame whose fixed pane has nothing to show yet (its slot is not
 * filled): the flexible pane takes the whole width rather than sit beside an
 * empty column. Not a collapse — the window was wide enough.
 */
export function singlePane(frame: FrameId, windowWidth: number): FrameGeometry {
  if (frame === 'T1') return drawnFrame(frame, windowWidth);
  return single(frame, windowWidth, GEOMETRY.sidebar, false);
}

/** One finding of R122's check. */
export interface BrokenPane {
  frame: FrameId;
  windowWidth: number;
  fixedWidth: number;
  usable: number;
}

/**
 * R122, as code: a fixed child that leaves its flexible sibling under 260.
 * Returns every offending geometry — an empty list is the pass. The sidebar
 * counts as a fixed child too, which is what catches a T4 or a collapsed frame
 * on a window too narrow for any pane at all.
 */
export function findBrokenPanes(geometries: readonly FrameGeometry[]): BrokenPane[] {
  return geometries
    .filter((g) => g.frame !== 'T1' && g.usable < GEOMETRY.minFlexible)
    .map((g) => ({
      frame: g.frame,
      windowWidth: g.windowWidth,
      fixedWidth: g.sidebar + (g.fixed?.width ?? 0),
      usable: g.usable,
    }));
}

/**
 * How many columns of at least 260 fit a pane (R121: *"Two columns do not fit
 * in 464"*). For the screens that lay content side by side at width — the
 * readings grid, the photo wall, before-and-after — so the column count comes
 * from the pane's measured width and never from the screen's.
 */
export function fitColumns(usable: number, gap: number, wanted: number): number {
  for (let n = Math.max(1, wanted); n > 1; n -= 1) {
    if ((usable - gap * (n - 1)) / n >= GEOMETRY.minFlexible) return n;
  }
  return 1;
}

/**
 * The windows the check runs at (T-27 brief): landscape 1024, 1194, 1366 and
 * portrait 768, 834 — the iPad, iPad Pro 11" and 12.9" families' widths.
 */
export const CHECK_WIDTHS = {
  landscape: [1024, 1194, 1366],
  portrait: [768, 834],
} as const;
