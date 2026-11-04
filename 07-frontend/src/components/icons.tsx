// ── Trace ──────────────────────────────────────────────
// Change:   PO ruling 2026-08-20 — "Icons everywhere, per r10 and rule 15",
//           and "Tailwind, CSS, STylesheet, UI COmponents - we should ahve
//           only one reference point not two"
// Rules:    B14 rule 15 (row actions are icons with tooltips, never text links)
// Defects:  DEF-348 (three byte-identical pencils under two names, plus a
//           fourth drawn inline) · DEF-337 · DEF-342
// Impacts:  every row-actions cell in the product imports from here; a raw
//           <svg> inside a row-actions container is a defect after this.
// ───────────────────────────────────────────────────────
//
// THE B14 RULE 15 ICON VOCABULARY, WITH ONE IMPLEMENTATION EACH.
//
// ⚠ THIS FILE EXISTS BECAUSE THE RULE HAD NO CODE. Rule 15 lists its glyphs in
// PROSE — "👁 view · ✎ edit/note · ⟲ roll back · 🔧 fix · 🖨 print · ✉ send ·
// ⚡ raise work · ✓ assign · − remove" — and prose is not importable, so every
// screen that converted its row actions drew its own copy. By 2026-08-20 the
// "edit" pencil existed FOUR TIMES, byte for byte:
//
//     SettingsReferenceData.tsx:494    function EditIcon()
//     SettingsRoutesCyclesTab.tsx:144  function EditIcon()
//     TemplateDetail.tsx:925           export function PencilIcon()
//     SettingsServicesTab.tsx:341      an inline <svg>, not even a component
//
// TrashIcon and PowerIcon were each drawn twice as well. Nothing was broken —
// they render identically — which is exactly why it survived: the cost of a
// duplicated vocabulary is only paid the day the vocabulary changes, and then
// the change is silently partial. That is hard-won law 5 ("one generated file,
// committed once") widened by the PO from generated files to the whole UI
// surface.
//
// ⚠ NAMED BY SHAPE, NOT BY VERB, AND THAT IS DELIBERATE. One glyph serves
// several verbs — the eye is "view", "view asset" and "view units"; the pencil
// is "edit", "change" and "new version" — so a verb name would force a second
// export for the same paths and re-open the thing this file closes. The
// verb→glyph mapping is the table below, and it is the part to argue with.
//
//     VERB (as it appears in i18n)            GLYPH        r10 `title`
//     ──────────────────────────────────────  ───────────  ──────────────────
//     view · viewUnits · view asset           EyeIcon      "View" / "View asset"
//     edit · change · newVersion · editUom    PencilIcon   "Edit" / "Edit mapping"
//     delete · remove                         TrashIcon    "Remove"
//     deactivate · reactivate · enable ·      PowerIcon    "Deactivate"
//       disable
//     rollBack                                RollBackIcon "Roll back"
//     publish · commit                        CommitIcon   —
//     waive (a deposit, a fee) — DEF-CUS-9778 WaiveIcon    —
//       (was CommitIcon's tick, which read
//       as "paid"); undo waive is rollBack
//     assign · reassign · move (a payment     SwapIcon     "Reassign"
//       to another account, CR-135 P1.6)
//     reapply — a payment onto a NAMED bill   TagIcon      —
//       (CR-135 P1.6); it joins assignPlan
//       four rows below on the same glyph
//     retire                                  RetireIcon   "Retire"
//     logRepair · logTest                     WrenchIcon   "Raise work order"
//     assignPlan                              TagIcon      —
//     moveUp / moveDown                       ChevronUp/   "↑↓ to reorder"
//                                               ChevronDown
//     placement                               LayoutIcon   —
//     temp_password                           KeyIcon      —
//     activation_code — a new phone app       PhoneIcon    —
//       code for a field technician
//       (DEF-IDN-10365, CR-187-BRC10)
//     download · export (CSV/PDF)             DownloadIcon r10 `btn-icon-sm`, tooltip
//                                                          "Download CSV"
//     fetchReading — ask the meter head-end   FetchIcon    — (DEF-CUS-10050)
//       for one meter's reading
//
// ⚠ FOUR OF THESE HAVE NO r10 PRECEDENT (commit, assignPlan, placement,
// temp_password; `archive`'s ArchiveIcon left with the Plans list's row action,
// CR-167 task 6, when it had no other caller) and are chosen here rather than transcribed. They are the ones to
// check in the browser walkthrough; if any reads wrong, this file is the one
// place it changes.
//
// GEOMETRY IS ONE CONSTANT. 16px in a 24-unit viewBox, `aria-hidden` because
// the accessible name lives on the BUTTON (see `RowAction`), and `currentColor`
// so the danger and disabled states inherit — A12 requires inline SVG and
// forbids an icon font.
//
// ⚠ 16px AND NOT r10's 14px. The seven tables already converted render at 16
// and changing it would move pixels on screens this ruling did not touch. r10's
// `btn-icon-sm` is 14; the divergence is recorded so nobody "fixes" it later.

