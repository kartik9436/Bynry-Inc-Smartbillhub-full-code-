// ── Trace ──────────────────────────────────────────────
// Change:  CR-130-BRC07 — step 1's unit picker reads the unit THIS UTILITY
//          declared it measures this service in, instead of offering every
//          unit no other service has claimed.
// Defect:  DEF-RAT-6152 — step 1 offered eight units on a Sewer schedule, all
//          eight selectable and none preselected, while `tenant_services`
//          already said `kgal`; and for a `share` service the save-time notice
//          never fires either, so nothing warned at entry OR at save.
// Rules:   PO ruling 2026-09-22, verbatim: "youa re correct — however dont hard
//          code anything - use logic to derive it so that it is flexible and
//          handle any scenario. that the objective." · CLAUDE.md hard rule 3
//          (a quantity always carries its unit) · BR-TEN-029 · DEF-184's scope
//          rule (`selectors.uom_scope_filter`)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE POINT OF TESTING THE DERIVATION AND NOT THE CARD.** It is the SHAPE
// hard-won law 2 and `activatedServices.test.ts` are about: a list assembled by
// hand fails silently when the data underneath it changes, and the only thing
// that cannot drift is a named function with its contract written down. So
// these cases assert the RULE, and never a service code — a case naming
// `water` would be the hard-coding the Product Owner ruled against, in the
// test instead of the screen.
import { describe, expect, it } from "vitest";

import type { BillingBasis, LookupEntry, TenantServiceRow } from "@/api/endpoints";

import {
  declaredUnitFor,
  scheduleUomOptions,
} from "./ratingShared";

function service(
  code: string,
  name: string,
  enabled: boolean,
  basis: BillingBasis | undefined,
  units: { primary?: string | null; billed?: string | null } = {},
): TenantServiceRow {
  return {
    service: code,
    name,
    enabled,
    ...(basis === undefined ? {} : { billing_basis: basis }),
    primary_uom: units.primary ?? null,
    alt_uom: null,
    billed_uom: units.billed ?? null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  };
}

function unit(code: string, scope: string | null, active = true): LookupEntry {
  return {
    id: `uom-${code}`,
    code,
    name: `${code} long name`,
    active,
    ...(scope === null ? {} : { service: { code: scope, name: scope } }),
  } as unknown as LookupEntry;
}

// The utility the Product Owner was looking at: water and sewer sold, trash
// sold, everything else switched off. Sewer is a `share` service — it reads no
// register — and trash is `capacity`, which COUNTS carts.
const UTILITY: TenantServiceRow[] = [
  service("water", "Water", true, "metered", { primary: "kgal" }),
  service("sewer", "Sewer", true, "share", { primary: "kgal" }),
  service("trash", "Trash", true, "capacity", { primary: "cart" }),
  service("electric", "Electric", false, "metered", { primary: "kWh" }),
];

// ── `CR-130-BRC07` §3 · **THE Based on CASES ARE GONE, AND THAT IS THE FIX** ──
//
// This file held seven cases over a `basisServiceOptions()` that derived the
// **Based on** list in TSX — enabled · not this service · meters a quantity —
// and every one of them passed. **They were deleted with the function when
// wave A landed `GET /rate-schedules/percent-basis-options`.**
//
// ⚠ **DELETING A PASSING TEST NEEDS A REASON, AND THIS IS IT.** The rule did
// not go away; it moved to the one place it belongs, and wave A's appendix
// (A.2) states why in the words both lanes agreed: *"It exists so the
// derivation is not written a second time in TSX … hard-won law 2 is precisely
// about the front end keeping its own copy of that list."* Keeping these cases
// would have kept the second copy alive to serve them — a test is a reason to
// keep code, which is exactly what makes a redundant one expensive. The rule
// is now asserted by `06-backend/tests/test_cr130_percent_basis.py`, against
// the code that answers the screen, and `cr130_laneb_percent_card_walkthrough.mjs`
// reads the rendered list in a browser on both bases.
//
// What stays here is the half that is genuinely the SCREEN's: step 1's units.

describe("CR-130-BRC07 §8.3 — step 1's units, narrowed to what this utility declared", () => {
  // The seeded catalogue as measured on a running database: 28 units, of which
  // seven carry no service scope and therefore reach every service.
  const CATALOGUE: LookupEntry[] = [
    unit("EDU", "sewer"),
    unit("kgal", null),
    unit("ccf", null),
    unit("kW", null),
    unit("month", null),
    unit("kWh", "electric"),
    unit("gal", "water", false),
  ];

  it("reads billed_uom first, then primary_uom, then nothing", () => {
    expect(declaredUnitFor(UTILITY, "sewer")).toBe("kgal");
    const billed = [service("sewer", "Sewer", true, "share", { primary: "kgal", billed: "ccf" })];
    expect(declaredUnitFor(billed, "sewer")).toBe("ccf");
    expect(declaredUnitFor([service("sewer", "Sewer", true, "share")], "sewer")).toBeNull();
    expect(declaredUnitFor(UTILITY, "nothing-like-this")).toBeNull();
  });

  it("leaves exactly ONE unit selectable, and keeps the rest PRESENT", () => {
    const options = scheduleUomOptions(CATALOGUE, "sewer", "kgal");
    const selectable = options.filter((one) => one.reason === "offered");
    expect(selectable.map((one) => one.value)).toEqual(["kgal"]);
    // ⚠ **PRESENT AND UNSELECTABLE, NEVER ABSENT** — `FieldOption`'s doctrine,
    // which `activeUomOptions` quotes: absent and the user never learns the
    // unit exists; selectable and they only learn on submit. Five of the six
    // ACTIVE units stay on screen carrying their reason.
    expect(options.filter((one) => one.reason === "not_declared").map((one) => one.value)).toEqual([
      "EDU",
      "ccf",
      "kW",
      "month",
    ]);
    // BR-TEN-029 is applied first and is never overridden: a deactivated unit
    // is gone, not greyed.
    expect(options.map((one) => one.value)).not.toContain("gal");
    // And the scope rule still decides who is in the list at all.
    expect(options.map((one) => one.value)).not.toContain("kWh");
  });

  it("keeps TODAY's list when the utility has declared nothing", () => {
    // There is no narrowing to do, and inventing one would be choosing a unit
    // on the utility's behalf.
    const undeclared = scheduleUomOptions(CATALOGUE, "sewer", null);
    expect(undeclared.filter((one) => one.reason !== "offered")).toHaveLength(0);
    expect(undeclared).toHaveLength(scheduleUomOptions(CATALOGUE, "sewer", "kgal").length);
  });

  it("does not re-admit a declared unit the scope rule excluded", () => {
    // `_apply_service_uom` refuses to create this, so it cannot arise through
    // the product — and adding the unit back would be the screen overruling
    // the write path, which `resolve_uom` would refuse on save anyway.
    const options = scheduleUomOptions(CATALOGUE, "sewer", "kWh");
    expect(options.map((one) => one.value)).not.toContain("kWh");
    expect(options.filter((one) => one.reason === "not_declared")).toHaveLength(0);
  });

  it("keeps an already-saved out-of-scope unit visible and refused", () => {
    // §8.3(5) — the existing escape hatch, unchanged. A stored value vanishing
    // from the control that shows it reads as data loss.
    const options = scheduleUomOptions(CATALOGUE, "sewer", "kgal", ["kWh"]);
    const stored = options.find((one) => one.value === "kWh");
    expect(stored).toBeDefined();
    expect(stored?.reason).toBe("out_of_scope");
  });
});
