// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories)  Screens: every date/timestamp display (S17, S30, S33, S36, S39, …)
// Rules:    BR-SHL-023 (tenant TZ + regional format, one formatting path)
// ───────────────────────────────────────────────────────
// FE-13 DateCell (B13 §1): THE date/timestamp display. The tenant's timezone
// and regional date format arrive as props (IS-8 — Settings → Company →
// Regional & Formats; fed by US-SHL-013's service wiring), so switching the
// tenant setting re-renders every date with no code change (US-SHL-013 TC-1).
// Two input shapes, deliberately distinct:
//   · calendar date "YYYY-MM-DD" — formatted from the string itself. A due
//     date has no timezone; running it through one could shift the day.
//   · instant (ISO timestamp) — converted INTO the tenant TZ before display.
// Time renders 24h; the tenant time-format preference joins with the
// US-SHL-013 formatting-service wiring.
import i18n from "@/i18n";

// PO ruling 2026-08-10 ("more date formats", then "we also need DD-MMM-YY"):
// SEVEN, up from three.
//
// Six are purely numeric and cover every convention the eleven BR-SHL-041
// locales use. The seventh, `DD-MMM-YY`, is the one that carries a month NAME —
// which is prose, and prose has to come from somewhere. It comes from `Intl`
// (see monthShort below), not from a translation catalog, so it is already
// correct in all eleven and cannot go stale when a twelfth is added. That is
// what makes the month-name format safe here; hand-listing "Jan…Dec" would not
// have been.
export type RegionalDateFormat =
  | "MM/DD/YYYY" // United States
  | "DD/MM/YYYY" // most of the world, incl. es-419 · pt-BR · id-ID · it-IT
  | "YYYY-MM-DD" // ISO 8601
  | "DD.MM.YYYY" // de-DE and much of continental Europe
  | "DD-MM-YYYY" // hi-IN and Dutch convention
  | "YYYY/MM/DD" // ja-JP · ko-KR
  | "DD-MMM-YY"; // PO 2026-08-10 — the one month-NAME format (25-Aug-26)

/**
 * The seven formats above, as a value.
 *
 * DEF-SHL-3964: the union is a TYPE, and `tenant_settings.date_format` is a
 * bare TEXT column — so something has to check at runtime that what the server
 * sent is one of the seven. This is that list, and it lives here rather than in
 * the Settings screen because `arrange()` below is the exhaustive switch it has
 * to agree with. `SettingsRegionalTab` reads it from here for its dropdown, so
 * there is one list and it cannot drift from the switch.
 */
export const REGIONAL_DATE_FORMATS: readonly RegionalDateFormat[] = [
  "MM/DD/YYYY",
  "DD/MM/YYYY",
  "YYYY-MM-DD",
  "DD.MM.YYYY",
  "DD-MM-YYYY",
  "YYYY/MM/DD",
  "DD-MMM-YY",
];

/** True when `value` is one of the seven the product renders (DEF-SHL-3964). */
export function isRegionalDateFormat(value: unknown): value is RegionalDateFormat {
  return typeof value === "string" && REGIONAL_DATE_FORMATS.includes(value as RegionalDateFormat);
}

const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

// The abbreviated month name for `DD-MMM-YY`, in the LANGUAGE THE APP IS
// RENDERING. This is why the other six formats are numeric: a month name is
// prose, and prose has to come from somewhere. `Intl` is that somewhere — it
// ships localized month names for every one of the eleven BR-SHL-041 locales,
// so this needs no catalog entry and cannot go stale when a language is added.
//
// BR-SHL-023 still holds. The Date built here is used ONLY to look up a month
// name — never to derive the day or the year, which stay the literal digits
// parsed out of the value. Mid-month at noon UTC keeps the lookup itself immune
// to any offset; nothing about it can shift a calendar date.
export function monthLabel(
  month: string | number,
  locale: string,
  style: "short" | "long" = "short",
): string {
  const index = Number(month) - 1;
  if (!Number.isInteger(index) || index < 0 || index > 11) return String(month);
  try {
    return new Intl.DateTimeFormat(locale, { month: style, timeZone: "UTC" }).format(
      new Date(Date.UTC(2000, index, 15, 12)),
    );
  } catch {
    return String(month); // unknown locale tag — digits beat an exception
  }
}

