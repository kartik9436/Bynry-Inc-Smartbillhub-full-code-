// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount details OVERVIEW
//           (images 19, 24, 26): four tiles, *Details*, *Eligibility*, the
//           versions table and *See every change in Audit*.
// Defect:   DEF-RAT-9291 D23 (tiles on every tab) · D24 (Type tile on three
//           lines) · D25 (75 · 75 units on a plan carrying it) · D26
//           (rationale under Who qualifies) · D27 (money without $) · D28 (red
//           kickers over grey labels) · D33 (entered values never shown) · D34
//           (Effective to under Who qualifies)
// Rules:    README point 6 (every entered value shown) · B14 rules 31, 33, 37 ·
//           BR-RAT-087 (the server's display strings, `$` included)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getDiscountVersionLines } from "@/api/discountDetailEndpoints";
import type { DiscountDetailRow, DiscountVersionLine } from "@/api/discountDetailEndpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { todayInZone } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import { DiscountStatusCell } from "../discountListParts";
import { SECTION_HEADING } from "../discountForm/discountFormShared";
import { DASH, detailsFacts, eligibilityFacts, tileFigures, versionStatus, windowText } from "./discountDetailModel";
import type { DiscountRegional, Translator } from "./discountDetailModel";

export function discountVersionsQueryKey(discountId: string) {
  return ["discounts", discountId, "versions"] as const;
}

/**
 * Value · Offered to · Receiving it · Granted (image 19). *Granted* is the
 * server's `granted_this_month`, a dash while it is `null` (`DEF-2430`).
 */
export function discountTiles(row: DiscountDetailRow, t: Translator): KpiTile[] {
  const figures = tileFigures(row, t);
  return [
    { id: "value", label: t("rating.discountForm.review.value"), value: figures.value, detail: figures.valueDetail || undefined },
    { id: "offered", label: t("rating.discountDetail.kpi.offered"), value: figures.offered, detail: t("rating.discountDetail.kpi.unitsOnPlans") },
    { id: "receiving", label: t("rating.discountDetail.kpi.receiving"), value: figures.receiving, detail: t("rating.discountDetail.kpi.accounts") },
    { id: "granted", label: t("rating.discountDetail.kpi.granted"), value: figures.granted, detail: t("rating.discountDetail.kpi.thisMonth") },
  ];
}

/** The versions table at the foot of *Eligibility* (images 19, 24, 26). */
export function DiscountVersionsTable(props: {
  discountId: string;
  client: ApiClient;
  regional: DiscountRegional;
  t: Translator;
}) {
  const { t, regional } = props;
  const query = useQuery({
    queryKey: discountVersionsQueryKey(props.discountId),
    queryFn: () => getDiscountVersionLines(props.discountId, props.client),
    enabled: props.discountId !== "",
    staleTime: REFERENCE_STALE_MS,
  });
  if (query.isPending) return <LoadingSkeleton variant="table" />;
  if (query.isError) return <Note>{t("rating.taxDetail.versions.failed")}</Note>;
  const rows: readonly DiscountVersionLine[] = query.data ?? [];
  const today = todayInZone(regional.timeZone);
  return (
    <div className="border border-divider" data-discount-versions="">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("rating.discountDetail.versions.version")}</th>
            <th scope="col" className="!text-right">
              {t("rating.discountForm.review.value")}
            </th>
            <th scope="col">{t("rating.taxDetail.versions.dates")}</th>
            <th scope="col">{t("rating.taxDetail.versions.status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            // B14 rule 31 — the id is the key, never a cell.
            <tr key={row.id} data-version-status={row.status}>
              <td>{t("rating.discountDetail.versions.n", { n: row.version_no })}</td>
              <td className="!text-right font-semibold tabular-nums">{row.value_display ?? DASH}</td>
              <td className="tabular-nums">
                {windowText(row.effective_from, row.effective_to, regional, t("rating.taxes.list.noEnd")) ?? DASH}
              </td>
              <td>
                <DiscountStatusCell status={versionStatus(row, today)} />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}

export function DiscountOverviewTab(props: {
  row: DiscountDetailRow;
  client: ApiClient;
  regional: DiscountRegional;
  auditTo: string;
  t: Translator;
}) {
  const { row, t } = props;
  return (
    <div className="flex flex-col gap-5" data-discount-overview="">
      <KPIStrip kpis={discountTiles(row, t)} />

      <Panel as="section" aria-labelledby="discount-detail-details">
        <h2 id="discount-detail-details" className={SECTION_HEADING}>
          {t("rating.discountForm.step.details")}
        </h2>
        <FactBlock name="discount-details" variant="strip" columns={3} facts={detailsFacts(row, t)} />
      </Panel>

      <Panel as="section" aria-labelledby="discount-detail-eligibility">
        <h2 id="discount-detail-eligibility" className={SECTION_HEADING}>
          {t("rating.discountForm.step.eligibility")}
        </h2>
        <FactBlock
          name="discount-eligibility"
          variant="strip"
          columns={3}
          facts={eligibilityFacts(row, t, props.regional)}
        />
        <div className="mt-5">
          <DiscountVersionsTable discountId={row.id} client={props.client} regional={props.regional} t={t} />
        </div>
        <div className="mt-4">
          <InlineLinkTo className="font-semibold" to={props.auditTo} data-discount-see-audit="">
            {t("rating.taxDetail.seeAudit")}
          </InlineLinkTo>
        </div>
      </Panel>
    </div>
  );
}
