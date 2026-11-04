// ── Trace ──────────────────────────────────────────────
// Change:   CR-157-BRC10 wave B — RAT-02 View details, rebuilt from the
//           2026-10-01 drawing: FOUR tabs, Overview · Rates · Plans · Audit.
// Drawing:  05-prototype/rate-schedules-2026-10-01/images/08–39 (eight
//           schedules × four tabs), read as IMAGES (B14 rule 42). The figures
//           in them are illustrations (rule 37); our UI standard decides
//           spacing, type and components (rule 44).
// Rulings:  decision log 2026-10-01, last column "rate-schedule redesign" —
//           Overview = Details + Billing rules as label-over-value lists, with
//           Effective from / Effective to as two items; Rates = Base charges
//           (# · Size · Base charge · Minimum · Units · Version · From · To,
//           *From BASE-W* a link to that code) then Usage charges with the
//           method named and NO version strip; Plans = Plan · Code · Customer
//           class · Status · Units with *Class differs*; Audit adds Filed as and
//           Corrected. The MINIMUM is per meter size (PO 2026-10-01, option A).
// Rules:    B14 rule 43 (each tab is a component) · rule 21 (Tailwind; this
//           file is on route-b-migrated.txt) · rule 31 (no id on screen) ·
//           rule 33 (labels ≤ 3 words, no rationale) · hard rule 2 (money
//           displays 2; the server formats it) · NFR-3 (the Plans tab pages)
// Tests:    ./rateScheduleView.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import type { ScheduleDetail, VersionRow, VersionStructure } from "@/api/endpoints";
import { getSchedulePlans, getScheduleRates } from "@/api/rateScheduleReads";
import type { ScheduleRates } from "@/api/rateScheduleReads";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { formatMoney, formatRate } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { formatPercent } from "@/components/PercentCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { planDetailRoute } from "./planDetail/planDetailModel";
import { formatQuantity, trimQuantity } from "@/components/UnitCell";
import { useTenantPath } from "@/routing/tenantPath";

import { PLANS_RATES_ROUTE, enumLabel } from "./ratingShared";
import type { Translator } from "./ratingShared";
import { sizeWithoutService } from "./sizeOrder";

// ── shared pieces ───────────────────────────────────────────────────────────

const KICKER = "m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700";
// `text-right!` — PlainTable sets `[&_td]:text-left`, which outranks a bare utility.
const NUM = "text-right! tabular-nums";

/** A cell with nothing to say says `—`; it is never blank. */
function Dash() {
  return <span>—</span>;
}

/** The charge code's View details — the *From BASE-W ↗* link's destination. */
export function chargeCodeRoute(chargeId: string): string {
  return `${PLANS_RATES_ROUTE}/charge-codes/${chargeId}`;
}

/** `24:00` for a window that ends at midnight — the server stores `00:00`
 *  as an END for exactly that (`services._window_intervals`). */
export function windowEnd(value: string): string {
  return value === "00:00" || value === "00:00:00" ? "24:00" : value.slice(0, 5);
}

/** The month and day a season starts or ends, in the app's language. A season
 *  repeats every year, so no year is ever shown (PO 2026-10-01). */
export function monthDay(month: number, day: number, locale: string): string {
  const name = new Intl.DateTimeFormat(locale, { month: "short", timeZone: "UTC" }).format(
    new Date(Date.UTC(2001, month - 1, 1)),
  );
  return `${day} ${name}`;
}

// ── Usage charges — ONE table per method, shared with the wizard's Review ──

/**
 * The method's own table, read-only (`09`, `13`, `17`, `21`, `25`, `29`, `33`,
 * `37` — the Rates tab — and step 3 of the wizard, which draws the same table).
 * Prices are RATES: up to 4 places, zeros past the 2nd dropped (PO 2026-10-02, narrowing OQ-620(a)),
 * formatted here only
 * because a currency needs the tenant's number format. No arithmetic.
 */
