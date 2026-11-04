// ── Trace ──────────────────────────────────────────────
// Change:   the NEW CONNECT REDESIGN of 2026-09-28 — **THE READ-ONLY FACT
//           BLOCK, IN THE KIT.** Drawn three times in the five steps:
//           `step2-premise.png`'s *This plan*, `step4-charges.png`'s summary
//           strip, `step5-review.png`'s *At a glance*.
// Rules:    **B14 rule 43** (a piece of UI is built as a COMPONENT) · rule 36
//           (extend the kit; where the kit lacks a piece, ADD IT TO THE KIT) ·
//           rule 44 (the drawing says WHAT is on screen; our UI standard says
//           HOW it is built) · rule 31 (no database id is ever the visible
//           value of a field) · rule 33 (a LABEL ≤ 3 words, a FACT ≤ 6) · rule
//           21 (Tailwind utilities; this file is on
//           `src/styles/route-b-migrated.txt`) · hard rule 2 (money DISPLAYS
//           to 2 decimals)
// Tests:    src/components/FactBlock.dom.test.tsx
// Impacts:  src/features/customers/disconnect/DisconnectFacts.tsx (promoted —
//           see below) · 07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY IT EXISTS — A PO RULING, NOT A TIDY-UP
// ══════════════════════════════════════════════════════════════════════════
// The PO rejected read-only values drawn as disabled input boxes, verbatim:
// *"we dont display it like this at other places we will ahve to follow UI
// rules"*. A disabled box says *you could type here, but not yet*; a fact says
// *this is what it is*. They are different statements and only one of them is
// true of a plan's code or a build's service-point count.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · IT IS A PROMOTION, NOT A NEW COMPONENT
// ══════════════════════════════════════════════════════════════════════════
// `features/customers/disconnect/DisconnectFacts.tsx` was built on 2026-09-25
// and its own lifecycle block asked for exactly this, in as many words:
//
//     E3 it lives in `features/customers/disconnect/` and not in the kit. Only
//        this wizard draws it today; B14 rule 36 says to put a piece a SECOND
//        screen needs into the kit, and promoting it the day a second screen
//        wants one is one import line. Stated so the next lane moves it rather
//        than copying it.
//
// A second screen wants one. So this is that file's markup, moved, and
// `DisconnectFacts` is now a delegation with its props unchanged — its two
// call sites and the `data-facts` handle its test and its walkthrough read did
// not move a pixel.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · TWO SHAPES, AND THE DRAWINGS ASKED FOR BOTH
// ══════════════════════════════════════════════════════════════════════════
//   * `card`  — a bordered card of label-over-value pairs, wrapping. What the
//               disconnect wizard already draws, byte-for-byte.
//   * `strip` — the same pairs DIVIDED by hairlines, which is what
//               `step4-charges.png` and `step5-review.png` draw: seven and
//               nine cells across, each ruled off from the next.
//
// ⚠ **THE HAIRLINES ARE THE GRID'S GAP, NOT A BORDER PER CELL.** `gap-px` over
// a `bg-divider` container with `bg-bg` cells shows the container through the
// gaps, in BOTH directions — so a row that wraps at 1280 gets its rule between
// the two rows as well, which a per-cell `border-l` cannot do without knowing
// where the wrap lands.
//
// ⚠ **ONE LABEL TREATMENT, AND `step2-premise.png` DRAWS ANOTHER.** That frame
// puts *CODE · STATUS · EFFECTIVE* in small uppercase while steps 4 and 5 draw
// theirs in sentence case. Two of the three agree, and B14 rule 44 gives our
// UI standard the say over how a thing is BUILT, so there is one label
// treatment here rather than a knob. Recorded because it is a divergence from
// a drawing and not an oversight.
import type { ReactNode } from "react";

