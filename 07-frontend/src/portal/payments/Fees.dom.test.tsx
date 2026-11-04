// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-050 (EP-CWP-09) · Screen: CWP-050
// Rules:    BR-CWP-058 · BR-CWP-056 (the Pay control is disabled with its
//           reason) · BR-CWP-093 · B14 rule 31 (the `SR-` number is the
//           identity) · CLAUDE.md hard rule 2 · hard-won law 2 (assert the
//           destination BY ADDRESS)
// Cases:    TC-1 the four rows · TC-2 ⚠ $335.00 and $150.00 · TC-3 the waived
//           row struck through · TC-5 the held control · TC-6 ⚠ no amount box ·
//           TC-8 nothing before approval · the deposit that is ABSENT, never
//           $0.00 · the holding screen is GONE
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalFees } from "../api/portalClient";

let readFees: () => Promise<PortalFees> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getFees: () => readFees() };
});

const { FeesView } = await import("./Fees");

const cell = (amount: string, display: string) => ({
  kind: "amount",
  amount,
  display,
  currency: "USD",
});

/** `US-CWP-050` §4 — `SR-26-0061`, and `$185.00 + $150.00 = $335.00`. */
const BODY: PortalFees = {
  any: true,
  reference: "SR-26-0061",
  lines: [
    {
      what: "New connection",
      when: "before_we_start",
      amount: "185.0000",
      display: "$185.00",
      currency: "USD",
      waived: false,
      settled: false,
    },
    {
      what: "Meter installation",
      when: "before_we_start",
      amount: "150.0000",
      display: "$150.00",
      currency: "USD",
      waived: false,
      settled: false,
    },
    {
      what: "Account set-up",
      when: "before_we_start",
      amount: "25.0000",
      display: "$25.00",
      currency: "USD",
      waived: true,
      settled: false,
    },
    {
      what: "Security deposit",
      when: "on_your_first_bill",
      amount: "150.0000",
      display: "$150.00",
      currency: "USD",
      waived: false,
      settled: false,
    },
  ],
  to_pay_now: cell("335.0000", "$335.00"),
  on_first_bill: cell("150.0000", "$150.00"),
  available: false,
  held_reason: "no_fee_payment_path",
  problems: [{ code: "no_card_fee_computed" }],
};

/** ⚠ Mounted under the REAL path pattern (`DEF-CWP-3925`) — see the autopay
 *  test's own note for why a bare `MemoryRouter` cannot catch a broken link. */
