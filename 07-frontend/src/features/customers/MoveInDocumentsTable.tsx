// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.25 (lane MVI-WIZ-CUST, 2026-10-05) — the move-in
//           Customer step's *Documents* table array (images 33, 39, 40).
// Rules:    B14 rules 20 (one table type — the kit's `TableArray`), 15 (the
//           row action is an icon), 33 (the fact on the heading ≤ 6 words;
//           *"Required ones come from Settings › Configure"* is RATIONALE and
//           is zero words on screen), 43, 44 · BR-CUS-095 (the checklist is
//           the utility's, ships unticked; a required row stays) ·
//           BR-SHL-031 (PDF, PNG, JPG or CSV up to 10 MB — the server is the
//           guard) · BR-CUS-073 / BR-CUS-080 (a request's documents travel by
//           reference; a staged one files at Complete)
// Server:   `GET /move-ins/documents/required` · `POST /move-ins/documents`
//           (stage) · `GET /move-ins/documents/{card}/content` · the commit's
//           `documents: [{card_id, doc_type}]` (CR §9.IDN-2, P2.25)
// Tests:    moveInWizard/StepCustomer.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ROWS, IN THE ORDER IMAGE 33 DRAWS THEM:
//   1. one row per REQUIRED type, locked (*Required rows stay*) — filled by a
//      request document of that type if the move came from one, else by a
//      staged upload, else an *Upload* button;
//   2. the request's other documents, locked — they travel by reference;
//   3. rows the clerk added with *+ Add document*: a type (a listed type drops
//      out of the next row's list — P2.25), an upload, a ✕.
//
// ⚠ **THE DRAWN `NOTE` COLUMN IS NOT BUILT.** An account document has no note
// column (`account_documents` carries none) and the commit has nowhere to put
// one, so a box that typed into nothing would be a live control that saves
// nothing (hard-won law 2's mirror). Recorded in the decision log (P2.25,
// screen) as a difference from images 33, 39 and 40.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { openDocumentContent } from "@/components/documents";
import { UploadButton } from "@/components/FileField";
import { StatusPill } from "@/components/StatusPill";
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  getMoveInRequiredDocuments,
  stageMoveInDocument,
  stagedMoveInDocumentPath,
} from "./customerEndpoints";
import { DESIGNED_DOC_TYPES, DOC_TYPE_OTHER, getServiceRequestDocuments } from "./serviceRequestEndpoints";
import type { ServiceRequestDocument } from "./serviceRequestEndpoints";

/** A row the clerk holds (parked with the draft): a type and, once uploaded,
 *  its staged card. `card_id` is a handle, never shown (B14 rule 31). */
export interface MoveInDocDraft {
  key: string;
  doc_type: string;
  card_id: string;
  name: string;
}

const ATTACHABLE: readonly string[] = [...DESIGNED_DOC_TYPES, DOC_TYPE_OTHER];
const ACCEPT = ".pdf,.png,.jpg,.jpeg,.csv,application/pdf,image/png,image/jpeg,text/csv";

let nextKey = 0;
export function newDocDraft(docType = ""): MoveInDocDraft {
  nextKey += 1;
  return { key: `doc-${Date.now().toString(36)}-${nextKey}`, doc_type: docType, card_id: "", name: "" };
}

/** The commit's `documents` — staged cards only; a row with no file sends
 *  nothing (an empty card is not a document). */
export function documentsPayload(rows: readonly MoveInDocDraft[]): { card_id: string; doc_type: string }[] {
  return rows
    .filter((row) => row.card_id !== "" && row.doc_type !== "")
    .map((row) => ({ card_id: row.card_id, doc_type: row.doc_type }));
}

export function hydrateDocDrafts(raw: unknown): MoveInDocDraft[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((row): row is Record<string, unknown> => typeof row === "object" && row !== null)
    .map((row) => ({
      ...newDocDraft(),
      doc_type: typeof row.doc_type === "string" && ATTACHABLE.includes(row.doc_type) ? row.doc_type : "",
      card_id: typeof row.card_id === "string" ? row.card_id : "",
      name: typeof row.name === "string" ? row.name : "",
    }));
}

interface Row {
  key: string;
  doc_type: string;
  required: boolean;
  /** Locked — a required row or a request's document; its ✕ is refused. */
  locked: boolean;
  request: ServiceRequestDocument | null;
  /** Index into the clerk's drafts, or -1 for a row with none yet. */
  draft: number;
  card_id: string;
  name: string;
}

/**
 * Lane CF-1 (2026-10-18), task 7 — the SHARED documents table: Move-in, the
 * staff service request and New connect draw this one table (customer-forms
 * drawing set, images 01, 03, 06, 15). A host may hand in `stage` — where an
 * upload goes; absent, it is staged for the move-in's Complete. The document
 * types offered are the same nine everywhere (`ATTACHABLE`, the
 * eight designed types and *Anything else*) — PO 2026-10-18: Move-in's *Add
 * document* offers the types the service request offers.
 */
