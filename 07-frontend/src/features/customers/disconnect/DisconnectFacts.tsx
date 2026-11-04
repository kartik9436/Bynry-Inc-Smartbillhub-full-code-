// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 — **the fact strip**,
//           drawn at the top of step 1 (`The account`) and step 4 (`This cut`)
//           and on both master variants of each.
// Rules:    B14 rule 31 (no database id is ever the visible value of a field) ·
//           rule 33 (a LABEL ≤ 3 words) · rule 21 (Tailwind utilities; this
//           file is on `src/styles/route-b-migrated.txt`) · rule 43 · hard rule
//           2 (money DISPLAYS to 2 decimals)
// Tests:    ../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ⚠ **IT IS NOT A TABLE AND IT IS NOT `RecapBox`.** The drawings put a white
// card inside the grey panel holding four to six label-over-value pairs laid
// out across the width — *Customer · Address · Balance · Services* on step 1,
// *Account · Address · Reason · Services · Cut date · Work order* on step 4.
// A `<dl>`, because that is what it is: label→value pairs with no header row
// and no column a clerk scans. `RecapBox` is label-LEFT/value-RIGHT, one row
// per fact, with a rule above an outcome — that is step 4's DEPOSIT block, and
// it renders a real `RecapBox` two panels down rather than a second copy of
// this.
//
// ⚠ **`ITEM 3.8 — EACH FACT APPEARS ONCE.** The five-step wizard repeated the
// account, the address and the balance on every step; a strip is cheap enough
// to repeat and that is exactly the trap. It is drawn on TWO steps and on
// neither of the two in between, which is the drawing's decision and not this
// component's: the component renders what it is handed.
// ⚠ **PROMOTED TO THE KIT ON 2026-09-28, AND THIS IS NOW A DELEGATION.** The
// exception below asked for exactly that — *"promoting it the day a second
// screen wants one is one import line. Stated so the next lane moves it rather
// than copying it."* The New Connect redesign draws three of them, so the
// markup now lives in `components/FactBlock.tsx` and this file keeps only its
// NAME and its props: two call sites, one test assertion on `data-facts` and
// one walkthrough selector, all unmoved.
//
// It is kept rather than deleted because deleting it would edit two live step
// files in the same commit as a kit change. **Prefer `FactBlock` in new code.**
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";

/** One pair. `label` is three words or fewer (B14 rule 33) and `value` is a
 *  node so a figure can arrive through `MoneyCell` rather than as a
 *  hand-formatted string — hard rule 2 is DISPLAY 2 decimals, and a six-decimal
 *  balance interpolated into JSX is `DEF-CUS-4999`.
 *
 *  ⚠ An alias of the kit's `Fact`, so the two cannot drift into two shapes. */
export type DisconnectFact = Fact;

/**
 * The facts card.
 *
 * ⚠ **IT WRAPS RATHER THAN SHRINKS.** `auto-fit` with a 180px floor means four
 * facts lay out across 1440 and across 1280 alike, and a fifth or a sixth — the
 * master variant adds *Own debt* and *Transferred up* — wraps onto a second row
 * instead of squeezing six values into a width that fits four. Nothing here
 * carries a fixed height, so a long address and a German label both grow the
 * card rather than clipping (§10 of the UI method). That behaviour is
 * `FactBlock`'s `card` variant, which is where the classes now live.
 */
export function DisconnectFacts(props: { facts: readonly DisconnectFact[]; name: string }) {
  return <FactBlock facts={props.facts} name={props.name} variant="card" />;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 · B14 rules 21, 31, 33, 43
// generated: 2026-09-25 by lane WIZARD
// gates: tsc · vitest src/features/customers/DisconnectWizard.test.tsx ·
//        routeBUtilities (this file is on src/styles/route-b-migrated.txt)
// exceptions:
//   E3 CLOSED 2026-09-28 by lane COMPONENTS. It read: "it lives in
//      `features/customers/disconnect/` and not in the kit. Only this wizard
//      draws it today; B14 rule 36 says to put a piece a SECOND screen needs
//      into the kit, and promoting it the day a second screen wants one is one
//      import line. Stated so the next lane moves it rather than copying it."
//      The New Connect redesign is that second screen. The markup is
//      `components/FactBlock.tsx`; this file is the delegation, so no call site
//      and no test handle moved.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
