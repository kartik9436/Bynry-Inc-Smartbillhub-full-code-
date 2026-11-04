// ── Trace ──────────────────────────────────────────────
// Change:   CR-126-BRC07 — the BUILD RECORD's shared row primitives, drawn on
//           blueprint p098–p099 and read as IMAGES (B14 rule 42).
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — PO: *"make them
//           coponents - dont write stand alone code, engineer it"*) · rule 36
//           (the shared kit, not a fourth opinion about what a fact row looks
//           like) · rule 33 (RATIONALE is ZERO WORDS ON SCREEN — the reason a
//           fact is absent never reaches the page body) · rule 21 (Tailwind
//           utilities; this directory is on `styles/route-b-migrated.txt`)
// Tests:    src/features/work/buildRecord/buildRecordPanels.test.tsx
// ───────────────────────────────────────────────────────
/**
 * One drawn fact — label left, value RIGHT, a hairline between rows.
 *
 * ⚠ **THE MARKUP IS `disconnect/record/recordFacts.FactRow`'s, CHARACTER FOR
 * CHARACTER**, which is `TransferRecordPage.TransferFactRow`'s before it, which
 * is `MoveRecordPage.Fact`'s before that. **Four record screens now share one
 * row shape and they must not drift into four** — a fresh opinion about what a
 * fact row looks like is exactly what B14 rule 36 exists to stop, and it is
 * what the PO found by looking at four shipped screens rather than any gate.
 *
 * ⚠ **THE HAIRLINE IS `border-b` ON THE ROW WITH `last:border-0`, NOT A GAP.**
 * A `divide-y` on the parent is equivalent right up until one row is
 * conditionally absent — and on this record most rows are, because the record
 * read that fills them does not exist yet.
 */
import type { ReactNode } from "react";


export function FactRow(props: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-neutral-200 py-3 last:border-0">
      <dt className="text-sm text-neutral-600">{props.label}</dt>
      <dd className="text-sm font-medium text-right text-neutral-900">{props.children}</dd>
    </div>
  );
}

/**
 * A stated absence — the quiet half of a row.
 *
 * ⚠ **THE BLUEPRINT DRAWS ABSENCES RATHER THAN HIDING THEM**: `— not yet`
 * against *Activated at*, `— not given` against *External system reference*,
 * *"units are named on the next tab"* against *Unit, flat or suite*. An absent
 * fact is a FACT about this build, so the row stays and the value says so.
 *
 * ⚠ **THE SHORT LABEL IS WHAT A CLERK READS; ANY REASON RIDES ON `title`** —
 * B14 rule 33. WHY a fact is missing is RATIONALE and is zero words on screen.
 * It stays reachable for anyone debugging and never reaches the page body.
 * ⚠ **A REFUSAL IS THE OPPOSITE CASE AND IS NOT THIS COMPONENT.** Why a
 * control cannot be PRESSED is visible text always (`BR-SHL-025`), because a
 * touch or keyboard user never sees a tooltip and a refusal has to be READ.
 */
export function Absent(props: { label: string; reason?: string }) {
  return (
    <span className="text-neutral-600 font-normal" data-absent="" title={props.reason}>
      {props.label}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-126-BRC07 · blueprint p098–p099 read as images (B14 rule 42)
// generated: 2026-09-20 by lane NCD-2 (front-end shell)
// gates: G31 (this directory is on route-b-migrated.txt in this commit) · G13
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
