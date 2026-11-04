/**
 * The app root's ONE data provider (`session/FieldRuntime.tsx`): it opens the
 * signed-in technician's tenant store at sign-in and closes it at sign-out,
 * signing out deletes nothing unsent, *Send now* sends each item under its
 * captor's own credential and tells telemetry's gate, a turned-in route is
 * told to the server with the next run, and every wave's provider is fed from
 * the same store. And `App` installs telemetry's global crash handler.
 *
 * Mounted the way the app mounts it: a real `SessionManager` whose outbox
 * port is the store holder's, under `SessionProvider` and the i18n provider.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, render, screen, waitFor } from '@testing-library/react-native';
import { forwardRef, type ReactNode, useImperativeHandle } from 'react';
import { Text } from 'react-native';

import App from '../../src/App';
import * as outboxQ from '../../src/db/queries/outbox';
import * as routeQ from '../../src/db/queries/route';
import { scoped } from '../../src/db/scoped';
import { StoreHolder, storeOutboxPort } from '../../src/db/storeHolder';
import { FakeNetwork, UNWIRED_DEVICE } from '../../src/device';
import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { useOptionalReads } from '../../src/screens/reads/services';
import { useJobPort } from '../../src/screens/theJob/JobPort';
import { useFieldData } from '../../src/screens/theDay/fieldData';
import { DeviceRegister } from '../../src/security/deviceRegister';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { MemorySecretStore } from '../../src/security/secretStore';
import { FieldRuntime, type FieldRuntimeValue, useFieldRuntime } from '../../src/session/FieldRuntime';
import { PasswordVerifier } from '../../src/session/passwordVerifier';
import { SessionProvider } from '../../src/session/SessionProvider';
import { SessionManager } from '../../src/session/sessionManager';
import { capture } from '../../src/sync/outbox';
import { wakeRoutes } from '../../src/sync/routeWake';
import type { RouteStopsPage, RoutesApi, RoutesPage, TurnInBody } from '../../src/sync/routes';
import { createMemoryStore, createTelemetry } from '../../src/telemetry';
import { ManualClock } from '../../src/security/clock';
import { memoryFactory } from '../db/support/nodeDriver';
import { MemoryFiles } from '../db/support/fixtures';
import { FakeAuthApi, PEOPLE, SHIFT_START, TENANT } from './fakes';
import { FakeServer } from '../sync/support/fakeServer';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

class FakeRoutesServer extends FakeServer implements RoutesApi {
  readonly turnIns: Array<{ routeId: string; body: TurnInBody }> = [];
  myRoutes(): Promise<RoutesPage> {
    return Promise.resolve({ results: [], next_page: null });
  }
  routePage(): Promise<RouteStopsPage> {
    return Promise.reject(new Error('not asked'));
  }
  turnIn(routeId: string, body: TurnInBody): Promise<unknown> {
    this.turnIns.push({ routeId, body });
    return Promise.resolve({ ok: true });
  }
  cantReadReasons() {
    return Promise.resolve({ results: [] });
  }
}

/** What the runtime offers, reached from inside the tree the app mounts. */
const Probe = forwardRef<{ runtime: FieldRuntimeValue | null; turnIn: ((id: string) => void) | undefined }>(function Probe(_props, ref) {
  const runtime = useFieldRuntime();
  const reads = useOptionalReads();
  const job = useJobPort();
  const day = useFieldData();
  useImperativeHandle(ref, () => ({ runtime, turnIn: reads?.services.turnInRoute }), [runtime, reads]);
  return (
    <>
      <Text testID="probe-store">{runtime?.db ? runtime.db.tenant : 'no store'}</Text>
      <Text testID="probe-waves">{[reads ? 'reads' : '', job ? 'job' : '', day.db ? 'day' : ''].filter(Boolean).join(',')}</Text>
    </>
  );
});

