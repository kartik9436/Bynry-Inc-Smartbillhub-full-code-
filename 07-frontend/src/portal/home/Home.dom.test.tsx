// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-024 (EP-CWP-04) — the balance a customer came for.
//           Screen: CWP-022 (the LEAD TILE; the rest of Home is wave F)
// Rules:    BR-CWP-047 (re-read on every mount; nothing caches a balance) ·
//           BR-CWP-015 (separately, and totalled ONLY when there is more than
//           one — a total of one number is noise) · B14 rule 17 (an empty
//           state that says what fills it) · CLAUDE.md hard rule 2 (4 dp
//           stored, 2 dp displayed)
// Defects:  DEF-CWP-3766 — `Home.tsx` cited this file from the day it shipped
//           and it did not exist. G95 now refuses that shape.
// Cases:    US-CWP-024 TC-1 (the figure and the date) · TC-2 (four rows and a
//           total) · the householder's missing total · the empty state ·
//           US-CWP-025 TC-1/2/3/5/7 (the attention panel, the tip slot, the
//           usage tile and its unit — and each of them ABSENT)
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { BalanceSummary, PortalHome } from "../api/portalClient";

// A plain function rather than `vi.fn()` — a spy tracks the promise it returns
// and that tracking reaches a rejection before the component's own `.catch`,
// which turns a handled error into a suite failure. Same reasoning as
// `MyAccounts.dom.test.tsx`.
let readHome: () => Promise<PortalHome> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getHome: () => readHome() };
});

const { HomeView, daysUntil } = await import("./Home");

const ONE: BalanceSummary = {
  as_of: "2026-09-02",
  account_count: 1,
  total_owing: "142.1800",
  currency: "USD",
  problems: [],
  accounts: [
    {
      account_id: "a1",
      owing: "142.1800",
      bills_open: "142.1800",
      credit_held: "0.0000",
      currency: "USD",
      due_on: "2026-09-14",
      open_bill_count: 1,
      problems: [],
    },
  ],
};

/** ⚠ The page reads ONE endpoint since wave F — `getHome` — and the balances
 *  are a key inside it. The lead tile's markup is unchanged; what moved is
 *  where its data comes from, and this helper keeps every case below written
 *  in terms of the balances they were written for. */
const NO_SERVICE: PortalHome["service"] = {
  address: { value: null, varies: false },
  plan: { value: null, varies: false },
  billed: { value: null, varies: false },
  paperless: { value: null, varies: false },
};

/** ⚠ **NOTHING KNOWN ABOUT THE ACCOUNT, WHICH IS AN ORDINARY ANSWER AND NOT AN
 *  ERROR** (`BR-CWP-093`). Every case that does not care about the account card
 *  gets this and the card draws NOTHING at all — which is itself asserted
 *  below, because a card that appears empty is the defect this shape exists to
 *  prevent. */
const NO_IDENTITY: PortalHome["identity"] = {
  name: { value: null, varies: false },
  status: { value: null, varies: false },
  status_class: { value: null, varies: false },
  services: [],
  equipment: [],
  phone: null,
  phone_varies: false,
  email: null,
  email_varies: false,
};

/**
 * ⚠ **MOUNTED UNDER THE REAL ROUTE PATTERN, NOT BARE** (`DEF-CWP-3925`'s
 * fixture half, hard-won law 2). `usePortalPath` reads `:tenant` off the
 * address the browser is on; a component mounted bare in a `MemoryRouter`
 * builds every link as `//portal/…` — a protocol-relative URL to ANOTHER HOST
 * that reads as a perfectly good string to `toContain`. Every door this screen
 * draws is asserted below, so the fixture has to be able to tell a working link
 * from a broken one.
 */
