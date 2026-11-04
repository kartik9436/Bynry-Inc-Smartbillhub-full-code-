/**
 * The app root: builds the services once, then mounts the providers and the
 * navigation tree (T-12, T-13, T-14).
 *
 *   ThemeProvider (with the saved theme mode and *Bigger text*, FF-51;
 *   screens/me/prefs.ts) → GestureHandlerRootView → SafeAreaProvider →
 *   I18nProvider → SessionProvider → GettingInProvider → FieldRuntime (THE
 *   one data provider: the tenant store opened at sign-in and closed at
 *   sign-out, the sync engine on its schedule, and every wave's provider
 *   fed from them — the "me" services and MeShellStatus, THE one shell
 *   status, among them) → UpdateRequiredGate (*Update the app* in place of
 *   the navigator once the server refuses this build, DEF-FLD-10355; inside
 *   the runtime so captured work keeps draining) → NavigationContainer →
 *   AppNavigator
 *
 * Telemetry's global crash handler is installed once the services exist, so
 * an uncaught error is recorded (scrubbed) before the platform's own handler.
 *
 * The theme is outermost so the boot screen is themed too (T-08; the kit's
 * `useTheme()` refuses to run without it).
 *
 * Until the services are built (the keystore read and the language pick take a
 * moment on a cold start) it shows the product name and nothing else. If they
 * cannot be built it says so in plain words rather than showing a blank page;
 * nothing captured is touched either way, because nothing here can touch it.
 */
import { NavigationContainer } from '@react-navigation/native';
import { type ComponentType, useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AppText } from './components/AppText';
import { I18nProvider } from './i18n/I18nProvider';
import { AppNavigator } from './navigation/AppNavigator';
import { UpdateRequiredGate } from './release/UpdateRequiredGate';
import { PREF, savedBiggerText, savedThemeMode, writeFlag } from './screens/me/prefs';
import { GettingInProvider } from './screens/gettingIn/gettingInServices';
import { handsetUtilityIn } from './security/handsetUtility';
import { type AppStateLike, FieldRuntime, type FieldRuntimeDeps } from './session/FieldRuntime';
import { type ErrorUtilsLike, installGlobalCrashHandler } from './telemetry';
import { type AppServiceOverrides, type AppServices, createAppServices } from './session/services';
import { SessionProvider } from './session/SessionProvider';
import { ThemeProvider, useTheme } from './theme';

/** The product's name — a brand, so not translated, and shown before any catalogue loads. */
export const PRODUCT_NAME = 'SMART360 Next Field';

/** React Native's global error hook, where the platform has one. */
function platformErrorUtils(): ErrorUtilsLike | null {
  const g = globalThis as { ErrorUtils?: ErrorUtilsLike };
  return g.ErrorUtils && typeof g.ErrorUtils.setGlobalHandler === 'function' ? g.ErrorUtils : null;
}

function platformAppState(): AppStateLike | undefined {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return (require('react-native') as { AppState: AppStateLike }).AppState;
  } catch {
    return undefined;
  }
}

export interface AppProps {
  overrides?: AppServiceOverrides;
  /** The global error hook (tests pass a fake; the app uses React Native's). */
  errorUtils?: ErrorUtilsLike | null;
  appState?: AppStateLike;
  /**
   * The native layer (`NativeApp.tsx`): the device host's viewfinders, *Keep
   * screen on* and the push registration — drawn inside the theme, the words
   * and the session, beside the navigation. Absent in tests and previews.
   */
  NativeLayer?: ComponentType<{ services: AppServices }>;
}

export default function App({ overrides, errorUtils, appState, NativeLayer }: AppProps) {
  const [services, setServices] = useState<AppServices | null>(null);
  const [failed, setFailed] = useState(false);

  // Built once per services, so the runtime's store, transport and engine are
  // not rebuilt on every render.
  const runtime = useMemo<FieldRuntimeDeps | null>(
    () =>
      services
        ? {
            holder: services.holder,
            session: services.session,
            prefs: services.prefs,
            device: services.handset,
            network: services.network,
            transportFor: services.transportFor,
            files: services.files,
            telemetry: services.telemetry,
            newId: services.newId,
            appState: appState ?? platformAppState(),
            MapView: services.MapView,
            crashReporter: services.crashReporter,
            pinning: services.pinning,
          }
        : null,
    [services, appState],
  );

  // Which utility this handset signs in to — remembered from the office's
  // code (FF-56/57), never from the build (DEF-FLD-10580).
  const handsetUtility = useMemo(() => (services ? handsetUtilityIn(services.prefs) : null), [services]);

  useEffect(() => {
    if (!services) return;
    const hook = errorUtils === undefined ? platformErrorUtils() : errorUtils;
    return hook ? installGlobalCrashHandler(services.telemetry.crashes, hook) : undefined;
  }, [services, errorUtils]);

  useEffect(() => {
    let live = true;
    createAppServices(overrides)
      .then((s) => {
        if (live) setServices(s);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [overrides]);

  if (!services) {
    return (
      <ThemeProvider>
        <Boot failed={failed} />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider
      initialMode={savedThemeMode(services.prefs)}
      onModeChange={(m) => services.prefs.set(PREF.THEME_MODE, m)}
      initialBiggerText={savedBiggerText(services.prefs)}
      onBiggerTextChange={(on) => writeFlag(services.prefs, PREF.BIGGER_TEXT, on)}
    >
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SafeAreaProvider>
          <I18nProvider fieldI18n={services.fieldI18n} prefs={services.prefs}>
            <SessionProvider manager={services.session}>
              <GettingInProvider
                value={{
                  api: services.api,
                  ...(handsetUtility ? { utility: handsetUtility } : {}),
                  serverSet: services.serverSet,
                  deviceId: () => services.device.deviceId(),
                  deviceName: () => services.device.deviceName(),
                  ...(services.permissions ? { permissions: services.permissions } : {}),
                }}
              >
                <FieldRuntime deps={runtime as FieldRuntimeDeps}>
                  <UpdateRequiredGate>
                    <NavigationContainer>
                      <AppNavigator />
                    </NavigationContainer>
                  </UpdateRequiredGate>
                </FieldRuntime>
                {NativeLayer ? <NativeLayer services={services} /> : null}
              </GettingInProvider>
            </SessionProvider>
          </I18nProvider>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ThemeProvider>
  );
}

/** Before any catalogue loads: the product name, and a plain sentence if it cannot start. */
function Boot({ failed }: { failed: boolean }) {
  const theme = useTheme();
  return (
    <View
      style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.colors.page, gap: theme.space[2] }}
      testID={failed ? 'app-boot-failed' : 'app-booting'}
    >
      <AppText variant="title">{PRODUCT_NAME}</AppText>
      {failed ? (
        <AppText variant="body" tone="muted">
          Could not start. Restart the app.
        </AppText>
      ) : null}
    </View>
  );
}
