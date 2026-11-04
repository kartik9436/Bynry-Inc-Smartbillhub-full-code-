// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave B — CHG-01, View details of ONE charge code, BUILT
//           FROM THE IMAGES (B14 rules 41, 42; our UI standard on spacing,
//           sizes and components, rule 44; every drawn figure an illustration,
//           rule 37). Screen: CHG-01.
// Images:   05-prototype/charge-codes-2026-10-01/images
//             base  06–21 (BASE-FIRE scheduled · BASE-W · BASE-S · BASE-T)
//             plan  22–33 (CONN by size · DEPOSIT by class · LATE penalty)
//             other 34–42 (APP-FEE GL not set · RE-READ · TAP entered when used)
// Ruling:   decision log 2026-10-01 *"CHARGE-CODE LIST AND VIEW DETAILS"* —
//           header = code, bill line, Kind badge, Status; no rationale sentence
//           under the title; tabs Overview · Prices · Plans · Audit, and OTHER
//           HIDES PLANS; Details + How it bills; tiles by kind.
// ───────────────────────────────────────────────────────
/**
 * What it replaces: the charge kind of the shared `DefinitionDetailPage` (one
 * page for charges, discounts and taxes). Discounts and taxes stay there; the
 * charge route opens THIS page, which varies by kind as the PO ruled.
 *
 * Every figure is the server's: the tiles are `usage` (sent bills of last
 * month, `null` when billing cannot answer), the prices are the rows in force
 * today, the Audit rows are `versions` — the price history read from the dated
 * rows and `rate_change_log`. Nothing here adds money.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getCharge,
  getChargePlans,
  getLookupEntries,
  getMyPermissions,
  setChargeActive,
} from "@/api/endpoints";
import type { ChargeReachRow, ChargeRow, LookupEntry } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { Fact } from "@/components/FactBlock";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { TableArray } from "@/components/TableArray";
import { useToast } from "@/components/Toast";
import { useRegional } from "@/features/metering/meteringShared";
import {
  RefusalNotice,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { ALL_SIZES, GRACE_FALLBACK, PER_CASE, STORED_CLASSES, assetKeyFor, chargedKey, floorText, hasFloors, inClassOrder, pricedByWords, rowsInSizeOrder, sizeLabel, sizesFor } from "./chargeCodeModel";
import type { PricedBy } from "./chargeCodeModel";
import {
  ChargeNote,
  FactsPanel,
  GlValue,
  HowItBillsPanel,
  KindBadge,
  PricesReadTable,
  dollars,
  graceText,
} from "./chargeCodeParts";
import type { PriceReadRow } from "./chargeCodeParts";
import { DEFINITION_ROUTES, definitionWizardPath } from "./definitionDetail";
import {
  DASHBOARD_ROUTE,
  GuardedButton,
  RatingStatusPill,
  activeStatusTone,
  ratingAccess,
  ratingIsDenied,
  ratingIsReadOnly,
} from "./ratingShared";
import type { Translator } from "./ratingShared";

export const CHARGE_DETAIL_TABS = ["overview", "prices", "plans", "audit"] as const;
export type ChargeDetailTab = (typeof CHARGE_DETAIL_TABS)[number];

/** Other HIDES Plans (PO 2026-10-01) — an other charge is added by a clerk, never carried. */
export function chargeDetailTabs(kind: ChargeRow["kind"]): ChargeDetailTab[] {
  return kind === "other" ? ["overview", "prices", "audit"] : [...CHARGE_DETAIL_TABS];
}

const SIZE_PAGE = 200;

/** What the code is priced by, read off the rows in force today. */
export function storedPricedBy(row: ChargeRow): PricedBy {
  const inForce = row.size_amounts ?? [];
  // DEF-RAT-8753 — `per_case` is *Entered when used*; a penalty with class
  // terms is priced by customer class.
  if (row.amount_rule === PER_CASE) return "entered";
  if (row.amount_rule === "percent" || row.amount_rule === "percent_with_minimum") {
    return (row.class_terms ?? []).length > 0 ? "class" : "one";
  }
  if (inForce.some((price) => price.size_class !== ALL_SIZES)) return "size";
  if (inForce.some((price) => price.customer_class !== null)) return "class";
  if (row.amount === null && inForce.length === 0) return "entered";
  return "one";
}

