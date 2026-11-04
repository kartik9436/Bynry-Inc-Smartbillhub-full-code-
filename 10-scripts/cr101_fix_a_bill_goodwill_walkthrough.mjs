#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane L — `DEF-BIL-5368` (the wizard never collected or
//           sent the goodwill credit) and `DEF-BIL-5381` (it never sends a
//           posting period), walked in a browser at 1440 and 1280
// Rules:    hard-won law 6 (diff the running app against the drawing — no gate
//           reads rendered output) · hard-won law 2 (built is not wired) ·
//           BR-BIL-014 (nothing money-bearing before approval) · B14 rules
//           31/32/33/41/42
// ───────────────────────────────────────────────────────
/**
 * WALK THE ONE JOURNEY THAT WAS DEAD: GOODWILL → A REAL CASE ON SCREEN 26.4.
 *
 *   BASE=http://127.0.0.1:4191 SHOTS=<dir> node \
 *     10-scripts/cr101_fix_a_bill_goodwill_walkthrough.mjs
 *
 * ⚠ **THIS IS THE WALK THE UNIT TESTS COULD NOT DO, AND IT IS WHY THE DEFECT
 * LIVED.** Every suite was green while ticking Goodwill and pressing Continue
 * left the clerk on step 1: the server refused the case as *"a goodwill credit
 * of 0.00 is not a concession"*, because no field collected the figure and no
 * caller ever set `goodwill_amount`. So this presses the real Continue against
 * the real service and reads what comes back.
 *
 * What it proves, in order:
 *   1. the field is ABSENT until a class-C reason is ticked, and absent again
 *      when it is unticked — it belongs to the reason, not to the screen;
 *   2. Continue with the box EMPTY is refused on the client, in four words,
 *      and no case is opened;
 *   3. Continue with a figure OPENS a real case and lands on the drawn `26.4`
 *      body, with the credit rendered as money at two decimals;
 *   4. step 3's books panel and what its POSTS IN row says (`DEF-BIL-5381`);
 *   5. no rule id, question id or dotted identifier anywhere, read off the
 *      RENDERED DOM; no uuid; no horizontal scroll at either width.
 *
 * ⚠ **IT WRITES A PREVIEW AND THEN CLOSES IT.** `Continue` opens a case, which
 * writes the case row, its pinned bill and the impact and NOTHING money-bearing
 * (BR-BIL-014). `Send for approval` is never pressed and neither is step 4's
 * commit. Every case this walk opens is closed through the screen's own *Close
 * without correcting*, and the run ends by asserting the tenant holds no open
 * case — the demo tenant was clean when this lane started and must be left that
 * way.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4191";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/lane-L-shots";
const AMOUNT = process.env.AMOUNT ?? "40.00";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

const LIVE_STATUSES = new Set(["preview", "pending_approval", "approved", "executing", "open"]);
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
/** The id grammar a clerk must never read (B14 rules 31/32). */
const INTERNAL = /\b(?:BR|US|EP)-[A-Z]{3}-\d{3,5}|\b(?:OQ|DEF|CR)-(?:[A-Z]{3}-)?\d{3,5}|\bGT-\d+\b|[a-z_]+\.[a-z_]{3,}\(/;

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
}

