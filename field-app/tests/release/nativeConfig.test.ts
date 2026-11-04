/**
 * A preview build WITHOUT the Firebase files and WITHOUT a Google Maps key
 * (`app.config.ts`, `src/release/nativeConfig.ts`): the config leaves both
 * out, says so in `extra`, and the JavaScript then never reaches for them —
 * no Crashlytics (crash files stay on the handset), no Android push token,
 * and no native Android map view (which crashes without a key).
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a binary whose real `Constants` carries
 * a different `extra` shape than `buildConfig` writes. The round trip below
 * feeds `buildConfig`'s own `extra` into `nativeConfig`, so a renamed key on
 * one side goes red here.
 */
import * as RNFBApp from '@react-native-firebase/app';
import * as RNFBCrashlytics from '@react-native-firebase/crashlytics';
import * as Notifications from 'expo-notifications';
import type { ExpoConfig } from 'expo/config';

import appJson from '../../app.json';
import { ANDROID_FIREBASE_FILE, buildConfig, FIREBASE_PLUGINS, IOS_FIREBASE_FILE } from '../../app.config';
import { createPushRegistrar } from '../../src/device/native/notifications';
import { mapViewFor, nativeConfig, pushAvailable } from '../../src/release/nativeConfig';
import { nativeCrashlytics } from '../../src/telemetry/firebaseCrashlytics';

const base = (appJson as unknown as { expo: Partial<ExpoConfig> }).expo;
const NOTHING = { exists: () => false, env: {} };
const EVERYTHING = { exists: () => true, env: { GOOGLE_MAPS_ANDROID_API_KEY: 'AIza-test' } };
const pluginNames = (c: ExpoConfig) => (c.plugins ?? []).map((p) => (Array.isArray(p) ? p[0] : p));

describe('app.config.ts', () => {
  test('no Firebase files and no map key: neither is referenced, and extra says so', () => {
    const c = buildConfig(base, NOTHING);
    expect(c.android?.googleServicesFile).toBeUndefined();
    expect(c.ios?.googleServicesFile).toBeUndefined();
    for (const p of FIREBASE_PLUGINS) expect(pluginNames(c)).not.toContain(p);
    expect(c.android?.config?.googleMaps).toBeUndefined();
    expect(c.extra).toMatchObject({ firebaseConfigured: false, mapsAvailable: { ios: true, android: false } });
  });

  test('with both files and a key: the files, the two plugins (after build-properties) and the key are all in', () => {
    const c = buildConfig(base, EVERYTHING);
    expect(c.android?.googleServicesFile).toBe(ANDROID_FIREBASE_FILE);
    expect(c.ios?.googleServicesFile).toBe(IOS_FIREBASE_FILE);
    const names = pluginNames(c);
    expect(names.indexOf('@react-native-firebase/app')).toBe(names.indexOf('expo-build-properties') + 1);
    expect(names).toContain('@react-native-firebase/crashlytics');
    expect(c.android?.config?.googleMaps?.apiKey).toBe('AIza-test');
    expect(c.extra).toMatchObject({ firebaseConfigured: true, mapsAvailable: { ios: true, android: true } });
  });

  test('half a pair is none: the app plugin refuses a platform with no file, so one file alone adds nothing', () => {
    const c = buildConfig(base, { exists: (p) => p === ANDROID_FIREBASE_FILE, env: {} });
    expect(c.android?.googleServicesFile).toBeUndefined();
    expect(pluginNames(c)).not.toContain('@react-native-firebase/app');
    expect(c.extra).toMatchObject({ firebaseConfigured: false });
  });

  test('app.json itself names no Firebase file or plugin, and carries the proposed identity', () => {
    const raw = JSON.stringify(appJson);
    expect(raw).not.toContain('googleServicesFile');
    expect(raw).not.toContain('@react-native-firebase');
    expect(base.owner).toBe('bynry');
    expect(base.android?.package).toBe('io.bynry.smart360.field');
    expect(base.ios?.bundleIdentifier).toBe('io.bynry.smart360.field');
  });
});

