// ── Trace ──────────────────────────────────────────────
// Tracker:  BULK-CHG-56 (the clerk acceptance walk, F1–F5 and S1–S4: E12, E13)
// Journey:  J73 — the bulk bill run, breakdown and scale (F1–F5, S1–S4) ·
//           08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
// Criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md §3 (F) and §4 (S)
// Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md E12, B21, B27, B28
// Seed:     `manage.py seed_j72_bulk_run --send-failure --second-clerk` (F) and
//           `… --accounts 10000|40000` (S), on top of `manage.py seed_demo`, on PostgreSQL
// Harness:  10-scripts/j73_bulk_run_harness.py (Meter Reads down/up, the worker kill,
//           the S1 pass time and the S2 server times — what a browser cannot do)
// ───────────────────────────────────────────────────────
//
// HOW THIS WALK IS ORGANISED (J72 § HOW THIS WALK IS ORGANISED, PO 2026-09-30):
// one test per clerk check, NAMED by its check id, run at 1440 and at 1280
// (`E2E_VIEWPORT`). Each test's first lines say what PASS means, in the
// acceptance file's own figures. The count is always nine; a check that cannot
// be walked yet is `test.fixme` WITH WHAT IT WAITS ON — never deleted.
//
// ⚠ WHY `test.fixme` AND NOT J72's `test.fail`. J72 runs every step and fails
// where the work is missing, so a landing flips it to "expected to fail but
// passed". These nine cannot reach their subject at all yet — the bulk lane's
// Check job, Send breaks and batching are not merged (2026-09-30) — so running
// them would only time out in `reachCheck`. When the named work lands, delete
// the `fixme` line: the body below it is the walk.
//
// HOW TO RUN IT (one database per world; RESET between widths):
//   F-checks  seed_j72_bulk_run --send-failure --second-clerk
//   S-checks  seed_j72_bulk_run --accounts 10000   (S1 at 10,000)
//             seed_j72_bulk_run --accounts 40000   (S1 at 40,000, S2, S3, S4)
//   E2E_VIEWPORT=1440 E2E_BASE_URL=http://127.0.0.1:<web> npx playwright test \
//     e2e/J73-bulk-run-breakdown-and-scale.spec.ts --workers=1
//   J73_SCALE=40000 selects the S world; without it the S tests skip by name.
import { execSync } from "node:child_process";
import { rmSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Browser, Page } from "@playwright/test";

import {
  expandInnerScroller,
  signIn,
  signInPassword,
  signInPath,
  skipUnlessAppServer,
  tenant,
} from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SCALE = Number(process.env.J73_SCALE ?? "0");
const SHOTS = "../08-qa/screens/bulk-bill-run-j73-2026-09-30";
const CYCLE = /J72-RIVERSIDE/;

/** What each check waits on (2026-09-30). Delete a `fixme` when its line lands. */
const WAITS = {
  F1: "set E2E_J73_WORKER_KILL and E2E_J73_WORKER_START (the stack runs JOBS_EAGER=false with a Celery billing worker; the scale world --accounts 300 so a Check lasts minutes)",
  F2: "set E2E_WALK_SWITCHES_DIR to the SBH_WALK_SWITCHES_DIR the server was started with (DEF-BIL-8510)",
  F3: "seed --send-failure (electric's revenue account cleared; AC-2026-00008's bill breaks at Send)",
  F5: "no browser way to make ONE account's check fail unexpectedly; proved by test (check_engine CHECK_FAILED, test_b7__an_unexpected_error_blocks_only_that_account_with_a_support_reference)",
  B27: "B27 (batched Check loads) not merged — S1 bar is after batching",
  B28: "B28 (parallel batches, per-utility cap) not merged",
  S2: "the 40,000-account world is not seeded on this machine",
} as const;

/** DEF-BIL-8510 — the TEST-ONLY outage switch (`core/walk_switches.py`). */
const SWITCHES = process.env.E2E_WALK_SWITCHES_DIR ?? "";
function meterReads(state: "down" | "up"): void {
  const file = `${SWITCHES}/meter_reads.down`;
  if (state === "down") writeFileSync(file, "J73 F2 walk");
  else rmSync(file, { force: true });
}

