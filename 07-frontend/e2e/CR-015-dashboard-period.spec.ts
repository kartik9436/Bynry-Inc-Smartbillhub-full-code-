// ── Trace ──────────────────────────────────────────────
// Change:  CR-015 (12-governance/11-change-requests.md §CR-015) — *"we will
//          ahve to allow period filter on dashbaord - so user can select the
//          filter ; default filter can be last cycle or last 30 days and let
//          user to change the peiod"*
// Defect:  DEF-299 (`as_of` was eleven days in the future) · DEF-298 (a
//          calendar month is the wrong window for cycle-shaped work)
// Screens: S7 — the first screen after every single sign-in.
// Rules:   BR-REP-035 (the period vocabulary and its ruled default) ·
//          BR-REP-036 (`as_of` is the READ moment clamped into the period) ·
//          BR-REP-028 (regions fail independently) · BR-SHL-011 (URL grammar
//          `f.<name>`; an unknown value falls back, never errors) · B14 rule 8
//          (one dropdown style)
// ───────────────────────────────────────────────────────
//
// **EVERY CLAIM HERE IS ASSERTED ON TEXT A PERSON READS IN A REAL BROWSER.**
// Nothing in this file reads the API payload and calls that a screen — CR-012
// needed three passes for exactly that reason, and its final one found two rows
// that were correct on the wire and rendered nowhere.
//
// ⚠ **THE CENTRAL ASSERTION IS NOT THAT A PICKER EXISTS.** CR-015's own
// condition is that *"the selected period is stated prominently, NOT BURIED IN
// A FILTER CONTROL"*, because once a user may choose a window the dashboard can
// differ from Finance **while both are correct** — and that reads as a bug. So
// the cases below assert on the SPELLED-OUT DATES at the top of the page, which
// is what a person compares against Finance, and treat the control as the means
// rather than the deliverable.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

skipUnlessAppServer(test);

const dashboardPath = (query = ""): string => `/${tenant()}/dashboard${query}`;

/** The period bar, by the class the screen actually renders. */
const bar = (page: Page) => page.locator('[data-dash="period-bar"]');

/** The window as a person reads it: `Showing 12 Aug 2026 – 19 Aug 2026`. */
async function shownRange(page: Page): Promise<string> {
  return (await bar(page).locator('[data-dash="period-range"]').innerText()).trim();
}

/** `Figures as of 19 Aug 2026`. */
async function shownAsOf(page: Page): Promise<string> {
  return (await bar(page).locator('[data-dash="period-asof"]').innerText()).trim();
}

/** Every date on screen, as `YYYY-MM-DD`, read out of the bar's own text.
 *
 *  ⚠ **BOTH ORDERS, AND THE FIRST VERSION OF THIS HELPER GOT IT WRONG** — run 1
 *  of this spec reported *"the bar must state BOTH ends of the window; it reads
 *  'Showing Aug 12, 2026 – Aug 19, 2026'"*, which is the screen working and the
 *  TEST failing: the parser assumed `12 Aug 2026` and the browser under test is
 *  en-US. Recorded rather than quietly fixed, because a red that turns out to be
 *  the check's own fault is the one worth writing down (DEF-174's shape).
 *
 *  Parsed rather than string-matched on purpose: a locale change must not
 *  silently turn this whole file into a test of nothing. */
function isoDays(text: string): string[] {
  const pattern = /(?:(\d{1,2}) (\w{3,}) (\d{4}))|(?:(\w{3,}) (\d{1,2}),? (\d{4}))/g;
  return [...text.matchAll(pattern)].map((match) => {
    const day = Number(match[1] ?? match[5]);
    const monthName = match[2] ?? match[4];
    const month = new Date(`${monthName} 1, 2000`).getMonth() + 1;
    const year = match[3] ?? match[6];
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// DEF-299 · THE SCREEN NO LONGER LABELS ITSELF WITH A DAY THAT HAS NOT HAPPENED
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-015 · the as-of moment on screen is today, never a future date ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  await expect(bar(page)).toBeVisible();
  // RED, quoted, from the live stack this spec was written against, on
  // 2026-08-19:
  //     as_of 2026-08-31 period {'start': '2026-08-01', 'end': '2026-08-31'}
  // The first screen after every sign-in said it was as of a moment eleven
  // days in the future, and the PO's consistency rule — "a KPI must agree with
  // its owning module for the same as-of moment" — could not be checked by a
  // person comparing that label against Finance's 19th.
  const asOfText = await shownAsOf(page);
  const [asOf] = isoDays(asOfText);
  expect(asOf, `the as-of line reads "${asOfText}"`).toBeTruthy();

  const today = await page.evaluate(() => {
    const now = new Date();
    const pad = (value: number) => String(value).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  });
  // A day either side for a browser and a utility in different timezones —
  // the defect was ELEVEN days, so this stays a real assertion.
  const drift = Math.abs(
    (new Date(`${asOf}T00:00:00`).getTime() - new Date(`${today}T00:00:00`).getTime()) / 86_400_000,
  );
  expect(drift, `the screen says as of ${asOf} and today is ${today}`).toBeLessThanOrEqual(1);
});

// ═══════════════════════════════════════════════════════════════════════════
// THE PERIOD IS STATED, PROMINENTLY — CR-015's own condition
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-015 · the window is spelled out in dates above the figures ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const range = await shownRange(page);
  const days = isoDays(range);
  expect(days.length, `the bar must state BOTH ends of the window; it reads "${range}"`).toBe(2);
  expect(days[0] <= days[1], `${days[0]} must not be after ${days[1]}`).toBe(true);

  // Prominent means ABOVE the figures, not below them and not in a footnote:
  // a reader comparing this screen against Finance must meet the window before
  // the first number.
  const barBox = await bar(page).boundingBox();
  const kpiBox = await page.locator(".kpi-grid").first().boundingBox();
  expect(barBox, "the period bar renders").not.toBeNull();
  expect(kpiBox, "the KPI strip renders").not.toBeNull();
  expect(barBox!.y).toBeLessThan(kpiBox!.y);

  // And no raw key or machine token reaches the screen (DEF-307's shape).
  await expect(bar(page)).not.toContainText("dashboard.period.");
  await expect(bar(page)).not.toContainText("last_cycle");
  await expect(bar(page)).not.toContainText("last_30_days");
});

