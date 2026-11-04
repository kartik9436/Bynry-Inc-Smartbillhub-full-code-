#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane D — Fix a bill step 2's MANY-BILL bodies,
//           `26.2 Several months` and `26.3 A batch`, walked in a browser at
//           both staff widths against a real PostgreSQL tenant
// Rules:    hard-won law 6 (diff the running app against the drawing — no gate
//           reads rendered output) · B14 rules 41/42 · NFR-3 · the UI skill's
//           §15 close-out
// ───────────────────────────────────────────────────────
/**
 * WALK 26.2 AND 26.3, AT 1440 AND 1280, AND CAPTURE THEM.
 *
 *   BASE=http://127.0.0.1:8207 SHOTS=<dir> node \
 *     10-scripts/cr101_fix_a_bill_step2_bulk_walkthrough.mjs
 *
 * ⚠ **THIS ONE WRITES A CASE ROW, AND SAYS SO.** Step 1's Continue calls
 * `POST /corrections`, which opens a PREVIEW: the case, its pinned bills and
 * their impacts. Nothing money-bearing exists — no credit note, no rebill, no
 * journal line (BR-BIL-014) — and **every case this walk opens is ABANDONED
 * before it moves on**, so the bills are free for a sibling lane. Approve and
 * commit are never pressed.
 *
 * ⚠ **A RUN-SCOPE CASE PINS EVERY BILL IN THE RUN.** That is the whole point of
 * 26.3 and it is also why the abandon is not optional: leaving one open would
 * lock every bill in that run behind BR-BIL-048 for everybody else.
 *
 * What it proves: the two variants render from a REAL case at the real address,
 * the answer band carries both directions, the aggregate's five rows and the
 * warning counts are the server's, `List them` filters the collapsed list, the
 * per-bill rows carry what was paid and where it goes, no figure shows four
 * decimals, no uuid is visible, and the page does not scroll sideways.
 * What it cannot: whether it LOOKS like p136/p137 — that is a person, over the
 * PNGs it saves, written up in the lane record.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8207";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/fix-a-bill-step2-bulk";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

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

async function noSidewaysScroll(page, label) {
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (wide) fail(`${label}: the page scrolls sideways`);
  else ok(`${label}: no horizontal scroll`);
}

/**
 * Open a case from step 1 and land on step 2. `configure` picks the scope.
 * Returns false when the case could not be opened, with the reason printed —
 * a sibling's open case on one of the bills is the common one (BR-BIL-048).
 */
async function openCase(page, configure, label) {
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  await configure(page);
  await page.locator('label[for="bil-fix-reason-wrong_rate_plan"]').click();
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  const landed = await page
    .waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 90000 })
    .then(() => true)
    .catch(() => false);
  if (!landed) {
    const why = await page.locator('[data-wizard="frame"]').innerText();
    fail(`${label}: the case would not open — ${why.slice(0, 260).replace(/\s+/g, " ")}`);
    return false;
  }
  await page.waitForTimeout(1200);
  return true;
}

/** Close the case with a reason, so its bills are free for a sibling lane. */
async function abandon(page, label) {
  const button = page.locator("button", { hasText: "Close without correcting" }).first();
  if ((await button.count()) === 0) {
    fail(`${label}: no way to close the case — it is left OPEN on the tenant`);
    return;
  }
  await button.click();
  await page.waitForTimeout(2500);
  ok(`${label}: the case was abandoned, so its bills are free`);
}

const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
// Tall on purpose — the step content scrolls INSIDE the shell, so a full-page
// capture at laptop height photographs the inner container wherever the last
// click left it (lane A, 2026-09-15). Width is the design variable.
const TALL = Number(process.env.TALL ?? "2600");

