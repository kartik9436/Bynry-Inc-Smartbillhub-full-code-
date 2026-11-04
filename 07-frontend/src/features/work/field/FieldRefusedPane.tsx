// ── Trace ──────────────────────────────────────────────
// Change:   CR-194-BRC10 — the fifth pane of *From the field*: field work the
//           server REFUSED, kept for the office (PO 2026-10-26, *"store on
//           both"*). The office reads what was sent, marks it reviewed, or
//           applies it to the job.
// Server:   GET work/refused-items · GET work/refused-items/{id} ·
//           POST …/{id}/review {note?} · POST …/{id}/apply
// Rules:    BR-WRK-071 · B14 rule 15 (row actions are icons) · 21 (Tailwind
//           only — on route-b-migrated.txt) · 31 (no id shown: a name, the
//           job's number, words) · 33 · 36 (the kit: DataTable, FilterBar,
//           ModalShell, Panel, FactBlock) · 43 (its own component, mounted by
//           `FieldDeskPage`) · CLAUDE.md hard rule 3 (a reading with its unit)
// ───────────────────────────────────────────────────────
//
// ⚠ **NO DRAWING EXISTS FOR THIS PANE.** The PO approved the plan's columns —
// Technician · Job · What · Reason · When · Status — and a detail with the
// work (a reading's value and unit, the photographs, the note), *Mark
// reviewed* and *Apply to the job*. The layout is composed from the kit on
// the findings pane's pattern; recorded in `CR-194-BRC10` §4.
//
// ⚠ **THE PANE STARTS ON *Open* BECAUSE THAT IS THE WORK**, as the findings
// pane does; a cleared filter reads `all`, never the server's silent default.
//
// ⚠ **THE DETAIL IS A DIALOG, ON THE ESTIMATE PRECEDENT** — one record, two
// outcomes, back to the list it was opened from; nobody links to a refusal.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { isApiError } from "@/api/client";
import { apiHref } from "@/api/apiHref";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { FilterBar } from "@/components/FilterBar";
import { ModalShell, TextField } from "@/components/FormModal";
import { EyeIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { WorkingButton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";

import {
  REFUSED_STATUSES,
  applyRefusedWork,
  getRefusedWork,
  listRefusedWork,
  markRefusedReviewed,
} from "./refusedWorkEndpoints";
import type { RefusedCounts, RefusedDetail, RefusedFacets, RefusedRow, RefusedStatus } from "./refusedWorkEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;
type Exists = (key: string) => boolean;

const STATUS_TONE: Record<RefusedStatus, StatusTone> = {
  open: "warning",
  reviewed: "neutral",
  applied: "success",
  applied_later: "success",
};

/** Every kind either door can refuse — `ITEM_KINDS` (job) and the reads door's
 *  four. One list, so a kind the server adds reads as *Other* rather than a code. */
export const REFUSED_KINDS = [
  "safety_tick",
  "task_tick",
  "reading",
  "material",
  "attachment",
  "signature",
  "close",
  "photo",
  "add_meter",
  "finding",
] as const;

/** What it was — a word, never the wire code (rule 31). */
export function kindText(kind: string, t: Translate): string {
  return (REFUSED_KINDS as readonly string[]).includes(kind) ? t(`work.refused.kind.${kind}`) : t("work.refused.kind.other");
}

/** The reason in the catalogue's words. The reads door's keys
 *  (`work.mobile.reads.<reason>`) are carried as the field app's
 *  `field.reads.refused.<reason>`; a key this build has no sentence for reads
 *  as *Refused by the server.* rather than a raw code. */
export function reasonText(
  row: { message_key: string; reason: string; params: Record<string, unknown> },
  t: Translate,
  exists: Exists,
): string {
  const key = row.message_key;
  if (key !== "" && exists(key)) return t(key, row.params);
  const reads = /^work\.mobile\.reads\.([a-z0-9_]+)$/.exec(key);
  if (reads !== null && exists(`field.reads.refused.${reads[1]}`)) return t(`field.reads.refused.${reads[1]}`, row.params);
  return t("work.refused.reason.other");
}

export interface RefusedCells {
  when: (row: RefusedRow) => React.ReactNode;
  actions: (row: RefusedRow) => React.ReactNode;
}

/** TECHNICIAN · JOB · WHAT · REASON · WHEN · STATUS · actions. */
export function refusedTableConfig(
  t: Translate,
  exists: Exists,
  counts: RefusedCounts | undefined,
  facets: RefusedFacets | undefined,
  cells: RefusedCells,
): TableConfig<RefusedRow> {
  return {
    screenId: "WRK-26",
    getRowId: (row) => row.id,
    defaultSort: { sort: "last_refused_at", dir: "desc" },
    searchFields: ["order_no"],
    searchPlaceholder: "work.refused.search",
    filters: [
      {
        name: "status",
        label: t("work.field.col.status"),
        options: REFUSED_STATUSES.map((s) => ({ value: s, label: t(`work.refused.status.${s}`) })),
        counts: counts === undefined ? undefined : { ...counts },
      },
      {
        name: "reason",
        label: t("work.field.col.reason"),
        options: (facets?.reasons ?? []).map((r) => ({
          value: r.reason,
          label: reasonText({ message_key: r.message_key, reason: r.reason, params: {} }, t, exists),
        })),
      },
      {
        name: "technician",
        label: t("work.field.col.technician"),
        options: (facets?.technicians ?? []).map((p) => ({ value: p.id, label: p.name })),
      },
      {
        name: "kind",
        label: t("work.refused.col.what"),
        options: (facets?.kinds ?? []).map((k) => ({ value: k, label: kindText(k, t) })),
      },
    ],
    columns: [
      {
        key: "technician",
        label: t("work.field.col.technician"),
        identity: true,
        cell: (row) => (row.technician === null ? <Dash /> : row.technician),
      },
      {
        key: "job",
        label: t("work.refused.col.job"),
        cell: (row) =>
          row.work_order?.order_no ? <span className="tabular-nums">{row.work_order.order_no}</span> : <Dash />,
      },
      {
        key: "kind",
        label: t("work.refused.col.what"),
        cell: (row) => <span data-refused-kind={row.kind}>{kindText(row.kind, t)}</span>,
      },
      {
        key: "reason",
        label: t("work.field.col.reason"),
        cell: (row) => <span data-refused-reason={row.reason}>{reasonText(row, t, exists)}</span>,
      },
      { key: "when", label: t("work.refused.col.when"), cell: cells.when },
      {
        key: "status",
        label: t("work.field.col.status"),
        cell: (row) => <StatusPill tone={STATUS_TONE[row.status]}>{t(`work.refused.status.${row.status}`)}</StatusPill>,
      },
      { key: "actions", label: t("work.field.col.actions"), cell: cells.actions },
    ],
  };
}

const EMPTY_CELLS: RefusedCells = { when: () => null, actions: () => null };

export function FieldRefusedPane(props: { client: ApiClient }) {
  const { t, i18n } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const exists: Exists = (key) => i18n.exists(key);
  const { timeZone, dateFormat } = useRegional({});
  const [state, setState] = useState<TableRequestState>(() => ({
    ...defaultRequestState(refusedTableConfig(translate, exists, undefined, undefined, EMPTY_CELLS)),
    filters: { status: "open" },
  }));
  const [opened, setOpened] = useState<RefusedRow | null>(null);
  const filters = state.filters;

  const listQuery = useQuery({
    queryKey: ["work", "field", "refused", state.page, state.per, state.q, filters],
    queryFn: () =>
      listRefusedWork(
        {
          status: filters.status ?? "",
          reason: filters.reason,
          technician: filters.technician,
          kind: filters.kind,
          q: state.q,
          page: state.page,
          per: state.per,
        },
        props.client,
      ),
  });
  const rows = useMemo(() => listQuery.data?.rows ?? [], [listQuery.data]);

  const config = refusedTableConfig(translate, exists, listQuery.data?.body.counts, listQuery.data?.body.facets, {
    when: (row) => <DateCell value={row.last_refused_at} timeZone={timeZone} dateFormat={dateFormat} />,
    actions: (row) => (
      <RowActions>
        <RowAction
          label={t("work.refused.open", { what: kindText(row.kind, translate) })}
          icon={<EyeIcon />}
          testId="refused-open"
          onClick={() => setOpened(row)}
        />
      </RowActions>
    ),
  });

  return (
    <div data-field-pane="refused">
      <DataTable<RefusedRow>
        config={config}
        state={state}
        onStateChange={setState}
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
        rows={rows}
        totalRows={listQuery.data?.total ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError ? { reason: t("work.field.loadFailed"), onRetry: () => void listQuery.refetch() } : null
        }
        empty={{ title: t("work.refused.empty.title"), helper: t("work.refused.empty.helper") }}
      />
      {opened !== null && (
        <RefusedWorkDialog row={opened} client={props.client} onClose={() => setOpened(null)} />
      )}
    </div>
  );
}

/** The work as sent, in its kind's words — never the raw payload. */
export function workFacts(detail: RefusedDetail, t: Translate): Fact[] {
  const facts: Fact[] = [];
  const work = detail.work;
  const reading = work.reading;
  if (reading !== undefined) {
    if (reading.prompt) facts.push({ id: "prompt", label: t("work.refused.fact.reading"), value: reading.prompt });
    if (reading.meter_no) facts.push({ id: "meter", label: t("work.refused.fact.meter"), value: reading.meter_no });
    if (reading.unable_to_read) {
      facts.push({ id: "value", label: t("work.refused.fact.value"), value: t("work.refused.unableToRead") });
    } else if (reading.value_text) {
      facts.push({ id: "value", label: t("work.refused.fact.value"), value: reading.value_text });
    } else if (reading.value !== undefined && reading.value !== null) {
      // Hard rule 3: the figure is shown WITH its unit, or with none — never one guessed.
      const value = reading.unit ? `${reading.value} ${reading.unit}` : reading.value;
      facts.push({ id: "value", label: t("work.refused.fact.value"), value: <span className="tabular-nums">{value}</span> });
    }
  }
  if (work.task?.title) facts.push({ id: "task", label: t("work.refused.fact.task"), value: work.task.title });
  if (work.safety?.text) facts.push({ id: "safety", label: t("work.refused.fact.safety"), value: work.safety.text });
  if (work.material !== undefined) {
    const qty = work.material.qty ?? "";
    facts.push({
      id: "material",
      label: t("work.refused.fact.part"),
      value: [work.material.part, [qty, work.material.unit].filter(Boolean).join(" ")].filter(Boolean).join(" · ") || "—",
    });
  }
  if (work.note) facts.push({ id: "note", label: t("work.refused.fact.note"), value: work.note });
  return facts;
}

/** The detail: who, which job, why; the work; the photographs; Mark reviewed
 *  (with a note) and Apply to the job. */
export function RefusedWorkDialog(props: { row: RefusedRow; client: ApiClient; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const exists: Exists = (key) => i18n.exists(key);
  const { tenant = "" } = useParams();
  const { timeZone, dateFormat } = useRegional({});
  const toast = useToast();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: ["work", "field", "refused", "detail", props.row.id],
    queryFn: () => getRefusedWork(props.row.id, props.client),
  });
  const detail = detailQuery.data;

  function fail(error: unknown) {
    if (isApiError(error) && error.messageKey) {
      setRefusal(reasonText({ message_key: error.messageKey, reason: "", params: error.params ?? {} }, translate, exists));
    } else {
      setRefusal(t("api.error.unexpected"));
    }
  }
  function done(message: string) {
    toast(message);
    void queryClient.invalidateQueries({ queryKey: ["work", "field", "refused"] });
    props.onClose();
  }
  const review = useMutation({
    mutationFn: () => markRefusedReviewed(props.row.id, note.trim(), props.client),
    onSuccess: () => done(t("work.refused.reviewed")),
    onError: fail,
  });
  const apply = useMutation({
    mutationFn: () => applyRefusedWork(props.row.id, props.client),
    onSuccess: () => done(t("work.refused.applied", { order: props.row.work_order?.order_no ?? "" })),
    onError: fail,
  });
  const busy = review.isPending || apply.isPending;
  const actionable = detail !== undefined && (detail.status === "open" || detail.status === "reviewed");

  const header: Fact[] = [
    { id: "technician", label: t("work.field.col.technician"), value: props.row.technician ?? "—" },
    { id: "job", label: t("work.refused.col.job"), value: props.row.work_order?.order_no ?? "—" },
    { id: "reason", label: t("work.field.col.reason"), value: reasonText(props.row, translate, exists) },
    {
      id: "captured",
      label: t("work.refused.fact.captured"),
      value: props.row.captured_at ? (
        <DateCell value={props.row.captured_at} timeZone={timeZone} dateFormat={dateFormat} />
      ) : (
        "—"
      ),
    },
    {
      id: "status",
      label: t("work.field.col.status"),
      value: <StatusPill tone={STATUS_TONE[props.row.status]}>{t(`work.refused.status.${props.row.status}`)}</StatusPill>,
    },
  ];
  if (props.row.refusal_count > 1) {
    header.push({ id: "times", label: t("work.refused.fact.times"), value: String(props.row.refusal_count) });
  }

  return (
    <ModalShell title={kindText(props.row.kind, translate)} kicker={t("work.refused.kicker")} onClose={props.onClose} size="wide" busy={busy}>
      <div className="modal-body flex flex-col gap-4" data-refused-detail="">
        <FactBlock name="refused-who" facts={header} variant="strip" />
        {detailQuery.isPending && <p className="m-0 text-md text-neutral-600">{t("work.refused.loading")}</p>}
        {detailQuery.isError && <RefusalStrip>{t("work.field.loadFailed")}</RefusalStrip>}
        {detail !== undefined && (
          <>
            <Panel title={t("work.refused.workTitle")} data-refused-work="">
              {workFacts(detail, translate).length === 0 ? (
                <p className="m-0 text-md text-neutral-600">{t("work.refused.noFields")}</p>
              ) : (
                <FactBlock name="refused-work" facts={workFacts(detail, translate)} variant="rows" />
              )}
            </Panel>
            {detail.photos.length > 0 && (
              <Panel title={t("work.field.col.photos")} data-refused-photos="">
                <ul className="m-0 flex list-none flex-wrap gap-3 p-0">
                  {detail.photos.map((photo, index) =>
                    photo.state === "uploaded" && photo.attachment_id && photo.work_order_id && tenant !== "" ? (
                      <li key={photo.attachment_id} className="h-24 w-24 border border-divider bg-surface">
                        <img
                          src={apiHref(`/${tenant}/work-orders/${photo.work_order_id}/attachments/${photo.attachment_id}/content`)}
                          alt={t("work.refused.photoAlt", { n: index + 1 })}
                          className="h-full w-full object-cover"
                          data-refused-photo="uploaded"
                        />
                      </li>
                    ) : (
                      <li
                        key={`phone-${index}`}
                        className="flex h-24 w-24 items-center justify-center border border-divider bg-surface p-2 text-center text-sm text-neutral-600"
                        data-refused-photo="on_phone"
                      >
                        {t("work.refused.photoOnPhone")}
                      </li>
                    ),
                  )}
                </ul>
              </Panel>
            )}
            {detail.note !== "" && (
              <FactBlock
                name="refused-note"
                facts={[{ id: "officeNote", label: t("work.refused.fact.officeNote"), value: detail.note }]}
                variant="rows"
              />
            )}
            {actionable && (
              <TextField id="refused-note" label={t("work.refused.noteLabel")} value={note} onChange={setNote} multiline />
            )}
            {refusal !== null && <RefusalStrip data-refused-refusal="">{refusal}</RefusalStrip>}
          </>
        )}
      </div>
      <div className="modal-foot">
        <Button variant="ghost" disabled={busy} onClick={props.onClose}>
          {t("forms.close")}
        </Button>
        {actionable && detail?.can_apply === true && (
          <Button variant="secondary" disabled={busy} onClick={() => apply.mutate()} data-refused-apply="">
            {t("work.refused.apply")}
          </Button>
        )}
        {actionable && (
          <WorkingButton working={review.isPending} disabled={busy} onClick={() => review.mutate()}>
            {t("work.refused.markReviewed")}
          </WorkingButton>
        )}
      </div>
    </ModalShell>
  );
}
