// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-031 (EP-CWP-06) · Screen: CWP-065
// Rules:    BR-CWP-049 (the deposit is shown while it is held) · BR-CWP-052
//           (⚠ the credit tier never appears) · BR-CWP-053 (the exemption's
//           expiry and its reminder) · B14 rule 17 (an absence is nothing at
//           all, never a $0.00)
// Cases:    US-CWP-031 TC-1 (the figure and the date) · TC-2 (not money off a
//           bill) · TC-5 (the exemption) · TC-7 (nothing internal on screen) ·
//           TC-8 (no deposit ⇒ no panel) · and the interest the engine cannot
//           work out, which must be words rather than a zero
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { AccountBalance, AccountSummary } from "../api/portalClient";

// A plain function, not `vi.fn()` — a recording stand-in notices a rejected
// promise before the screen's own error handling does and reports it as a
// crash. Same reasoning as `MyAccounts.dom.test.tsx`.
let readSummary: () => Promise<AccountSummary> = async () => {
  throw new Error("no behaviour set");
};
/** ⚠ **THE SECOND READ IS MOCKED TOO, AND IT HAS TO BE.** Left real it calls
 *  a server that is not there, rejects, and the screen quietly draws no money
 *  strip — so a case asserting the strip would fail for a reason that has
 *  nothing to do with the screen, and a case asserting its ABSENCE would pass
 *  no matter what the code did. */
let readBalance: () => Promise<AccountBalance> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getAccountSummary: () => readSummary(),
    getAccountBalance: () => readBalance(),
  };
});

const { YourAccountView } = await import("./YourAccount");