function draw(balances: BalanceSummary, extra: Partial<PortalHome> = {}) {
  readHome = async () => ({
    as_of: "2026-09-02",
    balances,
    last_bill: null,
    last_payment: null,
    usage: [],
    usage_series: [],
    recent_bills: [],
    service: NO_SERVICE,
    identity: NO_IDENTITY,
    attention: [],
    tip: null,
    ...extra,
  });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
      <Routes>
        <Route
          path="/:tenant/portal/home"
          element={<HomeView today={new Date("2026-09-02T00:00:00Z")} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-022 · the lead balance tile (US-CWP-024)", () => {
  it("TC-1 — the figure and the date, with the days between them", async () => {
    draw(ONE);
    expect(await screen.findByText("$142.18")).toBeTruthy();
    // ⚠ 2 Sep to 14 Sep is TWELVE days, and the tile says so rather than
    // making the customer count. The arithmetic is `daysUntil`'s, asserted
    // below on its own so a formatting change cannot hide a date bug.
    expect(screen.getByText(/in 12 days/)).toBeTruthy();
  });

  it("a householder gets the date on the tile and NO accounts door (BR-CWP-015)", async () => {
    // ⚠ **THE FOUR-ROWS-AND-A-TOTAL PRESENTATION MOVED TO `CWP-023` ON
    // 2026-09-05, WHICH IS WHERE `US-CWP-024` ALWAYS PUT IT** — its acceptance
    // reads *"when the ACCOUNTS SCREEN loads, then it shows four rows totalling
    // $872.82 without merging them"*, and `MyAccounts.dom.test.tsx` asserts
    // exactly that with nothing beside the total to press. `CWP-022`'s layout
    // opens with a `KpiRow` and has no room for four rows (`DEF-CWP-3965`).
    const { container } = draw(ONE);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-kpi-lead]")).not.toBeNull();
    expect(container.querySelector("[data-home-accounts-door]")).toBeNull();
    expect(container.querySelector("[data-due]")?.textContent).toContain("in 12 days");
  });

  it("TC-2 — the landlord's four accounts total $872.82, and the rows are one door away", async () => {
    const { container } = draw({
      ...ONE,
      account_count: 4,
      total_owing: "872.8200",
      accounts: [
        ONE.accounts[0],
        { ...ONE.accounts[0], account_id: "a2", owing: "0.0000", due_on: null },
        { ...ONE.accounts[0], account_id: "a3", owing: "318.0400" },
        { ...ONE.accounts[0], account_id: "a4", owing: "412.6000" },
      ],
    });
    expect(await screen.findByText("$872.82")).toBeTruthy();
    // ⚠ **NOTHING BESIDE THE FIGURE TO PRESS** (`BR-CWP-015` — the total is
    // information, never payable). The door goes to the ROWS, which is
    // `CWP-023`, and it is asserted BY ADDRESS: a component mounted off its own
    // route pattern builds `//portal/accounts`, a protocol-relative URL to
    // another host that `toContain("accounts")` would happily accept.
    const tile = container.querySelector("[data-kpi='balance']");
    expect(tile?.querySelector("button")).toBeNull();
    const door = container.querySelector("[data-home-accounts-door]");
    expect(door?.getAttribute("href")).toBe("/pine-hill/portal/accounts");
  });

  it("B14 rule 17 — no accounts is a sentence, never a bare $0.00", async () => {
    const { container } = draw({ ...ONE, account_count: 0, total_owing: null, accounts: [] });
    expect(await screen.findByText("Add an account and your balance appears here.")).toBeTruthy();
    expect(container.querySelector("[data-kpi-row]")).toBeNull();
    expect(screen.queryByText("$0.00")).toBeNull();
  });

  it("says so when the read fails, rather than showing a stale or zero figure", async () => {
    readHome = async () => {
      throw new Error("read failed");
    };
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
        <Routes>
          <Route
            path="/:tenant/portal/home"
            element={<HomeView today={new Date("2026-09-02T00:00:00Z")} />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read your balance.")).toBeTruthy();
  });
});

/**
 * `R-22` (PO 2026-09-11, verbatim: *"differntiate it using text message"*) and
 * `R-10` (*"when a screen tells a customer something bad, the thing they can do
 * about it must be on that same screen, next to the message"*).
 *
 * ⚠ **THE THREE SENTENCES ALREADY DIFFERED; NOTHING SAID WHICH STATE IT WAS.**
 * Home drew one bare `Card` with one grey line for loading, for failed and for
 * empty, so R-22 was unobservable by anything but a person reading the words —
 * and the loading and failed branches carried no `data-screen="CWP-022"` at
 * all, which is the mark every rendered check in this repo selects on.
 *
 * ⚠ **AND NO PAGE TITLE IS ASSERTED, DELIBERATELY.** `CWP-022` is in
 * `pageHeadCensus.test.ts`'s `CORRECTLY_HEADLESS`, on the drawing's own
 * authority — a title above the balance would push the one figure the page
 * exists for below the fold.
 */
