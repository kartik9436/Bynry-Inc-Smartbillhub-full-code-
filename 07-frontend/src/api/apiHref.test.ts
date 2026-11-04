// ── Trace ──────────────────────────────────────────────
// Change:  CR-144-BRC07 (FB11) — the client and the link helper both use the
//          build's API base URL, and the build refuses to run without one.
// Rules:   PO 2026-09-28 (two hosts) · hard-won law 3 (defaults fail closed) ·
//          law 7 (a check whose false pass you cannot describe is a check you
//          do not understand).
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { apiHref, serverLinkHref } from "./apiHref";
import { API_PREFIX, DEFAULT_BASE_URL, apiPath, createApiClient } from "./client";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error — a plain .mjs build-config module with no .d.ts by design.
import { DEPLOYED_MODES, EXPECTED_API_ORIGIN, policyWithApiOrigin, resolveApiBaseUrl } from "../../scripts/deployConfig.mjs";

describe("the API base URL is a fact of the build", () => {
  it("the client's default base URL is whatever VITE_API_BASE_URL held", () => {
    // Under vitest no deployed env file is loaded, so this is the same-origin
    // answer — and that IS the contract for the dev server and the local stack.
    expect(DEFAULT_BASE_URL).toBe(import.meta.env.VITE_API_BASE_URL ?? "");
  });

  it("a client built with an explicit origin sends there, keeping the /api prefix", async () => {
    const seen: string[] = [];
    const client = createApiClient({
      baseUrl: "https://api-smart360.bynry.com",
      tenant: "brazosbend",
      fetchImpl: (async (url: string) => {
        seen.push(String(url));
        return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
      }) as unknown as typeof fetch,
    });
    await client.get("/accounts");
    expect(seen).toEqual(["https://api-smart360.bynry.com/api/brazosbend/accounts"]);
  });

  it("API_PREFIX is unchanged — only the origin moved", () => {
    expect(API_PREFIX).toBe("/api");
    expect(apiPath("brazosbend", "/accounts")).toBe("/api/brazosbend/accounts");
  });
});

describe("apiHref — the one helper the browser-facing links share", () => {
  it("puts the build's base URL in front of the /api prefix", () => {
    expect(apiHref("/brazosbend/routes/17/route-sheet")).toBe(
      `${DEFAULT_BASE_URL}/api/brazosbend/routes/17/route-sheet`,
    );
  });

  it("composes exactly what a fetch of the same endpoint composes", () => {
    // The whole point: a LINK and a FETCH of one endpoint can never disagree
    // about where the API is.
    expect(apiHref("/brazosbend/accounts")).toBe(`${DEFAULT_BASE_URL}${apiPath("brazosbend", "/accounts")}`);
  });

  it("adds the missing leading slash rather than welding two segments together", () => {
    // DEF-CUS-5072's character, one layer out: `apiHref("brazosbend/x")` must
    // not build `/apibrazosbend/x`.
    expect(apiHref("brazosbend/x")).toBe(`${DEFAULT_BASE_URL}/api/brazosbend/x`);
  });

  it("REFUSES a path that already carries the prefix instead of doubling it", () => {
    expect(() => apiHref("/api/brazosbend/x")).toThrow(/already begins/);
  });
});

