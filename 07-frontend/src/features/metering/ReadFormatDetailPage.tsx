// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11: ONE read format — its header, the
//           draft's questions as an editable list, and its versions. PO,
//           verbatim: *"utility users want customizations they wantt to collect
//           various data during meter reads hence we need to create meter read
//           format templates"*.
// Rules:    BR-MET-1211 (questions typed like custom fields, plus Photo) ·
//           BR-MET-1213 (versioned; a published version never changes — an
//           edit opens a NEW DRAFT) · BR-MET-1214 (asked when · follow-ups name
//           an EARLIER question) · BR-MET-1217 (raise a job) · BR-MET-1212
//           (retire is refused while anything points at it) · B14 rule 2 (one
//           page header) · rule 6 (danger tier on retire and delete) · rule 15
//           (row actions are icons, two visible, the rest under `…`) · rule 21
//           (Tailwind; on route-b-migrated.txt) · rule 31 (a question shows its
//           label, never its id) · rule 33 (copy caps)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **ORDER IS THE MEANING, SO THE QUESTION LIST DOES NOT SORT.** A follow-up
// may only name an EARLIER question, so the list is shown in the draft's own
// order and is moved with *Move up* / *Move down*, each of which sends the
// WHOLE order (`POST …/questions/reorder`) — the server refuses a move that
// would put a follow-up above the question it follows, and that refusal is
// shown on the page. A sortable header would let a clerk read the list in an
// order that is not the one a reader is asked in.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { clientPage } from "@/components/clientTable";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { ChevronDownIcon, ChevronUpIcon, PencilIcon, TrashIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { RefusalNotice } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ReadFormatQuestionModal } from "./ReadFormatQuestionModal";
import { READ_FORMATS_ROUTE, statusTone } from "./ReadFormatsPage";
import {
  deleteQuestion,
  getReadFormat,
  listReadFormatVersions,
  newReadFormatDraft,
  publishReadFormat,
  readFormatKeys,
  reorderQuestions,
  retireReadFormat,
} from "./readFormatsEndpoints";
import type { ReadFormatDetail, ReadFormatQuestion, ReadFormatVersion } from "./readFormatsEndpoints";
import { readFormatRefusal } from "./readFormatsShared";

export const READ_FORMAT_DETAIL_SCREEN = "SET-04.readFormatDetail";

export const READ_FORMAT_TABS = ["questions", "versions"] as const;
export type ReadFormatTab = (typeof READ_FORMAT_TABS)[number];

