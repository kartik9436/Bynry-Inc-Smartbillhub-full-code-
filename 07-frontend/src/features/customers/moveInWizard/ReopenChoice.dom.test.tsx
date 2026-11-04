// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-181-BRC10 F2 / F3 (lane REOPEN, 2026-10-13) — a returning
//           customer on the move-in's Customer step: the two new match levels,
//           *Reopen AC-… / New account*, what it owes, the balance choice, and
//           what the step sends to Complete.
// Rules:    PO rulings 2026-10-13: *"Q1 C both; Q2 - Reopen, for the same unit
//           only ; Q3 - … Must pay first · Carry it onto the reopened account ·
//           Clerk chooses"* · *"Q4 - keep 5 years right now"* · B14 rules 31,
//           33 · hard rule 2 (the figure is the ledger's, shown, never summed)
// ───────────────────────────────────────────────────────
//
// THE WORKED CASE: Viktor Valdez, C-00022, record holds name + phone only;
// AC-2026-00022 on SCW-U-022 closed 09/17/2026 owing $84.20.
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import type { CustomerReopenOffer, CustomerSearchRow } from "../customerEndpoints";
import { CustomerMatchPanel } from "../customerMatch/CustomerMatchPanel";
import { emptyCustomerForm } from "../NewAccountWizard";
import type { CustomerForm } from "../NewAccountWizard";
import { ReopenChoice } from "./ReopenChoice";
import {
  emptyStepCustomerOwn,
  hydrateStepCustomerOwn,
  moveInCustomerProblem,
  searchQueryFor,
  stepCustomerPayload,
} from "./StepCustomer";
import type { StepCustomerOwn } from "./StepCustomer";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function wrap(node: ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/silvercreek/move-ins/new"]}>
          <Routes>
            <Route path="/:tenant/move-ins/new" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const UNIT = "01a12b2b-f81f-7f63-af9c-a972541a177d";

const OFFER: CustomerReopenOffer = {
  account_id: "01a12b2b-0000-7000-8000-000000000022",
  account_no: "AC-2026-00022",
  closed_at: "2026-09-17",
  eligible: true,
  reason: null,
  outstanding: "84.2000",
  currency: "USD",
  within_years: 5,
};

const VIKTOR: CustomerSearchRow = {
  id: "01a12ac9-0000-7000-8000-000000000022",
  customer_no: "C-00022",
  display_name: "Viktor Valdez",
  kind: "person",
  verdict: "name_phone",
  agreed: ["name", "phone"],
  last_occupant: true,
  reopen: OFFER,
  accounts: {
    count: 1,
    rows: [
      {
        id: OFFER.account_id,
        account_no: "AC-2026-00022",
        status_code: "closed",
        status_name: "Closed",
        closed_at: "2026-09-17",
        address: { line1: "22 Silver Creek Rd", unit_label: "SCW-U-022", city: "Ottumwa", state: "IA", postal_code: "52501" },
        balance: "84.200000",
        outstanding: "84.200000",
        confident: false,
      },
    ],
    outstanding_total: "84.200000",
    currency: "USD",
    available: true,
  },
  company: null,
};

const viktorForm = (patch: Partial<CustomerForm> = {}): CustomerForm => ({
  ...emptyCustomerForm(),
  account_type: "residential",
  customer_kind: "person",
  full_name: "Viktor Valdez",
  email: "viktor@example.com",
  phone: "(641) 555-0122",
  ...patch,
});

afterEach(cleanup);

function matchPanel(row: CustomerSearchRow) {
  return render(
    wrap(
      <CustomerMatchPanel
        result={{ result: row.verdict, count: 1, customers: [row] }}
        pending={false}
        failed={false}
        linkedId={null}
        linkedRow={null}
        dismissed={[]}
        onLink={() => undefined}
        onUnlink={() => undefined}
        onNotThem={() => undefined}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    ),
  );
}

describe("Q1 (C) · the two weaker levels each say their own word", () => {
  // Lane CF-1 (2026-10-18) — the stacked cards became ONE results table: the
  // level is the Match column's icon, its words in the tooltip and the
  // accessible name (customer-forms drawing set, images 01 and 10).
  it("same name and phone — with what he owes, and that he lived here last", () => {
    matchPanel(VIKTOR);
    const row = document.querySelector('[data-match-row="name_phone"]') as HTMLElement;
    expect(row).not.toBeNull();
    const text = row.textContent ?? "";
    expect(text).toContain("Viktor Valdez");
    expect(text).toContain("C-00022");
    expect(text).toContain("$84.20");
    const mark = row.querySelector("[data-match-mark]") as HTMLElement;
    const said = mark.getAttribute("aria-label") ?? "";
    expect(said).toContain(t("customers.moveIn.customer.match.name_phone"));
    expect(said).toContain(t("customers.moveIn.customer.match.last_occupant"));
    expect(said).toContain("Name and phone match.");
    expect(mark.getAttribute("title")).toBe(said);
    expect(row.querySelector("[data-match-lived-here]")).not.toBeNull();
    // Distinct from Q5's words — the clerk can tell the levels apart.
    expect(said).not.toContain(t("customers.moveIn.customer.match.found"));
    expect(said).not.toContain(t("customers.moveIn.customer.match.possible"));
    expect(document.body.innerHTML).not.toContain(VIKTOR.id); // B14 rule 31
  });

  it("the unit's last occupant, found on the name alone", () => {
    matchPanel({ ...VIKTOR, verdict: "last_occupant", agreed: ["name"] });
    const row = document.querySelector('[data-match-row="last_occupant"]') as HTMLElement;
    const said = row.querySelector("[data-match-mark]")?.getAttribute("aria-label") ?? "";
    // said once, as the level — not again as an extra fact
    expect(said.split(t("customers.moveIn.customer.match.last_occupant")).length - 1).toBe(1);
    expect(row.querySelector("[data-match-lived-here]")).not.toBeNull();
  });

  it("the search sends the unit and never the email", () => {
    expect(searchQueryFor(viktorForm(), UNIT)).toEqual({
      kind: "person",
      name: "Viktor Valdez",
      phone: "(641) 555-0122",
      unit_id: UNIT,
    });
    expect(searchQueryFor(viktorForm())).not.toHaveProperty("unit_id");
  });
});

function choice(props: Partial<Parameters<typeof ReopenChoice>[0]> = {}) {
  const seen: { mode?: string; balance?: string; paid: number } = { paid: 0 };
  const client = createApiClient({
    tenant: "silvercreek",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("payment-methods") || url.includes("/methods")) return json({ methods: [] });
      return json({ results: [], count: 0 });
    },
  } as never);
  render(
    wrap(
      <ReopenChoice
        offer={OFFER}
        mode="reopen"
        balance=""
        onMode={(mode) => (seen.mode = mode)}
        onBalance={(value) => (seen.balance = value)}
        onPaid={() => (seen.paid += 1)}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        client={client}
        showErrors={false}
        {...props}
      />,
    ),
  );
  return seen;
}

