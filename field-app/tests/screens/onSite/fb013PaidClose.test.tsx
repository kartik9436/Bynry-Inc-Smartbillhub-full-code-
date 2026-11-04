/**
 * FB-013 (DEF-FLD-10642 / DEF-WRK-10641) — PO rulings of 2026-10-28:
 *   (a) a FRESH read showing the balance cleared STOPS the money-check step;
 *       R17 (stale is warned, never blocked) is unchanged;
 *   (b) at the stopped step: "Close — payment received" and "Hand back to
 *       office"; the Close screen offers "Not done — payment received" with a
 *       prefilled, editable remark, and the money the phone saw rides on the
 *       close; offered ONLY on a fresh cleared read;
 *   (c) R18 — the stop keys off the step's `money_fresh_minutes` only.
 *
 * Red proof (law 7): every case here was run against the code before FB-013
 * and failed (no `balance-cleared`, no `close-payment-received`, no paid
 * outcome, and the bundle dropped `money_fresh_minutes`).
 */
import { fireEvent, waitFor, within } from '@testing-library/react-native';

import * as woItemQ from '../../../src/db/queries/woItem';
import * as outboxQ from '../../../src/db/queries/outbox';
import { deviceWide, scoped } from '../../../src/db/scoped';
import { applyChangesPage } from '../../../src/sync/delta';
import { applyBundle } from '../../../src/sync/extras';
import type { WireBundle } from '../../../src/sync/fieldApi';
import { sendPending } from '../../../src/sync/outbox';
import { TransportError, type JobCard } from '../../../src/sync/transport';
import { FakeClock, openStore, steadyRandom } from '../../db/support/fixtures';
import { FakeServer } from '../../sync/support/fakeServer';
import { captured, current, DANA, local, makeWave, NOW, openScreen } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const owing = { workOrderId: 'wo-4824', currency: 'USD', balance: '241.38', asAt: local(17, 9, 12) };
const paidNow = {
  ...owing,
  balance: '0.00',
  asAt: NOW.toISOString(),
  latestPayment: { amount: '241.38', at: local(20, 9, 40), state: 'cleared' as const },
};
const SNAPSHOT = {
  task_id: 't-24-3',
  balance: '0.00',
  currency: 'USD',
  as_at: NOW.toISOString(),
  checked_at: NOW.toISOString(),
  latest_payment: { amount: '241.38', at: local(20, 9, 40), state: 'cleared' },
};

describe('FF-27 · a fresh cleared balance stops the step (ruling a)', () => {
  test('Check now answers $0.00: the step is stopped, with Close — payment received and Hand back to office', async () => {
    const w = makeWave();
    w.money.hold(owing).answer(paidNow);
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    fireEvent.press(within(app.onTop()).getByTestId('check-now'));
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-cleared')).toBeTruthy());
    const page = within(app.onTop());
    expect(page.getByTestId('balance-cleared')).toHaveTextContent(/Balance cleared\. Do not disconnect\.$/);
    expect(page.queryByTestId('disconnect')).toBeNull();
    expect(page.getByTestId('close-payment-received')).toHaveTextContent('Close — payment received');
    expect(page.getByTestId('hand-back')).toHaveTextContent('Hand back to office');
  });

  test('Close — payment received opens FF-34 carrying what the phone saw', async () => {
    const w = makeWave();
    w.money.hold(paidNow);
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    fireEvent.press(within(app.onTop()).getByTestId('close-payment-received'));
    expect(current(app.ref)).toEqual({ name: 'FF-34', params: { workOrderId: 'wo-4824', paymentReceived: SNAPSHOT } });
  });

  test('Hand back to office opens the hand-back screen for the job', async () => {
    const w = makeWave();
    w.money.hold(paidNow);
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    fireEvent.press(within(app.onTop()).getByTestId('hand-back'));
    expect(current(app.ref)).toEqual({ name: 'FF-58', params: { workOrderId: 'wo-4824' } });
    expect(`FF-27 → ${current(app.ref).name}`).toBe('FF-27 → FF-58');
  });

  test('negative — a STALE $0.00 (no signal) is only the R17 warning: no stop, no paid close', async () => {
    const w = makeWave();
    w.money.hold({ ...paidNow, asAt: local(17, 9, 12) });
    w.money.online = false;
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    const page = within(app.onTop());
    expect(page.queryByTestId('balance-cleared')).toBeNull();
    expect(page.queryByTestId('close-payment-received')).toBeNull();
    expect(page.getByTestId('unverified-step')).toBeTruthy();
    expect(page.getByTestId('disconnect')).toHaveTextContent('Disconnect anyway');
    expect(page.getByTestId('disconnect')).not.toBeDisabled();
  });

  test('negative — the bar is the STEP\'s: a $0.00 read 7 minutes ago on a 5-minute step is stale', async () => {
    const w = makeWave();
    w.money.hold({ ...paidNow, asAt: new Date(NOW.getTime() - 7 * 60_000).toISOString() });
    w.money.online = false;
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    expect(within(app.onTop()).queryByTestId('close-payment-received')).toBeNull();
  });

  test('negative (R18) — a step with no payment check never stops, even at $0.00', async () => {
    const w = makeWave();
    w.money.hold(paidNow);
    woItemQ.upsert(scoped(w.db, DANA), { id: 't-24-3', workOrderId: 'wo-4824', kind: 'task', position: 3, label: 'Close the valve' }, local(20, 7));
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    const page = within(app.onTop());
    expect(page.queryByTestId('balance-cleared')).toBeNull();
    expect(page.getByTestId('disconnect')).toHaveTextContent('Disconnect');
  });
});

