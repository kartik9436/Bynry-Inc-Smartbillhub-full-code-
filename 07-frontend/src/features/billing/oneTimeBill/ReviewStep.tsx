// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/*-3-review.png (inventory.md §4)
// Design:  11-one-time-bill-redesign.md §1 step 3 — PO 2026-09-30, verbatim:
//          *"can you improve the Charge - maybe make it table"*
// Plan:    12-one-time-bill-build-plan.md F11
// Rules:   B14 rules 21, 31, 33, 43, 44 · CLAUDE.md rules 2 and 3
// ───────────────────────────────────────────────────────
/**
 * STEP 3 — the bill as it will print, as a TABLE: Service · Meter / asset ·
 * Charge · Quantity · Rate · Amount, rows grouped (one group per period, then
 * move-in and other charges), each group with its subtotal; then subtotal,
 * tax, total. Then Delivery.
 *
 * ⚠ **THE KICKER IS `{kind} · draft`, NOT `{kind} bill · draft`.** The mock-up
 * assembled `First bill bill · draft` by gluing ` bill` onto a kind whose name
 * already ends in it — a string fault the coordinator named as not to copy.
 */
import type { ReactNode } from "react";

import type {
  OneTimeBillDelivery,
  OneTimeBillDocument,
  OneTimeBillKind,
  OneTimeBillLine,
  OneTimeBillWarning,
} from "@/api/billingOpsEndpoints";
import { ONE_TIME_BILL_DELIVERIES } from "@/api/billingOpsEndpoints";
import { SelectField } from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";
import { formatPercent } from "@/components/PercentCell";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { DayShareNote } from "@/components/DayShareNote";
import { SizeBreakdown } from "@/components/SizeBreakdown";
import { formatQuantity } from "@/components/UnitCell";

import {
  OTB_TABLE,
  OtbPanel,
  PanelAside,
  ServiceLabel,
  TableScroll,
  WarningNote,
  day,
  money,
  rateMoney,
  span,
} from "./oneTimeBillShared";
import type { OtbFormat } from "./oneTimeBillShared";

/** A deposit or a fee is not a service line: its first cell is the charge's
 *  own name, with no colour square. */
function isChargeLine(line: OneTimeBillLine): boolean {
  return line.charge === "deposit" || line.charge === "fee";
}

function quantityCell(line: OneTimeBillLine, fmt: OtbFormat): string {
  if (line.quantity === null) return "—";
  // A base line is one of something — `1`, as drawn — whatever the counted
  // service's unit is (DEF-BIL-8315).
  if (line.charge === "base") return formatQuantity(line.quantity);
  if (line.unit !== null && line.unit !== "") return `${formatQuantity(line.quantity)} ${line.unit}`;
  // A percent line's quantity is the MONEY it is a share of (`$35.18`).
  if (line.charge === "percent") return money(line.quantity, fmt);
  return formatQuantity(line.quantity);
}

function rateCell(line: OneTimeBillLine, t: Translator, fmt: OtbFormat): string {
  if (line.flags.includes("base_not_set")) return t("billing.oneTimeBill.bill.rateNotSet");
  if (line.rate === null) return "—";
  if (line.rate === "tiered") return t("billing.oneTimeBill.bill.rateTiered");
  // DEF-BIL-8304 — a %-of-service line that carries a UNIT is priced on a
  // share of the basis QUANTITY (BR-RAT-1015: 40% of 12.2 kgal at $5.00/kgal),
  // so its rate is a unit price, not a percentage. Only a line with no unit
  // (a share of the basis CHARGE) carries its percent as the rate.
  if (line.charge === "percent" && (line.unit === null || line.unit === "")) {
    return formatPercent(line.rate, "points");
  }
  return rateMoney(line.rate, fmt);
}

/** The Charge cell's words: `Usage`, `Base`, and for a service priced by
 *  COUNT `Per cart` / `Base · per cart` (DEF-BIL-8315); a fee names its code,
 *  `Fee · RECON` (DEF-BIL-8312, US-BIL-032 TC-3). */
