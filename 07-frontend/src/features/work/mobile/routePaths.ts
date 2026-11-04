// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040 — the phone shell's route table, as DATA
// Rules:    CLAUDE.md hard-won law 2's mirror — a hold is asserted by ADDRESS,
//           so the address has to be something a test can read
// Tests:    src/features/work/mobile/heldPanes.test.ts
// ───────────────────────────────────────────────────────

/**
 * Every path `MobileApp` mounts, relative to `/{tenant}/work/mobile`.
 *
 * ⚠ **IT IS A LIST BECAUSE A TEST HAS TO READ IT.** `heldPanes.test.ts` asserts
 * that wave K's and wave L's addresses are NOT in here, which is what makes the
 * hold expire loudly the day one of them is mounted. Reading the routes out of
 * the JSX would be a parse; keeping them here is a fact, and `MobileApp.tsx`
 * renders exactly these.
 *
 * ⚠ **SO ADDING A ROUTE MEANS ADDING IT HERE TOO.** A route mounted in the JSX
 * and missing from this list would leave the hold test passing over a screen
 * that had landed — the very failure this whole mechanism exists to prevent.
 * `MobileApp.test.tsx` asserts the two agree.
 */
export const MOBILE_ROUTE_PATHS: readonly string[] = [
  "",
  "week",
  "jobs/:orderId",
  // ── CR-070 wave K (2026-09-05) — what the phone sends back ────────────
  // Added in the SAME commit that mounts them in `MobileApp.tsx` and deletes
  // their rows from `HELD_PANES`. Landing a screen and releasing the control
  // that pointed at it are one act (hard-won law 2's mirror); `heldPanes.test.ts`
  // is what made that unmissable — it went red on this line and named all three.
  "jobs/:orderId/readings",
  "jobs/:orderId/photos",
  "jobs/:orderId/signature",
  // ── CR-070 wave L (2026-09-05) — the close ────────────────────────────
  // Added in the SAME commit that mounts it in `MobileApp.tsx` and deletes its
  // row from `HELD_PANES`. `heldPanes.test.ts` went red on this line and named
  // the pane, its wave, its screen and its story — nobody had to remember.
  "jobs/:orderId/close",
  // ── DEF-WRK-9583 (2026-10-04) — the field app's own sign-in door ──────
  "signin",
] as const;