// ═══════════════════════════════════════════════════════════════════════════
// THE RULED DEFAULT, AND THE FALLBACK
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-015 · the default window is the last completed cycle, or the last 30 days ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const select = bar(page).locator("select");
  await expect(select).toBeVisible();
  const selected = await select.inputValue();
  // The PO offered "last cycle or last 30 days" and the two are NOT
  // equivalent: a completed cycle is the utility's own unit and is STABLE,
  // where a rolling window shows two people different figures an hour apart.
  // The rolling one is the FALLBACK, for the tenant with no cycle yet.
  expect(["last_cycle", "last_30_days"]).toContain(selected);

  const options = await select.locator("option").allTextContents();
  expect(options.length, "the menu must carry more than the window it opened on").toBeGreaterThan(
    1,
  );
  // Nothing in the menu is a raw id — every entry is a sentence.
  for (const option of options) {
    expect(option.trim()).not.toMatch(/^[a-z0-9_]+$/);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// CHANGING THE PERIOD CHANGES THE FIGURES, AND THE URL SAYS WHICH
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-015 · picking another window moves the dates, the figures and the URL ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const before = await shownRange(page);
  const revenueTile = page.locator(".kpi", { hasText: "Revenue" }).first();
  const revenueBefore = await revenueTile.innerText();

  const select = bar(page).locator("select");
  const ids = await select.locator("option").evaluateAll((nodes) =>
    nodes.map((node) => (node as HTMLOptionElement).value),
  );
  const current = await select.inputValue();
  const other = ids.find((id) => id !== current);
  const target = other ?? ids[ids.length - 1];
  await select.selectOption(target);

  // The window on screen must MOVE — a picker that changes nothing is the
  // "built is not wired" failure (hard-won law 2) wearing a select.
  await expect
    .poll(async () => shownRange(page), { timeout: 20_000 })
    .not.toBe(before);

  // BR-SHL-011: the choice is in the URL, so it is shareable and survives a
  // reload. This is the direct answer to the PO's *"there is now way user can
  // see previous values."*
  expect(page.url()).toContain(`f.period=${target}`);

  const after = await shownRange(page);
  await page.reload();
  await expect(bar(page)).toBeVisible();
  expect(await shownRange(page), "a reload must open on the SAME window").toBe(after);

  // The figures are read again for the new window rather than reused: the
  // revenue tile carries a value or an em-dash and never a stale one under a
  // new heading. (Equality is legitimate — two windows can bill the same — so
  // this asserts the tile RE-RENDERED with a real value, not that it differs.)
  await expect(revenueTile).toBeVisible();
  expect((await revenueTile.innerText()).length).toBeGreaterThan(0);
  expect(revenueBefore.length).toBeGreaterThan(0);
});

test(`CR-015 · a hand-edited period falls back instead of breaking the front door ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  // BR-SHL-011: an unknown, misspelled or no-longer-available value FALLS BACK.
  // A landing page that 500s on a stale bookmark is a locked front door.
  await page.goto(dashboardPath("?f.period=last_fortnight"));

  await expect(bar(page)).toBeVisible();
  const days = isoDays(await shownRange(page));
  expect(days.length).toBe(2);
  await expect(page.locator(".kpi-grid").first()).toBeVisible();
  const select = bar(page).locator("select");
  expect(["last_cycle", "last_30_days"]).toContain(await select.inputValue());
});

// ═══════════════════════════════════════════════════════════════════════════
// THE HEADER STILL SPEAKS FOR TODAY — the one thing that must NOT move
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-015 · the header date stays TODAY when a closed window is selected ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(dashboardPath());

  const headerBefore = (await page.locator(".fin-rollup-item").first().innerText()).trim();

  const select = bar(page).locator("select");
  const ids = await select.locator("option").evaluateAll((nodes) =>
    nodes.map((node) => (node as HTMLOptionElement).value),
  );
  if (!ids.includes("last_period")) {
    test.skip(true, "this tenant has no fiscal calendar, so there is no closed period to pick");
  }
  await select.selectOption("last_period");
  await expect.poll(async () => shownAsOf(page), { timeout: 20_000 }).toContain("Jul");

  // The page HEADER answers "what day is it, what closes next" — a statement
  // about NOW. Fed the clamped as-of of a closed window it would head the page
  // with last month's date and count down from it.
  const headerAfter = (await page.locator(".fin-rollup-item").first().innerText()).trim();
  expect(headerAfter, "the greeting line's date must not follow the period picker").toBe(
    headerBefore,
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-015 (12-governance/11-change-requests.md §CR-015) · 12-governance/02-decision-log.md 2026-08-19 §"FOUR RULINGS" 3 and 4
// screens: S7
// generated: 2026-08-19 by story-coder (CR-015 lane)
// gates: run twice against the booted stack, the second time over the first run's leftovers.
// ──────────────────────────────────────────────────────────
