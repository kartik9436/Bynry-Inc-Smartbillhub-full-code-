// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6728 — Finance > Close & export: the params band is one row
//          on THREE baselines. PO, deployed v2.351.84, tenant Ottumwa Water
//          Works: *"on close and export screen - filter is not align - it is
//          not in 1 line."*
// Rules:   B14 rule 44 / 38 / 43 / 21. CLAUDE.md hard-won law 6 — no gate in
//          this repo reads rendered output.
// ───────────────────────────────────────────────────────
//
// THE MEASUREMENT. `filterRow.dom.test.tsx` pins the two structural decisions;
// this is the only thing that can prove the controls actually share a baseline,
// because jsdom has no layout engine and returns zeroes for every rectangle.
//
// ⚠ **IT MUST RUN ON A TENANT WHOSE DATE FORMAT IS NOT THE BROWSER'S.** The
// sentence that broke the row is `regionalDateEcho` (IS-8) — the tenant's own
// format under the native date input, rendered ONLY when it differs from what
// the browser locale draws inside the control. `brazosbend` seeds
// `MM/DD/YYYY`, which is exactly what a headless Chromium draws, so the echo is
// `null`, the bar measures perfectly aligned, and the run proves nothing. Set
// the tenant to one of the other six first:
//
//     psql "$DATABASE_URL" -c "begin; set local app.tenant_id='<uuid>';
//        update tenant_settings set date_format='DD-MMM-YY'; commit;"
//
// ⚠ `app.tenant_id` MUST be inside a transaction or FORCE RLS returns zero rows
// and reads exactly like an empty tenant.
//
// Usage:  BASE=http://127.0.0.1:8612 TENANT=brazosbend \
//         EMAIL=… PASSWORD=… WIDTH=1440 node 10-scripts/finance_filter_row_baseline.mjs
//
// It exits 1 when the controls do not share a top, and prints every control's
// measured top either way — a check whose output cannot distinguish pass from
// fail to a READER is worse than no check (hard-won law 7 habit 3).
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8612";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const WIDTH = Number(process.env.WIDTH ?? 1440);
const SHOTS = process.env.SHOTS ?? "/tmp/def-led-6714";
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: 1100 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

await page.goto(`${BASE}/${TENANT}/finance/export?view=export`, { waitUntil: "domcontentloaded" });
await page.waitForSelector('[data-filter-row="export-params"]', { timeout: 20000 });
await page.waitForTimeout(1200);
writeFileSync(`${SHOTS}/export-params-${WIDTH}.png`, await page.screenshot());

const measured = await page.evaluate(() => {
  const row = document.querySelector('[data-filter-row="export-params"]');
  if (row === null) return { error: "the params band is not on the page" };
  const out = [];
  for (const ctrl of row.querySelectorAll("input, select, button")) {
    const cell = ctrl.closest("div");
    const under = cell?.querySelector(".field-help, .field-date-display") ?? null;
    out.push({
      control: ctrl.id || (ctrl.textContent || "").trim().slice(0, 20),
      top: Math.round(ctrl.getBoundingClientRect().top),
      under: under === null ? null : (under.textContent || "").trim().slice(0, 24),
    });
  }
  return { rowTop: Math.round(row.getBoundingClientRect().top), controls: out };
});

if (measured.error !== undefined) {
  console.error("FAIL " + measured.error);
  await browser.close();
  process.exit(1);
}

// One line of output per control, so a reader sees the answer and not an exit code.
for (const c of measured.controls) {
  console.log(`  ${String(c.control).padEnd(22)} top=${c.top}  under=${c.under ?? "-"}`);
}

const tops = new Set(measured.controls.map((c) => c.top));
// A stacked bar (phone width) is a different shape and is not what this checks.
const stacked = WIDTH < 640;
if (stacked) {
  console.log(`\nWIDTH=${WIDTH}: the band is STACKED, one control per line — nothing to align.`);
  console.log(`  ${measured.controls.length} controls, ${tops.size} distinct tops (expected: one each)`);
  await browser.close();
  process.exit(tops.size === measured.controls.length ? 0 : 1);
}
console.log(
  `\nWIDTH=${WIDTH}: ${measured.controls.length} controls on ${tops.size} baseline(s) ` +
    `— tops ${[...tops].sort((a, b) => a - b).join(", ")}`,
);
await browser.close();
if (tops.size === 1) {
  console.log("PASS — every control in the band shares one baseline.");
  process.exit(0);
}
console.error(
  `FAIL — DEF-LED-6728: the band is one row on ${tops.size} baselines. ` +
    "A field carrying a sentence under its control must not move that control.",
);
process.exit(1);
