// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax details OVERVIEW (images 18,
//           22, 23): four tiles, the over-20% band, *Rate and scope* with its
//           versions table, *On the bill and filing*.
// Defect:   DEF-RAT-9272 P32 (Not worked out yet band) · P33 (a sentence under
//           every section) · P34 (150% with no warning) · P37 (filing typed in
//           on details) · P39/P40 (versions table on Overview; no Rate history
//           tab) · P41 · P42 · P43 (filing as typed fractions)
// Rules:    PO round 6 (versions table + "See every change in Audit") · README
//           points 2, 3, 7 · B14 rule 31 · rule 33 · rule 37 · BR-RAT-087
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getTaxVersions } from "@/api/endpoints";
import type { TaxVersionRow } from "@/api/endpoints";
import type { TaxDetailRow } from "@/api/taxDetailEndpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { formatDate } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import { TaxStatusCell } from "../taxListParts";
import { SECTION_HEADING } from "../taxForm/taxFormShared";
import {
  DASH,
  EXAMPLE_BILL,
  billAndFilingFacts,
  overTwentyEffect,
  rateAndScopeFacts,
  taxIsOverTwenty,
  taxRateFigure,
  taxRateUnitKey,
} from "./taxDetailModel";
import type { TaxRegional, Translator } from "./taxDetailModel";

/** A versions row as 2.472.0 serves it: `version` and `amount_display` added
 *  (§9 additions, task 3). Optional, so an older row renders a dash. */
export type TaxVersionLine = TaxVersionRow & {
  readonly version?: number | null;
  readonly amount_display?: string | null;
};

/**
 * The four tiles — Rate, Premises, Plans, Collected (images 18, 22, 23).
 *
 * ⚠ **COLLECTED HAS NO READ, AND THE TILE SAYS SO IN FOUR WORDS RATHER THAN
 * SHOWING A FIGURE.** Nothing on the server totals what one tax collected in a
 * month (searched: no rating, billing or ledger read does). The drawing's
 * `$0.00` and `$3,015.60` are illustrations (B14 rule 37); a `$0.00` here
 * would be a confident wrong number, and P32's *Not worked out yet* band was
 * the old screen's way of saying the same thing at four times the length.
 */
export function taxTiles(row: TaxDetailRow, t: Translator): KpiTile[] {
  const reached = row.premises_reached;
  const total = row.premises_total;
  return [
    {
      id: "rate",
      label: t("rating.taxDetail.kpi.rate"),
      value: taxRateFigure(row, t),
      detail: t(taxRateUnitKey(row)),
    },
    {
      id: "premises",
      label: t("rating.taxDetail.kpi.premises"),
      value: reached === null || reached === undefined ? DASH : reached,
      detail:
        total === null || total === undefined ? undefined : t("rating.taxDetail.kpi.ofTotal", { total }),
    },
    {
      id: "plans",
      label: t("rating.taxDetail.kpi.plans"),
      value: row.used_by_plans,
      detail: t("rating.taxDetail.kpi.usingIt"),
    },
    {
      id: "collected",
      label: t("rating.taxDetail.kpi.collected"),
      value: DASH,
      detail: t("rating.taxDetail.kpi.collectedNotCounted"),
    },
  ];
}

/** *150% is high. On a $60.00 bill it adds $90.00. Fix the rate* (image 18). */
export function OverTwentyBand(props: { row: TaxDetailRow; fixTo: string; t: Translator }) {
  const { row, t } = props;
  if (!taxIsOverTwenty(row)) return null;
  const effect = overTwentyEffect(row);
  return (
    <p className="m-0 bg-warning-100 px-3 py-3 text-base text-warning-700" role="status" data-tax-over-20="">
      <strong className="font-semibold">{t("rating.taxDetail.overTwenty.high", { rate: taxRateFigure(row, t) })}</strong>{" "}
      {effect !== null && t("rating.taxForm.rateHighEffect", { bill: EXAMPLE_BILL, amount: effect })}{" "}
      <InlineLinkTo to={props.fixTo} className="font-semibold" data-tax-fix-rate="">
        {t("rating.taxDetail.overTwenty.fix")}
      </InlineLinkTo>
    </p>
  );
}

/** The small versions table at the foot of *Rate and scope* (PO round 6). */
export function TaxVersionsTable(props: {
  taxId: string;
  client: ApiClient;
  regional: TaxRegional;
  t: Translator;
}) {
  const { t, regional } = props;
  const query = useQuery({
    queryKey: ["taxes", props.taxId, "versions"],
    queryFn: () => getTaxVersions(props.taxId, props.client) as Promise<TaxVersionLine[]>,
    enabled: props.taxId !== "",
    staleTime: REFERENCE_STALE_MS,
  });
  if (query.isPending) return <LoadingSkeleton variant="table" />;
  if (query.isError) return <Note>{t("rating.taxDetail.versions.failed")}</Note>;
  const rows: readonly TaxVersionLine[] = query.data ?? [];
  const day = (value: string | null, openEnd: boolean) =>
    value === null
      ? openEnd
        ? t("rating.taxes.list.noEnd")
        : DASH
      : formatDate(value, regional.timeZone, regional.dateFormat);
  return (
    <div className="border border-divider" data-tax-versions="">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("rating.taxes.list.col.version")}</th>
            <th scope="col" className="!text-right">
              {t("rating.taxForm.field.rate")}
            </th>
            <th scope="col">{t("rating.taxDetail.versions.dates")}</th>
            <th scope="col">{t("rating.taxDetail.versions.status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            // B14 rule 31 — the id is the key, never a cell.
            <tr key={row.id} data-version-current={row.is_current ? "" : undefined}>
              <td>{row.version === null || row.version === undefined ? DASH : t("rating.taxes.list.version", { n: row.version })}</td>
              <td className="!text-right font-semibold tabular-nums">
                {row.amount_display ?? row.rate_display ?? DASH}
              </td>
              <td className="tabular-nums">
                {day(row.effective_from, false)} – {day(row.effective_to, true)}
              </td>
              <td>
                <TaxStatusCell status={row.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

export function TaxOverviewTab(props: {
  row: TaxDetailRow;
  client: ApiClient;
  regional: TaxRegional;
  fixTo: string;
  auditTo: string;
  t: Translator;
}) {
  const { row, t } = props;
  return (
    <div className="flex flex-col gap-5" data-tax-overview="">
      <div className="flex flex-col">
        <KPIStrip kpis={taxTiles(row, t)} />
        <OverTwentyBand row={row} fixTo={props.fixTo} t={t} />
      </div>

      <Panel as="section" aria-labelledby="tax-detail-rate-scope">
        <h2 id="tax-detail-rate-scope" className={SECTION_HEADING}>
          {t("rating.taxDetail.section.rateScope")}
        </h2>
        <FactBlock name="rate-scope" variant="strip" columns={3} facts={rateAndScopeFacts(row, t, props.regional)} />
        <div className="mt-5">
          <TaxVersionsTable taxId={row.id} client={props.client} regional={props.regional} t={t} />
        </div>
        <div className="mt-4">
          <InlineLinkTo className="font-semibold" to={props.auditTo} data-tax-see-audit="">
            {t("rating.taxDetail.seeAudit")}
          </InlineLinkTo>
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="tax-detail-bill-filing">
        <h2 id="tax-detail-bill-filing" className={SECTION_HEADING}>
          {t("rating.taxDetail.section.billFiling")}
        </h2>
        <FactBlock name="bill-filing" variant="strip" columns={3} facts={billAndFilingFacts(row, t)} />
      </Panel>
    </div>
  );
}
