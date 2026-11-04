// ── Trace ──────────────────────────────────────────────
// Change:   CR-013 P2 — the shared DEFINITION DETAIL, rows 8 · 11 · 14
//           Screens: CHG-01 · CHG-01.discount · CHG-01.tax
// Rules:    BR-RAT-084 (ONE component, THREE routes, THREE screen ids; tab
//           counts 5 · 5 · 6; four KPI tiles that differ per kind) ·
//           BR-RAT-087 / DEF-364 (the SERVER's `*_display` string reaches the
//           screen and the stored fraction never does) · BR-SHL-011 (the open
//           tab is URL state) · BR-SHL-025 (a control is disabled WITH its
//           reason) · `09-screen-inventory.md` §2 · §10 · §18
// ───────────────────────────────────────────────────────
//
// THE POINT OF THIS SUITE IS THAT ALL THREE KINDS GO THROUGH ONE SHELL. Every
// case below renders `DefinitionDetailPage` with a different `kind` and asserts
// the thing BR-RAT-084 says must NOT collapse: three routes, three ids, three
// tab sets, three sets of four tiles. A refactor that "simplifies" the three
// into one tab list fails here rather than on a screenshot.
//
// The two load-bearing absences, asserted rather than commented:
//
//   · **The Versions tab is not `audit_log`** (§10). The source is read as text
//     and checked for any audit reference, because the wrong implementation is
//     the plausible one and it would pass every rendering assertion.
//   · **The raw stored value never reaches the screen** (DEF-364). `0.062500`
//     and `0.015000` are searched for in the rendered markup by hand — the two
//     exact strings a customer read for nine days.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  ChargeReachRow,
  ChargeRow,
  DiscountDetail,
  GlAccountRef,
  MyPermissions,
  TaxRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { resolveScreen } from "@/routing/screenIds";

import appSource from "@/App.tsx?raw";

import {
  DefinitionDetailPage,
  EDITABLE_KINDS,
  HELD_ACTION_SEGMENTS,
  definitionTabFrom,
} from "./DefinitionDetailPage";
import type { KpiTile } from "../../components/KPIStrip";
import type { DefinitionKpis } from "./definitionDetail";
import {
  DEFINITION_KINDS,
  DEFINITION_KPI_LABEL_KEYS,
  DEFINITION_ROUTES,
  DEFINITION_TABS,
  DEFINITION_TAB_IDS,
  definitionIsServed,
  definitionPath,
  emptyKpis,
  isHistoryTab,
  presentCharge,
  presentDiscount,
  presentTax,
} from "./definitionDetail";
import type {
  DefinitionKind,
  DefinitionPresentation,
  DefinitionRegional,
} from "./definitionDetail";
import type { Translator } from "./ratingShared";

// §10 is a build instruction, so the file itself is evidence — see the suite at
// the bottom.
import pageSource from "./DefinitionDetailPage.tsx?raw";
import configSource from "./definitionDetail.tsx?raw";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t: Translator = (key, params) => i18n.t(key, params);

/**
 * A catalog string as it appears in `renderToStaticMarkup`'s output.
 *
 * ⚠ WITHOUT THIS, HALF THE COPY ASSERTIONS BELOW ARE UNWRITABLE AND THE OTHER
 * HALF ARE ACCIDENTS. React escapes `&`, `<`, `>`, `"` and `'` in text nodes,
 * so `Value & rules` is `Value &amp; rules` in the markup and a plain
 * `toContain` on the catalog value fails — while a key with no punctuation
 * passes and looks like proof. Escaping the EXPECTED side keeps the assertion
 * pointed at the catalog rather than at a hand-typed copy of it.
 */
function shown(key: string): string {
  return i18n
    .t(key)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}
const REGIONAL: DefinitionRegional = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

const ACCOUNTS: GlAccountRef[] = [
  // r10 draws 4200 on the charge detail and 2301 on the tax detail — a revenue
  // account against a liability one, which is CR-013 part 4's whole point.
  { id: "gl-4200", code: "4200", name: "Water base revenue" },
  { id: "gl-2301", code: "2301", name: "Local tax payable" },
];

// The US-RAT-008 §4 seed shape: stored precision AND the display strings the
// server sends beside it (BR-RAT-087). A fixture carrying only one of the two
// could not tell a correct screen from DEF-364.
const BASE_W: ChargeRow = {
  id: "c-base-w",
  code: "BASE-W",
  name: "Water base service",
  charge_type: "recurring",
  service: "water",
  amount_rule: "flat",
  amount: "12.000000",
  percent: null,
  min_amount: null,
  max_amount: null,
  amount_display: "12.00",
  percent_display: null,
  min_amount_display: null,
  max_amount_display: null,
  gl_account_id: "gl-4200",
  // BR-RAT-088 (DEF-372): BASE-W IS the water base charge, and it says so
  // because a tenant DECLARED it — never because its code starts "BASE-".
  is_base: true,
  size_amounts: [], // DEF-431 — no per-size base rows on this fixture
  taxable_default: true,
  auto_apply: true,
  waivable: false,
  separate_line: true,
  status: "active",
  used_by_plans: 4,
  used_by_invoice_lines: 915,
};

const LATE: ChargeRow = {
  ...BASE_W,
  id: "c-late",
  code: "LATE",
  name: "Late fee",
  charge_type: "penalty",
  service: null, // BR-RAT-035: account-level, so "Any service" is the answer
  amount_rule: "percent_with_minimum",
  amount: null,
  percent: "0.015000",
  min_amount: "5.000000",
  amount_display: null,
  percent_display: "1.50%",
  min_amount_display: "5.00",
  taxable_default: false,
  used_by_plans: 2,
};

const BEXAR: TaxRow = {
  ...taxRowDefaults(),
  id: "tax-bexar",
  name: "Bexar County local tax",
  jurisdiction: {
    id: "j-bexar",
    name: "Bexar County",
    authority: "Bexar County",
    level: "county",
    reference_no: null,
  },
  kind: "percent",
  rate: "0.062500",
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
  applies_to_services: ["water"],
  // r10 draws Bexar County as *"Customer class · All · No residential
  // exemption at county level"*, so the inclusion list is empty — and the
  // county scope is the mechanism a bill run cannot resolve today.
  applies_to_customer_classes: [],
  premises_scope_kind: "county",
  premises_scope_value: "Bexar County",
  liability_gl_account_id: "gl-2301",
  remit_to: "Bexar County",
  filing_frequency: "monthly",
  filing_form: null,
  effective_from: "2026-08-01",
  effective_to: null,
  status: "active",
  used_by_plans: 5,
};

/**
 * r10's own SENIOR row, as `GET /discounts/{id}` serves it (CR-013 part 3).
 *
 * ⚠ THE TWO FIGURES THIS FIXTURE EXISTS TO PIN. `value` is `15.000000` and
 * `value_display` is `"15.00%"` — a discount stores PERCENTAGE POINTS where
 * `charges.percent` stores a fraction, so a screen that scaled this itself
 * would render `1500.00%`. And `cap_per_bill` is `null`, not `"0.00"`:
 * BR-RAT-075 makes a null cap UNCAPPED, which is the opposite fact from a cap
 * of zero. Both are asserted below rather than merely carried.
 */
