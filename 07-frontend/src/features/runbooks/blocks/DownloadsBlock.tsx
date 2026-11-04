// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C1b — block 12 of the twelve.
// Screens: every runbook EXCEPT 4, 6 and 13.  Rules: B14 rule 4 (`↓` downloads)
//          · rule 36 · IS-11 (the export formats).
// ───────────────────────────────────────────────────────
// The two result files. `DownloadButton` (FE-14) is the kit's control and
// already carries rule 4's `↓` grammar and the IS-11 format choice.
//
// ⚠ *"every runbook except 4, 6 and 13"* — from the COVERAGE table, not the
// block table, which claims all 21. The drawings settle it: those three sheets
// carry no `↓` button at all. An absent `downloads` block draws nothing, which
// is what those three show; a block that always rendered would put a download
// button on three screens the pack does not give one.
import { DownloadButton } from "@/components/DownloadButton";

import type { DownloadsPayload } from "./types";

export function DownloadsBlock(props: {
  payload: DownloadsPayload;
  /** Which file, in which format. Required: a download control wired to nothing
   *  is dead UI that passes every test (hard-won law 2, G13's own shape). */
  onDownload: (fileId: string, format: "csv" | "pdf") => void;
}) {
  return (
    <div className="flex flex-wrap gap-2" data-block="downloads">
      {props.payload.files.map((file) => (
        <span key={file.id} data-download={file.id} title={file.label}>
          <DownloadButton
            pdf={file.format === "pdf"}
            onDownload={(format) => props.onDownload(file.id, format === "pdf" ? "pdf" : "csv")}
          />
        </span>
      ))}
    </div>
  );
}
