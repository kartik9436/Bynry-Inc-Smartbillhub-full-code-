// ── Trace ──────────────────────────────────────────────
// Change:  PO report 2026-09-22 rows 2 and 3 — *"once you remove the virus
//          check - you will ahveonly two cases verified or rejected in case of
//          rejected show the reason in short to user why it is rejected."*
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT; standalone code inside a
//          page is not reuse) · rule 33 (a LABEL ≤ 3 words; RATIONALE zero
//          words on screen) · rule 21 (Tailwind utilities only — this file is
//          listed in `src/styles/route-b-migrated.txt`)
// Screens: `REQ-03.4` capture step 4 · `REQ-03.6` step 6's review table ·
//          `REQ-02` the request detail's Documents tab
// Defect:  `DEF-CUS-5872` (four seeded rows read `verified` over a file that
//          resolves to nothing)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ONE VERDICT, THREE TABLES, AND IT WAS SPELLED THREE WAYS
// ══════════════════════════════════════════════════════════════════════════
// When the PO's ruling landed it was built in `DocumentTable.tsx`, and the two
// other places that print the same fact were not touched:
//
//   * `ServiceRequestDetailPage.tsx`'s Documents tab — the REVIEWER's screen —
//     still drew a third, neutral `Not yet checked` pill and had never shown
//     the rejection reason at all;
//   * `ServiceRequestCapturePage.tsx` step 6's review table printed the RAW
//     `verification_state` through the catalogue with **no `file_present`
//     guard**, so on the beta's six broken rows (`DEF-CUS-5872`) it read
//     `Verified` over a file nobody can open.
//
// So the clerk who ATTACHES a document, the clerk who REVIEWS it and the
// screen that summarises it all said different things about one row. That is
// what rule 43 is for: the decision moves into a component, and the three
// tables ask it.
//
// ⚠ **`file_present`, NEVER `verification_state` ALONE.** Four of the beta's
// six placeholder rows carry `verified` over a `storage_ref` that resolves to
// nothing. A cell trusting the state column tells a clerk an identity document
// has been checked, over a file that cannot be opened.
//
// ⚠ **AND AN UNJUDGED FILE RENDERS AS NOTHING.** The ruling removes the third
// WORD, not the third STATE: a file that is attached and not yet reviewed is a
// real, reachable position and this product must not claim a verdict nobody
// gave. The empty cell is the invitation; the row's own actions are the door.
import { shortReason } from "./documentCapture";
import type { DocumentTranslator } from "./documentCapture";

/** What a document row says, once, for every table that prints it. */
export type DocumentVerdict = "nothing_attached" | "awaiting" | "verified" | "rejected";

/**
 * The verdict, decided from the two fields that carry it.
 *
 * Exported separately from the cell because a caller sometimes needs the
 * ANSWER without the markup — the Documents tab counts how many rows read
 * `verified` to print *"1 of 3 verified"*, and counting that a second way is
 * how a header and a table come to disagree (PO report 2026-09-22, row 4).
 */
export function documentVerdict(row: {
  file_present: boolean;
  verification_state: string;
}): DocumentVerdict {
  if (!row.file_present) return "nothing_attached";
  if (row.verification_state === "verified") return "verified";
  if (row.verification_state === "rejected") return "rejected";
  return "awaiting";
}

export function DocumentStateCell(props: {
  row: { file_present: boolean; verification_state: string; reject_reason: string | null };
  t: DocumentTranslator;
  /**
   * Say `Nothing attached` in words rather than leaving the cell empty.
   *
   * ⚠ **THE TWO TABLES DISAGREE ABOUT THIS FOR A REASON, AND IT IS NOT TASTE.**
   * The capture table has a FILE column one place left that already prints `—`
   * for a row with no file, and printing it twice made *no file yet* and
   * *reviewed and refused* read as one kind of thing — which is the ruling's
   * own argument. The request DETAIL's tab draws the file name as a control,
   * so its FILE cell is a dash with no words on it, and a reviewer scanning
   * that table needs the absence said once somewhere.
   */
  nameTheAbsence?: boolean;
}) {
  const verdict = documentVerdict(props.row);
  if (verdict === "rejected") {
    const reason = (props.row.reject_reason ?? "").trim();
    return (
      <span data-doc-verdict="rejected" data-doc-rejected="" className="text-danger-700">
        {props.t("customers.serviceRequest.capture.state.rejected")}
        {/* ⚠ **THE REASON, SHORT — row 3 of the PO's list.** `reject_reason`
            has been stored since the column was written and `reject_document`
            has REQUIRED one since it was built; no screen on the reviewer's
            side had ever rendered it, so a clerk could refuse a licence with a
            reason and the next clerk saw the word `Rejected` and nothing else.
            Cut by CHARACTERS and not by words, because this is not our
            sentence — see `shortReason`. */}
        {reason !== "" && (
          <span className="block text-neutral-700" data-reject-reason="" title={reason}>
            {shortReason(reason)}
          </span>
        )}
      </span>
    );
  }
  if (verdict === "verified") {
    return (
      <span data-doc-verdict="verified" data-doc-verified="">
        {props.t("customers.serviceRequest.capture.state.verified")}
      </span>
    );
  }
  if (verdict === "nothing_attached" && props.nameTheAbsence === true) {
    return (
      <span data-doc-verdict="nothing_attached" className="text-neutral-700">
        {props.t("customers.serviceRequest.capture.state.nothingAttached")}
      </span>
    );
  }
  /* ⚠ **NOTHING, NOT AN EM DASH.** A dash is a table's mark for *there is no
     file* and it belongs to the FILE column. A second dash here would be a
     fifth value wearing punctuation. */
  return <span data-doc-verdict={verdict} />;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO report 2026-09-22 rows 2, 3 and 4 · B14 rule 43
// gates: G31 skips this folder (Route B) and routeBUtilities.test.ts owns it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