const ICON_BOX = { viewBox: "0 0 24 24", width: 16, height: 16, "aria-hidden": true } as const;

/** The one stroke weight. `1.8` on the tick only, because a bare check reads
 *  thin beside a closed shape at 16px. */
const STROKE = { fill: "none", stroke: "currentColor", strokeWidth: "1.6" } as const;

/** 👁 view */
export function EyeIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M1.8 12S5.6 5.5 12 5.5 22.2 12 22.2 12 18.4 18.5 12 18.5 1.8 12 1.8 12z" {...STROKE} />
      <circle cx="12" cy="12" r="3.2" {...STROKE} />
    </svg>
  );
}

/** ? help — r10's own glyph, top bar (DEF-450).
 *
 * Taken verbatim from `SMARTBillHub.dc.html`: a circle plus the question-mark
 * stroke `M9 9a3 3 0 116 0c0 2-3 3-3 3M12 17v.01`. It lives HERE rather than
 * inline in AppShell because B14 rule 15 puts the icon vocabulary in one file
 * and nowhere else — DEF-348 is what happens otherwise, the same pencil four
 * times under two names, and DEF-349 records the shell already carrying a
 * SECOND vocabulary of seven inline SVGs. This one does not add an eighth.
 */
export function HelpIcon() {
  return (
    <svg {...ICON_BOX}>
      <circle cx="12" cy="12" r="10" {...STROKE} />
      <path d="M9 9a3 3 0 116 0c0 2-3 3-3 3M12 17v.01" {...STROKE} />
    </svg>
  );
}

/** ⓘ a marker on a header or label pointing at the disclosure that explains it.
 *
 * Drawn on the bills list's STATUS header in the billing blueprint's entry 01
 * (p007, the REDESIGN, read as an image per B14 rule 42): a circle with an `i`,
 * the same grey as the header text, sitting immediately after the word.
 *
 * ⚠ **IT IS A MARKER, NOT A PLACE TO PUT A SENTENCE.** B14 rule 33 puts
 * RATIONALE at zero words on screen and rule 32 puts a stated absence in a
 * `<details>` CLOSED by default. This glyph says *there is an explanation
 * below*; the explanation goes in the disclosure, never in a tooltip that
 * grows into a paragraph.
 *
 * Distinct from `HelpIcon` (a question mark) on purpose: that one offers help
 * with a task, this one marks a fact that has a footnote.
 */
export function InfoIcon() {
  return (
    <svg {...ICON_BOX}>
      <circle cx="12" cy="12" r="9" {...STROKE} />
      <path d="M12 11v5.5M12 7.6v.01" {...STROKE} strokeLinecap="round" />
    </svg>
  );
}

/** ✎ edit / change / new version */
export function PencilIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M4 20h4L18.5 9.5a2.1 2.1 0 10-3-3L5 17v3z" {...STROKE} />
    </svg>
  );
}

/** 📋✓ review — a request waiting for a clerk's decision (`CR-171-BRC10`
 *  image 01, the Move-ins list's *To approve* row). A board with a tick on it,
 *  so it reads as *look this over* and not as `CommitIcon`'s bare ✓, which
 *  COMMITS. */
export function ReviewIcon() {
  return (
    <svg {...ICON_BOX}>
      <rect x="5" y="4" width="14" height="17" {...STROKE} />
      <path d="M9 4V2.8h6V4" {...STROKE} />
      <path d="M8.5 13l2.5 2.5 4.5-5" {...STROKE} />
    </svg>
  );
}

/** ⋯ more — the row-action overflow.
 *
 *  B14 rule 15 has always ended *"Max 2 visible, then `…`"* and the product had
 *  no glyph for the second half of that sentence, so every table drew all of
 *  its actions and the rule was ratified and unenforceable. Three filled dots
 *  rather than a typographic ellipsis: at 16px a text `…` sits on the baseline
 *  and reads as punctuation left behind, where a centred trio reads as a
 *  control. */
