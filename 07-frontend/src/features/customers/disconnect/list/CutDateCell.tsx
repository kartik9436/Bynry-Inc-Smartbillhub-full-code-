// ── Trace ──────────────────────────────────────────────
// Change:   PO 2026-09-20, verbatim: *"Something has to read cut dates daily
//           and surface what's due… A case due last week stops looking
//           identical to one due next month. The clerk stops being the
//           scheduler."* This is the ROW half of the screen side.
// Drawing:  `05-prototype/02 Accounts Menu Blueprint.pdf` p140, rendered AS AN
//           IMAGE (B14 rule 42). ⚠ **THE DRAWING DOES NOT COVER THIS.** p140
//           draws `CUT DATE` as a plain date and captions the DUE TO CUT tile
//           *"the date has arrived"*; there is no overdue state anywhere on the
//           register, on the case record (p141–p143) or in the wizard. Said
//           rather than invented: this cell is built to the neighbouring
//           disconnect cells (`TierCell`'s bordered chip, `OwedCell`'s named
//           absence) and to the shared kit, and the addition is REPORTED.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — this is reachable by
//           any worklist that grows a due date) · rule 33 (a LABEL ≤ 3 words;
//           a FACT ≤ 6 words; RATIONALE is ZERO words on screen) · rule 31 (no
//           database id is a visible value) · rule 37 (a drawn figure is an
//           illustration) · rule 21 (Tailwind utilities; this file is on
//           `route-b-migrated.txt` in its first commit) · BR-SHL-010 (the
//           served vocabulary is the only vocabulary)
// Tests:    ../../DisconnectsListDrawing.dom.test.tsx (EXTENDED, not a second
//           file) · 10-scripts/po20260921_cut_date_watch_walkthrough.mjs
// Impacts:  ../../DisconnectsTab.tsx (the `cut_date` cell) ·
//           06-backend/apps/customers/disconnect_due.py (the ONE predicate)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT THIS CHANGES, AND WHY THE ACCENT WAS NOT ENOUGH
// ══════════════════════════════════════════════════════════════════════════
// §5.8.2 says *"`CUT DATE` renders in the accent when it is this week"*, and
// the server decides it — `disconnect_reads._within_the_week`, whose own
// docstring records what it costs:
//
//   > ⚠ **A SCHEDULED CUT WHOSE DATE HAS PASSED IS IN NEITHER** — it is not
//   > accented and it is not counted — which is what the caption says and is
//   > not obviously what a clerk wants.
//
// So a cut booked for last Monday rendered in exactly the same plain text as
// one booked for next month. **That is the PO's sentence, in a table cell.**
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · TWO FACTS ABOUT ONE DATE, AND NEITHER IS COMPUTED HERE
// ══════════════════════════════════════════════════════════════════════════
// `cut_date_is_this_week` (forward-looking) and `cut_due.status` (overdue,
// today, ahead, no date, done) are BOTH the server's. **This cell re-derives
// neither, and it must not**: there is one calendar in this product, and a
// second one on the screen is how a tile and its list stop agreeing — which is
// `DEF-CUS-6055`, on this same screen, this same month.
//
// ⚠ **`status: "done"` RENDERS AS AN ORDINARY DATE AND NOT AS OVERDUE.** The
// supply is already off; the date on that row is the record of WHEN, not a
// plan. Reading it as late is the defect this whole change was raised over.
import type { DisconnectCutDue } from "../../worklistEndpoints";

/** The words this cell can print, so a caller cannot invent a twelfth. */
const OVERDUE = "overdue";
const DUE_TODAY = "due_today";

export function CutDateCell(props: {
  /** Already formatted by the screen's own `DateCell` — this component never
   *  touches a locale, a timezone or a format (BR-SHL-023's posture for money,
   *  applied to dates: ONE formatting path). */
  date: React.ReactNode;
  /** `null` when no date is booked. The dash is the drawing's own absence. */
  hasDate: boolean;
  /** The server's forward-looking accent (§5.8.2), unchanged. */
  isThisWeek: boolean;
  /** The server's `cut_due` block. See §2 — nothing here is recomputed. */
  due: DisconnectCutDue | undefined;
  /** Pre-translated by the screen; never a key and never a code. */
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  if (!props.hasDate) {
    return <span aria-hidden="true">—</span>;
  }
  const status = props.due?.status ?? "";
  const late = status === OVERDUE;
  const today = status === DUE_TODAY;
  // The accent stays exactly as the drawing has it; overdue takes the danger
  // tone, which is the tone this module already uses for the consequences of a
  // cut (`CutPreviewPanel`, `MarkAsCutDialog`).
  const dateTone = late
    ? "text-danger-700"
    : props.isThisWeek || today
      ? "text-accent-700"
      : undefined;
  return (
    <span
      className="inline-flex flex-col items-start gap-0.5"
      data-cut-this-week={props.isThisWeek}
      data-cut-due={status}
    >
      <span className={dateTone}>{props.date}</span>
      {(late || today) && (
        <span
          className="inline-flex items-center gap-1"
          data-cut-due-marker={status}
        >
          {/* §5.8.2's *"a bordered chip"*, at `TierCell`'s size — the size
              every other chip in this product uses (B14 rule 5's small tier).
              A LABEL: one word, or two. Rule 33. */}
          <span
            className={`inline-flex items-center border px-1.5 py-0.5 text-xs uppercase tracking-wide ${
              late ? "border-danger-500 text-danger-700" : "border-accent text-accent-700"
            }`}
          >
            {late
              ? props.t("customers.disconnects.cutDue.overdue", { defaultValue: "Overdue" })
              : props.t("customers.disconnects.cutDue.dueToday", { defaultValue: "Due today" })}
          </span>
          {/* A FACT, ≤ 6 words (B14 rule 33), and only when there is a number
              to state. `days_overdue` is the server's; a day count worked out
              in the browser would be the second calendar §2 forbids. */}
          {late && (props.due?.days_overdue ?? 0) > 0 && (
            <span className="text-xs text-neutral-700" data-cut-due-days={props.due?.days_overdue}>
              {props.t("customers.disconnects.cutDue.daysLate", {
                defaultValue: "{{count}} days late",
                count: props.due?.days_overdue ?? 0,
              })}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO ruling 2026-09-20 (*"A case due last week stops looking identical
//         to one due next month"*) · Accounts blueprint p140 (as an image) ·
//         disconnect_due.py (the served `cut_due` block) · B14 rules 21, 31,
//         33, 37, 43 · DEF-CUS-6055
// generated: 2026-09-20 by lane DBLD-3 (the cut-date watcher)
// checklist: A=n/a(no backend half in this file) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E3 **THE DRAWING DOES NOT DRAW AN OVERDUE STATE** — p140 draws
//         `CUT DATE` as a plain date and nothing on the register, the record or
//         the wizard shows a date that has passed. The marker is built to the
//         neighbouring cells and the shared kit, and it is REPORTED rather than
//         claimed as drawn · E3 **NOTHING IS COMPUTED HERE** — both facts about
//         the date are the server's, because a second calendar on the screen is
//         `DEF-CUS-6055` rebuilt · E3 **a case that has been CUT renders as an
//         ordinary date**, never as overdue: the date on that row records when
//         the supply went off
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
