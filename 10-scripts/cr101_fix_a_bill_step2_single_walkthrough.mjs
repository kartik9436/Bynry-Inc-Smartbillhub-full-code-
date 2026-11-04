#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane C — Fix a bill STEP TWO, entries `26.1 One bill`
//           (class R) and `26.5 The page only` (class D), walked in a browser
//           at both staff widths
// Rules:    hard-won law 6 (diff the running app against the drawing — no gate
//           reads rendered output) · B14 rules 31, 32, 33, 41, 42 · the UI
//           skill's §15 close-out
// Defects:  DEF-BIL-5349 (the status as a raw code) · DEF-BIL-5355 · DEF-BIL-5356
// ───────────────────────────────────────────────────────
/**
 * WALK STEP TWO'S TWO SINGLE-BILL SHAPES, AT 1440 AND 1280, AND CAPTURE THEM.
 *
 *   BASE=http://127.0.0.1:8126 SHOTS=<dir> \
 *     node 10-scripts/cr101_fix_a_bill_step2_single_walkthrough.mjs
 *
 * What it proves: that step 2 renders the DRAWN body rather than the carried
 * one for a class-R single case and for a class-D case; that every figure is at
 * two decimals; that the unmoved lines are on screen beside the moved ones;
 * that the three absent panels on 26.5 are DRAWN with their reason; that the
 * case status reads as words rather than `pending_approval`; and that no
 * database id, rule id or dotted identifier reaches the clerk.
 *
 * What it cannot prove: that it LOOKS like p134/p135 and p139/p140. That
 * comparison is a person's, over the PNGs this saves, and it is written up in
 * the lane record (hard-won law 6 — the one law with no tool behind it).
 *
 * ⚠ **IT OPENS TWO PREVIEW CASES AND ABANDONS BOTH.** A preview writes the case
 * row and its pinned bill and nothing money-bearing (BR-BIL-014); the approval
 * signature is never recorded and the step-4 commit is never pressed. Each case
 * is closed with a reason at the end of its own pass, so the bill is free for a
 * sibling lane — which is the state the shared demo tenant has to be left in.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8126";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/fix-a-bill-step2-single";
mkdirSync(SHOTS, { recursive: true });

/** Lane A opened a case on this one and APPROVED it; it is not free. */
const RESERVED = (process.env.RESERVED ?? "BL-2608-000042").split(",");

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

/** `CLAUDE.md`'s id grammar, and a dotted Python identifier. */
const INTERNAL =
  /\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\.[a-z_][a-z0-9_]*/g;
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
/** Money at anything other than two decimals (DEF-BIL-5337's shape). */
const OVER_PRECISE = /\d\.\d{3,}/;

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

/**
 * Open a case from step 1 on a bill nobody else is holding, and land on step 2.
 * Returns the bill it used, or null when the tenant has none free.
 */
async function openCase(page, reasonCode, taken) {
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  const issued = await api(page, "/invoices?per=40&f.status=issued&sort=issue_date&dir=desc");
  const subject = (issued.body?.results ?? []).find(
    (row) => row.invoice_no && !RESERVED.includes(row.invoice_no) && !taken.includes(row.invoice_no),
  );
  if (subject === undefined) {
    fail("no free issued bill on the tenant to open a case on");
    return null;
  }
  await page.locator("#bil-fix-scope").selectOption("single");
  await page.waitForSelector("[data-bil-finder]", { timeout: 15000 });
  await page.locator("[data-bil-finder] input[type=search]").first().fill(subject.invoice_no);
  await page.waitForTimeout(1800);
  await page.locator("[data-bil-finder] tbody tr").first().locator("button").first().click();
  await page.locator(`label[for="bil-fix-reason-${reasonCode}"]`).click();
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 60000 });
  await page.waitForSelector("[data-fix-step2-variant]", { timeout: 30000 });
  return subject;
}

async function abandon(page, label) {
  const button = page.locator('[data-wizard="secondary"] button, button', {
    hasText: "Close without correcting",
  });
  if ((await button.count()) === 0) {
    fail(`${label}: no 'Close without correcting' control to abandon the case with`);
    return;
  }
  await button.first().click();
  await page.waitForTimeout(2500);
  ok(`${label}: the case was abandoned, so the bill is free again`);
}

async function readStep(page, width, entry) {
  const body = page.locator("[data-fix-step2-variant]");
  const variant = await body.getAttribute("data-fix-step2-variant");
  if (variant === entry) ok(`step 2 renders entry ${entry}`);
  else fail(`step 2 rendered ${variant}, expected ${entry}`);

  // The carried body's stated absence must NOT be over a drawn variant.
  if ((await page.locator("[data-fix-held]").count()) === 0) {
    ok("no 'new layout not built yet' over the drawn body");
  } else {
    fail("the stated absence is still drawn over a variant that has landed");
  }

  const text = await body.innerText();
  const band = await page.locator("[data-fix-answer]").innerText();
  note(`  answer: ${band.replace(/\s+/g, " ")}`);
  if (band.trim() === "") fail("the answer band is empty");

  const status = await page.locator("[data-fix-status]").innerText();
  const code = await page.locator("[data-fix-status]").getAttribute("data-fix-status");
  if (status.trim() === code) fail(`DEF-BIL-5349: the status still reads its code — ${status}`);
  else ok(`the status reads "${status.trim()}" for ${code}`);

  const internals = text.match(INTERNAL) ?? [];
  if (internals.length === 0) ok("no rule id, question id or dotted identifier on screen");
  else fail(`internal references on screen: ${JSON.stringify([...new Set(internals)])}`);

  if (UUID.test(text)) fail("a database id is visible on step 2");
  else ok("no database id on step 2");

  if (OVER_PRECISE.test(text)) {
    fail(`a figure past two decimals is on screen: ${(text.match(OVER_PRECISE) ?? [])[0]}`);
  } else {
    ok("every figure is at two decimals");
  }

  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (wide) fail(`${entry} at ${width}: the page scrolls sideways`);
  else ok(`${entry} at ${width}: no horizontal scroll`);
  return text;
}

