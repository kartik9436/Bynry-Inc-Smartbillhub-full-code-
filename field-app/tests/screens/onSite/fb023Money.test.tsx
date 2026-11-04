/**
 * FB-023 (decision log 2026-10-31, PO F1–F6) — what the technician sees about
 * money on a field job, proved on a handset built ONLY through the real sync
 * path: the change feed (`pullChanges` → `applyChangesPage`), the job bundle
 * (`fetchBundles`) and the real money door (`httpMoneyPort` over the job's
 * `GET work/mobile/jobs/{id}/money`, mapped by `moneyFromWire`). Nothing here
 * writes a technician's employment, a job's account or a money figure into the
 * handset database by hand — the shared fixture did, which is how every
 * earlier money test passed while no real phone ever showed a balance
 * (DEF-FLD-10789, DEF-FLD-10790).
 *
 * Figures are test data (B14 rule 37): Aaron Bruner's $241.38 disconnect.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import * as workOrderQ from '../../../src/db/queries/workOrder';
import { scoped } from '../../../src/db/scoped';
import { fakeDevicePorts } from '../../../src/screens/onSite/ports';
import { unwiredSignature } from '../../../src/screens/closing/signature';
import { unwiredScanner } from '../../../src/screens/raise/scanner';
import { httpMoneyPort, moneyFromWire, storeMoneyMemory } from '../../../src/session/fieldDoors';
import { pullChanges } from '../../../src/sync/delta';
import { fetchBundles } from '../../../src/sync/extras';
import type { FieldApi, WireBundle, WireJobDetails, WireJobMoney } from '../../../src/sync/fieldApi';
import type { JobCard } from '../../../src/sync/transport';
import { FakeClock, idSource, openStore } from '../../db/support/fixtures';
import { FakeServer, serverBundle, serverCard } from '../../sync/support/fakeServer';
import { DANA as JOB_DANA, makeServices } from '../theJob/fixture';
import { mountJob, onTop as jobOnTop } from '../theJob/harness';
import { current, DANA, NOW, openScreen, PATEL, type Wave } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const JOB = 'wo-9001';

const card = (): JobCard => serverCard({ id: JOB, order_no: 'WO-9001', type: 'Disconnect — non-payment' });

function bundle(over: { details?: WireJobDetails | null; account?: boolean } = {}): WireBundle {
  const b = serverBundle(card(), {
    tasks: [
      { id: 't-1', seq: 1, title: 'Photograph the meter', ticked_at: '2026-10-20T09:00:00+00:00' },
      { id: 't-2', seq: 2, title: 'Close the valve', money_fresh_minutes: 5 },
    ],
    customer: { name: 'Aaron Bruner', phone: '(512) 555-0188', account_no: 'A-10588' },
    ...(over.account === false ? {} : { account_id: 'acc-10588' }),
    ...('details' in over ? { details: over.details } : {}),
  });
  return b;
}

const money = (over: Partial<WireJobMoney> = {}): WireJobMoney => ({
  order_no: 'WO-9001',
  as_at: NOW.toISOString(),
  fresh_minutes: 5,
  withheld: null,
  account_no: 'A-10588',
  owing: { amount: '241.3800', display: '241.38', currency: 'USD' },
  balance: { amount: '241.3800', display: '241.38', currency: 'USD' },
  currency: 'USD',
  latest_payment: null,
  charges: [],
  disconnect: null,
  unavailable: [],
  ...over,
});

const POSTED = money({
  owing: { amount: '0.0000', display: '0.00', currency: 'USD' },
  balance: { amount: '0.0000', display: '0.00', currency: 'USD' },
  latest_payment: { amount: '241.3800', display: '241.38', currency: 'USD', state: 'posted', posted_at: '2026-10-20T09:40:00', cleared_at: null, method: 'Card' },
});

interface Synced extends Wave {
  calls: string[];
  setAnswer(a: WireJobMoney | Error): void;
}

/**
 * A handset that has synced once: the feed (with or without the server's
 * `technician.employment`), then the bundle. The money port is the REAL
 * one over a fake `jobMoney`; `db` is reused to model an app restart.
 */
async function synced(opts: { tech?: string; employment?: 'employee' | 'contractor' | null; details?: WireJobDetails | null; account?: boolean; db?: Wave['db'] } = {}): Promise<Synced> {
  const tech = opts.tech ?? DANA;
  const clock = new FakeClock(NOW.getTime());
  const db = opts.db ?? openStore('silver-creek', undefined, clock);
  const server = new FakeServer();
  const employment = opts.employment === undefined ? 'employee' : opts.employment;
  server.pages.push({
    changes: [{ change: 'upsert', order_id: JOB, at: 't1', job: card() }],
    count: 1,
    next_cursor: 'c1',
    has_more: false,
    ...(employment ? { technician: { employment } } : {}),
  });
  server.bundles.set(JOB, bundle({ ...('details' in opts ? { details: opts.details } : {}), account: opts.account }));
  await pullChanges(db, server, tech, { clock });
  await fetchBundles(db, server as unknown as FieldApi, tech, { clock });

  const calls: string[] = [];
  let answer: WireJobMoney | Error = money();
  const api = {
    jobMoney: async (id: string) => {
      calls.push(id);
      if (answer instanceof Error) throw answer;
      return answer;
    },
  } as unknown as FieldApi;
  const port = httpMoneyPort(api, storeMoneyMemory(db, () => clock.now()));
  const device = fakeDevicePorts({ photos: [], words: [], location: null });
  return {
    db,
    clock,
    money: port as never,
    device,
    data: { db, technicianId: tech, newId: idSource('k'), clock, money: port, device, scanner: unwiredScanner, signature: unwiredSignature },
    calls,
    setAnswer: (a) => {
      answer = a;
    },
  };
}