function setup(network = new FakeNetwork('wifi')) {
  const clock = new ManualClock(SHIFT_START);
  const secrets = new MemorySecretStore();
  const prefs = new MemoryKeyValueStore();
  const factory = memoryFactory();
  const holder = new StoreHolder(factory, { now: () => new Date(clock.now()).toISOString() });
  const api = new FakeAuthApi();
  let n = 0;
  const device = new DeviceRegister(secrets, () => `device-${(n += 1)}`);
  const verifier = new PasswordVerifier(secrets, async (s) => `h-${s}`, () => 'salt');
  const session = new SessionManager({ api, secrets, prefs, clock, device, verifier, outbox: storeOutboxPort(holder) });
  const server = new FakeRoutesServer();
  const telemetry = createTelemetry({ store: createMemoryStore(), analytics: { send: async () => undefined }, identity: () => null });
  let ids = 0;
  const deps = {
    holder,
    session,
    prefs,
    device: UNWIRED_DEVICE,
    network,
    transportFor: () => server,
    files: new MemoryFiles(),
    telemetry,
    newId: () => `id-${(ids += 1)}`,
    now: () => new Date(clock.now()),
    syncEveryMs: 60 * 60 * 1000,
  };
  const ref: { current: { runtime: FieldRuntimeValue | null; turnIn: ((id: string) => void) | undefined } | null } = { current: null };
  const Wrapper = ({ children }: { children?: ReactNode }) => (
    <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={prefs}>
      <SessionProvider manager={session}>
        <FieldRuntime deps={deps}>
          <Probe ref={ref} />
          {children}
        </FieldRuntime>
      </SessionProvider>
    </I18nProvider>
  );
  return { clock, holder, factory, session, server, telemetry, prefs, network, ref, Wrapper };
}

const signIn = (session: SessionManager, login = 'd.ortiz') =>
  session.signIn({ tenant: TENANT, login, password: PEOPLE[login]!.password });

