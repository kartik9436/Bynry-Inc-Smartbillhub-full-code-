// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-040 (EP-CWP-08) · Screen: CWP-033
// Rules:    BR-CWP-073 (unmeasured services SAY SO — **no empty chart**) ·
//           BR-MET-106 (an unread month is ABSENT, never 0; estimates marked) ·
//           BR-CWP-093 (nothing empty ever appears) · BR-CWP-095 (one tip) ·
//           CLAUDE.md hard rule 3 (the unit on the axis and in the CSV) ·
//           B14 rule 31 (no database id on screen)
// Cases:    the picker and what it re-draws · the chart and its axis · the
//           marked extremes and the MONTH each happened in · the sewer panel
//           with NO chart · the trash panel naming the cart · a trash-only
//           account · no comparison against nothing · the CSV's unit column
// CR-085:   s50 — ONE SERVICE AT A TIME. The Product Owner's own words, *"on
//           this screen usage you will ahve to give drop down for utility
//           services"*, and the drawing's reason: kWh and thousand gallons
//           cannot share a page, let alone an axis (hard rule 3). ⚠ The cases
//           that used to read a sewer or a trash panel now CHOOSE it first —
//           the panel is still exactly what `BR-CWP-073` asks for, it is just
//           behind the tab it belongs to.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type {
  PortalUsageMetric,
  PortalUsageSeries,
  PortalUsage,
  PortalUsagePoint,
  PortalUsageService,
} from "../api/portalClient";

let readUsage: (months: number) => Promise<PortalUsage> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getAccountUsage: (_id: string, months: number) => readUsage(months) };
});

const { UsageView, usageCsv, kpiColumns } = await import("./Usage");

/** `US-CWP-040` §4's own twelve months. Lowest `3,050`, highest `4,820`. */
const GALLONS = [3050, 3410, 3760, 4090, 4820, 4300, 4180, 3900, 4300, 4090, 3410, 4820];

function point(index: number, gallons: number | null, estimated = false): PortalUsagePoint {
  const month = `2026-${String(index + 1).padStart(2, "0")}`;
  if (gallons === null) {
    return {
      month,
      quantity: null,
      quantity_display: null,
      unit: null,
      absent: true,
      read_count: 0,
      estimated_read_count: 0,
      estimated: false,
      computed_at: null,
    };
  }
  return {
    month,
    quantity: `${gallons}.000000`,
    quantity_display: String(gallons),
    unit: "gal",
    absent: false,
    read_count: 1,
    estimated_read_count: estimated ? 1 : 0,
    estimated,
    computed_at: "2026-09-01T00:00:00Z",
  };
}

const WATER: PortalUsageService = {
  code: "water",
  name: "Water",
  basis: "metered",
  measured: true,
  billed_on: null,
  series: {
    service: { code: "water", name: "Water" },
    unit: "gal",
    unit_absence: null,
    points: GALLONS.map((gallons, index) => point(index, gallons)),
    months_present: 12,
    months_absent: 0,
    metrics: {
      avg_per_month: {
        value: "4010",
        display: "4010",
        unit: "gal",
        absent_reason: null,
        description: "last_12_months",
      },
      peak: { value: "4820", display: "4820", unit: "gal", month: "2026-05", absent_reason: null },
      low: { value: "3050", display: "3050", unit: "gal", month: "2026-01", absent_reason: null },
      yoy: {
        value: "18.000000",
        display: "+18.00",
        unit: null,
        absent_reason: null,
        description: "vs_prior_year",
        // ⚠ **THE TWO YEAR TOTALS ARE SERVED AND THIS FIXTURE OMITTED THEM**
        // — `monthly_usage_reads` has carried them since `CR-030` W3, and
        // `33.5`'s card is built from them rather than by summing the twelve
        // points on screen (`BR-MET-106` makes an absent month absent, so a
        // screen-side total would understate a year with a gap). Raw, exactly
        // as the wire sends them: the grouping is the screen's job.
        this_year_total: "48120.000000",
        prior_year_total: "44900.000000",
      },
      // CPB-06 / CPB-07 — absent by default, which is what every account in
      // the product answers until it has two stated months. The cases that
      // exercise them override this pair rather than the whole series.
      vs_last_month: {
        value: null,
        display: null,
        difference: null,
        difference_display: null,
        unit: null,
        direction: null,
        month: "2026-08",
        against_month: null,
        absent_reason: "no_earlier_month",
        description: "vs_previous_month",
      },
      same_month_last_year: {
        value: null,
        display: null,
        difference: null,
        difference_display: null,
        unit: null,
        direction: null,
        month: "2026-08",
        against_month: null,
        absent_reason: "no_same_month_last_year",
        description: "vs_same_month_last_year",
      },
    },
  },
};

const SEWER: PortalUsageService = {
  code: "sewer",
  name: "Sewer",
  basis: "share",
  measured: false,
  series: null,
  billed_on: { kind: "share", of: "water" },
};

const TRASH: PortalUsageService = {
  code: "trash",
  name: "Trash",
  basis: "capacity",
  measured: false,
  series: null,
  billed_on: { kind: "equipment", count: 1, size: "96 gal cart", equipment: "Refuse cart" },
};

