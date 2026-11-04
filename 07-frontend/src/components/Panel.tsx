// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 4b-2 — migrate the biggest shared LAYOUT container
//           (PO, "Cntinue 4b-2")
// Rules:    CR-018 §6 "Every screen renders identically to its pre-migration
//           self" · Route B ruling 2026-08-19 (styles in the markup)
// Impacts:  149 call sites across 46 components; `.met-panel` and
//           `.met-panel h3` leave `features/metering/metering.css`.
// ───────────────────────────────────────────────────────
//
// THE PANEL — a bordered surface with a heading, used 149 times.
//
// ⚠ THIS WAS SIZED AS THE HARD ONE AND IT IS NOT, WHICH IS PHASE 4b-1's WHOLE
// POINT. `.met-panel` looked like a styling SCOPE: `components/FormModal.css`
// styled `input`, `select`, `textarea` and `label:has(> …)` as its descendants,
// and Route B has no parent selector. Those selectors turned out to name THREE
// scopes — `.view`, `.fin-page`, `.met-panel` — where `.view` (the shell's
// `<main>`) already covers every one of them. Measured in a browser over 15
// screens, 42 panels and 172 controls, then deleted: zero pixel movement. What
// was left is four declarations and one heading rule.
//
// WHY A COMPONENT AND NOT 149 COPIES OF THE UTILITY STRING
//
// The same reason `buttonKit.ts` gives: a string repeated at every call site is
// a string that must be corrected at every call site, and Tailwind cannot warn
// you about the ones you missed. It is also how a container acquires variants
// nobody decided on.
//
// ⚠ `[&_h3]:` IS THE DESCENDANT SELECTOR, AND IT IS NOT A LOOPHOLE. Route B
// removes CLASS NAMES; it does not forbid a rule that reaches a child. Tailwind
// compiles `[&_h3]:text-h5` to `.<hash> h3 { … }` — the same shape
// `.met-panel h3` had, written where the container is written instead of in a
// stylesheet 400 lines away, and checked by the compiler like every other
// utility.
//
// ⚠ AND `text-h5` SETS MORE THAN A SIZE — that is checked, not assumed. The
// token carries `--text-h5--line-height`, `--letter-spacing` and `--font-weight`
// as v4 modifiers, while `.met-panel h3` set only `font-size` and `margin`. It
// is still identical HERE because `global.css` already gives every `h1`–`h6`
// exactly those three values from exactly those tokens, so the modifiers repeat
// what the element has. On a NON-heading element it would not be, which is what
// OQ-279 is about — do not copy this line onto a `<p>`.

import type { HTMLAttributes, ReactNode } from "react";

import { SectionHeadingTag, SectionScope, useSectionHeadingLevel } from "./HeadingLevel";

/**
 * ⚠ **ADDED 2026-09-04 UNDER B14 RULE 36, FOR `DEF-CWP-3655`.** The customer
 * portal had grown a SECOND kit: `portal/components/content.tsx` exported a
 * `Panel` with three border tones and a header row, and
 * `portal/components/primitives.tsx` exported ANOTHER `Panel` for the rail —
 * two components under one name, one directory from this file, while this
 * file's own `title` prop had been added the same morning for exactly the
 * drift one level down. The tones travel here so there is one answer.
 *
 * ⚠ **A TONE IS A BORDER, NOT A FILL.** The portal's two `Panel`s disagreed
 * about that — one changed the border, the other changed the background — and
 * *"one component, one visual decision"* means the disagreement is settled
 * rather than carried. The border says which kind of note this is; the surface
 * stays the surface, so a page of panels reads as one page.
 */
export type PanelTone = "plain" | "info" | "warning" | "emergency" | "group";

