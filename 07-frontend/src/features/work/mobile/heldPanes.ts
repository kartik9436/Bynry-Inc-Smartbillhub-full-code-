// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040 (the shell) · the panes that arrive in waves K and L
// Rules:    CLAUDE.md hard-won law 2 AND ITS MIRROR (DEF-CWP-3925, 2026-09-05)
// Tests:    src/features/work/mobile/heldPanes.test.ts — the test that FIRES
//           WHEN THE HOLD EXPIRES
// ───────────────────────────────────────────────────────

/**
 * **The panes this wave does not build, and the test that goes red the day one
 * of them lands.**
 *
 * ⚠ **WHY THIS FILE EXISTS AT ALL.** Hard-won law 2's mirror, learned on
 * 2026-09-05 and one day old when this was written: the customer portal's front
 * page had **two working doors out of eight**, because five cards and three nav
 * words were all still refusing over changes that had shipped days earlier.
 * *"The mechanism is a rule with a clock in it"* — a control is held until its
 * screen lands, which is correct the day it is written and rots silently on the
 * day the screen arrives, because landing a screen and releasing the thing that
 * pointed at it are two acts and only the first feels like the work.
 *
 * **Every check passed over it**: 42 test files, 391 cases, `tsc`, every gate —
 * because each wave tested ITS OWN screen at ITS OWN address, and the question
 * *has the door started pointing at it* belonged to nobody.
 *
 * So the law's remedy is followed literally: **the hold and the test that fires
 * when the hold expires are written in the same commit**, and the hold is
 * asserted BY ADDRESS and BY THE SCREEN ID it will open — not by the greyed
 * label, which is the part that would be edited without thinking.
 *
 * `heldPanes.test.ts` asserts, for each row below, that `route` is **not** yet
 * mounted in `MOBILE_ROUTES`. The day wave K mounts `readings`, that assertion
 * fails and the failure message names the pane, its wave and this file — so the
 * lane landing the screen is TOLD to release the control rather than having to
 * remember.
 */
export type HeldPane = {
  /** Stable key. Also the i18n suffix for the label and the refusal. */
  readonly id: string;
  /** Which wave lands it. Named so the failure message can say so. */
  readonly wave: "K" | "L";
  /** The address it will occupy, relative to `/{tenant}/work/mobile/`. */
  readonly route: string;
  /** The screen it opens, in the product's own vocabulary. */
  readonly screen: string;
  /** The story that owns it — for the lane that has to go and read one. */
  readonly story: string;
};

export const HELD_PANES: readonly HeldPane[] = [
  // ⚠ WAVE K's THREE ROWS — `readings`, `photos` and `signature` — WERE
  // DELETED FROM HERE ON 2026-09-05, in the same commit that mounted their
  // routes and linked them from `JobPage`. That is the mechanism working
  // exactly as wave J designed it: `heldPanes.test.ts` went RED the moment the
  // addresses appeared in `MOBILE_ROUTE_PATHS`, and its failure message named
  // each pane, its wave, its screen and this file. Nobody had to remember.
  // ⚠ **WAVE L's ROW — `close` — WAS DELETED FROM HERE ON 2026-09-05, in the
  // same commit that mounted `jobs/:orderId/close` and linked it from
  // `JobPage`.** That is the mechanism working exactly as wave J designed it:
  // `heldPanes.test.ts` went RED the moment the address appeared in
  // `MOBILE_ROUTE_PATHS`, and its failure message named the pane, its wave, its
  // screen and this file.
  //
  // **THE LIST IS NOW EMPTY, AND EMPTY IS A STATEMENT: the phone holds nothing
  // back.** It is KEPT rather than deleted because it is the machinery, not the
  // data — a lane adding the next hold inherits the expiry test instead of
  // writing one, and writing one from scratch is precisely what nobody does
  // (`DEF-CWP-3925`).
] as const;

/**
 * The refusal a held control shows.
 *
 * ⚠ **FIVE OR SIX WORDS, B14 rule 33**, and it names no wave, no story and no
 * rule id — B14 rule 32 keeps internal codes out of copy a technician reads.
 * *"Arrives in the next release."* is five words; the catalogue owns the string
 * and this only names the key.
 */
export const HELD_PANE_REFUSAL_KEY = "work.mobile.pane.held";
