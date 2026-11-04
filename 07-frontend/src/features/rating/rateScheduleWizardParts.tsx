// ── Trace ──────────────────────────────────────────────
// Change:   CR-157-BRC10 wave B — the pieces of the THREE-step rate-schedule
//           wizard (Details · Pricing · Review), each a component (B14 rule 43).
// Drawing:  05-prototype/rate-schedules-2026-10-01/images/40–71, read as IMAGES
//           (B14 rule 42): the summary aside on every step; step 2's *Base
//           rates* table (# · Utility service · Asset · Size · Base charge ·
//           Minimum) and *Usage rates* table per method; step 3's read-only
//           *Prices*. Figures are illustrations (rule 37); our UI standard
//           decides how each piece is built (rule 44).
// Rulings:  decision log 2026-10-01 "rate-schedule redesign" — TOU *Window* and
//           *Days* are DROPDOWNS and the register FOLLOWS the window (read-only);
//           seasonal *Starts*/*Ends* are DATE PICKERS and only month + day are
//           kept (*"Repeats every year."*); the MINIMUM is per meter size (PO
//           2026-10-01, option A) — a blank reads *No minimum*.
// Defects:  DEF-RAT-8748 — a stored bound or price is SHOWN trimmed
//           (`0.000000` → `0`, `4.409600` → `4.4096`) and never rewritten
//           until the clerk types; see `shownQuantity` / `shownRate`.
//           DEF-RAT-9119 — the per-size MINIMUM is money and shows two places
//           (`15.000000` → `15.00`) through `RateCell`'s `money`.
// Tests:    ./rateScheduleWizard3.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useRef } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ChargeRow, LookupEntry, VersionStructure } from "@/api/endpoints";
import { formatMoney } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import { trimQuantity } from "@/components/UnitCell";

import { baseAmountForSize } from "./baseCharge";
import { ChargeNote } from "./chargeCodeParts";
import { TOU_CHANNELS, nextSeasonKey } from "./RateScheduleWizard";
import type { ScheduleDraft, SeasonDraft, SizeRowDraft, TierDraft, WindowDraft } from "./RateScheduleWizard";
import { useMoneyBox } from "./ratingShared";
import type { Translator } from "./ratingShared";
import { sizeWithoutService, sortBySize } from "./sizeOrder";

// ── display helpers (DEF-RAT-8748) ─────────────────────────────────────────

/** A bound as a clerk reads it — `0.000000` → `0`, `5.500000` → `5.5`. The
 *  DRAFT keeps the stored bytes until the clerk types (US-RAT-005 TC-3). */
export function shownQuantity(value: string): string {
  return /^-?\d+(\.\d+)?$/.test(value.trim()) ? trimQuantity(value.trim()) : value;
}

/** A rate as a clerk reads it — four places, zeros kept (OQ-620(a)):
 *  `4.409600` → `4.4096`, `6.100000` → `6.1000`. Only trailing zeros past the
 *  fourth place are dropped; a typed value is never rounded. */
export function shownRate(value: string): string {
  const match = /^(-?\d+\.\d{4})(0+)$/.exec(value.trim());
  return match === null ? value : match[1];
}

const NUMBER: TableArrayColumn<unknown> = {
  key: "n",
  label: "#",
  cell: (_row, index) => <span className="text-neutral-600">{index + 1}</span>,
};

function numberColumn<Row>(): TableArrayColumn<Row> {
  return NUMBER as TableArrayColumn<Row>;
}

/** The kicker-styled fact on a table's heading (`BASE-W · 3 OF 3 PRICED`). */
function Kicker(props: { children: ReactNode }) {
  return (
    <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
      {props.children}
    </span>
  );
}

/** A right-aligned money/rate input inside a table cell. Labelled for a
 *  screen reader by its column; the header is what a sighted clerk reads. */
export function RateCell(props: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  error?: string;
  /** A MONEY box (`DEF-RAT-9119`): shows a stored `15.000000` as `15.00`
   *  through `useMoneyBox`, and posts the stored bytes until the clerk types.
   *  Absent, the box shows `value` exactly as before. */
  money?: boolean;
}) {
  const box = useMoneyBox(props.value, props.onChange);
  return (
    <input
      type="text"
      inputMode="decimal"
      className="input input-num"
      aria-label={props.label}
      aria-invalid={props.error === undefined ? undefined : true}
      title={props.error}
      placeholder={props.placeholder}
      value={props.money === true ? box.shown : props.value}
      data-cell={props.name}
      onChange={(event) => (props.money === true ? box.emit : props.onChange)(event.target.value)}
    />
  );
}

// ── the summary aside (every step, images 40–71) ───────────────────────────

function AsideRow(props: { label: string; value: ReactNode; name: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-base" data-aside-row={props.name}>
      <span className="text-neutral-700">{props.label}</span>
      <span className="text-right">{props.value}</span>
    </div>
  );
}

