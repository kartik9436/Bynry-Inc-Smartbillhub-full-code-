#!/usr/bin/env node
// Combined walk — a clerk posts closing readings through Reads > + Add reading.
// CW_READS='[["E-5000","2026-10-31","3950"],...]' CW_SHOT=S4-0
import { open, BASE, T } from "./combined_walk_2026_10_14_lib.mjs";

const READS = JSON.parse(process.env.CW_READS || "[]");
const SHOT = process.env.CW_SHOT || "S4-0";
const w = await open({ clock: process.env.CW_CLOCK });
const { page, check, shot } = w;
try {
  await w.staff();
  let i = 0;
  for (const [meter, date, value] of READS) {
    i += 1;
    await page.goto(`${BASE}/${T}/reads`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "+ Add reading" }).click();
    await page.fill("#meter_no", meter);
    await page.locator("#meter_no").press("Tab");
    await page.waitForSelector('[data-testid="quick-read-meter"]', { timeout: 20000 });
    await page.fill("#read_date", date);
    await page.locator("#read_date").press("Tab");
    await page.fill("#reading", value);
    const posted = page
      .waitForResponse((r) => r.request().method() === "POST" && /\/read-batches\/[^/]+\/post$/.test(r.url()), { timeout: 30000 })
      .then(async (r) => ({ status: r.status(), body: await r.text() }))
      .catch(() => null);
    await page.getByRole("button", { name: /Post reading/ }).click();
    const res = await posted;
    check(`${meter} ${date} = ${value} posts`, res && res.status < 300, res ? String(res.status) : "no response");
    await shot(`${SHOT}-${i}-${meter}.png`);
  }
} catch (e) {
  check("reads ran to the end", false, String(e).split("\n")[0]);
}
process.exit(await w.done());
