// ── Trace ──────────────────────────────────────────────
// Journey:  J70 — the one-time bill, redesigned (E1–E11) + the PO's scenarios of
//           2026-09-30 (P1–P6) · 08-qa/01-e2e/journeys/J70-one-time-bill-redesign.md
// Stories:  US-BIL-010, US-BIL-011, US-BIL-012, US-BIL-013, US-BIL-014,
//           US-BIL-032, US-BIL-033, US-BIL-034, US-BIL-035
// Plan:     04-docs/05-modules/07-billing/12-one-time-bill-build-plan.md E1–E11
// Drawing:  05-prototype/one-time-bill-2026-09-30/ (the E11 baseline)
// Seed:     10-scripts/seed_j70_one_time_bill.py (on top of `manage.py seed_demo`)
// ───────────────────────────────────────────────────────
//
// HOW TO RUN IT. Against a stack whose database was migrated, `seed_demo`-ed and
// then seeded by `10-scripts/seed_j70_one_time_bill.py` — and RESET to that
// state before each viewport, because the journeys send real bills (E8 needs
// E1's bill to exist; a second pass over the same database meets E1's own
// bill as a duplicate):
//
//   E2E_VIEWPORT=1440 E2E_BASE_URL=http://127.0.0.1:<web> npx playwright test e2e/J70-one-time-bill.spec.ts
//   (reset the database)
//   E2E_VIEWPORT=1280 E2E_BASE_URL=… npx playwright test e2e/J70-one-time-bill.spec.ts
//
// Screens land in 08-qa/screens/one-time-bill-e2e-2026-09-30/, named after the
// D1 image of the same state (`1440-03-Interim-2-services.png` …) so E11 is a
// side-by-side, file for file.
//
// ⚠ EVERY READING IS TYPED ON STEP 2, AS DESIGNED (2026-09-30 defect-fix lane).
// Until DEF-BIL-8300 was fixed, step 1 could not reach step 2 for an account
// whose meters had no reading in the period and this spec saved the readings
// through `/read-batches` first. That workaround is GONE: step 1 now warns how
// many meters need a reading and continues, the clerk types them on step 2,
// and the page saves them through Meter Reads on step 2's Continue.
//
// ⚠ AND ON EVERY STEP: the frame's generic "This step isn't finished" line
// never stands alone (DEF-BIL-8321) — `neverGenericAlone` after each Continue.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SHOTS = "../08-qa/screens/one-time-bill-e2e-2026-09-30";
const UNIT = (letter: string) => new RegExp(`Unit ${letter}(?:Active|Closed|Pending|\\s|$)`);

