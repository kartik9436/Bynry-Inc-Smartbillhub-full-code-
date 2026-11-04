/**
 * Example data for the bulk bill run — the component tests and the capture
 * harness share it. Every figure, name and date is example data (B14 rule 37),
 * shaped exactly as the served reads answer (`run_scope.preview`, the
 * Check's `check_store` reads, `signoff`, `not_in_run`, `/summary`, `/breaks`).
 * TEST AND HARNESS ONLY — nothing in the product imports this file.
 */
import type { BillRunPricingShadow } from "@/api/endpoints";
import type {
  CheckAccount,
  CheckAccountFinding,
  CheckCategoryGroup,
  CheckReadyPage,
  CheckReadyRow,
  CheckReport,
  CheckSeverity,
  CheckSummary,
  CheckTag,
  CheckTagPage,
  CheckTagRow,
  CheckTiles,
  FixHere,
  NotInRunGroup,
  RunTemplateRow,
  ScopeMissingMeterRow,
  ScopeNobodyRow,
  ScopePreview,
  ScopeProblem,
  ServedNotInRun,
  ServedNotInRunRow,
  SignOffSummary,
} from "@/api/bulkRunEndpoints";
import type { CycleRow } from "@/api/endpoints";
import type { BillTemplateLibrary } from "@/api/billingOpsEndpoints";
import type {
  BillRunBreaksPayload,
  BillRunDetail,
  BillRunReadLock,
  BillRunSummary,
  BillRunTotals,
} from "@/features/billing/billRunEndpoints";

export const CYCLE_ID = "11111111-1111-4111-8111-111111111111";
export const TEMPLATE_ID = "22222222-2222-4222-8222-222222222222";
export const RUN_ID = "33333333-3333-4333-8333-333333333333";

export function cycleRow(): CycleRow {
  return {
    id: CYCLE_ID,
    code: "Cycle 3",
    routes: ["r1", "r2"],
    window_start: null,
    window_end: null,
    bill_date: "2026-10-01",
    due_days: 21,
    due_date: "2026-10-22",
    expected: 1482,
    collected: null,
    progress: null,
    status: "open",
    lifecycle_status: "active",
    name: "Riverside",
    frequency: "Monthly",
    start_day: 1,
    days_to_complete: 5,
    next_period: { period_start: "2026-09-01", period_end: "2026-09-30" },
  } as unknown as CycleRow;
}

export function templateLibrary(): BillTemplateLibrary {
  return {
    template: { id: TEMPLATE_ID, name: "Standard bill", template_type: "standard", is_fallback: true },
    current: { version_no: 4, layout_key: "classic", published_on: "2026-06-01", options: {} },
    versions: [],
    layouts: [],
    publish_role: "system_admin",
    published_status: "published",
    unavailable: [],
  };
}

export const SERVICES = [
  { service: "electric", name: "Electric", enabled: true },
  { service: "water", name: "Water", enabled: true },
  { service: "sewer", name: "Sewer", enabled: true },
  { service: "trash", name: "Trash", enabled: true },
  { service: "storm_water", name: "Storm water", enabled: true },
  // The rest of the eleven (BR-RAT-024), served and switched off — the
  // catalogue is always whole; what varies is what a utility sells (G47).
  { service: "gas", name: "Gas", enabled: false },
  { service: "solar", name: "Solar", enabled: false },
  { service: "broadband", name: "Broadband", enabled: false },
  { service: "thermal_heat", name: "Thermal/Heat", enabled: false },
  { service: "battery", name: "Battery", enabled: false },
  { service: "fire", name: "Fire", enabled: false },
];

function problem(code: string, severity: "refusal" | "warning", field: string | null, key: string, params: Record<string, unknown> = {}): ScopeProblem {
  return { code, severity, field, message_key: `billing.runScope.${key}`, params };
}

const RUN_REF = { run_id: "run-0231", run_no: "BR-0231", label: "August 2026 · Riverside", period_start: "2026-08-01", period_end: "2026-08-31" };

/** `serverOrder` — the warnings exactly as the live server listed them on the
 *  J72 seed at E11 (2026-10-01): bill date first, both period-end lines after,
 *  and ONE unit with nobody to bill (DEF-BIL-8672, DEF-BIL-8673). */
