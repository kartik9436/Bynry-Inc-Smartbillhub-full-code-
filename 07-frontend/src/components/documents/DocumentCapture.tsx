// ── Trace ──────────────────────────────────────────────
// Change:  **B14 rule 43**, PO 2026-09-20: *"document sotrage - we need to
//          make it compoentn so thatw e cna use it in other palces also"*.
//          This is the whole block a host renders in one line.
// Rules:   B14 rule 43 (clause 3 — where two hosts draw it differently, share
//          the field set and let each own its construction) · rule 32 (a
//          stated absence is CLOSED by default) · rule 33 · rule 21
// Screens: `REQ-03.4` step 4 today; `TRF-02.x` next.
// ───────────────────────────────────────────────────────
import type { RegionalDateFormat } from "@/components/DateCell";

import { DocumentCaptureForm } from "./DocumentCaptureForm";
import type { DocumentTypeOption } from "./DocumentCaptureForm";
import { DocumentTable } from "./DocumentTable";
import type {
  DocumentCaptureValue,
  DocumentRequiredOf,
  DocumentRow,
  DocumentTranslator,
} from "./documentCapture";

/**
 * **THE WHOLE DRAWN BLOCK — table, chips, form, two buttons** — in one
 * element, for a host that draws it the way p078 does.
 *
 * ⚠ **A HOST THAT DRAWS IT DIFFERENTLY DOES NOT HAVE TO TAKE THIS ONE.** Rule
 * 43 clause 3: where two screens legitimately draw the same block
 * differently, share the FIELD SET and let each own its CONSTRUCTION, never
 * fork the block. So `DocumentTable` and `DocumentCaptureForm` are each
 * exported on their own — a transfer step that wants the form and no table
 * takes the form, and it is still the same form.
 *
 * ⚠ **THE FILTER IS THE ONLY STATE THIS HOLDS, AND IT IS VIEW STATE.** Which
 * chip is pressed is nothing the server stores and nothing a host needs back.
 * The half-typed form IS handed out, because a `File` a clerk has chosen is
 * the one thing a host may want to keep across a step change.
 */