describe('the JavaScript reads the build', () => {
  test('round trip: what buildConfig writes is what nativeConfig reads', () => {
    expect(nativeConfig(buildConfig(base, NOTHING).extra)).toEqual({ firebase: false, maps: { ios: true, android: false } });
    expect(nativeConfig(buildConfig(base, EVERYTHING).extra)).toEqual({ firebase: true, maps: { ios: true, android: true } });
  });

  test('a binary that says nothing (Expo Go, an old config) is treated as having neither — fail closed', () => {
    expect(nativeConfig(undefined)).toEqual({ firebase: false, maps: { ios: false, android: false } });
  });
});

describe('no Firebase', () => {
  const getCrashlytics = (RNFBCrashlytics as unknown as { getCrashlytics: jest.Mock }).getCrashlytics;
  const getApps = (RNFBApp as unknown as { getApps: jest.Mock }).getApps;

  beforeEach(() => getCrashlytics.mockClear());

  test('the build says no Firebase: no reporter, and the SDK is never constructed', () => {
    expect(nativeCrashlytics(false)).toBeNull();
    expect(getCrashlytics).not.toHaveBeenCalled();
  });

  test('no default Firebase app was created natively: no reporter, nothing constructed, nothing thrown', () => {
    getApps.mockReturnValueOnce([]);
    expect(nativeCrashlytics(true)).toBeNull();
    expect(getCrashlytics).not.toHaveBeenCalled();
  });

  test('the module is not linked (require throws): no reporter, nothing thrown', () => {
    getApps.mockImplementationOnce(() => {
      throw new Error("You attempted to use a firebase module that's not installed natively");
    });
    expect(nativeCrashlytics(true)).toBeNull();
  });

  test('Android push is off without Firebase (no FCM); iOS push needs no Firebase file', () => {
    expect(pushAvailable('android', nativeConfig({ firebaseConfigured: false }))).toBe(false);
    expect(pushAvailable('ios', nativeConfig({ firebaseConfigured: false }))).toBe(true);
    expect(pushAvailable('android', nativeConfig({ firebaseConfigured: true }))).toBe(true);
  });

  test('push off: the registrar never asks the platform for a token and registers nothing', async () => {
    const getToken = Notifications.getDevicePushTokenAsync as jest.Mock;
    getToken.mockClear();
    const registerDevice = jest.fn();
    const r = createPushRegistrar({
      session: {
        snapshot: () => ({ phase: 'signedIn', active: { tenant: 't', technicianId: 'u' } }) as never,
        subscribe: () => () => undefined,
        courierAccessToken: () => 'access',
      },
      api: { registerDevice },
      deviceId: async () => 'd',
      deviceName: async () => 'Van 14',
      allowed: async () => true,
      pushToken: async () => null,
    });
    await expect(r.tryNow()).resolves.toBe(false);
    r.stop();
    expect(getToken).not.toHaveBeenCalled();
    expect(registerDevice).not.toHaveBeenCalled();
  });
});

describe('no Google Maps key', () => {
  test('Android without a key: the native map is never made, so the placeholder stays', () => {
    const make = jest.fn(() => 'esri');
    expect(mapViewFor('android', nativeConfig(buildConfig(base, NOTHING).extra), make)).toBeUndefined();
    expect(make).not.toHaveBeenCalled();
  });

  test('Android with a key, and iOS always: the Esri map', () => {
    expect(mapViewFor('android', nativeConfig(buildConfig(base, EVERYTHING).extra), () => 'esri')).toBe('esri');
    expect(mapViewFor('ios', nativeConfig(buildConfig(base, NOTHING).extra), () => 'esri')).toBe('esri');
  });
});

describe('over-the-air updates are off until an update server is configured', () => {
  const none = { exists: () => false, env: {} };
  test('no updates.url → runtime pinned to the version, updates disabled', () => {
    const out = buildConfig({ name: 'x', slug: 'x', version: '2.594.1', runtimeVersion: { policy: 'fingerprint' }, updates: { enabled: true } } as never, none);
    expect(out.runtimeVersion).toBe('2.594.1');
    expect(out.updates?.enabled).toBe(false);
  });
  test('with updates.url → the fingerprint policy stands', () => {
    const out = buildConfig({ name: 'x', slug: 'x', version: '2.594.1', runtimeVersion: { policy: 'fingerprint' }, updates: { enabled: true, url: 'https://u.expo.dev/abc' } } as never, none);
    expect(out.runtimeVersion).toEqual({ policy: 'fingerprint' });
    expect(out.updates?.enabled).toBe(true);
  });
});
