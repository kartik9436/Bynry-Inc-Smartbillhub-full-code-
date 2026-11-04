// @vitest-environment jsdom
// CR-166-BRC10 round 2 task 4 — the New discount form, mounted under its REAL
// route pattern (hard-won law 2's fixture clause), against a fake API that
// answers the round-2 contract (CR-166 §9).
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { definitionWizardPath } from "../definitionDetail";
import appSource from "../../../App.tsx?raw";
import { NewDiscountWizard } from "./NewDiscountWizard";

afterEach(cleanup);

const TENANT = "brazosbend";
const NEW_ROUTE = definitionWizardPath("discount", null);

const SERVICES = [
  { service: "water", name: "Water", enabled: true, billed_uom: "kgal", primary_uom: "gal" },
  { service: "gas", name: "Gas", enabled: false, billed_uom: null, primary_uom: null },
] as unknown as TenantServiceRow[];

const FORM_OPTIONS = {
  program_owners: [
    { value: "billing", label: "Billing" },
    { value: "customer_service", label: "Customer service" },
  ],
  exclusivity_groups: [
    { value: "none", label: "None" },
    { value: "age_based", label: "Age-based" },
  ],
  eligibility: [
    { value: "everyone", label: "Everyone on the plan", checked_by: "system" },
    { value: "autopay_on", label: "Autopay is on", checked_by: "system" },
    { value: "age_65", label: "Age 65 or over", checked_by: "proof" },
  ],
  enrollment_modes: [
    { value: "automatic", label: "SERVER FALLBACK automatic" },
    { value: "apply_and_approve", label: "SERVER FALLBACK apply" },
  ],
  verification: [{ value: "annual_recertification", label: "Annual recertification" }],
  lapse: [{ value: "notify_then_drop", label: "Notify, then drop the enrollment" }],
  budget_periods: [{ value: "annual", label: "Annual" }],
  budget_out: [{ value: "suspend", label: "Suspend the discount" }],
  types: [
    { value: "percentage", label: "Percentage" },
    { value: "fixed_amount", label: "Fixed amount" },
    { value: "charge_waiver", label: "Charge waiver" },
    { value: "usage_allowance", label: "Usage allowance" },
  ],
  applies_to: [
    { value: "whole_bill", label: "Subtotal before taxes" },
    { value: "one_service", label: "One service" },
    { value: "named_codes", label: "Named charge codes" },
  ],
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
      if (url.includes("/discounts/form-options")) {
        return opts.formOptions ? json(200, FORM_OPTIONS) : json(404, { code: "NOT_FOUND", message_key: "x" });
      }
      if (url.includes("/charges")) {
        return json(200, {
          count: 2,
          next: null,
          previous: null,
          results: [
            { id: "c1", code: "BASE-W", name: "Water base" },
            { id: "c2", code: "USE-W", name: "Water usage" },
          ],
        });
      }
      if (url.includes("/shell/display")) {
        return json(200, { regional: { currency: "USD" }, company: {}, period: null });
      }
      if (url.endsWith("/discounts") && method === "POST") {
        return json(201, { id: "disc-1", name: body?.name ?? "" });
      }
      return json(200, {});
    },
  });
}