// ⚠ **EXPORTED AS `monthLabel` ON 2026-09-18 (`DEF-RAT-5733`), AND THE ONLY
// CHANGE IS THE `style` ARGUMENT AND THE NAME.** The season editor needs the
// FULL month name for its picker (*April*) and the SHORT one for the range it
// echoes back (*1 Apr – 30 Sep*), and B14 rule 35 says a catalogue is written
// in its own language rather than translated from English — which twelve
// hand-written month names in eleven catalogues would breach on the day a
// twelfth language is added. `Intl` already ships them, which is the argument
// the comment above made for `DD-MMM-YY` and it is the same argument here.
// `monthShort` stays as the call site `arrange` already had, so no existing
// output moves by a byte.
function monthShort(month: string, locale: string): string {
  return monthLabel(month, locale, "short");
}

function arrange(
  format: RegionalDateFormat,
  y: string,
  m: string,
  d: string,
  locale: string,
): string {
  switch (format) {
    case "MM/DD/YYYY":
      return `${m}/${d}/${y}`;
    case "DD/MM/YYYY":
      return `${d}/${m}/${y}`;
    case "DD.MM.YYYY":
      return `${d}.${m}.${y}`;
    case "DD-MM-YYYY":
      return `${d}-${m}-${y}`;
    case "YYYY/MM/DD":
      return `${y}/${m}/${d}`;
    case "YYYY-MM-DD":
      return `${y}-${m}-${d}`;
    case "DD-MMM-YY":
      // Two-digit year, as the PO specified. Worth knowing: a 2-digit year is
      // ambiguous on a document someone files for seven years — this is a
      // SCREEN format, and IS-11 keeps every CSV export on ISO-8601 regardless.
      return `${d}-${monthShort(m, locale)}-${y.slice(-2)}`;
  }
}

/**
 * **THE MIRROR OF `formatDate` FOR A CALENDAR DATE: what a person TYPED in the
 * utility's own format, back to `YYYY-MM-DD` — or `null` when it is not a real
 * date in that format** (`DEF-CUS-6358`, PO 2026-09-23: pickers follow the
 * utility's date format).
 *
 * ⚠ **IT LIVES HERE, BESIDE `arrange`, FOR BR-SHL-023's REASON.** One file owns
 * how a date is written on screen; a second file that owned how it is READ
 * would drift from it the first time a format was added. Every one of the
 * seven `REGIONAL_DATE_FORMATS` is parsed, and a test walks all seven through
 * `formatDate` and back.
 *
 * Accepted as well, whatever the format: ISO `YYYY-MM-DD` (what a paste from
 * another system usually is), any of `/ . -` or a space as the separator, and
 * one-digit days and months. `DD-MMM-YY`'s month is matched against the month
 * names `Intl` gives for `locale` and for English, case-blind, or as digits.
 *
 * ⚠ **A TWO-DIGIT YEAR IS AMBIGUOUS AND IS RESOLVED, NEVER GUESSED SILENTLY.**
 * It is read as this century unless that lands after `max` (a date of birth),
 * in which case it is the century before. With no `max` it is this century.
 * No `Date` is built from the parts except to check the day exists in the month.
 */
export function parseRegionalDate(
  text: string,
  dateFormat: RegionalDateFormat,
  options: { locale?: string; max?: string } = {},
): string | null {
  const raw = text.trim();
  if (raw === "") return null;
  const iso = DATE_ONLY_RE.exec(raw);
  if (iso !== null) return realDate(iso[1], iso[2], iso[3]);
  const parts = raw.split(/[\s./-]+/).filter((part) => part !== "");
  if (parts.length !== 3) return null;
  const locale = options.locale ?? (i18n.language || "en");
  let y: string;
  let m: string;
  let d: string;
  switch (dateFormat) {
    case "MM/DD/YYYY":
      [m, d, y] = parts;
      break;
    case "DD/MM/YYYY":
    case "DD.MM.YYYY":
    case "DD-MM-YYYY":
      [d, m, y] = parts;
      break;
    case "YYYY/MM/DD":
    case "YYYY-MM-DD":
      [y, m, d] = parts;
      break;
    case "DD-MMM-YY": {
      [d, m, y] = parts;
      const month = monthFromText(m, locale);
      if (month === null) return null;
      m = month;
      break;
    }
  }
  if (!/^\d{1,2}$/.test(d) || !/^\d{1,2}$/.test(m)) return null;
  if (/^\d{2}$/.test(y)) {
    y = centuryFor(y, options.max);
  }
  if (!/^\d{4}$/.test(y)) return null;
  return realDate(y, m.padStart(2, "0"), d.padStart(2, "0"));
}

