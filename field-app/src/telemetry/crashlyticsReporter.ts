/**
 * The Crashlytics adapter — T-73. PO ruling 2026-10-21 (decision log, "Field
 * app: crash reporter, technician identity…", answer 1: "B. Crashlytics").
 *
 * It turns a SCRUBBED crash report into Crashlytics calls. It never sees a raw
 * error: the message is already gone and the stack is code coordinates only, so
 * the Error it hands Crashlytics is rebuilt from those and carries no text from
 * the screen.
 *
 * WIRED 2026-10-21: `firebaseCrashlytics.ts` builds the SDK side and `NativeApp.tsx`
 * passes it here (and firebase.json's VERIFIED values are explained there:
 * chaining must be ON in 22.4). Before that: the SDK (`@react-native-firebase/app` + `/crashlytics`) was NOT installed by
 * this lane — it needs native configuration (google-services files, the Expo
 * config plugin) that the coordinator owns. So the module is a PARAMETER typed by
 * the narrow `CrashlyticsLike` below, which the real module satisfies; on the
 * handset: `createCrashlyticsReporter(crashlytics())`.
 *
 * ⚠ WHEN THE SDK LANDS, ITS OWN JAVASCRIPT HANDLER MUST BE OFF. React Native
 * Firebase installs a global JS error handler that reports every uncaught error
 * — message included — straight to Crashlytics, around the scrubber. In
 * `firebase.json` that is `crashlytics_is_error_generation_on_js_crash_enabled:
 * false` and `crashlytics_javascript_exception_handler_chaining_enabled: false`
 * (names to be verified against the version installed). Native crashes still go
 * to Crashlytics directly; they carry native stacks, not screen text.
 */
import type { CrashReporter } from './crashReporter';
import type { ScrubbedCrashReport } from './types';

/** The part of `@react-native-firebase/crashlytics` this adapter uses. */
export interface CrashlyticsLike {
  log(message: string): void;
  setAttributes(attributes: Record<string, string>): Promise<null> | Promise<void> | void;
  setUserId(userId: string): Promise<null> | Promise<void> | void;
  recordError(error: Error, jsErrorName?: string): void;
}

function rebuiltError(report: ScrubbedCrashReport): Error {
  const err = new Error(report.screen ? `${report.errorType} on ${report.screen}` : report.errorType);
  err.name = report.errorType;
  err.stack = [
    `${err.name}: ${err.message}`,
    ...report.frames.map((f) => `    at ${f.fn} (${f.file}:${f.line}:${f.col})`),
  ].join('\n');
  return err;
}

export function createCrashlyticsReporter(crashlytics: CrashlyticsLike): CrashReporter {
  return {
    async send(report) {
      const attrs: Record<string, string> = {
        fatal: String(report.fatal),
        screen: report.screen ?? '',
        components: report.components.join(' > '),
      };
      const id = report.identity;
      if (id) {
        attrs.tenant = id.tenant;
        attrs.role = id.role;
        attrs.device_id = id.deviceId;
        // The technician's own name (PO 2026-10-21, "Yes, by name").
        if (id.technicianName) attrs.technician_name = id.technicianName;
      }
      await crashlytics.setAttributes(attrs);
      await crashlytics.setUserId(id?.technicianId ?? '');
      for (const b of report.breadcrumbs) {
        const fields = Object.entries(b.fields)
          .map(([k, v]) => `${k}=${String(v)}`)
          .join(' ');
        crashlytics.log(fields ? `${b.name} ${fields}` : b.name);
      }
      crashlytics.recordError(rebuiltError(report), report.errorType);
    },
  };
}
