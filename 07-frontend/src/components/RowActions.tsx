// ── Trace ──────────────────────────────────────────────
// Change:   PO ruling 2026-08-20 — "Icons everywhere, per r10 and rule 15",
//           and "we should ahve only one reference point not two"
// Rules:    B14 rule 15 (icons with tooltips, never text links) · BR-SHL-025
//           (a control that cannot act is DISABLED WITH ITS REASON, never hidden)
// Defects:  DEF-337 (four red words in one cell on Users & roles) · DEF-342
// Impacts:  the ACTIONS cell of every list table; five per-feature container
//           classes retire into this one component.
// ───────────────────────────────────────────────────────
//
// THE ACTIONS CELL, ONCE.
//
// ⚠ FIVE CONTAINERS AND TWO CONVENTIONS IS WHAT THIS REPLACES. Before this the
// product had `.ast-row-actions`, `.met-row-actions`, `.settings-row-actions`,
// `.rating-row-actions` and `.fin-row-actions` — five declarations of the same
// flex row, with three different gaps — and, underneath them, TWO ways of
// drawing an action: seven tables used icons (CR-003/CR-004) and sixteen used
// text links. DEF-337 is what the text half looks like to a customer: *"Edit /
// Deactivate / Remove / Reset temp password sit as four red words in one cell"*.
//
// ⚠ AND THE SPLIT IS WHAT MADE DEF-342 UNFIXABLE. Text needed `0 8px`, a 16px
// glyph needed `2px 6px`, so the product carried two row-action button sizes
// under one font size and neither was wrong. One content, one tier: see `BOX`
// in `buttonKit.ts`.
//
// WHY A COMPONENT AND NOT A CLASS, AND NOT A UTILITY STRING EITHER:
//
//   * `aria-label` is not optional here and a class cannot carry it. An icon
//     with no accessible name passes every text-absence check in the suite and
//     is unusable without a mouse — B14's own note on rule 15 says so, and it
//     is the failure the obvious guard misses. Making the label a REQUIRED PROP
//     is the only form where forgetting it does not compile.
//   * `title` is the only thing that says WHY on a disabled control (BR-SHL-025),
//     so `reason` and `disabled` are ONE prop. A caller cannot disable a button
//     here without saying why, because there is no boolean to pass.
//   * Repeating the utilities at every call site does not work — see the header
//     of `buttonKit.ts`. Two utilities filling one property are decided at build
//     time, not by the order they are written in.

import { useRef, useState } from "react";
import type { ReactNode, SyntheticEvent } from "react";
import { Button, ButtonAnchor, ButtonLink } from "./Button";
import { MoreIcon } from "./icons";

/**
 * The ACTIONS cell's container.
 *
 * `gap-1` (4px) and not the 8px the assets and metering tables used: 4px is what
 * the seven already-icon tables have rendered since CR-003, and a 32px box does
 * not need 8px between neighbours. The tables that move are the ones this
 * ruling converts.
 */
export function RowActions(props: { children: ReactNode }) {
  // DEF-352 (fixed 2026-08-22, W15): `flex-wrap` let four 32px icons fold
  // 2×2 inside the ACTIONS column the old text links had sized. Row actions
  // are ONE row by definition — r10 draws them so on every table — so the
  // container refuses to wrap and the cell grows to its content instead.
  return <span className="inline-flex items-center gap-1 flex-nowrap">{props.children}</span>;
}

