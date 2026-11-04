#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 lane F — Fix a bill STEP FOUR (`26.8 Generate and
//           send`) walked in a browser at both staff widths
// Rules:    hard-won law 6 (diff the running app against the drawing — no gate
//           reads rendered output) · B14 rules 31, 32, 33, 41, 42 · BR-BIL-014
//           (nothing money-bearing before approval) · BR-BIL-047 (abandoning is
//           an explicit, reasoned act)
// ───────────────────────────────────────────────────────
/**
 * WALK STEP 4, AT 1440 AND 1280, AND CAPTURE IT.
 *
 *   BASE=http://127.0.0.1:8084 SHOTS=<dir> node 10-scripts/cr101_fix_a_bill_step4_walkthrough.mjs
 *   …                                     node …_step4_walkthrough.mjs --approved
 *
 * ⚠ **IT NEVER PRESSES THE BUTTON THAT WRITES.** The default pass opens ONE
 * preview case on a bill nobody else is holding, walks it to step 4 through
 * step 3's approval signature — which writes a signature and no money
 * (BR-BIL-014) — reads the screen, captures it, and then ABANDONS the case with
 * a reason so the bill is free for a sibling lane. `Create the documents & post`
 * is counted and never clicked.
 *
 * `--approved` is the second half: it opens the case a sibling left APPROVED
 * and NOT EXECUTED from the *Corrections so far* table, and records what the
 * product actually does with it. That pass ends in an abandon too.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8084";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "SCRATCH/fix-a-bill-step4";
mkdirSync(SHOTS, { recursive: true });

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const INTERNAL = /\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/;

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

/** Read the whole step-4 body and rule it against what p144/p145 draw. */
async function readStep4(page, label) {
  const body = page.locator('[data-fix-step="generate-and-send"]');
  const text = await body.innerText();
  note(`\n── ${label} · step 4 as a clerk reads it ──────────────────────────`);
  note(text.replace(/\n{2,}/g, "\n"));
  note("──────────────────────────────────────────────────────────────────\n");

  const headings = await body.locator('[data-testid^="fix-send-group-"] h2').allInnerTexts();
  if (headings.length === 3) ok(`three groups — ${JSON.stringify(headings.map((h) => h.replace(/\s+/g, " ")))}`);
  else fail(`step 4 draws ${headings.length} groups`);

  const band = await body.locator("[data-fix-send-band]").innerText().catch(() => "");
  if (band.trim() !== "") ok(`the band answers — "${band.replace(/\s+/g, " ")}"`);
  else fail("step 4 draws no answer band");

  const rows = await body.locator("[data-fix-document]").evaluateAll((els) =>
    els.map((el) => ({
      kind: el.getAttribute("data-fix-document"),
      cells: [...el.querySelectorAll("th,td")].map((c) => c.textContent.trim()),
    })),
  );
  note(`  group 1 rows: ${JSON.stringify(rows)}`);
  if (rows.length >= 2) ok(`group 1 counts ${rows.length} kinds`);
  else fail("group 1 draws fewer than two rows");
  if (rows.some((r) => /\d\.\d{4}\b/.test(r.cells.join(" ")))) fail("a four-decimal figure reached group 1");

  const channels = await body.locator("[data-fix-channel]").evaluateAll((els) =>
    els.map((el) => [...el.querySelectorAll("th,td")].map((c) => c.textContent.trim())),
  );
  note(`  group 2 rows: ${JSON.stringify(channels)}`);

  const gate = await body.locator("[data-fix-approval-state]").innerText().catch(() => "");
  const undo = await body.locator("[data-fix-no-undo]").innerText().catch(() => "");
  if (gate.trim() !== "") ok(`the gate says — "${gate.trim()}"`);
  else fail("the gate says nothing about approval");
  if (undo.trim() !== "") ok(`the no-undo band says — "${undo.trim()}"`);
  else fail("step 4 draws no no-undo band");

  if (UUID.test(text)) fail("a database id is visible on step 4");
  else ok("no database id on step 4");
  const hit = text.match(INTERNAL);
  if (hit) fail(`an internal id is visible on step 4 — ${hit[0]}`);
  else ok("no rule id, question id or defect id on step 4");
  if (await body.locator("button").count()) fail("the step body draws a button of its own");
  else ok("the step body draws no button — the one that writes is the frame's");
  return { text, rows, channels, gate, undo, band };
}

