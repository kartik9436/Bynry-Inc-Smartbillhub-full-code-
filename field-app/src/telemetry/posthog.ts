/**
 * PostHog — analytics and flags (AD-18; agreed by both the Work page and the
 * Decisions page, unlike the crash provider).
 *
 * PostHog is only ever a TRANSPORT here. Events reach it from our own queue
 * (`analyticsQueue.ts`), already scrubbed, and only when the work gate is clear.
 * So every one of PostHog's own capture paths is switched off — each of them
 * would be a route around the scrubber:
 *   - session replay OFF (R68): not configured carefully, off;
 *   - app-lifecycle events, touch autocapture and screen autocapture OFF;
 *   - PostHog's own error tracking OFF — crashes go through `crashReporter.ts`;
 *   - person profiles never created, GeoIP disabled;
 *   - in-memory persistence: our queue is the offline store, PostHog's would be
 *     a second, unscrubbed one.
 *
 * This file imports PostHog's TYPES only, so nothing native loads in tests. The
 * app constructs the client with `POSTHOG_OPTIONS` and passes it here.
 */
import type { PostHog, PostHogOptions } from 'posthog-react-native';
import type { AnalyticsTransport } from './analyticsQueue';
import type { FlagFetcher } from './flags';

/** Read by `<PostHogProvider autocapture={…}>` — touch and screen autocapture off. */
export const POSTHOG_PROVIDER_AUTOCAPTURE = false as const;

export function posthogOptions(host: string, deviceId: string): PostHogOptions {
  return {
    host,
    enableSessionReplay: false,
    captureAppLifecycleEvents: false,
    errorTracking: { autocapture: false },
    persistence: 'memory',
    personProfiles: 'never',
    disableGeoip: true,
    disableSurveys: true,
    sendFeatureFlagEvent: false,
    preloadFeatureFlags: false,
    // The anonymous device id is the distinct id. The technician's id and name
    // ride as super properties (below), so no person profile is created.
    bootstrap: { distinctId: deviceId, isIdentifiedId: false },
  };
}

type PostHogLike = Pick<PostHog, 'capture' | 'flush' | 'register' | 'reloadFeatureFlagsAsync'>;

export function createPostHogTransport(client: PostHogLike): AnalyticsTransport {
  return {
    async send(events, identity) {
      // Super properties: tenant, role and — PO 2026-10-21, "Yes, by name" — the
      // signed-in technician's id and name. The device id is the distinct id.
      // Only what the identity allow list kept arrives here (`scrubIdentity`).
      if (identity) {
        const props: Record<string, string> = { tenant: identity.tenant, role: identity.role };
        if (identity.technicianId) props.technician_id = identity.technicianId;
        if (identity.technicianName) props.technician_name = identity.technicianName;
        await client.register(props);
      }
      for (const e of events) client.capture(e.name, { ...e.fields, $timestamp: new Date(e.at).toISOString() });
      await client.flush();
    },
  };
}

export function posthogFlagFetcher(client: PostHogLike): FlagFetcher {
  return () => client.reloadFeatureFlagsAsync();
}
