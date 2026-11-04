// ── Trace ──────────────────────────────────────────────
// Rules:   CLAUDE.md hard-won law 5 (one source, never a second copy free to
//          drift) · law 7 (a fixture that cannot tell a working case from a
//          broken one is worse than none)
// Tests:   AssetLifecycle.test.tsx · RaiseWorkOrder.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The asset row and the full detail payload, as ONE definition.
 *
 * **WHY THIS FILE EXISTS.** These two builders lived inside
 * `AssetLifecycle.test.tsx` and a third test file needed them: screen 27 grew
 * the five-slot header, the header reads the asset, and a test that seeds only
 * its own payload renders a loading skeleton for ever. Copying them would have
 * made a second definition free to drift from the served shape — hard-won law 5,
 * which this repository has already paid for twice.
 *
 * ⚠ **`BATTERY`-SHAPED CASES MATTER AND MUST NOT BE "TIDIED".** `assigned` and
 * `assigned_address` are deliberately independent: an asset in inventory can
 * carry an address it does not occupy, and a caller that tests "is there an
 * address" instead of `assigned` draws a battery sitting in a warehouse at
 * someone else's street. That bug was found by a fixture built exactly this way.
 *
 * ⚠ **B14 rule 37 — every figure here is an ILLUSTRATION.** No reading, date or
 * consumption value in this file may be asserted as a fact about the product.
 */
import type { AssetDetail, AssetRow } from "@/api/endpoints";

export function asset(over: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-4022",
    asset_no: "M-4022",
    serial_no: "WT-1102",
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "active",
    status_name: "Installed/Active",
    behavior_class: "in_service",
    meter_type: "ami",
    meter_type_name: "AMI",
    read_method: "ami",
    read_method_name: "AMI",
    multiplier: "1.000000",
    // BR-AST-500: null is the state every meter loaded before 2026-08-28 is in.
    size_class: null,
    // The size AS A CLERK READS IT, beside the code (`DEF-AST-7130`).
    size_class_name: null,
    unit: "kgal",
    net_metering: false,
    manufacturer: "Neptune",
    model: "T-10",
    install_date: "2023-05-02",
    parent_asset_no: null,
    service_point_id: "sp-2",
    assigned_unit_id: "u-101a",
    assigned_to: "Unit A",
    assigned_address: "1408 Elm Street",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit", "reassign", "log_repair", "retire"],
    ...over,
  };
}


/** The FULL detail payload the four pages load — the served AST-02 shape. */
export function detail(over: Partial<AssetDetail> = {}): AssetDetail {
  return {
    ...asset(),
    specs: {
      form_class: null,
      register_digits: 9,
      firmware_version: null,
      seal_no: null,
      warranty_end: null,
      last_test_date: null,
      test_interval_months: 96,
      location_note: null,
      allocation_rule: null,
      loss_tolerance_pct: null,
      allocation_share_pct: null,
    },
    classifications: {
      asset_type: { code: "meter", name: "Meter" },
      meter_type: { code: "ami", name: "AMI" },
      read_method: { code: "ami", name: "AMI" },
    },
    billing_chain: {
      premises_id: "p-elm",
      premise_no: "P-00101",
      premise_address: "1408 Elm Street",
      unit_id: "u-101a",
      unit_label: "Unit A",
      account: null,
    },
    sub_assets: [],
    valuation: {
      supplier: "Itron Inc",
      purchase_cost: "164.0000",
      purchase_date: "2024-03-12",
      warranty_end: "2029-03-12",
      warranty_covered: true,
      depreciation_method: null,
      // The W4 served block — the r10 worked case at the FORMULA's figures
      // ($19.8167/$144.1833; r10's $19.83/$144.17 is the reported delta).
      present_value: "144.1833",
      accumulated_depreciation: "19.8167",
      age_months: 29,
      life_months: 240,
      book_value_amount: null,
      book_value_treatment: null,
      currency: "USD",
    },
    lifecycle: {
      age_months: 29,
      expected_life_years: 20,
      certification_due: null,
      replacement_year: 2044,
    },
    linked_meter: null,
    ...over,
  };
}
