/**
 * The reading rule, as a pure function so it is tested without a screen.
 *
 * R11 (PO ruled): *"A reading outside its range is flagged, never refused. The
 * technician types it a second time; the same value twice is accepted and
 * marked for the office. A different second value was a typo and no flag is
 * raised. Out of range never blocks completion."* R12: every quantity carries
 * its unit — the unit is not an input here, it is the reading's own.
 *
 * Figures stay DECIMAL STRINGS (hard rule 2's reasoning for a meter figure):
 * compared digit by digit, never through a float, so `48210.50` and
 * `48210.5` are the same reading and `0.1 + 0.2` never enters it.
 */
import { isDecimalString } from '../../db/decimal';

/** What the technician typed, as a decimal string — grouping commas and spaces dropped; `null` if it is not a number. */
export function parseTyped(text: string): string | null {
  const t = text.replace(/[,\s]/g, '');
  if (t === '') return null;
  const normal = t.startsWith('.') ? `0${t}` : t.endsWith('.') ? t.slice(0, -1) : t;
  return isDecimalString(normal) ? normal : null;
}

function split(d: string): { neg: boolean; int: string; frac: string } {
  const neg = d.startsWith('-');
  const body = neg ? d.slice(1) : d;
  const [i = '0', f = ''] = body.split('.');
  return { neg, int: i.replace(/^0+(?=\d)/, ''), frac: f.replace(/0+$/, '') };
}

/** -1, 0, 1 — exact, on the strings. */
export function compareDecimal(a: string, b: string): number {
  const x = split(a);
  const y = split(b);
  const zero = (p: { int: string; frac: string }) => p.int === '0' && p.frac === '';
  const xNeg = x.neg && !zero(x);
  const yNeg = y.neg && !zero(y);
  if (xNeg !== yNeg) return xNeg ? -1 : 1;
  const sign = xNeg ? -1 : 1;
  if (x.int.length !== y.int.length) return (x.int.length < y.int.length ? -1 : 1) * sign;
  if (x.int !== y.int) return (x.int < y.int ? -1 : 1) * sign;
  const len = Math.max(x.frac.length, y.frac.length);
  const xf = x.frac.padEnd(len, '0');
  const yf = y.frac.padEnd(len, '0');
  if (xf === yf) return 0;
  return (xf < yf ? -1 : 1) * sign;
}

export function inRange(value: string, min: string | null, max: string | null): boolean {
  if (min !== null && compareDecimal(value, min) < 0) return false;
  if (max !== null && compareDecimal(value, max) > 0) return false;
  return true;
}

/** What the screen does with a figure the technician has just committed. */
export type ReadingVerdict =
  /** In range (or no range): save it, not flagged. */
  | { kind: 'save'; value: string; flagged: false }
  /** Out of range, first time: ask for it again. Nothing is saved yet. */
  | { kind: 'again'; value: string }
  /** Out of range and the same figure twice: save it, marked for the office. */
  | { kind: 'save'; value: string; flagged: true };

/**
 * `pending` is the out-of-range figure the technician was asked to type again,
 * if any. A second figure that differs is the first one's typo: it is judged
 * on its own, and no flag is raised for the first (R11, US-FLD-009 TC-3).
 */
export function judgeReading(
  value: string,
  range: { min: string | null; max: string | null },
  pending: string | null,
): ReadingVerdict {
  if (inRange(value, range.min, range.max)) return { kind: 'save', value, flagged: false };
  if (pending !== null && compareDecimal(pending, value) === 0) return { kind: 'save', value, flagged: true };
  return { kind: 'again', value };
}
