// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-9821 — PO request 2026-10-06: *"In this screen all
//           component bind in plan like rate, charge,code, base reate, taxes,
//           discount needs to visible this data is required for clark while
//           attaching the plan based on data clark will take decision"*, drawn
//           and approved (claude.ai/artifact/9poRZzcU1ooxCw9A78jXgy; *"okay -
//           please do these changes"*). Decision log 2026-10-06 *"NEW CONNECT
//           STEP 2: THE 'THIS PLAN' BLOCK IS REDRAWN …"*.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT) · rule 44 (the drawing
//           says what and where; the kit says how) · rule 20 (one table type:
//           the kit's `EditableTable`, read-only) · rule 21 (utilities only) ·
//           rule 31 (names, never ids) · rule 33 · CLAUDE.md hard rule 2 (money
//           DISPLAYS 2 places; a unit price shows up to 4 — the server's own
//           words, nothing here formats or sums a price)
// Tests:    src/features/rating/planSections/ThisPlanBlock.dom.test.tsx ·
//           src/features/customers/newConnectSteps12Redesign.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// THE PLAN A CLERK IS ABOUT TO ATTACH, EVERY COMPONENT IT BINDS, IN ONE BLOCK.
//
// ⚠ **IT READS THE PLAN DETAILS PAGE'S OWN SECTIONS** (`GET /plans/{id}`,
// `plan_reads.plan_sections`) and the same helpers `PlanSections` words them
// with — so this block and the plan's page cannot describe one plan two ways.
// What it adds is the NARROWING: only the services `services` names (the
// address's), and the base the server narrowed to the account's class.
//
// ⚠ **THE ORDER AND WHAT IS OPEN ARE THE DRAWING'S**: summary · warnings ·
// Base charges (open) · Usage rates (open) · Other charges · Deposit · Taxes ·
// Discounts · Outside city (closed, each with its one-line summary on the
// header — `Disclosure` cannot fold a figure away, see its header).
//
// ⚠ **A WARNING IS DRAWN ONLY WHEN IT IS TRUE.** *"names no base code"* is the
// server's `base.named === false` — not "no base was found": a pooled code may
// still serve the bill, and the schedule still names none. An older server
// that does not send `named` gets no warning, never a false one.
//
// ⚠ **EVERY NAME OPENS ITS OWN PAGE IN A NEW TAB** — the clerk is mid-wizard,
// and a same-tab link would leave the draft (the drawing's own note).
import type { ReactNode } from "react";

import type { PlanDetail } from "@/api/endpoints";
import type {
  PlanChargeSection,
  PlanDiscountSection,
  PlanPricedRow,
  PlanRef,
  PlanSectionDeposit,
  PlanSections,
  PlanServiceSection,
  PlanTaxSection,
} from "@/api/planFormEndpoints";
import { formatDate } from "@/components/DateCell";
import { Disclosure } from "@/components/Disclosure";
import { EditableTable } from "@/components/EditableTable";
import type { EditableColumn } from "@/components/EditableTable";
import { FactBlock } from "@/components/FactBlock";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { WarningBox } from "@/components/WarningBox";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { graceText } from "../chargeCodeParts";
import { planDetailRoute } from "../planDetail/planDetailModel";
import { planStatusTone } from "../ratingShared";
import type { Translator } from "../ratingShared";
import {
  classOrSizeWord,
  moneyShown,
  pricedAmount,
  pricedRowsInOrder,
  refPath,
  serviceWord,
  taxedWord,
  usageKindWord,
  usageRowLabel,
  usageRowRate,
  usageRowsInOrder,
  whenWord,
} from "./PlanSections";

const DASH = "—";

/** The five collapsed parts, in the drawn order — exported for the test. */
export const THIS_PLAN_COLLAPSED = ["charges", "deposit", "taxes", "discounts", "outside"] as const;

export interface ThisPlanBlockProps {
  planId: string;
  /** `GET /plans/{id}`'s own row — status, version and the plan's dates. */
  detail: PlanDetail;
  /** The same body's sections, read with the account's class (`?classes=`). */
  sections: PlanSections;
  /** The services the address takes, as service codes, in the clerk's order. */
  services: readonly string[];
  /** The account's class BY NAME, for the footer; `null` when none is chosen. */
  className: string | null;
  t: Translator;
}

