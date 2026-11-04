// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 12 — the staff service request's
//           step 1 is the SHARED customer form (drawing set
//           `customer-forms-2026-10-18`, image 03). **Fill EVERY field, press
//           Continue, and the save carries every value** — the Who panel, the
//           Identity panel (incl. Move-in's government ID), Contact by, the full
//           co-applicant card, the mailing address (sent as `mailing_*`), the
//           Preferences (no Autopay) and a business's Tax ID (`DEF-CUS-10223`).
//           The server half — saved and read back — is
//           `06-backend/tests/test_cf1_customer_forms_2026_10_18.py`.
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { ServiceRequestCapturePage } from "./ServiceRequestCapturePage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function makeClient(calls: Call[]) {
  return createApiClient({
    tenant: "annarbor",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://x");
      const path = url.pathname.replace(/^\/api\/annarbor/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
      calls.push({ method, path, body });
      const json = (payload: unknown, status = 200): Response =>
        new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
      if (path === "/service-requests/categories") {
        return json({ selectable: [{ code: "residential", name: "Residential" }], legacy: [] });
      }
      if (path === "/shell/display") return json({ regional: { language: "en" } });
      if (path === "/settings/services") return json([{ service: "water", name: "Water", enabled: true }]);
      if (path === "/service-requests/capture-defaults") {
        return json({ requested_start: "2026-10-15", working_days: 15, holidays_counted: 0 });
      }
      if (path === "/service-requests" && method === "POST") {
        // A created draft, shaped enough for the wizard to carry on.
        return json({
          header: { id: "sr-new", request_no: "SR-26-0101", state: "draft", channel: "walk_in" },
          applicant: { identifier: {}, co_applicant: { name: null, email: null, phone: null } },
          location_and_services: { services: [], billing_address_same: true },
          documents: { documents: [], checklist_required: [] },
          fees: {
            lines: [],
            outstanding_lines: 0,
            quoted: { amount: "0.0000", currency: null },
            settled: { amount: "0.0000", currency: null },
            collected: { amount: "0.0000", currency: null },
            outstanding: { amount: "0.0000", currency: null },
          },
          decision: {},
          history: [],
        });
      }
      return json({ count: 0, next: null, previous: null, results: [] });
    },
  });
}

