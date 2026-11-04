// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-057 (EP-WRK-11) — the dispatcher's alerts: what was sent
//           to which handset, whether it was answered, and which emergencies
//           went five minutes unanswered (R28's list — *dispatch is told*)
// Server:   GET work/field-alerts?state=all|awaiting_ack|overdue&page=&per=
//           (`apps/work/field_alerts.office_alerts`)
// Rules:    BR-FLD-00028 (an emergency must be answered; five minutes and
//           dispatch is told) · BR-FLD-00029 (dispatch messages only) ·
//           NFR-3 (paged, no cap) · B14 rules 16 · 17 · 20 · 21 · 31 · 33
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ANSWER COLUMN IS DERIVED FROM THE SERVER'S OWN FACTS, NEVER FROM THIS
// BROWSER'S CLOCK.** `late` is computed on the server against its own `now`
// (E2E-23: a phone's or a PC's clock may be wrong), so *Overdue* here is the
// server's word for it and a slow PC cannot make an alert look answered in
// time.
//
// ⚠ **THERE IS NO "SEND" BUTTON ON THIS LIST, DELIBERATELY.** Every alert but a
// dispatch message names an ORDER (`field_alerts.send_alert`), so the door is
// *Send alert…* on the order itself, where the order and its technician are
// already known (`SendAlertDialog`). The empty state says so.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { DateCell } from "@/components/DateCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { FIELD_ALERT_STATES, listFieldAlerts, orderAddress } from "./fieldDeskEndpoints";
import type { FieldAlertRow } from "./fieldDeskEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

export type AlertAnswer = "answered" | "answeredLate" | "overdue" | "waiting" | "noAnswer";

/** One alert's answer, in one word, from the server's facts alone. */
export function alertAnswer(row: FieldAlertRow): AlertAnswer {
  if (!row.ack_required) return "noAnswer";
  if (row.acknowledged_at !== null) return row.late ? "answeredLate" : "answered";
  return row.late ? "overdue" : "waiting";
}

const ANSWER_TONE: Record<AlertAnswer, StatusTone> = {
  answered: "success",
  answeredLate: "warning",
  overdue: "danger",
  waiting: "warning",
  noAnswer: "muted",
};

export interface AlertCells {
  order: (row: FieldAlertRow) => React.ReactNode;
  sent: (row: FieldAlertRow) => React.ReactNode;
}

/** ALERT · ORDER · TECHNICIAN · SENT · ANSWER · MESSAGE. */
export function fieldAlertsTableConfig(t: Translate, cells: AlertCells): TableConfig<FieldAlertRow> {
  return {
    screenId: "WRK-26",
    getRowId: (row) => row.id,
    defaultSort: { sort: "sent_at", dir: "desc" },
    filters: [
      {
        name: "state",
        label: t("work.field.col.answer"),
        options: FIELD_ALERT_STATES.map((s) => ({
          value: s,
          label: t(s === "overdue" ? "work.field.answer.overdue" : "work.field.answer.waiting"),
        })),
      },
    ],
    columns: [
      {
        key: "kind",
        label: t("work.field.col.alert"),
        identity: true,
        cell: (row) => <span data-alert-kind={row.kind}>{t(`work.field.kind.${row.kind}`)}</span>,
      },
      { key: "order_no", label: t("work.field.col.order"), cell: cells.order },
      {
        key: "technician",
        label: t("work.field.col.technician"),
        cell: (row) => (row.technician === null ? <Dash /> : row.technician),
      },
      { key: "sent_at", label: t("work.field.col.sent"), cell: cells.sent },
      {
        key: "answer",
        label: t("work.field.col.answer"),
        cell: (row) => {
          const answer = alertAnswer(row);
          return (
            <span className="inline-flex flex-wrap items-center gap-1" data-alert-answer={answer}>
              <StatusPill tone={ANSWER_TONE[answer]}>{t(`work.field.answer.${answer}`)}</StatusPill>
              {row.dispatch_told && <StatusPill tone="danger">{t("work.field.dispatchTold")}</StatusPill>}
            </span>
          );
        },
      },
      {
        key: "message",
        label: t("work.field.col.message"),
        cell: (row) => (row.message === null || row.message === "" ? <Dash /> : row.message),
      },
    ],
  };
}

const EMPTY_CELLS: AlertCells = { order: () => null, sent: () => null };

export function FieldAlertsPane(props: { client: ApiClient }) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional({});
  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(fieldAlertsTableConfig(translate, EMPTY_CELLS)),
  );
  const alertState = state.filters.state ?? "";

  const listQuery = useQuery({
    queryKey: ["work", "field", "alerts", state.page, state.per, alertState],
    queryFn: () => listFieldAlerts({ state: alertState, page: state.page, per: state.per }, props.client),
  });
  const rows = useMemo(() => listQuery.data?.rows ?? [], [listQuery.data]);

  const config = fieldAlertsTableConfig(translate, {
    order: (row) =>
      row.order_no === null || row.work_order_id === null ? (
        <Dash />
      ) : (
        <InlineLinkTo to={tenantPath(orderAddress(row.work_order_id))}>
          {row.order_no}
        </InlineLinkTo>
      ),
    sent: (row) => <DateCell value={row.sent_at} timeZone={timeZone} dateFormat={dateFormat} withTime />,
  });

  return (
    <div data-field-pane="alerts">
      <DataTable<FieldAlertRow>
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
        empty={{ title: t("work.field.alertsEmpty.title"), helper: t("work.field.alertsEmpty.helper") }}
      />
    </div>
  );
}