/** The month a typed `Aug` / `août` / `8` names, as two digits, or null. */
function monthFromText(text: string, locale: string): string | null {
  if (/^\d{1,2}$/.test(text)) return text.padStart(2, "0");
  const needle = text.toLowerCase().replace(/\.$/, "");
  for (const tag of [locale, "en"]) {
    for (let index = 1; index <= 12; index += 1) {
      for (const style of ["short", "long"] as const) {
        const name = monthLabel(index, tag, style).toLowerCase().replace(/\.$/, "");
        if (name === needle) return String(index).padStart(2, "0");
      }
    }
  }
  return null;
}

/** This century, or the one before when this one lands after `max`. */
function centuryFor(yy: string, max?: string): string {
  const thisCentury = `20${yy}`;
  if (max === undefined || !DATE_ONLY_RE.test(max)) return thisCentury;
  return thisCentury > max.slice(0, 4) ? `19${yy}` : thisCentury;
}

/** `YYYY-MM-DD` when the day exists in that month, otherwise null. */
function realDate(y: string, m: string, d: string): string | null {
  const month = Number(m);
  const day = Number(d);
  if (month < 1 || month > 12 || day < 1) return null;
  const last = new Date(Date.UTC(Number(y), month, 0)).getUTCDate();
  return day > last ? null : `${y}-${m}-${d}`;
}

export function formatDate(
  value: string,
  timeZone: string,
  dateFormat: RegionalDateFormat,
  withTime = false,
  // Only `DD-MMM-YY` reads this. Defaults to the language the app is currently
  // rendering, so a month name never disagrees with the sentence around it.
  locale: string = i18n.language || "en",
): string {
  const dateOnly = DATE_ONLY_RE.exec(value);
  if (dateOnly !== null) {
    // BR-SHL-023: a calendar date is the same calendar date in every tenant —
    // no Date() round-trip (parsing "2026-08-25" as UTC midnight and then
    // rendering in a TZ west of it would show the 24th).
    const [, y, m, d] = dateOnly;
    return arrange(dateFormat, y, m, d, locale);
  }
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) {
    return value; // malformed — verbatim beats "Invalid Date"
  }
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone, // tenant TZ — an instant always displays in tenant time (IS-8)
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(instant);
    const get = (type: Intl.DateTimeFormatPartTypes): string =>
      parts.find((p) => p.type === type)?.value ?? "";
    const date = arrange(dateFormat, get("year"), get("month"), get("day"), locale);
    return withTime ? `${date} ${get("hour")}:${get("minute")}` : date;
  } catch {
    return value; // unknown timezone id — verbatim beats a crashed screen
  }
}