function mount(calls: Call[]) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/annarbor/requests/new?step=1"]}>
        <Routes>
          <Route path="/:tenant/requests/new" element={<ServiceRequestCapturePage client={makeClient(calls)} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const byId = <T extends HTMLElement = HTMLInputElement>(id: string) => document.getElementById(id) as T;

afterEach(cleanup);

describe("task 12 · the service request saves every field of the shared form", () => {
  it("a person: fill every field, Continue, and the create carries every value", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    mount(calls);
    await screen.findByRole("heading", { name: t("customers.form.whoApplying") });
    await waitFor(() => expect(document.querySelector('#account_type option[value="residential"]')).not.toBeNull());
    fireEvent.change(byId<HTMLSelectElement>("account_type"), { target: { value: "residential" } });
    fireEvent.change(byId("full_name"), { target: { value: "Maria Lopez" } });
    fireEvent.change(byId("email"), { target: { value: "maria.lopez@example.com" } });
    fireEvent.change(byId("phone"), { target: { value: "(734) 555-0182" } });
    await user.type(byId("dob"), "04/12/1988");
    await user.tab();
    fireEvent.change(byId<HTMLSelectElement>("contact_by"), { target: { value: "text" } });
    fireEvent.change(byId("ssn"), { target: { value: "123-45-4471" } });
    fireEvent.change(byId("driving_licence"), { target: { value: "MI L-552-118-903" } });
    fireEvent.change(byId("gov_id_last4"), { target: { value: "9001" } });

    // The co-applicant card — every field the drawing shows.
    fireEvent.click(screen.getByLabelText(t("customers.form.coApplicants.tick")));
    fireEvent.change(byId("co_owner_0_full_name"), { target: { value: "Daniel Lopez" } });
    fireEvent.change(byId<HTMLSelectElement>("co_owner_0_relationship"), { target: { value: "spouse" } });
    fireEvent.change(byId<HTMLSelectElement>("co_owner_0_responsible_for_bills"), { target: { value: "yes" } });
    fireEvent.change(byId("co_owner_0_phone"), { target: { value: "(734) 555-0144" } });
    fireEvent.change(byId("co_owner_0_email"), { target: { value: "dan.lopez@example.com" } });
    await user.type(byId("co_owner_0_date_of_birth"), "09/30/1986");
    await user.tab();
    fireEvent.change(byId("co_owner_0_ssn"), { target: { value: "987-65-2208" } });
    fireEvent.change(byId("co_owner_0_driving_licence"), { target: { value: "MI D-111" } });

    // Mailing address — unticked, five US parts.
    fireEvent.click(screen.getByLabelText(t("customers.account.field.mailingSame")));
    fireEvent.change(byId("mailing_line1"), { target: { value: "PO Box 2210" } });
    fireEvent.change(byId("mailing_city"), { target: { value: "Ypsilanti" } });
    fireEvent.change(byId("mailing_state"), { target: { value: "Mich" } });
    fireEvent.click(byId("mailing_state-opt-MI"));
    fireEvent.change(byId("mailing_postal_code"), { target: { value: "48197" } });

    // Preferences — no Autopay on a request.
    fireEvent.click(screen.getByLabelText(t("customers.moveIn.prefs.tick")));
    expect(byId("autopay")).toBeNull();
    fireEvent.change(byId<HTMLSelectElement>("paperless"), { target: { value: "on" } });
    fireEvent.change(byId<HTMLSelectElement>("sms_reminders"), { target: { value: "on" } });

    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    const create = await waitFor(() => {
      const found = calls.find((call) => call.method === "POST" && call.path === "/service-requests");
      expect(found).toBeDefined();
      return found as Call;
    });
    expect(create.body).toMatchObject({
      applicant_kind: "person",
      applicant_name: "Maria Lopez",
      applicant_email: "maria.lopez@example.com",
      applicant_phone: "(734) 555-0182",
      date_of_birth: "1988-04-12",
      ssn: "123-45-4471",
      drivers_licence: "MI L-552-118-903",
      gov_id_last4: "9001",
      contact_by: "text",
      paperless: true,
      sms_reminders: true,
      mailing_same: false,
      mailing_line1: "PO Box 2210",
      mailing_city: "Ypsilanti",
      mailing_state: "MI",
      mailing_postal_code: "48197",
      co_applicants: [
        {
          full_name: "Daniel Lopez",
          relationship: "spouse",
          responsible_for_bills: true,
          phone: "(734) 555-0144",
          email: "dan.lopez@example.com",
          date_of_birth: "1986-09-30",
          ssn: "987-65-2208",
          driving_licence: "MI D-111",
        },
      ],
    });
    // The category is set through its own door, as before.
    await waitFor(() =>
      expect(calls.some((call) => call.method === "POST" && call.path === "/service-requests/sr-new/category")).toBe(true),
    );
  });

  it("DEF-CUS-10223 · a business's Tax ID is sent", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByRole("heading", { name: t("customers.form.whoApplying") });
    await waitFor(() => expect(document.querySelector('#account_type option[value="residential"]')).not.toBeNull());
    fireEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.company") }));
    fireEvent.change(byId<HTMLSelectElement>("account_type"), { target: { value: "residential" } });
    fireEvent.change(byId("full_name"), { target: { value: "Kestrel Bakery LLC" } });
    fireEvent.change(byId("tax_id"), { target: { value: "47-1234567" } });
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    const create = await waitFor(() => {
      const found = calls.find((call) => call.method === "POST" && call.path === "/service-requests");
      expect(found).toBeDefined();
      return found as Call;
    });
    expect(create.body).toMatchObject({ applicant_kind: "business", tax_id: "47-1234567" });
    expect(create.body).not.toHaveProperty("drivers_licence");
  });

  it("Move-in's rules: a person with no phone, or a malformed email, does not leave step 1", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByRole("heading", { name: t("customers.form.whoApplying") });
    await waitFor(() => expect(document.querySelector('#account_type option[value="residential"]')).not.toBeNull());
    fireEvent.change(byId<HTMLSelectElement>("account_type"), { target: { value: "residential" } });
    fireEvent.change(byId("full_name"), { target: { value: "Maria Lopez" } });
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    expect(await screen.findByText(t("customers.moveIn.customer.problem.phone"))).toBeInTheDocument();
    fireEvent.change(byId("phone"), { target: { value: "(734) 555-0182" } });
    fireEvent.change(byId("email"), { target: { value: "maria@" } });
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
    expect((await screen.findAllByText(t("customers.form.emailInvalid"))).length).toBeGreaterThan(0);
    expect(calls.some((call) => call.method === "POST" && call.path === "/service-requests")).toBe(false);
  });
});