export type ScopeState = "continuous" | "gap" | "overlap" | "warnings" | "problems" | "serverOrder";

export function scopePreview(state: ScopeState = "continuous"): ScopePreview {
  const always = [
    problem("units_nobody_to_bill", "warning", null, "warning.nobodyToBill", { count: 7 }),
    problem("services_no_meter", "warning", null, "warning.missingMeter", { count: 9 }),
  ];
  const refusals: ScopeProblem[] = [];
  const warnings: ScopeProblem[] =
    state === "serverOrder"
      ? [
          problem("bill_day_differs", "warning", "bill_date", "warning.billDayDiffers", { billDay: 1 }),
          problem("due_days_changed", "warning", "due_days", "warning.dueDaysChanged", { cycleDays: 21 }),
          problem("period_length", "warning", "period_end", "warning.periodLength", { days: 45, expected: 30, frequency: "Monthly" }),
          problem("period_after_today", "warning", "period_end", "warning.periodAfterToday"),
          problem("units_nobody_to_bill", "warning", null, "warning.nobodyToBill", { count: 1 }),
          problem("services_no_meter", "warning", null, "warning.missingMeter", { count: 1 }),
        ]
      : [...always];
  let continuity: ScopePreview["continuity"] = { state: "continuous", run: RUN_REF };
  if (state === "gap") {
    continuity = { state: "gap", from: "2026-10-01", to: "2026-10-09", days: 9, run: RUN_REF };
    warnings.unshift(problem("period_gap", "warning", "period_start", "warning.periodGap", { from: "2026-10-01", to: "2026-10-09", days: 9 }));
  }
  if (state === "overlap") {
    continuity = { state: "overlap", run: RUN_REF };
    refusals.push(problem("period_overlap", "refusal", "period_start", "refusal.periodOverlap", { run_id: "run-0231", runNo: "BR-0231", from: "2026-09-15", to: "2026-09-30" }));
  }
  if (state === "warnings") {
    warnings.unshift(
      problem("period_length", "warning", "period_end", "warning.periodLength", { days: 45, expected: 30, frequency: "Monthly" }),
      problem("bill_day_differs", "warning", "bill_date", "warning.billDayDiffers", { billDay: 1 }),
      problem("due_days_changed", "warning", "due_days", "warning.dueDaysChanged", { cycleDays: 21 }),
      problem("template_not_usual", "warning", "template_id", "warning.templateNotUsual"),
    );
  }
  if (state === "problems") {
    refusals.push(
      problem("label_missing", "refusal", "label", "refusal.labelMissing"),
      problem("period_order", "refusal", "period_end", "refusal.periodOrder"),
      problem("bill_date_needed", "refusal", "bill_date", "refusal.billDateNeeded"),
      problem("due_days_invalid", "refusal", "due_days", "refusal.dueDaysInvalid"),
      problem("template_unpublished", "refusal", "template_id", "refusal.templateUnpublished"),
    );
    warnings.unshift(problem("no_run_number_series", "warning", null, "warning.noRunNumberSeries"));
  }
  return {
    refusals,
    warnings,
    can_start: refusals.length === 0,
    counts: {
      units_in_cycle: 1482,
      accounts_to_bill: 1406,
      regular_accounts: 1394,
      master_accounts: 12,
      meters: 2210,
      sub_meters: 64,
      behind_the_meter: 118,
      missing_meter: 9,
      units_nobody_to_bill: 7,
    },
    last_run_counts: { run_id: "run-0231", accounts_to_bill: 1398, regular_accounts: 1387, master_accounts: 11 },
    continuity,
    previous_run: RUN_REF,
    cycle: {
      id: CYCLE_ID,
      code: "Cycle 3",
      name: "Riverside",
      frequency: "Monthly",
      reads_start_day: 1,
      days_to_complete: 5,
      bill_day: 1,
      due_days: 21,
      routes: 14,
      first_run_date: "2025-01-01",
      runs_so_far: 20,
      status: "active",
    },
    previous_runs: {
      count: 3,
      next: null,
      previous: null,
      results: [
        { id: "run-0231", run_no: "BR-0231", label: "August 2026 · Riverside", cycle_id: CYCLE_ID, period_start: "2026-08-01", period_end: "2026-08-31", issued_at: "2026-09-01", accounts: 1398, bills_issued: 1371, value: "209944.1800", value_currency: "USD", held: 0, status: "issued", bill_type: "cycle", created_at: "2026-09-01", ran_by_name: "J. Ortiz" },
        { id: "run-0230", run_no: "BR-0230", label: "July 2026 · Riverside", cycle_id: CYCLE_ID, period_start: "2026-07-01", period_end: "2026-07-31", issued_at: "2026-08-01", accounts: 1390, bills_issued: 1366, value: "211402.5500", value_currency: "USD", held: 0, status: "issued", bill_type: "cycle", created_at: "2026-08-01", ran_by_name: "J. Ortiz" },
        { id: "run-0229", run_no: "BR-0229", label: "July 2026 · retry", cycle_id: CYCLE_ID, period_start: "2026-07-01", period_end: "2026-07-31", issued_at: null, accounts: 0, bills_issued: 0, value: null, value_currency: "USD", held: 0, status: "abandoned", bill_type: "cycle", created_at: "2026-07-31", ran_by_name: "S. Cohen" },
      ],
    },
  };
}

