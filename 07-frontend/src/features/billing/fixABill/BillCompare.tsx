// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — F4, the old bill and the new bill side by side
// Drawing: 05-prototype/fix-a-bill-2026-10-12/06, 08, 09 (month tabs), 10 (rate
//          types change, "—" lines), 11 (credit note), 12 (reissued), 13 (deposits)
// Rulings: decision log 2026-10-12 *FIX A BILL REVAMP* item 8
// Rules:   BR-BIL-044 (the nine sections) · hard rule 2 (money 2 places, a unit
//          price up to 4) · B14 rules 31, 43, 44
// ───────────────────────────────────────────────────────
/**
 * THE COMPARISON IS LAID OUT AS THE BILL IS (item 8): each service its own
 * section with its rate type, its base charge and its usage lines; then charge
 * codes, discounts, deposits, subtotal, taxes per authority with their base,
 * and the total. Every line shows quantity × unit price.
 *
 * **THE ROWS LINE UP ACROSS THE TWO SIDES BY LINE** — `alignDocuments` merges
 * the two documents' section and line keys (contract A3: a line `key` is
 * stable across `was` and `becomes`), so a change of rate type shows as "—" on
 * one side rather than shifting every row below it.
 */
import { useState } from "react";

import type {
  CorrectionDocLine,
  CorrectionDocument,
  CorrectionPreviewBill,
} from "@/api/billingOpsEndpoints";
import { StatusPill } from "@/components/StatusPill";

import { OtbPanel, PanelAside, ServiceLabel } from "../oneTimeBill/oneTimeBillShared";

import { monthLabel, signOf } from "./fixABillModel";
import type { Translate } from "./fixABillModel";
import {
  Band,
  changeBandTone,
  changeTone,
  money,
  percent,
  plainNumber,
  signedMoney,
  unitPrice,
} from "./fixABillShared";
import type { FixFmt } from "./fixABillShared";

// ── Alignment (pure) ───────────────────────────────────────────────────────

/** Merge two ordered key lists, keeping each side's own order: a key only on
 *  the right lands just after the key it follows there. */
export function mergeKeys(left: readonly string[], right: readonly string[]): string[] {
  const merged = [...left];
  let anchor = -1;
  for (const key of right) {
    const at = merged.indexOf(key);
    if (at >= 0) {
      anchor = at;
      continue;
    }
    merged.splice(anchor + 1, 0, key);
    anchor += 1;
  }
  return merged;
}

export interface AlignedSection {
  key: string;
  kind: string;
  serviceCode: string | null;
  was: { rateType: string | null; total: string } | null;
  becomes: { rateType: string | null; total: string } | null;
  lines: { key: string; was: CorrectionDocLine | null; becomes: CorrectionDocLine | null }[];
}

export interface Aligned {
  sections: AlignedSection[];
  taxes: {
    key: string;
    was: CorrectionDocument["taxes"][number] | null;
    becomes: CorrectionDocument["taxes"][number] | null;
  }[];
}

export function alignDocuments(was: CorrectionDocument, becomes: CorrectionDocument): Aligned {
  const sectionKeys = mergeKeys(
    was.sections.map((s) => s.key),
    becomes.sections.map((s) => s.key),
  );
  const sections = sectionKeys.map((key): AlignedSection => {
    const left = was.sections.find((s) => s.key === key) ?? null;
    const right = becomes.sections.find((s) => s.key === key) ?? null;
    const any = (left ?? right) as NonNullable<typeof left>;
    const lineKeys = mergeKeys(
      left?.lines.map((l) => l.key) ?? [],
      right?.lines.map((l) => l.key) ?? [],
    );
    return {
      key,
      kind: any.kind,
      serviceCode: any.service_code,
      was: left === null ? null : { rateType: left.rate_type, total: left.total },
      becomes: right === null ? null : { rateType: right.rate_type, total: right.total },
      lines: lineKeys.map((lineKey) => ({
        key: lineKey,
        was: left?.lines.find((l) => l.key === lineKey) ?? null,
        becomes: right?.lines.find((l) => l.key === lineKey) ?? null,
      })),
    };
  });
  const taxKeys = mergeKeys(
    was.taxes.map((x) => x.key),
    becomes.taxes.map((x) => x.key),
  );
  return {
    sections,
    taxes: taxKeys.map((key) => ({
      key,
      was: was.taxes.find((x) => x.key === key) ?? null,
      becomes: becomes.taxes.find((x) => x.key === key) ?? null,
    })),
  };
}

