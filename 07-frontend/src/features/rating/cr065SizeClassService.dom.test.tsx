// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-2385 — a rate schedule for ONE service offers every OTHER
//           service's size classes, so the Fire schedule prices *Electric
//           CT-metered*.   Screens: S9 / r10 RAT-03 · CHG-02
// Change:   CR-065 tasks B1, B2 and D1 — the two wizards ask for the schedule's
//           own service.
// Ruling:   PO 2026-09-02, verbatim, sent with a screenshot of the Fire rate
//           schedule's minimum-bill step: *"This is where we are setting rates
//           for fire  you should show only capacity for fire . in Setting a
//           capacity needs to tags to utility services ."*
// Rules:    BR-TEN-078 (SUPERSEDED for this one list by that ruling) ·
//           BR-TEN-071 (a tenant's own row is never deleted, so an UNTAGGED
//           size must keep listing everywhere)
// Note:     Written BEFORE the fix and shown RED — hard-won law 7.
// ───────────────────────────────────────────────────────
/**
 * **THE ACCEPTANCE CASE IS THE PRODUCT OWNER'S OWN SCREENSHOT**, rendered:
 * open a FIRE rate schedule's size step and the table holds fire's line sizes
 * and no *Electric CT-metered*, no *Gas 250 CFH*.
 *
 * ⚠ **THE THIRD CASE IS THE ONE THAT WOULD OTHERWISE HAVE COST SOMETHING.**
 * Until today every screen offered all sixty sizes, so a schedule out there may
 * already price a size belonging to another service. A filter that simply
 * dropped it would hide a PRICED row while leaving it in the payload — invisible
 * on screen, still saved, impossible to delete. So the offer is the union with
 * whatever this schedule already prices, and this file pins it.
 */
import { describe, expect, it } from "vitest";

import type { LookupEntry } from "@/api/endpoints";

import { sizeClassesForService } from "./ratingShared";

// `DEF-GOV-10106` — the RENDERED case that mounted the old five-step wizard's
// `SizeMatrixStep` left with that component (retired with `DEF-RAT-8755`; the
// three-step wizard replaced it on 2026-10-01, `5804b0fc1`). The filter it
// rendered through is `sizeClassesForService`, which every case below pins.

/**
 * The list as the server now serves it — every platform row names its service.
 *
 * The third fire row was `HYD` "Private hydrant" until 2026-09-03, when the PO
 * said *"remove private hydrants from list"* and a hydrant became an asset
 * rather than a utility-service size. This fixture must only name codes the
 * product actually seeds, or it asserts filtering over a row nobody can have.
 */
const SIZES: LookupEntry[] = [
  { id: "f1", code: "FL-2", name: 'Fire line 2"', active: true, is_system: true, used_by: 0, service: { id: "svc-f", code: "fire" } },
  { id: "f2", code: "FL-6", name: 'Fire line 6"', active: true, is_system: true, used_by: 0, service: { id: "svc-f", code: "fire" } },
  { id: "f3", code: "FL-8", name: 'Fire line 8"', active: true, is_system: true, used_by: 0, service: { id: "svc-f", code: "fire" } },
  { id: "e1", code: "E-CT", name: "Electric CT-metered", active: true, is_system: true, used_by: 0, service: { id: "svc-e", code: "electric" } },
  { id: "e2", code: "E-3P-400", name: "Electric 3φ 400A", active: true, is_system: true, used_by: 0, service: { id: "svc-e", code: "electric" } },
  { id: "g1", code: "G-250", name: "Gas 250 CFH (residential)", active: true, is_system: true, used_by: 0, service: { id: "svc-g", code: "gas" } },
  { id: "g2", code: "G-1000", name: "Gas 1,000+ CFH", active: true, is_system: true, used_by: 0, service: { id: "svc-g", code: "gas" } },
  // A row the tenant added and NOBODY has tagged. BR-TEN-071 forbids deleting
  // it, so `null` means "nobody has said" and it is offered everywhere.
  { id: "t1", code: "FL-14", name: 'Fire line 14"', active: true, is_system: false, used_by: 0, service: null },
  // Retired — leaves every picker, tagged or not (BR-TEN-029).
  { id: "f4", code: "FL-4", name: 'Fire line 4"', active: false, is_system: true, used_by: 0, service: { id: "svc-f", code: "fire" } },
];

const codes = (rows: readonly LookupEntry[]) => rows.map((row) => row.code);

describe("CR-065 — a rate schedule offers its OWN service's sizes", () => {
  it("the PO's screenshot: a FIRE schedule shows fire's sizes and no electric or gas row", () => {
    const offered = codes(sizeClassesForService(SIZES, "fire"));
    expect(offered).toEqual(["FL-2", "FL-6", "FL-8", "FL-14"]);
    expect(offered).not.toContain("E-CT");
    expect(offered).not.toContain("E-3P-400");
    expect(offered).not.toContain("G-250");
    expect(offered).not.toContain("G-1000");
  });

  it("an UNTAGGED size is offered on every service, because nobody has said which it is", () => {
    for (const service of ["fire", "electric", "gas", "water"]) {
      expect(codes(sizeClassesForService(SIZES, service))).toContain("FL-14");
    }
  });

  it("a size this schedule ALREADY PRICES stays on the table even when it is another service's", () => {
    // Dropping it would hide a priced row while leaving it in the payload.
    const offered = codes(sizeClassesForService(SIZES, "fire", ["E-CT"]));
    expect(offered).toContain("E-CT");
    expect(offered).not.toContain("G-250");
  });

  it("a RETIRED size is still never offered — the service filter narrows, it does not replace", () => {
    expect(codes(sizeClassesForService(SIZES, "fire"))).not.toContain("FL-4");
    expect(codes(sizeClassesForService(SIZES, "fire", ["FL-4"]))).not.toContain("FL-4");
  });

  it("no service chosen yet offers every active size, because there is nothing to filter by", () => {
    expect(codes(sizeClassesForService(SIZES, ""))).toHaveLength(8);
  });

});
