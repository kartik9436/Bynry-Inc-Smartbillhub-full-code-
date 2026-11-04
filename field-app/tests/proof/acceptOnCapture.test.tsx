/**
 * DEF-FLD-10612 (beta report MQ-027) — ANY WORK ON A JOB ACCEPTS IT.
 *
 * DEF-FLD-10579 put the server's accept on three buttons (Today's *Start*,
 * the stop's *Start*, FF-15's *Continue*). Every test started work through
 * Start, so work saved by any OTHER way in — FF-15's Safety row, a photo, a
 * note, the tablet's pane (its own file), a job opened cold as a notification
 * opens it — went to the server unaccepted and came back *Accept the job
 * first*. The PO (decision log 2026-10-26, *"MQ-027"*), verbatim: *"if
 * technician is starting the job , that means it have accepted it , so this
 * issue should not be there as accept the job first"*.
 *
 * The fake applies the server's acceptance rule (BR-WRK-059), and can refuse
 * the accept itself the three ways the server does (`mobile.accept_job`): a
 * 404 when the job is no longer this technician's (reassigned),
 * `job_finished` (cancelled or closed) and `job_already_declined`.
 *
 * Proved RED on the code before this fix (law 7) — the outbox held no
 * `job_accept` and the first case failed:
 *   expect(received).toEqual(expected)
 *   - Array ["job_accept", "safety_tick"]
 *   + Array ["safety_tick"]
 * and the FF-50 cases found thirteen rows each with *Fix and send again*.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as woItemQ from '../../src/db/queries/woItem';
import { scoped } from '../../src/db/scoped';
import { declineJob } from '../../src/screens/theDay/acceptance';
import { addStep, capturePhoto, tickSafety } from '../../src/screens/theJob/actions';
import type { DoorExtra } from '../../src/sync/fieldApi';
import { TransportError, type BatchAnswer, type WireItem } from '../../src/sync/transport';
import { buildHandset, card, mountHandset, openAt, PEOPLE, ProofServer, settle, signInAs, syncNow, TENANT, upsert, type Handset } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MINUTE = 60_000;

type AcceptRefusal = 'reassigned' | 'cancelled' | 'declined' | null;

/** The server's acceptance rule, applied — and its accept door, refusing when told to. */
class AcceptingServer extends ProofServer {
  readonly accepted = new Set<string>();
  readonly order: string[] = [];
  refuseAccept: AcceptRefusal = null;

  override sendJobBatch(workOrderId: string, items: WireItem[]): Promise<BatchAnswer> {
    this.order.push(`batch:${workOrderId}`);
    if (this.accepted.has(workOrderId)) return super.sendJobBatch(workOrderId, items);
    const answers = items.map((i) => ({
      key: i.key,
      kind: i.kind,
      seq: i.seq,
      result: 'refused' as const,
      ack: false,
      detail: { reason: 'accept_the_job_first', message_key: 'work.mobile.accept_the_job_first', params: { order_no: workOrderId } },
    }));
    return Promise.resolve({ accepted: 0, duplicate: 0, refused: answers.length, held_for_review: 0, acknowledged: [], items: answers });
  }

  override acceptJob(jobId: string, extra?: DoorExtra): Promise<Record<string, unknown>> {
    this.order.push(`accept:${jobId}`);
    this.doorCalls.push(['accept', jobId]);
    this.doorExtras.push(['accept', extra]);
    if (this.refuseAccept === 'reassigned') {
      // `_own_job_or_404`: the job is no longer assigned to her.
      return Promise.reject(new TransportError('http', 'HTTP 404', 404, { code: null, message: 'not found' }));
    }
    if (this.refuseAccept === 'cancelled') {
      return Promise.reject(new TransportError('http', 'HTTP 409', 409, { code: 'BIZ-STATE', message_key: 'work.mobile.job_finished' }));
    }
    if (this.refuseAccept === 'declined') {
      return Promise.reject(new TransportError('http', 'HTTP 409', 409, { code: 'BIZ-STATE', message_key: 'work.mobile.job_already_declined' }));
    }
    this.accepted.add(jobId);
    return Promise.resolve({ order_id: jobId, technician_acceptance: { state: 'accepted', at: new Date().toISOString(), reason: null } });
  }

