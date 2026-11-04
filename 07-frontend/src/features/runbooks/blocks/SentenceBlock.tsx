// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 8 of the twelve.
// Screens: RBS-006-R4 (*Read this aloud*) · R6 (the stop card) · R11.
// Rules: B14 rule 36 · rule 32 · rule 33 (and see the stated absence below).
// ───────────────────────────────────────────────────────
// ⚠ THE WORD BUDGET IS A STATED ABSENCE, NOT AN OVERSIGHT — and it is stated in
// `OutcomeCard`'s own docstring, in `09-component-inventory.md` Part 4 §1 (which
// MEASURED it: 28 boxes, 14–88 words, median 25.5, all over rule 33's six-word
// cap) and in `08-screen-layouts.md`. The decision is owed by wave `C3`, which
// draws `RBS-004`'s Outcome box. **This block counts nothing and truncates
// nothing**, deliberately: silently trimming would make the divergence
// invisible instead of settleable.
import { OutcomeCard } from "@/components/OutcomeCard";

import type { SentencePayload } from "./types";

export function SentenceBlock(props: { payload: SentencePayload; action?: React.ReactNode }) {
  return (
    <OutcomeCard tone={props.payload.tone} label={props.payload.label} action={props.action}>
      {props.payload.text}
    </OutcomeCard>
  );
}
