// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09) · Screen: CWP-038 · wireframes/CWP-038.png
// Rules:    BR-CWP-058 (where it will land, BEFORE it commits) · BR-CWP-056 /
//           CR-068 R3 (a control that may not be used is VISIBLE, DISABLED and
//           carries its reason) · BR-CWP-057 (a brand and four digits — the
//           token is never on the wire and never in the DOM) · B14 rule 20
//           (one table type) · rule 31 (no database id is a visible value) ·
//           rule 36 (compose the kit — no raw <button>) · CLAUDE.md hard rule 2
//           (2 dp displayed)
// Cases:    TC-1 (no provider → the Pay control is HELD, in place, with its
//           reason) · TC-4 (the panel reads $102.18 BEFORE the commit) ·
//           TC-5 (two bills, oldest first) · TC-6 (a timeout says so and offers
//           the retry) · TC-7 (the retry carries the key the preview minted —
//           read off the BODY that reaches the transport) · TC-9 (cash-only) ·
//           the confirmation's destination, ASSERTED BY ADDRESS
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THE COPY IS NOT ASSERTED AND THAT IS DELIBERATE.** This lane's eleven
// catalogues are merged by the parent lane (the locale files are one file each
// and four lanes are writing at once — hard-won law 11), so until they land
// `t()` answers the KEY. A query by accessible name would therefore be
// asserting the ABSENCE of a translation, and would have to be rewritten the
// day the words arrive. What is asserted instead is STRUCTURE, FIGURES,
// REFUSAL CODES and ADDRESSES — the four things a catalogue merge cannot
// silently change. The one exception is a saved method, whose label is SERVER
// data (`Chase ••••4021`) and is stable either way.
//
// ⚠ **AND THE ADDRESS ASSERTION IS THE POINT OF MOUNTING IT ROUTED**
// (`DEF-CWP-3925`). `usePortalPath` reads the tenant off the address the
// browser is on, so a `MemoryRouter` with `initialEntries` and **no matching
// `<Route>`** binds no params at all and every href comes out `//portal/…` — a
// protocol-relative URL to another host, which reads as a perfectly good string
// to `toContain`. Declaring the route is what makes the href assertion below
// able to fail.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalPayNow, PortalPayPreview, PortalPayResult } from "../api/payNowClient";

// Plain functions rather than `vi.fn()` — a recording stand-in reaches a
// rejected promise before the screen's own `catch` does (the reasoning
// `MyDetails.dom.test.tsx` records two directories over).
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

const { PayNowView } = await import("./PayNow");

const MINTED = "pay_26_08841";

const AUGUST_BILL = {
  invoice_id: "d4f0-not-shown",
  number: "BL-2608-0141",
  issued_on: "2026-08-26",
  total: "142.1800",
  amount_due: "142.1800",
  allocated: "0.0000",
  open_balance: "142.1800",
  currency: "USD",
};

const JULY_BILL = {
  ...AUGUST_BILL,
  invoice_id: "aa11-not-shown",
  number: "BL-2607-0139",
  issued_on: "2026-07-26",
  total: "18.0000",
  amount_due: "18.0000",
  open_balance: "18.0000",
};

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

const EXPIRED = {
  ...CHASE,
  id: "77aa-not-shown",
  label: "Visa ••••4417",
  brand: "Visa",
  last_four: "4417",
  kind: "card" as const,
  status: "expired",
  selectable: false,
  held_reason: "card_has_expired",
};

const PAYABLE: PortalPayNow = {
  account_no: "A-10432",
  balance: "142.1800",
  currency: "USD",
  bills: [AUGUST_BILL],
  bill_count: 1,
  instruments: [CHASE],
  can_pay: true,
  held_reason: null,
  order: "oldest_first",
  environment: "sandbox",
  problems: [],
};

/** The `$40.00` panel — `$142.18` becomes `$102.18`, and the SERVER says so. */
const PARTIAL: PortalPayPreview = {
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
  lands_on: PARTIAL.lands_on,
  idempotency_key: MINTED,
  environment: "sandbox",
  problems: [],
};

