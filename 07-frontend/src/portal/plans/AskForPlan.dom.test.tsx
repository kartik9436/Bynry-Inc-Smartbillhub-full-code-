// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-051 (EP-CWP-10) · Screen: CWP-042
// Rules:    BR-CWP-062 (the remainder goes on the FINAL instalment and the
//           screen shows it) · BR-CWP-063 (new bills still arrive) ·
//           BR-CWP-064 (late-fee suspension is a PER-PLAN election) ·
//           BR-CWP-066 (a customer may only ASK) · B14 rule 31 · rule 33
// Open:     OQ-CWP-1720 — the box must NOT say a plan ends after two misses
// Cases:    five of $22.03 and a final $22.05 totalling $132.20 · the FLAGGED
//           rounding row · the copy says FIVE then one · fees still apply ·
//           asking creates a REQUEST and says so · the missing sentence
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { ApiError } from "@/api/client";
import type { AccountBalance, PortalPlanPreview } from "../api/portalClient";

let readPreview: () => Promise<PortalPlanPreview> = async () => {
  throw new Error("no behaviour set");
};
//: `readPreview` above is a `let` because four cases swap it. This one never
//: is: every case here asks and is routed to a clerk, so the OTHER outcome —
//: a plan the product grants outright (`plan_created: true`) — is not
//: exercised anywhere. Recorded rather than silently made `const`.
const sendAsk: () => Promise<{ reference: string; plan_created: boolean; granted_by: string }> =
  async () => ({ reference: "SR-26-0074", plan_created: false, granted_by: "clerk" });

//: ⚠ **THE BALANCE READ IS MOCKED HERE OR IT IS NOT TESTED AT ALL.** Left to
//: the real client it fails in jsdom, the screen swallows it by design, and
//: the *What you owe* row simply does not draw — a silent absence that every
//: assertion below would have passed straight over (`CR-085`).
let readBalance: () => Promise<AccountBalance> = async () => BALANCE;

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    previewPlan: () => readPreview(),
    askForPlan: () => sendAsk(),
    getAccountBalance: () => readBalance(),
  };
});

/** The balance `CWP-022` and `CWP-027` already print for this account. */
const BALANCE = {
  account_id: "acc-1",
  owing: "172.2000",
  bills_open: "172.2000",
  credit_held: "0.0000",
  currency: "USD",
  due_on: "2026-08-22",
  open_bill_count: 1,
  bills: [],
  problems: [],
} as unknown as AccountBalance;

const { AskForPlanView } = await import("./AskForPlan");

