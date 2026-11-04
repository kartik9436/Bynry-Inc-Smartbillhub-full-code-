// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.07 — a move-in REQUEST's Documents tab (image 21).
//           `DEF-CUS-9764`: image 21's own four columns (the kit's
//           `neededLayout`), NEEDED from the checklist as well as the tick.
//           The kit's `DocumentTable` (rule 43's named document surface), fed
//           the request's own documents read; nothing is re-drawn here.
// Data:     `GET /service-requests/{id}/documents` · each file opens through
//           its content route.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DocumentTable, openDocumentContent } from "@/components/documents";
import { LoadingSkeleton } from "@/components/StateFrame";

import { DOC_TYPE_OTHER, getServiceRequestDocuments } from "../serviceRequestEndpoints";
import { DetailGroup, EmptyLine } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

export function RequestDocumentsTab(props: { requestId: string; regional: Regional; client?: ApiClient }) {
  const { t, i18n } = useTranslation();
  const client = props.client ?? api;
  const query = useQuery({
    queryKey: ["move-detail-request-documents", props.requestId],
    queryFn: () => getServiceRequestDocuments(props.requestId, client),
  });
  const contentPath = (id: string) =>
    `/service-requests/${encodeURIComponent(props.requestId)}/documents/${encodeURIComponent(id)}/content`;
  return (
    <DetailGroup title={t("customers.moveDetail.section.documents")} name="documents">
      {query.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : query.isError || !query.data ? (
        <EmptyLine>{t("customers.moveDetail.absent.notReadable")}</EmptyLine>
      ) : query.data.documents.length === 0 ? (
        <EmptyLine>{t("customers.moveDetail.documents.none")}</EmptyLine>
      ) : (
        <DocumentTable
          rows={query.data.documents}
          t={t}
          locale={i18n.language}
          timeZone={props.regional.timeZone}
          dateFormat={props.regional.dateFormat}
          // `DEF-CUS-9764` — NEEDED is the uploader's own tick OR the tenant's
          // move-in checklist (`BR-CUS-095`), the capture page's two halves
          // (`docRequired`). Reading the tick alone printed *No* beside a
          // document the checklist requires.
          requiredOf={(row) => {
            if (row.doc_type === DOC_TYPE_OTHER) return null;
            return row.required === true || (query.data.checklist_required ?? []).includes(row.doc_type);
          }}
          neededLayout
          onOpen={(row) => openDocumentContent(contentPath(row.id), "view")}
        />
      )}
    </DetailGroup>
  );
}
