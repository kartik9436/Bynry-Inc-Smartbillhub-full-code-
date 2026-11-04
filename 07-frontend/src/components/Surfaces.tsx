// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 4b-4 — the last three of the five the PO named, done
//           TOGETHER rather than in series ("why you ahve to do them in series")
// Rules:    CR-018 §6 · B14 rule 21 (new UI is Tailwind) · B14 rule 20 (one
//           table type size) · BR-SHL-020 (server refusals)
// Impacts:  166 call sites; three classes leave two stylesheets.
// ───────────────────────────────────────────────────────
//
// ⚠ THESE THREE ARE MIGRATED IN ONE PASS, AND THE PO IS RIGHT THAT THEY SHOULD
// BE. The expensive part of a migration here is not the edit, it is the
// before/after browser census — six minutes a run, and a screen that carries a
// refusal, a table and a link needs the same walk whichever class you are
// chasing. Doing them one at a time paid that cost three times over the same
// screens. The diff still tells them apart because every element is tagged with
// which component drew it.

import type { HTMLAttributes, ReactNode, TableHTMLAttributes } from "react";
import { Link } from "react-router-dom";
import type { LinkProps } from "react-router-dom";

/* ── The red strip a server refusal renders in ─────────────────────────────
 *
 * `.settings-refusal`, declaration for declaration:
 *
 *      background: var(--color-danger-100)      → bg-danger-100
 *      color: var(--color-danger-700)           → text-danger-700
 *      font-size: var(--text-base)      (13px)  → text-base
 *      padding: var(--space-2) var(--space-3)   → py-2 px-3
 *      margin: 0                                → m-0
 *      border-left: 2px solid …danger-500       → border-l-2 border-l-danger-500
 *      max-width: var(--desc-measure)           → max-w-measure
 *
 * ⚠ THE LAST DECLARATION CAME FROM A SECOND RULE 700 LINES AWAY. `.settings-refusal`
 * was declared TWICE in `SettingsPage.css` — once at line 149 for its colours and
 * padding, and again at line 857 in a `.panel-hint, .settings-refusal` pair for
 * `max-width` alone. Both applied, so the class worked; but nobody reading
 * either rule could see the whole of it. Consolidating them is not a tidy-up,
 * it is the reason a component API is worth having: one place to read.
 */
const REFUSAL =
  "bg-danger-100 text-danger-700 text-base py-2 px-3 m-0 " +
  "border-l-2 border-l-danger-500 max-w-measure";

/** The red error strip — BR-SHL-020's server refusal. 71 sites.
 *
 * ⚠ NAMED `RefusalStrip`, NOT `Refusal`, and tsc is why: `Refusal` is already an
 * exported INTERFACE in `features/tenancy/settingsShared.tsx` — the shape of the
 * server's answer — and 30 files import it. A component with the same name
 * collides in every one of them. The strip is the thing that DRAWS a refusal;
 * the interface is the refusal. */
