// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 9 of the twelve.
// Screens: RBS-006-R4 · R6 · R13.  Rules: B14 rule 20 · 31 · 36.
// ───────────────────────────────────────────────────────
// Label · value. `PlainTable` (`components/Surfaces.tsx`) is the kit's
// key–value table: no header, no toolbar, no pager.
//
// ⚠ `RBS-006-R13` REGION 4 IS WRONG ABOUT ITS OWN COMPONENT and the sheets'
// preamble is the standard to apply — *"a sheet and its frame cannot disagree;
// if one is wrong, both are"*. It declares a `DataTable` whose first column is
// row-action icons, and its rows are label-and-value: it is THIS block.
// `09-component-inventory.md` Part 4 §9 records the finding.
import { PlainTable } from "@/components/Surfaces";

import { ReportValueCell } from "./ReportValueCell";
import type { BlockContext, FactsPayload } from "./types";

export function FactsBlock(props: { payload: FactsPayload; ctx: BlockContext }) {
  return (
    <section data-block="facts">
      {props.payload.heading !== undefined && (
        <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
          {props.payload.heading}
        </h5>
      )}
      <PlainTable>
        <tbody>
          {props.payload.rows.map((row) => (
            <tr key={row.id} data-fact-row="">
              <th scope="row" className="text-left font-normal text-neutral-700">
                {row.label}
              </th>
              <td className="text-right">
                <ReportValueCell value={row.value} ctx={props.ctx} />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </section>
  );
}
