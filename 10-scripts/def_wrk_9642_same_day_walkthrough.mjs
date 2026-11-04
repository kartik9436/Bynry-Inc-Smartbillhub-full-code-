// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-WRK-9642 · BR-MET-1189 — PO 2026-10-04: "take the reading records
//          in register and use date and highest consumption reading if it is
//          apprved and validated".
// Walks:   the accepted field job on E-5000, then E-5000's Reads tab, at 1440.
//          Prerequisite (PostgreSQL): a Meter set job raised on E-5000, closed by
//          R. Patel through 10-scripts/technician_api_walk.py with the opening
//          register 3412 on the day the office read 3400, and accepted by Dana.
// Run:     BASE=http://127.0.0.1:5199 ASSET=<E-5000 id> ORDER=WO-0041 \
//          node 10-scripts/def_wrk_9642_same_day_walkthrough.mjs
// ───────────────────────────────────────────────────────
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5199";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ASSET = process.env.ASSET;
const ORDER = process.env.ORDER ?? "WO-0041";
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = process.env.OUT ?? new URL("../08-qa/work-2026-10-04/sameday/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([page.waitForLoadState("networkidle"), page.keyboard.press("Enter")]);
await page.waitForTimeout(1500);

await page.goto(`${BASE}/${TENANT}/work/orders/${ORDER}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}01-order-accepted.png`, fullPage: false });
const orderText = await page.locator("main").innerText().catch(() => "");
console.log("ORDER accepted shown:", /Accepted/i.test(orderText));

await page.goto(`${BASE}/${TENANT}/assets/${ASSET}?tab=reads`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
const table = page.locator("table").filter({ hasText: "Counts for billing" }).first();
await table.scrollIntoViewIfNeeded().catch(() => {});
await page.screenshot({ path: `${OUT}02-e5000-reads-counted.png`, fullPage: false });
const text = await page.locator("main").innerText().catch(() => "");
const lines = text.split("\n").filter((l) => /3,?400|3,?412|Counts for billing|Kept as history/.test(l));
console.log(lines.join("\n"));
console.log("VERDICT counts:", /Counts for billing/.test(text), "history:", /Kept as history/.test(text));
await browser.close();
