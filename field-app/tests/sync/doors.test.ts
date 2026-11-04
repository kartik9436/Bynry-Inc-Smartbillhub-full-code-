/**
 * @jest-environment node
 *
 * Lane S-GAPS — the own-door items (`sync/doors.ts`) now travel like a sync
 * item: under their CAPTOR's capture token whoever is signed in, with the
 * item's key on the acts and hand-back doors so a resend answers `duplicate`.
 * A crew member leaving (FF-29's ×) and a correction typed as minutes for
 * another person have doors; admin time and route findings still wait.
 *
 * Each case below was run against the code before this lane and failed there
 * (the lane report quotes the failures): the items waited for their captor to
 * be the one signed in, the act and hand-back carried no key, and a leave and
 * a minutes-correction sat on the `unrouted` channel.
 */
import * as outboxQ from '../../src/db/queries/outbox';
import { scoped } from '../../src/db/scoped';
import { correctTime, removeTechnician } from '../../src/screens/onSite/crewActions';
import type { Wave } from '../../src/screens/onSite/fieldData';
import type { DoorExtra, FieldApi, LabourMoments } from '../../src/sync/fieldApi';
import { capture, sendPending } from '../../src/sync/outbox';
import { TransportError, withExtra } from '../../src/sync/transport';
import { FakeClock, idSource, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const marco = { technicianId: 'marco', capturedBy: 'marco' };
const tokens = { tokenFor: (t: string) => `token-of-${t}` };

type Call = { door: string; jobId: string | null; body: unknown; extra: DoorExtra | undefined };

/** The sync fake plus the own doors, recording what each call carried. */
class DoorServer extends FakeServer implements Pick<FieldApi, 'jobAct' | 'recordLabour' | 'addCrew' | 'leaveCrew' | 'handBack' | 'raiseOrder' | 'jobBundle'> {
  readonly calls: Call[] = [];
  /** Throw this for the next call to a door, once. */
  failNext = new Map<string, TransportError>();
  private readonly seen = new Set<string>();

  private answer(door: string, jobId: string | null, body: unknown, extra: DoorExtra | undefined): Promise<Record<string, unknown>> {
    this.calls.push({ door, jobId, body, extra });
    const fail = this.failNext.get(door);
    if (fail) {
      this.failNext.delete(door);
      return Promise.reject(fail);
    }
    // The server's rule 7: a key it has seen answers `duplicate`.
    const key = extra?.key ? `${door}:${extra.key}` : null;
    const duplicate = key !== null && this.seen.has(key);
    if (key) this.seen.add(key);
    return Promise.resolve({ duplicate });
  }
  jobAct(jobId: string, act: 'depart' | 'arrive', extra?: DoorExtra) {
    return this.answer('act', jobId, { act }, extra);
  }
  recordLabour(jobId: string, moments: LabourMoments, extra?: DoorExtra) {
    return this.answer('labour', jobId, moments, extra);
  }
  addCrew(jobId: string, body: { technician_id: string; key: string }, extra?: DoorExtra) {
    return this.answer('crew', jobId, body, extra);
  }
  leaveCrew(jobId: string, body: { technician_id: string; ended_at: string | null }, extra?: DoorExtra) {
    return this.answer('leave', jobId, body, extra);
  }
  handBack(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra) {
    return this.answer('handBack', jobId, body, extra);
  }
  raiseOrder(body: Record<string, unknown>, extra?: DoorExtra) {
    return this.answer('raise', null, body, extra);
  }
  jobBundle(): never {
    throw new Error('not asked');
  }
  to(door: string): Call[] {
    return this.calls.filter((c) => c.door === door);
  }
}

function setup() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const deps = { newId: idSource('k'), clock };
  const server = new DoorServer();
  const opts = { clock, tokens, random: steadyRandom };
  return { clock, db, deps, server, opts };
}

function waveFor(env: ReturnType<typeof setup>, who: { technicianId: string; capturedBy: string }): Wave {
  return {
    db: env.db,
    technicianId: who.technicianId,
    newId: env.deps.newId,
    clock: env.clock,
    me: who.technicianId,
    s: scoped(env.db, who.technicianId),
    captor: who,
    deps: env.deps,
  } as unknown as Wave;
}

const depart = (at: string) => ({ action: 'start', kind: 'travel', started_at: at });

