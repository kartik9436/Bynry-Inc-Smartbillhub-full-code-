// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 3 — the SHARED classes. PO ruling 2026-08-19,
//           verbatim *"Route B"*: the styles go in the markup and the class
//           names go away.
// Rules:    B14 rule 5 (two button sizes only — default and small, 12px; no
//           inline font sizes) · B14 rule 6 (destructive commits use the
//           danger tier — outlined at rest, filled on hover) · CR-018 §6
//           (every screen renders identically to its pre-migration self)
// Impacts:  every component that draws a button. `components/StateFrame.css`
//           keeps `.btn*` declared until the LAST call site is migrated —
//           deleting it while 70+ files still name it is DEF-327 in reverse.
// ───────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS AT ALL — the question Phase 3 was sent to answer
// ─────────────────────────────────────────────────────────────────────
// Route B says "put the utilities in the markup". `.btn` is written at 250
// sites in 83 of our 127 components. Taken literally, Route B means 250 copies
// of the same 24-utility string — and then a padding change is an 83-file edit,
// which is the job class names were invented to do.
//
// So the utility string is written ONCE, here, and the 250 sites ask for it by
// MEANING (`variant="primary"`) rather than by the class NAME the markup used
// to carry. This is Tailwind's own published guidance for a repeated
// ⚠ AND THE NAME IS NOT SPELLED OUT ANYWHERE ABOVE, DELIBERATELY. Since
// CR-018 Phase 4a deleted the six variant rules, no stylesheet declares those
// names any more — so `g31_declared_classes.py` reports a class name quoted in
// a COMMENT as an undeclared class asked for by this file. It did, on the very
// commit that deleted them. Documenting a Route B escape hatch by example has
// now tripped that gate three times; describe the shape, do not write it.
// pattern, and it is what this codebase already does for `DataTable`,
// `StateFrame` and `FormModal`.
//
// ⚠ IT IS NOT `@apply`, AND THE DIFFERENCE IS THE WHOLE RULING. `@apply .btn`
// in a component layer keeps the CLASS NAME as the contract, so a component
// can still name a class nothing declares and tsc, eslint and toHaveClass()
// all still pass — DEF-327's exact failure mode, which recurred six times in
// five months. That is Route A, and the PO rejected it. Here the contract is a
// TYPE: `variant="primry"` does not compile.
//
// THE THREE THINGS THE CALL SITES NEEDED THAT A `<button>`-ONLY COMPONENT
// COULD NOT GIVE, measured across all 250 sites before this was written
// ────────────────────────────────────────────────────────────────────────
//   1. The kit is applied to FIVE elements, not one: <button> ×192,
//      <GuardedButton> ×36, <Link> ×20, <a> ×1, <summary> ×1. A component that
//      renders <button> covers 192. Hence `ButtonLink` / `ButtonAnchor`, and
//      `buttonClasses()` for the one <summary>, which is the open-control of a
//      <details> menu and CANNOT be another element without losing the
//      disclosure behaviour.
//   2. SEVEN stylesheet rules style a button from its PARENT
//      (`.settings-row-actions .btn`, `.met-row-actions .btn`, …). Utilities
//      have no parent selector, so those overrides have to travel down to each
//      button. They are `size` and `className` here, never a parent rule.
//   3. Three sites assemble the class at runtime from state
//      (`btn btn-secondary${active ? " active" : ""}`). Those are props now.
//
// WHY THE OPACITY MODIFIER IS SPELLED OUT LONG-HAND
// ─────────────────────────────────────────────────
// `bg-text/7` is the readable idiom and it emits `color-mix(in OKLAB, …)`.
// Our stylesheets write `color-mix(in srgb, …)` at 243 sites. On the near-black
// ink the two round to the same rgb; on the saturated accent they do not. A
// migration that silently changes colour space is not the "renders identically"
// CR-018 §6 requires, so the space is written out. Phase 1 recorded this as the
// single biggest readability cost Route B pays; it is paid again here.

