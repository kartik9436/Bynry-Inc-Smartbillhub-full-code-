// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9043 — no screen let a clerk link an existing customer to a
//           service request; the only press sent `customer_id: null`.
// Harness:  the finder's real search (`GET /customers?q=`) against a fake
//           server, and the Approve window's own slot — so the case proves the
//           door is IN the window, not merely that a component exists
//           (hard-won law 2: built is not wired).
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { RequestCustomerLink } from "./RequestCustomerLink";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const MARCUS = {
  id: "cust-marcus",
  customer_no: "C-00053",
  display_name: "Marcus Bell",
  kind: "person",
  verdict: "found",
  agreed: ["driving_licence"],
  accounts: null,
  company: null,
};

/** `GET …/customer-search` — found for one request, nothing for the other. */
function server() {
  const asked: string[] = [];
  const client = createApiClient({
    tenant: "sixrivers",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://x");
      if (url.pathname.endsWith("/customer-search")) {
        asked.push(url.pathname);
        const found = url.pathname.includes("sr-found");
        const body = found
          ? { result: "found", count: 1, customers: [MARCUS] }
          : { result: "new", count: 0, customers: [] };
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 404 });
    },
  });
  return { client, asked };
}

function mount(
  requestId: string,
  client: ReturnType<typeof createApiClient>,
  onLink: (id: string) => void,
  onNoMatch?: () => void,
) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {/* Lane CF-1 — mounted under the real route pattern (hard-won law 2):
          the shared search table's View icon builds a tenant address. */}
      <MemoryRouter initialEntries={[`/annarbor/requests/${requestId}`]}>
        <Routes>
          <Route
            path="/:tenant/requests/:id"
            element={
              <RequestCustomerLink
                t={t}
                client={client}
                requestId={requestId}
                timeZone="America/Chicago"
                dateFormat="MM/DD/YYYY"
                onLink={onLink}
                onNoMatch={onNoMatch}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ⚠ `DEF-CUS-10043` (PO 2026-10-11): the free-text finder this tested is
// replaced by the move-in's *Search customer ID*, asked with the request's own
// identity — *"use existing customer ID search function … use existing rule"*.
describe("DEF-CUS-10043 · Search customer matches by the request's ID", () => {
  it("found: one press shows the customer's NUMBER and Link hands over that customer", async () => {
    const { client, asked } = server();
    const linked: string[] = [];
    mount("sr-found", client, (id) => linked.push(id));
    fireEvent.click(document.querySelector("[data-customer-search]") as HTMLButtonElement);
    await waitFor(() => expect(asked).toEqual(["/api/sixrivers/service-requests/sr-found/customer-search"]));
    expect(await screen.findByText(/C-00053/)).toBeInTheDocument();
    fireEvent.click(document.querySelector('[data-testid^="match-link-"]') as HTMLButtonElement);
    expect(linked).toEqual(["cust-marcus"]);
    await waitFor(() => expect(document.querySelector('[data-customer-match="linked"]')).not.toBeNull());
    expect(document.body.textContent).not.toContain("cust-marcus");
  });

  it("nothing on file: it says No customer found", async () => {
    const { client } = server();
    mount("sr-nobody", client, () => undefined);
    fireEvent.click(document.querySelector("[data-customer-search]") as HTMLButtonElement);
    expect(await screen.findByText(t("customers.moveIn.customer.match.newLine"))).toBeInTheDocument();
    expect(document.querySelector('[data-customer-match="new"]')).not.toBeNull();
  });

  // PO 2026-10-11, option B — *Record that I searched* merged in here.
  it("No match is offered only after a search answers, and pressing it records once", async () => {
    const { client } = server();
    let recorded = 0;
    mount("sr-nobody", client, () => undefined, () => (recorded += 1));
    expect(document.querySelector('[data-action="record-search"]')).toBeNull();
    fireEvent.click(document.querySelector("[data-customer-search]") as HTMLButtonElement);
    const noMatch = await waitFor(() => {
      const node = document.querySelector('[data-action="record-search"]');
      if (node === null) throw new Error("No match not offered");
      return node as HTMLButtonElement;
    });
    expect(noMatch.textContent).toBe(t("customers.serviceRequest.match.noMatch"));
    fireEvent.click(noMatch);
    expect(recorded).toBe(1);
    expect(await screen.findByText(t("customers.serviceRequest.match.noMatchRecorded"))).toBeInTheDocument();
    expect(document.querySelector('[data-action="record-search"]')).toBeNull();
  });

  it("a match that is the wrong person can still be answered with No match", async () => {
    const { client } = server();
    let recorded = 0;
    mount("sr-found", client, () => undefined, () => (recorded += 1));
    fireEvent.click(document.querySelector("[data-customer-search]") as HTMLButtonElement);
    expect(await screen.findByText(/C-00053/)).toBeInTheDocument();
    fireEvent.click(document.querySelector('[data-action="record-search"]') as HTMLButtonElement);
    expect(recorded).toBe(1);
  });
});
