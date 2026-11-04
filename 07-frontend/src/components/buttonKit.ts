// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 3 — the SHARED classes (PO ruling 2026-08-19, "Route B")
// Rules:    B14 rule 5 (two button sizes) · B14 rule 6 (the danger tier)
// Impacts:  components/Button.tsx renders these; nothing else may.
// ───────────────────────────────────────────────────────
//
// THE BUTTON KIT AS UTILITY STRINGS — the ONE copy, transcribed declaration by
// declaration from `components/StateFrame.css` and PROVED equal to it by
// `e2e/CR-018-phase3-button-parity.spec.ts`, which renders both in the live
// bundle and diffs every computed property in rest / hover / active / disabled.
//
// It is a separate module from `Button.tsx` for ONE reason and it is not taste:
// the parity spec runs in Node and must import these strings to inject them
// into the page. `Button.tsx` imports react-router, so importing IT from a spec
// drags a router into a test that needs a string. A file that cannot be
// imported by the thing that checks it is a file nothing checks.
//
// See `Button.tsx` for why this is a component API and not `@apply`.

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  /**
   * A DESTRUCTIVE ROW ACTION — the delete/retire icon in a table cell.
   *
   * ⚠ IT IS A VARIANT AND NOT A `className`, and that is the whole point.
   * The product had this colouring three times: `.settings-danger` (text
   * only), `.met-danger` (text + border, `:not(:disabled)`) and the shared
   * `.btn-danger` tier — DEF-344. Handing it in as a class also RELIES ON
   * THE CASCADE: an unlayered stylesheet rule beats a Tailwind utility, so
   * `.settings-danger` wins over `text-accent-text` by layer order rather than by
   * anything the caller wrote. Under Route B that is a coin toss waiting to
   * be re-flipped by a build-order change. Filling the colour slot ONCE, here,
   * is the only form that cannot be re-flipped.
   *
   * It is NOT `danger`: rule 6's danger tier is an OUTLINED button that FILLS
   * on hover, for a destructive COMMIT. A row action opens a confirm dialog;
   * the commit inside that dialog is where rule 6 applies.
   */
  | "ghost-danger"
  | "link";

/**
 * ⚠ THREE SIZES SINCE 2026-08-20, AND B14 RULE 5 SAYS TWO. It was FOUR, and
 * this comment said so; the fourth is gone because the PO ruled on the thing
 * that was actually causing it.
 *
 * Rule 5 is *"two button sizes only — default and small (12px)"*, and
 * `CR-016-ui-conformance.spec.ts` enforces it as `distinctButtonFontSizes:
 * ["12px","14px"]` — FONT SIZES. Underneath that one conforming type size the
 * product rendered FOUR different button paddings, because three stylesheets
 * re-styled buttons from a PARENT selector and nothing had ever compared them:
 *
 *     .btn-sm                       6px 8px   ← the declared small tier
 *     .ast-row-actions .btn         0   8px   ← assets row actions
 *     .met-row-actions .btn         0   8px   ← metering row actions
 *     .settings-row-actions .btn    2px 6px   ← settings + templates row actions
 *
 * ⚠ THE LAST TWO WERE NEVER A DISAGREEMENT ABOUT PADDING. `0 8px` is what a
 * WORD needs in a table row and `2px 6px` is what a 16px SQUARE needs, and the
 * product had both because half its tables rendered text row actions and half
 * rendered icons. **PO ruling 2026-08-20: "Icons everywhere, per r10 and rule
 * 15"** — one content, one tier. `row` is now the icon tier, a fixed 32x32 box
 * with no padding, and `settings-row` is deleted.
 *
 * **That is DEF-342's real fix and it is why DEF-342 could not be fixed here.**
 * The defect row said the ruling was the PO's and not a migration's, and it was:
 * collapsing the two by editing padding would have moved pixels to satisfy a
 * rule whose real violation was rule 15.
 *
 * The three that remain are `default`, `sm` and `row`. `row` is a different
 * SHAPE rather than a third scale step — it is the only tier with a fixed box —
 * so whether rule 5's "two" is now satisfied is a question for the r10 pass,
 * and the guard in `buttonKit.test.ts` is ratcheted at 3 rather than asserted
 * at 2 so that the answer can be no without the suite being permanently red.
 */
