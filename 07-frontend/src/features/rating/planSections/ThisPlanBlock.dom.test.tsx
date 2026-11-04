// @vitest-environment jsdom
// DEF-CUS-9821 — the This-plan block, built to the PO-approved drawing
// (claude.ai/artifact/9poRZzcU1ooxCw9A78jXgy). What would make these pass
// wrongly: a warning keyed on "no base found" (Solar's pooled code would hide
// it — the `named: false` case below fails it); links asserted by text only
// (each is asserted by `target` and by its address under the real tenant).
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { THIS_PLAN_COLLAPSED, ThisPlanBlock, planWarnings } from "./ThisPlanBlock";
import { DRAWN_DETAIL, DRAWN_PLAN_ID, DRAWN_RAW, DRAWN_SECTIONS } from "./thisPlanFixture";
import { normalisePlanSections } from "@/api/planFormEndpoints";
import type { PlanSections } from "@/api/planFormEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const TENANT = "annarbor";

function mount(sections: PlanSections = DRAWN_SECTIONS, services = ["battery", "solar"], className: string | null = "Residential") {
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/connections/new?step=2`]}>
      <Routes>
        <Route
          path="/:tenant/connections/new"
          element={
            <ThisPlanBlock
              planId={DRAWN_PLAN_ID}
              detail={DRAWN_DETAIL}
              sections={sections}
              services={services}
              className={className}
              t={t}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ThisPlanBlock — the drawing's eight parts", () => {
  it("draws the summary strip with the drawn facts", () => {
    const { container } = mount();
    const strip = container.querySelector('[data-facts="this-plan-summary"]');
    expect(strip).not.toBeNull();
    const text = strip?.textContent ?? "";
    for (const word of ["Code", "MBSP", "Version", "v1", "Published", "In force", "10/01/2026 → open", "Account type", "Every class", "Minimum bill", "None", "Covers", "2 of 2 services"]) {
      expect(text).toContain(word);
    }
  });

  it("draws Base charges and Usage rates OPEN, the other five CLOSED with a summary", () => {
    const { container } = mount();
    expect(container.querySelector('[data-this-plan-part="base"]')).not.toBeNull();
    expect(container.querySelector('[data-this-plan-part="usage"]')).not.toBeNull();
    for (const part of THIS_PLAN_COLLAPSED) {
      expect(container.querySelector(`[data-this-plan-part="${part}"]`), part).toBeNull();
    }
    const text = container.textContent ?? "";
    expect(text).toContain("Battery not chosen · Solar $10.00"); // the clerk's order
    expect(text).toContain("2 rate schedules");
    expect(text).toContain("2 · Late payment fee 1.50% · min $5.00 · Connection fee $25.00");
    expect(text).toContain("Residential $150.00 · Commercial $300.00");
    expect(text).toContain("2 · 8.00% total");
    // ⊕ `DEF-CUS-9836` — by NAME, as drawn; it read `CAP 10% · AUTOPAY $1.00`.
    expect(text).toContain("2 · CAP / low-income credit 10% · Autopay $1.00");
    expect(text).toContain("Same price");
    expect(container.querySelectorAll('button[aria-expanded="false"]')).toHaveLength(5);
    expect(container.querySelectorAll('button[aria-expanded="true"]')).toHaveLength(2);
  });

  it("Base charges: BASE-SOL links, Battery is Not chosen with dashes", () => {
    const { container } = mount();
    const base = container.querySelector('[data-this-plan-part="base"]') as HTMLElement;
    const solar = within(base).getByRole("link", { name: /BASE-SOL/ });
    expect(solar).toHaveAttribute("target", "_blank");
    expect(solar).toHaveAttribute("href", `/${TENANT}/plans-rates/charge-codes/bc-sol`);
    expect(base.querySelector('[data-base-not-chosen="battery"]')?.textContent).toBe("Not chosen");
    expect(base.textContent).toContain("Month");
    expect(base.textContent).toContain("Residential");
  });

  it("Usage rates: unit prices keep four places, the schedule links in a new tab", () => {
    const { container } = mount();
    const usage = container.querySelector('[data-this-plan-part="usage"]') as HTMLElement;
    expect(usage.textContent).toContain("$0.0425");
    expect(usage.textContent).toContain("V1 from 10/01/2026");
    const link = within(usage).getByRole("link", { name: /Municipal Battery Service Rate/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("href", `/${TENANT}/plans-rates/rates/sch-bat`);
  });

  it("Taxes expands to authority, rate, what is taxed and classes", async () => {
    const { container } = mount();
    await userEvent.click(screen.getByRole("button", { name: /^Taxes/ }));
    const taxes = container.querySelector('[data-this-plan-part="taxes"]') as HTMLElement;
    expect(taxes).not.toBeNull();
    for (const word of ["State sales tax", "State of Michigan", "6.00%", "Every class", "City of Ann Arbor", "2.00%", "Residential, Commercial"]) {
      expect(taxes.textContent).toContain(word);
    }
    expect(within(taxes).getByRole("link", { name: /State sales tax/ })).toHaveAttribute("target", "_blank");
  });

  it("Other charges, Deposit and Discounts open to the drawn columns", async () => {
    const { container } = mount();
    await userEvent.click(screen.getByRole("button", { name: /^Other charges/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Deposit/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Discounts/ }));
    const charges = container.querySelector('[data-this-plan-part="charges"]')?.textContent ?? "";
    expect(charges).toContain("After the due date");
    expect(charges).toContain("5 calendar days");
    const deposit = container.querySelector('[data-this-plan-part="deposit"]')?.textContent ?? "";
    expect(deposit).toContain("$300.00");
    expect(deposit).toContain("Yes");
    const discounts = container.querySelector('[data-this-plan-part="discounts"]')?.textContent ?? "";
    expect(discounts).toContain("Applied for");
    expect(discounts).toContain("Automatic");
    expect(discounts).toContain("Needed");
  });

  it("every link opens a new tab, Open the plan included", () => {
    mount();
    const links = screen.getAllByRole("link");
    expect(links.length).toBeGreaterThan(4);
    for (const link of links) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link.getAttribute("href")).toMatch(new RegExp(`^/${TENANT}/plans-rates/`));
    }
    expect(screen.getByRole("link", { name: /Open the plan/ })).toHaveAttribute("href", `/${TENANT}/plans-rates/plans/${DRAWN_PLAN_ID}`);
  });

  it("the footer names the class, and never the not-zero sentence", () => {
    const { container } = mount();
    expect(container.textContent).toContain("Figures come from the plan, for Residential accounts at this address.");
    expect(container.textContent).not.toContain("It is not zero");
  });
});

describe("ThisPlanBlock — a warning only when it is true", () => {
  it("Battery's schedule names no base code: one warning, linked to the schedule", () => {
    const { container } = mount();
    const warning = container.querySelector('[data-warning="this-plan-noBaseCode"]') as HTMLElement;
    expect(warning.textContent).toContain("Battery: its rate schedule names no base code.");
    const link = within(warning).getByRole("link", { name: /Choose a base code/ });
    expect(link).toHaveAttribute("href", `/${TENANT}/plans-rates/rates/sch-bat`);
    expect(link).toHaveAttribute("target", "_blank");
    expect(container.querySelectorAll("[data-warning]")).toHaveLength(1);
  });

  it("no warning when every schedule names its code and the plan covers every service", () => {
    expect(planWarnings(DRAWN_SECTIONS, ["solar"])).toEqual([]);
    const { container } = mount(DRAWN_SECTIONS, ["solar"]);
    expect(container.querySelectorAll("[data-warning]")).toHaveLength(0);
  });

  it("a service the address takes and the plan does not cover", () => {
    expect(planWarnings(DRAWN_SECTIONS, ["solar", "water"]).map((w) => [w.kind, w.service])).toEqual([["notCovered", "water"]]);
    const { container } = mount(DRAWN_SECTIONS, ["solar", "water"]);
    expect(container.textContent).toContain("Water: not in this plan.");
  });

  it("a base price not set, and an older server that sends no `named` says nothing", () => {
    const raw = structuredClone(DRAWN_RAW);
    Object.assign(raw.services[0].base, { state: "refused", flat_display: null });
    delete (raw.services[1].base as { named?: boolean }).named;
    const kinds = planWarnings(normalisePlanSections(raw), ["solar", "battery"]).map((w) => [w.kind, w.service]);
    expect(kinds).toEqual([["priceNotSet", "solar"]]);
  });
});
