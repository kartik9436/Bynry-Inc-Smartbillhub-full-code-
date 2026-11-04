// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-003 (S18 New Account wizard, FIVE steps since c107eaae7 —
//           DEF-CUS-5185, PO: the plan step is gone)   Screens: S18
// ⚠ `DEF-CUS-9107` (2026-10-02): this file asserted the SIX-step wizard for
//           three weeks after it became five. Every case below that moved says
//           which ruling moved it.
// Rules:    BR-CUS-012 (the confirmed attribute set) · BR-CUS-017 (one active
//           account per unit) · BR-CUS-018 (draft vs activating create) ·
//           BR-CUS-019 (the duplicate check is advisory — and unbuildable) ·
//           BR-CUS-020 (only vacant units) · BR-CUS-021 (initial reads belong
//           to metering) · BR-CUS-022 (the start date is the first bill's) ·
//           BR-CUS-023 (the deposit is a plan lookup) · BR-CUS-028 (the
//           preference set) · BR-CUS-029 (no account plan snapshot) ·
//           BR-CUS-045 (the last four of a government id only) · BR-CUS-054 (no
//           customer entity) · BR-CUS-058 (the credit tier is computed) ·
//           BR-CUS-059 (autopay capture-only) · BR-CUS-060 (delivery day
//           dropped) · BR-MET-040 (a plan is required at activation) ·
//           BR-SHL-018/019 (the shared wizard rail and ONE commit) ·
//           BR-SHL-025 (disabled WITH the reason) · BR-SHL-044 (one header)
// ───────────────────────────────────────────────────────
// §4 test data is Elena Rivera on P-11800 · Unit A (US-CUS-003 §4), rendered
// through the seeded query cache — no network, ever.
//
// The payload assertions are the sharp end of this file: `createAccountPayload`
// must carry EXACTLY what the endpoint accepts and must never carry a field the
// endpoint refuses, because a refused field fails the whole create and a
// silently dropped one is a preference the user believes they saved.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { MyPermissions, Paginated, UnitRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import {
  CREATE_MODES,
  NEW_ACCOUNT_STEP_COUNT,
  NEW_ACCOUNT_STEP_IDS,
  NewAccountReviewStep,
  NewAccountWizard,
  UnitRecordPanel,
  createAccountPayload,
  customerNumberShortfall,
  emptyCustomerForm,
  emptyPreferencesForm,
  stepFromParam,
  vacantUnitOptions,
} from "./NewAccountWizard";
import { emptyDepositForm } from "./depositCapability";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNT_CATEGORIES_QUERY_KEY,
  ACCOUNT_NEW_ROUTE,
} from "./customersShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

function unit(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "u-11800a",
    unit_no: "U-11800-A",
    premises_id: "p-11800",
    premise_no: "P-11800",
    premise_address: "1408 Elm Street",
    label: "Unit A",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: "rp-res-std",
    plan_effective_from: "2024-01-01",
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    // CR-089 wave A · BR-MET-1162 — a unit's own point. `null` is the state
    // all 1,109 units are in today, and `point.source: "premises"` is the
    // ruled fallback: this unit reads its building's.
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters: [
      { id: "ast-5001", asset_no: "M-5001", qualifier: null },
      { id: "ast-5002", asset_no: "W-5001", qualifier: null },
    ],
    occupancy: "vacant",
    occupant: null,
    account_no: null,
    status: "vacant",
    // DEF-755 — *what is METERED here*, now under its own name. `services`
    // above is what the unit's PREMISES offers; the two answer different
    // questions and no longer share a word.
    metered_services: [],
    sub_metered: false,
    ...over,
  };
}

function unitsPage(rows: UnitRow[]): Paginated<UnitRow> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

// ⛔ **DEF-684 — THREE INVENTED CODES, ON PURPOSE.** BR-CUS-094 (PO
// 2026-08-24) expanded the signed vocabulary to SEVEN and made `government`
// LEGACY, and this screen kept rendering a hardcoded four. A fixture using the
// REAL codes could not tell a fetched list from a typed one, so these three
// exist in no constant, no catalogue and no seed: they can only reach the
// screen through `GET /service-requests/categories`.
const SERVED_CATEGORIES = {
  selectable: [
    { code: "zzz_selectable_one", name: "Zzz selectable one" },
    { code: "zzz_selectable_two", name: "Zzz selectable two" },
  ],
  legacy: [
    {
      code: "zzz_legacy",
      name: "Zzz legacy",
      br_ref: "BR-CUS-094",
      why: "unselectable_on_new_records_valid_everywhere_else",
    },
  ],
};