/** `US-CWP-051` §4 — the story's own fixture, as the server serves it. */
const PLAN: PortalPlanPreview = {
  account_no: "ACC-10519-C",
  service_address: "1408 Elm St · A",
  balance: "172.2000",
  down_payment: "40.0000",
  spread: "132.2000",
  currency: "USD",
  cadence: "monthly",
  term_months: 6,
  first_due_on: "2026-09-14",
  instalments: [
    { seq: 1, due_on: "2026-09-14", amount: "22.0300", carries_the_rounding: false },
    { seq: 2, due_on: "2026-10-14", amount: "22.0300", carries_the_rounding: false },
    { seq: 3, due_on: "2026-11-14", amount: "22.0300", carries_the_rounding: false },
    { seq: 4, due_on: "2026-12-14", amount: "22.0300", carries_the_rounding: false },
    { seq: 5, due_on: "2027-01-14", amount: "22.0300", carries_the_rounding: false },
    { seq: 6, due_on: "2027-02-14", amount: "22.0500", carries_the_rounding: true },
  ],
  base_instalment_count: 5,
  base_amount: "22.0300",
  final_amount: "22.0500",
  suspend_late_fees: false,
  suspend_disconnect: true,
  current_bill_still_due: true,
  writes: [],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN** (CLAUDE.md hard-won
 * law 2). Bare inside a `MemoryRouter` with no matching `<Route>`,
 * `useParams().tenant` is `undefined` and every address this screen builds
 * comes out `//portal/…` — a protocol-relative URL to ANOTHER HOST that reads
 * as a perfectly good string to `toContain`. The door assertion below cannot
 * be written truthfully without this.
 */
function draw(plan: PortalPlanPreview = PLAN) {
  readPreview = async () => plan;
  readBalance = async () => BALANCE;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/ask-for-a-plan"]}>
      <Routes>
        <Route
          path="/:tenant/portal/ask-for-a-plan"
          element={<AskForPlanView accountId="acc-1" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** Fill the two required fields and press *See the instalments*. */
async function see(container: HTMLElement) {
  fireEvent.change(container.querySelector("#first-due") as HTMLInputElement, {
    target: { value: "2026-09-14" },
  });
  fireEvent.click(screen.getByText("See the installments"));
  await screen.findByText("The last installment carries the rounding.");
}

afterEach(cleanup);

describe("CWP-042 · ask for a payment plan (US-CWP-051)", () => {
  it("TC-1/TC-2 — five of $22.03, a final $22.05, and $132.20 in total", async () => {
    const { container } = draw();
    await see(container);
    const amounts = Array.from(container.querySelectorAll("[data-instalment]")).map(
      (cell) => cell.textContent,
    );
    expect(amounts).toEqual(["$22.03", "$22.03", "$22.03", "$22.03", "$22.03", "$22.05"]);
    expect(container.querySelector("[data-total='spread']")?.textContent).toContain("$132.20");
  });

  it("BR-CWP-062 — the LAST row is the one flagged as carrying the rounding", async () => {
    // ⚠ The flag is the ENGINE's, not this screen's idea of *last*.
    const { container } = draw();
    await see(container);
    const flagged = container.querySelectorAll("[data-rounding='true']");
    expect(flagged).toHaveLength(1);
    expect(flagged[0]?.textContent).toBe("$22.05");
    expect(container.querySelector("[data-rounding-note]")?.textContent).toBe(
      "The last installment carries the rounding.",
    );
  });

  it("TC-3 — the consequence box says FIVE payments then one, not six", async () => {
    // The blueprint's own box read *six payments of $22.03, then one of $22.05*
    // — seven payments, $154.23 — beside its own table of six totalling
    // $132.20. The count is the SERVER's, so the copy cannot drift from it.
    const { container } = draw();
    await see(container);
    const box = container.querySelector("[data-consequence]")?.textContent ?? "";
    expect(box).toContain("5 payments of $22.03, then one of $22.05.");
    expect(box).not.toContain("6 payments of $22.03");
  });

  it("TC-11 — where the election is off the box says fees still apply", async () => {
    // ⚠ `BR-CWP-064`. The blueprint calls a box promising otherwise *worse than
    // a blank space*.
    const { container } = draw();
    await see(container);
    const box = container.querySelector("[data-consequence]")?.textContent ?? "";
    expect(box).toContain("Late fees still apply.");
    expect(box).not.toContain("Late fees stop while you keep to it.");
  });

  it("BR-CWP-063 — the box says new bills still arrive and must still be paid", async () => {
    const { container } = draw();
    await see(container);
    expect(container.querySelector("[data-consequence]")?.textContent).toContain(
      "New bills still arrive and still have to be paid.",
    );
  });

  it("OQ-CWP-1720 — the box does NOT say the plan ends after two misses", async () => {
    // ⚠ **THE ABSENCE IS THE ASSERTION.** The blueprint promises *miss two and
    // the plan ends*; the Product Owner ruled on 2026-08-11 that nobody is
    // dropped, and the code implements that ruling. Printing the blueprint's
    // sentence would be a promise on a customer's screen that nothing keeps.
    const { container } = draw();
    await see(container);
    const box = container.querySelector("[data-consequence]")?.textContent ?? "";
    expect(box).not.toMatch(/plan ends/i);
    expect(box).toContain("The plan stays open.");
  });

  it("TC-10 — asking raises a REQUEST and the screen says no plan exists yet", async () => {
    // `BR-CWP-066`: a plan is granted by a clerk. The confirmation carries the
    // `SR-` reference and never implies a plan is now running.
    const { container } = draw();
    await see(container);
    fireEvent.click(screen.getByText("Ask for this plan ✓"));
    expect(await screen.findByText("We have your request")).toBeTruthy();
    expect(container.querySelector("[data-reference='SR-26-0074']")).toBeTruthy();
    expect(container.textContent).toContain("Someone at the office will set the plan up.");
  });

  /**
   * `DEF-CWP-<no-reason>` — **a disabled control says why** (`BR-SHL-025`,
   * `BR-CWP-056`). *See the instalments* was greyed with nothing on it at all,
   * twenty lines above a `CommitButton` in the same file that does it
   * correctly — which is how it survived review: the file already knew how.
   */
  it("no disabled control is greyed without saying why (BR-SHL-025)", async () => {
    const { container } = draw();
    await screen.findByText("See the installments");
    const disabled = Array.from(container.querySelectorAll("button")).filter(
      (one) => one.disabled,
    );
    expect(disabled.length).toBeGreaterThan(0);
    for (const one of disabled) {
      expect(one.getAttribute("title") ?? "").not.toBe("");
    }
    // The SAME sentence as the rail's commit, because it is the same refusal:
    // both are waiting on the two date boxes. Two sentences for one cause is
    // how a customer learns to stop reading them.
    const seeButton = screen.getByText("See the installments").closest("button");
    expect(seeButton).toBeDisabled();
    expect(seeButton).toHaveAttribute("title", "Fill in the dates first");
  });

  it("B14 rule 31 — no database id reaches the page", async () => {
    const { container } = draw();
    await see(container);
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("CR-085 — the total is on the screen BEFORE the choice, not after it", async () => {
    // ⚠ **THE FIGURE THE WHOLE SCREEN IS ABOUT.** The drawing opens *What you
    // owe · $247.30*; the product opened on an empty number box and asked the
    // customer to spread a total it had not told them. The figure is the
    // server's `owing` at two decimals, and it is present with no preview run.
    const { container } = draw();
    await screen.findByText("What you owe");
    const row = container.querySelector("[data-total='what-you-owe']");
    expect(row?.textContent).toContain("What you owe");
    expect(row?.textContent).toContain("$172.20");
    expect(container.querySelector("[data-instalments]")).toBeNull();
  });

  it("CR-085 — assistance is offered here, from the moment the screen opens", async () => {
    // ⚠ *"a customer asking for a plan is exactly the one who may qualify for a
    // grant — and most do not know it exists"* (wireframe screen 42). It is
    // outside the preview branch, so it does not wait for an instalment table.
    // ⚠ The address is asserted WHOLE: a bare `/help-paying` would come out
    // `//portal/help-paying`, another host, which `toContain` accepts.
    const { container } = draw();
    await screen.findByText("What you owe");
    expect(container.querySelector("[data-ask-plan-help]")).not.toBeNull();
    const door = container.querySelector("[data-ask-plan-help]")?.parentElement?.querySelector("a");
    expect(door?.getAttribute("href")).toBe("/pine-hill/portal/help-paying");
  });

  it("a refused preview says so instead of drawing a table", async () => {
    readPreview = async () => {
      throw new Error("refused");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/ask-for-a-plan"]}>
        <AskForPlanView accountId="acc-1" />
      </MemoryRouter>,
    );
    fireEvent.change(container.querySelector("#first-due") as HTMLInputElement, {
      target: { value: "2026-09-14" },
    });
    fireEvent.click(screen.getByText("See the installments"));
    // ⚠ **A THROWN `Error` IS NOT AN `ApiError`**, so it has no catalogue key
    // of its own and `refusalText` falls back to the client's own copy. That
    // is the `DEF-CWP-4141` fix's OTHER half: the screen stopped printing one
    // sentence for every cause, and a cause with no sentence still gets one.
    expect(
      await screen.findByText("Something went wrong. Nothing was saved — try again."),
    ).toBeTruthy();
    expect(container.querySelector("[data-instalments]")).toBeNull();
  });

  it("DEF-CWP-4141 — a refused term prints the SERVER's sentence, with its bound", async () => {
    // ⚠ **THE DEFECT, AS A TEST.** `payments_seam` refuses a term outside 2–12
    // with `message_key: portal.plan.termOutOfRange` and `params {min, max}`,
    // and `portal.plan.termOutOfRange` — *"Choose between 2 and 12 months."* —
    // has existed in all eleven catalogues and was rendered by NOTHING. Both
    // handlers caught everything into `portal.askPlan.couldNotRead`, so a
    // customer asking for thirteen months was told to check dates they had
    // filled in correctly, and the number the screen already knew was on the
    // wire and thrown away with it.
    readPreview = async () => {
      throw new ApiError(422, {
        code: "VAL_RANGE",
        message_key: "portal.plan.termOutOfRange",
        params: { min: 2, max: 12 },
        br_ref: "BR-CWP-062",
      });
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/ask-for-a-plan"]}>
        <AskForPlanView accountId="acc-1" />
      </MemoryRouter>,
    );
    fireEvent.change(container.querySelector("#first-due") as HTMLInputElement, {
      target: { value: "2026-09-14" },
    });
    fireEvent.change(container.querySelector("#term-months") as HTMLInputElement, {
      target: { value: "13" },
    });
    fireEvent.click(screen.getByText("See the installments"));
    expect(await screen.findByText("Choose between 2 and 12 months.")).toBeTruthy();
    // ⚠ And the sentence that was wrong for four of the five causes is gone.
    expect(
      screen.queryByText("We could not work that out. Please check the dates."),
    ).not.toBeInTheDocument();
  });

  it("DEF-CWP-4912 — the screen has a page heading, which it did not", async () => {
    // ⚠ **THE ONLY HEADING IN THIS SCREEN'S WHOLE DOCUMENT WAS AN `h3` READING
    // *There may be help too*, IN THE RAIL.** A customer arriving from the
    // overdue screen landed on a form with no title, and a screen reader
    // announced the assistance panel as the page. It is the LAST of
    // `DEF-CWP-4000`'s ten: the head sweep fixed nine screens by moving a head
    // above the branches, and this one had no head to move.
    // ⚠ **THE TITLE IS *Spread what you owe*, WHICH IS THE SCREEN'S OWN WORDS
    // AND NOT THE LINK'S.** `portal.askPlan.title` is what the card's own
    // section heading already said; it is PROMOTED to the page head rather
    // than duplicated, so the screen now names itself once. *Ask for a payment
    // plan* is `portal.overdue.askForAPlan` — the LABEL on the door, which is
    // a different string with a different job.
    const { container } = draw();
    await screen.findByText("Spread what you owe");
    const h1 = container.querySelector("h1");
    expect(h1).not.toBeNull();
    expect(h1?.textContent).toBe("Spread what you owe");
    // B14 rule 2 — ONE page header. The card no longer repeats the title.
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(screen.getAllByText("Spread what you owe")).toHaveLength(1);
    expect(container.querySelector('[data-screen="CWP-042"]')).not.toBeNull();
  });

  it("the drawing's back link goes to the overdue screen, by its WHOLE address", async () => {
    // ⚠ **`← Past due` IS THE FIRST LINE OF THE `CR-085` DRAWING AT BOTH 390
    // AND 1280**, and it is the only way back to the screen most customers
    // arrive from. `08-screen-layouts.md`'s T2 line and `wireframes/CWP-042.png`
    // draw a step bar and no head at all; the two frames disagree and the screen
    // is built on what they agree about — the head names the TASK, the step bar
    // names the STEP. See `STEP_BAR_INSTEAD` in `components/pageHeadCensus.test.ts`.
    //
    // ⚠ **THE WHOLE ADDRESS, NOT A FRAGMENT** — hard-won law 2's named fixture
    // defect. A component mounted with no `/:tenant/portal` route leaves
    // `useParams().tenant` undefined and builds `//portal/overdue`, a
    // protocol-relative URL to ANOTHER HOST, which reads as a perfectly good
    // string to `toContain`. This fixture mounts under the real path pattern and
    // this assertion names every segment, so neither mistake can pass.
    const { container } = draw();
    await screen.findByText("Spread what you owe");
    const back = container.querySelector('[data-testid="ask-plan-back"]');
    expect(back).not.toBeNull();
    expect(back?.getAttribute("href")).toBe("/pine-hill/portal/overdue");
    expect(back?.textContent).toContain("Past due");
  });

  it("DEF-CWP-4912 — the confirmation carries the head too", async () => {
    // A customer who has just asked for a plan should still be able to see
    // what screen they are on.
    const { container } = draw();
    fireEvent.change(container.querySelector("#first-due") as HTMLInputElement, {
      target: { value: "2026-09-14" },
    });
    fireEvent.click(screen.getByText("See the installments"));
    await screen.findByText("Ask for this plan ✓");
    fireEvent.click(screen.getByText("Ask for this plan ✓"));
    await screen.findByText(/SR-/);
    expect(container.querySelector("h1")?.textContent).toBe("Spread what you owe");
    expect(container.querySelector('[data-screen="CWP-042"]')).not.toBeNull();
  });

});
