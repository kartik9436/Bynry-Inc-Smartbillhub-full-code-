// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-10706 (tester L1-08) — one cheque could not be split across
//          a landlord's units from any screen
// Ruling:  PO 2026-10-30 Q4 = A — "Pay for…" exactly as the approved mock-up ·
//          BR-PAY-1126..1130 (a master may pay its units; leftover = the
//          master's credit; a split must sum exactly or nothing commits)
// ───────────────────────────────────────────────────────
/**
 * Grand Vista Properties (AC-2026-00618) pays units 101–108 with cheque #5521
 * for **$1,003.60** — nine open bills on eight accounts (unit 103 has an older
 * $40.00 balance as well as October's $92.10), the mock-up's own figures.
 *
 * Mounted under the real path pattern with the master in router STATE, as the
 * *Pay units* door hands it over (`payUnitsDoor.dom.test.tsx` asserts the door).
 *
 * RED FIRST: before this change Record payment had no *Pay for* switch and
 * nothing in the product called `/premises-position` or `/premises-payments`.
 *
 * WHAT WOULD MAKE THESE PASS WRONGLY: a commit that posts whatever is typed and
 * lets the server refuse — so the $0.01-short case asserts NOTHING was posted;
 * a body that sends one part per BILL (the server keys parts per account and
 * would take unit 103 twice) — so the body is asserted to hold eight parts and
 * unit 103's part to carry two targets.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { OpenBillRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import type { PremisesPosition, TenderBody } from "./PayForSeveral";
import { RecordPaymentPage } from "./RecordPaymentPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);
const TENANT = "brazosbend";
const MASTER = "0192f0aa-0618-7d3b-9a55-2f1d3c4b5a60";

function bill(number: string, total: string, owes: string, issued = "2026-10-01"): OpenBillRow {
  return {
    invoice_id: `inv-${number}`,
    number,
    issued_on: issued,
    total,
    amount_due: total,
    allocated: "0.0000",
    open_balance: owes,
    currency: "USD",
    composition: null,
  };
}

const UNITS: [string, string, string, OpenBillRow[]][] = [
  ["Unit 101", "AC-2026-00622", "M. Ortiz", [bill("BL-2610-000412", "121.4000", "121.4000")]],
  ["Unit 102", "AC-2026-00623", "L. Chen", [bill("BL-2610-000413", "118.7500", "118.7500")]],
  [
    "Unit 103",
    "AC-2026-00624",
    "P. Rivera",
    [
      bill("BL-2609-000377", "86.0000", "40.0000", "2026-09-01"),
      bill("BL-2610-000414", "92.1000", "92.1000"),
    ],
  ],
  ["Unit 104", "AC-2026-00625", "S. Novak", [bill("BL-2610-000415", "109.8000", "109.8000")]],
  ["Unit 105", "AC-2026-00626", "Vacant", [bill("BL-2610-000416", "127.3500", "127.3500")]],
  ["Unit 106", "AC-2026-00627", "A. Bauer", [bill("BL-2610-000417", "115.2000", "115.2000")]],
  ["Unit 107", "AC-2026-00628", "K. Mensah", [bill("BL-2610-000418", "141.6000", "141.6000")]],
  ["Unit 108", "AC-2026-00629", "R. Dutta", [bill("BL-2610-000419", "137.4000", "137.4000")]],
];

const POSITION: PremisesPosition = {
  payer: {
    id: MASTER,
    account_no: "AC-2026-00618",
    name: "Grand Vista Properties",
    own_total_open: "0.0000",
    own_bills: [],
  },
  units: UNITS.map(([label, accountNo, holder, bills]) => ({
    unit_id: `u-${label}`,
    label,
    accounts: [
      {
        account_id: `acc-${accountNo}`,
        account_no: accountNo,
        customer_name: holder,
        currency: "USD",
        bills,
        total_open: null,
        bill_count: bills.length,
        problems: [],
      },
    ],
  })),
  unit_count: 8,
  units_total_open: "1003.6000",
};

const METHODS = [{ id: "m-check", code: "check", name: "Cheque" }];

function clientFor(post: (path: string, body: TenderBody) => Promise<unknown>): ApiClient {
  return {
    get: vi.fn(async (path: string) => {
      if (path.endsWith("/premises-position")) return { status: 200, data: POSITION };
      if (path.startsWith("/payments")) {
        return { status: 200, data: { results: [], count: 0, methods: METHODS, totals: {} } };
      }
      return { status: 200, data: { results: [], count: 0 } };
    }),
    post: vi.fn(post),
  } as unknown as ApiClient;
}

function recordedTender(body: TenderBody) {
  return {
    status: 201,
    data: {
      created: true,
      amount: body.amount,
      currency: "USD",
      reference: body.reference,
      part_count: body.parts.length,
      payments: body.parts.map((part, index) => ({
        id: `p-${index}`,
        payment_no: `PY-261031-${String(index + 1).padStart(4, "0")}`,
        created: true,
        status: "posted",
        amount: part.amount,
        currency: "USD",
        applied: part.amount,
        credit_carried: "0",
        allocations: [],
        problems: [],
      })),
    },
  };
}

function mount(client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[
            {
              pathname: `/${TENANT}/payments/record/new`,
              state: { payFor: { id: MASTER, accountNo: "AC-2026-00618", kind: "master" } },
            },
          ]}
        >
          <Routes>
            <Route
              path="/:tenant/payments/record/new"
              element={
                <RecordPaymentPage
                  client={client}
                  today="2026-10-31"
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function fillCheque(amount: string) {
  await screen.findByText("BL-2610-000419");
  fireEvent.change(document.getElementById("amount") as HTMLElement, {
    target: { value: amount },
  });
  fireEvent.change(document.getElementById("method") as HTMLElement, {
    target: { value: "check" },
  });
  fireEvent.change(document.getElementById("confirmation") as HTMLElement, {
    target: { value: "5521" },
  });
}

const recordButton = () => screen.getByRole("button", { name: t("payments.form.submit") });

describe("DEF-PAY-10706 — Pay for several accounts (Grand Vista, cheque #5521)", () => {
  it("Pay units opens on Several accounts with the master's units grouped, each bill pre-filled", async () => {
    mount(clientFor(async () => ({ status: 201, data: null })));
    expect(screen.getByRole("radio", { name: t("payments.payFor.several") })).toBeChecked();
    await screen.findByText("BL-2610-000419");
    // Grouped by unit, the unit's account number and holder on the group row.
    const groups = document.querySelectorAll("[data-pay-for-group]");
    expect(groups).toHaveLength(8);
    expect(groups[2].textContent).toBe("Unit 103 · AC-2026-00624 · P. Rivera");
    expect(
      (
        screen.getByLabelText(
          t("payments.openBills.amountFor", { number: "BL-2609-000377" }),
        ) as HTMLInputElement
      ).value,
    ).toBe("40.00");
    expect(document.querySelector("[data-pay-for-owes]")?.textContent).toBe(
      "Owes $1,003.60 across 9 bills on 8 accounts",
    );
    // The master's own row, where a leftover becomes its credit.
    expect(document.querySelector("[data-pay-for-credit-row]")?.textContent).toContain(
      "Own account · AC-2026-00618",
    );
    // No database id anywhere on screen (B14 rule 31).
    expect(document.body.textContent).not.toContain(MASTER);
    expect(document.body.textContent).not.toContain("acc-AC-2026");
  });

  it("$1,003.60 across units 101–108 posts eight parts to the premises route", async () => {
    const posted: { path: string; body: TenderBody }[] = [];
    mount(
      clientFor(async (path, body) => {
        posted.push({ path, body });
        return recordedTender(body);
      }),
    );
    await fillCheque("1003.60");
    expect(
      document.querySelector("[data-left-to-allocate]")?.getAttribute("data-left-to-allocate"),
    ).toBe("zero");
    expect(document.querySelector("[data-left-to-allocate]")?.textContent).toBe(
      "Left to allocate$0.00",
    );
    const will = document.querySelector('[data-consequence="pay-for"]') as HTMLElement;
    expect(will.textContent).toContain("8 payments · $1,003.60");
    expect(will.textContent).toContain("From one Cheque #5521.");
    expect(will.textContent).toContain("Ready to record.");
    fireEvent.click(recordButton());
    await waitFor(() => expect(posted).toHaveLength(1));
    const [{ path, body }] = posted;
    expect(path).toBe(`/accounts/${MASTER}/premises-payments`);
    expect(body.amount).toBe("1003.60");
    expect(body.reference).toBe("5521");
    expect(body.method).toBe("check");
    expect(body.parts).toHaveLength(8);
    const unit103 = body.parts.find((part) => part.account_id === "acc-AC-2026-00624");
    expect(unit103?.amount).toBe("132.100000");
    expect(unit103?.targets).toEqual([
      { invoice_number: "BL-2609-000377", amount: "40.00" },
      { invoice_number: "BL-2610-000414", amount: "92.10" },
    ]);
    expect(body.parts.every((part) => part.apply_to === "split")).toBe(true);
    // The result: eight PY- numbers, one per account.
    const recorded = await screen.findByText("Recorded 8 payments · $1,003.60", { selector: "p" });
    const table = within(recorded.parentElement as HTMLElement);
    expect(table.getByText("PY-261031-0008").textContent).toBe("PY-261031-0008");
    expect(table.getByText("AC-2026-00629").textContent).toBe("AC-2026-00629");
  });

  it("$0.01 short: Left to allocate reads $0.01, Record payment is blocked and nothing is posted", async () => {
    const post = vi.fn(async () => ({ status: 201, data: null }));
    mount(clientFor(post));
    await fillCheque("1003.61");
    expect(document.querySelector("[data-left-to-allocate]")?.textContent).toBe(
      "Left to allocate$0.01",
    );
    expect(recordButton()).toBeDisabled();
    expect(screen.getByText(t("payments.payFor.allocateRest"))).toBeInTheDocument();
    fireEvent.click(recordButton());
    expect(post).not.toHaveBeenCalled();
  });

  it("the leftover goes on the master's own row and posts as the master's credit", async () => {
    const posted: TenderBody[] = [];
    mount(
      clientFor(async (_path, body) => {
        posted.push(body);
        return recordedTender(body);
      }),
    );
    await fillCheque("1023.60");
    expect(document.querySelector("[data-left-to-allocate]")?.textContent).toBe(
      "Left to allocate$20.00",
    );
    fireEvent.change(
      screen.getByLabelText(t("payments.payFor.creditFor", { account: "AC-2026-00618" })),
      { target: { value: "20.00" } },
    );
    expect(document.querySelector('[data-consequence="pay-for"]')?.textContent).toContain(
      "$20.00 becomes credit on AC-2026-00618.",
    );
    fireEvent.click(recordButton());
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].parts).toHaveLength(9);
    expect(posted[0].parts[8]).toEqual({
      account_id: MASTER,
      amount: "20.00",
      apply_to: "carry_credit",
    });
  });

  it("no open counter: the server's refusal is shown and nothing is recorded", async () => {
    mount(
      clientFor(async () => {
        throw new ApiError(422, {
          code: "BIZ-COMPLETENESS",
          message_key: "payments.counter.till_required",
          params: { detail: "no till" },
        });
      }),
    );
    await fillCheque("1003.60");
    fireEvent.click(recordButton());
    expect(
      await screen.findByText(t("payments.counter.till_required", { detail: "no till" })),
    ).toBeInTheDocument();
    expect(document.querySelector("[data-pay-for-recorded]")).toBeNull();
  });
});
