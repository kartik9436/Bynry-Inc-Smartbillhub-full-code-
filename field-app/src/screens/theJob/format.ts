/**
 * How the job screens write a time, a duration and a figure. The handset's
 * own clock and locale; never money (R16 — this app reads money and these
 * screens show none).
 */

const pad = (n: number) => String(n).padStart(2, '0');

/** `08:46` — the phone's local time. */
export function hhmm(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Whole minutes between two instants (never negative). */
export function minutesBetween(fromIso: string, toIso: string): number {
  return Math.max(0, Math.floor((Date.parse(toIso) - Date.parse(fromIso)) / 60000));
}

/** `14m`, `1h 12m`, `2h` — the boards' short form. The unit letters come from the catalogue. */
export function shortDuration(minutes: number, units: { h: string; m: string }): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}${units.m}`;
  if (m === 0) return `${h}${units.h}`;
  return `${h}${units.h} ${m}${units.m}`;
}

/** `48,180` from `48180`, `1,204.5` from `1204.5` — grouping on the STRING, never a float. */
export function groupDigits(decimal: string | null | undefined): string {
  if (decimal === null || decimal === undefined || decimal === '') return '';
  const neg = decimal.startsWith('-');
  const body = neg ? decimal.slice(1) : decimal;
  const [int = '', frac] = body.split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${neg ? '-' : ''}${grouped}${frac !== undefined ? `.${frac}` : ''}`;
}

/** `20 Oct 2026` from the phone's clock — the stamp's date. Month words from the catalogue. */
export function dayMonthYear(iso: string, months: readonly string[]): string {
  const d = new Date(iso);
  return `${d.getDate()} ${months[d.getMonth()] ?? ''} ${d.getFullYear()}`;
}

/** `30.2651, -97.7494` — four places, as the stamp draws it. */
export function position(lat: number | null, lng: number | null): string | null {
  if (lat === null || lng === null) return null;
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

/** Initials for an avatar: `DO` from `Dana Ortiz` or `D. Ortiz`. */
export function initials(name: string): string {
  const parts = name.replace(/\./g, ' ').split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

/** `1.2 MB`, `280 KB` — what a file weighs, binary units as the compressor counts them. */
export function fileSize(bytes: number, units: { kb: string; mb: string }): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} ${units.mb}`;
  return `${Math.max(1, Math.round(bytes / 1024))} ${units.kb}`;
}
