/**
 * CERTIFICATE PINNING (`OQ-FLD-12797`, PO 2026-10-24: *"plese dont hardcode
 * it use settings - security values set in staff portal"*).
 *
 * What is proved here:
 *  - the set the build STARTS with comes from its config (`extra.pins`, or the
 *    build's `FIELD_APP_PINS`), not from code;
 *  - the server's list REPLACES it only when it arrived over a connection that
 *    was already pinned;
 *  - a list that is empty, malformed, expired, too short, or shares no key with
 *    the set in force is refused, and the LAST GOOD SET is kept;
 *  - the app pins before its first request, and every sync run reads the
 *    office's list (built is not wired — hard-won law 2).
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a controller that reports `enforced`
 * without the native module having been called. Each `enforced` assertion
 * below is paired with the module's own call record.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, render, waitFor } from '@testing-library/react-native';
import { forwardRef, useImperativeHandle } from 'react';
import { readFileSync } from 'fs';
import { join } from 'path';
import type { ExpoConfig } from 'expo/config';

import appJson from '../../app.json';
import { buildConfig, pinsFromEnv } from '../../app.config';
import { StoreHolder, storeOutboxPort } from '../../src/db/storeHolder';
import { FakeNetwork, UNWIRED_DEVICE } from '../../src/device';
import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { ManualClock } from '../../src/security/clock';
import { DeviceRegister } from '../../src/security/deviceRegister';
import { hostOf, PinningController, type PinningNative, PinStore, type SettingsApi } from '../../src/security/pinning';
import { bootstrapPins, decideAdoption, type Pin } from '../../src/security/pins';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { MemorySecretStore } from '../../src/security/secretStore';
import { FieldRuntime, type FieldRuntimeValue, useFieldRuntime } from '../../src/session/FieldRuntime';
import { PasswordVerifier } from '../../src/session/passwordVerifier';
import { createAppServices } from '../../src/session/services';
import { SessionProvider } from '../../src/session/SessionProvider';
import { SessionManager } from '../../src/session/sessionManager';
import { createMemoryStore, createTelemetry } from '../../src/telemetry';
import { memoryFactory } from '../db/support/nodeDriver';
import { MemoryFiles } from '../db/support/fixtures';
import { FakeAuthApi, PEOPLE, SHIFT_START, TENANT } from '../session/fakes';
import { FakeServer } from '../sync/support/fakeServer';

const X1: Pin = { spki_sha256: 'C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=', label: 'ISRG Root X1', not_after: '2035-06-04' };
const GTS: Pin = { spki_sha256: 'hxqRlPTu1bMS/0DITB1SSu0vd4u/8l8TjPgfaAp63Gc=', label: 'GTS Root R1', not_after: '2036-06-22' };
const X2: Pin = { spki_sha256: 'diGVwiVYbubAI3RW4hB9xU8e/CH2GnkuvVFZE8zmgzI=', label: 'ISRG Root X2', not_after: '2040-09-17' };
const G2: Pin = { spki_sha256: 'i7WTqTvh0OioIruIfFR4kMPnBqrS2rdiVPl/s2uC/CY=', label: 'DigiCert G2', not_after: '2038-01-15' };
const TODAY = '2026-10-24';
const NOW = () => new Date('2026-10-24T12:00:00Z');
const ORIGIN = 'https://field.smartbillhub.example';

function fakeNative(available = true) {
  const calls: Parameters<PinningNative['initialize']>[0][] = [];
  const native: PinningNative = {
    isAvailable: () => available,
    initialize: async (options) => {
      calls.push(options);
    },
  };
  return { native, calls };
}

function controller(opts: { available?: boolean; stored?: Pin[]; bootstrap?: Pin[]; origin?: string } = {}) {
  const kv = new MemoryKeyValueStore();
  const store = new PinStore(kv);
  if (opts.stored) store.write(opts.stored);
  const { native, calls } = fakeNative(opts.available ?? true);
  const c = new PinningController({ native, store, bootstrap: opts.bootstrap ?? [X1, GTS], origin: opts.origin ?? ORIGIN, now: NOW, mode: 'on' });
  return { c, store, kv, calls };
}

const serverList = (list: unknown): SettingsApi => ({ settings: async () => ({ field_app_pins: list }) });

describe('the starting set is config, never code', () => {
  test("app.json's documented default: the current issuer and one backup issuer", () => {
    const base = (appJson as unknown as { expo: Partial<ExpoConfig> }).expo;
    const extra = buildConfig(base, { exists: () => false, env: {} }).extra;
    expect(bootstrapPins(extra)).toEqual([X1, GTS]);
  });

  test("the build's FIELD_APP_PINS replaces it", () => {
    const base = (appJson as unknown as { expo: Partial<ExpoConfig> }).expo;
    const env = { FIELD_APP_PINS: JSON.stringify([X2, G2]) };
    expect(bootstrapPins(buildConfig(base, { exists: () => false, env }).extra)).toEqual([X2, G2]);
  });

  test('a malformed FIELD_APP_PINS fails the build rather than shipping a phone pinned to nothing', () => {
    expect(() => pinsFromEnv({ FIELD_APP_PINS: 'nope' })).toThrow();
    expect(() => pinsFromEnv({ FIELD_APP_PINS: JSON.stringify([X1]) })).toThrow();
    expect(() => pinsFromEnv({ FIELD_APP_PINS: JSON.stringify([X1, { ...GTS, spki_sha256: 'short' }]) })).toThrow();
  });

  test('no key is typed into the source: the hashes live in app.json and nowhere under src/', () => {
    for (const file of ['pins.ts', 'pinning.ts']) {
      const text = readFileSync(join(__dirname, '../../src/security', file), 'utf8');
      expect(text).not.toContain(X1.spki_sha256);
      expect(text).not.toContain(GTS.spki_sha256);
    }
  });
});

describe('decideAdoption', () => {
  const current = [X1, GTS];

  test('replaces the set only over a pinned connection', () => {
    expect(decideAdoption({ current, incoming: [X1, GTS, X2], arrivedPinned: false, today: TODAY })).toEqual({ adopt: false, reason: 'not_pinned' });
    expect(decideAdoption({ current, incoming: [X1, GTS, X2], arrivedPinned: true, today: TODAY })).toEqual({ adopt: true, pins: [X1, GTS, X2] });
  });

  test('refuses an empty list', () => {
    expect(decideAdoption({ current, incoming: [], arrivedPinned: true, today: TODAY })).toEqual({ adopt: false, reason: 'too_few' });
  });

  test('refuses a list whose keys have expired', () => {
    const expired = [{ ...X1, not_after: '2026-10-23' }, { ...GTS, not_after: '2025-01-01' }];
    expect(decideAdoption({ current, incoming: expired, arrivedPinned: true, today: TODAY })).toEqual({ adopt: false, reason: 'too_few' });
  });

  test('drops an expired key but adopts the rest when two good ones remain', () => {
    const mixed = [X1, GTS, { ...X2, not_after: '2026-01-01' }];
    const answer = decideAdoption({ current: [X1, G2], incoming: mixed, arrivedPinned: true, today: TODAY });
    expect(answer).toEqual({ adopt: true, pins: [X1, GTS] });
  });

  test('refuses a malformed list — one bad entry spoils it', () => {
    for (const bad of [null, 'x', [X1, { ...GTS, spki_sha256: 'nope' }], [X1, { ...GTS, not_after: '22/06/2036' }]]) {
      expect(decideAdoption({ current, incoming: bad, arrivedPinned: true, today: TODAY })).toEqual({ adopt: false, reason: 'malformed' });
    }
  });

  test('refuses a list sharing no key with the set in force', () => {
    expect(decideAdoption({ current, incoming: [X2, G2], arrivedPinned: true, today: TODAY })).toEqual({ adopt: false, reason: 'no_common_key' });
  });

  test('says when nothing changed', () => {
    expect(decideAdoption({ current, incoming: [GTS, X1], arrivedPinned: true, today: TODAY })).toEqual({ adopt: false, reason: 'unchanged' });
  });
});

describe('PinningController', () => {
  test('pins the server host with the starting set when nothing is stored', async () => {
    const t = controller();
    expect(await t.c.start()).toBe('enforced');
    expect(t.calls).toEqual([
      { 'field.smartbillhub.example': { includeSubdomains: false, publicKeyHashes: [X1.spki_sha256, GTS.spki_sha256], expirationDate: '2036-06-22' } },
    ]);
  });

  test('replaces the set from the server over a pinned connection, stores it and re-pins', async () => {
    const t = controller();
    await t.c.start();
    const answer = await t.c.refresh(serverList([X1, GTS, X2]));
    expect(answer).toEqual({ adopt: true, pins: [X1, GTS, X2] });
    expect(t.store.read()).toEqual([X1, GTS, X2]);
    expect(t.calls.at(-1)!['field.smartbillhub.example']!.publicKeyHashes).toEqual([X1.spki_sha256, GTS.spki_sha256, X2.spki_sha256]);
    expect(t.c.current()).toEqual([X1, GTS, X2]);
  });

  test('without the native module nothing is pinned, so the server list is NEVER adopted', async () => {
    const t = controller({ available: false });
    expect(await t.c.start()).toBe('unavailable');
    expect(await t.c.refresh(serverList([X1, GTS, X2]))).toEqual({ adopt: false, reason: 'not_pinned' });
    expect(t.store.read()).toBeNull();
    expect(t.c.current()).toEqual([X1, GTS]);
    expect(t.calls).toEqual([]);
  });

  test('keeps the last good set when the server sends an empty or expired list', async () => {
    const t = controller({ stored: [X1, GTS, X2] });
    await t.c.start();
    expect(await t.c.refresh(serverList([]))).toEqual({ adopt: false, reason: 'too_few' });
    expect(await t.c.refresh(serverList([{ ...X1, not_after: '2026-01-01' }, { ...GTS, not_after: '2026-01-01' }]))).toEqual({
      adopt: false,
      reason: 'too_few',
    });
    expect(t.store.read()).toEqual([X1, GTS, X2]);
    expect(t.c.current()).toEqual([X1, GTS, X2]);
    expect(t.calls).toHaveLength(1); // only the start
  });

  test('a stored list that is garbage falls back to the starting set, never to nothing', async () => {
    const t = controller();
    t.kv.set('security.pins.v1', '{not json');
    expect(t.c.current()).toEqual([X1, GTS]);
    expect(await t.c.start()).toBe('enforced');
  });

  test('a starting set with fewer than two live keys is reported, not pinned to', async () => {
    const t = controller({ bootstrap: [X1, { ...GTS, not_after: '2020-01-01' }] });
    expect(await t.c.start()).toBe('no_valid_pins');
    expect(t.calls).toEqual([]);
  });

  test('no server address, no host to pin', async () => {
    expect(hostOf('https://a.example:8443/api')).toBe('a.example');
    expect(hostOf('')).toBeNull();
    const t = controller({ origin: '' });
    expect(await t.c.start()).toBe('no_host');
  });
});

describe('wired into the app', () => {
  test('createAppServices does NOT pin when the build config does not switch it on (dormant, CR-195-BRC10)', async () => {
    const { native, calls } = fakeNative(true);
    const before = process.env.EXPO_PUBLIC_API_BASE_URL;
    process.env.EXPO_PUBLIC_API_BASE_URL = ORIGIN;
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => undefined);
    try {
      const services = await createAppServices({
        secrets: new MemorySecretStore(),
        api: new FakeAuthApi(),
        driver: memoryFactory(),
        network: new FakeNetwork('none'),
        pinningNative: native,
        extra: { pins: [X2, G2], pinning: 'off' },
      });
      expect(services.pinning.state).toBe('off_by_config');
      expect(calls).toEqual([]);
    } finally {
      warn.mockRestore();
      process.env.EXPO_PUBLIC_API_BASE_URL = before;
    }
  });

  test('createAppServices pins before anything else when the build config says on', async () => {
    const { native, calls } = fakeNative(true);
    const before = process.env.EXPO_PUBLIC_API_BASE_URL;
    process.env.EXPO_PUBLIC_API_BASE_URL = ORIGIN;
    try {
      const services = await createAppServices({
        secrets: new MemorySecretStore(),
        api: new FakeAuthApi(),
        driver: memoryFactory(),
        network: new FakeNetwork('none'),
        pinningNative: native,
        extra: { pins: [X2, G2], pinning: 'on' },
      });
      expect(services.pinning.state).toBe('enforced');
      expect(calls[0]!['field.smartbillhub.example']!.publicKeyHashes).toEqual([X2.spki_sha256, G2.spki_sha256]);
    } finally {
      process.env.EXPO_PUBLIC_API_BASE_URL = before;
    }
  });

  test('App hands the services’ pinning to the runtime', () => {
    const app = readFileSync(join(__dirname, '../../src/App.tsx'), 'utf8');
    expect(app).toContain('pinning: services.pinning');
  });

  test('every sync run reads the office’s list through the runtime', async () => {
    class SettingsServer extends FakeServer {
      asked = 0;
      settings() {
        this.asked += 1;
        return Promise.resolve({ field_app_pins: [X1, GTS, X2] });
      }
    }
    const clock = new ManualClock(SHIFT_START);
    const secrets = new MemorySecretStore();
    const prefs = new MemoryKeyValueStore();
    const holder = new StoreHolder(memoryFactory(), { now: () => new Date(clock.now()).toISOString() });
    let n = 0;
    const device = new DeviceRegister(secrets, () => `device-${(n += 1)}`);
    const verifier = new PasswordVerifier(secrets, async (s) => `h-${s}`, () => 'salt');
    const session = new SessionManager({ api: new FakeAuthApi(), secrets, prefs, clock, device, verifier, outbox: storeOutboxPort(holder) });
    const server = new SettingsServer();
    const seen: SettingsApi[] = [];
    const pinning = { refresh: async (api: SettingsApi) => void seen.push(api) };
    const ref: { current: { value: FieldRuntimeValue | null } | null } = { current: null };
    const Probe = forwardRef<{ value: FieldRuntimeValue | null }>(function Probe(_p, r) {
      const runtime = useFieldRuntime();
      useImperativeHandle(r, () => ({ value: runtime }), [runtime]);
      return null;
    });
    render(
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={prefs}>
        <SessionProvider manager={session}>
          <FieldRuntime
            deps={{
              holder,
              session,
              prefs,
              device: UNWIRED_DEVICE,
              network: new FakeNetwork('wifi'),
              transportFor: () => server as never,
              files: new MemoryFiles(),
              telemetry: createTelemetry({ store: createMemoryStore(), analytics: { send: async () => undefined }, identity: () => null }),
              newId: () => 'id',
              now: () => new Date(clock.now()),
              syncEveryMs: 60 * 60 * 1000,
              pinning,
            }}
          >
            <Probe ref={ref} />
          </FieldRuntime>
        </SessionProvider>
      </I18nProvider>,
    );
    await act(async () => {
      await session.signIn({ tenant: TENANT, login: 'd.ortiz', password: PEOPLE['d.ortiz']!.password });
    });
    await waitFor(() => expect(ref.current?.value?.db).toBeTruthy());
    seen.length = 0;
    await act(async () => {
      await ref.current!.value!.syncNow();
    });
    expect(seen).toHaveLength(1);
    expect(await seen[0]!.settings()).toEqual({ field_app_pins: [X1, GTS, X2] });
  });
});
