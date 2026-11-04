// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 · US-RBS-003 — CR-075 wave D tasks D3 and D4.
// Screens: RBS-002.1 · RBS-002.2 · RBS-003.1 · RBS-003.2 · RBS-003.3.
// Rules:   `BR-RBS-025` · `TC-RBS-20` · `BR-RBS-002`.
// ───────────────────────────────────────────────────────
// THE TWELVE-TEMPLATE LIBRARY `TC-RBS-20` IS WRITTEN AGAINST.
//
// `EP-RBS-01` §3: *"The library with the twelve shipped templates → exactly
// **eight** chips; **none reads Assets or Work**"*, and the sheet's own toolbar
// gives the eight with their counts — *Billing 4 · Collections 2 · Accounts 1 ·
// Data Sync 1 · Finance 1 · Onboarding & Cutover 1 · Payments 1 · Reads 1* — which
// is twelve templates across eight of the sixteen categories.
//
// ⚠ **THE SHIPPED REGISTRY HOLDS ONE RUNBOOK TODAY, NOT TWELVE.**
// `apps/runbooks/definitions/__init__.py` registers `configuration_check` and
// nothing else, so the LIVE screen draws one card and one category chip. That
// is why `TC-RBS-20`'s case is a fixture rather than a browser assertion: the
// case the rule is about — a library big enough for eight chips out of sixteen
// categories — does not exist yet on any database, and waiting for it would mean
// the rule ships untested until phase 5. The browser walkthrough asserts what is
// actually there and prints the number, which is the other half.
//
// ⚠ **AND THE CHIPS HERE ARE THE SERVER'S, NOT DERIVED FROM `ROWS`.** They are
// written out separately and deliberately: a fixture that computed them from its
// own rows could not tell a screen reading `category_chips` from a screen
// counting the page, which is the exact confusion `TC-RBS-20` exists to catch.
// `TWO_PAGE_CHIPS` below is the same eight over a SHORT row list, so a screen
// that counts rows draws two chips where the rule wants eight.
import type { CatalogueRow, CategoryChip, KindChip, TemplateRow } from "./libraryTypes";

function template(
  key: string,
  name: string,
  kind: TemplateRow["kind"],
  category: string,
  state: TemplateRow["state"],
  extra: Partial<TemplateRow> = {},
): TemplateRow {
  return {
    template_key: key,
    name,
    kind,
    category,
    tags: [],
    subject_type: kind === "check" ? "tenant" : "account",
    unit_of_work: kind === "check" ? "config graph" : "account",
    triggers: ["manual"],
    steps: 3,
    ports: kind === "check" ? [] : ["queue_notice"],
    writes_nothing: kind === "check",
    state,
    unavailable_reason: null,
    ...extra,
  };
}

/** Twelve templates over eight categories — `TC-RBS-20`'s own library. */
export const TWELVE_TEMPLATES: TemplateRow[] = [
  template("configuration_check", "Can we bill?", "check", "billing", "added"),
  template("test_bill", "Test bill", "check", "billing", "added"),
  template("coverage_grid", "Coverage grid", "check", "billing", "not_added"),
  template("pre_bill_sweep", "Pre-bill sweep", "check", "billing", "added"),
  template("collections_ladder", "Collections ladder", "action", "collections", "added"),
  template("disconnect_eligibility", "Disconnect eligibility", "check", "collections", "not_added"),
  template("move_outs", "Move-outs", "action", "accounts", "not_added"),
  template("gis_reconciliation", "GIS reconciliation", "action", "data_sync", "not_added"),
  template("month_end", "Books tie-out", "check", "finance", "added"),
  template("cutover_readiness", "Ready for cutover?", "check", "onboarding_cutover", "added"),
  template("cash_application", "Cash application", "action", "payments", "added"),
  template("read_validation", "Read validation", "action", "reads", "not_added"),
];

/** The EIGHT chips the server counts for that library, in `models.CATEGORIES`
 *  order — which is the order `selectors._template_category_chips` returns and
 *  therefore the order the row must draw. **Assets and Work are absent, and that
 *  absence is the rule** (`BR-RBS-025`). */
export const EIGHT_CHIPS: CategoryChip[] = [
  { category: "onboarding_cutover", count: 1 },
  { category: "accounts", count: 1 },
  { category: "reads", count: 1 },
  { category: "billing", count: 4 },
  { category: "collections", count: 2 },
  { category: "payments", count: 1 },
  { category: "finance", count: 1 },
  { category: "data_sync", count: 1 },
];

/** `All 12 · Checks 7 · Actions 5` — the server's own counts over the twelve. */
export const KIND_CHIPS: KindChip[] = [
  { kind: "all", count: 12 },
  { kind: "check", count: 7 },
  { kind: "action", count: 5 },
];

/** A template with nothing shipped for it — the `unavailable` card the sheet
 *  draws (*Budget billing is switched off for you*). Nothing serves this state
 *  today; the fixture is what proves the branch draws its reason rather than a
 *  bare grey button. */
export const UNAVAILABLE_TEMPLATE = template(
  "budget_billing_relevel",
  "Budget billing re-level",
  "action",
  "billing",
  "unavailable",
  { unavailable_reason: "Budget billing is switched off for you." },
);

/** One configured runbook — `RBS-003`'s first row, with a finished run. */
export function catalogueRow(
  key: string,
  name: string,
  extra: Partial<CatalogueRow> = {},
): CatalogueRow {
  return {
    key,
    name,
    kind: "check",
    category: "billing",
    tags: [],
    origin: "shipped",
    enabled: true,
    trigger_kind: "manual",
    cap: null,
    current_version: 1,
    writes_nothing: true,
    last_run: null,
    open_items: 0,
    ...extra,
  };
}

/** The three rows `RBS-003.1` needs to show every state it draws: a finished
 *  Check with open items, an Action waiting for a person, and a paused one. */
export const THREE_RUNBOOKS: CatalogueRow[] = [
  catalogueRow("configuration_check", "Can we bill?", {
    open_items: 3,
    last_run: {
      id: "0192f3aa-0000-7000-8000-000000000001",
      status: "done",
      mode: "dry",
      trigger: "manual",
      started_at: null,
      finished_at: "2026-09-06T08:12:00Z",
      took_seconds: 41.2,
      counts: { checked: 1004 },
    },
  }),
  catalogueRow("collections_ladder", "Collections ladder", {
    kind: "action",
    category: "collections",
    trigger_kind: "schedule",
    writes_nothing: false,
    open_items: 6,
    last_run: {
      id: "0192f3aa-0000-7000-8000-000000000002",
      status: "awaiting_approval",
      mode: "dry",
      trigger: "schedule",
      started_at: null,
      finished_at: null,
      took_seconds: null,
      counts: { planned: 812 },
    },
  }),
  catalogueRow("returned_payments", "Returned payments", {
    kind: "action",
    category: "payments",
    enabled: false,
    trigger_kind: "schedule",
    writes_nothing: false,
  }),
];

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 · US-RBS-003 (CR-075 wave D tasks D3/D4) · TC-RBS-20 · EP-RBS-01 §3 · wireframes/RBS-002.1 and RBS-003.1
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest
// exceptions: the twelve templates are a FIXTURE because the shipped registry holds one; the reason is in the header
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
