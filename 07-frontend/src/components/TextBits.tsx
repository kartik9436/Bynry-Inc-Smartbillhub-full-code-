// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 4b-3 — the two leaf text classes the PO prioritised
//           ("priotise - kicker + settings-note")
// Rules:    CR-018 §6 (every screen renders identically) · Route B
// Impacts:  155 call sites; `.kicker` leaves `styles/global.css` and
//           `.settings-note` leaves `features/tenancy/SettingsPage.css`.
// ───────────────────────────────────────────────────────
//
// TWO PIECES OF TEXT THAT APPEAR EVERYWHERE AND OWN NO LOGIC.
//
// They are together in one file because they are the same KIND of thing — a
// styled run of text with no behaviour — and splitting a 20-line component into
// its own module is how a components directory becomes unreadable. `Panel` and
// `RowActions` are separate because each carries decisions (an element, an
// accessible name, a disabled contract); these carry none.
//
// ⚠ `.kicker` IS THE CAUTIONARY TALE OF THIS WHOLE MIGRATION, and its old
// comment in `global.css` says why: until that rule was written, **all 63 call
// sites rendered 15px body copy in the tenant's ink** — "byte-identical in the
// DOM to a class that works, invisible to tsc, eslint and vitest, and visible
// only in computed style". A class name that styles nothing looks exactly like
// one that styles everything. That is what the before/after browser census
// exists for, and it is why these two are migrated behind one.

import type { HTMLAttributes, ReactNode } from "react";

/** `.kicker`, declaration for declaration:
 *
 *      font-size: var(--text-xs)        (11px)  → text-xs
 *      letter-spacing: 0.1em                    → tracking-kicker
 *      text-transform: uppercase                → uppercase
 *      color: var(--color-accent)               → text-accent
 *      font-family: var(--font-heading)         → font-heading
 *      font-weight: 800                         → font-extrabold
 */
const KICKER = "text-xs tracking-kicker uppercase text-accent-text font-heading font-extrabold";

/**
 * The small uppercase label above a heading — "REFERENCE DATA" over "Units of
 * measure". 66 sites, 64 of them a `<span>` and two a `<div>`, so the element
 * is the caller's: `Panel` learned that the hard way when 47 of its sites
 * turned out to be `<section>`.
 */
export function Kicker({
  as: Tag = "span",
  className,
  children,
  ...rest
}: {
  as?: "span" | "div";
  children: ReactNode;
} & HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      data-kicker=""
      className={className === undefined ? KICKER : `${KICKER} ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/** `.settings-note`, declaration for declaration:
 *
 *      font-size: var(--text-xs)                          (11px) → text-xs
 *      color: color-mix(in srgb, var(--color-text) 60%, transparent)
 *      margin: 0                                                 → m-0
 *
 *  ⚠ THE COLOUR IS AN ARBITRARY VALUE AND THAT IS CORRECT HERE. `color-mix` at
 *  60% of the ink is not a palette entry — it is this one caption's dimming, and
 *  three other classes dim by different amounts (65%, 70%). Tokenising it would
 *  invent a design decision nobody made. `buttonKit.ts` writes its hover tints
 *  the same way and for the same reason.
 */
const NOTE = "text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)] m-0";

/**
 * The small grey caption under a title, explaining what the thing does. 89
 * sites, 84 of them a `<p>` and five a `<span>`.
 */
export function Note({
  as: Tag = "p",
  className,
  children,
  ...rest
}: {
  as?: "p" | "span";
  children: ReactNode;
} & HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      data-note=""
      className={className === undefined ? NOTE : `${NOTE} ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  );
}
