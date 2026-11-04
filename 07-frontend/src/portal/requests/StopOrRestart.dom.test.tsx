// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-062 (EP-CWP-11) · Screen: CWP-052
// Rules:    BR-CWP-080 (the account STAYS OPEN and standing charges keep
//           running) · BR-CWP-081 (both figures, and the cheaper option named)
//           · BR-CWP-056 (held WITH its reason) · B14 rule 33 · rule 35
// Cases:    TC-1 the box · TC-2 `$92.50` against `$335.00` → stopping ·
//           TC-3 `$351.50` against `$335.00` → closing · TC-4 the phrase *the
//           account stays open* is present · TC-5 restart before stop refused
//           · TC-8 no standing charge says so rather than showing `$0.00`
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalStopOrRestart } from "../api/portalClient";

let readComparison: () => Promise<PortalStopOrRestart> = async () => {
  throw new Error("no behaviour set");
};
/** Every body `POST …/stop-or-restart/ask` was called with, this run. */
let asked: Record<string, unknown>[] = [];
/** What `GET /portal/my-details` answers. `phone` is the field that decides
 *  whether the commit is even offered — see `applicant_phone` below. */
let MY_DETAILS: { legal_name: string | null; email: string | null; phone: string | null } = {
  legal_name: "Ana Alvarez",
  email: "ana@example.test",
  phone: "(512) 555-0134",
};
const sendAsk: () => Promise<{
  reference: string;
  supply_stopped: boolean;
  account_stays_open: boolean;
}> = async () => ({ reference: "SR-26-0060", supply_stopped: false, account_stays_open: true });

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getStopOrRestart: () => readComparison(),
    askToStopOrRestart: (_id: string, body: Record<string, unknown>) => {
      asked.push(body);
      return sendAsk();
    },
    // The contact this login already has on file, prefilled into the check
    // step's boxes — see `applicant_phone` below.
    getMyDetails: async () => MY_DETAILS,
  };
});

const { StopOrRestartView } = await import("./StopOrRestart");

/** `US-CWP-062` §4's own figures: five months at `$18.50` against `$185.00`
 *  plus a `$150.00` deposit. */
const FIVE_MONTHS: PortalStopOrRestart = {
  stop_from: "2026-11-01",
  start_again: "2027-04-01",
  months: 5,
  account_stays_open: true,
  standing_charge_monthly: "18.5000",
  standing_charge_unavailable: null,
  cost_of_stopping: "92.5000",
  connection_fee: "185.0000",
  new_deposit: "150.0000",
  cost_of_closing: "335.0000",
  cheaper: "stopping",
  no_verdict: null,
  currency: "USD",
  services: [{ code: "water", name: "Water", since: "2026-01-05" }],
};