describe("Q2 / Q3 · Reopen AC-… and what it still owes", () => {
  it("offers the SAME account by number, what it owes, and the clerk's two choices", () => {
    const seen = choice();
    const text = document.body.textContent ?? "";
    expect(screen.getByRole("radio", { name: t("customers.moveIn.reopen.reopen", { account: "AC-2026-00022" }) })).toBeChecked();
    expect(screen.getByRole("radio", { name: t("customers.moveIn.reopen.new") })).toBeInTheDocument();
    expect(text).toContain("Closed 09/17/2026");
    expect(document.querySelector("[data-reopen-owes]")?.textContent).toBe("Owes $84.20");
    fireEvent.click(screen.getByRole("radio", { name: t("customers.moveIn.reopen.carryOption") }));
    expect(seen.balance).toBe("carry");
    fireEvent.click(screen.getByRole("radio", { name: t("customers.moveIn.reopen.new") }));
    expect(seen.mode).toBe("new");
    expect(text).not.toContain(OFFER.account_id); // B14 rule 31
  });

  it("Must pay first opens Payments' own record-payment form on the old account", async () => {
    choice({ balance: "pay_first" });
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.reopen.recordPayment") }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByRole("dialog").textContent ?? "").toContain("AC-2026-00022");
  });

  it("Complete's refusal, routed back here, is drawn beside the choice", () => {
    choice({ balance: "pay_first", refusal: t("customers.moveIn.reopen.payFirst") });
    expect(document.querySelector("[data-reopen-refusal]")?.textContent).toBe("Pay the old balance first.");
  });

  it("nothing owed asks no balance question", () => {
    choice({ offer: { ...OFFER, outstanding: "0.0000" } });
    expect(document.querySelector('[data-reopen-owes="0"]')?.textContent).toBe(t("customers.moveIn.reopen.nothingOwed"));
    expect(screen.queryByRole("radio", { name: t("customers.moveIn.reopen.carryOption") })).toBeNull();
  });

  it("too old: a new account, and why in six words or fewer", () => {
    choice({ offer: { ...OFFER, eligible: false, reason: "too_old" } });
    expect(document.querySelector('[data-reopen="refused"]')?.textContent).toContain(
      t("customers.moveIn.reopen.why.too_old", { years: 5 }),
    );
    expect(screen.queryByRole("radio")).toBeNull();
  });
});

