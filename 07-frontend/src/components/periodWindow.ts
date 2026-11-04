// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-LED-10071 (J3 — the Journal's Period filter) · DEF-LED-10072
//           (P1/P2/P4 — the Trial balance period becomes a control)
// Ruling:   12-governance/02-decision-log.md 2026-10-12 "FINANCE: JOURNAL
//           SEARCH AND THE PERIOD CONTROLS", CONFIRMED (PO: *"this good please
//           start and fix it"*)
// Rules:    BR-SHL-023 (a calendar date never round-trips through a zone) ·
//           BR-TEN-043 (no money screen reads a clock the caller did not state)
// ───────────────────────────────────────────────────────
//
// The ARITHMETIC of a period, with no React in it — so `tableTypes` can name a
// choice's type, `FilterBar` and `PeriodPicker` can share one definition of
// "Last 30 days", and every rule here is provable without a DOM.
//
// ⚠ **`today` IS ALWAYS THE CALLER'S, AND IT IS THE UTILITY'S BUSINESS DATE.**
// Nothing here reads a clock. A screen passes `todayInZone(<tenant zone>,
// now())` — the tenant's own calendar day, never the browser's (BR-TEN-043):
// at 9pm in Houston a UTC clock is already on tomorrow, and "Last 30 days"
// would quietly drop the oldest day a clerk meant to see.
//
// ⚠ **CALENDAR ARITHMETIC IS DONE IN UTC ON PURPOSE.** `Date.UTC` is used only
// to count days between two calendar dates, and a calendar date has no zone
// (BR-SHL-023), so no daylight-saving shift can move a boundary.

// ⚠ NO IMPORT FROM `tableTypes`, deliberately: `tableTypes` imports THIS file
// to restore a period from the URL, and the edge must point one way only.

/** Every quick choice the shared picker knows, in the order it offers them. */
export const PERIOD_CHOICES = [
  "this_month",
  "last_month",
  "last_30",
  "last_60",
  "last_90",
  "custom",
] as const;
export type PeriodChoice = (typeof PERIOD_CHOICES)[number];

/** P2 — the Trial balance offers all six. */
export const BALANCE_PERIOD_CHOICES: readonly PeriodChoice[] = PERIOD_CHOICES;
/** J3 — the Journal's filter offers the rolling windows and Custom. */
export const JOURNAL_PERIOD_CHOICES: readonly PeriodChoice[] = [
  "last_30",
  "last_60",
  "last_90",
  "custom",
];

export function isPeriodChoice(value: unknown): value is PeriodChoice {
  return (PERIOD_CHOICES as readonly unknown[]).includes(value);
}

/** One chosen window. `from`/`to` are calendar dates, `YYYY-MM-DD`, inclusive. */
export interface PeriodValue {
  choice: PeriodChoice;
  from: string;
  to: string;
}

/** The month a "This month" means — the finance period being worked in. */
export interface PeriodMonth {
  start: string;
  end: string;
}

function toUtc(day: string): number {
  const [y, m, d] = day.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

function fromUtc(ms: number): string {
  const at = new Date(ms);
  const y = at.getUTCFullYear();
  const m = String(at.getUTCMonth() + 1).padStart(2, "0");
  const d = String(at.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * Is this a real calendar day, `YYYY-MM-DD`? A day that does not exist —
 * `2026-02-31` — comes back from the UTC round trip as a different string.
 */
export function isPeriodDay(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && fromUtc(toUtc(value)) === value;
}

/** `day` moved by `n` calendar days. */
export function addDays(day: string, n: number): string {
  return fromUtc(toUtc(day) + n * 86_400_000);
}

/** `day` moved back one calendar month, clamped to that month's last day. */
function previousMonthSameDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  const year = m === 1 ? y - 1 : y;
  const month = m === 1 ? 12 : m - 1;
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return `${year}-${String(month).padStart(2, "0")}-${String(Math.min(d, last)).padStart(2, "0")}`;
}

function firstOfMonth(day: string): string {
  return `${day.slice(0, 8)}01`;
}

/**
 * The window a quick choice means on `today`, or `null` for Custom.
 *
 * * **Last N days** is N calendar days ENDING TODAY, both ends included —
 *   *Last 30 days* on 12 October is 13 September to 12 October.
 * * **This month** is the finance month being worked in (`month`), from its
 *   first day up to today — **P4: a period cannot end after today**, so the
 *   month's own end is clamped to the business date while the month is still
 *   running. With no month served it is the calendar month of `today`.
 * * **Last month** is the month before that one, whole.
 */
export function periodWindow(
  choice: PeriodChoice,
  today: string,
  month?: PeriodMonth | null,
): { from: string; to: string } | null {
  switch (choice) {
    case "last_30":
      return { from: addDays(today, -29), to: today };
    case "last_60":
      return { from: addDays(today, -59), to: today };
    case "last_90":
      return { from: addDays(today, -89), to: today };
    case "this_month": {
      const start = month?.start ?? firstOfMonth(today);
      const end = month?.end ?? today;
      return { from: start, to: end < today ? end : today };
    }
    case "last_month": {
      const start = month?.start ?? firstOfMonth(today);
      return { from: previousMonthSameDay(start), to: addDays(start, -1) };
    }
    case "custom":
      return null;
  }
}

/** Which quick choice a window IS on `today`, or Custom when it is none of them. */
export function choiceFor(
  from: string,
  to: string,
  today: string,
  choices: readonly PeriodChoice[],
  month?: PeriodMonth | null,
): PeriodChoice {
  for (const choice of choices) {
    const window = periodWindow(choice, today, month);
    if (window !== null && window.from === from && window.to === to) return choice;
  }
  return "custom";
}

/** P4 — why a typed window is refused, or `null` when it may be applied. */
export type PeriodRefusal = "incomplete" | "toBeforeFrom" | "endsAfterToday";

export function periodRefusal(from: string, to: string, today: string): PeriodRefusal | null {
  if (!isPeriodDay(from) || !isPeriodDay(to)) return "incomplete";
  if (to < from) return "toBeforeFrom";
  if (to > today) return "endsAfterToday";
  return null;
}

/**
 * The window a stored value MEANS today: a quick choice is re-counted from the
 * business date (a link saying *Last 30 days* means the last thirty days on
 * the day it is opened), and Custom keeps the dates it carries.
 */
export function resolvePeriod(
  value: PeriodValue,
  today: string,
  month?: PeriodMonth | null,
): { from: string; to: string } {
  return periodWindow(value.choice, today, month) ?? { from: value.from, to: value.to };
}