/** TC-3 — nineteen months is the first that crosses `$335.00 ÷ $18.50 = 18.1`. */
const NINETEEN_MONTHS: PortalStopOrRestart = {
  ...FIVE_MONTHS,
  start_again: "2028-06-01",
  months: 19,
  cost_of_stopping: "351.5000",
  cheaper: "closing",
};

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/stop-or-restart"]}>
      <Routes>
        <Route
          path="/:tenant/portal/stop-or-restart"
          element={<StopOrRestartView accountId="acc-1" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * ⚠ **STOPPING IS A JOURNEY NOW, SO THE DATES ARE ON STEP 2 (`CR-085` task
 * (c)).** The screen was one card — two dates, a reason and a danger commit,
 * with no read-back between the typing and the press. The wireframes draw four
 * steps and the PO ruled stop gets *"seperate screens"* of its own. Step 1 asks
 * whether the customer is coming back, which is what decides whether a restart
 * date is asked for at all.
 */
function pickDates(stop = "2026-11-01", start = "2027-04-01") {
  fireEvent.click(screen.getByText("Continue →"));
  fireEvent.change(screen.getByLabelText(/Stop from/), { target: { value: stop } });
  if (start) {
    fireEvent.change(screen.getByLabelText(/Start again/), { target: { value: start } });
  }
}

/** On to the read-back, where the commit lives. */
function reachCheck() {
  fireEvent.click(screen.getByText("Continue →"));
}

afterEach(cleanup);

beforeEach(() => {
  asked = [];
  MY_DETAILS = {
    legal_name: "Ana Alvarez",
    email: "ana@example.test",
    phone: "(512) 555-0134",
  };
});

describe("CWP-052 · stop or restart (US-CWP-062)", () => {
  it("TC-1/TC-4 · the box says the supply goes off and THE ACCOUNT STAYS OPEN", async () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    pickDates();
    await waitFor(() =>
      expect(container.querySelector('[data-consequence-code="charges_run"]')).not.toBeNull(),
    );
    // ⚠ TC-4 asserts THE PHRASE, because a screen that stopped saying it would
    // let a customer believe a stopped supply stops the bill.
    expect(
      container.querySelector('[data-consequence-code="stays_open"]')?.textContent,
    ).toBe("The account stays open.");
    expect(
      container.querySelector('[data-consequence-code="charges_run"]')?.textContent,
    ).toBe("Standing charges keep running — about $18.50 a month.");
  });

  it("TC-2 · $92.50 against $335.00, and the screen says STOPPING is cheaper", async () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    pickDates();
    expect(await screen.findByText("$92.50")).toBeInTheDocument();
    expect(screen.getByText("$185.00")).toBeInTheDocument();
    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(container.querySelector('[data-total="closing"]')?.textContent).toContain("$335.00");
    expect(container.querySelector("[data-verdict]")?.getAttribute("data-verdict")).toBe(
      "stopping",
    );
    expect(screen.getByText("For this property, stopping is cheaper.")).toBeInTheDocument();
  });

  it("TC-3 · nineteen months is $351.50 and the verdict FLIPS to closing", async () => {
    readComparison = async () => NINETEEN_MONTHS;
    const { container } = draw();
    pickDates("2026-11-01", "2028-06-01");
    expect(await screen.findByText("$351.50")).toBeInTheDocument();
    expect(container.querySelector("[data-verdict]")?.getAttribute("data-verdict")).toBe(
      "closing",
    );
    expect(
      screen.getByText("For this long, closing the account is cheaper."),
    ).toBeInTheDocument();
    // ⚠ The screen must not be able to say both, which is what a hardcoded
    // sentence would eventually do.
    expect(screen.queryByText("For this property, stopping is cheaper.")).toBeNull();
  });

  it("TC-5 · a restart before the stop is refused on the field, not the page", async () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    pickDates("2026-11-01", "2026-10-01");
    await waitFor(() =>
      expect(container.querySelector('[data-field-error="start_again"]')).not.toBeNull(),
    );
    expect(
      container.querySelector('[data-field-error="start_again"]')?.textContent,
    ).toBe("This is before the stop date.");
    // The commit is HELD while the dates disagree — never live-but-inert.
    const commit = container.querySelector("button[disabled]");
    expect(commit).not.toBeNull();
  });

  it("TC-8 · no standing charge SAYS SO rather than showing $0.00 as a saving", async () => {
    readComparison = async () => ({
      ...FIVE_MONTHS,
      standing_charge_monthly: null,
      standing_charge_unavailable: "no_standing_charge_on_this_plan",
      cost_of_stopping: null,
      cheaper: null,
      no_verdict: "no_standing_charge",
    });
    const { container } = draw();
    pickDates();
    await waitFor(() =>
      expect(container.querySelector("[data-compare-unavailable]")).not.toBeNull(),
    );
    expect(
      screen.getByText("We cannot work this comparison out for your property."),
    ).toBeInTheDocument();
    // ⚠ NOT A ZERO ANYWHERE, and no verdict either way.
    expect(container.textContent).not.toContain("$0.00");
    expect(container.querySelector("[data-verdict]")).toBeNull();
    // The consequence box still warns that charges run — it just cannot say
    // how much, which is a different sentence from *they are nothing*.
    expect(
      container.querySelector('[data-consequence-code="charges_run"]')?.textContent,
    ).toBe("Standing charges keep running. We cannot say how much a month.");
  });

  it("the confirmation repeats that nothing has been turned off", async () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    pickDates();
    await screen.findByText("$92.50");
    reachCheck();
    fireEvent.click(await screen.findByText("Request this ✓"));
    expect(await screen.findByText("Your reference is SR-26-0060.")).toBeInTheDocument();
    expect(container.querySelector("[data-stop-still-open]")?.textContent).toBe(
      "Nothing has been turned off yet, and the account stays open.",
    );
  });

  it("the panel is a sentence, not a table of dashes, before any date is given", () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    fireEvent.click(screen.getByText("Continue →"));
    expect(container.querySelector("[data-compare-waiting]")).not.toBeNull();
    expect(container.querySelector("[data-kvlist]")).toBeNull();
    expect(container.querySelector("[data-verdict]")).toBeNull();
  });
});

