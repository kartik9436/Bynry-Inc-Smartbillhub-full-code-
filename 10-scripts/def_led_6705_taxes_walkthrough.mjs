// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6705 / 6706 / 6707 / 6708 (2026-09-25, Product Owner,
//          deployed v2.351.84) — Finance > Taxes & Remittance printed
//          "Authority not named" above the authority's name, $0.00 billed,
//          "Not available" under Billed on bills, "Still owed -$65.00" and a
//          tie-out of $266.75 on the same screen.
// Rules:   BR-LED-007 · BR-BIL-069 · CLAUDE.md hard-won law 6 (no gate looks at
//          rendered output) · the brief's "reading a screen through innerText
//          lies about layout — capture the image"
// ───────────────────────────────────────────────────────
//
// RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING — a mid-run reseed looks
// exactly like a broken screen.
//
//   10-scripts/proof-db.sh clone taxlane --template sbh_tpl_finwire
//   DATABASE_URL=… manage.py runserver 127.0.0.1:8391 --noreload
//   (cd 07-frontend && npx vite build && PORT=8392 API_PROXY_TARGET=… node server.mjs)
//   BASE=http://127.0.0.1:8392 node 10-scripts/def_led_6705_taxes_walkthrough.mjs
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.BASE ?? "http://127.0.0.1:8392";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def_led_6705";
mkdirSync(OUT, { recursive: true });

// The box holds chromium-1194 and this checkout's playwright wants 1234;
// point at the binary that IS installed rather than reinstalling browsers.
const browser = await chromium.launch(
  process.env.CHROME ? { executablePath: process.env.CHROME } : {},
);
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const problems = [];
page.on("response", (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) problems.push(`${r.status()} ${r.url()}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log("signed in");

await page.goto(`${BASE}/${TENANT}/finance/taxes`, { waitUntil: "domcontentloaded" });
// Wait for the TABLE BODY, never for the panel head — a head renders while the
// table is still a skeleton, and a probe that fires then reads an empty product.
await page.waitForSelector('[data-fin="authority-name"]', { timeout: 30000 });
await page.waitForTimeout(600);
writeFileSync(`${OUT}/taxes.png`, await page.screenshot({ fullPage: true }));

// ⚠ innerText lies about LAYOUT, not about VALUES: the image above is the
// layout proof and these reads are the arithmetic proof. Both, never one.
const names = await page.locator('[data-fin="authority-name"]').allInnerTexts();
const bills = await page.locator('[data-fin="billed-from-bills"]').allInnerTexts();
const body = await page.locator("main").innerText();
const notNamed = (body.match(/Authority not named/g) ?? []).length;
console.log("authority names:", JSON.stringify(names));
console.log("billed-on-bills cells:", JSON.stringify(bills.map((b) => b.split("\n")[0])));
console.log("'Authority not named' occurrences:", notNamed);
console.log("--- the By authority table, row by row ---");
for (const row of await page.locator("table tbody tr, table tfoot tr").all()) {
  console.log("  ", (await row.innerText()).replace(/\n/g, " | "));
}
console.log("--- tie-out region ---");
console.log(body.match(/Ties out[\s\S]{0,200}/)?.[0] ?? "(tie-out panel not found)");
console.log("4xx/5xx:", problems.length ? problems : "none");
await browser.close();
