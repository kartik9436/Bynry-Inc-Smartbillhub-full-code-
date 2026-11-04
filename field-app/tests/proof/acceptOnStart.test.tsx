/**
 * DEF-FLD-10579 (beta report MQ-026) — THE PHONE NEVER ACCEPTED A JOB, so the
 * server refused ALL of a technician's work with *accept the job first*.
 *
 * The server's rule (`apps/work/mobile.require_captor_holds_job`, BR-WRK-059):
 * an item is taken only from the technician the job is assigned to AND who
 * ACCEPTED it. The fake below APPLIES that rule — every earlier fake took any
 * item for any job, which is how nothing caught this (the defect row's
 * escape reason).
 *
 * The PO's ruling (decision log 2026-10-24, *"MQ-026: STARTING A JOB ACCEPTS
 * IT; A NOT-YET-STARTED JOB CAN BE DECLINED WITH A REASON"*): the first
 * **Start** sends the server's accept ahead of any of that job's work; items
 * already refused with *accept the job first* go again on their own once it
 * lands; before starting, **Decline** with a reason; after, **Hand back**.
 *
 * Proved RED on the code before this fix (c0235680a), first case:
 *   expect(received).toEqual(expected)
 *   - Expected  - 1
 *   + Received  + 3
 *   - Array []
 *   + Array [
 *   +   "work.mobile.accept_the_job_first",
 *   + ]
 * — the safety tick was refused, and no accept was ever sent.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as woItemQ from '../../src/db/queries/woItem';
import { scoped } from '../../src/db/scoped';
import { refusalKeyOf } from '../../src/screens/me/dbData';
import { tickSafety } from '../../src/screens/theJob/actions';
import type { DoorExtra } from '../../src/sync/fieldApi';
import type { BatchAnswer, WireItem } from '../../src/sync/transport';
import { buildHandset, card, mountHandset, openAt, PEOPLE, ProofServer, settle, signInAs, syncNow, TENANT, upsert, type Handset } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MINUTE = 60_000;

/** The server's acceptance rule, applied: a job's items are refused until it is accepted. */
class AcceptingServer extends ProofServer {
  readonly accepted = new Set<string>();
  readonly declined = new Map<string, string>();
  /** Every door and batch, in the order the server saw them. */
  readonly order: string[] = [];

  override sendJobBatch(workOrderId: string, items: WireItem[]): Promise<BatchAnswer> {
    this.order.push(`batch:${workOrderId}`);
    if (this.accepted.has(workOrderId)) return super.sendJobBatch(workOrderId, items);
    // `sync._send_back`: refused, NOT acknowledged, nothing stored.
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
    this.accepted.add(jobId);
    return Promise.resolve({ order_id: jobId, technician_acceptance: { state: 'accepted', at: new Date().toISOString(), reason: null } });
  }

  override declineJob(jobId: string, body: { reason: string; note: string | null }, extra?: DoorExtra): Promise<Record<string, unknown>> {
    this.order.push(`decline:${jobId}`);
    this.doorCalls.push(['decline', jobId, body]);
    this.doorExtras.push(['decline', extra]);
    this.declined.set(jobId, body.reason);
    return Promise.resolve({ order_id: jobId, technician_acceptance: { state: 'declined', at: new Date().toISOString(), reason: body.reason } });
  }
}

async function dayWithOneJob(id = 'wo-7028', number = 'WO-0028') {
  const h: Handset = buildHandset({ network: 'wifi' });
  const server = new AcceptingServer();
  h.servers.set(TENANT, server);
  const first = new Date(h.clock.now() + 30 * MINUTE);
  server.feed([upsert(card(id, number, first, 40), h.iso())]);
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current;
  if (!db) throw new Error('the store did not open at sign-in');
  const s = scoped(db, DANA);
  db.transaction(() => {
    woItemQ.upsert(s, { id: `${id}-safe`, workOrderId: id, kind: 'safety', position: 1, label: 'Isolate supply' }, h.iso());
  });
  return { h, server, m, db, s, id, number };
}

function refusals(s: ReturnType<typeof scoped>): (string | null)[] {
  return outboxQ
    .listMine(s, { states: ['refused'], limit: 100 })
    .map((r) => (JSON.parse(r.refusal ?? '{}') as { message_key?: string }).message_key ?? null);
}

test('an unaccepted job: Start → work → sync — the accept goes first and nothing is refused', async () => {
  const { server, m, s, id } = await dayWithOneJob();
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-start`));
  });
  const port = m.inside.current.job;
  if (!port) throw new Error('no job port');
  tickSafety(port, id, `${id}-safe`);
  await syncNow(m);

  expect(refusals(s)).toEqual([]);
  expect(server.callsTo('accept')).toEqual([[id]]);
  // The accept reached the server before any of that job's work.
  expect(server.order.filter((o) => o.endsWith(id))).toEqual([`accept:${id}`, `batch:${id}`]);
  expect(server.applied.map((a) => a.kind)).toEqual(['safety_tick']);
  // Under Dana's own capture credential, like every other own-door item.
  expect(server.doorExtras.find(([d]) => d === 'accept')?.[1]?.captureToken).toBeTruthy();
  // A second press — Finish now: its one part, safety, is done (DEF-FLD-10607) — sends nothing more.
  await openAt(m, 'FF-10');
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-finish`));
  });
  await syncNow(m);
  expect(server.callsTo('accept')).toEqual([[id]]);
});

