/**
 * THE SHIPPED APP: `App` with the real handset plugged in. `index.ts`
 * registers this; every test mounts `App` itself with its own fakes, so no
 * test depends on a native module being there.
 *
 * What this adds to `App`, each behind the port it was built against:
 *   - the handset (`device/native`): camera and stamp, scanner, position,
 *     dictation, file picker — and the DEVICE HOST that draws the viewfinders;
 *   - biometric unlock (`expo-local-authentication`), returning you to your OWN
 *     session only (the session manager enforces that);
 *   - FF-07's real permissions, with iOS Critical Alerts;
 *   - notifications: the six Android channels, a push shown even while the app
 *     is open, the device push token registered for whoever is signed in, and
 *     a route-change push that downloads the routes (DEF-MET-10606);
 *   - *Keep screen on*, following FF-51 live;
 *   - the Esri map behind FF-13 / FF-14;
 *   - Crashlytics behind the scrubber, and PostHog as the analytics transport
 *     (only when the PO's key and host are in the build).
 *
 * ORDER MATTERS FOR CRASHES: the Crashlytics module is constructed here,
 * before `App` mounts, so its global handler is installed FIRST and ours
 * (`installGlobalCrashHandler`, in `App`) wraps it and runs first; then
 * `reclaimRejectionTracking` takes unhandled promise rejections back from it
 * (`telemetry/firebaseCrashlytics.ts` says why both are needed).
 *
 * Configuration the PO supplies (none of it is in the repo): the Firebase
 * files, the PostHog key and host, the Android Google Maps SDK key, the push
 * credentials — `field-app/README.md`, *Native configuration*. A build may lack
 * the Firebase files and the map key (`app.config.ts`); this file reads which
 * through `release/nativeConfig.ts` and leaves the missing piece out.
 */
import { useEffect } from 'react';
import { Platform } from 'react-native';
import { useTranslation } from 'react-i18next';

import App, { type AppProps } from './App';
import { DeviceHost, DeviceHostController, nativeDevice } from './device/native';
import { expoBiometric } from './device/native/biometric';
import { ESRI_PUBLIC_HOST, esriMapView } from './device/native/EsriMapView';
import { followKeepAwake, watchedStore, type WatchedStore } from './device/native/keepAwake';
import {
  createPushRegistrar,
  ensurePushChannels,
  listenForPushes,
  routeChangeHandler,
  showPushesInForeground,
} from './device/native/notifications';
import { expoPermissions } from './device/native/permissions';
import type { AppServiceOverrides, AppServices } from './session/services';
import { createCrashlyticsReporter } from './telemetry';
import { nativeCrashlytics, reclaimRejectionTracking } from './telemetry/firebaseCrashlytics';
import { posthogConfigFromEnv, posthogTransport } from './telemetry/posthogClient';
import { mapViewFor, nativeConfig, pushAvailable } from './release/nativeConfig';

const host = new DeviceHostController();
/** What this binary was built with (`app.config.ts` → `extra`): Firebase or not, a map key or not. */
const BUILT = nativeConfig();
const OS = Platform.OS === 'ios' ? 'ios' : 'android';
let registrar: { tryNow(): Promise<boolean>; stop(): void } | null = null;

function nativeOverrides(): AppServiceOverrides {
  const crashlytics = nativeCrashlytics(BUILT.firebase);
  const handset = nativeDevice(host);
  return {
    handset,
    biometric: expoBiometric(),
    wrapPrefs: watchedStore,
    analytics: (deviceId) => posthogTransport(posthogConfigFromEnv(), deviceId),
    crashReporter: crashlytics ? createCrashlyticsReporter(crashlytics) : undefined,
    permissions: expoPermissions((kind) => {
      if (kind === 'notifications') void registrar?.tryNow();
      // DEF-FLD-10605: allowed after start-up — start the position watch now, not at the next launch.
      if (kind === 'location') handset.location.startWatch?.();
    }),
    // No Android map key → never mount the native view (it crashes); the placeholder says *Map not installed*.
    MapView: mapViewFor(OS, BUILT, () => esriMapView(process.env.EXPO_PUBLIC_MAP_TILE_HOST ?? ESRI_PUBLIC_HOST)),
    platform: OS,
  };
}

const OVERRIDES = nativeOverrides();

function isWatched(store: unknown): store is WatchedStore {
  return typeof (store as { watch?: unknown }).watch === 'function';
}

export function NativeLayer({ services }: { services: AppServices }) {
  const { t } = useTranslation();

  useEffect(() => {
    reclaimRejectionTracking(services.telemetry.crashes);
  }, [services]);

  useEffect(() => (isWatched(services.prefs) ? followKeepAwake(services.prefs) : undefined), [services]);

  useEffect(() => {
    // DEF-WRK-10352: only the signed-in utility's pushes are acted on.
    showPushesInForeground(services.session);
    // DEF-MET-10606: a route given or taken away downloads the routes and says so.
    const unlisten = listenForPushes(services.session, routeChangeHandler(t));
    void ensurePushChannels(t).catch(() => undefined);
    const r = createPushRegistrar({
      session: services.session,
      api: services.api,
      deviceId: () => services.device.deviceId(),
      deviceName: () => services.device.deviceName(),
      // No Firebase on Android → no FCM: push is off, no token is asked for or registered.
      ...(pushAvailable(OS, BUILT) ? {} : { pushToken: async () => null }),
    });
    registrar = r;
    void r.tryNow();
    return () => {
      unlisten();
      r.stop();
      if (registrar === r) registrar = null;
    };
  }, [services, t]);

  return <DeviceHost host={host} />;
}

export default function NativeApp(props: Omit<AppProps, 'overrides' | 'NativeLayer'>) {
  return <App {...props} overrides={OVERRIDES} NativeLayer={NativeLayer} />;
}
