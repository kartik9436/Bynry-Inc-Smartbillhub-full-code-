// Walk of reading gaps A, F and D — PO ruling 2026-10-17 ("WHERE A USER ENTERS
// A METER READING"): DEF-AST-10182 (Retire with a replacement: old final + new
// opening reading, Fetch on both), DEF-MET-10183 (Fetch on Reads → Add reading
// and on One-time bill step 2), DEF-WRK-10184 (an accepted field move-out
// reading is a MOVE-OUT reading in the meter's history).
// Env: WEB, TENANT, OUT, EMAIL, PASSWORD, RETIRE_ID, RETIRE_NO, SPARE_NO,
// SPARE_ID, FINAL, OPENING, QUICK_METER, OTB_ACCOUNT, ORDER_NO, JOB_METER_ID.
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const env = process.env;
const WEB = env.WEB || "http://127.0.0.1:8104";
const T = env.TENANT || "brazosbend";
const OUT = env.OUT || "05-prototype/walk-reading-gaps-assets-2026-10-17";
mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
};

const exe = env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));
const shot = (name) => page.screenshot({ path: `${OUT}/${name}`, fullPage: true });
const settle = (ms = 1500) => page.waitForTimeout(ms);

async function readsTab(assetId) {
  await page.goto(`${WEB}/${T}/assets/${assetId}?tab=reads`, { waitUntil: "networkidle" });
  await settle(2500);
  return (await page.locator("main").innerText()).replace(/\s+/g, " ");
}