/**
 * One pair.
 *
 * `value` is a node so a figure arrives through `MoneyCell` rather than as a
 * hand-formatted string — hard rule 2 is DISPLAY 2 decimals, and a six-decimal
 * balance interpolated into JSX is `DEF-CUS-4999`.
 */
export interface Fact {
  /** Stable key. ⚠ **NEVER RENDERED** — B14 rule 31. */
  id: string;
  /** ≤ 3 words, no sentence (B14 rule 33). From the catalogue. */
  label: string;
  value: ReactNode;
}

export type FactBlockVariant = "card" | "strip" | "rows";

/**
 * ⚠ **THE ARBITRARY GRID TEMPLATE IS THE KIT'S EXISTING IDIOM, NOT A NEW
 * NUMBER.** `RecordGrid` writes `repeat(auto-fill,minmax(120px,1fr))` and the
 * card below writes `auto-fit,minmax(180px,1fr)` because that is what it
 * already rendered on 2026-09-25. Tailwind has no scale for a grid template,
 * so an arbitrary value is the only spelling there is; reusing the two the kit
 * already has keeps it at two.
 *
 * **WHY 120px FOR THE STRIP.** `step5-review.png` puts NINE cells across. A
 * 1440 staff screen gives about 1,150px of content, and 9 × 120 = 1,080 fits;
 * at the 1280 minimum it wraps rather than squeezing, which is the rule —
 * stack, never shrink.
 */
const SHELL: Record<FactBlockVariant, string> = {
  card: "m-0 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-x-6 gap-y-3 border border-divider bg-bg p-4",
  strip:
    "m-0 grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-px border border-divider bg-divider",
  // `CR-171-BRC10` P2.32 (images 45–46, the move-in Review): label LEFT on a
  // tinted column, value right, one ruled row per fact. The fixed-column
  // variants below have no `rows` entry of their own — a row table has one
  // column of pairs by definition, so `columns` is ignored for it.
  rows: "m-0 border border-divider bg-bg",
};

/**
 * ⚠ **A FIXED-COLUMN STRIP LETS ITS LAST FACT SPAN THE REST OF ITS ROW
 * (`DEF-RAT-9312`).** The hairlines are the shell's `bg-divider` showing
 * through `gap-px`, so a row the facts do not fill showed the SHELL there — a
 * dark-grey block (13 facts in three columns left two empty cells beside
 * *Exclusivity group* on the discount details page). The last cell takes
 * `col-span-<the cells left in its row>`, so the row is filled with the cell's
 * own surface and nothing is added inside the `<dl>` (which may hold only
 * `dt`/`dd` groups). ⚠ NOT `grid-column-end: -1`: with an automatic start that
 * MOVES the cell to the last column and leaves the gap before it — tried first
 * and seen in the browser. Literal class names, so the compiler emits them.
 */
const LAST_SPAN: Readonly<Record<number, string>> = { 2: "col-span-2", 3: "col-span-3", 4: "col-span-4" };

/** The class that lets the LAST of `count` facts fill its row, or "". */
export function lastFactSpan(count: number, columns: number | undefined): string {
  if (columns === undefined || count === 0) return "";
  const left = count % columns;
  return left === 0 ? "" : (LAST_SPAN[columns - left + 1] ?? "");
}

/** `columns={4}` — the same shells with the grid fixed at four across. */
const FOUR_ACROSS: Record<FactBlockVariant, string> = {
  card: "m-0 grid grid-cols-4 gap-x-6 gap-y-3 border border-divider bg-bg p-4",
  strip: "m-0 grid grid-cols-4 gap-px border border-divider bg-divider",
  rows: SHELL.rows,
};

/** `columns={3}` — three across (the charge-code *How it bills* block,
 *  `05-prototype/charge-codes-2026-10-01/images/06`: two rows of three). */
const THREE_ACROSS: Record<FactBlockVariant, string> = {
  card: "m-0 grid grid-cols-3 gap-x-6 gap-y-3 border border-divider bg-bg p-4",
  strip: "m-0 grid grid-cols-3 gap-px border border-divider bg-divider",
  rows: SHELL.rows,
};

