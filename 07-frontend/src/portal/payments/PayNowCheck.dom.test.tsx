// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09) · Screen: CWP-076 — blueprint 36 *Check
//           before you pay*, at `/{tenant}/portal/pay-now/check`
// Change:   CR-085 step 2 lane 6. PO 2026-09-11: *"it should be 3 screens -
//           confirmed"* · *"ii). Your ruling was about the shape, not the
//           addresses."*
// Rules:    R-10 (bad news carries its way out, on the same screen, next to the
//           message) · R-22 (three states, three sentences) · BR-CWP-056 (a
//           held control is visible, disabled and carries its reason) ·
//           CLAUDE.md hard rule 6 (ONE idempotency key, re-sent and never
//           re-minted) · B14 rule 31 (no database id on screen)
// Cases:    TC-7 (the commit carries the key the PREVIEW minted, and so does
//           the retry — read off the BODY that reaches the transport) · TC-1 /
//           TC-9 (a held commit says why, in the page text) · DEF-CWP-4868 (a
//           declined payment is not a dead end) · the wrong-turn card · only
//           `paid` leaves for CWP-077
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **STRUCTURE, FIGURES, REFUSAL CODES AND ADDRESSES — not copy**, which is
// the discipline `PayNow.dom.test.tsx` records in full. The exceptions are the
// sentences that are already in all eleven catalogues, where `t()` answers the
// words rather than the key and asserting them is asserting the product.
//
// ⚠ **MOUNTED ROUTED, AND THAT IS WHAT MAKES THE ADDRESS ASSERTIONS ABLE TO
// FAIL** (hard-won law 2's fixture clause). A `MemoryRouter` with no matching
// `<Route>` binds no params, so `usePortalPath` builds `//portal/…` — a
// protocol-relative URL to another host that reads as a perfectly good string
// to `toContain`.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalPayNow, PortalPayPreview, PortalPayResult } from "../api/payNowClient";

// Plain functions rather than `vi.fn()` — a recording stand-in reaches a
// rejected promise before the screen's own `catch` does.
let readScreen: () => Promise<PortalPayNow> = async () => {
  throw new Error("no behaviour set");
};
let readPreview: () => Promise<PortalPayPreview> = async () => {
  throw new Error("no behaviour set");
};
let doPay: () => Promise<PortalPayResult> = async () => {
  throw new Error("no behaviour set");
};
/** ⚠ EVERY BODY THAT REACHED THE TRANSPORT. TC-7 is asserted off this and off
 *  nothing else: the only assertion a screen that re-minted its key on every
 *  attempt cannot pass is one that reads the key it actually SENT. */
let sent: Array<[string, Record<string, unknown>]> = [];

vi.mock("../api/payNowClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/payNowClient");
  return {
    ...actual,
    getPayNow: () => readScreen(),
    previewPayment: (_id: string, body: Record<string, unknown>) => {
      sent.push(["preview", body]);
      return readPreview();
    },
    payNow: (_id: string, body: Record<string, unknown>) => {
      sent.push(["pay", body]);
      return doPay();
    },
  };
});

const { PayNowCheckView } = await import("./PayNowCheck");

const MINTED = "pay_26_08841";

const CHASE = {
  id: "9f1c-not-shown",
  label: "Chase ••••4021",
  brand: "Chase",
  last_four: "4021",
  kind: "bank" as const,
  status: "verified",
  used_for: ["autopay", "one_off"],
  expires_month: null,
  expires_year: null,
  selectable: true,
  held_reason: null,
};

const PAYABLE: PortalPayNow = {
  account_no: "A-10432",
  balance: "142.1800",
  currency: "USD",
  bills: [],
  bill_count: 1,
  instruments: [CHASE],
  can_pay: true,
  held_reason: null,
  order: "oldest_first",
  environment: "sandbox",
  problems: [],
};

const PRICED: PortalPayPreview = {
  amount: "40.0000",
  currency: "USD",
  order: "oldest_first",
  lands_on: [
    { number: "BL-2608-0141", owing: "142.1800", paying: "40.0000", owing_after: "102.1800" },
  ],
  credit_carried: "0.0000",
  remaining_balance: "102.1800",
  idempotency_key: MINTED,
  writes: [],
};

