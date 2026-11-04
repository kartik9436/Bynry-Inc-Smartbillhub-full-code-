// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-056 (EP-WRK-11) — orders a technician raised on site, for
//           the office to REVIEW: since FB-028 (PO 2026-10-31) each is already
//           assigned to the technician who raised it; accept marks it seen,
//           refuse with a reason cancels it (nothing deleted) (E2E-16)
// Server:   GET work/field-raised?status=&page=&per= ·
//           POST work-orders/{id}/field-raise {decision, reason?}
// Rules:    BR-FLD-00023 (R23 — SUPERSEDED 2026-10-31 by FB-028: no office
//           wait; the money decision is on the job's step) · BR-FLD-00024 (the number is the server's) ·
//           R112 (raised from a template, its version stamped — a version
//           that moved between the handset and the server is SHOWN) ·
//           B14 rule 6 (Refuse cancels an order — the danger tier) ·
//           rule 15 (icons, two visible) · 31 (no id shown — the position is
//           a place, not an id) · 33 · 21
// ───────────────────────────────────────────────────────
//
// ⚠ **A CLEARED STATUS FILTER MEANS EVERY STATUS.** The server's default is
// `pending`, so an absent filter would silently read *pending* under a chip
// row that says nothing is filtered — the endpoint wrapper sends `all`
// instead, and this pane STARTS on *Pending* because that is the work.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DateCell } from "@/components/DateCell";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { CommitIcon, EyeIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { FIELD_RAISE_STATUSES, decideFieldRaise, listFieldRaised, orderAddress } from "./fieldDeskEndpoints";
import type { FieldRaisedRow, FieldRaiseCounts, FieldRaiseStatus } from "./fieldDeskEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const STATUS_TONE: Record<FieldRaiseStatus, StatusTone> = {
  pending: "warning",
  accepted: "success",
  refused: "muted",
};

/** The template and its version — `v3`, or `v2 → v3` where the template moved
 *  between the handset picking it and the server stamping it (R112). */
export function templateText(row: FieldRaisedRow, t: Translate): string | null {
  const tpl = row.template;
  if (tpl === null) return null;
  if (tpl.version_moved && tpl.version_picked !== null && tpl.version_stamped !== null) {
    return `${tpl.name} · ${t("work.field.versionMoved", { picked: tpl.version_picked, stamped: tpl.version_stamped })}`;
  }
  const version = tpl.version_stamped ?? tpl.version_picked;
  return version === null ? tpl.name : `${tpl.name} · ${t("work.field.version", { version })}`;
}

export interface RaisedCells {
  raisedAt: (row: FieldRaisedRow) => React.ReactNode;
  actions: (row: FieldRaisedRow) => React.ReactNode;
}

/** ORDER · TEMPLATE · WHERE · RAISED BY · RAISED · ASSIGNED TO · POSITION · PHOTOS · STATUS · actions. */
export function fieldRaisedTableConfig(
  t: Translate,
  counts: FieldRaiseCounts | undefined,
  cells: RaisedCells,
): TableConfig<FieldRaisedRow> {
  return {
    screenId: "WRK-26",
    getRowId: (row) => row.order_id,
    defaultSort: { sort: "raised_at", dir: "asc" },
    filters: [
      {
        name: "status",
        label: t("work.field.col.status"),
        options: FIELD_RAISE_STATUSES.map((s) => ({ value: s, label: t(`work.field.status.${s}`) })),
        counts: counts === undefined ? undefined : { ...counts },
      },
    ],
    columns: [
      {
        key: "order_no",
        label: t("work.field.col.order"),
        identity: true,
        cell: (row) => (
          <span className="inline-flex items-center gap-2">
            <span className="tabular-nums">{row.order_no ?? ""}</span>
            {row.is_reconnect && <StatusPill tone="warning">{t("work.field.reconnect")}</StatusPill>}
          </span>
        ),
      },
      {
        key: "template",
        label: t("work.field.col.template"),
        cell: (row) => {
          const text = templateText(row, t);
          return text === null ? <Dash /> : <span data-template-version-moved={row.template?.version_moved ? "" : undefined}>{text}</span>;
        },
      },
      {
        key: "where",
        label: t("work.field.col.where"),
        cell: (row) => (row.premise?.address ? row.premise.address : <Dash />),
      },
      {
        key: "raised_by",
        label: t("work.field.col.raisedBy"),
        cell: (row) => (row.raised_by === null ? <Dash /> : row.raised_by),
      },
      { key: "raised_at", label: t("work.field.col.raisedAt"), cell: cells.raisedAt },
      {
        // FB-028 (PO 2026-10-31) — the raiser holds it from the raise; the
        // dispatcher may reassign it any time. A name, never an id (rule 31).
        key: "assigned_to",
        label: t("work.field.col.assignedTo"),
        cell: (row) => (row.assigned_to?.name ? row.assigned_to.name : <Dash />),
      },
      {
        key: "position",
        label: t("work.field.col.position"),
        cell: (row) =>
          row.position === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums" data-position="">
              {t("work.field.position", {
                lat: row.position.lat,
                lng: row.position.lng,
                accuracy: row.position.accuracy_m,
              })}
            </span>
          ),
      },
      {
        key: "photographs",
        label: t("work.field.col.photos"),
        cell: (row) => <span className="tabular-nums">{row.photographs}</span>,
      },
      {
        key: "status",
        label: t("work.field.col.status"),
        cell: (row) => <StatusPill tone={STATUS_TONE[row.status]}>{t(`work.field.status.${row.status}`)}</StatusPill>,
      },
      { key: "actions", label: t("work.field.col.actions"), cell: cells.actions },
    ],
  };
}

