// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10772 — a payments file's in-file duplicate cheque was
//           DROPPED by the importer's default "Drop exact duplicate rows" tick,
//           so it was never held and the receipt read 3 + 1 for 5 rows.
// Rulings:  decision log 2026-10-30 "Lockbox audit: what is fixed …" (LBX-08:
//           in-file duplicate cheque flagged and HELD) · "Lane PAY-E" (L2-08:
//           every row is loaded or rejected).
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { rowHandlingDefaultsFor } from "./kinds";

describe("DEF-PAY-10772 · what the Transform ticks start as", () => {
  it("payments starts with Drop exact duplicate rows OFF, so the cheque rule holds the copy", () => {
    expect(rowHandlingDefaultsFor("payments")).toEqual({
      drop_exact_duplicates: false,
      keep_latest_on_key: false,
      skip_rows_missing_required: false,
    });
  });

  it("every other importer keeps its default unchanged", () => {
    for (const kind of ["premises", "units", "accounts", "assets_meters"] as const) {
      expect(rowHandlingDefaultsFor(kind).drop_exact_duplicates).toBe(true);
    }
  });
});