describe("CWP-022 · loading, empty and failed (R-22, R-10)", () => {
  function drawFailed() {
    readHome = async () => {
      throw new Error("read failed");
    };
    return render(
      <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
        <Routes>
          <Route
            path="/:tenant/portal/home"
            element={<HomeView today={new Date("2026-09-02T00:00:00Z")} />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("the screen keeps its mark when the read fails", async () => {
    const { container } = drawFailed();
    await screen.findByText("We could not read your balance.");
    expect(container.querySelector("[data-screen='CWP-022']")).not.toBeNull();
  });

  it("the card says WHICH of the three it is, and the three differ", async () => {
    const { container } = drawFailed();
    await screen.findByText("We could not read your balance.");
    expect(container.querySelector("[data-portal-state]")?.getAttribute("data-portal-state")).toBe(
      "failed",
    );
    cleanup();
    const empty = draw({ ...ONE, account_count: 0, total_owing: null, accounts: [] });
    await screen.findByText("Add an account and your balance appears here.");
    expect(
      empty.container.querySelector("[data-portal-state]")?.getAttribute("data-portal-state"),
    ).toBe("empty");
  });

  it("R-10 — the failed card carries a way out, and it re-reads", async () => {
    const { container } = drawFailed();
    await screen.findByText("We could not read your balance.");
    const retry = container.querySelector("[data-way-out='home-retry']");
    expect(retry).not.toBeNull();
    expect(retry?.textContent).toBe("Try again");
    // ⚠ **A CONTROL THAT DOES SOMETHING.** `PortalState`'s own docstring names
    // the trap this asserts against — `EmptyList`'s `onCta: () => undefined`
    // (`DEF-MET-4764`), a button that looks pressable, is pressable, and does
    // nothing. Pressing it must reach the reader again.
    let reads = 0;
    readHome = async () => {
      reads += 1;
      throw new Error("read failed");
    };
    (retry as HTMLElement).click();
    await screen.findByText("We could not read your balance.");
    expect(reads).toBeGreaterThan(0);
  });

  it("R-10 — the empty card offers the thing its own sentence asks for", async () => {
    const { container } = draw({ ...ONE, account_count: 0, total_owing: null, accounts: [] });
    await screen.findByText("Add an account and your balance appears here.");
    const door = container.querySelector("[data-way-out='home-add-account']");
    expect(door?.getAttribute("href")).toBe("/pine-hill/portal/accounts/add");
    expect(door?.textContent).toBe("Add another account");
  });
});

/** The drawn `NOTHING DUE` state and the drawn door out of the account card. */
describe("CWP-022 · paid up, and the door to one account", () => {
  it("nothing owed says so, rather than printing a bare $0.00", async () => {
    const { container } = draw({
      ...ONE,
      total_owing: "0.0000",
      accounts: [{ ...ONE.accounts[0], owing: "0.0000", due_on: null, open_bill_count: 0 }],
    });
    await screen.findByText("$0.00");
    expect(container.querySelector("[data-home-paid-up]")?.textContent).toBe(
      "You are all paid up.",
    );
  });

  it("a due date still wins over the paid-up line", async () => {
    const { container } = draw(ONE);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-home-paid-up]")).toBeNull();
    expect(container.querySelector("[data-due]")).not.toBeNull();
  });

  it("DEF-CWP-4901 — the account card opens the screen about this property", async () => {
    const { container } = draw(ONE, {
      identity: { ...NO_IDENTITY, name: { value: "Elena Rivera", varies: false } },
    });
    await screen.findByText("Elena Rivera");
    const door = [...container.querySelectorAll("[data-testid='home-account'] a")].find(
      (a) => a.getAttribute("href") === "/pine-hill/portal/account",
    );
    expect(door, "the drawn → Everything about this account").not.toBeUndefined();
    expect(door?.textContent).toBe("Everything about this account");
  });
});

describe("daysUntil — the arithmetic on its own", () => {
  const today = new Date("2026-09-02T00:00:00Z");

  it("counts whole days forward", () => {
    expect(daysUntil("2026-09-14", today)).toBe(12);
  });

  it("is negative once the date has passed, so the caller can tell", () => {
    expect(daysUntil("2026-08-14", today)).toBe(-19);
  });

  it("answers null for no date rather than guessing a zero", () => {
    expect(daysUntil(null, today)).toBeNull();
  });
});

describe("CWP-022 · the rest of the page (US-CWP-025)", () => {
  it("TC-1 — an amount owing puts *Pay $142.18* in the attention panel", async () => {
    const { container } = draw(ONE, {
      attention: [{ kind: "pay", amount: "142.1800", currency: "USD" }],
    });
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-attention='pay']")?.textContent).toContain("Pay $142.18");
  });

  it("TC-2 — nothing to act on means NO panel, not an empty box", async () => {
    // ⚠ `BR-CWP-093`. The difference between a product with nothing to say
    // today and one that looks broken is exactly this.
    const { container } = draw(ONE);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-home-attention]")).toBeNull();
  });

  it("TC-3 — no tip is live, so there is no slot at all", async () => {
    const { container } = draw(ONE);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-tip-bar]")).toBeNull();
  });

  it("TC-7 — the usage tile carries its UNIT, never a bare number", async () => {
    // ⚠ **THE STORED FIGURE IS `NUMERIC(18,6)` AND THIS FIXTURE NOW SAYS SO
    // (`DEF-CWP-3770`).** The old version handed the component a hand-typed
    // `"4820"` that no server has ever sent, so the test passed while the live
    // tile read `4820.000000 gal`. The row below is the shape the read really
    // serves, and the assertion is that the screen draws the DISPLAY string.
    const { container } = draw(ONE, {
      usage: [
        {
          month: "2026-08",
          service: "water",
          unit: "gal",
          quantity: "4820.000000",
          quantity_display: "4820",
          estimated: false,
        },
      ],
    });
    await screen.findByText("$142.18");
    // ⚠ **THE WHOLE TILE, NOT THE FIGURE'S OWN SPAN.** Since `DEF-CWP-3965` the
    // unit is `KpiTile`'s `unit` slot beside the figure rather than a second
    // word inside it, and a test reading only the figure would go green over a
    // tile that had lost its unit — which is the one thing hard rule 3 exists
    // to stop.
    const tile = container.querySelector("[data-kpi='usage-water']")?.textContent ?? "";
    // ⚠ **GROUPED** (`DEF-CWP-4140`). This asserted the ungrouped `4820`, so
    // it passed on the defect and would have gone red on the fix — the
    // clearest possible case of a check pointed at the wrong thing.
    expect(tile).toContain("4,820");
    expect(tile).not.toContain("4820.000000");
    expect(tile).toContain("gal");
  });

  it("TC-5 — no measured service means no usage tile AND no empty chart", async () => {
    const { container } = draw(ONE);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-home-usage]")).toBeNull();
  });

  it("the two money tiles are ABSENT for a new customer, never $0.00", async () => {
    // ⚠ `$0.00` says *you were billed nothing*; an absent tile says *you have
    // not been billed yet*, and only one of those is true in week one.
    const { container } = draw(ONE);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-last-bill]")).toBeNull();
    expect(container.querySelector("[data-last-payment]")).toBeNull();
  });

  it("shows the last bill, the last payment and three recent bills when they exist", async () => {
    const bill = {
      number: "BL-2608-0141",
      issued_on: "2026-08-26",
      due_on: "2026-09-14",
      total: "142.1800",
      currency: "USD",
      period_start: "2026-07-27",
      period_end: "2026-08-26",
    };
    const { container } = draw(ONE, {
      last_bill: bill,
      last_payment: {
        amount: "138.4400",
        currency: "USD",
        paid_on: "2026-08-12",
        method: "Bank transfer",
      },
      // ⚠ **THREE DIFFERENT MONTHS, NOT THREE COPIES.** The chooser is keyed
      // on the bill number and LABELLED by the issue month; a fixture whose
      // three bills share one month draws three identical options and the
      // case could not tell a working chooser from a broken one.
      recent_bills: [
        bill,
        { ...bill, number: "BL-2607-0139", issued_on: "2026-07-26" },
        { ...bill, number: "BL-2606-0147", issued_on: "2026-06-26" },
      ],
    });
    await screen.findByText("$872.82").catch(() => undefined);
    expect(container.querySelector("[data-last-bill]")?.textContent).toContain("$142.18");
    expect(container.querySelector("[data-last-payment]")?.textContent).toContain("$138.44");
    // ⚠ **ONE BILL IS DRAWN AND THREE ARE OFFERED** — the panel is *Your
    // bill*, singular, since the Product Owner asked for the chooser
    // (2026-09-08). The other two are in it, so a customer can reach them
    // without leaving the page, which is the whole point of the control.
    expect(container.querySelectorAll("[data-bill]")).toHaveLength(1);
    const months = [
      ...container.querySelectorAll("[data-select='home-bill-month'] option"),
    ].map((one) => one.textContent);
    expect(months).toEqual([
      "Aug 2026 · $142.18",
      "Jul 2026 · $142.18",
      "Jun 2026 · $142.18",
    ]);
    // B14 rule 31 — the reference is the number on the paper.
    expect(container.textContent).toContain("BL-2608-0141");
  });
  /**
   * ⚠ **`DEF-CWP-3926` — WHAT A CUSTOMER ACTUALLY READ ON THIS SCREEN.** The
   * gap list fell back to the server's `detail`, and the server writes `detail`
   * for a developer, so `CWP-022` printed module paths, a rule id and a PO date
   * onto a customer's home page under their balance. Measured in a browser on
   * 2026-09-05 against the seeded demo; every unit test was green over it,
   * because every fixture in this file passed `problems: []`.
   *
   * The two halves of the fix are the two halves of this case: a code with a
   * sentence shows the SENTENCE, and a code without one shows NOTHING — not the
   * key, not the detail, not a placeholder. The third assertion is the general
   * form and is the one worth keeping: no internal of any kind reaches a
   * customer's screen (`BR-CWP-021`, B14 rules 31 and 32).
   */
  it("DEF-CWP-3926: a named gap is the customer's sentence, and an unknown gap is silence", async () => {
    const LEAK =
      "apps.billing.selectors.issued_invoices_for_account is not published, so no bill states " +
      "its usage+base / taxes / tenant-defined / fees balances (OQ-128, BR-PAY-038, PO 2026-08-11).";
    const { container } = draw({
      ...ONE,
      problems: [
        { code: "invoice_composition_unavailable", detail: LEAK },
        { code: "a_code_no_catalogue_has_ever_heard_of", detail: LEAK },
      ],
      // ⚠ **`as unknown as` BECAUSE THE SERVER SENDS MORE THAN THE CLIENT READS,
      //    AND THAT IS THE POINT OF THIS TEST.** `PortalProblem` declares `detail`
      //    off the type so no screen can reach for it (`DEF-CWP-3926`); the wire
      //    still carries it, so the fixture still carries it, or the regression is
      //    testing a paragraph nobody would have been handed anyway.
    } as unknown as BalanceSummary);
    await screen.findByText("$142.18");
    const gaps = container.querySelector("[data-home-problems]");
    expect(gaps).not.toBeNull();
    // The one with a sentence, in the customer's words.
    expect(gaps?.textContent).toContain("We cannot yet show how a payment was split across a bill.");
    // The one without: absent entirely — one line, not two.
    expect(gaps?.querySelectorAll("li")).toHaveLength(1);
    expect(container.textContent).not.toContain("a_code_no_catalogue_has_ever_heard_of");
    expect(container.textContent).not.toContain("portal.problem.");
    // The general form: no module path, no rule id, no internal anywhere.
    expect(container.textContent).not.toContain("apps.");
    expect(container.textContent).not.toMatch(/\b(BR|OQ|DEF)-[A-Z]{0,3}-?\d{3,5}\b/);
  });

  /** Every gap unknown -> the list is not drawn at all, rather than an empty
   *  bulleted box under the balance (B14 rule 17's shape, applied to a list
   *  that has nothing to say). */
  it("DEF-CWP-3926: a gap list with nothing sayable is ABSENT, not empty", async () => {
    const { container } = draw({
      ...ONE,
      problems: [{ code: "nobody_wrote_this_one", detail: "internal prose" }],
    } as unknown as BalanceSummary);
    await screen.findByText("$142.18");
    expect(container.querySelector("[data-home-problems]")).toBeNull();
    expect(container.textContent).not.toContain("internal prose");
  });
});

