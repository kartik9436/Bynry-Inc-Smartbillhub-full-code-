// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-054 (EP-CWP-10) · Screen: CWP-044
// Rules:    BR-CWP-054 (the level, the variance and the settle-up month are
//           SHOWN) · BR-BIL-017 / BR-BIL-021 (eligibility, rounding, cadence
//           and settle-up month are TENANT settings, read not assumed) ·
//           BR-CWP-001 (enrolment is not one of the six portal writes) ·
//           BR-CWP-056 (held WITH its reason) · CLAUDE.md hard rule 2 (2 dp)
// Cases:    TC-1 $1,501.09 -> $125.09 -> $125.00 · TC-2 the rounding is the
//           TENANT's · TC-3 too little history, with the reason in words ·
//           TC-4 an enrolled account is routed, not offered twice · TC-5 the
//           chart · TC-6 the settle-up month is NAMED, never hardcoded to June
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalLevelPay } from "../api/portalClient";

let readLevelPay: () => Promise<{ level_pay: PortalLevelPay | null }> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getLevelPay: () => readLevelPay() };
});

const { LevelPayView } = await import("./LevelPay");

/** `US-CWP-054` §4's own figures. `$1,501.09 ÷ 12 = $125.0908…` and the level
 *  is `$125.00` by the TENANT's `whole_dollar` rounding — not by a rule in the
 *  portal, which is what TC-2 is about. */
