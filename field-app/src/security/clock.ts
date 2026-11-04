/**
 * The one clock the auth and session code reads.
 *
 * Every expiry in this folder is a comparison against `now()`, so a test can
 * walk a technician through a whole shift (07:30 sign-in, 08:30 token expiry,
 * nine hours of capture with no signal) without waiting for any of it.
 */
export interface Clock {
  /** Milliseconds since the epoch. */
  now(): number;
}

export const systemClock: Clock = { now: () => Date.now() };

/** A clock a test moves by hand. */
export class ManualClock implements Clock {
  private t: number;

  constructor(start: number) {
    this.t = start;
  }

  now(): number {
    return this.t;
  }

  advance(ms: number): void {
    this.t += ms;
  }

  set(ms: number): void {
    this.t = ms;
  }
}

export const MINUTE_MS = 60 * 1000;
export const HOUR_MS = 60 * MINUTE_MS;
export const DAY_MS = 24 * HOUR_MS;
