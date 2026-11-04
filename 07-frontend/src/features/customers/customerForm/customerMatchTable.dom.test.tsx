// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 4 — the customer search RESULTS TABLE
//           (customer-forms drawing set, images 01, 10, 11), mounted under the
//           REAL route pattern (`/:tenant/move-ins/new`) so every address it
//           builds is checked with a tenant in it (hard-won law 2's fixture
//           clause: a bare mount turns `/customers?q=` into `//customers`).
// Rules:    decision log 2026-10-18 *"Search customer ID results — one table,
//           strongest first"* · BR-CUS-092 (phone as last four) · B14 rules 15,
//           31 · DEF-127 (the ledger's figures, shown not summed)
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CustomerSearchResult, CustomerSearchRow } from "../customerEndpoints";
import { CustomerMatchPanel } from "../customerMatch/CustomerMatchPanel";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const account = (id: string, no: string, closed: string | null, owed: string) => ({
  id,
  account_no: no,
  status_code: closed === null ? "active" : "closed",
  status_name: closed === null ? "Active" : "Closed",
  closed_at: closed,
  address: { line1: id === "a1" ? "88 Pine Vista" : "14 Willow Bend", unit_label: id === "a1" ? "Unit 2" : null, city: "Ann Arbor", state: "MI", postal_code: "48108" },
  balance: owed,
  outstanding: owed,
  confident: true,
});

/** Image 01's three customers, strongest first, as the server sends them. */
const MARIA: CustomerSearchRow = {
  id: "01a0c000-0000-7000-8000-000000000412",
  customer_no: "C-00412",
  display_name: "Maria Lopez",
  kind: "person",
  verdict: "found",
  agreed: ["name", "date_of_birth", "ssn"],
  date_of_birth: "1988-04-12",
  phone_last4: "0182",
  accounts: {
    count: 2,
    open_count: 0,
    rows: [account("a2", "AC-2024-00117", "2024-01-15", "42.100000"), account("a1", "AC-2026-00031", "2025-06-30", "0.000000")],
    outstanding_total: "42.100000",
    currency: "USD",
    available: true,
  },
  company: null,
};
const MARIA_L: CustomerSearchRow = {
  ...MARIA,
  id: "01a0c000-0000-7000-8000-000000000978",
  customer_no: "C-00978",
  display_name: "Maria L. Lopez",
  verdict: "possible",
  agreed: ["name", "date_of_birth"],
  phone_last4: "7731",
  accounts: { count: 1, open_count: 1, rows: [account("a3", "AC-2026-00200", null, "0.000000")], outstanding_total: "0.000000", currency: "USD", available: true },
};
const MARIA_LAST: CustomerSearchRow = {
  ...MARIA,
  id: "01a0c000-0000-7000-8000-000000001203",
  customer_no: "C-01203",
  verdict: "name_phone",
  agreed: ["name", "phone"],
  last_occupant: true,
  date_of_birth: null,
  accounts: { count: 0, open_count: 0, rows: [], outstanding_total: "0.000000", currency: "USD", available: true },
};
const THREE: CustomerSearchResult = { result: "found", count: 3, customers: [MARIA, MARIA_L, MARIA_LAST] };

/** The host's half — the link and the *Not them*s live in the STEP. */
function Host(props: { result: CustomerSearchResult }) {
  const [linked, setLinked] = useState<CustomerSearchRow | null>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);
  return (
    <CustomerMatchPanel
      result={props.result}
      pending={false}
      failed={false}
      linkedId={linked?.id ?? null}
      linkedRow={linked}
      dismissed={dismissed}
      onLink={setLinked}
      onUnlink={() => setLinked(null)}
      onNotThem={(row) => setDismissed((current) => [...current, row.id])}
      timeZone="America/Detroit"
      dateFormat="MM/DD/YYYY"
    />
  );
}