interface RowActionShape {
  /**
   * The action, in words, translated. It becomes BOTH `aria-label` and — when
   * the control is enabled — `title`. It is required and it is a `string`
   * rather than a `ReactNode`, because an accessible name is text.
   */
  label: string;
  /** A glyph from `components/icons.tsx`. Never a raw `<svg>`. */
  icon: ReactNode;
  /**
   * `null` = the action is allowed. Anything else DISABLES the control and
   * becomes its tooltip — BR-SHL-025: the user learns the rule instead of
   * hunting for a control somebody removed.
   */
  reason?: string | null;
  /**
   * A LONGER tooltip than the label, when the action has one — "Deleting a
   * route unassigns it from every cycle", say. It replaces `label` in `title`
   * and never in `aria-label`: the accessible name stays the short verb, so a
   * screen reader announces "Delete" and does not read a sentence at every row.
   *
   * `reason` still wins over it — a control that cannot act must say WHY before
   * it says what it would have done.
   */
  hint?: string;
  /** Destructive — delete, retire, remove. Colours the glyph, nothing else. */
  danger?: boolean;
  /**
   * `data-testid`, for the handful of tests that address a row action directly.
   *
   * ⚠ IT IS NOT THE PREFERRED HOOK AND IS NOT ADDED TO NEW CALL SITES. An icon
   * row action is addressable by its accessible name — `getByRole("button", {
   * name })` — which is the same string a screen reader announces, so a test
   * written that way fails when the label breaks. A `data-testid` passes with
   * no label at all, which is the exact failure rule 15 exists to prevent. This
   * prop carries the two ids TemplateCatalog already had.
   */
  testId?: string;
}

export function RowAction(
  props: RowActionShape & {
    working?: boolean;
    /**
     * `aria-pressed` — for the one row action that is a TOGGLE rather than a
     * command: "open this version in the editor" stays visibly on while that
     * version is the one open. Omit it everywhere else; a command that reports
     * a pressed state is announced as a toggle and confuses what it does.
     */
    pressed?: boolean;
    onClick: () => void;
  },
) {
  const blocked = props.reason ?? null;
  return (
    <Button
      variant={props.danger === true ? "ghost-danger" : "ghost"}
      size="row"
      aria-label={props.label}
      title={blocked ?? props.hint ?? props.label}
      disabled={blocked !== null || props.working === true}
      aria-pressed={props.pressed}
      data-testid={props.testId}
      onClick={blocked === null ? props.onClick : undefined}
    >
      {props.icon}
    </Button>
  );
}

/**
 * A row action that NAVIGATES — "View units" scoping the units list to a
 * premise, for one.
 *
 * ⚠ IT IS A LINK AND NOT A BUTTON WITH AN `onClick`, deliberately: a button
 * breaks middle-click and the browser's own "open in new tab", which is a real
 * loss on a row a clerk wants to open beside the one they are reading. Same
 * reason `ButtonLink` exists.
 *
 * A disabled link is not a thing the platform has, so a blocked navigation
 * renders as a disabled BUTTON carrying the reason — the control stays visible
 * and still says why, which is what BR-SHL-025 asks for.
 */
/**
 * A row action that LEAVES THE APP — a stored document served by the API, and
 * nothing else so far.
 *
 * ⚠ **IT IS AN `<a href>` AND NOT A ROUTER `Link`, WHICH IS THE WHOLE REASON IT
 * EXISTS** (`CR-085` `CPB-14`). `RowActionLink` renders a `Link`, and a `Link`
 * to `/api/…` is a client-side navigation into a route the SPA does not have:
 * the address bar changes, the router draws nothing, and the file is never
 * fetched. `ButtonAnchor` already carried this exact note for the bill PDF —
 * *"a plain `<a href>` that renders as a button — 1 site, the bill PDF, which
 * leaves the SPA and so cannot be a router Link"* — and this is that site made
 * addressable from a table row.
 *
 * ⚠ **A BLOCKED ANCHOR IS A DISABLED BUTTON CARRYING THE REASON**, exactly as
 * in `RowActionLink` and for its reason: a disabled link is not a thing the
 * platform has, and `BR-SHL-025` wants the control visible and still saying
 * why.
 *
 * ⚠ **THERE IS NO `download` PROP, AND THAT IS DELIBERATE.** A first draft had
 * one; nothing passed it, which is hard-won law 2 exactly — an optional prop
 * nothing supplies is dead code that every test passes over. It would also have
 * been wrong: the server already sends `Content-Disposition`, and a `download`
 * attribute on top of it OVERRIDES the filename the server chose, which is the
 * one carrying the number printed on the customer's paper.
 */
export function RowActionAnchor(props: RowActionShape & { href: string }) {
  const blocked = props.reason ?? null;
  if (blocked !== null) {
    return (
      <Button variant="ghost" size="row" aria-label={props.label} title={blocked} disabled>
        {props.icon}
      </Button>
    );
  }
  return (
    <ButtonAnchor
      variant="ghost"
      size="row"
      aria-label={props.label}
      title={props.hint ?? props.label}
      href={props.href}
      data-testid={props.testId}
    >
      {props.icon}
    </ButtonAnchor>
  );
}

