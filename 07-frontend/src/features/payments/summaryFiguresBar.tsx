// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-PAY-6335` — PO, walking S32 on 2026-09-23: *"these detailsa re
//          not aligned on ui - Figures for*"*. The business-day field, the two
//          counters and the *Mark returned post* button shared one band and sat
//          on three different baselines.
// Rules:   BR-TEN-043 (`as_of` is asked for, never taken from a clock) ·
//          BR-PAY-015 (autopay capture intents are a COUNT — there is no retry
//          and no charging path in v1, so this one carries no action) ·
//          BR-PAY-018 (the returned-post queue) · US-PAY-016 (S35's bulk mark,
//          the action that clears it) · IS-8 (the tenant's date format) ·
//          B14 rule 43 (a piece of UI is a COMPONENT — this file exists because
//          the band was 50 lines inside `SummaryTab.tsx`, importable by nothing)
//          · B14 rule 21 (Tailwind utilities, NO class added to a stylesheet —
//          listed in `src/styles/route-b-migrated.txt` in the same commit) ·
//          B14 rule 36 (the shared kit is how you comply: `DatePickerField` and
//          `Button` are the kit's, and the labelled figure follows
//          `components/AgeingCards.tsx`, the kit piece this blueprint already
//          minted) · B14 rule 33 (every string here is measured, not assumed)
// Screens: S32 — Payments → Summary, the top band
// Tests:   src/features/payments/summaryFiguresBar.dom.test.tsx (what a source
//          check can decide) · 10-scripts/render-checks/def-pay-6335-summary-
//          band.mjs (the geometry, which jsdom cannot see)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THE ALIGNMENT IS STRUCTURAL HERE AND WAS NOT BEFORE
// ══════════════════════════════════════════════════════════════════════════
// The band used to be `.pay-toolbar` — `display:flex; align-items:flex-end` —
// with the field as one child and a `.pay-chips` group as the other. That was
// CORRECT for a two-line field, and `payments.css` said so in as many words:
// *"`align-items: flex-end` lines the chips up with the bottom of the date
// input rather than its label"*. It stopped being true the moment the field
// grew to FOUR lines — label, input, the help sentence, and the IS-8 format
// echo — because flex-end aligns to the bottom of all four. **Measured on
// 2026-09-23: the counters' centre line sat at y=314 and the input's at y=268,
// and the band was 83px from the highest control's top to the lowest one's
// bottom.** Hard-won law 1: a comment claiming a guarantee is not the
// guarantee, and this one outlived its own premise by three weeks.
//
// ⚠ **SO NOTHING IN THIS BAND TAKES ITS ALIGNMENT FROM A NEIGHBOUR'S HEIGHT.**
// Every column is the same two boxes — a label, then a 36px control row — so
// the figures land on the input's row BY CONSTRUCTION rather than by an offset
// somebody measured once. Add a second help sentence tomorrow and the band is
// still aligned; that is the property the old one lacked.
//
// ⚠ **AND IT NO LONGER SHARES `.pay-toolbar` WITH FIVE SCREENS IT CANNOT SEE.**
// `BadDebtPanel`, `OutstandingsTab`, `WriteOffQueuePage`, `DepositsPage` and
// `CollectionsPage` all draw that class, so the tempting one-line fix — change
// `align-items` — moves five other screens on this screen's authority. That is
// the blast-radius half of the maintenance process (`12-governance/22-product-
// maintenance-process.md`), and it is why this is a new component rather than a
// CSS edit.
//
// ══════════════════════════════════════════════════════════════════════════
// THE DATE IS NOT PRINTED TWICE — THE SECOND LINE IS THE TENANT'S FORMAT
// ══════════════════════════════════════════════════════════════════════════
// `09/23/2026` in the control and `23-Sep-26` under it look like one fact said
// twice. They are not. A native `<input type="date">` renders in the BROWSER's
// locale, never the tenant's, so `DatePickerField` draws the IS-8 line beneath
// it — and `regionalDateEcho` returns **null** when the two would read the same
// (CR-043 finding 15), so that line appears ONLY when it is saying something
// the control is not. On a tenant whose `date_format` is `DD-MMM-YY` it is the
// one place their own format ever reaches this screen.
//
// ⚠ **IT IS KEPT, AND WHAT MAKES IT READ AS AN ECHO IS WHERE IT SITS.** Adrift
// in a wrap-flex band it was a stray date; inside the field's own 240px column,
// under the input it belongs to, it is that field in the tenant's format. There
// is no caption saying so and there must not be: B14 rule 33 puts RATIONALE at
// ZERO WORDS ON SCREEN, so the reason lives in this comment, which is what a
// comment is for.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { DatePickerField } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";

/**
 * One labelled figure, built as the kit's `AgeingCards` builds one: the name
 * above, the number below, nothing boxed.
 *
 * ⚠ **THE LABEL'S `mb-[5px]` IS `.field > label`'s DECLARED 5px AND NOT A
 * NUMBER SOMEBODY LIKED** (`FormModal.css`, and `DEF-SHL-4921` records why it
 * is 5 rather than the helper's 6). It is the one thing that makes a counter's
 * label box the same height as the field's, which is what puts the figure on
 * the input's row. Change it and the band goes out by that many pixels, and the
 * render-check beside this file will say so.
 */
