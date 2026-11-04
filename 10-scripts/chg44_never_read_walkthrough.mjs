/**
 * chg44_never_read_walkthrough — changes row 44, "no multiplier", walked in Chromium at 1440.
 *
 *     BASE=http://127.0.0.1:<web> \
 *     E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/chg44_never_read_walkthrough.mjs
 *
 * World: `seed_demo` → `seed_j72_bulk_run --never-read` on PostgreSQL 16. Unit 116
 * (Rosa Delgado, AC-2026-00012) has a water meter W-72116 that has never been read,
 * so it has no multiplier. The walk starts a September run on J72-RIVERSIDE and:
 *
 *   1. finds AC-2026-00012 under Meter history › "Meter never read" — a DECISION
 *      opening on Hold — and NOT under "Pricing refused" (the block it used to be);
 *   2. answers "Bill with multiplier 1" for it, as a clerk;
 *   3. re-checks it from the account's panel, and reads that the answered decision
 *      stays on the account and the account now asks its next question, "No reading";
 *   4. reloads, and reads the answer still on the account's record.
 *
 * It READS the screen and fails loudly. Screenshots: 08-qa/screens/chg44-never-read-2026-10-01/.
 */
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const OUT = new URL("../08-qa/screens/chg44-never-read-2026-10-01/", import.meta.url).pathname;
const BASE = process.env.BASE ?? "http://127.0.0.1:8645";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "AC-2026-00012";
const CASE = "meter_has_no_multiplier";
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail}`);
}

async function shot(page, name) {
  const pane = page.locator("main.view").first();
  const path = `${OUT}1440-${name}.png`;
  if ((await pane.count()) > 0) {
    await pane.screenshot({ path }).catch(async () => page.screenshot({ path }));
  } else {
    await page.screenshot({ path });
  }
}

async function openTag(page, code) {
  const row = page.locator(`[data-tag=${code}]`).first();
  await row.waitFor({ timeout: 30000 });
  await row.click();
  await page.locator(`[data-tag-pane=${code}]`).waitFor({ timeout: 15000 });
  return page.locator(`[data-tag-pane=${code}]`);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
try {
  await page.goto(`${BASE}/${TENANT}/signin`);
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60000 });

  // ── Scope: September on J72-RIVERSIDE ────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/billing/run`);
  await page.locator("[data-screen=bulk-bill-run]").waitFor({ timeout: 30000 });
  await page.locator("#label").fill("September 2026 · never read");
  const cycle = page.locator("#cycle_id");
  const option = cycle.locator("option").filter({ hasText: /J72-RIVERSIDE/ });
  await option.first().waitFor({ state: "attached", timeout: 20000 });
  await cycle.selectOption({ value: (await option.first().getAttribute("value")) ?? "" });
  await page.locator("#period_start").fill("2026-09-01");
  await page.locator("#period_end").fill("2026-09-30");
  await page.locator("#bill_date").fill("2026-10-01");
  await page.locator("#due_days").fill("21");
  const template = page.locator("#template_id");
  await template.locator("option").nth(1).waitFor({ state: "attached", timeout: 20000 });
  await template.selectOption({ index: 1 });
  await page.waitForTimeout(1800);
  await page.getByRole("button", { name: "Start checking", exact: true }).click();
  await page.locator("[data-check-results]").waitFor({ timeout: 180000 });
  await shot(page, "01-check-results");

  // ── 1. its own tag, a decision opening on Hold ───────────────────────────
  const tagRow = page.locator(`[data-tag=${CASE}]`).first();
  const tagText = (await tagRow.innerText()).replace(/\s+/g, " ");
  check("tag listed under Meter history", /Meter never read/.test(tagText), tagText);
  const pane = await openTag(page, CASE);
  await pane.locator(`[data-row-account="${ACCOUNT}"]`).first().waitFor({ timeout: 30000 }).catch(() => {});
  const paneText = (await pane.innerText()).replace(/\s+/g, " ");
  check("the account is in the tag", paneText.includes(ACCOUNT), paneText.slice(0, 300));
  check("choices are Hold and Bill with multiplier 1",
    /Hold/.test(paneText) && /Bill with multiplier 1/.test(paneText), paneText.slice(0, 300));
  const preselected = await pane.locator("[data-apply-all]").getAttribute("data-apply-all").catch(() => null);
  check("the suggested answer is Hold", preselected === "hold", `data-apply-all=${preselected}`);
  await shot(page, "02-meter-never-read-tag");

  const refused = page.locator("[data-tag=ruled_path_refused]");
  if ((await refused.count()) > 0) {
    const refusedPane = await openTag(page, "ruled_path_refused");
    const text = await refusedPane.innerText();
    check("not under Pricing refused", !text.includes(ACCOUNT), "ruled_path_refused tag present");
  } else {
    check("not under Pricing refused", true, "no Pricing refused tag at all");
  }

  // ── 2. Bill with multiplier 1 ─────────────────────────────────────────────
  const again = await openTag(page, CASE);
  await again.locator("[data-tag-actions]").getByRole("radio", { name: "Bill with multiplier 1" })
    .or(again.locator("[data-tag-actions]").getByRole("button", { name: "Bill with multiplier 1" }))
    .first()
    .click();
  await page.waitForTimeout(2500);
  await shot(page, "03-bill-with-multiplier-1");

  // ── 3. Re-check it, from the account's own panel ─────────────────────────
  const paneNow = await openTag(page, CASE);
  await paneNow.locator(`[data-row-account="${ACCOUNT}"] [data-open-account]`).first().click();
  const panel = page.locator("[data-side-panel=fix-account], [data-panel=fix-account]").first();
  const recheckButton = page.locator("[data-recheck-account]").first();
  await recheckButton.waitFor({ timeout: 15000 });
  await shot(page, "03b-fix-account-panel");
  await recheckButton.click();
  await page.waitForTimeout(4000);
  void panel;
  await page.reload();
  await page.locator("[data-check-results]").waitFor({ timeout: 120000 });
  const api = `${BASE}/api/${TENANT}`;
  const runId = page.url().match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)?.[0];
  check("run id read off the address", Boolean(runId), page.url());
  const kept = await openTag(page, CASE);
  await kept.locator(`[data-row-account="${ACCOUNT}"]`).first().waitFor({ timeout: 30000 });
  const keptText = (await kept.innerText()).replace(/\s+/g, " ");
  check("Re-check keeps the answered decision on the account", keptText.includes(ACCOUNT), keptText.slice(0, 300));
  await shot(page, "04-after-recheck-answer-kept");
  const noReading = await openTag(page, "missing_read");
  await noReading.locator(`[data-row-account="${ACCOUNT}"]`).first().waitFor({ timeout: 30000 });
  const nrText = await noReading.innerText();
  check("the account now asks its next question: No reading", nrText.includes(ACCOUNT), nrText.slice(0, 200));
  await shot(page, "05-after-recheck-no-reading");

  // ── 4. the answer is on the record ────────────────────────────────────────
  const report = await page.evaluate(async ([api, runId]) => {
    const r = await fetch(`${api}/billing/runs/${runId}/check/report?q=00012`, { credentials: "include" });
    return { status: r.status, body: await r.json() };
  }, [api, runId]);
  const row = report.body?.accounts?.results?.find((r) => r.account_no === ACCOUNT);
  const answered = (row?.decisions ?? []).find((d) => d.case === CASE);
  check("the answer is recorded with who and when",
    answered?.choice === "bill_with_multiplier_1" && Boolean(answered?.decided_by) && Boolean(answered?.decided_at),
    JSON.stringify(answered ?? report.status));
} catch (error) {
  check("walk completed", false, String(error).split("\n")[0]);
  await shot(page, "99-failure").catch(() => {});
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed ? 1 : 0);
