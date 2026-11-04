// ── Trace ──────────────────────────────────────────────
// Change:  CR-158-BRC10 — a customer attaches documents to a new-service
//          application before sending it. PO 2026-10-01, verbatim: *"we need
//          to now accept the document from portal - make provisio, and use
//          upload document component we build"*. `DF-4` is superseded for the
//          new-service request ONLY.
// Defects: DEF-CWP-9166 — an attached file had Remove and no View (PO
//          2026-10-02: *"document upload is working but user not able to view
//          give view button"*) · DEF-CWP-9167 — ONE ATTACH ROW PER REQUIRED
//          DOCUMENT, PO ruling 2026-10-02 (option A): *"a separate attach row
//          for each requirement (Photo ID, Proof of address), so it's always
//          clear what each file is for"*
// Rules:   B14 rule 43 (built as components; the file opens through the kit's
//          own `openDocumentContent`) · rule 31 (no database id on screen) ·
//          rule 33 (a label ≤ 3 words, a fact ≤ 6, rationale zero) · rule 21
// Screens: CWP-047 step 3 (ABOUT YOU — one row per document asked for) ·
//          CWP-009 step 4 (WE WILL NEED THESE FROM YOU — attached or later)
// Tests:   src/portal/guest/CheckAndSend.dom.test.tsx (*the PO's start-service
//          defects of 2026-10-02*, and the CR-158 cases above it)
// ───────────────────────────────────────────────────────
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { documentFileType, formatDocumentSize, openDocumentContent } from "@/components/documents";

import {
  applicationDocumentContentPath,
  removeApplicationDocument,
  uploadApplicationDocument,
} from "../api/guestClient";
import type {
  ApplicationDocument,
  ApplicationDocumentLimits,
  ApplicationDraft,
} from "../api/guestClient";
import { StatusChip } from "../components/primitives";
import { Announced } from "../components/a11y";

/** What the picker offers. The SERVER reads the bytes and is the authority;
 *  this only narrows the browser's own file dialog. */
export const APPLICATION_DOCUMENT_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

/** The figures used only until the draft has answered with its own. */
const FALLBACK_LIMITS: ApplicationDocumentLimits = {
  types: ["application/pdf", "image/jpeg", "image/png"],
  max_bytes: 10 * 1024 * 1024,
  max_files: 5,
};

/**
 * The documents this application asks for, in the server's order.
 *
 * ⚠ **THE SERVER'S LIST, NEVER A COPY HERE** (`applications.DOCUMENT_
 * REQUIREMENTS`, served on every draft read). This screen used to type
 * `["photo_id", "proof_of_address"]` itself, so the checklist and the upload
 * were two lists that could not know about each other — which is how two
 * attached files sat under two rows reading *NOW OR LATER* (`DEF-CWP-9167`).
 */
export function requirementsOf(draft: ApplicationDraft | null): readonly string[] {
  return draft?.document_requirements ?? [];
}

/** The files meeting `requirement`, and the files meeting none (*Other*). */
export function filesFor(
  documents: readonly ApplicationDocument[],
  requirement: string,
): ApplicationDocument[] {
  return documents.filter((one) => one.requirement === requirement);
}

export function otherFiles(
  documents: readonly ApplicationDocument[],
  requirements: readonly string[],
): ApplicationDocument[] {
  return documents.filter(
    (one) => one.requirement === null || one.requirement === undefined || !requirements.includes(one.requirement),
  );
}

/**
 * Open the applicant's OWN file in a new tab (`DEF-CWP-9166`).
 *
 * ⚠ **A NAVIGATION THROUGH THE KIT'S OWN OPENER, NOT A `fetch`** — the clerk's
 * file opens exactly this way (`openDocumentContent`), so the response's
 * `Content-Disposition`, `nosniff` and script-forbidding policy reach the tab.
 * The address carries the draft's token, which is the only thing that may open
 * it; another draft's token or another utility answers *not found*.
 */
export function openApplicationDocument(
  token: string,
  documentId: string,
  open?: (url: string) => void,
): string {
  return openDocumentContent(applicationDocumentContentPath(token, documentId), "view", { open });
}

