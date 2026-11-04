// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-WRK-9719 — a work order's photographs were addressed with no
//          API origin, so on a two-host deployment the browser asked the app's
//          static host for them and drew broken images. Same class as
//          DEF-TEN-9704 (the logo) and DEF-CWP-9718 (the portal QR code).
// ───────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, DEFAULT_BASE_URL: "https://api-smart360-dev.bynry.com" };
});

const { photoSrc } = await import("./PhotoViewer");

describe("photoSrc — a photograph is fetched from the API's origin", () => {
  it("carries the API's origin (DEF-WRK-9719)", () => {
    const photo = { key: "p1", title: "Meter", attachmentId: "a1", takenBy: null, takenAt: null, forText: "" };
    expect(photoSrc("brazosbend", "o1", photo)).toBe(
      "https://api-smart360-dev.bynry.com/api/brazosbend/work-orders/o1/attachments/a1/content",
    );
  });

  it("keeps a URL the caller already holds, and gives none without a tenant", () => {
    const held = { key: "s", title: "Sig", attachmentId: null, url: "https://x/y.png", takenBy: null, takenAt: null, forText: "" };
    expect(photoSrc("brazosbend", "o1", held)).toBe("https://x/y.png");
    expect(photoSrc("", "o1", { ...held, url: null, attachmentId: "a1" })).toBeNull();
  });
});
