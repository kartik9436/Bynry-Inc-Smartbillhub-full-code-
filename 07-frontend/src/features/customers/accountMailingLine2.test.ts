// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-6460 — the account page printed a mailing address without
//          its "Apt, suite or unit" line.
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { addressLine } from "./AccountDetailPage";

describe("DEF-CUS-6460 · the account page's mailing address keeps its unit line", () => {
  it("prints line2 after the street, the order an envelope reads", () => {
    expect(
      addressLine({
        id: "a1",
        kind: "mailing",
        line1: "1408 Elm St",
        line2: "Apt 3B",
        city: "Ottumwa",
        state: "IA",
        postal_code: "52501",
      }),
    ).toBe("1408 Elm St, Apt 3B, Ottumwa, IA, 52501");
  });

  it("an address with no unit line reads as before", () => {
    expect(
      addressLine({
        id: "a2",
        kind: "mailing",
        line1: "9 Oak Ave",
        line2: null,
        city: "Ottumwa",
        state: "IA",
        postal_code: "52501",
      }),
    ).toBe("9 Oak Ave, Ottumwa, IA, 52501");
  });
});
