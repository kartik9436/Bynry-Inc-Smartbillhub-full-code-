// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 rows 2–4 (PO 2026-10-04: "Data from one environment
//          must NEVER be sent to another environment's PostHog project").
// Tests:   src/analytics/config.test.ts · scripts/deployConfig.test.mjs (the
//          build half of the same rule)
// ───────────────────────────────────────────────────────
//
// THE RUN-TIME HALF OF THE ENVIRONMENT LOCK. The build half lives in
// `scripts/deployConfig.mjs` (`resolvePosthogConfig`): it refuses a dev or
// sandbox build carrying the production key. This half refuses to SEND from a
// page that is not on the host its build was made for — so a dev bundle copied
// to the production bucket, or opened from `localhost`, sends nothing.
//
// ⚠ `VITE_APP_ENV` IS READ AS A PROPERTY VALUE ONLY. Its own declaration says
// nothing may branch on it, and nothing here does: the decision below depends
// on the KEY and the HOST, never on the environment's name.

export interface BuiltAnalyticsConfig {
  key: string;
  host: string;
  /** Comma-separated `host[:port]` list the bundle may send from. */
  expectedHosts: string;
  environment: string;
}

export type AnalyticsDecision =
  | { on: true; key: string; host: string; environment: string }
  | { on: false; reason: "no-key" | "wrong-host" | "wrong-ingest-host" };

/** PostHog US cloud, the PO's answer 2 — the only ingest host this bundle may name. */
export const US_INGEST_HOST = "https://us.i.posthog.com";

/** What this BUILD carries. Vite inlines each read at build time (law 4). */
export function builtConfig(): BuiltAnalyticsConfig {
  return {
    key: (import.meta.env.VITE_POSTHOG_KEY ?? "").trim(),
    host: (import.meta.env.VITE_POSTHOG_HOST ?? "").trim() || US_INGEST_HOST,
    expectedHosts: (import.meta.env.VITE_POSTHOG_EXPECTED_HOSTS ?? "").trim(),
    environment: (import.meta.env.VITE_APP_ENV ?? "").trim() || "local",
  };
}

/** On or off, and why — a pure function of the build and the page's host. */
export function decideAnalytics(built: BuiltAnalyticsConfig, pageHost: string): AnalyticsDecision {
  if (built.key === "") {
    return { on: false, reason: "no-key" };
  }
  if (built.host !== US_INGEST_HOST) {
    return { on: false, reason: "wrong-ingest-host" };
  }
  const allowed = built.expectedHosts
    .split(",")
    .map((one) => one.trim().toLowerCase())
    .filter((one) => one !== "");
  if (!allowed.includes(pageHost.toLowerCase())) {
    return { on: false, reason: "wrong-host" };
  }
  return { on: true, key: built.key, host: built.host, environment: built.environment };
}
