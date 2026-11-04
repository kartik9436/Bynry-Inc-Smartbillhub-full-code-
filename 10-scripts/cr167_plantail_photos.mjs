// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 after close (lane PLAN-TAIL) — DEF-RAT-9519 on screen
//          at 1440: the New form's Charges step and Review for a Residential
//          plan with both taxes, and the details Overview + Charges tab of the
//          Residential and Commercial plans `cr167_plantail_taxes_pg.py` billed.
//   BASE=http://127.0.0.1:5391 RES=<id> COM=<id> OUT=08-qa/plans-2026-10-03/tail \
//     node 10-scripts/cr167_plantail_photos.mjs
// ───────────────────────────────────────────────────────
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");
const BASE = process.env.BASE ?? "http://127.0.0.1:5391";
const OUT = process.env.OUT ?? "08-qa/plans-2026-10-03/tail";
const TENANT = "brazosbend";
const PLANS = "plans-rates/plans";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    if (!dir.startsWith("chromium")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
      if (existsSync(join("/opt/pw-browsers", dir, sub))) return join("/opt/pw-browsers", dir, sub);
    }
  }
  throw new Error("no chromium found");
}
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const settle = (ms = 600) => page.waitForTimeout(ms);
const shot = async (name) => {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log("[shot]", name);
};
const text = async (sel = "main") => (await page.innerText(sel).catch(() => "")).replace(/\s+/g, " ");
const click = (name) => page.getByRole("button", { name, exact: true }).click();
async function pickLast(label, want) {
  const boxes = page.getByRole("combobox", { name: label, exact: true });
  const box = boxes.nth((await boxes.count()) - 1);
  const value = await box.evaluate((el, w) => [...el.options].find((o) => o.textContent.includes(w))?.value ?? null, want);
  if (value === null) throw new Error(`no ${want} in ${label}`);
  await box.selectOption(value);
}
const results = [];
const check = (what, pass, evidence) => {
  results.push({ what, pass });
  console.log(`${pass ? "PASS" : "FAIL"} ${what} — ${String(evidence ?? "").slice(0, 300)}`);
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// The details screens of the two billed plans.
for (const [key, id, want] of [["res", process.env.RES, "2.00%"], ["com", process.env.COM, "8.25%"]]) {
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}`, { waitUntil: "networkidle" });
  await settle(1200);
  await shot(`${key}-1-overview`);
  const overview = await text();
  check(`${key} Overview Taxes tile reads ${want}`, overview.includes(want), overview.match(/.{0,40}combined.{0,20}/)?.[0]);
  await page.goto(`${BASE}/${TENANT}/${PLANS}/${id}?tab=charges`, { waitUntil: "networkidle" });
  await page.locator("[data-plan-priced-tab=charges]").waitFor();
  await shot(`${key}-2-charges-tab`);
  const taxes = await text('[data-plan-section="taxes"]');
  check(`${key} Charges tab: "${want} combined"`, taxes.includes(`${want} combined`), taxes);
  check(
    `${key} Charges tab: the state tax ${key === "res" ? "IS" : "is NOT"} marked`,
    taxes.includes("Not charged to this plan's classes") === (key === "res"),
    taxes,
  );
}

// The New form, Residential, both taxes: step 3 and Review.
await page.goto(`${BASE}/${TENANT}/${PLANS}/new`, { waitUntil: "networkidle" });
await page.getByLabel(/^Plan name/).waitFor();
await page.getByLabel(/^Plan name/).fill("Tail · Residential");
await page.getByLabel(/^Code/).fill("PT-NEW");
await page.getByRole("button", { name: /^Customer classes/ }).click();
await page.getByRole("checkbox", { name: "Residential", exact: true }).check();
await page.keyboard.press("Escape");
await click("Continue");
await page.getByText("Services and rate schedules").waitFor();
await click("+ Add service");
await pickLast("Service", "Water");
await pickLast("Rate schedule", "Sample — Residential water");
await click("Continue");
await page.getByRole("button", { name: "+ Add tax" }).waitFor();
await click("+ Add tax");
await pickLast("Tax", "TX State Utility Tax");
await click("+ Add tax");
await pickLast("Tax", "Bexar");
await settle(1000);
await shot("new-3-charges-taxes");
const step3 = await text('[data-array="plan-taxes"]');
check("New step 3: the state tax is marked, combined 2.00%", step3.includes("Not charged to this plan's classes") && step3.includes("2.00%") && !step3.includes("8.25%"), step3);
await click("Continue");
await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
await click("Continue");
await page.getByRole("button", { name: "Publish plan" }).waitFor();
await settle(1000);
await shot("new-5-review");
await page.locator('[data-plan-section="taxes"]').scrollIntoViewIfNeeded();
await shot("new-5-review-taxes");
const review = await text('[data-plan-section="taxes"]');
check("New Review: the state tax is marked, 2.00% combined", review.includes("Not charged to this plan's classes") && review.includes("2.00% combined"), review);
const summary = await text();
check("New Review: nowhere says 8.25%", !summary.includes("8.25%"), summary.match(/.{0,40}8\.25%.{0,20}/)?.[0]);

await browser.close();
const failed = results.filter((r) => !r.pass).length;
console.log(`${results.length - failed}/${results.length} pass`);
process.exit(failed ? 1 : 0);
