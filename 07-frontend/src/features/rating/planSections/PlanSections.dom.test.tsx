// @vitest-environment jsdom
// CR-167-BRC10 round 2 task 4 — the ONE shared plan-sections component (ruling
// 11). Review mounts it now; round 3's details tabs mount the same sections.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { normalisePlanSections } from "@/api/planFormEndpoints";

import { foldedServiceLine } from "../planDetail/planDetailModel";
import { PlanSections, REVIEW_SECTIONS, baseLines } from "./PlanSections";
import type { PlanSectionId } from "./PlanSections";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

function ref(id: string, kind: string, code: string, name: string, version: number | null, from: string | null) {
  return { id, kind, code, name, version, version_label: null, effective_from: from, effective_to: null, next: null };
}

/** `GET /plans/{id}`'s sections as §7.3 serves them — through the normaliser,
 *  so the test reads what the screen reads. */
const SECTIONS = normalisePlanSections({
  currency: "USD",
  details: {
    name: "Residential City Plan",
    code: "RCP",
    customer_classes: [{ value: "cls-res", label: "Residential" }],
    description: "Water and sewer for homes.",
    intended_for: { cap_proof: false, min_demand_25kw: false, owner_occupied: true },
    notes: [{ attribute: "customer_class", operator: "is", value: "Residential" }],
    minimum_bill_display: "10.00",
    budget_billing: false,
  },
  services: [
    {
      service: "water",
      name: "Water",
      gl: { code: "4110", name: "Water revenue" },
      schedule: { ...ref("sch-w", "schedule", "RW", "Residential water (inclining tiers)", 4, "2026-09-30"), model: "tiered", model_label: "Tiered" },
      base: {
        code: ref("bc-w1", "base_code", "BASE-W1", "Water base", 2, "2026-09-01"),
        sized_by_label: "meter size",
        by_size: [
          { size_class: "5_8", size_label: '5/8"', amount_display: "10.00" },
          { size_class: "2", size_label: '2"', amount_display: "40.00" },
        ],
        flat_display: null,
        state: "ok",
        codes: ["BASE-W1"],
        monthly_amount: "10.0000",
      },
      minimum: { by_size: [{ size_class: "5_8", size_label: '5/8"', amount_display: "5.00" }], flat_display: null },
      usage: { kind: "blocks", kind_label: "Block (per month)", rows: [{ label: "0 – 5 kgal", rate_display: "$4.24 per kgal" }] },
      outside_city: { surcharged: true, percent_display: "25%" },
    },
    {
      service: "sewer",
      name: "Sewer",
      gl: null,
      schedule: null,
      base: { code: null, by_size: [], flat_display: null, state: "ambiguous", codes: ["BASE-S", "BASE-S2"], monthly_amount: null },
      minimum: { by_size: [], flat_display: null },
      usage: { kind: "", rows: [] },
      outside_city: { surcharged: false, percent_display: null },
    },
  ],
  base_total: { amount_display: "19.00", unavailable: null },
  outside_city_surcharge: { percent_display: "25%", service_names: ["Water"] },
  charge_codes: [
    {
      ref: ref("cc-late", "charge_code", "LATE", "Late payment fee", 1, "2026-08-01"),
      priced_by: "class",
      rows: [
        { class_or_size_label: "Residential", percent_display: "1.50%", min_display: "5.00" },
        { class_or_size_label: "Commercial", percent_display: "2.00%", min_display: "10.00" },
      ],
      gl: { code: "2610", name: "Late fees" },
      type_label: "Penalty",
      when_label: "After the due date",
    },
  ],
  taxes: [
    {
      ref: ref("tx-1", "tax", "TX", "TX State Utility Tax", 1, "2026-01-01"),
      rate_display: "6.25%",
      what_is_taxed_label: "Usage and base charges",
      gl: { code: "2200-02", name: "Tax payable" },
      authority: "Texas Comptroller",
      brought_by: "jurisdiction",
    },
  ],
  combined_tax_rate_display: "6.25%",
  deposits: [
    {
      ref: ref("dep-1", "deposit_code", "DEPOSIT", "Security deposit", 2, "2026-09-01"),
      priced_by: "class",
      rows: [{ class_or_size_label: "Residential", amount_display: "150.00" }],
      gl: { code: "2300", name: "Deposits held" },
    },
  ],
  discounts: [
    {
      ref: ref("disc-1", "discount", "SENIOR", "Senior discount", 1, "2026-08-01"),
      value_display: "15%",
      gl: { code: "4760", name: "Customer discounts" },
      enrolled: 12,
      offered_from: "2026-09-01",
      offered_until: null,
    },
  ],
});

