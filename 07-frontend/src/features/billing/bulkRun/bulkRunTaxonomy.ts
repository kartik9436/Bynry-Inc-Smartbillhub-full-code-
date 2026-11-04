// ── Trace ──────────────────────────────────────────────
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/inventory.md §3.3 (nine
//           categories, their tags and severities, as drawn)
// Plan:     15-bulk-bill-run-build-plan.md B10 (the taxonomy — engine lane) · F8
// Defects:  DEF-BIL-8216 (this file is INTERIM — the server owns the taxonomy
//           once A4 is served) · DEF-BIL-8209 (codes with no clerk label) ·
//           DEF-BIL-8210 (warnings not on the findings payload) · DEF-BIL-8211
//           (no payment checks)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE CHECK NO LONGER READS THIS FILE (DEF-BIL-8216, 2026-09-30).** The
 * Check step reads the SERVER's grouped findings, whose taxonomy is
 * `apps/billing/check_taxonomy.py`, and `groupFindings` is deleted. What still
 * reads it is Sign off's *Failed to draft* panel, whose `/breaks` rows carry a
 * bare reason code and no fix screen — `breakTag` and `fixScreenOf` name the
 * break and link it to where it is fixed. It goes when `/breaks` serves the
 * taxonomy's own `fix_action`.
 *
 * WHICH ENGINE CODE IS WHICH DRAWN TAG — INTERIM, UNTIL THE SERVER SERVES IT.
 *
 * Plan B10 makes this map the ENGINE's (code → category · tag · severity · fix
 * screen), served on the grouped read A4. Neither exists yet, so the Check step
 * groups the served `/findings` + `/exceptions` rows through this table. It is
 * the ONE place the mapping lives on the client, and `DEF-BIL-8216` says to
 * delete it when A4 lands.
 *
 * **A tag with `codes: []` has no source today.** It is still listed — the
 * drawing lists it — and the screen shows it as not available rather than as a
 * zero. That covers the nine Payments & balances tags (`DEF-BIL-8211`) and the
 * warning tags (`DEF-BIL-8210`).
 *
 * **Severities follow changes rows 44–46 (PO 2026-09-30)**, not the first
 * drawing: no check stops an account or fixes anything by itself; every former
 * stop with a sensible answer is a DECISION with a suggested answer, and only
 * no unit, master coverage, no size, pricing refused and the utility-wide stops
 * stay blocking. Where the engine still REPORTS one of those decision tags as a
 * blocked problem, its rows sit in the ruled tag with a Fix link and no answer
 * until the engine lane serves the case.
 *
 * **Nobody to bill is not a tag** (inventory §0): a unit with nobody to bill
 * has no account, so it is listed on Scope and in Not in this run, never on an
 * account row.
 */
import type { Severity } from "@/api/bulkRunEndpoints";

interface TagDefinition {
  id: string;
  category: string;
  severity: Severity;
  /** The engine's reason codes and decision cases this tag gathers. */
  codes: readonly string[];
}

export const CATEGORIES = [
  "payments",
  "readings",
  "meterHistory",
  "plans",
  "accounts",
  "master",
  "assets",
  "period",
  "setup",
] as const;
export type CategoryId = (typeof CATEGORIES)[number];

/** Where a problem is fixed, when it is not fixed on the row (plan B14). */
export type FixScreen = "meterReads" | "accounts" | "plans" | "assets" | "premises" | "payments" | "settings";

interface Def extends TagDefinition {
  fix: FixScreen;
}

function tag(id: string, category: CategoryId, severity: Severity, fix: FixScreen, codes: readonly string[] = []): Def {
  return { id, category, severity, fix, codes };
}

