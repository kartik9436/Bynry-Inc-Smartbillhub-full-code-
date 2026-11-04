/**
 * DayShareNote — the days a bill line's amount was cut down by (DEF-BIL-8744).
 *
 * A part-month per-kW line is prorated by calendar days (B4.3, DEF-BIL-8743)
 * while its kW and its rate stay whole, so `6 kW · $14.00 · $53.20` did not
 * foot. The server says by how many days (`day_share`, read off the line's
 * own pricing trace) and this prints it under the rate — `19/30 days` — so
 * quantity × rate × days ÷ cycle days is the amount beside it.
 *
 * ONE component for every screen that prints a bill line (B14 rule 43): the
 * one-time bill's review step, the bill detail's Charges tab and the portal's
 * bill detail. A FACT, so a fact's length and no rationale (B14 rule 33).
 * Renders nothing on a line that foots without it.
 */
import type { ReactNode } from "react";

type Translate = (key: string, params?: Record<string, unknown>) => string;

export function DayShareNote(props: {
  share: { days: number; of: number } | null | undefined;
  t: Translate;
}): ReactNode {
  const share = props.share;
  if (!share) return null;
  return (
    <span className="block text-sm font-normal" data-day-share={`${share.days}/${share.of}`}>
      {props.t("billing.bill.line.dayShare", { days: share.days, of: share.of })}
    </span>
  );
}
