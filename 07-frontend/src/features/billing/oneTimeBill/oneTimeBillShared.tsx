// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/ (inventory.md §9 — "build once, use many")
// Rules:   B14 rules 21 (utilities only), 31, 33, 36, 43, 44
// ───────────────────────────────────────────────────────
/**
 * The pieces every step of the one-time bill repeats (inventory §9): a panel
 * with a right-hand summary, the collapsible form of it, the colour square in
 * front of a service, the warning note, and the in-panel figure table.
 *
 * Each is a component so a step composes it rather than re-typing it (B14 rule
 * 43), and each is built from the kit — `Panel`, `PlainTable`, `StatusPill` —
 * so the page looks like the rest of the product rather than like the mock-up
 * (rule 44: our UI standard wins on spacing, size and type).
 */
import type { CSSProperties, ReactNode } from "react";
import { useState } from "react";

import { formatMoney, formatRate } from "@/components/MoneyCell";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";
import type { Translator } from "@/components/FormModal";
import type { OneTimeBillKind, OneTimeBillWarning } from "@/api/billingOpsEndpoints";
import { serviceBadge } from "@/features/rating/ratingShared";

/** The page's regional context, passed down rather than re-read per cell. */
export interface OtbFormat {
  t: Translator;
  currency: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** A 4-decimal wire amount at 2 decimals, beside its currency (rule 2). */
export function money(amount: string | null | undefined, fmt: OtbFormat): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  return formatMoney(amount, fmt.currency);
}

/**
 * A unit PRICE at 2 decimals where it has no more (`$3.25`, `$15.00`), and at
 * its own precision up to 4 where it does (`$0.1245`) — DEF-BIL-8316: the
 * wire's `3.2500` printed as `$3.2500` beside the drawing's `$3.25`. Money
 * displays 2 dp (CLAUDE.md rule 2); a sub-cent rate is not rounded to fit.
 */
export function rateMoney(amount: string | null | undefined, fmt: OtbFormat): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const fraction = amount.split(".")[1] ?? "";
  if (fraction.slice(2).replace(/0+$/, "") === "") return formatMoney(amount, fmt.currency);
  return formatRate(amount, fmt.currency);
}

/**
 * A meter READING as a person writes it: `19020`, `488.4` — never the wire's
 * `19020.000000` (DEF-BIL-8316). Trailing zeros only; the value is not
 * rounded, and a reading is a register value, not money.
 */
export function plainReading(value: string | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (!value.includes(".")) return value;
  return value.replace(/0+$/, "").replace(/\.$/, "");
}

/** A calendar date in the tenant's own format; `—` when there is none. */
export function day(value: string | null | undefined, fmt: OtbFormat): string {
  if (value === null || value === undefined || value === "") return "—";
  return formatDate(value, fmt.timeZone, fmt.dateFormat);
}

/** `Sep 1, 2026 – Sep 30, 2026`, in the tenant's format. */
export function span(start: string | null, end: string | null, fmt: OtbFormat): string {
  return `${day(start, fmt)} – ${day(end, fmt)}`;
}

/** A service's own word, from the catalogue every other screen reads. An
 *  unknown (tenant-added) code shows as itself rather than vanishing. */
export function serviceName(code: string, t: Translator): string {
  return t(`rating.service.${code}`, { defaultValue: code });
}

/** The kind's own word — `Interim`, `Catch-up`, `Penalty / theft`… */
export function kindName(kind: OneTimeBillKind, t: Translator): string {
  return t(`billing.oneTimeBill.kind.${kind}`);
}

/** The colour square in front of a service. The colour is the service's own
 *  token (`serviceBadge`), carried through `style` exactly as `ServiceChips`
 *  carries it — a class per service is the trap that file documents. */
export function ServiceSwatch(props: { code: string }) {
  const style: CSSProperties = { background: `var(${serviceBadge(props.code).token})` };
  return <span aria-hidden="true" className="inline-block h-2.5 w-2.5 shrink-0" style={style} />;
}

