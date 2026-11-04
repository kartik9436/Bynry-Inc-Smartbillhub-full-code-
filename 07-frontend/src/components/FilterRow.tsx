// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6728 — Finance > Close & export: the params band is one row
//          on THREE baselines. PO, deployed v2.351.84, tenant Ottumwa Water
//          Works: *"on close and export screen - filter is not align - it is
//          not in 1 line."*
// Rules:   B14 rule 44 (the drawing says WHAT is on the screen; our spacing,
//          token scale and component kit say HOW, and they win — including the
//          frame) · B14 rule 38 (rule 44's worked case for forms: side-by-side
//          fields and help under an input are CONSTRUCTION, ours to decide) ·
//          B14 rule 43 (a piece of UI is a COMPONENT; a bar aligned by hand on
//          one screen is not reuse) · B14 rule 21 (Tailwind utilities, no class
//          added to a stylesheet) · B14 rule 39 (the ratified field rhythm).
// ───────────────────────────────────────────────────────
//
// ONE HORIZONTAL BAND OF FILTER CONTROLS, ON ONE BASELINE, WITH ITS ACTION.
//
// ── WHAT WENT WRONG, MEASURED ───────────────────────────────────────────────
//
// Twenty screens in this product hand-roll `flex flex-wrap items-end gap-4`
// around a handful of kit fields. `items-end` aligns the BOTTOM of each field's
// box — and a field's box is label + control + whatever hangs under the
// control. So the instant one field in the row carries a sentence under its
// input and its neighbours do not, that field's LABEL and CONTROL are pushed up
// by the height of the sentence, and the row silently becomes two rows.
//
// Measured in Chromium at 1440px on `/:tenant/finance/export?view=export`,
// tenant date format `DD-MMM-YY` (`10-scripts/finance_filter_row_baseline.mjs`):
//
//     Period start / Period end   label top 334   input top 357   (echo below)
//     Group by / Send it to / Detail   label top 356   input top 380
//     Apply                                            top 377
//
// Three heights in one row: 23px between the dates and the selects, and Apply
// on a third because it carried a hand-written `pb-1` to push it down.
//
// ⚠ **AND IT IS INVISIBLE ON OUR OWN FIXTURE.** The sentence under those two
// date inputs is `regionalDateEcho` (IS-8) — the tenant's own date format,
// rendered ONLY when it differs from what the browser's locale draws inside the
// native control. `brazosbend` is `MM/DD/YYYY`, which is exactly what a
// headless Chromium draws, so the echo returns `null`, the bar measures
// perfectly aligned, and every test and every screenshot this repo has ever
// taken of this screen is of a bar that is not the one most tenants see. Six of
// the seven formats show it. That is hard-won law 6 with a twist: looking is
// necessary and not sufficient — you have to look at the tenant who complained.
//
// ── THE FIX IS THE RHYTHM, NOT A MARGIN ─────────────────────────────────────
//
// Nudging a margin until it looks right at 1440px is how this comes back; the
// nudge is `pb-1` and it is already here, on Apply, from the first build.
//
// The row aligns from the TOP instead, so **the baseline a control sits on no
// longer depends on anything BELOW it**: the label row is row one for every
// field, the control row is row two for every field, and a required marker
// (inline in the label) or a help/echo line (under the control) is out of the
// flow that decides where the control sits. Whether a field has them stops
// being a layout question.
//
// The action gets the same treatment rather than an offset: `FilterRowAction`
// renders a RESERVED, empty `.field-label` line above the button, so the button
// lands on the control row because it has a label slot exactly like every field
// beside it. It is reserved, never measured — the height comes from the same
// `.field-label` rule the real labels use, so if the type scale moves, the
// button moves with them. A `pt-[23px]` would not.
//
// ⚠ **IT HOLDS AT PHONE WIDTH BECAUSE IT STOPS BEING A ROW.** `flex-wrap` puts
// each cell on its own line under ~640px; a stacked cell's baseline is its own,
// the reserved label above the action is a blank line in a stack of fields —
// which is what every stacked form in the product already looks like — and
// `ml-auto` on a cell that is alone on its line does nothing. Verified at 390px.
//
// ⚠ **ONE THING THIS DOES NOT RESERVE, SAID OUT LOUD RATHER THAN LEFT TO BE
// DISCOVERED (hard-won law 1).** A label that WRAPS to two lines makes its own
// cell's control drop a line below its neighbours', because the label row is
// reserved by the tallest label rather than fixed at one line. Every caller
// today gives its cells a `min-w` wide enough for their label. Fixing it
// properly needs `grid-template-rows: subgrid` across the cells, which needs
// the kit's `.field` to become a grid participant — a change to every form in
// the product, not to this bar. If a wrapping label is ever reported, that is
// the fix, and it belongs to the kit.
import type { ReactNode } from "react";

/**
 * The band itself. `children` are the cells — kit fields, each in its own
 * width wrapper — and `action` is the one control that ACTS on them (`Apply`,
 * `Search`), pushed to the trailing edge.
 *
 * `as="form"` is offered because a params band should apply on Enter: a clerk
 * who has typed two dates expects the keyboard to work. The caller owns
 * `onSubmit`; this owns only the layout.
 */
export function FilterRow(props: {
  children: ReactNode;
  action?: ReactNode;
  /** Submitted as a form, so Enter applies. Default: a plain `div`. */
  onSubmit?: () => void;
  /** A name for the band in tests and walkthroughs. */
  "data-filter-row"?: string;
}) {
  const inner = (
    <>
      {props.children}
      {props.action !== undefined && <FilterRowAction>{props.action}</FilterRowAction>}
    </>
  );
  // `items-start`: the control's baseline is decided by the label above it and
  // by nothing under it. See the note above — this is the whole fix.
  const className = "flex flex-wrap items-start gap-4";
  if (props.onSubmit === undefined) {
    return (
      <div className={className} data-filter-row={props["data-filter-row"] ?? ""}>
        {inner}
      </div>
    );
  }
  return (
    <form
      className={className}
      data-filter-row={props["data-filter-row"] ?? ""}
      onSubmit={(event) => {
        event.preventDefault();
        props.onSubmit?.();
      }}
    >
      {inner}
    </form>
  );
}

/**
 * The trailing action's cell, with the RESERVED label slot that puts the button
 * on the same row as the controls.
 *
 * The blank line is `aria-hidden` and carries a non-breaking space so it has
 * the height of a line of label text rather than the height of nothing. It
 * announces nothing to a screen reader: the button already says what it does.
 *
 * Exported separately so a band with two actions can place the second one the
 * same way instead of inventing an offset for it.
 */
export function FilterRowAction(props: { children: ReactNode }) {
  return (
    // ⚠ **`field` AND A REAL `<label>`, NOT A `<span>` THAT LOOKS LIKE ONE.**
    // The first draft reserved the slot with `<span className="field-label">`
    // and the button came out **1px** high of the controls beside it. The kit
    // states the label's bottom margin TWICE — `.field-label` (4px) and
    // `.field > label` (5px), the second winning on specificity — so a slot
    // that is not a `label` inside a `.field` gets the other number. Measured
    // in Chromium, not guessed: input top 357, button top 356.
    //
    // Reserving the slot with the same ELEMENT in the same CONTEXT as a real
    // label is the difference between a reserved slot and a 1px guess, and it
    // is the whole point of this file: the height is the KIT's, so the kit
    // stays the only thing that decides it.
    <div className="field ml-auto" data-filter-row-action="">
      <label className="field-label" aria-hidden="true">
        {" "}
      </label>
      {props.children}
    </div>
  );
}
