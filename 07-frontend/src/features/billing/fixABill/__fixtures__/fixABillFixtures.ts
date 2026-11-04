// ── Trace ──────────────────────────────────────────────
// Change:   CR-180-BRC10 — vitest fixtures shaped EXACTLY like the contract
//           (`12-governance/change-requests/CR-180-BRC10-fix-a-bill-revamp.md`,
//           §"The contract" and additions A1–A6).
// Drawing:  05-prototype/fix-a-bill-2026-10-12/*.png — the figures are the
//           drawing's example data (B14 rule 37: illustrations, not facts).
// ───────────────────────────────────────────────────────
/**
 * Every payload the revamped Fix a bill reads, as the SERVER shapes it:
 * decimal strings at four places, codes not words, ids that must never reach
 * the screen (B14 rule 31). A fake that answers anything else would let the
 * screen pass against a server that does not exist.
 */
import type {
  CorrectionCaseV2,
  CorrectionCatalog,
  CorrectionDocument,
  CorrectionFixOptions,
  CorrectionPreview,
  CorrectionPreviewBill,
  CorrectionScopeResolutionV2,
  OneTimeBillAccount,
} from "@/api/billingOpsEndpoints";

export const ACCOUNT_ID = "acc0b0b0-0000-4000-8000-000000000002";
export const BILL_JUL = "b1110000-0000-4000-8000-000000002607";
export const BILL_AUG = "b1110000-0000-4000-8000-000000002608";
export const BILL_SEP = "b1110000-0000-4000-8000-000000002609";
export const BILL_OCT = "b1110000-0000-4000-8000-000000002610";
export const BILL_NOV_DRAFT = "b1110000-0000-4000-8000-000000002611";
export const RUN_ID = "run00000-0000-4000-8000-000000000007";
export const CASE_ID = "ca5e0000-0000-4000-8000-000000000012";
export const PLAN_ID = "p1a00000-0000-4000-8000-00000000000a";
export const PLAN_V4 = "p1a00000-0000-4000-8000-0000000000a4";
export const PLAN_V5 = "p1a00000-0000-4000-8000-0000000000a5";
export const SCHED_ID = "5c4e0000-0000-4000-8000-0000000000b1";
export const METER_ID = "a55e7000-0000-4000-8000-000000010442";

/** Every reason the drawing lists, in the server's classes and precedence. */
export const CATALOG: CorrectionCatalog = {
  reasons: [
    ...[
      "wrong_read",
      "wrong_plan",
      "wrong_rate",
      "wrong_tax",
      "missed_charge",
      "charge_billed_in_error",
      "wrong_discount",
      "wrong_deposit",
      "wrong_period_or_service",
      "theft_restated",
    ].map((code) => ({
      code,
      correction_class: "restatement",
      mechanism_in_words: "issues a corrected bill",
    })),
    {
      code: "goodwill",
      correction_class: "credit_only",
      mechanism_in_words: "issues a goodwill credit",
    },
    ...[
      "customer_name",
      "service_or_mailing_address",
      "premises_or_unit_label",
      "meter_number_or_read_dates",
      "template_or_language",
    ].map((code) => ({
      code,
      correction_class: "document",
      mechanism_in_words: "reprints the document",
    })),
  ],
  classes: [
    { code: "restatement", mechanism_in_words: "issues a corrected bill" },
    { code: "credit_only", mechanism_in_words: "issues a goodwill credit" },
    { code: "document", mechanism_in_words: "reprints the document" },
  ],
  routed_elsewhere: [
    { code: "bill_should_not_exist", detail: "server prose BR-BIL-027" },
    { code: "period_never_billed", detail: "server prose BR-BIL-018" },
    { code: "payment_on_wrong_bill", detail: "server prose BR-PAY-010" },
    { code: "master_data_only", detail: "server prose BR-BIL-049" },
  ],
  scope_kinds: ["account", "run", "price_mistake"],
  approver_role: "Finance manager",
  approval_mode: "second_person",
  approval_mode_unavailable: null,
  backbill_window_months: 12,
  backbill_window_unavailable: null,
  unavailable: [],
};

