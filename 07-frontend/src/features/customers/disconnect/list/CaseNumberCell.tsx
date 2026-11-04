// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-CUS-6744` — the Case # cell printed a 22-word paragraph on
//           every row that has no case, and the row rendered **277px tall**
//           against a normal row's 80px. Measured in Chromium at 1440 and at
//           1280, with `getBoundingClientRect`, on six live rows.
// Rules:    B14 rule 33 (**RATIONALE IS ZERO WORDS ON SCREEN**, and it is
//           REMOVED rather than shortened) · B14 rule 31 (no database id is
//           ever a visible value — `case_no` is a SERIES number, not an id) ·
//           B14 rule 43 (a piece of UI is a COMPONENT) · BR-SHL-010
// Design:   the redesign drawing for the Disconnects list — the two rows with
//           no case draw `—` in this column, nothing else
// Tests:    07-frontend/src/features/customers/DisconnectsTab.test.tsx
// Impacts:  DisconnectsTab.tsx only
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHY THIS IS NOT `RecordNumberCell`, WHICH ALREADY EXISTS
// ══════════════════════════════════════════════════════════════════════════
// `transferDisconnectShared.RecordNumberCell` renders the server's WHOLE
// `unavailable.detail` sentence, and it is mounted by **four** screens —
// Transfers, Move-outs, Move-ins and this one. Changing it would have fixed
// this list and silently redrawn three other lanes' tables in the same commit,
// which is the blast radius this repo's maintenance process asks to be listed
// BEFORE anything is changed rather than discovered after.
//
// So the shared component is left exactly as it is and this list renders its
// own cell. **The same paragraph is still on Transfers and Move-outs** — it is
// the same defect on two screens this lane does not own, and it is REPORTED
// rather than fixed here.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE SENTENCE IS NOT SHORTENED — IT LEAVES THE SCREEN
// ══════════════════════════════════════════════════════════════════════════
// B14 rule 33 is explicit that rationale is REMOVED rather than trimmed:
// cutting *"This account is on the list because a protection is in force. No
// disconnection case has been opened, so there is nothing to reference."* down
// to six words keeps the breach and makes it terser.
//
// ⚠ **THE FACT IS KEPT AND ONLY THE EXPLANATION GOES.** There is no case
// number, and `—` is this product's word for *there is no value here*. The two
// absences the server distinguishes — a protection row that never entered the
// ladder, and a real case on a tenant with no numbering series — are still told
// apart, on `data-tracks`, where a walk can read them and a clerk cannot. A
// clerk does not need to know WHICH kind of nothing it is in order to read the
// row; the one who does is holding a browser's dev tools.
//
// ⚠ **AND THE `title` IS NOT A LOOPHOLE.** It carries the same sentence for a
// mouse that rests on the dash. Rule 33 governs what a screen SAYS — text a
// clerk reads while scanning — and a tooltip is asked for rather than shown.
// That is the same split `OwedCell` and `StateCell` on this screen already use
// for their own served absences (`DEF-742`).
import type { JSX } from "react";

export interface CaseNumberAbsence {
  code: string;
  detail: string;
  open_question?: string;
  series?: string;
}

export function CaseNumberCell(props: {
  /** The allocated series number, or `null` when there is none. */
  number: string | null;
  /** The server's reason, present exactly when `number` is null. */
  unavailable: CaseNumberAbsence | null;
}): JSX.Element {
  const { number, unavailable } = props;
  if (number !== null && number !== "") {
    return (
      <span className="tabular-nums" data-record-number="disconnect">
        {number}
      </span>
    );
  }
  return (
    <span
      className="text-neutral-700"
      data-record-number="disconnect"
      data-record-number-absent=""
      data-tracks={unavailable?.open_question ?? unavailable?.code}
      title={unavailable?.detail ?? undefined}
    >
      {/* Not `aria-hidden`: this dash is the cell's whole VALUE, and a screen
          reader that skips it reads the row with one column missing. The two
          dashes on this screen that ARE decoration (an empty customer, an
          empty address) are hidden, and the difference is deliberate. */}
      —
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6744 · B14 rules 31, 33, 43 · the Disconnects list redesign
// generated: 2026-09-25 by lane LIST
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 **the shared `RecordNumberCell` is deliberately NOT changed** —
//         four screens mount it and three of them are other lanes'; the same
//         paragraph is still on Transfers and Move-outs and is REPORTED · E3
//         the absence CODE is still served and still distinguishes its two
//         causes; only the SENTENCE left the screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