// ── helpers ──────────────────────────────────────────────────────────────────

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForTimeout(400);
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${WIDTH}-${name}.png`, fullPage: true });
}

async function openKind(page: Page, kind: string): Promise<void> {
  await page.goto(`/${tenant()}/billing/one-time?kind=${kind}`);
  await expect(page.locator("[data-screen=one-time-bill]")).toBeVisible({ timeout: 30_000 });
}

/** The searchable dropdown: type, wait for the list, pick by the unit label. */
async function pickAccount(page: Page, term: string, unit: RegExp): Promise<void> {
  const combo = page.getByRole("combobox", { name: /Find account/ });
  await combo.fill(term);
  await expect(page.getByRole("option").first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("option").filter({ hasText: unit }).first().click();
  await expect(page.locator("[data-otb-panel=account]")).toContainText(term.split(" ")[0]);
}

/** DEF-BIL-8281 — the card's Plan and Cycle fill from the ACCOUNT on selection. */
async function cardFilled(page: Page): Promise<void> {
  const card = page.locator("[data-facts=otb-account]");
  await expect(card.locator("[data-fact=plan]")).not.toContainText("—", { timeout: 15_000 });
  await expect(card.locator("[data-fact=cycle]")).toContainText(/days? to pay/);
  // DEF-BIL-8282 — never "0 services" before a preview answers.
  await expect(page.locator("[data-otb-summary]")).not.toContainText(/^0 services|\b0 services/);
}

async function continueStep(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await neverGenericAlone(page);
}

/** DEF-BIL-8321 — the frame's generic line may stand only beside the problems list. */
async function neverGenericAlone(page: Page): Promise<void> {
  await page.waitForTimeout(1200);
  const blocked = page.locator("[data-wizard=blocked]");
  if ((await blocked.count()) === 0) return;
  const text = (await blocked.innerText()).trim();
  if (!/This step isn't finished/.test(text)) return;
  await expect(page.locator("[data-otb-problems]"), "the generic line stood alone").toBeVisible();
}

async function onStep(page: Page, n: number, timeout = 30_000): Promise<boolean> {
  try {
    await expect(page.locator(`[data-wizard-step="${n}"][data-state=active]`)).toBeVisible({ timeout });
    return true;
  } catch {
    return false;
  }
}

interface Read {
  meter: string;
  value: string;
  /** A first bill's move-in value, typed in the Previous column. */
  moveIn?: boolean;
}

/** Step 1 → 2 the designed way: step 1 continues, then each reading is typed. */
async function reachServices(page: Page, reads: Read[], shot1?: string): Promise<void> {
  if (reads.length > 0) {
    // DEF-BIL-8300 — step 1 says the meters need a reading and goes on.
    await expect(page.locator("[data-otb-waiting-readings]")).toBeVisible({ timeout: 30_000 });
  }
  if (shot1) await shot(page, shot1);
  await continueStep(page);
  expect(await onStep(page, 2, 45_000), "DEF-BIL-8300: step 1 reaches Services").toBe(true);
  for (const read of reads) {
    const role = read.moveIn ? "move_in" : "current";
    const input = page.locator(`[data-reading-row='${read.meter}'] input[id^='reading-'][id*='|${role}|']`).first();
    await input.fill(read.value);
  }
  if (reads.length > 0) await page.waitForTimeout(1500);
}

async function reviewAndSend(page: Page, name: { review: string; send: string; ticked?: string; sent?: string }) {
  await continueStep(page); // Services → Review (saves typed readings through Meter Reads)
  expect(await onStep(page, 3, 60_000), "Review").toBe(true);
  await expect(page.locator("[data-otb-bill]")).toBeVisible();
  const bill = page.locator("[data-otb-bill]");
  await expect.soft(bill, "DEF-BIL-8303: a 2% tax does not print as 0.02%").not.toContainText("0.02%");
  await expect
    .soft(bill, "DEF-BIL-8304: sewer's rate is $5.00 per kgal, not 5.00%")
    .not.toContainText(/Share of service[^$]*5\.00%/);
  await expect.soft(bill, "DEF-BIL-8302: the unit label prints once").not.toContainText(/(Unit [A-H]) · \1/);
  await expect.soft(bill, "DEF-BIL-8315: the header names the bill").toContainText(/bill · draft/i);
  await shot(page, name.review);
  await continueStep(page); // Review → Send (the draft is made here)
  expect(await onStep(page, 4, 60_000), "Send").toBe(true);
  const send = page.getByRole("button", { name: /^Send .* bill$/ });
  await expect(send).toBeDisabled();
  await shot(page, name.send);
  await tickAllFive(page, send);
  await expect(send).toBeEnabled();
  if (name.ticked) await shot(page, name.ticked);
  await send.click();
  await expect(page.locator("[data-otb-sent]")).toBeVisible({ timeout: 60_000 });
  if (name.sent) await shot(page, name.sent);
  return (await page.locator("[data-otb-sent]").innerText()).trim();
}

/** PO 2026-09-30, option B — the Send card's FIVE release confirmations. Send
 *  stays shut until the fifth is ticked; the retired single tick is gone. */
async function tickAllFive(page: Page, send: Locator): Promise<void> {
  await expect(page.locator("#otb-acknowledged"), "the one-tick box is retired").toHaveCount(0);
  const ids = ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"];
  for (const id of ids) {
    await expect(send, `Send is shut before ${id} is ticked`).toBeDisabled();
    await page.locator(`#otb-confirm-${id}`).check({ force: true });
  }
}

async function fillPeriods(page: Page, periods: string[][]): Promise<void> {
  for (let i = 0; i < periods.length; i++) {
    if (i > 0) await page.getByRole("button", { name: "Add period" }).click();
    await page.locator(`[id='sub_periods[${i}].period_start']`).fill(periods[i][0]);
    await page.locator(`[id='sub_periods[${i}].period_end']`).fill(periods[i][1]);
  }
}

// ── the journeys ─────────────────────────────────────────────────────────────