const SENIOR: DiscountDetail = {
  id: "d-senior",
  code: "SENIOR",
  name: "Senior discount",
  type: "percentage",
  value: "15.000000",
  value_display: "15.00%",
  currency: "USD",
  eligibility: "Age 65+",
  verification: "annual_recertification",
  // ⚠ AVAILABLE (3) IS NOT GRANTED (72) — BR-RAT-069, and the whole reason the
  // two counts are two columns.
  plans: 3,
  enrolled: 72,
  status: "active",
  programme_owner: "Customer service",
  funding_source: "Rate-payer funded",
  // CR-066 table 3 — where this discount posts. `null` is the honest fixture
  // value: nothing has overridden the `discount_contra_revenue` designation.
  gl_account_id: null,
  applies_to: "whole_bill",
  effective_from: "2026-01-01",
  version_no: 2,
  version_status: "active",
  version_id: "0198c1aa-0000-7000-8000-00000000ac71",
  report_in_assistance_filing: true,
  funding_exhausted_at: null,
  granted_to_date: "0.000000",
  granted_to_date_display: "0.00",
  effective_to: null,
  applies_to_service: null,
  applies_to_charge_codes: [],
  cap_per_bill: null,
  cap_per_bill_display: null,
  cap_per_year: null,
  cap_per_year_display: null,
  cap_lifetime: null,
  cap_lifetime_display: null,
  bill_floor_amount: "0.000000",
  bill_floor_amount_display: "0.00",
  stacking_precedence: 10,
  stacks_with_others: true,
  exclusivity_group: "assistance",
  enrolment_mode: "apply_and_approve",
  proof_required: true,
  accepted_proof_kinds: ["government_id", "birth_certificate"],
  proof_before_first_reduction: true,
  recertification_months: 12,
  recertification_notice_days: 60,
  recertification_grace_days: 0,
  lapse_behaviour: "notify_then_drop",
  budget_cap: "12312.000000",
  budget_cap_display: "12312.00",
  budget_period: "annual",
  exhaustion_behaviour: "suspend",
  budget_remaining: "12312.000000",
  budget_remaining_display: "12312.00",
  second_approval_required: true,
  second_approval_threshold: "10000.000000",
  second_approval_threshold_display: "10000.00",
  self_approved: false,
  change_reason: "Raised from -10% to -15%",
};

/** A CHARGE WAIVER, which is the row that proves the em-dash rule. Its stored
 *  `value` is a zero the column requires and its `value_display` is NULL,
 *  because a waiver removes the whole of what its scope selected and never
 *  reads the value — `0.00` on screen would say the utility waives nothing. */
const WAIVER: DiscountDetail = {
  ...SENIOR,
  id: "d-waiver",
  code: "WAIVE-BASE",
  name: "Base charge waived",
  type: "charge_waiver",
  value: "0.000000",
  value_display: null,
  eligibility: null,
  applies_to: "base_only",
  plans: 0,
  enrolled: 0,
  status: "draft",
  version_status: "draft",
  version_id: "0198c1aa-0000-7000-8000-00000000d411",
  budget_cap: null,
  budget_cap_display: null,
  budget_remaining: null,
  budget_remaining_display: null,
  recertification_months: null,
  accepted_proof_kinds: [],
};


function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access }],
  };
}

interface Seed {
  access?: string;
  charge?: ChargeRow;
  tax?: TaxRow;
  discount?: DiscountDetail;
  /** The `?tab=` the browser would be showing. */
  tab?: string;
  /** CR-087 — one page of `GET /charges/{id}/plans`, already in the cache. */
  chargePlans?: ChargeReachRow[];
}

/**
 * Renders one kind of the shared shell with its answers already in the cache.
 *
 * The route is mounted at its REAL pattern rather than bare, because the id is
 * a URL segment: rendering the page without it would leave `definitionId` empty
 * and every case would quietly assert against a screen that fetched nothing.
 */
