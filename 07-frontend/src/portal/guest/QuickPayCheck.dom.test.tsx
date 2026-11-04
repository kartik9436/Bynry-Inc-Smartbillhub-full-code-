// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-004 (EP-CWP-02) · Screen: CWP-003 · wireframes/CWP-003.png
// Rules:    BR-CWP-019/020 (the amount owing and a MASKED name, masked
//           SERVER-SIDE) · BR-CWP-021 (a guest sees an amount and a status,
//           never a person) · BR-CWP-023 (five wrong tries — step 2 is the
//           SAME door) · BR-CWP-057 (a token, a brand, a last four — never a
//           card number) · BR-CWP-058 (where the money lands, BEFORE the
//           button) · B14 rule 31 (no database id is a visible value) ·
//           rule 36 (compose the kit — no raw <button>)
// Cases:    the amount is RE-READ on load rather than carried · the masked
//           name is rendered verbatim and the full name is nowhere in the
//           markup · the card number is TOKENISED and never posted · the
//           consequence box names the figure and the bill before the button ·
//           a settled bill offers no card form · a refusal renders one
//           sentence · arriving with no handoff offers the live door back BY
//           ADDRESS · paying lands on /pine-hill/portal/pay/done carrying the
//           receipt
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { BillLookupView, GuestPayment, GuestPaymentReceipt } from "../api/guestClient";

// Plain functions rather than `vi.fn()` — a recording stand-in reaches a
// rejected promise before the screen's own `catch` does (the reasoning
// `MyDetails.dom.test.tsx` records one directory over).
let lookedUp: Array<[string, string]> = [];
let paid: Array<[string, GuestPayment]> = [];
let lookupAnswer: () => Promise<BillLookupView> = async () => {
  throw new Error("no behaviour set");
};
let payAnswer: () => Promise<GuestPaymentReceipt> = async () => {
  throw new Error("no behaviour set");
};

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    lookUpBill: (billNumber: string, postcode: string) => {
      lookedUp.push([billNumber, postcode]);
      return lookupAnswer();
    },
    payBill: (billNumber: string, body: GuestPayment) => {
      paid.push([billNumber, body]);
      return payAnswer();
    },
  };
});

const { QuickPayCheck } = await import("./QuickPayCheck");

const PAYABLE: BillLookupView = {
  number: "BL-2608-0141",
  amount: { kind: "amount", amount: "142.1800", display: "$142.18", currency: "USD" },
  status: "payable",
  due_on: "2026-09-14",
  masked_name: "M. A••••••",
  replaced_by: null,
};

const RECEIPT: GuestPaymentReceipt = {
  reference: "PAY-26-08841",
  amount: { kind: "amount", amount: "142.1800", display: "$142.18", currency: "USD" },
  paid_at: "2026-09-02T09:47:00+00:00",
  against: "BL-2608-0141",
  method: { brand: "visa", last_four: "8812" },
  receipt_sent: false,
};

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`DEF-CWP-3925`). A bare
 *  `MemoryRouter` leaves `useParams().tenant` undefined and every address the
 *  page builds comes out `//portal/…` — a protocol-relative URL to another
 *  host, which reads as a perfectly good string to `toContain`. */
let wentTo: string[] = [];
let handedOn: unknown = null;

function Landed() {
  const location = useLocation();
  wentTo.push(location.pathname);
  handedOn = location.state;
  return <p>landed</p>;
}

