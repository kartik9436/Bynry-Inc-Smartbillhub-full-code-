// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-CUS-6747` — the State cell printed BOTH axes as two state
//           words, so a held case read *At notice* and *On hold · Medical
//           certificate* in one column · `DEF-CUS-6749` — a crew that attended
//           and could not cut left the case reading exactly like one nobody had
//           visited · and the six clerk words the Product Owner asked for.
// Rules:    B14 rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 · rationale is ZERO
//           words on screen) · B14 rule 43 (a COMPONENT, not inline) · B14
//           rule 44 (our UI standard beats the drawing on the kit and the
//           tokens) · A12 §Semantic tokens (a tone is a MEANING, never a
//           colour) · BR-SHL-010 (the vocabulary is the server's) ·
//           BR-CUS-1083 (the four visit outcomes)
// Design:   the redesign drawing for the Disconnects list — one badge per row
//           with the reason in plain text beneath it
// Tests:    07-frontend/src/features/customers/DisconnectsTab.test.tsx
// Impacts:  DisconnectsTab.tsx only
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · ONE WORD IN THE COLUMN, AND NO PRECEDENCE IS INVENTED TO GET IT
// ══════════════════════════════════════════════════════════════════════════
// The server serves two INDEPENDENT axes on one cell: `stored` — the case's own
// state — and `held_by`, which is computed from the account's protections. A
// row can satisfy both, and **no rule ranks them** (`OQ-374`, still OPEN). The
// old cell refused to choose and printed both, which is honest about the data
// and unreadable in a column called *State*.
//
// ⚠ **THIS STILL CHOOSES NOTHING, AND THAT IS THE WHOLE TRICK.** The two facts
// are not ranked — they are given DIFFERENT JOBS. The badge answers *what is
// happening to this supply*, and the line under it answers *why*. A case at
// notice on a medical certificate reads **Held / Medical certificate**, and
// nothing about the notice is hidden: the Tier column still shows the rung the
// ladder reached and the Cut date column still shows what is booked.
//
// ⚠ **A PROTECTION WINS THE BADGE FOR A STATED REASON, NOT BY PRECEDENCE.**
// The blueprint's own sentence for this screen is *"On hold is not a delay, it
// is a protection"* — a held account is one the utility may NOT cut today,
// whatever rung the ladder is on, and that is the fact a clerk scanning this
// column is scanning for. So *held* is not "more important than" notice_sent;
// it is the answer to the question the column asks. `OQ-374` remains open and
// this file decides nothing for the segments it is about.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · SIX CLERK WORDS, AND THE ONE THE SIX DO NOT COVER
// ══════════════════════════════════════════════════════════════════════════
// Notified · Scheduled · Off · Reconnecting · Restored · Held. The stored codes did not
// move and neither did the server: these are the words under
// `customers.disconnects.state.<code>` in all eleven catalogues.
//
// ⚠ **`closed_out` IS A SEVENTH STATE AND WAS GIVEN NO CLERK WORD.** It is a
// real stored state (`BR-CUS-430`), it is offered as a filter, and a case can
// hold it on this list. It reads **Closed** here rather than being folded into
// one of the six — mapping it onto *Restored* would tell a clerk the supply is
// back on when the case was simply finished. **REPORTED, not decided**: if the
// six are meant to be exhaustive then `closed_out` should leave this list, and
// that is a ruling rather than a lane's choice.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · THE TONE IS A MEANING, AND WHERE THE DRAWING DISAGREES THE KIT WINS
// ══════════════════════════════════════════════════════════════════════════
// B14 rule 44: our UI standard beats the drawing on the component kit and the
// tokens, every time. So this mounts `StatusPill` — the kit's ONE status chip —
// and picks its tone by A12's meanings rather than by matching the drawn fill:
//
//   Notified  → `neutral`  the ladder is running; nothing has happened yet
//   Scheduled → `warning`  an act is BOOKED and a clerk should look
//   Off       → `danger`   the act has happened and the supply is off
//   Reconnecting → `warning`  a reconnect visit is BOOKED; money may still be owed
//                (was `Paid → success`, *"the money is in"* — false since
//                BR-CUS-1097; DEF-CUS-10667, 2026-10-29)
//   Restored  → `success`  the supply is back
//   Held      → `info`     A12's own words: *paused, and nothing is wrong*
//   Closed    → `muted`    A12's own words: *this is over*
//
// ⚠ **`Held` IS DRAWN AMBER AND IS BUILT `info`, DELIBERATELY.** A12 says in as
// many words that a tone is status MEANING and never decoration, and the
// blueprint's own sentence for this row is that a hold is a protection rather
// than a delay — *paused, and nothing is wrong* is that sentence. Reaching for
// `warning` because the drawing is yellow is the exact move A12 exists to stop.
// REPORTED, because it is a visible divergence from the drawing.
import type { JSX, ReactNode } from "react";

