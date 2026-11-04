// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 6 · lane FIX-7 — DEF-WRK-9671. A job the
//           certification rule raises on a meter in the warehouse stands on no
//           premises; where the meter carries a location note, that note is
//           where the job is.
// Rules:    CLAUDE.md hard rule 8 (an address is the PREMISES'; the note is the
//           asset's own words, read at use) · B14 rule 43 (a piece of UI is a
//           component) · rule 31 (no id on screen)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import { Dash } from "@/features/customers/customersShared";

/**
 * A job's *where* cell: the premises' address, else the asset's stored-at
 * note, else a dash — never a blank. ONE component so the order list, the
 * rule's Jobs tab, Approvals and a technician's Jobs tab cannot disagree.
 * `suffix` is what the Orders list draws after an address (the account number).
 */
export function WhereCell(props: {
  premise: { address: string | null } | null;
  storedAt?: string | null;
  suffix?: ReactNode;
}) {
  if (props.premise !== null && props.premise.address) {
    return (
      <span>
        {props.premise.address}
        {props.suffix}
      </span>
    );
  }
  if (props.storedAt) {
    return <span data-stored-at="">{props.storedAt}</span>;
  }
  return <Dash />;
}
