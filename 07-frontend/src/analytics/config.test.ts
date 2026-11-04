// CR-169-BRC10 §2 rows 3–4 — off without a key, and a bundle sends only on the
// host its build was made for. Written before `config.ts` (red first).
import { describe, expect, it } from "vitest";

import { decideAnalytics } from "./config";

const BUILT = {
  key: "phc_devkey",
  host: "https://us.i.posthog.com",
  expectedHosts: "app-dev.bynry.com",
  environment: "dev",
};

describe("decideAnalytics", () => {
  it("is OFF with no key (law 3)", () => {
    expect(decideAnalytics({ ...BUILT, key: "" }, "app-dev.bynry.com")).toEqual({ on: false, reason: "no-key" });
  });

  it("is ON on the host the build was made for", () => {
    const decision = decideAnalytics(BUILT, "app-dev.bynry.com");
    expect(decision.on).toBe(true);
  });

  it("is OFF on any other host — a dev bundle copied to production sends nothing", () => {
    expect(decideAnalytics(BUILT, "app.bynry.com")).toEqual({ on: false, reason: "wrong-host" });
    expect(decideAnalytics(BUILT, "localhost:5191")).toEqual({ on: false, reason: "wrong-host" });
  });

  it("is OFF with a key and no expected host at all", () => {
    expect(decideAnalytics({ ...BUILT, expectedHosts: "" }, "app-dev.bynry.com")).toEqual({
      on: false,
      reason: "wrong-host",
    });
  });

  it("accepts a comma-separated host list, spaces and case ignored", () => {
    expect(decideAnalytics({ ...BUILT, expectedHosts: "a.example.com, App-Dev.bynry.com" }, "app-dev.bynry.com").on).toBe(
      true,
    );
  });

  it("is OFF when the ingest host is not PostHog's US cloud (PO answer 2)", () => {
    expect(decideAnalytics({ ...BUILT, host: "https://eu.i.posthog.com" }, "app-dev.bynry.com")).toEqual({
      on: false,
      reason: "wrong-ingest-host",
    });
  });
});
