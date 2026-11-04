// @vitest-environment jsdom
// CR-165-BRC10 task 7 — EDIT a tax or fee (images 24–33), mounted under its
// REAL route pattern (hard-won law 2's fixture clause) at the exact address the
// details page links to, against a fake API that answers the round-2 contract.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, TaxJurisdiction, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { TAX_WIZARD_EDIT_PATTERN } from "../definitionDetail";
import { taxRowDefaults } from "../taxRowFixture";
import appSource from "../../../App.tsx?raw";
import { EditTaxForm } from "./EditTaxForm";
import { taxEditPath } from "./taxEditModel";
import type { TaxEditMode } from "./taxEditModel";

afterEach(cleanup);

const TENANT = "brazosbend";

const SERVICES = [
  { service: "solar", name: "Solar", enabled: true },
  { service: "battery", name: "Battery", enabled: true },
] as unknown as TenantServiceRow[];

const JURISDICTIONS: TaxJurisdiction[] = [
  { id: "j-city", name: "City", authority: "City of Ottumwa", level: "city", reference_no: null },
];

const FORM_OPTIONS = {
  boundaries: [
    { value: "everywhere", label: "Everywhere this utility serves" },
    { value: "city_limits", label: "Inside city limits" },
  ],
  due_rules: [{ value: "20th_next_month", label: "20th of the next month" }],
  bases: [
    { value: "percent", label: "A percentage of the bill" },
    { value: "flat_per_bill", label: "A fixed amount per bill" },
  ],
  filing_frequencies: [{ value: "monthly", label: "Monthly" }],
};

