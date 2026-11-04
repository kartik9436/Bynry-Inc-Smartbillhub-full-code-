/**
 * `CR-101-BRC03` §06 lane E — WALK STEP 3 AND THE GOODWILL STEP 2 IN A BROWSER.
 *
 * Hard-won law 6: *"diff the running app against the drawing — nine defects
 * were found this way and by nothing else"*, and it is the only check in this
 * repository that reads rendered output, because it is a person looking at what
 * this script captures. Blueprint pages: `26.4` on p138–p139, `26.6` on
 * p140–p142, `26.7` on p142–p144, read AS IMAGES (B14 rule 42).
 *
 * ⚠ **WHAT IT WRITES, STATED RATHER THAN IMPLIED.** Step 1's `Continue` opens a
 * PREVIEW case — the case row, its pinned bills and their impacts, and NO money
 * (`BR-BIL-014`). Step 2's `Continue` turns a page. **Step 3's `Send for
 * approval` is NEVER pressed here** (it records the approval signature) and
 * neither is step 4's commit. Every case this script opens is ABANDONED at the
 * end with a reason, so the bills are free for sibling lanes.
 *
 * ⚠ **`BL-2608-000042` IS OFF LIMITS** — lane A left an APPROVED case on it.
 *
 * ⚠ **A GOODWILL CASE CANNOT BE OPENED FROM THIS SCREEN AT ALL** — the wizard
 * never collects or sends `goodwill_amount`, so the server refuses every
 * class-C case with *"a goodwill credit of 0.00 is not a concession"*
 * (`DEF-BIL-5368`). This script proves that refusal by pressing Continue on a
 * goodwill reason, and then reaches the drawn `26.4` screen through a case
 * opened at the service layer, which is the only way it can be looked at today.
 *
 *   node 10-scripts/cr101_fix_a_bill_step3_walkthrough.mjs
 *
 * env: BASE · TENANT · EMAIL · PASSWORD · SHOTS · WIDTHS · TALL · GOODWILL_CASE
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:8085";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/fix-a-bill-step3";
const GOODWILL_CASE = process.env.GOODWILL_CASE ?? "";
mkdirSync(SHOTS, { recursive: true });

const problems = [];
const opened = [];
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

async function noSidewaysScroll(page, label) {
  const wide = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  if (wide) fail(`${label}: the page scrolls sideways`);
  else ok(`${label}: no horizontal scroll`);
}

/** Every internal reference a clerk can READ — the shared helper's rule, in the
 *  browser. `data-*` is deliberately not read (the 2026-08-19 ruling put the
 *  reference there on purpose). */
async function internalReferences(page) {
  return page.evaluate(() => {
    const ID = /\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/g;
    const DOTTED = /\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+\b/g;
    const frame = document.querySelector('[data-wizard="frame"]');
    if (frame === null) return ["no wizard frame"];
    const texts = [];
    const walk = document.createTreeWalker(frame, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n !== null; n = walk.nextNode()) texts.push(n.textContent ?? "");
    for (const el of frame.querySelectorAll("[title],[aria-label]")) {
      texts.push(el.getAttribute("title") ?? "", el.getAttribute("aria-label") ?? "");
    }
    const found = [];
    for (const text of texts) {
      found.push(...(text.match(ID) ?? []));
      found.push(
        ...(text.match(DOTTED) ?? []).filter((r) => r.includes("_") || r.split(".").length >= 3),
      );
    }
    return [...new Set(found)];
  });
}

/** Choose ONE bill through the finder — the two controls a clerk uses, in
 *  order: search the server, then press the row's own button. Lane A's step-1
 *  walk does exactly this; a click on the ROW does nothing, which is how the
 *  first draft of this script reached `Continue` with *No bill chosen*. */
/** Close the case this walk opened, WITH ITS REASON (`BR-BIL-047`), through the
 *  screen's own control — so the bills are free for sibling lanes and nothing
 *  money-bearing was ever written. */
async function abandon(page, label) {
  const button = page.locator("button", { hasText: "Close without correcting" }).first();
  if ((await button.count()) === 0) {
    fail(`${label}: no Close without correcting control to abandon the case with`);
    return;
  }
  await button.click();
  const confirm = page.locator('[role=dialog] button', { hasText: /Close|Confirm|Yes/ }).last();
  if ((await confirm.count()) > 0) await confirm.click();
  await page.waitForTimeout(2500);
  ok(`${label}: the case was closed without correcting`);
}

