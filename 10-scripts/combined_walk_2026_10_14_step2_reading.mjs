#!/usr/bin/env node
// Combined walk step 2 (CR-182) — a clerk posts a 10x water reading for Ana
// Alvarez (W-5000) through Reads > + Add reading; then Ana's portal Home and
// Readings are photographed. Env: CW_METER, CW_READ_DATE (YYYY-MM-DD), CW_VALUE.
import { open, BASE, T } from "./combined_walk_2026_10_14_lib.mjs";

const METER = process.env.CW_METER || "W-5000";
const DATE = process.env.CW_READ_DATE || "2026-10-13";
const VALUE = process.env.CW_VALUE || "1104";
const w = await open();
const { page, check, shot } = w;
try {
  await w.staff();
  await page.goto(`${BASE}/${T}/reads`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "+ Add reading" }).click();
  await page.fill("#meter_no", METER);
  await page.locator("#meter_no").press("Tab");
  await page.waitForSelector('[data-testid="quick-read-meter"]', { timeout: 20000 });
  await page.fill("#read_date", DATE);
  await page.locator("#read_date").press("Tab");
  await page.fill("#reading", VALUE);
  await shot("S2-1-staff-add-reading.png");
  const posted = page.waitForResponse((r) => r.request().method() === "POST" && /\/read-batches\/[^/]+\/post$/.test(r.url()), { timeout: 30000 })
    .then(async (r) => ({ status: r.status(), body: await r.text() })).catch(() => null);
  await page.getByRole("button", { name: /Post reading/ }).click();
  const res = await posted;
  check("the reading posts", res && res.status < 300, res ? `${res.status} ${res.body.slice(0, 200)}` : "no response");
  await shot("S2-2-staff-posted.png");

  // The portal, as Ana.
  await w.portal();
  await page.goto(`${BASE}/${T}/portal`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  const home = await page.locator("main").innerText();
  check("Home carries the high consumption alert", /High consumption alert/i.test(home),
    (home.match(/High consumption alert[^\n]*\n?[^\n]*/i) || [""])[0]);
  check("…naming the water reading as unusually high", /Water reading on [^\n]*unusually high/i.test(home));
  await shot("S2-3-portal-home-alert.png");
  await page.goto(`${BASE}/${T}/portal/readings`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  const readings = await page.locator("main").innerText();
  const tags = (readings.match(/High consumption alert/gi) || []).length;
  check("Readings tags exactly one row", tags === 1, `${tags} tag(s)`);
  await shot("S2-4-portal-readings-tag.png");
} catch (e) {
  check("step 2 ran to the end", false, String(e).split("\n")[0]);
  await page.screenshot({ path: `${process.env.CW_OUT || "05-prototype/combined-walk-2026-10-14"}/S2-FAILED.png`, fullPage: true }).catch(() => {});
}
process.exit(await w.done());
