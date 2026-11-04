// ── Trace ──────────────────────────────────────────────
// Change:  `CR-150-BRC09` `NCT-01` tasks 4, 5 and 6 — New Connect steps 1 and
//          2 rebuilt from `05-prototype/new-connect-redesign-2026-09-28/`
//          `step1-customer.png` and `step2-premise.png`.
// Rules:   CLAUDE.md hard rule 8 (an address lives on `premises`;
//          `kind='mailing'` is a named exception) · `BR-MET-1162` (a unit may
//          carry its own point — **every screen showing one says which of the
//          two it is showing**) · B14 rule 31 (no database id is ever a
//          visible value) · rule 43 (reuse the component) · hard-won law 2
//          (built is not wired) · law 6 · law 7
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE CAN AND CANNOT SEE — READ IT BEFORE TRUSTING IT GREEN
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS HARNESS DOES NO LAYOUT. EVERY ELEMENT HERE IS ZERO BY ZERO**, so it
// cannot see a panel in the wrong column, a gap off the spacing scale or a
// heading at the wrong size. It reads RENDERED OUTPUT — the markup a clerk's
// browser would receive — and never a prop.
//
// **The rendered proof is a browser and there is no substitute:**
// `10-scripts/nct01_steps12_walkthrough.mjs` opens both steps at 1440 beside
// the drawings. This file is the cheap half that runs on every commit.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY (law 7), stated once here and again
// per case:** every assertion below reads a STRING out of static markup, so a
// control that renders correctly and is wired to nothing would satisfy most of
// them. That is why the read-only and the same-as-service cases assert the
// ATTRIBUTE that makes the refusal real (`readonly`) rather than the value in
// the box, and why the mailing case changes the PREMISE and reads the MAILING
// box — a copy that did not walk would keep the old text.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import type { PlanDetail, RouteRow, TenantServiceRow, UnitPlanOption } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { normalisePlanSections } from "@/api/planFormEndpoints";
import { DRAWN_DETAIL, DRAWN_PLAN_ID, DRAWN_RAW, DRAWN_SECTIONS } from "@/features/rating/planSections/thisPlanFixture";
import { ToastProvider } from "@/components/Toast";

