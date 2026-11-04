// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 11 — **a move-in from an approved
//           request opens with EVERY field the request holds filled in**:
//           name, email, phone, date of birth, Contact by, the government ID,
//           the SSN and licence as masks (their numbers are carried by the
//           server), the co-applicant cards, the mailing address, the
//           preferences and the utility's own customer fields — and the
//           Customer step then SENDS the custom fields (`DEF-CUS-10224`) and
//           the co-owners.
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"* (PO: *"ALSO DATA COLECTED IS NOT LOST"*) ·
//           drawing set `customer-forms-2026-10-18` image 01's note *"From an
//           approved request: every field arrives filled in"*.
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { emptyCoOwner } from "./CoOwnerCards";
import { MoveInWizard } from "./MoveInWizard";
import { emptyStepCustomerOwn, stepCustomerPayload } from "./moveInWizard/StepCustomer";
import { emptyCustomerForm } from "./NewAccountWizard";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);
const REQUEST_ID = "01a0fa42-2903-7d5d-92bb-901f5c01f9aa";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Maria Lopez's approved request, every field of the shared form answered. */
const MARIA = {
  header: { id: REQUEST_ID, request_no: "SR-26-0101", requested_start: "2026-10-23" },
  applicant: {
    name: "Maria Lopez",
    email: "maria.lopez@example.com",
    phone: "(734) 555-0182",
    date_of_birth: "1988-04-12",
    language: "es",
    person_or_company: "person",
    customer_category: { account_type: { id: "at-1", code: "residential", name: "Residential" }, account_subtype: null },
    co_applicant: { name: "Daniel Lopez", email: "dan.lopez@example.com", phone: "(734) 555-0144" },
    co_applicants: [
      {
        full_name: "Daniel Lopez",
        relationship: "spouse",
        phone: "(734) 555-0144",
        email: "dan.lopez@example.com",
        contact_by: "email",
        date_of_birth: "1986-09-30",
        responsible_for_bills: true,
        ssn_last4: "2208",
        driving_licence_last4: null,
      },
    ],
    contact_by: "text",
    gov_id_last4: "9001",
    preferences: { paperless: true, sms_reminders: true },
    mailing_address: { same: false, line1: "PO Box 2210", line2: null, city: "Ypsilanti", state: "MI", postal_code: "48197" },
    customer_match: { customer_id: null, customer_no: null, display_name: null, tier: null, basis: null, confirmed_at: null, may_move_money: false },
    identifier: {
      ssn_last4: "4471",
      ssn_present: true,
      stored_encrypted: true,
      drivers_licence_last4: "8903",
      drivers_licence_present: true,
      drivers_licence_stored_encrypted: true,
      tax_id_last4: null,
      tax_id_present: false,
    },
  },
  location_and_services: { resolved_unit_id: "unit-b", billing_address_same: false },
  custom_data: { customers: { medical_priority: "No" } },
};