export const ACCOUNT_ROW = {
  id: ACCOUNT_ID,
  account_no: "AC-2026-00002",
  name: "Ben Bennett",
  premise: "418 Pecan St",
  unit_label: null,
  status_name: "Active",
  status_behavior_class: "billable",
  balance: "465.7700",
  balance_currency: "USD",
  last_bill_at: "2026-10-31",
};

export const ACCOUNT_FACTS: OneTimeBillAccount = {
  id: ACCOUNT_ID,
  account_no: "AC-2026-00002",
  name: "Ben Bennett",
  address: "418 Pecan St",
  plan: "Residential Standard",
  status_name: "Active",
  balance: "465.7700",
  currency: "USD",
  cycle_due_days: 21,
  cycle_name: "Cycle 7 · monthly",
  last_bill_on: "2026-10-31",
  moved_in_on: null,
};

function scopeBill(
  id: string,
  no: string,
  start: string,
  end: string,
  amount: string,
  paid: string,
  status: string,
) {
  return {
    invoice_id: id,
    invoice_no: no,
    account_id: ACCOUNT_ID,
    account_no: "AC-2026-00002",
    customer_name: "Ben Bennett",
    period_start: start,
    period_end: end,
    amount,
    total: amount,
    paid,
    state: status === "paid" ? ("paid" as const) : ("unpaid" as const),
    bill_status: status,
    currency: "USD",
  };
}

/** A1 — the account's whole correctable list, and the draft it leaves out. */
export const ACCOUNT_BILLS: CorrectionScopeResolutionV2 = {
  count: 4,
  results: [
    scopeBill(
      BILL_JUL,
      "BL-2607-000017",
      "2026-07-01",
      "2026-07-31",
      "258.3000",
      "258.3000",
      "paid",
    ),
    scopeBill(
      BILL_AUG,
      "BL-2608-000033",
      "2026-08-01",
      "2026-08-31",
      "268.3200",
      "268.3200",
      "paid",
    ),
    scopeBill(
      BILL_SEP,
      "BL-2609-000041",
      "2026-09-01",
      "2026-09-30",
      "233.0700",
      "0.0000",
      "issued",
    ),
    scopeBill(
      BILL_OCT,
      "BL-2610-000053",
      "2026-10-01",
      "2026-10-31",
      "232.7000",
      "0.0000",
      "issued",
    ),
  ],
  totals: { bills: 4, amount: "992.3900", paid: "526.6200", currency: "USD", accounts: 1 },
  excluded: [
    {
      invoice_id: BILL_NOV_DRAFT,
      invoice_no: null,
      period_start: "2026-11-01",
      period_end: "2026-11-30",
      code: "draft",
    },
  ],
  problems: [],
};

/** A1 — the picked bills' own total, asked of the server (never summed here). */
export function pickedTotals(ids: readonly string[]): CorrectionScopeResolutionV2 {
  const rows = ACCOUNT_BILLS.results.filter((row) => ids.includes(row.invoice_id));
  const amounts: Record<string, [string, string]> = {
    [BILL_OCT]: ["232.7000", "0.0000"],
    [`${BILL_AUG},${BILL_SEP},${BILL_OCT}`]: ["734.0900", "268.3200"],
  };
  const [amount, paid] = amounts[ids.join(",")] ?? ["0.0000", "0.0000"];
  return {
    count: rows.length,
    results: rows,
    totals: { bills: rows.length, amount, paid, currency: "USD", accounts: 1 },
    excluded: [],
    problems: [],
  };
}