describe("the build fails closed when the API origin is missing (FB3)", () => {
  it.each(DEPLOYED_MODES as string[])("mode %s refuses an absent variable", (mode) => {
    expect(() => resolveApiBaseUrl(mode, {})).toThrow(/VITE_API_BASE_URL is empty or missing/);
  });

  it.each(DEPLOYED_MODES as string[])("mode %s refuses an empty variable", (mode) => {
    expect(() => resolveApiBaseUrl(mode, { VITE_API_BASE_URL: "   " })).toThrow(
      /VITE_API_BASE_URL is empty or missing/,
    );
  });

  it("refuses a trailing slash, which would build a double one", () => {
    expect(() => resolveApiBaseUrl("production", { VITE_API_BASE_URL: "https://api.x.com/" })).toThrow(
      /must not end with/,
    );
  });

  it("refuses an origin carrying a path", () => {
    expect(() => resolveApiBaseUrl("production", { VITE_API_BASE_URL: "https://api.x.com/v2" })).toThrow(
      /bare ORIGIN/,
    );
  });

  it("accepts each environment's own host, as the PO's table names it", () => {
    for (const mode of DEPLOYED_MODES as string[]) {
      expect(resolveApiBaseUrl(mode, { VITE_API_BASE_URL: EXPECTED_API_ORIGIN[mode] })).toBe(
        EXPECTED_API_ORIGIN[mode],
      );
    }
  });

  it("leaves the dev server and the test run same-origin", () => {
    expect(resolveApiBaseUrl("development", {})).toBe("");
    expect(resolveApiBaseUrl("test", {})).toBe("");
  });
});

describe("the page-security policy carries the API origin (FB7)", () => {
  const BASE = [
    "default-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "frame-src 'self'",
    "object-src 'self'",
    "frame-ancestors 'self'",
  ];

  it("adds it to the four directives that stop being 'self'", () => {
    const policy = policyWithApiOrigin(BASE, "https://api-smart360.bynry.com") as string;
    for (const directive of ["img-src", "connect-src", "frame-src", "object-src"]) {
      expect(policy).toContain(`${directive} `);
      const clause = policy.split("; ").find((one: string) => one.startsWith(`${directive} `));
      expect(clause).toContain("https://api-smart360.bynry.com");
    }
  });

  it("does NOT widen frame-ancestors — that governs who may frame US", () => {
    const policy = policyWithApiOrigin(BASE, "https://api-smart360.bynry.com") as string;
    expect(policy.split("; ").find((one: string) => one.startsWith("frame-ancestors"))).toBe(
      "frame-ancestors 'self'",
    );
  });

  it("keeps 'unsafe-inline' on style-src — the Leaflet map needs it", () => {
    const policy = policyWithApiOrigin(BASE, "https://api-smart360.bynry.com") as string;
    expect(policy).toContain("style-src 'self' 'unsafe-inline' https://fonts.googleapis.com");
  });

  it("adds no wildcard anywhere", () => {
    const policy = policyWithApiOrigin(BASE, "https://api-smart360.bynry.com") as string;
    expect(policy).not.toContain("*");
  });

  it("leaves a same-origin build's policy exactly as it was", () => {
    expect(policyWithApiOrigin(BASE, "")).toBe(BASE.join("; "));
  });
});

describe("serverLinkHref — a link the server wrote, handed to a browser (DEF-TEN-9189)", () => {
  const link = "/api/exports/01a0fe2a-a1a3-7e3b-9b4c-dd8fedcf0ca6/file";

  it.each([
    ["dev", "https://api-smart360-dev.bynry.com"],
    ["sandbox", "https://api-smart360-sandbox.bynry.com"],
    ["production", "https://api-smart360.bynry.com"],
  ])("on a two-origin %s build the API host is in front", (_env, base) => {
    expect(serverLinkHref(link, base)).toBe(`${base}${link}`);
  });

  it("defaults to this build's VITE_API_BASE_URL — the same origin every fetch uses", () => {
    expect(serverLinkHref(link)).toBe(`${DEFAULT_BASE_URL}${link}`);
  });

  it("a same-origin build keeps the server's path exactly", () => {
    expect(serverLinkHref(link, "")).toBe(link);
  });

  it("an absolute link (a signed storage URL) is never rewritten", () => {
    const signed = "https://bucket.s3.amazonaws.com/t/x/export/2026/10/a.csv?X-Amz-Signature=1";
    expect(serverLinkHref(signed, "https://api-smart360.bynry.com")).toBe(signed);
    expect(serverLinkHref("//cdn.example/a.csv", "https://api-smart360.bynry.com")).toBe("//cdn.example/a.csv");
  });
});