function renderDetail(kind: DefinitionKind, id: string, seed: Seed = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access ?? "Full"));
  queryClient.setQueryData(queryKeys.ledgerAccounts, ACCOUNTS);
  if (seed.charge !== undefined) {
    queryClient.setQueryData(queryKeys.charge(id), seed.charge);
  }
  if (seed.tax !== undefined) {
    queryClient.setQueryData(queryKeys.tax(id), seed.tax);
  }
  if (seed.discount !== undefined) {
    queryClient.setQueryData(queryKeys.discount(id), seed.discount);
  }
  if (seed.chargePlans !== undefined) {
    // ⚠ THE ENVELOPE, NOT THE ROWS. `count` is the WHOLE set (NFR-3), and a
    // fixture that handed the component a bare array would let a pager fed the
    // page's own length pass — which is the exact defect the served count
    // exists to prevent.
    queryClient.setQueryData(queryKeys.chargePlans(id, 1), {
      count: seed.chargePlans.length,
      next: null,
      previous: null,
      results: seed.chargePlans,
    });
  }
  const pattern = `/${TEST_TENANT}/plans-rates/${DEFINITION_ROUTES[kind].segment}/:definitionId`;
  const url =
    `/${TEST_TENANT}${definitionPath(kind, id)}` +
    (seed.tab === undefined ? "" : `?tab=${seed.tab}`);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route
              path={pattern}
              element={
                <DefinitionDetailPage
                  kind={kind}
                  timeZone={REGIONAL.timeZone}
                  dateFormat={REGIONAL.dateFormat}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ── BR-RAT-084 · one component, three surfaces ─────────────────────────────

describe("BR-RAT-084 — ONE component, THREE routes, THREE screen ids", () => {
  it("all three kinds render through the same component, and the component is one file", () => {
    // The reduction the PO authorised is in FILES. Three renders, one import.
    const html = DEFINITION_KINDS.map((kind) =>
      renderDetail(kind, "x", { charge: BASE_W, tax: BEXAR, discount: SENIOR }),
    );
    expect(html).toHaveLength(3);
    for (const markup of html) {
      expect(markup).toMatch(/<h1[\s>]/);
    }
  });

  it("each of the three routes resolves to a DISTINCT screen id — the enumeration survives the reduction", () => {
    const ids = DEFINITION_KINDS.map(
      (kind) => resolveScreen(`/${TEST_TENANT}${definitionPath(kind, "x")}`).r10,
    );
    expect(ids).toEqual(["CHG-01", "CHG-01.discount", "CHG-01.tax"]);
    // Distinct is the whole ruling: a walkthrough evidences each one.
    expect(new Set(ids).size).toBe(3);
  });

  it("a deep link resolves for every kind, and the three paths are spelled in ONE place", () => {
    expect(definitionPath("charge", "c-1")).toBe("/plans-rates/charge-codes/c-1");
    expect(definitionPath("discount", "d-1")).toBe("/plans-rates/discounts/d-1");
    expect(definitionPath("tax", "t-1")).toBe("/plans-rates/taxes-fees/t-1");
    // An id with a slash or a space cannot break the route.
    expect(definitionPath("charge", "a b/c")).toBe("/plans-rates/charge-codes/a%20b%2Fc");
  });

  it("§2 part 7 / CR-087 B2: the counts are 5 · 5 · 3 and the shell does NOT normalise them", () => {
    // ⚠ THE TAX READ SIX UNTIL 2026-09-08 and this case asserted it. PO ruling
    // of that date, verbatim: *"overview and Remittance & filings - you can
    // merge it in Overview only"*. FOUR tabs — overview, basis, applicability,
    // remittance — answered ONE question about one object, so a clerk with a
    // customer on the phone clicked three times to read a rate, what it was
    // charged on and who it reached. They are five BLOCKS of one Overview now.
    // BR-RAT-084's *"the shell must not force them to be"* identical is what
    // this case still exists to guard, and the three counts differing by MORE
    // than they used to is that rule holding rather than breaking.
    expect(DEFINITION_TABS.charge).toHaveLength(5);
    // ⚠ **THE DISCOUNT WENT FIVE → THREE IN THE SAME HOUR THE TAX WENT SIX →
    // THREE (CR-087 C2).** Same ruling, same mechanism: Overview, `Value &
    // rules` and `Applicability` answered ONE question — what is this, what is
    // it worth, who qualifies — so a clerk on the phone opened all three to
    // answer one caller. They are three BLOCKS of one Overview now.
    expect(DEFINITION_TABS.discount).toEqual(["overview", "plans", "audit"]);
    expect(DEFINITION_TABS.tax).toHaveLength(3);
    // The second tab is a DIFFERENT tab on each kind — that is the ruling's
    // "the three are not identical", not a naming accident. On the two merged
    // kinds it is Plans, because what used to sit there folded into Overview.
    expect([
      DEFINITION_TABS.charge[1],
      DEFINITION_TABS.discount[1],
      DEFINITION_TABS.tax[1],
    ]).toEqual(["amounts", "plans", "plans"]);
    // ⚠ NO KIND CARRIES A REMITTANCE TAB ANY MORE, and the fields did not go
    // with it: they are read in the Overview's own `remittance` block and
    // entered in the form under it (`TaxRemittancePanel`).
    for (const kind of DEFINITION_KINDS) {
      expect(DEFINITION_TABS[kind]).not.toContain("remittance");
      // ⚠ EVERY KIND ENDS ON ITS HISTORY TAB, AND THE TWO SPELLINGS ARE A
      // MIGRATION IN PROGRESS. This line asserted `"versions"` under a comment
      // that already said *"Every kind ends on Audit"* — the comment was ahead
      // of the code by one lane. `audit` is the name every other module in the
      // product uses (assets, premises, units, accounts, bills, cycles, routes,
      // work templates); the discount moved first and the other two follow.
      expect(isHistoryTab(DEFINITION_TABS[kind][DEFINITION_TABS[kind].length - 1])).toBe(true);
    }
  });

  it("⚠ CR-087 C2 — the discount's last tab is `audit`, and it still draws VERSIONS", () => {
    expect(DEFINITION_TABS.discount).toContain("audit");
    expect(DEFINITION_TABS.discount).not.toContain("versions");
    expect(isHistoryTab("audit")).toBe(true);
    expect(isHistoryTab("versions")).toBe(true);
    expect(isHistoryTab("plans")).toBe(false);
    // ⚠ RENAMING THE TAB RENAMED THE TAB. A version row is a priced state a
    // bill can resolve to, with a CHANGE sentence a person wrote; an audit row
    // is an actor plus an action plus a timestamp and the engine never reads
    // one. The source-as-text guard further down this file is what keeps the
    // plausible wrong implementation out, and it is untouched.
  });

  it("every declared tab has a LABEL and a PANEL HEADING in the catalogue — a missing key renders the key", () => {
    // The union of the three tab lists, and the catalogue answering for each.
    // This is G15's defect class one level down: i18next renders the KEY when a
    // lookup misses, so a sixth tab added without its two strings ships a tab
    // reading `rating.definition.tab.exemptions` to a customer.
    // ⚠ `DEFINITION_TAB_IDS` IS A SUPERSET SINCE CR-087, DELIBERATELY. `basis`,
    // `applicability` and `remittance` are no kind's tab any more, and their
    // strings are KEPT: a fourth kind will want them, the panel headings are
    // reused as the tax Overview's own block titles, and deleting a key from
    // eleven catalogues to save three lines is a mass shared-file rewrite for
    // no gain. What must still hold is the direction that catches the real
    // defect — every DECLARED tab has both its strings.
    const declared = new Set(DEFINITION_KINDS.flatMap((kind) => DEFINITION_TABS[kind]));
    for (const tab of declared) {
      expect(DEFINITION_TAB_IDS).toContain(tab);
    }
    for (const tab of DEFINITION_TAB_IDS) {
      for (const stem of ["rating.definition.tab", "rating.definition.panel"]) {
        expect(i18n.t(`${stem}.${tab}`)).not.toBe(`${stem}.${tab}`);
      }
    }
  });

  it("the rendered tab strip carries the kind's own tabs — THREE for the tax, five for the others", () => {
    const charge = renderDetail("charge", BASE_W.id, { charge: BASE_W });
    expect(charge).toContain(shown("rating.definition.tab.amounts"));
    expect(charge).not.toContain(shown("rating.definition.tab.remittance"));

    const tax = renderDetail("tax", BEXAR.id, { tax: BEXAR });
    // Overview · Plans · Audit, and nothing else.
    expect(tax).toContain(shown("rating.definition.tab.overview"));
    expect(tax).toContain(shown("rating.definition.tab.plans"));
    // ⚠ THIS ASSERTED `tab.versions` AND PASSED WHILE THE STRIP DREW *Audit*.
    // The word *Versions* is elsewhere on the page, so a check pointed at the
    // wrong string could not fail — law 7's *"ask what would make this check
    // pass wrongly"*. It reads the id the tax actually declares, and the whole
    // list is asserted beside it so the tab cannot move without saying so.
    expect(tax).toContain(shown("rating.definition.tab.audit"));
    expect(DEFINITION_TABS.tax).toEqual(["overview", "plans", "audit"]);
    expect(tax).not.toContain(shown("rating.definition.tab.basis"));
    expect(tax).not.toContain(shown("rating.definition.tab.applicability"));
    // ⚠ CR-165-BRC10 round 3 (task 6): the tax Overview's two blocks are the
    // redesign's *Rate and scope* and *On the bill and filing* (images 18–23);
    // filing is READ there, no longer entered under *Remittance & filings*.
    expect(tax).toContain(shown("rating.taxDetail.section.rateScope"));
    expect(tax).toContain(shown("rating.taxDetail.section.billFiling"));

    // CR-087 C2 — the discount is three too: Overview · Plans · Audit.
    const discount = renderDetail("discount", SENIOR.id, { discount: SENIOR });
    expect(discount).toContain(shown("rating.definition.tab.overview"));
    expect(discount).toContain(shown("rating.definition.tab.plans"));
    expect(discount).toContain(shown("rating.definition.tab.audit"));
    // The two that folded in are gone from the STRIP — asserted as absences,
    // because a merge that leaves the old tabs beside the new one is no merge.
    expect(discount).not.toContain(shown("rating.definition.tab.value"));
    expect(discount).not.toContain(shown("rating.definition.tab.applicability"));
    expect(discount).not.toContain(shown("rating.definition.tab.remittance"));
  });

});

// ── §2 part 6 · THE KPI tiles, different per kind ──────────────────────────

/** The tile at `index`, or a loud failure. The strip is a 3-or-4 tuple since
 *  the tax lost its duplicate status tile, so indexing past three is `undefined`
 *  to the type checker — and a test that reaches for a tile the kind does not
 *  have should SAY SO rather than be silenced with a `!` or a cast. */
function tileAt(kpis: DefinitionKpis, index: number): KpiTile {
  const tile = kpis[index];
  if (!tile) throw new Error(`this strip has no tile ${index + 1}`);
  return tile;
}

/** How many tiles each kind draws. ⚠ THE TAX IS THREE BY PO RULING of
 *  2026-09-10 — verbatim *"show only one status"*. The blueprint's §2 says
 *  "exactly four" and draws the tax status twice, as the pill AND as a tile;
 *  the ruling keeps the pill, which is where every other Plans & Rates detail
 *  screen carries a lifecycle word. Nothing was invented to refill the slot. */
const TILES_PER_KIND: Record<string, number> = { charge: 4, discount: 4, tax: 3 };

describe("§2 part 6 — the KPI tiles, and they differ per kind", () => {
  it("every kind declares its own tile labels, and no two kinds declare the same set", () => {
    for (const kind of DEFINITION_KINDS) {
      expect(DEFINITION_KPI_LABEL_KEYS[kind]).toHaveLength(TILES_PER_KIND[kind]);
      expect(emptyKpis(kind, t)).toHaveLength(TILES_PER_KIND[kind]);
    }
    const sets = DEFINITION_KINDS.map((kind) => DEFINITION_KPI_LABEL_KEYS[kind].join("|"));
    expect(new Set(sets).size).toBe(3);
  });

  it("tile 1 is always the reach, and it is the SERVER's count", () => {
    expect(presentCharge(BASE_W, t, ACCOUNTS).kpis[0].label).toBe(
      i18n.t("rating.definition.kpi.charge.plans"),
    );
    expect(presentCharge(BASE_W, t, ACCOUNTS).kpis[0]).toMatchObject({ value: 4 });
    expect(presentTax(BEXAR, t, ACCOUNTS, REGIONAL).kpis[0]).toMatchObject({ value: 5 });
  });

  it("the LAST tile is TEXT on the charge and a rate on the tax — §2's own distinction", () => {
    // "BASIS · Per size" on the drawing; per-size amounts are not stored yet
    // (DEF-356), so the basis is the amount RULE and it is still a WORD.
    const basis = tileAt(presentCharge(BASE_W, t, ACCOUNTS).kpis, 3);
    expect(basis.label).toBe(i18n.t("rating.definition.kpi.charge.basis"));
    expect(basis).toMatchObject({ value: i18n.t("rating.charges.amountRule.flat") });
    expect(typeof (basis as { value: unknown }).value).toBe("string");

    // ⚠ **THE RATE MOVED FROM SLOT 4 TO SLOT 3** when the duplicate status tile
    // went (PO, *"show only one status"*). It is still the LAST tile, which is
    // what §2's distinction is actually about, so the case is read by position
    // from the end of the strip rather than by a hard-coded 3.
    const taxKpis = presentTax(BEXAR, t, ACCOUNTS, REGIONAL).kpis;
    const rate = tileAt(taxKpis, taxKpis.length - 1);
    expect(rate.label).toBe(i18n.t("rating.definition.kpi.tax.rate"));
    expect(rate).toMatchObject({ value: expect.stringContaining("6.25%") });
  });

  it("the tax draws its status ONCE — the pill, not a tile (PO 2026-09-10)", () => {
    const taxKpis = presentTax(BEXAR, t, ACCOUNTS, REGIONAL).kpis;
    expect(taxKpis).toHaveLength(3);
    // ⚠ Asserted on the VALUE, not on the retired label key. The key is gone
    // from all eleven catalogues, so `t()` on it would return the key string
    // itself and the comparison would pass for the wrong reason — a check that
    // cannot fail. The status WORD is what a reader would see twice.
    const statusWord = i18n.t(`rating.status.${BEXAR.status}`);
    for (const tile of taxKpis) {
      // ⚠ `KpiTile` is a UNION — one member carries `money`, the other `value` —
      // so `tile.value` does not typecheck across it. Narrowing with `in` reads
      // BOTH members, which is also what this case wants: a status word rendered
      // through the money slot would be just as wrong as one in the value slot.
      const shown = "value" in tile ? tile.value : tile.money;
      expect(shown).not.toBe(statusWord);
    }
    // and the pill still carries it — the presenter hands the shell the word
    expect(presentTax(BEXAR, t, ACCOUNTS, REGIONAL).statusValue).toBe(BEXAR.status);
  });

  it("a figure nothing serves renders an em-dash rather than a plausible number", () => {
    // Bills-last-month and monthly-revenue have no read (see the TODOs in
    // definitionDetail.tsx). `used_by_invoice_lines` is 915 on this fixture and
    // must NOT be borrowed for the tile: it counts a lifetime, not a month.
    const kpis = presentCharge(BASE_W, t, ACCOUNTS).kpis;
    expect(kpis[1]).toMatchObject({ value: "—" });
    expect(kpis[2]).toMatchObject({ value: "—" });
    expect(JSON.stringify(kpis)).not.toContain("915");
  });

  it("the strip keeps its four tiles on every kind, labels and all", () => {
    // ⚠ THIS CASE USED TO READ *"on a kind with no read at all"* and rendered
    // the discount route with an empty cache, because `GET /discounts/{id}` did
    // not exist. It does now, so the same guarantee is asserted over real data:
    // §2's four-tile shape is part of the specification and survives whether or
    // not every figure behind it is served.
    // CR-166 r3 t6: the discount route mounts its own page now, so only the
    // declared shape is asserted here (the page's tiles: discountDetail.dom.test.tsx).
    expect(DEFINITION_KPI_LABEL_KEYS.discount).toHaveLength(TILES_PER_KIND.discount);
    // And the shape still holds with nothing in the cache — `emptyKpis` is what
    // draws the four LABELS before any read answers.
    expect(emptyKpis("discount", t)).toHaveLength(TILES_PER_KIND.discount);
  });
});

// ── §2 parts 2–5 · the header ──────────────────────────────────────────────

/**
 * The route PATTERNS `App.tsx` actually registers, read out of `App.tsx`.
 *
 * ⚠ **READ FROM THE ROUTER AND NEVER RETYPED HERE, BECAUSE A HOLD-EXPIRY TEST
 * THAT NAMES ITS OWN ADDRESSES CANNOT SEE A SCREEN LAND** — which is the whole
 * failure `DEF-RAT-4647` is an instance of, and which a hold-expiry test on the
 * customer portal reproduced exactly (`DEF-CWP-3925`: *"a hold-expiry test
 * asserted a screen was REGISTERED at an address while the router was mounting
 * it somewhere else"*). If it does not come from the router, it is a second
 * opinion about the router.
 */
const ROUTED_WIZARD_PATTERNS: string[] = [
  ...appSource.matchAll(/path:\s*"([^"]*plans-rates[^"]*)"/g),
].map((match) => match[1]);

describe("§2 parts 2–5 — eyebrow, h1, sub-line and the action cluster", () => {
  it("the charge eyebrow is KIND · CODE · TYPE, and the h1 is the definition's name", () => {
    const view = presentCharge(BASE_W, t, ACCOUNTS);
    expect(view.eyebrow).toBe(
      `${i18n.t("rating.definition.kind.charge")} · BASE-W · ${i18n.t("rating.charges.type.recurring")}`,
    );
    expect(view.title).toBe("Water base service");
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W });
    expect(html).toContain("BASE-W");
    expect(html).toMatch(/<h1[^>]*>Water base service<\/h1>/);
  });

  it("the tax eyebrow is KIND · LEVEL · AUTHORITY — r10's `TAX · LOCAL · BEXAR COUNTY`", () => {
    const view = presentTax(BEXAR, t, ACCOUNTS, REGIONAL);
    expect(view.eyebrow).toBe(
      `${i18n.t("rating.definition.kind.tax")} · ${i18n.t("rating.taxes.level.county")} · Bexar County`,
    );
  });

  it("the sub-line names the GL by CODE and NAME, never by uuid (DEF-206)", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W });
    expect(html).toContain("4200 — Water base revenue");
    expect(html).not.toContain("gl-4200");
  });

  it("§18 row 9: `Edit` is LIVE on the charge kind — CHG-02 exists, so its reason has stopped being true", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W });
    // The Edit button's own element must no longer be disabled. Matching the
    // ELEMENT rather than the page is what makes this able to fail: the page
    // still carries `disabled` twice, for Duplicate and Retire.
    const edit = html.match(/<button[^>]*>Edit<\/button>/);
    expect(edit).not.toBeNull();
    // ⚠ THE ATTRIBUTE, NOT THE WORD. The shared Button's utility string carries
    // `disabled:opacity-45`, so `toContain("disabled")` passes on an ENABLED
    // button and this check would have proved nothing.
    expect(edit?.[0]).not.toContain('disabled=""');
    expect(edit?.[0]).not.toContain(shown("rating.definition.action.wizardPending"));
  });

  it("`Edit` IS LIVE ON THE TAX TOO — DEF-RAT-4647, a hold that outlived its screen", () => {
    // ⚠ THIS CASE ASSERTED THE OPPOSITE, AND IT WAS THE HOLD'S ONLY GUARD.
    // `TaxWizard.tsx` shipped, `App.tsx` routed `…/{id}/edit`, the same clerk
    // could open it from the LIST one click away — and this button stayed
    // greyed out on every role for two weeks, over a screen that was live. Then
    // this test passed, every day, because it asserted the refusal rather than
    // the destination. Hard-won law 2's mirror: G13 asks whether a prop is
    // passed; nothing asked whether a REFUSAL was still true.
    const html = renderDetail("tax", BEXAR.id, { tax: BEXAR });
    const edit = html.match(/<button[^>]*>Edit<\/button>/);
    expect(edit).not.toBeNull();
    // The ATTRIBUTE, not the word — the shared Button's utility string carries
    // `disabled:opacity-45`, so `toContain("disabled")` passes on an enabled one.
    expect(edit?.[0]).not.toContain('disabled=""');
  });

  it("THE HOLD-EXPIRY TEST: every kind whose wizard is routed is in EDITABLE_KINDS", () => {
    // ⚠ THIS IS THE THING DEF-RAT-4647 DID NOT HAVE, and hard-won law 2 asks
    // for it BY NAME: *"when you write a hold, write the test that fires when
    // the hold expires, in the same commit — assert the destination by ADDRESS
    // and by the screen id it opens, so the day the screen lands the suite goes
    // red and names it."* A fourth kind whose wizard lands with `EDITABLE_KINDS`
    // unmoved fails HERE, naming itself, instead of shipping a dead control.
    const routed = ROUTED_WIZARD_PATTERNS.join(" ");
    for (const kind of DEFINITION_KINDS) {
      const segment = DEFINITION_ROUTES[kind].segment;
      const hasWizardRoute = routed.includes(`plans-rates/${segment}/`);
      expect([kind, hasWizardRoute]).toEqual([kind, EDITABLE_KINDS.includes(kind)]);
    }
  });

  it("THE HOLDS THAT HAVE NOT EXPIRED: Duplicate and Retire still have nowhere to go", () => {
    // The other half of the same law. These two ARE still held, and the test
    // asserts the CONDITION rather than the greying: the day a route matching
    // either segment is registered, this goes red and names the hold that has
    // to be released with it.
    for (const segment of HELD_ACTION_SEGMENTS) {
      expect(ROUTED_WIZARD_PATTERNS.join(" ")).not.toContain(segment);
    }
    // And the refusal they carry is TRUE and is six words (B14 rule 33). It
    // used to be thirty-two, and by 2026-09-08 every clause of it was false.
    expect(i18n.t("rating.definition.action.notBuilt").split(/\s+/).length).toBeLessThanOrEqual(6);
  });

  it("§2 part 5 / CR-087 E1: the cluster is Duplicate · Edit · Retire, in that order", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W });
    for (const key of [
      "rating.definition.action.duplicate",
      "rating.definition.action.edit",
      "rating.definition.action.retire",
    ]) {
      expect(html).toContain(shown(key));
    }
    // ⚠ THE ORDER IS ASSERTED, NOT JUST THE MEMBERSHIP (CR-087 E1: *"the button
    // duplicate retire and edit as per other screen make it uniform for all
    // screen"*). Five detail screens offered five different action sets, two
    // put Retire in the middle, and the same button was called `Edit` here and
    // `Edit as new version` on a plan. The order is part of the uniformity.
    const positions = [
      "rating.definition.action.duplicate",
      "rating.definition.action.edit",
      "rating.definition.action.retire",
    ].map((key) => html.indexOf(shown(key)));
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    // BR-SHL-025's shape: the two that are still HELD are present, disabled,
    // and carry a reason that is TRUE (see the hold-expiry cases above).
    expect(html).toContain(shown("rating.definition.action.notBuilt"));
    expect(html).toContain('disabled=""');
  });

  it("BR-SHL-025: a View role gets the RBAC reason instead, on the same three buttons", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W, access: "View" });
    expect(html).toContain(shown("rating.readOnlyReason"));
    expect(html).toContain(shown("rating.definition.action.duplicate"));
  });

  it("a role with no plans_rates cell never sees the surface at all (BR-SHL-003)", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W, access: "—" });
    expect(html).toContain(shown("rating.denied"));
    expect(html).not.toContain("Water base service");
  });
});

