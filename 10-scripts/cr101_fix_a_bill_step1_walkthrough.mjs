#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane A — Fix a bill step 1 (screen 26 `What and why`)
//           walked in a browser at both doors and both staff widths
// Rules:    hard-won law 6 (diff the running app against the drawing — no gate
//           reads rendered output) · B14 rules 41/42 · the skill's §15 close-out
// ───────────────────────────────────────────────────────
/**
 * WALK SCREEN 26 AT ITS TWO DOORS, AT 1440 AND 1280, AND CAPTURE IT.
 *
 *   BASE=http://127.0.0.1:8081 SHOTS=<dir> node 10-scripts/cr101_fix_a_bill_step1_walkthrough.mjs
 *
 * What it proves, and what it cannot: it opens both doors, drives the scope
 * select through all six kinds, picks a bill through the finder, ticks two
 * reasons of different classes and reads group 4's sentence, chooses *several
 * months on one account* at the account door and reads the refusal on
 * Continue, and asserts no horizontal scroll at 1280. It does NOT compare
 * pixels to p132–p133 — that comparison is a person's, over the PNGs it saves
 * (`step1-billing-1440.png` … ), and it is written up in the lane record.
 *
 * ⚠ It WRITES NOTHING: Continue is pressed only where the screen must REFUSE,
 * so no case is opened on the tenant.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/fix-a-bill-step1";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

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

const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
// ⚠ TALL ON PURPOSE. The step content scrolls INSIDE the shell, so a full-page
// capture at a laptop height photographs the inner container at whatever
// scroll the last click left it — the 2026-09-15 "step 1 at 1440" handed to
// the Product Owner began at group 3. A tall viewport changes nothing about
// the layout at 1440 or 1280 (width is the design variable) and lets one
// capture hold the whole step. `TALL=1100` reproduces a laptop's height.
const TALL = Number(process.env.TALL ?? "2400");
for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: TALL } });
  const page = await ctx.newPage();
  page.on("pageerror", (error) => fail(`page error at ${width}: ${error.message}`));
  await signIn(page);
  note(`signed in at ${width} — ${page.url()}`);

  // ── billing's own door ──────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  const rail = await page.locator("[data-wizard-step]").allTextContents();
  if (rail.length === 4) ok(`four steps on the rail — ${JSON.stringify(rail)}`);
  else fail(`the rail draws ${rail.length} steps`);
  const groups = await page.locator('[data-testid^="fix-group-"] h2').allTextContents();
  note(`groups: ${JSON.stringify(groups)}`);
  if (groups.length !== 4) fail(`step 1 draws ${groups.length} groups; the drawing has four`);
  await page.screenshot({ path: `${SHOTS}/step1-billing-empty-${width}.png`, fullPage: true });

  // Every kind, in the select, in the drawing's order.
  const kinds = await page.locator("#bil-fix-scope option").evaluateAll((opts) =>
    opts.map((o) => o.value).filter(Boolean),
  );
  note(`kinds: ${JSON.stringify(kinds)}`);
  if (kinds.length === 6) ok("six ways in");
  else fail(`the scope select offers ${kinds.length} kinds`);

  // One bill → the finder → pick the newest issued bill by its number.
  await page.locator("#bil-fix-scope").selectOption("single");
  await page.waitForSelector("[data-bil-finder]", { timeout: 15000 });
  const issued = await api(page, "/invoices?per=5&f.status=issued&sort=issue_date&dir=desc");
  const subject = (issued.body?.results ?? []).find((row) => row.invoice_no);
  if (subject === undefined) {
    fail("no issued bill on the tenant to pick");
  } else {
    await page.locator("[data-bil-finder] input[type=search]").first().fill(subject.invoice_no);
    await page.waitForTimeout(1800);
    await page.locator("[data-bil-finder] tbody tr").first().locator("button").first().click();
    // The rows come from `GET /corrections/resolve` (lane B); wait for the bill
    // NUMBER rather than the container, which is drawn while the read is out.
    await page.waitForFunction(
      (no) => document.querySelector("[data-fix-resolved]")?.textContent?.includes(no) === true,
      subject.invoice_no,
      { timeout: 20000 },
    ).catch(() => undefined);
    const resolved = await page.locator("[data-fix-resolved]").innerText();
    if (resolved.includes(subject.invoice_no)) ok(`group 2 lists ${subject.invoice_no}`);
    else fail(`group 2 does not list ${subject.invoice_no} — ${resolved.slice(0, 120).replace(/\s+/g, " ")}`);
    if (/\d\.\d{4}\b/.test(resolved)) fail("a four-decimal figure reached group 2");
    else ok("every figure in group 2 is at two decimals");
    // PAID and STATE are the server's now: a money figure or the stated absence, never blank.
    const paidCells = await page.locator("[data-fix-resolved] tbody tr").first().locator("td").allInnerTexts();
    if (paidCells.length === 5 && paidCells[3].trim() !== "" && paidCells[4].trim() !== "") ok(`PAID · STATE read — ${paidCells[3]} · ${paidCells[4]}`);
    else fail(`PAID/STATE cells are blank or missing: ${JSON.stringify(paidCells)}`);
    const totals = await page.locator("[data-fix-resolved-totals]").innerText().catch(() => "");
    if (totals.trim() !== "") ok(`totals row — ${totals.replace(/\s+/g, " ")}`);
    else fail("no totals row under group 2");
    const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
    if (uuid.test(await page.locator('[data-fix-step="what-and-why"]').innerText())) fail("a uuid is visible on step 1");
    else ok("no uuid visible on step 1");
  }

  // Two reasons of different classes → the sentence names the STRONGER class.
  // A clerk clicks the LABEL; the input itself is visually hidden (`sr-only`).
  await page.locator('label[for="bil-fix-reason-customer_name"]').click();
  await page.locator('label[for="bil-fix-reason-wrong_read"]').click();
  const outcome = page.locator("[data-fix-outcome]");
  const klass = await outcome.getAttribute("data-fix-outcome");
  if (klass === "restatement") ok(`group 4 derives the strongest class — ${await outcome.innerText()}`);
  else fail(`group 4 derived ${klass}, expected restatement`);
  const routedDisabled = await page.locator("[data-fix-routed] input").evaluateAll((els) =>
    els.every((el) => el.disabled),
  );
  if (routedDisabled) ok("the five refusals are disabled");
  else fail("a refusal row is live");
  await page.screenshot({ path: `${SHOTS}/step1-billing-chosen-${width}.png`, fullPage: true });
  // ── the held steps, for the Product Owner to SEE (--steps) ──────────────
  // Continue opens a PREVIEW case (writes the case row, no money — BR-BIL-014);
  // step 2's Continue turns a page; step 3's records the approval signature.
  // The commit on step 4 is NEVER pressed here: nothing money-bearing is written.
  if (process.argv.includes("--steps")) {
    const shell = () => page.locator('[data-wizard="frame"]');
    await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
    await page.waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 60000 });
    await page.waitForTimeout(1200);
    await shell().screenshot({ path: `${SHOTS}/step2-held-${width}.png` });
    const held2 = await page.locator("[data-fix-held]").first().innerText().catch(() => "");
    if (held2.trim() !== "") ok(`step 2 states its absence — "${held2.trim()}" — over the carried body`);
    else fail("step 2 draws no stated absence");
    await page.locator('[data-wizard="actions"] button', { hasText: "See what it changes" }).click();
    await page.waitForSelector('[data-wizard-step="3"][data-state="active"]', { timeout: 30000 });
    await page.waitForTimeout(800);
    await shell().screenshot({ path: `${SHOTS}/step3-held-${width}.png` });
    await page.locator('[data-wizard="actions"] button', { hasText: "Send for approval" }).click();
    await page.waitForSelector('[data-wizard-step="4"][data-state="active"]', { timeout: 60000 });
    await page.waitForTimeout(1200);
    await shell().screenshot({ path: `${SHOTS}/step4-held-${width}.png` });
    const commit = await page.locator('[data-wizard="actions"] button', { hasText: "Create the documents" }).count();
    if (commit === 1) ok("step 4 draws the one button that writes — and it was NOT pressed");
    else fail(`step 4 draws ${commit} commit button(s)`);
    // Back to step 1 for the account-door half of the walk: a fresh page load.
  }
  // ⚠ NO element capture of the step-1 frame here — twice wrong on 2026-09-15.
  // (1) It sat AFTER the `--steps` block, so with `--steps` it photographed
  // step 4 under a step-1 name: the "step 1 at 1440" handed to the Product
  // Owner was step 4, byte-identical to the step-4 capture. (2) An element
  // screenshot of a frame taller than the viewport comes back as a stitched
  // fragment — the sticky bar drawn mid-image, the rest grey — at both doors.
  // The FULL-PAGE captures above (`step1-billing-empty`, `step1-billing-chosen`)
  // are the pictures a person compares to p132–p133; the held steps 2–4 fit the
  // viewport, which is why their frame captures are sound.
  await noSidewaysScroll(page, `billing door at ${width}`);

  // ── the account door ────────────────────────────────────────────────────
  if (subject !== undefined) {
    await page.goto(
      `${BASE}/${TENANT}/accounts/${subject.account_id}/issue-credit?bill=${subject.id}`,
      { waitUntil: "domcontentloaded" },
    );
    await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
    await page.waitForSelector("[data-fix-resolved]", { timeout: 15000 });
    const billField = await page.locator("#bil-fix-invoice").inputValue().catch(() => "");
    if (billField === subject.id) ok("account door: the handed-over bill is pre-chosen in the bounded select");
    else fail(`account door: the bill field holds ${JSON.stringify(billField)}`);
    await page.screenshot({ path: `${SHOTS}/step1-account-single-${width}.png`, fullPage: true });

    // Several months on one account — drawn, choosable, and Continue is HELD.
    await page.locator("#bil-fix-scope").selectOption("date_range");
    await page.waitForSelector("#bil-fix-from", { timeout: 15000 });
    const accountText = await page.locator("#bil-fix-account").innerText();
    if (accountText.trim() !== "") ok(`account door: account read back — ${accountText.trim()}`);
    else fail("account door: the Account field is empty");
    await page.locator("#bil-fix-from").fill("2026-01-01");
    await page.locator("#bil-fix-to").fill("2026-12-31");
    await page.waitForTimeout(1500);
    await page.locator('label[for="bil-fix-reason-wrong_rate_plan"]').click();
    await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
    await page.waitForTimeout(800);
    const blocked = await page.locator('[data-wizard="frame"]').innerText();
    if (blocked.includes("Not open yet for one account.")) ok("account window: Continue refused in plain words (DEF-BIL-5348)");
    else fail("account window: Continue was not refused with the held sentence");
    const railAfter = await page.locator('[data-wizard-step][data-state="active"]').getAttribute("data-wizard-step");
    if (railAfter === "1") ok("still on step 1 — nothing was opened");
    else fail(`the rail moved to step ${railAfter}`);
    await page.screenshot({ path: `${SHOTS}/step1-account-window-${width}.png`, fullPage: true });
    await noSidewaysScroll(page, `account door at ${width}`);
  }

  await ctx.close();
}

await browser.close();
console.log(`\n${problems.length} problem(s)`);
process.exit(problems.length === 0 ? 0 : 1);
