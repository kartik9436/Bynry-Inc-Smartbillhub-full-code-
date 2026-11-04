// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-056 (EP-CWP-10) · Screen: CWP-045
// Rules:    BR-CWP-047 (the credit is re-read every load, never cached) ·
//           BR-CWP-060 (the refund names the method it is going back to) ·
//           BR-CWP-093 · B14 rule 31 · CLAUDE.md hard rule 2
// Cases:    four dated steps · two credits naming their bill · ⚠ the sign the
//           server sent · the separating sentence · a voided refund is listed
//           and its reason is not · neither credits nor refunds draws one line
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalCredit, PortalRefund } from "../api/portalClient";

type Body = { any: boolean; refunds: PortalRefund[]; credits: PortalCredit[] };

let readMoneyBack: () => Promise<Body> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getMoneyBack: () => readMoneyBack() };
});

const { MoneyBackView } = await import("./MoneyBack");

/** `US-CWP-056` §4 — an `$89.80` refund sent by cheque `10241`, and two credits
 *  of `$25.88` used on `BL-2607-0139`. ⚠ **The credits arrive NEGATIVE.** */
const REFUND: PortalRefund = {
  amount: "89.8000",
  currency: "USD",
  status: "issued",
  method: "check",
  reference: "10241",
  reason: "final bill overpayment",
  requested_at: "2026-09-18T09:00:00Z",
  approved_at: "2026-09-19T09:00:00Z",
  issued_at: "2026-09-21T09:00:00Z",
  cleared_at: null,
  voided_at: null,
  steps: [
    { step: "requested", on: "2026-09-18T09:00:00Z" },
    { step: "approved", on: "2026-09-19T09:00:00Z" },
    { step: "issued", on: "2026-09-21T09:00:00Z" },
    { step: "cleared", on: null },
  ],
};

const CREDITS: PortalCredit[] = [
  {
    reason: "goodwill after a reading dispute", credit_note_no: "CN-26-0001",
    issued_on: "2026-07-12", amount: "-25.8800", currency: "USD",
    used_on_bill: "BL-2607-0139",
  },
  {
    reason: "overcharge corrected", credit_note_no: "CN-26-0002",
    issued_on: "2026-07-12", amount: "-25.8800", currency: "USD",
    used_on_bill: "BL-2607-0139",
  },
];

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** — see `HelpPaying.dom.test.tsx`
 *  for what a bare `MemoryRouter` costs: `useParams().tenant` is undefined and
 *  every address the screen builds comes out `//portal/…`, another host, which
 *  every assertion we own accepts (`BR-CWP-007`, hard-won law 2). */
