/**
 * DEF-FLD-10623 (PO retest item 7) — the office reassigned WO-0155 while the
 * phone held unsent work on it. FF-50 showed, on the first sync,
 * *"job_accept · This job was reassigned."* and on the next,
 * *"4 items · This job was reassigned."* — no job number (the change feed had
 * removed the job, and with it the number), the raw kind word, the refused
 * accept counted as work, and no *The office will review this.* because the
 * accept's door keeps no office copy and the group asked it anyway.
 *
 * Each test here goes through the REAL path: the work is captured while the
 * job is on the phone (so its accept is queued first, DEF-FLD-10579), then the
 * feed's `removed` deletes the job mirror, then the server's answers land.
 */
import 'react-native-gesture-handler/jestSetup';

import { screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../../src/db/queries/outbox';
import * as workOrder from '../../../src/db/queries/workOrder';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { groupRefusals } from '../../../src/screens/me/refusalGroups';
import { removeJobMirror } from '../../../src/sync/delta';
import { capture } from '../../../src/sync/outbox';
import { at, DANA, makeFixture, openScreen } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Fixture = ReturnType<typeof makeFixture>;

/** WO-0155 on the phone, not yet accepted; three readings saved; then the office moves it. */
function reassignWithWork(fixture: Fixture): { accept: string; work: string[] } {
  const s = scoped(fixture.db, DANA);
  workOrder.upsertFromServer(
    s,
    {
      id: 'wo-0155',
      number: 'WO-0155',
      type: 'Meter exchange',
      state: 'scheduled',
      dispatchState: 'scheduled',
      priorityCode: 'P3',
      priorityRank: 3,
      premiseId: null,
      windowStart: at('09:00'),
      windowEnd: null,
      dueAt: null,
      estMinutes: 45,
      accessNotes: null,
      hazards: null,
      gateCode: null,
      extra: null,
      serverUpdatedAt: at('06:00'),
    },
    at('06:00'),
  );
  const work = [0, 1, 2].map(
    (i) =>
      capture(
        fixture.db,
        { technicianId: DANA, capturedBy: DANA },
        { kind: 'reading', workOrderId: 'wo-0155', payload: { value: String(100 + i) } },
        { newId: fixture.ids, clock: { now: () => new Date(at('09:30')) } },
      ).key,
  );
  const accept = outboxQ.acceptanceActsMine(s, 'wo-0155').find((r) => r.kind === 'job_accept')!.id;
  // The change feed answers `removed` for a job that is no longer hers.
  removeJobMirror(s, 'wo-0155');
  expect(workOrder.getMine(s, 'wo-0155')).toBeUndefined();
  return { accept, work };
}

const card = () => within(screen.getAllByTestId('ff50-refused').at(-1)!);

test('the job number is kept on the act, so it survives the job leaving the phone', () => {
  const fixture = makeFixture();
  const { accept, work } = reassignWithWork(fixture);
  const s = scoped(fixture.db, DANA);
  for (const key of [accept, ...work]) expect(outboxQ.getMine(s, key)?.work_order_number).toBe('WO-0155');
});

test('reassigned with three readings kept for the office: "WO-0155 · 3 items · This job was reassigned." and the office sentence', async () => {
  const fixture = makeFixture();
  const { accept, work } = reassignWithWork(fixture);
  const receipt = deviceWide(fixture.db, 'receipt');
  outboxQ.refuse(receipt, accept, { status: 404, body: { message: 'not found' } });
  for (const key of work) {
    outboxQ.refuse(receipt, key, { reason: 'not_your_job', message_key: 'work.mobile.not_your_job', kept_for_office: true });
  }
  const app = await openScreen('FF-50', fixture);
  const c = card();
  expect(c.getByText('WO-0155 · 3 items · This job was reassigned.')).toBeTruthy();
  expect(c.getByText('The office will review this.')).toBeTruthy();
  expect(c.queryByText(/job_accept/)).toBeNull();
  expect(c.queryByText(/4 items/)).toBeNull();
  app.unmount();
});

test('the first sync, with only the accept back: "WO-0155 · This job was reassigned." — the readings still waiting, not refused', async () => {
  const fixture = makeFixture();
  const { accept, work } = reassignWithWork(fixture);
  outboxQ.refuse(deviceWide(fixture.db, 'receipt'), accept, { status: 404, body: { message: 'not found' } });
  const app = await openScreen('FF-50', fixture);
  const c = card();
  expect(c.getByText('WO-0155 · This job was reassigned.')).toBeTruthy();
  expect(c.queryByText(/job_accept/)).toBeNull();
  // No office copy exists for an accept, so nothing is promised.
  expect(c.queryByText('The office will review this.')).toBeNull();
  const s = scoped(fixture.db, DANA);
  expect(work.map((k) => outboxQ.getMine(s, k)?.state)).toEqual(['pending', 'pending', 'pending']);
  app.unmount();
});

describe('groupRefusals — the refused accept is the cause, not work', () => {
  const item = (id: string, kind: string, kept: boolean) => ({
    id,
    kind,
    workOrderId: 'wo-0155',
    workOrderNumber: 'WO-0155',
    reason: '',
    reasonKey: 'field.ff50.refused.reassigned',
    action: 'none' as const,
    keptForOffice: kept,
  });

  test('excluded from the count and from the office check', () => {
    const [g] = groupRefusals([item('a', 'job_accept', false), item('b', 'reading', true), item('c', 'reading', true)]);
    expect(g!.cause?.id).toBe('a');
    expect(g!.work.map((i) => i.id)).toEqual(['b', 'c']);
    expect(g!.keptForOffice).toBe(true);
  });

  test('an accept alone: no work, nothing kept, still one row', () => {
    const groups = groupRefusals([item('a', 'job_accept', false)]);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.work).toEqual([]);
    expect(groups[0]!.keptForOffice).toBe(false);
  });

  test('an accept refused for a reason the technician can fix is work, as before', () => {
    const [g] = groupRefusals([{ ...item('a', 'job_accept', false), action: 'fix' as const }]);
    expect(g!.cause).toBeNull();
    expect(g!.work).toHaveLength(1);
  });
});