/** `.met-panel`, declaration for declaration:
 *
 *      border: 1px solid var(--color-divider)   → border border-divider
 *      background: var(--color-surface)         → bg-surface
 *      padding: var(--space-4)   (16px)         → p-4
 *      margin-bottom: var(--space-4)            → mb-4
 *
 *  and `.met-panel h3 { font-size: var(--text-h5); margin: 0 0 var(--space-2) }`
 *  → `[&_h3]:text-h5 [&_h3]:m-0 [&_h3]:mb-2`.
 *
 *  ⚠ `border` alone is correct and was verified against the compiler rather
 *  than assumed: Tailwind v4 emits `border-style: var(--tw-border-style)` with
 *  it, whose `@property` default is `solid`. Preflight is OFF in this project
 *  until Phase 5, so "the reset supplies the style" would have been the wrong
 *  reason to believe it. */
const PANEL_BORDER_COLOUR = {
  plain: "border-divider",
  info: "border-info-700",
  warning: "border-warning-500",
  /** ⚠ **`emergency` KEEPS THE PLAIN BORDER AND ADDS A RULE DOWN ITS LEFT
   *  EDGE** — see `EMERGENCY_RULE`. It is deliberately NOT a fourth
   *  hue: `09-component-inventory.md` draws it as *"`border-l-4
   *  border-l-[var(--brand)]`, bold title in the body, no header row"*, and
   *  `ReportProblem.tsx` already records, from looking at the running screen,
   *  why a second colour was wrong here — the `info` tone put a blue box
   *  around *"someone may have reported this already"* while the panel saying
   *  *ring this number* stayed quiet. r10 draws no blue at all; its device for
   *  emphasis is a rule in `--color-accent`. */
  emergency: "border-divider",
} as const;

/**
 * ⚠ **THE BORDER COLOUR IS A SLOT, NOT AN APPENDED UTILITY** — the same
 * finding `buttonKit.ts` records at the top of its VARIANT table, one
 * container up. Two utilities that set `border-color` are a coin toss decided
 * at BUILD time, and appending `border-info-700` to a string that already
 * holds `border-divider` would render whichever the compiler happened to emit
 * last. It is filled exactly once, here, by name.
 */
function panelClasses(tone: PanelTone): string {
  /**
   * ⚠ **`group` IS NOT A BOX AT ALL — IT IS THE BLUEPRINT'S NAMED GROUP, AND
   * IT IS IN THE KIT RATHER THAN IN THE SCREEN ON PURPOSE (B14 rule 36:
   * "where the kit lacks a piece, ADD IT TO THE KIT rather than hand-rolling
   * it in the screen, which is how four screens acquire four different
   * chips").**
   *
   * PO ruling 2026-09-13, on the Accounts blueprint's own drawing of `ACC-02`:
   * build it *"exactly that way"*. The drawing groups every fact under a
   * heading in the accent, uppercase and tracked, with an accent rule beneath
   * it running the width of the column — and NO border, NO surface fill and NO
   * padding box around the facts themselves. It is the device r10 uses for
   * emphasis everywhere (see `EMERGENCY_RULE` below, which records that r10
   * draws no blue at all and reaches for an accent rule instead).
   *
   * The PO's own words for why the groups exist, 2026-09-10: *"when we do
   * information architecture, we have to logically group the information, give
   * group a heading so that it is easy for user to understand"*.
   *
   * ⚠ **NOT ONE OF THE 149 EXISTING CALL SITES MOVES A PIXEL.** This is a new
   * value of an existing union; every site that passes no `tone` still takes
   * the `plain` string below, unchanged, character for character. Whether the
   * rest of the product follows this screen is the PO's to rule and is
   * deliberately NOT decided here — `<Panel>` renders 546 blocks.
   */
  if (tone === "group") {
    return (
      // `mb-6` and not `mb-4`: with no border and no fill, the only thing
      // separating one group from the next is the gap, so it carries more
      // work than it does between two bordered cards. 24px is the ruled step
      // above the 16px `plain` uses (B14 rule 39).
      "mb-6 " +
      "[&_h3]:m-0 [&_h3]:mb-3 [&_h3]:pb-2 [&_h3]:text-xs [&_h3]:uppercase " +
      // ⚠ `tracking-[0.1em]` → `tracking-kicker`, 2026-09-13. NOT a silent
      // drive-by: the bracket form landed with this tone earlier today
      // (`eca9055e9`) and fails `eslint --max-warnings 0` in this very file —
      // `no-restricted-syntax`, the rule that exists because a bracket value is
      // a number nobody can grep for. `--tracking-kicker` IS 0.1em, declared in
      // `styles/tailwind.css` for exactly this reason, so the swap is
      // pixel-identical and the compiler proves it through
      // `routeBUtilities.test.ts`.
      "[&_h3]:tracking-kicker [&_h3]:font-heading [&_h3]:text-accent-text"
    );
  }
  return (
    `border ${PANEL_BORDER_COLOUR[tone]} bg-surface p-4 mb-4 ` +
    "[&_h3]:text-h5 [&_h3]:m-0 [&_h3]:mb-2"
  );
}

