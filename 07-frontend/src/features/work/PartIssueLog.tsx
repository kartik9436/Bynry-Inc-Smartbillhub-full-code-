// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4 (lane PARTS) — P3.11, the Issue log released.
// Defect:   DEF-WRK-9574 — *Issue log* sat greyed with *"Arrives with parts on
//           jobs."* over a live `GET /work/parts/issues` and a wrapper nothing
//           called (`listPartIssues`), after parts on jobs had landed.
// Story:    US-WRK-050 (who took what, and for which job — and NO running
//           balance, because no stock lawfully exists: OQ-WRK-1490 closed
//           2026-09-04 to option (a))
// Rules:    B14 rule 20 (one table type) · rule 16 (the pager footer) ·
//           rule 17 (an empty state) · rule 19 (this list's own search
//           prompt) · rule 21 (Tailwind; on route-b-migrated.txt) · rule 31
//           (no id is a visible value) · rule 43 (a component, not code inside
//           a page) · P1.18 (a quantity without four trailing zeros)
// Tests:    src/features/work/PartsPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NOT DRAWN.** Image 35 shows the Register segment only; the Issue log is
// built from the kit under B14 rule 44 — the same `DataTable`, the same
// search, the same pager as the register beside it — and it reads the server's
// own row (`apps/work/selectors._part_issue_row`) and nothing more.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";

import { quantityText } from "./orderPage/orderFormat";
import { listPartIssues } from "./workEndpoints";
import type { PartIssueRow } from "./workEndpoints";

/** The Issue log's own badge — one screen id per view (BR-SHL-035). */
export const WORK_PART_ISSUES_SCREEN = "WRK-10.issues";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The log's columns, exported so the test reads them without a DOM. */
export function partIssuesTableConfig(
  t: Translate,
  cells: { at: (row: PartIssueRow) => React.ReactNode },
): TableConfig<PartIssueRow> {
  return {
    screenId: WORK_PART_ISSUES_SCREEN,
    getRowId: (row) => row.id,
    // B14 rule 19 — what the server matches: part number, name and the job.
    searchFields: ["part_no", "part_name", "order_ref"],
    searchPlaceholder: "work.parts.issues.search",
    defaultSort: { sort: "at", dir: "desc" },
    columns: [
      { key: "at", label: t("work.parts.issues.col.at"), cell: cells.at },
      {
        key: "part_no",
        label: t("work.parts.col.partNo"),
        identity: true,
        cell: (row) => <span className="tabular-nums">{row.part_no}</span>,
      },
      { key: "part_name", label: t("work.parts.col.name"), cell: (row) => row.part_name },
      {
        key: "qty",
        label: t("work.parts.issues.col.qty"),
        numeric: true,
        // A NEGATIVE quantity is an issue and a positive one a return; the sign
        // IS the fact (`_part_issue_row`), so it is shown as the server sends it.
        cell: (row) => (
          <span className="tabular-nums whitespace-nowrap">
            {quantityText(row.qty)} {row.unit_of_measure}
          </span>
        ),
      },
      {
        key: "issued_to",
        label: t("work.parts.issues.col.issuedTo"),
        cell: (row) => (row.issued_to === "" ? <Dash /> : row.issued_to),
      },
      {
        key: "order_ref",
        label: t("work.parts.issues.col.job"),
        cell: (row) => (row.order_ref === "" ? <Dash /> : row.order_ref),
      },
      {
        key: "purpose",
        label: t("work.parts.issues.col.purpose"),
        cell: (row) => (row.purpose === "" ? <Dash /> : row.purpose),
      },
    ],
  };
}

export function PartIssueLog(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional({});
  const config = partIssuesTableConfig((key, params) => t(key, params), {
    at: (row) => (
      <DateCell value={row.at} timeZone={timeZone} dateFormat={dateFormat} withTime />
    ),
  });
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const query = useQuery({
    queryKey: ["work", "parts", "issues", state.q, state.page, state.per],
    queryFn: () => listPartIssues({ q: state.q, page: state.page, per: state.per }, client),
  });

  return (
    <div data-part-issue-log="" data-screen={WORK_PART_ISSUES_SCREEN}>
      <DataTable<PartIssueRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: t("work.parts.issues.loadFailed"), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: t("work.parts.issues.empty.title"),
          helper: t("work.parts.issues.empty.helper"),
        }}
      />
    </div>
  );
}

export default PartIssueLog;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.5 P3 · §5.8 P3.11 · DEF-WRK-9574 · US-WRK-050
// generated: 2026-10-04 by the CR-168 round-4 PARTS lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest PartsPage.test.tsx · routeBUtilities.test.ts · the cr168 parts walk
// exceptions: not drawn — built from the kit under B14 rule 44 (the drawing shows the Register segment only)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
