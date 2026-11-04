// Lane DEF-9786-9788 (DEF-CUS-9808) — Settings › Reference data › Account types at 1440, as the
// utility's admin: stop offering Government, photograph, offer it again, photograph.
//   MX_BASE=http://127.0.0.1:<port> node settings_photo.mjs <outdir>
import { createRequire } from "node:module";
import { join } from "node:path";

const REPO = new URL("../../../", import.meta.url).pathname;
const require = createRequire(join(REPO, "07-frontend/package.json"));
const { chromium } = require("playwright");
const BASE = process.env.MX_BASE || "http://127.0.0.1:5786";
const [out] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: process.env.MX_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await page.goto(`${BASE}/mvimatrix/signin`);
await page.fill("#signin-email", "marcus@cedarford.example");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin")), page.click('button[type="submit"]')]);
await page.goto(`${BASE}/mvimatrix/settings/reference-data?list=account_types`);
await page.waitForLoadState("networkidle").catch(() => undefined);
const row = page.locator("tr", { hasText: "Government" }).first();
let failed = 0;
const say = (ok, what) => { if (!ok) failed += 1; console.log(`${ok ? "PASS" : "FAIL"}  ${what}`); };
await row.getByRole("button", { name: "Stop offering" }).click();
await page.waitForTimeout(1500);
say((await row.innerText()).includes("Not offered"), "Government reads Not offered after Stop offering");
await page.screenshot({ path: join(out, "settings-account-types-not-offered.png"), fullPage: true });
await row.getByRole("button", { name: "Offer again" }).click();
await page.waitForTimeout(1500);
say((await row.innerText()).includes("Active"), "Government reads Active after Offer again");
await page.screenshot({ path: join(out, "settings-account-types-offered.png"), fullPage: true });
await browser.close();
process.exit(failed ? 1 : 0);
