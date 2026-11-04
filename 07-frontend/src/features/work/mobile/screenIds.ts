// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040/041/042/043 — the phone's own screens
// Rules:    CR-016 addendum (PO 2026-08-19: *"assign tags that are visible on
//           screen … as per modules how we are using in r10"*) · B14 rule 31
// Tests:    src/features/work/mobile/screenIds.test.ts
// Impacts:  10-scripts/gates/g29_allocated_badges.txt (WRK-21, WRK-22) ·
//           src/routing/screenIds.ts (ONE row: `noScreen: "own-register"`)
// ───────────────────────────────────────────────────────

/**
 * The field app's own screen register — the shape the customer portal
 * established (`src/portal/routing/screenIds.ts`).
 *
 * ⚠ **WHY A SECOND REGISTER RATHER THAN THREE MORE ROWS IN THE STAFF MAP.**
 * `src/routing/screenIds.ts` is asserted to mirror `App.tsx` **row for row, in
 * order** — that is what makes it trustworthy. The phone's three routes are
 * mounted INSIDE `MobileApp`, so they are invisible there, and adding them
 * would break the one property the staff map has. The staff map therefore
 * carries a single `noScreen: "own-register"` row for `/{tenant}/work/mobile/*`
 * and this file carries the screens.
 *
 * ⚠ **THE BADGES ARE MINTED, NOT BORROWED.** r10 draws `WRK-01`…`WRK-18` for
 * the DESKTOP dispatcher and does not draw the phone at all — the execution
 * plan says so for wave J in its own words: *"the pack does not draw the
 * phone"*. So `WRK-21` and `WRK-22` are allocated in
 * `10-scripts/gates/g29_allocated_badges.txt`, the way `WRK-19` (templates) and
 * `WRK-20` (the approval queue) were. A1 allocates nothing: its reserved
 * S61–S90 band is exhausted, which is REPORTED and not invented.
 */
export type MobileScreen = {
  /** Relative to `/{tenant}/work/mobile`. `""` is the index. */
  readonly path: string;
  /** The visible badge. */
  readonly badge: string;
  /** The product's own name for the screen. */
  readonly screen: string;
};

export const MOBILE_SCREENS: readonly MobileScreen[] = [
  { path: "", badge: "WRK-21", screen: "Work-010" },
  // Week is the SAME screen over a longer horizon (`US-WRK-040` TC-7), so it
  // carries the same badge: one sort, two windows. A second badge would invite
  // a second component and a second opinion about `BR-WRK-035`.
  { path: "week", badge: "WRK-21", screen: "Work-010" },
  { path: "jobs/:orderId", badge: "WRK-22", screen: "Work-011" },
  // ── CR-070 wave K — the three panes a technician fills in ──────────────
  // ⚠ ONE BADGE ACROSS THREE ROUTES, the same argument `week` makes above:
  // they are one screen in the product's vocabulary (`Work-012`), shown a pane
  // at a time because a phone has room for one. Three badges would invite three
  // screens and three opinions about when a job may close — which is exactly
  // the second-opinion problem `close_readiness()` is written to prevent.
  // ⚠ AND THE ORDER MATTERS: `screenIds.test.ts` compares this list to
  // `MOBILE_ROUTE_PATHS` position by position, so these three must appear in
  // the order `MobileApp` mounts them.
  { path: "jobs/:orderId/readings", badge: "WRK-23", screen: "Work-012" },
  { path: "jobs/:orderId/photos", badge: "WRK-23", screen: "Work-012" },
  { path: "jobs/:orderId/signature", badge: "WRK-23", screen: "Work-012" },
  // ── CR-070 wave L — the close, and it is the FOURTH pane of `Work-012` ──
  // Same badge for the same reason the three above share one: the close is not
  // a screen of its own, it is the last pane of the job the technician is
  // already on. A `WRK-24` here would invite a fourth component and a fourth
  // opinion about when a job may close.
  { path: "jobs/:orderId/close", badge: "WRK-23", screen: "Work-012" },
  // DEF-WRK-9583 — the staff sign-in (S3, r10 `ONB-03`) declaring `mobile`.
  { path: "signin", badge: "ONB-03", screen: "S3" },
] as const;
