// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-35 · task 23 — the S22 type selector and, on S33, the
//           day's cash total that EXCLUDES credits and adjustments. Its backend
//           half is task 22, which landed 2026-09-02 and made the defect live.
// Story:    US-PAY-004 TC-1 (the filter totals) · US-PAY-001 (the S22 modal)
// Screens:  S33 (the totals line) · S22 / S35 (the Record modal)
// Rules:    CS-35's own sentence — *"the day's cash total must EXCLUDE credits
//           and adjustments, or it will not tie to the drawer"* — and its
//           screen clause, *"a type selector (payment · credit · adjustment)
//           which hides the tender and reference fields for the latter two,
//           because there is no cheque and no bank line"* · BR-PAY-026 (the
//           tender vocabulary is the tenant's live list) · B2 O-4 (whether a
//           credit's sign lives on `amount` is UNRESOLVED and stays that way) ·
//           B14 rule 21 (this directory is NOT on route-b-migrated.txt) ·
//           B14 rule 32 (a line a clerk reads every day carries no noise) ·
//           CLAUDE.md rule 2 (money is a decimal string, never a number)
// Defects:  DEF-3207 — recording one credit blanked the day's takings figure
//           for the whole payments list.
// ───────────────────────────────────────────────────────
// §3's worked figure, and it is the one from the CR: **a day of $100.00 cash
// and a $25.00 credit banks $100.00 and lists the credit.** The drawer holds
// $100.00; the figure on screen has to be the one that ties to it.
//
// ⚠ **THE ASSERTION THAT MATTERS MOST IS THAT THE EXCLUDED ROW IS VISIBLE.** A
// total that quietly covers less than the list above it is worse than one that
// refuses, because nothing on the screen says which rows it left out. The old
// behaviour at least failed loudly; this must not fail quietly.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentMethodOption, PaymentsTotals } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

// ⚠ **`RecordPaymentModal` BECAME `RecordPaymentForm` ON 2026-09-23 (`DEF-PAY-6317`).**
// 2·3a is a PAGE at `/:tenant/payments/record/new` (blueprint p037), so the
// form is a COMPONENT (B14 rule 43) and the frame around it is `FormPage`
// rather than `FormModal`. The props are the same, with `onClose` renamed
// `onCancel` — a page goes BACK somewhere; it does not close. Every case below
// is unchanged and still asserts the same thing.
import { PaymentsTotalsLine } from "./PaymentsPage";
import { RecordPaymentForm } from "./RecordPaymentPage";
import type { Translator } from "@/features/tenancy/settingsShared";

const t: Translator = (key, params) => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

const METHODS: PaymentMethodOption[] = [
  { id: "met-cash", code: "cash", name: "Cash" },
  { id: "met-check", code: "check", name: "Check" },
];

function totals(over: Partial<PaymentsTotals> = {}): PaymentsTotals {
  return {
    count: 1,
    amount: "100.000000",
    currency: "USD",
    amount_unavailable: null,
    excluded_count: 0,
    ...over,
  };
}

function line(over: Partial<PaymentsTotals> = {}): string {
  return renderToStaticMarkup(<PaymentsTotalsLine totals={totals(over)} t={t} />);
}

afterEach(cleanup);

describe("DEF-3207 · a credit no longer blanks the day's takings", () => {
  it("$100.00 cash and a $25.00 credit shows $100.00 and says one row is not cash", () => {
    // The CR's own worked case. The drawer holds 100.00 and the figure ties.
    const html = line({ count: 2, amount: "100.000000", excluded_count: 1 });
    expect(html).toContain("100.00");
    expect(html).toContain(escaped(t("payments.totals.notCash")));
    // And the COUNT still names every matched row, so the two numbers together
    // tell a clerk that 2 rows produced 1 cash figure.
    expect(html).toContain(">2<");
  });

  it("the excluded figure is a COUNT and the credit's amount is never stated", () => {
    // Whether a credit's sign lives on `amount` is B2's own O-4 residue and is
    // still open. Counting is safe under either reading; summing is not.
    const html = line({ count: 2, amount: "100.000000", excluded_count: 1 });
    expect(html).not.toContain("25.00");
  });

  it("a day of pure cash carries NO extra item — rule 32, a line read every day", () => {
    const html = line({ count: 3, amount: "412.500000", excluded_count: 0 });
    expect(html).toContain("412.50");
    expect(html).not.toContain(escaped(t("payments.totals.notCash")));
  });

  it("the money label now says CASH, because that is what the figure is", () => {
    expect(line()).toContain(escaped(t("payments.totals.amount")));
    expect(t("payments.totals.amount")).toContain("Cash");
  });
});

