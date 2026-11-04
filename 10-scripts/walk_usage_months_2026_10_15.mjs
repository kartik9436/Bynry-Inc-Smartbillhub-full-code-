// Walk of the Usage tab's Month by month table — DEF-CUS-10162 / DEF-CUS-5146,
// PO ruling 2026-10-15 ("USAGE TAB MONTH BY MONTH"). Opens each account's
// Usage tab, screenshots the table and reads every row back by column.
// Env: WEB (SPA origin), TENANT, OUT, ACCOUNTS (comma list of account ids),
// PREFIX (shot name prefix, e.g. "before"/"after"), EMAIL, PASSWORD.
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8099";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-usage-months-2026-10-15";
const PREFIX = process.env.PREFIX || "after";
const ACCOUNTS = (process.env.ACCOUNTS || "").split(",").filter(Boolean);
mkdirSync(OUT, { recursive: true });

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: Number(process.env.WIDTH || 1440), height: 1000 } });
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));

try {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);

  for (const [index, id] of ACCOUNTS.entries()) {
    await page.goto(`${WEB}/${T}/accounts/${id}?tab=usage`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    const group = page.locator('[data-overview-group="usage-months"]');
    await group.waitFor({ timeout: 30000 });
    await group.scrollIntoViewIfNeeded();
    const table = await group.evaluate((el) => {
      const t = el.querySelector("table");
      const heads = [...t.querySelectorAll("thead th")].map((th) => th.innerText.trim());
      return {
        heads,
        rows: [...t.querySelectorAll("tbody tr")].map((tr) =>
          [...tr.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim()),
        ),
      };
    });
    console.log(`account ${id}`);
    console.log(`  ${table.heads.join(" | ")}`);
    for (const row of table.rows) console.log(`  ${row.join(" | ")}`);
    // The table's top (newest months). The app scrolls an inner container, not
    // the document, so: bring the group to the top of its scroller, step back
    // past the sticky header, and shoot the viewport.
    await group.evaluate((el) => {
      el.scrollIntoView({ block: "start" });
      let p = el.parentElement;
      while (p && p.scrollHeight <= p.clientHeight) p = p.parentElement;
      (p || document.scrollingElement).scrollBy(0, -90);
    });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${OUT}/${PREFIX}-${index + 1}-months-table.png` });
    await page.screenshot({ path: `${OUT}/${PREFIX}-${index + 1}-usage-tab.png`, fullPage: true });
    console.log(`  shots ${PREFIX}-${index + 1}-*.png`);
  }
} finally {
  await browser.close();
}
