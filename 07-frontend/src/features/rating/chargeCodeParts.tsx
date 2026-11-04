// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave B — the pieces the charge-code List, View details
//           and Add/Edit wizard share (B14 rule 43: a piece of UI is a
//           component, never standalone code inside a page).
// Images:   05-prototype/charge-codes-2026-10-01/images — the kind badge (01,
//           06, 22, 34), the Details / How it bills groups (06, 22, 34, 65),
//           the Prices table (07, 11, 15, 19, 23, 27, 31, 35, 41), the summary
//           aside (43–83) and the coloured notes (19, 27, 34, 53, 64).
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import type { ChargeKind } from "@/api/endpoints";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";

import type { Translator } from "./ratingShared";

export { dollars } from "./chargeCodeModel";

/** The KIND badge — base solid, plan blue, other grey (images 01, 06, 22, 34). */
export function KindBadge(props: { kind: ChargeKind | null | undefined; t: Translator }) {
  if (props.kind === null || props.kind === undefined) return null;
  const label = props.t(`rating.chargeCode.kindBadge.${props.kind}`);
  if (props.kind === "base") {
    return (
      <span className="pill bg-text text-bg" data-kind-badge="base">
        {label}
      </span>
    );
  }
  return (
    <span data-kind-badge={props.kind}>
      <StatusPill tone={props.kind === "plan" ? "info" : "neutral"}>{label}</StatusPill>
    </span>
  );
}

/** A short coloured note under a table (*"1 of 7 not priced."*, *"Held as a deposit…"*). */
export function ChargeNote(props: {
  tone: "warning" | "info" | "success";
  lead?: string;
  children: ReactNode;
  name: string;
}) {
  const tone =
    props.tone === "warning"
      ? "bg-warning-100 text-warning-700"
      : props.tone === "success"
        ? "bg-success-100 text-success-700"
        : "bg-info-100 text-info-700";
  return (
    <p
      className={`m-0 mt-4 flex flex-wrap gap-x-3 px-4 py-3 text-base ${tone}`}
      role="note"
      data-charge-note={props.name}
    >
      {props.lead !== undefined && <strong>{props.lead}</strong>}
      <span>{props.children}</span>
    </p>
  );
}

/** A titled group of facts, four across (the drawn *Details* / *Charge* box). */
export function FactsPanel(props: { title: string; name: string; facts: readonly Fact[]; children?: ReactNode }) {
  return (
    <Panel as="section" title={props.title} data-charge-facts={props.name}>
      <FactBlock facts={props.facts} name={props.name} columns={4} />
      {props.children}
    </Panel>
  );
}

/** The six *How it bills* settings as read-only facts. */
export function HowItBillsPanel(props: { facts: readonly Fact[]; t: Translator }) {
  return (
    <Panel as="section" title={props.t("rating.chargeCode.howItBills")} data-charge-facts="how">
      {/* Images 06 · 10: two rows of three, not one row of six. */}
      <FactBlock facts={props.facts} name="how" variant="strip" columns={3} />
    </Panel>
  );
}

/** One read-only price row, as the View *Prices* tab and the Review step draw it. */
export interface PriceReadRow {
  key: string;
  service?: string;
  asset?: string;
  size?: string;
  customerClass?: string;
  amount?: string | null;
  percent?: string | null;
  minimum?: string | null;
  /** DEF-RAT-8752 — a base size's minimum from the rate schedules (read-only,
   *  images 11 · 51): a figure, a range, or `null` drawn as a dash. */
  floor?: string | null;
}

/** The read-only Prices table — its columns follow what the code is priced by. */
export function PricesReadTable(props: {
  rows: readonly PriceReadRow[];
  columns: readonly ("service" | "asset" | "size" | "customerClass" | "amount" | "percent" | "minimum" | "floor")[];
  amountLabel: string;
  fact?: ReactNode;
  title?: string;
  t: Translator;
  children?: ReactNode;
}) {
  const { t } = props;
  const notPriced = (value: string | null | undefined) =>
    value === null || value === undefined ? (
      <span className="text-neutral-600">{t("rating.chargeCode.notPriced")}</span>
    ) : (
      value
    );
  const all: Record<string, TableArrayColumn<PriceReadRow>> = {
    service: {
      key: "service",
      label: t("rating.chargeCode.col.service"),
      cell: (row) => <span className="text-neutral-700">{row.service}</span>,
    },
    asset: {
      key: "asset",
      label: t("rating.chargeCode.col.asset"),
      cell: (row) => <span className="text-neutral-700">{row.asset ?? "—"}</span>,
    },
    size: {
      key: "size",
      label: t("rating.chargeCode.col.size"),
      cell: (row) => <strong>{row.size}</strong>,
    },
    customerClass: {
      key: "customerClass",
      label: t("rating.chargeCode.col.customerClass"),
      cell: (row) => <strong>{row.customerClass}</strong>,
    },
    percent: {
      key: "percent",
      label: t("rating.chargeCode.col.percent"),
      numeric: true,
      cell: (row) => notPriced(row.percent),
    },
    amount: {
      key: "amount",
      label: props.amountLabel,
      numeric: true,
      cell: (row) => notPriced(row.amount),
    },
    minimum: {
      key: "minimum",
      label: t("rating.chargeCode.col.minimum"),
      numeric: true,
      cell: (row) => notPriced(row.minimum),
    },
    floor: {
      key: "floor",
      label: t("rating.chargeCode.col.minimum"),
      numeric: true,
      cell: (row) => <span className="text-neutral-600">{row.floor ?? "—"}</span>,
    },
  };
  const number: TableArrayColumn<PriceReadRow> = {
    key: "n",
    label: "#",
    cell: (_row, index) => <span className="text-neutral-600">{index + 1}</span>,
  };
  return (
    <TableArray<PriceReadRow>
      readOnly
      collection="charge-prices"
      title={props.title ?? t("rating.chargeCode.prices")}
      fact={props.fact}
      columns={[number, ...props.columns.map((key) => all[key])]}
      rows={props.rows}
      rowKey={(row) => row.key}
      emptyText={t("rating.chargeCode.noPrices")}
    >
      {props.children}
    </TableArray>
  );
}