const PAID: PortalPayResult = {
  outcome: "paid",
  held_reason: null,
  payment_no: "PMT-26-09014",
  amount: "40.0000",
  currency: "USD",
  lands_on: PRICED.lands_on,
  idempotency_key: MINTED,
  environment: "sandbox",
  problems: [],
};

const HANDOFF = { amount: "40.0000", instrumentId: CHASE.id, idempotencyKey: MINTED };

/** The probe at `CWP-077`'s address — the receipt travels in router state, so
 *  this is the only way to assert WHAT was handed on. */
function Landed() {
  const location = useLocation();
  return <div data-landed-done={JSON.stringify(location.state)} />;
}

function draw(state: unknown = HANDOFF) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: "/pine-hill/portal/pay-now/check", state }]}>
      <Routes>
        <Route
          path="/:tenant/portal/pay-now/check"
          element={<PayNowCheckView accountId="acc-1" />}
        />
        <Route path="/:tenant/portal/pay-now/done" element={<Landed />} />
        <Route path="/:tenant/portal/pay-now" element={<div data-landed-choose="" />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** The Pay control, however it is drawn — disabled with its reason, or live. */
function payControl(container: HTMLElement): HTMLButtonElement {
  return container.querySelector('[data-pay-control="commit"] button') as HTMLButtonElement;
}

beforeEach(() => {
  sent = [];
  readScreen = async () => PAYABLE;
  readPreview = async () => PRICED;
  doPay = async () => PAID;
});
afterEach(cleanup);

describe("CWP-076 · check before you pay (US-CWP-045)", () => {
  it("re-reads the figures rather than carrying them, and shows the total and the landing", async () => {
    const { container } = draw();
    expect(await screen.findByTestId("pay-now-check")).toBeInTheDocument();
    expect(container.querySelector('[data-screen="CWP-076"]')).not.toBeNull();

    // ⚠ **IT ASKED THE SERVER AGAIN.** What step one hands on is the CHOICE,
    // not the answer — which is what makes the drawing's `AMOUNT CHANGED` state
    // real: a payment that landed in between changes what is about to be taken.
    await waitFor(() =>
      expect(sent.some((one) => one[0] === "preview" && one[1].amount === "40.0000")).toBe(true),
    );
    // ⚠ **AND IT PRESENTED THE KEY IT WAS GIVEN**, so the re-price, the commit
    // and every retry of it carry ONE string (hard rule 6).
    expect(sent.find((one) => one[0] === "preview")?.[1].idempotency_key).toBe(MINTED);

    expect(container.querySelector("[data-check-total]")?.textContent).toBe("$40.00");
    expect(container.querySelector("[data-check-after]")?.textContent).toBe("$102.18");
    expect(container.querySelector("[data-check-method]")?.textContent).toBe("Chase ••••4021");
    // B14 rule 31 — the instrument id travels, and is never on the glass.
    expect(container.textContent ?? "").not.toContain("not-shown");
  });

  it("TC-7 · the commit carries the key the PREVIEW minted, and so does the retry", async () => {
    doPay = async () => ({
      outcome: "no_answer",
      held_reason: null,
      payment_no: null,
      amount: "40.0000",
      currency: "USD",
      lands_on: [],
      idempotency_key: MINTED,
      environment: "sandbox",
      problems: [{ code: "gateway_did_not_answer" }],
    });
    const user = userEvent.setup();
    const { container } = draw();
    await screen.findByTestId("pay-now-check");
    await waitFor(() => expect(payControl(container)).toBeEnabled());
    await user.click(payControl(container));

    // ⚠ **READ OFF THE BODY THAT REACHED THE TRANSPORT** — the only assertion a
    // screen that re-minted its key on every attempt cannot pass.
    await waitFor(() => expect(sent.some((one) => one[0] === "pay")).toBe(true));
    expect(sent.find((one) => one[0] === "pay")?.[1].idempotency_key).toBe(MINTED);

    // TC-6: it SAYS the provider did not answer, and it offers the retry rather
    // than a dead end. ⚠ **AND IT DID NOT LEAVE FOR `CWP-077`** — only `paid`
    // does, because a screen called *Payment made* must not be reachable
    // without one.
    expect(container.querySelector('[data-pay-outcome="no_answer"]')).not.toBeNull();
    expect(container.querySelector("[data-landed-done]")).toBeNull();

    await user.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    await waitFor(() => expect(payControl(container)).toBeEnabled());
    await user.click(payControl(container));
    await waitFor(() => expect(sent.filter((one) => one[0] === "pay")).toHaveLength(2));
    // ⚠ **THE SAME STRING, BOTH TIMES.** A debit that already happened at the
    // provider is refused there on this key, so it is never taken twice.
    expect(sent.filter((one) => one[0] === "pay").map((one) => one[1].idempotency_key)).toEqual([
      MINTED,
      MINTED,
    ]);
  });

  /**
   * `DEF-CWP-4868` — **a declined payment was a dead end.**
   *
   * Measured in a browser at 390 and at 1280 on 2026-09-11: `declined` →
   * `controls: []`, `refused` → `controls: []`. The screen said *"No money was
   * taken. Try another card or bank account."* and offered no way to do either
   * — no back, no retry, no door to `/payment-methods` — and the form the
   * customer had filled in was gone. That is R-10 broken on the outcome a real
   * processor produces most often, and it is `DEF-CWP-3972`'s shape: a refusal
   * naming an action that is unreachable from where the person is standing.
   */
  describe("DEF-CWP-4868 · a declined payment carries its way out", () => {
    beforeEach(() => {
      doPay = async () => ({
        outcome: "declined",
        held_reason: null,
        payment_no: null,
        amount: "40.0000",
        currency: "USD",
        lands_on: [],
        idempotency_key: MINTED,
        environment: "sandbox",
        problems: [],
      });
    });

    it("draws the doors BESIDE the sentence, by address", async () => {
      const user = userEvent.setup();
      const { container } = draw();
      await screen.findByTestId("pay-now-check");
      await waitFor(() => expect(payControl(container)).toBeEnabled());
      await user.click(payControl(container));

      const outcome = await waitFor(() => {
        const found = container.querySelector('[data-pay-outcome="declined"]');
        expect(found).not.toBeNull();
        return found as HTMLElement;
      });
      // ⚠ **R-10 LITERALLY: *on that same screen, next to the message*.** The
      // ways out are INSIDE the block that carries the sentence, asserted by
      // containment — a test that only asked *does a link exist* would pass
      // with them in the page head or a rail.
      const waysOut = outcome.querySelector("[data-ways-out]");
      expect(waysOut).not.toBeNull();
      const methods = outcome.querySelector('[data-way-out="methods"]') as HTMLAnchorElement;
      expect(methods).toHaveAttribute("href", "/pine-hill/portal/payment-methods");
      const change = outcome.querySelector('[data-way-out="change"]') as HTMLAnchorElement;
      expect(change).toHaveAttribute("href", "/pine-hill/portal/pay-now");
      // ⚠ **AND *try again* IS NOT OFFERED ON A DECLINE.** Trying the same card
      // again is the one thing that cannot work, and offering it is how a
      // refusal starts naming an action that leads nowhere.
      expect(outcome.querySelector('[data-way-out="try-again"]')).toBeNull();
    });

    it("keeps the amount and the method on screen — blueprint 35's own DECLINED state", async () => {
      const user = userEvent.setup();
      const { container } = draw();
      await screen.findByTestId("pay-now-check");
      await waitFor(() => expect(payControl(container)).toBeEnabled());
      await user.click(payControl(container));

      await waitFor(() =>
        expect(container.querySelector('[data-pay-outcome="declined"]')).not.toBeNull(),
      );
      // *"the amount and method stay selected"* — the drawing's words.
      expect(container.querySelector("[data-check-total]")?.textContent).toBe("$40.00");
      expect(container.querySelector("[data-check-method]")?.textContent).toBe("Chase ••••4021");
    });
  });

  it("only `paid` leaves for CWP-077, and it hands on the SERVER's balance", async () => {
    const user = userEvent.setup();
    const { container } = draw();
    await screen.findByTestId("pay-now-check");
    await waitFor(() => expect(payControl(container)).toBeEnabled());
    await user.click(payControl(container));

    const landed = await waitFor(() => {
      const probe = container.querySelector("[data-landed-done]");
      expect(probe).not.toBeNull();
      return probe as HTMLElement;
    });
    const state = JSON.parse(landed.getAttribute("data-landed-done") ?? "null");
    expect(state.result.outcome).toBe("paid");
    expect(state.result.payment_no).toBe("PMT-26-09014");
    // ⚠ **THE BALANCE IS THE PREVIEW'S `remaining_balance`, CARRIED.** The
    // commit's own body has no balance on it, and a receipt that subtracted one
    // in the browser would be a second answer to *where do I stand*.
    expect(state.balanceAfter).toBe("102.1800");
  });

  /**
   * `DEF-CWP-4866` — a refusal only a mouse could read. See
   * `PayNow.dom.test.tsx`'s block for the measurement; this is the same fault
   * on the screen that actually takes the money.
   */
  it("DEF-CWP-4866 · a held commit says why, in the page TEXT", async () => {
    readScreen = async () => ({
      ...PAYABLE,
      can_pay: false,
      held_reason: "no_payment_provider_connected",
    });
    const { container } = draw();
    await screen.findByTestId("pay-now-check");

    const pay = payControl(container);
    expect(pay).toBeDisabled();
    expect(container.querySelector("[data-commit-reason]")?.textContent).toBe(
      "We cannot take card payments yet.",
    );
    // ⚠ **AND NOTHING IS PROMISED OVER IT** (`DEF-CWP-4867`).
    expect(container.querySelector("[data-consequence]")).toBeNull();
  });

  it("blueprint 36's METHOD EXPIRED · caught here, with the card's OWN reason", async () => {
    readScreen = async () => ({
      ...PAYABLE,
      instruments: [{ ...CHASE, selectable: false, held_reason: "card_has_expired" }],
    });
    const { container } = draw();
    await screen.findByTestId("pay-now-check");

    expect(payControl(container)).toBeDisabled();
    // Not the generic *Add a card or bank account.* — `BR-CWP-056` asks for THE
    // reason, and *"your card expired"* is a different instruction from *"you
    // have no card"*.
    expect(container.querySelector("[data-commit-reason]")?.textContent).toBe(
      "This card has expired.",
    );
  });

  it("arriving with nothing is a WRONG TURN, not an error, and the door back is live", async () => {
    const { container } = draw(null);
    expect(await screen.findByTestId("pay-now-check-no-handoff")).toBeInTheDocument();
    // R-22 — this is EMPTY, and the attribute is the only thing a check can
    // read to tell the three apart.
    expect(container.querySelector('[data-portal-state="empty"]')).not.toBeNull();
    const door = container.querySelector('[data-way-out="start-again"]') as HTMLAnchorElement;
    expect(door).toHaveAttribute("href", "/pine-hill/portal/pay-now");
    // ⚠ **AND NOTHING WAS ASKED OF THE SERVER.** There is nothing to ask about.
    expect(sent).toEqual([]);
  });

  it("a failed read says so, in its own words, with a way out", async () => {
    readPreview = async () => {
      throw new Error("nope");
    };
    const { container } = draw();
    expect(await screen.findByTestId("pay-now-check-failed")).toBeInTheDocument();
    expect(container.querySelector('[data-portal-state="failed"]')).not.toBeNull();
    // R-22: a failed sentence and a loading sentence are different strings.
    expect(container.querySelector('[data-state-sentence="failed"]')?.textContent).toBe(
      "We could not check this. Nothing has been taken.",
    );
    expect(container.querySelector('[data-way-out="change"]')).not.toBeNull();
    expect(screen.queryByTestId("pay-now-check")).toBeNull();
  });

  it("the page head and the screen id survive every branch", async () => {
    readPreview = async () => {
      throw new Error("nope");
    };
    const { container } = draw();
    await screen.findByTestId("pay-now-check-failed");
    // `DEF-CWP-4926` — the head is built once, above the branches.
    expect(container.querySelector('[data-screen="CWP-076"]')).not.toBeNull();
    expect(container.querySelector("h1")).not.toBeNull();
    const back = container.querySelector('[data-testid="check-back"]') as HTMLAnchorElement;
    expect(back).toHaveAttribute("href", "/pine-hill/portal/pay-now");
  });
});