function open(step: number) {
  const client = createApiClient({
    tenant: "sixrivers",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/custom-fields")) {
        return json({
          entity: "customers",
          fields: url.includes("screen=S18")
            ? [{ id: "f1", key: "medical_priority", label: "Medical priority", help_text: "", data_type: "text", options: [], is_required: false, display_order: 1, placement: {} }]
            : [],
        });
      }
      if (url.includes("/documents")) return json({ documents: [] });
      if (/\/service-requests\/[^/?]+(\?|$)/.test(url)) return json(MARIA);
      if (/\/move-ins\/units(\?|$)/.test(url)) {
        return json({ count: 1, next: null, previous: null, results: [
          { id: "unit-b", unit_no: "U-00002", label: "Main", premise_no: null, premise_name: null, address: { line1: "143 Willow Bend Dr", city: null, state: null, postal_code: null }, meters: [], state: "vacant", occupant: null, selectable: true, path: "move_in", reason_key: null },
        ] });
      }
      if (url.includes("categories")) return json({ selectable: [{ code: "residential", name: "Residential" }], legacy: [] });
      if (/\/accounts(\?|$)/.test(url)) return json({ count: 0, next: null, previous: null, results: [] });
      return json({ detail: "not found" }, 404);
    },
  } as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/sixrivers/move-ins/new?request=${REQUEST_ID}&step=${step}`]}>
          <Routes>
            <Route path="/:tenant/move-ins/new" element={<MoveInWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

const value = (id: string) => (document.getElementById(id) as HTMLInputElement | null)?.value;

describe("task 11 · a move-in from an approved request opens with every field filled in", () => {
  it("the customer step holds every value the request holds", async () => {
    open(2);
    await waitFor(() => expect(value("full_name")).toBe("Maria Lopez"));
    expect(value("email")).toBe("maria.lopez@example.com");
    expect(value("phone")).toBe("(734) 555-0182");
    expect(value("contact_by")).toBe("text");
    expect(value("gov_id_last4")).toBe("9001");
    // The SSN and licence: the request serves their last four only, so the
    // boxes stay EMPTY and say what is on file; the server carries the numbers.
    expect(value("ssn")).toBe("");
    expect(document.getElementById("ssn")).toHaveAttribute("placeholder", "•••-••-4471");
    expect(document.getElementById("driving_licence")).toHaveAttribute("placeholder", "•••• 8903");
    // The co-applicant is a co-owner card, ticked and named.
    expect(screen.getByLabelText(t("customers.moveIn.customer.coOwners.tick"))).toBeChecked();
    expect(document.body.textContent ?? "").toContain("Daniel Lopez");
    // The mailing address arrives unticked, with its parts.
    expect(screen.getByLabelText(t("customers.account.field.mailingSame"))).not.toBeChecked();
    expect(value("mailing_line1")).toBe("PO Box 2210");
    expect(value("mailing_city")).toBe("Ypsilanti");
    expect(value("mailing_postal_code")).toBe("48197");
    // The utility's own customer field, with the request's answer.
    await waitFor(() => expect(screen.getByLabelText(/Medical priority/)).toHaveValue("No"));
  });

  it("the co-owner card the request carried opens with every value but the identifiers", async () => {
    open(2);
    await waitFor(() => expect(document.body.textContent ?? "").toContain("Daniel Lopez"));
    fireEvent.click(screen.getByRole("button", { name: /Daniel Lopez/ }));
    expect(value("co_owner_0_full_name")).toBe("Daniel Lopez");
    expect(value("co_owner_0_relationship")).toBe("spouse");
    expect(value("co_owner_0_responsible_for_bills")).toBe("yes");
    expect(value("co_owner_0_phone")).toBe("(734) 555-0144");
    expect(value("co_owner_0_email")).toBe("dan.lopez@example.com");
    expect(value("co_owner_0_ssn")).toBe("");
  });
});

describe("DEF-CUS-10224 · the Customer step SENDS the utility's fields and the co-owners", () => {
  it("custom_data rides the customer block; co-owners ride co_owners", () => {
    const customer = {
      ...emptyCustomerForm(),
      customer_kind: "person",
      full_name: "Maria Lopez",
      phone: "(734) 555-0182",
    };
    const body = stepCustomerPayload(customer, {
      ...emptyStepCustomerOwn(),
      contact_by: "text",
      custom: { medical_priority: "No", empty: "" },
      co_owners_on: true,
      co_owners: [{ ...emptyCoOwner(), full_name: "Daniel Lopez", relationship: "spouse", responsible_for_bills: true }],
    });
    expect(body.customer).toMatchObject({ display_name: "Maria Lopez", kind: "person", custom_data: { medical_priority: "No" } });
    expect((body.customer as { custom_data: Record<string, unknown> }).custom_data).not.toHaveProperty("empty");
    expect(body.co_owners).toEqual([{ full_name: "Daniel Lopez", relationship: "spouse", responsible_for_bills: true }]);
    expect(body.contact).toMatchObject({ contact_by: "text" });
  });
});
