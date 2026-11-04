/**
 * Telemetry types — T-73..T-76 (CR-187-BRC10, Phase 1b), rules R66–R72.
 *
 * Two shapes exist for every record and they are deliberately different types:
 * a RAW one, which is whatever the calling code hands us and may hold anything,
 * and a SCRUBBED one, which is the only shape a transport, the disk queue or a
 * crash file will accept. The type system therefore makes "send it without
 * scrubbing" a compile error rather than a code-review comment.
 */

/** A primitive the scrubber may let through — never an object or an array. */
export type TelemetryValue = string | number | boolean;

/** What calling code hands to `track()` or `breadcrumb()`. Untrusted. */
export interface RawEvent {
  name: string;
  fields?: Record<string, unknown>;
}

declare const scrubbedBrand: unique symbol;

/** An event that has passed the allow list. Only `scrubEvent` makes one. */
export interface ScrubbedEvent {
  readonly [scrubbedBrand]: true;
  readonly name: string;
  readonly fields: Readonly<Record<string, TelemetryValue>>;
  /** Epoch milliseconds, from the injected clock. */
  readonly at: number;
}

/**
 * Who sent it — and the whole of who sent it. Tenant, role, an anonymous device
 * id, and the TECHNICIAN's own id and name.
 *
 * The technician fields exist because the PO ruled on 2026-10-21 that usage data
 * MAY name the individual technician (decision log, "Field app: crash reporter,
 * technician identity…", answer 2, option "B. Yes, by name"), which supersedes
 * R69 / AD-19's "tenant, role and an anonymous device id". They are the person
 * HOLDING the handset, filled from the signed-in session — never a customer.
 * A customer's name has no field here and no field in any event (`allowList.ts`).
 */
export interface TelemetryIdentity {
  tenant: string;
  role: string;
  deviceId: string;
  /** The signed-in technician's user id, from the session. */
  technicianId?: string;
  /** The signed-in technician's display name, from the session. */
  technicianName?: string;
}

/** One stack frame, reduced to code coordinates. */
export interface CrashFrame {
  fn: string;
  file: string;
  line: number;
  col: number;
}

/** What a crash site hands us. Untrusted: the message alone can hold a name. */
export interface RawCrash {
  error: unknown;
  fatal: boolean;
  /** The FF/RW screen id the crash happened on, when known. */
  screen?: string;
  /** React's component stack from an error boundary, when there is one. */
  componentStack?: string;
}

declare const crashBrand: unique symbol;

/** A crash report that has passed the scrubber. Only `scrubCrash` makes one. */
export interface ScrubbedCrashReport {
  readonly [crashBrand]: true;
  readonly kind: 'crash';
  /** `TypeError`, `RangeError`… — the class name, never the message. */
  readonly errorType: string;
  readonly fatal: boolean;
  readonly screen: string | null;
  readonly frames: readonly CrashFrame[];
  readonly components: readonly string[];
  readonly breadcrumbs: readonly ScrubbedEvent[];
  readonly identity: TelemetryIdentity | null;
  readonly at: number;
}

/** Synchronous key-value storage. Synchronous on purpose: a crash handler gets no await. */
export interface KeyValueStore {
  getString(key: string): string | undefined;
  set(key: string, value: string): void;
  delete(key: string): void;
}

export type Clock = () => number;
