// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 1 of the twelve.
// Screens: RBS-006-R2 · R3 · R9 · R12 · R13.  Rules: B14 rule 36 · rule 6.
// ───────────────────────────────────────────────────────
// Composition, not invention: the shape is `components/VerdictBand.tsx`, in the
// SHARED kit. This file's only job is to turn one frozen payload into its props
// and to hand the commit control down — which is why the tier is the CALLER's:
// B14 rule 6 makes a control that closes or sends the danger tier, and only the
// screen knows whether this run's button does either.
import { VerdictBand } from "@/components/VerdictBand";

import type { VerdictPayload } from "./types";

export function VerdictBlock(props: { payload: VerdictPayload; action?: React.ReactNode }) {
  return (
    <VerdictBand
      word={props.payload.word}
      tone={props.payload.tone}
      count={props.payload.count}
      detail={props.payload.detail}
      action={props.action}
    />
  );
}
