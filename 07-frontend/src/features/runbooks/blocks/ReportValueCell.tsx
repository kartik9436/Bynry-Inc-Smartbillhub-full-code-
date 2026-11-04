// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1b.
// Rules:    CLAUDE.md hard rule 2 (money 2 · percent 2 · a RATE 4) · hard rule 3
//           (a quantity carries an explicit unit) · `BR-SHL-023` (ONE formatting
//           path) · B14 rule 36 (compose the kit) · B14 rule 31
// Tests:    src/features/runbooks/blocks/blocks.test.tsx
// ───────────────────────────────────────────────────────
//
// **ONE CELL RENDERER, SO NO BLOCK EVER FORMATS A NUMBER.**
// `09-component-inventory.md` states the failure this exists to prevent, in the
// section on money, percent and rate: *"A screen that formats both with one
// helper is wrong in one of the two directions on every row."* All three kinds
// produce a well-formed string from the same stored `8.290000` — `$8.29`, `8.29`
// and `$8.2900` — **which is exactly why reaching for the wrong one is
// invisible.** So the payload declares the KIND and this picks the component;
// no block, and no screen, ever chooses.
import { DateCell } from "@/components/DateCell";
import { MoneyCell, formatRate } from "@/components/MoneyCell";
import { PercentCell } from "@/components/PercentCell";
import { Sparkline } from "@/components/Sparkline";
import { StatusPill } from "@/components/StatusPill";
import { UnitCell } from "@/components/UnitCell";
import { Link } from "react-router-dom";

import type { BlockContext, ReportValue } from "./types";

/**
 * Draw one report value.
 *
 * The switch is exhaustive over the discriminated union, so `tsc` refuses a new
 * kind that nothing draws — which is the compile-time half of `BR-RBS-021`'s
 * closed vocabulary. There is deliberately no `default:` arm: a default would
 * turn a new kind into a silently blank cell instead of a build failure.
 */
export function ReportValueCell(props: { value: ReportValue; ctx: BlockContext }) {
  const { value, ctx } = props;
  switch (value.kind) {
    case "text":
      return <>{value.text}</>;
    case "pill":
      return <StatusPill tone={value.tone}>{value.label}</StatusPill>;
    case "money":
      return <MoneyCell amount={value.amount} currency={value.currency} locale={ctx.locale} />;
    case "unit":
      return <UnitCell quantity={value.quantity} unit={value.unit} locale={ctx.locale} />;
    case "rate":
      // ⚠ `formatRate`, NEVER `formatMoney`. A rate is multiplied by a quantity
      // before it becomes money, so its precision compounds: round `$0.0025 per
      // kWh` to two and it prints `$0.00` beside a real charge. PO ruling on
      // `OQ-620`, 2026-08-27, as narrowed 2026-10-02 — up to four decimals.
      return (
        <span className="tabular-nums" data-cell="rate">
          {formatRate(value.rate, value.currency, ctx.locale)}
        </span>
      );
    case "percent":
      return (
        <PercentCell
          value={value.value}
          basis={value.basis}
          direction={value.direction}
          signed={value.signed}
          locale={ctx.locale}
        />
      );
    case "date":
      // The zone and the format come from the CONTEXT, never from the payload —
      // one formatting path, and `DEF-SHL-3964` is what an optional prop costs.
      return (
        <DateCell
          value={value.value}
          timeZone={ctx.timeZone}
          dateFormat={ctx.dateFormat}
          withTime={value.withTime}
        />
      );
    case "sparkline":
      return (
        <Sparkline
          points={value.points}
          label={value.label}
          source={value.source}
          markAt={value.markAt}
        />
      );
    case "link":
      // The fix route. `TC-RBS-14`'s static scan is *no failure reason without a
      // fix route*, and this is where the route lands.
      //
      // ⚠ **`ctx.toHref`, NEVER `value.to` — `DEF-RBS-4329`.** Every runbook
      // emits its routes tenant-relative (`settings/services`,
      // `payments/record`), following `tenancy.selectors.CHECKLIST_TARGETS`,
      // because the shell is what knows the tenant. Handed straight to `<Link
      // to>`, React Router resolved it against the CURRENT route — so from
      // `/:tenant/runbooks/:key/runs/:runId` every Fix link in the product
      // pointed at `…/runs/<id>/settings/services` and opened onto *"This
      // screen is not built yet."*
      //
      // It hid because three separate checks all looked one step short: the
      // backend suites assert the STRING, `blocks.test.tsx` renders this Link
      // outside any tenant route, and the browser check asserted an href
      // ENDING in the route — which a wrongly PREFIXED href still satisfies.
      // The check that found it clicked the link and read the screen.
      return (
        <Link to={ctx.toHref(value.to)} className="text-base underline" data-fix-route="">
          {value.label}
        </Link>
      );
  }
}

/** Plain text for a value, where markup will not do — a `title`, an
 *  `aria-label`, a CSV cell. Returns `null` for the kinds that have no honest
 *  one-line text (a sparkline is a picture; a pill has one). */
export function reportValueText(value: ReportValue): string | null {
  switch (value.kind) {
    case "text":
      return value.text;
    case "pill":
      return value.label;
    case "link":
      return value.label;
    case "sparkline":
      return value.label;
    default:
      // Money, rate, percent, unit and date are FORMATTED values, and formatting
      // them a second time here would be the second path `BR-SHL-023` forbids.
      return null;
  }
}