export function readFormatTabFrom(raw: string | null): ReadFormatTab {
  return raw === "versions" ? "versions" : "questions";
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** `keys` with the one at `index` swapped one place up (−1) or down (+1). */
export function movedKeys(keys: readonly string[], index: number, delta: -1 | 1): string[] {
  const next = [...keys];
  const target = index + delta;
  if (target < 0 || target >= next.length) {
    return next;
  }
  const [moved] = next.splice(index, 1);
  next.splice(target, 0, moved as string);
  return next;
}

/** What a question DOES beyond being asked — its follow-up and its job. */
export function behaviourText(
  q: ReadFormatQuestion,
  questions: readonly ReadFormatQuestion[],
  t: Translate,
): string | null {
  const parts: string[] = [];
  if (q.show_if !== null) {
    const parent = questions.find((other) => other.key === q.show_if?.question_key);
    parts.push(t("settings.readFormats.behaviour.follows", { question: parent?.label ?? "" }));
  }
  if (q.raise_work !== null) {
    parts.push(
      t("settings.readFormats.behaviour.raises", {
        template: q.raise_work.template?.name ?? "",
      }),
    );
  }
  return parts.length === 0 ? null : parts.join(" · ");
}

export function typeLabel(dataType: string, t: Translate): string {
  return dataType === "photo"
    ? t("settings.readFormats.type.photo")
    : t(`settings.customFields.type.${dataType}`);
}

export interface ReadFormatDetailPageProps extends RegionalProps {
  client?: ApiClient; // test seam
}

type Dialog =
  | { kind: "question"; existing: ReadFormatQuestion | null }
  | { kind: "delete"; question: ReadFormatQuestion }
  | { kind: "publish" }
  | { kind: "retire" }
  | null;

export function ReadFormatDetailPage(props: ReadFormatDetailPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const { formatId = "" } = useParams();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const [search, setSearch] = useSearchParams();
  const tab = readFormatTabFrom(search.get("tab"));
  const [dialog, setDialog] = useState<Dialog>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const query = useQuery({
    queryKey: readFormatKeys.detail(formatId),
    queryFn: () => getReadFormat(formatId, client),
  });

  function landed(detail: ReadFormatDetail): void {
    setRefusal(null);
    queryClient.setQueryData(readFormatKeys.detail(formatId), detail);
    void queryClient.invalidateQueries({ queryKey: readFormatKeys.all });
  }

  const action = useMutation({
    mutationFn: (run: () => Promise<ReadFormatDetail>) => run(),
    onSuccess: (detail) => landed(detail),
    onError: (error) => setRefusal(readFormatRefusal(error, t)),
  });

  if (query.data === undefined) {
    return query.isError ? (
      <RefusalNotice refusal={readFormatRefusal(query.error, t)} />
    ) : (
      <LoadingSkeleton variant="card" />
    );
  }

  const detail = query.data;
  const draft = detail.draft;
  const shown = draft ?? detail.current;
  const questions = shown?.questions ?? [];
  const editable = draft !== null && detail.status !== "retired";

  const header = (
    <PageHeader
      backTo={{ to: tenantPath(READ_FORMATS_ROUTE), label: t("settings.readFormats.title") }}
      kicker={detail.service.name}
      title={detail.name}
      status={
        <StatusPill tone={statusTone(detail.status)}>
          {t(`settings.readFormats.status.${detail.status}`)}
        </StatusPill>
      }
      rollup={
        detail.current_version === null
          ? t("settings.readFormats.neverPublished")
          : t(draft === null ? "settings.readFormats.versionLine" : "settings.readFormats.versionLineDraft", {
              n: detail.current_version.version_no,
            })
      }
      secondaryActions={
        <>
          {detail.status === "published" && draft === null && (
            <Button
              variant="secondary"
              onClick={() => action.mutate(() => newReadFormatDraft(formatId, client))}
            >
              {t("settings.readFormats.newDraft")}
            </Button>
          )}
          {detail.status === "published" && (
            <Button variant="danger" onClick={() => setDialog({ kind: "retire" })}>
              {t("settings.readFormats.action.retire")}
            </Button>
          )}
        </>
      }
      primaryAction={
        editable ? (
          <Button variant="primary" onClick={() => setDialog({ kind: "publish" })}>
            {t("settings.readFormats.publish")}
          </Button>
        ) : undefined
      }
      tabs={READ_FORMAT_TABS.map((id) => ({ id, label: t(`settings.readFormats.tab.${id}`) }))}
      activeTabId={tab}
      tabsLabel={t("settings.readFormats.tabsLabel")}
      onTabSelect={(next) => {
        const params = new URLSearchParams(search);
        params.set("tab", next.id);
        setSearch(params, { replace: true });
      }}
    />
  );

  return (
    <section aria-label={detail.name} className="flex flex-col gap-4">
      {header}
      <RefusalNotice refusal={refusal} />

      {tab === "questions" ? (
        <QuestionsList
          questions={questions}
          editable={editable}
          locked={detail.status === "published" && draft === null}
          onAdd={() => setDialog({ kind: "question", existing: null })}
          onEdit={(q) => setDialog({ kind: "question", existing: q })}
          onDelete={(q) => setDialog({ kind: "delete", question: q })}
          onMove={(index, delta) =>
            action.mutate(() =>
              reorderQuestions(
                formatId,
                movedKeys(
                  questions.map((q) => q.key),
                  index,
                  delta,
                ),
                client,
              ),
            )
          }
          busy={action.isPending}
        />
      ) : (
        <VersionsList formatId={formatId} client={client} regional={props} />
      )}

      {dialog?.kind === "question" && (
        <ReadFormatQuestionModal
          formatId={formatId}
          questions={questions}
          existing={dialog.existing}
          client={client}
          onClose={() => setDialog(null)}
          onSaved={(saved) => {
            setDialog(null);
            landed(saved);
            fireToast(t("settings.readFormats.question.saved"));
          }}
        />
      )}

      {dialog?.kind === "delete" && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("settings.readFormats.question.deleteTitle", { question: dialog.question.label })}
          consequence={t("settings.readFormats.question.deleteConsequence")}
          confirmLabel={t("settings.reference.delete")}
          working={action.isPending}
          onConfirm={() => {
            const key = dialog.question.key;
            setDialog(null);
            action.mutate(() => deleteQuestion(formatId, key, client));
          }}
          onCancel={() => setDialog(null)}
        />
      )}

      {dialog?.kind === "publish" && (
        <PublishDialog
          formatId={formatId}
          client={client}
          onClose={() => setDialog(null)}
          onPublished={(published) => {
            setDialog(null);
            landed(published);
            fireToast(
              t("settings.readFormats.published", {
                n: published.current_version?.version_no ?? "",
              }),
            );
          }}
        />
      )}

      {dialog?.kind === "retire" && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("settings.readFormats.retire.title", { name: detail.name })}
          consequence={t("settings.readFormats.retire.consequence")}
          confirmLabel={t("settings.readFormats.retire.confirm")}
          working={action.isPending}
          onConfirm={() => {
            setDialog(null);
            action.mutate(() => retireReadFormat(formatId, client));
          }}
          onCancel={() => setDialog(null)}
        />
      )}
    </section>
  );
}

