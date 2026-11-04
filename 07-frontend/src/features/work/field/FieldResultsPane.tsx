// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-055 (EP-WRK-11) — the office acceptance queue: finished
//           jobs with what the field SAID about them, reviewed, then accepted,
//           reopened or followed on (Walkthrough §4: *"Review and accept
//           completed work; reopen or raise a follow-on; see what a partial
//           left undone"*; E2E-04, -05, -06, -17, -18)
// Server:   GET work/acceptance-queue?outcome=&accepted=false&page=&per= ·
//           POST work-orders/{id}/accept (the ONE acceptance every door uses)
//           · POST work-orders/{id}/come-back
// Rules:    BR-FLD-00004 (four outcomes) · BR-WRK-007 (the queue is
//           finished-and-unaccepted) · NFR-3 (paged in SQL, no cap) ·
//           B14 rules 15 (row actions are icons, two then `…`) · 16 (the
//           shared pager footer) · 17 (an empty state) · 20 (one table type) ·
//           21 (Tailwind only; on route-b-migrated.txt) · 31 (no id shown) ·
//           33 (labels ≤ 3 words)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS NOT `Work-009` AND DOES NOT REPLACE IT.** `Work-009` (*Approvals*)
// is a DRAWN screen with seven drawn columns, and rule 41 builds a drawing
// exactly — so the outcome, the reason, the blocker, the steps left and the
// cost could not be added to it without breaking the drawing. They are this
// pane's columns instead. Both read the same population (finished, nobody has
// accepted); an Accept pressed on either clears the row from both.
//
// ⚠ **THE OUTCOME FILTER IS THE KIT'S `+ Filter`, WITH THE SERVER'S TALLY AS
// ITS COUNTS.** `tally` counts every outcome over the WHOLE queue, never the
// page (`field_outcomes.office_queue`), so `Partly done · 2` is true however
// far a clerk has paged.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { CommitIcon, EyeIcon, LinkIcon, RollBackIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { RowAction, RowActionLink, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { useToast } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { acceptWorkOrder } from "@/features/customers/newConnectEndpoints";
import { useTenantPath } from "@/routing/tenantPath";

import { FollowOnDialog, ReopenDialog } from "./ComeBackDialogs";
import { FIELD_OUTCOME_WORDS, listAcceptanceQueue, orderAddress } from "./fieldDeskEndpoints";
import type { AcceptanceRow, AcceptanceTally } from "./fieldDeskEndpoints";
import { FieldBlocker, FieldOutcomePill, FieldReason } from "./fieldWords";

/** The tenant currency a job's cost is shown in — the same constant, and the
 *  same reasoning, as `PerformancePage` and the parts register. */
const COST_CURRENCY = "USD";

type Translate = (key: string, params?: Record<string, unknown>) => string;

export interface ResultsCells {
  order: (row: AcceptanceRow) => React.ReactNode;
  actions: (row: AcceptanceRow) => React.ReactNode;
}

/**
 * The pane's table — ORDER · TECHNICIAN · OUTCOME · REASON · BLOCKED BY ·
 * STEPS LEFT · PHOTOS · COST · WAITING · actions. Exported so a test reads the
 * columns and the filter without rendering.
 */
export function fieldResultsTableConfig(
  t: Translate,
  tally: AcceptanceTally | undefined,
  cells: ResultsCells,
): TableConfig<AcceptanceRow> {
  return {
    screenId: "WRK-26",
    getRowId: (row) => row.id,
    // No search: the server declares no `q` on this route, and an empty
    // `searchFields` would draw a box that can never change a row.
    defaultSort: { sort: "completed_at", dir: "asc" },
    filters: [
      {
        name: "outcome",
        label: t("work.field.col.outcome"),
        options: FIELD_OUTCOME_WORDS.map((word) => ({ value: word, label: t(`work.field.outcome.${word}`) })),
        counts: tally === undefined ? undefined : Object.fromEntries(FIELD_OUTCOME_WORDS.map((w) => [w, tally[w] ?? 0])),
      },
    ],
    columns: [
      { key: "order_no", label: t("work.field.col.order"), identity: true, cell: cells.order },
      {
        key: "technician",
        label: t("work.field.col.technician"),
        cell: (row) => (row.technician === null ? <Dash /> : row.technician),
      },
      { key: "outcome", label: t("work.field.col.outcome"), cell: (row) => <FieldOutcomePill word={row.word} /> },
      { key: "reason", label: t("work.field.col.reason"), cell: (row) => <FieldReason record={row} /> },
      { key: "blocker", label: t("work.field.col.blocker"), cell: (row) => <FieldBlocker blocker={row.blocker} /> },
      {
        key: "steps_left",
        label: t("work.field.col.steps"),
        cell: (row) =>
          row.steps_total === 0 ? (
            <Dash />
          ) : (
            <span className="tabular-nums" data-steps-left={row.steps_total - row.steps_done}>
              {t("work.field.stepsOf", { left: row.steps_total - row.steps_done, total: row.steps_total })}
            </span>
          ),
      },
      {
        key: "photographs",
        label: t("work.field.col.photos"),
        cell: (row) => <span className="tabular-nums">{row.photographs}</span>,
      },
      {
        key: "cost",
        label: t("work.field.col.cost"),
        cell: (row) => <MoneyCell amount={row.cost.total} currency={COST_CURRENCY} />,
      },
      {
        key: "waiting_days",
        label: t("work.field.col.waiting"),
        cell: (row) =>
          row.waiting_days === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums">{t("work.approvals.waiting.days", { count: row.waiting_days })}</span>
          ),
      },
      { key: "actions", label: t("work.field.col.actions"), cell: cells.actions },
    ],
  };
}

