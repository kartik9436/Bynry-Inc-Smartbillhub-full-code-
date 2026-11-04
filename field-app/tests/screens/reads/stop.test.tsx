/**
 * RW-06 The stop, RW-07 Getting in, RW-08 Find a meter, RW-12 Master and subs
 * (EP-FLD-11 §3), under the real navigation over the Maple Heights fixture.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';

import * as routeReadQ from '../../../src/db/queries/routeRead';
import { scoped } from '../../../src/db/scoped';
import { RAY } from './fixture';
import { mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

function fill(db: Parameters<typeof scoped>[0], id: string, value: string) {
  routeReadQ.recordCapture(scoped(db, RAY), id, {
    captureKey: `cap-${id}`,
    value,
    unit: 'gal',
    readerStatus: 'read',
    capturedAt: '2026-10-20T10:00:00.000Z',
    capturedBy: RAY,
    identifiedBy: 'listed',
    readMethod: 'walk',
  });
}

describe('RW-06 The stop', () => {
  test('one address with every meter at it; name, unit label and account shown (US-FLD-055 TC-1, US-FLD-058 TC-1)', async () => {
    const app = await mountReads();
    const page = await app.open('RW-06', { stopId: 's1318' });
    expect(within(page!).getByTestId('stop-address')).toHaveTextContent('1318 Maple Street');
    expect(within(page!).getByTestId('stop-hazard')).toHaveTextContent(/Two dogs/);
    expect(within(page!).getByTestId('customer-r0471')).toHaveTextContent('Carla Ruiz');
    expect(within(page!).getByTestId('account-r0471')).toHaveTextContent('ACC-10294');
    expect(within(page!).getByText('Unit A')).toBeTruthy();
    expect(within(page!).getByTestId('customer-r0472')).toHaveTextContent('Desmond Oyelaran');
    expect(within(page!).getByText('Master and 3 sub-meters')).toBeTruthy();
    expect(within(page!).getByText('Maple Heights HOA')).toBeTruthy();
    expect(within(page!).getByTestId('stop-count')).toHaveTextContent('0 of 6');
    // The subs are reached through their master, not listed as loose meters.
    expect(within(page!).queryByTestId('meter-r0470a')).toBeNull();
    app.unmount();
  });

  test('its doors, by address', async () => {
    const app = await mountReads();
    for (const [door, to] of [
      ['door-RW-07', 'RW-07'],
      ['door-RW-09', 'RW-09'],
      ['door-RW-12', 'RW-12'],
      ['door-RW-19', 'RW-19'],
      ['door-RW-17', 'RW-17'],
    ] as const) {
      const page = await app.open('RW-06', { stopId: 's1318' });
      fireEvent.press(within(page!).getByTestId(door));
      expect(`${door} → ${app.current()}`).toBe(`${door} → ${to}`);
    }
    app.unmount();
  });

  test('a read meter shows the reader’s status instead of Read →', async () => {
    const app = await mountReads();
    fill(app.db, 'r0471', '52410');
    const page = await app.open('RW-06', { stopId: 's1318' });
    expect(within(within(page!).getByTestId('meter-r0471')).getByText('Read')).toBeTruthy();
    expect(within(page!).getByTestId('stop-count')).toHaveTextContent('1 of 6');
    app.unmount();
  });
});

describe('RW-07 Getting in', () => {
  test('the property’s own notes and hazard (US-FLD-055 TC-2)', async () => {
    const app = await mountReads();
    const page = await app.open('RW-07', { stopId: 's1318' });
    expect(within(page!).getByTestId('getting-in-hazard')).toHaveTextContent(/Two dogs/);
    expect(within(page!).getByTestId('getting-in-notes')).toHaveTextContent(/Gate 4417/);
    fireEvent.press(within(page!).getByTestId('door-RW-06'));
    expect(app.current()).toBe('RW-06');
    app.unmount();
  });
});

describe('RW-08 Find a meter', () => {
  test('finds by partial badge what is on this phone; a hit opens the read', async () => {
    const app = await mountReads();
    const page = await app.open('RW-08');
    fireEvent.changeText(within(page!).getByLabelText('Find a meter'), '882');
    expect(await within(page!).findByText('MTR-0471 · badge 88241')).toBeTruthy();
    expect(within(page!).getByText('MTR-0472 · badge 88242')).toBeTruthy();
    fireEvent.press(within(page!).getByTestId('door-RW-09'));
    expect(app.current()).toBe('RW-09');
    // The door, named (tests/navigation/doors.test.tsx checks every built screen's doors are).
    expect(`RW-08 → ${app.current()}`).toBe('RW-08 → RW-09');
    app.unmount();
  });

  test('a scanned badge on the route opens its read; one not on it goes to RW-19', async () => {
    const app = await mountReads();
    app.scanner.queue.push('88241', '90118');
    let page = await app.open('RW-08');
    await act(async () => {
      fireEvent.press(within(page!).getByTestId('door-RW-19'));
    });
    expect(app.current()).toBe('RW-09');
    expect(app.currentParams()?.readId).toBe('r0471');
    page = await app.open('RW-08');
    await act(async () => {
      fireEvent.press(within(page!).getByTestId('door-RW-19'));
    });
    expect(app.current()).toBe('RW-19');
    expect(`RW-08 → ${app.current()}`).toBe('RW-08 → RW-19');
    expect(app.currentParams()?.code).toBe('90118');
    app.unmount();
  });
});

describe('RW-12 Master and subs', () => {
  test('Still to find is the master less its subs, in the meter’s own unit (US-FLD-055 TC-3)', async () => {
    const app = await mountReads();
    fill(app.db, 'r0470', '92480');
    fill(app.db, 'r0470a', '31100');
    fill(app.db, 'r0470b', '29640');
    const page = await app.open('RW-12', { readId: 'r0470' });
    expect(within(page!).getByTestId('balance')).toHaveTextContent(/60,740 gal/);
    expect(within(page!).getByTestId('still-to-find')).toHaveTextContent(/31,740 gal/);
    expect(within(page!).getByText('Read Unit 3')).toBeTruthy();
    fireEvent.press(within(page!).getByTestId('door-RW-09'));
    expect(app.currentParams()?.readId).toBe('r0470c');
    app.unmount();
  });

  test('no balance is drawn until the master is read', async () => {
    const app = await mountReads();
    const page = await app.open('RW-12', { readId: 'r0470' });
    expect(within(page!).queryByTestId('balance')).toBeNull();
    expect(screen.getAllByTestId('screen-RW-12').length).toBeGreaterThan(0);
    app.unmount();
  });
});
