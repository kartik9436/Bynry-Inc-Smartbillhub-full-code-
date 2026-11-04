// Walk of the Accounts list's Account age and Aging — DEF-CUS-10180 /
// DEF-CUS-10181, PO ruling 2026-10-17 ("ACCOUNT AGE ON THE ACCOUNTS LIST;
// AGING STAYS MONEY AND IS FIXED TO READ BILLS"). Prints every visible row's
// account number, Aging and Account age cells; screenshots each step.
// Env: WEB (SPA origin), TENANT, OUT, EMAIL, PASSWORD.
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
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
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  acceptDownloads: true,
});
const page = await context.newPage();
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));

async function rows(label) {
  await page.waitForSelector("table tbody tr", { timeout: 60000 });
  await page.waitForTimeout(1200);
  const data = await page.evaluate(() => {
    const heads = [...document.querySelectorAll("table thead th")].map((th) =>
      th.innerText.replace(/[▲▼]/g, "").replace(/\s+/g, " ").trim().toUpperCase(),
    );
    const ia = heads.indexOf("ACCOUNT");
    const ig = heads.indexOf("AGING");
    const iage = heads.indexOf("ACCOUNT AGE");
    return {
      heads,
      rows: [...document.querySelectorAll("table tbody tr")].map((tr) => {
        const td = [...tr.querySelectorAll("td")].map((c) => c.innerText.replace(/\s+/g, " ").trim());
        return [td[ia], td[ig], td[iage]];
      }),
    };
  });
  console.log(`== ${label}`);
  console.log(`   headers: ${data.heads.join(" | ")}`);
  for (const r of data.rows) console.log(`   ${r.join(" | ")}`);
  return data;
}

async function shot(name) {
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log(`   shot ${name}.png`);
}

async function list(query) {
  await page.goto(`${WEB}/${T}/accounts?${query}`, { waitUntil: "networkidle" });
}

try {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);

  await list("per=25");
  await rows("1 default list (newest first) — Account age column next to Aging");
  await shot("1-account-age-column");

  await list("sort=account_age&dir=asc&per=25");
  await rows("2 Account age ascending — oldest first");
  await shot("2-sort-oldest-first");

  await list("sort=account_age&dir=desc&per=100");
  const desc = await rows("3 Account age descending — newest first, Not opened last");
  await shot("3-sort-newest-first");
  await page.evaluate(() => {
    const scroller = [...document.querySelectorAll("*")].find(
      (el) => el.scrollHeight > el.clientHeight + 50 && getComputedStyle(el).overflowY !== "visible",
    );
    (scroller || document.scrollingElement).scrollTop = 1e6;
  });
  await page.waitForTimeout(600);
  await shot("3b-sort-newest-first-bottom");
  writeFileSync(`${OUT}/sort-desc-rows.txt`, desc.rows.map((r) => r.join(" | ")).join("\n") + "\n");

  for (const [q, name, label] of [
    ["q=AC-2026-00042", "4-closed-account", "4 closed account — stopped ageing"],
    ["q=A-12048", "5-pending-not-opened", "5 pending activation — Not opened"],
    ["q=AC-2026-00051", "6-reopened-restarted", "6 reopened 10/14/2026 — restarted"],
    ["q=A-2012-OLD", "7-imported-2012", "7 imported with Opened 03/01/2012"],
    ["q=AC-2026-00001", "8-bill-77-days-overdue", "8 bill due 08/01/2026 unpaid — Aging"],
  ]) {
    await list(q);
    await rows(label);
    await shot(name);
  }

  await list("f.ageing=d61_90&per=25");
  await rows("9 Aging filter 61–90");
  await shot("9-aging-filter-61-90");

  await list("sort=ageing&dir=desc&per=25");
  await rows("10 Aging sort — oldest unpaid money first");
  await shot("10-aging-sort-desc");

  // The download — the shared control on the toolbar.
  await list("sort=account_age&dir=asc&per=25");
  await page.waitForSelector("table tbody tr");
  const button = page.getByRole("button", { name: /download|export/i }).first();
  await button.click();
  await page.waitForTimeout(500);
  await shot("11-download-requested");
  // This sandbox has no file storage (DOCUMENT_STORAGE_BUCKET unset), so the
  // job builds the file and cannot publish it; the screen's answer is shot
  // as-is and the same bytes are written by the prep script's --csv mode.
  await page.waitForTimeout(8000);
  await shot("11b-download-outcome");
  console.log("== 11 download requested; outcome shot 11b");
} finally {
  await browser.close();
}
