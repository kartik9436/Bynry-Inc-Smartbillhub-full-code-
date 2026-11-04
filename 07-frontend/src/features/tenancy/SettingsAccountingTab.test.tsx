// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-009 (EP-BIL-02 — the account-mapping page) · US-TEN-007 (the service rows it maps)
//           Screens: S8 (Settings → Accounting) · S56 (the mapping panel's read-only twin on Finance)
//           AMENDED 2026-08-16 (CR-004 task C): S71 Finance controls, moved here from Settings → Configure
//           → Reference data on the PO's ruling *"this is moved to accounting tab"*
// Rules:    BR-BIL-067 (the seeded service→revenue account is a DEFAULT the tenant may override) ·
//           BR-BIL-069 (a tax line names its AUTHORITY and each authority has its OWN liability account,
//           tenant-managed) · BR-BIL-010 (mapping stamps per line at issue; edits never re-map history) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason) · BR-SHL-020 (plain-language
//           failure) · BR-TEN-016 (every mapping change is audited server-side)
// ───────────────────────────────────────────────────────
// §4 test data: Silver Creek Water — the tenant BR-BIL-067 works its example on.
// Water sells water + sewer, so it is provisioned 4110 · 4115 · 4120 and NOT
// 4100/4105/4130/4140/4145/4150. Taxes are the $117.01 bill's three authorities:
// State of Texas 6.25 %, Harris County 1.00 %, City of Katy 1.00 %.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import { updateTenantService } from "@/api/endpoints";
import { updateTaxGlAccount } from "@/api/taxGlAccountEndpoints";
import type {
  GlAccountRef,
  LedgerChartResponse,
  RuleDocument,
  TaxRow,
  TenantServiceRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { chartQueryKey } from "@/features/ledger/ChartOfAccountsPanel";
// CR-013 P4 — the one shared `TaxRow` default, so this file stops carrying its
// own copy of a contract declared in `endpoints.ts` (see `taxRowFixture.ts`).
import { taxRowDefaults } from "@/features/rating/taxRowFixture";

import { referenceCard } from "./referenceDataConfig";
import { FINANCE_CONTROLS_PAGE } from "./settingsRulePages";
import {
  AccountingTab,
  accountingSubTabFromParam,
  accountPickerOptions,
  PAYMENT_DESIGNATIONS,
  reasonGlAccountId,
  tenderClearingAccountId,
  chartRouteAbsent,
  resolveAccount,
  serviceGlChanges,
  taxAuthorityRows,
  taxGlChanges,
} from "./SettingsAccountingTab";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const WATER_USAGE: GlAccountRef = { id: "acc-4110", code: "4110", name: "Water usage revenue" };
const WATER_BASE: GlAccountRef = { id: "acc-4115", code: "4115", name: "Water base revenue" };
const SEWER: GlAccountRef = { id: "acc-4120", code: "4120", name: "Sewer revenue" };

const SERVICES: TenantServiceRow[] = [
  {
    service: "water",
    name: "Water",
    enabled: true,
    primary_uom: "kgal",
    alt_uom: "ccf",
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: WATER_USAGE,
    base_revenue_account: WATER_BASE,
    rate_schedules: 2,
    active_accounts: 568,
  },
  {
    service: "sewer",
    name: "Sewer",
    enabled: true,
    primary_uom: "kgal",
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: SEWER,
    // BR-BIL-010's gap: a service with no base account cannot stamp a base line.
    base_revenue_account: null,
    rate_schedules: 1,
    active_accounts: 540,
  },
  {
    service: "gas",
    name: "Gas",
    enabled: false,
    primary_uom: null,
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 0,
    active_accounts: 0,
  },
];

function tax(id: string, name: string, authority: string | null, gl: string | null): TaxRow {
  return {
    ...taxRowDefaults(),
    id,
    name,
    jurisdiction:
      authority === null
        ? null
        : { id: `${id}-j`, name: authority, authority, level: null, reference_no: null },
    kind: "percent",
    rate: "0.0625",
    rate_display: "6.25%",
    base_includes_usage: true,
    base_includes_base: true,
    flat_amount: null,
    flat_frequency: null,
    per_unit_amount: null,
    per_unit_uom: null,
    // BR-RAT-036 as amended (DEF-386) — the fourth computation form.
    per_meter_amount: null,
    per_meter_amount_display: null,
    applies_above_units: null,
    applies_to_services: [],
    // DEF-273 / DEF-292 — the two qualifiers TAX-02 now sets. Empty here:
    // this suite is about the GL mapping, and "every class, everywhere" is
    // the honest default for a fixture that says nothing about scope.
    applies_to_customer_classes: [],
    premises_scope_kind: null,
    premises_scope_value: null,
    liability_gl_account_id: gl,
    remit_to: null,
    filing_frequency: "monthly",
    filing_form: null,
    effective_from: null,
    effective_to: null,
    status: "active",
    used_by_plans: 1,
  };
}

const TAXES: TaxRow[] = [
  tax("t-tx", "State sales tax", "State of Texas", "acc-2200"),
  tax("t-harris", "County sales tax", "Harris County", null),
  tax("t-katy", "City sales tax", "City of Katy", null),
];

// CR-004 task C: the S71 document this tab now renders as its third section.
// Decimals are the SERVER's own canonical strings, never numbers — the same law
// the rule page has always been held to.
const FINANCE_CONTROLS: RuleDocument = {
  bank_match_date_tolerance_days: 3,
  write_off_threshold_amount: "10",
  dso_target_days: 45,
  correction_approval_mode: "all",
  back_bill_cap_months: 12,
  back_bill_theft_exempt: true,
  tax_remitting_basis_by_authority: {},
};

/**
 * ⚠ **`sub` DEFAULTS TO `"mapping"` HERE AND TO `"chart"` IN THE PRODUCT, and
 * that is deliberate rather than a discrepancy** (CR-008, 2026-08-17). This
 * file's forty assertions are about the GL MAP, which is now the second of
 * three sub-tabs; defaulting the helper to it keeps every one of them testing
 * the thing it was written for. The tabs themselves — including which one
 * opens by default — are asserted separately, below.
 */
function renderTab(
  rows: TenantServiceRow[],
  taxes: TaxRow[],
  options: {
    readOnly?: boolean;
    chart?: GlAccountRef[];
    /** The chart panel's OWN read (`GET /ledger/accounts`, unfiltered). Without
     *  it the panel draws its loading skeleton and none of its controls. */
    coaChart?: LedgerChartResponse;
    financeControls?: RuleDocument;
    sub?: string;
    charges?: unknown[];
    discounts?: unknown[];
    reasons?: unknown[];
    tenders?: unknown[];
    designations?: unknown[];
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.tenantServices, rows);
  queryClient.setQueryData(queryKeys.taxes("gl-mapping"), taxes);
  if (options.chart !== undefined) {
    queryClient.setQueryData(queryKeys.ledgerAccounts, options.chart);
  }
  if (options.coaChart !== undefined) {
    queryClient.setQueryData(chartQueryKey("||||"), options.coaChart);
  }
  if (options.financeControls !== undefined) {
    queryClient.setQueryData(
      queryKeys.rulePage(FINANCE_CONTROLS_PAGE.slug),
      options.financeControls,
    );
  }
  queryClient.setQueryData(["charges", "gl-mapping"], options.charges ?? []);
  queryClient.setQueryData(["lookups", "reason_codes", "gl-mapping"], options.reasons ?? []);
  queryClient.setQueryData(["discounts", "gl-mapping"], options.discounts ?? []);
  queryClient.setQueryData(["lookups", "payment_methods", "gl-mapping"], options.tenders ?? []);
  queryClient.setQueryData(["ledger", "gl-mappings"], {
    designations: options.designations ?? [],
    services: { available: true, rows: [], write_route: "" },
    tax_authorities: { series: "2200", rows: [] },
    export_codes: { rows: [], missing: {} },
    unavailable: [],
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <AccountingTab readOnly={options.readOnly ?? false} sub={options.sub ?? "mapping"} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("kept from the seven-table map — the owners' writes and the column readers", () => {
  it("US-BIL-009 TC-2: the tax re-point REACHES the server — PATCH /taxes/{id}/gl-account (PO 2026-10-03 on CR-008)", async () => {
    expect(taxGlChanges("acc-2200")).toEqual({ liability_gl_account_id: "acc-2200" });
    expect(taxGlChanges(null)).toEqual({ liability_gl_account_id: null });

    const calls: { url: string; method: string | undefined; body: unknown }[] = [];
    const client = createApiClient({
      tenant: "silvercreekwater",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({
          url: String(input),
          method: init?.method,
          body: init?.body === undefined ? null : JSON.parse(String(init.body)),
        });
        return new Response(JSON.stringify({ ...TAXES[1], liability_gl_account_id: "acc-2201" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
      sleep: async () => undefined,
    });

    const saved = await updateTaxGlAccount("t-harris", taxGlChanges("acc-2201"), client);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/silvercreekwater/taxes/t-harris/gl-account");
    expect(calls[0].method).toBe("PATCH");
    expect(calls[0].body).toEqual({ liability_gl_account_id: "acc-2201" });
    expect(saved.liability_gl_account_id).toBe("acc-2201");
  });

  it("`tenderClearingAccountId` reads the column, and an empty string is UNMAPPED not a pointer", () => {
    expect(tenderClearingAccountId(TENDERS[0] as never)).toBe("acc-1015");
    expect(tenderClearingAccountId(TENDERS[1] as never)).toBeNull();
    expect(tenderClearingAccountId({ ...TENDERS[1], clearing_gl_account_id: "" } as never)).toBeNull();
  });

  it("the two lookup columns are DIFFERENT names — one is cash, the other revenue", () => {
    expect(tenderClearingAccountId({ default_gl_account_id: "acc-4110" } as never)).toBeNull();
    expect(reasonGlAccountId({ clearing_gl_account_id: "acc-1015" } as never)).toBeNull();
  });
});

// ⚠ **RETIRED 2026-10-29 (`CR-197-BRC10`) — TWENTY-SIX CASES THAT DESCRIBED THE
// SEVEN-TABLE GL MAP.** The PO ruled the mapping sub-tab ONE list (*"we neeed to
// create one single tabl on list view"*, decision log 2026-10-29), so the
// service, tax, payments, tender, charge, reason and discount sections those
// cases rendered no longer exist. Their claims moved, not vanished: every row
// type, its account, its gap and its read-only reason are asserted on the new
// list in `src/features/ledger/glMappingList.dom.test.tsx`, and the server's
// rows in `06-backend/tests/test_cr197_gl_mapping_list.py`.
describe("US-BIL-009 TC-2 — a re-point reaches the server on the payload it already accepts", () => {
  it("BR-BIL-067: `serviceGlChanges` builds exactly the two fields PUT /settings/services/<code> takes", () => {
    expect(serviceGlChanges({ revenue_account: "acc-4101", base_revenue_account: "acc-4115" })).toEqual(
      { revenue_account: "acc-4101", base_revenue_account: "acc-4115" },
    );
    // `null` CLEARS a mapping — a real thing a tenant may want (an account
    // retired, a chart restructured), and NOT the same as omitting the field.
    expect(serviceGlChanges({ revenue_account: null, base_revenue_account: null })).toEqual({
      revenue_account: null,
      base_revenue_account: null,
    });
  });

  it("US-BIL-009 TC-2: the re-point REACHES the server — PUT /settings/services/water with the account id", async () => {
    const calls: { url: string; body: unknown }[] = [];
    const client = createApiClient({
      tenant: "silvercreekwater",
      fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({
          url: String(input),
          body: init?.body === undefined ? null : JSON.parse(String(init.body)),
        });
        return new Response(
          JSON.stringify({ ...SERVICES[0], revenue_account: WATER_BASE, warnings: {} }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
      sleep: async () => undefined,
    });

    const saved = await updateTenantService(
      "water",
      serviceGlChanges({ revenue_account: "acc-4115", base_revenue_account: "acc-4115" }),
      client,
    );

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/silvercreekwater/settings/services/water");
    expect(calls[0].body).toEqual({
      revenue_account: "acc-4115",
      base_revenue_account: "acc-4115",
    });
    // (c) THE READ TRAVELS WITH THE WRITE — the response shows what it saved.
    expect(saved.revenue_account?.code).toBe("4115");
  });

  it("BR-SHL-025: a read-only role gets the change control disabled WITH its reason", () => {
    const html = renderTab(SERVICES, TAXES, { readOnly: true, chart: [WATER_USAGE, WATER_BASE] });
    expect(html).toContain(t("settings.readOnlyReason"));
    expect(html).toContain("disabled");
  });

  it("BR-BIL-010: the mapping states BEFORE the save that issued history keeps its stamps", () => {
    expect(t("settings.accounting.edit.note")).toContain("already issued");
  });
});

describe("the chart of accounts is DERIVED as absent from the response — never a build flag", () => {
  it("BR-SHL-020: a 404 on the collection route means 'no such resource', any other failure does not", () => {
    const notFound = new ApiError(404, { code: "NOT-FOUND", message_key: "api.error.notFound" });
    const serverError = new ApiError(500, { code: "ERR", message_key: "api.error.unexpected" });
    expect(chartRouteAbsent(notFound)).toBe(true);
    expect(chartRouteAbsent(serverError)).toBe(false);
    expect(chartRouteAbsent(new Error("offline"))).toBe(false);
  });

  it("the picker falls back to the accounts the SERVED rows already reference, and says the list is partial", () => {
    // No chart: the only accounts this tenant is KNOWN to own are the ones its
    // own service rows point at. That is a partial list and it says so.
    const partial = accountPickerOptions(SERVICES, undefined);
    expect(partial.complete).toBe(false);
    expect(partial.accounts.map((account) => account.code)).toEqual(["4110", "4115", "4120"]);

    // Chart served: the full chart wins and the partial notice disappears.
    const chart: GlAccountRef[] = [
      { id: "acc-1200", code: "1200", name: "Accounts receivable" },
      WATER_USAGE,
    ];
    const full = accountPickerOptions(SERVICES, chart);
    expect(full.complete).toBe(true);
    expect(full.accounts.map((account) => account.code)).toEqual(["1200", "4110"]);
  });

  it("DEF-050: no message on this screen names a hostname or an environment domain", () => {
    for (const key of [
      "settings.accounting.chart.absent",
      "settings.accounting.chart.partial",
      "settings.accounting.taxes.needsChart",
      "settings.accounting.noAccountsToPick",
      "settings.accounting.mappedUnresolved",
    ]) {
      expect(t(key)).not.toMatch(/https?:|www\.|\.com|\.io|\.net|localhost/);
    }
  });
});

describe("CR-004 task C — S71 Finance controls is a SECTION of this tab now", () => {
  it("the Finance-controls fields render inside the Accounting tab, under their own section heading", () => {
    const html = renderTab(SERVICES, TAXES, {
      financeControls: FINANCE_CONTROLS,
      sub: "controls",
    });

    // ⚠ CR-008 (2026-08-17): the two mapping sections are no longer ON this
    // screen — they are the GL-mapping SUB-TAB, and finance controls is its
    // own. Asserting their absence here is the point: it is what proves the
    // rule page renders on the tab a person actually opens for it.
    expect(html).not.toContain(t("settings.accounting.services.title"));

    // …and the moved page is headed like its siblings
    // and carrying the sample line the card used to show above it.
    expect(html).toContain("settings-frame-title");
    expect(html).toContain(t("settings.reference.card.finance_controls"));
    expect(html).toContain(t("settings.reference.sample.finance_controls"));

    // EVERY parameter of the page renders — this is the assertion that would go
    // red if the move had quietly dropped a field on the way across.
    for (const param of FINANCE_CONTROLS_PAGE.params) {
      expect(html).toContain(t(`settings.rules.finance_controls.${param.key}`));
    }
    // Real inputs and a real save, not a read-only echo of a page elsewhere.
    expect(html).toContain("<input");
    expect(html).toContain(t("settings.rules.save"));
    // BR-TEN-043 travels with the page: a new value governs what happens next.
    expect(html).toContain("New values apply from now on");
    // The server's stored values are what is shown — nothing is defaulted here.
    expect(html).toContain('value="45"');
    expect(html).toContain('value="3"');
  });

  it("the move changed the ENTRY POINT and nothing else — no field law was copied here", () => {
    // The card is gone from the Reference-data registry (PO 2026-08-16: "this
    // is moved to accounting tab")…
    expect(referenceCard("finance_controls")).toBeNull();
    // …while settingsRulePages.ts is still the ONE source of the field law, and
    // this tab renders that same row rather than a second copy of it.
    expect(FINANCE_CONTROLS_PAGE.card).toBe("finance_controls");
    expect(FINANCE_CONTROLS_PAGE.slug).toBe("finance-controls");
    expect(FINANCE_CONTROLS_PAGE.screen).toBe("S71");
    // The parameter labels this tab prints are the rule page's own keys, so a
    // field added to the registry appears here with nothing edited in this file.
    const html = renderTab(SERVICES, TAXES, {
      financeControls: FINANCE_CONTROLS,
      sub: "controls",
    });
    expect(html).toContain(t("settings.rules.finance_controls.tax_remitting_basis_by_authority"));
  });

  it("DEF-TEN-6935: no rule id reaches the screen, on any field of any rule page", () => {
    // ⚠ **THE ASSERTION IS THE INVERSE OF THE ONE THAT USED TO BE HERE.** This
    // case read `expect(html).toContain(t("settings.rules.ruleNote", { br:
    // "BR-LED-002" }))` — it asserted the defect. B14 rule 32 clause 4 bans a
    // rule id in clerk-facing copy and rule 33 puts the rationale it was
    // answering at zero words on screen, so the line is gone with nothing in
    // its place.
    //
    // It is matched by SHAPE rather than by the one id, because the id is
    // interpolated from `param.br`: a grep of the catalogues cannot see it —
    // `en.json` holds only `Set by {{br}}` — and an assertion naming
    // `BR-LED-002` would pass the day somebody re-introduces the line on a page
    // whose parameters carry a different rule.
    const html = renderTab(SERVICES, TAXES, {
      financeControls: FINANCE_CONTROLS,
      sub: "controls",
    });
    expect(html).not.toMatch(/BR-[A-Z]{3}-\d{3,5}/);
  });

  it("BR-SHL-025: a read-only role gets the rule page's save disabled WITH its reason too", () => {
    const html = renderTab(SERVICES, TAXES, {
      readOnly: true,
      financeControls: FINANCE_CONTROLS,
      sub: "controls",
    });
    // One reason, stated on every control this role cannot use — the GL change
    // buttons above and the moved page's save bar alike.
    expect(html).toContain(t("settings.readOnlyReason"));
    expect(html).toContain(t("settings.rules.save"));
    expect(html).toContain("disabled");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-008 · SET-11 — the three sub-tabs, the five mapping sections, and the
// six things the PO ruled OUT on 2026-08-17
// ══════════════════════════════════════════════════════════════════════════

const CHARGES = [
  {
    id: "c-late",
    code: "LATE",
    name: "Late fee",
    charge_type: "fee",
    service: null,
    amount_rule: "flat",
    amount: "8.00",
    percent: null,
    min_amount: null,
    max_amount: null,
    gl_account_id: "acc-4110",
    taxable_default: false,
    auto_apply: true,
    waivable: true,
    separate_line: true,
    status: "active",
    used_by_plans: 1,
    used_by_invoice_lines: 0,
  },
  {
    id: "c-ahc",
    code: "AHC",
    name: "After-hours service call",
    charge_type: "fee",
    service: null,
    amount_rule: "flat",
    amount: "75.00",
    percent: null,
    min_amount: null,
    max_amount: null,
    // r10's own GAP example, and BR-BIL-010's blocking condition.
    gl_account_id: null,
    taxable_default: false,
    auto_apply: false,
    waivable: false,
    separate_line: true,
    status: "active",
    used_by_plans: 0,
    used_by_invoice_lines: 0,
  },
];

const REASONS = [
  { id: "r-err", code: "BILLERR", name: "Billing error", active: true, is_system: true, used_by: 3, default_gl_account_id: "acc-4110" },
  { id: "r-good", code: "GOODWILL", name: "Goodwill", active: true, is_system: false, used_by: 1, default_gl_account_id: null },
];

// CR-066 table 3 — two discounts, one pointed at the contra-revenue account
// the PO approved and one nobody has overridden. The second is NOT a gap: a
// discount line already resolves `4760` by DESIGNATION at issue, so a blank
// cell here means "the product's own answer stands", which is why this section
// carries no warning banner where the Charges section does.
const DISCOUNTS = [
  { id: "d-senior", code: "SENIOR", name: "Senior discount", gl_account_id: "acc-4110" },
  { id: "d-cap", code: "CAP", name: "Low-income assistance", gl_account_id: null },
];

// CR-008 second-set ruling 1 — the four tenders r10's section 3 draws, as the
// flat-lookup rows they actually are. Card is MAPPED to a merchant clearing
// account; the other three are unmapped, which is today's behaviour for every
// tender in the product.
const TENDERS = [
  { id: "pm-card", code: "CARD", name: "Card — Stripe", active: true, is_system: true, used_by: 0, clearing_gl_account_id: "acc-1015" },
  { id: "pm-check", code: "CHECK", name: "Check — lockbox", active: true, is_system: true, used_by: 0, clearing_gl_account_id: null },
  { id: "pm-cash", code: "CASH", name: "Cash — counter", active: true, is_system: true, used_by: 0, clearing_gl_account_id: null },
  // Deactivated: no money lands anywhere, so it must not be offered an account.
  { id: "pm-ivr", code: "IVR", name: "IVR — phone", active: false, is_system: true, used_by: 0, clearing_gl_account_id: null },
];

const MERCHANT_CLEARING: GlAccountRef = {
  id: "acc-1015",
  code: "1015",
  name: "Merchant clearing — Stripe",
};

const DESIGNATIONS = [
  { designation: "cash", account_id: "acc-1000", code: "1000", name: "Operating bank", type: "asset", awaiting_finance_re_sign: false },
  { designation: "undeposited_funds", account_id: "acc-1050", code: "1050", name: "Undeposited funds", type: "asset", awaiting_finance_re_sign: false },
  { designation: "customer_credit_balance", account_id: null, code: null, name: null, type: null, awaiting_finance_re_sign: false },
  { designation: "deposit_liability", account_id: "acc-2300", code: "2300", name: "Customer deposits", type: "liability", awaiting_finance_re_sign: false },
  // Not a payments designation — it must NOT appear in section 3.
  { designation: "write_off", account_id: "acc-6900", code: "6900", name: "Bad debt", type: "expense", awaiting_finance_re_sign: false },
];

describe("CR-008 — SET-11 is three sub-tabs, and the chart is the one that opens", () => {
  it("all three sub-tab labels render, and `chart` is what an undefined segment resolves to", () => {
    expect(accountingSubTabFromParam(undefined)).toBe("chart");
    expect(accountingSubTabFromParam("mapping")).toBe("mapping");
    expect(accountingSubTabFromParam("controls")).toBe("controls");
    // A segment nobody defined is the DEFAULT, never a blank screen: a stale
    // bookmark must land somewhere real (the CONFIGURE_SUB_TABS precedent).
    expect(accountingSubTabFromParam("quickbooks")).toBe("chart");

    const html = renderTab(SERVICES, TAXES, { sub: "chart" });
    expect(html).toContain(t("settings.accounting.sub.chart"));
    expect(html).toContain(t("settings.accounting.sub.mapping"));
    expect(html).toContain(t("settings.accounting.sub.controls"));
    expect(html).toContain('role="tablist"');
  });

  it("the chart sub-tab draws the chart panel AND the import control", () => {
    const html = renderTab(SERVICES, TAXES, {
      sub: "chart",
      coaChart: {
        rows: [],
        types: [],
        categories: [],
        designations: [],
        roles_needing_account: [],
        pending_finance_re_sign: [],
        pending_finance_re_sign_cost: [],
        pending_finance_re_sign_books: [],
        cost_section_source: "",
        utility_books_source: "",
        currency: "USD",
      },
    });
    expect(html).toContain(t("settings.accounting.chart.title"));
    expect(html).toContain(t("settings.accounting.import.open"));
    // The panel itself is the ledger component, not a second chart screen —
    // its own add control is the evidence it is really mounted.
    //
    // ⚠ **THIS ASSERTED THE INLINE FORM'S TITLE (*"Add an account"*) UNTIL
    // 2026-10-02, AND WAS RED FROM 2026-09-22 (`294aa3954`, `DEF-LED-6140`).**
    // That fix made add and edit DIALOGS that open on a click, so the form's
    // title is no longer in the page until somebody presses *+ Add account*.
    // The button is the panel's own and is asserted instead, with a chart
    // seeded so the panel draws its table rather than its loading state.
    expect(html).toContain(t("finance.coa.add.open"));
    expect(html).not.toContain(t("finance.coa.add.title"));
  });

  it("BR-SHL-025: a read-only role sees the import control DISABLED, with its reason", () => {
    const html = renderTab(SERVICES, TAXES, { sub: "chart", readOnly: true });
    expect(html).toContain(t("settings.accounting.import.open"));
    expect(html).toContain(t("settings.readOnlyReason"));
    expect(html).toContain("disabled");
  });
});

describe("CR-008 — the finance-controls tab carries the two new money settings", () => {
  it("both new parameters render, and the ambiguous write-off label is gone", () => {
    const html = renderTab(SERVICES, TAXES, {
      sub: "controls",
      financeControls: {
        ...FINANCE_CONTROLS,
        bank_match_amount_tolerance: "0",
        write_off_approval_threshold_amount: "0",
      },
    });
    expect(html).toContain(t("settings.rules.finance_controls.bank_match_amount_tolerance"));
    expect(html).toContain(
      t("settings.rules.finance_controls.write_off_approval_threshold_amount"),
    );
    // ⚠ THE COLLISION CR-008 RULING 2 IS ABOUT. The two labels must not be
    // near-identical, because one is a $50-capped automatic clear-out and the
    // other decides whether a human approves a write-off at all.
    const automatic = t("settings.rules.finance_controls.write_off_threshold_amount");
    const approval = t("settings.rules.finance_controls.write_off_approval_threshold_amount");
    expect(automatic).not.toBe(approval);
    expect(automatic.toLowerCase()).toContain("final bill");
    expect(approval.toLowerCase()).toContain("approver");
  });

  it("the fiscal calendar POINTS at Regional, and names who may reopen a period", () => {
    const html = renderTab(SERVICES, TAXES, { sub: "controls" });
    expect(html).toContain(t("settings.accounting.fiscal.title"));
    expect(html).toContain(t("settings.accounting.fiscal.reopen"));
    // Ruling 5: System Admin is the only legal value, so it is a SENTENCE and
    // not a three-way picker. A <select> here would be the decoration the PO
    // ruled against.
    expect(t("settings.accounting.fiscal.reopen")).toContain("System Admin");
    expect(html).toContain(t("settings.accounting.scope.body"));
  });
});

describe("CR-008 — the six things the PO ruled OUT stay out", () => {
  it("no sub-tab mentions QuickBooks, a sync, a Synced pill or accrual-versus-cash", () => {
    const banned = [/quickbooks/i, /\bsync\b/i, /accrual/i, /last-sync/i, /rounding difference/i];
    for (const sub of ["chart", "mapping", "controls"]) {
      const html = renderTab(SERVICES, TAXES, {
        sub,
        charges: CHARGES,
        reasons: REASONS,
        designations: DESIGNATIONS,
        financeControls: FINANCE_CONTROLS,
      });
      for (const pattern of banned) {
        // Rulings 1, 3 and 8, asserted STRUCTURALLY: re-adding any of them
        // goes red here rather than being noticed in a design review.
        expect(html).not.toMatch(pattern);
      }
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// amended:  2026-08-17 by story-coder (CR-008 SECOND-SET rulings 1 and 2) — nine cases for the per-tender clearing account and for Settings being the ONE editor.
//        PROVED RED STRUCTURALLY, and the proof is a fact rather than a claim: at 4c91563 (the commit before this lane) `git show 4c91563:…/SettingsAccountingTab.tsx | grep -c tenderClearingAccountId` = 0
//        and the same grep for `perTenderTitle` in en.json = 0, so this file cannot even IMPORT against the previous tree — every one of the nine fails at module load.
//        The section-4 case is the one to keep: it asserts the charge action EXISTS, because ruling 2 took the picker off Plans & Rates and read-only with no editor anywhere is not one editor, it is none.
// packet: US-BIL-009@0000000 (story+rules snapshot — EP-BIL-02; BR-BIL-067/069 landed 2026-08-11 after the packet was cut, so the hash is a placeholder and is reported)
// generated: 2026-08-11 by story-coder (S8 Accounting / GL mapping lane)
// amended:   2026-08-16 by story-coder (CR-004 task C) — three tests for the moved S71 section: every one of FINANCE_CONTROLS_PAGE's seven parameters renders inside this tab (so a field lost in transit goes RED), the entry point is the ONLY thing that moved (the card is gone from referenceDataConfig, the field law is still settingsRulePages.ts's alone), and the read-only reason reaches the moved page's save bar as well as the GL buttons.
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — `GET /ledger/accounts` is contracted 11b §S56 and unserved) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: PROVED RED FIRST (law 7) — before the build, `tsc --noEmit` named all four gaps verbatim: "Module '\"@/api/endpoints\"' has no exported member 'GlAccountRef'", "Cannot find module './SettingsAccountingTab'", "'revenue_account' does not exist in type 'TenantServiceRow'" and "Property 'ledgerAccounts' does not exist", and `vitest run` on this file reported "Failed to load url ./SettingsAccountingTab … Does the file exist?" · after: tsc✔ · eslint --max-warnings 0✔ · vitest 59 files, 874 passed / 183 todo✔ (58 files, 858 + 183 was the pre-lane baseline — this lane adds 16 passing and drops nothing) · vite build✔ · G13 unwired-props PASS (71 components) · G14 prototype-conformance PASS · G15 i18n-parity PASS across ELEVEN catalogues (3126 keys each) · G19 env-hostnames PASS
// exceptions: E4 the chart's ABSENCE is asserted on the pure `chartRouteAbsent` rather than on a rendered failure frame — this suite renders through `renderToStaticMarkup`, where effects never run and a query can only be seeded with SUCCESS data (the BillsPage precedent); the RENDERED half is proved on the partial-list notice and the disabled tax control instead · E4 the modal itself is never opened by a click: the two writes are proved end to end through `createApiClient` with a recording `fetchImpl`, which asserts the URL, the method and the exact body — stronger evidence than a rendered form · E4 US-BIL-009 TC-3/TC-4/TC-6/TC-7 are server, posting-service and RLS scope and belong to the backend lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
