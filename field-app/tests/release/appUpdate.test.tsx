/**
 * DEF-FLD-10355 — the minimum-version refusal, handset half (07-endpoints N7,
 * R117, 15-release-and-rollback.md §5.3).
 *
 *  - both HTTP clients send the build on every request;
 *  - a 426 `app_too_old` raises the one signal and *Update the app* covers the
 *    navigator — with a store button only when the store address is known;
 *  - UNSENT WORK IS KEPT: a refused batch stays pending with no attempt
 *    counted, and sends once the server accepts it (after the update);
 *  - the schema version the server stamps on its answers reaches `delta.ts`,
 *    which refuses a version this build does not know.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: treating the 426 as an ordinary 4xx. It
 * is one, so without the `app_too_old` branch in `receipts.ts` every queued
 * item would be marked `refused` — the "kept" case below fails on exactly that
 * (red proof recorded in the lane report: `Expected "pending", Received
 * "refused"`).
 */
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import * as outboxQ from '../../src/db/queries/outbox';
import { scoped } from '../../src/db/scoped';
import { FIELD_KEYS_EN } from '../../src/i18n/catalogues';
import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import {
  BUILD_HEADER,
  createUpdateSignal,
  fieldAppHeaders,
  PLATFORM_HEADER,
  tooOldMinimum,
  VERSION_HEADER,
} from '../../src/release/appUpdate';
import { PRODUCT_VERSION } from '../../src/release/build';
import { storeUrlFor } from '../../src/release/stores';
import { UpdateRequiredGate } from '../../src/release/UpdateRequiredGate';
import { OfflineError } from '../../src/security/authApi';
import { createHttpAuthApi } from '../../src/security/httpAuthApi';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { pullChanges, UnknownSchemaVersionError } from '../../src/sync/delta';
import { SyncEngine } from '../../src/sync/engine';
import { capture, sendPending } from '../../src/sync/outbox';
import { HttpTransport, TransportError } from '../../src/sync/transport';
import { ThemeProvider } from '../../src/theme';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from '../sync/support/fakeServer';

const TOO_OLD = {
  code: null,
  message_key: 'errors.biz-state',
  params: { reason: 'app_too_old', minimum: '2.600.0', version: '2.590.0' },
  field_errors: [],
  br_ref: 'BR-FLD-00117',
  trace_id: 't',
};

const HEADERS = { [VERSION_HEADER]: '2.590.0', [BUILD_HEADER]: '7', [PLATFORM_HEADER]: 'ios' };

function reply(status: number, body: unknown, headers: Record<string, string> = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: { get: (name: string) => headers[name] ?? null },
  };
}

describe('what every request carries', () => {
  test('the product version, the binary build and the platform — a missing one left out, never made up', () => {
    expect(fieldAppHeaders('2.590.0', '7', 'android')).toEqual({ [VERSION_HEADER]: '2.590.0', [BUILD_HEADER]: '7', [PLATFORM_HEADER]: 'android' });
    expect(fieldAppHeaders('2.590.0', null, null)).toEqual({ [VERSION_HEADER]: '2.590.0' });
    expect(fieldAppHeaders()[VERSION_HEADER]).toBe(PRODUCT_VERSION);
  });

  test('the sync transport sends them, beside the bearer', async () => {
    const calls: RequestInit[] = [];
    const fetchImpl = jest.fn(async (_url: string, init: RequestInit) => {
      calls.push(init);
      return reply(200, { changes: [], count: 0, next_cursor: null, has_more: false });
    });
    const t = new HttpTransport({ origin: 'https://x', tenant: 'north', accessToken: () => 'acc', fetchImpl: fetchImpl as unknown as typeof fetch, appHeaders: () => HEADERS });
    await t.changes(null, 50);
    await t.sendJobBatch('wo-1', []);
    for (const init of calls) expect(init.headers).toMatchObject({ ...HEADERS, Authorization: 'Bearer acc' });
  });

  test('sign-in sends them too', async () => {
    const calls: RequestInit[] = [];
    const fetchImpl = jest.fn(async (_url: string, init: RequestInit) => {
      calls.push(init);
      return reply(201, { access_token: 'a', refresh_token: 'r', expires_in: 3600, user: { id: 'u', display_name: 'D', role: 'x' } });
    });
    const api = createHttpAuthApi({ baseUrl: 'https://x', fetchImpl: fetchImpl as unknown as typeof fetch, appHeaders: () => HEADERS });
    await api.signIn({ tenant: 'north', login: 'd@x', password: 'pw', deviceId: 'dev' });
    expect(calls[0]?.headers).toMatchObject(HEADERS);
  });
});

