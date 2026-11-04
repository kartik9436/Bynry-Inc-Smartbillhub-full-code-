// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10164 (PO 2026-10-17 — Premises and Units lists show
//           Created + Age). THE ONE AGE ARITHMETIC IN THE PRODUCT: the asset
//           and account age columns reuse it (PO: "use same code components").
// Rules:    BR-SHL-023 (tenant zone, one date path) · B14 rule 35 (the words
//           come from each catalogue, never from here)
// Tests:    07-frontend/src/lib/age.test.ts
// ───────────────────────────────────────────────────────
// An AGE is the calendar distance between two of the UTILITY's days — never a
// count of 24-hour periods, and never read on the browser's clock. The start
// may be a calendar date (`YYYY-MM-DD`, used as written) or an instant (turned
// into a day in the tenant's zone first); the end defaults to today in that
// same zone, so both halves of one subtraction are read on one clock
// (`DEF-CUS-6433`'s lesson, server side).
//
// ⚠ **WHOLE MONTHS ARE COUNTED BY ANNIVERSARY, CLAMPED TO THE MONTH'S END.**
// One month after 31 January is 28 (or 29) February, and one year after
// 29 February 2024 is 28 February 2025. So `2026-01-31 → 2026-02-28` is
// `1 mo`, not `28 days` — a property set up on the last day of a month has
// its monthly anniversary on the last day of every shorter month.
//
// The API below is shared and STABLE: `ageBetween`, `formatAge`, `dayInZone`.
import { todayInZone } from "@/components/DateCell";

export interface Age {
  years: number;
  months: number;
  days: number;
}

const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A calendar date as written, or an instant as a day in `timeZone`.
 *  `null` for anything that is neither. */
export function dayInZone(value: string | null | undefined, timeZone: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (DATE_ONLY_RE.test(value)) return value;
  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) return null;
  return todayInZone(timeZone, moment);
}

function parts(day: string): [number, number, number] {
  const match = DATE_ONLY_RE.exec(day);
  if (match === null) throw new Error(`not a calendar date: ${day}`);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function daysInMonth(year: number, month: number): number {
  // month is 1-based; day 0 of the next month is the last day of this one.
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** `start` moved forward by `count` whole months, clamped to the month end. */
function addMonths(year: number, month: number, day: number, count: number): number {
  const index = year * 12 + (month - 1) + count;
  const y = Math.floor(index / 12);
  const m = (index % 12) + 1;
  return Date.UTC(y, m - 1, Math.min(day, daysInMonth(y, m)));
}

/**
 * Whole years, then whole months, then days, from `start` to `end`
 * (`end` null = today in `timeZone`). `null` when `start` is missing or
 * unreadable, or when it falls after `end` — an age cannot be negative, and
 * `0 days` would be a different claim.
 */
export function ageBetween(start: string | null, end: string | null, timeZone: string): Age | null {
  const from = dayInZone(start, timeZone);
  const to = end === null ? todayInZone(timeZone) : dayInZone(end, timeZone);
  if (from === null || to === null) return null;
  const [sy, sm, sd] = parts(from);
  const [ey, em, ed] = parts(to);
  const endUtc = Date.UTC(ey, em - 1, ed);
  if (Date.UTC(sy, sm - 1, sd) > endUtc) return null;
  let total = (ey - sy) * 12 + (em - sm);
  if (addMonths(sy, sm, sd, total) > endUtc) total -= 1;
  const anchor = addMonths(sy, sm, sd, total);
  const days = Math.round((endUtc - anchor) / 86_400_000);
  return { years: Math.floor(total / 12), months: total % 12, days };
}

/** The translator this needs — `i18next`'s `t`, narrowed to what is used. */
export type AgeTranslator = (key: string, options?: Record<string, unknown>) => string;

/**
 * `30 yrs 7 mos` · `4 mos` · `12 days`, singulars by the catalogue's plural
 * forms (`common.age.years_one` = `1 yr`). Years and months when there is a
 * year; months alone under a year; days alone under a month (`0 days` on the
 * day itself). A whole number of years reads `5 yrs`, with no `0 mos`.
 */
export function formatAge(age: Age, t: AgeTranslator): string {
  if (age.years > 0) {
    const years = t("common.age.years", { count: age.years });
    if (age.months === 0) return years;
    return t("common.age.joined", {
      years,
      months: t("common.age.months", { count: age.months }),
    });
  }
  if (age.months > 0) return t("common.age.months", { count: age.months });
  return t("common.age.days", { count: age.days });
}