export function MoveInDocumentsTable(props: {
  rows: readonly MoveInDocDraft[];
  onChange: (rows: MoveInDocDraft[]) => void;
  serviceRequestId: string;
  t: Translator;
  client?: ApiClient;
  stage?: (args: { file: File; docType: string }) => Promise<{ card_id: string; name: string }>;
  /** Lane CF-1 — a host's OWN checklist (the service request's, for its
   *  request type — BR-CUS-095). Absent, the move-in checklist is read. */
  requiredTypes?: readonly string[];
  /** Lane CF-1 — how a file `stage` put somewhere else is opened. */
  fileHref?: (cardId: string) => string;
  /** Lane CF-1 — a host whose files are not on any server yet (New connect
   *  holds them until Create, BR-MET-112) opens them itself. Wins over
   *  `fileHref`. */
  openFile?: (cardId: string) => void;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const required = useQuery({
    queryKey: ["move-in-documents-required"],
    queryFn: () => getMoveInRequiredDocuments(client),
    enabled: props.requiredTypes === undefined,
  });
  const requestDocs = useQuery({
    queryKey: ["service-request-documents", props.serviceRequestId],
    queryFn: () => getServiceRequestDocuments(props.serviceRequestId, client),
    enabled: props.serviceRequestId !== "",
  });
  const [uploading, setUploading] = useState<string | null>(null);
  const [failed, setFailed] = useState<Record<string, string>>({});
  const stage = useMutation({
    mutationFn: (args: { file: File; docType: string }) =>
      props.stage !== undefined ? props.stage(args) : stageMoveInDocument(args, client),
  });

  const drafts = props.rows;
  // A file this table put on the request itself (a request host's `stage`)
  // is the clerk's row, not a second copy of it.
  const ownCards = new Set(drafts.map((row) => row.card_id).filter((id) => id !== ""));
  const fromRequest = (requestDocs.data?.documents ?? []).filter(
    (doc) => doc.file_present && !ownCards.has(doc.id),
  );
  const requiredTypes = props.requiredTypes ?? required.data ?? [];

  // ── assemble the rows the table draws ────────────────────────────────────
  const rows: Row[] = [];
  const usedDraft = new Set<number>();
  for (const type of requiredTypes) {
    const request = fromRequest.find((doc) => doc.doc_type === type) ?? null;
    const draftIndex = drafts.findIndex((row, index) => row.doc_type === type && !usedDraft.has(index));
    if (draftIndex >= 0) usedDraft.add(draftIndex);
    const draft = draftIndex >= 0 ? drafts[draftIndex] : null;
    rows.push({
      key: `required-${type}`,
      doc_type: type,
      required: true,
      locked: true,
      request: draft !== null && draft.card_id !== "" ? null : request,
      draft: draftIndex,
      card_id: draft?.card_id ?? "",
      name: draft?.name ?? "",
    });
  }
  for (const doc of fromRequest) {
    if (rows.some((row) => row.request?.id === doc.id)) continue;
    if (requiredTypes.includes(doc.doc_type)) continue;
    rows.push({
      key: `request-${doc.id}`,
      doc_type: doc.doc_type,
      required: false,
      locked: true,
      request: doc,
      draft: -1,
      card_id: "",
      name: doc.name ?? "",
    });
  }
  drafts.forEach((draft, index) => {
    if (usedDraft.has(index)) return;
    rows.push({
      key: draft.key,
      doc_type: draft.doc_type,
      required: false,
      locked: false,
      request: null,
      draft: index,
      card_id: draft.card_id,
      name: draft.name,
    });
  });

  const missing = rows.filter((row) => row.required && row.card_id === "" && row.request === null).length;
  const typeLabel = (code: string) => t(`customers.serviceRequest.docType.${code}`);

  const writeDraft = (row: Row, patch: Partial<MoveInDocDraft>) => {
    if (row.draft >= 0) {
      props.onChange(drafts.map((draft, index) => (index === row.draft ? { ...draft, ...patch } : draft)));
    } else {
      props.onChange([...drafts, { ...newDocDraft(row.doc_type), ...patch }]);
    }
  };

  const upload = (row: Row, file: File) => {
    if (row.doc_type === "") return;
    setUploading(row.key);
    setFailed((current) => {
      const next = { ...current };
      delete next[row.key];
      return next;
    });
    stage.mutate(
      { file, docType: row.doc_type },
      {
        onSuccess: (staged) => writeDraft(row, { card_id: staged.card_id, name: staged.name }),
        onError: () =>
          setFailed((current) => ({ ...current, [row.key]: "customers.moveIn.customer.docs.uploadFailed" })),
        onSettled: () => setUploading(null),
      },
    );
  };

  const columns: TableArrayColumn<Row>[] = [
    {
      key: "document",
      label: t("customers.moveIn.customer.docs.col.document"),
      cell: (row) => {
        if (row.locked) {
          return (
            <CellStatic name={`doc-type-${row.doc_type}`}>
              <span className="font-semibold">{typeLabel(row.doc_type)}</span>
            </CellStatic>
          );
        }
        const takenElsewhere = new Set(
          rows.filter((other) => other.key !== row.key).map((other) => other.doc_type),
        );
        return (
          <CellSelect
            name="doc-type"
            label={t("customers.moveIn.customer.docs.col.document")}
            placeholder={t("customers.moveIn.customer.choose")}
            fit
            value={row.doc_type}
            blockedReason={row.card_id !== "" ? t("customers.moveIn.customer.docs.typeFixed") : undefined}
            options={ATTACHABLE.filter(
              (code) => code === row.doc_type || code === DOC_TYPE_OTHER || !takenElsewhere.has(code),
            ).map((code) => ({ value: code, label: typeLabel(code) }))}
            onChange={(value) => writeDraft(row, { doc_type: value })}
          />
        );
      },
    },
    {
      key: "needed",
      label: t("customers.moveIn.customer.docs.col.needed"),
      cell: (row) =>
        row.required ? (
          <StatusPill tone="warning">{t("customers.moveIn.customer.docs.required")}</StatusPill>
        ) : (
          <span aria-hidden="true">—</span>
        ),
    },
    {
      key: "file",
      label: t("customers.moveIn.customer.docs.col.file"),
      cell: (row) => {
        if (row.request !== null) {
          const doc = row.request;
          return (
            <Button
              variant="link"
              data-doc-file="request"
              onClick={() =>
                openDocumentContent(
                  `/service-requests/${props.serviceRequestId}/documents/${doc.id}/content`,
                  "view",
                )
              }
            >
              {doc.name ?? typeLabel(doc.doc_type)}
            </Button>
          );
        }
        if (row.card_id !== "") {
          return (
            <span className="inline-flex items-center gap-2">
              <Button
                variant="link"
                data-doc-file="staged"
                onClick={() => {
                  const openFile = props.openFile;
                  if (openFile !== undefined) {
                    openFile(row.card_id);
                    return;
                  }
                  openDocumentContent((props.fileHref ?? stagedMoveInDocumentPath)(row.card_id), "view");
                }}
              >
                {row.name}
              </Button>
              <Button
                size="row"
                variant="ghost-danger"
                aria-label={t("customers.moveIn.customer.docs.removeFile", { name: row.name })}
                title={t("customers.moveIn.customer.docs.removeFile", { name: row.name })}
                data-doc-file-remove=""
                onClick={() => writeDraft(row, { card_id: "", name: "" })}
              >
                ✕
              </Button>
            </span>
          );
        }
        return (
          <UploadButton
            id={`doc-upload-${row.key}`}
            label={
              uploading === row.key ? t("states.loading") : t("customers.moveIn.customer.upload")
            }
            name={t("customers.moveIn.customer.docs.uploadFor", {
              type: row.doc_type === "" ? t("customers.moveIn.customer.docs.col.document") : typeLabel(row.doc_type),
            })}
            accept={ACCEPT}
            disabled={row.doc_type === "" || uploading !== null}
            onFile={(file) => upload(row, file)}
          />
        );
      },
    },
  ];

  const factParts = [
    missing > 0 ? t("customers.moveIn.customer.docs.missing", { count: missing }) : null,
    t("customers.moveIn.customer.docs.files"),
  ].filter((part): part is string => part !== null);

  return (
    <TableArray<Row>
      title={t("customers.moveIn.customer.docs.title")}
      fact={factParts.join(" · ")}
      collection="move-in-documents"
      columns={columns}
      rows={rows}
      rowKey={(row) => row.key}
      emptyText={t("customers.moveIn.customer.docs.empty")}
      removeLabel={t("customers.moveIn.customer.docs.remove")}
      rowRemoveBlocked={(row) => (row.locked ? t("customers.moveIn.customer.docs.stays") : undefined)}
      cellError={(row, _index, column) =>
        column === "file" && failed[row.key] !== undefined ? t(failed[row.key]) : undefined
      }
      onChange={(next) => {
        // A ✕ removes a clerk's row; locked rows refuse it, so `next` differs
        // from `rows` only by dropped clerk rows.
        const kept = new Set(next.map((row) => row.key));
        props.onChange(drafts.filter((draft, index) => {
          const shown = rows.find((row) => row.draft === index);
          return shown === undefined || kept.has(shown.key);
        }));
      }}
      actions={[
        {
          key: "add-document",
          label: t("customers.moveIn.customer.docs.add"),
          onClick: () => props.onChange([...drafts, newDocDraft()]),
        },
      ]}
      footerTrailing={
        <span className="text-sm text-neutral-700">{t("customers.moveIn.customer.docs.stays")}</span>
      }
    />
  );
}