const NAMES = ["Sara Cohen", "Kofi Mensah", "Elm St Apartments", "Maria Alvarez", "Omar Haddad", "Priya Natarajan", "Luis Alvarez", "Grace Okafor"];

export function accountNo(n: number): string {
  return `AC-2026-${String(12880 + n).padStart(5, "0")}`;
}

/** The Check's tiles as `check_store.counts` answers them. */
export function checkTiles(checked = true): CheckTiles & { left_out: number } {
  return checked
    ? { accounts: 1406, ready: 1394, to_price: 1380, held: 12, waived: 2, undecided: 0, decisions: 7, blocked: 4, silent: 1, left_out: 1, warnings: 3, problem_types: 6, stale: 0, checked_from: "2026-10-01T09:01:00Z", checked_at: "2026-10-01T09:04:00Z" }
    : { accounts: 0, ready: 0, decisions: 0, blocked: 0, silent: 0, left_out: 0, warnings: 0, problem_types: 0, stale: 0, checked_from: null, checked_at: null };
}

type TagSeed = [code: string, category: string, severity: CheckSeverity, screen: string, count: number, choices: string[], fixHere: FixHere];

/** A slice of the server taxonomy (`apps/billing/check_taxonomy.py`), in its order. */
const TAG_SEEDS: TagSeed[] = [
  ["late_fee", "payments_balances", "decision", "check", 1, ["apply", "waive"], null],
  ["autopay_card_expiring", "payments_balances", "warning", "payments", 3, [], null],
  ["bounced_payment_not_reversed", "payments_balances", "decision", "payments", 0, [], null],
  ["missing_read", "readings", "decision", "check", 3, ["estimate", "hold", "bill_without_service"], null],
  ["anchor_meter_exchanged", "meter_history", "decision", "reads", 2, ["estimate", "hold"], null],
  ["unit_has_no_plan", "plans_rates", "blocks", "accounts", 2, [], "set_plan"],
  ["account_has_no_unit", "accounts_units", "blocks", "accounts", 1, [], null],
  ["base_only_billing", "accounts_units", "decision", "check", 2, ["include", "waive"], null],
  ["account_has_nothing_to_bill", "accounts_units", null, "accounts", 1, [], null],
  ["connection_size_unresolved_for_sized_schedule", "assets_connections", "blocks", "assets", 1, [], "set_size"],
  ["billing_continuity", "billing_period", "decision", "check", 2, ["bill_as_is", "investigate"], null],
];

function tagOf(seed: TagSeed): CheckTag {
  const [code, category, severity, screen, n, choices, fixHere] = seed;
  return {
    code,
    category,
    severity,
    fix: screen,
    fix_action: { kind: screen === "check" ? "decide" : "link", screen },
    label_key: `billing.run.reason.${code}`,
    suggests: false,
    count: n,
    choices,
    default_choice: choices[0] ?? null,
    answer_for_all: null,
    fix_here: fixHere,
  };
}