function renderForm(opts: { formOptions?: boolean } = {}) {
  const sent: Sent[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${NEW_ROUTE}`]}>
          <Routes>
            <Route
              path={`/:tenant${NEW_ROUTE}`}
              element={
                <NewDiscountWizard
                  client={fakeClient(sent, { formOptions: opts.formOptions ?? true })}
                  dateFormat="MM/DD/YYYY"
                  timeZone="America/Chicago"
                />
              }
            />
            <Route path={`/:tenant/plans-rates/discounts`} element={<p>the list</p>} />
            <Route path={`/:tenant/plans-rates/discounts/:id`} element={<p>the details</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return sent;
}

async function fillDetails(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText(/^Code/), "senior");
  await user.type(screen.getByLabelText(/^Bill line label/), "Senior discount");
  await waitFor(() => expect(screen.getByRole("option", { name: "Billing" })).toBeInTheDocument());
  await user.selectOptions(screen.getByLabelText(/^Program owner/), "billing");
  await user.type(screen.getByRole("textbox", { name: /^Percent off/ }), "15");
}

describe("NewDiscountWizard · three one-word steps", () => {
  it("the rail is Details · Eligibility · Review", async () => {
    renderForm();
    const rail = await screen.findByRole("navigation");
    expect(within(rail).getAllByRole("button").map((b) => b.textContent?.replace(/^\d/, ""))).toEqual([
      "Details",
      "Eligibility",
      "Review",
    ]);
  });
});

describe("every list comes from GET /discounts/form-options", () => {
  it("program owner offers the server's rows and nothing else", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByRole("option", { name: "Billing" })).toBeInTheDocument());
    const owner = screen.getByLabelText(/^Program owner/);
    expect(within(owner).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "Choose",
      "Billing",
      "Customer service",
    ]);
  });

  it("a platform code reads in the catalogue's words; the server's label is only a fallback", async () => {
    const user = userEvent.setup();
    renderForm();
    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByLabelText(/^Enrollment/);
    expect(screen.getByRole("option", { name: "Automatic" })).toBeInTheDocument();
    expect(screen.queryByText(/SERVER FALLBACK/)).toBeNull();
  });

  it("an unserved form-options route is an empty dropdown, never a broken step", async () => {
    renderForm({ formOptions: false });
    const owner = await screen.findByLabelText(/^Program owner/);
    expect(within(owner).getAllByRole("option").map((o) => o.textContent)).toEqual(["Choose"]);
    expect(screen.getByLabelText(/^Code/)).toBeInTheDocument();
  });
});

describe("PO 2026-10-03 · Usage allowance is not offered until free units before pricing is built", () => {
  it("the Type list offers every server type but Usage allowance, though the server still serves it", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByRole("option", { name: /^Percentage/ })).toBeInTheDocument());
    const type = screen.getByLabelText(/^Type/);
    const offered = within(type).getAllByRole("option").map((o) => o.getAttribute("value"));
    expect(offered).toEqual(["percentage", "fixed_amount", "charge_waiver"]);
    expect(FORM_OPTIONS.types.map((o) => o.value)).toContain("usage_allowance");
  });
});

describe("currency is the utility's, shown and never typed", () => {
  it("reads USD with no box to type into", async () => {
    renderForm();
    await waitFor(() => expect(document.getElementById("discount-currency")?.textContent).toMatch(/^USD/));
    expect(screen.queryByRole("textbox", { name: /Currency/ })).toBeNull();
  });
});

describe("step validation · Continue names each missing box", () => {
  it("an empty step 1 says Fix 3 things first and names code, label and value (image 13)", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Fix 3 things first.")).toBeInTheDocument();
    expect(screen.getByText("Enter a code.")).toBeInTheDocument();
    expect(screen.getByText("Enter the bill line label.")).toBeInTheDocument();
    expect(screen.getByText("Enter the value.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });

  it("150% is refused on the box (image 14)", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.type(await screen.findByLabelText(/^Code/), "x");
    await user.type(screen.getByLabelText(/^Bill line label/), "x");
    await user.type(screen.getByRole("textbox", { name: /^Percent off/ }), "150");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Fix 1 thing first.")).toBeInTheDocument();
    expect(screen.getByText("Cannot be over 100%.")).toBeInTheDocument();
  });

  it("step 2 names who qualifies and an end before the start (image 16), and keeps what was typed", async () => {
    const user = userEvent.setup();
    renderForm();
    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(await screen.findByLabelText(/^Starts/), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText(/^Ends/), { target: { value: "2026-01-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Fix 2 things first.")).toBeInTheDocument();
    expect(screen.getByText("Choose who qualifies.")).toBeInTheDocument();
    expect(screen.getByText("Ends before it starts.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByLabelText(/^Code/)).toHaveValue("senior");
    expect(screen.getByRole("textbox", { name: /^Percent off/ })).toHaveValue("15");
  });
});

describe("ruling 3 · Automatic is offered only for a condition the system checks", () => {
  it("Age 65 or over (proof) draws Automatic disabled; Autopay is on (system) offers it", async () => {
    const user = userEvent.setup();
    renderForm();
    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const who = await screen.findByRole("combobox", { name: /^Who qualifies/ });
    await user.selectOptions(who, "age_65");
    expect(screen.getByRole("option", { name: "Automatic" })).toBeDisabled();
    await user.selectOptions(who, "autopay_on");
    expect(screen.getByRole("option", { name: "Automatic" })).not.toBeDisabled();
  });

  it("Automatic held over from a system condition is refused once a proof condition is chosen", async () => {
    const user = userEvent.setup();
    renderForm();
    await fillDetails(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    // The list's first enrollment mode, Automatic, is the default.
    await user.selectOptions(await screen.findByRole("combobox", { name: /^Who qualifies/ }), "age_65");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Automatic needs a system check.")).toBeInTheDocument();
  });
});

describe("Limits · one section, closed, reading No limits or N set", () => {
  it("opens on click and counts what is set", async () => {
    const user = userEvent.setup();
    renderForm();
    const toggle = await screen.findByRole("button", { name: /Limits/ });
    expect(toggle).toHaveTextContent("No limits");
    expect(screen.queryByLabelText(/^Cap per bill/)).toBeNull();
    await user.click(toggle);
    await user.type(screen.getByLabelText(/^Cap per bill/), "25");
    expect(toggle).toHaveTextContent("1 set");
  });

  it("a marked box inside opens it, so the mark is never hidden behind its summary", async () => {
    const user = userEvent.setup();
    renderForm();
    await fillDetails(user);
    const toggle = screen.getByRole("button", { name: /Limits/ });
    await user.click(toggle);
    await user.type(screen.getByLabelText(/^Cap per bill/), "lots");
    await user.click(toggle);
    expect(screen.queryByLabelText(/^Cap per bill/)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Enter an amount.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Cap per bill/)).toHaveValue("lots");
  });
});

describe("15 typed → 15% on the bill, end to end", () => {
  it("reads 15% on Review, −$9.00 off a $60.00 bill, and sends value \"15\" and the utility's currency", async () => {
    const user = userEvent.setup();
    const sent = renderForm();
    await fillDetails(user);
    // The panel reads "off subtotal before taxes" as the drawing does — the
    // in-sentence phrase is its own catalogue key, never a capitalised label
    // dropped into a sentence (DEF-RAT-9316).
    expect(document.querySelector("[data-discount-summary]")).toHaveTextContent("off subtotal before taxes");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.selectOptions(await screen.findByRole("combobox", { name: /^Who qualifies/ }), "age_65");
    await user.selectOptions(screen.getByLabelText(/^Enrollment/), "apply_and_approve");
    fireEvent.change(screen.getByLabelText(/^Starts/), { target: { value: "2026-11-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Saves as a draft.")).toBeInTheDocument();
    expect(document.querySelector("[data-review-row=value]")?.textContent).toContain("15%");
    expect(document.querySelector("[data-discount-example-reduction]")?.textContent).toBe("−$9.00");
    // Every Review row carries an Edit link back to its step.
    expect(screen.getAllByRole("button", { name: /^Edit / }).length).toBe(
      document.querySelectorAll("[data-review-row]").length,
    );
    await user.click(screen.getByRole("button", { name: "Save as draft" }));
    await waitFor(() => expect(document.getElementById("discount-saved-title")).toHaveTextContent("Senior discount saved as a draft"));
    const post = sent.find((call) => call.method === "POST" && call.url.endsWith("/discounts"));
    expect(post?.body?.value).toBe("15");
    expect(post?.body?.currency).toBe("USD");
    expect(post?.body?.program_owner).toBe("billing");
    expect(post?.body?.eligibility).toBe("age_65");
    expect(post?.body?.code).toBe("SENIOR");
  });
});

describe("hard-won law 2 · the New door opens THIS form", () => {
  // The hold this case was written for (edit left on DiscountWizard "until
  // round 3") expired in CR-166 round 3 task 7, as it was written to: the edit
  // route now opens the same form with What to change on top.
  it("App mounts NewDiscountWizard at the new route and EditDiscountForm at the edit route", () => {
    expect(appSource).toContain('{ path: "plans-rates/discounts/new", element: <NewDiscountWizard /> }');
    expect(appSource).toContain('{ path: "plans-rates/discounts/:definitionId/edit", element: <EditDiscountForm /> }');
    expect(appSource).not.toContain("<DiscountWizard />");
  });
});
