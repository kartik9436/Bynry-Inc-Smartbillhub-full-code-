// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — the *From the account*, *From
//           the asset* and Confirm summary panels (images 17, 19, 20): a
//           heading over label → value rows, labels in one column.
// Rules:    B14 rules 21 (Tailwind; listed in route-b-migrated.txt), 31 (no
//           database id is a value), 33 (a label ≤ 3 words), 43 (a piece of
//           UI is a component), 44 (our spacing and type scale).
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NOT `RecapBox` AND NOT `FactBlock`, AND THE DRAWING DECIDES WHICH.**
// `RecapBox` is the accent-bordered read-back BEFORE a commit, values pushed
// to the right edge; `FactBlock` is a grid of cards. Images 17, 19 and 20 draw
// neither: a plain `Panel` with its heading and two left-aligned columns. The
// `Panel` is the kit's; only the two columns are this file's.
import type { ReactNode } from "react";

import { Panel } from "@/components/Panel";

export interface RaiseFact {
  label: string;
  value: ReactNode;
  /** The hook a walkthrough finds this row by. */
  name: string;
}

export function RaiseFacts(props: { title: string; facts: readonly RaiseFact[]; name: string }) {
  return (
    <Panel as="section" title={props.title} data-raise-facts={props.name}>
      <dl className="m-0 flex flex-col gap-2">
        {props.facts.map((fact) => (
          <div key={fact.name} className="flex gap-4" data-raise-fact={fact.name}>
            <dt className="m-0 w-36 shrink-0 text-base text-neutral-700">{fact.label}</dt>
            <dd className="m-0 text-base text-neutral-900">{fact.value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
