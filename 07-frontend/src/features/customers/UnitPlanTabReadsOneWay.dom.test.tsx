// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave H — H1 (`PUJ-33`), H2 (`PUJ-34`), H3 (`PUJ-35`).
// Defects: DEF-MET-4689 (one date written four ways, two of them opposite
//          orders forty pixels apart) · DEF-MET-4693 (one sentence printed
//          seven times, and our implementation explained to a clerk).
// Rules:   BR-MET-1166 (a base charge of `0.00` is not free — the row says what
//          the service IS priced on) · BR-MET-1167 (a date is written one way
//          on a screen, with a named month) · B14 rule 32 (no rule id, no
//          internal code, no sentence about our implementation in clerk-facing
//          copy) · BR-RAT-027 (the base Σ is forwarded, never recomputed) ·
//          B4/B5 ❄️ FROZEN — nothing here computes money.
// Screens: PRM-03 (S15 unit detail → Plan tab)
// ───────────────────────────────────────────────────────
// **WHY THESE THREE DEFECTS COULD NOT BE CAUGHT BY THE TESTS THAT EXISTED, AND
// WHAT THIS FILE DOES DIFFERENTLY.**
//
// Every one of them is a property of the WHOLE PANEL rather than of any
// component in it. Each formatter was right on its own — a tenant format, a
// stored ISO string, two native date inputs the browser renders in its own
// locale — and each floor sentence was rendered once by its own row. So a test
// that asserted any single value passed, and the Product Owner found all three
// by reading the page.
//
// These cases therefore assert across the panel: how many DISTINCT date shapes
// the rendered text holds, and how many times one sentence appears in it. That
// is the comparison nothing in this repository was making.
//
// ⛔ **AND THEY ASSERT NO ARITHMETIC.** The panel forwards stored strings and
// this suite reads them back; `$0.00` is fixture input, not a computed figure.
//
// **RED PROVED FIRST**, on the pre-fix panel, through `vitest run` — the runner
// the suite actually uses, not a hand call (hard-won law 7):
//
//   H1  AssertionError: expected 'What this unit is priced on today. Th…'
//       to contain '1 Jun 2026'
//   H1  AssertionError: expected [ '2026-06-01', '2026-09-01', …(1) ]
//       to deeply equal []          // the three stray shapes, named
//   H2  AssertionError: expected +0 to be 1
//       // the plan's floor sentence — nought copies of the new wording, and
//       // six copies of "No floor is set on this plan." where one belongs
//   H3  AssertionError: expected +0 to be 6
//       // not one [data-priced-on] cell existed
//
// The fifth case — a payload carrying no `priced_on` — passes on BOTH sides,
// correctly and deliberately: it asserts an absence that was already true, and
// it is here so a later lane cannot make the column guess.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import i18n from "@/i18n";

import { UnitPricingPanel } from "./UnitPricingPanel";
import type { UnitPricing } from "./UnitPricingPanel";

const TEST_TENANT = "brazosbend";
const UNIT_ID = "01a08246-3eaf-7b8a-a671-ee5928dd3fa4";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * `SCW-U-001 · Unit 1`, 101 Silver Creek Rd on the seeded `brazosbend` demo,
 * read off `GET /units/{id}/pricing` in a browser on 2026-09-09 and trimmed to
 * the blocks these three cases are about.
 *
 * ⚠ **THE THREE `0.00` BASES ARE THE POINT AND ARE NOT TIDIED AWAY.** Trash,
 * Solar and Fire are each priced some other way — the size band times the
 * count, or the capacity installed — so a zero there is CORRECT and reads as
 * broken. That is `BR-MET-1166` and it is what `H3` puts a column beside.
 */
