// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 (PO 2026-10-04) — user-activity tracking in PostHog,
//          one project per environment. §2 rows 1–8, §3 answers 1–3, §5 (a).
// Tests:   src/analytics/client.test.ts · src/analytics/importGate.test.ts
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ONLY FILE IN THE APP THAT TOUCHES `posthog-js`** (the import gate
// fails any other). Screens call `track()` from `@/analytics`; they never see
// PostHog, so nothing can step around the allow-list in `events.ts`.
//
// WHAT IT DOES, IN THE ORDER IT MATTERS:
//   * **Off unless this build has a key AND the page is on the host the build
//     was made for** (`config.ts`). When off, `posthog-js` is never even
//     downloaded: it is a dynamic import in its own chunk, fetched from this
//     origin (`script-src 'self'` unchanged) and only when analytics is on.
//   * **The `no-external` bundle with the recorder inside it.** PostHog loads
//     nothing from its CDN — not the recorder, not surveys, not toolbars —
//     and `disable_external_dependency_loading` says so twice.
//   * **Nothing automatic.** Autocapture, automatic page views, page-leave,
//     rage/dead clicks, heatmaps, exceptions, web vitals, surveys, product
//     tours, chat and feature flags are all OFF. Every event that leaves is
//     one this product named in `events.ts`, plus PostHog's own `$identify`,
//     `$groupidentify` and the recording (`$snapshot`).
//   * **Every address cleaned on its way out** (`before_send` →
//     `privacy.ts`), the recording's own page address included.
//   * **Recording on for staff and portal** (PO answer 3, widened), masked by
//     default (`privacy.ts`), with network requests never recorded.
//   * **The portal is anonymous** (PO answer 1): no `identify`, no person
//     profile (`person_profiles: "identified_only"`), and entering the portal
//     after a staff session in the same tab RESETS first, so a portal visit is
//     never filed under a member of staff.
//   * **A failure never reaches a screen** (CR §4): every call is wrapped and
//     a failed send is dropped silently.

// `package.json` is the one version source (`components/BuildVersion.tsx` says
// why); read directly so the API client can import this file without React.
import { version as APP_VERSION } from "../../package.json";

import { builtConfig, decideAnalytics, type AnalyticsDecision, type BuiltAnalyticsConfig } from "./config";
import { cleanEventProperties, type EventName, type EventProperties } from "./events";
import { RECORDING_PRIVACY, cleanEventUrls, cleanSnapshotUrls } from "./privacy";

/** Which application a page belongs to — the `app` property (CR §2 row 5). */
export type AnalyticsApp = "staff" | "portal" | "field";

/** The slice of the PostHog instance this file uses. Tests hand in a fake. */
export interface PostHogLike {
  init(key: string, config: Record<string, unknown>): unknown;
  capture(event: string, properties?: Record<string, unknown>): unknown;
  identify(distinctId: string, properties?: Record<string, unknown>): unknown;
  group(type: string, key: string, properties?: Record<string, unknown>): unknown;
  register(properties: Record<string, unknown>): unknown;
  reset(): unknown;
  startSessionRecording?(): unknown;
}

interface Identity {
  userId: string;
  tenant: string;
}

let instance: PostHogLike | null = null;
let started = false;
let decision: AnalyticsDecision | null = null;
let queue: Array<(posthog: PostHogLike) => void> = [];
let identity: Identity | null = null;
let currentContext: string | null = null;

/** `localStorage.ph_debug = "true"` — PostHog's own debug switch — also shows OUR swallowed errors. */
function debugging(): boolean {
  try {
    return typeof localStorage !== "undefined" && localStorage.getItem("ph_debug") === "true";
  } catch {
    return false;
  }
}

function safely(run: () => void): void {
  try {
    run();
  } catch (error) {
    // CR §4 — analytics never breaks or slows a screen. Dropped, silently,
    // unless someone switched PostHog's debug on in this browser.
    if (debugging()) {
      console.warn("[analytics] dropped:", error);
    }
  }
}

/** Run now if PostHog is loaded, queue it if it is loading, drop it if off. */
function withPosthog(run: (posthog: PostHogLike) => void): void {
  if (decision === null || !decision.on) {
    return;
  }
  if (instance !== null) {
    const loaded = instance;
    safely(() => run(loaded));
  } else {
    queue.push(run);
  }
}

/** The PostHog `init` options. Exported for the test that pins them. */
export function initOptions(host: string, environment: string): Record<string, unknown> {
  return {
    api_host: host,
    // Nothing from PostHog's CDN, ever: the recorder is in our bundle.
    disable_external_dependency_loading: true,
    // Nothing automatic — every event is one `events.ts` names.
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    rageclick: false,
    capture_dead_clicks: false,
    capture_heatmaps: false,
    capture_exceptions: false,
    capture_performance: false,
    disable_surveys: true,
    disable_product_tours: true,
    disable_conversations: true,
    disable_web_experiments: true,
    advanced_disable_feature_flags: true,
    // Belt and braces for anything autocapture-shaped that slips through.
    mask_all_text: true,
    mask_all_element_attributes: true,
    mask_personal_data_properties: true,
    // The portal is anonymous: no person profile until `identify`, which only
    // the staff and field apps call.
    person_profiles: "identified_only",
    session_recording: {
      ...RECORDING_PRIVACY,
      recordHeaders: false,
      recordBody: false,
      // A request's address carries record ids and its body is a form.
      maskCapturedNetworkRequestFn: () => null,
    },
    before_send: (event: { event?: string; properties?: Record<string, unknown> } & Record<string, unknown> | null) => {
      if (event === null) {
        return null;
      }
      const cleaned: Record<string, unknown> = { ...event };
      if (event.properties) {
        const properties = cleanEventUrls(event.properties);
        if (event.event === "$snapshot" && "$snapshot_data" in properties) {
          properties.$snapshot_data = cleanSnapshotUrls(properties.$snapshot_data);
        }
        cleaned.properties = properties;
      }
      for (const key of ["$set", "$set_once"]) {
        const value = event[key];
        if (value && typeof value === "object") {
          cleaned[key] = cleanEventUrls(value as Record<string, unknown>);
        }
      }
      return cleaned;
    },
    loaded: (posthog: PostHogLike) => {
      safely(() => posthog.register({ environment, app_version: APP_VERSION }));
      // PO answer 3 — recording is ON. Started here rather than left to the
      // project's remote setting, so the ruling holds in every project.
      safely(() => posthog.startSessionRecording?.());
    },
  };
}

/**
 * Start once, at app load (`main.tsx`). Decides on/off, and only when on
 * fetches PostHog and replays whatever was tracked while it loaded.
 * `options` is for tests; production code passes nothing.
 */
export function startAnalytics(
  options: {
    load?: () => Promise<PostHogLike>;
    pageHost?: string;
    built?: BuiltAnalyticsConfig;
  } = {},
): AnalyticsDecision {
  const load = options.load ?? loadPosthog;
  const pageHost = options.pageHost ?? (typeof window !== "undefined" ? window.location.host : "");
  if (started && decision !== null) {
    return decision;
  }
  started = true;
  decision = decideAnalytics(options.built ?? builtConfig(), pageHost);
  if (debugging()) {
    console.info("[analytics] decision:", decision.on ? "on" : decision.reason);
  }
  if (!decision.on) {
    return decision;
  }
  const { key, host, environment } = decision;
  void load()
    .then((posthog) => {
      safely(() => posthog.init(key, initOptions(host, environment)));
      instance = posthog;
      const pending = queue;
      queue = [];
      for (const run of pending) {
        safely(() => run(posthog));
      }
    })
    .catch((error: unknown) => {
      queue = [];
      if (debugging()) {
        console.warn("[analytics] PostHog did not load:", error);
      }
    });
  return decision;
}

async function loadPosthog(): Promise<PostHogLike> {
  const module = await import("posthog-js/dist/module.full.no-external");
  return module.default as unknown as PostHogLike;
}

/** Send one catalogued event. Unknown keys and non-code strings are dropped. */
export function track<E extends EventName>(event: E, properties: EventProperties<E> = {} as EventProperties<E>): void {
  let cleaned: Record<string, unknown>;
  try {
    cleaned = cleanEventProperties(event, properties);
  } catch {
    return;
  }
  if (debugging()) {
    console.info("[analytics] track:", event, cleaned);
  }
  withPosthog((posthog) => posthog.capture(event, cleaned));
}

/**
 * The staff and field apps' identity (CR §2 rows 5–6). The internal user id
 * and nothing that names the person: never name, email or phone. A tenant
 * switch (a different utility's path in the same browser) resets FIRST, so
 * one person in two utilities is two clean sessions.
 */
export function identifyStaff(person: {
  userId: string;
  role: string | null;
  tenant: string;
  app: Exclude<AnalyticsApp, "portal">;
  language: string | null;
}): void {
  if (!person.userId || !person.tenant) {
    return;
  }
  if (identity !== null && identity.userId === person.userId && identity.tenant === person.tenant) {
    return;
  }
  const previous = identity;
  identity = { userId: person.userId, tenant: person.tenant };
  withPosthog((posthog) => {
    if (previous !== null) {
      posthog.reset();
    }
    posthog.identify(person.userId, {
      role: person.role ?? null,
      tenant: person.tenant,
      app: person.app,
      language: person.language ?? null,
    });
    posthog.group("tenant", person.tenant);
    posthog.register({ tenant: person.tenant, app: person.app, language: person.language ?? null });
  });
}

/** Sign-out, a dead session, or entering the anonymous portal (CR §2 row 7). */
export function resetAnalytics(): void {
  identity = null;
  withPosthog((posthog) => posthog.reset());
}

/**
 * Which app and utility the page now belongs to. Entering the PORTAL with a
 * staff identity in this tab resets first (PO answer 1).
 */
export function setPageContext(app: AnalyticsApp, tenant: string | null): void {
  if (app === "portal" && identity !== null) {
    resetAnalytics();
  }
  const context = `${app}|${tenant ?? ""}`;
  if (context === currentContext) {
    return;
  }
  currentContext = context;
  withPosthog((posthog) => posthog.register({ app, tenant }));
}

/** Tests only — forget every piece of module state. */
export function resetAnalyticsStateForTests(): void {
  instance = null;
  started = false;
  decision = null;
  queue = [];
  identity = null;
  currentContext = null;
}

/** The screen id `<body>` carries right now (`ScreenIdTag` / the portal's tag). */
export function currentScreenId(): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  return document.body?.dataset.screenId ?? document.body?.dataset.screenA1 ?? null;
}
