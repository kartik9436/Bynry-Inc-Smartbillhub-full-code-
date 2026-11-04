/**
 * How the day's screens write times, durations and distances. Every word
 * comes from the catalogue (`field.time.*`, `field.unit.*`); the numbers are
 * formatted here once so FF-10, FF-11, FF-12, FF-14 and FF-63 agree.
 *
 * Times are the handset's local clock in 24-hour form, as every board draws
 * them (*08:00–12:00*, *last sent 10:02*). The 12/24-hour choice on FF-51
 * Settings is the settings wave's to wire; it is not read here yet.
 */
import { type TFunction } from 'i18next';

function two(n: number): string {
  return String(n).padStart(2, '0');
}

/** `08:00` — the local wall clock. Null in, null out. */
export function clock(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${two(d.getHours())}:${two(d.getMinutes())}`;
}

/** `08:00–12:00`, or the one end that is known, or null. */
export function windowText(start: string | null, end: string | null): string | null {
  const a = clock(start);
  const b = clock(end);
  if (a && b) return `${a}–${b}`;
  return a ?? b;
}

/** `6h 20m`, `48m`, `1h` — a span of the day. */
export function duration(t: TFunction, minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  const h = Math.floor(m / 60);
  const rest = m % 60;
  if (h === 0) return t('field.time.minutesShort', { m: rest });
  if (rest === 0) return t('field.time.hoursShort', { h });
  return t('field.time.hoursMinutes', { h, m: two(rest) });
}

/** `10 min` — an estimate. */
export function estimate(t: TFunction, minutes: number | null): string | null {
  if (minutes == null) return null;
  return t('field.time.minutes', { m: Math.round(minutes) });
}

/** `22 Oct` — a due date, in the app's language. */
export function shortDate(iso: string | null, language: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(language, { day: 'numeric', month: 'short' });
}

/** `Tuesday 21 October` — Home's date line. */
export function longDate(d: Date, language: string): string {
  return d.toLocaleDateString(language, { weekday: 'long', day: 'numeric', month: 'long' });
}

/** `Tue` — a day tab. */
export function weekdayShort(d: Date, language: string): string {
  return d.toLocaleDateString(language, { weekday: 'short' });
}

/**
 * The local day a job belongs to, as `YYYY-MM-DD` — its window start, else
 * its deadline; null when it has neither (FB-029's *No date*). The same day
 * `day.listLater`/`listAll` sort by (SQLite's `'localtime'`), so a heading
 * is drawn once.
 */
export function jobDayKey(job: { windowStart: string | null; dueAt: string | null }): string | null {
  const iso = job.windowStart ?? job.dueAt;
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`;
}

/** `Mon, 3 Nov` — a date heading in the Later and All lists, in the app's language. */
export function headingDate(dayKey: string, language: string): string {
  const [y, m, d] = dayKey.split('-').map(Number);
  return new Date(y ?? 0, (m ?? 1) - 1, d ?? 1).toLocaleDateString(language, { weekday: 'short', day: 'numeric', month: 'short' });
}

const EARTH_RADIUS_MI = 3958.8;

/** Great-circle miles between two points. */
export function milesBetween(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = (x: number) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** `0.2` — one decimal place, as the boards draw a distance. */
export function miles(n: number): string {
  return n.toFixed(1);
}

/** The premises written on one line for a deep link: street, town, region, postcode. */
export function addressForDirections(p: {
  addressLine: string | null;
  locality: string | null;
  region: string | null;
  postalCode: string | null;
}): string | null {
  const town = [p.locality, [p.region, p.postalCode].filter(Boolean).join(' ')].filter(Boolean).join(', ');
  const whole = [p.addressLine, town].filter((x) => x && x.trim() !== '').join(', ');
  return whole === '' ? null : whole;
}

/** `Austin, TX 78704` — FF-14's second address line. */
export function localityLine(p: { locality: string | null; region: string | null; postalCode: string | null }): string | null {
  const tail = [p.region, p.postalCode].filter(Boolean).join(' ');
  const line = [p.locality, tail].filter((x) => x && x !== '').join(', ');
  return line === '' ? null : line;
}

/** `0.2 mi away` from where the handset is, or null with no fix or no point. */
export function distanceText(
  t: TFunction,
  here: { lat: number; lng: number } | null,
  to: { lat: number | null; lng: number | null },
): string | null {
  if (!here || to.lat == null || to.lng == null) return null;
  return t('field.unit.milesAway', { miles: miles(milesBetween(here, { lat: to.lat, lng: to.lng })) });
}
