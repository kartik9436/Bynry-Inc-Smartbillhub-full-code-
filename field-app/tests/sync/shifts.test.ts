/**
 * @jest-environment node
 *
 * CR-193-BRC10 (MQ-040 step 1) — End shift and Submit the day go through
 * their own doors from the outbox, under the CAPTOR's token, with the item's
 * key, sent when there is signal; and the week the day's sync downloads is
 * kept, so FF-46 reads it with no signal.
 */
import * as outboxQ from '../../src/db/queries/outbox';
import { scoped } from '../../src/db/scoped';
import { createShiftsPort, createTimesheetPort, weekFromWire } from '../../src/screens/me/shiftsPorts';
import { notWiredServices } from '../../src/screens/me/services';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { doorCallFor, DOOR_KINDS } from '../../src/sync/doors';
import type { DoorExtra } from '../../src/sync/fieldApi';
import { sendPending } from '../../src/sync/outbox';
import { cachedWeek, downloadWeek, type ShiftsApi, type WireWeek } from '../../src/sync/shifts';
import { TransportError } from '../../src/sync/transport';
import { FakeClock, idSource, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const tokens = { tokenFor: (t: string) => `token-of-${t}` };

/** The PO's worked example: Mon–Thu 07:00–15:30, Fri 30 Oct a utility holiday. */
function ortizWeek(): WireWeek {
  const shift = (date: string, weekday: string) => ({ date, weekday, kind: 'shift' as const, start: '07:00', end: '15:30', holiday: null, note: null, exception: null });
  return {
    from: '2026-10-26',
    to: '2026-11-01',
    today: '2026-10-28',
    days: [
      shift('2026-10-26', 'mon'),
      shift('2026-10-27', 'tue'),
      shift('2026-10-28', 'wed'),
      shift('2026-10-29', 'thu'),
      { date: '2026-10-30', weekday: 'fri', kind: 'holiday', start: null, end: null, holiday: 'Founders Day', note: null, exception: null },
      { date: '2026-10-31', weekday: 'sat', kind: 'off', start: null, end: null, holiday: null, note: null, exception: null },
      { date: '2026-11-01', weekday: 'sun', kind: 'off', start: null, end: null, holiday: null, note: null, exception: null },
    ],
    current: { start: '07:00', end: '15:30', started_at: '2026-10-28T07:00:00', minutes_so_far: 130 },
    ended_at: null,
  };
}

class ShiftServer extends FakeServer implements ShiftsApi {
  readonly calls: { door: string; body: unknown; extra: DoorExtra | undefined }[] = [];
  failNext: TransportError | null = null;
  private readonly seen = new Set<string>();
  myWeek(): Promise<WireWeek> {
    return Promise.resolve(ortizWeek());
  }
  private answer(door: string, body: unknown, extra?: DoorExtra) {
    this.calls.push({ door, body, extra });
    if (this.failNext) {
      const e = this.failNext;
      this.failNext = null;
      return Promise.reject(e);
    }
    const duplicate = this.seen.has(`${door}:${extra?.key}`);
    this.seen.add(`${door}:${extra?.key}`);
    return Promise.resolve({ duplicate });
  }
  endShift(body: { at: string }, extra?: DoorExtra) {
    return this.answer('shift_end', body, extra);
  }
  submitTimesheet(body: { date: string }, extra?: DoorExtra) {
    return this.answer('timesheet_submit', body, extra);
  }
  // `asFieldApi` needs these two to see a field API at all.
  jobBundle(): never {
    throw new Error('not asked');
  }
  raiseOrder(): never {
    throw new Error('not asked');
  }
}

function setup() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const prefs = new MemoryKeyValueStore();
  const deps = { db, prefs, newId: idSource('k'), now: () => new Date('2026-10-28T09:10:00') };
  return { clock, db, prefs, deps, server: new ShiftServer(), opts: { clock, tokens, random: steadyRandom } };
}

