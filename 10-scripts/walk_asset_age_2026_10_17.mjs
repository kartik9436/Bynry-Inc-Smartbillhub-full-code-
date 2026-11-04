// Walk of asset Age on the three Assets lists — DEF-AST-10178, PO ruling
// 2026-10-17 ("ASSET AGE ON METERS, SUB-METERS AND BEHIND-THE-METER LISTS").
// For each tab: sort Age oldest-first and newest-first, read the named rows
// back by column (Installed · Age), screenshot; then press Download on Meters.
// Env: WEB (SPA origin), TENANT, OUT, EMAIL, PASSWORD.
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8106";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-asset-age-2026-10-17";
mkdirSync(OUT, { recursive: true });

const WATCH = {
  meters: ["334556", "M-4022", "E-5001", "AST-04413"],
  sub_meters: ["SM-7040"],
  behind_the_meter: ["AST-00010", "BF-0002", "BAT-0001"],
};

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const context = await browser.newContext({
  viewport: { width: Number(process.env.WIDTH || 1440), height: 1000 },
  acceptDownloads: true,
});
const page = await context.newPage();
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));

async function readTable() {
  return page.evaluate(() => {
    const t = document.querySelector("main table") || document.querySelector("table");
    const heads = [...t.querySelectorAll("thead th")].map((th) => th.innerText.replace(/\s+/g, " ").trim());
    const rows = [...t.querySelectorAll("tbody tr")].map((tr) =>
      [...tr.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim()),
    );
    const danger = [...t.querySelectorAll("tbody tr")].map(
      (tr) => tr.querySelector("[data-age-cell] .text-danger-700") !== null,
    );
    return { heads, rows, danger };
  });
}

async function openTab(tab, dir) {
  const tabParam = tab === "meters" ? "" : `tab=${tab}&`;
  await page.goto(`${WEB}/${T}/assets?${tabParam}f.status=all&sort=age&dir=${dir}&per=100`, {
    waitUntil: "networkidle",
  });
  await page.locator("tbody tr").first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(800);
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

  for (const tab of Object.keys(WATCH)) {
    for (const dir of ["asc", "desc"]) {
      await openTab(tab, dir);
      const { heads, rows, danger } = await readTable();
      const iNo = 1;
      const iInst = heads.findIndex((h) => /^installed/i.test(h));
      const iAge = heads.findIndex((h) => /^age/i.test(h));
      console.log(`\n${tab} · sort=age dir=${dir} · ${rows.length} rows`);
      console.log(`  heads: ${heads.join(" | ")}`);
      console.log(`  first 5 by age: ${rows.slice(0, 5).map((r) => `${r[iNo]} (${r[iAge]})`).join(" · ")}`);
      {
        for (const no of WATCH[tab]) {
          const i = rows.findIndex((r) => r[iNo] === no);
          if (i < 0) {
            console.log(`  ${no}: not on this page`);
            continue;
          }
          console.log(
            `  ${no}: position ${i + 1} · Installed "${rows[i][iInst]}" · Age "${rows[i][iAge]}"${danger[i] ? " · RED" : ""}`,
          );
        }
      }
      await page.screenshot({ path: `${OUT}/${tab}-age-${dir}.png` });
    }
  }

  // The download of the Meters tab, sorted oldest first. A local machine has no
  // export bucket, so the job refuses with "File storage is not set up." — the
  // file itself is built by walk_asset_age_export_2026_10_17.py through the
  // kernel's own write path. This records what the screen says.
  await openTab("meters", "asc");
  await page.locator('[data-resource="assets"] button').first().click();
  await page.waitForTimeout(8000);
  console.log(`\ndownload notice: ${(await page.locator('[data-resource="assets"]').innerText()).replace(/\s+/g, " ")}`);
  await page.screenshot({ path: `${OUT}/meters-download-notice.png` });
} finally {
  await browser.close();
}