function payload(): UnitPricing {
  return {
    unit: {
      id: UNIT_ID,
      unit_no: "SCW-U-001",
      label: "Unit 1",
      premise_no: "P-00007",
      premise_address: "101 Silver Creek Rd",
      rate_plan_id: "01a08246-3b59-756e-b172-398777b8e7ad",
      plan_effective_from: "2026-06-01",
      plan_locked: false,
    },
    plan: {
      id: "01a08246-3b59-756e-b172-398777b8e7ad",
      code: "SCW-RES",
      name: "Sample — Residential",
      description: null,
      status: "published",
      version: 1,
      effective_from: "2026-06-01",
      effective_to: null,
      base_charges: "20.0000",
      minimum_bill_amount: null,
      budget_billing: null,
      resolved_on: "2026-09-30",
    },
    plan_absent: null,
    period: {
      supplied: true,
      start: "2026-09-01",
      end: "2026-09-30",
      as_of: "2026-09-30",
      source: "supplied",
    },
    plan_history: { served: false, reason: "not_asked", tracks: null, stretches: [], splits_at: [] },
    services: [
      {
        service: "electric",
        name: "Electric",
        base_charge: "12.0000",
        currency: "USD",
        minimum_amount: null,
        priced_on: { shape: "size_bands", capacity_uom: null, size_count: 6 },
      },
      {
        service: "water",
        name: "Water",
        base_charge: "8.0000",
        currency: "USD",
        minimum_amount: null,
        priced_on: { shape: "size_bands", capacity_uom: null, size_count: 9 },
      },
      {
        service: "trash",
        name: "Trash",
        base_charge: "0.0000",
        currency: "USD",
        minimum_amount: null,
        priced_on: { shape: "size_bands", capacity_uom: null, size_count: 7 },
      },
      {
        service: "solar",
        name: "Solar",
        base_charge: "0.0000",
        currency: "USD",
        minimum_amount: null,
        priced_on: { shape: "capacity", capacity_uom: "kW", size_count: 10 },
      },
      {
        service: "fire",
        name: "Fire",
        base_charge: "0.0000",
        currency: "USD",
        minimum_amount: null,
        priced_on: { shape: "size_bands", capacity_uom: null, size_count: 6 },
      },
      {
        service: "sewer",
        name: "Sewer",
        base_charge: "9.0000",
        currency: "USD",
        minimum_amount: null,
        priced_on: { shape: "no_size_axis", capacity_uom: null, size_count: 0 },
      },
    ],
    rate_schedules: [],
    // ⚠ `plan` is an OBJECT with a null amount, which is what
    // `GET /units/{id}/pricing` actually answers — read off the running
    // product on 2026-09-09, not assumed from the type. It matters: the
    // gathered *Minimum charges* table is drawn only when SOME floor is set,
    // and the guard reads `plan?.amount`, so a fixture passing `plan: null`
    // renders a table the real payload never produces and quietly changes what
    // this case is counting.
    minimum_charges: { plan: { amount: null, source: "plan" }, services: [], schedules: [] },
    charge_codes: [],
    discounts: {
      offered: [],
      granted: { served: false, reason: "unit_has_no_account", tracks: null },
    },
    taxes: { jurisdiction_rules: [], attachments: [], narrowing: null },
    penalty_rule: null,
    contract: { served: false, reason: "not_built", tracks: null, change_request: "CR-020" },
    worked_month: {
      served: false,
      reason: "no_service_prices_a_plan_outside_a_bill_run",
      tracks: "OQ-363",
    },
  } as unknown as UnitPricing;
}

function draw(body: UnitPricing) {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      {/* `showPeriod` is what the staff Plan tab passes, and it is the mount
          that draws the two native date inputs `DEF-MET-4689` is about. */}
      <UnitPricingPanel unitId={UNIT_ID} t={t} client={client} showPeriod={true} />
    </QueryClientProvider>,
  );
}

/**
 * Every date-shaped run of characters in the rendered text, deduplicated.
 *
 * ⚠ **NO `\b` ANCHORS, AND THAT IS THE SECOND TIME THIS CHECK WAS LOOKING AT
 * THE WRONG THING.** `textContent` concatenates a label and its value with no
 * separator — `Effective from2026-06-01` — so `\b\d{4}` never matches, because
 * `m` and `2` are both word characters and there is no boundary between them.
 * The first draft therefore reported the pre-fix panel as holding TWO stray
 * shapes when it held three, and would have gone on missing every date that
 * abuts its own label. Lookarounds on DIGITS are what the shape actually
 * needs: they stop `2026-09-011` reading as a date and nothing else.
 */
