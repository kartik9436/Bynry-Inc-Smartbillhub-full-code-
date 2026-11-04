/**
 * Notifications: the five Android channels are the SERVER'S five kinds (read
 * from `push.py` itself, so a drift goes red), an emergency is MAX and asks to
 * bypass Do Not Disturb, iOS asks for Critical Alerts, and the push token is
 * registered for whoever is signed in — once per technician and token — through
 * the existing devices route.
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import * as Notifications from 'expo-notifications';

import {
  createPushRegistrar,
  devicePushToken,
  ensurePushChannels,
  IOS_PERMISSION_REQUEST,
  listenForPushes,
  PUSH_CHANNELS,
  showPushesInForeground,
} from '../../../src/device/native/notifications';
import { expoPermissions } from '../../../src/device/native/permissions';
import { createHttpAuthApi } from '../../../src/security/httpAuthApi';
import type { SessionSnapshot } from '../../../src/session/sessionManager';

const N = Notifications as jest.Mocked<typeof Notifications>;
beforeEach(() => jest.clearAllMocks());

/** `PUSH_KINDS` as `06-backend/apps/work/push.py` declares it: kind → (channel id, importance). */
function serverKinds(): Map<string, { channel: string; importance: string }> {
  const src = readFileSync(resolve(__dirname, '../../../../06-backend/apps/work/push.py'), 'utf8');
  const block = src.slice(src.indexOf('PUSH_KINDS'), src.indexOf('\n}\n', src.indexOf('PUSH_KINDS')));
  const out = new Map<string, { channel: string; importance: string }>();
  for (const m of block.matchAll(/"(\w+)":\s*\{[^}]*?"android_channel_id":\s*"(\w+)"[^}]*?"android_importance":\s*"(\w+)"/g)) {
    out.set(m[1]!, { channel: m[2]!, importance: m[3]! });
  }
  return out;
}

test('the handset creates exactly the channels the server pushes on, at the server\'s importance', () => {
  const server = serverKinds();
  console.log(`push.py PUSH_KINDS read: ${server.size} kinds`);
  expect(server.size).toBe(6);
  expect(new Map(PUSH_CHANNELS.map((c) => [c.kind, { channel: c.kind, importance: c.importance }]))).toEqual(server);
});

test('Android: six channels, the emergency at MAX and bypassing Do Not Disturb, named in the technician\'s words', async () => {
  const made = await ensurePushChannels((k) => `«${k}»`, 'android');
  expect(made).toBe(6);
  expect(N.setNotificationChannelAsync).toHaveBeenCalledTimes(6);
  const emergency = N.setNotificationChannelAsync.mock.calls.find((c) => c[0] === 'emergency')?.[1];
  expect(emergency).toMatchObject({ name: '«field.ff42.kind.emergency»', importance: Notifications.AndroidImportance.MAX, bypassDnd: true });
  const message = N.setNotificationChannelAsync.mock.calls.find((c) => c[0] === 'dispatch_message')?.[1];
  expect(message).toMatchObject({ importance: Notifications.AndroidImportance.LOW, bypassDnd: false });
});

test('iOS has no channels; it asks for Critical Alerts with the permission (ADR-012)', async () => {
  await expect(ensurePushChannels((k) => k, 'ios')).resolves.toBe(0);
  expect(N.setNotificationChannelAsync).not.toHaveBeenCalled();
  N.requestPermissionsAsync.mockResolvedValueOnce({ granted: true, status: 'granted' } as never);
  const onGranted = jest.fn();
  await expect(expoPermissions(onGranted).request('notifications')).resolves.toBe('granted');
  expect(N.requestPermissionsAsync).toHaveBeenCalledWith(IOS_PERMISSION_REQUEST);
  expect(IOS_PERMISSION_REQUEST.ios.allowCriticalAlerts).toBe(true);
  expect(onGranted).toHaveBeenCalledWith('notifications');
});

const pushFor = (data: Record<string, unknown>) => ({ request: { content: { data } } }) as never;