/** Two decimal strings name the same amount (`8.0000` = `8.00`). */
function sameAmount(a: string | null | undefined, b: string | null | undefined): boolean {
  const norm = (x: string | null | undefined) =>
    x === null || x === undefined
      ? null
      : x
          .trim()
          .replace(/(\.\d*?)0+$/, "$1")
          .replace(/\.$/, "");
  return norm(a) === norm(b);
}

// ── One side ───────────────────────────────────────────────────────────────

const PERIOD_UNITS = new Set(["month", "day", "bill"]);

/** `500 kWh × $0.115 / kWh` · `$34.70 × 40%` · `1 × $2.50`. */
export function lineDetail(line: CorrectionDocLine, fmt: FixFmt): string {
  if (line.base !== null && line.percent !== null) {
    return `${money(line.base, fmt)} × ${percent(line.percent, fmt.language)}`;
  }
  if (line.qty === null || line.unit_price === null) return "";
  const qty = plainNumber(line.qty, fmt.language);
  const price = unitPrice(line.unit_price, fmt);
  if (line.unit === null) return `${qty} × ${price}`;
  const per = PERIOD_UNITS.has(line.unit) ? "" : ` / ${line.unit}`;
  return `${qty} ${line.unit} × ${price}${per}`;
}

const ROW = "flex items-start justify-between gap-3 border-b border-divider px-3 py-2";
const HEAD_ROW =
  "flex items-center justify-between gap-3 border-b border-divider bg-neutral-200 px-3 py-1.5";

function LineRow(props: {
  line: CorrectionDocLine | null;
  lineKey: string;
  changed: boolean;
  fmt: FixFmt;
}) {
  const { line } = props;
  return (
    <div className={`${ROW} ${props.changed ? "bg-accent-100" : ""}`} data-fix-line={props.lineKey}>
      {line === null ? (
        <>
          <span className="text-neutral-700">—</span>
          <span className="text-neutral-700">—</span>
        </>
      ) : (
        <>
          <span className="flex min-w-0 flex-col">
            <span>{line.label}</span>
            <span className="text-sm text-neutral-700">{lineDetail(line, props.fmt)}</span>
          </span>
          <span className="whitespace-nowrap tabular-nums">{money(line.amount, props.fmt)}</span>
        </>
      )}
    </div>
  );
}

function SectionHead(props: {
  section: AlignedSection;
  side: "was" | "becomes";
  t: Translate;
  fmt: FixFmt;
  /** PO 2026-10-13 — this service's usage was SHARED BY DAYS on the new bill. */
  sharedByDays?: boolean;
}) {
  const { section, t } = props;
  const mine = section[props.side];
  const other = section[props.side === "was" ? "becomes" : "was"];
  const rateType = mine?.rateType ?? null;
  const typeChanged = props.side === "becomes" && rateType !== (other?.rateType ?? null);
  const name =
    section.kind === "service" && section.serviceCode !== null ? (
      <ServiceLabel code={section.serviceCode} t={t} strong />
    ) : (
      <span className="font-heading font-semibold">
        {t(`billing.fixBill.section.${section.kind}`)}
      </span>
    );
  const kicker =
    section.kind === "deposits"
      ? t("billing.fixBill.section.depositsHeld")
      : rateType === null
        ? null
        : t(`billing.fixBill.rateType.${rateType}`, { defaultValue: rateType });
  return (
    <div className={HEAD_ROW} data-fix-section={section.key}>
      <span className="flex items-center gap-3">
        {name}
        {props.sharedByDays === true && (
          <span className="text-sm text-neutral-700" data-fix-shared-by-days={section.serviceCode}>
            {t("billing.fixBill.usageSharedByDays")}
          </span>
        )}
        {kicker !== null &&
          (typeChanged || section.kind === "deposits" ? (
            <StatusPill tone="warning">{kicker}</StatusPill>
          ) : (
            <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
              {kicker}
            </span>
          ))}
      </span>
      <span className="font-heading font-semibold tabular-nums">
        {mine === null ? money("0", props.fmt) : money(mine.total, props.fmt)}
      </span>
    </div>
  );
}

function TotalRow(props: { label: string; amount: string; strong?: boolean; changed?: boolean }) {
  return (
    <div
      className={`${HEAD_ROW} ${props.strong === true ? "py-3" : ""} ${props.changed === true ? "bg-accent-100" : ""}`}
    >
      <span className="font-heading font-semibold">{props.label}</span>
      <span className="font-heading font-semibold tabular-nums">{props.amount}</span>
    </div>
  );
}

