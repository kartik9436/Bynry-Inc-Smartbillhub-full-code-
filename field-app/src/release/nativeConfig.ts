/**
 * What THIS BINARY was built with, read from the config `app.config.ts` wrote
 * into it (`extra.firebaseConfigured`, `extra.mapsAvailable`) — so the
 * JavaScript never reaches for a native piece the build left out.
 *
 *  - **Firebase.** A preview build may be made without the PO's two Firebase
 *    files. Then there is no Crashlytics and no FCM: crash reports stay in the
 *    handset's crash file (scrubbed, kept, never sent — `telemetry/
 *    crashReporter.ts`), and Android push is simply off (no token is asked
 *    for, so nothing is registered with the server). iOS push uses APNs, which
 *    needs no Firebase file, so it is left as it is.
 *  - **The Android map.** react-native-maps without a Google Maps SDK key
 *    CRASHES the app when the map view mounts. Where the build has no key the
 *    native map is never mounted; FF-13 / FF-14 show the placeholder that says
 *    *Map not installed* (`screens/theDay/mapView.tsx`).
 *
 * BOTH FAIL CLOSED: a binary whose config says nothing (Expo Go, a test, a
 * config from before this file) is treated as having neither.
 */
import Constants from 'expo-constants';

export type NativePlatform = 'ios' | 'android';

export interface NativeConfig {
  firebase: boolean;
  maps: Record<NativePlatform, boolean>;
}

function bool(v: unknown): boolean {
  return v === true;
}

/** The binary's flags. `extra` is `Constants.expoConfig.extra` unless a test passes its own. */
export function nativeConfig(extra: unknown = Constants.expoConfig?.extra): NativeConfig {
  const e = (extra ?? {}) as { firebaseConfigured?: unknown; mapsAvailable?: { ios?: unknown; android?: unknown } | null };
  return {
    firebase: bool(e.firebaseConfigured),
    maps: { ios: bool(e.mapsAvailable?.ios), android: bool(e.mapsAvailable?.android) },
  };
}

/** May the native map view be mounted on this platform? */
export function mapsAvailable(os: NativePlatform, cfg: NativeConfig = nativeConfig()): boolean {
  return cfg.maps[os];
}

/** Is there a push provider on this platform? Android's is FCM, which needs Firebase; iOS's is APNs. */
export function pushAvailable(os: NativePlatform, cfg: NativeConfig = nativeConfig()): boolean {
  return os === 'ios' || cfg.firebase;
}

/**
 * The map component for this build: `make()` (the Esri map) where the native
 * view may be mounted, otherwise `undefined` — which leaves the placeholder in
 * place (`FieldDataProvider`'s default). `make` is only called when allowed.
 */
export function mapViewFor<T>(os: NativePlatform, cfg: NativeConfig, make: () => T): T | undefined {
  return mapsAvailable(os, cfg) ? make() : undefined;
}
