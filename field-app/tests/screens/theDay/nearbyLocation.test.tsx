/**
 * FF-11 Nearby and where the handset is (DEF-FLD-10605, MQ-051).
 *
 * The beta walk: Nearby said *Could not load · Nearby needs a signal.* while
 * online, and the same after a GPS fix and *Try again*. Nearby read only the
 * fix the handset already HELD and never asked for one, and every error
 * became the one no-signal sentence. These run the SHIPPED port
 * (`httpNearbyPort` + `nearbyFixFrom`) over a fake server and a fake handset
 * position, so the no-fix path runs — the tests before them handed Nearby a
 * ready-made list and it never did.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen } from '@testing-library/react-native';

import type { Fix, LocationDevice } from '../../../src/device';
import type { PermissionsPort } from '../../../src/screens/gettingIn/permissions';
import { httpNearbyPort, nearbyFixFrom } from '../../../src/session/fieldDoors';
import type { FieldApi } from '../../../src/sync/fieldApi';
import { TransportError } from '../../../src/sync/transport';
import { mountDay, open } from './support';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const NOW = Date.UTC(2026, 9, 26, 9, 0);
const FIX: Fix = { lat: 41.881235, lng: -87.623178, accuracy_m: 6, fix_at: new Date(NOW - 5_000).toISOString() };
const CARD = {
  id: 'wo-4840',
  order_no: 'WO-4840',
  type: 'Routine read',
  priority: { code: 'P3' },
  premise: { address: '1412 Elm Street' },
  distance_mi: '0.20',
  due_at: null,
  est_minutes: 10,
  holder: 'free',
};

function fakeApi(nearby: jest.Mock = jest.fn(async () => ({ count: 1, next: null, results: [CARD] }))) {
  return { api: { nearby, claim: jest.fn() } as unknown as FieldApi, nearby };
}

function handset(current: () => Promise<Fix | null>, last: () => Fix | null = () => null): LocationDevice {
  return { current: jest.fn(current), last: jest.fn(last) };
}

function fakePermissions(over: Partial<PermissionsPort> = {}): PermissionsPort & Record<string, jest.Mock> {
  return {
    canRequest: true,
    status: jest.fn(async () => 'denied' as const),
    request: jest.fn(async () => 'granted' as const),
    blocked: jest.fn(async () => false),
    openSettings: jest.fn(async () => undefined),
    ...over,
  } as never;
}

describe('nearbyFixFrom — a fresh fix, never only the held one', () => {
  test('no held fix, but the handset finds one now: that one', async () => {
    const where = nearbyFixFrom(handset(async () => FIX), () => NOW);
    await expect(where()).resolves.toEqual(FIX);
  });

  test('no fresh fix: the held one, only while it is fresh', async () => {
    await expect(nearbyFixFrom(handset(async () => null, () => FIX), () => NOW)()).resolves.toEqual(FIX);
    const old = { ...FIX, fix_at: new Date(NOW - 3 * 60 * 1000).toISOString() };
    await expect(nearbyFixFrom(handset(async () => null, () => old), () => NOW)()).resolves.toBeNull();
  });

  test('asking fails: the held fix if fresh, else none', async () => {
    await expect(nearbyFixFrom(handset(async () => Promise.reject(new Error('gps')), () => FIX), () => NOW)()).resolves.toEqual(FIX);
  });
});

describe('FF-11 Nearby — location, signal and server are three different answers', () => {
  test('no held fix but current() finds one: the list loads (MQ-051)', async () => {
    const { api, nearby } = fakeApi();
    const location = handset(async () => FIX);
    const app = await mountDay({ fieldData: { nearby: httpNearbyPort(api, nearbyFixFrom(location, () => NOW)) } });
    await open(app, 'FF-11');
    expect(await screen.findByTestId('nearby-count')).toHaveTextContent('1 unassigned');
    expect(nearby).toHaveBeenCalledWith(expect.objectContaining({ lat: FIX.lat, lng: FIX.lng, radiusMi: 2, page: 1 }));
    expect(location.current).toHaveBeenCalled();
    app.unmount();
  });

  test('no permission: "Location is off" and Turn on location asks for it, then loads', async () => {
    const { api, nearby } = fakeApi();
    let fix: Fix | null = null;
    const location = handset(async () => fix);
    const permissions = fakePermissions({
      request: jest.fn(async () => {
        fix = FIX;
        return 'granted' as const;
      }),
    });
    const app = await mountDay({ fieldData: { nearby: httpNearbyPort(api, nearbyFixFrom(location, () => NOW)) }, gettingIn: { permissions } });
    await open(app, 'FF-11');
    const off = await screen.findByTestId('nearby-off');
    expect(off).toHaveTextContent(/Location is off/);
    expect(off).not.toHaveTextContent(/signal/);
    expect(nearby).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.press(screen.getByText('Turn on location'));
    });
    expect(permissions.request).toHaveBeenCalledWith('location');
    expect(permissions.openSettings).not.toHaveBeenCalled();
    expect(await screen.findByTestId('nearby-count')).toHaveTextContent('1 unassigned');
    app.unmount();
  });

  test('permission refused for good: Turn on location opens the app settings', async () => {
    const { api } = fakeApi();
    const permissions = fakePermissions({ blocked: jest.fn(async () => true) });
    const app = await mountDay({ fieldData: { nearby: httpNearbyPort(api, nearbyFixFrom(handset(async () => null), () => NOW)) }, gettingIn: { permissions } });
    await open(app, 'FF-11');
    await screen.findByTestId('nearby-off');
    await act(async () => {
      fireEvent.press(screen.getByText('Turn on location'));
    });
    expect(permissions.openSettings).toHaveBeenCalled();
    expect(permissions.request).not.toHaveBeenCalled();
    app.unmount();
  });

  test('no signal (a network error): "Nearby needs a signal." and Try again asks again', async () => {
    const { api, nearby } = fakeApi(jest.fn(async () => Promise.reject(new TransportError('network', 'Network request failed'))));
    const app = await mountDay({ fieldData: { nearby: httpNearbyPort(api, nearbyFixFrom(handset(async () => FIX), () => NOW)) } });
    await open(app, 'FF-11');
    expect(await screen.findByTestId('nearby-offline')).toHaveTextContent(/Nearby needs a signal\./);
    await act(async () => {
      fireEvent.press(screen.getByText('Try again'));
    });
    expect(nearby).toHaveBeenCalledTimes(2);
    app.unmount();
  });

  test('the server fails (500): "Could not load" with Try again, never the signal sentence', async () => {
    const { api } = fakeApi(jest.fn(async () => Promise.reject(new TransportError('network', 'HTTP 500', 500))));
    const app = await mountDay({ fieldData: { nearby: httpNearbyPort(api, nearbyFixFrom(handset(async () => FIX), () => NOW)) } });
    await open(app, 'FF-11');
    const failed = await screen.findByTestId('nearby-failed');
    expect(failed).toHaveTextContent(/Could not load/);
    expect(failed).not.toHaveTextContent(/signal/);
    expect(screen.getByText('Try again')).toBeTruthy();
    app.unmount();
  });
});