/** The version in force today, if any — what *Effective from / to* read. */
function inForceVersion(row: ChargeRow) {
  return (row.versions ?? []).find((version) => version.state === "in_force") ?? null;
}

export interface ChargeCodeDetailPageProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

export function ChargeCodeDetailPage(props: ChargeCodeDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const chargeId = params.definitionId ?? "";
  const { timeZone, dateFormat } = useRegional(props);
  const [retiring, setRetiring] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const chargeQuery = useQuery({
    queryKey: queryKeys.charge(chargeId),
    queryFn: () => getCharge(chargeId, client),
    enabled: chargeId !== "",
  });
  const plansQuery = useQuery({
    queryKey: queryKeys.chargePlans(chargeId, 1),
    queryFn: () => getChargePlans(chargeId, { page: 1, per: 50 }, client),
    enabled: chargeId !== "",
    retry: false,
  });
  const sizesQuery = useQuery({
    queryKey: queryKeys.lookupEntries("service_size_classes", "", 1, SIZE_PAGE),
    queryFn: () => getLookupEntries("service_size_classes", { per: SIZE_PAGE }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const retire = useMutation({
    mutationFn: (row: ChargeRow) => setChargeActive(row.id, row.status !== "active", client),
    onSuccess: (saved) => {
      setRetiring(false);
      setRefusal(null);
      fireToast(
        t(
          saved.status === "active"
            ? "rating.charges.toast.reactivated"
            : "rating.charges.toast.deactivated",
          { code: saved.code },
        ),
      );
      void queryClient.invalidateQueries({ queryKey: ["charges"] });
    },
    onError: (error: unknown) => {
      setRetiring(false);
      setRefusal(refusalOf(error, translate));
    },
  });

  const listRoute = DEFINITION_ROUTES.charge.listRoute;
  if (permissionsQuery.isPending || chargeQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access) || isPermissionDenied(chargeQuery.error)) {
    return (
      <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />
    );
  }
  const row = chargeQuery.data;
  if (row === undefined) {
    return (
      <FailedWithRetry
        title={t("rating.chargeCode.view.loadFailed")}
        reason={apiErrorText(chargeQuery.error, translate)}
        onRetry={() => void chargeQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(listRoute))}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);
  const tabs = chargeDetailTabs(row.kind);
  const asked = searchParams.get("tab") as ChargeDetailTab | null;
  const active: ChargeDetailTab = asked !== null && tabs.includes(asked) ? asked : "overview";
  const entries: readonly LookupEntry[] = sizesQuery.data?.results ?? [];
  // DEF-RAT-9109: the backfill's 2000-01-01 (`PRICE_HISTORY_EPOCH`) is not a
  // date anyone set, so it is never printed as one — the same reading the
  // rate-schedule Rates tab has given it since 2.433.4. Every date on this
  // screen goes through here, so Overview and Audit cannot disagree.
  const day = (value: string | null | undefined) =>
    value === null || value === undefined || value === "2000-01-01"
      ? null
      : formatDate(value, timeZone, dateFormat);

  const scheduled = (row.versions ?? [])
    .filter((version) => version.state === "scheduled")
    .map((version) => version.effective_from)
    .sort()[0];

  return (
    <div className="flex flex-col gap-5 pt-6 px-4 pb-8" data-screen="CHG-01" data-charge-kind={row.kind ?? ""}>
      <PageHeader
        backTo={{ to: tenantPath(listRoute), label: t("rating.chargeCode.crumb") }}
        kicker={row.code}
        title={row.name}
        status={
          <span className="inline-flex items-center gap-2">
            <KindBadge kind={row.kind} t={translate} />
            <RatingStatusPill tone={activeStatusTone(row.status)} stem="rating.status" value={row.status} />
          </span>
        }
        secondaryActions={[
          <GuardedButton
            key="duplicate"
            readOnly
            readOnlyReason={t("rating.definition.action.notBuilt")}
            onClick={() => undefined}
          >
            {t("rating.definition.action.duplicate")}
          </GuardedButton>,
          // DEF-RAT-9116 — CR-087 E1: the same three, drawn the same way, on
          // every details screen; Edit is plain, as on rate-schedule details.
          <GuardedButton
            key="edit"
            readOnly={readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            onClick={() => navigate(tenantPath(definitionWizardPath("charge", row.id)))}
          >
            {t("rating.definition.action.edit")}
          </GuardedButton>,
          <GuardedButton
            key="retire"
            variant="danger"
            readOnly={readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            onClick={() => setRetiring(true)}
          >
            {t(row.status === "active" ? "rating.definition.action.retire" : "rating.action.reactivate")}
          </GuardedButton>,
        ]}
        // Images 06–42 draw the scheduled band and the four tiles ABOVE the
        // tab strip: they describe the code, not one tab (wave C comparison).
        aboveTabs={
          <div className="mt-6 flex flex-col gap-5">
            {scheduled !== undefined && (
              <ChargeNote tone="warning" lead={t("rating.chargeCode.view.scheduledLead")} name="scheduled">
                {t("rating.chargeCode.view.scheduled", { date: day(scheduled) })}
              </ChargeNote>
            )}
            <KPIStrip kpis={chargeTiles(row, plansQuery.data?.count ?? null, translate)} />
          </div>
        }
        tabs={tabs.map((id) => ({ id, label: t(`rating.chargeCode.tab.${id}`) }))}
        activeTabId={active}
        tabsLabel={t("rating.definition.tabsLabel")}
        onTabSelect={(tab) => {
          const next = new URLSearchParams(searchParams);
          next.set("tab", tab.id);
          setSearchParams(next, { replace: true });
        }}
      />
      <RefusalNotice refusal={refusal} />
      <ChargeTabBody
        tab={active}
        row={row}
        entries={entries}
        day={day}
        plans={plansQuery.data?.results ?? null}
        plansFailed={plansQuery.isError}
        t={translate}
      />
      {retiring && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("rating.chargeCode.view.retireTitle", { code: row.code })}
          consequence={t("rating.chargeCode.view.retireBody")}
          confirmLabel={t("rating.definition.action.retire")}
          working={retire.isPending}
          onConfirm={() => retire.mutate(row)}
          onCancel={() => setRetiring(false)}
        />
      )}
    </div>
  );
}

/** The four tiles, by kind (decision log 2026-10-01, *"tiles by kind"*). */
export function chargeTiles(row: ChargeRow, plans: number | null, t: Translator): KpiTile[] {
  const usage = row.usage ?? null;
  const count = (value: number | undefined) => (usage === null || value === undefined ? "—" : value.toLocaleString());
  const revenue = usage === null ? "—" : (dollars(usage.revenue_display) ?? "—");
  const pricedBy = storedPricedBy(row);
  if (row.kind === "other") {
    const amount = pricedBy === "entered" ? t("rating.chargeCode.pricedBy.entered") : (dollars(row.amount_display) ?? "—");
    return [
      { id: "times", label: t("rating.chargeCode.tile.timesUsed"), value: count(usage?.lines) },
      { id: "bills", label: t("rating.chargeCode.tile.bills"), value: count(usage?.bills) },
      { id: "revenue", label: t("rating.chargeCode.tile.revenueLastMonth"), value: revenue },
      { id: "amount", label: t("rating.chargeCode.tile.amount"), value: amount },
    ];
  }
  const reach: KpiTile = {
    id: "plans",
    label: t("rating.chargeCode.tile.plans"),
    value: plans === null ? "—" : plans.toLocaleString(),
  };
  const bills: KpiTile = { id: "bills", label: t("rating.chargeCode.tile.bills"), value: count(usage?.bills) };
  const money: KpiTile = { id: "revenue", label: t("rating.chargeCode.tile.revenue"), value: revenue };
  if (row.kind === "base") {
    const inForce = (row.size_amounts ?? []).length > 0 ? row.size_amounts ?? [] : [];
    const total = inForce.length === 0 ? 1 : inForce.length;
    const priced = inForce.length === 0 ? (row.amount === null ? 0 : 1) : inForce.filter((p) => p.amount !== null).length;
    return [
      reach,
      bills,
      money,
      { id: "sizes", label: t("rating.chargeCode.tile.sizesPriced"), value: t("rating.chargeCode.ofCount", { n: priced, total }) },
    ];
  }
  const words = pricedByWords({ kind: row.kind ?? "plan", pricedBy, customerClass: "" }, null);
  return [
    reach,
    bills,
    money,
    { id: "pricedBy", label: t("rating.chargeCode.field.pricedBy"), value: t(words.key, words.params) },
  ];
}

function ChargeTabBody(props: {
  tab: ChargeDetailTab;
  row: ChargeRow;
  entries: readonly LookupEntry[];
  day: (value: string | null | undefined) => string | null;
  plans: ChargeReachRow[] | null;
  plansFailed: boolean;
  t: Translator;
}) {
  const { row, t } = props;
  const tenantPath = useTenantPath();
  const pricedBy = storedPricedBy(row);
  const service = row.service === null ? t("rating.charges.anyService") : t(`rating.service.${row.service}`, { defaultValue: row.service });
  const assetKey = assetKeyFor(row.service ?? "", pricedBy === "size");
  const asset = assetKey === null ? null : t(assetKey);
  const classes = row.applies_to_customer_classes ?? [];
  const words = pricedByWords(
    // DEF-RAT-9176 — two or more classes read as "N classes", never "Every class".
    {
      kind: row.kind ?? "plan",
      pricedBy,
      customerClass: classes.length === 0 ? "" : classes.length === 1 ? classes[0] : STORED_CLASSES,
      storedClasses: classes,
    },
    asset,
  );
  const pricedByText = t(words.key, words.params);

  if (props.tab === "overview") {
    const version = inForceVersion(row);
    const facts: Fact[] = [
      { id: "code", label: t("rating.chargeCode.field.code"), value: row.code },
      { id: "billLine", label: t("rating.chargeCode.field.billLine"), value: row.name },
      { id: "kind", label: t("rating.chargeCode.field.kind"), value: row.kind ? t(`rating.chargeCode.kind.${row.kind}`) : "—" },
      {
        id: "type",
        label: t("rating.chargeCode.field.type"),
        // A base charge's Type is *Every bill* (image 18, the PO's View table);
        // the other kinds read their type's own word.
        value: row.kind === "base" ? t("rating.chargeCode.charged.everyBill") : typeWords(row.charge_type, t),
      },
      { id: "service", label: t("rating.chargeCode.field.service"), value: service },
    ];
    if (row.kind === "base") {
      facts.push({
        id: "customerClass",
        label: t("rating.chargeCode.field.customerClass"),
        value: classes.length === 0 ? t("rating.chargeCode.everyClass") : classes.map((c) => t(`rating.customerClass.${c}`, { defaultValue: c })).join(", "),
      });
    }
    facts.push({ id: "pricedBy", label: t("rating.chargeCode.field.pricedBy"), value: pricedByText });
    if (asset !== null) facts.push({ id: "asset", label: t("rating.chargeCode.field.asset"), value: asset });
    if (row.kind === "other") {
      facts.push({
        id: "amount",
        label: t("rating.chargeCode.tile.amount"),
        value: pricedBy === "entered" ? t("rating.chargeCode.pricedBy.entered") : (dollars(row.amount_display) ?? "—"),
      });
    }
    facts.push(
      { id: "gl", label: t("rating.chargeCode.field.gl"), value: <GlValue code={row.gl_account_code} name={row.gl_account_name} t={t} /> },
      { id: "from", label: t("rating.chargeCode.field.effectiveFrom"), value: props.day(version?.effective_from) ?? "—" },
      {
        id: "to",
        label: t("rating.chargeCode.field.effectiveTo"),
        value: version === null ? "—" : (props.day(version.effective_to) ?? t("rating.chargeCode.noEnd")),
      },
    );
    return (
      <div className="flex flex-col gap-5">
        <FactsPanel title={t("rating.chargeCode.details")} name="details" facts={facts}>
          {(row.gl_account_code === null || row.gl_account_code === undefined) && (
            <ChargeNote tone="warning" name="no-gl">
              {t("rating.chargeCode.view.noGl")}{" "}
              {/* CR-197-BRC10 Phase 3 — straight to its row on the one GL mapping list. */}
              <InlineLinkTo
                to={`${tenantPath("/settings/accounting/mapping")}?type=charge_code&q=${encodeURIComponent(row.code)}`}
                data-gl-mapping-fix=""
              >
                {t("rating.chargeCode.view.noGlLink")}
              </InlineLinkTo>
            </ChargeNote>
          )}
        </FactsPanel>
        <HowItBillsPanel facts={howItBills(row, t)} t={t} />
      </div>
    );
  }

  if (props.tab === "prices") {
    return <StoredPrices row={row} entries={props.entries} service={service} asset={asset} pricedBy={pricedBy} pricedByText={pricedByText} t={t} />;
  }

  if (props.tab === "plans") {
    if (props.plansFailed) return <ChargeNote tone="warning" name="plans-failed">{t("rating.chargeCode.view.plansFailed")}</ChargeNote>;
    return (
      <TableArray<ChargeReachRow>
        readOnly
        collection="charge-plans"
        title={t("rating.chargeCode.tab.plans")}
        columns={[
          { key: "plan", label: t("rating.chargeCode.col.plan"), cell: (plan) => plan.plan_name },
          // DEF-RAT-8752 — image 20: the plan's customer class and its accounts.
          {
            key: "class",
            label: t("rating.chargeCode.col.customerClass"),
            cell: (plan) =>
              (plan.customer_classes ?? []).length === 0
                ? t("rating.chargeCode.everyClass")
                : (plan.customer_classes ?? []).join(", "),
          },
          // Units gave way to Accounts once accounts had a read (image 20
          // draws Plan · Customer class · Accounts).
          {
            key: "accounts",
            label: t("rating.chargeCode.col.accounts"),
            numeric: true,
            cell: (plan) =>
              plan.accounts === null || plan.accounts === undefined ? "—" : plan.accounts.toLocaleString(),
          },
        ]}
        rows={props.plans ?? []}
        rowKey={(plan) => plan.plan_id}
        emptyText={t("rating.chargeCode.view.noPlans")}
      />
    );
  }

  const versions = row.versions ?? [];
  return (
    <TableArray<(typeof versions)[number]>
      readOnly
      collection="charge-versions"
      title={t("rating.chargeCode.tab.audit")}
      columns={[
        {
          key: "state",
          label: t("rating.chargeCode.col.version"),
          cell: (version) => (
            <StatusPill tone={version.state === "scheduled" ? "warning" : version.state === "in_force" ? "success" : "neutral"}>
              {t(`rating.chargeCode.versionState.${version.state}`)}
            </StatusPill>
          ),
        },
        { key: "from", label: t("rating.chargeCode.field.effectiveFrom"), cell: (version) => props.day(version.effective_from) },
        { key: "to", label: t("rating.chargeCode.field.effectiveTo"), cell: (version) => props.day(version.effective_to) ?? "—" },
        {
          key: "what",
          label: t("rating.chargeCode.col.whatChanged"),
          cell: (version) =>
            version.created
              ? t("rating.chargeCode.view.created")
              : version.changes
                  .filter((change) => !(change.before_display === change.after_display))
                  .map((change) =>
                    change.terms === true
                      ? // DEF-RAT-8753 — a class's percent and minimum, composed
                        // by the server (`1.50% · $5.00`); the class by name.
                        `${t(`rating.customerClass.${change.customer_class ?? ""}`, { defaultValue: change.customer_class ?? "" })}: ` +
                        `${change.before_display ?? t("rating.chargeCode.notPriced")} → ` +
                        `${change.after_display ?? t("rating.chargeCode.notPriced")}`
                      : // Glyphs between three translated parts — no catalogue key.
                        `${change.size_class === ALL_SIZES ? t("rating.chargeCode.view.amountItem") : sizeLabel(change.size_class ?? "", props.entries)}: ` +
                        `${dollars(change.before_display) ?? t("rating.chargeCode.notPriced")} → ` +
                        `${dollars(change.after_display) ?? t("rating.chargeCode.notPriced")}`,
                  )
                  .join(" · "),
        },
        { key: "who", label: t("rating.chargeCode.col.who"), cell: (version) => version.who ?? "—" },
        { key: "why", label: t("rating.chargeCode.col.why"), cell: (version) => version.why ?? "—" },
      ]}
      rows={versions}
      rowKey={(version) => version.effective_from}
      emptyText={t("rating.chargeCode.view.noVersions")}
    />
  );
}

/** The Prices tab — the rows in force today, laid out by what the code is priced by. */
function StoredPrices(props: {
  row: ChargeRow;
  entries: readonly LookupEntry[];
  service: string;
  asset: string | null;
  pricedBy: PricedBy;
  pricedByText: string;
  t: Translator;
}) {
  const { row, t } = props;
  if (props.pricedBy === "entered") {
    return (
      <Panel as="section" title={t("rating.chargeCode.prices")}>
        <p className="m-0 text-base" data-prices-entered="">{t("rating.chargeCode.view.entered")}</p>
      </Panel>
    );
  }
  const fact = <span className="font-heading text-xs font-semibold uppercase tracking-kicker">{props.pricedByText}</span>;
  const terms = row.class_terms ?? [];
  if (row.charge_type === "penalty" && terms.length > 0) {
    // DEF-RAT-8753 — image 31: one row per class, its percent and minimum,
    // Residential first as drawn.
    return (
      <PricesReadTable
        t={t}
        fact={fact}
        columns={["customerClass", "percent", "minimum"]}
        amountLabel={t("rating.chargeCode.col.amount")}
        rows={inClassOrder(terms).map((price) => ({
            key: price.customer_class ?? "every",
            customerClass:
              price.customer_class === null
                ? t("rating.chargeCode.everyClass")
                : t(`rating.customerClass.${price.customer_class}`, { defaultValue: price.customer_class }),
            percent: price.percent_display ?? null,
            minimum: dollars(price.min_amount_display),
          }))}
      />
    );
  }
  // DEF-RAT-8834 — a FLAT penalty (NSF $30.00) shows its amount like any other code.
  if (row.charge_type === "penalty" && (row.amount_rule === "percent" || row.amount_rule === "percent_with_minimum")) {
    return (
      <PricesReadTable
        t={t}
        fact={fact}
        columns={["customerClass", "percent", "minimum"]}
        amountLabel={t("rating.chargeCode.col.amount")}
        rows={[
          {
            key: "every",
            customerClass: t("rating.chargeCode.everyClass"),
            percent: row.percent_display,
            minimum: dollars(row.min_amount_display),
          },
        ]}
      />
    );
  }
  const inForce = row.size_amounts ?? [];
  const deposit = row.charge_type === "refundable" ? (
    <ChargeNote tone="info" name="deposit">{t("rating.chargeCode.depositNote")}</ChargeNote>
  ) : null;
  if (props.pricedBy === "class") {
    return (
      <PricesReadTable
        t={t}
        fact={fact}
        columns={["customerClass", "amount"]}
        amountLabel={t("rating.chargeCode.col.amount")}
        rows={inClassOrder(inForce).map((price) => ({
          key: price.customer_class ?? "every",
          customerClass: price.customer_class === null ? t("rating.chargeCode.everyClass") : t(`rating.customerClass.${price.customer_class}`, { defaultValue: price.customer_class }),
          amount: dollars(price.amount_display),
        }))}
      >
        {deposit}
      </PricesReadTable>
    );
  }
  const classes = row.applies_to_customer_classes ?? [];
  const amountLabel =
    row.kind === "base"
      ? classes.length === 0
        ? t("rating.chargeCode.everyClass")
        : // DEF-RAT-9176 — one class or several, named; never "Every class" for two.
          classes.map((c) => t(`rating.customerClass.${c}`, { defaultValue: c })).join(", ")
      : t("rating.chargeCode.col.amount");
  if (props.pricedBy === "size") {
    const rows = rowsInSizeOrder(inForce.map((price) => ({ ...price, size: price.size_class })), props.entries);
    // DEF-RAT-9322 — a size held for every class AND for one class reads as
    // two rows of one size unless the class is shown beside it.
    const byClass = rows.some((price) => price.customer_class !== null);
    const missing = rows.filter((price) => price.amount === null).length;
    const readRows: PriceReadRow[] = rows.map((price) => ({
      key: `${price.size}|${price.customer_class ?? ""}`,
      service: props.service,
      asset: props.asset ?? undefined,
      // DEF-RAT-9321 — the size's NAME (`Water 5/8"`), never its code.
      size: sizeLabel(price.size, props.entries),
      customerClass:
        price.customer_class === null
          ? t("rating.chargeCode.everyClass")
          : t(`rating.customerClass.${price.customer_class}`, { defaultValue: price.customer_class }),
      amount: dollars(price.amount_display),
      floor: floorText(row.size_minimums, price.size),
    }));
    // DEF-RAT-8752 — a BASE code shows the schedules' minimum beside each
    // size (image 11) — only where some schedule floors a size at all: images
    // 07 and 19 (fire, trash) draw no Minimum column. A plan code priced by
    // size has no schedule minimum.
    const head = byClass ? (["service", "asset", "size", "customerClass"] as const) : (["service", "asset", "size"] as const);
    const columns: ("service" | "asset" | "size" | "customerClass" | "amount" | "floor")[] =
      row.kind === "base" && hasFloors(row.size_minimums) ? [...head, "amount", "floor"] : [...head, "amount"];
    return (
      <PricesReadTable t={t} fact={fact} columns={columns} amountLabel={amountLabel} rows={readRows}>
        {missing > 0 && (
          <ChargeNote tone="warning" name="not-priced" lead={t("rating.chargeCode.notPricedLead", { n: missing, total: rows.length })}>
            {t("rating.chargeCode.notPricedBilled")}
          </ChargeNote>
        )}
        {deposit}
      </PricesReadTable>
    );
  }
  // One amount. A base names its service; a plan or other code is just the figure.
  const amount = dollars(row.amount_display);
  if (row.kind === "base") {
    // DEF-RAT-8836 — on a service with sizes the one amount is its *All sizes*
    // row and the asset is named; sewer (no sizes, by ruling) keeps "—".
    const assetKey = assetKeyFor(row.service ?? "", sizesFor(props.entries, row.service ?? "").length > 0);
    const asset = assetKey === null ? null : t(assetKey);
    return (
      <PricesReadTable
        t={t}
        fact={fact}
        columns={asset === null ? ["service", "asset", "amount"] : ["service", "asset", "size", "amount"]}
        amountLabel={amountLabel}
        rows={[{ key: "one", service: props.service, asset: asset ?? "—", size: t("rating.rs.allSizes"), amount }]}
      />
    );
  }
  return (
    <PricesReadTable t={t} fact={fact} columns={["amount"]} amountLabel={amountLabel} rows={[{ key: "one", amount }]}>
      {deposit}
    </PricesReadTable>
  );
}

export function typeWords(chargeType: string | null, t: Translator): string {
  if (chargeType === null) return "—";
  if (chargeType === "refundable") return t("rating.chargeCode.type.refundable");
  return t(`rating.charges.type.${chargeType}`, { defaultValue: chargeType });
}

/** The six *How it bills* facts for a stored code. */
export function howItBills(row: ChargeRow, t: Translator): Fact[] {
  const yesNo = (value: boolean) => t(value ? "rating.yes" : "rating.no");
  return [
    {
      id: "partMonth",
      label: t("rating.chargeCode.field.partMonth"),
      value: t(row.kind === "base" ? "rating.chargeCode.partMonth.days" : "rating.chargeCode.partMonth.full"),
    },
    { id: "charged", label: t("rating.chargeCode.field.charged"), value: t(chargedKey(row.charge_type ?? "")) },
    { id: "taxed", label: t("rating.chargeCode.field.taxed"), value: yesNo(row.taxable_default) },
    { id: "auto", label: t("rating.chargeCode.field.auto"), value: yesNo(row.auto_apply) },
    { id: "waive", label: t("rating.chargeCode.field.waive"), value: yesNo(row.waivable) },
    { id: "ownLine", label: t("rating.chargeCode.field.ownLine"), value: yesNo(row.separate_line) },
    // DEF-CUS-9819 — the utility's application fee (a one-time code only).
    ...(row.charge_type === "one_time"
      ? [{ id: "applicationFee", label: t("rating.chargeCode.field.applicationFee"), value: yesNo(row.is_application_fee === true) }]
      : []),
    // DEF-RAT-10739 (PO 2026-10-31 P7) — the NSF fee a bounce charges.
    ...(row.charge_type === "penalty"
      ? [{ id: "nsfFee", label: t("rating.chargeCode.field.nsfFee"), value: yesNo(row.is_nsf_fee === true) }]
      : []),
    // PO 2026-10-06 11 (a) — the late-fee grace lives on a penalty code.
    ...(row.charge_type === "penalty"
      ? [
          {
            id: "grace",
            label: t("rating.chargeCode.field.grace"),
            value: graceText(
              t,
              row.grace_days ?? row.grace_default?.days ?? GRACE_FALLBACK.days,
              row.grace_mode ?? row.grace_default?.mode ?? GRACE_FALLBACK.mode,
            ),
          },
        ]
      : []),
  ];
}