const POSITION: PortalLevelPay = {
  months_of_history: 12,
  required_months: 12,
  trailing_total: "1501.0900",
  months_counted: 12,
  monthly_average: "125.0908",
  level: "125",
  level_unavailable: null,
  currency: "USD",
  rounding: "whole_dollar",
  settle_up_month: 6,
  relevel_cadence_months: 6,
  settings_unavailable: null,
  enrolled: false,
  enrolled_level: null,
  enrolled_settle_up_month: null,
  billed: [
    "98.4000", "104.2000", "112.7000", "121.3000", "148.9000", "171.4000",
    "182.2000", "163.5000", "131.0000", "112.4000", "101.8000", "53.2900",
  ],
  // `CR-085` `CPB-18` — a full twelve months has no hole in it.
  missing_months: [],
  missing_month_gaps: [],
  missing_months_before_first_bill: [],
  first_billed_month: [2025, 9],
  join_held: true,
  join_held_reason: "OQ-CWP-1568",
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant` PATTERN** (CLAUDE.md hard-won law 2).
 * With an `initialEntries` and no matching `<Route>`, `useParams().tenant` is
 * `undefined` and every address this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. The door assertion below could not fail without it.
 */
function draw(position: PortalLevelPay | null) {
  readLevelPay = async () => ({ level_pay: position });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/level-pay"]}>
      <Routes>
        <Route path="/:tenant/portal/level-pay" element={<LevelPayView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-044 · level pay (US-CWP-054)", () => {
  it("DEF-CWP-3954 — the door to CWP-066, which nothing pointed at", async () => {
    // ⚠ Outside the branch that needs a computed figure, so a customer with
    // too little history to be quoted one can still ask where theirs stands.
    // ⚠ **ASSERTED ON BOTH BRANCHES, AND THE ENROLLED ONE IS THE POINT.** A
    // customer already on level pay is not offered enrolment a second time
    // (TC-4), so that card is all they see — and *where does mine stand* is
    // the only question they had.
    for (const position of [POSITION, { ...POSITION, enrolled: true, enrolled_level: "125.0000" }]) {
      cleanup();
      const { container } = draw(position);
      await screen.findByText("Where your budget billing stands");
      expect(
        container.querySelector("[data-where-next='level-pay'] a")?.getAttribute("href"),
      ).toBe("/pine-hill/portal/level-pay/standing");
    }
  });

  it("TC-1/TC-2 · shows the twelve months, the average AND the rounded level", async () => {
    const { container } = draw(POSITION);
    expect(await screen.findByText("$1,501.09")).toBeInTheDocument();
    // ⚠ BOTH figures, because *"$125.09 rounded to $125.00"* is the sentence
    // that explains the level, and a screen given only the level cannot say it.
    expect(screen.getByText("$125.09")).toBeInTheDocument();
    const total = container.querySelector('[data-total="level"]');
    expect(total?.textContent).toContain("$125.00");
    expect(total?.textContent).toContain("You would pay each month");
  });

  it("TC-6 · names the tenant's OWN settle-up month rather than hardcoding June", async () => {
    draw({ ...POSITION, settle_up_month: 9 });
    expect(await screen.findByText(/September settles the difference/)).toBeInTheDocument();
    // The failure mode no gate in this repo can see: right for one utility and
    // silently wrong for every other.
    expect(screen.queryByText(/June settles/)).not.toBeInTheDocument();
  });

  it("says the month is not set rather than picking one, when the tenant has not", async () => {
    // `settings_families` ratifies NO month — *"rule names the parameter,
    // ratifies no month"* — so null is a real answer and never June.
    draw({ ...POSITION, settle_up_month: null });
    expect(await screen.findByText(/have not set the month it settles up in/i)).toBeInTheDocument();
  });

  it("TC-3 · an account with too little history is not offered it, with the reason in words", async () => {
    draw({
      ...POSITION,
      months_of_history: 4,
      months_counted: 4,
      level: null,
      level_unavailable: "4/12 months of billing history",
      monthly_average: null,
      trailing_total: null,
    });
    expect(await screen.findByText(/You have 4 months of bills with us/)).toBeInTheDocument();
    // ⚠ NEVER `$0.00`. A zero monthly amount is a real, chooseable figure and
    // would read as *this customer pays nothing*.
    expect(document.body.textContent).not.toContain("$0.00");
    expect(screen.queryByRole("button", { name: /Join budget billing/ })).not.toBeInTheDocument();
  });

  it("TC-4 · an already-enrolled account is routed, not offered enrolment again", async () => {
    draw({
      ...POSITION,
      enrolled: true,
      enrolled_level: "125",
      enrolled_settle_up_month: 6,
    });
    expect(await screen.findByText(/already on budget billing, at \$125.00 a month/)).toBeInTheDocument();
    expect(screen.getByText(/settles up in June/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Join budget billing/ })).not.toBeInTheDocument();
  });

  it("TC-5 · the chart draws one bar per billed month and names the level line", async () => {
    const { container } = draw(POSITION);
    await screen.findByText("$1,501.09");
    // ⚠ **THE SELECTORS MOVED WITH THE COMPONENT (`DEF-CWP-3981`).** This
    // chart was `BilledBars`, declared inside `LevelPay.tsx`; it is the kit's
    // `MoneyBars` now, so a second screen (`CWP-066`) draws the same picture
    // instead of copying it — the drift B14 rule 36 exists to stop. Same
    // bars, same figures, same reasoning; one vocabulary.
    expect(container.querySelectorAll("[data-money-month]")).toHaveLength(12);
    // Every figure is in the DOM as TEXT, so the walkthrough and a screen
    // reader read the same numbers a sighted customer does.
    expect(container.querySelector("[data-money-reference]")?.textContent).toContain("$125.00");
    expect(screen.getByText("$171.40")).toBeInTheDocument();
  });

  it("holds Join level pay with its reason — enrolment is not a portal write", async () => {
    const { container } = draw(POSITION);
    await screen.findByText("$1,501.09");
    // BR-CWP-001 · 08-screen-layouts.md already draws this control **held**.
    expect(container.querySelector('[data-level-pay-join] [data-held="true"]')).not.toBeNull();
    expect(screen.getByRole("button", { name: /Join budget billing/ })).toBeDisabled();
    // B14 rule 33 — five or six words.
    expect(screen.getByText("Call us to join budget billing")).toBeInTheDocument();
  });

  it("says the cadence is not set rather than inventing one", async () => {
    draw({ ...POSITION, relevel_cadence_months: null });
    expect(
      await screen.findByText(/have not set how often the figure is checked/i),
    ).toBeInTheDocument();
  });

  it("says it cannot work the figure out when the tenant's settings are unreadable", async () => {
    draw({
      ...POSITION,
      level: null,
      level_unavailable: "the tenant's budget-billing settings cannot be read",
      settings_unavailable: "the tenant's budget-billing settings cannot be read",
      required_months: null,
      monthly_average: null,
      trailing_total: null,
    });
    // BR-BIL-021 — *"an unreachable eligibility_months is not twelve"*. The
    // refusal travels; it is not replaced by the seeded defaults.
    expect(await screen.findByText(/cannot work out a monthly amount/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("$0.00");
  });

  it("puts no database id on screen", async () => {
    draw(POSITION);
    await screen.findByText("$1,501.09");
    expect(document.body.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/i);
  });

  it("CR-085 — the honest sentence is on the screen, above the button", async () => {
    // ⚠ **THE ONE LINE THAT SAYS WHAT THIS DOES NOT DO** (wireframe screen 47):
    // *"'This spreads your bills — it does not lower them' is on the screen,
    // above the button. Budget billing generates complaints when the settle-up
    // arrives unexplained."* Every sentence on this screen described the
    // benefit and none of them stated the limit.
    const { container } = draw(POSITION);
    const honest = await screen.findByText(/does not lower them/);
    expect(honest).toBeInTheDocument();
    // Above the join control, not beneath it, and not in the rail.
    const join = container.querySelector("[data-level-pay-join]");
    expect(honest.compareDocumentPosition(join!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("CR-085 CPB-18 — a HOLE in the history names the month, not a count", async () => {
    // ⚠ **THE BLUEPRINT'S DONE-WHEN IS *"or says precisely which month is
    // missing"*.** *You have 11 months of bills and we average 12* is true and
    // useless: it does not say whether a bill went astray or whether the
    // customer has simply not been here a year, and they cannot act on either.
    // This account HAS been here a year and one bill never came.
    draw({
      ...POSITION,
      months_of_history: 11,
      months_counted: 11,
      level: null,
      level_unavailable: "11/12 months of billing history",
      monthly_average: null,
      trailing_total: null,
      missing_months: [[2026, 3]],
      missing_month_gaps: [[2026, 3]],
      missing_months_before_first_bill: [],
      first_billed_month: [2025, 9],
    });
    expect(await screen.findByText(/missing your bill for March 2026/i)).toBeInTheDocument();
    // ⚠ NEVER a figure averaged off eleven months and called a year. The
    // eligibility window is the TENANT'S setting (BR-BIL-017/021).
    expect(document.body.textContent).not.toContain("$0.00");
  });

  it("CR-085 CPB-18 — too little history says WHEN it becomes possible", async () => {
    // ⚠ **THE OTHER SHAPE, AND IT IS A DIFFERENT ANSWER.** Every missing month
    // falls BEFORE this account's first bill, so nothing went astray — they
    // joined in April. The count alone left a customer with nothing to do; the
    // month they qualify is a fact, derived from their own first bill and the
    // tenant's own window, and is not a promise about a figure.
    draw({
      ...POSITION,
      months_of_history: 4,
      months_counted: 4,
      level: null,
      level_unavailable: "4/12 months of billing history",
      monthly_average: null,
      trailing_total: null,
      missing_months: [[2026, 3], [2026, 2], [2026, 1], [2025, 12], [2025, 11], [2025, 10], [2025, 9], [2025, 8]],
      missing_month_gaps: [],
      missing_months_before_first_bill: [[2026, 3], [2026, 2], [2026, 1], [2025, 12], [2025, 11], [2025, 10], [2025, 9], [2025, 8]],
      first_billed_month: [2026, 4],
    });
    // The existing sentence stands — it is the honest reason.
    expect(await screen.findByText(/You have 4 months of bills with us/)).toBeInTheDocument();
    // 2026-04 is the first bill; twelve months of window ends 2027-03.
    expect(screen.getByText(/March 2027/)).toBeInTheDocument();
    // ⚠ **AND IT MUST NOT CALL THIS A MISSING BILL** — nothing went astray.
    expect(screen.queryByText(/missing your bill/i)).toBeNull();
  });

  it("CR-085 CPB-18 — an account never billed keeps its own sentence", async () => {
    // ⚠ **NO HISTORY IS NOT A HOLE IN ONE.** Listing twelve absences for
    // somebody who joined last week would be true and useless, and would
    // displace the sentence this case already has.
    const { container } = draw({
      ...POSITION,
      months_of_history: 0,
      months_counted: 0,
      level: null,
      level_unavailable: "0/12 months of billing history",
      monthly_average: null,
      trailing_total: null,
      billed: [],
      missing_months: [],
      missing_month_gaps: [],
      missing_months_before_first_bill: [],
      first_billed_month: null,
    });
    await screen.findByText(/does not lower them/);
    expect(container.textContent).not.toMatch(/missing your bill/i);
    expect(container.querySelector("[data-level-pay-chart-empty]")).not.toBeNull();
  });

  it("DEF-CWP-4678 — the chart's bar may shrink and its figure may not", async () => {
    // ⚠ **THIS IS A PROXY AND THE DOCSTRING SAYS SO, BECAUSE jsdom HAS NO
    // LAYOUT.** The real check is `10-scripts/render-checks/cr085-cpb18-cpb21.mjs`,
    // which measured `document.scrollWidth` 415px inside a 390px window on this
    // exact screen and now measures 390. Nothing in a DOM test can see that.
    //
    // ⚠ **WHAT WOULD MAKE IT PASS WRONGLY:** somebody solving the overflow a
    // different way — a wrapping track, a max-width — would leave these classes
    // as they are and this case would go RED over a screen that is fine. That is
    // a false FAILURE, which a reader can inspect; the direction that matters is
    // that it cannot pass while `shrink-0` is back on the bar, which is the one
    // regression that reproduces the defect exactly.
    const { container } = draw({
      ...POSITION,
      months_of_history: 11,
      level: null,
      level_unavailable: "11/12 months of billing history",
      missing_month_gaps: [[2026, 3]],
      missing_months: [[2026, 3]],
      first_billed_month: [2025, 9],
    });
    await screen.findByText(/does not lower them/);
    const chart = container.querySelector("[data-money-chart]");
    expect(chart, "CWP-044 draws no chart for an account that HAS bills").not.toBeNull();
    const figure = chart!.querySelector("[data-money-value]");
    expect(figure?.className).toContain("shrink-0");
    // The bar is the sibling before the figure, and it is the thing that gives way.
    const bar = figure!.previousElementSibling as HTMLElement | null;
    expect(bar?.getAttribute("aria-hidden")).toBe("true");
    expect(bar?.className).not.toContain("shrink-0");
  });

  it("CR-085 — the internal name *level pay* never reaches the customer", async () => {
    // ⚠ Wireframe screen 47, Words: *"'Budget billing' — what North American
    // utilities call it. 'Level pay' is the internal name and never appears."*
    // It appeared in eight English messages, on both of this feature's screens.
    const { container } = draw(POSITION);
    await screen.findByText(/does not lower them/);
    expect(container.textContent?.toLowerCase()).not.toContain("level pay");
  });


  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2, lane 7 — **R-10**, PO 2026-09-11, verbatim: *"when a
  // screen tells a customer something bad, the thing they can do about it
  // must be on that same screen, next to the message. Not a page away. Not in
  // a menu. Right there."*
  // ═══════════════════════════════════════════════════════════════════════

  it("R-10 — no account to work this out for is not the end of the screen", async () => {
    // ⚠ **THE WORST BREACH ON THIS WHOLE PATCH, AND THIS IS THE BRANCH.** It
    // rendered *"We could not find an account to work this out for."* and
    // NOTHING ELSE — no button, no telephone number, no link back — on a
    // screen somebody opens because their bills swing and they want them not
    // to. Every other empty branch in this group already carried a door.
    const { container } = draw(null);
    await screen.findByText("We could not find an account to work this out for.");
    // Next to the message, INSIDE the card that carries it — which is what
    // *"right there"* means and what a row somewhere else on the page is not.
    const card = container.querySelector('[data-portal-state="empty"]');
    expect(card).not.toBeNull();
    // Addresses asserted WHOLE: a bare `/help-paying` resolves to
    // `//portal/help-paying`, another host, and `toContain` accepts it.
    expect(card?.querySelector('[data-way-out="standing"]')?.getAttribute("href")).toBe(
      "/pine-hill/portal/level-pay/standing",
    );
    expect(card?.querySelector('[data-way-out="help-paying"]')?.getAttribute("href")).toBe(
      "/pine-hill/portal/help-paying",
    );
  });

  it("R-10 — the failed branch offers a Try again that REALLY RE-READS", async () => {
    // ⚠ **A PRESENCE ASSERTION WOULD PASS ON A BUTTON WIRED TO NOTHING**,
    // which is `EmptyList`'s own `onCta: () => undefined` defect
    // (`DEF-MET-4764`) and is exactly the false pass this case is written to
    // rule out. So the read is made to fail, the control is pressed, and the
    // SECOND read is made to succeed — the screen must then draw the figure.
    let calls = 0;
    readLevelPay = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return { level_pay: POSITION };
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/level-pay"]}>
        <Routes>
          <Route path="/:tenant/portal/level-pay" element={<LevelPayView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not work this out. Please try again.");
    expect(container.querySelector('[data-portal-state="failed"]')).not.toBeNull();
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    // ⚠ `$125.00` appears twice on the populated screen (the rounded row and
    // the total), so the wait is on the TOTAL row's own handle.
    await screen.findByText("Your bills, month by month");
    expect(container.querySelector('[data-total="level"]')).not.toBeNull();
    expect(container.querySelector('[data-portal-state="failed"]')).toBeNull();
    expect(calls).toBe(2);
  });

  it("R-22 — the three states are told apart by their SENTENCE and say which they are", async () => {
    // PO 2026-09-11, verbatim: *"differntiate it using text message"*. The
    // kind is in the DOM because no check in this repository can read whether
    // a sentence MEANS *empty*; the sentences are what a customer reads.
    const { container } = draw(null);
    await screen.findByText("We could not find an account to work this out for.");
    expect(container.querySelector("[data-portal-state]")?.getAttribute("data-portal-state")).toBe(
      "empty",
    );
  });

  it("DEF-CWP-4915 — the chart over twelve months is not captioned as one month", async () => {
    // It read *This month, either way* over this account's last twelve bills
    // with the level drawn across them — in all eleven catalogues. No check in
    // this repository can read whether a caption describes the thing under it.
    const { container } = draw(POSITION);
    await screen.findByText("Your bills, month by month");
    expect(container.textContent).not.toContain("This month, either way");
    expect(container.textContent).toContain("Your bills, month by month");
  });

});