describe('F3 — the phone learns employee / contractor from the real feed', () => {
  test('an employee, after a real sync, sees the balance — read on open, by the JOB', async () => {
    const w = await synced();
    const app = await openScreen(w, 'FF-25', { workOrderId: JOB });
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-amount')).toHaveTextContent('$241.38'));
    expect(w.calls).toEqual([JOB]);
    expect(screen.queryByTestId('header-chip')).toBeNull();
    expect(workOrderQ.getMine(scoped(w.db, DANA), JOB)?.account_id).toBe('acc-10588');
  });

  test('a contractor sees the name and no money, and nothing is asked', async () => {
    const w = await synced({ tech: PATEL, employment: 'contractor' });
    const app = await openScreen(w, 'FF-25', { workOrderId: JOB }, { login: 'r.patel' });
    const page = within(app.onTop());
    expect(page.getByText('Aaron Bruner')).toBeTruthy();
    expect(page.queryByTestId('balance-card')).toBeNull();
    expect(screen.getByTestId('header-chip')).toHaveTextContent('Contractor');
    expect(w.calls).toEqual([]);
  });

  test('an older server that names no role: money hidden, and no untrue Contractor chip', async () => {
    const w = await synced({ employment: null });
    const app = await openScreen(w, 'FF-25', { workOrderId: JOB });
    expect(within(app.onTop()).queryByTestId('balance-card')).toBeNull();
    expect(screen.queryByTestId('header-chip')).toBeNull();
    expect(w.calls).toEqual([]);
  });
});

describe('F1 — live on open, the last figure with its age offline', () => {
  test('Check now on a synced job asks the job door again — even when the bundle names no account', async () => {
    const w = await synced({ account: false });
    const app = await openScreen(w, 'FF-27', { workOrderId: JOB });
    await waitFor(() => expect(w.calls).toEqual([JOB]));
    await act(async () => {
      fireEvent.press(within(app.onTop()).getByTestId('check-now'));
    });
    expect(w.calls).toEqual([JOB, JOB]);
  });

  test('offline after a restart: the kept figure, with its age, and no ask', async () => {
    const first = await synced();
    const app = await openScreen(first, 'FF-25', { workOrderId: JOB });
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-amount')).toHaveTextContent('$241.38'));
    app.unmount();
    // A restart: same handset store, a NEW port with nothing in memory, 3 hours on.
    const again = await synced({ db: first.db });
    again.clock.advance(3 * 3600_000);
    const later = await openScreen(again, 'FF-25', { workOrderId: JOB }, { connection: 'offline' });
    const page = within(later.onTop());
    expect(page.getByTestId('balance-amount')).toHaveTextContent('$241.38');
    expect(page.getByText('Balance is 3 hours old')).toBeTruthy();
    expect(again.calls).toEqual([]);
  });
});

describe('F2 — posted counts as paid and never reads Cleared', () => {
  test('the wire mapping keeps the state and dates a posted payment when it was posted', () => {
    const r = moneyFromWire(JOB, POSTED)!;
    expect(r.latestPayment).toEqual({ amount: '241.3800', at: '2026-10-20T09:40:00', state: 'posted', method: 'Card' });
  });

  test('FF-25 says Posted and FF-26 says Payment posted — never Cleared', async () => {
    const w = await synced();
    w.setAnswer(POSTED);
    const app = await openScreen(w, 'FF-25', { workOrderId: JOB });
    await waitFor(() => expect(within(app.onTop()).getByTestId('payment-state')).toHaveTextContent('Posted'));
    expect(within(app.onTop()).queryByText('Cleared')).toBeNull();
    app.unmount();
    const restore = await openScreen(w, 'FF-26', { workOrderId: JOB });
    await waitFor(() => expect(within(restore.onTop()).getByTestId('cleared-card')).toBeTruthy());
    expect(within(restore.onTop()).getByText('Payment posted')).toBeTruthy();
    expect(within(restore.onTop()).queryByText('Payment cleared')).toBeNull();
  });

  test('FF-27: a posted payment stops the step; the close carries "posted"', async () => {
    const w = await synced();
    w.setAnswer(POSTED);
    const app = await openScreen(w, 'FF-27', { workOrderId: JOB });
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-cleared')).toBeTruthy());
    expect(within(app.onTop()).getByTestId('posted-not-cleared')).toHaveTextContent('Posted, not cleared.');
    fireEvent.press(within(app.onTop()).getByTestId('close-payment-received'));
    const sent = current(app.ref).params.paymentReceived as { latest_payment: { state: string } };
    expect(current(app.ref).name).toBe('FF-34');
    expect(sent.latest_payment.state).toBe('posted');
  });
});