function mount(props: {
  show?: readonly PlanSectionId[];
  links?: boolean;
  onEdit?: (section: PlanSectionId) => void;
  sections?: typeof SECTIONS;
}) {
  render(
    <MemoryRouter initialEntries={["/brazosbend/plans-rates/plans/p1"]}>
      <Routes>
        <Route
          path="/:tenant/plans-rates/plans/:planId"
          element={
            <PlanSections
              sections={props.sections ?? SECTIONS}
              show={props.show ?? REVIEW_SECTIONS}
              t={t}
              dateFormat="MM/DD/YYYY"
              timeZone="America/Chicago"
              links={props.links ?? false}
              onEdit={props.onEdit}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function section(id: string): HTMLElement {
  const found = document.querySelector(`[data-plan-section="${id}"]`);
  expect(found).not.toBeNull();
  return found as HTMLElement;
}

describe("ruling 9 · Review is tables, in the drawn order", () => {
  it("draws Plan, each service, Charge codes, Taxes, Deposits, Discounts, Billing terms", () => {
    mount({});
    const order = [...document.querySelectorAll("[data-plan-section]")].map((el) => el.getAttribute("data-plan-section"));
    expect(order).toEqual(["plan", "service", "service", "charges", "taxes", "deposits", "discounts", "billingTerms"]);
  });

  it("names a class and a note in words, never an id (DEF-RAT-9285)", () => {
    mount({});
    const plan = section("plan");
    expect(within(plan).getByText("Residential")).toBeInTheDocument();
    expect(within(plan).getByText("Customer class is Residential")).toBeInTheDocument();
    expect(within(plan).getByText("Owner-occupied premises")).toBeInTheDocument();
    expect(plan.textContent).not.toContain("cls-res");
  });
});

describe("DEF-RAT-9336 · the base shown is the code the bill charges", () => {
  it("water: ONE code with its version and from-date, base and minimum by size", () => {
    mount({});
    const water = document.querySelector('[data-plan-service="water"]') as HTMLElement;
    const base = water.querySelector('[data-fact="base"]') as HTMLElement;
    expect(within(base).getByText("BASE-W1")).toBeInTheDocument();
    expect(within(base).getByText("V2")).toBeInTheDocument();
    expect(within(base).getByText("from 09/01/2026")).toBeInTheDocument();
    expect(within(water).getByText("Base charges by meter size")).toBeInTheDocument();
    expect(within(water).getByText("$40.00")).toBeInTheDocument();
    expect(within(water).getByText("$5.00")).toBeInTheDocument();
    expect(within(water).getByText("+25%")).toBeInTheDocument();
    expect(within(water).getByText("Usage charges · Block (per month)")).toBeInTheDocument();
  });

  it("an ambiguous base names its codes and shows no figure", () => {
    mount({});
    const sewer = document.querySelector('[data-plan-service="sewer"]') as HTMLElement;
    expect(within(sewer).getByText("Choose a base code")).toBeInTheDocument();
    expect(within(sewer).getByText("BASE-S, BASE-S2")).toBeInTheDocument();
    expect(within(sewer).getByText("Same price")).toBeInTheDocument();
  });

  it("DEF-RAT-9504: an every-class plan's ambiguous base says which class pays which code", () => {
    // Through the normaliser, so the field the server adds is proved to reach the screen.
    const withOptions = normalisePlanSections({
      ...SECTIONS,
      services: SECTIONS.services.map((line) =>
        line.service === "sewer"
          ? {
              ...line,
              base: {
                ...line.base,
                options: [
                  { code: "BASE-S", classes: ["Residential"] },
                  { code: "BASE-S2", classes: ["Commercial", "Industrial"] },
                ],
              },
            }
          : line,
      ),
    });
    mount({ sections: withOptions });
    const sewer = document.querySelector('[data-plan-service="sewer"]') as HTMLElement;
    expect(within(sewer).getByText("Choose a base code")).toBeInTheDocument();
    expect(within(sewer).getByText("BASE-S · Residential")).toBeInTheDocument();
    expect(within(sewer).getByText("BASE-S2 · Commercial, Industrial")).toBeInTheDocument();
  });
});

describe("ruling 8 · every referenced item has a version pill and a from-date", () => {
  it("charge code, tax, deposit and discount rows each carry one", () => {
    mount({});
    for (const id of ["charges", "taxes", "deposits", "discounts"]) {
      expect(section(id).querySelector("[data-ref-pill]")).not.toBeNull();
    }
    expect(within(section("charges")).getByText("2.00% · min $10.00")).toBeInTheDocument();
    expect(within(section("taxes")).getByText("Texas Comptroller")).toBeInTheDocument();
    expect(within(section("taxes")).getByText("6.25% combined")).toBeInTheDocument();
  });

  it("DEF-RAT-9519 · a tax the plan's classes do not pay is listed and marked", () => {
    mount({
      sections: { ...SECTIONS, taxes: [{ ...SECTIONS.taxes[0], reaches_plan_classes: "none" }], combined_tax_rate_display: null },
    });
    expect(within(section("taxes")).getByText("TX State Utility Tax")).toBeInTheDocument();
    expect(within(section("taxes")).getByText("Not charged to this plan's classes")).toBeInTheDocument();
    expect(within(section("taxes")).queryByText(/combined/)).toBeNull();
  });

  it("discounts keep an Enrolled column and say No end", () => {
    mount({});
    const discounts = section("discounts");
    expect(within(discounts).getByText("Enrolled")).toBeInTheDocument();
    expect(within(discounts).getByText("12")).toBeInTheDocument();
    expect(within(discounts).getByText("No end")).toBeInTheDocument();
  });

  it("billing terms read monthly base charges, minimum bill and budget billing", () => {
    mount({});
    const terms = section("billingTerms");
    expect(within(terms).getByText("$19.00")).toBeInTheDocument();
    expect(within(terms).getByText("$10.00")).toBeInTheDocument();
    expect(within(terms).getByText("Not offered")).toBeInTheDocument();
  });
});

describe("ruling 11 · the details tabs mount subsets of the same sections", () => {
  it("Services tab: services and the totals strip only, names as links (ruling 13)", () => {
    mount({ show: ["services", "servicesTotals"], links: true });
    expect(document.querySelector('[data-plan-section="plan"]')).toBeNull();
    expect(within(section("servicesTotals")).getByText("25% on Water")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "BASE-W1" });
    expect(link).toHaveAttribute("href", "/brazosbend/plans-rates/charge-codes/bc-w1");
    expect(screen.getByRole("link", { name: "Residential water (inclining tiers)" })).toHaveAttribute(
      "href",
      "/brazosbend/plans-rates/rates/sch-w",
    );
  });

  it("Review: names are text, and a section's Edit says which section it opens", async () => {
    const onEdit = vi.fn();
    mount({ onEdit });
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    await userEvent.setup().click(screen.getByRole("button", { name: "Edit Taxes" }));
    expect(onEdit).toHaveBeenCalledWith("taxes");
  });
});

describe("OQ-RAT-12786 · a deposit priced by size reads its sizes (images 21, 30)", () => {
  it("Priced by Size, one row per size with its amount — 5/8\" $150.00, 2\" $600.00", () => {
    const sized = normalisePlanSections({
      currency: "USD",
      deposits: [
        {
          ref: ref("dep-2", "deposit_code", "DEP-SIZE", "Security deposit by size", 1, "2026-09-01"),
          priced_by: "size",
          // Served in CODE order, as the server sends it (W-2 < W-58).
          rows: [
            { class_or_size_label: 'Water 2"', amount_display: "600.00" },
            { class_or_size_label: 'Water 5/8"', amount_display: "150.00" },
          ],
          gl: { code: "2300", name: "Deposits held" },
        },
      ],
    });
    render(
      <MemoryRouter initialEntries={["/brazosbend/plans-rates/plans/p1"]}>
        <Routes>
          <Route
            path="/:tenant/plans-rates/plans/:planId"
            element={
              <PlanSections
                sections={sized}
                show={["deposits"]}
                t={t}
                dateFormat="MM/DD/YYYY"
                timeZone="America/Chicago"
                links={false}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    const box = section("deposits");
    expect(within(box).getByText("Size")).toBeInTheDocument();
    expect(within(box).getByText('Water 5/8"')).toBeInTheDocument();
    expect(within(box).getByText('Water 2"')).toBeInTheDocument();
    expect(within(box).getByText("$150.00")).toBeInTheDocument();
    expect(within(box).getByText("$600.00")).toBeInTheDocument();
    // DEF-RAT-9503 — smallest size first, by the size the name states.
    const classes = [...box.querySelectorAll('[data-lines="class"] > *')].map((el) => el.textContent);
    const amounts = [...box.querySelectorAll('[data-lines="amount"] > *')].map((el) => el.textContent);
    expect(classes).toEqual(['Water 5/8"', 'Water 2"']);
    expect(amounts).toEqual(["$150.00", "$600.00"]);
  });
});

describe("DEF-RAT-9740 · a typed deposit rule (ref: null) is drawn, never a crash", () => {
  it("the plan's own Residential $150.00 row reads as a Deposit, and the page stands", () => {
    // `plan_reads._deposits` serves a typed `plan_deposit_rules` row with
    // `ref: None` BY DESIGN. Red first: TypeError: Cannot read properties of
    // null (reading 'id') — the move-in's *See full rates* and the plan's
    // Billing tab both went to the application error page.
    const typed = normalisePlanSections({
      currency: "USD",
      deposits: [
        {
          ref: null,
          priced_by: "class",
          rows: [{ class_or_size_label: "Residential", amount_display: "150.00" }],
          gl: null,
        },
      ],
    });
    render(
      <MemoryRouter initialEntries={["/brazosbend/plans-rates/plans/p1"]}>
        <Routes>
          <Route
            path="/:tenant/plans-rates/plans/:planId"
            element={
              <PlanSections
                sections={typed}
                show={["deposits"]}
                t={t}
                dateFormat="MM/DD/YYYY"
                timeZone="America/Chicago"
                links
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    const box = section("deposits");
    expect(within(box).getByText("Residential")).toBeInTheDocument();
    expect(within(box).getByText("$150.00")).toBeInTheDocument();
    expect(within(box).getAllByText("Deposit").length).toBeGreaterThan(0);
  });
});

describe("CR-167 follow-up · sizes, the rate word and the service name (DEF-RAT-9507, 9508, 9509)", () => {
  it("DEF-RAT-9507: base charges by size read smallest first, whatever order they are served in", () => {
    const water = SECTIONS.services[0];
    const served = normalisePlanSections({
      ...SECTIONS,
      services: [
        {
          ...water,
          base: {
            ...water.base,
            by_size: [
              { size_class: "1", size_label: 'Water 1"', amount_display: "18.00" },
              { size_class: "1_5", size_label: 'Water 1½"', amount_display: "30.00" },
              { size_class: "3_4", size_label: 'Water 3/4"', amount_display: "12.00" },
              { size_class: "5_8", size_label: 'Water 5/8"', amount_display: "10.00" },
            ],
          },
        },
      ],
    });
    expect(baseLines(served.services[0], "USD", t).map((line) => line.size)).toEqual([
      'Water 5/8"',
      'Water 3/4"',
      'Water 1"',
      'Water 1½"',
    ]);
  });

  it("DEF-RAT-9508: the usage RATE column is a unit price, never a tax rate, in every catalogue", () => {
    const taxWords = ["税率", "세율", "Aliquota", "Alíquota"];
    for (const lng of ["de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]) {
      const word = i18n.t("rating.planSections.service.rate", { lng }) as string;
      expect(taxWords.some((tax) => word.includes(tax)), `${lng}: ${word}`).toBe(false);
    }
  });

  it("DEF-RAT-9509: a service heading is the catalogue's word for the service, not the server's English", async () => {
    await i18n.changeLanguage("ja-JP");
    try {
      mount({ show: ["services"] });
      const water = document.querySelector('[data-plan-service="water"]') as HTMLElement;
      expect(within(water).getAllByText(i18n.t("rating.service.water") as string).length).toBeGreaterThan(0);
      expect(within(water).queryByText("Water")).toBeNull();
    } finally {
      await i18n.changeLanguage("en");
    }
  });

  it("DEF-RAT-9518: the services' totals outside-city line names the services in the screen's language", async () => {
    await i18n.changeLanguage("ja-JP");
    try {
      mount({ show: ["services", "servicesTotals"] });
      const terms = document.querySelector('[data-plan-section="servicesTotals"]') as HTMLElement;
      expect(terms.textContent).toContain(i18n.t("rating.service.water") as string);
      expect(terms.textContent).not.toContain("Water");
    } finally {
      await i18n.changeLanguage("en");
    }
  });

  it("DEF-RAT-9518: a folded service's one line words its rate in the language, never the server's English", async () => {
    const section = normalisePlanSections({
      ...SECTIONS,
      services: [
        {
          ...SECTIONS.services[0],
          usage: {
            kind: "blocks",
            kind_label: "Block (per month)",
            rows: [
              { label: "0 – 5 kgal", rate_display: "$4.00 per kgal", rate_amount: "$4.00", rate_unit: "kgal" },
              { label: "Over 5 kgal", rate_display: "$8.00 per kgal", rate_amount: "$8.00", rate_unit: "kgal" },
            ],
          },
        },
      ],
    }).services[0];
    await i18n.changeLanguage("ja-JP");
    try {
      const line = foldedServiceLine(section, "USD", t);
      expect(line.usage).not.toContain("per");
      expect(line.usage).toContain("$4.00");
      expect(line.usage).toContain("$8.00");
    } finally {
      await i18n.changeLanguage("en");
    }
  });
});
