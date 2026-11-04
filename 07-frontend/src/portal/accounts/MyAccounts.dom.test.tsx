// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LINE 1 AND THE FILE IS `.dom.test.tsx`, WHICH IS THE
// CONVENTION `vitest.config.ts` SETS OUT (DEF-523): the default environment is
// `node` so 200+ first-paint suites stay fast, and an interactive suite opts in
// per file. This one clicks the Owing filter, so it needs a real DOM.
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-026 (EP-CWP-06) · Screen: CWP-023
// Rules:    BR-CWP-013 (flat — no nesting, no expander, no `children`) ·
//           BR-CWP-014 (the two labels are a BILLING fact) · BR-CWP-015
//           (totalled, never merged — and nothing beside the total to press) ·
//           BR-CWP-016 (a landlord never sees a tenant's) · B14 rule 20 (one
//           table type) · rule 31 (no database id is a visible value) ·
//           rule 36 (compose the kit — the chip is `StatusPill`)
// Cases:    US-CWP-026 TC-1 (four rows and $872.82) · TC-2 (the two labels) ·
//           TC-5 (a householder gets no total) · TC-7 (the Owing filter)
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalListRequest, MyAccounts } from "../api/portalClient";

// ⚠ **A PLAIN FUNCTION REFERENCE, NOT `vi.fn()`, AND THE REASON IS THE ERROR
// CASE.** A `vi.fn()` tracks the promise each call returns so `mock.settledResults`
// can report it, and that tracking attaches to a rejected promise before the
// component's own `.catch` does — so vitest reports *read failed* as this test
// failing, with the exact message the component was supposed to swallow. The
// symptom reads like the screen not handling the error, which is the opposite of
// what is happening. Swapping the behaviour behind an ordinary function keeps the
// suite's control over what the read does and takes the spy out of the chain.
let readAccounts: () => Promise<MyAccounts> = async () => {
  throw new Error("no behaviour set");
};
/** Every request, recorded — `DEF-CWP-5747`. Typed as the wrapper's own
 *  option bag, so an assertion about `filters.group` or `year` is checked
 *  against the shape that actually travels rather than against `{}`. */
let asked: (PortalListRequest & { year?: number; accountId?: string | null })[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getMyAccounts: (request: Record<string, unknown> = {}) => {
      asked.push(request);
      return readAccounts();
    },
  };
});

const { MyAccountsView } = await import("./MyAccounts");

