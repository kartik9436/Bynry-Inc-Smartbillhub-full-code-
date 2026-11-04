// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-TEN-9704 — the logo was a BROKEN IMAGE on every deployment where
//          the app and the API are two hosts: the <img> address had no API
//          origin, so the browser asked the app's static host and got
//          index.html. Reproduced 2026-10-05 (08-qa/logo-2026-10-05/before-*).
// Change:  CR-172-BRC10 — the address also carries the logo's reference, so a
//          replaced logo is a new address.
// ───────────────────────────────────────────────────────
//
// Under vitest no deployed env file is loaded, so the real DEFAULT_BASE_URL is
// "" and a same-origin path would pass any check written against it — which is
// exactly how this defect stayed invisible. So this file builds the client
// module WITH an API origin, the way a dev/sandbox/production bundle has one.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./client")>();
  return { ...actual, DEFAULT_BASE_URL: "https://api-smart360-dev.bynry.com" };
});

const { companyLogoFileUrl } = await import("./endpoints");

describe("companyLogoFileUrl — the one address every drawing of the logo uses", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/brazosbend/settings/company/profile");
  });
  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("carries the API's origin, so a two-host deployment asks the API and not the app (DEF-TEN-9704)", () => {
    expect(companyLogoFileUrl()).toBe(
      "https://api-smart360-dev.bynry.com/api/brazosbend/settings/company/logo/file",
    );
  });

  it("carries the logo's reference, so a replaced logo is a new address (CR-172-BRC10)", () => {
    const first = companyLogoFileUrl("0199b1c2-0000-7000-8000-000000000001");
    const second = companyLogoFileUrl("0199b1c2-0000-7000-8000-000000000002");
    expect(first).toBe(
      "https://api-smart360-dev.bynry.com/api/brazosbend/settings/company/logo/file?v=0199b1c2-0000-7000-8000-000000000001",
    );
    expect(second).not.toBe(first);
  });

  it("names the tenant the screen is on — the portal's path included", () => {
    window.history.pushState({}, "", "/lonestarridge/portal");
    expect(companyLogoFileUrl("r1")).toBe(
      "https://api-smart360-dev.bynry.com/api/lonestarridge/settings/company/logo/file?v=r1",
    );
  });

  it("gives no address at all outside a tenant, never a tenant-less one", () => {
    window.history.pushState({}, "", "/");
    expect(companyLogoFileUrl("r1")).toBeNull();
  });
});
