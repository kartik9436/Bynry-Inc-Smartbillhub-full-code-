/**
 * AVAILABILITY REACHES THE OFFICE — the handset's half of FB-033 (decision log
 * 2026-10-31, *"FB-033: availability from the phone reaches the office (PO,
 * D1–D4)"*; DEF-FLD-10799).
 *
 * Read from the server's code (`06-backend/apps/work/availability.py`):
 *
 *   POST work/mobile/availability {key, at, value, capture_token?}   `availability.record`
 *        → {value, at, applied, not_applied_reason, status, status_since, duplicate}
 *   GET  work/mobile/availability                                    `availability.current`
 *        → {status, status_since}
 *
 * THE TAP GOES THROUGH THE OUTBOX (`doors.ts`, kind `availability`): captured
 * at the press with a key minted on the handset and the TAP's time, sent when
 * there is signal, answered `duplicate` on a resend. So a choice made with no
 * signal counts from when it was pressed, never from when it arrived — and the
 * server keeps it out of the status when the office said something newer.
 *
 * THE OFFICE'S ANSWER IS READ BACK AFTER EACH SYNC (`readBack`, called by
 * `FieldRuntime`): an office *Unavailable* shows on the phone, a late tap the
 * server kept out is replaced by what it holds, and after End shift the chip
 * reads *Off duty*. A tap still waiting in the outbox is NOT overwritten — the
 * office has not heard it yet.
 */
import type { Availability } from '../navigation/ShellStatus';
import type { DoorExtra } from './fieldApi';

/** The three words the phone may say, as the server spells them. */
export type WireAvailability = 'available' | 'on_break' | 'off_duty';

export const WIRE_OF: Record<'available' | 'onBreak' | 'offDuty', WireAvailability> = {
  available: 'available',
  onBreak: 'on_break',
  offDuty: 'off_duty',
};

export interface WireAvailabilityStatus {
  status: string;
  status_since: string | null;
}

export interface AvailabilityApi {
  sendAvailability(body: { at: string; value: WireAvailability }, extra?: DoorExtra): Promise<unknown>;
  myAvailability(): Promise<WireAvailabilityStatus>;
}

export function asAvailabilityApi(x: unknown): AvailabilityApi | null {
  return x && typeof (x as AvailabilityApi).sendAvailability === 'function' && typeof (x as AvailabilityApi).myAvailability === 'function'
    ? (x as AvailabilityApi)
    : null;
}

/**
 * The server's `technicians.status` as the chip's word. `off_today` (End
 * shift) reads *Off duty*: the technician is off for the rest of the day
 * (D4 = B — the two stay separate records on the server). A word this build
 * does not know is null: the phone keeps what it had rather than guess.
 */
export function chipOf(status: string): Availability | null {
  switch (status) {
    case 'on_shift':
      return 'available';
    case 'on_break':
      return 'onBreak';
    case 'off_duty':
    case 'off_today':
      return 'offDuty';
    case 'unavailable':
      return 'unavailable';
    default:
      return null;
  }
}

/**
 * Read the status the office holds and hand it to `apply` (the screen store's
 * `applyOfficeStatus`) — unless `waiting` says a tap of this technician's is
 * still in the outbox. A failure keeps what the phone had; the caller never
 * lets it fail the sync.
 */
export async function readBack(
  api: AvailabilityApi,
  waiting: () => boolean,
  apply: (value: Availability, since: string | null) => void,
): Promise<Availability | null> {
  const wire = await api.myAvailability();
  if (waiting()) return null;
  const value = chipOf(wire.status);
  if (!value) return null;
  apply(value, wire.status_since);
  return value;
}
