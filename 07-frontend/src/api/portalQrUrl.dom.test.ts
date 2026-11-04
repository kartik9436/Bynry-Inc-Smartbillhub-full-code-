// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-9718 — the QR code on Settings › Configure › Customer
//          portal › Overview was a BROKEN IMAGE on every deployment where the
//          app and the API are two hosts: its address had no API origin, so
//          the browser asked the app's static host and got index.html.
//          Reproduced 2026-10-05 (08-qa/portal-host-2026-10-05/before-*).
// ───────────────────────────────────────────────────────
//
// Under vitest no deployed env file is loaded, so DEFAULT_BASE_URL is "" and a
// same-origin path would pass any check written against it. This file builds
// the client module WITH an API origin, the way a deployed bundle has one
// (the pattern of companyLogoFileUrl.dom.test.ts, DEF-TEN-9704).
import { describe, expect, it, vi } from "vitest";

vi.mock("./client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./client")>();
  return { ...actual, DEFAULT_BASE_URL: "https://api-smart360-sandbox.bynry.com" };
});

const { portalQrUrl } = await import("./portalSettingsEndpoints");

describe("portalQrUrl — the QR picture and its download ask the API, not the app", () => {
  it("the picture carries the API's origin (DEF-CWP-9718)", () => {
    expect(portalQrUrl("brazosbend")).toBe(
      "https://api-smart360-sandbox.bynry.com/api/brazosbend/settings/portal/qr.svg",
    );
  });

  it("the download carries it too", () => {
    expect(portalQrUrl("brazosbend", true)).toBe(
      "https://api-smart360-sandbox.bynry.com/api/brazosbend/settings/portal/qr.svg?download=1",
    );
  });
});
