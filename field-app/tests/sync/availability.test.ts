/**
 * @jest-environment node
 *
 * FB-033 (DEF-FLD-10799) — FF-45's choice reaches the office: captured in the
 * outbox at the tap with the TAP's time, sent once when there is signal under
 * the captor's token and the item's key, and the office's word read back
 * after the sync (an office *Unavailable* shows on the phone; a tap still on
 * its way is never overwritten).
 */
import * as outboxQ from '../../src/db/queries/outbox';
import { scoped } from '../../src/db/scoped';
import { applyOfficeStatus, readAvailability, writeAvailability } from '../../src/screens/me/availability';
import { createAvailabilityPort } from '../../src/screens/me/availabilityPort';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { type AvailabilityApi, chipOf, readBack, type WireAvailability, type WireAvailabilityStatus } from '../../src/sync/availability';
import { doorCallFor, DOOR_KINDS } from '../../src/sync/doors';
import type { DoorExtra } from '../../src/sync/fieldApi';
import { sendPending } from '../../src/sync/outbox';
import { TransportError } from '../../src/sync/transport';
import { FakeClock, idSource, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const tokens = { tokenFor: (t: string) => `token-of-${t}` };

class AvailabilityServer extends FakeServer implements AvailabilityApi {
  readonly calls: { body: unknown; extra: DoorExtra | undefined }[] = [];
  failNext: TransportError | null = null;
  office: WireAvailabilityStatus = { status: 'on_shift', status_since: null };
  private readonly seen = new Set<string>();
  sendAvailability(body: { at: string; value: WireAvailability }, extra?: DoorExtra) {
    this.calls.push({ body, extra });
    if (this.failNext) {
      const e = this.failNext;
      this.failNext = null;
      return Promise.reject(e);
    }
    const duplicate = this.seen.has(String(extra?.key));
    this.seen.add(String(extra?.key));
    return Promise.resolve({ duplicate, applied: true });
  }
  myAvailability() {
    return Promise.resolve(this.office);
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
  const deps = { db, newId: idSource('k'), now: () => new Date('2026-10-28T11:20:00') };
  return { clock, db, prefs, deps, server: new AvailabilityServer(), opts: { clock, tokens, random: steadyRandom } };
}

test('availability is an own-door kind with no job; a value the server does not know has no door', () => {
  expect(DOOR_KINDS).toEqual(expect.arrayContaining(['availability']));
  const meta = { key: 'k', capturedAt: '', location: null };
  expect(doorCallFor('availability', { at: '2026-10-28T10:42:00.000Z', value: 'on_break' }, null, meta)).toEqual({
    door: 'availability',
    at: '2026-10-28T10:42:00.000Z',
    value: 'on_break',
  });
  expect(doorCallFor('availability', { at: '2026-10-28T10:42:00.000Z', value: 'sleeping' }, null, meta)).toBeNull();
});

test('a tap with no signal waits, then goes ONCE with the tap time — not the send time', async () => {
  const env = setup();
  const tapped = new Date('2026-10-28T10:42:00');
  await createAvailabilityPort(env.deps).send(dana, 'onBreak', tapped);
  const [row] = outboxQ.listMine(scoped(env.db, 'dana'), { limit: 10 });
  expect([row?.kind, row?.channel, row?.work_order_id]).toEqual(['availability', 'job', null]);
  env.server.failNext = new TransportError('network', 'no signal');
  await sendPending(env.db, env.server, env.opts);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), row!.id)?.state).toBe('pending');
  expect(outboxQ.countOnTheirWayMine(scoped(env.db, 'dana'), 'availability')).toBe(1);
  env.clock.advance(60 * 60_000);
  await sendPending(env.db, env.server, env.opts);
  await sendPending(env.db, env.server, env.opts);
  const accepted = env.server.calls.filter((c, i) => i > 0);
  expect(accepted).toEqual([{ body: { at: tapped.toISOString(), value: 'on_break' }, extra: { key: row!.id, captureToken: 'token-of-dana' } }]);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), row!.id)?.state).toBe('accepted');
  expect(outboxQ.countOnTheirWayMine(scoped(env.db, 'dana'), 'availability')).toBe(0);
});

test('read-back: the office set Dana Unavailable — the phone shows it', async () => {
  const env = setup();
  writeAvailability(env.prefs, 'dana', 'available', new Date('2026-10-28T07:40:00'));
  env.server.office = { status: 'unavailable', status_since: '2026-10-28T11:00:00-05:00' };
  const apply = (v: Parameters<typeof applyOfficeStatus>[2], since: string | null) => applyOfficeStatus(env.prefs, 'dana', v, since);
  const shown = await readBack(env.server, () => false, apply);
  expect(shown).toBe('unavailable');
  expect(readAvailability(env.prefs, 'dana')).toEqual({ value: 'unavailable', since: '2026-10-28T11:00:00-05:00' });
});

test('read-back never overwrites a tap that has not reached the office yet', async () => {
  const env = setup();
  writeAvailability(env.prefs, 'dana', 'offDuty', new Date('2026-10-28T15:30:00'));
  env.server.office = { status: 'on_shift', status_since: null };
  const apply = (v: Parameters<typeof applyOfficeStatus>[2], since: string | null) => applyOfficeStatus(env.prefs, 'dana', v, since);
  expect(await readBack(env.server, () => true, apply)).toBeNull();
  expect(readAvailability(env.prefs, 'dana').value).toBe('offDuty');
});

test('after End shift the chip reads Off duty; on shift reads Available; a word this build does not know changes nothing', () => {
  expect(chipOf('off_today')).toBe('offDuty');
  expect(chipOf('off_duty')).toBe('offDuty');
  expect(chipOf('on_break')).toBe('onBreak');
  expect(chipOf('on_shift')).toBe('available');
  expect(chipOf('vacation')).toBeNull();
});