export function checkSummary(checked = true): CheckSummary {
  const categories: CheckCategoryGroup[] = [];
  for (const seed of checked ? TAG_SEEDS : []) {
    const tag = tagOf(seed);
    let group = categories.find((one) => one.category === tag.category);
    if (group === undefined) {
      group = { category: tag.category, label_key: `billing.check.category.${tag.category}`, count: 0, tags: [] };
      categories.push(group);
    }
    group.tags.push(tag);
    group.count += tag.count;
  }
  return {
    bill_run_id: RUN_ID,
    checked,
    tiles: checkTiles(checked),
    categories,
    unmapped: [],
    stop: null,
    unavailable: [],
    units_with_nobody_to_bill: checked ? 1 : null,
  };
}

/** Which accounts carry which code — the rows `?tag=` pages. */
const ROWS: Record<string, [n: number, service: string | null][]> = {
  late_fee: [[9, null]],
  autopay_card_expiring: [[12, null], [13, null], [14, null]],
  missing_read: [[1, "water"], [2, "water"], [7, "water"]],
  anchor_meter_exchanged: [[1, "water"], [3, "water"]],
  unit_has_no_plan: [[1, null], [2, null]],
  account_has_no_unit: [[5, null]],
  base_only_billing: [[10, null], [11, null]],
  connection_size_unresolved_for_sized_schedule: [[4, "fire"]],
  // DEF-BIL-8472 — the walk's pair: 15 is a GAP, 16 an OVERLAP (Investigate only).
  billing_continuity: [[15, null], [16, null]],
};

function codesOf(n: number): string[] {
  return Object.entries(ROWS)
    .filter(([, rows]) => rows.some(([one]) => one === n))
    .map(([code]) => code);
}

export function checkTagPage(code: string, page = 1, per = 50): CheckTagPage {
  const seed = TAG_SEEDS.find((one) => one[0] === code) as TagSeed;
  const tag = tagOf(seed);
  const rows = (ROWS[code] ?? []).map(([n, service]): CheckTagRow => ({
    account_id: `acc-${n}`,
    account_no: accountNo(n),
    customer_name: NAMES[n % NAMES.length],
    address: `${100 + n} Elm St`,
    unit_label: `Unit ${n}`,
    unit_id: `unit-${n}`,
    service_code: service,
    // DEF-BIL-8701 — the meter on the row's service, by its number (rule 31).
    meters: service === "water" ? [`W-${10440 + n}`] : [],
    // DEF-BIL-10200 — a late-fee row carries the run's figure and bills unless waived.
    message_key: code === "late_fee" ? "billing.check.lateFee.found" : null,
    params: code === "late_fee" ? { amount: "5.00", overdue: "100.00", currency: "USD", bills: 1 } : {},
    also_has: codesOf(n).filter((other) => other !== code),
    fix_here: tag.fix_here,
    choices: code === "billing_continuity" && n === 16 ? ["investigate"] : tag.choices,
    answer:
      code === "base_only_billing" && n === 10 ? "waive" : code === "missing_read" && n === 7 ? "estimate" : code === "late_fee" ? "apply" : null,
    answer_source:
      (code === "base_only_billing" && n === 10) || (code === "missing_read" && n === 7) ? "account" : code === "late_fee" ? "default" : null,
    answer_quantity: code === "missing_read" && n === 7 ? "7" : null,
    answer_unit: code === "missing_read" && n === 7 ? "kgal" : null,
    basis: code === "missing_read" && n !== 2 ? { quantity: "5.76", unit: "kgal", high: "8.1", low: "3.2", months: 12 } : null,
    stale: false,
  }));
  const lateFees = code === "late_fee" ? { late_fees: { accounts: rows.length, total: "5.00", waived: 0, currency: "USD" } } : {};
  return { tag, results: rows, count: rows.length, page, per, ...lateFees };
}

export function checkAccount(accountId: string): CheckAccount {
  const n = Number(accountId.replace("acc-", ""));
  const findings: CheckAccountFinding[] = [];
  for (const code of codesOf(n)) {
    const seed = TAG_SEEDS.find((one) => one[0] === code) as TagSeed;
    const tag = tagOf(seed);
    for (const [one, service] of ROWS[code]) {
      if (one !== n) continue;
      findings.push({
        code,
        category: tag.category,
        severity: tag.severity,
        service_code: service,
        message_key: null,
        params: {},
        tag: { code, label_key: tag.label_key, fix_action: tag.fix_action },
        choices: tag.choices,
        fix_here: tag.fix_here,
        answer: null,
      });
    }
  }
  return {
    account_id: accountId,
    account_no: accountNo(n),
    account_kind: "regular",
    customer_name: NAMES[n % NAMES.length],
    address: `${100 + n} Elm St`,
    unit_label: `Unit ${n}`,
    status: findings.some((f) => f.severity === "blocks") ? "blocked" : "decision",
    findings,
  };
}

