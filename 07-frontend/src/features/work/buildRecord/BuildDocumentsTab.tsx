// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 10 — the Documents tab. MOVED here from
//           `features/customers/BuildDetailTabs.tsx:947` by `DEF-CUS-7618`,
//           unchanged in what it renders.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/05-documents.png`
// Rules:    B14 rule 43 (PO: *"we need to make it compoentn so thatw e cna use
//           it in other palces also"*) · rule 31 · `BR-SHL-025` (the refusal
//           is in words beside the thing it is about)
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THIS TAB ALREADY COMPOSED ITS SHARED PANEL — IT WAS IN THE WRONG HOUSE
// ══════════════════════════════════════════════════════════════════════════
// The body is `components/documents`' `DocumentCapture`, the same block the
// account and the service request mount; there is no SECOND documents table
// here and there never was. What `G93` refused was the WRAPPER: a component
// named `BuildDocumentsTab` declared in `features/customers/`, which is a
// second home for a build panel whatever it contains. It lives in the kit now.
//
// ⚠ **A BUILD'S PAPERS ARE FILED AGAINST THE OWNER'S ACCOUNT, BY RULING.**
// Decision log 2026-09-21: *"nothing is owned by anybody else, so the owner's
// documents may be captured at step 1 and filed against what the commit
// creates"*, through `POST /accounts/{id}/documents`. So *Uploaded by* and
// *When* are REAL here and null on the wizard, which is exactly what the
// drawing's own note says.
//
// ⚠ **TWO COLUMNS THE PNG DRAWS ARE NOT IN THAT COMPONENT** — a DOCUMENT
// NUMBER and a WHEN of its own, which it folds into *Uploaded by* as
// `S. Ortiz · 05/04/2026`. Adding them is a change to `components/documents/`,
// which is another lane's this session; REPORTED rather than forked here,
// because a second documents table is the thing rule 43 was ruled on.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { listAccountDocuments, uploadAccountDocument } from "@/api/endpoints";
import type { AccountDocumentType } from "@/api/endpoints";
import { UPLOADABLE_ACCOUNT_DOCUMENT_TYPES } from "@/api/endpoints";
import { DocumentCapture, emptyDocumentCapture } from "@/components/documents";
import type { DocumentCaptureValue, DocumentRow } from "@/components/documents";
import { DOCUMENT_ACCEPT, openDocumentContent } from "@/components/documents";
import { accountDocumentContentPath } from "@/features/customers/AccountDocumentsTab";
import i18n from "@/i18n";

import { Section } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

const DOCUMENTS_KEY = (accountId: string) => ["account-documents", accountId, "build"] as const;

export function BuildDocumentsTab(props: BuildTabProps) {
  const { t } = props;
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DocumentCaptureValue>(() =>
    emptyDocumentCapture(UPLOADABLE_ACCOUNT_DOCUMENT_TYPES[0]),
  );
  const [nonce, setNonce] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const accountId = props.accountId;

  const list = useQuery({
    queryKey: DOCUMENTS_KEY(accountId ?? ""),
    queryFn: () => listAccountDocuments(accountId as string, {}, client),
    enabled: accountId !== null,
    retry: false,
  });

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadAccountDocument(
        accountId as string,
        { file, docType: form.docType as AccountDocumentType },
        client,
      ),
    onSuccess: () => {
      setForm(emptyDocumentCapture(form.docType));
      setNonce((n) => n + 1);
      void queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY(accountId ?? "") });
    },
  });

  if (accountId === null) {
    // BR-SHL-025 — the refusal is in words beside the thing it is about, and
    // it is this page's honest state on a build with no owner account yet.
    return (
      <Section
        id="documents"
        title={t("customers.build.documents.title", { defaultValue: "Documents" })}
      >
        <p className="text-sm text-neutral-700" data-build-empty="documents">
          {t("customers.build.documents.noAccount", {
            defaultValue: "Papers need an account first.",
          })}
        </p>
      </Section>
    );
  }

  const rows: DocumentRow[] = (list.data?.results ?? []).map((doc) => ({
    id: doc.id,
    doc_type: doc.doc_type,
    what_it_proves: null,
    // The account's document store asks for no number, so nothing is masked
    // over nothing (`draftDocumentRows` takes the same posture one screen on).
    document_number: null,
    name: doc.name,
    uploaded_at: doc.uploaded_at,
    uploaded_by_name: doc.uploaded_by_name,
    required: false,
    size_bytes: doc.size_bytes,
    original_size_bytes: null,
    file_present: true,
    // ⚠ **BLANK UNTIL A REVIEWER DECIDES — verified or rejected, no third
    // word** (PO 2026-09-22). The shared STATE cell prints NOTHING for this
    // value, which is the drawing's own rule.
    verification_state: "not_checked",
    reject_reason: null,
  }));

  return (
    <Section
      id="documents"
      title={t("customers.build.documents.title", { defaultValue: "Documents" })}
    >
      <DocumentCapture
        rows={rows}
        value={form}
        onChange={setForm}
        onSubmit={(withFile) => {
          if (!withFile || form.file === null) {
            setError(
              t("customers.build.documents.needsFile", { defaultValue: "Choose a file first." }),
            );
            return;
          }
          setError(null);
          upload.mutate(form.file);
        }}
        docTypes={UPLOADABLE_ACCOUNT_DOCUMENT_TYPES.map((code) => ({
          value: code,
          label: t(`customers.account.documents.type.${code}`),
        }))}
        // The tenant's checklist is a SERVICE REQUEST's checklist (`BR-CUS-095`)
        // and a build has none, so the answer is honestly unknown rather than
        // a tick nobody made.
        requiredOf={() => null}
        // ── `CR-163-BRC10` items 24 and 25 (`DEF-CUS-9186`, `DEF-CUS-9187`) ──
        // A filed document could not be OPENED here, and its type read as the
        // raw code. Both now come from the account's own Documents tab: its
        // content route (`DEF-CUS-9147`, 2.454.2 — reused, never a second
        // route) and its type vocabulary. Required and State are dropped: an
        // account's papers carry no checklist and no reviewer's verdict, so
        // both were blank on every row.
        onOpen={(row) => openDocumentContent(accountDocumentContentPath(accountId, row.id), "view")}
        openAsIcon
        docTypeLabel={(code) =>
          t(`customers.account.documents.type.${code}`, { defaultValue: code })
        }
        withoutChecklist
        t={t}
        locale={i18n.language}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        busy={upload.isPending}
        error={error}
        resetNonce={nonce}
        accept={DOCUMENT_ACCEPT}
        idPrefix="build-doc"
      />
    </Section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-150-BRC09 task 10 · `05-documents.png` (rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, with no change to what it renders
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
