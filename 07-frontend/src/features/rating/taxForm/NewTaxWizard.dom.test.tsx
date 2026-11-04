// @vitest-environment jsdom
// CR-165-BRC10 task 4 — the New tax or fee form, mounted under its REAL route
// pattern (hard-won law 2's fixture clause), against a fake API that answers
// the round-2 contract.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, TaxJurisdiction, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { TAX_WIZARD_NEW_ROUTE } from "../definitionDetail";
import appSource from "../../../App.tsx?raw";
import { NewTaxWizard } from "./NewTaxWizard";

afterEach(cleanup);

const TENANT = "brazosbend";

const SERVICES = [
  { service: "electric", name: "Electric", enabled: true },
  { service: "water", name: "Water", enabled: true },
  { service: "gas", name: "Gas", enabled: false },
  { service: "storm_water", name: "Storm water", enabled: false },
] as unknown as TenantServiceRow[];

const JURISDICTIONS: TaxJurisdiction[] = [
  { id: "j-state", name: "State", authority: "TX Comptroller", level: "state", reference_no: null },
];

const FORM_OPTIONS = {
  boundaries: [
    { value: "everywhere", label: "SERVER FALLBACK everywhere" },
    { value: "city_limits", label: "SERVER FALLBACK city" },
    { value: "school_district", label: "School district" },
  ],
  due_rules: [{ value: "20th_next_month", label: "20th of the next month" }],
  bases: [
    { value: "percent", label: "A percentage of the bill" },
    { value: "flat_per_bill", label: "A fixed amount per bill" },
  ],
  filing_frequencies: [{ value: "monthly", label: "Monthly" }],
};

function permissions(): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  };
}

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

function fakeClient(sent: Sent[], opts: { formOptions: boolean }) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
      sent.push({ method, url, body });
      const json = (status: number, payload: unknown) =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (url.includes("/taxes/form-options")) {
        return opts.formOptions ? json(200, FORM_OPTIONS) : json(404, { code: "NOT_FOUND", message_key: "x" });
      }
      if (url.includes("/settings/authority-accounts")) return json(404, { code: "NOT_FOUND", message_key: "x" });
      if (url.includes("/ledger/accounts")) {
        return json(200, { rows: [{ account_id: "gl-1", code: "2200-02", name: "Tax payable · State" }] });
      }
      if (url.includes("/taxes/matched-premises")) {
        return json(200, {
          count: 78,
          total: 84,
          sample: [{ id: "p1", premise_no: "P-00001", address_line: "101 Silver Creek Rd", city: "Ottumwa" }],
          resolvable: true,
          everywhere: true,
          narrowed: false,
        });
      }
      if (url.includes("/taxes/tax-src") && method === "GET") return json(200, SOURCE_TAX);
      if (url.includes("/taxes/tax-meter") && method === "GET") return json(200, { ...SOURCE_TAX, id: "tax-meter", kind: "per_meter", rate: null, per_meter_amount: "1.250000" });
      if (url.includes("/taxes/tax-draft") && method === "GET") return json(200, { ...SOURCE_TAX, id: "tax-draft", status: "draft", code: "CITY-PERMIT", name: "City permit fee" });
      if (url.includes("/taxes/tax-draft") && method === "PATCH") return json(200, { ...SOURCE_TAX, id: "tax-draft", name: "City permit fee" });
      if (url.includes("/taxes/tax-draft/activate") && method === "POST") return json(200, { ...SOURCE_TAX, id: "tax-draft", name: "City permit fee", status: "active" });
      if (url.endsWith("/taxes") && method === "POST") {
        return json(201, { id: "tax-1", name: body?.name ?? "" });
      }
      return json(200, {});
    },
  });
}

/** Duplicate's source (DEF-RAT-9299): County utility tax, 2 % on water and sewer. */
const SOURCE_TAX = {
  id: "tax-src",
  name: "County utility tax",
  code: "CNTY-UTIL",
  jurisdiction: { id: "j-state", name: "State" },
  kind: "percent",
  rate: "0.020000",
  applies_to_services: ["water"],
  applies_to_customer_classes: [],
  premises_scope_kind: null,
  premises_scope_value: "",
  base_includes_usage: true,
  base_includes_base: true,
  effective_from: "2026-01-01",
  effective_to: null,
  discount_treatment: "after",
  rounding_rule: "half_up",
  bill_label: "County tax",
  liability_gl_account_id: "gl-1",
  filing_frequency: "monthly",
  due_date_rule: "20th_next_month",
  authority_account: null,
  collection_allowance_percent: null,
  interest_penalty_percent: null,
  filing_reminder_recipient: "",
  version: 1,
  status: "active",
};

