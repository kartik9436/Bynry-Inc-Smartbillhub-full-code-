#!/usr/bin/env node
// DEF-WRK-9784 (maintenance, 2026-10-06) — the photograph the fix is judged by:
// a move-in's step 1, one Field visit row whose *For* is an ELECTRIC meter, its
// *Work order* list OPEN. The list must offer electric's visits and none of
// another service's. Read-only: it opens the wizard and never completes it.
//
// Usage (repo root; a matrix world from cr171_e2e_matrix_world.py, unit U-00006
// = M3, electric + gas, still vacant):
//   MX_BASE=http://127.0.0.1:5784 MX_OUT=<folder> MX_UNIT=U-00006 MX_METER=E- \
//   node 10-scripts/def_wrk_9784_field_visit_photo.mjs
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(REPO, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.MX_BASE || "http://127.0.0.1:5784";
const OUT = process.env.MX_OUT || join(REPO, "08-qa/movein-2026-10-06/def-wrk-9784");
const UNIT = process.env.MX_UNIT || "U-00006";
const METER = process.env.MX_METER || "E-";
const TENANT = process.env.MX_TENANT || "mvimatrix";
const CHROME = process.env.MX_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
page.setDefaultTimeout(30000);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", "jo.ramirez@cedarford.example");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin")), page.click('button[type="submit"]')]);
await page.goto(`${BASE}/${TENANT}/move-ins/new`, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => (document.querySelector("#mvi_unit")?.options.length ?? 0) > 1);
const unit = await page.$eval("#mvi_unit", (s, u) => [...s.options].find((o) => o.textContent.includes(u))?.value ?? "", UNIT);
if (!unit) throw new Error(`${UNIT} is not offered`);
await page.selectOption("#mvi_unit", unit);
await page.waitForSelector('[data-array="move-in-meters"] tbody tr');
await page.waitForLoadState("networkidle");
await page.click('[data-array-action="add-work-order"]');
const forOptions = await page.$$eval("#move_in-fv-0-for option", (os) => os.map((o) => ({ v: o.value, t: o.textContent })));
const meter = forOptions.find((o) => o.v.startsWith(METER));
if (!meter) throw new Error(`no ${METER} meter on ${UNIT}: ${JSON.stringify(forOptions)}`);
await page.selectOption("#move_in-fv-0-for", meter.v);
// The open list is drawn INSIDE the table's scroll box (DEF-WRK-9814), so the photograph
// gives the table five more rows of height to show it in. Typing narrows the list to the
// visit templates, which is what the defect is about.
for (let n = 0; n < 5; n += 1) await page.click('[data-array-action="add-work-order"]');
await page.locator("#move_in-fv-0-workOrder").click();
await page.keyboard.type("read");
await page.waitForTimeout(500);
const offered = await page.$$eval('[role="option"][id^="move_in-fv-0-workOrder"]', (os) => os.map((o) => o.textContent.trim()));
console.log(`For ${meter.v}: ${offered.length} entries`);
for (const label of offered) console.log(`  ${label}`);
const panel = page.locator('[data-field-visit-layout="panel"]');
await panel.scrollIntoViewIfNeeded();
await page.waitForTimeout(300);
await page.screenshot({ path: join(OUT, `field-visit-list-${meter.v}.png`), fullPage: false });
await browser.close();