describe('a push is acted on only for the utility the app is signed into (DEF-WRK-10352)', () => {
  const signedInto = (tenant: string | null) =>
    fakeSession(tenant ? { phase: 'unlocked', active: { ...dana, tenant } } : { phase: 'signedOut', active: null });

  async function foreground(session: ReturnType<typeof fakeSession>, data: Record<string, unknown>) {
    showPushesInForeground(session);
    const handler = N.setNotificationHandler.mock.calls[N.setNotificationHandler.mock.calls.length - 1]?.[0];
    return handler!.handleNotification(pushFor(data));
  }

  test('OUR utility\'s push shows and sounds while the app is open', async () => {
    await expect(foreground(signedInto('silver-creek'), { kind: 'emergency', tenant: 'silver-creek' })).resolves.toMatchObject({
      shouldShowBanner: true,
      shouldPlaySound: true,
    });
  });

  test('ANOTHER utility\'s push: no banner, no sound, no list, no badge — and the app is not told', async () => {
    await expect(foreground(signedInto('silver-creek'), { kind: 'new_job', tenant: 'oak-valley' })).resolves.toEqual({
      shouldShowBanner: false,
      shouldShowList: false,
      shouldPlaySound: false,
      shouldSetBadge: false,
    });
    const onOurs = jest.fn();
    listenForPushes(signedInto('silver-creek'), onOurs);
    const received = N.addNotificationReceivedListener.mock.calls[0]![0];
    const tapped = N.addNotificationResponseReceivedListener.mock.calls[0]![0];
    received(pushFor({ tenant: 'oak-valley' }));
    tapped({ notification: pushFor({ tenant: 'oak-valley' }) } as never);
    expect(onOurs).not.toHaveBeenCalled();
    received(pushFor({ tenant: 'silver-creek', order_no: 'WO-1042' }));
    expect(onOurs).toHaveBeenCalledWith({ tenant: 'silver-creek', order_no: 'WO-1042' }, 'received');
  });

  test('NOBODY signed in: nothing, even for a utility this phone has known', async () => {
    await expect(foreground(signedInto(null), { kind: 'emergency', tenant: 'silver-creek' })).resolves.toMatchObject({ shouldShowBanner: false, shouldPlaySound: false });
    const onOurs = jest.fn();
    listenForPushes(signedInto(null), onOurs);
    N.addNotificationReceivedListener.mock.calls[0]![0](pushFor({ tenant: 'silver-creek' }));
    N.addNotificationResponseReceivedListener.mock.calls[0]![0]({ notification: pushFor({ tenant: 'silver-creek' }) } as never);
    expect(onOurs).not.toHaveBeenCalled();
  });

  test('a push naming NO utility (what the server sends today) fails closed', async () => {
    await expect(foreground(signedInto('silver-creek'), { kind: 'new_job', order_no: 'WO-1042' })).resolves.toMatchObject({ shouldShowBanner: false });
  });

  test('the server payload names its utility (`data.tenant`) — the gate can open (DEF-WRK-10352)', () => {
    const src = readFileSync(resolve(__dirname, '../../../../06-backend/apps/work/push.py'), 'utf8');
    const body = src.slice(src.indexOf('def push_message'), src.indexOf('def scope_key'));
    expect(body).toMatch(/"tenant": tenant/);
  });
});

test('the device token is the platform\'s (FCM / APNs); an empty or failing answer is no token', async () => {
  N.getDevicePushTokenAsync.mockResolvedValueOnce({ type: 'android', data: 'fcm-abc' } as never);
  await expect(devicePushToken()).resolves.toBe('fcm-abc');
  N.getDevicePushTokenAsync.mockRejectedValueOnce(new Error('simulator'));
  await expect(devicePushToken()).resolves.toBeNull();
});

function fakeSession(snap: Partial<SessionSnapshot> & { phase: SessionSnapshot['phase'] }, token: string | null = 'access-1') {
  let listener: ((snap: SessionSnapshot) => void) | null = null;
  let current = { active: null, canSend: true, canCapture: true, captureNeedsPassword: false, known: [], ...snap } as SessionSnapshot;
  return {
    snapshot: () => current,
    subscribe: (l: (snap: SessionSnapshot) => void) => {
      listener = l;
      return () => {
        listener = null;
      };
    },
    courierAccessToken: () => token,
    set(next: Partial<SessionSnapshot>) {
      current = { ...current, ...next };
      listener?.(current);
    },
  };
}