/** A1 — a run's bills, paged, with the two left out (image 04). */
export const RUN_BILLS: CorrectionScopeResolutionV2 = {
  count: 48,
  results: [
    {
      ...scopeBill(
        "bb000001-0000-4000-8000-000000000001",
        "BL-2610-000001",
        "2026-10-01",
        "2026-10-31",
        "158.1000",
        "0.0000",
        "issued",
      ),
      account_no: "AC-2026-00001",
      customer_name: "Ana Alvarez",
    },
    {
      ...scopeBill(
        "bb000001-0000-4000-8000-000000000002",
        "BL-2610-000002",
        "2026-10-01",
        "2026-10-31",
        "198.9000",
        "0.0000",
        "issued",
      ),
      account_no: "AC-2026-00002",
      customer_name: "Ben Bennett",
    },
  ],
  totals: { bills: 48, amount: "9312.6000", paid: "4120.0000", currency: "USD", accounts: 48 },
  excluded: [
    {
      invoice_id: "bb000001-0000-4000-8000-000000000098",
      invoice_no: "BL-2610-000098",
      period_start: "2026-10-01",
      period_end: "2026-10-31",
      code: "open_case",
    },
    {
      invoice_id: "bb000001-0000-4000-8000-000000000099",
      invoice_no: "BL-2610-000099",
      period_start: "2026-10-01",
      period_end: "2026-10-31",
      code: "open_case",
    },
    {
      invoice_id: "bb000001-0000-4000-8000-000000000097",
      invoice_no: null,
      period_start: "2026-10-01",
      period_end: "2026-10-31",
      code: "draft",
    },
  ],
  problems: [],
};

export const RUNS = [
  {
    id: RUN_ID,
    run_no: "RUN-2610-07",
    cycle_id: "cyc7",
    cycle_code: "07",
    cycle_name: "Cycle 7",
    period_start: "2026-10-01",
    period_end: "2026-10-31",
    issued_at: "2026-11-01T10:00:00Z",
    accounts: 48,
    bills_issued: 48,
    value: "9312.6000",
    value_currency: "USD",
    held: 0,
    status: "issued",
    bill_type: "cycle",
    created_at: "2026-11-01T09:00:00Z",
  },
];

/** A2 — what the row selects offer, for Ben's account. */
export const OPTIONS: CorrectionFixOptions = {
  plans: [
    {
      id: PLAN_ID,
      name: "Residential Standard",
      versions: [
        { id: PLAN_V4, label: "v4", effective_from: "2026-01-01" },
        { id: PLAN_V5, label: "v5", effective_from: "2026-10-01" },
      ],
    },
  ],
  rate_schedules: [
    {
      id: SCHED_ID,
      name: "Water tiers",
      service_code: "water",
      versions: [{ id: "sv2", label: "v2", effective_from: "2026-08-01" }],
    },
  ],
  taxes: [
    { code: "STATE", name: "State sales tax", rate: "1.000000" },
    { code: "LOCAL", name: "Local utility tax", rate: "2.000000" },
  ],
  charge_codes: [{ code: "MTEST", name: "Meter test", amount: "40.0000" }],
  discounts: [{ id: "disc-senior", name: "Senior", version_label: "v1" }],
  price_targets: [{ kind: "rate", id: "tier-w2", label: "Water tier 2 ($4.50 / kgal)" }],
  meters: [
    {
      asset_id: METER_ID,
      label: "W-10442",
      service_code: "water",
      unit: "kgal",
      billed_reading: "1159.900000",
    },
  ],
  bill_lines: [{ key: "charge.PAPER", label: "Paper bill fee · PAPER" }],
  billed: {
    plan_id: PLAN_ID,
    plan_version_id: PLAN_V4,
    tax_rates: { STATE: "1.000000", LOCAL: "2.000000" },
    deposit: "0.0000",
    fields: {
      customer_name: "Ben Benett",
      service_or_mailing_address: "418 Pecon St, Brazos Bend, TX 77416",
      premises_or_unit_label: "418 Pecan St",
      meter_number_or_read_dates: "W-10442",
      template_or_language: "English",
    },
  },
};

function line(
  key: string,
  label: string,
  qty: string | null,
  unit: string | null,
  unitPrice: string | null,
  amount: string,
  base: string | null = null,
  percent: string | null = null,
) {
  return { key, label, qty, unit, unit_price: unitPrice, base, percent, amount };
}

