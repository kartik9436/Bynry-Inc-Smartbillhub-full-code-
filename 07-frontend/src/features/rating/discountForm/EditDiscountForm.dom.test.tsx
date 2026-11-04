// @vitest-environment jsdom
// CR-166-BRC10 round 3 task 7 — EDIT a discount (images 27–36), mounted under
// its REAL route pattern (hard-won law 2's fixture clause) at the exact address
// the details page links to, against a fake API that answers the round-2
// contract (CR-166 §9). Senior discount as the images draw it: 15 % off the
// subtotal before taxes, from 08/01/2026, no end, v1.
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import appSource from "../../../App.tsx?raw";
import { EditDiscountForm } from "./EditDiscountForm";
import { discountEditPath } from "./discountEditModel";

afterEach(cleanup);

const TENANT = "brazosbend";
const EDIT_PATTERN = "/plans-rates/discounts/:definitionId/edit";

const SERVICES = [{ service: "water", name: "Water", enabled: true, billed_uom: "kgal" }] as unknown as TenantServiceRow[];

const FORM_OPTIONS = {
  program_owners: [
    { value: "billing", label: "Billing" },
    { value: "finance", label: "Finance" },
  ],
  exclusivity_groups: [
    { value: "none", label: "None" },
    { value: "age_based", label: "Age-based" },
  ],
  eligibility: [
    { value: "everyone", label: "Everyone on the plan", checked_by: "system" },
    { value: "age_65_or_over", label: "Age 65 or over", checked_by: "proof" },
  ],
  enrollment_modes: [
    { value: "automatic", label: "Automatic" },
    { value: "apply_and_approve", label: "Apply and approve" },
  ],
  verification: [
    { value: "one_time_proof", label: "One-time proof at enrollment" },
    { value: "annual_recertification", label: "Annual recertification" },
  ],
  lapse: [{ value: "notify_then_drop", label: "Notify, then drop the enrollment" }],
  budget_periods: [{ value: "annual", label: "Annual" }],
  budget_out: [{ value: "suspend", label: "Suspend the discount" }],
  types: [
    { value: "percentage", label: "Percentage" },
    { value: "fixed_amount", label: "Fixed amount" },
    { value: "usage_allowance", label: "Usage allowance" },
  ],
  applies_to: [{ value: "whole_bill", label: "Subtotal before taxes" }],
};

/** SENIOR as served on PostgreSQL 16 (round 2's read, §9 shapes). */
function senior(extra: Record<string, unknown> = {}) {
  return {
    id: "disc-sr",
    code: "SENIOR",
    name: "Senior discount",
    type: "percentage",
    value: "15.000000",
    value_display: "15.00%",
    currency: "USD",
    eligibility: { value: "age_65_or_over", label: "Age 65 or over", checked_by: "proof" },
    verification: "annual_recertification",
    plans: 1,
    enrolled: 12,
    status: "active",
    stored_status: "active",
    programme_owner: "billing",
    program_owner: { value: "billing", label: "Billing" },
    funding_source: "Rate-payer funded",
    exclusivity_group: { value: "none", label: "None" },
    applies_to: "whole_bill",
    effective_from: "2026-08-01",
    effective_to: null,
    version: 1,
    version_no: 1,
    version_status: "active",
    version_id: "ver-1",
    report_in_assistance_filing: true,
    applies_to_service: null,
    applies_to_services: [],
    applies_to_charge_codes: [],
    cap_per_bill: null,
    cap_per_year: null,
    cap_lifetime: null,
    bill_floor_amount: "0.000000",
    stacking_precedence: 10,
    stacks_with_others: true,
    enrolment_mode: "apply_and_approve",
    proof_required: true,
    proof_before_first_reduction: true,
    recertification_months: 12,
    recertification_notice_days: 30,
    recertification_grace_days: 15,
    lapse_behaviour: "notify_then_drop",
    budget_cap: null,
    budget_period: "annual",
    exhaustion_behaviour: "suspend",
    ...extra,
  };
}

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

