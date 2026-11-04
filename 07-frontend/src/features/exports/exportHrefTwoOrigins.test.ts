// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-TEN-9189 — on a build whose API lives on its own origin, the
//          export Download saved `file.htm`: the server's `result_link`
//          (`/api/exports/{id}/file`) was handed to the browser with no host,
//          so it resolved against the APP's host and fetched its index page.
// Proof:   this file mocks the build's API origin. Without serverLinkHref in
//          exportDownloadHref / printSetOutcome both cases below go red.
// ───────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/api/client")>();
  return { ...real, DEFAULT_BASE_URL: "https://api-smart360-dev.bynry.com" };
});

import "@/i18n";
import i18n from "@/i18n";
import type { JobRecord } from "@/api/client";
import { printSetOutcome } from "@/features/billing/PrintBillsPage";
import { exportDownloadHref } from "@/features/exports/ListExportButton";

const LINK = "/api/exports/01a0fe2a-a1a3-7e3b-9b4c-dd8fedcf0ca6/file";

function job(kind: string): JobRecord {
  return {
    id: "01a0fe2a-a1a3-7e3b-9b4c-dd8fedcf0ca6",
    kind,
    status: "succeeded",
    progress: { done: 73, total: null },
    result_link: LINK,
    error: null,
  } as unknown as JobRecord;
}

describe("downloads on a two-origin build go to the API host (DEF-TEN-9189)", () => {
  it("a list export's Download points at the API origin, not the app's", () => {
    expect(exportDownloadHref(job("list_export"))).toBe(`https://api-smart360-dev.bynry.com${LINK}`);
  });

  it("a print set's Download points at the API origin, not the app's", () => {
    const t = i18n.t.bind(i18n) as unknown as Parameters<typeof printSetOutcome>[1];
    expect(printSetOutcome(job("bill_print_set"), t).href).toBe(`https://api-smart360-dev.bynry.com${LINK}`);
  });
});