function chargeWords(line: OneTimeBillLine, t: Translator): string {
  const unit = line.per_unit ?? null;
  if (unit !== null && line.charge === "per_asset") return t("billing.oneTimeBill.bill.charge.perUnit", { unit });
  if (unit !== null && line.charge === "base") return t("billing.oneTimeBill.bill.charge.basePerUnit", { unit });
  const word = t(`billing.oneTimeBill.bill.charge.${line.charge}`);
  const code = line.code ?? null;
  return code !== null && code !== "" ? `${word} · ${code}` : word;
}

/** The Meter / asset cell: the meter's number, or for a counted service the
 *  count it stands for (`1 cart`). */
function assetCell(line: OneTimeBillLine): string {
  if (line.asset_label !== null) return line.asset_label;
  if (line.per_unit && line.charge === "per_asset" && line.quantity !== null) {
    return `${formatQuantity(line.quantity)} ${line.per_unit}`;
  }
  return "—";
}

function chargeCell(line: OneTimeBillLine, t: Translator): ReactNode {
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      {chargeWords(line, t)}
      {line.flags.includes("base_not_set") && (
        <StatusPill tone="warning">{t("billing.oneTimeBill.bill.flag.baseNotSet")}</StatusPill>
      )}
      {line.flags.includes("estimated") && (
        <StatusPill tone="warning">{t("billing.oneTimeBill.bill.flag.estimated")}</StatusPill>
      )}
    </span>
  );
}

