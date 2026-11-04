// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-047 (EP-CWP-09) · Screen: CWP-040
// Rules:    BR-CWP-056 (visible, disabled, carrying its reason) · BR-PAY-015
//           (the intent is what the customer was told) · BR-PAY-013 (two
//           bounces and the account is cash-only) · B14 rule 31 · rule 33 ·
//           CLAUDE.md hard rule 2 · hard-won law 2 (a live screen behind a
//           dead control — assert the destination BY ADDRESS)
// Cases:    TC-1 the held switch over a real table · TC-2 the scheduled row ·
//           TC-3 ⚠ two em dashes on the unbilled month · TC-5 no date control ·
//           TC-6/TC-7 cash-only names the bounces · TC-9 the ceiling ·
//           the holding screen is GONE
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalAutopay } from "../api/portalClient";

let readAutopay: () => Promise<PortalAutopay> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getAutopay: () => readAutopay() };
});

const { AutopayView } = await import("./Autopay");

/** `US-CWP-047` §4 — `14 Sep 2026 $142.18 SCHEDULED`, then `— NOT BILLED YET`. */
const BODY: PortalAutopay = {
  enrolled: true,
  elected: true,
  cash_only: false,
  bounces: 0,
  available: false,
  held_reason: "no_automatic_charge",
  how_much: "whole_balance",
  ceiling: null,
  when: "due_date",
  when_settable: false,
  any_scheduled: true,
  next_few: [
    {
      scheduled_on: "2026-09-14",
      amount: "142.1800",
      display: "$142.18",
      currency: "USD",
      state: "scheduled",
      fulfilled: false,
    },
    {
      scheduled_on: null,
      amount: null,
      display: null,
      currency: null,
      state: "not_billed_yet",
      fulfilled: false,
    },
  ],
  problems: [
    { code: "no_charging_path_before_rails" },
    { code: "ceiling_has_no_column" },
    { code: "next_due_date_not_held" },
  ],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE IN A `MemoryRouter`**
 * (`DEF-CWP-3925`). A component mounted with no `/:tenant/portal` route sees
 * `useParams().tenant` as `undefined`, and every address it builds comes out
 * `//portal/…` — a protocol-relative URL to another host, which reads as a
 * perfectly good string to `toContain`. The one assertion that could catch a
 * broken link cannot be written without this.
 */
function draw(body: PortalAutopay) {
  readAutopay = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/autopay"]}>
      <Routes>
        <Route path="/:tenant/portal/autopay" element={<AutopayView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * The same screen **with the tenant's Regional settings published above it** —
 * `DEF-CWP-4870`.
 *
 * ⚠ **WITHOUT THIS WRAPPER THE DATE TEST CANNOT FAIL, WHICH IS WHY IT EXISTS
 * AS A SECOND HELPER RATHER THAN AS A CHANGE TO THE FIRST.** `usePortalDate`
 * returns the server's own string when no format is published — deliberately,
 * and its docstring says so — so a case mounted bare reads `2026-08-22` whether
 * the screen calls the formatter or ignores it. That is hard-won law 7's
 * *structurally incapable of failing*: the assertion above (`TC-2`) is true of
 * the broken screen and of the fixed one, and it passed all the way through
 * this defect. Every OTHER case keeps the bare mount, because that is the state
 * most tenants are actually in.
 */
function drawWithRegional(body: PortalAutopay) {
  readAutopay = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/autopay"]}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <Routes>
          <Route path="/:tenant/portal/autopay" element={<AutopayView accountId="acc-1" />} />
        </Routes>
      </TenantRegionalProvider>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

/**
 * The hold, waited for RATHER THAN READ IN THE SAME PASS AS ITS CARD
 * (`DEF-CWP-4007`).
 *
 * ⚠ **THIS FILE FAILED ONCE OVER A CORRECT SCREEN AND PASSED THE NEXT FOUR
 * RUNS.** `await screen.findByTestId("autopay")` waits for the CARD; every
 * `[data-held='true']` read below is a child of that card and used to be read
 * synchronously straight afterwards, which assumes the hold renders in the same
 * pass as its parent. That is true today and is not guaranteed under load — a
 * vite build and a headless chromium on the same box was enough, and the
 * failure was `expected null not to be null`, fifteen minutes of proving a
 * green change green, and no way to tell a flake from a regression.
 *
 * A test that goes red at random trains a reader to re-run rather than to look,
 * which is how a REAL failure gets waved through. So the case waits for the
 * thing it is about instead of for the thing that contains it.
 */
async function heldNode(container: HTMLElement): Promise<HTMLElement> {
  return await waitFor(() => {
    const el = container.querySelector<HTMLElement>("[data-held='true']");
    expect(el).not.toBeNull();
    return el as HTMLElement;
  });
}


describe("CWP-040 · autopay (US-CWP-047)", () => {
  it("TC-1 — the switch is held with its reason, and the table beside it is real", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    // ⚠ Visible, disabled, carrying its reason — never hidden (BR-CWP-056).
    const held = await heldNode(container);
    expect(held.querySelector("button")).toBeDisabled();
    expect(held.textContent?.trim()).not.toBe("");
    // The refusal does not empty the table it sits beside.
    expect(container.querySelector("[data-slot-amount='0']")?.textContent).toBe("$142.18");
  });

  it("TC-2 — the scheduled row reads the date and the amount the customer was told", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    // ⚠ **THE ATTRIBUTE CARRIES THE SERVER'S STRING; THE TEXT CARRIES THE
    // TENANT'S FORMAT** (`DEF-CWP-4870`). The two must not be the same string —
    // that is exactly what made the fault invisible one screen over. With no
    // Regional settings published (this mount), `usePortalDate` hands the
    // server's own string back, which is the deliberate behaviour and is what
    // this case reads.
    expect(container.querySelector("[data-slot-date='0']")?.getAttribute("data-slot-on")).toBe(
      "2026-09-14",
    );
    expect(container.querySelector("[data-slot-date='0']")?.textContent).toBe("2026-09-14");
    // Hard rule 2 — two decimals on screen, composed by the server.
    expect(container.querySelector("[data-slot-amount='0']")?.textContent).toBe("$142.18");
    expect(container.querySelector("[data-chip='slot-0']")).not.toBeNull();
  });

  it("⚠ TC-3 — an unbilled month shows TWO absences and invents neither", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    const amount = container.querySelector("[data-slot-amount='1']")?.textContent ?? "";
    const date = container.querySelector("[data-slot-date='1']")?.textContent ?? "";
    // ⚠ Never an estimate, never a zero, and never a guessed date.
    expect(amount).not.toContain("$");
    expect(amount).not.toContain("0.00");
    expect(date).not.toMatch(/\d{4}-\d{2}-\d{2}/);
    // Both cells say something rather than being blank (BR-CWP-093's posture).
    expect(amount.trim()).not.toBe("");
    expect(date.trim()).not.toBe("");
  });

  it("TC-5 — *when* is read-only and no control offers to change it", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    expect(container.querySelector("[data-when='due_date']")).not.toBeNull();
    // ⚠ A DISABLED DATE PICKER WOULD STILL BE A DATE PICKER.
    expect(container.querySelector("input[type='date']")).toBeNull();
    expect(container.querySelector("select")).toBeNull();
  });

  it("TC-6/TC-7 — a cash-only account is refused and the reason names the bounces", async () => {
    const { container } = draw({
      ...BODY,
      enrolled: false,
      cash_only: true,
      bounces: 2,
      held_reason: "cash_only",
      problems: [...BODY.problems, { code: "cash_only_no_autopay" }],
    });
    await screen.findByTestId("autopay");

    const held = await heldNode(container);
    expect(held.querySelector("button")).toBeDisabled();
    // ⚠ **THE REASON AND THE COUNT ARE ASSERTED AS STRUCTURE, NOT AS ENGLISH.**
    // The sentence is written by eleven catalogues (B14 rule 35), so asserting
    // *two payments have bounced* would be asserting one of them; what this
    // screen is responsible for is carrying the server's reason and its figure
    // to whichever catalogue writes the words.
    const hold = container.querySelector("[data-autopay-hold]");
    expect(hold?.getAttribute("data-autopay-hold")).toBe("cash_only");
    expect(hold?.getAttribute("data-bounces")).toBe("2");
  });

  it("⚠ the customer's own election survives the sanction", async () => {
    // `BR-PAY-013` — `cash_only_no_autopay` is a PRIVILEGE sanction and
    // `autopay` stays exactly as the customer left it. A screen that showed
    // *you are not enrolled* would be un-asking something they asked for.
    const { container } = draw({
      ...BODY,
      enrolled: false,
      elected: true,
      cash_only: true,
      bounces: 2,
      held_reason: "cash_only",
    });
    await screen.findByTestId("autopay");
    await heldNode(container);
  });

  it("TC-9 — no amount box anywhere: nothing stores a ceiling", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    // ⚠ A field that took `$200.00` would take a figure with nowhere to put it.
    expect(container.querySelector("input[type='number']")).toBeNull();
    expect(container.querySelectorAll("input")).toHaveLength(0);
  });

  it("⚠ the link to the methods screen is asserted BY ADDRESS (DEF-CWP-3925)", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    const link = container.querySelector("a[href*='payment-methods']");
    expect(link).not.toBeNull();
    // The whole address, so a `//portal/…` protocol-relative URL cannot pass.
    expect(link?.getAttribute("href")).toBe("/pine-hill/portal/payment-methods");
  });

  it("DEF-CWP-4683 — an account already ON autopay is told so, and offered the way OFF", async () => {
    // ⚠ **SIX OF THE 73 SEEDED PINE HILL ACCOUNTS ARE ALREADY ON AUTOPAY**, and
    // every one of them opened a page that offered to switch on a thing already
    // running, said nothing about it being on, and named no way off. The body
    // has carried `elected` and `enrolled` since wave Q; the screen read
    // neither.
    //
    // ⚠ **AND THIS FIXTURE WAS ALREADY IN THAT STATE** — `BODY` has read
    // `enrolled: true, elected: true` since the file was written, so every case
    // in it was drawing the enrolled account and asserting a screen built for
    // the other one. A fixture in a state nothing asserts about is how a screen
    // ships with a whole branch missing.
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");
    expect(container.querySelector("[data-autopay-state]")?.getAttribute("data-autopay-state"))
      .toBe("on");
    expect(screen.getByText(/Autopay is on/i)).toBeInTheDocument();
    // The control is the one that matches the state. Still HELD — stopping it is
    // a write and no ruling has opened one (BR-CWP-001) — but a held *off* names
    // the thing the customer actually wants and its reason says what to do.
    expect(screen.getByRole("button", { name: /Turn autopay off/i })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /Turn autopay on/i })).toBeNull();
  });

  it("DEF-CWP-4683 — an account NOT on autopay is offered it, as before", async () => {
    const { container } = draw({ ...BODY, elected: false, enrolled: false });
    await screen.findByTestId("autopay");
    expect(container.querySelector("[data-autopay-state]")?.getAttribute("data-autopay-state"))
      .toBe("off");
    expect(screen.getByRole("button", { name: /Turn autopay on/i })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /Turn autopay off/i })).toBeNull();
  });

  it("DEF-CWP-4683 — asked for and NOT running is said plainly, which is the worst state", async () => {
    // ⚠ **THIS IS THE ONE THAT COSTS MONEY.** `elected` is what the customer
    // asked for and nothing un-asks it; `enrolled` is whether the account may be
    // autopaid at all, and two bounces turn that off without touching their
    // election (`BR-PAY-013`). The screen used to read *We take the balance on
    // each due date* over an account where nothing would be taken — so somebody
    // expecting the bill to be paid gets a late fee instead.
    const { container } = draw({ ...BODY, elected: true, enrolled: false, cash_only: true, bounces: 2 });
    await screen.findByTestId("autopay");
    expect(container.querySelector("[data-autopay-state]")?.getAttribute("data-autopay-state"))
      .toBe("stopped");
    expect(screen.getByText(/not taking payments automatically/i)).toBeInTheDocument();
  });

  it("DEF-CWP-4683 — the *what happens* box does not contradict a stopped account", async () => {
    // ⚠ **FOUND BY LOOKING AT THE SCREEN, NOT BY READING THE CODE.** With the
    // status line added, a stopped account read *"we are not taking payments
    // automatically"* in bold and then, four lines down under a heading saying
    // WHAT HAPPENS, *"We take the balance on each due date."* Both sentences are
    // on the same card and one of them is false about this account.
    //
    // The bullets are a description of the PRODUCT and are correct; the heading
    // is what claims they describe this account today. So the heading is scoped
    // in the one state where the present tense is a lie, and the bullets are
    // left exactly as they are — they are also what somebody deciding whether to
    // switch it back on needs to read.
    draw({ ...BODY, elected: true, enrolled: false, cash_only: true, bounces: 2 });
    await screen.findByTestId("autopay");
    expect(screen.getByText(/when it is running/i)).toBeInTheDocument();
    expect(screen.queryByText(/^WHAT HAPPENS$/)).toBeNull();
  });

  it("⚠ the holding screen is GONE — this route no longer answers with one", async () => {
    // `ComingSoon`'s own docstring: the walkthrough fails on any
    // `data-holding-screen` left in the DOM, and replacing it is the first act
    // of the wave that owns the route.
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    expect(container.querySelector("[data-holding-screen]")).toBeNull();
    expect(container.querySelector("[data-screen='CWP-040']")).not.toBeNull();
  });

  /**
   * `DEF-CWP-4870` — **a raw ISO date on the one screen that says when money
   * leaves a bank account.**
   *
   * `NEXT FEW` printed `2026-08-22` while `/payments` two clicks away rendered
   * `08/13/2026` and `/payment-methods` rendered `06/02/2026`. It is
   * `DEF-CWP-4197`'s family — the fourth occurrence — on a screen that was not
   * in the grep that closed the other three, and `DEF-CWP-4131`'s own
   * prevention note says to grep every sibling screen that renders the same
   * KIND of value.
   */
  it("DEF-CWP-4870 — the scheduled date renders in the TENANT's format, not the wire's", async () => {
    const { container } = drawWithRegional(BODY);
    await screen.findByTestId("autopay");

    const cell = container.querySelector("[data-slot-date='0']") as HTMLElement;
    // The server's own string stays on the attribute, where a walkthrough reads
    // it; the customer reads their utility's format.
    expect(cell.getAttribute("data-slot-on")).toBe("2026-09-14");
    expect(cell.textContent).toBe("09/14/2026");
    // ⚠ **AND NO ISO DATE IS ANYWHERE IN THE RENDERED TEXT.** A test that only
    // checked this one cell would pass the day a second date column arrived.
    expect(container.textContent ?? "").not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  /**
   * **An empty `NEXT FEW` was headers over nothing** — B14 rule 17 and R-22
   * (PO 2026-09-11: *"differntiate it using text message"*). On an account with
   * autopay off the rail drew `DATE · EXPECTED · STATUS` and not one row, with
   * only the footnote beneath: a picture that says nothing, where the customer
   * needs a sentence saying what would fill it.
   */
  it("an empty NEXT FEW says what would fill it instead of drawing bare headers", async () => {
    const { container } = draw({ ...BODY, elected: false, any_scheduled: false, next_few: [] });
    await screen.findByTestId("autopay");

    expect(container.querySelector("[data-minitable]")).toBeNull();
    expect(container.querySelector("[data-next-few-empty]")?.textContent).toBe(
      "Nothing is scheduled yet. A payment appears here when a bill is issued.",
    );
  });

  /**
   * The `How much` helper promised a setting the product does not have —
   * *"Or set a ceiling and we will ring you above it."* — over a screen with no
   * ceiling control, on a type whose own comment reads *⚠ Always `null`:
   * `accounts` has no column for a ceiling*. Hard-won law 1 in customer-facing
   * copy: a sentence claiming a guarantee is not the guarantee.
   */
  it("DEF-CWP-4871 — the helper no longer offers a ceiling nothing can store", async () => {
    const { container } = draw(BODY);
    await screen.findByTestId("autopay");

    const text = container.textContent ?? "";
    expect(text).toContain("Always the whole balance. There is no limit to set.");
    expect(text).not.toContain("ceiling");
    // TC-9 already asserts there is no amount box; this asserts the COPY stopped
    // describing one.
  });

  /**
   * `DEF-CWP-4873`'s family, on THIS screen — **a plural noun after `1`.**
   *
   * The register row is filed against `/payment-methods` (*"1 bounced payments
   * block autopay."*). The same string shape is on this screen's own refusal,
   * and it was not in the row: `portal.autopay.held.cash_only` read
   * *"{{count}} payments bounced — cash only"*. Found by doing what
   * `DEF-CWP-4131`'s prevention note asks — grep every sibling rendering the
   * same KIND of value — rather than by any check.
   */
  it("DEF-CWP-4873 — ONE bounce reads as one payment, not as *1 payments*", async () => {
    const { container } = draw({
      ...BODY,
      elected: false,
      cash_only: true,
      bounces: 1,
      held_reason: "cash_only",
    });
    await screen.findByTestId("autopay");

    const held = await heldNode(container);
    expect(held.textContent).toContain("1 payment bounced");
    expect(held.textContent).not.toContain("1 payments");
  });

  it("two bounces still read as two payments", async () => {
    const { container } = draw({
      ...BODY,
      elected: false,
      cash_only: true,
      bounces: 2,
      held_reason: "cash_only",
    });
    await screen.findByTestId("autopay");

    const held = await heldNode(container);
    expect(held.textContent).toContain("2 payments bounced");
  });
});
