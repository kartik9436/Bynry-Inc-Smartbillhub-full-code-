/**
 * How the "me" screens write times, durations and distances — following the
 * technician's FF-51 choices (clock, date format, units). Pure functions, so
 * the tests can state the board's figures exactly: `5h 02m`, `20m`, `14:30`,
 * `2:30 PM`, `1.8 miles`.
 */
import type { ClockFormat, DateFormat, Units } from './prefs';

const pad = (n: number) => String(n).padStart(2, '0');

/** `302` → `5h 02m`; `20` → `20m`; `0` → `0m` (FF-47, FF-44). */
export function formatDuration(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${pad(m % 60)}m` : `${m}m`;
}

/** The clock time of an ISO instant, in the handset's zone. */
export function formatClock(iso: string, clock: ClockFormat): string {
  const d = new Date(iso);
  const h = d.getHours();
  const m = pad(d.getMinutes());
  if (clock === 'h24') return `${pad(h)}:${m}`;
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${m} ${h < 12 ? 'AM' : 'PM'}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** FF-51's three date formats: `20 Oct 2026` · `10/20/2026` · `2026-10-20`. */
export function formatDate(d: Date, format: DateFormat): string {
  const y = d.getFullYear();
  const mo = d.getMonth();
  const day = d.getDate();
  if (format === 'monthDayYear') return `${pad(mo + 1)}/${pad(day)}/${y}`;
  if (format === 'iso') return `${y}-${pad(mo + 1)}-${pad(day)}`;
  return `${pad(day)} ${MONTHS[mo] ?? ''} ${y}`;
}

const KM_PER_MILE = 1.609344;

/** A distance the server gives in miles, in the technician's units, to one place. */
export function formatDistance(miles: number, units: Units): { value: string; unit: 'miles' | 'km' } {
  return units === 'kilometres'
    ? { value: (miles * KM_PER_MILE).toFixed(1), unit: 'km' }
    : { value: miles.toFixed(1), unit: 'miles' };
}

/** Bytes as the FF-50 line shows them: `41 MB`. */
export function formatMegabytes(bytes: number): string {
  return `${Math.max(0, Math.round(bytes / 1_000_000))} MB`;
}

/** `m:ss` — the emergency's countdown (FF-43 "4:12"). */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(total / 60)}:${pad(total % 60)}`;
}
