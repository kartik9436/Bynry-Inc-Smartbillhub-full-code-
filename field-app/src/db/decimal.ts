/**
 * Meter figures and money travel as TEXT decimal strings, never as floats
 * (CLAUDE.md hard rule 2; Mobile data §2). This is the one check that a string
 * IS one, so a query refuses `"1e3"`, `"NaN"` or a float's `48210.499999…`
 * before it lands. Up to 6 places: money stores 4 and percentages 6.
 */
const DECIMAL_RE = /^-?\d{1,15}(\.\d{1,6})?$/;

export function isDecimalString(value: unknown): value is string {
  return typeof value === 'string' && DECIMAL_RE.test(value);
}

export function requireDecimal(value: unknown, field: string): string {
  if (!isDecimalString(value)) throw new Error(`${field} must be a decimal string, got ${JSON.stringify(value)}`);
  return value;
}

/** A decimal string, or null when the value is absent. */
export function optionalDecimal(value: unknown, field: string): string | null {
  return value === null || value === undefined || value === '' ? null : requireDecimal(value, field);
}
