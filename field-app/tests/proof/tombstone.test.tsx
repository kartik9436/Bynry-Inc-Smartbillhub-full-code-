/**
 * T-47 — THE TOMBSTONE, end to end: server feed → the client's delta → the
 * store → the screen. A job the dispatcher reassigns away arrives on
 * `GET work/mobile/changes` as `{change: 'removed'}` (R57), and must LEAVE the
 * handset — asserted by ADDRESS (FF-15 opened with that job's id now shows
 * "no job", the route it was at is gone) and by what the screen then shows
 * (Today no longer lists it) — while the work already captured against it
 * still reaches the server (Mobile data §10, "A job leaves your day").
 *
 * Proved RED (law 7): with `removeJobMirror`'s `workOrderQ.deleteMine` taken
 * out, Today went on listing WO-6002 and its address still opened the job —
 * quoted in the lane report.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, screen, within } from '@testing-library/react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as woItemQ from '../../src/db/queries/woItem';
import { scoped } from '../../src/db/scoped';
import { tickTask } from '../../src/screens/theJob/actions';
import { buildHandset, card, mountHandset, openAt, PEOPLE, removed, settle, signInAs, syncNow, TENANT, upsert } from './runtimeApp';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const DANA = PEOPLE['d.ortiz']!.technicianId;
const MINUTE = 60_000;

function todayIds(): string[] {
  return screen.queryAllByTestId(/^job-wo-\d+$/).map((el) => String(el.props.testID).replace('job-', ''));
}

/** Pull to refresh on Today (R43): the same act a thumb does — sync, then re-read. */
async function pullToRefresh(): Promise<void> {
  const list = screen.getByTestId('today-list');
  await act(async () => {
    await list.props.refreshControl.props.onRefresh();
  });
}

test('T-47: a job reassigned away leaves the handset — its address opens nothing and Today stops listing it', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const start = new Date(h.clock.now() + 30 * MINUTE);
  const jobs = [1, 2, 3].map((i) => card(`wo-600${i}`, `WO-600${i}`, new Date(start.getTime() + i * 60 * MINUTE)));
  server.feed(jobs.map((j) => upsert(j, h.iso())));

  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  const db = h.holder.current!;
  const s = scoped(db, DANA);
  woItemQ.upsert(s, { id: 'wo-6002-t1', workOrderId: 'wo-6002', kind: 'task', position: 1, label: 'Check seal' }, h.iso());

  // Before: all three on Today, and WO-6002's address opens it.
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(todayIds()).toEqual(['wo-6001', 'wo-6002', 'wo-6003']);
  await openAt(m, 'FF-15', { workOrderId: 'wo-6002' });
  expect(within(await screen.findByTestId('screen-FF-15')).queryByTestId('job-none')).toBeNull();
  expect(m.ref.getCurrentRoute()).toMatchObject({ name: 'FF-15', params: { workOrderId: 'wo-6002' } });

  // Dana ticks a task on it with no signal — captured work against the job.
  h.network.set('none');
  const ticked = tickTask(m.inside.current.job!, 'wo-6002', 'wo-6002-t1');

  // The dispatcher gives WO-6002 to Marco. The server's feed says so.
  server.feed([removed('wo-6002', h.iso())]);

  // Back on Today, signal returns, and Dana pulls to refresh.
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  h.network.set('wifi');
  await pullToRefresh();
  await settle();

  // BY WHAT THE SCREEN SHOWS: Today no longer lists it; the other two stay, in order.
  expect(todayIds()).toEqual(['wo-6001', 'wo-6003']);
  // BY ADDRESS: the address it lived at now opens "no job" — it is not on the phone.
  await openAt(m, 'FF-15', { workOrderId: 'wo-6002' });
  expect(m.ref.getCurrentRoute()).toMatchObject({ name: 'FF-15', params: { workOrderId: 'wo-6002' } });
  expect(within(await screen.findByTestId('screen-FF-15')).getByTestId('job-none')).toBeTruthy();
  // In the store: the mirror is gone, rows and all.
  expect(workOrderQ.getMine(s, 'wo-6002')).toBeUndefined();
  expect(woItemQ.listForOrder(s, 'wo-6002')).toEqual([]);
  // …and the tick Dana made on it still reached the server, once, before the mirror went.
  expect(server.applied.filter((a) => a.key === ticked)).toHaveLength(1);
  expect(outboxQ.getMine(s, ticked)?.state).toBe('accepted');
  m.unmount();
}, 60_000);

test('T-47 (background sync): a removal pulled by the runtime on its own reaches Today the next time Today is opened', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const start = new Date(h.clock.now() + 30 * MINUTE);
  server.feed([1, 2].map((i) => upsert(card(`wo-610${i}`, `WO-610${i}`, new Date(start.getTime() + i * 60 * MINUTE)), h.iso())));
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();

  await openAt(m, 'FF-63');
  server.feed([removed('wo-6101', h.iso())]);
  await syncNow(m); // the 15-minute run, or the one on reconnect — not a pull on Today
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(todayIds()).toEqual(['wo-6102']);
  m.unmount();
}, 60_000);

/**
 * DEF-FLD-10359 — A DEFECT THIS PROOF FOUND, held open by `test.failing` until
 * lane INTEGRATE-2 fixed it: the runtime now moves `storeVersion` after every
 * sync run and Today re-reads on it. The words below are how it was.
 * Today re-reads the store only on its own pull-to-refresh, a tab change or a
 * re-focus (`TodayScreen.tsx`, `tick`). A removal pulled by the runtime's OWN
 * runs — the 15-minute timer, coming back into signal — leaves the job on the
 * list the technician is looking at; tapping it opens FF-15 on "no job". The
 * fix belongs to the runtime → screen seam (a store-changed signal the day
 * screens re-read on), not to this test.
 */
test('T-47 (on screen, DEF-FLD-10359 fixed): Today, left open while the runtime pulls a removal, stops listing the job', async () => {
  const h = buildHandset({ network: 'wifi' });
  const server = h.serverFor(TENANT);
  const start = new Date(h.clock.now() + 30 * MINUTE);
  server.feed([1, 2].map((i) => upsert(card(`wo-620${i}`, `WO-620${i}`, new Date(start.getTime() + i * 60 * MINUTE)), h.iso())));
  const m = mountHandset(h);
  await signInAs(h, 'd.ortiz');
  await settle();
  await openAt(m, 'FF-10');
  await screen.findByTestId('screen-FF-10');
  expect(todayIds()).toEqual(['wo-6201', 'wo-6202']);
  server.feed([removed('wo-6201', h.iso())]);
  await syncNow(m);
  await settle();
  expect(todayIds()).toEqual(['wo-6202']);
  m.unmount();
}, 60_000);
