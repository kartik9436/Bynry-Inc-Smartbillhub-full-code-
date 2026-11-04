// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 11 of the twelve.
// Screens: RBS-006-R20.  Rules: B14 rule 15 (and the RULED divergence below) ·
//          rule 20 · rule 36 · `12-the-contract.md` §6 (the thirteen ports).
// ───────────────────────────────────────────────────────
// Accept / keep on a records row, each mapping to a port or an engine act.
//
// ⚠ **TEXT BUTTONS, AND IT IS A RULED DIVERGENCE FROM B14 RULE 15 RATHER THAN A
// BREACH OF IT.** Rule 15 says row actions are ICONS with tooltips, never text
// links, and its vocabulary is closed at nine verbs. `RBS-006-R20` draws two
// text buttons in a table cell — *Accept theirs →* and *Keep ours* — and
// `09-component-inventory.md` Part 4 §3 settles why that is right: neither is
// one of rule 15's nine verbs, and **an icon cannot carry WHICH of two values is
// being kept**. The precedent is already shipped in Integrations, whose
// `MappingRow` draws *Change* / *Map it* and whose `DecisionCard` draws *Accept
// the change · Keep ours · Ask the City*, both as text buttons.
//
// **So the rule this file embodies is: a DECISION is not a row action.** A
// Records table may carry ONE decision column of text buttons where the choice
// is between named values. Written down here and in `08-screen-layouts.md` so
// two screens cannot quietly answer it differently.
import { Button } from "@/components/Button";

import { ReportTable } from "./ReportTable";
import type { BlockContext, ReportRow, RowDecisionsPayload } from "./types";

export function RowDecisionsBlock(props: {
  payload: RowDecisionsPayload;
  ctx: BlockContext;
  /** What a decision DOES. Required — a decision column whose buttons do
   *  nothing is the dead-control shape this block's own docstring warns about. */
  onDecide: (rowId: string, choiceId: string) => void;
}) {
  const decide = (row: ReportRow) => (
    <span className="flex gap-2">
      {props.payload.choices.map((choice) => (
        <Button
          key={choice.id}
          variant="secondary"
          size="sm"
          onClick={() => props.onDecide(row.id, choice.id)}
          data-decision={choice.id}
        >
          {choice.label}
        </Button>
      ))}
    </span>
  );
  return (
    <section data-block="row_decisions">
      <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
        {props.payload.heading}
      </h5>
      <ReportTable
        caption={props.payload.heading}
        columns={props.payload.columns}
        rows={props.payload.rows}
        ctx={props.ctx}
        trailing={{ label: props.payload.choices.map((c) => c.label).join(" · "), render: decide }}
      />
    </section>
  );
}