test('the start works offline: the accept waits in the outbox and goes first when the signal returns', async () => {
  const { h, server, m, s, id } = await dayWithOneJob();
  h.network.set('none');
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-start`));
  });
  const port = m.inside.current.job!;
  tickSafety(port, id, `${id}-safe`);
  await syncNow(m);
  expect(server.callsTo('accept')).toEqual([]);
  h.network.set('wifi');
  await syncNow(m);
  expect(refusals(s)).toEqual([]);
  expect(server.order.filter((o) => o.endsWith(id))).toEqual([`accept:${id}`, `batch:${id}`]);
});

test('today’s stuck state: work refused for “accept the job first” clears after Start, with no Fix and send again', async () => {
  const { server, m, s, id } = await dayWithOneJob();
  // The beta handset's day, captured on a build before DEF-FLD-10612 put the
  // accept on every capture: thirteen items in the outbox and no accept…
  const db = m.inside.current.job!.db;
  db.transaction(() => {
    for (let i = 0; i < 13; i++) {
      outboxQ.insert(s, {
        id: `old-${i}`,
        workOrderId: id,
        routeId: null,
        kind: 'safety_tick',
        channel: 'job',
        payload: { safety_id: `${id}-safe` },
        seq: i + 1,
        capturedBy: DANA,
        capturedAt: new Date().toISOString(),
        location: null,
      });
    }
  });
  await syncNow(m);
  expect(refusals(s)).toHaveLength(13);
  expect(refusals(s).every((k) => k === 'work.mobile.accept_the_job_first')).toBe(true);
  // …and FF-50 says it in words, not as the raw code.
  const row = outboxQ.listMine(s, { states: ['refused'], limit: 1 })[0]!;
  expect(refusalKeyOf(row.refusal)).toBe('work.mobile.accept_the_job_first');
  // The old rows never ticked the step on the phone, so the card still reads Start; it accepts.
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-start`));
  });
  await syncNow(m);
  expect(refusals(s)).toEqual([]);
  expect(server.applied).toHaveLength(13);
  expect(server.callsTo('accept')).toEqual([[id]]);
});

test('Decline: a reason is required, the job stays listed as Declined, and Start and Decline go', async () => {
  const { server, m, id } = await dayWithOneJob();
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  const cardView = within(screen.getByTestId(`job-${id}`));
  await act(async () => {
    fireEvent.press(cardView.getByTestId(`job-${id}-decline`));
  });
  const sheet = within(await screen.findByTestId('decline-sheet'));
  // No reason picked: the button does nothing.
  expect(sheet.getByTestId('decline-confirm').props.accessibilityState?.disabled).toBe(true);
  await act(async () => {
    fireEvent.press(sheet.getByTestId('decline-reason-time'));
  });
  await act(async () => {
    fireEvent.press(sheet.getByTestId('decline-confirm'));
  });
  await syncNow(m);
  expect(server.callsTo('decline')).toEqual([[id, { reason: 'time', note: null }]]);
  expect(server.callsTo('accept')).toEqual([]);
  const after = within(screen.getByTestId(`job-${id}`));
  expect(after.getByTestId(`job-${id}-declined`)).toBeTruthy();
  expect(after.queryByTestId(`job-${id}-start`)).toBeNull();
  expect(after.queryByTestId(`job-${id}-decline`)).toBeNull();
});

test('“Other” needs a note before it can be sent', async () => {
  const { server, m, id } = await dayWithOneJob();
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-decline`));
  });
  const sheet = within(await screen.findByTestId('decline-sheet'));
  await act(async () => {
    fireEvent.press(sheet.getByTestId('decline-reason-other'));
  });
  expect(sheet.getByTestId('decline-confirm').props.accessibilityState?.disabled).toBe(true);
  await act(async () => {
    fireEvent.changeText(sheet.getByTestId('decline-note'), 'Van in the shop');
  });
  await act(async () => {
    fireEvent.press(sheet.getByTestId('decline-confirm'));
  });
  await syncNow(m);
  expect(server.callsTo('decline')).toEqual([[id, { reason: 'other', note: 'Van in the shop' }]]);
});

test('a job already accepted (on the web, or earlier) is not accepted again and offers no Decline', async () => {
  const { server, m, id } = await dayWithOneJob();
  // `mobile.bundle` answers where the job stands; the office accepted it for her.
  server.accepted.add(id);
  server.bundles.set(id, {
    order_id: id,
    order_no: 'WO-0028',
    template_id: null,
    template_version: null,
    safety: [],
    tasks: [],
    readings: [],
    materials: [],
    technician_acceptance: { state: 'accepted', at: '2026-10-24T08:05:00Z', reason: null },
  });
  await syncNow(m);
  expect(server.callsTo('bundle')).toContainEqual([id]);
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(within(screen.getByTestId(`job-${id}`)).queryByTestId(`job-${id}-decline`)).toBeNull();
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-start`));
  });
  await syncNow(m);
  expect(server.callsTo('accept')).toEqual([]);
});

test('once started, Decline is gone from the card and the job screen; Hand back is the way out', async () => {
  const { m, id } = await dayWithOneJob();
  await openAt(m, 'FF-15', { workOrderId: id });
  const before = within(await screen.findByTestId('screen-FF-15'));
  expect(before.getByTestId('job-decline')).toBeTruthy();
  expect(before.queryByTestId('door-FF-58')).toBeNull();

  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  await act(async () => {
    fireEvent.press(screen.getByTestId(`job-${id}-start`));
  });
  await openAt(m, 'FF-10');
  expect(within(screen.getByTestId(`job-${id}`)).queryByTestId(`job-${id}-decline`)).toBeNull();
  await openAt(m, 'FF-15', { workOrderId: id });
  const after = within(await screen.findByTestId('screen-FF-15'));
  expect(after.queryByTestId('job-decline')).toBeNull();
  expect(after.getByTestId('door-FF-58')).toBeTruthy();
});
