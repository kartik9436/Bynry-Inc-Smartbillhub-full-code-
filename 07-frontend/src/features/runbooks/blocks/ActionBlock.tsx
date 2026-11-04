// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 10 of the twelve.
// Screens: RBS-006-R5 · R9 · R12 · R13 · R15 · R18 · R19.
// Rules: B14 rule 6 (danger tier) · rule 4 (button grammar) · rule 33 ·
//        `BR-RBS-030` (closing a period stays a named person's act).
// ───────────────────────────────────────────────────────
// ONE button with a tier and an enabling condition.
//
// ⚠ **A DISABLED BUTTON MUST SAY WHY, AND THE TYPE MAKES IT IMPOSSIBLE NOT TO.**
// `ActionPayload` is a union: `enabled: false` REQUIRES `reason`, so `tsc`
// refuses a disabled control with no explanation. `RBS-006-R9`'s own caption is
// the case — *"Close period stays disabled until this list is empty. It says
// why: 3 items open."* — and hard-won law 2's 2026-09-05 mirror is what the
// alternative costs: on that day the customer portal had two working doors out
// of eight, five of them greyed out over holds that had expired days earlier,
// and G13 could not see any of it because it asks whether a prop is PASSED,
// never whether a refusal is still TRUE.
//
// ⚠ THE REASON IS THE `title` AND THE ACCESSIBLE DESCRIPTION, not a tooltip
// only a mouse can reach — a refusal half the readers cannot get to is half a
// refusal.
import { Button } from "@/components/Button";

import type { ActionPayload } from "./types";

export function ActionBlock(props: { payload: ActionPayload; onAct: () => void }) {
  const { payload } = props;
  const reason = payload.enabled ? undefined : payload.reason;
  return (
    <div className="flex flex-col gap-1" data-block="action">
      <div>
        <Button
          variant={payload.tier}
          onClick={props.onAct}
          disabled={!payload.enabled}
          title={reason}
          aria-describedby={reason === undefined ? undefined : "runbook-action-reason"}
          data-action-tier={payload.tier}
        >
          {payload.label}
        </Button>
      </div>
      {reason !== undefined && (
        <p
          id="runbook-action-reason"
          className="m-0 text-base text-neutral-700"
          data-action-reason=""
        >
          {reason}
        </p>
      )}
    </div>
  );
}
