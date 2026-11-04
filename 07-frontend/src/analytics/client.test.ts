// CR-169-BRC10 — the client's behaviour against a fake PostHog: off without a
// key, identity carries no name/email/phone, portal never identifies, sign-out
// and tenant switch reset, and every address leaving is cleaned.
import { afterEach, describe, expect, it } from "vitest";

import {
  identifyStaff,
  initOptions,
  resetAnalytics,
  resetAnalyticsStateForTests,
  setPageContext,
  startAnalytics,
  track,
  type PostHogLike,
} from "./client";

type Call = [string, ...unknown[]];

function fake(): { posthog: PostHogLike; calls: Call[] } {
  const calls: Call[] = [];
  const posthog: PostHogLike = {
    init: (...args) => calls.push(["init", ...args]),
    capture: (...args) => calls.push(["capture", ...args]),
    identify: (...args) => calls.push(["identify", ...args]),
    group: (...args) => calls.push(["group", ...args]),
    register: (...args) => calls.push(["register", ...args]),
    reset: () => calls.push(["reset"]),
  };
  return { posthog, calls };
}

const BUILT = {
  key: "phc_dev",
  host: "https://us.i.posthog.com",
  expectedHosts: "app-dev.bynry.com",
  environment: "dev",
};

async function started() {
  const { posthog, calls } = fake();
  startAnalytics({ load: async () => posthog, pageHost: "app-dev.bynry.com", built: BUILT });
  await new Promise((resolve) => setTimeout(resolve, 0));
  return calls;
}

afterEach(() => resetAnalyticsStateForTests());

describe("analytics client (CR-169-BRC10)", () => {
  it("loads nothing and sends nothing without a key", async () => {
    let loaded = false;
    const decision = startAnalytics({
      load: async () => {
        loaded = true;
        return fake().posthog;
      },
      pageHost: "app-dev.bynry.com",
      built: { ...BUILT, key: "" },
    });
    track("screen_viewed", { screen: "S22" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(decision).toEqual({ on: false, reason: "no-key" });
    expect(loaded).toBe(false);
  });

  it("loads nothing on a host the build was not made for", async () => {
    let loaded = false;
    startAnalytics({
      load: async () => {
        loaded = true;
        return fake().posthog;
      },
      pageHost: "app.bynry.com",
      built: BUILT,
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(loaded).toBe(false);
  });

  it("replays what was tracked while PostHog was loading, allow-list applied", async () => {
    const { posthog, calls } = fake();
    let release: (value: PostHogLike) => void = () => undefined;
    startAnalytics({
      load: () => new Promise((resolve) => (release = resolve)),
      pageHost: "app-dev.bynry.com",
      built: BUILT,
    });
    track("list_searched", { list: "accounts", has_search: true, result_count: 2, search: "Maria" } as never);
    release(posthog);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(calls.find((call) => call[0] === "capture")).toEqual([
      "capture",
      "list_searched",
      { list: "accounts", has_search: true, result_count: 2 },
    ]);
  });

  it("identifies staff by internal id with role/tenant/app/language only, and groups by tenant", async () => {
    const calls = await started();
    identifyStaff({ userId: "u-1", role: "billing_clerk", tenant: "brazosbend", app: "staff", language: "en-US" });
    const identify = calls.find((call) => call[0] === "identify");
    expect(identify).toEqual([
      "identify",
      "u-1",
      { role: "billing_clerk", tenant: "brazosbend", app: "staff", language: "en-US" },
    ]);
    expect(calls).toContainEqual(["group", "tenant", "brazosbend"]);
    const sent = JSON.stringify(calls);
    expect(sent).not.toMatch(/email|phone|full_name/);
  });

  it("resets on a tenant switch before identifying again", async () => {
    const calls = await started();
    identifyStaff({ userId: "u-1", role: "x", tenant: "brazosbend", app: "staff", language: null });
    identifyStaff({ userId: "u-1", role: "x", tenant: "riverbend", app: "staff", language: null });
    const order = calls.map((call) => call[0]).filter((name) => name === "identify" || name === "reset");
    expect(order).toEqual(["identify", "reset", "identify"]);
  });

  it("resets on sign-out", async () => {
    const calls = await started();
    identifyStaff({ userId: "u-1", role: "x", tenant: "brazosbend", app: "staff", language: null });
    resetAnalytics();
    expect(calls.at(-1)).toEqual(["reset"]);
  });

  it("the portal never identifies, and entering it after staff resets first (PO answer 1)", async () => {
    const calls = await started();
    identifyStaff({ userId: "u-1", role: "x", tenant: "brazosbend", app: "staff", language: null });
    setPageContext("portal", "brazosbend");
    const names = calls.map((call) => call[0]);
    expect(names.lastIndexOf("reset")).toBeGreaterThan(names.lastIndexOf("identify"));
    expect(calls.filter((call) => call[0] === "identify")).toHaveLength(1);
  });

  it("init turns every automatic capture off and loads nothing external", () => {
    const options = initOptions("https://us.i.posthog.com", "dev");
    expect(options).toMatchObject({
      autocapture: false,
      capture_pageview: false,
      capture_pageleave: false,
      disable_external_dependency_loading: true,
      person_profiles: "identified_only",
      session_recording: { maskAllInputs: true, maskTextSelector: "*", recordHeaders: false, recordBody: false },
    });
  });

  it("before_send cleans $current_url, $set_once and the recording's page address", () => {
    const beforeSend = initOptions("https://us.i.posthog.com", "dev").before_send as (
      event: Record<string, unknown>,
    ) => Record<string, unknown>;
    const out = beforeSend({
      event: "$snapshot",
      properties: {
        $current_url: "https://app-dev.bynry.com/brazosbend/accounts/AC-2026-00012?q=Maria",
        $title: "Maria Lopez",
        $snapshot_data: [{ type: 4, data: { href: "https://app-dev.bynry.com/brazosbend/accounts/AC-2026-00012" } }],
      },
      $set_once: { $initial_current_url: "https://app-dev.bynry.com/brazosbend/accounts/AC-2026-00012" },
    });
    const sent = JSON.stringify(out);
    expect(sent).not.toContain("AC-2026-00012");
    expect(sent).not.toContain("Maria");
  });
});
