/**
 * Telemetry — Phase 1b, T-73..T-76 (CR-187-BRC10). Rules R66–R72, AD-18 (crash half superseded: Crashlytics), AD-19,
 * Security §5.
 *
 * `createTelemetry` wires the pieces; each piece is also exported for tests.
 *
 * NOT WIRED YET, and each is a named hand-off rather than a hidden gap:
 *   - the CRASH PROVIDER is Crashlytics (PO 2026-10-21). `createCrashlyticsReporter`
 *     adapts it; WIRED 2026-10-21 (`firebaseCrashlytics.ts`, `NativeApp.tsx`). Before: not installed (native config,
 *     coordinator's). Until the app passes a reporter to `flush()`, crash files
 *     wait on the handset. Crashlytics' OWN JavaScript error handler must be
 *     turned off when the SDK lands, or JS errors reach it unscrubbed — see
 *     `crashlyticsReporter.ts`.
 *   - the SYNC ENGINE must call `gate.reportWork()` with the outbox and photo
 *     queue depths. Until it does the gate is closed (fail-closed) and nothing is
 *     sent — see `workGate.ts`.
 *   - the APP ROOT must call `installGlobalCrashHandler(capture, ErrorUtils)` and
 *     construct PostHog with `posthogOptions()`; the Settings screen (FF-51) reads
 *     `diagnosticsLine()`.
 */
import { createAnalyticsQueue, type AnalyticsQueue, type AnalyticsTransport } from './analyticsQueue';
import { createCrashCapture, type CrashCapture, type CrashReporter } from './crashReporter';
import { createScrubber, type Scrubber } from './scrubber';
import { createWorkGate, type WorkGate } from './workGate';
import type { Clock, KeyValueStore, RawEvent, TelemetryIdentity } from './types';
import type { SendOutcome } from './offline';

export interface TelemetryOptions {
  store: KeyValueStore;
  analytics: AnalyticsTransport;
  identity: () => TelemetryIdentity | null;
  clock?: Clock;
  gate?: WorkGate;
  scrubber?: Scrubber;
  maxEvents?: number;
  timeoutMs?: number;
}

export interface Telemetry {
  gate: WorkGate;
  scrubber: Scrubber;
  crashes: CrashCapture;
  analytics: AnalyticsQueue;
  /** An analytics event; also kept as a breadcrumb for the next crash. */
  track(raw: RawEvent): void;
  /** Crashes first (they are rarer and worth more), then events. Never throws. */
  flush(crashReporter?: CrashReporter): Promise<{ crashes: SendOutcome; events: SendOutcome }>;
}

export function createTelemetry(opts: TelemetryOptions): Telemetry {
  const scrubber = opts.scrubber ?? createScrubber(opts.clock);
  const gate = opts.gate ?? createWorkGate();
  const crashes = createCrashCapture({
    store: opts.store,
    scrubber,
    identity: opts.identity,
    timeoutMs: opts.timeoutMs,
  });
  const analytics = createAnalyticsQueue({
    store: opts.store,
    scrubber,
    gate,
    transport: opts.analytics,
    identity: opts.identity,
    maxEvents: opts.maxEvents,
    timeoutMs: opts.timeoutMs,
    droppedCrashes: () => crashes.droppedCount(),
    resetDroppedCrashes: () => crashes.resetDropped(),
  });
  return {
    gate,
    scrubber,
    crashes,
    analytics,
    track(raw) {
      analytics.track(raw);
      crashes.breadcrumb(raw);
    },
    async flush(crashReporter) {
      const crashOutcome: SendOutcome = crashReporter
        ? await crashes.sendPending(crashReporter, gate)
        : 'yielded';
      const events = await analytics.flush();
      return { crashes: crashOutcome, events };
    },
  };
}

export { ALLOW_LIST } from './allowList';
export type { AllowListPolicy } from './allowList';
export { createScrubber } from './scrubber';
export type { Scrubber } from './scrubber';
export { createWorkGate } from './workGate';
export type { WorkGate, WorkQueueState } from './workGate';
export { createAnalyticsQueue } from './analyticsQueue';
export type { AnalyticsQueue, AnalyticsTransport } from './analyticsQueue';
export { createCrashCapture, installGlobalCrashHandler } from './crashReporter';
export type { CrashCapture, CrashReporter, ErrorUtilsLike } from './crashReporter';
export { createFakeCrashReporter } from './fakeCrashReporter';
export { createCrashlyticsReporter } from './crashlyticsReporter';
export type { CrashlyticsLike } from './crashlyticsReporter';
export { createFeatureFlags } from './flags';
export type { FeatureFlags, FlagDefaults } from './flags';
export { diagnosticsLine } from './settingsLine';
export { getOrCreateDeviceId, telemetryIdentity } from './identity';
export { createMemoryStore, createMmkvStore } from './store';
export { posthogOptions, createPostHogTransport, posthogFlagFetcher, POSTHOG_PROVIDER_AUTOCAPTURE } from './posthog';
export { TelemetryErrorBoundary } from './TelemetryErrorBoundary';
export type * from './types';
