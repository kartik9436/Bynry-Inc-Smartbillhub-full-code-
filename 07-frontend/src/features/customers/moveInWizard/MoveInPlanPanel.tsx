// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.28 (lane MVI-WIZ-BILL) — the Billing step's Plan
//           panel, from images 41 and 42: four facts (Plan, Version, Base
//           charge, Deposit rule) and *See full rates*, which opens the SHARED
//           plan sections narrowed by rating to this move-in.
// Rules:    CR-167-BRC10 ruling 11 (*"one shared component"* — `PlanSections`
//           is consumed, never forked) · PO 2026-10-02 (a unit price shows up
//           to four places, every total two — `PlanSections` reads rating's own
//           strings) · OQ-BIL-12788 CLOSED (a) · BR-CUS-029 (the plan lives on
//           the UNIT; the account derives it — so nothing here picks one) ·
//           B14 rules 31, 33, 36, 43, 44
// Server:   GET /move-ins/pricing (§9.MONEY)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT DIFFERS FROM IMAGE 42, AND WHY (B14 rule 36 — the shared component's
// order and shape win over one drawing):**
//   · the sections come in `PlanSections`' own order — services, charges,
//     taxes, deposits, discounts — where image 42 draws deposit and charges
//     before discounts and taxes. Re-ordering them here would be a second plan
//     layout, which is the drift ruling 11 exists to stop;
//   · *Rate filing* and *Plan for* under the sections are not drawn — the
//     narrowed read serves no rate-filing fact, and the class is already the
//     Deposit rule's first word;
//   · the plan's charge codes keep `PlanSections`' columns; the drawn
//     *Taxable* column would tell a clerk a move-in fee is taxed, which the PO
//     ruled it is not (`OQ-BIL-12788` (a)).
import type { MoveInAssetNode, MoveInPricing } from "@/api/moveInMoneyEndpoints";
import { normalisePlanSections } from "@/api/planFormEndpoints";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Disclosure } from "@/components/Disclosure";
import { EditableTable } from "@/components/EditableTable";
import { FactBlock } from "@/components/FactBlock";
import { formatMoney } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { PlanSections } from "@/features/rating/planSections/PlanSections";
import type { Translator } from "@/features/tenancy/settingsShared";

const DASH = "—";

/** One row of the meters-and-devices table — the tree flattened, depth kept. */
interface AssetLine {
  key: string;
  depth: number;
  node: MoveInAssetNode;
}

function flatten(nodes: readonly MoveInAssetNode[], depth = 0, prefix = ""): AssetLine[] {
  return nodes.flatMap((node, index) => {
    const key = `${prefix}${index}-${node.asset_no ?? ""}`;
    return [{ key, depth, node }, ...flatten(node.children, depth + 1, `${key}/`)];
  });
}

/** The asset's kind in words — never the stored code (B14 rule 31). */
const KIND_KEYS: Readonly<Record<string, string>> = {
  meter: "customers.moveIn.plan.kind.meter",
  sub_meter: "customers.moveIn.plan.kind.subMeter",
  behind_the_meter: "customers.moveIn.plan.kind.device",
};

function kindWord(type: string | null, t: Translator): string {
  return type === null ? DASH : t(KIND_KEYS[type] ?? "customers.moveIn.plan.kind.device");
}

function AssetTree(props: { nodes: readonly MoveInAssetNode[]; t: Translator; service: string }) {
  const { t } = props;
  const rows = flatten(props.nodes);
  if (rows.length === 0) return null;
  return (
    <div data-plan-assets={props.service}>
      <h4 className="m-0 mb-2 font-heading text-sm font-semibold uppercase text-neutral-700">
        {t("customers.moveIn.plan.assetsHeading")}
      </h4>
      <EditableTable<AssetLine>
        readOnly
        caption=""
        numbered={false}
        reorderable={false}
        rows={rows}
        rowKey={(row) => row.key}
        emptyText=""
        data-collection={`move-in-assets-${props.service}`}
        columns={[
          {
            key: "id",
            label: t("customers.moveIn.plan.col.id"),
            cell: (row) => (
              <span className={row.depth === 0 ? "font-semibold" : row.depth === 1 ? "pl-4" : "pl-8"}>
                {row.node.asset_no ?? DASH}
              </span>
            ),
          },
          { key: "kind", label: t("customers.moveIn.plan.col.kind"), cell: (row) => kindWord(row.node.type, t) },
          { key: "size", label: t("customers.moveIn.plan.col.size"), cell: (row) => row.node.size_class ?? DASH },
        ]}
      />
    </div>
  );
}