function payload(services: PortalUsageService[], extra: Partial<PortalUsage> = {}): PortalUsage {
  return {
    as_of: "2026-09-02",
    window: { months: 12, from: "2025-10", to: "2026-09", options: [12, 24] },
    windows: [12, 24],
    services,
    next_reading: null,
    tip: null,
    //: `CWP-060`'s second placement (`DEF-CWP-3945`). `null` is the ordinary
    //: case and closes the slot up; the KEY is always present, so a lane can
    //: tell *nothing is attached* from *this build has no such feature*.
    attached_answer: null,
    ...extra,
  };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant` PATTERN** (CLAUDE.md hard-won law 2).
 * With an `initialEntries` and no matching `<Route>`, `useParams().tenant` is
 * `undefined` and every address this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. The door assertion below could not fail without it.
 */
function draw(view: PortalUsage) {
  readUsage = async () => view;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/usage"]}>
      <Routes>
        <Route path="/:tenant/portal/usage" element={<UsageView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * Choose a service the way a customer on a DESKTOP does.
 *
 * ⚠ **JSDOM APPLIES NO CSS, SO BOTH HALVES OF THE PICKER ARE IN THE DOM**
 * (`Bills.dom.test.tsx` records the same trap for its card list and its
 * table). `[data-segment=…]` is the desktop tab and `[data-service-select]` is
 * the phone dropdown; a test that queried neither specifically would find two
 * controls and be asserting about whichever came first.
 */
function chooseTab(container: HTMLElement, code: string) {
  const tab = container.querySelector(`[data-segment='${code}']`);
  if (tab === null) throw new Error(`no tab for ${code}`);
  fireEvent.click(tab);
}

afterEach(cleanup);

describe("CWP-033 · usage (US-CWP-040)", () => {
  it("the two doors this screen is the only way to, by address", async () => {
    // They were the portal's first door row, hand-drawn here; they are the
    // kit's `WhereNext` now (B14 rule 36) and this is what says the migration
    // did not move either address.
    const { container } = draw(payload([WATER]));
    await screen.findByText("Every reading");
    const doors = [...container.querySelectorAll("[data-where-next='usage'] a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(doors).toEqual(["/pine-hill/portal/readings", "/pine-hill/portal/equipment"]);
  });

  it("TC-2 — twelve bars, the AXIS labelled in gallons, extremes marked", async () => {
    const { container } = draw(payload([WATER, SEWER, TRASH]));
    await screen.findByText("Water · gal per month");

    const bars = container.querySelectorAll("[data-chart='water'] [data-month]");
    expect(bars).toHaveLength(12);
    // ⚠ HARD RULE 3 on the AXIS — `gal per month`, never a bare scale.
    expect(container.querySelector("[data-chart-axis]")?.textContent).toContain("gal");
    // ⚠ **THE TWO EXTREMES MOVED OUT OF THE AXIS FOOTNOTE AND INTO THE TILES,
    // AND THEY CARRY THEIR MONTH NOW** (`CR-085` s50 — *Lowest · Feb 412 kWh*).
    // The server has always served `metrics.low.month`; the footnote read
    // *Lowest 3050 gal* and answered half the question.
    expect(container.querySelector("[data-chart-lowest]")).toBeNull();
    // ⚠ **GROUPED, AND IT WAS NOT (`DEF-CWP-4168`).** The server composes
    // these through `metering/quantity_display.quantity_text`, which rounds and
    // trims and does NOT group — so this screen printed `4820` in a tile beside
    // a client-grouped `8,402 gal` in its year card, the same kind of number
    // written two ways one inch apart. `UnitCell`'s `formatQuantity` applies
    // the server's OWN rounding rule before it groups, so no digit changes.
    // This assertion pinned the ungrouped form and is amended with the fix,
    // exactly as `DEF-CWP-4009`'s `TC-2` was on the readings screen.
    expect(container.querySelector("[data-kpi-value='lowest-water']")?.textContent).toBe("3,050");
    expect(container.querySelector("[data-kpi-value='highest-water']")?.textContent).toBe("4,820");
  });

  it("CR-085 s50 — the picker offers the ACCOUNT'S OWN services and nothing else", async () => {
    // ⚠ *"The picker is built from the services this customer actually has —
    // never a fixed list"* (the drawing), which is hard-won law 2's own lesson:
    // the front end names the eleven services by hand in two files and the
    // eleventh one silently never appeared on screen.
    const { container } = draw(payload([WATER, SEWER, TRASH]));
    await screen.findByText("Water · gal per month");
    const tabs = [...container.querySelectorAll("[data-service-picker='service'] [data-segment]")];
    expect(tabs.map((tab) => tab.getAttribute("data-segment"))).toEqual([
      "water",
      "sewer",
      "trash",
    ]);
    // The phone's half is the Product Owner's own word — a DROP DOWN — and it
    // offers the same three.
    const options = [
      ...container.querySelectorAll("[data-service-select='service'] option"),
    ].map((option) => (option as HTMLOptionElement).value);
    expect(options).toEqual(["water", "sewer", "trash"]);
  });

  it("CR-085 s50 — ONE service at a time: only the chosen one is drawn at all", async () => {
    // The screen used to stack a chart per measured service and then repeat
    // every service in a row of cards underneath. On Ana's own account that is
    // **800 kWh and 8 kgal** on one page — the drawing's *"a customer cannot
    // read four units on one axis"*, one axis apart.
    const electric: PortalUsageService = {
      code: "electric",
      name: "Electric",
      basis: "metered",
      measured: true,
      billed_on: null,
      series: {
        ...WATER.series!,
        service: { code: "electric", name: "Electric" },
        unit: "kWh",
        points: GALLONS.map((value, index) => ({ ...point(index, value), unit: "kWh" })),
        metrics: {
          ...WATER.series!.metrics,
          avg_per_month: { ...WATER.series!.metrics.avg_per_month, unit: "kWh" },
          low: { ...WATER.series!.metrics.low, unit: "kWh" },
          peak: { ...WATER.series!.metrics.peak, unit: "kWh" },
        },
      },
    };
    const { container } = draw(payload([electric, WATER]));
    await screen.findByText("Electric · kWh per month");
    expect(container.querySelectorAll("[data-chart]")).toHaveLength(1);
    expect(container.querySelector("[data-chart='water']")).toBeNull();
    expect(container.querySelector("[data-chart-axis]")?.textContent).toContain("kWh");
    expect(container.querySelector("[data-kpi-unit='period-electric']")?.textContent).toBe("kWh");

    // ⚠ **AND SWITCHING MOVES EVERY FIGURE, NOT ONLY THE HEADING.** A chooser
    // that changes the title and leaves the chart is worse than none.
    chooseTab(container, "water");
    await screen.findByText("Water · gal per month");
    expect(container.querySelectorAll("[data-chart]")).toHaveLength(1);
    expect(container.querySelector("[data-chart='electric']")).toBeNull();
    expect(container.querySelector("[data-chart-axis]")?.textContent).toContain("gal");
    expect(container.querySelector("[data-kpi-unit='period-water']")?.textContent).toBe("gal");
    expect(container.querySelector("[data-kpi='period-electric']")).toBeNull();
  });

  it("CR-085 s50 — one service draws NO picker: a chooser with one option is furniture", async () => {
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-service-picker]")).toBeNull();
  });

  it("TC-1 — this period carries its unit and the year-on-year note", async () => {
    // ⚠ The three figures are the KIT's `KpiRow`/`KpiTile` now, not this
    // screen's own `Figure` (`CWP-033` 33.1, B14 rule 36) — so the selectors
    // are the kit's and the unit is its own span rather than part of the
    // number.
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-kpi-value='period-water']")?.textContent).toBe("4,820");
    expect(container.querySelector("[data-kpi-unit='period-water']")?.textContent).toBe("gal");
    // ⚠ **`+18.00` MOVED OUT OF THIS TILE AND DID NOT LEAVE THE SCREEN**
    // (`CR-085` CPB-07, 2026-09-08). The sub-line under the big number is
    // where the blueprint puts *"5% less than July"*, and a tile carrying two
    // comparison sentences breaks B14 rule 32 by addition. The year-on-year
    // percentage is a TOTAL against a TOTAL, so it now sits in the card
    // actually titled *Against last year*. **This assertion was not weakened:
    // it still demands the figure, at its new address**, which is the only
    // way this amendment can be told apart from quietly dropping it.
    expect(container.querySelector("[data-kpi-sub='period-water']")).toBeNull();
    expect(container.querySelector("[data-yoy-note='water']")?.textContent).toContain("+18.00");
  });

  it("33.1 — the drawing's row of figures, and the lead one names its service", async () => {
    const { container } = draw(
      payload([WATER, SEWER, TRASH], {
        next_reading: { from: "2026-09-02", to: "2026-09-06", open_now: false },
      }),
    );
    await screen.findByText("Water · gal per month");
    const row = container.querySelector("[data-kpi-row]");
    expect(row).not.toBeNull();
    // `CR-085` s50 — *This month · Lowest · Average · Highest*, plus the read
    // window when one is open. It was three.
    expect(row?.querySelectorAll("[data-kpi]").length).toBe(5);
    // ⚠ `WATER · THIS PERIOD`, never a bare `THIS PERIOD`: on an account with
    // electricity as well, the prefix is the only thing keeping it honest.
    expect(container.querySelector("[data-kpi='period-water']")?.textContent).toContain("Water");
    // The lead tile carries the brand rule the drawing puts on it.
    expect(
      container.querySelector("[data-kpi='period-water']")?.getAttribute("data-kpi-lead"),
    ).toBe("true");
    // The reading window is a TILE now, not a grey sentence under the title.
    // ⚠ **`toContain("09")` USED TO PASS ON A RAW ISO STRING** and would pass
    // again on one (`DEF-CWP-4685`) — `2026-09-02` contains `09` twice. The
    // dates are written by `Intl` now and this asserts the SENTENCE a person
    // reads, which is the only form that can tell the two apart.
    expect(container.querySelector("[data-kpi-value='next-reading']")?.textContent).toBe(
      "Sep 2 – Sep 6",
    );
  });

  it("33.1 — no reading window means no tile for it, never a dashed one", async () => {
    // `BR-CWP-093`: most days have no window open, and an absence is drawn as
    // nothing rather than as an empty box with a dash in it.
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelectorAll("[data-kpi]").length).toBe(4);
    expect(container.querySelector("[data-kpi='next-reading']")).toBeNull();
  });

  it("CR-085 s50 — the lowest and the highest month each say WHICH month", async () => {
    // ⚠ `Intl` writes the month, never a catalogue list of twelve names
    // (B14 rule 35) — and the server has served it the whole time.
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-kpi='lowest-water']")?.textContent).toContain(
      "Jan 2026",
    );
    expect(container.querySelector("[data-kpi='highest-water']")?.textContent).toContain(
      "May 2026",
    );
    // Hard rule 3 — never a bare number, on a tile as much as on an axis.
    expect(container.querySelector("[data-kpi-unit='lowest-water']")?.textContent).toBe("gal");
  });

  it("33.2 — the chart sits in a panel whose head names the service and the unit", async () => {
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    const panel = container.querySelector("[data-testid='usage-water']");
    expect(panel?.querySelector("h3")?.textContent).toBe("Water · gal per month");
    expect(panel?.querySelector("[data-chart='water']")).not.toBeNull();
  });

  it("33.2 — the brand note names whatever is billed as a share of this service", async () => {
    // ⚠ Read from `billed_on`, not hardcoded as *sewer follows water*: a
    // utility pricing something else as a share of water gets its own word.
    const { container } = draw(payload([WATER, SEWER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-share-note='water']")?.textContent).toBe(
      "Sewer is billed on this figure",
    );
  });

  it("33.2 — and there is no note at all when nothing is a share of it", async () => {
    const { container } = draw(payload([WATER, TRASH]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-share-note='water']")).toBeNull();
  });

  it("33.2 — every bar is dated, in the reader's own language", async () => {
    // The chart drew twelve bars a customer could not date. `Intl`, never a
    // list of twelve strings in eleven catalogues (B14 rule 35).
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    const labels = container.querySelectorAll("[data-chart-months='water'] [data-month-label]");
    expect(labels.length).toBe(12);
    expect(labels[0]?.textContent).toBe("Jan");
    expect(labels[11]?.textContent).toBe("Dec");
  });

  it("33.3 — the legend explains a mark the chart actually draws", async () => {
    // ⚠ The point of this case is the SECOND assertion. `data-extreme` had
    // marked the highest month since the chart was written and nothing
    // rendered the mark, so a legend entry naming it would have described a
    // distinction no reader could see (hard-won law 1, in pixels).
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(
      container.querySelector("[data-chart-legend='measured']")?.textContent,
    ).toContain("Measured");
    expect(
      container.querySelector("[data-chart-legend='highest']")?.textContent,
    ).toContain("Highest month");
    const peak = container.querySelector("[data-chart='water'] [data-extreme='highest']");
    expect(peak?.className).toContain("bg-accent-700");
    const ordinary = container.querySelector(
      "[data-chart='water'] [data-absent='false']:not([data-extreme])",
    );
    expect(ordinary?.className).toContain("bg-accent");
    expect(ordinary?.className).not.toContain("bg-accent-700");
  });

  it("CR-085 s50 — against last year, from the two totals the SERVER sends", async () => {
    // ⚠ **THE ROW OF PER-SERVICE CARDS IS GONE AND THIS IS WHERE ITS FIGURES
    // WENT.** `33.5` used to draw one card per service under the charts —
    // *WATER · This year 48,120 gal* sitting on a page whose picker could
    // perfectly well say ELECTRIC, which is the drawing's named failure with a
    // grid round it. The drawing's `ComparisonRows` belong to the chosen
    // service and are here instead.
    const { container } = draw(payload([WATER, SEWER, TRASH]));
    await screen.findByText("Water · gal per month");
    const year = container.querySelector("[data-testid='usage-year-water']");
    expect(year?.querySelector("[data-kv='this-year']")?.textContent).toContain("48,120 gal");
    expect(year?.querySelector("[data-kv='last-year']")?.textContent).toContain("44,900 gal");
    expect(container.querySelector("[data-testid='usage-card-water']")).toBeNull();
  });

  it("CR-085 s50 — no prior year is a SENTENCE, never a blank row", async () => {
    // The drawing's own state, and the one Ana's live account is actually in
    // (`absent_reason: "no_prior_reads"`). ⚠ It is not a raw key and not an
    // empty `KVList` — both of which pass a `toBeNull` check and neither of
    // which a customer can read.
    const lonely: PortalUsageService = {
      ...WATER,
      series: {
        ...WATER.series!,
        metrics: {
          ...WATER.series!.metrics,
          yoy: {
            value: null,
            display: null,
            unit: null,
            this_year_total: null,
            prior_year_total: null,
            absent_reason: "no_prior_reads",
            description: "vs_prior_year",
          },
        },
      },
    };
    const { container } = draw(payload([lonely]));
    await screen.findByText("Water · gal per month");
    // ⚠ **THE SENTENCE GOT MORE SPECIFIC AND THE CASE STILL DEMANDS ONE**
    // (`CR-085` CPB-06, 2026-09-08). This account has a stated August 2026 and
    // no August 2025, so the card now names the month it wanted instead of the
    // blanket *we do not have a year*. The blanket is still what an account
    // with NOTHING read gets — the case two describes below covers it — so
    // neither sentence was dropped; one of them narrowed.
    expect(container.querySelector("[data-no-same-month='water']")?.textContent).toBe(
      "No Aug 2025 to compare with.",
    );
    expect(container.querySelector("[data-no-prior-year='water']")).toBeNull();
    expect(container.querySelector("[data-kv='this-year']")).toBeNull();
  });

  it("33.6 — an unmeasured service is a TAB, and choosing it draws no chart", async () => {
    // ⚠ The panel `BR-CWP-073` asks for is unchanged; it is behind the tab it
    // belongs to now, which is what *one service at a time* means for a
    // service that produces no reading at all.
    const { container } = draw(payload([WATER, SEWER, TRASH]));
    await screen.findByText("Water · gal per month");
    chooseTab(container, "sewer");
    await screen.findByText("Not separately metered");
    expect(container.querySelector("[data-unmeasured='sewer']")).not.toBeNull();
    expect(container.querySelectorAll("[data-chart]")).toHaveLength(0);
    expect(container.querySelector("[data-kpi]")).toBeNull();
  });

  it("TC-3 · negative — the SEWER panel says what it is billed on and draws NOTHING", async () => {
    // ⚠ **THE ASSERTION IS THE ABSENCE**: no chart element and no zero series
    // anywhere inside the sewer panel (`BR-CWP-073`).
    const { container } = draw(payload([WATER, SEWER]));
    await screen.findByText("Water · gal per month");
    chooseTab(container, "sewer");
    await screen.findByText("Not separately metered");

    expect(container.querySelector("[data-billed-on='sewer']")?.textContent).toContain("water");
    expect(container.querySelector("[data-not-measured='sewer']")?.textContent).toBe(
      "Not separately metered",
    );
    expect(container.querySelector("[data-chart='sewer']")).toBeNull();
    const panel = container.querySelector("[data-unmeasured='sewer']");
    expect(panel?.querySelector("svg")).toBeNull();
    expect(panel?.textContent).not.toContain("0 gal");
  });

  it("TC-3b · negative — `measured` DECIDES, even if a series arrives beside it", async () => {
    // ⚠ **THIS CASE EXISTS BECAUSE TC-3 COULD NOT FAIL (hard-won law 7).**
    // Rewriting the screen's split as `series !== null` instead of `measured`
    // left every test green, because the fixture's sewer has no series — so the
    // assertion was true of the DATA rather than of the SCREEN. Here the server
    // sends a series for a `share` service, which is what a widened read or a
    // seam bug would do, and the panel must STILL say *billed on water used*
    // and draw nothing (`BR-CWP-073`). The same mutation now goes red here, and
    // it found a real bug one function over: `usageCsv` was keyed on `series`.
    const wrong: PortalUsageService = { ...SEWER, series: WATER.series };
    const { container } = draw(payload([wrong]));
    await screen.findByText("Not separately metered");
    expect(container.querySelector("[data-chart='sewer']")).toBeNull();
    expect(container.querySelector("[data-billed-on='sewer']")?.textContent).toContain("water");
    expect(usageCsv([wrong])).toBe("service,month,quantity,unit,estimated");
  });

  it("TC-4 · negative — the TRASH panel names the cart, and draws nothing", async () => {
    const { container } = draw(payload([WATER, TRASH]));
    await screen.findByText("Water · gal per month");
    chooseTab(container, "trash");
    await screen.findByText("Not measured");
    expect(container.querySelector("[data-billed-on='trash']")?.textContent).toContain(
      "96 gal cart",
    );
    expect(container.querySelector("[data-not-measured='trash']")?.textContent).toBe(
      "Not measured",
    );
    expect(container.querySelector("[data-chart='trash']")).toBeNull();
  });

  it("TC-5 · negative — a TRASH-ONLY account has no chart at all and still makes sense", async () => {
    const { container } = draw(payload([TRASH]));
    await screen.findByText("Not measured");
    expect(container.querySelectorAll("[data-chart]")).toHaveLength(0);
    expect(container.querySelector("[data-billed-on='trash']")?.textContent).toBeTruthy();
  });

  it("TC-6 · negative — no comparison is offered against nothing", async () => {
    // `absent_reason` is the read's own honest answer, and the note closes up
    // rather than printing `0%`.
    const lonely: PortalUsageService = {
      ...WATER,
      series: {
        ...WATER.series!,
        points: [point(7, 4820)],
        months_present: 1,
        months_absent: 0,
        metrics: {
          ...WATER.series!.metrics,
          yoy: {
            value: null,
            display: null,
            unit: null,
            absent_reason: "no_prior_reads",
            description: "vs_prior_year",
          },
        },
      },
    };
    const { container } = draw(payload([lonely]));
    await screen.findByText("Water · gal per month");
    // ⚠ **THIS ASSERTION USED TO READ `[data-figure-note='period-water']` AND
    // NOTHING IN THE PRODUCT HAS EVER CARRIED THAT ATTRIBUTE** (`CR-085` s50,
    // hard-won law 7's *structurally incapable of failing*). The tile's
    // sub-line is the kit's `data-kpi-sub`, and the old selector matched
    // nothing whether the note was drawn or not — so a case named *no
    // comparison is offered against nothing* was green over a screen that
    // offered one. Proved red before this line was written by rendering the
    // note unconditionally.
    expect(container.querySelector("[data-kpi-sub='period-water']")).toBeNull();
    // …and the comparison block below says so in a sentence rather than
    // drawing an empty pair of rows. ⚠ **THE SENTENCE IS THE ONE THAT NAMES
    // THE MONTH NOW** (`CR-085` CPB-06): a single stated month has an August
    // 2026 and no August 2025, which is a more useful absence to state than
    // *we do not have a year*.
    expect(container.querySelector("[data-no-same-month='water']")).not.toBeNull();
  });

  it("BR-MET-106 — an unread month draws NO BAR, never a zero one", async () => {
    const gappy: PortalUsageService = {
      ...WATER,
      series: {
        ...WATER.series!,
        points: [point(0, 3050), point(1, null), point(2, 4820, true)],
        months_present: 2,
        months_absent: 1,
      },
    };
    const { container } = draw(payload([gappy]));
    await screen.findByText("Water · gal per month");

    const absent = container.querySelector("[data-chart='water'] [data-absent='true']");
    expect(absent).not.toBeNull();
    expect((absent as HTMLElement).style.height).toBe("");
    // …and the estimate is MARKED rather than drawn like the others.
    expect(
      container.querySelector("[data-chart='water'] [data-estimated='true']"),
    ).not.toBeNull();
    expect(container.querySelector("[data-estimated-months='water']")?.textContent).toContain("1");
    // ⚠ **AND THE MARK IS NOW NAMED IN THE LEGEND** (`CR-085` s50 — *"marked
    // on the chart with a legend, so the customer knows which bars are
    // measured"*). The dashed outline has been drawn since the chart was
    // written and nothing said what it meant.
    expect(container.querySelector("[data-chart-legend='estimated']")?.textContent).toContain(
      "Estimated month",
    );
  });

  it("CR-085 s50 — and NO estimate legend where no bar is estimated", async () => {
    // A legend entry for a mark that is not on the chart explains a
    // distinction there is nothing to see (hard-won law 1, in pixels — the
    // same argument `33.3` records for the highest month).
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-chart-legend='estimated']")).toBeNull();
  });

  it("BR-CWP-093 — no open read window means NO tile, not a dash", async () => {
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-next-reading]")).toBeNull();
  });

  it("the read window, when one is open, names both of its dates", async () => {
    const { container } = draw(
      payload([WATER], {
        next_reading: { from: "2026-09-02", to: "2026-09-06", open_now: true },
      }),
    );
    await screen.findByText("Water · gal per month");
    const line = container.querySelector("[data-next-reading]")?.textContent ?? "";
    // ⚠ **THE DATES ARE NO LONGER ISO ON SCREEN** (`DEF-CWP-4685`) — an ISO
    // date is a machine format, and this tile printed two of them in the KPI
    // number font the first time anybody saw it draw.
    expect(line).toContain("Sep 2");
    expect(line).toContain("Sep 6");
  });

  it("TC-9 — the CSV carries the unit as a COLUMN on every row", () => {
    // A pure function, so the assertion is about the CONTENT rather than about
    // download machinery.
    const csv = usageCsv([WATER, SEWER, TRASH]);
    const lines = csv.split("\n");
    expect(lines[0]).toBe("service,month,quantity,unit,estimated");
    expect(lines).toHaveLength(13); // header + twelve stated months
    for (const line of lines.slice(1)) {
      expect(line.split(",")[3]).toBe("gal");
    }
    // ⚠ An unmeasured service contributes NO rows — a `0` would say the
    // customer used nothing (`BR-MET-106`).
    expect(csv).not.toContain("sewer");
    expect(csv).not.toContain("trash");
  });

  it("TC-9b — an absent month is absent from the CSV too, never a zero row", () => {
    const gappy: PortalUsageService = {
      ...WATER,
      series: { ...WATER.series!, points: [point(0, 3050), point(1, null)] },
    };
    expect(usageCsv([gappy]).split("\n")).toHaveLength(2);
  });

  it("CWP-062 — the tip is the KIT's bar, and it carries the words the server sent", async () => {
    // ⚠ **`DEF-CWP-3998` IS THE HALF THAT MATTERS HERE.** The screen used to
    // read `tip.body ?? tip.title` and the server has only ever sent `text`,
    // so a clerk who switched a tip on published an EMPTY box — and the old
    // fixture, built from the same invented type, agreed with it. This case
    // asserts the SERVED shape.
    const { container } = draw(
      payload([WATER], {
        tip: { text: "Watering before 10am loses less to evaporation.", target_screen: "portal_usage" },
      }),
    );
    await screen.findByText("Watering before 10am loses less to evaporation.");
    // The kit's component, not a private div: `data-usage-tip` is gone.
    expect(container.querySelector("[data-tip-bar]")).not.toBeNull();
    expect(container.querySelector("[data-usage-tip]")).toBeNull();
    // The drawing's kicker, from the catalogue rather than as a bare glyph.
    expect(container.querySelector("[data-tip-kicker]")?.textContent).toBe("Tip");
  });

  it("CWP-062 — no tip live means no bar at all, not an empty frame", async () => {
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    // `BR-CWP-095` / `BR-CWP-093`: the slot closes up so completely that
    // nobody can tell it was there.
    expect(container.querySelector("[data-tip-bar]")).toBeNull();
  });

  it("B14 rule 31 — no database id appears anywhere on the screen", async () => {
    const { container } = draw(payload([WATER, SEWER, TRASH]));
    await screen.findByText("Water · gal per month");
    expect(container.textContent ?? "").not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CR-085 blueprint · CPB-06 and CPB-07 — the two comparisons a person arrives
// with. Both were open because nothing on the server worked one out; both are
// `metering.monthly_usage` arithmetic now, so the figures below are the SAME
// figures a clerk sees on the staff Usage tab.
// ═══════════════════════════════════════════════════════════════════════════

/** A metric shaped like the wire's `vs_last_month` / `same_month_last_year`. */
function change(over: Partial<PortalUsageMetric> = {}): PortalUsageMetric {
  return {
    value: "-5.000000",
    display: "-5.00",
    difference: "-40.000000",
    difference_display: "-40",
    unit: "gal",
    direction: "less",
    month: "2026-08",
    against_month: "2026-07",
    absent_reason: null,
    description: "vs_previous_month",
    ...over,
  };
}

function withChanges(
  vsLastMonth: PortalUsageMetric,
  sameMonth: PortalUsageMetric,
): PortalUsageService {
  return {
    ...WATER,
    series: {
      ...WATER.series!,
      metrics: {
        ...WATER.series!.metrics,
        vs_last_month: vsLastMonth,
        same_month_last_year: sameMonth,
      },
    },
  };
}

const NO_SAME_MONTH: PortalUsageMetric = {
  value: null,
  display: null,
  difference: null,
  difference_display: null,
  unit: null,
  direction: null,
  month: "2026-08",
  against_month: null,
  absent_reason: "no_same_month_last_year",
  description: "vs_same_month_last_year",
};

describe("CPB-07 — usage compares against last month", () => {
  afterEach(cleanup);

  it("reads the blueprint's own sentence under the big number", async () => {
    const { container } = draw(payload([withChanges(change(), NO_SAME_MONTH)]));
    await screen.findByText("Water · gal per month");
    // The blueprint: *"The Usage screen reads '5% less than July' under the big
    // number"*. Displayed at two places (CLAUDE.md hard rule 2), and the month
    // is written by `Intl` rather than by a catalogue list of twelve names.
    expect(container.querySelector("[data-vs-last-month='water']")?.textContent).toBe(
      "5.00% less than Jul 2026",
    );
  });

  it("says THE SAME rather than a signed zero when nothing moved", async () => {
    const same = change({
      value: "0",
      display: "0.00",
      difference: "0",
      difference_display: "0",
      direction: "same",
    });
    const { container } = draw(payload([withChanges(same, NO_SAME_MONTH)]));
    await screen.findByText("Water · gal per month");
    // Ana's live account is this case — 800 kWh in July and 800 in August.
    // *"0.00% more"* is not a sentence anybody says.
    expect(container.querySelector("[data-vs-last-month='water']")?.textContent).toBe(
      "The same as Jul 2026",
    );
  });

  it("names the month it actually compared with when one in between is absent", async () => {
    // `BR-MET-106` — an unread month is ABSENT, never `0`, so the server walks
    // back to the nearest month that HAS a figure. The screen must print WHICH,
    // or *"20% less than last month"* would be a false claim about July.
    const skipped = change({
      display: "-20.00",
      difference_display: "-200",
      against_month: "2026-06",
    });
    const { container } = draw(payload([withChanges(skipped, NO_SAME_MONTH)]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-vs-last-month='water']")?.textContent).toBe(
      "20.00% less than Jun 2026",
    );
  });

  it("draws nothing at all rather than a dash when there is no earlier month", async () => {
    // `BR-CWP-093`. A first-month account has no comparison and the line closes
    // up; a dash under a big number reads as a figure we lost.
    const none = change({
      value: null,
      display: null,
      difference: null,
      difference_display: null,
      unit: null,
      direction: null,
      against_month: null,
      absent_reason: "no_earlier_month",
    });
    const { container } = draw(payload([withChanges(none, NO_SAME_MONTH)]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-vs-last-month='water']")).toBeNull();
  });
});

describe("CPB-06 — usage compares against the same month last year", () => {
  afterEach(cleanup);

  it("reads the blueprint's own sentence, WITH ITS UNIT, beside the chart", async () => {
    const sameMonth = change({
      value: "12.044818",
      display: "12.04",
      difference: "86.000000",
      difference_display: "86",
      direction: "more",
      against_month: "2025-08",
      description: "vs_same_month_last_year",
    });
    const { container } = draw(payload([withChanges(change(), sameMonth)]));
    await screen.findByText("Water · gal per month");
    // The blueprint: *"800 kWh · 86 kWh more than August 2025"*. ⚠ **THE UNIT
    // IS THE WHOLE POINT** (CLAUDE.md hard rule 3, and wave H's own finding —
    // a *"Monthly average 800"* that never said 800 of what).
    expect(container.querySelector("[data-same-month='water']")?.textContent).toBe(
      "86 gal more than Aug 2025",
    );
    // …and the sentence it replaces is gone.
    expect(container.querySelector("[data-no-prior-year='water']")).toBeNull();
  });

  it("states the absence naming the month, rather than the old blanket sentence", async () => {
    const { container } = draw(payload([withChanges(change(), NO_SAME_MONTH)]));
    await screen.findByText("Water · gal per month");
    // B14 rule 33 caps a refusal at five or six words. *"No August 2025 to
    // compare with."* names WHICH month is missing, which the blanket *"We do
    // not have a year to compare with yet"* never did.
    expect(container.querySelector("[data-no-same-month='water']")?.textContent).toBe(
      "No Aug 2025 to compare with.",
    );
  });

  it("never prints a difference without its unit", async () => {
    // The shape that makes wave H's defect impossible rather than merely fixed:
    // if the unit is absent the number is not rendered at all.
    const unitless = change({
      difference_display: "86",
      unit: null,
      direction: "more",
      against_month: "2025-08",
    });
    const { container } = draw(payload([withChanges(change(), unitless)]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-same-month='water']")).toBeNull();
  });
});

describe("CPB-06 · the browser's own finding — one absence, one sentence", () => {
  afterEach(cleanup);

  it("does not stack the blanket sentence under the one that names the month", async () => {
    // ⚠ **FOUND BY OPENING THE SCREEN, NOT BY A TEST** (hard-won law 6: no
    // gate in this repo reads rendered output). Ana's live account printed
    // *"No Aug 2025 to compare with."* and, underneath it, *"We do not have a
    // year to compare with yet."* — two refusals for one absence, the second
    // vaguer than the first, and B14 rule 32 broken by addition. Both DOM
    // cases above passed: each asserted its own line and neither asked what
    // sat beside it.
    const { container } = draw(payload([withChanges(change(), NO_SAME_MONTH)]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-no-same-month='water']")).not.toBeNull();
    expect(container.querySelector("[data-no-prior-year='water']")).toBeNull();
  });

  it("still says something when nothing has been read at all", async () => {
    // The blanket sentence is not dead code — it is the answer when the
    // same-month line has NO month to name either.
    const nothing: PortalUsageMetric = {
      ...NO_SAME_MONTH,
      month: null,
      absent_reason: "no_current_reads",
    };
    const blank: PortalUsageService = {
      ...withChanges(change(), nothing),
    };
    blank.series!.metrics.yoy = {
      value: null,
      display: null,
      unit: null,
      this_year_total: null,
      prior_year_total: null,
      absent_reason: "no_current_reads",
      description: "vs_prior_year",
    };
    const { container } = draw(payload([blank]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-no-same-month='water']")).toBeNull();
    expect(container.querySelector("[data-no-prior-year='water']")?.textContent).toBe(
      "We do not have a year to compare with yet.",
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CR-085 blueprint · CPB-08 — *"A usage month says what it cost"*. Done is
// *"The Usage screen reads '800 kWh at $0.1150 = $92.00' for August, and the
// figure is the bill's own line, not a re-calculation."*
// ═══════════════════════════════════════════════════════════════════════════

function withCost(cost: PortalUsageSeries["cost"]): PortalUsageService {
  return { ...WATER, series: { ...WATER.series!, cost } };
}

describe("CPB-08 — a usage month says what it cost", () => {
  afterEach(cleanup);

  /** ⚠ **ANA'S OWN JULY ELECTRIC LINES, COPIED OFF THE LIVE BILL** — not a
   *  shape this file invented. The first version of these cases made one up
   *  (`quantity_display`, one line) and passed against it while the server-side
   *  join answered `None` on every account in the product. */
  const TIER_1 = {
    description: "electric usage tier 1 (0-500 kWh)",
    quantity: "500",
    unit: "kWh",
    rate: "0.1100",
    rate_basis: "per_unit",
    rate_percent: null,
    amount_display: "55.00",
  };
  const TIER_2 = {
    ...TIER_1,
    description: "electric usage tier 2 (500-1000 kWh)",
    quantity: "300",
    rate: "0.1350",
    amount_display: "40.50",
  };

  it("reads the blueprint's own sentence, with its unit and its rate", async () => {
    const { container } = draw(
      payload([
        withCost({
          month: "2026-07",
          bill_number: "BL-2608-000052",
          lines: [TIER_1],
          total_display: "55.00",
          unit: "kWh",
        }),
      ]),
    );
    await screen.findByText("Water · gal per month");
    // A RATE shows FOUR decimals and money TWO (hard rule 2, `OQ-620`(a)).
    expect(container.querySelector("[data-usage-cost='water']")?.textContent).toBe(
      "500 kWh at $0.1100 = $55.00",
    );
  });

  it("draws EVERY tier the bill charged, and the bill's own total under them", async () => {
    // ⚠ **THE FINDING THAT CHANGED THIS PANEL.** The blueprint draws one line;
    // Ana's real July electric bill has two. Showing only the first would tell
    // a customer $55.00 about a month that cost $95.50.
    const { container } = draw(
      payload([
        withCost({
          month: "2026-07",
          bill_number: "BL-2608-000052",
          lines: [TIER_1, TIER_2],
          total_display: "95.50",
          unit: "kWh",
        }),
      ]),
    );
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-usage-cost-line='water-0']")?.textContent).toBe(
      "500 kWh at $0.1100 = $55.00",
    );
    expect(container.querySelector("[data-usage-cost-line='water-1']")?.textContent).toBe(
      "300 kWh at $0.1350 = $40.50",
    );
    // The total is the SERVER'S sum of the stored amounts; the screen adds
    // nothing, so it foots against the printed column by construction.
    expect(container.querySelector("[data-usage-cost-total='water']")?.textContent).toBe(
      "$95.50",
    );
  });

  it("does not repeat a single line's figure as a total underneath it", async () => {
    // B14 rule 32 — one sentence per section. A total under one line says the
    // same thing twice.
    const { container } = draw(
      payload([
        withCost({
          month: "2026-07",
          bill_number: "BL-1",
          lines: [TIER_1],
          total_display: "55.00",
          unit: "kWh",
        }),
      ]),
    );
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-usage-cost-total='water']")).toBeNull();
  });

  it("never prints a percentage rate wearing a dollar sign", async () => {
    // `DEF-CWP-3967`. `sewer usage — 40.00% of water usage charges` is a real
    // line on this product, and `0.4000` beside a `$` would be a lie about
    // money on a customer's screen.
    const { container } = draw(
      payload([
        withCost({
          month: "2026-07",
          bill_number: "BL-1",
          lines: [
            {
              description: "sewer usage — 40.00% of water usage charges",
              quantity: null,
              unit: null,
              rate: "0.4000",
              rate_basis: "percent",
              rate_percent: "40.00",
              amount_display: "16.75",
            },
          ],
          total_display: "16.75",
          unit: null,
        }),
      ]),
    );
    await screen.findByText("Water · gal per month");
    const line = container.querySelector("[data-usage-cost='water']")?.textContent ?? "";
    expect(line).toBe("sewer usage — 40.00% of water usage charges: $16.75");
    expect(line).not.toContain("$0.4000");
  });

  it("names the bill the figure came off, by its NUMBER", async () => {
    // B14 rule 31 — the reference on the customer's own paper, so they can go
    // and check it. Never an invoice id.
    const { container } = draw(
      payload([
        withCost({
          month: "2026-07",
          bill_number: "BL-2608-000052",
          lines: [TIER_1],
          total_display: "55.00",
          unit: "kWh",
        }),
      ]),
    );
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-usage-cost-bill='water']")?.textContent).toContain(
      "BL-2608-000052",
    );
  });

  it("says the month is not billed yet rather than printing nothing", async () => {
    // ⚠ **`null` IS THE COMMON ANSWER, NOT THE EDGE** — the latest stated month
    // is usually unbilled, and Ana's August is exactly that. B14 rule 33 caps a
    // refusal at five or six words. It must never read `$0.00`, which is a
    // claim that the month was free.
    const { container } = draw(payload([withCost(null)]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-usage-cost='water']")).toBeNull();
    expect(container.querySelector("[data-usage-not-billed='water']")?.textContent).toBe(
      "Not billed yet.",
    );
  });
});

describe("DEF-CWP-4685 — the next-reading tile, the first time anybody saw it draw", () => {
  afterEach(cleanup);

  it("writes the dates in the reader's own language, not as ISO", async () => {
    // ⚠ **THIS TILE HAD NEVER RENDERED FOR ANYBODY** (`DEF-MET-4684`: an OPEN
    // read window is unreachable by construction), so its copy had never been
    // read by a person. The first minute it went live it printed
    // `2026-09-14–2026-09-14` in the big KPI number font, wrapping over three
    // lines. The old case asserted the interpolation it built rather than the
    // sentence a person reads, so it was green over that.
    const { container } = draw(
      payload([WATER], {
        next_reading: { from: "2026-09-14", to: "2026-09-18", open_now: false },
      }),
    );
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-kpi-value='next-reading']")?.textContent).toBe(
      "Sep 14 – Sep 18",
    );
  });

  it("collapses a one-day window to a single date", async () => {
    // The `pine-hill` demo's own cycle is a single day, so the tile printed the
    // SAME date twice with a dash between them. *"Sep 14 – Sep 14"* is not a
    // range, it is a rendering bug wearing one.
    const { container } = draw(
      payload([WATER], {
        next_reading: { from: "2026-09-14", to: "2026-09-14", open_now: false },
      }),
    );
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-kpi-value='next-reading']")?.textContent).toBe("Sep 14");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// CR-085 step 2 lane 8 — the head that was never there, the row that wrapped,
// and the clerk's pinned answer that published into nothing.
// ════════════════════════════════════════════════════════════════════════════

describe("CWP-033 — the page head, the KPI row and the attached answer", () => {
  afterEach(cleanup);

  it("DEF-CWP-4846 — the title and the screen id are on EVERY branch", async () => {
    // ⚠ **THIS SCREEN HAD NO PAGE HEAD OF ANY KIND.** It was the last
    // `AWAITING_ANOTHER_LANE` entry in `pageHeadCensus.test.ts`, and
    // `document.querySelectorAll("h1,h2,h3,h4")` returned exactly ONE node at
    // both widths — the chart panel's `<h3>`. What stood where the title
    // belongs was an eleven-pixel `SectionTitle` inside the first card, and on
    // a failed read even that went away with the data.
    readUsage = async () => {
      throw new Error("500");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/usage"]}>
        <Routes>
          <Route path="/:tenant/portal/usage" element={<UsageView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read your usage.");
    expect(container.querySelector("h1")?.textContent).toBe("What you have used");
    expect(container.querySelector("[data-screen='CWP-033']")).not.toBeNull();
    // R-22 — the card SAYS which of the three states it is, which is the only
    // way anything in this repo can check that the failed address and the
    // loading address do not render the same thing.
    expect(container.querySelector("[data-portal-state='failed']")).not.toBeNull();
    // R-10 — the thing they can do about it, beside the message.
    expect(container.querySelector("[data-way-out='retry']")).not.toBeNull();
  });

  it("the head is drawn once — no screen writes a second title", async () => {
    // `pageHeadCensus.test.ts`'s last case says why: a screen that draws its
    // own heading element is how the portal acquired two `TwoCol`s and three
    // `Panel`s. The `SectionTitle` that used to repeat the page title inside
    // the first card is gone.
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    const titles = [...container.querySelectorAll("*")].filter(
      (el) => el.textContent === "What you have used" && el.children.length === 0,
    );
    expect(titles).toHaveLength(1);
  });

  it("DEF-CWP-4847 — five tiles never leave one alone on a second row", async () => {
    // ⚠ **jsdom APPLIES NO CSS, SO A GRID THAT WRAPS AND A GRID THAT DOES
    // NOT ARE THE SAME DOM.** The forty-eight cases above assert every tile's
    // label and value and could never have seen this. What IS assertable
    // without a browser is the arithmetic: `KpiRow` offers three columns and
    // four, and the old expression `tiles.length > 3 ? 4 : 3` handed five tiles
    // a four-column grid, so `NEXT READING DUE` sat alone with three quarters
    // of the row empty — and at 253px its own value wrapped over two lines.
    expect(kpiColumns(3)).toBe(3);
    expect(kpiColumns(4)).toBe(4);
    expect(kpiColumns(5)).toBe(3);
    // …and the rendered row asks for what the function says.
    const { container } = draw(
      payload([WATER], {
        next_reading: { from: "2026-09-30", to: "2026-10-02", open_now: false },
      }),
    );
    await screen.findByText("Water · gal per month");
    expect(container.querySelectorAll("[data-kpi]")).toHaveLength(5);
    expect(container.querySelector("[data-kpi-row]")?.className).toContain("grid-cols-3");
    expect(container.querySelector("[data-kpi-row]")?.className).not.toContain("grid-cols-4");
  });

  it("DEF-CWP-3945 — a clerk's pinned answer reaches the customer", async () => {
    // ⚠ **`ALSO_SHOW_SCREENS` IS `("bill", "usage", "overdue")` AND THE
    // USAGE PLACEMENT WENT NOWHERE.** `selectors.account_usage` never asked the
    // seam, `PortalUsage` had no field, and this screen had no card — so a
    // clerk who ticked *also show this on the Usage screen* got a confirmation
    // and no customer ever saw the answer. All three ends were built and
    // nothing joined them, which is `G13`'s blind spot: it asks whether a
    // prop has callers, and `AttachedAnswerCard` had none at all.
    const { container } = draw(
      payload([WATER], {
        attached_answer: {
          slug: "how-do-i-read-my-meter",
          question: "How do I read my meter?",
          topic: "readings",
          body: "The dial runs left to right; read the black digits only.",
          asked_for: "en",
          shown_in: "en",
          is_fallback: false,
          updated_on: "2026-09-01",
        },
      }),
    );
    await screen.findByText("How do I read my meter?");
    const card = container.querySelector("[data-attached-answer]");
    expect(card?.textContent).toContain("The dial runs left to right");
    // The slug is the ADDRESS, and it is built under the real tenant segment.
    expect(card?.querySelector("a")?.getAttribute("href")).toBe(
      "/pine-hill/portal/help/how-do-i-read-my-meter",
    );
  });

  it("DEF-CWP-3945 · negative — nothing pinned closes the slot up entirely", async () => {
    // `BR-CWP-093`. An empty card headed with a question is worse than no card.
    const { container } = draw(payload([WATER]));
    await screen.findByText("Water · gal per month");
    expect(container.querySelector("[data-attached-answer]")).toBeNull();
  });
});
