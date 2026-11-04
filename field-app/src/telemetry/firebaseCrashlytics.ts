/**
 * The Crashlytics SDK, wired: `@react-native-firebase/crashlytics` 22.4 (the
 * line built for React Native 0.79 / Expo SDK 53) behind `CrashlyticsLike`,
 * so every report still goes through the scrubber (`crashlyticsReporter.ts`).
 *
 * ⚠ **THE SDK'S OWN JAVASCRIPT PATHS ARE THE ROUTE AROUND THE SCRUBBER, AND
 * THERE ARE TWO OF THEM — VERIFIED AGAINST 22.4's `lib/handlers.js`.**
 *
 *  1. **The global error handler.** Constructing the module replaces React
 *     Native's handler with one that, when `isErrorGenerationOnJSCrashEnabled`,
 *     sends the error's MESSAGE to Crashlytics. `firebase.json` turns that off:
 *     `crashlytics_is_error_generation_on_js_crash_enabled: false`.
 *     ⚠ And `crashlytics_javascript_exception_handler_chaining_enabled` must be
 *     **TRUE**, not false as first written down: in this version, chaining OFF
 *     means the SDK's handler swallows the error — React Native's own handler
 *     is never called, so a fatal error neither shows in development nor ends
 *     the process in release. With generation off and chaining on, the SDK's
 *     handler sends nothing and passes the error on. Ours
 *     (`installGlobalCrashHandler`) is installed AFTER it and so runs first.
 *  2. **Unhandled promise rejections.** The SDK enables
 *     `promise/setimmediate/rejection-tracking` and, in release, records every
 *     unhandled rejection WITH ITS MESSAGE — no `firebase.json` key turns that
 *     off. So `reclaimRejectionTracking` re-enables the same tracker with our
 *     handler, which replaces the SDK's: the rejection goes to our crash file,
 *     scrubbed, as a non-fatal.
 *
 * Native crashes still go to Crashlytics directly; they carry native stacks,
 * not screen text.
 */
import { nativeConfig } from '../release/nativeConfig';
import type { CrashCapture } from './crashReporter';
import type { CrashlyticsLike } from './crashlyticsReporter';

interface RejectionTracking {
  enable(options: { allRejections?: boolean; onUnhandled?: (id: number, error: unknown) => void; onHandled?: (id: number) => void }): void;
}

/**
 * The SDK module, adapted. NULL — and the SDK is never constructed — where the
 * build has no Firebase (`configured` false: `app.config.ts` left the files and
 * plugins out, `release/nativeConfig.ts`), where no default Firebase app was
 * created natively, or where the module is not linked at all. Null means crash
 * reports stay in the handset's crash file; nothing is lost and nothing throws.
 */
export function nativeCrashlytics(configured: boolean = nativeConfig().firebase): CrashlyticsLike | null {
  if (!configured) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const app = require('@react-native-firebase/app') as { getApps?: () => unknown[] };
    if (typeof app.getApps === 'function' && app.getApps().length === 0) return null;
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const sdk = require('@react-native-firebase/crashlytics') as typeof import('@react-native-firebase/crashlytics');
    const instance = sdk.getCrashlytics();
    return {
      log: (message) => sdk.log(instance, message),
      setAttributes: (attributes) => sdk.setAttributes(instance, attributes),
      setUserId: (userId) => sdk.setUserId(instance, userId),
      recordError: (error, jsErrorName) => sdk.recordError(instance, error, jsErrorName),
    };
  } catch {
    return null;
  }
}

/**
 * Take unhandled promise rejections back from the SDK (path 2 above). Call it
 * AFTER `nativeCrashlytics()` has constructed the module.
 */
export function reclaimRejectionTracking(
  capture: Pick<CrashCapture, 'record'>,
  tracking: RejectionTracking | null = loadTracking(),
): boolean {
  if (!tracking) return false;
  tracking.enable({
    allRejections: true,
    onUnhandled: (_id, error) => capture.record({ error, fatal: false }),
  });
  return true;
}

function loadTracking(): RejectionTracking | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('promise/setimmediate/rejection-tracking') as RejectionTracking;
  } catch {
    return null;
  }
}
