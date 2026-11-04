// ── Trace ──────────────────────────────────────────────
// Change:  CR-200-BRC10 lane B F5 — the staff Approve window's *From the
//          customer* block names the apartment the applicant picked, and the
//          unit NUMBER it was linked to (B14 rule 31: never the id).
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { apartmentOf } from "./RequestCategoryToSet";
import type { ServiceRequestDetail } from "./serviceRequestEndpoints";

function detail(place: Record<string, unknown>): ServiceRequestDetail {
  return { location_and_services: place } as unknown as ServiceRequestDetail;
}

describe("F5 · the apartment on the Approve window", () => {
  it("the picked label and the linked unit's number", () => {
    expect(
      apartmentOf(
        detail({ address_unit_as_given: "B", resolved_unit_id: "0192-uuid", resolved_unit_no: "U-00004" }),
      ),
    ).toBe("B · U-00004");
  });

  it("Mine isn't listed: the label as typed, no number", () => {
    expect(apartmentOf(detail({ address_unit_as_given: "9Z", resolved_unit_id: null, resolved_unit_no: null }))).toBe(
      "9Z",
    );
  });

  it("never the id, and a dash when nothing was said", () => {
    const shown = apartmentOf(detail({ address_unit_as_given: null, resolved_unit_id: "0192-uuid", resolved_unit_no: null }));
    expect(shown).toBe("—");
    expect(shown).not.toContain("0192");
  });
});
