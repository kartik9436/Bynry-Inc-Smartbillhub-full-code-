// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-10784 — a refused re-upload of a file already loaded showed
//          "File already loaded as IMP-…" AND "HTTP 409 · BIZ-IDEMPOTENT · ref …"
//          under it, on the upload step and on commit, for every import target.
// Ruling:  PO 2026-10-31 P12 = A — plain words everywhere, never "HTTP 409 ·
//          BIZ-IDEMPOTENT".
// Red first (law 7): `supportLineOf` did not exist; the screen called
//          `diagnosticOf` for every failure, which is case 1's red.
// What would pass wrongly: a helper that never returns a line — cases 3 and 4
//          keep the support line for a failure with no sentence (DEF-964).
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import "@/i18n";
import { ApiError, diagnosticOf } from "@/api/client";
import i18n from "@/i18n";

import { supportLineOf } from "./ImportWorkflowPage";

const exists = (key: string) => i18n.exists(key);

function refused(status: number, code: string | null, key: string) {
  return new ApiError(status, {
    code,
    message_key: key,
    params: { run_no: "IMP-0012" },
    trace_id: "5f2b9c1d000000000000000000000000",
  });
}

describe("DEF-MET-10784 · a named import refusal says its sentence and no HTTP line", () => {
  it("the file already loaded: sentence yes, 'HTTP 409 · BIZ-IDEMPOTENT' no", () => {
    const error = refused(409, "BIZ-IDEMPOTENT", "metering.import.file_already_loaded");
    expect(diagnosticOf(error)).toContain("HTTP 409");
    expect(supportLineOf(error, exists)).toBeNull();
    expect(i18n.t("metering.import.file_already_loaded", { run_no: "IMP-0012" })).toContain("IMP-0012");
  });

  it("any other named 4xx refusal on the import screen is the same", () => {
    expect(supportLineOf(refused(422, "VAL-FORMAT", "metering.import.file_already_loaded"), exists)).toBeNull();
  });

  it("a failure with no sentence still carries the support line (DEF-964)", () => {
    const line = supportLineOf(refused(500, null, "api.error.unexpected"), exists);
    expect(line).toContain("HTTP 500");
    expect(supportLineOf(refused(409, "BIZ-IDEMPOTENT", "no.such.key.anywhere"), exists)).toContain("HTTP 409");
  });

  it("nothing answered at all still says so; no failure says nothing", () => {
    expect(supportLineOf(new TypeError("Failed to fetch"), exists)).toBe("TypeError: Failed to fetch");
    expect(supportLineOf(null, exists)).toBeNull();
  });
});
