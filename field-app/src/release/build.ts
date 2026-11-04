/**
 * The version on screen — T-58, R40 (*"The app version is on screen, so a
 * defect report can name a build"*), CR-187-BRC10.
 *
 * TWO NUMBERS, AND THEY COME FROM TWO DIFFERENT PLACES ON PURPOSE:
 *
 *  - the PRODUCT VERSION (`2.590.0`) is `field-app/package.json`, which G35
 *    holds in lockstep with `07-frontend/package.json` and
 *    `06-backend/pyproject.toml` (decision log 2026-10-21, twelve conflicts,
 *    #4: *"one product version; the field app shows it and keeps its own
 *    app-store build number"*). It travels with the JavaScript, so an
 *    over-the-air update that brings new JavaScript brings its new version.
 *
 *  - the BUILD NUMBER (`412`) is the NATIVE BINARY's — `CFBundleVersion` on
 *    iOS, `versionCode` on Android — read from the running binary, NEVER from
 *    `app.json`. `app.json` is bundled with the JavaScript too, so after an
 *    over-the-air update it would name the build the update was MADE from,
 *    not the build the technician is RUNNING — and those are exactly the two
 *    facts a defect report has to tell apart ("JS 2.592.0 on build 7").
 *
 * The board draws it as *2.587.0 · build 412* (FF-01 Splash, FF-09 menu foot);
 * B14 rule 37 makes those figures illustrations, the shape is what is built.
 * Where the binary has no build number (Expo Go, a test, the web) the version
 * is shown alone — a missing number is never made up.
 */
import Constants from 'expo-constants';

import pkg from '../../package.json';

/** The product version this JavaScript was built at. */
export const PRODUCT_VERSION: string = pkg.version;

/** The part of `expo-constants` read here — the native manifest of the binary. */
export interface NativeBuildSource {
  platform?: {
    ios?: { buildNumber?: string | null } | null;
    android?: { versionCode?: number | null } | null;
  } | null;
}

/**
 * The running binary's store build number, or null where there is none.
 *
 * ⚠ `expo-constants` is installed by `expo` itself (it is in `expo`'s own
 * dependencies) but is not yet a DIRECT dependency of this package; the
 * coordinator owns `package.json` and should add it with
 * `npx expo install expo-constants`. `expo-application`'s
 * `nativeBuildVersion` is the newer API for the same fact and is not installed.
 */
export function nativeBuildNumber(source: NativeBuildSource = Constants as unknown as NativeBuildSource): string | null {
  const ios = source.platform?.ios?.buildNumber;
  if (typeof ios === 'string' && /^\d+(\.\d+)*$/.test(ios.trim())) return ios.trim();
  const android = source.platform?.android?.versionCode;
  if (typeof android === 'number' && Number.isInteger(android) && android > 0) return String(android);
  return null;
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** `2.590.0 · build 7`, or `2.590.0` alone when the binary has no build number. */
export function versionLabel(t: Translate, version: string = PRODUCT_VERSION, build: string | null = nativeBuildNumber()): string {
  return build ? t('field.nav.versionBuild', { version, build }) : version;
}
