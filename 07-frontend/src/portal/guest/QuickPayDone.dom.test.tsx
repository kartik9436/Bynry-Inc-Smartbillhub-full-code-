// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-005 (EP-CWP-02) · Screen: CWP-004 · wireframes/CWP-004.png
// Rules:    BR-CWP-028 (every guest flow ends on a reference and offers to
//           send it) · BR-CWP-029 (enrolment attaches a password to a person
//           already on file) · BR-CWP-021 (never a person, never an internal) ·
//           B14 rule 31 (the reference is the HUMAN one, never a row id) ·
//           rule 36 (compose the kit)
// Cases:    TC-1 (the reference, the amount, the bill and the method) ·
//           TC-3 (the offer is a LINK and creates nothing) · TC-4 (it routes
//           to /pine-hill/portal/enrol — CWP-016, where the one-time code is
//           asked for) · TC-2 (an address given at step 2 becomes a FACT, not
//           a control) · the two held controls carry `data-held-for`, which is
//           the expiry test DEF-CWP-3925 asks for · a reload offers the live
//           door back BY ADDRESS · no uuid and no card number anywhere
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { GuestPaymentReceipt } from "../api/guestClient";
import { QuickPayDone } from "./QuickPayDone";

const RECEIPT: GuestPaymentReceipt = {
  reference: "PAY-26-08841",
  amount: { kind: "amount", amount: "142.1800", display: "$142.18", currency: "USD" },
  paid_at: "2026-09-02T09:47:00+00:00",
  against: "BL-2608-0141",
  method: { brand: "visa", last_four: "8812" },
  receipt_sent: false,
};

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`DEF-CWP-3925`) — a bare
 *  `MemoryRouter` leaves `useParams().tenant` undefined and every address the
 *  page builds comes out `//portal/…`, which reads as a perfectly good string
 *  to `toContain`. */
let wentTo: string[] = [];

function Landed() {
  wentTo.push(useLocation().pathname);
  return <p>landed</p>;
}