// ── BR-RAT-087 / DEF-364 · display strings, never the stored value ─────────

describe("BR-RAT-087 / DEF-364 — the screen renders the SERVER's display string", () => {
  it("a percent charge reads 1.50%, and the stored fraction 0.015000 is nowhere on the page", () => {
    const html = renderDetail("charge", LATE.id, { charge: LATE, tab: "amounts" });
    expect(html).toContain("1.50%");
    expect(html).not.toContain("0.015000");
    expect(html).not.toContain("0.015");
  });

  it("a percent tax reads 6.25%, and the string a customer read for nine days is absent", () => {
    const html = renderDetail("tax", BEXAR.id, { tax: BEXAR, tab: "basis" });
    expect(html).toContain("6.25%");
    expect(html).not.toContain("0.062500");
  });

  it("money renders at two places from `amount_display`, never from the six-place stored value", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W, tab: "amounts" });
    expect(html).toContain("12.00");
    expect(html).not.toContain("12.000000");
  });

  it("neither source file scales a stored value — the arithmetic B4 forbids is absent", () => {
    for (const source of [pageSource, configSource]) {
      expect(source).not.toContain("* 100");
      expect(source).not.toContain("toFixed");
      expect(source).not.toContain("parseFloat");
      expect(source).not.toContain("Number(");
    }
  });
});

