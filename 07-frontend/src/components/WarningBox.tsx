// ── Trace ──────────────────────────────────────────────
// Story:    US-INT-027 (EP-INT-07) — the dated warning, CR-069 wave H task H3.
//           Screens: S142 (frame `54.1`) · S7 (the attention strip)
// Rules:    B14 rule 36 (the captured packs give layout and detail, r10's
//           UI-RULES.md gives the VISUAL STYLE, and the SHARED COMPONENT KIT
//           is how you comply — PO 2026-09-04) · B14 rule 32 (one sentence
//           per section; no rule id or internal code in clerk-facing copy) ·
//           B14 rule 21 + its per-file clause (a Tailwind utility is emitted
//           ONLY for a file listed in `styles/route-b-migrated.txt`) ·
//           BR-INT-042 (a warning DAYS AHEAD, with the date)
// Tests:    src/components/WarningBox.dom.test.tsx  ⚠ `.dom.`, and this line
//           said `.test.tsx` until the file was renamed to opt into jsdom.
//           A citation to a test nobody wrote reads exactly like a citation to
//           one that passes (hard-won law 1) — G95 is the check for that on the
//           backend, and there is none on the front end, so this one was found
//           by hand rather than by a gate.
// Impacts:  src/features/integrations/ConnectionDetailPage.tsx ·
//           04-docs/05-modules/13-integrations/09-component-inventory.md
//           (row `WarningBox`, which named this before it existed)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE COMPONENT INVENTORY NAMED THIS BOX BEFORE ANY CODE EXISTED**, and
// `ConnectionDetailPage.tsx`'s own trailer has carried the absence in writing
// since wave C: *"the WarningBox (wave H) and BudgetLine (wave G) slots of
// template I3 are NOT rendered — a stated absence closed by default."* That
// note is what made this a slot to fill rather than a component to invent, and
// it is why the file lands in the KIT and not beside the one screen that needs
// it today: `09-component-inventory.md` row `WarningBox` gives the border and
// the amber, and B14 rule 36 says the kit is how a screen complies.
//
// ⚠ **THE TONE CLASS IS A WHOLE STRING PER TONE, NOT AN INTERPOLATION.**
// Tailwind's scanner cannot see `border-${tone}`; `routeBUtilities.test.ts`
// refuses an interpolated class in a migrated file by name, and a class the
// compiler never emitted renders as NOTHING while every `toContain` assertion
// still passes. `ConsequenceBox.tsx` carries the same warning for the same
// reason — this is that lesson obeyed, not restated.
//
// ⚠ **THIS FILE IS ON `route-b-migrated.txt`.** It was added there in the same
// commit that created it. Without that line every utility below is a class no
// stylesheet declares and the box renders as unstyled text — with `tsc`, eslint
// and every test green.
import type { ReactNode } from "react";

/** How much time is left, which is the only thing that changes the look.
 *
 *  `soon`    — the thing has not happened yet and there is time to act. Amber.
 *  `now`     — it has happened; something a utility depends on has stopped.
 *
 *  ⚠ There is deliberately no `info` tone. A box that is sometimes merely
 *  interesting is a box people stop reading, and the next one they skip is the
 *  one that mattered. If it does not need an action, it is not this component.
 */
export type WarningTone = "soon" | "now";

const BASE = "flex max-w-[720px] items-start gap-3 border-l-4 px-4 py-3 text-base";

