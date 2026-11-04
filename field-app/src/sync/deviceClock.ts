/**
 * The phone's clock against the server's — FB-014 (DEF-FLD-10639, PO
 * 2026-10-28, verbatim: *"job should be synced with the server accept the
 * future time"*).
 *
 * EVERY CALL carries the phone's own clock reading at the moment it is sent,
 * `X-Device-Time` (`transport.ts`). The SERVER does the correcting: it
 * measures `offset = server now − phone now` for that send and shifts every
 * time in it onto its own clock (`06-backend/core/device_clock.py`), and it
 * never refuses a send for a clock difference of any size. Nothing on the
 * phone re-stamps captured work — the times stay exactly as captured, which
 * is what lets the server keep the phone's original beside the shifted one.
 *
 * What the PHONE does with the answer is only this: every field answer
 * carries `X-Server-Time`, and the difference is kept here so FF-50 can say
 * *"Phone clock is N min fast. Fix the time."* past 5 minutes. The work still
 * goes either way. The send's own travel time is halved out (the server's
 * stamp is taken against the middle of the round trip), so a slow network does
 * not read as a wrong clock.
 *
 * Held in memory, not stored: the next answer measures it again, and a phone
 * that has not reached the server since it started has nothing to warn about.
 */

/** Past this the technician is told (PO 2026-10-28). */
export const WARN_AFTER_MS = 5 * 60 * 1000;

export const DEVICE_TIME_HEADER = 'X-Device-Time';
export const SERVER_TIME_HEADER = 'X-Server-Time';

type Listener = (offsetMs: number | null) => void;

let lastOffsetMs: number | null = null;
const listeners = new Set<Listener>();

/** server − phone, in ms, from the last answer that carried the server's time; null before one. */
export function clockOffsetMs(): number | null {
  return lastOffsetMs;
}

export function subscribeClockOffset(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function setClockOffsetMs(offsetMs: number | null): void {
  lastOffsetMs = offsetMs;
  for (const fn of listeners) fn(offsetMs);
}

/**
 * Record one answer's measurement. `sentAt` / `receivedAt` are the phone's
 * clock either side of the call; `serverTime` is the answer's `X-Server-Time`.
 * An absent or unreadable header changes nothing.
 */
export function recordServerTime(sentAt: Date, receivedAt: Date, serverTime: string | null | undefined): void {
  if (!serverTime) return;
  const server = Date.parse(serverTime);
  if (Number.isNaN(server)) return;
  const middle = (sentAt.getTime() + receivedAt.getTime()) / 2;
  setClockOffsetMs(Math.round(server - middle));
}

export interface ClockWarning {
  /** The phone is AHEAD of the server (fast) or behind it (slow). */
  direction: 'fast' | 'slow';
  /** Whole minutes, rounded. */
  minutes: number;
}

/** The warning FF-50 shows, or null within 5 minutes or before any measurement. */
export function clockWarning(offsetMs: number | null): ClockWarning | null {
  if (offsetMs === null || Math.abs(offsetMs) <= WARN_AFTER_MS) return null;
  // offset = server − phone: negative means the phone is ahead, i.e. fast.
  return { direction: offsetMs < 0 ? 'fast' : 'slow', minutes: Math.round(Math.abs(offsetMs) / 60000) };
}
