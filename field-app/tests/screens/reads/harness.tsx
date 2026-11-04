/**
 * Mounts the REAL navigation tree with the reading services under it — the
 * way the app root will once it provides them — over a fixture store. Never a
 * bare screen: every reads screen is reached by its route address, so a door
 * that builds a wrong address fails here (hard-won law 2's fixture lesson).
 *
 * Adds to `tests/navigation/harness.tsx` exactly the two providers the app
 * root does not mount yet: `ThemeProvider` and `ReadsServicesProvider`.
 */
import { CommonActions, createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, render, screen } from '@testing-library/react-native';
import { View } from 'react-native';

import type { TenantDb } from '../../../src/db/database';
import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AppNavigator } from '../../../src/navigation/AppNavigator';
import { routeTo } from '../../../src/navigation/routing';
import type { ScreenId } from '../../../src/navigation/screens';
import { ShellStatusProvider, UNKNOWN_STATUS } from '../../../src/navigation/ShellStatus';
import type { ReadsParams } from '../../../src/screens/reads/ReadsScreen';
import type { CameraPort, CameraShot, DictationPort, Fix, LocationAccess, LocationPort, ScannerPort } from '../../../src/screens/reads/ports';
import { unavailableDictation } from '../../../src/screens/reads/ports';
import { type ReadsServices, ReadsServicesProvider, type FindingsPort } from '../../../src/screens/reads/services';
import { MemoryKeyValueStore } from '../../../src/security/prefs';
import { SessionProvider } from '../../../src/session/SessionProvider';
import type { CrashCapture } from '../../../src/telemetry/crashReporter';
import { ThemeProvider } from '../../../src/theme';
import type { ThemeName } from '../../../src/theme';
import { FakeClock, idSource, openStore } from '../../db/support/fixtures';
import { makeHandset, signIn } from '../../session/fakes';
import { HERE, NOW, RAY, seedMapleHeights } from './fixture';

export class FakeScanner implements ScannerPort {
  readonly queue: string[] = [];
  constructor(readonly available = true) {}
  scan(): Promise<string | null> {
    return Promise.resolve(this.queue.shift() ?? null);
  }
}

/** The camera's live view, as the real port draws it (FB-002): a view a test can find. */
function FakeCameraLive() {
  return <View testID="fake-camera-live" />;
}

export class FakeCamera implements CameraPort {
  readonly stamps: string[][] = [];
  /** Files a screen handed back to be deleted (a removed or retaken draft photo). */
  readonly discarded: string[] = [];
  readonly Preview = FakeCameraLive;
  private n = 0;
  constructor(readonly available = true) {}
  discard(localPath: string): Promise<void> {
    this.discarded.push(localPath);
    return Promise.resolve();
  }
  take(stamp: readonly string[]): Promise<CameraShot> {
    this.stamps.push([...stamp]);
    this.n += 1;
    return Promise.resolve({ localPath: `file:///photos/p${this.n}.jpg`, sha256: `sha-${this.n}`, bytes: 250_000 });
  }
}

export class FakeLocation implements LocationPort {
  /** FB-003: what `ensureOn` answers — the platform's prompt, already answered. */
  access: LocationAccess = 'on';
  readonly ensureOn = jest.fn(() => Promise.resolve(this.access));
  readonly openSettings = jest.fn(() => Promise.resolve());
  private readonly listeners = new Set<(fix: Fix) => void>();
  constructor(public fix: Fix | null = { ...HERE, fix_at: NOW }) {}
  current(): Promise<Fix | null> {
    return Promise.resolve(this.fix);
  }
  /** The background watch's best fix (the device's `last()`). */
  last(): Fix | null {
    return this.fix;
  }
  subscribe(onFix: (fix: Fix) => void): () => void {
    this.listeners.add(onFix);
    return () => this.listeners.delete(onFix);
  }
  /** A fix arrives from the background watch. */
  emit(fix: Fix): void {
    this.fix = fix;
    for (const l of [...this.listeners]) l(fix);
  }
}

export const nullCrash: CrashCapture = {
  record: () => undefined,
  breadcrumb: () => undefined,
  sendPending: () => Promise.resolve({ sent: 0, failed: 0 } as never),
  pending: () => [],
  droppedCount: () => 0,
  resetDropped: () => undefined,
};

export interface MountOptions {
  theme?: ThemeName;
  tablet?: boolean;
  seed?: (db: TenantDb) => void;
  scanner?: FakeScanner;
  camera?: FakeCamera;
  location?: FakeLocation;
  dictation?: DictationPort;
  db?: TenantDb;
  /** BR-WRK-067 — the finding's online doors; absent is an offline build. */
  findings?: FindingsPort;
}

export async function mountReads(options: MountOptions = {}) {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  const clock = new FakeClock(Date.parse(NOW));
  const db = options.db ?? openStore('silver-creek', undefined, clock);
  if (!options.db) (options.seed ?? ((d) => seedMapleHeights(d)))(db);
  const scanner = options.scanner ?? new FakeScanner();
  const camera = options.camera ?? new FakeCamera();
  const location = options.location ?? new FakeLocation();
  const sent: number[] = [];
  const services: ReadsServices = {
    db,
    technicianId: RAY,
    capturedBy: RAY,
    readerName: 'R. Delacroix',
    clock,
    newId: idSource('k'),
    prefs: new MemoryKeyValueStore(),
    scanner,
    camera,
    location,
    dictation: options.dictation ?? unavailableDictation,
    crash: nullCrash,
    sendNow: () => {
      sent.push(Date.now());
      return Promise.resolve();
    },
    downloadRoutes: null,
    ...(options.findings ? { findings: options.findings } : {}),
  };
  const fieldI18n = createFieldI18n({ language: 'en' });
  const ref = createNavigationContainerRef<ParamListBase>();
  const utils = render(
    <ThemeProvider initialMode={options.theme ?? 'light'}>
      <I18nProvider fieldI18n={fieldI18n} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <ShellStatusProvider value={UNKNOWN_STATUS}>
            <ReadsServicesProvider value={services}>
              <NavigationContainer ref={ref}>
                <AppNavigator tablet={options.tablet ?? false} />
              </NavigationContainer>
            </ReadsServicesProvider>
          </ShellStatusProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>,
  );
  await screen.findByTestId('screen-FF-63');
  // Let the provider's first position read land.
  await act(async () => undefined);

  /** Open a screen by id, with the record it is about — the same address a door builds. */
  const open = async (id: ScreenId, params?: ReadsParams) => {
    const target = routeTo(id);
    const walk = (p: Record<string, unknown> | undefined): Record<string, unknown> | undefined => {
      if (!p) return undefined;
      if (p.params && typeof p.params === 'object') return { ...p, params: walk(p.params as Record<string, unknown>) };
      return { ...p, params };
    };
    await act(async () => {
      ref.dispatch(CommonActions.navigate(target.name, params ? walk(target.params as Record<string, unknown>) : target.params));
    });
    return (await screen.findAllByTestId(`screen-${id}`)).at(-1);
  };

  const current = () => ref.getCurrentRoute()?.name;
  const currentParams = () => ref.getCurrentRoute()?.params as ReadsParams | undefined;
  return { ...utils, ref, db, services, scanner, camera, location, clock, sent, open, current, currentParams };
}