export function checkReady(kind = ""): CheckReadyPage {
  const all: CheckReadyRow[] = Array.from({ length: 12 }, (_, i) => ({
    account_id: `ready-${i}`,
    account_no: `AC-2026-${String(30000 + i * 17).padStart(5, "0")}`,
    account_kind: i % 6 === 0 ? "master" : "regular",
    left_out: i === 3,
    customer_name: NAMES[i % NAMES.length],
    address: `${200 + i} Oak Ave`,
    unit_label: `Unit ${i}`,
    services: i === 1 ? ["electric", "water"] : ["water"],
    plan_name: "Residential 2026",
    all_read: i !== 2,
  }));
  const rows = kind === "" ? all : all.filter((row) => row.account_kind === kind);
  return { results: rows, count: rows.length, left_out: 1, page: 1, per: 50 };
}

/** DEF-BIL-8720 — with `planLater`, one bill holds back $225.00 of a payment
 *  plan as not yet due (BR-BIL-1061), so Amount due is $225.00 less and the
 *  balances table carries the plan line that makes it foot. */
export function signOffSummary(options: { planLater?: boolean } = {}): SignOffSummary {
  const summary = baseSignOffSummary();
  if (options.planLater !== true) return summary;
  const due = "235895.4100"; // 236,120.41 − 225.00
  return {
    ...summary,
    run_summary: { ...summary.run_summary, amount_due: due },
    payments_and_balances: { ...summary.payments_and_balances, plan_not_yet_due: "225.0000", amount_due: due },
  };
}

function baseSignOffSummary(): SignOffSummary {
  return {
    bill_run_id: RUN_ID,
    sent: false,
    run_summary: { bills: 1371, accounts_to_bill: 1406, this_run_charges: "214386.5200", payments_applied: 212, payments_count: 1840, amount_due: "236120.4100" },
    who_is_billed: {
      accounts: { to_bill: 1406, billed: 1371, regular: 1360, master: 11, not_billed: 37, blocked: 4, held: 7, nothing_to_bill: 1, left_out: 1, waived: 2, failed_to_draft: 2, reconciles: true },
      units: { in_cycle: 1482, billed: 1440, own_account: 1360, through_master: 80, not_billed: 42, account_not_billed: 34, nothing_to_bill: 1, nobody_to_bill: 7, reconciles: true },
    },
    usage_and_charges: {
      services: [
        { service_code: "electric", bills: 1302, usage: [{ quantity: "612340", unit: "kWh" }], usage_charges: "80212.4000", base_charges: "17000.0000", total: "97212.4000" },
        { service_code: "water", bills: 1371, usage: [{ quantity: "18420", unit: "kgal" }], usage_charges: "50410.9400", base_charges: "17000.0000", total: "67410.9400" },
      ],
      services_subtotal: "164623.3400",
      other: { taxes: "12480.1800", fees: "39133.0000", credits_and_adjustments: "-1850.0000" },
      this_run_charges: "214386.5200",
      reconciles: true,
    },
    payments_and_balances: {
      previous_balance: "48210.0000",
      payments_and_credits_applied: "26476.1100",
      accounts_with_payments_applied: 212,
      // DEF-BIL-8682 — the same figure parted by payments' own type column;
      // the two add back to it (25,260.51 + 1,215.60 = 26,476.11).
      payments_applied: "25260.5100",
      payments_count: 1840,
      credits_applied: "1215.6000",
      credits_count: 41,
      this_run_charges: "214386.5200",
      plan_not_yet_due: "0",
      amount_due: "236120.4100",
      reconciles: true,
      how_paid: {
        credit_covers: { bills: 14, amount: "0.0000" },
        level_pay: { bills: 88, amount: "10560.0000" },
        autopay: { bills: 402, amount: "61230.2200" },
        plan_instalment: { bills: 6, amount: "270.0000" },
        by_due_date: { bills: 861, amount: "164060.1900" },
      },
      credit_covers_bills: {
        results: [{ account_id: "acc-30", account_no: "AC-2026-12910", bill_total: "49.4400", credit: "500.0000", left_after: "450.5600", currency: "USD" }],
        count: 14,
      },
    },
    by_customer_type: [
      // The STORED class code, as the server sends it (DEF-BIL-8683: the live
      // screen printed `institutional`; this fixture used to send the word).
      { category: "residential", bills: 1212, amount: "148220.1000" },
      { category: "commercial", bills: 146, amount: "61904.3000" },
      { category: "institutional", bills: 13, amount: "4262.1200" },
    ],
    // `account_id` — record links (PO 2026-10-19): the number opens the account.
    waived: [{ account_no: accountNo(10), account_id: "acc-10", amount: "26.0000", currency: "USD" }],
    waived_total: "26.0000",
    currency: "USD",
  };
}