function Side(props: {
  side: "was" | "becomes";
  doc: CorrectionDocument;
  other: CorrectionDocument;
  aligned: Aligned;
  title: string;
  aside: string;
  t: Translate;
  fmt: FixFmt;
  /** The services whose usage the new bill shares by days (PO 2026-10-13). */
  sharedByDays?: readonly string[];
}) {
  const { side, doc, aligned, t } = props;
  const fmt = { ...props.fmt, currency: doc.currency };
  const mark = side === "becomes";
  return (
    <section
      className={`min-w-0 border border-divider bg-surface ${side === "was" ? "border-t-2 border-t-text" : "border-t-2 border-t-accent"}`}
      data-fix-side={side}
      aria-label={props.title}
    >
      <header className="flex items-center justify-between gap-3 border-b border-divider px-3 py-3">
        <span className="font-heading text-md font-semibold">{props.title}</span>
        <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
          {props.aside}
        </span>
      </header>
      {aligned.sections.map((section) => (
        <div key={section.key}>
          <SectionHead
            section={section}
            side={side}
            t={t}
            fmt={fmt}
            sharedByDays={
              side === "becomes" &&
              section.serviceCode !== null &&
              (props.sharedByDays ?? []).includes(section.serviceCode)
            }
          />
          {section.lines.map((pair) => {
            const line = pair[side];
            const other = pair[side === "was" ? "becomes" : "was"];
            const changed =
              mark &&
              line !== null &&
              (other === null ||
                !sameAmount(line.amount, other.amount) ||
                line.unit_price !== other.unit_price);
            return (
              <LineRow key={pair.key} lineKey={pair.key} line={line} changed={changed} fmt={fmt} />
            );
          })}
        </div>
      ))}
      <TotalRow label={t("billing.fixBill.compare.subtotal")} amount={money(doc.subtotal, fmt)} />
      <TotalRow label={t("billing.fixBill.compare.taxes")} amount={money(doc.tax_total, fmt)} />
      {aligned.taxes.map((pair) => {
        const tax = pair[side];
        const other = pair[side === "was" ? "becomes" : "was"];
        const changed =
          mark && tax !== null && (other === null || !sameAmount(tax.amount, other.amount));
        return (
          <div
            key={pair.key}
            className={`${ROW} ${changed ? "bg-accent-100" : ""}`}
            data-fix-line={pair.key}
          >
            {tax === null ? (
              <>
                <span className="text-neutral-700">—</span>
                <span className="text-neutral-700">—</span>
              </>
            ) : (
              <>
                <span className="flex min-w-0 flex-col">
                  <span>{tax.label}</span>
                  <span className="text-sm text-neutral-700">
                    {t("billing.fixBill.compare.taxOn", {
                      rate: percent(tax.rate, fmt.language),
                      base: money(tax.base, fmt),
                    })}
                  </span>
                </span>
                <span className="whitespace-nowrap tabular-nums">{money(tax.amount, fmt)}</span>
              </>
            )}
          </div>
        );
      })}
      <TotalRow label={t("billing.fixBill.compare.total")} amount={money(doc.total, fmt)} strong />
    </section>
  );
}

function planAside(doc: CorrectionDocument): string {
  return [doc.plan_name, doc.plan_version]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
}

/** Image 11's right-hand side: the credit note and what the bill now owes. */
function CreditNoteSide(props: { bill: CorrectionPreviewBill; t: Translate; fmt: FixFmt }) {
  const { bill, t, fmt } = props;
  return (
    <section
      className="min-w-0 self-start border border-divider border-t-2 border-t-accent bg-surface"
      data-fix-credit-note=""
      aria-label={t("billing.fixBill.compare.creditNote")}
    >
      <header className="flex items-center justify-between gap-3 border-b border-divider px-3 py-3">
        <span className="font-heading text-md font-semibold">
          {t("billing.fixBill.compare.creditNote")}
        </span>
        <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
          {t("billing.fixBill.compare.new")}
        </span>
      </header>
      {(bill.credit_note?.lines ?? []).map((line) => (
        <div key={line.key} className={ROW}>
          <span>{line.label}</span>
          <span className="whitespace-nowrap tabular-nums">{money(line.amount, fmt)}</span>
        </div>
      ))}
      <TotalRow
        label={t("billing.fixBill.compare.nowOwes")}
        amount={money(bill.becomes_total, fmt)}
      />
    </section>
  );
}

