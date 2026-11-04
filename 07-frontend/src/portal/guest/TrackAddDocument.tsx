// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-9049 — after a clerk's *Ask for more*, the applicant had no
//          way to send a second document (21-walk W14, 2026-10-02). Track said
//          *More info needed* and nothing else.
// Rules:   B14 rule 43 (a component, not code inside a page) · rule 21
//          (utilities only) · rule 33 (a label ≤ 3 words) · BR-CWP-024 (the
//          server answers progress and never data — so the only names listed
//          here are the files THIS person sent in THIS visit)
// Screens: CWP-012 (Track), shown only when the server says `can_add_document`
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { FileDropField } from "@/components/FileDropField";

import type { TrackView } from "../api/guestClient";
import { postTrackDocument } from "../api/guestClient";
import { Card, StatusChip } from "../components/primitives";

import { APPLICATION_DOCUMENT_ACCEPT } from "./ApplicationDocuments";

/** The application's own figure (`CR-158-BRC10`) — the server is the authority
 *  and states what is left; this is only the per-file size it also enforces. */
const MAX_MB = 10;

/**
 * **ADD A DOCUMENT — the applicant answers *Ask for more* with a file.**
 *
 * The same drop zone, types and limits as the application's own step 3, and
 * each file goes to the server the moment it is chosen, proved again by the
 * reference and the second fact the lookup used. The list under it names only
 * what was sent from this page in this visit, after the server took it: the
 * server never echoes a file name to a stranger (`BR-CWP-024`).
 */
export function TrackAddDocument(props: {
  reference: string;
  secondFact: string;
  view: TrackView;
  /** The host replaces its found view with the server's answer. */
  onView: (view: TrackView) => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [sent, setSent] = useState<string[]>([]);
  const left = props.view.documents_left ?? 0;
  const open = props.view.can_add_document === true;
  if (!open && sent.length === 0) return null;

  async function take(file: File | null): Promise<void> {
    if (file === null) return;
    setError(undefined);
    setBusy(true);
    try {
      props.onView(await postTrackDocument(props.reference, props.secondFact, file, props.client));
      setSent((names) => [...names, file.name]);
    } catch (failure) {
      setError(refusalText(t, failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card testId="cwp012-add-document">
      <div className="flex flex-col gap-3" data-track-add-document="">
        {sent.length > 0 && (
          <ul className="flex flex-col" aria-label={t("portal.track.sentFiles")}>
            {sent.map((name, index) => (
              <li
                key={`${name}-${index}`}
                className="flex items-center justify-between gap-4 border-b border-neutral-200 py-2"
                data-sent-file={name}
              >
                <span className="min-w-0 break-words text-body text-neutral-800">{name}</span>
                <StatusChip tone="success">{t("portal.track.sent")}</StatusChip>
              </li>
            ))}
          </ul>
        )}
        <FileDropField
          id="track-add-document"
          label={t("portal.track.addDocument")}
          hint={busy ? t("portal.apply.uploading") : t("portal.apply.dropAFile")}
          browseLabel={t("portal.apply.chooseAFile")}
          accept={APPLICATION_DOCUMENT_ACCEPT}
          help={t("portal.apply.attachLimits", { max_mb: MAX_MB, max: left })}
          disabled={busy || !open}
          error={error}
          onChange={(file) => void take(file)}
        />
      </div>
    </Card>
  );
}
