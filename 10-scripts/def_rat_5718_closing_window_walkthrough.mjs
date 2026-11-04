// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5718 — filing a new rate version silently rewrites the
//          CURRENT version's end date and no screen said so.
// Rules:   BR-RAT-037 (windows never overlap — the auto-close is REQUIRED and
//          correct; what was missing is saying it) · B14 rule 33 (a consequence
//          before an irreversible act) · BR-SHL-034 (a date only through
//          `DateCell`, in the tenant's own format)
// ───────────────────────────────────────────────────────
/**
 * Pick a date for a new rate version on a schedule that is already live, and
 * read what the screen now says about the rate customers are paying today.
 *
 *     BASE=http://127.0.0.1:8380 node 10-scripts/def_rat_5718_closing_window_walkthrough.mjs
 *
 * PO, in the beta, verbatim: *"i want to change the rate from tomorrow - eisting
 * rates say it is valid until 31 dec"*.
 *
 * ⚠ **THIS IS A CHECK FOR A SENTENCE THAT WAS ABSENT, AND AN ABSENCE IS
 * INVISIBLE TO EVERY OTHER CHECK IN THIS REPOSITORY.** The auto-close itself is
 * correct, is required by BR-RAT-037, and is asserted by tests that all pass.
 * Nothing anywhere asked whether the clerk was told.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8380";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL}`);

await page.goto(`${BASE}/${TENANT}/plans-rates/rates`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2000);
const liveRow = page.locator("table tbody tr", { hasText: "Active" }).first();
if (!(await liveRow.count())) {
  fail("no ACTIVE rate schedule — nothing whose window could be closed");
  await browser.close();
  process.exit(1);
}
note(`\n0 · ${(await liveRow.innerText()).replace(/\s+/g, " ").trim()}`);
await liveRow.locator("button.rating-link, a").first().click();
await page.waitForTimeout(2000);
const tariffId = page.url().split("/rates/")[1]?.split(/[/?#]/)[0] ?? "";

// ── 1 · step 4, no date yet ───────────────────────────────────────────────
note("\n1 · step 4 with no date typed — it must say nothing yet");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/${tariffId}/edit`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(2500);
for (let step = 0; step < 3; step += 1) {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (await cont.count()) { await cont.click().catch(() => {}); await page.waitForTimeout(800); }
}
await page.screenshot({ path: `${SHOTS}/rat5718_1_no_date.png`, fullPage: true });
const before = (await page.locator("body").innerText()).replace(/\s+/g, " ");
if (/The current rate ends/i.test(before)) {
  fail("it announces a closure before a date has been chosen");
} else {
  ok("silent until a date is picked");
}

// ── 2 · pick a date ───────────────────────────────────────────────────────
note("\n2 · pick a date and read the consequence");
const dateField = page.locator("#rate-effective-from");
if (!(await dateField.count())) {
  fail("no effective-from field on step 4");
} else {
  await dateField.fill("2027-03-01");
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${SHOTS}/rat5718_2_dated.png`, fullPage: true });
  const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  if (/The current rate ends/i.test(body)) {
    ok("it says the current rate ends");
  } else {
    fail("nothing says the live rate is about to be closed — the reported defect");
  }
  // ⚠ THE DATE ITSELF, and it must be the DAY BEFORE.
  const stamped = await page.locator('time[datetime="2027-02-28"]').count();
  if (stamped > 0) {
    ok("and names 28 Feb 2027 — the day before, through DateCell");
  } else {
    const anyTime = await page.locator("time").allTextContents();
    fail(`the day before is not on screen; <time> values were: ${anyTime.join(", ")}`);
  }
}

// ── 3 · it must follow the date ───────────────────────────────────────────
note("\n3 · change the date and the sentence must follow it");
if (await dateField.count()) {
  await dateField.fill("2027-07-01");
  await page.waitForTimeout(900);
  const moved = await page.locator('time[datetime="2027-06-30"]').count();
  const stale = await page.locator('time[datetime="2027-02-28"]').count();
  if (moved > 0 && stale === 0) {
    ok("it moved to 30 Jun 2027 and the old answer is gone");
  } else {
    fail(`the sentence did not follow the date (new=${moved}, stale=${stale})`);
  }
}

// ── 4 · and again above the confirm ───────────────────────────────────────
note("\n4 · B14 rule 33 — stated before the irreversible act, not only at step 4");
const cont = page.getByRole("button", { name: /^Continue$/ }).first();
if (await cont.count()) { await cont.click().catch(() => {}); await page.waitForTimeout(1200); }
await page.screenshot({ path: `${SHOTS}/rat5718_3_review.png`, fullPage: true });
const review = (await page.locator("body").innerText()).replace(/\s+/g, " ");
const onReview = await page.locator('time[datetime="2027-06-30"]').count();
if (/The current rate ends/i.test(review) && onReview > 0) {
  ok("Review & activate repeats it, with the same date");
} else {
  fail("the review step commits a money change without stating what it closes");
}

console.log(
  problems.length === 0
    ? "\nALL CHECKS PASSED"
    : `\n${problems.length} PROBLEM(S):\n - ${problems.join("\n - ")}`,
);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
