/**
 * The real position over expo-location: 6 decimals and 1 decimal, best fix
 * wins, no permission → no fix (never a made-up one).
 */
import * as Location from 'expo-location';

import { betterFix, expoLocation, FIX_STALE_MS, fixOf } from '../../../src/device/native/location';
import { expoPermissions } from '../../../src/device/native/permissions';

const loc = Location as jest.Mocked<typeof Location>;
const granted = { granted: true, status: 'granted', canAskAgain: true, expires: 'never' } as never;

function pos(lat: number, lng: number, accuracy: number | null, at: number) {
  return { coords: { latitude: lat, longitude: lng, accuracy, altitude: null, altitudeAccuracy: null, heading: null, speed: null }, timestamp: at } as never;
}

beforeEach(() => jest.clearAllMocks());

test('a position is stored to 6 decimals, its accuracy to 1, its time as ISO', () => {
  expect(fixOf(pos(41.88123456, -87.62317789, 4.267, Date.UTC(2026, 9, 21, 9, 14)))).toEqual({
    lat: 41.881235,
    lng: -87.623178,
    accuracy_m: 4.3,
    fix_at: '2026-10-21T09:14:00.000Z',
  });
});

test('a position with no accuracy is no fix (R90 needs one)', () => {
  expect(fixOf(pos(1, 2, null, 0))).toBeNull();
  expect(fixOf(null)).toBeNull();
});

test('best fix wins: a rougher new fix does not replace a sharper recent one; a stale one loses to anything', () => {
  const t0 = Date.UTC(2026, 9, 21, 9, 0);
  const sharp = { lat: 1, lng: 1, accuracy_m: 4, fix_at: new Date(t0).toISOString() };
  const rough = { lat: 2, lng: 2, accuracy_m: 30, fix_at: new Date(t0 + 10_000).toISOString() };
  expect(betterFix(sharp, rough, t0 + 10_000)).toBe(sharp);
  expect(betterFix(sharp, rough, t0 + FIX_STALE_MS + 1)).toBe(rough);
  expect(betterFix(rough, sharp, t0 + 10_000)).toBe(sharp);
  expect(betterFix(null, rough, t0)).toBe(rough);
});

test('current(): no permission → null, and the platform is not even asked for a position', async () => {
  const device = expoLocation({ watch: false });
  await expect(device.current()).resolves.toBeNull();
  expect(loc.getCurrentPositionAsync).not.toHaveBeenCalled();
});

test('current(): weighs the fresh fix against the last known and keeps the sharper; last() holds it', async () => {
  const now = Date.UTC(2026, 9, 21, 9, 0, 30);
  loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
  loc.getLastKnownPositionAsync.mockResolvedValueOnce(pos(41.1, -87.1, 5, now - 20_000));
  loc.getCurrentPositionAsync.mockResolvedValueOnce(pos(41.2, -87.2, 35, now - 1_000));
  const device = expoLocation({ watch: false, now: () => now });
  const fix = await device.current();
  expect(fix).toMatchObject({ lat: 41.1, lng: -87.1, accuracy_m: 5 });
  expect(device.last()).toEqual(fix);
  expect(loc.getCurrentPositionAsync).toHaveBeenCalledWith({ accuracy: Location.Accuracy.High });
});

test('current(): a held fix gone stale is answered as no fix, not as where the handset is', async () => {
  let now = Date.UTC(2026, 9, 21, 9, 0);
  loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
  loc.getCurrentPositionAsync.mockResolvedValueOnce(pos(41.1, -87.1, 5, now));
  const device = expoLocation({ watch: false, now: () => now });
  await device.current();
  now += FIX_STALE_MS + 1;
  loc.getCurrentPositionAsync.mockResolvedValueOnce(null as never);
  await expect(device.current()).resolves.toBeNull();
});

test('the background watch starts only with permission, and stops', async () => {
  loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
  const remove = jest.fn();
  let push: ((p: never) => void) | null = null;
  loc.watchPositionAsync.mockImplementationOnce(async (_o, cb) => {
    push = cb as never;
    return { remove };
  });
  const device = expoLocation();
  await new Promise((r) => setTimeout(r, 0));
  expect(loc.watchPositionAsync).toHaveBeenCalledWith(expect.objectContaining({ accuracy: Location.Accuracy.Balanced }), expect.any(Function));
  push!(pos(40, -80, 8, Date.now()));
  expect(device.last()).toMatchObject({ lat: 40, lng: -80, accuracy_m: 8 });
  device.stop();
  expect(remove).toHaveBeenCalled();
});

