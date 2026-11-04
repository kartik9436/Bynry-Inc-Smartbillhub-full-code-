/**
 * cr168_work_map_walk — CR-168-BRC10 P3.3 (lane W-MAP): the Work map's street
 * ground, walked in a browser at 1440 as Dana, TWICE.
 *
 *     BASE=http://127.0.0.1:5471 node 10-scripts/cr168_work_map_walk.mjs
 *
 * Run 1 — as shipped. Photographs image 24's state into
 *   08-qa/work-2026-10-04/after/24-map-the-day-on-the-ground.png
 * and records EVERY tile request: its URL, whether it was answered, and how
 * many tile images actually LOADED (`naturalWidth > 0`). A requested tile and a
 * drawn tile are different facts (`def_map_walkthrough.mjs`, DEF-INT-4287), so
 * both are printed and neither is inferred from the other.
 *
 * ⚠ **THE BUILT DOCUMENT CARRIES A BAKED-IN CONTENT-SECURITY-POLICY WHOSE
 * `img-src` DOES NOT NAME THE TILE HOST (`DEF-INT-7430`, open, the Assets
 * map's too).** So as shipped the BROWSER refuses every tile before a request
 * leaves it, and Playwright sees no request at all. Run 1 therefore records
 * the refusals the console prints and the `src` of every tile `<img>` the map
 * asked for; run 1b repeats with the page policy bypassed so the tile requests
 * actually go out and their network outcome is logged.
 *
 * Run 2 — the tile host BLOCKED (every request to it aborted by the browser).
 * Proves the condition P3.3 sets: the pins and the *not on the map* list still
 * work — a pin is clicked and must navigate, the strip's first order is
 * clicked and must navigate. Photographed as 24b-map-tiles-blocked.png.
 *
 * The tile HOST is read off the page (`data-tile-host`, which the screen takes
 * from the page policy's `tile_host`), never typed here.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5471";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const problems = [];
const fail = (m) => {
  problems.push(m);
  console.log(`FAIL  ${m}`);
};
const ok = (m) => console.log(`ok    ${m}`);

const browser = await chromium.launch({ executablePath: resolveChromium() });

async function walk({ label, block, shotName, bypassCSP = false }) {
  console.log(`\n── ${label} ──`);
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, bypassCSP });
  const page = await context.newPage();
  const tiles = [];
  const refusals = [];
  page.on("console", (m) => {
    if (/Content Security Policy/i.test(m.text()) && /tile/.test(m.text())) refusals.push(m.text());
  });
  const isTile = (url) => /\/tile\/\d+\/\d+\/\d+/.test(url);
  page.on("request", (r) => {
    if (isTile(r.url())) tiles.push({ url: r.url(), outcome: "pending" });
  });
  page.on("requestfinished", async (r) => {
    const row = tiles.find((t) => t.url === r.url() && t.outcome === "pending");
    if (row) row.outcome = `answered ${(await r.response())?.status() ?? "?"}`;
  });
  page.on("requestfailed", (r) => {
    const row = tiles.find((t) => t.url === r.url() && t.outcome === "pending");
    if (row) row.outcome = `failed: ${r.failure()?.errorText ?? "?"}`;
  });
  if (block) await page.route(isTile, (route) => route.abort("blockedbyclient"));

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#signin-email", { timeout: 60000 });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }).catch(async (e) => {
    await page.screenshot({ path: `${OUT}/W-MAP-signin-failed.png` });
    throw e;
  });
  await page.goto(`${BASE}/${TENANT}/work/map`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-pin]", { timeout: 60000 });
  await page.waitForTimeout(6000);

  const seen = await page.evaluate(() => {
    const box = document.querySelector('[data-map="work-orders"]');
    const canvas = document.querySelector('[data-map="work-orders"] [data-map-canvas]');
    const imgs = [...document.querySelectorAll('[data-map="work-orders"] img.leaflet-tile')];
    const pins = [...document.querySelectorAll("[data-pin]")].map((pin) => {
      const r = pin.getBoundingClientRect();
      const b = box.getBoundingClientRect();
      return {
        pin: pin.getAttribute("data-pin"),
        hollow: pin.getAttribute("data-hollow"),
        inside: r.left >= b.left && r.right <= b.right && r.top >= b.top && r.bottom <= b.bottom,
        left: pin.style.left,
      };
    });
    return {
      tileHost: canvas?.getAttribute("data-tile-host") ?? null,
      leaflet: canvas?.classList.contains("leaflet-container") ?? false,
      attribution:
        document.querySelector('[data-map="work-orders"] .leaflet-control-attribution')?.textContent?.trim() ?? "",
      tileImgs: imgs.length,
      tileSrcs: imgs.map((i) => i.getAttribute("src")),
      tilesLoaded: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
      pins,
      unplaced: document.querySelectorAll("[data-unplaced]").length,
    };
  });
  await page.screenshot({ path: `${OUT}/${shotName}`, fullPage: false });
  console.log(`photo        : ${OUT}/${shotName}`);
  console.log(`tile_host    : ${seen.tileHost || "(none)"}`);
  console.log(`leaflet map  : ${seen.leaflet}`);
  console.log(`attribution  : ${seen.attribution || "(none)"}`);
  console.log(`tile <img> src: ${seen.tileSrcs.length} asked for, e.g. ${seen.tileSrcs[0] ?? "(none)"}`);
  console.log(`CSP refusals : ${refusals.length}${refusals[0] ? ` — ${refusals[0].slice(0, 200)}` : ""}`);
  console.log(`tile requests: ${tiles.length}`);
  const outcomes = {};
  for (const t of tiles) outcomes[t.outcome] = (outcomes[t.outcome] ?? 0) + 1;
  for (const [k, v] of Object.entries(outcomes)) console.log(`   ${v} × ${k}`);
  for (const t of tiles.slice(0, 3)) console.log(`   e.g. ${t.url}`);
  console.log(`tile <img>   : ${seen.tileImgs} in the DOM, ${seen.tilesLoaded} actually drawn`);
  console.log(`pins         : ${seen.pins.length} (${seen.pins.filter((p) => p.hollow === "true").length} hollow), placed in px by the map: ${seen.pins.every((p) => p.left.endsWith("px"))}`);
  console.log(`not on map   : ${seen.unplaced}`);

  if (!seen.leaflet) fail(`${label}: no Leaflet map under the pins`);
  if (!/Esri/.test(seen.attribution)) fail(`${label}: no "Tiles © Esri" attribution`);
  if (!seen.tileHost) fail(`${label}: no tile_host on the canvas`);
  const asked = [...new Set([...seen.tileSrcs, ...tiles.map((t) => t.url)])];
  if (asked.length === 0) fail(`${label}: the map never asked for a tile`);
  else if (!asked.every((u) => seen.tileHost && u.startsWith(seen.tileHost)))
    fail(`${label}: a tile was asked of a host the policy did not name`);
  else ok(`${label}: ${asked.length} tiles asked of ${seen.tileHost}`);
  if (seen.pins.length === 0) fail(`${label}: no pins`);
  if (!seen.pins.every((p) => p.inside)) fail(`${label}: a pin sits outside the map box`);

  // The pins and the list must WORK, not merely be drawn.
  // The LAST pin in the DOM is the one painted on top: several jobs at one
  // address stack exactly (clustering is P3.1, not this task).
  const first = seen.pins[seen.pins.length - 1]?.pin;
  if (first) {
    const before = page.url();
    await page.locator(`[data-pin="${first}"]`).click();
    await page.waitForURL((u) => u.toString() !== before, { timeout: 15000 }).catch(() => undefined);
    if (page.url() === before) fail(`${label}: clicking pin ${first} did nothing`);
    else ok(`${label}: pin ${first} opens ${page.url().replace(BASE, "")}`);
    await page.goBack();
    await page.waitForSelector("[data-pin]", { timeout: 30000 });
  }
  if (seen.unplaced > 0) {
    const before = page.url();
    await page.locator("[data-unplaced] button").first().click();
    await page.waitForURL((u) => u.toString() !== before, { timeout: 15000 }).catch(() => undefined);
    if (page.url() === before) fail(`${label}: clicking the strip's first order did nothing`);
    else ok(`${label}: the strip's first order opens ${page.url().replace(BASE, "")}`);
  }
  await context.close();
  return { label, ...seen, tiles, refusals };
}

const shipped = await walk({ label: "as shipped", block: false, shotName: "24-map-the-day-on-the-ground.png" });
const network = await walk({
  label: "page policy bypassed — do the tile requests leave the browser?",
  block: false,
  bypassCSP: true,
  shotName: "24a-map-policy-bypassed.png",
});
const blocked = await walk({
  label: "tile host blocked",
  block: true,
  bypassCSP: true,
  shotName: "24b-map-tiles-blocked.png",
});
writeFileSync(`${OUT}/W-MAP-network-log.json`, JSON.stringify({ shipped, network, blocked, problems }, null, 2));
console.log(`\nnetwork log  : ${OUT}/W-MAP-network-log.json`);
await browser.close();
if (problems.length > 0) {
  console.log(`\nFAILED — ${problems.length} problem(s)`);
  process.exit(1);
}
console.log("\nPASSED");
