// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-055 (EP-CWP-10) · Screen: CWP-066
// Rules:    BR-CWP-054 (the level, the variance and the settle-up, plus each
//           re-levelling and what happened) · BR-CWP-052 (the utility's own
//           note about a customer is held back) · B14 rule 31 · rule 35
// Cases:    TC-1 `$125.00` · `$47.30` ahead · June · TC-2 BEHIND, and June
//           ADDS it · TC-3 each re-levelling with its actual and movement ·
//           TC-4 the override shows, its internal reason does not · TC-5 not
//           enrolled routes to CWP-044 · TC-7 ahead and behind IN WORDS
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalLevelStandingView } from "../api/portalClient";

let readStanding: () => Promise<PortalLevelStandingView> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getLevelPayStanding: () => readStanding() };
});

const { LevelPayStandingView } = await import("./LevelPayStanding");

/** `US-CWP-055` §4's own figures — `$125.00` since 1 Jan 2026, `$47.30` ahead,
 *  settling up in June. The `$125.00` is `CWP-044`'s own worked level:
 *  `$1,501.09 ÷ 12 = $125.09` rounded to `$125.00`. */
const AHEAD: PortalLevelStandingView = {
  standing: {
    level: "125.0000",
    override: null,
    computed_level: null,
    currency: "USD",
    variance: "47.3000",
    variance_direction: "ahead",
    settle_up_month: 6,
    enrolled_on: "2026-01-01",
    last_leveled_at: "2026-01-01",
    status: "enrolled",
    off_budget: false,
    changes: [
      {
        event: "releveled",
        on: "2026-06-30",
        level: "125.0000",
        actual: "1501.0900",
        movement: "0.0000",
        balance_after: "47.3000",
        currency: "USD",
      },
      {
        event: "enrolled",
        on: "2026-01-01",
        level: "125.0000",
        actual: null,
        movement: "0.0000",
        balance_after: "0.0000",
        currency: "USD",
      },
    ],
  },
  months: [
    { month: "2026-01", paid: "125.0000", used: "98.4000", currency: "USD" },
    { month: "2026-02", paid: "125.0000", used: "104.2000", currency: "USD" },
  ],
  join_at: null,
};