const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
// Tall on purpose — the step content scrolls INSIDE the shell, so a full-page
// capture at a laptop height photographs the inner container wherever the last
// click left it (lane A's own correction, 2026-09-15). Width is the design
// variable; the layout at 1440 and 1280 is unchanged by the height.
const TALL = Number(process.env.TALL ?? "2400");
const taken = [];

for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: TALL } });
  const page = await ctx.newPage();
  page.on("pageerror", (error) => fail(`page error at ${width}: ${error.message}`));
  await signIn(page);
  note(`\n══ ${width} ══ signed in`);

  // ── 26.1 · one bill, class R (`wrong_read`) ─────────────────────────────
  note(`\n26.1 · one bill — class R, at ${width}`);
  const rBill = await openCase(page, "wrong_read", taken);
  if (rBill !== null) {
    taken.push(rBill.invoice_no);
    note(`  subject: ${rBill.invoice_no}`);
    const text = await readStep(page, width, "26.1");
    for (const [testid, what] of [
      ["fix-what-group-lines", "1 line by line"],
      ["fix-what-group-discount", "2 their discount"],
      ["fix-what-group-paid", "3 what they have paid"],
    ]) {
      if ((await page.locator(`[data-testid="${testid}"]`).count()) === 1) ok(`group drawn — ${what}`);
      else fail(`group missing — ${what}`);
    }
    const rows = await page.locator("[data-fix-lines] tbody tr").count();
    const moved = await page.locator("[data-fix-lines] tbody tr[data-fix-line-moved]").count();
    if (rows > moved) ok(`${rows} lines drawn, ${moved} of them moved — the unmoved ones are on screen`);
    else fail(`every drawn line is a moved one (${rows} rows, ${moved} moved): the trail cannot be checked`);
    const total = await page.locator("[data-fix-lines-total]").innerText().catch(() => "");
    if (total.trim() !== "") ok(`the total row reads ${total.replace(/\s+/g, " ")}`);
    else fail("no total row under the trail");
    const paid = await page.locator('[data-testid="fix-what-group-paid"]').innerText();
    note(`  what they have paid: ${paid.replace(/\s+/g, " ").slice(0, 160)}`);
    if (/\$/.test(paid)) ok("the payments panel carries figures");
    else note("  (the payments panel states its absence on this case — the seam or the class)");
    if (/\bdiscount\b/i.test(text) || /reduction/i.test(text)) ok("the discount question is answered");
    await page.screenshot({ path: `${SHOTS}/step2-26.1-one-bill-${width}.png`, fullPage: true });
    await abandon(page, `26.1 at ${width}`);
  }

  // ── 26.5 · the page only, class D (`customer_name`) ─────────────────────
  note(`\n26.5 · the page only — class D, at ${width}`);
  const dBill = await openCase(page, "customer_name", taken);
  if (dBill !== null) {
    taken.push(dBill.invoice_no);
    note(`  subject: ${dBill.invoice_no}`);
    await readStep(page, width, "26.5");
    for (const [testid, what] of [
      ["fix-what-group-fields", "1 what changes on the page"],
      ["fix-what-group-money", "2 what the money does"],
      ["fix-what-group-document", "3 this becomes the document they are entitled to"],
    ]) {
      if ((await page.locator(`[data-testid="${testid}"]`).count()) === 1) ok(`group drawn — ${what}`);
      else fail(`group missing — ${what}`);
    }
    const panels = await page.locator("[data-fix-absent-panel]").count();
    if (panels === 3) ok("all three absent panels are DRAWN, never omitted");
    else fail(`${panels} absent panel(s) drawn; the drawing and p129 give three`);
    const moves = await page.locator("[data-fix-page-moves]").innerText().catch(() => "");
    if (/\$0\.00/.test(moves)) ok(`the $0.00 is drawn, not implied — ${moves.replace(/\s+/g, " ")}`);
    else fail(`the balance-moves row reads ${JSON.stringify(moves)}`);
    const absent = await page.locator('[data-fix-absent="document-fields"]').innerText().catch(() => "");
    if (absent.trim() !== "") ok(`DEF-BIL-5355 is stated rather than guessed — "${absent.trim()}"`);
    else fail("group 1 draws neither a diff nor its absence");
    await page.screenshot({ path: `${SHOTS}/step2-26.5-page-only-${width}.png`, fullPage: true });
    await abandon(page, `26.5 at ${width}`);
  }

  await ctx.close();
}

await browser.close();
console.log(`\n${problems.length} problem(s)`);
for (const problem of problems) console.log("  ✗ " + problem);
console.log(`screenshots in ${SHOTS}`);
process.exit(problems.length === 0 ? 0 : 1);