function draw(body: Body) {
  readMoneyBack = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/money-back"]}>
      <Routes>
        <Route path="/:tenant/portal/money-back" element={<MoneyBackView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-045 · credits and refunds (US-CWP-056)", () => {
  it("TC-1 — the refund's four steps, with the one that has not happened marked", async () => {
    const { container } = draw({ any: true, refunds: [REFUND], credits: CREDITS });
    await screen.findByText("A refund on its way");
    const steps = container.querySelectorAll("[data-timeline-step]");
    expect(steps).toHaveLength(4);
    expect(container.textContent).toContain("2026-09-18");
    expect(container.textContent).toContain("2026-09-21");
    // ⚠ *Cleared* has NOT happened — an absence in words, not a date.
    expect(steps[3]?.getAttribute("data-timeline-step")).toBe("future");
    expect(container.textContent).toContain("not yet");
    expect(container.querySelector("[data-clearing-note]")?.textContent).toContain(
      "ten working days",
    );
  });

  it("TC-8 — the refund names the method it is going back to", async () => {
    const { container } = draw({ any: true, refunds: [REFUND], credits: [] });
    await screen.findByText("A refund on its way");
    expect(container.querySelector("[data-refund-method='check']")?.textContent).toContain(
      "check 10241",
    );
  });

  it("TC-2 — two credits, each naming the bill it came off", async () => {
    const { container } = draw({ any: true, refunds: [], credits: CREDITS });
    await screen.findByText("Credits on the account");
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(container.textContent).toContain("goodwill after a reading dispute");
    expect(container.querySelectorAll("tbody tr")[0]?.textContent).toContain("BL-2607-0139");
  });

  it("⚠ the SIGN the server sent — a credit is negative, a refund is positive", async () => {
    // ⚠ A panel that once read `272.30` where a customer owed `222.30` is what
    // two writers disagreeing about a sign costs. Nothing between the table and
    // this screen takes an absolute value.
    const { container } = draw({ any: true, refunds: [REFUND], credits: CREDITS });
    await screen.findByText("A refund on its way");
    expect(container.querySelector("[data-credit='0']")?.textContent).toBe("-$25.88");
    expect(container.querySelector("[data-refund-amount]")?.textContent).toBe("$89.80");
  });

  it("TC-5 · negative — ONE sentence separates a credit from a refund", async () => {
    const { container } = draw({ any: true, refunds: [REFUND], credits: CREDITS });
    await screen.findByText("A refund on its way");
    expect(container.querySelector("[data-separating-sentence]")?.textContent).toBe(
      "A credit comes off your next bill. A refund is money sent back.",
    );
  });

  it("TC-4 · negative — a voided refund is LISTED as voided and its reason is not shown", async () => {
    const { container } = draw({
      any: true,
      refunds: [{ ...REFUND, status: "void", voided_at: "2026-09-25T09:00:00Z" }],
      credits: [],
    });
    // ⚠ **THE HEADING FOLLOWS THE STATE** (`DEF-CWP-4142`'s sibling
    // `DEF-CWP-4132`). This line read `findByText("A refund on its way")` and
    // PASSED, over a panel announcing cancelled money as money on its way —
    // the test asserted the defect. A voided refund is not on its way, and the
    // title has to say so or it contradicts the chip one line below it.
    await screen.findByText("A refund we canceled");
    expect(screen.queryByText("A refund on its way")).toBeNull();
    expect(container.querySelector("[data-chip='refund-void']")?.textContent).toContain(
      "Canceled on",
    );
    // The row is still here — never removed.
    expect(container.querySelector("[data-refund-amount]")?.textContent).toBe("$89.80");
    expect(container.textContent).not.toContain("wrong account");
  });

  it("TC-7 · negative — neither credits nor refunds draws ONE line, not two empty tables", async () => {
    const { container } = draw({ any: false, refunds: [], credits: [] });
    await screen.findByText("There is no money coming back to you at the moment.");
    expect(container.querySelector("tbody")).toBeNull();
    expect(container.querySelector("[data-timeline]")).toBeNull();
  });

  it("B14 rule 31 — no database id reaches the screen", async () => {
    const { container } = draw({ any: true, refunds: [REFUND], credits: CREDITS });
    await screen.findByText("A refund on its way");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// US-CWP-049 · where the refund is going back to (CR-068 phase 5, lane D)
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE STORY DRAWS *"Sent · 21 Sep · to the card ending 8812"* AND THIS
// SCREEN MAY NOT PRINT IT TODAY.** `BR-PAY-014` puts card refunds behind the
// rails (W7) and the database refuses `card` as a refund method, so money that
// came in on a card goes back out **by cheque**. Naming the card over a cheque
// in the post would be a promise on screen with nothing behind it. So the same
// fact is told truthfully — the card the money came in on, the cheque it is
// going back on, and WHY — which is the shape TC-3 already asks for.

const CARD_IN: PortalRefund = {
  ...REFUND,
  destination: {
    kind: "fallback",
    method: "check",
    reference: "10241",
    came_in_by: "card",
    brand: "Visa",
    last_four: "8812",
    fallback_reason: "card_rails_absent",
    posted_to: "91 Cedar Row, Austin, TX 78704",
  },
};

describe("CWP-045 · where the refund goes back (US-CWP-049)", () => {
  it("TC-1 — the card the money came in on is named, and so is the cheque", async () => {
    const { container } = draw({ any: true, refunds: [CARD_IN], credits: [] });
    await screen.findByText("A refund on its way");

    // ⚠ Asserted as STRUCTURE: the sentences are written by eleven catalogues
    // (B14 rule 35), and what this screen owes is carrying the server's facts.
    const where = container.querySelector("[data-destination='fallback']");
    expect(where).not.toBeNull();
    expect(where?.getAttribute("data-came-in-by")).toBe("card");
    // The cheque it is actually going back on is still named beside it.
    expect(container.querySelector("[data-refund-method='check']")).not.toBeNull();
  });

  it("⚠ TC-3 — an expired card says WHICH reason, never silently a dead card", async () => {
    const { container } = draw({
      any: true,
      refunds: [
        {
          ...CARD_IN,
          destination: {
            ...CARD_IN.destination!,
            last_four: "4417",
            fallback_reason: "card_expired",
          },
        },
      ],
      credits: [],
    });
    await screen.findByText("A refund on its way");

    expect(
      container.querySelector("[data-fallback-reason]")?.getAttribute("data-fallback-reason"),
    ).toBe("card_expired");
  });

  it("⚠ TC-4 — two sources name the rule that chose one, never a bare *sent*", async () => {
    const { container } = draw({
      any: true,
      refunds: [
        {
          ...CARD_IN,
          destination: {
            kind: "fallback",
            method: "check",
            reference: "10241",
            came_in_by: null,
            brand: null,
            last_four: null,
            fallback_reason: "several_sources",
            posted_to: null,
          },
        },
      ],
      credits: [],
    });
    await screen.findByText("A refund on its way");

    expect(
      container.querySelector("[data-fallback-reason]")?.getAttribute("data-fallback-reason"),
    ).toBe("several_sources");
    // No source is named, because no single payment describes where it came in.
    expect(container.querySelector("[data-came-in-by]")).toBeNull();
  });

  it("TC-2 — a cheque names the address it went to", async () => {
    const { container } = draw({ any: true, refunds: [CARD_IN], credits: [] });
    await screen.findByText("A refund on its way");

    expect(
      container.querySelector("[data-posted-to]")?.getAttribute("data-posted-to"),
    ).toBe("91 Cedar Row, Austin, TX 78704");
  });

  it("⚠ money going back the way it came carries NO fallback sentence", async () => {
    const { container } = draw({
      any: true,
      refunds: [
        {
          ...REFUND,
          destination: {
            kind: "original_method",
            method: "check",
            reference: "10241",
            came_in_by: "check",
            brand: null,
            last_four: null,
            fallback_reason: null,
            posted_to: "91 Cedar Row, Austin, TX 78704",
          },
        },
      ],
      credits: [],
    });
    await screen.findByText("A refund on its way");

    expect(container.querySelector("[data-destination='original_method']")).not.toBeNull();
    expect(container.querySelector("[data-fallback-reason]")).toBeNull();
  });

  it("⚠ a body served WITHOUT a destination renders exactly what it did before", async () => {
    // `destination` is optional on the type for this reason: a cached response
    // from before this landed must not throw, and the screen it renders is the
    // one `US-CWP-056` already shipped.
    const { container } = draw({ any: true, refunds: [REFUND], credits: [] });
    await screen.findByText("A refund on its way");

    expect(container.querySelector("[data-destination]")).toBeNull();
    expect(container.querySelector("[data-refund-method='check']")).not.toBeNull();
  });

  it("D9 — this screen is ONE column on purpose, and that is the drawing (CWP-045)", async () => {
    // ⚠ **UNJUDGEABLE UNTIL NOW** because the demo customer has no refund and
    // no credits, so audit row D9 could not say whether the missing rail was a
    // gap. The fixture here has both.
    //
    // ⚠ **VERDICT: correct, and the row's premise was wrong for this screen.**
    // `08-screen-layouts.md` marks `CWP-045` **T4** — *A REFUND ON ITS WAY*
    // above *CREDITS ON THE ACCOUNT*, two full-width panels, no rail — and
    // this composes no `TwoCol`, which is what T4 asks for. Recorded as a case
    // rather than a note so the next lane reading D9 does not "fix" it by
    // adding a column the drawing does not have.
    const { container } = draw({ any: true, refunds: [REFUND], credits: CREDITS });
    await screen.findAllByText(/refund/i);
    expect(container.querySelector("[data-twocol-rail]")).toBeNull();
  });

  it("CR-085 — nothing owed back says what would create a credit", async () => {
    // ⚠ The drawing's *no credit* state says what would produce one. Told only
    // *there is no money coming back*, a customer who believes they overpaid
    // has been answered without being given any way to check.
    // ⚠ **NO FIGURE IS INVENTED** — the sentence names the two things that
    // create a credit here and quotes nothing.
    const { container } = draw({ any: false, refunds: [], credits: [] });
    await screen.findByText("There is no money coming back to you at the moment.");
    expect(container.querySelector("[data-money-back-what-next]")?.textContent).toContain(
      "if you pay more than a bill",
    );
    expect(container.textContent).not.toMatch(/\$\d/);
  });


  it("R-10 — a failed read about money owed to you is not the end of the screen", async () => {
    // A failure here is the one that reads as *your money has gone*.
    let calls = 0;
    readMoneyBack = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return { any: true, refunds: [REFUND], credits: CREDITS };
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/money-back"]}>
        <Routes>
          <Route path="/:tenant/portal/money-back" element={<MoneyBackView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read this right now. Try again in a moment.");
    expect(
      container
        .querySelector('[data-portal-state="failed"] [data-way-out="payments"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/payments");
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    expect(await screen.findByText("A refund on its way")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

});
