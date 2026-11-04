/**
 * cr168_work_map_clusters_walk — CR-168-BRC10 round 3, lane MAP2: P3.1 (jobs at
 * one place cluster, every order reachable) and P3.2 (a mark opens the ORDER,
 * never its edit page), walked in Chromium at 1440 as Dana.
 *
 *     BASE=http://127.0.0.1:5541 node 10-scripts/cr168_work_map_clusters_walk.mjs
 *
 * Photographs image 24's state into
 *   08-qa/work-2026-10-04/after/24-map-the-day-on-the-ground.png
 * and the list of one place's jobs into 24c-map-one-place-opened.png.
 *
 * What it PROVES rather than draws (DEF-WRK-9598 was a screen where a count of
 * buttons said 17 and a mouse could reach 5):
 *   1. every order the map read serves as a pin is reachable — by clicking the
 *      single pins and, for each cluster, every job in its list — and each one
 *      lands on /work/orders/<id> with no /edit (DEF-WRK-9576);
 *   2. by KEYBOARD alone: Tab to a cluster, Enter, Enter lands on an order;
 *   3. the key is on screen and says what the two marks mean.
 *
 * It also prints how many map tiles actually DREW, and does not infer streets
 * from a request: this container has no route to the tile host, so the
 * expected answer here is 0.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5541";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("#signin-email", { timeout: 60000 });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

const MAP = `${BASE}/${TENANT}/work/map`;
async function openMap() {
  await page.goto(MAP, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-pin], [data-cluster]", { timeout: 60000 });
  await page.waitForTimeout(2500);
}
await openMap();

// What the server says is on the map — the denominator for "every order".
const served = await page.evaluate(async (tenant) => {
  const res = await fetch(`/api/${tenant}/work-orders/map`, { credentials: "include" });
  const data = await res.json();
  return data.pins.map((p) => ({ id: p.id, order_no: p.order_no }));
}, TENANT);
const marks = await page.evaluate(() => ({
  pins: [...document.querySelectorAll("[data-pin]")].map((b) => b.getAttribute("data-pin")),
  clusters: [...document.querySelectorAll("[data-cluster]")].map((b) => ({
    key: b.getAttribute("data-cluster"),
    count: Number(b.textContent),
    hollow: b.getAttribute("data-hollow"),
    label: b.getAttribute("aria-label"),
  })),
  key: document.querySelector("[data-map-key]")?.innerText.replace(/\n+/g, " · ") ?? null,
  tiles: document.querySelectorAll('[data-map="work-orders"] img.leaflet-tile').length,
  tilesDrawn: [...document.querySelectorAll('[data-map="work-orders"] img.leaflet-tile')].filter(
    (i) => i.complete && i.naturalWidth > 0,
  ).length,
}));
await page.screenshot({ path: `${OUT}/24-map-the-day-on-the-ground.png`, fullPage: false });
console.log(`photo        : ${OUT}/24-map-the-day-on-the-ground.png`);
console.log(`served pins  : ${served.length}`);
console.log(`marks drawn  : ${marks.pins.length} single + ${marks.clusters.length} clusters = ${marks.pins.length + marks.clusters.length}`);
for (const c of marks.clusters) console.log(`   cluster ${c.count}${c.hollow === "true" ? " (hollow)" : ""} — ${c.label}`);
console.log(`key          : ${marks.key ?? "(none)"}`);
console.log(`map tiles    : ${marks.tiles} asked for, ${marks.tilesDrawn} drew`);
if (marks.key === null) fail("no key on the map");
const inClusters = marks.clusters.reduce((n, c) => n + c.count, 0);
if (marks.pins.length + inClusters !== served.length)
  fail(`marks account for ${marks.pins.length + inClusters} orders, the server served ${served.length}`);

// ── 1 · every order reachable by mouse, and each lands on the ORDER ─────────
const reached = new Set();
async function landed(expectId) {
  await page.waitForURL((u) => /\/work\/orders\//.test(u.pathname), { timeout: 15000 }).catch(() => undefined);
  const path = new URL(page.url()).pathname;
  if (path.endsWith("/edit")) fail(`opened the EDIT page: ${path}`);
  else if (!path.endsWith(`/work/orders/${expectId}`)) fail(`expected /work/orders/${expectId}, got ${path}`);
  else reached.add(expectId);
}
const byNo = new Map(served.map((p) => [p.order_no ?? p.id, p.id]));
for (const pin of marks.pins) {
  await openMap();
  await page.locator(`[data-pin="${pin}"]`).click();
  await landed(byNo.get(pin));
}
let shotPanel = false;
for (const cluster of marks.clusters) {
  await openMap();
  await page.locator(`[data-cluster="${cluster.key}"]`).click();
  const jobs = await page.$$eval(`[data-cluster-panel] [data-cluster-job]`, (bs) =>
    bs.map((b) => b.getAttribute("data-cluster-job")),
  );
  if (jobs.length !== cluster.count) fail(`cluster of ${cluster.count} listed ${jobs.length}`);
  if (!shotPanel) {
    await page.screenshot({ path: `${OUT}/24c-map-one-place-opened.png`, fullPage: false });
    console.log(`photo        : ${OUT}/24c-map-one-place-opened.png — ${await page.locator("[data-cluster-panel]").innerText()}`.replace(/\n+/g, " · "));
    shotPanel = true;
  }
  for (const job of jobs) {
    await openMap();
    await page.locator(`[data-cluster="${cluster.key}"]`).click();
    await page.locator(`[data-cluster-job="${job}"]`).click();
    await landed(byNo.get(job));
  }
}
if (reached.size === served.length) ok(`all ${served.length} orders reached by mouse, each on its own page`);
else fail(`reached ${reached.size} of ${served.length} orders`);

// ── 2 · keyboard alone ──────────────────────────────────────────────────────
if (marks.clusters.length > 0) {
  await openMap();
  const first = marks.clusters[0].key;
  let focused = false;
  for (let i = 0; i < 80 && !focused; i += 1) {
    await page.keyboard.press("Tab");
    focused = await page.evaluate((k) => document.activeElement?.getAttribute("data-cluster") === k, first);
  }
  if (!focused) fail("Tab never reached the first cluster");
  else {
    await page.keyboard.press("Enter");
    await page.waitForSelector("[data-cluster-panel]");
    await page.keyboard.press("Enter");
    await page.waitForURL((u) => /\/work\/orders\/[^/]+$/.test(u.pathname), { timeout: 15000 }).catch(() => undefined);
    const path = new URL(page.url()).pathname;
    if (/\/work\/orders\/[^/]+$/.test(path)) ok(`keyboard: Tab · Enter · Enter opens ${path.replace(`/${TENANT}`, "")}`);
    else fail(`keyboard did not open an order (at ${path})`);
  }
}

await browser.close();
if (problems.length > 0) {
  console.log(`\nFAILED — ${problems.length} problem(s)`);
  process.exit(1);
}
console.log("\nPASSED");