function draw(state: unknown = { billNumber: "BL-2608-0141", postcode: "78702" }) {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: "/pine-hill/portal/pay/check", state } as never]}
    >
      <Routes>
        <Route path="/:tenant/portal/pay/check" element={<QuickPayCheck />} />
        <Route path="/:tenant/portal/pay/done" element={<Landed />} />
        <Route path="/:tenant/portal/pay" element={<Landed />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** ⚠ **FIELDS ARE FOUND BY ID, NOT BY LABEL TEXT.** The labels come out of the
 *  eleven catalogues (B14 rule 35) and this lane hands its keys to the merge
 *  lane rather than editing a shared catalogue, so a label assertion here would
 *  be asserting a translation rather than a screen. */
async function fillCard(container: HTMLElement, number = "4111111111118812") {
  const user = userEvent.setup();
  await user.type(container.querySelector("#quickpay-card") as HTMLInputElement, number);
  await user.type(container.querySelector("#quickpay-expires") as HTMLInputElement, "11/27");
  await user.type(container.querySelector("#quickpay-security") as HTMLInputElement, "123");
}

function payButton(container: HTMLElement) {
  return container.querySelector("[data-pay-control] button") as HTMLButtonElement;
}

beforeEach(() => {
  lookedUp = [];
  paid = [];
  wentTo = [];
  handedOn = null;
  lookupAnswer = async () => PAYABLE;
  payAnswer = async () => RECEIPT;
});
afterEach(cleanup);

describe("CWP-003 · check and pay (US-CWP-004)", () => {
  it("RE-READS the amount on load rather than carrying step 1's answer", async () => {
    // `US-CWP-004` §7 — *"the amount owing at the moment of commit, re-read
    // rather than carried from step 1"*. What step 1 hands on is the PAIR, so
    // this screen asks again — which is also what puts it behind the SAME
    // five-tries lockout rather than beside it (`BR-CWP-023`).
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(lookedUp).toEqual([["BL-2608-0141", "78702"]]);
    const money = container.querySelector("[data-money]");
    expect(money?.textContent).toBe("$142.18");
    // Hard rule 2 — four stored beside two displayed, and the screen formats
    // neither.
    expect(money?.getAttribute("data-money")).toBe("142.1800");
  });

  it("renders the server's mask verbatim and the full name is nowhere on the page", async () => {
    // ⚠ `US-CWP-004` §5, verbatim: *"Masked server-side. Never send the full
    // name and mask in the browser."* The PAYLOAD assertion that makes this
    // real is `tests/test_us_cwp_004_pay.py` TC-1 — a browser that received the
    // full name has already been told it, whatever it draws.
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-masked-name]")).not.toBeNull());
    expect(container.querySelector("[data-masked-name]")?.textContent).toBe("M. A••••••");
    expect(container.innerHTML).not.toMatch(/alvarez/i);
    expect(container.innerHTML).not.toMatch(/maria/i);
  });

  it("draws no service address, because the server serves none (BR-CWP-021)", async () => {
    // The wireframe puts *Service address* in the KVList; `guest_fields.py`'s
    // `NEVER_ON_A_GUEST_RESPONSE` names `address` and `postal_code`, so there is
    // nothing to draw. The holder already typed the postcode; the street would
    // tell them something they had not.
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(container.querySelector('[data-kv="service-address"]')).toBeNull();
    expect(container.innerHTML).not.toMatch(/elm st/i);
  });

  it("BR-CWP-058 — the consequence box names the figure and the bill BEFORE the button", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-consequence]")).not.toBeNull());
    // ⚠ **ASSERTED ON THE WRAPPER, NOT ON THE SENTENCE.** The sentence is the
    // catalogue's (B14 rule 35), so reading the figure out of the rendered text
    // would be asserting a TRANSLATION — and would go quiet in ten languages the
    // day one of them was reworded.
    const box = container.querySelector("[data-pay-amount]");
    expect(box?.getAttribute("data-pay-amount")).toBe("$142.18");
    expect(box?.getAttribute("data-pay-against")).toBe("BL-2608-0141");
    // It is drawn ABOVE the button, which is what `BR-CWP-058` is asking for:
    // afterwards the payment row can only be reversed, never edited.
    const control = container.querySelector("[data-pay-control]") as HTMLElement;
    const position = (box as HTMLElement).compareDocumentPosition(control);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // ⚠ **NO FEE LINE.** `OQ-1394` is CLOSED (2026-09-04): absorbed or
    // surcharged, per tenant, and beta ships ABSORBED. A surcharge would have
    // to be computed, disclosed here before the button and checked against the
    // customer's state — so what this box promises is what the person pays.
    expect(container.querySelector("[data-consequence]")?.textContent).not.toMatch(
      /surcharge/i,
    );
  });

  it("TOKENISES the card — the number is never in what is posted (BR-CWP-057)", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("#quickpay-card")).not.toBeNull());
    await fillCard(container);
    await userEvent.setup().click(payButton(container));
    await waitFor(() => expect(paid).toHaveLength(1));

    const [billNumber, body] = paid[0];
    expect(billNumber).toBe("BL-2608-0141");
    // `US-CWP-004` §5 — *"Never stored. Posted to the gateway, which returns a
    // token."* The digits are reduced to a brand and a last four; the number
    // itself is not in the body, in any nested value, or in any type on the
    // wire.
    // ⚠ **ASSERTED ON THE INSTRUMENT, NOT ON THE WHOLE BODY** (`DEF-CWP-4033`).
    // `expect(JSON.stringify(body)).not.toContain("123")` reads like the
    // strongest possible check and is a FLAKY one on a money path: the body
    // carries `attempt_token`, which is a `crypto.randomUUID()`, and a random
    // UUID contains the substring `123` about seven runs in a thousand. It
    // failed exactly once in a 649-case run and passed five times out of five
    // when the file was re-run alone — which is how a check on the guest
    // PAYMENT path gets quietly muted as "that flaky one".
    //
    // The rule being asserted is `US-CWP-004` §5 — *"Never stored. Posted to
    // the gateway, which returns a token."* — and it is about the INSTRUMENT.
    // The card number and the security code must not be anywhere in it, and
    // the key set below already pins it to exactly the three tokenised fields.
    const instrument = JSON.stringify(body.instrument);
    expect(instrument).not.toContain("4111111111118812");
    expect(instrument).not.toContain("123");
    // …and the card number, which cannot occur by chance, is still checked
    // over the WHOLE body: sixteen digits are not a UUID collision.
    expect(JSON.stringify(body)).not.toContain("4111111111118812");
    expect(Object.keys(body.instrument).sort()).toEqual(["brand", "last_four", "token"]);
    expect(body.instrument.brand).toBe("visa");
    expect(body.instrument.last_four).toBe("8812");
    // The figure the person agreed to travels for the server to COMPARE, and
    // the postcode re-proves the pair against the same five-tries counter.
    expect(body.amount).toBe("142.1800");
    expect(body.postcode).toBe("78702");
    // Hard rule 6 — one token per visit, so a double press collapses to one
    // payment rather than taking the money twice.
    expect(body.attempt_token).toBeTruthy();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `DEF-CWP-3951` — the form no longer asks for something nothing can use
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-3951 — no receipt address is collected, and none is posted", async () => {
    // ⚠ **THE FIELD WAS ACCEPTED, VALIDATED AND DROPPED**, and every test
    // passed because every test asked whether the input was ACCEPTED and none
    // asked what became of it. `record_payment` does queue a receipt — to the
    // ACCOUNT's own contacts under the tenant's election, a different address
    // — and `BR-NOT-013` means nothing dispatches in this release at all.
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("#quickpay-card")).not.toBeNull());
    // The box is gone, not merely ignored: a disabled-looking input a person
    // can still type into is the same false promise with worse manners.
    expect(container.querySelector("#quickpay-email")).toBeNull();
    await fillCard(container);
    await userEvent.setup().click(payButton(container));
    await waitFor(() => expect(paid).toHaveLength(1));
    expect(paid[0][1].receipt_email).toBeNull();
  });

  it("DEF-CWP-3951 — it says so in one sentence rather than saying nothing", async () => {
    // B14 rule 33 — a refusal is five or six words. Silence would leave a
    // person wondering where their receipt goes.
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("#quickpay-card")).not.toBeNull());
    const held = container.querySelector("[data-receipt-email-held]");
    expect(held).toBeTruthy();
    expect(held?.textContent).toBe("Email receipts are not available yet.");
  });

  it("a paid receipt lands on CWP-004 at /pine-hill/portal/pay/done, carrying it", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("#quickpay-card")).not.toBeNull());
    await fillCard(container);
    await userEvent.setup().click(payButton(container));
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/pay/done"]));
    expect(handedOn).toEqual({ receipt: RECEIPT });
  });

  it("the Pay control refuses until the card boxes are filled in", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("#quickpay-card")).not.toBeNull());
    expect(payButton(container)).toBeDisabled();
    expect(paid).toHaveLength(0);
  });

  it("TC-4/TC-5 — a settled bill states it and offers no card form at all", async () => {
    lookupAnswer = async () => ({
      ...PAYABLE,
      status: "settled",
      amount: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
    });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-nothing-to-pay]")).not.toBeNull());
    expect(container.querySelector("#quickpay-card")).toBeNull();
    expect(container.querySelector("[data-pay-control]")).toBeNull();
  });

  it("TC-2/TC-3 — ONE refusal sentence, and the card form is not drawn over it", async () => {
    lookupAnswer = async () => {
      throw new Error("refused");
    };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-quick-pay-refused]")).not.toBeNull());
    expect(container.querySelectorAll("[data-quick-pay-refused]")).toHaveLength(1);
    expect(container.querySelector("#quickpay-card")).toBeNull();
  });

  it("arriving with no handoff offers the LIVE door back, by address", async () => {
    // A reload, a bookmark, a link somebody kept. ⚠ Not an error state and not
    // a held control (`DEF-CWP-3925`, the mirror of dead UI): one sentence and
    // a working way on.
    const { container } = draw(null);
    expect(container.querySelector("[data-no-handoff]")).not.toBeNull();
    expect(lookedUp).toHaveLength(0);
    const back = container.querySelector('[data-screen="CWP-003"] a') as HTMLAnchorElement;
    expect(back.getAttribute("href")).toBe("/pine-hill/portal/pay");
    await userEvent.setup().click(back);
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/pay"]));
  });

  /**
   * `CR-085` — **THE LAST SCREEN AT WHICH ANYTHING CAN BE CHANGED HAD NO WAY
   * TO CHANGE ANYTHING.**
   *
   * That sentence is the wireframe's own description of this screen, and its
   * frame draws the way back twice — `← Pay` at the head on a phone, and *Go
   * back and change something* under the Pay button on a desk. This screen had
   * neither: the stepper is a list of `<li>`s rather than links, and the only
   * door to `/pay` was inside the *arrived with nothing* branch. A visitor who
   * typed one digit of the bill number wrong reached step 2, read a masked name
   * that was not theirs, and had nowhere to go but the browser's own back
   * button.
   *
   * ⚠ **ASSERTED BY ADDRESS AND BY POSITION.** `toContain("/pay")` passes on
   * `//portal/pay` — another host — and a door that exists somewhere on the
   * page is not a door beside the button somebody is deciding not to press.
   */
  it("CR-085 — the way back to step 1 sits beside the Pay button", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-pay-control]")).not.toBeNull());
    const back = container.querySelector("[data-pay-again] a") as HTMLAnchorElement;
    expect(back).not.toBeNull();
    expect(back.getAttribute("href")).toBe("/pine-hill/portal/pay");
    await userEvent.setup().click(back);
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/pay"]));
  });

  it("B14 rule 31 — nothing on the screen is a database id", async () => {
    const { container } = draw();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(container.querySelector("[data-bill-number]")?.textContent).toBe("BL-2608-0141");
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });
});