for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: TALL } });
  const page = await ctx.newPage();
  page.on("pageerror", (error) => fail(`page error at ${width}: ${error.message}`));
  await signIn(page);
  note(`\n=== ${width} × ${TALL} — signed in ===`);

  // ── 26.3 · A batch (a bill run) ─────────────────────────────────────────
  const openedBatch = await openCase(
    page,
    async (p) => {
      await p.locator("#bil-fix-scope").selectOption("run");
      await p.waitForSelector("#bil-fix-run", { timeout: 15000 });
      // ⚠ WAIT FOR AN OPTION, NOT FOR THE SELECT. The runs read is `enabled`
      // only once the kind is `run`, so the control is in the DOM carrying its
      // placeholder alone for as long as the request is out — and reading it
      // then gives "no bill run to choose" over a tenant that has four.
      await p.waitForFunction(
        () => document.querySelectorAll("#bil-fix-run option[value]:not([value=''])").length > 0,
        undefined,
        { timeout: 30000 },
      );
      const runs = await p
        .locator("#bil-fix-run option")
        .evaluateAll((opts) => opts.map((o) => o.value).filter(Boolean));
      const pick = process.env.RUN_ID ?? runs[0];
      await p.locator("#bil-fix-run").selectOption(pick);
      await p.waitForTimeout(2500);
    },
    `26.3 at ${width}`,
  );

  if (openedBatch) {
    const variant = await page
      .locator("[data-fix-step2-variant]")
      .getAttribute("data-fix-step2-variant");
    if (variant === "26.3") ok(`26.3 renders for a run-scope class-R case`);
    else fail(`a run-scope case rendered variant ${variant}`);

    const held = await page.locator("[data-fix-held]").count();
    if (held === 0) ok("no stated absence over the drawn screen");
    else fail('step 2 still draws "new layout not built yet" over a built screen');

    const band = await page.locator("[data-fix-answer]").innerText().catch(() => "");
    if (/up/.test(band) && /down/.test(band)) ok(`the answer names both directions — ${band.replace(/\s+/g, " ")}`);
    else fail(`the answer band collapses the directions — ${band.replace(/\s+/g, " ")}`);

    const groups = await page.locator('[data-testid^="fix-bulk-group-"] h2').allTextContents();
    note(`  groups: ${JSON.stringify(groups.map((g) => g.replace(/^\d\s*/, "")))}`);
    if (groups.length === 5) ok("five groups, as p137 and p129 ask");
    else fail(`26.3 draws ${groups.length} groups`);

    for (const key of ["credited", "replaced", "up", "down", "net"]) {
      const row = await page.locator(`[data-fix-move="${key}"]`).count();
      if (row !== 1) fail(`the which-way table has no ${key} row`);
    }
    const which = await page.locator("[data-fix-which-way]").innerText();
    note(`  which way they move: ${which.replace(/\s+/g, " ").slice(0, 220)}`);
    if (/\d\.\d{4}\b/.test(which)) fail("a four-decimal figure reached the which-way table");
    else ok("every figure in the which-way table is at two decimals");

    const eye = await page.locator("[data-fix-human-eye]").innerText();
    note(`  rows that need a human eye: ${eye.replace(/\s+/g, " ").slice(0, 220)}`);

    await page.screenshot({ path: `${SHOTS}/step2-batch-${width}.png`, fullPage: true });

    // `List them` must OPEN the collapsed list and filter it — a link that
    // scrolled to nothing would be the dead control law 2's mirror names.
    const listThem = page.locator("[data-fix-list-them]").first();
    if ((await listThem.count()) === 1) {
      const before = await page.locator("[data-fix-bulk-rows] tbody tr").count();
      await listThem.click();
      await page.waitForTimeout(900);
      const after = await page.locator("[data-fix-bulk-rows] tbody tr").count();
      if (before === 0 && after > 0) ok(`List them opened the collapsed list — ${after} row(s)`);
      else fail(`List them: ${before} rows before, ${after} after`);
      const rows = await page.locator("[data-fix-bulk-rows]").innerText();
      if (/\d\.\d{4}\b/.test(rows)) fail("a four-decimal figure reached the bill rows");
      else ok("every figure in the bill rows is at two decimals");
      await page.screenshot({ path: `${SHOTS}/step2-batch-listed-${width}.png`, fullPage: true });
    } else {
      note("  no warned row on this case, so `List them` is not drawn — nothing to press");
      await page.locator("summary, [aria-expanded]").filter({ hasText: "Show every bill" }).first().click().catch(() => undefined);
      await page.waitForTimeout(900);
      await page.screenshot({ path: `${SHOTS}/step2-batch-listed-${width}.png`, fullPage: true });
    }

    const body = await page.locator('[data-wizard="frame"]').innerText();
    if (UUID.test(body)) fail("a uuid is visible on step 2");
    else ok("no uuid visible on step 2");
    await noSidewaysScroll(page, `26.3 at ${width}`);
    await abandon(page, `26.3 at ${width}`);
  }

  // ── 26.2 · Several months (a window, many accounts) ─────────────────────
  const openedWindow = await openCase(
    page,
    async (p) => {
      await p.locator("#bil-fix-scope").selectOption("date_range");
      await p.waitForSelector("#bil-fix-from", { timeout: 15000 });
      await p.locator("#bil-fix-from").fill(process.env.FROM ?? "2026-06-01");
      await p.locator("#bil-fix-to").fill(process.env.TO ?? "2026-06-30");
      await p.waitForTimeout(2000);
    },
    `26.2 at ${width}`,
  );

  if (openedWindow) {
    const variant = await page
      .locator("[data-fix-step2-variant]")
      .getAttribute("data-fix-step2-variant");
    if (variant === "26.2") ok("26.2 renders for a date-range class-R case");
    else fail(`a date-range case rendered variant ${variant}`);

    const groups = await page.locator('[data-testid^="fix-bulk-group-"] h2').allTextContents();
    note(`  groups: ${JSON.stringify(groups.map((g) => g.replace(/^\d\s*/, "")))}`);
    if (groups.length === 2) ok("two groups, as p136 draws");
    else fail(`26.2 draws ${groups.length} groups`);

    const headers = await page.locator("[data-fix-bulk-rows] thead th").allInnerTexts();
    note(`  columns: ${JSON.stringify(headers.map((h) => h.replace(/[↑↓\s]+$/g, "").trim()))}`);
    const rows = await page.locator("[data-fix-bulk-rows] tbody tr").count();
    if (rows > 0) ok(`${rows} bill row(s) drawn open, as p136 draws them`);
    else fail("26.2 draws no bill rows");

    const first = await page.locator("[data-fix-bulk-rows] tbody tr").first().innerText();
    note(`  first row: ${first.replace(/\s+/g, " ").slice(0, 200)}`);
    if (/\d\.\d{4}\b/.test(first)) fail("a four-decimal figure reached a bill row");
    else ok("the bill row is at two decimals");
    const absent = await page.locator('[data-fix-absent="period"]').count();
    if (absent === rows) ok(`the month is stated as absent on all ${rows} rows, never guessed`);
    else fail(`${absent} of ${rows} rows state the month as absent`);

    await page.screenshot({ path: `${SHOTS}/step2-months-${width}.png`, fullPage: true });
    const body = await page.locator('[data-wizard="frame"]').innerText();
    if (UUID.test(body)) fail("a uuid is visible on 26.2");
    else ok("no uuid visible on 26.2");
    await noSidewaysScroll(page, `26.2 at ${width}`);
    await abandon(page, `26.2 at ${width}`);
  }

  await ctx.close();
}

await browser.close();
console.log(`\n${problems.length} problem(s)`);
for (const problem of problems) console.log("  - " + problem);
process.exit(problems.length === 0 ? 0 : 1);