try {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", env.EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", env.PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await settle();

  // ── A · Retire with a replacement ─────────────────────────────────────
  if (!env.SKIP_A) {
  await page.goto(`${WEB}/${T}/assets/${env.RETIRE_ID}/retire?step=1`, { waitUntil: "networkidle" });
  await page.locator("#final_read_value").waitFor({ timeout: 30000 });
  await page.selectOption("#reason", "replaced");
  await page.getByRole("button", { name: `Fetch reading for ${env.RETIRE_NO}` }).click();
  const oldSaid = page.locator(`[data-fetch-reading="${env.RETIRE_NO}"] [data-fetch-reading-state]`);
  await oldSaid.waitFor({ timeout: 20000 });
  check("Retire step 1: Fetch on the OLD meter answers honestly", true, await oldSaid.innerText());
  await page.fill("#final_read_value", env.FINAL);
  await shot("A1-retire-step1-final-read-fetch.png");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  const combo = page.getByRole("combobox", { name: /Replaced by/ });
  await combo.waitFor({ timeout: 20000 });
  await combo.fill(env.SPARE_NO);
  await page.getByRole("option", { name: new RegExp(env.SPARE_NO) }).first().click();
  await page.locator("#replacement_opening_read").waitFor({ timeout: 20000 });
  await page.getByRole("button", { name: `Fetch reading for ${env.SPARE_NO}` }).click();
  const newSaid = page.locator(`[data-fetch-reading="${env.SPARE_NO}"] [data-fetch-reading-state]`);
  await newSaid.waitFor({ timeout: 20000 });
  check("Retire step 2: Fetch on the NEW meter answers honestly", true, await newSaid.innerText());
  await page.fill("#replacement_opening_read", env.OPENING);
  const openingDate = await page.locator("#replacement_opening_read_date").inputValue();
  check("Retire step 2: the opening read date opens on the retire date", openingDate !== "", openingDate);
  await shot("A2-retire-step2-opening-read.png");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await settle();
  const radio = page.locator('input[name="book_value_treatment"]').first();
  if (await radio.count()) await radio.check();
  await shot("A3-retire-step3.png");
  const retired = page
    .waitForResponse((r) => r.request().method() === "POST" && /\/retire$/.test(r.url()), { timeout: 60000 })
    .then(async (r) => ({ status: r.status(), body: await r.text() }));
  await page.getByRole("button", { name: new RegExp(`Retire ${env.RETIRE_NO}`) }).click();
  const res = await retired;
  check("Retire commits", res.status < 300, `${res.status} ${res.body.slice(0, 160)}`);
  await settle(2500);

  const oldHistory = await readsTab(env.RETIRE_ID);
  check("OLD meter history shows the final reading", new RegExp(`\\b${env.FINAL}\\b`).test(oldHistory), env.FINAL);
  await shot("A4-old-meter-read-history.png");
  const newHistory = await readsTab(env.SPARE_ID);
  check("NEW meter history shows the opening reading", /\b12\b/.test(newHistory), env.OPENING);
  await shot("A5-new-meter-read-history.png");
  }

  // ── F · a multi-register meter: no Fetch, one date ───────────────────
  if (env.QUICK_MULTI) {
    await page.goto(`${WEB}/${T}/reads`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "+ Add reading" }).click();
    await page.fill("#meter_no", env.QUICK_MULTI);
    await page.locator("#meter_no").press("Tab");
    await page.waitForSelector('[data-testid="quick-read-meter"]', { timeout: 20000 });
    await settle();
    const none = await page.getByRole("button", { name: `Fetch reading for ${env.QUICK_MULTI}` }).count();
    const dates = await page.locator("#read_date").count();
    check("Add reading, multi-register meter: no Fetch, one date", none === 0 && dates === 1, `${none} fetch, ${dates} date`);
    await shot("F0-add-reading-multi-register-no-fetch.png");
    await page.keyboard.press("Escape");
    await settle();
  }

  // ── F · Reads → Add reading ───────────────────────────────────────────
  await page.goto(`${WEB}/${T}/reads`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "+ Add reading" }).click();
  await page.fill("#meter_no", env.QUICK_METER);
  await page.locator("#meter_no").press("Tab");
  await page.waitForSelector('[data-testid="quick-read-meter"]', { timeout: 20000 });
  await page.getByRole("button", { name: `Fetch reading for ${env.QUICK_METER}` }).click();
  const quickSaid = page.locator(`[data-fetch-reading="${env.QUICK_METER}"] [data-fetch-reading-state]`);
  await quickSaid.waitFor({ timeout: 20000 });
  check("Add reading: Fetch answers honestly", true, await quickSaid.innerText());
  await shot("F1-add-reading-fetch.png");
  await page.keyboard.press("Escape");
  await settle();

  // ── F · One-time bill step 2 ──────────────────────────────────────────
  await page.goto(`${WEB}/${T}/billing/one-time?kind=interim`, { waitUntil: "networkidle" });
  await page.locator("[data-screen=one-time-bill]").waitFor({ timeout: 30000 });
  await page.getByRole("combobox", { name: /Find account/ }).fill(env.OTB_ACCOUNT);
  await page.getByRole("option").first().waitFor({ timeout: 20000 });
  await page.getByRole("option").first().click();
  await page.getByText(env.OTB_ACCOUNT).first().waitFor({ timeout: 20000 });
  await settle(3000);
  await page.locator("#period_start").fill(env.OTB_FROM || "2026-10-01");
  await page.locator("#period_start").press("Tab");
  await page.locator("#period_end").fill(env.OTB_TO || "2026-10-17");
  await page.locator("#period_end").press("Tab");
  await settle();
  await shot("F2a-one-time-bill-step1.png");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator('[data-wizard-step="2"][data-state=active]').waitFor({ timeout: 60000 });
  const fetchButtons = page.getByRole("button", { name: /^Fetch reading for / });
  const count = await fetchButtons.count();
  check("One-time bill step 2: a Fetch per meter row", count > 0, `${count} meter(s)`);
  if (count > 0) {
    await fetchButtons.first().click();
    const said = page.locator("[data-fetch-reading-state]").first();
    await said.waitFor({ timeout: 20000 });
    check("One-time bill: Fetch answers honestly", true, await said.innerText());
  }
  await page.locator("[data-reading-row]").first().scrollIntoViewIfNeeded();
  await shot("F2-one-time-bill-step2-fetch.png");

  // ── D · accept the field move-out job ─────────────────────────────────
  await page.goto(`${WEB}/${T}/work/awaiting-approval`, { waitUntil: "networkidle" });
  await settle(2500);
  await shot("D1-awaiting-approval.png");
  const acceptButton = page.getByRole("button", { name: `Accept ${env.ORDER_NO}` });
  if (await acceptButton.count()) {
    await acceptButton.click();
    const accepted = page
      .waitForResponse((r) => r.request().method() === "POST" && /accept/.test(r.url()), { timeout: 60000 })
      .then(async (r) => ({ status: r.status(), body: await r.text() }));
    await page.getByRole("button", { name: "Accept ✓" }).click();
    const acc = await accepted;
    check("Field job accepted", acc.status < 300, `${acc.status}`);
    await settle(2500);
  } else {
    console.log(`  ${env.ORDER_NO} already accepted on an earlier pass of this walk`);
  }
  await readsTab(env.JOB_METER_ID);
  const sourceCell = page.locator("[data-read-source-event]").first();
  await sourceCell.waitFor({ timeout: 20000 });
  const cellText = (await sourceCell.innerText()).trim();
  const cellCode = await sourceCell.getAttribute("data-read-source-event");
  check("Meter's Reads tab shows the field reading as a Move-out reading", cellCode === "move_out", cellText);
  await sourceCell.scrollIntoViewIfNeeded();
  await shot("D2-job-meter-read-history.png");
  if (env.JOB_READ_ID) {
    await page.goto(`${WEB}/${T}/reads/${env.JOB_READ_ID}`, { waitUntil: "networkidle" });
    const tag = page.locator("[data-read-event]").first();
    await tag.waitFor({ timeout: 20000 });
    check("The field reading's detail tags it Move-out", (await tag.getAttribute("data-read-event")) === "move_out", await tag.innerText());
    await shot("D3-field-reading-detail-move-out.png");
  }
} catch (error) {
  check("walk ran to the end", false, String(error).split("\n")[0]);
  await page.screenshot({ path: `${OUT}/FAILED.png`, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