// Whole strings per tone — see the warning above.
//
// ⚠ **THIS SAID `border-amber-600` AND IT RENDERED AS NOTHING.** That is the
// class `09-component-inventory.md` writes against this box, and it is a
// TAILWIND DEFAULT-PALETTE name — which this product does not have. Its palette
// is the tokens in `styles/tokens.css` (`--color-warning-700: #a65d0a`), so
// `amber-600` was never emitted into the bundle and the box drew with no
// coloured border at all.
//
// **Nothing could have caught it except looking.** The class IS in the DOM, so
// `toContain("border-amber-600")` passed; `tsc` and eslint have no opinion on a
// class name; and B14 rule 21's per-file clause is about a file missing from
// `route-b-migrated.txt`, which this file is not. It was found in the browser
// walkthrough by reading a screenshot, which is hard-won law 6 word for word.
// `DEF-INT-4236`.
//
// `now` moves to the danger tier because B14 reserves that tier for a state a
// person has to act on rather than notice.
const WARNING_TONE: Record<WarningTone, string> = {
  soon: `${BASE} border-warning-700 bg-[color-mix(in_srgb,var(--color-warning-700)_8%,transparent)]`,
  // ⚠ **`-700`, NOT A BARE `danger` — AND THIS LINE IS `DEF-SHL-4281`
  // (fixed 2026-09-08 by the CR-089 wave I lane, which met it on a real
  // screen).** It read `border-danger` and `var(--color-danger)`. This theme
  // declares `--color-danger-100/500/700` and **no bare `--color-danger`**, so
  // the border fell back to the text colour (`rgb(32, 30, 29)`) and the tint
  // was `color-mix` over an invalid colour, which is fully transparent. B14
  // rule 6's danger tier — the tone reserved for a state a person must ACT on
  // — therefore drew with no colour at all, which is the comment three lines
  // above this one happening again in the same file.
  // The shade matches `soon` above deliberately: both are a 4px rail plus an
  // 8% tint of THE SAME token, so the pair reads as one scale.
  now: `${BASE} border-danger-700 bg-[color-mix(in_srgb,var(--color-danger-700)_8%,transparent)]`,
};

export interface WarningBoxProps {
  tone: WarningTone;
  /** The sentence that carries the DATE, in the tenant's own format.
   *
   *  ⚠ A `ReactNode` because frame `54.1` bolds the half that is the
   *  instruction — ***Needs re-authorising by 12 September.** After that, bills
   *  stop going out.* — and because the DATE must arrive already formatted by
   *  the caller through `DateCell`'s `formatDate`. This component must never
   *  format a date itself: BR-SHL-023 keeps ONE formatting path, and a second
   *  one here is how a screen ends up showing `2026-09-12` to a tenant who
   *  asked for `09/12/2026`. */
  sentence: ReactNode;
  /** The reassurance under the box — *"It takes about a minute and nothing else
   *  changes — the history stays."* One sentence (B14 rule 32); omit it when
   *  there is nothing true to say. */
  note?: ReactNode;
  /** The action. Frame `54.1` draws **Re-authorise now**; a box with no way to
   *  act on it is a box that trains people to ignore boxes. */
  action?: ReactNode;
  /** The hook a test or a browser walkthrough finds this box by. */
  "data-warning"?: string;
}

/**
 * The dated warning — frame `54.1`.
 *
 * One sentence, one reassurance, one action. It does not decide WHEN it should
 * appear and it does not compute how many days are left: the server settles
 * that once (`apps/integrations/expiry.py`) so that S142 and the S7 strip
 * cannot drift apart on which side of a boundary a date falls.
 */
export function WarningBox(props: WarningBoxProps) {
  return (
    <div className="flex max-w-[720px] flex-col gap-2">
      <div
        className={WARNING_TONE[props.tone]}
        // `role="status"` rather than `alert`: a screen reader should reach
        // this in the page's own order, not have the reading interrupted. The
        // credential lapses in eleven days; it is not a fire.
        role="status"
        data-warning={props["data-warning"] ?? props.tone}
        data-warning-tone={props.tone}
      >
        <p className="m-0 text-neutral-900">{props.sentence}</p>
      </div>
      {props.note !== undefined && (
        <p className="m-0 max-w-[720px] text-body text-neutral-700" data-warning-note="">
          {props.note}
        </p>
      )}
      {props.action !== undefined && <div className="flex gap-2">{props.action}</div>}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-INT-027 (EP-INT-07 — the dated warning) · frame 54.1 · 09-component-inventory.md row `WarningBox`
// generated: 2026-09-06 by the CR-069 wave H build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(ConnectionDetailPage renders it; the S7 strip reads the same `expiry` block) F✔ G✔ H=n/a
// gates: vitest src/components/WarningBox.test.tsx · G31 (rule 21 — utilities only, no stylesheet class added) · routeBUtilities (no interpolated class) · tsc
// exceptions: no `info` tone, deliberately — see the WarningTone docstring
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