function renderForm(opts: { formOptions?: boolean; query?: string } = {}) {
  const sent: Sent[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(queryKeys.taxJurisdictions, JURISDICTIONS);
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${TAX_WIZARD_NEW_ROUTE}${opts.query ?? ""}`]}>
          <Routes>
            <Route
              path={`/:tenant${TAX_WIZARD_NEW_ROUTE}`}
              element={
                <NewTaxWizard
                  client={fakeClient(sent, { formOptions: opts.formOptions ?? true })}
                  dateFormat="MM/DD/YYYY"
                  timeZone="America/Chicago"
                />
              }
            />
            <Route path={`/:tenant/plans-rates/taxes-fees`} element={<p>the list</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return sent;
}

async function fillStepOne(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Name on bill/), "State sales tax");
  await user.selectOptions(screen.getByLabelText(/^Authority/), "j-state");
}

describe("NewTaxWizard · the drawn four steps", () => {
  it("the rail is What it is · How much · Filing · Review & save", async () => {
    renderForm();
    const rail = await screen.findByRole("navigation");
    expect(within(rail).getAllByRole("button").map((b) => b.textContent?.replace(/^\d/, ""))).toEqual([
      "What it is",
      "How much",
      "Filing",
      "Review & save",
    ]);
  });
});

describe("P1 · Services offers only the switched-on services, All services first", () => {
  it("Electric and Water — never Gas or Storm water", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(await screen.findByRole("button", { name: /^Services/ }));
    const list = screen.getByRole("group", { name: "Services" });
    const labels = within(list).getAllByRole("checkbox").map((box) => box.closest("label")?.textContent);
    expect(labels).toEqual(["All services", "Electric", "Water"]);
  });
});

describe("step validation · Continue names each missing box", () => {
  it("an empty step 1 says Fix 2 things first and marks both boxes", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Fix 2 things first.")).toBeInTheDocument();
    expect(screen.getByText("Enter the name on the bill.")).toBeInTheDocument();
    expect(screen.getByText("Choose an authority.")).toBeInTheDocument();
    // Still on step 1, and nothing was posted.
    expect(screen.getByLabelText(/Name on bill/)).toBeInTheDocument();
  });

  it("nothing typed is lost going forward and back", async () => {
    const user = userEvent.setup();
    renderForm();
    await screen.findByLabelText(/Name on bill/);
    await fillStepOne(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByRole("textbox", { name: /^Rate/ }), "6.25");
    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByLabelText(/Name on bill/)).toHaveValue("State sales tax");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("textbox", { name: /^Rate/ })).toHaveValue("6.25");
  });
});

describe("P9 · 150 typed is flagged on step 2", () => {
  it("warns with the rate it read", async () => {
    const user = userEvent.setup();
    renderForm();
    await screen.findByLabelText(/Name on bill/);
    await fillStepOne(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByRole("textbox", { name: /^Rate/ }), "150");
    expect(screen.getByText("150% is high. Check the rate.")).toBeInTheDocument();
    expect(screen.getByText("Check the rate")).toBeInTheDocument();
  });
});

describe("DEF-RAT-9275 · Save draft & exit sends as_draft: true", () => {
  it("posts the draft flag and leaves for the list", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await screen.findByLabelText(/Name on bill/);
    await fillStepOne(user);
    await user.click(screen.getByRole("button", { name: "Save draft & exit" }));
    await screen.findByText("the list");
    const post = sent.find((call) => call.method === "POST" && call.url.endsWith("/taxes"));
    expect(post?.body?.as_draft).toBe(true);
  });

  it("an empty name stops the draft at step 1 instead of posting", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await user.click(await screen.findByRole("button", { name: "Save draft & exit" }));
    expect(await screen.findByText("Enter the name on the bill.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });
});

describe("6.25 typed → 6.25% on the bill, end to end", () => {
  it("reads 6.25% on Review, $3.75 on the example bill, and sends 0.0625", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await screen.findByLabelText(/Name on bill/);
    await fillStepOne(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByRole("textbox", { name: /^Rate/ }), "6.25");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: "2026-10-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.selectOptions(await screen.findByLabelText(/^Liability account/), "gl-1");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const rate = await screen.findByText("6.25% of the bill");
    expect(rate).toBeInTheDocument();
    expect(document.querySelector("[data-tax-example-effect]")?.textContent).toBe("$3.75");
    await user.click(screen.getByRole("button", { name: "Save tax" }));
    await screen.findByText("State sales tax saved");
    const post = sent.find((call) => call.method === "POST" && call.url.endsWith("/taxes"));
    expect(post?.body?.rate).toBe("0.0625");
    expect("as_draft" in (post?.body ?? {})).toBe(false);
  });
});

describe("rule 35 · the server's lists read in the catalogue's words", () => {
  it("a known value shows the catalogue word; an unknown one shows the server's label", async () => {
    renderForm();
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Everywhere this utility serves" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("option", { name: "Inside city limits" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "School district" })).toBeInTheDocument();
    expect(screen.queryByText(/SERVER FALLBACK/)).toBeNull();
  });
});

describe("hard-won law 2 · the New door opens THIS form", () => {
  it("App mounts NewTaxWizard at the new route; round 3 moved edit to EditTaxForm", () => {
    expect(appSource).toContain("{ path: TAX_WIZARD_NEW_ROUTE.slice(1), element: <NewTaxWizard /> }");
    // The hold this test carried ("edit stays on TaxWizard until round 3")
    // expired on 2026-10-03 (CR-165 task 7) and is asserted the other way.
    expect(appSource).toContain("{ path: TAX_WIZARD_EDIT_PATTERN.slice(1), element: <EditTaxForm /> }");
    expect(appSource).not.toContain("{ path: TAX_WIZARD_NEW_ROUTE.slice(1), element: <TaxWizard /> }");
  });
});

describe("a route that is not served yet is an empty list, never a broken step", () => {
  it("renders step 1 with no form-options and no authority accounts", async () => {
    renderForm({ formOptions: false });
    expect(await screen.findByLabelText(/Name on bill/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(/^Boundary/)).toBeInTheDocument());
  });
});

describe("Duplicate (image 21, DEF-RAT-9299) — the New form opens filled from a tax", () => {
  it("?duplicate=<id> fills every box from that tax except the code, and saves a NEW tax", async () => {
    const user = userEvent.setup();
    const sent = renderForm({ query: "?duplicate=tax-src" });
    expect(await screen.findByDisplayValue("County utility tax")).toBeInTheDocument();
    expect((screen.getByLabelText(/^Authority/) as HTMLSelectElement).value).toBe("j-state");
    expect(sent.some((call) => call.method === "GET" && call.url.includes("/taxes/tax-src"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByDisplayValue("2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const code = (await screen.findByLabelText(/^Code/)) as HTMLInputElement;
    expect(code.value).toBe("");
    expect(screen.getByDisplayValue("County tax")).toBeInTheDocument();
  });

  it("without the parameter the form opens empty and reads no tax", async () => {
    const sent = renderForm();
    expect(await screen.findByLabelText(/Name on bill/)).toHaveValue("");
    expect(sent.some((call) => call.url.includes("/taxes/tax-"))).toBe(false);
  });
});

describe("Finishing a draft (DEF-RAT-9305) — ?draft=<id> saves IN PLACE", () => {
  it("opens filled from the draft, code kept; Save tax PATCHes the draft then activates it, and creates nothing", async () => {
    const user = userEvent.setup();
    const sent = renderForm({ query: "?draft=tax-draft" });
    expect(await screen.findByDisplayValue("City permit fee")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(((await screen.findByLabelText(/^Code/)) as HTMLInputElement).value).toBe("CITY-PERMIT");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Save tax" }));
    await waitFor(() => expect(sent.some((call) => call.method === "POST" && call.url.includes("/taxes/tax-draft/activate"))).toBe(true));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.url).toContain("/taxes/tax-draft");
    expect(Object.keys(patch?.body ?? {})).not.toContain("as_draft");
    expect(sent.some((call) => call.method === "POST" && call.url.endsWith("/taxes"))).toBe(false);
  });

  it("Save draft & exit on a draft PATCHes it and leaves it a draft", async () => {
    const user = userEvent.setup();
    const sent = renderForm({ query: "?draft=tax-draft" });
    expect(await screen.findByDisplayValue("City permit fee")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save draft & exit" }));
    await waitFor(() => expect(sent.some((call) => call.method === "PATCH" && call.url.includes("/taxes/tax-draft"))).toBe(true));
    expect(sent.some((call) => call.url.includes("/activate"))).toBe(false);
    expect(sent.some((call) => call.method === "POST" && call.url.endsWith("/taxes"))).toBe(false);
  });
});

describe("THIS TAX panel — no confident wrong figure (DEF-RAT-9306)", () => {
  it("a per-meter tax reads a dash on a $60.00 bill, never $0.00", async () => {
    renderForm({ query: "?duplicate=tax-meter" });
    expect(await screen.findByDisplayValue("County utility tax")).toBeInTheDocument();
    const effect = document.querySelector("[data-tax-summary-effect]");
    expect(effect?.textContent).toBe("—");
  });

  it("a percentage still reads its figure: 2% on $60.00 is $1.20", async () => {
    renderForm({ query: "?duplicate=tax-src" });
    expect(await screen.findByDisplayValue("County utility tax")).toBeInTheDocument();
    expect(document.querySelector("[data-tax-summary-effect]")?.textContent).toBe("$1.20");
  });
});
