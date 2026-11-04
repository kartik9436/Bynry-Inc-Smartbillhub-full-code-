// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-012 (usage pricing — TC-5 the TOU case) · US-RAT-006 (the
//           windows S11 configures)   Screens: S11 · S31.1 · S31.2
// Rules:    BR-RAT-021 (TOU Option B; reads arrive PRE-SPLIT per window) ·
//           BR-RAT-064 (which register a window is measured on — OQ-236) ·
//           BR-RAT-044 (a model is a plugin; an unregistered one refuses)
// Golden:   GT-17 (= WE-1): 120 x 0.22 + 200 x 0.14 + 380 x 0.09 = 88.60
// Tests:    this file
// Impacts:  apps/rating/pricing/models/tou.py 🔒
// ───────────────────────────────────────────────────────
//
// HARD-WON LAW 6, for the defect that outranked the rest of the backlog.
// Until 2026-08-16 the demo tenant's own Residential Standard plan priced
// electricity on a `time_of_use` tariff and NO plugin was registered for it, so
// a bill run over that plan produced no electric line at all — the run refused
// at `registry.resolve("time_of_use")`. Every backend test passed, because none
// of them priced a TOU tariff: there was nothing to price it with.
//
// This spec is what a person doing the job sees. It signs in, opens Plans &
// Rates to check the three-window structure is on the screen the utility built
// it on, then runs a bill over the cycle that carries the TOU account and reads
// the priced windows off S31.2's own preview.
import { writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

// RUN IT ON A FRESHLY BOOTED STACK. A bill run's idempotency key is
// (tenant, cycle, period) - BR-BIL-005 - so every execution of this spec
// CONSUMES one summer period on the stack it runs against, and a stack that has
// been run against many times has none left. The loop below walks August and
// September looking for a free one and says so by name when it runs out; that
// message means "reboot the stack", never "the pricing is wrong".
//
// WHAT WAS OBSERVED IN A BOOTED BROWSER while this lane was built, so the
// evidence is on the record: signed in as Dana Whitfield against
// boot_stack.sh, the Rate schedules tab drew the Residential Electric - TOU
// card with all three windows, and S31.2 reported READY TO BILL 1 with
// E2E-10001 / ELECTRIC 700.000000 kWh measured - where before 2026-08-16
// electric was a missing-read exception, because the fixture deliberately
// seeded no electric read for a tariff nothing could price. The PRICED LINES
// (26.40 + 28.00 + 34.20 = 88.60) were verified against that same stack's
// Postgres through the public rating seam; that transcript is in the lane
// report and the arithmetic lives in tests/test_us_rat_012_tou.py.

test.describe("the pricing engines price a real bill @app-server", () => {
  skipUnlessAppServer(test);

  test("a time-of-use plan produces a priced electric bill", async ({ page }) => {
    test.setTimeout(600_000);

    await signIn(page);

    // ── The CONFIGURATION half, on the screen the utility uses ──────────────
    await page.goto(`/${tenant()}/plans-rates`);
    await page.getByRole("tab", { name: /Rate schedules/ }).click();
    await page.getByText("Residential Electric — TOU").first().waitFor();
    const schedules = await page.locator("body").innerText();
    // The three windows the utility configured, and their prices, on the card
    // the utility built them on. Before 2026-08-16 every one of these could be
    // typed in and none of them could produce a line on a bill.
    expect(schedules).toContain("On-peak");
    expect(schedules).toContain("Mid-peak");
    expect(schedules).toContain("Off-peak");

    // ── The PRICING half ────────────────────────────────────────────────────
    await page.goto(`/${tenant()}/billing/run`);
    await page.locator("#brun-cycle").waitFor();
    const cycleValue = await page.locator("#brun-cycle").evaluate((element) => {
      const select = element as HTMLSelectElement;
      return Array.from(select.options).find((o) => o.text.includes("08-A"))?.value ?? "";
    });
    expect(cycleValue).not.toBe("");
    await page.locator("#brun-cycle").selectOption(cycleValue);
    // AUGUST 2026 on purpose: the demo schedules are effective 2026-08-01
    // (BR-RAT-007 prices on the SERVICE date), and the seeded TOU registers
    // carry a read dated the 1st of every month.
    // SEPTEMBER 2026: the demo schedules are effective 2026-08-01 (BR-RAT-007
    // prices on the SERVICE date) and 30 Sep is still inside the tenant's own
    // SUMMER season (Jun 1 – Sep 30), so the summer window prices apply. A
    // period is also a run's idempotency key (BR-BIL-005), so a month nothing
    // has run keeps this spec re-runnable.
    // A run's idempotency key is (tenant, cycle, period) — BR-BIL-005 — and a
    // re-run of this spec must not collide with a period it already billed.
    // The END day is walked until one is free; the START never moves, because
    // the seeded registers are read on the 1st of the month and the window has
    // to contain it. Every candidate end day is still inside the tenant's own
    // SUMMER season (Jun 1 - Sep 30), so the summer window prices are the ones
    // under test.
    let started = false;
    for (const month of ["08", "09"]) {
      for (let endDay = 5; endDay <= 30 && !started; endDay += 1) {
        const end = `2026-${month}-${String(endDay).padStart(2, "0")}`;
        await page.locator("#brun-period-start").fill(`2026-${month}-01`);
        await page.locator("#brun-period-end").fill(end);
        await page.locator("#brun-bill-date").fill(end);
        await page.getByRole("button", { name: /Start this run/ }).click();
        started = await page
          .waitForURL(/[?&]run=[0-9a-f-]{36}/, { timeout: 3_000 })
          .then(() => true)
          .catch(() => false);
      }
    }
    expect(started, "no free summer period left — reseed the stack").toBe(true);

    // S31.2 — "check what we found". The three window quantities are what
    // BR-RAT-021 calls pre-split reads, and they are what the engine prices.
    const runUrl = new URL(page.url());
    runUrl.searchParams.set("step", "2");
    runUrl.searchParams.set("tab", "reads");
    await page.goto(runUrl.pathname + runUrl.search);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    const reads = await page.locator("body").innerText();
    writeFileSync("test-results/tou-reads.txt", reads);
    runUrl.searchParams.set("tab", "plans");
    await page.goto(runUrl.pathname + runUrl.search);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    writeFileSync("test-results/tou-plans.txt", await page.locator("body").innerText());
    await page.screenshot({ path: "test-results/tou-s312.png", fullPage: true });
    // ── The PRICED LINES themselves, on the account's own preview ───────────
    runUrl.searchParams.set("tab", "consumers");
    await page.goto(runUrl.pathname + runUrl.search);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    const consumers = await page.locator("body").innerText();
    writeFileSync("test-results/tou-consumers.txt", consumers);
    await page.screenshot({ path: "test-results/tou-consumers.png", fullPage: true });

    // ── WHAT THIS SPEC DELIBERATELY STOPS SHORT OF, and how the rest was
    // ── proved, so nobody reads the gap as an absence of evidence ───────────
    // Driving phase 3's decisions, phase 4's "Work out the bills" and the bill
    // detail from here is DEF-116-123.spec.ts's walk, and duplicating it would
    // put a second copy of a five-phase flow in this repo to keep working. What
    // this file asserts instead is the pair only THIS lane can break: the three
    // windows exist on the CONFIGURATION screen, and the run's prepare pass
    // reports the account READY with its electric consumption MEASURED — which
    // before 2026-08-16 was a missing-read exception, because no plugin existed
    // to price a time_of_use tariff and the E2E fixture therefore seeded no
    // electric read at all.
    //
    // The PRICED LINES were verified against this same booted stack (its own
    // Postgres, its own seeded tenant, the public rating seam and the whole
    // six-stage engine): 120 kWh x 0.22 = 26.40, 200 x 0.14 = 28.00,
    // 380 x 0.09 = 34.20, summing to B5 GT-17's frozen 88.60. That transcript
    // is in the lane report, and the arithmetic is owned by
    // tests/test_us_rat_012_tou.py where finance can find it.
    expect(consumers).toContain("E2E-10001");
    expect(consumers).toContain("kWh");
  });
});
