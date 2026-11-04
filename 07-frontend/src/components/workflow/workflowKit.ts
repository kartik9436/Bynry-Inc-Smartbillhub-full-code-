// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the reusable ETL workflow kit (PO ask, 2026-08-21:
//           "Have you create the detail on any workflow in tailwind - so that
//           we can use same elements/token again n again across platform?")
// Rules:    B14 rule 21 (new UI is Tailwind, no stylesheet class) · B14 rule 20
//           (one table type, two tiers) · B14 rule 18 (descriptions at 80%) ·
//           B14 rule 5 (two button sizes) · B14 rule 6 (danger tier on a
//           destructive commit) · BR-MET-088 · BR-MET-090 · BR-MET-091
// Impacts:  components/workflow/** only. Nothing else imports these strings.
// ───────────────────────────────────────────────────────
//
// THE WORKFLOW KIT — every utility string the ETL runner draws, written ONCE.
//
// WHY A KIT AND NOT UTILITIES IN THE MARKUP
// ─────────────────────────────────────────
// r10 draws NINE workflow kinds through one runner — premises, units, accounts,
// reads, lockbox payments, bank statements, cost inputs, rate tables, meters —
// and this product already has two import wizards that DIVERGED before the
// third arrived: `features/customers/ImportAccountsWizard.tsx` reaches into
// `met-panel-hint` and `met-facts`, which are METERING's own stylesheet classes,
// on a CUSTOMERS screen. It did that because there was no shared import
// vocabulary to reach for. This file is that vocabulary, so the tenth workflow
// costs a config object rather than a copy.
//
// ⚠ WHY THE STRINGS LIVE IN A `*Kit.ts` FILE AND NOT IN THE COMPONENTS
// ────────────────────────────────────────────────────────────────────
// `src/styles/routeBUtilities.test.ts` reads class tokens two ways, and only one
// of them can see a component API: `classTokens()` reads `className=` ATTRIBUTES
// (so `className={WF.rail}` contributes nothing at all), while `kitTokens()`
// walks every module-level constant in every file whose name ends `Kit.ts` and
// pushes each token through the REAL Tailwind compiler. `buttonKit.ts` exists
// for exactly that reason and its header records the measurement: `itmes-center`
// planted in a component kit gave "5 passed" from the Route B check and "PASS,
// 0 undeclared" from G31, with every button in the product flattened.
//
// So this file is named `workflowKit.ts` DELIBERATELY. A typo in any string
// below fails `npm test` by name. Constants here therefore hold class strings
// and NOTHING ELSE — a constant holding prose or a dotted i18n key would be read
// as a class candidate and reported as an orphan.
//
// ⚠ THE BREAKPOINT IS `max-lg:`, NOT `lg:` (G36, OQ-274). Our scale is
// desktop-first and `--breakpoint-*` is cleared and re-declared, so `max-lg:` IS
// `@media (max-width: 1024px)` and `lg:` would silently mean the other viewport.
//
// ⚠ AND THE RAIL BELOW IS BYTE-IDENTICAL TO `WizardFrame.tsx`'s `WIZ` RAIL.
// That is a KNOWN duplication of six strings, not an accident: r10 draws the ETL
// stage bar with the same `br-steps` rail the fifteen wizards use, and the
// correct end state is ONE rail kit both import. Extracting it means editing
// `WizardFrame.tsx`, which a sibling lane migrated hours ago and which this lane
// is told not to touch. Recorded in the decision log with the count so the next
// lane extracts it rather than rediscovering it.

/* ── The runner shell ─────────────────────────────────────────────────────── */

export const FRAME = "flex min-w-0 flex-col";

/** B14 rule 18 — a description caps at 80% of the content width, from the ONE
 *  `--desc-measure` token (`max-w-measure`), never a hand-picked `ch`. */
export const PROMISE =
  "mt-1 mb-4 max-w-measure text-base leading-body " +
  "text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]";