// ── §10 · the Versions tab is the object's OWN record ──────────────────────

describe("§10 — the Versions tab is the object's own version history, NOT audit_log", () => {
  it("every kind's Versions tab closes with the DATED banner, verbatim", () => {
    // ⚠ THE TAX IS NOT IN THIS LOOP SINCE CR-165-BRC10 ROUND 3 (task 6). PO
    // round 6 moved its versions to a small table on OVERVIEW and made its
    // Audit tab the record of every change with its reason (image 20), which
    // draws no dated banner. The charge and the discount keep theirs.
    // CR-166-BRC10 round 3 task 6: nor is the discount — its versions are a
    // table on Overview and its Audit tab is every change (image 22).
    for (const kind of DEFINITION_KINDS.filter((one) => one !== "tax" && one !== "discount")) {
      const html = renderDetail(kind, "x", {
        charge: BASE_W,
        tax: BEXAR,
        discount: SENIOR,
        // ⚠ THE KIND'S OWN LAST TAB, NOT A LITERAL. CR-087 C2 renamed the
        // discount's to `audit`, and a test spelling `versions` here would
        // render a tab that kind does not declare, fall back to Overview, and
        // report the banner missing while the banner was fine.
        tab: DEFINITION_TABS[kind][DEFINITION_TABS[kind].length - 1],
      });
      expect(html).toContain("Bills always use the version in force on the usage date.");
      expect(html).toContain("data-dated-banner");
    }
  });

  it("the banner is not drawn on any other tab", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W, tab: "overview" });
    expect(html).not.toContain("data-dated-banner");
  });

  it("⚠ the tab NEVER reaches for audit_log — the wrong implementation is the plausible one", () => {
    // §10: both are append-only histories of the same object, and a filtered
    // audit query would render a table that looks right. Neither source file
    // may so much as name the audit surface.
    for (const source of [pageSource, configSource]) {
      expect(source.toLowerCase()).not.toContain("auditviewerpath");
      expect(source.toLowerCase()).not.toContain("getauditlog");
      expect(source.toLowerCase()).not.toContain("/audit-log");
      expect(source.toLowerCase()).not.toContain("queryKeys.auditLog".toLowerCase());
    }
  });

  it("no version list is served, so the tab says which record it is waiting for", () => {
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W, tab: "versions" });
    expect(html).toContain(shown("rating.definition.versions.arrivesWith"));
    // And it does not draw an empty table, which would claim "no versions".
    expect(html).not.toContain("<tbody>");
  });
});