function fakeClient(sent: Sent[], row: Record<string, unknown>, refuse?: { url: string; field: string; key: string }) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
      sent.push({ method, url, body });
      const json = (status: number, payload: unknown) =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (refuse !== undefined && method !== "GET" && url.endsWith(refuse.url)) {
        return json(400, {
          code: "VAL-RANGE",
          message_key: refuse.key,
          field_errors: [{ field: refuse.field, code: "VAL-RANGE", message_key: refuse.key, params: { current_start: "2026-08-01" } }],
        });
      }
      if (url.includes("/discounts/form-options")) return json(200, FORM_OPTIONS);
      if (url.includes("/charges")) return json(200, { count: 0, next: null, previous: null, results: [] });
      if (url.includes("/shell/display")) return json(200, { regional: { currency: "USD" }, company: {}, period: null });
      if (url.endsWith("/discounts/disc-sr/new-value") && method === "POST") {
        return json(201, { id: "ver-2", version_no: 2, status: "active", effective_from: body?.effective_from, effective_to: null });
      }
      if (url.endsWith("/discounts/disc-sr/corrections") && method === "POST") {
        return json(200, { id: "ver-2", version_no: 2, status: "active", corrects: "ver-1", effective_from: "2026-08-01", effective_to: null });
      }
      if (url.endsWith("/discounts/disc-sr") && method === "PATCH") return json(200, { ...row, ...body });
      if (url.endsWith("/discounts/disc-sr")) return json(200, row);
      return json(200, {});
    },
  });
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function renderEdit(
  address: string,
  opts: { row?: Record<string, unknown>; refuse?: { url: string; field: string; key: string } } = {},
) {
  const sent: Sent[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${address}`]}>
          <Routes>
            <Route
              path={`/:tenant${EDIT_PATTERN}`}
              element={
                <>
                  <EditDiscountForm
                    client={fakeClient(sent, opts.row ?? senior(), opts.refuse)}
                    dateFormat="MM/DD/YYYY"
                    timeZone="America/Chicago"
                  />
                  <Where />
                </>
              }
            />
            <Route path="/:tenant/plans-rates/discounts/:definitionId" element={<p>the discount details</p>} />
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

const TITLE = { level: 1, name: "Edit Senior discount" } as const;

describe("D35 · Edit is the SAME full-page form, with What to change on top (image 27)", () => {
  it("the details page's address opens it: title, back link, three cards, Name and details chosen", async () => {
    renderEdit(discountEditPath("disc-sr", "info"));
    expect(await screen.findByRole("heading", TITLE)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Senior discount/ })).toHaveAttribute(
      "href",
      `/${TENANT}/plans-rates/discounts/disc-sr`,
    );
    const cards = screen.getByRole("radiogroup", { name: "What to change" });
    expect(within(cards).getAllByRole("radio").map((r) => r.closest("label")?.textContent)).toEqual([
      "Name and detailsSaved on this version",
      "New value from a dateMakes a new version",
      "Fix a mistakeSame dates, right value",
    ]);
    expect(within(cards).getByRole("radio", { name: /Name and details/ })).toBeChecked();
    expect(document.querySelector("[role=dialog]")).toBeNull();
  });

  it("each card is its own flow: Details · Eligibility · Review; New value · Review; Fix the value · Review", async () => {
    const user = userEvent.setup();
    renderEdit(discountEditPath("disc-sr", "info"));
    await screen.findByRole("heading", TITLE);
    expect(railLabels()).toEqual(["Details", "Eligibility", "Review"]);
    await user.click(screen.getByRole("radio", { name: /New value from a date/ }));
    expect(railLabels()).toEqual(["New value", "Review"]);
    expect(screen.getByTestId("where").textContent).toContain("change=change");
    await user.click(screen.getByRole("radio", { name: /Fix a mistake/ }));
    expect(railLabels()).toEqual(["Fix the value", "Review"]);
    expect(screen.getByTestId("where").textContent).toContain("change=correct");
  });

  it("the old Fix door's address (?correct=1) lands on Fix a mistake, not on Name and details", async () => {
    renderEdit("/plans-rates/discounts/disc-sr/edit?correct=1");
    await screen.findByRole("heading", TITLE);
    expect(screen.getByRole("radio", { name: /Fix a mistake/ })).toBeChecked();
    expect(screen.getByLabelText(/Why it was wrong/)).toBeInTheDocument();
  });
});

describe("D36 · Name and details (images 27–30) → PATCH /discounts/{id}", () => {
  it("image 27 · code and type are facts, value and limits are READ and locked; the label is a box", async () => {
    renderEdit(discountEditPath("disc-sr", "info"));
    expect(await screen.findByLabelText(/^Bill line label/)).toHaveValue("Senior discount");
    expect(screen.queryByRole("textbox", { name: /^Code/ })).toBeNull();
    expect(document.querySelector("#discount-code")?.textContent).toBe("SENIOR");
    expect(document.querySelector("#discount-type")?.textContent).toBe("Percentage");
    expect(screen.getByText("Change with a new value.")).toBeInTheDocument();
    const facts = document.querySelector("[data-facts=discount-value-limits]") as HTMLElement;
    expect(within(facts).getByText("15%")).toBeInTheDocument();
    expect(within(facts).getByText("Subtotal before taxes")).toBeInTheDocument();
    expect(within(facts).getByText("No limits")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /^Percent off/ })).toBeNull();
  });

  it("image 28 · the start is a fact with the door that moves it; the end is a box", async () => {
    const user = userEvent.setup();
    renderEdit(discountEditPath("disc-sr", "info"));
    await screen.findByLabelText(/^Bill line label/);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("combobox", { name: /^Who qualifies/ })).toBeInTheDocument();
    expect(document.querySelector("#discount-starts")?.textContent).toBe("08/01/2026");
    expect(screen.getByText("Change with a new value.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Ends/)).not.toBeDisabled();
  });

  it("images 29–30 · before → after on v1 in place, no bill; Save sends ONLY the changed key", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "info"));
    await screen.findByLabelText(/^Bill line label/);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.selectOptions(await screen.findByLabelText(/^Verification/), "one_time_proof");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const change = document.querySelector("[data-discount-change=verification]") as HTMLElement;
    expect(change.textContent).toBe("VerificationAnnual recertificationOne-time proof at enrollment");
    const version = document.querySelector("[data-discount-version=this]") as HTMLElement;
    expect(version.textContent).toBe("v1 · this version15%08/01/2026 – No endUpdated in place");
    expect(document.querySelector("[data-discount-example=edit]")).toBeNull(); // image 29 draws no bill
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Saved on this version. Logged in Audit.")).toBeInTheDocument();
    expect(document.querySelector("#discount-edit-saved-title")?.textContent).toBe("Senior discount saved");
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.url).toContain("/discounts/disc-sr");
    expect(patch?.body).toEqual({ verification_method: "one_time_proof" });
    await user.click(screen.getByRole("button", { name: "Back to discount" }));
    expect(await screen.findByText("the discount details")).toBeInTheDocument();
  });

  it("Save is held until something has changed", async () => {
    const user = userEvent.setup();
    renderEdit(discountEditPath("disc-sr", "info"));
    await screen.findByLabelText(/^Bill line label/);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByText("No changes yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});

describe("New value from a date (images 31–33) → POST /discounts/{id}/new-value", () => {
  it("image 32 · a start not after today's start: Must be after 08/01/2026, Fix 1 thing first", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "change"));
    const value = await screen.findByRole("textbox", { name: /^Percent off/ });
    await user.clear(value);
    await user.type(value, "12");
    fireEvent.change(screen.getByLabelText(/^New value starts/), { target: { value: "2026-07-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Must be after 08/01/2026.")).toBeInTheDocument();
    expect(screen.getByText("Fix 1 thing first.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });

  it("images 31, 33 · 12% from 01/01/2027: v1 ends 12/31/2026, −$9.00 → −$7.20, bills before keep 15%", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "change"));
    const value = await screen.findByRole("textbox", { name: /^Percent off/ });
    expect(value).toHaveValue("15");
    await user.clear(value);
    await user.type(value, "12");
    fireEvent.change(screen.getByLabelText(/^New value starts/), { target: { value: "2027-01-01" } });
    expect(screen.getByText("Today's value ends 12/31/2026.")).toBeInTheDocument();
    expect(document.querySelector("[data-discount-summary-figure]")?.textContent).toBe("12%");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const rows = [...document.querySelectorAll("[data-discount-change]")].map((row) => row.textContent);
    expect(rows).toEqual(["Value15%12%"]);
    expect(document.querySelector("[data-discount-bill-before]")?.textContent).toBe("−$9.00");
    expect(document.querySelector("[data-discount-bill-after]")?.textContent).toBe("−$7.20");
    expect(document.querySelector("[data-discount-version=today]")?.textContent).toBe(
      "v1 · today15%08/01/2026 – 12/31/2026Gets an end date",
    );
    expect(document.querySelector("[data-discount-version=next]")?.textContent).toBe(
      "v2 · new12%01/01/2027 – No endNew version",
    );
    expect(screen.getByText("Bills before 01/01/2027 keep 15%.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save new value" }));
    expect(await screen.findByText("v2 starts 01/01/2027. Logged in Audit.")).toBeInTheDocument();
    const post = sent.find((call) => call.method === "POST");
    expect(post?.url).toContain("/discounts/disc-sr/new-value");
    expect(post?.body).toEqual({ value: "12", effective_from: "2027-01-01" });
  });

  it("DEF-RAT-9313 · an end typed for the new value is SENT, and reads on v2", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "change"));
    const value = await screen.findByRole("textbox", { name: /^Percent off/ });
    await user.clear(value);
    await user.type(value, "12");
    fireEvent.change(screen.getByLabelText(/^New value starts/), { target: { value: "2027-01-01" } });
    fireEvent.change(screen.getByLabelText(/^Ends/), { target: { value: "2027-06-30" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(document.querySelector("[data-discount-version=next]")?.textContent).toContain("01/01/2027 – 06/30/2027");
    await user.click(screen.getByRole("button", { name: "Save new value" }));
    await screen.findByText("v2 starts 01/01/2027. Logged in Audit.");
    expect(sent.find((call) => call.method === "POST")?.body).toEqual({
      value: "12",
      effective_from: "2027-01-01",
      effective_to: "2027-06-30",
    });
  });

  it("a refusal from the server is marked on its box, never a dead click", async () => {
    const user = userEvent.setup();
    renderEdit(discountEditPath("disc-sr", "change"), {
      refuse: { url: "/discounts/disc-sr/new-value", field: "effective_from", key: "rating.discounts.new_value_not_after_start" },
    });
    const value = await screen.findByRole("textbox", { name: /^Percent off/ });
    await user.clear(value);
    await user.type(value, "12");
    fireEvent.change(screen.getByLabelText(/^New value starts/), { target: { value: "2027-01-01" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Save new value" }));
    expect(await screen.findByText("Start after the current start.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^New value starts/)).toBeInTheDocument();
  });
});

describe("D38 · Fix a mistake (images 34–36) → POST /discounts/{id}/corrections", () => {
  it("image 34 · the dates are READ, not boxes: Same dates as today.", async () => {
    renderEdit(discountEditPath("disc-sr", "correct"));
    expect(await screen.findByText("Same dates as today.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^New value starts/)).toBeNull();
    expect(document.querySelector("#discount-starts")?.textContent).toBe("08/01/2026");
    expect(document.querySelector("#discount-ends")?.textContent).toBe("No end");
    expect(screen.getByText("Shown in Audit.")).toBeInTheDocument();
  });

  it("image 35 · no reason: Enter the reason., Fix 1 thing first", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "correct"));
    const value = await screen.findByRole("textbox", { name: /^Percent off/ });
    await user.clear(value);
    await user.type(value, "1.5");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Enter the reason.")).toBeInTheDocument();
    expect(screen.getByText("Fix 1 thing first.")).toBeInTheDocument();
    expect(sent.some((call) => call.method === "POST")).toBe(false);
  });

  it("image 36 · v1 superseded and kept, v2 replaces it, issued bills keep 15% — and the reason is sent", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "correct"));
    const value = await screen.findByRole("textbox", { name: /^Percent off/ });
    await user.clear(value);
    await user.type(value, "1.5");
    await user.type(screen.getByLabelText(/Why it was wrong/), "Typed 15 instead of 1.5.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Typed 15 instead of 1.5.", { selector: "p" })).toBeInTheDocument();
    expect([...document.querySelectorAll("[data-discount-change]")].map((row) => row.textContent)).toEqual([
      "Value15%1.5%",
    ]);
    expect(document.querySelector("[data-discount-bill-before]")?.textContent).toBe("−$9.00");
    expect(document.querySelector("[data-discount-bill-after]")?.textContent).toBe("−$0.90");
    expect(document.querySelector("[data-discount-version=today]")?.textContent).toBe(
      "v1 · today15%08/01/2026 – No endSuperseded, kept",
    );
    expect(document.querySelector("[data-discount-version=next]")?.textContent).toBe(
      "v2 · correction1.5%08/01/2026 – No endReplaces v1",
    );
    expect(screen.getByText("Issued bills keep 15%. Correct those bills separately.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save correction" }));
    expect(await screen.findByText("v2 replaces v1. Logged in Audit.")).toBeInTheDocument();
    const post = sent.find((call) => call.method === "POST");
    expect(post?.url).toContain("/discounts/disc-sr/corrections");
    expect(post?.body).toEqual({ value: "1.5", reason: "Typed 15 instead of 1.5." });
  });
});

describe("a DRAFT edits in place and has one choice", () => {
  it("New value and Fix a mistake are drawn disabled; every box is a box; Save sends the change", async () => {
    const user = userEvent.setup();
    const sent = renderEdit(discountEditPath("disc-sr", "change"), {
      row: senior({ status: "draft", stored_status: "draft", version_status: "draft" }),
    });
    await screen.findByRole("heading", TITLE);
    expect(screen.getByRole("radio", { name: /Name and details/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /New value from a date/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Fix a mistake/ })).toBeDisabled();
    const value = screen.getByRole("textbox", { name: /^Percent off/ });
    await user.clear(value);
    await user.type(value, "20");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Save changes" }));
    await screen.findByText("Saved on this version. Logged in Audit.");
    expect(sent.find((call) => call.method === "PATCH")?.body).toEqual({ value: "20" });
  });
});

describe("PO 2026-10-03 · a usage-allowance draft already saved opens, its type read-only", () => {
  it("the type is a fact, never a list; a percentage draft is not offered Usage allowance", async () => {
    renderEdit(discountEditPath("disc-sr", "info"), {
      row: senior({
        status: "draft",
        stored_status: "draft",
        version_status: "draft",
        type: "usage_allowance",
        applies_to: "one_service",
        applies_to_service: "water",
        value: "2000.000000",
      }),
    });
    await screen.findByRole("heading", TITLE);
    expect(document.getElementById("discount-type")?.tagName).not.toBe("SELECT");
    expect(document.getElementById("discount-type")?.textContent).toMatch(/Usage allowance/);
    cleanup();
    renderEdit(discountEditPath("disc-sr", "info"), {
      row: senior({ status: "draft", stored_status: "draft", version_status: "draft" }),
    });
    await screen.findByRole("heading", TITLE);
    const type = screen.getByLabelText(/^Type/);
    expect(within(type).getAllByRole("option").map((o) => o.getAttribute("value"))).not.toContain("usage_allowance");
  });
});

describe("hard-won law 2 · the Edit door opens THIS form", () => {
  it("App mounts EditDiscountForm at the edit route; the old DiscountWizard is mounted nowhere", () => {
    expect(appSource).toContain(
      '{ path: "plans-rates/discounts/:definitionId/edit", element: <EditDiscountForm /> }',
    );
    expect(appSource).not.toContain("<DiscountWizard />");
    expect(appSource).not.toContain('from "@/features/rating/DiscountWizard"');
  });

  it("the details page's three addresses are the edit route plus ?change=", () => {
    expect(discountEditPath("disc-sr", "info")).toBe("/plans-rates/discounts/disc-sr/edit?change=info");
    expect(discountEditPath("disc-sr", "change")).toBe("/plans-rates/discounts/disc-sr/edit?change=change");
    expect(discountEditPath("disc-sr", "correct")).toBe("/plans-rates/discounts/disc-sr/edit?change=correct");
  });
});