export function MoreIcon() {
  return (
    <svg {...ICON_BOX}>
      <circle cx="5.5" cy="12" r="1.6" fill="currentColor" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
      <circle cx="18.5" cy="12" r="1.6" fill="currentColor" />
    </svg>
  );
}

/** ⧉ copy / clone — one sheet lifted off another.
 *
 *  Added by `CR-075` wave `E` for `RBS-003`'s **Clone** row action
 *  (`POST /runbooks/{key}/clone`, `07-endpoints.md` row 6). B14 rule 36 names
 *  the mechanism: *"Where the kit lacks a piece, ADD IT TO THE KIT — one
 *  component, one visual decision, every screen — rather than hand-rolling it
 *  in the screen."* The alternative was a raw `<svg>` in `MyRunbooks.tsx`,
 *  which is the sixth private glyph this file exists to prevent. */
export function CopyIcon() {
  return (
    <svg {...ICON_BOX}>
      <rect x="9" y="9" width="11" height="11" rx="2" {...STROKE} />
      <path d="M6 15H5a1 1 0 01-1-1V5a1 1 0 011-1h9a1 1 0 011 1v1" {...STROKE} />
    </svg>
  );
}

/** − remove / delete */
export function TrashIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M4 7h16M10 7V5h4v2M6 7l1 13h10l1-13" {...STROKE} />
    </svg>
  );
}

/** Power symbol — r10 draws deactivate/reactivate as ONE control, not two, so
 *  the glyph does not flip with the state and only the label does. */
export function PowerIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M12 3v9" {...STROKE} />
      <path d="M6.6 6.6a7.5 7.5 0 1010.8 0" {...STROKE} />
    </svg>
  );
}

/** ⏸ pause a schedule — `CR-142-BRC07` `P4.5`, screen `4·1`'s row actions.
 *
 * ⚠ **ADDED TO THE KIT RATHER THAN DRAWN INLINE, AND `G37` IS WHY.** The first
 * draft of `ScheduledTab.tsx` declared both this glyph and `PlayIcon` as inline
 * `<svg>` elements in the page, and the gate refused it by name: *"The B14 rule
 * 15 vocabulary lives in components/icons.tsx and nowhere else — that is
 * DEF-348, where the same pencil existed four times under two names."* It is
 * also B14 rule 43: a piece of UI is built as a COMPONENT, and standalone code
 * inside a page is not reuse.
 *
 * ⚠ **IT IS FILLED WHERE ITS NEIGHBOURS ARE STROKED, ON PURPOSE.** A pause is
 * two solid bars and a play is a solid triangle; drawing either as a 1.6-weight
 * outline at 16px produces a hollow shape nobody reads as a transport control.
 * `ICON_BOX` still governs the geometry, so it sits on the same 16px grid as
 * every other glyph here. */
export function PauseIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M9 5h2.5v14H9zM12.5 5H15v14h-2.5z" fill="currentColor" />
    </svg>
  );
}

/** ▶ run it now — `CR-142-BRC07` `P4.5`, and the RESUME half of the control
 *  above, because a paused schedule resumes with the same glyph a run starts
 *  with. See `PauseIcon` for why both are filled. */
export function PlayIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M8 5l11 7-11 7z" fill="currentColor" />
    </svg>
  );
}

/** ⟲ roll back */
export function RollBackIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M4 5v5h5" {...STROKE} />
      <path d="M4.6 10a8 8 0 113 8.4" {...STROKE} />
    </svg>
  );
}

/** ✓ commit / publish — B14 rule 4's commit verb as a glyph. */
export function CommitIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M4.5 12.5l5 5 10-11" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

/** ⇄ assign / reassign — r10's exact path for `title="Reassign"`. */
export function SwapIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M17 1l4 4-4 4M21 5H7M7 23l-4-4 4-4M3 19h14" {...STROKE} />
    </svg>
  );
}

/** ✕ retire — r10's exact path for `title="Retire"`. It is NOT the trash: a
 *  retired asset still exists and is still reportable, and the two verbs sit
 *  in the same cell on the Assets registry. */
export function RetireIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M6 6l12 12M18 6L6 18" {...STROKE} />
    </svg>
  );
}

/** 🔧 fix — "log repair" on a meter, "log test" on a backflow device. */
export function WrenchIcon() {
  return (
    <svg {...ICON_BOX}>
      <path
        d="M20.5 5.5a5 5 0 01-6.6 6.6L5.6 20.4a2 2 0 11-2.8-2.8l8.3-8.3a5 5 0 016.6-6.6l-3 3 2.8 2.8 3-3z"
        {...STROKE}
      />
    </svg>
  );
}