describe("CS-35 · the three cases that still refuse a figure, each naming itself", () => {
  it("nothing matched is not $0.00 — that would be a claim about the day", () => {
    const html = line({ count: 0, amount: null, currency: null, amount_unavailable: "no_rows" });
    expect(html).toContain(escaped(t("payments.totals.unavailable.no_rows")));
    expect(html).not.toContain("0.00");
  });

  it("a filter holding ONLY credits says so rather than reading $0.00", () => {
    // "$0.00" here reads as "we took nothing", which is a different and wrong
    // statement from "nothing here was cash".
    const html = line({
      count: 2,
      amount: null,
      currency: null,
      amount_unavailable: "no_cash_rows",
      excluded_count: 2,
    });
    expect(html).toContain(escaped(t("payments.totals.unavailable.no_cash_rows")));
    expect(html).not.toContain("0.00");
  });

  it("the retired refusal is gone from the catalogue, not left as a dead entry", () => {
    // `signed_rows_unresolved` is no longer served by anything. A key with no
    // call site renders to nobody and G18 counts it.
    expect(t("payments.totals.unavailable.signed_rows_unresolved")).toBe(
      "payments.totals.unavailable.signed_rows_unresolved",
    );
    expect(t("payments.totals.unavailable.no_cash_rows")).not.toBe(
      "payments.totals.unavailable.no_cash_rows",
    );
  });

  it("more than one currency is untouched — this change did not widen that", () => {
    const html = line({ amount: null, currency: null, amount_unavailable: "mixed_currencies" });
    expect(html).toContain(escaped(t("payments.totals.unavailable.mixed_currencies")));
  });
});

describe("CS-35 · the S22 type selector, and what it hides", () => {
  function form() {
    // The modal runs the account picker's own `useQuery`, so it needs a client.
    // `retry: false` because a missing route here is not a flaky network.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          {/* ⚠ **THE ROUTER IS NOT DECORATION — `DEF-PAY-6334`.** All six cases
              below have failed since `P2.9` put `RecordCounterBanner` at the
              top of this form on 2026-09-23: the banner calls `useTenantPath`,
              which is `useLocation`, and a provider stack with no Router in it
              throws *"useLocation() may be used only in the context of a
              <Router> component"* before a single assertion runs. Six cases
              INCAPABLE OF PASSING (law 7), hidden by the other reds here.

              And it is mounted at the REAL PATH PATTERN rather than a bare
              `MemoryRouter`: without `/:tenant`, `useParams().tenant` is
              undefined and every address the form builds comes out
              `//payments/…` — a protocol-relative URL to another host that
              reads as a perfectly good string to `toContain`
              (`DEF-CWP-3925`). */}
          <MemoryRouter initialEntries={["/brazos/payments/record/new"]}>
            <Routes>
              <Route
                path="/:tenant/payments/record/new"
                element={
                  <RecordPaymentForm
            client={{ get: () => Promise.resolve({ data: null }) } as never}
            methods={METHODS}
            today="2026-09-02"
            dateFormat="MM/DD/YYYY"
            currency="USD"
                    onCancel={() => undefined}
                    onRecorded={() => undefined}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("the selector offers all three, and starts on Payment", () => {
    // `payment` is the default, so a clerk who never touches it sends exactly
    // what this form has always sent.
    form();
    const select = screen.getByLabelText(t("payments.form.type")) as HTMLSelectElement;
    expect(select.value).toBe("payment");
    expect([...select.options].map((o) => o.value)).toEqual([
      "payment",
      "credit",
      "adjustment",
    ]);
  });

  it("a PAYMENT keeps the tender and the reference — nothing was taken away", () => {
    form();
    expect(screen.queryByLabelText(t("payments.form.method"))).not.toBeNull();
    expect(screen.queryByLabelText(t("payments.form.confirmation"))).not.toBeNull();
  });

  it("choosing CREDIT hides both, because there is no cheque and no bank line", () => {
    form();
    fireEvent.change(screen.getByLabelText(t("payments.form.type")), {
      target: { value: "credit" },
    });
    expect(screen.queryByLabelText(t("payments.form.method"))).toBeNull();
    expect(screen.queryByLabelText(t("payments.form.confirmation"))).toBeNull();
  });

  it("choosing ADJUSTMENT hides them too — CS-35 names both of the latter two", () => {
    form();
    fireEvent.change(screen.getByLabelText(t("payments.form.type")), {
      target: { value: "adjustment" },
    });
    expect(screen.queryByLabelText(t("payments.form.method"))).toBeNull();
  });

  it("switching back to Payment brings them back EMPTY, not carrying the old value", () => {
    // A hidden field that keeps its value is how a credit acquires a cheque
    // number nobody typed. The state is cleared on the way out, so the way back
    // is blank.
    form();
    const type = screen.getByLabelText(t("payments.form.type"));
    fireEvent.change(screen.getByLabelText(t("payments.form.confirmation")), {
      target: { value: "8842" },
    });
    fireEvent.change(type, { target: { value: "credit" } });
    fireEvent.change(type, { target: { value: "payment" } });
    const reference = screen.getByLabelText(
      t("payments.form.confirmation"),
    ) as HTMLInputElement;
    expect(reference.value).toBe("");
  });

  it("the help sentence says WHY, in one sentence (B14 rule 32)", () => {
    form();
    expect(screen.queryByText(t("payments.form.typeHelp"))).not.toBeNull();
  });
});