async function readCommitButton(page) {
  const actions = page.locator('[data-wizard="actions"]');
  const labels = await actions.locator("button").allInnerTexts();
  const commit = actions.locator("button").last();
  const cls = await commit.getAttribute("class");
  const disabled = await commit.isDisabled();
  note(`  footer buttons: ${JSON.stringify(labels.map((l) => l.replace(/\s+/g, " ")))}`);
  note(`  commit tier: ${/danger/.test(cls ?? "") ? "danger" : `NOT danger — ${cls}`}`);
  note(`  commit disabled: ${disabled}`);
  return { labels, danger: /danger/.test(cls ?? ""), disabled };
}

/** BR-BIL-047 — leave the bill free for a sibling lane. Never execute. */
async function abandon(page, label) {
  const close = page.locator('[data-wizard="actions"] button', { hasText: "Close without correcting" });
  if ((await close.count()) === 0) {
    fail(`${label}: no abandon control is reachable`);
    return;
  }
  if (await close.first().isDisabled()) {
    fail(`${label}: the abandon control is disabled`);
    return;
  }
  await close.first().click();
  await page.waitForTimeout(2500);
  ok(`${label}: the case was ABANDONED with a reason — nothing money-bearing written`);
}

const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
const TALL = Number(process.env.TALL ?? "2400");
const APPROVED_ONLY = process.argv.includes("--approved");