import { ACCOUNT_CATEGORIES_QUERY_KEY } from "./customersShared";
import { emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { OwnerScopeStep } from "./NewConnectOwnerStep";
import {
  addressReasons,
  newConnectPlansQueryKey,
  newConnectPremisesTypesQueryKey,
  newConnectRoutesQueryKey,
  PremiseStep,
  routeOptions,
} from "./NewConnectPremiseStep";

const TEST_TENANT = "brazosbend";
const PLAN_ID = "11111111-1111-1111-1111-111111111111";
const CLASS_PLAN_ID = "22222222-2222-2222-2222-222222222222";

const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

/** The eleven platform services as `GET /settings/services` answers them, with
 *  five sold — the drawn build's own set. `fire` is eleventh (`BR-RAT-024`). */
const PLATFORM_SERVICES = [
  "electric",
  "water",
  "gas",
  "sewer",
  "trash",
  "storm_water",
  "solar",
  "broadband",
  "thermal_heat",
  "battery",
  "fire",
] as const;

function tenantServices(enabled: readonly string[]): TenantServiceRow[] {
  return PLATFORM_SERVICES.map((service) => ({
    service: service as string,
    name: service as string,
    enabled: enabled.includes(service),
    primary_uom: null,
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  }));
}

const PLAN_OPTION: UnitPlanOption = {
  id: PLAN_ID,
  code: "RES-CITY",
  name: "Residential City Plan",
  status: "published",
  services: ["water", "sewer", "trash", "fire"],
  effective_from: "2026-09-01",
};

/** `GET /plans/{id}` as the drawn plan answers it. Four of the five chosen
 *  services are priced; `broadband` is deliberately absent, which is the row
 *  the drawing marks *Not in this plan*. */
const PLAN_DETAIL = {
  id: PLAN_ID,
  code: "RES-CITY",
  name: "Residential City Plan",
  description: "Residential water, sewer, trash and fire for city addresses.",
  status: "published",
  version: 4,
  account_type_ids: [],
  account_type_id: null,
  account_subtype_id: null,
  budget_billing: false,
  eligibility: {},
  minimum_bill_amount: "12.0000",
  effective_from: "2026-09-01",
  effective_to: null,
  base_charges: "98.0000",
  outside_city_factor: null,
  rate_schedules: [
    { service: "water", tariff_id: "t-w", tariff_name: 'Water 1"' },
    { service: "sewer", tariff_id: "t-s", tariff_name: "Follows water" },
  ],
  accounts: 0,
  services: [
    {
      service: "water",
      name: "Water",
      base_charge: "12.0000",
      // ⊕ `CR-164-BRC10` item 12 — served by `plan_detail` since that change.
      base_charge_code: "BASE-W",
      currency: "USD",
      schedule_minimum_amount: "6.0000",
      schedule_minimum_amount_display: "$6.00",
      gl_account_id: null,
      outside_city_exempt: false,
    },
    {
      service: "sewer",
      name: "Sewer",
      base_charge: "8.0000",
      currency: "USD",
      schedule_minimum_amount: null,
      schedule_minimum_amount_display: null,
      gl_account_id: null,
      outside_city_exempt: false,
    },
    {
      service: "trash",
      name: "Trash",
      base_charge: "18.0000",
      currency: "USD",
      schedule_minimum_amount: null,
      schedule_minimum_amount_display: null,
      gl_account_id: null,
      outside_city_exempt: true,
    },
    {
      service: "fire",
      name: "Fire",
      base_charge: "60.0000",
      currency: "USD",
      schedule_minimum_amount: null,
      schedule_minimum_amount_display: null,
      gl_account_id: null,
      outside_city_exempt: false,
    },
  ],
  charge_rules: [],
  deposit_rules: [],
  penalty_rule: null,
  late_fee_charge: null,
  tax_rules: [],
  tax_attachments: [],
  discounts: [],
  tax_lines: [],
  combined_tax_rate_display: null,
  versions: [],
} as unknown as PlanDetail;

const ROUTES: RouteRow[] = [
  {
    id: "route-uuid-0001",
    code: "RT-01",
    name: "North walk",
    route_type: "walk",
    feeder_ref: null,
    assigned_to: null,
    cycle_id: null,
    cycle_code: null,
    status: "active",
    members: 0,
    meters: 0,
    collected: null,
    last_completion: null,
    progress: null,
  } as unknown as RouteRow,
];

function seeded(): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(queryKeys.tenantServices, tenantServices(PLATFORM_SERVICES));
  client.setQueryData(newConnectPremisesTypesQueryKey, [
    { code: "apartment_complex", name: "Multi-unit residential", active: true },
  ]);
  client.setQueryData(newConnectPlansQueryKey, {
    count: 2,
    results: [
      PLAN_OPTION,
      { ...PLAN_OPTION, id: CLASS_PLAN_ID, code: "RES-ONLY" },
      { ...PLAN_OPTION, id: DRAWN_PLAN_ID, code: "MBSP", name: "Municipal Solar PV & Battery Service Plan", services: ["solar", "battery"] },
    ],
  });
  // ⊕ `DEF-CUS-9821` — ONE read of `GET /plans/{id}`, both shapes, keyed on
  // the plan AND the owner's class (`""` = none chosen yet). The drawing's
  // plan (MBSP) is the one the block's cases read.
  client.setQueryData(["new-connect", "plan-detail", PLAN_ID, ""], {
    detail: PLAN_DETAIL,
    sections: normalisePlanSections({ ...PLAN_DETAIL, details: { code: "RES-CITY", customer_classes: [] }, services: [] }),
  });
  client.setQueryData(["new-connect", "plan-detail", DRAWN_PLAN_ID, "residential"], {
    detail: DRAWN_DETAIL,
    sections: DRAWN_SECTIONS,
  });
  // ⊕ `CR-164-BRC10` item 13 — a plan that names ONE class, and the list the
  // plan wizard picks classes from.
  client.setQueryData(["new-connect", "plan-detail", CLASS_PLAN_ID, ""], {
    detail: { ...PLAN_DETAIL, id: CLASS_PLAN_ID, code: "RES-ONLY", account_type_ids: ["at-res"] },
    sections: normalisePlanSections({
      ...DRAWN_RAW,
      details: { ...DRAWN_RAW.details, code: "RES-ONLY", customer_classes: [{ value: "at-res", label: "Residential" }] },
    }),
  });
  client.setQueryData(queryKeys.lookupEntries("account_types", "", 1, 100), {
    count: 1,
    next: null,
    previous: null,
    results: [{ id: "at-res", code: "residential", name: "Residential", active: true }],
  });
  client.setQueryData(newConnectRoutesQueryKey, ROUTES);
  client.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [{ code: "residential", name: "Residential" }],
    legacy: [],
  });
  client.setQueryData(queryKeys.shellDisplay, {
    regional: { language: "en", state: "TX" },
  });
  return client;
}

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/...` PATTERN** (hard-won law 2): a bare
 * `MemoryRouter` with no matching route leaves `useParams().tenant` undefined
 * and every address the screen builds comes out protocol-relative — a string
 * that reads as perfectly good to `toContain`.
 */
function render(node: React.ReactNode): string {
  return renderToStaticMarkup(
    <QueryClientProvider client={seeded()}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=1`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<>{node}</>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function step1(over: Partial<NewConnectDraft> = {}): string {
  return render(
    <OwnerScopeStep
      draft={{ ...emptyDraft(), ...over }}
      onPatch={() => undefined}
      t={t}
    />,
  );
}

