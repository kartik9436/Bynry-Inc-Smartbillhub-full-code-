// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 36 (PO 2026-09-04) — MOVED here from
//           `features/work/SegmentedControl.tsx`, and merged with the private
//           `Segmented` that `features/integrations/ConnectModal.tsx` had
//           written for itself. Two implementations of one control is what
//           rule 36 calls *"the kit ignored"*.
// Defect:   DEF-3722 — the kit had no segmented control, so two lanes wrote
//           two on consecutive days with different borders, different type and
//           different selected states. Work's selected segment was `bg-bg`,
//           which is the PAGE colour: on a panel it read as nothing at all.
// Rules:    r10 `.seg` / `.seg-opt` (styles.css lines 166-177 — the visual
//           authority, transcribed declaration by declaration below) · B14
//           rule 21 (Tailwind utilities; on route-b-migrated.txt from its
//           first commit) · rule 5 (a segment is not a third button size — it
//           is a different control) · BR-SHL-025 (a control this deployment
//           cannot honour yet is VISIBLE and DISABLED WITH ITS REASON)
// Tests:    src/components/SegmentedControl.test.tsx ·
//           src/features/work/PartsPage.test.tsx ·
//           src/features/integrations/ConnectModal.dom.test.tsx
// Impacts:  features/work/PartsPage.tsx · features/integrations/ConnectModal.tsx
//           · 07-frontend/src/styles/route-b-migrated.txt (this file's line,
//           and the old path's line leaves in the same commit)
// ───────────────────────────────────────────────────────
//
// r10's SEGMENTED CONTROL, DECLARATION FOR DECLARATION
// ────────────────────────────────────────────────────
//     .seg      display:inline-flex; overflow:hidden          → inline-flex overflow-hidden
//               border:1px solid var(--color-divider)         → border border-divider
//               border-radius: var(--radius-md)               → (0 in this theme; no utility)
//     .seg-opt  display:inline-flex; align-items:center       → inline-flex items-center
//               gap:6px                                       → gap-1.5
//               padding:7px 12px                              → py-[7px] px-3
//               font-size:13px                                → text-base
//               cursor:pointer                                → cursor-pointer
//     .seg-opt + .seg-opt { border-left: 1px … }              → border-l border-divider,
//                                                                cancelled on the first
//     :has(input:checked) { background:accent; color:bg }     → bg-accent text-bg
//     :not(:checked):hover { background: text @ 7% }          → hover:bg-[color-mix…]
//
// ⚠ **THE SELECTED SEGMENT IS ACCENT-FILLED, AND THAT IS THE CORRECTION.**
// Work's control painted the selected segment `bg-bg` — `#f3f2f2`, the page's
// own background — so on a white panel the chosen segment was a very slightly
// grey word beside two other words, and on the page background it was
// invisible. r10 fills it with the accent and reverses the text, which is the
// same inversion the chips and the primary button use. Nothing else in this
// product signals "this one is chosen" with a 4% grey.
//
// ⚠ **7px IS AN ARBITRARY VALUE AND THAT IS CORRECT.** 7 is not on the 4px
// scale; the VALUE is arbitrary, not the utility. `buttonKit.ts` writes
// `px-[14.4px]` for the same reason and records it. Rounding to `py-2` would
// move every segment in the product by 1px to satisfy a preference nobody
// stated.
//
// ⚠ **AND THE TOKENS ARE THE THEME'S NAMES, NOT TAILWIND'S STOCK ONES.**
// `tailwind.css` sets `--color-*: initial`, so `border-slate-300` compiles to
// NOTHING while tsc, eslint and every `toContain` pass (DEF-INT-3630).
// `routeBUtilities.test.ts` compiles every class here against the real theme.
//
// WHY ONE COMPONENT WITH A `purpose`, AND NOT TWO EXPORTS
// ──────────────────────────────────────────────────────
// `Surfaces.tsx` splits `InlineLink` from `InlineLinkTo` because one needs
// `onClick` and the other needs `to` — different PROPS, so one component would
// take neither properly. Here the props are identical and only the ARIA role
// differs: Work's strip switches which list you are looking at (tabs), the
// connect modal's rows choose a value inside a form (radios). One prop names
// which, every other decision is shared, and a caller cannot get the visual
// half wrong by picking the wrong one.
import type { ReactNode } from "react";

