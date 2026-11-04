/**
 * Crash reporting — T-73, R66, R67.
 *
 * PROVIDER: CRASHLYTICS — PO ruling 2026-10-21 (decision log, "Field app: crash
 * reporter, technician identity…", answer 1, "B. Crashlytics"); AD-18's Sentry is
 * SUPERSEDED for crashes. `CrashReporter` stays provider-neutral and
 * `crashlyticsReporter.ts` is the Crashlytics adapter. Its SDK
 * (@react-native-firebase) is wired by the dependency lane (`firebaseCrashlytics.ts`); this lane did not install it — it needs native
 * configuration the coordinator owns — so the adapter takes the module as a
 * parameter, and tests send to the in-memory fake (`fakeCrashReporter.ts`).
 *
 * The lifecycle the task asks for:
 *   1. AT CRASH TIME — `record()` scrubs the crash and writes it to the crash file
 *      synchronously. No await: a fatal error gives the handler none.
 *   2. ON NEXT START — `sendPending()` hands each report to the provider, only when
 *      the work gate is clear, and removes a report only after it was accepted.
 *
 * Breadcrumbs: the last few scrubbed events, kept in memory and attached to the
 * report. A free-text log line is never a breadcrumb (`allowList.ts`).
 */
import { readJson, writeJson } from './store';
import type { Scrubber } from './scrubber';
import type {
  KeyValueStore,
  RawCrash,
  RawEvent,
  ScrubbedCrashReport,
  ScrubbedEvent,
  TelemetryIdentity,
} from './types';
import type { WorkGate } from './workGate';
import { withTimeout, type SendOutcome } from './offline';

/** The provider seam. `crashlyticsReporter.ts` implements it; the fake does in tests. */
export interface CrashReporter {
  send(report: ScrubbedCrashReport): Promise<void>;
}

export interface CrashCaptureOptions {
  store: KeyValueStore;
  scrubber: Scrubber;
  identity: () => TelemetryIdentity | null;
  maxPending?: number;
  maxBreadcrumbs?: number;
  timeoutMs?: number;
}

export interface CrashCapture {
  /** Synchronous. Writes the scrubbed report to the crash file before it returns. */
  record(raw: RawCrash): void;
  breadcrumb(raw: RawEvent): void;
  sendPending(reporter: CrashReporter, gate: WorkGate): Promise<SendOutcome>;
  pending(): readonly ScrubbedCrashReport[];
  droppedCount(): number;
  resetDropped(): void;
}

const CRASH_KEY = 'telemetry.crashes.v1';
const CRASH_DROPPED_KEY = 'telemetry.crashes.dropped.v1';

export function createCrashCapture(opts: CrashCaptureOptions): CrashCapture {
  const { store, scrubber } = opts;
  const maxPending = opts.maxPending ?? 10;
  const maxBreadcrumbs = opts.maxBreadcrumbs ?? 20;
  const timeoutMs = opts.timeoutMs ?? 15_000;
  const crumbs: ScrubbedEvent[] = [];
  let sending = false;

  const load = (): ScrubbedCrashReport[] => {
    const v = readJson<ScrubbedCrashReport[]>(store, CRASH_KEY, []);
    return Array.isArray(v) ? v : [];
  };
  const loadDropped = (): number => {
    const v = readJson<number>(store, CRASH_DROPPED_KEY, 0);
    return typeof v === 'number' && Number.isFinite(v) ? v : 0;
  };

  return {
    record(raw) {
      try {
        const report = scrubber.scrubCrash(raw, crumbs, opts.identity());
        const list = load();
        list.push(report);
        let dropped = loadDropped();
        if (list.length > maxPending) {
          const over = list.length - maxPending;
          list.splice(0, over);
          dropped += over;
          writeJson(store, CRASH_DROPPED_KEY, dropped);
        }
        writeJson(store, CRASH_KEY, list);
      } catch {
        // A crash in the crash handler must not replace the technician's crash
        // with a second one (R67).
      }
    },

    breadcrumb(raw) {
      try {
        const e = scrubber.scrubEvent(raw);
        if (!e) return;
        crumbs.push(e);
        if (crumbs.length > maxBreadcrumbs) crumbs.splice(0, crumbs.length - maxBreadcrumbs);
      } catch {
        /* invisible */
      }
    },

    async sendPending(reporter, gate) {
      if (sending) return 'busy';
      if (load().length === 0) return 'empty';
      if (!gate.canSend()) return 'yielded';
      sending = true;
      try {
        let report: ScrubbedCrashReport | undefined;
        while ((report = load()[0]) !== undefined) {
          if (!gate.canSend()) return 'yielded';
          // Re-judged on the way out: the crash file may predate this build's
          // allow list, and the network is the boundary that matters. A report
          // that no longer passes is discarded, not sent.
          const safe = scrubber.rescrubCrash(report);
          if (!safe) {
            const rest = load();
            rest.shift();
            writeJson(store, CRASH_KEY, rest);
            continue;
          }
          await withTimeout(() => reporter.send(safe), timeoutMs);
          const rest = load();
          rest.shift();
          writeJson(store, CRASH_KEY, rest);
        }
        return 'sent';
      } catch {
        return 'failed';
      } finally {
        sending = false;
      }
    },

    pending: () => load(),
    droppedCount: () => loadDropped(),
    resetDropped: () => void writeJson(store, CRASH_DROPPED_KEY, 0),
  };
}

/** React Native's global error hook, typed narrowly so tests can pass a fake. */
export interface ErrorUtilsLike {
  getGlobalHandler(): (error: unknown, isFatal?: boolean) => void;
  setGlobalHandler(handler: (error: unknown, isFatal?: boolean) => void): void;
}

/**
 * Records every uncaught JavaScript error to the crash file, then hands it to
 * whatever handler was there before (React Native's red box in development, the
 * process exit in release). Returns an uninstall function.
 */
export function installGlobalCrashHandler(
  capture: CrashCapture,
  errorUtils: ErrorUtilsLike,
  currentScreen: () => string | undefined = () => undefined,
): () => void {
  const previous = errorUtils.getGlobalHandler();
  errorUtils.setGlobalHandler((error, isFatal) => {
    capture.record({ error, fatal: isFatal === true, screen: currentScreen() });
    previous(error, isFatal);
  });
  return () => errorUtils.setGlobalHandler(previous);
}