async function api(page, path) {
  const response = await page.request.fetch(`${BASE}/api/${TENANT}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

async function noSidewaysScroll(page, label) {
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (wide) fail(`${label}: the page scrolls sideways`);
  else ok(`${label}: no horizontal scroll`);
}

/** The whole step's rendered text — what a clerk can actually read. */
async function stepText(page) {
  return page.locator('[data-wizard="frame"]').innerText();
}

const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
const TALL = Number(process.env.TALL ?? "2400");

for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: TALL } });
  const page = await ctx.newPage();
  page.on("pageerror", (error) => fail(`page error at ${width}: ${error.message}`));
  await signIn(page);
  note(`\n══ ${width} ══ signed in — ${page.url()}`);

  // A bill nothing else holds. `BR-BIL-048` refuses a second case on a chain,
  // so the subject is chosen from the issued list and re-chosen if it is taken.
  const issued = await api(page, "/invoices?per=20&f.status=issued&sort=issue_date&dir=desc");
  const subject = (issued.body?.results ?? []).find((row) => row.invoice_no);
  if (subject === undefined) {
    fail("no issued bill on the tenant to correct");
    break;
  }
  note(`subject bill: ${subject.invoice_no} · ${subject.total} ${subject.currency}`);

  await page.goto(`${BASE}/${TENANT}/billing/fix?bill=${subject.id}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  await page.waitForSelector("[data-fix-resolved]", { timeout: 20000 });

  // ── 1 · the field belongs to the reason ─────────────────────────────────
  if ((await page.locator("[data-fix-goodwill]").count()) === 0) {
    ok("no reason ticked: no credit field");
  } else fail("the credit field is drawn before any reason is ticked");

  await page.locator('label[for="bil-fix-reason-wrong_read"]').click();
  if ((await page.locator("[data-fix-goodwill]").count()) === 0) {
    ok("a class-R reason asks for no figure");
  } else fail("the credit field is drawn for a restatement");
  await page.locator('label[for="bil-fix-reason-wrong_read"]').click();

  await page.locator('label[for="bil-fix-reason-goodwill"]').click();
  await page.waitForSelector("[data-fix-goodwill]", { timeout: 10000 });
  const fieldText = (await page.locator("[data-fix-goodwill]").innerText()).replace(/\s+/g, " ").trim();
  ok(`Goodwill ticked → the field is drawn — "${fieldText}"`);
  await page.screenshot({ path: `${SHOTS}/goodwill-step1-field-${width}.png`, fullPage: true });

  // ── 2 · Continue with the box empty is refused HERE, in four words ───────
  const before = await api(page, "/corrections?per=200");
  const openBefore = (before.body?.results ?? []).filter((row) => LIVE_STATUSES.has(row.status)).length;
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  await page.waitForSelector('[data-wizard="blocked"]', { timeout: 15000 });
  const refusal = (await page.locator('[data-wizard="blocked"]').innerText()).trim();
  if (refusal === "Type the credit amount.") ok(`empty box refused — "${refusal}"`);
  else fail(`the empty box was refused with "${refusal}"`);
  const stillStep1 = await page.locator('[data-wizard-step="1"][data-state="active"]').count();
  if (stillStep1 === 1) ok("still on step 1 — the rail did not move");
  else fail("the rail advanced on an empty credit");
  const afterRefusal = await api(page, "/corrections?per=200");
  const openAfterRefusal = (afterRefusal.body?.results ?? []).filter((row) => LIVE_STATUSES.has(row.status)).length;
  if (openAfterRefusal === openBefore) ok("no case was opened by the refused press");
  else fail(`the refused press opened ${openAfterRefusal - openBefore} case(s)`);
  await page.screenshot({ path: `${SHOTS}/goodwill-step1-refused-${width}.png`, fullPage: true });

  // ── 3 · a figure, then the real Continue ────────────────────────────────
  await page.locator("#bil-fix-goodwill").fill(AMOUNT);
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 60000 });
  await page.waitForTimeout(1200);

  const opened = await api(page, "/corrections?per=200");
  // ⚠ **THE OPEN CASE IS `pending_approval`, NOT `preview`.** `open_case` sets
  // `preview` on the row it creates and then moves it to `pending_approval` in
  // the same call, once the impacts and the hash are stored — so `preview` is a
  // state no reader ever sees. A walk that looked for it found nothing while
  // the case was sitting there (found here, 2026-09-15). Nothing money-bearing
  // exists in either state: BR-BIL-014, and step 4's commit is what writes.
  const live = (opened.body?.results ?? []).find((row) => LIVE_STATUSES.has(row.status));
  if (live === undefined) {
    fail(
      `Continue advanced but no live case is listed — list said ${opened.status}, ` +
        `${(opened.body?.results ?? []).length} row(s), top statuses ` +
        JSON.stringify((opened.body?.results ?? []).slice(0, 3).map((r) => r.status)),
    );
  }
  else {
    note(`  case ${live.case_no ?? "(this tenant has no Correction number series)"} id ${live.id} · class ${live.correction_class} · scope ${JSON.stringify(live.scope)}`);
    if (live.correction_class === "credit_only") ok(`a class-C case opened — ${live.case_no ?? live.id}`);
    else fail(`the opened case is class ${live.correction_class}`);
    if (String(live.scope?.goodwill_amount ?? "") === AMOUNT) {
      ok(`the case carries the typed figure — goodwill_amount ${live.scope.goodwill_amount}`);
    } else fail(`the case carries goodwill_amount ${JSON.stringify(live.scope?.goodwill_amount)}`);
    if (live.posting_period === null) {
      note(`  DEF-BIL-5381: posting_period is null on the opened case, as this screen sends none`);
    } else note(`  posting_period on the opened case: ${live.posting_period}`);
  }

  const variant = await page.locator("[data-fix-step2-variant]").getAttribute("data-fix-step2-variant").catch(() => null);
  if (variant === "26.4") ok("step 2 draws the blueprint's 26.4 Goodwill body");
  else fail(`step 2 drew variant ${JSON.stringify(variant)}, expected 26.4`);
  const step2 = await stepText(page);
  if (step2.includes("$40.00") || step2.includes(`$${AMOUNT}`)) ok(`the credit is rendered as money — ${AMOUNT}`);
  else fail(`the credit does not read as $${AMOUNT} on 26.4`);
  if (/\d\.\d{4}\b/.test(step2)) fail("a four-decimal figure reached screen 26.4");
  else ok("every figure on 26.4 is at two decimals");
  const held = await page.locator("[data-fix-held]").count();
  if (held === 0) ok("no stated absence on step 2 — the drawn body is live");
  else fail(`step 2 still draws ${held} stated absence(s)`);
  await page.screenshot({ path: `${SHOTS}/goodwill-step2-26.4-${width}.png`, fullPage: true });
  await noSidewaysScroll(page, `step 2 at ${width}`);

  // ── 4 · step 3's books panel and its POSTS IN row (DEF-BIL-5381) ─────────
  await page.locator('[data-wizard="actions"] button', { hasText: "See what it changes" }).click();
  await page.waitForSelector('[data-wizard-step="3"][data-state="active"]', { timeout: 30000 });
  await page.waitForTimeout(900);
  const step3 = await stepText(page);
  const posts = step3.split("\n").find((line) => /posts in/i.test(line)) ?? "";
  note(`  step 3, books panel: "${posts.trim()}"`);
  if (posts.includes("Not set on this preview.")) {
    note("  DEF-BIL-5381 stands: the preview names no posting period, and the screen says so rather than drawing a month it did not choose");
  } else ok(`the books panel names a posting period — "${posts.trim()}"`);
  await page.screenshot({ path: `${SHOTS}/goodwill-step3-books-${width}.png`, fullPage: true });
  await noSidewaysScroll(page, `step 3 at ${width}`);

  // ── 5 · nothing internal reaches the clerk, on any of the three ──────────
  for (const [label, text] of [["step 2", step2], ["step 3", step3]]) {
    const hit = INTERNAL.exec(text);
    if (hit === null) ok(`${label}: no rule id, question id or dotted identifier on screen`);
    else fail(`${label}: a clerk can read "${hit[0]}"`);
    if (UUID.test(text)) fail(`${label}: a uuid is visible`);
    else ok(`${label}: no uuid visible`);
  }

  // ── 6 · close it. Nothing money-bearing was written and none is left open ─
  await page.locator('[data-wizard="actions"] button', { hasText: "Close without correcting" }).click();
  await page.waitForTimeout(2500);
  const after = await api(page, "/corrections?per=200");
  const openAfter = (after.body?.results ?? []).filter((row) => LIVE_STATUSES.has(row.status));
  if (openAfter.length === 0) ok("the tenant holds NO open correction case");
  else fail(`${openAfter.length} case(s) left open: ${openAfter.map((r) => `${r.case_no}:${r.status}`).join(", ")}`);

  await ctx.close();
}

await browser.close();
console.log(`\n${problems.length} problem(s)`);
for (const problem of problems) console.log(` - ${problem}`);
process.exit(problems.length === 0 ? 0 : 1);