export const STAGE_HEAD = "mb-4";
export const STAGE_TITLE = "mt-2 mb-1 text-h3 font-heading font-extrabold text-text";
export const STAGE_BLURB =
  "m-0 max-w-measure text-base leading-body " +
  "text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]";

/** 04-docs/README §Interactions and US-SHL-010 say "right-aligned action row",
 *  which is what `WizardFrame` renders and what this footer matches. */
export const FOOTER = "mt-8 flex justify-end gap-2 border-t-2 border-divider pt-5";

/* ── The stage rail ───────────────────────────────────────────────────────── */

export const RAIL =
  "mb-6 flex border-y-2 border-divider " +
  "max-lg:flex-nowrap max-lg:overflow-x-auto";
export const RAIL_STEP =
  "flex flex-1 cursor-pointer items-center gap-3 border-0 border-r border-divider " +
  "bg-transparent px-5 py-4 text-left font-heading text-base font-semibold " +
  "text-text last:border-r-0 " +
  "disabled:cursor-default disabled:opacity-100 " +
  "max-lg:flex-none max-lg:whitespace-nowrap";
export const RAIL_STEP_ACTIVE = "text-accent-text";
export const RAIL_BADGE =
  "flex h-[26px] w-[26px] flex-none items-center justify-center bg-surface text-sm";
export const RAIL_BADGE_ACTIVE = "bg-accent text-on-accent";
export const RAIL_BADGE_DONE = "bg-text text-bg";

/** The stage that WRITES says so on the rail. §4's diagram marks stage 4 "⚠ THE
 *  ONLY STAGE THAT WRITES" and r10 marks it nowhere — a runner whose promise is
 *  "nothing is written until you commit at stage four" has to point at four. */
export const RAIL_WRITES =
  "ml-auto text-xs font-heading font-extrabold uppercase tracking-kicker text-danger-700";

/* ── Stage 1 · the source choices and the drop target ─────────────────────── */

export const SOURCE_GRID = "mb-4 grid grid-cols-4 gap-2 max-lg:grid-cols-2";
export const SOURCE_CARD =
  "flex cursor-pointer flex-col gap-1.5 border-t-2 border-t-divider bg-surface p-4";
export const SOURCE_CARD_SELECTED = "border-t-accent";
/** Not disabled-looking-but-clickable: the card states WHY and takes no press. */
export const SOURCE_CARD_OFF = "cursor-not-allowed opacity-60";
export const SOURCE_TITLE = "font-heading text-md font-bold text-text";
export const SOURCE_SUB =
  "text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
export const SOURCE_OFF_REASON = "text-xs font-semibold text-danger-700";
export const SOURCE_INPUT = "sr-only";

export const DROPZONE =
  "flex w-full cursor-pointer flex-col gap-2 border-2 border-dashed border-divider " +
  "bg-transparent p-9 text-center text-base text-text";
export const DROPZONE_FACTS =
  "text-xs text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]";
export const DROPZONE_HASH = "break-all font-mono text-xs";

/* ── The figure strip · three uses, one component ─────────────────────────── */

export const FIG_ROWS = "bg-surface p-3.5 text-base leading-body";
export const FIG_ROW = "flex justify-between gap-4";
export const FIG_ROW_VALUE = "font-bold tabular-nums";
/** The same slot when the value is a WORD ("Premises"), not a count — tabular
 *  figures on a word do nothing and saying so keeps the two readable. */
export const FIG_ROW_VALUE_TEXT = "font-bold";
export const FIG_TILES = "grid grid-cols-4 gap-3 text-center max-lg:grid-cols-2";
/**
 * The same strip at FIVE across — `CR-036` amendment 1 (f).
 *
 * ⚠ **THE FIFTH TILE IS THE ONLY ONE AN OPERATOR ACTUALLY NEEDS.** The stage-3
 * strip printed *"ROWS CHECKED 9881 · PASSED CLEAN 0 · ERRORS 0 · WARNINGS
 * 9881"* on a run where **every one of the 9,881 rows was going to load**, and
 * the Product Owner read it as total failure — *"it rejected and shown all
 * error"*. Four true numbers and no answer to the question being asked. `Will
 * load` is that answer, so the grid gains a column rather than the figure being
 * squeezed into a sentence under four tiles that already mislead.
 */
