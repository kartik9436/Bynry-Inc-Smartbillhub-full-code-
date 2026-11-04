// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 AST-W5 T1 (B16 §4.4 · §10-D5 RULED 2026-08-22: "Launch
//           with counts & costs only" — no vans, no reorder thresholds, no
//           stock table, stock-count import deferred). Screens: AST-01.inventory.
// Rules:    §10-D5 · §10-D7 ("Work R5" — the ONE two-word disabled reason) ·
//           BR-AST-031 (the drill filters on the behavior CLASS `available`,
//           served as the reserved status value `uninstalled`) · hard rule 2
//           (money 4 dp stored, 2 dp displayed — MoneyCell) · BR-SHL-025
//           (disabled-with-reason, never hidden) · B14 r21 (Tailwind)
// Impacts:  AssetRegistryPage.tsx (mounts this on ?tab=inventory) ·
//           GET /assets/stock (apps/assets/api.py)
// ───────────────────────────────────────────────────────
// AST-01.inventory — the Inventory tab of the Assets page.
//
// AGGREGATE lines, not entity rows: each row is "everything uninstalled of
// one type", so the table is the detail-panel table (the AssetDetailPage
// TABLE discipline), not a DataTable — there is nothing to search, sort or
// page on five aggregate lines, and r10 draws it exactly this plain. The
// DRILL is the row's own affordance: clicking a type opens the real registry
// filtered to that type's uninstalled rows, where every list capability
// already exists (B16 §5.1b: "no second detail screen exists anywhere").
//
// WHAT IS DELIBERATELY ABSENT, per §10-D5, and the tests assert each absence:
// the Yard / On-vans split (everything uninstalled is one number), the
// "Reorder at" column and its Healthy/At-reorder/Below-reorder statuses, the
// "Raise reorder" button, and the "↑ Import stock count" button. r10 draws
// them all; the ruling cut them: "Launch with counts & costs only."
// "Parts in Work →" is LIVE since CR-070 wave M. It was disabled with the two
// words "Work R5" while the Work module did not exist; `Work-025` (the parts
// register) shipped in wave C and this control went on refusing over it for two
// waves — a live screen behind a dead door, which no gate in this repo can see
// (hard-won law 2's mirror clause, `DEF-CWP-3925`).
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAssetStockEveryPage } from "@/api/endpoints";
import type { AssetStockRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { KPIStrip } from "@/components/KPIStrip";
import { formatMoney, MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { ServiceTags } from "@/features/rating/ratingShared";
import { WORK_PARTS_ROUTE } from "@/features/work/WorkShell";
import { useTenantPath } from "@/routing/tenantPath";

import { AssetDash, useTranslator } from "./assetsShared";

export const assetStockQueryKey = ["assets", "stock"] as const;

/**
 * The drill: one stock line → the REAL registry, preset to that type's
 * uninstalled rows. `f.status=uninstalled` is the server's reserved
 * behavior-class value (BR-AST-031 — the class, never a stage label), so the
 * link survives a tenant who renamed their Inventory stage.
 */
export function stockDrillPath(row: Pick<AssetStockRow, "tab" | "type">): string {
  const params = new URLSearchParams();
  params.set("tab", String(row.tab));
  params.set("f.type", row.type);
  params.set("f.status", "uninstalled");
  return `/assets?${params.toString()}`;
}

const TABLE =
  "w-full border-collapse text-table [&_td]:border-b [&_td]:border-b-divider [&_td]:p-2 [&_td]:text-left [&_td]:align-top [&_th]:border-b [&_th]:border-b-divider [&_th]:p-2 [&_th]:text-left [&_th]:align-top [&_th]:font-heading [&_th]:text-table-header [&_th]:uppercase [&_th]:tracking-table-header";

export interface AssetInventoryTabProps {
  /** BR-SHL-025: null = allowed; a string disables writes WITH it. (The tab
   *  itself is read-only; kept for the shape every tab body shares.) */
  writeBlockedReason: string | null;
  /** Navigate to one stock line's filtered registry (stockDrillPath). */
  onDrill: (row: AssetStockRow) => void;
  client?: ApiClient;
}

export function AssetInventoryTab(props: AssetInventoryTabProps) {
  const { t } = useTranslation();
  const translate = useTranslator();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;

  const stock = useQuery({
    queryKey: assetStockQueryKey,
    queryFn: () => getAssetStockEveryPage(client),
    retry: false,
  });

  if (stock.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (stock.data === undefined) {
    return (
      <p role="alert" className="text-base">
        {apiErrorText(stock.error, translate)}
      </p>
    );
  }

  const { kpis, rows } = stock.data;
  const money = (amount: string | null): string | null =>
    amount !== null && kpis.currency !== null ? formatMoney(amount, kpis.currency) : null;
  const atCost = money(kpis.value_at_cost);

  return (
    <>
      {/* r10's KPI strip MINUS the two D5 cut cards (On vans · Below reorder). */}
      <div className="mb-5">
        <KPIStrip
          kpis={[
            {
              id: "uninstalled",
              label: t("assets.stock.kpi.uninstalled"),
              value: <span>{kpis.uninstalled.toLocaleString()}</span>,
              detail:
                atCost !== null
                  ? t("assets.stock.kpi.atCost", { amount: atCost })
                  : undefined,
            },
            {
              id: "aged_over_12_months",
              label: t("assets.stock.kpi.aged"),
              value: <span>{kpis.aged_over_12_months.toLocaleString()}</span>,
              detail: t("assets.stock.kpi.agedDetail"),
            },
          ]}
        />
      </div>

      <div className="overflow-x-auto">
        <table className={TABLE}>
          <thead>
            <tr>
              <th>{t("assets.stock.col.type")}</th>
              <th>{t("assets.stock.col.service")}</th>
              <th className="[&&]:text-right">{t("assets.stock.col.count")}</th>
              <th className="[&&]:text-right">{t("assets.stock.col.unitCost")}</th>
              <th className="[&&]:text-right">{t("assets.stock.col.value")}</th>
              <th>{t("assets.stock.col.supplier")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={6}>{t("assets.stock.empty")}</td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.type}>
                <td>
                  {/* The drill — a real navigation, so it is a link-styled
                      button with an accessible name naming its destination. */}
                  <button
                    type="button"
                    className="cursor-pointer border-0 bg-transparent p-0 text-left text-accent-700 hover:underline focus-visible:underline"
                    aria-label={t("assets.stock.drill", { type: row.type_name })}
                    onClick={() => props.onDrill(row)}
                  >
                    {row.type_name}
                  </button>
                </td>
                <td>
                  {/* HONEST-EMPTY for never-assigned stock: service is only
                      recorded through the service point minted at assignment. */}
                  {row.services.length > 0 ? (
                    <ServiceTags services={row.services} />
                  ) : (
                    <AssetDash />
                  )}
                </td>
                <td className="[&&]:text-right tabular-nums">{row.count.toLocaleString()}</td>
                <td className="[&&]:text-right tabular-nums">
                  {row.unit_cost !== null && kpis.currency !== null ? (
                    <>
                      <MoneyCell amount={row.unit_cost} currency={kpis.currency} />
                      {row.unit_cost_min !== null &&
                        row.unit_cost_max !== null &&
                        row.unit_cost_min !== row.unit_cost_max && (
                          <span className="block text-xs text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
                            {t("assets.stock.range", {
                              min: money(row.unit_cost_min),
                              max: money(row.unit_cost_max),
                            })}
                          </span>
                        )}
                    </>
                  ) : (
                    <AssetDash />
                  )}
                </td>
                <td className="[&&]:text-right tabular-nums">
                  {row.value !== null && kpis.currency !== null ? (
                    <MoneyCell amount={row.value} currency={kpis.currency} />
                  ) : (
                    <AssetDash />
                  )}
                </td>
                <td>{row.suppliers.length > 0 ? row.suppliers.join(" · ") : <AssetDash />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* §10-D7: the ONE footer control r10 draws that survives D5 — visible,
          disabled, with EXACTLY the two ruled words. Its r10 siblings (Raise
          reorder · Import stock count) are D5-cut, not drawn. */}
      {/* LIVE since CR-070 wave M. `Work-025` (the parts register) shipped in
          wave C, and this control went on refusing over it for two waves —
          which is hard-won law 2's mirror clause exactly: a live screen behind
          a dead door, invisible to every gate because nothing asks whether a
          REFUSAL is still true. Its r10 siblings (Raise reorder · Import stock
          count) stay D5-cut and are not drawn. */}
      <div className="mt-4 flex flex-wrap gap-2" data-parts-in-work="">
        <Button variant="secondary" onClick={() => navigate(tenantPath(WORK_PARTS_ROUTE))}>
          {t("assets.stock.partsInWork")}
        </Button>
      </div>
    </>
  );
}

export default AssetInventoryTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-028/B16@2026-08-22 §4.4 + §10-D5/D7 (AST-W5 T1)
// generated: 2026-08-22 by the CR-028 AST-W5 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetNewTabs.test.tsx — aggregates, D5 absences, the Work-R5 sweep) · i18n ×11
// exceptions: E3 the Service cell is HONEST-EMPTY for never-assigned stock — the schema records service only through the assignment-minted service point, so r10's per-stock-line service tag has no data source (reported in the lane close-out) · E4 aggregate lines render the detail-panel TABLE, not a DataTable: nothing to search/sort/page on a handful of aggregates, and the drill leads to the real DataTable registry
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
