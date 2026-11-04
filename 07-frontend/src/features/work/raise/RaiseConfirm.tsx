// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — step 3, *Confirm* (image 17)
//           and the *Result* (image 18).
// Rulings:  19 (one job per unit ticked — the jobs table is that list, read
//           back before the ONE press) · 16 (actions top right; a step flow
//           keeps its footer — so *Back · Raise N jobs ✓* stays in the frame's
//           footer and the result's two buttons sit at its foot, right).
// Rules:    B14 rules 4 (`Verb ✓` commits), 11 (a consequence box before the
//           commit), 20 (one table type), 21, 31 (an order NUMBER, never its
//           uuid), 33, 43, 44 · BR-WRK-027 (bulk results are per job, never a
//           boolean).
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { TableArray } from "@/components/TableArray";

import { RaiseFacts } from "./RaiseFacts";
import type { RaiseFact } from "./RaiseFacts";
import type { BulkRaiseOutcome } from "./raiseEndpoints";

/** One job the press will raise — a unit, or an asset on a unit. */
export interface RaiseJobLine {
  key: string;
  unit: string;
  asset: string | null;
  where: string | null;
  lastRead: string | null;
}

export function RaiseConfirmStep(props: {
  heading: string;
  facts: readonly RaiseFact[];
  jobs: readonly RaiseJobLine[];
  assetJobs: boolean;
  assigneeName: string | null;
}) {
  const { t } = useTranslation();
  const count = props.jobs.length;
  const numbered = props.jobs.map((job, index) => ({ ...job, n: index + 1 }));
  return (
    <div className="flex flex-col gap-4" data-raise-step="confirm">
      <RaiseFacts title={props.heading} facts={props.facts} name="raise-summary" />
      <div data-testid="raise-jobs">
        <TableArray
          readOnly
          title={t("work.raise.jobsTitle")}
          collection="raise-jobs"
          columns={[
            { key: "n", label: t("work.raise.col.number"), cell: (row) => <span className="tabular-nums">{row.n}</span> },
            { key: "unit", label: t("work.raise.col.unit"), cell: (row) => row.unit },
            ...(props.assetJobs
              ? [
                  { key: "asset", label: t("work.raise.col.asset"), cell: (row: (typeof numbered)[number]) => <span className="font-semibold">{row.asset ?? ""}</span> },
                  { key: "where", label: t("work.raise.col.where"), cell: (row: (typeof numbered)[number]) => row.where ?? "—" },
                  { key: "lastRead", label: t("work.raise.col.lastRead"), cell: (row: (typeof numbered)[number]) => row.lastRead ?? t("work.raise.neverRead") },
                ]
              : []),
          ]}
          rows={numbered}
          rowKey={(row) => row.key}
          emptyText={t("work.raise.jobsEmpty")}
        />
      </div>
      <ConsequenceBox
        tone="check"
        tag={t("work.newOrder.confirm.tag")}
        title={t("work.raise.effectTitle", { count })}
        body={[
          props.assetJobs ? t("work.raise.effectAssets") : t("work.raise.effectUnits"),
          props.assigneeName === null ? t("work.raise.effectQueued") : t("work.raise.effectTold", { name: props.assigneeName }),
        ].join(" ")}
        data-consequence="raise-jobs"
      />
    </div>
  );
}

export function RaiseResult(props: {
  outcome: BulkRaiseOutcome;
  lines: readonly RaiseJobLine[];
  /** A refusal's catalogue key, worded in the reader's language. */
  reasonText: (key: string) => string;
  onRaiseMore: () => void;
  onOpenOrders: () => void;
  /** `DEF-WRK-9658` — where a raised job's NUMBER opens: its order page. The
   *  number was plain text, unlike every other Work result. Required, so a
   *  caller cannot leave it dead (hard-won law 2). */
  orderHref: (orderNo: string) => string;
}) {
  const { t } = useTranslation();
  const rows = props.outcome.results.map((result, index) => ({
    key: result.id ?? `${result.unit_id ?? ""}${result.asset_id ?? ""}${index}`,
    result,
    line: props.lines[index],
  }));
  return (
    <div className="flex flex-col gap-4" data-raise-step="result">
      <TableArray
        readOnly
        title={t("work.raise.resultTitle", { count: props.outcome.done })}
        collection="raise-result"
        fact={props.outcome.failed > 0 ? t("work.raise.resultFailed", { count: props.outcome.failed }) : undefined}
        columns={[
          { key: "job", label: t("work.raise.col.job"), cell: (row) =>
              row.result.order_no ? (
                <InlineLinkTo
                  to={props.orderHref(row.result.order_no)}
                  className="whitespace-nowrap font-semibold"
                  data-raise-result-order={row.result.order_no}
                >
                  {row.result.order_no}
                </InlineLinkTo>
              ) : (
                "—"
              ),
          },
          { key: "unit", label: t("work.raise.col.unit"), cell: (row) => row.result.unit?.label ?? row.line?.unit ?? "" },
          { key: "asset", label: t("work.raise.col.asset"), cell: (row) => row.result.asset?.asset_no ?? row.line?.asset ?? "—" },
          {
            key: "result",
            label: t("work.raise.col.result"),
            cell: (row) =>
              row.result.ok ? (
                <StatusPill tone="success">{t("work.raise.resultRaised")}</StatusPill>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <StatusPill tone="danger">{t("work.raise.resultRefused")}</StatusPill>
                  {row.result.reason !== null ? props.reasonText(row.result.reason) : null}
                </span>
              ),
          },
        ]}
        rows={rows}
        rowKey={(row) => row.key}
        emptyText={t("work.raise.jobsEmpty")}
      />
      <div className="flex justify-end gap-2" data-raise-result-actions="">
          <Button variant="secondary" onClick={props.onRaiseMore}>
            {t("work.raise.raiseMore")}
          </Button>
          <Button variant="primary" onClick={props.onOpenOrders}>
            {t("work.raise.openOrders")}
          </Button>
      </div>
    </div>
  );
}