export function ScheduleAside(props: {
  editing: boolean;
  name: string;
  service: string;
  structure: string;
  unit: string;
  customerClass: string;
  baseCode: string;
  /** `v4`, `v3 (corrected)` — edit only. */
  version: string | null;
  sizesPriced: string;
  /** `1,306 · 3 plans` — edit only. */
  reach: string | null;
  saved: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Panel as="aside" aria-label={t("rating.rs.wiz.asideLabel")} data-rs-aside="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t(props.editing ? "rating.rs.wiz.editing" : "rating.rs.wiz.newSchedule")}
      </p>
      <p className="m-0 mt-2 font-heading text-metric-lg font-semibold break-words" data-aside-name="">
        {props.name.trim() === "" ? "—" : props.name}
      </p>
      <div className="mt-3 flex flex-col gap-1.5">
        <AsideRow name="service" label={t("rating.rs.col.service")} value={props.service || "—"} />
        <AsideRow name="structure" label={t("rating.rates.col.structure")} value={props.structure || "—"} />
        <AsideRow name="unit" label={t("rating.rs.fact.unit")} value={props.unit || "—"} />
        <AsideRow name="class" label={t("rating.rs.col.customerClass")} value={props.customerClass || "—"} />
        <AsideRow name="baseCode" label={t("rating.rs.col.baseCode")} value={props.baseCode || "—"} />
        {props.version !== null && (
          <AsideRow name="version" label={t("rating.rateDetail.versions.col.version")} value={props.version} />
        )}
      </div>
      <div className="mt-3 flex flex-col gap-1.5 border-t border-divider pt-3">
        <AsideRow name="sizes" label={t("rating.rs.kpi.sizesPriced")} value={props.sizesPriced} />
        {props.reach !== null && (
          <AsideRow name="reach" label={t("rating.rs.wiz.accountsAffected")} value={props.reach} />
        )}
      </div>
      <p className="m-0 mt-3 text-base text-neutral-700" data-aside-foot={props.saved ? "saved" : "nothing"}>
        {t(props.saved ? "rating.rs.wiz.saved" : "rating.rs.wiz.nothingSaved")}
      </p>
    </Panel>
  );
}

// ── step 2 · Base rates ─────────────────────────────────────────────────────

/** A row of the base table: a size, and on step 3 of a per-class schedule the
 *  class code it is priced from (`DEF-RAT-9118`). */
type BaseRow = SizeRowDraft & { charge?: ChargeRow };

/** Sizes priced on step 2, counted the way the View's tile counts them.
 *
 *  `DEF-RAT-9118` — with `classCharges` (a schedule priced from each class's
 *  own base code) every size counts once PER CODE, as the View's tile counts
 *  its `base_rows` (`schedule_reads.schedule_rates`). */
export function baseRowsPriced(
  draft: ScheduleDraft,
  baseCharge: ChargeRow | null,
  classCharges: readonly ChargeRow[] = [],
): { priced: number; total: number } {
  const rows = draft.size_rows.filter((row) => row.size_class !== "");
  if (rows.length === 0) {
    return { priced: 0, total: 0 };
  }
  const charges = classCharges.length > 1 ? classCharges : baseCharge === null ? [] : [baseCharge];
  const perCode = Math.max(charges.length, 1);
  const priced = rows.reduce(
    (sum, row) =>
      sum + charges.filter((charge) => baseAmountForSize(charge, row.size_class).amountDisplay !== null).length,
    0,
  );
  return { priced, total: rows.length * perCode };
}

/** `DEF-RAT-9118` — the classes a base code is read for, in the clerk's words.
 *  The code's own `applies_to_customer_classes`, every one named (BASE-W reads
 *  *Residential, Municipal*); an unscoped code reads *Every class*. */
export function classesOfCharge(charge: ChargeRow, t: Translator): string {
  const classes = charge.applies_to_customer_classes ?? [];
  if (classes.length === 0) return t("rating.rs.everyClass");
  return classes.map((code) => t(`rating.customerClass.${code}`, { defaultValue: code })).join(", ");
}

/**
 * `44`–`52`: one table, a row per size the schedule prices, `+ Add row` under
 * it (disabled with its reason once every size has a row — `52`). The base is
 * the CODE's (BR-RAT-088), read-only; a size the code does not price says *Not
 * priced* and the band under the table says what that bills (`51`). The
 * MINIMUM is the size's own (PO 2026-10-01, option A); blank is *No minimum*.
 *
 * A service with no sizes draws ONE *All sizes* row with no Add (`44`, `50`):
 * the base is the code's single amount and there is no size row to carry a
 * per-size minimum, so that cell reads *No minimum* rather than offering a box
 * nothing stores.
 */