const EMPTY_CELLS: RaisedCells = { raisedAt: () => null, actions: () => null };

type Asking = { act: "accept" | "refuse"; row: FieldRaisedRow } | null;

export function FieldRaisedPane(props: { client: ApiClient }) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional({});
  const [state, setState] = useState<TableRequestState>(() => ({
    ...defaultRequestState(fieldRaisedTableConfig(translate, undefined, EMPTY_CELLS)),
    filters: { status: "pending" },
  }));
  const [asking, setAsking] = useState<Asking>(null);
  const [working, setWorking] = useState(false);
  const status = state.filters.status ?? "";

  const listQuery = useQuery({
    queryKey: ["work", "field", "raised", state.page, state.per, status],
    queryFn: () => listFieldRaised({ status, page: state.page, per: state.per }, props.client),
  });
  const rows = useMemo(() => listQuery.data?.rows ?? [], [listQuery.data]);

  async function accept(row: FieldRaisedRow) {
    setWorking(true);
    try {
      await decideFieldRaise(row.order_id, { decision: "accept" }, props.client);
      toast(t("work.field.accepted", { order: row.order_no ?? "" }));
      void queryClient.invalidateQueries({ queryKey: ["work"] });
    } catch (error) {
      toast(refusalText(translate, error));
    } finally {
      setWorking(false);
      setAsking(null);
    }
  }

  const config = fieldRaisedTableConfig(translate, listQuery.data?.body.counts, {
    raisedAt: (row) => <DateCell value={row.raised_at} timeZone={timeZone} dateFormat={dateFormat} />,
    actions: (row) => {
      // A decided raise reads its decision in STATUS and offers no act on it.
      const pending = row.status === "pending";
      return (
        <RowActions>
          <RowActionLink
            label={t("work.field.open", { order: row.order_no ?? "" })}
            icon={<EyeIcon />}
            to={tenantPath(orderAddress(row.order_id))}
          />
          {pending && (
            <RowAction
              label={t("work.field.accept", { order: row.order_no ?? "" })}
              icon={<CommitIcon />}
              testId="raised-accept"
              onClick={() => setAsking({ act: "accept", row })}
            />
          )}
          {pending && (
            <RowAction
              label={t("work.field.refuse", { order: row.order_no ?? "" })}
              icon={<TrashIcon />}
              danger
              testId="raised-refuse"
              onClick={() => setAsking({ act: "refuse", row })}
            />
          )}
        </RowActions>
      );
    },
  });

  return (
    <div data-field-pane="raised">
      <DataTable<FieldRaisedRow>
        config={config}
        state={state}
        onStateChange={setState}
        filterBarSlot={<FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />}
        rows={rows}
        totalRows={listQuery.data?.total ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? { reason: t("work.field.loadFailed"), onRetry: () => void listQuery.refetch() }
            : null
        }
        empty={{ title: t("work.field.raisedEmpty.title"), helper: t("work.field.raisedEmpty.helper") }}
      />

      {asking?.act === "accept" && (
        <ConfirmDialog
          title={t("work.approvals.acceptTitle", { order: asking.row.order_no ?? "" })}
          consequence={t("work.field.raisedAcceptConsequence")}
          confirmLabel={t("work.approvals.acceptConfirm")}
          cancelLabel={t("work.field.back")}
          working={working}
          onConfirm={() => void accept(asking.row)}
          onCancel={() => setAsking(null)}
        />
      )}
      {asking?.act === "refuse" && (
        <RefuseRaisedDialog
          row={asking.row}
          client={props.client}
          onClose={() => setAsking(null)}
          onDone={() => {
            toast(t("work.field.refuseDone", { order: asking.row.order_no ?? "" }));
            setAsking(null);
            void queryClient.invalidateQueries({ queryKey: ["work"] });
          }}
        />
      )}
    </div>
  );
}

/** *Refuse* — a reason, then the order is canceled (the server's `cancel`
 *  posture: it keeps its number and its history). Danger tier, rule 6. */
export function RefuseRaisedDialog(props: {
  row: FieldRaisedRow;
  client: ApiClient;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await decideFieldRaise(props.row.order_id, { decision: "refuse", reason: reason.trim() }, props.client);
      props.onDone();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }
  return (
    <FormModal
      title={t("work.field.refuseTitle", { order: props.row.order_no ?? "" })}
      schema={z.object({ reason: z.string().trim().min(1, t("work.field.reasonRequired")) })}
      values={{ reason }}
      submitLabel={t("work.field.refuseSubmit")}
      submitVariant="danger"
      cancelLabel={t("work.field.back")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <TextField id="reason" label={t("work.field.reason")} value={reason} onChange={setReason} multiline required />
      <p className="m-0 text-md" data-consequence="work-field-refuse">
        {t("work.field.refuseConsequence")}
      </p>
    </FormModal>
  );
}