// ── §18 row 11 · the discount, now that it HAS a read ──────────────────────
//
// ⚠ THIS SUITE USED TO ASSERT THE ABSENCE. Four of its cases required
// `definitionIsServed("discount")` to be FALSE, the five tabs to name the
// missing endpoint, and the back link to land on the bare Plans & Rates route
// because §18 row 10's tab did not exist. `GET /discounts/{id}` is served now
// and the tab is built, so every one of those assertions was inverted rather
// than deleted — what they were protecting (a screen that never invents a
// figure) is asserted below against real data instead.

describe("§18 row 11 — the discount kind renders from its own read", () => {
  // ⚠ CR-166-BRC10 round 3 task 6 (2026-10-03): the discount kind mounts its own
  // page (`discountDetail/DiscountDetailPage`, images 19–26), so the shell cases
  // that rendered a discount here were RETIRED, not rewritten — each fact they
  // guarded is asserted on the new page in `discountDetail.dom.test.tsx`.
  it("the route renders the discount, not the kind's placeholder title", () => {
    const html = renderDetail("discount", SENIOR.id, { discount: SENIOR });
    expect(html).toContain("Senior discount");
    expect(html).toContain(shown("rating.definition.tab.audit"));
    // The eyebrow is `DISCOUNT · SENIOR · PERCENTAGE · V2` — and V2 is real,
    // because unlike a charge code a discount DOES carry a version table.
    expect(html).toContain("SENIOR");
    expect(html).toContain("V2");
  });

  it("⚠ the percentage renders as 15.00% and the stored 15.000000 never reaches the screen", () => {
    // The discount half of DEF-364. A discount stores PERCENTAGE POINTS, so the
    // wrong formatter renders 1500.00% — well-formed, wrong, and invisible to
    // every gate. Both failure strings are searched for by hand.
    const html = renderDetail("discount", SENIOR.id, { discount: SENIOR });
    expect(html).toContain("15.00%");
    expect(html).not.toContain("15.000000");
    expect(html).not.toContain("1500.00%");
  });

  it("⚠ a charge waiver's value is an em-dash and NEVER 0.00", () => {
    // The discipline of the whole change: a waiver removes the whole of what
    // its scope selected and never reads `value`, so a zero on screen would
    // state that the utility waives nothing.
    const html = renderDetail("discount", WAIVER.id, { discount: WAIVER, tab: "value" });
    expect(html).toContain("Base charge waived");
    expect(html).not.toContain("0.00 ");
    const view = presentDiscount(WAIVER, t, REGIONAL);
    const value = view.panels.value.find((f) => f.labelKey === "rating.discounts.col.value");
    expect(value?.value).toBe("—");
  });

  it("⚠ an untyped cap is an em-dash and the bill FLOOR is a real 0.00", () => {
    // BR-RAT-075 makes a null cap UNCAPPED; BR-RAT-074 makes a floor of zero
    // MEAN that the bill may reach zero. Same glyph rule, opposite answers, and
    // the only place in the product where the difference is drawn.
    const view = presentDiscount(SENIOR, t, REGIONAL);
    const field = (key: string) => view.panels.value.find((f) => f.labelKey === key)?.value;
    expect(field("rating.discounts.capPerBill")).toBe("—");
    expect(field("rating.discounts.capPerYear")).toBe("—");
    expect(field("rating.discounts.capLifetime")).toBe("—");
    expect(field("rating.discounts.floorLabel")).toBe("0.00");
    expect(field("rating.discounts.budgetLabel")).toBe("12312.00");
  });

  it("⚠ CR-091-BRC01 — THE DETAIL VIEW NAMES THE SERVICES, AND IT NAMED NONE", () => {
    // PO, 2026-09-10: *"we will ahve to dsplay in detail view"*. Before today a
    // discount narrowed to one service read EXACTLY like one that applied to
    // everything, on the page a clerk opens to answer a customer — the CR's own
    // finding: *"the detail view — nothing at all"*.
    const field = (view: DefinitionPresentation, key: string) =>
      view.panels.value.find((f) => f.labelKey === key)?.value;

    const specific = presentDiscount(
      { ...SENIOR, applies_to: "specific_services", applies_to_services: ["water", "electric"] },
      t,
      REGIONAL,
    );
    expect(field(specific, "rating.discounts.servicesLabel")).toBe("Water · Electric");

    // The stored singular reads back as its own service, not as everything.
    const single = presentDiscount(
      { ...SENIOR, applies_to: "one_service", applies_to_service: "water" },
      t,
      REGIONAL,
    );
    expect(field(single, "rating.discounts.servicesLabel")).toBe("Water");

    // ⚠ AND THE ROW IS DRAWN EVEN WHEN THE ANSWER IS *ALL SERVICES*. A row that
    // appears on only two of the seven scopes is an absence nobody can see.
    expect(field(presentDiscount(SENIOR, t, REGIONAL), "rating.discounts.servicesLabel")).toBe(
      "All services",
    );
  });

  it("an empty stored list reads as an ABSENCE, never as *every service*", () => {
    // The write path refuses it, so such a row should not exist — and if one
    // does, the reading the PO ruled OUT (*empty means everywhere*) must not be
    // the one a clerk sees.
    const view = presentDiscount(
      { ...SENIOR, applies_to: "specific_services", applies_to_services: [] },
      t,
      REGIONAL,
    );
    expect(view.panels.value.find((f) => f.labelKey === "rating.discounts.servicesLabel")?.value)
      .toBe("—");
  });

  it("CR-087-p076 §7 — the accepted proof kinds join on ` · `, as the frame draws", () => {
    // Built as `Government ID, Birth certificate`; drawn as
    // `Government ID · Birth certificate`. A comma reads as part of a
    // document's own name where the mid-dot cannot.
    const view = presentDiscount(SENIOR, t, REGIONAL);
    const proof = view.panels.applicability.find(
      (f) => f.labelKey === "rating.discounts.proofKindsLabel",
    );
    expect(proof?.value).toBe("Government ID · Birth certificate");
  });

  it("CR-087-p076 §6 — ENROLMENT reads back the FACT, not the chooser's hint", () => {
    // Built as `Apply and approve, with proof — a document is needed as well`:
    // a dropdown option's explanatory clause, printed as a value on a fact
    // grid. The frame draws the bare answer.
    const view = presentDiscount(SENIOR, t, REGIONAL);
    const row = view.panels.applicability.find(
      (f) => f.labelKey === "rating.discounts.enrolmentModeLabel",
    );
    expect(row?.value).toBe("Apply and approve, with proof");
    expect(row?.value).not.toContain("—");
    expect(row?.value).not.toContain("document is needed");
  });

  it("CR-087-p076 §5 — the funding source is on the sub-line ONCE, and it is not", () => {
    // ⚠ The file's own comment has claimed since the merge that the funding
    // source *"moved off the sub-line into `what it is`"*. It moved INTO
    // `what it is` and did not move OFF, so one fact printed twice on one
    // screen while the code said otherwise (hard-won law 1).
    const view = presentDiscount(SENIOR, t, REGIONAL);
    const sub = view.subline.map((part) => (typeof part === "string" ? part : "")).join(" | ");
    expect(sub).not.toContain(SENIOR.funding_source as string);
    // And it IS still shown, once, where the frame puts it.
    const identity = view.blocks?.overview?.find((block) => block.id === "identity");
    expect(
      identity?.fields.find((f) => f.labelKey === "rating.discounts.col.funding")?.value,
    ).toBe(SENIOR.funding_source);
    // The drawn sub-line is TWO parts: the effective date and the overlay rule.
    expect(view.subline).toHaveLength(2);
  });

  it("⚠ tile 1 counts PLANS and tile 2 counts ENROLMENTS — available is not granted", () => {
    // BR-RAT-069. A shell that read one number for both would tell a utility
    // that every account on a plan carrying SENIOR is being charged 15% less.
    const view = presentDiscount(SENIOR, t, REGIONAL);
    expect(view.kpis[0]).toMatchObject({ value: SENIOR.plans });
    expect(view.kpis[1]).toMatchObject({ value: SENIOR.enrolled });
    expect(SENIOR.plans).not.toBe(SENIOR.enrolled);
  });

  it("tile 3 is an em-dash, because a MONTHLY programme cost is not served", () => {
    // `granted_to_date` IS served and is a true 0.00 — no bill has ever carried
    // a reduction, because R6 is not wired into apps/billing. Rendering that as
    // "per month" would be a wrong number rather than a missing one.
    const view = presentDiscount(SENIOR, t, REGIONAL);
    expect(view.kpis[2]).toMatchObject({ value: "—" });
  });

  it("`definitionIsServed` answers for all three kinds now", () => {
    for (const kind of DEFINITION_KINDS) {
      expect(definitionIsServed(kind)).toBe(true);
    }
  });

  it("its back link lands on the Discounts tab, which §18 row 10 finally builds", () => {
    expect(DEFINITION_ROUTES.discount.listRoute).toBe("/plans-rates/discounts");
    expect(DEFINITION_ROUTES.charge.listRoute).toBe("/plans-rates/charge-codes");
    expect(DEFINITION_ROUTES.tax.listRoute).toBe("/plans-rates/taxes-fees");
  });
});

