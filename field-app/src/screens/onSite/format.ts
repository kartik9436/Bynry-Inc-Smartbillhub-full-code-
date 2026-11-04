/**
 * How the on-site, closing and raise screens write money, durations and
 * times. Pure functions, no React, so each is tested as a table.
 *
 * MONEY IS NEVER A FLOAT (CLAUDE.md hard rule 2; BR-FLD-00020). Amounts
 * arrive as decimal strings ("241.3800") and are rounded HALF-UP to two
 * places by string arithmetic; a unit price keeps up to four places
 * (PO 2026-10-02). Nothing here adds, subtracts or compares two amounts
 * except `isZeroAmount`, which reads digits.
 */
import { requireDecimal } from '../../db/decimal';

/** Integer digits and the fraction, padded/rounded half-up to `places`. */
function roundDecimal(value: string, places: number): { negative: boolean; whole: string; fraction: string } {
  const d = requireDecimal(value, 'amount');
  const negative = d.startsWith('-');
  const body = negative ? d.slice(1) : d;
  const [w = '0', f = ''] = body.split('.');
  const padded = (f + '0'.repeat(places + 1)).slice(0, places + 1);
  const keep = padded.slice(0, places);
  const roundUp = Number(padded.charAt(places)) >= 5;
  let digits = (w + keep).replace(/^0+(?=\d)/, '');
  if (roundUp) {
    // Add one to the last digit of an integer held as a string.
    const chars = digits.split('');
    let i = chars.length - 1;
    while (i >= 0) {
      if (chars[i] === '9') {
        chars[i] = '0';
        i -= 1;
      } else {
        chars[i] = String(Number(chars[i]) + 1);
        break;
      }
    }
    digits = (i < 0 ? '1' : '') + chars.join('');
  }
  digits = digits.padStart(places + 1, '0');
  const whole = places === 0 ? digits : digits.slice(0, digits.length - places);
  const fraction = places === 0 ? '' : digits.slice(digits.length - places);
  return { negative, whole: whole.replace(/^0+(?=\d)/, ''), fraction };
}

function group(whole: string): string {
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

const SYMBOLS: Record<string, string> = { USD: '$', CAD: '$' };

/** "$241.38" from "241.3800". Two places, half-up, grouped. */
export function formatMoney(amount: string, currency = 'USD'): string {
  const r = roundDecimal(amount, 2);
  const symbol = SYMBOLS[currency] ?? `${currency} `;
  const zero = /^0*$/.test(r.whole + r.fraction);
  return `${r.negative && !zero ? '−' : ''}${symbol}${group(r.whole)}.${r.fraction}`;
}

/** A unit price: as many places as it carries, at least 2, at most 4. */
export function formatUnitPrice(amount: string, currency = 'USD'): string {
  const d = requireDecimal(amount, 'unit price');
  const carried = (d.split('.')[1] ?? '').replace(/0+$/, '').length;
  const places = Math.min(4, Math.max(2, carried));
  const r = roundDecimal(d, places);
  const symbol = SYMBOLS[currency] ?? `${currency} `;
  return `${r.negative ? '−' : ''}${symbol}${group(r.whole)}.${r.fraction}`;
}

/** True when the amount rounds to zero at two places — "$0.00". */
export function isZeroAmount(amount: string): boolean {
  const r = roundDecimal(amount, 2);
  return /^0*$/.test(r.whole + r.fraction);
}

/** A meter figure with grouping, unit kept by the caller: "48,180". */
export function formatFigure(value: string): string {
  const d = requireDecimal(value, 'figure');
  const [w = '0', f] = d.replace(/^-/, '').split('.');
  return `${d.startsWith('-') ? '−' : ''}${group(w)}${f ? `.${f}` : ''}`;
}

/** "1h 12m", "14m", "0m". */
export function formatMinutes(total: number): string {
  const m = Math.max(0, Math.round(total));
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return h > 0 ? `${h}h ${rest}m` : `${rest}m`;
}

/** Whole minutes between two instants, never negative. */
export function minutesBetween(from: string | Date, to: string | Date): number {
  const a = typeof from === 'string' ? Date.parse(from) : from.getTime();
  const b = typeof to === 'string' ? Date.parse(to) : to.getTime();
  return Math.max(0, Math.floor((b - a) / 60000));
}

const pad = (n: number) => String(n).padStart(2, '0');

/** "09:58", in the handset's own time zone. */
export function formatClock(at: string | Date): string {
  const d = typeof at === 'string' ? new Date(at) : at;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "20 Oct". */
export function formatDay(at: string | Date): string {
  const d = typeof at === 'string' ? new Date(at) : at;
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

/** "12 Jun 2026". */
export function formatDate(at: string | Date): string {
  const d = typeof at === 'string' ? new Date(at) : at;
  return `${pad(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** "20 Oct 09:58". */
export function formatStamp(at: string | Date): string {
  return `${formatDay(at)} ${formatClock(at)}`;
}

/** Same calendar day on the handset. */
export function sameDay(a: string | Date, b: string | Date): boolean {
  const x = typeof a === 'string' ? new Date(a) : a;
  const y = typeof b === 'string' ? new Date(b) : b;
  return x.getFullYear() === y.getFullYear() && x.getMonth() === y.getMonth() && x.getDate() === y.getDate();
}

/** "3:12" — hours and minutes left, never negative. */
export function formatCountdown(minutes: number): string {
  const m = Math.max(0, Math.floor(minutes));
  return `${Math.floor(m / 60)}:${pad(m % 60)}`;
}

/** Two initials from a display name: "D. Ortiz" → "DO". */
export function initialsOf(name: string): string {
  const parts = name.replace(/\./g, ' ').split(/\s+/).filter(Boolean);
  const first = parts[0]?.charAt(0) ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.charAt(0) ?? '') : '';
  return (first + last).toUpperCase();
}

/** "1400 Elm Street · Unit A" / "Austin, TX 78704" from a premise row. */
export function addressLines(p: {
  address_line: string | null;
  locality: string | null;
  region: string | null;
  postal_code: string | null;
} | null | undefined): { line1: string; line2: string } {
  if (!p) return { line1: '', line2: '' };
  const place = [p.locality, [p.region, p.postal_code].filter(Boolean).join(' ')].filter(Boolean).join(', ');
  return { line1: p.address_line ?? '', line2: place };
}
