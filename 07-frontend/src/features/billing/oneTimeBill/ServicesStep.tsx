// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/*-2-services*.png (inventory.md §3)
// Design:  11-one-time-bill-redesign.md §3 (services decision table), §4 (step 2 by kind)
// Plan:    12-one-time-bill-build-plan.md F6–F10
// Rules:   B14 rules 21, 31, 33, 43, 44 · CLAUDE.md rules 2 (money 2 dp on
//          screen) and 3 (a quantity always carries its unit)
// ───────────────────────────────────────────────────────
/**
 * STEP 2 — Services, Rates, Move-in charges (the three collapsible, in that
 * order, PO 2026-09-30), then Readings, then Periods / Settlement / Evidence /
 * Charge as the kind needs.
 *
 * Every row here is the SERVER's — `preview.services`, `.rates`, `.readings`.
 * The screen groups, counts and formats; it never decides whether a service is
 * billed, and it never types a list of services (skill §12).
 *
 * ⚠ **A READING IS SAVED BY METER READS, NEVER BY BILLING** (design §4 rule for
 * every kind). The inputs here only hold what the clerk typed; the page saves
 * them through `/read-batches` on Continue.
 */
import { Link } from "react-router-dom";
import { Fragment, useState } from "react";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

import type {
  OneTimeBillCharge,
  OneTimeBillKind,
  OneTimeBillMoveInCharges,
  OneTimeBillPeriodRow,
  OneTimeBillPreview,
  OneTimeBillRateRow,
  OneTimeBillReadingRow,
  OneTimeBillReadingStatus,
  OneTimeBillServiceRow,
  OneTimeBillSettlement,
  OneTimeBillWarning,
} from "@/api/billingOpsEndpoints";
import { Button } from "@/components/Button";
import { FactBlock } from "@/components/FactBlock";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";
import { sumAmounts } from "@/components/moneyMath";
import { formatPercent } from "@/components/PercentCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { formatQuantity } from "@/components/UnitCell";
import { MeterReadingEntry } from "@/features/metering/MeterReadingEntry";

import { editableRoles, footingShares, lastPeriodIndex, readingKey, serviceCounts } from "./oneTimeBillModel";
import type { OneTimeBillForm } from "./oneTimeBillModel";
import {
  CollapsiblePanel,
  OTB_TABLE,
  OtbPanel,
  PanelAside,
  ServiceLabel,
  ServiceSwatch,
  TableScroll,
  WarningNote,
  day,
  money,
  plainReading,
  rateMoney,
  serviceName,
  span,
} from "./oneTimeBillShared";
import type { OtbFormat } from "./oneTimeBillShared";

const GREY_ROW = "text-neutral-600";

// ── Services ────────────────────────────────────────────────────────────────

function serviceStatusPill(row: OneTimeBillServiceRow, t: Translator, fmt: OtbFormat): ReactNode {
  switch (row.status) {
    case "billed":
      return <StatusPill tone="success">{billedWords(row, t)}</StatusPill>;
    case "billed_base_zero":
      return (
        <StatusPill tone="warning">
          {t("billing.oneTimeBill.services.status.baseZero", { amount: money("0", fmt) })}
        </StatusPill>
      );
    case "follows_basis":
      return (
        <StatusPill tone="info">
          {t("billing.oneTimeBill.services.status.follows", {
            service: serviceName(row.basis_service ?? "", t),
          })}
        </StatusPill>
      );
    case "not_in_service":
      return <StatusPill tone="neutral">{t("billing.oneTimeBill.services.status.notInService")}</StatusPill>;
    default:
      return <StatusPill tone="neutral">{t("billing.oneTimeBill.services.status.notTaken")}</StatusPill>;
  }
}

/** `Billed · 2 meters`, `Billed · 1 cart` — the asset NOUN, not `2` or
 *  `2 assets` (DEF-BIL-8316). A service the server gives no kind keeps the
 *  plain word. */
function billedWords(row: OneTimeBillServiceRow, t: Translator): string {
  // DEF-BIL-10221 — a summed capacity reads its installed total, `Billed ·
  // 57.84 kW`, the quantity the bill line prices.
  if (row.installed) {
    return t("billing.oneTimeBill.services.status.billedCounted", {
      count: row.installed.quantity,
      unit: row.installed.unit,
    });
  }
  if (row.asset_kind === "count" && row.count_unit) {
    return t("billing.oneTimeBill.services.status.billedCounted", {
      count: Math.max(row.count, row.assets.length),
      unit: row.count_unit,
    });
  }
  if (row.asset_kind === "meter" && row.count > 1) {
    return t("billing.oneTimeBill.services.status.billedMeters", { count: row.count });
  }
  return row.count > 1
    ? t("billing.oneTimeBill.services.status.billedCount", { count: row.count })
    : t("billing.oneTimeBill.services.status.billed");
}

function assetText(row: OneTimeBillServiceRow, t: Translator): string {
  if (row.assets.length === 0) {
    return row.status === "follows_basis"
      ? t("billing.oneTimeBill.services.asset.notNeeded")
      : t("billing.oneTimeBill.services.asset.none");
  }
  const labels = row.assets.map((asset) => asset.label).join(", ");
  // DEF-BIL-8316 — `2 meters · W-10442, W-10443`, `Meter E-55120`,
  // `1 cart · CART-J70A1`: the noun the server names, never `2 assets`.
  if (row.asset_kind === "count" && row.count_unit) {
    return t("billing.oneTimeBill.services.asset.counted", {
      count: row.assets.length,
      unit: row.count_unit,
      labels,
    });
  }
  if (row.asset_kind === "meter") {
    return row.assets.length > 1
      ? t("billing.oneTimeBill.services.asset.meters", { count: row.assets.length, labels })
      : t("billing.oneTimeBill.services.asset.meter", { label: labels });
  }
  return row.assets.length > 1
    ? t("billing.oneTimeBill.services.asset.many", { count: row.assets.length, labels })
    : labels;
}