/** One label/value line of the summary aside. */
function AsideRow(props: { label: string; value: ReactNode; name: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-base" data-aside-row={props.name}>
      <span className="text-neutral-700">{props.label}</span>
      <span className="text-right">{props.value}</span>
    </div>
  );
}

export type AsideStatus =
  | { kind: "all" }
  | { kind: "missing"; count: number }
  | { kind: "entered" };

/** The wizard's sticky summary — the GL account lives HERE (PO 2026-10-01). */
export function ChargeSummaryAside(props: {
  editing: boolean;
  code: string;
  billLine: string;
  kind: string;
  service: string;
  gl: ReactNode;
  effective: string;
  pricedBy: string;
  rows: string;
  priced: string | null;
  status: AsideStatus | null;
  saved: boolean;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="aside" aria-label={t("rating.chargeCode.aside.label")} data-charge-aside="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t(props.editing ? "rating.chargeCode.aside.editing" : "rating.chargeCode.aside.new")}
      </p>
      <p className="m-0 mt-2 font-heading text-metric-lg font-semibold" data-aside-code="">
        {props.code === "" ? "—" : props.code}
      </p>
      <div className="mt-3 flex flex-col gap-1.5">
        <AsideRow name="billLine" label={t("rating.chargeCode.field.billLine")} value={props.billLine || "—"} />
        <AsideRow name="kind" label={t("rating.chargeCode.field.kind")} value={props.kind || "—"} />
        <AsideRow name="service" label={t("rating.chargeCode.field.service")} value={props.service || "—"} />
        <AsideRow name="gl" label={t("rating.chargeCode.field.gl")} value={props.gl} />
        <AsideRow name="effective" label={t("rating.chargeCode.aside.effective")} value={props.effective} />
      </div>
      <div className="mt-3 flex flex-col gap-1.5 border-t border-divider pt-3">
        <AsideRow name="pricedBy" label={t("rating.chargeCode.field.pricedBy")} value={props.pricedBy} />
        <AsideRow name="rows" label={t("rating.chargeCode.aside.rows")} value={props.rows} />
        {props.priced !== null && (
          <AsideRow name="priced" label={t("rating.chargeCode.aside.priced")} value={props.priced} />
        )}
      </div>
      <div className="mt-3" data-aside-status={props.status?.kind ?? "none"}>
        {props.status?.kind === "all" && (
          <StatusPill tone="success">{t("rating.chargeCode.aside.allPriced")}</StatusPill>
        )}
        {props.status?.kind === "missing" && (
          <StatusPill tone="warning">
            {t("rating.chargeCode.aside.notPriced", { count: props.status.count })}
          </StatusPill>
        )}
        {props.status?.kind === "entered" && (
          <StatusPill tone="info">{t("rating.chargeCode.pricedBy.entered")}</StatusPill>
        )}
      </div>
      <p className="m-0 mt-3 text-base text-neutral-700" data-aside-foot={props.saved ? "saved" : "nothing"}>
        {t(props.saved ? "rating.chargeCode.aside.saved" : "rating.chargeCode.aside.nothingSaved")}
      </p>
    </Panel>
  );
}

/** The GL account as a person reads it — `4140 — Trash`, or *Not set* as a warning. */
export function GlValue(props: { code?: string | null; name?: string | null; t: Translator }) {
  if (props.code === null || props.code === undefined) {
    return (
      <span data-gl="unset">
        <StatusPill tone="warning">{props.t("rating.gl.unset")}</StatusPill>
      </span>
    );
  }
  return (
    <span data-gl="set">
      {props.code}
      {props.name ? ` — ${props.name}` : ""}
    </span>
  );
}

/** PO 2026-10-06 11 (a) — a late-fee grace in words: *5 calendar days*. */
export function graceText(t: Translator, days: number | string, mode: string): string {
  return t(mode === "business" ? "rating.chargeCode.grace.business" : "rating.chargeCode.grace.calendar", {
    count: Number(days),
  });
}