/**
 * The accent rule under a `group` heading. It sits on the HEADER ROW and never
 * on the `<h3>`, because the drawing runs it the full width of the column and
 * a group with a control beside its title (`HISTORY  All bills →`) must keep
 * one unbroken rule under both. An `<h3>` is as wide as its own text.
 */
/**
 * ⚠ **`pb-1.5` → `pb-2` (6px → 8px), 2026-09-13.** B14 rule 39 ratifies ONE
 * spacing scale — 4 · 8 · 12 · 16 · 20 · 24 · 32 — and forbids an ad-hoc 3, 7,
 * 9 or 14 by name. 6 was in the same class: off the scale, and the gap a reader
 * sees under the rule is `pb` + `mb` together, so this row measured **18px**,
 * which is not a step either. At 8 it is `8 + 12 = 20` — `--space-5`, the step
 * B14 rule 39 itself added — and both halves are on the scale on their own.
 *
 * ⚠ **FOUND BY THE ACC-02 BROWSER CENSUS, NOT BY A TEST**
 * (`10-scripts/render-checks/acc02-overview-conformance.mjs`, which measures
 * `paddingBottom + marginBottom` against that scale). jsdom computes no layout,
 * so no vitest case in this repo could have seen it — B14 rule 39's own status
 * cell says the pixel half is unenforced and law 6 says a person is the only
 * instrument. It is fixed HERE rather than in the screen because the kit is
 * where a visual decision belongs (B14 rule 36), and it moves every `group`
 * panel at once, which is the point.
 */
/**
 * The accent rule under a `group` heading. It sits on the HEADER ROW and never
 * on the `<h3>`, because the drawing runs it the full width of the column and
 * an `<h3>` is only as wide as its text.
 *
 * ⚠ **`[&>*:last-child]:my-[-0.5rem]` IS LOAD-BEARING, NOT TIDYING.** A flex
 * row is as tall as its tallest child, so a group carrying an edit control was
 * **15px taller** than one without it — measured at 1440, MONEY's header row
 * 42px and CUSTOMER's 57px — and `items-baseline` then dropped the heading by
 * exactly that much. The two columns' first headings did not sit on one line,
 * which is what the PO read off the running product: *"Money and Customer - not
 * coming in 1 line - it is not align"*.
 *
 * Pulling the control's own padding back out of the flow makes the row's height
 * the HEADING's, whether or not anything sits beside it. The control still
 * renders at its full size and stays a finger-sized target; it simply stops
 * dictating where the rule is drawn.
 */