const CELL: Record<FactBlockVariant, string> = {
  card: "",
  strip: "bg-bg px-3 py-2",
  rows: "grid grid-cols-6 border-b border-divider last:border-b-0",
};

/** The label and value halves. `card` and `strip` stack them (label over
 *  value); `rows` sets them side by side, the label on a tinted sixth. */
const TERM: Record<FactBlockVariant, string> = {
  card: "m-0 text-base text-neutral-700",
  strip: "m-0 text-base text-neutral-700",
  rows: "m-0 col-span-1 bg-neutral-100 px-3 py-2 text-base text-neutral-700",
};
const VALUE: Record<FactBlockVariant, string> = {
  card: "m-0 mt-1 text-base font-semibold text-neutral-900",
  strip: "m-0 mt-1 text-base font-semibold text-neutral-900",
  rows: "m-0 col-span-5 px-3 py-2 text-base text-neutral-900",
};

/**
 * A BLOCK OF FACTS — label above value, read-only.
 *
 * ⚠ **IT WRAPS RATHER THAN SHRINKS.** Nothing here carries a fixed height, so
 * a long address and a German label both grow the block rather than clipping
 * it. A fixed pixel height on anything holding text is the never-do list's
 * entry for exactly this.
 */
export function FactBlock(props: {
  facts: readonly Fact[];
  /** The DOM handle a walkthrough finds this block by. */
  name: string;
  /** Absent is `card` — byte-for-byte what `DisconnectFacts` rendered. */
  variant?: FactBlockVariant;
  /** A FIXED four-across grid where a drawing draws one (the one-time bill's
   *  account card — DEF-BIL-8318). Absent, the block wraps by width exactly
   *  as before. */
  columns?: 3 | 4;
}) {
  const variant = props.variant ?? "card";
  const shell =
    props.columns === 4 ? FOUR_ACROSS[variant] : props.columns === 3 ? THREE_ACROSS[variant] : SHELL[variant];
  // ⚠ NO `aria-label` HERE, DELIBERATELY. A `<dl>` has no widget role, so a
  // name on it is dropped by the accessibility tree — a thing that renders and
  // means nothing, which is hard-won law 2's other face. The block is named by
  // the heading above it (`Panel`'s `title`, `BandHeading`), which is how every
  // drawing places it.
  return (
    <dl className={shell} data-facts={props.name}>
      {props.facts.map((fact, index) => (
        <div
          key={fact.id}
          className={
            index === props.facts.length - 1 && variant === "strip"
              ? `${CELL[variant]} ${lastFactSpan(props.facts.length, props.columns)}`.trim()
              : CELL[variant]
          }
          data-fact={fact.id}
        >
          <dt className={TERM[variant]}>{fact.label}</dt>
          <dd className={VALUE[variant]}>{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the NEW CONNECT REDESIGN of 2026-09-28 · 05-prototype/new-connect-redesign-2026-09-28/{step2-premise,step4-charges,step5-review}.png · the PO on read-only values drawn as disabled boxes · B14 rules 21, 31, 33, 36, 43, 44 · hard rule 2 · DisconnectFacts.tsx's own exception E3
// generated: 2026-09-28 by lane COMPONENTS
// checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E=DisconnectFacts delegates here; the New Connect step lanes consume it F✔ G✔ H=n/a
// gates: tsc · vitest src/components/FactBlock.dom.test.tsx · vitest src/features/customers/DisconnectWizard.test.tsx (the promotion must move nothing) · routeBUtilities (this file is on src/styles/route-b-migrated.txt) · G31
// exceptions:
//   E1 `step2-premise.png` draws its labels in small uppercase and this renders
//      sentence case, per §3. A divergence from a drawing, stated rather than
//      silently followed or silently ignored.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