function renderWizard(
  path: string,
  seed: {
    units?: Paginated<UnitRow>;
    access?: string;
    categories?: typeof SERVED_CATEGORIES | null;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed.units !== undefined) {
    queryClient.setQueryData(["units", "vacant-picker"], seed.units);
  }
  if (seed.categories !== null) {
    queryClient.setQueryData(
      ACCOUNT_CATEGORIES_QUERY_KEY,
      seed.categories ?? SERVED_CATEGORIES,
    );
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <NewAccountWizard />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const CUSTOMER = {
  ...emptyCustomerForm(),
  account_type: "residential",
  full_name: "Elena Rivera",
  email: "elena.rivera@example.com",
  phone: "+1 (281) 555-0100",
  dob: "1991-03-18",
  gov_id_last4: "4218",
};

describe("US-CUS-003 — the S18 New account wizard", () => {
  it("US-CUS-003 §1 / BR-CUS-018: the FIVE ruled steps render on the SHARED wizard frame, never a hand-rolled stepper", () => {
    // FIVE since `c107eaae7` (2026-09-13, `DEF-CUS-5185`). PO, in the
    // blueprint: *"there should not be any step to select a plan as plan is
    // already attached on the unit itself."* The plan check moved onto step 2.
    expect([...NEW_ACCOUNT_STEP_IDS]).toEqual([
      "customer",
      "unit",
      "preferences",
      "deposit",
      "review",
    ]);
    expect(NEW_ACCOUNT_STEP_COUNT).toBe(5);
    const html = renderWizard(ACCOUNT_NEW_ROUTE, {
      units: unitsPage([unit()]),
      access: "Full",
    });
    // The frame's own rail and action row (B13 §1) — this screen draws neither.
    expect(html).toContain('data-wizard="frame"');
    expect(html).toContain('data-wizard="rail"');
    // Route B (2026-08-21): one `data-wizard-step` per button, and the rail no
    // longer shares its prefix — so this is 5, not 5 + 1.
    expect((html.match(/data-wizard-step=/g) ?? []).length).toBe(5);
    expect(html).toContain("Continue");
  });

  it("US-CUS-003 §1 / BR-SHL-044: the shared page header carries the prototype's kicker, H1 and step line", () => {
    const html = renderWizard(ACCOUNT_NEW_ROUTE, { units: unitsPage([unit()]), access: "Full" });
    expect(html).toContain("page-header");
    expect(html).toContain("New account");
    expect(html).toMatch(/<h1[^>]*>Create a first-time customer account\.<\/h1>/);
    // The step line under the title, from the frame's own count (five since
    // `c107eaae7`); the old *Six steps.* sub-line is not drawn.
    expect(html).toContain("Step 1 of 5 · Customer");
    expect(html).not.toContain("Six steps.");
    expect(html).toContain("← Accounts");
    // No bespoke head anywhere.
    expect(html).not.toContain("cus-head");
  });

  it("US-CUS-003 TC-1 / BR-CUS-045: step 1 collects the contact, and asks for four id digits only", () => {
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=1`, { access: "Full" });
    expect(html).toContain("Who is this account for?");
    expect(html).toContain('id="full_name"');
    expect(html).toContain('id="gov_id_last4"');
    // `DEF-CUS-6360` (PO 2026-09-23) — the hint *"The last four digits only.
    // The server keeps four digits…"* was rationale and is DELETED (B14 rule
    // 33); the four-digit rule is kept by `moveInPayload` / `createAccountPayload`
    // cutting to the last four, asserted in its own case below.
    expect(html).not.toContain("The server keeps four digits");
    // The prototype's ID TYPE selector is absent — the column was never built.
    expect(html).not.toContain("Driver's license");
    expect(html).not.toContain('id="gov_id_type"');
  });

  it("US-CUS-003 TC-5 / BR-CUS-019 / BR-CUS-054: there is no duplicate check, and the step no longer explains why", () => {
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=1`, { access: "Full" });
    // `DEF-CUS-6360` — the note was rationale (B14 rule 33, zero words) and
    // was also false: the customer table exists and a returning customer is
    // matched on the server. Deleted, not reworded.
    expect(html).not.toContain("There is no duplicate check on this step.");
    expect(html).not.toContain("Use existing customer");
    // The prototype's Individual/Business/Government is the CUSTOMER entity's
    // kind, which has no table; the field offered is the account CATEGORY the
    // endpoint actually stores.
    //
    // ⛔ **DEF-684 — THIS ASSERTION USED TO READ `toContain("Government")`.**
    // It was correct when it was written and BR-CUS-094 (PO 2026-08-24) made it
    // a pin on a defect: `government` is LEGACY, no new record may carry it,
    // and this screen offered it anyway. Rendered output is the only place that
    // can be seen — tsc cannot type-check a vocabulary and every unit test on
    // this file passed over the wrong four for two days.
    expect(html).toContain("Zzz selectable one");
    expect(html).toContain("Zzz selectable two");
    expect(html).not.toContain("Zzz legacy");
    // ⚠ **THE OPTION'S OWN MARKUP, NOT THE WORD.** `not.toContain("Government")`
    // is RED on this page for the wrong reason — the `gov_id_last4` field is
    // labelled *Government ID* three fields down. A check whose output cannot
    // distinguish pass from fail is worse than no check, so this names the
    // radio the defect was about.
    expect(html).not.toContain('value="government"');
  });

  it("DEF-684 / BR-CUS-094: with nothing served, the step states it rather than offering a typed list", () => {
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=1`, {
      access: "Full",
      categories: { selectable: [], legacy: [] },
    });
    // A18 §1 — an empty control that looks broken is the alternative.
    expect(html).toContain("This customer category is not set up here.");
    // And nothing falls back to a hardcoded four.
    expect(html).not.toContain('value="government"');
    expect(html).not.toContain('value="industrial"');
  });

  it("US-CUS-003 TC-1 / BR-CUS-020: step 2 offers only vacant units, and shows what the picked one carries", () => {
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=2`, {
      units: unitsPage([unit()]),
      access: "Full",
    });
    // The step's title is the drawing's *Which unit?*, and the panel heading
    // that said the same sentence twice is gone (`c107eaae7`).
    expect(html).toContain("Which unit?");
    expect(html).not.toContain("Pick the unit they&#x27;ll be billed for.");
    expect(html).toContain("Only vacant units are offered.");
    expect(html).toContain("1408 Elm Street · U-11800-A");
    expect(vacantUnitOptions([unit()])).toEqual([
      { value: "u-11800a", label: "1408 Elm Street · U-11800-A" },
    ]);
    // A18 §1 in miniature: no vacant unit is a statement, not a blank control.
    const none = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=2`, {
      units: unitsPage([]),
      access: "Full",
    });
    expect(none).toContain("No vacant unit is available");
  });

  it("US-CUS-003 TC-7 / BR-CUS-021: step 2 asks for the start date and captures NO initial read", () => {
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=2`, {
      units: unitsPage([unit()]),
      access: "Full",
    });
    expect(html).toContain('id="opened_at"');
    expect(html).toContain('type="date"');
    expect(html).toContain("No initial meter read is captured here.");
    // The prototype's read-source select posts nowhere and is not drawn.
    expect(html).not.toContain("AMI · pull today's reading");
    expect(html).not.toContain("Estimate from prior 3 cycles");
  });

  it("US-CUS-003 TC-2/TC-6 / BR-CUS-029 / BR-MET-040: NO step and NO control offers a plan", () => {
    // `c107eaae7` (`DEF-CUS-5185`) deleted the plan step: a step that
    // collected nothing. What it CHECKED moved onto step 2's unit panel (the
    // next case). No step, on any page, draws a plan control.
    for (const step of [1, 2, 3, 4, 5]) {
      const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=${step}`, {
        units: unitsPage([unit()]),
        access: "Full",
      });
      expect(html).not.toContain('id="plan"');
      expect(html).not.toContain('id="rate_plan_id"');
      expect(html).not.toContain("The plan this account bills on.");
    }
  });

  it("US-CUS-003 TC-6 / BR-MET-040: a unit with no plan is named, on step 2, as a create that WILL be refused", () => {
    // The check the deleted step ran, now WHERE THE UNIT IS CHOSEN
    // (`UnitRecordPanel`, mounted under step 2's picker).
    const panel = (plan: unknown) => {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      queryClient.setQueryData(["new-account-unit-pricing", "u-11800a"], { plan });
      return renderToStaticMarkup(
        <QueryClientProvider client={queryClient}>
          <UnitRecordPanel picked={unit()} t={(key, params) => i18n.t(key, params)} />
        </QueryClientProvider>,
      );
    };
    expect(panel(null)).toContain(
      "This unit has no plan, so activating will be refused.",
    );
    const withPlan = panel({ code: "RES-STD", name: "Residential Standard", version: 3 });
    expect(withPlan).toContain("RES-STD · Residential Standard · v3");
    expect(withPlan).not.toContain("activating will be refused");
  });

  it("DEF-CUS-5114: the unit panel's base charge reads as money in the TENANT's currency — $20.00, at two places", () => {
    const panel = (currency: string | null) => {
      const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      queryClient.setQueryData(["new-account-unit-pricing", "u-11800a"], {
        plan: { code: "RES-STD", name: "Residential Standard", version: 3, base_charges: "20.000000" },
      });
      return renderToStaticMarkup(
        <TenantRegionalProvider
          value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY", currency }}
        >
          <QueryClientProvider client={queryClient}>
            <UnitRecordPanel picked={unit()} t={(key, params) => i18n.t(key, params)} />
          </QueryClientProvider>
        </TenantRegionalProvider>,
      );
    };
    const usd = panel("USD");
    expect(usd).toContain("$20.00");
    expect(usd).not.toContain("20.000000");
    // Nothing published: the right number of places and NO invented symbol.
    const unknown = panel(null);
    expect(unknown).toContain("20.00");
    expect(unknown).not.toContain("$");
  });

  it("US-CUS-003 §5 / BR-CUS-059 / BR-CUS-060: step 3 offers only what the account can hold", () => {
    // Step 3 since `c107eaae7` (it was 4 when the plan step stood before it).
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=3`, { access: "Full" });
    expect(html).toContain("Step 3 of 5 · Account preferences");
    expect(html).toContain('id="autopay"');
    // American English since `d351e5fee` (DEF-SHL-6351): *enrollment*.
    expect(html).toContain("Autopay is recorded as an enrollment only.");
    expect(html).toContain('id="preferred_language"');
    expect(html).toContain('id="tax_exempt"');
    // The two genuinely unbuilt preferences and the DROPPED delivery day:
    // named, not drawn as switches that save nowhere.
    expect(html).not.toContain('id="budget_billing"');
    expect(html).not.toContain('id="bill_delivery_day"');
    // Reworded `bc81fea4f` (2026-09-13); the fact is unchanged: the day is
    // never coming, because cycles decide bill dates (BR-CUS-060).
    expect(html).toContain("Bill delivery day is not coming: cycles decide bill dates.");
    // ⛔ **`paperless` AND `sms_reminders` ARE NO LONGER ASSERTED ABSENT HERE,
    // AND THEY ARE NOT ASSERTED PRESENT EITHER.** Both columns are writable
    // (`customers 0034`, 2026-08-31) and `CR-094-BRC01` wave H collects them on
    // the MOVE-IN's *Account preferences* step, which is the step the PO ruled
    // on. The blueprint redraws THIS wizard as five steps with an *Account
    // preferences* step of its own, and that step-count change is a different
    // ruled item in the same CR. Pinning either direction here would decide it
    // by test — so the absence is left unasserted and stated instead.
  });

  it("PO 2026-09-12: step 4 COLLECTS the deposit, through the shared capability", () => {
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL TODAY** — *"step 5 collects
    // nothing and names both refusals"* — and it was green on the bug. The
    // engine it refused over (`purpose="deposit"` → 2300 → `BR-CUS-670`'s
    // register) shipped on 2026-08-27; the step said *"the plan's deposit
    // schedule and the deposit path that writes it … both arrive with the
    // deposit work"*. `DEF-1840`'s shape: a test written from the same
    // misunderstanding as the code cannot catch it.
    // Step 4 since `c107eaae7`. ⚠ **AND SINCE `39d6ee638` (2026-09-23) THE
    // SHARED STEP ASKS FOR THE UNIT AND THE CATEGORY FIRST** — the deposit is
    // the PLAN's figure for that category, so with no unit picked (a static
    // render cannot pick one) the shared capability says what it needs rather
    // than offering a decision over no figure. Its decision control, with a
    // unit and a category, is asserted in `depositCapability.test.tsx`.
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=4`, { access: "Full" });
    expect(html).toContain("Step 4 of 5 · Deposit");
    expect(html).toContain("Choose the unit and category first.");
    expect(html).not.toContain("Deposit &amp; credit.");
    expect(html).not.toContain("Nothing will be recorded");
    // ⛔ **AND NOTHING ELSE IS DRAWN YET, WHICH IS THE CORRECT ANSWER.** A
    // fresh form says *"No"* to the deposit, so there is no amount, no tender
    // and no credit-tier note over an account that owes nothing (rule 32's
    // description budget). The credit-tier absence — `BR-CUS-058`, the tier is
    // COMPUTED and has no input path — appears once a deposit IS required, and
    // is asserted there: `depositCapability.test.tsx`.
    expect(html).not.toContain('id="deposit_amount"');
    expect(html).not.toContain("BR-CUS-058");
    // ⛔ The carry-forward question is the MOVE-IN's alone (blueprint page 71):
    // a counter sign-up has no previous tenancy to carry a deposit from.
    expect(html).not.toContain("BR-CUS-024");
  });

  it("US-CUS-003 TC-4 / BR-CUS-018 / BR-SHL-019: the review step chooses draft or activate, and there is exactly ONE commit", () => {
    // Step 5 since `c107eaae7`.
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=5`, { access: "Full" });
    expect(html).toContain("Step 5 of 5 · Review");
    expect([...CREATE_MODES]).toEqual(["activate", "draft"]);
    expect(html).toContain("Create and activate");
    expect(html).toContain("Save as a draft");
    // BR-TEN-035: the number is allocated at save, so none is shown before it.
    expect(html).toContain("Allocated when you save");
    expect(html).not.toContain("A-12048");
    // BR-SHL-019: the frame's ✓ is the only commit on the page.
    expect((html.match(/data-variant="primary"/g) ?? []).length).toBe(1);
    expect(html).toContain("Create &amp; activate ✓");
  });

  it("DEF-CUS-9505: the review shows the deposit the Deposit step took — the same form, so they cannot disagree", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, SERVED_CATEGORIES);
    const review = (deposit: ReturnType<typeof emptyDepositForm>) =>
      renderToStaticMarkup(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <NewAccountReviewStep
              customer={CUSTOMER}
              unit={{ unit_id: "", opened_at: "" }}
              preferences={emptyPreferencesForm()}
              deposit={deposit}
              picked={null}
              mode="activate"
              created={null}
              dateFormat="MM/DD/YYYY"
              onEdit={() => undefined}
              onMode={() => undefined}
              t={(key, params) => i18n.t(key, params) as string}
            />
          </MemoryRouter>
        </QueryClientProvider>,
      );
    const taken = review({ ...emptyDepositForm(), decision: "required", amount: "150.00" });
    expect(taken).toContain("Yes — take one");
    // The amount row is drawn. Mounted with NO shell above it, nothing has
    // published the tenant's currency, so the figure is the stated absence —
    // never a defaulted `USD` (`DEF-CUS-5114`'s other half is the test below).
    expect(taken).toContain(i18n.t("customers.deposit.field.amount") as string);
    expect(taken).toContain(i18n.t("customers.deposit.totals.currencyAbsent") as string);
    const none = review(emptyDepositForm());
    expect(none).toContain("No deposit on this plan.");
  });

  it("DEF-CUS-5114: under the shell, the review reads the TENANT's currency — $600.00, not the absence", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, SERVED_CATEGORIES);
    const html = renderToStaticMarkup(
      <TenantRegionalProvider
        value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY", currency: "USD" }}
      >
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <NewAccountReviewStep
              customer={CUSTOMER}
              unit={{ unit_id: "", opened_at: "" }}
              preferences={emptyPreferencesForm()}
              deposit={{ ...emptyDepositForm(), decision: "required", amount: "600.0000" }}
              picked={null}
              mode="activate"
              created={null}
              dateFormat="MM/DD/YYYY"
              onEdit={() => undefined}
              onMode={() => undefined}
              t={(key, params) => i18n.t(key, params) as string}
            />
          </MemoryRouter>
        </QueryClientProvider>
      </TenantRegionalProvider>,
    );
    expect(html).toContain("$600.00");
    expect(html).not.toContain(i18n.t("customers.deposit.totals.currencyAbsent") as string);
  });

  it("US-CUS-003 §1: the review step names what the create will NOT write", () => {
    const html = renderWizard(`${ACCOUNT_NEW_ROUTE}?step=5`, { access: "Full" });
    expect(html).toContain("What this create will not write");
    // ⚠ *a deposit* LEFT this sentence when the wizard began COLLECTING one
    // (PO 2026-09-12, `e009d2eab`): the create now writes the deposit if one
    // was taken, and says so in the sentence before.
    expect(html).toContain("It does not write a plan snapshot, an initial meter read");
    expect(html).toContain("and the deposit if one was taken");
  });

  it("US-CUS-003 §RBAC / BR-SHL-025: a View role sees the flow with the reason, and a '—' cell sees nothing", () => {
    const viewOnly = renderWizard(ACCOUNT_NEW_ROUTE, { units: unitsPage([unit()]), access: "View" });
    expect(viewOnly).toContain("Your role can view accounts but not change them.");
    expect(viewOnly).toContain('data-wizard="frame"');

    const denied = renderWizard(ACCOUNT_NEW_ROUTE, { units: unitsPage([unit()]), access: "—" });
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain('data-wizard="frame"');
  });

  it("US-CUS-003 §5 / BR-SHL-011: an out-of-range or non-numeric ?step= clamps rather than erroring", () => {
    expect(stepFromParam(null)).toBe(1);
    expect(stepFromParam("3")).toBe(3);
    expect(stepFromParam("0")).toBe(1);
    expect(stepFromParam("99")).toBe(5);
    expect(stepFromParam("banana")).toBe(1);
  });

  it("US-CUS-003 TC-1 §5: the payload is EXACTLY the field set the endpoint accepts", () => {
    const payload = createAccountPayload({
      customer: CUSTOMER,
      unit: { unit_id: "u-11800a", opened_at: "2026-08-15" },
      preferences: { ...emptyPreferencesForm(), autopay: true },
      mode: "activate",
    });
    expect(payload).toEqual({
      unit_id: "u-11800a",
      account_type: "residential",
      status: "active",
      opened_at: "2026-08-15",
      autopay: true,
      tax_exempt: false,
      // `BR-CUS-028` + `BR-BIL-036` — the two delivery elections, sent
      // UNCONDITIONALLY because `false` is a real answer: "not paperless" is a
      // preference, not an absent value. Writable since `customers 0034`
      // (2026-08-31) and collected on the wizard since `CR-094-BRC01` wave H.
      paperless: false,
      sms_reminders: false,
      // `DEF-CUS-9191` — the utility's own account fields travel EMPTY too, so
      // a required one drawn on this wizard and left blank is checked.
      custom_data: {},
      contact: {
        full_name: "Elena Rivera",
        email: "elena.rivera@example.com",
        phone: "+1 (281) 555-0100",
        dob: "1991-03-18",
        gov_id_last4: "4218",
        is_primary: true,
      },
      // ⚠ **THE `customer` BLOCK JOINED 2026-09-01, AND THIS SCREEN SENT NONE
      // UNTIL THEN (`BR-CUS-1023`, `DEF-2818`).** The server has accepted one
      // since `CR-056` W3 and nothing posted it, so every account opened here
      // had a blank customer column. `kind` is ABSENT because this fixture
      // states none — an unstated kind mints no number and says so, and a
      // default would hide that. `custom_data` (`CR-161-BRC10` W4) is the
      // utility's own CUSTOMER fields, sent EMPTY too for `DEF-CUS-9191`'s
      // reason: a required one drawn on this wizard and left blank is checked.
      customer: { display_name: "Elena Rivera", custom_data: {} },
    });
  });

  it("BR-CUS-1023: the block carries the kind and ONLY that kind's identifiers", () => {
    // A PERSON — the SSN, the licence, the date of birth and the phone.
    const person = createAccountPayload({
      customer: {
        ...CUSTOMER,
        customer_kind: "person",
        ssn: " 123-45-6789 ",
        driving_licence: "TX-4417",
        tax_id: "12-3456789",
      },
      unit: { unit_id: "u-1", opened_at: "2026-08-15" },
      preferences: emptyPreferencesForm(),
      mode: "activate",
    });
    expect(person.customer).toEqual({
      display_name: "Elena Rivera",
      kind: "person",
      identity: {
        ssn: "123-45-6789",
        driving_licence: "TX-4417",
        date_of_birth: "1991-03-18",
        phone: "+1 (281) 555-0100",
      },
      custom_data: {},
    });

    // A COMPANY — the Tax ID and the phone, and NEVER the person's fields.
    // The server refuses a borrowed field BY NAME, so sending one would refuse
    // the whole create rather than being ignored (`BR-CUS-1022`).
    const company = createAccountPayload({
      customer: {
        ...CUSTOMER,
        customer_kind: "company",
        ssn: "123-45-6789",
        driving_licence: "TX-4417",
        tax_id: " 12-3456789 ",
      },
      unit: { unit_id: "u-1", opened_at: "2026-08-15" },
      preferences: emptyPreferencesForm(),
      mode: "activate",
    });
    expect(company.customer).toEqual({
      display_name: "Elena Rivera",
      kind: "company",
      identity: { tax_id: "12-3456789", phone: "+1 (281) 555-0100" },
      custom_data: {},
    });
  });

  it("BR-CUS-1023: every sentence the shortfall points at exists in the catalogue", async () => {
    // ⚠ **A KEY THAT RESOLVES TO NOTHING RENDERS AS SILENCE.** The PO ruling of
    // 2026-08-19 suppresses server `detail` text, so an unresolved key here is
    // a clerk who is told nothing at all about why no number was made. These
    // are the SAME four keys `identity_match.NOT_CREATED_MESSAGE_KEY` sends,
    // so this is the client half of one contract; the backend asserts its own.
    const en = (await import("@/i18n/locales/en.json")).default as Record<string, string>;
    for (const key of [
      "customers.customer.display_name_required",
      "customers.customer.identity_kind_required",
      "customers.customer.identity_required_person",
      "customers.customer.identity_required_company",
    ]) {
      expect(en[key], key).toBeTruthy();
      // B14 rule 32 clause 4 — no rule id and no internal code in clerk copy.
      expect(en[key]).not.toMatch(/BR-|DEF-|OQ-|customer_/);
    }
  });

  it("BR-CUS-1023: the shortfall names the missing thing, per kind, and a name alone is not enough", () => {
    expect(customerNumberShortfall(emptyCustomerForm())).toBe(
      "customers.customer.display_name_required",
    );
    expect(customerNumberShortfall(CUSTOMER)).toBe(
      "customers.customer.identity_kind_required",
    );
    // A PHONE CREATES A PERSON — the PO named it. `CUSTOMER` already has one.
    expect(customerNumberShortfall({ ...CUSTOMER, customer_kind: "person" })).toBeNull();
    expect(
      customerNumberShortfall({ ...CUSTOMER, customer_kind: "person", phone: "" }),
    ).toBe("customers.customer.identity_required_person");
    // AND A PHONE DOES NOT CREATE A COMPANY — the PO's list for a business
    // names the Tax ID and nothing else.
    expect(customerNumberShortfall({ ...CUSTOMER, customer_kind: "company" })).toBe(
      "customers.customer.identity_required_company",
    );
    expect(
      customerNumberShortfall({ ...CUSTOMER, customer_kind: "company", tax_id: "12-3456789" }),
    ).toBeNull();
  });

  it("US-CUS-003 §5: no refused field can reach the wire, whatever is typed", () => {
    const payload = createAccountPayload({
      customer: {
        ...CUSTOMER,
        // `DEF-CUS-6359` — a mailing address is written only with *Same as
        // service address* UNTICKED; ticked (the default) writes none.
        mailing_same: false,
        mailing_line1: "PO Box 88",
        mailing_city: "Katy",
      },
      unit: { unit_id: "u-11800a", opened_at: "2026-08-15" },
      preferences: {
        autopay: true,
        // `CR-094-BRC01` wave H — `BR-CUS-028`'s two delivery elections, in
        // `PreferencesForm` since the refusal on both columns expired.
        paperless: true,
        sms_reminders: false,
        preferred_language: " es ",
        tax_exempt: true,
        tax_exempt_ref: "TX-4491",
        tax_exempt_expires: "2027-01-01",
        custom_data: {},
      },
      mode: "activate",
    });
    // `services.REFUSED_FIELDS` — each of these fails the WHOLE create if sent.
    for (const refused of [
      "plan",
      "rate_plan_id",
      "plan_version",
      // ⚠ **`customer` LEFT THIS LIST ON 2026-09-01 AND THE LIST WAS ALREADY
      // WRONG.** `services.CREATE_FIELDS` has accepted a `customer` block
      // since `CR-056` W3 (2026-08-31); this line kept asserting the refusal
      // that existed before it, which is why nothing noticed that the screen
      // sent no block at all (`DEF-2818`). `customer_id` IS still refused at
      // the top level — the clerk's chosen customer travels INSIDE the block.
      "customer_id",
      "deposit_on_file",
      "deposit_received_on",
      "deposit_election",
      "credit_tier",
      // ⛔ **`paperless` AND `sms_reminders` LEFT THIS LIST ON 2026-09-12
      // (`CR-094-BRC01` wave H).** They were removed from
      // `services.REFUSED_FIELDS` on 2026-08-31 (`CR-052` task 14, migration
      // `customers 0034`) and have been in `CREATE_FIELDS` AND `PATCH_FIELDS`
      // ever since; the SCREENS went on refusing them for twelve days. A test
      // that pins an expired refusal is green on the bug — `DEF-1840`'s shape —
      // so the entries are deleted rather than reworded (hard-won law 1).
      "budget_billing",
      "statement_language",
      "bill_delivery_day",
      "initial_reads",
      "account_no",
      "balance",
      "currency",
      "closed_at",
    ]) {
      expect(payload).not.toHaveProperty(refused);
    }
    // What IS accepted travels trimmed, and the mailing address is a real row.
    expect(payload.preferred_language).toBe("es");
    expect(payload.tax_exempt_ref).toBe("TX-4491");
    expect(payload.addresses).toEqual([
      { kind: "mailing", line1: "PO Box 88", city: "Katy", state: "", postal_code: "" },
    ]);
  });

  it("US-CUS-003 TC-4 / BR-CUS-018: the draft mode sends the pending status, and an empty contact sends none", () => {
    const draft = createAccountPayload({
      customer: emptyCustomerForm(),
      unit: { unit_id: "u-11800a", opened_at: "" },
      preferences: emptyPreferencesForm(),
      mode: "draft",
    });
    expect(draft.status).toBe("pending_activation");
    // B2 §2: no mailing row means "same as service" — an address of empty
    // strings would be a different, and wrong, claim.
    expect(draft).not.toHaveProperty("addresses");
    // The server requires `full_name` once a contact is sent, so an empty one
    // is omitted rather than posted as a nameless contact row.
    expect(draft).not.toHaveProperty("contact");
    // An unset start date is omitted, not sent as an empty string.
    expect(draft).not.toHaveProperty("opened_at");
  });

  it("US-CUS-003 §5 / BR-CUS-045: a longer government id is cut to its last four before it leaves the browser", () => {
    const payload = createAccountPayload({
      customer: { ...CUSTOMER, gov_id_last4: "123456789" },
      unit: { unit_id: "u-11800a", opened_at: "2026-08-15" },
      preferences: emptyPreferencesForm(),
      mode: "activate",
    });
    expect((payload.contact as Record<string, unknown>).gov_id_last4).toBe("6789");
  });

  it.todo(
    "US-CUS-003 TC-1: Continue through all six steps and commit — the click path needs a browser; each step's validate() and the payload are asserted statically above",
  );
  it.todo(
    "US-CUS-003 TC-3: a plan override writes back to the unit's assignment history — no plan field exists, because the account plan table does not (BR-CUS-029)",
  );
  it.todo(
    "US-CUS-003 TC-7 (negative): a backdated start with an AMI pull is refused — there is no initial-read control to refuse (BR-CUS-021)",
  );
  it.todo(
    "US-CUS-003 TC-8 (isolation): a Lone Star Ridge session sees only its own units and creates only its own rows — server/RLS scope (G5)",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-003@bbed56d (story+rules snapshot — EP-CUS-02 lead story for the write path)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 2 — S18)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔
// exceptions: E4 TC-1's full six-step walk and the commit itself need a browser (the frame's Continue is a click): every step's fields, every refusal and the exact payload are asserted statically instead, which is where the defects would be · E4 TC-3 (plan override → unit assignment history) cannot be asserted at all — no plan field exists because BR-CUS-029's table does not · E4 TC-7's backdated-start-with-AMI-pull refusal has no control to refuse: initial reads are metering's (BR-CUS-021) · E4 TC-8 is server/RLS scope (G5) · E4 the step-3 "unit has no plan" refusal renders only once a unit is picked, which a static render cannot do — the pick-a-unit-first branch is asserted here and the BR-MET-040 refusal itself is the server's, surfaced through the frame's A18 §4 card
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