export type ButtonSize = "default" | "sm" | "row";

/* ── THE UTILITY STRINGS, ONE COPY EACH — AND WHY THEY ARE ASSEMBLED IN SLOTS
 * RATHER THAN CONCATENATED
 * ────────────────────────────────────────────────────────────────────────
 * ⚠ THIS IS THE FINDING OF THE PHASE 3 SPIKE AND IT IS NOT A DETAIL.
 *
 * The obvious translation is `BASE + " " + VARIANT + " " + SIZE`, exactly as
 * the markup wrote `class="btn btn-primary btn-sm"`. **It silently does not
 * work**, and the first run of `CR-018-phase3-button-parity.spec.ts` printed
 * 540 differing properties to prove it: the primary button rendered with a
 * TRANSPARENT background and BODY-COLOURED text, and the small button rendered
 * at the default padding.
 *
 * The cause is the whole difference between a class name and a utility. In
 * CSS, `.btn-primary { background: var(--color-accent) }` beats
 * `.btn { background: transparent }` because it is LATER IN THE FILE — that is
 * the cascade, and the class attribute's order is irrelevant to it. Tailwind
 * emits ONE rule per utility and sorts them by property, so `bg-transparent`
 * and `bg-accent` land in whatever order the compiler chose and the class
 * attribute cannot change it. **Two utilities that set the same property are a
 * coin toss, and the coin is tossed at build time.**
 *
 * So each CSS property is filled exactly ONCE, by a named slot. `.btn-ghost`
 * overriding only `padding-inline` while `.btn-sm` sets `padding-block` — a
 * three-class cascade the old markup got for free — is resolved here, in code,
 * where it can be read and tested.
 *
 * ⚠ AND IT IS WHY REPEATING THE UTILITIES AT ALL 250 CALL SITES WOULD NOT HAVE
 * WORKED EITHER. Every author of every site would have had to do this
 * resolution in their head, and getting it wrong renders a plausible button of
 * the wrong colour with every gate green.
 *
 * Every string below is a literal, not a template — Tailwind's scanner reads
 * source TEXT and cannot see a class it would have to evaluate. Phase 0 lost
 * 55 of 76 swatches to exactly that.
 *
 * The transcription from `components/StateFrame.css` is PROVED, not reviewed:
 * the parity spec renders the legacy class names and this module's output side
 * by side in the live bundle and diffs EVERY computed property in rest / hover
 * / active / disabled. */

/** Everything that does not depend on variant or size. Deliberately sets NO
 *  background-color, color, border-color, font-size or padding: those five are
 *  slots, for the reason above. */
const STRUCTURE =
  "inline-flex items-center justify-center gap-1.5 cursor-pointer no-underline " +
  "font-heading font-extrabold leading-btn border rounded-md " +
  "disabled:opacity-45 disabled:cursor-not-allowed";

/** B14 rule 5's two tiers, and the ONLY place a button font size is written. */
const FONT_SIZE = {
  default: "text-btn",
  sm: "text-btn-sm",
  row: "text-btn-sm",
} as const;

/** `.btn` is `padding: var(--space-2) calc(var(--space-3) * 1.2)`; `.btn-sm` is
 *  `calc(var(--space-1) * 1.5) var(--space-2)`. `px-[14.4px]` is arbitrary
 *  because 14.4 is not on the 4px scale — the value is arbitrary, not the
 *  utility. */
const PAD_BLOCK = {
  default: "py-2",
  sm: "py-1.5",
  row: "py-0",
} as const;
const PAD_INLINE = {
  default: "px-[14.4px]",
  sm: "px-2",
  row: "px-0",
} as const;