/** One warning the block draws, or none. Pure, so the "only when true" rule is
 *  asserted without a render. */
export interface PlanWarning {
  kind: "noBaseCode" | "notCovered" | "priceNotSet";
  service: string;
  /** The schedule to open for *Choose a base code*. */
  schedule: PlanRef | null;
}

export function planWarnings(sections: PlanSections, services: readonly string[]): PlanWarning[] {
  const out: PlanWarning[] = [];
  for (const code of services) {
    const line = sections.services.find((row) => row.service === code) ?? null;
    if (line === null) {
      out.push({ kind: "notCovered", service: code, schedule: null });
      continue;
    }
    if (line.schedule !== null && line.base.named === false) {
      out.push({ kind: "noBaseCode", service: code, schedule: line.schedule });
    }
    if (line.base.state === "refused") {
      out.push({ kind: "priceNotSet", service: code, schedule: line.schedule });
    }
  }
  return out;
}

/** A name that opens its own page in a new tab, with the drawn `↗`. */
function NewTabLink(props: { to: string; children: ReactNode; name?: string }) {
  const tenantPath = useTenantPath();
  return (
    <InlineLinkTo
      to={tenantPath(props.to)}
      target="_blank"
      rel="noopener noreferrer"
      className="font-semibold"
      data-new-tab={props.name ?? ""}
    >
      {props.children}
      <span aria-hidden="true"> ↗</span>
    </InlineLinkTo>
  );
}

function RefLink(props: { item: PlanRef; byName?: boolean }) {
  const label = props.byName === true ? props.item.name || props.item.code : props.item.code || props.item.name;
  return (
    <NewTabLink to={refPath(props.item)} name={props.item.kind}>
      {label}
    </NewTabLink>
  );
}

function Lines(props: { lines: readonly string[]; name: string }) {
  return (
    <span className="flex flex-col gap-1" data-lines={props.name}>
      {props.lines.map((line, index) => (
        <span key={`${props.name}-${index}`}>{line}</span>
      ))}
    </span>
  );
}

function table<Row>(name: string, columns: EditableColumn<Row>[], rows: readonly Row[], key: (row: Row, index: number) => string, empty: string) {
  return (
    <EditableTable<Row>
      readOnly
      caption=""
      numbered={false}
      reorderable={false}
      columns={columns}
      rows={[...rows]}
      rowKey={key}
      emptyText={empty}
      data-collection={`this-plan-${name}`}
    />
  );
}

/** *$10.00*, or a size's figures, for one service's base. */
function baseAmountLines(line: PlanServiceSection, currency: string | null): string[] {
  const { base } = line;
  // `DEF-RAT-9832` — a schedule naming no base code bills `$0.00`; say so.
  if (base.state === "not_named" && base.flat_display !== null) return [moneyShown(base.flat_display, currency)];
  if (base.state !== "ok") return [DASH];
  if (base.flat_display !== null) return [moneyShown(base.flat_display, currency)];
  if (base.by_size.length > 0) {
    return base.by_size.map((size) => `${size.size_label} · ${moneyShown(size.amount_display, currency)}`);
  }
  return [DASH];
}

function classesWord(classes: readonly string[] | undefined, t: Translator): string {
  if (classes === undefined) return DASH;
  return classes.length === 0 ? t("rating.thisPlan.everyClass") : classes.join(", ");
}

/**
 * ⊕ `DEF-CUS-9836` — the Taxes card's summary, as drawn: *2 · 8.00% total*.
 * The total is the SERVER's (`combined_tax_rate_display`, summed on the stored
 * six-place fractions and narrowed to the account's class by `?classes=`) —
 * this never adds two decimals (hard rule 2). A flat tax is not a percentage,
 * so it is not in the total and the line says it is there (*· 1 flat*). With
 * no single figure (no percentage tax this class pays), the count alone.
 */