test("an own-door item goes under its CAPTOR's token, whoever is signed in — it no longer waits for them", async () => {
  const env = setup();
  const k = capture(env.db, dana, { kind: 'crew_time', workOrderId: 'wo-1', payload: depart('2026-10-21T08:00:00Z') }, env.deps);
  const h = capture(env.db, dana, { kind: 'hand_back', workOrderId: 'wo-2', payload: { reason: 'Van broke down' } }, env.deps);
  const summary = await sendPending(env.db, env.server, env.opts);
  expect(summary.waitingForCaptor).toBe(0);
  expect(env.server.to('labour')[0]?.extra).toEqual({ captureToken: 'token-of-dana' });
  // The act and the hand-back carry the item's own key (07-endpoints.md §0 rule 7).
  expect(env.server.to('act')[0]?.extra).toEqual({ key: k.key, captureToken: 'token-of-dana' });
  expect(env.server.to('handBack')[0]?.extra).toEqual({ key: h.key, captureToken: 'token-of-dana' });
  expect(outboxQ.getMine(scoped(env.db, 'dana'), k.key)?.state).toBe('accepted');
});

test('a resend of an act the server already has settles as duplicate, never as a second depart', async () => {
  const env = setup();
  const k = capture(env.db, dana, { kind: 'crew_time', workOrderId: 'wo-1', payload: depart('2026-10-21T08:00:00Z') }, env.deps);
  // The first send's answer is lost: the server HAS the act; the phone does not know.
  await env.server.jobAct('wo-1', 'depart', { key: k.key, captureToken: 'token-of-dana' });
  await sendPending(env.db, env.server, env.opts);
  expect(env.server.to('act').map((c) => c.extra?.key)).toEqual([k.key, k.key]);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), k.key)?.state).toBe('accepted');
  const h = capture(env.db, dana, { kind: 'hand_back', workOrderId: 'wo-3', payload: { reason: 'Too far' } }, env.deps);
  await env.server.handBack('wo-3', { reason: 'Too far', note: null }, { key: h.key });
  await sendPending(env.db, env.server, env.opts);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), h.key)?.state).toBe('duplicate');
});

test("a refused CAPTOR token waits for that captor and stops nobody else's work", async () => {
  const env = setup();
  const d = capture(env.db, dana, { kind: 'hand_back', workOrderId: 'wo-d', payload: { reason: 'Parts' } }, env.deps);
  const m = capture(env.db, marco, { kind: 'task_tick', workOrderId: 'wo-m', payload: {} }, env.deps);
  env.server.failNext.set(
    'handBack',
    new TransportError('auth', 'HTTP 403', 403, { message_key: 'work.mobile.capture_token_expired' }),
  );
  const summary = await sendPending(env.db, env.server, env.opts);
  expect(summary.stoppedForAuth).toBe(false);
  expect(summary.waitingForCaptor).toBe(1);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), d.key)).toMatchObject({ state: 'pending', attempts: 0, last_error: 'waiting_for_captor_sign_in' });
  expect(outboxQ.getMine(scoped(env.db, 'marco'), m.key)?.state).toBe('accepted');
});

test('a refusal of the SESSION still stops the run, as before', async () => {
  const env = setup();
  capture(env.db, dana, { kind: 'hand_back', workOrderId: 'wo-d', payload: { reason: 'Parts' } }, env.deps);
  env.server.failNext.set('handBack', new TransportError('auth', 'HTTP 401', 401, { message_key: 'auth.session_expired' }));
  const summary = await sendPending(env.db, env.server, env.opts);
  expect(summary.stoppedForAuth).toBe(true);
  expect(summary.waitingForCaptor).toBe(0);
});

test("FF-29's × goes to the crew door as a leave, with the moment it was tapped", async () => {
  const env = setup();
  const w = waveFor(env, dana);
  const key = removeTechnician(w, 'wo-1', 'tech-marco');
  expect(outboxQ.getMine(scoped(env.db, 'dana'), key)?.channel).toBe('job');
  await sendPending(env.db, env.server, env.opts);
  const leave = env.server.to('leave')[0]!;
  expect(leave.jobId).toBe('wo-1');
  expect(leave.body).toEqual({ technician_id: 'tech-marco', ended_at: env.clock.now().toISOString() });
  expect(leave.extra).toEqual({ captureToken: 'token-of-dana' });
});

