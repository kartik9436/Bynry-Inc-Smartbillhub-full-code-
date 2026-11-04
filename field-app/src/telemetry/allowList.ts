/**
 * THE ALLOW LIST — T-74, R66, AD-19.
 *
 * Every event, breadcrumb and log record passes through this before it is written
 * to the handset's telemetry queue, and therefore before it can leave the handset.
 * It is a list of what MAY go, never of what may not: an event name that is not
 * here is dropped whole, and a field that is not listed under its event is dropped.
 * Nothing is masked — a masked value still tells someone a value existed, and a
 * mask is a block list of the patterns we happened to think of.
 *
 * Every field also carries a VALUE rule, because a field name is a promise the
 * caller can break: `screen: 'Sarah Miller'` names an allowed field and carries a
 * customer. A value that fails its rule drops that field.
 *
 * Free text has no rule here and never will: an error message, a note, a log line
 * written as a sentence. If it can hold a sentence it can hold a name.
 *
 * Adding an event is a code change reviewed like any other — that is the point.
 * Do not add a field that can carry a customer's name, address, account number,
 * balance, reading, photograph, signature or any outbox payload (R66).
 *
 * Open, and not decided here: a `work_type` field ("disconnect orders run nine
 * minutes long", Stack.txt) needs the tenant-configurable work-type codes as an
 * enumerable set; until that seam exists the field is absent rather than a
 * free-token pattern that would also admit a surname.
 */
import type { TelemetryValue } from './types';

export type ValueRule = (value: unknown) => value is TelemetryValue;

const SCREEN_ID = /^(FF|RW)-\d{2}$/;

/** An FF-nn or RW-nn screen id — the design's own ids, never a route param. */
export const screenId: ValueRule = (v): v is string =>
  typeof v === 'string' && SCREEN_ID.test(v);

/** A whole number in [min, max]. Bounded so a field cannot smuggle an id. */
export const intIn =
  (min: number, max: number): ValueRule =>
  (v): v is number =>
    typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max;

export const oneOf =
  (...allowed: readonly string[]): ValueRule =>
  (v): v is string =>
    typeof v === 'string' && allowed.includes(v);

export const bool: ValueRule = (v): v is boolean => typeof v === 'boolean';

const DAY_MS = 24 * 60 * 60 * 1000;
const durationMs = intIn(0, DAY_MS);
const outcome = oneOf('ok', 'failed', 'cancelled', 'yielded');
const network = oneOf('none', 'cellular', 'wifi', 'unknown');

/**
 * THE IDENTITY ALLOW LIST — a SEPARATE list from the event list below, on purpose.
 *
 * The technician's own identity may travel (PO 2026-10-21, "Yes, by name"); a
 * customer's never may (R66). The two are kept apart by STRUCTURE, not by
 * inspecting values — no pattern can tell "Dana Reyes" the technician from
 * "Sarah Miller" the customer:
 *   - a person's name is allowed in exactly one place, `identity.technicianName`,
 *     which is filled from the signed-in session and nowhere else;
 *   - no EVENT field anywhere below accepts a name or any free text, so a screen
 *     cannot put a customer's name into an event however it labels the field;
 *   - any other identity key (`name`, `userId`, `customerName`…) is dropped.
 */
const TECHNICIAN_ID = /^[A-Za-z0-9_-]{1,64}$/;
// A display name: printable, one line, bounded. It is not a value check for
// customer data (none is possible) — the guarantee is where it comes from.
const PERSON_NAME = /^[^\u0000-\u001f\u007f]{1,80}$/;

export const IDENTITY_ALLOW_LIST = {
  tenant: (v: unknown): v is string => typeof v === 'string' && /^[a-z0-9][a-z0-9-]{0,62}$/.test(v),
  // A server role code. Pattern, not enum: the role list is the server's.
  role: (v: unknown): v is string => typeof v === 'string' && /^[a-z][a-z_]{0,31}$/.test(v),
  deviceId: (v: unknown): v is string =>
    typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(v),
  technicianId: (v: unknown): v is string => typeof v === 'string' && TECHNICIAN_ID.test(v),
  technicianName: (v: unknown): v is string => typeof v === 'string' && PERSON_NAME.test(v.trim()),
} as const;

/** The three an identity cannot be sent without; the technician pair is optional. */
export const IDENTITY_REQUIRED = ['tenant', 'role', 'deviceId'] as const;

/** Event name → the fields it may carry → the rule each value must meet. */
export type AllowListPolicy = Readonly<Record<string, Readonly<Record<string, ValueRule>>>>;

export const ALLOW_LIST: AllowListPolicy = {
  // The four paths that actually hurt (AD-18, Stack.txt "Performance").
  app_start: { duration_ms: durationMs, cold: bool },
  day_pull: { duration_ms: durationMs, outcome, items: intIn(0, 100_000), network },
  batch_send: { duration_ms: durationMs, outcome, items: intIn(0, 100_000), network },
  photo_upload: { duration_ms: durationMs, outcome, kilobytes: intIn(0, 1_000_000), network },
  // Which screens are used and where a flow is abandoned (Stack.txt "Product analytics").
  screen_view: { screen: screenId },
  flow_abandoned: { screen: screenId, step: intIn(0, 50) },
  job_timed: { screen: screenId, duration_ms: durationMs, outcome },
  // The telemetry queue reporting on itself (R67): how much it had to throw away.
  telemetry_dropped: { events: intIn(0, 10_000_000), crashes: intIn(0, 1_000_000) },
};
