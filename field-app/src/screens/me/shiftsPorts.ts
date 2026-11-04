/**
 * FF-46's week and End shift, FF-47's Submit the day — WIRED (`CR-193-BRC10`,
 * MQ-040 step 1, decision log 2026-10-26). Replaces the `ME-shifts` and
 * `ME-timesheet-submit` holds for everything step 1 approved.
 *
 * ⚠ **REQUEST TIME OFF IS NOT HERE ON PURPOSE.** Step 2 (time-off requests,
 * office approval, notifications) is not approved, so `requestTimeOff` stays
 * the not-wired port it was: it says it was not sent.
 *
 * The week is read from what the day's sync kept (`sync/shifts.ts`), so it
 * opens with no signal. *End shift* and *Submit the day* are CAPTURED through
 * the outbox at the press — their key minted here — and go when there is
 * signal; what the handset captured is what the screen shows at once.
 */
import type { TenantDb } from '../../db/database';
import type { KeyValueStore } from '../../security/prefs';
import { capture } from '../../sync/outbox';
import {
  cachedWeek,
  endedLocally,
  localDay,
  markEnded,
  markSubmitted,
  submittedLocally,
  type WireWeek,
} from '../../sync/shifts';
import type { Captor, ShiftDay, ShiftsPort, ShiftWeek, TimesheetPort } from './services';

export interface ShiftsDeps {
  db: TenantDb;
  prefs: KeyValueStore;
  newId(): string;
  now(): Date;
  /** Send now, quietly, when there may be signal; a failure leaves the item queued. */
  sendNow?: () => Promise<void>;
}

/** `2026-10-26` + `07:00` → a wall-clock instant on the handset's own clock. */
const wall = (date: string, hhmm: string) => `${date}T${hhmm}:00`;

export function weekFromWire(wire: WireWeek, ended: { day: string } | null, now: Date): ShiftWeek {
  const days: ShiftDay[] = wire.days.map((d) => ({
    date: `${d.date}T00:00:00`,
    kind: d.kind,
    start: d.kind === 'shift' && d.start ? wall(d.date, d.start) : null,
    end: d.kind === 'shift' && d.end ? wall(d.date, d.end) : null,
    name: d.kind === 'holiday' ? d.holiday : null,
    note: d.note,
  }));
  const today = localDay(now);
  const endedToday = wire.ended_at !== null && wire.today === today ? true : ended?.day === today;
  let current: ShiftWeek['current'] = null;
  if (!endedToday && wire.today === today) {
    if (wire.current) {
      current = { start: wall(today, wire.current.start), end: wall(today, wire.current.end), startedAt: wire.current.started_at };
    } else {
      // Kept BEFORE the window opened: the server had nothing to say yet, so
      // the shift starts at the window's start, on this handset's clock.
      const row = wire.days.find((d) => d.date === today);
      const start = row?.kind === 'shift' && row.start && row.end ? new Date(wall(today, row.start)) : null;
      const keptAt = wire.downloaded_at ? Date.parse(wire.downloaded_at) : NaN;
      if (row && start && keptAt < start.getTime() && now.getTime() >= start.getTime()) {
        current = { start: wall(today, row.start!), end: wall(today, row.end!), startedAt: start.toISOString() };
      }
    }
  }
  return { current, days };
}

export function createShiftsPort(deps: ShiftsDeps, base: ShiftsPort): ShiftsPort {
  return {
    async week(technicianId) {
      const wire = cachedWeek(deps.prefs, technicianId);
      return wire ? weekFromWire(wire, endedLocally(deps.prefs, technicianId), deps.now()) : null;
    },
    // Step 2 is not approved — the not-wired port, unchanged.
    requestTimeOff: base.requestTimeOff,
    async endShift(captor: Captor, at: Date) {
      capture(deps.db, captor, { kind: 'shift_end', payload: { at: at.toISOString() } }, { newId: deps.newId, clock: { now: deps.now } });
      markEnded(deps.prefs, captor.technicianId, at);
      void deps.sendNow?.().catch(() => undefined);
    },
  };
}

export function createTimesheetPort(deps: ShiftsDeps): TimesheetPort {
  return {
    async submitDay(captor: Captor, day: Date) {
      const date = localDay(day);
      capture(deps.db, captor, { kind: 'timesheet_submit', payload: { date } }, { newId: deps.newId, clock: { now: deps.now } });
      markSubmitted(deps.prefs, captor.technicianId, date);
      void deps.sendNow?.().catch(() => undefined);
    },
    submitted(technicianId: string, day: Date) {
      return submittedLocally(deps.prefs, technicianId).includes(localDay(day));
    },
  };
}