/** Colour square + name, the first cell of every service row. */
export function ServiceLabel(props: { code: string; t: Translator; strong?: boolean; suffix?: string }) {
  return (
    <span className="inline-flex items-center gap-2" data-service={props.code}>
      <ServiceSwatch code={props.code} />
      <span className={props.strong === true ? "font-heading font-semibold" : undefined}>
        {serviceName(props.code, props.t)}
        {/* A meter number never breaks at its hyphen (`W-` / `10442`), which
            the drawing's own tables do — inventory §0. */}
        {props.suffix !== undefined && <span className="whitespace-nowrap">{` · ${props.suffix}`}</span>}
      </span>
    </span>
  );
}

/** The quiet uppercase words at the right of a panel heading — `4 billed · 2 not
 *  in service`, `As it will print`, `3 periods`. Uppercase comes from CSS; the
 *  catalogue holds sentence case (inventory "How to read this file"). */
export function PanelAside(props: { children: ReactNode }) {
  return (
    <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
      {props.children}
    </span>
  );
}

/** A step-2 panel: heading on the left, its summary on the right. */
export function OtbPanel(props: {
  id: string;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Panel
      as="section"
      title={props.title}
      trailing={props.aside}
      data-otb-panel={props.id}
      aria-label={props.title}
    >
      {props.children}
    </Panel>
  );
}

/**
 * The three sections the PO ruled collapsible — Services, Rates, Move-in
 * charges — open by default (*"can you make services , Rates, Move-in charges
 * … collapable/expand"*, 2026-09-30). Collapsed, only the heading row stands.
 *
 * The toggle is a real `<button>` with `aria-expanded`, named by the section's
 * own heading, so a keyboard and a screen reader both reach it.
 */
export function CollapsiblePanel(props: {
  id: string;
  title: string;
  aside: ReactNode;
  toggleLabel: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(props.defaultOpen ?? true);
  const bodyId = `otb-${props.id}-body`;
  return (
    <Panel
      as="section"
      title={props.title}
      aria-label={props.title}
      data-otb-panel={props.id}
      data-open={open ? "true" : "false"}
      trailing={
        <span className="flex items-center gap-3">
          {props.aside}
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center border border-divider bg-bg text-xs"
            aria-expanded={open}
            aria-controls={bodyId}
            aria-label={props.toggleLabel}
            onClick={() => setOpen((was) => !was)}
          >
            <span aria-hidden="true">{open ? "▲" : "▼"}</span>
          </button>
        </span>
      }
    >
      <div id={bodyId} hidden={!open} className="mt-3">
        {props.children}
      </div>
    </Panel>
  );
}

/**
 * The in-panel figure table's extra rules over `PlainTable`: a bordered box, a
 * shaded head, numbers right-aligned. `[data-num]` rather than `text-right` on
 * the cell, because `PlainTable`'s own `[&_td]:text-left` is the more specific
 * selector and would win (the `CloseView` precedent).
 */
export const OTB_TABLE =
  "border border-divider [&_thead_th]:bg-neutral-200 [&_[data-num]]:text-right " +
  "[&_[data-num]]:whitespace-nowrap [&_[data-total]>*]:bg-neutral-200 " +
  "[&_[data-total]>*]:font-heading [&_[data-total]>*]:font-semibold " +
  "[&_tbody_th[scope=row]]:font-normal";

/** A table that may be wider than its panel scrolls inside its own box — the
 *  page never scrolls sideways, and no column is clipped (the drawing's Rates
 *  Amount column is; ours must not be). */
export function TableScroll(props: { children: ReactNode }) {
  return <div className="max-w-full overflow-x-auto">{props.children}</div>;
}

/** `1 warning.` then each warning's own sentence, as drawn under Services and
 *  under the bill. Absent when there are none. */
export function WarningNote(props: { warnings: readonly OneTimeBillWarning[]; t: Translator }) {
  if (props.warnings.length === 0) return null;
  return (
    <p
      className="m-0 mt-3 flex flex-wrap gap-x-3 bg-warning-100 px-3 py-2 text-base text-warning-700"
      role="status"
      data-otb-warnings={props.warnings.length}
    >
      <strong>{props.t("billing.oneTimeBill.warnings.count", { count: props.warnings.length })}</strong>
      {props.warnings.map((warning, index) => (
        <span key={`${warning.key}-${index}`}>{props.t(warning.key, warning.params)}</span>
      ))}
    </p>
  );
}