const SECOND_CLERK = "marcus.webb.j73@brazosbendutilities.com";
const F3_ACCOUNT = "AC-2026-00008"; // the one electric bill (seed --send-failure)
const SEPTEMBER = {
  name: "September 2026 · Riverside",
  start: "2026-09-01",
  end: "2026-09-30",
  bill: "2026-10-01",
  days: "21",
};

// ── helpers ──────────────────────────────────────────────────────────────────

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForTimeout(400);
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${WIDTH}-${name}.png`, fullPage: true });
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

/** Open the September Riverside run: start it, or follow the overlap refusal's link to it. */
async function openSeptemberRun(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/billing/run`);
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
  await page.locator("#label").fill(SEPTEMBER.name);
  const cycle = page.locator("#cycle_id");
  const option = cycle.locator("option").filter({ hasText: CYCLE });
  await expect(option).toHaveCount(1, { timeout: 20_000 });
  await cycle.selectOption({ value: (await option.getAttribute("value")) ?? "" });
  await page.locator("#period_start").fill(SEPTEMBER.start);
  await page.locator("#period_end").fill(SEPTEMBER.end);
  await page.locator("#bill_date").fill(SEPTEMBER.bill);
  await page.locator("#due_days").fill(SEPTEMBER.days);
  await page.waitForTimeout(1500);
  const existing = page.locator("[data-run-problems=refusal] a", { hasText: /^Open / });
  if ((await existing.count()) > 0) {
    await page.goto((await existing.first().getAttribute("href")) ?? "");
  } else {
    await page.getByRole("button", { name: "Start checking", exact: true }).click();
  }
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
}

/** The Check's "n of N" as numbers, or null while no count is on screen. */
async function checkProgress(page: Page): Promise<{ done: number; total: number } | null> {
  const text =
    (await page
      .locator("[data-run-progress=checking]")
      .first()
      .textContent()
      .catch(() => null)) ?? "";
  const m = /([\d,]+)\s+of\s+([\d,]+)/.exec(text);
  return m ? { done: Number(m[1].replace(/,/g, "")), total: Number(m[2].replace(/,/g, "")) } : null;
}

/** A second browser signed in as the second clerk (seed --second-clerk). */
async function signInAs(browser: Browser, email: string): Promise<Page> {
  const context = await browser.newContext({ viewport: { width: WIDTH, height: 1000 } });
  const page = await context.newPage();
  await page.goto(signInPath());
  await page.locator("#signin-email").fill(email);
  await page.locator("#signin-password").fill(signInPassword());
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor();
  return page;
}

async function timed(page: Page, open: () => Promise<void>, ready: string): Promise<number> {
  const t0 = Date.now();
  await open();
  await expect(page.locator(ready).first()).toBeVisible({ timeout: 60_000 });
  return Date.now() - t0;
}

// ── the checks ───────────────────────────────────────────────────────────────

