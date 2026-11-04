// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · P2.23 — *"The grain line."* Built from
//          `05-prototype/09 Reports Build Brief.pdf` p024 (2·1a, the line under
//          the title, note ⑩) and p013 (the P2.23 row), read as RENDERED
//          IMAGES per B14 rule 42.
// Rules:   B14 rule 33 (a FACT is ≤ 6 words; RATIONALE is ZERO words on screen)
//          · B14 rule 32 (a screen has a description budget) ·
//          B14 rule 43 (a piece of UI used twice is a COMPONENT).
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT IT IS, AND THE ONE THING IT MUST NOT BECOME                        ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// *"One row per account."* Four words, under the title, on every report. The
// brief's own row says what kind of sentence it is: **"A FACT in four words,
// not rationale"**. It does not explain why the report groups that way, it does
// not say what the reader should do with it, and it never grows a second
// clause — B14 rule 33 puts rationale at zero words on screen, and a grain line
// that starts explaining is the first sentence of a paragraph.
//
// ⚠ **THE DRAWING PUTS THREE FACTS ON THIS LINE AND ONLY ONE OF THEM IS MINE.**
// p024 note ⑩ reads *"One row per account · Billing calendar · based on today's
// customer details"* and names three tasks: the grain (`P2.23`, this file), the
// billing calendar (`P2.25`) and the as-is/as-was basis (`P2.19`). The other
// two are lane REP-P2-MODEL's and are NOT drawn here as placeholders: a line
// reading *"One row per account · —"* would be a control saying nothing, which
// is the shape this whole phase exists to remove. The component takes the other
// two as optional props so that landing them is an argument rather than a
// rewrite of this file.
//
// ⚠ **A REPORT THAT DOES NOT STATE ITS GRAIN RENDERS NOTHING HERE.** The server
// sends `grain` as a CODE and omits it where it has none. A wrong grain line is
// worse than no grain line, because a reader believes it — and the obvious
// wrong answer was ready to hand: `datasets.py` gives the AR ageing's dataset
// the grain *"one payment allocation"*, which is true of the dataset and false
// of the report, whose rows are one per debtor.
import type { ReactNode } from "react";

import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * The facts, in the drawing's order, with the empty ones dropped.
 *
 * Pure and exported so *"none states it twice"* — the brief's own outcome — is
 * a property with a test rather than a thing somebody looked at once.
 */
export function grainFacts(parts: readonly (string | null | undefined)[]): string[] {
  const seen = new Set<string>();
  const facts: string[] = [];
  for (const part of parts) {
    const words = (part ?? "").trim();
    if (words === "" || seen.has(words)) {
      continue;
    }
    seen.add(words);
    facts.push(words);
  }
  return facts;
}

/**
 * *"One row per account"*, under the report's title.
 *
 * `grain` is the server's CODE (`account`, `bill`, `method`, …) and the
 * sentence is the catalogues', in eleven languages — B14 rule 35: a catalogue
 * is written in its own language and never translated from English by whoever
 * happened to be building the screen.
 */
export function ReportGrainLine(props: {
  /** The server's grain code, or undefined when this report states none. */
  grain: string | undefined;
  t: Translator;
  /** `P2.25`'s billing-or-calendar fact, when that lane lands it. */
  calendar?: string;
  /** `P2.19`'s as-is/as-was fact, when that lane lands it. */
  basisOfAttributes?: string;
  /**
   * **DRAW THE FACTS ONLY, FOR A ROLL-UP THAT IS ALREADY A `.fin-rollup`**
   * (`DEF-REP-7011`).
   *
   * The Product Owner counted four stacked lines above the register's first
   * row and asked for two. The brief had already said so — p025 note ⑩:
   * *"Grain · calendar · basis, **in one line** under the title"* — and the
   * product drew the window on one line and the grain on the next.
   *
   * ⚠ **OPT-IN, SO NOTHING ELSE MOVES.** Absent renders the `<p>` this
   * component has always rendered, with its own `data-grain`. Present renders
   * the SAME items with no wrapper, so the caller's roll-up supplies the
   * middot and the baseline — the separator is `.fin-rollup-item`'s own
   * `::before`, which needs a `.fin-rollup-item` sibling before it and gets
   * one either way.
   *
   * ⚠ **WHICH FACTS, AND IN WHAT ORDER, IS STILL THIS FILE'S DECISION.** Only
   * where they render has moved; a caller that built the spans itself would
   * be the 120-lines-inline shape B14 rule 43 was ratified against.
   */
  inline?: boolean;
}): ReactNode {
  const grain =
    props.grain === undefined || props.grain === ""
      ? null
      : props.t(`reports.grain.${props.grain}`, { defaultValue: "" });
  const facts = grainFacts([grain, props.calendar, props.basisOfAttributes]);
  if (facts.length === 0) {
    return null;
  }
  const items = facts.map((fact) => (
    <span key={fact} className="fin-rollup-item" data-grain-fact={fact}>
      {fact}
    </span>
  ));
  if (props.inline === true) {
    // ⚠ **`data-grain` TRAVELS WITH THE FACTS, NOT WITH THE WRAPPER.** There
    // is no wrapper here, and a test — or a walkthrough — that asked for the
    // attribute and found nothing would report a grain line missing from a
    // header that draws it perfectly (hard-won law 7's *looking at the wrong
    // thing*). It goes on the first item.
    return (
      <>
        <span className="fin-rollup-item" data-grain={props.grain}>
          {facts[0]}
        </span>
        {items.slice(1)}
      </>
    );
  }
  return (
    <p className="fin-rollup" data-grain={props.grain}>
      {items}
    </p>
  );
}