function Counter(props: { id: string; label: string; value: number; children?: ReactNode }) {
  return (
    <div data-counter={props.id} className="shrink-0">
      <span data-counter-label="" className="mb-[5px] block text-sm text-neutral-700">
        {props.label}
      </span>
      {/* `h-9` is `.input`'s 36px. The figure and any action beside it are
          centred in that box, so both sit on the business-day input's row. */}
      <div className="flex h-9 items-center gap-3">
        <span
          data-counter-value=""
          className="font-heading text-h4 font-extrabold leading-none tabular-nums"
        >
          {props.value}
        </span>
        {props.children}
      </div>
    </div>
  );
}

export interface SummaryFiguresBarProps {
  /** BR-TEN-043: the business day. Held by the page, typed by the clerk, and
   *  never read from a clock — here or on the wire. */
  asOf: string;
  onAsOfChange: (next: string) => void;
  /** IS-8: the tenant's Regional format, which is what the echo line states. */
  dateFormat: RegionalDateFormat;
  /**
   * The two needs-attention counts, or **null while the read has not answered**
   * — `GET /payments/summary`'s `chips`, passed through unrenamed.
   *
   * ⚠ **NULL DRAWS NO COUNTERS, WHICH IS WHAT THE SCREEN ALREADY DID.** The
   * band was `{view !== undefined && …}` around the whole chip group before
   * this component existed, and a counter that renders `0` while the server
   * has said nothing is a screen claiming a fact it does not hold. The field
   * still draws, because the business day is the clerk's to type whether or
   * not the figures have arrived.
   *
   * · `autopay_scheduled` (BR-PAY-015) carries **no action on purpose**: v1
   *   records what SHOULD be captured and staff record the money, so a control
   *   here would be a charging path the product does not have.
   * · `returned_mail` (BR-PAY-018) carries one — see `onMarkReturnedPost`.
   */
  chips: { autopay_scheduled: number; returned_mail: number } | null;
  /** US-PAY-016 — S35's bulk mark. The count states the backlog; this clears
   *  it. Until this button existed the queue was one nobody could add to,
   *  which is what `surface_debt.txt`'s `payments` line said in as many words. */
  onMarkReturnedPost: () => void;
}

/**
 * S32's top band: the business day these figures cover, what is waiting, and
 * the one act that clears it.
 */
export function SummaryFiguresBar(props: SummaryFiguresBarProps) {
  const { t } = useTranslation();
  return (
    <div
      data-band="summary-figures"
      className="mb-4 flex flex-wrap items-start gap-x-8 gap-y-3 border-t-2 border-t-divider bg-surface px-4 py-3"
    >
      {/* `w-60` is the 240px `.pay-toolbar .field` capped a date input at, for
          the reason recorded there: a native date input reports a large
          max-content width, so uncapped it eats the row and everything else
          wraps under it. The help sentence and the format echo hang BELOW the
          control row inside this column, which is exactly why no sibling may
          take its alignment from this block's height. */}
      <div className="w-60 shrink-0">
        {/* B14 rule 33 — the help text says WHAT the field is and stops there.
            It once carried the reason as well ("It is never taken from a
            clock, so yesterday's numbers stay yesterday's"), which is
            BR-TEN-043 explained to a clerk trying to type a date. Six words,
            measured: "The business day these figures cover." */}
        <DatePickerField
          id="summary_as_of"
          label={t("payments.summary.asOf")}
          value={props.asOf}
          onChange={props.onAsOfChange}
          dateFormat={props.dateFormat}
          required
          help={t("payments.summary.asOfHelp")}
        />
      </div>

      {props.chips !== null && (
        <>
          <Counter
            id="autopay"
            label={t("payments.summary.chip.autopay")}
            value={props.chips.autopay_scheduled}
          />

          <Counter
            id="returned-mail"
            label={t("payments.summary.chip.returnedMail")}
            value={props.chips.returned_mail}
          >
            <Button variant="secondary" onClick={props.onMarkReturnedPost}>
              {t("payments.returnedMail.bulk.open")}
            </Button>
          </Counter>
        </>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6335 (maintenance) · `05-prototype/06 Payments Page Blueprint.pdf` p027-p029 read as IMAGES at 2.0 and 6.0 (B14 rule 42)
// generated: 2026-09-23 by LANE FIGURES-FOR
// checklist: A=n/a(no endpoint change) B✔ C✔ D✔(browser) E✔ F✔ G✔ H=n/a
// gates: tsc · vitest summaryFiguresBar.dom.test.tsx + SummaryTab.test.tsx · G31 (this file is on src/styles/route-b-migrated.txt) · routeBUtilities.test.ts · 10-scripts/render-checks/def-pay-6335-summary-band.mjs in BOTH modes
// exceptions: ⚠ THE BLUEPRINT DRAWS NO SUCH BAND AT ALL. §03 frame 1·1 (p027-p029) redraws S32 AS A WORKLIST — counter band, `Needs you`, `TODAY` tiles — and neither the business-day field nor these two counters nor this button appear anywhere on it. That is a whole redesign with its own read ("One read that gathers the five waiting counts") and it is FILED, not built here: building it would delete the only control that types `as_of` (BR-TEN-043 requires it on the wire) and the only door to US-PAY-016's bulk mark, which is B14 rule 41's one legitimate question — a drawn element that contradicts a signed rule. This lane fixed the band the PO reported and left the redesign owned rather than silently half-done.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