import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";

/** The tone each state MEANS — §3. Keyed on the server's codes, plus the
 *  computed `held`, which is not a stored state and never will be. */
export const DISCONNECT_STATE_TONE: Record<string, StatusTone> = {
  notice_sent: "neutral",
  scheduled: "warning",
  cut: "danger",
  reconnecting: "warning",
  restored: "success",
  closed_out: "muted",
  stopped: "muted",
  on_hold: "info",
  in_progress_draft: "neutral",
  parked: "neutral",
};

/** The computed axis has no stored code, so it carries its own key. */
export const HELD_TONE: StatusTone = "info";

export interface DisconnectVisitFact {
  outcome: string;
  visited_on: string;
  clears_the_cut_date: boolean;
}

export function DisconnectStateBadge(props: {
  /** The stored case state, or null on a row that is here for a protection. */
  stored: string | null;
  /** The protection kinds in force, already turned into clerk words. */
  held: string[];
  /** The clerk word for `stored`, resolved by the screen's own label map. */
  storedLabel: string;
  /** The clerk word for a held row — *Held*. */
  heldLabel: string;
  /** The crew's last attendance, or null when none is recorded. §4. */
  visit: DisconnectVisitFact | null;
  /** `Visited` plus the outcome's word, already translated. */
  visitLabel: string | null;
  /** The visit date, rendered by the screen's one calendar. */
  visitDate: ReactNode;
  /** A qualifier for the pill — the server's own sentence, asked for rather
   *  than shown (rule 33's tooltip split). */
  title?: string;
}): JSX.Element {
  const { stored, held, visit } = props;
  const isHeld = held.length > 0;
  const code = isHeld ? "on_hold" : (stored ?? "");
  const tone = isHeld ? HELD_TONE : (DISCONNECT_STATE_TONE[code] ?? "neutral");
  const word = isHeld ? props.heldLabel : props.storedLabel;

  return (
    <span
      className="inline-flex flex-col items-start gap-1"
      data-state-stored={stored ?? undefined}
      data-state-held={isHeld ? "" : undefined}
      data-state-shown={code || undefined}
    >
      {stored === null && !isHeld ? (
        <span aria-hidden="true">—</span>
      ) : (
        <StatusPill tone={tone} title={props.title}>
          {word}
        </StatusPill>
      )}
      {/* ⚠ **THE REASON, AND IT IS NOT A SECOND STATE WORD.** Plain text, one
          size down, so the column reads as one answer with a qualifier rather
          than as two competing statuses. A FACT, so rule 33 gives it six
          words — `Weather moratorium` and `Medical certificate` are two. */}
      {isHeld && (
        <span className="text-sm text-neutral-700" data-state-reason="">
          {held.join(" · ")}
        </span>
      )}
      {/* ══════════════════════════════════════════════════════════════════
          4 · THE CREW WAS THERE — `DEF-CUS-6749`
          ══════════════════════════════════════════════════════════════════
          Three of the four outcomes CLEAR the cut date and put the case back
          to `notice_sent`, which is a real and correct state — so without this
          line a case a crew drove to on Tuesday and a case nobody has ever
          visited are the SAME WORD with the same empty Cut date. That is the
          whole defect, and it is why this rides in the state cell rather than
          in a column of its own: it is the qualifier that makes the badge
          truthful, exactly as the protection reason above it is.

          ⚠ **ABSENT MEANS NOTHING IS RECORDED, NOT THAT NOBODY WENT**, which
          is why there is no *Not visited* line on the other rows. A screen
          that printed one would be making a claim about the world from the
          absence of a row. */}
      {visit !== null && props.visitLabel !== null && (
        <span
          className="text-sm text-neutral-700"
          data-state-visit={visit.outcome}
          data-visit-cleared-date={visit.clears_the_cut_date ? "" : undefined}
        >
          {props.visitLabel}
          {props.visitDate !== null && <> · {props.visitDate}</>}
        </span>
      )}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6745 · DEF-CUS-6747 · DEF-CUS-6749 · B14 rules 33, 43, 44 ·
//         A12 §Semantic tokens · BR-CUS-1083 · OQ-374 (OPEN, untouched)
// generated: 2026-09-25 by lane LIST
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 **`Held` is drawn amber and is built `info`** — A12 makes a
//         tone a meaning and the blueprint's own sentence is that a hold is a
//         protection rather than a delay; REPORTED · E3 **`closed_out` reads
//         `Closed`**, a seventh word the six do not cover; REPORTED rather than
//         folded into one of them · E3 **`OQ-374` is untouched** — the two axes
//         are given different jobs, not ranked
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
