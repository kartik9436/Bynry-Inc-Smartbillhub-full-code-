// CR-169-BRC10 §2 row 8 — every event has an allow-list, and anything else is
// dropped before it can reach PostHog. Written before `events.ts` (red first).
import { describe, expect, it } from "vitest";

import { EVENT_CATALOGUE, cleanEventProperties } from "./events";

describe("the event catalogue (CR-169-BRC10 §2)", () => {
  it("names every event object_action, snake case", () => {
    for (const name of Object.keys(EVENT_CATALOGUE)) {
      expect(name).toMatch(/^[a-z]+(?:_[a-z]+)+$/);
    }
  });

  it("carries the first wired set", () => {
    expect(Object.keys(EVENT_CATALOGUE).sort()).toEqual(
      [
        "action_refused",
        "list_filtered",
        "list_searched",
        "report_downloaded",
        "screen_viewed",
        "user_sign_in_failed",
        "user_signed_in",
        "user_signed_out",
        "work_order_status_changed",
      ].sort(),
    );
  });

  it("drops a key that is not on the event's allow-list", () => {
    const cleaned = cleanEventProperties("list_searched", {
      list: "accounts",
      has_search: true,
      result_count: 3,
      // what a careless call site might add — the search text itself
      search: "Maria Lopez",
    } as never);
    expect(cleaned).toEqual({ list: "accounts", has_search: true, result_count: 3 });
    expect(JSON.stringify(cleaned)).not.toContain("Maria");
  });

  it("drops a string value that is not a code (a name, an amount, an email)", () => {
    expect(cleanEventProperties("list_filtered", { list: "accounts", filter: "Maria Lopez" })).toEqual({
      list: "accounts",
    });
    expect(cleanEventProperties("action_refused", { screen: "S22", code: "$186.40" })).toEqual({ screen: "S22" });
    expect(cleanEventProperties("action_refused", { screen: "S22", code: "maria@example.com" })).toEqual({
      screen: "S22",
    });
  });

  it("keeps counts and yes/no only as numbers and booleans", () => {
    expect(
      cleanEventProperties("list_searched", { list: "payments", has_search: "yes", result_count: "12" } as never),
    ).toEqual({ list: "payments" });
  });

  it("refuses an event name that is not in the catalogue", () => {
    expect(() => cleanEventProperties("bill_amount_viewed" as never, {})).toThrow(/catalogue/);
  });

  it("keeps a SCREEN id even though it is shaped like a printed reference (DSH-01, ACC-01)", () => {
    expect(cleanEventProperties("screen_viewed", { screen: "ACC-01", screen_a1: "S17" })).toEqual({
      screen: "ACC-01",
      screen_a1: "S17",
    });
    expect(cleanEventProperties("report_downloaded", { report: "PAY-02.send-notice", format: "csv" })).toEqual({
      report: "PAY-02.send-notice",
      format: "csv",
    });
  });
});