function draw(receipt: GuestPaymentReceipt | null = RECEIPT) {
  return render(
    <MemoryRouter
      initialEntries={[
        {
          pathname: "/pine-hill/portal/pay/done",
          state: receipt === null ? null : { receipt },
        } as never,
      ]}
    >
      <Routes>
        <Route path="/:tenant/portal/pay/done" element={<QuickPayDone />} />
        <Route path="/:tenant/portal/enrol" element={<Landed />} />
        <Route path="/:tenant/portal/pay" element={<Landed />} />
        {/* `CWP-012` — the door `US-CWP-005` TC-3 asks for, live since
            2026-09-05. Routed here so the assertion below can be made BY
            ADDRESS and then CLICKED, which is the only form of it that can
            tell a working link from a string (`DEF-CWP-3925`). */}
        <Route path="/:tenant/portal/track" element={<Landed />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  wentTo = [];
});
afterEach(cleanup);

describe("CWP-004 · paid (US-CWP-005)", () => {
  it("TC-1 — the reference, the amount, the bill it went against and the method", () => {
    const { container } = draw();
    expect(container.querySelector('[data-screen="CWP-004"]')).not.toBeNull();
    // B14 rule 31 — `PAY-26-08841`, the number somebody reads down a telephone.
    expect(container.querySelector("[data-reference]")?.textContent).toBe("PAY-26-08841");
    expect(container.querySelector("[data-against]")?.textContent).toBe("BL-2608-0141");
    expect(container.querySelector("[data-paid-at]")?.getAttribute("data-paid-at")).toBe(
      "2026-09-02T09:47:00+00:00",
    );
    // ⚠ **THE FIGURE IS READ OFF THE WRAPPER, NOT OUT OF THE SENTENCE.**
    // *$142.18 received, thank you* is the catalogue's (B14 rule 35), so
    // asserting through the title would be asserting a TRANSLATION.
    expect(
      container.querySelector("[data-receipt-amount]")?.getAttribute("data-receipt-amount"),
    ).toBe("$142.18");
    // `BR-CWP-057` — a brand and a last four, which is the whole of what a
    // person is shown about the instrument. The two FACTS are asserted here;
    // the sentence joining them is the catalogue's (B14 rule 35).
    const method = container.querySelector("[data-method]");
    expect(method?.getAttribute("data-method")).toBe("visa");
    expect(method?.getAttribute("data-last-four")).toBe("8812");
  });

  it("TC-3/TC-4 — the login is OFFERED as a link to /pine-hill/portal/enrol", async () => {
    // ⚠ *"It does not create the login silently"* (`US-CWP-005` §1) and it
    // *"does not skip the one-time code because a payment just succeeded"*
    // (TC-4). An ordinary link to `CWP-016` is what both of those mean: nothing
    // is created here, and the door asks for the code like it asks everybody.
    const { container } = draw();
    const offer = container.querySelector("[data-enrol-offer]") as HTMLElement;
    expect(offer).not.toBeNull();
    const link = offer.querySelector("a") as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/pine-hill/portal/enrol");
    await userEvent.setup().click(link);
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/enrol"]));
  });

  it("the offer is drawn whether or not a login exists, and says nothing about one", () => {
    // ⚠ A server flag saying *this account has no login yet* would answer a
    // question a neighbour holding the bill has no business asking
    // (`BR-CWP-021`), so nothing on the receipt carries one — the offer is
    // unconditional and `/enrol` protects itself.
    const { container } = draw();
    expect(container.querySelector("[data-enrol-offer]")).not.toBeNull();
    expect(JSON.stringify(RECEIPT)).not.toMatch(/enrol|credential|has_login/i);
  });

  it("TC-2 — the receipt is not withheld for want of an email address", () => {
    // *"The receipt is already downloadable without it."* Nothing on this
    // screen is conditional on an address: the reference is drawn either way.
    const { container } = draw({ ...RECEIPT, receipt_sent: false });
    expect(container.querySelector("[data-reference]")?.textContent).toBe("PAY-26-08841");
  });

  it("an address given at step 2 becomes a FACT, not a second control", () => {
    // A held button over a thing that has already happened is worse than no
    // button, so *email it to me* is replaced by the statement that it went —
    // and the address itself never comes back from the server (`US-CWP-004` §4,
    // *"a guest may be a neighbour"*).
    const { container } = draw({ ...RECEIPT, receipt_sent: true });
    expect(container.querySelector("[data-receipt-sent]")).not.toBeNull();
    expect(container.querySelector('[data-held-for="US-CWP-005-receipt-email"]')).toBeNull();
    expect(container.innerHTML).not.toMatch(/@/);
  });

  it("every held control names the thing that releases it (DEF-CWP-3925)", () => {
    // ⚠ **THIS IS THE EXPIRY TEST HARD-WON LAW 2 ASKS FOR, IN THE ONLY FORM
    // AVAILABLE TODAY.** Neither the receipt DOCUMENT (`US-CWP-005` TC-6, the
    // document class that already exists) nor a guest send has a route yet, so
    // there is no address to assert. What CAN be asserted is the name of the
    // work that lifts each hold: build either, take the attribute off, and this
    // case goes red and says which control it was — *a hold with no such test
    // is a promise nobody is keeping*.
    //
    // ⚠ **BOTH REASONS RE-CHECKED 2026-09-05 AND BOTH ARE STILL TRUE**, which
    // is the half of `DEF-CWP-3925` that costs nothing and is skipped anyway.
    // `guest_api.urlpatterns` serves eighteen public routes and NONE of them is
    // a receipt; `apps/portal/api.py` has `portal/bills/{number}/document.pdf`
    // for a BILL and no equivalent for a payment, authenticated or not; and
    // `payments/receipts.py` QUEUES `BR-PAY-024`'s document to be printed or
    // posted without publishing any door a stranger could open. A hold that is
    // honest is correct, so both stay — and the third door on this screen,
    // *look it up*, went LIVE the same day because its reason did expire.
    const { container } = draw({ ...RECEIPT, receipt_sent: false });
    const held = Array.from(container.querySelectorAll("[data-held-for]")).map((node) =>
      node.getAttribute("data-held-for"),
    );
    expect(held.sort()).toEqual([
      "US-CWP-005-receipt-document",
      "US-CWP-005-receipt-email",
    ]);
    // And each is a DISABLED control carrying its reason on the page — never
    // hidden and never live-but-inert (`BR-CWP-056`).
    for (const node of container.querySelectorAll("[data-held-for]")) {
      expect(node.querySelector("[data-held]")).not.toBeNull();
      expect(node.querySelector("button")).toBeDisabled();
    }
  });

  it("a reload with no receipt says so once and offers TWO live doors back", async () => {
    // `/pay/done` carries nothing in its address on purpose, so a refreshed tab
    // has no receipt to draw. Not an error state and not a shut door: one
    // sentence and a working way on, asserted BY ADDRESS.
    //
    // ⚠ **THE FIRST DOOR IS TC-3 AND IT WAS A STATED GAP UNTIL 2026-09-05.**
    // *"The receipt is still reachable by reference"* had no destination while
    // `selectors.TRACKABLE_SERIES` refused the `PAY-` series; it names the
    // payment now, so `/track` is a real page and this asserts it that way.
    const { container } = draw(null);
    expect(container.querySelector("[data-no-receipt]")).not.toBeNull();
    expect(container.querySelector("[data-reference]")).toBeNull();
    const doors = Array.from(
      container.querySelectorAll('[data-screen="CWP-004"] a'),
    ) as HTMLAnchorElement[];
    expect(doors.map((one) => one.getAttribute("href"))).toEqual([
      "/pine-hill/portal/track",
      "/pine-hill/portal/pay",
    ]);
    await userEvent.setup().click(doors[0]);
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/track"]));
  });

  it("and the door back to the bill still works (US-CWP-005 TC-3, the other half)", async () => {
    // Two doors answer two different people: somebody who KEPT the reference
    // tracks it, and somebody who lost it with the tab has only the paper.
    const { container } = draw(null);
    const doors = Array.from(
      container.querySelectorAll('[data-screen="CWP-004"] a'),
    ) as HTMLAnchorElement[];
    await userEvent.setup().click(doors[1]);
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/pay"]));
  });

  it("BR-CWP-021 · B14 rule 31 — no person, no uuid, no card number", () => {
    const { container } = draw();
    expect(container.innerHTML).not.toMatch(/alvarez|maria/i);
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
    // The gateway token is the rails' secret and a guest screen has no use for
    // it; the receipt carries a brand and a last four and nothing else.
    expect(container.innerHTML).not.toMatch(/sbx_|tok_/);
    // Six digits in a row would be four too many for a last four.
    expect(container.querySelector("[data-method]")?.textContent).not.toMatch(/\d{6}/);
  });

  it("the stepper says step three, not step two", () => {
    const { container } = draw();
    expect(container.querySelector("[data-stepper]")).not.toBeNull();
    expect(screen.getAllByText(/✓/).length).toBeGreaterThanOrEqual(2);
  });
});