test('a correction typed as minutes goes as the moments it means — naming the person only when it is not the captor', async () => {
  const env = setup();
  const w = waveFor(env, dana);
  const arrived = '2026-10-21T08:46:00.000Z';
  // FF-29: Dana corrects M. Chen — 0 minutes' travel (came with lead), 72 minutes' labour.
  correctTime(w, 'wo-1', { personId: 'tech-marco', arrivedAt: arrived, labourFrom: null }, { travel: 0, labour: 72 });
  // FF-15: Dana corrects her own — 14 minutes' travel, 72 minutes' labour.
  correctTime(w, 'wo-1', { personId: 'dana', arrivedAt: '2026-10-21T08:14:00.000Z', labourFrom: null }, { travel: 14, labour: 72 });
  await sendPending(env.db, env.server, env.opts);
  const [chen, own] = env.server.to('labour');
  expect(chen!.body).toEqual({
    depart_at: arrived,
    arrive_at: arrived,
    start_at: arrived,
    end_at: '2026-10-21T09:58:00.000Z',
  });
  expect(chen!.extra).toEqual({ captureToken: 'token-of-dana', technicianId: 'tech-marco' });
  expect(own!.body).toEqual({
    depart_at: '2026-10-21T08:00:00.000Z',
    arrive_at: '2026-10-21T08:14:00.000Z',
    start_at: '2026-10-21T08:14:00.000Z',
    end_at: '2026-10-21T09:26:00.000Z',
  });
  expect(own!.extra).toEqual({ captureToken: 'token-of-dana' });
});

test('admin time still waits; a route finding goes to the reads door (BR-WRK-067)', async () => {
  const env = setup();
  const admin = capture(
    env.db,
    dana,
    { kind: 'crew_time', workOrderId: null, payload: { action: 'start', kind: 'admin', task: 'vehicle_check', started_at: '2026-10-21T07:30:00Z' } },
    env.deps,
  );
  const finding = capture(env.db, dana, { kind: 'route_finding', routeId: 'r-1', payload: { finding: 'leak' } }, env.deps);
  await sendPending(env.db, env.server, env.opts);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), admin.key)).toMatchObject({ channel: 'unrouted', state: 'pending' });
  expect(outboxQ.getMine(scoped(env.db, 'dana'), finding.key)).toMatchObject({ channel: 'route' });
  expect(env.server.calls.filter((c) => JSON.stringify(c).includes('crew_time'))).toEqual([]);
});

test('FB-014 (DEF-FLD-10639): a REFUSED time no longer holds the close behind it until the next run', async () => {
  // WO-0171: the time item was refused ("That time is in the future") and the
  // close waited for the next sync — up to 15 minutes — so the office saw the
  // status change late. Red before the fix: the close stayed `pending`.
  const env = setup();
  const time = capture(env.db, dana, { kind: 'crew_time', workOrderId: 'wo-1', payload: depart('2026-10-21T08:00:00Z') }, env.deps);
  const close = capture(env.db, dana, { kind: 'close', workOrderId: 'wo-1', payload: { outcome: 'passed' } }, env.deps);
  env.server.failNext.set('act', new TransportError('http', 'HTTP 400', 400, { message_key: 'work.labour.moment_in_future' }));
  await sendPending(env.db, env.server, env.opts);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), time.key)?.state).toBe('refused');
  expect(outboxQ.getMine(scoped(env.db, 'dana'), close.key)?.state).toBe('accepted');
});

test('a network failure on a door still stops its job, so capture order holds', async () => {
  const env = setup();
  capture(env.db, dana, { kind: 'crew_time', workOrderId: 'wo-1', payload: depart('2026-10-21T08:00:00Z') }, env.deps);
  const close = capture(env.db, dana, { kind: 'close', workOrderId: 'wo-1', payload: { outcome: 'passed' } }, env.deps);
  env.server.failNext.set('act', new TransportError('network', 'offline'));
  await sendPending(env.db, env.server, env.opts);
  expect(outboxQ.getMine(scoped(env.db, 'dana'), close.key)?.state).toBe('pending');
});

test('the wire body carries key, capture_token and technician_id only when present', () => {
  expect(withExtra({ act: 'depart' })).toEqual({ act: 'depart' });
  expect(withExtra({ act: 'depart' }, { key: 'k1', captureToken: 't', technicianId: 'x' })).toEqual({
    act: 'depart',
    key: 'k1',
    capture_token: 't',
    technician_id: 'x',
  });
  expect(withExtra({ reason: 'r' }, { captureToken: null })).toEqual({ reason: 'r' });
});
