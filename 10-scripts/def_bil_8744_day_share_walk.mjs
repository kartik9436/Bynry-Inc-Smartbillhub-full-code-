// DEF-BIL-8744 — the J75 world's prorated per-kW lines, read and screenshotted,
// BEFORE and AFTER the day fraction was printed.
//
// A part-month solar or battery line is cut down by days (DEF-BIL-8743,
// 2.428.1) while its kW and rate stay whole, so it printed
// "6 kW · $14.00 · $53.20". After the fix it reads
// "6 kW · $14.00 · 19/30 days · $53.20" — on the one-time bill's Review step,
// the sent bill's Charges tab and the printed document.
//
//   MODE=sent   — Six Rivers' issued bills (DB a copy of `sbh_six`):
//                 BILLS=<id3>,<id4>,<id5> → each bill's Charges tab.
//   MODE=review — the same copy: Unit 7's final bill (1–18 Oct) driven to
//                 Review; with SEND=1 sent, then its Charges tab and the printed
//                 document it kept at issue.
//   PHASE=before|after names the screenshots; EXPECT_DAYS=1 asserts the fraction
//   is printed, EXPECT_DAYS=0 asserts it is not (the before state).
//
//   E2E_CHROMIUM_EXECUTABLE=… BASE=http://127.0.0.1:<web> MODE=sent PHASE=after \
//   EXPECT_DAYS=1 BILLS=… node 10-scripts/def_bil_8744_day_share_walk.mjs
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url).pathname);
const { chromium } = require("playwright");

const OUT = new URL("../08-qa/screens/six-service-onetime-2026-10-01/", import.meta.url).pathname;
const BASE = process.env.BASE ?? "http://127.0.0.1:8844";
const TENANT = process.env.TENANT ?? "sixrivers";
const EMAIL = process.env.EMAIL ?? "priya@sixriversutility.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const MODE = process.env.MODE ?? "sent";
const PHASE = process.env.PHASE ?? "after";
const EXPECT_DAYS = process.env.EXPECT_DAYS !== "0";
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail ?? ""}`);
}

/** The app scrolls inside `main.view`; release it so a full-page capture
 *  holds the whole bill (`07-frontend/e2e/support/app.ts` expandInnerScroller). */
async function shot(page, name) {
  await page.evaluate(() => {
    const main = document.querySelector("main.view");
    for (let el = main; el !== null; el = el.parentElement) {
      el.style.setProperty("height", "auto", "important");
      el.style.setProperty("max-height", "none", "important");
      el.style.setProperty("overflow", "visible", "important");
    }
  });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}1440-def-bil-8744-${PHASE}-${name}.png`, fullPage: true });
}

/** Every row whose text names kW, flattened. */
async function kwRows(page, selector) {
  const rows = await page.locator(selector).allInnerTexts();
  if (process.env.DEBUG_ROWS) console.log(rows.map((t) => t.replace(/\s+/g, " ").trim()));
  return rows.map((t) => t.replace(/\s+/g, " ").trim()).filter((t) => /\bkW\b/.test(t) && /\$/.test(t));
}