describe("what the step sends to Complete, and what holds Continue", () => {
  const linkedOwn = (patch: Partial<StepCustomerOwn> = {}): StepCustomerOwn => ({
    ...emptyStepCustomerOwn(),
    contact_by: "text",
    linked: VIKTOR,
    ...patch,
  });

  it("reopen + carry: the account handle and the choice", () => {
    const body = stepCustomerPayload(viktorForm(), linkedOwn({ reopen_balance: "carry" }));
    expect(body.reopen_account_id).toBe(OFFER.account_id);
    expect(body.reopen_balance).toBe("carry");
    expect(body.customer).toMatchObject({ customer_id: VIKTOR.id });
  });

  it("New account sends no reopen; an ineligible offer sends none either", () => {
    expect(stepCustomerPayload(viktorForm(), linkedOwn({ reopen_mode: "new" }))).not.toHaveProperty("reopen_account_id");
    const old = linkedOwn({ linked: { ...VIKTOR, reopen: { ...OFFER, eligible: false, reason: "too_old" } } });
    expect(stepCustomerPayload(viktorForm(), old)).not.toHaveProperty("reopen_account_id");
  });

  it("owing with no choice holds Continue, by name", () => {
    expect(moveInCustomerProblem(viktorForm(), linkedOwn(), false)).toBe("customers.moveIn.reopen.choiceRequired");
    expect(moveInCustomerProblem(viktorForm(), linkedOwn({ reopen_balance: "pay_first" }), false)).toBeNull();
    expect(moveInCustomerProblem(viktorForm(), linkedOwn({ reopen_mode: "new" }), false)).toBeNull();
  });

  it("a parked draft keeps the reopen and the choice, never the figure", () => {
    const own = linkedOwn({ reopen_balance: "carry" });
    const parked = hydrateStepCustomerOwn(
      JSON.parse(JSON.stringify({ ...own, linked: { ...own.linked, accounts: null, reopen: { ...OFFER, outstanding: null } } })),
    );
    expect(parked.linked?.reopen?.account_no).toBe("AC-2026-00022");
    expect(parked.linked?.reopen?.outstanding).toBeNull();
    expect(parked.reopen_balance).toBe("carry");
    expect(stepCustomerPayload(viktorForm(), parked).reopen_account_id).toBe(OFFER.account_id);
  });
});