function notInRow(n: number, group: NotInRunGroup, reason: string | null, queue: ServedNotInRunRow["queue"] = null): ServedNotInRunRow {
  return {
    key: `account:acc-${n}`,
    kind: "account",
    group,
    reason,
    also: group === "blocked" && n === 1 ? 1 : 0,
    account_id: `acc-${n}`,
    account_no: accountNo(n),
    account_kind: "regular",
    unit_id: `unit-${n}`,
    customer_name: NAMES[n % NAMES.length],
    address: `${100 + n} Elm St`,
    unit_label: `Unit ${n}`,
    queue,
  };
}

export function notInRun(group = "", sent = false): ServedNotInRun {
  const queued = (): ServedNotInRunRow["queue"] =>
    sent ? { reason_code: "check_blocked", held_on: "2026-10-01", next_cycle: false, resolved_by_run_id: null, age_days: 0 } : null;
  const all: ServedNotInRunRow[] = [
    notInRow(5, "blocked", "account_has_no_unit", queued()),
    notInRow(4, "blocked", "connection_size_unresolved_for_sized_schedule", queued()),
    notInRow(7, "held", "hold", queued()),
    notInRow(6, "nothing", "account_has_nothing_to_bill"),
    { ...notInRow(33, "left_out", "staff_left_out_by_clerk", queued()), account_id: "ready-3" },
    {
      key: "unit:unit-90",
      kind: "unit",
      group: "nobody",
      reason: "unit_has_no_billable_account",
      also: 0,
      account_id: null,
      account_no: null,
      account_kind: null,
      unit_id: "unit-90",
      customer_name: null,
      address: "190 Elm St",
      unit_label: "Unit 90",
      queue: null,
    },
  ];
  const counts = { blocked: 2, held: 1, nothing: 1, left_out: 1, waived: 0, nobody: 1, accounts: 5, units: 1 };
  const rows = group === "" ? all : all.filter((row) => row.group === group);
  return { bill_run_id: RUN_ID, sent, counts, results: rows, count: rows.length, page: 1, per: 50 };
}

export function checkReport(status = ""): CheckReport {
  const summary = checkSummary();
  const accounts = [
    { account_id: "acc-5", account_no: accountNo(5), status: "blocked", checked_at: "2026-10-01T09:04:00Z", problems: [{ code: "account_has_no_unit", severity: "blocks" as const, service_code: null }] },
    {
      account_id: "acc-1",
      account_no: accountNo(1),
      status: "decision",
      checked_at: "2026-10-01T09:04:00Z",
      problems: [{ code: "missing_read", severity: "decision" as const, service_code: "water" }, { code: "unit_has_no_plan", severity: "decision" as const, service_code: null }],
      // DEF-BIL-8555 — its own answer and the tag's Answer for all.
      decisions: [
        { case: "missing_read", choice: "estimate", scope: "account" as const, reason: null, quantity: "7", unit: "kgal", service_code: "water", decided_by: "Priya Menon", decided_at: "2026-10-01T09:12:00Z" },
        { case: "unit_has_no_plan", choice: "hold", scope: "all" as const, reason: null, quantity: null, unit: null, service_code: null, decided_by: "Alex Reed", decided_at: "2026-10-01T09:10:00Z" },
      ],
    },
    { account_id: "ready-0", account_no: "AC-2026-30000", status: "ready", checked_at: "2026-10-01T09:04:00Z", problems: [] },
  ];
  const rows = status === "" ? accounts : accounts.filter((row) => row.status === status);
  return { bill_run_id: RUN_ID, sent: true, tiles: summary.tiles, categories: summary.categories, accounts: { results: rows, count: rows.length, page: 1, per: 50 } };
}