export function RowActionLink(props: RowActionShape & { to: string }) {
  const blocked = props.reason ?? null;
  if (blocked !== null) {
    return (
      <Button variant="ghost" size="row" aria-label={props.label} title={blocked} disabled>
        {props.icon}
      </Button>
    );
  }
  return (
    <ButtonLink
      variant="ghost"
      size="row"
      aria-label={props.label}
      title={props.hint ?? props.label}
      to={props.to}
    >
      {props.icon}
    </ButtonLink>
  );
}


/* ── THE OVERFLOW, WHICH B14 RULE 15 HAS ASKED FOR SINCE IT WAS WRITTEN ─────
 *
 * The rule's last clause is *"Max 2 visible, then `…`"* and the product had no
 * `…` at all, so every table drew its whole action set and the second half of a
 * ratified rule was unenforceable. The units list drew FIVE glyphs in one cell
 * where its frame draws three.
 *
 * ⚠ **IT IS `<details>` AND NOT A HAND-ROLLED POPOVER, AND THAT IS THE DESIGN
 * RATHER THAN THE SHORTCUT.** The platform's disclosure already gives, for
 * free, every behaviour a menu written in React state has to be given and then
 * tested: it opens on Enter and on Space, it is in the tab order once, it
 * closes on Escape, and — the part that matters in THIS repository — **it
 * renders open-able markup under `renderToStaticMarkup`**, so a static suite
 * can read what is inside it. A `useState` menu renders as nothing at all to
 * `renderToStaticMarkup`, which is how a menu of four actions would become four
 * assertions that pass over an empty cell.
 *
 * ⚠ **THE PANEL IS ABSOLUTELY POSITIONED AND THAT IS ALLOWED.** The never-do
 * list forbids absolute positioning *"to achieve a LAYOUT that flex or grid
 * should do"*. A floating panel over a table row is not a layout; it is the one
 * thing absolute positioning is for. It is anchored to the RIGHT, because the
 * actions cell is the last column of every table that has one.
 */
export function RowActionsMore(props: {
  /** The trigger's accessible name — *More actions*, translated. Required for
   *  the same reason `RowAction.label` is: an icon with no name passes every
   *  text-absence check in the suite and is unusable without a mouse. */
  label: string;
  /** `RowMenuAction`s. Two or more, or the caller should have drawn the action
   *  itself — a menu holding one item is a button wearing a costume. */
  children: ReactNode;
}) {
  // ⚠ **IT OPENS UPWARD WHEN, AND ONLY WHEN, THE TABLE'S OWN SCROLL BOX WOULD
  // CUT IT (DEF-SHL-5378).** A list wider than its column now scrolls sideways
  // inside `[data-table-scroll]`, and `overflow-x: auto` clips the y axis too —
  // measured on Units at 1280: the last row's menu showed one item of four. So
  // on open, if the panel crosses the bottom of a box that clips and there is
  // room above, it flips. Outside a scrolling table nothing changes: `up` stays
  // false and the markup is the one it always was.
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [up, setUp] = useState(false);
  function onToggle(event: SyntheticEvent<HTMLDetailsElement>) {
    const details = event.currentTarget;
    const panel = panelRef.current;
    if (!details.open || panel === null) {
      setUp(false);
      return;
    }
    const box = details.closest<HTMLElement>("[data-table-scroll]");
    const clips = box === null ? "" : getComputedStyle(box).overflowX;
    if (box === null || !["auto", "scroll", "hidden", "clip"].includes(clips)) {
      return;
    }
    const boxRect = box.getBoundingClientRect();
    const boxBottom = boxRect.top + box.clientHeight;
    const panelRect = panel.getBoundingClientRect();
    const summaryTop = details.getBoundingClientRect().top;
    if (panelRect.bottom > boxBottom && summaryTop - boxRect.top >= panelRect.height) {
      setUp(true);
    }
  }
  return (
    <details className="relative inline-flex" data-row-more="" onToggle={onToggle}>
      <summary
        aria-label={props.label}
        title={props.label}
        className={
          "inline-flex h-8 w-8 cursor-pointer list-none items-center justify-center " +
          "rounded-md text-accent-text [&::-webkit-details-marker]:hidden " +
          "hover:bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)]"
        }
      >
        <MoreIcon />
      </summary>
      <div
        ref={panelRef}
        data-opens={up ? "up" : undefined}
        className={
          (up
            ? "absolute right-0 bottom-[calc(100%+var(--space-1))] z-40 flex min-w-48 "
            : "absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-48 ") +
          "flex-col border border-divider bg-surface py-1 shadow-md"
        }
      >
        {props.children}
      </div>
    </details>
  );
}

