// @vitest-environment jsdom
// DEF-RAT-9832 — PO 2026-10-06: a rate schedule that names no base code bills
// a $0.00 base, and the clerk is asked to choose one. The server sends
// `state: "not_named"` with `flat_display: "0.00"`; nothing is taken from the
// charge-code pool. What would make these pass wrongly: an amount cell that
// renders any money string (the `$0.00` is asserted exactly, and the warning
// is asserted by its link to the schedule).
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { ThisPlanBlock } from "./ThisPlanBlock";
import { baseLines } from "./PlanSections";
import { DRAWN_DETAIL, DRAWN_PLAN_ID, DRAWN_RAW } from "./thisPlanFixture";
import { normalisePlanSections } from "@/api/planFormEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const TENANT = "annarbor";

/** The drawn plan, with Battery's schedule naming no base code while Battery
 *  HAS base codes in the catalogue — the `not_named` answer. */
function notNamedSections() {
  const raw = structuredClone(DRAWN_RAW) as typeof DRAWN_RAW;
  const battery = raw.services.find((line) => line.service === "battery");
  if (battery === undefined) throw new Error("fixture has no battery line");
  Object.assign(battery.base, { state: "not_named", flat_display: "0.00", monthly_amount: "0.0000", named: false });
  return normalisePlanSections(raw);
}

function mount() {
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/connections/new?step=2`]}>
      <Routes>
        <Route
          path="/:tenant/connections/new"
          element={
            <ThisPlanBlock
              planId={DRAWN_PLAN_ID}
              detail={DRAWN_DETAIL}
              sections={notNamedSections()}
              services={["battery", "solar"]}
              className="Residential"
              t={t}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("a schedule naming no base code (DEF-RAT-9832)", () => {
  it("keeps the server's not_named state", () => {
    const battery = notNamedSections().services.find((line) => line.service === "battery");
    expect(battery?.base.state).toBe("not_named");
  });

  it("Base charges reads $0.00 for it, with Choose a base code linked to the schedule", () => {
    const { container } = mount();
    const base = container.querySelector('[data-this-plan-part="base"]') as HTMLElement;
    const row = base.querySelector('[data-base-not-chosen="battery"]')?.closest("tr") as HTMLElement;
    expect(row.textContent).toContain("$0.00");
    expect(base.querySelector('[data-base-not-chosen="battery"]')?.textContent).toBe("Not chosen");
    const warning = container.querySelector('[data-warning="this-plan-noBaseCode"]') as HTMLElement;
    const link = within(warning).getByRole("link", { name: /Choose a base code/ });
    expect(link).toHaveAttribute("href", `/${TENANT}/plans-rates/rates/sch-bat`);
  });

  it("the shared plan sections show Every size $0.00", () => {
    const battery = notNamedSections().services.find((line) => line.service === "battery");
    if (battery === undefined) throw new Error("no battery");
    const lines = baseLines(battery, "USD", t);
    expect(lines.map((line) => line.base)).toEqual(["$0.00"]);
  });
});