function step2(over: Partial<NewConnectDraft> = {}): string {
  return render(
    <PremiseStep draft={{ ...emptyDraft(), ...over }} onPatch={() => undefined} t={t} />,
  );
}

/** The markup of one `data-step-content` panel, so a case cannot accidentally
 *  match a string that lives in a different panel. */
function panel(html: string, name: string): string {
  const open = html.indexOf(`data-step-content="${name}"`);
  expect(open, `panel ${name} is not on the screen`).toBeGreaterThan(-1);
  // To the NEXT top-level panel marker, not a fixed window: a fixed window is
  // the shape that made this helper report a missing row for a row that was
  // simply past the cut (law 7 — a check reporting zero over a scope it
  // silently excludes). `account-details` is nested inside `customer-search`
  // and is skipped so the outer panel keeps its whole body.
  let next = html.length;
  for (const marker of [...html.matchAll(/data-step-content="([a-z-]+)"/g)]) {
    const at = marker.index ?? 0;
    if (at > open && marker[1] !== "account-details") {
      next = at;
      break;
    }
  }
  return html.slice(open, next);
}

/** Is the input with this id rendered `readonly`? Reads the ATTRIBUTE and not
 *  the value, because a value that happens to match proves nothing. */
function isReadOnly(html: string, id: string): boolean {
  const at = html.indexOf(`id="${id}"`);
  expect(at, `no input ${id}`).toBeGreaterThan(-1);
  const tagStart = html.lastIndexOf("<", at);
  const tag = html.slice(tagStart, html.indexOf(">", at) + 1);
  return tag.includes("readonly");
}

