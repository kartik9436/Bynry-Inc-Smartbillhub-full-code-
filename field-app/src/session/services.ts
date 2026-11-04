/**
 * Builds the app's services from the real platform pieces — the keystore,
 * encrypted MMKV, `expo-crypto`, `expo-localization`, the HTTP auth client —
 * and, since the integration lane, the pieces the ONE data provider
 * (`FieldRuntime.tsx`) needs: the store holder over the expo-sqlite driver,
 * the server transport per tenant, the handset (`src/device`), the network,
 * the file store and telemetry. Each can be overridden, so a test builds the
 * real `App` over better-sqlite3 and fakes.
 */
import * as Crypto from 'expo-crypto';
import type { ComponentType } from 'react';
import { getLocales } from 'expo-localization';

import { StoreHolder, storeOutboxPort } from '../db/storeHolder';
import type { DriverFactory } from '../db/driver';
import { type Device, netInfoNetwork, type NetworkPort, UNWIRED_DEVICE } from '../device';
import { createFieldI18n, type FieldI18n } from '../i18n/i18n';
import { expoFileStore } from '../sync/files';
import type { FileStore } from '../sync/photos';
import type { RoutesApi } from '../sync/routes';
import { HttpTransport, type Transport } from '../sync/transport';
import { type AnalyticsTransport, type CrashReporter, createTelemetry, getOrCreateDeviceId, type Telemetry, telemetryIdentity } from '../telemetry';
import type { PermissionsPort } from '../screens/gettingIn/permissions';
import type { MapViewProps } from '../screens/theDay/mapView';
import { savedLanguage } from '../i18n/I18nProvider';
import { matchLanguage } from '../i18n/languages';
import { serverAddress } from '../release/serverAddress';
import { type AuthApi } from '../security/authApi';
import { type BiometricPort, unavailableBiometric } from '../security/biometric';
import { systemClock } from '../security/clock';
import { DeviceRegister } from '../security/deviceRegister';
import { createHttpAuthApi } from '../security/httpAuthApi';
import Constants from 'expo-constants';

import { nativePinning, type PinningNative, PinningController, PinStore } from '../security/pinning';
import { bootstrapPins, pinningMode } from '../security/pins';
import { type KeyValueStore, openEncryptedPrefs } from '../security/prefs';
import { keystoreSecretStore, type SecretStore } from '../security/secretStore';
import { type OutboxPort } from './outboxPort';
import { PasswordVerifier } from './passwordVerifier';
import { SessionManager } from './sessionManager';

/**
 * A session view of the outbox that REFUSES rather than answering zero —
 * "nothing waiting" on a handset holding a day of work is the one wrong
 * answer this port must never give. The app uses `storeOutboxPort` over the
 * open store; this stays for previews built with no store at all.
 */
export const outboxNotWired: OutboxPort = {
  unsentCounts: () => Promise.reject(new Error('outbox not wired yet (T-10)')),
  dropMirror: () => Promise.reject(new Error('outbox not wired yet (T-10)')),
};

export interface AppServices {
  session: SessionManager;
  fieldI18n: FieldI18n;
  prefs: KeyValueStore;
  device: DeviceRegister;
  api: AuthApi;
  /** The tenant store the app has open (opened at sign-in, closed at sign-out). */
  holder: StoreHolder;
  handset: Device;
  network: NetworkPort;
  transportFor(tenant: string, accessToken: () => string | null): Transport & RoutesApi;
  files: FileStore;
  telemetry: Telemetry;
  newId(): string;
  /** Crashlytics, where the build has it; crash files wait on the handset otherwise. */
  crashReporter?: CrashReporter;
  /** FF-07's real permissions, where the build has them. */
  permissions?: PermissionsPort;
  /** The real map behind FF-13 / FF-14, where the build has one. */
  MapView?: ComponentType<MapViewProps>;
  /** This build has a usable server address (`release/serverAddress.ts`); false → FF-05 says *No server set*. */
  serverSet: boolean;
  /** Certificate pinning (`OQ-FLD-12797`): started before any request; refreshed after each sync. */
  pinning: PinningController;
}

export interface AppServiceOverrides {
  api?: AuthApi;
  outbox?: OutboxPort;
  biometric?: BiometricPort;
  secrets?: SecretStore;
  /** The SQLite driver (the app: expo-sqlite; a test: better-sqlite3). */
  driver?: DriverFactory;
  handset?: Device;
  network?: NetworkPort;
  transportFor?: AppServices['transportFor'];
  files?: FileStore;
  newId?: () => string;
  /** Wraps the preferences store once it is open (the native build watches it for *Keep screen on*). */
  wrapPrefs?: (prefs: KeyValueStore) => KeyValueStore;
  /** The analytics transport, given the telemetry device id; null = none configured. */
  analytics?: (telemetryDeviceId: string) => AnalyticsTransport | null;
  crashReporter?: CrashReporter;
  permissions?: PermissionsPort;
  MapView?: ComponentType<MapViewProps>;
  /** What this handset registers as with the server (`work/mobile/devices`). */
  platform?: 'ios' | 'android';
  /** The pinning module (tests); the app uses `react-native-ssl-public-key-pinning`. */
  pinningNative?: PinningNative;
  /** The build's config `extra` (tests); the app reads `Constants.expoConfig.extra`. */
  extra?: unknown;
}

