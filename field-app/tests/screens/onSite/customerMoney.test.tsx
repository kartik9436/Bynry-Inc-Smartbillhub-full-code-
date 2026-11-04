/**
 * T-20 money screens — FF-25 Customer, FF-26 Restoration, FF-27 Disconnect,
 * FF-61 Reconnect — mounted under the real navigator from the fixture
 * handset (US-FLD-012, US-FLD-025, US-FLD-075; R16, R17, R26, R111).
 *
 * Red proof (law 7): with `seesMoney` returning true for everyone, the
 * contractor case (FF-25 TC-3) fails; with `isStale`'s `>` flipped to `<`,
 * E2E-11 fails.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import { formatMoney, formatUnitPrice } from '../../../src/screens/onSite/format';
import { current, local, makeWave, NOW, openScreen, PATEL } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

const ago = (ms: number) => new Date(NOW.getTime() - ms).toISOString();

describe('FF-25 Customer', () => {
  test('TC-1: an employee sees who, where, the meter, this visit, and the balance with its age', async () => {
    const w = makeWave();
    w.money.hold({ workOrderId: 'wo-4822', currency: 'USD', balance: '241.3800', asAt: ago(40_000) });
    const app = await openScreen(w, 'FF-25', { workOrderId: 'wo-4822' });
    const page = within(app.onTop());
    expect(page.getByText('Sarah Miller')).toBeTruthy();
    expect(page.getByText('1400 Elm Street · Unit A')).toBeTruthy();
    expect(page.getByText('Austin, TX 78704')).toBeTruthy();
    expect(page.getByText('Account A-10432')).toBeTruthy();
    expect(page.getByText('W-4471')).toBeTruthy();
    expect(page.getByText('Meter exchange · 5/8"')).toBeTruthy();
    expect(page.getByText('WO-4822 · 08:00–12:00')).toBeTruthy();
    expect(page.getByTestId('balance-amount')).toHaveTextContent('$241.38');
    expect(page.getByText('Read 40 seconds ago')).toBeTruthy();
    expect(screen.queryByTestId('header-chip')).toBeNull();
  });

  test('TC-3 negative: a contractor sees the name and not the money (R26)', async () => {
    const w = makeWave({ tech: PATEL });
    w.money.hold({ workOrderId: 'wo-4822', currency: 'USD', balance: '241.38', asAt: ago(40_000) });
    const app = await openScreen(w, 'FF-25', { workOrderId: 'wo-4822' }, { login: 'r.patel' });
    const page = within(app.onTop());
    expect(page.getByText('Sarah Miller')).toBeTruthy();
    expect(page.queryByTestId('balance-card')).toBeNull();
    expect(page.queryByText('$241.38')).toBeNull();
    expect(screen.getByTestId('header-chip')).toHaveTextContent('Contractor');
    expect(w.money.checks).toBe(0);
  });

  test('TC-4 negative: nothing on the screen takes or stages money (R16)', async () => {
    const w = makeWave();
    w.money.hold({ workOrderId: 'wo-4822', currency: 'USD', balance: '241.38', asAt: ago(10 * 60_000) });
    const app = await openScreen(w, 'FF-25', { workOrderId: 'wo-4822' });
    const labels = within(app.onTop())
      .getAllByRole('button')
      .map((b) => String(b.props.accessibilityLabel));
    expect(labels.join('|')).not.toMatch(/pay|tender|collect|card/i);
  });

  test('TC-5: amounts at two places, a unit price up to four (R20)', () => {
    expect(formatMoney('241.3800')).toBe('$241.38');
    expect(formatMoney('241.385')).toBe('$241.39');
    expect(formatMoney('1234567.004')).toBe('$1,234,567.00');
    expect(formatMoney('0.0000')).toBe('$0.00');
    expect(formatUnitPrice('0.0425')).toBe('$0.0425');
    expect(formatUnitPrice('8.9375')).toBe('$8.9375');
    expect(formatUnitPrice('0.1')).toBe('$0.10');
    expect(() => formatMoney('1e3')).toThrow();
  });

  test('doors: back to the job, Restoration and Disconnect, carrying the job', async () => {
    for (const [testID, to] of [
      ['door-FF-15', 'FF-15'],
      ['door-FF-26', 'FF-26'],
      ['door-FF-27', 'FF-27'],
    ] as const) {
      const w = makeWave();
      const app = await openScreen(w, 'FF-25', { workOrderId: 'wo-4822' });
      fireEvent.press(within(app.onTop()).getByTestId(testID));
      expect(current(app.ref)).toEqual({ name: to, params: { workOrderId: 'wo-4822' } });
      app.unmount();
    }
  });
});

describe('FF-26 Restoration', () => {
  test('TC-2 (E2E-13): payment cleared, balance now $0.00, restore within 3:12', async () => {
    const w = makeWave();
    w.money.hold({
      workOrderId: 'wo-4826',
      currency: 'USD',
      balance: '0.00',
      asAt: local(20, 10, 2),
      latestPayment: { amount: '241.38', at: local(18, 16, 4), state: 'cleared' as const, method: 'Card' },
    });
    const app = await openScreen(w, 'FF-26', { workOrderId: 'wo-4826' });
    const page = within(app.onTop());
    expect(page.getByTestId('cleared-amount')).toHaveTextContent('$241.38');
    expect(page.getByText('Card · 18 Oct 16:04 · checked 10:02')).toBeTruthy();
    expect(page.getByTestId('balance-now')).toHaveProp('accessibilityLabel', 'Balance now, $0.00');
    expect(page.getByTestId('countdown')).toHaveTextContent('3:12');
    expect(page.getByText('by 13:12 today')).toBeTruthy();
    expect(page.getByText('Photo')).toBeTruthy(); // drawn upper-case by the chip's style
    fireEvent.press(page.getByTestId('door-FF-17'));
    expect(current(app.ref)).toEqual({ name: 'FF-17', params: { workOrderId: 'wo-4826' } });
  });

  test('a contractor sees the job and the countdown, not the cleared payment (R26)', async () => {
    const w = makeWave({ tech: PATEL });
    w.money.hold({ workOrderId: 'wo-4826', currency: 'USD', balance: '0.00', asAt: local(20, 10), latestPayment: { amount: '241.38', at: local(18, 16), state: 'cleared' as const } });
    const app = await openScreen(w, 'FF-26', { workOrderId: 'wo-4826' }, { login: 'r.patel' });
    const page = within(app.onTop());
    expect(page.queryByTestId('cleared-card')).toBeNull();
    expect(page.getByTestId('countdown')).toHaveTextContent('3:12');
  });
});

describe('FF-27 Disconnect · stale money', () => {
  const stale = { workOrderId: 'wo-4824', currency: 'USD', balance: '241.38', asAt: local(17, 9, 12) };

  test('TC-1 (E2E-11): Check now turns the amber balance green, $0.00, and the step is stopped (FB-013)', async () => {
    const w = makeWave();
    w.money.hold(stale).answer({ ...stale, balance: '0.00', asAt: NOW.toISOString() });
    // Opened with no signal (FB-023 F1: online, the screen checks on open) —
    // the kept 3-day-old figure is what the technician first sees.
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' }, { connection: 'offline' });
    const page = within(app.onTop());
    expect(page.getByText('Balance is 3 days old')).toBeTruthy();
    expect(page.getByTestId('balance-amount')).toHaveTextContent('$241.38');
    expect(page.getByText('Read 17 Oct 09:12 · must be under 5 minutes old')).toBeTruthy();
    expect(page.getByTestId('unverified-step')).toHaveTextContent(/3 · Close the valve\. Recorded as unverified\.$/);
    expect(page.getByTestId('disconnect')).toHaveTextContent('Disconnect anyway');
    expect(app.onTop()).toBeTruthy();
    fireEvent.press(page.getByTestId('check-now'));
    await waitFor(() => expect(within(app.onTop()).getByTestId('balance-amount')).toHaveTextContent('$0.00'));
    const after = within(app.onTop());
    expect(after.getByText('Read 0 seconds ago')).toBeTruthy();
    expect(after.queryByTestId('unverified-step')).toBeNull();
    expect(after.queryByTestId('disconnect')).toBeNull();
    // FB-013 (PO 2026-10-28) supersedes the board's *Close — customer paid*:
    // a fresh cleared balance STOPS the step (fb013PaidClose.test.tsx).
    expect(after.getByTestId('balance-cleared')).toHaveTextContent(/Balance cleared\. Do not disconnect\.$/);
    expect(after.getByTestId('close-payment-received')).toHaveTextContent('Close — payment received');
    // The drawn title: the native header is configured with the job's number.
    expect(screen.UNSAFE_root.findAll((n: { props: { title?: string } }) => n.props.title === 'WO-4824').length).toBeGreaterThan(0);
  });

  test('TC-2 (E2E-12) + TC-4: no signal, three days old — warned, never blocked, and proceeding is recorded as unverified', async () => {
    const w = makeWave();
    w.money.hold(stale);
    w.money.online = false;
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    fireEvent.press(within(app.onTop()).getByTestId('check-now'));
    await waitFor(() => expect(within(app.onTop()).getByText('No answer. Try again.')).toBeTruthy());
    const button = within(app.onTop()).getByTestId('disconnect');
    expect(button).not.toBeDisabled();
    fireEvent.press(button);
    expect(current(app.ref)).toEqual({
      name: 'FF-34',
      params: { workOrderId: 'wo-4824', moneyUnverified: { balance: '241.38', as_at: stale.asAt } },
    });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-27 → ${current(app.ref).name}`).toBe('FF-27 → FF-34');
  });

  test('TC-3 negative: a step with no freshness on its template never warns (R18)', async () => {
    const w = makeWave();
    w.money.hold(stale);
    // Re-seed step 3 without a declared freshness.
    const { scoped } = jest.requireActual('../../../src/db/scoped');
    const woItemQ = jest.requireActual('../../../src/db/queries/woItem');
    woItemQ.upsert(scoped(w.db, 'tech-dana'), { id: 't-24-3', workOrderId: 'wo-4824', kind: 'task', position: 3, label: 'Close the valve' }, local(20, 7));
    const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
    const page = within(app.onTop());
    expect(page.queryByTestId('unverified-step')).toBeNull();
    expect(page.getByTestId('disconnect')).toHaveTextContent('Disconnect');
    expect(page.getByTestId('disconnect')).not.toHaveTextContent('anyway');
    fireEvent.press(page.getByTestId('disconnect'));
    expect(current(app.ref).params).toEqual({ workOrderId: 'wo-4824' });
  });
});

describe('FF-61 Before you reconnect', () => {
  const both = {
    workOrderId: 'wo-4830',
    currency: 'USD',
    balance: '0.00',
    asAt: new Date(NOW.getTime() - 30_000).toISOString(),
    arrearsBefore: '312.40',
    latestPayment: { amount: '312.40', at: local(20, 9, 40), state: 'cleared' as const },
    reconnectFee: { amount: '45.00', chargedAt: local(18, 10), paid: false },
  };

  test('TC-1: two things, not one — arrears $0.00, the fee $45.00 unpaid', async () => {
    const w = makeWave();
    w.money.hold(both);
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    const page = within(app.onTop());
    expect(page.getByText('Two things, not one')).toBeTruthy();
    expect(page.getByTestId('arrears-amount')).toHaveTextContent('$0.00');
    expect(page.getByText('Was $312.40 · paid 09:40 today')).toBeTruthy();
    expect(page.getByTestId('fee-amount')).toHaveTextContent('$45.00');
    expect(page.getByText('Charged 18 Oct · not paid')).toBeTruthy();
    expect(page.getByTestId('fee-case')).toHaveTextContent('Arrears cleared. Fee not paid.');
    expect(page.getByText('Read 30 seconds ago')).toBeTruthy();
  });

  test('TC-2: Reconnect anyway is recorded as reconnected with the fee outstanding', async () => {
    const w = makeWave();
    w.money.hold(both);
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    fireEvent.press(within(app.onTop()).getByTestId('reconnect-anyway'));
    expect(current(app.ref)).toEqual({ name: 'FF-34', params: { workOrderId: 'wo-4830', feeOutstanding: { amount: '45.00' } } });
  });

  test('TC-3 negative: both read over five minutes ago — warned with Check now, never blocked', async () => {
    const w = makeWave();
    w.money.hold({ ...both, asAt: ago(11 * 60_000) });
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    const page = within(app.onTop());
    expect(page.getByText('Read 11 minutes ago')).toBeTruthy();
    expect(page.getByTestId('check-now')).not.toBeDisabled();
    expect(page.getByTestId('reconnect-anyway')).not.toBeDisabled();
    fireEvent.press(page.getByTestId('leave-off'));
    expect(current(app.ref)).toEqual({ name: 'FF-15', params: { workOrderId: 'wo-4830' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-61 → ${current(app.ref).name}`).toBe('FF-61 → FF-15');
  });

  test('fee paid and arrears clear and fresh: a plain Reconnect', async () => {
    const w = makeWave();
    w.money.hold({ ...both, reconnectFee: { amount: '45.00', chargedAt: local(18, 10), paid: true } });
    const app = await openScreen(w, 'FF-61', { workOrderId: 'wo-4830' });
    const page = within(app.onTop());
    expect(page.queryByTestId('not-blocked')).toBeNull();
    fireEvent.press(page.getByTestId('reconnect'));
    expect(current(app.ref)).toEqual({ name: 'FF-34', params: { workOrderId: 'wo-4830' } });
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`FF-61 → ${current(app.ref).name}`).toBe('FF-61 → FF-34');
  });
});

test('with no server the money port refuses in words, and the screen still lets the job go on', async () => {
  const { unwiredMoneyPort } = jest.requireActual('../../../src/screens/onSite/money');
  await expect(unwiredMoneyPort.check('x')).rejects.toThrow('N13 (T-33): no server on this build');
  const w = makeWave({ money: unwiredMoneyPort });
  const app = await openScreen(w, 'FF-27', { workOrderId: 'wo-4824' });
  const page = within(app.onTop());
  expect(page.getByText('Balance not checked')).toBeTruthy();
  expect(page.getByTestId('disconnect')).not.toBeDisabled();
});
