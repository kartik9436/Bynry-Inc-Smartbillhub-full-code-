// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09) · Screen: CWP-077 — blueprint 37 *Payment
//           made*, at `/{tenant}/portal/pay-now/done`
// Change:   CR-085 step 2 lane 6. PO 2026-09-11: *"it should be 3 screens -
//           confirmed"* · *"ii). Your ruling was about the shape, not the
//           addresses."*
// Rules:    R-22 (three states, three sentences) · B14 rule 31 (the `PMT-`
//           number, never a row id) · CLAUDE.md hard rule 2 (2 dp) · hard rule
//           4 (a receipt, never a form)
// Cases:    the receipt · **a screen called *Payment made* cannot be reached
//           without one** · the sandbox sentence · the wrong-turn card
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { PortalPayResult } from "../api/payNowClient";
import { PayNowDoneView } from "./PayNowDone";

const PAID: PortalPayResult = {
  outcome: "paid",
  held_reason: null,
  payment_no: "PMT-26-09014",
  amount: "40.0000",
  currency: "USD",
  lands_on: [
    { number: "BL-2608-0141", owing: "142.1800", paying: "40.0000", owing_after: "102.1800" },
  ],
  idempotency_key: "pay_26_08841",
  environment: null,
  problems: [],
};

function draw(state: unknown) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: "/pine-hill/portal/pay-now/done", state }]}>
      <Routes>
        <Route path="/:tenant/portal/pay-now/done" element={<PayNowDoneView />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-077 · payment made (US-CWP-045)", () => {
  it("names the payment, the figure and where it landed", async () => {
    const { container } = draw({ result: PAID, balanceAfter: "102.1800" });
    expect(await screen.findByTestId("pay-now-done")).toBeInTheDocument();
    expect(container.querySelector('[data-screen="CWP-077"]')).not.toBeNull();

    // B14 rule 31 — the `PMT-` number a customer would read out on the
    // telephone, never a row id.
    expect(container.querySelector("[data-payment-no]")?.textContent).toBe("PMT-26-09014");
    // Hard rule 2 — four decimals stored, two displayed.
    expect(container.querySelector("[data-paid-amount]")?.textContent).toBe("$40.00");
    expect(container.querySelector("[data-done-after='0']")?.textContent).toBe("$102.18");
    // Blueprint 37's own note: *the balance AFTER the payment is on the
    // confirmation*, and it is the SERVER's figure carried, never a
    // subtraction made here.
    expect(container.querySelector("[data-balance-after]")?.textContent).toBe("$102.18");
  });

  it("points at the payments list BY ADDRESS", async () => {
    const { container } = draw({ result: PAID, balanceAfter: "102.1800" });
    await screen.findByTestId("pay-now-done");

    // ⚠ **BY ADDRESS AND NOT BY PRESENCE** (`DEF-CWP-3925`, hard-won law 2's
    // fixture clause). Mounted bare this would read `//portal/payments` — a
    // protocol-relative URL to another host — and `toContain("/payments")`
    // would call it a perfectly good string.
    const links = Array.from(container.querySelectorAll("a"));
    const toList = links.find((one) => one.getAttribute("href")?.endsWith("/payments"));
    expect(toList).toBeDefined();
    expect(toList).toHaveAttribute("href", "/pine-hill/portal/payments");
  });

  /**
   * ⚠ **THE TRAP THE SPLIT RULING NAMED, AND THE TEST THAT CLOSES IT.**
   *
   * `/pay`'s own route comment records that *the lookup ships and the payment
   * does not — no gateway exists, so the Pay control renders disabled carrying
   * its reason.* **A screen called *Payment made* must not imply money moved on
   * a tenant with no gateway.** So the only state this screen accepts is a
   * result the server answered `paid`; every other outcome stays on `CWP-076`
   * where the way out is, and anything else arriving here is read as no receipt
   * at all.
   */
  describe("a screen called *Payment made* cannot be reached without one", () => {
    for (const outcome of ["declined", "no_answer", "refused"] as const) {
      it(`refuses a ${outcome} result and draws the wrong-turn card instead`, async () => {
        const { container } = draw({ result: { ...PAID, outcome }, balanceAfter: null });
        expect(await screen.findByTestId("pay-now-no-receipt")).toBeInTheDocument();
        expect(screen.queryByTestId("pay-now-done")).toBeNull();
        // The words a customer reads must not say a payment was made.
        expect(container.querySelector("h1")?.textContent).toBe(
          "We cannot show that receipt here",
        );
        expect(container.querySelector("[data-payment-no]")).toBeNull();
      });
    }

    it("a reload with no state at all is EMPTY, not FAILED, with two live doors", async () => {
      const { container } = draw(null);
      expect(await screen.findByTestId("pay-now-no-receipt")).toBeInTheDocument();
      // R-22 — the kind is in the DOM because no check can read whether a
      // sentence MEANS empty.
      expect(container.querySelector('[data-portal-state="empty"]')).not.toBeNull();
      const payments = container.querySelector('[data-way-out="payments"]') as HTMLAnchorElement;
      expect(payments).toHaveAttribute("href", "/pine-hill/portal/payments");
      const payNow = container.querySelector('[data-way-out="pay-now"]') as HTMLAnchorElement;
      expect(payNow).toHaveAttribute("href", "/pine-hill/portal/pay-now");
    });
  });

  it("a sandbox tenant says on the receipt that no real money moved", async () => {
    const { container } = draw({
      result: { ...PAID, environment: "sandbox" },
      balanceAfter: "102.1800",
    });
    await screen.findByTestId("pay-now-done");
    expect(container.querySelector("[data-sandbox]")?.textContent).toBe(
      "This utility is still testing. No real money moves.",
    );
  });

  it("says where to look instead when no balance was priced, rather than drawing a dash", async () => {
    const { container } = draw({ result: PAID, balanceAfter: null });
    await screen.findByTestId("pay-now-done");
    // R-23's shape and B14 rule 17: an absence gets a sentence, never an em
    // dash a customer reads as zero.
    expect(container.querySelector("[data-balance-after]")).toBeNull();
    expect(container.querySelector("[data-no-balance]")?.textContent).toBe(
      "Your payments list shows what is left owing.",
    );
  });

  it("is a receipt and not a form — no commit control anywhere on it", async () => {
    const { container } = draw({ result: PAID, balanceAfter: "102.1800" });
    await screen.findByTestId("pay-now-done");
    // Hard rule 4 — a payment is never edited; a correction is a new row.
    expect(container.querySelector("[data-pay-control]")).toBeNull();
    expect(container.querySelectorAll("button")).toHaveLength(0);
  });
});