/** `US-CWP-026` §4 — Maria's four, exactly as the story states them. */
const LANDLORD: MyAccounts = {
  as_of: "2026-09-02",
  account_count: 4,
  // The window the server serves since `DEF-CWP-5747`. ⚠ **`count` IS WHAT THE
  // SEARCH MATCHED AND `account_count` IS THE WHOLE SET** — the second is what
  // decides whether a total and the *Owing* chip are drawn at all, and reading
  // the first for that would hide both the moment somebody typed.
  count: 4,
  page: 1,
  per: 50,
  total_owing: "872.8200",
  currency: "USD",
  show_total: true,
  problems: [],
  accounts: [
    {
      id: "a1",
      account_no: "ACC-10432-A",
      service_address: "1408 Elm St · A",
      services: [{ code: "water", name: "Water" }],
      owing: "142.1800",
      currency: "USD",
      due_on: "2026-09-14",
      state: "due",
      days_overdue: null,
      billed_to: "tenant",
      is_master: false,
    },
    {
      id: "a2",
      account_no: "ACC-10432-B",
      service_address: "1408 Elm St · B",
      services: [{ code: "water", name: "Water" }],
      owing: "0.0000",
      currency: "USD",
      due_on: null,
      state: "clear",
      days_overdue: null,
      billed_to: "tenant",
      is_master: false,
    },
    {
      id: "a3",
      account_no: "ACC-10432-C",
      service_address: "1408 Elm St · Common",
      services: [{ code: "water", name: "Water" }],
      owing: "318.0400",
      currency: "USD",
      due_on: "2026-09-14",
      state: "due",
      days_overdue: null,
      billed_to: "owner",
      is_master: true,
    },
    {
      id: "a4",
      account_no: "ACC-10519-A",
      service_address: "22 Palm Ct",
      services: [{ code: "water", name: "Water" }],
      owing: "412.6000",
      currency: "USD",
      due_on: "2026-08-14",
      state: "overdue",
      days_overdue: 19,
      billed_to: "tenant",
      is_master: false,
    },
  ],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant` PATTERN** (CLAUDE.md hard-won law 2).
 * With an `initialEntries` and no matching `<Route>`, `useParams().tenant` is
 * `undefined` and every address this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. The door assertion below could not fail without it.
 */
function draw(data: MyAccounts) {
  // ⚠ **THE STAND-IN APPLIES THE CHIP AND THE SEARCH, BECAUSE BOTH ARE THE
  // SERVER'S NOW (`DEF-CWP-5747`).** `Owing` is `?f.state=owing` and the box is
  // `?q=`; a stand-in that returned every row whatever was asked would make
  // TC-7 pass over a screen that had stopped narrowing at all — law 7's
  // *incapable of failing* shape. The predicates mirror
  // `apps/portal/selectors.MY_ACCOUNT_FILTERS` and `MY_ACCOUNT_SEARCH_FIELDS`.
  readAccounts = async () => {
    const request = asked[asked.length - 1] ?? {};
    const chip = (request.filters as Record<string, string> | undefined)?.state;
    const needle = String(request.q ?? "").toLowerCase();
    let rows = data.accounts;
    if (chip === "owing") rows = rows.filter((row) => row.state !== "clear");
    if (needle !== "") {
      rows = rows.filter(
        (row) =>
          (row.service_address ?? "").toLowerCase().includes(needle) ||
          row.account_no.toLowerCase().includes(needle) ||
          row.services.some((service) => service.name.toLowerCase().includes(needle)),
      );
    }
    // ⚠ **`account_count` DOES NOT MOVE AND `count` DOES.** The first is the
    // whole set — it decides whether a total and the chip are drawn at all —
    // and the second is what the search matched.
    return { ...data, accounts: rows, count: rows.length };
  };
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/accounts"]}>
      <Routes>
        <Route path="/:tenant/portal/accounts" element={<MyAccountsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * **THE DESKTOP TABLE HALF.**
 *
 * ⚠ **THIS SCREEN NOW DRAWS EVERY ACCOUNT TWICE — ONCE AS A TABLE ROW AND ONCE
 * AS A PHONE CARD — AND ONLY ONE IS EVER VISIBLE** (`DEF-CWP-4905`). The switch
 * is CSS (`hidden … max-md:flex` / `max-md:hidden`) and jsdom applies no CSS, so
 * an unscoped `screen.getByText("1408 Elm St · A")` finds two elements and
 * fails. Scoping is not a workaround: every assertion it wraps is ABOUT the
 * table — its rows, its chips, its filter — and saying so is what stops the
 * same query silently starting to answer with the card instead. The same shape
 * `bills/Bills.dom.test.tsx` and `usage/Equipment.dom.test.tsx` already use.
 */
function deskEl(container: HTMLElement): HTMLElement {
  return container.querySelector("[data-list='CWP-023']") as HTMLElement;
}

function desk(container: HTMLElement) {
  return within(deskEl(container));
}

/** The phone half — the stack of cards. */
function cards(container: HTMLElement) {
  return within(container.querySelector("[data-accounts-cards]") as HTMLElement);
}

describe("CWP-023 · all my accounts (US-CWP-026)", () => {
  it("DEF-CWP-3954 — the door to CWP-020, which nothing pointed at", async () => {
    // `08-screen-layouts.md` draws *+ Add an account* as a head action on this
    // page, and it is the moment somebody asks for a second one.
    const { container } = draw(LANDLORD);
    await screen.findByText("Add another account");
    const doors = [...container.querySelectorAll("a")].filter(
      (a) => a.getAttribute("href") === "/pine-hill/portal/accounts/add",
    );
    // ⚠ **EXACTLY ONE, AND THE COUNT IS THE ASSERTION** (`DEF-CWP-4905`). Two
    // lanes each added this control citing a different drawing, so the screen
    // carried the same label twice. A test that only asked *does the door
    // exist* passed on both of them.
    expect(doors).toHaveLength(1);
    expect(doors[0].textContent).toContain("Add another account");
  });

  afterEach(cleanup);

  /**
   * `DEF-CWP-4905` — at 390 the table put `BALANCE` and `STATUS` past the right
   * edge, so the two facts the screen exists to answer were behind a sideways
   * scroll. jsdom cannot measure that; what it CAN prove is that the phone half
   * exists, carries both facts from the same payload, and offers a door with a
   * WORD on it rather than a bare icon with a tooltip no phone can show.
   */
  it("the phone half carries the money, the status and a door with a word", async () => {
    const { container } = draw(LANDLORD);
    await screen.findByText("$872.82");
    expect(container.querySelectorAll("[data-account-card]")).toHaveLength(4);
    expect(cards(container).getByText("$412.60")).toBeTruthy();
    expect(cards(container).getByText("19 days overdue")).toBeTruthy();
    const open = container.querySelector("[data-card-open='a4']");
    expect(open?.textContent).toBe("Open 22 Palm Ct");
    expect(open?.getAttribute("href")).toBe("/pine-hill/portal/account");
    // The paid-up row is offered no payment, on the card as in the table.
    expect(container.querySelector("[data-card-pay='a2']")).toBeNull();
    expect(container.querySelector("[data-card-pay='a4']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/pay-now",
    );
  });

  /**
   * `DEF-CWP-4901` — `CWP-065` had ONE inbound link in the whole portal and it
   * was on `My details`. The drawing's `→ Open` is *"this property's own
   * page"*; the built eye went to `/bills`.
   */
  it("the row's eye opens THIS PROPERTY'S page, which is what the drawing draws", async () => {
    const { container } = draw(LANDLORD);
    await screen.findByText("$872.82");
    expect(container.querySelector("[data-account-open='a1']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/account",
    );
  });

  // ⚠ **WITHOUT THIS EVERY CASE AFTER THE FIRST SEES TWO SCREENS.** There is no
  // global `setupFiles` in this repo (`vitest.config.ts` says why), so Testing
  // Library's auto-cleanup never registers and each `render` stacks another
  // copy into the same document — which surfaces as *"Found multiple elements
  // with the text: $872.82"*, a failure that reads like a duplicate-render bug
  // in the SCREEN rather than a missing hook in the SUITE.

  it("TC-1 — four rows, $872.82, and four separate balances", async () => {
    const { container } = draw(LANDLORD);
    expect(await screen.findByText("$872.82")).toBeTruthy();
    expect(container.querySelectorAll("tbody tr")).toHaveLength(4);
    for (const owed of ["$142.18", "$0.00", "$318.04", "$412.60"]) {
      expect(desk(container).getByText(owed)).toBeTruthy();
    }
  });

  it("TC-1 — the total has NOTHING beside it to press (BR-CWP-015)", async () => {
    const { container } = draw(LANDLORD);
    const total = await screen.findByText("$872.82");
    const line = total.closest("[data-accounts-total]");
    expect(line).toBeTruthy();
    expect(line?.querySelector("button")).toBeNull();
    expect(line?.querySelector("a")).toBeNull();
    // ⚠ And no nesting anywhere: `BR-CWP-013`'s flat set is a DOM fact, not a
    // description. A master with children would be a table inside a table.
    expect(container.querySelectorAll("table")).toHaveLength(1);
  });

  it("TC-2 — the master reads *Billed to you as owner* and the rest do not", async () => {
    const { container } = draw(LANDLORD);
    await screen.findByText("$872.82");
    // ⚠ The counts DOUBLE now that every account is drawn on both halves, so
    // they are taken from the table rather than from the document — the same
    // fact, asked of one half instead of of two.
    expect(deskEl(container).querySelectorAll('[data-billed-to="owner"]')).toHaveLength(1);
    expect(deskEl(container).querySelectorAll('[data-billed-to="tenant"]')).toHaveLength(3);
    expect(desk(container).getByText("Billed to you as owner")).toBeTruthy();
  });

  /** ⚠ **THE NUMBER A LANDLORD READS OUT ON THE TELEPHONE.** This cell drew
   *  the address and *Tenant billed* and nothing else, while its own docstring
   *  said `account_no` *"is shown as a second line, because that is the number
   *  they will quote"* — hard-won law 1, a claimed guarantee that was not one.
   *  The wireframe gives the number a column of its own; on a phone it draws
   *  it under the address, which is what this asserts. */
  it("every row shows the account number, not only the address", async () => {
    const { container } = draw(LANDLORD);
    await screen.findByText("$872.82");
    const numbers = [...deskEl(container).querySelectorAll("[data-account-no]")].map(
      (one) => one.textContent,
    );
    expect(numbers).toEqual(["ACC-10432-A", "ACC-10432-B", "ACC-10432-C", "ACC-10519-A"]);
    // ⚠ **A DATABASE ID IS STILL NEVER THE VISIBLE VALUE** (B14 rule 31): the
    // id keys the attribute, the printed reference is the text.
    expect(container.textContent).not.toContain("acc-1");
  });

  it("TC-7 — *19 days overdue* is composed HERE from a number on the wire", async () => {
    const { container } = draw(LANDLORD);
    // The server sent `days_overdue: 19` and the word *overdue* appears in no
    // response body anywhere (B14 rule 35 — the catalogue writes the words).
    await screen.findByText("$872.82");
    expect(desk(container).getByText("19 days overdue")).toBeTruthy();
    expect(desk(container).getByText("Clear")).toBeTruthy();
  });

  it("TC-7 — the Owing filter drops the $0.00 row and keeps three", async () => {
    const user = userEvent.setup();
    const { container } = draw(LANDLORD);
    await screen.findByText("$872.82");
    await user.click(container.querySelector('[data-segmented="accounts-filter"] [data-segment="owing"]') as HTMLElement);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    // ⚠ **THE FILTER IS THE TABLE'S AND THE CARDS ARE NOT FILTERED**, which is
    // stated here rather than left to be discovered: the toolbar belongs to
    // `PortalListTable` and does not exist on the phone half, exactly as it
    // does not on `CWP-027` and `CWP-037`. So the `$0.00` row is gone from the
    // table and still on a card, and only one of the two is ever on screen.
    expect(desk(container).queryByText("$0.00")).toBeNull();
  });

  it("TC-5 — a householder gets one row and NO total line", async () => {
    const { container } = draw({
      ...LANDLORD,
      account_count: 1,
      show_total: false,
      accounts: [LANDLORD.accounts[0]],
    });
    // ⚠ Both halves draw the one account, so the figure is on screen TWICE and
    // `findByText` would throw on the ambiguity. The wait is for the read to
    // land; the assertion is about the table.
    await screen.findAllByText("$142.18");
    expect(desk(container).getByText("$142.18")).toBeTruthy();
    expect(container.querySelector("[data-accounts-total]")).toBeNull();
    // ⚠ And no filter either — two words offering a choice over one row.
    expect(container.querySelector('[data-segmented="accounts-filter"] [data-segment="owing"]')).toBeNull();
  });

  it("B14 rule 31 — the address is the visible value, never a database id", async () => {
    const { container } = draw(LANDLORD);
    await screen.findByText("$872.82");
    expect(desk(container).getByText("1408 Elm St · A")).toBeTruthy();
    for (const row of LANDLORD.accounts) {
      expect(container.textContent).not.toContain(row.id);
    }
  });

  it("says so when the read fails, rather than drawing an empty table", async () => {
    readAccounts = async () => {
      throw new Error("read failed");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/accounts"]}>
        <MyAccountsView />
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read your accounts.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
  });
  /**
   * `DEF-CWP-3926` — the same gap list as `CWP-022`'s, from the same payload,
   * so it is now the same component (`NamedGaps`, B14 rule 36). This case is
   * the WIRING half rather than the logic half: the logic is proved once on
   * Home, and what can still break here is this screen quietly drawing its own
   * list again, or passing the wrong mark and losing the list altogether
   * (hard-won law 2).
   */
  it("DEF-CWP-3926: the gap list is the customer's sentence, and nothing internal reaches it", async () => {
    const { container } = draw({
      ...LANDLORD,
      problems: [
        {
          code: "accounts_in_several_currencies",
          detail: "apps.payments.selectors.balance_for_accounts saw 2 currencies (BR-PAY-032).",
        },
        { code: "not_a_code_anybody_wrote", detail: "internal prose" },
      ],
      // ⚠ **`as unknown as` BECAUSE THE SERVER SENDS MORE THAN THE CLIENT READS,
      //    AND THAT IS THE POINT OF THIS TEST.** `PortalProblem` declares `detail`
      //    off the type so no screen can reach for it (`DEF-CWP-3926`); the wire
      //    still carries it, so the fixture still carries it, or the regression is
      //    testing a paragraph nobody would have been handed anyway.
    } as unknown as MyAccounts);
    await screen.findByText("$872.82");
    const gaps = container.querySelector("[data-accounts-problems]");
    expect(gaps).not.toBeNull();
    expect(gaps?.textContent).toContain("Your accounts use different currencies");
    expect(gaps?.querySelectorAll("li")).toHaveLength(1);
    expect(container.textContent).not.toContain("apps.");
    expect(container.textContent).not.toContain("internal prose");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-5747` — THE PAGE, THE SEARCH, THE CHIP AND THE SORT ARE THE
// SERVER'S. `BR-CWP-016` is untouched: every row is still built from the
// session's own flat account set, so there is no query here for a page or a
// sort to widen.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CWP-5747 · the accounts list asks the server for its page", () => {
  afterEach(() => {
    cleanup();
    asked = [];
  });

  it("asks for page 1 of fifty on the first render", async () => {
    draw(LANDLORD);
    await screen.findByTestId("my-accounts");
    expect(asked[0].page).toBe(1);
    expect(asked[0].per).toBe(50);
  });

  it("sends what was typed as `q` and goes back to page 1", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      draw(LANDLORD);
      await screen.findByTestId("my-accounts");
      fireEvent.change(screen.getByPlaceholderText(/search/i), {
        target: { value: "Palm" },
      });
      await vi.advanceTimersByTimeAsync(400);
      const last = asked[asked.length - 1];
      expect(last.q).toBe("Palm");
      expect(last.page).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("sends the Owing chip as a filter rather than narrowing what arrived", async () => {
    draw(LANDLORD);
    await screen.findByTestId("my-accounts");
    fireEvent.click(document.querySelector("[data-segment='owing']") as Element);
    expect(asked[asked.length - 1].filters).toMatchObject({ state: "owing" });
  });
});
