// @vitest-environment jsdom
// CR-169-BRC10 — a work order's status change sends the two words, nothing else.
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { resetAnalyticsStateForTests, startAnalytics, type PostHogLike } from "./client";
import { useWorkOrderStatusAnalytics } from "./useStatusChangeAnalytics";

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

describe("useWorkOrderStatusAnalytics", () => {
  it("sends from/to on a change, nothing on first read or on another order", async () => {
    startAnalytics({
      load: async () => posthog,
      pageHost: "h",
      built: { key: "k", host: "https://us.i.posthog.com", expectedHosts: "h", environment: "dev" },
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    const { rerender } = renderHook(({ id, status }) => useWorkOrderStatusAnalytics(id, status), {
      initialProps: { id: "o1", status: "scheduled" },
    });
    rerender({ id: "o1", status: "on_hold" });
    rerender({ id: "o2", status: "completed" });
    expect(captured).toEqual([["work_order_status_changed", { from: "scheduled", to: "on_hold" }]]);
  });
});