/** expo-sqlite, loaded only when the app opens a store (a test passes its own driver). */
const lazyExpoDriver: DriverFactory = (fileName) => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { openExpoDriver } = require('../db/drivers/expoSqlite') as typeof import('../db/drivers/expoSqlite');
  return openExpoDriver(fileName);
};

/** No analytics client is configured in this build: events wait in their queue, never lost, never sent. */
const analyticsNotWired = { send: () => Promise.reject(new Error('analytics transport not configured')) };

function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/** A v4 UUID: the platform's, or one built from its random bytes where it has none. */
function uuid(): string {
  const made = (Crypto.randomUUID as (() => string) | undefined)?.();
  if (typeof made === 'string' && made) return made;
  const b = Crypto.getRandomBytes(16);
  b[6] = ((b[6] ?? 0) & 0x0f) | 0x40;
  b[8] = ((b[8] ?? 0) & 0x3f) | 0x80;
  const h = hex(b);
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export async function createAppServices(overrides: AppServiceOverrides = {}): Promise<AppServices> {
  const secrets = overrides.secrets ?? keystoreSecretStore;
  const opened = await openEncryptedPrefs(secrets, (n) => Crypto.getRandomBytes(n));
  const prefs = overrides.wrapPrefs ? overrides.wrapPrefs(opened) : opened;
  // OQ-FLD-12797 — pin BEFORE the first request (a session restore may
  // refresh its token over the network). The set is the server's last
  // adopted list, else the build's starting set from its config.
  const pinning = new PinningController({
    native: overrides.pinningNative ?? nativePinning,
    store: new PinStore(prefs),
    bootstrap: bootstrapPins(overrides.extra !== undefined ? overrides.extra : Constants.expoConfig?.extra),
    // Off only in the beta build (DEF-FLD-10617); a config without the word pins.
    mode: pinningMode(overrides.extra !== undefined ? overrides.extra : Constants.expoConfig?.extra),
    origin: process.env.EXPO_PUBLIC_API_BASE_URL ?? '',
    now: () => new Date(),
  });
  await pinning.start();
  const api =
    overrides.api ?? createHttpAuthApi({ baseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? '', platform: overrides.platform });
  const device = new DeviceRegister(secrets, () => Crypto.randomUUID());
  const verifier = new PasswordVerifier(
    secrets,
    (input) => Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, input),
    () => hex(Crypto.getRandomBytes(16)),
  );
  const holder = new StoreHolder(overrides.driver ?? lazyExpoDriver);
  const session = new SessionManager({
    api,
    secrets,
    prefs,
    clock: systemClock,
    device,
    verifier,
    outbox: overrides.outbox ?? storeOutboxPort(holder),
    biometric: overrides.biometric ?? unavailableBiometric,
  });
  await session.restore();
  const newId = overrides.newId ?? uuid;
  const origin = process.env.EXPO_PUBLIC_API_BASE_URL ?? '';
  const telemetryDevice = getOrCreateDeviceId(prefs, uuid);
  const telemetry = createTelemetry({
    store: prefs,
    analytics: overrides.analytics?.(telemetryDevice) ?? analyticsNotWired,
    identity: () => {
      const snap = session.snapshot();
      const tech = snap.phase === 'signedOut' ? null : snap.active;
      return tech
        ? telemetryIdentity(tech.tenant, 'field_app', telemetryDevice, { id: tech.userId, name: tech.displayName })
        : null;
    },
  });

  const handsetLanguages = getLocales().map((l) => l.languageTag);
  const fieldI18n = createFieldI18n({ language: savedLanguage(prefs) ?? matchLanguage(handsetLanguages) });

  return {
    session,
    fieldI18n,
    prefs,
    device,
    api,
    holder,
    handset: overrides.handset ?? UNWIRED_DEVICE,
    network: overrides.network ?? netInfoNetwork(),
    transportFor:
      overrides.transportFor ?? ((tenant, accessToken) => new HttpTransport({ origin: origin.replace(/\/+$/, ''), tenant, accessToken })),
    files: overrides.files ?? expoFileStore,
    telemetry,
    newId,
    crashReporter: overrides.crashReporter,
    permissions: overrides.permissions,
    MapView: overrides.MapView,
    // A test's own api (and transport) stands in for the server.
    serverSet: overrides.api ? true : serverAddress() !== null,
    pinning,
  };
}