// ── BR-SHL-011 · the open tab is URL state ─────────────────────────────────

describe("BR-SHL-011 — the open tab is URL state, and an unknown one falls back", () => {
  it("`?tab=` opens that tab on the kind that has it", () => {
    // ⚠ `?tab=remittance` NOW FALLS BACK TO THE OVERVIEW, and the remittance
    // FACTS are still on it — that is the merge working rather than a link
    // breaking. An old bookmark lands on a page that answers its question.
    const html = renderDetail("tax", BEXAR.id, { tax: BEXAR, tab: "remittance" });
    expect(html).toContain("Bexar County");
    // CR-165-BRC10 round 3: the filing facts are read on Overview under *On
    // the bill and filing* (image 18), so the stale bookmark still finds them.
    expect(html).toContain(shown("rating.taxDetail.section.billFiling"));
  });

  it("the fallback is the KIND's first tab, not a shared literal", () => {
    for (const kind of DEFINITION_KINDS) {
      expect(definitionTabFrom(kind, null)).toBe(DEFINITION_TABS[kind][0]);
      expect(definitionTabFrom(kind, "no-such-tab")).toBe(DEFINITION_TABS[kind][0]);
    }
    // A tab that belongs to ANOTHER kind is unknown here and falls back too —
    // `?tab=remittance` on a charge code must not open a blank panel.
    expect(definitionTabFrom("charge", "remittance")).toBe("overview");
    // The tax has no `remittance` tab any more, so the unknown-tab fallback is
    // what a stale bookmark meets — and it lands on the Overview, which now
    // carries the block it was looking for.
    expect(definitionTabFrom("tax", "remittance")).toBe("overview");
  });

  /**
   * **`CR-087` · `DEF-RAT-4832` — THE TWO SPELLINGS OF THE HISTORY TAB RESOLVE
   * TO EACH OTHER, AND THE ADDRESS STILL DOES NOT MOVE.**
   *
   * PO ruling 2026-09-10, verbatim: *"Change the label, keep the address"*. The
   * charge code's tab has READ `Audit` in all eleven catalogues since the
   * rename, while its address is `versions` — so every document, drawing and
   * person naturally writes `?tab=audit`, and that landed on the OVERVIEW.
   * Silently: `definitionTabFrom` cannot tell a mistyped tab from a synonym,
   * nothing errored, nothing logged, and a link simply opened the wrong screen.
   *
   * ⚠ **PROVED RED FIRST** (hard-won law 7) — against the pre-fix function,
   * which is the `tabs.includes(raw) ? raw : tabs[0]` one-liner:
   *
   *     AssertionError: expected 'overview' to be 'versions'
   *
   * ⚠ **AND THE MIRROR IS ALREADY REACHABLE, WHICH IS WHY IT IS ASSERTED TOO.**
   * A `?tab=versions` link to a DISCOUNT — written before that kind was renamed
   * on 2026-09-08 — lands on its Overview for the identical reason.
   */
  it("CR-087: ?tab=audit opens the charge's history tab, and ?tab=versions opens the discount's", () => {
    expect(definitionTabFrom("charge", "audit")).toBe("versions");
    expect(definitionTabFrom("discount", "versions")).toBe("audit");
    expect(definitionTabFrom("tax", "versions")).toBe("audit");
    // Each kind's OWN spelling is untouched — this widens what is ACCEPTED and
    // changes nothing about what resolves already.
    expect(definitionTabFrom("charge", "versions")).toBe("versions");
    expect(definitionTabFrom("discount", "audit")).toBe("audit");
    // ...and it is not a licence for any unknown tab: only a HISTORY spelling
    // maps, so a mistyped tab still falls back rather than guessing.
    expect(definitionTabFrom("charge", "audits")).toBe("overview");
  });

  /**
   * **`CR-087` · `CHG-01`'s PLANS TAB IS BUILT — PO 2026-09-10: *"build"*.**
   *
   * It rendered ONE SENTENCE saying it could not do its job, and that sentence
   * is the text the blueprint quotes back as the defect: *"The tile above
   * counts the plans that carry this definition. Naming them one by one needs a
   * read that does not exist yet."*
   *
   * ⚠ **PROVED RED FIRST** (hard-won law 7) — against the pre-fix branch, which
   * returned the `ArrivesWith` sentence for every kind:
   *
   *     AssertionError: expected '…Naming them one by one needs a read that
   *     does not exist yet.…' to contain 'Sample — Residential'
   *
   * ⚠ **THE ROUTE IS THE SERVER'S WORD, ASSERTED AS A WORD.** A screen that
   * read the route off `plan_code === null` would decide a fact the server
   * already knows; the base row's code cell states its own absence instead.
   */
  it("CR-087: the charge's Plans tab names the plans, and names WHICH ROUTE reaches each", () => {
    const reach: ChargeReachRow[] = [
      { plan_id: "p1", plan_name: "Sample — Residential", plan_code: "SCW-RES", reached_by: "named", units: 74 },
      { plan_id: "p3", plan_name: "Sample — Residential water", plan_code: null, reached_by: "base", units: 132 },
    ];
    const html = renderDetail("charge", BASE_W.id, {
      charge: BASE_W,
      tab: "plans",
      chargePlans: reach,
    });
    // ⚠ B14 rule 37 — these figures are the FIXTURE's, never a drawn one. The
    // blueprint inks `74`, `12` and `132` as illustrations and no test may
    // assert a drawn number; what is asserted here is that the ROW this suite
    // seeded reaches the screen.
    // `renderToStaticMarkup` escapes `&`, `<`, `>`, `"` and `'` and NOTHING
    // else, so an em dash reaches the markup as itself.
    expect(html).toContain("Sample \u2014 Residential");
    expect(html).toContain("SCW-RES");
    expect(html).toContain(">74<");
    expect(html).toContain(shown("rating.chargePlans.reachedBy.named"));
    expect(html).toContain(shown("rating.chargePlans.reachedBy.base"));
    // The base row does not name the code, and says so rather than showing a
    // bare dash a clerk would read as a missing value.
    expect(html).toContain(shown("rating.chargePlans.noPlanCode"));
    // The `TWO ROUTES` callout, once, under the table.
    expect(html).toContain(shown("rating.chargePlans.routesLabel"));
    // …and the sentence the tab used to be is gone from this kind.
    expect(html).not.toContain(shown("rating.definition.plans.arrivesWith"));
  });

  /**
   * ⚠ **THE DISCOUNT STILL SAYS IT CANNOT, AND THAT IS CORRECT.** It has no
   * endpoint, so its sentence is still TRUE for it. A branch that answered for
   * every kind would turn a true stated absence into a screen that renders
   * nothing and explains nothing, which is worse than the sentence it replaced.
   * The branch is therefore gated on the KIND, read here as source so a later
   * widening has to argue with a test rather than with a comment.
   *
   * (The TAX's own Plans tab is a sibling lane's work under the same PO ruling
   * — `taxDetailTabs.tsx` — so nothing here asserts about that kind in either
   * direction.)
   */
  it("CR-087: the discount keeps its stated absence, because its read really is missing", () => {
    expect(pageSource).toContain('if (props.kind === "charge" && props.definitionId !== "")');
    expect(pageSource).toContain('t("rating.definition.plans.arrivesWith")');
  });

  /**
   * ⚠ **THE ADDRESS DOES NOT MOVE, AND THAT IS THE HALF A TEST HAS TO HOLD.**
   * The ruling keeps `?tab=versions` so links already sent to people keep
   * working. `selectTab` writes the kind's OWN id back into the query string,
   * so a clerk clicking the tab copies `versions` out of the address bar. Read
   * as source, because the write-back is a one-line effect no rendering
   * assertion reaches.
   */
  it("CR-087: the tab a clerk clicks writes the KIND's own id back, not the synonym", () => {
    expect(pageSource).toContain("next.set(TAB_PARAM, id)");
    // The strip is built from the kind's own list, so the id it hands
    // `selectTab` is `versions` on a charge and `audit` on a discount.
    expect(pageSource).toContain("const tabs = DEFINITION_TABS[kind].map((id) => ({");
  });
});

