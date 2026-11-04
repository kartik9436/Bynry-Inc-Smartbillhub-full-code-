/**
 * CERTIFICATE PINS — what the phone trusts, where the set comes from, and when
 * it may change (`OQ-FLD-12797`, PO 2026-10-24; `18-field-app/12-security.md`
 * §4 *Transport* and §7.2).
 *
 * PO, verbatim: *"Trust the certificate issuer's key plus one backup issuer,
 * replaced through an app update at least 60 days before either expires.
 * plese dont hardcode it use settings - security values set in staff
 * portal"*.
 *
 * So the set is NOT in this code:
 *
 *  1. **The build carries a STARTING set in its config** — `extra.pins`, from
 *     `app.json` or the build's `FIELD_APP_PINS` environment value
 *     (`app.config.ts`). That is what a fresh install trusts on its very first
 *     connection, before it has ever heard from the server.
 *  2. **From then on the server's list replaces it** — the office keeps it on
 *     Settings › Security; the phone downloads it with its settings
 *     (`GET work/mobile/settings`) and keeps it (`PinStore`).
 *
 * ⚠ **A PIN LIST CAN ONLY BE TRUSTED IF IT ARRIVED OVER A CONNECTION THAT WAS
 * ALREADY PINNED** — otherwise whoever sits in the middle of an unpinned
 * connection hands the phone their own key and is trusted from then on. So
 * `decideAdoption` refuses a list that did not arrive pinned, and refuses one
 * that would leave the phone with fewer than two unexpired keys, or with no
 * key in common with the set it is using now (the key that just answered is in
 * that set; a list without it is a list the phone could never reach the server
 * with again). Refused means the LAST GOOD SET is kept, unchanged.
 */

/** One trusted key: base64 SHA-256 of a SubjectPublicKeyInfo, a name, and its last valid day. */
export interface Pin {
  spki_sha256: string;
  label: string;
  /** `YYYY-MM-DD`, UTC — the day the authority's certificate stops being valid. */
  not_after: string;
}

/** The design's *"two pins"* — and iOS will not pin a host on fewer than two. */
export const MIN_PINS = 2;

const BASE64_32 = /^[A-Za-z0-9+/]{43}=$/;
const CALENDAR_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function isPin(value: unknown): value is Pin {
  const p = value as Partial<Pin> | null;
  return (
    !!p &&
    typeof p.spki_sha256 === 'string' &&
    BASE64_32.test(p.spki_sha256) &&
    typeof p.label === 'string' &&
    typeof p.not_after === 'string' &&
    CALENDAR_DATE.test(p.not_after)
  );
}

/** Today in UTC as `YYYY-MM-DD` — the same calendar a certificate's `notAfter` is in. */
export function utcDay(now: Date): string {
  return now.toISOString().slice(0, 10);
}

/** The pins whose last valid day has not passed. ISO dates compare as strings. */
export function usablePins(pins: readonly Pin[], today: string): Pin[] {
  return pins.filter((p) => p.not_after >= today);
}

/** A list of pins, or null when ANY entry is malformed — a half-good list is not trusted. */
export function parsePins(value: unknown): Pin[] | null {
  if (!Array.isArray(value) || !value.every(isPin)) return null;
  return value.map((p: Pin) => ({ spki_sha256: p.spki_sha256, label: p.label, not_after: p.not_after }));
}

/**
 * The build's starting set, from its config (`extra.pins`). An empty array
 * when the config carries none or carries a malformed one — the pinning layer
 * then reports that it is NOT enforcing rather than pinning to nothing.
 */
export function bootstrapPins(extra: unknown): Pin[] {
  const pins = parsePins((extra as { pins?: unknown } | null | undefined)?.pins);
  return pins ?? [];
}

/**
 * Whether this build pins at all — `extra.pinning`, written by `app.config.ts`
 * from the build's `FIELD_APP_PINNING` (`CR-195-BRC10`; decision log
 * 2026-10-28, PO: *"start A1"* — pinning is DORMANT, not a go-live
 * requirement; both the beta and the store build say `off`).
 *
 * ⚠ Only the exact word `on` turns it on. A config with no `pinning`, or
 * anything else in it, does not pin and relies on the operating system's
 * standard certificate check. Until 2026-10-28 this read the other way
 * round (only `off` turned it off — `DEF-FLD-10617`).
 */
export type PinningMode = 'on' | 'off';

export function pinningMode(extra: unknown): PinningMode {
  return (extra as { pinning?: unknown } | null | undefined)?.pinning === 'on' ? 'on' : 'off';
}

/** `pinning_off`: this build does not pin (dormant, CR-195-BRC10), so no list is ever adopted. */
export type RefusalReason = 'not_pinned' | 'malformed' | 'too_few' | 'no_common_key' | 'unchanged' | 'pinning_off';

export type Adoption = { adopt: true; pins: Pin[] } | { adopt: false; reason: RefusalReason };

function sameSet(a: readonly Pin[], b: readonly Pin[]): boolean {
  const key = (ps: readonly Pin[]) =>
    ps
      .map((p) => `${p.spki_sha256}|${p.not_after}|${p.label}`)
      .sort()
      .join(',');
  return key(a) === key(b);
}

/**
 * May the phone replace `current` with `incoming`? Pure — the caller says
 * whether the answer arrived over a pinned connection and what day it is.
 */
export function decideAdoption(input: {
  current: readonly Pin[];
  incoming: unknown;
  arrivedPinned: boolean;
  today: string;
}): Adoption {
  if (!input.arrivedPinned) return { adopt: false, reason: 'not_pinned' };
  const incoming = parsePins(input.incoming);
  if (incoming === null) return { adopt: false, reason: 'malformed' };
  const usable = usablePins(incoming, input.today);
  if (usable.length < MIN_PINS) return { adopt: false, reason: 'too_few' };
  const now = new Set(usablePins(input.current, input.today).map((p) => p.spki_sha256));
  if (now.size > 0 && !usable.some((p) => now.has(p.spki_sha256))) {
    return { adopt: false, reason: 'no_common_key' };
  }
  if (sameSet(usable, input.current)) return { adopt: false, reason: 'unchanged' };
  return { adopt: true, pins: usable };
}
