// ── Trace ──────────────────────────────────────────────
// Change:   `CR-135` `P1.8` of `05-prototype/06 Payments Page Blueprint.pdf` —
//           §03 frame 2·1b *Bulk* (p031–p033), read at 2.0. Its *To build* row:
//           *"The eligible count on the bar · **the per-row confirm** · a
//           consequence box"*, and its notes ④⑤ — *"Who is skipped, and why"*
//           and *"Per row · a clerk reverses payments, not a number"*.
// Rules:    B14 rule 11 (a consequence preview before a commit that writes
//           money) · rule 20 (one table tier — this composes `PlainTable`
//           rather than declaring a second) · rule 31 (no database id is the
//           visible value of a field) · rule 33 (a FACT caps at six words) ·
//           rule 36 (where the kit lacks a piece, ADD IT TO THE KIT) ·
//           rule 43 (a piece of UI is a COMPONENT)
// Screens:  2·1b the payments bulk confirm · 7·1 Debtors (the same gap)
// Tests:    src/components/selectionRowPreview.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// A BULK CONFIRM THAT TAKES ONLY A COUNT IS THE DEFECT THIS EXISTS FOR
// ══════════════════════════════════════════════════════════════════════════
// The blueprint files it as a GAP, in its own words: *"`bulkActionRefusal`
// returns "allowed" if ANY selected row can be acted on. Select five payments
// where one is reversible and four are not, and the button is live, bright, and
// says nothing. The confirm that follows takes **only a count** — it asks
// "Reverse 5 payments?" when it is about to reverse one and silently refuse
// four. You find out afterwards, per row."*
//
// And it names the fix as a DISPLAY problem rather than a logic one: *"The
// product already knows which four. `bulkReverseRefusal(row)` computes a reason
// per row — not an admin, not cleared, already a reversal — and the bar throws
// that away for a single yes/no. **The fix is not new logic; it is showing what
// is already computed.**"*
//
// ⚠ **SO THIS COMPONENT COMPUTES NOTHING.** It takes rows that already carry
// their verdict and draws them. Every question of WHICH rows and WHY belongs to
// the screen that owns the rule, because that is the screen whose single-row
// control must agree with it — a bulk Reverse that refused something the row
// Reverse allows would be two answers to one rule on one page.
//
// ⚠ **IT IS IN THE KIT AND NOT IN `paymentsBulk.tsx` FOR TWO REASONS, AND THE
// SECOND IS THE ONE THAT MATTERS.** B14 rule 43 asks for a component because a
// second host cannot reuse what is not addressable — and 7·1's own bulk bar has
// exactly this gap over write-off and collections. The second: `features/
// payments/` is NOT on `styles/route-b-migrated.txt`, and the stylesheets stand
// at their rule-21 ceiling, so a table written there could add no class at all.
import type { ReactNode } from "react";

import { PlainTable } from "./Surfaces";

export interface SelectionPreviewRow {
  id: string;
  /** The HUMAN-FACING number — a payment number, an account number. **Never a
   *  uuid** (B14 rule 31), and this panel is read by the clerk who is about to
   *  press the button. */
  label: ReactNode;
  /** What this row belongs to: the account it was taken on, the premises it
   *  sits at. */
  owner: ReactNode;
  /** Already formatted by the caller — this component formats no money
   *  (`BR-SHL-023`: ONE money path). */
  amount?: ReactNode;
  /** What will happen to THIS row, in the customer's terms — *"Reversed"*, or
   *  *"Skipped — already a reversal"*. Note ⑦ of 2·1b. */
  outcome: ReactNode;
  /**
   * Whether this row is one the run will NOT act on.
   *
   * ⚠ **IT DRIVES A `data-` HOOK AND A MUTED WEIGHT, NEVER A COLOUR ALONE.**
   * A skipped row that differs only in colour tells a colour-blind clerk
   * nothing, and the row's own sentence already says what happened — the
   * weight is a second channel, not the message.
   */
  skipped?: boolean;
}

export interface SelectionRowPreviewProps {
  /** The four column headings, already translated. `amount` omitted draws
   *  three columns. */
  columns: { label: string; owner: string; amount?: string; outcome: string };
  rows: readonly SelectionPreviewRow[];
  /** The group's accessible name — a table of unlabelled rows is unreadable
   *  without sight of the heading above it. */
  caption: string;
}

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

export function SelectionRowPreview(props: SelectionRowPreviewProps) {
  const withAmount = props.columns.amount !== undefined;
  return (
    <PlainTable data-selection-preview="">
      {/* A real `<caption>`, visually hidden: the heading above this table is
          the screen's, and a screen reader landing on the table itself needs
          to be told what it is looking at. */}
      <caption className="sr-only">{props.caption}</caption>
      <thead>
        <tr>
          <th scope="col">{props.columns.label}</th>
          <th scope="col">{props.columns.owner}</th>
          {withAmount && <th scope="col">{props.columns.amount}</th>}
          <th scope="col">{props.columns.outcome}</th>
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row) => (
          <tr
            key={row.id}
            data-preview-row={row.id}
            data-preview-skipped={row.skipped === true ? "true" : "false"}
          >
            <td>{row.label}</td>
            <td>{row.owner}</td>
            {withAmount && <td className="tabular-nums">{row.amount}</td>}
            <td className={row.skipped === true ? MUTED : undefined}>{row.outcome}</td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

export default SelectionRowPreview;

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p14 `P1.8` · §03 frame 2·1b (p031–p033) rendered at 2.0
// generated: 2026-09-22 by LANE P1-C
// checklist: A✔ B=n/a(no endpoint) C✔ D=n/a E✔(the bulk Reverse and Refund confirms both draw it) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/components/selectionRowPreview.dom.test.tsx · G31 (listed on src/styles/route-b-migrated.txt in this commit) · routeBUtilities.test.ts
// exceptions: E3 it composes `PlainTable` rather than declaring its own table, so B14 rule 20's single tier holds without a second decision
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