function onBillText(row: OneTimeBillServiceRow, t: Translator, fmt: OtbFormat): string {
  switch (row.status) {
    case "billed":
      return row.count > 1
        ? t("billing.oneTimeBill.services.onBill.lines", { count: row.count })
        : t("billing.oneTimeBill.services.onBill.usageBase");
    case "billed_base_zero":
      return t("billing.oneTimeBill.services.onBill.baseZero", { amount: money("0", fmt) });
    case "follows_basis":
      return t("billing.oneTimeBill.services.onBill.follows", {
        service: serviceName(row.basis_service ?? "", t),
      });
    case "not_in_service":
      return t("billing.oneTimeBill.services.onBill.noLineZero", { amount: money("0", fmt) });
    default:
      return t("billing.oneTimeBill.services.onBill.noLine");
  }
}

export function servicesAside(services: readonly OneTimeBillServiceRow[], t: Translator): string {
  const counts = serviceCounts(services);
  return [
    t("billing.oneTimeBill.services.aside.billed", { count: counts.billed }),
    t("billing.oneTimeBill.services.aside.notInService", { count: counts.notInService }),
    t("billing.oneTimeBill.services.aside.notTaken", { count: counts.notTaken }),
  ].join(" · ");
}

export function ServicesTable(props: {
  services: readonly OneTimeBillServiceRow[];
  warnings: readonly OneTimeBillWarning[];
  t: Translator;
  fmt: OtbFormat;
}) {
  const { t, fmt } = props;
  return (
    <CollapsiblePanel
      id="services"
      title={t("billing.oneTimeBill.services.title")}
      aside={<PanelAside>{servicesAside(props.services, t)}</PanelAside>}
      toggleLabel={t("billing.oneTimeBill.services.title")}
    >
      <TableScroll>
        <PlainTable className={OTB_TABLE}>
          <thead>
            <tr>
              <th scope="col">{t("billing.oneTimeBill.services.col.service")}</th>
              <th scope="col">{t("billing.oneTimeBill.services.col.asset")}</th>
              <th scope="col">{t("billing.oneTimeBill.services.col.status")}</th>
              <th scope="col">{t("billing.oneTimeBill.services.col.onBill")}</th>
            </tr>
          </thead>
          <tbody>
            {props.services.map((row) => {
              const grey = row.status === "not_in_service" || row.status === "not_taken";
              return (
                <tr key={row.service} className={grey ? GREY_ROW : undefined} data-service-row={row.service}>
                  <td>
                    <ServiceLabel code={row.service} t={t} strong />
                  </td>
                  <td>{assetText(row, t)}</td>
                  <td>{serviceStatusPill(row, t, fmt)}</td>
                  <td>{onBillText(row, t, fmt)}</td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      </TableScroll>
      <WarningNote warnings={props.warnings} t={t} />
    </CollapsiblePanel>
  );
}

// ── Rates ───────────────────────────────────────────────────────────────────

function usageRateLines(row: OneTimeBillRateRow, t: Translator, fmt: OtbFormat): string[] {
  const rate = row.usage_rate;
  if (rate === null) return [];
  if (rate.tiers !== undefined && rate.tiers.length > 0) {
    return rate.tiers.map((tier) => {
      const price = rateMoney(tier.price, fmt);
      return tier.up_to === null
        ? t("billing.oneTimeBill.rates.tierAbove", { price, unit: tier.unit })
        : t("billing.oneTimeBill.rates.tierUpTo", {
            price,
            unit: tier.unit,
            upTo: formatQuantity(tier.up_to),
          });
    });
  }
  if (rate.percent !== undefined) {
    return [
      t("billing.oneTimeBill.rates.percentOf", {
        percent: formatPercent(rate.percent, "points"),
        service: serviceName(rate.basis_service ?? "", t),
      }),
    ];
  }
  if (rate.price !== undefined) {
    return [
      t("billing.oneTimeBill.rates.perUnit", {
        price: rateMoney(rate.price, fmt),
        unit: rate.unit ?? "",
      }),
    ];
  }
  return [];
}

function baseChargeCell(row: OneTimeBillRateRow, t: Translator, fmt: OtbFormat): ReactNode {
  const base = row.base_charge;
  if (base === null) return "—";
  if (!base.set) {
    return (
      <StatusPill tone="warning">
        {t("billing.oneTimeBill.rates.baseNotSet", { amount: money("0", fmt) })}
      </StatusPill>
    );
  }
  const parts = [money(base.amount, fmt)];
  if (base.code !== null) parts.push(base.code);
  let text = parts.join(" · ");
  if (base.per_asset) text = t("billing.oneTimeBill.rates.basePerAsset", { base: text });
  if (base.prorated !== null) {
    text = t("billing.oneTimeBill.rates.baseProrated", { base: text, fraction: base.prorated });
  }
  return text;
}

/** A price version as the drawing's SHORT cell — the service and the day its
 *  prices started (`Water · from Jul 16, 2026`) — where the server says when;
 *  the schedule's long name otherwise (DEF-BIL-8316). No ordinal is invented:
 *  rating stores none. */
function versionLabel(
  row: OneTimeBillRateRow,
  version: { label: string; from: string | null },
  t: Translator,
  fmt: OtbFormat,
): string {
  if (version.from === null || version.from === "") return version.label;
  return t("billing.oneTimeBill.rates.versionShort", {
    service: serviceName(row.service, t),
    date: day(version.from, fmt),
  });
}

function versionsCell(row: OneTimeBillRateRow, t: Translator, fmt: OtbFormat): ReactNode {
  if (row.versions.length === 0) return "—";
  const labels = row.versions.map((version) => versionLabel(row, version, t, fmt)).join(" → ");
  if (row.versions.length === 1) return labels;
  return (
    <span className="flex flex-col items-start gap-1">
      <span>{labels}</span>
      <StatusPill tone="info">
        {/* DEF-BIL-10067 (b) — EVERY cut, not only the first: electric cut on
            15 and 20 Sep read "Split 09/15/2026" (after-walk 2026-10-12). */}
        {t("billing.oneTimeBill.rates.split", {
          date: row.versions
            .slice(1)
            .map((version) => day(version.from, fmt))
            .join(", "),
        })}
      </StatusPill>
    </span>
  );
}

export function RatesTable(props: {
  rates: readonly OneTimeBillRateRow[];
  plan: string | null;
  perPeriod: boolean;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { t, fmt } = props;
  const total = sumAmounts(props.rates.map((row) => row.amount));
  const aside = [
    props.plan,
    props.perPeriod ? t("billing.oneTimeBill.rates.perPeriod") : null,
    money(total, fmt),
  ]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
  return (
    <CollapsiblePanel
      id="rates"
      title={t("billing.oneTimeBill.rates.title")}
      aside={<PanelAside>{aside}</PanelAside>}
      toggleLabel={t("billing.oneTimeBill.rates.title")}
    >
      <TableScroll>
        <PlainTable className={OTB_TABLE}>
          <thead>
            <tr>
              <th scope="col">{t("billing.oneTimeBill.rates.col.serviceMeter")}</th>
              <th scope="col">{t("billing.oneTimeBill.rates.col.rateType")}</th>
              <th scope="col">{t("billing.oneTimeBill.rates.col.usageRate")}</th>
              <th scope="col">{t("billing.oneTimeBill.rates.col.base")}</th>
              <th scope="col">{t("billing.oneTimeBill.rates.col.minimum")}</th>
              <th scope="col">{t("billing.oneTimeBill.rates.col.version")}</th>
              <th scope="col" data-num="">
                {t("billing.oneTimeBill.rates.col.amount")}
              </th>
            </tr>
          </thead>
          <tbody>
            {props.rates.map((row, index) => {
              const suffix =
                row.asset_label ??
                (row.rate_type === null ? t("billing.oneTimeBill.rates.noAsset") : undefined);
              const key = `${row.service}-${row.asset_id ?? index}`;
              if (row.rate_type === null) {
                return (
                  <tr key={key} className={GREY_ROW} data-rate-row={row.service}>
                    <td>
                      <ServiceLabel code={row.service} t={t} strong suffix={suffix} />
                    </td>
                    <td colSpan={5}>{t("billing.oneTimeBill.rates.noRate")}</td>
                    <td data-num="">{money(row.amount, fmt)}</td>
                  </tr>
                );
              }
              return (
                <Fragment key={key}>
                  <tr data-rate-row={row.service}>
                    <td>
                      <ServiceLabel code={row.service} t={t} strong suffix={suffix} />
                    </td>
                    <td>{t(`billing.oneTimeBill.rates.type.${row.rate_type}`)}</td>
                    <td>
                      {usageRateLines(row, t, fmt).map((line) => (
                        <span key={line} className="block">
                          {line}
                        </span>
                      ))}
                    </td>
                    <td>{baseChargeCell(row, t, fmt)}</td>
                    <td>{row.minimum === null ? t("billing.oneTimeBill.rates.none") : money(row.minimum, fmt)}</td>
                    <td>{versionsCell(row, t, fmt)}</td>
                    <td data-num="">{money(row.amount, fmt)}</td>
                  </tr>
                  {/* DEF-BIL-10067 OTB-2/3/4 (PO 2026-10-12, *"this is okay"*) —
                      a service cut at ITS OWN rate change shows one line per
                      part: its dates, its usage share, its rate and its
                      amount, from the split the bill was priced on. */}
                  {(row.parts ?? []).map((part, partIndex, parts) => (
                    <tr
                      key={`${key}-${part.period_start}`}
                      className="text-neutral-700"
                      data-rate-part={`${row.service}:${part.period_start}`}
                    >
                      <td className="pl-8">{span(part.period_start, part.period_end, fmt)}</td>
                      <td>
                        {/* DEF-BIL-10067 (a) — the shown shares foot to the
                            read: the last part takes the remainder. */}
                        {part.quantity === null
                          ? "—"
                          : `${formatQuantity(
                              footingShares(parts.map((each) => each.quantity))[partIndex] ?? part.quantity,
                            )} ${part.unit ?? ""}`}
                      </td>
                      <td>
                        {usageRateLines({ ...row, usage_rate: part.usage_rate }, t, fmt).map((line) => (
                          <span key={line} className="block">
                            {line}
                          </span>
                        ))}
                      </td>
                      <td />
                      <td />
                      <td>{versionLabel(row, { label: part.version_label, from: part.version_from }, t, fmt)}</td>
                      <td data-num="">{money(part.amount, fmt)}</td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
            <tr data-total="">
              <td colSpan={6}>{t("billing.oneTimeBill.rates.beforeTax")}</td>
              <td data-num="">{money(total, fmt)}</td>
            </tr>
          </tbody>
        </PlainTable>
      </TableScroll>
    </CollapsiblePanel>
  );
}

// ── Move-in charges (first bill) ────────────────────────────────────────────

export function MoveInChargesPanel(props: {
  charges: OneTimeBillMoveInCharges;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { charges, t, fmt } = props;
  const total = sumAmounts(charges.lines.map((line) => line.amount));
  return (
    <CollapsiblePanel
      id="move-in"
      title={t("billing.oneTimeBill.moveIn.title")}
      aside={<PanelAside>{t("billing.oneTimeBill.moveIn.aside", { amount: money(total, fmt) })}</PanelAside>}
      toggleLabel={t("billing.oneTimeBill.moveIn.title")}
    >
      <FactBlock
        name="otb-move-in"
        facts={[
          { id: "moved-in", label: t("billing.oneTimeBill.moveIn.date"), value: day(charges.moved_in_on, fmt) },
          { id: "asked", label: t("billing.oneTimeBill.moveIn.asked"), value: money(charges.deposit_asked, fmt) },
          { id: "paid", label: t("billing.oneTimeBill.moveIn.paid"), value: money(charges.deposit_paid, fmt) },
        ]}
      />
      <div className="mt-3">
        <TableScroll>
          <PlainTable className={OTB_TABLE}>
            <thead>
              <tr>
                <th scope="col">{t("billing.oneTimeBill.moveIn.col.charge")}</th>
                <th scope="col">{t("billing.oneTimeBill.moveIn.col.type")}</th>
                <th scope="col">{t("billing.oneTimeBill.moveIn.col.basis")}</th>
                <th scope="col" data-num="">
                  {t("billing.oneTimeBill.moveIn.col.amount")}
                </th>
              </tr>
            </thead>
            <tbody>
              {charges.lines.map((line, index) => (
                <tr key={`${line.kind}-${index}`}>
                  <td>{line.label}</td>
                  <td>{t(`billing.oneTimeBill.moveIn.type.${line.kind}`)}</td>
                  <td>
                    {line.kind === "deposit"
                      ? t("billing.oneTimeBill.moveIn.depositBasis", {
                          asked: money(charges.deposit_asked, fmt),
                          paid: money(charges.deposit_paid, fmt),
                        })
                      : t("billing.oneTimeBill.moveIn.feeBasis", { code: line.code ?? "—" })}
                  </td>
                  <td data-num="">{money(line.amount, fmt)}</td>
                </tr>
              ))}
              <tr data-total="">
                <td colSpan={3}>{t("billing.oneTimeBill.moveIn.total")}</td>
                <td data-num="">{money(total, fmt)}</td>
              </tr>
            </tbody>
          </PlainTable>
        </TableScroll>
      </div>
    </CollapsiblePanel>
  );
}

// ── Readings ────────────────────────────────────────────────────────────────

const READING_STATUS_TONE: Record<OneTimeBillReadingStatus, StatusTone> = {
  accepted: "success",
  actual: "success",
  refused: "danger",
  waiting: "neutral",
  estimated: "warning",
  assessed: "warning",
};

function ReadingStatusPill(props: { row: OneTimeBillReadingRow; t: Translator }) {
  const { row, t } = props;
  const label =
    row.status === "refused" && row.refusal_key !== null
      ? t(row.refusal_key, { defaultValue: t("billing.oneTimeBill.readings.status.refused") })
      : t(`billing.oneTimeBill.readings.status.${row.status}`);
  return <StatusPill tone={READING_STATUS_TONE[row.status]}>{label}</StatusPill>;
}

function usageText(row: OneTimeBillReadingRow, typed = ""): string {
  const live = liveUsage(row.previous.value, typed);
  if (live !== null) return `${formatQuantity(live)} ${row.unit}`;
  return row.usage === null ? "—" : `${formatQuantity(row.usage)} ${row.unit}`;
}

/**
 * `DEF-BIL-10067` OTB-1 (PO 2026-10-12) — the usage RECALCULATES as the
 * reading is typed: 4.6 over 2.9 reads **1.7 kgal** at once, not the 5.1 the
 * saved read gave. Exact decimal arithmetic on the strings (`sumAmounts`),
 * never a float; `null` (show the server's figure) while the box is empty, not
 * a number, or there is no previous reading to subtract from. A typed reading
 * BELOW the previous one shows its negative difference and the server's
 * rollover check decides what it means — nothing here guesses a rollover.
 */
export function liveUsage(previous: string | null, typed: string): string | null {
  const value = typed.trim();
  if (previous === null || value === "" || !/^-?\d+(\.\d+)?$/.test(value)) return null;
  const negated = previous.trim().startsWith("-") ? previous.trim().slice(1) : `-${previous.trim()}`;
  return sumAmounts([value, negated]);
}

function MeterCell(props: { row: OneTimeBillReadingRow; service: string | null }) {
  return (
    <span className="flex flex-col whitespace-nowrap">
      <span className="inline-flex items-center gap-2 font-heading font-semibold">
        {props.service !== null && <ServiceSwatch code={props.service} />}
        {props.row.label}
      </span>
      <span className="text-sm text-neutral-700">{props.row.unit}</span>
    </span>
  );
}

/** Which service a meter belongs to, read off the services table — so the
 *  reading row carries the same colour square as its service. */
function serviceOf(asset: string, services: readonly OneTimeBillServiceRow[] | null): string | null {
  return services?.find((row) => row.assets.some((a) => a.asset_id === asset))?.service ?? null;
}

const NEEDED_TONE: Record<string, StatusTone> = {
  every_meter: "info",
  move_in_and_new: "info",
  final: "info",
  last_period: "info",
  none: "neutral",
};

type ReadingsChange = (key: string, patch: { value?: string; readAt?: string }) => void;

/** DEF-BIL-8562 — ask for (service) or withdraw (null) a meter's own estimate. */
type EstimateChange = (assetId: string, service: string | null) => void;

function readingValue(form: OneTimeBillForm, key: string): { value: string; readAt: string } {
  return form.readings[key] ?? { value: "", readAt: "" };
}

/** The date a window row's reading is taken on: the clerk's, else the bill's. */
function readDateOf(current: { readAt: string }, row: OneTimeBillReadingRow): string {
  return current.readAt !== "" ? current.readAt : (row.current.read_at ?? "");
}

/** One-window readings — interim, first bill, final: one row per meter. */
function WindowReadings(props: {
  kind: OneTimeBillKind;
  rows: readonly OneTimeBillReadingRow[];
  services: readonly OneTimeBillServiceRow[] | null;
  movedInOn: string | null;
  form: OneTimeBillForm;
  onChange: ReadingsChange;
  onEstimate?: EstimateChange;
  client: ApiClient;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { kind, t, fmt } = props;
  const estimates = props.form.estimates ?? {};
  /** `DEF-MET-10183` — which rows hold the head-end's reading (and its date).
   *  Screen state only: the form keeps `{value, readAt}`, which is all the
   *  read batch needs. */
  const [fetchedRows, setFetchedRows] = useState<Record<string, boolean>>({});
  const previousHead =
    kind === "first"
      ? t("billing.oneTimeBill.readings.col.moveInReading")
      : kind === "final"
        ? t("billing.oneTimeBill.readings.col.lastBilled")
        : t("billing.oneTimeBill.readings.col.previous");
  return (
    <TableScroll>
      <PlainTable className={OTB_TABLE}>
        <thead>
          <tr>
            <th scope="col">{t("billing.oneTimeBill.readings.col.meter")}</th>
            <th scope="col" data-num="">
              {previousHead}
            </th>
            <th scope="col">{t("billing.oneTimeBill.readings.col.readOn")}</th>
            {/* ⚠ READING BEFORE ITS DATE since `DEF-MET-10183` (2026-10-17):
                the two cells are now ONE shared `MeterReadingEntry` (PO, *"use
                same code components"*), which draws Fetch, the reading, then
                the date — so the headings follow the order the piece draws. */}
            <th scope="col">
              {kind === "final"
                ? t("billing.oneTimeBill.readings.col.finalReading")
                : t("billing.oneTimeBill.readings.col.newReading")}
              <span className="text-accent" aria-hidden="true">
                {" *"}
              </span>
            </th>
            <th scope="col">
              {kind === "final"
                ? t("billing.oneTimeBill.readings.col.moveOutDate")
                : t("billing.oneTimeBill.readings.col.newReadDate")}
            </th>
            <th scope="col" data-num="">
              {t("billing.oneTimeBill.readings.col.usage")}
            </th>
            <th scope="col">{t("billing.oneTimeBill.readings.col.check")}</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => {
            const roles = editableRoles(kind, row, null);
            const currentKey = readingKey(row, "current");
            const moveInKey = readingKey(row, "move_in");
            const current = readingValue(props.form, currentKey);
            const refused = row.status === "refused";
            return (
              <tr key={row.asset_id} data-reading-row={row.label}>
                <td>
                  <MeterCell row={row} service={serviceOf(row.asset_id, props.services)} />
                </td>
                <td data-num="">
                  {roles.includes("move_in") ? (
                    <span className="flex flex-col items-end gap-1">
                      <TextField
                        id={`reading-${moveInKey}`}
                        label={t("billing.oneTimeBill.readings.moveInFor", { meter: row.label })}
                        labelHidden
                        numeric
                        value={readingValue(props.form, moveInKey).value}
                        onChange={(value) =>
                          props.onChange(moveInKey, { value, readAt: props.movedInOn ?? "" })
                        }
                      />
                      <StatusPill tone="warning">{t("billing.oneTimeBill.readings.noneOnFile")}</StatusPill>
                    </span>
                  ) : row.previous.value === null ? (
                    "—"
                  ) : (
                    formatQuantity(row.previous.value)
                  )}
                </td>
                <td>{day(kind === "first" ? (props.movedInOn ?? row.previous.read_at) : row.previous.read_at, fmt)}</td>
                {kind === "interim" && estimates[row.asset_id] !== undefined && row.current.value === null ? (
                  <>
                    <td>
                      {/* DEF-BIL-8562 — this meter is billed on its own estimate. */}
                      <span className="flex flex-col items-start gap-1" data-otb-estimated={row.label}>
                        <StatusPill tone="warning">{t("billing.oneTimeBill.readings.status.estimated")}</StatusPill>
                        <Button size="sm" onClick={() => props.onEstimate?.(row.asset_id, null)}>
                          {t("billing.oneTimeBill.readings.typeInstead")}
                        </Button>
                      </span>
                    </td>
                    <td>
                      {row.current.fixed_date ? (
                        day(row.current.read_at, fmt)
                      ) : (
                        <DatePickerField
                          id={`read-date-${currentKey}`}
                          label={t("billing.oneTimeBill.readings.dateFor", { meter: row.label })}
                          labelHidden
                          value={current.readAt !== "" ? current.readAt : (row.current.read_at ?? "")}
                          onChange={(readAt) => props.onChange(currentKey, { readAt })}
                          dateFormat={fmt.dateFormat}
                        />
                      )}
                    </td>
                  </>
                ) : (
                  <>
                    {/* ⚠ **THE SHARED READING PIECE — `DEF-MET-10183`** (PO
                        2026-10-17, *"use same code components"* … *"for meter
                        reading, date and fetch"*). Fetch asks the head-end AS OF
                        this row's read date — the bill's read date — so a
                        later reading never lands on this bill; a fetch fills
                        the reading AND the head-end's own date. A row whose
                        date the bill fixes (a move-out's) keeps that date as
                        text in its own cell. The ids are the ones this table
                        always used, so nothing that addresses them moves. */}
                    <td colSpan={row.current.fixed_date ? 1 : 2}>
                      <span className="flex flex-col items-start gap-1">
                        <MeterReadingEntry
                          meterNo={row.label}
                          assetId={row.asset_id}
                          unit={row.unit}
                          value={current.value !== "" ? current.value : plainReading(row.current.value)}
                          readDate={readDateOf(current, row)}
                          fetched={fetchedRows[currentKey] === true}
                          defaultReadDate={row.current.read_at ?? ""}
                          // The meter's previous reading, which this row's own
                          // Previous column already prints — so it is passed
                          // as data and not drawn again (no `showLastReading`).
                          // Its day is the date picker's floor: a new reading
                          // dated before the one it is measured from has no
                          // usage to bill.
                          lastReading={{ value: row.previous.value, readAt: row.previous.read_at }}
                          minDate={row.previous.read_at?.slice(0, 10) ?? undefined}
                          asOf={readDateOf(current, row)}
                          showFetch
                          showReadDate={!row.current.fixed_date}
                          labelsHidden
                          readingLabel={t("billing.oneTimeBill.readings.readingFor", { meter: row.label })}
                          dateLabel={t("billing.oneTimeBill.readings.dateFor", { meter: row.label })}
                          valueId={`reading-${currentKey}`}
                          dateId={`read-date-${currentKey}`}
                          onChange={(next) => {
                            setFetchedRows((was) => ({ ...was, [currentKey]: next.fetched }));
                            props.onChange(currentKey, {
                              value: next.value,
                              readAt: row.current.fixed_date ? (row.current.read_at ?? "") : next.readDate,
                            });
                          }}
                          client={props.client}
                          t={t}
                          timeZone={fmt.timeZone}
                          dateFormat={fmt.dateFormat}
                        />
                        {kind === "interim" &&
                          props.onEstimate !== undefined &&
                          row.current.value === null &&
                          current.value === "" && (
                            <Button
                              size="sm"
                              aria-label={t("billing.oneTimeBill.readings.estimateFor", { meter: row.label })}
                              onClick={() =>
                                props.onEstimate?.(row.asset_id, serviceOf(row.asset_id, props.services) ?? "")
                              }
                            >
                              {t("billing.oneTimeBill.readings.estimate")}
                            </Button>
                          )}
                      </span>
                    </td>
                    {row.current.fixed_date && <td>{day(row.current.read_at, fmt)}</td>}
                  </>
                )}
                <td data-num="">{refused ? "—" : usageText(row, current.value)}</td>
                <td>
                  <ReadingStatusPill row={row} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    </TableScroll>
  );
}

/** Per-period readings — catch-up and penalty: one block per missed period. */
function PeriodReadings(props: {
  kind: OneTimeBillKind;
  rows: readonly OneTimeBillReadingRow[];
  periods: readonly OneTimeBillPeriodRow[];
  services: readonly OneTimeBillServiceRow[] | null;
  form: OneTimeBillForm;
  onChange: ReadingsChange;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { t, fmt } = props;
  const last = lastPeriodIndex(props.rows);
  return (
    <div className="flex flex-col gap-4">
      {props.periods.map((period, index) => {
        const rows = props.rows.filter((row) => row.period_index === index);
        const entering = props.kind === "backbill" && index === last;
        return (
          <div key={`${period.period_start}-${index}`} data-reading-period={index}>
            <h4 className="m-0 mb-2 flex items-center gap-2 font-heading text-base font-semibold">
              {span(period.period_start, period.period_end, fmt)}
              {entering && <StatusPill tone="info">{t("billing.oneTimeBill.readings.enter")}</StatusPill>}
            </h4>
            <TableScroll>
              <PlainTable className={OTB_TABLE}>
                <thead>
                  <tr>
                    <th scope="col">{t("billing.oneTimeBill.readings.col.meter")}</th>
                    <th scope="col" data-num="">
                      {t("billing.oneTimeBill.readings.col.startReading")}
                    </th>
                    <th scope="col">{t("billing.oneTimeBill.readings.col.startDate")}</th>
                    <th scope="col" data-num="">
                      {t("billing.oneTimeBill.readings.col.endReading")}
                    </th>
                    <th scope="col">{t("billing.oneTimeBill.readings.col.endDate")}</th>
                    <th scope="col" data-num="">
                      {t("billing.oneTimeBill.readings.col.usage")}
                    </th>
                    <th scope="col">{t("billing.oneTimeBill.readings.col.reading")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const key = readingKey(row, "last_period");
                    const typed = readingValue(props.form, key);
                    const service = serviceOf(row.asset_id, props.services);
                    return (
                      <tr key={`${row.asset_id}-${index}`} data-reading-row={row.label}>
                        <td>
                          <span className="inline-flex items-center gap-2 whitespace-nowrap font-heading font-semibold">
                            {service !== null && <ServiceSwatch code={service} />}
                            {row.label}
                          </span>
                        </td>
                        <td data-num="">
                          {row.previous.value === null ? "—" : formatQuantity(row.previous.value)}
                        </td>
                        <td>{day(row.previous.read_at, fmt)}</td>
                        <td data-num="">
                          {entering ? (
                            <TextField
                              id={`reading-${key}`}
                              label={t("billing.oneTimeBill.readings.readingFor", { meter: row.label })}
                              labelHidden
                              numeric
                              value={typed.value !== "" ? typed.value : plainReading(row.current.value)}
                              onChange={(value) =>
                                props.onChange(key, {
                                  value,
                                  readAt: typed.readAt !== "" ? typed.readAt : (row.current.read_at ?? ""),
                                })
                              }
                            />
                          ) : row.current.value === null ? (
                            "—"
                          ) : (
                            formatQuantity(row.current.value)
                          )}
                        </td>
                        <td>
                          {entering ? (
                            <DatePickerField
                              id={`read-date-${key}`}
                              label={t("billing.oneTimeBill.readings.dateFor", { meter: row.label })}
                              labelHidden
                              value={typed.readAt !== "" ? typed.readAt : (row.current.read_at ?? "")}
                              onChange={(readAt) => props.onChange(key, { readAt })}
                              dateFormat={fmt.dateFormat}
                            />
                          ) : (
                            day(row.current.read_at, fmt)
                          )}
                        </td>
                        <td data-num="">{usageText(row, entering ? typed.value : "")}</td>
                        <td>
                          <ReadingStatusPill row={row} t={t} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </PlainTable>
            </TableScroll>
          </div>
        );
      })}
    </div>
  );
}

export function ReadingsPanel(props: {
  preview: OneTimeBillPreview;
  form: OneTimeBillForm;
  onChange: ReadingsChange;
  onEstimate?: EstimateChange;
  readsHref: string;
  /** `DEF-MET-10183` — the Fetch control asks the head-end through it. */
  client?: ApiClient;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { preview, t } = props;
  const readings = preview.readings;
  if (readings === null) return null;
  const perPeriod = props.form.kind === "backbill" || props.form.kind === "penalty";
  const footnote =
    props.form.kind === "penalty"
      ? t("billing.oneTimeBill.readings.footPenalty")
      : props.form.kind === "backbill"
        ? t("billing.oneTimeBill.readings.footCatchUp")
        : t("billing.oneTimeBill.readings.foot");
  return (
    <OtbPanel
      id="readings"
      title={t("billing.oneTimeBill.readings.title")}
      aside={
        <StatusPill tone={NEEDED_TONE[readings.needed] ?? "neutral"}>
          {t(`billing.oneTimeBill.readings.needed.${readings.needed}`)}
        </StatusPill>
      }
    >
      <div className="mt-3">
        {perPeriod ? (
          <PeriodReadings
            kind={props.form.kind}
            rows={readings.rows}
            periods={preview.periods ?? []}
            services={preview.services}
            form={props.form}
            onChange={props.onChange}
            t={t}
            fmt={props.fmt}
          />
        ) : (
          <WindowReadings
            kind={props.form.kind}
            rows={readings.rows}
            services={preview.services}
            movedInOn={preview.account.moved_in_on}
            form={props.form}
            onChange={props.onChange}
            onEstimate={props.onEstimate}
            client={props.client ?? api}
            t={t}
            fmt={props.fmt}
          />
        )}
      </div>
      <p className="m-0 mt-3 text-base text-neutral-700">
        {footnote}
        {!perPeriod && (
          <>
            {" "}
            {t("billing.oneTimeBill.readings.multiRegister")}{" "}
            <Link to={props.readsHref} className="font-semibold text-accent-700 underline">
              {t("billing.oneTimeBill.readings.fullScreen")}
            </Link>
          </>
        )}
      </p>
    </OtbPanel>
  );
}

// ── Periods (catch-up, penalty) ─────────────────────────────────────────────

const PERIOD_READING_TONE: Record<OneTimeBillPeriodRow["reading"], StatusTone> = {
  actual: "success",
  estimated: "warning",
  assessed: "warning",
  waiting: "neutral",
};

export function PeriodsTable(props: { periods: readonly OneTimeBillPeriodRow[]; t: Translator; fmt: OtbFormat }) {
  const { t, fmt } = props;
  return (
    <OtbPanel
      id="periods"
      title={t("billing.oneTimeBill.periods.title")}
      aside={<PanelAside>{t("billing.oneTimeBill.periods.aside", { count: props.periods.length })}</PanelAside>}
    >
      <div className="mt-3">
        <TableScroll>
          <PlainTable className={OTB_TABLE}>
            <thead>
              <tr>
                <th scope="col">{t("billing.oneTimeBill.periods.col.period")}</th>
                <th scope="col" data-num="">
                  {t("billing.oneTimeBill.periods.col.days")}
                </th>
                <th scope="col">{t("billing.oneTimeBill.periods.col.version")}</th>
                <th scope="col">{t("billing.oneTimeBill.periods.col.reading")}</th>
                <th scope="col">{t("billing.oneTimeBill.periods.col.note")}</th>
              </tr>
            </thead>
            <tbody>
              {props.periods.map((period, index) => (
                <tr key={`${period.period_start}-${index}`}>
                  <td>{span(period.period_start, period.period_end, fmt)}</td>
                  <td data-num="">{period.days}</td>
                  <td>{period.versions.join(" · ")}</td>
                  <td>
                    <StatusPill tone={PERIOD_READING_TONE[period.reading]}>
                      {t(`billing.oneTimeBill.readings.status.${period.reading}`)}
                    </StatusPill>
                  </td>
                  <td>
                    {period.split_on === null ? (
                      "—"
                    ) : (
                      <StatusPill tone="info">
                        {t("billing.oneTimeBill.periods.split", { date: day(period.split_on, fmt) })}
                      </StatusPill>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </TableScroll>
      </div>
    </OtbPanel>
  );
}

// ── Settlement (final) ──────────────────────────────────────────────────────

/** The negative of a decimal string, for the two lines that come OFF the bill. */
function negate(amount: string): string {
  return amount.startsWith("-") ? amount.slice(1) : `-${amount}`;
}

export function SettlementPanel(props: {
  settlement: OneTimeBillSettlement;
  path: string;
  onPathChange: (path: string) => void;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { settlement, t, fmt } = props;
  const refund = settlement.remainder.startsWith("-");
  return (
    <OtbPanel
      id="settlement"
      title={t("billing.oneTimeBill.settlement.title")}
      aside={<PanelAside>{t("billing.oneTimeBill.settlement.aside")}</PanelAside>}
    >
      <div className="mt-3">
        <PlainTable className={OTB_TABLE}>
          <tbody>
            <tr>
              <td>{t("billing.oneTimeBill.settlement.thisBill")}</td>
              <td data-num="">{money(settlement.this_bill, fmt)}</td>
            </tr>
            <tr>
              <td>{t("billing.oneTimeBill.settlement.prior")}</td>
              <td data-num="">{money(settlement.prior_balance, fmt)}</td>
            </tr>
            <tr>
              <td>{t("billing.oneTimeBill.settlement.deposit")}</td>
              <td data-num="">{money(negate(settlement.deposit), fmt)}</td>
            </tr>
            <tr>
              <td>{t("billing.oneTimeBill.settlement.interest")}</td>
              <td data-num="">{money(negate(settlement.interest), fmt)}</td>
            </tr>
            <tr data-total="">
              <td>
                {refund ? t("billing.oneTimeBill.settlement.refund") : t("billing.oneTimeBill.settlement.leftToPay")}
              </td>
              <td data-num="">{money(refund ? negate(settlement.remainder) : settlement.remainder, fmt)}</td>
            </tr>
          </tbody>
        </PlainTable>
      </div>
      {settlement.paths.length > 0 && (
        <fieldset className="m-0 mt-4 border-0 p-0" data-otb-settle="">
          <legend className="mb-2 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
            {t("billing.oneTimeBill.settlement.how")}
          </legend>
          <div className="flex flex-col gap-2">
            {settlement.paths.map((path) => (
              <label key={path} className="inline-flex items-center gap-2 text-md">
                <input
                  type="radio"
                  name="otb-settlement-path"
                  value={path}
                  checked={props.path === path}
                  onChange={() => props.onPathChange(path)}
                />
                {t(`billing.oneTimeBill.settlement.path.${path}`, { defaultValue: path })}
              </label>
            ))}
          </div>
        </fieldset>
      )}
    </OtbPanel>
  );
}

/**
 * Step 1's WARNING that meters still wait for a reading — and that the next
 * step is where they are typed (DEF-BIL-8300, PO 2026-09-30: *"2 meters need
 * a reading. Enter them next."*). A warning, never a refusal: step 1 goes on.
 * Absent when every needed reading is on file.
 */
export function WaitingReadingsNote(props: { preview: OneTimeBillPreview | null; t: Translator }) {
  const waiting = (props.preview?.readings?.rows ?? []).filter((row) => row.status === "waiting").length;
  if (waiting === 0) return null;
  return (
    <p
      className="m-0 mt-4 bg-warning-100 px-4 py-3 text-base text-warning-700"
      role="status"
      data-otb-waiting-readings={waiting}
    >
      {props.t("billing.oneTimeBill.readings.needNext", { count: waiting })}
    </p>
  );
}

// ── Evidence (penalty) ──────────────────────────────────────────────────────

/** A penalty's approver as the clerk left it: a staff user picked from the
 *  list, or a name typed — RECORDED, never required (PO 2026-09-30). */
export interface ApproverChoice {
  userId: string;
  name: string;
}

/** The send body's `approved_by` (contract §5), or undefined when nobody is
 *  named. A picked user wins over a typed name. */
export function approvedBy(choice: ApproverChoice): { user_id: string } | { name: string } | undefined {
  if (choice.userId !== "") return { user_id: choice.userId };
  const typed = choice.name.trim();
  return typed === "" ? undefined : { name: typed };
}

export function EvidencePanel(props: {
  found: string;
  onFoundChange: (value: string) => void;
  approver: ApproverChoice;
  onApproverChange: (value: ApproverChoice) => void;
  staff: readonly { value: string; label: string }[];
  t: Translator;
}) {
  const { t } = props;
  return (
    <OtbPanel id="evidence" title={t("billing.oneTimeBill.evidence.title")}>
      <div className="mt-3 grid grid-cols-2 gap-4">
        <TextField
          id="otb-evidence"
          label={t("billing.oneTimeBill.evidence.found")}
          multiline
          value={props.found}
          onChange={props.onFoundChange}
        />
        <div className="field">
          <label htmlFor="otb-evidence-file">{t("billing.oneTimeBill.evidence.photos")}</label>
          <input id="otb-evidence-file" type="file" className="input" aria-describedby="otb-evidence-file-help" />
          <p className="field-help mt-1.5 mb-0" id="otb-evidence-file-help">
            {t("billing.oneTimeBill.evidence.optional")}
          </p>
        </div>
      </div>
      {/* DEF-BIL-8305 — approval is RECORDED, not gated (PO 2026-09-30): the
          clerk picks a staff member or types a name, and the send carries it
          as `approved_by`. The old "Needs approval before it is sent." note
          is retired from all eleven catalogues — it described a gate that
          does not exist. */}
      <div className="mt-4 grid grid-cols-2 gap-4" data-otb-approver="">
        <SelectField
          id="otb-approved-by"
          label={t("billing.oneTimeBill.evidence.approvedBy")}
          value={props.approver.userId}
          onChange={(userId) => props.onApproverChange({ ...props.approver, userId })}
          options={[...props.staff]}
          placeholder={t("billing.oneTimeBill.evidence.approverNone")}
          help={t("billing.oneTimeBill.evidence.optional")}
        />
        <TextField
          id="otb-approved-by-name"
          label={t("billing.oneTimeBill.evidence.approverName")}
          value={props.approver.name}
          onChange={(name) => props.onApproverChange({ ...props.approver, name })}
          disabled={props.approver.userId !== ""}
        />
      </div>
    </OtbPanel>
  );
}

// ── Charge (penalty, fee) ───────────────────────────────────────────────────

export function ChargePanel(props: {
  charge: OneTimeBillCharge;
  kind: OneTimeBillKind;
  taxRate: string | null;
  note: string;
  onNoteChange: (value: string) => void;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { charge, t, fmt } = props;
  return (
    <OtbPanel
      id="charge"
      title={t("billing.oneTimeBill.charge.title")}
      aside={
        <PanelAside>
          {props.kind === "fee" ? t("billing.oneTimeBill.charge.noUsage") : t("billing.oneTimeBill.charge.optional")}
        </PanelAside>
      }
    >
      <div className="mt-3">
        <PlainTable className={OTB_TABLE}>
          <thead>
            <tr>
              <th scope="col">{t("billing.oneTimeBill.charge.col.code")}</th>
              <th scope="col">{t("billing.oneTimeBill.charge.col.charge")}</th>
              <th scope="col" data-num="">
                {t("billing.oneTimeBill.charge.col.amount")}
              </th>
              <th scope="col">{t("billing.oneTimeBill.charge.col.tax")}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{charge.code}</td>
              <td>{charge.label}</td>
              <td data-num="">{money(charge.amount, fmt)}</td>
              <td>
                {!charge.taxable
                  ? t("billing.oneTimeBill.charge.taxNone")
                  : props.taxRate === null
                    ? t("billing.oneTimeBill.charge.taxable")
                    : t("billing.oneTimeBill.charge.taxableAt", { rate: formatPercent(props.taxRate, "points") })}
              </td>
            </tr>
          </tbody>
        </PlainTable>
      </div>
      {props.kind === "fee" && (
        <div className="mt-4">
          <TextField
            id="otb-note"
            label={t("billing.oneTimeBill.charge.note")}
            value={props.note}
            onChange={props.onNoteChange}
          />
        </div>
      )}
    </OtbPanel>
  );
}
