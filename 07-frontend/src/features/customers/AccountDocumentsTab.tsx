// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave I — `ACC-S8`, "An account can hold a
//           document". Step 1 lane 2 finding F10: *"An account can hold no
//           document … the tab draws five column heads over the stated
//           absence."* This is the tab that fills them.
// Story:    US-CUS-011 · screen S21, tab `ACC-T10`.
// Rules:    BR-CUS-036 (CONFIRMED — the five-value type lookup) · BR-SHL-031
//           (PDF/PNG/JPG/CSV, 10 MB, staff-mediated in v1) · BR-SHL-010 (an
//           undeclared capability is not rendered) · BR-SHL-025 (a forbidden
//           control is disabled WITH its reason) · BR-SHL-034 (one date
//           formatter) · B14 rule 16 (every list table carries the pagination
//           footer) · rule 19 (the search prompt names what it matches) ·
//           rule 20 (one table type) · rule 21 (Tailwind utilities; this file
//           adds NO class to a stylesheet and is registered in
//           `styles/route-b-migrated.txt`) · rule 31 (no database id on screen)
//           · rule 33 (on-screen text is capped by what it is for) · rule 36
//           (compose the kit) · rule 38 (a form is built by the UI rules) ·
//           rule 39 (label → input → helper, 20px between fields).
// ───────────────────────────────────────────────────────
// ⚠ **THE DRAWING, QUOTED RATHER THAN LINKED** — `ACC-T10`, read off the
// rendered page by the step 1 lane and recorded in
// `04-docs/05-modules/03-customers/conformance/CR-094-lane2-account-detail-step1.md`
// §1.5:
//
//   toolbar  `All` `Correspondence` `Evidence` `Filter ▾` `Search` ·
//            `Upload document` *(disabled)* `Columns ▾` `Export`
//   columns  `DOCUMENT` · `TYPE` · `DATE` · `UPLOADED BY` · `SIZE`
//
// **THE FIVE COLUMNS ARE BUILT EXACTLY AS DRAWN, IN THAT ORDER.** Three of the
// toolbar's items differ, and each difference is stated here rather than made
// quietly:
//
//  1 · **`Upload document` IS NO LONGER DISABLED.** That was the stated absence
//      this wave exists to remove, and the string that said so goes with it —
//      hard-won law 1: the string changes with the fact, in the same commit.
//
//  2 · ⚠ **THE CHIPS ARE `BR-CUS-036`'s FIVE TYPES, NOT THE DRAWING'S TWO.**
//      The drawing offers `All` · `Correspondence` · `Evidence`, and
//      **`Evidence` is not one of the five CONFIRMED values** (System ·
//      Contract · KYC · Payment · Correspondence, PO closure batch 2026-08-08).
//      A wireframe cannot amend signed law, so the filter follows the rule. The
//      divergence is FILED — the conformance file and the decision log of
//      2026-09-12 both carry it — rather than resolved silently in either
//      direction. (B14 rule 37 says the same about a drawn NUMBER; this is a
//      drawn VALUE and the reasoning transfers.)
//
//  3 · ⛔ **NO `Export`, AND IT IS A STATED ABSENCE RATHER THAN A FORGOTTEN
//      PROP.** `POST /exports` resolves only the resources a module REGISTERS,
//      and nothing registers `account_documents`. `BR-SHL-010` keeps an
//      undeclared capability unrendered — and not drawn DISABLED either, which
//      is `BR-SHL-025`'s posture for a control this ROLE cannot use, not one
//      the PRODUCT does not have. A download button here would be a control
//      wired to a 404 (hard-won law 2). The same sentence `DisconnectsTab`
//      already makes about its own toolbar.
//
// `Filter ▾` and `Columns ▾` come from the kit and need no argument.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  ACCOUNT_DOCUMENT_ACCEPT,
  ACCOUNT_DOCUMENT_TYPES,
  AUDIT_LOCKED_ACCOUNT_DOCUMENT_TYPES,
  UPLOADABLE_ACCOUNT_DOCUMENT_TYPES,
  listAccountDocuments,
  removeAccountDocument,
  uploadAccountDocument,
} from "@/api/endpoints";
import type { AccountDocument, AccountDocumentType } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FileField } from "@/components/FileField";
import { FilterBar } from "@/components/FilterBar";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { openDocumentContent } from "@/components/documents";
import { EyeIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { toEnvelope } from "@/features/metering/PremisesListPage";
import { Panel } from "@/components/Panel";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import { CELL_FULL, useAccessCell, useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

import { ACCOUNTS_PERMISSION, Dash } from "./customersShared";
import { AccountAgreementsPanel } from "./AccountAgreementsPanel";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

/** The screen id `TableConfig` keys its column preference on — S21's tab, so a
 *  clerk's chosen columns survive leaving the account and coming back. */
const DOCUMENTS_TABLE_SCREEN = "S21.documents";

/**
 * The five CONFIRMED types as `{value, label}`, from ONE list.
 *
 * ⚠ **DERIVED, NEVER HAND-TYPED.** `CLAUDE.md`'s hard-won law 2 records the
 * service list being typed out by hand in two places, so an eleventh service
 * never appears on screen and fails silently. The chips, the picker and the
 * `TYPE` cell all read `ACCOUNT_DOCUMENT_TYPES`, so a sixth type appears in
 * three places or in none.
 */
function typeOptions(
  t: (key: string) => string,
  values: readonly AccountDocumentType[],
): { value: string; label: string }[] {
  return values.map((value) => ({
    value,
    label: t(`customers.account.documents.type.${value}`),
  }));
}

/**
 * WHY this document cannot be taken back — or `null` when it can.
 *
 * ⚠ **`BR-SHL-025`: A CONTROL THAT CANNOT ACT CARRIES ITS REASON, NEVER
 * HIDDEN.** A clerk who finds no Remove on a contract learns nothing; a clerk
 * who finds a disabled one saying *Contract files cannot be removed* learns the
 * rule. `RowAction` takes the two as ONE prop for exactly this reason — there
 * is no boolean to pass without a sentence.
 *
 * ⚠ **THE LIST IS DERIVED AND NOT TYPED OUT — hard-won law 2.**
 * `AUDIT_LOCKED_ACCOUNT_DOCUMENT_TYPES` is the one place the answer lives, and
 * the SERVER refuses the same set with 409 whatever this returns. This decides
 * what a clerk SEES; it is the door, never the lock.
 */
export function lockedReason(
  t: (key: string) => string,
  docType: AccountDocumentType,
): string | null {
  return (AUDIT_LOCKED_ACCOUNT_DOCUMENT_TYPES as readonly string[]).includes(docType)
    ? t(`customers.account.documents.locked.${docType}`)
    : null;
}

/** How big the file is, in the unit a person would say it in.
 *
 * ⚠ **FORMATTED ON THE SCREEN, NOT ON THE SERVER**, and that is the same
 * decision `BR-SHL-034` records for dates: a server returning `"1.2 MB"` has
 * chosen a locale's decimal separator in the wrong place. The server sends a
 * byte count; this renders it. */
export function formatBytes(bytes: number, locale: string): string {
  if (bytes < 1024) {
    return `${bytes.toLocaleString(locale)} B`;
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${Math.round(kb).toLocaleString(locale)} KB`;
  }
  return `${(kb / 1024).toLocaleString(locale, { maximumFractionDigits: 1 })} MB`;
}

export function documentsTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    date: (row: AccountDocument) => JSX.Element;
    size: (row: AccountDocument) => JSX.Element;
    actions: (row: AccountDocument) => JSX.Element;
  },
): TableConfig<AccountDocument> {
  return {
    screenId: DOCUMENTS_TABLE_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["name"],
    // B14 rule 19 — the prompt names WHAT the box matches. The server searches
    // the stored document's own name and nothing else, so the prompt says so.
    searchPlaceholder: "customers.account.documents.search",
    filters: [
      {
        name: "type",
        label: t("customers.account.documents.field.type"),
        options: typeOptions(t, ACCOUNT_DOCUMENT_TYPES),
      },
    ],
    // `BR-CUS-1046` (PO 2026-09-10): *"The new newly created entries should
    // always show on the top."* `uploaded` is the SERVER's sort name.
    defaultSort: { sort: "uploaded", dir: "desc" },
    columns: [
      {
        key: "name",
        // ⚠ B14 rule 31 — the visible value is the document's NAME, never its
        // id. The id is the React key and the address of the download link.
        identity: true,
        sortable: true,
        label: t("customers.account.documents.col.document"),
        cell: (row) => <span>{row.name}</span>,
      },
      {
        key: "type",
        sortable: true,
        label: t("customers.account.documents.col.type"),
        cell: (row) => <span>{t(`customers.account.documents.type.${row.doc_type}`)}</span>,
      },
      {
        key: "uploaded",
        sortable: true,
        label: t("customers.account.documents.col.date"),
        cell: cells.date,
      },
      {
        key: "uploaded_by",
        label: t("customers.account.documents.col.uploadedBy"),
        // ⚠ **NEVER AN EMPTY CELL WHERE A PERSON IS EXPECTED.** A document the
        // product filed itself has no human behind it (`BR-CUS-036`: system
        // documents *"attach automatically"*), and a blank reads as *"nobody
        // knows"* — rule 31's reasoning applied to an absence rather than to a
        // uuid. It says *The system*, which is what happened.
        cell: (row) => (
          <span>
            {row.uploaded_by_name ?? t("customers.account.documents.filedBySystem")}
          </span>
        ),
      },
      {
        key: "size",
        numeric: true,
        label: t("customers.account.documents.col.size"),
        cell: cells.size,
      },
      // ⚠ **A SIXTH COLUMN OVER `ACC-T10`'s FIVE, AND THE DRAWING IS NOT BEING
      // OVERRULED — IT IS OLDER THAN THE RULING.** The wireframe draws
      // `DOCUMENT · TYPE · DATE · UPLOADED BY · SIZE` and no row action,
      // because when it was drawn nothing in the product could remove a
      // document. `BR-CUS-1052` (PO 2026-09-13) is what changed, and B14 rule
      // 15 then decides the SHAPE: row actions are icons with tooltips, one
      // trailing column, never a text link in a cell.
      //
      // ⚠ **THE COLUMN IS ALWAYS DRAWN AND THE CONTROL IN IT MAY BE DISABLED —
      // `BR-SHL-025`, AND THE CHOICE IS DELIBERATE.** A first draft omitted the
      // whole column for a read-only role, which is how an optional prop nobody
      // passes becomes dead UI (hard-won law 2) and how a clerk learns nothing
      // from an absence. Two reasons can reach the bin and each is a sentence a
      // person can act on: *this role cannot write here* (the page's own
      // `useAccessCell` gate, exactly as `AccountDetailPage` states it) and
      // *this document is audit-locked* (`BR-CUS-036`).
      {
        key: "actions",
        label: t("customers.account.documents.col.actions"),
        cell: cells.actions,
      },
    ],
  };
}

/**
 * The address a filed document OPENS at — `DEF-CUS-9147`.
 *
 * ⚠ **THE CONTENT ROUTE, NOT THE BEARER LINK.** `GET …/documents/{docId}` mints
 * a link straight to the object store, and the developer's filesystem store
 * mints `file://`, which a browser refuses. The content route serves the bytes
 * through the API with `Content-Disposition`, `nosniff` and a no-script policy,
 * on every backend — the choice `CR-158-BRC10` made for a service request's
 * documents, reused rather than made a second time (B14 rule 43).
 */
export function accountDocumentContentPath(accountId: string, documentId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/documents/${encodeURIComponent(documentId)}/content`;
}

export function documentsQueryKey(accountId: string, state: TableRequestState): readonly unknown[] {
  return ["account-documents", accountId, state.q, state.sort, state.dir, state.page, state.per, state.filters];
}

/**
 * The upload form — three fields, one outcome, back to the list it opened from.
 *
 * ⚠ **A MODAL, AND THE PRECEDENT IS THE ESTIMATE-READ DIALOG.** B14 rule 30 was
 * DECLINED, so there is no rule to cite; what B14 says instead is to follow the
 * estimate precedent, and this matches it on every clause — a handful of
 * fields, one outcome, returns to the list, nobody links to it, and losing it
 * on refresh costs nothing.
 *
 * ⚠ **RULE 38 — the FORM is built by the UI rules.** Label → input → helper,
 * 20px between fields, the kit's own `FormModal` footer. The drawing says what
 * the form CONTAINS and the kit says how it is constructed.
 */
export function UploadDocumentForm(props: {
  accountId: string;
  client: ApiClient;
  onClose: () => void;
  onFiled: () => void;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<string>("");
  const [name, setName] = useState("");

  const schema = z.object({
    // The three server refusals this form can produce before it posts. Each
    // message is a KEY, so the other ten languages reach it.
    "document-file": z.string().min(1, { message: t("customers.document.file_required") }),
    "document-type": z.string().min(1, { message: t("customers.document.type_unknown") }),
    "document-name": z.string().min(1, { message: t("customers.document.name_required") }),
  });

  return (
    <FormModal
      title={t("customers.account.documents.upload")}
      schema={schema}
      values={{
        "document-file": file === null ? "" : file.name,
        "document-type": docType,
        "document-name": name,
      }}
      submitLabel={t("customers.account.documents.submit")}
      onClose={props.onClose}
      onSubmit={async (): Promise<FormSubmitOutcome> => {
        try {
          if (file === null) {
            // The schema already refuses this, so reaching here means the
            // browser cleared the picker between validation and submit.
            return {
              ok: false,
              error: {
                code: "VAL-001",
                message_key: "customers.document.file_required",
                params: {},
              },
            };
          }
          await uploadAccountDocument(
            props.accountId,
            { file, docType: docType as AccountDocumentType, name },
            props.client,
          );
          props.onFiled();
          return { ok: true };
        } catch (error) {
          // ⚠ **THE ENVELOPE IS RETURNED AND NOT ALSO RENDERED HERE**
          // (`DEF-MET-4722`): `FormModal` renders `message_key` as its own
          // form-message for every consumer, so a modal that also kept the
          // sentence would print it twice, one line apart. **413 and 415 arrive
          // through this path** — B12 r1 HTTP-series envelopes with
          // `code: null` — and land under the form exactly like a 422.
          return { ok: false, error: toEnvelope(error) };
        }
      }}
    >
      <FileField
        id="document-file"
        label={t("customers.account.documents.field.file")}
        required
        accept={ACCOUNT_DOCUMENT_ACCEPT}
        // ⚠ `BR-SHL-031`'s allowlist and cap, said once on the screen. The
        // SERVER enforces both (415 and 413); this only saves a clerk choosing
        // a file that was always going to be refused. B14 rule 33: an
        // INSTRUCTION caps at six words PER SENTENCE, and two sentences of six
        // beat one of twelve.
        help={t("customers.account.documents.fileHelp")}
        fileName={file?.name ?? null}
        onChange={(chosen) => {
          setFile(chosen);
          if (chosen !== null && name === "") {
            setName(chosen.name);
          }
        }}
      />
      <SelectField
        id="document-type"
        label={t("customers.account.documents.field.type")}
        required
        value={docType}
        onChange={setDocType}
        // ⚠ **FOUR OPTIONS, NOT FIVE.** `system` is a value a row can HAVE and
        // not one a person may choose — `BR-CUS-036` says system documents
        // *"attach automatically"*, so offering it would let a clerk assert
        // that the product generated a file they scanned. The server refuses it
        // too; this is the door rather than the lock.
        options={typeOptions(t, UPLOADABLE_ACCOUNT_DOCUMENT_TYPES)}
        // `DEF-SHL-10751` — the state starts "", and with no placeholder the
        // box drew its FIRST type while holding none: picking that shown type
        // did nothing and the form said "required".
        placeholder={t("customFields.chooseOne")}
      />
      <TextField
        id="document-name"
        label={t("customers.account.documents.field.name")}
        required
        value={name}
        onChange={setName}
      />
    </FormModal>
  );
}

/**
 * S21's **Documents** tab — every file filed against this account.
 *
 * ⚠ **THE QUESTION THIS TAB ANSWERS HAD NO ANSWER AT ALL.** `BR-CUS-036` was
 * CONFIRMED on 2026-08-08 and named an `account_documents` table; neither the
 * table nor an upload endpoint existed, so this tab drew five column heads over
 * a sentence saying so. Both exist now.
 */
export function AccountDocumentsTab(props: RegionalProps & {
  accountId: string;
  client?: ApiClient;
}) {
  const { t, i18n } = useTranslation();
  // ⚠ **THE HOOK, NOT TWO PROPS.** `useRegional` is how every other dated table
  // on this screen resolves the tenant's zone and format, and it must run on
  // every render and never after an early return — which is why it is here and
  // not inside the cell.
  const { timeZone, dateFormat } = useRegional(props);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [uploading, setUploading] = useState(false);
  /** The row whose Remove was pressed — `null` while no dialog is open. */
  const [removing, setRemoving] = useState<AccountDocument | null>(null);

  // ⚠ **THE SAME GATE THE PAGE AROUND THIS TAB ALREADY USES**, not a second
  // one: `AccountDetailPage` reads `useAccessCell(ACCOUNTS_PERMISSION)` and
  // turns anything but Full into a reason. `BR-SHL-025` — the control stays
  // visible and says why. The server refuses regardless; this saves a round
  // trip and, more usefully, tells the clerk which of the two rules stopped
  // them.
  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  const remove = useMutation({
    mutationFn: (row: AccountDocument) => removeAccountDocument(props.accountId, row.id, client),
    onSuccess: () => {
      setRemoving(null);
      toast(t("customers.account.documents.removed"));
      void queryClient.invalidateQueries({
        queryKey: ["account-documents", props.accountId],
      });
    },
    onError: () => {
      // ⚠ **THE DIALOG CLOSES ON A FAILURE TOO, AND THE TOAST CARRIES IT.** A
      // dialog that stays open over a 409 invites the clerk to press again
      // against a rule that will refuse them every time — the refusal a
      // disabled bin was already telling them about, arriving a second way.
      setRemoving(null);
      toast(t("customers.account.documents.removeFailed"));
    },
  });

  const config = useMemo(
    () =>
      documentsTableConfig(t, {
        date: (row) =>
          // `BR-SHL-034` — ONE date formatter in this product. A tab that
          // formatted its own would be the second. A filing with no date cannot
          // happen (the column is NOT NULL), and the dash is here because the
          // wire type says it can rather than because the product does.
          row.uploaded_at === null ? (
            <Dash />
          ) : (
            <DateCell value={row.uploaded_at} timeZone={timeZone} dateFormat={dateFormat} />
          ),
        size: (row) => (
          <span className="tabular-nums">{formatBytes(row.size_bytes, i18n.language)}</span>
        ),
        // B14 rule 15 — an ICON with a tooltip, never a text link, and the
        // `danger` flag colours the glyph because this one destroys a filing.
        // ⚠ **THE ROLE GATE WINS OVER THE DOCUMENT LOCK WHEN BOTH APPLY**: a
        // read-only Executive looking at a contract is told they cannot write
        // here, which is the rule they would hit first and the one they can do
        // something about.
        actions: (row) => (
          <RowActions>
            {/* `DEF-CUS-9147` — the row could be filed and not OPENED. View
                first and the destructive act last, the order every other list
                draws (B14 rule 15: two visible, 👁 then −). ⚠ **NO `reason`:
                opening is a READ**, `AnyTenantRole` on the server, so a
                read-only role and an audit-locked contract both still open. */}
            <RowAction
              icon={<EyeIcon />}
              label={t("customers.account.documents.open")}
              onClick={() => {
                openDocumentContent(accountDocumentContentPath(props.accountId, row.id), "view");
              }}
            />
            <RowAction
              icon={<TrashIcon />}
              label={t("customers.account.documents.remove")}
              reason={writeBlockedReason ?? lockedReason(t, row.doc_type)}
              danger
              working={remove.isPending && removing?.id === row.id}
              onClick={() => setRemoving(row)}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      t,
      i18n.language,
      timeZone,
      dateFormat,
      writeBlockedReason,
      remove.isPending,
      removing?.id,
      props.accountId,
    ],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const listQuery = useQuery({
    queryKey: documentsQueryKey(props.accountId, state),
    queryFn: () =>
      listAccountDocuments(
        props.accountId,
        {
          q: state.q,
          page: state.page,
          per: state.per,
          sort: state.sort,
          dir: state.dir,
          type: state.filters.type,
        },
        client,
      ),
  });


  return (
    /* `data-account-overview` and the per-group `data-overview-group` hook are
       what the BROWSER census selects on (`10-scripts/render-checks/
       acc02-tab-conformance.mjs`): jsdom computes no layout, so no vitest case
       in this repo can say the screen LOOKS like the drawing. One column on
       this tab, because the drawing gives it one. */
    <div data-account-overview="">
      <div className="flex min-w-0 flex-col gap-4">
        {/* CR-190-BRC10 — the agreements sent to accept: Sent / Accepted /
            Expired, and Resend. Draws nothing on an account never sent one. */}
        <AccountAgreementsPanel
          accountId={props.accountId}
          timeZone={timeZone}
          dateFormat={dateFormat}
          writeBlockedReason={writeBlockedReason}
          client={client}
        />
        <Panel
          as="section"
          tone="group"
          data-overview-group="documents"
          data-screen={DOCUMENTS_TABLE_SCREEN}
          title={t("customers.account.tab.documents")}
          /* r10 draws this as the tab's PRIMARY. It is a SECONDARY here: the
             page header already carries the screen's one primary (Record
             payment, BR-SHL-044), which is B14 rule 4 and the same choice the
             Adjustments tab beside it makes. */
          trailing={
            <Button variant="secondary" onClick={() => setUploading(true)}>
              {t("customers.account.documents.upload")}
            </Button>
          }
        >
      <DataTable<AccountDocument>
        config={config}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("customers.account.documents.loadFailed"),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("customers.account.documents.empty"),
          helper: t("customers.account.documents.fileHelp"),
          ctaLabel: t("customers.account.documents.upload"),
          // B14 rule 4 — the page header already carries this screen's primary.
          ctaVariant: "secondary",
          onCta: () => setUploading(true),
        }}
      />

      {removing !== null && (
        <ConfirmDialog
          title={t("customers.account.documents.removeTitle")}
          // ⚠ **THE CONSEQUENCE IS THE WHOLE RULING, IN TWO SENTENCES.**
          // `BR-CUS-1052` says *removed* means it leaves the account and NOT
          // that the bytes are erased, and a clerk who believes they have
          // destroyed a customer's identity scan has been told the opposite of
          // what happened. B14 rule 33 caps a consequence at six words per
          // sentence and two sentences: *"This leaves the account permanently.
          // The stored file is kept."* — five and five, and neither is cut
          // below clarity. The RETENTION RULE behind the second sentence is
          // rationale and is ZERO words on screen; it lives in
          // `BR-SHL-031` and in this comment.
          consequence={t("customers.account.documents.removeWarning")}
          confirmLabel={t("customers.account.documents.remove")}
          // ⚠ B14 rule 6, AND THE PROP MUST STAND ALONE ON ITS LINE: the
          // call-site census in `ConfirmDialogTier.dom.test.tsx` reads this
          // file as TEXT, and a trailing comment here reads as an undeclared
          // tier.
          confirmVariant="danger"
          working={remove.isPending}
          onConfirm={() => remove.mutate(removing)}
          onCancel={() => setRemoving(null)}
        />
      )}

      {uploading && (
        <UploadDocumentForm
          accountId={props.accountId}
          client={client}
          onClose={() => setUploading(false)}
          onFiled={() => {
            setUploading(false);
            toast(t("customers.account.documents.filed"));
            void queryClient.invalidateQueries({
              queryKey: ["account-documents", props.accountId],
            });
          }}
        />
      )}
        </Panel>
      </div>
    </div>
  );
}