test.describe(`J70 — the one-time bill at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "420000"));

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  test("E7 · problems: every step-1 problem at once, each on its field", async ({ page }) => {
    await openKind(page, "interim");
    await expect(page.locator("[data-otb-kinds] button")).toHaveCount(6);
    await expect(page.locator("[data-otb-kinds]")).toContainText(
      /Interim.*First bill.*Final.*Catch-up.*Penalty \/ theft.*Fee/s,
    );
    for (const step of ["Account", "Services", "Review", "Send"]) {
      await expect(page.locator("[data-wizard=rail]")).toContainText(step);
    }
    await pickAccount(page, "Alvarez", UNIT("A"));
    await cardFilled(page);
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-08-20");
    await page.locator("#due_days").fill("");
    await continueStep(page);
    const banner = page.locator("[data-otb-problems]");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText("Fix 2 things to continue.");
    await expect(page.locator(".field:has(#period_end)")).toContainText("Ends before it starts.");
    await expect(page.locator(".field:has(#due_days)")).toContainText("Enter days to pay.");
    // DEF-BIL-8317 — the fields with a problem are marked (and tinted).
    await expect(page.locator("#period_end")).toHaveClass(/input-invalid/);
    await expect(page.locator("#due_days")).toHaveClass(/input-invalid/);
    expect(await onStep(page, 1, 2_000)).toBe(true);
    await shot(page, "33-state-problems-Interim");

    // The catch-up pair: no reason, a period that ends before it starts.
    await page.locator("[data-otb-kinds] button[data-kind=backbill]").click();
    await page.locator("#sub_periods\\[0\\]\\.period_start").fill("2026-08-31");
    await page.locator("#sub_periods\\[0\\]\\.period_end").fill("2026-08-01");
    await page.locator("#due_days").fill("");
    await continueStep(page);
    await expect(banner).toBeVisible();
    await expect(page.locator(".field:has(#reason_code)")).toContainText("Choose a reason.");
    await expect(page.locator(".field:has([id='sub_periods[0].period_end'])")).toContainText(
      "Ends before it starts.",
    );
    await expect(banner).not.toContainText(/billing run|cycle/i);
    await shot(page, "34-state-problems-Catch-up");

    // Fee: no charge code.
    await page.locator("[data-otb-kinds] button[data-kind=fee]").click();
    await continueStep(page);
    await expect(page.locator(".field:has(#charge_code)")).toContainText("Choose a charge code.");
    await shot(page, "35-state-problems-Fee");
  });

  test("E10 · a reading lower than the last one is refused on its row", async ({ page }) => {
    await openKind(page, "interim");
    await pickAccount(page, "Alvarez", UNIT("A"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await reachServices(page, [{ meter: "W-10442", value: "480.0" }]);
    await expect(page.locator("[data-reading-row='W-10442']")).toContainText(/Below last reading|Refused/, {
      timeout: 20_000,
    });
    await continueStep(page);
    expect(await onStep(page, 2, 5_000), "Continue stays on step 2").toBe(true);
    await shot(page, "E10-below-last-reading");
  });

  test("E1 / P1 · interim with NO reading in the period: warn, continue, type on step 2, send", async ({
    page,
  }) => {
    await openKind(page, "interim");
    const combo = page.getByRole("combobox", { name: /Find account/ });
    await combo.fill("Alvarez");
    await expect(page.getByRole("option").first()).toBeVisible({ timeout: 20_000 });
    await expect(combo).toHaveAttribute("aria-expanded", "true");
    await shot(page, "02-Interim-1-account-dropdown-open");
    await page.getByRole("option").filter({ hasText: UNIT("A") }).first().click();
    await cardFilled(page);
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await expect(page.locator("#due_days")).toHaveValue("21", { timeout: 15_000 });
    const card = page.locator("[data-otb-panel=account]");
    await expect.soft(card, "DEF-BIL-8302: the unit label prints once").not.toContainText("Unit A · Unit A");
    await expect(page.locator("[data-otb-waiting-readings]")).toContainText("3 meters need a reading. Enter them next.", {
      timeout: 30_000,
    });
    await shot(page, "01-Interim-1-account");

    await reachServices(page, [
      { meter: "W-10442", value: "488.4" },
      { meter: "W-10443", value: "136.7" },
      { meter: "E-55120", value: "19020" },
    ]);
    const services = page.locator("[data-otb-panel=services]");
    await expect(services).toContainText("2 meters · W-10442, W-10443");
    await expect(services).toContainText("Billed · 2 meters");
    await expect(services).toContainText("Billed · base $0.00");
    await expect(services).toContainText("Billed · follows Water");
    await expect(services).toContainText(/Billed · 1 cart/);
    await expect(services.locator("tr", { hasText: "Gas" })).toContainText("Not in service");
    await expect(services.locator("tr", { hasText: "Fire" })).toContainText("Not in service");
    await expect(services.locator("tr", { hasText: "Broadband" })).toContainText("Not taken");
    // DEF-BIL-8316 — catalogue order: electric, water, …, trash, …
    await expect(services).toContainText(/Electric[\s\S]*Water[\s\S]*Sewer[\s\S]*Trash/);
    await expect(page.locator("[data-wizard=content]")).toContainText("No base charge for Electric. Billed $0.00.");
    const rates = page.locator("[data-otb-panel=rates]");
    await expect(rates).toContainText("Water · W-10442");
    await expect(rates).toContainText("$8.00 · BASE-W");
    await expect(rates).toContainText("$3.25 / kgal to 5 kgal");
    await expect(rates).toContainText("Per asset");
    await expect(rates).toContainText("Not set · $0.00");
    await expect(page.locator("[data-reading-row]")).toHaveCount(3);
    await expect(page.locator("[data-reading-row='W-10442']")).toContainText("Accepted", { timeout: 20_000 });
    await shot(page, "03-Interim-2-services");
    await services.getByRole("button", { expanded: true }).first().click();
    await rates.getByRole("button", { expanded: true }).first().click();
    await shot(page, "04-Interim-2-services-collapsed");

    await continueStep(page);
    expect(await onStep(page, 3, 60_000), "Review").toBe(true);
    const bill = page.locator("[data-otb-bill]");
    // DEF-BIL-8315 — one usage line per meter, base 1 × rate, trash per cart.
    await expect(bill.locator("tr", { hasText: "W-10442" }).filter({ hasText: "Usage" })).toHaveCount(1);
    await expect(bill).toContainText(/W-10442\s*Usage\s*6\.1 kgal\s*Tiered\s*\$21\.20/);
    await expect(bill).toContainText(/Base\s*1\s*\$8\.00\s*\$8\.00/);
    // Trash is ONE line per service, base inside it (PO "per service",
    // DEF-BIL-8151) — so "Per cart", and no separate base line.
    await expect(bill).toContainText(/Trash\s*1 cart\s*Per cart\s*1 cart/);
    await expect(bill).toContainText("Interim bill · draft");
    await page.getByRole("button", { name: "Back", exact: true }).click();
    expect(await onStep(page, 2, 20_000)).toBe(true);
    const sent = await reviewAndSend(page, {
      review: "05-Interim-3-review",
      send: "06-Interim-4-send",
      ticked: "07-Interim-4-send-ticked",
      sent: "08-Interim-4-sent",
    });
    expect(sent).toMatch(/Bill .+ sent/);
    expect(sent).toMatch(/Locked/);
  });

  test("E1b · the issued bill: two water meters, each line names its meter", async ({ page }) => {
    await page.goto(`/${tenant()}/billing`);
    const row = page.getByRole("row").filter({ hasText: "Maria Alvarez" }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await row.getByRole("link").first().click();
    await expect(page).toHaveURL(/\/billing\/bills\//);
    const main = page.locator("main");
    await expect(main).toContainText("Water $58.40", { timeout: 30_000 });
    await expect(main).not.toContainText(/Gas \$|Fire \$|Broadband \$/);
    await main.getByText(/See every charge/).first().click();
    await expect(page.locator("main")).toContainText("Water", { timeout: 30_000 });
    await expect(page.locator("main"), "DEF-BIL-8315: each water line names its meter").toContainText("W-10442");
    await expect(page.locator("main")).toContainText("W-10443");
    await shot(page, "E1-issued-bill-every-charge");
  });

  test("E8 · already billed: the banner stands over step 2 and names the bill", async ({ page }) => {
    await openKind(page, "interim");
    await pickAccount(page, "Alvarez", UNIT("A"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    const banner = page.locator("[data-otb-duplicate]");
    await expect(banner).toBeVisible({ timeout: 45_000 });
    await continueStep(page);
    // DEF-BIL-8319 — as drawn, over step 2 with the services below it.
    expect(await onStep(page, 2, 30_000), "already billed reaches step 2").toBe(true);
    await expect(banner).toContainText("Already billed for this period.");
    await expect(banner).toContainText(/BL-|\d{3,}/);
    await expect(banner.getByRole("link", { name: "Open that bill" })).toBeVisible();
    await shot(page, "36-state-already-billed");
  });

  test("E6 · fee: a reconnection fee, taxed once, the line names RECON", async ({ page }) => {
    await openKind(page, "fee");
    await pickAccount(page, "Alvarez", UNIT("A"));
    const recon = await page.locator("#charge_code option", { hasText: "Reconnection" }).first().getAttribute("value");
    await page.locator("#charge_code").selectOption(recon ?? "RECON");
    await shot(page, "29-Fee-1-account");
    await continueStep(page);
    expect(await onStep(page, 2, 45_000)).toBe(true);
    await expect(page.locator("[data-otb-panel=services]")).toHaveCount(0);
    await expect(page.locator("[data-reading-row]")).toHaveCount(0);
    const charge = page.locator("[data-otb-panel=charge]");
    await expect(charge).toContainText("RECON");
    await page.locator("#otb-note").fill("Reconnected Sep 30 after payment");
    await shot(page, "30-Fee-2-services");
    await continueStep(page);
    expect(await onStep(page, 3, 60_000)).toBe(true);
    const bill = page.locator("[data-otb-bill]");
    await expect(bill).toContainText("Reconnection fee");
    await expect(bill, "DEF-BIL-8312 / US-BIL-032 TC-3: the fee line names its code").toContainText("Fee · RECON");
    await expect.soft(bill, "B7: a taxable RECON is taxed").toContainText(/Tax/);
    await shot(page, "31-Fee-3-review");
    await continueStep(page);
    expect(await onStep(page, 4, 60_000)).toBe(true);
    await shot(page, "32-Fee-4-send");
    await tickAllFive(page, page.getByRole("button", { name: /^Send .* bill$/ }));
    await page.getByRole("button", { name: /^Send .* bill$/ }).click();
    await expect(page.locator("[data-otb-sent]")).toBeVisible({ timeout: 60_000 });
  });

  test("E2 / P3 · first bill: move-in date pre-filled, CHANGED by the clerk, deposit and CONN, send", async ({
    page,
  }) => {
    await openKind(page, "first");
    await pickAccount(page, "Alvarez", UNIT("C"));
    await cardFilled(page);
    const moveIn = page.locator("#period_start");
    await expect(moveIn).toHaveValue("2026-09-12", { timeout: 15_000 });
    await expect(moveIn).toBeEditable();
    // A date AFTER the recorded move-in read (Sep 12), so the bill has a
    // prior register to count from (a date before it leaves no prior read,
    // which BR-BIL-062 refuses by name).
    await moveIn.fill("2026-09-13");
    await expect(page.locator(".field:has(#period_start)")).toContainText(/Differs from the account \(.*\)/);
    await page.locator("#period_end").fill("2026-09-30");
    await reachServices(
      page,
      [
        { meter: "W-10443C", value: "128.9", moveIn: true },
        { meter: "W-10442C", value: "488.4" },
        { meter: "W-10443C", value: "136.7" },
        { meter: "E-55120C", value: "19020" },
      ],
      "09-First-bill-1-account",
    );
    const moveInPanel = page.locator("[data-otb-panel=move-in]");
    await expect(moveInPanel).toBeVisible();
    await expect(moveInPanel).toContainText("CONN");
    await expect(moveInPanel).toContainText(/Deposit/);
    await expect(moveInPanel).toContainText(/09\/13\/2026|Sep 13/);
    await shot(page, "10-First-bill-2-services");
    await page.locator("[data-otb-panel=services]").getByRole("button", { expanded: true }).first().click();
    await page.locator("[data-otb-panel=rates]").getByRole("button", { expanded: true }).first().click();
    await moveInPanel.getByRole("button", { expanded: true }).first().click();
    await shot(page, "11-First-bill-2-services-collapsed");
    await reviewAndSend(page, { review: "12-First-bill-3-review", send: "13-First-bill-4-send" });
  });

  test("P4 · first bill for an account with NO move-in date: Plan and Cycle shown, only the move-in asks", async ({
    page,
  }) => {
    await openKind(page, "first");
    await pickAccount(page, "Grant", UNIT("G"));
    await cardFilled(page);
    await expect(page.locator("#period_start")).toHaveValue("");
    await page.locator("#period_end").fill("2026-09-30");
    await continueStep(page);
    const banner = page.locator("[data-otb-problems]");
    await expect(banner).toContainText("Enter the move-in date.");
    await expect(banner).not.toContainText("Enter the period.");
    await expect(page.locator(".field:has(#period_start)")).toContainText("Enter the move-in date.");
    await expect(page.locator("#period_start")).toHaveClass(/input-invalid/);
    await banner.getByText("Enter the move-in date.").click();
    await expect(page.locator("#period_start")).toBeFocused();
    await shot(page, "P4-first-bill-no-move-in-date");
  });

  test("E3 / P2 · final with NO reading in the period: warn, continue, final readings typed, send", async ({
    page,
  }) => {
    await openKind(page, "final");
    await pickAccount(page, "Alvarez", UNIT("D"));
    await cardFilled(page);
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-18");
    await reachServices(
      page,
      [
        { meter: "W-10442D", value: "485.0" },
        { meter: "W-10443D", value: "133.0" },
        { meter: "E-55120D", value: "18700" },
      ],
      "14-Final-1-account",
    );
    const settlement = page.locator("[data-otb-panel=settlement]");
    await expect(settlement).toBeVisible();
    const collect = settlement.getByRole("radio", { name: "Collect" });
    if ((await collect.count()) > 0) {
      await collect.check({ force: true });
    } else {
      await expect(settlement).toContainText(/Refund due|Left to pay|Write-off/);
    }
    await shot(page, "15-Final-2-services");
    await page.locator("[data-otb-panel=services]").getByRole("button", { expanded: true }).first().click();
    await page.locator("[data-otb-panel=rates]").getByRole("button", { expanded: true }).first().click();
    await shot(page, "16-Final-2-services-collapsed");
    // DEF-BIL-8313 — a deposit-holding final bill is SENT (interest to the move-out day).
    const sent = await reviewAndSend(page, { review: "17-Final-3-review", send: "18-Final-4-send" });
    expect(sent).toMatch(/Bill .+ sent/);
  });

  test("E4 · catch-up: three periods across a price change, one estimated", async ({ page }) => {
    await openKind(page, "backbill");
    await pickAccount(page, "Alvarez", UNIT("E"));
    // Jul–Sep (was Jun–Aug): the demo seed closes August, and a catch-up dated
    // Aug 31 is refused by the books (BR-LED-006) — test data, as E5. July still
    // splits at the Jul 16 price change and W-10443E still has no July read.
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("MISSED");
    await shot(page, "19-Catch-up-1-account");
    await continueStep(page);
    expect(await onStep(page, 2, 45_000), "DEF-BIL-8310: the catch-up preview answers").toBe(true);
    const lastRows = page.locator("[data-reading-row] input[id^='reading-'][id*='|last_period|']");
    const typeInto = [
      ["W-10442E", "482.3"],
      ["W-10443E", "130.6"],
      ["E-55120E", "18420"],
    ];
    for (const [meter, value] of typeInto) {
      const input = page.locator(`[data-reading-row='${meter}'] input[id^='reading-'][id*='|last_period|']`).last();
      if ((await input.count()) > 0 && (await input.isEditable())) await input.fill(value);
    }
    expect(await lastRows.count()).toBeGreaterThan(0);
    const periodsPanel = page.locator("[data-otb-panel=periods]");
    await expect(periodsPanel).toBeVisible();
    await expect.soft(periodsPanel, "the July price change splits July").toContainText(/Jul|07\/16|split/i);
    await expect.soft(page.locator("[data-wizard=content]"), "W-10443E July is estimated").toContainText("Estimated");
    await shot(page, "20-Catch-up-2-services");
    await page.locator("[data-otb-panel=services]").getByRole("button", { expanded: true }).first().click();
    await page.locator("[data-otb-panel=rates]").getByRole("button", { expanded: true }).first().click();
    await shot(page, "21-Catch-up-2-services-collapsed");
    await reviewAndSend(page, { review: "22-Catch-up-3-review", send: "23-Catch-up-4-send" });
  });

  test("E5 · penalty: assessed reads, evidence, approver recorded; send is not refused for approval", async ({
    page,
  }) => {
    await openKind(page, "penalty");
    await pickAccount(page, "Alvarez", UNIT("F"));
    // Jul–Sep, so the bill is dated in an OPEN month: the demo seed closes
    // August, and a bill dated Aug 31 is refused by the books (test data, 2026-09-30).
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("TAMPER");
    const tamper = await page.locator("#charge_code option", { hasText: "Tamper" }).first().getAttribute("value");
    await page.locator("#charge_code").selectOption(tamper ?? "TAMPER");
    await shot(page, "24-Penalty-1-account");
    await continueStep(page);
    expect(await onStep(page, 2, 45_000), "DEF-BIL-8310: the penalty preview answers").toBe(true);
    await page.locator("#otb-evidence").fill("Bypass pipe found at meter W-10442F");
    // DEF-BIL-8305 — approval is RECORDED: a staff member, or a typed name.
    await expect(page.locator("[data-otb-panel=evidence]")).not.toContainText("Needs approval");
    await page.locator("#otb-approved-by").selectOption({ label: "Dana Whitfield" });
    await shot(page, "25-Penalty-2-services");
    await page.locator("[data-otb-panel=services]").getByRole("button", { expanded: true }).first().click();
    await page.locator("[data-otb-panel=rates]").getByRole("button", { expanded: true }).first().click();
    await shot(page, "26-Penalty-2-services-collapsed");
    const sent = await reviewAndSend(page, { review: "27-Penalty-3-review", send: "28-Penalty-4-send" });
    expect(sent, "PO 2026-09-30: approval is recorded, never a gate").toMatch(/Bill .+ sent/);
  });

  test("E9 · an account with no service agreements bills everything connected and warns", async ({ page }) => {
    await openKind(page, "interim");
    await pickAccount(page, "Brooks", UNIT("B"));
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await reachServices(page, [
      { meter: "W-10450", value: "215.0" },
      { meter: "E-55121", value: "10200" },
    ]);
    await expect(page.locator("[data-wizard=content]")).toContainText("No services on file. Billed all connected.");
    const services = page.locator("[data-otb-panel=services]");
    for (const name of ["Water", "Electric", "Trash"]) {
      await expect(services.locator("tr", { hasText: name }).first()).toContainText("Billed");
    }
    await shot(page, "E9-no-agreements-services");
    await reviewAndSend(page, { review: "E9-no-agreements-review", send: "E9-no-agreements-send" });
  });

  test("P5 · catch-up over Jul–Sep for an account with NO readings in those months", async ({ page }) => {
    await openKind(page, "backbill");
    await pickAccount(page, "Robert", UNIT("H"));
    await cardFilled(page);
    await fillPeriods(page, [
      ["2026-07-01", "2026-07-31"],
      ["2026-08-01", "2026-08-31"],
      ["2026-09-01", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption("MISSED");
    await continueStep(page);
    const reached = await onStep(page, 2, 45_000);
    await shot(page, "P5-catch-up-no-readings-step-1-or-2");
    expect(reached, "a catch-up with no readings reaches step 2 or names why").toBe(true);
    for (const [meter, value] of [
      ["W-10442H", "470.0"],
      ["W-10443H", "125.0"],
      ["E-55120H", "18500"],
    ]) {
      const input = page.locator(`[data-reading-row='${meter}'] input[id^='reading-'][id*='|last_period|']`).last();
      if ((await input.count()) > 0 && (await input.isEditable())) await input.fill(value);
    }
    await page.waitForTimeout(1500);
    await shot(page, "P5-catch-up-no-readings-services");
    await reviewAndSend(page, { review: "P5-catch-up-no-readings-review", send: "P5-catch-up-no-readings-send" });
  });

  test("P6 · penalty with the PO's overlapping periods names the row, then bills", async ({ page }) => {
    await openKind(page, "penalty");
    await pickAccount(page, "Robert", UNIT("H"));
    await fillPeriods(page, [
      ["2026-09-30", "2026-09-30"],
      ["2026-08-30", "2026-09-30"],
    ]);
    await page.locator("#reason_code").selectOption({ index: 1 });
    await page.locator("#due_days").fill("2");
    await continueStep(page);
    const banner = page.locator("[data-otb-problems]");
    await expect(banner).toContainText("Overlaps another period.");
    await expect(page.locator(".field:has([id='sub_periods[0].period_start'])")).toContainText(
      "Overlaps another period.",
    );
    await shot(page, "P6-penalty-overlapping-periods");
  });
});