const EMPTY_CELLS: ResultsCells = { order: () => null, actions: () => null };

type Asking =
  | { act: "accept"; row: AcceptanceRow }
  | { act: "reopen"; row: AcceptanceRow }
  | { act: "follow_on"; row: AcceptanceRow }
  | null;

export function FieldResultsPane(props: { client: ApiClient }) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(fieldResultsTableConfig(translate, undefined, EMPTY_CELLS)),
  );
  const [asking, setAsking] = useState<Asking>(null);
  const [working, setWorking] = useState(false);
  const outcome = state.filters.outcome ?? "";

  const listQuery = useQuery({
    queryKey: ["work", "field", "results", state.page, state.per, outcome],
    queryFn: () => listAcceptanceQueue({ outcome, page: state.page, per: state.per }, props.client),
  });
  const rows = useMemo(() => listQuery.data?.rows ?? [], [listQuery.data]);

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["work"] });
  }

  async function accept(row: AcceptanceRow) {
    setWorking(true);
    try {
      await acceptWorkOrder(row.id, props.client);
      toast(t("work.field.accepted", { order: row.order_no ?? "" }));
      refresh();
    } catch (error) {
      toast(refusalText(translate, error));
    } finally {
      setWorking(false);
      setAsking(null);
    }
  }

  const config = fieldResultsTableConfig(translate, listQuery.data?.body.tally, {
    order: (row) => (
      <span className="flex flex-col">
        <span className="tabular-nums">{row.order_no ?? ""}</span>
        {row.type !== null && <span className="text-sm text-neutral-600">{row.type}</span>}
      </span>
    ),
    // B14 rule 15 — two icons visible (👁 then ✓), the rest behind `…`.
    actions: (row) => (
      <RowActions>
        <RowActionLink
          label={t("work.field.open", { order: row.order_no ?? "" })}
          icon={<EyeIcon />}
          to={tenantPath(orderAddress(row.id))}
        />
        <RowAction
          label={t("work.field.accept", { order: row.order_no ?? "" })}
          icon={<CommitIcon />}
          testId="field-accept"
          onClick={() => setAsking({ act: "accept", row })}
        />
        <RowActionsMore label={t("work.field.more", { order: row.order_no ?? "" })}>
          <RowMenuAction
            label={t("work.field.reopen")}
            icon={<RollBackIcon />}
            testId="field-reopen"
            onClick={() => setAsking({ act: "reopen", row })}
          />
          <RowMenuAction
            label={t("work.field.followOn")}
            icon={<LinkIcon />}
            testId="field-follow-on"
            onClick={() => setAsking({ act: "follow_on", row })}
          />
        </RowActionsMore>
      </RowActions>
    ),
  });

  return (
    <div data-field-pane="results">
      <DataTable<AcceptanceRow>
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
        empty={{
          title: t("work.field.resultsEmpty.title"),
          helper: t("work.field.resultsEmpty.helper"),
        }}
      />

      {asking?.act === "accept" && (
        <ConfirmDialog
          title={t("work.approvals.acceptTitle", { order: asking.row.order_no ?? "" })}
          consequence={t("work.field.acceptConsequence")}
          confirmLabel={t("work.approvals.acceptConfirm")}
          cancelLabel={t("work.approvals.keepWaiting")}
          working={working}
          onConfirm={() => void accept(asking.row)}
          onCancel={() => setAsking(null)}
        />
      )}
      {asking?.act === "reopen" && (
        <ReopenDialog
          orderId={asking.row.id}
          orderNo={asking.row.order_no ?? ""}
          client={props.client}
          onClose={() => setAsking(null)}
          onDone={() => {
            toast(t("work.field.reopenDone", { order: asking.row.order_no ?? "" }));
            setAsking(null);
            refresh();
          }}
        />
      )}
      {asking?.act === "follow_on" && (
        <FollowOnDialog
          orderId={asking.row.id}
          orderNo={asking.row.order_no ?? ""}
          client={props.client}
          onClose={() => setAsking(null)}
          onDone={(answer) => {
            toast(t("work.field.followOnDone", { order: answer.follow_on?.order_no ?? "" }));
            setAsking(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}
