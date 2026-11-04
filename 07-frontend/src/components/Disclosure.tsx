// ── Trace ──────────────────────────────────────────────
// Change:   PO ruling 2026-08-24 — "Please pay attention to expand and collaps
//           compotent on UI - build it in Tailwind", and "under each expand -
//           detials of that are is displayed", sent with the MOV-01 move-in
//           screenshots that draw the pattern six times on one screen.
// Rules:    B14 rule 21 (new UI is Tailwind utilities and adds NO stylesheet
//           class — G31 enforces it) · B14 rule 12 (one toolbar grammar) ·
//           BR-SHL-025 (a control that cannot act is DISABLED WITH ITS REASON)
// Tests:    src/components/DisclosureEditAction.dom.test.tsx (the `action`
//           slot and the `card` variant, added 2026-09-28; this file carried
//           NO `Tests:` line before that, which is its own small finding)
// Impacts:  MOV-01 step 4 panels B–E; the request capture wizard; anywhere a
//           screen carries detail a clerk opens only when the customer asks ·
//           the New Connect review step's four groups, each with an `Edit ›`.
// ───────────────────────────────────────────────────────
//
// THE EXPAND/COLLAPSE ROW, ONCE.
//
// WHAT THE DESIGN ACTUALLY ASKS FOR, and it is not a generic accordion:
//
//   B · Rate schedules                        One per service · click to expand
//   ┌────────────────────────────────────────────────────────────────────────┐
//   │ [E] Residential Electric  Tiered · 3 blocks · 2 sizes  $18.50/mo Expand▾│
//   │ [W] Residential Water  Inclining block · 3 blocks     $12.00/mo Collapse▴│
//   │     BLOCK        RANGE              RATE                                │
//   │     Tier 1       0–2 kgal           $3.00/kgal            ← the detail  │
//   └────────────────────────────────────────────────────────────────────────┘
//
//   C · Charge codes   3 apply · 1 does not · $38.50 base            Expand ▾
//
// ⚠ THE LOAD-BEARING PROPERTY IS THAT COLLAPSING NEVER HIDES A NUMBER. Every
// closed row in MOV-01 still states its figure — `$18.50/mo`, `$38.50 base`,
// `6.25% state · 2.00% city franchise`, `Typical month ≈ $56.00 · first bill ≈
// $16.00`. What collapses is the DERIVATION, never the result. That is why
// `summary` and `value` sit on the HEADER and not inside `children`: a caller
// physically cannot fold a figure away, because the slot that would hide it
// does not exist. The screen's own sentence is the specification — *"Charge
// codes, taxes, and the worked month are collapsed — open them when the
// customer asks."* The clerk opens detail to EXPLAIN a number they can already
// read aloud, not to discover it.
//
// WHY A COMPONENT AND NOT A UTILITY STRING AT EACH CALL SITE:
//
//   * `aria-expanded` + `aria-controls` + a matching `id` are three things that
//     must agree, and nothing checks that they do. Generating the id here means
//     they cannot disagree. An accordion whose header does not announce its
//     state is unusable with a screen reader and looks perfect in a screenshot.
//   * `<details>/<summary>` was considered and REJECTED: it cannot put the
//     open/closed word on the RIGHT of a flex row with a value beside it
//     without fighting the marker, its animation story is worse, and Safari
//     still prints an expanded `<details>` differently. The native element buys
//     keyboard behaviour that a `<button>` already has for free.
//   * Two utilities filling one property are resolved at BUILD time, not by the
//     order a caller writes them — see the header of `buttonKit.ts`. So the
//     variants live here as whole strings, never as a base + an override.
//
// ⚠ NO STYLESHEET CLASS IS ADDED BY THIS FILE (B14 rule 21). Every class below
// is a Tailwind utility over the `@theme` tokens in `styles/tailwind.css`. This
// file is registered in `styles/route-b-migrated.txt` so `routeBUtilities.test`
// asks the stricter, compiler-backed question — does each utility generate a
// rule — rather than G31's "is it declared by a .css", which is false by
// design for a Tailwind file.

import { useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

/**
 * `section` is a page-level band (C · Charge codes). `row` is one line inside
 * a bordered list (a rate schedule). They differ in weight and rule, not in
 * behaviour — see the drawing in this file's header.
 *
 * ⚠ **`card` ADDED 2026-09-28 FOR THE NEW CONNECT REVIEW STEP**, which draws
 * four SEPARATE bordered boxes with gaps between them rather than one bordered
 * list with dividers (`step5-review.png`). That is arrangement, and B14 rule
 * 41 gives the drawn shape to the drawing; rule 44 keeps the border, the fill
 * and the type scale ours. A host stacks them with a gap; it is not a
 * `DisclosureList`.
 */
/**
 * ⚠ **`panel` — A FORM SECTION THAT FOLDS (CR-176-BRC10, B14 rule 36, opt-in).**
 * Add units draws *Names & numbers* and *Plan & start* as closed sections in
 * the panel's own frame, headed at section size, with the current choice and
 * a caret on the right and no *Expand* word (images 04 and 08 of
 * `05-prototype/add-units-redesign-2026-10-09/`). The other three variants are
 * untouched.
 */
export type DisclosureVariant = "section" | "row" | "card" | "panel";

const SHELL: Record<DisclosureVariant, string> = {
  section: "border-t border-t-divider py-4",
  row: "border-b border-b-divider last:border-b-0",
  card: "border border-divider bg-surface",
  panel: "border border-divider bg-surface",
};

const HEADER: Record<DisclosureVariant, string> = {
  // `w-full` + `text-left` because a <button> centres its content by default,
  // which silently right-aligns a title the moment a summary is short.
  section:
    "flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 bg-transparent px-0 py-1 text-left " +
    "hover:text-accent-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
  row:
    "flex w-full flex-wrap items-center gap-x-3 gap-y-1 bg-transparent px-4 py-3 text-left " +
    "hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
  card:
    "flex w-full flex-wrap items-baseline gap-x-2 gap-y-1 bg-transparent px-4 py-3 text-left " +
    "hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
  panel:
    "flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 bg-transparent px-5 py-5 text-left " +
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
};

const TITLE: Record<DisclosureVariant, string> = {
  section: "font-heading text-base font-semibold text-text",
  row: "font-heading text-sm font-semibold text-text",
  card: "font-heading text-base font-semibold text-text",
  panel: "font-heading text-h4 text-text",
};

const BODY: Record<DisclosureVariant, string> = {
  section: "pt-3",
  row: "px-4 pb-4",
  card: "px-4 pb-4",
  panel: "px-5 pb-5",
};

export interface DisclosureProps {
  /** The heading. Stays readable closed — it is what the clerk scans. */
  title: ReactNode;
  /** The one-line gist, shown closed AND open. In MOV-01 this is where the
   *  figures live: "3 apply · 1 does not · $38.50 base". Never fold a number
   *  into `children` that belongs here. */
  summary?: ReactNode;
  /** The right-hand figure, e.g. `$18.50/mo`. Rendered before the toggle word
   *  so the eye lands on the money, not on the control. */
  value?: ReactNode;
  /** A service badge or icon, before the title. */
  leading?: ReactNode;
  /** Something that is true of the panel as a whole — MOV-01 draws
   *  `1 exception raised` and `None selected` here. Shown closed. */
  status?: ReactNode;
  /** THE DETAIL. Rendered only when open, directly beneath the header. */
  children: ReactNode;
  /** Open on first render. Default closed — MOV-01's own instruction is that
   *  charge codes, taxes and the worked month arrive collapsed. */
  defaultOpen?: boolean;
  variant?: DisclosureVariant;
  /** BR-SHL-025: a panel with nothing behind it does not silently do nothing.
   *  Pass the REASON and the control disables itself carrying it — there is no
   *  boolean, so a caller cannot disable this without saying why. */
  unavailableReason?: string | null;
  /**
   * ⚠ **A CONTROL OF ITS OWN ON THE HEADER ROW — THE REVIEW STEP'S `Edit ›`.
   * ADDED 2026-09-28, OPT-IN, AND IT MOVES NOTHING EXISTING.**
   *
   * `step5-review.png` draws four groups and each carries an `Edit ›` that
   * goes back to that step. **It cannot live in `children`** — it has to be
   * reachable while the group is COLLAPSED, and `children` is unmounted then —
   * **and it cannot live inside the toggle**, because HTML forbids a button or
   * a link inside a button and a browser that tolerates it gives the clerk one
   * target that does two things.
   *
   * So it is rendered BESIDE the toggle, and the wrapper appears only when
   * something is passed: absent, the DOM is byte-for-byte what every existing
   * caller renders.
   *
   * ⚠ **THE KIT DOES NOT OWN THE DESTINATION OR THE WORDS.** It is a node —
   * `InlineLinkTo`, a `Button`, whatever the host's step needs — so the
   * address, the catalogue key and `Verb →`'s grammar (B14 rule 4) stay with
   * the screen that knows them.
   */
  action?: ReactNode;
}

export function Disclosure({
  title,
  summary,
  value,
  leading,
  status,
  children,
  defaultOpen = false,
  variant = "section",
  unavailableReason = null,
  action,
}: DisclosureProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  // One id, used by BOTH `aria-controls` and the region — so the pair cannot
  // drift apart the way two hand-written strings do.
  const bodyId = useId();
  const blocked = unavailableReason !== null && unavailableReason !== "";
  const isOpen = open && !blocked;

  const toggle = (
    <button
      type="button"
      aria-expanded={isOpen}
        aria-controls={bodyId}
        disabled={blocked}
        title={blocked ? unavailableReason : undefined}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        className={`${HEADER[variant]} disabled:cursor-not-allowed disabled:opacity-45`}
      >
        {leading !== undefined && <span className="shrink-0">{leading}</span>}
        <span className={TITLE[variant]}>{title}</span>
        {summary !== undefined && (
          <span className="text-sm text-neutral-700">{summary}</span>
        )}
        {/* `ml-auto` on a wrapper rather than on `value` itself: when the row
            wraps on a narrow viewport the figure and the toggle must travel
            together, or the word "Expand" ends up on a line of its own. */}
        <span className="ml-auto flex shrink-0 items-baseline gap-3">
          {status !== undefined && (
            <span className="text-xs text-neutral-700">{status}</span>
          )}
          {value !== undefined && variant !== "panel" && (
            <span className="font-heading text-sm font-semibold text-text">{value}</span>
          )}
          {variant === "panel" ? (
            <span className="text-base text-neutral-700" data-disclosure-state="">
              {value}
              <span aria-hidden="true" className="ml-1">
                {isOpen ? "▴" : "▾"}
              </span>
            </span>
          ) : (
            <span aria-hidden="true" className="text-sm font-medium text-accent-text">
              {isOpen ? t("common.disclosure.collapse") : t("common.disclosure.expand")}
              <span className="ml-1">{isOpen ? "▴" : "▾"}</span>
            </span>
          )}
        </span>
      </button>
  );

  return (
    <div className={SHELL[variant]}>
      {/* ⚠ THE WRAPPER APPEARS ONLY WHEN THERE IS SOMETHING TO PUT BESIDE THE
          TOGGLE, so every caller that predates `action` renders the button as
          a direct child exactly as before. `flex-1` on the toggle rather than
          a width: the action keeps its own width and the toggle takes the
          rest, so a long summary never pushes `Edit ›` off the row. */}
      {action === undefined ? (
        toggle
      ) : (
        <div className="flex items-center gap-3">
          <span className="min-w-0 flex-1">{toggle}</span>
          <span className="shrink-0 pr-4" data-disclosure-action="">
            {action}
          </span>
        </div>
      )}
      {/* Unmounted when closed, not merely hidden: these panels carry tables of
          rates and charge codes, and a screen with six of them would otherwise
          render — and pay for — every row a clerk never opens. */}
      {isOpen && (
        <div id={bodyId} className={BODY[variant]}>
          {children}
        </div>
      )}
    </div>
  );
}

/** The bordered container a `row` variant belongs in. Exported so the border
 *  radius and divider are declared ONCE — five features each writing their own
 *  wrapper is exactly the drift `RowActions` was created to end. */
export function DisclosureList({ children }: { children: ReactNode }) {
  // ⚠ NO CORNER RADIUS, AND THAT IS THE DESIGN, NOT AN OMISSION. `tailwind.css`
  // clears `--radius-*` and re-declares every key as 0 — "the Modernist system
  // is square (tokens.css: keep 0, do not fix)". My first draft wrote `rounded`
  // out of habit; `routeBUtilities.test.ts` failed it with "these render
  // NOTHING", because the theme declares no DEFAULT radius key at all. The
  // right fix was to delete it rather than reach for `rounded-md`, which does
  // compile and would still have drawn a square corner while telling the next
  // reader the design wanted a curve.
  return <div className="border border-divider bg-surface">{children}</div>;
}
