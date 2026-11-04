// ── Trace ──────────────────────────────────────────────
// Change:  SET-10's five document shapes (PO 2026-09-07) — the class vocabulary
//          the three NEW shapes needed: a phone-width bubble, an inbox header,
//          a signature block and an in-app banner over a sketch of its screen.
// Rules:   B14 rule 21 (new UI is Tailwind utilities and adds NO class to a
//          stylesheet; this file is on `route-b-migrated.txt`)
// ───────────────────────────────────────────────────────
/**
 * THE CLASSES `templateSurfaces.tsx` DRAWS ITS THREE NEW SHAPES WITH.
 *
 * ⚠ **WHY THIS IS A `Kit.ts` FILE AND NOT FOUR CONSTANTS IN THE COMPONENT,
 * WHICH IS WHERE THEY STARTED.** `src/styles/routeBUtilities.test.ts` is the
 * only check in this repo that can answer whether a Tailwind utility is REAL —
 * it loads the actual compiler and asks it — and it reads class names from two
 * places: a `className="…"` literal, and a module-level constant **in a file
 * whose name ends `Kit.ts`**. A component that keeps its classes in constants
 * and writes `className={CONSTANT}` is in neither.
 *
 * That was measured rather than assumed: with these constants living in
 * `templateSurfaces.tsx`, `bg-red-500` was planted in one of them — a class
 * this theme deliberately deletes, so it renders NOTHING — and all ten tests
 * passed. `tsc` passes too, and so would any `toHaveClass` assertion, because
 * the class IS in the DOM. That is B14 rule 21's exact failure mode
 * (`DEF-974`), reachable from a file that had just been added to the ledger to
 * prevent it.
 *
 * Moving them here puts them where the compiler already looks. It is the
 * repo's own convention doing the work rather than a new check — and the
 * general hole is filed as `DEF-SHL-4477` rather than papered over here,
 * because every other component that declares its own class constants is still
 * in it and this file's move fixes only itself.
 */

import { SMS_METER } from "./notificationsKit";

/* ── the vocabulary ─────────────────────────────────────────────────────────
   B14 rule 21: this file is on `07-frontend/src/styles/route-b-migrated.txt`,
   so every token below is compiled by Tailwind and checked by
   `src/styles/routeBUtilities.test.ts` — which asks the REAL compiler, so a
   typo'd utility fails there rather than rendering as nothing on screen.
   ⚠ They are declared here rather than in `notificationsKit.ts` deliberately:
   that file was being edited by another lane in the same hours this one was
   written, and a shared-file write for four constants is the mechanism-two
   revert hard-won law 11 records. Move them across when the file is quiet. */

/** A TEXT MESSAGE, at the width a handset actually gives it.
 *
 *  ⚠ **190px AND NOT `SMS_BUBBLE`'s 352px, AND THE DIFFERENCE IS THE POINT.**
 *  The shared bubble is `max-w-[22rem]`, which is wider than a phone's text
 *  column and lets a 160-character body sit on three comfortable lines. A
 *  clerk reading that has no way to see that the same words wrap to six lines
 *  on the phone it is going to. The design asks for a phone, so this is a
 *  phone: the bubble is the message's real measure and the count underneath
 *  says what it costs. */
export const SMS_PHONE_BUBBLE =
  "mx-0 my-2 w-full max-w-[190px] whitespace-pre-wrap break-words " +
  "border border-divider bg-surface p-3 text-base leading-body";
/** The count under the bubble, at the bubble's own width so the two read as one
 *  object rather than as a message and an unrelated statistic. */
export const SMS_PHONE_METER = "w-full max-w-[190px] " + SMS_METER;

/** The inbox's own header — who it is from and who it is going to, under the
 *  subject. `INBOX_LINES` already draws the rule beneath the block. */
export const INBOX_META = "flex flex-col gap-0.5 text-sm";
/** One `From:` / `To:` line. The label is fixed-width so the two values line up
 *  the way an inbox lines them up. */
export const INBOX_META_ROW = "flex min-w-0 items-baseline gap-2";
export const INBOX_META_LABEL = "flex-none font-semibold";
export const INBOX_META_VALUE = "min-w-0 truncate";

/** The sketch of the screen an in-app message appears ON. Deliberately faint
 *  and deliberately contentless: it exists to give the banner a SCALE, and a
 *  sketch carrying real words would be a second document on the page. */
export const APP_SKETCH =
  "mx-0 my-2 w-full border border-divider bg-neutral-100 p-3";
export const APP_SKETCH_BAR = "h-3 w-full bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)]";
export const APP_SKETCH_BAR_SHORT = "h-3 w-1/3 bg-[color-mix(in_srgb,var(--color-text)_16%,transparent)]";
export const APP_SKETCH_ROWS = "flex flex-col gap-2";
/** The banner itself, drawn over the sketch at the width it really occupies. */
export const APP_BANNER =
  "w-full whitespace-pre-wrap border-l-2 border-l-accent bg-surface p-3 " +
  "text-base leading-body shadow-sm";
/** Who reads this one. ONE sentence — B14 rule 32's description budget. */
export const APP_AUDIENCE = "m-0 mt-2 text-sm";

/** The signature block: a rule to sign on, the sample sitting on it, and the
 *  author's OWN label underneath. */
export const SIGN_BLOCK = "mt-6 flex flex-wrap items-end gap-x-10 gap-y-6";
export const SIGN_FIELD = "flex min-w-[12rem] flex-1 flex-col";
export const SIGN_INK = "min-h-6 pb-1";
export const SIGN_RULE = "h-px w-full bg-text";
export const SIGN_LABEL = "mt-1 text-sm";

