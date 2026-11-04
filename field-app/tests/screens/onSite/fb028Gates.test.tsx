/**
 * FB-028 (DEF-FLD-10803) — PO rulings of 2026-10-31: a job RAISED ON SITE
 * gates its own steps.
 *   RECONNECT (FF-61): the live balance at or below the template's Reconnect
 *     limit enables Reconnect; above it the step stops — "Still owes $804.50.
 *     Leave it off." — and the office is told; a figure that is not fresh
 *     cannot pass ("Check the balance with signal.").
 *   DISCONNECT (FF-27): stops with its reason when the balance is cleared,
 *     the notice period is not over, or the account is protected; the office
 *     is told on each.
 *   SKILL (FF-15, W3 = C): the phone warns before Start.
 * Worked figures from the decision log: $18.40 and $804.50 against $25.00; a
 * notice ending 5 Nov.
 *
 * Red proof (law 7): every case here was run against the code before FB-028
 * and failed (no `reconnect-gated`, no `disconnect-held`, no tell, no
 * `job-skill-missing`; `Reconnect anyway` was offered at $804.50).
 */
import { fireEvent, waitFor, within } from '@testing-library/react-native';

import * as workOrderQ from '../../../src/db/queries/workOrder';
import { scoped } from '../../../src/db/scoped';
import { resetTold } from '../../../src/screens/onSite/fieldGate';
import { pullChanges } from '../../../src/sync/delta';
import { fetchBundles } from '../../../src/sync/extras';
import type { FieldApi } from '../../../src/sync/fieldApi';
import { FakeClock } from '../../db/support/fixtures';
import { FakeServer, serverBundle, serverCard } from '../../sync/support/fakeServer';
import { DANA as JOB_DANA, makeServices } from '../theJob/fixture';
import { mountJob, onTop as jobOnTop } from '../theJob/harness';
import { current, DANA, local, makeWave, NOW, openScreen } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

beforeEach(() => resetTold());

const raised = (w: ReturnType<typeof makeWave>, id: string, extra: Record<string, unknown> = {}) =>
  workOrderQ.setDetails(scoped(w.db, DANA), id, { raised_on_site: true, reconnect_limit: '25.0000', ...extra });

const fresh = (wo: string, balance: string, gate: Record<string, unknown> | null = null) => ({
  workOrderId: wo,
  currency: 'USD',
  balance,
  asAt: NOW.toISOString(),
  gate: gate as never,
});

describe('FF-61 · a reconnect raised on site is gated by the template limit', () => {
  test('$18.40 owed, at or under $25.00, read now: Reconnect is enabled and nothing is told', async () => {
    const w = makeWave();
    raised(w, 'wo-4830');
    w.money.answer(fresh('wo-4830', '18.40'));
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('reconnect')).toBeTruthy());
    const page = within(app.onTop());
    expect(page.getByTestId('reconnect')).not.toBeDisabled();
    expect(page.queryByTestId('reconnect-gated')).toBeNull();
    expect(page.queryByTestId('reconnect-anyway')).toBeNull();
    expect(w.money.told).toEqual([]);
  });

  test('$25.00 exactly passes (at or below)', async () => {
    const w = makeWave();
    raised(w, 'wo-4830');
    w.money.answer(fresh('wo-4830', '25.00'));
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('reconnect')).toBeTruthy());
  });

  test('$804.50 owed: the step stops, says why, offers only Leave it off, and the office is told once', async () => {
    const w = makeWave();
    raised(w, 'wo-4830');
    w.money.answer(fresh('wo-4830', '804.50'));
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('reconnect-gated')).toBeTruthy());
    const page = within(app.onTop());
    expect(page.getByTestId('reconnect-gated')).toHaveTextContent(/Still owes \$804\.50\. Leave it off\.$/);
    expect(page.queryByTestId('reconnect')).toBeNull();
    expect(page.queryByTestId('reconnect-anyway')).toBeNull();
    await waitFor(() => expect(w.money.told).toEqual([{ workOrderId: 'wo-4830', reason: 'owes_over_limit', owing: '804.50' }]));
    fireEvent.press(page.getByTestId('leave-off'));
    expect(current(app.ref).name).toBe('FF-15');
  });

  test('a stale figure with no signal cannot pass: Check the balance with signal, no Reconnect', async () => {
    const w = makeWave();
    raised(w, 'wo-4830');
    w.money.hold({ ...fresh('wo-4830', '18.40'), asAt: local(17, 9, 12) });
    w.money.online = false;
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    const page = within(app.onTop());
    expect(page.getByTestId('reconnect-gated')).toHaveTextContent(/Check the balance with signal\.$/);
    expect(page.queryByTestId('reconnect')).toBeNull();
    expect(page.queryByTestId('reconnect-anyway')).toBeNull();
  });

  test('negative — an office-requested reconnect (not raised on site) is unchanged: Reconnect anyway at $804.50', async () => {
    const w = makeWave();
    w.money.answer(fresh('wo-4830', '804.50'));
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('reconnect-anyway')).toBeTruthy());
    expect(within(app.onTop()).queryByTestId('reconnect-gated')).toBeNull();
    expect(w.money.told).toEqual([]);
  });
});