/**
 * ⛔ **WHAT THE NATIVE `<input type="date">` WILL PRINT, AS BEST IT CAN BE
 * ASKED — and this exists to stop a date field printing its own value twice
 * (CR-043 finding 15).**
 *
 * PO, on the Run bills wizard: *Period from* showed `08/01/2026` in the picker
 * and `08/01/2026` again as grey text underneath it, *"and a clerk asks which
 * one counts"*.
 *
 * **The grey line is not a bug and must not simply be deleted.** IS-8 says a
 * date renders in the TENANT's Regional format (Settings → Company). The
 * native control ignores that completely — it renders in the BROWSER's own
 * locale — so a German tenant on a US-configured browser genuinely sees
 * `08/01/2026` in the box when their format says `01.08.2026`, and the line
 * beneath is the only place their format appears. Removing it would break IS-8
 * for exactly the tenants it was written for.
 *
 * What is redundant is the case where the two agree, which is the ordinary one.
 * So the line is rendered **only when it would say something the input does
 * not** — and this function is how that is decided.
 *
 * ⚠ **IT IS AN APPROXIMATION AND THAT IS STATED ON PURPOSE.** No API reports
 * what a native date input renders. Chrome follows the browser's UI language,
 * Firefox the OS regional setting; `Intl` with no locale argument resolves the
 * browser's default, which is the closest thing available and agrees with both
 * in the ordinary case. The residual risk is bounded and one-directional: if
 * the guess says *"identical"* and the input actually prints something else,
 * the tenant format is hidden — never wrong, only absent. It is never shown
 * incorrectly, and any disagreement about the FORMAT still shows the line.
 * `null` (an unknown locale, a malformed value) errs toward SHOWING it.
 */
/**
 * **TODAY, IN THE TENANT'S OWN TIMEZONE, AS `YYYY-MM-DD`** — the calendar-date
 * string every date input and every `min`/`max` bound in this product speaks.
 *
 * ⚠ **IT EXISTS BECAUSE THREE SCREENS PROPOSED NO DATE AT ALL AND NOBODY COULD
 * SEE IT** (`DEF-MET-4991`). `BR-PAY-033` says the UI ALWAYS proposes a
 * pre-filled default date, and `DatePickerField` honours that faithfully — for
 * whatever its consumer passes as `prefill`. Reassign, Log repair and Retire
 * each read `today` from a prop, and `App.tsx` mounts all three with **no props
 * at all**, so `prefill` was `undefined` and all three rendered `value=""` in
 * the shipped product. Measured in Chromium at 1440 and 1280. That is hard-won
 * law 2 exactly — *a component with an optional prop that nothing passes is
 * dead UI* — and it hid because the unit tests pass `today` explicitly, so
 * every one of them was green over a screen the router wires differently.
 *
 * ⚠ **THE TENANT'S ZONE AND NOT THE BROWSER'S, AND NOT UTC.** `todayIso()` in
 * `billingOpsShared` slices an ISO instant, which is UTC — fine for the write
 * it stamps, and wrong for a `max="not in the future"` bound, where a tenant
 * behind UTC would be refused their own today for several hours each evening.
 * `useRegional` already resolves the tenant's zone on every one of these
 * screens (`IS-8`), so the bound uses it.
 *
 * An unknown zone id returns the browser's own day rather than throwing: a
 * crashed screen is a worse answer than a date that may be one day out, and
 * `Intl` is the same guard `formatDate` above already uses.
 */