export interface Segment {
  id: string;
  label: string;
  /**
   * BR-SHL-025 — why this segment cannot be chosen yet. A segment with a
   * reason renders disabled AND says why; a segment with none is live. There
   * is no third state, because "greyed out and silent" is the state that
   * makes a person click twice and then file a defect.
   */
  disabledReason?: string;
  /**
   * Disabled with NO sentence — the manifest decided, not the deployment.
   * The connect modal's *How to sign in* draws all three methods and lights
   * the one the provider uses; the other two are facts about the provider,
   * not refusals owed an explanation.
   */
  disabled?: boolean;
  /**
   * A count drawn after the label in a lighter weight — the Crews page's
   * *Technicians 4 · Crews 2 · Contractors 1* (`CR-168-BRC10` images 25, 27,
   * 28). Opt-in, under B14 rule 36's one-optional-prop move: absent renders
   * byte-for-byte what every existing caller renders. Zero renders.
   */
  count?: number;
}

/** r10 `.seg` — the strip. */
const STRIP = "inline-flex overflow-hidden border border-divider";

/** r10 `.seg-opt` — one segment. The divider is cancelled on the first. */
const SEGMENT =
  "inline-flex items-center gap-1.5 border-l border-divider first:border-l-0 " +
  "px-3 py-[7px] text-base";

/** `:has(input:checked)` — ink reversed out of the accent. */
const CHOSEN = "bg-accent text-on-accent font-semibold";

/** `:not(:has(input:checked)):hover` — the 7% tint r10 uses everywhere. */
const RESTING =
  "cursor-pointer text-text bg-transparent " +
  "hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]";

/** The button kit's own disabled presentation, so one product has one. */
const UNAVAILABLE = "cursor-not-allowed bg-transparent text-text opacity-45";