export function BillPreview(props: {
  kind: OneTimeBillKind;
  bill: OneTimeBillDocument;
  customer: string;
  accountLine: string;
  billDate: string | null;
  dueDate: string | null;
  period: { start: string | null; end: string | null } | null;
  warnings: readonly OneTimeBillWarning[];
  t: Translator;
  fmt: OtbFormat;
}) {
  const { bill, t, fmt } = props;
  return (
    <OtbPanel
      id="bill"
      title={t("billing.oneTimeBill.bill.title")}
      aside={<PanelAside>{t("billing.oneTimeBill.bill.asPrinted")}</PanelAside>}
    >
      <div className="mt-3 border border-divider bg-bg" data-otb-bill="">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b-2 border-b-text p-4">
          <div>
            <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
              {t("billing.oneTimeBill.bill.kicker", { kind: t(`billing.oneTimeBill.bill.kindTitle.${props.kind}`) })}
            </p>
            <p className="m-0 mt-1 font-heading text-h4 font-semibold">{props.customer}</p>
            <p className="m-0 text-base text-neutral-700">{props.accountLine}</p>
          </div>
          <dl className="m-0 grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-base">
            <dt className="text-neutral-700">{t("billing.oneTimeBill.bill.billDate")}</dt>
            <dd className="m-0">{day(props.billDate, fmt)}</dd>
            <dt className="text-neutral-700">{t("billing.oneTimeBill.bill.dueDate")}</dt>
            <dd className="m-0 font-semibold">{day(props.dueDate, fmt)}</dd>
            {props.period !== null && (
              <>
                <dt className="text-neutral-700">{t("billing.oneTimeBill.bill.period")}</dt>
                <dd className="m-0">{span(props.period.start, props.period.end, fmt)}</dd>
              </>
            )}
          </dl>
        </div>
        <TableScroll>
          <PlainTable className={`${OTB_TABLE} border-0`}>
            <thead>
              <tr>
                <th scope="col">{t("billing.oneTimeBill.bill.col.service")}</th>
                <th scope="col">{t("billing.oneTimeBill.bill.col.meter")}</th>
                <th scope="col">{t("billing.oneTimeBill.bill.col.charge")}</th>
                <th scope="col" data-num="">
                  {t("billing.oneTimeBill.bill.col.quantity")}
                </th>
                <th scope="col" data-num="">
                  {t("billing.oneTimeBill.bill.col.rate")}
                </th>
                <th scope="col" data-num="">
                  {t("billing.oneTimeBill.bill.col.amount")}
                </th>
              </tr>
            </thead>
            {bill.groups.map((group, groupIndex) => (
              <tbody key={`${group.label}-${groupIndex}`} data-bill-group={groupIndex}>
                <tr data-total="">
                  <th scope="rowgroup" colSpan={5} className="uppercase tracking-kicker">
                    {group.period_start !== null && group.period_end !== null
                      ? span(group.period_start, group.period_end, fmt)
                      : // A dateless group's label is a stable CODE from the
                        // server (`charges`, `move_in_charges`, `other_charges`);
                        // its words are the catalogue's (B14 rule 35).
                        t(`billing.oneTimeBill.bill.group.${group.label}`, {
                          defaultValue: group.label,
                        })}
                  </th>
                  <td data-num="">{money(group.subtotal, fmt)}</td>
                </tr>
                {group.lines.map((line, lineIndex) => (
                  <tr key={lineIndex} data-bill-line={line.charge}>
                    <td>{isChargeLine(line) ? line.service : <ServiceLabel code={line.service} t={t} />}</td>
                    <td>{assetCell(line)}</td>
                    <td>
                      {chargeCell(line, t)}
                      {/* PO 2026-10-01 — size × count × base, as the sent
                          bill's line will store it (`billing/0039`). */}
                      <SizeBreakdown rows={line.breakdown} formatAmount={(amount) => rateMoney(amount, fmt)} t={t} />
                    </td>
                    <td data-num="">{quantityCell(line, fmt)}</td>
                    <td data-num="">
                      {rateCell(line, t, fmt)}
                      {/* DEF-BIL-8744 — `19/30 days` under a rate whose
                          amount was cut down by days, so the line foots. */}
                      <DayShareNote share={line.day_share} t={t} />
                    </td>
                    <td data-num="">{money(line.amount, fmt)}</td>
                  </tr>
                ))}
              </tbody>
            ))}
            <tbody data-bill-foot="">
              <tr className="text-neutral-700">
                <td colSpan={5}>{t("billing.oneTimeBill.bill.subtotal")}</td>
                <td data-num="">{money(bill.subtotal, fmt)}</td>
              </tr>
              {bill.tax.map((tax, index) => (
                <tr key={`${tax.label}-${index}`} className="text-neutral-700">
                  <td colSpan={5}>
                    {t("billing.oneTimeBill.bill.taxLine", {
                      label: tax.label,
                      rate: formatPercent(tax.rate, "points"),
                    })}
                  </td>
                  <td data-num="">{money(tax.amount, fmt)}</td>
                </tr>
              ))}
              {bill.one_time_charges !== undefined && bill.one_time_charges !== null && (
                // DEF-BIL-8565 — deposit, connection and tamper charges have a
                // footer line, so Subtotal + Tax + this = Total due.
                <tr className="text-neutral-700" data-bill-one-time="">
                  <td colSpan={5}>{t("billing.oneTimeBill.bill.oneTimeCharges")}</td>
                  <td data-num="">{money(bill.one_time_charges, fmt)}</td>
                </tr>
              )}
              <tr data-total="">
                <td colSpan={5}>{t("billing.oneTimeBill.bill.totalDue")}</td>
                <td data-num="" data-otb-total="">
                  {money(bill.total, fmt)}
                </td>
              </tr>
            </tbody>
          </PlainTable>
        </TableScroll>
      </div>
      <WarningNote warnings={props.warnings} t={t} />
    </OtbPanel>
  );
}

export function DeliveryPanel(props: {
  value: OneTimeBillDelivery;
  onChange: (value: OneTimeBillDelivery) => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <OtbPanel id="delivery" title={t("billing.oneTimeBill.delivery.title")}>
      <div className="mt-2 grid grid-cols-3 gap-4">
        <SelectField
          id="otb-delivery"
          label={t("billing.oneTimeBill.delivery.sendBy")}
          value={props.value}
          onChange={(value) => props.onChange(value as OneTimeBillDelivery)}
          options={ONE_TIME_BILL_DELIVERIES.map((delivery) => ({
            value: delivery,
            label: t(`billing.oneTimeBill.delivery.${delivery}`),
          }))}
        />
      </div>
    </OtbPanel>
  );
}