/**
 * The COLUMN CHOOSER glyph — r10's own: a box split by two vertical rules,
 * tooltipped *"Choose columns · ↑↓ to reorder"*. It sits at the right of every
 * table toolbar (`DataTable`), which is the one place it is used.
 *
 * ⚠ IT LIVED INSIDE `DataTable.tsx` AS A LITERAL `<svg>` AND G37 WAS RED (DEF-462).
 * That is DEF-348's exact shape — a glyph declared where it is used rather than
 * where the vocabulary lives — and the reason the rule exists is that the second
 * copy is invisible: the edit pencil existed four times under two names before
 * anyone noticed. `strokeWidth` is 2 rather than the shared `1.6` because that
 * is what r10 draws for this glyph; stated here rather than silently normalised.
 */
export function ColumnsIcon() {
  return (
    <svg {...ICON_BOX}>
      <rect x="3" y="3" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M9 3v18M15 3v18" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

/**
 * ↓ download — the toolbar's export control (CR-045 A.3, B14 rule 4's `↓`).
 *
 * ⚠ **IT IS HERE AND NOT INLINE IN `DownloadButton`, WHICH IS THE WHOLE POINT
 * OF THIS FILE.** The column chooser tried the inline route first and G37 was
 * red on it from the commit that added it (DEF-462): *"inline so it needs no
 * icon dependency"* is precisely what rule 15 forbids, because DEF-348 found
 * the same pencil four times under two names once that argument was accepted
 * anywhere.
 *
 * An arrow into a tray, not a bare chevron: `ChevronDownIcon` already means
 * "reorder this row down" in this same vocabulary, and one glyph for two verbs
 * that appear in the SAME toolbar is the ambiguity a shared vocabulary exists
 * to remove.
 */
export function DownloadIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M12 3v11m0 0 4-4m-4 4-4-4M4 19h16" {...STROKE} />
    </svg>
  );
}

/**
 * Fetch — *Fetch reading* on a metered row (DEF-CUS-10050): ask the utility's
 * meter head-end for this meter's reading NOW. Two arrows round a circle, the
 * sync mark, because the act is "bring this in from the other system"; the
 * tray arrow is already `DownloadIcon`'s, and that one leaves the app.
 */
export function FetchIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M20 12a8 8 0 0 1-13.7 5.6M4 12a8 8 0 0 1 13.7-5.6" {...STROKE} />
      <path d="M18 3v4h-4M6 21v-4h4" {...STROKE} />
    </svg>
  );
}

/** Tag — "assign plan" on a unit. A plan is a thing attached to the row, which
 *  is what a tag is; the swap arrows would read as moving the unit itself. */
export function TagIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M3 12V4h8l9 9-8 8-9-9z" {...STROKE} />
      <circle cx="7.5" cy="7.5" r="1.4" {...STROKE} />
    </svg>
  );
}

/** 📌 pin / unpin — the Notes tab's row action (`ACC-T11`). A drawing-pin seen
 *  from the side: the head, the shaft, the point. `PinnedIcon` is the same pin
 *  struck through, so *pinned* and *not pinned* read as one control in two
 *  states rather than as two different actions. */
export function PinIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M9 3h6l-1 5 3 3v2H7v-2l3-3z" {...STROKE} />
      <path d="M12 13v8" {...STROKE} />
    </svg>
  );
}

/** 📌 unpin — the pin above, struck through. */
export function PinOffIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M9 3h6l-1 5 3 3v2H7v-2l3-3z" {...STROKE} />
      <path d="M12 13v8" {...STROKE} />
      <path d="M4 4l16 16" {...STROKE} />
    </svg>
  );
}

/** ↑ reorder up */
export function ChevronUpIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M5 15l7-7 7 7" {...STROKE} />
    </svg>
  );
}

/** ↓ reorder down */
export function ChevronDownIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M5 9l7 7 7-7" {...STROKE} />
    </svg>
  );
}

/** → open a row (a closed row's arrow) — the customer search table's open
 *  arrow (customer forms drawing set 2026-10-18, images 01 and 10). */
export function ChevronRightIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M9 5l7 7-7 7" {...STROKE} />
    </svg>
  );
}

/** 🔗 link — "this is the same customer" on the customer search table
 *  (drawing set 2026-10-18, image 01). */
