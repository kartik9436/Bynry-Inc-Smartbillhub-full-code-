/**
 * The build's configuration: `app.json`, plus what may not be written into the
 * repo and what depends on whether it is present.
 *
 *  1. **Firebase (Crashlytics, and FCM push on Android) — OPTIONAL.** The two
 *     files live in `secrets/` (ignored by git; the PO supplies them):
 *     `secrets/google-services.json` (Android) and
 *     `secrets/GoogleService-Info.plist` (iOS). Each platform's
 *     `googleServicesFile` is set only when ITS file exists, and the
 *     `@react-native-firebase/app` / `crashlytics` config plugins are added
 *     only when BOTH exist — the app plugin refuses a prebuild for a platform
 *     whose file is missing, so half a pair is treated as none.
 *     `extra.firebaseConfigured` tells the JavaScript which build it is in
 *     (`src/release/nativeConfig.ts`): without Firebase, crash reports are kept
 *     on the handset (never sent, never lost) and Android push is off.
 *
 *  2. **The Android Google Maps SDK key — OPTIONAL.** react-native-maps draws
 *     the stops over Esri's tiles (ADR-011), but on Android the native map view
 *     will not start without a Google Maps SDK key — and mounting it without
 *     one CRASHES THE APP — even though no Google tile is ever drawn. iOS needs
 *     no key. The key is read from the build's environment
 *     (`GOOGLE_MAPS_ANDROID_API_KEY`); `extra.mapsAvailable` says, per
 *     platform, whether the native map may be mounted, and where it may not the
 *     map screens show the placeholder that says *Map not installed*.
 *
 * ⚠ Both decisions change the native layer, so they change the runtime
 * FINGERPRINT (`runtimeVersion.policy: "fingerprint"`): an over-the-air update
 * made from a build WITH a key never reaches a binary built WITHOUT one, and
 * the other way round. That is what makes it safe to read them from `extra`.
 *
 *  3. **Over-the-air updates — OFF until they are set up.** The fingerprint
 *     policy only means something when there is an update server (`updates.url`)
 *     and a signing certificate, and neither exists yet (`15-release-and-
 *     rollback.md` §7). Without them the first EAS build FAILED in
 *     *Configure expo-updates*: the fingerprint computed on the coordinator's
 *     machine differed from the one EAS computed (an `android/` folder and
 *     autolinking paths seen only on the builder) — a check guarding updates
 *     that cannot be sent. So while `updates.url` is absent the build pins
 *     `runtimeVersion` to the product version and sets `updates.enabled:
 *     false`: the APK runs only its built-in code, exactly what it would do
 *     anyway. The day `eas update:configure` adds a url, `app.json`'s
 *     fingerprint policy is back in force with no edit here.
 *
 *  4. **The certificate pins the build STARTS with — config, never code**
 *     (`OQ-FLD-12797`, PO 2026-10-24: *"dont hardcode it use settings"*).
 *     `extra.pins` is `app.json`'s documented default — ISRG Root X1 (Let's
 *     Encrypt, the current issuer) and GTS Root R1 (Google Trust Services,
 *     the backup issuer) — unless the build's environment carries
 *     `FIELD_APP_PINS`, a JSON list of `{spki_sha256, label, not_after}`.
 *     A malformed value FAILS THE BUILD rather than shipping a phone that
 *     pins to nothing. After the first sync the server's list (Settings ›
 *     Security) replaces it — `src/security/pinning.ts`.
 *
 *  5. **Whether the build pins at all — OFF unless `FIELD_APP_PINNING=on`**
 *     (`CR-195-BRC10`; decision log 2026-10-28, PO: *"start A1"*). Pinning
 *     is NOT a go-live requirement: the phone relies on Android's standard
 *     certificate validation (system authorities only), and the pinning code
 *     is kept DORMANT so it can be switched back on as configuration alone —
 *     `FIELD_APP_PINNING=on` plus a correct issuer list (item 4). Both
 *     `eas.json` profiles, `preview` (the beta APK) and `production` (the
 *     store build), say `off` explicitly; unset also means off. ⚠ **Until
 *     2026-10-28 unset meant ON and a production build with `off` was
 *     REFUSED here** (`DEF-FLD-10617`, 2026-10-26). Law 3 is applied, not
 *     broken: the safety floor is the operating system's check, which no
 *     config turns off, and a wrong pin list is what locked the fleet out on
 *     2.603.0 — so the option you type is now `on`. Any word other than
 *     `on`/`off` still fails the build; `extra.pinning` is always written.
 *     The guard is `tests/release/pinningSwitch.test.ts`.
 *
 * `buildConfig` is exported so `tests/release/nativeConfig.test.ts` can run it
 * with and without the files and the key.
 */