export function DocumentCapture(props: {
  /** Everything the record holds, unfiltered. */
  rows: readonly DocumentRow[];
  value: DocumentCaptureValue;
  onChange: (next: DocumentCaptureValue) => void;
  onSubmit: (withFile: boolean) => void;
  docTypes: readonly DocumentTypeOption[];
  requiredOf: DocumentRequiredOf;
  t: DocumentTranslator;
  locale: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  busy?: boolean;
  error?: string | null;
  resetNonce?: number;
  accept?: string;
  idPrefix?: string;
  /** See `DocumentCaptureForm` — `false` draws ONE `Attach a file` button
   *  and keeps BOTH of its routes (`DEF-CUS-7851`). Defaults to `true`. */
  expectedDocumentButton?: boolean;
  /** See `DocumentCaptureForm` — `false` drops the `Attaching one`
   *  heading the approved REQ-03 drawing does not draw. Defaults to `true`. */
  formHeading?: boolean;
  onOpen?: (row: DocumentRow) => void;
  /** See `DocumentTable` — `CR-158-BRC10`, save rather than open. */
  onDownload?: (row: DocumentRow) => void;
  openingId?: string | null;
  openError?: string | null;
  /** See `DocumentTable` — `CR-163-BRC10` items 24 and 25. */
  docTypeLabel?: (code: string) => string;
  withoutChecklist?: boolean;
  openAsIcon?: boolean;
}) {
  return (
    // ══════════════════════════════════════════════════════════════════════
    // **ONE BLOCK, ONE RHYTHM — PO 2026-09-22, item 8**, verbatim: *"relay out
    // the documents section"* so the table, the attach control and the buttons
    // **read as one thing**.
    //
    // ⚠ **THE FIX IS A RHYTHM, NOT A BOX.** These were four siblings of a
    // fragment, each carrying whatever margin it happened to have: the table
    // met the host's `<h3>` at **8px** (measured in a browser, item 6) and the
    // form's own `mt-4` did the rest, so the section read as three unrelated
    // things stacked. `flex flex-col gap-5` is B14 rule 39's **20px**, the one
    // this product already uses between a field and the next, applied ONCE at
    // the group instead of per child. `mt-5` above the group is the same 20px
    // between the host's heading and the first thing under it.
    //
    // ⚠ **IT IS A GAP AND NOT A MARGIN ON EACH CHILD, DELIBERATELY.** A margin
    // per child is what produced the 8px: two of them collapse, a third does
    // not, and nobody can see which. A gap cannot collapse and there is one
    // number to read.
    // ══════════════════════════════════════════════════════════════════════
    <div className="mt-5 flex flex-col gap-5" data-doc-section="">
      {/* ⚠ **FOUR WORDS, AND ONLY WHEN THE RECORD REALLY HOLDS NOTHING.**
          Rule 32 puts a stated absence CLOSED by default — nothing to show is
          nothing on screen, not an empty table with an explanation under it. */}
      {props.rows.length === 0 ? (
        <p className="text-sm text-neutral-700" data-doc-empty="">
          {props.t("customers.serviceRequest.capture.nothingBroughtIn")}
        </p>
      ) : (
        <DocumentTable
          rows={props.rows}
          t={props.t}
          locale={props.locale}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          requiredOf={props.requiredOf}
          onOpen={props.onOpen}
          onDownload={props.onDownload}
          openingId={props.openingId}
          openError={props.openError}
          docTypeLabel={props.docTypeLabel}
          withoutChecklist={props.withoutChecklist}
          openAsIcon={props.openAsIcon}
        />
      )}
      {/* ══════════════════════════════════════════════════════════════════
          ⛔ **THE FOUR CHIPS ARE GONE FROM CAPTURE — PO 2026-09-22, item 10.**
          `All · Required · Missing · Rejected` are the REVIEWER's filters and
          **nothing on a capture screen can be Missing or Rejected**: nothing
          has been attached and nothing has been reviewed. They stay on
          `ServiceRequestDetailPage`, which is where a document is actually
          verified or rejected.

          ⚠ **AND THE CLERK CANNOT COME BACK HERE TO USE THEM, WHICH IS WHAT
          SETTLED IT RATHER THAN AN OPINION.** A request sent back for a
          rejected document does NOT reopen this wizard: the draft-resume path
          has zero production callers and `serviceRequestResumeHold.test.ts`
          (`DEF-CUS-5881`) fails if anybody wires one. So there is no state of
          this screen in which a chip has anything to narrow, and the
          conditional *show them when there is something to filter* would be a
          branch that can never be taken.

          ⚠ **THAT PATH IS NAMED IN PROSE HERE AND NOT SPELLED OUT, AND THE
          REASON IS WORTH KNOWING — `DEF-CUS-6193`.** The guard greps the
          source for the symbol and **cannot tell a comment from code**, so
          writing it in backticks made it report *"SOMETHING NOW LINKS TO THE
          DRAFT RESUME PATH"* over a file that links to nothing — a check
          failing on a fault it invented. Its own message says *do not add this
          file to an allow list and do not loosen this assertion*, and that is
          right: the guard protects a real money path (`DEF-CUS-5880` — a
          resumed draft renders EMPTY boxes over stored email, phone and SSN,
          and every step PUTs the whole form). So the comment moves instead of
          the guard. **The same weakness bit `routeBUtilities.test.ts` on the
          same day**, which is why it is recorded rather than just worked
          around.

          ⚠ **`DocumentFilterChips` IS DELETED (`DEF-GOV-10106`)** — an
          exported component nothing rendered, which G40 counts as dead UI.
          `DOCUMENT_FILTERS` and `filterDocumentRows` stay: they are the
          reviewer's vocabulary, and `ServiceRequestDetailPage` hand-rolls its
          own copy of the same four; adopting them there is rule 43's work.
          ══════════════════════════════════════════════════════════════════ */}
      <DocumentCaptureForm
        value={props.value}
        onChange={props.onChange}
        onSubmit={props.onSubmit}
        docTypes={props.docTypes}
        t={props.t}
        busy={props.busy}
        error={props.error}
        accept={props.accept}
        resetNonce={props.resetNonce}
        idPrefix={props.idPrefix}
        expectedDocumentButton={props.expectedDocumentButton}
        formHeading={props.formHeading}
      />
      {/* ⛔ **NO SCAN LINE, AND NO SCAN — PO 2026-09-22 and 2026-09-23.**
          The line read *"Every attachment lands Not checked."* and went on
          2026-09-22 (item 5, *"remove the virus check"*). ⚠ **ONLY THE
          SENTENCE WENT THAT DAY, AND THIS NOTE SAID "NOTHING ABOUT HOW A FILE
          IS HANDLED CHANGED" — WHICH WAS THE DEFECT.** A scanner still ran on
          the wire in front of every upload, so a host with no scanner refused
          every file this form sent (*"The virus scanner is unreachable"*).
          The PO asked again on 2026-09-23 and the scan itself is deleted,
          with its refusal keys and this line's key (`DEF-SHL-6347`). A PO
          instruction names a THING, not the words that describe it on screen.

          ⚠ **AND THE `Not checked` STATE WENT WITH IT** — see
          `DocumentStateCell`: STATE is the reviewer's two verdicts, and an
          unjudged file prints nothing. */}
    </div>
  );
}