export function todayInZone(timeZone: string, now: Date = new Date()): string {
  try {
    // `en-CA` renders exactly `YYYY-MM-DD`, which is the calendar-date string
    // this product uses end to end — no parsing, no re-assembly.
    return new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
  } catch {
    return new Intl.DateTimeFormat("en-CA", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
  }
}

/** `YYYY-MM-DDTHH:mm`, with the seconds some browsers append. */
const WALL_CLOCK_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?$/;

/**
 * **NOW, AS A WALL CLOCK IN THE TENANT'S OWN ZONE** — `YYYY-MM-DDTHH:mm`, the
 * value an `<input type="datetime-local">` holds. `todayInZone`'s sibling, and
 * here for the same reason: one formatting path (BR-SHL-023), never a second
 * derivation at a call site.
 *
 * ⚠ **IT RETURNS A WALL CLOCK AND NOT AN INSTANT, WHICH IS THE POINT.** At
 * 20:59 UTC a Houston utility is at 15:59 and this answers `…T15:59`. That is
 * what the clerk's screen says and what they would write on a slip; the zone it
 * belongs to is the tenant's, and `apps/payments/api._moment` anchors it there
 * on arrival (BR-TEN-081 / OQ-153, *"a time of day with no zone … came from a
 * human in that utility"*). Converting it to an offset here would mean deriving
 * the tenant's UTC offset — DST included — in the browser, which is the same
 * answer computed twice in two places.
 */
export function nowInZone(timeZone: string, now: Date = new Date()): string {
  const build = (zone: string | undefined): string => {
    const parts = new Intl.DateTimeFormat("en-CA", {
      ...(zone === undefined ? {} : { timeZone: zone }),
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23", // 24-hour, and `00` rather than `24` at midnight
    }).formatToParts(now);
    const get = (type: Intl.DateTimeFormatPartTypes): string =>
      parts.find((p) => p.type === type)?.value ?? "";
    return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
  };
  try {
    return build(timeZone);
  } catch {
    // An unknown IANA id. The browser's own zone is the only thing left, and a
    // wrong-by-hours default a clerk can see and correct beats a crashed form.
    return build(undefined);
  }
}

/**
 * **THE EARLIEST AND LATEST MOMENT A COUNTER SCREEN WILL ACCEPT** —
 * `BR-PAY-1191`, PO ruling 2026-09-23, verbatim: *"(b) Backdate within the
 * same day"*.
 *
 * Midnight on the utility's own day, and now. Backward within today is the
 * correction the picker exists for (a clerk who opened at 09:00 and started
 * the till at 11:00); yesterday moves a shift's takings into a day that is
 * already reported, and forward is scheduling rather than correcting.
 *
 * ⚠ **ONE DEFINITION, FOUR SCREENS, AND THE SERVER AGREES WITH IT BY
 * CONSTRUCTION.** `apps/payments/counters_api._refuse_a_moment_off_today`
 * applies the same bound through `settings_seam.tenant_now()`, which resolves
 * the same tenancy clock `nowInZone` is rendering against. Computing the day
 * boundary a second way at a call site is how the screen and the rule come to
 * disagree — which is `DEF-094` exactly, one layer up.
 */
export function sameDayBounds(
  timeZone: string,
  now: Date = new Date(),
): { min: string; max: string } {
  const wall = nowInZone(timeZone, now);
  return { min: `${wall.slice(0, 10)}T00:00`, max: wall };
}

/**
 * A wall clock rendered in the TENANT's date format — `09/23/2026 15:59`.
 *
 * ⚠ **NO TIMEZONE ROUND-TRIP, EVER.** The value is already in the tenant's
 * zone, so this re-arranges its parts exactly as the calendar-date branch of
 * `formatDate` does. Handing `new Date()` a naive string would parse it as the
 * BROWSER's local time and then render it somewhere else again — the drift
 * `DEF-SHL-3964` is about, rebuilt one layer down.
 *
 * The time is always 24-hour: `RegionalDateFormat` has seven values and none of
 * them says anything about a clock, so there is no tenant setting to obey and
 * inventing one here would be a setting nothing honours (hard-won law 1).
 */
export function formatWallClock(
  value: string,
  dateFormat: RegionalDateFormat,
  locale: string = i18n.language || "en",
): string {
  const parts = WALL_CLOCK_RE.exec(value);
  if (parts === null) {
    return value; // malformed — verbatim beats "Invalid Date"
  }
  const [, y, m, d, hh, mm] = parts;
  return `${arrange(dateFormat, y, m, d, locale)} ${hh}:${mm}`;
}

/**
 * The IS-8 line beneath a datetime input, or `null` when it would repeat what
 * the control already shows. `regionalDateEcho`'s sibling, and it carries the
 * same stated approximation: no API reports what a native picker renders, so
 * `Intl` in the browser's own locale is the closest available guess.
 *
 * ⚠ **THE HOUR CYCLE IS DELIBERATELY NOT FORCED HERE.** `formatWallClock`
 * always says 24-hour; a `datetime-local` on an `en-US` browser says
 * `3:59 PM`. Asking `Intl` for the locale's OWN cycle is what makes the two
 * compare unequal in that case, so the tenant's line is shown — which is
 * correct, because the control genuinely is not saying it. Forcing `h23` on
 * both sides would call them identical and hide it.
 */
export function regionalDateTimeEcho(
  value: string,
  dateFormat: RegionalDateFormat,
  locale?: string,
): string | null {
  const parts = WALL_CLOCK_RE.exec(value);
  if (parts === null) {
    return null; // nothing in the control to duplicate
  }
  const [, y, m, d, hh, mm] = parts;
  const ours = formatWallClock(value, dateFormat, locale ?? (i18n.language || "en"));
  let theirs: string;
  try {
    theirs = new Intl.DateTimeFormat(locale, {
      timeZone: "UTC", // the wall clock is read back exactly as it was written
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(Date.UTC(Number(y), Number(m) - 1, Number(d), Number(hh), Number(mm))));
  } catch {
    return ours; // unknown locale tag — show the line rather than guess
  }
  // `Intl` separates the date and the time with a comma; a picker does not.
  return theirs.replace(", ", " ") === ours ? null : ours;
}

export function browserDateText(value: string, locale?: string): string | null {
  const dateOnly = DATE_ONLY_RE.exec(value);
  if (dateOnly === null) {
    return null; // not a calendar date — the picker holds nothing to duplicate
  }
  const [, y, m, d] = dateOnly;
  try {
    return new Intl.DateTimeFormat(locale, {
      timeZone: "UTC", // a calendar date never routes through a zone (this file's law)
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date(Date.UTC(Number(y), Number(m) - 1, Number(d), 12)));
  } catch {
    return null; // unknown locale tag — show the line rather than guess
  }
}

/**
 * The IS-8 line beneath a date input, or `null` when it would be the same
 * characters the input is already showing.
 *
 * One function rather than a comparison at the call site, because there is one
 * date-picker component and this is the whole of the rule: **say the tenant's
 * format whenever the control is not already saying it.**
 */
export function regionalDateEcho(
  value: string,
  dateFormat: RegionalDateFormat,
  locale?: string,
): string | null {
  if (value === "") {
    return null;
  }
  const ours = formatDate(value, "UTC", dateFormat);
  const theirs = browserDateText(value, locale);
  return theirs === ours ? null : ours;
}

/**
 * CR-028 (B16 §4.8, the measured drift list): r10's list columns print dates
 * at MONTH-YEAR density — "Mar 2024" in Installed, "Sep 2030" in Warranty.
 * Same discipline as `DD-MMM-YY`: the month NAME comes from `Intl` in the
 * language the app is rendering, so it needs no catalog entry, and the day and
 * year are never derived through a timezone round-trip. Display density only —
 * the machine-readable value on the `<time>` element stays the full date, and
 * IS-11 keeps every CSV export on ISO-8601 regardless.
 */
export function formatMonthYear(
  value: string,
  timeZone: string,
  locale: string = i18n.language || "en",
): string {
  const dateOnly = DATE_ONLY_RE.exec(value);
  if (dateOnly !== null) {
    const [, y, m] = dateOnly;
    return `${monthShort(m, locale)} ${y}`;
  }
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) {
    return value; // malformed — verbatim beats "Invalid Date"
  }
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone, // an instant always displays in tenant time (IS-8)
      year: "numeric",
      month: "2-digit",
    }).formatToParts(instant);
    const get = (type: Intl.DateTimeFormatPartTypes): string =>
      parts.find((p) => p.type === type)?.value ?? "";
    return `${monthShort(get("month"), locale)} ${get("year")}`;
  } catch {
    return value; // unknown timezone id — verbatim beats a crashed screen
  }
}