/**
 * **THE APPLICANT'S FILES — one row per document asked for.**
 *
 * ⚠ **EACH FILE GOES TO THE SERVER THE MOMENT IT IS CHOSEN, SAYING WHICH ROW IT
 * WAS CHOSEN ON**, and the rows are redrawn from the server's answer. A list
 * kept only in the browser would say *attached* over a file that never
 * arrived — the failure `reports` refuses a photo to avoid. Closing the tab
 * loses nothing: the files are on the draft, each with its requirement.
 *
 * ⚠ **A REFUSAL NAMES THE FILE** (`{{name}}: use PDF, JPG, PNG.`), because a
 * person who chose two files needs to know which one was turned away.
 *
 * ⚠ **A FILE ATTACHED BEFORE THE ROWS EXISTED KEEPS WORKING** — it has no
 * requirement, so it is listed under *Other documents* with View and Remove,
 * and it still travels with the application.
 */
export function ApplicationDocuments(props: {
  token: string;
  draft: ApplicationDraft;
  /** The host replaces its draft with the server's answer. */
  onDraft: (draft: ApplicationDraft) => void;
  client?: ApiClient;
  /** The test seam for opening a file. Defaults to a new browser tab. */
  open?: (url: string) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const documents = props.draft.documents ?? [];
  const requirements = requirementsOf(props.draft);
  const limits = props.draft.document_limits ?? FALLBACK_LIMITS;
  const full = documents.length >= limits.max_files;
  const maxMb = Math.round(limits.max_bytes / (1024 * 1024));
  const others = otherFiles(documents, requirements);

  async function take(file: File | null, requirement: string): Promise<void> {
    if (file === null) return;
    setError(undefined);
    setBusy(true);
    try {
      props.onDraft(await uploadApplicationDocument(props.token, file, props.client, requirement));
    } catch (failure) {
      setError(refusalText(t, failure));
    } finally {
      setBusy(false);
    }
  }

  async function remove(documentId: string): Promise<void> {
    setError(undefined);
    setBusy(true);
    try {
      props.onDraft(await removeApplicationDocument(props.token, documentId, props.client));
    } catch (failure) {
      setError(refusalText(t, failure));
    } finally {
      setBusy(false);
    }
  }

  const view = (documentId: string) => openApplicationDocument(props.token, documentId, props.open);

  return (
    <div className="flex flex-col gap-1" data-application-documents="">
      {requirements.map((requirement) => (
        <RequirementRow
          key={requirement}
          requirement={requirement}
          label={t(`portal.apply.document.${requirement}`)}
          files={filesFor(documents, requirement)}
          busy={busy}
          full={full}
          onAttach={(file) => void take(file, requirement)}
          onView={view}
          onRemove={(id) => void remove(id)}
        />
      ))}
      {others.length > 0 ? (
        <div className="flex flex-col gap-1 py-2" data-other-documents="">
          <span className="text-body font-semibold text-neutral-800">
            {t("portal.apply.otherDocuments")}
          </span>
          <AttachedFiles documents={others} busy={busy} onView={view} onRemove={(id) => void remove(id)} />
        </div>
      ) : null}
      <p className="mt-1 text-base text-neutral-600" data-attach-limits="">
        {busy
          ? t("portal.apply.uploading")
          : t("portal.apply.attachLimits", { max_mb: maxMb, max: limits.max_files })}
      </p>
      {error !== undefined ? (
        // Announced, not only shown — a refused file is news (question 7).
        <Announced tone="error" className="text-base font-semibold text-danger-700" data-attach-error="">
          {error}
        </Announced>
      ) : null}
    </div>
  );
}

/**
 * ONE document asked for: its name, the files attached as it, and *Attach*.
 *
 * ⚠ **THE FILE INPUT IS HIDDEN AND THE BUTTON IS THE CONTROL**, so the row is
 * reached by Tab like every other button, shows the product's own focus ring,
 * and is announced as *Attach Photo ID* rather than as a browser's *Choose
 * file, no file chosen*. The input is taken out of the tab order so nobody
 * meets the same control twice.
 */
function RequirementRow(props: {
  requirement: string;
  label: string;
  files: ApplicationDocument[];
  busy: boolean;
  full: boolean;
  onAttach: (file: File | null) => void;
  onView: (documentId: string) => void;
  onRemove: (documentId: string) => void;
}) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  return (
    <div
      className="flex flex-col gap-1 border-b border-neutral-200 py-2"
      data-requirement={props.requirement}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-body font-semibold text-neutral-800">{props.label}</span>
        <input
          ref={input}
          type="file"
          className="hidden"
          tabIndex={-1}
          aria-hidden="true"
          accept={APPLICATION_DOCUMENT_ACCEPT}
          data-attach-input={props.requirement}
          onChange={(event) => {
            const chosen = event.target.files;
            props.onAttach(chosen !== null && chosen.length > 0 ? chosen[0] : null);
            // The same file chosen twice must still fire `change`.
            event.target.value = "";
          }}
        />
        <Button
          variant="secondary"
          size="sm"
          data-action="attach-file"
          data-requirement={props.requirement}
          disabled={props.busy || props.full}
          aria-label={t("portal.apply.attachNamed", { name: props.label })}
          onClick={() => input.current?.click()}
        >
          {t("portal.apply.attach")}
        </Button>
      </div>
      <AttachedFiles
        documents={props.files}
        busy={props.busy}
        onView={props.onView}
        onRemove={props.onRemove}
      />
    </div>
  );
}