/**
 * One line of that menu: the SAME glyph the row would have drawn, and the word
 * beside it.
 *
 * ⚠ **THE WORD IS NOT OPTIONAL AND IT IS NOT A SECOND CONVENTION.** B14 rule 15
 * puts icons on the ROW because a row is scanned; inside an opened menu there
 * is nothing to scan and an icon-only column would be a puzzle. Every menu in
 * r10 is words. The glyph is kept so a clerk who learns `⇄` on one table
 * recognises it on the next.
 *
 * `reason` behaves exactly as it does on `RowAction` — BR-SHL-025: a control
 * that cannot act is disabled WITH its reason, never hidden.
 */
export function RowMenuAction(props: RowActionShape & { onClick: () => void }) {
  const blocked = props.reason ?? null;
  return (
    <button
      type="button"
      disabled={blocked !== null}
      title={blocked ?? props.hint ?? props.label}
      data-testid={props.testId}
      onClick={blocked === null ? props.onClick : undefined}
      className={MENU_ITEM + (props.danger === true ? " text-danger-700" : " text-text")}
    >
      {props.icon}
      <span>{props.label}</span>
    </button>
  );
}

/**
 * The same line of that menu, when the destination is a DOCUMENT rather than an
 * action — the bill's printable page, say.
 *
 * ⚠ **ADDED 2026-09-14 (`CR-101-BRC03`) HERE RATHER THAN IN THE SCREEN, WHICH
 * IS B14 RULE 36'S OWN MECHANISM.** The Billing blueprint moves *Print bill*
 * into the bill detail's `…` overflow, and `Print bill` has been an `<a href>`
 * since `CR-053` for a stated reason the screen records: *"an anchor is what
 * lets middle-click and open in new tab work on it"*. Routing it through
 * `RowMenuAction`'s `onClick` would have had the screen call `window.open`,
 * which loses both — a real regression dressed as a reuse.
 *
 * **It is `RowMenuAction` with one element changed.** Both now take their class
 * string from the same constant, so the two lines of one menu cannot drift into
 * two looks — which is the whole reason this is here and not in the screen.
 *
 * A blocked anchor renders as a DISABLED BUTTON rather than a dead link: there
 * is no `disabled` on `<a>`, and an anchor that silently does nothing is worse
 * than a control that says why (BR-SHL-025).
 */
export function RowMenuAnchor(props: RowActionShape & { href: string }) {
  const blocked = props.reason ?? null;
  if (blocked !== null) {
    return (
      <button
        type="button"
        disabled
        title={blocked}
        data-testid={props.testId}
        className={MENU_ITEM + " text-text"}
      >
        {props.icon}
        <span>{props.label}</span>
      </button>
    );
  }
  return (
    <a
      href={props.href}
      target="_blank"
      rel="noreferrer"
      title={props.hint ?? props.label}
      data-testid={props.testId}
      className={MENU_ITEM + " text-text no-underline"}
    >
      {props.icon}
      <span>{props.label}</span>
    </a>
  );
}

/** One line of an opened row menu — shared by `RowMenuAction` and
 *  `RowMenuAnchor` so the two cannot drift. */
const MENU_ITEM =
  "flex w-full cursor-pointer items-center gap-2 border-none bg-transparent " +
  "px-3 py-1.5 text-left font-body text-md leading-body " +
  "hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)] " +
  "disabled:cursor-not-allowed disabled:opacity-45";