export function SegmentedControl(props: {
  segments: readonly Segment[];
  active: string;
  onSelect?: (id: string) => void;
  /** What the whole control chooses between, for a screen reader. */
  label: string;
  /**
   * The id of a VISIBLE element that already says what this control chooses
   * between. When it is given, the control points at that element instead of
   * carrying `label` as its own `aria-label`.
   *
   * ⚠ **ONE OPTIONAL PROP RATHER THAN A SECOND SEGMENTED CONTROL
   * (`DEF-CWP-3996`, B14 rule 36).** The portal's `SegmentedChoice` needs a
   * label a SIGHTED person can read — four bare `On`/`Off` pairs shipped on
   * `CWP-025` floating above a table with nothing saying what they switch. An
   * `aria-label` cannot fix that and, worse, HIDES it: every accessibility
   * check that looks for an accessible name passes on the broken control, so
   * a checker reports it as labelled. The visible label belongs to the
   * caller's layout; what belongs HERE is the wire that ties the two together,
   * because a floating word beside a control is not a label to anything that
   * reads the page.
   *
   * The same move `ChipTone` records for `danger` and `TotalRow` for `signed`:
   * a union or a signature widened by one name, never a second component.
   */
  labelledBy?: string;
  /**
   * `view` (default) switches what is shown — tablist/tab. `choice` picks a
   * value inside a form — radiogroup/radio.
   */
  purpose?: "view" | "choice";
  /** Names the control for a test or a walkthrough: `data-segmented="cadence"`. */
  name?: string;
  /** BR-SHL-025 — a role that may read but not write: every segment disabled. */
  readOnly?: boolean;
  className?: string;
}): ReactNode {
  const purpose = props.purpose ?? "view";
  // ⚠ DEF-WRK-3646 — THE REASON IS RENDERED, NOT ONLY A `title`.
  // The control's first draft passed `disabledReason` to `title` alone and
  // said in its own comment that the sentence was "the control's own title AND
  // its visible text below". There was no text below. A tooltip does not exist
  // on a touch screen, so the segment was a grey word that did nothing and
  // never said why. The test could not tell the two apart, because a `title`
  // attribute IS the sentence.
  const reasons = props.segments
    .filter((segment) => segment.disabledReason !== undefined)
    .map((segment) => ({ id: segment.id, reason: segment.disabledReason as string }));
  return (
    <div className={props.className}>
      <div
        role={purpose === "view" ? "tablist" : "radiogroup"}
        // One name or the other, never both: `aria-labelledby` wins wherever
        // both are set, so carrying the string as well would leave a second,
        // silently-ignored copy of the label to drift out of step.
        {...(props.labelledBy === undefined
          ? { "aria-label": props.label }
          : { "aria-labelledby": props.labelledBy })}
        data-segmented-control=""
        data-segmented={props.name}
        className={STRIP}
      >
        {props.segments.map((segment) => {
          const chosen = segment.id === props.active;
          const stopped =
            props.readOnly === true || segment.disabled === true || segment.disabledReason !== undefined;
          return (
            <button
              key={segment.id}
              type="button"
              role={purpose === "view" ? "tab" : "radio"}
              {...(purpose === "view" ? { "aria-selected": chosen } : { "aria-checked": chosen })}
              aria-disabled={stopped ? true : undefined}
              // ⚠ THE CHOSEN SEGMENT IS NEVER `disabled`, EVEN READ-ONLY. A
              // disabled element is removed from the tab order and reads as
              // absent, and the chosen segment is the one fact the control is
              // there to state. The connect modal relied on exactly this for
              // its sign-in row and it travels with the component now.
              disabled={stopped && !chosen}
              title={segment.disabledReason}
              data-segment={segment.id}
              data-segment-disabled={stopped ? "true" : undefined}
              onClick={() => {
                if (!stopped && props.onSelect !== undefined) props.onSelect(segment.id);
              }}
              className={`${SEGMENT} ${chosen ? CHOSEN : stopped ? UNAVAILABLE : RESTING}`}
            >
              {segment.label}
              {segment.count !== undefined && (
                <span data-segment-count="" className="tabular-nums font-normal opacity-75">
                  {segment.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {reasons.map((entry) => (
        // B14 rule 33 — a refusal sentence is five or six words. The catalogue
        // holds the words; this only decides that a person can read them
        // without a pointing device. `data-segment-reason` is what the test and
        // the walkthrough read, and neither can be satisfied by an attribute
        // (the test strips tags; the walkthrough reads innerText).
        <p key={entry.id} data-segment-reason={entry.id} className="mt-1 text-base text-neutral-600">
          {entry.reason}
        </p>
      ))}
    </div>
  );
}

export default SegmentedControl;

// ── Lifecycle ─────────────────────────────────────────────
// packet: B14 rule 36 (PO 2026-09-04) · DEF-3722 · r10 styles.css `.seg` · 09-component-inventory.md "three things the staff kit does not have"
// generated: 2026-09-04 by the CR-070 wave C build lane, as features/work/SegmentedControl.tsx · MOVED into the kit and merged with the connect modal's private copy 2026-09-04 by the style-conformance lane
// checklist: A=n/a(a control) B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest src/components/SegmentedControl.test.tsx + src/features/work + src/features/integrations · routeBUtilities.test.ts (every utility here compiles against the real theme) · the cr070-c walkthrough reads the chosen segment's COLOUR from computed style
// exceptions: the Issue log segment on Work > Parts ships DISABLED WITH ITS REASON — parts issued against a job are wave N's (WM-22)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