/**
 * A FIXED BOX, for the one tier that has one.
 *
 * ⚠ THIS IS WHY `row` AND `settings-row` COULD COLLAPSE AT ALL. They were
 * `0 8px` and `2px 6px` — two paddings, because one held a WORD squeezed into a
 * table row and the other held a 16px SQUARE. Once every row action is an icon
 * (PO ruling 2026-08-20) the content is the same and so is the box, and B14
 * rule 5's "two sizes" is one step closer than it has ever been: four tiers
 * became three on this commit.
 *
 * 32x32 is not new. `.settings-icon-btn` has been `width: 32px; height: 32px;
 * padding: 0` since CR-003, and it beat the size's padding through the cascade
 * rather than through anything the kit knew about — so the seven already-icon
 * tables rendered at exactly this box before this change and render at exactly
 * it after. That is the pixel-neutrality claim, and it is checkable: the box is
 * now written where the size is written.
 */
const BOX = {
  default: "",
  sm: "",
  row: "w-8 h-8",
} as const;

/** `.btn-ghost { padding-inline: var(--space-1) }` sits AFTER `.btn-sm` in
 *  StateFrame.css, so a small ghost button takes its block padding from the
 *  size and its inline padding from the variant.
 *
 *  ⚠ IT DOES NOT WIN AGAINST THE TWO ROW SIZES, and that is a specificity fact
 *  rather than a preference: `.ast-row-actions .btn` is (0,2,0) and `.btn-ghost`
 *  is (0,1,0), so a ghost button in a row action has always taken the row's
 *  inline padding. Measured on the live Assets screen before this migration:
 *  `0px 8px`, not `0px 4px`. */
const GHOST_PAD_INLINE = "px-1";
const GHOST_KEEPS_PAD_INLINE: readonly ButtonSize[] = ["default", "sm"];

/** The four colour slots per variant: background, text, border, and the state
 *  variants. `hover:`/`active:` utilities are emitted after their plain
 *  counterparts by the compiler, so those DO layer as written. */
const VARIANT: Record<ButtonVariant, string> = {
  /** `.btn-primary` */
  primary:
    "bg-accent text-on-accent border-transparent " +
    "hover:bg-accent-600 hover:text-on-accent-600 active:bg-accent-700 active:text-on-accent-700",
  /** `.btn-secondary` */
  secondary:
    "bg-transparent text-text border-divider " +
    "hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)] " +
    "active:bg-[color-mix(in_srgb,var(--color-text)_14%,transparent)]",
  /** `.btn-ghost` */
  ghost:
    "bg-transparent text-accent-text border-transparent " +
    "hover:bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)] " +
    "active:bg-[color-mix(in_srgb,var(--color-accent)_18%,transparent)]",
  /** `.btn-danger` — B14 rule 6: outlined at rest, FILLED on hover, so the
   *  commit is not reachable without the colour having changed first. */
  danger:
    "bg-transparent text-danger-700 border-danger-500 " +
    "hover:not-disabled:text-[#fff] hover:not-disabled:bg-danger-700 " +
    "hover:not-disabled:border-danger-700 active:not-disabled:bg-danger-700",
  /** A destructive row-action icon. Ghost geometry, danger colour: `text` and
   *  `border` are filled here so nothing downstream has to win a cascade. The
   *  hover tint is the danger hue at the same 10% the ghost uses for the accent,
   *  so the two row-action tiers feel like one control with two meanings. */
  "ghost-danger":
    "bg-transparent text-danger-700 border-transparent " +
    "hover:bg-[color-mix(in_srgb,var(--color-danger-700)_10%,transparent)] " +
    "active:bg-[color-mix(in_srgb,var(--color-danger-700)_18%,transparent)]",
  /** `.btn-link` carries NO `.btn` in the markup today, so it replaces the
   *  structure rather than adding to it — see `classesFor`. */
  link:
    // `border: 0` in CSS resets the border to width 0, style `none` AND colour
    // `currentColor`. `border-none` alone leaves the colour at the UA's
    // `buttonborder` black, which is invisible at width 0 and still a diff the
    // parity census reports — so the colour slot is filled explicitly.
    "inline p-0 border-none border-current bg-transparent bg-none cursor-pointer " +
    "font-heading font-semibold text-btn-sm text-accent-text underline " +
    "hover:text-accent-700",
};