function expectDays(name, rows, days) {
  const usage = rows.filter((r) => !/base charge|Base · per/i.test(r));
  const withDays = usage.filter((r) => r.includes(days));
  check(
    `${name}: ${EXPECT_DAYS ? "every" : "no"} prorated kW line prints ${days}`,
    EXPECT_DAYS ? usage.length > 0 && withDays.length === usage.length : withDays.length === 0,
    JSON.stringify(usage),
  );
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`);
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60000 });
}

async function toReview(page, { kind, name, unit, start, end, meter, value }) {
  await page.goto(`${BASE}/${TENANT}/billing/one-time?kind=${kind}`);
  await page.locator("[data-screen=one-time-bill]").waitFor({ timeout: 30000 });
  const combo = page.getByRole("combobox", { name: /Find account/ });
  await combo.fill(name);
  await page.getByRole("option").first().waitFor({ timeout: 20000 });
  await page.getByRole("option").filter({ hasText: new RegExp(`Unit ${unit}(?:Active|Closed|Pending|\\s|,|$)`) }).first().click();
  await page.locator("[data-facts=otb-account] [data-fact=plan]").filter({ hasNotText: "—" }).waitFor({ timeout: 15000 });
  if (start) await page.locator("#period_start").fill(start);
  else await page.waitForFunction(() => document.querySelector("#period_start")?.value, null, { timeout: 15000 });
  await page.locator("#period_end").fill(end);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator('[data-wizard-step="2"][data-state=active]').waitFor({ timeout: 45000 });
  await page.locator(`[data-reading-row='${meter}'] input[id^='reading-'][id*='|current|']`).first().fill(value);
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator('[data-wizard-step="3"][data-state=active]').waitFor({ timeout: 60000 });
  await page.locator("[data-otb-bill]").waitFor({ timeout: 30000 });
  await page.waitForTimeout(600);
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
try {
  await signIn(page);
  if (MODE === "sent") {
    const bills = (process.env.BILLS ?? "").split(",").filter(Boolean);
    const days = ["19/30 days", "18/30 days", "18/30 days"];
    for (const [i, id] of bills.entries()) {
      const n = i + 3;
      await page.goto(`${BASE}/${TENANT}/billing/bills/${id}?tab=lines`);
      await page.locator("tr[data-bil=bill-line]").first().waitFor({ timeout: 30000 });
      await page.waitForTimeout(1200);
      expectDays(`case ${n} Charges tab`, await kwRows(page, "tr[data-bil=bill-line]"), days[i]);
      await shot(page, `case${n}-charges`);
      // No document check here: a sent bill's printed copy is KEPT at issue
      // (BR-BIL-030) and these three were issued before the fix, so their
      // copies rightly stay as printed. The document is proved on a bill sent
      // AFTER it — MODE=review SEND=1.
    }
  } else if (MODE === "doc") {
    // Re-open a bill sent by MODE=review SEND=1 (INVOICE=<id>).
    await page.goto(`${BASE}/${TENANT}/billing/bills/${process.env.INVOICE}/document`);
    await page.waitForTimeout(6000);
    const doc = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    const kw = doc.match(/solar usage.{0,80}?[0-9]+\.[0-9]{2} USD/)?.[0] ?? "";
    check("printed document shows the solar kW line", kw !== "", kw);
    check(`printed document ${EXPECT_DAYS ? "says" : "does not say"} 18/31 days`, kw !== "" && kw.includes("18/31 days") === EXPECT_DAYS, kw);
  } else {
    // Units 3–5 already carry their sent first and final bills on `sbh_six`, so
    // the Review step is walked on Unit 7 (Gita Rao: SOL-P2 + SOL-P4 = 6 kW,
    // BAT-10), finalled 1–18 October: 6 kW × $14.00 × 18/31 = $48.77.
    await toReview(page, { kind: "final", name: "Rao", unit: "7", start: "2026-10-01", end: "2026-10-18", meter: "W-2007", value: "635.0" });
    expectDays("Unit 7 final Review", await kwRows(page, "[data-otb-bill] tr[data-bill-line]"), "18/31 days");
    await shot(page, "unit7-final-review");
    if (process.env.SEND === "1") {
      // Send it (J75's five confirmations), then open the document the send
      // KEPT — rendered at issue from the stored lines, so it carries the share.
      await page.getByRole("button", { name: "Continue", exact: true }).click();
      await page.locator('[data-wizard-step="4"][data-state=active]').waitFor({ timeout: 60000 });
      for (const id of ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"]) {
        const box = page.locator(`#otb-confirm-${id}`);
        if ((await box.count()) > 0) await box.check({ force: true });
      }
      const [response] = await Promise.all([
        page.waitForResponse((r) => r.request().method() === "POST" && /\/billing\/one-time\/[^/]+\/send$/.test(r.url()), { timeout: 90000 }),
        page.getByRole("button", { name: /^Send .* bill$/ }).click(),
      ]);
      const sent = await response.json();
      check("Unit 7 final bill sent", response.status() < 300, `${sent.invoice_no} ${sent.total}`);
      await page.goto(`${BASE}/${TENANT}/billing/bills/${sent.invoice_id}?tab=lines`);
      await page.locator("tr[data-bil=bill-line]").first().waitFor({ timeout: 30000 });
      await page.waitForTimeout(1200);
      expectDays("Unit 7 sent Charges tab", await kwRows(page, "tr[data-bil=bill-line]"), "18/31 days");
      await shot(page, "unit7-final-charges");
      await page.goto(`${BASE}/${TENANT}/billing/bills/${sent.invoice_id}/document`);
      await page.waitForTimeout(6000);
      const doc = (await page.locator("main").innerText()).replace(/\s+/g, " ");
      const kw = doc.match(/solar usage.{0,80}?[0-9]+\.[0-9]{2} USD/)?.[0] ?? "";
      check("Unit 7 printed document shows the solar kW line", kw !== "", kw);
      check(
        `Unit 7 printed document ${EXPECT_DAYS ? "says" : "does not say"} 18/31 days`,
        kw !== "" && kw.includes("18/31 days") === EXPECT_DAYS,
        kw,
      );
      await shot(page, "unit7-final-document");
    }
  }
} catch (error) {
  check("walk completed", false, String(error).split("\n")[0]);
  if (process.env.FAIL_SHOT) await page.screenshot({ path: process.env.FAIL_SHOT, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed} of ${results.length} PASS`);
process.exit(failed ? 1 : 0);
