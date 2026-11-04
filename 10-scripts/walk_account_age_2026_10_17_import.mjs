// Walk, part 2 — the accounts import's Opened column and its refusal
// (DEF-CUS-10180). Opens the import run the prep script loaded on the copy and
// the import start page, and screenshots both. Env: WEB, TENANT, OUT, RUN.
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8107";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-account-age-2026-10-17";
mkdirSync(OUT, { recursive: true });
const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
try {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.goto(`${WEB}/${T}/accounts?tab=imports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/12-imports-tab.png` });
  const link = page.getByText("legacy-accounts-2012.csv").first();
  if (await link.count()) {
    await link.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: `${OUT}/12b-import-run.png`, fullPage: true });
    const body = await page.evaluate(() => document.body.innerText);
    for (const line of body.split("\n")) {
      if (/future|Opened|A-FUTURE|A-2012-OLD|created|rejected/i.test(line)) console.log(`  ${line.trim()}`);
    }
  } else {
    console.log("  run not listed on the Imports tab");
  }
} finally {
  await browser.close();
}