describe('FF-27 · a disconnect raised on site stops with its reason', () => {
  test('the notice period runs until 5 Nov: Leave it on, only Hand back, office told', async () => {
    const w = makeWave();
    raised(w, 'wo-4824');
    w.money.answer(fresh('wo-4824', '241.38', { noticeEndsOn: '2026-11-05', noticeOpen: true, protected: false }));
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('disconnect-held')).toBeTruthy());
    const page = within(app.onTop());
    expect(page.getByTestId('disconnect-held')).toHaveTextContent(/Notice period ends 5 Nov\. Leave it on\.$/);
    expect(page.queryByTestId('disconnect')).toBeNull();
    expect(page.getByTestId('hand-back')).toBeTruthy();
    await waitFor(() => expect(w.money.told.map((x) => x.reason)).toEqual(['notice_open']));
  });

  test('a protected account: Protected account. Leave it on.', async () => {
    const w = makeWave();
    raised(w, 'wo-4824');
    w.money.answer(fresh('wo-4824', '241.38', { noticeEndsOn: null, noticeOpen: false, protected: true }));
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('disconnect-held')).toHaveTextContent(/Protected account\. Leave it on\.$/));
    expect(within(app.onTop()).queryByTestId('disconnect')).toBeNull();
    await waitFor(() => expect(w.money.told.map((x) => x.reason)).toEqual(['protected']));
  });

  test('the balance cleared: FB-013\'s stop, and on a raised job the office is told', async () => {
    const w = makeWave();
    raised(w, 'wo-4824');
    w.money.answer(fresh('wo-4824', '0.00', { noticeEndsOn: null, noticeOpen: false, protected: false }));
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-cleared')).toBeTruthy());
    await waitFor(() => expect(w.money.told.map((x) => x.reason)).toEqual(['balance_cleared']));
  });

  test('nothing holds it: the notice is over, not protected, still owing — Disconnect as before', async () => {
    const w = makeWave();
    raised(w, 'wo-4824');
    w.money.answer(fresh('wo-4824', '241.38', { noticeEndsOn: '2026-10-18', noticeOpen: false, protected: false }));
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    await waitFor(() => expect(within(app.onTop()).getByTestId('disconnect')).toHaveTextContent('Disconnect'));
    expect(within(app.onTop()).queryByTestId('disconnect-held')).toBeNull();
    expect(w.money.told).toEqual([]);
  });
});

describe('FF-15 · a skill gap warns before Start (W3 = C)', () => {
  // Through the REAL sync: the server's bundle carries the advice in the job's
  // details (`mobile._field_raise_details`), the handset keeps it, FF-15 reads it.
  const JOB = 'wo-9028';
  async function syncedJob(advice: { skill: { name: string } | null; has_skill: boolean }) {
    const f = makeServices();
    const server = new FakeServer();
    const card = serverCard({ id: JOB, order_no: 'WO-9028', type: 'Backflow test' });
    server.pages.push({ changes: [{ change: 'upsert', order_id: JOB, at: 't1', job: card }], count: 1, next_cursor: 'c1', has_more: false });
    server.bundles.set(JOB, serverBundle(card, { details: { raised_on_site: true, skill_advice: advice } }));
    const clock = new FakeClock();
    await pullChanges(f.db, server, JOB_DANA, { clock });
    await fetchBundles(f.db, server as unknown as FieldApi, JOB_DANA, { clock });
    await mountJob(f.services, 'FF-15', { params: { workOrderId: JOB }, openJob: JOB });
    return within(jobOnTop('FF-15'));
  }

  test("This job needs Backflow tester (certified). You don't have it.", async () => {
    const top = await syncedJob({ skill: { name: 'Backflow tester (certified)' }, has_skill: false });
    await waitFor(() =>
      expect(top.getByTestId('job-skill-missing')).toHaveTextContent("This job needs Backflow tester (certified). You don't have it."),
    );
  });

  test('negative — holding the skill shows nothing', async () => {
    const top = await syncedJob({ skill: { name: 'Water II' }, has_skill: true });
    await waitFor(() => expect(top.getByTestId('job-state')).toBeTruthy());
    expect(top.queryByTestId('job-skill-missing')).toBeNull();
  });
});