describe("New Connect step 1 · Customer, from step1-customer.png", () => {
  // ══════════════════════════════════════════════════════════════════════
  // TASK 4 · THE SEARCH AND THE ACCOUNT DETAILS ARE ONE BLOCK
  // ══════════════════════════════════════════════════════════════════════

  // ⊕ **LANE CF-1 (2026-10-18) — STEP 1 IS MOVE-IN'S SHARED CUSTOMER FORM**
  // (drawing set `customer-forms-2026-10-18`, image 06, read as an IMAGE; PO
  // *"Move in UI is latest and correct"*). The cases that asserted the
  // 2026-09-29 panels — Gov-ID, Communication, the automatic *Existing
  // customer* card, one short co-applicant form, the account uploader — are
  // superseded by the drawing's own: Who · Identity (with *Search customer
  // ID*) · More about the customer · Co-owners · Documents · Mailing address,
  // then Reference and Work, which the drawing does not touch.
  function at(html: string, marker: string): number {
    const found = html.indexOf(marker);
    expect(found, `${marker} is not on the screen`).toBeGreaterThan(-1);
    return found;
  }

  it("Search customer ID is back, in the Identity panel, and the automatic card is gone", () => {
    const html = step1({ owner: { ...emptyDraft().owner, partyKind: "person" } });
    const identity = html.slice(at(html, 'data-customer-panel="identity"'));
    expect(identity).toContain("data-search-customer-id");
    expect(html).not.toContain('data-step-content="customer-match"');
  });

  it("every drawn panel of step 1 is on the screen, in the drawn order", () => {
    const html = step1({ owner: { ...emptyDraft().owner, partyKind: "person" } });
    const order = [
      'data-customer-panel="who"',
      'data-customer-panel="identity"',
      'data-tick-panel="co_owner"',
      'data-array="move-in-documents"',
      'data-tick-panel="mailing"',
      'data-step-content="reference"',
      'data-step-content="work"',
    ].map((marker) => at(html, marker));
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("the co-owner panel and the mailing address are tick panels, empty until ticked", () => {
    const html = step1();
    const co = html.slice(at(html, 'data-tick-panel="co_owner"'));
    expect(co).not.toContain('id="co_owner_0_full_name"');
    // The mailing address is the building's until the tick is taken off.
    expect(html).not.toContain('id="mailing_city"');
  });

  it("untick and the mailing address becomes the clerk's own", () => {
    const html = step1({ mailing: { ...emptyDraft().mailing, sameAsService: false } });
    expect(isReadOnly(html, "mailing_city")).toBe(false);
  });

  it("no database id is a visible value on step 1", () => {
    // B14 rule 31. A uuid in a `value=` is the shape the rule forbids; a uuid
    // as a SELECT option's value is how a picker works and is not on screen,
    // so the case looks for one in rendered TEXT.
    const html = step1();
    expect(html).not.toMatch(/>[^<]*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
  });
});

describe("New Connect step 2 · Premise, from step2-premise.png", () => {
  // ══════════════════════════════════════════════════════════════════════
  // TASK 6 · THE POINT, THE VERIFIED TAG, AND WHOSE POINT IT IS
  // ══════════════════════════════════════════════════════════════════════

  it("latitude, longitude and the verified tick are on the record", () => {
    const block = panel(step2(), "record");
    expect(block).toContain('id="nc_lat"');
    expect(block).toContain('id="nc_lng"');
    expect(block).toContain('id="nc_location_verified"');
    expect(block).toContain("Latitude");
    expect(block).toContain("Longitude");
    expect(block).toContain("Location verified");
  });

  it("the screen SAYS the point is the building's — BR-MET-1162", () => {
    // ⚠ **THIS IS THE RULE'S OWN LAST CLAUSE AND IT IS THE REASON THIS CASE
    // EXISTS.** A unit may carry its own point and where it does those are the
    // truth for that unit, so *every screen showing a point says which of the
    // two it is showing*. Without the sentence a clerk cannot tell a unit's
    // point from its building's on any later screen.
    //
    // ⚠ **WHAT WOULD MAKE IT PASS WRONGLY:** asserting the SENTENCE only. The
    // marker is asserted too, so a screen that later shows a UNIT's point has
    // to change the marker rather than leave a now-false sentence standing.
    const block = panel(step2(), "record");
    expect(block).toContain('data-point-belongs-to="premise"');
    expect(block).toContain("The point is the building&#x27;s.");
  });

  it("Unit, apt. or suite is ENABLED and takes a value", () => {
    // It was `disabled` with *"Named on the next step"* under it and the PO
    // asked why. The drawing settles it: enabled, optional, postal.
    const html = step2({ premise: { ...emptyDraft().premise, unit: "Suite 200" } });
    const at = html.indexOf('id="nc_unit"');
    expect(at).toBeGreaterThan(-1);
    const tag = html.slice(html.lastIndexOf("<", at), html.indexOf(">", at) + 1);
    expect(tag).not.toContain("disabled");
    expect(tag).toContain('value="Suite 200"');
    expect(html).toContain("Units are named on step 3.");
  });

  it("city, state and ZIP are READ-ONLY over a premises already on file", () => {
    // ⚠ **HARD RULE 8.** The address belongs to `premises`; once a building is
    // named, the town is the register's answer and a second one typed here is
    // how one property's history splits in two.
    const onFile = step2({
      premise: {
        ...emptyDraft().premise,
        premisesId: "prem-uuid-1",
        city: "Ottumwa",
        state: "Iowa",
        postalCode: "52501",
      },
    });
    expect(isReadOnly(onFile, "nc_city")).toBe(true);
    expect(isReadOnly(onFile, "nc_state")).toBe(true);
    expect(isReadOnly(onFile, "nc_zip")).toBe(true);
    // A NEW address is the clerk's own, or nothing could ever be created.
    const fresh = step2();
    expect(isReadOnly(fresh, "nc_city")).toBe(false);
  });

  it("Scope moved here from step 1", () => {
    expect(step2()).toContain('data-step-content="scope"');
    expect(step1()).not.toContain('data-step-content="scope"');
  });

  // ⊕ `DEF-CUS-9821` — PO 2026-10-06, the approved drawing. These two cases
  // replace *"the plan is shown IN FULL"* and *"every chosen service gets a
  // priced row"*, whose table the redraw removed (*"What each service is
  // priced at"* is gone; the block's Base charges and Usage rates replace it).
  function drawnStep(): string {
    return step2({
      planApartments: DRAWN_PLAN_ID,
      premiseServices: ["solar", "battery"],
      owner: { ...emptyDraft().owner, category: "residential" },
    });
  }

  it("Services and plan carries the This-plan block's eight parts (DEF-CUS-9821)", () => {
    const block = panel(drawnStep(), "services-and-plan");
    expect(block).toContain('data-plan-summary="MBSP"');
    expect(block).toContain('data-facts="this-plan-summary"');
    expect(block).toContain('data-warning="this-plan-noBaseCode"');
    for (const part of ["base", "usage"]) expect(block).toContain(`data-this-plan-part="${part}"`);
    // The five collapsed parts are drawn by their headers, closed.
    for (const title of ["Other charges", "Deposit", "Taxes", "Discounts", "Outside city"]) expect(block).toContain(title);
    expect(block).toContain("2 · 8.00% total");
    expect(block).toContain("Figures come from the plan, for Residential accounts at this address.");
    // The redraw REPLACED the old table and facts; they are not drawn twice.
    expect(block).not.toContain("What each service is priced at");
    expect(block).not.toContain('data-service-row="');
    expect(block).not.toContain("It is not zero");
  });

  it("the block's every link opens a new tab under the tenant (DEF-CUS-9821)", () => {
    const block = panel(drawnStep(), "services-and-plan");
    const anchors = [...block.matchAll(/<a [^>]*>/g)].map((m) => m[0]);
    expect(anchors.length).toBeGreaterThan(4);
    for (const tag of anchors) {
      expect(tag).toContain('target="_blank"');
      expect(tag).toContain(`href="/${TEST_TENANT}/plans-rates/`);
    }
  });

  it("the read route is a list of the utility's own routes, by CODE", () => {
    // B14 rule 31 — a route's uuid is never the value of a control where a
    // human-readable key exists, and `_resolve_create_route` takes either.
    expect(routeOptions(ROUTES, "")).toEqual([{ value: "RT-01", label: "RT-01 · North walk" }]);
    // A stored code the list does not hold is KEPT, never silently dropped.
    expect(routeOptions(ROUTES, "RT-99")).toEqual([
      { value: "RT-01", label: "RT-01 · North walk" },
      { value: "RT-99", label: "RT-99" },
    ]);
    expect(step2()).toContain("Choose a route");
  });

  it("no database id is a visible value on step 2", () => {
    const html = step2({ planApartments: PLAN_ID, premiseServices: ["water"] });
    expect(html).not.toMatch(/>[^<]*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `CR-164-BRC10` — STEP 2 (items 12, 13, 14, Q7)
// ══════════════════════════════════════════════════════════════════════════
describe("CR-164-BRC10 — step 2's plan table and address reasons", () => {
  it("Budget billing is not on step 2 (PO ruling Q6)", () => {
    const block = panel(
      step2({ planApartments: PLAN_ID, premiseServices: ["water"] }),
      "services-and-plan",
    );
    expect(block).not.toContain("Budget billing");
  });

  it("Account type names the plan's customer class (item 13)", () => {
    const block = panel(
      step2({ planApartments: CLASS_PLAN_ID, premiseServices: ["water"] }),
      "services-and-plan",
    );
    expect(block).toContain("Residential");
    expect(block).not.toContain("Every class");
  });

  it("hides Unit, apt. for an apartment complex (PO ruling Q7)", () => {
    const complex = step2({ premise: { ...emptyDraft().premise, premiseType: "apartment_complex" } });
    expect(complex).not.toContain('id="nc_unit"');
    const house = step2({ premise: { ...emptyDraft().premise, premiseType: "single_family" } });
    expect(house).toContain('id="nc_unit"');
  });

  it("says why a State or ZIP looks wrong, and blocks nothing", () => {
    expect(addressReasons({ state: "Texas", postalCode: "78704" }, "TX")).toEqual({
      state: "customers.newConnect.step2.stateNotACode",
      zip: null,
    });
    expect(addressReasons({ state: "IA", postalCode: "5250" }, "TX")).toEqual({
      state: "customers.newConnect.step2.stateNotTheUtilitys",
      zip: "customers.newConnect.step2.zipShape",
    });
    // `tenants.state` is stored as typed at sign-up — `Texas` is TX.
    expect(addressReasons({ state: "TX", postalCode: "78704" }, "Texas")).toEqual({
      state: null,
      zip: null,
    });
    expect(addressReasons({ state: "tx", postalCode: "78704-1234" }, "TX")).toEqual({
      state: null,
      zip: null,
    });
    const html = step2({ premise: { ...emptyDraft().premise, state: "IA" } });
    expect(html).toContain("Not this utility&#x27;s state.");
  });
});