/**
 * Where step one hands the customer, and WHAT IT HANDS THEM WITH.
 *
 * ⚠ **THE HANDOFF IS ROUTER STATE, SO IT CANNOT BE READ OFF AN ADDRESS** —
 * which is the point of it (an amount and an instrument id in a URL end up in
 * access logs, in history and in a `Referer` header). A probe at the
 * destination is therefore the only way to assert it, and asserting it is the
 * only way a test can fail the day somebody re-mints the idempotency key at the
 * step boundary.
 */
function Landed() {
  const location = useLocation();
  return <div data-landed-check={JSON.stringify(location.state)} />;
}

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/pay-now"]}>
      <Routes>
        <Route path="/:tenant/portal/pay-now" element={<PayNowView accountId="acc-1" />} />
        <Route path="/:tenant/portal/pay-now/check" element={<Landed />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  sent = [];
  readScreen = async () => PAYABLE;
  readPreview = async () => PARTIAL;
  doPay = async () => PAID;
});
afterEach(cleanup);

/**
 * Type an amount. **The panel prices itself** (`DEF-CWP-3970`).
 *
 * ⚠ **THERE IS NO CONTROL TO PRESS ANY MORE, AND ITS ABSENCE IS THE FIX.**
 * This helper used to end with a click on `[data-see]` — *Show me where it
 * goes* — a control of our own invention that the wireframe does not have and
 * that held the Pay button behind it. `WHERE IT WILL GO` is a STANDING panel,
 * so a preview follows the amount and nothing has to be pressed to see it.
 *
 * ⚠ **EVERY CONTROL IS FOUND BY A `data-` HOOK OR AN `id`, NEVER BY ITS LABEL.**
 * See the file header for why.
 */
async function priceIt(container: HTMLElement, amount = "40") {
  const user = userEvent.setup();
  await user.click(container.querySelector('[data-radio="another"] input') as HTMLElement);
  await user.type(container.querySelector("#pay-amount") as HTMLElement, amount);
  await waitFor(() => expect(container.querySelector("[data-after='0']")).not.toBeNull());
}

/** The Pay control, however it is drawn — disabled with its reason, or live. */
function payControl(container: HTMLElement): HTMLButtonElement {
  return container.querySelector("[data-pay-control] button") as HTMLButtonElement;
}