test('both acts are own-door kinds with a door of their own — no job needed', () => {
  expect(DOOR_KINDS).toEqual(expect.arrayContaining(['shift_end', 'timesheet_submit']));
  const meta = { key: 'k', capturedAt: '', location: null };
  expect(doorCallFor('shift_end', { at: '2026-10-28T15:31:00.000Z' }, null, meta)).toEqual({ door: 'shift_end', at: '2026-10-28T15:31:00.000Z' });
  expect(doorCallFor('timesheet_submit', { date: '2026-10-28' }, null, meta)).toEqual({ door: 'timesheet_submit', date: '2026-10-28' });
  expect(doorCallFor('timesheet_submit', { date: 'today' }, null, meta)).toBeNull();
});

test('End shift is captured at the press, then sent under the captor’s token with its key', async () => {
  const env = setup();
  const port = createShiftsPort(env.deps, notWiredServices().shifts);
  await port.endShift(dana, new Date('2026-10-28T15:31:00'));
  const queued = outboxQ.listMine(scoped(env.db, 'dana'), { limit: 10 });
  expect(queued.map((r) => [r.kind, r.channel, r.work_order_id])).toEqual([['shift_end', 'job', null]]);
  await sendPending(env.db, env.server, env.opts);
  expect(env.server.calls).toEqual([
    { door: 'shift_end', body: { at: new Date('2026-10-28T15:31:00').toISOString() }, extra: { key: queued[0]!.id, captureToken: 'token-of-dana' } },
  ]);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), queued[0]!.id)?.state).toBe('accepted');
});

test('with no signal Submit the day waits, then goes once; a resend answers duplicate', async () => {
  const env = setup();
  const port = createTimesheetPort(env.deps);
  await port.submitDay(dana, new Date('2026-10-28T16:00:00'));
  expect(port.submitted?.('dana', new Date('2026-10-28T18:00:00'))).toBe(true);
  expect(port.submitted?.('dana', new Date('2026-10-27T18:00:00'))).toBe(false);
  env.server.failNext = new TransportError('network', 'no signal');
  await sendPending(env.db, env.server, env.opts);
  const [row] = outboxQ.listMine(scoped(env.db, 'dana'), { limit: 10 });
  expect(row?.state).toBe('pending');
  env.clock.advance(60 * 60_000);
  await sendPending(env.db, env.server, env.opts);
  expect(env.server.calls.map((c) => c.body)).toEqual([{ date: '2026-10-28' }, { date: '2026-10-28' }]);
  expect(new Set(env.server.calls.map((c) => c.extra?.key))).toEqual(new Set([row!.id]));
  expect(outboxQ.getMine(scoped(env.db, 'dana'), row!.id)?.state).toBe('accepted');
});

test('the week the sync downloaded is kept and read with no signal: Mon–Thu 07:00–15:30, Fri Founders Day', async () => {
  const env = setup();
  await downloadWeek(env.server, env.prefs, 'dana', new Date('2026-10-28T06:00:00'));
  expect(cachedWeek(env.prefs, 'dana')?.days).toHaveLength(7);
  const week = await createShiftsPort(env.deps, notWiredServices().shifts).week('dana', env.deps.now());
  expect(week?.days.map((d) => [d.kind, d.start, d.name])).toEqual([
    ['shift', '2026-10-26T07:00:00', null],
    ['shift', '2026-10-27T07:00:00', null],
    ['shift', '2026-10-28T07:00:00', null],
    ['shift', '2026-10-29T07:00:00', null],
    ['holiday', null, 'Founders Day'],
    ['off', null, null],
    ['off', null, null],
  ]);
  expect(week?.current?.startedAt).toBe('2026-10-28T07:00:00');
});

test('after End shift on this handset, today has no shift in progress — before the server has heard', () => {
  const wire = ortizWeek();
  expect(weekFromWire(wire, null, new Date('2026-10-28T12:00:00')).current).not.toBeNull();
  expect(weekFromWire(wire, { day: '2026-10-28' }, new Date('2026-10-28T15:40:00')).current).toBeNull();
  // A week kept yesterday says nothing about today's shift.
  expect(weekFromWire({ ...wire, today: '2026-10-27' }, null, new Date('2026-10-28T12:00:00')).current).toBeNull();
});