export function LinkIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M10 14a4.5 4.5 0 006.4 0l3.2-3.2a4.5 4.5 0 00-6.4-6.4L11.5 6" {...STROKE} />
      <path d="M14 10a4.5 4.5 0 00-6.4 0l-3.2 3.2a4.5 4.5 0 006.4 6.4l1.7-1.6" {...STROKE} />
    </svg>
  );
}

/** ⛓︎̸ unlink — the one-line *Linked* state's undo (image 11). */
export function UnlinkIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M14.5 16.5l-2.3 2.3a4.5 4.5 0 01-6.4-6.4l2.3-2.3" {...STROKE} />
      <path d="M9.5 7.5l2.3-2.3a4.5 4.5 0 016.4 6.4l-2.3 2.3" {...STROKE} />
      <path d="M4 4l16 16" {...STROKE} />
    </svg>
  );
}

/** ⌂ house — *Lived here last* on the customer search table (image 01). */
export function HomeIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M3.5 11L12 4l8.5 7" {...STROKE} />
      <path d="M6 9.5V20h12V9.5M10 20v-5h4v5" {...STROKE} />
    </svg>
  );
}

/** Key — "reset temporary password" on an invited user. No r10 precedent; a key
 *  is the one credential glyph a person reads without a legend. */
export function KeyIcon() {
  return (
    <svg {...ICON_BOX}>
      <circle cx="7.5" cy="15.5" r="4" {...STROKE} />
      <path d="M10.5 12.5L20 3M17 6l2.5 2.5M14.5 8.5L17 11" {...STROKE} />
    </svg>
  );
}

/** Phone — "new phone app code" for a field technician (DEF-IDN-10365,
 *  CR-187-BRC10). No r10 precedent; the code is what claims the native app,
 *  so the glyph is the device it is typed into. */
export function PhoneIcon() {
  return (
    <svg {...ICON_BOX}>
      <rect x="7" y="3" width="10" height="18" rx="2" {...STROKE} />
      <path d="M11 18h2" {...STROKE} />
    </svg>
  );
}

/** Layout frame — "placement", where a custom field appears on a form. */
export function LayoutIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M3 4h18v16H3zM3 9h18M9 9v11" {...STROKE} />
    </svg>
  );
}

/* ── The five the S21 ICON RAIL needed and this vocabulary did not own ─────
 *
 * BR-SHL-045 (PO 2026-08-24, closing B18's D2) rules the account-detail rail
 * as SEVEN named glyphs: ✉ Send statement · 🖨 Print bill · $ Issue credit ·
 * ⇄ Change plan · ⚡ Disconnect notice · 🗓 Payment plan · ✎ Add note. Two of
 * the seven were already here — `SwapIcon` (⇄) and `PencilIcon` (✎) — and the
 * other five existed NOWHERE in the product. Three of the five are named in
 * B14 rule 15's own prose list (✉ send, 🖨 print, ⚡ raise) and had simply
 * never been drawn; `g37_row_actions.py` says what to do about that in as many
 * words: *"Import the glyph, or add it to icons.tsx if it is genuinely new."*
 *
 * ⚠ EVERY PATH IS r10's OWN, transcribed from `SMARTBillHub.dc.html`'s account
 * detail (the `btn-icon-sm` rail, byte offsets ~167k–169k) rather than chosen
 * here. Nothing in this block is invented.
 *
 * ⚠ AND TWO OF THE SEVEN ARE DELIBERATELY *NOT* ADDED, which is the whole point
 * of one owner. r10's rail draws ⇄ as `M17 1l4 4-4 4M21 5H7a4 4 0 00-4 4…` —
 * `SwapIcon`'s path with two rounded corners — and ✎ as `M17 3a2.8 2.8 0 114
 * 4L7 21l-4 1 1-4z`, a second pencil. Adding either would be DEF-348 exactly:
 * the same shape twice under two names, the cost paid only on the day the
 * vocabulary changes. The rail imports `SwapIcon` and `PencilIcon`; the
 * four-unit path divergence from r10 is recorded here so nobody "fixes" it by
 * adding a sixth and seventh glyph.
 *
 * Geometry is the row-action family's (16px, stroke 1.6), not r10's 14px at
 * stroke 2 — the same divergence this file's header already records for every
 * other glyph, applied consistently rather than re-opened per icon.
 */

