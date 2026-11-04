// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, Sent, the *Check report* tab
// Rules:    PO ruling 2026-09-30 (the Check is kept with the run as a read-only
//           report) · billing/0034 (the record is locked at Send) · NFR-3 ·
//           B14 rules 3, 21, 31, 33, 43
// Plan:     15-bulk-bill-run-build-plan.md A13 · F-report
// ───────────────────────────────────────────────────────
/**
 * THE CHECK REPORT — a SENT run's Check, exactly as it stood at Send.
 *
 * Reads `GET …/check/report`: the tiles, and every checked account with its
 * problems, ONE SERVER PAGE at a time (NFR-3), filtered by status on the
 * server. Nothing on it acts — the record is locked at Send (`billing/0034`),
 * so the report offers no answer, fix or re-check.
 *
 * DEF-BIL-8555 · clerk check A6: each account's ANSWERS ride with it — the
 * clerk's own (with the reason and an estimate's quantity) and the tag's
 * *Answer for all* it fell under — each with who gave it and on which day.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { checkReportKey, getCheckReport } from "@/api/bulkRunEndpoints";
import type { CheckReport as CheckReportData, CheckReportDecision } from "@/api/bulkRunEndpoints";
import type { Translator } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { PageSize } from "@/components/tableTypes";

import { FactCards, RUN_TABLE, TableScroll, count, day } from "./bulkRunShared";
import type { FactCardItem, RunFormat } from "./bulkRunShared";
import { choiceLabel, tagLabel } from "./CheckPanes";

const STATUSES = ["ready", "decision", "blocked", "quiet", "left_out"] as const;

const STATUS_TONE: Record<string, StatusTone> = {
  ready: "success",
  decision: "warning",
  blocked: "danger",
  quiet: "neutral",
  left_out: "neutral",
};

function statusLabel(status: string, t: Translator): string {
  return t(`billing.bulkRun.report.status.${status}`, { defaultValue: status });
}

/** One answer as a line: what, for which tag when it was for all, who, when. */
function answerLine(decision: CheckReportDecision, t: Translator, fmt: RunFormat | undefined): string {
  const answer = choiceLabel(decision.choice, t, decision.case);
  const what =
    decision.quantity !== null && decision.unit !== null
      ? `${answer} ${decision.quantity} ${decision.unit}`
      : answer;
  const parts = [
    decision.scope === "all"
      ? t("billing.bulkRun.report.forAll", { answer: what, tag: tagLabel({ code: decision.case }, t) })
      : what,
    decision.decided_by ?? t("billing.bulkRun.report.someone"),
    fmt === undefined ? decision.decided_at.slice(0, 10) : day(decision.decided_at, fmt),
  ];
  if (decision.reason !== null && decision.reason !== "") parts.push(decision.reason);
  return parts.join(" · ");
}

export function CheckReport(props: {
  runId: string;
  client: ApiClient;
  t: Translator;
  fmt?: RunFormat;
  /** Record links (PO 2026-10-19): where an account number opens (new tab). */
  accountHref?: (accountId: string) => string;
}) {
  const { t } = props;
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const reportQuery = useQuery({
    queryKey: checkReportKey(props.runId, page, per, status),
    queryFn: () => getCheckReport(props.runId, { page, per, status }, props.client),
    retry: false,
    placeholderData: (previous) => previous,
  });
  const report: CheckReportData | null = reportQuery.data ?? null;
  const labels = new Map<string, string>();
  for (const category of report?.categories ?? []) for (const tag of category.tags) labels.set(tag.code, tagLabel(tag, t));
  const tiles = report?.tiles ?? null;
  const items: FactCardItem[] = [
    { id: "accounts", label: t("billing.bulkRun.report.checked"), value: count(tiles?.accounts ?? null) },
    { id: "ready", label: t("billing.bulkRun.check.tile.ready"), value: count(tiles?.ready ?? null) },
    { id: "blocked", label: t("billing.bulkRun.check.tile.blocked"), value: count(tiles?.blocked ?? null) },
    { id: "decision", label: t("billing.bulkRun.check.tile.decision"), value: count(tiles?.decisions ?? null) },
  ];
  const rows = report?.accounts.results ?? [];
  const total = report?.accounts.count ?? 0;
  return (
    <Panel as="section" title={t("billing.bulkRun.report.title")} aria-label={t("billing.bulkRun.report.title")} data-check-report="">
      <p className="m-0 mt-1 text-base text-neutral-700">{t("billing.bulkRun.report.asAtSend")}</p>
      <div className="mt-3">
        <FactCards name="check-report" items={items} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3 border border-divider bg-surface px-3 py-2">
        <SegmentedControl
          name="check-report-status"
          label={t("billing.bulkRun.report.filterLabel")}
          segments={[
            { id: "", label: t("billing.bulkRun.report.status.all") },
            ...STATUSES.map((one) => ({ id: one, label: statusLabel(one, t) })),
          ]}
          active={status}
          onSelect={(id) => {
            setStatus(id);
            setPage(1);
          }}
        />
      </div>
      {rows.length === 0 ? (
        <p className="m-0 mt-3 text-base text-neutral-700" role="status">
          {t("billing.bulkRun.check.nobodyHere")}
        </p>
      ) : (
        <TableScroll>
          <PlainTable className={`${RUN_TABLE} mt-3`} data-run-table="check-report">
            <thead>
              <tr>
                <th scope="col">{t("billing.bulkRun.col.account")}</th>
                <th scope="col">{t("billing.bulkRun.col.status")}</th>
                <th scope="col">{t("billing.bulkRun.report.problems")}</th>
                <th scope="col">{t("billing.bulkRun.report.answers")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.account_id} data-report-row={row.status}>
                  <td className="font-heading font-semibold">
                    {props.accountHref !== undefined ? (
                      <a href={props.accountHref(row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                        {row.account_no}
                      </a>
                    ) : (
                      row.account_no
                    )}
                  </td>
                  <td>
                    <StatusPill tone={STATUS_TONE[row.status] ?? "neutral"}>{statusLabel(row.status, t)}</StatusPill>
                  </td>
                  <td>
                    {row.problems.length === 0
                      ? "—"
                      : row.problems
                          .map((problem) => labels.get(problem.code) ?? tagLabel({ code: problem.code }, t))
                          .filter((name, index, all) => all.indexOf(name) === index)
                          .join(" · ")}
                  </td>
                  <td>
                    {(row.decisions ?? []).length === 0 ? (
                      "—"
                    ) : (
                      <ul className="m-0 flex list-none flex-col gap-1 p-0">
                        {(row.decisions ?? []).map((decision) => (
                          <li key={`${decision.case}-${decision.scope}-${decision.decided_at}`} data-report-decision={decision.scope}>
                            {answerLine(decision, t, props.fmt)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </TableScroll>
      )}
      {total > 0 && (
        <ListPager total={total} page={page} per={per} onPage={setPage} onPer={(next) => { setPer(next); setPage(1); }} />
      )}
    </Panel>
  );
}