// ── Hard-won law 2 · the detail is reachable ───────────────────────────────

describe("hard-won law 2 — the detail has a door", () => {
  it("§2 part 8: the Overview is ONE panel and it is headed WHAT THIS IS", () => {
    const view = presentCharge(BASE_W, t, ACCOUNTS);
    expect(Object.keys(view.panels)).toContain("overview");
    const html = renderDetail("charge", BASE_W.id, { charge: BASE_W });
    expect(html).toContain(shown("rating.definition.panel.overview"));
    // "and nothing else" — ONE panel, not two. Counted rather than searched for
    // by text: "Amounts" is also a TAB LABEL on this very page, so a plain
    // `not.toContain` would fail on a correct screen and pass on a stacked one
    // the moment someone renamed the tab.
    expect(html.match(/data-panel=""/g) ?? []).toHaveLength(1);
  });

  it("BR-RAT-035: an account-level charge reads `Any service`, which is a real answer", () => {
    const view = presentCharge(LATE, t, ACCOUNTS);
    expect(JSON.stringify(view.panels.overview)).toContain(i18n.t("rating.charges.anyService"));
  });

  it("the charge-codes tab links its identity cell at the detail route, for every role", () => {
    // The landing tab is what makes this screen reachable, and reading a
    // definition is not a write — so the link is a link, not a role-guarded
    // button that a View role would find disabled.
    const source = readTab("ChargeCodesTab");
    expect(source).toContain('definitionPath("charge", row.id)');
    expect(source).toContain("InlineLinkTo");
  });

  it("the taxes & fees tab does the same", () => {
    const source = readTab("TaxesFeesTab");
    expect(source).toContain('definitionPath("tax", row.id)');
    // CR-165 task 5: the name cell is a component now (B14 rule 43), and it is
    // the one that draws the link the tab hands its path to.
    expect(source).toContain("<TaxNameCell");
    expect(taxListPartsSource).toContain("InlineLinkTo");
  });
});

// The two landing tabs are read as text for the same reason CR-008's "one
// editor" case does it next door: "there is a door" is a claim about a call
// site, and a rendering assertion on a table cell would pass on a `<span>`.
import chargeTabSource from "./ChargeCodesTab.tsx?raw";
import taxTabSource from "./TaxesFeesTab.tsx?raw";
import taxListPartsSource from "./taxListParts.tsx?raw";
import { taxRowDefaults } from "./taxRowFixture";

function readTab(name: "ChargeCodesTab" | "TaxesFeesTab"): string {
  return name === "ChargeCodesTab" ? chargeTabSource : taxTabSource;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-013 P2 (rows 8 · 11 · 14) · BR-RAT-084 (PO ruling 2026-08-20)
// generated: 2026-08-20
// checklist: A✔ B✔ C✔ D=deferred(no API half in this packet — the absent reads are asserted as absent, not exercised) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest 34 passed (this file) · 1560 passed / 185 todo across 100 files✔ (1526/185 across 99 was the pre-lane baseline — the suite grew, nothing was dropped) · g31_declared_classes✔ · routeBUtilities 9/9✔ · g29_screen_ids✔
// exceptions: E1 — the three landing-tab "door" cases read the tab SOURCE as
//            text rather than rendering it. "There is a link to the detail" is
//            a claim about a call site, and a rendering assertion on a table
//            cell passes on a `<span>`; the same idiom the CR-008 "one editor"
//            case next door uses, for the same reason.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