export function runDetail(phase = "draft"): BillRunDetail {
  return {
    id: RUN_ID,
    run_no: "BR-0232",
    // DEF-BIL-8680 / 8685 — the name the clerk typed and who signed it off,
    // as `selectors.run_detail_dict` serves them.
    label: "September 2026 · Riverside",
    signed_off:
      phase === "authorised" || phase === "issued" ? { by: "Dana Whitfield", at: "2026-10-01T14:42:00Z" } : null,
    phase,
    status: phase === "issued" ? "issued" : "draft",
    scope: { cycle_id: CYCLE_ID, period_start: "2026-09-01", period_end: "2026-09-30", bill_date: "2026-10-01", due_days: 21, bill_type: "cycle", services: null, account_id: null, parent_run_id: null },
    decisions: { taken: 0, by_case: {} },
    counts: { accounts: 1406, drafts: 1371, bills_issued: phase === "issued" ? 1369 : 0, breaks: phase === "issued" ? 2 : 0, breaks_total: 2, breaks_by_stage: {}, held: 9 },
    findings_summary: null,
    issued_at: null,
    created_at: "2026-10-01T09:00:00Z",
  };
}

/** DEF-BIL-8685 / 8809 — Meter Reads' answer for the reads the sent bills
 *  priced, on its own read (`GET …/read-lock`) since it left the run read. */
export function readLock(phase = "draft"): BillRunReadLock {
  return {
    bill_run_id: RUN_ID,
    meter_reads: phase === "issued" ? { state: "locked", reads: 2210, locked: 2210 } : null,
  };
}

/** DEF-BIL-8809 — `GET …/totals`, the summary's headline as the server serves
 *  it (`selectors.run_totals_dict`): the same figures as `summary()`. */
export function totals(): BillRunTotals {
  const full = summary();
  return {
    bill_run_id: full.bill_run_id,
    bills: full.bills,
    amount: full.amount,
    currency: full.currency,
    gross_amount: full.gross_amount,
    credits_applied: full.credits_applied,
    credit_count: full.credit_count,
  };
}

export function summary(): BillRunSummary {
  return {
    bill_run_id: RUN_ID,
    accounts: 1371,
    bills: 1371,
    consumption: [
      { service: "electric", quantity: "612340", unit: "kWh" },
      { service: "water", quantity: "18420", unit: "kgal" },
      { service: "sewer", quantity: "17880", unit: "kgal" },
    ],
    amount: "214386.5200",
    currency: "USD",
    gross_amount: "216236.5200",
    credits_applied: "1850.0000",
    credit_count: 41,
    credits_named: [],
    by_category: [
      { axis: "service", key: "electric", bills: 1302, amount: "97212.4000", currency: "USD" },
      { axis: "service", key: "water", bills: 1371, amount: "67410.9400", currency: "USD" },
      { axis: "service", key: "sewer", bills: 1340, amount: "20318.0000", currency: "USD" },
      { axis: "service", key: "trash", bills: 1210, amount: "17346.0000", currency: "USD" },
      { axis: "service", key: "storm_water", bills: 1371, amount: "5183.0000", currency: "USD" },
      { axis: "consumer_category", key: "Residential", bills: 1212, amount: "148220.1000", currency: "USD" },
      { axis: "consumer_category", key: "Commercial", bills: 146, amount: "61904.3000", currency: "USD" },
      { axis: "consumer_category", key: "Government", bills: 13, amount: "4262.1200", currency: "USD" },
    ],
    axes_status: "PROPOSED",
    coverage: [],
    problems: [],
  };
}

export function breaks(): BillRunBreaksPayload {
  return {
    bill_run_id: RUN_ID,
    breaks: [
      { id: "b1", account_id: "acc-20", account_no: "AC-2026-00902", stage: "assemble-document", reason: "template_cannot_render", detail: "", retryable: true, resolution: null, job_id: null, raised_at: null, updated_at: null },
      { id: "b2", account_id: "acc-21", account_no: "AC-2026-01144", stage: "price-usage", reason: "plan_has_no_tariff_for_service", detail: "", retryable: false, resolution: null, job_id: null, raised_at: null, updated_at: null },
    ],
    break_count: 2,
    breaks_by_stage: {},
    includes_resolved: false,
  };
}