  override declineJob(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<Record<string, unknown>> {
    this.order.push(`decline:${jobId}`);
    this.doorCalls.push(['decline', jobId, body]);
    this.doorExtras.push(['decline', extra]);
    return Promise.resolve({ order_id: jobId, technician_acceptance: { state: 'declined', at: new Date().toISOString(), reason: body.reason } });
  }
}

async function dayWithOneJob(id = 'wo-7028', number = 'WO-0028') {
  const h: Handset = buildHandset({ network: 'wifi' });
  const server = new AcceptingServer();
  h.servers.set(TENANT, server);
  server.feed([upsert(card(id, number, new Date(h.clock.now() + 30 * MINUTE), 40), h.iso())]);
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current;
  if (!db) throw new Error('the store did not open at sign-in');
  const s = scoped(db, DANA);
  db.transaction(() => {
    woItemQ.upsert(s, { id: `${id}-safe`, workOrderId: id, kind: 'safety', position: 1, label: 'Isolate supply' }, h.iso());
    woItemQ.upsert(s, { id: `${id}-task`, workOrderId: id, kind: 'task', position: 2, label: 'Swap the meter' }, h.iso());
  });
  return { h, server, m, db, s, id, number };
}

/** This job's outbox, in send order. */
function queued(s: ReturnType<typeof scoped>, id: string): string[] {
  return s
    .all<{ kind: string }>(`SELECT kind FROM outbox WHERE technician_id = :technician_id AND work_order_id = :id ORDER BY seq`, { id })
    .map((r) => r.kind);
}

function refusals(s: ReturnType<typeof scoped>): (string | null)[] {
  return outboxQ
    .listMine(s, { states: ['refused'], limit: 100 })
    .map((r) => (JSON.parse(r.refusal ?? '{}') as { message_key?: string }).message_key ?? null);
}

const PHOTO = { localPath: 'file:///p/1.jpg', sha256: 'a'.repeat(64), bytes: 1200, width: 800, height: 600, overCeiling: false };

test("a safety tick on FF-15's Safety row with no Start: the accept goes first and nothing is refused", async () => {
  const { server, m, s, id } = await dayWithOneJob();
  await openAt(m, 'FF-15', { workOrderId: id });
  const job = within(await screen.findByTestId('screen-FF-15'));
  await act(async () => {
    fireEvent.press(job.getByTestId('door-FF-16'));
  });
  const safety = within(await screen.findByTestId('screen-FF-16'));
  await act(async () => {
    fireEvent.press(safety.getByTestId(`safety-${id}-safe`));
  });
  expect(queued(s, id)).toEqual(['job_accept', 'safety_tick']);
  await syncNow(m);
  expect(refusals(s)).toEqual([]);
  expect(server.order.filter((o) => o.endsWith(id))).toEqual([`accept:${id}`, `batch:${id}`]);
  expect(server.applied.map((a) => a.kind)).toEqual(['safety_tick']);
});

test('a photo and a note (an added step) on an unstarted job: ONE accept, ahead of both', async () => {
  const { server, m, s, id } = await dayWithOneJob();
  const port = m.inside.current.job!;
  capturePhoto(port, id, PHOTO, { task_id: `${id}-task` });
  addStep(port, id, { label: 'Clear the pit', reason: 'Flooded', minutes: 10, photoRequired: false, position: 3 });
  expect(queued(s, id)).toEqual(['job_accept', 'photo', 'remark']);
  await syncNow(m);
  expect(refusals(s)).toEqual([]);
  expect(server.callsTo('accept')).toEqual([[id]]);
});

test('a job opened cold, as a notification opens it: the first tick accepts it', async () => {
  const { m, s, id } = await dayWithOneJob();
  // No Today, no Start: FF-15 is the first screen of the visit.
  await openAt(m, 'FF-16', { workOrderId: id });
  const safety = within(await screen.findByTestId('screen-FF-16'));
  await act(async () => {
    fireEvent.press(safety.getByTestId(`safety-${id}-safe`));
  });
  await syncNow(m);
  expect(queued(s, id)[0]).toBe('job_accept');
  expect(refusals(s)).toEqual([]);
});

test('Start and the capture path are one accept, whichever comes first', async () => {
  const { server, m, s, id } = await dayWithOneJob();
  const port = m.inside.current.job!;
  tickSafety(port, id, `${id}-safe`);
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    // Resume (or Finish) — whichever the card reads with its safety done.
    fireEvent.press(screen.getByTestId(new RegExp(`^job-${id}-(start|resume|finish)$`)));
  });
  expect(queued(s, id).filter((k) => k === 'job_accept')).toHaveLength(1);
  await syncNow(m);
  expect(server.callsTo('accept')).toEqual([[id]]);
  // Work after the accept landed queues nothing more.
  capturePhoto(port, id, PHOTO, { task_id: `${id}-task` });
  await syncNow(m);
  expect(server.callsTo('accept')).toEqual([[id]]);
  expect(refusals(s)).toEqual([]);
});