function draw(body: PortalFees) {
  readFees = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/fees"]}>
      <Routes>
        <Route path="/:tenant/portal/fees" element={<FeesView />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-050 · fees to pay (US-CWP-050)", () => {
  it("TC-1 — four rows, including the deposit that lands on the first bill", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    expect(container.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(container.querySelector("[data-fee='0']")?.textContent).toBe("New connection");
    expect(container.querySelector("[data-fee='3']")?.textContent).toBe("Security deposit");
    expect(container.querySelector("[data-fee-when='on_your_first_bill']")).not.toBeNull();
  });

  it("⚠ TC-2 — $335.00 to pay now, $150.00 on the first bill, $25.00 in neither", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    expect(container.querySelector("[data-total='to-pay-now']")?.textContent).toContain(
      "$335.00",
    );
    expect(container.querySelector("[data-total='on-first-bill']")?.textContent).toContain(
      "$150.00",
    );
    // The waived figure is on screen as a LINE and in no total.
    expect(
      container.querySelector("[data-total='to-pay-now']")?.textContent,
    ).not.toContain("$360.00");
  });

  it("⚠ TC-3 — the waived fee is listed, struck through, not removed", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    const waived = container.querySelector("[data-fee-amount='2']");
    expect(waived?.tagName.toLowerCase()).toBe("s");
    expect(waived?.textContent).toBe("$25.00");
    expect(waived?.hasAttribute("data-waived")).toBe(true);
  });

  it("TC-5 — the Pay control is disabled with its reason, over a readable table", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    const held = container.querySelector("[data-held='true']");
    expect(held?.querySelector("button")).toBeDisabled();
    // ⚠ The FIGURE is asserted as structure — the label around it is a
    // catalogue sentence and its word order is not this screen's to promise.
    const hold = container.querySelector("[data-fees-hold]");
    expect(hold?.getAttribute("data-fees-hold")).toBe("no_fee_payment_path");
    expect(hold?.getAttribute("data-pay-amount")).toBe("$335.00");
    // The table is fully readable behind the refusal.
    expect(container.querySelectorAll("tbody tr")).toHaveLength(4);
  });

  it("⚠ TC-6 — there is no amount box, so no partial payment is expressible", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelector("form")).toBeNull();
  });

  it("TC-8 — nothing is quoted before a clerk approves", async () => {
    const { container } = draw({
      any: false,
      reference: null,
      lines: [],
      to_pay_now: null,
      on_first_bill: null,
      available: false,
      held_reason: "no_fee_payment_path",
      problems: [],
    });
    await screen.findByTestId("fees");

    // ⚠ The empty branch is now the shared portal state card (`CR-085` step 2,
    // R-22): the kind is in the DOM, which is the only way that rule can be
    // checked at all — a check cannot read whether a SENTENCE means *empty*.
    expect(container.querySelector('[data-portal-state="empty"]')).not.toBeNull();
    // ⚠ **AND `data-screen` IS ON THIS BRANCH NOW.** It was on two of the four,
    // so a failed or still-loading `/fees` carried no screen mark and every
    // rendered check in this repository selects on exactly that.
    expect(container.querySelector('[data-screen="CWP-050"]')).not.toBeNull();
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector("[data-held='true']")).toBeNull();
    expect(container.textContent).not.toContain("$");
  });

  it("⚠ a deposit nobody has priced is ABSENT — never a $0.00 row", async () => {
    const { container } = draw({
      ...BODY,
      lines: BODY.lines.slice(0, 3),
      on_first_bill: null,
      problems: [{ code: "deposit_not_priced" }],
    });
    await screen.findByTestId("fees");

    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(container.querySelector("[data-total='on-first-bill']")).toBeNull();
    expect(container.textContent).not.toContain("$0.00");
    // And the rail's deposit note goes with it rather than promising a return
    // of money nobody is taking.
    expect(container.querySelector("[data-deposit-note]")).toBeNull();
  });

  it("⚠ B14 rule 31 — the SR number is the identity and no row id is on screen", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    expect(container.querySelector("[data-reference]")?.textContent).toBe("SR-26-0061");
    // A uuid, or eight characters of one, is the same breach.
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  });

  it("⚠ the question link is asserted BY ADDRESS (DEF-CWP-3925)", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    const link = container.querySelector("a[href*='ask-a-question']");
    expect(link?.getAttribute("href")).toBe("/pine-hill/portal/ask-a-question");
  });

  it("⚠ the holding screen is GONE — this route no longer answers with one", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("fees");

    expect(container.querySelector("[data-holding-screen]")).toBeNull();
    expect(container.querySelector("[data-screen='CWP-050']")).not.toBeNull();
  });

  it("D9 — the rail draws its two notes when there are fees to pay (CWP-050)", async () => {
    // ⚠ **UNJUDGEABLE UNTIL NOW** because the demo customer has no fees.
    // ⚠ **VERDICT: correct.** `08-screen-layouts.md` gives `CWP-050` a rail of
    // `Panel.Info` and `Panel.Warning`, and both are there beside the fee
    // table with the fixture that has fees on it.
    const { container } = draw(BODY);
    await screen.findAllByText(/335/);
    const rail = container.querySelector("[data-screen='CWP-050'] [data-twocol-rail]");
    expect(rail, "CWP-050 draws no right-hand column").not.toBeNull();
    expect(rail?.querySelectorAll("[data-panel]").length ?? 0).toBeGreaterThanOrEqual(1);
  });

  it("R-10 — a failed read still offers the question route, and really re-reads", async () => {
    let calls = 0;
    readFees = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return BODY;
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/fees"]}>
        <Routes>
          <Route path="/:tenant/portal/fees" element={<FeesView />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read this right now. Try again in a moment.");
    // ⚠ **AND `data-screen` IS ON THIS BRANCH NOW** — it was on two of the four,
    // so a failed or still-loading `/fees` carried no screen mark and every
    // rendered check in this repository selects on exactly that.
    expect(container.querySelector("[data-screen='CWP-050']")).not.toBeNull();
    expect(
      container
        .querySelector('[data-portal-state="failed"] [data-way-out="ask-a-question"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/ask-a-question");
    // ⚠ A presence assertion would pass on a button wired to nothing
    // (`DEF-MET-4764`), so the control is pressed and the second read succeeds.
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    // ⚠ **WAIT ON A FEE ROW, NOT ON `data-testid="fees"`.** The FAILED card
    // carries that same testid — `PortalState testId="fees"` — so a wait on it
    // resolves instantly against the card that is still refusing, and the
    // assertion proves the retry happened when it has not. That is exactly the
    // false pass this case exists to rule out, met while writing the case.
    await screen.findByText("New connection");
    expect(container.querySelector("[data-reference]")?.textContent).toBe("SR-26-0061");
    expect(container.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(container.querySelector('[data-portal-state="failed"]')).toBeNull();
    expect(calls).toBe(2);
  });

});