/**
 * **THE ONE DATE SHAPE A SCREEN USES WHEN IT MUST NOT BE READ TWO WAYS —
 * `1 Jun 2026`** (`DEF-MET-4689`, `BR-MET-1167`, CR-089 wave H).
 *
 * `06/01/2026` is 1 June to a Texan and 6 January to almost everyone else, and
 * **nothing on a screen tells a reader which convention it is in**. A named
 * month removes every reading but the right one; that is the whole of the
 * argument, and it is why this exists beside the seven regional formats rather
 * than as an eighth one.
 *
 * ⚠ **IT DOES NOT OVERRIDE `BR-SHL-023` — IT IS THE SAME DEPARTURE
 * `formatMonthYear` AND `formatMonthDay` ALREADY MAKE, FOR THE SAME REASON.**
 * Those two also ignore the tenant's chosen arrangement and take their month
 * name from `Intl`, because a display DENSITY is a property of the place a date
 * is drawn, not of the tenant's numeric preference. This is a display
 * UNAMBIGUITY and it is the same kind of thing. The tenant's own format still
 * governs every screen that has not asked for this one.
 *
 * ⚠ **FIXED ORDER, LOCALISED MONTH — and the precedent is the PO's own seventh
 * format.** `DD-MMM-YY` (PO 2026-08-10, *"we also need DD-MMM-YY"*) puts the
 * day first and takes `Jun` from `Intl`, in the language the app is rendering;
 * a ja-JP reader would conventionally write the year first, and this does not.
 * That divergence is inherited deliberately rather than invented here: three
 * formatters in this file compose a fixed order with a localised month name,
 * and a fourth arrangement would be a fourth thing to keep in step.
 *
 * The day is printed without a leading zero (`1`, not `01`) so the shape cannot
 * be mistaken for one of the numeric formats at a glance. As everywhere in this
 * file, a calendar date is formatted from its own digits and never routed
 * through a timezone; an instant is converted into the tenant's zone first.
 */