const GROUP_HEAD =
  "relative mb-3 flex items-baseline border-b-2 border-b-accent pb-2 " +
  // ⚠ **THE CONTROL IS TAKEN OUT OF THE FLOW ENTIRELY, AND TWO CHEAPER FIXES
  // WERE MEASURED AND REJECTED FIRST.** A flex row is as tall as its tallest
  // child, so a group with an edit control was 15px taller than one without —
  // MONEY's header row 42px, CUSTOMER's 57px at 1440 — and `items-baseline`
  // then dropped the heading by that much, so the two columns' first headings
  // did not sit on one line. The PO read it off the running product.
  //   · `[&>*:last-child]:my-[-0.5rem]` — WRONG SELECTOR: on a group with no
  //     control, `last-child` IS the `<h3>`, so it pulled the heading in and
  //     made the row 14px. Still misaligned, now in the other direction.
  //   · `[&>*:nth-child(2)]:my-[-0.5rem]` — right selector, wrong instrument:
  //     it closed 15px to 7px, and the remaining gap is whatever padding that
  //     particular control happens to carry. A number tuned to one control is
  //     a number the next control breaks.
  // Absolute positioning makes the row's height the HEADING's, whatever sits
  // beside it — so this cannot drift when a group gains a different control.
  // The control keeps its own size and stays a finger-sized target.
  "[&>*:nth-child(2)]:absolute [&>*:nth-child(2)]:right-0 " +
  "[&>*:nth-child(2)]:top-1/2 [&>*:nth-child(2)]:-translate-y-1/2";


/**
 * The prototype's accent rule above a figure — one panel uses it, the "Today"
 * total on Payments.
 *
 * ⚠ IT IS A PROP AND NOT THE CALLER'S `className`, AND THE CENSUS IS WHY. It
 * was `.pay-today { border-top: 2px solid var(--color-accent) }` in
 * `payments.css`, and it stopped winning the moment `Panel` began writing
 * `border border-divider` itself: a feature class and a Panel utility BOTH land
 * unlayered in the built sheet, so which one set the panel's border came down
 * to source order — and the utility was later. The before/after census caught
 * it as three properties on two screens, 2px accent quietly becoming 1px
 * divider, and nothing else in the repo would have.
 *
 * Written here, the order is not luck: `border-width` and `border-top-width`
 * are DIFFERENT properties, so the two compose instead of racing. That is the
 * same trap `buttonKit.ts` documents for variants, one level up at a container
 * — and the same answer: fill each property exactly once, in one place.
 */
const ACCENT = "border-t-2 border-t-accent";

/**
 * The `emergency` tone's left rule (`09-component-inventory.md` §4).
 *
 * ⚠ **`border-l-accent`, NEVER `border-l-[var(--brand)]`**, which is what the
 * inventory's prose literally says. `--brand` is a variable this product sets
 * NOWHERE, and every rule that read it painted GREY (`DEF-CWP-3736`). The
 * tenant's own hex arrives as an override of `--color-accent` on the portal
 * frame, so this is the utility that actually takes the tenant's colour.
 *
 * ⚠ **THE TWO BORDER UTILITIES COMPOSE RATHER THAN RACE**, and it is checked
 * rather than assumed — `TipBar` in `portal/components/content.tsx` ships the
 * identical pair and its own note records the reasoning: `border` / `border-l-4`
 * are `border-width` / `border-left-width`, and `border-divider` /
 * `border-l-accent` are `border-color` / `border-left-color`, which Tailwind
 * emits shorthand-first so the left edge is not a coin toss decided at build
 * time. That is the trap this file already documents for its own tone slot.
 */
const EMERGENCY_RULE = "border-l-4 border-l-accent";

/**
 * ⚠ THE ELEMENT IS THE CALLER'S, AND THIS PROP EXISTS BECAUSE ASSUMING
 * OTHERWISE WOULD HAVE CHANGED 47 SCREENS. The first version of this component
 * hardcoded `<div>` and its comment explained why the tag must not move inside a
 * class migration — while **47 of the 149 call sites were `<section>`**, which
 * the codemod skipped because it only looked for `<div>`. Rendering those as a
 * `<div>` moves the accessibility tree and can flip `:first-child` and sibling
 * rules on every screen they are on.
 *
 * So the tag is carried through: `as="section"` where the source said section,
 * default `div` where it said div. CR-018 §6 — every screen renders identically
 * to its pre-migration self — includes the element it renders as.
 *
 * `data-panel` exists so a check can still find these after the class name is
 * gone: the census that proves this migration pixel-neutral selects
 * `.met-panel, [data-panel]` and would otherwise compare an empty set to an
 * empty set and pass.
 */
