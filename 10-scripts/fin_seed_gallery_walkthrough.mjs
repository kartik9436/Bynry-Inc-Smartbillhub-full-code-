// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6640 — the demo fixture's calendar is a set of fixed 2026
//          dates, so every period-scoped Finance screen reads $0.00 once the
//          real clock passes August. This walk is what PROVES the seeder fixed
//          it: it photographs all twelve Finance surfaces and MEASURES what is
//          on each one, so a screen that is still empty says so with a number
//          beside it rather than being quietly photographed.
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//          running app yourself) · hard-won law 7 (a check's output must
//          distinguish pass from fail TO A READER, and a check reporting zero
//          over a scope it excludes is indistinguishable from an empty one —
//          hence the per-screen row count, money-cell count and non-zero
//          count, and hence the FULL-PAGE fix below).
// ───────────────────────────────────────────────────────
/**
 * Photograph every Finance screen, at 1440 and again at 1280, and print what
 * is on each one.
 *
 * ⚠ **`fullPage: true` DOES NOT WORK ON THIS PRODUCT, AND SILENTLY PRODUCES A
 * VIEWPORT SHOT.** The shell scrolls an inner `main.view` rather than the
 * document — measured on Finance → Revenue & AR: `document.scrollHeight` is
 * 900 and `main.view.scrollHeight` is 2,166. So Playwright's full-page capture
 * is told the page is 900px tall, believes it, and returns a crop with no
 * error and no warning. Every shot comes out exactly the viewport height,
 * which reads as a deliberate framing rather than as a truncation.
 * **This walk therefore measures the scroller and GROWS THE VIEWPORT to it**
 * before each capture, and prints each shot's height so a reader can see the
 * difference between a short screen and a cropped one.
 *
 * RUN:
 *   BASE=http://127.0.0.1:<your web port> SHOTS=<dir> \
 *     node 10-scripts/fin_seed_gallery_walkthrough.mjs
 *
 * ⚠ Against a database nobody else is seeding — `10-scripts/proof-db.sh clone
 * <yours>`, then `10-scripts/seed_finance_current_period.py --database <it>` —
 * and on your own ports. Kill by the PID you recorded, never `pkill -f`.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import fs from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:8956";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/fin-gallery";
fs.mkdirSync(SHOTS, { recursive: true });

/** The twelve Finance surfaces, in the order the tab strip draws them. */
const SCREENS = [
  ["gl-journal", "/finance?view=journal", "General ledger · Journal"],
  ["gl-balance", "/finance?view=balance", "General ledger · Trial balance"],
  ["gl-chart", "/finance?view=chart", "General ledger · Chart of accounts"],
  ["gl-accruals", "/finance?view=accruals", "General ledger · Accruals"],
  ["revenue-services", "/finance/revenue?view=services", "Revenue & AR · Services"],
  ["revenue-aging", "/finance/revenue?view=aging", "Revenue & AR · Aging"],
  ["revenue-tieout", "/finance/revenue?view=tieout", "Revenue & AR · Tie-out"],
  ["revenue-writeoffs", "/finance/revenue?view=writeoffs", "Revenue & AR · Write-offs"],
  ["revenue-refunds", "/finance/revenue?view=refunds", "Revenue & AR · Refunds"],
  ["deposits", "/finance/deposits", "Deposits & Bank"],
  ["taxes", "/finance/taxes", "Taxes & Remittance"],
  ["costs", "/finance/cost-of-service", "Costs"],
  ["export", "/finance/export", "Close & export"],
];

const lines = [];
const say = (m) => { console.log(m); lines.push(m); };

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => say(`  !! page error: ${e.message}`));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
say("signed in");

/** The version stamp the sidebar prints, which is what a README must quote. */
const version = await page.evaluate(() => {
  const el = [...document.querySelectorAll("*")].find(
    (n) => n.children.length === 0 && /^v\d+\.\d+\.\d+$/.test((n.textContent || "").trim())
  );
  return el ? el.textContent.trim() : "(none on screen)";
});
say(`VERSION ON SCREEN: ${version}`);

/** The period line the Finance head prints — the whole point of DEF-LED-6640. */
await page.goto(`${BASE}/${TENANT}/finance`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
const periodLine = await page.evaluate(() => {
  const m = document.body.innerText.match(/FY\d{4}[^\n]*/);
  return m ? m[0] : "(no period line)";
});
say(`PERIOD ON SCREEN : ${periodLine}`);

async function capture(name, url, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(`${BASE}/${TENANT}${url}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);
  // Grow the viewport to the SHELL's scroller, not the document's.
  const needed = await page.evaluate(() => {
    const main = document.querySelector("main.view") || document.body;
    const chrome = window.innerHeight - main.clientHeight;
    return Math.min(9000, Math.ceil(main.scrollHeight + chrome + 24));
  });
  if (needed > 900) {
    await page.setViewportSize({ width, height: needed });
    await page.waitForTimeout(900);
  }
  const suffix = width === 1440 ? "" : `-${width}`;
  const file = `${SHOTS}/${name}${suffix}.png`;
  await page.screenshot({ path: file, fullPage: true });
  return needed;
}

const table = [];
for (const [name, url, label] of SCREENS) {
  try {
    const height = await capture(name, url, 1440);
    const measured = await page.evaluate(() => {
      const text = document.body.innerText;
      const money = text.match(/\$[\d,]+\.\d\d/g) || [];
      return {
        rows: document.querySelectorAll("table tbody tr").length,
        money: money.length,
        nonZero: money.filter((m) => m !== "$0.00").length,
        absences: (text.match(/^.*(?:No |Not available|nothing|cannot).*$/gim) || [])
          .map((s) => s.trim()).filter(Boolean).slice(0, 3),
      };
    });
    say(
      `\n── ${label}\n   ${url}\n   shot 1440 × ${height}px · table rows ${measured.rows}` +
      ` · money cells ${measured.money} (non-zero ${measured.nonZero})`
    );
    if (measured.absences.length) {
      say(`   states an absence: ${measured.absences.join(" | ")}`);
    }
    table.push({ name, label, url, height, ...measured });
    await capture(name, url, 1280);
  } catch (e) {
    say(`\n── ${label} FAILED: ${e.message}`);
  }
}

say("\n── SUMMARY ────────────────────────────────────────────────");
for (const row of table) {
  const verdict = row.rows > 0 || row.nonZero > 0 ? "has data" : "EMPTY";
  say(`   ${row.label.padEnd(36)} rows ${String(row.rows).padStart(3)} · non-zero money ${String(row.nonZero).padStart(3)} · ${verdict}`);
}

fs.writeFileSync(`${SHOTS}/walk-notes.txt`, lines.join("\n") + "\n");
say(`\nnotes written to ${SHOTS}/walk-notes.txt`);
await browser.close();