/** In the drawing's order within each category (inventory §3.3). */
export const TAGS: readonly Def[] = [
  // Payments & balances — no payment fact is on the findings payload (DEF-BIL-8211).
  tag("paidAfterCutoff", "payments", "decision", "payments", ["paid_after_cutoff"]),
  tag("unmatchedPayment", "payments", "decision", "payments", ["unmatched_payment"]),
  tag("bouncedPayment", "payments", "decision", "payments", ["bounced_payment_not_reversed"]),
  tag("planInstalmentDue", "payments", "decision", "payments", ["plan_instalment_due"]),
  tag("levelPayOffTrack", "payments", "decision", "payments", ["level_pay_off_track"]),
  tag("lateFee", "payments", "decision", "payments", ["late_fee"]),
  tag("creditCoversBill", "payments", "warning", "payments", ["credit_covers_bill"]),
  tag("autopayCardExpiring", "payments", "warning", "payments", ["autopay_card_expiring"]),
  tag("depositNotPaid", "payments", "warning", "payments", ["deposit_not_paid"]),
  tag("inCollections", "payments", "warning", "payments", ["in_collections"]),
  // Readings
  tag("noReading", "readings", "decision", "meterReads", ["missing_read"]),
  tag("estimatedReading", "readings", "decision", "meterReads", ["estimated_read"]),
  tag("usageTooHigh", "readings", "decision", "meterReads", ["high_usage"]),
  tag("usageTooLow", "readings", "decision", "meterReads", ["low_usage"]),
  tag("noUsage", "readings", "decision", "meterReads", ["no_usage"]),
  tag("factorChanged", "readings", "decision", "meterReads", ["meter_factor"]),
  tag("meterReplaced", "readings", "decision", "meterReads", ["replacement"]),
  tag("trueUpDue", "readings", "decision", "meterReads", ["true_up"]),
  // Changes rows 45–46 (PO 2026-09-30): two former "auto" cases, now decisions
  // with a suggested answer. No engine case raises either yet (engine lane).
  tag("readingNoUnit", "readings", "decision", "meterReads", ["reading_has_no_unit", "reading_and_meter_have_no_unit"]),
  tag("possibleRollover", "readings", "decision", "meterReads", ["possible_rollover"]),
  tag("disputedReading", "readings", "decision", "meterReads", ["account_held_by_disputed_read"]),
  tag("readsNotPublished", "readings", "blocks", "meterReads", [
    "metering_has_not_published_reads",
    "missing_read_undecided_at_calculate",
  ]),
  // Meter history
  tag("meterSwapped", "meterHistory", "decision", "meterReads", ["anchor_meter_exchanged", "meter_swapped"]),
  tag("readingWentDown", "meterHistory", "decision", "meterReads", ["anchor_register_went_backwards"]),
  tag("touUnmatched", "meterHistory", "decision", "meterReads", ["anchor_tou_windows_unanchorable"]),
  tag("noMultiplier", "meterHistory", "decision", "meterReads", ["anchor_multiplier_unstated"]),
  // Changes row 44 (built 2026-10-01): a meter never read has no multiplier —
  // its own bucket (row 46). Hold (default) / Bill with multiplier 1.
  tag("meterNeverRead", "meterHistory", "decision", "meterReads", ["meter_has_no_multiplier"]),
  // Plans & rates
  // PO 2026-10-01 (BR-BIL-1063): no plan on the unit BLOCKS until the plan is
  // fixed — there is no customer-type default plan to answer it with.
  tag("noPlan", "plans", "blocks", "accounts", ["unit_has_no_plan"]),
  tag("planNotPublished", "plans", "decision", "plans", ["plan_not_published"]),
  tag("noPriceForService", "plans", "decision", "plans", ["plan_has_no_tariff_for_service"]),
  tag("noPriceInForce", "plans", "decision", "plans", ["tariff_has_no_version_in_force_at_service_date"]),
  tag("noChargeForType", "plans", "decision", "plans", ["no_charge_applies_to_this_customer_type"]),
  tag("pricingRefused", "plans", "blocks", "plans", ["rating_refused_to_price", "ruled_path_refused"]),
  tag("extraCharge", "plans", "decision", "plans", ["extra_charge"]),
  tag("billTooHigh", "plans", "decision", "plans", ["overcharge"]),
  tag("baseZero", "plans", "warning", "plans", ["base_not_set"]),
  // PO 2026-10-01: a capacity size with no base price bills $0.00 — a
  // warning, never a reason to leave the account out; no sign-off tick.
  tag("sizeBaseZero", "plans", "warning", "plans", ["base_size_not_priced"]),
  // PO 2026-10-01 (DEF-RAT-8004, option A): two versions of one rate schedule
  // in force on one date — the newest priced; a warning, no sign-off tick.
  tag("versionsOverlap", "plans", "warning", "plans", ["schedule_versions_overlap"]),
  // Accounts & units
  tag("noUnit", "accounts", "blocks", "accounts", ["account_has_no_unit"]),
  tag("standingChargesOnly", "accounts", "decision", "accounts", ["base_only_billing"]),
  tag("partlyDisconnected", "accounts", "blocks", "accounts", ["cut_covers_some_services_and_not_others"]),
  // Master accounts
  tag("coverageUnknown", "master", "blocks", "accounts", ["master_coverage_unresolved"]),
  tag("unitsOnTwoPlans", "master", "blocks", "accounts", ["master_coverage_spans_two_plans"]),
  tag("serviceRepeated", "master", "blocks", "accounts", ["master_coverage_repeats_a_service"]),
  tag("unitStateUnknown", "master", "blocks", "accounts", [
    "unbilled_unit_service_state_unreadable",
    "master_unbilled_units_unpriceable",
    "unit_service_priced_nowhere",
  ]),
  // Assets & connections
  tag("noSize", "assets", "blocks", "assets", ["connection_size_unresolved_for_sized_schedule"]),
  tag("noAssetCount", "assets", "blocks", "assets", ["unmetered_asset_count_undetermined"]),
  tag("noSizeClass", "assets", "blocks", "assets", ["installed_capacity_undetermined"]),
  // PO 2026-10-01: a meter with no recorded size on a schedule with per-size
  // minimums bills no minimum — a warning naming the meter, no sign-off tick.
  tag("meterSizeNotRecorded", "assets", "warning", "assets", ["meter_size_not_recorded"]),
  tag("missingMeter", "assets", "warning", "assets"),
  // Billing period
  tag("gapOrOverlap", "period", "decision", "meterReads", ["billing_continuity"]),
  tag("longOrShortPeriod", "period", "decision", "meterReads", ["days_threshold"]),
  tag("priceChangedMidPeriod", "period", "decision", "plans", ["price_changed_mid_period"]),
  // Setup
  tag("currencyNotSet", "setup", "blocks", "settings", ["tenant_currency_unresolved"]),
  tag("cityLimitsUnknown", "setup", "decision", "premises", ["premises_jurisdiction_unstated"]),
  tag("noBillNumberSeries", "setup", "warning", "settings"),
  tag("noServicesOnFile", "setup", "warning", "accounts", ["no_service_agreements"]),
  // An engine code this table does not know yet — never a raw code on screen.
  tag("otherBlock", "setup", "blocks", "accounts"),
  tag("otherDecision", "setup", "decision", "accounts"),
];

export const NOTHING_TO_BILL_CODES = ["account_has_nothing_to_bill"] as const;
export const NOBODY_TO_BILL_CODES = ["unit_has_no_billable_account", "cycle_has_no_service_points"] as const;

export function fallbackTag(source: "blocks" | "decision"): string {
  return source === "blocks" ? "otherBlock" : "otherDecision";
}

export const TAXONOMY = {
  categories: CATEGORIES,
  tags: TAGS,
  fallbackTag,
  nothingToBillCodes: NOTHING_TO_BILL_CODES,
  nobodyToBillCodes: NOBODY_TO_BILL_CODES,
};

/** DEF-BIL-8675 — the drawn tag an engine code belongs to, or null. Its
 *  `billing.bulkRun.tag.<id>.name` and `.meaning` are the clerk's words on the
 *  Check (D1 11–23); the engine's `billing.run.reason.*` sentences stay the
 *  older exceptions screen's. */
export function tagIdOf(code: string): string | null {
  return TAGS.find((entry) => entry.codes.includes(code))?.id ?? null;
}

export function fixScreenOf(tagId: string): FixScreen {
  return TAGS.find((entry) => entry.id === tagId)?.fix ?? "accounts";
}
