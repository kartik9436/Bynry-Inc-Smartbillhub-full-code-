// @vitest-environment jsdom
// DEF-RAT-10027 (PO ruling 2026-10-09, option (a)) and DEF-RAT-10028 — the
// Filing step of EDIT a tax, mounted under its REAL route pattern (hard-won law
// 2's fixture clause), against a fake API.
//
//   10028 · a select must show its SAVED value. A chart of 60 accounts with the
//           saved one 57th; a saved liability account that is no longer active
//           (so not among the options); a retired registration number. Each
//           shows the tax's own label, never the placeholder.
//   10027 · the field is the tax registration number with the authority: its
//           label, the options narrowed to the tax's authority (unlinked rows
//           still offered), the chosen authority and number under the field and
//           in the THIS TAX panel, and an empty note that names the authority
//           and opens Settings › Accounting › Tax filing accounts directly.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, TaxJurisdiction, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { TAX_WIZARD_EDIT_PATTERN } from "../definitionDetail";
import { taxRowDefaults } from "../taxRowFixture";
import { EditTaxForm } from "./EditTaxForm";
import { taxEditPath } from "./taxEditModel";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const TENANT = "queenwest";

const JURISDICTIONS: TaxJurisdiction[] = [
  { id: "j-city", name: "City of Queen West Finance", authority: null, level: "city", reference_no: null },
  { id: "j-state", name: "State Department of Revenue", authority: null, level: "state", reference_no: null },
] as unknown as TaxJurisdiction[];

const FORM_OPTIONS = {
  boundaries: [{ value: "everywhere", label: "Everywhere this utility serves" }],
  due_rules: [{ value: "20th_next_month", label: "20th of the next month" }],
  bases: [{ value: "percent", label: "A percentage of the bill" }],
  filing_frequencies: [{ value: "monthly", label: "Monthly" }],
};

/** Sixty accounts, in code order — the saved one is the 57th. */
const CHART = Array.from({ length: 60 }, (_, index) => ({
  account_id: `gl-${index + 1}`,
  code: String(2000 + (index + 1) * 5),
  name: `Account ${index + 1}`,
}));

const CITY_NUMBER = {
  id: "acct-city",
  authority_name: "City of Queen West Finance",
  account_number: "CQW-FR-0091",
  jurisdiction_id: "j-city",
  active: true,
};
const STATE_NUMBER = {
  id: "acct-state",
  authority_name: "State Department of Revenue",
  account_number: "32-1180544",
  jurisdiction_id: "j-state",
  active: true,
};
const TYPED_NUMBER = {
  id: "acct-typed",
  authority_name: "Queen West (typed)",
  account_number: "QW-1",
  jurisdiction_id: null,
  active: true,
};

/** City Utility Franchise Fee 2% — every filing field saved. */
function franchiseFee(overrides: Record<string, unknown> = {}) {
  return {
    ...taxRowDefaults(),
    id: "tax-ff",
    name: "City Utility Franchise Fee",
    jurisdiction: JURISDICTIONS[0],
    kind: "percent",
    rate: "0.020000",
    rate_display: "2%",
    effective_from: "2026-01-01",
    code: "CUFF",
    liability_gl_account_id: "gl-57",
    gl_account_code: "2285",
    gl_account_name: "Account 57",
    filing_frequency: "monthly",
    due_date_rule: "20th_next_month",
    collection_allowance_percent: "0.005000",
    interest_penalty_percent: "0.015000",
    version: 1,
    authority_account: { id: "acct-city", label: "City of Queen West Finance · CQW-FR-0091" },
    ...overrides,
  };
}

function permissions(): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  };
}

interface World {
  tax: Record<string, unknown>;
  chart?: typeof CHART;
  numbers?: (typeof CITY_NUMBER)[];
}

function fakeClient(world: World) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      const json = (status: number, payload: unknown) =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (url.includes("/taxes/form-options")) return json(200, FORM_OPTIONS);
      if (url.includes("/settings/authority-accounts")) {
        const rows = world.numbers ?? [CITY_NUMBER, STATE_NUMBER, TYPED_NUMBER];
        return json(200, { count: rows.length, next: null, previous: null, results: rows });
      }
      if (url.includes("/ledger/accounts")) return json(200, { rows: world.chart ?? CHART });
      if (url.includes("/taxes/matched-premises")) {
        return json(200, { count: 84, total: 84, sample: [], resolvable: true, everywhere: true, narrowed: false });
      }
      if (url.endsWith("/taxes/tax-ff")) return json(200, world.tax);
      return json(200, {});
    },
  });
}