function draw(view: PortalLevelStandingView) {
  readStanding = async () => view;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/level-pay/standing"]}>
      <Routes>
        <Route
          path="/:tenant/portal/level-pay/standing"
          element={<LevelPayStandingView accountId="acc-1" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-066 · where your level pay stands (US-CWP-055)", () => {
  it("TC-1/TC-7 · $125.00 a month, $47.30 AHEAD in words, settling up in June", async () => {
    const { container } = draw(AHEAD);
    // ⚠ `$125.00` APPEARS FIVE TIMES AND CORRECTLY SO — the tile at the top,
    // the new level on the re-levelling row, and once per month on the chart
    // added by `DEF-CWP-3981` (the fixture holds two months and the level did
    // not move between them). The test says so rather than pretending any of
    // them is not there.
    //
    // ⚠ **THE COUNT WENT 3 → 5 WHEN THE CHART LANDED, AND THAT IS THE CASE
    // DOING ITS JOB.** A count assertion over a whole screen is a tripwire on
    // every later addition: it went red the moment a picture drew the same
    // figure the tile above it states, which is exactly when a human should
    // look and decide whether the repetition is the arithmetic being right
    // (it is here) or a duplication.
    expect(await screen.findAllByText("$125.00")).toHaveLength(5);
    // ⚠ `$47.30` APPEARS TWICE FOR THE SAME REASON — the variance tile and the
    // balance-after cell on the re-levelling row are the same figure, which is
    // the arithmetic being right rather than a duplication.
    expect(screen.getAllByText("$47.30")).toHaveLength(2);
    // ⚠ TC-7 — *ahead* is a WORD beside a positive figure, never a bare `+`
    // or a signed number a customer has to interpret.
    expect(screen.getByText("You are ahead by")).toBeInTheDocument();
    expect(screen.getByText("June")).toBeInTheDocument();
    expect(container.textContent).not.toContain("+47.30");
  });

  it("TC-2 · negative · a customer BEHIND reads *behind*, and June ADDS it", async () => {
    const { container } = draw({
      ...AHEAD,
      standing: { ...AHEAD.standing!, variance_direction: "behind" },
    });
    expect(await screen.findByText("You are behind by")).toBeInTheDocument();
    expect(screen.queryByText("You are ahead by")).toBeNull();
    // The June panel says which DIRECTION it moves the bill, which is the half
    // of the sentence a customer actually acts on.
    expect(container.querySelector('[data-consequence-code="behind"]')?.textContent).toBe(
      "You have used $47.30 more than you paid, so that is added to the bill.",
    );
  });

  it("TC-3 · each re-levelling is listed with its actual and the balance after", async () => {
    const { container } = draw(AHEAD);
    await screen.findAllByText("$125.00");
    const rows = container.querySelectorAll("[data-row]");
    expect(rows).toHaveLength(2);
    expect(container.textContent).toContain("We checked the figure");
    expect(container.textContent).toContain("You joined budget billing");
    expect(container.textContent).toContain("2026-06-30");
    // ⚠ B14 rule 31 — a re-levelling is identified by its DATE, not by a row id.
    expect(container.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
    // ⚠ AND THE RAW EVENT CODE IS NEVER RENDERED.
    expect(container.textContent).not.toContain("releveled");
  });

  it("TC-4 · negative · the override is shown and its internal reason is not", async () => {
    const { container } = draw({
      ...AHEAD,
      standing: {
        ...AHEAD.standing!,
        level: "160.0000",
        override: "160.0000",
        computed_level: "125.0000",
      },
    });
    expect(
      await screen.findByText(
        "Your monthly amount is set to $160.00 rather than the $125.00 we worked out.",
      ),
    ).toBeInTheDocument();
    // ⚠ THE REASON IS NOT ON THE WIRE AT ALL — the type has no field for it,
    // so there is nothing for a screen to leak. This asserts the consequence.
    expect(container.textContent).not.toContain("reason");
  });

  it("TC-5 · negative · a customer NOT on level pay is routed, not shown a blank", async () => {
    const { container } = draw({ standing: null, months: [], join_at: "/level-pay" });
    expect(
      await screen.findByText(
        "You are not on budget billing, so there is nothing to show here yet.",
      ),
    ).toBeInTheDocument();
    // ⚠ NO KPI STRIP AND NO `$0.00` VARIANCE — an empty standing screen would
    // read as *you are exactly level*, which is a claim about somebody who
    // never joined.
    // ⚠ **`[data-kpi-row]`, NOT `.kpi-grid` — `DEF-CWP-4914`.** The strip on
    // this screen is the PORTAL's `KpiRow` now, because the staff `KPIStrip`
    // prints its `BR-REP-001` date basis in the tile header and put
    // **AS AT POSTING DATE** on two tiles of a customer's screen. `.kpi-grid`
    // is the staff component's own class, so this assertion could no longer
    // fail on this screen — hard-won law 7's *incapable of failing* shape, in
    // a check that still reported a pass.
    expect(container.querySelector("[data-kpi-row]")).toBeNull();
    expect(container.textContent).not.toContain("$0.00");
    // The SERVER said where to send them — and the address is asserted WHOLE,
    // because a `to` that is not run through `usePortalPath` comes out
    // `//portal/level-pay`, which is another host and which `toContain` would
    // accept (`BR-CWP-007`). This lane wrote exactly that bug and this line is
    // what caught it.
    expect(
      container.querySelector('[data-way-out="join"]')?.getAttribute("href"),
    ).toBe("/pine-hill/portal/level-pay");
    expect(
      container.querySelector('[data-portal-state="empty"] [data-way-out="join"]'),
    ).not.toBeNull();
  });

  it("a settle-up month the tenant has not set says so rather than defaulting to June", async () => {
    const { container } = draw({
      ...AHEAD,
      standing: { ...AHEAD.standing!, settle_up_month: null },
    });
    await screen.findAllByText("$125.00");
    expect(container.textContent).toContain(
      "We have not set the month it settles up in yet.",
    );
    expect(container.textContent).not.toContain("June");
  });

  it("a first year with no changes yet gets a sentence, not an empty table", async () => {
    const { container } = draw({
      ...AHEAD,
      standing: { ...AHEAD.standing!, changes: [] },
    });
    await screen.findAllByText("$125.00");
    expect(container.querySelector("[data-changes-empty]")).not.toBeNull();
    expect(container.querySelector("[data-minitable]")).toBeNull();
  });

  it("a read that fails says so and draws no figures", async () => {
    readStanding = async () => {
      throw new Error("nope");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/level-pay/standing"]}>
        <Routes>
          <Route
            path="/:tenant/portal/level-pay/standing"
            element={<LevelPayStandingView accountId="acc-1" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("We could not read this. Please try again."),
    ).toBeInTheDocument();
    expect(container.querySelector(".kpi-grid")).toBeNull();
  });

  it("D9 — the rail carries what happens in June and what leaving costs (CWP-066)", async () => {
    // ⚠ **UNJUDGEABLE UNTIL 2026-09-05** because the demo customer is not on
    // level pay. The rail was correct then and is correct now; the MAIN
    // column's missing chart is `DEF-CWP-3981` and is FIXED — see the case
    // below.
    const { container } = draw(AHEAD);
    await screen.findAllByText(/125/);
    const rail = container.querySelector("[data-screen='CWP-066'] [data-twocol-rail]");
    expect(rail, "CWP-066 draws no right-hand column").not.toBeNull();
    expect(rail?.textContent?.length ?? 0).toBeGreaterThan(0);
  });

  it("D6 — the two money series are DRAWN, not counted (CWP-066)", async () => {
    // ⚠ **`DEF-CWP-3981`, and the row's own reasoning is what made it
    // buildable.** `months[]` — what you PAID against what it actually COST —
    // has been served since `US-CWP-055`, and this screen rendered a COUNT of
    // it: *"12 months counted"*. The whole subject of a level-pay standing
    // screen is the GAP between those two lines, and a count cannot show a
    // gap.
    //
    // ⚠ **BOTH SERIES ARE MONEY AND NEITHER IS A QUANTITY.**
    // `billing_seam.level_pay_months` puts both through `_money()`: `paid` is
    // the level in force that month, `used` is what the bill actually came
    // to. So hard rule 3 is not engaged — there is no unit here, only a
    // currency — and the row was right that pushing money through `UsageBars`
    // would have labelled a currency as a unit. This is `MoneyBars`, lifted
    // out of `LevelPay.tsx` into the kit rather than copied (B14 rule 36).
    const { container } = draw(AHEAD);
    await screen.findAllByText(/125/);
    const chart = container.querySelector("[data-money-chart='level-standing']");
    expect(chart, "CWP-066 draws no chart").not.toBeNull();
    // Two months in the fixture, each with BOTH series, every figure as text.
    expect(chart!.querySelectorAll("[data-money-month]")).toHaveLength(2);
    expect(chart!.querySelector("[data-money-value='2026-01']")?.textContent).toContain("125.00");
    expect(chart!.querySelector("[data-money-compare='2026-01']")?.textContent).toContain("98.40");
    // ⚠ A swatch with no word beside it explains nothing — two series, two
    // words, from the catalogue rather than from this file.
    expect(chart!.querySelector("[data-money-legend]")?.textContent?.length ?? 0).toBeGreaterThan(0);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2, lane 7 — `DEF-CWP-4914` and R-10.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-4914 — no reporting date basis is printed on a customer's tile", async () => {
    // ⚠ **`AS AT POSTING DATE` WAS ON TWO OF THE THREE TILES, IN THE LARGEST
    // TYPE ON THE SCREEN.** The staff `KPIStrip`'s money tile REQUIRES a
    // `BR-REP-001` date basis and prints it in the tile header. It tells an
    // accountant which of two dates a figure is cut on; a customer reads it as
    // an error or as a date that is somehow theirs. `primitives.tsx` built
    // `KpiRow`/`KpiTile` for exactly this reason and said so in its own
    // docstring, and this screen imported the other one anyway.
    const { container } = draw(AHEAD);
    await screen.findByText("You pay each month");
    expect(container.textContent).not.toMatch(/posting date/i);
    expect(container.textContent).not.toMatch(/as at/i);
    // The portal's own strip, three tiles, is what `08-screen-layouts.md` names.
    expect(container.querySelector("[data-kpi-row]")).not.toBeNull();
    for (const tile of ["level", "variance", "settles"]) {
      expect(container.querySelector(`[data-kpi='${tile}']`)).not.toBeNull();
    }
  });

  it("R-10 — a failed read names the joining screen and really re-reads", async () => {
    let calls = 0;
    readStanding = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return AHEAD;
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/level-pay/standing"]}>
        <Routes>
          <Route
            path="/:tenant/portal/level-pay/standing"
            element={<LevelPayStandingView accountId="acc-1" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read this. Please try again.");
    expect(
      container
        .querySelector('[data-portal-state="failed"] [data-way-out="level-pay"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/level-pay");
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    expect(await screen.findByText("You pay each month")).toBeInTheDocument();
    expect(container.querySelector('[data-kpi-value="level"]')?.textContent).toBe("$125.00");
    expect(calls).toBe(2);
  });

});
