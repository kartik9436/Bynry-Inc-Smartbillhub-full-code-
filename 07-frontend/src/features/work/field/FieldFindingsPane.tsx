// ── Trace ──────────────────────────────────────────────
// Story:    BR-WRK-067 (PO 2026-10-22, *"if a rule is set work order will get
//           created , if not user can create the work order"*) — the fourth
//           pane of *From the field*: what meter readers found on a route
//           (RW-21 *Raise it*, RW-18's mismatch), and the office's *Create
//           work order…* for a finding no rule took. CR-187-BRC10 lane FINDINGS.
// Server:   GET work/route-findings?status=&page=&per= ·
//           POST work/route-findings/{id}/work-order {template_id, priority_id?}
// Rules:    BR-MET-1202 (the capture point is where the PHONE was — labelled
//           so, never as the property's place) · B14 rule 15 (icons, two
//           visible) · 21 (Tailwind only — listed on route-b-migrated.txt) ·
//           31 (no id shown: the meter's number, the stop's address, a name)
//           · 33 · 43 (its own component, mounted by `FieldDeskPage`)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PANE STARTS ON *Open* BECAUSE THAT IS THE WORK** — a finding a rule
// already turned into a job needs nobody; a cleared filter reads `all`, never
// the server's silent default (`listRouteFindings`).
//
// ⚠ **THE PHOTOGRAPHS ARE A COUNT.** They are route photos held in metering
// (`field_read_photos`) and no office read of their bytes exists yet; the
// column says how many came back, which is what the raised pane does too.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { CommitIcon, EyeIcon } from "@/components/icons";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { getRaiseOptions, listTemplates } from "../workEndpoints";
import {
  ROUTE_FINDING_STATUSES,
  createFindingWorkOrder,
  listRouteFindings,
  orderAddress,
} from "./fieldDeskEndpoints";
import type { RouteFindingCounts, RouteFindingRow, RouteFindingStatus } from "./fieldDeskEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const STATUS_TONE: Record<RouteFindingStatus, StatusTone> = {
  open: "warning",
  work_order_created: "success",
};

/** The page fetches every published template and priority for the dialog in
 *  one read each; the server pages both, and this is the rule builder's own
 *  figure (`useRuleLookups`). */
const LOOKUP_PER = 200;

/** Where the finding is — the METER's number when the reader named one, else
 *  the stop's address (rule 31: a number a clerk quotes, never an id). */
export function findingPlace(row: RouteFindingRow): string | null {
  if (row.meter_no) return row.stop?.address ? `${row.meter_no} · ${row.stop.address}` : row.meter_no;
  return row.stop?.address ?? row.stop?.premise_no ?? null;
}

/** The capture point — the phone's own fix, with its accuracy where it came. */
export function capturePointText(row: RouteFindingRow, t: Translate): string | null {
  const point = row.capture_point;
  if (point === null) return null;
  if (point.accuracy_m === null) return `${point.lat}, ${point.lng}`;
  return t("work.field.position", { lat: point.lat, lng: point.lng, accuracy: point.accuracy_m });
}

export interface FindingCells {
  foundAt: (row: RouteFindingRow) => React.ReactNode;
  actions: (row: RouteFindingRow) => React.ReactNode;
}

/** FINDING · METER OR STOP · TECHNICIAN · FOUND · CAPTURE POINT · PHOTOS ·
 *  WORK ORDER · STATUS · actions. */
export function fieldFindingsTableConfig(
  t: Translate,
  counts: RouteFindingCounts | undefined,
  cells: FindingCells,
): TableConfig<RouteFindingRow> {
  return {
    screenId: "WRK-26",
    getRowId: (row) => row.id,
    defaultSort: { sort: "received_at", dir: "desc" },
    filters: [
      {
        name: "status",
        label: t("work.field.col.status"),
        options: ROUTE_FINDING_STATUSES.map((s) => ({ value: s, label: t(`work.findings.status.${s}`) })),
        counts: counts === undefined ? undefined : { ...counts },
      },
    ],
    columns: [
      {
        key: "kind",
        label: t("work.findings.col.finding"),
        identity: true,
        cell: (row) => <span data-finding-kind={row.kind}>{t(`work.findings.kind.${row.kind}`)}</span>,
      },
      {
        key: "place",
        label: t("work.findings.col.place"),
        cell: (row) => {
          const place = findingPlace(row);
          return place === null ? <Dash /> : <span className="tabular-nums">{place}</span>;
        },
      },
      {
        key: "technician",
        label: t("work.findings.col.technician"),
        cell: (row) => (row.technician === null ? <Dash /> : row.technician),
      },
      { key: "found_at", label: t("work.findings.col.found"), cell: cells.foundAt },
      {
        key: "capture_point",
        label: t("work.findings.col.capturePoint"),
        cell: (row) => {
          const text = capturePointText(row, t);
          return text === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums" data-capture-point="">
              {text}
            </span>
          );
        },
      },
      {
        key: "photographs",
        label: t("work.field.col.photos"),
        cell: (row) => <span className="tabular-nums">{row.photographs}</span>,
      },
      {
        key: "work_order",
        label: t("work.findings.col.workOrder"),
        cell: (row) =>
          row.work_order === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums" data-finding-conversion={row.conversion ?? ""}>
              {row.work_order.order_no ?? ""}
            </span>
          ),
      },
      {
        key: "status",
        label: t("work.field.col.status"),
        cell: (row) => <StatusPill tone={STATUS_TONE[row.status]}>{t(`work.findings.status.${row.status}`)}</StatusPill>,
      },
      { key: "actions", label: t("work.field.col.actions"), cell: cells.actions },
    ],
  };
}

