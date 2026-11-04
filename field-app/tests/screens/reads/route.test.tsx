/**
 * RW-01 … RW-05 — getting a route and walking it (EP-FLD-10, EP-FLD-11 §3),
 * mounted under the real navigation over the Maple Heights fixture.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as walkQ from '../../../src/db/queries/readsWalk';
import { scoped } from '../../../src/db/scoped';
import { FakeLocation, mountReads } from './harness';
import { RAY } from './fixture';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

describe('RW-01 My routes', () => {
  test('Reads opens My routes from the bottom bar, in the same app (US-FLD-053 TC-1)', async () => {
    const app = await mountReads();
    fireEvent.press(screen.getByTestId('tab-RW-01'));
    expect(app.current()).toBe('RW-01');
    const page = await screen.findByTestId('screen-RW-01');
    expect(within(page).getByText('Maple Heights')).toBeTruthy();
    expect(within(page).getByText('On the phone')).toBeTruthy();
    expect(within(page).getByText('Riverside East')).toBeTruthy();
    expect(within(page).getByText('Not downloaded')).toBeTruthy();
    // TC-2: the same outbox as jobs — its count is the outbox's.
    expect(within(page).getByText('0 waiting to send')).toBeTruthy();
    app.unmount();
  });

  test('its doors go where they say, by address', async () => {
    const app = await mountReads();
    for (const [door, to] of [
      ['door-RW-02', 'RW-02'],
      ['door-RW-03', 'RW-03'],
      ['door-RW-08', 'RW-08'],
      ['door-RW-26', 'RW-26'],
    ] as const) {
      const page = await app.open('RW-01');
      fireEvent.press(within(page!).getByTestId(door));
      expect(`${door} → ${app.current()}`).toBe(`${door} → ${to}`);
    }
    expect(app.sent.length).toBe(1); // Send now sends
    app.unmount();
  });
});

describe('RW-02 Route summary and RW-03 Download', () => {
  test('RW-02 shows the route as downloaded (US-FLD-054 TC-1)', async () => {
    const app = await mountReads();
    const page = await app.open('RW-02', { routeId: 'wlk-07' });
    expect(within(page!).getByTestId('route-name')).toHaveTextContent('Maple Heights');
    expect(within(page!).getByLabelText('5 stops')).toBeTruthy();
    expect(within(page!).getByLabelText('10 meters')).toBeTruthy();
    expect(within(page!).getByLabelText('3 sub-meters')).toBeTruthy();
    for (const v of ['WLK-07', 'Water', 'walk', 'North', 'WTR-M Oct']) expect(within(page!).getByText(v)).toBeTruthy();
    fireEvent.press(within(page!).getByTestId('door-RW-04'));
    expect(app.current()).toBe('RW-04');
    app.unmount();
  });

  test('RW-03 counts what is ON the phone, and the walk opens only at 100% (US-FLD-054 TC-2, TC-4)', async () => {
    const app = await mountReads();
    // Riverside East has nothing on the phone: the walk is not offered.
    let page = await app.open('RW-03', { routeId: 'drv-02' });
    expect(within(page!).getByTestId('download-percent')).toHaveTextContent('0%');
    expect(within(page!).getByTestId('door-RW-05')).toBeDisabled();
    expect(within(page!).getByText('Opens at 100%')).toBeTruthy();
    // No server door yet: said in words, not faked.
    expect(within(page!).getByText('Routes cannot be downloaded yet.')).toBeTruthy();
    page = await app.open('RW-03', { routeId: 'wlk-07' });
    expect(within(page!).getByTestId('download-percent')).toHaveTextContent('100%');
    fireEvent.press(within(page!).getByTestId('door-RW-05'));
    expect(app.current()).toBe('RW-05');
    app.unmount();
  });
});

describe('RW-05 The walk', () => {
  test('lists ADDRESSES, nearest first by default, with no signal needed for the points (US-FLD-056 TC-1, TC-3)', async () => {
    const app = await mountReads();
    const page = await app.open('RW-05', { routeId: 'wlk-07' });
    const order = [0, 1, 2, 3, 4].map((i) => within(page!).getByTestId(`stop-${i}`));
    expect(order.map((n) => within(n).getAllByText(/Maple|Birch/)[0]?.props.children)).toEqual([
      '1318 Maple Street',
      '1322 Maple Street',
      '1240 Maple Street',
      '1206 Maple Street',
      '42 Birch Lane',
    ]);
    expect(within(order[0]!).getByText('40 m')).toBeTruthy();
    expect(within(order[4]!).getByText('310 m')).toBeTruthy();
    expect(within(order[0]!).getByText('6 meters · stop 12')).toBeTruthy();
    app.unmount();
  });

  test('walk order is one tap away (US-FLD-056 TC-2)', async () => {
    const app = await mountReads();
    const page = await app.open('RW-05', { routeId: 'wlk-07' });
    fireEvent.press(within(page!).getByTestId('walk-order-walk'));
    const first = within(page!).getByTestId('stop-0');
    expect(within(first).getByText('1240 Maple Street')).toBeTruthy();
    expect(within(page!).getByTestId('stop-4')).toHaveTextContent(/42 Birch Lane/);
    app.unmount();
  });

  test('with no fix at all, it says so and shows the office order rather than a wrong "nearest"', async () => {
    const app = await mountReads({ location: new FakeLocation(null) });
    const page = await app.open('RW-05', { routeId: 'wlk-07' });
    expect(within(page!).getByText('No position yet. Walk order shown.')).toBeTruthy();
    expect(within(within(page!).getByTestId('stop-0')).getByText('1240 Maple Street')).toBeTruthy();
    app.unmount();
  });

  test('its doors: the stop, the map, progress, and a meter not listed', async () => {
    const app = await mountReads();
    for (const [door, to] of [
      ['door-RW-06', 'RW-06'],
      ['door-RW-04', 'RW-04'],
      ['door-RW-22', 'RW-22'],
      ['door-RW-19', 'RW-19'],
    ] as const) {
      const page = await app.open('RW-05', { routeId: 'wlk-07' });
      fireEvent.press(within(page!).getByTestId(door));
      expect(`${door} → ${app.current()}`).toBe(`${door} → ${to}`);
    }
    // The primary opens the NEAREST stop, by its id.
    const page = await app.open('RW-05', { routeId: 'wlk-07' });
    fireEvent.press(within(page!).getByTestId('door-RW-06'));
    expect(app.currentParams()?.stopId).toBe('s1318');
    app.unmount();
  });

  // US-FLD-077 TC-1 (the stop beside the list on a tablet) moved to
  // `tests/tablet/contextPanes.test.tsx` (T-28/T-29): RW-05 now splits by the
  // width of the PANE it is given, so the case runs at the board's 1024 × 768
  // inside the tablet frame; this file mounts at Jest's 750 window, where the
  // frame's one pane (530) cannot hold two columns of 260 (R122).

  test('reading out of sequence is never refused, and the order walked is the capture times (R77, TC-4)', async () => {
    const app = await mountReads();
    const s = scoped(app.db, RAY);
    // Read stop 13 (1322) before stop 12 (1318): nothing refuses it.
    let page = await app.open('RW-09', { readId: 'r1240' });
    for (const k of ['2', '1', '0', '0']) fireEvent.press(within(page!).getByTestId(`keypad-${k}`));
    await act(async () => {
      fireEvent.press(within(page!).getByTestId('door-RW-13'));
    });
    app.clock.advance(60_000);
    page = await app.open('RW-09', { readId: 'r1206' });
    for (const k of ['3', '1', '0', '0']) fireEvent.press(within(page!).getByTestId(`keypad-${k}`));
    await act(async () => {
      fireEvent.press(within(page!).getByTestId('door-RW-13'));
    });
    const walked = walkQ.captureTimes(s, 'wlk-07');
    expect(walked).toHaveLength(2);
    expect(walkQ.meter(s, 'r1240')?.captured_at).toBe(walked[0]);
    expect(walkQ.meter(s, 'r1206')?.captured_at).toBe(walked[1]);
    app.unmount();
  });
});

describe('RW-04 Route map', () => {
  test('plots every stop from its downloaded point, the nearest marked next, with the reader', async () => {
    const app = await mountReads();
    const page = await app.open('RW-04', { routeId: 'wlk-07' });
    expect(within(page!).getByTestId('pin-s1318-next')).toBeTruthy();
    expect(within(page!).getByTestId('pin-s42-toDo')).toBeTruthy();
    expect(within(page!).getByTestId('pin-you')).toBeTruthy();
    expect(within(page!).getByText('5 left')).toBeTruthy();
    fireEvent.press(within(page!).getByTestId('door-RW-06'));
    expect(app.current()).toBe('RW-06');
    expect(app.currentParams()?.stopId).toBe('s1318');
    app.unmount();
  });
});