/** Image 06's old bill — Ben's October, laid out by service and rate type. */
export const DOC_WAS: CorrectionDocument = {
  invoice_no: "BL-2610-000053",
  plan_name: "Residential Standard",
  plan_version: "v4",
  currency: "USD",
  sections: [
    {
      key: "water",
      kind: "service",
      service_code: "water",
      rate_type: "tiered",
      total: "42.7000",
      lines: [
        line("water.base", "Base charge", "1", "month", "8.0000", "8.0000"),
        line("water.tier1", "Tier 1 · 0–5 kgal", "5.0", "kgal", "3.2500", "16.2500"),
        line("water.tier2", "Tier 2 · 5–10 kgal", "4.1", "kgal", "4.5000", "18.4500"),
      ],
    },
    {
      key: "sewer",
      kind: "service",
      service_code: "sewer",
      rate_type: "percent_of",
      total: "13.8800",
      lines: [
        line(
          "sewer.pct",
          "40% of water usage",
          null,
          null,
          null,
          "13.8800",
          "34.7000",
          "40.000000",
        ),
      ],
    },
    {
      key: "charges",
      kind: "charges",
      service_code: null,
      rate_type: null,
      total: "2.5000",
      lines: [line("charge.PAPER", "Paper bill fee · PAPER", "1", null, "2.5000", "2.5000")],
    },
  ],
  subtotal: "227.0100",
  taxes: [
    {
      key: "tax.STATE",
      label: "State sales tax",
      rate: "1.000000",
      base: "227.0100",
      amount: "2.2700",
    },
  ],
  tax_total: "5.6900",
  total: "232.7000",
};

/** Image 06's corrected bill — tier 2 grows, a tier 3 line appears. */
export const DOC_BECOMES: CorrectionDocument = {
  ...DOC_WAS,
  invoice_no: null,
  sections: [
    {
      ...DOC_WAS.sections[0],
      total: "55.9500",
      lines: [
        DOC_WAS.sections[0].lines[0],
        DOC_WAS.sections[0].lines[1],
        line("water.tier2", "Tier 2 · 5–10 kgal", "5.0", "kgal", "4.5000", "22.5000"),
        line("water.tier3", "Tier 3 · 10+ kgal", "1.6", "kgal", "5.7500", "9.2000"),
      ],
    },
    {
      ...DOC_WAS.sections[1],
      total: "19.1800",
      lines: [
        line(
          "sewer.pct",
          "40% of water usage",
          null,
          null,
          null,
          "19.1800",
          "47.9500",
          "40.000000",
        ),
      ],
    },
    DOC_WAS.sections[2],
  ],
  subtotal: "245.5600",
  taxes: [
    {
      key: "tax.STATE",
      label: "State sales tax",
      rate: "1.000000",
      base: "245.5600",
      amount: "2.4600",
    },
  ],
  tax_total: "5.8800",
  total: "251.4400",
};

function previewBill(
  id: string,
  no: string,
  start: string,
  end: string,
  delta: string,
): CorrectionPreviewBill {
  return {
    invoice_id: id,
    invoice_no: no,
    account_id: ACCOUNT_ID,
    account_no: "AC-2026-00002",
    customer_name: "Ben Bennett",
    period_start: start,
    period_end: end,
    was: { ...DOC_WAS, invoice_no: no },
    becomes: DOC_BECOMES,
    credit_note: null,
    was_total: "232.7000",
    becomes_total: "251.4400",
    delta,
    paid: "0.0000",
    moves_to_new_bill: "0.0000",
    still_owed: "251.4400",
    posting_period: "2026-10",
    new_due_date: "2026-11-21",
  };
}

const FINANCE = {
  entries: [
    { entry: "credit_notes" as const, amount: "232.7000" },
    { entry: "new_bills" as const, amount: "251.4400" },
  ],
  net: "18.7400",
  accounts: [
    { code: "4100", name: "Electric revenue", change: "0.0000" },
    { code: "4200", name: "Water revenue", change: "13.2500" },
    { code: "2300", name: "State sales tax payable", change: "0.1900" },
  ],
  closed_through: "2026-08",
  earliest_open: "2026-09",
};