/** ✉ send — "Send statement". B14 rule 15's ✉, drawn at last. */
export function EnvelopeIcon() {
  return (
    <svg {...ICON_BOX}>
      <rect x="2" y="4" width="20" height="16" {...STROKE} />
      <path d="M2 6l10 7L22 6" {...STROKE} />
    </svg>
  );
}

/** 🖨 print — "Print bill". B14 rule 15's 🖨. */
export function PrinterIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M6 9V2h12v7" {...STROKE} />
      <rect x="6" y="14" width="12" height="8" {...STROKE} />
      <path
        d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"
        {...STROKE}
      />
    </svg>
  );
}

/** $ money — "Issue credit". A currency glyph and not a plus-in-a-circle: the
 *  rail's neighbour ⚡ is destructive, and the two must not read as a pair of
 *  generic marks (BR-SHL-045's own reasoning for making the label an
 *  accessible name rather than a hover tooltip). */
export function DollarIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M12 2v20M17 6H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" {...STROKE} />
    </svg>
  );
}

/** $⃠ waive — a charge that will not be charged: a move-in's deposit, a
 *  request's fee (`DEF-CUS-9778`). The dollar of `DollarIcon`, struck through,
 *  the way `PinnedIcon` strikes the pin. ⚠ NOT the tick: `CommitIcon` is
 *  commit / publish / approve / verify, and beside an amount a tick reads as
 *  *paid*, the opposite of a waive. NOT ✕ either: in a `TableArray` the ✕ is
 *  the row's own *remove*, drawn in the same cell. */
export function WaiveIcon() {
  return (
    <svg {...ICON_BOX} data-icon="waive">
      <path d="M12 2v20M17 6H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" {...STROKE} />
      <path d="M4 4l16 16" {...STROKE} />
    </svg>
  );
}

/** ⚡ the bolt — "Disconnect notice", and the ONE glyph in the rail that is
 *  destructive. It renders in the danger tier (`RowAction danger`), because
 *  B14 rule 6 says the destructive control is distinguishable by COLOUR and
 *  not only by shape. B14 rule 15's prose calls this one "⚡ raise work". */
export function BoltIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" {...STROKE} />
    </svg>
  );
}

/** 🗓 calendar — "Payment plan": a schedule of dated instalments. */
export function CalendarIcon() {
  return (
    <svg {...ICON_BOX}>
      <rect x="3" y="4" width="18" height="17" {...STROKE} />
      <path d="M16 2v4M8 2v4M3 10h18" {...STROKE} />
    </svg>
  );
}


/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 wave I — THE DELIVERY SURFACES, so the Kind column stops being words
 * ══════════════════════════════════════════════════════════════════════════
 *
 * *"on this screen for KInd - can you use Icons - it will save real estate on
 * screen"* — the Product Owner, 2026-08-30, reading Settings → Configure →
 * Templates. That column prints the server's own delivery-format copy, and
 * three of its twelve values are compound — *"PDF + e-signature"*, *"Certified
 * print + email"*, *"Door hanger print + email"* — so they wrapped to two and
 * three lines and set the height of the rows they were in.
 *
 * ⚠ **A COMPOUND KIND IS N ICONS, NEVER ONE COMPOSITE GLYPH.** *"Email + SMS"*
 * draws the envelope and the bubble, each carrying its own half of the words as
 * its accessible name. A single "email-and-sms" mark would be unreadable, would
 * need a new glyph per combination, and would break the moment the server adds
 * a thirteenth value.
 *
 * ⚠ **AND EVERY ONE OF THEM KEEPS THE WORD IT REPLACED.** An icon-only cell is
 * unusable without a mouse unless the word survives as the accessible name, so
 * the SERVER's own text rides on `aria-label` and `title` — not a paraphrase
 * composed here, which would drift from the value the column sorts and filters
 * on. A silent glyph is a regression, not a declutter.
 *
 * Geometry is the row-action family's, unchanged: 16px in a 24-unit viewBox,
 * `aria-hidden`, `currentColor`, stroke 1.6. These are the same marks at the
 * same weight as the pencil and the eye beside them.
 */

/* ⚠ THESE FOUR ICONS LOOK DEAD AND ARE NOT (DEF-2735, 2026-09-01). MessageIcon,
 * DocumentIcon, SignatureIcon and BellIcon are drawn by the Templates list's
 * Kind column, through the KIND_GLYPHS lookup table in
 * `features/notifications/TemplateCatalog.tsx` — `{ icon: SignatureIcon }`,
 * rendered as `<glyph.icon />`. `<MessageIcon` appears NOWHERE, so a grep for
 * the mount finds nothing and G40 reported all four as rendered by nothing
 * until its detector learned to see a lookup-table mount. The row's honest
 * conclusion from that red was "either wire them or delete them"; deleting them
 * would have taken four live glyphs off a screen a clerk is looking at.
 */