export function MoveInPlanPanel(props: {
  status: "pending" | "failed" | "ready";
  pricing: MoveInPricing | undefined;
  /** `Residential` — the customer class's name. */
  classLabel: string;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  t: Translator;
}) {
  const { t, pricing } = props;
  const raw = pricing?.plan ?? null;
  // The narrowed read is the SAME shape `GET /plans/{id}` serves, so it goes
  // through the same normaliser before the shared component draws it — a raw
  // payload is how a typed deposit rule (`ref: null`) crashed this panel
  // (`DEF-RAT-9740`).
  const plan = raw === null ? null : { ...normalisePlanSections(raw), as_of: raw.as_of, plan_version: raw.plan_version };
  const currency = plan?.currency ?? pricing?.fees.currency ?? null;
  const date = (iso: string | null | undefined) =>
    iso === null || iso === undefined || iso === "" ? DASH : formatDate(iso, props.timeZone, props.dateFormat);
  const depositRow = pricing?.fees.rows.find((row) => row.kind === "deposit" && row.amount !== null);
  const version = plan?.plan_version ?? null;

  return (
    <Panel
      as="section"
      title={t("customers.moveIn.plan.heading")}
      trailing={<span className="text-base text-neutral-700">{t("customers.moveIn.plan.fromUnit")}</span>}
      data-move-in-plan={props.status}
    >
      {props.status === "pending" && <LoadingSkeleton variant="card" />}
      {props.status === "failed" && <RefusalStrip role="alert">{t("customers.moveIn.plan.failed")}</RefusalStrip>}
      {props.status === "ready" && plan === null && (
        <p className="m-0 text-base text-neutral-700" data-move-in-plan-absent="">
          {t("customers.moveIn.plan.none")}
        </p>
      )}
        {plan !== null && pricing !== undefined && (
          <div className="flex flex-col gap-4">
            <FactBlock
              name="move-in-plan"
              columns={4}
              facts={[
                { id: "plan", label: t("customers.moveIn.plan.plan"), value: plan.details.name },
                {
                  id: "version",
                  label: t("customers.moveIn.plan.versionOn", { date: date(plan.as_of) }),
                  value:
                    version === null
                      ? DASH
                      : t("customers.moveIn.plan.versionValue", {
                          version: version.version,
                          from: date(version.effective_from),
                        }),
                },
                {
                  id: "base",
                  label: t("customers.moveIn.plan.base"),
                  value:
                    plan.base_total.amount_display === null || currency === null
                      ? DASH
                      : t("customers.moveIn.plan.baseValue", {
                          amount: formatMoney(plan.base_total.amount_display, currency),
                        }),
                },
                {
                  id: "deposit",
                  label: t("customers.moveIn.plan.depositRule"),
                  value:
                    depositRow === undefined || depositRow.amount === null || currency === null
                      ? t("customers.moveIn.plan.noDeposit")
                      : `${props.classLabel} ${formatMoney(depositRow.amount, currency)}`.trim(),
                },
              ]}
            />
            <Disclosure title={t("customers.moveIn.plan.fullRates")}>
              <div data-move-in-full-rates="">
                <PlanSections
                  sections={plan}
                  show={["services", "charges", "taxes", "deposits", "discounts"]}
                  t={t}
                  dateFormat={props.dateFormat}
                  timeZone={props.timeZone}
                  links={false}
                  serviceExtra={(section) => (
                    <AssetTree
                      service={section.service}
                      nodes={pricing.assets.find((entry) => entry.service === section.service)?.assets ?? []}
                      t={t}
                    />
                  )}
                />
              </div>
            </Disclosure>
          </div>
        )}
    </Panel>
  );
}