describe('the refusal', () => {
  test('only a 426 naming app_too_old counts', () => {
    expect(tooOldMinimum(426, TOO_OLD)).toBe('2.600.0');
    expect(tooOldMinimum(426, { params: { reason: 'app_too_old' } })).toBeNull();
    expect(tooOldMinimum(426, { params: { reason: 'other' } })).toBeUndefined();
    expect(tooOldMinimum(409, TOO_OLD)).toBeUndefined();
    expect(tooOldMinimum(426, null)).toBeUndefined();
  });

  test('the sync transport raises the signal and throws app_too_old, not an ordinary 4xx', async () => {
    const seen: (string | null)[] = [];
    const t = new HttpTransport({
      origin: 'https://x',
      tenant: 'north',
      accessToken: () => 'acc',
      fetchImpl: (async () => reply(426, TOO_OLD)) as unknown as typeof fetch,
      onAppTooOld: (m) => seen.push(m),
    });
    await expect(t.changes(null, 50)).rejects.toMatchObject({ kind: 'app_too_old', status: 426 });
    expect(seen).toEqual(['2.600.0']);
  });

  test('sign-in reads it as offline (nothing held is dropped) and raises the signal', async () => {
    const seen: (string | null)[] = [];
    const api = createHttpAuthApi({ baseUrl: 'https://x', fetchImpl: (async () => reply(426, TOO_OLD)) as unknown as typeof fetch, onAppTooOld: (m) => seen.push(m) });
    await expect(api.signIn({ tenant: 'north', login: 'd@x', password: 'pw', deviceId: 'dev' })).rejects.toBeInstanceOf(OfflineError);
    await expect(api.refreshAccess({ tenant: 'north', accessToken: 'a', refreshToken: 'r', deviceId: 'dev' })).rejects.toBeInstanceOf(OfflineError);
    expect(seen).toEqual(['2.600.0', '2.600.0']);
  });
});

describe('unsent work is kept', () => {
  test('a refused build leaves every item pending, counts no attempt, and it sends after the update', async () => {
    const clock = new FakeClock();
    const db = openStore('north', undefined, clock);
    const server = new FakeServer();
    const deps = { newId: idSource('k'), clock };
    const dana = { technicianId: 'dana', capturedBy: 'dana' };
    const a = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    const b = capture(db, dana, { kind: 'reading', workOrderId: 'wo-2', payload: {} }, deps);
    const opts = { clock, tokens: { tokenFor: () => 't' }, random: steadyRandom };

    const send = server.sendJobBatch.bind(server);
    server.sendJobBatch = async () => {
      throw new TransportError('app_too_old', 'HTTP 426 app_too_old', 426, TOO_OLD);
    };
    const refused = await sendPending(db, server, opts);
    expect(refused.stoppedForUpdate).toBe(true);
    expect(refused.refused).toBe(0);
    for (const k of [a, b]) {
      expect(outboxQ.getMine(scoped(db, 'dana'), k.key)).toMatchObject({ state: 'pending', attempts: 0 });
    }

    // The update is installed: the same items, same keys, now land.
    server.sendJobBatch = send;
    const after = await sendPending(db, server, opts);
    expect(after.accepted).toBe(2);
    expect(server.applied.map((x) => x.key).sort()).toEqual([a.key, b.key].sort());
  });

  test('the engine downloads nothing while refused, and still pushes', async () => {
    const clock = new FakeClock();
    const db = openStore('north', undefined, clock);
    const server = new FakeServer();
    capture(db, { technicianId: 'dana', capturedBy: 'dana' }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: idSource(), clock });
    const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: () => 't' }, clock });
    const r = await engine.sync({ technicianId: 'dana', network: 'wifi', skipPull: true });
    expect(r.data.accepted).toBe(1);
    expect(r.pull).toBeNull();
    expect(server.cursorsSeen).toEqual([]);
  });
});