/**
 * Every token the kit can write, flattened.
 *
 * ⚠ IT EXISTS SO THE KIT CAN BE CHECKED AT ALL. `g31_declared_classes.py` and
 * `src/styles/routeBUtilities.test.ts` both read `className=` ATTRIBUTES, and a
 * component API puts its class strings in constants instead — so both go blind
 * the moment the markup stops naming classes. `buttonKit.test.ts` walks this
 * list through the real Tailwind compiler on every `npm test`; without it, a
 * typo here is invisible to the whole safety net. See the header of that file
 * for the measurement that proved the hole.
 */
export const BUTTON_KIT_TOKENS: readonly string[] = [
  STRUCTURE,
  ...Object.values(FONT_SIZE),
  ...Object.values(PAD_BLOCK),
  ...Object.values(PAD_INLINE),
  ...Object.values(BOX),
  GHOST_PAD_INLINE,
  ...Object.values(VARIANT),
]
  .flatMap((s) => s.split(" "))
  .filter((t) => t !== "");

/**
 * The CSS property a utility fills, for the handful of properties a caller is
 * allowed to override. Used to DROP the kit's own token when the caller supplies
 * one for the same property.
 *
 * ⚠ THIS EXISTS BECAUSE CLASS ORDER MEANS NOTHING IN TAILWIND. Appending
 * `justify-start` to a string that already contains `justify-center` does not
 * override it — the compiler emits one rule per utility in an order of its own
 * choosing, and which one wins is decided at build time. The same trap that
 * made `bg-accent` lose to `bg-transparent` on the first run of the parity spec.
 * Anything not listed here is simply appended, which is correct for utilities
 * that add a property the kit never sets.
 */
const SLOT_OF: readonly { prefix: string; slot: string }[] = [
  { prefix: "justify-", slot: "justify-content" },
  { prefix: "items-", slot: "align-items" },
  { prefix: "px-", slot: "padding-inline" },
  { prefix: "py-", slot: "padding-block" },
  { prefix: "p-", slot: "padding" },
  { prefix: "w-", slot: "width" },
  { prefix: "h-", slot: "height" },
];

function slotOf(token: string): string | null {
  for (const { prefix, slot } of SLOT_OF) if (token.startsWith(prefix)) return slot;
  return null;
}

function mergeExtra(base: string, extra?: string): string {
  if (extra === undefined || extra === "") return base;
  const taken = new Set(
    extra
      .split(" ")
      .map(slotOf)
      .filter((s): s is string => s !== null),
  );
  const kept = base.split(" ").filter((t) => {
    const slot = slotOf(t);
    return slot === null || !taken.has(slot);
  });
  return [...kept, extra].join(" ");
}

function classesFor(variant: ButtonVariant, size: ButtonSize, extra?: string): string {
  const parts =
    variant === "link"
      ? [VARIANT.link]
      : [
          STRUCTURE,
          FONT_SIZE[size],
          PAD_BLOCK[size],
          (variant === "ghost" || variant === "ghost-danger") &&
          GHOST_KEEPS_PAD_INLINE.includes(size)
            ? GHOST_PAD_INLINE
            : PAD_INLINE[size],
          BOX[size],
          VARIANT[variant],
        ];
  return mergeExtra(parts.filter((p) => p !== "").join(" "), extra);
}

/**
 * The class string, for the elements a component cannot wrap.
 *
 * ⚠ USE A COMPONENT IF YOU CAN. This exists for `<summary>` — the open-control
 * of a `<details>` disclosure, which cannot be a `<button>` without losing the
 * behaviour — and for `GuardedButton`, which builds its own element because
 * BR-SHL-025 makes the disabled-with-reason part of the control. Every other
 * caller should render `<Button>` / `<ButtonLink>` / `<ButtonAnchor>`, because a
 * string handed back out is a string that can be concatenated with a class name
 * nobody declares, and that is the hole Route B was bought to close.
 */
export function buttonClasses(
  variant: ButtonVariant = "secondary",
  size: ButtonSize = "default",
  extra?: string,
): string {
  return classesFor(variant, size, extra);
}