const dana = { technicianId: 'u-dana', userId: 'u-dana', displayName: 'Dana', login: 'dana@x', tenant: 'silver-creek' };
const marco = { technicianId: 'u-marco', userId: 'u-marco', displayName: 'Marco', login: 'marco@x', tenant: 'silver-creek' };

test('the token is registered for whoever is signed in, once per technician — and again after a switch', async () => {
  const session = fakeSession({ phase: 'unlocked', active: dana });
  const registerDevice = jest.fn(async () => ({ deviceId: 'h-1', name: 'Van 14 tablet' }));
  const r = createPushRegistrar({
    session,
    api: { registerDevice },
    deviceId: async () => 'h-1',
    deviceName: async () => 'Van 14 tablet',
    pushToken: async () => 'fcm-abc',
    allowed: async () => true,
  });
  await r.tryNow();
  await r.tryNow();
  expect(registerDevice).toHaveBeenCalledTimes(1);
  expect(registerDevice).toHaveBeenCalledWith({ tenant: 'silver-creek', accessToken: 'access-1', deviceId: 'h-1', name: 'Van 14 tablet', pushToken: 'fcm-abc' });
  session.set({ active: marco });
  await r.tryNow();
  expect(registerDevice).toHaveBeenCalledTimes(2);
  expect(registerDevice.mock.calls[1]).toEqual([expect.objectContaining({ pushToken: 'fcm-abc' })]);
  r.stop();
});

test('nothing is registered signed out, offline (no access token), without permission, or without a token', async () => {
  const registerDevice = jest.fn(async () => ({ deviceId: 'h', name: '' }));
  const base = { api: { registerDevice }, deviceId: async () => 'h', deviceName: async () => null };
  await createPushRegistrar({ ...base, session: fakeSession({ phase: 'signedOut', active: dana }), pushToken: async () => 't', allowed: async () => true }).tryNow();
  await createPushRegistrar({ ...base, session: fakeSession({ phase: 'unlocked', active: dana }, null), pushToken: async () => 't', allowed: async () => true }).tryNow();
  await createPushRegistrar({ ...base, session: fakeSession({ phase: 'unlocked', active: dana }), pushToken: async () => 't', allowed: async () => false }).tryNow();
  await createPushRegistrar({ ...base, session: fakeSession({ phase: 'unlocked', active: dana }), pushToken: async () => null, allowed: async () => true }).tryNow();
  expect(registerDevice).not.toHaveBeenCalled();
});

test('a refused registration is tried again, not remembered as done', async () => {
  const registerDevice = jest.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ deviceId: 'h', name: '' });
  const r = createPushRegistrar({
    session: fakeSession({ phase: 'unlocked', active: dana }),
    api: { registerDevice },
    deviceId: async () => 'h',
    deviceName: async () => null,
    pushToken: async () => 't',
    allowed: async () => true,
  });
  await expect(r.tryNow()).resolves.toBe(false);
  await expect(r.tryNow()).resolves.toBe(true);
  expect(registerDevice).toHaveBeenCalledTimes(2);
});

test('the HTTP client sends the token as push_token on POST work/mobile/devices, with the platform', async () => {
  const calls: Array<{ url: string; body: unknown }> = [];
  const fetchImpl = (async (url: string, init: { body?: string }) => {
    calls.push({ url, body: init.body ? JSON.parse(init.body) : null });
    return { status: 200, ok: true, json: async () => ({ device_id: 'h-1', name: 'Van 14 tablet' }) };
  }) as unknown as typeof fetch;
  const api = createHttpAuthApi({ baseUrl: 'https://u.example', platform: 'ios', fetchImpl });
  await api.registerDevice({ tenant: 'silver-creek', accessToken: 'a', deviceId: 'h-1', name: 'Van 14 tablet', pushToken: 'apns-xyz' });
  expect(calls[0]?.url).toMatch(/silver-creek\/work\/mobile\/devices$/);
  expect(calls[0]?.body).toEqual({ device_id: 'h-1', name: 'Van 14 tablet', platform: 'ios', push_token: 'apns-xyz' });
  await api.registerDevice({ tenant: 'silver-creek', accessToken: 'a', deviceId: 'h-1', name: 'Van 14 tablet' });
  expect(calls[1]?.body).toEqual({ device_id: 'h-1', name: 'Van 14 tablet', platform: 'ios' });
});