function dateShapes(text: string): string[] {
  const found = new Set<string>();
  for (const m of text.matchAll(/(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)/g)) found.add(m[0]);
  for (const m of text.matchAll(/(?<!\d)\d{2}\/\d{2}\/\d{4}(?!\d)/g)) found.add(m[0]);
  for (const m of text.matchAll(/(?<!\d)\d{1,2} [A-Z][a-z]{2} \d{4}(?!\d)/g)) found.add(m[0]);
  return [...found].sort();
}

// ⚠ `DEF-MET-8839` — THE CLOCK IS PINNED. The period inputs default to the
// CURRENT month (`currentMonthPeriod(new Date())`), so on the real clock H1
// expected September and went red on 1 October. Pinned to the day the fixture
// above was read off the live endpoint; `Date` only, so `waitFor` and the
// query's promises still run on real timers.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-09-09T12:00:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("CR-089 wave H · the unit's Plan tab reads one way", () => {
  it("H1 · every date on the panel is a NAMED MONTH, and no numeric shape survives", async () => {
    const { container } = draw(payload());
    await waitFor(() => expect(screen.getByText("SCW-RES")).toBeInTheDocument());
    const text = container.textContent ?? "";

    // The three dates this panel prints, each in the one shape.
    expect(text).toContain("1 Jun 2026"); // the plan's Effective from
    expect(text).toContain("1 Sep 2026"); // the period, start
    expect(text).toContain("30 Sep 2026"); // the period, end

    // ⚠ THE ASSERTION THAT ACTUALLY CATCHES THIS DEFECT, and it is a
    // statement about the SCREEN rather than about any value on it: the
    // stored strings must be GONE from the text, not merely joined by a
    // prettier one. `2026-06-01` beside `1 Jun 2026` is the defect.
    expect(text).not.toContain("2026-06-01");
    expect(text).not.toContain("2026-09-01");
    expect(text).not.toContain("2026-09-30");
    expect(text).not.toContain("06/01/2026");

    // The native inputs still hold ISO — that is what the control's VALUE is
    // and changing it would break the picker. The named month is the line
    // beneath, which is the only place a reader can compare the two boxes.
    const inputs = [...container.querySelectorAll('input[type="date"]')];
    expect(inputs.map((el) => (el as HTMLInputElement).value)).toEqual([
      "2026-09-01",
      "2026-09-30",
    ]);
  });

  it("H1 · counted rather than eyeballed — the panel holds ONE date shape", async () => {
    const { container } = draw(payload());
    await waitFor(() => expect(screen.getByText("SCW-RES")).toBeInTheDocument());
    // Four shapes were what the Product Owner met. Every remaining date must
    // match `D MMM YYYY` and nothing else.
    // ⚠ **THE FAILURE HAS TO NAME WHAT IT FOUND** (hard-won law 7, habit 3).
    // A first draft asserted `every(...)` was `true` and failed with *expected
    // false to be true*, which tells a reader nothing about which shape leaked
    // through. This one prints the offending strings.
    const shapes = dateShapes(container.textContent ?? "");
    const notNamed = shapes.filter((one) => !/^\d{1,2} [A-Z][a-z]{2} \d{4}$/.test(one));
    expect(notNamed).toEqual([]);
    expect(shapes.length).toBeGreaterThan(0);
  });

  it("H2 · the floor sentence appears ONCE, and every service floor reads 'none'", async () => {
    const { container } = draw(payload());
    await waitFor(() => expect(screen.getByText("SCW-RES")).toBeInTheDocument());
    const text = container.textContent ?? "";

    const sentence = t("metering.unit.pricing.floorAbsent");
    const copies = text.split(sentence).length - 1;
    expect(copies).toBe(1);

    // Six services, six short floors — plus nothing else, because the
    // gathered Minimum charges table is absent when no floor is set anywhere.
    // ⚠ **COUNTED OVER THE ROWS, NOT OVER THE TEXT.** The first draft of this
    // case counted occurrences of the word in `textContent` and read SEVEN
    // where six were drawn — "none" is an ordinary English word and it is a
    // substring of other copy on the same panel. A count that can be inflated
    // by a neighbouring sentence cannot tell a pass from a fail, which is the
    // shape hard-won law 7 keeps naming.
    const shortWord = t("metering.unit.pricing.floorNone");
    const serviceRows = [...container.querySelectorAll("[data-plan-service]")];
    expect(serviceRows.length).toBe(6);
    const floorCells = serviceRows.map((row) => {
      const cells = row.querySelectorAll("td");
      return (cells[cells.length - 1].textContent ?? "").trim();
    });
    expect(floorCells).toEqual(Array(6).fill(shortWord));

    // The sentence the panel used to print seven times is gone from it. The
    // KEY is still `PlanDetail`'s, where it is printed once and is right.
    expect(text).not.toContain("No floor is set on this plan.");
  });

  it("H3 · a zero base says what the service is priced on, on the same row", async () => {
    const { container } = draw(payload());
    await waitFor(() => expect(screen.getByText("SCW-RES")).toBeInTheDocument());

    const cells = [...container.querySelectorAll("[data-priced-on]")];
    expect(cells.length).toBe(6);

    const row = (service: string): HTMLElement =>
      container.querySelector(`[data-plan-service="${service}"]`) as HTMLElement;

    // Fire's zero is CORRECT — the size of the line picks the price and the
    // count multiplies it (CR-063) — and this is the sentence that says so.
    expect(row("fire").textContent).toContain("$0.00");
    expect(row("fire").querySelector("[data-priced-on]")?.getAttribute("data-priced-on")).toBe(
      "size_bands",
    );
    expect(row("trash").querySelector("[data-priced-on]")?.getAttribute("data-priced-on")).toBe(
      "size_bands",
    );
    // Solar sums a capacity rather than banding, and names its unit.
    expect(row("solar").querySelector("[data-priced-on]")?.getAttribute("data-priced-on")).toBe(
      "capacity",
    );
    expect(row("solar").textContent).toContain("kW");
    // Sewer is ruled to have no size class at all — a third fact, said as one.
    expect(row("sewer").querySelector("[data-priced-on]")?.getAttribute("data-priced-on")).toBe(
      "no_size_axis",
    );
  });

  it("H3 · a payload with no `priced_on` renders the row and no cell — never a guess", async () => {
    // The mirror case, and it is the one an older cached response produces.
    // An absence is not a shape: the column is empty for that row rather than
    // being filled with whichever sentence looks most likely.
    const stale = payload();
    stale.services = stale.services.map((row) => {
      const rest = { ...row };
      delete rest.priced_on;
      return rest;
    });
    const { container } = draw(stale);
    await waitFor(() => expect(screen.getByText("SCW-RES")).toBeInTheDocument());
    expect(container.querySelectorAll("[data-priced-on]").length).toBe(0);
    expect(container.querySelector('[data-plan-service="fire"]')?.textContent).toContain("$0.00");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 §6 wave H (H1/H2/H3) · DEF-MET-4689 · DEF-MET-4693 ·
//         BR-MET-1166 · BR-MET-1167 · B14 rule 32
// screens: S15 (PRM-03, Plan tab)
// generated: 2026-09-09 by the CR-089 wave H lane
// gates: RED PROVED FIRST through `vitest run`, the harness that runs it — the
//        three quoted failures are in this file's header. The date, floor and
//        column checks were each shown to fail on the pre-fix panel before the
//        fix was written.
// exceptions: (1) jsdom rather than the node-environment suites next door,
//     because two cases read `input[type=date]` VALUES and one counts shapes
//     across the settled DOM · (2) the fixture is cast through `unknown`: it
//     carries the blocks these cases read and empty lists for the eleven this
//     panel also draws, which is a trimmed real response and not a new contract
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
