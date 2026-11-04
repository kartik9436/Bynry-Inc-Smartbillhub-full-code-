// ── Trace ──────────────────────────────────────────────
// Tracker:  BULK-CHG-56 (the clerk acceptance walk, U1–U7: E1–E11)
// Journey:  J72 — the bulk bill run, redesigned (E1–E11) ·
//           08-qa/01-e2e/journeys/J72-bulk-bill-run-redesign.md
// Stories:  US-BIL-036 … US-BIL-041 · US-BIL-005 · US-BIL-006
// Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md §E (E1–E11), D1
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/ (72 images, 36 states — the E11 baseline)
// Seed:     `manage.py seed_j72_bulk_run` (06-backend/apps/tenancy/management/commands/),
//           on top of `manage.py seed_demo`, on PostgreSQL
// ───────────────────────────────────────────────────────
//
// HOW TO RUN IT. Against a stack whose PostgreSQL database was migrated,
// `seed_demo`-ed and then `seed_j72_bulk_run`-ed, RESET to that state before
// each viewport (the walk creates the September run and, where the wiring is
// in, prices and sends it):
//
//   E2E_VIEWPORT=1440 E2E_BASE_URL=http://127.0.0.1:<web> npx playwright test e2e/J72-bulk-bill-run.spec.ts
//   (reset the database)
//   E2E_VIEWPORT=1280 E2E_BASE_URL=… npx playwright test e2e/J72-bulk-bill-run.spec.ts
//
// THE CASES RUN IN FILE ORDER (`--workers=1`) because they share ONE September run: E2 and
// E3's gap need no run; E1 starts it and walks as far as the wiring goes; E4–E7
// work on it at Check; E8–E10 need Sign off and Send; E3's overlap needs it to
// exist. A case the other lane's unfinished wiring cannot reach yet is marked
// `test.fail(…)` WITH THE PLAN TASK THAT UNBLOCKS IT — never skipped — so the day
// that task lands the case passes, Playwright reports "expected to fail but
// passed", and the hold is released by a red rather than by somebody remembering
// (hard-won law 2's hold-expiry rule).
//
// THE WORLD IS THE SEED'S, NOT THE JOURNEY TABLE'S. J72's preconditions name
// figures (10 accounts, a master, BR-0231/BR-0229); the seed's own roster is in
// its docstring and in J72 § WALKED — 12 units, 11 accounts, one vacant unit,
// cycle `J72-RIVERSIDE · Riverside`, August run `RUN-0001`. A drawn figure is an
// illustration (B14 rule 37); every figure asserted below is the seed's.
//
// Screens land in 08-qa/screens/bulk-bill-run-e2e-2026-09-30/, named after the
// D1 image of the same state (`1440-01-scope-continuous.png` …), so E11 is a
// side-by-side, file for file.
import { readdirSync, rmSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SHOTS = "../08-qa/screens/bulk-bill-run-e2e-2026-09-30";
const D1 = "../05-prototype/bulk-bill-run-2026-09-30";
const CYCLE = /J72-RIVERSIDE/;
const RUN_NAME = "September 2026 · Riverside";

/** What a case still waits on; a case waiting on one says which. B14 (inline
 *  fixes), B19 (sign-off summary), DEF-BIL-8471 and DEF-BIL-8472 landed with the
 *  bulk-run-rest lane (2.413.0) and their cases are released below. */
const WAITS = {
  B21: "DEF-BIL-8510: the stack was started without SBH_WALK_SWITCHES_DIR (E2E_WALK_SWITCHES_DIR)",
} as const;

/** DEF-BIL-8510 — the TEST-ONLY outage switch (`core/walk_switches.py`): the
 *  server is started with `SBH_WALK_SWITCHES_DIR=<dir>` and this walk writes
 *  `<dir>/meter_reads.down` to take Meter Reads down, and removes it to bring
 *  it back. Production forbids it outright. */
const SWITCHES = process.env.E2E_WALK_SWITCHES_DIR ?? "";
function meterReads(state: "down" | "up"): void {
  const file = `${SWITCHES}/meter_reads.down`;
  if (state === "down") writeFileSync(file, "J72 E6 walk");
  else rmSync(file, { force: true });
}

/**
 * THE SERVED TAG CODES (DEF-BIL-8216). The screen reads the server's grouping,
 * so a tag is named by its engine code, never by the retired client map's
 * words (`noReading`, `gapOrOverlap` …). On the seed: no reading `00003`;
 * disputed reading `00005`; no plan `00004` and `00005` — the Check lists EVERY
 * problem on an account (U5), so `00005` is under both; standing charges only
 * `00011`; gap `00009` and overlap `00010`; paid after cut-off `00007`.
 */
const TAG = {
  noReading: "missing_read",
  disputedReading: "account_held_by_disputed_read",
  noPlan: "unit_has_no_plan",
  standingChargesOnly: "base_only_billing",
  gapOrOverlap: "billing_continuity",
  paidAfterCutoff: "paid_after_cutoff",
} as const;

// ── helpers ──────────────────────────────────────────────────────────────────

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForTimeout(400);
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${WIDTH}-${name}.png`, fullPage: true });
}

async function openRun(page: Page, query = ""): Promise<void> {
  await page.goto(`/${tenant()}/billing/run${query}`);
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
}

async function onStep(page: Page, label: string, timeout = 30_000): Promise<boolean> {
  try {
    await expect(page.locator("[data-wizard=rail] [aria-current=step]")).toContainText(label, {
      timeout,
    });
    return true;
  } catch {
    return false;
  }
}

interface Scope {
  name?: string;
  start: string;
  end: string;
  bill?: string;
  days?: string;
  template?: boolean;
}

/** Fill What to bill. Waits for the preview the screen asks on every change. */
async function fillScope(page: Page, s: Scope): Promise<void> {
  await page.locator("#label").fill(s.name ?? "");
  const cycle = page.locator("#cycle_id");
  const option = cycle.locator("option").filter({ hasText: CYCLE });
  await expect(option, "the seeded Riverside cycle is offered").toHaveCount(1, { timeout: 20_000 });
  await cycle.selectOption({ value: (await option.getAttribute("value")) ?? "" });
  await page.locator("#period_start").fill(s.start);
  await page.locator("#period_end").fill(s.end);
  if (s.bill !== undefined) await page.locator("#bill_date").fill(s.bill);
  if (s.days !== undefined) await page.locator("#due_days").fill(s.days);
  if (s.template !== false) {
    const template = page.locator("#template_id");
    await expect(template.locator("option").nth(1)).toBeAttached({ timeout: 20_000 });
    await template.selectOption({ index: 1 });
  }
  await page.waitForTimeout(1500); // the preview's debounce + round trip
}

const SEPTEMBER: Scope = {
  name: RUN_NAME,
  start: "2026-09-01",
  end: "2026-09-30",
  bill: "2026-10-01",
  days: "21",
};

function startButton(page: Page) {
  return page.getByRole("button", { name: "Start checking", exact: true });
}

/** Re-open the September run at whatever step its phase names (it must exist). */
async function reopenRun(page: Page): Promise<void> {
  await openRun(page);
  await fillScope(page, SEPTEMBER);
  const open = page.locator("[data-run-problems=refusal] a", { hasText: /^Open / });
  await expect(open.first(), "the September run exists (E1 started it)").toBeVisible({
    timeout: 20_000,
  });
  await page.goto((await open.first().getAttribute("href")) ?? "");
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
}

/** Reach Check for the September run: start it, or re-open it if it exists. */
async function reachCheck(page: Page): Promise<void> {
  await openRun(page);
  await fillScope(page, SEPTEMBER);
  const duplicate = page.locator("[data-run-problems=refusal] a", { hasText: /^Open / });
  if ((await duplicate.count()) > 0) {
    const href = (await duplicate.first().getAttribute("href")) ?? "";
    await page.goto(href);
  } else {
    await expect(startButton(page)).toBeEnabled({ timeout: 20_000 });
    await startButton(page).click();
  }
  expect(await onStep(page, "Check", 90_000), "the run reaches Check").toBe(true);
  await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 90_000 });
}

async function openTag(page: Page, tag: string): Promise<void> {
  const row = page.locator(`[data-tag=${tag}]`).first();
  await expect(row, `tag ${tag} is listed`).toBeVisible({ timeout: 30_000 });
  await row.click();
  await expect(page.locator(`[data-tag-pane=${tag}]`)).toBeVisible({ timeout: 15_000 });
}

// ── the journeys ─────────────────────────────────────────────────────────────

test.describe(`J72 — the bulk bill run at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  // ⚠ NOT `mode: "serial"`, deliberately: serial SKIPS every later case after
  // one failure ("12 did not run" on the first walk), which is the silent skip
  // this spec exists to avoid. Run with `--workers=1`; the file's order is the
  // order above, and each case re-opens the run it needs (`reachCheck`).
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "420000"));

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  test("U6 · E2 · Scope problems: every refusal at once, each on its field", async ({ page }) => {
    await openRun(page);
    for (const step of ["Scope", "Check", "Sign off", "Send"]) {
      await expect(page.locator("[data-wizard=rail]")).toContainText(step);
    }
    // Absent on purpose (inventory §11): no services filter, no standing answers.
    await expect(page.locator("[data-step=scope]")).not.toContainText(
      /Which services|Standing answers/i,
    );
    // Run name empty · period end before its start · days to pay -3. The bill
    // date is left empty on purpose: this cycle HAS a bill day, so an empty
    // bill date resolves and is not a refusal (BR-BIL-1050). The template stays
    // at its pre-selected published one — the seed holds no unpublished
    // template (J72's "Winter insert · draft" is not seeded).
    await fillScope(page, {
      name: "",
      start: "2026-09-01",
      end: "2026-08-20",
      bill: "",
      days: "-3",
      template: false,
    });
    const refusals = page.locator("[data-run-problems=refusal]");
    await expect(refusals).toBeVisible({ timeout: 20_000 });
    await expect(refusals).toContainText("Fix 3 things to start.");
    await expect(refusals.locator("li")).toHaveCount(3);
    for (const field of ["label", "period_end", "due_days"]) {
      await expect(
        page.locator(`.field:has(#${field})`),
        `${field} carries its own message`,
      ).toContainText(/\S/);
    }
    await expect(startButton(page)).toBeDisabled();
    await expect(page.locator("[data-run-footnote=refusal]")).toContainText(
      /Fix \d+ things first\./,
    );
    await shot(page, "05-scope-problems");

    // A bill date before the period ends is refused alone.
    await fillScope(page, { ...SEPTEMBER, bill: "2026-09-25" });
    await expect(page.locator(".field:has(#bill_date)")).toContainText(/\S/, { timeout: 20_000 });
    await expect(startButton(page)).toBeDisabled();
  });

  test("U6 · E3a · a gap warns and still starts; no 'continue anyway' tick", async ({ page }) => {
    await openRun(page);
    await fillScope(page, {
      ...SEPTEMBER,
      start: "2026-10-10",
      end: "2026-11-09",
      bill: "2026-11-10",
    });
    const continuity = page.locator("[data-continuity=gap]");
    await expect(continuity).toBeVisible({ timeout: 20_000 });
    // Dates in the tenant's own format (Settings → Company: MM/DD/YYYY).
    await expect(continuity).toContainText("09/01/2026 – 10/09/2026 not billed.");
    await expect(page.locator("[data-step=scope] input[type=checkbox]")).toHaveCount(0);
    await expect(page.locator("[data-run-problems=warning]")).toBeVisible();
    await shot(page, "02-scope-gap");
    // The gap alone refuses nothing (a Nov period ends after today, which is a
    // warning too); Start is not held by the gap.
    await expect(
      page.locator("[data-run-problems=refusal] [data-problem-line*=period_gap]"),
    ).toHaveCount(0);
  });

  test("U1 · E1 · clean run, Scope: continuous, the counts, two warnings, Start enabled", async ({
    page,
  }) => {
    await openRun(page);
    await shot(page, "06-scope-panels-collapsed");
    await fillScope(page, SEPTEMBER);
    const continuity = page.locator("[data-continuity=continuous]");
    await expect(continuity).toBeVisible({ timeout: 20_000 });
    await expect(continuity).toContainText(
      /Follows run RUN-\d+ \(08\/01\/2026 – 08\/31\/2026\)\. 30 days\./,
    );
    const covers = page.locator("[data-run-facts=covers]");
    await expect(covers.locator("[data-run-fact=units]")).toContainText("12");
    await expect(covers.locator("[data-run-fact=accounts]")).toContainText("11");
    await expect(covers.locator("[data-run-fact=accounts]")).toContainText("Last run 6");
    await expect(covers.locator("[data-run-fact=regular]")).toContainText("11");
    await expect(covers.locator("[data-run-fact=master]")).toContainText("0");
    const warnings = page.locator("[data-run-problems=warning]");
    await expect(warnings).toContainText(/You can still start\./);
    await expect(warnings.getByRole("button", { name: "See units" })).toBeVisible();
    await expect(startButton(page)).toBeEnabled();
    await shot(page, "01-scope-continuous");
    await shot(page, "04-scope-warnings");
    await warnings.getByRole("button", { name: "See units" }).click();
    await expect(page.locator("[data-run-panel=nobody]")).toBeVisible();
    // DEF-BIL-8221 — the panel lists the units behind the count, each with
    // Add account opening the unit in a new tab.
    await expect(page.locator("[data-run-panel=nobody] [data-scope-row]").first()).toBeVisible({ timeout: 20_000 });
    await expect(page.locator("[data-run-panel=nobody] a[data-link=add-account]").first()).toHaveAttribute(
      "target",
      "_blank",
    );
    await shot(page, "07-scope-nobody-to-bill-panel");
    await page.locator("[data-run-panel=nobody] [data-run-panel-close]").click();

    // Start → Check. Everything after this line is the Check wiring.
    await startButton(page).click();
    expect(await onStep(page, "Check", 90_000), "Start checking opens Check").toBe(true);
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 90_000 });
    await shot(page, "20-check-ready-to-bill");
  });

  test("U5 · E4 · decide a tag for all, override one row, apply to selected", async ({ page }) => {
    // Released 2026-09-30 (bulk-run-rest, 2.413.0): DEF-BIL-8472 fixed — each
    // row serves its own answers and Apply to selected answers the lawful rows.
    test.setTimeout(180_000);
    await reachCheck(page);
    // The tiles, from the SAVED Check (DEF-BIL-8216): nothing on the seed
    // blocks; no plan, a disputed reading, a missing read, paid after cut-off,
    // a gap, an overlap and standing charges only each need a decision.
    await expect(page.getByRole("button", { name: /^Blocked accounts 0$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Ready accounts 4$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Need a decision 7$/ })).toBeVisible();
    for (const [tag, n] of [
      [TAG.noReading, 1],
      [TAG.disputedReading, 1],
      [TAG.noPlan, 2],
      [TAG.standingChargesOnly, 1],
      [TAG.gapOrOverlap, 2],
    ] as const) {
      await expect(page.locator(`[data-tag=${tag}]`), `${tag} lists ${n}`).toContainText(String(n));
    }
    await openTag(page, TAG.noReading);
    const pane = page.locator(`[data-tag-pane=${TAG.noReading}]`);
    await expect(pane.locator("[data-row-account]")).toHaveCount(1);
    await expect(pane.locator("[data-row-account='AC-2026-00003']")).toBeVisible();
    await shot(page, "11-check-decision-tag-no-reading");
    // U5 · DEF-BIL-8418 — Answer for all OPENS on the Billing default
    // (S66 run_default_missing_read = Estimate), stored on the run at Check.
    const answer = pane.getByRole("radiogroup", { name: "Answer for all 1:" });
    await expect(answer.getByRole("radio", { name: "Estimate" })).toBeChecked({
      timeout: 20_000,
    });
    // Answer for all: Hold.
    await answer.getByRole("radio", { name: "Hold" }).click();
    await expect(answer.getByRole("radio", { name: "Hold" })).toBeChecked({
      timeout: 20_000,
    });
    // Override the one row: Estimate, with its figure (DEF-BIL-8551) — the box
    // starts from the account's own usual month when metering has one.
    await pane
      .getByRole("combobox", { name: "Decide for AC-2026-00003" })
      .selectOption({ value: "estimate" });
    const box = pane.locator("[data-estimate-box]");
    await expect(box).toBeVisible();
    const usage = box.getByLabel("Usage");
    if ((await usage.inputValue()) === "") await usage.fill("7");
    const unit = box.getByLabel("Unit");
    if ((await unit.inputValue()) === "") await unit.fill("kgal");
    await box.getByRole("button", { name: "Record this estimate" }).click();
    await expect(pane.locator("[data-decision=answered]")).toHaveCount(1, { timeout: 20_000 });
    await expect(pane.locator("[data-estimate-recorded]")).toContainText("Estimate:");
    // Gap or overlap has TWO rows (the seed's gap 00009 and overlap 00010):
    // select both, choose Bill as it stands — only the gap may take it.
    await openTag(page, TAG.gapOrOverlap);
    const gap = page.locator(`[data-tag-pane=${TAG.gapOrOverlap}]`);
    await expect(gap.locator("[data-row-account]")).toHaveCount(2);
    await gap.getByRole("checkbox", { name: "Select AC-2026-00009" }).check();
    await gap.getByRole("checkbox", { name: "Select AC-2026-00010" }).check();
    await gap.getByRole("radiogroup").getByRole("radio").first().click();
    await expect(gap.locator("[data-apply-selected]")).toContainText("Apply to 1 selected");
    await expect(gap.locator("[data-cannot-take]")).toContainText("1 cannot take this answer.");
    await shot(page, "12-check-decision-rows-selected");
    await gap.locator("[data-apply-selected]").click();
    await expect(
      gap.locator("[data-row-account='AC-2026-00009'] [data-decision=answered]"),
    ).toBeVisible({ timeout: 20_000 });
    // The overlap row offers Look into it only (PO 2026-09-30 case 4).
    const overlap = gap.getByRole("combobox", { name: "Decide for AC-2026-00010" });
    await expect(overlap.locator("option")).toHaveText(["Choose", "Look into it"]);
  });

  test("U5 · E5 · fix an account inline, re-check, it moves to Ready", async ({ page }) => {
    // Released 2026-09-30 (bulk-run-rest, 2.413.0): B14 inline fixes (DEF-BIL-8218).
    test.setTimeout(120_000);
    await reachCheck(page);
    await openTag(page, TAG.noPlan);
    const pane = page.locator(`[data-tag-pane=${TAG.noPlan}]`);
    // Both no-plan accounts: the Check lists every problem on an account, so
    // 00005 (no plan AND a disputed reading) is here as well as under Disputed.
    await expect(pane.locator("[data-row-account]")).toHaveCount(2);
    const row = pane.locator("[data-row-account='AC-2026-00004']");
    const fix = row.locator("[data-fix-here=set_plan] select");
    await expect(fix, "the row offers a plan to pick (B14)").toHaveCount(1, { timeout: 10_000 });
    await expect(fix.locator("option").nth(1)).toBeAttached({ timeout: 20_000 });
    await fix.selectOption({ index: 1 });
    await shot(page, "13-check-blocking-fixed-on-row");
    await row.locator("[data-fix-save]").click();
    // Written by its owner, re-checked: 00004 leaves the tag; 00005 stays.
    await expect(pane.locator("[data-row-account='AC-2026-00004']")).toHaveCount(0, {
      timeout: 30_000,
    });
    await expect(pane.locator("[data-row-account='AC-2026-00005']")).toBeVisible();
    await shot(page, "23-check-fixed-rechecked-row");
    await openTag(page, TAG.disputedReading);
    await expect(
      page.locator(`[data-tag-pane=${TAG.disputedReading}] [data-row-account='AC-2026-00005']`),
    ).toBeVisible();
  });

  test("F2 · E6 · Meter Reads down: the stop names what and who; the run is kept", async ({ page }) => {
    test.fail(SWITCHES === "", WAITS.B21);
    test.setTimeout(240_000);
    await reachCheck(page);
    const runUrl = page.url();
    // Meter Reads goes down AFTER the run started (Scope refuses a run while
    // it is down), and the clerk presses Check again.
    meterReads("down");
    try {
      await page.locator("[data-check-again]").click();
      const stop = page.locator("[data-check-stop]");
      await expect(stop).toContainText("Meter Reads is not answering.", { timeout: 60_000 });
      await expect(stop).toContainText("Support can fix this.");
      await expect(stop).toContainText(/Ref SBH-[0-9A-F]{8}\./);
      await expect(stop).toContainText("The run is saved.");
      await shot(page, "10-check-module-down");
    } finally {
      meterReads("up");
    }
    await page.locator("[data-check-stop]").getByRole("button", { name: "Try again" }).click();
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 90_000 });
    expect(page.url(), "the same run carries on").toBe(runUrl);
  });

  test("U5 · E7 · Paid after cut-off: applied to this bill", async ({ page }) => {
    // Released 2026-09-30: DEF-BIL-8471 — the served tag sits under Payments &
    // balances with its own name (the screen reads the server's grouping).
    test.setTimeout(120_000);
    await reachCheck(page);
    await expect(page.locator(`[data-tag=${TAG.paidAfterCutoff}]`)).toContainText("Paid after cut-off");
    await openTag(page, TAG.paidAfterCutoff);
    const pane = page.locator(`[data-tag-pane=${TAG.paidAfterCutoff}]`);
    await expect(pane.locator("[data-row-account='AC-2026-00007']")).toBeVisible();
    await shot(page, "16-check-payments-tag");
    await pane
      .getByRole("combobox", { name: "Decide for AC-2026-00007" })
      .selectOption({ label: "Apply to this bill" });
    await expect(pane.locator("[data-decision=answered]")).toHaveCount(1, { timeout: 20_000 });
  });

  test("U1 · U4 · E1b · Check → Calculate → Sign off (the rest of the clean run)", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await reachCheck(page);
    // The overlap row (00010, already billed Sep 1 – Sep 30) takes the ONE
    // lawful answer, row by row; everything else keeps its pre-selected answer.
    await openTag(page, TAG.gapOrOverlap);
    await page
      .getByRole("combobox", { name: "Decide for AC-2026-00010" })
      .selectOption({ label: "Look into it" });
    await expect(
      page.locator(
        `[data-tag-pane=${TAG.gapOrOverlap}] [data-row-account='AC-2026-00010'] [data-decision=answered]`,
      ),
    ).toBeVisible({ timeout: 20_000 });
    const price = page.getByRole("button", { name: /^Price \d+ accounts?$/ });
    await expect(price).toBeEnabled({ timeout: 30_000 });
    await price.click();
    await shot(page, "24-calculating-progress");
    expect(await onStep(page, "Sign off", 180_000), "Calculate opens Sign off").toBe(true);
    await shot(page, "25-signoff-summary-all-open");
    // Stop here: E8 reads this Sign off before E1c sends (a sent run cannot
    // re-open its Sign off step — the rail locks every step once Sent).
  });

  test("A1 · E8 · Sign off: every figure reconciles to Scope's", async ({ page }) => {
    // Released 2026-09-30 (bulk-run-rest, 2.413.0): B19 sign-off summary
    // (DEF-BIL-8220) — every figure is the server's and adds back.
    test.setTimeout(120_000);
    await reopenRun(page);
    expect(await onStep(page, "Sign off", 15_000), "the calculated run re-opens at Sign off").toBe(
      true,
    );
    const accounts = page.locator("[data-run-table=who-accounts]");
    await expect(accounts).toBeVisible({ timeout: 30_000 });
    const cell = async (name: string) =>
      Number(
        (await accounts.locator(`[data-who-row=${name}] td[data-num]`).innerText()).replace(/\D/g, ""),
      );
    // Scope said 11 accounts to bill and 12 units.
    expect(await cell("to-bill")).toBe(11);
    const billed = await cell("billed");
    const notBilled = await cell("not-billed");
    expect(billed + notBilled, "Billed + Not billed = Accounts to bill").toBe(11);
    let parts = 0;
    for (const name of ["blocked", "held", "nothing", "left-out", "waived", "failed"]) {
      parts += await cell(name);
    }
    expect(parts, "the Not billed lines add back").toBe(notBilled);
    const drafts = await page.request.get(
      `/api/${tenant()}/invoices?f.bill_run_id=${new URL(page.url()).searchParams.get("run")}&per=200`,
    );
    const drafted = ((await drafts.json()).results ?? []).length;
    expect(billed, "Billed = the drafts Calculate made").toBe(drafted);
    await expect(page.locator("[data-no-reconcile]")).toHaveCount(0);
    await expect(page.locator("[data-run-table=who-units]")).toContainText("12");
    await expect(page.getByText("Not available yet.")).toHaveCount(0);
    await shot(page, "26-signoff-who-is-billed");
    await shot(page, "27-signoff-usage-and-charges");
    await shot(page, "28-signoff-payments-and-balances");
  });

  test("U1 · E1c · Sign off → Send (the clean run goes out)", async ({ page }) => {
    test.setTimeout(240_000);
    await reopenRun(page);
    expect(await onStep(page, "Sign off", 15_000), "the calculated run re-opens at Sign off").toBe(
      true,
    );
    const confirmations = page.getByRole("group", { name: "Sign off" });
    for (const name of [
      "Bills follow our rules and rates",
      "Email customers have agreed to e-bills",
      "SMS customers have agreed to texts",
      "Autopay customers charged on due date",
      "I checked the totals",
    ]) {
      await confirmations.getByRole("checkbox", { name }).check();
    }
    await shot(page, "31-signoff-confirmations-ticked");
    const actions = page.locator("[data-wizard=actions]");
    await actions.getByRole("button", { name: "Sign off", exact: true }).click();
    expect(await onStep(page, "Send", 60_000), "Sign off opens Send").toBe(true);
    await shot(page, "32-send-not-ticked");
    await page
      .getByRole("region", { name: "Send" })
      .getByRole("checkbox", { name: "I checked the totals" })
      .check();
    await shot(page, "33-send-ticked");
    const send = actions.getByRole("button", { name: /^Send \d+ bills?$/ });
    await send.click();
    await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 120_000 });
    await shot(page, "35-send-sent-not-in-run");
  });

  test("F3 · A4 · E9 · Send with a break: sent and broken shown apart", async ({ page }) => {
    // `seed_j72_bulk_run --send-failure` clears ELECTRIC's revenue account, so
    // the one electric bill — AC-2026-00008's — is refused at Send and every
    // other bill goes (DEF-BIL-8421: the old template pin broke nothing). On
    // the plain seed every bill goes and there is no "not sent" line.
    test.fail(
      process.env.E2E_J72_SEND_FAILURE !== "1",
      "the break is seeded only with --send-failure (E2E_J72_SEND_FAILURE=1)",
    );
    test.setTimeout(240_000);
    await reopenRun(page);
    await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 30_000 });
    const sent = Number((await page.locator("[data-sent-count]").getAttribute("data-sent-count")) ?? "0");
    const notSent = page.locator("[data-not-sent]");
    await expect(notSent).toHaveAttribute("data-not-sent", "1");
    await notSent.locator("[data-see=breaks]").click();
    const panel = page.locator("[data-run-panel=not-sent]");
    await expect(panel.locator("[data-row-account='AC-2026-00008']")).toContainText(
      "A service has no revenue account.",
    );
    await expect(panel.locator("[data-row-account]")).toHaveCount(1);
    await shot(page, "35-send-sent-not-in-run");
    // Retry failed while the cause stands: the same one bill fails again, the
    // sent count does not move — nothing was sent twice.
    await panel.getByRole("button", { name: "Retry failed" }).click();
    await page.waitForTimeout(4000);
    await page.reload();
    await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 30_000 });
    expect(Number((await page.locator("[data-sent-count]").getAttribute("data-sent-count")) ?? "0")).toBe(sent);
    await expect(page.locator("[data-not-sent]")).toHaveAttribute("data-not-sent", "1");
  });

  // Named for what it asserts: the catch-up run STARTS. Walking that child run
  // through Check · Sign off · Send (J72 E10's second half) is not written yet.
  test("U7 · E10 · Not in this run → a catch-up run starts from Sent", async ({ page }) => {
    test.setTimeout(180_000);
    await reopenRun(page);
    await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 30_000 });
    const rows = page.locator("[data-not-in-run-row]");
    await expect(rows.first()).toBeVisible();
    await rows.first().locator("input[type=checkbox]").check();
    await page.locator("[data-catch-up]").click();
    await expect(page.locator("[data-catch-up-started]")).toBeVisible({ timeout: 60_000 });
    await shot(page, "36-send-catch-up-started");
  });

  test("U6 · E3b · an overlap is refused and links the run", async ({ page }) => {
    await openRun(page);
    await fillScope(page, {
      ...SEPTEMBER,
      start: "2026-09-15",
      end: "2026-10-14",
      bill: "2026-10-15",
    });
    await expect(page.locator("[data-continuity=overlap]")).toBeVisible({ timeout: 20_000 });
    const refusals = page.locator("[data-run-problems=refusal]");
    await expect(refusals).toContainText(/09\/15\/2026.*09\/30\/2026/);
    const open = refusals.locator("a", { hasText: /^Open RUN-\d+/ });
    await expect(open).toHaveCount(1);
    expect(await open.getAttribute("href")).toMatch(/\/billing\/run\?run=/);
    await expect(startButton(page)).toBeDisabled();
    await shot(page, "03-scope-overlap");
  });

  test("U2 · E11 · every captured state has its D1 image", async () => {
    // Figures are NOT compared (B14 rule 37); the arrangement is compared by eye
    // against the D1 image of the same name, per the UI skill's §4 checklist.
    const drawn = readdirSync(D1).filter((f) => f.endsWith(`-${WIDTH}.png`));
    expect(drawn, "36 drawn states at this width").toHaveLength(36);
    let taken: string[] = [];
    try {
      taken = readdirSync(SHOTS).filter((f) => f.startsWith(`${WIDTH}-`));
    } catch {
      taken = []; // no screenshot taken yet at this width
    }
    for (const file of taken) {
      const state = file.replace(`${WIDTH}-`, "").replace(/\.png$/, "");
      expect(drawn, `${file} has a drawing`).toContain(`${state}-${WIDTH}.png`);
    }
    // Every drawn state captured is the goal; today the Check → Send states wait on the other lane.
    test.info().annotations.push({ type: "captured", description: `${taken.length} of 36` });
  });
});
