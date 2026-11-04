/**
 * Phone or tablet, decided by width (AD-12: *"Tablet — The drawer becomes a
 * permanent sidebar and the list sits beside its detail"*; FF-09 T: *"It is
 * the 220px column on the left, always there"*).
 *
 * The test is the SHORTER side of the window at 600 — Android's own
 * "smallest width 600dp" tablet line — so a phone turned on its side (844 ×
 * 390) stays a phone and a tablet held upright (768 × 1024) stays a tablet.
 * Turning a handset over must not move its whole navigation. Our judgment,
 * recorded here; the design names 220px and draws tablets at 1024 × 768.
 */
export const SIDEBAR_WIDTH = 220;

export const TABLET_MIN_SHORT_SIDE = 600;

export function isTabletSize(width: number, height: number): boolean {
  return Math.min(width, height) >= TABLET_MIN_SHORT_SIDE;
}