/**
 * The files on the application — name, then TYPE · size underneath, and
 * **View** beside **Remove** (`DEF-CWP-9166`). Without `onRemove` the list is
 * read-only; without `onView` there is nothing to open.
 */
export function AttachedFiles(props: {
  documents: readonly ApplicationDocument[];
  onView?: (documentId: string) => void;
  onRemove?: (documentId: string) => void;
  busy?: boolean;
}) {
  const { t, i18n } = useTranslation();
  if (props.documents.length === 0) return null;
  return (
    <ul className="flex flex-col" aria-label={t("portal.apply.attachedFiles")}>
      {props.documents.map((document) => (
        <li
          key={document.id}
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-1"
          data-attached-file={document.name}
        >
          <span className="min-w-0 break-words text-body text-neutral-800">
            {document.name}
            <span className="block text-sm text-neutral-600 tabular-nums">
              {[
                documentFileType(document.content_type),
                formatDocumentSize(document.size_bytes, i18n.language),
              ]
                .filter((part): part is string => part !== null)
                .join(" · ")}
            </span>
          </span>
          <span className="flex items-center gap-2">
            {props.onView !== undefined && (
              <Button
                variant="secondary"
                size="sm"
                data-action="view-file"
                aria-label={t("portal.apply.viewFileNamed", { name: document.name })}
                onClick={() => props.onView?.(document.id)}
              >
                {t("portal.apply.viewFile")}
              </Button>
            )}
            {props.onRemove !== undefined && (
              <Button
                variant="secondary"
                size="sm"
                data-action="remove-file"
                disabled={props.busy === true}
                aria-label={t("portal.apply.removeFileNamed", { name: document.name })}
                onClick={() => props.onRemove?.(document.id)}
              >
                {t("portal.apply.removeFile")}
              </Button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * **CHECK AND SEND's half — per document asked for, *Attached ✓ <file name>*
 * or *Bring later*** (`DEF-CWP-9167`, PO ruling 2026-10-02). The file name
 * opens the file (`DEF-CWP-9166`), so the applicant can check the right scan is
 * going before they press Send. Files attached as no requirement follow under
 * *Other documents*.
 *
 * ⚠ **IT READS THE DRAFT, NEVER A LIST OF ITS OWN**: a row says *Attached* only
 * because the server holds a file filed against that requirement.
 */
export function DocumentChecklist(props: {
  token: string;
  draft: ApplicationDraft;
  open?: (url: string) => void;
}) {
  const { t } = useTranslation();
  const documents = props.draft.documents ?? [];
  const requirements = requirementsOf(props.draft);
  const others = otherFiles(documents, requirements);
  const fileLink = (document: ApplicationDocument) => (
    <Button
      key={document.id}
      variant="ghost"
      size="sm"
      data-view-file={document.name}
      aria-label={t("portal.apply.viewFileNamed", { name: document.name })}
      onClick={() => openApplicationDocument(props.token, document.id, props.open)}
    >
      {document.name}
    </Button>
  );
  return (
    <div className="flex flex-col" data-document-checklist="">
      {requirements.map((requirement) => {
        const files = filesFor(documents, requirement);
        return (
          <div
            key={requirement}
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-neutral-200 py-2"
            data-document={requirement}
            data-document-state={files.length > 0 ? "attached" : "later"}
          >
            <span className="text-body text-neutral-800">
              {t(`portal.apply.document.${requirement}`)}
            </span>
            {files.length > 0 ? (
              <span className="flex flex-wrap items-center gap-2">
                <StatusChip tone="success">{t("portal.apply.attachedTick")}</StatusChip>
                {files.map(fileLink)}
              </span>
            ) : (
              <StatusChip tone="neutral">{t("portal.apply.bringLater")}</StatusChip>
            )}
          </div>
        );
      })}
      {others.length > 0 ? (
        <div
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-neutral-200 py-2"
          data-other-documents=""
        >
          <span className="text-body text-neutral-800">{t("portal.apply.otherDocuments")}</span>
          <span className="flex flex-wrap items-center gap-2">{others.map(fileLink)}</span>
        </div>
      ) : null}
    </div>
  );
}