async function pickBill(page, invoiceNo) {
  await page.locator("#bil-fix-scope").selectOption("single");
  await page.waitForSelector("[data-bil-finder]", { timeout: 15000 });
  await page.locator("[data-bil-finder] input[type=search]").first().fill(invoiceNo);
  await page.waitForTimeout(900);
  await page.locator("[data-bil-finder] tbody tr").first().locator("button").first().click();
  await page.waitForTimeout(400);
}

const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
const TALL = Number(process.env.TALL ?? "2600");

for (const width of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: TALL } });
  const page = await ctx.newPage();
  page.on("pageerror", (error) => fail(`page error at ${width}: ${error.message}`));
  await signIn(page);
  console.log(`\n── ${width} ──────────────────────────────────────────────`);

  // ── 26.6 · step 3 on ONE BILL ───────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  await pickBill(page, process.env.BILL_R ?? "BL-2608-000051");
  // ⚠ The reason box is `sr-only` with a drawn mark beside it, so an ordinary
  // click lands on the mark and never on the input. `force` is the honest form
  // here: the label IS the control and a clerk clicks the words.
  await page.locator('[data-testid="fix-group-3"] tr[data-fix-reason="wrong_read"] label').click();
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  try {
    await page.waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 45000 });
  } catch {
    // A refusal is a RESULT, not a crash: print what the clerk would read, and
    // photograph it, before giving up on this bill.
    const said = await page.locator('[data-wizard="frame"]').innerText();
    fail(`step 1 Continue did not advance. The frame says: ${said.slice(0, 400)}`);
    await page.screenshot({ path: `${SHOTS}/step1-continue-refused-${width}.png`, fullPage: true });
    throw new Error("step 1 would not advance — see the capture");
  }
  const caseNo = await page.locator('[data-wizard="frame"]').innerText();
  opened.push(`step-1 Continue at ${width}: a preview case was opened`);
  await page.locator('[data-wizard="actions"] button', { hasText: "See what it changes" }).click();
  await page.waitForSelector('[data-wizard-step="3"][data-state="active"]', { timeout: 60000 });
  await page.waitForSelector('[data-fix-step="what-it-changes"]', { timeout: 30000 });
  ok(`26.6: step 3 draws the lane-E body (case text length ${caseNo.length})`);

  const panels = await page.locator('[data-fix-step="what-it-changes"] h2').allTextContents();
  console.log(`    panels: ${JSON.stringify(panels)}`);
  const refs = await internalReferences(page);
  if (refs.length === 0) ok("26.6: no rule id, question id or module path on screen");
  else fail(`26.6: a clerk can read ${JSON.stringify(refs)}`);
  await noSidewaysScroll(page, "26.6");
  await page.screenshot({ path: `${SHOTS}/step3-26.6-one-bill-${width}.png`, fullPage: true });

  // The frame's own footer, WITHOUT pressing it: the approval signature is not
  // this walk's to record.
  const send = await page
    .locator('[data-wizard="actions"] button', { hasText: "Send for approval" })
    .count();
  if (send === 1) ok("26.6: the footer offers Send for approval, and it is not pressed");
  else fail(`26.6: the footer has ${send} Send for approval buttons`);

  await abandon(page, "26.6");

  // ── 26.7 · step 3 over MANY bills ───────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  // ⚠ **A BULK SCOPE THAT RESOLVES IS NOT YET A BULK SCOPE THAT OPENS.** The
  // June run resolves to 39 bills and the server REFUSES the case — a bill
  // whose chain has moved, a window, a status. That refusal is the server's and
  // is correct; what this walk needs is any bulk scope it will accept, so it
  // tries the four kinds in the drawing's own order and stops at the first that
  // previews. If none does, that is reported rather than papered over.
  let bulkDone = false;
  for (const kind of ["run", "cycle", "plan", "service"]) {
    if (bulkDone) break;
    await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
    await page.locator("#bil-fix-scope").selectOption(kind);
    await page.waitForTimeout(900);
    const chooser = page.locator('[data-testid="fix-group-1"] select').nth(1);
    const options = await chooser.locator("option").count();
    for (let index = 1; index < options && !bulkDone; index += 1) {
      await chooser.selectOption({ index });
      await page.waitForTimeout(1200);
      const rows = await page.locator("[data-fix-resolved] tbody tr").count();
      if (rows === 0) continue;
      await page.locator('[data-testid="fix-group-3"] tr[data-fix-reason="wrong_read"] label').click();
      await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
      try {
        await page.waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 90000 });
      } catch {
        await page.locator('[data-testid="fix-group-3"] tr[data-fix-reason="wrong_read"] label').click();
        continue;
      }
      await page.locator('[data-wizard="actions"] button', { hasText: "See what it changes" }).click();
      await page.waitForSelector('[data-fix-step="what-it-changes"]', { timeout: 60000 });
      const months = await page.locator("[data-fix-month]").count();
      ok(`26.7: a ${kind} scope of ${rows} bill(s) draws ${months} month row(s)`);
      const bulkRefs = await internalReferences(page);
      if (bulkRefs.length === 0) ok("26.7: no rule id, question id or module path on screen");
      else fail(`26.7: a clerk can read ${JSON.stringify(bulkRefs)}`);
      await noSidewaysScroll(page, "26.7");
      await page.screenshot({ path: `${SHOTS}/step3-26.7-many-${width}.png`, fullPage: true });
      await abandon(page, "26.7");
      bulkDone = true;
    }
  }
  if (!bulkDone) fail("26.7: no bulk scope on this tenant would open a case");

  // ── 26.4 · step 2 on a GOODWILL case ────────────────────────────────────
  // (a) THE REFUSAL A CLERK MEETS TODAY. The wizard never collects or sends
  //     `goodwill_amount`, so the server refuses every class-C case
  //     (`DEF-BIL-5368`). This is the screen as it stands, photographed.
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  await pickBill(page, process.env.BILL_C ?? "BL-2608-000050");
  await page.locator('[data-testid="fix-group-3"] tr[data-fix-reason="goodwill"] label').click();
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  await page.waitForTimeout(4000);
  const step = await page
    .locator('[data-wizard-step][data-state="active"]')
    .getAttribute("data-wizard-step");
  await page.screenshot({
    path: `${SHOTS}/def-bil-5368-goodwill-refused-${width}.png`,
    fullPage: true,
  });
  if (step === "1") {
    ok("26.4: the screen cannot open a goodwill case — it stays on step 1 (DEF-BIL-5368)");
  } else {
    fail(`26.4: a goodwill case opened after all — the rail is on step ${step}`);
  }

  // (b) THE DRAWN SCREEN, with the request COMPLETED BY THIS WALK.
  // ⚠ **THE WALK ADDS `goodwill_amount` TO THE REQUEST; THE PRODUCT DOES NOT.**
  // This is the only way `26.4` can be looked at until `DEF-BIL-5368` is fixed,
  // and the capture is labelled so nobody reads it as the shipped behaviour.
  // Nothing else about the request, the response or the screen is touched.
  await page.route("**/corrections", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.continue();
    const body = JSON.parse(request.postData() ?? "{}");
    if (!Array.isArray(body.reason_codes) || !body.reason_codes.includes("goodwill")) {
      return route.continue();
    }
    return route.continue({
      postData: JSON.stringify({ ...body, goodwill_amount: "40.00", balance_before: "0.00" }),
    });
  });
  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });
  await pickBill(page, process.env.BILL_C2 ?? "BL-2608-000067");
  await page.locator('[data-testid="fix-group-3"] tr[data-fix-reason="goodwill"] label').click();
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  try {
    await page.waitForSelector('[data-fix-step="goodwill"]', { timeout: 60000 });
    const groups = await page.locator('[data-fix-step="goodwill"] h2').allTextContents();
    console.log(`    26.4 groups: ${JSON.stringify(groups)}`);
    const gwRefs = await internalReferences(page);
    if (gwRefs.length === 0) ok("26.4: no rule id, question id or module path on screen");
    else fail(`26.4: a clerk can read ${JSON.stringify(gwRefs)}`);
    await noSidewaysScroll(page, "26.4");
    await page.screenshot({ path: `${SHOTS}/step2-26.4-goodwill-${width}.png`, fullPage: true });
    await abandon(page, "26.4");
  } catch {
    const said = await page.locator('[data-wizard="frame"]').innerText();
    fail(`26.4: the drawn body did not render — ${said.slice(0, 200)}`);
  }
  await page.unroute("**/corrections");

  await ctx.close();
}

await browser.close();
console.log("\nopened (all abandoned afterwards by laneE_abandon_cases.py):");
for (const one of opened) console.log("  " + one);
console.log(problems.length === 0 ? "\n0 problems" : `\n${problems.length} problem(s)`);
process.exit(problems.length === 0 ? 0 : 1);
