// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-035 (EP-CWP-07) · Screen: CWP-030
// Rules:    BR-CWP-046 (the lines sum EXACTLY to the difference) · BR-CWP-093 ·
//           B14 rule 31 · rule 32 (a stated absence, closed by default; no
//           internal code in customer copy) · CLAUDE.md hard rule 3
// Questions: OQ-CWP-1563 — the decomposition is unsigned, so the breakdown
//           panel states its absence rather than drawing a split nobody chose.
// Cases:    the headline and its SIGN · a bill that went DOWN · a first bill
//           with no comparison at all · the stated absence · the year panel
//           with its unit on every figure · the summing invariant on screen
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalBillComparison } from "../api/portalClient";

let readComparison: () => Promise<PortalBillComparison> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getBillComparison: () => readComparison() };
});

const { BillComparisonView, signedMoney } = await import("./BillComparison");

/** The story's own two months: July `$138.44`, August `$142.18`, `+$3.74`. */
const ROSE: PortalBillComparison = {
  number: "BL-2608-0141",
  compared: true,
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  prior_number: "BL-2607-0139",
  prior_period_end: "2026-07-31",
  total_display: "142.18",
  prior_total_display: "138.44",
  difference: "3.7400",
  difference_display: "3.74",
  direction: "cost_more",
  components: [],
  components_available: false,
  components_blocked_by: "OQ-CWP-1563",
  against_last_year: [
    {
      service: "water",
      service_name: "Water",
      unit: "gal",
      this_year: "4820",
      last_year: "4090",
      this_year_label: "2026-08",
      last_year_label: "2025-08",
      this_year_estimated: false,
      last_year_estimated: false,
    },
  ],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN — `CR-085` step 2, hard-won law 2.**
 * This helper rendered `BillComparisonView` bare inside a `MemoryRouter` with
 * no `/:tenant/portal/…` route, so `useParams().tenant` was `undefined` and
 * every address the screen built came out `//portal/…` — a protocol-relative
 * URL to ANOTHER HOST, which reads as a perfectly good string to `toContain`.
 * Nothing on this screen asserted a door, so nothing noticed; this file now
 * asserts two, and a fixture that cannot tell a working link from a broken one
 * cannot be used to check either.
 */
function draw(view: PortalBillComparison) {
  readComparison = async () => view;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/bills/BL-2608-0141/comparison"]}>
      <Routes>
        <Route
          path="/:tenant/portal/bills/:number/comparison"
          element={<BillComparisonView number="BL-2608-0141" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-030 · why this bill is different (US-CWP-035)", () => {
  it("TC-1 — the headline names the difference and which way it went", async () => {
    const { container } = draw(ROSE);
    await screen.findByText("Against last month");
    expect(screen.getByText("This bill cost $3.74 more than last month.")).toBeTruthy();
    expect(container.querySelector("[data-figure='difference']")?.textContent).toBe("+$3.74");
    expect(container.querySelector("[data-direction]")?.getAttribute("data-direction")).toBe(
      "cost_more",
    );
  });

  it("the difference on screen IS this bill's total less last month's, from the printed figures", async () => {
    // ⚠ **THE ARITHMETIC, READ BACK OUT OF THE DOM.** `142.18 − 138.44 = 3.74`,
    // on the strings the customer is looking at — the check the story asks for
    // and the one nothing else in this repo performs.
    //
    // ⚠ **IN WHOLE CENTS, AND THE FIRST DRAFT OF THIS LINE WAS WRONG.** In
    // floating point `142.18 - 138.44` is `3.740000000000009`, so the check
    // failed on a page that was perfectly correct. That is CLAUDE.md hard rule
    // 2's *never float* arriving in a test rather than in the product: the
    // figures are exact at two decimals, so the comparison is made in the unit
    // they are exact in.
    const { container } = draw(ROSE);
    await screen.findByText("Against last month");
    const cents = (selector: string) =>
      Math.round(
        Number(container.querySelector(selector)!.textContent!.replace(/[$,+]/g, "")) * 100,
      );
    expect(cents("[data-figure='total']") - cents("[data-figure='prior_total']")).toBe(374);
    expect(cents("[data-figure='difference']")).toBe(374);
  });

  it("TC-4 — a bill that went DOWN reads *cost less* and keeps its minus sign", async () => {
    // ⚠ Nothing takes an absolute value. A refund read as a charge is the
    // failure `accountDetailTabs.tsx` records once already.
    const { container } = draw({
      ...ROSE,
      direction: "cost_less",
      difference: "-3.7400",
      difference_display: "-3.74",
      total_display: "138.44",
      prior_total_display: "142.18",
    });
    await screen.findByText("Against last month");
    expect(screen.getByText("This bill cost $3.74 less than last month.")).toBeTruthy();
    expect(container.querySelector("[data-figure='difference']")?.textContent).toBe("-$3.74");
  });

  it("a bill that did not move says so, with no plus and no minus", async () => {
    const { container } = draw({
      ...ROSE,
      direction: "cost_the_same",
      difference: "0.0000",
      difference_display: "0.00",
      prior_total_display: "142.18",
    });
    await screen.findByText("Against last month");
    expect(container.querySelector("[data-figure='difference']")?.textContent).toBe("$0.00");
  });

  it("TC-5 — a FIRST bill offers no comparison at all, not one against zero", async () => {
    const { container } = draw({
      number: "BL-2608-0141",
      compared: false,
      period_start: "2026-08-01",
      period_end: "2026-08-31",
      total_display: "142.18",
      components: [],
      components_available: false,
      components_blocked_by: "OQ-CWP-1563",
      against_last_year: [],
    });
    await screen.findByText(/first bill/);
    expect(container.querySelector("[data-no-comparison='']")).toBeTruthy();
    // ⚠ **`DEF-CWP-4862` — THE HEADING WAS DRAWN TWICE.** The head renders
    // `Why is this bill different?` on every branch; this branch then opened
    // its card with a `SectionTitle` holding the SAME string, so the screen
    // asked its question in 40px type and again immediately underneath. It
    // arrived when the head moved out of the success branch and nobody
    // re-read the branch the section title had been the only heading of.
    // ⚠ **COUNTED OVER EVERY LEAF NODE, NOT OVER `h1, h2, h3` — AND THE FIRST
    // DRAFT OF THIS ASSERTION WAS THE `h1, h2, h3` FORM, WHICH COULD NOT
    // FAIL.** `SectionTitle` renders a `<p>`, so a check that looked only at
    // heading tags would have found ONE match over the defect and one match
    // over the fix, passed both times, and told nobody. It was caught by
    // breaking the code first and watching the wrong thing stay green (law 7).
    const saidTwice = [...container.querySelectorAll("*")].filter(
      (node) =>
        node.children.length === 0 &&
        (node.textContent ?? "").trim() === "Why is this bill different?",
    );
    expect(saidTwice).toHaveLength(1);
    expect(saidTwice[0].tagName).toBe("H1");
    // R-22 — *nothing to compare with* is an ABSENCE, not a failure.
    expect(container.querySelector("[data-portal-state='empty']")).not.toBeNull();
    // No difference figure anywhere on the page — not a zero, not a dash.
    expect(container.querySelector("[data-figure='difference']")).toBeNull();
    expect(container.querySelector("[data-total='difference']")).toBeNull();
  });

  it("OQ-CWP-1563 — the breakdown states its absence in words and shows no split", async () => {
    // ⚠ An empty list drawn as a panel would read as *"nothing moved"*, which is
    // a different and false statement (B14 rule 32).
    const { container } = draw(ROSE);
    await screen.findByText("Against last month");
    expect(container.querySelector("[data-components-absent='']")).toBeTruthy();
    expect(container.querySelector("[data-components='']")).toBeNull();
    // …and the question id is not shown to a customer (rule 32).
    expect(container.textContent).not.toContain("OQ-CWP-1563");
  });

  it("BR-CWP-046 — when the components arrive they are drawn with their signs and they sum", async () => {
    // The story's own four, and the invariant read back off the page:
    // +8.83 + 0.00 + 4.29 − 9.38 = +3.74, exactly.
    const { container } = draw({
      ...ROSE,
      components_available: true,
      components_blocked_by: null,
      // ⚠ **THE PO's OWN FOUR, AT THE GRANULARITY THEY WERE PUT AT**
      // (`DEF-CWP-3968`): a usage bucket, a base bucket, a discount bucket and
      // a tax bucket. The `code` is a handle for this test and is NEVER shown.
      components: [
        { code: "water_usage", service: "water", kind: "usage", amount: "8.8300", amount_display: "8.83" },
        { code: "trash_base", service: "trash", kind: "base", amount: "0.0000", amount_display: "0.00" },
        { code: "bill_discount", service: null, kind: "discount", amount: "4.2900", amount_display: "4.29" },
        { code: "sewer_tax", service: "sewer", kind: "tax", amount: "-9.3800", amount_display: "-9.38" },
      ],
    });
    await screen.findByText("What moved");
    // ⚠ **A SHARE THAT DID NOT MOVE READS `unchanged`** (`DEF-CWP-3968`), so
    // it contributes a real ZERO to the sum rather than parsing as `NaN`. The
    // invariant is unchanged and is still read back off the PAGE: the drawn
    // figures must sum to the drawn headline, which is what `BR-CWP-046`
    // means by no tolerance.
    const drawn = [...container.querySelectorAll("[data-component]")].map((el) => {
      const text = el.textContent!.trim();
      return text === "unchanged" ? 0 : Number(text.replace(/[$,+]/g, ""));
    });
    expect(drawn).toEqual([8.83, 0, 4.29, -9.38]);
    expect(Number(drawn.reduce((a, b) => a + b, 0).toFixed(2))).toBe(3.74);
    expect(container.querySelector("[data-component='water_usage']")?.textContent).toBe("+$8.83");
    expect(container.querySelector("[data-component='sewer_tax']")?.textContent).toBe("-$9.38");
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `DEF-CWP-3968` — the ruled behaviour, which shipped as a stated absence
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-3968 — every reason is NAMED IN WORDS, never by its code", async () => {
    // ⚠ **B14 rule 32 — no internal code in customer-facing copy.** The panel
    // used to render `portal.billWhy.component.<code>` with the CODE as its
    // own fallback, so a component the catalogue had no word for would have
    // printed `lower_tax_smaller_sewer_share` on a customer's screen. The
    // words are composed from the SERVICE and the KIND instead, through the
    // `rating.service.*` keys the bill's own headings already use (law 5).
    const { container } = draw({
      ...ROSE,
      components_available: true,
      components_blocked_by: null,
      components: [
        { code: "water_usage", service: "water", kind: "usage", amount: "8.8300", amount_display: "8.83" },
        { code: "trash_base", service: "trash", kind: "base", amount: "0.0000", amount_display: "0.00" },
        { code: "bill_tax", service: null, kind: "tax", amount: "-5.0900", amount_display: "-5.09" },
      ],
    });
    await screen.findByText("What moved");
    const panel = container.querySelector("[data-components='']")?.textContent ?? "";
    expect(panel).toContain("Water used");
    expect(panel).toContain("Trash standing charge");
    expect(panel).toContain("Tax");
    // Not one code reaches the screen.
    expect(panel).not.toContain("water_usage");
    expect(panel).not.toContain("trash_base");
    expect(panel).not.toContain("bill_tax");
  });

  it("the shares are FOOTED, and the foot is the served difference", async () => {
    // ⚠ **THE DRAWING CLOSES THIS LIST WITH *Total difference +$14.80*, AND
    // ITS REASON IS THE WHOLE SCREEN:** *"the customer is never asked to
    // subtract … the parts add to it"*. A list of signed shares with nothing
    // under it leaves the reader adding four figures to check they reach the
    // headline they read at the top of the page.
    // ⚠ **NOTHING IS SUMMED HERE.** `BR-CWP-046` serves the shares only when
    // they sum EXACTLY to the difference, so the foot re-prints the server's
    // own `difference_display` — a browser adding the rows would be a second
    // implementation of the one figure this page exists to explain.
    const { container } = draw({
      ...ROSE,
      components_available: true,
      components_blocked_by: null,
      components: [
        { code: "water_usage", service: "water", kind: "usage", amount: "2.3700", amount_display: "2.37" },
        { code: "sewer_usage", service: "sewer", kind: "usage", amount: "0.9500", amount_display: "0.95" },
        { code: "bill_tax", service: null, kind: "tax", amount: "0.4200", amount_display: "0.42" },
      ],
    });
    await screen.findByText("What moved");
    expect(screen.getByText("Total difference")).toBeTruthy();
    expect(container.querySelector("[data-figure='components_total']")?.textContent).toBe("+$3.74");
    // It is INSIDE the panel the shares are in, under them.
    expect(
      container.querySelector("[data-components=''] [data-figure='components_total']"),
    ).not.toBeNull();
  });

  it("DEF-CWP-3968 — a share that did not move reads 'unchanged', not '+$0.00'", async () => {
    // *Trash cart charge unchanged* is one of the four lines the PO ruled on.
    // A signed zero is a machine's way of writing the same fact, and a
    // customer scanning for what changed reads it as a change.
    const { container } = draw({
      ...ROSE,
      components_available: true,
      components_blocked_by: null,
      components: [
        { code: "trash_base", service: "trash", kind: "base", amount: "0.0000", amount_display: "0.00" },
      ],
    });
    await screen.findByText("What moved");
    expect(container.querySelector("[data-component='trash_base']")?.textContent).toBe(
      "unchanged",
    );
  });

  it("DEF-CWP-3968 — a bill-level charge is named without a service", async () => {
    // A tax or a whole-bill discount belongs to no service, so the row must
    // not read `null charges` or fall through to a code.
    const { container } = draw({
      ...ROSE,
      components_available: true,
      components_blocked_by: null,
      components: [
        { code: "bill_discount", service: null, kind: "discount", amount: "4.2900", amount_display: "4.29" },
      ],
    });
    await screen.findByText("What moved");
    const panel = container.querySelector("[data-components='']")?.textContent ?? "";
    expect(panel).toContain("Discounts");
    expect(panel).not.toContain("null");
    expect(panel).not.toContain("bill_discount");
  });

  it("TC-8 — the year panel shows both figures WITH their unit", async () => {
    // Hard rule 3: `4,090 → 4,820` with no unit is two bare numbers.
    const { container } = draw(ROSE);
    await screen.findByText("Against the same month last year");
    expect(container.querySelector("[data-year-compare='water']")?.textContent).toBe(
      "4090 gal → 4820 gal",
    );
    expect(container.querySelector("[data-jump-hint='']")?.textContent).toContain("leak");
  });

  it("BR-CWP-093 — no year-on-year data means NO year panel", async () => {
    draw({ ...ROSE, against_last_year: [] });
    await screen.findByText("Against last month");
    expect(screen.queryByText("Against the same month last year")).toBeNull();
  });

  it("signedMoney marks a rise and never invents one", () => {
    expect(signedMoney("8.83")).toBe("+$8.83");
    expect(signedMoney("0.00")).toBe("$0.00");
    expect(signedMoney("-9.38")).toBe("-$9.38");
  });

  it("the screen tags itself CWP-030 and carries no database id", async () => {
    const { container } = draw(ROSE);
    await screen.findByText("Against last month");
    expect(container.querySelector("[data-screen='CWP-030']")).toBeTruthy();
    expect(container.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  });

  it("a comparison it cannot work out says so", async () => {
    readComparison = async () => {
      throw new Error("refused");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/bills/BL-2608-0141/comparison"]}>
        <Routes>
          <Route
            path="/:tenant/portal/bills/:number/comparison"
            element={<BillComparisonView number="BL-2608-0141" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("We could not work this out.")).toBeTruthy();
    // ⚠ **R-10 — the way out beside the message** (PO 2026-09-11). It was one
    // grey sentence in a card with nothing to press.
    const state = container.querySelector("[data-portal-state='failed']");
    expect(state).not.toBeNull();
    expect(state?.querySelector("[data-way-out='retry']")).not.toBeNull();
    expect(state?.querySelector("[data-way-out='bill']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/bills/BL-2608-0141",
    );
  });

  it("D6 — the panel draws the two-bar comparison, not four numbers (CWP-030)", async () => {
    // ⚠ `DEF-CWP-3981`. `08-screen-layouts.md` opens AGAINST LAST AUGUST with
    // *a tiny two-bar chart with mono labels* and the panel drew figures only.
    // On this screen the picture IS the explanation: two bars of different
    // heights answer *why did August cost more* faster than a sentence with
    // four numbers in it.
    const { container } = draw(ROSE);
    await screen.findAllByText(/4090 gal/);
    const chart = container.querySelector("[data-chart='year-water']");
    expect(chart, "CWP-030 draws no comparison chart").not.toBeNull();
    // Two bars, both real — an absent month has no place in a two-point
    // comparison, and the server drops a service that cannot supply both.
    expect(chart?.querySelectorAll("[data-absent='false']").length).toBe(2);
    // ⚠ The TALLER one is marked, which is the whole point of the picture.
    expect(chart?.querySelector("[data-extreme='highest']")).not.toBeNull();
    // Hard rule 3 — the unit is on the axis, not assumed.
    expect(chart?.querySelector("[data-chart-axis]")?.textContent).toContain("gal");
  });


  it("DEF-CWP-4213 — the screen offers a way to ACT on the bill it explains", async () => {
    // ⚠ **IT EXPLAINED A BILL AND THE ONLY CONTROL ON IT WAS THE BACK LINK.**
    // A customer who has just read *this bill cost $3.74 more than last month*
    // wants one of two things: the bill itself, line by line, or somebody to
    // look at it. Both are addresses this product already serves and neither
    // had a door from here.
    // ⚠ **THE FIRST IS ALSO THE DOOR LANE 8 ASKED FOR BY NAME** — `CPB-08`
    // joins a usage month to the bill line that produced it, and both screens
    // read the same catalogue key so they cannot end up with two phrasings of
    // *open the bill*. Asserted by ADDRESS, because a label proves nothing.
    const { container } = draw(ROSE);
    await screen.findByText("Against last month");
    const doors = container.querySelector("[data-where-next='bill-why']");
    expect(doors).not.toBeNull();
    const whole = doors?.querySelector("[data-door='/bills/BL-2608-0141'] a");
    expect(whole?.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2608-0141");
    expect(whole?.textContent).toBe("See the whole bill →");
    expect(
      doors?.querySelector("[data-door='/bills/BL-2608-0141/dispute'] a")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/bills/BL-2608-0141/dispute");
  });
});