// ⚠ `data-variant` / `data-size` ARE PART OF THE CONTRACT, NOT DEBUG ATTRIBUTES
// ────────────────────────────────────────────────────────────────────────────
// 32 assertions in 19 test files ask B14's questions by CLASS NAME —
// a `toContain` on the primary variant's class for rule "exactly one primary
// action in the header", `not.toContain` for "no primary on this tab", and so
// on. Route B deletes
// the class name, so every one of those assertions breaks, and rewriting them
// against a utility such as `bg-accent` would tie a RULE about intent to an
// incidental fact about colour — the day the primary stops being accent-filled,
// 32 tests go green while meaning nothing.
//
// So the component states its own intent. `data-variant` is written by THIS
// file and can never be mistyped by a caller, which is more than the class name
// it replaces could say. It is also what finally lets B14 rule 5 be asked
// properly: "how many button SIZES does this screen render" is
// `[data-size]` — a question no stylesheet could answer, and the reason the
// product has been rendering four different small-button paddings under one
// conforming font size.
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";

import { buttonClasses, type ButtonSize, type ButtonVariant } from "./buttonKit";

export { buttonClasses } from "./buttonKit";
export type { ButtonSize, ButtonVariant } from "./buttonKit";

type ButtonOwnProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Classes that are NOT the button kit — a layout override the parent used to
   *  impose through a descendant selector, or one of the 159 shared classes
   *  Phase 3 has not reached yet. Never a `btn*` name. */
  className?: string;
  children?: ReactNode;
};

/** 189 of the 192 `<button>` sites write `type="button"`; the default is here so
 *  that the exception has to be typed rather than the rule. */
export function Button({
  variant = "secondary",
  size = "default",
  className,
  type = "button",
  ...rest
}: ButtonOwnProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      data-variant={variant}
      data-size={size}
      className={buttonClasses(variant, size, className)}
      {...rest}
    />
  );
}

/** A router `<Link>` that renders as a button — 20 sites. It is a link because
 *  it NAVIGATES; making it a button would break middle-click and the browser's
 *  own "open in new tab", which is a real loss on a bill document. */
export function ButtonLink({
  variant = "secondary",
  size = "default",
  className,
  ...rest
}: ButtonOwnProps & LinkProps) {
  return (
    <Link
      data-variant={variant}
      data-size={size}
      className={buttonClasses(variant, size, className)}
      {...rest}
    />
  );
}

/**
 * The `<summary>` of a `<details>` disclosure, drawn as a button — 1 site, the
 * CSV/PDF download menu.
 *
 * ⚠ IT IS A COMPONENT AND NOT A CALL TO `buttonClasses` IN THE MARKUP, and that
 * was MEASURED rather than preferred. Written as a call inside the class
 * attribute, `g31_declared_classes.py` pulls the quoted VARIANT NAME out of the
 * expression and reports it as an undeclared class — the gate went from 0 to 1
 * on exactly that one line. Its grammar cannot tell a class name from an
 * argument that happens to be a string, and it should not have to.
 *
 * (Writing that sentence out with the offending call spelled literally tripped
 * the same gate a second time, from a COMMENT — which is worth knowing before
 * anyone documents a Route B escape hatch by example.)
 *
 * So every element the kit is applied to gets a wrapper, and the class string
 * never appears at a call site at all.
 */
export function ButtonSummary({
  variant = "secondary",
  size = "default",
  className,
  ...rest
}: ButtonOwnProps & HTMLAttributes<HTMLElement>) {
  return (
    <summary
      data-variant={variant}
      data-size={size}
      className={buttonClasses(variant, size, className)}
      {...rest}
    />
  );
}

/** A plain `<a href>` that renders as a button — 1 site, the bill PDF, which
 *  leaves the SPA and so cannot be a router Link. */
export function ButtonAnchor({
  variant = "secondary",
  size = "default",
  className,
  ...rest
}: ButtonOwnProps & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      data-variant={variant}
      data-size={size}
      className={buttonClasses(variant, size, className)}
      {...rest}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-018 Phase 3 (the shared-class spike) · PO ruling 2026-08-19 "Route B"
// generated: 2026-08-20 by the CR-018 Phase 3 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=pending(the other 159 shared classes)
// gates: e2e/CR-018-phase3-button-parity.spec.ts — every computed property of
//        every variant × every state, legacy vs component, in the live bundle