function mount(result: CustomerSearchResult = THREE) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/annarbor/move-ins/new"]}>
        <Routes>
          <Route path="/:tenant/move-ins/new" element={<Host result={result} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("the customer search results table (images 01, 10, 11)", () => {
  it("three customers: one table, strongest first, every drawn column", () => {
    mount();
    expect(document.querySelectorAll("[data-match-block]")).toHaveLength(0); // no stacked cards
    expect(screen.getByText(t("customers.moveIn.customer.match.count", { count: 3 }))).toBeInTheDocument();
    expect(screen.getByText(t("customers.moveIn.customer.match.strongestFirst"))).toBeInTheDocument();
    const headers = Array.from(document.querySelectorAll("[data-match-table] thead th")).map((th) => th.textContent);
    expect(headers).toEqual([
      t("customers.moveIn.customer.match.col.open"),
      t("customers.moveIn.customer.match.col.match"),
      t("customers.moveIn.customer.match.col.customer"),
      t("customers.moveIn.customer.match.col.dob"),
      t("customers.moveIn.customer.match.col.phone"),
      t("customers.moveIn.customer.match.col.accounts"),
      t("customers.moveIn.customer.match.col.owed"),
      t("customers.moveIn.customer.match.col.actions"),
    ]);
    const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-match-row]"));
    expect(rows.map((row) => row.dataset.matchCustomerNo)).toEqual(["C-00412", "C-00978", "C-01203"]);
    const [first, second, third] = rows;
    expect(first.textContent).toContain("04/12/1988");
    expect(first.querySelector("[data-match-phone]")?.textContent).toBe("•••-0182");
    expect(first.querySelector("[data-match-accounts-count]")?.textContent).toBe("2 · 0 open");
    // Owed is a danger pill when due, a plain figure when not, a dash with no accounts.
    expect(first.querySelector("[data-match-owed] .pill.past")?.textContent).toBe("$42.10");
    expect(document.querySelectorAll("[data-match-owed] .pill")).toHaveLength(1);
    expect(second.querySelector("[data-match-owed]")?.textContent).toBe("$0.00");
    expect(second.querySelector("[data-match-accounts-count]")?.textContent).toBe("1 · 1 open");
    expect(third.querySelector("[data-match-owed]")?.textContent).toBe("—");
    expect(third.querySelector("[data-match-accounts-count]")?.textContent).toBe("0");
    // One coloured icon; the strength and what agreed are its name and tooltip.
    const mark = (row: HTMLElement) => row.querySelector("[data-match-mark]") as HTMLElement;
    expect(mark(first).getAttribute("aria-label")).toMatch(/^Existing customer · Name, date of birth,? and SSN match\.$/);
    expect(mark(second).getAttribute("aria-label")).toContain(t("customers.moveIn.customer.match.possible"));
    expect(mark(third).getAttribute("aria-label")).toContain(t("customers.moveIn.customer.match.last_occupant"));
    expect(third.querySelector("[data-match-lived-here]")).not.toBeNull();
    expect(first.querySelector("[data-match-lived-here]")).toBeNull();
    // Legend and the none-of-these fact.
    const legend = document.querySelector("[data-match-legend]")?.textContent ?? "";
    expect(legend).toContain(t("customers.moveIn.customer.match.found"));
    expect(legend).toContain(t("customers.moveIn.customer.match.possible"));
    expect(legend).toContain(t("customers.moveIn.customer.match.last_occupant"));
    expect(legend).toContain(t("customers.moveIn.customer.match.noneOfThese"));
    // B14 rule 31 — no handle anywhere a clerk reads.
    expect(document.body.textContent ?? "").not.toContain(MARIA.id);
  });

  it("the arrow opens a customer's accounts (image 10) and closes them again", () => {
    mount();
    const open = screen.getByRole("button", { name: t("customers.moveIn.customer.match.showAccounts", { name: "Maria Lopez · C-00412" }) });
    fireEvent.click(open);
    const sub = document.querySelector('[data-match-accounts-row="C-00412"]') as HTMLElement;
    expect(sub).not.toBeNull();
    const heads = Array.from(sub.querySelectorAll("thead th")).map((th) => th.textContent);
    expect(heads).toEqual([
      t("customers.moveIn.customer.match.col.account"),
      t("customers.moveIn.customer.match.col.address"),
      t("customers.moveIn.customer.match.col.state"),
      t("customers.moveIn.customer.match.col.outstanding"),
    ]);
    const text = sub.textContent ?? "";
    expect(text).toContain("AC-2024-00117");
    expect(text).toContain("14 Willow Bend");
    expect(text).toContain("Closed 01/15/2024");
    expect(text).toContain("$42.10 due");
    expect(text).toContain("88 Pine Vista · Unit 2");
    // The account number opens the account, under THIS tenant.
    expect(within(sub).getByRole("link", { name: "AC-2024-00117" }).getAttribute("href")).toBe("/annarbor/accounts/a2");
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.match.hideAccounts", { name: "Maria Lopez · C-00412" }) }));
    expect(document.querySelector('[data-match-accounts-row="C-00412"]')).toBeNull();
  });

  it("view customer opens the customers list for that number, in a new tab, under this tenant", () => {
    mount();
    const view = screen.getByRole("link", { name: t("customers.moveIn.customer.match.view", { name: "Maria Lopez · C-00412" }) });
    expect(view.getAttribute("href")).toBe("/annarbor/customers?q=C-00412");
    expect(view.getAttribute("target")).toBe("_blank");
    expect(view.getAttribute("rel")).toContain("noopener");
  });

  it("Link collapses the table to one Linked line (image 11); the unlink icon brings the table back", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.match.linkName", { name: "Maria Lopez · C-00412" }) }));
    expect(document.querySelector("[data-match-table]")).toBeNull();
    const line = document.querySelector('[data-customer-match="linked"]') as HTMLElement;
    expect(line.textContent).toContain(t("customers.moveIn.customer.match.linked"));
    expect(line.textContent).toContain("Maria Lopez · C-00412 · Existing customer");
    expect(line.textContent).toContain("2 accounts · $42.10 outstanding");
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.match.unlink") }));
    expect(document.querySelectorAll("[data-match-row]")).toHaveLength(3);
  });

  it("Not them drops that row; dropping every row says a new customer ID is given", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.match.notThemName", { name: "Maria L. Lopez · C-00978" }) }));
    expect(Array.from(document.querySelectorAll<HTMLElement>("[data-match-row]")).map((row) => row.dataset.matchCustomerNo)).toEqual(["C-00412", "C-01203"]);
    expect(screen.getByText(t("customers.moveIn.customer.match.count", { count: 2 }))).toBeInTheDocument();
    for (const name of ["Maria Lopez · C-00412", "Maria Lopez · C-01203"]) {
      fireEvent.click(screen.getAllByRole("button", { name: t("customers.moveIn.customer.match.notThemName", { name }) })[0]);
    }
    expect(document.querySelector('[data-customer-match="new"]')?.textContent).toContain(t("customers.moveIn.customer.match.newLine"));
  });
});