const WITH_DEPOSIT: AccountSummary = {
  account_id: "a1",
  opened_on: "2021-03-04",
  deposit: {
    held: "150.0000",
    taken_on: "2021-03-04",
    interest: "3.5000",
    currency: "USD",
    returns_at_closing: true,
    is_money_off_a_bill: false,
  },
  services: [
    { code: "water", name: "Water", since: "2021-03-04" },
    { code: "trash", name: "Trash", since: "2024-06-01" },
  ],
  billing: {
    current: { name: "Residential Standard", since: "2026-01-01" },
    before: [{ name: "Residential Basic", from: "2021-03-04", to: "2025-12-31" }],
  },
  tax_exemption: { until: "2027-03-31", certificate_on_file: true, reminder_days_before: 30 },
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant` PATTERN** (CLAUDE.md hard-won law 2).
 * With an `initialEntries` and no matching `<Route>`, `useParams().tenant` is
 * `undefined` and every address this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. The door assertion below could not fail without it.
 */
const OWING: AccountBalance = {
  account_id: "a1",
  owing: "191.0000",
  bills_open: "191.0000",
  credit_held: "0.0000",
  currency: "USD",
  due_on: "2026-08-22",
  open_bill_count: 1,
  problems: [],
};

function draw(data: AccountSummary, balance: AccountBalance | "unreadable" = OWING) {
  readSummary = async () => data;
  readBalance =
    balance === "unreadable"
      ? async () => {
          throw new Error("the balance could not be read");
        }
      : async () => balance;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/account"]}>
      <Routes>
        <Route path="/:tenant/portal/account" element={<YourAccountView accountId="a1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-065 · your account (US-CWP-031)", () => {
  it("DEF-CWP-3954 — the door to CWP-032, in the panel that is always drawn", async () => {
    // ⚠ In HOW YOU ARE BILLED rather than a card of its own: the deposit and
    // the tax panels are absent on most accounts, and a door that comes and
    // goes is a door nobody learns.
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText("Your final bill");
    expect(
      container.querySelector("[data-where-next='your-account'] a")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/final-bill");
  });

  /** ⚠ **THE SCREEN ABOUT ONE PROPERTY DID NOT SAY WHAT THAT PROPERTY OWED.**
   *  The captured wireframe puts *Amount due · $191.00 · Due Aug 22* second
   *  only to the address; a landlord opening this page holds exactly that
   *  question about exactly this account, and had to change the switcher and
   *  go back to Home to answer it. */
  it("the amount due for THIS account is on the page, with its date", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText("$191.00");
    expect(container.querySelector("[data-account-owing]")?.textContent).toBe("$191.00");
    expect(container.querySelector("[data-account-due]")?.textContent).toContain("Aug 22, 2026");
    // ⚠ **THE HUMAN DATE, AND THE ISO ONE ASSERTED ABSENT** — the same call
    // TC-1 makes one panel down.
    expect(container.querySelector("[data-account-due]")?.textContent).not.toContain("2026-08-22");
  });

  /** ⚠ **ABSENT, NEVER `$0.00`.** A zero here reads as *you owe us nothing*,
   *  which is a different claim from *we could not look* — the same call
   *  `US-CWP-031` TC-8 makes about the deposit. */
  it("a balance that cannot be read draws NO strip, and the rest of the page stands", async () => {
    const { container } = draw(WITH_DEPOSIT, "unreadable");
    await screen.findByText(/\$150\.00/);
    expect(container.querySelector("[data-account-owing]")).toBeNull();
    expect(container.textContent).not.toContain("$0.00");
    expect(container.querySelector("[data-testid='your-account-deposit']")).not.toBeNull();
  });

  /** ⚠ **FIVE DOORS, EACH TO A ROUTED ADDRESS.** The page offered two, and
   *  both of them are ENDS — the final bill and stopping service. This screen
   *  is where somebody holding several properties arrives to ask a question
   *  about one of them, and the next thing they want is one of these five. */
  // ⚠ SIX SINCE 2026-10-02 — `/property` (`CWP-078`, the property statement)
  // joined: it had been routed since 2026-09-27 with no door anywhere
  // (`DEF-CWP-9131`), and this account's page is where it belongs.
  it("the Go to list opens the six places this account leads", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText(/\$150\.00/);
    const doors = [
      ...container.querySelectorAll("[data-where-next='your-account-go-to'] a"),
    ].map((one) => one.getAttribute("href"));
    expect(doors).toEqual([
      "/pine-hill/portal/bills",
      "/pine-hill/portal/usage",
      "/pine-hill/portal/equipment",
      "/pine-hill/portal/requests",
      "/pine-hill/portal/documents",
      "/pine-hill/portal/property",
    ]);
  });

  it("TC-1 — the deposit says how much and since when", async () => {
    // ⚠ Scoped to the deposit LINE, not the page: `2021-03-04` is also the day
    // water started, and a page-wide match found both and could not tell which
    // panel it was reading. An assertion that cannot say where it looked is
    // one that passes for the wrong reason later.
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText(/\$150\.00/);
    const held = container.querySelector("[data-deposit-held]")?.textContent ?? "";
    expect(held).toContain("$150.00");
    // ⚠ **THE HUMAN DATE, AND THE ISO ONE ASSERTED ABSENT** (`DEF-CWP-4131`).
    // This read `toContain("2021-03-04")` and therefore PASSED ON THE DEFECT —
    // the screen printed a machine date to a customer and the one test that
    // touched it agreed. Asserting the absence too is what stops the next
    // "simplification" putting the raw value back with the suite still green.
    expect(held).toContain("Mar 4, 2021");
    expect(held).not.toContain("2021-03-04");
    expect(container.querySelector("[data-deposit-interest]")?.textContent).toContain("$3.50");
  });

  it("TC-2 — and says it is NOT money off a bill", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText(/\$150\.00/);
    expect(container.querySelector("[data-deposit-not-credit]")?.textContent).toContain(
      "not money off a bill",
    );
  });

  it("an interest the engine cannot work out is WORDS, never a zero", async () => {
    // ⚠ The signed accrual answers null when it cannot compute, and the
    // settlement that pays this money out fails closed on the same value. A
    // `$0.00` here would be a figure disagreeing with the final bill.
    const { container } = draw({
      ...WITH_DEPOSIT,
      deposit: { ...WITH_DEPOSIT.deposit!, interest: null },
    });
    await screen.findByText(/\$150\.00/);
    const line = container.querySelector("[data-deposit-interest]");
    expect(line?.textContent).toContain("not worked out yet");
    expect(line?.textContent).not.toContain("$0.00");
  });

  it("TC-8 — no deposit means NO panel, not a $0.00", async () => {
    const { container } = draw({ ...WITH_DEPOSIT, deposit: null });
    // ⚠ The plan line reads its date like every other date on this screen
    // now (`DEF-CWP-4131`) — a customer is told *since Jan 1, 2026*, not
    // *since 2026-01-01*.
    await screen.findByText("Residential Standard, since Jan 1, 2026");
    expect(container.querySelector("[data-deposit-held]")).toBeNull();
    expect(screen.queryByText(/\$0\.00/)).toBeNull();
  });

  it("TC-3/TC-4 — services carry the utility's own word, and the plan its history", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText(/\$150\.00/);
    expect(screen.getByText("Water")).toBeTruthy();
    expect(screen.getByText("Trash")).toBeTruthy();
    expect(container.querySelector("[data-plan-current]")?.textContent).toContain(
      "Residential Standard",
    );
    expect(container.querySelector("[data-plan-before]")?.textContent).toContain(
      "Residential Basic",
    );
  });

  it("TC-5 — the exemption shows its expiry AND that a reminder comes", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText(/\$150\.00/);
    const untilText = container.querySelector("[data-tax-until]")?.textContent ?? "";
    expect(untilText).toContain("Mar 31, 2027");
    expect(untilText).not.toContain("2027-03-31");
    expect(container.querySelector("[data-tax-reminder]")?.textContent).toContain("month before");
  });

  it("TC-7 — nothing internal is on the page", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText(/\$150\.00/);
    for (const forbidden of ["credit_tier", "match_tier", "match_basis", "B2"]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });

  it("D9 — the standing facts are in a RIGHT-HAND COLUMN, not four cards down one", async () => {
    // ⚠ `DEF-CWP-3984`. This screen composed `Card`, `KVList` and
    // `SectionTitle` and nothing else, so the tax panel, the *send a new
    // certificate* button and *when this account opened* had nowhere to be.
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText("Your services");

    const rail = container.querySelector("[data-screen='CWP-065'] [data-twocol-rail]");
    expect(rail, "CWP-065 draws no second column").not.toBeNull();
    // ⚠ Asserted INSIDE the rail, not merely present on the page — that is the
    // difference between "the panel exists" and "the panel is where the
    // drawing puts it", and the whole point of the row.
    expect(rail?.querySelector("[data-testid='your-account-tax']")).not.toBeNull();
    expect(rail?.querySelector("[data-testid='your-account-this']")).not.toBeNull();
    // And the main column still holds what belongs to it.
    const main = container.querySelector("[data-screen='CWP-065'] [data-twocol-main]");
    expect(main?.querySelector("[data-testid='your-account-billing']")).not.toBeNull();
    expect(main?.querySelector("[data-testid='your-account-tax']")).toBeNull();
  });

  it("D9 — the rail carries the expiry, the certificate and when the account opened", async () => {
    const { container } = draw(WITH_DEPOSIT);
    await screen.findByText("Your services");
    expect(container.querySelector("[data-tax-until] [data-kv='runs-out']")?.textContent).toContain(
      "Mar 31, 2027",
    );
    expect(container.querySelector("[data-tax-until] [data-kv='on-file']")).not.toBeNull();
    expect(container.querySelector("[data-opened-on] [data-kv='opened']")).not.toBeNull();
    // Held with its reason visible, never a live-looking dead button
    // (hard-won law 2's mirror). Its reason is a RULING — US-CWP-064's signed
    // deferral of consumer upload — so it cannot rot the way a hold waiting on
    // a screen does.
    expect(container.querySelector("[data-held='true']")?.textContent).toContain(
      "Mail or bring it in",
    );
  });

  it("DEF-CWP-9795 — a per-tax certificate shows the tax it removes and when it runs out", async () => {
    // Ruling (A) 2026-10-05: a certificate leaves the blanket flag false, so
    // M5's church (City of Cedar Ford utility tax, to 12/31/2028) had no panel.
    const { container } = draw({
      ...WITH_DEPOSIT,
      tax_exemption: {
        until: null,
        certificate_on_file: true,
        reminder_days_before: 30,
        taxes: [{ tax: "City of Cedar Ford utility tax", until: "2028-12-31" }],
      },
    });
    await screen.findByText("Your services");
    const panel = container.querySelector("[data-testid='your-account-tax']");
    expect(panel, "a certificate-only account shows no exemption").not.toBeNull();
    expect(panel?.querySelector("[data-kv='from-0']")?.textContent).toContain(
      "Exempt fromCity of Cedar Ford utility tax",
    );
    expect(panel?.querySelector("[data-kv='runs-out']")?.textContent).toContain("Dec 31, 2028");
    expect(panel?.textContent).not.toContain("—");
  });

  it("D9 — no exemption means no tax panel at all, and the rail still draws", async () => {
    // `BR-CWP-093`: most accounts hold no exemption, and a *Tax exempt* panel
    // saying *not exempt* is a fact nobody asked for.
    const { container } = draw({ ...WITH_DEPOSIT, tax_exemption: null });
    await screen.findByText("Your services");
    expect(container.querySelector("[data-testid='your-account-tax']")).toBeNull();
    expect(container.querySelector("[data-testid='your-account-this']")).not.toBeNull();
  });

  it("says so when the read fails, rather than drawing empty panels", async () => {
    readSummary = async () => {
      throw new Error("read failed");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/account"]}>
        <YourAccountView accountId="a1" />
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not read your account.")).toBeTruthy();
    expect(container.querySelector("[data-deposit-held]")).toBeNull();
  });
});