export function UsageChargesTable(props: {
  model: string | null;
  structure: VersionStructure | undefined;
  uom: string | null;
}) {
  const { t, i18n } = useTranslation();
  const structure = props.structure ?? {};
  const currency = structure.currency ?? "USD";
  const unit = props.uom ?? structure.unit ?? "";
  const rate = (value: string | null | undefined): ReactNode =>
    value === null || value === undefined || value === "" ? <Dash /> : formatRate(value, currency);
  const per = t("rating.rs.usage.pricePer", { unit });
  const model = props.model ?? structure.model ?? "";

  if (model === "tiered" || model === "flat") {
    const tiers = (structure.tiers ?? []).filter((tier) => tier.size_class === null);
    if (model === "flat") {
      return (
        <PlainTable data-usage-table="flat">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col" className={NUM}>
                {per}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td className={NUM}>{rate(tiers[0]?.unit_price)}</td>
            </tr>
          </tbody>
        </PlainTable>
      );
    }
    return (
      <PlainTable data-usage-table="tiered">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">{t("rating.rs.usage.from", { unit })}</th>
            <th scope="col">{t("rating.rs.usage.to", { unit })}</th>
            <th scope="col" className={NUM}>
              {per}
            </th>
          </tr>
        </thead>
        <tbody>
          {tiers.map((tier, index) => (
            <tr key={`${tier.seq}:${index}`}>
              <td>{index + 1}</td>
              {/* The unit is in the header, so the cell is the number alone. */}
              <td className="tabular-nums">
                {tier.from_qty === null ? <Dash /> : trimQuantity(tier.from_qty)}
              </td>
              <td className="tabular-nums">
                {tier.to_qty === null ? t("rating.tier.openEnded") : trimQuantity(tier.to_qty)}
              </td>
              <td className={NUM}>{rate(tier.unit_price)}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    );
  }
  if (model === "time_of_use") {
    return (
      <PlainTable data-usage-table="time_of_use">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">{t("rating.rs.usage.window")}</th>
            <th scope="col">{t("rating.rs.usage.days")}</th>
            <th scope="col">{t("rating.tou.start")}</th>
            <th scope="col">{t("rating.tou.end")}</th>
            <th scope="col">{t("rating.rs.usage.register")}</th>
            <th scope="col" className={NUM}>
              {per}
            </th>
          </tr>
        </thead>
        <tbody>
          {(structure.windows ?? []).map((window, index) => (
            <tr key={`${window.label}:${window.day_type}:${index}`}>
              <td>{index + 1}</td>
              <td>{windowName(t, window.label)}</td>
              <td>{t(`rating.dayType.${window.day_type}`, { defaultValue: window.day_type })}</td>
              <td className="tabular-nums">{window.start_time.slice(0, 5)}</td>
              <td className="tabular-nums">{windowEnd(window.end_time)}</td>
              <td className="bg-neutral-100 text-neutral-700">
                {window.channel === null || window.channel === "" ? (
                  <Dash />
                ) : (
                  t(`rating.rs.window.${window.channel}`, { defaultValue: window.channel })
                )}
              </td>
              <td className={NUM}>{rate(window.unit_price)}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    );
  }
  if (model === "seasonal") {
    const seasons = structure.seasons ?? [];
    const tiers = structure.tiers ?? [];
    return (
      <PlainTable data-usage-table="seasonal">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">{t("rating.tou.season")}</th>
            <th scope="col">{t("rating.tou.start")}</th>
            <th scope="col">{t("rating.tou.end")}</th>
            <th scope="col" className={NUM}>
              {per}
            </th>
          </tr>
        </thead>
        <tbody>
          {seasons.map((season, index) => {
            const own = tiers.find((tier) => tier.season === season.label);
            return (
              <tr key={`${season.label}:${index}`}>
                <td>{index + 1}</td>
                <td>{season.label}</td>
                <td>{monthDay(season.start_month, season.start_day, i18n.language || "en")}</td>
                <td>{monthDay(season.end_month, season.end_day, i18n.language || "en")}</td>
                <td className={NUM}>{rate(own?.unit_price)}</td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    );
  }
  if (model === "capacity") {
    const capacity = structure.capacity;
    return (
      <PlainTable data-usage-table="capacity">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col" className={NUM}>
              {t("rating.rs.usage.pricePer", { unit: capacity?.unit_label ?? unit })}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>1</td>
            <td className={NUM}>{rate(capacity?.rate_per_unit)}</td>
          </tr>
        </tbody>
      </PlainTable>
    );
  }
  if (model === "demand") {
    const demand = structure.demand;
    // ⚠ The drawing's *Power factor below* column is not drawn: no stored field
    // holds a threshold, and a column nothing fills is a control that answers
    // nothing (BR-SHL-010). The penalty RATE is stored and shown.
    return (
      <PlainTable data-usage-table="demand">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col" className={NUM}>
              {t("rating.rs.usage.energyPerKwh")}
            </th>
            <th scope="col" className={NUM}>
              {t("rating.rs.usage.demandPerKw")}
            </th>
            <th scope="col">{t("rating.rs.usage.peakWindow")}</th>
            <th scope="col" className={NUM}>
              {t("rating.rs.usage.pfCharge")}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>1</td>
            <td className={NUM}>{rate(demand?.energy_rate_per_kwh)}</td>
            <td className={NUM}>{rate(demand?.demand_rate_per_kw)}</td>
            <td>{demand?.peak_window_label ?? <Dash />}</td>
            <td className={NUM}>
              {demand?.pf_penalty_enabled ? rate(demand.pf_penalty_rate_per_kw) : <Dash />}
            </td>
          </tr>
        </tbody>
      </PlainTable>
    );
  }
  // percent_of_service
  const basis = structure.basis_service;
  return (
    <PlainTable data-usage-table="percent_of_service">
      <thead>
        <tr>
          <th scope="col">#</th>
          <th scope="col">{t("rating.rs.usage.ofService")}</th>
          <th scope="col">{t("rating.rs.usage.percent")}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1</td>
          <td>
            {basis === null || basis === undefined || basis === "" ? (
              <Dash />
            ) : (
              t(`rating.service.${basis}`, { defaultValue: basis })
            )}
          </td>
          <td className="tabular-nums">
            {structure.percent === null || structure.percent === undefined ? (
              <Dash />
            ) : (
              formatPercent(structure.percent, "points")
            )}
          </td>
        </tr>
      </tbody>
    </PlainTable>
  );
}

/** A canonical window name in the app's language; a tenant's own name as typed. */
export function windowName(t: Translator, label: string): string {
  const key = label.toLowerCase().replace(/[\s-]/g, "");
  const channel = key === "onpeak" ? "tou_on" : key === "midpeak" ? "tou_mid" : key === "offpeak" ? "tou_off" : null;
  return channel === null ? label : t(`rating.rs.window.${channel}`);
}

// ── Overview ────────────────────────────────────────────────────────────────

export function RateOverviewTab(props: {
  detail: ScheduleDetail;
  version: VersionRow | null;
  customerClass: string | null;
  baseCode: string | null;
  glAccount: string | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { detail, version } = props;
  const date = (value: string | null | undefined, empty: string): ReactNode =>
    value === null || value === undefined ? (
      empty
    ) : (
      <DateCell value={value} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );
  const details: Fact[] = [
    { id: "structure", label: t("rating.rates.col.structure"), value: enumLabel(translate, "rating.model", detail.structure) },
    { id: "service", label: t("rating.rs.col.service"), value: detail.service_name },
    { id: "class", label: t("rating.rs.col.customerClass"), value: props.customerClass ?? t("rating.rs.everyClass") },
    { id: "unit", label: t("rating.rs.fact.unit"), value: version?.uom ?? "—" },
    { id: "baseCode", label: t("rating.rs.fact.baseChargeCode"), value: props.baseCode ?? "—" },
    // PO 2026-10-01, option A — the minimum is set per meter size.
    { id: "minimum", label: t("rating.rs.col.minimum"), value: t("rating.rs.minimum.perSize") },
    { id: "gl", label: t("rating.rs.fact.glAccount"), value: props.glAccount ?? "—" },
    { id: "currency", label: t("rating.rs.fact.currency"), value: version?.currency ?? "—" },
    { id: "from", label: t("rating.rs.fact.effectiveFrom"), value: date(version?.effective_from, "—") },
    { id: "to", label: t("rating.rs.fact.effectiveTo"), value: date(version?.effective_to, t("rating.rs.noEnd")) },
    { id: "regulator", label: t("rating.rs.fact.regulatorRef"), value: version?.regulator_ref ?? "—" },
  ];
  // The product's own rules, stated as FACTS (`08-view-W-RES-overview.png`).
  const rules: Fact[] = (["partMonth", "rounding", "priceChange", "mistake", "retire"] as const).map(
    (id) => ({ id, label: t(`rating.rs.rule.${id}`), value: t(`rating.rs.rule.${id}Value`) }),
  );
  return (
    <Panel as="section" data-rs-tab="overview">
      <h3>{t("rating.rs.panel.details")}</h3>
      <FactBlock name="rs-details" facts={details} columns={4} />
      <h3 className="mt-6">{t("rating.rs.panel.billingRules")}</h3>
      <FactBlock name="rs-billing-rules" facts={rules} columns={4} />
    </Panel>
  );
}

// ── Rates ───────────────────────────────────────────────────────────────────

export function BaseChargesTable(props: {
  rates: ScheduleRates;
  /** Image 09 draws `5/8"`, not `Water 5/8"` — the schedule names the service. */
  serviceName?: string;
  currency: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The start of the schedule version this tab shows (DEF-RAT-9102). */
  versionFrom?: string | null;
}) {
  const { t } = useTranslation();
  const { rates } = props;
  // DEF-RAT-9102 (PO 2026-10-02, *"in rate schedule form date is not
  // displayed"*): From is the day the row's price is in force ON THIS
  // SCHEDULE — the LATER of the price's own start and the version's start. A
  // price backfilled from 2000-01-01 is served null (2.433.4) and so reads the
  // version's start; a price change starting later reads its own date. Display
  // only: nothing stored moves. ISO dates compare as strings.
  const inForceFrom = (own: string | null): string | null => {
    const version = props.versionFrom ?? null;
    if (own === null) return version;
    if (version === null) return own;
    return own > version ? own : version;
  };
  // DEF-RAT-8833 — a schedule that names no class shows every class's base code;
  // each row then says which class and code it is read for.
  const byClass = (rates.base_codes ?? []).length > 1;
  const classWord = (code: string | null | undefined) =>
    code ? t(`rating.customerClass.${code}`, { defaultValue: code }) : t("rating.rs.everyClass");
  const date = (value: string | null, open: boolean): ReactNode =>
    value === null ? (
      open ? t("rating.rs.noEnd") : <Dash />
    ) : (
      <DateCell value={value} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );
  return (
    <PlainTable data-base-table="">
      <thead>
        <tr>
          <th scope="col">#</th>
          <th scope="col">{t("rating.tier.size")}</th>
          {byClass && <th scope="col">{t("rating.rs.col.customerClass")}</th>}
          <th scope="col" className={NUM}>
            {t("rating.rs.col.baseCharge")}
          </th>
          <th scope="col" className={NUM}>
            {t("rating.rs.col.minimum")}
          </th>
          <th scope="col" className={NUM}>
            {t("rating.plans.col.units")}
          </th>
          <th scope="col">{t("rating.rateDetail.versions.col.version")}</th>
          <th scope="col">{t("rating.rs.col.from")}</th>
          <th scope="col">{t("rating.rs.col.to")}</th>
        </tr>
      </thead>
      <tbody>
        {rates.base_rows.map((row) => (
          <tr key={`${row.code ?? ""}|${row.size_class ?? "all"}`} data-base-row={row.size_class ?? "all"} data-base-row-code={row.code}>
            <td>{row.seq}</td>
            <td>
              {row.size_name === null
                ? t("rating.rs.allSizes")
                : sizeWithoutService(row.size_name, props.serviceName ?? "")}
            </td>
            {byClass && (
              <td data-base-row-class="">
                {classWord(row.customer_class)} · {row.code}
              </td>
            )}
            <td className={NUM}>
              {row.priced && row.amount !== null ? (
                formatMoney(row.amount, props.currency)
              ) : (
                <StatusPill tone="warning">{t("rating.rs.notPriced")}</StatusPill>
              )}
            </td>
            <td className={NUM}>
              {row.minimum === null ? t("rating.rs.noMinimum") : formatMoney(row.minimum, props.currency)}
            </td>
            <td className={NUM}>{formatQuantity(String(row.units))}</td>
            <td>{row.version === null ? <Dash /> : t("rating.rateDetail.kicker.version", { n: row.version })}</td>
            <td>{row.priced ? date(inForceFrom(row.effective_from), false) : <Dash />}</td>
            <td>{row.priced ? date(row.effective_to, true) : <Dash />}</td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

export function RateRatesTab(props: {
  detail: ScheduleDetail;
  version: VersionRow | null;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const tenantPath = useTenantPath();
  const ratesQuery = useQuery({
    queryKey: ["rate-schedules", "rates", props.detail.id],
    queryFn: () => getScheduleRates(props.detail.id, props.client),
    retry: false,
  });
  const currency = props.version?.currency ?? "USD";
  const rates = ratesQuery.data;
  return (
    <div className="flex flex-col gap-5" data-rs-tab="rates">
      <Panel
        as="section"
        title={t("rating.rs.panel.baseCharges")}
        trailing={
          rates?.base_code === null || rates === undefined ? undefined : (
            <p className={KICKER}>
              {t("rating.rs.col.from")}{" "}
              <Link
                to={tenantPath(chargeCodeRoute(rates.base_code!.id))}
                className="font-heading text-base text-accent-700 underline"
                data-base-code-link=""
              >
                {rates.base_code!.code} ↗
              </Link>
              {(rates.base_codes ?? []).slice(1).map((code) => (
                <span key={code.id}>
                  {" · "}
                  <Link
                    to={tenantPath(chargeCodeRoute(code.id))}
                    className="font-heading text-base text-accent-700 underline"
                    data-base-code-link={code.code}
                  >
                    {code.code} ↗
                  </Link>
                </span>
              ))}
            </p>
          )
        }
      >
        {rates === undefined ? (
          <LoadingSkeleton variant="table" />
        ) : (
          <BaseChargesTable
            rates={rates}
            serviceName={props.detail.service_name}
            currency={currency}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            versionFrom={props.version?.effective_from ?? null}
          />
        )}
      </Panel>
      <Panel
        as="section"
        title={t("rating.rs.panel.usageCharges")}
        trailing={
          <p className={KICKER}>
            {t("rating.rs.methodIs", {
              method: enumLabel(translate, "rating.model", props.detail.structure),
            })}
          </p>
        }
      >
        <UsageChargesTable
          model={props.detail.structure}
          structure={props.version?.structure}
          uom={props.version?.uom ?? null}
        />
      </Panel>
    </div>
  );
}

// ── Plans ───────────────────────────────────────────────────────────────────

const PLANS_PER_DEFAULT: PageSize = 50;

export function RatePlansTab(props: { detail: ScheduleDetail; client: ApiClient }) {
  const tenantPath = useTenantPath();
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PLANS_PER_DEFAULT);
  const plansQuery = useQuery({
    queryKey: ["rate-schedules", "plans", props.detail.id, page, per],
    queryFn: () => getSchedulePlans(props.detail.id, { page, per }, props.client),
    retry: false,
  });
  const rows = plansQuery.data?.results ?? [];
  return (
    <Panel as="section" title={t("rating.rateDetail.panel.plans")} data-rs-tab="plans">
      {plansQuery.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : rows.length === 0 ? (
        <p className="m-0 text-base text-neutral-700">{t("rating.rs.plans.empty")}</p>
      ) : (
        <>
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{t("rating.plans.col.plan")}</th>
                <th scope="col">{t("rating.plans.col.code")}</th>
                <th scope="col">{t("rating.rs.col.customerClass")}</th>
                <th scope="col">{t("rating.plans.col.status")}</th>
                <th scope="col" className={NUM}>
                  {t("rating.plans.col.units")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.plan_id} data-plan-row={row.plan_code}>
                  {/* Record links (PO 2026-10-19): the plan opens the plan. */}
                  <td>
                    <InlineLinkTo to={tenantPath(planDetailRoute(row.plan_id))}>{row.plan_name}</InlineLinkTo>
                  </td>
                  <td>{row.plan_code}</td>
                  <td>
                    <span className="inline-flex flex-wrap items-center gap-2">
                      <span>
                        {row.customer_classes.length === 0
                          ? t("rating.rs.everyClass")
                          : row.customer_classes.join(", ")}
                      </span>
                      {row.class_differs && (
                        <StatusPill tone="warning">{t("rating.rs.plans.classDiffers")}</StatusPill>
                      )}
                    </span>
                  </td>
                  <td>
                    <StatusPill tone={row.status === "published" ? "success" : "neutral"}>
                      {t(`rating.plan.status.${row.status}`, { defaultValue: row.status })}
                    </StatusPill>
                  </td>
                  <td className={NUM}>{formatQuantity(String(row.units))}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
          {/* NFR-3 — the server pages; the footer appears once there is more
              than one page, as on every other list of a few rows. */}
          {(plansQuery.data?.count ?? 0) > per && (
            <ListPager
              page={page}
              per={per}
              total={plansQuery.data?.count ?? 0}
              onPage={setPage}
              onPer={(next) => {
                setPer(next);
                setPage(1);
              }}
            />
          )}
        </>
      )}
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-004@0b56fac (CR-157-BRC10 wave B)
// generated: 2026-10-01 by the CR-157-BRC10 wave B lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest RateScheduleDetail / RateSchedulesTable✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
