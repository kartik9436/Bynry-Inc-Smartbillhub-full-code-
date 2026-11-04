// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-052 (EP-CWP-10) · Screen: CWP-043
// Rules:    BR-CWP-063 (a plan holds the arrears; new bills still arrive) ·
//           BR-CWP-064 (late-fee and disconnection suspension are a PER-PLAN
//           election) · B14 rule 31 (no database id on screen) · rule 33
// Open:     OQ-CWP-1720 — the panel must NOT say a plan ends after two misses
// Cases:    six rows with four states · the payment that cleared each · the
//           down payment · the cadence READ from the record · fees still apply
//           · a CLOSED plan still reachable · the missing sentence
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalPlan } from "../api/portalClient";

let readPlans: () => Promise<{ plans: PortalPlan[] }> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getCurrentPlans: () => readPlans() };
});

const { YourPlanView } = await import("./YourPlan");

/** `US-CWP-052` §4 — the story's own fixture, read on 5 December 2026. */
const PLAN: PortalPlan = {
  status: "active",
  live: true,
  cadence: "monthly",
  currency: "USD",
  total: "172.2000",
  down_payment: "40.0000",
  spread: "132.2000",
  paid_to_date: "66.0900",
  term_months: 6,
  started_on: "2026-09-03",
  closed_on: null,
  suspend_late_fees: true,
  suspend_disconnect: true,
  autopay_enabled: true,
  current_bill_still_due: true,
  instalments_total: "132.2000",
  // ⚠ A copy of the signed agreement IS kept for this plan (`CR-085`
  // `CPB-14`). The case below asserts the other branch explicitly.
  agreement_available: true,
  instalments: [
    {
      seq: 1, due_on: "2026-09-14", amount: "22.0300", currency: "USD",
      state: "paid_on_time", days_until: null, paid_on: "2026-09-14",
      paid_reference: "PAY-26-09011", carries_the_rounding: false,
    },
    {
      seq: 2, due_on: "2026-10-14", amount: "22.0300", currency: "USD",
      state: "paid_on_time", days_until: null, paid_on: "2026-10-14",
      paid_reference: "PAY-26-10004", carries_the_rounding: false,
    },
    {
      seq: 3, due_on: "2026-11-14", amount: "22.0300", currency: "USD",
      state: "paid_late", days_until: null, paid_on: "2026-11-15",
      paid_reference: "PAY-26-11077", carries_the_rounding: false,
    },
    {
      seq: 4, due_on: "2026-12-14", amount: "22.0300", currency: "USD",
      state: "due_next", days_until: 9, paid_on: null,
      paid_reference: null, carries_the_rounding: false,
    },
    {
      seq: 5, due_on: "2027-01-14", amount: "22.0300", currency: "USD",
      state: "to_come", days_until: null, paid_on: null,
      paid_reference: null, carries_the_rounding: false,
    },
    {
      seq: 6, due_on: "2027-02-14", amount: "22.0500", currency: "USD",
      state: "to_come", days_until: null, paid_on: null,
      paid_reference: null, carries_the_rounding: true,
    },
  ],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN** (CLAUDE.md hard-won
 * law 2). Bare inside a `MemoryRouter` with no matching `<Route>`,
 * `useParams().tenant` is `undefined` and every address this screen builds
 * comes out `//portal/…` — a protocol-relative URL to ANOTHER HOST that reads
 * as a perfectly good string to `toContain`. A door assertion cannot be
 * written truthfully without this.
 */
function draw(plans: PortalPlan[]) {
  readPlans = async () => ({ plans });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/plan"]}>
      <Routes>
        <Route path="/:tenant/portal/plan" element={<YourPlanView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-043 · your payment plan (US-CWP-052)", () => {
  it("TC-1 — six rows with their four states, and DUE IN 9 DAYS on the next", async () => {
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelectorAll("tbody tr")).toHaveLength(6);
    expect(screen.getAllByText("Paid on time")).toHaveLength(2);
    expect(screen.getByText("Paid late")).toBeTruthy();
    expect(screen.getAllByText("To come")).toHaveLength(2);
  });

  it("TC-2 — instalment two NAMES the payment that cleared it", async () => {
    // ⚠ Without it a customer cannot match an instalment to a line on their
    // bank statement, which is the reason this screen exists at all.
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-paid-by='2']")?.textContent).toBe(
      "Paid by PAY-26-10004",
    );
    expect(container.querySelector("[data-paid-by='4']")).toBeNull();
  });

  it("TC-3/TC-4 — the down payment is shown and the cadence is READ", async () => {
    const { container } = draw([{ ...PLAN, cadence: "weekly" }]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-up-front]")?.textContent).toBe("$40.00");
    // ⚠ READ from the record, never assumed monthly.
    expect(container.querySelector("[data-cadence]")?.textContent).toBe("Weekly");
  });

  it("the instalments add up to the amount the plan spreads", async () => {
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-total='instalments-total']")?.textContent).toContain(
      "$132.20",
    );
  });

  it("TC-6 — the hold panel carries *new bills still arrive*", async () => {
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-hold='late-fees']")?.textContent).toBe(
      "No late fees on the amount in the plan.",
    );
    expect(container.querySelector("[data-hold='new-bills']")?.textContent).toBe(
      "New bills still arrive and still have to be paid.",
    );
  });

  it("TC-5 — a plan with the election OFF says fees still apply", async () => {
    // ⚠ `BR-CWP-064`. The case the blueprint calls *worse than a blank space*.
    const { container } = draw([{ ...PLAN, suspend_late_fees: false }]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-hold='late-fees']")?.textContent).toBe(
      "Late fees still apply on this plan.",
    );
  });

  it("OQ-CWP-1720 — the panel does NOT say the plan ends after two misses", async () => {
    // ⚠ **THE ABSENCE IS THE ASSERTION.** PO 2026-08-11: *"nodrop we chase for
    // payments until write off"*. The panel says what happens instead.
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.textContent).not.toMatch(/plan ends/i);
    expect(container.querySelector("[data-missed-note]")?.textContent).toBe(
      "We get in touch about it. The plan stays open.",
    );
  });

  it("TC-8 — a CLOSED plan is still reachable, marked closed with its date", async () => {
    const { container } = draw([
      { ...PLAN, status: "closed", live: false, closed_on: "2025-12-01" },
    ]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-plan='closed']")).toBeTruthy();
    expect(container.querySelector("[data-closed-on='2025-12-01']")?.textContent).toContain(
      "Closed on 2025-12-01.",
    );
  });

  it("TC-10 — autopay on the plan reaches the screen", async () => {
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.querySelector("[data-autopay='on']")?.textContent).toBe("Yes");
  });

  it("B14 rule 31 — no database id reaches the page", async () => {
    const { container } = draw([PLAN]);
    await screen.findByText("Due in 9 days");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("a customer with no plan gets a sentence, never an empty table", async () => {
    const { container } = draw([]);
    expect(await screen.findByText("You are not on a payment plan.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
  });

  it("says so when the read fails, rather than drawing an empty plan", async () => {
    readPlans = async () => {
      throw new Error("read failed");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/plan"]}>
        <YourPlanView accountId="acc-1" />
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read your plan.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
  });

  it("CR-085 — not on a plan is not the end of the screen", async () => {
    // ⚠ *You are not on a payment plan.* was the entire page, on a screen a
    // customer opens because they are wondering whether they could be.
    const { container } = draw([]);
    await screen.findByText("You are not on a payment plan.");
    // ⚠ The door is now a `waysOut` on the shared state card (`CR-085` step 2,
    // R-10): same destination, asserted WHOLE, and asserted to be INSIDE the
    // card that carries the sentence.
    expect(
      container
        .querySelector('[data-portal-state="empty"] [data-way-out="ask-for-a-plan"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/ask-for-a-plan");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` `CPB-14` — the SIGNED agreement, which was held over a document
  // the store may well be holding. `CPB-03` released the same hold on
  // `CWP-063` a wave earlier and left this one standing.
  // ═══════════════════════════════════════════════════════════════════════

  it("CPB-14 · the agreement is a live download at this tenant and this account", async () => {
    const { container } = draw([PLAN]);
    await screen.findByText(/Your payment plan/i);
    const link = container.querySelector("[data-download='plan-agreement']");
    expect(link?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/accounts/acc-1/plans/current/agreement",
    );
    expect(screen.queryByText("Downloads arrive later this year")).not.toBeInTheDocument();
  });

  it("CPB-14 · and it is HELD, truthfully, where no copy was filed", async () => {
    const { container } = draw([{ ...PLAN, agreement_available: false }]);
    await screen.findByText(/Your payment plan/i);
    expect(container.querySelector("[data-download='plan-agreement']")).toBeNull();
    // The same sentence `CWP-031` uses, because it is the same fact about the
    // same document — and unlike the hold it replaces it cannot rot: the
    // server answers it from the store on every draw.
    expect(screen.getByText("We kept no copy of this.")).toBeInTheDocument();
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2, lane 7 — `DEF-CWP-4181`, `DEF-CWP-4183` and R-10.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-4181 — a plan with a payment due next offers a way to pay it", async () => {
    // ⚠ **THE DRAWING HEADS THIS SCREEN *· actions ↓ Agreement · Pay the next
    // one*** and only the agreement was built. The old note said this lane
    // *"will not invent a destination for money"* — true when it was written,
    // and it stopped being true when `CWP-038` shipped: `/pay-now` is routed,
    // live, and is the door `CWP-057` already sends *Pay $412.60* to.
    // ⚠ **THE AMOUNT IS THE SERVER'S `due_next` ROW AND NOTHING IS SUMMED.**
    const { container } = draw([PLAN]);
    await screen.findByText("Your payment plan");
    const pay = container.querySelector('a[href="/pine-hill/portal/pay-now"]');
    expect(pay).not.toBeNull();
    expect(pay?.textContent).toContain("$22.03");
  });

  it("DEF-CWP-4181 — a closed plan with nothing due next offers NO pay control", async () => {
    // `BR-CWP-093`. A control that would take money against nothing is worse
    // than no control.
    const closed = {
      ...PLAN,
      live: false,
      closed_on: "2026-12-01",
      instalments: PLAN.instalments.map((row) => ({ ...row, state: "paid_on_time" as const })),
    };
    const { container } = draw([closed]);
    await screen.findByText("Your payment plan");
    expect(container.querySelector('a[href="/pine-hill/portal/pay-now"]')).toBeNull();
  });

  it("DEF-CWP-4183 — the title is printed ONCE, not twice one line apart", async () => {
    // `Your payment plan` as the page `<h1>` and `YOUR PAYMENT PLAN` as the
    // card's section title — B14 rule 32's description budget spent saying the
    // screen's own name again.
    const { container } = draw([PLAN]);
    await screen.findByText("Your payment plan");
    expect(screen.getAllByText("Your payment plan")).toHaveLength(1);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
  });

  it("R-10 — a failed read still names the way to ask for a plan", async () => {
    let calls = 0;
    readPlans = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return { plans: [PLAN] };
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/plan"]}>
        <Routes>
          <Route path="/:tenant/portal/plan" element={<YourPlanView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read your plan.");
    expect(
      container
        .querySelector('[data-portal-state="failed"] [data-way-out="ask-for-a-plan"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/ask-for-a-plan");
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    // ⚠ **WAIT ON SOMETHING THE POPULATED BRANCH DRAWS AND THE FAILED ONE DOES
    // NOT.** `data-testid="your-plan"` is on BOTH cards, so waiting on it would
    // return immediately over the failure and prove nothing — the false pass
    // this whole group of cases exists to rule out.
    await screen.findByText("3 of 6 paid.");
    expect(container.querySelector("[data-progress]")?.textContent).toBe("3 of 6 paid.");
    expect(container.querySelector('[data-portal-state="failed"]')).toBeNull();
    expect(calls).toBe(2);
  });

});