/** Image 06 → 16/17 — one bill, one wrong reading, re-priced. */
export const PREVIEW_ONE: CorrectionPreview = {
  correction_class: "restatement",
  scope_kind: "account",
  currency: "USD",
  count: 1,
  accounts: 1,
  bills: [previewBill(BILL_OCT, "BL-2610-000053", "2026-10-01", "2026-10-31", "18.7400")],
  totals: {
    was: "232.7000",
    becomes: "251.4400",
    net: "18.7400",
    up: { count: 1, amount: "18.7400" },
    down: { count: 0, amount: "0.0000" },
    unchanged: 0,
  },
  customer: {
    name: "Ben Bennett",
    account_no: "AC-2026-00002",
    owes_before: "465.7700",
    owes_after: "484.5100",
    refund: null,
    credit_notes: 1,
    new_bills: 1,
    reprints: 0,
    channels: ["post"],
    new_due_date: "2026-11-21",
  },
  bulk: null,
  finance: FINANCE,
  page_changes: [],
  approver: { role_name: "Finance manager", user_name: "R. Chen" },
  preview_hash: "sha256:one",
  problems: [],
};

/** Image 09 — three months, a reading on all, goodwill on Oct, a reprint. */
export const PREVIEW_SEVERAL: CorrectionPreview = {
  ...PREVIEW_ONE,
  count: 3,
  bills: [
    previewBill(BILL_AUG, "BL-2608-000033", "2026-08-01", "2026-08-31", "-11.3800"),
    previewBill(BILL_SEP, "BL-2609-000041", "2026-09-01", "2026-09-30", "8.1300"),
    previewBill(BILL_OCT, "BL-2610-000053", "2026-10-01", "2026-10-31", "-6.2600"),
  ],
  totals: {
    was: "734.0900",
    becomes: "724.5800",
    net: "-9.5100",
    up: { count: 1, amount: "8.1300" },
    down: { count: 2, amount: "-17.6400" },
    unchanged: 0,
  },
  page_changes: [{ field: "customer_name", was: "Ben Benett", becomes: "Ben Bennett" }],
  preview_hash: "sha256:several",
};

/** Image 11 — goodwill only: the old bill beside the credit note. */
export const PREVIEW_CREDIT: CorrectionPreview = {
  ...PREVIEW_ONE,
  correction_class: "credit_only",
  bills: [
    {
      ...previewBill(BILL_OCT, "BL-2610-000053", "2026-10-01", "2026-10-31", "-25.0000"),
      becomes: null,
      becomes_total: "207.7000",
      credit_note: {
        lines: [{ key: "goodwill", label: "Goodwill credit · BL-2610-000053", amount: "-25.0000" }],
        total: "-25.0000",
      },
    },
  ],
  totals: {
    was: "232.7000",
    becomes: "207.7000",
    net: "-25.0000",
    up: { count: 0, amount: "0.0000" },
    down: { count: 1, amount: "-25.0000" },
    unchanged: 0,
  },
  preview_hash: "sha256:credit",
};

/** Image 12 — address only: reprint, amounts unchanged. */
export const PREVIEW_REPRINT: CorrectionPreview = {
  ...PREVIEW_ONE,
  correction_class: "document",
  bills: [
    {
      ...previewBill(BILL_OCT, "BL-2610-000053", "2026-10-01", "2026-10-31", "0.0000"),
      becomes: { ...DOC_WAS, invoice_no: null },
      becomes_total: "232.7000",
    },
  ],
  totals: {
    was: "232.7000",
    becomes: "232.7000",
    net: "0.0000",
    up: { count: 0, amount: "0.0000" },
    down: { count: 0, amount: "0.0000" },
    unchanged: 1,
  },
  page_changes: [
    {
      field: "service_or_mailing_address",
      was: "418 Pecon St, Brazos Bend, TX 77416",
      becomes: "418 Pecan St, Brazos Bend, TX 77461",
    },
  ],
  preview_hash: "sha256:reprint",
};