/**
 * ⚠ **THESE CASES EXIST BECAUSE EVERY EXISTING ONE PASSED OVER `DEF-CWP-3965`.**
 * The Product Owner opened the live product and said *"the UI is not as per
 * agreement"*; the screen had no balance strip, no right rail, and an attention
 * panel whose entire content was the bare text `Pay $155.45`. Seventeen cases in
 * this file were green over it, because each asked whether a FIGURE was right
 * and none asked what SHAPE the page was in.
 *
 * ⚠ **THEY ARE NOT THE WHOLE GUARD AND MUST NOT BE READ AS ONE** (hard-won law
 * 6). A `jsdom` test can see that a region is in the DOM; it cannot see that it
 * RENDERS — this theme clears Tailwind's palette, so a class can be present and
 * paint nothing (`DEF-974`). `10-scripts/render-checks/def-cwp-3965-home-
 * layout.mjs` opens the built page in a real engine and measures it.
 */
describe("CWP-022 · the SHAPE the layout signs off (DEF-CWP-3965)", () => {
  const FULL: Partial<PortalHome> = {
    last_bill: {
      number: "BL-2608-0141",
      issued_on: "2026-08-26",
      due_on: "2026-09-14",
      total: "142.1800",
      currency: "USD",
      period_start: "2026-07-27",
      period_end: "2026-08-26",
    },
    last_payment: {
      amount: "138.4400",
      currency: "USD",
      paid_on: "2026-08-12",
      method: "Bank transfer",
    },
    usage: [
      {
        month: "2026-08",
        service: "water",
        unit: "gal",
        quantity: "4820.000000",
        quantity_display: "4820",
        estimated: false,
      },
    ],
    usage_series: [
      {
        month: "2026-07",
        service: "water",
        unit: "gal",
        quantity: "4090.000000",
        quantity_display: "4090",
        estimated: false,
      },
      {
        month: "2026-08",
        service: "water",
        unit: "gal",
        quantity: "4820.000000",
        quantity_display: "4820",
        estimated: false,
      },
    ],
    recent_bills: [
      {
        number: "BL-2608-0141",
        issued_on: "2026-08-26",
        due_on: "2026-09-14",
        total: "142.1800",
        currency: "USD",
        period_start: "2026-07-27",
        period_end: "2026-08-26",
        owing: "142.1800",
        state: "due",
        usage: [{ quantity_display: "4820", unit: "gal" }],
      },
    ],
    service: {
      address: { value: "1408 Elm St · A", varies: false },
      plan: { value: "Residential Standard", varies: false },
      billed: { value: "Monthly", varies: false },
      paperless: { value: true, varies: false },
    },
    identity: {
      name: { value: "Marcus Bell", varies: false },
      status: { value: "Active", varies: false },
      status_class: { value: "billable", varies: false },
      services: [
        { code: "water", name: "Water" },
        { code: "sewer", name: "Sewer" },
      ],
      equipment: ["8841-C", "W-2209"],
      phone: "••• ••• 0148",
      phone_varies: false,
      email: "m•••@example.com",
      email_varies: false,
    },
    attention: [{ kind: "pay", amount: "142.1800", currency: "USD" }],
  };

  it("opens with a KpiRow of four, the balance leading", async () => {
    const { container } = draw(ONE, FULL);
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the
    // table, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-kpi-row]")).not.toBeNull();
    const tiles = [...container.querySelectorAll("[data-kpi]")].map((n) =>
      n.getAttribute("data-kpi"),
    );
    expect(tiles).toEqual(["balance", "last-bill", "last-payment", "usage-water"]);
    // The lead variant is the brand rule down the left edge, and it is on the
    // BALANCE and on nothing else (`09-component-inventory.md` §4).
    expect(container.querySelectorAll("[data-kpi-lead]")).toHaveLength(1);
    expect(container.querySelector("[data-kpi-lead]")?.getAttribute("data-kpi")).toBe("balance");
  });

  it("the attention row is a chip, a sentence AND a button — not a bare figure", async () => {
    // ⚠ This is the defect the PO actually pointed at: the whole panel was the
    // text `Pay $155.45` and nothing else.
    const { container } = draw(ONE, FULL);
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the
    // table, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    const row = container.querySelector("[data-attention='pay']");
    expect(row?.querySelector("[data-chip='attention-pay']")).not.toBeNull();
    expect(row?.querySelector("p")?.textContent).toContain("$142.18");
    const pay = row?.querySelector("a");
    expect(pay?.textContent).toContain("Pay $142.18");
    expect(pay?.getAttribute("href")).toBe("/pine-hill/portal/pay-now");
  });

  /**
   * ⚠ **PO RULING 2026-09-08, verbatim: *"please give me drop down to select
   * last 6 months - on this - August bill · BL-2608-000077"*.** The panel was
   * a three-row table headed *RECENT BILLS*; it is ONE bill now, with the
   * chooser above it and the whole list still one click away.
   *
   * The last assertion is the one that matters and is the reason the panel
   * redraws in place rather than filtering a table under a fixed heading:
   * **every figure on it belongs to the month the heading names.**
   */
  it("the bill panel names ONE month and everything on it belongs to that month", async () => {
    const { container } = draw(ONE, FULL);
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the bill
    // panel, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    const heading = container.querySelector("[data-bill-heading]")?.textContent ?? "";
    expect(heading).toContain("Aug 2026");
    expect(heading).toContain("$142.18");
    const periodText = container.querySelector("[data-bill-period]")?.textContent ?? "";
    expect(periodText).toContain("Jul 27, 2026");
    expect(periodText).not.toContain("2026-07-27");
    // Hard rule 3 — the quantity carries its unit here too.
    expect(container.querySelector("[data-bill-usage]")?.textContent).toBe("4820 gal");
    expect(container.querySelector("[data-chip='state-BL-2608-0141']")).not.toBeNull();
    // B14 rule 15 — the two ways into the bill are icons, and they go somewhere.
    expect(
      container.querySelector("[data-bill-open='BL-2608-0141']")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/bills/BL-2608-0141");
    expect(
      container.querySelector("[data-bill-printed='BL-2608-0141']")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/bills/BL-2608-0141/document");
  });

  /**
   * ⚠ **THE ONE FAILURE MODE i18next HAS THAT NOTHING ELSE CATCHES: A MISSING
   * KEY IS RENDERED AS THE KEY** (`DEF-CWP-4940`).
   *
   * This screen deliberately borrows five of its column headings from other
   * screens' catalogue entries, because B14 rule 35 says to reuse the word the
   * product already ships rather than mint a parallel one. **The cost of
   * borrowing is that another lane's rename lands on this screen**, and it did:
   * `portal.bills.colPeriod` and `portal.bills.colUsage` were renamed and
   * deleted by the bills lane in `448776e5a`, and Home printed both key strings
   * as headings to a customer.
   *
   * **Nothing went red.** `tsc` cannot see inside a string; `G18` does see it
   * (it is the *"renders raw to a user"* count) and was already red on 21 other
   * keys that morning; and every rendering assertion in this file passed,
   * because the key IS the text in the DOM — `toContain`, `toBeInTheDocument`
   * and a browser walk all agree that something is drawn.
   *
   * So the assertion is on the SHAPE of every string the screen draws, not on
   * any one heading: **no text on Home may look like a catalogue key.** It goes
   * red on the next rename, whoever makes it, without naming a key.
   */
  it("DEF-CWP-4940 — no heading on Home is a raw catalogue key", async () => {
    const { container } = draw(ONE, FULL);
    await screen.findAllByText("$142.18");
    const headings = [...container.querySelectorAll("[data-kvlist] dt")].map(
      (dt) => dt.textContent ?? "",
    );
    expect(headings.length).toBeGreaterThan(3);
    expect(headings.filter((h) => h.startsWith("portal."))).toEqual([]);
    // …and the same question asked of the whole screen, because a heading is
    // not the only place a borrowed key can be missing.
    expect(container.textContent ?? "").not.toMatch(/portal\.[a-zA-Z]+\.[a-zA-Z]/);
  });

  /** ⚠ **A CHOOSER WITH ONE OPTION IS FURNITURE** — the wireframe says it of
   *  this very panel (*"a first bill means no chooser at all"*) and the account
   *  switcher already obeys the same rule two components away. */
  it("one bill draws NO chooser, and the bill still draws", async () => {
    const { container } = draw(ONE, FULL);
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-select='home-bill-month']")).toBeNull();
    expect(container.querySelector("[data-bill='BL-2608-0141']")).not.toBeNull();
  });

  it("the rail carries the chart and the instalments panel", async () => {
    const { container } = draw(ONE, FULL);
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the bill
    // panel, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-chart='home-water']")).not.toBeNull();
    expect(container.querySelector("[data-home-usage-door='water']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/usage",
    );
    expect(container.querySelector("[data-home-instalments]")).not.toBeNull();
  });

  /**
   * ⚠ **THE CARD THE PRODUCT OWNER ASKED FOR, 2026-09-08** — *"we are not
   * displaying account # of Customer nmae - ther eis no identifier"*, then
   * *"just show IDs not details - Equipment ... W-2209, 8841-C, F-0118 - this
   * is enough + account status"*.
   *
   * ⚠ **THE EQUIPMENT ASSERTION IS THE POINT OF THE CASE.** It asserts the
   * REFERENCES and asserts the ABSENCE of a description, because *8841-C* and
   * *Electric meter 8841-C · 5/8 inch* both contain the reference and only one
   * of them is what was asked for.
   *
   * ⚠ **AND THE MASK.** A full telephone number must never reach this screen;
   * the server masks it, and this is the assertion that says so from the
   * reader's side.
   */
  it("the account card names who, what is taken, what is fitted — and the status", async () => {
    const { container } = draw(ONE, FULL);
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-identity='name']")?.textContent).toBe("Marcus Bell");
    expect(container.querySelector("[data-identity='services']")?.textContent).toBe(
      "Water · Sewer",
    );
    const equipment = container.querySelector("[data-identity='equipment']")?.textContent ?? "";
    expect(equipment).toBe("8841-C · W-2209");
    expect(equipment).not.toContain("meter");
    // ⚠ **THE MASK, FROM THE READER'S SIDE.** The screen never receives a full
    // telephone number or e-mail address — the server masks both — so no edit
    // of this component can reveal one.
    expect(container.querySelector("[data-identity='phone']")?.textContent).toBe("••• ••• 0148");
    expect(container.querySelector("[data-identity='email']")?.textContent).toBe(
      "m•••@example.com",
    );
    expect(container.querySelector("[data-chip='account-status']")?.textContent).toBe("Active");
    expect(container.querySelector("[data-identity='plan']")?.textContent).toBe(
      "Residential Standard",
    );
    expect(container.querySelector("[data-identity='billed']")?.textContent).toBe("Monthly");
    // `BR-BIL-036` — print is the FLOOR, so paperless ADDS email and the words
    // say so rather than reading *On*, which a customer reads as *paper stopped*.
    expect(container.querySelector("[data-identity='paperless']")?.textContent).toBe(
      "Email and paper",
    );
    // ⚠ **NOT THE ADDRESS AND NOT THE ACCOUNT NUMBER** — the frame draws both
    // on the account bar one line above, and drawing them twice is the *"too
    // much content"* the Product Owner has objected to four times.
    expect(container.querySelector("[data-identity='address']")).toBeNull();
  });

  /** ⚠ **NO GOVERNMENT ID REACHES THIS SCREEN, AND THAT IS A DECISION RATHER
   *  THAN AN OMISSION.** The drawing asks for *Driving licence ••••4417*;
   *  `customers.Contact.gov_id_last4` holds four digits and nothing in the
   *  portal reads it. This case is what fires the day somebody serves one
   *  without the decision being made — a row named for it, or four bare digits
   *  on a card, both fail here. */
  it("no government id is drawn, because none is served", async () => {
    const { container } = draw(ONE, FULL);
    await screen.findAllByText("$142.18");
    const card = container.querySelector("[data-testid='home-account']");
    // ⚠ The card must BE there, or this case passes over an absent screen —
    // which is hard-won law 7's *structurally incapable of failing*.
    expect(card).not.toBeNull();
    expect(container.querySelector("[data-identity='gov-id']")).toBeNull();
    expect(card?.textContent ?? "").not.toMatch(/licence|license|passport/i);
  });

  it("a fact the accounts disagree on says so, rather than showing one of them", async () => {
    const { container } = draw(ONE, {
      ...FULL,
      service: {
        address: { value: null, varies: true },
        plan: { value: "Residential Standard", varies: false },
        billed: { value: null, varies: false },
        paperless: { value: null, varies: true },
      },
      identity: {
        ...FULL.identity!,
        phone: null,
        phone_varies: true,
        status: { value: null, varies: true },
      },
    });
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the bill
    // panel, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-identity='plan']")?.textContent).toBe(
      "Residential Standard",
    );
    expect(container.querySelector("[data-identity='paperless']")?.textContent).toBe(
      "Varies by account",
    );
    // ⚠ **ONE OF FOUR TELEPHONE NUMBERS SHOWN ALONE READS AS SETTLED**, which
    // is the whole reason `varies` is served rather than resolved.
    expect(container.querySelector("[data-identity='phone']")?.textContent).toBe(
      "Varies by account",
    );
    expect(container.querySelector("[data-chip='account-status']")?.textContent).toBe(
      "Varies by account",
    );
    // `BR-CWP-093` — a row with no answer is ABSENT, never a dash.
    expect(container.querySelector("[data-identity='billed']")).toBeNull();
  });

  /** ⚠ **A BUNDLE OLDER OR NEWER THAN ITS SERVER MUST NOT TAKE THE PAGE DOWN.**
   *  This was live for one build: the card read `identity.status_class.value`
   *  first, a server that had not been restarted sent no `identity`, and the
   *  WHOLE home page became a React error screen — balance, bill and charts
   *  gone. `tsc` and every case here passed, because the type says the block is
   *  always there and every fixture obeys the type. A real browser found it. */
  it("a payload with no account block at all draws no card, not an error screen", async () => {
    const { container } = draw(ONE, {
      ...FULL,
      identity: undefined as unknown as PortalHome["identity"],
    });
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-testid='home-account']")).toBeNull();
    // The page itself is still there — that is the whole point of the case.
    expect(container.querySelector("[data-owing]")?.textContent).toBe("$142.18");
    expect(container.querySelector("[data-home-recent-bills]")).not.toBeNull();
  });

  it("BR-CWP-093 — an account with nothing known draws NO card at all", async () => {
    const { container } = draw(ONE, {
      ...FULL,
      service: NO_SERVICE,
      identity: NO_IDENTITY,
    });
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the bill
    // panel, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-identity]")).toBeNull();
    expect(container.querySelector("[data-testid='home-account']")).toBeNull();
  });

  it("BR-CWP-073 / TC-5 — no measured service means no tile AND no empty chart", async () => {
    const { container } = draw(ONE, { ...FULL, usage: [], usage_series: [] });
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the
    // table, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    expect(container.querySelector("[data-home-usage]")).toBeNull();
    expect(container.querySelector("[data-chart]")).toBeNull();
    expect(container.querySelector("[data-chart-empty]")).toBeNull();
  });

  it("the tip slot is ABOVE the tiles, where the layout puts it", async () => {
    // ⚠ It was the LAST card on the page, which is the one place a customer
    // leaving in thirty seconds never reaches.
    // ⚠ **THE FIXTURE SAID `{ body: … }` AND THE SERVER HAS NEVER SENT THAT**
    // (`DEF-CWP-3998`). `tip_for_screen` returns `{"text", "target_screen"}`,
    // so the box rendered EMPTY for every live tip while this case passed —
    // a fixture written from the client type can only confirm the client
    // type. The text is asserted below for that reason.
    const { container } = draw(ONE, {
      ...FULL,
      tip: { text: "Water before 10am.", target_screen: "portal_home" },
    });
    // ⚠ `findAll` — `$142.18` is on the tile, in the sentence and in the
    // table, and `findByText` refuses when a string is on the page more than
    // once. That is the layout working, not a duplicate render.
    await screen.findAllByText("$142.18");
    await screen.findByText("Water before 10am.");
    // The kit's `TipBar` now, not this screen's own div (`DEF-CWP-3985`).
    const tip = container.querySelector("[data-tip-bar]");
    const strip = container.querySelector("[data-kpi-row]");
    expect(tip).not.toBeNull();
    expect(strip).not.toBeNull();
    const order = (tip as Element).compareDocumentPosition(strip as Node);
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