describe('F4 — the Balance & payments tick hides the display, never the stop', () => {
  test('tick off: no balance card on FF-25 or FF-27, and a cleared balance STILL stops the disconnect', async () => {
    const w = await synced({ details: { show_balance_payments: false } });
    w.setAnswer(POSTED);
    const customer = await openScreen(w, 'FF-25', { workOrderId: JOB });
    await waitFor(() => expect(w.calls.length).toBe(1));
    expect(within(customer.onTop()).queryByTestId('balance-card')).toBeNull();
    customer.unmount();
    const app = await openScreen(w, 'FF-27', { workOrderId: JOB });
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-cleared')).toHaveTextContent(/Balance cleared\. Do not disconnect\.$/));
    expect(within(app.onTop()).queryByTestId('balance-card')).toBeNull();
    expect(within(app.onTop()).getByTestId('close-payment-received')).toBeTruthy();
  });
});

describe('F5 — plan and notice on a disconnect job', () => {
  test('behind on the plan, and the 48-hour notice with its date and amount', async () => {
    const w = await synced();
    w.setAnswer(
      money({
        disconnect: {
          plan: { status: 'behind', missed: 1 },
          notice: { tier: 'tier_3_48_hour', issued_on: '2026-10-16', amount: { amount: '241.3800', display: '241.38', currency: 'USD' } },
        },
      }),
    );
    const app = await openScreen(w, 'FF-27', { workOrderId: JOB });
    await waitFor(() => expect(within(app.onTop()).getByTestId('plan-status')).toHaveTextContent('Behind'));
    expect(within(app.onTop()).getByTestId('disconnect-notice')).toHaveProp(
      'accessibilityLabel',
      expect.stringContaining('48-hour notice · 16 Oct · $241.38'),
    );
  });
});

describe('F6 — the four ticks the phone used to ignore', () => {
  const OFF = { show_account_summary: false, show_asset_card: false, show_access_notes: false, show_appointment: false };

  test('FF-25: no account number, no call, no meter card, no visit window', async () => {
    const on = await synced();
    const shown = await openScreen(on, 'FF-25', { workOrderId: JOB });
    expect(within(shown.onTop()).getByText('Account A-10588')).toBeTruthy();
    expect(within(shown.onTop()).getByTestId('service-card')).toBeTruthy();
    expect(within(shown.onTop()).getByTestId('call')).toBeTruthy();
    shown.unmount();

    const w = await synced({ details: OFF });
    const app = await openScreen(w, 'FF-25', { workOrderId: JOB });
    const page = within(app.onTop());
    expect(page.getByText('Aaron Bruner')).toBeTruthy();
    expect(page.queryByText('Account A-10588')).toBeNull();
    expect(page.queryByTestId('call')).toBeNull();
    expect(page.queryByTestId('service-card')).toBeNull();
    expect(page.queryByText(/WO-9001 · \d\d:\d\d–/)).toBeNull();
  });

  test('FF-28: the access notes go when their tick is off', async () => {
    const on = await synced();
    const shown = await openScreen(on, 'FF-28', { workOrderId: JOB });
    expect(within(shown.onTop()).getByTestId('premise-notes')).toBeTruthy();
    shown.unmount();
    const w = await synced({ details: { show_access_notes: false } });
    const app = await openScreen(w, 'FF-28', { workOrderId: JOB });
    expect(within(app.onTop()).queryByTestId('premise-notes')).toBeNull();
  });

  test('FF-15: no customer name or account, no asset card, no window — the address and Navigate stay', async () => {
    const f = makeServices();
    const server = new FakeServer();
    server.pages.push({ changes: [{ change: 'upsert', order_id: JOB, at: 't1', job: card() }], count: 1, next_cursor: 'c1', has_more: false });
    server.bundles.set(JOB, bundle({ details: OFF }));
    const clock = new FakeClock();
    await pullChanges(f.db, server, JOB_DANA, { clock });
    await fetchBundles(f.db, server as unknown as FieldApi, JOB_DANA, { clock });
    await mountJob(f.services, 'FF-15', { params: { workOrderId: JOB }, openJob: JOB });
    const top = within(jobOnTop('FF-15'));
    expect(top.queryByTestId('job-customer-name')).toBeNull();
    expect(top.queryByTestId('job-customer-account')).toBeNull();
    expect(top.queryByTestId('job-asset')).toBeNull();
    expect(top.queryByTestId('door-FF-39')).toBeNull();
    expect(top.getByText('1400 Elm Street')).toBeTruthy();
    expect(top.getByTestId('job-navigate')).toBeEnabled();
  });
});