describe('DEF-FLD-10605: the watch starts when permission arrives later', () => {
  const denied = { granted: false, status: 'denied', canAskAgain: true, expires: 'never' } as never;
  const tick = () => new Promise((r) => setTimeout(r, 0));

  test('no permission at start → no watch; startWatch() after the grant starts it, once', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValue(denied);
    const device = expoLocation();
    await tick();
    expect(loc.watchPositionAsync).not.toHaveBeenCalled();
    loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
    device.startWatch();
    device.startWatch();
    await tick();
    device.startWatch();
    await tick();
    expect(loc.watchPositionAsync).toHaveBeenCalledTimes(1);
    device.stop();
  });

  test('current() with permission starts the watch too, so a later screen has a held fix', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValue(denied);
    const device = expoLocation();
    await tick();
    loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
    await device.current();
    await tick();
    expect(loc.watchPositionAsync).toHaveBeenCalledTimes(1);
    device.stop();
  });
});

describe('DEF-FLD-10605: blocked() — the platform will not ask again', () => {
  test('denied and cannot ask again → blocked; denied but can ask → not', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValueOnce({ granted: false, status: 'denied', canAskAgain: false, expires: 'never' } as never);
    await expect(expoPermissions().blocked!('location')).resolves.toBe(true);
    loc.getForegroundPermissionsAsync.mockResolvedValueOnce({ granted: false, status: 'denied', canAskAgain: true, expires: 'never' } as never);
    await expect(expoPermissions().blocked!('location')).resolves.toBe(false);
  });
});

describe('DEF-FLD-10632 (FB-003): ensureOn() — Android is asked where location is used', () => {
  const denied = (canAskAgain: boolean) => ({ granted: false, status: 'denied', canAskAgain, expires: 'never' }) as never;

  test('not allowed yet → the platform prompt; allowed → on', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValueOnce(denied(true));
    loc.requestForegroundPermissionsAsync.mockResolvedValueOnce(granted);
    const device = expoLocation({ watch: false });
    await expect(device.ensureOn!()).resolves.toBe('on');
    expect(loc.requestForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
  });

  test('refused with Don\'t ask again → blocked, and the prompt is not shown', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValueOnce(denied(false));
    const device = expoLocation({ watch: false });
    await expect(device.ensureOn!()).resolves.toBe('blocked');
    expect(loc.requestForegroundPermissionsAsync).not.toHaveBeenCalled();
  });

  test('refused now, may be asked again → refused; refused for good at the prompt → blocked', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValue(denied(true));
    loc.requestForegroundPermissionsAsync.mockResolvedValueOnce(denied(true));
    const device = expoLocation({ watch: false });
    await expect(device.ensureOn!()).resolves.toBe('refused');
    loc.requestForegroundPermissionsAsync.mockResolvedValueOnce(denied(false));
    await expect(device.ensureOn!()).resolves.toBe('blocked');
  });

  test('allowed but the phone\'s Location is off → Android\'s Turn on location dialog', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
    (loc.hasServicesEnabledAsync as jest.Mock).mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    const device = expoLocation({ watch: false });
    await expect(device.ensureOn!()).resolves.toBe('on');
    expect(loc.enableNetworkProviderAsync).toHaveBeenCalledTimes(1);
  });

  test('the dialog declined → off', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
    (loc.hasServicesEnabledAsync as jest.Mock).mockResolvedValue(false);
    (loc.enableNetworkProviderAsync as jest.Mock).mockRejectedValueOnce(new Error('declined'));
    const device = expoLocation({ watch: false });
    await expect(device.ensureOn!()).resolves.toBe('off');
    (loc.hasServicesEnabledAsync as jest.Mock).mockResolvedValue(true);
  });

  test('every fix the watch accepts is told to subscribers', async () => {
    loc.getForegroundPermissionsAsync.mockResolvedValue(granted);
    let push: ((p: never) => void) | null = null;
    loc.watchPositionAsync.mockImplementationOnce(async (_o, cb) => {
      push = cb as never;
      return { remove: jest.fn() };
    });
    const device = expoLocation();
    const seen: unknown[] = [];
    const off = device.subscribe!((f) => seen.push(f));
    await new Promise((r) => setTimeout(r, 0));
    push!(pos(40, -80, 8, Date.now()));
    expect(seen).toEqual([expect.objectContaining({ lat: 40, accuracy_m: 8 })]);
    off();
    device.stop();
  });
});
