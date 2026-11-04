// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — P1.16 (dates read as
//           dates), P1.18 (numbers without four trailing zeros), P1.19 (the
//           service by its name), P1.2 (the window on the order).
// Rules:    IS-8 (an instant shows in the TENANT's zone and format) · hard
//           rule 3 (a quantity keeps its unit) · B14 rules 37/44 (the drawing's
//           *24 Sep, 6:03 AM* is an illustration; the tenant's own format is
//           the standard the screen is built to)
// ───────────────────────────────────────────────────────
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatQuantity } from "@/components/UnitCell";

export interface Regional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** An instant, in the utility's own zone and format, with the time. P1.16:
 *  the Audit tab printed `2026-10-04T05:38:42.963368+00:00`. */
export function whenText(iso: string | null | undefined, regional: Regional): string | null {
  if (iso === null || iso === undefined || iso === "") return null;
  return formatDate(iso, regional.timeZone, regional.dateFormat, true);
}

/** A DUE, which a person picks as a DATE (ruling 23: the raise wizard and the
 *  edit form both offer a date picker) and the server keeps as the tenant's
 *  midnight. A midnight is therefore *no time of its own* and reads as the
 *  date alone — `10/06/2026 00:00` beside a visit window of 08:00–12:00 was a
 *  time nobody chose (`DEF-WRK-9697`). A due stamped from a priority's promise
 *  (raise + SLA hours) carries its own minute and keeps it. */
export function dueText(iso: string | null | undefined, regional: Regional): string | null {
  const full = whenText(iso, regional);
  if (full === null || !full.endsWith(" 00:00")) return full;
  return full.slice(0, -" 00:00".length);
}

/** A promised slot — `10/04/2026 09:00–12:00`. The end's date is dropped when
 *  it is the start's day, which is every slot a dispatcher books. */
export function windowText(
  start: string | null | undefined,
  end: string | null | undefined,
  regional: Regional,
): string | null {
  const from = whenText(start, regional);
  if (from === null) return null;
  const to = whenText(end, regional);
  if (to === null) return from;
  const [fromDay] = from.split(" ");
  const [toDay, toTime] = to.split(" ");
  return fromDay === toDay && toTime !== undefined ? `${from}–${toTime}` : `${from}–${to}`;
}

/** P1.18 — `2.0000 each` → `2 each`, `99999999.0000` → `99,999,999`. The
 *  product's ONE quantity formatter (`UnitCell.formatQuantity`): trailing
 *  zeros carry no measurement, so nothing a meter said is lost. */
export function quantityText(value: string | null | undefined): string | null {
  if (value === null || value === undefined || value === "") return null;
  return formatQuantity(value);
}

/** A reading's range, `0–99,999,999`, or null when either end is open. */
export function rangeText(min: string | null, max: string | null): string | null {
  const low = quantityText(min);
  const high = quantityText(max);
  if (low === null || high === null) return null;
  return `${low}–${high}`;
}