describe('FF-34 · Not done — payment received (ruling b)', () => {
  test('offered and chosen only with a paid snapshot; the remark is prefilled and editable; the snapshot rides on the close', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824', paymentReceived: SNAPSHOT });
    const page = within(app.onTop());
    expect(page.getAllByRole('radio').map((r) => r.props.accessibilityLabel)).toContain('Not done — payment received');
    expect(page.getByTestId('outcome-not_done_payment_received')).toHaveProp('accessibilityState', { checked: true, selected: true });
    const remark = page.getByTestId('remark-input');
    expect(remark.props.value).toBe('Customer has paid. Not disconnected.');
    fireEvent.changeText(remark, 'Paid at the counter. Not disconnected.');
    fireEvent.press(within(app.onTop()).getByTestId('close-job'));
    const close = captured(w.db).find((a) => a.kind === 'close')!;
    expect(close.body).toMatchObject({
      outcome: 'not_done_payment_received',
      field_data: { reason: 'Paid at the counter. Not disconnected.', money_seen: SNAPSHOT },
    });
    expect((close.body.field_data as Record<string, unknown>).required_photos_missing).toBeUndefined();
  });

  test('negative — without a paid snapshot the outcome is not offered', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824' });
    const page = within(app.onTop());
    expect(page.getAllByRole('radio').map((r) => r.props.accessibilityLabel)).not.toContain('Not done — payment received');
    expect(page.queryByTestId('remark')).toBeNull();
  });

  test('the paid close queues offline and is sent once the signal returns', async () => {
    const w = makeWave();
    const app = await openScreen(w, 'FF-34', { workOrderId: 'wo-4824', paymentReceived: SNAPSHOT });
    fireEvent.press(within(app.onTop()).getByTestId('close-job'));
    // The job's accept goes through its own door (the FakeServer serves
    // batches only); only the close is in question here, so it is answered.
    for (const row of captured(w.db).filter((a) => a.kind === 'job_accept')) {
      outboxQ.settle(deviceWide(w.db, 'receipt'), row.id, 'accepted', NOW.toISOString(), null);
    }
    const server = new FakeServer();
    const realSend = server.sendJobBatch.bind(server);
    server.sendJobBatch = async () => {
      throw new TransportError('network', 'no signal');
    };
    const opts = { clock: new FakeClock(NOW.getTime()), tokens: { tokenFor: (t: string) => `token-of-${t}` }, random: steadyRandom };
    await sendPending(w.db, server, opts);
    expect(server.applied).toEqual([]);
    expect(captured(w.db).find((a) => a.kind === 'close')?.state).toBe('pending');
    server.sendJobBatch = realSend;
    opts.clock.advanceDays(1);
    await sendPending(w.db, server, opts);
    const sent = server.applied.filter((a) => a.kind === 'close');
    expect(sent).toHaveLength(1);
    expect(sent[0]!.payload).toMatchObject({ outcome: 'not_done_payment_received', field_data: { money_seen: SNAPSHOT } });
  });
});

describe('the job bundle keeps the step\'s payment check (DEF-FLD-10642)', () => {
  test('money_fresh_minutes and money_charge_code land in the task detail', () => {
    const clock = new FakeClock();
    const db = openStore('north', undefined, clock);
    const card = {
      id: 'wo-29', order_no: 'WO-0029', type: 'Disconnection', premise: { id: 'p-29', premise_no: 'PR-29', address: '12 Elm St' },
      window_start: null, window_end: null, due_at: null, est_minutes: 30, priority: { code: 'P2', rank: 2 },
      state: 'scheduled', dispatch_state: 'SCHEDULED', access_notes: '', hazards: '', gate_code: '',
    } as unknown as JobCard;
    applyChangesPage(db, 'dana', { changes: [{ change: 'upsert', order_id: 'wo-29', at: 't', job: card }], count: 1, next_cursor: 'c0', has_more: false }, clock.now());
    const bundle = {
      order_id: 'wo-29', order_no: 'WO-0029', template_id: 'tpl-1', template_version: 1, safety: [], readings: [], materials: [],
      tasks: [
        { id: 't-1', seq: 1, title: 'Photograph the meter' },
        { id: 't-2', seq: 2, title: 'Close the valve', money_fresh_minutes: 5, money_charge_code: null },
        { id: 't-3', seq: 3, title: 'Reconnect', money_fresh_minutes: 15, money_charge_code: 'CC-RECON' },
      ],
    } as unknown as WireBundle;
    applyBundle(db, 'dana', bundle, clock.now());
    const detail = (id: string) =>
      JSON.parse(woItemQ.listForOrder(scoped(db, 'dana'), 'wo-29', 'task').find((t) => t.id === id)?.detail ?? '{}');
    expect(detail('t-1')).not.toHaveProperty('money_fresh_minutes');
    expect(detail('t-2')).toMatchObject({ money_fresh_minutes: 5 });
    expect(detail('t-2')).not.toHaveProperty('money_charge_code');
    expect(detail('t-3')).toMatchObject({ money_fresh_minutes: 15, money_charge_code: 'CC-RECON' });
  });
});