export function Panel({
  as: Tag = "div",
  accent = false,
  tone = "plain",
  title,
  trailing,
  className,
  children,
  ...rest
}: {
  /**
   * ⚠ `aside` ADDED 2026-09-04 with `tone`, and for the same reason: the
   * portal's rail panels are `<aside>` elements, and rendering one as a `<div>`
   * moves the accessibility tree — the exact mistake the note below records
   * for `<section>`.
   *
   * ⚠ `article` ADDED 2026-09-16 (`DEF-INT-5497`), and for the THIRD time for
   * the same reason. The connector grid's 28 cards are `<article>` elements —
   * each is a self-contained thing a screen reader can navigate to — and they
   * were a hand-rolled box with `border-neutral-200 bg-bg`: no accent rule, and
   * a background byte-identical to the page, measured in a browser at
   * `rgb(243,242,242)` against a page of `rgb(243,242,242)`. The Product Owner
   * read it off the running product — *"see there is a line on top and color to
   * card - panel ui is not correct"*. **The fix is one word here rather than a
   * fourth opinion about what a card looks like**, which is B14 rule 36; adding
   * a tag to this union moves no existing call site by a pixel.
   */
  as?: "div" | "section" | "aside" | "article";
  accent?: boolean;
  /** See `PanelTone`. Absent is `plain`, which is byte-for-byte what the 149
   *  existing call sites already render. */
  tone?: PanelTone;
  /**
   * ⚠ **ADDED 2026-09-04 UNDER B14 RULE 36**, which says in as many words:
   * *"where the kit lacks a piece, ADD IT TO THE KIT rather than hand-rolling
   * it in the screen, which is how four screens acquire four different
   * chips."* Three screens of `CR-068` wave D had each written their own
   * `<section>` with their own border and their own small-caps `<h3>` — the
   * same drift, one component down.
   *
   * OPTIONAL, and absent renders byte-for-byte what this component rendered
   * before, so none of the 149 existing call sites moves a pixel. A panel that
   * already writes its own `<h3>` keeps doing so.
   */
  title?: ReactNode;
  /**
   * A control on the title's row — the *See all* link the portal's help and
   * visit panels carry.
   *
   * ⚠ **IT IS A PROP AND NOT `children`, BECAUSE A HEADER ROW IS A LAYOUT
   * DECISION AND THIS IS WHERE LAYOUT DECISIONS LIVE.** `portal/components/
   * content.tsx` drew its own `<header className="flex items-center
   * justify-between …">` with its own bottom border and its own small-caps
   * `<h2>`; that is three visual decisions taken in a screen file, which is
   * how a product ends up with four different section headers.
   *
   * ⚠ **ABSENT TAKES THE OLD PATH EXACTLY.** No wrapper element appears
   * around the `<h3>` unless something is being put beside it, so no existing
   * call site moves a pixel — asserted in `PageHeader`-style by
   * `Panel.test.tsx`, not assumed.
   */
  trailing?: ReactNode;
  children: ReactNode;
  // ⚠ **`title` IS OMITTED FROM THE HTML ATTRIBUTES, AND WITHOUT THIS THE
  // PROP DECLARED ABOVE IS UNUSABLE AS DOCUMENTED.** `HTMLAttributes` carries
  // its own `title?: string` (the tooltip), so intersecting the two narrowed
  // this component's `title` to `ReactNode & string` — a type nothing but a
  // string satisfies. The prop's own doc has said `ReactNode` since it was
  // added; the first caller to pass an element (the reading detail's five
  // panels, whose headings the drawings show as the red small-caps label) met
  // `TS2322` instead. **NOTHING EXISTING MOVES:** every current call site
  // passes a string, a string is still a `ReactNode`, and no rendered output
  // changes. B14 rule 36 — where the kit lacks the piece a drawing needs, the
  // kit is where it is added, as an opt-in.
} & Omit<HTMLAttributes<HTMLElement>, "title">) {
  let base = accent ? `${panelClasses(tone)} ${ACCENT}` : panelClasses(tone);
  if (tone === "emergency") base = `${base} ${EMERGENCY_RULE}`;
  // ⚠ **AN OUTLINE, WHERE ONE IS KEPT — AND ONLY THEN (`DEF-CWP-10563`).**
  // The title has always been an `<h3>`, which is right inside a staff screen
  // whose tab strip owns the h2, and wrong in the customer portal, where a
  // panel sits straight under the page's h1 and the outline jumped h1 → h3 on
  // most pages. `useSectionHeadingLevel()` is `null` everywhere except under
  // the portal's `HeadingLevelProvider`, so EVERY STAFF PANEL TAKES THE
  // UNCHANGED BRANCH BELOW, byte for byte. In the portal the title takes the
  // outline's level and the panel's contents sit one level further down.
  //
  // The size does not move: the `<h3>` was sized by this panel's own
  // `[&_h3]:text-h5 [&_h3]:m-0 [&_h3]:mb-2`, and those three utilities are put
  // on the heading itself here. `global.css` sets only `font-size` per tag,
  // which `text-h5` overrides. The `group` tone is not drawn in the portal and
  // keeps its `<h3>` everywhere, deliberately — its heading row has
  // specificity of its own (see `GROUP_HEAD`) that this would disturb.
  const outline = useSectionHeadingLevel();
  if (outline !== null && title !== undefined && tone !== "group") {
    const heading = (
      <SectionHeadingTag tag={`h${Math.min(6, outline)}` as `h${1 | 2 | 3 | 4 | 5 | 6}`} className="m-0 mb-2 text-h5">
        {title}
      </SectionHeadingTag>
    );
    return (
      <Tag
        data-panel=""
        data-tone={tone === "plain" ? undefined : tone}
        className={className === undefined ? base : `${base} ${className}`}
        {...rest}
      >
        {trailing === undefined ? (
          heading
        ) : (
          <div className="flex items-start justify-between gap-3">
            {heading}
            {trailing}
          </div>
        )}
        <SectionScope inner={Math.min(6, outline + 1)}>{children}</SectionScope>
      </Tag>
    );
  }
  return (
    <Tag
      data-panel=""
      data-tone={tone === "plain" ? undefined : tone}
      className={className === undefined ? base : `${base} ${className}`}
      {...rest}
    >
      {title === undefined ? (
        children
      ) : tone === "group" ? (
        /* The `group` tone ALWAYS wraps its title row, with or without a
           control, so the accent rule is one unbroken line either way. The
           `<h3>`'s own bottom margin and padding are dropped into the wrapper
           here — `[&_h3]:mb-3 [&_h3]:pb-1.5` above would otherwise push the
           rule away from the text it belongs to. */
        <>
          <div className={GROUP_HEAD}>
            <h3 className="m-0 p-0">{title}</h3>
            {trailing}
          </div>
          {children}
        </>
      ) : trailing === undefined ? (
        <><h3>{title}</h3>{children}</>
      ) : (
        <>
          {/* `items-start`, not `items-center`: the `<h3>` keeps its own
              `mb-2` from PANEL, and centring against a margin the heading
              still owns would fight a slot this component already filled. */}
          <div className="flex items-start justify-between gap-3">
            <h3>{title}</h3>
            {trailing}
          </div>
          {children}
        </>
      )}
    </Tag>
  );
}
