/**
 * The PostHog CLIENT, built for the shipped app (`posthog.ts` holds the
 * options and the transport; this file is the one that constructs the SDK).
 *
 * Built with `posthogOptions()` — replay, lifecycle, autocapture and the SDK's
 * own error tracking all OFF, persistence in memory — so the only way an event
 * reaches PostHog is our scrubbed, gated queue (`analyticsQueue.ts`).
 *
 * The project key and the host are the PO's to supply (`EXPO_PUBLIC_POSTHOG_KEY`,
 * `EXPO_PUBLIC_POSTHOG_HOST` — the host picks the data region, US or EU, which
 * is not ours to choose). Without BOTH, there is no client: events wait in
 * their queue, never lost, never sent.
 */
import { PostHog } from 'posthog-react-native';

import type { AnalyticsTransport } from './analyticsQueue';
import { createPostHogTransport, posthogOptions } from './posthog';

export interface PostHogConfig {
  apiKey?: string | null;
  host?: string | null;
}

export function posthogConfigFromEnv(): PostHogConfig {
  return { apiKey: process.env.EXPO_PUBLIC_POSTHOG_KEY ?? null, host: process.env.EXPO_PUBLIC_POSTHOG_HOST ?? null };
}

/** The transport over a real client, or null when the key or host is missing. */
export function posthogTransport(config: PostHogConfig, deviceId: string): AnalyticsTransport | null {
  const apiKey = config.apiKey?.trim();
  const host = config.host?.trim();
  if (!apiKey || !host) return null;
  return createPostHogTransport(new PostHog(apiKey, posthogOptions(host, deviceId)));
}