/** Image 14 → 18 — a run re-priced: going up and going down kept apart. */
export const PREVIEW_BULK: CorrectionPreview = {
  correction_class: "restatement",
  scope_kind: "run",
  currency: "USD",
  count: 48,
  accounts: 48,
  bills: [
    {
      ...previewBill(
        "bb000001-0000-4000-8000-000000000001",
        "BL-2610-000001",
        "2026-10-01",
        "2026-10-31",
        "13.1300",
      ),
      account_no: "AC-2026-00001",
      customer_name: "Ana Alvarez",
      was: null,
      becomes: null,
      was_total: "158.1000",
      becomes_total: "171.2300",
    },
    {
      ...previewBill(
        "bb000001-0000-4000-8000-000000000006",
        "BL-2610-000006",
        "2026-10-01",
        "2026-10-31",
        "0.0000",
      ),
      account_no: "AC-2026-00006",
      customer_name: "Farid Fontaine",
      was: null,
      becomes: null,
      was_total: "61.0000",
      becomes_total: "61.0000",
    },
  ],
  totals: {
    was: "9312.6000",
    becomes: "9724.9600",
    net: "412.3600",
    up: { count: 44, amount: "412.3600" },
    down: { count: 0, amount: "0.0000" },
    unchanged: 4,
  },
  customer: null,
  bulk: {
    credit_notes: 44,
    new_bills: 44,
    reprints: 0,
    refunds: null,
    payments_moved: "2014.6000",
    channels: ["post"],
  },
  finance: { ...FINANCE, net: "412.3600" },
  page_changes: [],
  approver: { role_name: "Finance manager", user_name: "R. Chen" },
  preview_hash: "sha256:bulk",
  problems: [],
};

const CASE_BASE = {
  id: CASE_ID,
  case_no: "CC-2026-012",
  correction_class: "restatement",
  reason_codes: ["wrong_read"],
  scope_kind: "account",
  scope: {},
  bills: 1,
  net_delta: "18.7400",
  currency: "USD",
  posting_period: "2026-10",
  preview_hash: "sha256:one",
  initiated_by: "u-dana",
  approved_by: null,
  approved_on: null,
  executed_on: null,
  closed_reason: null,
  created_at: "2026-10-12T10:00:00Z",
  no_rollback: "",
  unavailable: [],
  items: [{ reason: "wrong_read", item: METER_ID, value: "1162.4", bill_ids: null }],
  preview: PREVIEW_ONE,
};

/** A4 — the case at Send, seen by the clerk who sent it. */
export const CASE_PENDING_CLERK: CorrectionCaseV2 = {
  ...CASE_BASE,
  status: "pending_approval",
  bills_detail: [],
  approval: {
    role_name: "Finance manager",
    approver_name: "R. Chen",
    initiated_by_name: "Dana Whitfield",
    sent_on: "2026-10-12",
    approved_by_name: null,
  },
  viewer_can_approve: false,
};

/** A4 — the same case, opened by the approver. */
export const CASE_PENDING_APPROVER: CorrectionCaseV2 = {
  ...CASE_PENDING_CLERK,
  viewer_can_approve: true,
};

/** A5 — after Approve and issue: the numbers, never the ids. */
export const CASE_DONE: CorrectionCaseV2 = {
  ...CASE_PENDING_APPROVER,
  status: "done",
  approved_by: "u-chen",
  approved_on: "2026-10-12",
  executed_on: "2026-10-12",
  bills_detail: [
    {
      invoice_id: BILL_OCT,
      invoice_no: "BL-2610-000053",
      account_id: ACCOUNT_ID,
      delta_amount: "18.7400",
      currency: "USD",
      direction: "up",
      status: "done",
      failure_reason: null,
      warnings: [],
      impact: {},
      credit_note_id: "cn000000-0000-4000-8000-000000000041",
      credit_note_no: "CN-2610-0041",
      rebill_invoice_id: "b1110000-0000-4000-8000-000000000118",
      rebill_invoice_no: "BL-2610-00118",
      document_instance_id: null,
    },
  ],
  result: {
    case_id: CASE_ID,
    status: "done",
    succeeded: [BILL_OCT],
    failed: [],
    skipped_already_done: [],
    summary: "1 bill corrected",
  },
};

/** A5 — bulk done, with a failure and an already-done kept apart. */
export const CASE_DONE_BULK: CorrectionCaseV2 = {
  ...CASE_DONE,
  scope_kind: "run",
  bills: 48,
  net_delta: "412.3600",
  preview: PREVIEW_BULK,
  bills_detail: [],
  result: {
    case_id: CASE_ID,
    status: "done",
    succeeded: Array.from({ length: 42 }, (_, n) => `ok-${n}`),
    failed: [{ invoice_id: "bad-1", reason: "x" }],
    skipped_already_done: ["skip-1"],
    summary: "",
  },
};