export function RefusalStrip({
  as: Tag = "p",
  className,
  children,
  ...rest
}: {
  as?: "p" | "div" | "span" | "td";
  children: ReactNode;
  /** ⚠ ONE call site renders the strip as a table cell spanning the row, so the
   *  cell attributes have to reach the element. `HTMLAttributes` does not carry
   *  `colSpan`; `TdHTMLAttributes` does, and it is a superset for our purposes. */
  colSpan?: number;
} & HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      data-refusal=""
      className={className === undefined ? REFUSAL : `${REFUSAL} ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/* ── The small plain table inside a detail tab or a wizard preview ─────────
 *
 * `.met-table` and its three descendant rules. The descendants are written as
 * Tailwind's descendant variant, the same move `Panel` made for `h3`: Route B
 * removes class NAMES, it does not forbid a rule that reaches a child.
 *
 * ⚠ `thead th` IS SCOPED AND MUST STAY SCOPED. The original comment says why: a
 * `<th>` in a BODY row is a row header — the tie-out table's left column — and
 * must match the `<td>`s beside it, not the column labels above. Applying the
 * header tier to every `<th>` made that row 12px inside a 13.5px table. The
 * variant is `[&_thead_th]:`, not `[&_th]:`, for exactly that reason.
 */
const PLAIN_TABLE =
  "w-full border-collapse text-table " +
  "[&_th]:border-b [&_th]:border-b-divider [&_th]:p-2 [&_th]:text-left [&_th]:align-top " +
  "[&_td]:border-b [&_td]:border-b-divider [&_td]:p-2 [&_td]:text-left [&_td]:align-top " +
  "[&_thead_th]:font-heading [&_thead_th]:text-table-header " +
  "[&_thead_th]:uppercase [&_thead_th]:tracking-table-header";

/** A plain table — not the shared `DataTable`, the small ones showing a few
 *  rows of figures inside a panel or a wizard preview. 51 sites. */
export function PlainTable({
  className,
  children,
  ...rest
}: { children: ReactNode } & TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table
      data-plaintable=""
      className={className === undefined ? PLAIN_TABLE : `${PLAIN_TABLE} ${className}`}
      {...rest}
    >
      {children}
    </table>
  );
}

/* ── A word that looks like a link and is a button ─────────────────────────
 *
 * ⚠ `font: inherit` IS THE INTERESTING DECLARATION AND IT CANNOT BE COPIED
 * ACROSS AS A SHORTHAND. Written as `[font:inherit]`, Tailwind emits it AFTER
 * `text-md` — verified against the compiler, not assumed — so the shorthand
 * would silently overwrite the font SIZE with the inherited one, and this
 * button would render at the table's 13.5px instead of its own 14px. A one-word
 * class, a size nobody would notice moving, and no test in the repo could see
 * it.
 *
 * So each property is filled exactly once, which is `buttonKit.ts`'s rule
 * restated: `font: inherit` on a `<button>` means "undo the UA font", and what
 * it resolves to here is the body family, a normal weight and the body leading
 * — with the size then set explicitly.
 *
 *      background: none          → bg-transparent bg-none   (the shorthand
 *                                  clears the COLOUR too, so both slots)
 *      border: 0                 → border-none border-current  (same reasoning
 *                                  as the kit's `link` variant: `border-none`
 *                                  alone leaves the colour at the UA's
 *                                  `buttonborder`, which is a diff a census
 *                                  reports even at zero width)
 *      font: inherit             → font-body font-normal leading-body
 *      font-size: var(--text-md) → text-md
 *      color: var(--color-accent-700) → text-accent-700
 *      cursor / text-align / text-decoration → cursor-pointer text-left no-underline
 *      :hover, :focus-visible    → hover:underline focus-visible:underline
 *
 * ⚠ IT IS DELIBERATELY *NOT* `<Button variant="link">`. That tier is 12px and
 * carries the heading family at semibold; this is 14px body text. Folding them
 * together moves pixels on 23 screens and is a DESIGN decision the PO has not
 * been asked for — a migration does not get to make it.
 */
const INLINE_LINK =
  "bg-transparent bg-none border-none border-current p-0 " +
  "font-body font-normal leading-body text-md text-accent-700 " +
  "cursor-pointer text-left no-underline hover:underline focus-visible:underline";

/**
 * The same look on a real `<a href>` — 4 sites, every one a mailto: or an
 * external document the browser must handle itself.
 *
 * ⚠ A THIRD EXPORT RATHER THAN A THIRD `as` VALUE, and by now the pattern is
 * the point: a `<button>` needs `onClick`, a router `<Link>` needs `to`, an
 * `<a>` needs `href`, and one component taking all three takes none of them
 * properly. `RowActions` reached the same shape from the same direction.
 */
export function InlineLinkAnchor({
  className,
  children,
  ...rest
}: { children: ReactNode } & HTMLAttributes<HTMLAnchorElement> & {
  href: string;
  target?: string;
  rel?: string;
}) {
  return (
    <a
      data-inlinelink=""
      className={className === undefined ? INLINE_LINK : `${INLINE_LINK} ${className}`}
      {...rest}
    >
      {children}
    </a>
  );
}

/** A link-shaped `<button>` inside a table cell — it ACTS, it does not
 *  navigate. 20 sites. */
export function InlineLink({
  className,
  type = "button",
  children,
  ...rest
}: { children: ReactNode } & HTMLAttributes<HTMLButtonElement> & { type?: "button" | "submit" }) {
  return (
    <button
      type={type}
      data-inlinelink=""
      className={className === undefined ? INLINE_LINK : `${INLINE_LINK} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

/**
 * The same look, on a router `<Link>` that really does navigate — 21 sites,
 * every one of them an id or a name in a table cell that opens a record.
 *
 * ⚠ IT IS A SEPARATE EXPORT AND NOT AN `as` PROP, for the reason `RowActionLink`
 * is separate from `RowAction`: a `<Link>` needs `to` and a `<button>` needs
 * `onClick`, and a component that accepts both accepts neither properly. The
 * codemod's first pass turned these into `<InlineLink as="a">` and tsc refused
 * it — which is the check working, one step before a census would have found
 * twenty-one dead controls.
 */
export function InlineLinkTo({
  className,
  children,
  ...rest
}: { children: ReactNode } & LinkProps) {
  return (
    <Link
      data-inlinelink=""
      className={className === undefined ? INLINE_LINK : `${INLINE_LINK} ${className}`}
      {...rest}
    >
      {children}
    </Link>
  );
}