/** `This bill rises by $18.74.` (+ `All 3 bills: −$9.51.` for several). */
export function ChangeBand(props: {
  delta: string;
  allNet: string | null;
  count: number;
  t: Translate;
  fmt: FixFmt;
}) {
  const way = signOf(props.delta);
  const key = way === "up" ? "rises" : way === "down" ? "drops" : "same";
  return (
    <Band tone={changeBandTone(props.delta)} hook="change">
      <strong>
        {props.t(`billing.fixBill.compare.${key}`, {
          amount: money(props.delta.replace(/^-/, ""), props.fmt),
        })}
      </strong>
      {props.allNet !== null && props.count > 1 && (
        <span>
          {props.t("billing.fixBill.compare.allBills", {
            count: props.count,
            amount: signedMoney(props.allNet, props.fmt),
          })}
        </span>
      )}
    </Band>
  );
}

/** One bill's two sides. */
function OneComparison(props: {
  bill: CorrectionPreviewBill;
  cls: string | null;
  t: Translate;
  fmt: FixFmt;
}) {
  const { bill, t, fmt } = props;
  if (bill.was === null) return null;
  if (props.cls === "credit_only") {
    const empty: CorrectionDocument = { ...bill.was, sections: [], taxes: [] };
    return (
      <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1" data-fix-compare="">
        <Side
          side="was"
          doc={bill.was}
          other={empty}
          aligned={alignDocuments(bill.was, bill.was)}
          title={bill.invoice_no ?? "—"}
          aside={planAside(bill.was)}
          t={t}
          fmt={fmt}
        />
        <CreditNoteSide bill={bill} t={t} fmt={fmt} />
      </div>
    );
  }
  const becomes = bill.becomes ?? bill.was;
  const aligned = alignDocuments(bill.was, becomes);
  const reprint = props.cls === "document";
  return (
    <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1" data-fix-compare="">
      <Side
        side="was"
        doc={bill.was}
        other={becomes}
        aligned={aligned}
        title={bill.invoice_no ?? "—"}
        aside={planAside(bill.was)}
        t={t}
        fmt={fmt}
      />
      <Side
        side="becomes"
        doc={becomes}
        other={bill.was}
        aligned={aligned}
        title={t(
          reprint ? "billing.fixBill.compare.reissued" : "billing.fixBill.compare.corrected",
        )}
        aside={reprint ? t("billing.fixBill.compare.sameAmounts") : planAside(becomes)}
        t={t}
        fmt={fmt}
        sharedByDays={bill.usage_shared_by_days ?? []}
      />
    </div>
  );
}

/** *Old bill and new bill* — month tabs when several bills, then the two
 *  sides, then the change band. */
export function ComparePanel(props: {
  bills: readonly CorrectionPreviewBill[];
  cls: string | null;
  net: string;
  t: Translate;
  fmt: FixFmt;
}) {
  const { bills, t, fmt } = props;
  const [chosen, setChosen] = useState(0);
  const index = Math.min(chosen, Math.max(0, bills.length - 1));
  const bill = bills[index];
  if (bill === undefined || bill.was === null) return null;
  const title = t(
    props.cls === "credit_only"
      ? "billing.fixBill.compare.titleCredit"
      : "billing.fixBill.compare.title",
  );
  return (
    <OtbPanel
      id="compare"
      title={title}
      aside={
        props.cls === "credit_only" ? undefined : (
          <PanelAside>{t("billing.fixBill.compare.aside", { count: bills.length })}</PanelAside>
        )
      }
    >
      {bills.length > 1 && (
        <div
          role="tablist"
          aria-label={title}
          className="mb-3 flex flex-wrap gap-1 border-b border-divider"
        >
          {bills.map((one, i) => (
            <button
              key={one.invoice_id}
              type="button"
              role="tab"
              aria-selected={i === index}
              className={`-mb-px cursor-pointer border-0 border-b-2 bg-transparent px-3 py-2 text-base ${i === index ? "border-accent font-semibold" : "border-transparent"}`}
              onClick={() => setChosen(i)}
            >
              {monthLabel(one.period_end, fmt.language)}
              {" · "}
              <span className={changeTone(one.delta)}>{signedMoney(one.delta, fmt)}</span>
            </button>
          ))}
        </div>
      )}
      <OneComparison bill={bill} cls={props.cls} t={t} fmt={fmt} />
      <ChangeBand delta={bill.delta} allNet={props.net} count={bills.length} t={t} fmt={fmt} />
    </OtbPanel>
  );
}
