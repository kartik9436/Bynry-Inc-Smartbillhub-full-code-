// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-012 · US-CUS-013 · US-CUS-014 · US-CUS-015 — the S22 quick
//           actions. `ACC-S14` (accounts blueprint p208) commits every one of
//           the thirteen to "a recap before it commits", and R4 (p154–174)
//           draws the same box on all thirteen.
// Rules:    B14 rule 11 (a consequence preview before a commit that writes
//           money, service state or a legal notice) · B14 rule 21 (a new
//           component is Tailwind utilities and adds NO stylesheet class) ·
//           B14 rule 32 (one sentence per section) · B14 rule 33 (a LABEL is
//           three words; RATIONALE is zero words on screen) · B14 rule 36 +
//           rule 38 (if the kit genuinely lacks a piece the drawing needs, ADD
//           IT TO THE KIT as an opt-in, so nothing existing moves)
// Tests:    src/components/RecapBox.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS IN THE KIT AND NOT IN THE ONE FEATURE THAT NEEDS IT TODAY
// ══════════════════════════════════════════════════════════════════════════
// **This repo already holds THREE private answers to this one question**, and
// none of them can see the others because an import names a PATH (`G86` clause
// (c), and the fold that brought `ConsequenceBox` here for the same reason):
//
//   · `features/customers/JobIntakeWizard.tsx` — a local `ReviewRow`, label
//     ABOVE value, four call sites.
//   · `features/customers/depositCapability.tsx` — `DepositReviewRows`, its own
//     shape again, read by the Move-in wizard.
//   · `.met-preview-list` — a stylesheet class, read by `AccountDetailPage` and
//     `MoveOutWizard`.
//
// A fourth private copy is how a product stops looking like one product. So the
// shape R4 draws thirteen times lands HERE, once.
//
// ⚠ **NOTHING EXISTING IS MIGRATED ONTO IT IN THIS COMMIT, DELIBERATELY.** The
// three above are read by live screens with their own tests, and re-pointing
// them is a visual change to four wizards on the authority of a component move
// — which is exactly the blast radius rule 38 says no single lane owns. They
// are REPORTED (`DEF-SHL-5123`) and left alone.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE DRAWING ASKS FOR, AND WHAT IT IS NOT
// ══════════════════════════════════════════════════════════════════════════
// R4's box is label-LEFT / value-RIGHT, one row per fact, with a RULE above a
// final bold row carrying the outcome — *"Balance after this adjustment
// $2,000.00"*, *"Account status after this  Closed"*, *"Still outstanding after
// this  $1,910.00"*.
//
// **That is not `ConsequenceBox` and it must not be folded into it.**
// `ConsequenceBox` says ONE SENTENCE about what will happen; this enumerates
// the FIGURES that will change. Two shapes under one name is `DEF-CWP-3655`.
// **Where a quick action needs the sentence as well, it renders a real
// `ConsequenceBox` beside this** — R4's *"Two things the server will not manage,
// and says so now rather than after"* is exactly that, and it is composed, not
// re-implemented.
import type { ReactNode } from "react";

/** One fact the commit will change. `label` is three words (B14 rule 33). */
export interface RecapRow {
  label: string;
  /** A `ReactNode` so a figure can arrive through `MoneyCell` rather than as a
   *  hand-formatted string — hard rule 2 is DISPLAY 2 decimals, and
   *  `DEF-CUS-4999` was a six-decimal balance interpolated into JSX two inches
   *  from the same figure rendered correctly. */
  value: ReactNode;
  /** The hook a walkthrough finds this row by. Defaults to nothing. */
  testId?: string;
}

export interface RecapBoxProps {
  /** R4 writes two: *"What pressing the button will do"* on a commit that
   *  changes service state, *"What this does to the account"* on one that
   *  changes money. Both are the drawing's words and neither is generated. */
  title: string;
  rows: readonly RecapRow[];
  /** The bold row under the rule — the one figure the clerk reads back. Absent
   *  where the drawing draws no total (`ACC-Q08` Print bill, `ACC-Q13` Add
   *  note), and absent means the rule is not drawn either. */
  outcome?: RecapRow;
  /** Anything that belongs INSIDE the box under the figures — R4 puts a
   *  `ConsequenceBox` here on `ACC-Q03` and `ACC-Q09`. */
  children?: ReactNode;
  "data-recap"?: string;
}

const ROW = "flex items-baseline justify-between gap-4 border-b border-b-divider py-2 last:border-b-0";

/**
 * The figures a commit will change, read back before it commits.
 *
 * ⚠ **`<dl>` AND NOT A TABLE.** These are label→value pairs, not a grid a
 * clerk sorts or scans in columns; a table would promise a header row that the
 * drawing does not draw and a screen reader would announce one that is not
 * there.
 */
export function RecapBox(props: RecapBoxProps) {
  return (
    <div
      className="border border-accent p-4"
      role="note"
      data-recap={props["data-recap"] ?? ""}
    >
      <p className="m-0 mb-2 text-sm font-bold text-neutral-900">{props.title}</p>
      <dl className="m-0">
        {props.rows.map((row) => (
          <div className={ROW} key={row.label} data-recap-row={row.testId ?? row.label}>
            <dt className="m-0 text-sm text-neutral-700">{row.label}</dt>
            <dd className="m-0 text-right text-sm text-neutral-900">{row.value}</dd>
          </div>
        ))}
      </dl>
      {props.outcome !== undefined && (
        <div
          className="mt-2 flex items-baseline justify-between gap-4 border-t-2 border-t-neutral-900 pt-2"
          data-recap-outcome={props.outcome.testId ?? ""}
        >
          <span className="text-sm font-bold text-neutral-900">{props.outcome.label}</span>
          <span className="text-right text-sm font-bold text-neutral-900">
            {props.outcome.value}
          </span>
        </div>
      )}
      {props.children !== undefined && <div className="mt-4">{props.children}</div>}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave J · ACC-S14 (accounts blueprint p208) · R4 p154–174 · 14-ui-conventions.md rules 11, 21, 32, 33, 36, 38
// generated: 2026-09-12 by the CR-094 wave J build lane
// checklist: A✔ B✔ C✔ D=n/a(no endpoint) E✔(AccountQuickActionForm renders it) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/RecapBox.test.tsx · routeBUtilities (this file is on src/styles/route-b-migrated.txt)
// exceptions: E3 the three existing private recap shapes (JobIntakeWizard.ReviewRow, DepositReviewRows, .met-preview-list) are NOT migrated onto this — reported as DEF-SHL-5123 rather than re-pointed, because that is a visual change to four live wizards on the authority of a component move (B14 rule 38's blast-radius clause)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
