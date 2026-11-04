/**
 * The tablet suite's handset: ONE fixture store holding every wave's test
 * data — the job boards' world (`screens/onSite/fixture.ts`: WO-4822 and its
 * neighbours, D. Ortiz's day), Maple Heights (`screens/reads/fixture.ts`) on
 * the same technician, WO-4824 closed this morning, and the boards' alerts —
 * mounted under the REAL navigator with every provider the app root mounts
 * (`session/FieldRuntime.tsx`), at the window the test sets.
 *
 * Each test file mocks the window hook to read `tabletWindow` (React Native's
 * hook is a lazy getter that `jest.spyOn` cannot replace):
 *
 *   jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
 *     __esModule: true, default: () => require('./harness').tabletWindow,
 *   }));
 *
 * The app decides phone or tablet from that window, exactly as on a handset;
 * nothing passes `tablet` to the navigator.
 */
import { CommonActions, createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, render, screen } from '@testing-library/react-native';

import * as closedQ from '../../src/db/queries/workOrderClosed';
import { scoped } from '../../src/db/scoped';
import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { AppNavigator } from '../../src/navigation/AppNavigator';
import { routeTo } from '../../src/navigation/routing';
import type { ScreenId } from '../../src/navigation/screens';
import { ShellStatusProvider, type ShellStatusValue, UNKNOWN_STATUS } from '../../src/navigation/ShellStatus';
import { createDbMeData } from '../../src/screens/me/dbData';
import { type MeServices, MeServicesProvider, notWiredServices } from '../../src/screens/me/services';
import { type NearbyPort } from '../../src/screens/theDay/nearbyApi';
import { FieldDataProvider as SiteDataProvider } from '../../src/screens/onSite/fieldData';
import { unavailableDictation } from '../../src/screens/reads/ports';
import { ReadsServicesProvider } from '../../src/screens/reads/services';
import { FieldDataProvider as DayDataProvider } from '../../src/screens/theDay/fieldData';
import { JobPortProvider } from '../../src/screens/theJob/JobPort';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { SessionProvider } from '../../src/session/SessionProvider';
import { ThemeProvider, type ThemeName } from '../../src/theme';
import { idSource } from '../db/support/fixtures';
import { boardAlerts, FakeAlerts } from '../screens/me/support';
import { DANA, local, makeWave, NOW } from '../screens/onSite/fixture';
import { FakeCamera, FakeLocation, FakeScanner, nullCrash } from '../screens/reads/harness';
import { seedMapleHeights } from '../screens/reads/fixture';
import { makeHandset, signIn } from '../session/fakes';

/** The window every screen measures. Tests set it before mounting. */
export const tabletWindow = { width: 1024, height: 768, scale: 2, fontScale: 1 };

export function setWindow(width: number, height: number): void {
  tabletWindow.width = width;
  tabletWindow.height = height;
}

export async function mountTablet(
  options: { theme?: ThemeName; status?: ShellStatusValue; nearby?: NearbyPort; me?: Partial<MeServices> } = {},
) {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  const wave = makeWave();
  const db = wave.db;
  seedMapleHeights(db, { technician: DANA });
  // WO-4824 was closed at 09:58 this morning — FF-35's record.
  closedQ.recordClose(scoped(db, DANA), 'wo-4824', 'passed', local(20, 9, 58));
  const alerts = new FakeAlerts();
  alerts.items = boardAlerts();
  const newId = idSource('t');
  const me = notWiredServices({ data: createDbMeData(db, { newId }), alerts, now: () => NOW, ...options.me });

  const ref = createNavigationContainerRef<ParamListBase>();
  render(
    <ThemeProvider initialMode={options.theme ?? 'light'}>
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <ShellStatusProvider value={options.status ?? UNKNOWN_STATUS}>
            <MeServicesProvider services={me}>
              <DayDataProvider value={options.nearby ? { db, now: () => NOW, nearby: options.nearby } : { db, now: () => NOW }}>
                <JobPortProvider
                  services={{
                    db,
                    captor: () => ({ technicianId: DANA, capturedBy: DANA }),
                    displayName: 'D. Ortiz',
                    clock: wave.clock,
                    newId,
                  }}
                >
                  <SiteDataProvider value={wave.data}>
                    <ReadsServicesProvider
                      value={{
                        db,
                        technicianId: DANA,
                        capturedBy: DANA,
                        readerName: 'D. Ortiz',
                        clock: wave.clock,
                        newId,
                        prefs: new MemoryKeyValueStore(),
                        scanner: new FakeScanner(),
                        camera: new FakeCamera(),
                        location: new FakeLocation(),
                        dictation: unavailableDictation,
                        crash: nullCrash,
                        sendNow: () => Promise.resolve(),
                        downloadRoutes: null,
                      }}
                    >
                      <NavigationContainer ref={ref}>
                        <AppNavigator />
                      </NavigationContainer>
                    </ReadsServicesProvider>
                  </SiteDataProvider>
                </JobPortProvider>
              </DayDataProvider>
            </MeServicesProvider>
          </ShellStatusProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>,
  );
  await screen.findByTestId('screen-FF-63');
  await act(async () => undefined);

  /** Open a screen by its address, with the record it is about. */
  const open = async (id: ScreenId, params?: Record<string, unknown>) => {
    const target = routeTo(id);
    const walk = (p: Record<string, unknown> | undefined): Record<string, unknown> | undefined => {
      if (!p) return params;
      if (p.params && typeof p.params === 'object') return { ...p, params: walk(p.params as Record<string, unknown>) };
      return { ...p, params };
    };
    await act(async () => {
      ref.dispatch(CommonActions.navigate(target.name, params ? walk(target.params as Record<string, unknown>) : target.params));
    });
    // Port reads (the alerts) are promises; let them land.
    await act(async () => {
      await Promise.resolve();
    });
  };
  return { ref, db, wave, alerts, open, current: () => ref.getCurrentRoute()?.name };
}

type Instance = typeof screen.UNSAFE_root;

/** The host view of the frame holding `id` (`nativeID="frame-of-<id>"`). */
export function frameOf(id: ScreenId): Instance {
  const found = screen.UNSAFE_root.findAll((n: Instance) => n.props.nativeID === `frame-of-${id}` && typeof n.type === 'string');
  const f = found.at(-1);
  if (!f) throw new Error(`no frame holds ${id}`);
  return f;
}

/** A pane's laid-out width: the `width` its host view is given (the flexible pane's is its flex share). */
export function paneWidth(pane: Instance): number | 'flex' {
  const style = ([] as Array<Record<string, unknown>>).concat(pane.props.style ?? []).reduce((a, b) => ({ ...a, ...(b ?? {}) }), {});
  return typeof style.width === 'number' ? style.width : 'flex';
}