/** ann arbor City as images 24–33 draw it: 150 %, 09/01/2026 – 11/10/2027, v1. */
const ANN_ARBOR = {
  ...taxRowDefaults(),
  id: "tax-aa",
  name: "ann arbor City",
  jurisdiction: JURISDICTIONS[0],
  kind: "percent",
  rate: "1.500000",
  rate_display: "150%",
  applies_to_services: ["solar", "battery"],
  effective_from: "2026-09-01",
  effective_to: "2027-11-10",
  code: "AA-CITY",
  liability_gl_account_id: "gl-1",
  filing_frequency: "monthly",
  due_date_rule: "20th_next_month",
  collection_allowance_percent: "0.005000",
  interest_penalty_percent: "0.015000",
  filing_reminder_recipient: "filings@ottumwawater.example",
  version: 1,
  authority_account: { id: "acct-1", label: "City of Ottumwa Finance · OTT-0042" },
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

function fakeClient(sent: Sent[]) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
      sent.push({ method, url, body });
      const json = (status: number, payload: unknown) =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (url.includes("/taxes/form-options")) return json(200, FORM_OPTIONS);
      if (url.includes("/settings/authority-accounts")) {
        return json(200, {
          count: 1,
          next: null,
          previous: null,
          results: [{ id: "acct-1", authority_name: "City of Ottumwa Finance", account_number: "OTT-0042", jurisdiction_id: null, active: true }],
        });
      }
      if (url.includes("/ledger/accounts")) {
        return json(200, { rows: [{ account_id: "gl-1", code: "2200-01", name: "Tax payable · Local" }] });
      }
      if (url.includes("/taxes/matched-premises")) {
        return json(200, { count: 84, total: 84, sample: [], resolvable: true, everywhere: true, narrowed: false });
      }
      if (url.endsWith("/taxes/tax-aa/new-rate") && method === "POST") {
        return json(201, { ...ANN_ARBOR, id: "tax-aa-2", version: 2, rate: body?.rate, effective_from: body?.effective_from });
      }
      if (url.endsWith("/taxes/tax-aa/corrections") && method === "POST") {
        return json(201, { ...ANN_ARBOR, id: "tax-aa-2", version: 2, rate: body?.rate });
      }
      if (url.endsWith("/taxes/tax-aa") && method === "PATCH") return json(200, { ...ANN_ARBOR, ...body });
      if (url.endsWith("/taxes/tax-aa")) return json(200, ANN_ARBOR);
      return json(200, {});
    },
  });
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function renderEdit(mode: TaxEditMode) {
  const sent: Sent[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(queryKeys.taxJurisdictions, JURISDICTIONS);
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${taxEditPath("tax-aa", mode)}`]}>
          <Routes>
            <Route
              path={`/:tenant${TAX_WIZARD_EDIT_PATTERN}`}
              element={
                <>
                  <EditTaxForm client={fakeClient(sent)} dateFormat="MM/DD/YYYY" timeZone="America/Chicago" />
                  <Where />
                </>
              }
            />
            <Route path="/:tenant/plans-rates/taxes-fees/:definitionId" element={<p>the tax details</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return sent;
}

function railLabels(): string[] {
  const rail = screen.getByRole("navigation");
  return within(rail)
    .getAllByRole("button")
    .map((b) => (b.textContent ?? "").replace(/^[\d✓]/, ""));
}

describe("P44 · Edit is the SAME full-page form, with What to change on top", () => {
  it("the details page's address opens it: title, back link, three cards, Name and filing chosen", async () => {
    renderEdit("info");
    expect(await screen.findByRole("heading", { level: 1, name: "Edit ann arbor City" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ann arbor City/ })).toHaveAttribute(
      "href",
      `/${TENANT}/plans-rates/taxes-fees/tax-aa`,
    );
    const cards = screen.getByRole("radiogroup", { name: "What to change" });
    expect(within(cards).getAllByRole("radio").map((r) => r.closest("label")?.textContent)).toEqual([
      "Name and filingSaved on this version",
      "New rate from a dateMakes a new version",
      "Fix a mistakeSame dates, right rate",
    ]);
    expect(within(cards).getByRole("radio", { name: /Name and filing/ })).toBeChecked();
    expect(document.querySelector("[role=dialog]")).toBeNull();
  });

  it("P45 · each card is its own flow: Name · Filing · Review; New rate · Review; Fix the rate · Review", async () => {
    const user = userEvent.setup();
    renderEdit("info");
    await screen.findByRole("heading", { level: 1, name: "Edit ann arbor City" });
    expect(railLabels()).toEqual(["Name", "Filing", "Review & save"]);
    await user.click(screen.getByRole("radio", { name: /New rate from a date/ }));
    expect(railLabels()).toEqual(["New rate", "Review & save"]);
    expect(screen.getByTestId("where").textContent).toContain("change=change");
    await user.click(screen.getByRole("radio", { name: /Fix a mistake/ }));
    expect(railLabels()).toEqual(["Fix the rate", "Review & save"]);
    expect(screen.getByTestId("where").textContent).toContain("change=correct");
  });

  it("?change=correct opens Fix a mistake directly — the details page's Fix the rate door", async () => {
    renderEdit("correct");
    await screen.findByRole("heading", { level: 1, name: "Edit ann arbor City" });
    expect(screen.getByRole("radio", { name: /Fix a mistake/ })).toBeChecked();
    expect(screen.getByLabelText(/Why it was wrong/)).toBeInTheDocument();
  });
});

describe("Name and filing (images 24–27) → PATCH /taxes/{id}", () => {
  it("P46 · rate and reach are READ and locked; the name is a box", async () => {
    renderEdit("info");
    expect(await screen.findByLabelText(/Name on bill/)).toHaveValue("ann arbor City");
    expect(screen.getByText("Change with a new rate.")).toBeInTheDocument();
    const facts = document.querySelector("[data-facts=tax-rate-reach]") as HTMLElement;
    expect(within(facts).getByText("150% of the bill")).toBeInTheDocument();
    expect(within(facts).getByText("09/01/2026 – 11/10/2027")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /^Rate/ })).toBeNull();
  });

  it("the liability account is locked on Filing — CR-008 as amended", async () => {
    const user = userEvent.setup();
    renderEdit("info");
    await screen.findByLabelText(/Name on bill/);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByLabelText(/^Liability account/)).toBeDisabled();
    expect(screen.getByText("Changed in Settings › Accounting.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Filing reminder to/)).not.toBeDisabled();
  });

  it("P49 · Review shows before → after and v1 updated in place; Save sends ONLY the changed key", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("info");
    await screen.findByLabelText(/Name on bill/);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const reminder = await screen.findByLabelText(/^Filing reminder to/);
    await user.clear(reminder);
    await user.type(reminder, "tax@ottumwawater.example");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const change = (await screen.findByText("tax@ottumwawater.example")).closest("tr") as HTMLElement;
    expect(within(change).getByText("Filing reminder to")).toBeInTheDocument();
    expect(within(change).getByText("filings@ottumwawater.example")).toBeInTheDocument();
    const version = document.querySelector("[data-tax-version=this]") as HTMLElement;
    expect(version.textContent).toContain("v1 · this version");
    expect(version.textContent).toContain("Updated in place");
    expect(document.querySelector("[data-tax-example=edit]")).toBeNull(); // image 26 draws no bill
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Saved on this version. Logged in Audit.")).toBeInTheDocument();
    expect(document.querySelector("#tax-edit-saved-title")?.textContent).toBe("ann arbor City saved");
    expect(screen.getByText("Saved on this version. Logged in Audit.")).toBeInTheDocument();
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.url).toContain("/taxes/tax-aa");
    expect(patch?.body).toEqual({ filing_reminder_recipient: "tax@ottumwawater.example" });
    expect(sent.some((call) => call.body !== null && "liability_gl_account_id" in call.body)).toBe(false);
    await user.click(screen.getByRole("button", { name: "Back to tax" }));
    expect(await screen.findByText("the tax details")).toBeInTheDocument();
  });

  it("Save is held until something has changed", async () => {
    const user = userEvent.setup();
    renderEdit("info");
    await screen.findByLabelText(/Name on bill/);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByText("No changes yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});

describe("New rate from a date (images 28–30) → POST /taxes/{id}/new-rate", () => {
  it("image 29 · a start not after today's start: Must be after 09/01/2026, Fix 1 thing first", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("change");
    const rate = await screen.findByRole("textbox", { name: /^Rate/ });
    await user.clear(rate);
    await user.type(rate, "6.25");
    fireEvent.change(screen.getByLabelText(/^New rate starts/), { target: { value: "2026-08-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Must be after 09/01/2026.")).toBeInTheDocument();
    expect(screen.getByText("Fix 1 thing first.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });

  it("P47 · 6.25% from 11/01/2026: v1 ends 10/31/2026, $90.00 → $3.75, bills before keep 150%", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("change");
    const rate = await screen.findByRole("textbox", { name: /^Rate/ });
    await user.clear(rate);
    await user.type(rate, "6.25");
    fireEvent.change(screen.getByLabelText(/^New rate starts/), { target: { value: "2026-11-01" } });
    expect(screen.getByText("Today's rate ends 10/31/2026.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const rateRow = (await screen.findByText("Rate", { selector: "td" })).closest("tr") as HTMLElement;
    expect(rateRow.textContent).toContain("150%");
    expect(rateRow.textContent).toContain("6.25%");
    expect(document.querySelector("[data-tax-bill-before]")?.textContent).toBe("$90.00");
    expect(document.querySelector("[data-tax-bill-after]")?.textContent).toBe("$3.75");
    const today = document.querySelector("[data-tax-version=today]")?.textContent ?? "";
    expect(today).toContain("v1 · today");
    expect(today).toContain("09/01/2026 – 10/31/2026");
    expect(today).toContain("Gets an end date");
    const next = document.querySelector("[data-tax-version=next]")?.textContent ?? "";
    expect(next).toContain("v2 · new");
    expect(next).toContain("11/01/2026 – 11/10/2027");
    expect(screen.getByText("Bills before 11/01/2026 keep 150%.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save new rate" }));
    expect(await screen.findByText("v2 starts 11/01/2026. Logged in Audit.")).toBeInTheDocument();
    const post = sent.find((call) => call.method === "POST");
    expect(post?.url).toContain("/taxes/tax-aa/new-rate");
    expect(post?.body).toMatchObject({ kind: "percent", rate: "0.0625", effective_from: "2026-11-01", effective_to: "2027-11-10" });
    expect(Object.keys(post?.body ?? {})).not.toContain("base_includes_usage");
  });
});

describe("Fix a mistake (images 31–33) → POST /taxes/{id}/corrections", () => {
  it("dates are READ, not boxes: Same dates as today.", async () => {
    renderEdit("correct");
    expect(await screen.findByText("Same dates as today.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Starts/)).toBeNull();
    const dates = document.querySelector("[data-tax-dates=locked]") as HTMLElement;
    expect(dates.textContent).toContain("09/01/2026");
    expect(dates.textContent).toContain("11/10/2027");
  });

  it("P48 · image 32 — no reason: Enter the reason., Fix 1 thing first", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("correct");
    const rate = await screen.findByRole("textbox", { name: /^Rate/ });
    await user.clear(rate);
    await user.type(rate, "6.25");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Enter the reason.")).toBeInTheDocument();
    expect(screen.getByText("Fix 1 thing first.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });

  it("P50 · v1 superseded and kept, v2 replaces it, issued bills keep 150% — and the reason is sent", async () => {
    const user = userEvent.setup();
    const sent = renderEdit("correct");
    const rate = await screen.findByRole("textbox", { name: /^Rate/ });
    await user.clear(rate);
    await user.type(rate, "6.25");
    await user.type(screen.getByLabelText(/Why it was wrong/), "Rate typed as 150%.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Rate typed as 150%.", { selector: "p" })).toBeInTheDocument();
    const today = document.querySelector("[data-tax-version=today]")?.textContent ?? "";
    expect(today).toContain("Superseded, kept");
    expect(today).toContain("09/01/2026 – 11/10/2027");
    const next = document.querySelector("[data-tax-version=next]")?.textContent ?? "";
    expect(next).toContain("v2 · correction");
    expect(next).toContain("Replaces v1");
    expect(next).toContain("09/01/2026 – 11/10/2027");
    expect(screen.getByText("Issued bills keep 150%. Correct those bills separately.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save correction" }));
    expect(await screen.findByText("v2 replaces v1. Logged in Audit.")).toBeInTheDocument();
    const post = sent.find((call) => call.method === "POST");
    expect(post?.url).toContain("/taxes/tax-aa/corrections");
    expect(post?.body).toMatchObject({ kind: "percent", rate: "0.0625", reason: "Rate typed as 150%." });
    expect(Object.keys(post?.body ?? {})).not.toContain("effective_from");
    await user.click(screen.getByRole("button", { name: "Back to tax" }));
    expect(await screen.findByText("the tax details")).toBeInTheDocument();
  });
});

describe("hard-won law 2 · the Edit door opens THIS form", () => {
  it("App mounts EditTaxForm at the edit route; the old TaxWizard is mounted nowhere", () => {
    expect(appSource).toContain("{ path: TAX_WIZARD_EDIT_PATTERN.slice(1), element: <EditTaxForm /> }");
    expect(appSource).not.toContain("<TaxWizard />");
    expect(appSource).not.toContain('from "@/features/rating/TaxWizard"');
  });

  it("the details page's three addresses are the edit pattern plus ?change=", () => {
    expect(taxEditPath("tax-aa", "info")).toBe("/plans-rates/taxes-fees/tax-aa/edit?change=info");
    expect(taxEditPath("tax-aa", "change")).toBe("/plans-rates/taxes-fees/tax-aa/edit?change=change");
    expect(taxEditPath("tax-aa", "correct")).toBe("/plans-rates/taxes-fees/tax-aa/edit?change=correct");
  });
});