export function thisPlanTaxSummary(sections: PlanSections, t: Translator): string {
  const parts = [
    sections.combined_tax_rate_display === null
      ? String(sections.taxes.length)
      : t("rating.thisPlan.taxes.summary", {
          n: sections.taxes.length,
          rate: sections.combined_tax_rate_display,
        }),
  ];
  const flat = sections.taxes.filter((row) => row.rate_percent === null && row.rate_display !== null).length;
  if (flat > 0) parts.push(t("rating.thisPlan.taxes.flat", { count: flat }));
  return parts.join(" · ");
}

/** The first figure of a priced code — *1.50%, min $5.00*, *$25.00*. */
function firstAmount(rows: readonly PlanPricedRow[], currency: string | null, t: Translator): string {
  const first = rows[0];
  return first === undefined ? DASH : pricedAmount(first, currency, t);
}

export function ThisPlanBlock(props: ThisPlanBlockProps) {
  const { t, sections, detail } = props;
  const regional = useRegional({});
  const currency = sections.currency;
  const date = (iso: string | null | undefined) =>
    iso === null || iso === undefined || iso === "" ? DASH : formatDate(iso, regional.timeZone, regional.dateFormat);
  const name = (code: string) => {
    const line = sections.services.find((row) => row.service === code);
    return serviceWord(code, line?.name ?? code, t);
  };
  // Only the services the address takes, in the clerk's order.
  const lines: PlanServiceSection[] = props.services.flatMap((code) => {
    const line = sections.services.find((row) => row.service === code);
    return line === undefined ? [] : [line];
  });
  const warnings = planWarnings(sections, props.services);
  const covered = lines.length;

  // ── 1 · the summary strip ──────────────────────────────────────────────
  const classes = sections.details.customer_classes;
  const facts = [
    { id: "code", label: t("rating.thisPlan.fact.code"), value: sections.details.code || detail.code || DASH },
    {
      id: "version",
      label: t("rating.thisPlan.fact.version"),
      value: (
        <span className="flex flex-wrap items-center gap-2">
          {/* `v1` — a letter and a number, no word to translate (the step's
              own `v${version}` before the redraw; G15 refuses a catalogue
              value identical in eleven languages). */}
          <span>{`v${detail.version}`}</span>
          <StatusPill tone={planStatusTone(detail.status)}>
            {t(`rating.plan.status.${detail.status}`, { defaultValue: detail.status })}
          </StatusPill>
        </span>
      ),
    },
    {
      id: "inForce",
      label: t("rating.thisPlan.fact.inForce"),
      // Two dates and an arrow, as the step drew it before the redraw.
      value: `${date(detail.effective_from)} → ${
        detail.effective_to ? date(detail.effective_to) : t("rating.thisPlan.openEnded")
      }`,
    },
    {
      id: "accountType",
      label: t("rating.thisPlan.fact.accountType"),
      value: classes.length === 0 ? t("rating.thisPlan.everyClass") : classes.map((row) => row.label).join(", "),
    },
    {
      id: "minimum",
      label: t("rating.thisPlan.fact.minimum"),
      value:
        sections.details.minimum_bill_display === null
          ? t("rating.planSections.none")
          : moneyShown(sections.details.minimum_bill_display, currency),
    },
    {
      id: "covers",
      label: t("rating.thisPlan.fact.covers"),
      value: t("rating.thisPlan.coversCount", { covered, count: props.services.length }),
    },
  ];

  // ── 2 · Base charges ───────────────────────────────────────────────────
  const baseColumns: EditableColumn<PlanServiceSection>[] = [
    { key: "service", label: t("rating.thisPlan.col.service"), cell: (row) => name(row.service) },
    {
      key: "code",
      label: t("rating.thisPlan.col.baseCode"),
      cell: (row) =>
        row.base.code !== null && row.base.state !== "ambiguous" && row.base.state !== "none" ? (
          <RefLink item={row.base.code} />
        ) : (
          <span data-base-not-chosen={row.service}>
            <StatusPill tone="warning">{t("rating.thisPlan.base.notChosen")}</StatusPill>
          </span>
        ),
    },
    {
      key: "amount",
      label: t("rating.thisPlan.col.amount"),
      numeric: true,
      cell: (row) => <Lines name="base-amount" lines={baseAmountLines(row, currency)} />,
    },
    {
      key: "per",
      label: t("rating.thisPlan.col.per"),
      cell: (row) => (row.base.state === "ok" ? t("rating.thisPlan.perMonth") : DASH),
    },
    {
      key: "appliesTo",
      label: t("rating.thisPlan.col.appliesTo"),
      cell: (row) => (row.base.state === "ok" ? classesWord(row.base.classes, t) : DASH),
    },
  ];
  const baseSummary = lines
    .map((row) =>
      row.base.state === "ok" && row.base.code !== null
        ? `${name(row.service)} ${baseAmountLines(row, currency)[0]}`
        : t("rating.thisPlan.base.summaryNotChosen", { service: name(row.service) }),
    )
    .join(" · ");

  // ── 3 · Usage rates ────────────────────────────────────────────────────
  const usageColumns: EditableColumn<PlanServiceSection>[] = [
    { key: "service", label: t("rating.thisPlan.col.service"), cell: (row) => name(row.service) },
    {
      key: "schedule",
      label: t("rating.thisPlan.col.schedule"),
      cell: (row) => (row.schedule === null ? DASH : <RefLink item={row.schedule} byName />),
    },
    {
      key: "version",
      label: t("rating.thisPlan.col.version"),
      cell: (row) =>
        row.schedule === null || row.schedule.version === null
          ? DASH
          : row.schedule.effective_from === null
            ? t("rating.taxes.list.version", { n: row.schedule.version })
            : t("rating.thisPlan.versionFrom", {
                version: t("rating.taxes.list.version", { n: row.schedule.version }),
                date: date(row.schedule.effective_from),
              }),
    },
    {
      key: "priced",
      label: t("rating.thisPlan.col.priced"),
      cell: (row) => usageKindWord(row, t) ?? row.schedule?.model_label ?? DASH,
    },
    {
      key: "rates",
      label: t("rating.thisPlan.col.rates"),
      numeric: true,
      cell: (row) => {
        const rows = usageRowsInOrder(row.usage);
        if (rows.length === 0) return DASH;
        return (
          <Lines
            name="rates"
            lines={rows.map((one) =>
              rows.length === 1 && one.label_key === "eachMonth"
                ? usageRowRate(one, t)
                : `${usageRowLabel(one, t)} · ${usageRowRate(one, t)}`,
            )}
          />
        );
      },
    },
  ];
  const scheduleCount = lines.filter((row) => row.schedule !== null).length;

  // ── 4 · Other charges ──────────────────────────────────────────────────
  const chargeColumns: EditableColumn<PlanChargeSection>[] = [
    { key: "code", label: t("rating.thisPlan.col.code"), cell: (row) => <RefLink item={row.ref} /> },
    { key: "name", label: t("rating.thisPlan.col.name"), cell: (row) => row.ref.name || DASH },
    { key: "when", label: t("rating.thisPlan.col.when"), cell: (row) => whenWord(row, t) },
    {
      key: "amount",
      label: t("rating.thisPlan.col.amount"),
      numeric: true,
      cell: (row) => {
        const priced = pricedRowsInOrder(row);
        if (priced.length === 0) return DASH;
        return (
          <Lines
            name="charge-amount"
            lines={priced.map((one) =>
              priced.length === 1 ? pricedAmount(one, currency, t) : `${classOrSizeWord(one, t)} · ${pricedAmount(one, currency, t)}`,
            )}
          />
        );
      },
    },
    {
      key: "grace",
      label: t("rating.thisPlan.col.grace"),
      cell: (row) => (row.grace ? graceText(t, row.grace.days, row.grace.mode) : DASH),
    },
  ];
  const charges = sections.charge_codes;
  const chargeSummary = [
    String(charges.length),
    ...charges.map((row) => `${row.ref.name || row.ref.code} ${firstAmount(pricedRowsInOrder(row), currency, t)}`),
  ].join(" · ");

  // ── 5 · Deposit — one row per class or size the code prices ────────────
  interface DepositLine {
    key: string;
    deposit: PlanSectionDeposit;
    row: PlanPricedRow | null;
  }
  const depositLines: DepositLine[] = sections.deposits.flatMap((deposit, index): DepositLine[] => {
    const rows = pricedRowsInOrder(deposit);
    return rows.length === 0
      ? [{ key: `${deposit.ref?.id ?? index}-0`, deposit, row: null }]
      : rows.map((row, at) => ({ key: `${deposit.ref?.id ?? index}-${at}`, deposit, row }));
  });
  const depositColumns: EditableColumn<DepositLine>[] = [
    {
      key: "code",
      label: t("rating.thisPlan.col.code"),
      cell: (line) => (line.deposit.ref === null ? t("rating.planSections.col.deposit") : <RefLink item={line.deposit.ref} />),
    },
    {
      key: "appliesTo",
      label: t("rating.thisPlan.col.appliesTo"),
      cell: (line) => (line.row === null ? DASH : classOrSizeWord(line.row, t)),
    },
    {
      key: "amount",
      label: t("rating.thisPlan.col.amount"),
      numeric: true,
      cell: (line) => (line.row === null ? DASH : pricedAmount(line.row, currency, t)),
    },
    {
      key: "refundable",
      label: t("rating.thisPlan.col.refundable"),
      cell: (line) =>
        line.deposit.refundable === true
          ? t("rating.yes")
          : line.deposit.refundable === false
            ? t("rating.no")
            : DASH,
    },
  ];
  const depositSummary = depositLines
    .map((line) => (line.row === null ? DASH : `${classOrSizeWord(line.row, t)} ${pricedAmount(line.row, currency, t)}`))
    .join(" · ");

  // ── 6 · Taxes ──────────────────────────────────────────────────────────
  const taxColumns: EditableColumn<PlanTaxSection>[] = [
    { key: "tax", label: t("rating.thisPlan.col.tax"), cell: (row) => <RefLink item={row.ref} byName /> },
    { key: "authority", label: t("rating.thisPlan.col.authority"), cell: (row) => row.authority ?? DASH },
    { key: "rate", label: t("rating.thisPlan.col.rate"), numeric: true, cell: (row) => row.rate_display ?? DASH },
    { key: "taxes", label: t("rating.thisPlan.col.taxes"), cell: (row) => taxedWord(row, t) },
    { key: "classes", label: t("rating.thisPlan.col.classes"), cell: (row) => classesWord(row.customer_classes, t) },
  ];
  const taxSummary = thisPlanTaxSummary(sections, t);

  // ── 7 · Discounts ──────────────────────────────────────────────────────
  const discountColumns: EditableColumn<PlanDiscountSection>[] = [
    { key: "discount", label: t("rating.thisPlan.col.discount"), cell: (row) => <RefLink item={row.ref} byName /> },
    { key: "value", label: t("rating.thisPlan.col.value"), numeric: true, cell: (row) => row.value_display ?? DASH },
    {
      key: "how",
      label: t("rating.thisPlan.col.how"),
      cell: (row) =>
        row.enrolment_mode === "automatic" ? (
          <StatusPill tone="success">{t("rating.thisPlan.discount.automatic")}</StatusPill>
        ) : row.enrolment_mode === "apply_and_approve" ? (
          <StatusPill tone="info">{t("rating.thisPlan.discount.appliedFor")}</StatusPill>
        ) : (
          DASH
        ),
    },
    {
      key: "proof",
      label: t("rating.thisPlan.col.proof"),
      cell: (row) =>
        row.proof_required === true
          ? t("rating.thisPlan.discount.proofNeeded")
          : row.proof_required === false
            ? t("rating.no")
            : DASH,
    },
  ];
  const discountSummary = [
    String(sections.discounts.length),
    // ⊕ `DEF-CUS-9836` — by NAME, as drawn (*Paperless*), never the code in
    // capitals (`PAPERLESS`); the table below already reads names.
    ...sections.discounts.map((row) => `${row.ref.name || row.ref.code} ${row.value_display ?? DASH}`),
  ].join(" · ");

  // ── 8 · Outside city ───────────────────────────────────────────────────
  const outsideWord = (row: PlanServiceSection) =>
    row.outside_city.surcharged && row.outside_city.percent_display !== null
      ? `+${row.outside_city.percent_display}`
      : t("rating.planSections.service.samePrice");
  const outsideColumns: EditableColumn<PlanServiceSection>[] = [
    { key: "service", label: t("rating.thisPlan.col.service"), cell: (row) => name(row.service) },
    { key: "outside", label: t("rating.thisPlan.col.outside"), cell: (row) => outsideWord(row) },
  ];
  const surcharged = lines.filter((row) => row.outside_city.surcharged && row.outside_city.percent_display !== null);
  const outsideSummary =
    surcharged.length === 0
      ? t("rating.planSections.service.samePrice")
      : surcharged.map((row) => `${name(row.service)} ${outsideWord(row)}`).join(" · ");

  return (
    <div className="mt-5 flex flex-col gap-3 border-t-2 border-text pt-4" data-this-plan={sections.details.code}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h4 className="m-0 font-heading text-md font-semibold">{t("rating.thisPlan.title")}</h4>
        <NewTabLink to={planDetailRoute(props.planId)} name="plan">
          {t("rating.thisPlan.openPlan")}
        </NewTabLink>
      </div>

      <FactBlock name="this-plan-summary" variant="strip" facts={facts} />

      {warnings.map((warning) => (
        <WarningBox
          key={`${warning.kind}-${warning.service}`}
          tone="soon"
          data-warning={`this-plan-${warning.kind}`}
          sentence={
            <span className="flex flex-wrap items-baseline justify-between gap-3">
              <span>{t(`rating.thisPlan.warn.${warning.kind}`, { service: name(warning.service) })}</span>
              {warning.kind === "noBaseCode" && warning.schedule !== null && (
                <NewTabLink to={refPath(warning.schedule)} name="choose-base-code">
                  {t("rating.thisPlan.warn.chooseBaseCode")}
                </NewTabLink>
              )}
            </span>
          }
        />
      ))}

      <Disclosure variant="card" defaultOpen title={t("rating.thisPlan.base.title")} summary={baseSummary}>
        <div data-this-plan-part="base">
          {table("base", baseColumns, lines, (row) => row.service, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <Disclosure
        variant="card"
        defaultOpen
        title={t("rating.thisPlan.usage.title")}
        summary={t("rating.thisPlan.usage.summary", { count: scheduleCount })}
      >
        <div data-this-plan-part="usage">
          {table("usage", usageColumns, lines, (row) => row.service, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <Disclosure variant="card" title={t("rating.thisPlan.charges.title")} summary={chargeSummary}>
        <div data-this-plan-part="charges">
          {table("charges", chargeColumns, charges, (row) => row.ref.id, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <Disclosure variant="card" title={t("rating.thisPlan.deposit.title")} summary={depositSummary || t("rating.planSections.none")}>
        <div data-this-plan-part="deposit">
          {table("deposit", depositColumns, depositLines, (line) => line.key, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <Disclosure variant="card" title={t("rating.thisPlan.taxes.title")} summary={taxSummary}>
        <div data-this-plan-part="taxes">
          {table("taxes", taxColumns, sections.taxes, (row) => row.ref.id, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <Disclosure variant="card" title={t("rating.thisPlan.discounts.title")} summary={discountSummary}>
        <div data-this-plan-part="discounts">
          {table("discounts", discountColumns, sections.discounts, (row) => row.ref.id, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <Disclosure variant="card" title={t("rating.thisPlan.outside.title")} summary={outsideSummary}>
        <div data-this-plan-part="outside">
          {table("outside", outsideColumns, lines, (row) => row.service, t("rating.planSections.none"))}
        </div>
      </Disclosure>

      <p className="m-0 text-sm text-neutral-700" data-this-plan-footer="">
        {props.className === null
          ? t("rating.thisPlan.footer")
          : t("rating.thisPlan.footerForClass", { class: props.className })}
      </p>
    </div>
  );
}