describe("CWP-038 · pay now (US-CWP-045)", () => {
  it("draws the three steps, the amounts and the saved method before anything is typed", async () => {
    const { container } = draw();
    expect(await screen.findByTestId("pay-now")).toBeInTheDocument();
    expect(container.querySelector('[data-screen="CWP-038"]')).not.toBeNull();
    expect(container.querySelector("[data-stepper]")).not.toBeNull();
    // ⚠ **B14 RULE 31, READ AS IT IS WRITTEN: no database id is ever the
    // VISIBLE VALUE of a field.** So this asserts the rendered TEXT and not the
    // markup. A radio's `value` and a `data-` hook legitimately carry the id —
    // that is how the choice travels back, exactly as `open_bill_position`
    // serves `invoice_id` beside the `number` a person reads — and an assertion
    // over `innerHTML` would forbid the mechanism rather than the mistake.
    expect(container.textContent ?? "").not.toContain("not-shown");
    // The label a person actually reads is the brand and four digits.
    expect(container.textContent ?? "").toContain("Chase ••••4021");
    // `BR-CWP-057` — a brand and four digits, and no token anywhere.
    expect(screen.getByText(/Chase ••••4021/)).toBeInTheDocument();
  });

  it("TC-4 · the panel reads $102.18 BEFORE anything commits", async () => {
    const { container } = draw();
    await screen.findByTestId("pay-now");
    await priceIt(container);

    // ⚠ **THE ASSERTION THE WHOLE SCREEN EXISTS FOR** (`BR-CWP-058`). The
    // figure is on screen and NOTHING has been paid — `sent` proves it: one
    // preview, no commit.
    await waitFor(() =>
      expect(container.querySelector("[data-after='0']")?.textContent).toBe("$102.18"),
    );
    expect(container.querySelector("[data-bill='0']")?.textContent).toBe("BL-2608-0141");
    expect(container.querySelector("[data-paying='0']")?.textContent).toBe("$40.00");
    // ⚠ **NOTHING WAS PAID** — which is the assertion, and it is now made
    // directly rather than through a preview COUNT. The count moved when the
    // panel started standing: opening the screen prices *Everything you owe*
    // before a key is pressed, so there is more than one preview and never a
    // commit.
    expect(sent.some((one) => one[0] === "pay")).toBe(false);
    expect(sent.every((one) => one[0] === "preview")).toBe(true);
  });

  it("TC-5 · two open bills land oldest first, in the server's order", async () => {
    readScreen = async () => ({ ...PAYABLE, bills: [JULY_BILL, AUGUST_BILL], bill_count: 2 });
    readPreview = async () => ({
      ...PARTIAL,
      lands_on: [
        { number: "BL-2607-0139", owing: "18.0000", paying: "18.0000", owing_after: "0.0000" },
        { number: "BL-2608-0141", owing: "142.1800", paying: "22.0000", owing_after: "120.1800" },
      ],
    });
    const { container } = draw();
    await screen.findByTestId("pay-now");
    await priceIt(container);

    await waitFor(() =>
      expect(container.querySelector("[data-bill='0']")?.textContent).toBe("BL-2607-0139"),
    );
    expect(container.querySelector("[data-bill='1']")?.textContent).toBe("BL-2608-0141");
    expect(container.querySelector("[data-after='1']")?.textContent).toBe("$120.18");
    // ⚠ THE FOOTER NAMES THE TENANT'S RULE, READ FROM THE SERVER. A sentence
    // typed into this file would go on saying *oldest first* on the day a
    // utility configured something else.
    expect(container.querySelector("[data-order='oldest_first']")).not.toBeNull();
  });

  /**
   * ⚠ **TC-7 LIVES ON `CWP-076` NOW, AND HALF OF IT LIVES HERE.**
   *
   * The commit moved to the screen the PO's ruling created (*"it should be 3
   * screens - confirmed"*), so the assertion that the commit carries the
   * PREVIEW's key is in `PayNowCheck.dom.test.tsx`. What this screen still owes
   * the contract is that it HANDS THAT KEY ON rather than dropping it — a
   * screen that handed on only the amount would look perfectly correct here and
   * would make step two mint a fresh key, which is idempotency that reads
   * correctly and protects nothing.
   */
  it("TC-7 (first half) · hands on the amount, the instrument and the key the PREVIEW minted", async () => {
    const user = userEvent.setup();
    const { container } = draw();
    await screen.findByTestId("pay-now");
    await priceIt(container);
    await waitFor(() => expect(container.querySelector("[data-after='0']")).not.toBeNull());
    await user.click(payControl(container));

    const landed = await waitFor(() => {
      const probe = container.querySelector("[data-landed-check]");
      expect(probe).not.toBeNull();
      return probe as HTMLElement;
    });
    expect(JSON.parse(landed.getAttribute("data-landed-check") ?? "null")).toEqual({
      amount: "40",
      instrumentId: CHASE.id,
      idempotencyKey: MINTED,
    });
    // ⚠ **AND NOTHING WAS PAID FROM THIS SCREEN.** The commit is not here any
    // more, and this is the assertion that fails the day somebody puts it back.
    expect(sent.some((one) => one[0] === "pay")).toBe(false);
  });

  /**
   * ⚠ **`DEF-CWP-4869` — THE COMMIT STAYED LIVE WHILE THE PANEL DESCRIBED
   * ANOTHER PAYMENT.**
   *
   * Typing into *Another amount* changed the button label immediately — it is
   * computed locally — while `panel` kept the PREVIOUS preview for at least
   * `PRICE_AFTER_MS` plus a round trip, and `ready` stayed true across that
   * window. Observed on screen simultaneously on 2026-09-11: button
   * `Pay $40.00 ✓` over *"Takes $191.00 … Clears bill BL-2608-0141 in full"*
   * and a rail reading `PAYING $191.00`. **And the control carried the previous
   * amount's idempotency key**, which is the one string hard rule 6 makes
   * load-bearing.
   */
  it("DEF-CWP-4869 · a changed amount clears the priced panel and holds the control", async () => {
    const user = userEvent.setup();
    const { container } = draw();
    await screen.findByTestId("pay-now");

    // ⚠ **THE AMOUNT MUST GO FROM ONE PRICEABLE FIGURE TO ANOTHER WITHOUT
    // PASSING THROUGH NOTHING, OR THIS CASE CANNOT SEE THE DEFECT.** The first
    // draft clicked *Another amount* (an empty box, so `priceable` is false)
    // and typed — and the OLD code cleared the panel on that empty step all by
    // itself, so the case passed against the bug. It was written, mutated and
    // caught (hard-won law 7: *ask what would make this check pass wrongly*).
    // `$40.00` → `$400.00` never stops being priceable, and that is the window
    // the customer actually stood in.
    await user.click(container.querySelector('[data-radio="another"] input') as HTMLElement);
    await user.type(container.querySelector("#pay-amount") as HTMLElement, "40");
    await waitFor(() =>
      expect(container.querySelector("[data-paying='0']")?.textContent).toBe("$40.00"),
    );

    // A preview that never answers: the window this defect lives in, held open.
    let answer: (value: PortalPayPreview) => void = () => undefined;
    readPreview = () =>
      new Promise<PortalPayPreview>((resolve) => {
        answer = resolve;
      });
    await user.type(container.querySelector("#pay-amount") as HTMLElement, "0");

    // ⚠ **THE STALE PANEL IS GONE BEFORE THE NEW ONE ARRIVES.** Observed on
    // screen on 2026-09-11: a button reading `Pay $40.00 ✓` over *"Takes
    // $191.00 … Clears bill BL-2608-0141 in full"* and a rail reading `PAYING
    // $191.00` — three figures, two payments, one screen.
    await waitFor(() => expect(container.querySelector("[data-paying='0']")).toBeNull());
    expect(container.querySelector("[data-consequence]")).toBeNull();
    // ⚠ **AND THE CONTROL CANNOT BE PRESSED OVER A FIGURE NOBODY HAS PRICED**,
    // which is the half that carried the PREVIOUS amount's idempotency key —
    // the one string hard rule 6 makes load-bearing.
    expect(payControl(container)).toBeDisabled();

    // ⚠ **WAIT FOR THE REQUEST, NOT FOR A CLOCK.** The re-price is debounced by
    // `PRICE_AFTER_MS`, so resolving before it has been ASKED resolves a
    // promise nothing is listening to — and the test then fails for a reason
    // that has nothing to do with the defect.
    await waitFor(() =>
      expect(sent.some((one) => one[0] === "preview" && one[1].amount === "400")).toBe(true),
    );
    answer({ ...PARTIAL, amount: "400.0000" });
    await waitFor(() => expect(payControl(container)).toBeEnabled());
  });

  it("TC-1 · with no provider connected the Pay control is VISIBLE, DISABLED and says why", async () => {
    readScreen = async () => ({
      ...PAYABLE,
      can_pay: false,
      held_reason: "no_payment_provider_connected",
      environment: null,
    });
    const { container } = draw();
    await screen.findByTestId("pay-now");

    // ⚠ **NEVER HIDDEN AND NEVER LIVE-BUT-INERT** (`BR-CWP-056` / `CR-068` R3).
    // It is in its normal place, it cannot be pressed, and the reason is ON it.
    const pay = payControl(container);
    expect(pay).toBeInTheDocument();
    expect(pay).toBeDisabled();
    expect(pay).toHaveAttribute("title");
    expect(pay.getAttribute("title")).not.toBe("");
  });

  it("TC-9 · a cash-only account is refused with its reason, not with a dead control", async () => {
    readScreen = async () => ({
      ...PAYABLE,
      can_pay: false,
      held_reason: "account_is_cash_only",
    });
    const { container } = draw();
    await screen.findByTestId("pay-now");
    const pay = payControl(container);
    expect(pay).toBeDisabled();
    // ⚠ THE REASON ARRIVES AS A CODE AND THE CATALOGUES WRITE THE WORDS.
    // Asserting the CODE is what survives the merge that brings them.
    expect(pay.getAttribute("title")).toContain("This account is cash only.");
  });

  it("an expired card is listed, cannot be chosen, and carries its reason", async () => {
    readScreen = async () => ({ ...PAYABLE, instruments: [CHASE, EXPIRED] });
    const { container } = draw();
    await screen.findByTestId("pay-now");

    // One radio, not two: the expired card is present and unselectable.
    expect(screen.getAllByRole("radio", { name: /••••/ })).toHaveLength(1);
    expect(container.querySelector(`[data-method-held="${EXPIRED.id}"]`)).not.toBeNull();
  });

  it("a sandbox connection says so on the screen, because no real money moved", async () => {
    const { container } = draw();
    await screen.findByTestId("pay-now");
    await priceIt(container);
    await waitFor(() => expect(container.querySelector("[data-sandbox]")).not.toBeNull());
  });

  /**
   * `DEF-CWP-<pay-now-zero>` — **a customer who owes nothing is an ordinary
   * customer**, and they are exactly the person who opens Pay now to check.
   * `Everything you owe · $0.00` is pre-selected, so they choose nothing, press
   * *Show me where it goes*, and until 2026-09-05 the page did not change: no
   * panel, no message, no spinner, and a `422` swallowed as an unhandled
   * rejection that fails no assertion in vitest and changes nothing in a
   * screenshot.
   */
  describe("DEF-CWP-<pay-now-zero> · nothing owing", () => {
    beforeEach(() => {
      readScreen = async () => ({ ...PAYABLE, balance: "0.0000", bills: [], bill_count: 0 });
      readPreview = async () => {
        // What the server really answers: VAL-003, `amount must be positive`.
        throw new Error("VAL-003");
      };
    });

    it("asks the server nothing and draws no panel, rather than doing nothing visible", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");

      // ⚠ **THE REFUSAL IS LOCAL.** `$0.00` cannot be priced, so no preview is
      // sent — the server's own `422 VAL-003` is never provoked and never has
      // to be explained. This is the assertion that fails the day the standing
      // preview stops checking the amount before it fires.
      await waitFor(() => expect(container.querySelector("[data-methods]")).not.toBeNull());
      expect(sent).toEqual([]);
      expect(container.querySelector("[data-minitable]")).toBeNull();
      expect(container.querySelector("[data-consequence]")).toBeNull();
    });

    it("holds the Pay control for the SAME reason, not for a preview nobody can ask for", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");
      const pay = payControl(container);
      expect(pay).toBeDisabled();
      // ⚠ **THE WORDS, AND THIS ONE IS THE EXCEPTION THE FILE HEADER ALLOWS
      // FOR.** `portal.payNow.amountMustBePositive` is in all eleven
      // catalogues, so `t()` answers the sentence and not the key.
      // *"Choose an amount first."* would be a LIE to someone whose only
      // choice is `$0.00` and who has already chosen it; five words, B14
      // rule 33, and no rule id (rule 32). And *"See where it goes first."* —
      // the old `heldNoPreview` — would have sent them to a control this
      // screen no longer has (`DEF-CWP-3970`).
      expect(pay.getAttribute("title")).toBe("Enter an amount above zero.");
    });

    it("a preview the server refuses is DRAWN, and the screen survives it", async () => {
      // A payable balance, and a preview that refuses anyway — the general
      // case the missing `try` swallowed, of which `$0.00` was one instance.
      readScreen = async () => PAYABLE;
      const { container } = draw();
      await screen.findByTestId("pay-now");
      // ⚠ **NOTHING IS TYPED AND NOTHING IS PRESSED.** The standing preview
      // fires on open, so the refused case is reachable without a click — and
      // `priceIt` cannot be used here, because it waits for a panel this
      // preview will never produce.

      // The customer is TOLD, and their amount, method and radios are still
      // where they left them — `pay-now`, not `pay-now-failed`.
      await waitFor(() =>
        expect(container.querySelector("[data-see-refused]")).not.toBeNull(),
      );
      expect(screen.queryByTestId("pay-now-failed")).toBeNull();
      expect(screen.getByTestId("pay-now")).toBeInTheDocument();
      expect(container.querySelector("[data-minitable]")).toBeNull();
    });
  });

  /**
   * `DEF-CWP-3970` — **the panel is a standing right-rail panel, not a gate.**
   *
   * The screen used to carry *Show me where it goes*, a control of our own
   * invention, and held the Pay button behind it with *"See where it goes
   * first."* The wireframe (`P24`) draws `WHERE IT WILL GO` visible from the
   * moment the screen opens, and its own design note says why: payments are
   * allocated by a rule the utility configures, so a person paying part of a
   * balance must see which bill it lands on BEFORE they commit — afterwards the
   * payment cannot be edited, only reversed (hard rule 4).
   */
  it("DEF-CWP-3970 · the panel is on screen before anything is pressed, and the gate is gone", async () => {
    const { container } = draw();
    await screen.findByTestId("pay-now");

    // ⚠ **NOBODY CLICKED ANYTHING.** `draw()` mounts and this is the next line.
    await waitFor(() =>
      expect(container.querySelector("[data-after='0']")?.textContent).toBe("$102.18"),
    );
    expect(container.querySelector("[data-bill='0']")?.textContent).toBe("BL-2608-0141");

    // ⚠ **AND THE INVENTED CONTROL IS GONE, ASSERTED BY ITS ABSENCE.** A test
    // that only checked the panel appears would go on passing the day somebody
    // re-added a button in front of it.
    expect(container.querySelector("[data-see]")).toBeNull();
    expect(container.querySelector("[data-see-control]")).toBeNull();
    // Its refusal is gone from the Pay control too: with a method chosen and a
    // priced amount there is nothing left to be held for.
    expect(payControl(container)).toBeEnabled();
  });

  /**
   * `DEF-CWP-3971` — **"Takes $155.45 from ."**
   *
   * `portal.payNow.consequence.takes` is *"Takes {{amount}} from {{method}}."*
   * and the bullet was written whether or not a method had been chosen, so the
   * interpolation was empty and the sentence on the panel that tells a customer
   * what is about to happen to their money ended on a bare full stop.
   *
   * ⚠ **THE ASSERTION IS THE WHOLE SENTENCE, NOT A FRAGMENT OF IT.** A
   * `toContain("Takes")` passes on the broken string, which is exactly how this
   * reached a browser with a green suite behind it.
   */
  describe("DEF-CWP-3971 · the consequence sentence names a method or is not written", () => {
    it("names the method in full when one is chosen", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");
      await waitFor(() => expect(container.querySelector("[data-consequence]")).not.toBeNull());

      expect(container.querySelector("[data-bullet='0']")?.textContent).toBe(
        "Takes $40.00 from Chase \u2022\u2022\u2022\u20224021.",
      );
    });

    it("writes no *takes* bullet at all when no method is chosen", async () => {
      // The customer with nothing saved: the third radio is selected, and it is
      // a destination rather than a way to pay.
      readScreen = async () => ({ ...PAYABLE, instruments: [] });
      const { container } = draw();
      await screen.findByTestId("pay-now");
      await waitFor(() => expect(container.querySelector("[data-consequence]")).not.toBeNull());

      const bullets = Array.from(container.querySelectorAll("[data-bullet]")).map(
        (one) => one.textContent ?? "",
      );
      // ⚠ **NOT ONE SENTENCE ENDS ON A BARE FULL STOP, AND NONE OF THEM IS THE
      // *takes* SENTENCE.** Both halves matter: the first is the symptom the PO
      // read on the screen, the second is the rule.
      expect(bullets.some((one) => one.startsWith("Takes "))).toBe(false);
      expect(bullets.some((one) => /\sfrom\s*\.$/.test(one))).toBe(false);
      expect(bullets.length).toBeGreaterThan(0);
    });
  });

  /**
   * `DEF-CWP-3972` — **a customer with no saved card could not pay, and the
   * screen told them to do the one thing it would not let them do.**
   *
   * `Methods()` rendered only saved instruments; with none it rendered the
   * stated absence and stopped. The wireframe's third radio was missing and the
   * Pay button was held with *"Add a card or bank account."* — with no control
   * on the screen that added one. Both halves were individually correct, which
   * is why nothing caught it: no rule asks whether the action a refusal
   * INSTRUCTS is reachable from where the person is standing.
   */
  describe("DEF-CWP-3972 · a customer with nothing saved can get somewhere", () => {
    beforeEach(() => {
      readScreen = async () => ({ ...PAYABLE, instruments: [] });
    });

    it("offers the wireframe's third radio and selects it, because it is the only one", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");

      const third = container.querySelector(
        '[data-radio="_different"] input',
      ) as HTMLInputElement;
      expect(third).not.toBeNull();
      expect(third.checked).toBe(true);
    });

    it("carries the door the refusal names, ASSERTED BY ADDRESS", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");

      // ⚠ **BY ADDRESS AND NOT BY PRESENCE** (`DEF-CWP-3925`). Mounted bare
      // this would read `//portal/payment-methods` — another host — and
      // `toContain("/payment-methods")` would call it a perfectly good string.
      const door = container.querySelector("[data-add-a-method] a") as HTMLAnchorElement;
      expect(door).not.toBeNull();
      expect(door).toHaveAttribute("href", "/pine-hill/portal/payment-methods");
    });

    it("holds Pay with a reason that is now TRUE, rather than one nothing can satisfy", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");

      const pay = payControl(container);
      expect(pay).toBeDisabled();
      // Six words, B14 rule 33 — and the screen it instructs is one link away.
      expect(pay.getAttribute("title")).toBe("Add a card or bank account.");
    });

    it("still names what would fill the empty list, above the radio rather than instead of it", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");
      // B14 rule 17 is kept: the sentence is a lead-in now, not the whole
      // section. It was the whole section, and that is what made it a dead end.
      expect(container.querySelector("[data-methods-empty]")).not.toBeNull();
      expect(container.querySelector("[data-methods]")).not.toBeNull();
    });
  });

  /**
   * Delta row 38.5 — **the button row is at the bottom left of the card.** It
   * floated outside the card, top right, and there was no `Back` at all.
   */
  it("draws Back and Pay together, inside the card — Back LEFT, Pay RIGHT (DEF-CWP-9164)", async () => {
    const { container } = draw();
    await screen.findByTestId("pay-now");

    const card = container.querySelector('[data-testid="pay-now"]') as HTMLElement;
    await waitFor(() => expect(card.querySelector("[data-consequence]")).not.toBeNull());
    expect(card.querySelector("[data-pay-control]")).not.toBeNull();
    expect(card.querySelector("[data-back]")).not.toBeNull();
    // ⚠ **INSIDE THE CARD, ASSERTED BY CONTAINMENT.** A test that only asked
    // *does a Back button exist* would pass with it back in the rail.
    expect(card.contains(container.querySelector("[data-consequence]"))).toBe(true);

    // ⚠ **THIS ASSERTED PAY FIRST UNTIL 2026-10-02.** The PO ruled the order
    // for every portal form that day — Back on the LEFT, the commit on the
    // RIGHT (`DEF-CWP-9164`, decision log *"PORTAL START-SERVICE FORM — FIVE
    // DEFECTS"*) — and `WizardFooter` is the one place it lives.
    const inOrder = Array.from(card.querySelectorAll("[data-pay-control], [data-back]"));
    expect(inOrder[0]?.getAttribute("data-back")).toBe("");
    expect(inOrder[1]?.getAttribute("data-pay-control")).toBe("");
    expect(inOrder[0]?.closest("[data-footer-side]")?.getAttribute("data-footer-side")).toBe("back");
    expect(inOrder[1]?.closest("[data-footer-side]")?.getAttribute("data-footer-side")).toBe("forward");
  });

  it("a read that fails says so and draws no amounts", async () => {
    readScreen = async () => {
      throw new Error("nope");
    };
    const { container } = draw();
    // ⚠ ITS OWN TEST ID. A failed read and a loading read are two different
    // screens, and a query that could not tell them apart would pass over
    // either.
    expect(await screen.findByTestId("pay-now-failed")).toBeInTheDocument();
    expect(container.querySelector("[data-stepper]")).toBeNull();
    expect(container.querySelector("[data-minitable]")).toBeNull();
    expect(container.querySelector("[data-pay-control]")).toBeNull();
  });

  /**
   * `DEF-CWP-4866` — **a refusal that only a mouse could read.**
   *
   * `CommitButton` renders its reason on `title=` and nowhere else. Measured in
   * a browser on 2026-09-11 at 390 and at 1280: `aria-label` null,
   * `aria-describedby` null, and the sentence **nowhere in the page text**. A
   * tooltip needs a mouse and a second of hover, so on the phone the PO named
   * as the primary case the reason a payment button will not work did not
   * exist. `HeldButton`, in the same kit file, has rendered exactly this kind
   * of sentence visibly all along — one screen said *We cannot draft payments
   * yet* out loud while the screen that takes the money said nothing.
   *
   * ⚠ **THE ASSERTION IS `textContent`, NOT AN ATTRIBUTE**, because an
   * attribute is what the old behaviour already satisfied. This is the test
   * that could not pass before the fix.
   */
  describe("DEF-CWP-4866 · a held commit says why, in the page text", () => {
    it("puts the server's reason in the TEXT and not only on title", async () => {
      readScreen = async () => ({
        ...PAYABLE,
        can_pay: false,
        held_reason: "no_payment_provider_connected",
      });
      const { container } = draw();
      await screen.findByTestId("pay-now");

      const pay = payControl(container);
      expect(pay).toBeDisabled();
      expect(pay.getAttribute("title")).toBe("We cannot take card payments yet.");
      // The half a phone can read.
      expect(container.querySelector("[data-commit-reason]")?.textContent).toBe(
        "We cannot take card payments yet.",
      );
      expect(container.textContent ?? "").toContain("We cannot take card payments yet.");
    });

    it("says nothing at all once the control is live", async () => {
      const { container } = draw();
      await screen.findByTestId("pay-now");
      await waitFor(() => expect(payControl(container)).toBeEnabled());
      // A standing sentence under a working button is noise, and B14 rule 32
      // budgets every one of them.
      expect(container.querySelector("[data-commit-reason]")).toBeNull();
    });
  });

  /**
   * `DEF-CWP-4867` — **`WHAT THIS WILL DO` promised the payment over a dead
   * button.**
   *
   * The box was drawn on `panel !== null` alone and never asked whether the
   * payment could happen, so an account with no provider connected read *"Takes
   * $40.00 from Chase ••••4021. Clears bill BL-2608-0141 in full. Emails you a
   * receipt."* over a control that could not be pressed and — until
   * `DEF-CWP-4866` — gave no reason. A confident promise, a dead button and no
   * explanation is the worst of the three possible screens.
   */
  it("DEF-CWP-4867 · no consequence is promised over a commit that cannot run", async () => {
    readScreen = async () => ({
      ...PAYABLE,
      can_pay: false,
      held_reason: "account_is_cash_only",
    });
    const { container } = draw();
    await screen.findByTestId("pay-now");
    // The PANEL still draws — `BR-CWP-058` is about telling somebody where
    // their money would go, and that is true whether or not we can take it.
    await waitFor(() => expect(container.querySelector("[data-after='0']")).not.toBeNull());
    // The PROMISE does not.
    expect(container.querySelector("[data-consequence]")).toBeNull();
  });
});
