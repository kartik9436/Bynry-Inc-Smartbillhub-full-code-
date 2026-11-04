/**
 * The arithmetic of a reading, done on TEXT decimals and never on floats
 * (hard rule 2; Mobile data §2): a figure is scaled to an integer of
 * millionths in a BigInt, so `52410 − 48210` is exactly `4200` and never
 * `4199.999…`.
 *
 * And the one judgment the handset makes about a figure — where it sits
 * against what was expected — kept apart from the office's verdict (R96):
 * this is a WARNING for the reader, never a status of the reading.
 */
import { isDecimalString } from '../../db/decimal';

const SCALE = 1_000_000n;
const PLACES = 6;

export function toScaled(value: string): bigint {
  if (!isDecimalString(value)) throw new Error(`not a decimal string: ${JSON.stringify(value)}`);
  const negative = value.startsWith('-');
  const [whole = '0', frac = ''] = (negative ? value.slice(1) : value).split('.');
  const scaled = BigInt(whole) * SCALE + BigInt((frac + '000000').slice(0, PLACES));
  return negative ? -scaled : scaled;
}

export function fromScaled(n: bigint): string {
  const negative = n < 0n;
  const abs = negative ? -n : n;
  const whole = abs / SCALE;
  const frac = (abs % SCALE).toString().padStart(PLACES, '0').replace(/0+$/, '');
  return `${negative ? '-' : ''}${whole.toString()}${frac ? `.${frac}` : ''}`;
}

export function subtract(a: string, b: string): string {
  return fromScaled(toScaled(a) - toScaled(b));
}

export function add(values: readonly string[]): string {
  return fromScaled(values.reduce((sum, v) => sum + toScaled(v), 0n));
}

export function compare(a: string, b: string): -1 | 0 | 1 {
  const x = toScaled(a);
  const y = toScaled(b);
  return x < y ? -1 : x > y ? 1 : 0;
}

/** `52410` → `52,410`; keeps every place the figure carries. */
export function group(value: string): string {
  const negative = value.startsWith('-');
  const [whole = '', frac] = (negative ? value.slice(1) : value).split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${negative ? '−' : ''}${grouped}${frac ? `.${frac}` : ''}`;
}

/** Where a typed figure sits. `below_previous` is its own warning, not "low" (R81). */
export type RangeVerdict = 'inside' | 'high' | 'low' | 'below_previous' | 'unknown';

export function verdict(value: string, previous: string | null, min: string | null, max: string | null): RangeVerdict {
  if (!isDecimalString(value)) return 'unknown';
  if (previous && isDecimalString(previous) && compare(value, previous) < 0) return 'below_previous';
  if (max && isDecimalString(max) && compare(value, max) > 0) return 'high';
  if (min && isDecimalString(min) && compare(value, min) < 0) return 'low';
  if (!min && !max) return 'unknown';
  return 'inside';
}

/** True when the figure must be warned about before it is kept (R80). */
export function needsWarning(v: RangeVerdict): boolean {
  return v === 'high' || v === 'low' || v === 'below_previous';
}

/** What the reading implies was used since last time — null when either is missing. */
export function used(value: string, previous: string | null): string | null {
  if (!previous || !isDecimalString(previous) || !isDecimalString(value)) return null;
  return subtract(value, previous);
}

/** Metres between two points on the ground (haversine). A distance, not money. */
export function metresBetween(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6_371_000;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** `40 m`, `1.2 km` — rounded as a walker reads it. */
export function distanceText(m: number): string {
  if (m < 1000) return `${Math.round(m / 10) * 10} m`;
  return `${(m / 1000).toFixed(1)} km`;
}

/**
 * The accuracy beyond which a fix is "poor" (R91). ⚠ NOT RULED: R90/R91 and
 * requirements 63–64 say a poor fix warns and accepts, and no document names
 * the figure. Until one does, a fix with any accuracy is stored as it came —
 * the accuracy beside the point (US-FLD-064 TC-2) — and only NO fix is
 * classified and warned. Gap reported by the reads wave; never guessed here.
 */
export const POOR_FIX_THRESHOLD_M: number | null = null;

/** The fix quality a reading records (R91: poor or none warns, never refuses). */
export function fixQuality(accuracy: number | null): 'good' | 'poor' | 'none' | null {
  if (accuracy === null) return 'none';
  if (POOR_FIX_THRESHOLD_M === null) return null;
  return accuracy <= POOR_FIX_THRESHOLD_M ? 'good' : 'poor';
}
