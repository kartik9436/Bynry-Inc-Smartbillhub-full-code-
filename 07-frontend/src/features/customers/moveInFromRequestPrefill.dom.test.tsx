// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9044 — a move-in opened from an approved request asked the
//           clerk AGAIN for the unit, the person-or-company and the move-in
//           date, all three of which the request holds. PO 2026-09-19: *"here
//           if ove is coming from service request these details will be
//           filled in"*.
// Harness:  the REAL wizard at the REAL standalone address
//           (`/:tenant/move-ins/new?request=…`, where an approval lands), over
//           a fake server holding one request and two vacant units.
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { MoveInWizard } from "./MoveInWizard";

const REQUEST_ID = "01a0fa42-2903-7d5d-92bb-901f5c01f82d";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const UNITS = {
  count: 2,
  next: null,
  previous: null,
  results: [
    { id: "unit-a", unit_no: "U-00001", label: "Main", premise_id: "p-a", premise_address: "88 Riverbend Way", occupancy: "vacant" },
    { id: "unit-b", unit_no: "U-00002", label: "Main", premise_id: "p-b", premise_address: "14 Alder Run", occupancy: "vacant" },
  ],
};

let linkedAs: { customer_id: string; customer_no: string; display_name: string } | null = null;
let taxLast4: string | null = null;

function request(kind: string) {
  return {
    header: { id: REQUEST_ID, request_no: "SR-26-0009", requested_start: "2026-10-23" },
    applicant: {
      name: "Alder Freight Co",
      email: "ap@alderfreight.test",
      phone: "(281) 555-0204",
      date_of_birth: null,
      language: null,
      person_or_company: kind,
      customer_category: { account_type: { id: "at-1", code: "commercial", name: "Commercial" }, account_subtype: null },
      customer_match: {
        customer_id: linkedAs?.customer_id ?? null,
        customer_no: linkedAs?.customer_no ?? null,
        display_name: linkedAs?.display_name ?? null,
        tier: linkedAs ? "strong" : null,
        basis: null,
        confirmed_at: linkedAs ? "2026-10-02T09:00:00Z" : null,
        may_move_money: linkedAs !== null,
      },
      identifier: {
        ssn_last4: null,
        ssn_present: false,
        stored_encrypted: false,
        drivers_licence_last4: null,
        drivers_licence_present: false,
        drivers_licence_stored_encrypted: false,
        tax_id_last4: taxLast4,
        tax_id_present: taxLast4 !== null,
      },
    },
    location_and_services: {
      resolved_unit_id: "unit-b",
      billing_address_same: true,
    },
  };
}

function open(kind: string, step: number) {
  const client = createApiClient({
    tenant: "sixrivers",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/documents")) return json({ documents: [] });
      if (/\/service-requests\/[^/?]+(\?|$)/.test(url)) return json(request(kind));
      // `DEF-CUS-10190` — step 1's unit search, in its own shape.
      if (/\/move-ins\/units(\?|$)/.test(url)) {
        return json({ count: 2, next: null, previous: null, results: [
          { id: "unit-a", unit_no: "U-00001", label: "Main", premise_no: null, premise_name: null, address: { line1: "88 Riverbend Way", city: null, state: null, postal_code: null }, meters: [], state: "vacant", occupant: null, selectable: true, path: "move_in", reason_key: null },
          { id: "unit-b", unit_no: "U-00002", label: "Main", premise_no: null, premise_name: null, address: { line1: "14 Alder Run", city: null, state: null, postal_code: null }, meters: [], state: "vacant", occupant: null, selectable: true, path: "move_in", reason_key: null },
        ].filter((row) => !url.includes("unit_id=") || url.includes(`unit_id=${row.id}`)) });
      }
      if (/\/units(\?|$)/.test(url)) return json(UNITS);
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

/** `CR-171-BRC10` P2.27 (image 40) — a company's step also asks for its
 *  Business type and its Contact person (each drawn with *). */
function fillCompanyBasics(): void {
  fireEvent.change(document.getElementById("business_type") as HTMLSelectElement, { target: { value: "llc" } });
  fireEvent.change(document.getElementById("contact_full_name") as HTMLInputElement, { target: { value: "Dee Alder" } });
  fireEvent.change(document.getElementById("contact_email") as HTMLInputElement, { target: { value: "dee@alder.example" } });
  fireEvent.change(document.getElementById("contact_phone") as HTMLInputElement, { target: { value: "641-555-0100" } });
}

describe("DEF-CUS-9044 · a move-in from a request starts with what the request holds", () => {
  afterEach(() => {
    cleanup();
    linkedAs = null;
    taxLast4 = null;
  });

  it("step 1 · the unit the clerk picked on the request is the unit chosen", async () => {
    open("person", 1);
    await waitFor(() =>
      // `DEF-CUS-10190` — the unit search replaced the select: the chosen unit
      // is its own line, by NUMBER (never an id on screen).
      expect(document.querySelector('[data-move-in-unit-search="chosen"]')?.textContent).toContain("U-00002"),
    );
  });

  it("step 2 · a BUSINESS applicant opens as a company, not as nothing", async () => {
    open("business", 2);
    await waitFor(() => {
      const company = document.querySelector(
        'input[name="customer_kind"][value="company"]',
      ) as HTMLInputElement | null;
      expect(company?.checked).toBe(true);
    });
  });

  it("DEF-CUS-9052 · a LINKED business is named on step 2 and the step does not demand a Tax ID", async () => {
    linkedAs = { customer_id: "cust-1", customer_no: "C-00054", display_name: "Alder Freight Co" };
    open("business", 2);
    await waitFor(() =>
      expect(document.querySelector("[data-identity-from-request]")?.textContent).toBe(
        "C-00054 · Alder Freight Co",
      ),
    );
    fillCompanyBasics();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(document.getElementById("paperless")).not.toBeNull());
  });

  it("DEF-CUS-9052 · a NEW business's Tax ID from the application stands in for the box", async () => {
    taxLast4 = "0003";
    open("business", 2);
    await waitFor(() =>
      expect(document.querySelector("[data-identity-from-request]")?.textContent).toBe("•••• 0003"),
    );
    fillCompanyBasics();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(document.getElementById("paperless")).not.toBeNull());
  });

  it("DEF-CUS-9052 · with neither, the step still holds for the Tax ID (BR-CUS-1024)", async () => {
    open("business", 2);
    await waitFor(() => expect(document.getElementById("full_name")).not.toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(document.querySelector("[data-customer-problem]")).not.toBeNull());
    expect(document.getElementById("paperless")).toBeNull();
  });

  // `CR-171-BRC10` — the date is on step 1 · Unit, and the customer on step
  // 2, since the wizard became four steps (2026-10-05); Continue past the
  // customer now lands on step 3 · Billing, whose first box is `paperless`.
  it("step 1 · the move-in date is the day they asked to start", async () => {
    open("person", 1);
    await waitFor(() => {
      const box = document.getElementById("opened_at") as HTMLInputElement | null;
      expect(box?.value ?? "").toMatch(/10\/23\/2026|2026-10-23/);
    });
  });
});
