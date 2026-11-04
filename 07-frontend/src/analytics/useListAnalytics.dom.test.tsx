// @vitest-environment jsdom
// CR-169-BRC10 — a list search or filter sends counts and names only.
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { resetAnalyticsStateForTests, startAnalytics, type PostHogLike } from "./client";
import { useListAnalytics } from "./useListAnalytics";

const captured: unknown[][] = [];
const posthog: PostHogLike = {
  init: () => undefined,
  capture: (...args) => captured.push(args),
  identify: () => undefined,
  group: () => undefined,
  register: () => undefined,
  reset: () => undefined,
};

afterEach(() => {
  resetAnalyticsStateForTests();
  captured.length = 0;
});

describe("useListAnalytics", () => {
  it("sends nothing for the list's starting state, then counts only", async () => {
    startAnalytics({
      load: async () => posthog,
      pageHost: "h",
      built: { key: "k", host: "https://us.i.posthog.com", expectedHosts: "h", environment: "dev" },
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    const { rerender } = renderHook((props) => useListAnalytics(props), {
      initialProps: { list: "S17", q: "", filters: {} as Record<string, unknown>, settled: true, total: 40 },
    });
    expect(captured).toEqual([]);
    rerender({ list: "S17", q: "Maria Lopez", filters: {}, settled: false, total: 40 });
    rerender({ list: "S17", q: "Maria Lopez", filters: {}, settled: true, total: 2 });
    rerender({ list: "S17", q: "Maria Lopez", filters: { status: "active" }, settled: true, total: 1 });
    expect(captured).toEqual([
      ["list_searched", { list: "S17", has_search: true, result_count: 2 }],
      ["list_filtered", { list: "S17", filter: "status", result_count: 1 }],
    ]);
    expect(JSON.stringify(captured)).not.toMatch(/Maria|active/);
  });
});
