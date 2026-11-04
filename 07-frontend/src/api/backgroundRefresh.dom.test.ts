// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-IDN-10024 — a polling page kept its session awake for ever
// Ruling:   PO 2026-10-08, "automatic refreshes stop counting as activity"
// Pairs:    06-backend/tests/test_def_idn_security_settings_true.py (server half)
// ───────────────────────────────────────────────────────
/**
 * The client half of the idle clock: a request sent while nobody has touched
 * the page carries `X-Background-Refresh: 1`; one sent after a click does not.
 * Decided once in `createApiClient`, so every poll — TanStack `refetchInterval`,
 * `pollJob`, a plain `setInterval` — is covered without being tagged.
 */
import { describe, expect, it } from "vitest";

import {
  BACKGROUND_AFTER_MS,
  BACKGROUND_REFRESH_HEADER,
  createApiClient,
  markUserActivity,
} from "./client";

function headersOfOneGet(): Promise<Record<string, string>> {
  let seen: Record<string, string> = {};
  const client = createApiClient({
    baseUrl: "http://api.test",
    tenant: "silvercreek",
    fetchImpl: async (_url, init) => {
      seen = (init?.headers ?? {}) as Record<string, string>;
      return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
  return client.get("/me").then(() => seen);
}

describe("DEF-IDN-10024 — background refreshes do not count as activity", () => {
  it("a request right after a person's input carries no background header", async () => {
    markUserActivity();
    const headers = await headersOfOneGet();
    expect(headers[BACKGROUND_REFRESH_HEADER]).toBeUndefined();
  });

  it("a request after a minute with no input is marked as a background refresh", async () => {
    markUserActivity(Date.now() - BACKGROUND_AFTER_MS - 1);
    const headers = await headersOfOneGet();
    expect(headers[BACKGROUND_REFRESH_HEADER]).toBe("1");
  });

  it("a real click puts the next request back in the person's hands", async () => {
    markUserActivity(Date.now() - BACKGROUND_AFTER_MS - 1);
    window.dispatchEvent(new Event("pointerdown"));
    const headers = await headersOfOneGet();
    expect(headers[BACKGROUND_REFRESH_HEADER]).toBeUndefined();
  });

  it("the header name is the one the server reads", () => {
    expect(BACKGROUND_REFRESH_HEADER).toBe("X-Background-Refresh");
  });
});
