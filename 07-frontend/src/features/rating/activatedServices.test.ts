// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5691 — the Plans, Rate schedules, Charge codes and Taxes &
//          fees filters offered all ELEVEN platform services on a tenant with
//          two switched on · DEF-RAT-5692 — the plan wizard's step-2 picker
//          offered the nine the tenant has not switched on, each of which the
//          server refuses.
// Rules:   BR-RAT-024 (services ⊆ the tenant-enabled catalogue) · PO ruling
//          2026-09-17, verbatim: "in filter - we should only show activated
//          Utility services and not all that are available; same is the case in
//          plan - only activated utility services shouel ddiplayed"
// ───────────────────────────────────────────────────────
//
// ⚠ **THE POINT OF TESTING THE HELPER AND NOT THE FOUR CALL SITES.** The four
// tabs each built this list themselves, identically, and all four were wrong in
// the same way — which is what a copied three-line `.map()` does. One named
// function is the thing that cannot drift; these cases are its contract.
import { describe, expect, it } from "vitest";

import type { TenantServiceRow } from "@/api/endpoints";

import { activatedServiceOptions, activatedServices } from "./ratingShared";

function row(service: string, name: string, enabled: boolean): TenantServiceRow {
  return {
    service,
    name,
    enabled,
    billing_basis: "metered",
    primary_uom: null,
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  };
}

// The live shape the PO reported from: eleven served, two switched on.
const ELEVEN: TenantServiceRow[] = [
  row("electric", "Electric", true),
  row("water", "Water", true),
  row("gas", "Gas", false),
  row("sewer", "Sewer", false),
  row("trash", "Trash", false),
  row("storm_water", "Storm water", false),
  row("solar", "Solar", false),
  row("broadband", "Broadband", false),
  row("thermal_heat", "Thermal/Heat", false),
  row("battery", "Battery", false),
  row("fire", "Fire", false),
];

describe("activatedServices — BR-RAT-024, PO ruling 2026-09-17", () => {
  it("keeps only the services the tenant has switched on", () => {
    expect(activatedServices(ELEVEN).map((one) => one.service)).toEqual(["electric", "water"]);
  });

  // ⚠ THE CONTROL CASE. A filter that returned everything and a filter that
  // returned the right thing would both pass the case above if the fixture had
  // all eleven enabled — so prove the helper can tell the two apart.
  it("keeps all eleven when the tenant has switched all eleven on", () => {
    const all = ELEVEN.map((one) => ({ ...one, enabled: true }));
    expect(activatedServices(all)).toHaveLength(11);
  });

  it("returns nothing — not everything — when the tenant has switched none on", () => {
    const none = ELEVEN.map((one) => ({ ...one, enabled: false }));
    expect(activatedServices(none)).toEqual([]);
  });

  it("survives an absent payload without offering the catalogue instead", () => {
    expect(activatedServices(undefined)).toEqual([]);
  });

  it("preserves the server's catalogue order rather than re-sorting it", () => {
    const two = [ELEVEN[10], ELEVEN[0]].map((one) => ({ ...one, enabled: true }));
    expect(activatedServices(two).map((one) => one.service)).toEqual(["fire", "electric"]);
  });
});

describe("activatedServiceOptions — the filter vocabulary", () => {
  it("offers the tenant's two, labelled with the server's own names", () => {
    expect(activatedServiceOptions(ELEVEN)).toEqual([
      { value: "electric", label: "Electric" },
      { value: "water", label: "Water" },
    ]);
  });

  // DEF-RAT-5691's own sentence: a filter offering a value that can never match
  // any row is a filter that lies.
  it("offers no switched-off service, so every option can match a row", () => {
    const offered = activatedServiceOptions(ELEVEN).map((one) => one.value);
    const off = ELEVEN.filter((one) => !one.enabled).map((one) => one.service);
    for (const code of off) expect(offered).not.toContain(code);
  });
});