test('a declined job: the work is saved, never dropped, and no accept is queued', async () => {
  const { server, m, db, s, id } = await dayWithOneJob();
  const port = m.inside.current.job!;
  expect(declineJob(db, s, port.captor(), id, { reason: 'time', note: '' }, { newId: port.newId, clock: port.clock })).toBe(true);
  tickSafety(port, id, `${id}-safe`);
  expect(queued(s, id)).toEqual(['job_decline', 'safety_tick']);
  await syncNow(m);
  expect(server.callsTo('accept')).toEqual([]);
});

test('an accept refused as reassigned: FF-50 shows one row with that reason and no Fix and send again', async () => {
  const { server, m, s, id } = await dayWithOneJob();
  server.refuseAccept = 'reassigned';
  const port = m.inside.current.job!;
  tickSafety(port, id, `${id}-safe`);
  await syncNow(m);
  await syncNow(m);
  // The accept is refused and the tick behind it comes back "accept first" — kept, never dropped.
  expect(refusals(s)).toHaveLength(2);
  // A second tick does not stack a second accept on a refused one.
  tickSafety(port, id, `${id}-safe`);
  expect(queued(s, id).filter((k) => k === 'job_accept')).toHaveLength(1);
  await syncNow(m);

  await openAt(m, 'FF-50');
  const sync = within(await screen.findByTestId('ff50-refused'));
  // DEF-FLD-10623: the refused accept is the row's cause, not an item — two ticks.
  expect(sync.getByText('WO-0028 · 2 items · This job was reassigned.')).toBeTruthy();
  expect(sync.queryAllByText('Fix and send again')).toHaveLength(0);
  expect(sync.queryAllByText('Send again')).toHaveLength(0);
  expect(sync.queryAllByText('Accept the job first.')).toHaveLength(0);
});

test('thirteen refusals on one job for one reason are ONE row with the count', async () => {
  const { server, m, s, id } = await dayWithOneJob();
  server.refuseAccept = 'cancelled';
  const port = m.inside.current.job!;
  for (let i = 0; i < 12; i++) tickSafety(port, id, `${id}-safe`);
  await syncNow(m);
  await syncNow(m);
  expect(refusals(s)).toHaveLength(13);

  await openAt(m, 'FF-50');
  const sync = within(await screen.findByTestId('ff50-refused'));
  // The feed has not said "cancelled", so the server's own words for job_finished.
  // Twelve ticks; the accept is the cause and is not counted (DEF-FLD-10623).
  expect(sync.getByText('WO-0028 · 12 items · This job is already finished.')).toBeTruthy();
  expect(sync.queryAllByText('Fix and send again')).toHaveLength(0);
  // The items are behind it, one press away.
  const toggle = sync.getAllByText('Show items')[0]!;
  await act(async () => {
    fireEvent.press(toggle);
  });
  expect(sync.getAllByText('Safety check')).toHaveLength(12);
});

test('an accept refused because she declined it says so', async () => {
  const { server, m, id } = await dayWithOneJob();
  server.refuseAccept = 'declined';
  tickSafety(m.inside.current.job!, id, `${id}-safe`);
  await syncNow(m);
  await syncNow(m);
  await openAt(m, 'FF-50');
  const sync = within(await screen.findByTestId('ff50-refused'));
  // One tick behind the refused accept: named by its word (DEF-FLD-10623).
  expect(sync.getByText('WO-0028 · Safety check · You declined this job.')).toBeTruthy();
});
