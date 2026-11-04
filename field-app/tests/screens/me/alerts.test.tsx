/**
 * T-23 — FF-42 Alerts and FF-43 Emergency (US-FLD-013 §3), on the real
 * navigation tree with the alert feed as a fake port (`N25` is another lane's).
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { TextInput } from 'react-native';

import { EMERGENCY_ACK_MS } from '../../../src/screens/me/emergency';
import { boardAlerts, makeFixture, NOW, openScreen } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function onTop(id: string) {
  const all = screen.getAllByTestId(`screen-${id}`);
  return within(all.at(-1) as Parameters<typeof within>[0]);
}

describe('FF-42 Alerts', () => {
  test('TC-4: the emergency not acknowledged, then job cancelled, payment, schedule, and a dispatch message', async () => {
    const f = makeFixture();
    f.alerts.items = boardAlerts();
    const app = await openScreen('FF-42', f);
    const s = onTop('FF-42');
    expect(s.getByText(/^emergency · not acknowledged$/i)).toBeTruthy();
    expect(s.getByText('Gas leak reported')).toBeTruthy();
    // 48 seconds in: 4:12 left (R28).
    expect(s.getByTestId('ff42-countdown')).toHaveTextContent('Dispatch told in 4:12');
    for (const words of ['Aaron Bruner has paid', 'WO-4831 moved to 14:00', 'J. Okafor', 'Schedule change', 'Job canceled']) {
      expect(s.getAllByText(new RegExp(words)).length).toBeGreaterThan(0);
    }
    fireEvent.press(s.getByTestId('door-FF-43'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-43');
    app.unmount();
  });

  test('TC-5 (negative): dispatch messages only — there is no crew chat, nowhere to type', async () => {
    const f = makeFixture();
    f.alerts.items = boardAlerts();
    const app = await openScreen('FF-42', f);
    expect(onTop('FF-42').UNSAFE_queryAllByType(TextInput)).toHaveLength(0);
    app.unmount();
  });

  test('not wired: the feed says it is not on this phone, never an empty "all clear"', async () => {
    const f = makeFixture({ alerts: { list: async () => null, acknowledge: async () => undefined, markAllRead: async () => undefined } });
    const app = await openScreen('FF-42', f);
    expect(onTop('FF-42').getByTestId('ff42-not-wired')).toHaveTextContent(/Not on this phone yet/);
    app.unmount();
  });
});

describe('FF-43 Emergency', () => {
  test('TC-1: Gas leak reported, 14 Oak Street, WO-4850 — dispatch is told in 4:12; three acts', async () => {
    const f = makeFixture();
    f.alerts.items = boardAlerts();
    const app = await openScreen('FF-43', f);
    const s = onTop('FF-43');
    expect(s.getByTestId('ff43-title')).toHaveTextContent('Gas leak reported');
    expect(s.getByTestId('ff43-address')).toHaveTextContent('14 Oak Street');
    expect(s.getByText('1.8 miles · 7 min')).toBeTruthy();
    expect(s.getByText('WO-4850')).toBeTruthy();
    expect(s.getByText('10:06 · caller')).toBeTruthy();
    expect(s.getByTestId('ff43-countdown')).toHaveTextContent(/Dispatch is told in\s*4:12/);
    for (const label of ['Acknowledge', 'Call dispatch', 'Cannot attend']) {
      expect(s.getByRole('button', { name: label })).toBeTruthy();
    }
    app.unmount();
  });

  test('TC-2 (negative): five minutes with no acknowledgement — the screen says dispatch has been told', async () => {
    const f = makeFixture();
    f.alerts.items = boardAlerts().map((a) =>
      a.kind === 'emergency' ? { ...a, at: new Date(NOW.getTime() - EMERGENCY_ACK_MS).toISOString() } : a,
    );
    const app = await openScreen('FF-43', f);
    expect(onTop('FF-43').getByTestId('ff43-countdown')).toHaveTextContent(/Dispatch has been told/);
    app.unmount();
  });

  test('Acknowledge goes to the server, then back to Alerts, where the emergency is no longer open', async () => {
    const f = makeFixture();
    f.alerts.items = boardAlerts();
    const app = await openScreen('FF-43', f);
    await act(async () => {
      fireEvent.press(onTop('FF-43').getByTestId('door-FF-42'));
    });
    expect(f.alerts.acks).toEqual(['em-1']);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-42');
    app.unmount();
  });

  test('an acknowledgement that did not reach the server keeps the technician on the emergency (N25 not built)', async () => {
    const f = makeFixture();
    f.alerts.items = boardAlerts();
    f.alerts.failAck = true;
    const app = await openScreen('FF-43', f);
    await act(async () => {
      fireEvent.press(onTop('FF-43').getByTestId('door-FF-42'));
    });
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-43');
    expect(onTop('FF-43').getByTestId('ff43-problem')).toHaveTextContent('Not acknowledged. Call dispatch.');
    app.unmount();
  });

  test('R107: Cannot attend never hands the job back — it calls dispatch', async () => {
    const calls: string[] = [];
    const f = makeFixture({ dispatch: { call: async () => void calls.push('dispatch') } });
    f.alerts.items = boardAlerts();
    const app = await openScreen('FF-43', f);
    await act(async () => {
      fireEvent.press(onTop('FF-43').getByTestId('ff43-cannot-attend'));
    });
    expect(calls).toEqual(['dispatch']);
    expect(f.alerts.acks).toEqual([]);
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-43');
    app.unmount();
  });
});