/**
 * ⚠ **THE JOURNEY, AND THE REQUEST THAT COULD NEVER SUCCEED — `CR-085` task
 * (c).** Every case below was watched fail against the one-card screen before
 * it was written green (hard-won law 7).
 */
describe("CWP-052 · the stop journey, and the phone it never sent", () => {
  it("opens on WHAT YOU NEED — step 1 of 3 — and asks nothing about dates yet", () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    expect(container.querySelector('[data-step="what"]')).not.toBeNull();
    expect(
      container.querySelector('[data-stepper] [data-state="current"]')?.getAttribute("data-step"),
    ).toBe("1");
    expect(screen.queryByLabelText(/Stop from/)).toBeNull();
  });

  it("a customer with no date to come back on is not asked for one", () => {
    readComparison = async () => FIVE_MONTHS;
    draw();
    fireEvent.click(screen.getByLabelText(/Not yet, I have no date/));
    fireEvent.click(screen.getByText("Continue →"));
    expect(screen.getByLabelText(/Stop from/)).toBeInTheDocument();
    // ⚠ A box for a date the customer has just said they do not have is the
    // screen not listening.
    expect(screen.queryByLabelText(/Start again/)).toBeNull();
  });

  it("the read-back comes BEFORE the commit, and names what will happen", async () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    pickDates();
    await screen.findByText("$92.50");
    // The commit is nowhere near the date boxes — that is the whole point.
    expect(screen.queryByText("Request this ✓")).toBeNull();
    reachCheck();
    expect(container.querySelector('[data-kv="last_day"] dd')?.textContent).toBe("2026-11-01");
    expect(container.querySelector('[data-consequence-code="stays_open"]')).not.toBeNull();
    expect(screen.getByText("Request this ✓")).toBeInTheDocument();
  });

  it("B14 rule 6 · the commit that turns a supply off is the DANGER tier", async () => {
    readComparison = async () => FIVE_MONTHS;
    const { container } = draw();
    pickDates();
    await screen.findByText("$92.50");
    reachCheck();
    // ⚠ `08-screen-layouts.md` CWP-052 draws it as `Button(danger)` and calls
    // it the *"second danger-tier commit"*; this file's own docstring has
    // claimed the danger tier since it was written, and the DOM measured
    // `primary` — hard-won law 1 exactly.
    expect(
      container.querySelector('[data-testid="stop-check"] [data-variant="danger"]')?.textContent,
    ).toContain("Request this");
  });

  it("the request CARRIES A PHONE, which is why it used to be refused", async () => {
    readComparison = async () => FIVE_MONTHS;
    draw();
    pickDates();
    await screen.findByText("$92.50");
    reachCheck();
    fireEvent.click(await screen.findByText("Request this ✓"));
    await waitFor(() => expect(asked).toHaveLength(1));
    // ⚠ `create_from_portal` REQUIRES `applicant_phone` — *"a promise to ring
    // needs a way to ring"* — and this screen sent a stop date, a restart date
    // and a reason. Every press answered 422 VAL-001 `applicant_phone`, on a
    // route that had no door in the portal, so nobody had ever reached it.
    expect(asked[0].phone).toBe("(512) 555-0134");
  });

  it("and the commit is held, with its reason, when there is no phone to send", async () => {
    readComparison = async () => FIVE_MONTHS;
    MY_DETAILS = { legal_name: null, email: null, phone: null };
    const { container } = draw();
    pickDates();
    await screen.findByText("$92.50");
    reachCheck();
    const commit = await waitFor(() => {
      const found = container.querySelector('[data-testid="stop-check"] [data-variant="danger"]');
      expect(found).not.toBeNull();
      return found as HTMLButtonElement;
    });
    // BR-CWP-056 — disabled WITH the reason, never a vanished control.
    expect(commit.disabled).toBe(true);
    expect(commit.getAttribute("title")).toBe("We need a phone number");
  });
});
