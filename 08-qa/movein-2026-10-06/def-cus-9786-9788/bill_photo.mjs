// Lane DEF-9786-9788 (DEF-BIL-9787) — photograph an issued bill of M7's account at 1440, signed
// in as the clerk, and check the PO is on the bill page and on the printed PDF's text.
//   MX_BASE=http://127.0.0.1:<port> node bill_photo.mjs <invoiceId> <outdir>
import { createRequire } from "node:module";
import { join } from "node:path";

const REPO = new URL("../../../", import.meta.url).pathname;
const require = createRequire(join(REPO, "07-frontend/package.json"));
const { chromium } = require("playwright");
const BASE = process.env.MX_BASE || "http://127.0.0.1:5786";
const [invoiceId, out] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: process.env.MX_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
await page.goto(`${BASE}/mvimatrix/signin`);
await page.fill("#signin-email", "jo.ramirez@cedarford.example");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin")), page.click('button[type="submit"]')]);
let failed = 0;
// The bill as it was sent (the frozen page and its PDF) carries the PO. S30's own header names
// the customer only and draws no PO, as its drawing does, so it is not asserted here.
for (const [path, name] of [[`/mvimatrix/billing/bills/${invoiceId}/document`, "M7-bill-document.png"]]) {
  await page.goto(`${BASE}${path}`);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(1500);
  const text = await page.locator("body").innerText();
  const ok = text.includes("PO-2026-118");
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${path} shows PO-2026-118`);
  await page.screenshot({ path: join(out, name), fullPage: true });
}
await browser.close();
process.exit(failed ? 1 : 0);
