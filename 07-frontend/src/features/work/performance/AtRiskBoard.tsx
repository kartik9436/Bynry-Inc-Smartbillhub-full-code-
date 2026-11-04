// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane PERFORMANCE — P5.3, the at-risk board:
//           *"What breaks today, before it breaks. A dispatcher opens it
//           first."* (blueprint §02, capability D19). NAMED, NOT DRAWN — built
//           from the component kit under B14 rule 44 in image 65's style, and
//           put to the PO as a photograph.
// Reads:    `GET /work/at-risk?page=&per=` (lane SRV-4, CR-168 §20.2) — open
//           jobs whose promise, held time added back, falls inside the
//           tenant's warning window or has passed, SOONEST FIRST, paged in SQL.
// Rules:    NFR-3 (the server pages; this screen never cuts a page) · NFR-5 ·
//           B14 rules 2, 17, 20 (the kit `DataTable`), 21, 31 (no uuid on
//           screen), 33 (a fact ≤ 6 words), 37, 44.
// Tests:    src/features/work/performance/cr168Performance.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NO TILES, AND THAT IS P5.1's LESSON APPLIED HERE.** The read serves ONE
// count — the jobs in the window — and nothing splits it into *late* and *due
// soon* over the whole set. Tiles counted from the page in hand would describe
// a page and not the board, which is exactly the headline-disagrees-with-its-
// rows defect image 65 was drawn to remove (`DEF-WRK-9586`). The count and the
// window go in the panel's fact line instead, both from the server.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { formatDate } from "@/components/DateCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_ORDERS_ROUTE } from "../WorkShell";
import { fetchAtRisk, spanParts } from "./performanceEndpoints";
import type { AtRiskRow } from "./performanceEndpoints";

/** `WRK-25`, minted (CR-168-BRC10 §30). The board was a view of the
 *  Performance tab and wore its `WRK-16` until the PO's answer (1) of
 *  2026-10-05 made it a tab of its own next to Orders (`AtRiskPage`). */
export const AT_RISK_SCREEN = "WRK-25";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** *2 d 3 h* / *5 h 20 m* / *40 m* — the largest two units that are not zero. */
export function spanText(t: Translate, minutes: number): string {
  const { d, h, m } = spanParts(minutes);
  if (d > 0) return t("work.atRisk.span.dh", { d, h });
  if (h > 0) return t("work.atRisk.span.hm", { h, m });
  return t("work.atRisk.span.m", { m });
}

/** The count-down cell: *Late 5 h 20 m* in the danger tone, *3 h left* in the
 *  warning tone. The SERVER decided `overdue`; this only words it. */
export function PromiseLeft(props: { row: AtRiskRow; t: Translate }) {
  const { promise } = props.row;
  return promise.overdue ? (
    <span data-promise="late">
      <StatusPill tone="danger">{props.t("work.atRisk.late", { span: spanText(props.t, promise.minutes_left) })}</StatusPill>
    </span>
  ) : (
    <span data-promise="left">
      <StatusPill tone="warning">{props.t("work.atRisk.left", { span: spanText(props.t, promise.minutes_left) })}</StatusPill>
    </span>
  );
}

export function atRiskTableConfig(
  t: Translate,
  cells: {
    order: (row: AtRiskRow) => React.ReactNode;
    promised: (row: AtRiskRow) => React.ReactNode;
  },
): TableConfig<AtRiskRow> {
  return {
    screenId: AT_RISK_SCREEN,
    getRowId: (row) => row.id,
    // The server fixes the order — soonest promise first — and declares no
    // sort; no header offers one (B14 rule 19's dead-control mirror).
    defaultSort: { sort: "promise", dir: "asc" },
    columns: [
      { key: "order", label: t("work.atRisk.col.order"), identity: true, cell: cells.order },
      { key: "type", label: t("work.atRisk.col.type"), cell: (row) => <span>{row.type}</span> },
      {
        key: "where",
        label: t("work.atRisk.col.where"),
        cell: (row) => <span>{row.premise?.address ?? "—"}</span>,
      },
      {
        key: "who",
        label: t("work.atRisk.col.who"),
        cell: (row) =>
          row.technician === null ? (
            <StatusPill tone="danger">{t("work.atRisk.nobody")}</StatusPill>
          ) : (
            <span>{row.technician.name}</span>
          ),
      },
      { key: "promised", label: t("work.atRisk.col.promised"), cell: cells.promised },
      {
        key: "left",
        label: t("work.atRisk.col.left"),
        cell: (row) => <PromiseLeft row={row} t={t} />,
      },
    ],
  };
}

/** P5.3 — every job about to break its promise, or already past it. */
export function AtRiskBoard(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional({});
  const translate: Translate = (key, params) => t(key, params);

  const config = useMemo(
    () =>
      atRiskTableConfig(translate, {
        order: (row) =>
          row.order_no === null ? (
            <span>—</span>
          ) : (
            <InlineLinkTo to={tenantPath(`${WORK_ORDERS_ROUTE}/${row.order_no}`)} data-at-risk-order={row.order_no}>
              {row.order_no}
            </InlineLinkTo>
          ),
        promised: (row) => (
          <span className="tabular-nums" data-promise-due="">
            {formatDate(row.promise.due_at, timeZone, dateFormat, true)}
          </span>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: ["work", "at-risk", state.page, state.per],
    queryFn: () => fetchAtRisk({ page: state.page, per: state.per }, client),
  });
  const data = query.data;

  return (
    <div data-at-risk-board="">
      {data !== undefined && (
        <p className="mb-3 text-base text-neutral-700" data-at-risk-fact="">
          {data.window_hours === null
            ? t("work.atRisk.factPast", { count: data.count })
            : t("work.atRisk.fact", { count: data.count, hours: data.window_hours })}
        </p>
      )}
      <DataTable<AtRiskRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={data?.results ?? []}
        totalRows={data?.count ?? null}
        loading={query.isPending}
        error={query.isError ? { reason: t("work.atRisk.loadFailed"), onRetry: () => void query.refetch() } : null}
        empty={{
          title: t("work.atRisk.empty.title"),
          helper: t("work.atRisk.empty.helper"),
        }}
      />
    </div>
  );
}