function QuestionsList(props: {
  questions: readonly ReadFormatQuestion[];
  editable: boolean;
  locked: boolean;
  busy: boolean;
  onAdd: () => void;
  onEdit: (q: ReadFormatQuestion) => void;
  onDelete: (q: ReadFormatQuestion) => void;
  onMove: (index: number, delta: -1 | 1) => void;
}) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const lockedReason = props.editable ? null : t("settings.readFormats.lockedReason");
  const { questions } = props;

  const config: TableConfig<ReadFormatQuestion> = useMemo(
    () => ({
      screenId: `${READ_FORMAT_DETAIL_SCREEN}.questions`,
      getRowId: (row) => row.key,
      defaultSort: { sort: "seq", dir: "asc" },
      columns: [
        {
          key: "seq",
          label: t("settings.readFormats.col.order"),
          numeric: true,
          cell: (row) => <span className="tabular-nums">{questions.indexOf(row) + 1}</span>,
        },
        {
          key: "label",
          label: t("settings.readFormats.col.question"),
          identity: true,
          cell: (row) =>
            props.editable ? (
              <button
                type="button"
                className="text-left text-accent underline"
                onClick={() => props.onEdit(row)}
              >
                {row.label}
              </button>
            ) : (
              <span>{row.label}</span>
            ),
        },
        {
          key: "data_type",
          label: t("settings.readFormats.col.type"),
          cell: (row) => <span>{typeLabel(row.data_type, translate)}</span>,
        },
        {
          key: "asked_when",
          label: t("settings.readFormats.question.askedWhen"),
          cell: (row) => <span>{t(`settings.readFormats.asked.${row.asked_when}`)}</span>,
        },
        {
          key: "is_required",
          label: t("settings.readFormats.col.required"),
          cell: (row) =>
            row.is_required ? <span>{t("settings.readFormats.answer.yes")}</span> : <Dash />,
        },
        {
          key: "behaviour",
          label: t("settings.readFormats.col.behaviour"),
          cell: (row) => {
            const text = behaviourText(row, questions, translate);
            return text === null ? <Dash /> : <span>{text}</span>;
          },
        },
        {
          key: "actions",
          label: t("settings.reference.col.actions"),
          cell: (row) => {
            const index = questions.indexOf(row);
            return (
              <RowActions>
                <RowAction
                  label={t("settings.readFormats.action.moveUp")}
                  icon={<ChevronUpIcon />}
                  reason={lockedReason ?? (index === 0 ? t("settings.readFormats.alreadyFirst") : null)}
                  working={props.busy}
                  onClick={() => props.onMove(index, -1)}
                />
                <RowAction
                  label={t("settings.readFormats.action.moveDown")}
                  icon={<ChevronDownIcon />}
                  reason={
                    lockedReason ??
                    (index === questions.length - 1 ? t("settings.readFormats.alreadyLast") : null)
                  }
                  working={props.busy}
                  onClick={() => props.onMove(index, 1)}
                />
                <RowActionsMore label={t("settings.readFormats.action.more")}>
                  <RowMenuAction
                    label={t("settings.readFormats.action.edit")}
                    icon={<PencilIcon />}
                    reason={lockedReason}
                    onClick={() => props.onEdit(row)}
                  />
                  <RowMenuAction
                    label={t("settings.reference.delete")}
                    icon={<TrashIcon />}
                    danger
                    reason={lockedReason}
                    onClick={() => props.onDelete(row)}
                  />
                </RowActionsMore>
              </RowActions>
            );
          },
        },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, questions, props.editable, props.busy, lockedReason],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  // Order is the meaning: the page is cut from the draft's own order and the
  // sort never moves (`sortValue` answers the position).
  const page = clientPage(questions, state, {
    search: (row) => [row.label],
    filter: () => true,
    sortValue: (row) => row.seq,
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {props.locked ? (
          <p className="m-0 text-base" role="note">
            {t("settings.readFormats.lockedNote")}
          </p>
        ) : (
          <span />
        )}
        {props.editable && (
          <Button variant="secondary" onClick={props.onAdd}>
            {t("settings.readFormats.question.addButton")}
          </Button>
        )}
      </div>
      <DataTable<ReadFormatQuestion>
        config={config}
        state={state}
        onStateChange={setState}
        rows={page.page}
        totalRows={page.total}
        loading={false}
        empty={{
          title: t("settings.readFormats.question.emptyTitle"),
          helper: t("settings.readFormats.question.emptyHelper"),
          ...(props.editable
            ? { ctaLabel: t("settings.readFormats.question.addButton"), ctaVariant: "secondary" as const, onCta: props.onAdd }
            : {}),
        }}
      />
    </div>
  );
}

function VersionsList(props: { formatId: string; client: ApiClient; regional: RegionalProps }) {
  const { t } = useTranslation();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const config: TableConfig<ReadFormatVersion> = useMemo(
    () => ({
      screenId: `${READ_FORMAT_DETAIL_SCREEN}.versions`,
      getRowId: (row) => row.id,
      defaultSort: { sort: "version_no", dir: "desc" },
      columns: [
        {
          key: "version_no",
          label: t("settings.readFormats.col.version"),
          identity: true,
          cell: (row) =>
            row.version_no === null ? (
              <span>{t("settings.readFormats.status.draft")}</span>
            ) : (
              <span className="tabular-nums">{t("settings.readFormats.versionNo", { n: row.version_no })}</span>
            ),
        },
        {
          key: "published_at",
          label: t("settings.readFormats.col.published"),
          cell: (row) =>
            row.published_at === null ? (
              <Dash />
            ) : (
              <DateCell value={row.published_at} timeZone={timeZone} dateFormat={dateFormat} />
            ),
        },
        {
          key: "published_by",
          label: t("settings.readFormats.col.by"),
          cell: (row) => (row.published_by === null ? <Dash /> : <span>{row.published_by}</span>),
        },
        {
          key: "change_note",
          label: t("settings.readFormats.col.whatChanged"),
          cell: (row) => (row.change_note === null ? <Dash /> : <span>{row.change_note}</span>),
        },
      ],
    }),
    [t, timeZone, dateFormat],
  );
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: readFormatKeys.versions(props.formatId, state.page, state.per),
    queryFn: () => listReadFormatVersions(props.formatId, { page: state.page, per: state.per }, props.client),
  });
  return (
    <DataTable<ReadFormatVersion>
      config={config}
      state={state}
      onStateChange={setState}
      rows={query.data?.rows ?? []}
      totalRows={query.data?.total ?? null}
      loading={query.isPending}
      error={
        query.isError
          ? { reason: t("settings.readFormats.loadFailed"), onRetry: () => void query.refetch() }
          : null
      }
      empty={{
        title: t("settings.readFormats.versions.emptyTitle"),
        helper: t("settings.readFormats.versions.emptyHelper"),
      }}
    />
  );
}

/** *Publish* — the draft becomes the next numbered version; an optional note. */
function PublishDialog(props: {
  formatId: string;
  client: ApiClient;
  onClose: () => void;
  onPublished: (detail: ReadFormatDetail) => void;
}) {
  const { t } = useTranslation();
  const [note, setNote] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      props.onPublished(await publishReadFormat(props.formatId, note, props.client));
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.readFormats.publishTitle")}
      schema={z.object({ change_note: z.string().max(500, t("settings.reference.tooLong", { max: 500 })) })}
      values={{ change_note: note }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("settings.readFormats.publish")}
    >
      <TextField
        id="change_note"
        label={t("settings.readFormats.col.whatChanged")}
        value={note}
        onChange={setNote}
        multiline
      />
      <p className="m-0 text-base" data-consequence="read-format-publish">
        {t("settings.readFormats.publishConsequence")}
      </p>
    </FormModal>
  );
}