export function formatNamedDate(
  value: string,
  timeZone: string,
  locale: string = i18n.language || "en",
): string {
  const dateOnly = DATE_ONLY_RE.exec(value);
  if (dateOnly !== null) {
    const [, y, m, d] = dateOnly;
    return `${String(Number(d))} ${monthShort(m, locale)} ${y}`;
  }
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) {
    return value; // malformed — verbatim beats "Invalid Date"
  }
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone, // an instant always displays in tenant time (IS-8)
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(instant);
    const get = (type: Intl.DateTimeFormatPartTypes): string =>
      parts.find((p) => p.type === type)?.value ?? "";
    return `${String(Number(get("day")))} ${monthShort(get("month"), locale)} ${get("year")}`;
  } catch {
    return value; // unknown timezone id — verbatim beats a crashed screen
  }
}

/**
 * CR-028 (DEF-592): the sub-meter last-read date at r10's density — "Aug 3".
 * Month name via Intl (see monthShort); day and year never round-trip a
 * timezone. Accepts a calendar date or an ISO timestamp's date prefix.
 */
export function formatMonthDay(value: string, locale: string = i18n.language || "en"): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (match === null) {
    return value; // malformed — verbatim beats a guess
  }
  const [, , m, d] = match;
  return `${monthShort(m, locale)} ${String(Number(d))}`;
}

export interface DateCellProps {
  value: string; // "YYYY-MM-DD" calendar date, or an ISO timestamp
  timeZone: string; // tenant TZ (IANA), e.g. "America/Boise" — REQUIRED (IS-8)
  dateFormat: RegionalDateFormat; // tenant Regional date format — REQUIRED
  withTime?: boolean; // timestamps only: append HH:mm in the tenant TZ
  monthYear?: boolean; // CR-028: r10's list-column density — "Mar 2024"
  //: CR-089 wave H / `BR-MET-1167` — `1 Jun 2026`, the shape a screen uses when
  //: two readings of the same digits would both be plausible. Wins over
  //: `monthYear` when both are set, because it is the more specific request.
  namedMonth?: boolean;
}

export function DateCell(props: DateCellProps) {
  return (
    // <time dateTime> keeps the machine-readable value alongside the display.
    // CR-018 Route B: `.cell-date` (DateCell.css, deleted) ported value for
    // value — `tabular-nums` (A12: dates align in columns) + `whitespace-nowrap`.
    <time className="tabular-nums whitespace-nowrap" dateTime={props.value}>
      {props.namedMonth === true
        ? formatNamedDate(props.value, props.timeZone)
        : props.monthYear === true
          ? formatMonthYear(props.value, props.timeZone)
          : formatDate(props.value, props.timeZone, props.dateFormat, props.withTime)}
    </time>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-22 by the CR-028 AST-W1 lane (formatMonthYear + the `monthYear` prop — r10's month-year list-column density, B16 §4.8; month name via Intl exactly like DD-MMM-YY, so no catalog entry and no timezone round-trip on a calendar date)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope) · [AST-W1 2026-08-22] tsc✔ eslint✔ vitest (assets suite green, see AssetRegistry.test.tsx trailer)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