describe('the schema version (R117)', () => {
  test('the header reaches the change feed, and a version this build does not know is refused', async () => {
    const clock = new FakeClock();
    const db = openStore('north', undefined, clock);
    const page = { changes: [], count: 0, next_cursor: null, has_more: false };
    const known = new HttpTransport({ origin: 'https://x', tenant: 'north', accessToken: () => 'a', fetchImpl: (async () => reply(200, page, { 'X-Field-Schema-Version': '1' })) as unknown as typeof fetch });
    expect((await known.changes(null, 50)).schema_version).toBe(1);
    await expect(pullChanges(db, known, 'dana', { clock })).resolves.toMatchObject({ pages: 1 });

    const newer = new HttpTransport({ origin: 'https://x', tenant: 'north', accessToken: () => 'a', fetchImpl: (async () => reply(200, page, { 'X-Field-Schema-Version': '2' })) as unknown as typeof fetch });
    await expect(pullChanges(db, newer, 'dana', { clock })).rejects.toBeInstanceOf(UnknownSchemaVersionError);
  });
});

describe('Update the app', () => {
  const i18n = createFieldI18n({ language: 'en', source: () => FIELD_KEYS_EN });

  function mount(props: { platform: string; urls: { appStore: string; googlePlay: string }; openUrl?: (u: string) => void }) {
    const signal = createUpdateSignal();
    render(
      <ThemeProvider initialMode="light">
        <I18nProvider fieldI18n={i18n} prefs={new MemoryKeyValueStore()}>
          <UpdateRequiredGate signal={signal} {...props}>
            <Text testID="the-app">app</Text>
          </UpdateRequiredGate>
        </I18nProvider>
      </ThemeProvider>,
    );
    return signal;
  }

  test('nothing until refused; then one blocking screen in place of the app', async () => {
    const signal = mount({ platform: 'ios', urls: { appStore: '', googlePlay: '' } });
    expect(screen.getByTestId('the-app')).toBeTruthy();
    expect(screen.queryByTestId('update-required')).toBeNull();

    act(() => signal.raise('2.600.0'));
    expect(screen.queryByTestId('the-app')).toBeNull();
    expect(screen.getByText('Update the app')).toBeTruthy();
    expect(screen.getByText('Your unsent work is kept.')).toBeTruthy();
    expect(screen.getByText('Needs version 2.600.0 or newer.')).toBeTruthy();
  });

  test('no store address yet: the instruction, and no button that opens nothing', async () => {
    const signal = mount({ platform: 'android', urls: { appStore: '', googlePlay: '' } });
    act(() => signal.raise(null));
    expect(screen.getByTestId('update-required-instruction')).toBeTruthy();
    expect(screen.queryByTestId('update-required-store')).toBeNull();
    expect(screen.queryByTestId('update-required-minimum')).toBeNull();
  });

  test('with the address: a button to this platform’s store', async () => {
    const opened: string[] = [];
    const urls = { appStore: 'https://apps.apple.com/app/id1', googlePlay: 'https://play.google.com/store/apps/details?id=x' };
    const signal = mount({ platform: 'android', urls, openUrl: (u) => opened.push(u) });
    act(() => signal.raise('2.600.0'));
    fireEvent.press(screen.getByText('Open the store'));
    expect(opened).toEqual([urls.googlePlay]);
    expect(storeUrlFor('ios', urls)).toBe(urls.appStore);
    expect(storeUrlFor('web', urls)).toBeNull();
  });

  test('the words keep B14 rule 33’s caps', () => {
    const words = (k: string) => String(FIELD_KEYS_EN[k]).split(/\s+/).length;
    expect(words('field.update.title')).toBeLessThanOrEqual(3);
    expect(words('field.update.openStore')).toBeLessThanOrEqual(3);
    for (const k of ['field.update.tooOld', 'field.update.workKept', 'field.update.needs', 'field.update.fromStore']) {
      expect(words(k)).toBeLessThanOrEqual(6);
    }
  });
});