import { existsSync } from 'fs';
import { join } from 'path';

import pkg from './package.json';

import type { ConfigContext, ExpoConfig } from 'expo/config';

export const ANDROID_FIREBASE_FILE = './secrets/google-services.json';
export const IOS_FIREBASE_FILE = './secrets/GoogleService-Info.plist';
export const FIREBASE_PLUGINS = ['@react-native-firebase/app', '@react-native-firebase/crashlytics'] as const;

export interface BuildInputs {
  /** Does this project-relative file exist? */
  exists: (relativePath: string) => boolean;
  env: Record<string, string | undefined>;
}

type Plugins = NonNullable<ExpoConfig['plugins']>;

/** Put the Firebase plugins right after `expo-build-properties` (static frameworks), where they were. */
function withFirebasePlugins(plugins: Plugins): Plugins {
  const after = plugins.findIndex((p) => (Array.isArray(p) ? p[0] : p) === 'expo-build-properties');
  const at = after < 0 ? plugins.length : after + 1;
  return [...plugins.slice(0, at), ...FIREBASE_PLUGINS, ...plugins.slice(at)];
}

/** `FIELD_APP_PINS` from the build's environment, or undefined when unset. Throws when malformed. */
export function pinsFromEnv(env: Record<string, string | undefined>): unknown[] | undefined {
  const raw = (env.FIELD_APP_PINS ?? '').trim();
  if (raw === '') return undefined;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('FIELD_APP_PINS is not JSON');
  }
  const ok = (p: unknown) => {
    const v = p as { spki_sha256?: unknown; label?: unknown; not_after?: unknown } | null;
    return (
      !!v &&
      typeof v.spki_sha256 === 'string' &&
      /^[A-Za-z0-9+/]{43}=$/.test(v.spki_sha256) &&
      typeof v.label === 'string' &&
      typeof v.not_after === 'string' &&
      /^\d{4}-\d{2}-\d{2}$/.test(v.not_after)
    );
  };
  if (!Array.isArray(parsed) || parsed.length < 2 || !parsed.every(ok)) {
    throw new Error('FIELD_APP_PINS must list at least two {spki_sha256, label, not_after}');
  }
  return parsed;
}

/** `FIELD_APP_PINNING` from the build's environment: `off` when unset or empty (CR-195-BRC10). Throws on any other word. */
export function pinningFromEnv(env: Record<string, string | undefined>): 'on' | 'off' {
  const raw = (env.FIELD_APP_PINNING ?? '').trim().toLowerCase();
  if (raw === '' || raw === 'off') return 'off';
  if (raw === 'on') return 'on';
  throw new Error(`FIELD_APP_PINNING must be "on" or "off", not "${raw}"`);
}

export function buildConfig(config: Partial<ExpoConfig>, inputs: BuildInputs): ExpoConfig {
  const androidFirebase = inputs.exists(ANDROID_FIREBASE_FILE);
  const iosFirebase = inputs.exists(IOS_FIREBASE_FILE);
  const firebaseConfigured = androidFirebase && iosFirebase;
  const mapsKey = (inputs.env.GOOGLE_MAPS_ANDROID_API_KEY ?? '').trim();
  const updatesConfigured = Boolean(config.updates?.url);
  const envPins = pinsFromEnv(inputs.env);
  // CR-195-BRC10 (PO 2026-10-28, "start A1"): any profile may build with pinning off.
  const pinning = pinningFromEnv(inputs.env);
  const plugins = (config.plugins ?? []).filter((p) => !(FIREBASE_PLUGINS as readonly unknown[]).includes(Array.isArray(p) ? p[0] : p));

  return {
    ...config,
    ios: {
      ...config.ios,
      ...(firebaseConfigured ? { googleServicesFile: IOS_FIREBASE_FILE } : {}),
    },
    android: {
      ...config.android,
      ...(firebaseConfigured ? { googleServicesFile: ANDROID_FIREBASE_FILE } : {}),
      config: {
        ...config.android?.config,
        ...(mapsKey ? { googleMaps: { apiKey: mapsKey } } : {}),
      },
    },
    plugins: firebaseConfigured ? withFirebasePlugins(plugins) : plugins,
    ...(updatesConfigured
      ? {}
      : { runtimeVersion: config.version ?? pkg.version, updates: { ...config.updates, enabled: false } }),
    extra: {
      ...config.extra,
      firebaseConfigured,
      mapsAvailable: { ios: true, android: mapsKey !== '' },
      ...(envPins ? { pins: envPins } : {}),
      pinning,
    },
  } as ExpoConfig;
}

export default ({ config }: ConfigContext): ExpoConfig =>
  buildConfig(config, {
    exists: (relativePath) => existsSync(join(__dirname, relativePath)),
    env: process.env,
  });