test.describe(`J73 — bulk run breakdown and scale at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "2400000"));

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  // ── §3 · when something breaks, does the clerk know? ─────────────────────

  test("F1 · a worker dies mid-Check: progress resumes where it stopped, nothing checked twice", async ({
    page,
  }) => {
    // PASS: the Check shows n of N; the billing worker is SIGKILLed; a fresh
    // worker starts; with NO clerk action the screen's own poll hands the job
    // back (DEF-BIL-8511) and n carries on from where it stopped, never from 0.
    // U3: the page is reloaded while the worker is dead and lands on Check.
    // "Nothing checked twice" is the harness's accounts_saved_twice = 0.
    const kill = process.env.E2E_J73_WORKER_KILL ?? "";
    const start = process.env.E2E_J73_WORKER_START ?? "";
    test.skip(kill === "" || start === "", WAITS.F1);
    await openSeptemberRun(page);
    expect(await onStep(page, "Check", 60_000)).toBe(true);
    await expect
      .poll(async () => (await checkProgress(page))?.done ?? 0, { timeout: 600_000 })
      .toBeGreaterThanOrEqual(50);
    const before = await checkProgress(page);
    execSync(kill, { stdio: "inherit" });
    await page.reload();
    expect(await onStep(page, "Check", 60_000), "U3: the run re-opens on Check").toBe(true);
    await shot(page, "F1-worker-killed");
    execSync(start, { stdio: "inherit" });
    await expect
      .poll(async () => (await checkProgress(page))?.done ?? 0, { timeout: 600_000 })
      .toBeGreaterThan((before?.done ?? 0) + 25);
    const after = await checkProgress(page);
    expect(after?.done ?? 0, "carried on from where it stopped").toBeGreaterThan(before?.done ?? 0);
    await shot(page, "F1-check-resumed");
  });

  test("F2 · Meter Reads is down: a banner says what and who, Try again, the run is kept", async ({
    page,
  }) => {
    // PASS: with Meter Reads down, Check shows the stop banner naming Meter
    // Reads and who fixes it, the server's support reference (SBH-xxxxxxxx),
    // and Try again; after it is back, Try again completes the Check on the
    // SAME run. The switch is a file (DEF-BIL-8510), never a product setting.
    test.skip(SWITCHES === "", WAITS.F2);
    await openSeptemberRun(page);
    expect(await onStep(page, "Check", 60_000)).toBe(true);
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
    const runUrl = page.url();
    meterReads("down");
    try {
      await page.locator("[data-check-again]").click();
      const stop = page.locator("[data-check-stop]");
      await expect(stop).toBeVisible({ timeout: 60_000 });
      await expect(stop).toContainText(/Meter Reads/);
      await expect(stop).toContainText("Support can fix this.");
      await expect(stop).toContainText(/SBH-[0-9A-F]{8}/);
      await shot(page, "F2-meter-reads-down");
    } finally {
      meterReads("up");
    }
    await page.locator("[data-check-stop]").getByRole("button", { name: "Try again" }).click();
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
    expect(page.url(), "the run is kept").toBe(runUrl);
  });

  test("F3 · some bills fail at Send: sent and failed apart, each with its reason, Retry failed sends only those", async ({
    page,
  }) => {
    // PASS (seed --send-failure, AFTER J72's clean run has sent September):
    // Sent shows the bills that went and "1 bill not sent" apart; See breaks
    // lists AC-2026-00008 with its reason; Retry failed retries ONLY that bill
    // — while the cause stands it fails again and the sent count does not
    // move, so nothing is sent twice.
    test.skip(process.env.E2E_J72_SEND_FAILURE !== "1", WAITS.F3);
    await openSeptemberRun(page);
    // A sent run draws the Sent card and its tabs; the rail has no current
    // step any more, so the card is the thing to wait for (not `onStep`).
    await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 60_000 });
    const sent = Number((await page.locator("[data-sent-count]").getAttribute("data-sent-count")) ?? "0");
    const notSent = page.locator("[data-not-sent]");
    await expect(notSent).toHaveAttribute("data-not-sent", "1", { timeout: 60_000 });
    await notSent.locator("[data-see=breaks]").click();
    await expect(page.locator(`[data-row-account='${F3_ACCOUNT}']`)).toContainText(/revenue account/i);
    await shot(page, "F3-send-one-break");
    await page.getByRole("button", { name: /Retry failed/ }).click();
    await page.waitForTimeout(4000);
    await page.reload();
    await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 60_000 });
    expect(Number((await page.locator("[data-sent-count]").getAttribute("data-sent-count")) ?? "0")).toBe(sent);
    await expect(page.locator("[data-not-sent]")).toHaveAttribute("data-not-sent", "1");
  });

  test("F4 · two clerks open one run: the second sees who is on it; two Sends cannot both issue", async ({
    page,
    browser,
  }) => {
    // PASS (seed --second-clerk): Marcus opens the run Dana has open and is
    // told Dana is on it (DEF-BIL-8512). The second half — two Sends cannot
    // both issue — is proved on PostgreSQL by two concurrent releases
    // (tests/test_bbr_f4_two_sends_pg.py): each bill issued once.
    await openSeptemberRun(page);
    const marcus = await signInAs(browser, SECOND_CLERK);
    await marcus.goto(page.url().replace(/^https?:\/\/[^/]+/, ""));
    await expect(marcus.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
    await expect(marcus.locator("[data-run-presence]")).toContainText(/Dana/, { timeout: 60_000 });
    await shot(marcus, "F4-second-clerk");
    // And Dana is told Marcus is there, on her next heartbeat (30 s).
    await expect(page.locator("[data-run-presence]")).toContainText(/Marcus Webb/, { timeout: 45_000 });
  });

  test("F5 · something unexpected: a support reference, the run kept, the account blocked with it", async ({
    page,
  }) => {
    // PASS: an account whose check fails unexpectedly is listed as blocked
    // with a support reference (SBH-xxxxxxxx) the clerk can read out; every
    // other account is checked; the run is kept. Proved today by test
    // (check_engine `CHECK_FAILED`), not yet by a browser.
    test.fixme(true, WAITS.F5);
    await openSeptemberRun(page);
    await expect(page.locator("[data-check-results]")).toContainText(/SBH-[0-9A-F]{8}/, {
      timeout: 120_000,
    });
  });

  // ── §4 · does it hold at the size of the utility? ────────────────────────

  test("S1 · Check time: ≤ 10 min at 10,000 accounts; ≤ 30 min at 40,000", async ({ page }) => {
    // PASS: from Start checking to the tiles, ≤ 600 s at 10,000 accounts and
    // ≤ 1,800 s at 40,000, with "n of N" moving the whole way.
    test.skip(!SCALE, "S world only (J73_SCALE=10000|40000)");
    test.fixme(true, `${WAITS.B27}; ${WAITS.B28}`);
    const bar = SCALE >= 40_000 ? 1_800_000 : 600_000;
    const t0 = Date.now();
    await openSeptemberRun(page);
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: bar });
    expect(Date.now() - t0).toBeLessThanOrEqual(bar);
    await shot(page, `S1-check-${SCALE}`);
  });

  test("S2 · screens stay quick at 40,000: a tag's list, Sign off, Not in this run open in < 2 s, paged", async ({
    page,
  }) => {
    // PASS at 40,000: each of the three opens in under 2,000 ms and shows a
    // page (a pager, never all rows).
    test.skip(SCALE < 40_000, "S world at 40,000 only (J73_SCALE=40000)");
    test.fixme(true, WAITS.S2);
    await openSeptemberRun(page);
    const tag = page.locator("[data-tag]").first();
    const tagMs = await timed(page, () => tag.click(), "[data-tag-pane]");
    expect(tagMs, "a tag's account list").toBeLessThan(2_000);
    await expect(
      page.locator("[data-tag-pane] [data-pager], [data-tag-pane] nav").first(),
    ).toBeVisible();
    expect(await onStep(page, "Sign off", 1_800_000)).toBe(true);
    const signOffMs = await timed(
      page,
      async () => {
        await page.reload();
      },
      "[data-step=signoff]",
    );
    expect(signOffMs, "Sign off").toBeLessThan(2_000);
    const notInRunMs = await timed(
      page,
      () => page.locator("[data-see]").first().click(),
      "[data-not-in-run]",
    );
    expect(notInRunMs, "Not in this run").toBeLessThan(2_000);
  });

  test("S3 · Send at scale: 40,000 bills issue with progress; a failure part-way resumes, no duplicate numbers", async ({
    page,
  }) => {
    // PASS at 40,000: Send shows n of 40,000 moving to the end; a worker
    // killed part-way resumes; afterwards invoice numbers are unique and the
    // count of issued bills equals Sign off's billed count.
    test.skip(SCALE < 40_000, "S world at 40,000 only (J73_SCALE=40000)");
    test.fixme(true, `${WAITS.B28}; ${WAITS.S2}`);
    await openSeptemberRun(page);
    expect(await onStep(page, "Send", 3_600_000)).toBe(true);
    await expect(page.locator("[data-send-progress]")).toBeVisible();
  });

  test("S4 · other utilities keep working: another utility's run still starts while one runs 40,000", async ({
    page,
  }) => {
    // PASS: while Brazos Bend's 40,000-account Check runs, a second utility's
    // run starts and its Check moves within a minute (per-utility cap = half
    // the billing workers, minimum 1 — decided 2026-09-30). Needs a second
    // provisioned tenant (10-scripts/cr051_provision_utilities.py).
    test.skip(SCALE < 40_000, "S world at 40,000 only (J73_SCALE=40000)");
    test.fixme(true, WAITS.B28);
    await openSeptemberRun(page);
    await expect(page.locator("[data-run-progress=checking]")).toBeVisible({ timeout: 60_000 });
  });
});
