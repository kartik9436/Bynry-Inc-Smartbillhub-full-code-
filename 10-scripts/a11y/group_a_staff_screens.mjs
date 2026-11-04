// ── Trace ──────────────────────────────────────────────
// Ask:      Portal a11y Group A, the eight decisions (decision log 2026-10-23):
//           decisions 6 (staff fields filled white) and 7 (staff primary
//           buttons take the contrast-picked ink). Lane A11Y-A-FINISH.
// ───────────────────────────────────────────────────────
/**
 * group_a_staff_screens — READ-ONLY. Signs a staff user in, opens five staff
 * screens, takes a full-page screenshot of each and measures what decisions 6
 * and 7 change: every visible primary button's text on its fill, and every
 * visible text field's border on its fill.
 *
 *   BASE=http://127.0.0.1:4331 STAFF_EMAIL=… STAFF_PASSWORD=… \
 *     node 10-scripts/a11y/group_a_staff_screens.mjs --out=<dir> --label=before
 *
 * Fake data only (the `seed_portal_demo` fixture). Prints one line per screen
 * and writes <out>/<label>-<screen>.png and <out>/<label>.json.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a sign-in that did not take (every
 * screen is the sign-in page) — the run refuses unless the URL left /signin;
 * a screen with no field or button measured — its count is printed beside it.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, "..", "..", "07-frontend");
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, v] = a.replace(/^--/, "").split("=");
    return [k, v ?? true];
  }),
);
const require = createRequire(join(FRONTEND, "package.json"));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4331";
const TENANT = process.env.TENANT ?? "pine-hill";
const OUT = resolve(String(args.out ?? "."));
const LABEL = String(args.label ?? "run");
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SCREENS = [
  ["dashboard", "/dashboard"],
  ["accounts", "/accounts"],
  ["premises", "/premises"],
  ["settings-company", "/settings"],
  ["bill-runs", "/billing"],
];

function ratio(a, b) {
  const lum = ([r, g, b2]) => {
    const f = (c) => {
      c /= 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b2);
  };
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100;
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", process.env.STAFF_EMAIL);
await page.fill("#signin-password", process.env.STAFF_PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !String(u).includes("/signin"), { timeout: 30000 });

const report = [];
for (const [name, path] of SCREENS) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("h1", { timeout: 20000 }).catch(() => null);
  await page.waitForTimeout(2500);
  const measured = await page.evaluate(() => {
    const rgb = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
    };
    const buttons = [...document.querySelectorAll('button[data-variant="primary"], .btn-primary')]
      .filter(visible)
      .map((el) => {
        const cs = getComputedStyle(el);
        return { text: el.textContent.trim().slice(0, 30), fg: rgb(cs.color), bg: rgb(cs.backgroundColor) };
      });
    const fields = [...document.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), select, textarea')]
      .filter(visible)
      .map((el) => {
        const cs = getComputedStyle(el);
        return { id: el.id || el.name || el.type, border: rgb(cs.borderTopColor), bg: rgb(cs.backgroundColor) };
      });
    return { h1: document.querySelector("h1")?.textContent?.trim() ?? null, buttons, fields };
  });
  const buttons = measured.buttons.map((b) => ({ ...b, ratio: ratio(b.fg, b.bg) }));
  const fields = measured.fields.map((f) => ({ ...f, ratio: ratio(f.border, f.bg) }));
  await page.screenshot({ path: join(OUT, `${LABEL}-${name}.png`), fullPage: true });
  const low = (list, floor) => list.filter((x) => x.ratio < floor).length;
  console.log(
    `${name.padEnd(18)} h1=${JSON.stringify(measured.h1)} primary buttons ${buttons.length} (under 4.5: ${low(buttons, 4.5)}; ` +
      `${[...new Set(buttons.map((b) => b.ratio))].join("/") || "-"}) · fields ${fields.length} (under 3: ${low(fields, 3)}; ` +
      `${[...new Set(fields.map((f) => f.ratio))].join("/") || "-"})`,
  );
  report.push({ name, path, h1: measured.h1, buttons, fields });
}
writeFileSync(join(OUT, `${LABEL}.json`), JSON.stringify(report, null, 2));
await browser.close();