/** 💬 SMS — a text message. A speech bubble and not a phone: the phone glyph
 *  reads as "call", which is the one thing this platform never does. */
export function MessageIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M21 12a8 8 0 01-8 8H8l-5 3 1.4-4.2A8 8 0 1121 12z" {...STROKE} />
    </svg>
  );
}

/** 📄 a PDF page — a printable document this platform RENDERS, as opposed to
 *  `PrinterIcon`, which is the act of putting one on paper. The folded corner
 *  is what tells the two apart at 16px. */
export function DocumentIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" {...STROKE} />
      <path d="M14 3v5h5" {...STROKE} />
    </svg>
  );
}

/** ✒ e-signature — a document a customer SIGNS. A written stroke over a base
 *  line, which is the one shape that reads as a signature rather than as a
 *  pencil (`PencilIcon`, four glyphs up, is edit and must stay distinct). */
export function SignatureIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M3 17c3 0 4-9 6.5-9S12 16 14 16s2.5-4 4-4 1.5 3 3 3" {...STROKE} />
      <path d="M3 21h18" {...STROKE} />
    </svg>
  );
}

/** 🔔 an in-app message — the one "surface" that never leaves the product. The
 *  shell's own bell (`ShellBellIcon`) is 18px and carries `.top-icon`, so it is
 *  not reusable inside a table cell; this is the same idea at the row-action
 *  family's geometry, which is the divergence this file's header already
 *  records for every other glyph. */
export function BellIcon() {
  return (
    <svg {...ICON_BOX}>
      <path d="M18 8a6 6 0 10-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" {...STROKE} />
      <path d="M10.3 21a2 2 0 003.4 0" {...STROKE} />
    </svg>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
 * THE SHELL VOCABULARY (DEF-349) — the second family, now in the one file
 * ══════════════════════════════════════════════════════════════════════════
 *
 * G37 found this on its first run, before it had ever been pointed at a defect:
 * `components/AppShell.tsx` declared its own `<svg>`s — the twelve rail glyphs,
 * the collapse/expand hamburger, the search glyph and the notification bell —
 * a SECOND icon vocabulary beside the row-action one this file owns. Nothing
 * was broken; they render correctly. The cost of a duplicated vocabulary is
 * only paid the day the vocabulary changes, and then the change is silently
 * partial — DEF-348, where the same pencil existed four times.
 *
 * The PO's ruling is wider than the defect that prompted it: *"Tailwind, CSS,
 * STylesheet, UI COmponents - we should ahve only one reference point not two"*
 * does not say "one per family". So they live here, and `AppShell.tsx` declares
 * no `<svg>` at all — its name is off `g37_row_actions.py`'s SVG_OWNERS list,
 * which leaves ONE owner, which is what that list was always meant to hold.
 *
 * ⚠ THE GEOMETRY IS A SECOND CONSTANT, AND THAT IS THE DECISION, NOT AN
 * OVERSIGHT. `ICON_BOX`/`STROKE` above are 16px at stroke 1.6; the shell family
 * is stroke 2 and is sized by AppShell.css (16px in the rail and on the bell,
 * 14px on the search) or by an explicit prop (the hamburger: 16 in the rail,
 * 18 in the top bar). Folding those into one constant would MOVE PIXELS on the
 * chrome of every screen in the product, and CR-018 §6 says a visual change is
 * filed rather than folded into a refactor. This move is byte-identical:
 * measured in Chromium before and after, 12 rail glyphs at 16x16 stroke 2px,
 * collapse 16x16, expand 18x18, search 14x14, bell 16x16 — every number the
 * same. **The remaining divergence — two strokes and two hamburger sizes — is
 * filed as DEF-574 to be RULED, because r10 draws its sidebar at 16px and every
 * stroke in its markup is 2, so it is the row-action family's 1.6 that has to
 * answer for itself.**
 *
 * `side-icon` travels WITH the glyph rather than being applied by the caller:
 * `AppShell.css` sizes `.side-item .side-icon`, and a rail glyph that forgets
 * the class renders at the browser's default 300x150 — exactly the "built is
 * not wired" shape (hard-won law 2).
 * ══════════════════════════════════════════════════════════════════════════ */

/** The shell family's geometry. The stroke sits on the `<svg>`, as it did in
 *  AppShell, so the children inherit it and the emitted markup is unchanged. */
const SHELL_ICON = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  "aria-hidden": true,
} as const;

/** ☰ collapse / expand — the SAME glyph at two sizes: 16 in the rail's brand
 *  row, 18 in the top bar. The pair is r10-divergent and is DEF-574's to rule;
 *  the prop keeps both exactly as they render today. */
export function ShellMenuIcon(props: { size: 16 | 18 }) {
  return (
    <svg {...SHELL_ICON} width={props.size} height={props.size}>
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  );
}

/** 🔍 the top-bar search glyph. No width/height: `.shell-search > svg` sizes it
 *  to 14px and positions it inside the input. */
export function ShellSearchIcon() {
  return (
    <svg {...SHELL_ICON}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

/** 🔔 the notification bell. Sized 16px by `.shell-bell > summary svg`. */
export function ShellBellIcon() {
  return (
    <svg {...SHELL_ICON}>
      <path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9M10 21a2 2 0 004 0" />
    </svg>
  );
}

/* ── The twelve rail glyphs, in BR-SHL-001's order ────────────────────────
 * Their PATHS are unchanged from AppShell.tsx; only their home moved. */

/** Rail · Dashboard */
export function NavDashboardIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <rect x="3" y="3" width="7" height="9" />
      <rect x="14" y="3" width="7" height="5" />
      <rect x="14" y="12" width="7" height="9" />
      <rect x="3" y="16" width="7" height="5" />
    </svg>
  );
}

/** Rail · Plans & Rates */
export function NavPlansRatesIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M4 4h16v6H4zM4 14h16v6H4zM8 4v6M16 14v6" />
    </svg>
  );
}