async function openFiling(world: World) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(queryKeys.taxJurisdictions, JURISDICTIONS);
  queryClient.setQueryData(queryKeys.tenantServices, [] as TenantServiceRow[]);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${taxEditPath("tax-ff", "info")}`]}>
          <Routes>
            <Route
              path={`/:tenant${TAX_WIZARD_EDIT_PATTERN}`}
              element={<EditTaxForm client={fakeClient(world)} dateFormat="MM/DD/YYYY" timeZone="America/Chicago" />}
            />
            <Route path="/:tenant/settings/:tab/:sub" element={<p>settings sub-tab</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await screen.findByLabelText(/Name on bill/);
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByLabelText(/^Liability account/);
  return user;
}

function shownOf(id: string): string {
  const select = document.getElementById(id) as HTMLSelectElement;
  return select.options[select.selectedIndex]?.text ?? "";
}

async function settled(id: string, text: RegExp | string) {
  await screen.findByText(text, { selector: `#${id} option` });
}

describe("DEF-RAT-10028 · Edit → Name and filing → step 2 shows every saved value", () => {
  it("a chart of 60 accounts with the saved one 57th: the liability account shows it", async () => {
    await openFiling({ tax: franchiseFee() });
    await settled("tax-liability", "2285 · Account 57");
    expect(shownOf("tax-liability")).toBe("2285 · Account 57");
    expect(screen.getByLabelText(/^Code/)).toHaveValue("CUFF");
    expect(shownOf("tax-due")).toBe("20th of the next month");
    expect(screen.getByLabelText(/^Allowance you keep/)).toHaveValue("0.5");
    expect(screen.getByLabelText(/^Late-filing interest/)).toHaveValue("1.5");
    expect(shownOf("tax-authority-account")).toBe("City of Queen West Finance · CQW-FR-0091");
  });

  it("a saved liability account that is not among the options shows the tax's own label, not the placeholder", async () => {
    // Deactivated since the tax was saved: `f.status=active` leaves it out.
    const chart = CHART.filter((row) => row.account_id !== "gl-57");
    await openFiling({ tax: franchiseFee(), chart });
    await settled("tax-liability", "2280 · Account 56");
    expect(shownOf("tax-liability")).toBe("2285 · Account 57");
    expect(shownOf("tax-liability")).not.toBe(t("rating.taxForm.placeholder.liability"));
  });

  it("a retired registration number stays shown on the tax that files under it", async () => {
    await openFiling({ tax: franchiseFee(), numbers: [STATE_NUMBER] });
    await settled("tax-liability", "2285 · Account 57");
    expect(shownOf("tax-authority-account")).toBe("City of Queen West Finance · CQW-FR-0091");
  });

  it("a saved due rule the options have not delivered still reads in words", async () => {
    await openFiling({ tax: franchiseFee({ due_date_rule: "15th_next_month" }) });
    await settled("tax-liability", "2285 · Account 57");
    expect(shownOf("tax-due")).toBe(t("rating.taxForm.option.due.15th_next_month"));
  });
});

describe("DEF-RAT-10027 · the tax registration number with the authority", () => {
  it("the field is labelled as the registration number", async () => {
    await openFiling({ tax: franchiseFee() });
    expect(screen.getByLabelText(new RegExp(`^${t("rating.taxForm.field.authorityAccount")}`))).toBeInTheDocument();
    expect(t("rating.taxForm.field.authorityAccount")).toBe("Tax registration no.");
    expect(t("rating.taxForm.field.authorityAccount").split(" ").length).toBeLessThanOrEqual(3);
  });

  it("offers only the numbers held with the tax's authority, plus the unlinked ones", async () => {
    await openFiling({ tax: franchiseFee({ authority_account: null }) });
    await settled("tax-authority-account", /CQW-FR-0091/);
    const offered = Array.from((document.getElementById("tax-authority-account") as HTMLSelectElement).options)
      .map((option) => option.text)
      .filter((text) => text !== t("rating.taxForm.placeholder.authorityAccount"));
    expect(offered).toEqual(["City of Queen West Finance · CQW-FR-0091", "Queen West (typed) · QW-1"]);
  });

  it("once chosen, the authority and number show under the field and in the THIS TAX panel", async () => {
    await openFiling({ tax: franchiseFee() });
    await settled("tax-authority-account", /CQW-FR-0091/);
    const under = document.querySelector("[data-tax-authority-account-chosen]") as HTMLElement;
    expect(under).toHaveTextContent("City of Queen West Finance · CQW-FR-0091");
    const panel = document.querySelector("[data-tax-summary]") as HTMLElement;
    const fact = within(panel).getByText(t("rating.taxForm.summary.registration")).closest("div") as HTMLElement;
    expect(fact).toHaveTextContent("City of Queen West Finance · CQW-FR-0091");
  });

  it("with no number held with that authority, the note names it and Add one opens Tax filing accounts", async () => {
    const user = await openFiling({ tax: franchiseFee({ authority_account: null }), numbers: [STATE_NUMBER] });
    const note = await screen.findByText(
      t("rating.taxForm.help.authorityAccountNone", { authority: "City of Queen West Finance" }),
      { exact: false },
    );
    const link = within(note.closest("[data-tax-add-account]") as HTMLElement).getByRole("link", {
      name: t("rating.taxForm.addOne"),
    });
    expect(link).toHaveAttribute("href", `/${TENANT}/settings/accounting/authorities`);
    await user.click(link);
    expect(await screen.findByText("settings sub-tab")).toBeInTheDocument();
  });
});