const EMPTY_CELLS: FindingCells = { foundAt: () => null, actions: () => null };

export function FieldFindingsPane(props: { client: ApiClient }) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional({});
  const [state, setState] = useState<TableRequestState>(() => ({
    ...defaultRequestState(fieldFindingsTableConfig(translate, undefined, EMPTY_CELLS)),
    filters: { status: "open" },
  }));
  const [creating, setCreating] = useState<RouteFindingRow | null>(null);
  const status = state.filters.status ?? "";

  const listQuery = useQuery({
    queryKey: ["work", "field", "findings", state.page, state.per, status],
    queryFn: () => listRouteFindings({ status, page: state.page, per: state.per }, props.client),
  });
  const rows = useMemo(() => listQuery.data?.rows ?? [], [listQuery.data]);

  const config = fieldFindingsTableConfig(translate, listQuery.data?.body.counts, {
    foundAt: (row) => {
      // The phone's clock at capture (R92), else when the server received it.
      const at = row.captured_at ?? row.received_at;
      return at === null ? <Dash /> : <DateCell value={at} timeZone={timeZone} dateFormat={dateFormat} />;
    },
    actions: (row) => {
      const finding = t(`work.findings.kind.${row.kind}`);
      return (
        <RowActions>
          {row.work_order !== null && (
            <RowActionLink
              label={t("work.field.open", { order: row.work_order.order_no ?? "" })}
              icon={<EyeIcon />}
              to={tenantPath(orderAddress(row.work_order.id))}
            />
          )}
          {row.status === "open" && (
            <RowAction
              label={t("work.findings.create", { finding })}
              icon={<CommitIcon />}
              testId="finding-create"
              onClick={() => setCreating(row)}
            />
          )}
        </RowActions>
      );
    },
  });

  return (
    <div data-field-pane="findings">
      <DataTable<RouteFindingRow>
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
        empty={{ title: t("work.findings.empty.title"), helper: t("work.findings.empty.helper") }}
      />
      {creating !== null && (
        <CreateFindingWorkOrderDialog
          row={creating}
          client={props.client}
          onClose={() => setCreating(null)}
          onDone={(orderNo) => {
            toast(t("work.findings.created", { order: orderNo }));
            setCreating(null);
            void queryClient.invalidateQueries({ queryKey: ["work"] });
          }}
        />
      )}
    </div>
  );
}

/** *Create work order…* — a published template (required) and a priority
 *  (optional; the template's own applies without one). Once per finding: the
 *  server answers the existing job if another hand got there first. */
export function CreateFindingWorkOrderDialog(props: {
  row: RouteFindingRow;
  client: ApiClient;
  onClose: () => void;
  onDone: (orderNo: string) => void;
}) {
  const { t } = useTranslation();
  const [templateId, setTemplateId] = useState("");
  const [priorityId, setPriorityId] = useState("");
  const templates = useQuery({
    queryKey: ["work", "findings", "templates"],
    queryFn: () => listTemplates({ per: LOOKUP_PER }, props.client),
  });
  const options = useQuery({
    queryKey: ["work", "findings", "raise-options"],
    queryFn: () => getRaiseOptions(props.client),
  });
  // A draft (`version` 0) or a deactivated template cannot raise (BR-WRK-011).
  const templateOptions = (templates.data?.results ?? [])
    .filter((row) => row.active && row.version >= 1)
    .map((row) => ({ value: row.id, label: row.name }));
  const priorityOptions = (options.data?.priorities ?? []).map((row) => ({ value: row.id, label: row.name }));

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const made = await createFindingWorkOrder(
        props.row.id,
        priorityId === "" ? { template_id: templateId } : { template_id: templateId, priority_id: priorityId },
        props.client,
      );
      props.onDone(made.work_order?.order_no ?? "");
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("work.findings.createTitle")}
      schema={z.object({ template: z.string().min(1, t("work.findings.templateRequired")) })}
      values={{ template: templateId }}
      submitLabel={t("work.findings.createSubmit")}
      cancelLabel={t("work.field.back")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <p className="m-0 text-md" data-finding-summary="">
        {t(`work.findings.kind.${props.row.kind}`)}
        {findingPlace(props.row) === null ? "" : ` · ${findingPlace(props.row)}`}
      </p>
      <SelectField
        id="template"
        label={t("work.findings.template")}
        value={templateId}
        onChange={setTemplateId}
        options={templateOptions}
        placeholder={t("work.rules.builder.pickTemplate")}
        required
      />
      <SelectField
        id="priority"
        label={t("work.findings.priority")}
        value={priorityId}
        onChange={setPriorityId}
        options={priorityOptions}
        placeholder={t("work.findings.templatePriority")}
      />
    </FormModal>
  );
}
