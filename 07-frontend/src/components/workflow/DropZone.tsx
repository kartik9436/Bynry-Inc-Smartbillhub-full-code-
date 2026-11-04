// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 1 EXTRACT, the file target (design B15 §4.1)
// Rules:    BR-MET-018 (a read import is keyed on the FILE, and the hash is what
//           identifies it) · B14 rule 21 (Tailwind)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { ReceivedFile } from "./contract";
import * as WF from "./workflowKit";

/**
 * The file target, which **states what it received**: name, row count, size and
 * SHA-256.
 *
 * ⚠ THE HASH IS ON SCREEN BECAUSE THE RECEIPT PROMISES IT LATER. B15 §4.5's
 * receipt reads `c19a…4407 · verified`, and a hash a user first sees at stage 5
 * is a hash they cannot compare against anything. Showing it at the moment the
 * file is accepted is what makes "verified" mean something.
 *
 * ⚠ AND IT IS THE SERVER'S DIGEST, ALWAYS (B15 §16 TC-2: *"a client-supplied
 * hash proves nothing"*). This component receives `ReceivedFile` from
 * `POST /imports` and displays it; it computes nothing.
 *
 * ⚠ EMPTY IS A STATE, NOT A BLANK BOX. Before a file arrives the target says so
 * in the same place the facts will appear, so nothing on the stage moves when
 * the file lands.
 */
export interface DropZoneProps {
  /** `null` until `POST /imports` answers. */
  file: ReceivedFile | null;
  onBrowse: () => void;
}

export function DropZone({ file, onBrowse }: DropZoneProps) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className={WF.DROPZONE}
      data-workflow="dropzone"
      data-state={file === null ? "empty" : "received"}
      onClick={onBrowse}
    >
      <span>{t("workflow.drop.prompt")}</span>
      {file === null ? (
        <span className={WF.DROPZONE_FACTS}>{t("workflow.drop.empty")}</span>
      ) : (
        <>
          <span className={WF.DROPZONE_FACTS} data-workflow="dropzone-facts">
            {file.name}
            {/* ⚠ **`0` IS NOT A ROW COUNT — CR-054 task 18.** Both callers hand
                this component a file BEFORE the server has counted it: the
                premises runner passes `rows: 0` for a picked-but-not-uploaded
                file, and reads has the bytes in the browser and deliberately
                does not count them itself (ONE counting path — hard-won law 5).
                Printing "0 rows" over a file the clerk can see has 1,180 of them
                is the `CR-036` (f) failure in miniature: the true statement is
                *not yet*, and the screen said *none*. So the clause appears when
                there is a count and not before. */}
            {file.rows > 0 ? ` · ${t("workflow.drop.rows", { count: file.rows })}` : ""} ·{" "}
            {file.size_label}
          </span>
          {file.sha256 !== "" && (
            <span className={WF.DROPZONE_HASH} data-workflow="dropzone-hash">
              {t("workflow.drop.hash", { hash: file.sha256 })}
            </span>
          )}
        </>
      )}
    </button>
  );
}
