// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-008 (Charge codes tab + S12) · US-RAT-009 (Taxes & fees tab + S13)
//           Screens: S9, S12, S13
// Rules:    BR-RAT-005 (fees and late are never in the tax base) · BR-RAT-035 (identity,
//           deactivate-first, amounts are SEEDS never constants) · BR-RAT-036 (three tax
//           forms; only usage + base are offerable) · BR-RAT-041 ("Formula" is visible and
//           DISABLED) · BR-RAT-042 (the per-unit threshold is MARGINAL) · BR-TEN-037
//           (tenant-entered jurisdictions) · BR-SHL-010/011/025/032
// ───────────────────────────────────────────────────────
// Two load-bearing absences here: the taxable-base panel can express ONLY usage
// and base (B4.2 removed the prototype's Fees and tax-on-tax boxes), and the
// S12 form ships not one amount literal — BR-RAT-035 makes NSF $30 and
// reconnect $45 seed DATA, not defaults this screen would re-introduce.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError, createApiClient } from "@/api/client";
import referenceDataSource from "../tenancy/referenceDataConfig.ts?raw";
import { CHARGE_AMOUNT_RULE_FORMULA, createTax, setChargeActive } from "@/api/endpoints";
import type {
  ChargeRow,
  Paginated,
  TaxJurisdiction,
  TaxRow,
  TenantServiceRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { apiErrorText } from "@/features/tenancy/settingsShared";

import {
  ChargeCodesTab,
  amountFieldsFor,
  amountRuleOptions,
  chargeAmountDisplay,
  chargeIsLocked,
  chargeSchema,
  chargeTableConfig,
} from "./ChargeCodesTab";
import { TaxesFeesTab, taxAppliesToCell, taxRateDisplay, taxTableConfig } from "./TaxesFeesTab";
// CR-165-BRC10 task 7: `TaxWizard.tsx` is retired. The S13 form is
// `taxForm/` — New (`NewTaxWizard`) and Edit (`EditTaxForm`), one draft, one
// payload builder — so the form rules are asserted on that builder.
import { emptyTaxFormDraft, taxFormPayload } from "./taxForm/taxFormModel";
import type { TaxFormDraft } from "./taxForm/taxFormModel";
import { infoPatchPayload, lockedFields } from "./taxForm/taxEditModel";
import { decimalShapeError } from "./ratingShared";
import type { RatingTabRender } from "./ratingShared";
import type { Translator } from "./ratingShared";

// US-SHL-020 addendum r2: a tab hands its button and its content to the frame
// rather than rendering the button itself. These tests exercise the tab alone,
// so they stand in for the frame and render both halves.
const bothHalves: RatingTabRender = ({ action, body }) => (
  <>
    {action}
    {body}
  </>
);

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…` and
// every tenant-scoped call goes to `/api/{tenant}/…`. Tests state the tenant
// the browser would be showing, so both are visible here rather than implied.
const TEST_TENANT = "brazosbend";

// CR-008 ruling 2 — the two source files, read as text so "one editor" is
// checkable rather than merely commented. See the case at the bottom.
import chargeSource from "./ChargeCodesTab.tsx?raw";
// CR-013 §18 row 9: the charge-code EDITOR is a route now, so "one GL editor"
// has to be asserted where the editing happens.
import chargeWizardSource from "./ChargeCodeWizard.tsx?raw";
import taxTabSource from "./TaxesFeesTab.tsx?raw";
import { taxRowDefaults } from "./taxRowFixture";

const t: Translator = (key, params) => i18n.t(key, params);

const SERVICES: TenantServiceRow[] = [
  {
    service: "electric",
    name: "Electric",
    enabled: true,
    primary_uom: "kWh",
    alt_uom: "kW",
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 4,
    active_accounts: 1098,
  },
  {
    service: "water",
    name: "Water",
    enabled: true,
    primary_uom: "kgal",
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    // BR-BIL-067's GL half: not what this suite is about, and NULL is the
    // honest value — an unmapped service is a real state (BR-BIL-010).
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: 3,
    active_accounts: 950,
  },
];

// The US-RAT-008 §4 seed. Every amount is a decimal STRING; the percent is the
// stored FRACTION (0.015 = 1.5 %).
const CONN: ChargeRow = {
  id: "c-conn",
  code: "CONN",
  name: "Connection",
  charge_type: "one_time",
  service: null,
  amount_rule: "flat",
  amount: "85.000000",
  percent: null,
  min_amount: null,
  max_amount: null,
  // BR-RAT-087: what the SERVER sends for display. Stored precision above,
  // rendered precision here — the tab reads these (DEF-364).
  amount_display: "85.00",
  percent_display: null,
  min_amount_display: null,
  max_amount_display: null,
  gl_account_id: null,
  // BR-RAT-088 (DEF-372): declared, never inferred. A connection fee is not
  // anybody's base charge, and the flag is now served on every row.
  is_base: false,
  size_amounts: [], // DEF-431 — no per-size base rows on this fixture
  taxable_default: false,
  auto_apply: false,
  waivable: true,
  separate_line: true,
  status: "active",
  used_by_plans: 0,
  used_by_invoice_lines: 0,
};

const LATE: ChargeRow = {
  ...CONN,
  id: "c-late",
  code: "LATE",
  name: "Late fee",
  charge_type: "penalty",
  amount_rule: "percent_with_minimum",
  amount: null,
  percent: "0.015000",
  min_amount: "5.000000",
  amount_display: null,
  percent_display: "1.50%",
  min_amount_display: "5.00",
  used_by_plans: 4,
};

const TX_STATE: TaxRow = {
  ...taxRowDefaults(),
  id: "tax-tx",
  name: "TX State Utility Tax",
  jurisdiction: {
    id: "j-tx",
    name: "Texas Comptroller",
    authority: "Texas Comptroller",
    level: "state",
    reference_no: null,
  },
  kind: "percent",
  rate: "0.062500",
  // DEF-291 read this row as "0.062500 of the taxable base".
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
  // DEF-273: r10 exempts residential from the State Utility Tax, so the
  // INCLUSION list names the two classes it does reach — which is the
  // fixture that makes the `Applies to` cell say so.
  applies_to_customer_classes: ["commercial", "industrial"],
  premises_scope_kind: null,
  premises_scope_value: null,
  liability_gl_account_id: null,
  remit_to: "Texas Comptroller",
  filing_frequency: "monthly",
  filing_form: null,
  effective_from: "2026-08-01",
  effective_to: null,
  status: "active",
  used_by_plans: 2,
};

const CONSERVATION: TaxRow = {
    ...TX_STATE,
  id: "tax-cons",
  name: "Water Conservation Surcharge",
  kind: "per_unit",
  rate: null,
  per_unit_amount: "0.250000",
  per_unit_uom: "kgal",
  // BR-RAT-036 as amended (DEF-386) — the fourth computation form.
  per_meter_amount: null,
  per_meter_amount_display: null,
  applies_to_services: ["water"],
  filing_frequency: "annual",
};

const JURISDICTIONS: TaxJurisdiction[] = [
  {
    id: "j-tx",
    name: "Texas Comptroller",
    authority: "Texas Comptroller",
    level: "state",
    reference_no: null,
  },
];

const CHARGE_CONFIG = chargeTableConfig(t, [], {
  code: () => <span />,
  kind: () => <span />,
  pricedBy: () => "",
  type: () => "",
  service: () => "",
  amount: () => "",
  customerClass: () => "",
  gl: () => <span />,
  taxable: () => "",
  status: () => <span />,
  actions: () => <span />,
});
const TAX_CONFIG = taxTableConfig(t, [], {
  name: () => <span />,
  version: () => <span />,
  appliesTo: () => <span />,
  rate: () => <span />,
  from: () => <span />,
  to: () => <span />,
  gl: () => <span />,
  premises: () => <span />,
  status: () => <span />,
  open: () => <span />,
});

const DEFAULT_STATE = { q: "", page: 1, per: 50 as const, filters: {} };

function renderCharges(rows: ChargeRow[]): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  const state = { ...DEFAULT_STATE, ...CHARGE_CONFIG.defaultSort };
  queryClient.setQueryData(
    queryKeys.charges(serializeTableParams(state, CHARGE_CONFIG).toString()),
    {
      count: rows.length,
      next: null,
      previous: null,
      results: rows,
    } satisfies Paginated<ChargeRow>,
  );
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/plans-rates/charge-codes"]}>
          <ChargeCodesTab readOnly={false} timeZone="America/Chicago" dateFormat="MM/DD/YYYY"
              render={bothHalves}
            />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderTaxes(rows: TaxRow[]): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  queryClient.setQueryData(queryKeys.taxJurisdictions, JURISDICTIONS);
  const state = { ...DEFAULT_STATE, ...TAX_CONFIG.defaultSort };
  queryClient.setQueryData(queryKeys.taxes(serializeTableParams(state, TAX_CONFIG).toString()), {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
  } satisfies Paginated<TaxRow>);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/plans-rates/taxes-fees"]}>
          <TaxesFeesTab readOnly={false} timeZone="America/Chicago" dateFormat="MM/DD/YYYY"
              render={bothHalves}
            />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-RAT-008 — charge codes (S9 tab + S12)", () => {
  it("US-RAT-008 TC-1: the catalog columns, and LATE rendered as its percent plus its minimum", () => {
    const html = renderCharges([CONN, LATE]);
    for (const label of ["Code", "Description", "Type", "Amount", "GL account"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).toContain("CONN");
    expect(html).toContain("LATE");
    expect(CHARGE_CONFIG.defaultSort).toEqual({ sort: "code", dir: "asc" });
    // ⚠ THIS ASSERTED THE DEFECT UNTIL 2026-08-20 (DEF-364). It read
    // `percent: "0.015000"` and expected the sentence "0.015000 of the amount",
    // with a comment explaining that the screen must not multiply by 100.
    //
    // The comment's REASON was right and is unchanged: scaling here would be
    // client-side money arithmetic on a value the server owns (CLAUDE.md #2).
    // The conclusion drawn from it was wrong — if the client may not format,
    // the SERVER must, and nobody built that half. So a customer read
    // "0.015000 of the amount" for as long as this test kept it green.
    //
    // The fix is not a multiplication in this file. It is `percent_display`,
    // formatted server-side by `_display_percent` (BR-RAT-087).
    const display = chargeAmountDisplay(LATE);
    expect(display.key).toBe("rating.charges.amount.percentWithMin");
    expect(display.params).toEqual({ percent: "1.50%", min: "5.00" });
    expect(t(display.key, display.params)).toBe("1.50% of the amount, at least 5.00");
    expect(chargeAmountDisplay(CONN).params).toEqual({ amount: "85.00" });
  });

  it("US-RAT-008 TC-2: the form's field set follows the amount rule", () => {
    expect(amountFieldsFor("flat")).toEqual({ amount: true, percent: false, minimum: false });
    expect(amountFieldsFor("percent")).toEqual({ amount: false, percent: true, minimum: false });
    expect(amountFieldsFor("percent_with_minimum")).toEqual({
      amount: false,
      percent: true,
      minimum: true,
    });
  });

  it("US-RAT-008 TC-5/TC-6: a duplicate code and a negative amount are the SERVER's refusals", () => {
    const duplicate = new ApiError(422, {
      code: "VAL-001",
      message_key: "rating.charges.duplicate_code",
    });
    expect(apiErrorText(duplicate, t)).toBe("A charge code with that code already exists.");
    const negative = new ApiError(422, { code: "VAL-003", message_key: "rating.below_minimum" });
    expect(apiErrorText(negative, t)).toContain("below the lowest value allowed");
    // The client-side schema is SHAPE only: "-85" is a well-formed decimal and
    // is sent, because BR-RAT-043 needs negatives and only the server knows
    // which fields may hold one.
    const shaped = chargeSchema(t).safeParse({
      code: "TAMPER",
      name: "Meter tampering",
      amount_rule: "flat",
      amount: "-85",
      percent: "",
      min_amount: "",
      max_amount: "",
    });
    expect(shaped.success).toBe(true);
    const malformed = chargeSchema(t).safeParse({
      code: "TAMPER",
      name: "Meter tampering",
      amount_rule: "flat",
      amount: "$85",
      percent: "",
      min_amount: "",
      max_amount: "",
    });
    expect(malformed.success).toBe(false);
  });

  it("US-RAT-008 TC-7 / BR-RAT-035: deactivate is always allowed; delete is the server's lock", async () => {
    expect(chargeIsLocked(CONN)).toBe(false);
    expect(chargeIsLocked(LATE)).toBe(true); // attached to 4 plans
    let body: unknown = null;
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (_input, init) => {
        body = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ ...LATE, status: "inactive" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const saved = await setChargeActive("c-late", false, client);
    expect(body).toEqual({ active: false });
    expect(saved.status).toBe("inactive");
    const locked = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "rating.charges.locked_referenced",
      params: { plans: 4, invoice_lines: 0 },
      br_ref: "BR-RAT-035",
    });
    expect(apiErrorText(locked, t)).toContain("4 plans");
    expect(apiErrorText(locked, t)).toContain("Deactivate it instead");
  });

  it("US-RAT-008 TC-8 / BR-RAT-041: Formula is VISIBLE and cannot be chosen or sent", () => {
    const options = amountRuleOptions(t);
    const formula = options.find((option) => option.value === CHARGE_AMOUNT_RULE_FORMULA);
    // Present, so the user learns the rule exists…
    expect(formula).toBeDefined();
    // …and unselectable, so they never learn it by being refused at submit.
    expect(formula?.disabled).toBe(true);
    expect(formula?.label).toContain("not available yet");
    // Belt and braces: the schema refuses it too, in the rule's own words.
    const result = chargeSchema(t).safeParse({
      code: "X",
      name: "X",
      amount_rule: CHARGE_AMOUNT_RULE_FORMULA,
      amount: "",
      percent: "",
      min_amount: "",
      max_amount: "",
    });
    expect(result.success).toBe(false);
  });

  it("BR-RAT-035: not one amount literal ships with this screen", () => {
    // The prototype's NSF $30 and reconnect $45 are SEED DATA, so an empty
    // catalog renders an empty form — never a pre-filled amount.
    const html = renderCharges([]);
    expect(html).toContain("No charge codes yet");
    for (const seedAmount of ["30.00", "45.00", "85.00", "150.00"]) {
      expect(html).not.toContain(seedAmount);
    }
  });

  it("BR-RAT-005: the taxable flag says out loud that it cannot tax a fee", () => {
    expect(t("rating.charges.taxableHelp")).toContain("never part of the tax base");
  });

  it("BR-SHL-010: the declared capability row, Download included (POST /exports, 2026-08-10)", () => {
    expect(CHARGE_CONFIG.searchFields).toEqual(["code", "name"]);
    expect(CHARGE_CONFIG.filters?.map((filter) => filter.name)).toEqual([
      "type",
      "service",
      "status",
      // CR-156-BRC10 — declared so `f.kind` survives the URL; drawn as chips.
      "kind",
    ]);
    // EP-RAT-03 declares "Export: CSV (IS-9)". The route it needed did not
    // exist when this suite was written, so this assertion was its negative;
    // POST /exports landed with the list-export lane and it is now the
    // positive — CSV only, because IS-11 forbids XLSX and nothing can ask.
    const html = renderCharges([CONN]);
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="charges"');
    expect(html).not.toContain("XLSX");
  });

  it.todo(
    "US-RAT-008 TC-3/TC-4: re-creating LATE and overriding CONN at $95 on a plan — the plan attachment is S10's, and both need a click (browser scope)",
  );
  it.todo("US-RAT-008 TC-9 (isolation): two tenants may both hold a CONN — server scope (G5)");
});

describe("US-RAT-009 — taxes & fees (S9 tab + S13)", () => {
  it("US-RAT-009 TC-1: the drawn columns, with the rate as the server displays it", () => {
    const html = renderTaxes([TX_STATE, CONSERVATION]);
    // CR-165 images 01–03 (DEF-RAT-9274): Remittance left the list for the
    // details page; the GL heading is the drawing's `GL account`.
    for (const label of ["Applies to", "Rate", "From", "To", "GL account", "Premises"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).toContain("TX State Utility Tax");
    expect(html).toContain("Water Conservation Surcharge");
    // ⚠ DEF-291's exact sentence, asserted as correct until 2026-08-20: this
    // read "0.062500 of the taxable amount". The defect was filed nine days
    // earlier against the Taxes screen and this test went on protecting it.
    // BR-RAT-087 (DEF-364): the server sends "6.25%" and the screen renders it.
    expect(t(taxRateDisplay(TX_STATE).key, taxRateDisplay(TX_STATE).params)).toBe(
      "6.25% of the taxable amount",
    );
    expect(t(taxRateDisplay(CONSERVATION).key, taxRateDisplay(CONSERVATION).params)).toBe(
      "0.25 per kgal",
    );
    // DEF-RAT-9143 · PO 2026-10-02: a per-unit tax is a UNIT PRICE — up to
    // four places, at least two. It printed the six stored places raw.
    expect(
      t(
        taxRateDisplay({ ...CONSERVATION, per_unit_amount: "0.002500" }).key,
        taxRateDisplay({ ...CONSERVATION, per_unit_amount: "0.002500" }).params,
      ),
    ).toBe("0.0025 per kgal");
    expect(
      t(taxRateDisplay({ ...TX_STATE, kind: "flat_per_bill", flat_amount: "0.850000" }).key, {
        amount: "0.850000",
      }),
    ).toBe("0.850000 per bill");
  });

  it("US-RAT-009 TC-3 / BR-RAT-036: the taxable base can express ONLY usage and base", () => {
    const html = renderTaxes([TX_STATE]).toLowerCase();
    // The two legal bases exist as ids…
    expect(t("rating.taxes.baseUsage")).toBe("Usage charges");
    expect(t("rating.taxes.baseBase")).toBe("Base service charges");
    // …and the prototype's two illegal ones have no control anywhere. B4.2
    // makes them impossible, so they are absent rather than disabled.
    for (const forbidden of ["base_includes_fees", "tax_on_tax", "base_includes_tax"]) {
      expect(html).not.toContain(forbidden);
    }
    // ⚠ THE SENTENCE MOVED, THE RULE DID NOT (2026-09-19 copy sweep).
    // `baseHelp` used to add *"Fees, late charges and other taxes are never
    // part of the base, so there is nothing else to choose"* — nineteen words,
    // of which the second clause is RATIONALE for an absent control, which
    // B14 rule 33 puts at zero words on screen. What the rule needs said is
    // that the base is CLOSED at two, and that is what is asserted now; the
    // forbidden ids above are the half that proves nothing else is offered.
    expect(t("rating.taxes.baseHelp")).toContain("Only these two");
  });

  it("US-RAT-009 TC-2: the form's payload carries the figure of its computation form, and no other", () => {
    // AMENDED 2026-08-21 — BR-RAT-036 has FOUR forms (PO ruling, option C,
    // DEF-386). RESTATED 2026-10-03 (CR-165 task 7) on the form that is
    // mounted: each form sends exactly ONE figure. An unknown form sends NONE
    // rather than defaulting to percent — a silent default here would price a
    // fee as a share of the whole bill.
    const figures = (draft: TaxFormDraft) =>
      ["rate", "flat_amount", "per_unit_amount", "per_meter_amount"].filter(
        (key) => key in taxFormPayload(draft, { asDraft: false, placeBoundaries: [] }),
      );
    const base = { ...emptyTaxFormDraft(), rate_percent: "6.25", amount: "1.25", per_unit_uom: "kWh" };
    expect(figures({ ...base, basis: "percent" })).toEqual(["rate"]);
    expect(figures({ ...base, basis: "flat_per_bill" })).toEqual(["flat_amount"]);
    expect(figures({ ...base, basis: "per_unit" })).toEqual(["per_unit_amount"]);
    expect(figures({ ...base, basis: "per_meter" })).toEqual(["per_meter_amount"]);
    expect(figures({ ...base, basis: "not_a_form" })).toEqual([]);
  });

  it("US-RAT-009 TC-5: a blank or negative rate is the SERVER's refusal, not a client guess", async () => {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(
          JSON.stringify({
            code: "VAL-001",
            message_key: "rating.required",
            field_errors: [{ field: "rate", code: "VAL-001", message_key: "rating.required" }],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
    });
    await expect(createTax({ name: "x", kind: "percent" }, client)).rejects.toBeInstanceOf(
      ApiError,
    );
    // The shape guard passes a negative through — the SERVER owns the bound.
    //
    // ⚠ IT IS ASSERTED ON `decimalShapeError` NOW, NOT ON A ZOD SCHEMA. TAX-02
    // deleted `taxSchema` when it replaced the modal: `FormModal` validated
    // before submitting, a full-page wizard submits to the server, and
    // `ratingShared`'s module law calls a client-side copy of a money bound *"a
    // second, drifting rulebook over money"*. The SHAPE rule survived the
    // reshape and is asserted where it lives; the duplicate did not.
    expect(decimalShapeError("-0.02")).toBeNull();
    expect(decimalShapeError("6.25%")).toBe("rating.error.notDecimal");
  });

  it("US-RAT-009 TC-7 / BR-RAT-042: the per-unit threshold is live, and MARGINAL", () => {
    // OQ-054 is CLOSED → BR-RAT-042, and the server now stores the threshold —
    // so the field is offered rather than blocked, with the marginal rule said
    // on it. (The story's TC-7 predates the closure; reported.)
    // ⚠ SHORTENED 2026-09-19, AND THE WORD UNDER TEST IS *ABOVE*. The
    // marginal rule is the whole point of BR-RAT-042 — only the units ABOVE
    // the threshold are taxed, never the whole quantity — so the assertion
    // holds that word rather than the old twelve-word sentence around it.
    expect(t("rating.taxes.appliesAboveHelp")).toContain("Only units above this are taxed");
  });

  it("BR-TEN-037: authorities are tenant-entered, with an inline add and no registry", () => {
    // ⚠ **THE HELP LINE IS GONE AND THE RULE IS ASSERTED WHERE IT IS REAL**
    // (2026-09-19 copy sweep). It read *"Authorities are yours to enter: there
    // is no shared registry to look one up in."* — fifteen words explaining WHY
    // the product has no lookup, which B14 rule 33 makes ZERO words on screen.
    // **A sentence saying there is no registry was never the guarantee anyway**
    // (hard-won law 1): what makes BR-TEN-037 true is that the picker carries an
    // INLINE ADD and the wizard has the four fields behind it, so that is what
    // this case checks now — a control, not a claim about one.
    // ⚠ RESTATED 2026-10-03 (CR-165 task 7). The inline add lived in
    // `TaxWizard.tsx`, which is retired; the redrawn New form (image 04) draws
    // the authority as a plain dropdown. BR-TEN-037's guarantee — the utility
    // ENTERS its own authorities — is held by Settings › Reference data, whose
    // `tax_jurisdictions` list is where an authority is added.
    expect(referenceDataSource).toContain("tax_jurisdictions");
  });

  it("BR-SHL-010: the declared capability row, Download included (POST /exports, 2026-08-10)", () => {
    expect(TAX_CONFIG.searchFields).toEqual(["name", "authority"]);
    // CR-165 + PO 2026-10-03 (*"filter and not button for filters"*): the kit's
    // `+ Filter` set, each narrowed by the server, plus the banner's `over_20`.
    expect(TAX_CONFIG.filters?.map((filter) => filter.name)).toEqual([
      "status",
      "service",
      "level",
      "over_20",
    ]);
    const html = renderTaxes([TX_STATE]);
    expect(html).toContain('data-download="button"');
    expect(html).toContain('data-resource="taxes"');
    expect(html).not.toContain("XLSX");
  });

  it("an empty applies-to list means EVERY service, and says so", () => {
    const html = renderTaxes([TX_STATE]);
    expect(html).toContain("All services");
    const scoped = renderTaxes([CONSERVATION]);
    expect(scoped).toContain("Water");
  });

  it("DEF-292: the Applies-to cell shows the customer classes and the premises scope", () => {
    // Both qualifiers have been writable, seedable and ENFORCED since
    // 2026-08-18 and appeared on NO screen — *"the ruled City Franchise Fee,
    // which applies 'inside city limits only', can never be given a city and
    // reaches nobody, for ever."* The cell is half the fix; TAX-02 is the other.
    expect(taxAppliesToCell(TX_STATE, t)).toBe("All services · Commercial, Industrial");
    const franchise: TaxRow = {
            ...TX_STATE,
      applies_to_customer_classes: [],
      premises_scope_kind: "city_limits",
      premises_scope_value: "Silver Creek",
    };
    expect(taxAppliesToCell(franchise, t)).toBe("All services · Inside city limits: Silver Creek");
    // A boundary switched on and never named reaches NOBODY, and the list says
    // so rather than rendering an unscopeable tax as though it applied.
    expect(taxAppliesToCell({ ...franchise, premises_scope_value: "" }, t)).toBe(
      "All services · Inside city limits: not named yet",
    );
    // ⚠ CR-165 (DEF-RAT-9274): the LIST no longer prints the boundary — the
    // drawing's Applies-to cell is services and classes, and the list's
    // Premises column (`N of M`) is where an unscopeable tax now shows, as 0.
    // The cell function above is kept for the details page's read.
  });

  it("CR-013 P4 · CR-165 P28: the tab holds ONE door to the wizard and opens no modal", () => {
    // Hard-won law 2 in both directions: the doors go somewhere, and nothing is
    // left pointing at the modal that was removed. The row's pencil to the EDIT
    // door is gone (P28) — a row opens the details page, where Edit lives.
    const source = taxTabSource;
    expect(source).toContain("TAX_WIZARD_NEW_ROUTE");
    expect(source).not.toContain("taxWizardEditPath");
    expect(source).not.toContain("FormModal");
    expect(source).not.toContain("TaxFormModal");
  });

  it.todo(
    "US-RAT-009 TC-4/TC-6: plan × jurisdiction attachment and its uniqueness — the attachment is S10's and the refusal needs a click (browser scope)",
  );
  it.todo(
    "US-RAT-009 TC-8 (isolation): jurisdiction lists never leak between tenants — server scope (G5)",
  );
});

describe("CR-008 ruling 2 — these two screens SHOW a GL account and no longer EDIT one", () => {
  // PO 2026-08-17: *"editing and chaigng will be done in setting only"* and
  // *"we will display it every place where it make sense"*.

  it("the list still names the account by CODE and NAME — display did not go away with the editor", () => {
    const html = renderCharges([{ ...LATE, gl_account_id: "acc-4200" }]);
    expect(html).toContain(">GL account<");
    // Unresolvable here because this fixture serves no chart — and even then
    // it is words, never the uuid (DEF-206's own lesson).
    expect(html).not.toContain("acc-4200");
  });

  it("an UNMAPPED charge still reads as unset rather than blank", () => {
    const html = renderCharges([CONN]);
    expect(html).toContain(t("rating.gl.unset"));
  });

  it("the copy points at the one editor and names it", () => {
    expect(t("rating.gl.editedInSettings")).toContain("Accounting");
    expect(t("rating.gl.openSettings")).toContain("Accounting");
  });

  it("⚠ THE FORMS OMIT THE GL FIELD — absent, not null, because null CLEARS a mapping", () => {
    // The only mechanically checkable form of "one editor": read the two
    // source files and assert neither builds a GL key into its save payload.
    // It goes RED the day somebody re-adds a picker to either screen, which is
    // the one thing that would quietly give a utility two editors again.
    //
    // Why `null` would be worse than a second editor: both forms used to send
    // the pointer on EVERY save, so a read-only field left sending `null`
    // would wipe a charge's account whenever somebody renamed the charge —
    // and BR-BIL-010 then refuses the WHOLE bill at issue.
    // `?raw` is Vite's own source read, typed by `vite/client` — no node:fs,
    // so the same assertion runs in vitest and would in a browser runner.
    //
    // ⚠ THE CHARGE HALF MOVED FILES ON 2026-08-21 AND THE GUARD MOVED WITH IT.
    // S12 left `ChargeCodesTab` for the full-page `ChargeCodeWizard` (CR-013
    // §18 row 9, PO: *"Wizards for each type - no modal"*), so the EDITOR that
    // could re-acquire a GL picker is that file now. Asserting only against the
    // tab would have kept passing while saying nothing — the exact shape of a
    // check that survives a refactor and stops watching anything.
    const charge = chargeSource;
    const wizard = chargeWizardSource;
    // ⚠ THE TAX SOURCE MOVED WITH ITS FORM (CR-013 P4). This assertion has to
    // follow the file that BUILDS THE PAYLOAD, not the file that is named after
    // the screen — pointed at `TaxesFeesTab.tsx` it would now pass over a file
    // with no payload in it at all, which is a check that cannot fail.
    for (const source of [charge, wizard]) {
      expect(source).not.toMatch(/^\s+gl_account_id: /m);
    }
    // ⚠ RESTATED 2026-10-03 (CR-165 task 7, and the PO's CR-008 amendment of
    // the same day: *"Pick it when you create the tax; change it later only in
    // Settings"*). The NEW form may send the liability account — it is chosen
    // at creation. The EDIT form may not, in any variation: it is locked, and
    // the PATCH a live tax sends never carries it even if the box moved.
    for (const mode of ["info", "change", "correct"] as const) {
      expect(lockedFields(mode).has("liability_gl_account_id")).toBe(true);
    }
    const before = emptyTaxFormDraft();
    expect(
      "liability_gl_account_id" in infoPatchPayload(before, { ...before, liability_gl_account_id: "gl-x" }),
    ).toBe(false);
    // …and both EDITORS DO render the read-only field that replaced the picker.
    // CR-156-BRC10 wave B (PO 2026-10-01, *"i will move GL code to side panel"*):
    // the charge wizard SHOWS the code's account read-only in its summary aside
    // (`GlValue`), and still posts none.
    expect(wizard).toContain("<GlValue");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// amended:  2026-08-17 by story-coder (CR-008 ruling 2) — four cases for "these screens SHOW a GL account and no longer EDIT one".
//        PROVED RED, quoted: the payload guard run against the previous version finds exactly what it forbids —
//          `git show 4c91563:…/ChargeCodesTab.tsx | grep -nE '^\s+(gl_account_id|liability_gl_account_id): '` → `625:      gl_account_id: glAccount === "" ? null : glAccount,`
//          the same on TaxesFeesTab.tsx → `571:      liability_gl_account_id: glAccount === "" ? null : glAccount,`
//        and 0 matches in both at HEAD. It reads the sources through Vite's `?raw`, not node:fs, so it needs no @types/node and would run in a browser runner unchanged.
//        WHY THAT GUARD AND NOT A CLICK: the S12/S13 modals open on a click and this file is renderToStaticMarkup only (the pre-existing E4 exception below). The payload is the part that can silently destroy data —
//        a read-only field left sending `null` CLEARS a mapping on every unrelated save — so it is the part asserted here, and the rendered field is proved by clicking in the browser walkthrough.
// packet: US-RAT-008@7d1a8ef (story+rules snapshot hash — EP-RAT-03; co-story US-RAT-009@7d1a8ef)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S12/S13) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 US-RAT-009 TC-7 expects the "applies above" field to BLOCK the save pending OQ-054; OQ-054 is CLOSED→BR-RAT-042 and the server stores the threshold, so the field is live with the marginal semantics stated — the superseded TC is asserted in its RATIFIED form and the divergence reported · E4 opening the S12/S13 modal is a click, so the form's own field-visibility law is proved through `amountFieldsFor`/`taxFieldsFor` and the modal's rendering is browser scope
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