/** Rail · Premises */
export function NavPremisesIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M3 21V9l9-6 9 6v12M9 21v-8h6v8" />
    </svg>
  );
}

/** Rail · Assets */
export function NavAssetsIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <rect x="3" y="4" width="18" height="7" rx="1" />
      <path d="M7 8h.01M7 15h10M7 19h10" />
    </svg>
  );
}

/** Rail · Accounts */
export function NavAccountsIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-7 8-7s8 3 8 7" />
    </svg>
  );
}

/** Rail · Reads */
export function NavReadsIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

/** Rail · Billing */
export function NavBillingIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M4 4h16v18l-4-2-4 2-4-2-4 2z" />
      <path d="M8 9h8M8 13h8M8 17h5" />
    </svg>
  );
}

/** Rail · Payments */
export function NavPaymentsIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <rect x="2" y="6" width="20" height="14" />
      <path d="M2 10h20M6 16h4" />
    </svg>
  );
}

/** Rail · Work — a wrench, r10's own icon vocabulary for field work. */
export function NavWorkIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M14.7 6.3a4 4 0 01-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 015.4-5.4l-2.5 2.5-1.4-1.4z" />
    </svg>
  );
}

/** Rail · Finance */
export function NavFinanceIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M4 20V4M4 20h16M8 16V10M12 16V6M16 16v-4M20 16v-8" />
    </svg>
  );
}

/**
 * Rail · Runbooks — a checklist on a clipboard: a ticked line over two plain
 * ones. It says *a written procedure that gets run* without borrowing Reports'
 * document page or Work's wrench, which are its two neighbours on the rail.
 *
 * BR-SHL-001 amendment 3 (PO 2026-09-06, "Nav bar will have Runbook as menu
 * item - above reports module"). A12: inline SVG on currentColor, no icon font.
 */
export function NavRunbooksIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M9 3h6a1 1 0 011 1v1H8V4a1 1 0 011-1z" />
      <path d="M16 5h2a1 1 0 011 1v14a1 1 0 01-1 1H6a1 1 0 01-1-1V6a1 1 0 011-1h2" />
      <path d="M8 11l1.5 1.5L12 10M14 12h3M8 17h9" />
    </svg>
  );
}

/** Rail · Reports */
export function NavReportsIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6M9 13h6M9 17h4" />
    </svg>
  );
}

/** Rail · Settings */
export function NavSettingsIcon() {
  return (
    <svg {...SHELL_ICON} className="side-icon">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 01-4 0v-.1a1.7 1.7 0 00-1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 010-4h.1a1.7 1.7 0 001.5-1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 014 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 010 4h-.1a1.7 1.7 0 00-1.5 1z" />
    </svg>
  );
}
