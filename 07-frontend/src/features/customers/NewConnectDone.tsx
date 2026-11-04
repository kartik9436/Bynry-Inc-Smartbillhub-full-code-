// ── Trace ──────────────────────────────────────────────
// Change:   Lane E wave 1 — SPLIT OUT OF `NewConnectWizard.tsx`, unchanged.
//           One file per step so five lanes can work at once instead of
//           queueing on one ~1,900-line file (CLAUDE.md law 11 — in a
//           shared tree the second lane to commit reverts the first, with
//           a correct file count and nothing in the diff to notice).
// Rules:    BR-SHL-025 (a control that cannot act is DISABLED WITH ITS
//           REASON) · CR-151-BRC09 (a build has its own page again, NCT-02)
//           · B14 rules 21, 31, 33
// Defects:  DEF-CUS-9174 (raw codes on screen; "2 document filed.") ·
//           DEF-CUS-9175 (Open went to the account, not the build's page)
// Tests:    NewConnectWizard.test.tsx · newConnectDoneAbsences.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Kicker, Note } from "@/components/TextBits";
import { useTenantPath } from "@/routing/tenantPath";

import type { CommitResult } from "./newConnectEndpoints";
import { buildPagePath, commitAbsenceNotes } from "./newConnectShared";
import type { Translator } from "./newConnectShared";
import { ManifestRow } from "./newConnectStepKit";

// ══════════════════════════════════════════════════════════════════════════
// THE ANSWER — replacing the wizard rather than navigating away from it
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **THE COMMIT'S OWN `unavailable` BLOCK IS RENDERED, NOT SWALLOWED.**
 * `commit_connection` answers with two stated absences on a perfectly
 * successful commit — the quote was recorded and posted by nothing, and no
 * sub-meter link could be made. A toast on the way to the detail screen would
 * show neither, and the person who just built 26 units would find out later.
 */
export function NewConnectDone(props: {
  result: CommitResult;
  t: Translator;
  /**
   * How the owner's step-1 documents fared — PO ruling 2026-09-21.
   *
   * ⚠ **`null` MEANS THE CLERK BROUGHT NONE, AND IT IS NOT THE SAME AS ZERO
   * FILED.** Nothing is drawn for a build with no documents; a build whose
   * documents could NOT be filed says so, with the count, because a clerk who
   * handed over three deeds and is told nothing will assume all three landed.
   * Hard-won law 2's mirror — a control that reached nothing, silently.
   *
   * ⚠ **THE COUNT IS PLURALISED BY THE CATALOGUE (`_one` / `_other`)** —
   * `DEF-CUS-9174`: one form for every count read *"2 document filed."*.
   */
  documents?: { filed: number; unfiled: number } | null;
}) {
  // ⚠ `DEF-CUS-9175` — THE DESTINATION IS DECIDED HERE, NOT BY THE HOST. It
  // was an `onOpen(home)` callback the wizard filled with `buildHomePath`,
  // which is the owner's ACCOUNT; a callback made the address untestable from
  // this component, so the test that would have caught it could not be
  // written. Now `newConnectDoneAbsences.dom.test.tsx` mounts this under the
  // real route pattern and asserts where the press lands, by address.
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  return (
    <Panel as="section" data-commit-done="">
      <Kicker>{props.t("customers.newConnect.done.kicker", { defaultValue: "Created" })}</Kicker>
      <h2 className="font-heading text-h4 m-0 mb-2">{props.result.connection_no}</h2>
      <PlainTable>
        <tbody>
          <ManifestRow
            label={props.t("customers.newConnect.manifest.units", { defaultValue: "Units" })}
            value={props.result.manifest.units}
          />
          <ManifestRow
            label={props.t("customers.newConnect.manifest.meters", { defaultValue: "Meters" })}
            value={props.result.manifest.meters}
          />
          <ManifestRow
            label={props.t("customers.newConnect.manifest.planAssignments", {
              defaultValue: "Plan assignments",
            })}
            value={props.result.manifest.plan_assignments}
          />
        </tbody>
      </PlainTable>
      {props.documents != null && props.documents.filed > 0 && (
        <Note className="mt-2 max-w-measure" data-documents-filed={props.documents.filed}>
          {props.t("customers.newConnect.done.documentsFiled", {
            count: props.documents.filed,
          })}
        </Note>
      )}
      {props.documents != null && props.documents.unfiled > 0 && (
        <RefusalStrip data-documents-unfiled={props.documents.unfiled}>
          {props.t("customers.newConnect.done.documentsUnfiled", {
            count: props.documents.unfiled,
          })}
        </RefusalStrip>
      )}
      {/* ⚠ **`DEF-CUS-7692` — THIS RENDERED `{absence.detail}` AND THAT IS 86
          WORDS OF THE SERVER'S OWN ENGLISH RATIONALE.** B14 rule 33 puts
          rationale at ZERO words on screen and `BR-SHL-020 r2` keeps English
          off the wire. **THE ABSENCE IS STILL STATED — only the reasoning
          goes.** The server's `detail` is untouched on the payload, for
          support and the log.

          ⚠ **`DEF-CUS-9174` — AND THE FACTS THEN PRINTED AS CODES.** A payment
          taken at step 4 forwards its own problems onto this list
          (`BR-MET-1187`), receipts and queue notes among them, and the old
          fallback printed any code it did not know: twelve tokens on one real
          commit. `commitAbsenceNotes` drops bookkeeping, words what a clerk
          can act on, de-duplicates, and never returns a code (B14 rule 31). */}
      {commitAbsenceNotes(props.result.unavailable, props.t).map((note) => (
        <Note key={note.code} className="mt-2 max-w-measure" data-absence={note.code}>
          {note.sentence}
        </Note>
      ))}
      {/* ⚠ `DEF-CUS-9175` — the button opens the BUILD'S OWN PAGE, NCT-02 at
          `/connections/<id>`, restored by `CR-151-BRC09`. Until 2026-10-02 it
          opened the build's HOME (wave O, when that page had been deleted),
          which landed a clerk on the owner's account. A commit always answers
          with its id, so the disabled branch is a guard rather than a case,
          and it says why instead of doing nothing (`BR-SHL-025`). */}
      <div className="mt-4">
        {(props.result.id ?? "") === "" ? (
          <Button
            disabled
            title={props.t("customers.newConnect.done.openBlocked", {
              defaultValue: "This build has no home yet.",
            })}
          >
            {props.t("customers.newConnect.done.open", { defaultValue: "Open the connection →" })}
          </Button>
        ) : (
          <Button
            data-open-build=""
            onClick={() => navigate(tenantPath(buildPagePath(props.result.id)))}
          >
            {props.t("customers.newConnect.done.open", { defaultValue: "Open the connection →" })}
          </Button>
        )}
      </div>
    </Panel>
  );
}