export const FIG_TILES_5 = "grid grid-cols-5 gap-3 text-center max-lg:grid-cols-2";
export const FIG_TILE = "bg-surface p-3.5";
/** r10 tints the exception tile rather than colouring only its number, so the
 *  count reads as flagged at a glance and not only to someone who knows the
 *  palette. `color-mix(in srgb…)` long-hand: the `/10` modifier emits OKLAB and
 *  this design system writes sRGB at 243 sites (buttonKit.ts records why). */
export const FIG_TILE_FLAGGED = "bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)] p-3.5";
export const FIG_TILE_VALUE = "mt-1 font-heading text-metric font-extrabold tabular-nums";
export const FIG_TILE_VALUE_FLAGGED =
  "mt-1 font-heading text-metric font-extrabold tabular-nums text-accent-text";
export const FIG_CAPTION = "mb-1.5 block";
/**
 * ⛔ **DEF-2439 — A `<caption>`'s OWN SPACING AND ALIGNMENT, WITHOUT `block`.**
 *
 * ⚠ **`text-left` IS NOT DECORATION.** A `<caption>` centres by default, and the
 * five reads tables that moved to this kit were left-aligned by
 * `reads.css`'s own `.rd-* caption` rule — heading family, weight 600, the same
 * 65% ink. Those four declarations are ported here value for value, which is
 * what B14 rule 21 means by a MIGRATION: the pixels do not move, only where
 * they are written.
 *
 * `FIG_CAPTION` is right on the `<div>` kickers that head the figure strips.
 * On a `<caption>` it is not: `display: block` takes the element out of the
 * table's caption box, and the browser then lays it out as an ordinary block
 * inside the table wrapper — **below the header row**. Measured in Chromium
 * 2026-08-30: caption at y=634, `thead` at y=598, on a table whose caption is
 * the FIRST child of the element.
 *
 * It has been that way on the premises, units, assets and accounts importers
 * since CR-023 and nothing could see it: `tsc` and eslint read a string, the
 * class IS in the DOM so `routeBUtilities.test.ts` compiles it happily, and
 * jsdom does no layout at all. A browser is the only reader that can tell a
 * caption above a table from a caption below its header.
 */
export const TABLE_CAPTION =
  "mb-1.5 text-left font-heading font-semibold " +
  "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/* ── Tables · B14 rule 20's two tiers come from `PlainTable`, not from here ── */

/**
 * Right-aligned numeric columns take tabular numerals so a column of counts
 * lines up (B15 §9 note 6; r10 sets `font-feature-settings:tnum` on every one).
 *
 * ⛔ **`[&&]:` IS NOT DECORATION — WITHOUT IT THESE HAVE NEVER RIGHT-ALIGNED
 * ANYTHING (DEF-2438).** `PlainTable` carries `[&_td]:text-left` and
 * `[&_th]:text-left` on the TABLE, and an arbitrary variant on the parent beats
 * a plain utility on the cell. Measured in Chromium, 2026-08-30, on the reads
 * rules table: `className: "text-right tabular-nums"`, computed
 * `text-align: left`. So every count in this kit — `HITS` on the rules table,
 * `ROW` on the reject list — has been LEFT-aligned on all six importers since
 * CR-023, under a comment promising the opposite. Hard-won law 1, and only a
 * browser could see it: the class IS in the DOM, so `routeBUtilities.test.ts`
 * compiles it, G31 passes it and every `toHaveClass` assertion is satisfied.
 *
 * `[&&]:` doubles the class selector, which raises specificity above the
 * parent's variant. It is this repo's own established idiom —
 * `features/assets/AssetLifecycleTab.tsx` already writes it on eight cells for
 * exactly this reason.
 */