// ── DEF-BIL-8221 · DEF-BIL-8222 — the Scope panels' rows and the templates ──

export const UNIT_NOBODY_ID = "33333333-3333-4333-8333-333333333301";
export const UNIT_NO_METER_ID = "33333333-3333-4333-8333-333333333302";

export function scopeNobodyRows(): ScopeNobodyRow[] {
  return [
    {
      unit_id: UNIT_NOBODY_ID,
      address: "1416 Elm St",
      unit: "Unit B",
      services: ["water"],
      last_account: { account_no: "AC-2026-00099", account_id: "acc-99", moved_out: "2026-08-12" },
    },
  ];
}

export function scopeMissingMeterRows(): ScopeMissingMeterRow[] {
  return [{ unit_id: UNIT_NO_METER_ID, address: "1408 Elm St", unit: "Unit A", service: "gas", account_no: "AC-2026-00101", account_id: "acc-101" }];
}

export const SECOND_TEMPLATE_ID = "22222222-2222-4222-8222-222222222223";

export function runTemplates(): RunTemplateRow[] {
  return [
    { id: TEMPLATE_ID, name: "Standard bill", version_no: 4, category: null },
    { id: SECOND_TEMPLATE_ID, name: "Winter insert", version_no: 1, category: null },
  ];
}

/** The pricing check's states (`GET …/pricing-shadow`, DEF-BIL-10121). */
export type PricingState = "none" | "differ" | "nothing" | "failed" | "hold" | "unreadable" | "no_cycle";

/** `GET /billing/runs/{id}/pricing-shadow` as `shadow_report.report_for_prepared` answers it. */
export function pricingShadow(state: "none" | "differ" | "nothing"): BillRunPricingShadow {
  const base: BillRunPricingShadow = {
    accounts: 1406,
    attempted: 1406,
    agreed: 1406,
    disagreed: 0,
    chain_refused: 0,
    not_attempted: 0,
    by_step: {},
    blocked_by_reason: {},
    steps: [],
    classes: [],
    blocked_classes: [],
    accounts_detail: [],
  };
  if (state === "nothing") return { ...base, attempted: 0, agreed: 0, not_attempted: 1406 };
  if (state === "none") return base;
  const differing = ["AC-2026-00031", "AC-2026-00047", "AC-2026-00112"].map((accountNo, index) => ({
    account_id: `acc-shadow-${index + 1}`,
    account_no: accountNo,
    status: "disagreed",
    refusal_step: null,
    refusal_type: null,
    refusal_sentence: null,
    blocked_reason: null,
    blocked_detail: null,
    live_summary: null,
    divergences: [
      {
        step: "R3/R4",
        service: "water",
        live: "18.5000",
        chain: "22.7000",
        live_display: "18.50",
        chain_display: "22.70",
        is_money: true,
        note: null,
        sentence: `R3/R4 water on ${accountNo}: billing today says 18.50, the new rules say 22.70`,
      },
    ],
  }));
  return {
    ...base,
    agreed: 1403,
    disagreed: 3,
    by_step: { "R3/R4": 3 },
    steps: [{ step: "R3/R4", accounts: differing.map((row) => row.account_no), count: 3, refusals: 0, divergences: 3 }],
    classes: [
      {
        class_id: "R3/R4 · the two paths resolved different figures",
        kind: "divergence",
        step: "R3/R4",
        what: "the two paths resolved different figures",
        refusal_type: null,
        services: ["water"],
        accounts: 3,
        occurrences: 3,
        example_account_no: "AC-2026-00031",
        example_sentence: differing[0].divergences[0].sentence,
        example_service: "water",
        example_live: "18.5000",
        example_chain: "22.7000",
        example_live_display: "18.50",
        example_chain_display: "22.70",
        example_live_summary: null,
        is_money: true,
      },
    ],
    accounts_detail: [
      ...differing,
      { ...differing[0], account_id: "acc-shadow-agreed", account_no: "AC-2026-00001", status: "agreed", divergences: [] },
    ],
  };
}
