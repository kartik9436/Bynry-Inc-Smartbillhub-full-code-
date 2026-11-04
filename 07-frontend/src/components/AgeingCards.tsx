// ── Trace ──────────────────────────────────────────────
// Change:   `P0.11` of `05-prototype/06 Payments Page Blueprint.pdf` — *"Kit:
//           ageing cards and the stage rail … Two small components the drawings
//           already use."* Outcome: *"Payments draws the runner's rail and the
//           debtor bands from the kit, not from copies."*
// Rules:    B14 rule 36 (*"where the kit lacks a piece, ADD IT TO THE KIT — one
//           component, one visual decision, every screen — rather than
//           hand-rolling it in the screen"*) · B14 rule 32 (a card carries one
//           fact and one sentence, no more) · B14 rule 21 (Tailwind utilities,
//           no stylesheet class — this file is listed in the same commit) ·
//           B14 rule 37 (a figure drawn in a wireframe is an ILLUSTRATION: the
//           blueprint's $6,712.26 and 75.7% are examples, and nothing here
//           computes or assumes either)
// Screens:  7·1 Debtors (the five debtor bands) — and any list that ages money
// Tests:    src/components/ageingCards.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS IS, AND WHY IT IS NOT A `KPIStrip`
// ══════════════════════════════════════════════════════════════════════════
// The blueprint draws the debtor screen with TWO rows of figures and says in as
// many words that they are different things:
//
//   · the tiles above — *owed · overdue · over 60 · being chased* — are the
//     answer to *how bad is it*, and they are READ;
//   · the ageing bands below are *"five cards, each a filter … lighter than the
//     tiles above, and they narrow the list"*, and they are PRESSED.
//
// A `KPIStrip` is the first kind. Drawing the second through it is what the
// product does today: five ageing figures rendered at tile weight, with a
// SEPARATE `<select>` beside the search box doing the filtering they look like
// they should do. Two controls for one question, and the one that looks like a
// control is the one that is not.
//
// ⚠ **AMENDED 2026-09-28 — `KPIStrip` CAN NOW BE PRESSED, AND THIS COMPONENT
// IS STILL THE RIGHT ONE HERE (hard-won law 1: the comment changes with the
// fact, in the commit that changes it).** A PO ruling of that date gave the
// Accounts register four status tiles that each narrow the list, so the strip
// grew an opt-in `press` on a tile. **The split above survives with one word
// changed: it was never really about pressability, it is about WEIGHT.** This
// screen draws TWO rows — heavy tiles that are read, lighter tone-ruled cards
// that are pressed — and that second row is what these are. Accounts draws
// ONE row, so its figures and its filters are the same objects and belong in
// the strip. **Do not read this heading as *"a tile cannot filter"* any more,
// and do not replace these cards with a pressable strip:** the tone rule, the
// lighter treatment and the band vocabulary are this screen's, not the
// strip's.
//
// ⚠ **THE TONE IS THE BAND'S, NOT THE FIGURE'S.** `90+ DAYS` is drawn in the
// danger tier when it holds `$0.00`, because the tier names the AGE and a
// clerk reads the row by position. A tone computed from the amount would make
// the strip change shape as money moved, which is the opposite of a scale.
//
// ⚠ **EVERY CLASS IS A WHOLE STRING PER TONE, NEVER AN INTERPOLATION.**
// Tailwind's scanner cannot see `border-t-${tone}`; `routeBUtilities.test.ts`
// refuses an interpolated class in a listed file by name, and a class the
// compiler never emitted renders as nothing while every `toContain` assertion
// still passes.
import type { ReactNode } from "react";

/** How old the money in this band is — never how much of it there is. */
export type AgeingTone = "neutral" | "warning" | "danger";

/** The coloured rule along the top of a card, and nothing else about it. */
const TONE_RULE: Record<AgeingTone, string> = {
  neutral: "border-t-divider",
  warning: "border-t-warning-700",
  danger: "border-t-danger-500",
};

export interface AgeingBand {
  /** The value this card filters the list to. Never a database id (B14 rule 31). */
  id: string;
  /** The band's own name, from the caller's catalogue (`G15`). */
  label: string;
  /** The money, already rendered — a `MoneyCell`, or the caller's stated
   *  absence when no currency code could be read. This component formats
   *  nothing: BR-SHL-023 gives the product ONE money path and it is not here. */
  value: ReactNode;
  /** One sentence under the figure — *"75.7% of the debt"* — or `null` when the
   *  caller has nothing true to say. B14 rule 32 allows exactly one. */
  detail: ReactNode | null;
  tone: AgeingTone;
}

export interface AgeingCardsProps {
  /** The group's accessible name. Five unnamed buttons in a row are unusable
   *  without a mouse, which is the same failure B14's note on rule 15 records. */
  label: string;
  bands: readonly AgeingBand[];
  /** The band the list is narrowed to, or `null` for all of them. */
  selectedId: string | null;
  /** Called with the band's id, or `null` when the selected card is pressed
   *  again — which is how a clerk clears the filter without hunting for an ✕. */
  onSelect: (id: string | null) => void;
}

export function AgeingCards(props: AgeingCardsProps) {
  return (
    <div
      className="mb-3 grid grid-cols-[repeat(auto-fit,minmax(9rem,1fr))] gap-2"
      role="group"
      aria-label={props.label}
      data-ageing-cards=""
    >
      {props.bands.map((band) => {
        const selected = band.id === props.selectedId;
        return (
          <button
            key={band.id}
            type="button"
            // ⚠ `aria-pressed` AND NOT `aria-selected`: these are toggle
            // buttons, not tabs, and a screen reader announcing "tab" for a
            // filter tells a clerk the list will be replaced rather than
            // narrowed.
            aria-pressed={selected}
            data-band={band.id}
            onClick={() => props.onSelect(selected ? null : band.id)}
            className={`flex cursor-pointer flex-col items-start gap-0.5 border border-divider border-t-2 bg-surface px-3 py-2 text-left ${
              TONE_RULE[band.tone]
            } ${selected ? "outline outline-2 outline-text" : ""}`}
          >
            <span className="font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
              {band.label}
            </span>
            <span className="text-h4 font-extrabold tabular-nums">{band.value}</span>
            {band.detail !== null && (
              <span className="text-btn-sm text-neutral-600">{band.detail}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p13 `P0.11` · §03 screen 7·1 rendered at 2.0 (the five bands, their tones and their share line)
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B=n/a(no endpoint) C✔ D=n/a E✔(OutstandingsTab renders it) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/ageingCards.dom.test.tsx · G31 (this file is on src/styles/route-b-migrated.txt) · routeBUtilities.test.ts
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