export function BaseRatesTable(props: {
  draft: ScheduleDraft;
  sizeClasses: readonly LookupEntry[];
  baseCharge: ChargeRow | null;
  /** `DEF-RAT-9118` — a schedule that names no class and no single code is
   *  priced from EACH class's own base code (billing reads the account's class,
   *  `DEF-RAT-8833`). Two or more here: step 3 shows one row per size AND code,
   *  as View details does, and step 2's cells list every code. Fewer: unchanged. */
  classCharges?: readonly ChargeRow[];
  serviceName: string;
  assetName: string | null;
  errors: Record<string, string>;
  onPatch: (next: Partial<ScheduleDraft>) => void;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { draft, baseCharge } = props;
  const classCharges = (props.classCharges ?? []).length > 1 ? (props.classCharges ?? []) : [];
  const byClass = classCharges.length > 1;
  const nameOf = (code: string) => props.sizeClasses.find((entry) => entry.code === code)?.name ?? code;
  // Images 45 and 54 draw `5/8"`, not `Water 5/8"`: the service has its own
  // column on the same row, so a size name that opens with it reads it twice.
  const shown = (name: string) => sizeWithoutService(name, props.serviceName);
  const sized = props.sizeClasses.length > 0 || draft.size_rows.length > 0;
  // `DEF-RAT-8830` — THE ROWS ARE SORTED AS LOADED, AND THEN THEY STAY WHERE
  // THE CLERK PUT THEM. Sorting on every render moved a row the instant its
  // size was picked (a 2-yard dumpster jumped above the 96-gallon cart) and
  // re-mounted it, so focus was lost and a minimum typed into the bottom row
  // landed on another size. Every edit writes the rows back in the order shown,
  // so after the first one the draft's own order IS the sorted order plus the
  // rows added since, at the bottom where they were added. The read-only table
  // (step 3) is always sorted.
  const edited = useRef(false);
  const rows: SizeRowDraft[] = !sized
    ? [{ size_class: "", minimum_bill: "" }]
    : edited.current && props.readOnly !== true
      ? draft.size_rows
      : [
          ...sortBySize(
            draft.size_rows.filter((row) => row.size_class !== ""),
            (row) => nameOf(row.size_class),
          ),
          ...draft.size_rows.filter((row) => row.size_class === ""),
        ];
  const used = new Set(rows.map((row) => row.size_class));
  const offered = sortBySize(
    props.sizeClasses.filter((entry) => !used.has(entry.code)),
    (entry) => entry.name,
  );
  const counted = baseRowsPriced(draft, baseCharge, classCharges);
  const code = byClass ? classCharges.map((charge) => charge.code).join(" · ") : (baseCharge?.code ?? "—");
  // DEF-RAT-9118 — step 3 reads one row per size AND class code, the View's own
  // layout; each row carries the code it is priced from.
  const shownRows: BaseRow[] =
    byClass && props.readOnly === true
      ? rows.flatMap((row) => classCharges.map((charge) => ({ ...row, charge })))
      : rows;
  const fact = (
    <Kicker>
      {sized
        ? t("rating.rs.wiz.basePricedOf", { code, priced: counted.priced, total: counted.total })
        : t("rating.rs.wiz.basePricedOf", { code, priced: baseCharge === null ? 0 : 1, total: 1 })}
    </Kicker>
  );
  const priceOf = (charge: ChargeRow | null, row: SizeRowDraft): ReactNode => {
    if (charge === null) return "—";
    const base = baseAmountForSize(charge, sized ? row.size_class : null);
    if (base.amountDisplay === null) {
      return (
        <span className="bg-warning-100 px-2 py-0.5 font-heading text-xs font-semibold uppercase text-warning-700">
          {t("rating.rs.notPriced")}
        </span>
      );
    }
    return formatMoney(base.amountDisplay, "USD");
  };
  // Step 2 keeps one row per size (its minimum is the size's own): the cell
  // lists each code's price on its own line, the code beside it.
  const baseText = (row: BaseRow): ReactNode =>
    row.charge !== undefined ? (
      priceOf(row.charge, row)
    ) : byClass ? (
      <span className="flex flex-col items-end gap-1">
        {classCharges.map((charge) => (
          <span key={charge.id} className="whitespace-nowrap" data-base-class-code={charge.code}>
            {charge.code} · {priceOf(charge, row)}
          </span>
        ))}
      </span>
    ) : (
      priceOf(baseCharge, row)
    );
  const missing = counted.total - counted.priced;
  function setRows(next: SizeRowDraft[]): void {
    edited.current = true;
    props.onPatch({ size_rows: next });
  }
  function patchRow(index: number, next: Partial<SizeRowDraft>): void {
    setRows(rows.map((row, at) => (at === index ? { ...row, ...next } : row)));
  }
  const columns: TableArrayColumn<BaseRow>[] = [
    numberColumn<SizeRowDraft>(),
    {
      key: "service",
      label: t("rating.rs.wiz.col.utilityService"),
      cell: () => <span className="text-neutral-700">{props.serviceName}</span>,
    },
    {
      key: "asset",
      label: t("rating.rs.wiz.col.asset"),
      cell: () => <span className="text-neutral-700">{props.assetName ?? "—"}</span>,
    },
    {
      key: "size",
      label: t("rating.tier.size"),
      cell: (row, index) =>
        !sized ? (
          <CellStatic name="size">{t("rating.rs.allSizes")}</CellStatic>
        ) : props.readOnly === true ? (
          <CellStatic name="size">{shown(nameOf(row.size_class))}</CellStatic>
        ) : (
          <CellSelect
            name={`size-${index}`}
            label={t("rating.tier.size")}
            value={row.size_class}
            placeholder={t("rating.rs.wiz.chooseSize")}
            onChange={(size_class) => patchRow(index, { size_class })}
            options={sortBySize(
              props.sizeClasses.filter((entry) => entry.code === row.size_class || !used.has(entry.code)),
              (entry) => entry.name,
            ).map((entry) => ({ value: entry.code, label: shown(entry.name) }))}
          />
        ),
    },
    ...(byClass && props.readOnly === true
      ? [
          {
            key: "class",
            label: t("rating.rs.col.customerClass"),
            cell: (row: BaseRow) => (
              <span className="text-neutral-700" data-base-row-class="">
                {row.charge === undefined ? "" : `${classesOfCharge(row.charge, translate)} · ${row.charge.code}`}
              </span>
            ),
          },
        ]
      : []),
    {
      key: "base",
      label: t("rating.rs.col.baseCharge"),
      numeric: true,
      cell: (row) => <span className="text-neutral-700">{baseText(row)}</span>,
    },
    {
      key: "minimum",
      label: t("rating.rs.col.minimum"),
      numeric: true,
      cell: (row, index) =>
        !sized || props.readOnly === true ? (
          <span>
            {row.minimum_bill.trim() === ""
              ? t("rating.rs.noMinimum")
              : formatMoney(row.minimum_bill.trim(), "USD")}
          </span>
        ) : (
          <RateCell
            name={`minimum-${index}`}
            label={t("rating.rs.col.minimum")}
            placeholder={t("rating.rs.noMinimum")}
            money
            value={row.minimum_bill}
            onChange={(minimum_bill) => patchRow(index, { minimum_bill })}
            error={props.errors[`size_rows[${index}].minimum_bill`]}
          />
        ),
    },
  ];
  const warning =
    missing > 0 ? (
      <ChargeNote
        tone="warning"
        name="rs-not-priced"
        lead={t("rating.rs.wiz.notPricedLead", { missing, total: counted.total })}
      >
        {t("rating.rs.wiz.notPricedBilled")}
      </ChargeNote>
    ) : null;
  if (props.readOnly === true) {
    return (
      <TableArray<BaseRow>
        readOnly
        collection="rs-base-rows"
        title={t("rating.rs.wiz.prices")}
        columns={columns}
        rows={shownRows}
        rowKey={(row, index) => `${row.size_class || `all-${index}`}|${row.charge?.code ?? ""}`}
        emptyText={t("rating.rs.wiz.noSizes")}
      >
        {warning}
      </TableArray>
    );
  }
  return (
    <TableArray<BaseRow>
      collection="rs-base-rows"
      title={t("rating.rs.wiz.baseRates")}
      fact={fact}
      columns={columns}
      rows={rows}
      // By POSITION (`DEF-RAT-8830`): keyed by its size, a row was re-mounted
      // the moment its size was picked and the clerk's focus went with it.
      rowKey={(_row, index) => `row-${index}`}
      emptyText={t("rating.rs.wiz.noSizes")}
      removeLabel={t("rating.rs.wiz.removeRow")}
      rowRemoveBlocked={sized ? undefined : () => t("rating.rs.wiz.everySizeUsed")}
      onChange={(next) => setRows(sized ? next : [])}
      actions={[
        {
          key: "add-size",
          label: t("rating.rs.wiz.addRow"),
          onClick: () => setRows([...rows, { size_class: "", minimum_bill: "" }]),
          blockedReason: !sized || offered.length === 0 ? t("rating.rs.wiz.everySizeUsed") : undefined,
        },
      ]}
      footerTrailing={
        <span className="flex gap-4 text-base text-neutral-700">
          {(!sized || offered.length === 0) && <span data-every-size-used="">{t("rating.rs.wiz.everySizeUsed")}</span>}
          {(byClass || baseCharge !== null) && <span>{t("rating.rs.wiz.baseSetOn", { code })}</span>}
        </span>
      }
    >
      {warning}
      {props.errors.size_rows !== undefined && (
        <ChargeNote tone="warning" name="rs-size-rows">
          {props.errors.size_rows}
        </ChargeNote>
      )}
    </TableArray>
  );
}

// ── step 2 · Usage rates — one table per method ────────────────────────────

/** The three window names the redesign offers (`46-add-2-pricing-tou.png`).
 *  The VALUE posted is the name the server reads its register from
 *  (`services.tou_register_for_window`); the label is the app's language. */
export const TOU_WINDOWS: readonly { value: string; channel: (typeof TOU_CHANNELS)[number] }[] = [
  { value: "On-peak", channel: "tou_on" },
  { value: "Mid-peak", channel: "tou_mid" },
  { value: "Off-peak", channel: "tou_off" },
];

/** The register a window NAME sets — the server's own rule, mirrored for the
 *  read-only Register cell. A tenant's own name keeps its stated register. */
export function registerForWindow(window: Pick<WindowDraft, "label" | "channel">): string {
  const key = window.label.toLowerCase().replace(/[\s-]/g, "");
  const found = TOU_WINDOWS.find((option) => option.value.toLowerCase().replace(/[\s-]/g, "") === key);
  return found === undefined ? window.channel : found.channel;
}

const DAY_TYPE_VALUES = ["weekday", "weekend", "holiday"] as const;

/** `HH:MM` for a time picker; a stored `HH:MM:SS` loses its seconds. */
function timeValue(value: string): string {
  return value.length >= 5 ? value.slice(0, 5) : value;
}

/** A season's month + day as a date-picker value. A picker carries a year; the
 *  year shown is a display year and is never stored (decision log 2026-10-01,
 *  *"SEASONAL STARTS AND ENDS ARE DATE PICKERS"*). An END earlier than its START
 *  is a season crossing New Year and is shown in the NEXT year, so Winter reads
 *  10/01 → 04/30 of the year after. */
export function seasonPickerValue(
  month: string,
  day: string,
  displayYear: number,
): string {
  const m = Number(month);
  const d = Number(day);
  if (!Number.isInteger(m) || !Number.isInteger(d) || m < 1 || m > 12 || d < 1 || d > 31) {
    return "";
  }
  return `${displayYear}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** The month + day a picked date stores. The year is dropped on purpose. */
export function seasonFromPicker(value: string): { month: string; day: string } {
  const match = /^\d{4}-(\d{2})-(\d{2})$/.exec(value);
  if (match === null) {
    return { month: "", day: "" };
  }
  return { month: String(Number(match[1])), day: String(Number(match[2])) };
}

export function seasonEndYear(season: SeasonDraft, year: number): number {
  const start = Number(season.start_month) * 100 + Number(season.start_day);
  const end = Number(season.end_month) * 100 + Number(season.end_day);
  return end < start ? year + 1 : year;
}

export function UsageRatesEditor(props: {
  draft: ScheduleDraft;
  errors: Record<string, string>;
  displayYear: number;
  onPatch: (next: Partial<ScheduleDraft>) => void;
  /** The method's own editor where the drawn table cannot carry a ruled field
   *  (percent of another service — `BR-RAT-1030`'s basis). */
  percentEditor: ReactNode;
}) {
  const { t } = useTranslation();
  const { draft } = props;
  const unit = draft.uom.trim() === "" ? "—" : draft.uom;
  const per = t("rating.rs.usage.pricePer", { unit });
  const title = t("rating.rs.wiz.usageRates");
  const fact = <Kicker>{t(`rating.model.${draft.model}`, { defaultValue: draft.model })}</Kicker>;
  const err = (key: string) => props.errors[key];

  if (draft.model === "flat" || draft.model === "capacity") {
    const capacity = draft.model === "capacity";
    const value = capacity ? draft.capacity.rate_per_unit : (draft.tiers[0]?.unit_price ?? "");
    const label = capacity
      ? t("rating.rs.usage.pricePer", { unit: draft.capacity.unit_label.trim() || unit })
      : per;
    return (
      <TableArray<{ key: string }>
        collection="rs-usage-rows"
        title={title}
        fact={fact}
        columns={[
          numberColumn<{ key: string }>(),
          {
            key: "price",
            label,
            numeric: true,
            cell: () => (
              <RateCell
                name="price-0"
                label={label}
                value={shownRate(value)}
                error={err(capacity ? "structure.capacity.rate_per_unit" : "structure.unit_price")}
                onChange={(next) =>
                  capacity
                    ? props.onPatch({
                        capacity: {
                          unit_label: draft.capacity.unit_label.trim() || draft.uom,
                          rate_per_unit: next,
                        },
                      })
                    : props.onPatch({ tiers: [{ from_qty: "0", to_qty: "", unit_price: next }] })
                }
              />
            ),
          },
        ]}
        rows={[{ key: "one" }]}
        rowKey={(row) => row.key}
        emptyText=""
        readOnly
      />
    );
  }

  if (draft.model === "tiered") {
    const tiers = draft.tiers;
    const setTiers = (next: TierDraft[]) => props.onPatch({ tiers: next });
    const patchTier = (index: number, next: Partial<TierDraft>) =>
      setTiers(tiers.map((tier, at) => (at === index ? { ...tier, ...next } : tier)));
    return (
      <TableArray<TierDraft>
        collection="rs-usage-rows"
        title={title}
        fact={fact}
        columns={[
          numberColumn<TierDraft>(),
          {
            key: "from",
            label: t("rating.rs.usage.from", { unit }),
            numeric: true,
            cell: (tier, index) => (
              <RateCell
                name={`tier-from-${index}`}
                label={t("rating.rs.usage.from", { unit })}
                value={shownQuantity(tier.from_qty)}
                error={err(`structure.tiers[${index}].from_qty`)}
                onChange={(from_qty) => patchTier(index, { from_qty })}
              />
            ),
          },
          {
            key: "to",
            label: t("rating.rs.usage.to", { unit }),
            numeric: true,
            cell: (tier, index) => (
              <RateCell
                name={`tier-to-${index}`}
                label={t("rating.rs.usage.to", { unit })}
                value={shownQuantity(tier.to_qty)}
                error={err(`structure.tiers[${index}].to_qty`)}
                onChange={(to_qty) => patchTier(index, { to_qty })}
              />
            ),
          },
          {
            key: "price",
            label: per,
            numeric: true,
            cell: (tier, index) => (
              <RateCell
                name={`tier-price-${index}`}
                label={per}
                value={shownRate(tier.unit_price)}
                error={err(`structure.tiers[${index}].unit_price`)}
                onChange={(unit_price) => patchTier(index, { unit_price })}
              />
            ),
          },
        ]}
        rows={tiers}
        rowKey={(_tier, index) => `tier-${index}`}
        emptyText={t("rating.rs.wiz.noTiers")}
        removeLabel={t("rating.rs.wiz.removeRow")}
        onChange={setTiers}
        actions={[
          {
            key: "add-tier",
            label: t("rating.rs.wiz.addRow"),
            onClick: () =>
              setTiers([
                ...tiers,
                // A new block starts where the one above it ends (DEF-RAT-5717).
                { from_qty: tiers[tiers.length - 1]?.to_qty.trim() ?? "", to_qty: "", unit_price: "" },
              ]),
          },
        ]}
      />
    );
  }

  if (draft.model === "time_of_use") {
    const windows = draft.windows;
    const setWindows = (next: WindowDraft[]) => props.onPatch({ windows: next });
    const patchWindow = (index: number, next: Partial<WindowDraft>) =>
      setWindows(
        windows.map((window, at) => {
          if (at !== index) return window;
          const merged = { ...window, ...next };
          // The REGISTER FOLLOWS THE WINDOW — the drawn read-only column.
          return { ...merged, channel: registerForWindow(merged) };
        }),
      );
    const windowOptions = (current: string) => {
      const canonical = TOU_WINDOWS.map((option) => ({
        value: option.value,
        label: t(`rating.rs.window.${option.channel}`),
      }));
      // A tenant's own window name (BR-RAT-067) stays selectable on its row.
      return current !== "" && !TOU_WINDOWS.some((option) => option.value === current)
        ? [...canonical, { value: current, label: current }]
        : canonical;
    };
    return (
      <TableArray<WindowDraft>
        collection="rs-usage-rows"
        title={title}
        fact={fact}
        columns={[
          numberColumn<WindowDraft>(),
          {
            key: "window",
            label: t("rating.rs.usage.window"),
            // `DEF-RAT-8841` — a floor under both dropdowns: beside two time
            // pickers they were squeezed to `On-` and `We` (image 46 draws
            // `On-peak` and `Weekday` whole).
            cell: (window, index) => (
              <div className="min-w-24">
                <CellSelect
                  name={`window-${index}`}
                  label={t("rating.rs.usage.window")}
                  value={window.label}
                  placeholder={t("rating.rs.wiz.choose")}
                  options={windowOptions(window.label)}
                  onChange={(label) => patchWindow(index, { label })}
                />
              </div>
            ),
          },
          {
            key: "days",
            label: t("rating.rs.usage.days"),
            cell: (window, index) => (
              <div className="min-w-24">
                <CellSelect
                  name={`days-${index}`}
                  label={t("rating.rs.usage.days")}
                  value={window.day_type}
                  placeholder={t("rating.rs.wiz.choose")}
                  options={DAY_TYPE_VALUES.map((value) => ({ value, label: t(`rating.dayType.${value}`) }))}
                  onChange={(day_type) => patchWindow(index, { day_type })}
                />
              </div>
            ),
          },
          {
            key: "starts",
            label: t("rating.tou.start"),
            cell: (window, index) => (
              <input
                type="time"
                className="input w-28"
                aria-label={t("rating.tou.start")}
                data-cell={`starts-${index}`}
                value={timeValue(window.start_time)}
                onChange={(event) => patchWindow(index, { start_time: event.target.value })}
              />
            ),
          },
          {
            key: "ends",
            label: t("rating.tou.end"),
            cell: (window, index) => (
              <input
                type="time"
                className="input w-28"
                aria-label={t("rating.tou.end")}
                data-cell={`ends-${index}`}
                value={timeValue(window.end_time)}
                onChange={(event) => patchWindow(index, { end_time: event.target.value })}
              />
            ),
          },
          {
            key: "register",
            label: t("rating.rs.usage.register"),
            cell: (window) => {
              const channel = registerForWindow(window);
              return (
                <span className="whitespace-nowrap bg-neutral-100 px-2 py-1 text-neutral-700" data-register={channel || "none"}>
                  {channel === "" ? "—" : t(`rating.rs.window.${channel}`, { defaultValue: channel })}
                </span>
              );
            },
          },
          {
            key: "price",
            label: per,
            numeric: true,
            // `DEF-RAT-8841` — the price keeps a floor too, and the two time
            // pickers a fixed width, so no column is squeezed to nothing.
            cell: (window, index) => (
              <div className="min-w-24">
                <RateCell
                  name={`window-price-${index}`}
                  label={per}
                  value={shownRate(window.unit_price)}
                  error={err(`structure.windows[${index}].unit_price`)}
                  onChange={(unit_price) => patchWindow(index, { unit_price })}
                />
              </div>
            ),
          },
        ]}
        rows={windows}
        rowKey={(_window, index) => `window-${index}`}
        emptyText={t("rating.rs.wiz.noWindows")}
        removeLabel={t("rating.rs.wiz.removeRow")}
        onChange={setWindows}
        actions={[
          {
            key: "add-window",
            label: t("rating.rs.wiz.addRow"),
            onClick: () => {
              // The server prices a window inside a SEASON (BR-RAT-033) and
              // refuses a time-of-use schedule with none
              // (`rating.seasons.required`). Image 46 draws no season, so the
              // first window brings one whole-year season with it; a schedule
              // that already has seasons (a resumed or older one) keeps them.
              const seasons: SeasonDraft[] =
                draft.seasons.length > 0
                  ? draft.seasons
                  : [
                      {
                        key: nextSeasonKey([]),
                        label: t("rating.rs.wiz.allYear"),
                        start_month: "1",
                        start_day: "1",
                        end_month: "12",
                        end_day: "31",
                        unit_price: "",
                      },
                    ];
              props.onPatch({
                seasons,
                windows: [
                  ...windows,
                  {
                    label: "",
                    season_key: windows[windows.length - 1]?.season_key ?? seasons[0].key,
                    day_type: "weekday",
                    start_time: "",
                    end_time: "",
                    unit_price: "",
                    channel: "",
                  },
                ],
              });
            },
          },
        ]}
      >
        {props.errors["structure.windows"] !== undefined && (
          <ChargeNote tone="warning" name="rs-windows">
            {props.errors["structure.windows"]}
          </ChargeNote>
        )}
      </TableArray>
    );
  }

  if (draft.model === "seasonal") {
    const seasons = draft.seasons;
    const setSeasons = (next: SeasonDraft[]) => props.onPatch({ seasons: next });
    const patchSeason = (index: number, next: Partial<SeasonDraft>) =>
      setSeasons(seasons.map((season, at) => (at === index ? { ...season, ...next } : season)));
    return (
      <TableArray<SeasonDraft>
        collection="rs-usage-rows"
        title={title}
        fact={fact}
        note={t("rating.rs.wiz.repeatsEveryYear")}
        columns={[
          numberColumn<SeasonDraft>(),
          {
            key: "season",
            label: t("rating.tou.season"),
            cell: (season, index) => (
              <input
                type="text"
                className="input"
                aria-label={t("rating.tou.season")}
                data-cell={`season-${index}`}
                value={season.label}
                onChange={(event) => patchSeason(index, { label: event.target.value })}
              />
            ),
          },
          {
            key: "starts",
            label: t("rating.tou.start"),
            cell: (season, index) => (
              <input
                type="date"
                className="input"
                aria-label={t("rating.tou.start")}
                data-cell={`season-start-${index}`}
                value={seasonPickerValue(season.start_month, season.start_day, props.displayYear)}
                onChange={(event) => {
                  const picked = seasonFromPicker(event.target.value);
                  patchSeason(index, { start_month: picked.month, start_day: picked.day });
                }}
              />
            ),
          },
          {
            key: "ends",
            label: t("rating.tou.end"),
            cell: (season, index) => (
              <input
                type="date"
                className="input"
                aria-label={t("rating.tou.end")}
                data-cell={`season-end-${index}`}
                value={seasonPickerValue(
                  season.end_month,
                  season.end_day,
                  seasonEndYear(season, props.displayYear),
                )}
                onChange={(event) => {
                  const picked = seasonFromPicker(event.target.value);
                  patchSeason(index, { end_month: picked.month, end_day: picked.day });
                }}
              />
            ),
          },
          {
            key: "price",
            label: per,
            numeric: true,
            cell: (season, index) => (
              <RateCell
                name={`season-price-${index}`}
                label={per}
                value={shownRate(season.unit_price)}
                error={err(`structure.seasons[${index}].unit_price`)}
                onChange={(unit_price) => patchSeason(index, { unit_price })}
              />
            ),
          },
        ]}
        rows={seasons}
        rowKey={(season) => season.key}
        emptyText={t("rating.rs.wiz.noSeasons")}
        removeLabel={t("rating.rs.wiz.removeRow")}
        onChange={setSeasons}
        actions={[
          {
            key: "add-season",
            label: t("rating.rs.wiz.addRow"),
            onClick: () =>
              setSeasons([
                ...seasons,
                {
                  key: nextSeasonKey(seasons),
                  label: "",
                  start_month: "",
                  start_day: "",
                  end_month: "",
                  end_day: "",
                  unit_price: "",
                },
              ]),
          },
        ]}
      >
        {props.errors["structure.seasons"] !== undefined && (
          <ChargeNote tone="warning" name="rs-seasons">
            {props.errors["structure.seasons"]}
          </ChargeNote>
        )}
      </TableArray>
    );
  }

  if (draft.model === "demand") {
    const demand = draft.demand;
    const patchDemand = (next: Partial<ScheduleDraft["demand"]>) => {
      const merged = { ...demand, ...next };
      // The power-factor charge is ON exactly when a rate is typed.
      props.onPatch({
        demand: { ...merged, pf_penalty_enabled: merged.pf_penalty_rate_per_kw.trim() !== "" },
      });
    };
    const cell = (field: "energy_rate_per_kwh" | "demand_rate_per_kw" | "pf_penalty_rate_per_kw", label: string) => (
      <RateCell
        name={field}
        label={label}
        value={shownRate(demand[field])}
        error={err(`structure.demand.${field}`)}
        onChange={(value) => patchDemand({ [field]: value })}
      />
    );
    return (
      <TableArray<{ key: string }>
        collection="rs-usage-rows"
        title={title}
        fact={fact}
        columns={[
          numberColumn<{ key: string }>(),
          {
            key: "energy",
            label: t("rating.rs.usage.energyPerKwh"),
            numeric: true,
            cell: () => cell("energy_rate_per_kwh", t("rating.rs.usage.energyPerKwh")),
          },
          {
            key: "demand",
            label: t("rating.rs.usage.demandPerKw"),
            numeric: true,
            cell: () => cell("demand_rate_per_kw", t("rating.rs.usage.demandPerKw")),
          },
          {
            key: "peak",
            label: t("rating.rs.usage.peakWindow"),
            cell: () => (
              <input
                type="text"
                className="input"
                aria-label={t("rating.rs.usage.peakWindow")}
                data-cell="peak_window_label"
                value={demand.peak_window_label}
                onChange={(event) => patchDemand({ peak_window_label: event.target.value })}
              />
            ),
          },
          {
            key: "pf",
            label: t("rating.rs.usage.pfCharge"),
            numeric: true,
            cell: () => cell("pf_penalty_rate_per_kw", t("rating.rs.usage.pfCharge")),
          },
        ]}
        rows={[{ key: "one" }]}
        rowKey={(row) => row.key}
        emptyText=""
        readOnly
      />
    );
  }

  // percent_of_service — the drawn two columns cannot carry `BR-RAT-1030`'s
  // required basis (*usage* or *charges* — PO 2026-09-22, no safe default), so
  // the method's own ruled editor sits inside the panel.
  return (
    <Panel as="section" title={title} trailing={fact} data-array="rs-usage-rows">
      {props.percentEditor}
    </Panel>
  );
}

// ── step 3 · the draft as the View's usage table reads it ──────────────────

/** The draft's structure in the SERVED shape, so step 3 draws the very table
 *  the View's Rates tab draws (`UsageChargesTable`) — one table, two screens. */
export function draftStructureForView(draft: ScheduleDraft): VersionStructure {
  const unit = draft.uom || null;
  const base: VersionStructure = { model: draft.model, unit, currency: "USD" };
  const tierRow = (tier: TierDraft, index: number, season: string | null = null) => ({
    seq: index + 1,
    season,
    size_class: null,
    from_qty: tier.from_qty.trim() === "" ? null : tier.from_qty.trim(),
    to_qty: tier.to_qty.trim() === "" ? null : tier.to_qty.trim(),
    unit_price: tier.unit_price.trim() === "" ? null : tier.unit_price.trim(),
    from_qty_display: tier.from_qty.trim() === "" ? null : shownQuantity(tier.from_qty),
    to_qty_display: tier.to_qty.trim() === "" ? null : shownQuantity(tier.to_qty),
  });
  switch (draft.model) {
    case "flat":
    case "tiered":
      return { ...base, tiers: draft.tiers.map((tier, index) => tierRow(tier, index)) };
    case "time_of_use":
      return {
        ...base,
        windows: draft.windows.map((window) => ({
          label: window.label,
          season: null,
          day_type: window.day_type,
          start_time: window.start_time,
          end_time: window.end_time,
          unit_price: window.unit_price.trim() === "" ? null : window.unit_price.trim(),
          channel: registerForWindow(window) || null,
        })),
      };
    case "seasonal":
      return {
        ...base,
        seasons: draft.seasons.map((season) => ({
          label: season.label,
          start_month: Number(season.start_month),
          start_day: Number(season.start_day),
          end_month: Number(season.end_month),
          end_day: Number(season.end_day),
        })),
        tiers: draft.seasons.map((season, index) =>
          tierRow({ from_qty: "0", to_qty: "", unit_price: season.unit_price }, index, season.label),
        ),
      };
    case "capacity":
      return {
        ...base,
        capacity: {
          unit_label: draft.capacity.unit_label || draft.uom,
          rate_per_unit: draft.capacity.rate_per_unit.trim() === "" ? null : draft.capacity.rate_per_unit.trim(),
          currency: "USD",
        },
      };
    case "demand":
      return {
        ...base,
        demand: {
          energy_rate_per_kwh: draft.demand.energy_rate_per_kwh.trim() || null,
          demand_rate_per_kw: draft.demand.demand_rate_per_kw.trim() || null,
          peak_window_label: draft.demand.peak_window_label.trim() || null,
          ratchet_enabled: draft.demand.ratchet_enabled,
          ratchet_pct: draft.demand.ratchet_pct.trim() || null,
          pf_penalty_enabled: draft.demand.pf_penalty_enabled,
          pf_penalty_rate_per_kw: draft.demand.pf_penalty_rate_per_kw.trim() || null,
        },
      };
    default:
      return {
        ...base,
        percent: draft.percent.trim() === "" ? null : draft.percent.trim(),
        basis_service: draft.basis_service || null,
        percent_basis: draft.percent_basis,
      };
  }
}

// ── step 3 · What changes ───────────────────────────────────────────────────

export interface ChangeRow {
  item: string;
  now: string;
  next: string;
}

/** What this edit changes, by AREA (`64-edit-change-3.png`: *Usage rates · In
 *  force · Changed*). Compared on the posted payload, so a reformatted but
 *  equal value is not a change. */
export function draftChanges(
  before: Record<string, unknown> | null,
  after: Record<string, unknown>,
  t: Translator,
): ChangeRow[] {
  if (before === null) return [];
  const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
  const rows: ChangeRow[] = [];
  const area = (key: string, label: string) => {
    if (!same(before[key], after[key])) {
      rows.push({ item: label, now: t("rating.rs.wiz.inForce"), next: t("rating.rs.wiz.changed") });
    }
  };
  area("name", t("rating.rs.wiz.field.name"));
  area("account_type_id", t("rating.rs.col.customerClass"));
  area("base_charge_code", t("rating.rs.fact.baseChargeCode"));
  area("size_rows", t("rating.rs.wiz.baseRates"));
  area("structure", t("rating.rs.wiz.usageRates"));
  return rows;
}
