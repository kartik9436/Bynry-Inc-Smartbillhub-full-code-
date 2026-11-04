// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.45 / ruling 27 (*"can also
//           view the orders that crew had worked on"*): a technician's Jobs
//           tab. Built from the IMAGE
//           `05-prototype/work-backoffice-2026-10-04/images/32-crews-one-technician-jobs.png`.
// Server:   `GET /work/technicians/{slug}/jobs?f.state=open|done&q=&page=&per=`
//           (lane SRV-3, `2.502.0`): every job the person holds or was ever
//           given, paged in SQL, newest first; each row is the dispatcher's own
//           row plus `still_holds`.
// Rules:    B14 rule 12/16 (the kit table's toolbar and pager) · 17 · 19 · 20 ·
//           31 (an order opens by its own page, the number is the link) · 33
// Tests:    src/features/work/crewsLane.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// Image 32's *CLOSED* column is drawn on every row: the dispatcher's row has
// carried `completed_at` since lane SRV-4 (CR-168 §20.3), which expired the
// hold lane CREWS wrote here — a column shown only when a row happened to
// carry the key is gone with it.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { useTenantRegional } from "@/components/TenantRegional";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";

import { workOrderDetailPath } from "./OrderDetailPage";
import { dispatchStateTone, workOrderOutcomeTone, workOrderStateTone } from "./OrdersPage";
import { listTechnicianJobs } from "./crewsEndpoints";
import type { TechnicianJobRow, TechnicianJobState } from "./crewsEndpoints";
import { WhereCell } from "./WhereCell";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const JOB_STATES: readonly TechnicianJobState[] = ["all", "open", "done"];

function WhenCell(props: { value: string | null | undefined }) {
  const regional = useTenantRegional();
  if (props.value === null || props.value === undefined) return <Dash />;
  if (regional === null) return <span className="tabular-nums">{props.value.slice(0, 10)}</span>;
  return <DateCell value={props.value} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />;
}

/** Image 32's columns, in the drawing's order. */
export function technicianJobsConfig(
  t: Translate,
  cells: { order: (row: TechnicianJobRow) => React.ReactNode },
): TableConfig<TechnicianJobRow> {
  return {
    screenId: "WRK-08",
    getRowId: (row) => row.id,
    searchFields: ["order_no", "premise"],
    searchPlaceholder: "work.technician.jobs.search",
    defaultSort: { sort: "raised", dir: "desc" },
    columns: [
      { key: "order_no", label: t("work.technician.jobs.col.order"), identity: true, cell: cells.order },
      { key: "type", label: t("work.technician.jobs.col.type"), cell: (row) => <span>{row.type}</span> },
      {
        key: "address",
        label: t("work.technician.jobs.col.address"),
        cell: (row) => <WhereCell premise={row.premise} storedAt={row.stored_at} />,
      },
      {
        key: "status",
        label: t("work.technician.jobs.col.status"),
        cell: (row) => (
          <span className="inline-flex flex-wrap items-center gap-1">
            {/* A finished job reads *Completed* in the state's own green, as
                image 32 draws it; anything still out reads where it is. */}
            {row.state === "completed" ? (
              <StatusPill tone={workOrderStateTone(row.state)}>{t("work.orders.state.completed")}</StatusPill>
            ) : (
              <StatusPill tone={dispatchStateTone(row.dispatch_state)}>
                {t(`work.orders.dispatch.${row.dispatch_state}`)}
              </StatusPill>
            )}
            {row.state === "completed" && (row.accepted ?? null) === null && (
              <StatusPill tone="warning">{t("work.technician.jobs.awaitingApproval")}</StatusPill>
            )}
            {row.state === "completed" && (row.accepted ?? null) !== null && (
              <StatusPill tone="success">{t("work.technician.jobs.accepted")}</StatusPill>
            )}
            {!row.still_holds && <StatusPill tone="muted">{t("work.technician.jobs.movedOn")}</StatusPill>}
          </span>
        ),
      },
      {
        key: "due",
        label: t("work.technician.jobs.col.due"),
        cell: (row) => <WhenCell value={row.due_at ?? row.sla?.due_at ?? null} />,
      },
      {
        key: "closed",
        label: t("work.technician.jobs.col.closed"),
        cell: (row) => <WhenCell value={row.completed_at} />,
      },
      {
        key: "outcome",
        label: t("work.technician.jobs.col.outcome"),
        cell: (row) =>
          row.outcome === null ? (
            <Dash />
          ) : (
            <StatusPill tone={workOrderOutcomeTone(row.outcome)}>{t(`work.orders.outcome.${row.outcome}`)}</StatusPill>
          ),
      },
    ],
  };
}

export function TechnicianJobsTab(props: { client: ApiClient; slug: string }) {
  const { t } = useTranslation();
  const params = useParams();
  const tenant = params.tenant ?? "";
  const translate: Translate = (key, values) => t(key, values);
  const [jobState, setJobState] = useState<TechnicianJobState>("all");
  const [state, setState] = useState<TableRequestState>(() => ({
    ...defaultRequestState(technicianJobsConfig(translate, { order: () => null })),
  }));

  const query = useQuery({
    queryKey: ["work", "technician", props.slug, "jobs", jobState, state.q, state.page, state.per],
    queryFn: () =>
      listTechnicianJobs(props.slug, { state: jobState, q: state.q, page: state.page, per: state.per }, props.client),
  });
  const rows = query.data?.results ?? [];

  const config = useMemo(
    () =>
      technicianJobsConfig(
        translate,
        {
          order: (row) => (
            <InlineLinkTo to={workOrderDetailPath(tenant, row.id)}>{row.order_no ?? ""}</InlineLinkTo>
          ),
        },
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, tenant],
  );

  return (
    <div data-technician-jobs="">
      <DataTable<TechnicianJobRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={query.data?.count ?? null}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: t("work.technician.jobs.failed"), onRetry: () => void query.refetch() }
            : null
        }
        filterBarSlot={
          <div className="flex flex-1 items-center justify-between gap-3">
            <SegmentedControl
              name="technician-jobs-state"
              label={t("work.technician.jobs.which")}
              active={jobState}
              onSelect={(next) => {
                setJobState(next as TechnicianJobState);
                setState((now) => ({ ...now, page: 1 }));
              }}
              segments={JOB_STATES.map((id) => ({ id, label: t(`work.technician.jobs.state.${id}`) }))}
            />
            {query.data !== undefined && (
              <strong className="text-sm tabular-nums" data-jobs-count="">
                {t("work.technician.jobs.count", { count: query.data.count })}
              </strong>
            )}
          </div>
        }
        empty={{
          title: t("work.technician.jobs.empty"),
          helper: t("work.technician.jobs.emptyHelper"),
        }}
      />
    </div>
  );
}

export default TechnicianJobsTab;