for (const width of APPROVED_ONLY ? [1440] : WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width, height: TALL } });
  const page = await ctx.newPage();
  page.on("pageerror", (error) => fail(`page error at ${width}: ${error.message}`));
  await signIn(page);
  note(`\n=== signed in at ${width} ===`);

  await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="fix-group-1"]', { timeout: 30000 });

  if (APPROVED_ONLY) {
    // ── the case a sibling left APPROVED and NOT EXECUTED ─────────────────
    const cases = await api(page, "/corrections?per=20");
    const open = (cases.body?.results ?? []).find((row) => row.status === "approved");
    if (open === undefined) {
      fail("no approved-and-not-executed case on the tenant");
    } else {
      note(`the approved case: bills=${open.bills} class=${open.correction_class} scope=${open.scope_kind}`);
      // ⚠ Every row's case cell reads the same words (no case number is minted
      // until execution), so the APPROVED row is found by its STATUS cell — not
      // by taking the first link, which on 2026-09-15 opened a `done` case and
      // reported the abandon control disabled for a reason that was the
      // script's own (law 7's *looking at the wrong thing*).
      const rows = page.locator("table").last().locator("tbody tr");
      const statuses = await rows.evaluateAll((els) =>
        els.map((el) => el.querySelector("td:last-child")?.textContent?.trim() ?? ""),
      );
      note(`  *Corrections so far* statuses: ${JSON.stringify(statuses)}`);
      const index = statuses.findIndex((s) => !/^done$/i.test(s));
      if (index === -1) {
        fail("no unfinished case row in *Corrections so far*");
        await ctx.close();
        continue;
      }
      const link = rows.nth(index).locator("a, button");
      const count = await link.count();
      note(`  opening the row whose status reads "${statuses[index]}"`);
      if (count > 0) {
        await link.first().click();
        await page.waitForTimeout(2500);
        const railState = await page
          .locator("[data-wizard-step]")
          .evaluateAll((els) => els.map((el) => el.getAttribute("data-state")));
        note(`  after opening the case, the rail reads ${JSON.stringify(railState)}`);
        const step4 = await page.locator('[data-fix-step="generate-and-send"]').count();
        if (step4 === 1) {
          await readStep4(page, "the approved case");
          await readCommitButton(page);
        } else {
          fail(
            "opening a case from *Corrections so far* leaves the rail on step 1 — " +
              "the steps that show the case cannot be reached from the list",
          );
          // Say what the clerk DOES get, so the finding is specific.
          const foot = await page.locator("table").last().innerText();
          note(`  the list row now reads: ${foot.split("\n").slice(0, 4).join(" | ")}`);
        }
        await page.screenshot({ path: `${SHOTS}/approved-case-opened-${width}.png`, fullPage: true });
        await abandon(page, "the approved case");
        await page.screenshot({ path: `${SHOTS}/approved-case-abandoned-${width}.png`, fullPage: true });
      }
    }
    await ctx.close();
    continue;
  }

  // ── a fresh case of this lane's own ──────────────────────────────────────
  await page.locator("#bil-fix-scope").selectOption("single");
  await page.waitForSelector("[data-bil-finder]", { timeout: 15000 });
  const issued = await api(page, "/invoices?per=25&f.status=issued&sort=issue_date&dir=desc");
  // ⚠ **THE HELD SET COMES OFF EACH OPEN CASE'S BILLS, NOT OFF ITS `scope`.**
  // The first draft read `Object.values(row.scope)`, which holds the invoice id
  // only for a `single` case — a `date_range` or `run` case's scope is dates and
  // ids of other things entirely. On 2026-09-15 a sibling lane held nine bills
  // inside bulk cases, this walk picked one of them, and `BR-BIL-048` refused
  // the second case on that bill exactly as it should: the walk was wrong, not
  // the product. One extra request per open case buys the right answer.
  const openCases = ((await api(page, "/corrections?per=50")).body?.results ?? []).filter(
    (row) => row.status !== "done",
  );
  const held = new Set();
  for (const row of openCases) {
    const detail = await api(page, `/corrections/${row.id}`);
    for (const bill of detail.body?.bills_detail ?? []) held.add(bill.invoice_id);
  }
  note(`${openCases.length} open case(s) hold ${held.size} bill(s) — those are skipped`);
  const subject = (issued.body?.results ?? []).find(
    (row) => row.invoice_no && !held.has(row.id) && row.invoice_no !== "BL-2608-000042",
  );
  if (subject === undefined) {
    fail("no free issued bill to open a case on");
    await ctx.close();
    continue;
  }
  note(`subject bill: ${subject.invoice_no} (${subject.total} ${subject.currency ?? ""})`);
  await page.locator("[data-bil-finder] input[type=search]").first().fill(subject.invoice_no);
  await page.waitForTimeout(1800);
  await page.locator("[data-bil-finder] tbody tr").first().locator("button").first().click();
  await page.locator('label[for="bil-fix-reason-wrong_read"]').click();
  await page.waitForTimeout(400);

  // Step 1 → 2: opens a PREVIEW case. No money (BR-BIL-014).
  await page.locator('[data-wizard="actions"] button', { hasText: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="2"][data-state="active"]', { timeout: 60000 });
  // Step 2 → 3: a page turn.
  await page.locator('[data-wizard="actions"] button', { hasText: "See what it changes" }).click();
  await page.waitForSelector('[data-wizard-step="3"][data-state="active"]', { timeout: 30000 });
  // Step 3 → 4: this records the APPROVAL SIGNATURE, and writes no money.
  await page.locator('[data-wizard="actions"] button', { hasText: "Send for approval" }).click();
  await page.waitForSelector('[data-wizard-step="4"][data-state="active"]', { timeout: 60000 });
  await page.waitForTimeout(1500);

  await readStep4(page, `${width} · a fresh approved case`);
  const commit = await readCommitButton(page);
  if (commit.danger) ok("the one button that writes is the danger tier (B14 rule 6)");
  else fail("the commit button is not the danger tier");
  if (commit.labels.some((l) => /Close without correcting/.test(l))) {
    ok("abandon-with-a-reason stays reachable from step 4 (BR-BIL-047)");
  } else fail("no abandon control on step 4");

  await page.screenshot({ path: `${SHOTS}/step4-${width}.png`, fullPage: true });
  await page.locator('[data-wizard="frame"]').screenshot({ path: `${SHOTS}/step4-frame-${width}.png` });
  await noSidewaysScroll(page, `step 4 at ${width}`);

  await abandon(page, `${width} · the fresh case`);
  await page.screenshot({ path: `${SHOTS}/step4-after-abandon-${width}.png`, fullPage: true });
  await ctx.close();
}

await browser.close();
console.log(`\n${problems.length} problem(s)`);
for (const p of problems) console.log(" - " + p);
process.exit(problems.length === 0 ? 0 : 1);