describe('the app root’s data provider', () => {
  test('mounts the technician’s tenant store after sign-in, feeds every wave from it, and closes it at sign-out', async () => {
    const t = setup();
    render(<t.Wrapper />);
    expect(screen.getByTestId('probe-store')).toHaveTextContent('no store');
    expect(t.holder.current).toBeNull();

    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(screen.getByTestId('probe-store')).toHaveTextContent(TENANT));
    expect([...t.factory.files.keys()]).toEqual([`field-${TENANT}.sqlite`]);
    expect(t.holder.current?.tenant).toBe(TENANT);
    expect(screen.getByTestId('probe-waves')).toHaveTextContent('reads,job,day');

    await act(async () => {
      await t.session.signOut();
    });
    await waitFor(() => expect(screen.getByTestId('probe-store')).toHaveTextContent('no store'));
    expect(t.holder.current).toBeNull();
    expect(screen.getByTestId('probe-waves')).toHaveTextContent('');
  });

  test('signing out deletes nothing unsent: the work is there, unsent, when the store opens again', async () => {
    const t = setup(new FakeNetwork('none'));
    render(<t.Wrapper />);
    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(t.holder.current).not.toBeNull());
    const db = t.holder.current!;
    const dana = PEOPLE['d.ortiz']!.technicianId;
    const deps = { newId: () => 'k-1', clock: { now: () => new Date(SHIFT_START) } };
    const k = capture(db, { technicianId: dana, capturedBy: dana }, { kind: 'reading', workOrderId: 'wo-1', payload: { value: '52410' } }, deps);
    expect((await t.session.unsentSummary()).mine).toEqual({ items: 1, photos: 0 });

    await act(async () => {
      await t.session.signOut();
    });
    expect(t.holder.current).toBeNull();

    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(t.holder.current).not.toBeNull());
    expect(outboxQ.getMine(scoped(t.holder.current!, dana), k.key)).toMatchObject({ state: 'pending' });
    expect((await t.session.unsentSummary()).mine).toEqual({ items: 1, photos: 0 });
  });

  test('Send now sends under the captor’s own capture credential and tells the gate the queue is clear', async () => {
    const t = setup();
    render(<t.Wrapper />);
    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(t.ref.current?.runtime?.db).toBeTruthy());
    const dana = PEOPLE['d.ortiz']!.technicianId;
    const db = t.holder.current!;
    capture(db, { technicianId: dana, capturedBy: dana }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: () => 'k-9', clock: { now: () => new Date(SHIFT_START) } });

    await act(async () => {
      await t.ref.current!.runtime!.syncNow();
    });
    const token = t.session.captureCredentialOf(dana)?.serverToken;
    expect(token).toBeTruthy();
    expect(t.server.applied.map((a) => [a.key, a.captor])).toEqual([['k-9', token]]);
    expect(t.telemetry.gate.reason()).toBe('clear');
    expect(t.ref.current!.runtime!.status).toMatchObject({ syncPending: 0, connection: 'online' });
  });

  test('a route turned in on RW-25 is told to the server with the next run, with every capture key on it', async () => {
    const t = setup();
    render(<t.Wrapper />);
    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(t.ref.current?.turnIn).toBeTruthy());
    const dana = PEOPLE['d.ortiz']!.technicianId;
    routeQ.upsert(scoped(t.holder.current!, dana), { id: 'wlk-07', code: 'WLK-07' }, new Date(SHIFT_START).toISOString());
    t.ref.current!.turnIn!('wlk-07');
    await act(async () => {
      await t.ref.current!.runtime!.syncNow();
    });
    expect(t.server.turnIns).toHaveLength(1);
    expect(t.server.turnIns[0]).toMatchObject({ routeId: 'wlk-07', body: { keys: [], counts: { done: 0 } } });
    // Told once: the queue is empty after the answer.
    await act(async () => {
      await t.ref.current!.runtime!.syncNow();
    });
    expect(t.server.turnIns).toHaveLength(1);
  });

  test('a route-change push downloads the routes: a route the office took away leaves the phone (DEF-MET-10606)', async () => {
    const t = setup();
    render(<t.Wrapper />);
    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(t.ref.current?.runtime?.db).toBeTruthy());
    const dana = PEOPLE['d.ortiz']!.technicianId;
    routeQ.upsert(scoped(t.holder.current!, dana), { id: 'rt-002', code: 'RT-002' }, new Date(SHIFT_START).toISOString());
    const asked = jest.spyOn(t.server, 'myRoutes');
    await act(async () => {
      expect(wakeRoutes({ kind: 'route_change', tenant: TENANT, lost: '1', route: 'RT-002' })).toBe(1);
    });
    await waitFor(() => expect(asked).toHaveBeenCalled());
    await waitFor(() => expect(routeQ.listMine(scoped(t.holder.current!, dana)).map((r) => r.id)).toEqual([]));
  });

  test('with no signal, Send now sends nothing, loses nothing, and the gate is told the handset is offline', async () => {
    const t = setup(new FakeNetwork('none'));
    render(<t.Wrapper />);
    await act(async () => {
      await signIn(t.session);
    });
    await waitFor(() => expect(t.ref.current?.runtime?.db).toBeTruthy());
    const dana = PEOPLE['d.ortiz']!.technicianId;
    capture(t.holder.current!, { technicianId: dana, capturedBy: dana }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: () => 'k-3', clock: { now: () => new Date(SHIFT_START) } });
    await act(async () => {
      await t.ref.current!.runtime!.syncNow();
    });
    expect(t.server.requests).toHaveLength(0);
    expect(t.telemetry.gate.reason()).toBe('offline');
    expect(t.ref.current!.runtime!.status).toMatchObject({ syncPending: 1, connection: 'offline' });
  });
});

test('App installs telemetry’s global crash handler, which records and then hands on', async () => {
  let installed: ((error: unknown, isFatal?: boolean) => void) | null = null;
  const previous = jest.fn();
  const errorUtils = {
    getGlobalHandler: () => previous,
    setGlobalHandler: (h: (error: unknown, isFatal?: boolean) => void) => {
      installed = h;
    },
  };
  render(
    <App
      overrides={{ secrets: new MemorySecretStore(), api: new FakeAuthApi(), driver: memoryFactory(), network: new FakeNetwork('none') }}
      errorUtils={errorUtils}
      appState={{ addEventListener: () => ({ remove: () => undefined }) }}
    />,
  );
  expect(await screen.findByTestId('screen-FF-01')).toBeTruthy();
  expect(installed).not.toBeNull();
  installed!(new Error('boom'), true);
  expect(previous).toHaveBeenCalledWith(expect.any(Error), true);
});