export const NUM_CELL = "[&&]:text-right tabular-nums";
export const NUM_HEAD = "[&&]:text-right";
export const TABLE_WRAP = "w-full overflow-x-auto";
export const CELL_MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
export const CELL_REASON =
  "mt-1 block text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/* ── Stage 4 · the dry run, and stage 5 · the receipt ─────────────────────── */

export const NOTE_BLOCK = "bg-surface p-3 text-sm leading-body";

/** An inline control that reads as a link inside a sentence (DEF-770).
 *  It is a `<button>`, not an `<a>`: it moves the wizard between stages
 *  and navigates nowhere, so an anchor would lie to a screen reader and
 *  offer an open-in-new-tab a wizard cannot honour. */
export const LINK_INLINE =
  "cursor-pointer border-0 bg-transparent p-0 font-body text-sm text-accent-text " +
  "underline-offset-2 hover:underline";
export const NOTE_BLOCK_WARN =
  "bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body";
export const CHECK_STACK = "mt-3 flex flex-col gap-2";

export const RECEIPT_GRID = "grid grid-cols-2 gap-3.5 text-base max-lg:grid-cols-1";
export const RECEIPT_VALUE = "mt-1 break-all";
export const RECEIPT_VALUE_SMALL = "mt-1 break-all text-xs";

/** The rollback callout. Danger tint because the action it describes REVERSES
 *  writes — B14 rule 6's reasoning, applied to the sentence as well as the
 *  button. */
export const CALLOUT =
  "flex gap-3 border-l-2 border-l-danger-500 bg-danger-100 p-3 text-base leading-body " +
  "text-danger-700";
export const CALLOUT_BODY = "max-w-measure";

/**
 * Every token this kit can write, flattened — the list `workflowKit.test.ts`
 * pushes through the real Tailwind compiler, and the list
 * `routeBUtilities.test.ts` reaches independently by walking `*Kit.ts`.
 *
 * Two readers on purpose: this one names the tokens, so a token DELETED from a
 * component but left here still has to compile; the other one re-derives them
 * from the source text, so a token added to a constant and forgotten here is
 * still checked. `buttonKit.ts` publishes `BUTTON_KIT_TOKENS` for the same
 * reason.
 */
export const WORKFLOW_KIT_TOKENS: readonly string[] = [
  FRAME,
  PROMISE,
  STAGE_HEAD,
  STAGE_TITLE,
  STAGE_BLURB,
  FOOTER,
  RAIL,
  RAIL_STEP,
  RAIL_STEP_ACTIVE,
  RAIL_BADGE,
  RAIL_BADGE_ACTIVE,
  RAIL_BADGE_DONE,
  RAIL_WRITES,
  SOURCE_GRID,
  SOURCE_CARD,
  SOURCE_CARD_SELECTED,
  SOURCE_CARD_OFF,
  SOURCE_TITLE,
  SOURCE_SUB,
  SOURCE_OFF_REASON,
  SOURCE_INPUT,
  DROPZONE,
  DROPZONE_FACTS,
  DROPZONE_HASH,
  FIG_ROWS,
  FIG_ROW,
  FIG_ROW_VALUE,
  FIG_ROW_VALUE_TEXT,
  FIG_TILES,
  FIG_TILES_5,
  FIG_TILE,
  FIG_TILE_FLAGGED,
  FIG_TILE_VALUE,
  FIG_TILE_VALUE_FLAGGED,
  FIG_CAPTION,
  TABLE_CAPTION,
  NUM_CELL,
  NUM_HEAD,
  TABLE_WRAP,
  CELL_MUTED,
  CELL_REASON,
  LINK_INLINE,
  NOTE_BLOCK,
  NOTE_BLOCK_WARN,
  CHECK_STACK,
  RECEIPT_GRID,
  RECEIPT_VALUE,
  RECEIPT_VALUE_SMALL,
  CALLOUT,
  CALLOUT_BODY,
]
  .flatMap((s) => s.split(" "))
  .filter((t) => t !== "");
